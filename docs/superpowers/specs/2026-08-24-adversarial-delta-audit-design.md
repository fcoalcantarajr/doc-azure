# Adversarial Delta Audit Correction Design

## Purpose

Correct the existing Wiki-versus-`Processo-Agil` audit so that every published
finding is supported by the exact documentary claim and the exact current Azure
DevOps value. Preserve the user's uncommitted checkout, work only in an isolated
branch, regenerate the four Portuguese delta pages, and update their existing
Notion pages only after local verification succeeds.

## Context and observed failures

The current local expansion is not safe to publish even though its unit suite is
green. The adversarial baseline produced this evidence:

- `uv run pytest -q`: 51 tests plus 17 subtests passed in the user's checkout.
- `uv run python verify.py`: failed C5 because eight documentary pointers do not
  substantiate their claims, and failed C13 because Notion still contains the
  previously published, smaller reports.
- Three independent read-only reviews rejected the expanded deltas.

The material defects are:

1. Static lists classify inherited or disabled WITs as implemented
   `AZURE_ONLY` items without preserving `isDisabled` evidence.
2. State counts are hardcoded and linked to nearby WIT text instead of an exact
   numeric statement in the relevant section.
3. Generic JSON pointers such as `/value/0/id` resolve but do not prove fields
   such as `Custom.Bloqueado`, `Natureza`, or `Priority`.
4. Rules, layouts, and behaviors are declared absent or non-verifiable without
   collecting their documented GET endpoints.
5. Current state is used to imply historical changelog chronology.
6. Cache checks happen after requests are scheduled, so a nominal cache hit can
   still call Azure.
7. The verifier mutates deliverables during determinism checks and validates
   pointer shape more strongly than claim truth.
8. The Notion publication script is a success-returning stub, while fetched
   Notion snapshots prove only the older report content.
9. `docs/profile-analysis.md` and related ignored profile output are unrelated
   to the audit and must not enter the correction branch.

## Authority and REST safety ruling

The user's approved clarification governs the transport boundary: HTTP method is
not the definition of a read. The client may retain exactly two documented POST
query operations—WIQL execution and work-items-batch retrieval—because they read
data and do not create Azure resources. All creation POST routes, PUT, PATCH,
DELETE, and method override remain forbidden.

This audit is expected to need only GET endpoints. The optional query POSTs stay
allowlisted at the reusable client boundary but will not be called unless a
material claim genuinely requires work-item evidence. Every executed Azure
operation must be recorded by method and sanitized route in the session log.

The repository's literal GET-only rule and its lexical gate are therefore part
of the defect: they must be replaced by a semantic method-route allowlist, not by
removing the already reviewed safe-query capability.

## Selected approach: explicit evidence-first claim catalog

Use a curated, versioned claim catalog plus small deterministic evaluators. Do
not infer audit claims from keyword proximity, generic phrases, or WIT-wide
substring searches. Curation is appropriate because there are four fixed source
pages and materially different claim types; the catalog makes judgment visible
and reviewable while code keeps evaluation reproducible.

Two alternatives were rejected:

- **Patch the existing heuristics.** Faster initially, but another nearby word
  can silently turn into evidence. It cannot satisfy the evidence rule.
- **Write four reports manually.** It can be accurate once, but it does not meet
  the reproducibility requirement and cannot detect source or process drift.

## Result model

Each report row has these fields:

| Field | Meaning |
|---|---|
| `id` | Stable page-local claim identifier. |
| `finding` | One comparable claim in Brazilian Portuguese. |
| `status` | One of the four values below. |
| `documented` | What the page actually states, or `n/a`. |
| `implemented` | What current Azure evidence shows, or `n/a`. |
| `doc_evidence` | Exact wiki line pointer plus stored excerpt identity. |
| `azure_evidence` | Exact JSON path to the value that proves the result. |
| `impact_or_limit` | Descriptive consequence or verification limit, not an unsupported recommendation. |

Statuses are exactly:

- `CONFIRMADO`: the documentary claim and current Azure value agree.
- `DIVERGENTE`: comparable documentary and current values disagree, including
  an active Azure configuration materially omitted by the page.
- `NAO_VERIFICAVEL_API_PROCESSO`: the claim concerns history, actual practice,
  board/team configuration, external jobs, adoption, or another fact that the
  collected process-definition API cannot prove.
- `AMBIGUO`: available evidence permits more than one material interpretation,
  such as relative layout order across incomparable containers.

Absence may be called a divergence only when the collected endpoint is complete
for that property. Failure to collect a relevant endpoint is not proof of
absence.

