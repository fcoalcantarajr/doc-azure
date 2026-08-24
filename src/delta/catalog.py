"""Strict schema for explicit, source-backed wiki claims."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType


CATALOG_SCHEMA_VERSION = 1
PAGE_SLUGS = {
    35: "leiame",
    10: "politicas",
    9: "changelog",
    37: "apendice",
}
SUPPORTED_CHECK_KINDS = frozenset(
    {
        "equals",
        "count_equals",
        "active_wit_set",
        "active_required_field_count",
        "wit_presence",
        "field_presence",
        "field_required",
        "field_name_pattern_minimum",
        "field_property",
        "state_presence",
        "state_sequence",
        "state_property",
        "wit_state_set_equal",
        "transition_field_coverage",
        "rule_count",
        "rule_presence",
        "rule_action",
        "layout_control",
        "layout_control_order",
        "unique_custom_field_minimum",
        "behavior_rank",
        "technical_context",
        "limitation",
        "ambiguous",
    }
)
_HASH = re.compile(r"^[0-9a-f]{64}$")
_CLAIM_KEYS = frozenset(
    {"id", "page_id", "slug", "finding", "doc", "check", "limit"}
)
_DOC_KEYS = frozenset({"path", "line", "excerpt", "sha256", "value"})
_CHECK_KEYS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "equals": (
        frozenset({"artifact", "pointer", "expected"}),
        frozenset(),
    ),
    "count_equals": (
        frozenset({"wit", "family", "expected"}),
        frozenset(),
    ),
    "active_wit_set": (
        frozenset({"expected", "identity"}),
        frozenset({"exclude_customizations"}),
    ),
    "active_required_field_count": (
        frozenset({"field", "expected"}),
        frozenset({"exclude_customizations"}),
    ),
    "wit_presence": (
        frozenset({"wit", "expected"}),
        frozenset(),
    ),
    "field_presence": (
        frozenset({"wit", "field", "expected"}),
        frozenset(),
    ),
    "field_required": (
        frozenset({"wit", "field", "expected"}),
        frozenset(),
    ),
    "field_name_pattern_minimum": (
        frozenset({"wit", "prefix", "suffix", "expected_minimum"}),
        frozenset(),
    ),
    "field_property": (
        frozenset({"wit", "field", "property", "expected"}),
        frozenset(),
    ),
    "state_presence": (
        frozenset({"wit", "state", "expected"}),
        frozenset(),
    ),
    "state_sequence": (
        frozenset({"wit", "expected"}),
        frozenset(),
    ),
    "state_property": (
        frozenset({"wit", "state", "property", "expected"}),
        frozenset(),
    ),
    "wit_state_set_equal": (
        frozenset({"left_wit", "right_wit", "expected"}),
        frozenset(),
    ),
    "transition_field_coverage": (
        frozenset({"wit", "direction", "expected"}),
        frozenset(),
    ),
    "rule_count": (
        frozenset({"wit", "expected"}),
        frozenset(),
    ),
    "rule_presence": (
        frozenset({"wit", "rule", "expected"}),
        frozenset(),
    ),
    "rule_action": (
        frozenset(
            {
                "wit",
                "condition_field",
                "condition_value",
                "action_type",
                "target_field",
                "action_value",
                "expected",
            }
        ),
        frozenset(),
    ),
    "layout_control": (
        frozenset({"wit", "control", "expected"}),
        frozenset(),
    ),
    "layout_control_order": (
        frozenset({"wit", "control", "expected"}),
        frozenset(),
    ),
    "unique_custom_field_minimum": (
        frozenset({"wits", "expected_minimum"}),
        frozenset(),
    ),
    "behavior_rank": (
        frozenset({"behavior", "expected"}),
        frozenset(),
    ),
    "technical_context": (
        frozenset({"artifact", "pointer"}),
        frozenset(),
    ),
    "limitation": (
        frozenset({"implemented"}),
        frozenset(),
    ),
    "ambiguous": (
        frozenset({"implemented"}),
        frozenset(),
    ),
}


class CatalogError(ValueError):
    """Raised when a claim catalog is malformed or underspecified."""


@dataclass(frozen=True)
class DocumentaryClaim:
    """Exact documentary source and the value asserted by that source."""

    path: str
    line: int
    excerpt: str
    sha256: str
    value: str

    def __post_init__(self) -> None:
        _require_string(self.path, "doc.path")
        _require_positive_int(self.line, "doc.line")
        _require_string(self.excerpt, "doc.excerpt")
        _require_string(self.value, "doc.value")
        if not isinstance(self.sha256, str) or _HASH.fullmatch(self.sha256) is None:
            raise CatalogError("doc.sha256 must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class CheckSpec:
    """One evaluator kind and only its explicitly declared parameters."""

    kind: str
    parameters: Mapping[str, object]

    def __post_init__(self) -> None:
        _require_string(self.kind, "check.kind")
        if self.kind not in SUPPORTED_CHECK_KINDS:
            raise CatalogError(f"unsupported check kind: {self.kind!r}")
        if not isinstance(self.parameters, Mapping):
            raise CatalogError("check parameters must be an object")
        copied = {key: _freeze_json(value) for key, value in self.parameters.items()}
        if any(not isinstance(key, str) for key in copied):
            raise CatalogError("check parameter names must be strings")
        _validate_check_parameters(self.kind, copied)
        object.__setattr__(self, "parameters", MappingProxyType(copied))


@dataclass(frozen=True)
class ClaimSpec:
    """One material comparison sourced from exactly one wiki page."""

    id: str
    page_id: int
    slug: str
    finding: str
    doc: DocumentaryClaim
    check: CheckSpec
    limit: str
    doc_fragments: tuple[DocumentaryClaim, ...] = ()

    def __post_init__(self) -> None:
        _require_string(self.id, "id")
        _require_positive_int(self.page_id, "page_id")
        _require_string(self.slug, "slug")
        _require_string(self.finding, "finding")
        if not isinstance(self.limit, str) or (
            self.limit != "" and not self.limit.strip()
        ):
            raise CatalogError("limit must be a string")
        if not isinstance(self.doc, DocumentaryClaim):
            raise CatalogError("doc must be a DocumentaryClaim")
        if not isinstance(self.check, CheckSpec):
            raise CatalogError("check must be a CheckSpec")
        if any(
            not isinstance(fragment, DocumentaryClaim)
            for fragment in self.doc_fragments
        ):
            raise CatalogError("doc fragments must be DocumentaryClaim values")
        expected_slug = PAGE_SLUGS.get(self.page_id)
        if expected_slug != self.slug:
            raise CatalogError("page_id and slug do not identify the same fixed page")
        expected_path = f"out/wiki/{self.slug}.md"
        if self.doc.path != expected_path:
            raise CatalogError(f"doc.path must be {expected_path!r}")
        if any(fragment.path != expected_path for fragment in self.doc_fragments):
            raise CatalogError(f"doc.path must be {expected_path!r}")
        if any(fragment.sha256 != self.doc.sha256 for fragment in self.doc_fragments):
            raise CatalogError("all documentary fragments must use the same page hash")

    @property
    def documents(self) -> tuple[DocumentaryClaim, ...]:
        """Return every exact fragment supporting this claim in source order."""

        return (self.doc, *self.doc_fragments)


def load_catalog(path: Path) -> tuple[ClaimSpec, ...]:
    """Load a strict versioned catalog while preserving source order."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise CatalogError("catalog is unreadable or invalid JSON") from None
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "claims"}:
        raise CatalogError("catalog root must contain schema_version and claims")
    if payload["schema_version"] != CATALOG_SCHEMA_VERSION:
        raise CatalogError("catalog schema_version is unsupported")
    raw_claims = payload["claims"]
    if not isinstance(raw_claims, list) or not raw_claims:
        raise CatalogError("catalog claims must be a non-empty array")

    claims = tuple(_parse_claim(raw_claim) for raw_claim in raw_claims)
    identifiers = tuple(claim.id for claim in claims)
    if len(identifiers) != len(set(identifiers)):
        raise CatalogError("catalog contains duplicate claim IDs")
    return claims


