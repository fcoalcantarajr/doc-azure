# Documentary coverage contract

The offline builder now accepts a reviewed documentary baseline:

```sh
uv run python scripts/03_build_delta.py --coverage-baseline config/document-coverage.json
```

The referenced configuration must be explicitly created and reviewed; it is not
automatically accepted from current source text. A production baseline and the
unified runtime remain pending. Omitting this option retains the older builder's
exact-source behavior and does not assert full documentary coverage.

## Schema version 1

The JSON root has exactly four keys:

- `schema_version`: integer `1`, not a boolean.
- `catalog_sha256`: SHA-256 of the exact catalog bytes.
- `claim_ids`: every catalog claim ID, once, in catalog order.
- `documents`: exactly `leiame`, `politicas`, `changelog`, `apendice`.

Each document contains exactly `source_sha256` (the catalog's raw source hash)
and `line_hashes` (ordered SHA-256 values from `document_fingerprint`). These
hashes are an explicit reviewed coverage boundary, not a semantic interpretation
or proof that a human catalog author captured every relevant assertion.

Keep the corresponding original Wiki snapshots in ignored evidence storage;
removed text cannot be recovered from a hash. Reported deletion spans identify
baseline line numbers and hashes. Added/replaced spans include current line
numbers and exact text. Do not publish raw evidence without checking sensitivity.

## Behavior and limits

Only CRLF/LF conversion is normalized. Whitespace, capitalization, Unicode,
duplicate lines, blank lines and terminal newline changes remain detectable.
If any page changes materially, `assess_documents` returns its change spans and
excludes all claims from that page. The builder refuses publication with
`UNMAPPED_DOC_CHANGE`, leaving previous reports untouched; its exit code is 1.
It does not classify the new prose as either a match or a conflict.

For cosmetic equivalence, the in-memory claim receives the actual current byte
hash, and every source excerpt is reverified before the existing evaluator runs.
Neither source snapshots nor the versioned catalog are rewritten.

To adopt a material documentary change, review the exact changed text, update
the explicit claims and regressions, and review a new baseline in the same
versioned change. Never refresh the baseline merely to make a gate green.

This component does not yet provide process-inventory coverage, whole-run
structured reports or the final application's distinct exit codes. Those remain
explicit tasks in the deterministic-runtime plan.

## Verification receipt

Tests exercise real snapshots, catalog parsing, claim evaluation and a subprocess
invocation of the offline command. The command first builds unchanged fixtures,
then rejects newly appended prose while retaining the previous report bytes.

- RED (builder): unexpected keyword argument `coverage_baseline` (2 failures).
- RED (CLI): unrecognized argument `--coverage-baseline` (1 failure).
- GREEN: 24 focused integration/builder/entrypoint tests.
- Full regression: 338 passed in 2.89s.
