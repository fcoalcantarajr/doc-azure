"""Bind documentary drift checks to a reviewed, versioned assertion catalog."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

from delta.catalog import ClaimSpec, PAGE_SLUGS, load_catalog
from delta.coverage import DocumentChange, compare_document
from delta.evidence import verify_doc_content
from doc_azure.snapshot import read_snapshot_artifact, resolve_snapshot_root


class CoverageError(ValueError):
    """The versioned coverage contract is absent, malformed or incompatible."""


@dataclass(frozen=True)
class DocumentCoverage:
    claims: tuple[ClaimSpec, ...]
    changes: tuple[DocumentChange, ...]


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CoverageError("duplicate key in documentary baseline")
        result[key] = value
    return result


def _load_baseline(path: Path, catalog: Path, claims: tuple[ClaimSpec, ...]) -> dict:
    try:
        payload = json.loads(path.read_bytes(), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, ValueError):
        raise CoverageError("documentary baseline is unreadable or invalid") from None
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version", "catalog_sha256", "claim_ids", "documents"
    }:
        raise CoverageError("documentary baseline has an invalid schema")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise CoverageError("unsupported documentary baseline version")
    if payload["catalog_sha256"] != hashlib.sha256(catalog.read_bytes()).hexdigest():
        raise CoverageError("catalog hash differs from reviewed baseline")
    if payload["claim_ids"] != [claim.id for claim in claims]:
        raise CoverageError("catalog claim inventory differs from reviewed baseline")
    documents = payload["documents"]
    if not isinstance(documents, dict) or set(documents) != set(PAGE_SLUGS.values()):
        raise CoverageError("baseline must cover all four documentary pages")
    for slug, document in documents.items():
        if not isinstance(document, dict) or set(document) != {"source_sha256", "line_hashes"}:
            raise CoverageError("invalid documentary page baseline")
        hashes = document["line_hashes"]
        if not isinstance(hashes, list) or not hashes or any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            for value in hashes
        ):
            raise CoverageError("invalid documentary line hashes")
        page_claims = [claim for claim in claims if claim.slug == slug]
        if not page_claims or any(
            fragment.sha256 != document["source_sha256"]
            for claim in page_claims for fragment in claim.documents
        ):
            raise CoverageError("baseline source hash differs from catalog")
    return documents


def assess_documents(root: Path, catalog: Path, baseline: Path) -> DocumentCoverage:
    """Return only source-verified claims; exclude every materially changed page.

    Cosmetic equivalence adjusts only the in-memory source byte hash. The exact
    catalog excerpt is still verified against current bytes before evaluation.
    This never edits the versioned catalog or accepts an updated baseline.
    """
    claims = load_catalog(catalog)
    documents = _load_baseline(baseline, catalog, claims)
    generation = resolve_snapshot_root(root / "out/wiki")
    changes: list[DocumentChange] = []
    safe_hashes: dict[str, str] = {}
    for slug in PAGE_SLUGS.values():
        contents = read_snapshot_artifact(generation, f"{slug}.md")
        page_changes = compare_document(slug, tuple(documents[slug]["line_hashes"]), contents)
        changes.extend(page_changes)
        if not page_changes:
            safe_hashes[slug] = hashlib.sha256(contents).hexdigest()
            for claim in claims:
                if claim.slug == slug:
                    for fragment in claim.documents:
                        verify_doc_content(contents, fragment.line, fragment.excerpt,
                                           safe_hashes[slug], label=fragment.path)
    verified = tuple(
        replace(claim,
                doc=replace(claim.doc, sha256=safe_hashes[claim.slug]),
                doc_fragments=tuple(replace(fragment, sha256=safe_hashes[claim.slug])
                                    for fragment in claim.doc_fragments))
        for claim in claims if claim.slug in safe_hashes
    )
    if resolve_snapshot_root(root / "out/wiki") != generation:
        raise CoverageError("wiki generation changed during coverage assessment")
    return DocumentCoverage(verified, tuple(changes))
