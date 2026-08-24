"""Offline orchestration for evidence-backed delta report construction."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path

from delta.catalog import CatalogError, PAGE_SLUGS, load_catalog
from delta.evaluator import EvaluationError, evaluate_claim
from delta.models import AuditResult, ReportProvenance
from delta.render import render_report
from doc_azure.snapshot import (
    SnapshotError,
    read_snapshot_artifact,
    resolve_snapshot_root,
)


class BuildError(RuntimeError):
    """Raised when complete verified inputs cannot produce all reports."""


FIXED_SLUGS = tuple(PAGE_SLUGS.values())


def build_all_reports(
    root: Path,
    catalog_path: Path,
    output_dir: Path,
) -> tuple[Path, ...]:
    """Evaluate all claims and publish four per-file atomic reports with rollback."""

    repository_root = Path(root)
    destination = Path(output_dir)
    try:
        claims = load_catalog(catalog_path)
    except CatalogError as error:
        raise BuildError(f"catalog validation failed: {error}") from None

    grouped = {slug: [] for slug in FIXED_SLUGS}
    for claim in claims:
        grouped[claim.slug].append(claim)
    if any(not grouped[slug] for slug in FIXED_SLUGS):
        raise BuildError("catalog must contain exactly the four fixed pages")

    provenance = _load_report_provenance(repository_root)
    rendered: dict[str, str] = {}
    try:
        for slug in FIXED_SLUGS:
            result = AuditResult(
                tuple(evaluate_claim(claim, repository_root) for claim in grouped[slug])
            )
            rendered[slug] = render_report(result, provenance)
    except (EvaluationError, ValueError) as error:
        raise BuildError(f"claim evaluation failed: {error}") from None
    if _load_report_provenance(repository_root) != provenance:
        raise BuildError("snapshot generation changed during report build")

    _ensure_output_directory(destination)
    temporary_paths: list[Path] = []
    backup_paths: dict[Path, Path | None] = {}
    final_paths: list[Path] = []
    try:
        for slug in FIXED_SLUGS:
            final_path = destination / f"{slug}.md"
            temporary_path = _stage_text(final_path, rendered[slug])
            temporary_paths.append(temporary_path)
            final_paths.append(final_path)
            previous = _read_existing_regular(final_path)
            backup_paths[final_path] = (
                None
                if previous is None
                else _stage_bytes(final_path, previous, suffix=".backup.tmp")
            )
        _publish_with_rollback(temporary_paths, final_paths, backup_paths)
    except OSError:
        raise BuildError("report publication failed") from None
    finally:
        for temporary_path in temporary_paths:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        for backup_path in backup_paths.values():
            if backup_path is None:
                continue
            try:
                backup_path.unlink(missing_ok=True)
            except OSError:
                pass

    return tuple(final_paths)


def _load_report_provenance(root: Path) -> ReportProvenance:
    try:
        wiki_generation, wiki_collected_at, wiki_manifest_hash = (
            _snapshot_metadata(root / "out" / "wiki")
        )
        process_generation, process_collected_at, process_manifest_hash = (
            _snapshot_metadata(root / "out" / "process")
        )
        process_payload = json.loads(
            read_snapshot_artifact(root / "out" / "process", "process.json")
        )
        if not isinstance(process_payload, dict):
            raise ValueError("process response is not an object")
        return ReportProvenance(
            wiki_collected_at=wiki_collected_at,
            wiki_generation_id=wiki_generation,
            wiki_manifest_sha256=wiki_manifest_hash,
            process_collected_at=process_collected_at,
            process_generation_id=process_generation,
            process_manifest_sha256=process_manifest_hash,
            process_name=process_payload.get("name"),
            process_id=process_payload.get("typeId"),
        )
    except (OSError, UnicodeError, ValueError, SnapshotError):
        raise BuildError("snapshot provenance is malformed or incomplete") from None


def _snapshot_metadata(logical_root: Path) -> tuple[str, str, str]:
    resolved = resolve_snapshot_root(logical_root)
    if resolved.parent.name != "snapshots":
        raise ValueError("versioned snapshot generation is required")
    manifest_bytes = _read_existing_regular(resolved / "manifest.json")
    if manifest_bytes is None:
        raise ValueError("snapshot manifest is missing")
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict):
        raise ValueError("snapshot manifest is not an object")
    collected_at = manifest.get("collected_at")
    if not isinstance(collected_at, str):
        raise ValueError("snapshot collected_at is malformed")
    return (
        resolved.name,
        collected_at,
        hashlib.sha256(manifest_bytes).hexdigest(),
    )


def _stage_text(final_path: Path, contents: str) -> Path:
    return _stage_bytes(final_path, contents.encode("utf-8"), suffix=".tmp")


def _stage_bytes(final_path: Path, contents: bytes, *, suffix: str) -> Path:
    descriptor, raw_path = tempfile.mkstemp(
        prefix=f".{final_path.name}.",
        suffix=suffix,
        dir=final_path.parent,
    )
    temporary_path = Path(raw_path)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def _ensure_output_directory(path: Path) -> None:
    if path.is_symlink():
        raise BuildError("report output directory must not be a symlink")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise BuildError("report output directory is unavailable") from None
    if path.is_symlink() or not path.is_dir():
        raise BuildError("report output directory must be a real directory")


def _read_existing_regular(path: Path) -> bytes | None:
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, os.O_RDONLY | no_follow)
    except FileNotFoundError:
        return None
    except OSError:
        raise BuildError(f"existing report must be a regular file: {path.name}") from None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise BuildError(
                f"existing report must be a regular file: {path.name}"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def _publish_with_rollback(
    temporary_paths: list[Path],
    final_paths: list[Path],
    backup_paths: dict[Path, Path | None],
) -> None:
    published: list[Path] = []
    try:
        for temporary_path, final_path in zip(
            temporary_paths, final_paths, strict=True
        ):
            os.replace(temporary_path, final_path)
            published.append(final_path)
    except OSError:
        rollback_failed = False
        for final_path in reversed(published):
            backup_path = backup_paths[final_path]
            try:
                if backup_path is None:
                    final_path.unlink(missing_ok=True)
                else:
                    os.replace(backup_path, final_path)
                    backup_paths[final_path] = None
            except OSError:
                rollback_failed = True
        if rollback_failed:
            raise BuildError("report publication failed and rollback was incomplete") from None
        raise BuildError("report publication failed; previous reports were restored") from None
