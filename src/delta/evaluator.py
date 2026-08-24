"""Typed evaluators for explicit documentary-versus-process claims."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import UUID

from delta.catalog import ClaimSpec
from delta.evidence import EvidenceError, resolve_json_pointer, verify_doc_content
from delta.models import EvidencePointer, Finding, FindingStatus
from doc_azure.snapshot import SnapshotError, read_snapshot_artifact


class EvaluationError(ValueError):
    """Raised when complete evidence cannot support a declared evaluator."""


@dataclass(frozen=True)
class _Observed:
    status: FindingStatus
    implemented: str
    evidence: EvidencePointer | None


class _EvidenceContext:
    """Resolve verified logical snapshots and artifact-map identities lazily."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._mapping: dict[str, object] | None = None

    def verify_document(self, claim: ClaimSpec) -> EvidencePointer:
        prefix = "out/wiki/"
        if not claim.doc.path.startswith(prefix):
            raise EvaluationError("document evidence path is outside out/wiki")
        relative_path = claim.doc.path.removeprefix(prefix)
        contents = _read_snapshot(
            self.root / "out" / "wiki",
            relative_path,
            "wiki",
        )
        verify_doc_content(
            contents,
            claim.doc.line,
            claim.doc.excerpt,
            claim.doc.sha256,
            label=claim.doc.path,
        )
        return EvidencePointer(claim.doc.path, f"L{claim.doc.line}")

    def load_process_artifact(
        self, relative_path: str
    ) -> tuple[dict[str, object], EvidencePointer]:
        safe_path = _safe_artifact_path(relative_path)
        try:
            payload = json.loads(
                _read_snapshot(
                    self.root / "out" / "process",
                    safe_path.as_posix(),
                    "process",
                )
            )
        except (UnicodeError, ValueError):
            raise EvaluationError(
                f"process artifact {relative_path!r} is unreadable"
            ) from None
        if not isinstance(payload, dict):
            raise EvaluationError(
                f"process artifact {relative_path!r} must be a JSON object"
            )
        return payload, EvidencePointer(f"out/process/{relative_path}", "/")

    def artifact_map(self) -> dict[str, object]:
        if self._mapping is None:
            mapping, _ = self.load_process_artifact("artifact-map.json")
            _validate_artifact_map(mapping)
            globals_payload = mapping["globals"]
            process_path = globals_payload["process"]
            process, _ = self.load_process_artifact(process_path)
            if (
                process.get("name") != mapping["process_name"]
                or process.get("typeId") != mapping["process_id"]
            ):
                raise EvaluationError(
                    "artifact map identity does not match process artifact"
                )
            self._mapping = mapping
        return self._mapping

    def wit_entry(self, reference_name: str) -> dict[str, object]:
        entries = self.artifact_map()["work_item_types"]
        matches = [
            entry
            for entry in entries
            if entry.get("reference_name") == reference_name
        ]
        if len(matches) != 1:
            raise EvaluationError(
                f"artifact map must contain exactly one WIT {reference_name!r}"
            )
        return matches[0]

    def wit_artifact(self, reference_name: str, family: str) -> str:
        entry = self.wit_entry(reference_name)
        artifacts = entry["artifacts"]
        artifact_path = artifacts.get(family)
        if not isinstance(artifact_path, str):
            raise EvaluationError(
                f"WIT {reference_name!r} has no {family!r} artifact mapping"
            )
        return _safe_artifact_path(artifact_path).as_posix()


Evaluator = Callable[[_EvidenceContext, Mapping[str, object]], _Observed]


def evaluate_claim(claim: ClaimSpec, evidence_root: Path) -> Finding:
    """Verify one exact documentary source and evaluate only its declared check."""

    if not isinstance(claim, ClaimSpec):
        raise EvaluationError("claim must be a ClaimSpec")
    context = _EvidenceContext(evidence_root)
    doc_evidence = context.verify_document(claim)
    try:
        evaluator = _EVALUATORS[claim.check.kind]
    except KeyError:
        raise EvaluationError(
            f"unsupported evaluator kind {claim.check.kind!r}"
        ) from None
    observed = evaluator(context, claim.check.parameters)
    return Finding(
        id=claim.id,
        finding=claim.finding,
        status=observed.status,
        documented=claim.doc.value,
        implemented=observed.implemented,
        doc_evidence=doc_evidence,
        azure_evidence=observed.evidence,
        impact_or_limit=(
            "" if observed.status is FindingStatus.CONFIRMADO else claim.limit
        ),
    )


