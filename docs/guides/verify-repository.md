# Verificar o repositório

Execute a porta de verificação completa do repositório. Esta porta valida a integridade do código, dos arquivos de configuração e dos relatórios — sem modificar nada.

## Antes de começar

**uv instalado.** O projeto usa `uv` para gerenciar dependências.

```bash
uv --version
```

Deve retornar algo como `uv 0.x.y`. Se não retornar, instale com:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Repositório clonado.** Verifique que o arquivo de configuração do catálogo existe:

```bash
ls config/wiki_claims.json
```

Se o arquivo não existir, siga o [Quickstart](../quickstart.md) antes de continuar.

**Testes passando.** A porta executa o suite de testes. Verifique que os testes passam:

```bash
uv run pytest -q
```

Deve retornar algo como `X passed` sem erros.

## Passo a passo

### 1. Rodar a porta sem opções

O modo padrão valida 11 invariantes do repositório: layout, gitignore, cobertura, allowlist Azure, módulos Python, contrato documentado, segredos, relatórios, artefatos Notion, entrypoints de scripts e suite de testes.

```bash
uv run python verify.py
```

**O que você deve ver:**

```
GATE_OK
```

Esta é a única mensagem de sucesso. Se todos os 11 checks passarem, o script imprime `GATE_OK` e retorna código 0.

> **Importante:** Esta é uma porta de procedência para mantenedores, não uma verificação de clone limpo. Só pode retornar `GATE_OK` em uma máquina que retenha as gerações exatas de Wiki e processo ignoradas nomeadas nos arquivos atuais em `deltas/`. Um `--refresh` novo cria novas gerações e não restaura aquela evidência histórica.

### 2. Rodar com exigência de publicação (`--require-publication`)

Use `--require-publication` para exigir recibos exatos obtidos pelo conector para as quatro páginas do Notion. Este modo é útil antes de publicar ou verificar se a publicação está íntegra.

```bash
uv run python verify.py --require-publication
```

**O que você deve ver:**

```
GATE_OK
```

Se não houver recibos de publicação ou o manifesto estiver desatualizado, a porta falha com `GATE_FAIL` e código 1.

## Como ler o resultado

O script retorna exatamente dois resultados:

| Saída | Código | Significado |
|-------|--------|-------------|
| `GATE_OK` | 0 | Todos os 11 checks passaram |
| `GATE_FAIL: <erro>` | 1 | Um ou mais checks falharam |

A mensagem de erro aparece no **stderr**, não no stdout. Se você redirecionar a saída, verifique também o stderr.

Os 11 checks executados em ordem:

1. **verify_layout** — arquivos obrigatórios existem
2. **verify_gitignore** — padrões de ignorados estão completos
3. **verify_coverage_baselines** — baselines de cobertura são válidos
4. **verify_read_allowlist** — tabela de operações Azure está correta
5. **verify_python_modules** — módulos Python não têm erros de sintaxe nem são apenas prosa
6. **verify_documented_contract** — modelo de status está em AGENTS.md e delta-method.md
7. **verify_secret_literals** — valores de `.env` não estão em arquivos rastreados
8. **verify_reports** — relatórios em `deltas/` são idênticos à reconstrução verificada
9. **verify_notion_artifacts** — manifesto de publicação e recibos estão consistentes
10. **verify_script_entrypoints** — todos os scripts aceitam `--help`
11. **Suite de testes** — `uv run pytest -q` passa

## Se der errado

**`uv: command not found`**

`uv` não está instalado ou não está no PATH. Instale com o comando mostrado em [Antes de começar](#antes-de-começar).

**`GATE_FAIL: required files are missing: <lista>`**

Arquivos obrigatórios do repositório não existem ou estão vazios. Verifique que o repositório está clonado completo e que nenhum arquivo foi removido manualmente.

**`GATE_FAIL: legacy contract files remain: <lista>`**

Arquivos legados que deveriam ter sido removidos ainda existem. Exclua os arquivos listados.

**`GATE_FAIL: gitignore category is incomplete: <categoria>`**

O `.gitignore` não contém padrões para todas as categorias exigidas. Adicione os padrões que faltam para a categoria indicada.

**`GATE_FAIL: coverage baseline files are missing`**

Os arquivos `config/wiki_claims.json`, `config/document-coverage.json` ou `config/process-coverage.json` não existem. Execute o setup do projeto primeiro.

**`GATE_FAIL: a secret environment file is tracked`**

O arquivo `.env` ou um arquivo `.env.*` (exceto `.env.example`) está rastreado pelo Git. Remova-o do rastreamento:

```bash
git rm --cached .env
```

**`GATE_FAIL: secret literal found in: <caminhos>`**

Um valor sensível do `.env` foi encontrado em arquivos rastreados. Verifique os arquivos listados e remova os valores secretos.

**`GATE_FAIL: Python module is unreadable or invalid: <caminho>`**

Um arquivo `.py` em `src/` ou `scripts/` tem erro de sintaxe ou encoding. Corrija o arquivo indicado.

**`GATE_FAIL: prose-only Python module: <caminho>`**

Um arquivo `.py` contém apenas uma docstring sem código executável. Remova o arquivo ou adicione código executável.

**`GATE_FAIL: documented status is missing: <status>`**

O modelo de status (CONFIRMADO, DIVERGENTE, NAO_VERIFICAVEL_API_PROCESSO ou AMBIGUO) não está documentado em `AGENTS.md` ou `docs/delta-method.md`. Adicione a documentação que falta.

**`GATE_FAIL: retired heuristic status remains: <status>`**

Um status antigo (DOC_ONLY, AZURE_ONLY ou MATCH) ainda está documentado. Remova as referências ao status aposentado.

**`GATE_FAIL: deltas/<arquivo> differs from verified rebuild`**

O relatório em `deltas/` não corresponde à reconstrução verificada. Execute `--refresh` para gerar novos relatórios, ou verifique se o arquivo foi modificado manualmente.

**`GATE_FAIL: Notion publication manifest is stale relative to reports`**

O manifesto de publicação em `out/notion/publication-manifest.json` não corresponde aos relatórios atuais. Execute `04_prepare_notion.py` para atualizar.

**`GATE_FAIL: verified Notion fetched receipts are missing`** (com `--require-publication`)

Os recibos de leitura do Notion não existem em `out/notion/fetched/`. Publique as páginas primeiro ou execute sem `--require-publication`.

**`GATE_FAIL: subprocess 'uv' failed with exit code <código>`**

Um subprocesso falhou. Verifique se `uv` está instalado e se o repositório está configurado corretamente.

**Código de saída diferente de 0 ou 1**

O script `verify.py` só retorna 0 (sucesso) ou 1 (falha). Se outro código aparecer, pode ser erro do interpretador Python — verifique se Python 3.11+ está instalado.

## Próximo passo

Saiba mais sobre a [visão geral do projeto](../README.md) ou consulte o [guia de saída de códigos](../reference/exit-codes.md).
