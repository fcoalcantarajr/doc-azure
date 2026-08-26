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

The 2026-08-26 handoff uses the hashes below. Source hashes bind the versioned
reports; body hashes bind the enhanced-Markdown payload; semantic hashes bind
the title, marker, methodology, status definitions, provenance, summary, and
every ordered finding field. They prove local identity only.

| Slug | Source SHA-256 | Prepared body SHA-256 | Semantic SHA-256 |
| --- | --- | --- | --- |
| `leiame` | `029f0692fe361e86b78ca2fa64f4287a8f657d242defb328f80cfa0bd281f0c0` | `3ed3730dabc383357be1ab87eec19ceb2df4b36a25dcc68debd2c86eb65a3480` | `91d53b7f4c159d5f356a44b2ff8f2822237765264934c60f1031ccedbe64a4ee` |
| `politicas` | `408132c52da0e2cca534d00fc2055d96ac456f83c0863b15ab419e5037aa56f7` | `9377ebbcb6d2f51e495c4d2d4842e2a13c0b25ee10bfe7c9f6d5f8e37c5d16f4` | `05a4e9d316ea7d45a67f0d6886519b6e0296da82f1c65265d1a54af81ba3c0b3` |
| `changelog` | `cb26377a16a014c8480bf5253158002b201688c833cf8e896d0d816a99bb2387` | `5b8dad454344f38fa1114dd75ce530909c4b00d1259b78fa2f5ccefbc21395c5` | `216880addc240de022ecd5c5262b33d7030a8ad0f6c93912dc58212c73337db4` |
| `apendice` | `b52fbf654da2a2c4b721153354ea02c5e3195210644adfc5205066babfaeab8d` | `01b41c9296c10aabac0618c8bc530011fb7709316cb0c176ac17e1554f43dfb5` | `d1f21cac9ba5f9ced527139475048d714d282ef4632f008bdaddb4754c50cfa0` |

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