def _equals(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    artifact = _string_parameter(parameters, "artifact")
    pointer = _string_parameter(parameters, "pointer", allow_empty=True)
    payload, base_pointer = context.load_process_artifact(artifact)
    try:
        actual = resolve_json_pointer(payload, pointer)
    except EvidenceError as error:
        raise EvaluationError(f"Azure evidence pointer failed: {error}") from None
    evidence = EvidencePointer(base_pointer.path, pointer or "/")
    return _comparison(actual, parameters["expected"], evidence)


def _count_equals(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    return _evaluate_count(
        context,
        _string_parameter(parameters, "wit"),
        _string_parameter(parameters, "family"),
        parameters["expected"],
    )


def _active_wit_set(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    identity = _string_parameter(parameters, "identity")
    mapping = context.artifact_map()
    entries = mapping["work_item_types"]
    active: list[str] = []
    for entry in entries:
        if entry["is_disabled"]:
            continue
        value = entry[identity]
        if not isinstance(value, str) or not value.strip():
            raise EvaluationError(f"artifact map WIT {identity} is malformed")
        active.append(value)
    if len(active) != len(set(active)):
        raise EvaluationError(f"active WIT {identity} values are not unique")
    actual = tuple(sorted(active, key=lambda value: (value.casefold(), value)))
    expected_value = parameters["expected"]
    if not isinstance(expected_value, Sequence) or isinstance(
        expected_value, (str, bytes)
    ):
        raise EvaluationError("active WIT expected value is malformed")
    expected = tuple(
        sorted(expected_value, key=lambda value: (value.casefold(), value))
    )
    evidence = EvidencePointer(
        "out/process/artifact-map.json", "/work_item_types"
    )
    return _comparison(actual, expected, evidence)


def _wit_presence(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    target = _string_parameter(parameters, "wit")
    entries = context.artifact_map()["work_item_types"]
    matches = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry["reference_name"] == target and not entry["is_disabled"]
    ]
    if len(matches) > 1:
        raise EvaluationError(f"active WIT {target!r} occurs more than once")
    actual = bool(matches)
    selector = (
        f"/work_item_types/{matches[0][0]}/reference_name"
        if matches
        else "/work_item_types"
    )
    return _presence_comparison(
        actual,
        parameters["expected"],
        EvidencePointer("out/process/artifact-map.json", selector),
    )


def _field_presence(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    field = _string_parameter(parameters, "field")
    expected = parameters["expected"]
    artifact = context.wit_artifact(wit, "fields")
    payload, base_pointer = context.load_process_artifact(artifact)
    entries = _envelope(payload, f"fields for {wit}")
    matches = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry.get("referenceName") == field
    ]
    if len(matches) > 1:
        raise EvaluationError(f"field {field!r} occurs more than once in {wit!r}")
    if matches:
        index, _ = matches[0]
        actual = True
        selector = f"/value/{index}/referenceName"
    else:
        actual = False
        selector = "/value"
    evidence = EvidencePointer(base_pointer.path, selector)
    return _presence_comparison(actual, expected, evidence)


def _field_required(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    field = _string_parameter(parameters, "field")
    artifact = context.wit_artifact(wit, "fields")
    payload, base_pointer = context.load_process_artifact(artifact)
    entries = _envelope(payload, f"fields for {wit}")
    matches = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry.get("referenceName") == field
    ]
    if len(matches) != 1:
        if not matches:
            return _Observed(
                FindingStatus.AMBIGUO,
                "campo ausente; obrigatoriedade não aplicável",
                EvidencePointer(base_pointer.path, "/value"),
            )
        raise EvaluationError(f"field {field!r} occurs more than once in {wit!r}")
    index, entry = matches[0]
    if "required" not in entry:
        return _Observed(
            FindingStatus.AMBIGUO,
            "obrigatoriedade não declarada pela resposta",
            EvidencePointer(base_pointer.path, f"/value/{index}"),
        )
    actual = entry["required"]
    if type(actual) is not bool:
        raise EvaluationError(f"field {field!r} required value is malformed")
    evidence = EvidencePointer(base_pointer.path, f"/value/{index}/required")
    return _comparison(actual, parameters["expected"], evidence)


def _state_presence(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    state = _string_parameter(parameters, "state")
    artifact = context.wit_artifact(wit, "states")
    payload, base_pointer = context.load_process_artifact(artifact)
    entries = _envelope(payload, f"states for {wit}")
    matches = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry.get("name") == state
    ]
    if len(matches) > 1:
        raise EvaluationError(f"state {state!r} occurs more than once in {wit!r}")
    actual = bool(matches)
    selector = f"/value/{matches[0][0]}/name" if matches else "/value"
    evidence = EvidencePointer(base_pointer.path, selector)
    return _presence_comparison(actual, parameters["expected"], evidence)


def _rule_count(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    return _evaluate_count(
        context,
        _string_parameter(parameters, "wit"),
        "rules",
        parameters["expected"],
    )


def _layout_control(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    target = _string_parameter(parameters, "control")
    artifact = context.wit_artifact(wit, "layout")
    payload, base_pointer = context.load_process_artifact(artifact)
    matches: list[str] = []
    pages = _list_member(payload, "pages", "layout pages")
    for page_index, page in enumerate(pages):
        sections = _list_member(page, "sections", "layout sections")
        for section_index, section in enumerate(sections):
            groups = _list_member(section, "groups", "layout groups")
            for group_index, group in enumerate(groups):
                controls = _list_member(group, "controls", "layout controls")
                for control_index, control in enumerate(controls):
                    for key in ("id", "referenceName"):
                        if control.get(key) == target:
                            matches.append(
                                "/pages/"
                                f"{page_index}/sections/{section_index}/groups/"
                                f"{group_index}/controls/{control_index}/{key}"
                            )
                            break
    if len(matches) > 1:
        raise EvaluationError(f"layout control {target!r} is not unique in {wit!r}")
    actual = bool(matches)
    selector = matches[0] if matches else "/pages"
    evidence = EvidencePointer(base_pointer.path, selector)
    return _presence_comparison(actual, parameters["expected"], evidence)


def _behavior_rank(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    target = _string_parameter(parameters, "behavior")
    globals_payload = context.artifact_map()["globals"]
    artifact = globals_payload.get("process_behaviors")
    if not isinstance(artifact, str):
        raise EvaluationError("artifact map has no process behaviors artifact")
    payload, base_pointer = context.load_process_artifact(artifact)
    entries = _envelope(payload, "process behaviors")
    matches = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry.get("referenceName") == target
    ]
    if len(matches) > 1:
        raise EvaluationError(f"process behavior {target!r} is not unique")
    if not matches:
        return _Observed(
            FindingStatus.DIVERGENTE,
            "comportamento ausente",
            EvidencePointer(base_pointer.path, "/value"),
        )
    index, entry = matches[0]
    rank = entry.get("rank")
    if not isinstance(rank, int) or isinstance(rank, bool):
        raise EvaluationError(f"process behavior {target!r} rank is malformed")
    evidence = EvidencePointer(base_pointer.path, f"/value/{index}/rank")
    return _comparison(rank, parameters["expected"], evidence)


def _limitation(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    del context
    return _Observed(
        FindingStatus.NAO_VERIFICAVEL_API_PROCESSO,
        _string_parameter(parameters, "implemented"),
        None,
    )


def _ambiguous(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    del context
    return _Observed(
        FindingStatus.AMBIGUO,
        _string_parameter(parameters, "implemented"),
        None,
    )


_EVALUATORS: dict[str, Evaluator] = {
    "equals": _equals,
    "count_equals": _count_equals,
    "active_wit_set": _active_wit_set,
    "wit_presence": _wit_presence,
    "field_presence": _field_presence,
    "field_required": _field_required,
    "state_presence": _state_presence,
    "rule_count": _rule_count,
    "layout_control": _layout_control,
    "behavior_rank": _behavior_rank,
    "limitation": _limitation,
    "ambiguous": _ambiguous,
}


def _evaluate_count(
    context: _EvidenceContext,
    wit: str,
    family: str,
    expected: object,
) -> _Observed:
    artifact = context.wit_artifact(wit, family)
    payload, base_pointer = context.load_process_artifact(artifact)
    entries = _envelope(payload, f"{family} for {wit}")
    count = payload.get("count")
    if count != len(entries):
        raise EvaluationError(f"{family} count/value mismatch for {wit!r}")
    return _comparison(
        count,
        expected,
        EvidencePointer(base_pointer.path, "/count"),
    )


def _comparison(
    actual: object, expected: object, evidence: EvidencePointer
) -> _Observed:
    normalized_actual = _normalize(actual)
    normalized_expected = _normalize(expected)
    status = (
        FindingStatus.CONFIRMADO
        if (
            type(normalized_actual) is type(normalized_expected)
            and normalized_actual == normalized_expected
        )
        else FindingStatus.DIVERGENTE
    )
    return _Observed(status, _format_value(actual), evidence)


def _presence_comparison(
    actual: bool, expected: object, evidence: EvidencePointer
) -> _Observed:
    status = (
        FindingStatus.CONFIRMADO
        if type(expected) is bool and actual is expected
        else FindingStatus.DIVERGENTE
    )
    return _Observed(status, "presente" if actual else "ausente", evidence)


def _normalize(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _normalize(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_normalize(child) for child in value)
    return value


def _format_value(value: object) -> str:
    if type(value) is bool:
        return "sim" if value else "não"
    if isinstance(value, str):
        return value
    normalized = _normalize(value)
    if isinstance(normalized, tuple):
        normalized = list(normalized)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


def _envelope(payload: Mapping[str, object], label: str) -> tuple[dict[str, object], ...]:
    count = payload.get("count")
    values = payload.get("value")
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or not isinstance(values, list)
        or count != len(values)
        or any(not isinstance(entry, dict) for entry in values)
    ):
        raise EvaluationError(f"{label} count/value envelope is malformed")
    return tuple(values)


def _list_member(
    payload: Mapping[str, object], key: str, label: str
) -> tuple[dict[str, object], ...]:
    values = payload.get(key)
    if not isinstance(values, list) or any(
        not isinstance(entry, dict) for entry in values
    ):
        raise EvaluationError(f"{label} are malformed")
    return tuple(values)


def _validate_artifact_map(payload: Mapping[str, object]) -> None:
    if set(payload) != {
        "schema_version",
        "process_name",
        "process_id",
        "globals",
        "work_item_types",
    }:
        raise EvaluationError("artifact map schema is malformed")
    if (
        payload["schema_version"] != 1
        or payload["process_name"] != "Processo-Agil"
    ):
        raise EvaluationError("artifact map schema is malformed")
    process_id = payload["process_id"]
    try:
        UUID(process_id)
    except (TypeError, ValueError, AttributeError):
        raise EvaluationError("artifact map process ID is malformed") from None
    work_item_types = payload.get("work_item_types")
    globals_payload = payload.get("globals")
    if (
        not isinstance(work_item_types, list)
        or not isinstance(globals_payload, dict)
        or any(not isinstance(entry, dict) for entry in work_item_types)
    ):
        raise EvaluationError("artifact map is malformed")
    if set(globals_payload) != {
        "processes",
        "process",
        "work_item_types",
        "process_behaviors",
    }:
        raise EvaluationError("artifact map globals schema is malformed")
    for artifact in globals_payload.values():
        if not isinstance(artifact, str):
            raise EvaluationError("artifact map path is malformed")
        _safe_artifact_path(artifact)
    references: list[str] = []
    for entry in work_item_types:
        if set(entry) != {
            "name",
            "reference_name",
            "customization",
            "is_disabled",
            "artifacts",
        }:
            raise EvaluationError("artifact map WIT schema is malformed")
        reference_name = entry.get("reference_name")
        name = entry.get("name")
        customization = entry.get("customization")
        disabled = entry.get("is_disabled")
        artifacts = entry.get("artifacts")
        if (
            not isinstance(reference_name, str)
            or not reference_name.strip()
            or not isinstance(name, str)
            or not name.strip()
            or not isinstance(customization, str)
            or not customization.strip()
            or type(disabled) is not bool
            or not isinstance(artifacts, dict)
        ):
            raise EvaluationError("artifact map WIT entry is malformed")
        if set(artifacts) != {"fields", "states", "rules", "layout", "behaviors"}:
            raise EvaluationError("artifact map WIT artifacts schema is malformed")
        for artifact in artifacts.values():
            if not isinstance(artifact, str):
                raise EvaluationError("artifact map path is malformed")
            _safe_artifact_path(artifact)
        references.append(reference_name)
    if len(references) != len(set(references)):
        raise EvaluationError("artifact map WIT references are not unique")


def _safe_artifact_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise EvaluationError("process artifact path is malformed")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise EvaluationError("process artifact path is unsafe")
    return path


def _read_snapshot(logical_root: Path, relative_path: str, label: str) -> bytes:
    try:
        return read_snapshot_artifact(logical_root, relative_path)
    except SnapshotError as error:
        raise EvaluationError(f"{label} snapshot is incomplete: {error}") from None


def _string_parameter(
    parameters: Mapping[str, object], name: str, *, allow_empty: bool = False
) -> str:
    value = parameters.get(name)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise EvaluationError(f"check parameter {name!r} is malformed")
    return value
