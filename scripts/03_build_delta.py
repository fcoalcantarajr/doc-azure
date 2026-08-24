#!/usr/bin/env -S uv run python
"""Build four deterministic delta reports from verified local snapshots."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from delta.build import BuildError, build_all_reports


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse explicit offline input and output locations."""

    parser = argparse.ArgumentParser(
        description="Build evidence-backed Processo-Agil delta reports offline."
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=PROJECT_ROOT,
        help="root containing the versioned out/wiki and out/process snapshots",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=PROJECT_ROOT / "config" / "wiki_claims.json",
        help="strict explicit-claim catalog",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "deltas",
        help="directory that receives the four deterministic Markdown reports",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the offline build once and report only artifact paths."""

    arguments = parse_args(argv)
    try:
        paths = build_all_reports(
            arguments.evidence_root,
            arguments.catalog,
            arguments.output_dir,
        )
    except BuildError as error:
        print(f"BUILD_FAILED: {error}", file=sys.stderr)
        return 1
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
