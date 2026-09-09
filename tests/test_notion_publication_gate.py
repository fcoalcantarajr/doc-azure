"""Adversarial tests for the Notion review and publication gate."""

from __future__ import annotations

import csv
import hashlib
import inspect
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from delta import notion as notion_module
from delta.notion import NotionPublicationError, prepare_notion


STATUSES = (
    "CONFIRMADO",
    "DIVERGENTE",
    "NAO_VERIFICAVEL_API_PROCESSO",
    "AMBIGUO",
)


def _report(slug: str, finding_id: str) -> str:
    return f"""# Delta — {slug}

DELTA-AUDIT-MARKER-{slug}

## Metodologia e status

Este relatório compara documento e configuração atual.

- `CONFIRMADO`: valores iguais.
- `DIVERGENTE`: valores diferentes.
- `NAO_VERIFICAVEL_API_PROCESSO`: API insuficiente.
- `AMBIGUO`: mais de uma interpretação.

## Proveniência dos snapshots

- Wiki: coletada em `2026-08-26T13:59:02+00:00`; geração `wiki-generation`; SHA-256 do manifesto `{'a' * 64}`.
- Processo: coletado em `2026-08-26T13:59:14+00:00`; geração `process-generation`; SHA-256 do manifesto `{'b' * 64}`.
- Processo avaliado: `Processo-Agil` (ID `9d82e632-9028-4a6b-86f8-3edb3281cb15`).
- Os caminhos lógicos resolvem pelas gerações acima.

## Resumo por status

| Status | Quantidade |
| --- | ---: |
| CONFIRMADO | 1 |
| DIVERGENTE | 0 |
| NAO_VERIFICAVEL_API_PROCESSO | 0 |
| AMBIGUO | 0 |

## Achados detalhados

| ID | Achado | Status | Documentado | Implementado | Evidência documental | Evidência Azure | Impacto ou limite |
| --- | --- | --- | --- | --- | --- | --- | --- |
| {finding_id} | Achado {slug} | CONFIRMADO | esperado | observado | out/wiki/{slug}.md#L1 | out/process/process.json#/name | limite {slug} |
"""


def _seed_reports(root: Path) -> None:
    delta_root = root / "deltas"
    delta_root.mkdir(parents=True)
    for index, slug in enumerate(("leiame", "politicas", "changelog", "apendice")):
        (delta_root / f"{slug}.md").write_text(
            _report(slug, f"{index + 1}-CLAIM-001"), encoding="utf-8"
        )


def _function(name: str):
    candidate = getattr(notion_module, name, None)
    assert callable(candidate), f"missing Notion gate function: {name}"
    return candidate


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _connector_result(payload: dict[str, object]) -> str:
    return json.dumps(
        {
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "isError": False,
        }
    )


def _fetch_connector_result(
    *,
    title: str,
    url: str,
    parent_id: str | None,
    body: str,
    as_of: str,
    last_edited: str,
) -> str:
    parent = ""
    if parent_id is not None:
        parent = (
            "<ancestor-path>\n"
            f'<parent-page url="https://app.notion.com/p/{parent_id.replace("-", "")}" '
            'title="Azure"/>\n'
            "</ancestor-path>\n"
        )
    return _connector_result(
        {
            "metadata": {"type": "page"},
            "title": title,
            "url": url,
            "text": (
                f'Here is the result of "fetch" as of {as_of}:\n'
                f'<page url="{url}">\n'
                f"{parent}"
                "<properties>\n"
                f"{json.dumps({'title': title}, ensure_ascii=False)}\n"
                "</properties>\n"
                "<content>\n"
                f"{body}\n"
                "</content>\n"
                "</page>"
            ),
            "page_last_edited_at": last_edited,
        }
    )


def test_prepare_notion_renders_semantically_equivalent_notion_tables(
    tmp_path: Path,
) -> None:
    _seed_reports(tmp_path)

    manifest = prepare_notion(tmp_path)

    parse_report = _function("parse_report_semantics")
    parse_notion = _function("parse_notion_semantics")
    for entry in manifest.entries:
        source = (tmp_path / "deltas" / f"{entry.slug}.md").read_text(
            encoding="utf-8"
        )
        prepared_path = tmp_path / entry.prepared_path
        prepared = prepared_path.read_text(encoding="utf-8")
        assert '<table fit-page-width="true" header-row="true">' in prepared
        assert "| ID | Achado |" not in prepared
        source_semantics = parse_report(source, entry.slug)
        prepared_semantics = parse_notion(prepared, entry.slug)
        assert prepared_semantics == source_semantics
        assert entry.semantic_sha256 == source_semantics.sha256


