# Notion Publication

Publication status for the four delta pages comparing Azure DevOps wiki pages against Processo-Agil implementation.

| slug | notion_url | created | updated |
|------|-----------|---------|---------|
| leiame | pending | - | - |
| politicas | pending | - | - |
| changelog | pending | - | - |
| apendice | pending | - | - |

## Notes

- Parent page: https://app.notion.com/p/2a1412e08c26803ba988dc619a396e45 (page id: 2a1412e0-8c26-803b-a988-dc619a396e45, title: "Azure")
- Page titles in Notion:
  - "Delta — Leia-me Processo da Organização Única × Processo-Agil implementado"
  - "Delta — Template de Políticas Explícitas × Processo-Agil implementado"
  - "Delta — Changelog × Processo-Agil implementado"
  - "Delta — Apêndice Técnico × Processo Organização Única × Processo-Agil implementado"

## Publication Process

1. Use Notion MCP `create_pages` or `update_page` under parent page id `2a1412e0-8c26-803b-a988-dc619a396e45`
2. Each page contains a `DELTA-AUDIT-MARKER-<slug>` marker line
3. Full content is the corresponding deltas/<slug>.md file
4. Metadata (created/updated) captured from Notion API response

Status: **Pending** - awaiting STEP 9 Notion MCP publication.