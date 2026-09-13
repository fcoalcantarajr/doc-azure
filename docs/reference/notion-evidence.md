# Referência dos arquivos de evidência do Notion

Use esta referência somente ao publicar os quatro relatórios preparados. A
auditoria Azure normal não exige esses arquivos. O fluxo de publicação usa o
conector Notion e o navegador integrado ao ChatGPT; a aplicação Python prepara
e verifica a evidência, mas não atualiza externamente o Notion.

O verificador rigoroso rejeita campos ausentes ou extras, resultados de
ferramenta inventados, horários obsoletos, hashes divergentes, IDs de chat
reutilizados, páginas duplicadas, respostas de revisão idênticas e diferenças
semânticas. Preserve os resultados brutos exatos. Não reescreva um resultado
bruto para fazê-lo passar.

Identidades fixas da hierarquia:

- página pai: `2a1412e0-8c26-803b-a988-dc619a396e45`;
- hub de auditoria Azure: `3c3412e0-8c26-809d-8e12-e5498b5fde60`.

O hub e a página pai são páginas diferentes. O hub e as quatro páginas fixas de
relatório são filhos diretos da página pai; o hub é irmão dos relatórios.

## Antes de qualquer atualização externa

1. Execute o comando de preparação em uma linha do [contrato de publicação no
   Notion](../notion-publication.md#preparação-local).
2. Abra `out/notion/review/review-manifest.json` e anote `packet_sha256` e
   `prompt_sha256`. Não calcule hashes diferentes a partir de texto copiado.
3. Inspecione cada corpo em `out/notion/prepared/` para detectar dados pessoais,
   segredos ou conteúdo inadequado ao destino.
4. Conclua as duas revisões e a reconciliação descritas abaixo.
5. Execute `uv run python scripts/04_prepare_notion.py --verify-publication`.
   Antes de existir evidência de publicação, o comando deve falhar. Isso confirma
   que a porta falha fechada; não é autorização para atualizar páginas.

## Árvore de diretórios obrigatória

Arquivos marcados como `gerado` vêm de `scripts/04_prepare_notion.py`. Arquivos
`capturado` devem conter o resultado externo exato. Arquivos `registrado` são
recibos laterais cujos valores são copiados da evidência capturada.

```text
out/notion/
├── publication-manifest.json                 gerado
├── prepared/
│   ├── leiame.md                             gerado
│   ├── politicas.md                          gerado
│   ├── changelog.md                          gerado
│   └── apendice.md                           gerado
├── review/
│   ├── packet.csv                            gerado
│   ├── prompt.txt                            gerado
│   ├── review-manifest.json                  gerado
│   ├── responses/
│   │   ├── kimi-k3.md                        capturado
│   │   └── opus-5.md                         capturado
│   ├── raw/
│   │   ├── kimi-k3.json                      capturado
│   │   └── opus-5.json                       capturado
│   ├── receipts/
│   │   ├── kimi-k3.json                      registrado
│   │   └── opus-5.json                       registrado
│   └── reconciliation.json                   registrado
├── raw/
│   ├── notion-update-<slug>.json             capturado, quatro arquivos
│   ├── notion-fetch-<slug>.json              capturado, quatro arquivos
│   ├── notion-fetch-parent.json              capturado
│   ├── notion-fetch-hub.json                 capturado
│   └── notion-search-<slug>-<kind>.json       capturado, doze arquivos
└── fetched/
    ├── <slug>.md                             capturado, quatro arquivos
    ├── <slug>.json                           registrado, quatro arquivos
    ├── hierarchy.json                        registrado
    └── duplicate-search.json                 registrado
```

`<slug>` é exatamente `leiame`, `politicas`, `changelog` ou `apendice`.
`<kind>` é exatamente `page_id`, `title` ou `marker`.

## Calcular o hash de um arquivo

Use o mesmo comando no macOS, Linux e WSL. Substitua `PATH` por um caminho
relativo da árvore acima:

```sh
uv run python -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" PATH
```

Calcule o hash dos bytes no disco depois de salvar o arquivo. Não calcule o hash
de texto copiado da tela.

## Capturar cada revisão do navegador

Use chats novos e separados. Antes do envio, confirme visualmente o modelo
atribuído e o esforço máximo. Envie os mesmos `packet.csv` e `prompt.txt` gerados
aos dois chats. Registre todos os horários com fuso, por exemplo
`2026-09-09T18:30:00-03:00`.

Salve a resposta completa do modelo, sem os controles da interface, no arquivo
Markdown correspondente em `review/responses/`. Salve um envelope bruto do
resultado do navegador em `review/raw/`. O arquivo bruto é um objeto JSON com
exatamente `isError` e `content`. `isError` é `false`; `content` contém um item
de texto cujo `text` é um objeto codificado como JSON com exatamente estes
campos:

| Campo | Valor obrigatório |
| --- | --- |
| `surface` | `chatgpt-integrated-browser` |
| `chat_id`, `chat_url` | Identidade deste chat distinto |
| `model` | `Kimi K3` ou `Opus 5`, compatível com o nome do recibo |
| `effort` | `maximum` |
| `packet_name` | `packet.csv` |
| `packet_sha256`, `prompt_sha256` | Valores de `review-manifest.json` |
| `model_verified_at`, `effort_verified_at`, `sent_at`, `completed_at` | Horários com fuso, em ordem causal |
| `response_markdown` | Conteúdo exato do arquivo de resposta salvo |

Cada `review/receipts/<model>.json` tem exatamente estes campos:

```text
schema_version, model, effort, surface, packet_sha256, prompt_sha256,
chat_id, chat_url, model_verified_at, effort_verified_at, sent_at,
completed_at, verdict, response_path, response_sha256,
browser_result_path, browser_result_sha256, findings
```

Use `schema_version: 1`, `effort: "maximum"` e
`surface: "chatgpt-integrated-browser"`. `verdict` é exatamente `PASS` ou
`NEEDS_FIXES`. Cada item de `findings` tem exatamente `id`, `severity` e
`summary`, todos textos não vazios. Os caminhos são relativos ao repositório.
Os hashes da resposta salva e do navegador bruto devem corresponder aos arquivos.

Se as respostas forem idênticas byte a byte ou a autodescrição de uma resposta
conflitar com o modelo visível na interface, preserve a anomalia e repita as duas
revisões em chats novos. A porta rejeita hashes de resposta iguais; a
autodescrição exige conferência visual. O texto conflitante já fica preservado
em `response_markdown` no envelope bruto. Registre qualquer observação adicional
em uma nota de operador separada, fora dos JSON validados; não acrescente campos
aos schemas fechados. Não trate concordância como prova.

## Reconciliar as revisões

Crie `review/reconciliation.json` somente depois que as duas revisões
terminarem. Ele tem exatamente estes campos:

```text
schema_version, packet_sha256, review_response_hashes, reconciled_at,
outcome, report_semantic_hashes, decisions
```

Use `schema_version: 1`. Copie `report_semantic_hashes` do manifesto de revisão
gerado. `review_response_hashes` associa as chaves exatas `Kimi K3` e `Opus 5`
aos hashes das respostas. `reconciled_at` não pode ser anterior a nenhuma
revisão.

Crie uma decisão para cada par `(modelo, ID do achado)` e nenhuma outra. Cada
decisão tem exatamente:

```text
model, finding_id, decision, rationale, changed_reports
```

`decision` é `accepted`, `rejected` ou `deferred`; `rationale` é uma explicação
não vazia baseada em evidência; `changed_reports` é uma lista de slugs dos
relatórios afetados e pode estar vazia. Um achado material adiado bloqueia a
publicação mesmo que o esquema JSON passe.

## Atualizar e buscar cada página fixa

Para cada entrada do manifesto, use o conector Notion para substituir o corpo
do `page_id` existente exato pelo Markdown preparado correspondente. Nunca crie
uma página. Salve o resultado exato e bem-sucedido da ferramenta como
`raw/notion-update-<slug>.json`.

Busque a mesma página depois da atualização e salve o resultado exato como
`raw/notion-fetch-<slug>.json`. Extraia, sem alteração, o texto completo entre
`<content>` e `</content>` do resultado bruto para `fetched/<slug>.md`. O
analisador rigoroso aceita o corpo com ou sem uma quebra de linha final.

Os arquivos brutos de atualização e busca são envelopes JSON exatos do tipo
`CallToolResult` do conector:

```json
{
  "isError": false,
  "content": [
    {"type": "text", "text": "<string JSON exata retornada pelo conector>"}
  ]
}
```

O resultado interno da atualização deve identificar a página atualizada. O
resultado interno da busca deve representar uma página do Notion, com título,
URL, horário de referência do conector, propriedades, corpo, página pai e
horário da última edição quando o conector o fornecer.

Cada `fetched/<slug>.json` tem exatamente estes campos:

```text
schema_version, slug, title, page_id, parent_page_id, url, marker,
updated_at, fetched_at, connector_as_of, last_edited_available,
last_edited_time, semantic_sha256, raw_fetch_path, raw_fetch_sha256,
update_receipt_path, update_receipt_sha256
```

Use `schema_version: 1`. Copie os valores fixos de identidade e semântica de
`publication-manifest.json`. `fetched_at` não pode ser anterior a `updated_at`,
e `connector_as_of` não pode ser anterior a `fetched_at`. Defina
`last_edited_available` como `false` e `last_edited_time` como `null` somente
quando o resultado bruto do conector realmente omitir esse campo.

## Provar a hierarquia

Depois das atualizações, busque a página pai fixa e o hub de auditoria Azure.
Salve os resultados exatos como `raw/notion-fetch-parent.json` e
`raw/notion-fetch-hub.json`. Crie `fetched/hierarchy.json` com exatamente:

```text
schema_version, parent_page_id, parent_title, hub_page_id, fetched_at,
parent_fetch_path, parent_fetch_sha256, hub_fetch_path, hub_fetch_sha256,
pages
```

Use `schema_version: 1`. `pages` é uma lista ordenada de quatro itens que
corresponde ao manifesto de publicação. Cada item tem exatamente `page_id`,
`title`, `parent_page_id` e `url`.

## Provar a ausência de duplicatas

Faça doze buscas no Notion limitadas à página pai: ID, título exato e marcador
de cada uma das quatro páginas. Salve cada resultado exato como
`raw/notion-search-<slug>-<kind>.json`. Uma busca bruta usa o mesmo envelope
`CallToolResult`; seu objeto interno deve ter `type: "workspace_search"` e uma
lista `results`.

Crie `fetched/duplicate-search.json` com exatamente `schema_version` e
`searches`. Use `schema_version: 1`. A lista `searches` tem exatamente doze
itens, cada um com:

```text
slug, kind, query, scope_parent_page_id, expected_page_id,
matched_page_ids, searched_at, raw_search_path, raw_search_sha256
```

Em cada item, `matched_page_ids` deve conter somente o ID fixo esperado. Nenhum
resultado ou mais de um resultado bloqueia a publicação.

## Verificações finais

Execute os dois comandos:

```sh
uv run python scripts/04_prepare_notion.py --verify-publication
uv run python verify.py --require-publication
```

Os marcadores obrigatórios são `NOTION_PUBLICATION_OK` e `GATE_OK`. Se qualquer
comando falhar, procure a mensagem exata em [Solução de
problemas](../troubleshooting.md), preserve toda a evidência e não declare que
os relatórios atuais estão publicados.