def test_prepare_notion_uses_the_existing_full_titles(tmp_path: Path) -> None:
    _seed_reports(tmp_path)

    manifest = prepare_notion(tmp_path)

    assert all(entry.title.startswith("Delta —") for entry in manifest.entries)


def test_prepare_review_packet_is_deterministic_and_mentions_private_github(
    tmp_path: Path,
) -> None:
    _seed_reports(tmp_path)
    assert "repository_url" in inspect.signature(prepare_notion).parameters

    first = prepare_notion(
        tmp_path,
        repository_url="https://github.com/example/doc-azure",
    )
    review_root = tmp_path / "out" / "notion" / "review"
    first_bytes = {
        path.name: path.read_bytes()
        for path in review_root.iterdir()
        if path.is_file()
    }
    second = prepare_notion(
        tmp_path,
        repository_url="https://github.com/example/doc-azure",
    )

    assert second == first
    assert first_bytes == {
        path.name: path.read_bytes()
        for path in review_root.iterdir()
        if path.is_file()
    }
    prompt = (review_root / "prompt.txt").read_text(encoding="utf-8")
    assert "https://github.com/example/doc-azure" in prompt
    assert "acesso ao GitHub" in prompt
    for required in (
        "tente falsificar",
        "falsos MATCH",
        "gaps de cobertura",
        "dependências ocultas de IA",
        "fail-open",
        "não determinismo",
        "sem IA",
        "Kimi K3",
        "Opus 5",
        "esforço máximo",
    ):
        assert required in prompt
    with (review_root / "packet.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 4
    assert rows[0]["claim_id"] == "1-CLAIM-001"
    assert rows[0]["evidence_azure"] == "out/process/process.json#/name"


def test_prepare_review_packet_rejects_secret_like_content(tmp_path: Path) -> None:
    _seed_reports(tmp_path)
    report = tmp_path / "deltas" / "leiame.md"
    report.write_text(
        report.read_text(encoding="utf-8").replace(
            "limite leiame", "Authorization: Bearer leaked-value"
        ),
        encoding="utf-8",
    )

    with pytest.raises(NotionPublicationError, match="sensitive"):
        prepare_notion(
            tmp_path,
            repository_url="https://github.com/example/doc-azure",
        )


def _seed_review_gate(root: Path) -> object:
    manifest = prepare_notion(
        root,
        repository_url="https://github.com/example/doc-azure",
    )
    review_root = root / "out" / "notion" / "review"
    review_manifest = json.loads(
        (review_root / "review-manifest.json").read_text(encoding="utf-8")
    )
    now = datetime(2026, 8, 26, 14, 0, tzinfo=timezone.utc)
    responses = review_root / "responses"
    receipts = review_root / "receipts"
    responses.mkdir()
    receipts.mkdir()
    response_hashes: dict[str, str] = {}
    for offset, (slug, model) in enumerate(
        (("kimi-k3", "Kimi K3"), ("opus-5", "Opus 5"))
    ):
        response_path = responses / f"{slug}.md"
        response_path.write_text(f"# {model}\n\nPASS\n", encoding="utf-8")
        response_hashes[model] = _sha(response_path)
        raw_path = review_root / "raw" / f"{slug}.json"
        raw_path.parent.mkdir(exist_ok=True)
        model_verified_at = (now + timedelta(minutes=offset)).isoformat()
        effort_verified_at = (now + timedelta(minutes=offset)).isoformat()
        sent_at = (now + timedelta(minutes=offset + 1)).isoformat()
        completed_at = (now + timedelta(minutes=offset + 2)).isoformat()
        raw_path.write_text(
            _connector_result(
                {
                    "surface": "chatgpt-integrated-browser",
                    "chat_id": f"chat-{offset}",
                    "chat_url": f"https://app.notion.com/chat-{offset}",
                    "model": model,
                    "effort": "maximum",
                    "packet_name": "packet.csv",
                    "packet_sha256": review_manifest["packet_sha256"],
                    "prompt_sha256": review_manifest["prompt_sha256"],
                    "model_verified_at": model_verified_at,
                    "effort_verified_at": effort_verified_at,
                    "sent_at": sent_at,
                    "completed_at": completed_at,
                    "response_markdown": response_path.read_text(encoding="utf-8"),
                }
            ),
            encoding="utf-8",
        )
        receipt = {
            "schema_version": 1,
            "model": model,
            "effort": "maximum",
            "surface": "chatgpt-integrated-browser",
            "packet_sha256": review_manifest["packet_sha256"],
            "prompt_sha256": review_manifest["prompt_sha256"],
            "chat_id": f"chat-{offset}",
            "chat_url": f"https://app.notion.com/chat-{offset}",
            "model_verified_at": model_verified_at,
            "effort_verified_at": effort_verified_at,
            "sent_at": sent_at,
            "completed_at": completed_at,
            "verdict": "PASS",
            "response_path": str(response_path.relative_to(root)),
            "response_sha256": response_hashes[model],
            "browser_result_path": str(raw_path.relative_to(root)),
            "browser_result_sha256": _sha(raw_path),
            "findings": [],
        }
        (receipts / f"{slug}.json").write_text(
            json.dumps(receipt, indent=2), encoding="utf-8"
        )
    reconciliation = {
        "schema_version": 1,
        "packet_sha256": review_manifest["packet_sha256"],
        "review_response_hashes": response_hashes,
        "reconciled_at": (now + timedelta(minutes=5)).isoformat(),
        "outcome": "no material changes required",
        "report_semantic_hashes": review_manifest["report_semantic_hashes"],
        "decisions": [],
    }
    (review_root / "reconciliation.json").write_text(
        json.dumps(reconciliation, indent=2), encoding="utf-8"
    )
    return manifest


def test_review_gate_accepts_two_independent_bound_reviews(tmp_path: Path) -> None:
    _seed_reports(tmp_path)
    _seed_review_gate(tmp_path)

    _function("verify_review_gate")(tmp_path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("model", "Other", "model"),
        ("effort", "high", "effort"),
        ("surface", "external-notion-app", "surface"),
        ("packet_sha256", "0" * 64, "packet"),
    ),
)
def test_review_gate_rejects_wrong_review_identity(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    _seed_reports(tmp_path)
    _seed_review_gate(tmp_path)
    receipt = tmp_path / "out" / "notion" / "review" / "receipts" / "kimi-k3.json"
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload[field] = value
    receipt.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(NotionPublicationError, match=message):
        _function("verify_review_gate")(tmp_path)


def test_review_gate_rejects_reused_chat_and_missing_response(tmp_path: Path) -> None:
    _seed_reports(tmp_path)
    _seed_review_gate(tmp_path)
    root = tmp_path / "out" / "notion" / "review"
    kimi = json.loads((root / "receipts" / "kimi-k3.json").read_text())
    opus_path = root / "receipts" / "opus-5.json"
    opus = json.loads(opus_path.read_text())
    opus["chat_id"] = kimi["chat_id"]
    opus_path.write_text(json.dumps(opus), encoding="utf-8")

    with pytest.raises(NotionPublicationError, match="chat"):
        _function("verify_review_gate")(tmp_path)

    opus["chat_id"] = "chat-1"
    opus_path.write_text(json.dumps(opus), encoding="utf-8")
    (root / "responses" / "opus-5.md").unlink()
    with pytest.raises(NotionPublicationError, match="response"):
        _function("verify_review_gate")(tmp_path)


def test_review_gate_cross_checks_receipt_against_raw_browser_result(
    tmp_path: Path,
) -> None:
    _seed_reports(tmp_path)
    _seed_review_gate(tmp_path)
    review_root = tmp_path / "out" / "notion" / "review"
    receipt_path = review_root / "receipts" / "kimi-k3.json"
    receipt = json.loads(receipt_path.read_text())
    response = (tmp_path / receipt["response_path"]).read_text(encoding="utf-8")
    raw_path = review_root / "raw-kimi.json"
    raw_path.write_text(
        _connector_result(
            {
                "surface": receipt["surface"],
                "chat_id": receipt["chat_id"],
                "chat_url": receipt["chat_url"],
                "model": "Other",
                "effort": receipt["effort"],
                "packet_name": "packet.csv",
                "packet_sha256": receipt["packet_sha256"],
                "prompt_sha256": receipt["prompt_sha256"],
                "model_verified_at": receipt["model_verified_at"],
                "effort_verified_at": receipt["effort_verified_at"],
                "sent_at": receipt["sent_at"],
                "completed_at": receipt["completed_at"],
                "response_markdown": response,
            }
        ),
        encoding="utf-8",
    )
    receipt["browser_result_path"] = str(raw_path.relative_to(tmp_path))
    receipt["browser_result_sha256"] = _sha(raw_path)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(NotionPublicationError, match="browser result"):
        _function("verify_review_gate")(tmp_path)


def test_review_gate_rejects_stale_or_incomplete_reconciliation(tmp_path: Path) -> None:
    _seed_reports(tmp_path)
    _seed_review_gate(tmp_path)
    review_root = tmp_path / "out" / "notion" / "review"
    receipt_path = review_root / "receipts" / "kimi-k3.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["findings"] = [
        {"id": "K-1", "severity": "important", "summary": "Material issue"}
    ]
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(NotionPublicationError, match="reconciliation"):
        _function("verify_review_gate")(tmp_path)

    receipt["findings"] = []
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    report = tmp_path / "deltas" / "leiame.md"
    report.write_text(
        report.read_text(encoding="utf-8").replace("limite leiame", "novo limite"),
        encoding="utf-8",
    )
    with pytest.raises(NotionPublicationError, match="stale"):
        _function("verify_review_gate")(tmp_path)


