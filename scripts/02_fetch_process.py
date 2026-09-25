#!/usr/bin/env -S uv run python
"""Collect the complete Processo-Agil definition into an atomic snapshot.

By default, a cached snapshot is reused. If no snapshot is found, the command
performs an initial read-only REST collection. Use --refresh to recollect and
atomically replace the snapshot.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from doc_azure.azure_client import AzureReadClient  # noqa: E402
from doc_azure.process_collector import (  # noqa: E402
    ARTIFACT_KINDS,
    GLOBAL_ARTIFACT_PATHS,
    MAPPING_ARTIFACT_PATH,
    read_cached_process_manifest,
)
from doc_azure.process_runtime import (  # noqa: E402
    Clock,
    HttpClientFactory,
    collect_process_with_settings,
    make_http_client,
    utc_now,
)
from doc_azure.settings import Settings  # noqa: E402
from doc_azure.snapshot import SnapshotManifest  # noqa: E402


SettingsLoader = Callable[[Path], Settings]


async def _collect_with_settings(
    project_root: Path,
    settings: Settings,
    *,
    refresh: bool,
    http_client_factory: HttpClientFactory,
    now: Clock,
) -> tuple[SnapshotManifest, int]:
    """Compatibility seam delegating to the shared collection runtime."""

    return await collect_process_with_settings(
        project_root,
        settings,
        refresh=refresh,
        http_client_factory=http_client_factory,
        now=now,
        azure_client_factory=AzureReadClient,
    )


def _artifact_counts(manifest: SnapshotManifest) -> Counter[str]:
    counts: Counter[str] = Counter()
    for artifact in manifest.artifacts:
        path = Path(artifact.path)
        if artifact.path in GLOBAL_ARTIFACT_PATHS:
            counts["globals"] += 1
        elif artifact.path == MAPPING_ARTIFACT_PATH:
            counts["mapping"] += 1
        elif path.name.removesuffix(".json") in ARTIFACT_KINDS:
            counts[path.name.removesuffix(".json")] += 1
    return counts


def _print_result(manifest: SnapshotManifest, *, request_count: int) -> None:
    counts = _artifact_counts(manifest)
    for family in ("globals", "mapping", *ARTIFACT_KINDS):
        print(f"{family}: {counts[family]}")
    print(f"requests: {request_count}")


def main(
    argv: Sequence[str] | None = None,
    *,
    project_root: Path = PROJECT_ROOT,
    settings_loader: SettingsLoader = Settings.load,
    http_client_factory: HttpClientFactory = make_http_client,
    now: Clock = utc_now,
) -> int:
    """Check cache first, then run one coroutine for a required collection."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="fetch and atomically replace the complete process snapshot",
    )
    args = parser.parse_args(argv)

    if not args.refresh:
        try:
            cached_manifest = read_cached_process_manifest(project_root)
        except Exception:
            print(
                "ERROR: cached process snapshot failed validation",
                file=sys.stderr,
            )
            return 1
        if cached_manifest is not None:
            _print_result(cached_manifest, request_count=0)
            return 0

    try:
        settings = settings_loader(project_root)
        manifest, request_count = asyncio.run(
            _collect_with_settings(
                project_root,
                settings,
                refresh=args.refresh,
                http_client_factory=http_client_factory,
                now=now,
            )
        )
    except Exception:
        print("ERROR: process collection failed safely", file=sys.stderr)
        return 1

    if not manifest.complete:
        print("ERROR: process collection is incomplete", file=sys.stderr)
        return 1
    _print_result(manifest, request_count=request_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
