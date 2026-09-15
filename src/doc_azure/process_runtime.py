"""Shared runtime wiring for a single read-only process collection."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import httpx

from doc_azure.azure_client import AzureReadClient
from doc_azure.process_collector import collect_process
from doc_azure.settings import Settings
from doc_azure.snapshot import SnapshotManifest


HttpClientFactory = Callable[[], httpx.AsyncClient]
Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Return an aware UTC publication timestamp."""

    return datetime.now(timezone.utc)


def make_http_client() -> httpx.AsyncClient:
    """Construct the one HTTP transport reused for one collection."""

    return httpx.AsyncClient(timeout=60.0)


async def collect_process_with_settings(
    project_root: Path,
    settings: Settings,
    *,
    refresh: bool,
    http_client_factory: HttpClientFactory = make_http_client,
    now: Clock = utc_now,
    azure_client_factory: Callable[..., AzureReadClient] = AzureReadClient,
) -> tuple[SnapshotManifest, int]:
    """Collect through one client and return the sanitized request count."""

    async with http_client_factory() as http:
        client = azure_client_factory(
            http,
            f"https://dev.azure.com/{settings.organization}",
            settings.pat,
            asyncio.Semaphore(8),
        )
        manifest = await collect_process(
            project_root,
            client,
            refresh=refresh,
            now=now,
        )
        return manifest, len(client.request_records)
