"""Public API for evidence-backed, offline delta auditing."""

from .build import BuildError, build_all_reports
from .catalog import (
    CatalogError,
    CheckSpec,
    ClaimSpec,
    DocumentaryClaim,
    load_catalog,
)
from .evaluator import EvaluationError, evaluate_claim
from .evidence import EvidenceError, resolve_json_pointer, verify_doc_line
from .models import AuditResult, EvidencePointer, Finding, FindingStatus
from .notion import (
    NotionPublicationError,
    PublicationEntry,
    PublicationManifest,
    expected_publication_manifest,
    load_publication_manifest,
    prepare_notion,
    verify_draft_publication_gate,
    verify_publication_gate,
    verify_review_gate,
    verify_fetched_notion,
)
from .notion_semantics import (
    FindingSemantic,
    ReportSemantic,
    ReportSemanticError,
    parse_notion_semantics,
    parse_report_semantics,
    render_notion_body,
)
from .render import render_report


__all__ = (
    "AuditResult",
    "BuildError",
    "CatalogError",
    "CheckSpec",
    "ClaimSpec",
    "DocumentaryClaim",
    "EvaluationError",
    "EvidenceError",
    "EvidencePointer",
    "Finding",
    "FindingSemantic",
    "FindingStatus",
    "NotionPublicationError",
    "PublicationEntry",
    "PublicationManifest",
    "ReportSemantic",
    "ReportSemanticError",
    "build_all_reports",
    "evaluate_claim",
    "expected_publication_manifest",
    "load_catalog",
    "load_publication_manifest",
    "prepare_notion",
    "verify_draft_publication_gate",
    "parse_notion_semantics",
    "parse_report_semantics",
    "render_report",
    "resolve_json_pointer",
    "render_notion_body",
    "verify_doc_line",
    "verify_fetched_notion",
    "verify_publication_gate",
    "verify_review_gate",
)
