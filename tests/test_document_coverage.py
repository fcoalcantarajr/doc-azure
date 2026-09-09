"""Validate documentary coverage against real catalog and snapshot readers."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from delta import document_coverage
from delta.coverage import document_fingerprint
from delta.evaluator import evaluate_claim
from delta.build import BuildError, build_all_reports
from doc_azure.snapshot import SnapshotWriter, read_snapshot_artifact
from tests.test_delta_builder import COLLECTED_AT, PAGES, seed_catalog_and_wiki


def seed_baseline(root: Path, catalog: Path) -> Path:
    claims = json.loads(catalog.read_text())["claims"]
    documents = {}
    for slug in PAGES.values():
        contents = read_snapshot_artifact(root / "out/wiki", f"{slug}.md")
        documents[slug] = {
            "source_sha256": hashlib.sha256(contents).hexdigest(),
            "line_hashes": list(document_fingerprint(contents)),
        }
    path = root / "coverage.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
        "claim_ids": [claim["id"] for claim in claims],
        "documents": documents,
    }))
    return path


def replace_wiki(root: Path, slug: str, contents: bytes) -> None:
    originals = {
        name: read_snapshot_artifact(root / "out/wiki", f"{name}.md")
        for name in PAGES.values()
    }
    originals[slug] = contents
    writer = SnapshotWriter(root / "out/wiki")
    for name, body in originals.items():
        writer.write_text(f"{name}.md", body.decode())
    writer.commit_manifest(collected_at=COLLECTED_AT, requests=())


def test_unchanged_sources_return_all_verified_claims(tmp_path):
    catalog = seed_catalog_and_wiki(tmp_path)
    baseline = seed_baseline(tmp_path, catalog)
    result = document_coverage.assess_documents(tmp_path, catalog, baseline)
    assert not result.changes
    assert len(result.claims) == 4
    assert all(evaluate_claim(claim, tmp_path) for claim in result.claims)


def test_new_prose_outside_claim_is_gap_and_page_is_not_evaluated(tmp_path):
    catalog = seed_catalog_and_wiki(tmp_path)
    baseline = seed_baseline(tmp_path, catalog)
    original = read_snapshot_artifact(tmp_path / "out/wiki", "leiame.md")
    replace_wiki(tmp_path, "leiame", original + b"A new mandatory field.\n")
    result = document_coverage.assess_documents(tmp_path, catalog, baseline)
    assert result.changes[0].current_lines == ("A new mandatory field.",)
    assert result.changes[0].slug == "leiame"
    assert all(claim.slug != "leiame" for claim in result.claims)
    assert len(result.claims) == 3


def test_cosmetic_change_keeps_real_current_hash_and_evaluates(tmp_path):
    catalog = seed_catalog_and_wiki(tmp_path)
    baseline = seed_baseline(tmp_path, catalog)
    original = read_snapshot_artifact(tmp_path / "out/wiki", "leiame.md")
    current = original.replace(b"\n", b"\r\n")
    replace_wiki(tmp_path, "leiame", current)
    result = document_coverage.assess_documents(tmp_path, catalog, baseline)
    assert not result.changes
    claim = next(claim for claim in result.claims if claim.slug == "leiame")
    assert claim.doc.sha256 == hashlib.sha256(current).hexdigest()
    assert evaluate_claim(claim, tmp_path)
    assert json.loads(catalog.read_text())["claims"][0]["doc"]["sha256"] != claim.doc.sha256


@pytest.mark.parametrize("mutation", ["lost", "duplicate", "source", "version", "extra", "missing_page"])
def test_incompatible_baseline_fails_closed(tmp_path, mutation):
    catalog = seed_catalog_and_wiki(tmp_path)
    baseline = seed_baseline(tmp_path, catalog)
    payload = json.loads(baseline.read_text())
    if mutation == "lost":
        payload["claim_ids"].pop()
    elif mutation == "duplicate":
        payload["claim_ids"].append(payload["claim_ids"][0])
    elif mutation == "source":
        payload["documents"]["leiame"]["source_sha256"] = "0" * 64
    elif mutation == "version":
        payload["schema_version"] = True
    elif mutation == "extra":
        payload["override"] = True
    else:
        del payload["documents"]["leiame"]
    baseline.write_text(json.dumps(payload))
    with pytest.raises(document_coverage.CoverageError):
        document_coverage.assess_documents(tmp_path, catalog, baseline)


def test_catalog_changed_without_baseline_update_fails_closed(tmp_path):
    catalog = seed_catalog_and_wiki(tmp_path)
    baseline = seed_baseline(tmp_path, catalog)
    catalog.write_text(catalog.read_text() + "\n")
    with pytest.raises(document_coverage.CoverageError, match="catalog"):
        document_coverage.assess_documents(tmp_path, catalog, baseline)


def test_report_build_refuses_unknown_prose_before_publication(tmp_path):
    catalog = seed_catalog_and_wiki(tmp_path)
    baseline = seed_baseline(tmp_path, catalog)
    original = read_snapshot_artifact(tmp_path / "out/wiki", "leiame.md")
    replace_wiki(tmp_path, "leiame", original + b"New obligation.\n")
    output = tmp_path / "reports"
    with pytest.raises(BuildError, match="UNMAPPED_DOC_CHANGE.*leiame"):
        build_all_reports(tmp_path, catalog, output, coverage_baseline=baseline)
    assert not output.exists()


def test_report_build_accepts_only_cosmetic_equivalence_with_current_provenance(tmp_path):
    catalog = seed_catalog_and_wiki(tmp_path)
    baseline = seed_baseline(tmp_path, catalog)
    original = read_snapshot_artifact(tmp_path / "out/wiki", "leiame.md")
    replace_wiki(tmp_path, "leiame", original.replace(b"\n", b"\r\n"))
    paths = build_all_reports(tmp_path, catalog, tmp_path / "reports", coverage_baseline=baseline)
    assert len(paths) == 4
    assert "Processo-Agil" in paths[0].read_text()


def test_offline_command_enforces_requested_coverage_baseline(tmp_path):
    catalog = seed_catalog_and_wiki(tmp_path)
    baseline = seed_baseline(tmp_path, catalog)
    script = Path(__file__).parents[1] / "scripts/03_build_delta.py"
    command = [sys.executable, str(script), "--evidence-root", str(tmp_path),
               "--catalog", str(catalog), "--coverage-baseline", str(baseline),
               "--output-dir", str(tmp_path / "reports")]
    clean = subprocess.run(command, capture_output=True, text=True)
    assert clean.returncode == 0, clean.stderr
    previous = (tmp_path / "reports/leiame.md").read_bytes()
    original = read_snapshot_artifact(tmp_path / "out/wiki", "leiame.md")
    replace_wiki(tmp_path, "leiame", original + b"New obligation.\n")
    changed = subprocess.run(command, capture_output=True, text=True)
    assert changed.returncode == 1
    assert "UNMAPPED_DOC_CHANGE: leiame" in changed.stderr
    assert (tmp_path / "reports/leiame.md").read_bytes() == previous
