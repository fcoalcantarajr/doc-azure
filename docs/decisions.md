# Decisions

## Alternativa descartada: 01_fetch_wiki.py

Direct API calls without caching — rejected because AGENTS.md R5 requires idempotency.

## Alternativa descartada: 02_fetch_process.py

Hardcoded processTypeId — rejected because AGENTS.md requires runtime discovery.

## Alternativa descartada: 03_build_delta.py

LLM-based classification — rejected because AGENTS.md requires deterministic, evidence-based classification.

## Alternativa descartada: 04_publish_notion.py

webfetch on notion.so — rejected because Notion MCP must be used per mission spec.

## Decision — 2026-09-09: stable report verification across equivalent refreshes

The versioned Markdown reports retain collection provenance for auditability, but
`collected_at`, immutable snapshot generation IDs and manifest hashes are
run-specific. Comparing those fields literally made `verify.py` reject a fresh
equivalent collection even when every evaluated finding was unchanged. The gate
now canonicalizes only those two provenance lines before comparison; all other
report bytes, including process identity, findings, evidence pointers and
status, remain exact. A regression test recreates both snapshot generations
with identical artifacts and a different collection date.

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
will receive two separate reviews in Notion AI through the browser integrated
into this ChatGPT task: Kimi K3 and Opus 5, both visibly set to maximum effort.
The user explicitly superseded the earlier Notion desktop-app instruction on
2026-08-24. Their findings must be reconciled against raw evidence and cannot
substitute for the deterministic verifier. Missing model/effort, login, MFA,
or CAPTCHA fails closed; no external Notion app, alternative surface, or model
is substituted.

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
The deterministic plan requests fields, states, rules, expanded layout, and WIT
behavior associations for every entry, using its validated `referenceName` in
the modern 7.1 routes. Case-folded or Unicode-normalized route/file collisions
are rejected. A versioned `artifact-map.json` records the raw identity and the
five evidence paths for downstream evaluators.

Ruling: all fetched JSON objects are written to unpublished staging before
shape interpretation and are published only after every response validates.
List families use exact `count`/`value` envelopes, states use
`stateCategory`, process behavior ranks are preserved, and behavior
associations require `behavior.id` without inventing an optional
`isLegacyDefault`. The original root-`pages` layout contract was superseded
after the live direct-layout GET returned HTTP 400 for Test Case. Layout now
uses the base Work Item Type GET with `$expand=layout`, preserves the complete
raw WIT response, verifies its `referenceName`, and traverses
`/layout/pages`. A 404 or malformed family names the failing artifact and
aborts the generation.

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

## Task 5 — RED evidence

Command: `env UV_CACHE_DIR=/private/tmp/doc-azure-uv-cache uv run --no-sync
pytest tests/test_delta_catalog.py tests/test_delta_evaluator.py -q`

Result: collection failed as expected with `2 errors in 0.09s`; both failures
were `ModuleNotFoundError: No module named 'delta.catalog'`. This proves that no
typed catalog schema or explicit evaluator registry existed. The RED suite
already specifies exact documentary hashes/excerpts, active-versus-disabled
WIT handling, exact field/rule/layout/behavior pointers, and current-state
limits for historical claims.

## Task 5 — iterative adversarial RED evidence

The first self-review added a malformed `count_equals` family test. It failed
once in `0.07s`, proving that a non-envelope family could pass schema loading;
the family allowlist then made the focused suite green. A second focused test
for exact state-name evidence failed once in `0.06s` because no
`state_presence` evaluator existed; the evaluator now returns the exact state
name pointer rather than inferring history from a count.

The first independent catalog review returned `NEEDS_FIXES`: all 111 original
references were exact, but page 9 omitted material versions 0.0 through 0.9,
including RTC fields, native effort fields, Incidente, transition-date fields,
and homologation states. A new production-catalog coverage test and
`wit_presence` test failed as expected with `2 failed, 23 passed in 0.14s`.
The catalog now contains 156 unique claims: 24 for page 35, 20 for page 10, 67
for page 9, and 45 for page 37. All 156 SHA-256/line/excerpt triples were
rechecked against the four exact source files.

