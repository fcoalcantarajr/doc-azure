# Códigos de saída do doc-azure

Referência de todos os códigos de saída retornados pelos scripts do doc-azure.

## `run_audit.py`

Script principal de auditoria. Executa o pipeline completo de validação.

| Código | Nome | O que significa | O que fazer |
|--------|------|-----------------|-------------|
| `0` | `CLEAN` | Todos os checks passaram. Resultado impresso: `{status}: {logical_sha256}`. Escrito em `out/audit/CURRENT`. | Nenhuma ação necessária. |
| `1` | `DELTAS` | Issues de validação delta encontradas. Resultado normal — significa que existem divergências entre wiki e processo. | Verificar relatório gerado para detalhes das divergências. |
| `2` | `COVERAGE_GAP` | Gaps de cobertura documental encontrados. | Revisar `out/delta/document_coverage.json` para identificar itens faltantes. |
| `3` | `ACQUISITION_VALIDATION_FAILED` | Falha na validação de aquisição. | Verificar logs de coleta (`out/wiki/`, `out/process/`) para identificar a falha. |
| `4` | `INTERNAL_ERROR` | Erro interno ou exceção não tratada. Mensagem impressa: `RUN_OUTPUT_FAILED: {type(error).__name__}`. | Verificar traceback. Se `SettingsError`, checar variáveis de ambiente (principalmente `AZDO_PAT`). |

Referência: `scripts/run_audit.py:39`, `scripts/run_audit.py:37`

## `verify.py`

Verificação de provenance do relatório. Valida integridade e versão dos artefatos.

| Código | Nome | O que significa | O que fazer |
|--------|------|-----------------|-------------|
| `0` | `GATE_OK` | Provenance verificado com sucesso. | Nenhuma ação necessária. |
| `1` | `GATE_FAIL` | Falha na verificação de provenance. Mensagem impressa: `GATE_FAIL: {error}`. | Verificar se `_VOLATILE_PROVENANCE_LINES` ou `_REPORT_PROVENANCE_LINE` foram alterados. Reexecutar `run_audit.py` antes de tentar novamente. |

Referência: `verify.py:630-633`

## Scripts auxiliares

| Script | Sucesso | Falha | Observação |
|--------|---------|-------|------------|
| `01_fetch_wiki.py` | `0` | `1` | Mensagens de erro: `ERROR: cached wiki snapshot failed validation`, `ERROR: wiki collection failed safely` |
| `02_fetch_process.py` | `0` | `1` | |
| `03_build_delta.py` | `0` | `1` | Mensagem de erro: `BUILD_FAILED: {error}` |
| `04_prepare_notion.py` | `0` | `1` | Mensagem de erro: `NOTION_PREPARATION_FAILED: {error}` |
| `setup.py` | `0` | `1` | |
| `prepare_baselines.py` | `0` | — | Sempre retorna 0 |

## Notas

- `DELTAS` (código `1` do `run_audit.py`) **não é falha** — é o resultado esperado quando existem divergências entre documentação e processo. É o estado mais comum de trabalho.
- Todos os scripts seguem o padrão `uv run python scripts/<nome>.py`.
- Para refazer qualquer etapa com cache limpo, usar a flag `--refresh`.
