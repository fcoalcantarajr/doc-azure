"""Build review artifacts and enforce external Notion evidence gates."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

from delta.notion import PUBLICATION_RECEIPT_FIELDS
from delta.notion_external_evidence import (
    ExternalEvidenceError,
    parse_browser_review_result,
    parse_notion_fetch_result,
    parse_notion_search_result,
    parse_notion_update_result,
)
from delta.notion_semantics import ReportSemantic, parse_notion_semantics


_HASH = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE = re.compile(
    r"(?i)(authorization\s*:|bearer\s+|azdo_pat|github_pat_|ghp_|"
    r"(?:^|[/\\])\.env(?:$|\s|[/\\])|password\s*[:=])"
)
_REVIEW_MODELS = {"kimi-k3": "Kimi K3", "opus-5": "Opus 5"}
_REVIEW_RECEIPT_FIELDS = {
    "schema_version",
    "model",
    "effort",
    "surface",
    "packet_sha256",
    "prompt_sha256",
    "chat_id",
    "chat_url",
    "model_verified_at",
    "effort_verified_at",
    "sent_at",
    "completed_at",
    "verdict",
    "response_path",
    "response_sha256",
    "browser_result_path",
    "browser_result_sha256",
    "findings",
}
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def prepare_review_artifacts(
    root: Path,
    manifest: object,
    semantics: tuple[ReportSemantic, ...],
    repository_url: str,
    error_type: type[ValueError],
) -> None:
    """Write one deterministic, secret-screened review packet and prompt."""

    repository_root = Path(root)
    _validate_repository_url(repository_url, error_type)
    packet = _render_packet(manifest, semantics)
    prompt = _render_prompt(repository_url)
    if _SENSITIVE.search(packet) or _SENSITIVE.search(prompt):
        raise error_type("review artifacts contain sensitive content")
    review_root = repository_root / "out" / "notion" / "review"
    packet_bytes = packet.encode("utf-8")
    prompt_bytes = prompt.encode("utf-8")
    review_manifest = {
        "schema_version": 1,
        "repository_url": repository_url,
        "packet_path": "out/notion/review/packet.csv",
        "packet_sha256": _sha256(packet_bytes),
        "prompt_path": "out/notion/review/prompt.txt",
        "prompt_sha256": _sha256(prompt_bytes),
        "report_semantic_hashes": {
            entry.slug: semantic.sha256
            for entry, semantic in zip(manifest.entries, semantics, strict=True)
        },
    }
    _atomic_write(review_root / "packet.csv", packet_bytes, error_type)
    _atomic_write(review_root / "prompt.txt", prompt_bytes, error_type)
    _atomic_write(
        review_root / "review-manifest.json",
        _json_bytes(review_manifest),
        error_type,
    )


def verify_review_gate(root: Path, error_type: type[ValueError]) -> None:
    """Require two independent, bound browser reviews and reconciliation."""

    from delta.notion import expected_publication_manifest

    repository_root = Path(root)
    review_root = repository_root / "out" / "notion" / "review"
    review_manifest = _load_json(
        review_root / "review-manifest.json", error_type, "review manifest"
    )
    expected_review_fields = {
        "schema_version",
        "repository_url",
        "packet_path",
        "packet_sha256",
        "prompt_path",
        "prompt_sha256",
        "report_semantic_hashes",
    }
    if set(review_manifest) != expected_review_fields or review_manifest.get(
        "schema_version"
    ) != 1:
        raise error_type("review manifest schema is invalid")
    _validate_repository_url(str(review_manifest["repository_url"]), error_type)
    for kind in ("packet", "prompt"):
        _verify_bound_file(
            repository_root,
            review_manifest.get(f"{kind}_path"),
            review_manifest.get(f"{kind}_sha256"),
            error_type,
            kind,
        )
    expected_manifest = expected_publication_manifest(repository_root)
    current_hashes = {
        entry.slug: entry.semantic_sha256 for entry in expected_manifest.entries
    }
    if review_manifest.get("report_semantic_hashes") != current_hashes:
        raise error_type("review gate is stale relative to versioned reports")

    receipts: dict[str, dict[str, object]] = {}
    response_hashes: dict[str, str] = {}
    chat_ids: set[str] = set()
    completed_times: list[datetime] = []
    finding_keys: set[tuple[str, str]] = set()
    for slug, model in _REVIEW_MODELS.items():
        receipt = _load_json(
            review_root / "receipts" / f"{slug}.json",
            error_type,
            f"{model} review receipt",
        )
        _verify_review_receipt(
            repository_root,
            receipt,
            model,
            str(review_manifest["packet_sha256"]),
            str(review_manifest["prompt_sha256"]),
            error_type,
        )
        chat_id = receipt["chat_id"]
        if chat_id in chat_ids:
            raise error_type("review receipts reuse the same chat")
        chat_ids.add(str(chat_id))
        completed_times.append(_parse_time(receipt["completed_at"], error_type, "review"))
        response_hashes[model] = str(receipt["response_sha256"])
        for finding in receipt["findings"]:
            finding_keys.add((model, str(finding["id"])))
        receipts[model] = receipt

    if len(set(response_hashes.values())) != len(response_hashes):
        raise error_type("review response bodies are byte-identical")

    reconciliation = _load_json(
        review_root / "reconciliation.json", error_type, "review reconciliation"
    )
    _verify_reconciliation(
        reconciliation,
        str(review_manifest["packet_sha256"]),
        response_hashes,
        current_hashes,
        finding_keys,
        max(completed_times),
        error_type,
    )


def verify_publication_gate(root: Path, error_type: type[ValueError]) -> None:
    """Require semantic read-back plus raw hierarchy and duplicate evidence."""

    from delta.notion import (
        expected_publication_manifest,
        load_publication_manifest,
    )

    repository_root = Path(root)
    verify_review_gate(repository_root, error_type)
    notion_root = repository_root / "out" / "notion"
    manifest = load_publication_manifest(notion_root / "publication-manifest.json")
    expected = expected_publication_manifest(repository_root)
    if manifest != expected:
        raise error_type("publication manifest is stale relative to reports")
    fetched_root = notion_root / "fetched"
    fetched_receipts: dict[str, dict[str, object]] = {}
    for entry in manifest.entries:
        receipt = _load_json(
            fetched_root / f"{entry.slug}.json",
            error_type,
            f"{entry.slug} publication receipt",
        )
        fetched_body = _read_regular_bytes(
            fetched_root / f"{entry.slug}.md", error_type, "fetched body"
        )
        try:
            fetched_semantics = parse_notion_semantics(
                fetched_body.decode("utf-8"), entry.slug
            )
        except (UnicodeError, ValueError):
            raise error_type(f"{entry.slug}: semantic read-back is invalid") from None
        if (
            fetched_semantics.sha256 != entry.semantic_sha256
            or receipt.get("semantic_sha256") != entry.semantic_sha256
        ):
            raise error_type(f"{entry.slug}: semantic read-back differs")
        _verify_publication_receipt(
            repository_root,
            entry,
            receipt,
            fetched_body,
            error_type,
        )
        fetched_receipts[entry.slug] = receipt
    _verify_hierarchy(repository_root, fetched_root, manifest, error_type)
    _verify_duplicate_searches(repository_root, fetched_root, manifest, error_type)


def _render_packet(manifest: object, semantics: tuple[ReportSemantic, ...]) -> str:
    stream = io.StringIO(newline="")
    fieldnames = (
        "page_slug",
        "claim_id",
        "finding",
        "status",
        "documented",
        "implemented",
        "evidence_documental",
        "evidence_azure",
        "impact_or_limit",
        "report_semantic_sha256",
    )
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for entry, semantic in zip(manifest.entries, semantics, strict=True):
        for finding in semantic.findings:
            writer.writerow(
                {
                    "page_slug": entry.slug,
                    "claim_id": finding.claim_id,
                    "finding": finding.finding,
                    "status": finding.status,
                    "documented": finding.documented,
                    "implemented": finding.implemented,
                    "evidence_documental": finding.evidence_documental,
                    "evidence_azure": finding.evidence_azure,
                    "impact_or_limit": finding.impact_or_limit,
                    "report_semantic_sha256": semantic.sha256,
                }
            )
    return stream.getvalue()


def _render_prompt(repository_url: str) -> str:
    return f"""Faça uma revisão adversarial e independente do delta entre as quatro páginas da Wiki e o Processo-Agil implementado no Azure DevOps.

