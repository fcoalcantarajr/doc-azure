"""Tests for one-command, secret-free help on every user-facing script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    "script",
    (
        "setup.py",
        "01_fetch_wiki.py",
        "02_fetch_process.py",
        "03_build_delta.py",
        "04_prepare_notion.py",
    ),
)
def test_script_help_never_requires_credentials(script: str) -> None:
    completed = subprocess.run(
        (sys.executable, f"scripts/{script}", "--help"),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env={"PATH": str(Path(sys.executable).parent)},
    )

    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout.lower()
