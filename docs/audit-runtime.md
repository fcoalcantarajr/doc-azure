# Deterministic runtime

Canonical command:

```sh
uv run python scripts/run_audit.py --refresh
```

`--refresh` fetches both source families through the existing allowlisted Azure
REST collectors. Omit it for cache-first operation; `--offline` forbids network
acquisition and requires complete local snapshots. The command accepts `--root`,
`--catalog`, `--document-baseline` and `--process-baseline` for fixture/replay use.
The ignored `.env` supplies `AZDO_PAT` for network runs only.

## Pipeline and outputs

Acquisition -> existing collector completeness validation -> documentary coverage
-> process inventory comparison -> existing claim evaluator -> result bundle.
There is no model, prompt, semantic heuristic, or Notion request in this flow.

The existing immutable `SnapshotWriter` publishes one bundle under `out/audit`.
Resolve its `CURRENT` pointer to find `run.json`, `global.md` and all four page
reports. Error/gap runs also publish their own diagnostic bundle, clearly marked
incomplete; they never replace source evidence or canonical `deltas/` reports.

Exit contract:

| Code | Meaning |
| --- | --- |
| 0 | Every evaluated assertion confirmed, no coverage gap |
| 1 | Coverage complete, at least one non-confirmed finding |
| 2 | Coverage gap or invalid/missing coverage contract |
| 3 | Acquisition or snapshot/input validation failed |
| 4 | Unexpected internal error or inability to publish outputs |

`logical_sha256` excludes generation IDs, collection timestamps and run creation
time. Provenance remains separately recorded in JSON and rendered reports.
Immutable run generations may differ on replay while logical results match.

## Process inventory baseline

`config/process-coverage.json` has exactly `schema_version: 1`,
`catalog_sha256` and `entries`. Entries are fingerprints from `fingerprint_json`
over the complete map of artifact filename to parsed JSON response. Every node
has a type-preserving fingerprint, addressed by an escaped JSON Pointer. Empty
containers and array order are preserved; object-key order is normalized.

Current policy is conservative: every inventory drift is a coverage gap even
when individual mapped assertions can still be evaluated. This avoids claiming
coverage of new surfaces, but may require review for API ordering or metadata
changes. No property is dropped as supposedly volatile without evidence. A
reviewed baseline is not, by itself, proof that all relevant prose was modeled.

## Reviewed baseline and current receipt

The complete pipeline is tested against synthetic full collector fixtures, both
offline and through HTTP transport substitution with the real collectors.
The refresh test observes 18 GET requests and no writes. The CLI is exercised as
a subprocess. The first implementation exposed missing collector clock arguments
and incorrect categorization of corrupt snapshots; both have regression tests.

The versioned baselines were prepared from the complete verified snapshots with
`scripts/prepare_baselines.py`, then checked byte-for-byte before being added to
`config/`. They contain 222 claim IDs, four page line inventories (572, 361, 593
and 517 lines respectively) and 40,559 process JSON nodes across 110 artifacts.
The files contain hashes and selectors, not raw Azure response bodies.

Baseline SHA-256 values:

- `config/document-coverage.json`: `2e0d956a8f74f3933779d297adfff1328267de1ccd8a04e555228b7edbf2990e`
- `config/process-coverage.json`: `4fe95039f993a9473677b98e4a652bc4d0d79c1ad1a6658d6598bdfce9cd2418`

A fresh `--refresh` run on 2026-09-09 collected four Wiki pages with four GETs
and 109 process artifacts with 109 GETs. It returned code 1 (`DELTAS`), coverage
complete, zero gaps and 222 classified findings: 123 `CONFIRMADO`, 59
`DIVERGENTE`, 31 `NAO_VERIFICAVEL_API_PROCESSO` and 9 `AMBIGUO`. Its logical
hash was `3ea48dc27b83ba7ba1491f56538e893433f52eaf9df063affe099dbca0166369`.

The report verifier intentionally canonicalizes only collection timestamp,
snapshot-generation ID and manifest-hash fields in the provenance section. All
logical findings and stable report text remain byte-compared, so a fresh
equivalent collection cannot create a false drift while a real report mutation
still fails the gate.

Remaining work is external to the deterministic runtime: the exact Notion AI
reviews and the gated canonical Notion publication/read-back.

Validation for this increment: duplicate-identifier RED/GREEN regression,
offline no-network, clean/internal exit and process-drift regressions pass; full
suite currently has 374 tests. The fresh
live run is evidence of the application path, not completion of the Notion gates.
