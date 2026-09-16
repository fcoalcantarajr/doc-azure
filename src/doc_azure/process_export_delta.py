"""Compare two process export models and render a traceable LLM-ready delta."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from doc_azure.process_export_render import (
    EvidenceFamily,
    JsonArray,
    JsonObject,
    JsonValue,
    ProcessExportModel,
    WorkItemTypeModel,
    to_builtin,
)


DELTA_SCHEMA_VERSION = 1
DeltaStatus = Literal["SEM_BASELINE", "SEM_ALTERACOES", "COM_ALTERACOES"]
ChangeKind = Literal["added", "removed", "changed"]
_MISSING = object()


@dataclass(frozen=True)
class SnapshotIdentity:
    """Stable identity of one immutable process source generation."""

    source_generation: str
    source_manifest_sha256: str
    source_collected_at: str

    @classmethod
    def from_model(cls, model: ProcessExportModel) -> SnapshotIdentity:
        return cls(
            source_generation=model.source_generation,
            source_manifest_sha256=model.source_manifest_sha256,
            source_collected_at=model.source_collected_at,
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "source_generation": self.source_generation,
            "source_manifest_sha256": self.source_manifest_sha256,
            "source_collected_at": self.source_collected_at,
        }


@dataclass(frozen=True)
class EvidenceLocation:
    """Exact source artifact and JSON Pointer for one side of a change."""

    source_generation: str
    artifact_path: str
    json_pointer: str

    def as_dict(self) -> dict[str, str]:
        return {
            "source_generation": self.source_generation,
            "artifact_path": self.artifact_path,
            "json_pointer": self.json_pointer,
        }


@dataclass(frozen=True)
class DeltaChange:
    """One semantic addition, removal, or value change."""

    kind: ChangeKind
    scope: tuple[tuple[str, str], ...]
    path: str
    before: JsonValue | object
    after: JsonValue | object
    before_evidence: EvidenceLocation | None
    after_evidence: EvidenceLocation | None

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "scope": dict(self.scope),
            "path": self.path,
            "before": _value_state(self.before),
            "after": _value_state(self.after),
            "before_evidence": (
                self.before_evidence.as_dict()
                if self.before_evidence is not None
                else None
            ),
            "after_evidence": (
                self.after_evidence.as_dict()
                if self.after_evidence is not None
                else None
            ),
        }


@dataclass(frozen=True)
class ProcessDelta:
    """Deterministic comparison between the current and previous export source."""

    baseline: SnapshotIdentity | None
    current: SnapshotIdentity
    changes: tuple[DeltaChange, ...]

    @property
    def status(self) -> DeltaStatus:
        if self.baseline is None:
            return "SEM_BASELINE"
        if not self.changes:
            return "SEM_ALTERACOES"
        return "COM_ALTERACOES"

    def as_dict(self) -> dict[str, object]:
        counts = {"added": 0, "removed": 0, "changed": 0}
        for change in self.changes:
            counts[change.kind] += 1
        return {
            "schema_version": DELTA_SCHEMA_VERSION,
            "status": self.status,
            "baseline": self.baseline.as_dict() if self.baseline else None,
            "current": self.current.as_dict(),
            "summary": {**counts, "total": len(self.changes)},
            "changes": [change.as_dict() for change in self.changes],
        }


def build_process_delta(
    current: ProcessExportModel,
    baseline: ProcessExportModel | None,
) -> ProcessDelta:
    """Return the complete semantic delta with exact evidence locations."""

    current_identity = SnapshotIdentity.from_model(current)
    if baseline is None:
        return ProcessDelta(None, current_identity, ())

    changes: list[DeltaChange] = []
    _compare_family(
        changes,
        scope=(('kind', 'process'),),
        before=baseline.process,
        after=current.process,
        before_generation=baseline.source_generation,
        after_generation=current.source_generation,
    )
    _compare_family(
        changes,
        scope=(('kind', 'global_behaviors'),),
        before=baseline.behaviors,
        after=current.behaviors,
        before_generation=baseline.source_generation,
        after_generation=current.source_generation,
    )

    previous_types = {item.reference_name: item for item in baseline.work_item_types}
    current_types = {item.reference_name: item for item in current.work_item_types}
    for reference_name in sorted(previous_types.keys() | current_types.keys()):
        _compare_work_item_type(
            changes,
            reference_name,
            previous_types.get(reference_name),
            current_types.get(reference_name),
            baseline.source_generation,
            current.source_generation,
        )
    return ProcessDelta(
        SnapshotIdentity.from_model(baseline),
        current_identity,
        tuple(changes),
    )


def baseline_identity_from_delta(
    payload: dict[str, object],
    *,
    expected_current: SnapshotIdentity,
) -> SnapshotIdentity | None:
    """Read the baseline identity from a previously generated delta."""

    if set(payload) != {
        "schema_version", "status", "baseline", "current", "summary", "changes"
    } or payload.get("schema_version") != DELTA_SCHEMA_VERSION:
        raise ValueError("previous delta schema is invalid")
    current = _parse_identity(payload.get("current"))
    if current != expected_current:
        raise ValueError("previous delta current source does not match provenance")
    baseline_payload = payload.get("baseline")
    if baseline_payload is None:
        if payload.get("status") != "SEM_BASELINE":
            raise ValueError("previous delta baseline status is invalid")
        return None
    if payload.get("status") not in {"SEM_ALTERACOES", "COM_ALTERACOES"}:
        raise ValueError("previous delta baseline status is invalid")
    return _parse_identity(baseline_payload)


def _compare_work_item_type(
    changes: list[DeltaChange],
    reference_name: str,
    before: WorkItemTypeModel | None,
    after: WorkItemTypeModel | None,
    before_generation: str,
    after_generation: str,
) -> None:
    metadata_scope = (
        ("kind", "work_item_type"),
        ("reference_name", reference_name),
        ("family", "metadata"),
    )
    _compare_values(
        changes,
        metadata_scope,
        before.metadata if before else _MISSING,
        after.metadata if after else _MISSING,
        before_generation,
        after_generation,
        before.metadata_source_path if before else None,
        after.metadata_source_path if after else None,
        before.metadata_json_pointer if before else "",
        after.metadata_json_pointer if after else "",
        (),
        (),
        (),
    )
    before_families = {family.name: family for family in before.families} if before else {}
    after_families = {family.name: family for family in after.families} if after else {}
    ordered_names = tuple(before_families) + tuple(
        name for name in after_families if name not in before_families
    )
    for name in ordered_names:
        _compare_family(
            changes,
            scope=(
                ("kind", "work_item_type"),
                ("reference_name", reference_name),
                ("family", name),
            ),
            before=before_families.get(name),
            after=after_families.get(name),
            before_generation=before_generation,
            after_generation=after_generation,
        )


def _compare_family(
    changes: list[DeltaChange],
    *,
    scope: tuple[tuple[str, str], ...],
    before: EvidenceFamily | None,
    after: EvidenceFamily | None,
    before_generation: str,
    after_generation: str,
) -> None:
    _compare_values(
        changes,
        scope,
        before.value if before else _MISSING,
        after.value if after else _MISSING,
        before_generation,
        after_generation,
        before.source_path if before else None,
        after.source_path if after else None,
        before.json_pointer if before else "",
        after.json_pointer if after else "",
        (),
        (),
        (),
    )
    _compare_values(
        changes,
        scope,
        before.additional_properties if before and before.additional_properties else _MISSING,
        after.additional_properties if after and after.additional_properties else _MISSING,
        before_generation,
        after_generation,
        before.source_path if before else None,
        after.source_path if after else None,
        before.additional_properties_json_pointer if before else "",
        after.additional_properties_json_pointer if after else "",
        (),
        (),
        (),
    )


def _compare_values(
    changes: list[DeltaChange],
    scope: tuple[tuple[str, str], ...],
    before: JsonValue | object,
    after: JsonValue | object,
    before_generation: str,
    after_generation: str,
    before_artifact: str | None,
    after_artifact: str | None,
    before_base_pointer: str | None,
    after_base_pointer: str | None,
    logical_segments: tuple[str, ...],
    before_segments: tuple[str, ...],
    after_segments: tuple[str, ...],
) -> None:
    if before is _MISSING and after is _MISSING:
        return
    if before is _MISSING or after is _MISSING:
        _append_change(
            changes,
            scope,
            before,
            after,
            before_generation,
            after_generation,
            before_artifact,
            after_artifact,
            before_base_pointer,
            after_base_pointer,
            logical_segments,
            before_segments,
            after_segments,
        )
        return
    if isinstance(before, JsonObject) and isinstance(after, JsonObject):
        before_properties = _logical_properties(before)
        after_properties = _logical_properties(after)
        ordered_keys = tuple(before_properties) + tuple(
            key for key in after_properties if key not in before_properties
        )
        for key in ordered_keys:
            before_entry = before_properties.get(key)
            after_entry = after_properties.get(key)
            _compare_values(
                changes,
                scope,
                before_entry[0] if before_entry else _MISSING,
                after_entry[0] if after_entry else _MISSING,
                before_generation,
                after_generation,
                before_artifact,
                after_artifact,
                before_base_pointer,
                after_base_pointer,
                logical_segments + (key,),
                before_segments + (before_entry[1] if before_entry else key,),
                after_segments + (after_entry[1] if after_entry else key,),
            )
        return
    if isinstance(before, JsonArray) and isinstance(after, JsonArray):
        for index in range(max(len(before.items), len(after.items))):
            segment = str(index)
            _compare_values(
                changes,
                scope,
                before.items[index] if index < len(before.items) else _MISSING,
                after.items[index] if index < len(after.items) else _MISSING,
                before_generation,
                after_generation,
                before_artifact,
                after_artifact,
                before_base_pointer,
                after_base_pointer,
                logical_segments + (segment,),
                before_segments + (segment,),
                after_segments + (segment,),
            )
        return
    if _json_equal(before, after):
        return
    _append_change(
        changes,
        scope,
        before,
        after,
        before_generation,
        after_generation,
        before_artifact,
        after_artifact,
        before_base_pointer,
        after_base_pointer,
        logical_segments,
        before_segments,
        after_segments,
    )


def _append_change(
    changes: list[DeltaChange],
    scope: tuple[tuple[str, str], ...],
    before: JsonValue | object,
    after: JsonValue | object,
    before_generation: str,
    after_generation: str,
    before_artifact: str | None,
    after_artifact: str | None,
    before_base_pointer: str | None,
    after_base_pointer: str | None,
    logical_segments: tuple[str, ...],
    before_segments: tuple[str, ...],
    after_segments: tuple[str, ...],
) -> None:
    kind: ChangeKind
    if before is _MISSING:
        kind = "added"
    elif after is _MISSING:
        kind = "removed"
    else:
        kind = "changed"
    changes.append(
        DeltaChange(
            kind=kind,
            scope=scope,
            path=_join_pointer("", logical_segments),
            before=before,
            after=after,
            before_evidence=_evidence(
                before,
                before_generation,
                before_artifact,
                before_base_pointer,
                before_segments,
            ),
            after_evidence=_evidence(
                after,
                after_generation,
                after_artifact,
                after_base_pointer,
                after_segments,
            ),
        )
    )


def _logical_properties(value: JsonObject) -> dict[str, tuple[JsonValue, str]]:
    result: dict[str, tuple[JsonValue, str]] = {}
    for key, item in value.properties:
        if key in value.synthetic_properties and isinstance(item, JsonObject):
            for nested_key, nested in _logical_properties(item).items():
                result[nested_key] = nested
            continue
        result[key] = (item, key)
    return result


def _evidence(
    value: JsonValue | object,
    generation: str,
    artifact: str | None,
    base_pointer: str | None,
    segments: tuple[str, ...],
) -> EvidenceLocation | None:
    if value is _MISSING or artifact is None:
        return None
    return EvidenceLocation(
        generation,
        artifact,
        _join_pointer(base_pointer or "", segments),
    )


def _join_pointer(base: str, segments: tuple[str, ...]) -> str:
    suffix = "".join(f"/{_pointer_escape(segment)}" for segment in segments)
    return f"{base}{suffix}"


def _pointer_escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _json_equal(before: object, after: object) -> bool:
    if type(before) is not type(after):
        return False
    return before == after


def _value_state(value: JsonValue | object) -> dict[str, object]:
    if value is _MISSING:
        return {"present": False}
    return {"present": True, "value": to_builtin(value)}  # type: ignore[arg-type]


def _parse_identity(value: object) -> SnapshotIdentity:
    if not isinstance(value, dict) or set(value) != {
        "source_generation", "source_manifest_sha256", "source_collected_at"
    }:
        raise ValueError("snapshot identity is invalid")
    generation = value.get("source_generation")
    digest = value.get("source_manifest_sha256")
    collected_at = value.get("source_collected_at")
    if not all(
        isinstance(item, str) and item
        for item in (generation, digest, collected_at)
    ):
        raise ValueError("snapshot identity is invalid")
    return SnapshotIdentity(generation, digest, collected_at)