Você está no Notion AI e tem acesso ao GitHub. Use esse acesso para ler diretamente o repositório privado {repository_url} e conferir código, testes, documentação, relatórios e apontadores do pacote CSV anexado. Não presuma que a conclusão local está correta: tente falsificar a conclusão.

Procure, no mínimo: falsos MATCH e falsos deltas; gaps de cobertura; claims ou WITs novos/removidos; seletores que deixam de resolver; respostas parciais; heurísticas frágeis; dependências ocultas de IA; falhas fail-open; problemas de segurança; não determinismo; proveniência fraca; e qualquer classificação sem evidência. Verifique cobertura das afirmações documentais, correspondência entre status, conteúdo e evidências, omissões ou extrapolações, escopo dos WITs ativos/desabilitados, reprodutibilidade e equivalência semântica dos quatro corpos preparados para o Notion. O runtime obrigatoriamente deve funcionar sem IA, LLM, embeddings, prompts ou agentes. Não solicite nem reproduza segredos, o arquivo .env ou dados pessoais brutos.

Os revisores designados são Kimi K3 e Opus 5, cada um com esforço máximo, em chats independentes no navegador integrado ao ChatGPT. Não substitua esses modelos, não trate concordância como prova e declare explicitamente se consultou o repositório privado e o CSV.