The first independent code review also found bool/int equality aliasing,
post-resolution artifact reads that did not recheck the manifest hash, and an
underspecified artifact-map schema. Equality now compares normalized values
only when their normalized types match. Snapshot artifact reads use no-follow
directory/file descriptors and recheck the manifested digest in the same read
operation. The artifact map requires its exact schema, UUID process ID, global
paths, WIT identity, and all five per-WIT families.

The second review found two final issues. Seven illustrative transition-field
claims cited generic section headings rather than the named examples; they now
point exactly to changelog lines 294 and 450 and explicitly remain spot checks,
while separate rows classify complete per-state coverage as ambiguous. The map
also was not cross-checked with `process.json`; the targeted regression failed
once in `0.10s`, then passed after `process_name`/`process_id` were required to
equal the collected `name`/`typeId`.

## Task 5 — GREEN evidence and rulings

Focused command: `env UV_CACHE_DIR=/private/tmp/doc-azure-uv-cache uv run
--no-sync pytest tests/test_delta_evaluator.py::test_artifact_map_identity_must_match_process_artifact
tests/test_delta_evaluator.py tests/test_delta_catalog.py -q`

Result: `26 passed in 0.18s`.

Full command: `env UV_CACHE_DIR=/private/tmp/doc-azure-uv-cache uv run
--no-sync pytest -q`

Result: `226 passed in 0.47s`.

Compile command: `env UV_CACHE_DIR=/private/tmp/doc-azure-uv-cache uv run
--no-sync python -m compileall -q src scripts tests`

Result: exit code 0 with no output. `git diff --check` also exited zero.

Ruling: `CONFIRMADO` and `DIVERGENTE` compare only the current, exact process
configuration. Historical chronology, board practice, organizational adoption,
external jobs, policy compliance, and semantic responsibility remain
`NAO_VERIFICAVEL_API_PROCESSO` or `AMBIGUO`; current presence never proves when
or why a change occurred. Example fields do not stand in for full field-family
coverage.

Final independent verdicts: `APPROVED` for the 156-claim catalog and
`APPROVED` for the evaluator/snapshot hardening. Reviewers confirmed exact
documentary pointers, material changelog coverage, illustrative limits, strict
process identity cross-checking, no-follow/hash reads, and the 26-test focused
gate.

## Task 6 — RED evidence

Builder command: `uv run pytest tests/test_delta_builder.py -q`

Result: collection failed as expected with `ModuleNotFoundError: No module
named 'delta.build'` in `0.07s`. The tests already required all four fixed
pages, catalog order, byte-for-byte determinism, and preservation of existing
reports when claim evaluation fails.

Verifier command: `uv run pytest tests/test_verify.py -q`

Result: collection failed as expected with `ImportError: cannot import name
'VerificationError' from 'verify'` in `0.08s`. The tests already required a
temporary non-mutating rebuild and rejection of a resolvable but wrong JSON
pointer, a nearby rather than cataloged documentary line, report-status
mutation, subprocess failure, secret leakage, and incomplete ignore policy.

Notion hardening command: `uv run pytest tests/test_prepare_notion.py -q`

Result: collection failed as expected with `ImportError: cannot import name
'load_publication_manifest' from 'delta.notion'` in `0.08s`. This adversarial
cycle was added after the first implementation exposed a real weakness: it
declared a marker in the manifest without proving the marker existed in the
body, and it had no strict disk-manifest loader.

Renderer and initial Notion tests were written by isolated implementation
agents before their production modules, but their terminal receipts were lost
when both agent turns were interrupted by a service usage-limit error. This is
recorded as missing process evidence rather than reconstructed as a successful
RED observation. The later Notion hardening RED above is retained and the
renderer behavior is covered by the focused and full GREEN suites.

## Task 6 — GREEN evidence and rulings

Focused command: `uv run pytest tests/test_delta_render.py
tests/test_delta_builder.py tests/test_prepare_notion.py tests/test_verify.py -q`

Result: `28 passed in 0.16s`.

Compile command: `uv run python -m compileall -q src scripts verify.py tests`

Result: exit code 0 with no output.

