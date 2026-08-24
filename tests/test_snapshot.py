from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import doc_azure.snapshot as snapshot_module
from doc_azure.azure_client import RequestRecord
from doc_azure.snapshot import SnapshotError, SnapshotWriter


COLLECTED_AT = datetime(2026, 8, 24, 15, 30, tzinfo=timezone.utc)


def staging_directories(parent: Path, root_name: str) -> list[Path]:
    return sorted(parent.glob(f".{root_name}.staging-*"))


def test_failed_refresh_keeps_previous_snapshot(tmp_path: Path) -> None:
    current = tmp_path / "process"
    current.mkdir()
    (current / "process.json").write_text('{"name":"old"}', encoding="utf-8")

    writer = SnapshotWriter(current)
    writer.write_json("process.json", {"name": "new"})
    writer.abort()

    assert json.loads((current / "process.json").read_text()) == {"name": "old"}
    assert staging_directories(tmp_path, "process") == []


def test_commit_writes_complete_manifest_with_exact_artifact_hashes(
    tmp_path: Path,
) -> None:
    current = tmp_path / "wiki"
    writer = SnapshotWriter(current)
    writer.write_text("leiame.md", "# Leia-me\n")
    writer.write_json("metadata/leiame.json", {"id": 35, "title": "Leia-me"})

    manifest = writer.commit_manifest(
        collected_at=COLLECTED_AT,
        requests=(
            RequestRecord(
                "GET", "/project/_apis/wiki/wikis/wiki-id/pages/35"
            ),
        ),
    )

    raw_manifest = json.loads((current / "manifest.json").read_text())
    assert raw_manifest == {
        "schema_version": 1,
        "complete": True,
        "collected_at": "2026-08-24T15:30:00+00:00",
        "requests": [
            {
                "method": "GET",
                "path": "/project/_apis/wiki/wikis/wiki-id/pages/35",
            }
        ],
        "artifacts": [
            {
                "path": "leiame.md",
                "sha256": hashlib.sha256(b"# Leia-me\n").hexdigest(),
            },
            {
                "path": "metadata/leiame.json",
                "sha256": hashlib.sha256(
                    b'{\n  "id": 35,\n  "title": "Leia-me"\n}\n'
                ).hexdigest(),
            },
        ],
    }
    assert manifest.complete is True
    assert tuple(artifact.path for artifact in manifest.artifacts) == (
        "leiame.md",
        "metadata/leiame.json",
    )
    assert staging_directories(tmp_path, "wiki") == []


def test_commit_replaces_the_artifact_set_without_retaining_stale_files(
    tmp_path: Path,
) -> None:
    current = tmp_path / "process"
    current.mkdir()
    (current / "stale.json").write_text("{}", encoding="utf-8")
    writer = SnapshotWriter(current)
    writer.write_json("process.json", {"name": "Processo-Agil"})

    writer.commit_manifest(collected_at=COLLECTED_AT, requests=())

    assert not (current / "stale.json").exists()
    assert json.loads((current / "process.json").read_text()) == {
        "name": "Processo-Agil"
    }


def test_failed_directory_swap_restores_the_previous_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = tmp_path / "process"
    current.mkdir()
    (current / "process.json").write_text('{"name":"old"}', encoding="utf-8")
    writer = SnapshotWriter(current)
    writer.write_json("process.json", {"name": "new"})
    real_replace = snapshot_module.os.replace
    calls = 0

    def fail_new_snapshot(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated swap failure")
        real_replace(source, destination)

    monkeypatch.setattr(snapshot_module.os, "replace", fail_new_snapshot)

    with pytest.raises(SnapshotError, match="replace"):
        writer.commit_manifest(collected_at=COLLECTED_AT, requests=())

    assert json.loads((current / "process.json").read_text()) == {"name": "old"}
    writer.abort()


@pytest.mark.parametrize(
    "relative_path",
    (
        "/absolute.json",
        "../outside.json",
        "nested/../../outside",
        ".",
        "manifest.json",
    ),
)
def test_rejects_paths_that_escape_or_replace_snapshot_metadata(
    tmp_path: Path, relative_path: str
) -> None:
    outside = tmp_path / "outside.json"
    writer = SnapshotWriter(tmp_path / "process")

    with pytest.raises(SnapshotError, match="relative artifact path"):
        writer.write_text(relative_path, "unsafe")

    assert not outside.exists()
    writer.abort()


def test_abort_removes_only_the_callers_staging_directory(tmp_path: Path) -> None:
    current = tmp_path / "process"
    current.mkdir()
    (current / "process.json").write_text('{"name":"old"}', encoding="utf-8")
    first = SnapshotWriter(current)
    second = SnapshotWriter(current)
    first.write_json("process.json", {"name": "first"})
    second.write_json("process.json", {"name": "second"})
    before = staging_directories(tmp_path, "process")
    assert len(before) == 2

    first.abort()

    after = staging_directories(tmp_path, "process")
    assert len(after) == 1
    assert after[0] in before
    assert json.loads((current / "process.json").read_text()) == {"name": "old"}
    second.abort()


def test_writer_cannot_change_files_after_commit_or_abort(tmp_path: Path) -> None:
    committed = SnapshotWriter(tmp_path / "committed")
    committed.write_text("page.md", "content")
    committed.commit_manifest(collected_at=COLLECTED_AT, requests=())
    with pytest.raises(SnapshotError, match="inactive"):
        committed.write_text("other.md", "other")

    aborted = SnapshotWriter(tmp_path / "aborted")
    aborted.abort()
    with pytest.raises(SnapshotError, match="inactive"):
        aborted.write_text("page.md", "content")


def test_json_serialization_is_deterministic(tmp_path: Path) -> None:
    writer = SnapshotWriter(tmp_path / "process")
    artifact = writer.write_json("process.json", {"z": 1, "a": "á"})

    expected = '{\n  "a": "á",\n  "z": 1\n}\n'.encode()
    assert artifact.sha256 == hashlib.sha256(expected).hexdigest()
    writer.abort()
