"""Contract tests for the deterministic process-only LLM export."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
import httpx

from doc_azure.snapshot import (
    SnapshotError,
    SnapshotWriter,
    resolve_snapshot_root,
    select_snapshot_generation,
)
from tests.test_process_collector import (
    COLLECTED_AT,
    EPIC_REFERENCE,
    PROCESS_ID,
    USER_STORY_REFERENCE,
    expected_artifacts,
    fixture_payloads,
    seed_process_snapshot,
)
from doc_azure.settings import Settings


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "export_process_for_llm.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("export_process_for_llm", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest_hash(root: Path) -> str:
    generation = resolve_snapshot_root(root)
    return hashlib.sha256((generation / "manifest.json").read_bytes()).hexdigest()


def publish_source(
    root: Path,
    *,
    mutation: tuple[str, object] | None = None,
) -> Path:
    artifacts = expected_artifacts()
    if mutation is not None:
        artifact_path, payload = mutation
        artifacts[artifact_path] = payload  # type: ignore[assignment]
    writer = SnapshotWriter(root / "out" / "process")
    for path, payload in artifacts.items():
        writer.write_json(path, payload)
    writer.commit_manifest(collected_at=COLLECTED_AT, requests=())
    return resolve_snapshot_root(root / "out" / "process")


def test_export_writes_bundle_summary_and_every_work_item_type(tmp_path: Path) -> None:
    from doc_azure.process_export import export_process_for_llm

    seed_process_snapshot(tmp_path)
    result = export_process_for_llm(tmp_path)

    assert result.bundle_path.is_file()
    assert result.work_item_types_root.is_dir()
    assert sorted(path.name for path in result.work_item_types_root.iterdir()) == [
        f"{USER_STORY_REFERENCE}.md",
        f"{EPIC_REFERENCE}.md",
    ]
    provenance = json.loads((result.generation_root / "provenance.json").read_text())
    assert provenance == {
        "schema_version": 1,
        "source_generation": resolve_snapshot_root(
            tmp_path / "out" / "process"
        ).name,
        "source_manifest_sha256": manifest_hash(tmp_path / "out" / "process"),
        "source_collected_at": COLLECTED_AT.isoformat(),
        "process_id": PROCESS_ID,
        "process_name": "Processo-Agil",
        "scope": "process-only",
        "omitted_properties": ["url"],
        "work_item_type_counts": {"total": 2, "active": 1, "disabled": 1},
    }
    manifest = json.loads((result.generation_root / "manifest.json").read_text())
    assert {artifact["path"] for artifact in manifest["artifacts"]} == {
        "README.md",
        "bundle.md",
        "process-summary.md",
        "provenance.json",
        f"work-item-types/{EPIC_REFERENCE}.md",
        f"work-item-types/{USER_STORY_REFERENCE}.md",
    }


def test_export_covers_all_families_and_traceability(tmp_path: Path) -> None:
    from doc_azure.process_export import export_process_for_llm

    seed_process_snapshot(tmp_path)
    result = export_process_for_llm(tmp_path)
    text = (result.work_item_types_root / f"{EPIC_REFERENCE}.md").read_text()

    for heading in ("Estados", "Campos", "Regras", "Layout", "Behaviors"):
        assert f"## {heading}" in text
    for family in ("states", "fields", "rules", "layout", "behaviors"):
        assert f"workitemtypes/{EPIC_REFERENCE}/{family}.json" in text
    assert "JSON Pointer" in text
    assert "Desabilitado" in text
    assert "Ativo" in (
        result.work_item_types_root / f"{USER_STORY_REFERENCE}.md"
    ).read_text()
    summary = (result.generation_root / "process-summary.md").read_text()
    bundle = result.bundle_path.read_text()
    assert result.source_generation in summary
    assert manifest_hash(tmp_path / "out" / "process") in summary
    assert result.source_generation in bundle
    layout_section = text.split("## Layout", 1)[1].split("## Behaviors", 1)[0]
    assert "JSON Pointer: `/layout`" in layout_section
    assert "JSON Pointer: ``" in layout_section
    assert "`/layout/pages/0`" in layout_section


def test_layout_outline_pointers_ignore_synthetic_additional_properties(
    tmp_path: Path,
) -> None:
    from doc_azure.process_export import export_process_for_llm

    artifacts = expected_artifacts()
    layout_path = f"workitemtypes/{EPIC_REFERENCE}/layout.json"
    layout_payload = artifacts[layout_path]
    control = layout_payload["layout"]["pages"][0]["sections"][0]["groups"][0][
        "controls"
    ][0]  # type: ignore[index]
    control["contribution"] = {"id": "Contoso.Extension"}  # type: ignore[index]
    publish_source(tmp_path, mutation=(layout_path, layout_payload))

    result = export_process_for_llm(tmp_path)
    text = (result.work_item_types_root / f"{EPIC_REFERENCE}.md").read_text()

    expected_pointer = (
        "/layout/pages/0/sections/0/groups/0/controls/0/contribution"
    )
    assert f"`{expected_pointer}`" in text
    assert "/additional_properties/contribution" not in text


def test_export_preserves_values_unknown_properties_and_only_removes_url(
    tmp_path: Path,
) -> None:
    from doc_azure.process_export import export_process_for_llm

    artifacts = expected_artifacts()
    fields_path = f"workitemtypes/{EPIC_REFERENCE}/fields.json"
    fields = artifacts[fields_path]
    first = fields["value"][0]  # type: ignore[index]
    first.update(  # type: ignore[union-attr]
        {
            "url": "https://transport.invalid",
            "not_url": "preservar",
            "missingWitness": None,
            "falseWitness": False,
            "zeroWitness": 0,
            "emptyWitness": "",
            "markdownWitness": "a|b`c\\d\nlinha",
        }
    )
    publish_source(tmp_path, mutation=(fields_path, fields))

    result = export_process_for_llm(tmp_path)
    text = (result.work_item_types_root / f"{EPIC_REFERENCE}.md").read_text()

    assert "transport.invalid" not in text
    assert '"not_url": "preservar"' in text
    assert '"missingWitness": null' in text
    assert '"falseWitness": false' in text
    assert '"zeroWitness": 0' in text
    assert '"emptyWitness": ""' in text
    assert "a|b`c\\\\d\\nlinha" in text


def test_export_marks_absent_optional_properties_separately(tmp_path: Path) -> None:
    from doc_azure.process_export import export_process_for_llm

    seed_process_snapshot(tmp_path)
    result = export_process_for_llm(tmp_path)
    text = (result.work_item_types_root / f"{EPIC_REFERENCE}.md").read_text()

    assert "(ausente)" in text


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
def test_export_model_rejects_non_finite_json_numbers(value: float) -> None:
    from doc_azure.process_export_render import freeze_json

    with pytest.raises(TypeError, match="non-finite"):
        freeze_json(value)


def test_repeated_export_reuses_identical_generation_and_bytes(tmp_path: Path) -> None:
    from doc_azure.process_export import export_process_for_llm

    seed_process_snapshot(tmp_path)
    first = export_process_for_llm(tmp_path)
    current = (tmp_path / "out" / "process-llm" / "CURRENT").read_bytes()
    before = {path.relative_to(first.generation_root): path.read_bytes()
              for path in first.generation_root.rglob("*") if path.is_file()}

    second = export_process_for_llm(tmp_path)

    assert second.reused is True
    assert second.generation_root == first.generation_root
    assert (tmp_path / "out" / "process-llm" / "CURRENT").read_bytes() == current
    assert {path.relative_to(second.generation_root): path.read_bytes()
            for path in second.generation_root.rglob("*") if path.is_file()} == before


def test_export_reselects_matching_orphan_when_current_is_missing(
    tmp_path: Path,
) -> None:
    from doc_azure.process_export import export_process_for_llm

    seed_process_snapshot(tmp_path)
    first = export_process_for_llm(tmp_path)
    export_root = tmp_path / "out" / "process-llm"
    (export_root / "CURRENT").unlink()

    second = export_process_for_llm(tmp_path)

    assert second.reused is True
    assert second.generation_root == first.generation_root
    assert (export_root / "CURRENT").read_text().strip() == first.generation_root.name
    assert list((export_root / "snapshots").iterdir()) == [first.generation_root]


def test_changed_source_creates_and_retains_a_new_generation(tmp_path: Path) -> None:
    from doc_azure.process_export import export_process_for_llm

    seed_process_snapshot(tmp_path)
    first = export_process_for_llm(tmp_path)
    process = expected_artifacts()["process.json"]
    process["description"] = "nova descrição"
    publish_source(tmp_path, mutation=("process.json", process))

    second = export_process_for_llm(tmp_path)

    assert second.generation_root != first.generation_root
    assert first.generation_root.is_dir()
    assert "nova descrição" in second.bundle_path.read_text()


def test_returning_to_historical_source_reselects_original_export(tmp_path: Path) -> None:
    from doc_azure.process_export import export_process_for_llm

    first_source = publish_source(tmp_path)
    first_export = export_process_for_llm(tmp_path)
    process = expected_artifacts()["process.json"]
    process["description"] = "fonte B"
    second_source = publish_source(tmp_path, mutation=("process.json", process))
    second_export = export_process_for_llm(tmp_path)
    select_snapshot_generation(
        tmp_path / "out" / "process",
        first_source.name,
        expected_generation=second_source.name,
    )

    reused = export_process_for_llm(tmp_path)

    assert reused.reused is True
    assert reused.generation_root == first_export.generation_root
    assert reused.generation_root != second_export.generation_root
    assert len(list((tmp_path / "out" / "process-llm" / "snapshots").iterdir())) == 2


def test_historical_reuse_revalidates_candidate_under_selection_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import doc_azure.process_export as process_export

    first_source = publish_source(tmp_path)
    first_export = process_export.export_process_for_llm(tmp_path)
    process = expected_artifacts()["process.json"]
    process["description"] = "fonte B"
    second_source = publish_source(tmp_path, mutation=("process.json", process))
    second_export = process_export.export_process_for_llm(tmp_path)
    select_snapshot_generation(
        tmp_path / "out" / "process",
        first_source.name,
        expected_generation=second_source.name,
    )
    real_select = select_snapshot_generation

    def forge_then_select(
        root: Path,
        generation: str,
        *,
        expected_generation: str | None,
        validator: object = None,
    ) -> Path:
        candidate = root / "snapshots" / generation
        bundle = candidate / "bundle.md"
        bundle.write_text("forged\n")
        manifest_path = candidate / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        artifact = next(
            item for item in manifest["artifacts"] if item["path"] == "bundle.md"
        )
        artifact["sha256"] = hashlib.sha256(bundle.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        return real_select(
            root,
            generation,
            expected_generation=expected_generation,
            validator=validator,  # type: ignore[arg-type]
        )

    monkeypatch.setattr(process_export, "select_snapshot_generation", forge_then_select)

    with pytest.raises(process_export.ProcessExportError, match="different process source"):
        process_export.export_process_for_llm(tmp_path)

    assert resolve_snapshot_root(tmp_path / "out" / "process-llm") == (
        second_export.generation_root
    )
    assert first_export.bundle_path.read_text() == "forged\n"


def test_forged_current_export_is_never_reused(tmp_path: Path) -> None:
    from doc_azure.process_export import export_process_for_llm

    seed_process_snapshot(tmp_path)
    genuine = export_process_for_llm(tmp_path)
    provenance = json.loads((genuine.generation_root / "provenance.json").read_text())
    forged = SnapshotWriter(tmp_path / "out" / "process-llm")
    for path in ("README.md", "bundle.md", "process-summary.md"):
        forged.write_text(path, "forged\n")
    forged.write_json("provenance.json", provenance)
    forged.write_text("work-item-types/wrong-a.md", "forged\n")
    forged.write_text("work-item-types/wrong-b.md", "forged\n")
    forged.commit_manifest(collected_at=COLLECTED_AT, requests=())

    result = export_process_for_llm(tmp_path)

    assert result.reused is True
    assert result.generation_root == genuine.generation_root
    assert result.bundle_path.read_text() != "forged\n"


def test_same_source_published_before_writer_is_not_duplicated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import doc_azure.process_export as process_export

    seed_process_snapshot(tmp_path)
    published: Path | None = None

    def publish_between_checks(
        root: Path,
        provenance: dict[str, object],
        artifacts: dict[str, str],
    ) -> None:
        nonlocal published
        writer = SnapshotWriter(root)
        for path, content in artifacts.items():
            writer.write_text(path, content)
        writer.commit_manifest(
            collected_at=str(provenance["source_collected_at"]), requests=()
        )
        published = resolve_snapshot_root(root)
        return None

    monkeypatch.setattr(
        process_export, "_find_reusable_export", publish_between_checks
    )

    result = process_export.export_process_for_llm(tmp_path)

    assert result.reused is True
    assert result.generation_root == published
    assert len(list((tmp_path / "out" / "process-llm" / "snapshots").iterdir())) == 1


def test_current_switch_during_read_cannot_mix_source_generations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import doc_azure.process_export as process_export

    first_source = publish_source(tmp_path)
    process = expected_artifacts()["process.json"]
    process["description"] = "segunda geração"
    second_source = publish_source(tmp_path, mutation=("process.json", process))
    (tmp_path / "out" / "process" / "CURRENT").write_text(first_source.name + "\n")
    original = process_export.read_snapshot_artifact
    switched = False

    def switching_read(root: Path, path: str) -> bytes:
        nonlocal switched
        if not switched:
            switched = True
            (tmp_path / "out" / "process" / "CURRENT").write_text(
                second_source.name + "\n"
            )
        return original(root, path)

    monkeypatch.setattr(process_export, "read_snapshot_artifact", switching_read)
    result = process_export.export_process_for_llm(tmp_path)

    assert json.loads((result.generation_root / "provenance.json").read_text())[
        "source_generation"
    ] == first_source.name
    assert "segunda geração" not in result.bundle_path.read_text()


@pytest.mark.parametrize(
    "source_setup, message",
    (
        (lambda root: None, "snapshot"),
        (
            lambda root: seed_process_snapshot(
                root, omitted=frozenset({f"workitemtypes/{EPIC_REFERENCE}/rules.json"})
            ),
            "snapshot",
        ),
    ),
)
def test_missing_or_incomplete_source_fails_closed(
    tmp_path: Path, source_setup: object, message: str
) -> None:
    from doc_azure.process_export import ProcessExportError, export_process_for_llm

    source_setup(tmp_path)  # type: ignore[operator]
    with pytest.raises((ProcessExportError, SnapshotError), match=message):
        export_process_for_llm(tmp_path)


def test_tampered_or_incompatible_snapshot_fails_closed(tmp_path: Path) -> None:
    from doc_azure.process_export import ProcessExportError, export_process_for_llm

    seed_process_snapshot(tmp_path)
    source = resolve_snapshot_root(tmp_path / "out" / "process")
    (source / "process.json").write_text("{}\n")
    with pytest.raises(ProcessExportError, match="validation failed"):
        export_process_for_llm(tmp_path)

    other = tmp_path / "other"
    seed_process_snapshot(other)
    source = resolve_snapshot_root(other / "out" / "process")
    manifest = json.loads((source / "manifest.json").read_text())
    manifest["schema_version"] = 999
    (source / "manifest.json").write_text(json.dumps(manifest) + "\n")
    with pytest.raises(ProcessExportError, match="validation failed"):
        export_process_for_llm(other)


def test_write_failure_preserves_previous_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import doc_azure.process_export as process_export

    seed_process_snapshot(tmp_path)
    first = process_export.export_process_for_llm(tmp_path)
    current_path = tmp_path / "out" / "process-llm" / "CURRENT"
    before = current_path.read_bytes()
    process = expected_artifacts()["process.json"]
    process["description"] = "fonte alterada"
    publish_source(tmp_path, mutation=("process.json", process))

    def fail_write(*args: object, **kwargs: object) -> object:
        raise SnapshotError("simulated write failure")

    monkeypatch.setattr(process_export.SnapshotWriter, "write_text", fail_write)
    with pytest.raises(process_export.ProcessExportError, match="write failure"):
        process_export.export_process_for_llm(tmp_path)

    assert current_path.read_bytes() == before
    assert first.generation_root.is_dir()


def test_concurrent_different_export_after_commit_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import doc_azure.process_export as process_export

    seed_process_snapshot(tmp_path)
    real_commit = SnapshotWriter.commit_manifest
    raced = False

    def commit_then_race(
        writer: SnapshotWriter, *, collected_at: object, requests: object
    ) -> object:
        nonlocal raced
        result = real_commit(writer, collected_at=collected_at, requests=requests)
        if not raced and writer._root.name == "process-llm":
            raced = True
            competitor = SnapshotWriter(writer._root)
            competitor.write_text("README.md", "competitor\n")
            competitor.write_text("bundle.md", "competitor\n")
            competitor.write_text("process-summary.md", "competitor\n")
            competitor.write_json(
                "provenance.json",
                {
                    "schema_version": 1,
                    "source_generation": "f" * 32,
                    "source_manifest_sha256": "f" * 64,
                    "source_collected_at": COLLECTED_AT.isoformat(),
                    "process_id": PROCESS_ID,
                    "process_name": "Processo-Agil",
                    "scope": "process-only",
                    "omitted_properties": ["url"],
                    "work_item_type_counts": {"total": 0, "active": 0, "disabled": 0},
                },
            )
            real_commit(competitor, collected_at=collected_at, requests=())
        return result

    monkeypatch.setattr(SnapshotWriter, "commit_manifest", commit_then_race)

    with pytest.raises(process_export.ProcessExportError, match="different process source"):
        process_export.export_process_for_llm(tmp_path)


def test_cli_offline_never_loads_credentials_and_prints_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    seed_process_snapshot(tmp_path)
    script = load_script()

    def fail_settings(root: Path) -> object:
        raise AssertionError("offline export loaded credentials")

    assert script.main([], project_root=tmp_path, settings_loader=fail_settings) == 0
    output = capsys.readouterr().out
    assert output.startswith("LLM_EXPORT_OK\n")
    assert str((tmp_path / "out" / "process-llm").resolve()) in output


def test_cli_failure_is_sanitized(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    script = load_script()

    assert script.main([], project_root=tmp_path) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("LLM_EXPORT_FAILED: ")
    assert "Traceback" not in captured.err

    assert script.main(["--unknown"], project_root=tmp_path) == 1
    assert capsys.readouterr().err == (
        "LLM_EXPORT_FAILED: argumentos inválidos; execute com --help\n"
    )


def test_cli_names_invalid_export_current_and_documented_recovery_works(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from doc_azure.process_export import export_process_for_llm

    seed_process_snapshot(tmp_path)
    result = export_process_for_llm(tmp_path)
    result.bundle_path.write_text("tampered\n")
    script = load_script()

    assert script.main([], project_root=tmp_path) == 1
    assert capsys.readouterr().err == (
        "LLM_EXPORT_FAILED: out/process-llm/CURRENT está inválido; "
        "consulte o troubleshooting\n"
    )

    export_root = tmp_path / "out" / "process-llm"
    (export_root / "CURRENT").rename(export_root / "CURRENT.invalid")
    assert script.main([], project_root=tmp_path) == 0
    assert capsys.readouterr().out.startswith("LLM_EXPORT_OK\n")


def test_cli_refresh_uses_only_process_get_routes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script = load_script()
    payloads = fixture_payloads()
    requests: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        route = request.url.path.removeprefix("/bancodonordeste")
        return httpx.Response(200, json=payloads[route], request=request)

    def http_client_factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(transport))

    settings = Settings(
        organization="bancodonordeste",
        project="Torre CCR - Concessão de Crédito",
        page_ids=(35, 10, 9, 37),
        process_name="Processo-Agil",
        api_version="7.1",
        pat="fixture-only-pat",
        output_root=tmp_path / "out",
        wiki_id="fixture-wiki-id",
    )

    assert script.main(
        ["--refresh"],
        project_root=tmp_path,
        settings_loader=lambda root: settings,
        http_client_factory=http_client_factory,
        now=lambda: COLLECTED_AT,
    ) == 0
    assert requests
    assert {request.method for request in requests} == {"GET"}
    assert all("/_apis/work/processes" in request.url.path for request in requests)
    assert all("wiki" not in request.url.path.lower() for request in requests)
    assert capsys.readouterr().out.startswith("LLM_EXPORT_OK\n")


def test_real_cli_smoke_exports_without_network(tmp_path: Path) -> None:
    seed_process_snapshot(tmp_path)

    completed = subprocess.run(
        (
            "uv",
            "run",
            "--no-sync",
            "python",
            "scripts/export_process_for_llm.py",
            "--root",
            str(tmp_path),
        ),
        cwd=SCRIPT_PATH.parents[1],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.startswith("LLM_EXPORT_OK\n")
    assert (tmp_path / "out" / "process-llm" / "CURRENT").is_file()
