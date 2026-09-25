# Contrato de publicação no Notion

## Localização e identidades das páginas existentes

Os quatro relatórios canônicos são páginas fixas. A publicação canônica deve
atualizá-las no lugar; substitutas e duplicatas não fazem parte desse fluxo.

Página ancestral Azure DevOps: `2a1412e0-8c26-803b-a988-dc619a396e45`

Pai direto dos relatórios e do hub: `66b81130-f72c-4864-9e1e-534c7459d620`
(`IA, automações & sessões`), filho da página Azure DevOps acima.

ID do hub de auditoria Azure: `3c3412e0-8c26-809d-8e12-e5498b5fde60`

O hub é irmão das quatro páginas de relatório sob `IA, automações & sessões`.
A página Azure DevOps é o ancestral seguinte. A porta canônica rigorosa busca o
pai direto e o hub.

| Slug | Título existente | ID da página existente | URL | Marcador |
| --- | --- | --- | --- | --- |
| `leiame` | Delta — Leiame × Processo-Agil implementado | `3c3412e0-8c26-813c-ad9c-d57026cfd566` | https://app.notion.com/p/3c3412e08c26813cad9cd57026cfd566 | `DELTA-AUDIT-MARKER-leiame` |
| `politicas` | Delta — Políticas Explícitas × Processo-Agil implementado | `3c3412e0-8c26-813a-8312-dc52450adf39` | https://app.notion.com/p/3c3412e08c26813a8312dc52450adf39 | `DELTA-AUDIT-MARKER-politicas` |
| `changelog` | Delta — Changelog - Processo Ágil no Azure DevOps × Processo-Agil implementado | `3c3412e0-8c26-81b8-b9fd-cca04e04452b` | https://app.notion.com/p/3c3412e08c2681b8b9fdcca04e04452b | `DELTA-AUDIT-MARKER-changelog` |
| `apendice` | Delta — Apêndice Técnico — Processo Organização Única × Processo-Agil implementado | `3c3412e0-8c26-81dc-81c1-fbf0c7cac428` | https://app.notion.com/p/3c3412e08c2681dc81c1fbf0c7cac428 | `DELTA-AUDIT-MARKER-apendice` |

## Preparação local

Execute o comando abaixo somente depois que os quatro relatórios versionados
passarem pela construção offline. Ele grava, sob `out/notion`, corpos em
Markdown aprimorado ignorados pelo Git, hashes semânticos, um CSV determinístico
com 222 linhas e um prompt idêntico para as revisões. O comando não realiza
operação externa nem comprova publicação.

```sh
uv run python scripts/04_prepare_notion.py --repository-url https://github.com/fcoalcantarajr/doc-azure
```

A entrega de 2026-09-09 usa os hashes abaixo. Os hashes de fonte vinculam os
relatórios versionados; os hashes de corpo vinculam o conteúdo em Markdown
aprimorado; os hashes semânticos vinculam título, marcador, metodologia,
definições de status, procedência, resumo e todos os campos ordenados dos
achados. Eles comprovam apenas identidade local.

| Slug | SHA-256 da fonte | SHA-256 do corpo preparado | SHA-256 semântico |
| --- | --- | --- | --- |
| `leiame` | `6c31f5f4f9eafc7be4113b7f47cdfbc1bd7071beb6dfe4f16e9922af784fe9cd` | `a3c39fdf14630abfe19cb3a4f327a80f9dee3124f932d5c9847190f62f1c4b8b` | `65805cf7ceec02e130cd71a18392214a915230a91c8e3abb490f0239bf75e3e8` |
| `politicas` | `8153ddb60686e9dd0e11ef5153af734e1996d534e2e12d91340e2273676dc1e7` | `9bb955668612b94e0ecc60f12e86d7fc7652259c343213609521c3088c28e438` | `f5722959e969e703fc2f861d8eba7c61fbf67487f4eb29be75aaa7d23d1cc200` |
| `changelog` | `a6b6baa9bf333d34ab7a47b54652f61c16b8a5b4e2e331159ff33d6e663e0c2d` | `7e91fe550387e579ebfe57919a0bb4b941fafb42613ae107ec8b00e006b7e9af` | `02e60d1a5df8b0dcafb0ab0901829fd79879ff3b0cb0c4dc23cf263c357d5fa8` |
| `apendice` | `e5099008ab565ef6ef5e625fbc749391df34771b8685defeec61ee7946ac9bae` | `17851534d1efbaa4c5654f4884b24824603f66925da069c3c9c71fe960ea00d2` | `96b0326091548d2c6a47313a32c4b93aad84c0d33329161dca12dc75d332b17c` |

