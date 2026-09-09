#!/usr/bin/env -S uv run python
"""Prepare ignored coverage candidates; review and version them separately."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from doc_azure.baselines import prepare_baselines
from doc_azure.snapshot import SnapshotWriter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--catalog", type=Path)
    args = parser.parse_args(argv)
    candidates = prepare_baselines(args.root, args.catalog or args.root / "config/wiki_claims.json")
    writer = SnapshotWriter(args.root / "out/baseline-candidate")
    try:
        for name, payload in candidates.items():
            writer.write_json(name, payload)
        writer.commit_manifest(collected_at=datetime.now(timezone.utc), requests=())
    except BaseException:
        writer.abort()
        raise
    print("Candidates prepared; accepted config unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
