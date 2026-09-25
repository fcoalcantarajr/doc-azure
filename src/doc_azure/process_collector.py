"""Collect a complete inherited-process definition into an atomic snapshot."""

from __future__ import annotations

import asyncio
import json
import os
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from doc_azure.azure_client import (
    AzureReadClient,
    AzureReadError,
    RequestRecord,
    is_allowlisted_read,
)
from doc_azure.snapshot import (
    SnapshotManifest,
    SnapshotWriter,
    read_snapshot_artifact,
    read_snapshot_manifest,
    resolve_snapshot_root,
)


PROCESS_NAME = "Processo-Agil"
GLOBAL_ARTIFACT_PATHS = (
    "processes.json",
    "process.json",
    "workitemtypes.json",
    "behaviors.json",
)
MAPPING_ARTIFACT_PATH = "artifact-map.json"
ARTIFACT_KINDS = ("fields", "states", "rules", "layout", "behaviors")
MAPPING_SCHEMA_VERSION = 2


class ProcessCollectionError(RuntimeError):
    """Raised when process evidence is missing, ambiguous, or malformed."""


class ProcessArtifactError(ProcessCollectionError):
    """Raised when one named evidence family cannot be collected safely."""


class _IncompleteSnapshot(ProcessCollectionError):
    """Internal signal for a valid but non-current process snapshot schema."""


@dataclass(frozen=True)
class WorkItemType:
    """The complete identity and enabled state needed for evidence planning."""

    name: str
    reference_name: str
    customization: str
    is_disabled: bool


@dataclass(frozen=True)
class ArtifactRequest:
    """One deterministic per-WIT evidence artifact and its modern REST route."""

    kind: str
    work_item_type_name: str
    reference_name: str
    artifact_path: str

    def api_path(self, process_id: str) -> str:
        """Return the exact Azure DevOps 7.1 route for this artifact."""

        _validate_process_id(process_id)
        if self.kind == "layout":
            return (
                f"/_apis/work/processes/{process_id}/workitemtypes/"
                f"{self.reference_name}"
            )
        if self.kind == "behaviors":
            return (
                f"/_apis/work/processes/{process_id}/workitemtypesbehaviors/"
                f"{self.reference_name}/behaviors"
            )
        return (
            f"/_apis/work/processes/{process_id}/workitemtypes/"
            f"{self.reference_name}/{self.kind}"
        )

    def api_query(self) -> dict[str, object] | None:
        """Return the read-only query required by this evidence family."""

        if self.kind == "layout":
            return {"$expand": "layout"}
        return None


@dataclass(frozen=True)
class ProcessCollectionPlan:
    """A stable, collision-free plan derived from the full raw WIT index."""

    work_item_types: tuple[WorkItemType, ...]
    requests: tuple[ArtifactRequest, ...]

    @classmethod
    def from_index(
        cls, index_payload: Mapping[str, object]
    ) -> ProcessCollectionPlan:
        """Validate the index and request all five families for every WIT."""

        entries = _validate_envelope(index_payload, "work item type index")
        work_item_types = tuple(
            sorted(
                (_parse_work_item_type(entry) for entry in entries),
                key=lambda wit: (wit.reference_name.casefold(), wit.reference_name),
            )
        )
        _validate_unique_work_item_types(work_item_types)
        requests = tuple(
            ArtifactRequest(
                kind=kind,
                work_item_type_name=work_item_type.name,
                reference_name=work_item_type.reference_name,
                artifact_path=(
                    f"workitemtypes/{work_item_type.reference_name}/{kind}.json"
                ),
            )
            for work_item_type in work_item_types
            for kind in ARTIFACT_KINDS
        )
        if len({request.artifact_path.casefold() for request in requests}) != len(
            requests
        ):
            raise ProcessCollectionError(
                "work item referenceName values collide as artifact filenames"
            )
        return cls(work_item_types=work_item_types, requests=requests)

    def requests_for(self, work_item_type_name: str) -> tuple[ArtifactRequest, ...]:
        """Return all evidence requests for one exact display name."""

        return tuple(
            request
            for request in self.requests
            if request.work_item_type_name == work_item_type_name
        )

    def mapping_payload(self, process_id: str) -> dict[str, object]:
        """Return the versioned reference-name-to-artifact mapping."""

        _validate_process_id(process_id)
        return {
            "schema_version": MAPPING_SCHEMA_VERSION,
            "process_name": PROCESS_NAME,
            "process_id": process_id,
            "globals": {
                "processes": "processes.json",
                "process": "process.json",
                "work_item_types": "workitemtypes.json",
                "process_behaviors": "behaviors.json",
            },
            "work_item_types": [
                {
                    "name": work_item_type.name,
                    "reference_name": work_item_type.reference_name,
                    "customization": work_item_type.customization,
                    "is_disabled": work_item_type.is_disabled,
                    "artifacts": {
                        request.kind: request.artifact_path
                        for request in self.requests
                        if request.reference_name == work_item_type.reference_name
                    },
                }
                for work_item_type in self.work_item_types
            ],
        }


