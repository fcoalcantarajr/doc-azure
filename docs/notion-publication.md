# Notion publication contract

## Location and existing-page identities

All four reports remain children of the same existing hub page. Publication
must update these pages in place; creating replacements or duplicates is
forbidden.

Parent page ID: `2a1412e0-8c26-803b-a988-dc619a396e45`

| Slug | Existing title | Existing page ID | URL | Marker |
| --- | --- | --- | --- | --- |
| `leiame` | Delta — Leiame × Processo-Agil implementado | `3c3412e0-8c26-813c-ad9c-d57026cfd566` | https://app.notion.com/p/3c3412e08c26813cad9cd57026cfd566 | `DELTA-AUDIT-MARKER-leiame` |
| `politicas` | Delta — Políticas Explícitas × Processo-Agil implementado | `3c3412e0-8c26-813a-8312-dc52450adf39` | https://app.notion.com/p/3c3412e08c26813a8312dc52450adf39 | `DELTA-AUDIT-MARKER-politicas` |
| `changelog` | Delta — Changelog - Processo Ágil no Azure DevOps × Processo-Agil implementado | `3c3412e0-8c26-81b8-b9fd-cca04e04452b` | https://app.notion.com/p/3c3412e08c2681b8b9fdcca04e04452b | `DELTA-AUDIT-MARKER-changelog` |
| `apendice` | Delta — Apêndice Técnico — Processo Organização Única × Processo-Agil implementado | `3c3412e0-8c26-81dc-81c1-fbf0c7cac428` | https://app.notion.com/p/3c3412e08c2681dc81c1fbf0c7cac428 | `DELTA-AUDIT-MARKER-apendice` |

## Local preparation

Run the command below only after the four versioned reports pass the offline
build. It writes ignored enhanced-Markdown bodies, semantic hashes, a
deterministic 222-row CSV, and an identical review prompt below `out/notion`;
it performs no external operation and does not claim publication.

```text
uv run python scripts/04_prepare_notion.py \
  --repository-url https://github.com/fcoalcantarajr/doc-azure
```

The 2026-09-09 handoff uses the hashes below. Source hashes bind the versioned
reports; body hashes bind the enhanced-Markdown payload; semantic hashes bind
the title, marker, methodology, status definitions, provenance, summary, and
every ordered finding field. They prove local identity only.

| Slug | Source SHA-256 | Prepared body SHA-256 | Semantic SHA-256 |
| --- | --- | --- | --- |
| `leiame` | `6c31f5f4f9eafc7be4113b7f47cdfbc1bd7071beb6dfe4f16e9922af784fe9cd` | `a3c39fdf14630abfe19cb3a4f327a80f9dee3124f932d5c9847190f62f1c4b8b` | `65805cf7ceec02e130cd71a18392214a915230a91c8e3abb490f0239bf75e3e8` |
| `politicas` | `8153ddb60686e9dd0e11ef5153af734e1996d534e2e12d91340e2273676dc1e7` | `9bb955668612b94e0ecc60f12e86d7fc7652259c343213609521c3088c28e438` | `f5722959e969e703fc2f861d8eba7c61fbf67487f4eb29be75aaa7d23d1cc200` |
| `changelog` | `a6b6baa9bf333d34ab7a47b54652f61c16b8a5b4e2e331159ff33d6e663e0c2d` | `7e91fe550387e579ebfe57919a0bb4b941fafb42613ae107ec8b00e006b7e9af` | `02e60d1a5df8b0dcafb0ab0901829fd79879ff3b0cb0c4dc23cf263c357d5fa8` |
| `apendice` | `e5099008ab565ef6ef5e625fbc749391df34771b8685defeec61ee7946ac9bae` | `17851534d1efbaa4c5654f4884b24824603f66925da069c3c9c71fe960ea00d2` | `96b0326091548d2c6a47313a32c4b93aad84c0d33329161dca12dc75d332b17c` |

Current review packet SHA-256: `0bbf6aabebf57703b60ea619e36ade4ff8023cd14256cd7b8a3103cc32cd282f`.
Current review prompt SHA-256: `9921af82e43b24bb5a01069d2c251e8dc813f90199b606bb49740fbe475a73a3`.

## Mandatory adversarial review gate

Before any page update, review the prepared reports in two independent Notion
AI chats:

1. Kimi K3, maximum effort.
2. Opus 5, maximum effort.

The Notion AI interaction must use the browser integrated into ChatGPT. The
external Notion desktop app is outside the authorized workflow. Each reviewer
receives the same reports, claim catalog, methodology, and material evidence
excerpts. Reviews remain independent until both verdicts are captured. Any
material conflict is reconciled against raw snapshot evidence, not by majority
vote. If the exact model, maximum-effort setting, signed-in session, or required
UI is unavailable, publication fails closed.

For each chat, preserve a sanitized response file and JSON receipt containing
the exact model, maximum effort, integrated-browser surface, distinct chat ID,
packet/prompt hashes, timestamps, verdict, structured findings, and response
hash. `out/notion/review/reconciliation.json` must bind both responses and
record a decision for every finding. A PASS is process evidence, not proof that
the source claims are true.

## External capability receipt — 2026-09-09

The required gate is intentionally still closed. Exact searches for `Kimi K3`
and `Opus 5` returned no published agents. Searching existing Notion agent
sessions returned HTTP 403 `restricted_resource` with the message that this
connection lacks the `interact with agents` capability and must be disconnected
and reconnected/re-authorized. The current Codex tool inventory also has no
interactive browser/Computer Use surface; `open_in_codex` can display a tab but
cannot operate the Notion AI UI.

This is not permission to substitute another model, a connector session, the
Notion desktop app, or a different browser. To resume, reconnect the Notion
integration with agent interaction enabled and make the ChatGPT-integrated
browser available. Then re-run the exact searches, create two independent
maximum-effort reviews, preserve their receipts, and only after reconciliation
continue to the fixed-page updates below. No Notion page was modified while
this prerequisite was missing.

On the resumed attempt, the user authorized the browser plugin and
`open_in_codex` queued the canonical page in the integrated panel, but the
session still exposed no browser interaction tool (typing, clicking, or form
submission). Therefore no review prompt was sent and no Notion content changed.
The plugin-management read-back is more specific: app `browser` is
`not_installed`, and `browser@openai-bundled` resolves as `plugin_not_found` for
this user. Authorization alone therefore did not make the requested plugin
available to the session.

## Update and proof

After the review gate passes, use the Notion connector to update the four fixed
page IDs in place. Fetch the parent, audit hub, all four pages, and three scoped
duplicate searches per page (ID, exact title, and marker). Save sanitized raw
connector results, receipts, and complete fetched bodies below ignored
`out/notion`.

- `<slug>.json`: fixed identities, times, semantic hash, and hashes/paths of the
  raw update and fetch receipts.
- `<slug>.md`: complete connector-fetched enhanced-Markdown body.
- `hierarchy.json`: common-parent/hub proof backed by raw fetches.
- `duplicate-search.json`: exactly twelve scoped searches backed by raw results.

Run:

```text
uv run python scripts/04_prepare_notion.py --verify-publication
uv run python verify.py --require-publication
```

The strict gate requires review reconciliation, exact page identities and
titles, common parent, no duplicates, fresh update/read-back order, raw receipt
hashes, and semantic equivalence of every ordered finding. Only its successful
read-back checks justify a current “published” status.
