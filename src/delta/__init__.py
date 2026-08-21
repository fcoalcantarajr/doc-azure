"""Pure functions for delta classification, rendering, and evidence validation.

No network access. No file I/O outside the explicit paths passed in.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

VALID_CLASSES = frozenset({"DOC_ONLY", "AZURE_ONLY", "DIVERGENT", "MATCH"})


def validate_class(cls: str) -> bool:
    """Return True if cls is one of the four valid class literals."""
    return cls in VALID_CLASSES


def classify_row(row: dict[str, Any]) -> dict[str, Any]:
    """Validate a row's class and evidence asymmetry. Returns row on success.
    
    DOC_ONLY must have azure_evidence == 'n/a'.
    AZURE_ONLY must have doc_evidence == 'n/a'.
    Raises ValueError on violation.
    """
    cls = row.get("class", "")
    if not validate_class(cls):
        raise ValueError(f"Invalid class: {cls!r}")
    
    doc_ev = row.get("doc_evidence", "")
    azure_ev = row.get("azure_evidence", "")
    
    if cls == "DOC_ONLY" and azure_ev != "n/a":
        raise ValueError(f"DOC_ONLY row must have azure_evidence='n/a', got: {azure_ev!r}")
    if cls == "AZURE_ONLY" and doc_ev != "n/a":
        raise ValueError(f"AZURE_ONLY row must have doc_evidence='n/a', got: {doc_ev!r}")
    
    return row


def render_delta_table(rows: list[dict[str, Any]]) -> str:
    """Render a markdown table with the delta columns."""
    if not rows:
        rows = []
    for row in rows:
        if not row.get("claim_pt", "").strip():
            raise ValueError(f"Row {row.get('id', '?')!r} has empty claim_pt")
        classify_row(row)  # validates class and evidence
    
    header = "| id | claim (pt-BR) | class | doc_evidence | azure_evidence | consequence |"
    sep = "| --- | --- | --- | --- | --- | --- |"
    lines = [header, sep]
    for row in rows:
        consequence = row.get("consequence", "")
        if row.get("class") != "MATCH" and not consequence.strip():
            raise ValueError(f"Non-MATCH row {row.get('id', '?')!r} missing consequence")
        lines.append(
            f"| {row['id']} | {row['claim_pt']} | {row['class']} | "
            f"{row.get('doc_evidence', '')} | {row.get('azure_evidence', '')} | "
            f"{consequence} |"
        )
    return "\n".join(lines)


def render_summary_block(rows: list[dict[str, Any]]) -> str:
    """Render the SUMMARY block with per-class counts."""
    counts = {"DOC_ONLY": 0, "AZURE_ONLY": 0, "DIVERGENT": 0, "MATCH": 0}
    for row in rows:
        cls = row.get("class", "")
        if cls in counts:
            counts[cls] += 1
    return (
        "SUMMARY\n"
        f"DOC_ONLY={counts['DOC_ONLY']}\n"
        f"AZURE_ONLY={counts['AZURE_ONLY']}\n"
        f"DIVERGENT={counts['DIVERGENT']}\n"
        f"MATCH={counts['MATCH']}\n"
    )


def validate_evidence_pointer(ptr: str, base_dir: Path) -> bool:
    """Validate that a pointer like 'path/to/file.md#L5' or 'file.json#/foo/bar' resolves.
    
    For doc pointers: file exists AND line N exists.
    For azure pointers: file exists AND json-path resolves.
    Returns False on any failure.
    """
    if "#L" in ptr:
        # Doc pointer: file#L<line>
        file_part, _, line_part = ptr.partition("#L")
        try:
            line_num = int(line_part)
        except ValueError:
            return False
        p = Path(file_part)
        if not p.is_absolute():
            p = base_dir / file_part
        if not p.exists():
            return False
        try:
            lines = p.read_text().splitlines()
            return 1 <= line_num <= len(lines)
        except Exception:
            return False
    elif "#/" in ptr:
        # Azure pointer: file.json#/json/path
        file_part, _, json_path = ptr.partition("#/")
        p = Path(file_part)
        if not p.is_absolute():
            p = base_dir / file_part
        if not p.exists():
            return False
        try:
            data = json.loads(p.read_text())
            for key in json_path.split("/"):
                if key == "":
                    continue
                if isinstance(data, list):
                    try:
                        idx = int(key)
                        data = data[idx]
                    except (ValueError, IndexError):
                        return False
                elif isinstance(data, dict):
                    if key not in data:
                        return False
                    data = data[key]
                else:
                    return False
            return True
        except Exception:
            return False
    return False


def resolve_evidence_pointers(rows: list[dict[str, Any]], base_dir: Path) -> dict[str, bool]:
    """Validate all evidence pointers in rows. Returns {row_id: bool}."""
    results = {}
    for row in rows:
        row_id = row.get("id", "?")
        doc_ptr = row.get("doc_evidence", "")
        azure_ptr = row.get("azure_evidence", "")
        doc_ok = True
        azure_ok = True
        if doc_ptr and doc_ptr != "n/a":
            doc_ok = validate_evidence_pointer(doc_ptr, base_dir)
        if azure_ptr and azure_ptr != "n/a":
            azure_ok = validate_evidence_pointer(azure_ptr, base_dir)
        results[row_id] = doc_ok and azure_ok
    return results