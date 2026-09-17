"""Render one immutable process export model into Portuguese Markdown."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True)
class JsonObject:
    """An immutable JSON object preserving property order."""

    properties: tuple[tuple[str, "JsonValue"], ...]
    synthetic_properties: frozenset[str] = frozenset()


@dataclass(frozen=True)
class JsonArray:
    """An immutable JSON array preserving item order."""

    items: tuple["JsonValue", ...]


JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | JsonObject | JsonArray


@dataclass(frozen=True)
class EvidenceFamily:
    """One reduced evidence family with its exact source location."""

    name: str
    source_path: str
    json_pointer: str
    value: JsonValue
    additional_properties: JsonObject | None = None
    additional_properties_json_pointer: str | None = None


@dataclass(frozen=True)
class WorkItemTypeModel:
    """One work item type and all five evidence families."""

    name: str
    reference_name: str
    customization: str
    is_disabled: bool
    metadata: JsonObject
    metadata_source_path: str
    metadata_json_pointer: str
    families: tuple[EvidenceFamily, ...]


@dataclass(frozen=True)
class ProcessExportModel:
    """The single semantic model used by every generated representation."""

    process: EvidenceFamily
    behaviors: EvidenceFamily
    work_item_types: tuple[WorkItemTypeModel, ...]
    source_generation: str
    source_manifest_sha256: str
    source_collected_at: str


MISSING = object()


def freeze_json(value: object) -> JsonValue:
    """Recursively remove exact ``url`` keys and freeze a JSON value."""

    if isinstance(value, dict):
        return JsonObject(
            tuple(
                (key, freeze_json(item))
                for key, item in value.items()
                if key != "url"
            )
        )
    if isinstance(value, list):
        return JsonArray(tuple(freeze_json(item) for item in value))
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("process export contains a non-finite JSON number")
    if value is None or type(value) in (bool, int, float, str):
        return value
    raise TypeError("process export contains a non-JSON value")


def to_builtin(value: JsonValue) -> object:
    """Convert the immutable JSON representation for deterministic encoding."""

    if isinstance(value, JsonObject):
        return {key: to_builtin(item) for key, item in value.properties}
    if isinstance(value, JsonArray):
        return [to_builtin(item) for item in value.items]
    return value


def render_process_summary(model: ProcessExportModel, *, level: int = 1) -> str:
    """Render process identity, global behaviors, provenance pointers and limits."""

    title = "#" * level
    child = "#" * (level + 1)
    lines = [
        f"{title} Resumo do processo",
        "",
        _limitations(),
        "",
        _source_line(model.process),
        "",
        f"{child} Identidade e configuração observada",
        "",
        _json_block(model.process.value),
        "",
        f"{child} Procedência",
        "",
        f"- Geração de origem: `{model.source_generation}`",
        f"- SHA-256 do manifesto de origem: `{model.source_manifest_sha256}`",
        f"- Coletado em: `{model.source_collected_at}`",
        "- Escopo: `process-only`",
        "- Propriedades omitidas: `url`",
        "",
        f"{child} Behaviors globais",
        "",
        _source_line(model.behaviors),
        "",
        _json_block(model.behaviors.value),
    ]
    if model.behaviors.additional_properties is not None:
        lines.extend(
            (
                "",
                "`additional_properties` fora do conjunto principal:",
                f"JSON Pointer: {_code(model.behaviors.additional_properties_json_pointer or '')}",
                "",
                _json_block(model.behaviors.additional_properties),
            )
        )
    lines.extend(
        (
            "",
            f"{child} Inventário de tipos de item",
            "",
            "| Nome | referenceName | Estado | Customização |",
            "| --- | --- | --- | --- |",
        )
    )
    for wit in model.work_item_types:
        lines.append(
            "| "
            + " | ".join(
                (
                    _table(wit.name),
                    _table(wit.reference_name),
                    "Desabilitado" if wit.is_disabled else "Ativo",
                    _table(wit.customization),
                )
            )
            + " |"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_work_item_type(wit: WorkItemTypeModel, *, level: int = 1) -> str:
    """Render one WIT from the same semantics used by the bundle."""

    title = "#" * level
    child = "#" * (level + 1)
    status = "Desabilitado" if wit.is_disabled else "Ativo"
    lines = [
        f"{title} {_heading(wit.name)}",
        "",
        _limitations(),
        "",
        f"- `referenceName`: {_code(wit.reference_name)}",
        f"- Estado: **{status}**",
        f"- Customização: {_code(wit.customization)}",
        f"- Artefato de metadados: {_code(wit.metadata_source_path)}",
        f"- JSON Pointer de metadados: {_code(wit.metadata_json_pointer)}",
        "",
        f"{child} Metadados",
        "",
        _json_block(wit.metadata),
    ]
    for family in wit.families:
        lines.extend(
            (
                "",
                f"{child} {_family_title(family.name)}",
                "",
                _source_line(family),
                "",
            )
        )
        lines.extend(_render_family(family))
    return "\n".join(lines).rstrip() + "\n"


def render_bundle(model: ProcessExportModel) -> str:
    """Render the complete process as one self-contained Markdown document."""

    sections = [
        "# Snapshot do Processo-Agil para LLM\n\n"
        "Este arquivo reúne o mesmo modelo semântico do resumo e dos arquivos "
        "individuais. Pode ser usado sem consultar os JSON brutos.\n",
        render_process_summary(model, level=2),
    ]
    sections.extend(
        render_work_item_type(wit, level=2) for wit in model.work_item_types
    )
    return "\n".join(section.rstrip() for section in sections) + "\n"


def render_export_readme() -> str:
    """Return the short guide shipped inside each immutable generation."""

    return """# Como usar esta exportação

