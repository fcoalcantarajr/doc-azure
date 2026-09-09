# Complete user guide

This guide assumes no Python experience. Follow the sections in order for a
first run. Commands are safe to copy exactly unless a step explicitly tells you
to replace a value.

## What this application does

`doc-azure` answers one fixed question: where do four approved Azure DevOps
Wiki pages agree with, differ from, or go beyond what the current inherited
`Processo-Agil` configuration can prove?

It is a command-line application, not a website. You run commands in a
terminal. A fresh run reads a fixed Azure DevOps organization and project,
saves private evidence locally, evaluates 222 reviewed claims, and writes
reports. It never edits Azure DevOps.

## Access checklist

You need all items in this list before a fresh network run:

- access to the private `fcoalcantarajr/doc-azure` GitHub repository;
- membership in the `bancodonordeste` Azure DevOps organization;
- read access to project `Torre CCR - Concessão de Crédito`;
- read access to its approved Wiki pages and the `Processo-Agil` process;
- permission to create an Azure DevOps PAT;
- a PAT limited to the organization, with an expiration date, **Wiki: Read**,
  and **Work Items: Read** scopes.

If an item is missing, send this request to the responsible administrator:

> I need read-only access to the Azure DevOps organization `bancodonordeste`,
> project `Torre CCR - Concessão de Crédito`, its project Wiki, and inherited
> process metadata for `Processo-Agil`. I also need permission to create a
> short-lived PAT with only Wiki: Read and Work Items: Read scopes. I do not
> need permission to create, update, or delete Azure DevOps content.

