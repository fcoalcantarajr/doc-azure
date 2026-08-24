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
        "wit_presence",
        "field_presence",
        "field_required",
        "state_presence",
        "rule_count",
        "layout_control",
        "behavior_rank",
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
        frozenset(),
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
    "state_presence": (
        frozenset({"wit", "state", "expected"}),
        frozenset(),
    ),
    "rule_count": (
        frozenset({"wit", "expected"}),
        frozenset(),
    ),
    "layout_control": (
        frozenset({"wit", "control", "expected"}),
        frozenset(),
    ),
    "behavior_rank": (
        frozenset({"behavior", "expected"}),
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

    def __post_init__(self) -> None:
        _require_string(self.id, "id")
        _require_positive_int(self.page_id, "page_id")
        _require_string(self.slug, "slug")
        _require_string(self.finding, "finding")
        _require_string(self.limit, "limit")
        if not isinstance(self.doc, DocumentaryClaim):
            raise CatalogError("doc must be a DocumentaryClaim")
        if not isinstance(self.check, CheckSpec):
            raise CatalogError("check must be a CheckSpec")
        expected_slug = PAGE_SLUGS.get(self.page_id)
        if expected_slug != self.slug:
            raise CatalogError("page_id and slug do not identify the same fixed page")
        expected_path = f"out/wiki/{self.slug}.md"
        if self.doc.path != expected_path:
            raise CatalogError(f"doc.path must be {expected_path!r}")


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
    if not isinstance(raw_doc, dict) or set(raw_doc) != _DOC_KEYS:
        raise CatalogError("doc must contain the exact documentary schema")
    if not isinstance(raw_check, dict) or "kind" not in raw_check:
        raise CatalogError("check must contain kind")
    kind = raw_check["kind"]
    parameters = {key: value for key, value in raw_check.items() if key != "kind"}
    return ClaimSpec(
        id=raw_claim["id"],
        page_id=raw_claim["page_id"],
        slug=raw_claim["slug"],
        finding=raw_claim["finding"],
        doc=DocumentaryClaim(
            path=raw_doc["path"],
            line=raw_doc["line"],
            excerpt=raw_doc["excerpt"],
            sha256=raw_doc["sha256"],
            value=raw_doc["value"],
        ),
        check=CheckSpec(kind=kind, parameters=parameters),
        limit=raw_claim["limit"],
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
        "state",
        "identity",
        "control",
        "behavior",
        "implemented",
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
        "layout_control",
        "wit_presence",
    }:
        _require_bool(parameters["expected"], "check.expected")
    elif kind in {"count_equals", "rule_count", "behavior_rank"}:
        _require_non_negative_int(parameters["expected"], "check.expected")
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
    if kind == "count_equals":
        if parameters["family"] not in {
            "fields",
            "states",
            "rules",
            "behaviors",
        }:
            raise CatalogError("count_equals family is unsupported")


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