Esta geração contém somente a configuração observada do processo `Processo-Agil`.
Ela não consulta nem reproduz a Wiki. Além do snapshot atual, `delta.md` e
`delta.json` comparam a fonte atual com a fonte da exportação anterior.
Se a exportação anterior não registrava delta, a migração informa
`SEM_BASELINE`, sem inventar uma comparação.

- Use `bundle.md` quando a ferramenta aceitar um único arquivo.
- Use `delta.md` para ler as mudanças e `delta.json` para processamento estruturado.
- Use `process-summary.md` com um ou mais arquivos de `work-item-types/` quando
  precisar reduzir o contexto.
- Consulte `provenance.json` para identificar a geração de origem.

Os documentos preservam nomes, labels, defaults, condições e ações. A
propriedade de transporte `url` foi removida recursivamente. Inspecione o pacote
antes de enviá-lo a uma LLM corporativa aprovada. A exportação descreve o que a
API retornou; não prova intenção institucional, governança, uso real ou correção.
"""


def _render_family(family: EvidenceFamily) -> list[str]:
    if family.name == "fields":
        return _render_table_and_exact(
            family,
            ("referenceName", "name", "type", "required", "defaultValue", "order"),
        )
    if family.name == "states":
        return _render_table_and_exact(
            family,
            ("id", "name", "stateCategory", "order", "hidden"),
        )
    if family.name == "behaviors":
        return _render_table_and_exact(
            family,
            ("behavior", "isDefault", "isLegacyDefault", "order"),
        )
    if family.name == "rules":
        lines = [
            "Condições e ações abaixo mantêm os valores JSON exatos e a ordem da API.",
            "",
            _json_block(family.value),
        ]
        return _with_family_additional(lines, family)
    if family.name == "layout":
        lines = [
            "Hierarquia completa de páginas, seções, grupos, controles e controles "
            "de sistema, na ordem observada:",
            "",
            *_layout_outline(family.value, family.json_pointer),
            "",
            "Representação JSON exata da hierarquia:",
            "",
            _json_block(family.value),
        ]
        return _with_family_additional(lines, family)
    return _with_family_additional([_json_block(family.value)], family)


def _render_table_and_exact(
    family: EvidenceFamily, columns: tuple[str, ...]
) -> list[str]:
    value = family.value
    items = value.items if isinstance(value, JsonArray) else ()
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for item in items:
        lines.append(
            "| "
            + " | ".join(_table(_property(item, column)) for column in columns)
            + " |"
        )
    lines.extend(("", "Valores completos e `additional_properties`:", "", _json_block(value)))
    return _with_family_additional(lines, family)


def _with_family_additional(
    lines: list[str], family: EvidenceFamily
) -> list[str]:
    if family.additional_properties is None:
        return lines
    return [
        *lines,
        "",
        "`additional_properties` fora do conjunto principal:",
        f"JSON Pointer: {_code(family.additional_properties_json_pointer or '')}",
        "",
        _json_block(family.additional_properties),
    ]


def _layout_outline(value: JsonValue, base_pointer: str) -> list[str]:
    lines: list[str] = []

    def visit(node: JsonValue, depth: int, pointer: str) -> None:
        if isinstance(node, JsonObject):
            label = _first_property(node, ("label", "name", "id", "referenceName"))
            if label is not MISSING:
                lines.append(f"{'  ' * depth}- {_code(pointer)} — {_table(label)}")
            for key, item in node.properties:
                if isinstance(item, (JsonObject, JsonArray)):
                    child_pointer = (
                        pointer
                        if key in node.synthetic_properties
                        else f"{pointer}/{_pointer_escape(key)}"
                    )
                    visit(item, depth + 1, child_pointer)
        elif isinstance(node, JsonArray):
            for index, item in enumerate(node.items):
                visit(item, depth, f"{pointer}/{index}")

    visit(value, 0, base_pointer)
    return lines or ["- (hierarquia vazia)"]


def _property(value: JsonValue, key: str) -> object:
    if not isinstance(value, JsonObject):
        return MISSING
    for candidate, item in value.properties:
        if candidate == key:
            return to_builtin(item)
    return MISSING


def _first_property(value: JsonObject, keys: tuple[str, ...]) -> object:
    for key in keys:
        item = _property(value, key)
        if item is not MISSING:
            return item
    return MISSING


def _source_line(family: EvidenceFamily) -> str:
    return (
        f"- Artefato de origem: {_code(family.source_path)}\n"
        f"- JSON Pointer: {_code(family.json_pointer)}"
    )


def _json_block(value: JsonValue) -> str:
    payload = json.dumps(
        to_builtin(value), ensure_ascii=False, allow_nan=False, indent=2
    )
    longest = max((len(match.group()) for match in re.finditer(r"`+", payload)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}json\n{payload}\n{fence}"


def _table(value: object) -> str:
    if value is MISSING:
        return "(ausente)"
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (
        encoded.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _code(value: str) -> str:
    longest = max((len(match.group()) for match in re.finditer(r"`+", value)), default=0)
    fence = "`" * max(1, longest + 1)
    padding = " " if value.startswith(("`", " ")) or value.endswith(("`", " ")) else ""
    return f"{fence}{padding}{value}{padding}{fence}"


def _heading(value: str) -> str:
    flattened = " ".join(value.splitlines())
    return re.sub(r"([\\`*_{}\[\]<>()#+.!|\-])", r"\\\1", flattened)


def _pointer_escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _family_title(name: str) -> str:
    return {
        "states": "Estados",
        "fields": "Campos",
        "rules": "Regras",
        "layout": "Layout",
        "behaviors": "Behaviors",
    }[name]


def _limitations() -> str:
    return (
        "> **Limite:** descrição da configuração observada na API Azure DevOps. "
        "Não prova intenção institucional, governança, uso real nem correção."
    )