Ruling: report generation is offline and explicit. It evaluates all 156
catalog entries, preserves catalog order, renders the exact Portuguese status
model, stages every report before replacement, and produces stable bytes. The
gate rebuilds into a temporary directory and compares exact bytes, so a pointer
that merely resolves cannot validate the wrong value or status.

Ruling: local Notion preparation is separate from external publication. The
manifest binds exact body hashes and markers to four pre-existing page IDs,
their common parent, and canonical URLs. Preparation never creates or updates a
Notion page; connector read-back must prove those identities and hashes.

Ruling: the mandatory Kimi K3 and Opus 5 reviews use separate chats and maximum
effort in Notion AI. Per the user's explicit correction, this UI work must run
only in the browser integrated into ChatGPT. The external Notion desktop app is
not an authorized fallback. Missing exact model/effort controls or an
authentication barrier fails the publication gate closed.

## Task 7 — adversarial catalog reconciliation

Ruling: compound documentary claims retain multiple exact fragments from one
page hash instead of weakening evidence to a range or nearby-text search. Every
fragment is verified and rendered. A confirmed current-state finding retains
its cataloged limit when that limit qualifies historical chronology, practice,
or semantics.

Ruling: artifact-map schema 2 is required because layout artifacts now preserve
the complete expanded WIT response. Old schema-1 layout evidence fails closed;
it is never reinterpreted or rewritten in place. The successful GET-only refresh
selected process generation `73fca39c089f4f729909385a432c6405`, collected at
`2026-08-24T19:56:55.605291+00:00`, with complete manifest SHA-256
`999c80597a527e1ba0316e2eeaffacaf0f17be172458d4609874cdadc5453987`.

Ruling: the production catalog contains 222 source-backed claims. Technical
behavior ranks and WIT associations are current process facts, but remain
`AMBIGUO` with respect to Flight Levels, real parentage, and board placement.
Current configuration can corroborate a changelog claim, but cannot prove its
date, authorship, sequence, or causal account.

Ruling: the four reports were rebuilt twice from the same immutable generations
and produced identical hashes. Local Notion preparation reproduced those exact
hashes and `uv run python verify.py` returned `GATE_OK`. External Notion review,
update, and connector read-back remain a separate Task 8 gate.

Controller adjudication: generation `73fca39c089f4f729909385a432c6405`
supersedes the earlier fixed generation
`0a3d5d62e8384b039e238ab235da96b5`. The refresh used 109 GET-only receipts;
all raw Azure payload bytes are identical between the generations, while only
`manifest.json` and `artifact-map.json` changed to bind the corrected schema-2
layout mapping. This recorded ruling, rather than reviewer prose, authorizes the
new generation for final evaluation.

## Task 6 — independent adversarial review

The first independent verdict was `NEEDS_FIXES` with two medium findings. The
four reports were staged but replaced sequentially without rollback, so a
failure on the third replacement could leave a mixed set. Separately,
`verify_reports` and `verify_layout` followed symlinks for versioned reports.

Targeted RED command: `uv run pytest
tests/test_delta_builder.py::test_build_all_reports_rolls_back_every_replaced_report_on_publish_failure
tests/test_verify.py::test_verify_reports_rejects_a_symlink_even_with_identical_bytes
-q`

Result: `2 failed in 0.09s`. The simulated third replacement left the first two
new files in place, and an identical external symlink passed the gate.

Targeted GREEN command: the same command.

Result: `2 passed in 0.16s`. The builder now saves regular-file backups and
rolls back every earlier replacement after an ordinary publication failure.
The gate uses `O_NOFOLLOW`, requires regular files, and rejects symlinks in both
report comparison and required-layout checks. This is rollback-backed batch
publication, not a claim of crash-atomicity across four filesystem paths.

Full command: `uv run pytest -q`

Result before the final ignore-policy fixture was added: `240 passed in 0.57s`.

Final independent verdict: `APPROVED`. The reviewer confirmed both prior
findings were closed and found no additional material regression in fixed
Notion identities, hashes, secret handling, deterministic reports, or the
legacy-contract removal.

## Task 6 — setup entrypoint correction

The one-command entrypoint check exposed an additional legacy defect after the
main review: `python scripts/setup.py --help` loaded `AZDO_PAT` before argument
parsing, and the setup created obsolete `out/raw`, `out/normalized`, and
`out/reports` directories.