def _seed_publication_gate(root: Path) -> object:
    manifest = _seed_review_gate(root)
    notion_root = root / "out" / "notion"
    fetched_root = notion_root / "fetched"
    raw_root = notion_root / "raw"
    fetched_root.mkdir()
    raw_root.mkdir()
    update_time = datetime(2026, 8, 26, 15, 0, tzinfo=timezone.utc)
    for entry in manifest.entries:
        prepared = root / entry.prepared_path
        fetched_body = fetched_root / f"{entry.slug}.md"
        fetched_body.write_bytes(prepared.read_bytes())
        raw_fetch = raw_root / f"{entry.slug}-fetch.json"
        raw_update = raw_root / f"{entry.slug}-update.json"
        raw_fetch.write_text(
            _fetch_connector_result(
                title=entry.title,
                url=entry.url,
                parent_id=entry.parent_page_id,
                body=fetched_body.read_text(encoding="utf-8"),
                as_of=(update_time + timedelta(minutes=1)).isoformat(),
                last_edited=(update_time + timedelta(minutes=1)).isoformat(),
            ),
            encoding="utf-8",
        )
        raw_update.write_text(
            _connector_result(
                {"page_id": entry.page_id, "url": entry.url, "status": "updated"}
            ),
            encoding="utf-8",
        )
        receipt = {
            "schema_version": 1,
            "slug": entry.slug,
            "title": entry.title,
            "page_id": entry.page_id,
            "parent_page_id": entry.parent_page_id,
            "url": entry.url,
            "marker": entry.marker,
            "updated_at": update_time.isoformat(),
            "fetched_at": (update_time + timedelta(minutes=1)).isoformat(),
            "connector_as_of": (update_time + timedelta(minutes=1)).isoformat(),
            "last_edited_available": True,
            "last_edited_time": (update_time + timedelta(minutes=1)).isoformat(),
            "semantic_sha256": entry.semantic_sha256,
            "raw_fetch_path": str(raw_fetch.relative_to(root)),
            "raw_fetch_sha256": _sha(raw_fetch),
            "update_receipt_path": str(raw_update.relative_to(root)),
            "update_receipt_sha256": _sha(raw_update),
        }
        (fetched_root / f"{entry.slug}.json").write_text(
            json.dumps(receipt, indent=2), encoding="utf-8"
        )
    parent_raw = raw_root / "parent-fetch.json"
    hub_raw = raw_root / "hub-fetch.json"
    parent_raw.write_text(
        _fetch_connector_result(
            title="Azure",
            url=(
                "https://app.notion.com/p/"
                + manifest.parent_page_id.replace("-", "")
            ),
            parent_id=None,
            body="Parent page",
            as_of=(update_time + timedelta(minutes=2)).isoformat(),
            last_edited=(update_time + timedelta(minutes=2)).isoformat(),
        ),
        encoding="utf-8",
    )
    hub_id = "3c3412e0-8c26-809d-8e12-e5498b5fde60"
    hub_raw.write_text(
        _fetch_connector_result(
            title="Sessão com Codex - Delta do Azure",
            url="https://app.notion.com/p/" + hub_id.replace("-", ""),
            parent_id=manifest.parent_page_id,
            body="Hub page",
            as_of=(update_time + timedelta(minutes=2)).isoformat(),
            last_edited=(update_time + timedelta(minutes=2)).isoformat(),
        ),
        encoding="utf-8",
    )
    hierarchy = {
        "schema_version": 1,
        "parent_page_id": manifest.parent_page_id,
        "parent_title": "Azure",
        "hub_page_id": "3c3412e0-8c26-809d-8e12-e5498b5fde60",
        "fetched_at": (update_time + timedelta(minutes=2)).isoformat(),
        "parent_fetch_path": str(parent_raw.relative_to(root)),
        "parent_fetch_sha256": _sha(parent_raw),
        "hub_fetch_path": str(hub_raw.relative_to(root)),
        "hub_fetch_sha256": _sha(hub_raw),
        "pages": [
            {
                "page_id": entry.page_id,
                "title": entry.title,
                "parent_page_id": entry.parent_page_id,
                "url": entry.url,
            }
            for entry in manifest.entries
        ],
    }
    (fetched_root / "hierarchy.json").write_text(
        json.dumps(hierarchy, indent=2), encoding="utf-8"
    )
    searches = []
    for entry in manifest.entries:
        for kind, query in (
            ("page_id", entry.page_id),
            ("title", entry.title),
            ("marker", entry.marker),
        ):
            raw_path = raw_root / f"search-{entry.slug}-{kind}.json"
            raw_path.write_text(
                _connector_result(
                    {
                        "results": [
                            {
                                "id": entry.page_id,
                                "title": entry.title,
                                "url": entry.url,
                                "type": "page",
                                "highlight": entry.marker,
                            }
                        ],
                        "type": "workspace_search",
                    }
                ),
                encoding="utf-8",
            )
            searches.append(
                {
                    "slug": entry.slug,
                    "kind": kind,
                    "query": query,
                    "scope_parent_page_id": manifest.parent_page_id,
                    "expected_page_id": entry.page_id,
                    "matched_page_ids": [entry.page_id],
                    "searched_at": (update_time + timedelta(minutes=3)).isoformat(),
                    "raw_search_path": str(raw_path.relative_to(root)),
                    "raw_search_sha256": _sha(raw_path),
                }
            )
    (fetched_root / "duplicate-search.json").write_text(
        json.dumps({"schema_version": 1, "searches": searches}, indent=2),
        encoding="utf-8",
    )
    return manifest


