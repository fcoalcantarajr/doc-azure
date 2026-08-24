"""Tests for deterministic, page-scoped delta report rendering."""

from __future__ import annotations

import pytest

from delta.models import (
    AuditResult,
    EvidencePointer,
    Finding,
    FindingStatus,
    ReportProvenance,
)
from delta.render import render_report


TITLES = {
    "leiame": "Leia-me Processo da Organização Única",
    "politicas": "Template de políticas explícitas",
    "changelog": "Changelog",
    "apendice": "Apêndice Técnico Processo Organização Única",
}
PROVENANCE = ReportProvenance(
    wiki_collected_at="2026-08-24T18:25:50+00:00",
    wiki_generation_id="1" * 32,
    wiki_manifest_sha256="2" * 64,
    process_collected_at="2026-08-24T18:35:59+00:00",
    process_generation_id="3" * 32,
    process_manifest_sha256="4" * 64,
    process_name="Processo-Agil",
    process_id="9d82e632-9028-4a6b-86f8-3edb3281cb15",
)


def make_finding(
    *,
    slug: str = "leiame",
    finding_id: str = "35-PROCESS-001",
    finding: str = "Identidade do processo",
    status: FindingStatus = FindingStatus.CONFIRMADO,
    documented: str = "Processo-Agil",
    implemented: str = "Processo-Agil",
    doc_selector: str = "L144",
    azure_path: str | None = "out/process/process.json",
    azure_selector: str = "/name",
    impact_or_limit: str = "",
) -> Finding:
    return Finding(
        id=finding_id,
        finding=finding,
        status=status,
        documented=documented,
        implemented=implemented,
        doc_evidence=EvidencePointer(f"out/wiki/{slug}.md", doc_selector),
        azure_evidence=(
            None
            if azure_path is None
            else EvidencePointer(azure_path, azure_selector)
        ),
        impact_or_limit=impact_or_limit,
    )


@pytest.mark.parametrize(("slug", "title"), TITLES.items())
def test_report_uses_the_page_title_and_publication_marker(
    slug: str, title: str
) -> None:
    report = render_report(AuditResult((make_finding(slug=slug),)), PROVENANCE)

    assert report.startswith(
        f"# Delta — {title} × Processo-Agil implementado\n"
    )
    assert f"DELTA-AUDIT-MARKER-{slug}" in report
    assert "## Metodologia e status" in report
    assert "## Resumo por status" in report
    assert "## Achados detalhados" in report
    assert "## Proveniência dos snapshots" in report
    assert "`11111111111111111111111111111111`" in report
    assert "`33333333333333333333333333333333`" in report
    assert "`Processo-Agil`" in report
    assert "`9d82e632-9028-4a6b-86f8-3edb3281cb15`" in report
    assert "caminhos lógicos" in report


def test_report_uses_exact_portuguese_statuses_and_stable_summary_counts() -> None:
    findings = (
        make_finding(),
        make_finding(
            finding_id="35-STATE-002",
            finding="Quantidade de estados",
            status=FindingStatus.DIVERGENTE,
            documented="8",
            implemented="9",
            azure_path="out/process/workitemtypes/Custom.Bug/states.json",
            azure_selector="/count",
            impact_or_limit="A documentação não representa o fluxo atual.",
        ),
        make_finding(
            finding_id="35-HISTORY-003",
            finding="Data da implantação",
            status=FindingStatus.NAO_VERIFICAVEL_API_PROCESSO,
            documented="2026-04-27",
            implemented="A API expõe somente a configuração atual.",
            azure_path=None,
            impact_or_limit="A API de processo não preserva a cronologia.",
        ),
        make_finding(
            finding_id="35-LAYOUT-004",
            finding="Ordem relativa dos controles",
            status=FindingStatus.AMBIGUO,
            documented="A antes de B",
            implemented="A e B estão em grupos distintos.",
            azure_path="out/process/workitemtypes/Custom.Bug/layout.json",
            azure_selector="/pages/0",
            impact_or_limit="Grupos distintos não estabelecem uma ordem única.",
        ),
    )

    report = render_report(AuditResult(findings), PROVENANCE)

    summary = "\n".join(
        (
            "| Status | Quantidade |",
            "| --- | ---: |",
            "| CONFIRMADO | 1 |",
            "| DIVERGENTE | 1 |",
            "| NAO_VERIFICAVEL_API_PROCESSO | 1 |",
            "| AMBIGUO | 1 |",
        )
    )
    assert summary in report
    assert "DOC_ONLY" not in report
    assert "AZURE_ONLY" not in report
    assert "| 35-PROCESS-001 | Identidade do processo | CONFIRMADO |" in report
    assert (
        "| 35-HISTORY-003 | Data da implantação | "
        "NAO_VERIFICAVEL_API_PROCESSO |" in report
    )


