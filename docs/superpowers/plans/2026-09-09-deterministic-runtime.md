# Deterministic Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Complete the original audit and deliver an independently executable, deterministic, fail-closed auditor.

**Architecture:** Reuse the existing collectors, immutable snapshots, catalog and evaluator. Add explicit documentary and inventory coverage baselines, then a runtime orchestrator and CLI that produce a complete run bundle independently of Notion. Publication and external reviews remain separate delivery gates.

**Tech Stack:** Python 3.11+, uv, httpx, pytest; no AI runtime dependency.

**Spec:** `/Users/chicao/.codex/attachments/0e0b988c-f7c4-41e4-aa83-61dc243956b2/goal-objective.md` (authoritative full objective).

## Global Constraints

- Azure is semantically read-only; only existing tested method/route allowlists.
- Preserve existing worktree and uncommitted corrections; no unrelated cleanup.
- No `.env`, raw snapshots, credentials or sensitive payloads in Git.
- New documentary prose cannot be interpreted automatically.
- A coverage gap is not a clean audit; do not lower existing verification gates.
- Runtime must work without Notion, models, agents, prompts or embeddings.
- Same normalized inputs and rule versions produce identical logical results.
- Final delivery includes all nineteen objective acceptance requirements.

## Task 1: Explicit documentary drift

**Files:** Create `src/delta/coverage.py`, `tests/test_delta_coverage.py`; update `docs/decisions.md`.

**Interfaces:** `document_fingerprint(contents: bytes) -> tuple[str, ...]`;
`compare_document(slug: str, baseline: tuple[str, ...], current: bytes) -> tuple[DocumentChange, ...]`.
Fingerprints retain line order and all Markdown-sensitive whitespace. Only CRLF
becomes LF. Changes expose current line numbers/text and deleted baseline hashes;
raw baseline source remains in ignored evidence rather than a duplicate Git copy.

- [x] Add tests for additions, deletions, replacements and harmless CRLF.
- [x] Run `uv run pytest -q tests/test_delta_coverage.py`; record missing-feature RED.
- [x] Implement immutable change records, strict baseline validation and deterministic line comparison.
- [x] Test blank lines, hard breaks, indentation, Unicode and repeated lines to prevent over-normalization.
- [ ] Run focused and full suites; record results before a cohesive commit.

Example acceptance: baseline `b"Required: yes\n"` and current
`b"Required: no\n"` produce one replacement at current line 1 whose excerpt is
`Required: no`, not a MATCH or inferred conflict.

Task 1 evidence: initial collection failed because `delta.coverage` did not
exist (`ImportError: cannot import name 'coverage' from 'delta'`); after
implementation all 14 focused tests passed. Full suite: 325 passed in 2.87s.
Integration and a versioned live baseline remain Task 2/3 work; no claim is made
that the runtime coverage gate is already operational.

## Task 2: Versioned coverage and inventory

**Files:** Extend `src/delta/coverage.py`; create a focused inventory module and
`config/coverage.json`; extend coverage/inventory tests.

- [ ] Build explicit baseline schema tied to catalog claim IDs and source hashes.
- [ ] Test lost/duplicate claims and malformed/unknown baseline versions before implementation.
- [ ] Compare complete process artifact inventories for WIT/field/state/rule/behavior/layout additions, removals and changes; do not equate unchanged baseline with assertion coverage.
- [ ] Distinguish mapped evaluated changes from unreviewed surfaces; report exact artifact/selectors for gaps.
- [ ] Use existing collector completeness checks and add missing partial-response/duplicate identity regressions.
- [ ] Create reviewed baseline from current verified snapshots; never auto-accept drift during normal execution.

## Task 3: Unified run and outputs

**Files:** Create `src/doc_azure/audit.py`, `src/doc_azure/__main__.py`,
`tests/test_audit_runtime.py`; extend `src/delta/build.py` without duplicating evaluator logic.

- [ ] Write fixture E2E tests for clean/delta/coverage/acquisition/internal exit outcomes.
- [ ] Implement one async acquisition boundary reusing Settings and AzureReadClient.
- [ ] Pin both generations for each run, validate completeness, evaluate coverage then existing assertions.
- [ ] Publish four reports, global Markdown and structured JSON as one isolated run bundle.
- [ ] Keep timestamps in provenance, outside logical content hash.
- [ ] Test no network on offline replay, no Notion dependency, deterministic bytes and idempotency.
- [ ] Document `uv run python -m doc_azure run` and explicit refresh/replay options.

## Task 4: Real verification and delivery

**Files:** README, architecture/maintenance/handoff docs and existing publication evidence.

- [ ] Run complete current Azure audit read-only; inspect classifications and coverage, not just exit success.
- [ ] Rerun setup, all tests, local gates and historical secret scan.
- [ ] Commit cohesive verified changes and synchronize private GitHub with remote read-back.
- [ ] Only now request independent Opus 5 / Kimi K3 Notion AI falsification reviews through the required integrated browser.
- [ ] Reconcile actual findings with TDD; rerun affected gates.
- [ ] Update four canonical Notion pages, fetch and verify saved content; run strict publication gate.
- [ ] Audit all nineteen objective requirements; leave goal active if any evidence is missing.
