"""Tests for src/delta evidence pointer validation."""
from pathlib import Path
from src.delta import validate_evidence_pointer, resolve_evidence_pointers
import json

FIXTURES = Path(__file__).parent / "fixtures"


def test_validate_doc_evidence_resolves():
    """Valid doc_evidence pointer resolves to existing line."""
    # Write a fixture file for this test
    wiki = FIXTURES / "_test_wiki.md"
    wiki.write_text("# Test\nLine 1\nLine 2\nLine 3\n")
    try:
        assert validate_evidence_pointer(str(wiki) + "#L2", base_dir=FIXTURES) is True
    finally:
        wiki.unlink()


def test_validate_doc_evidence_dangling_line():
    """Dangling line reference fails."""
    wiki = FIXTURES / "_test_wiki.md"
    wiki.write_text("# Test\nLine 1\n")
    try:
        assert validate_evidence_pointer(str(wiki) + "#L99", base_dir=FIXTURES) is False
    finally:
        wiki.unlink()


def test_validate_azure_evidence_resolves():
    """Valid azure_evidence pointer resolves to JSON path."""
    proc = FIXTURES / "_test_process.json"
    proc.write_text(json.dumps({"states": [{"name": "New"}]}))
    try:
        ptr = str(proc) + "#/states/0/name"
        assert validate_evidence_pointer(ptr, base_dir=FIXTURES) is True
    finally:
        proc.unlink()


def test_validate_azure_evidence_dangling_path():
    """Dangling JSON path fails."""
    proc = FIXTURES / "_test_process.json"
    proc.write_text(json.dumps({"states": [{"name": "New"}]}))
    try:
        ptr = str(proc) + "#/nonexistent/path"
        assert validate_evidence_pointer(ptr, base_dir=FIXTURES) is False
    finally:
        proc.unlink()


def test_resolve_batch():
    """resolve_evidence_pointers validates all rows and returns per-row results."""
    rows = [
        {"id": "R001", "doc_evidence": str(FIXTURES / "wiki_leiame.md") + "#L1"},
        {"id": "R002", "doc_evidence": str(FIXTURES / "nonexistent.md") + "#L1"},
    ]
    results = resolve_evidence_pointers(rows, base_dir=FIXTURES)
    assert results["R001"] is True
    assert results["R002"] is False
