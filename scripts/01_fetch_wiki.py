#!/usr/bin/env -S uv run python
"""Collect approved Azure DevOps wiki pages into an atomic snapshot.

By default, a cached snapshot is reused. If no snapshot is found, the command
performs an initial read-only REST collection. Use --refresh to recollect and
atomically replace the snapshot.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from doc_azure.azure_client import AzureReadClient  # noqa: E402
from doc_azure.settings import Settings  # noqa: E402
from doc_azure.snapshot import SnapshotManifest  # noqa: E402
from doc_azure.wiki_collector import (  # noqa: E402
    WIKI_ARTIFACT_PATHS,
    collect_wiki_pages,
    read_cached_wiki_manifest,
)


HttpClientFactory = Callable[[], httpx.AsyncClient]
SettingsLoader = Callable[[Path], Settings]
Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Return an aware UTC collection timestamp."""

    return datetime.now(timezone.utc)


def make_http_client() -> httpx.AsyncClient:
    """Construct the one HTTP transport reused for a live collection."""

    return httpx.AsyncClient(timeout=60.0)


async def _collect_with_settings(
    project_root: Path,
    settings: Settings,
    *,
    refresh: bool,
    http_client_factory: HttpClientFactory,
    now: Clock,
) -> tuple[SnapshotManifest, int]:
    async with http_client_factory() as http:
        client = AzureReadClient(
            http,
            f"https://dev.azure.com/{settings.organization}",
            settings.pat,
            asyncio.Semaphore(4),
        )
        manifest = await collect_wiki_pages(
            project_root,
            client,
            refresh=refresh,
            now=now,
        )
        return manifest, len(client.request_records)


def _print_result(*, action: str, request_count: int) -> None:
    for relative_path in WIKI_ARTIFACT_PATHS:
        print(f"[{action}] out/wiki/{relative_path}")
    print(f"requests: {request_count}")


def main(
    argv: Sequence[str] | None = None,
    *,
    project_root: Path = PROJECT_ROOT,
    settings_loader: SettingsLoader = Settings.load,
    http_client_factory: HttpClientFactory = make_http_client,
    now: Clock = utc_now,
) -> int:
    """Run one cache check and, only when needed, one async collection."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="fetch and atomically replace a complete wiki snapshot",
    )
    args = parser.parse_args(argv)

    if not args.refresh:
        try:
            cached_manifest = read_cached_wiki_manifest(project_root)
        except Exception:
            print("ERROR: cached wiki snapshot failed validation", file=sys.stderr)
            return 1
        if cached_manifest is not None:
            if not cached_manifest.complete:
                print("ERROR: cached wiki snapshot is incomplete", file=sys.stderr)
                return 1
            _print_result(action="skipped", request_count=0)
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
        print("ERROR: wiki collection failed safely", file=sys.stderr)
        return 1

    if not manifest.complete:
        print("ERROR: wiki collection is incomplete", file=sys.stderr)
        return 1
    action = "saved" if request_count else "skipped"
    _print_result(action=action, request_count=request_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
