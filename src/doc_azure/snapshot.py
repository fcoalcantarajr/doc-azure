"""Versioned snapshot publication with a locked atomic current pointer."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import unicodedata
import uuid
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from doc_azure.azure_client import RequestRecord


class SnapshotError(RuntimeError):
    """Raised when a snapshot cannot be staged, resolved, or published safely."""


@dataclass(frozen=True)
class SnapshotArtifact:
    """The relative path and content identity of one staged artifact."""

    path: str
    sha256: str


@dataclass(frozen=True)
class SnapshotManifest:
    """A complete immutable receipt for one collected snapshot."""

    schema_version: int
    complete: bool
    collected_at: str
    requests: tuple[RequestRecord, ...]
    artifacts: tuple[SnapshotArtifact, ...]

    def as_dict(self) -> dict[str, object]:
        """Return the deterministic JSON-compatible manifest representation."""

        return {
            "schema_version": self.schema_version,
            "complete": self.complete,
            "collected_at": self.collected_at,
            "requests": [
                {"method": request.method, "path": request.path}
                for request in self.requests
            ],
            "artifacts": [
                {"path": artifact.path, "sha256": artifact.sha256}
                for artifact in self.artifacts
            ],
        }


_CURRENT = "CURRENT"
_LOCK = ".snapshot.lock"
_MANIFEST = "manifest.json"
_SNAPSHOTS = "snapshots"
_GENERATION_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)


class SnapshotWriter:
    """Stage a generation and publish it only if its baseline remains current."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        _ensure_snapshot_container(self._root)
        with _snapshot_lock(self._root):
            self._expected_publication = _publication_token(self._root)
        self._generation = uuid.uuid4().hex
        self._staging = Path(
            tempfile.mkdtemp(prefix=".staging-", dir=self._root)
        )
        self._registered_paths: set[str] = set()
        self._active = True

    def write_json(
        self, relative_path: str | Path, payload: Mapping[str, object]
    ) -> SnapshotArtifact:
        """Stage deterministic UTF-8 JSON and return its provisional identity."""

        self._ensure_active()
        try:
            content = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            ) + "\n"
        except (TypeError, ValueError):
            raise SnapshotError("artifact must be JSON serializable") from None
        return self.write_text(relative_path, content)

    def write_text(
        self, relative_path: str | Path, content: str
    ) -> SnapshotArtifact:
        """Stage text without following any symlink in its destination path."""

        self._ensure_active()
        if not isinstance(content, str):
            raise SnapshotError("text artifact content must be a string")
        normalized_path = _validate_relative_path(relative_path)
        encoded = content.encode("utf-8")
        _write_file_no_follow(self._staging, normalized_path, encoded)
        path_text = normalized_path.as_posix()
        self._registered_paths.add(path_text)
        return SnapshotArtifact(path_text, hashlib.sha256(encoded).hexdigest())

    def commit_manifest(
        self,
        *,
        collected_at: datetime | str,
        requests: Iterable[RequestRecord],
    ) -> SnapshotManifest:
        """Publish a complete generation with lock-protected compare-and-swap."""

        self._ensure_active()
        request_records = tuple(requests)
        if any(not isinstance(record, RequestRecord) for record in request_records):
            raise SnapshotError("manifest requests must be sanitized RequestRecord values")
        timestamp = _format_collected_at(collected_at)

        with _snapshot_lock(self._root):
            if _publication_token(self._root) != self._expected_publication:
                raise SnapshotError("stale snapshot writer cannot replace current generation")
            artifacts = _enumerate_registered_artifacts(
                self._staging, self._registered_paths
            )
            manifest = SnapshotManifest(
                schema_version=1,
                complete=True,
                collected_at=timestamp,
                requests=request_records,
                artifacts=artifacts,
            )
            manifest_bytes = (
                json.dumps(manifest.as_dict(), ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
            _write_file_no_follow(
                self._staging,
                PurePosixPath(_MANIFEST),
                manifest_bytes,
            )
            self._move_staging_to_generation()
            _publish_current_pointer(self._root, self._generation)

        return manifest

    def abort(self) -> None:
        """Remove only this writer's unpublished staging directory."""

        if not self._active:
            return
        shutil.rmtree(self._staging, ignore_errors=True)
        self._active = False

    def _move_staging_to_generation(self) -> Path:
        snapshots_root = _ensure_real_child_directory(self._root, _SNAPSHOTS)
        generation_root = snapshots_root / self._generation
        if _lexists(generation_root):
            raise SnapshotError("snapshot generation already exists")
        try:
            os.replace(self._staging, generation_root)
        except OSError:
            raise SnapshotError("snapshot generation move failed") from None
        self._active = False
        return generation_root

    def _ensure_active(self) -> None:
        if not self._active:
            raise SnapshotError("snapshot writer is inactive")


def resolve_snapshot_root(root: Path) -> Path:
    """Resolve and verify the immutable generation behind a logical root."""

    logical_root = Path(root)
    _require_real_directory(logical_root, "snapshot root")
    current_path = logical_root / _CURRENT
    if _lexists(current_path):
        generation = _read_current_generation(logical_root)
        snapshots_root = logical_root / _SNAPSHOTS
        _require_real_directory(snapshots_root, "CURRENT target container")
        target = snapshots_root / generation
        _require_real_directory(target, "CURRENT target")
        _validate_complete_snapshot(target, legacy=False)
        return target

    manifest_path = logical_root / _MANIFEST
    if _lexists(manifest_path):
        _validate_complete_snapshot(logical_root, legacy=True)
        return logical_root
    raise SnapshotError("snapshot root has no complete CURRENT or legacy snapshot")


def read_snapshot_artifact(root: Path, relative_path: str | Path) -> bytes:
    """Read one manifested artifact without following path symlinks.

    The artifact digest is checked again in the same operation. This prevents a
    caller from interpreting bytes that changed after the snapshot was resolved.
    """

    normalized_path = _validate_relative_path(relative_path)
    resolved_root = resolve_snapshot_root(root)
    try:
        root_descriptor = os.open(
            resolved_root,
            os.O_RDONLY | _DIRECTORY | _NOFOLLOW,
        )
    except OSError:
        raise SnapshotError("snapshot root changed while being read") from None
    try:
        manifest_bytes = _read_regular_at(
            root_descriptor,
            PurePosixPath(_MANIFEST),
            "manifest",
        )
        expected_hash = _artifact_hash_from_manifest(
            manifest_bytes,
            normalized_path.as_posix(),
        )
        payload = _read_regular_at(
            root_descriptor,
            normalized_path,
            "snapshot artifact",
        )
    finally:
        os.close(root_descriptor)
    if hashlib.sha256(payload).hexdigest() != expected_hash:
        raise SnapshotError("snapshot artifact hash does not match manifest")
    return payload


def read_snapshot_manifest(root: Path) -> SnapshotManifest:
    """Read and parse the selected manifest without following its final path."""

    resolved_root = resolve_snapshot_root(root)
    manifest_bytes = _read_regular_file(resolved_root / _MANIFEST, "manifest")
    return _parse_snapshot_manifest(manifest_bytes)


def _publication_token(root: Path) -> str:
    current_path = root / _CURRENT
    if _lexists(current_path):
        generation = _read_current_generation(root)
        snapshots_root = root / _SNAPSHOTS
        _require_real_directory(snapshots_root, "CURRENT target container")
        target = snapshots_root / generation
        _require_real_directory(target, "CURRENT target")
        _validate_complete_snapshot(target, legacy=False)
        return f"current:{generation}"
    manifest_path = root / _MANIFEST
    if _lexists(manifest_path):
        _validate_complete_snapshot(root, legacy=True)
        return f"legacy:{hashlib.sha256(_read_regular_file(manifest_path, 'manifest')).hexdigest()}"
    return "empty"


@contextmanager
def _snapshot_lock(root: Path) -> Iterator[None]:
    lock_path = root / _LOCK
    flags = os.O_RDWR | os.O_CREAT | _NOFOLLOW
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError:
        raise SnapshotError("snapshot lock is not a safe regular file") from None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise SnapshotError("snapshot lock is not a safe regular file")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    except OSError:
        raise SnapshotError("snapshot interprocess lock failed") from None
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _ensure_snapshot_container(root: Path) -> None:
    if not root.name:
        raise SnapshotError("snapshot root must be a named directory")
    root.parent.mkdir(parents=True, exist_ok=True)
    try:
        root.mkdir(exist_ok=True)
    except OSError:
        raise SnapshotError("snapshot root could not be created safely") from None
    _require_real_directory(root, "snapshot root")


def _ensure_real_child_directory(root: Path, name: str) -> Path:
    child = root / name
    try:
        child.mkdir(exist_ok=True)
    except OSError:
        raise SnapshotError("snapshot control directory is unsafe") from None
    _require_real_directory(child, "snapshot control directory")
    return child


def _require_real_directory(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except (FileNotFoundError, OSError):
        raise SnapshotError(f"{label} is missing") from None
    if stat.S_ISLNK(metadata.st_mode):
        raise SnapshotError(f"{label} is a symlink")
    if not stat.S_ISDIR(metadata.st_mode):
        raise SnapshotError(f"{label} is not a directory")


def _write_file_no_follow(root: Path, relative_path: PurePosixPath, content: bytes) -> None:
    directory_descriptors: list[int] = []
    try:
        current_descriptor = os.open(root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
        directory_descriptors.append(current_descriptor)
        for part in relative_path.parts[:-1]:
            try:
                os.mkdir(part, mode=0o700, dir_fd=current_descriptor)
            except FileExistsError:
                pass
            next_descriptor = os.open(
                part,
                os.O_RDONLY | _DIRECTORY | _NOFOLLOW,
                dir_fd=current_descriptor,
            )
            if not stat.S_ISDIR(os.fstat(next_descriptor).st_mode):
                os.close(next_descriptor)
                raise SnapshotError("staging path contains a symlink or non-directory")
            directory_descriptors.append(next_descriptor)
            current_descriptor = next_descriptor

        file_descriptor = os.open(
            relative_path.name,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | _NOFOLLOW,
            0o600,
            dir_fd=current_descriptor,
        )
        try:
            if not stat.S_ISREG(os.fstat(file_descriptor).st_mode):
                raise SnapshotError("staging destination is symlink or non-regular")
            with os.fdopen(file_descriptor, "wb", closefd=False) as destination:
                destination.write(content)
                destination.flush()
        finally:
            os.close(file_descriptor)
    except SnapshotError:
        raise
    except OSError:
        raise SnapshotError("staging path contains a symlink or non-regular entry") from None
    finally:
        for descriptor in reversed(directory_descriptors):
            os.close(descriptor)


def _enumerate_registered_artifacts(
    staging: Path, registered_paths: set[str]
) -> tuple[SnapshotArtifact, ...]:
    observed: dict[str, tuple[bytes, int]] = {}

    def visit(directory: Path, prefix: PurePosixPath) -> None:
        try:
            entries = tuple(os.scandir(directory))
        except OSError:
            raise SnapshotError("staging contains a non-regular entry") from None
        for entry in entries:
            relative = prefix / entry.name if prefix.parts else PurePosixPath(entry.name)
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError:
                raise SnapshotError("staging contains a non-regular entry") from None
            if stat.S_ISLNK(metadata.st_mode):
                raise SnapshotError("staging artifact is a symlink")
            if stat.S_ISDIR(metadata.st_mode):
                visit(Path(entry.path), relative)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise SnapshotError("staging contains a non-regular entry")
            payload = _read_regular_file(Path(entry.path), "staging artifact")
            observed[relative.as_posix()] = (payload, len(payload))

    visit(staging, PurePosixPath())
    observed_paths = set(observed)
    unregistered = observed_paths - registered_paths
    if unregistered:
        raise SnapshotError("unregistered staging artifact found")
    missing = registered_paths - observed_paths
    if missing:
        raise SnapshotError("missing registered staging artifact")
    if any(size == 0 for _, size in observed.values()):
        raise SnapshotError("empty registered staging artifact")
    if not registered_paths:
        raise SnapshotError("empty registered staging artifact set")
    return tuple(
        SnapshotArtifact(path, hashlib.sha256(observed[path][0]).hexdigest())
        for path in sorted(observed)
    )


def _publish_current_pointer(root: Path, generation: str) -> None:
    temporary = root / f".CURRENT-{uuid.uuid4().hex}.tmp"
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as pointer:
                pointer.write(f"{generation}\n".encode("ascii"))
                pointer.flush()
        finally:
            os.close(descriptor)
        os.replace(temporary, root / _CURRENT)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise SnapshotError("CURRENT atomic publication failed") from None


def _read_current_generation(root: Path) -> str:
    current_path = root / _CURRENT
    payload = _read_regular_file(current_path, "CURRENT")
    if len(payload) > 128:
        raise SnapshotError("CURRENT pointer is malformed")
    try:
        decoded_pointer = payload.decode("ascii")
    except UnicodeDecodeError:
        raise SnapshotError("CURRENT pointer is malformed") from None
    if not decoded_pointer.endswith("\n") or decoded_pointer.count("\n") != 1:
        raise SnapshotError("CURRENT pointer is malformed")
    generation = decoded_pointer[:-1]
    if not _GENERATION_PATTERN.fullmatch(generation):
        raise SnapshotError("CURRENT pointer is malformed")
    return generation


def _validate_complete_snapshot(root: Path, *, legacy: bool) -> None:
    manifest_path = root / _MANIFEST
    manifest_bytes = _read_regular_file(manifest_path, "manifest")
    manifest = _parse_snapshot_manifest(manifest_bytes)
    if not manifest.artifacts:
        raise SnapshotError("snapshot manifest is incomplete")

    expected_hashes = {
        artifact.path: artifact.sha256 for artifact in manifest.artifacts
    }
    if len(expected_hashes) != len(manifest.artifacts):
        raise SnapshotError("snapshot manifest artifact is duplicated")

    observed_files = _snapshot_files(root, legacy=legacy)
    expected_files = set(expected_hashes) | {_MANIFEST}
    if set(observed_files) != expected_files:
        raise SnapshotError("snapshot artifact set does not match manifest")
    for path, expected_hash in expected_hashes.items():
        payload = observed_files[path]
        if not payload:
            raise SnapshotError("snapshot artifact is empty")
        if hashlib.sha256(payload).hexdigest() != expected_hash:
            raise SnapshotError("snapshot artifact hash does not match manifest")


def _parse_snapshot_manifest(manifest_bytes: bytes) -> SnapshotManifest:
    """Parse the strict manifest schema shared by validation and consumers."""

    try:
        payload = json.loads(manifest_bytes)
    except (UnicodeError, ValueError):
        raise SnapshotError("snapshot manifest is malformed") from None
    if (
        not isinstance(payload, dict)
        or set(payload) != {
            "schema_version",
            "complete",
            "collected_at",
            "requests",
            "artifacts",
        }
        or payload.get("schema_version") != 1
        or payload.get("complete") is not True
        or not isinstance(payload.get("collected_at"), str)
        or not payload["collected_at"].strip()
        or not isinstance(payload.get("requests"), list)
        or not isinstance(payload.get("artifacts"), list)
    ):
        raise SnapshotError("snapshot manifest is incomplete")

    requests: list[RequestRecord] = []
    for request in payload["requests"]:
        if not isinstance(request, dict) or set(request) != {"method", "path"}:
            raise SnapshotError("snapshot manifest request is malformed")
        try:
            requests.append(RequestRecord(request["method"], request["path"]))
        except (TypeError, ValueError):
            raise SnapshotError("snapshot manifest request is malformed") from None

    artifacts: list[SnapshotArtifact] = []
    paths: set[str] = set()
    for artifact in payload["artifacts"]:
        if not isinstance(artifact, dict):
            raise SnapshotError("snapshot manifest artifact is malformed")
        if set(artifact) != {"path", "sha256"}:
            raise SnapshotError("snapshot manifest artifact is malformed")
        try:
            path = _validate_relative_path(artifact.get("path"))
        except SnapshotError:
            raise SnapshotError("snapshot manifest artifact is malformed") from None
        digest = artifact.get("sha256")
        if not isinstance(digest, str) or not _HASH_PATTERN.fullmatch(digest):
            raise SnapshotError("snapshot manifest artifact is malformed")
        path_text = path.as_posix()
        if path_text in paths:
            raise SnapshotError("snapshot manifest artifact is duplicated")
        paths.add(path_text)
        artifacts.append(SnapshotArtifact(path_text, digest))
    return SnapshotManifest(
        schema_version=payload["schema_version"],
        complete=payload["complete"],
        collected_at=payload["collected_at"],
        requests=tuple(requests),
        artifacts=tuple(artifacts),
    )


def _snapshot_files(root: Path, *, legacy: bool) -> dict[str, bytes]:
    files: dict[str, bytes] = {}

    def visit(directory: Path, prefix: PurePosixPath) -> None:
        try:
            entries = tuple(os.scandir(directory))
        except OSError:
            raise SnapshotError("snapshot artifact set cannot be read") from None
        for entry in entries:
            if not prefix.parts and legacy and _is_legacy_control_name(entry.name):
                continue
            relative = prefix / entry.name if prefix.parts else PurePosixPath(entry.name)
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError:
                raise SnapshotError("snapshot artifact set cannot be read") from None
            if stat.S_ISLNK(metadata.st_mode):
                label = "manifest" if relative.as_posix() == _MANIFEST else "artifact"
                raise SnapshotError(f"snapshot {label} is a symlink")
            if stat.S_ISDIR(metadata.st_mode):
                visit(Path(entry.path), relative)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise SnapshotError("snapshot contains a non-regular artifact")
            files[relative.as_posix()] = _read_regular_file(
                Path(entry.path), "snapshot artifact"
            )

    visit(root, PurePosixPath())
    return files


def _is_legacy_control_name(name: str) -> bool:
    return (
        name in {_LOCK, _SNAPSHOTS}
        or name.startswith(".staging-")
        or name.startswith(".CURRENT-")
    )


def _read_regular_file(path: Path, label: str) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | _NOFOLLOW)
    except OSError:
        if path.is_symlink():
            raise SnapshotError(f"{label} is a symlink") from None
        raise SnapshotError(f"{label} is missing or unreadable") from None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise SnapshotError(f"{label} is not a regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as source:
            return source.read()
    finally:
        os.close(descriptor)


def _read_regular_at(
    root_descriptor: int,
    relative_path: PurePosixPath,
    label: str,
) -> bytes:
    directory_descriptors: list[int] = []
    current_descriptor = root_descriptor
    try:
        for part in relative_path.parts[:-1]:
            next_descriptor = os.open(
                part,
                os.O_RDONLY | _DIRECTORY | _NOFOLLOW,
                dir_fd=current_descriptor,
            )
            directory_descriptors.append(next_descriptor)
            current_descriptor = next_descriptor
        descriptor = os.open(
            relative_path.name,
            os.O_RDONLY | _NOFOLLOW,
            dir_fd=current_descriptor,
        )
    except OSError:
        for directory_descriptor in reversed(directory_descriptors):
            os.close(directory_descriptor)
        raise SnapshotError(f"{label} is missing, unreadable, or a symlink") from None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise SnapshotError(f"{label} is not a regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as source:
            return source.read()
    finally:
        os.close(descriptor)
        for directory_descriptor in reversed(directory_descriptors):
            os.close(directory_descriptor)


def _artifact_hash_from_manifest(manifest_bytes: bytes, path: str) -> str:
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeError, ValueError):
        raise SnapshotError("snapshot manifest is malformed") from None
    artifacts = manifest.get("artifacts") if isinstance(manifest, dict) else None
    if not isinstance(artifacts, list):
        raise SnapshotError("snapshot manifest is malformed")
    matches = [
        artifact.get("sha256")
        for artifact in artifacts
        if isinstance(artifact, dict) and artifact.get("path") == path
    ]
    if len(matches) != 1 or not isinstance(matches[0], str):
        raise SnapshotError("snapshot artifact is absent from manifest")
    if _HASH_PATTERN.fullmatch(matches[0]) is None:
        raise SnapshotError("snapshot manifest artifact is malformed")
    return matches[0]


def _validate_relative_path(relative_path: object) -> PurePosixPath:
    if not isinstance(relative_path, (str, Path)):
        raise SnapshotError("relative artifact path is invalid")
    raw_path = str(relative_path)
    if (
        not raw_path
        or any(unicodedata.category(character) == "Cc" for character in raw_path)
        or "\\" in raw_path
        or raw_path.startswith("/")
        or raw_path.endswith("/")
        or unicodedata.normalize("NFC", raw_path) != raw_path
    ):
        raise SnapshotError("relative artifact path is invalid")
    path = PurePosixPath(raw_path)
    if (
        not path.parts
        or path.as_posix() != raw_path
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix().casefold() == _MANIFEST
    ):
        raise SnapshotError("relative artifact path is invalid")
    return path


def _format_collected_at(collected_at: datetime | str) -> str:
    if isinstance(collected_at, datetime):
        if collected_at.tzinfo is None or collected_at.utcoffset() is None:
            raise SnapshotError("collected_at datetime must include a timezone")
        return collected_at.isoformat()
    if isinstance(collected_at, str) and collected_at.strip():
        return collected_at
    raise SnapshotError("collected_at must be a non-empty timestamp")


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)
