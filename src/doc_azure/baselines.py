"""Prepare review candidates, never silently accept coverage during an audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from delta.catalog import PAGE_SLUGS, load_catalog
from delta.coverage import document_fingerprint
from delta.document_coverage import _unique_object
from delta.evidence import verify_doc_content
from delta.process_coverage import fingerprint_json
from doc_azure.process_collector import read_cached_process_manifest
from doc_azure.snapshot import read_snapshot_artifact, resolve_snapshot_root
from doc_azure.wiki_collector import read_cached_wiki_manifest


def prepare_baselines(root: Path, catalog: Path) -> dict[str, dict]:
    """Produce deterministic candidates only for an exact source-backed catalog.

    The caller must review and explicitly version these files. This function has
    no network access and writes nothing, especially not the accepted config.
    """
    catalog_bytes = catalog.read_bytes()
    claims = load_catalog(catalog)
    if {claim.slug for claim in claims} != set(PAGE_SLUGS.values()):
        raise ValueError("catalog must cover all four pages")
    wiki_manifest = read_cached_wiki_manifest(root)
    process_manifest = read_cached_process_manifest(root)
    if wiki_manifest is None or process_manifest is None:
        raise ValueError("complete wiki and process snapshots are required")
    wiki_root = resolve_snapshot_root(root / "out/wiki")
    process_root = resolve_snapshot_root(root / "out/process")
    documents = {}
    for slug in PAGE_SLUGS.values():
        contents = read_snapshot_artifact(wiki_root, slug + ".md")
        for claim in claims:
            if claim.slug == slug:
                for fragment in claim.documents:
                    verify_doc_content(contents, fragment.line, fragment.excerpt,
                                       fragment.sha256, label=fragment.path)
        documents[slug] = {"source_sha256": hashlib.sha256(contents).hexdigest(),
                           "line_hashes": list(document_fingerprint(contents))}
    artifacts = {entry.path: json.loads(read_snapshot_artifact(process_root, entry.path),
                                     object_pairs_hook=_unique_object)
                 for entry in process_manifest.artifacts}
    if (resolve_snapshot_root(root / "out/wiki") != wiki_root
            or resolve_snapshot_root(root / "out/process") != process_root
            or catalog.read_bytes() != catalog_bytes):
        raise ValueError("baseline sources changed during preparation")
    common = {"schema_version": 1, "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest()}
    return {
        "document-coverage.json": {**common, "claim_ids": [claim.id for claim in claims],
                                    "documents": documents},
        "process-coverage.json": {**common, "entries": fingerprint_json(artifacts)},
    }
