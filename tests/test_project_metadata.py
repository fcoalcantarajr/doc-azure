"""Keep the executable packaging contract aligned with the setup guide."""

from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_runtime_and_development_dependencies_are_separated_and_documented() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]

    assert project["requires-python"] == ">=3.11"
    assert project["dependencies"] == ["httpx>=0.25.0"]
    assert metadata["dependency-groups"]["dev"] == ["pytest>=8.0.0"]

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Python 3.11+" in readme
    assert "`httpx>=0.25.0`" in readme
    assert "`pytest>=8.0.0`" in readme
