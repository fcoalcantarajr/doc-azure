# Adversarial Delta Audit Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce and publish four evidence-backed delta reports comparing the four fixed Azure DevOps wiki pages with the current `Processo-Agil` definition, while preserving the user's dirty `main` checkout.

**Architecture:** Replace keyword heuristics with a versioned claim catalog and typed evaluators. A single async, semantically read-only HTTP boundary collects complete raw snapshots atomically; deterministic renderers and a non-mutating verifier prove each claim before Notion publication.

**Tech Stack:** Python 3.13 via `uv`, `httpx>=0.28.1`, `pytest`, Azure DevOps REST API 7.1, authenticated Notion connector.

**Spec:** `docs/superpowers/specs/2026-08-24-adversarial-delta-audit-design.md`

## Global Constraints

- Work only in `/private/tmp/doc-azure-adversarial-fix` on branch `fix/adversarial-delta-audit`; never modify or clean the user's dirty `main` checkout.
- Azure organization is `bancodonordeste`; process is exact name `Processo-Agil`, expected ID `9d82e632-9028-4a6b-86f8-3edb3281cb15`; wiki ID is `87014e24-4977-4d27-8e12-c05208008d95`; page IDs are `35`, `10`, `9`, and `37`.
- Azure operations are semantically read-only. GET is permitted only on the wiki/process/work-item read families. POST is permitted only for exact WIQL and work-items-batch query routes; creation POST, PUT, PATCH, DELETE, redirects, absolute URLs, and method override are forbidden.
- The live audit should use GET only unless a cataloged material claim explicitly needs work-item data. Every executed method and sanitized route is recorded.
- Never print, log, commit, persist in reports, or publish `AZDO_PAT`, Notion credentials, Authorization headers, or encoded variants.
- Python code and technical docs are English. The four delta reports and their Notion page bodies are Brazilian Portuguese.
- Status is exactly one of `CONFIRMADO`, `DIVERGENTE`, `NAO_VERIFICAVEL_API_PROCESSO`, or `AMBIGUO`.
- Every row has a stable ID, documentary value, implemented value, exact documentary evidence, exact Azure evidence or explicit limitation, and a descriptive impact/limit when not confirmed.
- No inference from current state may prove historical chronology. Missing collection is never evidence of absence.
- Use one `asyncio.run` per script, one reused `httpx.AsyncClient` per live run, and one shared semaphore. Retry only 408, 429, 500, 502, 503, and 504; honor `Retry-After`; never retry 401/403.
- Without `--refresh`, a complete cache produces zero network calls and byte-identical output. Refresh writes to staging and replaces a snapshot only after complete success.
- Tests use fixtures, named fakes, and temporary directories; they never require ignored `out/` or live network.
- Stage explicit paths only. Never use recursive/wildcard staging, rebase, amend, force push, `--no-verify`, or destructive cleanup.
- Notion updates target the existing audit hub and four child pages; do not create duplicate report pages.

## File Map

