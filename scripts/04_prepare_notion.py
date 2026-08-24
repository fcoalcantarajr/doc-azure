#!/usr/bin/env -S uv run python
"""Prepare local Notion bodies or verify connector-fetched read-back files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from delta.notion import (
    NotionPublicationError,
    expected_publication_manifest,
    load_publication_manifest,
    prepare_notion,
    verify_fetched_notion,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse preparation and non-mutating read-back verification modes."""

    parser = argparse.ArgumentParser(
        description="Prepare deterministic bodies for four existing Notion pages."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_ROOT,
        help="project root containing deltas and out/notion",
    )
    parser.add_argument(
        "--verify-fetched",
        type=Path,
        metavar="DIRECTORY",
        help="verify connector-fetched <slug>.json and <slug>.md receipts",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Prepare files locally, or validate fetched files without external writes."""

    arguments = parse_args(argv)
    try:
        if arguments.verify_fetched is None:
            manifest = prepare_notion(arguments.root)
            print(arguments.root / "out" / "notion" / "publication-manifest.json")
            for entry in manifest.entries:
                print(arguments.root / entry.prepared_path)
        else:
            manifest_path = (
                arguments.root / "out" / "notion" / "publication-manifest.json"
            )
            manifest = load_publication_manifest(manifest_path)
            if manifest != expected_publication_manifest(arguments.root):
                raise NotionPublicationError(
                    "publication manifest is stale relative to versioned reports"
                )
            verify_fetched_notion(manifest, arguments.verify_fetched)
            print("NOTION_FETCHED_OK")
    except NotionPublicationError as error:
        print(f"NOTION_PREPARATION_FAILED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
