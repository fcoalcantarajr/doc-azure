# Publicar no Notion

Prepare, revise, atualize e prove as quatro páginas fixas do Notion. O Python prepara e valida a evidência; as operações externas são executadas no Codex com o conector Notion e o navegador integrado.

Este fluxo modifica páginas externas. Confirme autorização para a publicação imediatamente antes da primeira atualização. Nunca crie páginas substitutas.

## Antes de começar

Você precisa de:

- quatro relatórios oficiais já construídos em `deltas/`;
- acesso ao repositório privado no GitHub;
- Codex com o conector Notion conectado e o navegador integrado autenticado no Notion AI;
- Kimi K3 e Opus 5 disponíveis com esforço máximo;
- autorização para atualizar as quatro páginas existentes.

As identidades fixas e a hierarquia estão no [contrato de publicação](../notion-publication.md#localização-e-identidades-das-páginas-existentes). Os formatos exatos dos recibos estão na [referência de evidências](../reference/notion-evidence.md).

## 1. Preparar o pacote local

Use a URL real do remoto GitHub que contém o commit a revisar:

```sh
uv run python scripts/04_prepare_notion.py --repository-url https://github.com/fcoalcantarajr/doc-azure
```

Resultado esperado: o comando lista caminhos absolutos. Eles terminam em `out/notion/publication-manifest.json` e nos quatro arquivos:

```text
<caminho do projeto>/out/notion/prepared/leiame.md
<caminho do projeto>/out/notion/prepared/politicas.md
<caminho do projeto>/out/notion/prepared/changelog.md
<caminho do projeto>/out/notion/prepared/apendice.md
```

Com `--repository-url`, ele também cria `out/notion/review/packet.csv`, `prompt.txt` e `review-manifest.json`. Nada é enviado ao Notion nessa etapa.

Abra os quatro corpos preparados e confirme que não contêm PAT, dado pessoal ou conteúdo impróprio para o destino.

## 2. Obter duas revisões independentes

No navegador integrado, crie um chat novo do Notion AI para cada modelo. Não mostre a resposta de um ao outro.

No primeiro chat:

1. selecione `Kimi K3`;
2. selecione esforço máximo;
3. envie exatamente `out/notion/review/prompt.txt` e `packet.csv`;
4. aguarde a resposta completa;
5. preserve a resposta e a identidade do chat conforme a referência de evidências.

Repita em outro chat com `Opus 5` e esforço máximo, usando os mesmos arquivos. Se um modelo ou o esforço máximo estiver indisponível, interrompa a publicação; não substitua silenciosamente.

Neste contrato, “navegador integrado” é a superfície do navegador integrado do Codex/ChatGPT; o recibo usa o valor literal `chatgpt-integrated-browser`. O aplicativo desktop do Notion não satisfaz essa exigência. O operador não deve montar recibos ou envelopes brutos à mão: peça ao Codex para preservar o resultado real e preencher os arquivos conforme a referência. Se ele não tiver acesso simultâneo ao repositório, ao conector e a essa superfície, interrompa o fluxo.

Uma forma autônoma de operar é pedir ao Codex, na mesma tarefa local que tem acesso ao repositório, ao navegador e ao conector Notion:

```text
Revise este pacote em dois chats novos e separados do Notion AI: Kimi K3 e Opus 5, ambos com esforço máximo. Use exatamente out/notion/review/prompt.txt e packet.csv, não compartilhe as respostas entre os modelos, preserve os resultados brutos e preencha os recibos nos caminhos definidos em docs/reference/notion-evidence.md. Não publique ainda.
```

## 3. Reconciliar e repetir

Leia os dois pareceres. Para cada achado, registre em `out/notion/review/reconciliation.json` uma decisão `accepted`, `rejected` ou `deferred`, com justificativa baseada em evidência.

- Corrija todo achado material aceito.
- Para rejeitar, demonstre por código, teste ou contrato por que o achado não procede.
- Qualquer achado adiado bloqueia a publicação; o schema atual não registra
  materialidade estruturada para permitir uma exceção segura.
- Qualquer alteração nos relatórios invalida o pacote: reconstrua, prepare novamente e obtenha duas revisões novas.

Antes de reconciliar os achados, confirme a independência das respostas. Se os
dois corpos forem idênticos byte a byte ou se uma resposta descrever um modelo
diferente do que estava visivelmente selecionado antes do envio, preserve os
recibos anômalos, não atualize o Notion e repita **as duas** revisões em chats
novos. A [referência de evidências](../reference/notion-evidence.md#capturar-cada-revisão-do-navegador)
explica como registrar a anomalia sem alterar os schemas fechados. Não prossiga
com uma resposta antiga e apenas uma revisão repetida.

Prossiga somente quando cada achado dos dois modelos tiver uma decisão: todo
achado aceito já foi corrigido e todo achado rejeitado tem justificativa baseada
em código, teste ou contrato. Não pode restar achado material `deferred`. Um
veredito `NEEDS_FIXES` pode ser encerrado por essa reconciliação; a porta não
exige que o texto literal do veredito mude para `PASS`.

## 4. Confirmar que a porta está fechada

Antes da atualização externa, execute:

```sh
uv run python scripts/04_prepare_notion.py --verify-publication
```

Resultado esperado neste momento: `NOTION_PREPARATION_FAILED: ...`, porque ainda não existem recibos completos. Um sucesso prematuro indica evidência antiga ou misturada; pare e preserve `out/notion` para investigação.

## 5. Atualizar as quatro páginas existentes

Confirme novamente a autorização. No Codex, use o conector Notion para substituir o corpo de cada `page_id` fixo pelo arquivo preparado do mesmo slug. Não altere título, identidade ou hierarquia e não crie página.

Salve o resultado bruto de cada atualização em `out/notion/raw/notion-update-<slug>.json` exatamente como retornado. Em seguida, busque cada página pelo conector, salve a resposta em `out/notion/raw/notion-fetch-<slug>.json` e extraia o corpo integral para `out/notion/fetched/<slug>.md`.

## 6. Registrar hierarquia e buscas por duplicatas

Busque pelo conector:

- o parent fixo;
- o hub fixo;
- cada uma das quatro páginas.

Depois faça doze buscas limitadas ao parent: por ID, título exato e marcador de cada slug. Preserve também respostas vazias como evidência bruta, mas elas não aprovam a verificação de unicidade. Registre os resultados e recibos na [referência de evidências](../reference/notion-evidence.md#registrar-buscas-por-duplicatas).

Essas buscas são evidência complementar, não prova exaustiva de ausência: a documentação oficial do Notion diz que Search não garante todos os resultados e pode não refletir imediatamente páginas compartilhadas. `has_more: false` e `next_cursor: null` encerram a paginação retornada, mas não eliminam essa limitação. O schema atual não contém inventário independente comprovadamente completo, então resultado vazio ou a presença de somente a página esperada mantém o gate bloqueado. O conector atual `ai_search` também pode omitir os campos de paginação, caso em que o parser falha antes.

## 7. Verificar o retorno do conector

```sh
uv run python scripts/04_prepare_notion.py --verify-fetched out/notion/fetched
```

Resultado esperado:

```text
NOTION_FETCHED_OK
```

Esse comando compara os quatro corpos lidos de volta; ainda não valida sozinho revisões, hierarquia e duplicatas.

## 8. Registrar o bloqueio das portas rigorosas

```sh
uv run python scripts/04_prepare_notion.py --verify-publication
```

Neste momento, a porta canônica bloqueia após validar os demais recibos com
`Notion Search is not an exhaustive uniqueness proof; no independent complete
inventory evidence is present`. O comando retorna código `1`; não espere
`NOTION_PUBLICATION_OK` com Search como única evidência de ausência.

Depois execute:

```sh
uv run python verify.py --require-publication
```

Com `--require-publication`, o verificador também retorna `GATE_FAIL` pela mesma
limitação. O `GATE_OK` sem esse argumento verifica a auditoria local; não
comprova publicação. Não declare a publicação concluída até que exista e seja
validada uma fonte independente comprovadamente completa para a unicidade.

Preserve os erros e recibos brutos para rastreabilidade; não altere páginas
originais ou cópias com base em buscas que não provam unicidade.

## Se der errado

Não ajuste JSON ou resposta bruta para fazê-los passar. Preserve o erro e procure a mensagem exata em [Solução de problemas](../troubleshooting.md). A [referência de evidências](../reference/notion-evidence.md) contém a árvore de arquivos e cada campo obrigatório.
