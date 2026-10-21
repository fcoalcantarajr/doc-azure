#!/usr/bin/env -S uv run python
"""Exporte o snapshot do Processo-Agil para consumo por uma LLM."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable, Sequence
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from doc_azure.process_export import (  # noqa: E402
    ProcessExportError,
    ProcessExportResult,
    export_process_for_llm,
)
from doc_azure.azure_client import AzureReadError
from doc_azure.process_collector import ProcessArtifactError
from doc_azure.process_runtime import (  # noqa: E402
    Clock,
    HttpClientFactory,
    collect_process_with_settings,
    make_http_client,
    utc_now,
)
from doc_azure.settings import Settings, SettingsError  # noqa: E402
from doc_azure.snapshot import SnapshotError


SettingsLoader = Callable[[Path], Settings]


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ProcessExportError("argumentos inválidos; execute com --help")


def main(
    argv: Sequence[str] | None = None,
    *,
    project_root: Path = PROJECT_ROOT,
    settings_loader: SettingsLoader = Settings.load,
    http_client_factory: HttpClientFactory = make_http_client,
    now: Clock = utc_now,
) -> int:
    """Optionally refresh only the process, then publish its derived export."""

    parser = _ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="coletar novamente somente o processo via requisições GET",
    )
    parser.add_argument(
        "--root",
        type=Path,
        metavar="DIRETORIO",
        help="raiz do projeto (padrão: repositório deste script)",
    )
    stage = "arguments"
    refresh_requested = False
    try:
        args = parser.parse_args(argv)
        refresh_requested = args.refresh
        root = (args.root if args.root is not None else Path(project_root)).resolve()
        if args.refresh:
            stage = "settings"
            settings = settings_loader(root)
            stage = "process_refresh"
            asyncio.run(
                collect_process_with_settings(
                    root,
                    settings,
                    refresh=True,
                    http_client_factory=http_client_factory,
                    now=now,
                )
            )
        stage = "local_export"
        if refresh_requested:
            result = export_process_for_llm(root, refresh=True)
        else:
            result = export_process_for_llm(root)
    except Exception as error:
        print(f"LLM_EXPORT_FAILED: {_safe_message(error)}", file=sys.stderr)
        if refresh_requested:
            print(_diagnostic_line(stage, error), file=sys.stderr)
        return 1

    _print_result(result)
    return 0


def _print_result(result: ProcessExportResult) -> None:
    if result.baseline_unavailable:
        print(
            "LLM_EXPORT_WARNING: baseline anterior inválido; "
            "refresh concluído sem comparação",
            file=sys.stderr,
        )
    print("LLM_EXPORT_OK")
    print(result.bundle_path)
    print(result.delta_markdown_path)
    print(result.delta_json_path)
    print(result.work_item_types_root)


def _safe_message(error: Exception) -> str:
    if isinstance(error, ProcessExportError):
        text = str(error)
        if text == "argumentos inválidos; execute com --help":
            return text
        if "CURRENT is missing" in text:
            return "out/process/CURRENT está ausente"
        if "export CURRENT is invalid" in text:
            return (
                "out/process-llm/CURRENT está inválido; "
                "consulte o troubleshooting"
            )
        if "previous export baseline is invalid" in text:
            return "o baseline da exportação anterior está ausente ou inválido"
        if "historical export changed during locked validation" in text:
            return (
                "uma geração histórica mudou durante a validação; "
                "repita o comando"
            )
        if "concurrent export" in text:
            return "outra execução publicou uma fonte diferente; tente novamente"
        if "write failure" in text:
            return "não foi possível publicar a exportação local com segurança"
        return "o snapshot do processo está ausente, incompleto ou inválido"
    return "a exportação falhou com segurança; consulte o troubleshooting"


def _diagnostic_line(stage: str, error: Exception) -> str:
    fields = [
        "LLM_EXPORT_DIAGNOSTIC:",
        f"stage={stage}",
        f"exception_type={type(error).__name__}",
    ]
    detail = _safe_diagnostic_detail(error)
    if detail:
        single_line_detail = detail.replace("\r", "\\r").replace("\n", "\\n")
        fields.append(f"detail={single_line_detail}")
    return " ".join(fields)


def _safe_diagnostic_detail(error: Exception) -> str:
    if isinstance(
        error,
        (AzureReadError, ProcessArtifactError, SettingsError, SnapshotError),
    ):
        return str(error)
    if isinstance(error, ProcessExportError):
        return _safe_message(error)
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
