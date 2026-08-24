"""Typed evaluators for explicit documentary-versus-process claims."""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import UUID

from delta.catalog import ClaimSpec, DocumentaryClaim
from delta.evidence import EvidenceError, resolve_json_pointer, verify_doc_content
from delta.models import EvidencePointer, Finding, FindingStatus
from doc_azure.process_collector import MAPPING_SCHEMA_VERSION
from doc_azure.snapshot import SnapshotError, read_snapshot_artifact


class EvaluationError(ValueError):
    """Raised when complete evidence cannot support a declared evaluator."""


@dataclass(frozen=True)
class _Observed:
    status: FindingStatus
    implemented: str
    evidence: EvidencePointer | tuple[EvidencePointer, ...] | None


class _EvidenceContext:
    """Resolve verified logical snapshots and artifact-map identities lazily."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._mapping: dict[str, object] | None = None

    def verify_document(self, document: DocumentaryClaim) -> EvidencePointer:
        prefix = "out/wiki/"
        if not document.path.startswith(prefix):
            raise EvaluationError("document evidence path is outside out/wiki")
        relative_path = document.path.removeprefix(prefix)
        contents = _read_snapshot(
            self.root / "out" / "wiki",
            relative_path,
            "wiki",
        )
        verify_doc_content(
            contents,
            document.line,
            document.excerpt,
            document.sha256,
            label=document.path,
        )
        return EvidencePointer(document.path, f"L{document.line}")

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
    doc_evidence = tuple(
        context.verify_document(document) for document in claim.documents
    )
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
        impact_or_limit=claim.limit,
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
    excluded_customizations = _customization_filter(parameters)
    active: list[str] = []
    excluded_active: list[str] = []
    disabled: list[str] = []
    for entry in entries:
        value = entry[identity]
        if not isinstance(value, str) or not value.strip():
            raise EvaluationError(f"artifact map WIT {identity} is malformed")
        if entry["is_disabled"]:
            disabled.append(value)
        elif entry["customization"] in excluded_customizations:
            excluded_active.append(value)
        else:
            active.append(value)
    all_identities = (*active, *excluded_active, *disabled)
    if len(all_identities) != len(set(all_identities)):
        raise EvaluationError(f"WIT {identity} values are not unique")
    actual = tuple(sorted(active, key=lambda value: (value.casefold(), value)))
    excluded = tuple(
        sorted(excluded_active, key=lambda value: (value.casefold(), value))
    )
    disabled_values = tuple(
        sorted(disabled, key=lambda value: (value.casefold(), value))
    )
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
    status = (
        FindingStatus.CONFIRMADO
        if type(actual) is type(expected) and actual == expected
        else FindingStatus.DIVERGENTE
    )
    implemented = (
        f"ativos comparados: {_identity_list(actual)}; "
        f"ativos excluídos: {_identity_list(excluded)}; "
        f"desabilitados: {_identity_list(disabled_values)}"
    )
    return _Observed(status, implemented, evidence)


def _identity_list(values: Sequence[str]) -> str:
    return ", ".join(values) if values else "nenhum"


def _active_required_field_count(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    field = _string_parameter(parameters, "field")
    expected = parameters["expected"]
    excluded_customizations = _customization_filter(parameters)
    matching_wits: list[str] = []
    evidence: list[EvidencePointer] = [
        EvidencePointer("out/process/artifact-map.json", "/work_item_types")
    ]
    for entry in context.artifact_map()["work_item_types"]:
        if (
            entry["is_disabled"]
            or entry["customization"] in excluded_customizations
        ):
            continue
        wit = entry["reference_name"]
        artifact = context.wit_artifact(wit, "fields")
        payload, base_pointer = context.load_process_artifact(artifact)
        entries = _envelope(payload, f"fields for {wit}")
        matches = [
            (index, candidate)
            for index, candidate in enumerate(entries)
            if candidate.get("referenceName") == field
        ]
        if len(matches) > 1:
            raise EvaluationError(f"field {field!r} occurs more than once in {wit!r}")
        if not matches:
            evidence.append(EvidencePointer(base_pointer.path, "/value"))
            continue
        index, candidate = matches[0]
        evidence.append(
            EvidencePointer(base_pointer.path, f"/value/{index}/required")
        )
        required = candidate.get("required")
        if type(required) is not bool:
            return _Observed(
                FindingStatus.AMBIGUO,
                f"obrigatoriedade não declarada em {wit}",
                tuple(
                    (
                        *evidence[:-1],
                        EvidencePointer(base_pointer.path, f"/value/{index}"),
                    )
                ),
            )
        if required:
            matching_wits.append(wit)
    count = len(matching_wits)
    status = (
        FindingStatus.CONFIRMADO
        if type(expected) is int and count == expected
        else FindingStatus.DIVERGENTE
    )
    noun = "WIT ativo" if count == 1 else "WITs ativos"
    implemented = f"{count} {noun}: " + ", ".join(matching_wits)
    return _Observed(
        status,
        implemented,
        tuple(evidence),
    )


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


def _field_alternative(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    expected_field = _string_parameter(parameters, "expected_field")
    actual_field = _string_parameter(parameters, "actual_field")
    actual_name = _string_parameter(parameters, "actual_name")
    artifact = context.wit_artifact(wit, "fields")
    payload, base_pointer = context.load_process_artifact(artifact)
    entries = _envelope(payload, f"fields for {wit}")
    expected_matches = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry.get("referenceName") == expected_field
    ]
    actual_matches = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry.get("referenceName") == actual_field
    ]
    if len(expected_matches) > 1:
        raise EvaluationError(
            f"field {expected_field!r} occurs more than once in {wit!r}"
        )
    if len(actual_matches) != 1:
        raise EvaluationError(
            f"alternative field {actual_field!r} must occur exactly once in {wit!r}"
        )
    actual_index, actual_entry = actual_matches[0]
    observed_name = actual_entry.get("name")
    if not isinstance(observed_name, str) or not observed_name.strip():
        raise EvaluationError(f"alternative field {actual_field!r} name is malformed")
    if observed_name != actual_name:
        raise EvaluationError(
            f"alternative field {actual_field!r} name does not match catalog"
        )
    expected_present = bool(expected_matches)
    expected_selector = (
        f"/value/{expected_matches[0][0]}/referenceName"
        if expected_present
        else "/value"
    )
    status = (
        FindingStatus.CONFIRMADO
        if expected_present
        else FindingStatus.DIVERGENTE
    )
    return _Observed(
        status,
        (
            f"campo documentado {'presente' if expected_present else 'ausente'}; "
            f"alternativa presente: {actual_field} ({observed_name})"
        ),
        (
            EvidencePointer(base_pointer.path, expected_selector),
            EvidencePointer(
                base_pointer.path,
                f"/value/{actual_index}/referenceName",
            ),
            EvidencePointer(base_pointer.path, f"/value/{actual_index}/name"),
        ),
    )


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


def _field_name_pattern_minimum(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    prefix = _string_parameter(parameters, "prefix")
    suffix = _string_parameter(parameters, "suffix")
    expected_minimum = parameters["expected_minimum"]
    artifact = context.wit_artifact(wit, "fields")
    payload, base_pointer = context.load_process_artifact(artifact)
    entries = _envelope(payload, f"fields for {wit}")
    matches: list[str] = []
    for entry in entries:
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise EvaluationError(f"field name is malformed in {wit!r}")
        if name.startswith(prefix) and name.endswith(suffix):
            matches.append(name)
    count = len(matches)
    status = (
        FindingStatus.CONFIRMADO
        if type(expected_minimum) is int and count >= expected_minimum
        else FindingStatus.DIVERGENTE
    )
    noun = "campo" if count == 1 else "campos"
    return _Observed(
        status,
        f"{count} {noun}: " + ", ".join(matches),
        EvidencePointer(base_pointer.path, "/value"),
    )


def _field_property(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    field = _string_parameter(parameters, "field")
    property_name = _string_parameter(parameters, "property")
    artifact = context.wit_artifact(wit, "fields")
    payload, base_pointer = context.load_process_artifact(artifact)
    entries = _envelope(payload, f"fields for {wit}")
    matches = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry.get("referenceName") == field
    ]
    if len(matches) != 1:
        raise EvaluationError(f"field {field!r} must occur exactly once in {wit!r}")
    index, entry = matches[0]
    if property_name not in entry:
        raise EvaluationError(
            f"field {field!r} property {property_name!r} is absent"
        )
    return _comparison(
        entry[property_name],
        parameters["expected"],
        EvidencePointer(base_pointer.path, f"/value/{index}/{property_name}"),
    )


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


def _state_sequence(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    artifact = context.wit_artifact(wit, "states")
    payload, base_pointer = context.load_process_artifact(artifact)
    entries = _envelope(payload, f"states for {wit}")
    ordered: list[tuple[int, str]] = []
    for entry in entries:
        order = entry.get("order")
        name = entry.get("name")
        if (
            not isinstance(order, int)
            or isinstance(order, bool)
            or not isinstance(name, str)
            or not name.strip()
        ):
            raise EvaluationError(f"state order/name is malformed in {wit!r}")
        ordered.append((order, name))
    if len({order for order, _ in ordered}) != len(ordered):
        raise EvaluationError(f"state order is not unique in {wit!r}")
    if len({name for _, name in ordered}) != len(ordered):
        raise EvaluationError(f"state name is not unique in {wit!r}")
    actual = tuple(name for _, name in sorted(ordered))
    return _comparison(
        actual,
        parameters["expected"],
        EvidencePointer(base_pointer.path, "/value"),
    )


def _state_property(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    state = _string_parameter(parameters, "state")
    property_name = _string_parameter(parameters, "property")
    artifact = context.wit_artifact(wit, "states")
    payload, base_pointer = context.load_process_artifact(artifact)
    entries = _envelope(payload, f"states for {wit}")
    matches = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry.get("name") == state
    ]
    if len(matches) != 1:
        raise EvaluationError(f"state {state!r} must occur exactly once in {wit!r}")
    index, entry = matches[0]
    if property_name not in entry:
        raise EvaluationError(
            f"state {state!r} property {property_name!r} is absent"
        )
    return _comparison(
        entry[property_name],
        parameters["expected"],
        EvidencePointer(base_pointer.path, f"/value/{index}/{property_name}"),
    )


def _wit_state_set_equal(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    left_wit = _string_parameter(parameters, "left_wit")
    right_wit = _string_parameter(parameters, "right_wit")
    left, left_pointer = _state_names(context, left_wit)
    right, right_pointer = _state_names(context, right_wit)
    actual = set(left) == set(right)
    implemented = (
        f"{left_wit}={_format_value(tuple(sorted(left)))}; "
        f"{right_wit}={_format_value(tuple(sorted(right)))}"
    )
    status = (
        FindingStatus.CONFIRMADO
        if type(parameters["expected"]) is bool
        and actual is parameters["expected"]
        else FindingStatus.DIVERGENTE
    )
    return _Observed(status, implemented, (left_pointer, right_pointer))


def _state_names(
    context: _EvidenceContext, wit: str
) -> tuple[tuple[str, ...], EvidencePointer]:
    artifact = context.wit_artifact(wit, "states")
    payload, base_pointer = context.load_process_artifact(artifact)
    entries = _envelope(payload, f"states for {wit}")
    names = tuple(entry.get("name") for entry in entries)
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise EvaluationError(f"state names are malformed in {wit!r}")
    if len(names) != len(set(names)):
        raise EvaluationError(f"state names are not unique in {wit!r}")
    return names, EvidencePointer(base_pointer.path, "/value")


def _transition_field_coverage(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    direction = _string_parameter(parameters, "direction")
    state_names, state_pointer = _state_names(context, wit)
    fields_artifact = context.wit_artifact(wit, "fields")
    fields_payload, fields_pointer = context.load_process_artifact(fields_artifact)
    fields = _envelope(fields_payload, f"fields for {wit}")
    references: set[str] = set()
    for field in fields:
        reference = field.get("referenceName")
        if not isinstance(reference, str) or not reference.strip():
            raise EvaluationError(f"field referenceName is malformed in {wit!r}")
        references.add(reference)
    prefix = "EntrouemEstado" if direction == "entry" else "SaiudoEstado"
    expected_references = {
        state: f"Custom.{prefix}{_identifier_text(state)}Date"
        for state in state_names
    }
    missing = [
        state
        for state, reference in expected_references.items()
        if reference not in references
    ]
    actual = not missing
    status = (
        FindingStatus.CONFIRMADO
        if type(parameters["expected"]) is bool
        and actual is parameters["expected"]
        else FindingStatus.DIVERGENTE
    )
    covered = len(state_names) - len(missing)
    implemented = f"{covered} de {len(state_names)} estados cobertos"
    if missing:
        implemented += "; ausentes: " + ", ".join(missing)
    return _Observed(
        status,
        implemented,
        (
            EvidencePointer(fields_pointer.path, "/value"),
            state_pointer,
        ),
    )


def _identifier_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(character for character in normalized if character.isalnum())


def _rule_count(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    return _evaluate_count(
        context,
        _string_parameter(parameters, "wit"),
        "rules",
        parameters["expected"],
    )


def _rule_presence(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    target = _string_parameter(parameters, "rule")
    artifact = context.wit_artifact(wit, "rules")
    payload, base_pointer = context.load_process_artifact(artifact)
    entries = _envelope(payload, f"rules for {wit}")
    matches = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry.get("name") == target
    ]
    if len(matches) > 1:
        raise EvaluationError(f"rule {target!r} occurs more than once in {wit!r}")
    actual = bool(matches)
    selector = f"/value/{matches[0][0]}/name" if matches else "/value"
    return _presence_comparison(
        actual,
        parameters["expected"],
        EvidencePointer(base_pointer.path, selector),
    )


def _rule_action(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    artifact = context.wit_artifact(wit, "rules")
    payload, base_pointer = context.load_process_artifact(artifact)
    rules = _envelope(payload, f"rules for {wit}")
    matches: list[tuple[int, int]] = []
    for rule_index, rule in enumerate(rules):
        conditions = _list_member(rule, "conditions", f"rule conditions for {wit}")
        actions = _list_member(rule, "actions", f"rule actions for {wit}")
        condition_matches = any(
            condition.get("field") == parameters["condition_field"]
            and condition.get("value") == parameters["condition_value"]
            for condition in conditions
        )
        if not condition_matches:
            continue
        for action_index, action in enumerate(actions):
            if (
                action.get("actionType") == parameters["action_type"]
                and action.get("targetField") == parameters["target_field"]
                and action.get("value") == parameters["action_value"]
            ):
                matches.append((rule_index, action_index))
    if len(matches) > 1:
        raise EvaluationError(f"rule action predicate is not unique in {wit!r}")
    actual = bool(matches)
    selector = (
        f"/value/{matches[0][0]}/actions/{matches[0][1]}"
        if matches
        else "/value"
    )
    return _presence_comparison(
        actual,
        parameters["expected"],
        EvidencePointer(base_pointer.path, selector),
    )


def _unique_custom_field_minimum(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    raw_wits = parameters["wits"]
    if not isinstance(raw_wits, Sequence) or isinstance(raw_wits, (str, bytes)):
        raise EvaluationError("unique custom field WITs are malformed")
    references: set[str] = set()
    evidence: list[EvidencePointer] = []
    for raw_wit in raw_wits:
        if not isinstance(raw_wit, str) or not raw_wit.strip():
            raise EvaluationError("unique custom field WITs are malformed")
        artifact = context.wit_artifact(raw_wit, "fields")
        payload, base_pointer = context.load_process_artifact(artifact)
        entries = _envelope(payload, f"fields for {raw_wit}")
        for entry in entries:
            reference = entry.get("referenceName")
            customization = entry.get("customization")
            if (
                not isinstance(reference, str)
                or not reference.strip()
                or not isinstance(customization, str)
                or not customization.strip()
            ):
                raise EvaluationError(f"field identity is malformed in {raw_wit!r}")
            if customization == "custom":
                references.add(reference)
        evidence.append(EvidencePointer(base_pointer.path, "/value"))
    expected_minimum = parameters["expected_minimum"]
    status = (
        FindingStatus.CONFIRMADO
        if type(expected_minimum) is int and len(references) >= expected_minimum
        else FindingStatus.DIVERGENTE
    )
    return _Observed(
        status,
        f"{len(references)} campos tecnicamente customizados únicos",
        tuple(evidence),
    )


def _layout_control(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    target = _string_parameter(parameters, "control")
    control, evidence, identity_key = _find_layout_control(context, wit, target)
    if control is not None:
        evidence = EvidencePointer(
            evidence.path,
            f"{evidence.selector}/{identity_key}",
        )
    return _presence_comparison(control is not None, parameters["expected"], evidence)


def _layout_control_order(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    wit = _string_parameter(parameters, "wit")
    target = _string_parameter(parameters, "control")
    control, evidence, _ = _find_layout_control(context, wit, target)
    if control is None:
        raise EvaluationError(f"layout control {target!r} is absent in {wit!r}")
    order = control.get("order")
    if not isinstance(order, int) or isinstance(order, bool):
        raise EvaluationError(f"layout control {target!r} order is malformed")
    return _comparison(
        order,
        parameters["expected"],
        EvidencePointer(evidence.path, f"{evidence.selector}/order"),
    )


def _find_layout_control(
    context: _EvidenceContext,
    wit: str,
    target: str,
) -> tuple[dict[str, object] | None, EvidencePointer, str | None]:
    artifact = context.wit_artifact(wit, "layout")
    payload, base_pointer = context.load_process_artifact(artifact)
    if payload.get("referenceName") != wit:
        raise EvaluationError(f"layout artifact identity does not match {wit!r}")
    layout = payload.get("layout")
    if not isinstance(layout, dict):
        raise EvaluationError("expanded layout is malformed")
    matches: list[tuple[str, dict[str, object], str]] = []
    pages = _list_member(layout, "pages", "layout pages")
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
                                (
                                    "/layout/pages/"
                                    f"{page_index}/sections/{section_index}/groups/"
                                    f"{group_index}/controls/{control_index}",
                                    control,
                                    key,
                                )
                            )
                            break
    if len(matches) > 1:
        raise EvaluationError(f"layout control {target!r} is not unique in {wit!r}")
    if not matches:
        return None, EvidencePointer(base_pointer.path, "/layout/pages"), None
    selector, control, identity_key = matches[0]
    return control, EvidencePointer(base_pointer.path, selector), identity_key


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


def _technical_context(
    context: _EvidenceContext, parameters: Mapping[str, object]
) -> _Observed:
    artifact = _string_parameter(parameters, "artifact")
    pointer = _string_parameter(parameters, "pointer", allow_empty=True)
    payload, base_pointer = context.load_process_artifact(artifact)
    try:
        actual = resolve_json_pointer(payload, pointer)
    except EvidenceError as error:
        raise EvaluationError(f"Azure evidence pointer failed: {error}") from None
    return _Observed(
        FindingStatus.AMBIGUO,
        _format_value(actual),
        EvidencePointer(base_pointer.path, pointer or "/"),
    )


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
    "active_required_field_count": _active_required_field_count,
    "wit_presence": _wit_presence,
    "field_presence": _field_presence,
    "field_alternative": _field_alternative,
    "field_required": _field_required,
    "field_name_pattern_minimum": _field_name_pattern_minimum,
    "field_property": _field_property,
    "state_presence": _state_presence,
    "state_sequence": _state_sequence,
    "state_property": _state_property,
    "wit_state_set_equal": _wit_state_set_equal,
    "transition_field_coverage": _transition_field_coverage,
    "rule_count": _rule_count,
    "rule_presence": _rule_presence,
    "rule_action": _rule_action,
    "layout_control": _layout_control,
    "layout_control_order": _layout_control_order,
    "unique_custom_field_minimum": _unique_custom_field_minimum,
    "behavior_rank": _behavior_rank,
    "technical_context": _technical_context,
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
        payload["schema_version"] != MAPPING_SCHEMA_VERSION
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


def _customization_filter(
    parameters: Mapping[str, object],
) -> tuple[str, ...]:
    value = parameters.get("exclude_customizations", ())
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise EvaluationError("active WIT customization filter is malformed")
    return tuple(value)
