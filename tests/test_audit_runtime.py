"""End-to-end offline auditing with complete collector fixtures."""

import asyncio
import hashlib
import json
import httpx
import subprocess
import sys
from pathlib import Path

from doc_azure import audit
from doc_azure import baselines
from delta.process_coverage import fingerprint_json
from doc_azure.snapshot import read_snapshot_artifact, read_snapshot_manifest
from tests.test_process_collector import expected_artifacts, seed_process_snapshot
from tests.test_process_collector import fixture_payloads
from tests.test_wiki_collector import seed_complete_wiki_snapshot, load_page_payloads
from tests.test_document_coverage import seed_baseline


def seed_run(root):
    seed_complete_wiki_snapshot(root)
    seed_process_snapshot(root)
    catalog = root / "claims.json"
    claims = []
    for page_id, slug in ((35, "leiame"), (10, "politicas"), (9, "changelog"), (37, "apendice")):
        contents = read_snapshot_artifact(root / "out/wiki", slug + ".md")
        claims.append({"id": f"{page_id}-LIMIT-001", "page_id": page_id, "slug": slug,
                       "finding": "Dimensão documental não verificável",
                       "doc": {"path": f"out/wiki/{slug}.md", "line": 1,
                               "excerpt": contents.decode().splitlines()[0],
                               "sha256": hashlib.sha256(contents).hexdigest(), "value": "descrito"},
                       "check": {"kind": "limitation", "implemented": "Não verificável pela API."},
                       "limit": "A API não representa esta dimensão."})
    catalog.write_text(json.dumps({"schema_version": 1, "claims": claims}))
    documents = seed_baseline(root, catalog)
    logical = root / "out/process"
    artifacts = {entry.path: json.loads(read_snapshot_artifact(logical, entry.path))
                 for entry in read_snapshot_manifest(logical).artifacts}
    inventory = root / "inventory.json"
    inventory.write_text(json.dumps({"schema_version": 1,
                                    "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
                                    "entries": fingerprint_json(artifacts)}))
    return catalog, documents, inventory


def run(root, inputs):
    return asyncio.run(audit.run_audit(root, *inputs, offline=True))


def test_offline_run_publishes_complete_bundle_without_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("AZDO_PAT", raising=False)
    result = run(tmp_path, seed_run(tmp_path))
    assert result.exit_code == 1
    summary = json.loads(read_snapshot_artifact(tmp_path / "out/audit", "run.json"))
    assert summary["status"] == "DELTAS"
    assert summary["coverage_complete"] is True
    assert len(summary["pages"]) == 4
    assert summary["findings"]
    for name in ("global", "leiame", "politicas", "changelog", "apendice"):
        assert read_snapshot_artifact(tmp_path / "out/audit", name + ".md")


def test_offline_run_never_constructs_http_transport(tmp_path, monkeypatch):
    inputs = seed_run(tmp_path)
    monkeypatch.setattr(audit.httpx, "AsyncClient", lambda **kwargs: (_ for _ in ()).throw(AssertionError("network")))
    assert run(tmp_path, inputs).exit_code == 1


def test_run_unknown_document_prose_is_explicit_gap(tmp_path):
    inputs = seed_run(tmp_path)
    pages = load_page_payloads()
    pages[35]["content"] += "New undocumented obligation.\n"
    seed_complete_wiki_snapshot(tmp_path, pages)
    result = run(tmp_path, inputs)
    assert result.exit_code == 2
    summary = json.loads(read_snapshot_artifact(tmp_path / "out/audit", "run.json"))
    assert summary["status"] == "COVERAGE_GAP"
    assert summary["coverage_complete"] is False
    assert any(gap["status"] == "UNMAPPED_DOC_CHANGE" for gap in summary["gaps"])


def test_replay_has_same_logical_hash(tmp_path):
    inputs = seed_run(tmp_path)
    first = run(tmp_path, inputs)
    second = run(tmp_path, inputs)
    assert first.logical_sha256 == second.logical_sha256


