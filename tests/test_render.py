"""Tests for src/delta render logic (markdown table generation)."""
from src.delta import render_delta_table, render_summary_block


def test_render_table_with_rows():
    """Render a markdown table from a list of rows."""
    rows = [
        {"id": "R001", "claim_pt": "Test", "class": "MATCH",
         "doc_evidence": "out/wiki/x.md#L1", "azure_evidence": "out/process/y.json#/z"}
    ]
    md = render_delta_table(rows)
    assert "| id | claim (pt-BR) | class | doc_evidence | azure_evidence |" in md
    assert "R001" in md
    assert "MATCH" in md


def test_render_table_empty():
    """Empty row list produces a valid empty table."""
    md = render_delta_table([])
    assert "| id | claim (pt-BR) | class | doc_evidence | azure_evidence |" in md


def test_render_summary_counts():
    """Summary block contains correct counts per class."""
    rows = [
        {"class": "MATCH"},
        {"class": "MATCH"},
        {"class": "DIVERGENT"},
        {"class": "DOC_ONLY"},
        {"class": "AZURE_ONLY"},
        {"class": "AZURE_ONLY"},
    ]
    summary = render_summary_block(rows)
    assert "DOC_ONLY=1" in summary
    assert "AZURE_ONLY=2" in summary
    assert "DIVERGENT=1" in summary
    assert "MATCH=2" in summary


def test_render_summary_empty():
    """Empty rows produce all-zero counts."""
    summary = render_summary_block([])
    assert "DOC_ONLY=0" in summary
    assert "AZURE_ONLY=0" in summary
    assert "DIVERGENT=0" in summary
    assert "MATCH=0" in summary


def test_render_rejects_empty_claim():
    """Rows with empty claim_pt are rejected."""
    try:
        render_delta_table([{"id": "R001", "claim_pt": "", "class": "MATCH",
                            "doc_evidence": "x", "azure_evidence": "y"}])
        assert False, "Should have raised"
    except ValueError:
        pass
