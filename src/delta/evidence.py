"""Exact resolution and verification for collected evidence artifacts."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path


class EvidenceError(ValueError):
    """Raised when an evidence pointer or excerpt cannot be proved exactly."""


def resolve_json_pointer(document: object, pointer: str) -> object:
    """Resolve an RFC 6901 JSON Pointer, returning precisely the selected value."""
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise EvidenceError("JSON Pointer must start with '/' at segment '<root>'")

    current = document
    for raw_segment in pointer[1:].split("/"):
        segment = _decode_pointer_segment(raw_segment)
        if isinstance(current, dict):
            if segment not in current:
                raise EvidenceError(f"JSON Pointer failed at segment {segment!r}")
            current = current[segment]
            continue
        if isinstance(current, list):
            index = _array_index(segment)
            if index is None or index >= len(current):
                raise EvidenceError(f"JSON Pointer failed at segment {segment!r}")
            current = current[index]
            continue
        raise EvidenceError(f"JSON Pointer failed at segment {segment!r}")
    return current


def verify_doc_line(path: Path, line: int, excerpt: str, source_sha256: str) -> None:
    """Prove that a numbered source line and the file hash match their catalog entry."""
    contents = _read_regular_file_no_follow(path)
    verify_doc_content(contents, line, excerpt, source_sha256, label=str(path))


def verify_doc_content(
    contents: bytes,
    line: int,
    excerpt: str,
    source_sha256: str,
    *,
    label: str,
) -> None:
    """Prove an exact source line against already verified artifact bytes."""

    if not isinstance(contents, bytes):
        raise EvidenceError("document contents must be bytes")
    actual_sha256 = hashlib.sha256(contents).hexdigest()
    if actual_sha256 != source_sha256:
        raise EvidenceError(f"SHA-256 mismatch for {label}")

    try:
        lines = contents.decode("utf-8").splitlines()
    except UnicodeError:
        raise EvidenceError(f"document is not UTF-8: {label}") from None
    if line < 1 or line > len(lines):
        raise EvidenceError(f"line {line} is outside {label}")
    if lines[line - 1] != excerpt:
        raise EvidenceError(f"exact excerpt does not match line {line} in {label}")


def _read_regular_file_no_follow(path: Path) -> bytes:
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, os.O_RDONLY | no_follow)
    except OSError:
        raise EvidenceError(f"document is missing, unreadable, or a symlink: {path}") from None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise EvidenceError(f"document is not a regular file: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as source:
            return source.read()
    finally:
        os.close(descriptor)


def _decode_pointer_segment(raw_segment: str) -> str:
    decoded: list[str] = []
    index = 0
    while index < len(raw_segment):
        character = raw_segment[index]
        if character != "~":
            decoded.append(character)
            index += 1
            continue
        if index + 1 == len(raw_segment) or raw_segment[index + 1] not in {"0", "1"}:
            raise EvidenceError(f"invalid JSON Pointer escape at segment {raw_segment!r}")
        decoded.append("~" if raw_segment[index + 1] == "0" else "/")
        index += 2
    return "".join(decoded)


def _array_index(segment: str) -> int | None:
    if not segment or any(character < "0" or character > "9" for character in segment):
        return None
    if len(segment) > 1 and segment.startswith("0"):
        return None
    try:
        return int(segment)
    except ValueError:
        return None
