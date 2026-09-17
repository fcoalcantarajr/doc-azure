# Application architecture and handoff

The executable boundary is `scripts/run_audit.py`. It has no Notion import and
does not call an AI service. The pipeline is deliberately linear:

```text
Azure REST (GET plus two query-only POST routes)
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

## Derived process-only LLM export

`scripts/export_process_for_llm.py` is a separate derived-output boundary. It
pins and validates one immutable `out/process` generation before the first
artifact read, builds one immutable semantic model, and renders both
`bundle.md` and the per-WIT documents from that same model. It never imports the
Wiki, delta evaluator, Notion code, or an LLM client.

The selected export is also the explicit predecessor boundary. Its source
identity loads a second immutable semantic model, and the exporter derives
`delta.md` plus a closed `delta.json` from the two models. If the current source
already equals the selected export source, the prior baseline recorded in that
generation is retained so retries remain byte-stable. UUID names and filesystem
timestamps are never used to infer chronology. A concurrent change to the
selected export aborts the operation before reuse or publication.

The export removes only exact transport properties named `url` and redundant
validated `count/value` envelopes. It preserves array order, explicit `order`
values, scalar distinctions, and unknown API extensions under
`additional_properties`. `SnapshotWriter` publishes the derived files and their
hashes atomically under `out/process-llm`; provenance binds the result to the
source generation and exact source-manifest hash. Reuse requires both values to
match together with the delta baseline and rendered bytes. This representation
is descriptive evidence, not proof of institutional
intent, governance, actual use, or configuration correctness.

## Handoff checklist

Use the canonical command, then rebuild four versioned reports and prepare the
Notion packet. Before claiming completion, verify all 19 objective requirements,
run the strict external-review/publication gate, read back the four canonical
Notion pages under the common parent, scan reachable Git history for secrets, and
push only the intended branch to the private repository.