@dataclass(frozen=True)
class _SnapshotState:
    resolved_root: Path
    manifest: SnapshotManifest
    artifact_paths: frozenset[str]

    def has(self, relative_path: str) -> bool:
        return relative_path in self.artifact_paths

    def read_text(self, relative_path: str) -> str:
        try:
            return read_snapshot_artifact(
                self.resolved_root,
                relative_path,
            ).decode("utf-8")
        except (OSError, UnicodeError):
            raise ProcessCollectionError(
                f"cached process artifact {relative_path} is unreadable"
            ) from None

    def read_json(self, relative_path: str) -> dict[str, object]:
        try:
            payload = json.loads(self.read_text(relative_path))
        except ValueError:
            raise ProcessCollectionError(
                f"cached process artifact {relative_path} is malformed"
            ) from None
        if not isinstance(payload, dict):
            raise ProcessCollectionError(
                f"cached process artifact {relative_path} is malformed"
            )
        return payload

    def seed(self, writer: SnapshotWriter, relative_path: str) -> None:
        writer.write_text(relative_path, self.read_text(relative_path))


def select_process_id(processes_payload: Mapping[str, object]) -> str:
    """Select exactly one exact-name process and return its documented typeId."""

    entries = _validate_envelope(processes_payload, "process list")
    matches = [entry for entry in entries if entry.get("name") == PROCESS_NAME]
    if len(matches) != 1:
        raise ProcessCollectionError(
            f"process list must contain exactly one {PROCESS_NAME!r} entry"
        )
    process_id = matches[0].get("typeId")
    if not isinstance(process_id, str) or not process_id.strip():
        raise ProcessCollectionError("selected process has an invalid typeId")
    _validate_process_id(process_id)
    return process_id