| Path | Responsibility |
|---|---|
| `AGENTS.md` | Binding semantic read-only, evidence, status, TDD, language, and Git rules. |
| `.gitignore` | Secret, cache, virtualenv, build, output, editor/OS, log, and database exclusions. |
| `src/delta/models.py` | Immutable `FindingStatus`, `EvidencePointer`, `Finding`, and `AuditResult`. |
| `src/delta/evidence.py` | Exact Markdown/hash and JSON Pointer resolution. |
| `src/delta/catalog.py` | Load and validate the explicit claim catalog. |
| `src/delta/evaluator.py` | Typed evaluator registry and finding production. |
| `src/delta/render.py` | Deterministic Portuguese Markdown rendering. |
| `src/delta/__init__.py` | Narrow public exports only. |
| `src/doc_azure/azure_client.py` | Async semantic allowlist, retries, redaction, request records. |
| `src/doc_azure/snapshot.py` | Atomic files, hashes, manifests, staging/commit of raw snapshots. |
| `src/doc_azure/wiki_collector.py` | Cache-first collection of four wiki pages and metadata. |
| `src/doc_azure/process_collector.py` | Cache-first complete process, WIT, fields, states, rules, layouts, and behaviors collection. |
| `config/wiki_claims.json` | Versioned per-page claims, excerpts, parameters, and limitations. |
| `scripts/01_fetch_wiki.py` | One-command wiki collection entry point. |
| `scripts/02_fetch_process.py` | One-command process collection entry point. |
| `scripts/03_build_delta.py` | Offline catalog evaluation and report generation. |
| `scripts/04_prepare_notion.py` | Deterministic Notion bodies/manifests and fetched-content verification. |
| `verify.py` | Non-mutating end-to-end gate. |
| `tests/fixtures/audit/` | Minimal complete wiki/process/catalog fixtures. |
| `tests/test_delta_models.py` | Status and finding invariants. |
| `tests/test_delta_evidence.py` | Exact pointer/excerpt/hash resolution. |
| `tests/test_delta_evaluator.py` | Evaluator kinds and epistemic classifications. |
| `tests/test_delta_render.py` | Four deterministic Portuguese reports. |
| `tests/test_azure_client.py` | Method-route boundary, retry, redirect, redaction. |
| `tests/test_snapshot.py` | Atomic manifest and refresh behavior. |
| `tests/test_wiki_collector.py` | Zero-call cache and four-page collection. |
| `tests/test_process_collector.py` | Complete endpoint plan, metadata preservation, failure atomicity. |
| `tests/test_verify.py` | Gate rejects false evidence, mutation, stale Notion, and subprocess failure. |
| `tests/test_prepare_notion.py` | Payload hashes and fetched-page equivalence. |
| `docs/session-2026-08-24.md` | Commands, RED/GREEN evidence, live receipts, uncertainty, and final audit. |

---

### Task 1: Establish the immutable evidence-backed finding model

**Files:**
- Create: `src/delta/models.py`
- Create: `src/delta/evidence.py`
- Modify: `src/delta/__init__.py`
- Create: `tests/test_delta_models.py`
- Create: `tests/test_delta_evidence.py`
- Modify: `docs/decisions.md`

**Interfaces:**
- Produces: `FindingStatus(str, Enum)` with the four exact Portuguese values.
- Produces: `EvidencePointer(path: str, selector: str)`.
- Produces: `Finding(id, finding, status, documented, implemented, doc_evidence, azure_evidence, impact_or_limit)`.
- Produces: `resolve_json_pointer(document: object, pointer: str) -> object`.
- Produces: `verify_doc_line(path: Path, line: int, excerpt: str, source_sha256: str) -> None`.

- [ ] **Step 1: Write failing model tests**

```python
def test_finding_status_literals_are_exact():
    assert {status.value for status in FindingStatus} == {
        "CONFIRMADO",
        "DIVERGENTE",
        "NAO_VERIFICAVEL_API_PROCESSO",
        "AMBIGUO",
    }


def test_non_confirmed_finding_requires_impact_or_limit():
    with pytest.raises(ValueError, match="impact_or_limit"):
        Finding(
            id="35-STATE-001",
            finding="Quantidade de estados de Bug",
            status=FindingStatus.DIVERGENTE,
            documented="8",
            implemented="9",
            doc_evidence=EvidencePointer("out/wiki/leiame.md", "L10"),
            azure_evidence=EvidencePointer("out/process/Bug_states.json", "/count"),
            impact_or_limit="",
        )
```

- [ ] **Step 2: Write failing exact-evidence tests**

```python
def test_doc_evidence_rejects_nearby_but_not_exact_text(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("# Bug\nPossui 8 estados\n", encoding="utf-8")
    digest = hashlib.sha256(page.read_bytes()).hexdigest()
    with pytest.raises(EvidenceError, match="exact excerpt"):
        verify_doc_line(page, 1, "Possui 8 estados", digest)


def test_json_pointer_returns_exact_array_item():
    document = {"value": [{"id": "System.State"}, {"id": "Custom.Bloqueado"}]}
    assert resolve_json_pointer(document, "/value/1/id") == "Custom.Bloqueado"
```

- [ ] **Step 3: Observe RED**

Run: `uv run pytest tests/test_delta_models.py tests/test_delta_evidence.py -q`

Expected: collection fails because `delta.models` and `delta.evidence` do not exist. Append the command and relevant failure to `docs/decisions.md` before implementation.

- [ ] **Step 4: Implement the immutable model and exact evidence primitives**

