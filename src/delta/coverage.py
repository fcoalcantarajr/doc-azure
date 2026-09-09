"""Exact documentary drift detection; never infer the meaning of new prose."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class DocumentChange:
    """Changed source span, with removed content represented by baseline hashes."""

    slug: str
    kind: str
    baseline_start_line: int
    baseline_line_hashes: tuple[str, ...]
    current_start_line: int
    current_lines: tuple[str, ...]
    status: str = "UNMAPPED_DOC_CHANGE"


def _document_lines(contents: bytes) -> tuple[str, ...]:
    if not isinstance(contents, bytes):
        raise ValueError("document must be UTF-8 bytes")
    try:
        text = contents.decode("utf-8").replace("\r\n", "\n")
    except UnicodeError:
        raise ValueError("document must be UTF-8 bytes") from None
    # Do not use splitlines: terminal LF and lone CR must remain distinguishable.
    parts = text.split("\n")
    return tuple(part + "\n" for part in parts[:-1]) + (parts[-1],)


def document_fingerprint(contents: bytes) -> tuple[str, ...]:
    """Hash ordered lines after CRLF normalization, retaining other whitespace."""
    return tuple(
        hashlib.sha256(line.encode("utf-8")).hexdigest()
        for line in _document_lines(contents)
    )


def compare_document(
    slug: str, baseline: tuple[str, ...], current: bytes
) -> tuple[DocumentChange, ...]:
    """Identify unreviewed changes against an explicit versioned fingerprint.

    Deleted source text is not reconstructed from hashes. Consumers must retain
    the baseline snapshot for that evidence. Line positions are one-based, and
    insertion/deletion positions can identify the boundary immediately after EOF.
    """
    if not isinstance(baseline, tuple) or not baseline or any(
        not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
        for value in baseline
    ):
        raise ValueError("document baseline must contain ordered SHA-256 hashes")
    current_lines = _document_lines(current)
    matcher = SequenceMatcher(
        None, baseline, document_fingerprint(current), autojunk=False
    )
    return tuple(
        DocumentChange(
            slug=slug,
            kind=kind,
            baseline_start_line=old_start + 1,
            baseline_line_hashes=baseline[old_start:old_end],
            current_start_line=new_start + 1,
            current_lines=tuple(
                line.removesuffix("\n") for line in current_lines[new_start:new_end]
            ),
        )
        for kind, old_start, old_end, new_start, new_end in matcher.get_opcodes()
        if kind != "equal"
    )