async def collect_process(
    root: Path,
    client: AzureReadClient | None,
    *,
    refresh: bool,
    now: Callable[[], datetime],
) -> SnapshotManifest:
    """Return complete cached evidence or atomically collect missing artifacts."""

    project_root = Path(root)
    if not refresh:
        cached_manifest = read_cached_process_manifest(project_root)
        if cached_manifest is not None:
            return cached_manifest

    logical_root = project_root / "out" / "process"
    writer = SnapshotWriter(logical_root)
    try:
        if not refresh:
            cached_manifest = read_cached_process_manifest(project_root)
            if cached_manifest is not None:
                writer.abort()
                return cached_manifest
        if client is None:
            raise ProcessCollectionError(
                "an Azure read client is required for process collection"
            )

        prior_state = None if refresh else _load_snapshot_state(logical_root)
        first_request = len(client.request_records)

        processes = await _obtain_global_payload(
            writer,
            prior_state,
            client,
            artifact_path="processes.json",
            api_path="/_apis/work/processes",
            validator=lambda payload: select_process_id(payload),
        )
        process_id = select_process_id(processes)

        process = await _obtain_global_payload(
            writer,
            prior_state,
            client,
            artifact_path="process.json",
            api_path=f"/_apis/work/processes/{process_id}",
            validator=lambda payload: _validate_process(payload, process_id),
        )
        _validate_process(process, process_id)

        index = await _obtain_global_payload(
            writer,
            prior_state,
            client,
            artifact_path="workitemtypes.json",
            api_path=f"/_apis/work/processes/{process_id}/workitemtypes",
            validator=ProcessCollectionPlan.from_index,
        )
        plan = ProcessCollectionPlan.from_index(index)

        process_behaviors = await _obtain_global_payload(
            writer,
            prior_state,
            client,
            artifact_path="behaviors.json",
            api_path=f"/_apis/work/processes/{process_id}/behaviors",
            validator=_validate_process_behaviors,
        )
        _validate_process_behaviors(process_behaviors)

        mapping = plan.mapping_payload(process_id)
        prior_mapping_is_current = prior_state is None
        if prior_state is not None and prior_state.has(MAPPING_ARTIFACT_PATH):
            cached_mapping = prior_state.read_json(MAPPING_ARTIFACT_PATH)
            prior_mapping_is_current = cached_mapping == mapping
            if cached_mapping == mapping:
                prior_state.seed(writer, MAPPING_ARTIFACT_PATH)
            else:
                writer.write_json(MAPPING_ARTIFACT_PATH, mapping)
        else:
            writer.write_json(MAPPING_ARTIFACT_PATH, mapping)

        missing_requests: list[ArtifactRequest] = []
        for request in plan.requests:
            can_reuse = (
                request.kind != "layout" or prior_mapping_is_current
            )
            if (
                can_reuse
                and prior_state is not None
                and prior_state.has(request.artifact_path)
            ):
                cached_payload = prior_state.read_json(request.artifact_path)
                if _is_legacy_layout_payload(request, cached_payload):
                    missing_requests.append(request)
                    continue
                _validate_artifact_payload(request, cached_payload)
                prior_state.seed(writer, request.artifact_path)
            else:
                missing_requests.append(request)

        fetched = await _fetch_missing_artifacts(
            writer,
            client,
            tuple(missing_requests),
            process_id,
        )
        if len(fetched) != len(missing_requests):
            raise AssertionError("artifact request and response counts diverged")

        new_requests = client.request_records[first_request:]
        prior_requests = () if prior_state is None else prior_state.manifest.requests
        collection_mode = "cache_assisted"
        if prior_state is None:
            expected_routes = _expected_process_routes(process_id, plan)
            observed_routes = {
                (record.method, record.path) for record in new_requests
            }
            if (
                observed_routes != expected_routes
                or any(
                    not is_allowlisted_read(record.method, record.path)
                    for record in new_requests
                )
            ):
                raise ProcessCollectionError(
                    "fresh process API request route coverage is incomplete"
                )
            collection_mode = "full_api"
        requests = tuple(
            sorted(
                (*prior_requests, *new_requests),
                key=lambda record: (record.path, record.method),
            )
        )
        return writer.commit_manifest(
            collected_at=now(),
            requests=requests,
            collection_mode=collection_mode,
        )
    except BaseException:
        writer.abort()
        raise


def read_cached_process_manifest(root: Path) -> SnapshotManifest | None:
    """Return a fully validated current-schema process snapshot when present."""

    logical_root = Path(root) / "out" / "process"
    state = _load_snapshot_state(logical_root)
    if state is None:
        return None
    try:
        _validate_snapshot_state(state)
        return state.manifest
    except _IncompleteSnapshot:
        return None


def read_validated_process_manifest(snapshot_root: Path) -> SnapshotManifest:
    """Read one fixed process generation and require the complete current schema."""

    state = _load_snapshot_state(Path(snapshot_root))
    if state is None:
        raise ProcessCollectionError("process snapshot is missing")
    try:
        _validate_snapshot_state(state)
    except _IncompleteSnapshot as error:
        raise ProcessCollectionError(str(error)) from None
    return state.manifest


