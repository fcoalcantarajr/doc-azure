"""Immutable domain objects for evidence-backed delta findings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


def _require_non_blank_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-blank string")


class FindingStatus(str, Enum):
    """Epistemic outcome of one documented-versus-implemented claim."""

    CONFIRMADO = "CONFIRMADO"
    DIVERGENTE = "DIVERGENTE"
    NAO_VERIFICAVEL_API_PROCESSO = "NAO_VERIFICAVEL_API_PROCESSO"
    AMBIGUO = "AMBIGUO"


@dataclass(frozen=True)
class EvidencePointer:
    """A path and an exact selector within one collected source artifact."""

    path: str
    selector: str

    def __post_init__(self) -> None:
        _require_non_blank_string(self.path, "EvidencePointer.path")
        _require_non_blank_string(self.selector, "EvidencePointer.selector")


@dataclass(frozen=True)
class Finding:
    """One immutable comparison supported by documentary and process evidence."""

    id: str
    finding: str
    status: FindingStatus
    documented: str
    implemented: str
    doc_evidence: EvidencePointer | None
    azure_evidence: EvidencePointer | None
    impact_or_limit: str

    def __post_init__(self) -> None:
        _require_non_blank_string(self.id, "Finding.id")
        _require_non_blank_string(self.finding, "Finding.finding")
        _require_non_blank_string(self.documented, "Finding.documented")
        _require_non_blank_string(self.implemented, "Finding.implemented")
        if not isinstance(self.impact_or_limit, str):
            raise ValueError("Finding.impact_or_limit must be a string")
        if not isinstance(self.status, FindingStatus):
            raise ValueError("Finding.status must be a FindingStatus")
        if not isinstance(self.doc_evidence, EvidencePointer):
            raise ValueError("Finding.doc_evidence is required")
        if self.azure_evidence is not None and not isinstance(self.azure_evidence, EvidencePointer):
            raise ValueError("Finding.azure_evidence must be an EvidencePointer or None")
        if self.status in {FindingStatus.CONFIRMADO, FindingStatus.DIVERGENTE}:
            if self.azure_evidence is None:
                raise ValueError("Finding.azure_evidence is required for this status")
        if self.status is not FindingStatus.CONFIRMADO and not self.impact_or_limit.strip():
            raise ValueError("Finding.impact_or_limit is required for non-confirmed findings")


@dataclass(frozen=True)
class AuditResult:
    """A collection of findings whose stable identifiers are unique."""

    findings: tuple[Finding, ...]

    def __post_init__(self) -> None:
        try:
            findings = tuple(self.findings)
        except TypeError as error:
            raise ValueError("AuditResult.findings must be iterable") from error
        if not all(isinstance(finding, Finding) for finding in findings):
            raise ValueError("AuditResult.findings must contain Finding instances")
        object.__setattr__(self, "findings", findings)
        finding_ids = tuple(finding.id for finding in findings)
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("AuditResult.findings contains duplicate finding IDs")
