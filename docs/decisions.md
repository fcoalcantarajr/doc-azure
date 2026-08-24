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

## Task 3 — RED evidence

Command: `uv run pytest tests/test_wiki_collector.py -q`

Result: collection failed as expected with `1 error in 0.08s` and
`ModuleNotFoundError: No module named 'doc_azure.wiki_collector'`. This proves
the cache-first wiki collector, exact page-ID plan, fail-closed validation, and
atomic publication behavior did not exist before the Task 3 production change.

## Task 3 — GREEN evidence and rulings

Focused command: `uv run pytest tests/test_wiki_collector.py -q`

Result: `13 passed in 0.10s` with no warnings.

Full command: `uv run pytest -q`

Result: `163 passed in 0.22s` with no warnings.

Compile command: `uv run python -m compileall -q src tests
scripts/01_fetch_wiki.py`

Result: exit code 0 with no output. The standalone help command `uv run python
scripts/01_fetch_wiki.py --help` also exited 0 without loading credentials or
making a request.

Ruling: `out/wiki` is a logical snapshot root. A non-refresh run resolves and
validates the complete `CURRENT` generation before settings, PAT access, HTTP
client construction, clock evaluation, or `asyncio.run`. A cache hit reports
zero requests and leaves every logical-root byte, including `CURRENT`,
unchanged.

Ruling: the only requested pages are IDs 35, 10, 9, and 37 at the approved
page-by-ID route with `includeContent=true`. Each response must carry its exact
integer ID, an absolute path with a non-blank final segment, and non-blank
string content. `WikiPage.title` is derived from that final path segment because
the official response shape does not guarantee a separate `title` member. A
404, malformed response, or failed refresh aborts staging and cannot publish an
empty stub or replace the previous generation.

Ruling: Markdown content is stored verbatim in `<slug>.md`; every non-content
response member is preserved semantically in `<slug>.metadata.json`. The
manifest records only sanitized method/path receipts, with query values kept
out of receipt paths.

Rejected alternative: keep the old path-based, per-file cache. It could create
empty 404 stubs, mix stale and refreshed files, load the PAT on complete cache
hits, and offered no complete-snapshot identity for later evidence pointers.

## Task 3 review correction — RED evidence

Official-shape command: `uv run pytest
tests/test_wiki_collector.py::test_official_payload_without_title_derives_title_from_path
-q`

Result: `4 failed in 0.06s`. Every official-shape fixture omitted `title`, and
the collector rejected each one with `wiki page <id> title is missing` instead
of deriving the title from the documented absolute `path` member.

Race command: `uv run pytest
tests/test_wiki_collector.py::test_non_refresh_rechecks_cache_after_writer_creation_before_requesting
-q`

Result: `1 failed in 0.06s`. A competing writer published a complete snapshot
after the first cache check; the collector still made all four requests and
then failed the writer CAS with `stale snapshot writer cannot replace current
generation`. This isolates the missing post-construction cache recheck.

## Task 3 review correction — GREEN evidence and rulings

Focused command: `uv run pytest tests/test_wiki_collector.py -q`

Result: `24 passed in 0.08s` with no warnings.

Full command: `uv run pytest -q`

Result: `174 passed in 0.21s` with no warnings.

Compile command: `uv run python -m compileall -q src tests
scripts/01_fetch_wiki.py`

Result: exit code 0 with no output.

Ruling: the four audit fixtures mirror the official page-by-ID response shape
and intentionally omit `title`. `_parse_page` validates the raw absolute
`path`, rejects a missing or blank final segment, and derives the immutable
`WikiPage.title` from that segment. Snapshot metadata remains the raw response
minus only `content`; no derived title is inserted into evidence.

Ruling: a non-refresh collector performs a second complete-cache check after
constructing its baseline writer and before validating a client or creating
request coroutines. If another writer published in that interval, it aborts
its empty staging directory and returns the competing complete snapshot with
zero requests and no byte changes. Publication after the second check remains
protected by `SnapshotWriter` compare-and-swap and fails stale rather than
overwriting newer evidence.

## User-added adversarial Notion AI gate

Decision: before the four pages are updated, the final sanitized delta packet
will receive two separate reviews in the Notion desktop app through the
explicitly requested Computer Use plugin: Kimi K3 and Opus 5, both visibly set
to maximum effort. Their findings must be reconciled against raw evidence and
cannot substitute for the deterministic verifier. Missing model/effort, login,
MFA, or CAPTCHA fails closed; no alternative surface or model is substituted.

## Task 4 — RED evidence

Command: `uv run pytest tests/test_process_collector.py -q`

Result: collection failed as expected with `1 error in 0.10s` and
`ModuleNotFoundError: No module named 'doc_azure.process_collector'`. This
proves that the complete process collector, exact `typeId` discovery,
disabled-WIT preservation, five per-WIT evidence families, cache reuse, and
atomic refresh behavior did not exist before the Task 4 implementation.

## Task 4 — GREEN evidence and rulings

Focused command: `uv run pytest tests/test_process_collector.py -q`

Result: `18 passed in 0.14s` with no warnings.

Full command: `uv run pytest -q`

Result: `192 passed in 0.34s` with no warnings.

Compile command: `uv run python -m compileall -q src scripts tests`

Result: exit code 0 with no output. The standalone help command `uv run python
scripts/02_fetch_process.py --help` also exited 0 without loading credentials or
making a request.