RED command: `uv run pytest
tests/test_settings.py::SettingsTests::test_setup_is_idempotent
tests/test_script_entrypoints.py::test_script_help_never_requires_credentials
-q`

Result: `2 failed, 4 passed in 2.07s`. The exact directory contract differed,
and `setup.py --help` exited 1 with a missing-credential exception.

GREEN command: `uv run pytest
tests/test_settings.py::SettingsTests::test_setup_is_idempotent
tests/test_script_entrypoints.py -q`

Result: `6 passed in 1.46s`. Setup now parses help before configuration,
returns a sanitized failure on invalid local configuration, and idempotently
creates only `out/wiki`, `out/process`, and `out/notion`.

## Task 8 — semantic Notion publication gate

RED command: `uv run pytest -q tests/test_notion_publication_gate.py`

Result: `19 failed in 0.15s`. The prepared Notion bodies were byte-oriented
GFM copies, and the project had no strict semantic parser, private-GitHub-bound
review packet, dual-model review receipts, reconciliation receipt, or
publication read-back gate.

Decision: represent the report and its Notion rendering through one canonical
semantic model. Bind deterministic review artifacts to the private repository,
require independent Kimi K3 and Opus 5 receipts from distinct in-app browser
chats at maximum effort, reconcile every review finding, and accept publication
only after raw-receipt-backed hierarchy, duplicate-search, freshness, title,
marker, and semantic-equivalence checks pass for all four existing pages.

Entrypoint RED command: `uv run pytest -q
tests/test_script_entrypoints.py::test_notion_entrypoint_exposes_review_and_strict_publication_modes
tests/test_verify.py::test_require_publication_delegates_to_the_strict_external_gate`

Result: `2 failed in 0.15s`. The one-command interface exposed neither the
private-repository review binding nor the strict publication mode, and the
repository gate still delegated to the legacy byte-oriented fetched-body check.

Entrypoint GREEN: the same command returned `2 passed in 0.24s`. Full GREEN:
`uv run pytest -q` returned `300 passed in 1.05s`; `uv run python verify.py`
returned `GATE_OK` after deterministic preparation against the intended private
repository URL.

## 2026-08-26 — fresh Azure read-only generation

The Wiki and Processo-Agil collectors were rerun with `--refresh`. The Wiki
generation `3da21e0bad63483fab84d4c997b64040` contains four GET receipts; the
process generation `86456cdbde1c47f5bb579e9f0dbcfbe4` contains 110 artifacts
and 109 GET receipts. Rebuilding twice changed no semantic finding or report
hash beyond the expected provenance lines. Decision: supersede the 2026-08-24
generation for publication because it is fresher and equally read-only, while
recording that stability is evidence of no observed process delta, not proof
that the documentation is complete or historically accurate.

## 2026-09-08 — moved repository and fresh live evidence

The repository moved to `/Volumes/SSD/codigo-trabalho/doc-azure`. The registered
linked worktree pointed to a missing gitdir, while the moved residual directory
contained only ignored `.venv` and `.env` entries. We pruned only the stale Git
registration and recreated `fix/adversarial-delta-audit` below the ignored
`.worktrees/` directory; both the residual directory and dirty `main` checkout
were preserved.

The ignored Azure snapshots did not move with the branch, so treating the
August reports as current would have left a provenance gap. Both collectors
were therefore rerun. The new generation has four Wiki GET receipts and 109
process GET receipts. Three reports changed only in provenance. `leiame` also
changed the observed technical custom-field union from 209 to 214; its status
remains `CONFIRMADO` because the documentary claim is the lower bound `50+`.
This is a current implementation change, not evidence about authorship, cause,
or the historical sequence of the five additional fields.

## 2026-09-08 — adversarial whole-branch review hardening

Two independent read-only reviewers inspected the branch from merge base
`31078f9bff58c76da40e0d850df80598f6f2a622`. The fidelity review confirmed the
local deliverables and identified only the still-pending external Notion gate
plus a stale GitHub receipt. The standards review found three material defects:
raw external receipts were hashed but not interpreted, collector cache readers
could follow an artifact swapped after initial validation, and README dependency
claims disagreed with executable metadata.

