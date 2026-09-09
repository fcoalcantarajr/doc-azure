# Application architecture and handoff

The executable boundary is `scripts/run_audit.py`. It has no Notion import and
does not call an AI service. The pipeline is deliberately linear:

```text
Azure REST (GET allowlist)
        |
        v
immutable wiki/process generations
        |
        +--> documentary baseline -> exact line coverage
        +--> process baseline -----> typed JSON-pointer inventory coverage
        |
        v
versioned catalog -> existing deterministic evaluator -> classifications
        |
        v
atomic out/audit/{run.json,global.md,four pages}
```

Collectors use one `httpx.AsyncClient` per live run and record only sanitized
method/path receipts. The immutable `SnapshotWriter` validates the manifest and
artifact hashes before exposing a generation. Cached reads use no-follow,
digest-checked file descriptors. Partial envelopes, missing artifacts, duplicate
identities, invalid JSON and response identity mismatches fail closed.

## Source of truth and maintenance

`config/wiki_claims.json` is the only assertion catalog. Each claim has a stable
ID, fixed Wiki page, exact line/excerpt/hash, deterministic check kind and an
explicit limitation. Do not add keyword extraction or a second evaluator. To add
a claim:

1. collect a fresh read-only Wiki snapshot;
2. write the smallest deterministic check and exact Azure JSON pointer;
3. add a fixture regression that fails when the predicate or pointer is broken;
4. run `scripts/prepare_baselines.py` and review both resulting candidates;
5. update the catalog and baselines in one audited change;
6. run the full gate and inspect the generated evidence.

Material prose not represented by a claim is `UNMAPPED_DOC_CHANGE`; it is never
classified as a match. Only CRLF/LF is normalized. A process inventory change is
`PROCESS_INVENTORY_CHANGE` and causes `COVERAGE_GAP`, even if existing claims
happen to remain true. This deliberately favors visible under-coverage over a
false clean result.

## Result classes

- `CONFIRMADO`: exact documented value and current process evidence agree.
- `DIVERGENTE`: both dimensions are comparable and differ.
- `NAO_VERIFICAVEL_API_PROCESSO`: the process API cannot establish the documentary
  dimension (chronology, governance or runtime practice, for example).
- `AMBIGUO`: current evidence supports more than one material interpretation.
- `UNMAPPED_DOC_CHANGE` / `PROCESS_INVENTORY_CHANGE`: coverage gate findings;
  they are not assertion classifications.

The run exit code distinguishes clean, deltas, coverage gaps, acquisition or
snapshot validation failure, and unexpected internal failure. Logical hashes omit
generation IDs and timestamps; provenance still records them for reproduction.

## Security and limitations

`.env`, raw snapshots and generated output remain ignored. Baselines contain
hashes and pointers, not raw Azure response bodies, but names and selectors can
still be sensitive. Review before publication. A local receipt proves what the
client captured; it cannot cryptographically attest to a remote server response.
The process inventory is intentionally conservative about metadata/order changes.
Notion publication and external adversarial reviews are separate, explicit gates.

## Handoff checklist

Use the canonical command, then rebuild four versioned reports and prepare the
Notion packet. Before claiming completion, verify all 19 objective requirements,
run the strict external-review/publication gate, read back the four canonical
Notion pages under the common parent, scan reachable Git history for secrets, and
push only the intended branch to the private repository.