Use frozen dataclasses, reject duplicate/blank IDs, require documentary evidence for every cataloged wiki claim, require Azure evidence for confirmed/divergent current-process claims, and require a non-empty limit for non-confirmed findings. JSON Pointer decoding supports `~0` and `~1`, integer array indices, root pointer `""`, and raises `EvidenceError` with the failing segment.

- [ ] **Step 5: Preserve the legacy surface until the atomic report transition**

Export the new model/evidence API from `src/delta/__init__.py` without removing the legacy renderer/classifier yet. Task 6 removes that surface in the same commit that migrates the builder, verifier, reports, and legacy tests, so no intermediate commit breaks the existing suite.

- [ ] **Step 6: Verify GREEN and the full existing suite**

Run: `uv run pytest tests/test_delta_models.py tests/test_delta_evidence.py -q`

Expected: all focused tests pass with no warnings.

Run: `uv run pytest -q`

Expected: the pre-transition legacy suite and new tests all pass.

- [ ] **Step 7: Commit exact paths**

Stage only `src/delta/models.py`, `src/delta/evidence.py`, `src/delta/__init__.py`, `tests/test_delta_models.py`, `tests/test_delta_evidence.py`, and `docs/decisions.md`.

Commit: `refactor(delta): establish evidence-backed finding model`

---

### Task 2: Unify the async semantic REST boundary and atomic snapshots

**Files:**
- Modify: `AGENTS.md`
- Modify: `src/doc_azure/azure_client.py`
- Create: `src/doc_azure/snapshot.py`
- Modify: `tests/test_azure_client.py`
- Create: `tests/test_snapshot.py`
- Modify: `docs/api-contract.md`
- Modify: `docs/decisions.md`

**Interfaces:**
- Produces: `AllowedOperation(method: str, path_pattern: Pattern[str])`.
- Produces: `RequestRecord(method: str, path: str)` with sanitized path only.
- Produces: `AzureReadClient(http: httpx.AsyncClient, base_url: str, pat: str, semaphore: asyncio.Semaphore, sleeper: AsyncSleeper = asyncio.sleep)`.
- Produces: `await AzureReadClient.request_json(method, path, *, query=None, body=None) -> dict[str, object]`.
- Produces: `SnapshotWriter(root: Path)` with `write_json`, `write_text`, `commit_manifest`, and `abort`.

- [ ] **Step 1: Write failing async boundary tests**

```python
def test_allows_only_semantic_reads():
    assert is_allowlisted_read("GET", "/_apis/work/processes/x/workitemtypes")
    assert is_allowlisted_read("POST", "/project/_apis/wit/wiql")
    assert is_allowlisted_read("POST", "/project/_apis/wit/workitemsbatch")
    assert not is_allowlisted_read("POST", "/project/_apis/wit/queries")
    assert not is_allowlisted_read("PATCH", "/_apis/work/processes/x")


def test_redirect_is_rejected_without_second_request():
    fake = FakeAsyncHttp([FakeResponse(302, headers={"Location": "https://evil.invalid"})])
    with pytest.raises(AzureReadError, match="redirect"):
        asyncio.run(make_client(fake).request_json("GET", "/_apis/work/processes"))
    assert len(fake.requests) == 1
```

Add focused tests for 401/403 no retry, 429 `Retry-After`, transient retry cap, PAT/Authorization redaction, query credential rejection, absolute URL rejection, API-version override, invalid JSON, and POST-body restriction.

- [ ] **Step 2: Write failing snapshot tests**

```python
def test_failed_refresh_keeps_previous_snapshot(tmp_path):
    current = tmp_path / "process"
    current.mkdir()
    (current / "process.json").write_text('{"name":"old"}', encoding="utf-8")
    writer = SnapshotWriter(current)
    writer.write_json("process.json", {"name": "new"})
    writer.abort()
    assert json.loads((current / "process.json").read_text()) == {"name": "old"}
```

- [ ] **Step 3: Observe RED**

Run: `uv run pytest tests/test_azure_client.py tests/test_snapshot.py -q`

Expected: new async/client and snapshot expectations fail. Record the relevant RED lines.

- [ ] **Step 4: Implement the async client**