def validate_process_request_routes(snapshot_root: Path) -> SnapshotManifest:
    """Require exact GET receipts for every route in one complete snapshot."""

    manifest = read_validated_process_manifest(snapshot_root)
    resolved_root = resolve_snapshot_root(Path(snapshot_root))
    processes = json.loads(read_snapshot_artifact(resolved_root, "processes.json"))
    process_id = select_process_id(processes)
    index = json.loads(read_snapshot_artifact(resolved_root, "workitemtypes.json"))
    plan = ProcessCollectionPlan.from_index(index)
    expected_routes = _expected_process_routes(process_id, plan)
    observed_routes = {(record.method, record.path) for record in manifest.requests}
    if (
        observed_routes != expected_routes
        or any(
            not is_allowlisted_read(record.method, record.path)
            for record in manifest.requests
        )
    ):
        raise ProcessCollectionError(
            "process API request route coverage is incomplete or unexpected"
        )
    return manifest


def _expected_process_routes(
    process_id: str,
    plan: ProcessCollectionPlan,
) -> set[tuple[str, str]]:
    return {
        ("GET", "/_apis/work/processes"),
        ("GET", f"/_apis/work/processes/{process_id}"),
        ("GET", f"/_apis/work/processes/{process_id}/workitemtypes"),
        ("GET", f"/_apis/work/processes/{process_id}/behaviors"),
        *(
            ("GET", request.api_path(process_id))
            for request in plan.requests
        ),
    }


def _validate_snapshot_state(state: _SnapshotState) -> None:
    processes = _required_json(state, "processes.json")
    process_id = select_process_id(processes)
    _validate_process(_required_json(state, "process.json"), process_id)
    plan = ProcessCollectionPlan.from_index(
        _required_json(state, "workitemtypes.json")
    )
    _validate_process_behaviors(_required_json(state, "behaviors.json"))
    mapping = _required_json(state, MAPPING_ARTIFACT_PATH)
    if mapping != plan.mapping_payload(process_id):
        raise _IncompleteSnapshot("process artifact mapping schema is stale")
    expected_paths = {
        *GLOBAL_ARTIFACT_PATHS,
        MAPPING_ARTIFACT_PATH,
        *(request.artifact_path for request in plan.requests),
    }
    if state.artifact_paths != expected_paths:
        raise _IncompleteSnapshot("process snapshot artifact set is incomplete")
    for request in plan.requests:
        payload = _required_json(state, request.artifact_path)
        if _is_legacy_layout_payload(request, payload):
            raise _IncompleteSnapshot("process layout artifact schema is stale")
        _validate_artifact_payload(request, payload)


async def _obtain_global_payload(
    writer: SnapshotWriter,
    prior_state: _SnapshotState | None,
    client: AzureReadClient,
    *,
    artifact_path: str,
    api_path: str,
    validator: Callable[[Mapping[str, object]], object],
) -> dict[str, object]:
    if prior_state is not None and prior_state.has(artifact_path):
        payload = prior_state.read_json(artifact_path)
        prior_state.seed(writer, artifact_path)
        validator(payload)
        return payload
    try:
        payload = await client.request_json("GET", api_path)
        writer.write_json(artifact_path, payload)
        validator(payload)
    except AzureReadError as error:
        raise ProcessArtifactError(
            f"global {artifact_path} artifact failed: {error}"
        ) from None
    except ProcessCollectionError as error:
        raise ProcessArtifactError(
            f"global {artifact_path} artifact is malformed: {error}"
        ) from None
    return payload


async def _fetch_artifact(
    writer: SnapshotWriter,
    client: AzureReadClient,
    request: ArtifactRequest,
    process_id: str,
) -> dict[str, object]:
    try:
        payload = await client.request_json(
            "GET",
            request.api_path(process_id),
            query=request.api_query(),
        )
        writer.write_json(request.artifact_path, payload)
        _validate_artifact_payload(request, payload)
        return payload
    except AzureReadError as error:
        raise ProcessArtifactError(
            f"{request.kind} artifact failed: {error}"
        ) from None
    except ProcessCollectionError as error:
        raise ProcessArtifactError(
            f"{request.kind} artifact is malformed: {error}"
        ) from None


