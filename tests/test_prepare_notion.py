"""Tests for local Notion publication preparation and receipt verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from delta.notion import (
    NOTION_PARENT_PAGE_ID,
    NotionPublicationError,
    load_publication_manifest,
    prepare_notion,
    verify_fetched_notion,
)


DELTA_BODIES = {
    "leiame": "# Leiame\n\nDELTA-AUDIT-MARKER-leiame\n\nDelta de leiame.\n",
    "politicas": "# Políticas\n\nDELTA-AUDIT-MARKER-politicas\n\nDelta de políticas.\n",
    "changelog": "# Changelog\n\nDELTA-AUDIT-MARKER-changelog\n\nDelta de changelog.\n",
    "apendice": "# Apêndice\n\nDELTA-AUDIT-MARKER-apendice\n\nDelta de apêndice.\n",
}


def write_delta_files(root: Path) -> None:
    delta_root = root / "deltas"
    delta_root.mkdir()
    for slug, body in DELTA_BODIES.items():
        (delta_root / f"{slug}.md").write_text(body, encoding="utf-8")


def write_fetched_snapshot(root: Path, entry: object, body: str) -> None:
    page = entry
    snapshot = {
        "slug": page.slug,
        "page_id": page.page_id,
        "parent_page_id": page.parent_page_id,
        "url": page.url,
        "marker": page.marker,
    }
    (root / f"{page.slug}.json").write_text(
        json.dumps(snapshot), encoding="utf-8"
    )
    (root / f"{page.slug}.md").write_text(body, encoding="utf-8")


def test_prepare_notion_copies_deltas_and_writes_deterministic_manifest(
    tmp_path: Path,
) -> None:
    write_delta_files(tmp_path)

    manifest = prepare_notion(tmp_path)

    manifest_path = tmp_path / "out" / "notion" / "publication-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest.parent_page_id == NOTION_PARENT_PAGE_ID
    assert payload["parent_page_id"] == NOTION_PARENT_PAGE_ID
    assert [entry.slug for entry in manifest.entries] == list(DELTA_BODIES)
    for entry in manifest.entries:
        prepared = tmp_path / "out" / "notion" / "prepared" / f"{entry.slug}.md"
        assert prepared.read_text(encoding="utf-8") == DELTA_BODIES[entry.slug]
        assert entry.body_sha256 == hashlib.sha256(
            DELTA_BODIES[entry.slug].encode("utf-8")
        ).hexdigest()
        assert entry.marker == f"DELTA-AUDIT-MARKER-{entry.slug}"

    assert prepare_notion(tmp_path) == manifest
    assert load_publication_manifest(manifest_path) == manifest


def test_prepare_notion_rejects_a_body_without_its_marker_before_writing(
    tmp_path: Path,
) -> None:
    write_delta_files(tmp_path)
    (tmp_path / "deltas" / "leiame.md").write_text(
        "# Leiame sem marcador\n", encoding="utf-8"
    )

    with pytest.raises(NotionPublicationError, match="marker"):
        prepare_notion(tmp_path)

    assert not (tmp_path / "out").exists()


def test_verify_fetched_notion_accepts_matching_receipts(tmp_path: Path) -> None:
    write_delta_files(tmp_path)
    manifest = prepare_notion(tmp_path)
    fetched_root = tmp_path / "fetched"
    fetched_root.mkdir()
    for entry in manifest.entries:
        write_fetched_snapshot(fetched_root, entry, DELTA_BODIES[entry.slug])

    verify_fetched_notion(manifest, fetched_root)


def test_verify_fetched_notion_rejects_body_hash_mismatch(tmp_path: Path) -> None:
    write_delta_files(tmp_path)
    manifest = prepare_notion(tmp_path)
    fetched_root = tmp_path / "fetched"
    fetched_root.mkdir()
    for entry in manifest.entries:
        body = "alterado" if entry.slug == "leiame" else DELTA_BODIES[entry.slug]
        write_fetched_snapshot(fetched_root, entry, body)

    with pytest.raises(NotionPublicationError, match="body hash"):
        verify_fetched_notion(manifest, fetched_root)


def test_verify_fetched_notion_rejects_wrong_parent_receipt(tmp_path: Path) -> None:
    write_delta_files(tmp_path)
    manifest = prepare_notion(tmp_path)
    fetched_root = tmp_path / "fetched"
    fetched_root.mkdir()
    for entry in manifest.entries:
        write_fetched_snapshot(fetched_root, entry, DELTA_BODIES[entry.slug])
    leiame_receipt = fetched_root / "leiame.json"
    payload = json.loads(leiame_receipt.read_text(encoding="utf-8"))
    payload["parent_page_id"] = "wrong-parent"
    leiame_receipt.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(NotionPublicationError, match="parent_page_id"):
        verify_fetched_notion(manifest, fetched_root)


@pytest.mark.parametrize("field", ("page_id", "url", "marker"))
def test_verify_fetched_notion_rejects_missing_identity_field(
    tmp_path: Path,
    field: str,
) -> None:
    write_delta_files(tmp_path)
    manifest = prepare_notion(tmp_path)
    fetched_root = tmp_path / "fetched"
    fetched_root.mkdir()
    for entry in manifest.entries:
        write_fetched_snapshot(fetched_root, entry, DELTA_BODIES[entry.slug])
    receipt = fetched_root / "leiame.json"
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    del payload[field]
    receipt.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(NotionPublicationError, match=field):
        verify_fetched_notion(manifest, fetched_root)


def test_load_publication_manifest_rejects_missing_body_hash(
    tmp_path: Path,
) -> None:
    write_delta_files(tmp_path)
    prepare_notion(tmp_path)
    manifest_path = tmp_path / "out" / "notion" / "publication-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    del payload["entries"][0]["body_sha256"]
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(NotionPublicationError, match="schema"):
        load_publication_manifest(manifest_path)
