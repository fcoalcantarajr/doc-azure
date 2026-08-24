# Decisions

## Alternativa descartada: 01_fetch_wiki.py

Direct API calls without caching — rejected because AGENTS.md R5 requires idempotency.

## Alternativa descartada: 02_fetch_process.py

Hardcoded processTypeId — rejected because AGENTS.md requires runtime discovery.

## Alternativa descartada: 03_build_delta.py

LLM-based classification — rejected because AGENTS.md requires deterministic, evidence-based classification.

## Alternativa descartada: 04_publish_notion.py

webfetch on notion.so — rejected because Notion MCP must be used per mission spec.

## Task 1 — RED evidence

Command: `uv run pytest tests/test_delta_models.py tests/test_delta_evidence.py -q`

Result: collection failed as expected before implementation: `ModuleNotFoundError: No module named 'delta.models'` and `ModuleNotFoundError: No module named 'delta.evidence'` (2 collection errors).

## Task 1 — GREEN evidence

Focused command: `uv run pytest tests/test_delta_models.py tests/test_delta_evidence.py -q`

Result: `11 passed in 0.07s` with no warnings.

Full command: `uv run pytest -q`

Result: `58 passed, 17 subtests passed in 0.59s`.

## Task 1 — invariant-fix RED evidence

Command: `uv run pytest tests/test_delta_models.py tests/test_delta_evidence.py -q`

Result: `9 failed, 17 passed in 0.05s`. The failures proved the missing runtime
validation and immutability guarantees: `AttributeError: 'NoneType' object has
no attribute 'strip'`, `Failed: DID NOT RAISE ValueError`, list-backed
`AuditResult.findings`, and acceptance of the non-ASCII JSON Pointer index
`٠`.

## Task 1 — invariant-fix GREEN evidence

Focused command: `uv run pytest tests/test_delta_models.py tests/test_delta_evidence.py -q`

Result: `26 passed in 0.02s`.

Full command: `uv run pytest -q`

Result: `73 passed, 17 subtests passed in 0.06s`.

## Task 2 — RED evidence

Command: `uv run pytest tests/test_azure_client.py tests/test_snapshot.py -q`

Result: collection failed as expected before implementation with two errors:
`ImportError: cannot import name 'ALLOWED_OPERATIONS' from
'doc_azure.azure_client'` and `ModuleNotFoundError: No module named
'doc_azure.snapshot'`. These failures prove that the async semantic boundary
and atomic snapshot writer required by Task 2 did not yet exist.

## Task 2 — GREEN evidence

Focused command: `uv run pytest tests/test_azure_client.py tests/test_snapshot.py -q`

Result: `57 passed in 0.30s` with no warnings.

Compile command: `uv run python -m compileall -q src tests`

Result: exit code 0 with no output.

Full command: `uv run pytest -q`

Result: `105 passed in 0.66s` with no warnings.

Decision: classify Azure operations by an explicit method-route table. GET is
limited to the required wiki, process, and work-item read families; POST is
limited to exact WIQL and work-items-batch query routes with endpoint-specific
body validation. This implements the user's approved clarification without
authorizing any Azure mutation.

Rejected alternative: keep the synchronous `urllib` transport and wrap it in
coroutines. That would block the event loop, prevent one reused
`httpx.AsyncClient`, and duplicate retry and sanitization behavior in later
collectors.

Decision: stage every artifact and the complete manifest in a sibling directory
before swapping the snapshot. A failed collection can call `abort()` without
touching the current snapshot, and a failed directory swap restores the prior
snapshot.
