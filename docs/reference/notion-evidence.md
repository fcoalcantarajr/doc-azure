# Referência dos arquivos de evidência do Notion

Use esta referência somente ao publicar os quatro relatórios preparados. A
auditoria Azure normal não exige esses arquivos. O fluxo de publicação usa o
conector Notion e o navegador integrado ao ChatGPT; a aplicação Python prepara
e verifica a evidência, mas não atualiza externamente o Notion. OpenCode com
OMO-Slim e `9router` é usado para revisão de código/documentação e não produz
nem substitui os recibos Kimi K3 e Opus 5 exigidos para este gate de publicação.

O verificador rigoroso rejeita campos ausentes ou extras, capturas internamente
inconsistentes, horários obsoletos, hashes divergentes, IDs de chat reutilizados,
páginas duplicadas, respostas de revisão idênticas e diferenças semânticas. Os
envelopes registrados vinculam as observações da sessão; eles não são assinaturas
criptográficas dos serviços externos. Preserve os resultados brutos exatos. Não
reescreva um resultado bruto para fazê-lo passar.

Identidades fixas da hierarquia:

- página Azure DevOps ancestral: `2a1412e0-8c26-803b-a988-dc619a396e45`;
- pai direto dos relatórios e do hub: `66b81130-f72c-4864-9e1e-534c7459d620`;
- hub de auditoria Azure: `3c3412e0-8c26-809d-8e12-e5498b5fde60`.

O hub e os quatro relatórios são filhos diretos de `IA, automações & sessões`;
essa página e `Staging — duplicatas pra conferir` são filhas da página Azure
DevOps. O verificador confere o pai direto em cada modo.

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
│   └── notion-search-<slug>-<kind>.json       captura de chamada e resposta, doze arquivos
├── fetched/
    ├── <slug>.md                             capturado, quatro arquivos
    ├── <slug>.json                           registrado, quatro arquivos
    ├── hierarchy.json                        registrado
    └── duplicate-search.json                 registrado
└── draft/
    ├── targets.json                           registrado
    ├── raw/
    │   ├── staging-parent-fetch.json          capturado
    │   ├── duplicate-<slug>.json              capturado
    │   ├── source-<slug>.json                 capturado, quatro arquivos
    │   ├── copy-before-edit-<slug>.json       capturado, quatro arquivos
    │   ├── target-fetch-<slug>.json            capturado, quatro arquivos
    │   ├── target-update-<slug>.json           capturado, quatro arquivos
    │   └── search-<slug>-<kind>.json           capturado, doze arquivos
    └── fetched/
        ├── <slug>.md                           capturado, quatro arquivos
        ├── <slug>.json                          registrado, quatro arquivos
        └── duplicate-search.json                registrado
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
`surface: "chatgpt-integrated-browser"`. A resposta deve ser somente um objeto
JSON válido com exatamente `verdict`, `findings`, `unverifiable_gaps`,
`repository_consulted` e `packet_csv_consulted`. `verdict` é `PASS` ou
`NEEDS_FIXES`; cada achado tem exatamente `id`, `severity`, `claim_or_page`,
`evidence` e `proposed_correction`, todos textos não vazios. `findings` deve
coincidir exatamente com a lista do recibo, e o veredito deve coincidir com
`verdict`; assim o recibo não pode omitir um achado presente na resposta nem
contradizer seu veredito. `unverifiable_gaps` é uma lista de textos e os dois
campos `*_consulted` são booleanos. Para passar a porta, ambos os vereditos
devem ser `PASS`. `NEEDS_FIXES` bloqueia a publicação. Os caminhos são relativos
ao repositório. Os hashes da resposta salva e do navegador bruto devem
corresponder aos arquivos.

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
relatórios afetados e pode estar vazia. Como o schema não registra materialidade
de forma estruturada, qualquer decisão `deferred` bloqueia a publicação até ser
resolvida; esse critério é intencionalmente mais estrito que bloquear apenas
adiamentos materiais.

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
`connector_as_of` não pode ser anterior a `fetched_at` nem ao
`page_last_edited_at` bruto. Se a última edição for posterior ao estado que o
conector declara ter lido, a resposta é obsoleta e bloqueia os modos canônico e
de cópia. Defina
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