async def _fetch_missing_artifacts(
    writer: SnapshotWriter,
    client: AzureReadClient,
    requests: tuple[ArtifactRequest, ...],
    process_id: str,
) -> tuple[dict[str, object], ...]:
    """Fetch one family set and settle every task before returning or raising."""

    tasks = tuple(
        asyncio.create_task(_fetch_artifact(writer, client, request, process_id))
        for request in requests
    )
    try:
        return tuple(await asyncio.gather(*tasks))
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


def _load_snapshot_state(logical_root: Path) -> _SnapshotState | None:
    if not os.path.lexists(logical_root):
        return None
    if not (
        os.path.lexists(logical_root / "CURRENT")
        or os.path.lexists(logical_root / "manifest.json")
    ):
        return None
    resolved_root = resolve_snapshot_root(logical_root)
    manifest = read_snapshot_manifest(resolved_root)
    return _SnapshotState(
        resolved_root=resolved_root,
        manifest=manifest,
        artifact_paths=frozenset(artifact.path for artifact in manifest.artifacts),
    )


def _required_json(state: _SnapshotState, relative_path: str) -> dict[str, object]:
    if not state.has(relative_path):
        raise _IncompleteSnapshot(
            f"process snapshot is missing {relative_path}"
        )
    return state.read_json(relative_path)


def _validate_envelope(
    payload: Mapping[str, object], label: str
) -> tuple[dict[str, object], ...]:
    if not isinstance(payload, Mapping):
        raise ProcessCollectionError(f"{label} is malformed")
    count = payload.get("count")
    values = payload.get("value")
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or not isinstance(values, list)
        or count != len(values)
        or any(not isinstance(entry, dict) for entry in values)
    ):
        raise ProcessCollectionError(f"{label} count/value envelope is malformed")
    return tuple(values)


def _parse_work_item_type(entry: Mapping[str, object]) -> WorkItemType:
    name = entry.get("name")
    reference_name = entry.get("referenceName")
    customization = entry.get("customization")
    is_disabled = entry.get("isDisabled")
    if not isinstance(name, str) or not name.strip():
        raise ProcessCollectionError("work item type name is malformed")
    if not isinstance(reference_name, str) or not reference_name.strip():
        raise ProcessCollectionError("work item type referenceName is malformed")
    _validate_route_segment(reference_name, label="work item type referenceName")
    if not isinstance(customization, str) or not customization.strip():
        raise ProcessCollectionError("work item type customization is malformed")
    if type(is_disabled) is not bool:
        raise ProcessCollectionError("work item type isDisabled is malformed")
    return WorkItemType(name, reference_name, customization, is_disabled)


def _validate_unique_work_item_types(
    work_item_types: tuple[WorkItemType, ...],
) -> None:
    reference_keys = [
        unicodedata.normalize("NFC", wit.reference_name).casefold()
        for wit in work_item_types
    ]
    if len(set(reference_keys)) != len(reference_keys):
        raise ProcessCollectionError(
            "work item type referenceName values are not unique"
        )
    name_keys = [wit.name.casefold() for wit in work_item_types]
    if len(set(name_keys)) != len(name_keys):
        raise ProcessCollectionError("work item type names are not unique")


def _validate_route_segment(value: str, *, label: str) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != unicodedata.normalize("NFC", value)
        or value in {".", ".."}
        or any(character in value for character in "/\\%?#")
        or any(unicodedata.category(character) == "Cc" for character in value)
    ):
        raise ProcessCollectionError(f"{label} is not a safe path segment")


def _validate_process_id(value: str) -> None:
    _validate_route_segment(value, label="process typeId")
    try:
        UUID(value)
    except ValueError:
        raise ProcessCollectionError("process typeId is not a UUID") from None


def _validate_process(payload: Mapping[str, object], process_id: str) -> None:
    if payload.get("name") != PROCESS_NAME or payload.get("typeId") != process_id:
        raise ProcessCollectionError("selected process response identity is malformed")


def _validate_process_behaviors(payload: Mapping[str, object]) -> None:
    entries = _validate_envelope(payload, "process behaviors")
    for entry in entries:
        reference_name = entry.get("referenceName")
        rank = entry.get("rank")
        if (
            not isinstance(reference_name, str)
            or not reference_name.strip()
            or not isinstance(rank, int)
            or isinstance(rank, bool)
            or rank < 0
        ):
            raise ProcessCollectionError(
                "process behavior referenceName/rank is malformed"
            )