Use `httpx.AsyncClient.request(..., follow_redirects=False)` through the injected client, the shared semaphore, and an injected sleeper. Append a `RequestRecord` only immediately before a real call. Force `api-version=7.1`; sanitize exceptions and records; reject 3xx before following. The method-route allowlist is data, not lexical grep.

- [ ] **Step 5: Implement atomic snapshot staging**

Write under a sibling temporary staging directory, calculate SHA-256 for every artifact, and only replace the current artifact set after a complete manifest is written. Manifest fields are `schema_version`, `complete`, `collected_at`, `requests`, and `artifacts` with relative path/hash. `abort()` removes only its own staging directory.

Update only the REST-method clause in `AGENTS.md` so it describes the approved semantic allowlist and forbids every mutating route/verb. Leave the legacy delta-class section for Task 6's atomic report transition.

- [ ] **Step 6: Verify GREEN and compile**

Run: `uv run pytest tests/test_azure_client.py tests/test_snapshot.py -q`

Run: `uv run python -m compileall -q src tests`

- [ ] **Step 7: Commit exact paths**

Commit: `refactor(azure): unify read boundary and atomic snapshots`

---

### Task 3: Make wiki collection truly cache-first

**Files:**
- Create: `src/doc_azure/wiki_collector.py`
- Modify: `scripts/01_fetch_wiki.py`
- Create: `tests/test_wiki_collector.py`
- Create: `tests/fixtures/audit/wiki-pages.json`
- Modify: `docs/decisions.md`

**Interfaces:**
- Produces: `WikiPage(page_id: int, slug: str, title: str, content: str)`.
- Produces: `collect_wiki_pages(root: Path, client: AzureReadClient | None, *, refresh: bool, now: Callable[[], datetime]) -> SnapshotManifest`.
- Consumes: `SnapshotWriter` and `AzureReadClient` from Task 2.

- [ ] **Step 1: Write failing zero-call cache test**

```python
def test_complete_wiki_cache_returns_before_client_is_required(tmp_path):
    seed_complete_wiki_snapshot(tmp_path)
    before = snapshot_bytes(tmp_path / "out" / "wiki")
    manifest = asyncio.run(
        collect_wiki_pages(tmp_path, None, refresh=False, now=fixed_now)
    )
    assert manifest.complete is True
    assert snapshot_bytes(tmp_path / "out" / "wiki") == before
```

Also test exact four page IDs, metadata preservation, no 404 stub, refresh atomicity, deterministic non-refresh bytes, and sanitized request records.

- [ ] **Step 2: Observe RED**

Run: `uv run pytest tests/test_wiki_collector.py -q`

Expected: import failure for `doc_azure.wiki_collector`. Record RED.

- [ ] **Step 3: Implement collection**

Resolve paths by page ID, request `includeContent=true`, require a non-empty string `content`, save `<slug>.md` and `<slug>.metadata.json`, and commit one complete wiki manifest. Check the complete manifest before loading PAT, constructing a client, or creating coroutines.

- [ ] **Step 4: Make the script a thin one-command entry point**

`main()` parses only `--refresh`, loads settings, runs exactly one top-level coroutine, prints saved/skipped relative paths and a request count, and returns non-zero on incomplete collection. It never prints URLs with query values or exception repr containing credentials.

- [ ] **Step 5: Verify GREEN and idempotence**

Run: `uv run pytest tests/test_wiki_collector.py -q`

Run the fixture entry point twice in a temporary root through the test; assert second-run request count zero and identical hashes.

- [x] **Step 6: Commit exact paths**

Commit: `fix(wiki): make page collection cache-first`

---

### Task 4: Collect the complete process definition without stale evidence

**Files:**
- Create: `src/doc_azure/process_collector.py`
- Modify: `scripts/02_fetch_process.py`
- Create: `tests/test_process_collector.py`
- Create: `tests/fixtures/audit/process-index.json`
- Create fixture files for fields, states, rules, layout, process behaviors, and WIT behavior associations under `tests/fixtures/audit/process/`
- Modify: `docs/api-contract.md`
- Modify: `docs/decisions.md`

**Interfaces:**
- Produces: `WorkItemType(name, reference_name, customization, is_disabled)`.
- Produces: `ProcessCollectionPlan.from_index(index_payload) -> tuple[ArtifactRequest, ...]`.
- Produces: `collect_process(root: Path, client: AzureReadClient | None, *, refresh: bool, now: Callable[[], datetime]) -> SnapshotManifest`.

