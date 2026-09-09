# doc-azure

Offline-first audit tooling for comparing four fixed Azure DevOps wiki pages
with the inherited `Processo-Agil` process configuration. Azure collection is
semantically read-only; generated evidence remains ignored under `out/`.

## Setup

Python 3.11+ and `uv` are required. The project has one runtime dependency,
`httpx>=0.25.0`; the default development group adds `pytest>=8.0.0`.

```text
uv sync
uv run --no-sync python scripts/setup.py
```

The setup command is safe to repeat. It validates local inputs without printing
the PAT. Keep `AZDO_PAT` only in the ignored `.env` file.

## Workflow

```text
# Canonical complete run (read-only Azure collection plus all coverage gates).
uv run python scripts/run_audit.py --refresh

# Replay the current generations without network access.
uv run python scripts/run_audit.py --offline

# Networked Azure DevOps reads; both collectors fail closed outside the allowlist.
uv run python scripts/01_fetch_wiki.py --refresh
uv run python scripts/02_fetch_process.py --refresh

# Offline catalog evaluation and deterministic reports.
uv run python scripts/03_build_delta.py

# Offline Notion-body and adversarial-review preparation; this does not publish.
uv run python scripts/04_prepare_notion.py \
  --repository-url https://github.com/fcoalcantarajr/doc-azure

# Non-mutating local gate.
uv run python verify.py
```

Outputs:

- immutable raw snapshots and manifests: ignored `out/wiki` and `out/process`;
- versioned reports: `deltas/leiame.md`, `deltas/politicas.md`,
  `deltas/changelog.md`, and `deltas/apendice.md`;
- ignored semantic Notion bodies, review packet, receipts, and publication
  read-back evidence: `out/notion`.

The current audit evaluates 222 explicit claims backed by exact documentary
fragments. Reports identify the wiki/process generations, collection times,
manifest hashes, process name, and process UUID used for evaluation.

## Safety boundary

Azure DevOps collection uses an explicit allowlist of read-only routes. It is
GET-only for Wiki/process reads; the allowlist permits only the two documented
query-only POST routes when a collector needs them. No collector creates,
updates, or deletes process/wiki data. Raw evidence may contain employee data
and must not be committed. Never stage `.env` or `out/`.

Notion publication is a separate gated step. Two independent reviews must use
Kimi K3 and Opus 5 at maximum effort in the ChatGPT-integrated browser, with
the same repository-bound CSV packet. After reconciliation, update only the
four fixed pages listed in `docs/notion-publication.md`, fetch them back, and
run `uv run python verify.py --require-publication`. Local preparation, a model
verdict, or a marker alone is not proof of external publication.

See `docs/delta-method.md` for the evidence model and
`docs/audit-runtime.md` and `docs/architecture.md` for the executable pipeline.
See `docs/session-2026-09-08.md` for the current audit receipt. The independent
local review and its dispositions are in `docs/adversarial-review-2026-09-08.md`.
