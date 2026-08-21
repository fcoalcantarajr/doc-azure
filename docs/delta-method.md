# Delta Generation Method

This document describes the algorithm for comparing Azure DevOps wiki pages against the Processo-Agil implementation and generating delta markdown files.

## Overview

The delta method identifies discrepancies between documentation (wiki pages) and implementation (process model). Each row in a delta represents a claim about a specific artifact that appears in one artifact but not the other, or appears differently.

## Input Sources

### Wiki Pages (out/wiki/)
Four wiki pages are fetched from Azure DevOps:
- **leiame** (page_id=35) - "Leia-me Processo da Organização Única"
- **politicas** (page_id=10) - "Template de políticas explícitas"  
- **changelog** (page_id=9) - "Changelog"
- **apendice** (page_id=37) - "Apêndice Técnico Processo Organização Única"

### Process Model (out/process/)
The Azure DevOps Processo-Agil process is fetched:
- **process.json** - Full process definition including work item types
- **WIT files** - Fields for each work item type

## Delta Classification

Every row is classified as one of four classes:

| Class | Meaning | Evidence Constraints |
|-------|---------|---------------------|
| **MATCH** | Documented and implemented identically | Both doc_evidence and azure_evidence required |
| **DOC_ONLY** | Only in wiki, not in process | azure_evidence must be "n/a" |
| **AZURE_ONLY** | Only in process, not in wiki | doc_evidence must be "n/a" |
| **DIVERGENT** | Present in both but differ | Both evidences required, describes difference |

## Algorithm

### Step 1: Extract Artifacts

From wiki pages:
- Extract all work item type names, field names, and policy definitions
- Identify section headers, rules, and configurations

From process model:
- Extract work item type names from `workItemTypes[].name`
- Extract field names from `workItemTypes[].fields[]`
- Extract rules from `workItemTypes[].fields[].helpText`, `readOnly`, `required`

### Step 2: Normalize Identifiers

Both sources use different naming conventions:
- Wiki may use Portuguese titles with spaces
- Process uses camelCase or specific Azure DevOps identifiers

Normalize both to a canonical form for comparison.

### Step 3: Compare Sets

For each artifact category:
1. Compute intersection → MATCH candidates
2. Wiki-only → DOC_ONLY
3. Process-only → AZURE_ONLY
4. Compare properties of intersection → DIVERGENT if different

### Step 4: Generate Markdown Table

```markdown
| id | claim (pt-BR) | class | doc_evidence | azure_evidence | consequence |
|----|---------------|-------|--------------|----------------|-------------|
| ... | ... | ... | ... | ... | ... |
```

### Step 5: Render Summary Block

After all rows, append:
```markdown
SUMMARY
DOC_ONLY=N
AZURE_ONLY=N
DIVERGENT=N
MATCH=N
```

## Evidence Pointers

### Document Evidence
Format: `out/wiki/<slug>.md#L<line>`
- File exists under `out/wiki/`
- Line number exists in file

Example: `out/wiki/leiame.md#L42`

### Azure Evidence
Format: `out/process/<file>.json#/json/path`
- File exists under `out/process/`
- JSON path resolves

Example: `out/process/process.json#/workItemTypes/0/name`

## Idempotency

Scripts are idempotent:
- Running without `--refresh` skips network calls for existing files
- Running with `--refresh` forces re-fetch from Azure DevOps
- Output is deterministic: same input produces identical output

## Validation Rules

1. Every row must have a valid class literal
2. DOC_ONLY rows must have `azure_evidence = "n/a"`
3. AZURE_ONLY rows must have `doc_evidence = "n/o"`
4. Non-MATCH rows must have a non-empty consequence sentence

## Running the Delta

1. Fetch wiki: `uv run python scripts/01_fetch_wiki.py`
2. Fetch process: `uv run python scripts/02_fetch_process.py`
3. Build delta: `uv run python scripts/03_build_delta.py`

The delta builder reads `out/wiki/` and `out/process/` and produces `deltas/<slug>.md`.