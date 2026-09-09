"""Baseline candidates require complete evidence and matching explicit claims."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from doc_azure import baselines
from tests.test_audit_runtime import seed_run
from tests.test_wiki_collector import load_page_payloads, seed_complete_wiki_snapshot
from doc_azure.snapshot import read_snapshot_artifact


def test_candidate_matches_verified_inputs_without_changing_catalog(tmp_path):
    catalog, documents, inventory = seed_run(tmp_path)
    before = catalog.read_bytes()
    candidate = baselines.prepare_baselines(tmp_path, catalog)
    assert candidate["document-coverage.json"] == json.loads(documents.read_bytes())
    assert candidate["process-coverage.json"] == json.loads(inventory.read_bytes())
    assert catalog.read_bytes() == before
    assert candidate == baselines.prepare_baselines(tmp_path, catalog)


def test_candidate_cannot_accept_new_prose_without_catalog_update(tmp_path):
    catalog, _, _ = seed_run(tmp_path)
    pages = load_page_payloads()
    pages[35]["content"] += "New obligation.\n"
    seed_complete_wiki_snapshot(tmp_path, pages)
    with pytest.raises(ValueError, match="SHA-256"):
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
