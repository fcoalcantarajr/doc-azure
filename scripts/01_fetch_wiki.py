#!/usr/bin/env -S uv run python
"""Fetch Azure DevOps wiki pages (idempotent, GET-only)."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path

import httpx


def _basic_auth(pat: str) -> str:
    """Return the Basic authorization header value for an Azure DevOps PAT."""
    encoded = base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


# ─── constants ─────────────────────────────────────────────────────────────────

RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
SEMAPHORE_LIMIT = 4
API_VERSION = "7.1"

ORG_URL = "https://dev.azure.com/bancodonordeste"
PROJECT_ID = "7ee590c5-7201-4acc-83f5-3e73023a0ab1"
WIKI_ID = "87014e24-4977-4d27-8e12-c05208008d95"

# page_id → slug mapping (from wiki page IDs to file names)
PAGE_ID_MAP: dict[int, str] = {
    35: "leiame",
    10: "politicas",
    9: "changelog",
    37: "apendice",
}

# slug → wiki page path (display path in wiki)
PAGE_PATHS: dict[str, str] = {
    "leiame": "/Home",
    "politicas": "/Template de políticas explícitas",
    "changelog": "/Changelog",
    "apendice": "/Apêndice Técnico - Processo Organização Única",
}

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_WIKI = REPO_ROOT / "out" / "wiki"


# ── HTTP client ───────────────────────────────────────────────────────────────

async def _fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    semaphore: asyncio.Semaphore,
) -> httpx.Response:
    """Fetch URL with retry on transient errors; respect Retry-After header."""

    async with semaphore:
        retry_count = 0
        while True:
            response = await client.get(url, headers=headers)
            if response.status_code not in RETRY_STATUSES:
                return response

            retry_count += 1
            if retry_count >= 5:
                response.raise_for_status()

            retry_after = response.headers.get("Retry-After", "1")
            try:
                wait = float(retry_after)
            except ValueError:
                wait = 1.0
            await asyncio.sleep(wait)


# ── core logic ────────────────────────────────────────────────────────────────

async def fetch_page(
    client: httpx.AsyncClient,
    pat: str,
    slug: str,
    page_path: str,
    semaphore: asyncio.Semaphore,
) -> tuple[str, str]:
    """Fetch one wiki page by path and return (slug, content)."""

    from urllib.parse import quote

    encoded_path = quote(page_path, safe="")
    url = (
        f"{ORG_URL}/{PROJECT_ID}/_apis/wiki/wikis/{WIKI_ID}"
        f"/pages/{encoded_path}?includeContent=true&api-version={API_VERSION}"
    )
    headers = {
        "Accept": "application/json",
        "Authorization": _basic_auth(pat),
    }

    response = await _fetch_with_retry(client, url, headers, semaphore)

    if response.status_code == 404:
        # Page doesn't exist - return empty content (will create stub file)
        return slug, ""

    response.raise_for_status()
    data = response.json()

    content = data.get("content", "") or ""
    if isinstance(content, dict):
        content = json.dumps(content)

    return slug, content


async def fetch_all_pages(pat: str, refresh: bool) -> dict[str, Path]:
    """Fetch all configured wiki pages; write to out/wiki/<slug>.md."""

    OUT_WIKI.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, Path] = {}

    async with httpx.AsyncClient(timeout=60.0) as client:
        semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
        tasks = [
            fetch_page(client, pat, slug, page_path, semaphore)
            for slug, page_path in PAGE_PATHS.items()
        ]

        for coro in asyncio.as_completed(tasks):
            slug, content = await coro
            out_path = OUT_WIKI / f"{slug}.md"

            # Idempotency: skip if file exists and not refresh
            if out_path.exists() and not refresh:
                print(f"  [skip] {slug}.md (exists, use --refresh to refetch)")
                outputs[slug] = out_path
                continue

            out_path.write_text(content, encoding="utf-8")
            if content:
                print(f"  [saved] {slug}.md ({len(content)} chars)")
            else:
                print(f"  [stub] {slug}.md (empty - page not found)")
            outputs[slug] = out_path

    return outputs


def _track_calls(increment: int = 0) -> None:
    """Write a simple network-call counter to out/_calls.json."""
    calls_file = REPO_ROOT / "out" / "_calls.json"
    try:
        data = json.loads(calls_file.read_text()) if calls_file.exists() else {}
    except Exception:
        data = {}
    data["network_calls"] = data.get("network_calls", 0) + increment
    calls_file.parent.mkdir(parents=True, exist_ok=True)
    calls_file.write_text(json.dumps(data), encoding="utf-8")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Azure DevOps wiki pages")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch even if output files already exist",
    )
    args = parser.parse_args()

    pat = _load_pat()
    if not pat:
        print("ERROR: AZDO_PAT not set", file=sys.stderr)
        return 1

    _track_calls(0)  # initialize counter on first run

    try:
        outputs = asyncio.run(fetch_all_pages(pat, args.refresh))
    except httpx.HTTPStatusError as exc:
        print(f"HTTP error: {exc.response.status_code} {exc.request.url}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"\nFetched {len(outputs)} wiki page(s) → out/wiki/")
    return 0


def _load_pat() -> str | None:
    env_pat = Path(".env").read_text() if Path(".env").exists() else ""
    for line in env_pat.splitlines():
        line = line.strip()
        if line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            if key.strip() == "AZDO_PAT":
                return val.strip().strip("'\"")
    import os
    return os.environ.get("AZDO_PAT")


if __name__ == "__main__":
    sys.exit(main())