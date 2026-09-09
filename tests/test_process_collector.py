from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import httpx
import pytest

import doc_azure.process_collector as process_collector_module
from doc_azure.azure_client import AzureReadClient, AzureReadError, RequestRecord
from doc_azure.process_collector import (
    ARTIFACT_KINDS,
    GLOBAL_ARTIFACT_PATHS,
    MAPPING_SCHEMA_VERSION,
    MAPPING_ARTIFACT_PATH,
    PROCESS_NAME,
    ProcessArtifactError,
    ProcessCollectionError,
    ProcessCollectionPlan,
    WorkItemType,
    collect_process,
    read_cached_process_manifest,
    select_process_id,
)
from doc_azure.settings import Settings
from doc_azure.snapshot import SnapshotError, SnapshotWriter, resolve_snapshot_root


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "audit"
PROCESS_FIXTURE_ROOT = FIXTURE_ROOT / "process"
SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "02_fetch_process.py"
COLLECTED_AT = datetime(2026, 8, 24, 16, 45, tzinfo=timezone.utc)
PROCESS_ID = "9b6f2d8e-8d31-4f26-a781-8e2a9e9a0f47"
EPIC_REFERENCE = "Microsoft.VSTS.WorkItemTypes.Epic"
USER_STORY_REFERENCE = "Custom.UserStory"


def fixed_now() -> datetime:
    return COLLECTED_AT


def fail_if_called() -> datetime:
    raise AssertionError("complete cache evaluated the clock")


def load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def load_index() -> dict[str, object]:
    return load_json(FIXTURE_ROOT / "process-index.json")


def fixture_payloads() -> dict[str, dict[str, object]]:
    index = load_index()
    index_entries = {
        entry["referenceName"]: entry
        for entry in index["value"]
    }
    payloads = {
        "/_apis/work/processes": load_json(
            PROCESS_FIXTURE_ROOT / "processes.json"
        ),
        f"/_apis/work/processes/{PROCESS_ID}": load_json(
            PROCESS_FIXTURE_ROOT / "process.json"
        ),
        f"/_apis/work/processes/{PROCESS_ID}/workitemtypes": index,
        f"/_apis/work/processes/{PROCESS_ID}/behaviors": load_json(
            PROCESS_FIXTURE_ROOT / "process-behaviors.json"
        ),
    }
    fixture_stems = {
        EPIC_REFERENCE: "epic",
        USER_STORY_REFERENCE: "user-story",
    }
    for reference_name, stem in fixture_stems.items():
        for kind in ARTIFACT_KINDS:
            fixture_path = PROCESS_FIXTURE_ROOT / f"{stem}-{kind}.json"
            if kind == "layout":
                route = (
                    f"/_apis/work/processes/{PROCESS_ID}/workitemtypes/"
                    f"{reference_name}"
                )
                payloads[route] = {
                    **copy.deepcopy(index_entries[reference_name]),
                    "layout": load_json(fixture_path),
                }
                continue
            if kind == "behaviors":
                route = (
                    f"/_apis/work/processes/{PROCESS_ID}/"
                    f"workitemtypesbehaviors/{reference_name}/behaviors"
                )
            else:
                route = (
                    f"/_apis/work/processes/{PROCESS_ID}/workitemtypes/"
                    f"{reference_name}/{kind}"
                )
            payloads[route] = load_json(fixture_path)
    return payloads


def is_layout_route(path: str) -> bool:
    return path in {
        f"/_apis/work/processes/{PROCESS_ID}/workitemtypes/{reference_name}"
        for reference_name in (EPIC_REFERENCE, USER_STORY_REFERENCE)
    }


class FixtureClient:
    """Return independent official-shape fixtures and record every read."""

    def __init__(
        self,
        payloads: Mapping[str, dict[str, object]] | None = None,
        *,
        failures: Mapping[str, Exception] | None = None,
    ) -> None:
        self.payloads = dict(payloads or fixture_payloads())
        self.failures = dict(failures or {})
        self.calls: list[str] = []
        self._request_records: list[RequestRecord] = []

    @property
    def request_records(self) -> tuple[RequestRecord, ...]:
        return tuple(self._request_records)

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, object] | None = None,
        body: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        assert method == "GET"
        expected_query = {"$expand": "layout"} if is_layout_route(path) else None
        assert query == expected_query
        assert body is None
        self.calls.append(path)
        self._request_records.append(RequestRecord("GET", path))
        await asyncio.sleep(0)
        if path in self.failures:
            raise self.failures[path]
        return copy.deepcopy(self.payloads[path])


