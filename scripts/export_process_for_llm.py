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
from doc_azure.process_runtime import (  # noqa: E402
    Clock,
    HttpClientFactory,
    collect_process_with_settings,
    make_http_client,
    utc_now,
)
from doc_azure.settings import Settings  # noqa: E402


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
    try:
        args = parser.parse_args(argv)
        root = (args.root if args.root is not None else Path(project_root)).resolve()
        if args.refresh:
            settings = settings_loader(root)
            asyncio.run(
                collect_process_with_settings(
                    root,
                    settings,
                    refresh=True,
                    http_client_factory=http_client_factory,
                    now=now,
                )
            )
        result = export_process_for_llm(root)
    except Exception as error:
        print(f"LLM_EXPORT_FAILED: {_safe_message(error)}", file=sys.stderr)
        return 1

    _print_result(result)
    return 0


def _print_result(result: ProcessExportResult) -> None:
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


if __name__ == "__main__":
    raise SystemExit(main())