def test_report_preserves_catalog_order_and_exact_evidence_pointers() -> None:
    result = AuditResult(
        (
            make_finding(
                finding_id="35-SECOND-002",
                doc_selector="L20",
                azure_selector="/value/1/referenceName",
            ),
            make_finding(
                finding_id="35-FIRST-001",
                doc_selector="L10",
                azure_selector="/value/0/referenceName",
            ),
        )
    )

    first_render = render_report(result, PROVENANCE)
    second_render = render_report(result, PROVENANCE)

    assert first_render == second_render
    assert first_render.index("35-SECOND-002") < first_render.index("35-FIRST-001")
    assert "out/wiki/leiame.md#L20" in first_render
    assert "out/process/process.json#/value/1/referenceName" in first_render
    assert first_render.endswith("\n")


def test_report_renders_every_exact_documentary_fragment() -> None:
    finding = make_finding()
    finding = Finding(
        id=finding.id,
        finding=finding.finding,
        status=finding.status,
        documented=finding.documented,
        implemented=finding.implemented,
        doc_evidence=(
            EvidencePointer("out/wiki/leiame.md", "L93"),
            EvidencePointer("out/wiki/leiame.md", "L100"),
        ),
        azure_evidence=finding.azure_evidence,
        impact_or_limit=finding.impact_or_limit,
    )

    report = render_report(AuditResult((finding,)), PROVENANCE)

    assert "out/wiki/leiame.md#L93<br>out/wiki/leiame.md#L100" in report


def test_report_renders_every_exact_azure_pointer() -> None:
    finding = make_finding()
    finding = Finding(
        id=finding.id,
        finding=finding.finding,
        status=finding.status,
        documented=finding.documented,
        implemented=finding.implemented,
        doc_evidence=finding.doc_evidence,
        azure_evidence=(
            EvidencePointer("out/process/a.json", "/value"),
            EvidencePointer("out/process/b.json", "/value"),
        ),
        impact_or_limit=finding.impact_or_limit,
    )

    report = render_report(AuditResult((finding,)), PROVENANCE)

    assert "out/process/a.json#/value<br>out/process/b.json#/value" in report


def test_report_escapes_markdown_table_cells_without_losing_line_breaks() -> None:
    finding = make_finding(
        finding_id=r"35-PIPE|BACK\SLASH",
        finding="Achado | principal\nsegunda linha",
        documented=r"valor | documentado\literal",
        implemented="valor atual\r\ncom detalhe",
        doc_selector="L1|L2",
        azure_selector="/a|b",
    )

    report = render_report(AuditResult((finding,)), PROVENANCE)

    assert r"35-PIPE\|BACK\\SLASH" in report
    assert "Achado \\| principal<br>segunda linha" in report
    assert r"valor \| documentado\\literal" in report
    assert "valor atual<br>com detalhe" in report
    assert "out/wiki/leiame.md#L1\\|L2" in report
    assert "out/process/process.json#/a\\|b" in report


def test_report_rejects_empty_or_mixed_page_results() -> None:
    with pytest.raises(ValueError, match="at least one finding"):
        render_report(AuditResult(()), PROVENANCE)

    mixed = AuditResult(
        (
            make_finding(slug="leiame"),
            make_finding(slug="changelog", finding_id="9-PROCESS-001"),
        )
    )
    with pytest.raises(ValueError, match="exactly one wiki page"):
        render_report(mixed, PROVENANCE)


def test_report_rejects_an_unknown_documentary_evidence_path() -> None:
    result = AuditResult((make_finding(slug="desconhecido"),))

    with pytest.raises(ValueError, match="approved wiki page"):
        render_report(result, PROVENANCE)
