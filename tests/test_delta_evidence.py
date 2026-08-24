"""Tests for exact documentary and JSON evidence primitives."""

import hashlib

import pytest

from delta.evidence import EvidenceError, resolve_json_pointer, verify_doc_line


def test_doc_evidence_rejects_nearby_but_not_exact_text(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("# Bug\nPossui 8 estados\n", encoding="utf-8")
    digest = hashlib.sha256(page.read_bytes()).hexdigest()
    with pytest.raises(EvidenceError, match="exact excerpt"):
        verify_doc_line(page, 1, "Possui 8 estados", digest)


def test_doc_evidence_rejects_a_changed_source_hash(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("Possui 8 estados\n", encoding="utf-8")
    with pytest.raises(EvidenceError, match="SHA-256"):
        verify_doc_line(page, 1, "Possui 8 estados", "0" * 64)


def test_json_pointer_returns_exact_array_item():
    document = {"value": [{"id": "System.State"}, {"id": "Custom.Bloqueado"}]}
    assert resolve_json_pointer(document, "/value/1/id") == "Custom.Bloqueado"


def test_json_pointer_decodes_escaped_property_names_and_root():
    document = {"a/b": {"~name": "value"}}
    assert resolve_json_pointer(document, "") is document
    assert resolve_json_pointer(document, "/a~1b/~0name") == "value"


def test_json_pointer_names_the_failing_segment():
    with pytest.raises(EvidenceError, match="missing"):
        resolve_json_pointer({"value": []}, "/value/missing")