def _parse_claim(raw_claim: object) -> ClaimSpec:
    if not isinstance(raw_claim, dict) or set(raw_claim) != _CLAIM_KEYS:
        raise CatalogError("each claim must contain the exact claim schema")
    raw_doc = raw_claim["doc"]
    raw_check = raw_claim["check"]
    raw_documents = raw_doc if isinstance(raw_doc, list) else [raw_doc]
    if not raw_documents or any(
        not isinstance(document, dict) or set(document) != _DOC_KEYS
        for document in raw_documents
    ):
        raise CatalogError("doc must contain one or more exact documentary fragments")
    if not isinstance(raw_check, dict) or "kind" not in raw_check:
        raise CatalogError("check must contain kind")
    kind = raw_check["kind"]
    parameters = {key: value for key, value in raw_check.items() if key != "kind"}
    documents = tuple(_parse_document(document) for document in raw_documents)
    return ClaimSpec(
        id=raw_claim["id"],
        page_id=raw_claim["page_id"],
        slug=raw_claim["slug"],
        finding=raw_claim["finding"],
        doc=documents[0],
        check=CheckSpec(kind=kind, parameters=parameters),
        limit=raw_claim["limit"],
        doc_fragments=documents[1:],
    )


def _parse_document(raw_doc: Mapping[str, object]) -> DocumentaryClaim:
    return DocumentaryClaim(
        path=raw_doc["path"],
        line=raw_doc["line"],
        excerpt=raw_doc["excerpt"],
        sha256=raw_doc["sha256"],
        value=raw_doc["value"],
    )


