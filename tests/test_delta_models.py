"""Tests for immutable, evidence-backed delta findings."""

import pytest

from delta.models import AuditResult, EvidencePointer, Finding, FindingStatus


def make_finding(**overrides: object) -> Finding:
    values: dict[str, object] = {
        "id": "35-STATE-001",
        "finding": "Quantidade de estados de Bug",
        "status": FindingStatus.DIVERGENTE,
        "documented": "8",
        "implemented": "9",
        "doc_evidence": EvidencePointer("out/wiki/leiame.md", "L10"),
        "azure_evidence": EvidencePointer("out/process/Bug_states.json", "/count"),
        "impact_or_limit": "The documented workflow differs from the current process.",
    }
    values.update(overrides)
    return Finding(**values)  # type: ignore[arg-type]


def test_finding_status_literals_are_exact():
    assert {status.value for status in FindingStatus} == {
        "CONFIRMADO",
        "DIVERGENTE",
        "NAO_VERIFICAVEL_API_PROCESSO",
        "AMBIGUO",
    }


def test_non_confirmed_finding_requires_impact_or_limit():
    with pytest.raises(ValueError, match="impact_or_limit"):
        make_finding(impact_or_limit="")


def test_finding_requires_a_non_blank_id_and_documentary_evidence():
    with pytest.raises(ValueError, match="id"):
        make_finding(id="  ")
    with pytest.raises(ValueError, match="doc_evidence"):
        make_finding(doc_evidence=None)


def test_confirmed_and_divergent_findings_require_azure_evidence():
    with pytest.raises(ValueError, match="azure_evidence"):
        make_finding(azure_evidence=None)


def test_audit_result_rejects_duplicate_finding_ids():
    finding = make_finding()
    with pytest.raises(ValueError, match="duplicate"):
        AuditResult(findings=(finding, finding))


def test_finding_is_immutable():
    finding = make_finding()
    with pytest.raises(AttributeError):
        finding.id = "changed"  # type: ignore[misc]
