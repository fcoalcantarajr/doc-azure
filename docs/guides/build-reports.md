# Gerar os relatórios delta

Monte os quatro relatórios Markdown com as conclusões da auditoria a partir dos snapshots locais já verificados. O script é 100 % offline — não acessa a rede, não precisa de token.

## Antes de começar

**uv instalado.**

```bash
uv --version
```

Deve retornar algo como `uv 0.x.y`. Se não retornar, instale com:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Snapshots locais existem.** Verifique que os snapshots wiki e de processo foram coletados:

```bash
ls out/wiki/snapshots/
ls out/process/snapshots/
```

Ambos os diretórios devem conter pelo menos uma pasta de geração (ex.: `20250825T120000Z/`). Se estiverem vazios, execute primeiro os passos de coleta descritos em [Rodar a auditoria](run-audit.md).

**Catálogo de afirmações existe.**

```bash
ls config/wiki_claims.json
```

Se o arquivo não existir, consulte a [configuração](../configuration.md) antes de continuar.

## Passo a passo

### 1. Rodar com a configuração padrão

Use a configuração padrão quando quiser gerar os relatórios a partir do catálogo e dos snapshots existentes, sem restrições de cobertura documental.

```bash
uv run python scripts/03_build_delta.py
```

**O que você deve ver:**

Saída no stdout com um caminho por linha, um para cada relatório:

```
/Volumes/.../doc-azure/deltas/leiame.md
/Volumes/.../doc-azure/deltas/changelog.md
/Volumes/.../doc-azure/deltas/politicas.md
/Volumes/.../doc-azure/deltas/apendice.md
```

Código de saída: `0`.

Cada arquivo gerado contém a tabela completa de afirmações avaliadas para o slug correspondente, com status (CONFIRMADO, DIVERGENTE, NAO_VERIFICAVEL_API_PROCESSO ou AMBIGUO), ponteiros de evidência em `out/wiki/` e `out/process/`, e a proveniência dos snapshots.

### 2. Rodar com baseline de cobertura

Use `--coverage-baseline` quando quiser que o script rejeite qualquer alteração documental não mapeada na baseline. Essa é a invocação recomendada para auditorias oficiais.

```bash
uv run python scripts/03_build_delta.py --coverage-baseline config/document-coverage.json
```

**O que você deve ver:**

Mesma saída do modo padrão:

```
/Volumes/.../doc-azure/deltas/leiame.md
/Volumes/.../doc-azure/deltas/changelog.md
/Volumes/.../doc-azure/deltas/politicas.md
/Volumes/.../doc-azure/deltas/apendice.md
```

Código de saída: `0`.

