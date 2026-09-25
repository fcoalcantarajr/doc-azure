"""Baseline candidates require complete evidence and matching explicit claims."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from doc_azure import baselines
from tests.test_audit_runtime import seed_run
from tests.test_wiki_collector import load_page_payloads, seed_complete_wiki_snapshot
from doc_azure.snapshot import (
    read_snapshot_artifact,
    read_snapshot_manifest_with_sha256,
    resolve_snapshot_root,
)


def test_candidate_matches_verified_inputs_without_changing_catalog(tmp_path):
    catalog, documents, inventory = seed_run(tmp_path)
    before = catalog.read_bytes()
    candidate = baselines.prepare_baselines(tmp_path, catalog)
    assert candidate["document-coverage.json"] == json.loads(documents.read_bytes())
    assert candidate["process-coverage.json"] == json.loads(inventory.read_bytes())
    process_baseline = candidate["process-coverage.json"]
    process_root = resolve_snapshot_root(tmp_path / "out/process")
    manifest, manifest_sha256 = read_snapshot_manifest_with_sha256(
        tmp_path / "out/process"
    )
    assert process_baseline["schema_version"] == 2
    assert process_baseline["source"] == {
        "generation_id": process_root.name,
        "manifest_sha256": manifest_sha256,
        "collected_at": manifest.collected_at,
        "request_count": len(manifest.requests),
        "artifact_count": len(manifest.artifacts),
        "collection_mode": "full_api",
    }
    assert process_baseline["entries"] == json.loads(inventory.read_bytes())["entries"]
    assert catalog.read_bytes() == before
    assert candidate == baselines.prepare_baselines(tmp_path, catalog)


def test_candidate_cannot_accept_new_prose_without_catalog_update(tmp_path):
    catalog, _, _ = seed_run(tmp_path)
    pages = load_page_payloads()
    pages[35]["content"] += "New obligation.\n"
    seed_complete_wiki_snapshot(tmp_path, pages)
    with pytest.raises(ValueError, match="SHA-256"):
        baselines.prepare_baselines(tmp_path, catalog)


def test_candidate_rejects_process_snapshot_with_missing_get_receipt(tmp_path):
    catalog, _, _ = seed_run(tmp_path)
    process_root = resolve_snapshot_root(tmp_path / "out/process")
    manifest_path = process_root / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["requests"] = manifest["requests"][1:]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="process API request route coverage"):
        baselines.prepare_baselines(tmp_path, catalog)


@pytest.mark.parametrize("receipt_change", ["post", "extra"])
def test_candidate_rejects_invalid_process_get_receipts(tmp_path, receipt_change):
    catalog, _, _ = seed_run(tmp_path)
    process_root = resolve_snapshot_root(tmp_path / "out/process")
    manifest_path = process_root / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if receipt_change == "post":
        manifest["requests"][0]["method"] = "POST"
    else:
        manifest["requests"].append(
            {"method": "GET", "path": "/_apis/work/processes/unexpected/extra"}
        )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="process API request route coverage"):
        baselines.prepare_baselines(tmp_path, catalog)


def test_candidate_accepts_full_api_retry_receipt(tmp_path):
    catalog, _, _ = seed_run(tmp_path)
    process_root = resolve_snapshot_root(tmp_path / "out/process")
    manifest_path = process_root / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["requests"].append(manifest["requests"][0])
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    candidate = baselines.prepare_baselines(tmp_path, catalog)["process-coverage.json"]

    assert candidate["source"]["collection_mode"] == "full_api"
    assert candidate["source"]["request_count"] == 15


def test_candidate_rejects_complete_but_unattested_process_receipts(
    tmp_path,
):
    catalog, _, _ = seed_run(tmp_path)
    process_root = resolve_snapshot_root(tmp_path / "out/process")
    manifest_path = process_root / "manifest.json"
    payload = json.loads(manifest_path.read_bytes())
    payload["schema_version"] = 1
    payload.pop("collection_mode")
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    source_manifest, _ = read_snapshot_manifest_with_sha256(process_root)
    assert len(source_manifest.requests) == 14
    assert getattr(source_manifest, "collection_mode", None) is None

    with pytest.raises(ValueError, match="full_api"):
        baselines.prepare_baselines(tmp_path, catalog)


def test_preparation_command_writes_only_ignored_candidates(tmp_path):
    catalog, documents, _ = seed_run(tmp_path)
    script = Path(__file__).parents[1] / "scripts/prepare_baselines.py"
    result = subprocess.run([sys.executable, str(script), "--root", str(tmp_path),
                             "--catalog", str(catalog)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    candidate = read_snapshot_artifact(tmp_path / "out/baseline-candidate", "document-coverage.json")
    assert json.loads(candidate) == json.loads(documents.read_bytes())
    assert not (tmp_path / "config/document-coverage.json").exists()
