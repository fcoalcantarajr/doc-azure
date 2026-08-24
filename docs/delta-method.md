# Evidence-backed delta method

## Purpose

The audit compares explicit claims in four fixed Azure DevOps wiki pages with
the current inherited-process representation of `Processo-Agil`. It does not
infer claims from keywords, manufacture rows to satisfy a gate, or treat the
current process API as historical evidence.

## Fixed documentary scope

| Page ID | Slug | Source |
| ---: | --- | --- |
| 35 | `leiame` | Leia-me Processo da Organização Única |
| 10 | `politicas` | Template de políticas explícitas |
| 9 | `changelog` | Changelog |
| 37 | `apendice` | Apêndice Técnico Processo Organização Única |

`config/wiki_claims.json` is the versioned comparison contract. Every entry
contains a stable ID, page and slug, material finding, exact source path, exact
line and excerpt, full source SHA-256, documented value, one typed evaluator,
and an explicit limit. The strict loader rejects unknown fields, unsupported
evaluator kinds, duplicate IDs, inconsistent page/slug/path identities, and
malformed evaluator parameters.

## Evidence snapshots

`scripts/01_fetch_wiki.py` and `scripts/02_fetch_process.py` publish immutable
snapshot generations below `out/wiki` and `out/process`. `CURRENT` selects the
complete generation. Its manifest records a UTC collection time, sanitized
method/path receipts for every real HTTP attempt, the exact artifact set, and a
SHA-256 for every artifact. Readers reject incomplete manifests, stale hashes,
unsafe paths, symlinks, and partial generations.

Azure DevOps remains semantically read-only. The imported allowlist permits
GET only on the required wiki, inherited-process, and work-item query routes.
POST is permitted only for the exact query-only WIQL and work-items-batch
routes. The process collector itself uses the inherited-process GET routes.
Creation, update, deletion, redirects, absolute URLs, and method overrides are
rejected before transport.

## Typed evaluation

Each claim declares one evaluator instead of a prose comparison. Supported
evaluators cover exact JSON values, counts, active work-item-type sets,
work-item-type/state/field presence, field requiredness, rule counts, layout
controls, behavior ranks, explicit API limitations, and genuine ambiguity.

Before evaluation, the documentary source hash, line number, and complete line
text must all match. Process values are read only from manifested artifacts.
JSON pointers use RFC 6901 and resolve to the exact compared value. Presence
and numeric checks are type-strict, so Boolean values cannot silently equal
integers. The artifact map is schema-checked and its process name and ID must
match the mapped `process.json` identity.

Every finding receives exactly one of these epistemic statuses:

| Status | Meaning | Azure pointer |
| --- | --- | --- |
| `CONFIRMADO` | The documented and current implemented values agree exactly. | Required |
| `DIVERGENTE` | Both values are comparable and differ. | Required |
| `NAO_VERIFICAVEL_API_PROCESSO` | The process API does not represent the claimed dimension. | Not asserted |
| `AMBIGUO` | The available evidence permits multiple material readings. | Included only when it supports the ambiguity |

The last two statuses are not synonyms for absence. Historical chronology,
runtime scripts, team practice, governance, and operational compliance cannot
be inferred from a current process-definition response. Conversely, an
absence claim is accepted only when the relevant endpoint family was collected
completely and the exact returned collection proves the absence.

## Deterministic report build

Run:

```text
uv run python scripts/03_build_delta.py
```

The builder performs no network operation. It loads every catalog claim,
revalidates both snapshot families, evaluates claims in catalog order, renders
one Brazilian-Portuguese report per fixed slug, stages all four files, and
atomically replaces each destination. The same inputs produce identical UTF-8
bytes. Catalog, evidence, evaluator, and rendering failures stop before any
replacement. If a later file replacement fails, verified backups restore every
file already replaced. This rollback protects ordinary I/O failures; it does
not claim a single filesystem transaction across four paths if the process or
machine terminates between replacements.

Custom local paths are explicit:

```text
uv run python scripts/03_build_delta.py \
  --evidence-root /path/to/repository \
  --catalog /path/to/wiki_claims.json \
  --output-dir /path/to/reports
```

## Notion handoff

`scripts/04_prepare_notion.py` only prepares local artifacts. It reads the four
versioned reports, requires each fixed publication marker, binds it to the
pre-existing parent/page IDs and URLs recorded in `docs/notion-publication.md`,
writes exact bodies below ignored `out/notion/prepared`, and records body hashes
in `out/notion/publication-manifest.json`. It never creates or updates a Notion
page.

After connector updates and connector read-back, pairs of `<slug>.json` and
`<slug>.md` below `out/notion/fetched` are verified with:

```text
uv run python scripts/04_prepare_notion.py \
  --verify-fetched out/notion/fetched
```

The verifier rejects a wrong or missing slug, page ID, parent ID, URL, marker,
or body hash.

## Repository gate

`uv run python verify.py` rebuilds reports into a temporary directory and
compares exact bytes without changing versioned outputs. It also imports and
exercises the Azure method/route allowlist, runs the test suite and script entry
points, checks the full ignore policy, scans sensitive `.env` values without
printing them, validates the current status contract, rejects prose-only Python
modules, and validates any local Notion manifest or fetched receipts.

The final post-publication gate is:

```text
uv run python verify.py --require-publication
```

Success is the single marker `GATE_OK`.
