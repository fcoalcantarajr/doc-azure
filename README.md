# doc-azure

Use this command-line application to compare four approved Azure DevOps Wiki
pages with the current `Processo-Agil` process configuration. The application
reads Azure DevOps, creates local evidence, and produces four audit reports. It
does not change Azure DevOps.

## Start here

Choose the path that matches what you need:

| Goal | Read or run |
| --- | --- |
| Install and run the audit for the first time | [Complete user guide](docs/user-guide.md) |
| Reuse the last local evidence without Azure access | `uv run python scripts/run_audit.py --offline` |
| Run a fresh read-only Azure audit | `uv run python scripts/run_audit.py --refresh` |
| Understand a result or exit code | [Read the results](docs/user-guide.md#read-the-results) |
| Fix an error | [Troubleshooting](docs/troubleshooting.md) |
| Prepare or verify the Notion publication | [Notion publication contract](docs/notion-publication.md) |
| Maintain the application | [Technical documentation map](docs/README.md) |

If this is your first visit, follow the complete user guide in order. Do not
start with a script under `scripts/` unless that guide tells you to.

## What you need

- A macOS, Linux, or Windows computer with a terminal.
- Git, `uv`, and Python 3.11+. `uv` installs and selects the required Python
  version, so a separate Python installation is optional.
- Read access to the fixed Azure DevOps organization, project, Wiki, and
  inherited process.
- A short-lived, least-privilege Azure DevOps Personal Access Token (PAT) with
  **Wiki: Read** and **Work Items: Read** scopes for a fresh audit.
- Access to the private repository. Notion workspace and Notion AI access are
  needed only for publication.

You cannot solve missing organization or project permission with a command.
The [access checklist](docs/user-guide.md#access-checklist) tells you exactly
what to request from an administrator.

The runtime has one direct dependency, `httpx>=0.25.0`. The development group
adds `pytest>=8.0.0`. `uv sync --locked` installs both from `uv.lock`.

## First run

Run these commands from a terminal. Replace only the repository clone step if
you already have this project folder.

```sh
git clone https://github.com/fcoalcantarajr/doc-azure.git
cd doc-azure
uv sync --locked
cp .env.example .env
```

On Windows PowerShell, use `Copy-Item .env.example .env` instead of `cp`.
Open `.env`, replace the placeholder with your PAT, save the file, and then run:

```sh
uv run --no-sync python scripts/setup.py
uv run python scripts/run_audit.py --refresh
```

`DELTAS` and exit code `1` are a valid audit result: the application completed
and found differences or evidence limits. They do not mean that the program
crashed. See [Read the results](docs/user-guide.md#read-the-results) before
deciding what to do.

## Safety boundary

The Azure client fails closed outside its explicit allowlist. Collection uses
GET requests for Wiki and process reads; only the two documented query-only
POST routes are permitted by the shared safety contract. Creation, update,
deletion, redirects, absolute URLs, and method overrides are rejected before
transport.

Keep `.env` and everything under `out/` private. They are ignored by Git
because raw evidence can include employee data and `.env` contains a secret.
Never paste a PAT into a command, issue, chat, log, report, or Notion page.

Notion publication is separate from the core audit. It updates only four fixed
existing pages after independent Kimi K3 and Opus 5 reviews, reconciliation,
connector read-back, and the strict publication gate. Preparing local Notion
files does not publish anything.

## What the application produces

- `out/wiki/` and `out/process/`: ignored immutable source snapshots.
- `out/audit/`: ignored per-run diagnostic and result bundles.
- `deltas/`: four versioned Brazilian-Portuguese reports.
- `out/notion/`: ignored publication bodies, review packets, and receipts.

The audit evaluates 222 explicit claims. Every conclusion has an exact Wiki
source pointer; comparable findings also have an exact process evidence
pointer. See [Evidence-backed delta method](docs/delta-method.md) for the
technical rules.
