# AGENTS.md

## Hard Rules R1..R10

R1. Azure DevOps is semantically read-only. GET is allowed only for the approved wiki, process,
    and work-item read routes. POST is allowed only for the exact WIQL and work-items-batch query
    routes. Creation POST, PUT, PATCH, DELETE, redirects, absolute URLs, and method override are
    forbidden. The gate imports and exercises the method-route allowlist.
R2. No secret in any artifact, log, commit, test fixture, Notion page or docs file.
R3. Nothing enters a deliverable without evidence. Every delta row carries an evidence pointer to a
    file under out/ that exists. No pointer, no row.
R4. Tests before implementation. A pytest test must fail for the right reason before the code that
    makes it pass is written. Record the RED output line in docs/decisions.md.
R5. Every script runs standalone with ONE command: uv run python scripts/<name>.py
    Idempotent: re-running with cache present must not re-fetch and must not change output bytes.
    Refetch only with an explicit --refresh flag.
R6. No prose-only Python module. If a .py file has no executable behavior, it must not exist.
    Prose goes in docs/*.md.
R7. Python 3.11+, uv, asyncio-first with a single httpx.AsyncClient, one asyncio.run per script,
    Semaphore to cap concurrency, retry only {408,429,500,502,503,504}, honor Retry-After,
    never retry 401/403.
R8. Conventional Commits, atomic, one logical change per commit. Use the git-commit skill.
    Never git push --force, never --no-verify, never rebase, never amend a pushed commit.
    Never commit .env or anything under out/.
R9. If a check is inconvenient, you prove it wrong with an official-doc URL and @oracle signs off in
    docs/decisions.md. You never delete, soften or comment out a check to make the gate pass.
R10. Language: English in code, tests, commits and agent reasoning. Brazilian Portuguese in
     README.md, the four Notion delta pages, deltas/, and the operational documentation:
     docs/README.md, docs/quickstart.md, docs/configuration.md, docs/audit-runtime.md,
     docs/notion-publication.md, docs/troubleshooting.md, docs/guides/,
     docs/reference/exit-codes.md and docs/reference/notion-evidence.md. English in the maintainer
     and historical documentation: docs/architecture.md, docs/document-coverage.md,
     docs/decisions.md, docs/archive/, docs/superpowers/, docs/reference/api-contract.md and
     docs/reference/delta-method.md. A new documentation file follows its audience: operator-facing
     material is Brazilian Portuguese; maintainer or historical material is English. If the audience
     is not unambiguous from these directory rules, update R10 to classify the path before adding it.

## Adversarial review workflow

For material changes to CLI behavior, evidence or baseline provenance, security boundaries,
publication gates, or user-facing contracts, run a hostile read-only review with OpenCode using
oh-my-opencode-slim and the `9router` preset when available. Start OpenCode from the exact project
checkout being reviewed; do not reuse a session whose working directory points to another project.
Bind the request to `https://github.com/fcoalcantarajr/doc-azure`, the base and head SHAs when
available, and the complete working-tree diff. Ask for standards and specification findings with
file and line references. The reviewer must not edit files, run external API calls, or publish.

Treat failed delegated reviewers, provider errors, and unavailable credits as missing review
coverage, not as clean findings. Report an orchestrator-only pass as such; do not call it an
independent specialist review. Do not buy credits or silently change the model or preset. Re-review
the final diff after any accepted correction.

This code/document review is separate from the Notion publication gate. It does not replace the
Kimi K3 and Opus 5 receipts required by the current Notion publication contract in
`docs/notion-publication.md`.

## Delta Model

Each report row evaluates one explicit, versioned catalog claim. The status is
exactly one of:

- CONFIRMADO: the exact documented value and current process evidence agree.
- DIVERGENTE: both sides are comparable and their exact values differ.
- NAO_VERIFICAVEL_API_PROCESSO: the process API cannot prove the documentary
  dimension, such as chronology, runtime automation, governance, or practice.
- AMBIGUO: the collected evidence supports more than one material interpretation.

Every row requires an exact `out/wiki/<slug>.md#L<line>` documentary pointer.
CONFIRMADO and DIVERGENTE also require an exact
`out/process/<artifact>.json#<json-pointer>` pointer. A non-confirmed row states
its impact or epistemic limit explicitly. Report order follows catalog order;
heuristic keyword extraction and filler rows are forbidden.

Every real Azure HTTP attempt is recorded in the snapshot manifest as a
sanitized method and path. An absence conclusion is valid only when the
collector completed the relevant endpoint family and the exact returned
artifact proves the absence.

## The Four Slugs

- leiame     (wiki page id 35) "Leia-me Processo da Organização Única"
- politicas  (wiki page id 10) "Template de políticas explícitas"
- changelog  (wiki page id 9)  "Changelog"
- apendice   (wiki page id 37) "Apêndice Técnico Processo Organização Única"

## Gate Philosophy

Never trust a gate that only checks internal consistency.