SHA-256 do pacote registrado na entrega de 2026-09-09: `0bbf6aabebf57703b60ea619e36ade4ff8023cd14256cd7b8a3103cc32cd282f`.
SHA-256 do prompt registrado na entrega de 2026-09-09: `9921af82e43b24bb5a01069d2c251e8dc813f90199b606bb49740fbe475a73a3`.

Esses valores são evidência histórica, não parâmetros para uma nova revisão.
Em toda nova execução, `out/notion/review/review-manifest.json` é a única fonte
autoritativa para `packet_sha256` e `prompt_sha256`. O hash do prompt também
depende do valor exato informado em `--repository-url`.

## Porta obrigatória de revisão adversarial

Antes de atualizar qualquer página, revise os relatórios preparados em dois
chats independentes do Notion AI:

1. Kimi K3, esforço máximo.
2. Opus 5, esforço máximo.

A interação com o Notion AI deve usar o navegador integrado ao ChatGPT. O
aplicativo externo do Notion não pertence ao fluxo autorizado. Cada revisor
recebe os mesmos relatórios, catálogo de reivindicações, metodologia e trechos
materiais de evidência. As revisões permanecem independentes até a captura dos
dois vereditos. Todo conflito material é reconciliado contra a evidência bruta
dos snapshots, não por votação. Se o modelo exato, o esforço máximo, a sessão
autenticada ou a interface exigida estiver indisponível, a publicação falha
fechada.

Se os dois corpos de resposta forem idênticos byte a byte, ou se uma resposta
descrever um modelo diferente daquele visivelmente selecionado antes do envio,
a independência não foi estabelecida. Preserve o recibo anômalo, abra dois chats
novos, repita as duas revisões e não atualize o Notion até os novos recibos
satisfazerem a porta. O verificador rejeita automaticamente hashes de resposta
iguais. A autodescrição conflitante exige conferência visual do operador: a
resposta anômala já permanece no envelope bruto; registre a decisão em uma nota
separada, fora dos JSON de schema fechado, e não acrescente campos aos recibos.

Para cada chat, preserve um arquivo de resposta sanitizado e um recibo JSON com
modelo exato, esforço máximo, superfície do navegador integrado, ID distinto do
chat, hashes do pacote e do prompt, horários, veredito, achados estruturados e
hash da resposta. `out/notion/review/reconciliation.json` deve vincular as duas
respostas e registrar uma decisão para cada achado. Um `PASS` é evidência do
processo, não prova de que as afirmações das fontes são verdadeiras.

## Recibo da revisão externa — 2026-09-09

A porta do navegador foi executada em dois chats distintos do Notion AI, com o
modelo e o esforço exatos visíveis antes do envio:

- Opus 5, máximo, chat `3d6412e08c268085876700a963b885ac`, concluído em
  `2026-09-09T13:25:16.766Z`;
- Kimi K3, máximo, chat `3d6412e08c2680df8dce00a93c3be004`, concluído em
  `2026-09-09T13:43:30Z`.

Ambos retornaram `NEEDS_FIXES` com 15 achados. Os corpos eram idênticos e
incluíam autodescrição incompatível com o modelo exibido na interface; portanto,
o acordo não foi tratado como corroboração independente. Os recibos brutos da
interface continuam sendo a evidência de modelo. A reconciliação cobre os 30
pares modelo/achado. F1-F3 identificaram corretamente as páginas externas então
desatualizadas; F9 expôs uma lacuna reproduzível de autenticação da procedência
e foi corrigido começando pelo teste. Os demais achados foram rejeitados porque
não apresentaram contraexemplo causal ou contrariavam contrato já aplicado.
Nenhum hash semântico de relatório mudou.

Naquele ciclo histórico, anterior à proteção automática contra respostas
idênticas, os quatro IDs fixos foram atualizados no lugar pelo conector Notion.
A releitura pelo conector, a busca da página pai e do hub e as doze buscas no
escopo da página pai satisfizeram a porta vigente à época. Esse registro não
seria aceito pela porta atual e não é precedente para respostas idênticas ou
autoinconsistentes: a regra de falha fechada acima governa toda nova execução.

