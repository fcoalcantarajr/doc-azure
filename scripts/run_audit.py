#!/usr/bin/env -S uv run python
"""Execute the complete deterministic audit without any AI service."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from doc_azure.audit import run_audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--document-baseline", type=Path)
    parser.add_argument("--process-baseline", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="require complete local snapshots")
    mode.add_argument("--refresh", action="store_true", help="collect current sources with read-only REST")
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(run_audit(
            args.root,
            args.catalog or args.root / "config/wiki_claims.json",
            args.document_baseline or args.root / "config/document-coverage.json",
            args.process_baseline or args.root / "config/process-coverage.json",
            offline=args.offline, refresh=args.refresh,
        ))
    except Exception as error:
        # Output failures must not print source bodies, URLs or credentials.
        print(f"RUN_OUTPUT_FAILED: {type(error).__name__}", file=sys.stderr)
        return 4
    status = ("CLEAN", "DELTAS", "COVERAGE_GAP", "ACQUISITION_VALIDATION_FAILED", "INTERNAL_ERROR")[result.exit_code]
    print(f"{status}: {result.logical_sha256}")
    print(args.root / "out/audit/CURRENT")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
