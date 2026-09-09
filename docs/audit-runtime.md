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

## Current delivery status and remaining work

The complete pipeline is tested against synthetic full collector fixtures, both
offline and through HTTP transport substitution with the real collectors.
The refresh test observes 18 GET requests and no writes. The CLI is exercised as
a subprocess. The first implementation exposed missing collector clock arguments
and incorrect categorization of corrupt snapshots; both have regression tests.

The live versioned baselines are not yet authored/reviewed. Therefore the default
real-data command must currently report a coverage gap, not completion. Remaining
work includes baseline maintenance tooling, finer mapped-change coverage policy,
additional clean/internal-error/selector/partial-response regressions, final live
refresh and inspection, documentation reconciliation, private GitHub sync, final
Notion AI reviews and canonical Notion publication/read-back.

Validation for this increment: 23 new runtime/inventory tests passed; full suite
361 passed in 3.42s. This receipt is not the final application acceptance gate.