Responda em português com: (1) veredito PASS ou NEEDS_FIXES; (2) achados numerados, cada um com severidade, claim/page, evidência concreta e correção proposta; (3) lacunas não verificáveis; e (4) declaração explícita de que consultou ou não o repositório privado e o CSV.
"""


def _verify_review_receipt(
    root: Path,
    receipt: dict[str, object],
    model: str,
    packet_hash: str,
    prompt_hash: str,
    error_type: type[ValueError],
) -> None:
    if set(receipt) != _REVIEW_RECEIPT_FIELDS or receipt.get("schema_version") != 1:
        raise error_type(f"{model}: review receipt schema is invalid")
    checks = {
        "model": model,
        "effort": "maximum",
        "surface": "chatgpt-integrated-browser",
        "packet_sha256": packet_hash,
        "prompt_sha256": prompt_hash,
    }
    for field, expected in checks.items():
        if receipt.get(field) != expected:
            raise error_type(f"{model}: review {field} is invalid")
    for field in ("chat_id", "chat_url"):
        if not isinstance(receipt.get(field), str) or not receipt[field]:
            raise error_type(f"{model}: review chat identity is invalid")
    times = [
        _parse_time(receipt[field], error_type, f"{model} {field}")
        for field in (
            "model_verified_at",
            "effort_verified_at",
            "sent_at",
            "completed_at",
        )
    ]
    if times[0] > times[2] or times[1] > times[2] or times[2] > times[3]:
        raise error_type(f"{model}: review timestamps are invalid")
    if receipt.get("verdict") not in {"PASS", "NEEDS_FIXES"}:
        raise error_type(f"{model}: review verdict is invalid")
    _verify_bound_file(
        root,
        receipt.get("response_path"),
        receipt.get("response_sha256"),
        error_type,
        f"{model} response",
    )
    _verify_bound_file(
        root,
        receipt.get("browser_result_path"),
        receipt.get("browser_result_sha256"),
        error_type,
        f"{model} browser result",
    )
    response = _read_root_file(
        root,
        str(receipt["response_path"]),
        error_type,
        f"{model} response",
    )
    browser_raw = _read_root_file(
        root,
        str(receipt["browser_result_path"]),
        error_type,
        f"{model} browser result",
    )
    try:
        browser = parse_browser_review_result(browser_raw)
    except ExternalEvidenceError as error:
        raise error_type(f"{model}: browser result is invalid: {error}") from None
    expected_browser = {
        "surface": receipt["surface"],
        "chat_id": receipt["chat_id"],
        "chat_url": receipt["chat_url"],
        "model": receipt["model"],
        "effort": receipt["effort"],
        "packet_sha256": receipt["packet_sha256"],
        "prompt_sha256": receipt["prompt_sha256"],
        "model_verified_at": receipt["model_verified_at"],
        "effort_verified_at": receipt["effort_verified_at"],
        "sent_at": receipt["sent_at"],
        "completed_at": receipt["completed_at"],
    }
    for field, value in expected_browser.items():
        if getattr(browser, field) != value:
            raise error_type(
                f"{model}: browser result {field} disagrees with review receipt"
            )
    try:
        browser_response = browser.response_markdown.encode("utf-8")
    except UnicodeError:
        raise error_type(f"{model}: browser result response is invalid") from None
    if browser_response != response:
        raise error_type(f"{model}: browser result response differs")
    findings = receipt.get("findings")
    if not isinstance(findings, list):
        raise error_type(f"{model}: review findings are invalid")
    identifiers: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {
            "id",
            "severity",
            "summary",
        }:
            raise error_type(f"{model}: review finding schema is invalid")
        if any(not isinstance(value, str) or not value for value in finding.values()):
            raise error_type(f"{model}: review finding is invalid")
        if finding["id"] in identifiers:
            raise error_type(f"{model}: duplicate review finding id")
        identifiers.add(finding["id"])


def _verify_reconciliation(
    payload: dict[str, object],
    packet_hash: str,
    response_hashes: dict[str, str],
    report_hashes: dict[str, str],
    finding_keys: set[tuple[str, str]],
    latest_review: datetime,
    error_type: type[ValueError],
) -> None:
    expected_fields = {
        "schema_version",
        "packet_sha256",
        "review_response_hashes",
        "reconciled_at",
        "outcome",
        "report_semantic_hashes",
        "decisions",
    }
    if set(payload) != expected_fields or payload.get("schema_version") != 1:
        raise error_type("review reconciliation schema is invalid")
    if payload.get("packet_sha256") != packet_hash:
        raise error_type("review reconciliation packet is invalid")
    if payload.get("review_response_hashes") != response_hashes:
        raise error_type("review reconciliation response hashes are invalid")
    if payload.get("report_semantic_hashes") != report_hashes:
        raise error_type("review reconciliation is stale relative to reports")
    reconciled_at = _parse_time(
        payload.get("reconciled_at"), error_type, "review reconciliation"
    )
    if reconciled_at < latest_review:
        raise error_type("review reconciliation predates a review")
    if not isinstance(payload.get("outcome"), str) or not payload["outcome"]:
        raise error_type("review reconciliation outcome is invalid")
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise error_type("review reconciliation decisions are invalid")
    covered: set[tuple[str, str]] = set()
    for decision in decisions:
        if not isinstance(decision, dict) or set(decision) != {
            "model",
            "finding_id",
            "decision",
            "rationale",
            "changed_reports",
        }:
            raise error_type("review reconciliation decision schema is invalid")
        key = (decision.get("model"), decision.get("finding_id"))
        if key not in finding_keys or key in covered:
            raise error_type("review reconciliation finding coverage is invalid")
        if decision.get("decision") not in {"accepted", "rejected", "deferred"}:
            raise error_type("review reconciliation decision is invalid")
        if not isinstance(decision.get("rationale"), str) or not decision["rationale"]:
            raise error_type("review reconciliation rationale is invalid")
        reports = decision.get("changed_reports")
        if not isinstance(reports, list) or any(not isinstance(item, str) for item in reports):
            raise error_type("review reconciliation changed reports are invalid")
        covered.add(key)
    if covered != finding_keys:
        raise error_type("review reconciliation does not cover every finding")


def _verify_publication_receipt(
    root: Path,
    entry: object,
    receipt: dict[str, object],
    fetched_body: bytes,
    error_type: type[ValueError],
) -> None:
    if set(receipt) != PUBLICATION_RECEIPT_FIELDS or receipt.get("schema_version") != 1:
        raise error_type(f"{entry.slug}: publication receipt schema is invalid")
    for field in ("slug", "title", "page_id", "parent_page_id", "url", "marker"):
        if receipt.get(field) != getattr(entry, field):
            raise error_type(f"{entry.slug}: publication {field} does not match")
    updated = _parse_time(receipt.get("updated_at"), error_type, "publication update")
    fetched = _parse_time(receipt.get("fetched_at"), error_type, "publication fetch")
    connector_as_of = _parse_time(
        receipt.get("connector_as_of"), error_type, "connector freshness"
    )
    if fetched < updated or connector_as_of < fetched:
        raise error_type(f"{entry.slug}: fetched publication is not fresh")
    last_available = receipt.get("last_edited_available")
    if not isinstance(last_available, bool):
        raise error_type(f"{entry.slug}: last-edited availability is invalid")
    if last_available:
        last_edited = _parse_time(
            receipt.get("last_edited_time"), error_type, "last edited time"
        )
        if last_edited < updated:
            raise error_type(f"{entry.slug}: last-edited proof is not fresh")
    elif receipt.get("last_edited_time") is not None:
        raise error_type(f"{entry.slug}: unavailable last-edited time must be null")
    for path_field, hash_field, label in (
        ("raw_fetch_path", "raw_fetch_sha256", "raw fetch"),
        ("update_receipt_path", "update_receipt_sha256", "update receipt"),
    ):
        _verify_bound_file(
            root,
            receipt.get(path_field),
            receipt.get(hash_field),
            error_type,
            label,
        )
    raw_fetch = _read_root_file(
        root,
        str(receipt["raw_fetch_path"]),
        error_type,
        f"{entry.slug} raw fetch",
    )
    raw_update = _read_root_file(
        root,
        str(receipt["update_receipt_path"]),
        error_type,
        f"{entry.slug} update receipt",
    )
    try:
        fetched = parse_notion_fetch_result(raw_fetch)
        update = parse_notion_update_result(raw_update)
    except ExternalEvidenceError as error:
        raise error_type(f"{entry.slug}: raw fetch/update is invalid: {error}") from None
    expected_fetch = {
        "page_id": entry.page_id,
        "parent_page_id": entry.parent_page_id,
        "title": entry.title,
        "url": entry.url,
        "connector_as_of": receipt["connector_as_of"],
        "last_edited_time": receipt["last_edited_time"],
    }
    if any(getattr(fetched, field) != value for field, value in expected_fetch.items()):
        raise error_type(f"{entry.slug}: raw fetch disagrees with publication receipt")
    raw_body = fetched.body.encode("utf-8")
    if fetched_body not in {raw_body, raw_body + b"\n"}:
        raise error_type(f"{entry.slug}: raw fetch body differs from saved read-back")
    if fetched.page_id != update.page_id or fetched.url != update.url:
        raise error_type(f"{entry.slug}: raw update identity differs")


def _verify_hierarchy(root: Path, fetched: Path, manifest: object, error_type: type[ValueError]) -> None:
    payload = _load_json(fetched / "hierarchy.json", error_type, "hierarchy receipt")
    expected_fields = {
        "schema_version",
        "parent_page_id",
        "parent_title",
        "hub_page_id",
        "fetched_at",
        "parent_fetch_path",
        "parent_fetch_sha256",
        "hub_fetch_path",
        "hub_fetch_sha256",
        "pages",
    }
    if set(payload) != expected_fields or payload.get("schema_version") != 1:
        raise error_type("Notion hierarchy receipt schema is invalid")
    if payload.get("parent_page_id") != manifest.parent_page_id:
        raise error_type("Notion hierarchy parent is invalid")
    if payload.get("hub_page_id") != "3c3412e0-8c26-809d-8e12-e5498b5fde60":
        raise error_type("Notion hierarchy hub is invalid")
    _parse_time(payload.get("fetched_at"), error_type, "hierarchy fetch")
    for prefix in ("parent", "hub"):
        _verify_bound_file(
            root,
            payload.get(f"{prefix}_fetch_path"),
            payload.get(f"{prefix}_fetch_sha256"),
            error_type,
            f"hierarchy {prefix} raw fetch",
        )
    try:
        parent = parse_notion_fetch_result(
            _read_root_file(
                root,
                str(payload["parent_fetch_path"]),
                error_type,
                "hierarchy parent raw fetch",
            )
        )
        hub = parse_notion_fetch_result(
            _read_root_file(
                root,
                str(payload["hub_fetch_path"]),
                error_type,
                "hierarchy hub raw fetch",
            )
        )
    except ExternalEvidenceError as error:
        raise error_type(f"Notion hierarchy raw fetch is invalid: {error}") from None
    if (
        parent.page_id != manifest.parent_page_id
        or payload.get("parent_title") not in {parent.title, parent.title.removeprefix("⛵ ")}
        or hub.page_id != payload.get("hub_page_id")
        or hub.parent_page_id != manifest.parent_page_id
    ):
        raise error_type("Notion hierarchy raw fetch disagrees with receipt")
    expected_pages = [
        {
            "page_id": entry.page_id,
            "title": entry.title,
            "parent_page_id": entry.parent_page_id,
            "url": entry.url,
        }
        for entry in manifest.entries
    ]
    if payload.get("pages") != expected_pages:
        raise error_type("Notion hierarchy pages or parent are invalid")


def _verify_duplicate_searches(
    root: Path,
    fetched: Path,
    manifest: object,
    error_type: type[ValueError],
) -> None:
    payload = _load_json(
        fetched / "duplicate-search.json", error_type, "duplicate search receipt"
    )
    if set(payload) != {"schema_version", "searches"} or payload.get(
        "schema_version"
    ) != 1:
        raise error_type("duplicate search receipt schema is invalid")
    searches = payload.get("searches")
    if not isinstance(searches, list) or len(searches) != len(manifest.entries) * 3:
        raise error_type("duplicate search coverage is invalid")
    expected: dict[tuple[str, str], tuple[str, str]] = {}
    for entry in manifest.entries:
        expected[(entry.slug, "page_id")] = (entry.page_id, entry.page_id)
        expected[(entry.slug, "title")] = (entry.title, entry.page_id)
        expected[(entry.slug, "marker")] = (entry.marker, entry.page_id)
    seen: set[tuple[str, str]] = set()
    for search in searches:
        required = {
            "slug",
            "kind",
            "query",
            "scope_parent_page_id",
            "expected_page_id",
            "matched_page_ids",
            "searched_at",
            "raw_search_path",
            "raw_search_sha256",
        }
        if not isinstance(search, dict) or set(search) != required:
            raise error_type("duplicate search row schema is invalid")
        key = (search.get("slug"), search.get("kind"))
        if key not in expected or key in seen:
            raise error_type("duplicate search identity is invalid")
        query, page_id = expected[key]
        if (
            search.get("query") != query
            or search.get("scope_parent_page_id") != manifest.parent_page_id
            or search.get("expected_page_id") != page_id
            or search.get("matched_page_ids") != [page_id]
        ):
            raise error_type("duplicate search found a missing or duplicate page")
        _parse_time(search.get("searched_at"), error_type, "duplicate search")
        _verify_bound_file(
            root,
            search.get("raw_search_path"),
            search.get("raw_search_sha256"),
            error_type,
            "duplicate search raw receipt",
        )
        raw_search = _read_root_file(
            root,
            str(search["raw_search_path"]),
            error_type,
            "duplicate search raw receipt",
        )
        try:
            observed = parse_notion_search_result(raw_search).exact_page_ids(
                str(search["kind"]),
                str(search["query"]),
            )
        except ExternalEvidenceError as error:
            raise error_type(f"duplicate raw search is invalid: {error}") from None
        if list(observed) != search.get("matched_page_ids"):
            raise error_type("duplicate raw search disagrees with receipt")
        seen.add(key)
    if seen != set(expected):
        raise error_type("duplicate search coverage is incomplete")


def _validate_repository_url(url: str, error_type: type[ValueError]) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or len([part for part in parsed.path.split("/") if part]) != 2
    ):
        raise error_type("repository_url must identify one private GitHub repository")


def _verify_bound_file(
    root: Path,
    raw_path: object,
    raw_hash: object,
    error_type: type[ValueError],
    label: str,
) -> None:
    if not isinstance(raw_path, str) or not raw_path:
        raise error_type(f"{label} path is invalid")
    if not isinstance(raw_hash, str) or _HASH.fullmatch(raw_hash) is None:
        raise error_type(f"{label} hash is invalid")
    body = _read_root_file(root, raw_path, error_type, label)
    if _sha256(body) != raw_hash:
        raise error_type(f"{label} hash does not match")


def _read_root_file(
    root: Path,
    relative: str,
    error_type: type[ValueError],
    label: str,
) -> bytes:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise error_type(f"{label} path escapes the repository")
    return _read_regular_bytes(Path(root) / candidate, error_type, label)


def _load_json(path: Path, error_type: type[ValueError], label: str) -> dict[str, object]:
    try:
        payload = json.loads(_read_regular_bytes(path, error_type, label).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise error_type(f"{label} is not valid JSON") from None
    if not isinstance(payload, dict):
        raise error_type(f"{label} must be a JSON object")
    return payload


def _read_regular_bytes(path: Path, error_type: type[ValueError], label: str) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | _NOFOLLOW)
    except OSError:
        raise error_type(f"cannot read {label}") from None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise error_type(f"cannot read {label}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def _parse_time(value: object, error_type: type[ValueError], label: str) -> datetime:
    if not isinstance(value, str):
        raise error_type(f"{label} timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise error_type(f"{label} timestamp is invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise error_type(f"{label} timestamp must include a timezone")
    return parsed


def _json_bytes(payload: dict[str, object]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, body: bytes, error_type: type[ValueError]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(body)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    except OSError as error:
        raise error_type(f"cannot write {path.name}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()
