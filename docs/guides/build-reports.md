# Gerar os relatórios delta

Reconstrua, sem acesso à rede, os quatro relatórios Markdown a partir dos snapshots locais e da cobertura revisada.

## Antes de começar

Você precisa de gerações completas selecionadas por `out/wiki/CURRENT` e `out/process/CURRENT`. Em um clone novo, execute primeiro uma [auditoria atualizada](run-audit.md).

Confirme o catálogo e a baseline obrigatória para um resultado oficial:

```sh
ls config/wiki_claims.json config/document-coverage.json
```

Resultado esperado: o terminal mostra os dois caminhos.

## Construção oficial

Execute sempre a baseline de cobertura na construção que será revisada, versionada ou publicada:

```sh
uv run python scripts/03_build_delta.py --coverage-baseline config/document-coverage.json
```

Resultado esperado, nesta ordem:

```text
<caminho do projeto>/deltas/leiame.md
<caminho do projeto>/deltas/politicas.md
<caminho do projeto>/deltas/changelog.md
<caminho do projeto>/deltas/apendice.md
```

O comando retorna `0`. Cada relatório contém procedência, resumo e achados com um dos quatro status: `CONFIRMADO`, `DIVERGENTE`, `NAO_VERIFICAVEL_API_PROCESSO` ou `AMBIGUO`.

Não remova `--coverage-baseline` para contornar `UNMAPPED_DOC_CHANGE`. A execução sem baseline existe para diagnóstico e testes internos, mas não prova cobertura e não deve alimentar commit ou publicação.

## Conferir os arquivos

```sh
ls -l deltas/leiame.md deltas/politicas.md deltas/changelog.md deltas/apendice.md
```

Resultado esperado: quatro arquivos regulares, legíveis e não vazios.

## Opções avançadas

| Opção | Padrão | Uso |
| --- | --- | --- |
| `--evidence-root` | raiz do projeto | raiz que contém `out/wiki` e `out/process` |
| `--catalog` | `config/wiki_claims.json` | catálogo de reivindicações |
| `--coverage-baseline` | nenhum | baseline documental; obrigatória no fluxo oficial |
| `--output-dir` | `deltas/` | destino dos quatro relatórios |

Consulte a ajuda exata:

```sh
uv run python scripts/03_build_delta.py --help
```

Resultado esperado: a lista de opções termina sem erro.

## Se der errado

- `BUILD_FAILED: snapshot validation failed: snapshot root is missing`: não há evidência local; execute a auditoria atualizada ou obtenha snapshots privados aprovados.
- `BUILD_FAILED: UNMAPPED_DOC_CHANGE: <slugs>`: interrompa. Um mantenedor deve revisar a mudança, o catálogo, testes e baseline.
- `BUILD_FAILED: catalog validation failed`: corrija a estrutura de `config/wiki_claims.json`; não altere os relatórios à mão.
- `BUILD_FAILED: catalog must contain exactly the four fixed pages`: restaure os quatro slugs obrigatórios no catálogo.
- `BUILD_FAILED: claim evaluation failed`: os snapshots ou seletores não satisfazem o catálogo; preserve a mensagem e revise a evidência.
- `BUILD_FAILED: snapshot generation changed during report build`: nenhuma outra execução deve mover `CURRENT` durante a construção; repita depois que ela terminar.
- Erros de procedência, diretório, link simbólico, escrita ou rollback: preserve `deltas/` e a mensagem exata; corrija permissões, espaço ou tipo do caminho antes de repetir.

## Próximo passo

Execute a [porta de verificação](verify-repository.md). Para publicação externa, siga depois o [guia do Notion](publish-notion.md).
