"""Atomic, hash-addressed snapshot staging for collected evidence."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from doc_azure.azure_client import RequestRecord


class SnapshotError(RuntimeError):
    """Raised when a snapshot cannot be staged or committed safely."""


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


class SnapshotWriter:
    """Build a complete sibling snapshot before replacing the current one."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        if not self._root.name or self._root.is_symlink():
            raise SnapshotError("snapshot root must be a named non-symlink path")
        if self._root.exists() and not self._root.is_dir():
            raise SnapshotError("snapshot root must be a directory")
        self._root.parent.mkdir(parents=True, exist_ok=True)
        self._staging = Path(
            tempfile.mkdtemp(
                prefix=f".{self._root.name}.staging-", dir=self._root.parent
            )
        )
        self._artifacts: dict[str, SnapshotArtifact] = {}
        self._active = True

    def write_json(
        self, relative_path: str | Path, payload: Mapping[str, object]
    ) -> SnapshotArtifact:
        """Stage deterministic UTF-8 JSON and return its content identity."""

        try:
            content = json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ) + "\n"
        except (TypeError, ValueError):
            raise SnapshotError("artifact must be JSON serializable") from None
        return self.write_text(relative_path, content)

    def write_text(
        self, relative_path: str | Path, content: str
    ) -> SnapshotArtifact:
        """Stage one UTF-8 text artifact beneath the private staging root."""

        self._ensure_active()
        if not isinstance(content, str):
            raise SnapshotError("text artifact content must be a string")
        normalized_path = _validate_relative_path(relative_path)
        destination = self._staging / normalized_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        encoded = content.encode("utf-8")
        destination.write_bytes(encoded)
        artifact = SnapshotArtifact(
            path=normalized_path.as_posix(),
            sha256=hashlib.sha256(encoded).hexdigest(),
        )
        self._artifacts[artifact.path] = artifact
        return artifact

    def commit_manifest(
        self,
        *,
        collected_at: datetime | str,
        requests: Iterable[RequestRecord],
    ) -> SnapshotManifest:
        """Write a complete manifest, then replace the current artifact set."""

        self._ensure_active()
        request_records = tuple(requests)
        if any(not isinstance(record, RequestRecord) for record in request_records):
            raise SnapshotError("manifest requests must be sanitized RequestRecord values")
        manifest = SnapshotManifest(
            schema_version=1,
            complete=True,
            collected_at=_format_collected_at(collected_at),
            requests=request_records,
            artifacts=tuple(
                self._artifacts[path] for path in sorted(self._artifacts)
            ),
        )
        manifest_path = self._staging / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                manifest.as_dict(),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self._replace_current_snapshot()
        return manifest

    def abort(self) -> None:
        """Remove only this writer's private staging directory."""

        if not self._active:
            return
        shutil.rmtree(self._staging, ignore_errors=True)
        self._active = False

    def _replace_current_snapshot(self) -> None:
        backup: Path | None = None
        if self._root.exists():
            backup = Path(
                tempfile.mkdtemp(
                    prefix=f".{self._root.name}.backup-", dir=self._root.parent
                )
            )
            backup.rmdir()
            try:
                os.replace(self._root, backup)
            except OSError as error:
                raise SnapshotError("could not prepare atomic snapshot replacement") from error

        try:
            os.replace(self._staging, self._root)
        except OSError as error:
            if backup is not None and backup.exists() and not self._root.exists():
                try:
                    os.replace(backup, self._root)
                except OSError as restore_error:
                    raise SnapshotError(
                        "snapshot replace failed and previous snapshot could not be restored"
                    ) from restore_error
            raise SnapshotError("snapshot replace failed; previous snapshot restored") from error

        self._active = False
        if backup is not None:
            shutil.rmtree(backup)

    def _ensure_active(self) -> None:
        if not self._active:
            raise SnapshotError("snapshot writer is inactive")


def _validate_relative_path(relative_path: str | Path) -> PurePosixPath:
    raw_path = str(relative_path)
    path = PurePosixPath(raw_path)
    if (
        not raw_path
        or raw_path == "."
        or raw_path.startswith("/")
        or "\\" in raw_path
        or "//" in raw_path
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix().casefold() == "manifest.json"
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
