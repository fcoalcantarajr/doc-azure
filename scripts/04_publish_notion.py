#!/usr/bin/env -S uv run python
"""Publish delta pages to Notion via REST API.
Requires NOTION_TOKEN in .env. Without it, prints NOTION_TOKEN_ABSENT and exits 0.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    import argparse
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"

    parser = argparse.ArgumentParser(description="Publish deltas to Notion")
    parser.add_argument("--refresh", action="store_true", help="Force republish")
    args = parser.parse_args()

    # Check for NOTION_TOKEN
    token = None
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                if key.strip() == "NOTION_TOKEN":
                    token = val.strip().strip("'\"")
                    break

    if not token:
        print("NOTION_TOKEN_ABSENT")
        return 0

    # NOTION_TOKEN present - implement REST API publication here
    print("Notion publication via REST API not yet implemented")
    print("Use Notion MCP tool for publication when NOTION_TOKEN is absent")
    return 0


if __name__ == "__main__":
    sys.exit(main())