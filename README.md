# doc-azure

Offline-first audit tooling for comparing four fixed Azure DevOps wiki pages
with the inherited `Processo-Agil` process configuration. Azure collection is
semantically read-only; generated evidence remains ignored under `out/`.

## Setup

Python 3.13 and `uv` are required. The project has one runtime dependency,
`httpx>=0.28.1`.

```text
uv sync
uv run --no-sync python scripts/setup.py
```

The setup command is safe to repeat. It validates local inputs without printing
the PAT. Keep `AZDO_PAT` only in the ignored `.env` file.

## Workflow

```text
# Networked Azure DevOps reads; both collectors fail closed outside the allowlist.
uv run python scripts/01_fetch_wiki.py --refresh
uv run python scripts/02_fetch_process.py --refresh

# Offline catalog evaluation and deterministic reports.
uv run python scripts/03_build_delta.py

# Offline Notion-body preparation only; this does not publish.
uv run python scripts/04_prepare_notion.py

# Non-mutating local gate.
uv run python verify.py
```

Outputs:

- immutable raw snapshots and manifests: ignored `out/wiki` and `out/process`;
- versioned reports: `deltas/leiame.md`, `deltas/politicas.md`,
  `deltas/changelog.md`, and `deltas/apendice.md`;
- ignored prepared Notion bodies and manifest: `out/notion`.

The current audit evaluates 223 explicit claims backed by exact documentary
fragments. Reports identify the wiki/process generations, collection times,
manifest hashes, process name, and process UUID used for evaluation.

## Safety boundary

Azure DevOps collection uses allowlisted GET requests only for this workflow.
No collector creates, updates, or deletes process/wiki data. Raw evidence may
contain employee data and must not be committed. Never stage `.env` or `out/`.

Notion publication is a separate, pending step. After the required independent
Notion AI reviews, use the authenticated Notion connector to update only the
four fixed pages listed in `docs/notion-publication.md`, fetch them back, and run
`uv run python verify.py --require-publication`. Local preparation is not proof
of external publication.

See `docs/delta-method.md` for the evidence model and
`docs/session-2026-08-24.md` for the current audit receipt.