def test_publication_gate_accepts_semantic_readback_and_external_provenance(
    tmp_path: Path,
) -> None:
    _seed_reports(tmp_path)
    _seed_publication_gate(tmp_path)

    _function("verify_publication_gate")(tmp_path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("title", "title"),
        ("parent", "parent"),
        ("duplicate", "duplicate"),
        ("raw", "raw"),
        ("freshness", "fresh"),
        ("row", "semantic"),
    ),
)
def test_publication_gate_rejects_adversarial_receipts(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    _seed_reports(tmp_path)
    manifest = _seed_publication_gate(tmp_path)
    fetched = tmp_path / "out" / "notion" / "fetched"
    receipt_path = fetched / "leiame.json"
    receipt = json.loads(receipt_path.read_text())
    if mutation == "title":
        receipt["title"] = "wrong"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    elif mutation == "parent":
        receipt["parent_page_id"] = "wrong"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    elif mutation == "duplicate":
        path = fetched / "duplicate-search.json"
        payload = json.loads(path.read_text())
        payload["searches"][0]["matched_page_ids"].append("duplicate")
        path.write_text(json.dumps(payload), encoding="utf-8")
    elif mutation == "raw":
        receipt["raw_fetch_path"] = "out/notion/raw/missing.json"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    elif mutation == "freshness":
        receipt["fetched_at"] = "2026-08-26T14:00:00+00:00"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    else:
        body = (fetched / "leiame.md").read_text(encoding="utf-8")
        (fetched / "leiame.md").write_text(
            body.replace("Achado leiame", "Achado alterado"), encoding="utf-8"
        )

    with pytest.raises(NotionPublicationError, match=message):
        _function("verify_publication_gate")(tmp_path)


def test_publication_gate_rejects_reordered_or_extra_findings(tmp_path: Path) -> None:
    _seed_reports(tmp_path)
    manifest = _seed_publication_gate(tmp_path)
    entry = manifest.entries[0]
    body_path = tmp_path / "out" / "notion" / "fetched" / "leiame.md"
    body = body_path.read_text(encoding="utf-8")
    row = (
        "\t<tr>\n"
        "\t\t<td>EXTRA</td>\n"
        "\t\t<td>Extra</td>\n"
        "\t\t<td>CONFIRMADO</td>\n"
        "\t\t<td>x</td>\n"
        "\t\t<td>x</td>\n"
        "\t\t<td>x</td>\n"
        "\t\t<td>x</td>\n"
        "\t\t<td>x</td>\n"
        "\t</tr>\n"
    )
    body_path.write_text(body.replace("</table>", row + "</table>", 2), encoding="utf-8")

    with pytest.raises(NotionPublicationError, match="semantic"):
        _function("verify_publication_gate")(tmp_path)


def test_publication_gate_cross_checks_raw_fetch_identity(tmp_path: Path) -> None:
    _seed_reports(tmp_path)
    _seed_publication_gate(tmp_path)
    fetched = tmp_path / "out" / "notion" / "fetched"
    receipt_path = fetched / "leiame.json"
    receipt = json.loads(receipt_path.read_text())
    raw_path = tmp_path / receipt["raw_fetch_path"]
    raw_path.write_text(
        _connector_result(
            {
                "metadata": {"type": "page"},
                "title": receipt["title"],
                "url": "https://app.notion.com/p/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "text": (
                    'Here is the result of "fetch" as of 2026-08-26T15:01:00Z:\n'
                    '<page url="https://app.notion.com/p/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">\n'
                    "<ancestor-path>\n"
                    '<parent-page url="https://app.notion.com/p/'
                    + receipt["parent_page_id"].replace("-", "")
                    + '" title="Azure"/>\n'
                    "</ancestor-path>\n"
                    "<properties>\n"
                    + json.dumps({"title": receipt["title"]}, ensure_ascii=False)
                    + "\n</properties>\n<content>\n"
                    + (fetched / "leiame.md").read_text(encoding="utf-8")
                    + "\n</content>\n</page>"
                ),
                "page_last_edited_at": "2026-08-26T15:01:00Z",
            }
        ),
        encoding="utf-8",
    )
    receipt["raw_fetch_sha256"] = _sha(raw_path)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(NotionPublicationError, match="raw fetch"):
        _function("verify_publication_gate")(tmp_path)


def test_publication_gate_cross_checks_raw_search_matches(tmp_path: Path) -> None:
    _seed_reports(tmp_path)
    _seed_publication_gate(tmp_path)
    fetched = tmp_path / "out" / "notion" / "fetched"
    duplicate_path = fetched / "duplicate-search.json"
    duplicate = json.loads(duplicate_path.read_text())
    row = duplicate["searches"][0]
    raw_path = tmp_path / row["raw_search_path"]
    raw_path.write_text(
        _connector_result(
            {
                "results": [
                    {
                        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                        "title": "Other",
                        "url": "https://app.notion.com/p/aaaaaaaabbbbccccddddeeeeeeeeeeee",
                        "type": "page",
                    }
                ],
                "type": "workspace_search",
            }
        ),
        encoding="utf-8",
    )
    row["raw_search_sha256"] = _sha(raw_path)
    duplicate_path.write_text(json.dumps(duplicate), encoding="utf-8")

    with pytest.raises(NotionPublicationError, match="raw search"):
        _function("verify_publication_gate")(tmp_path)