def _validate_artifact_payload(
    request: ArtifactRequest, payload: Mapping[str, object]
) -> None:
    kind = request.kind
    if kind not in ARTIFACT_KINDS:
        raise ProcessCollectionError("process artifact family is unsupported")
    if kind == "layout":
        if payload.get("referenceName") != request.reference_name:
            raise ProcessCollectionError("layout work item type identity is malformed")
        layout = payload.get("layout")
        if not isinstance(layout, dict):
            raise ProcessCollectionError("expanded layout is malformed")
        _validate_layout(layout)
        return

    entries = _validate_envelope(payload, f"{kind} artifact")
    _validate_unique_artifact_entries(entries, kind)
    if kind == "fields":
        if any(
            not isinstance(entry.get("referenceName"), str)
            or not entry["referenceName"].strip()
            or ("required" in entry and type(entry["required"]) is not bool)
            for entry in entries
        ):
            raise ProcessCollectionError(
                "fields referenceName/required is malformed"
            )
    elif kind == "states":
        if any(
            not isinstance(entry.get("name"), str)
            or not entry["name"].strip()
            or not isinstance(entry.get("stateCategory"), str)
            or not entry["stateCategory"].strip()
            for entry in entries
        ):
            raise ProcessCollectionError("states stateCategory is malformed")
    elif kind == "behaviors":
        if any(
            not isinstance(entry.get("behavior"), dict)
            or not isinstance(entry["behavior"].get("id"), str)
            or not entry["behavior"]["id"].strip()
            or type(entry.get("isDefault")) is not bool
            or (
                "isLegacyDefault" in entry
                and type(entry["isLegacyDefault"]) is not bool
            )
            for entry in entries
        ):
            raise ProcessCollectionError(
                "behavior association booleans or id are malformed"
            )


def _validate_unique_artifact_entries(
    entries: tuple[dict[str, object], ...], kind: str
) -> None:
    """Reject duplicate identities before an evaluator can choose ambiguously."""

    if kind == "fields":
        identities = [entry.get("referenceName") for entry in entries]
    elif kind in {"states", "rules"}:
        identities = [entry.get("id") for entry in entries]
    elif kind == "behaviors":
        identities = [
            entry.get("behavior", {}).get("id")
            if isinstance(entry.get("behavior"), dict)
            else None
            for entry in entries
        ]
    else:
        return
    normalized = [
        unicodedata.normalize("NFC", identity).casefold()
        if isinstance(identity, str)
        else None
        for identity in identities
    ]
    if None in normalized or len(normalized) != len(set(normalized)):
        raise ProcessCollectionError(f"{kind} identifiers are not unique")


def _is_legacy_layout_payload(
    request: ArtifactRequest,
    payload: Mapping[str, object],
) -> bool:
    """Recognize only the prior raw FormLayout-at-root evidence shape."""

    return (
        request.kind == "layout"
        and "pages" in payload
        and "layout" not in payload
        and "referenceName" not in payload
    )


def _validate_layout(payload: Mapping[str, object]) -> None:
    pages = payload.get("pages")
    if not isinstance(pages, list) or any(
        not isinstance(page, dict) for page in pages
    ):
        raise ProcessCollectionError("layout pages are malformed")
    for page in pages:
        sections = page.get("sections")
        if not isinstance(sections, list) or any(
            not isinstance(section, dict) for section in sections
        ):
            raise ProcessCollectionError("layout sections are malformed")
        for section in sections:
            groups = section.get("groups")
            if not isinstance(groups, list) or any(
                not isinstance(group, dict) for group in groups
            ):
                raise ProcessCollectionError("layout groups are malformed")
            for group in groups:
                controls = group.get("controls")
                if not isinstance(controls, list) or any(
                    not isinstance(control, dict) for control in controls
                ):
                    raise ProcessCollectionError("layout controls are malformed")
