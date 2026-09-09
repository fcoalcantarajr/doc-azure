# Troubleshooting

Match the exact terminal message or symptom. Do not expose `.env`, PAT values,
raw employee data, or files under `out/` when asking for help.

## `uv: command not found`

Cause: `uv` is absent or the terminal has not reloaded its executable path.

1. Install `uv` from the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/).
2. Close and reopen the terminal.
3. Run `uv --version`.

## `SETUP_FAILED: local configuration is invalid`

Cause: `.env` is missing, `AZDO_PAT` is empty, or a non-comment line in `.env`
does not contain `=`.

1. Copy `.env.example` to `.env`.
2. Keep exactly one `AZDO_PAT=...` setting with a real PAT.
3. Run `uv run --no-sync python scripts/setup.py` again.

The setup command deliberately hides the detailed value and never prints the
PAT.

## Fresh audit ends with `ACQUISITION_VALIDATION_FAILED`

Cause: the client could not acquire or validate a complete Azure snapshot. The
most common reasons are an expired PAT, missing scope, missing project access,
network failure, or a changed Azure response.

1. Confirm the PAT has not expired and is limited to `bancodonordeste`.
2. Confirm **Wiki: Read** and **Work Items: Read** scopes.
3. Confirm you can view the fixed project Wiki and `Processo-Agil` in Azure
   DevOps with the same identity.
4. Retry `uv run python scripts/run_audit.py --refresh` once.
5. If it still fails, preserve the sanitized terminal message and ask a
   maintainer to inspect the snapshot validation. Do not send the PAT or raw
   `out/` files.

A failed refresh leaves the previously selected complete source generations
unchanged.

## Offline audit says acquisition or snapshot validation failed

Cause: a new clone has no ignored cached snapshots, or local snapshots are
incomplete or invalid.

- If current Azure access is allowed, run
  `uv run python scripts/run_audit.py --refresh`.
- If network access is forbidden, obtain an approved private copy of the
  complete `out/wiki` and `out/process` evidence. Git does not contain it.

Do not create fake production evidence to make offline mode pass.

## Audit prints `DELTAS` and the shell reports exit code `1`

This is a completed audit, not a crash. Exit code `1` means coverage is complete
and at least one evaluated claim is not `CONFIRMADO`.

Open the current `global.md` and page reports as described in
[Read the results](user-guide.md#read-the-results).

## Audit prints `COVERAGE_GAP`

Cause: current Wiki text or process inventory differs from the reviewed
coverage baseline.

Stop before publication. A maintainer must review the exact change, update the
claim catalog or deterministic checks when needed, add a regression test, and
approve new baselines. Do not regenerate a baseline only to make the gate pass.

## `GATE_FAIL: Notion verification failed: ...`

Cause: `verify.py` found a local `out/notion` manifest and its external receipts
are missing, obsolete, malformed, or inconsistent with the current reports.

1. If publication is required, rerun the complete process in
   [Notion publication contract](notion-publication.md); do not hand-edit a
   receipt.
2. If publication is not required, preserve the old `out/notion` directory as
   audit evidence outside the project. Move it to an approved backup location;
   do not overwrite or delete it.
3. Regenerate only the local prepared files with
   `uv run python scripts/04_prepare_notion.py --repository-url https://github.com/fcoalcantarajr/doc-azure`.
4. Run `uv run python verify.py` again.

Never delete external receipts that must be retained under an audit or records
policy. The directory is ignored by Git but can still be institutional evidence.

## `NOTION_PREPARATION_FAILED: publication manifest is stale`

Cause: a versioned report changed after the local Notion bodies were prepared.

Run:

```sh
uv run python scripts/04_prepare_notion.py --repository-url https://github.com/fcoalcantarajr/doc-azure
```

Then restart both independent model reviews. Old reviews are bound to the old
packet and cannot approve a new one.

## Notion model, effort, page, or connector is unavailable

Stop the publication. The contract forbids model substitution, lower effort,
replacement pages, or a different surface. Local reports remain usable; only
the external publication gate is blocked.

## `GATE_FAIL` without a Notion message

Read the text after `GATE_FAIL:`. It names the failed invariant without printing
source bodies or credentials. Run the focused test suite for more diagnostic
detail:

```sh
uv run pytest -q
```

If the tests pass but the repository gate fails, the remaining failure is a
repository, evidence, generated-report, secret, or publication invariant. Do
not bypass the gate.

## The terminal prints `Hello from doc-azure!`

Cause: you ran the placeholder `main.py`, which is not the application entry
point. Run `uv run python scripts/run_audit.py --refresh` for a fresh audit.
