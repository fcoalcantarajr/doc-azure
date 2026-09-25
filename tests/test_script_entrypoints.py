"""Tests for one-command, secret-free help on every user-facing script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    ("script", "required_terms"),
    (
        (
            "01_fetch_wiki.py",
            (
                "by default",
                "cached snapshot",
                "no snapshot",
                "read-only rest",
                "--refresh",
            ),
        ),
        (
            "02_fetch_process.py",
            (
                "by default",
                "cached snapshot",
                "no snapshot",
                "read-only rest",
                "--refresh",
            ),
        ),
        (
            "run_audit.py",
            (
                "by default",
                "complete local snapshots",
                "missing source snapshots",
                "read-only rest",
                "--offline",
                "--refresh",
            ),
        ),
    ),
)
def test_collection_help_explains_default_network_behavior(
    script: str, required_terms: tuple[str, ...]
) -> None:
    completed = subprocess.run(
        (sys.executable, f"scripts/{script}", "--help"),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env={"PATH": str(Path(sys.executable).parent)},
    )

    assert completed.returncode == 0, completed.stderr
    help_text = " ".join(completed.stdout.split()).casefold()
    missing = [term for term in required_terms if term not in help_text]
    assert not missing, f"{script} help omits cache/network behavior: {missing}"


@pytest.mark.parametrize(
    "script",
    (
        "setup.py",
        "01_fetch_wiki.py",
        "02_fetch_process.py",
        "03_build_delta.py",
        "04_prepare_notion.py",
        "export_process_for_llm.py",
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


def test_notion_entrypoint_exposes_review_and_strict_publication_modes() -> None:
    completed = subprocess.run(
        (sys.executable, "scripts/04_prepare_notion.py", "--help"),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env={"PATH": str(Path(sys.executable).parent)},
    )

    assert completed.returncode == 0, completed.stderr
    assert "--repository-url" in completed.stdout
    assert "--review-base-sha" in completed.stdout
    assert "--review-head-sha" in completed.stdout
    assert "--verify-publication" in completed.stdout


def test_verify_help_exposes_separate_canonical_and_draft_gates() -> None:
    completed = subprocess.run(
        (sys.executable, "verify.py", "--help"),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env={"PATH": str(Path(sys.executable).parent)},
    )

    assert completed.returncode == 0, completed.stderr
    assert "--require-publication" in completed.stdout
    assert "--require-draft-publication" in completed.stdout
