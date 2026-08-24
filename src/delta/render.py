"""Deterministic Markdown rendering for one page-scoped delta audit."""

from __future__ import annotations

from delta.models import (
    AuditResult,
    EvidencePointer,
    Finding,
    FindingStatus,
    ReportProvenance,
)


_PAGE_TITLES = {
    "leiame": "Leia-me Processo da Organização Única",
    "politicas": "Template de políticas explícitas",
    "changelog": "Changelog",
    "apendice": "Apêndice Técnico Processo Organização Única",
}
_DOC_PATH_TO_SLUG = {
    f"out/wiki/{slug}.md": slug for slug in _PAGE_TITLES
}
_STATUS_ORDER = (
    FindingStatus.CONFIRMADO,
    FindingStatus.DIVERGENTE,
    FindingStatus.NAO_VERIFICAVEL_API_PROCESSO,
    FindingStatus.AMBIGUO,
)
_STATUS_EXPLANATIONS = (
    (FindingStatus.CONFIRMADO, "a documentação e a configuração atual concordam"),
    (
        FindingStatus.DIVERGENTE,
        "a documentação e a configuração atual são comparáveis, mas diferem",
    ),
    (
        FindingStatus.NAO_VERIFICAVEL_API_PROCESSO,
        "a API de processo não consegue comprovar a afirmação",
    ),
    (
        FindingStatus.AMBIGUO,
        "a evidência disponível admite mais de uma interpretação material",
    ),
)


def render_report(result: AuditResult, provenance: ReportProvenance) -> str:
    """Render one non-empty, single-wiki audit result as stable PT-BR Markdown."""

    if not isinstance(result, AuditResult):
        raise ValueError("result must be an AuditResult")
    if not isinstance(provenance, ReportProvenance):
        raise ValueError("provenance must be ReportProvenance")
    if not result.findings:
        raise ValueError("report requires at least one finding")

    slug = _single_page_slug(result.findings)
    lines = [
        f"# Delta — {_PAGE_TITLES[slug]} × Processo-Agil implementado",
        "",
        f"DELTA-AUDIT-MARKER-{slug}",
        "",
        "## Metodologia e status",
        "",
        (
            "Este relatório compara afirmações documentais explícitas com a "
            "configuração atual coletada do Processo-Agil. Cada achado preserva "
            "os apontadores exatos das evidências usadas na comparação."
        ),
        "",
    ]
    lines.extend(
        f"- `{status.value}`: {explanation}."
        for status, explanation in _STATUS_EXPLANATIONS
    )
    lines.extend(("", "## Proveniência dos snapshots", ""))
    lines.extend(_render_provenance(provenance))
    lines.extend(("", "## Resumo por status", ""))
    lines.extend(_render_summary(result.findings))
    lines.extend(("", "## Achados detalhados", ""))
    lines.extend(_render_findings(result.findings))
    return "\n".join(lines) + "\n"


def _render_provenance(provenance: ReportProvenance) -> tuple[str, ...]:
    return (
        (
            "- Wiki: coletada em "
            f"`{provenance.wiki_collected_at}`; geração "
            f"`{provenance.wiki_generation_id}`; SHA-256 do manifesto "
            f"`{provenance.wiki_manifest_sha256}`."
        ),
        (
            "- Processo: coletado em "
            f"`{provenance.process_collected_at}`; geração "
            f"`{provenance.process_generation_id}`; SHA-256 do manifesto "
            f"`{provenance.process_manifest_sha256}`."
        ),
        (
            f"- Processo avaliado: `{provenance.process_name}` "
            f"(ID `{provenance.process_id}`)."
        ),
        (
            "- Os caminhos lógicos `out/wiki/...` e `out/process/...` "
            "resolvem pelas gerações imutáveis identificadas acima."
        ),
    )


def _single_page_slug(findings: tuple[Finding, ...]) -> str:
    slugs: set[str] = set()
    for finding in findings:
        evidence_pointers = finding.doc_evidence
        if not isinstance(evidence_pointers, tuple):
            raise ValueError("every finding requires documentary evidence")
        for evidence in evidence_pointers:
            try:
                slugs.add(_DOC_PATH_TO_SLUG[evidence.path])
            except KeyError:
                raise ValueError(
                    "documentary evidence is not an approved wiki page: "
                    f"{evidence.path!r}"
                ) from None
    if len(slugs) != 1:
        raise ValueError("report findings must belong to exactly one wiki page")
    return next(iter(slugs))


def _render_summary(findings: tuple[Finding, ...]) -> tuple[str, ...]:
    counts = {status: 0 for status in _STATUS_ORDER}
    for finding in findings:
        counts[finding.status] += 1
    return (
        "| Status | Quantidade |",
        "| --- | ---: |",
        *(f"| {status.value} | {counts[status]} |" for status in _STATUS_ORDER),
    )


def _render_findings(findings: tuple[Finding, ...]) -> tuple[str, ...]:
    rows = [
        (
            "| ID | Achado | Status | Documentado | Implementado | "
            "Evidência documental | Evidência Azure | Impacto ou limite |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    rows.extend(_render_finding(finding) for finding in findings)
    return tuple(rows)


def _render_finding(finding: Finding) -> str:
    cells = (
        finding.id,
        finding.finding,
        finding.status.value,
        finding.documented,
        finding.implemented,
        _render_pointers(finding.doc_evidence),
        _render_pointers(finding.azure_evidence),
        finding.impact_or_limit,
    )
    return "| " + " | ".join(_escape_table_cell(cell) for cell in cells) + " |"


def _render_pointer(pointer: EvidencePointer | None) -> str:
    if pointer is None:
        return "n/a"
    return f"{pointer.path}#{pointer.selector}"


def _render_pointers(
    pointers: tuple[EvidencePointer, ...] | None,
) -> str:
    if pointers is None:
        return "n/a"
    return "\n".join(_render_pointer(pointer) for pointer in pointers)




def _escape_table_cell(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "<br>")
    )