Se houver alterações documentais não mapeadas na baseline, o script falha antes de gerar os relatóveis. Veja [Se der errado](#se-der-errado).

**Se der errado:**

Veja a seção [Se der errado](#se-der-errado) abaixo.

### 3. Flags avançadas

As flags abaixo não são necessárias no uso diário. São úteis para testes ou quando o projeto está em diretório diferente.

| Flag | Descrição | Padrão |
|------|-----------|--------|
| `--evidence-root <caminho>` | Raiz contendo os snapshots em `out/wiki` e `out/process` | `PROJECT_ROOT` |
| `--catalog <caminho>` | Caminho para o catálogo de afirmações | `config/wiki_claims.json` |
| `--coverage-baseline <caminho>` | Baseline documental revisada; rejeita alterações não mapeadas | (nenhum) |
| `--output-dir <caminho>` | Diretório que recebe os quatro relatórios Markdown | `deltas/` |

Exemplo com todas as flags:

```bash
uv run python scripts/03_build_delta.py \
  --evidence-root /outro/caminho \
  --catalog config/wiki_claims.json \
  --coverage-baseline config/document-coverage.json \
  --output-dir /outro/caminho/deltas
```

> **Atenção:** `--coverage-baseline` é opcional. Sem ele, o script aceita qualquer alteração documental sem reclamar. Com ele, qualquer slug com alteração não mapeada gera erro imediato.

## Como ler o resultado

### Arquivos gerados

Cada relatório é um arquivo Markdown independente em `deltas/`:

| Arquivo | Slug | Conteúdo |
|---------|------|----------|
| `leiame.md` | leiame | Afirmações do Leia-me do Processo da Organização Única |
| `changelog.md` | changelog | Afirmações do Changelog |
| `politicas.md` | politicas | Afirmações do Template de Políticas Explícitas |
| `apendice.md` | apendice | Afirmações do Apêndice Técnico |

### Estrutura de cada relatório

Cada relatório contém:

1. **Cabeçalho de proveniência** — identificação do processo, geração dos snapshots, data da coleta.
2. **Tabela de afirmações** — cada linha avalia uma afirmação explícita do catálogo.
3. **Status** — exatamente um dos quatro valores:
   - **CONFIRMADO** — valor documentado e evidência de processo concordam.
   - **DIVERGENTE** — valores comparáveis mas diferentes.
   - **NAO_VERIFICAVEL_API_PROCESSO** — a API de processo não consegue provar a dimensão documental (cronologia, automação, governança, prática).
   - **AMBIGUO** — evidência coletada admite mais de uma interpretação material.
4. **Ponteiros de evidência** — cada linha aponta para arquivos exatos em `out/wiki/<slug>.md#L<linha>` e `out/process/<artifact>.json#<json-pointer>`.

### Verificar a integridade dos relatórios

Confirme que os arquivos foram escritos corretamente:

```bash
ls -la deltas/*.md
```

Cada arquivo deve ter tamanho maior que zero e permissão de leitura.

### Publicar no Notion

Para publicar os relatórios gerados no Notion, consulte a [preparação para o Notion](publish-notion.md).

## Se der errado

**`BUILD_FAILED: UNMAPPED_DOC_CHANGE: <slugs>`**

O `--coverage-baseline` foi informado e existem alterações documentais em slugs não mapeados na baseline. Para resolver: atualize `config/document-coverage.json` com os slugs afetados, ou remova `--coverage-baseline` se quiser ignorar a verificação.

**`BUILD_FAILED: catalog validation failed: <erro>`**

O catálogo em `config/wiki_claims.json` contém erros de estrutura. Verifique que o arquivo é JSON válido e segue o formato esperado. Consulte a [configuração](../configuration.md).

**`BUILD_FAILED: catalog must contain exactly the four fixed pages`**

O catálogo não contém afirmações para os quatro slugs obrigatórios: `leiame`, `changelog`, `politicas`, `apendice`. Verifique que `config/wiki_claims.json` inclui todos eles.

**`BUILD_FAILED: claim evaluation failed: <erro>`**

Falha ao avaliar uma ou mais afirmações. Geralmente causada por snapshots malformados ou campos obrigatórios ausentes. Verifique que os snapshots em `out/wiki/` e `out/process/` foram coletados por completo.

**`BUILD_FAILED: snapshot generation changed during report build`**

Os snapshots foram modificados durante a execução do script. Execute novamente — o script deve rodar em ambiente onde ninguém altera `out/` simultaneamente.

**`BUILD_FAILED: snapshot provenance is malformed or incomplete`**

Os metadados de proveniência dos snapshots estão corrompidos ou incompletos. Verifique que `out/wiki/snapshots/` e `out/process/snapshots/` contêm `manifest.json` válido.

**`BUILD_FAILED: report output directory must not be a symlink`**

`deltas/` é um link simbólico. Remova o link e crie um diretório real.

**`BUILD_FAILED: report output directory is unavailable`**

O diretório `deltas/` não pôde ser criado. Verifique permissões de escrita no diretório pai.

**`BUILD_FAILED: report output directory must be a real directory`**

Após criação, `deltas/` não é um diretório real (pode ter sido substituído por um arquivo ou link). Remova o obstáculo e execute novamente.

**`BUILD_FAILED: existing report must be a regular file: <nome>`**

Um dos relatórios existentes em `deltas/` não é um arquivo regular (ex.: é um diretório ou link). Remova o obstáculo e execute novamente.

**`BUILD_FAILED: report publication failed; previous reports were restored`**

Falha ao renomear os arquivos temporários para o destino final. Os relatórios anteriores foram restaurados automaticamente. Verifique permissões e espaço em disco em `deltas/`.

**`BUILD_FAILED: report publication failed and rollback was incomplete`**

Falha tanto na publicação quanto na restauração dos backups. Verifique manualmente `deltas/` e restaure os arquivos a partir do backup se necessário.

**`BUILD_FAILED: report publication failed`**

Erro genérico de E/S durante a escrita. Verifique espaço em disco e permissões em `deltas/`.

## Próximo passo

Saiba mais sobre a [preparação para o Notion](publish-notion.md) ou consulte a [visão geral do projeto](../README.md).
