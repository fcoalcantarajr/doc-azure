# Executar a auditoria

Compare as quatro páginas fixas da Wiki com o `Processo-Agil` do Azure DevOps. O aplicativo faz somente requisições REST de leitura e grava evidências locais.

## Antes de começar

Conclua o [início rápido](../quickstart.md). Para uma coleta nova, confirme que `.env` contém um PAT válido e que sua conta tem os acessos da [lista de verificação](../configuration.md#lista-de-verificação-de-acesso).

Confirme que o catálogo versionado existe:

```sh
ls config/wiki_claims.json
```

Resultado esperado: o terminal mostra `config/wiki_claims.json`.

## Escolher o modo

Use somente um destes comandos:

| Necessidade | Comando |
| --- | --- |
| Coletar o estado atual do Azure | `uv run python scripts/run_audit.py --refresh` |
| Reusar snapshots locais completos, sem rede | `uv run python scripts/run_audit.py --offline` |
| Reusar a cache e buscar somente o que faltar | `uv run python scripts/run_audit.py` |

Para a primeira auditoria ou quando as fontes podem ter mudado, use:

```sh
uv run python scripts/run_audit.py --refresh
```

Uma execução concluída imprime duas linhas semelhantes a estas:

```text
DELTAS: <hash de 64 caracteres>
<caminho do projeto>/out/audit/CURRENT
```

O código do shell pode ser `0`, `1`, `2` ou `3`; cada um é um resultado classificado. O código `4` significa que o bundle final não pôde ser produzido.

`--offline` e `--refresh` são incompatíveis. Se não houver snapshots locais completos, o modo offline termina com `ACQUISITION_VALIDATION_FAILED`.

## Como ler o resultado

`out/audit/CURRENT` contém apenas o identificador da geração atual. Resolva o diretório dessa geração com:

```sh
uv run python -c "from pathlib import Path; p=Path('out/audit'); print(p/'snapshots'/(p/'CURRENT').read_text().strip())"
```

Resultado esperado: um caminho como `out/audit/snapshots/<identificador>`.

Nesse diretório, leia:

- `global.md`: status global, quantidade de reivindicações, lacunas e hash lógico;
- `leiame.md`, `politicas.md`, `changelog.md` e `apendice.md`: achados por página;
- `run.json`: recibo estruturado da execução.

No `run.json`, os campos principais são `status`, `exit_code`, `coverage_complete`, `pages`, `findings`, `gaps`, `logical_sha256` e `provenance`. `findings` e `gaps` são listas; não existe um objeto `summary`.

| Código | Status | Interpretação |
| --- | --- | --- |
| `0` | `CLEAN` | Cobertura completa e todas as reivindicações confirmadas. |
| `1` | `DELTAS` | Auditoria concluída com pelo menos um achado diferente de `CONFIRMADO`. É um resultado válido. |
| `2` | `COVERAGE_GAP` | A fonte mudou fora da cobertura revisada. Interrompa a publicação. |
| `3` | `ACQUISITION_VALIDATION_FAILED` | A coleta ou validação de snapshots não foi concluída. |
| `4` | `INTERNAL_ERROR` | A aplicação não conseguiu gravar o resultado final. |

Consulte a [referência de códigos de saída](../reference/exit-codes.md) para as ações de recuperação.

## Opções avançadas

As opções substituem estes padrões:

| Opção | Padrão |
| --- | --- |
| `--root` | raiz detectada do repositório |
| `--catalog` | `config/wiki_claims.json` |
| `--document-baseline` | `config/document-coverage.json` |
| `--process-baseline` | `config/process-coverage.json` |

Veja a ajuda exata da versão instalada:

```sh
uv run python scripts/run_audit.py --help
```

Resultado esperado: a lista de opções termina sem erro.

## Se der errado

- `uv: command not found`: instale o `uv` conforme o [início rápido](../quickstart.md).
- `RUN_OUTPUT_FAILED: FileNotFoundError`: confirme os três arquivos em `config/` listados acima e o valor de `--root`.
- `ACQUISITION_VALIDATION_FAILED` numa coleta nova: siga o diagnóstico de PAT, acesso e rede em [Solução de problemas](../troubleshooting.md#auditoria-nova-termina-com-acquisition_validation_failed).
- `COVERAGE_GAP`: não regenere a baseline para silenciar a diferença; encaminhe a mudança para revisão de catálogo e cobertura.

## Próximo passo

Para reconstruir os relatórios versionados, siga [Gerar os relatórios delta](build-reports.md).
