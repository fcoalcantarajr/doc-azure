"""Fail-closed verification for reviewed Notion report copies in Staging."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from delta.notion_external_evidence import (
    ExternalEvidenceError,
    NotionFetchEvidence,
    parse_notion_duplicate_result,
    parse_notion_fetch_result,
)
from delta.notion_semantics import parse_notion_semantics


_DRAFT_FIELDS = {
    "slug",
    "source_page_id",
    "source_title",
    "page_id",
    "title",
    "parent_page_id",
    "url",
    "marker",
    "prepared_path",
    "body_sha256",
    "semantic_sha256",
    "duplicated_at",
    "duplicate_result_path",
    "duplicate_result_sha256",
    "source_fetch_path",
    "source_fetch_sha256",
    "source_final_fetch_path",
    "source_final_fetch_sha256",
    "copy_fetch_path",
    "copy_fetch_sha256",
}
_PAGE_ID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
_STAGING_TITLE = "Staging — duplicatas pra conferir"


def verify_draft_publication_gate(root: Path, error_type: type[ValueError]) -> None:
    """Verify reviewed, distinct copies plus their raw creation and read-back facts."""

    from delta.notion import (
        NOTION_AZURE_PAGE_ID,
        NOTION_DRAFT_PARENT_PAGE_ID,
        NOTION_PARENT_PAGE_ID,
        PublicationEntry,
        expected_publication_manifest,
    )
    from delta.notion_gate import (
        _load_json,
        _parse_time,
        _read_root_file,
        _verify_bound_file,
        _verify_duplicate_searches,
        _verify_publication_receipt,
        verify_review_gate,
    )

    repository_root = Path(root)
    verify_review_gate(repository_root, error_type)
    expected = expected_publication_manifest(repository_root)
    draft_root = repository_root / "out" / "notion" / "draft"
    targets = _load_json(draft_root / "targets.json", error_type, "draft targets")
    if set(targets) != {
        "schema_version",
        "draft_parent_page_id",
        "draft_parent_fetch_path",
        "draft_parent_fetch_sha256",
        "entries",
    } or targets.get("schema_version") != 1:
        raise error_type("draft target manifest schema is invalid")
    if targets.get("draft_parent_page_id") != NOTION_DRAFT_PARENT_PAGE_ID:
        raise error_type("draft parent is invalid")

    _verify_bound_file(
        repository_root,
        targets.get("draft_parent_fetch_path"),
        targets.get("draft_parent_fetch_sha256"),
        error_type,
        "draft parent raw fetch",
    )
    draft_parent = _read_fetch(
        repository_root,
        str(targets["draft_parent_fetch_path"]),
        error_type,
        "draft parent",
    )
    if (
        draft_parent.page_id != NOTION_DRAFT_PARENT_PAGE_ID
        or draft_parent.parent_page_id != NOTION_AZURE_PAGE_ID
        or draft_parent.title.removeprefix("📲 ") != _STAGING_TITLE
    ):
        raise error_type("draft parent hierarchy is invalid")

    raw_entries = targets.get("entries")
    if not isinstance(raw_entries, list) or len(raw_entries) != len(expected.entries):
        raise error_type("draft target coverage is invalid")
    expected_by_slug = {entry.slug: entry for entry in expected.entries}
    original_ids = {entry.page_id for entry in expected.entries}
    target_ids: set[str] = set()
    target_entries: list[PublicationEntry] = []
    updated_times: list[datetime] = []
    source_final_fetch_times: list[datetime] = []
    draft_fetched = repository_root / "out" / "notion" / "draft" / "fetched"

    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict) or set(raw_entry) != _DRAFT_FIELDS:
            raise error_type("draft target entry schema is invalid")
        slug = raw_entry.get("slug")
        canonical = expected_by_slug.get(slug) if isinstance(slug, str) else None
        if canonical is None or len(target_entries) >= len(expected.entries):
            raise error_type("draft target identity is invalid")
        if slug in {entry.slug for entry in target_entries}:
            raise error_type("draft target coverage contains a duplicate slug")

        page_id = _normalized_page_id(raw_entry.get("page_id"), error_type)
        if page_id in original_ids or page_id == NOTION_DRAFT_PARENT_PAGE_ID:
            raise error_type(f"{slug}: copy page id must differ from source pages")
        if page_id in target_ids:
            raise error_type("draft copy page IDs must be distinct")
        target_ids.add(page_id)

        title = f"Rascunho — {canonical.title}"
        url = f"https://app.notion.com/p/{page_id.replace('-', '')}"
        expected_fields = {
            "source_page_id": canonical.page_id,
            "source_title": canonical.title,
            "title": title,
            "parent_page_id": NOTION_DRAFT_PARENT_PAGE_ID,
            "url": url,
            "marker": canonical.marker,
            "prepared_path": canonical.prepared_path,
            "body_sha256": canonical.body_sha256,
            "semantic_sha256": canonical.semantic_sha256,
        }
        if any(
            raw_entry.get(field) != value for field, value in expected_fields.items()
        ):
            raise error_type(f"{slug}: draft target metadata does not match reports")

        duplicated_at = _parse_time(
            raw_entry.get("duplicated_at"), error_type, "page duplication"
        )
        for path_field, hash_field, label in (
            ("duplicate_result_path", "duplicate_result_sha256", "duplicate result"),
            ("source_fetch_path", "source_fetch_sha256", "source raw fetch"),
            (
                "source_final_fetch_path",
                "source_final_fetch_sha256",
                "final source raw fetch",
            ),
            ("copy_fetch_path", "copy_fetch_sha256", "initial copy raw fetch"),
        ):
            _verify_bound_file(
                repository_root,
                raw_entry.get(path_field),
                raw_entry.get(hash_field),
                error_type,
                label,
            )

        duplicate_raw = _read_root_file(
            repository_root,
            str(raw_entry["duplicate_result_path"]),
            error_type,
            f"{slug} duplicate result",
        )
        try:
            duplicate = parse_notion_duplicate_result(duplicate_raw)
        except ExternalEvidenceError as error:
            raise error_type(f"{slug}: duplicate result is invalid: {error}") from None
        if duplicate.page_id != page_id or duplicate.url != url:
            raise error_type(f"{slug}: duplicate result identifies another page")

        source = _read_fetch(
            repository_root,
            str(raw_entry["source_fetch_path"]),
            error_type,
            f"{slug} source",
        )
        source_final = _read_fetch(
            repository_root,
            str(raw_entry["source_final_fetch_path"]),
            error_type,
            f"{slug} final source",
        )
        copy = _read_fetch(
            repository_root,
            str(raw_entry["copy_fetch_path"]),
            error_type,
            f"{slug} initial copy",
        )
        if (
            source.page_id != canonical.page_id
            or source.title != canonical.title
            or source.url != canonical.url
            or source.parent_page_id != NOTION_PARENT_PAGE_ID
            or copy.page_id != page_id
            or copy.url != url
            or copy.parent_page_id != source.parent_page_id
        ):
            raise error_type(f"{slug}: source and copy identities are inconsistent")
        if (
            source_final.page_id != source.page_id
            or source_final.title != source.title
            or source_final.url != source.url
            or source_final.parent_page_id != source.parent_page_id
            or source_final.body != source.body
            or source_final.last_edited_time != source.last_edited_time
        ):
            raise error_type(f"{slug}: source changed after copy updates")
        source_fetched_at = _parse_time(
            source.connector_as_of, error_type, "source fetch"
        )
        source_final_fetched_at = _parse_time(
            source_final.connector_as_of, error_type, "final source fetch"
        )
        copy_fetched_at = _parse_time(copy.connector_as_of, error_type, "copy fetch")
        if not (source_fetched_at <= duplicated_at <= copy_fetched_at):
            raise error_type(f"{slug}: copy provenance timestamps are invalid")
        source_final_fetch_times.append(source_final_fetched_at)
        if re.search(r"<(?:page|database)\s+url=", copy.body):
            raise error_type(f"{slug}: copy contains child pages or databases")
        try:
            source_semantics = parse_notion_semantics(source.body, slug)
            copy_semantics = parse_notion_semantics(copy.body, slug)
        except ValueError:
            raise error_type(f"{slug}: source copy semantics are invalid") from None
        if source_semantics.sha256 != copy_semantics.sha256:
            raise error_type(f"{slug}: initial copy differs from its source")

        draft_entry = PublicationEntry(
            slug=slug,
            title=title,
            page_id=page_id,
            parent_page_id=NOTION_DRAFT_PARENT_PAGE_ID,
            url=url,
            marker=canonical.marker,
            prepared_path=canonical.prepared_path,
            body_sha256=canonical.body_sha256,
            semantic_sha256=canonical.semantic_sha256,
        )
        target_receipt = _load_json(
            draft_fetched / f"{slug}.json",
            error_type,
            f"{slug} draft publication receipt",
        )
        target_body = _read_root_file(
            repository_root,
            f"out/notion/draft/fetched/{slug}.md",
            error_type,
            f"{slug} draft read-back",
        )
        try:
            semantic = parse_notion_semantics(target_body.decode("utf-8"), slug)
        except (UnicodeError, ValueError):
            raise error_type(
                f"{slug}: draft read-back semantic content is invalid"
            ) from None
        if semantic.sha256 != canonical.semantic_sha256:
            raise error_type(f"{slug}: draft read-back differs from reviewed report")
        _verify_publication_receipt(
            repository_root,
            draft_entry,
            target_receipt,
            target_body,
            error_type,
        )
        updated_at = _parse_time(
            target_receipt.get("updated_at"), error_type, "draft update"
        )
        if updated_at < duplicated_at:
            raise error_type(f"{slug}: draft was updated before it was duplicated")
        if copy_fetched_at > updated_at:
            raise error_type(f"{slug}: copy fetch must precede update")
        updated_times.append(updated_at)
        target_entries.append(draft_entry)

    if tuple(entry.slug for entry in target_entries) != tuple(expected_by_slug):
        raise error_type("draft target order is invalid")
    if any(fetched_at < max(updated_times) for fetched_at in source_final_fetch_times):
        raise error_type("final source fetch predates copy updates")
    duplicate_manifest = SimpleNamespace(
        parent_page_id=NOTION_DRAFT_PARENT_PAGE_ID,
        entries=tuple(target_entries),
    )
    _verify_duplicate_searches(
        repository_root,
        draft_fetched,
        duplicate_manifest,
        error_type,
    )
    searches = _load_json(
        draft_fetched / "duplicate-search.json",
        error_type,
        "draft duplicate searches",
    )["searches"]
    last_update = max(updated_times)
    if any(
        _parse_time(search.get("searched_at"), error_type, "draft duplicate search")
        < last_update
        for search in searches
    ):
        raise error_type("draft duplicate search predates the copy updates")
    raise error_type(
        "Notion Search is not an exhaustive uniqueness proof; "
        "no independent complete inventory evidence is present"
    )


def _read_fetch(
    root: Path,
    path: str,
    error_type: type[ValueError],
    label: str,
) -> NotionFetchEvidence:
    from delta.notion_gate import _read_root_file

    raw = _read_root_file(root, path, error_type, label)
    try:
        return parse_notion_fetch_result(raw)
    except ExternalEvidenceError as error:
        raise error_type(f"{label} is invalid: {error}") from None


def _normalized_page_id(value: object, error_type: type[ValueError]) -> str:
    if not isinstance(value, str) or _PAGE_ID.fullmatch(value) is None:
        raise error_type("draft copy page ID is invalid")
    return value
