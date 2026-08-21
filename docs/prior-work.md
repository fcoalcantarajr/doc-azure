# Prior Work — Session 1

Source: sessions/session-1.md (read-only evidence, NOT a source of truth)

| item | done_on_disk | claim_only | missing |
|------|--------------|------------|---------|
| AGENTS.md | yes | - | - |
| .gitignore hardened | yes | - | - |
| src/doc_azure/settings.py | yes (existing) | - | - |
| src/doc_azure/azure_client.py | yes (existing) | - | - |
| tests/test_settings.py | yes (existing) | - | - |
| tests/test_azure_client.py | yes (existing) | - | - |
| docs/api-contract.md | yes (this run) | - | - |
| docs/prior-work.md | yes (this run) | - | - |
| docs/README.md | no | - | write under 200 lines |
| docs/delta-method.md | no | - | describe delta generation algorithm |
| docs/decisions.md | no | - | record rejected alternatives |
| docs/notion-publication.md | no | - | after STEP 9 |
| verify.py | no | - | write with C1-C14 |
| scripts/01_fetch_wiki.py | no | - | GET-only wiki fetcher |
| scripts/02_fetch_process.py | no | - | GET-only process fetcher |
| scripts/03_build_delta.py | no | - | delta builder from out/ |
| scripts/04_publish_notion.py | no | - | Notion publisher (REST API or absent) |
| src/delta/__init__.py | no | - | pure classify/render functions |
| tests/test_classify.py | no | - | pytest, pure |
| tests/test_render.py | no | - | pytest, pure |
| tests/test_evidence.py | no | - | pytest, pure |
| tests/fixtures/ | no | - | hand-made small fixtures |
| deltas/leiame.md | no | - | produced by 03_build_delta |
| deltas/politicas.md | no | - | produced by 03_build_delta |
| deltas/changelog.md | no | - | produced by 03_build_delta |
| deltas/apendice.md | no | - | produced by 03_build_delta |
| Notion publication | no | - | after STEP 9 |
| out/ cache | no (empty) | - | populated by scripts/01 and /02 |