"""Behavioral tests for raw external-evidence parsing."""

from __future__ import annotations

import json

import pytest

from delta.notion_external_evidence import (
    ExternalEvidenceError,
    parse_browser_review_result,
    parse_notion_fetch_result,
    parse_notion_search_result,
    parse_notion_update_result,
)


PAGE_ID = "3c3412e0-8c26-813c-ad9c-d57026cfd566"
PARENT_ID = "2a1412e0-8c26-803b-a988-dc619a396e45"
PAGE_URL = "https://app.notion.com/p/3c3412e08c26813cad9cd57026cfd566"
TITLE = "Delta — Leiame × Processo-Agil implementado"
BODY = "DELTA-AUDIT-MARKER-leiame\n\n## Resumo"


def _tool_result(payload: dict[str, object]) -> bytes:
    return json.dumps(
        {
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "isError": False,
        }
    ).encode()


def _fetch_payload(*, page_id: str = PAGE_ID, parent_id: str = PARENT_ID) -> dict[str, object]:
    return {
        "metadata": {"type": "page"},
        "title": TITLE,
        "url": PAGE_URL,
        "text": (
            'Here is the result of "fetch" as of 2026-09-09T01:00:00.000Z:\n'
            f'<page url="{PAGE_URL}">\n'
            "<ancestor-path>\n"
            f'<parent-page url="https://app.notion.com/p/{parent_id.replace("-", "")}" '
            'title="Azure"/>\n'
            "</ancestor-path>\n"
            "<properties>\n"
            f'{{"title":{json.dumps(TITLE, ensure_ascii=False)}}}\n'
            "</properties>\n"
            "<content>\n"
            f"{BODY}\n"
            "</content>\n"
            "</page>"
        ),
        "page_last_edited_at": "2026-09-09T00:59:00.000Z",
    }


def test_fetch_result_cross_checks_page_parent_title_body_and_timestamp() -> None:
    evidence = parse_notion_fetch_result(_tool_result(_fetch_payload()))

    assert evidence.page_id == PAGE_ID
    assert evidence.parent_page_id == PARENT_ID
    assert evidence.title == TITLE
    assert evidence.body == BODY
    assert evidence.connector_as_of == "2026-09-09T01:00:00.000Z"
    assert evidence.last_edited_time == "2026-09-09T00:59:00.000Z"


def test_fetch_result_rejects_receipt_identity_not_present_in_raw_result() -> None:
    with pytest.raises(ExternalEvidenceError, match="parent"):
        parse_notion_fetch_result(_tool_result(_fetch_payload(parent_id="wrong")))


def test_fetch_result_accepts_title_prefixed_by_verified_page_emoji() -> None:
    payload = _fetch_payload()
    payload["title"] = f"⛵ {TITLE}"
    payload["icon"] = {"type": "emoji", "emoji": "⛵"}

    evidence = parse_notion_fetch_result(_tool_result(payload))

    assert evidence.title == f"⛵ {TITLE}"


def test_update_result_requires_success_and_exact_page_identity() -> None:
    evidence = parse_notion_update_result(
        _tool_result({"page_id": PAGE_ID, "url": PAGE_URL, "status": "updated"})
    )

    assert evidence.page_id == PAGE_ID
    assert evidence.url == PAGE_URL

    with pytest.raises(ExternalEvidenceError, match="update"):
        parse_notion_update_result(
            json.dumps(
                {
                    "content": [{"type": "text", "text": "failed"}],
                    "isError": True,
                }
            ).encode()
        )


def test_update_result_accepts_native_page_id_only_success() -> None:
    evidence = parse_notion_update_result(_tool_result({"page_id": PAGE_ID}))

    assert evidence.page_id == PAGE_ID
    assert evidence.url == PAGE_URL


def test_search_result_returns_only_raw_exact_matches() -> None:
    raw = _tool_result(
        {
            "results": [
                {"id": PAGE_ID, "title": TITLE, "url": PAGE_URL, "highlight": BODY},
                {
                    "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "title": "Similar",
                    "url": "https://app.notion.com/p/aaaaaaaabbbbccccddddeeeeeeeeeeee",
                },
            ],
            "type": "workspace_search",
        }
    )

    evidence = parse_notion_search_result(raw)

    assert evidence.exact_page_ids("title", TITLE) == (PAGE_ID,)
    assert evidence.exact_page_ids("marker", "DELTA-AUDIT-MARKER-leiame") == (PAGE_ID,)
    assert evidence.exact_page_ids("page_id", PAGE_ID) == (PAGE_ID,)


def test_search_result_normalizes_connector_highlight_emphasis() -> None:
    raw = _tool_result(
        {
            "results": [
                {
                    "id": PAGE_ID,
                    "title": TITLE,
                    "url": PAGE_URL,
                    "highlight": "**DELTA-AUDIT-MARKER-leiame**",
                    "type": "page",
                }
            ],
            "type": "workspace_search",
        }
    )

    evidence = parse_notion_search_result(raw)

    assert evidence.exact_page_ids(
        "marker", "DELTA-AUDIT-MARKER-leiame"
    ) == (PAGE_ID,)


def test_browser_review_result_binds_ui_facts_and_response() -> None:
    response = "PASS\n\n## Achados\nNenhum achado material."
    raw = _tool_result(
        {
            "surface": "chatgpt-integrated-browser",
            "chat_id": "chat-kimi-independent",
            "chat_url": "https://app.notion.com/chat-kimi-independent",
            "model": "Kimi K3",
            "effort": "maximum",
            "packet_name": "packet.csv",
            "packet_sha256": "a" * 64,
            "prompt_sha256": "b" * 64,
            "model_verified_at": "2026-09-09T01:00:00+00:00",
            "effort_verified_at": "2026-09-09T01:00:00+00:00",
            "sent_at": "2026-09-09T01:01:00+00:00",
            "completed_at": "2026-09-09T01:02:00+00:00",
            "response_markdown": response,
        }
    )

    evidence = parse_browser_review_result(raw)

    assert evidence.model == "Kimi K3"
    assert evidence.response_markdown == response

    altered = json.loads(raw)
    altered_payload = json.loads(altered["content"][0]["text"])
    altered_payload["model"] = "Other"
    altered["content"][0]["text"] = json.dumps(altered_payload)
    with pytest.raises(ExternalEvidenceError, match="model"):
        parse_browser_review_result(json.dumps(altered).encode())