- [ ] **Step 1: Write failing completeness tests**

```python
def test_plan_preserves_disabled_status_and_requests_all_artifact_families():
    plan = ProcessCollectionPlan.from_index(load_fixture("process-index.json"))
    epic = next(wit for wit in plan.work_item_types if wit.name == "Epic")
    assert epic.is_disabled is True
    assert {request.kind for request in plan.requests_for("Epic")} == {
        "fields", "states", "rules", "layout", "behaviors"
    }
```

Add tests for exact process selection, active/disabled WIT preservation, process behavior ranks, zero-call complete cache, missing-artifact-only fetch, 404 as explicit artifact error, refresh failure keeping the old snapshot, and one shared client/semaphore.

- [ ] **Step 2: Observe RED**

Run: `uv run pytest tests/test_process_collector.py -q`

Expected: import failure for `doc_azure.process_collector`. Record RED.

- [ ] **Step 3: Implement process discovery and the deterministic request plan**

Persist the full process response and full WIT index before deriving filenames. Use `referenceName` in routes and a manifest mapping reference name to filenames. Collect:

```text
GET /_apis/work/processes
GET /_apis/work/processes/{processId}
GET /_apis/work/processes/{processId}/workitemtypes
GET /_apis/work/processes/{processId}/behaviors
GET /_apis/work/processes/{processId}/workitemtypes/{ref}/fields
GET /_apis/work/processes/{processId}/workitemtypes/{ref}/states
GET /_apis/work/processes/{processId}/workitemtypes/{ref}/rules
GET /_apis/work/processes/{processId}/workitemtypes/{ref}/layout
GET /_apis/work/processes/{processId}/workitemtypesbehaviors/{ref}/behaviors
```

No artifact error may be silently converted to an empty response. A failed refresh aborts the staging snapshot.

- [ ] **Step 4: Replace the script orchestration**

Use one `asyncio.run`, one `httpx.AsyncClient`, one `AzureReadClient`, and one semaphore. On a complete cache hit, return before PAT/client creation. Print counts by artifact family and sanitized request count only.

- [ ] **Step 5: Verify GREEN**

Run: `uv run pytest tests/test_process_collector.py -q`

Run: `uv run python -m compileall -q src scripts tests`

- [x] **Step 6: Commit exact paths**

Commit: `fix(process): collect complete atomic evidence`

---

### Task 5: Replace heuristic deltas with an explicit claim catalog

**Files:**
- Create: `src/delta/catalog.py`
- Create: `src/delta/evaluator.py`
- Create: `config/wiki_claims.json`
- Create: `tests/test_delta_catalog.py`
- Create: `tests/test_delta_evaluator.py`
- Create: `tests/fixtures/audit/wiki_claims.json`
- Modify: `src/delta/__init__.py`
- Modify: `src/delta/evidence.py`
- Modify: `src/doc_azure/snapshot.py`
- Modify: `tests/test_snapshot.py`
- Modify: `docs/decisions.md`

**Interfaces:**
- Produces: `ClaimSpec` with `id`, `page_id`, `slug`, `finding`, `doc`, `check`, and `limit`.
- Produces: `load_catalog(path: Path) -> tuple[ClaimSpec, ...]`.
- Produces: `evaluate_claim(claim: ClaimSpec, evidence_root: Path) -> Finding`.
- Produces evaluator kinds: `equals`, `count_equals`, `active_wit_set`,
  `wit_presence`, `field_presence`, `field_required`, `state_presence`,
  `rule_count`, `layout_control`, `behavior_rank`, `limitation`, and
  `ambiguous`.

- [x] **Step 1: Write failing schema and evaluator tests**

```python
def test_field_presence_returns_exact_field_pointer(audit_fixture):
    claim = make_claim(kind="field_presence", field_id="Custom.Bloqueado")
    finding = evaluate_claim(claim, audit_fixture)
    assert finding.status is FindingStatus.CONFIRMADO
    assert finding.azure_evidence.selector == "/value/1/id"


def test_historical_claim_is_not_proven_by_current_field_presence(audit_fixture):
    claim = make_historical_claim(current_field_id="Custom.Natureza")
    finding = evaluate_claim(claim, audit_fixture)
    assert finding.status is FindingStatus.NAO_VERIFICAVEL_API_PROCESSO
```

