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

## Task 2 review hardening — RED evidence

Command: `uv run pytest tests/test_azure_client.py tests/test_snapshot.py -q`

Result: `31 failed, 57 passed in 0.45s`. The failures reproduced every reviewed
defect before production changes: literal/base64 PAT material reached HTTP from
paths and query keys; mutable query values were accepted; nested POST data
changed while blocked on `Semaphore(0)`; HTTP and transport exceptions exposed
response/path/exception PII; the versioned `CURRENT` resolver and CAS did not
exist; staging was not re-enumerated; symlinks/non-regular/missing/empty files
were not rejected; hashes were not recomputed under lock; and path aliases/NUL
did not consistently raise `SnapshotError`.

Additional RED: `uv run pytest
tests/test_snapshot.py::test_resolver_requires_canonical_current_pointer_bytes
-q` produced `3 failed in 0.06s`; the resolver incorrectly accepted CURRENT
without its single terminating newline and with leading or duplicate whitespace.

Additional RED: `uv run pytest
tests/test_snapshot.py::test_resolver_rejects_legacy_manifest_missing_required_field
-q` produced `2 failed in 0.06s`; a legacy manifest marked complete was accepted
without the required `collected_at` or `requests` field.

Additional RED: `uv run pytest
tests/test_snapshot.py::test_resolver_rejects_symlink_snapshot_container -q`
produced `1 failed in 0.05s` with `Failed: DID NOT RAISE SnapshotError`; the
resolver validated the generation target but still followed a symlink in its
intermediate `snapshots` container.

Additional RED: `uv run pytest
tests/test_snapshot.py::test_writer_rejects_symlink_snapshot_container_at_baseline
-q` produced `1 failed in 0.06s` with `Failed: DID NOT RAISE SnapshotError`;
the writer's construction-time CAS baseline independently followed the same
unsafe intermediate container.

## Task 2 review hardening — GREEN evidence and rulings

Focused command: `uv run pytest tests/test_azure_client.py
tests/test_snapshot.py -q`

Result: `95 passed in 0.13s` with no warnings. This includes independent
resolver and construction-time CAS checks for a symlinked `snapshots`
container.

Compile command: `uv run python -m compileall -q src tests`

Result: exit code 0 with no output.

Full command: `uv run pytest -q`

Result: `143 passed in 0.16s` with no warnings.

Ruling: all request inputs become private immutable state before the first
await. Paths and query keys reject literal, percent-encoded, plus-encoded, and
Basic-auth PAT variants; query values are copied JSON-compatible scalars; POST
bodies are serialized, credential-checked, deserialized, and schema-validated
before semaphore acquisition. This closes mutation-after-validation windows.

Ruling: an `AzureReadError` never embeds `str(RequestError)`, response text,
query/body values, or path identifiers. It exposes only method, a templated
route, a safe transport class, and/or HTTP status. Redaction is not an adequate
substitute because unknown PII cannot be enumerated reliably.

Ruling: the earlier whole-directory replacement is superseded. Publications
now create immutable version directories and atomically replace only CURRENT.
Writers capture a baseline at construction and compare it again under an
interprocess lock before staging validation, generation movement, and pointer
publication. A stale writer fails; a pointer-swap failure leaves the previous
generation selected; prior generations are never deleted.

Ruling: Tasks 3–6 must treat `out/wiki` and `out/process` as logical roots and
read through `resolve_snapshot_root`. CURRENT is authoritative and fails closed;
flat legacy fallback is read-only and available only when CURRENT is absent and
manifest shape, exact artifact set, regular-file status, and every hash verify.
A partial Task 4 refresh may retain cache entries only by reading the resolved
generation and writing them back through `SnapshotWriter`.

Rejected alternative: retain the preview `work/processdefinitions` 4.1 layout
and behavior routes. The current contract uses the official 7.1
`work/processes` fields, layout, and work-item-type behavior routes, keeping one
versioned endpoint model and one forced API version.

Limit: atomic rename and locking protect cooperating processes and readers from
process crashes around CURRENT publication. This task does not claim power-loss
durability because files and parent directories are not fsynced. It also does
not implement multiprocess stress tests or garbage collection; neither is
required for Tasks 3–6, and retaining generations is the safer audit default.

## Task 2 second scoped re-review — RED evidence

Command: `uv run pytest
tests/test_azure_client.py::test_rejects_sensitive_and_method_override_query_metadata_before_http
tests/test_snapshot.py::test_rejects_noncanonical_or_reserved_artifact_paths -q`

Result: `7 failed, 12 passed in 0.26s`. The four normalized query keys
`client_secret`, `password_hash`, `credential_blob`, and
`X-HTTP-Method-Override` reached the transport instead of failing before a
request record. Snapshot paths containing newline, tab, or DEL were written
instead of raising `SnapshotError`.

## Task 2 second scoped re-review — GREEN evidence and rulings

Focused command: `uv run pytest tests/test_azure_client.py
tests/test_snapshot.py -q`

Result: `102 passed in 0.15s` with no warnings.

Compile command: `uv run python -m compileall -q src tests`

Result: exit code 0 with no output.

Full command: `uv run pytest -q`

Result: `150 passed in 0.16s` with no warnings.

Ruling: the exact normalized key `continuationtoken` remains allowed, but all
other normalized keys are rejected when they contain `authorization`,
`credential`, `password`, or `secret`, end in `token`, or match a normalized
HTTP method-override alias. Rejection happens before both the transport and
request-record append.

Ruling: snapshot artifact paths reject every Unicode `Cc` control character,
including NUL, newline, tab, DEL, and the C1 control range, before filesystem
access.