def _validate_check_parameters(kind: str, parameters: Mapping[str, object]) -> None:
    required, optional = _CHECK_KEYS[kind]
    keys = frozenset(parameters)
    missing = required - keys
    if missing:
        name = sorted(missing)[0]
        raise CatalogError(f"{kind} check is missing {name}")
    unexpected = keys - required - optional
    if unexpected:
        name = sorted(unexpected)[0]
        raise CatalogError(f"{kind} check has unexpected parameter {name}")

    for name in (
        "artifact",
        "pointer",
        "wit",
        "family",
        "field",
        "rule",
        "state",
        "identity",
        "control",
        "behavior",
        "implemented",
        "prefix",
        "suffix",
        "property",
        "left_wit",
        "right_wit",
        "direction",
        "condition_field",
        "condition_value",
        "action_type",
        "target_field",
        "action_value",
    ):
        if name in parameters:
            _require_string(parameters[name], f"check.{name}")
    if "artifact" in parameters:
        _validate_artifact_path(parameters["artifact"])
    if "pointer" in parameters:
        pointer = parameters["pointer"]
        if pointer != "" and not pointer.startswith("/"):
            raise CatalogError("check.pointer must be an RFC 6901 pointer")

    if kind in {
        "field_presence",
        "field_required",
        "state_presence",
        "rule_presence",
        "layout_control",
        "wit_presence",
        "wit_state_set_equal",
        "transition_field_coverage",
        "rule_action",
    }:
        _require_bool(parameters["expected"], "check.expected")
    elif kind in {
        "count_equals",
        "rule_count",
        "behavior_rank",
        "layout_control_order",
        "active_required_field_count",
    }:
        _require_non_negative_int(parameters["expected"], "check.expected")
    elif kind in {"field_name_pattern_minimum", "unique_custom_field_minimum"}:
        _require_non_negative_int(
            parameters["expected_minimum"],
            "check.expected_minimum",
        )
        if parameters["expected_minimum"] == 0:
            raise CatalogError("check.expected_minimum must be positive")
    elif kind == "state_sequence":
        _validate_unique_strings(parameters["expected"], "state_sequence expected")
    elif kind == "field_property":
        if parameters["property"] != "customization":
            raise CatalogError("field_property property is unsupported")
    elif kind == "state_property":
        if parameters["property"] != "stateCategory":
            raise CatalogError("state_property property is unsupported")
    if kind == "transition_field_coverage" and parameters["direction"] not in {
        "entry",
        "exit",
    }:
        raise CatalogError("transition_field_coverage direction is unsupported")
    if kind == "unique_custom_field_minimum":
        _validate_unique_strings(parameters["wits"], "unique custom field WITs")
    elif kind == "active_wit_set":
        if parameters["identity"] not in {"name", "reference_name"}:
            raise CatalogError("active_wit_set identity is unsupported")
        expected = parameters["expected"]
        if (
            not isinstance(expected, Sequence)
            or isinstance(expected, (str, bytes))
            or not expected
            or any(not isinstance(item, str) or not item.strip() for item in expected)
            or len(set(expected)) != len(expected)
        ):
            raise CatalogError("active_wit_set expected must be unique strings")
        _validate_unique_strings(
            parameters.get("exclude_customizations", ()),
            "active_wit_set exclude_customizations",
            allow_empty=True,
        )
    if kind == "active_required_field_count":
        _validate_unique_strings(
            parameters.get("exclude_customizations", ()),
            "active_required_field_count exclude_customizations",
            allow_empty=True,
        )
    if kind == "count_equals":
        if parameters["family"] not in {
            "fields",
            "states",
            "rules",
            "behaviors",
        }:
            raise CatalogError("count_equals family is unsupported")


def _validate_unique_strings(
    value: object,
    label: str,
    *,
    allow_empty: bool = False,
) -> None:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or (not allow_empty and not value)
        or any(not isinstance(item, str) or not item.strip() for item in value)
        or len(set(value)) != len(value)
    ):
        raise CatalogError(f"{label} must be unique strings")


def _validate_artifact_path(value: object) -> None:
    _require_string(value, "check.artifact")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise CatalogError("check.artifact must be a safe relative path")


def _freeze_json(value: object) -> object:
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise CatalogError("check objects must use string keys")
        return MappingProxyType(
            {key: _freeze_json(child) for key, child in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json(child) for child in value)
    if value is None or type(value) in {str, int, float, bool}:
        return value
    if isinstance(value, tuple):
        return tuple(_freeze_json(child) for child in value)
    raise CatalogError("check parameters must be JSON-compatible")


def _require_string(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{label} must be a non-blank string")


def _require_positive_int(value: object, label: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise CatalogError(f"{label} must be a positive integer")


def _require_non_negative_int(value: object, label: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CatalogError(f"{label} must be a non-negative integer")


def _require_bool(value: object, label: str) -> None:
    if type(value) is not bool:
        raise CatalogError(f"{label} must be a boolean")
