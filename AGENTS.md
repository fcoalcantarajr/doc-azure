# AGENTS.md

## Hard Rules R1..R10

R1. Azure DevOps: GET only. No POST, PATCH, PUT, DELETE against dev.azure.com, ever, in any script,
    test or ad-hoc command. The gate greps for this.
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

Each delta is a table of ROWS. Each row is one comparable claim, carrying:
| id | claim (pt-BR) | class | doc_evidence | azure_evidence |

class is exactly one of: DOC_ONLY | AZURE_ONLY | DIVERGENT | MATCH
- DOC_ONLY   = the wiki states it, the process does not implement it
- AZURE_ONLY = the process implements it, the wiki does not state it
- DIVERGENT  = both state it, and they differ (say HOW, with both values)
- MATCH      = both agree

doc_evidence   = out/wiki/<slug>.md#L<line>            (or "n/a" only when class is AZURE_ONLY)
azure_evidence = out/process/<file>.json#<json-path>   (or "n/a" only when class is DOC_ONLY)

Every non-MATCH row states the consequence in one sentence.

## The Four Slugs

- leiame     (wiki page id 35) "Leia-me Processo da Organização Única"
- politicas  (wiki page id 10) "Template de políticas explícitas"
- changelog  (wiki page id 9)  "Changelog"
- apendice   (wiki page id 37) "Apêndice Técnico Processo Organização Única"

## Gate Philosophy

Never trust a gate that only checks internal consistency.
