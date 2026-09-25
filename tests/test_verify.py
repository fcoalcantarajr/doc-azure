"""Adversarial tests for the repository truth-checking gate."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from delta.build import build_all_reports
from doc_azure.snapshot import (
    SnapshotError,
    SnapshotWriter,
    read_snapshot_artifact,
    resolve_snapshot_root,
)
from verify import (
    VerificationError,
    main as verify_main,
    run_checked,
    verify_gitignore,
    verify_layout,
    verify_notion_artifacts,
    verify_reports,
    verify_coverage_baselines,
    verify_secret_literals,
)
from tests.test_audit_runtime import seed_run
from tests.test_process_collector import expected_artifacts, seed_process_snapshot


PAGES = ((35, "leiame"), (10, "politicas"), (9, "changelog"), (37, "apendice"))
COLLECTED_AT = datetime(2026, 8, 24, tzinfo=timezone.utc)


def test_verify_layout_uses_current_document_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: list[str] = []

    def record_required(path: Path) -> bool:
        observed.append(path.relative_to(tmp_path).as_posix())
        return True

    monkeypatch.setattr("verify._is_nonempty_regular_file", record_required)

    verify_layout(tmp_path)

    assert "docs/reference/delta-method.md" in observed
    assert "docs/archive/session-2026-08-26.md" in observed
    assert "scripts/export_process_for_llm.py" in observed
    assert "src/doc_azure/process_export.py" in observed
    assert "src/doc_azure/process_export_delta.py" in observed
    assert "src/doc_azure/process_export_delta_render.py" in observed
    assert "src/doc_azure/process_export_render.py" in observed
    assert "docs/guides/export-process-for-llm.md" in observed
    assert "docs/delta-method.md" not in observed
    assert "docs/session-2026-08-26.md" not in observed


def test_main_reports_snapshot_failure_without_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_gate(*args: object, **kwargs: object) -> None:
        raise SnapshotError("snapshot root has no complete CURRENT")

    monkeypatch.setattr("verify.verify_repository", fail_gate)

    assert verify_main([]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "GATE_FAIL: snapshot root has no complete CURRENT\n"


def seed_verified_repository(root: Path) -> Path:
    wiki_writer = SnapshotWriter(root / "out" / "wiki")
    claims: list[dict[str, object]] = []
    for index, (page_id, slug) in enumerate(PAGES):
        body = f"# {slug}\nProcesso-Agil\nLinha alternativa {slug}\n"
        wiki_writer.write_text(f"{slug}.md", body)
        check: dict[str, object]
        if index == 0:
            check = {
                "kind": "equals",
                "artifact": "process.json",
                "pointer": "/name",
                "expected": "Processo-Agil",
            }
        else:
            check = {
                "kind": "limitation",
                "implemented": "A API não representa esta afirmação.",
            }
        claims.append(
            {
                "id": f"{page_id}-VERIFY-001",
                "page_id": page_id,
                "slug": slug,
                "finding": f"Verificação de {slug}",
                "doc": {
                    "path": f"out/wiki/{slug}.md",
                    "line": 2,
                    "excerpt": "Processo-Agil",
                    "sha256": hashlib.sha256(body.encode()).hexdigest(),
                    "value": "Processo-Agil",
                },
                "check": check,
                "limit": "A diferença altera a interpretação documental.",
            }
        )
    wiki_writer.commit_manifest(collected_at=COLLECTED_AT, requests=())

    process_writer = SnapshotWriter(root / "out" / "process")
    process_writer.write_json(
        "process.json",
        {
            "name": "Processo-Agil",
            "typeId": "9d82e632-9028-4a6b-86f8-3edb3281cb15",
        },
    )
    process_writer.commit_manifest(collected_at=COLLECTED_AT, requests=())

    catalog = root / "config" / "wiki_claims.json"
    catalog.parent.mkdir()
    catalog.write_text(
        json.dumps({"schema_version": 1, "claims": claims}),
        encoding="utf-8",
    )
    build_all_reports(root, catalog, root / "deltas")
    return catalog


def mutate_catalog(catalog: Path, mutation: object) -> None:
    payload = json.loads(catalog.read_text(encoding="utf-8"))
    mutation(payload)
    catalog.write_text(json.dumps(payload), encoding="utf-8")


def test_verify_reports_accepts_exact_unmodified_outputs_without_mutation(
    tmp_path: Path,
) -> None:
    seed_verified_repository(tmp_path)
    before = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (tmp_path / "deltas").iterdir()
    }

    verify_reports(tmp_path)

    after = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (tmp_path / "deltas").iterdir()
    }
    assert after == before


def test_verify_reports_ignores_run_specific_snapshot_provenance(
    tmp_path: Path,
) -> None:
    """A fresh equivalent collection must not invalidate stable reports."""

    seed_verified_repository(tmp_path)
    wiki_root = tmp_path / "out" / "wiki"
    process_root = tmp_path / "out" / "process"
    process_source = resolve_snapshot_root(process_root)

    wiki_writer = SnapshotWriter(wiki_root)
    for _, slug in PAGES:
        wiki_writer.write_text(
            f"{slug}.md",
            read_snapshot_artifact(wiki_root, f"{slug}.md").decode("utf-8"),
        )
    wiki_writer.commit_manifest(
        collected_at=COLLECTED_AT.replace(day=25), requests=()
    )

    process_writer = SnapshotWriter(process_root)
    process_writer.write_text(
        "process.json",
        read_snapshot_artifact(process_source, "process.json").decode("utf-8"),
    )
    process_writer.commit_manifest(
        collected_at=COLLECTED_AT.replace(day=25), requests=()
    )

    verify_reports(tmp_path)


def test_verify_reports_rejects_unverifiable_versioned_provenance(
    tmp_path: Path,
) -> None:
    seed_verified_repository(tmp_path)
    report = tmp_path / "deltas" / "leiame.md"
    report.write_text(
        re.sub(
            r"- Wiki: coletada em `[^`]+`; geração `[^`]+`; "
            r"SHA-256 do manifesto `[^`]+`\.",
            "- Wiki: coletada em `2026-08-24T00:00:00+00:00`; "
            f"geração `{'0' * 32}`; SHA-256 do manifesto `{'0' * 64}`.",
            report.read_text(encoding="utf-8"),
            count=1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(VerificationError, match="provenance"):
        verify_reports(tmp_path)


def test_verify_reports_rejects_resolvable_but_wrong_json_pointer(
    tmp_path: Path,
) -> None:
    catalog = seed_verified_repository(tmp_path)
    mutate_catalog(
        catalog,
        lambda payload: payload["claims"][0]["check"].update(pointer="/typeId"),
    )

    with pytest.raises(VerificationError, match="differs from verified rebuild"):
        verify_reports(tmp_path)


def test_verify_reports_rejects_nearby_instead_of_exact_wiki_line(
    tmp_path: Path,
) -> None:
    catalog = seed_verified_repository(tmp_path)
    mutate_catalog(
        catalog,
        lambda payload: payload["claims"][0]["doc"].update(
            line=3, excerpt="Linha alternativa leiame"
        ),
    )

    with pytest.raises(VerificationError, match="differs from verified rebuild"):
        verify_reports(tmp_path)


def test_verify_reports_rejects_report_status_mutation(tmp_path: Path) -> None:
    seed_verified_repository(tmp_path)
    report = tmp_path / "deltas" / "leiame.md"
    report.write_text(
        report.read_text(encoding="utf-8").replace(
            "CONFIRMADO", "DIVERGENTE", 1
        ),
        encoding="utf-8",
    )

    with pytest.raises(VerificationError, match="differs from verified rebuild"):
        verify_reports(tmp_path)


def test_verify_reports_rejects_a_symlink_even_with_identical_bytes(
    tmp_path: Path,
) -> None:
    seed_verified_repository(tmp_path)
    report = tmp_path / "deltas" / "leiame.md"
    external = tmp_path / "external.md"
    external.write_bytes(report.read_bytes())
    report.unlink()
    report.symlink_to(external)

    with pytest.raises(VerificationError, match="regular file"):
        verify_reports(tmp_path)


def test_verify_coverage_baselines_rejects_missing_versioned_contract(tmp_path):
    seed_verified_repository(tmp_path)
    with pytest.raises(VerificationError, match="coverage baseline"):
        verify_coverage_baselines(tmp_path)


def seed_versioned_coverage_baselines(root: Path) -> Path:
    catalog, documents, process = seed_run(root)
    config = root / "config"
    config.mkdir()
    (config / "wiki_claims.json").write_bytes(catalog.read_bytes())
    (config / "document-coverage.json").write_bytes(documents.read_bytes())
    process_path = config / "process-coverage.json"
    process_path.write_bytes(process.read_bytes())
    return process_path


def test_verify_coverage_baselines_rejects_missing_process_source(tmp_path):
    process_path = seed_versioned_coverage_baselines(tmp_path)
    payload = json.loads(process_path.read_bytes())
    del payload["source"]
    process_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(VerificationError, match="process coverage baseline schema"):
        verify_coverage_baselines(tmp_path)


@pytest.mark.parametrize("corruption", ["manifest_hash", "entries"])
def test_verify_coverage_baselines_rejects_unverifiable_process_source(
    tmp_path, corruption
):
    process_path = seed_versioned_coverage_baselines(tmp_path)
    payload = json.loads(process_path.read_bytes())
    if corruption == "manifest_hash":
        payload["source"]["manifest_sha256"] = "0" * 64
    else:
        first_entry = next(iter(payload["entries"]))
        payload["entries"][first_entry] = "0" * 64
    process_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(VerificationError, match="coverage baseline is invalid"):
        verify_coverage_baselines(tmp_path)


def test_verify_coverage_baselines_uses_matching_full_api_current_after_clone(
    tmp_path,
):
    process_path = seed_versioned_coverage_baselines(tmp_path)
    source_generation = json.loads(process_path.read_bytes())["source"]["generation_id"]
    seed_process_snapshot(tmp_path, collection_mode="full_api")
    current_generation = resolve_snapshot_root(tmp_path / "out" / "process").name
    assert current_generation != source_generation
    shutil.rmtree(tmp_path / "out" / "process" / "snapshots" / source_generation)

    verify_coverage_baselines(tmp_path)


@pytest.mark.parametrize("current_mode", ["cache_assisted", "content_drift"])
def test_verify_coverage_baselines_rejects_unverifiable_clone_current(
    tmp_path, current_mode
):
    process_path = seed_versioned_coverage_baselines(tmp_path)
    source_generation = json.loads(process_path.read_bytes())["source"]["generation_id"]
    custom_text = None
    if current_mode == "content_drift":
        changed_process = expected_artifacts()["process.json"]
        changed_process["unmappedProperty"] = "new"
        custom_text = {"process.json": json.dumps(changed_process)}
    seed_process_snapshot(
        tmp_path,
        collection_mode=(
            "cache_assisted" if current_mode == "cache_assisted" else "full_api"
        ),
        custom_text=custom_text,
    )
    shutil.rmtree(tmp_path / "out" / "process" / "snapshots" / source_generation)

    with pytest.raises(VerificationError, match="coverage baseline is invalid"):
        verify_coverage_baselines(tmp_path)


def test_run_checked_rejects_failed_subprocess_without_echoing_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    secret_output = "do-not-echo-this-output"

    def failed_run(*args: object, **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(args[0], 7, secret_output, secret_output)

    monkeypatch.setattr("verify.subprocess.run", failed_run)
    with pytest.raises(VerificationError) as raised:
        run_checked(("tool", "check"), tmp_path)

    assert secret_output not in str(raised.value)


def test_verify_secret_literals_rejects_env_value_without_disclosing_it(
    tmp_path: Path,
) -> None:
    secret = "unique-sensitive-value-987654"
    (tmp_path / ".env").write_text(f"AZDO_PAT={secret}\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "leak.md").write_text(f"accidental {secret}\n", encoding="utf-8")

    with pytest.raises(VerificationError) as raised:
        verify_secret_literals(tmp_path)

    assert secret not in str(raised.value)
    assert "docs/leak.md" in str(raised.value)


def test_verify_gitignore_requires_every_requested_category(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")

    with pytest.raises(VerificationError, match="gitignore category"):
        verify_gitignore(tmp_path)


def test_repository_gitignore_covers_every_requested_category() -> None:
    verify_gitignore(Path(__file__).parents[1])


def test_require_publication_delegates_to_the_strict_external_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[Path] = []
    monkeypatch.setattr(
        "verify.verify_publication_gate",
        lambda root: calls.append(Path(root)),
        raising=False,
    )

    verify_notion_artifacts(tmp_path, require_fetched=True)

    assert calls == [tmp_path]
