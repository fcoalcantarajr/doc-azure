from __future__ import annotations

import asyncio
import importlib.util
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from doc_azure.azure_client import AzureReadClient, AzureReadError, RequestRecord
from doc_azure.settings import Settings
from doc_azure.snapshot import SnapshotError, SnapshotWriter, resolve_snapshot_root
from doc_azure.wiki_collector import (
    PAGE_SPECS,
    WikiCollectionError,
    WikiPage,
    collect_wiki_pages,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "audit" / "wiki-pages.json"
SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "01_fetch_wiki.py"
COLLECTED_AT = datetime(2026, 8, 24, 15, 30, tzinfo=timezone.utc)
PROJECT_IDENTIFIER = "7ee590c5-7201-4acc-83f5-3e73023a0ab1"
WIKI_IDENTIFIER = "87014e24-4977-4d27-8e12-c05208008d95"
EXPECTED_PAGE_SLUGS = {
    35: "leiame",
    10: "politicas",
    9: "changelog",
    37: "apendice",
}


def fixed_now() -> datetime:
    return COLLECTED_AT


def fail_if_called() -> datetime:
    raise AssertionError("cache hit evaluated the clock")


def load_page_payloads() -> dict[int, dict[str, object]]:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return {int(page_id): payload for page_id, payload in raw.items()}


class WikiTransport:
    """Serve full fixture responses by requested page ID."""

    def __init__(
        self,
        payloads: Mapping[int, dict[str, object]],
        *,
        statuses: Mapping[int, int] | None = None,
    ) -> None:
        self._payloads = payloads
        self._statuses = statuses or {}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        page_id = int(request.url.path.rsplit("/", 1)[-1])
        status = self._statuses.get(page_id, 200)
        payload = self._payloads.get(page_id, {"message": "unavailable"})
        return httpx.Response(status, json=payload, request=request)


def make_client(http: httpx.AsyncClient) -> AzureReadClient:
    return AzureReadClient(
        http,
        "https://dev.azure.com/bancodonordeste",
        "test-pat",
        asyncio.Semaphore(4),
    )


def snapshot_bytes(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def seed_complete_wiki_snapshot(project_root: Path) -> None:
    payloads = load_page_payloads()
    writer = SnapshotWriter(project_root / "out" / "wiki")
    records: list[RequestRecord] = []
    for page_id, slug in EXPECTED_PAGE_SLUGS.items():
        payload = payloads[page_id]
        writer.write_text(f"{slug}.md", str(payload["content"]))
        writer.write_json(
            f"{slug}.metadata.json",
            {key: value for key, value in payload.items() if key != "content"},
        )
        records.append(RequestRecord("GET", expected_page_path(page_id)))
    writer.commit_manifest(collected_at=COLLECTED_AT, requests=records)


def expected_page_path(page_id: int) -> str:
    return (
        f"/{PROJECT_IDENTIFIER}/_apis/wiki/wikis/{WIKI_IDENTIFIER}"
        f"/pages/{page_id}"
    )


async def collect_with_transport(
    project_root: Path,
    transport: WikiTransport,
    *,
    refresh: bool,
) -> tuple[object, tuple[RequestRecord, ...]]:
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
        client = make_client(http)
        manifest = await collect_wiki_pages(
            project_root,
            client,
            refresh=refresh,
            now=fixed_now,
        )
        return manifest, client.request_records


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fetch_wiki_entrypoint", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("wiki entry point could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_complete_wiki_cache_returns_before_client_is_required(tmp_path: Path) -> None:
    seed_complete_wiki_snapshot(tmp_path)
    logical_root = tmp_path / "out" / "wiki"
    before = snapshot_bytes(logical_root)

    manifest = asyncio.run(
        collect_wiki_pages(tmp_path, None, refresh=False, now=fail_if_called)
    )

    assert manifest.complete is True
    assert snapshot_bytes(logical_root) == before


def test_collection_requests_exact_page_ids_and_preserves_all_metadata(
    tmp_path: Path,
) -> None:
    payloads = load_page_payloads()
    transport = WikiTransport(payloads)

    manifest, records = asyncio.run(
        collect_with_transport(tmp_path, transport, refresh=False)
    )

    assert WikiPage(35, "leiame", "title", "content").page_id == 35
    assert {spec.page_id: spec.slug for spec in PAGE_SPECS} == EXPECTED_PAGE_SLUGS
    requested_page_ids = {
        int(request.url.path.rsplit("/", 1)[-1])
        for request in transport.requests
    }
    assert requested_page_ids == {
        35,
        10,
        9,
        37,
    }
    assert len(transport.requests) == 4
    for request in transport.requests:
        assert request.method == "GET"
        assert request.url.params.get_list("includeContent") == ["true"]
        assert request.url.params.get_list("api-version") == ["7.1"]

    resolved = resolve_snapshot_root(tmp_path / "out" / "wiki")
    for page_id, slug in EXPECTED_PAGE_SLUGS.items():
        payload = payloads[page_id]
        assert (resolved / f"{slug}.md").read_text(encoding="utf-8") == payload[
            "content"
        ]
        assert json.loads(
            (resolved / f"{slug}.metadata.json").read_text(encoding="utf-8")
        ) == {key: value for key, value in payload.items() if key != "content"}

    expected_paths = tuple(
        sorted(
            path
            for slug in EXPECTED_PAGE_SLUGS.values()
            for path in (f"{slug}.md", f"{slug}.metadata.json")
        )
    )
    assert tuple(artifact.path for artifact in manifest.artifacts) == expected_paths
    assert records == tuple(
        RequestRecord("GET", expected_page_path(page_id))
        for page_id in (35, 10, 9, 37)
    )
    assert manifest.requests == tuple(sorted(records, key=lambda record: record.path))
    assert all("?" not in record.path for record in manifest.requests)


@pytest.mark.parametrize(
    ("page_id", "bad_content"),
    ((35, ""), (10, "   \n"), (9, {"unexpected": "object"})),
)
def test_blank_or_non_string_content_aborts_without_publishing(
    tmp_path: Path, page_id: int, bad_content: object
) -> None:
    payloads = load_page_payloads()
    payloads[page_id]["content"] = bad_content
    transport = WikiTransport(payloads)

    with pytest.raises(WikiCollectionError, match=f"page {page_id}"):
        asyncio.run(collect_with_transport(tmp_path, transport, refresh=False))

    logical_root = tmp_path / "out" / "wiki"
    assert not (logical_root / "CURRENT").exists()
    assert list(logical_root.rglob("*.md")) == []


def test_404_aborts_instead_of_publishing_an_empty_stub(tmp_path: Path) -> None:
    transport = WikiTransport(load_page_payloads(), statuses={10: 404})

    with pytest.raises(AzureReadError, match="HTTP 404"):
        asyncio.run(collect_with_transport(tmp_path, transport, refresh=False))

    logical_root = tmp_path / "out" / "wiki"
    assert not (logical_root / "CURRENT").exists()
    assert list(logical_root.rglob("*.md")) == []


def test_failed_refresh_keeps_current_generation_byte_identical(tmp_path: Path) -> None:
    seed_complete_wiki_snapshot(tmp_path)
    logical_root = tmp_path / "out" / "wiki"
    before = snapshot_bytes(logical_root)
    current_before = (logical_root / "CURRENT").read_bytes()
    payloads = load_page_payloads()
    payloads[35]["content"] = "# Replacement that must not be published\n"
    transport = WikiTransport(payloads, statuses={37: 404})

    with pytest.raises(AzureReadError, match="HTTP 404"):
        asyncio.run(collect_with_transport(tmp_path, transport, refresh=True))

    assert (logical_root / "CURRENT").read_bytes() == current_before
    assert snapshot_bytes(logical_root) == before


def test_non_refresh_cache_is_deterministic_and_makes_zero_requests(
    tmp_path: Path,
) -> None:
    seed_complete_wiki_snapshot(tmp_path)
    logical_root = tmp_path / "out" / "wiki"
    before = snapshot_bytes(logical_root)

    first = asyncio.run(
        collect_wiki_pages(tmp_path, None, refresh=False, now=fail_if_called)
    )
    middle = snapshot_bytes(logical_root)
    second = asyncio.run(
        collect_wiki_pages(tmp_path, None, refresh=False, now=fail_if_called)
    )

    assert first == second
    assert middle == before
    assert snapshot_bytes(logical_root) == before


def test_refresh_without_client_fails_before_touching_current_snapshot(
    tmp_path: Path,
) -> None:
    seed_complete_wiki_snapshot(tmp_path)
    logical_root = tmp_path / "out" / "wiki"
    before = snapshot_bytes(logical_root)

    with pytest.raises(WikiCollectionError, match="client"):
        asyncio.run(
            collect_wiki_pages(tmp_path, None, refresh=True, now=fail_if_called)
        )

    assert snapshot_bytes(logical_root) == before


def test_corrupt_authoritative_cache_fails_closed_without_client(
    tmp_path: Path,
) -> None:
    seed_complete_wiki_snapshot(tmp_path)
    logical_root = tmp_path / "out" / "wiki"
    resolved = resolve_snapshot_root(logical_root)
    (resolved / "leiame.md").write_text("tampered", encoding="utf-8")

    with pytest.raises(SnapshotError, match="hash"):
        asyncio.run(
            collect_wiki_pages(tmp_path, None, refresh=False, now=fail_if_called)
        )


def test_entry_point_fetches_once_then_skips_before_settings_and_asyncio(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script()
    payloads = load_page_payloads()
    transport = WikiTransport(payloads)
    credential = "entrypoint-test-value"
    settings = Settings(
        organization="bancodonordeste",
        project="Torre CCR - Concessão de Crédito",
        page_ids=(35, 10, 9, 37),
        process_name="Processo-Agil",
        api_version="7.1",
        pat=credential,
        output_root=tmp_path / "out",
        wiki_id=WIKI_IDENTIFIER,
    )
    factory_calls = 0

    def http_client_factory() -> httpx.AsyncClient:
        nonlocal factory_calls
        factory_calls += 1
        return httpx.AsyncClient(transport=httpx.MockTransport(transport))

    real_run = asyncio.run
    run_count = 0

    def counted_run(coroutine: object) -> object:
        nonlocal run_count
        run_count += 1
        return real_run(coroutine)  # type: ignore[arg-type]

    monkeypatch.setattr(module.asyncio, "run", counted_run)
    first_result = module.main(
        [],
        project_root=tmp_path,
        settings_loader=lambda _: settings,
        http_client_factory=http_client_factory,
        now=fixed_now,
    )
    first_output = capsys.readouterr()
    logical_root = tmp_path / "out" / "wiki"
    before_second_run = snapshot_bytes(logical_root)

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("complete cache evaluated a runtime dependency")

    second_result = module.main(
        [],
        project_root=tmp_path,
        settings_loader=forbidden,
        http_client_factory=forbidden,
        now=fail_if_called,
    )
    second_output = capsys.readouterr()

    assert first_result == 0
    assert second_result == 0
    assert run_count == 1
    assert factory_calls == 1
    assert len(transport.requests) == 4
    assert snapshot_bytes(logical_root) == before_second_run
    assert "requests: 4" in first_output.out
    assert "[saved] out/wiki/leiame.md" in first_output.out
    assert "requests: 0" in second_output.out
    assert "[skipped] out/wiki/leiame.md" in second_output.out
    combined_output = (
        first_output.out
        + first_output.err
        + second_output.out
        + second_output.err
    )
    assert credential not in combined_output


def test_entry_point_never_prints_exception_credential_material(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_script()
    credential = "output-forbidden-value"

    def failing_settings_loader(project_root: Path) -> Settings:
        raise RuntimeError(f"remote failure included {credential}")

    result = module.main(
        [],
        project_root=tmp_path,
        settings_loader=failing_settings_loader,
    )
    output = capsys.readouterr()

    assert result == 1
    assert credential not in output.out + output.err


def test_entry_point_accepts_only_refresh_option() -> None:
    module = load_script()

    with pytest.raises(SystemExit) as raised:
        module.main(["--unexpected"], project_root=Path("unused"))

    assert raised.value.code == 2