## Registrar buscas por duplicatas

Faça doze buscas no Notion limitadas à página pai: ID, título exato e marcador
de cada uma das quatro páginas. Cada chamada usa somente `query`, `page_url` e
`page_size: 50`; não passe filtros, cursores, ordenações ou seletores adicionais
que possam restringir os resultados. Salve cada captura como
`raw/notion-search-<slug>-<kind>.json`, usando exatamente este envelope:

```json
{
  "schema_version": 1,
  "request": {
    "query": "texto exato enviado",
    "page_url": "ID ou URL exata da página pai",
    "page_size": 50
  },
  "response": {
    "isError": false,
    "content": [{"type": "text", "text": "JSON exato retornado pelo conector"}]
  }
}
```

Registre em `request` os argumentos enviados; o gate exige exatamente essas
três chaves, compara `query` e `page_url` com o recibo e calcula o hash sobre o
envelope inteiro. O conector não ecoa esses argumentos no
resultado: esse envelope é uma observação capturada da sessão que associa a
chamada à resposta salva, não uma assinatura criptográfica da plataforma. Não
alegue autenticação além dessa associação. Preserve `response` sem alterações.
O payload interno pode declarar `type: "workspace_search"` ou `type:
"ai_search"` e deve conter uma lista `results`, `has_more: false` e
`next_cursor: null`. Uma resposta sem indicadores explícitos de paginação
completa, com `has_more: true`, ou com `request_status.incomplete_reason` não
nulo bloqueia a conclusão da busca. A API oficial exige `has_more` e
`next_cursor` ([referência oficial](https://developers.notion.com/reference/post-search)); se um conector não os devolver, não infira completude pela quantidade de resultados. Mesmo com paginação encerrada, a documentação oficial informa que Search não garante todos os resultados e que a indexação pode atrasar ([limitações oficiais](https://developers.notion.com/reference/search-optimizations-and-limitations)). Portanto, esses recibos registram resultados retornados; uma lista vazia não prova ausência de duplicatas.
Cada item de `results` deve identificar uma página com `id`,
`title` e `url` não vazios; quando `type` estiver presente, seu valor deve ser
`"page"`. Nas quatro buscas por marcador, o item da página esperada também deve
conter `highlight` como texto e esse texto deve incluir o marcador exato. O
conector pode acrescentar formatação ao destaque, mas não pode omitir o
marcador. Preserve o resultado bruto mesmo quando algum desses campos faltar:
a porta deve falhar, e o operador não deve completar ou corrigir a resposta à
mão.

Crie `fetched/duplicate-search.json` com exatamente `schema_version` e
`searches`. Use `schema_version: 1`. A lista `searches` tem exatamente doze
itens, cada um com:

```text
slug, kind, query, scope_parent_page_id, expected_page_id,
matched_page_ids, searched_at, raw_search_path, raw_search_sha256
```

Em cada item, `matched_page_ids` registra o ID fixo esperado uma vez ou uma
lista vazia. Mais de um resultado exato ou uma resposta vazia bloqueia a porta
de unicidade. Respostas vazias podem se repetir entre consultas diferentes
quando cada envelope registra a query e o parent exatos e a resposta declara
paginação encerrada; o parser as aceita como evidência bruta, mas não como prova
de ausência. Uma resposta não vazia com somente a página esperada tampouco
prova unicidade. O schema atual não oferece uma prova independente; por isso,
após validar os recibos, a porta continua bloqueada até existir evidência
independente comprovadamente completa. Respostas não vazias reutilizadas entre
queries distintas são rejeitadas; resultados amplos que contenham várias cópias continuam bloqueados.
Se o resultado bruto trouxer a página esperada mas o
título ou marcador não corresponder à consulta, a porta falha. Se uma busca por
marcador encontrar a página mas a resposta não trouxer `highlight` contendo o
marcador, siga o diagnóstico específico em [Solução de
problemas](../troubleshooting.md#busca-por-marcador-do-notion-não-retorna-highlight-válido).

## Verificações finais

Primeiro, verifique isoladamente os quatro corpos relidos:

```sh
uv run python scripts/04_prepare_notion.py --verify-fetched out/notion/fetched
```

O marcador obrigatório dessa etapa é `NOTION_FETCHED_OK`. Ele prova a
equivalência dos quatro corpos com o manifesto atual, mas não valida sozinho as
revisões, a hierarquia ou as buscas de duplicatas. Se o marcador não aparecer,
siga o diagnóstico de [`--verify-fetched`](../troubleshooting.md#--verify-fetched-não-imprime-notion_fetched_ok)
antes de executar as portas completas.

Depois execute os dois comandos:

```sh
uv run python scripts/04_prepare_notion.py --verify-publication
uv run python verify.py --require-publication
```

No estado atual, não espere os marcadores `NOTION_PUBLICATION_OK` e `GATE_OK`
com `--require-publication`: ambos os gates rejeitam Search como prova de
unicidade porque falta inventário independente comprovadamente completo. O
primeiro comando imprime `NOTION_PREPARATION_FAILED` e o segundo `GATE_FAIL`.
Preserve os recibos e não declare que os relatórios atuais estão publicados.
O `GATE_OK` sem opção de publicação cobre somente a porta local.

## Verificar publicação somente em cópias

Use este modo quando a atualização tiver sido autorizada em cópias. Ele não
altera a porta canônica. Os quatro originais continuam identificados no
`publication-manifest.json`; os destinos de rascunho ficam somente em
`draft/targets.json`.

O objeto de topo de `draft/targets.json` tem exatamente:

```text
schema_version, draft_parent_page_id, draft_parent_fetch_path,
draft_parent_fetch_sha256, entries
```

`schema_version` é `1`; `draft_parent_page_id` é o Staging
`2d5412e0-8c26-803d-9e30-ec56c88af85f`. O fetch capturado para esse pai deve
mostrar Staging sob Azure DevOps. `entries` contém exatamente os quatro slugs,
na mesma ordem do manifesto de publicação. Cada item tem exatamente:

```text
slug, source_page_id, source_title, page_id, title, parent_page_id, url,
marker, prepared_path, body_sha256, semantic_sha256, duplicated_at,
duplicate_result_path, duplicate_result_sha256, source_fetch_path,
source_fetch_sha256, source_final_fetch_path, source_final_fetch_sha256,
copy_fetch_path, copy_fetch_sha256
```

`source_page_id` e `source_title` são os valores do manifesto canônico.
`page_id` vem do resultado bruto de `notion_duplicate_page`, deve ser diferente
de todo ID-fonte e de todos os outros destinos. O título final é
`Rascunho — <título original>` e `parent_page_id` é o ID de Staging. O resultado
bruto da duplicação deve identificar exatamente `page_id` e `url`.

`source_fetch_path` registra o original antes da duplicação;
`copy_fetch_path` registra a cópia antes de qualquer edição; e
`source_final_fetch_path` registra o original após todas as atualizações. O gate
verifica que ID, título, URL, pai, corpo e horário de última edição da fonte
continuam iguais entre os dois fetches. A cópia inicial tem ID próprio, começa
sob o mesmo pai do original e mantém a mesma semântica. A ordem exigida é
`source_fetch ≤ duplicação ≤ copy_fetch ≤ atualização ≤ read-back`; cada fetch
final da fonte ocorre depois da última atualização das cópias. Confira
manualmente `truncated`, `unknown_block_count` e
`unknown_block_ids` antes da edição; fetch incompleto bloqueia a operação.

Os recibos finais `<slug>.json` e corpos `<slug>.md` usam o mesmo schema do
modo canônico, mas ficam em `draft/fetched/`. Os recibos devem identificar o ID
de cópia, o título `Rascunho — ...` e o pai Staging. As buscas por ID, título e
marcador também são limitadas ao Staging e devem retornar somente a cópia
esperada.

Execute:

```sh
uv run python verify.py --require-draft-publication
```

Com Search como única evidência de unicidade, esse comando retorna `GATE_FAIL`
porque falta inventário independente comprovadamente completo. Se vier a
retornar `GATE_OK` após uma mudança futura no contrato de evidência, ele
comprovará somente os quatro rascunhos. Use `--require-publication` para a
porta canônica; os dois modos são exclusivos.
