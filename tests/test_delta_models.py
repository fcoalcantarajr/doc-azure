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


@pytest.mark.parametrize("status", [FindingStatus.CONFIRMADO, FindingStatus.DIVERGENTE])
def test_confirmed_and_divergent_findings_require_azure_evidence(status):
    with pytest.raises(ValueError, match="azure_evidence"):
        make_finding(status=status, azure_evidence=None)


def test_unverifiable_finding_allows_missing_azure_evidence():
    finding = make_finding(
        status=FindingStatus.NAO_VERIFICAVEL_API_PROCESSO,
        azure_evidence=None,
    )
    assert finding.azure_evidence is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", None),
        ("finding", 1),
        ("documented", " "),
        ("implemented", None),
        ("impact_or_limit", 1),
    ],
)
def test_finding_rejects_invalid_string_fields_without_attribute_errors(field, value):
    with pytest.raises(ValueError, match=field):
        make_finding(**{field: value})


def test_documented_and_implemented_accept_explicit_not_applicable_value():
    finding = make_finding(documented="n/a", implemented="n/a")
    assert (finding.documented, finding.implemented) == ("n/a", "n/a")


def test_finding_rejects_runtime_invalid_status_and_evidence_pointer_values():
    with pytest.raises(ValueError, match="status"):
        make_finding(status="DIVERGENTE")
    with pytest.raises(ValueError, match="doc_evidence"):
        make_finding(doc_evidence="out/wiki/leiame.md#L10")
    with pytest.raises(ValueError, match="azure_evidence"):
        make_finding(azure_evidence="out/process/Bug_states.json#/count")


def test_evidence_pointer_rejects_non_string_or_blank_members():
    with pytest.raises(ValueError, match="path"):
        EvidencePointer(path=None, selector="L10")
    with pytest.raises(ValueError, match="selector"):
        EvidencePointer(path="out/wiki/leiame.md", selector=" ")


def test_evidence_pointer_is_immutable():
    pointer = EvidencePointer("out/wiki/leiame.md", "L10")
    with pytest.raises(AttributeError):
        pointer.path = "changed"  # type: ignore[misc]


def test_audit_result_rejects_duplicate_finding_ids():
    finding = make_finding()
    with pytest.raises(ValueError, match="duplicate"):
        AuditResult(findings=(finding, finding))


def test_audit_result_normalizes_findings_to_an_immutable_tuple():
    result = AuditResult(findings=[make_finding()])
    assert result.findings == (make_finding(),)
    assert isinstance(result.findings, tuple)
    with pytest.raises(AttributeError):
        result.findings = ()  # type: ignore[misc]


def test_finding_is_immutable():
    finding = make_finding()
    with pytest.raises(AttributeError):
        finding.id = "changed"  # type: ignore[misc]
