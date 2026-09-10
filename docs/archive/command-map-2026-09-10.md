# doc-azure — Files, Commands, and Error Reference

## FILES

### Core Modules

| File | Key Contents |
|------|-------------|
| `src/doc_azure/settings.py` | `SettingsError(ValueError)`, `AZDO_PAT` env var |
| `src/doc_azure/azure_client.py` | `AzureReadError(RuntimeError)` |
| `src/doc_azure/wiki_collector.py` | `WikiCollectionError(RuntimeError)` |
| `src/doc_azure/snapshot.py` | `SnapshotError(RuntimeError)` |
| `src/doc_azure/audit.py` | `RunOutcome`, audit pipeline logic |
| `verify.py` | `VerificationError`, `_VOLATILE_PROVENANCE_LINES`, `_REPORT_PROVENANCE_LINE`, `_verify_versioned_report_provenance()`, `_verify_report_provenance()` |

### Delta Modules (`src/delta/`)

| File | Key Contents |
|------|-------------|
| `src/delta/build.py` | `BuildError(RuntimeError)` |
| `src/delta/catalog.py` | `CatalogError(ValueError)` |
| `src/delta/document_coverage.py` | `CoverageError(ValueError)` |
| `src/delta/evaluator.py` | `EvaluationError(ValueError)` |
| `src/delta/notion.py` | `NotionPublicationError(ValueError)` |
| `src/delta/evidence.py` | `EvidenceError` |
| `src/delta/notion_semantics.py` | `ReportSemanticError` |

### CLI Scripts

| File | Purpose |
|------|---------|
| `scripts/run_audit.py` | Main audit entry point |
| `scripts/01_fetch_wiki.py` | Fetch wiki pages |
| `scripts/02_fetch_process.py` | Fetch process pages |
| `scripts/03_build_delta.py` | Build delta artifacts |
| `scripts/04_prepare_notion.py` | Prepare Notion publication |
| `scripts/setup.py` | Project setup |
| `scripts/prepare_baselines.py` | Baseline preparation |

### Config and Docs

- `config/` — Project configuration
- `docs/` — 20 markdown documentation files
- `deltas/` — 4 delta output files (leiame, changelog, politicas, apendice)

---

## COMMANDS

### `python scripts/run_audit.py`

Validates the full delta pipeline. On success prints `{status}: {logical_sha256}` and writes `out/audit/CURRENT`. On `Exception`: prints `RUN_OUTPUT_FAILED: {type(error).__name__}`, returns 4.

### `python scripts/01_fetch_wiki.py`

Flags: `--root`, `--catalog`, `--evidence-root`, `--verify-fetched`, `--refresh`

### `python scripts/02_fetch_process.py`

Flags: `--root`, `--catalog`, `--evidence-root`, `--refresh`

### `python scripts/03_build_delta.py`

On `BuildError`: prints `BUILD_FAILED: {error}`, returns 1. On success prints output paths, returns 0.

### `python scripts/04_prepare_notion.py`

On `NotionPublicationError`: prints `NOTION_PREPARATION_FAILED: {error}`, returns 1. On success prints manifest path and entry paths, returns 0.

### `python scripts/setup.py`

Returns 0 (success) or 1 (failure).

### `python scripts/prepare_baselines.py`

Returns 0 always.

---

## EXIT CODES AND ERRORS

### Exit Codes (run_audit.py)

| Code | Status String | Meaning |
|------|--------------|---------|
| 0 | `CLEAN` | All checks passed |
| 1 | `DELTAS` | Delta validation issues |
| 2 | `COVERAGE_GAP` | Coverage gaps found |
| 3 | `ACQUISITION_VALIDATION_FAILED` | Acquisition validation failed |
| 4 | `INTERNAL_ERROR` | Internal error or unhandled exception |

### Error Class Hierarchy

| Class | Parent | Module |
|-------|--------|--------|
| `SettingsError` | `ValueError` | `src/doc_azure/settings.py` |
| `AzureReadError` | `RuntimeError` | `src/doc_azure/azure_client.py` |
| `WikiCollectionError` | `RuntimeError` | `src/doc_azure/wiki_collector.py` |
| `SnapshotError` | `RuntimeError` | `src/doc_azure/snapshot.py` |
| `EvaluationError` | `ValueError` | `src/delta/evaluator.py` |
| `NotionPublicationError` | `ValueError` | `src/delta/notion.py` |
| `CoverageError` | `ValueError` | `src/delta/document_coverage.py` |
| `BuildError` | `RuntimeError` | `src/delta/build.py` |
| `CatalogError` | `ValueError` | `src/delta/catalog.py` |
| `EvidenceError` | — | `src/delta/evidence.py` |
| `ReportSemanticError` | — | `src/delta/notion_semantics.py` |
| `VerificationError` | — | `verify.py` |

### Key Error Strings

- `RUN_OUTPUT_FAILED: {type(error).__name__}` — `scripts/run_audit.py`
- `BUILD_FAILED: {error}` — `scripts/03_build_delta.py`
- `NOTION_PREPARATION_FAILED: {error}` — `scripts/04_prepare_notion.py`
- `"ERROR: cached wiki snapshot failed validation"` — `scripts/01_fetch_wiki.py`
- `"ERROR: wiki collection failed safely"` — `scripts/01_fetch_wiki.py`

### Verify Module (`verify.py`)

- `VerificationError` raised on provenance verification failure
- `_VOLATILE_PROVENANCE_LINES` — regex pattern for volatile provenance lines
- `_REPORT_PROVENANCE_LINE` — regex pattern for report provenance lines
- `_verify_versioned_report_provenance()` — validates versioned report provenance
- `_verify_report_provenance()` — validates report provenance

### Script Return Codes Summary

| Script | Success | Failure |
|--------|---------|---------|
| `run_audit.py` | 0–3 | 4 |
| `01_fetch_wiki.py` | 0 | 1 |
| `02_fetch_process.py` | 0 | 1 |
| `03_build_delta.py` | 0 | 1 |
| `04_prepare_notion.py` | 0 | 1 |
| `setup.py` | 0 | 1 |
| `prepare_baselines.py` | 0 | — |
