"""Deterministic, type-preserving JSON inventory fingerprints and drift spans."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

@dataclass(frozen=True)
class InventoryChange:
    pointer: str
    kind: str
    previous_sha256: str | None
    current_sha256: str | None


def fingerprint_json(value: object) -> dict[str, str]:
    """Fingerprint every JSON node; object order alone is ignored.

    Container markers retain empty containers and distinguish arrays from maps.
    Array order remains significant because layout/state order can be material.
    No property is silently dropped as presumed volatile.
    """
    entries: dict[str, str] = {}

    def visit(node: object, pointer: str) -> None:
        if type(node) not in {dict, list, str, int, float, bool, type(None)}:
            raise ValueError("inventory contains a non-JSON value")
        marker = ["object"] if isinstance(node, dict) else ["array"] if isinstance(node, list) else ["value", node]
        encoded = json.dumps(marker, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        entries[pointer] = hashlib.sha256(encoded.encode()).hexdigest()
        if isinstance(node, dict):
            if any(not isinstance(key, str) for key in node):
                raise ValueError("inventory object keys must be strings")
            for key in sorted(node):
                visit(node[key], pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, pointer + "/" + str(index))

    visit(value, "")
    return entries


def _validate_inventory(entries: dict[str, str]) -> None:
    if not isinstance(entries, dict) or "" not in entries:
        raise ValueError("inventory must include its root fingerprint")
    for pointer, digest in entries.items():
        if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
            raise ValueError("inventory has an invalid JSON pointer")
        # Validate RFC 6901 escapes independently of the original source value.
        if re.search(r"~(?![01])", pointer):
            raise ValueError("inventory has an invalid JSON pointer escape")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("inventory has an invalid SHA-256 fingerprint")


def compare_inventory(previous: dict[str, str], current: dict[str, str]) -> tuple[InventoryChange, ...]:
    """Return every changed node, including additions and removals, in stable order."""
    _validate_inventory(previous)
    _validate_inventory(current)
    return tuple(
        InventoryChange(pointer,
                        "added" if pointer not in previous else "removed" if pointer not in current else "changed",
                        previous.get(pointer), current.get(pointer))
        for pointer in sorted(previous.keys() | current.keys())
        if previous.get(pointer) != current.get(pointer)
    )
