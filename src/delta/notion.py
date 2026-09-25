"""Prepare exact delta bodies and verify read-back Notion receipts locally."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from delta.notion_semantics import (
    ReportSemantic,
    ReportSemanticError,
    parse_notion_semantics,
    parse_report_semantics,
    render_notion_body,
)


NOTION_AZURE_PAGE_ID = "2a1412e0-8c26-803b-a988-dc619a396e45"
NOTION_PARENT_PAGE_ID = "66b81130-f72c-4864-9e1e-534c7459d620"
NOTION_DRAFT_PARENT_PAGE_ID = "2d5412e0-8c26-803d-9e30-ec56c88af85f"
_PAGE_METADATA = {
    "leiame": {
        "title": "Delta — Leiame × Processo-Agil implementado",
        "page_id": "3c3412e0-8c26-813c-ad9c-d57026cfd566",
        "url": "https://app.notion.com/p/3c3412e08c26813cad9cd57026cfd566",
    },
    "politicas": {
        "title": "Delta — Políticas Explícitas × Processo-Agil implementado",
        "page_id": "3c3412e0-8c26-813a-8312-dc52450adf39",
        "url": "https://app.notion.com/p/3c3412e08c26813a8312dc52450adf39",
    },
    "changelog": {
        "title": (
            "Delta — Changelog - Processo Ágil no Azure DevOps × "
            "Processo-Agil implementado"
        ),
        "page_id": "3c3412e0-8c26-81b8-b9fd-cca04e04452b",
        "url": "https://app.notion.com/p/3c3412e08c2681b8b9fdcca04e04452b",
    },
    "apendice": {
        "title": (
            "Delta — Apêndice Técnico — Processo Organização Única × "
            "Processo-Agil implementado"
        ),
        "page_id": "3c3412e0-8c26-81dc-81c1-fbf0c7cac428",
        "url": "https://app.notion.com/p/3c3412e08c2681dc81c1fbf0c7cac428",
    },
}
_ENTRY_FIELDS = frozenset(
    {
        "slug",
        "title",
        "page_id",
        "parent_page_id",
        "url",
        "marker",
        "prepared_path",
        "body_sha256",
        "semantic_sha256",
    }
)
PUBLICATION_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "slug",
        "title",
        "page_id",
        "parent_page_id",
        "url",
        "marker",
        "updated_at",
        "fetched_at",
        "connector_as_of",
        "last_edited_available",
        "last_edited_time",
        "semantic_sha256",
        "raw_fetch_path",
        "raw_fetch_sha256",
        "update_receipt_path",
        "update_receipt_sha256",
    }
)
_HASH = re.compile(r"^[0-9a-f]{64}$")
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class NotionPublicationError(ValueError):
    """Raised when local publication artifacts or read-back receipts disagree."""


@dataclass(frozen=True)
class PublicationEntry:
    """One existing Notion page and the exact local body prepared for it."""

    slug: str
    title: str
    page_id: str
    parent_page_id: str
    url: str
    marker: str
    prepared_path: str
    body_sha256: str
    semantic_sha256: str


@dataclass(frozen=True)
class PublicationManifest:
    """Deterministic local handoff for updating existing Notion pages only."""

    schema_version: int
    parent_page_id: str
    entries: tuple[PublicationEntry, ...]


def expected_publication_manifest(root: Path) -> PublicationManifest:
    """Build the expected manifest in memory without writing any file."""

    manifest, _, _ = _collect_entries_and_bodies(Path(root))
    return manifest


def prepare_notion(
    root: Path,
    *,
    repository_url: str | None = None,
    review_base_sha: str | None = None,
    review_head_sha: str | None = None,
) -> PublicationManifest:
    """Validate all sources, then atomically stage four exact delta bodies."""

    repository_root = Path(root)
    if repository_url is None and (
        review_base_sha is not None or review_head_sha is not None
    ):
        raise NotionPublicationError(
            "repository_url is required when binding a review commit range"
        )
    if repository_url is not None:
        from delta.notion_gate import _validate_review_request

        _validate_review_request(
            repository_url,
            review_base_sha,
            review_head_sha,
            NotionPublicationError,
        )
    manifest, bodies, semantics = _collect_entries_and_bodies(repository_root)
    notion_root = repository_root / "out" / "notion"
    for entry, body in zip(manifest.entries, bodies, strict=True):
        _atomic_write_bytes(repository_root / entry.prepared_path, body)
    _atomic_write_json(notion_root / "publication-manifest.json", manifest)
    if repository_url is not None:
        from delta.notion_gate import prepare_review_artifacts

        prepare_review_artifacts(
            repository_root,
            manifest,
            semantics,
            repository_url,
            review_base_sha,
            review_head_sha,
            NotionPublicationError,
        )
    return manifest


def load_publication_manifest(path: Path) -> PublicationManifest:
    """Load and strictly validate one deterministic publication manifest."""

    try:
        payload = json.loads(_read_regular_bytes(Path(path)).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise NotionPublicationError("publication manifest is not valid JSON") from None
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "parent_page_id",
        "entries",
    }:
        raise NotionPublicationError("publication manifest schema is invalid")
    raw_entries = payload["entries"]
    if not isinstance(raw_entries, list):
        raise NotionPublicationError("publication manifest schema is invalid")
    entries: list[PublicationEntry] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict) or set(raw_entry) != _ENTRY_FIELDS:
            raise NotionPublicationError("publication manifest entry schema is invalid")
        try:
            entries.append(PublicationEntry(**raw_entry))
        except TypeError:
            raise NotionPublicationError(
                "publication manifest entry schema is invalid"
            ) from None
    manifest = PublicationManifest(
        schema_version=payload["schema_version"],
        parent_page_id=payload["parent_page_id"],
        entries=tuple(entries),
    )
    _validate_manifest(manifest)
    return manifest


def verify_fetched_notion(manifest: PublicationManifest, fetched_root: Path) -> None:
    """Reject identity or semantic differences in connector-fetched pages."""

    _validate_manifest(manifest)
    fetched = Path(fetched_root)
    for entry in manifest.entries:
        receipt = _read_receipt(fetched / f"{entry.slug}.json")
        _verify_receipt(entry, receipt)
        body = _read_regular_bytes(fetched / f"{entry.slug}.md")
        try:
            semantic = parse_notion_semantics(body.decode("utf-8"), entry.slug)
        except (UnicodeError, ReportSemanticError):
            raise NotionPublicationError(
                f"{entry.slug}: fetched body semantic content is invalid"
            ) from None
        if semantic.sha256 != entry.semantic_sha256:
            raise NotionPublicationError(
                f"{entry.slug}: body semantic hash does not match manifest"
            )


def verify_review_gate(root: Path) -> None:
    """Verify the two external browser reviews and their reconciliation."""

    from delta.notion_gate import verify_review_gate as verify

    verify(Path(root), NotionPublicationError)


def verify_publication_gate(root: Path) -> None:
    """Verify reviews, publication receipts, and semantic read-back."""

    from delta.notion_gate import verify_publication_gate as verify

    verify(Path(root), NotionPublicationError)


def verify_draft_publication_gate(root: Path) -> None:
    """Verify reviewed copies in Staging without accepting canonical-page edits."""

    from delta.notion_draft_gate import verify_draft_publication_gate as verify

    verify(Path(root), NotionPublicationError)


def _collect_entries_and_bodies(
    root: Path,
) -> tuple[
    PublicationManifest,
    tuple[bytes, ...],
    tuple[ReportSemantic, ...],
]:
    entries: list[PublicationEntry] = []
    bodies: list[bytes] = []
    semantics: list[ReportSemantic] = []
    for slug, metadata in _PAGE_METADATA.items():
        source_body = _read_regular_bytes(root / "deltas" / f"{slug}.md")
        marker = f"DELTA-AUDIT-MARKER-{slug}"
        try:
            semantic = parse_report_semantics(source_body.decode("utf-8"), slug)
        except (UnicodeError, ReportSemanticError) as error:
            raise NotionPublicationError(f"{slug}: {error}") from None
        if semantic.marker != marker:
            raise NotionPublicationError(f"{slug}: publication marker is invalid")
        prepared_body = render_notion_body(semantic).encode("utf-8")
        entries.append(
            PublicationEntry(
                slug=slug,
                title=metadata["title"],
                page_id=metadata["page_id"],
                parent_page_id=NOTION_PARENT_PAGE_ID,
                url=metadata["url"],
                marker=marker,
                prepared_path=f"out/notion/prepared/{slug}.md",
                body_sha256=_sha256(prepared_body),
                semantic_sha256=semantic.sha256,
            )
        )
        bodies.append(prepared_body)
        semantics.append(semantic)
    manifest = PublicationManifest(
        schema_version=2,
        parent_page_id=NOTION_PARENT_PAGE_ID,
        entries=tuple(entries),
    )
    _validate_manifest(manifest)
    return manifest, tuple(bodies), tuple(semantics)


def _validate_manifest(manifest: PublicationManifest) -> None:
    if not isinstance(manifest, PublicationManifest):
        raise NotionPublicationError("publication manifest type is invalid")
    if (
        manifest.schema_version != 2
        or manifest.parent_page_id != NOTION_PARENT_PAGE_ID
        or tuple(entry.slug for entry in manifest.entries)
        != tuple(_PAGE_METADATA)
    ):
        raise NotionPublicationError("publication manifest identity is invalid")
    for entry in manifest.entries:
        metadata = _PAGE_METADATA[entry.slug]
        expected = {
            "title": metadata["title"],
            "page_id": metadata["page_id"],
            "parent_page_id": NOTION_PARENT_PAGE_ID,
            "url": metadata["url"],
            "marker": f"DELTA-AUDIT-MARKER-{entry.slug}",
            "prepared_path": f"out/notion/prepared/{entry.slug}.md",
        }
        if any(getattr(entry, field) != value for field, value in expected.items()):
            raise NotionPublicationError(
                f"{entry.slug}: publication manifest metadata is invalid"
            )
        if not isinstance(entry.body_sha256, str) or _HASH.fullmatch(
            entry.body_sha256
        ) is None:
            raise NotionPublicationError(
                f"{entry.slug}: publication manifest body hash is invalid"
            )
        if not isinstance(entry.semantic_sha256, str) or _HASH.fullmatch(
            entry.semantic_sha256
        ) is None:
            raise NotionPublicationError(
                f"{entry.slug}: publication manifest semantic hash is invalid"
            )


def _read_receipt(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(_read_regular_bytes(path).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise NotionPublicationError(f"cannot read receipt {path.name}") from None
    if not isinstance(payload, dict):
        raise NotionPublicationError(f"receipt {path.name} must be a JSON object")
    return payload


def _verify_receipt(entry: PublicationEntry, receipt: dict[str, object]) -> None:
    expected_fields = {
        "slug": entry.slug,
        "title": entry.title,
        "page_id": entry.page_id,
        "parent_page_id": entry.parent_page_id,
        "url": entry.url,
        "marker": entry.marker,
        "semantic_sha256": entry.semantic_sha256,
    }
    for field, expected in expected_fields.items():
        if receipt.get(field) != expected:
            raise NotionPublicationError(
                f"{entry.slug}: receipt {field} does not match manifest"
            )
    if set(receipt) != PUBLICATION_RECEIPT_FIELDS or receipt.get("schema_version") != 1:
        raise NotionPublicationError(f"{entry.slug}: receipt schema is invalid")


def _atomic_write_json(path: Path, manifest: PublicationManifest) -> None:
    payload = {
        "schema_version": manifest.schema_version,
        "parent_page_id": manifest.parent_page_id,
        "entries": [asdict(entry) for entry in manifest.entries],
    }
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _atomic_write_bytes(path, encoded)


def _atomic_write_bytes(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(body)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    except OSError as error:
        raise NotionPublicationError(f"cannot write {path.name}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _read_regular_bytes(path: Path) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | _NOFOLLOW)
    except OSError:
        raise NotionPublicationError(f"cannot read {path.name}") from None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise NotionPublicationError(f"cannot read {path.name}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()
