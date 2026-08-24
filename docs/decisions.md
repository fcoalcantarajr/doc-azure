# Decisions

## Alternativa descartada: 01_fetch_wiki.py

Direct API calls without caching — rejected because AGENTS.md R5 requires idempotency.

## Alternativa descartada: 02_fetch_process.py

Hardcoded processTypeId — rejected because AGENTS.md requires runtime discovery.

## Alternativa descartada: 03_build_delta.py

LLM-based classification — rejected because AGENTS.md requires deterministic, evidence-based classification.

## Alternativa descartada: 04_publish_notion.py

webfetch on notion.so — rejected because Notion MCP must be used per mission spec.

## Task 1 — RED evidence

Command: `uv run pytest tests/test_delta_models.py tests/test_delta_evidence.py -q`

Result: collection failed as expected before implementation: `ModuleNotFoundError: No module named 'delta.models'` and `ModuleNotFoundError: No module named 'delta.evidence'` (2 collection errors).

## Task 1 — GREEN evidence

Focused command: `uv run pytest tests/test_delta_models.py tests/test_delta_evidence.py -q`

Result: `11 passed in 0.07s` with no warnings.

Full command: `uv run pytest -q`

Result: `58 passed, 17 subtests passed in 0.59s`.
