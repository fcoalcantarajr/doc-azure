# Historical handoff snapshot

The original Session 1 inventory was a baseline gap analysis, not a live source
of truth. Its earlier `no`/`missing` values are superseded by the current
repository state summarized here.

The table below records the state observed on 2026-09-09. It is historical
evidence, not current operating guidance. Use `../README.md` for current docs.

## State recorded on 2026-09-09

| Area | Status recorded then | Handoff recorded then |
| --- | --- | --- |
| Safety and repository rules | Present | `AGENTS.md`, `.gitignore` |
| Azure settings and read boundary | Present and tested | `src/doc_azure/settings.py`, `src/doc_azure/azure_client.py`, `../reference/api-contract.md` |
| Immutable wiki/process collectors | Present and tested | `scripts/01_fetch_wiki.py`, `scripts/02_fetch_process.py`, `src/doc_azure/` |
| Explicit claim catalog | 222 source-backed claims | `config/wiki_claims.json` |
| Versioned coverage baselines | Reviewed documentary and process inventories | `config/document-coverage.json`, `config/process-coverage.json` |
| Canonical deterministic runtime | Refresh/offline audit with exit contract | `scripts/run_audit.py`, `docs/audit-runtime.md` |
| Delta methodology and decisions | Current | `../reference/delta-method.md`, `../decisions.md` |
| Offline report builder | Present and deterministic | `scripts/03_build_delta.py`, `src/delta/` |
| Versioned reports | Current | `deltas/leiame.md`, `deltas/politicas.md`, `deltas/changelog.md`, `deltas/apendice.md` |
| Local Notion preparation | Semantic bodies and repository-bound review packet present; ignored output only | `scripts/04_prepare_notion.py`, `docs/notion-publication.md`, `out/notion/` |
| Repository gate | Present; local gate passed in that environment | `verify.py` |
| Tests and fixtures | Present | `tests/`, `tests/fixtures/` |
| Current audit receipt | Present | `session-2026-09-08.md` |
| External Notion publication | Pending at that handoff | `../notion-publication.md` |

## Historical baseline

Session 1 notes remain in `sessions/session-1.md` as read-only historical
evidence. They record what was absent at that earlier point and must not be used
as a current inventory. Current implementation status comes from the files and
verification receipts named above.

## Resume point recorded then

The local handoff is complete only when the current receipt records deterministic
report hashes, fresh read-only collection, two identical non-secret setup runs
without versioned mutation, the full test result, and `GATE_OK`. External completion additionally requires
the independent Notion AI reviews, in-place connector updates to the four fixed
pages, connector read-back, and `uv run python verify.py --require-publication`.