Add tests that disabled WITs are not treated as active, exact wiki excerpt/hash is required, wrong WIT fails, rule/layout/behavior pointers target their proving elements, duplicate IDs fail, and unsupported check kinds fail closed.

- [x] **Step 2: Observe RED**

Run: `uv run pytest tests/test_delta_catalog.py tests/test_delta_evaluator.py -q`

Expected: missing catalog/evaluator modules. Record RED.

- [x] **Step 3: Implement schema validation and typed evaluators**

No evaluator searches arbitrary prose. Each receives explicit parameters and either returns the exact actual value/pointer or an explicit limitation. `active_wit_set` compares only `isDisabled=false`; system test WITs are reported only when the documentary claim asserts a complete inventory.

- [x] **Step 4: Curate the material catalog**

Catalog at least these page-specific families, using exact current source excerpts and evidence paths:

- page 35: process identity, documented WIT structure, behavior ranks/hierarchy limit, HU state count, cross-WIT state variation, board mapping limit, required blocked field count, field volume, transition timestamps, conditional rules, external hours job limit, adoption/roles/benefits limits;
- page 10: every explicit policy template section, WIT applicability, state/field requirements that process endpoints can prove, and governance/practice items that cannot be proven;
- page 9: state changes, Natureza/Priority/current-field corroboration versus historical chronology, co-executors 1/2/3 per correct WIT, relative order ambiguity, rules/layouts, and any external-script claims;
- page 37: all twelve documented business WIT state counts, field/requiredness counts, rule counts, behavior mappings/ranks, layouts, and automation limitations.

Do not include a row only to satisfy a non-empty gate. Every row must be material and source-backed.

- [x] **Step 5: Verify GREEN**

Run: `uv run pytest tests/test_delta_catalog.py tests/test_delta_evaluator.py -q`

- [ ] **Step 6: Commit exact paths**

Commit: `feat(delta): evaluate explicit wiki claims`

---

### Task 6: Render deterministic reports and build a truth-checking gate

**Files:**
- Modify: `AGENTS.md`
- Create: `src/delta/render.py`
- Modify: `src/delta/__init__.py`
- Modify: `scripts/03_build_delta.py`
- Delete: `scripts/04_publish_notion.py`
- Create: `scripts/04_prepare_notion.py`
- Modify: `verify.py`
- Delete: `tests/test_classify.py`
- Delete: `tests/test_render.py`
- Delete: `tests/test_evidence.py`
- Create: `tests/test_delta_render.py`
- Create: `tests/test_verify.py`
- Create: `tests/test_prepare_notion.py`
- Modify: `docs/delta-method.md`
- Modify: `docs/decisions.md`

**Interfaces:**
- Produces: `render_report(result: AuditResult) -> str`.
- Produces: `build_all_reports(root: Path, catalog_path: Path, output_dir: Path) -> tuple[Path, ...]`.
- Produces: `prepare_notion(root: Path) -> PublicationManifest`.
- Produces: `verify_fetched_notion(manifest: PublicationManifest, fetched_root: Path) -> None`.

- [x] **Step 1: Write failing renderer tests**

```python
def test_renderer_uses_exact_portuguese_statuses_and_separate_pages():
    reports = render_fixture_reports()
    assert set(reports) == {"leiame", "politicas", "changelog", "apendice"}
    assert "| CONFIRMADO |" in reports["leiame"]
    assert "DOC_ONLY" not in "".join(reports.values())
```

Test deterministic row order by catalog order, Markdown escaping, no empty confirmed values, non-confirmed impact/limit, and stable summary counts.

- [x] **Step 2: Write failing verifier tests**

Test that the gate rejects: a resolvable but wrong JSON pointer, a nearby rather than exact wiki line, evaluator/status mismatch, failed subprocess, report mutation, missing Notion parent/page/hash, stale fetched content, and a secret literal.

- [x] **Step 3: Observe RED**

Run: `uv run pytest tests/test_delta_render.py tests/test_verify.py tests/test_prepare_notion.py -q`