External-evidence RED: three focused tests showed that a mismatched browser
model, wrong raw fetch page, and wrong raw search results were not rejected.
GREEN: the gate now parses raw browser and Notion tool-result envelopes and
cross-checks every derived fact with the side receipts and saved response/body.
Focused result: `27 passed in 0.65s`.

Snapshot RED: two tests replaced a valid wiki/process artifact with an
identical-content symlink after `resolve_snapshot_root`; both cache readers
accepted it. GREEN: the shared snapshot module now owns strict manifest parsing,
and collectors read manifested artifacts through the no-follow, digest-checking
primitive. Focused result: `2 passed in 0.20s`; snapshot/collector regression:
`97 passed in 0.75s`.

Metadata RED: the new contract test showed `pytest` in runtime dependencies and
README claims of Python 3.13/`httpx>=0.28.1` despite the approved design and
package contract using Python 3.11+/`httpx>=0.25.0`. GREEN: `pytest>=8.0.0` is
now in the default development group, the runtime has only `httpx`, and README
matches `pyproject.toml`. Focused result: `1 passed in 0.01s`.

The latest full regression after these corrections returned `311 passed in
2.99s`; compile, `git diff --check`, and `uv run python verify.py` also passed.
The raw tool captures remain local evidence rather than cryptographic server
attestations, an interface limitation documented explicitly rather than hidden.

## 2026-09-09 — deterministic documentary coverage increment

The expanded objective requires unknown prose to become an explicit coverage
gap rather than an inferred assertion. Added a pure line-fingerprint comparison
component with immutable source-span records. It normalizes CRLF to LF only:
trimming whitespace, case folding, Unicode folding and line deduplication were
rejected because they can erase material Markdown or documentary differences.

RED: `ImportError: cannot import name 'coverage' from 'delta'` established the
missing module before implementation. GREEN: 14 focused cases passed; the full
suite returned 325 passed in 2.87s. This is not yet the integrated coverage gate.
The runtime plan tracks baseline validation, inventory coverage, unified outputs,
real execution and external publication/review as separate unfinished tasks.

## 2026-09-09 — source-bound documentary coverage

Added a strict versioned documentary baseline consumer tied to the catalog byte
hash, ordered claim IDs, all four page source hashes and ordered line hashes.
Unknown keys, duplicate JSON keys, boolean schema versions, lost or duplicated
claim inventory and missing pages fail closed. A materially changed page returns
explicit change spans and contributes no evaluable claims; unchanged pages remain
available. CRLF-only equivalence updates the in-memory evidence hash, then checks
every exact excerpt against the actual current snapshot bytes. Catalog files are
never rewritten during assessment.

RED: `ImportError: cannot import name 'document_coverage' from 'delta'`.
GREEN: `24 passed in 0.41s` across both coverage modules, including integration
with the real catalog, snapshot reader and existing evaluator. No alternate
semantic evaluator was introduced. Baseline authoring/review and unified run
integration are still pending; this is not evidence of whole-process coverage.

Builder integration RED: two failures reported unexpected keyword argument
`coverage_baseline`. CLI RED: the subprocess rejected `--coverage-baseline`.
GREEN: the option now enforces documentary coverage before report publication,
accepts tested cosmetic equivalence and preserves old report bytes on a gap.
Focused integration/build/entrypoint suite: 24 passed; full suite: 338 passed in
2.89s. The option remains explicit until a reviewed live baseline is delivered;
the unified application must make coverage mandatory rather than inherit this
legacy compatibility default.

## 2026-09-09 — unified deterministic runtime and process inventory

Added a single-command pipeline reusing both collectors, documentary coverage,
the existing evaluator/renderer and atomic snapshot publication. JSON inventory
fingerprints preserve types, empty containers, array order and exact escaped
pointers. Drift remains an explicit coverage gap, even when individual claims
still evaluate. No second semantic evaluator or AI service was introduced.

RED: missing `process_coverage` and `audit` modules; executable command missing.
Behavioral RED then exposed refresh returning code 4 (missing required `now`
argument) and a corrupt snapshot returning 4 instead of validation code 3.
GREEN: 23 focused cases, including real collectors over fixture HTTP (18 GETs),
subprocess CLI, gap bundles and deterministic replay; full suite 361 passed in
3.42s. Live baseline review remains a required subsequent step; normal execution
never manufactures a baseline to suppress a gap.

