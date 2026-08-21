#!/usr/bin/env -S uv run python
"""Fetch Azure DevOps process model (idempotent, GET-only)."""

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
FIELDS_API_VERSION = "4.1-preview.1"

BASE_URL = "https://dev.azure.com/bancodonordeste"
PROCESS_NAME = "Processo-Agil"

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PROCESS = REPO_ROOT / "out" / "process"


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

async def get_process_id(client: httpx.AsyncClient, pat: str) -> str:
    """Get the process ID for 'Processo-Agil' by name."""

    url = f"{BASE_URL}/_apis/work/processes?api-version={API_VERSION}"
    headers = {
        "Accept": "application/json",
        "Authorization": _basic_auth(pat),
    }

    response = await _fetch_with_retry(client, url, headers, asyncio.Semaphore(1))
    response.raise_for_status()
    data = response.json()

    processes = data.get("value", [])
    for proc in processes:
        if proc.get("name") == PROCESS_NAME:
            return proc["typeId"]

    raise RuntimeError(f"Process '{PROCESS_NAME}' not found")


async def fetch_process(
    client: httpx.AsyncClient,
    process_id: str,
    semaphore: asyncio.Semaphore,
    pat: str,
) -> dict:
    """Fetch full process definition."""

    url = f"{BASE_URL}/_apis/work/processes/{process_id}?api-version={API_VERSION}"
    headers = {
        "Accept": "application/json",
        "Authorization": _basic_auth(pat),
    }

    response = await _fetch_with_retry(client, url, headers, semaphore)
    response.raise_for_status()
    return response.json()


async def fetch_wit_list(
    client: httpx.AsyncClient,
    process_id: str,
    semaphore: asyncio.Semaphore,
    pat: str,
) -> list[dict]:
    """Fetch work item types list for a process."""

    url = f"{BASE_URL}/_apis/work/processes/{process_id}/workItemTypes?api-version={API_VERSION}"
    headers = {
        "Accept": "application/json",
        "Authorization": _basic_auth(pat),
    }

    response = await _fetch_with_retry(client, url, headers, semaphore)
    response.raise_for_status()
    return response.json().get("value", [])


async def fetch_wit_fields(
    client: httpx.AsyncClient,
    process_id: str,
    wit_name: str,
    semaphore: asyncio.Semaphore,
    pat: str,
) -> dict:
    """Fetch fields for a work item type."""

    url = (
        f"{BASE_URL}/_apis/work/processes/{process_id}/workItemTypes/{wit_name}/fields"
        f"?api-version={FIELDS_API_VERSION}"
    )
    headers = {
        "Accept": "application/json",
        "Authorization": _basic_auth(pat),
    }

    response = await _fetch_with_retry(client, url, headers, semaphore)
    response.raise_for_status()
    return response.json()


async def fetch_all(process_id: str, pat: str, refresh: bool) -> dict[str, Path]:
    """Fetch process model and all WIT fields; write to out/process/."""

    OUT_PROCESS.mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
    outputs: dict[str, Path] = {}

    process_json_path = OUT_PROCESS / "process.json"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Fetch main process definition
        if process_json_path.exists() and not refresh:
            print(f"  [skip] process.json (exists, use --refresh to refetch)")
            process_data = json.loads(process_json_path.read_text())
        else:
            process_data = await fetch_process(client, process_id, semaphore, pat)
            process_json_path.write_text(json.dumps(process_data, indent=2), encoding="utf-8")
            print(f"  [saved] process.json")
        outputs["process"] = process_json_path

        # Get work item types from separate endpoint (handles inherited processes)
        wit_list = await fetch_wit_list(client, process_id, semaphore, pat)

        # Fetch fields for each WIT using referenceName (API requires referenceName)
        wit_tasks = [
            fetch_wit_fields(client, process_id, wit["referenceName"], semaphore, pat)
            for wit in wit_list
        ]

        wit_results = await asyncio.gather(*wit_tasks, return_exceptions=True) if wit_tasks else []

        for wit_info, wit_result in zip(wit_list, wit_results):
            wit_name = wit_info["name"]
            wit_name_clean = wit_name.replace(" ", "_")
            wit_path = OUT_PROCESS / f"{wit_name_clean}.json"

            if isinstance(wit_result, Exception):
                print(f"  [error] {wit_name_clean}.json: {wit_result}")
                continue

            if wit_path.exists() and not refresh:
                print(f"  [skip] {wit_name_clean}.json (exists, use --refresh to refetch)")
            else:
                wit_path.write_text(json.dumps(wit_result, indent=2), encoding="utf-8")
                print(f"  [saved] {wit_name_clean}.json")
            outputs[wit_name_clean] = wit_path

    return outputs


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


def _get_network_calls() -> int:
    """Read network call counter."""
    calls_file = REPO_ROOT / "out" / "_calls.json"
    if calls_file.exists():
        try:
            data = json.loads(calls_file.read_text())
            return data.get("network_calls", 0)
        except Exception:
            pass
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Azure DevOps process model")
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

    # Try to get process_id from cache first
    process_json_path = OUT_PROCESS / "process.json"
    if process_json_path.exists() and not args.refresh:
        try:
            process_id = json.loads(process_json_path.read_text())["typeId"]
        except Exception:
            process_id = None
    else:
        process_id = None

    try:
        async def _get_id():
            async with httpx.AsyncClient(timeout=60.0) as client:
                return await get_process_id(client, pat)

        if process_id is None:
            process_id = asyncio.run(_get_id())
    except Exception as exc:
        print(f"Error getting process ID: {exc}", file=sys.stderr)
        return 1

    # Count expected network calls for tracking
    calls_increment = 1  # get process ID
    if process_json_path.exists() and not args.refresh:
        calls_increment = 0  # reusing cached process.json, no network calls needed

    try:
        outputs = asyncio.run(fetch_all(process_id, pat, args.refresh))
    except httpx.HTTPStatusError as exc:
        print(f"HTTP error: {exc.response.status_code} {exc.request.url}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Track network calls
    calls_file = REPO_ROOT / "out" / "_calls.json"
    try:
        data = json.loads(calls_file.read_text()) if calls_file.exists() else {}
    except Exception:
        data = {}
    data["network_calls"] = data.get("network_calls", 0) + calls_increment
    calls_file.parent.mkdir(parents=True, exist_ok=True)
    calls_file.write_text(json.dumps(data), encoding="utf-8")

    print(f"\nFetched {len(outputs)} files → out/process/")
    return 0


if __name__ == "__main__":
    sys.exit(main())