Expected: new modules/functions are missing. Record RED.

- [x] **Step 4: Implement offline build and rendering**

`03_build_delta.py` takes `--evidence-root`, `--catalog`, and `--output-dir`, defaults to project paths, performs no network, writes atomically, and returns non-zero on any claim error. A second identical run must not change bytes.

- [x] **Step 5: Replace the Notion stub with local preparation**

`04_prepare_notion.py` creates `out/notion/publication-manifest.json` and one deterministic Markdown body per slug. It never claims an external write. `--verify-fetched` validates connector-fetched snapshots against page ID, parent ID, URL, and SHA-256.

- [x] **Step 6: Make `verify.py` non-mutating and substantive**

Run builders in a temporary directory, check return codes, compare bytes against versioned reports, reload every claim, rerun every evaluator, and verify exact documentary/Azure values. Keep secret, layout, docs, script one-command, and no-prose-module checks. Replace lexical method detection with tests/imported allowlist assertions.

Verify `.gitignore` contains the complete requested categories: secrets/credentials, Python caches, virtual environments, builds/generated `out/`, editor/OS state, logs, local databases, and local agent/worktree state. It already satisfies the design unless a focused test proves a missing category.

- [x] **Step 7: Complete the atomic contract transition**

Replace the old English relation classes in `AGENTS.md` with the exact Portuguese statuses from Global Constraints. Keep the semantic read-only, secret, TDD, one-command, async, language, and Git rules. State that actual live operations are logged and absence requires complete endpoint evidence. Remove the three legacy delta tests and legacy exports only after the new builder/verifier tests are green.

- [x] **Step 8: Verify GREEN and full suite**

Run: `uv run pytest tests/test_delta_render.py tests/test_verify.py tests/test_prepare_notion.py -q`

Run: `uv run pytest -q`

- [ ] **Step 9: Commit exact paths**

Commit: `fix(audit): verify claims instead of pointer shape`

---

### Task 7: Refresh live evidence, finalize the catalog, and document the audit

**Files:**
- Modify: `config/wiki_claims.json`
- Modify: `deltas/leiame.md`
- Modify: `deltas/politicas.md`
- Modify: `deltas/changelog.md`
- Modify: `deltas/apendice.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/api-contract.md`
- Modify: `docs/delta-method.md`
- Modify: `docs/decisions.md`
- Modify: `docs/prior-work.md`
- Modify: `docs/notion-publication.md`
- Create: `docs/session-2026-08-24.md`

**Interfaces:**
- Consumes all code from Tasks 1-6.
- Produces the four final versioned reports and complete human/model handoff.

- [ ] **Step 1: Provide the ignored runtime inputs safely**

Link or copy the original repository's ignored `.env` into the worktree without printing it. Verify `.env` and `out/` remain ignored before live execution. Never stage either path.

- [ ] **Step 2: Run live refreshes through documented REST reads**

Run:

```text
uv run python scripts/01_fetch_wiki.py --refresh
uv run python scripts/02_fetch_process.py --refresh
```

Expected: four wiki pages, exact process, full WIT index, process behaviors, and all per-WIT artifact families saved with a complete manifest. Inspect the sanitized request log and prove no non-allowlisted operation ran.

- [ ] **Step 3: Reconcile catalog excerpts and evidence against the live snapshot**

Update source line/excerpt/hash and exact JSON pointer parameters only from observed files. Add material missing claims found during reconciliation; remove unsupported or editorial rows. For changelog history, preserve the current-state-versus-history distinction.

- [ ] **Step 4: Generate the four reports twice**

Run twice: `uv run python scripts/03_build_delta.py`

Expected: identical SHA-256 for all four reports; no network calls.

- [ ] **Step 5: Run the local Notion preparation**

Run: `uv run python scripts/04_prepare_notion.py`

Expected: four page bodies plus publication manifest, all ignored under `out/notion/`.

- [ ] **Step 6: Complete human-readable documentation**

Document what changed, why, authority rulings, exact Azure operations, evidence snapshot timestamp/hashes, rejected approaches, RED/GREEN commands, report summaries, limitations, and remaining uncertainty. README must show one-command setup, each script command, output locations, safety boundary, and Notion connector step.

- [ ] **Step 7: Verify before commit**

