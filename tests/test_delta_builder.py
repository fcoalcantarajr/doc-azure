"""Tests for deterministic, offline construction of all four delta reports."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from delta.build import BuildError, build_all_reports
from delta.render import render_report as real_render_report
from doc_azure.snapshot import SnapshotWriter


PAGES = {
    35: "leiame",
    10: "politicas",
    9: "changelog",
    37: "apendice",
}
COLLECTED_AT = datetime(2026, 8, 24, tzinfo=timezone.utc)


def test_build_with_coverage_reports_missing_snapshots_as_build_error(
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[1]

    with pytest.raises(BuildError, match="snapshot validation failed"):
        build_all_reports(
            tmp_path,
            repository_root / "config/wiki_claims.json",
            tmp_path / "reports",
            coverage_baseline=repository_root / "config/document-coverage.json",
        )


def seed_catalog_and_wiki(root: Path) -> Path:
    writer = SnapshotWriter(root / "out" / "wiki")
    claims: list[dict[str, object]] = []
    for page_id, slug in PAGES.items():
        text = f"# {slug}\nAlegação {slug}\n"
        writer.write_text(f"{slug}.md", text)
        claims.append(
            {
                "id": f"{page_id}-LIMIT-001",
                "page_id": page_id,
                "slug": slug,
                "finding": f"Limite de verificação de {slug}",
                "doc": {
                    "path": f"out/wiki/{slug}.md",
                    "line": 2,
                    "excerpt": f"Alegação {slug}",
                    "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "value": "descrito",
                },
                "check": {
                    "kind": "limitation",
                    "implemented": "A API de processo não representa essa dimensão.",
                },
                "limit": "Não é possível confirmar pela API de processo.",
            }
        )
    writer.commit_manifest(collected_at=COLLECTED_AT, requests=())
    process = SnapshotWriter(root / "out" / "process")
    process.write_json(
        "process.json",
        {"name": "Processo-Agil", "typeId": "9d82e632-9028-4a6b-86f8-3edb3281cb15"},
    )
    process.commit_manifest(collected_at=COLLECTED_AT, requests=())
    catalog = root / "claims.json"
    catalog.write_text(
        json.dumps({"schema_version": 1, "claims": claims}),
        encoding="utf-8",
    )
    return catalog


def test_build_all_reports_is_deterministic_and_returns_fixed_slug_order(
    tmp_path: Path,
) -> None:
    catalog = seed_catalog_and_wiki(tmp_path)
    output = tmp_path / "reports"

    first = build_all_reports(tmp_path, catalog, output)
    first_bytes = {path.name: path.read_bytes() for path in first}
    second = build_all_reports(tmp_path, catalog, output)

    assert tuple(path.name for path in first) == (
        "leiame.md",
        "politicas.md",
        "changelog.md",
        "apendice.md",
    )
    assert first_bytes == {path.name: path.read_bytes() for path in second}
    report = first[0].read_text(encoding="utf-8")
    assert "## Proveniência dos snapshots" in report
    assert "Processo-Agil" in report
    assert "9d82e632-9028-4a6b-86f8-3edb3281cb15" in report


def test_build_rejects_snapshot_generation_that_changes_after_metadata_capture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    catalog = seed_catalog_and_wiki(tmp_path)
    output = tmp_path / "reports"
    changed = False

    def change_wiki_generation(result: object, provenance: object) -> str:
        nonlocal changed
        if not changed:
            changed = True
            replacement = SnapshotWriter(tmp_path / "out" / "wiki")
            for slug in PAGES.values():
                replacement.write_text(slug + ".md", f"# {slug}\nAlegação {slug}\n")
            replacement.commit_manifest(collected_at=COLLECTED_AT, requests=())
        return real_render_report(result, provenance)  # type: ignore[arg-type]

    monkeypatch.setattr("delta.build.render_report", change_wiki_generation)

    with pytest.raises(BuildError, match="changed during report build"):
        build_all_reports(tmp_path, catalog, output)

    assert not output.exists()


def test_build_all_reports_rejects_a_missing_fixed_page_before_writing(
    tmp_path: Path,
) -> None:
    catalog = seed_catalog_and_wiki(tmp_path)
    payload = json.loads(catalog.read_text(encoding="utf-8"))
    payload["claims"] = payload["claims"][:-1]
    catalog.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "reports"

    with pytest.raises(BuildError, match="exactly the four fixed pages"):
        build_all_reports(tmp_path, catalog, output)

    assert not output.exists()


def test_build_all_reports_preserves_existing_outputs_on_evaluation_failure(
    tmp_path: Path,
) -> None:
    catalog = seed_catalog_and_wiki(tmp_path)
    output = tmp_path / "reports"
    output.mkdir()
    sentinel = output / "leiame.md"
    sentinel.write_text("unchanged\n", encoding="utf-8")
    payload = json.loads(catalog.read_text(encoding="utf-8"))
    payload["claims"][2]["doc"]["line"] = 99
    catalog.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(BuildError, match="claim evaluation failed"):
        build_all_reports(tmp_path, catalog, output)

    assert sentinel.read_text(encoding="utf-8") == "unchanged\n"
    assert sorted(path.name for path in output.iterdir()) == ["leiame.md"]


def test_build_all_reports_rolls_back_every_replaced_report_on_publish_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    catalog = seed_catalog_and_wiki(tmp_path)
    output = tmp_path / "reports"
    build_all_reports(tmp_path, catalog, output)
    original = {}
    for path in output.iterdir():
        body = f"previous-{path.name}\n".encode()
        path.write_bytes(body)
        original[path.name] = body

    real_replace = os.replace
    publication_calls = 0
    failed = False

    def fail_third_publication(source: object, destination: object) -> None:
        nonlocal publication_calls, failed
        if Path(destination).parent == output and not failed:
            publication_calls += 1
            if publication_calls == 3:
                failed = True
                raise OSError("simulated publication failure")
        real_replace(source, destination)

    monkeypatch.setattr("delta.build.os.replace", fail_third_publication)

    with pytest.raises(BuildError, match="publication failed"):
        build_all_reports(tmp_path, catalog, output)

    assert {
        path.name: path.read_bytes() for path in output.iterdir() if not path.name.startswith(".")
    } == original
    assert not tuple(output.glob(".*.tmp"))