class CoordinatedFailureClient(FixtureClient):
    """Hold one request open until a sibling fails, exposing task cleanup."""

    def __init__(self, *, failure_path: str, blocked_path: str) -> None:
        super().__init__()
        self.failure_path = failure_path
        self.blocked_path = blocked_path
        self.blocked_started = asyncio.Event()
        self.blocked_cancelled = False
        self.active_special_requests = 0

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, object] | None = None,
        body: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        if path not in {self.failure_path, self.blocked_path}:
            return await super().request_json(
                method,
                path,
                query=query,
                body=body,
            )

        assert method == "GET"
        assert query is None
        assert body is None
        self.calls.append(path)
        self._request_records.append(RequestRecord("GET", path))
        self.active_special_requests += 1
        try:
            if path == self.blocked_path:
                self.blocked_started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    self.blocked_cancelled = True
                    raise
            await self.blocked_started.wait()
            raise AzureReadError("coordinated artifact failure")
        finally:
            self.active_special_requests -= 1


def expected_artifacts() -> dict[str, dict[str, object]]:
    payloads = fixture_payloads()
    plan = ProcessCollectionPlan.from_index(load_index())
    artifacts = {
        "processes.json": payloads["/_apis/work/processes"],
        "process.json": payloads[f"/_apis/work/processes/{PROCESS_ID}"],
        "workitemtypes.json": payloads[
            f"/_apis/work/processes/{PROCESS_ID}/workitemtypes"
        ],
        "behaviors.json": payloads[
            f"/_apis/work/processes/{PROCESS_ID}/behaviors"
        ],
        MAPPING_ARTIFACT_PATH: plan.mapping_payload(PROCESS_ID),
    }
    for request in plan.requests:
        artifacts[request.artifact_path] = payloads[request.api_path(PROCESS_ID)]
    return artifacts


def seed_process_snapshot(
    project_root: Path,
    *,
    omitted: frozenset[str] = frozenset(),
    custom_text: Mapping[str, str] | None = None,
) -> None:
    writer = SnapshotWriter(project_root / "out" / "process")
    records: list[RequestRecord] = []
    for path, payload in expected_artifacts().items():
        if path in omitted:
            continue
        if custom_text is not None and path in custom_text:
            writer.write_text(path, custom_text[path])
        else:
            writer.write_json(path, payload)
    for route in fixture_payloads():
        records.append(RequestRecord("GET", route))
    writer.commit_manifest(collected_at=COLLECTED_AT, requests=records)


