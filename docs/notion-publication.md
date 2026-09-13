# Contrato de publicação no Notion

## Localização e identidades das páginas existentes

Os quatro relatórios permanecem filhos diretos da página pai fixa. A publicação
deve atualizar essas páginas no lugar; é proibido criar substitutas ou duplicatas.

ID da página pai: `2a1412e0-8c26-803b-a988-dc619a396e45`

ID do hub de auditoria Azure: `3c3412e0-8c26-809d-8e12-e5498b5fde60`

O hub é outro filho da página pai acima, ao lado das quatro páginas de
relatório. Ele não é pai delas. A porta rigorosa de evidências busca tanto a
página pai quanto esse hub irmão.

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

SHA-256 do pacote de revisão atual: `0bbf6aabebf57703b60ea619e36ade4ff8023cd14256cd7b8a3103cc32cd282f`.
SHA-256 do prompt de revisão atual: `9921af82e43b24bb5a01069d2c251e8dc813f90199b606bb49740fbe475a73a3`.

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
iguais; a autodescrição conflitante exige conferência visual do operador e deve
ser registrada no recibo bruto.

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
pai comum, ausência de duplicatas, ordem temporal válida entre atualização e
releitura, hashes dos recibos brutos e equivalência semântica de todos os
achados ordenados. Somente a releitura bem-sucedida justifica o estado atual
“publicado”.