def test_missing_baseline_cannot_report_success(tmp_path):
    catalog, documents, inventory = seed_run(tmp_path)
    result = run(tmp_path, (catalog, documents, tmp_path / "missing.json"))
    assert result.exit_code == 2
    summary = json.loads(read_snapshot_artifact(tmp_path / "out/audit", "run.json"))
    assert summary["coverage_complete"] is False


def test_clean_exit_code_requires_all_explicit_claims_confirmed(tmp_path):
    catalog, _, _ = seed_run(tmp_path)
    payload = json.loads(catalog.read_text())
    for claim in payload["claims"]:
        claim["check"] = {
            "kind": "equals", "artifact": "process.json",
            "pointer": "/name", "expected": "Processo-Agil",
        }
    catalog.write_text(json.dumps(payload))
    candidates = baselines.prepare_baselines(tmp_path, catalog)
    for name, value in candidates.items():
        (tmp_path / name).write_text(json.dumps(value))
    result = run(tmp_path, (catalog, tmp_path / "document-coverage.json", tmp_path / "process-coverage.json"))
    assert result.exit_code == 0
    summary = json.loads(read_snapshot_artifact(tmp_path / "out/audit", "run.json"))
    assert summary["status"] == "CLEAN"
    assert all(row["status"] == "CONFIRMADO" for row in summary["findings"])


def test_unexpected_runtime_failure_has_internal_exit_code(tmp_path, monkeypatch):
    inputs = seed_run(tmp_path)
    monkeypatch.setattr(audit, "assess_documents", lambda *args: (_ for _ in ()).throw(RuntimeError("boom")))
    result = run(tmp_path, inputs)
    assert result.exit_code == 4


def test_new_valid_process_property_is_a_coverage_gap(tmp_path):
    inputs = seed_run(tmp_path)
    process = expected_artifacts()["process.json"]
    process["unmappedProperty"] = "new"
    seed_process_snapshot(tmp_path, custom_text={"process.json": json.dumps(process) + "\n"})
    result = run(tmp_path, inputs)
    assert result.exit_code == 2
    summary = json.loads(read_snapshot_artifact(tmp_path / "out/audit", "run.json"))
    assert any(gap["pointer"].endswith("/unmappedProperty") for gap in summary["gaps"])


def test_refresh_executes_real_collectors_through_read_only_http(tmp_path, monkeypatch):
    inputs = seed_run(tmp_path)
    process = fixture_payloads()
    pages = load_page_payloads()
    methods = []

    def respond(request):
        methods.append(request.method)
        route = request.url.path.removeprefix("/bancodonordeste")
        payload = pages[int(route.rsplit("/", 1)[-1])] if "/pages/" in route else process[route]
        return httpx.Response(200, json=payload)

    original = httpx.AsyncClient
    monkeypatch.setenv("AZDO_PAT", "synthetic-pat")
    monkeypatch.setattr(audit.httpx, "AsyncClient", lambda **kwargs: original(
        transport=httpx.MockTransport(respond), **kwargs))
    result = asyncio.run(audit.run_audit(tmp_path, *inputs, refresh=True))
    assert result.exit_code == 1
    assert len(methods) == 18
    assert set(methods) == {"GET"}


def test_corrupt_snapshot_is_validation_failure_not_internal_error(tmp_path):
    inputs = seed_run(tmp_path)
    (tmp_path / "out/process/CURRENT").write_text("invalid\n")
    assert run(tmp_path, inputs).exit_code == 3


def test_single_command_executes_the_complete_offline_audit(tmp_path):
    catalog, documents, inventory = seed_run(tmp_path)
    script = Path(__file__).parents[1] / "scripts/run_audit.py"
    result = subprocess.run([sys.executable, str(script), "--offline", "--root", str(tmp_path),
                             "--catalog", str(catalog), "--document-baseline", str(documents),
                             "--process-baseline", str(inventory)], capture_output=True, text=True)
    assert result.returncode == 1, result.stderr
    assert "DELTAS" in result.stdout
    assert read_snapshot_artifact(tmp_path / "out/audit", "global.md")