Run: `uv run pytest -q`

Run: `uv run python verify.py` (publication check may remain explicitly pending until Task 8; every other check must pass).

Run twice: `uv run --no-sync python scripts/setup.py`

Expected: both setup runs exit zero, print identical non-secret output, and do not modify versioned files.

Run: `git diff --check` and inspect `git status --short` to ensure no `out/`, `.env`, credential, token, or profile-analysis artifact is staged.

- [ ] **Step 8: Commit exact versioned paths**

Commit: `docs(delta): publish evidence-backed audit reports`

---

### Task 8: Adversarially review, update, and verify Notion, then close the audit

**Files:**
- Modify: `docs/notion-publication.md`
- Modify: `docs/session-2026-08-24.md`
- Modify: `docs/decisions.md`

**Interfaces:**
- Consumes: four prepared Notion bodies and publication manifest.
- Produces: two model-specific adversarial review receipts, reconciled reports,
  verified hub/four-page receipts, and final gate evidence.

- [ ] **Step 1: Read the Notion enhanced Markdown specification**

Fetch `notion://docs/enhanced-markdown-spec` through the Notion connector before any update.

- [ ] **Step 2: Run two adversarial reviews in Notion AI through the integrated browser**

Use only the browser integrated into this ChatGPT task; do not use the external
Notion desktop app. Create two separate Notion AI chats from the same sanitized
review packet: the four prepared delta bodies, methodology/status definitions,
and material limitations. Select exactly Kimi K3 in one chat and Opus 5 in the
other, with maximum effort for each. Ask both to find unsupported conclusions,
missing material comparisons, wrong evidence/status, historical claims inferred
from current state, and publication risks. Verify the selected model and effort
in the visible UI before sending. Do not silently substitute a model, effort,
browser surface, or connector; stop at login, MFA, CAPTCHA, missing model, or
unavailable effort. Do not transmit raw employee records, credentials, or
ignored evidence files.

- [ ] **Step 3: Reconcile both model reviews against raw evidence**

Record each chat receipt, verdict, and finding in ignored runtime evidence and
summarize it in `docs/session-2026-08-24.md`. Resolve every material finding by
checking the catalog and exact raw pointers; model agreement is not proof. If a
finding changes the catalog or reports, rerun Tasks 5–7 builders, tests,
verification, hashes, and Notion preparation before publication. Document
rejected model advice with evidence.

- [ ] **Step 4: Resolve the existing page hierarchy**

Fetch the existing Azure parent, audit hub, and four child pages from the IDs/URLs in `docs/notion-publication.md`. Verify all report pages share the same direct parent. Do not create duplicates.

- [ ] **Step 5: Update the four child pages**

Replace only each report page body with its prepared current Markdown. Keep titles and parent unchanged. Record returned page ID and URL.

- [ ] **Step 6: Fetch and verify all five pages**

Fetch hub plus four children after update. Save sanitized snapshots/receipts under ignored `out/notion/`; run:

`uv run python scripts/04_prepare_notion.py --verify-fetched`

Expected: page IDs, common parent, URLs, and all four content hashes match.

- [ ] **Step 7: Update publication/session docs and commit**

Record verified URLs, IDs, common parent, timestamps, hashes, and connector receipts without credentials.

Commit: `docs(notion): record verified delta publication`

- [ ] **Step 8: Final verification**

Run fresh:

```text
uv run pytest -q
uv run python verify.py
uv run python -m compileall -q src scripts tests
git diff --check
git status --short --branch
```

Expected: test suite passes, verifier prints its success marker and exits zero, compilation is silent, diff check is clean, and the branch worktree is clean.

- [ ] **Step 9: Independent whole-branch review**

Generate a review package from merge base `31078f9` to HEAD. The reviewer must inspect spec compliance, exact evidence truth, GET/optional-query boundary, secrets, reproducibility, Notion equivalence, documentation, and deferred ledger findings. Resolve every Critical/Important finding through one scoped fix wave and re-review.

- [ ] **Step 10: Finish without unauthorized integration**

Use `superpowers:finishing-a-development-branch`. Do not merge, push, or remove the worktree automatically. Report branch, commits, test/gate evidence, Notion URLs, original `main` status, and every recorded ruling with its cost if wrong.
