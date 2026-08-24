# Notion publication contract

## Location and existing-page identities

All four reports remain children of the same existing hub page. Publication
must update these pages in place; creating replacements or duplicates is
forbidden.

Parent page ID: `2a1412e0-8c26-803b-a988-dc619a396e45`

| Slug | Existing title | Existing page ID | URL | Marker |
| --- | --- | --- | --- | --- |
| `leiame` | Leiame × Processo-Agil implementado | `3c3412e0-8c26-813c-ad9c-d57026cfd566` | https://app.notion.com/p/3c3412e08c26813cad9cd57026cfd566 | `DELTA-AUDIT-MARKER-leiame` |
| `politicas` | Políticas Explícitas × Processo-Agil implementado | `3c3412e0-8c26-813a-8312-dc52450adf39` | https://app.notion.com/p/3c3412e08c26813a8312dc52450adf39 | `DELTA-AUDIT-MARKER-politicas` |
| `changelog` | Changelog - Processo Ágil no Azure DevOps × Processo-Agil implementado | `3c3412e0-8c26-81b8-b9fd-cca04e04452b` | https://app.notion.com/p/3c3412e08c2681b8b9fdcca04e04452b | `DELTA-AUDIT-MARKER-changelog` |
| `apendice` | Apêndice Técnico — Processo Organização Única × Processo-Agil implementado | `3c3412e0-8c26-81dc-81c1-fbf0c7cac428` | https://app.notion.com/p/3c3412e08c2681dc81c1fbf0c7cac428 | `DELTA-AUDIT-MARKER-apendice` |

## Local preparation

Run `uv run python scripts/04_prepare_notion.py` only after the four versioned
reports pass the offline build. The script writes ignored prepared bodies and a
manifest below `out/notion`; it performs no external operation and does not
claim publication.

The 2026-08-24 local handoff is prepared from the verified report hashes below.
These hashes prove local identity only; they are not external publication
receipts.

| Slug | Prepared/report SHA-256 |
| --- | --- |
| `leiame` | `0ed68ff1d706d1a46a9b331f622f0fae6cfbdab1cde5da6b5287e398f71969db` |
| `politicas` | `76600376c81fe8cb0c64e804e8a5d1d374d973289e1f40b9cca442f751f13157` |
| `changelog` | `497b87a21aac19df4c77861aa43602c4d6768564cf65bdcf265c223cefcf279d` |
| `apendice` | `ffc1916547413f77e6559298a33231f6ccf01498bab3125427dc482cc619dc17` |

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

## Update and proof

After the review gate passes, use the Notion connector to update the four fixed
page IDs in place. Fetch every page back through the connector and save a
sanitized local receipt plus Markdown body under `out/notion/fetched`:

- `<slug>.json`: slug, fixed page ID, parent ID, canonical URL, and marker.
- `<slug>.md`: complete fetched body.

Run:

```text
uv run python scripts/04_prepare_notion.py \
  --verify-fetched out/notion/fetched
uv run python verify.py --require-publication
```

Only these successful read-back checks justify a current “published” status.
Earlier timestamps or markers are historical context, not evidence that this
session's reports were updated.
