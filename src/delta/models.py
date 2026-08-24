"""Immutable domain objects for evidence-backed delta findings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


_GENERATION_ID = re.compile(r"^[0-9a-f]{32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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
class ReportProvenance:
    """Identity of the exact wiki and process snapshots behind a report."""

    wiki_collected_at: str
    wiki_generation_id: str
    wiki_manifest_sha256: str
    process_collected_at: str
    process_generation_id: str
    process_manifest_sha256: str
    process_name: str
    process_id: str

    def __post_init__(self) -> None:
        for label in ("wiki", "process"):
            collected_at = getattr(self, f"{label}_collected_at")
            _require_timezone_timestamp(collected_at, f"{label} collected_at")
            generation = getattr(self, f"{label}_generation_id")
            if not isinstance(generation, str) or not _GENERATION_ID.fullmatch(
                generation
            ):
                raise ValueError(f"{label} generation ID is malformed")
            manifest = getattr(self, f"{label}_manifest_sha256")
            if not isinstance(manifest, str) or not _SHA256.fullmatch(manifest):
                raise ValueError(f"{label} manifest SHA-256 is malformed")
        _require_non_blank_string(self.process_name, "process_name")
        try:
            UUID(self.process_id)
        except (TypeError, ValueError, AttributeError):
            raise ValueError("process_id must be a UUID") from None


def _require_timezone_timestamp(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{label} must be a timestamp with timezone") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include timezone")


@dataclass(frozen=True)
class EvidencePointer:
    """A path and an exact selector within one collected source artifact."""

    path: str
    selector: str

    def __post_init__(self) -> None:
        _require_non_blank_string(self.path, "EvidencePointer.path")
        _require_non_blank_string(self.selector, "EvidencePointer.selector")


class EvidencePointers(tuple[EvidencePointer, ...]):
    """Immutable one-or-more evidence pointers with singleton compatibility."""

    def __new__(cls, values: object) -> EvidencePointers:
        if not isinstance(values, tuple) or not values or any(
            not isinstance(pointer, EvidencePointer) for pointer in values
        ):
            raise ValueError("evidence pointers must be a non-empty tuple")
        return super().__new__(cls, values)

    @property
    def path(self) -> str:
        if len(self) != 1:
            raise AttributeError("multiple evidence pointers have no single path")
        return self[0].path

    @property
    def selector(self) -> str:
        if len(self) != 1:
            raise AttributeError("multiple evidence pointers have no single selector")
        return self[0].selector


@dataclass(frozen=True)
class Finding:
    """One immutable comparison supported by documentary and process evidence."""

    id: str
    finding: str
    status: FindingStatus
    documented: str
    implemented: str
    doc_evidence: EvidencePointer | tuple[EvidencePointer, ...] | None
    azure_evidence: EvidencePointer | tuple[EvidencePointer, ...] | None
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
        if isinstance(self.doc_evidence, EvidencePointer):
            object.__setattr__(
                self, "doc_evidence", EvidencePointers((self.doc_evidence,))
            )
        else:
            try:
                object.__setattr__(
                    self, "doc_evidence", EvidencePointers(self.doc_evidence)
                )
            except ValueError:
                raise ValueError("Finding.doc_evidence is required") from None
        if isinstance(self.azure_evidence, EvidencePointer):
            object.__setattr__(
                self, "azure_evidence", EvidencePointers((self.azure_evidence,))
            )
        elif self.azure_evidence is not None:
            try:
                object.__setattr__(
                    self, "azure_evidence", EvidencePointers(self.azure_evidence)
                )
            except ValueError:
                raise ValueError(
                    "Finding.azure_evidence must contain EvidencePointer values"
                ) from None
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
