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
contains a stable ID, page and slug, material finding, one or more exact source
fragments from the same page/hash, documented value, one typed evaluator, and
an explicit limit. Compound claims preserve every exact source line required to
prove both property and scope. The strict loader rejects unknown fields,
unsupported evaluator kinds, duplicate IDs, inconsistent page/slug/path
identities, mixed fragment hashes, and malformed evaluator parameters.

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
evaluators cover exact JSON values and counts; filtered active WIT sets and
required-field counts; WIT/state/field presence; exact state sequences and set
equality; field/state properties; documented-versus-implemented field
alternatives with exact identity and label pointers; transition-field coverage; rule counts,
presence, and actions; layout controls and local order; unique technically
custom field minima; exact technical context; explicit API limitations; and
genuine ambiguity.

Before evaluation, every documentary source hash, line number, and complete
line text must match. Process values are read only from manifested artifacts.
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
atomically replaces each destination. Every report records both collection
times, generation IDs, manifest hashes, and the exact process identity. The
builder re-reads provenance after evaluation and aborts if either selected
generation changed. The same inputs produce identical UTF-8 bytes. Catalog,
evidence, evaluator, and rendering failures stop before any replacement. If a
later file replacement fails, verified backups restore every file already
replaced. This rollback protects ordinary I/O failures; it does not claim a
single filesystem transaction across four paths if the process or machine
terminates between replacements.

Custom local paths are explicit:

```text
uv run python scripts/03_build_delta.py \
  --evidence-root /path/to/repository \
  --catalog /path/to/wiki_claims.json \
  --output-dir /path/to/reports
```

## Notion handoff

`scripts/04_prepare_notion.py` only prepares or verifies local artifacts. It
parses the four versioned reports into a canonical semantic model, renders
Notion enhanced-Markdown tables, binds the output to the fixed existing page
identities, and records both byte and semantic hashes. With `--repository-url`,
it also creates a deterministic, secret-screened CSV and identical adversarial
review prompt bound to the private GitHub repository. It never creates or
updates a Notion page.

The legacy local identity check remains available for diagnosis:

```text
uv run python scripts/04_prepare_notion.py \
  --verify-fetched out/notion/fetched
```

Final publication uses `--verify-publication`. It additionally requires two
independent, packet-bound Notion AI review receipts, full reconciliation, raw
update/fetch receipts, hierarchy proof, twelve duplicate searches, fresh
timestamps, and exact semantic equivalence of every ordered finding.

## Repository gate

`uv run python verify.py` rebuilds reports into a temporary directory and
compares exact bytes without changing versioned outputs. It also imports and
exercises the Azure method/route allowlist, runs the test suite and script entry
points, checks the full ignore policy, scans sensitive `.env` values without
printing them, validates the current status contract, rejects prose-only Python
modules, and validates any local Notion manifest. With
`--require-publication`, it delegates to the complete external-evidence gate.

The final post-publication gate is:

```text
uv run python verify.py --require-publication
```

Success is the single marker `GATE_OK`.