def snapshot_bytes(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "fetch_process_entrypoint", SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("process entry point could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_selects_exactly_one_named_process_by_type_id() -> None:
    payload = load_json(PROCESS_FIXTURE_ROOT / "processes.json")

    assert select_process_id(payload) == PROCESS_ID

    payload["value"] = [
        *payload["value"],  # type: ignore[list-item]
        {
            "typeId": "duplicate-process",
            "name": PROCESS_NAME,
            "customizationType": "inherited",
        },
    ]
    payload["count"] = 3
    with pytest.raises(ProcessCollectionError, match="exactly one"):
        select_process_id(payload)

    payload["value"] = [
        {"typeId": "wrong", "name": "Processo Ágil"},
    ]
    payload["count"] = 1
    with pytest.raises(ProcessCollectionError, match="exactly one"):
        select_process_id(payload)


def test_process_selection_rejects_missing_type_id() -> None:
    payload = load_json(PROCESS_FIXTURE_ROOT / "processes.json")
    selected = payload["value"][1]  # type: ignore[index]
    del selected["typeId"]  # type: ignore[index]

    with pytest.raises(ProcessCollectionError, match="typeId"):
        select_process_id(payload)


def test_process_selection_rejects_non_uuid_type_id() -> None:
    payload = load_json(PROCESS_FIXTURE_ROOT / "processes.json")
    selected = payload["value"][1]  # type: ignore[index]
    selected["typeId"] = "process-123"  # type: ignore[index]

    with pytest.raises(ProcessCollectionError, match="UUID"):
        select_process_id(payload)


def test_plan_preserves_disabled_status_and_all_artifact_families() -> None:
    plan = ProcessCollectionPlan.from_index(load_index())
    epic = next(wit for wit in plan.work_item_types if wit.name == "Epic")

    assert epic == WorkItemType(
        name="Epic",
        reference_name=EPIC_REFERENCE,
        customization="system",
        is_disabled=True,
    )
    assert {request.kind for request in plan.requests_for("Epic")} == set(
        ARTIFACT_KINDS
    )
    assert next(
        wit for wit in plan.work_item_types if wit.name == "História de Usuário"
    ).is_disabled is False


def test_plan_is_deterministic_and_uses_safe_unique_reference_paths() -> None:
    payload = load_index()
    reversed_payload = {**payload, "value": list(reversed(payload["value"]))}

    first = ProcessCollectionPlan.from_index(payload)
    second = ProcessCollectionPlan.from_index(reversed_payload)

    assert first == second
    assert len(first.requests) == 2 * len(ARTIFACT_KINDS)
    assert all(
        request.reference_name in request.api_path(PROCESS_ID)
        for request in first.requests
    )
    assert len({request.artifact_path.casefold() for request in first.requests}) == len(
        first.requests
    )


def test_layout_uses_official_work_item_type_get_expansion() -> None:
    plan = ProcessCollectionPlan.from_index(load_index())
    request = next(
        candidate
        for candidate in plan.requests_for("História de Usuário")
        if candidate.kind == "layout"
    )

    assert request.api_path(PROCESS_ID) == (
        f"/_apis/work/processes/{PROCESS_ID}/workitemtypes/"
        f"{USER_STORY_REFERENCE}"
    )
    assert request.api_query() == {"$expand": "layout"}


@pytest.mark.parametrize(
    "reference_names",
    (
        ("Custom.Duplicate", "custom.duplicate"),
        ("unsafe/name", "Custom.Safe"),
        ("unsafe%2Fname", "Custom.Safe"),
        ("..", "Custom.Safe"),
    ),
)
def test_plan_rejects_reference_segment_or_filename_collisions(
    reference_names: tuple[str, str],
) -> None:
    payload = load_index()
    entries = copy.deepcopy(payload["value"])
    for entry, reference_name in zip(entries, reference_names, strict=True):
        entry["referenceName"] = reference_name
    payload["value"] = entries

    with pytest.raises(ProcessCollectionError, match="referenceName"):
        ProcessCollectionPlan.from_index(payload)


def test_collection_preserves_raw_payloads_mapping_and_behavior_ranks(
    tmp_path: Path,
) -> None:
    client = FixtureClient()

    manifest = asyncio.run(
        collect_process(tmp_path, client, refresh=False, now=fixed_now)
    )

    resolved = resolve_snapshot_root(tmp_path / "out" / "process")
    for artifact_path, expected in expected_artifacts().items():
        assert load_json(resolved / artifact_path) == expected
    ranks = [
        behavior["rank"]
        for behavior in load_json(resolved / "behaviors.json")["value"]
    ]
    assert ranks == [10, 20, 30, 40]
    mapping = load_json(resolved / MAPPING_ARTIFACT_PATH)
    assert mapping["schema_version"] == MAPPING_SCHEMA_VERSION
    assert mapping["process_id"] == PROCESS_ID
    assert {item["reference_name"] for item in mapping["work_item_types"]} == {
        EPIC_REFERENCE,
        USER_STORY_REFERENCE,
    }
    assert tuple(artifact.path for artifact in manifest.artifacts) == tuple(
        sorted(expected_artifacts())
    )
    assert len(client.calls) == 4 + 2 * len(ARTIFACT_KINDS)


def test_complete_cache_returns_before_client_and_clock_are_required(
    tmp_path: Path,
) -> None:
    seed_process_snapshot(tmp_path)
    logical_root = tmp_path / "out" / "process"
    before = snapshot_bytes(logical_root)

    manifest = asyncio.run(
        collect_process(tmp_path, None, refresh=False, now=fail_if_called)
    )

    assert manifest.complete is True
    assert snapshot_bytes(logical_root) == before


def test_legacy_layout_schema_refetches_only_expanded_layouts(
    tmp_path: Path,
) -> None:
    artifacts = expected_artifacts()
    legacy_mapping = copy.deepcopy(artifacts[MAPPING_ARTIFACT_PATH])
    legacy_mapping["schema_version"] = 1
    custom_text = {
        MAPPING_ARTIFACT_PATH: json.dumps(legacy_mapping, ensure_ascii=False),
    }
    plan = ProcessCollectionPlan.from_index(load_index())
    layout_requests = tuple(
        request for request in plan.requests if request.kind == "layout"
    )
    for request in layout_requests:
        expanded = artifacts[request.artifact_path]
        custom_text[request.artifact_path] = json.dumps(
            expanded["layout"],
            ensure_ascii=False,
        )
    seed_process_snapshot(tmp_path, custom_text=custom_text)
    client = FixtureClient()

    asyncio.run(collect_process(tmp_path, client, refresh=False, now=fixed_now))

    assert MAPPING_SCHEMA_VERSION == 2
    assert set(client.calls) == {
        request.api_path(PROCESS_ID) for request in layout_requests
    }
    resolved = resolve_snapshot_root(tmp_path / "out" / "process")
    assert load_json(resolved / MAPPING_ARTIFACT_PATH)["schema_version"] == 2
    assert all(
        "layout" in load_json(resolved / request.artifact_path)
        for request in layout_requests
    )


def test_partial_cache_fetches_only_missing_artifacts_and_seeds_bytes_verbatim(
    tmp_path: Path,
) -> None:
    plan = ProcessCollectionPlan.from_index(load_index())
    epic_fields = next(
        request.artifact_path
        for request in plan.requests_for("Epic")
        if request.kind == "fields"
    )
    user_story_rules = next(
        request.artifact_path
        for request in plan.requests_for("História de Usuário")
        if request.kind == "rules"
    )
    unusual_process_text = (
        '{"name":"Processo-Agil", '
        f'"typeId":"{PROCESS_ID}"}}\n'
    )
    seed_process_snapshot(
        tmp_path,
        omitted=frozenset({epic_fields, user_story_rules}),
        custom_text={"process.json": unusual_process_text},
    )
    client = FixtureClient()

    asyncio.run(collect_process(tmp_path, client, refresh=False, now=fixed_now))

    expected_routes = {
        request.api_path(PROCESS_ID)
        for request in plan.requests
        if request.artifact_path in {epic_fields, user_story_rules}
    }
    assert set(client.calls) == expected_routes
    assert len(client.calls) == 2
    resolved = resolve_snapshot_root(tmp_path / "out" / "process")
    assert (resolved / "process.json").read_text(encoding="utf-8") == (
        unusual_process_text
    )
    assert set(load_json(resolved / user_story_rules)) == {"count", "value"}


def test_404_names_the_failed_artifact_and_does_not_publish(tmp_path: Path) -> None:
    plan = ProcessCollectionPlan.from_index(load_index())
    failed_request = next(
        request
        for request in plan.requests_for("Epic")
        if request.kind == "rules"
    )
    failure = AzureReadError(
        "GET /_apis/work/processes/{processId}/workitemtypes/"
        "{witRefName}/{artifact} HTTP 404"
    )
    client = FixtureClient(failures={failed_request.api_path(PROCESS_ID): failure})

    with pytest.raises(ProcessArtifactError, match=r"rules.*HTTP 404"):
        asyncio.run(
            collect_process(tmp_path, client, refresh=False, now=fixed_now)
        )

    logical_root = tmp_path / "out" / "process"
    assert not (logical_root / "CURRENT").exists()


def test_failed_artifact_cancels_and_awaits_siblings_before_abort(
    tmp_path: Path,
) -> None:
    plan = ProcessCollectionPlan.from_index(load_index())
    failure_request = plan.requests[0]
    blocked_request = plan.requests[1]
    client = CoordinatedFailureClient(
        failure_path=failure_request.api_path(PROCESS_ID),
        blocked_path=blocked_request.api_path(PROCESS_ID),
    )

    async def exercise() -> None:
        with pytest.raises(ProcessArtifactError, match="coordinated"):
            await collect_process(
                tmp_path,
                client,
                refresh=False,
                now=fixed_now,
            )
        assert client.blocked_started.is_set()
        assert client.blocked_cancelled is True
        assert client.active_special_requests == 0

    asyncio.run(exercise())
    assert not (tmp_path / "out" / "process" / "CURRENT").exists()


def test_malformed_family_aborts_instead_of_becoming_an_empty_list(
    tmp_path: Path,
) -> None:
    payloads = fixture_payloads()
    states_route = next(path for path in payloads if path.endswith("/states"))
    payloads[states_route] = {"count": 0}

    with pytest.raises(ProcessArtifactError, match="states.*malformed"):
        asyncio.run(
            collect_process(
                tmp_path,
                FixtureClient(payloads),
                refresh=False,
                now=fixed_now,
            )
        )

    assert not (tmp_path / "out" / "process" / "CURRENT").exists()


@pytest.mark.parametrize(
    ("family", "identity_path"),
    (("fields", ("referenceName",)), ("states", ("id",)), ("rules", ("id",))),
)
def test_collection_rejects_duplicate_family_identifiers(
    tmp_path: Path, family: str, identity_path: tuple[str, ...]
) -> None:
    payloads = fixture_payloads()
    route = next(path for path in payloads if path.endswith(f"/{family}"))
    entries = payloads[route]["value"]
    entries.append(copy.deepcopy(entries[0]))
    payloads[route]["count"] = len(entries)
    with pytest.raises(ProcessArtifactError, match=f"{family}.*unique"):
        asyncio.run(
            collect_process(tmp_path, FixtureClient(payloads), refresh=False, now=fixed_now)
        )
    assert not (tmp_path / "out" / "process" / "CURRENT").exists()


@pytest.mark.parametrize(
    ("route_suffix", "remove_path", "error_family"),
    (
        (
            f"/{USER_STORY_REFERENCE}",
            ("layout", "pages", 0, "sections"),
            "layout",
        ),
        (
            f"/{USER_STORY_REFERENCE}",
            ("referenceName",),
            "layout",
        ),
        ("/behaviors", ("value", 0, "isDefault"), "behaviors"),
        (
            f"/{PROCESS_ID}/behaviors",
            ("value", 0, "referenceName"),
            "behaviors.json",
        ),
    ),
)
def test_collection_rejects_shapes_required_by_downstream_evaluators(
    tmp_path: Path,
    route_suffix: str,
    remove_path: tuple[object, ...],
    error_family: str,
) -> None:
    payloads = fixture_payloads()
    matching_routes = [path for path in payloads if path.endswith(route_suffix)]
    route = matching_routes[0]
    if route_suffix == "/behaviors":
        route = next(path for path in matching_routes if "workitemtypesbehaviors" in path)
    node: object = payloads[route]
    for segment in remove_path[:-1]:
        node = node[segment]  # type: ignore[index]
    del node[remove_path[-1]]  # type: ignore[index]

    with pytest.raises(ProcessArtifactError, match=error_family):
        asyncio.run(
            collect_process(
                tmp_path,
                FixtureClient(payloads),
                refresh=False,
                now=fixed_now,
            )
        )

    assert not (tmp_path / "out" / "process" / "CURRENT").exists()


@pytest.mark.parametrize(
    ("family", "key"),
    (("fields", "required"), ("behaviors", "isLegacyDefault")),
)
def test_optional_boolean_members_are_validated_only_when_present(
    tmp_path: Path, family: str, key: str
) -> None:
    payloads = fixture_payloads()
    routes = [path for path in payloads if path.endswith(f"/{family}")]
    if family == "behaviors":
        route = next(path for path in routes if "workitemtypesbehaviors" in path)
    else:
        route = routes[0]
    payloads[route]["value"][0][key] = "not-a-boolean"  # type: ignore[index]

    with pytest.raises(ProcessArtifactError, match=family):
        asyncio.run(
            collect_process(
                tmp_path,
                FixtureClient(payloads),
                refresh=False,
                now=fixed_now,
            )
        )

    assert not (tmp_path / "out" / "process" / "CURRENT").exists()


def test_failed_refresh_keeps_current_generation_byte_identical(
    tmp_path: Path,
) -> None:
    seed_process_snapshot(tmp_path)
    logical_root = tmp_path / "out" / "process"
    before = snapshot_bytes(logical_root)
    plan = ProcessCollectionPlan.from_index(load_index())
    failed_request = next(
        request
        for request in plan.requests
        if request.kind == "layout" and request.reference_name == USER_STORY_REFERENCE
    )
    client = FixtureClient(
        failures={
            failed_request.api_path(PROCESS_ID): AzureReadError(
                "GET /_apis/work/processes/{processId}/workitemtypes/"
                "{witRefName}/{artifact} HTTP 404"
            )
        }
    )

    with pytest.raises(ProcessArtifactError, match="layout.*HTTP 404"):
        asyncio.run(
            collect_process(tmp_path, client, refresh=True, now=fixed_now)
        )

    assert snapshot_bytes(logical_root) == before


def test_non_refresh_rechecks_complete_cache_after_writer_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logical_root = tmp_path / "out" / "process"
    published_bytes: dict[str, bytes] = {}
    real_writer = SnapshotWriter

    def writer_that_observes_competing_publication(root: Path) -> SnapshotWriter:
        stale_writer = real_writer(root)
        seed_process_snapshot(tmp_path)
        published_bytes.update(snapshot_bytes(logical_root))
        return stale_writer

    monkeypatch.setattr(
        process_collector_module,
        "SnapshotWriter",
        writer_that_observes_competing_publication,
    )
    client = FixtureClient()

    manifest = asyncio.run(
        collect_process(tmp_path, client, refresh=False, now=fail_if_called)
    )

    assert manifest.complete is True
    assert client.calls == []
    assert snapshot_bytes(logical_root) == published_bytes


def test_script_uses_one_http_client_one_read_client_and_semaphore_eight(
    tmp_path: Path,
) -> None:
    module = load_script()
    payloads = fixture_payloads()
    transport_requests: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        transport_requests.append(request)
        route = request.url.path.removeprefix("/bancodonordeste")
        return httpx.Response(
            200,
            json=payloads[route],
            request=request,
        )

    http_instances: list[httpx.AsyncClient] = []

    def http_client_factory() -> httpx.AsyncClient:
        http = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        http_instances.append(http)
        return http

    constructed: list[tuple[httpx.AsyncClient, asyncio.Semaphore]] = []
    real_client = AzureReadClient

    def client_factory(
        http: httpx.AsyncClient,
        base_url: str,
        pat: str,
        semaphore: asyncio.Semaphore,
    ) -> AzureReadClient:
        constructed.append((http, semaphore))
        return real_client(http, base_url, pat, semaphore)

    module.AzureReadClient = client_factory
    settings = Settings(
        organization="bancodonordeste",
        project="Torre CCR - Concessão de Crédito",
        page_ids=(35, 10, 9, 37),
        process_name=PROCESS_NAME,
        api_version="7.1",
        pat="fixture-only-pat",
        output_root=tmp_path / "out",
        wiki_id="fixture-wiki-id",
    )

    manifest, request_count = asyncio.run(
        module._collect_with_settings(
            tmp_path,
            settings,
            refresh=False,
            http_client_factory=http_client_factory,
            now=fixed_now,
        )
    )

    assert manifest.complete is True
    assert request_count == 14
    assert len(http_instances) == 1
    assert len(constructed) == 1
    assert constructed[0][0] is http_instances[0]
    assert constructed[0][1]._value == 8
    assert len(transport_requests) == 14
    layout_requests = [
        request
        for request in transport_requests
        if is_layout_route(request.url.path.removeprefix("/bancodonordeste"))
    ]
    assert len(layout_requests) == 2
    assert all(
        request.url.params.get("$expand") == "layout"
        for request in layout_requests
    )
    assert all(
        "$expand" not in request.url.params
        for request in transport_requests
        if request not in layout_requests
    )


def test_entry_point_cache_hit_precedes_settings_client_and_asyncio(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script()
    seed_process_snapshot(tmp_path)
    before = snapshot_bytes(tmp_path / "out" / "process")

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("complete cache evaluated a runtime dependency")

    monkeypatch.setattr(module.asyncio, "run", forbidden)
    result = module.main(
        [],
        project_root=tmp_path,
        settings_loader=forbidden,
        http_client_factory=forbidden,
        now=fail_if_called,
    )
    output = capsys.readouterr()

    assert result == 0
    assert snapshot_bytes(tmp_path / "out" / "process") == before
    assert "requests: 0" in output.out
    assert PROCESS_ID not in output.out + output.err
    assert EPIC_REFERENCE not in output.out + output.err
    assert read_cached_process_manifest(tmp_path) is not None


def test_cache_reader_does_not_follow_artifact_swapped_after_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_process_snapshot(tmp_path)
    outside = tmp_path / "outside-process.json"
    outside.write_text(
        json.dumps(expected_artifacts()["process.json"], indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    original_resolve = process_collector_module.resolve_snapshot_root
    swapped = False

    def resolve_then_swap(root: Path) -> Path:
        nonlocal swapped
        resolved = original_resolve(root)
        if not swapped:
            target = resolved / "process.json"
            target.unlink()
            target.symlink_to(outside)
            swapped = True
        return resolved

    monkeypatch.setattr(
        process_collector_module,
        "resolve_snapshot_root",
        resolve_then_swap,
    )

    with pytest.raises(SnapshotError, match="symlink|hash"):
        read_cached_process_manifest(tmp_path)


def test_refresh_requests_every_global_and_per_wit_artifact(tmp_path: Path) -> None:
    seed_process_snapshot(tmp_path)
    client = FixtureClient()

    asyncio.run(collect_process(tmp_path, client, refresh=True, now=fixed_now))

    assert set(client.calls) == set(fixture_payloads())
    assert len(client.calls) == 14
