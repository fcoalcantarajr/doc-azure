# Notion evidence file reference

Use this reference only when publishing the four prepared reports. The normal
Azure audit does not require these files. The publication workflow is operated
through the connected Notion MCP and the ChatGPT-integrated browser; the Python
application prepares and verifies evidence but does not perform an external
Notion update.

The strict verifier rejects missing fields, extra fields, invented tool results,
stale timestamps, mismatched hashes, reused chat IDs, duplicate pages, and
semantic differences. Preserve exact raw tool results. Do not rewrite a raw
result to make it pass.

## Before any external update

1. Run the one-line preparation command in
   [Notion publication contract](notion-publication.md#local-preparation).
2. Open `out/notion/review/review-manifest.json` and record its
   `packet_sha256` and `prompt_sha256`. Do not calculate different hashes from
   copied text.
3. Inspect every prepared body under `out/notion/prepared/` for personal,
   secret, or destination-inappropriate content.
4. Complete both reviews and reconciliation below.
5. Run `uv run python scripts/04_prepare_notion.py --verify-publication`. It
   must fail before publication evidence exists. This confirms that the gate is
   fail-closed; it is not authorization to update pages.

## Required directory tree

Files marked `generated` come from `scripts/04_prepare_notion.py`. Files marked
`captured` must contain the exact external result. Files marked `recorded` are
side receipts whose values are copied from the captured evidence.

```text
out/notion/
├── publication-manifest.json                 generated
├── prepared/
│   ├── leiame.md                             generated
│   ├── politicas.md                          generated
│   ├── changelog.md                          generated
│   └── apendice.md                           generated
├── review/
│   ├── packet.csv                            generated
│   ├── prompt.txt                            generated
│   ├── review-manifest.json                  generated
│   ├── responses/
│   │   ├── kimi-k3.md                        captured
│   │   └── opus-5.md                         captured
│   ├── raw/
│   │   ├── kimi-k3.json                      captured
│   │   └── opus-5.json                       captured
│   ├── receipts/
│   │   ├── kimi-k3.json                      recorded
│   │   └── opus-5.json                       recorded
│   └── reconciliation.json                   recorded
├── raw/
│   ├── notion-update-<slug>.json             captured, four files
│   ├── notion-fetch-<slug>.json              captured, four files
│   ├── notion-fetch-parent.json              captured
│   ├── notion-fetch-hub.json                 captured
│   └── notion-search-<slug>-<kind>.json       captured, twelve files
└── fetched/
    ├── <slug>.md                             captured, four files
    ├── <slug>.json                           recorded, four files
    ├── hierarchy.json                        recorded
    └── duplicate-search.json                 recorded
```

`<slug>` is exactly `leiame`, `politicas`, `changelog`, or `apendice`.
`<kind>` is exactly `page_id`, `title`, or `marker`.

## Hash one file

Use the same command on macOS, Linux, and WSL. Replace `PATH` with one relative
file path from the tree above:

```sh
uv run python -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" PATH
```

Hash the bytes on disk after saving the file. Do not hash copied screen text.

## Capture each browser review

Use separate new chats. Before submission, visibly confirm the assigned model
and maximum effort. Send the same generated `packet.csv` and `prompt.txt` to
both chats. Record all timestamps with a timezone, for example
`2026-09-09T18:30:00-03:00`.

Save the complete model response, without UI chrome, as the matching Markdown
file under `review/responses/`. Save one raw browser-result envelope under
`review/raw/`. The raw file is a JSON object with exactly `isError` and
`content`. `isError` is `false`; `content` contains one text item whose `text`
is a JSON-encoded object with exactly these fields:

| Field | Required value |
| --- | --- |
| `surface` | `chatgpt-integrated-browser` |
| `chat_id`, `chat_url` | Identity of this distinct chat |
| `model` | `Kimi K3` or `Opus 5`, matching the receipt filename |
| `effort` | `maximum` |
| `packet_name` | `packet.csv` |
| `packet_sha256`, `prompt_sha256` | Values from `review-manifest.json` |
| `model_verified_at`, `effort_verified_at`, `sent_at`, `completed_at` | Timezone-aware timestamps in causal order |
| `response_markdown` | Exact content of the saved response file |

Each `review/receipts/<model>.json` has exactly these fields:

```text
schema_version, model, effort, surface, packet_sha256, prompt_sha256,
chat_id, chat_url, model_verified_at, effort_verified_at, sent_at,
completed_at, verdict, response_path, response_sha256,
browser_result_path, browser_result_sha256, findings
```

Use `schema_version: 1`; `effort: "maximum"`; and
`surface: "chatgpt-integrated-browser"`. `verdict` is exactly `PASS` or
`NEEDS_FIXES`. Each `findings` item has exactly `id`, `severity`, and `summary`,
all nonempty strings. Paths are repository-relative. The saved response and
raw-browser hashes must match their files.

If responses are byte-identical or a response's model self-description
conflicts with the model visible in the UI, preserve the anomaly and repeat
both reviews in new chats. Do not treat agreement as proof.

## Reconcile the reviews

Create `review/reconciliation.json` only after both reviews finish. It has
exactly these fields:

```text
schema_version, packet_sha256, review_response_hashes, reconciled_at,
outcome, report_semantic_hashes, decisions
```

Use `schema_version: 1`. Copy `report_semantic_hashes` from the generated review
manifest. `review_response_hashes` maps the exact keys `Kimi K3` and `Opus 5`
to the response hashes. `reconciled_at` must not precede either review.

Create one decision for every `(model, finding id)` pair and no others. Each
decision has exactly:

```text
model, finding_id, decision, rationale, changed_reports
```

`decision` is `accepted`, `rejected`, or `deferred`; `rationale` is a nonempty
evidence-based explanation; `changed_reports` is a list of affected report
slugs and may be empty. A material deferred finding blocks publication even if
the JSON schema itself passes.

## Update and fetch each fixed page

For each manifest entry, use the connected Notion MCP to replace the body of
that exact existing `page_id` with its matching prepared Markdown. Never create
a page. Save the exact successful tool result as
`raw/notion-update-<slug>.json`.

Fetch the same page after the update and save the exact tool result as
`raw/notion-fetch-<slug>.json`. Extract the complete text between the raw
result's `<content>` and `</content>` markers, without changing it, to
`fetched/<slug>.md`. The strict parser accepts the body with or without one
final newline.

Raw update and fetch files are exact MCP `CallToolResult` JSON envelopes:

```json
{
  "isError": false,
  "content": [
    {"type": "text", "text": "<exact JSON string returned by the connector>"}
  ]
}
```

The inner update result must identify the updated page. The inner fetch result
must be a Notion page result with title, URL, connector-as-of time, properties,
body, parent page, and last-edited time when the connector supplies it.

Each `fetched/<slug>.json` has exactly these fields:

```text
schema_version, slug, title, page_id, parent_page_id, url, marker,
updated_at, fetched_at, connector_as_of, last_edited_available,
last_edited_time, semantic_sha256, raw_fetch_path, raw_fetch_sha256,
update_receipt_path, update_receipt_sha256
```

Use `schema_version: 1`. Copy fixed identity and semantic values from
`publication-manifest.json`. `fetched_at` must not precede `updated_at`, and
`connector_as_of` must not precede `fetched_at`. Set
`last_edited_available` to `false` and `last_edited_time` to `null` only when
the raw connector result truly omits that field.

## Prove hierarchy

Fetch the fixed parent and the Azure audit hub after page updates. Save their
exact tool results as `raw/notion-fetch-parent.json` and
`raw/notion-fetch-hub.json`. Create `fetched/hierarchy.json` with exactly:

```text
schema_version, parent_page_id, parent_title, hub_page_id, fetched_at,
parent_fetch_path, parent_fetch_sha256, hub_fetch_path, hub_fetch_sha256,
pages
```

Use `schema_version: 1`. `pages` is an ordered four-item list matching the
publication manifest. Each item has exactly `page_id`, `title`,
`parent_page_id`, and `url`.

## Prove no duplicates

Run twelve parent-scoped Notion searches: page ID, exact title, and marker for
each of the four pages. Save every exact result as
`raw/notion-search-<slug>-<kind>.json`. A raw search uses the same
`CallToolResult` envelope and its inner object must have
`type: "workspace_search"` and a `results` list.

Create `fetched/duplicate-search.json` with exactly `schema_version` and
`searches`. Use `schema_version: 1`. The `searches` list has exactly twelve
items, each with:

```text
slug, kind, query, scope_parent_page_id, expected_page_id,
matched_page_ids, searched_at, raw_search_path, raw_search_sha256
```

For each item, `matched_page_ids` must contain only the one expected fixed page
ID. Zero matches or more than one match blocks publication.

## Final checks

Run both commands:

```sh
uv run python scripts/04_prepare_notion.py --verify-publication
uv run python verify.py --require-publication
```

Required markers are `NOTION_PUBLICATION_OK` and `GATE_OK`. If either command
fails, match its exact message in [Troubleshooting](troubleshooting.md), retain
all evidence, and do not claim that the current reports are published.
