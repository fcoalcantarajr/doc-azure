"""Tests for src/delta classification logic."""
from src.delta import classify_row, validate_class


def test_classify_valid_classes():
    """Each of the four valid classes is accepted."""
    for cls in ("DOC_ONLY", "AZURE_ONLY", "DIVERGENT", "MATCH"):
        assert validate_class(cls) is True


def test_classify_invalid_class():
    """Unknown class strings are rejected."""
    assert validate_class("INVALID") is False
    assert validate_class("") is False
    assert validate_class("doc_only") is False  # case-sensitive


def test_classify_row_doc_only():
    """DOC_ONLY rows have n/a azure_evidence."""
    result = classify_row({
        "class": "DOC_ONLY",
        "doc_evidence": "out/wiki/x.md#L1",
        "azure_evidence": "n/a"
    })
    assert result["class"] == "DOC_ONLY"


def test_classify_row_azure_only():
    """AZURE_ONLY rows have n/a doc_evidence."""
    result = classify_row({
        "class": "AZURE_ONLY",
        "doc_evidence": "n/a",
        "azure_evidence": "out/process/x.json#/foo"
    })
    assert result["class"] == "AZURE_ONLY"


def test_classify_rejects_bad_evidence():
    """DOC_ONLY with non-n/a azure_evidence is rejected."""
    try:
        classify_row({
            "class": "DOC_ONLY",
            "doc_evidence": "out/wiki/x.md#L1",
            "azure_evidence": "out/process/x.json#/foo"
        })
        assert False, "Should have raised"
    except ValueError:
        pass


def test_classify_rejects_azure_only_with_doc():
    """AZURE_ONLY with non-n/a doc_evidence is rejected."""
    try:
        classify_row({
            "class": "AZURE_ONLY",
            "doc_evidence": "out/wiki/x.md#L1",
            "azure_evidence": "out/process/x.json#/foo"
        })
        assert False, "Should have raised"
    except ValueError:
        pass
