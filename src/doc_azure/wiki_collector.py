"""Cache-first collection of the four approved Azure DevOps wiki pages."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from doc_azure.azure_client import AzureReadClient, RequestRecord
from doc_azure.snapshot import (
    SnapshotManifest,
    SnapshotWriter,
    read_snapshot_artifact,
    read_snapshot_manifest,
    resolve_snapshot_root,
)


PROJECT_IDENTIFIER = "7ee590c5-7201-4acc-83f5-3e73023a0ab1"
WIKI_IDENTIFIER = "87014e24-4977-4d27-8e12-c05208008d95"


class WikiCollectionError(RuntimeError):
    """Raised when a page response cannot form a complete wiki snapshot."""


@dataclass(frozen=True)
class WikiPageSpec:
    """One approved wiki page identity and its stable local slug."""

    page_id: int
    slug: str


@dataclass(frozen=True)
class WikiPage:
    """Validated content needed by downstream delta evaluation."""

    page_id: int
    slug: str
    title: str
    content: str


PAGE_SPECS = (
    WikiPageSpec(35, "leiame"),
    WikiPageSpec(10, "politicas"),
    WikiPageSpec(9, "changelog"),
    WikiPageSpec(37, "apendice"),
)

WIKI_ARTIFACT_PATHS = tuple(
    sorted(
        path
        for spec in PAGE_SPECS
        for path in (f"{spec.slug}.md", f"{spec.slug}.metadata.json")
    )
)


async def collect_wiki_pages(
    root: Path,
    client: AzureReadClient | None,
    *,
    refresh: bool,
    now: Callable[[], datetime],
) -> SnapshotManifest:
    """Return cached evidence or atomically publish all four live responses."""

    project_root = Path(root)
    if not refresh:
        cached_manifest = read_cached_wiki_manifest(project_root)
        if cached_manifest is not None:
            return cached_manifest

    logical_root = project_root / "out" / "wiki"
    writer = SnapshotWriter(logical_root)
    try:
        if not refresh:
            cached_manifest = read_cached_wiki_manifest(project_root)
            if cached_manifest is not None:
                writer.abort()
                return cached_manifest
        if client is None:
            raise WikiCollectionError(
                "an Azure read client is required for collection"
            )
        first_request = len(client.request_records)
        collected = await _fetch_all_pages(client)
        for page, metadata in collected:
            writer.write_text(f"{page.slug}.md", page.content)
            writer.write_json(f"{page.slug}.metadata.json", metadata)
        requests = tuple(
            sorted(
                client.request_records[first_request:],
                key=lambda record: (record.path, record.method),
            )
        )
        return writer.commit_manifest(collected_at=now(), requests=requests)
    except BaseException:
        writer.abort()
        raise


def read_cached_wiki_manifest(root: Path) -> SnapshotManifest | None:
    """Read a complete approved wiki snapshot without changing logical-root bytes."""

    logical_root = Path(root) / "out" / "wiki"
    if not _lexists(logical_root):
        return None
    if not _has_publication(logical_root):
        return None

    resolved_root = resolve_snapshot_root(logical_root)
    manifest = read_snapshot_manifest(resolved_root)
    _validate_wiki_artifacts(resolved_root, manifest)
    return manifest


async def _fetch_all_pages(
    client: AzureReadClient,
) -> tuple[tuple[WikiPage, dict[str, object]], ...]:
    return tuple(
        await asyncio.gather(
            *(_fetch_page(client, spec) for spec in PAGE_SPECS)
        )
    )


async def _fetch_page(
    client: AzureReadClient, spec: WikiPageSpec
) -> tuple[WikiPage, dict[str, object]]:
    payload = await client.request_json(
        "GET",
        _page_path(spec.page_id),
        query={"includeContent": "true"},
    )
    page = _parse_page(spec, payload)
    metadata = dict(payload)
    del metadata["content"]
    return page, metadata


def _parse_page(spec: WikiPageSpec, payload: Mapping[str, object]) -> WikiPage:
    response_id = payload.get("id")
    page_path = payload.get("path")
    content = payload.get("content")
    if type(response_id) is not int or response_id != spec.page_id:
        raise WikiCollectionError(f"wiki page {spec.page_id} returned the wrong id")
    if not isinstance(page_path, str) or not page_path.startswith("/"):
        raise WikiCollectionError(f"wiki page {spec.page_id} path is invalid")
    title = page_path.rsplit("/", 1)[-1]
    if not title.strip():
        raise WikiCollectionError(f"wiki page {spec.page_id} path is invalid")
    if not isinstance(content, str) or not content.strip():
        raise WikiCollectionError(f"wiki page {spec.page_id} content is blank")
    return WikiPage(spec.page_id, spec.slug, title, content)


def _page_path(page_id: int) -> str:
    return (
        f"/{PROJECT_IDENTIFIER}/_apis/wiki/wikis/{WIKI_IDENTIFIER}"
        f"/pages/{page_id}"
    )


def _has_publication(logical_root: Path) -> bool:
    return _lexists(logical_root / "CURRENT") or _lexists(
        logical_root / "manifest.json"
    )


def _validate_wiki_artifacts(
    resolved_root: Path, manifest: SnapshotManifest
) -> None:
    artifact_paths = tuple(artifact.path for artifact in manifest.artifacts)
    if artifact_paths != WIKI_ARTIFACT_PATHS:
        raise WikiCollectionError("wiki snapshot artifact set is incomplete")

    for spec in PAGE_SPECS:
        try:
            content = read_snapshot_artifact(
                resolved_root,
                f"{spec.slug}.md",
            ).decode("utf-8")
            metadata = json.loads(
                read_snapshot_artifact(
                    resolved_root,
                    f"{spec.slug}.metadata.json",
                )
            )
        except (OSError, UnicodeError, ValueError):
            raise WikiCollectionError(
                f"wiki page {spec.page_id} cache is unreadable"
            ) from None
        if not isinstance(metadata, dict) or "content" in metadata:
            raise WikiCollectionError(
                f"wiki page {spec.page_id} metadata is malformed"
            )
        _parse_page(spec, {**metadata, "content": content})


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)
