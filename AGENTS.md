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
R10. Language: English in all code, tests, commits, docs/ and reasoning. The four Notion delta
     pages and the delta markdown files are in Brazilian Portuguese, because the audience is
     Portuguese-speaking and the wiki and the process are in Portuguese.

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
