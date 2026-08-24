from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

import doc_azure.snapshot as snapshot_module
from doc_azure.azure_client import RequestRecord
from doc_azure.snapshot import SnapshotError, SnapshotWriter


COLLECTED_AT = datetime(2026, 8, 24, 15, 30, tzinfo=timezone.utc)


def resolve_snapshot_root(root: Path) -> Path:
    return snapshot_module.resolve_snapshot_root(root)


def staging_directories(root: Path) -> list[Path]:
    return sorted(root.glob(".staging-*"))


def publish_process_snapshot(root: Path, name: str) -> Path:
    writer = SnapshotWriter(root)
    writer.write_json("process.json", {"name": name})
    writer.commit_manifest(collected_at=COLLECTED_AT, requests=())
    return resolve_snapshot_root(root)


def write_legacy_snapshot(root: Path, content: bytes = b'{"name":"legacy"}') -> None:
    root.mkdir(parents=True)
    (root / "process.json").write_bytes(content)
    manifest = {
        "schema_version": 1,
        "complete": True,
        "collected_at": "2026-08-24T15:30:00+00:00",
        "requests": [],
        "artifacts": [
            {
                "path": "process.json",
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        ],
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def test_failed_refresh_keeps_previous_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "process"
    previous = publish_process_snapshot(root, "old")
    writer = SnapshotWriter(root)
    writer.write_json("process.json", {"name": "new"})

    writer.abort()

    assert resolve_snapshot_root(root) == previous
    assert json.loads((previous / "process.json").read_text()) == {"name": "old"}
    assert staging_directories(root) == []


def test_commit_publishes_versioned_snapshot_through_atomic_current_pointer(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wiki"
    writer = SnapshotWriter(root)
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

    resolved = resolve_snapshot_root(root)
    assert resolved.parent == root / "snapshots"
    assert (root / "CURRENT").read_text(encoding="ascii").strip() == resolved.name
    raw_manifest = json.loads((resolved / "manifest.json").read_text())
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


def test_stale_writer_cannot_replace_a_newer_generation(tmp_path: Path) -> None:
    root = tmp_path / "process"
    first = SnapshotWriter(root)
    stale = SnapshotWriter(root)
    first.write_json("process.json", {"name": "first"})
    stale.write_json("process.json", {"name": "stale"})
    first.commit_manifest(collected_at=COLLECTED_AT, requests=())
    first_generation = resolve_snapshot_root(root)

    with pytest.raises(SnapshotError, match="stale"):
        stale.commit_manifest(collected_at=COLLECTED_AT, requests=())

    assert resolve_snapshot_root(root) == first_generation
    assert json.loads((first_generation / "process.json").read_text()) == {
        "name": "first"
    }
    stale.abort()


def test_crash_before_current_swap_keeps_previous_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "process"
    previous = publish_process_snapshot(root, "old")
    writer = SnapshotWriter(root)
    writer.write_json("process.json", {"name": "new"})
    real_replace = snapshot_module.os.replace

    def fail_current_swap(source: Path, destination: Path) -> None:
        if Path(destination) == root / "CURRENT":
            raise OSError("simulated pointer swap failure")
        real_replace(source, destination)

    monkeypatch.setattr(snapshot_module.os, "replace", fail_current_swap)

    with pytest.raises(SnapshotError, match="CURRENT"):
        writer.commit_manifest(collected_at=COLLECTED_AT, requests=())

    assert resolve_snapshot_root(root) == previous
    assert json.loads((previous / "process.json").read_text()) == {"name": "old"}


def test_cleanup_failure_after_publication_cannot_turn_success_into_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "process"
    previous = publish_process_snapshot(root, "old")
    writer = SnapshotWriter(root)
    writer.write_json("process.json", {"name": "new"})

    def fail_cleanup(*args, **kwargs) -> None:
        raise OSError("cleanup forbidden")

    monkeypatch.setattr(snapshot_module.shutil, "rmtree", fail_cleanup)

    writer.commit_manifest(collected_at=COLLECTED_AT, requests=())

    current = resolve_snapshot_root(root)
    assert current != previous
    assert previous.exists()
    assert json.loads((current / "process.json").read_text()) == {"name": "new"}


@pytest.mark.parametrize("damage", ("unregistered", "missing", "empty"))
def test_commit_reenumerates_registered_artifacts_under_lock(
    tmp_path: Path, damage: str
) -> None:
    root = tmp_path / "process"
    writer = SnapshotWriter(root)
    writer.write_json("process.json", {"name": "new"})
    staging = staging_directories(root)[0]
    if damage == "unregistered":
        (staging / "extra.json").write_text("{}", encoding="utf-8")
    elif damage == "missing":
        (staging / "process.json").unlink()
    else:
        (staging / "process.json").write_bytes(b"")

    with pytest.raises(SnapshotError, match=damage):
        writer.commit_manifest(collected_at=COLLECTED_AT, requests=())

    writer.abort()


def test_commit_rejects_symlink_artifact_without_reading_target(tmp_path: Path) -> None:
    root = tmp_path / "process"
    outside = tmp_path / "outside.json"
    outside.write_text('{"private":"outside"}', encoding="utf-8")
    writer = SnapshotWriter(root)
    writer.write_json("process.json", {"name": "new"})
    artifact = staging_directories(root)[0] / "process.json"
    artifact.unlink()
    artifact.symlink_to(outside)

    with pytest.raises(SnapshotError, match="symlink"):
        writer.commit_manifest(collected_at=COLLECTED_AT, requests=())

    writer.abort()


def test_commit_rejects_non_regular_staging_entry(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO creation is unavailable")
    root = tmp_path / "process"
    writer = SnapshotWriter(root)
    writer.write_json("process.json", {"name": "new"})
    os.mkfifo(staging_directories(root)[0] / "unexpected.fifo")

    with pytest.raises(SnapshotError, match="non-regular"):
        writer.commit_manifest(collected_at=COLLECTED_AT, requests=())

    writer.abort()


def test_commit_recalculates_hashes_from_staging_under_lock(tmp_path: Path) -> None:
    root = tmp_path / "process"
    writer = SnapshotWriter(root)
    original = writer.write_text("process.json", '{"name":"first"}\n')
    replacement = b'{"name":"replacement"}\n'
    (staging_directories(root)[0] / "process.json").write_bytes(replacement)

    manifest = writer.commit_manifest(collected_at=COLLECTED_AT, requests=())

    assert manifest.artifacts[0].sha256 == hashlib.sha256(replacement).hexdigest()
    assert manifest.artifacts[0].sha256 != original.sha256


def test_write_does_not_follow_a_staging_parent_symlink(tmp_path: Path) -> None:
    root = tmp_path / "process"
    outside = tmp_path / "outside"
    outside.mkdir()
    writer = SnapshotWriter(root)
    (staging_directories(root)[0] / "nested").symlink_to(outside, target_is_directory=True)

    with pytest.raises(SnapshotError, match="symlink"):
        writer.write_text("nested/private.txt", "must stay inside")

    assert not (outside / "private.txt").exists()
    writer.abort()


@pytest.mark.parametrize(
    "relative_path",
    (
        "",
        ".",
        "./page.md",
        "nested/./page.md",
        "page.md/",
        "/absolute.json",
        "../outside.json",
        "nested/../../outside",
        "nested//alias.json",
        "nul\x00byte.json",
        "line\nbreak.json",
        "tab\tname.json",
        "delete\x7f.json",
        "manifest.json",
        "MANIFEST.JSON",
    ),
)
def test_rejects_noncanonical_or_reserved_artifact_paths(
    tmp_path: Path, relative_path: str
) -> None:
    writer = SnapshotWriter(tmp_path / "process")

    with pytest.raises(SnapshotError, match="relative artifact path"):
        writer.write_text(relative_path, "unsafe")

    writer.abort()


def test_abort_removes_only_the_callers_staging_directory(tmp_path: Path) -> None:
    root = tmp_path / "process"
    previous = publish_process_snapshot(root, "old")
    first = SnapshotWriter(root)
    second = SnapshotWriter(root)
    first.write_json("process.json", {"name": "first"})
    second.write_json("process.json", {"name": "second"})
    before = staging_directories(root)
    assert len(before) == 2

    first.abort()

    after = staging_directories(root)
    assert len(after) == 1
    assert after[0] in before
    assert resolve_snapshot_root(root) == previous
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


def test_resolver_accepts_only_complete_exact_legacy_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "process"
    write_legacy_snapshot(root)

    assert resolve_snapshot_root(root) == root

    (root / "unregistered.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SnapshotError, match="artifact set"):
        resolve_snapshot_root(root)
    (root / "unregistered.json").unlink()

    (root / "process.json").write_text('{"name":"tampered"}', encoding="utf-8")
    with pytest.raises(SnapshotError, match="hash"):
        resolve_snapshot_root(root)


@pytest.mark.parametrize("required_field", ("collected_at", "requests"))
def test_resolver_rejects_legacy_manifest_missing_required_field(
    tmp_path: Path, required_field: str
) -> None:
    root = tmp_path / "process"
    write_legacy_snapshot(root)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop(required_field)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(SnapshotError, match="manifest.*incomplete"):
        resolve_snapshot_root(root)


def test_resolver_prioritizes_current_and_fails_closed_when_it_is_malformed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "process"
    write_legacy_snapshot(root)
    (root / "CURRENT").write_text("../legacy\n", encoding="ascii")

    with pytest.raises(SnapshotError, match="CURRENT"):
        resolve_snapshot_root(root)


@pytest.mark.parametrize("pointer_format", ("{}", " {}\n", "{}\n\n"))
def test_resolver_requires_canonical_current_pointer_bytes(
    tmp_path: Path, pointer_format: str
) -> None:
    root = tmp_path / "process"
    resolved = publish_process_snapshot(root, "current")
    (root / "CURRENT").write_text(
        pointer_format.format(resolved.name), encoding="ascii"
    )

    with pytest.raises(SnapshotError, match="CURRENT"):
        resolve_snapshot_root(root)


def test_resolver_fails_closed_when_current_target_is_missing(tmp_path: Path) -> None:
    root = tmp_path / "process"
    write_legacy_snapshot(root)
    (root / "CURRENT").write_text("0" * 32 + "\n", encoding="ascii")

    with pytest.raises(SnapshotError, match="target"):
        resolve_snapshot_root(root)


def test_resolver_rejects_symlink_current_target_and_artifact(tmp_path: Path) -> None:
    root = tmp_path / "process"
    resolved = publish_process_snapshot(root, "current")
    current_pointer = root / "CURRENT"
    pointer_value = current_pointer.read_text(encoding="ascii")
    current_pointer.unlink()
    pointer_source = tmp_path / "pointer.txt"
    pointer_source.write_text(pointer_value, encoding="ascii")
    current_pointer.symlink_to(pointer_source)
    with pytest.raises(SnapshotError, match="CURRENT.*symlink"):
        resolve_snapshot_root(root)

    current_pointer.unlink()
    current_pointer.write_text(pointer_value, encoding="ascii")
    artifact = resolved / "process.json"
    artifact_content = artifact.read_bytes()
    artifact.unlink()
    outside = tmp_path / "outside.json"
    outside.write_bytes(artifact_content)
    artifact.symlink_to(outside)
    with pytest.raises(SnapshotError, match="artifact.*symlink"):
        resolve_snapshot_root(root)


def test_resolver_rejects_symlink_generation_target(tmp_path: Path) -> None:
    root = tmp_path / "process"
    resolved = publish_process_snapshot(root, "current")
    moved = root / "snapshots" / (resolved.name + "-real")
    resolved.rename(moved)
    resolved.symlink_to(moved, target_is_directory=True)

    with pytest.raises(SnapshotError, match="target.*symlink"):
        resolve_snapshot_root(root)


def test_resolver_rejects_symlink_snapshot_container(tmp_path: Path) -> None:
    root = tmp_path / "process"
    publish_process_snapshot(root, "current")
    snapshots = root / "snapshots"
    moved = root / "snapshots-real"
    snapshots.rename(moved)
    snapshots.symlink_to(moved, target_is_directory=True)

    with pytest.raises(SnapshotError, match="target container.*symlink"):
        resolve_snapshot_root(root)


def test_writer_rejects_symlink_snapshot_container_at_baseline(
    tmp_path: Path,
) -> None:
    root = tmp_path / "process"
    publish_process_snapshot(root, "current")
    snapshots = root / "snapshots"
    moved = root / "snapshots-real"
    snapshots.rename(moved)
    snapshots.symlink_to(moved, target_is_directory=True)

    with pytest.raises(SnapshotError, match="target container.*symlink"):
        SnapshotWriter(root)