## 2026-09-09 — reviewed production baselines and identifier closure

Baseline candidates were prepared from the complete local snapshots with no
network or file mutation outside ignored `out/baseline-candidate/`. The exact
candidate bytes were checked against the committed configuration: 222 catalog
claim IDs, four page line inventories and 40,559 process JSON nodes across 110
artifacts. The process candidate stores hashes and JSON pointers, not response
bodies.

Fresh `scripts/run_audit.py --refresh` evidence collected four Wiki pages in four
GETs and produced 110 process artifacts from 109 GETs. The extra artifact is the
locally derived inventory map. It returned `DELTAS` (code 1),
coverage complete, zero gaps and 222 findings (123 confirmed, 59 divergent, 31
API-unverifiable and 9 ambiguous). Reports were rebuilt for the fresh generation
and the repository gate returned `GATE_OK`.

Adversarial RED: three process fixtures with duplicate field/state/rule
identifiers were accepted. GREEN: the collector now rejects duplicate normalized
identities before snapshot publication; full suite then returned 367 tests, and
the final runtime/clean/internal/no-network/process-drift additions returned 373 tests. The
coverage gate also became part of `verify.py`; a report cannot pass the gate by
omitting the reviewed documentary baseline.

The review prompt was expanded to require explicit falsification of false MATCHes
and deltas, coverage gaps, fragile heuristics, hidden AI dependencies, fail-open
paths, security defects and nondeterminism, and to require that reviewers verify
the runtime works without AI. It names Kimi K3 and Opus 5 at maximum effort and
the integrated ChatGPT browser as hard constraints. Focused prompt tests passed;
the regenerated prompt hash is recorded in `docs/notion-publication.md`.

## 2026-09-09 — adversarial provenance closure

The external reviews exposed one reproducible integrity gap in the local gate:
report comparison correctly ignored run-specific snapshot identity, but it also
accepted a versioned provenance line whose generation and manifest hash did not
identify any immutable local snapshot. The logical comparison and provenance
authentication are now separate checks. A versioned report may differ from the
current equivalent generation, but each masked provenance line must resolve to
a complete immutable generation whose `collected_at` and manifest SHA-256 match.

RED: `test_verify_reports_rejects_unverifiable_versioned_provenance` failed with
`Failed: DID NOT RAISE VerificationError` after replacing the Wiki generation
and manifest hash with well-formed zero values. GREEN: the new case, the fresh
equivalent-generation case, and the exact-unmodified-output case all passed
(`3 passed in 3.01s`). No delta report or publication semantic hash changed.

## 2026-09-09 — native Notion connector serialization

The live connector read-back exposed two equivalent representations that the
local parser had not modeled: HTML-style `<br>` elements and Notion-generated
Markdown links whose target is exactly the visible hostname token. The parser
now normalizes only those two cases. A link whose target differs from its visible
label remains material and fails the semantic hash check. The connector's native
successful update receipt contains only `page_id`; its canonical Notion URL is
derived only for that exact one-field schema, while the prior expanded schema
retains its strict URL and status checks.

RED: the two live-format regressions failed with `Notion table XML is invalid`
and `update URL is invalid`. GREEN: four focused acceptance and adversarial cases
passed (`4 passed in 0.34s`), including rejection of a link to another target.

The same live read-back then exposed three additional connector conventions:
JSON brackets/braces are backslash-escaped in cells, a page emoji prefixes the
top-level title while the properties title remains plain, and the extracted
body omits the conventional final newline kept by the local receipt file. Each
normalization is narrow: the emoji must be the exact structured page icon, only
one optional final newline is tolerated, and non-equivalent links still fail.

RED: the live publication gate first rejected `raw fetch body differs`, then
rejected the escaped JSON semantic content; the focused emoji fixture also
failed with `fetch title is not present in page properties`. GREEN: the focused
connector serialization and adversarial-link cases passed, both hierarchy
fetches parsed, and the complete external-evidence gate returned
`NOTION_PUBLICATION_OK`.
