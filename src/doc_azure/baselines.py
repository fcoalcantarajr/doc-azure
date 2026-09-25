"""Prepare review candidates, never silently accept coverage during an audit."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Mapping

from delta.catalog import PAGE_SLUGS, load_catalog
from delta.coverage import document_fingerprint
from delta.document_coverage import _unique_object
from delta.evidence import verify_doc_content
from delta.process_coverage import fingerprint_json
from doc_azure.process_collector import (
    ProcessCollectionError,
    read_cached_process_manifest,
    validate_process_request_routes,
)
from doc_azure.snapshot import (
    SnapshotError,
    read_snapshot_artifact,
    read_snapshot_manifest_with_sha256,
    resolve_snapshot_root,
)
from doc_azure.wiki_collector import read_cached_wiki_manifest


_GENERATION_ID = re.compile(r"^[0-9a-f]{32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PROCESS_SOURCE_FIELDS = {
    "generation_id",
    "manifest_sha256",
    "collected_at",
    "request_count",
    "artifact_count",
    "collection_mode",
}


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
    process_logical_root = root / "out/process"
    process_root = resolve_snapshot_root(process_logical_root)
    source_manifest, process_manifest_sha256 = read_snapshot_manifest_with_sha256(
        process_logical_root
    )
    if (
        process_root.parent.name != "snapshots"
        or not _GENERATION_ID.fullmatch(process_root.name)
    ):
        raise ValueError("process baseline source must be an immutable CURRENT generation")
    try:
        process_manifest = validate_process_request_routes(process_root)
    except ProcessCollectionError as error:
        raise ValueError(str(error)) from None
    if process_manifest != source_manifest:
        raise ValueError("process baseline source changed during preparation")
    if process_manifest.collection_mode != "full_api":
        raise ValueError("process baseline source must have full_api collection mode")
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
            or read_snapshot_manifest_with_sha256(process_logical_root)[1]
            != process_manifest_sha256
            or catalog.read_bytes() != catalog_bytes):
        raise ValueError("baseline sources changed during preparation")
    common = {"schema_version": 1, "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest()}
    process_source = {
        "generation_id": process_root.name,
        "manifest_sha256": process_manifest_sha256,
        "collected_at": process_manifest.collected_at,
        "request_count": len(process_manifest.requests),
        "artifact_count": len(process_manifest.artifacts),
        "collection_mode": process_manifest.collection_mode,
    }
    return {
        "document-coverage.json": {**common, "claim_ids": [claim.id for claim in claims],
                                    "documents": documents},
        "process-coverage.json": {
            **common,
            "schema_version": 2,
            "source": process_source,
            "entries": fingerprint_json(artifacts),
        },
    }


def validate_process_coverage_source(root: Path, payload: Mapping[str, object]) -> None:
    """Verify the immutable process generation named by a coverage baseline."""

    source = payload.get("source")
    if not isinstance(source, dict) or set(source) != _PROCESS_SOURCE_FIELDS:
        raise ValueError("process coverage baseline source schema is invalid")
    generation_id = source.get("generation_id")
    manifest_sha256 = source.get("manifest_sha256")
    collected_at = source.get("collected_at")
    request_count = source.get("request_count")
    artifact_count = source.get("artifact_count")
    collection_mode = source.get("collection_mode")
    if (
        not isinstance(generation_id, str)
        or not _GENERATION_ID.fullmatch(generation_id)
        or not isinstance(manifest_sha256, str)
        or not _SHA256.fullmatch(manifest_sha256)
        or not isinstance(collected_at, str)
        or not collected_at.strip()
        or type(request_count) is not int
        or request_count < 0
        or type(artifact_count) is not int
        or artifact_count < 1
        or collection_mode != "full_api"
    ):
        raise ValueError("process coverage baseline source metadata is invalid")

    process_root = Path(root) / "out" / "process"
    source_root = process_root / "snapshots" / generation_id
    source_is_present = source_root.exists() or source_root.is_symlink()
    try:
        snapshot_root = (
            source_root if source_is_present else resolve_snapshot_root(process_root)
        )
        manifest, actual_manifest_sha256 = read_snapshot_manifest_with_sha256(
            snapshot_root
        )
        verified_manifest = validate_process_request_routes(snapshot_root)
        if verified_manifest != manifest:
            raise ValueError("process coverage baseline source changed")
        if source_is_present and (
            actual_manifest_sha256 != manifest_sha256
            or manifest.collected_at != collected_at
            or len(manifest.requests) != request_count
            or len(manifest.artifacts) != artifact_count
            or manifest.collection_mode != collection_mode
        ):
            raise ValueError("process coverage baseline source metadata differs")
        if not source_is_present and (
            manifest.collection_mode != "full_api"
            or len(manifest.artifacts) != artifact_count
            or request_count
            < len({(record.method, record.path) for record in manifest.requests})
        ):
            raise ValueError("process coverage baseline source metadata differs")
        artifacts = {
            entry.path: json.loads(
                read_snapshot_artifact(snapshot_root, entry.path),
                object_pairs_hook=_unique_object,
            )
            for entry in manifest.artifacts
        }
    except (OSError, SnapshotError, ProcessCollectionError, UnicodeError, ValueError):
        raise ValueError("process coverage baseline source is invalid") from None

    entries = payload.get("entries")
    if not isinstance(entries, dict) or entries != fingerprint_json(artifacts):
        raise ValueError("process coverage entries differ from their source generation")
