"""Parse and render the canonical semantics of one delta report."""

from __future__ import annotations

import hashlib
import html
import json
import re
import xml.etree.ElementTree as element_tree
from dataclasses import asdict, dataclass


_STATUS_BULLET = re.compile(r"^- `([^`]+)`: (.+)$")
_PROVENANCE_BULLET = re.compile(r"^- (.+)$")
_EXPECTED_FINDING_HEADERS = (
    "ID",
    "Achado",
    "Status",
    "Documentado",
    "Implementado",
    "Evidência documental",
    "Evidência Azure",
    "Impacto ou limite",
)
_EXPECTED_SUMMARY_HEADERS = ("Status", "Quantidade")


class ReportSemanticError(ValueError):
    """Raised when a report cannot be represented without losing meaning."""


@dataclass(frozen=True)
class FindingSemantic:
    """Canonical values of one ordered audit finding."""

    claim_id: str
    finding: str
    status: str
    documented: str
    implemented: str
    evidence_documental: str
    evidence_azure: str
    impact_or_limit: str


@dataclass(frozen=True)
class ReportSemantic:
    """Canonical publication meaning shared by Markdown and Notion bodies."""

    title: str
    marker: str
    methodology: str
    status_definitions: tuple[tuple[str, str], ...]
    provenance: tuple[str, ...]
    summary: tuple[tuple[str, int], ...]
    findings: tuple[FindingSemantic, ...]

    @property
    def sha256(self) -> str:
        """Return a stable hash of the complete semantic representation."""

        payload = json.dumps(
            asdict(self),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def parse_report_semantics(body: str, slug: str) -> ReportSemantic:
    """Parse a versioned GFM report into its canonical semantic model."""

    sections = _split_sections(body, slug)
    summary_rows = _parse_markdown_table(sections["Resumo por status"])
    finding_rows = _parse_markdown_table(sections["Achados detalhados"])
    return _assemble_semantics(
        sections,
        slug,
        summary_rows,
        finding_rows,
    )


def parse_notion_semantics(body: str, slug: str) -> ReportSemantic:
    """Parse an enhanced-Markdown Notion body into canonical semantics."""

    sections = _split_sections(body, slug)
    summary_rows = _parse_xml_table(sections["Resumo por status"])
    finding_rows = _parse_xml_table(sections["Achados detalhados"])
    return _assemble_semantics(
        sections,
        slug,
        summary_rows,
        finding_rows,
    )


def render_notion_body(semantic: ReportSemantic) -> str:
    """Render one canonical report with Notion enhanced-Markdown tables."""

    lines = [
        f"# {semantic.title}",
        "",
        semantic.marker,
        "",
        "## Metodologia e status",
        "",
        semantic.methodology,
        "",
        *(f"- `{status}`: {definition}" for status, definition in semantic.status_definitions),
        "",
        "## Proveniência dos snapshots",
        "",
        *(f"- {item}" for item in semantic.provenance),
        "",
        "## Resumo por status",
        "",
        _render_xml_table(
            _EXPECTED_SUMMARY_HEADERS,
            tuple((status, str(quantity)) for status, quantity in semantic.summary),
        ),
        "",
        "## Achados detalhados",
        "",
        _render_xml_table(
            _EXPECTED_FINDING_HEADERS,
            tuple(
                (
                    finding.claim_id,
                    finding.finding,
                    finding.status,
                    finding.documented,
                    finding.implemented,
                    finding.evidence_documental,
                    finding.evidence_azure,
                    finding.impact_or_limit,
                )
                for finding in semantic.findings
            ),
        ),
    ]
    return "\n".join(lines) + "\n"


def _split_sections(body: str, slug: str) -> dict[str, str]:
    if not isinstance(body, str):
        raise ReportSemanticError(f"{slug}: report body must be text")
    normalized = body.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ReportSemanticError(f"{slug}: report title is missing")
    headings: list[tuple[int, str]] = [
        (index, line[3:])
        for index, line in enumerate(lines)
        if line.startswith("## ")
    ]
    expected = (
        "Metodologia e status",
        "Proveniência dos snapshots",
        "Resumo por status",
        "Achados detalhados",
    )
    if tuple(name for _, name in headings) != expected:
        raise ReportSemanticError(f"{slug}: report sections are invalid")
    first_heading = headings[0][0]
    preamble = [line.strip() for line in lines[1:first_heading] if line.strip()]
    marker = f"DELTA-AUDIT-MARKER-{slug}"
    if preamble != [marker]:
        raise ReportSemanticError(f"{slug}: publication marker is missing or invalid")
    sections: dict[str, str] = {
        "title": lines[0][2:].strip(),
        "marker": marker,
    }
    for offset, (start, name) in enumerate(headings):
        end = headings[offset + 1][0] if offset + 1 < len(headings) else len(lines)
        sections[name] = "\n".join(lines[start + 1 : end]).strip()
    return sections


def _assemble_semantics(
    sections: dict[str, str],
    slug: str,
    summary_rows: tuple[tuple[str, ...], ...],
    finding_rows: tuple[tuple[str, ...], ...],
) -> ReportSemantic:
    methodology_lines = sections["Metodologia e status"].splitlines()
    status_start = next(
        (index for index, line in enumerate(methodology_lines) if line.startswith("- `")),
        None,
    )
    if status_start is None:
        raise ReportSemanticError(f"{slug}: status definitions are missing")
    methodology = "\n".join(methodology_lines[:status_start]).strip()
    definitions: list[tuple[str, str]] = []
    for line in methodology_lines[status_start:]:
        if not line.strip():
            continue
        match = _STATUS_BULLET.fullmatch(line.strip())
        if match is None:
            raise ReportSemanticError(f"{slug}: status definition is invalid")
        definitions.append((match.group(1), match.group(2)))
    provenance: list[str] = []
    for line in sections["Proveniência dos snapshots"].splitlines():
        if not line.strip():
            continue
        match = _PROVENANCE_BULLET.fullmatch(line.strip())
        if match is None:
            raise ReportSemanticError(f"{slug}: provenance is invalid")
        provenance.append(match.group(1))
    if not methodology or not definitions or not provenance:
        raise ReportSemanticError(f"{slug}: report metadata is incomplete")
    if not summary_rows or summary_rows[0] != _EXPECTED_SUMMARY_HEADERS:
        raise ReportSemanticError(f"{slug}: summary table headers are invalid")
    summary: list[tuple[str, int]] = []
    for row in summary_rows[1:]:
        if len(row) != 2:
            raise ReportSemanticError(f"{slug}: summary row is invalid")
        try:
            quantity = int(row[1])
        except ValueError:
            raise ReportSemanticError(f"{slug}: summary quantity is invalid") from None
        if quantity < 0:
            raise ReportSemanticError(f"{slug}: summary quantity is invalid")
        summary.append((row[0], quantity))
    if not finding_rows or finding_rows[0] != _EXPECTED_FINDING_HEADERS:
        raise ReportSemanticError(f"{slug}: finding table headers are invalid")
    findings: list[FindingSemantic] = []
    for row in finding_rows[1:]:
        if len(row) != len(_EXPECTED_FINDING_HEADERS):
            raise ReportSemanticError(f"{slug}: finding row is invalid")
        findings.append(FindingSemantic(*row))
    if not findings:
        raise ReportSemanticError(f"{slug}: at least one finding is required")
    counts = {status: 0 for status, _ in summary}
    for finding in findings:
        if finding.status not in counts:
            raise ReportSemanticError(f"{slug}: finding status is absent from summary")
        counts[finding.status] += 1
    if tuple(counts.items()) != tuple(summary):
        raise ReportSemanticError(f"{slug}: summary does not match finding rows")
    return ReportSemantic(
        title=sections["title"],
        marker=sections["marker"],
        methodology=methodology,
        status_definitions=tuple(definitions),
        provenance=tuple(provenance),
        summary=tuple(summary),
        findings=tuple(findings),
    )


def _parse_markdown_table(section: str) -> tuple[tuple[str, ...], ...]:
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    if len(lines) < 3:
        raise ReportSemanticError("Markdown table is incomplete")
    rows = tuple(_split_markdown_row(line) for line in lines)
    separator = rows[1]
    if any(re.fullmatch(r":?-{3,}:?", cell) is None for cell in separator):
        raise ReportSemanticError("Markdown table separator is invalid")
    return (rows[0], *rows[2:])


def _split_markdown_row(line: str) -> tuple[str, ...]:
    if not line.startswith("|") or not line.endswith("|"):
        raise ReportSemanticError("Markdown table row is invalid")
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for character in line[1:-1]:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == "|":
            cells.append(_normalize_cell("".join(current)))
            current = []
        else:
            current.append(character)
    if escaped:
        current.append("\\")
    cells.append(_normalize_cell("".join(current)))
    return tuple(cells)


def _normalize_cell(value: str) -> str:
    return html.unescape(value.strip().replace("<br>", "\n").replace("<br/>", "\n"))


def _parse_xml_table(section: str) -> tuple[tuple[str, ...], ...]:
    try:
        table = element_tree.fromstring(section)
    except element_tree.ParseError:
        raise ReportSemanticError("Notion table XML is invalid") from None
    if table.tag != "table" or table.attrib != {
        "fit-page-width": "true",
        "header-row": "true",
    }:
        raise ReportSemanticError("Notion table attributes are invalid")
    rows: list[tuple[str, ...]] = []
    for row in table:
        if row.tag != "tr" or row.attrib:
            raise ReportSemanticError("Notion table row is invalid")
        cells: list[str] = []
        for cell in row:
            if cell.tag != "td" or cell.attrib:
                raise ReportSemanticError("Notion table cell is invalid")
            cells.append(_xml_cell_text(cell))
        rows.append(tuple(cells))
    return tuple(rows)


def _xml_cell_text(cell: element_tree.Element) -> str:
    parts = [cell.text or ""]
    for child in cell:
        if child.tag != "br" or child.attrib or list(child):
            raise ReportSemanticError("Notion table cell markup is invalid")
        parts.append("\n")
        parts.append(child.tail or "")
    return "".join(parts).strip()


def _render_xml_table(
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
) -> str:
    rendered = ['<table fit-page-width="true" header-row="true">']
    for row in (headers, *rows):
        rendered.append("\t<tr>")
        rendered.extend(f"\t\t<td>{_escape_xml_cell(cell)}</td>" for cell in row)
        rendered.append("\t</tr>")
    rendered.append("</table>")
    return "\n".join(rendered)


def _escape_xml_cell(value: str) -> str:
    return html.escape(value, quote=False).replace("\n", "<br />")
