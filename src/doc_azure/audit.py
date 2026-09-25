"""One deterministic audit pipeline; Notion is not part of its execution path."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from delta.build import BuildError, FIXED_SLUGS, _load_report_provenance
from delta.document_coverage import CoverageError, assess_documents, _unique_object
from delta.evaluator import evaluate_claim
from delta.models import AuditResult
from delta.process_coverage import compare_inventory, fingerprint_json
from delta.render import render_report
from doc_azure.azure_client import AzureReadClient, AzureReadError
from doc_azure.baselines import validate_process_coverage_source
from doc_azure.process_collector import (
    ProcessCollectionError,
    collect_process,
    read_cached_process_manifest,
    read_validated_process_manifest,
    validate_process_request_routes,
)
from doc_azure.settings import Settings
from doc_azure.snapshot import SnapshotError, SnapshotWriter, read_snapshot_artifact, resolve_snapshot_root
from doc_azure.wiki_collector import WikiCollectionError, collect_wiki_pages, read_cached_wiki_manifest


@dataclass(frozen=True)
class RunOutcome:
    exit_code: int
    logical_sha256: str


def _json_value(value: object) -> object:
    if is_dataclass(value):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _process_gaps(root: Path, catalog: Path, baseline: Path) -> tuple[list[dict], dict]:
    try:
        payload = json.loads(baseline.read_bytes(), object_pairs_hook=_unique_object)
    except (OSError, ValueError):
        raise CoverageError("process coverage baseline is missing or malformed") from None
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version", "catalog_sha256", "source", "entries"
    }:
        raise CoverageError("invalid process coverage schema")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 2:
        raise CoverageError("unsupported process coverage schema")
    if payload["catalog_sha256"] != hashlib.sha256(catalog.read_bytes()).hexdigest():
        raise CoverageError("process coverage catalog hash differs")
    try:
        validate_process_coverage_source(root, payload)
    except (OSError, UnicodeError, TypeError, ValueError, ProcessCollectionError):
        raise CoverageError("process coverage baseline source is invalid") from None
    generation = resolve_snapshot_root(root / "out" / "process")
    manifest = read_validated_process_manifest(generation)
    try:
        validate_process_request_routes(generation)
    except ProcessCollectionError:
        raise CoverageError("process API request route coverage is incomplete") from None
    artifacts = {entry.path: json.loads(read_snapshot_artifact(generation, entry.path),
                                     object_pairs_hook=_unique_object)
                 for entry in manifest.artifacts}
    current = fingerprint_json(artifacts)
    try:
        changes = compare_inventory(payload["entries"], current)
    except ValueError:
        raise CoverageError("invalid process coverage inventory") from None
    if resolve_snapshot_root(root / "out" / "process") != generation:
        raise ValueError("process snapshot changed during baseline comparison")
    return [{**asdict(change), "status": "PROCESS_INVENTORY_CHANGE"} for change in changes], current


async def _acquire(root: Path, *, offline: bool, refresh: bool) -> None:
    if offline and refresh:
        raise ValueError("offline and refresh cannot be combined")
    if not refresh and read_cached_wiki_manifest(root) and read_cached_process_manifest(root):
        return
    if offline:
        raise ValueError("offline mode requires complete snapshots")
    settings = Settings.load(root)
    async with httpx.AsyncClient(timeout=60.0) as http:
        client = AzureReadClient(http, f"https://dev.azure.com/{settings.organization}",
                                 settings.pat, asyncio.Semaphore(8))
        now = lambda: datetime.now(timezone.utc)
        await collect_wiki_pages(root, client, refresh=refresh, now=now)
        await collect_process(root, client, refresh=refresh, now=now)


async def run_audit(root: Path, catalog: Path, document_baseline: Path,
                    process_baseline: Path, *, offline: bool = False,
                    refresh: bool = False) -> RunOutcome:
    """Acquire or replay sources and atomically publish a complete result bundle.

    Exit codes: 0 all confirmed, 1 non-confirmed findings, 2 coverage gap,
    3 acquisition/validation failure, 4 unexpected internal failure.
    Inventory drift is conservatively a gap until explicitly reviewed; existing
    mapped assertions still run and retain their own independent classifications.
    """
    summary: dict = {"schema_version": 1, "coverage_complete": False,
                     "pages": list(FIXED_SLUGS), "findings": [], "gaps": []}
    rendered: dict[str, str] = {}
    provenance = None
    try:
        await _acquire(root, offline=offline, refresh=refresh)
        provenance = _load_report_provenance(root)
        coverage = assess_documents(root, catalog, document_baseline)
        process_gaps, inventory = _process_gaps(root, catalog, process_baseline)
        summary["gaps"] = [asdict(change) for change in coverage.changes] + process_gaps
        summary["catalog_sha256"] = hashlib.sha256(catalog.read_bytes()).hexdigest()
        summary["process_inventory_sha256"] = hashlib.sha256(
            json.dumps(inventory, sort_keys=True).encode()).hexdigest()
        for slug in FIXED_SLUGS:
            findings = tuple(evaluate_claim(claim, root) for claim in coverage.claims if claim.slug == slug)
            summary["findings"].extend(_json_value(findings))
            if findings:
                rendered[slug] = render_report(AuditResult(findings), provenance)
        if _load_report_provenance(root) != provenance:
            raise ValueError("source generations changed during audit")
        summary["coverage_complete"] = not summary["gaps"]
        code = 2 if summary["gaps"] else 1 if any(
            row["status"] != "CONFIRMADO" for row in summary["findings"]) else 0
    except CoverageError as error:
        code = 2
        summary["gaps"].append({"status": "COVERAGE_CONTRACT_INVALID", "reason": str(error)})
    except (ValueError, OSError, BuildError, SnapshotError, AzureReadError,
            ProcessCollectionError, WikiCollectionError) as error:
        code = 3
        summary["error_type"] = type(error).__name__
    except Exception as error:
        code = 4
        summary["error_type"] = type(error).__name__
    summary["status"] = ("CLEAN", "DELTAS", "COVERAGE_GAP", "ACQUISITION_VALIDATION_FAILED", "INTERNAL_ERROR")[code]
    summary["exit_code"] = code
    digest = hashlib.sha256(json.dumps(summary, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    summary["logical_sha256"] = digest
    summary["provenance"] = asdict(provenance) if provenance else None
    summary["created_at"] = datetime.now(timezone.utc).isoformat()
    writer = SnapshotWriter(root / "out/audit")
    try:
        writer.write_json("run.json", summary)
        global_text = (f"# Auditoria Processo-Agil\n\nEstado: {summary['status']}\n\n"
                       f"Claims avaliadas: {len(summary['findings'])}\n\n"
                       f"Lacunas: {len(summary['gaps'])}\n\nHash lógico: `{digest}`\n")
        writer.write_text("global.md", global_text)
        for slug in FIXED_SLUGS:
            warning = "" if code < 2 else f"Auditoria incompleta: {summary['status']}. Consulte run.json.\n\n"
            writer.write_text(slug + ".md", warning + rendered.get(slug, f"# {slug}\n\nSem classificação válida nesta execução.\n"))
        writer.commit_manifest(collected_at=summary["created_at"], requests=())
    except BaseException:
        writer.abort()
        raise
    return RunOutcome(code, digest)
