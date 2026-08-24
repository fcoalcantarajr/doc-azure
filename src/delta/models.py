"""Immutable domain objects for evidence-backed delta findings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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
        if not self.path.strip():
            raise ValueError("EvidencePointer.path must not be blank")
        if not self.selector.strip():
            raise ValueError("EvidencePointer.selector must not be blank")


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
        if not self.id.strip():
            raise ValueError("Finding.id must not be blank")
        if not self.finding.strip():
            raise ValueError("Finding.finding must not be blank")
        if self.doc_evidence is None:
            raise ValueError("Finding.doc_evidence is required")
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
        finding_ids = tuple(finding.id for finding in self.findings)
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("AuditResult.findings contains duplicate finding IDs")