## Raw evidence and collection

Raw responses are saved before interpretation under ignored `out/` paths:

- `out/wiki/<slug>.md` and page metadata;
- `out/process/process.json`;
- `out/process/workitemtypes.json`, preserving `name`, `referenceName`,
  `customization`, and `isDisabled`;
- process behaviors and ranks;
- per-WIT fields, states, rules, layout, and behavior associations;
- a snapshot manifest containing sanitized method-route entries, response
  hashes, fetch timestamp, and completeness status.

Collection uses Python 3.11+, `uv`, one `asyncio.run`, one reused
`httpx.AsyncClient`, and a shared semaphore. Only retry 408, 429, 500, 502,
503, and 504; honor `Retry-After`; never retry 401 or 403.

Without `--refresh`, an existing complete manifest means zero network calls and
byte-identical output. If the manifest is incomplete, request only missing
artifacts based on the cached WIT inventory. With `--refresh`, write a complete
snapshot to a staging directory and atomically replace the current snapshot only
after every required response succeeds. A failed refresh must never leave stale
files presented as current.

## Claim catalog and evaluation

The catalog records, for each claim:

- page ID and slug;
- stable claim ID and source excerpt;
- exact line anchor plus source-content hash;
- evaluator kind and typed parameters;
- expected documentary value;
- exact Azure artifact family;
- explicit limitation when the process API cannot answer the claim.

Evaluator kinds include process identity, active WIT inventory, state count,
field presence/requiredness, rule count or rule predicate, layout control
presence/order, behavior mapping/rank, and manual API limitation. Evaluators
return typed actual values and exact evidence pointers. A field evaluator must
point to the array element whose `id` is the claimed field; it may not point to a
generic first element.

Changelog rows compare the documented historical statement with current state
only when clearly labeled as current corroboration. Current presence never proves
the date or sequence of a past change. Historical chronology that lacks a
versioned Azure snapshot is `NAO_VERIFICAVEL_API_PROCESSO`.

## Rendering and verification

Render exactly four deterministic Markdown files:

- `deltas/leiame.md`;
- `deltas/politicas.md`;
- `deltas/changelog.md`;
- `deltas/apendice.md`.

The verifier must:

1. run tests and fail on non-zero subprocess results;
2. evaluate in a temporary directory without modifying versioned reports;
3. verify the stored wiki excerpt and source hash;
4. dereference the exact Azure JSON path;
5. rerun the evaluator predicate and compare its value/status to the row;
6. confirm non-confirmed rows contain a descriptive impact or limit;
7. scan versioned and generated text for secrets;
8. compare report hashes to prepared and fetched Notion artifacts;
9. fail if Notion page ID, URL, parent, or content hash is absent or mismatched.

Tests use versioned minimal fixtures, named fake transports, and temporary
directories. They must not depend on the user's ignored `out/` cache. Each bug
fix records a real RED command and relevant failure before production code.

## Notion publication

Update the existing audit hub and its four existing child pages rather than
creating duplicates. The authenticated Notion connector performs the external
write. Local Python prepares deterministic page bodies and hashes; it must not
pretend to publish when no Notion API credential is available.

The local workflow produces a publication manifest with slug, page ID, parent
ID, URL, local content hash, and timestamp. After connector updates, fetch all
five pages and archive sanitized content snapshots/receipts under ignored
`out/notion/`. Verification compares the fetched page bodies to the current
local reports.

## Git and workspace handling

- Work only in `/private/tmp/doc-azure-adversarial-fix` on
  `fix/adversarial-delta-audit`.
- Leave the user's modified `main` checkout untouched.
- Import only relevant local changes for comparison; do not import or delete
  profile-analysis artifacts.
- Stage explicit paths only, create atomic Conventional Commits, never rebase,
  amend, force-push, or bypass hooks.
- Do not push, merge, or remove a worktree without separate authority.

## Success criteria

The correction is complete only when:

1. focused tests and the full suite pass with pristine output;
2. the verifier exits zero without mutating tracked files;
3. live raw evidence is complete and every Azure operation is semantically read-only;
4. each report row is supported by an exact source excerpt and evaluator-backed
   Azure value or an explicit API limitation;
5. the four local reports and four fetched Notion child pages are content-equivalent;
6. the Notion hub/parent relationships and receipts are verified;
7. no secret appears in tracked/generated deliverables;
8. documentation records work performed, reasons, decisions, rejected
   alternatives, commands, RED/GREEN evidence, and remaining uncertainty;
9. the user's original `main` working tree changes remain untouched.
