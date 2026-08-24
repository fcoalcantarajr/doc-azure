#!/usr/bin/env -S uv run python
"""Validate local configuration and create only required runtime directories."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from doc_azure.settings import (  # noqa: E402
    Settings,
    SettingsError,
    ensure_runtime_directories,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse arguments before configuration so --help never needs a secret."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_ROOT,
        help="project root containing .env and ignored out/ artifacts",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Validate credentials and idempotently create exact runtime roots."""

    arguments = parse_args(argv)
    try:
        Settings.load(arguments.root)
        directories = ensure_runtime_directories(arguments.root)
    except (OSError, UnicodeError, SettingsError):
        print("SETUP_FAILED: local configuration is invalid", file=sys.stderr)
        return 1
    for directory in directories:
        print(directory)
    print("CONFIGURATION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
