"""Project configuration and runtime-directory setup."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class SettingsError(ValueError):
    """Raised when required project configuration is unavailable."""


@dataclass(frozen=True, repr=False)
class Settings:
    organization: str
    project: str
    page_ids: tuple[int, ...]
    process_name: str
    api_version: str
    pat: str
    output_root: Path
    wiki_id: Optional[str] = None
    process_id: Optional[str] = None

    @classmethod
    def load(cls, project_root: Path) -> "Settings":
        file_pat = _load_dotenv_pat(project_root)
        pat = os.environ.get("AZDO_PAT") or file_pat
        if not pat:
            raise SettingsError(
                "AZDO_PAT is required; add it to .env or the environment"
            )
        return cls(
            organization="bancodonordeste",
            project="Torre CCR - Concessão de Crédito",
            page_ids=(35, 10, 9, 37),
            process_name="Processo-Agil",
            api_version="7.1",
            pat=pat,
            output_root=project_root / "out",
        )

    def __repr__(self) -> str:
        return (
            "Settings(organization='bancodonordeste', "
            "process_name='Processo-Agil', pat='<redacted>')"
        )


def _load_dotenv_pat(project_root: Path) -> Optional[str]:
    env_path = project_root / ".env"
    if not env_path.exists():
        return None

    file_values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        env_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SettingsError(f"Invalid .env entry on line {line_number}")
        key, value = (part.strip() for part in line.split("=", 1))
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        file_values[key] = value
    return file_values.get("AZDO_PAT")


def ensure_runtime_directories(project_root: Path) -> tuple[Path, ...]:
    paths = (
        project_root / "out" / "raw",
        project_root / "out" / "normalized",
        project_root / "out" / "reports",
        project_root / "out" / "notion",
    )
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    return paths
