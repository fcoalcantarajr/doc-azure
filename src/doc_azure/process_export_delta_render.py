"""Render one immutable process delta for people, LLMs, and automation."""

from __future__ import annotations

import json
import re
from html import escape
import unicodedata

from doc_azure.process_export_delta import (
    ChangeKind,
    EvidenceLocation,
    ProcessDelta,
)


def render_delta_json(delta: ProcessDelta) -> str:
    """Render the closed machine-readable delta document."""

    return json.dumps(
        delta.as_dict(),
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def render_delta_markdown(delta: ProcessDelta) -> str:
    """Render a standalone Portuguese delta for people and LLMs."""

    summary = delta.as_dict()["summary"]
    assert isinstance(summary, dict)
    lines = [
        "# Delta do snapshot do Processo-Agil",
        "",
        "> **Limite:** este delta compara configurações observadas na API. Não prova "
        "intenção institucional, governança, uso real nem correção.",
        "",
        f"- Status: `{delta.status}`",
        f"- Geração atual: `{delta.current.source_generation}`",
        f"- SHA-256 atual: `{delta.current.source_manifest_sha256}`",
    ]
    if delta.baseline is None:
        lines.extend(
            (
                "- Baseline: `(ausente)`",
                "",
                "Nenhum baseline comparável estava disponível para este delta.",
            )
        )
        return "\n".join(lines).rstrip() + "\n"

    lines.extend(
        (
            f"- Geração anterior: `{delta.baseline.source_generation}`",
            f"- SHA-256 anterior: `{delta.baseline.source_manifest_sha256}`",
            "",
            "## Resumo",
            "",
            f"- Adições: `{summary['added']}`",
            f"- Remoções: `{summary['removed']}`",
            f"- Alterações: `{summary['changed']}`",
            f"- Total: `{summary['total']}`",
        )
    )
    if not delta.changes:
        lines.extend(("", "Nenhuma alteração semântica foi observada."))
        return "\n".join(lines).rstrip() + "\n"

    for index, change in enumerate(delta.changes, start=1):
        lines.extend(
            (
                "",
                f"## {index}. {_kind_label(change.kind)} — {_scope_label(change.scope)}",
                "",
                f"- Caminho relativo: {_code(change.path)}",
                _evidence_line("Evidência anterior", change.before_evidence),
                _evidence_line("Evidência atual", change.after_evidence),
                "",
                "### Valor anterior",
                "",
                _json_block(change.as_dict()["before"]),
                "",
                "### Valor atual",
                "",
                _json_block(change.as_dict()["after"]),
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def render_delta_bundle_section(delta: ProcessDelta) -> str:
    """Render the compact delta index embedded in the complete bundle."""

    summary = delta.as_dict()["summary"]
    assert isinstance(summary, dict)
    lines = [
        "## Delta desde a exportação anterior",
        "",
        f"- Status: `{delta.status}`",
        "- Conteúdo completo: `delta.md`",
        "- Dados estruturados: `delta.json`",
        f"- Total de mudanças: `{summary['total']}`",
    ]
    if delta.baseline is None:
        lines.append("- Geração anterior: `(ausente)`")
    else:
        lines.append(f"- Geração anterior: `{delta.baseline.source_generation}`")
    return "\n".join(lines).rstrip() + "\n"


def _kind_label(kind: ChangeKind) -> str:
    return {
        "added": "Adicionado",
        "removed": "Removido",
        "changed": "Alterado",
    }[kind]


def _scope_label(scope: tuple[tuple[str, str], ...]) -> str:
    values = dict(scope)
    if values["kind"] == "process":
        return "processo"
    if values["kind"] == "global_behaviors":
        return "behaviors globais"
    reference_name = json.dumps(values["reference_name"], ensure_ascii=False)[1:-1]
    return f"{_code(escape(reference_name))} / {values['family']}"


def _evidence_line(label: str, evidence: EvidenceLocation | None) -> str:
    if evidence is None:
        return f"- {label}: `(ausente)`"
    return (
        f"- {label}: {_code(evidence.artifact_path)} · "
        f"JSON Pointer {_code(evidence.json_pointer)} · geração "
        f"{_code(evidence.source_generation)}"
    )


def _json_block(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)
    longest = max(
        (len(match.group()) for match in re.finditer(r"`+", payload)),
        default=0,
    )
    fence = "`" * max(3, longest + 1)
    return f"{fence}json\n{payload}\n{fence}"


def _code(value: str) -> str:
    value = "".join(
        f"\\u{ord(character):04x}"
        if unicodedata.category(character) == "Cc"
        else character
        for character in value
    )
    longest = max(
        (len(match.group()) for match in re.finditer(r"`+", value)),
        default=0,
    )
    fence = "`" * max(1, longest + 1)
    padding = (
        " "
        if value.startswith(("`", " ")) or value.endswith(("`", " "))
        else ""
    )
    return f"{fence}{padding}{value}{padding}{fence}"
