# Rodar a auditoria

Execute a auditoria completa do projeto e obtenha um relatório com o status de cada afirmação do catálogo frente às fontes documentais e de processo.

## Antes de começar

**uv instalado.** O projeto usa `uv` para gerenciar dependências e executar scripts.

```bash
uv --version
```

Deve retornar algo como `uv 0.x.y`. Se não retornar, instale com:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Repositório clonado e configurado.** Verifique que o catálogo de tarefas existe:

```bash
ls out/catalog/tasksCatalog.json
```

Se o arquivo não existir, siga o [Quickstart](../quickstart.md) antes de continuar.

## Passo a passo

### 1. Rodar com a configuração padrão

O modo padrão reaproveita a última coleta armazenada na cache. Se a cache não existe, baixa tudo. Se está incompleta, obtém apenas os dados que faltam.

```bash
uv run python scripts/run_audit.py
```

**O que você deve ver:**

Na primeira execução, o script baixa fontes do Azure DevOps — pode levar alguns minutos. Ao final:

```
DELTAS: <hash de 64 caracteres>
/Volumes/.../doc-azure/out/audit/CURRENT
```

`DELTAS` é o resultado normal quando a auditoria encontra diferenças. **Não é uma falha de execução.**

Em execuções seguintes, se a cache estiver completa, o script pula a rede e processa direto.

**Se der errado:**

Veja a seção [Se der errado](#se-der-errado) abaixo.

### 2. Atualizar fontes e rodar (`--refresh`)

Use `--refresh` para forçar nova coleta por REST, mesmo que a cache exista.

```bash
uv run python scripts/run_audit.py --refresh
```

**O que você deve ver:**

Saída idêntica ao modo padrão:

```
DELTAS: <hash de 64 caracteres>
/Volumes/.../doc-azure/out/audit/CURRENT
```

Útil quando as fontes podem ter mudado — por exemplo, após novas edições no Azure DevOps.

**Se der errado:**

Veja a seção [Se der errado](#se-der-errado) abaixo.

### 3. Rodar offline (`--offline`)

Use `--offline` quando não houver conexão ou quando quiser trabalhar apenas com snapshots locais já baixados.

```bash
uv run python scripts/run_audit.py --offline
```

**O que você deve ver:**

```
DELTAS: <hash de 64 caracteres>
/Volumes/.../doc-azure/out/audit/CURRENT
```

Se a cache não existir, o script falha. Veja [Se der errado](#se-der-errado).

> **Importante:** `--offline` e `--refresh` não podem ser usados juntos. O script rejeita a combinação.

**Se der errado:**

Veja a seção [Se der errado](#se-der-errado) abaixo.

### 4. Flags avançadas

As flags abaixo não são necessárias no uso diário. São úteis para testes ou quando o projeto está em diretório diferente.

| Flag | Descrição | Padrão |
|------|-----------|--------|
| `--root <caminho>` | Diretório raiz do projeto | `PROJECT_ROOT` |
| `--catalog <caminho>` | Caminho para o catálogo | `out/catalog/tasksCatalog.json` |
| `--document-baseline <caminho>` | Baseline documental | `out/document-snapshot/processed_lfs/current_baseline` |
| `--process-baseline <caminho>` | Baseline de processo | `out/process-snapshot/processed_lfs/current_baseline` |

Exemplo:

```bash
uv run python scripts/run_audit.py --root /outro/diretorio --refresh
```

## Como ler o resultado

Após a execução, abra o relatório:

```bash
cat out/audit/CURRENT
```

Na seção `summary`, procure por:

```json
{
  "total_claims": N,
  "confirmed": X,
  "divergent": Y,
  "unchecked": Z
}
```

- **confirmed** — afirmações confirmadas entre documentação e processo.
- **divergent** — diferenças encontradas entre documentação e processo.
- **unchecked** — afirmações não verificáveis pela API.

Cada linha de divergência aponta evidência exata em `out/` e no wiki.

Mensagens de progresso aparecem no stderr. O stdout retorna apenas o resultado final (`status: hash` + caminho do relatório).

## Se der errado

**`uv: command not found`**

`uv` não está instalado ou não está no PATH. Instale com o comando mostrado em [Antes de começar](#antes-de-começar).

**`RUN_OUTPUT_FAILED: FileNotFoundError`** (stderr, código 4)

Arquivo de entrada não encontrado. Verifique que `out/catalog/tasksCatalog.json` existe e que `--root` aponta para o diretório correto.

**Falha com `--offline` sem cache**

Se a cache não existir, `--offline` não tem dados para processar. Execute primeiro com o modo padrão (sem flags) ou com `--refresh` para criar a cache.

**`DELTAS` na saída (código 1)**

`DELTAS` **não é erro**. Significa que a auditoria encontrou diferenças entre as fontes — resultado esperado quando há divergências legítimas.

**Código de saída diferente de 0 ou 1**

| Código | Significado |
|--------|-------------|
| 0 | `CLEAN` — sem divergências |
| 1 | `DELTAS` — divergências registradas (normal) |
| 2 | `COVERAGE_GAP` — cobertura incompleta |
| 3 | `ACQUISITION_VALIDATION_FAILED` — falha na validação de aquisição |
| 4 | `INTERNAL_ERROR` — erro interno do script |

Códigos 2, 3 e 4 indicam problemas que precisam de atenção.

Para confirmar flags a qualquer momento:

```bash
uv run python scripts/run_audit.py --help
```

## Próximo passo

Saiba mais sobre a [visão geral do projeto](../user-guide.md).
