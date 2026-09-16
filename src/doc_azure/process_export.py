"""Build and atomically publish a deterministic process-only LLM export."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from doc_azure.process_collector import (
    ARTIFACT_KINDS,
    MAPPING_ARTIFACT_PATH,
    ProcessCollectionError,
    read_validated_process_manifest,
)
from doc_azure.process_export_render import (
    EvidenceFamily,
    JsonArray,
    JsonObject,
    JsonValue,
    ProcessExportModel,
    WorkItemTypeModel,
    freeze_json,
    render_bundle,
    render_export_readme,
    render_process_summary,
    render_work_item_type,
)
from doc_azure.process_export_delta import (
    ProcessDelta,
    SnapshotIdentity,
    baseline_identity_from_delta,
    build_process_delta,
)
from doc_azure.process_export_delta_render import (
    render_delta_bundle_section,
    render_delta_json,
    render_delta_markdown,
)
from doc_azure.snapshot import (
    SnapshotError,
    SnapshotWriter,
    read_snapshot_artifact,
    read_snapshot_manifest_with_sha256,
    resolve_snapshot_root,
    select_snapshot_generation,
)


EXPORT_SCHEMA_VERSION = 1
EXPORT_ROOT = Path("out/process-llm")
PROVENANCE_KEYS = frozenset(
    {
        "schema_version",
        "source_generation",
        "source_manifest_sha256",
        "source_collected_at",
        "process_id",
        "process_name",
        "scope",
        "omitted_properties",
        "work_item_type_counts",
    }
)


class ProcessExportError(RuntimeError):
    """Raised when a process export cannot be validated or published safely."""


@dataclass(frozen=True)
class ProcessExportResult:
    """Paths and identity for one successful process export."""

    generation_root: Path
    bundle_path: Path
    delta_markdown_path: Path
    delta_json_path: Path
    work_item_types_root: Path
    source_generation: str
    reused: bool


_KNOWN_BY_FAMILY = {
    "fields": frozenset(
        {
            "referenceName", "name", "type", "description", "required",
            "defaultValue", "allowGroups", "customization", "readOnly",
            "identity", "pickList", "url", "order",
        }
    ),
    "states": frozenset(
        {
            "id", "name", "color", "stateCategory", "order",
            "customizationType", "hidden", "url",
        }
    ),
    "rules": frozenset(
        {
            "id", "name", "conditions", "actions", "isDisabled",
            "customizationType", "url",
        }
    ),
    "behaviors": frozenset(
        {"behavior", "isDefault", "isLegacyDefault", "url", "order"}
    ),
}
_KNOWN_PROCESS = frozenset(
    {
        "typeId", "name", "description", "customizationType",
        "parentProcessTypeId", "isEnabled", "isDefault", "url",
    }
)
_KNOWN_WIT = frozenset(
    {
        "name", "referenceName", "description", "color", "icon",
        "isDisabled", "customization", "url", "inherits",
    }
)
_KNOWN_GLOBAL_BEHAVIOR = frozenset(
    {"referenceName", "name", "rank", "color", "inherits", "url"}
)
_KNOWN_NESTED = frozenset(
    {
        "actionType", "actions", "behavior", "behaviorRefName", "color",
        "conditionType", "conditions", "controlType", "controls",
        "customization", "customizationType", "defaultValue", "description",
        "field", "groups", "hidden", "icon", "id", "inherits",
        "isContribution", "isDefault", "isDisabled", "isEnabled",
        "isLegacyDefault", "isLocked", "label", "layout", "locked", "name",
        "order", "overridden", "pageType", "pages", "parentProcessTypeId",
        "rank", "readOnly", "referenceName", "required", "sections",
        "stateCategory", "systemControls", "targetField", "type", "typeId",
        "url", "value", "visible", "watermark",
    }
)


def export_process_for_llm(root: Path) -> ProcessExportResult:
    """Export the fixed generation selected by ``out/process/CURRENT``."""

    project_root = Path(root)
    logical_source = project_root / "out" / "process"
    if not os.path.lexists(logical_source / "CURRENT"):
        raise ProcessExportError("process snapshot CURRENT is missing")
    try:
        source_root = resolve_snapshot_root(logical_source)
        source_manifest = read_validated_process_manifest(source_root)
        _, source_manifest_sha256 = read_snapshot_manifest_with_sha256(source_root)
        model, process_id, process_name = _load_model(
            source_root,
            source_manifest_sha256=source_manifest_sha256,
            source_collected_at=source_manifest.collected_at,
        )
    except (SnapshotError, ProcessCollectionError, ValueError, TypeError) as error:
        raise ProcessExportError(f"process snapshot validation failed: {error}") from None

    provenance = _provenance(
        model,
        source_generation=source_root.name,
        source_manifest_sha256=source_manifest_sha256,
        source_collected_at=source_manifest.collected_at,
        process_id=process_id,
        process_name=process_name,
    )
    export_root = project_root / EXPORT_ROOT
    baseline_export_generation = _selected_generation(export_root)
    baseline_model = _load_previous_model(
        project_root,
        export_root,
        baseline_export_generation,
        current_identity=SnapshotIdentity.from_model(model),
    )
    delta = build_process_delta(model, baseline_model)
    rendered_artifacts = _render_artifacts(model, provenance, delta)
    if _selected_generation(export_root) != baseline_export_generation:
        raise ProcessExportError(
            "concurrent export published a different process source"
        )
    existing = _find_reusable_export(export_root, provenance, rendered_artifacts)
    if existing is not None:
        return _result(existing, source_root.name, reused=True)

    writer = SnapshotWriter(export_root)
    concurrent = _matching_current_export(
        export_root, provenance, rendered_artifacts
    )
    if concurrent is not None:
        writer.abort()
        return _result(concurrent, source_root.name, reused=True)
    if _selected_generation(export_root) != baseline_export_generation:
        writer.abort()
        raise ProcessExportError(
            "concurrent export published a different process source"
        )
    try:
        for path, content in rendered_artifacts.items():
            writer.write_text(path, content)
        writer.commit_manifest(collected_at=source_manifest.collected_at, requests=())
    except BaseException as error:
        writer.abort()
        if isinstance(error, SnapshotError) and "stale snapshot writer" in str(error):
            winner = _matching_current_export(
                export_root, provenance, rendered_artifacts
            )
            if winner is not None:
                return _result(winner, source_root.name, reused=True)
            raise ProcessExportError(
                "concurrent export published a different process source"
            ) from None
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        raise ProcessExportError(f"export write failure: {error}") from None

    published = _matching_current_export(
        export_root, provenance, rendered_artifacts
    )
    if published is None:
        raise ProcessExportError(
            "concurrent export published a different process source"
        )
    return _result(published, source_root.name, reused=False)


def _load_model(
    source_root: Path,
    *,
    source_manifest_sha256: str,
    source_collected_at: str,
) -> tuple[ProcessExportModel, str, str]:
    process_payload = _read_json(source_root, "process.json")
    process_id = _required_string(process_payload, "typeId", "process ID")
    process_name = _required_string(process_payload, "name", "process name")
    mapping = _read_json(source_root, MAPPING_ARTIFACT_PATH)
    index = _read_json(source_root, "workitemtypes.json")
    index_values = _envelope_values(index, "work item type index")
    index_by_reference = {
        _required_string(entry, "referenceName", "work item referenceName"):
        (position, entry)
        for position, entry in enumerate(index_values)
    }

    mapped_types = mapping.get("work_item_types")
    if not isinstance(mapped_types, list):
        raise ProcessExportError("process artifact map is malformed")
    work_item_types: list[WorkItemTypeModel] = []
    for mapped in mapped_types:
        if not isinstance(mapped, dict):
            raise ProcessExportError("process artifact map is malformed")
        reference_name = _required_string(mapped, "reference_name", "referenceName")
        if reference_name not in index_by_reference:
            raise ProcessExportError("process artifact map and index differ")
        position, metadata_payload = index_by_reference[reference_name]
        artifacts = mapped.get("artifacts")
        if not isinstance(artifacts, dict):
            raise ProcessExportError("work item artifact map is malformed")
        families = tuple(
            _load_family(source_root, family, _required_path(artifacts, family))
            for family in ARTIFACT_KINDS
        )
        work_item_types.append(
            WorkItemTypeModel(
                name=_required_string(mapped, "name", "work item name"),
                reference_name=reference_name,
                customization=_required_string(mapped, "customization", "customization"),
                is_disabled=_required_bool(mapped, "is_disabled", "disabled state"),
                metadata=_semantic_object(metadata_payload, _KNOWN_WIT),
                metadata_source_path="workitemtypes.json",
                metadata_json_pointer=f"/value/{position}",
                families=families,
            )
        )
    work_item_types.sort(key=lambda item: item.reference_name)

    behaviors_payload = _read_json(source_root, "behaviors.json")
    behavior_values, behavior_extra = _reduce_envelope(
        behaviors_payload, "process behaviors", known=_KNOWN_GLOBAL_BEHAVIOR
    )
    model = ProcessExportModel(
        process=EvidenceFamily(
            "process",
            "process.json",
            "",
            _semantic_object(process_payload, _KNOWN_PROCESS),
        ),
        behaviors=EvidenceFamily(
            "behaviors",
            "behaviors.json",
            "/value",
            behavior_values,
            behavior_extra,
            "",
        ),
        work_item_types=tuple(work_item_types),
        source_generation=source_root.name,
        source_manifest_sha256=source_manifest_sha256,
        source_collected_at=source_collected_at,
    )
    return model, process_id, process_name


def _load_family(source_root: Path, name: str, path: str) -> EvidenceFamily:
    payload = _read_json(source_root, path)
    if name == "layout":
        layout = payload.get("layout")
        if not isinstance(layout, dict):
            raise ProcessExportError("layout artifact is invalid")
        outer = {
            key: value
            for key, value in payload.items()
            if key not in {"layout", "url"}
        }
        return EvidenceFamily(
            name,
            path,
            "/layout",
            _semantic_object(layout, frozenset({"pages"})),
            _semantic_object(outer, frozenset()) if outer else None,
            "",
        )
    values, extra = _reduce_envelope(
        payload, name, known=_KNOWN_BY_FAMILY[name]
    )
    return EvidenceFamily(name, path, "/value", values, extra, "")


def _reduce_envelope(
    payload: dict[str, object], label: str, *, known: frozenset[str]
) -> tuple[JsonArray, JsonObject | None]:
    values = _envelope_values(payload, label)
    normalized = tuple(_semantic_object(entry, known) for entry in values)
    envelope_extra = {
        key: value for key, value in payload.items() if key not in {"count", "value", "url"}
    }
    extra = _semantic_object(envelope_extra, frozenset()) if envelope_extra else None
    return JsonArray(normalized), extra


def _semantic_object(payload: dict[str, object], known: frozenset[str]) -> JsonObject:
    value = _require_object(freeze_json(payload))
    primary = tuple(
        (key, _normalize_nested(item))
        for key, item in value.properties
        if key in known and key != "url"
    )
    additional = tuple(
        (key, _normalize_nested(item))
        for key, item in value.properties
        if key not in known and key != "url"
    )
    if additional:
        primary += (("additional_properties", JsonObject(additional)),)
    return JsonObject(
        primary,
        frozenset({"additional_properties"}) if additional else frozenset(),
    )


def _normalize_nested(value: JsonValue) -> JsonValue:
    if isinstance(value, JsonArray):
        return JsonArray(tuple(_normalize_nested(item) for item in value.items))
    if not isinstance(value, JsonObject):
        return value
    primary = tuple(
        (key, _normalize_nested(item))
        for key, item in value.properties
        if key in _KNOWN_NESTED and key != "url"
    )
    additional = tuple(
        (key, _normalize_nested(item))
        for key, item in value.properties
        if key not in _KNOWN_NESTED and key != "url"
    )
    if additional:
        primary += (("additional_properties", JsonObject(additional)),)
    return JsonObject(
        primary,
        frozenset({"additional_properties"}) if additional else frozenset(),
    )


def _provenance(
    model: ProcessExportModel,
    *,
    source_generation: str,
    source_manifest_sha256: str,
    source_collected_at: str,
    process_id: str,
    process_name: str,
) -> dict[str, object]:
    disabled = sum(wit.is_disabled for wit in model.work_item_types)
    total = len(model.work_item_types)
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "source_generation": source_generation,
        "source_manifest_sha256": source_manifest_sha256,
        "source_collected_at": source_collected_at,
        "process_id": process_id,
        "process_name": process_name,
        "scope": "process-only",
        "omitted_properties": ["url"],
        "work_item_type_counts": {
            "total": total,
            "active": total - disabled,
            "disabled": disabled,
        },
    }


def _render_artifacts(
    model: ProcessExportModel,
    provenance: dict[str, object],
    delta: ProcessDelta,
) -> dict[str, str]:
    bundle = (
        render_bundle(model).rstrip()
        + "\n\n"
        + render_delta_bundle_section(delta)
    )
    artifacts = {
        "README.md": render_export_readme(),
        "bundle.md": bundle,
        "delta.json": render_delta_json(delta),
        "delta.md": render_delta_markdown(delta),
        "process-summary.md": render_process_summary(model),
        "provenance.json": json.dumps(
            provenance,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
    }
    artifacts.update(
        {
            f"work-item-types/{wit.reference_name}.md": render_work_item_type(wit)
            for wit in model.work_item_types
        }
    )
    return artifacts


def _find_reusable_export(
    root: Path,
    provenance: dict[str, object],
    expected_artifacts: dict[str, str],
) -> Path | None:
    if not os.path.lexists(root):
        return None
    current: Path | None = None
    expected_generation: str | None = None
    if os.path.lexists(root / "CURRENT"):
        try:
            current = resolve_snapshot_root(root)
        except SnapshotError:
            return None
        expected_generation = current.name
        if _matching_generation(current, provenance, expected_artifacts):
            return current
    elif os.path.lexists(root / "manifest.json"):
        return None

    snapshots_root = root / "snapshots"
    try:
        candidates = sorted(
            (
                candidate
                for candidate in snapshots_root.iterdir()
                if current is None or candidate.name != current.name
            ),
            key=lambda candidate: candidate.name,
        )
    except OSError:
        return None
    for candidate in candidates:
        if not _matching_generation(candidate, provenance, expected_artifacts):
            continue
        try:
            return select_snapshot_generation(
                root,
                candidate.name,
                expected_generation=expected_generation,
                validator=lambda target: _matching_generation(
                    target, provenance, expected_artifacts
                ),
            )
        except SnapshotError as error:
            winner = _matching_current_export(root, provenance, expected_artifacts)
            if winner is not None:
                return winner
            if str(error) == "snapshot generation failed selection validation":
                raise ProcessExportError(
                    "historical export changed during locked validation"
                ) from None
            raise ProcessExportError(
                "concurrent export published a different process source"
            ) from None
    return None


def _matching_current_export(
    root: Path,
    provenance: dict[str, object],
    expected_artifacts: dict[str, str],
) -> Path | None:
    try:
        current = resolve_snapshot_root(root)
    except SnapshotError:
        return None
    return (
        current
        if _matching_generation(current, provenance, expected_artifacts)
        else None
    )


def _selected_generation(root: Path) -> str | None:
    if not os.path.lexists(root / "CURRENT"):
        return None
    try:
        return resolve_snapshot_root(root).name
    except SnapshotError as error:
        raise ProcessExportError(f"export CURRENT is invalid: {error}") from None


def _matching_generation(
    generation: Path,
    provenance: dict[str, object],
    expected_artifacts: dict[str, str],
) -> bool:
    try:
        payload = _read_json(generation, "provenance.json")
        if set(payload) != PROVENANCE_KEYS or payload != provenance:
            return False
        manifest, _ = read_snapshot_manifest_with_sha256(generation)
        if {artifact.path for artifact in manifest.artifacts} != set(
            expected_artifacts
        ):
            return False
        return all(
            read_snapshot_artifact(generation, path) == content.encode("utf-8")
            for path, content in expected_artifacts.items()
        )
    except (SnapshotError, ProcessExportError, ValueError, TypeError, KeyError):
        return False


def _result(root: Path, source_generation: str, *, reused: bool) -> ProcessExportResult:
    return ProcessExportResult(
        generation_root=root.resolve(),
        bundle_path=(root / "bundle.md").resolve(),
        delta_markdown_path=(root / "delta.md").resolve(),
        delta_json_path=(root / "delta.json").resolve(),
        work_item_types_root=(root / "work-item-types").resolve(),
        source_generation=source_generation,
        reused=reused,
    )


def _load_previous_model(
    project_root: Path,
    export_root: Path,
    selected_export_generation: str | None,
    *,
    current_identity: SnapshotIdentity,
) -> ProcessExportModel | None:
    if selected_export_generation is None:
        return None
    selected_export = export_root / "snapshots" / selected_export_generation
    try:
        provenance = _read_json(selected_export, "provenance.json")
        previous_current = _identity_from_provenance(provenance)
        baseline_identity = previous_current
        if previous_current == current_identity:
            baseline_identity = _prior_identity_for_same_source(
                selected_export,
                previous_current,
            )
        if baseline_identity is None:
            return None
        return _load_model_for_identity(project_root, baseline_identity)
    except (SnapshotError, ProcessCollectionError, ValueError, TypeError) as error:
        raise ProcessExportError(f"previous export baseline is invalid: {error}") from None


def _prior_identity_for_same_source(
    selected_export: Path,
    current_identity: SnapshotIdentity,
) -> SnapshotIdentity | None:
    try:
        payload = _read_json(selected_export, "delta.json")
    except ProcessExportError as error:
        if "is invalid" in str(error):
            return current_identity
        raise
    return baseline_identity_from_delta(
        payload,
        expected_current=current_identity,
    )


def _identity_from_provenance(payload: dict[str, object]) -> SnapshotIdentity:
    if set(payload) != PROVENANCE_KEYS:
        raise ValueError("previous export provenance schema is invalid")
    generation = payload.get("source_generation")
    digest = payload.get("source_manifest_sha256")
    collected_at = payload.get("source_collected_at")
    if not all(
        isinstance(item, str) and item
        for item in (generation, digest, collected_at)
    ):
        raise ValueError("previous export provenance identity is invalid")
    return SnapshotIdentity(generation, digest, collected_at)


def _load_model_for_identity(
    project_root: Path,
    identity: SnapshotIdentity,
) -> ProcessExportModel:
    if (
        len(identity.source_generation) != 32
        or any(
            character not in "0123456789abcdef"
            for character in identity.source_generation
        )
    ):
        raise ValueError("previous source generation is invalid")
    source_root = (
        project_root
        / "out"
        / "process"
        / "snapshots"
        / identity.source_generation
    )
    manifest = read_validated_process_manifest(source_root)
    _, digest = read_snapshot_manifest_with_sha256(source_root)
    if (
        digest != identity.source_manifest_sha256
        or manifest.collected_at != identity.source_collected_at
    ):
        raise ValueError("previous source identity does not match its manifest")
    model, _, _ = _load_model(
        source_root,
        source_manifest_sha256=digest,
        source_collected_at=manifest.collected_at,
    )
    return model


def _read_json(root: Path, path: str) -> dict[str, object]:
    try:
        payload = json.loads(read_snapshot_artifact(root, path).decode("utf-8"))
    except (SnapshotError, UnicodeError, ValueError):
        raise ProcessExportError(f"process artifact {path} is invalid") from None
    if not isinstance(payload, dict):
        raise ProcessExportError(f"process artifact {path} is invalid")
    return payload


def _envelope_values(payload: dict[str, object], label: str) -> list[dict[str, object]]:
    values = payload.get("value")
    count = payload.get("count")
    if (
        not isinstance(values, list)
        or type(count) is not int
        or count != len(values)
        or any(not isinstance(item, dict) for item in values)
    ):
        raise ProcessExportError(f"{label} envelope is invalid")
    return values


def _required_string(payload: dict[str, object], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ProcessExportError(f"{label} is invalid")
    return value


def _required_bool(payload: dict[str, object], key: str, label: str) -> bool:
    value = payload.get(key)
    if type(value) is not bool:
        raise ProcessExportError(f"{label} is invalid")
    return value


def _required_path(payload: dict[str, object], key: str) -> str:
    return _required_string(payload, key, f"{key} artifact path")


def _require_object(value: JsonValue) -> JsonObject:
    if not isinstance(value, JsonObject):
        raise ProcessExportError("expected a JSON object")
    return value
