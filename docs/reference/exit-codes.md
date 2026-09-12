# Códigos de saída do doc-azure

Use esta referência depois de executar um comando. A mensagem exata continua sendo a melhor pista para diagnóstico.

## Auditoria principal

`uv run python scripts/run_audit.py [--refresh | --offline]`

| Código | Status | Significado | Próxima ação |
| --- | --- | --- | --- |
| `0` | `CLEAN` | Cobertura completa; todas as reivindicações foram confirmadas. | Leia o bundle atual e prossiga. |
| `1` | `DELTAS` | Cobertura completa; existe pelo menos um achado diferente de `CONFIRMADO`. | Leia `global.md` e os relatórios da geração atual. Não trate como falha do programa. |
| `2` | `COVERAGE_GAP` | O texto documental ou inventário de processo divergiu da baseline revisada. | Abra `run.json` da geração atual e examine `gaps`. Interrompa a publicação. |
| `3` | `ACQUISITION_VALIDATION_FAILED` | A coleta ou validação das fontes não produziu snapshots completos. | Verifique PAT, acesso, rede e manifests em `out/wiki` e `out/process`. |
| `4` | `INTERNAL_ERROR` | Uma exceção impediu a gravação do bundle final. | Use o tipo em `RUN_OUTPUT_FAILED: <tipo>` e a [solução de problemas](../troubleshooting.md). |

`out/audit/CURRENT` contém o ID da geração, não o relatório. Resolva o diretório e leia `run.json` conforme [Como ler o resultado](../guides/run-audit.md#como-ler-o-resultado).

## Porta do repositório

`uv run python verify.py [--require-publication]`

| Código | Saída | Significado |
| --- | --- | --- |
| `0` | `GATE_OK` | Todos os invariáveis exigidos pelo modo escolhido passaram. |
| `1` | `GATE_FAIL: <mensagem>` | O primeiro invariável indicado falhou. |

Não altere expressões internas nem regenere evidência para silenciar a falha. Siga a mensagem e o [guia da porta](../guides/verify-repository.md).

## Scripts auxiliares

| Script | Sucesso | Falha conhecida |
| --- | --- | --- |
| `01_fetch_wiki.py` | `0` | `1` |
| `02_fetch_process.py` | `0` | `1` |
| `03_build_delta.py` | `0` | `1`, com `BUILD_FAILED: <mensagem>` para falhas tratadas |
| `04_prepare_notion.py` | `0` | `1`, com `NOTION_PREPARATION_FAILED: <mensagem>` |
| `setup.py` | `0` | `1` |
| `prepare_baselines.py` | `0` quando conclui | outro código ou traceback se a execução não concluir |

`--refresh` pertence à coleta. Ele cria uma geração imutável nova e não apaga cache, não recria evidência histórica e não corrige automaticamente relatórios ou recibos.
