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

The 2026-09-08 handoff uses the hashes below. Source hashes bind the versioned
reports; body hashes bind the enhanced-Markdown payload; semantic hashes bind
the title, marker, methodology, status definitions, provenance, summary, and
every ordered finding field. They prove local identity only.

| Slug | Source SHA-256 | Prepared body SHA-256 | Semantic SHA-256 |
| --- | --- | --- | --- |
| `leiame` | `d3bf8ab6d35ae967c72bc46424e30031fc8ae67339271cd3df344ffb126f33fb` | `450597f22a1f3e4736931a284770f6fcdc1ac01badf650ee92376cf31742c70a` | `aac05ae06f232b70ff7eac69eeb1d5cd80432291578ea06ab76c374294157de9` |
| `politicas` | `1732f271039b56d072ee0b65019d2437df44519869152cb469840f9ea2fcb570` | `ca93bf9a8b174a4ca283e43daa877cf67c475eac6658617ea6253e4a6644b54b` | `ec5cbace77da6c3e7a615577e81f9537c8372a137553f6b9e010209c6b5ea16b` |
| `changelog` | `d3936680d5d2488095620d0f7e75374fe52dbc105eb1697677f09579f4206d02` | `bd62dec86a20862fb13906592692b86d57dc0d6536da44fcaaff7362e50b6a9d` | `a1dfbca9fd1d56dea616bf2f649610f92c8fa49e72a40ec4a51678032d77f694` |
| `apendice` | `9eed58805a7e66fd05c068220a21afd03cf6996c0945e96d605504b1278e9d3b` | `2c071d41d753f816b8e0e9ca1e77123d37d6ab0cd5527b405ed232bb23a85292` | `305adf732124deed523fecce547bdebf1101707ed7b8fc7f266ca49935205594` |

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