Notion publication has extra prerequisites. Read [Publish to Notion](#publish-to-notion)
only if publication is part of your task.

## Install the tools

### 1. Install Git

Run `git --version`. If it prints a version, continue.

- macOS: running `git --version` opens the Command Line Tools installer when
  Git is absent.
- Windows: install [Git for Windows](https://git-scm.com/download/win).
- Debian or Ubuntu: run `sudo apt install git`.
- Other systems: use the [official Git installation guide](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git).

### 2. Install uv

Use one official option:

```sh
# macOS or Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen the terminal. Run `uv --version`. If the command is still not
found, follow the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

You do not need to install Python separately. The project requests Python 3.13
through `.python-version`; its supported minimum is Python 3.11. `uv` downloads
a compatible Python when needed.

## Download and prepare the project

### 1. Clone the private repository

```sh
git clone https://github.com/fcoalcantarajr/doc-azure.git
cd doc-azure
```

If GitHub asks you to authenticate, use your approved organization method. A
GitHub password is not accepted for Git operations over HTTPS.

Already have the folder? Open a terminal in it and confirm:

```sh
git rev-parse --show-toplevel
```

The printed path must end in `doc-azure`.

### 2. Install the locked dependencies

```sh
uv sync --locked
```

Expected result: `uv` creates or updates `.venv` and completes without an error.
You do not need to activate this environment; every project command begins with
`uv run`.

### 3. Create the private configuration file

macOS or Linux:

```sh
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Open `.env` in a text editor. Replace the placeholder after `AZDO_PAT=` with
your PAT. Keep the setting on one line:

```dotenv
AZDO_PAT=your_actual_token_goes_here
```

Do not add quotes unless the token itself requires them. Never share the file
or its contents. The application accepts `AZDO_PAT` from the process environment
instead, but `.env` is easier for a first run.

To open the file from the terminal, use `open -e .env` on macOS,
`nano .env` on Linux, or `notepad .env` in Windows PowerShell. Save and close
the editor before continuing.

### 4. Validate the configuration

```sh
uv run --no-sync python scripts/setup.py
```

Expected final line:

```text
CONFIGURATION_OK
```

This step checks only the local format and creates ignored output directories.
It does not prove that the PAT is current or has remote permission.

## Run the audit

### Fresh read-only audit

```sh
uv run python scripts/run_audit.py --refresh
```

`--refresh` requests all four Wiki pages and the complete current process model.
The application records sanitized request paths, validates every response, and
publishes a new local run only after the evidence is complete.

The final output has a status, a logical SHA-256, and the path to
`out/audit/CURRENT`. Example:

```text
DELTAS: <64-character logical hash>
.../doc-azure/out/audit/CURRENT
```

Do not assume that any nonzero exit code means a crash. Interpret the status
using the next section.

### Offline audit

Use existing complete snapshots without network access:

```sh
uv run python scripts/run_audit.py --offline
```

Offline mode never contacts Azure DevOps. It fails if this copy of the project
does not already contain complete ignored snapshots under `out/wiki` and
`out/process`. A new Git clone does not contain them.

### Cache-first audit

Reuse complete cached evidence and fetch only missing pieces:

```sh
uv run python scripts/run_audit.py
```

Use `--refresh` when the decision requires current Azure state. Use `--offline`
when network access is forbidden. Use no mode only for cache-first recovery or
diagnosis.

## Read the results

### 1. Interpret the terminal status

| Exit | Status | Meaning | Next action |
| ---: | --- | --- | --- |
| 0 | `CLEAN` | Coverage is complete and every evaluated claim agrees. | Review and retain the reports. |
| 1 | `DELTAS` | The run completed; at least one finding is divergent, ambiguous, or not verifiable through the process API. | Read `global.md`, then the four page reports. |
| 2 | `COVERAGE_GAP` | A Wiki or process change is outside the reviewed coverage contract. | Stop publication and ask a maintainer to review the changed source and baseline. |
| 3 | `ACQUISITION_VALIDATION_FAILED` | Azure access, network, response, or snapshot validation failed. | Use [Troubleshooting](troubleshooting.md). |
| 4 | `INTERNAL_ERROR` | The application could not complete or publish its local output. | Preserve the terminal message and use [Troubleshooting](troubleshooting.md). |

`DELTAS` is the normal result when the audit finds useful differences. It is
not a failed execution.

### 2. Find the current run

`out/audit/CURRENT` contains the identifier of the selected run. To print the
current report directory on any supported operating system, run:

```sh
uv run python -c "from pathlib import Path; p=Path('out/audit'); print(p/'snapshots'/(p/'CURRENT').read_text().strip())"
```

Open `global.md` in that directory first. It summarizes coverage and all four
reports. Then open `leiame.md`, `politicas.md`, `changelog.md`, and
`apendice.md` for finding-level evidence. `run.json` contains the same run in a
machine-readable form.

### 3. Interpret each finding

| Finding status | What the evidence supports |
| --- | --- |
| `CONFIRMADO` | The exact documented and implemented values agree. |
| `DIVERGENTE` | The values are comparable and differ. |
| `NAO_VERIFICAVEL_API_PROCESSO` | The current process API does not represent the documentary dimension. This is not proof of absence. |
| `AMBIGUO` | Available evidence supports more than one material interpretation. |

Every finding points to exact local Wiki evidence. Comparable findings also
point to exact process JSON. Treat employee names and raw evidence as private.

## Build the versioned reports

The complete runtime creates an ignored diagnostic bundle. To rebuild the four
versioned reports in `deltas/` from verified snapshots, run:

```sh
uv run python scripts/03_build_delta.py
```

Expected output: the four paths under `deltas/`. This command performs no
network request. If it detects unmapped source changes or invalid evidence, it
stops before replacing the reports. A replacement failure restores verified
backups for files already touched.

## Verify the repository

Run the local project gate:

```sh
uv run python verify.py
```

Expected success marker:

```text
GATE_OK
```

The gate runs tests, validates the Azure request boundary, rebuilds and compares
reports, checks ignored files, and scans for tracked secret values. If a local
`out/notion` publication manifest exists, the gate also validates it. Therefore
an obsolete external receipt can fail this command even when the Python tests
pass; follow the matching message in [Troubleshooting](troubleshooting.md).

## Publish to Notion

Skip this section if you only need the local audit. Publication changes four
existing Notion pages, so it requires the separate contract and proof chain.

Prerequisites:

- edit access to the fixed `Azure` hub and its four existing delta pages;
- the connected Notion MCP workspace;
- the ChatGPT-integrated browser signed in to Notion AI;
- Kimi K3 and Opus 5 available at maximum effort;
- access to the private GitHub repository URL used in the review packet.

### 1. Prepare local publication files

```sh
uv run python scripts/04_prepare_notion.py --repository-url https://github.com/fcoalcantarajr/doc-azure
```

This command writes only ignored files under `out/notion`. It does not contact
Notion and does not publish.

### 2. Complete the external gate

Follow [Notion publication contract](notion-publication.md) exactly. In summary:

1. Send the identical packet to separate Kimi K3 and Opus 5 chats at maximum
   effort in the integrated browser.
2. Preserve the model, effort, chat, packet, prompt, response, and time receipts.
3. Reconcile every material finding against source evidence; agreement by vote
   is insufficient.
4. Update only the four fixed existing page IDs through the Notion connector,
   then fetch them and check their common parent and duplicates.

If the exact model, effort, signed-in session, or fixed page identity is not
available, stop. Do not substitute a model or create replacement pages.

### 3. Prove publication

```sh
uv run python scripts/04_prepare_notion.py --verify-publication
uv run python verify.py --require-publication
```

Required success markers are `NOTION_PUBLICATION_OK` and `GATE_OK`. A prepared
file, AI verdict, update response, or marker by itself is not proof of current
publication.

## Repeat a routine audit

1. Open a terminal in `doc-azure`.
2. Run `git status --short` and do not discard changes you do not recognize.
3. Run `uv sync --locked` after pulling a new revision.
4. Run `uv run python scripts/run_audit.py --refresh`.
5. Read the status and current `global.md`; publish only when the publication
   contract is part of the task.

## Protect and remove local data

- Revoke or rotate the PAT according to your organization's policy.
- Delete `.env` when this computer should no longer retain the credential.
- Treat `out/` as private evidence. Removing it deletes cached snapshots,
  generated reports, and publication receipts; make an approved backup first
  if the audit trail must be retained.
- Do not commit `.env` or `out/`. Run `git status --short` before every commit.

The application has no remote cleanup operation because it does not create or
change Azure DevOps data. Notion page changes are external and are governed by
the fixed-page publication contract.