## Atualização e prova

Depois que a porta de revisão passar, use o conector Notion para atualizar no
lugar os quatro IDs fixos. Busque a página pai, o hub de auditoria, as quatro
páginas e faça três buscas de duplicatas por página, limitadas ao pai: ID,
título exato e marcador. Salve sob `out/notion`, ignorado pelo Git, os resultados
brutos sanitizados do conector, os recibos e os corpos completos relidos.

Antes da primeira atualização externa, siga a [referência dos arquivos de
evidência do Notion](reference/notion-evidence.md). Ela define a árvore completa,
os campos JSON exatos, os envelopes de resultados brutos, o comando de hash e
as verificações finais. Não invente campos nem edite à mão resultados brutos do
conector.

- `<slug>.json`: identidades fixas, horários, hash semântico e caminhos/hashes
  dos recibos brutos de atualização e busca.
- `<slug>.md`: corpo completo em Markdown aprimorado relido pelo conector.
- `hierarchy.json`: prova de pai comum e hub, sustentada por buscas brutas.
- `duplicate-search.json`: exatamente doze buscas no escopo, sustentadas por
  resultados brutos.

Execute:

```text
uv run python scripts/04_prepare_notion.py --verify-publication
uv run python verify.py --require-publication
```

A porta rigorosa exige reconciliação das revisões, identidades e títulos exatos,
pai comum, ordem temporal válida entre atualização e releitura, hashes dos
recibos brutos e equivalência semântica de todos os achados ordenados. Search
não é exaustivo; nem zero resultados nem um único resultado provam ausência de
duplicatas. Como o conector atual não fornece um inventário independente
comprovadamente completo, a porta de unicidade permanece bloqueada. A releitura
semântica, isoladamente, não justifica o estado atual “publicado”.

## Cópias de revisão em Staging

Quando houver autorização para editar cópias, use um fluxo separado da
publicação canônica. Primeiro conclua e reconcilie as revisões Kimi K3 e Opus 5
do pacote atual. Depois, duplique cada página-fonte pelo conector Notion e
preserve o resultado bruto da duplicação. Faça fetch da fonte e da cópia ainda
antes de editar; os IDs devem ser diferentes e a semântica da cópia deve
coincidir com a da fonte.

Mova somente as cópias para `Staging — duplicatas pra conferir`
(`2d5412e0-8c26-803d-9e30-ec56c88af85f`), renomeie cada uma como
`Rascunho — <título original>` e substitua o conteúdo da cópia pelo corpo
revisado. Não use `notion_update_page` nos IDs-fonte. Antes de substituir o
conteúdo, confira no fetch que a cópia está completa e não tem páginas-filhas
que seriam removidas.

Depois de atualizar todas as cópias, faça novo fetch de cada fonte para
confirmar que ID, título, pai, corpo e horário de última edição continuam
iguais ao estado inicial. Registre as identidades fonte/cópia, o resultado
bruto da duplicação, os fetches inicial e final da fonte, o fetch pré-edição da
cópia, os recibos de atualização e os read-backs em `out/notion/draft/`. Essa
árvore é ignorada pelo Git e tem schema próprio. A porta de rascunho exige IDs
distintos dos originais, cópia semântica inicial igual à fonte, destino sob
Staging, fetch pré-edição anterior à atualização, fontes preservadas após todas
as atualizações, read-back semântico e doze buscas dentro de Staging. As buscas
podem detectar correspondências retornadas, mas Search não garante todos os
resultados nem indexação imediata; como falta prova independente no schema
atual, a porta de unicidade permanece bloqueada mesmo quando cada busca retorna
somente a cópia esperada. Respostas vazias podem ser preservadas como evidência
bruta, mas também bloqueiam a porta.

Execute o gate completo do modo de cópia:

```sh
uv run python verify.py --require-draft-publication
```

`--require-publication` verifica a publicação canônica nos quatro IDs
originais. Se uma futura revisão do contrato permitir prova independente de
unicidade, um sucesso do modo de rascunho comprovará somente as cópias em
Staging; não significará que as páginas canônicas foram atualizadas.
