# Independent branch review — 2026-09-08

## Fixed point and scope

- Merge base: `31078f9bff58c76da40e0d850df80598f6f2a622`.
- Reviewed branch: `fix/adversarial-delta-audit`.
- Reviewers were read-only and independent. One assessed repository standards;
  the other assessed fidelity to the approved design, plan, and user request.
- These reviews are local code/spec reviews. They do not satisfy the separate
  Kimi K3 and Opus 5 Notion AI publication gate.

## Standards review

1. **P1 — external gate accepted self-declared evidence.** Review, publication,
   hierarchy and search receipts checked fields, timestamps and hashes but did
   not interpret the raw result content. Accepted. The gate now parses raw
   browser/connector envelopes and cross-checks model, effort, chat, response,
   page, parent, title, content, update identity and exact search matches.
2. **P2 — snapshot cache readers had a TOCTOU seam.** Wiki and process
   collectors re-read validated artifacts through `Path.read_text`, allowing a
   post-validation symlink swap. Accepted. Manifest parsing is centralized and
   artifact reads use the no-follow, same-operation digest-checking primitive.
3. **P2 — environment contract contradicted executable metadata.** README said
   Python 3.13 and `httpx>=0.28.1`; the approved design/package contract was
   Python 3.11+ and `httpx>=0.25.0`, with `pytest` mixed into runtime. Accepted.
   README and package metadata now agree, with test tooling in the dev group.

The reviewer also noted duplicated unsafe manifest readers and repeated
path/hash evidence pairs. The first was removed. The second remains explicit in
the serialized receipt schema, while parsing/verification is centralized behind
the external-evidence module.

## Spec fidelity review

1. **P1 — external delivery is incomplete.** Confirmed. Local `GATE_OK` proves
   readiness only. Completion still requires independent Kimi K3 and Opus 5
   reviews, reconciliation, four in-place Notion updates, read-back, hierarchy
   and duplicate evidence, then the strict publication gate.
2. **P2 — GitHub receipt was stale.** Accepted and corrected. The private
   repository was read back as `PRIVATE`, default branch `main`, at commit
   `d1764951eacb235326db1886117e67505abc67d6` before this corrective commit.

The reviewer found no scope creep. It confirmed fixed Wiki/process identities,
the requested ignore categories, executable one-command scripts, the four
reports, and GET-only live collection for this audit.

## Verification after dispositions

- External-evidence focused suite: `27 passed in 0.65s`.
- Snapshot and collector suite: `97 passed in 0.75s`.
- Full suite: `311 passed in 2.99s`.
- `uv run python -m compileall -q src scripts tests`: passed.
- `git diff --check`: passed.
- `uv run python verify.py`: `GATE_OK`.
