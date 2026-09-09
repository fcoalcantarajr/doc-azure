"""Parse raw browser and Notion connector results into verified facts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse


_HASH = re.compile(r"^[0-9a-f]{64}$")
_NOTION_ID = re.compile(r"^[0-9a-f]{32}$")
_AS_OF = re.compile(r'\bas of (.+?(?:Z|[+-]\d\d:\d\d)):\n<page ')
_PAGE = re.compile(r'<page url="([^"]+)"(?: [^>]*)?>')
_PARENT = re.compile(r'<parent-page url="([^"]+)"[^>]*/>')
_PROPERTIES = re.compile(r"<properties>\n(.*?)\n</properties>", re.DOTALL)
_CONTENT = re.compile(r"<content>\n(.*?)\n</content>", re.DOTALL)
_BROWSER_FIELDS = {
    "surface",
    "chat_id",
    "chat_url",
    "model",
    "effort",
    "packet_name",
    "packet_sha256",
    "prompt_sha256",
    "model_verified_at",
    "effort_verified_at",
    "sent_at",
    "completed_at",
    "response_markdown",
}


class ExternalEvidenceError(ValueError):
    """Raised when a raw external tool result cannot prove the claimed fact."""


@dataclass(frozen=True)
class NotionFetchEvidence:
    """Identity, hierarchy, content, and freshness extracted from a raw fetch."""

    page_id: str
    parent_page_id: str | None
    title: str
    url: str
    body: str
    connector_as_of: str
    last_edited_time: str | None


@dataclass(frozen=True)
class NotionUpdateEvidence:
    """Page identity returned by one successful raw update result."""

    page_id: str
    url: str


@dataclass(frozen=True)
class NotionSearchEvidence:
    """Exact-match projection of a raw Notion workspace search."""

    results: tuple[dict[str, object], ...]

    def exact_page_ids(self, kind: str, query: str) -> tuple[str, ...]:
        """Return stable unique page IDs satisfying one exact query meaning."""

        if kind not in {"page_id", "title", "marker"}:
            raise ExternalEvidenceError("search kind is invalid")
        matched: list[str] = []
        for result in self.results:
            raw_id = result.get("id")
            if not isinstance(raw_id, str):
                continue
            page_id = _normalize_notion_id(raw_id, "search page")
            if kind == "page_id":
                is_match = page_id == _normalize_notion_id(query, "search query")
            elif kind == "title":
                is_match = result.get("title") == query
            else:
                highlight = result.get("highlight")
                is_match = isinstance(highlight, str) and query in highlight
            if is_match and page_id not in matched:
                matched.append(page_id)
        return tuple(matched)


@dataclass(frozen=True)
class BrowserReviewEvidence:
    """Review identity and response extracted from one raw browser-tool result."""

    surface: str
    chat_id: str
    chat_url: str
    model: str
    effort: str
    packet_name: str
    packet_sha256: str
    prompt_sha256: str
    model_verified_at: str
    effort_verified_at: str
    sent_at: str
    completed_at: str
    response_markdown: str


def parse_notion_fetch_result(raw: bytes) -> NotionFetchEvidence:
    """Parse one raw Notion fetch CallToolResult without trusting a side receipt."""

    payload = _tool_payload(raw, "fetch")
    if payload.get("metadata") != {"type": "page"}:
        raise ExternalEvidenceError("fetch metadata is invalid")
    title = _required_text(payload.get("title"), "fetch title")
    url = _required_text(payload.get("url"), "fetch URL")
    text = _required_text(payload.get("text"), "fetch page text")
    page_match = _PAGE.search(text)
    properties_match = _PROPERTIES.search(text)
    content_match = _CONTENT.search(text)
    as_of_match = _AS_OF.search(text)
    if (
        page_match is None
        or properties_match is None
        or content_match is None
        or as_of_match is None
    ):
        raise ExternalEvidenceError("fetch page envelope is incomplete")
    page_id = _notion_id_from_url(page_match.group(1), "fetch page")
    if _notion_id_from_url(url, "fetch URL") != page_id:
        raise ExternalEvidenceError("fetch page identity is inconsistent")
    parent_match = _PARENT.search(text)
    parent_id = (
        _notion_id_from_url(parent_match.group(1), "fetch parent")
        if parent_match is not None
        else None
    )
    try:
        properties = json.loads(properties_match.group(1))
    except json.JSONDecodeError:
        raise ExternalEvidenceError("fetch page properties are invalid") from None
    if not isinstance(properties, dict) or properties.get("title") != title:
        raise ExternalEvidenceError("fetch title is not present in page properties")
    connector_as_of = _parse_time(as_of_match.group(1), "connector as-of")
    last_edited_raw = payload.get("page_last_edited_at")
    last_edited = (
        _parse_time(last_edited_raw, "last-edited")
        if last_edited_raw is not None
        else None
    )
    return NotionFetchEvidence(
        page_id=page_id,
        parent_page_id=parent_id,
        title=title,
        url=_canonical_page_url(url, page_id),
        body=content_match.group(1),
        connector_as_of=connector_as_of,
        last_edited_time=last_edited,
    )


def parse_notion_update_result(raw: bytes) -> NotionUpdateEvidence:
    """Require a successful raw update result with one exact page identity."""

    payload = _tool_payload(raw, "update")
    page_id = _normalize_notion_id(payload.get("page_id"), "update page")
    url = _required_text(payload.get("url"), "update URL")
    status = payload.get("status")
    if status not in {"updated", "succeeded", "success"}:
        raise ExternalEvidenceError("update status is invalid")
    if _notion_id_from_url(url, "update URL") != page_id:
        raise ExternalEvidenceError("update page identity is inconsistent")
    return NotionUpdateEvidence(page_id=page_id, url=_canonical_page_url(url, page_id))


def parse_notion_search_result(raw: bytes) -> NotionSearchEvidence:
    """Parse one raw Notion search result for later exact-match evaluation."""

    payload = _tool_payload(raw, "search")
    if payload.get("type") != "workspace_search":
        raise ExternalEvidenceError("search result type is invalid")
    results = payload.get("results")
    if not isinstance(results, list) or any(not isinstance(item, dict) for item in results):
        raise ExternalEvidenceError("search results are invalid")
    for result in results:
        if result.get("type") != "page" and "type" in result:
            raise ExternalEvidenceError("search result contains a non-page entity")
        _normalize_notion_id(result.get("id"), "search page")
        _required_text(result.get("title"), "search title")
        _required_text(result.get("url"), "search URL")
    return NotionSearchEvidence(tuple(results))


def parse_browser_review_result(raw: bytes) -> BrowserReviewEvidence:
    """Parse one raw browser-tool result and validate its review invariants."""

    payload = _tool_payload(raw, "browser review")
    if set(payload) != _BROWSER_FIELDS:
        raise ExternalEvidenceError("browser review schema is invalid")
    model = _required_text(payload.get("model"), "browser review model")
    if model not in {"Kimi K3", "Opus 5"}:
        raise ExternalEvidenceError("browser review model is invalid")
    checks = {
        "surface": "chatgpt-integrated-browser",
        "effort": "maximum",
        "packet_name": "packet.csv",
    }
    for field, expected in checks.items():
        if payload.get(field) != expected:
            raise ExternalEvidenceError(f"browser review {field} is invalid")
    for field in ("chat_id", "chat_url", "response_markdown"):
        _required_text(payload.get(field), f"browser review {field}")
    for field in ("packet_sha256", "prompt_sha256"):
        value = payload.get(field)
        if not isinstance(value, str) or _HASH.fullmatch(value) is None:
            raise ExternalEvidenceError(f"browser review {field} is invalid")
    parsed_times = [
        datetime.fromisoformat(_parse_time(payload[field], f"browser review {field}"))
        for field in (
            "model_verified_at",
            "effort_verified_at",
            "sent_at",
            "completed_at",
        )
    ]
    if parsed_times[0] > parsed_times[2] or parsed_times[1] > parsed_times[2] or parsed_times[2] > parsed_times[3]:
        raise ExternalEvidenceError("browser review timestamps are invalid")
    return BrowserReviewEvidence(**payload)


def _tool_payload(raw: bytes, label: str) -> dict[str, object]:
    try:
        envelope = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise ExternalEvidenceError(f"raw {label} result is not valid JSON") from None
    if not isinstance(envelope, dict) or envelope.get("isError") is not False:
        raise ExternalEvidenceError(f"raw {label} result reports an error")
    content = envelope.get("content")
    if not isinstance(content, list):
        raise ExternalEvidenceError(f"raw {label} result has no content")
    texts = [
        item.get("text")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    if len(texts) != 1 or not isinstance(texts[0], str):
        raise ExternalEvidenceError(f"raw {label} result has ambiguous text content")
    try:
        payload = json.loads(texts[0])
    except json.JSONDecodeError:
        raise ExternalEvidenceError(f"raw {label} text is not valid JSON") from None
    if not isinstance(payload, dict):
        raise ExternalEvidenceError(f"raw {label} payload must be an object")
    return payload


def _normalize_notion_id(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ExternalEvidenceError(f"{label} identity is invalid")
    compact = value.replace("-", "").lower()
    if _NOTION_ID.fullmatch(compact) is None:
        raise ExternalEvidenceError(f"{label} identity is invalid")
    return f"{compact[:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:]}"


def _notion_id_from_url(url: str, label: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in {"app.notion.com", "www.notion.so", "notion.so"}:
        raise ExternalEvidenceError(f"{label} URL is invalid")
    compact_candidates = re.findall(r"[0-9a-fA-F]{32}", parsed.path.replace("-", ""))
    if len(compact_candidates) != 1:
        raise ExternalEvidenceError(f"{label} URL identity is invalid")
    return _normalize_notion_id(compact_candidates[0], label)


def _canonical_page_url(url: str, page_id: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/p/{page_id.replace('-', '')}"


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExternalEvidenceError(f"{label} is invalid")
    return value


def _parse_time(value: object, label: str) -> str:
    text = _required_text(value, f"{label} timestamp")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ExternalEvidenceError(f"{label} timestamp is invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExternalEvidenceError(f"{label} timestamp must include a timezone")
    return text
