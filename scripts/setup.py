"""Validate configuration and create local runtime directories."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from doc_azure.settings import Settings, ensure_runtime_directories  # noqa: E402


def main() -> None:
    Settings.load(PROJECT_ROOT)
    for directory in ensure_runtime_directories(PROJECT_ROOT):
        print(directory)
    print("Configuration OK")


if __name__ == "__main__":
    main()
