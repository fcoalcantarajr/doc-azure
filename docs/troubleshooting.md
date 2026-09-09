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

## `ModuleNotFoundError: No module named 'fcntl'`

Cause: the application was started in native Windows. Snapshot locking requires
the Unix `fcntl` interface.

1. Install [WSL with Ubuntu](https://learn.microsoft.com/en-us/windows/wsl/install).
2. Open the Ubuntu terminal.
3. Clone and run the project again entirely inside WSL.

Do not mix a native Windows virtual environment with the WSL project folder.

## Fresh audit ends with `ACQUISITION_VALIDATION_FAILED`

Cause: the client could not acquire or validate a complete Azure snapshot. The
most common reasons are an expired PAT, missing scope, missing project access,
network failure, a changed Azure response, or leaving the literal
`replace_with_your_azure_devops_pat` value from `.env.example` unchanged.

1. Open `.env` and confirm that the example placeholder was replaced. Do not
   paste the actual value into the terminal or a support message.
2. Confirm the PAT has not expired and is limited to `bancodonordeste`.
3. Confirm **Wiki: Read** and **Work Items: Read** scopes.
4. Confirm you can view the fixed project Wiki and `Processo-Agil` in Azure
   DevOps with the same identity.
5. Retry `uv run python scripts/run_audit.py --refresh` once.
6. If it still fails, preserve the sanitized terminal message and ask a
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

An offline-only operator does not need `.env` or `scripts/setup.py`. Place the
approved snapshots at the exact paths above and run `--offline` directly.

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

## `BUILD_FAILED: UNMAPPED_DOC_CHANGE: ...`

Cause: the standalone report build used the reviewed coverage baseline and
found changed Wiki text that no approved claim covers.

Stop publication. Do not rerun without `--coverage-baseline` and do not refresh
the baseline merely to make the command succeed. A maintainer must review the
changed text, catalog, tests, and baseline. Other `BUILD_FAILED:` messages mean
that the snapshots, catalog, selectors, or output path are invalid; preserve
the message and do not commit partially investigated reports.

## `RUN_OUTPUT_FAILED: ...`

Cause: the audit classified its work but could not write the final local bundle.
Common causes are a read-only project folder, insufficient disk space, an
unsupported filesystem lock, or a damaged path under `out/audit`.

1. Confirm the project folder and `out/` are writable by your account.
2. Confirm that the disk has free space.
3. On Windows, confirm that the project is running inside WSL.
4. Preserve existing `out/` evidence and the exact error type after the colon.
5. Retry once only after correcting the identified filesystem problem.

Do not delete or chmod the whole project as a generic workaround.

## Gate cannot rebuild reports or says provenance is unverifiable

Typical text includes `verified report rebuild failed`, `provenance is
unverifiable`, or `snapshot root has no complete CURRENT`.

Cause: `verify.py` is a maintainer provenance gate. It requires the exact
ignored Wiki and process generations named inside the current versioned
`deltas/` reports. Git does not distribute those snapshots, and a new refresh
creates different generation IDs.

- On the evidence-bearing audit machine, confirm the named generations still
  exist under `out/wiki/snapshots/` and `out/process/snapshots/`, then retry.
- On a clone without those retained generations, run `uv run pytest -q` for a
  portable code health check. Do not call that result `GATE_OK`.
- If full provenance proof is required, obtain the approved historical
  generations through the organization's private evidence-transfer process.

Never fabricate or rename a generation to match a report.

## `GATE_FAIL: Notion verification failed: ...`

Cause: `verify.py` found a local `out/notion` manifest and its external receipts
are missing, obsolete, malformed, or inconsistent with the current reports.

1. Move the entire old `out/notion` directory to a timestamped, approved backup
   location outside the project. This preserves `review/` and `fetched/`
   together and prevents old receipts from contaminating the new run.
2. Regenerate the local prepared files with
   `uv run python scripts/04_prepare_notion.py --repository-url https://github.com/fcoalcantarajr/doc-azure`.
3. If publication is not required, run `uv run python verify.py` again.
4. If publication is required, repeat the complete review, reconciliation,
   update, read-back, and proof flow in
   [Notion publication contract](notion-publication.md). Do not reuse or
   hand-edit an old receipt.

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
