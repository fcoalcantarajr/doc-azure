# Publicar no Notion

Gere as páginas Notion a partir dos deltas e publique-as via Notion MCP + Notion AI.

## Antes de começar

**uv instalado.** O projeto usa `uv` para gerenciar dependências e executar scripts.

```bash
uv --version
```

Deve retornar algo como `uv 0.x.y`. Se não retornar, instale com:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Deltas construídos.** Os arquivos sob `out/notion/` devem existir. Verifique:

```bash
ls out/notion/
```

Se o diretório não existir ou estiver vazio, execute `03_build_delta.py` antes de continuar.

**Notion MCP conectado.** A integração Notion MCP precisa estar configurada no seu ambiente. Consulte [configuração](../configuration.md) se necessário.

**Navegador disponível.** O passo de publicação requer ChatGPT e Notion AI abertos no navegador, com Kimi K3 e Opus 5 (max effort) acessíveis.

**URL do repositório.** Anote a URL HTTPS do repositório GitHub. Será usada como `--repository-url`.

## Passo a passo

### 1. Preparar páginas localmente

O modo padrão gera os arquivos Notion sob `out/notion/`. Não contata o Notion e não publica.

```bash
uv run python scripts/04_prepare_notion.py --repository-url https://github.com/usuario/doc-azure
```

**O que você deve ver:**

```
out/notion/manifest.json
out/notion/leiame.md
out/notion/politicas.md
out/notion/changelog.md
out/notion/apendice.md
```

Cada arquivo é uma página Notion em Markdown pronta para publicação.

**Se der errado:**

Veja a seção [Se der errado](#se-der-errado) abaixo.

### 2. Verificar com fetched (`--verify-fetched`)

Após baixar as páginas do Notion via MCP, verifique se o conteúdo local confere com o que foi obtido remoto.

```bash
uv run python scripts/04_prepare_notion.py \
  --repository-url https://github.com/usuario/doc-azure \
  --verify-fetched out/notion-fetched
```

**O que você deve ver:**

```
NOTION_FETCHED_OK
```

O diretório `out/notion-fetched` deve conter as páginas baixadas do Notion antes de rodar esta verificação.

**Se der errado:**

Veja a seção [Se der errado](#se-der-errado) abaixo.

### 3. Verificar publicação (`--verify-publication`)

Após publicar as páginas no Notion, confirme que a publicação foi concluída corretamente.

```bash
uv run python scripts/04_prepare_notion.py \
  --repository-url https://github.com/usuario/doc-azure \
  --verify-publication
```

**O que você deve ver:**

```
NOTION_PUBLICATION_OK
```

**Se der errado:**

Veja a seção [Se der errado](#se-der-errado) abaixo.

### 4. Flags avançadas

As flags abaixo não são necessárias no uso diário. São úteis para testes ou quando o projeto está em diretório diferente.

| Flag | Descrição | Padrão |
|------|-----------|--------|
| `--root <caminho>` | Diretório raiz do projeto | `PROJECT_ROOT` |
| `--repository-url <url>` | URL HTTPS do repositório GitHub | (obrigatório) |
| `--verify-fetched <diretório>` | Diretório com páginas baixadas do Notion | — |
| `--verify-publication` | Verifica se a publicação foi concluída | — |

Exemplo com `--root`:

```bash
uv run python scripts/04_prepare_notion.py \
  --root /outro/diretorio \
  --repository-url https://github.com/usuario/doc-azure
```

## Como ler o resultado

Após a preparação, abra o manifesto:

```bash
cat out/notion/manifest.json
```

O manifesto lista cada página com seu slug, caminho local e status. Cada arquivo Markdown sob `out/notion/` corresponde a uma página Notion.

As quatro páginas publicadas são:

- **leiame** — Leia-me Processo da Organização Única
- **politicas** — Template de políticas explícitas
- **changelog** — Changelog
- **apendice** — Apêndice Técnico Processo Organização Única

Mensagens de progresso aparecem no stderr. O stdout retorna apenas o resultado final (caminho do manifesto + caminhos das entradas).

## Se der errado

**`uv: command not found`**

`uv` não está instalado ou não está no PATH. Instale com o comando mostrado em [Antes de começar](#antes-de-começar).

**`NOTION_PREPARATION_FAILED: {error}`**

Erro na preparação local. Verifique:

- `out/notion/` existe e é gravável.
- `--repository-url` foi informado.
- Os deltas foram construídos (`out/notion/` contém arquivos).

**`NOTION_FETCHED_OK` não aparece com `--verify-fetched`**

O diretório informado não confere com o conteúdo local. Verifique que o caminho está correto e que as páginas foram baixadas do Notion via MCP antes de rodar a verificação.

**`NOTION_PUBLICATION_OK` não aparece com `--verify-publication`**

A publicação no Notion não foi concluída ou as páginas não foram atualizadas. Verifique se o Notion MCP está conectado e se as páginas foram publicadas corretamente.

**Código de saída 1**

| Código | Significado |
|--------|-------------|
| 0 | Sucesso — preparação ou verificação concluída |
| 1 | Falha — verifique a mensagem de erro acima |

Para confirmar flags a qualquer momento:

```bash
uv run python scripts/04_prepare_notion.py --help
```

## Próximo passo

Saiba mais sobre a [visão geral do projeto](../user-guide.md).
