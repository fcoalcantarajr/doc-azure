# Completion audit — 2026-09-09

This is an evidence matrix for the full objective. It intentionally distinguishes
local proof from the remaining external Notion gate.

| Objective requirement | Current evidence | Status |
| --- | --- | --- |
| Four Wikis collected | Fresh `--refresh`: four GETs; Wiki generation `bb212f30efad4e0ea3f014416cf223c2` | `PROVEN` |
| Processo-Agil collected | Fresh `--refresh`: 109 GETs, 110 artifacts; process generation `d41998ae06ed42389777c400c61c8598` | `PROVEN` |
| Four deltas calculated | 222 findings and four rebuilt reports | `PROVEN` |
| Four canonical Notion pages updated | Fetches still show older 2026-08-21 bodies | `PENDING_EXTERNAL` |
| Single repeatable application | `scripts/run_audit.py --refresh` / `--offline` | `PROVEN` |
| Runtime without AI | Runtime imports Azure/httpx, catalog/evaluator only; offline no-network regression | `PROVEN` |
| Explicit versioned catalog | `config/wiki_claims.json`, 222 stable claims | `PROVEN` |
| Unknown documentation changes visible | `UNMAPPED_DOC_CHANGE`, exact spans, fail-closed tests | `PROVEN` |
| Coverage gaps fail closed | Documentary and 40,559-node process baselines; code 2 and drift tests | `PROVEN` |
| Structured and human outputs | `out/audit/run.json`, `global.md`, four page reports | `PROVEN` |
| Full test suite | `374 passed` | `PROVEN` |
| Repository gate | `uv run python verify.py`: `GATE_OK` | `PROVEN` |
| Fresh real end-to-end run | `--refresh`: code 1 `DELTAS`, zero gaps, 222 findings | `PROVEN` |
| Idempotent setup | Two `scripts/setup.py` runs; unchanged Git state | `PROVEN` |
| No tracked secrets | Bounded reachable-blob history scan; no `.env`, known values or token/key patterns | `PROVEN` (bounded scan) |
| Private GitHub branch at revalidation | `PRIVATE`; normal non-force branch read-back succeeded | `PROVEN` |
| Kimi K3 review | No exact model/browser tool available in this session | `PENDING_EXTERNAL` |
| Opus 5 review | No exact model/browser tool available in this session | `PENDING_EXTERNAL` |
| Valid findings reconciled | Cannot reconcile reviews that have not run | `PENDING_EXTERNAL` |
| Clone/configure/run handoff | README, architecture, baselines and one-command script are versioned | `PROVEN` locally; publication gate pending |

The authenticated Notion connector search found no workspace agents named Kimi K3
or Opus 5. The exposed tool inventory lacks browser control/Computer Use. The
required exact-model reviews therefore remain a real external dependency; this
audit does not substitute connector output or another model and does not update
the four Notion pages prematurely.

## Revalidation on 2026-09-09

- The code-regression revalidation was performed with a clean
  `fix/adversarial-delta-audit` worktree at implementation commit
  `96ca6f9ca8967ff6bfd092c58717f40b89384abe`; subsequent commits in this
  section are documentation-only.
- The local `origin` configuration was restored to the authorized private
  repository and a normal, non-force push reported `Everything up-to-date`.
  Read-back still reports the private repository, `main` at
  `d1764951eacb235326db1886117e67505abc67d6`, and the audit branch at the
  current commit above.
- Exact Notion-agent searches for `Kimi K3` and `Opus 5` returned no agents.
  Historical-session search is also unavailable because the connected Notion
  integration returned HTTP 403 `restricted_resource`: it lacks the
  `interact with agents` capability and requires reconnect/re-authorization.
- No Notion page was updated in this revalidation. Publication remains
  fail-closed until the exact integrated-browser reviews and their raw
  receipts exist.
- A fresh equivalent Azure collection changed only snapshot provenance
  (`collected_at`, generation IDs and manifest hashes), so the report verifier
  now canonicalizes those explicitly volatile fields while retaining byte-level
  comparison for all logical report content. The regression is covered by
  `test_verify_reports_ignores_run_specific_snapshot_provenance`.
- After that correction, `uv run python verify.py --require-publication` fails
  at the intended external gate (`cannot read Kimi K3 review receipt`), rather
  than falsely reporting report drift.

## Fresh hashes

- logical run: `3ea48dc27b83ba7ba1491f56538e893433f52eaf9df063affe099dbca0166369`
- documentary baseline: `2e0d956a8f74f3933779d297adfff1328267de1ccd8a04e555228b7edbf2990e`
- process baseline: `4fe95039f993a9473677b98e4a652bc4d0d79c1ad1a6658d6598bdfce9cd2418`
- review packet: `0bbf6aabebf57703b60ea619e36ade4ff8023cd14256cd7b8a3103cc32cd282f`
- review prompt: `9921af82e43b24bb5a01069d2c251e8dc813f90199b606bb49740fbe475a73a3`