Ruling: process discovery retains the complete `processes.json` response,
requires exactly one `name == "Processo-Agil"`, and uses that entry's documented
`typeId` for every subsequent route. Zero or duplicate exact-name matches and a
missing or unsafe `typeId` fail closed. The exact process response must repeat
both the selected name and `typeId`.

Ruling: `workitemtypes.json` preserves every active and disabled index entry.
The deterministic plan requests fields, states, rules, direct layout, and WIT
behavior associations for every entry, using its validated `referenceName` in
the modern 7.1 routes. Case-folded or Unicode-normalized route/file collisions
are rejected. A versioned `artifact-map.json` records the raw identity and the
five evidence paths for downstream evaluators.

Ruling: all fetched JSON objects are written to unpublished staging before
shape interpretation and are published only after every response validates.
List families use exact `count`/`value` envelopes, states use
`stateCategory`, layout is a direct `pages` object, process behavior ranks are
preserved, and behavior associations require `behavior.id` without inventing
an optional `isLegacyDefault`. A 404 or malformed family names the failing
artifact and aborts the generation.

Ruling: a complete non-refresh snapshot returns before settings, PAT, client,
clock, coroutine, or network work. A valid partial generation is copied through
`SnapshotWriter` byte-for-byte and requests only missing raw artifacts; a
second cache check closes the publication race. Refresh ignores cached payloads
and fetches all four globals plus all five families for every indexed WIT. One
`asyncio.run`, one `httpx.AsyncClient`, one `AzureReadClient`, and one shared
`Semaphore(8)` cover the live script, whose output contains only family counts
and a sanitized request count.

Rejected alternative: retain the old flat, display-name filenames and preview
4.1 fields route. That design omitted four evidence families, silently skipped
failed WITs, conflated active and disabled entries, performed two event-loop
runs, and could mix stale files with current responses.

## Task 4 self-review hardening — RED evidence

Command: `uv run pytest
tests/test_process_collector.py::test_collection_rejects_shapes_required_by_downstream_evaluators
-q`

Result: `4 failed in 0.51s`. The collector accepted fields without the
`required` boolean, a layout page without `sections`, a WIT behavior association
without `isDefault`, and a process behavior without `id`. Those responses had
valid top-level envelopes but could not support the exact downstream field,
layout, or behavior evaluators.

Correction after official-schema recheck: two premises in that first
self-review test were wrong and are not accepted as evidence. A field may omit
`required`; when present it must be boolean, and absence remains undeclared for
the evaluator. A global process behavior uses `referenceName`, not `id`; only a
WIT behavior association uses `behavior.id`. The tests and fixtures were
corrected before the production hardening was accepted. `isLegacyDefault` is
also optional and is validated as boolean only when present.

## Task 4 self-review hardening — GREEN evidence

Focused command: `uv run pytest tests/test_process_collector.py -q`

Result: `23 passed in 0.19s` with no warnings.

Full command: `uv run pytest -q`

Result: `197 passed in 0.37s` with no warnings.

Compile command: `uv run python -m compileall -q src scripts tests`

Result: exit code 0 with no output. Corrected validation now requires the
official nested layout chain, `referenceName` plus integer `rank` for global
behaviors, `behavior.id` plus boolean `isDefault` for associations, and boolean
types for optional `required` and `isLegacyDefault` only when those keys exist.

## Task 4 adversarial cleanup — RED evidence

Command: `.venv/bin/pytest
tests/test_process_collector.py::test_process_selection_rejects_non_uuid_type_id
tests/test_process_collector.py::test_failed_artifact_cancels_and_awaits_siblings_before_abort
-q`

Result: `2 failed in 0.13s`. The selector accepted the documented `typeId`
field even when it was not a UUID. Separately, the first artifact failure
escaped `asyncio.gather` while a sibling request remained live; the outer abort
therefore ran before sibling cancellation and cleanup completed. The direct
virtual-environment pytest entry point was used for this RED observation only
because the sandboxed `uv run` process could not access uv's existing cache;
all GREEN and completion gates still require the documented `uv run` commands.

## Task 4 adversarial cleanup — GREEN evidence

Focused command: `env UV_CACHE_DIR=/private/tmp/doc-azure-uv-cache uv run
--no-sync pytest tests/test_process_collector.py -q`

Result: `25 passed in 0.14s` with no warnings.

Full command: `env UV_CACHE_DIR=/private/tmp/doc-azure-uv-cache uv run
--no-sync pytest -q`

Result: `199 passed in 0.35s` with no warnings.

Compile command: `env UV_CACHE_DIR=/private/tmp/doc-azure-uv-cache uv run
--no-sync python -m compileall -q src scripts tests`

Result: exit code 0 with no output. The `--no-sync` and temporary cache path
only isolate uv from sandbox-inaccessible user cache metadata; the existing
lockfile-managed virtual environment remains the execution environment.

Ruling: the process `typeId` must be both a safe route segment and parseable as
a UUID. Its original text is preserved for route construction and evidence.
Artifact fetches are explicit tasks; on any exception or cancellation, every
sibling is cancelled and awaited with `return_exceptions=True` before the
original exception reaches the outer snapshot-abort boundary.

Independent scoped review verdict: `APPROVED`. The reviewer confirmed that the
cleanup settles sibling tasks before snapshot abort and that UUID validation
blocks arbitrary route identifiers while preserving the literal API identity.
