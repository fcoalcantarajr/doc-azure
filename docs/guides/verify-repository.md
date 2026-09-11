# Verificar o repositório

Execute a porta de verificação do projeto e obtenha `GATE_OK` quando todos os checks passarem.

## Antes de começar

**uv instalado.** O projeto usa `uv` para gerenciar dependências e executar scripts.

```bash
uv --version
```

Deve retornar algo como `uv 0.x.y`. Se não retornar, instale com:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Repositório clonado.** Verifique que o arquivo principal existe:

```bash
ls verify.py
```

Se o arquivo não existir, siga o [Quickstart](../quickstart.md) antes de continuar.

## Passo a passo

### 1. Rodar com a configuração padrão

Execute a verificação completa do repositório:

```bash
uv run python verify.py
```

**O que você deve ver:**

```
GATE_OK
```

`GATE_OK` significa que todos os 12 checks passaram: layout, gitignore, cobertura, allowlist de leitura, módulos Python, contrato documentado, literais secretos, relatórios, artefatos Notion, entrypoints de scripts e testes pytest.

**Se der errado:**

Veja a seção [Se der errado](#se-der-errado) abaixo.

### 2. Exigir recibo de publicação (`--require-publication`)

Use `--require-publication` quando precisar validar que receipts exatos do Notion existem para as quatro páginas do projeto:

```bash
uv run python verify.py --require-publication
```

**O que você deve ver:**

```
GATE_OK
```

Quando a flag está ativa, o gate também valida o manifesto de publicação em `out/notion`. Um recibo externo obsoleto pode falhar mesmo quando os testes Python passam.

**Se der errado:**

Veja a seção [Se der errado](#se-der-errado) abaixo.

### 3. Verificar saúde de clone sem snapshots

Se você tem um clone sem as gerações históricas de Wiki e processo ignoradas nomeadas nos arquivos em `deltas/`, o `verify.py` não retornará `GATE_OK`. Use pytest como verificação portátil:

```bash
uv run pytest -q
```

Todos os testes devem passar. Esse resultado **não** prova procedência de relatório ou publicação.

## Como ler o resultado

Mensagens de progresso aparecem no stderr. O resultado final aparece no stdout:

| Saída | Significado |
|-------|-------------|
| `GATE_OK` | Todos os checks passaram |
| `GATE_FAIL: <erro>` | Um check falhou — o erro descreve o motivo |

O código de saída é `0` para sucesso e `1` para falha.

## Se der errado

**`uv: command not found`**

`uv` não está instalado ou não está no PATH. Instale com o comando mostrado em [Antes de começar](#antes-de-começar).

**`GATE_FAIL: a secret environment file is tracked`**

Um arquivo `.env` ou similar foi rastreado pelo git. Remova do rastreamento (sem deletar do disco):

```bash
git rm --cached <arquivo>
```

**`GATE_FAIL: secret literal found in: <arquivo>`**

Um valor que parece segredo foi encontrado em um arquivo rastreado. Verifique se é um falso positivo ou substitua por uma referência a variável de ambiente.

**`GATE_FAIL: required files are missing: <lista>`**

Arquivos essenciais estão faltando no repositório. Verifique se o clone está completo.

**`GATE_FAIL: legacy contract files remain: <lista>`**

Arquivos legados de contrato ainda existem. Remova-os seguindo a orientação na mensagem.

**`GATE_FAIL: coverage baseline files are missing`**

Os arquivos de baseline de cobertura estão faltando em `out/`. Execute a auditoria primeiro para gerá-los.

**`GATE_FAIL: gitignore category is incomplete: <lista>`**

O `.gitignore` não cobre todas as categorias esperadas. Adicione as entradas faltantes.

**`GATE_FAIL: Notion publication manifest is stale relative to reports`**

O manifesto de publicação em `out/notion` está obsoleto em relação aos relatórios atuais. Execute `--refresh` para atualizar os relatórios, ou publique novamente no Notion.

**Resultado é `GATE_OK` no clone mas `GATE_FAIL` em outra máquina**

A porta só retorna `GATE_OK` na máquina que retenha as gerações exatas de Wiki e processo ignoradas nos arquivos atuais em `deltas/`. Em clones sem snapshots históricos, use `uv run pytest -q` como verificação portátil.

## Próximo passo

Saiba mais sobre a [visão geral do projeto](../user-guide.md).
