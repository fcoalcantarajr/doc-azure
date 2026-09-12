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

As identidades fixas e a hierarquia estão no [contrato de publicação](../notion-publication.md#location-and-existing-page-identities). Os formatos exatos dos recibos estão na [referência de evidências](../reference/notion-evidence.md).

## 1. Preparar o pacote local

Use a URL real do remoto GitHub que contém o commit a revisar:

```sh
uv run python scripts/04_prepare_notion.py --repository-url https://github.com/fcoalcantarajr/doc-azure
```

Resultado esperado: o comando lista `out/notion/publication-manifest.json` e os quatro arquivos:

```text
out/notion/prepared/leiame.md
out/notion/prepared/politicas.md
out/notion/prepared/changelog.md
out/notion/prepared/apendice.md
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

Uma forma autônoma de operar é pedir ao Codex, na mesma tarefa local que tem acesso ao repositório, ao navegador e ao conector Notion:

```text
Revise este pacote em dois chats novos e separados do Notion AI: Kimi K3 e Opus 5, ambos com esforço máximo. Use exatamente out/notion/review/prompt.txt e packet.csv, não compartilhe as respostas entre os modelos, preserve os resultados brutos e preencha os recibos nos caminhos definidos em docs/reference/notion-evidence.md. Não publique ainda.
```

## 3. Reconciliar e repetir

Leia os dois pareceres. Para cada achado, registre em `out/notion/review/reconciliation.json` uma decisão `accepted`, `rejected` ou `deferred`, com justificativa baseada em evidência.

- Corrija todo achado material aceito.
- Para rejeitar, demonstre por código, teste ou contrato por que o achado não procede.
- Um achado material adiado bloqueia a publicação.
- Qualquer alteração nos relatórios invalida o pacote: reconstrua, prepare novamente e obtenha duas revisões novas.

Prossiga somente quando os dois modelos aprovarem o mesmo pacote e a reconciliação não tiver pendência material.

## 4. Confirmar que a porta está fechada

Antes da atualização externa, execute:

```sh
uv run python scripts/04_prepare_notion.py --verify-publication
```

Resultado esperado neste momento: `NOTION_PREPARATION_FAILED: ...`, porque ainda não existem recibos completos. Um sucesso prematuro indica evidência antiga ou misturada; pare e preserve `out/notion` para investigação.

## 5. Atualizar as quatro páginas existentes

Confirme novamente a autorização. No Codex, use o conector Notion para substituir o corpo de cada `page_id` fixo pelo arquivo preparado do mesmo slug. Não altere título, identidade ou hierarquia e não crie página.

Salve o resultado bruto de cada atualização em `out/notion/raw/notion-update-<slug>.json` exatamente como retornado. Em seguida, busque cada página pelo conector, salve `notion-fetch-<slug>.json` e extraia o corpo integral para `out/notion/fetched/<slug>.md`.

## 6. Provar hierarquia e ausência de duplicatas

Busque pelo conector:

- o parent fixo;
- o hub fixo;
- cada uma das quatro páginas.

Depois faça doze buscas limitadas ao parent: por ID, título exato e marcador de cada slug. Cada busca deve encontrar somente a página esperada. Grave os resultados e recibos exatamente nos caminhos da [referência de evidências](../reference/notion-evidence.md#prove-no-duplicates).

## 7. Verificar o retorno do conector

```sh
uv run python scripts/04_prepare_notion.py --verify-fetched out/notion/fetched
```

Resultado esperado:

```text
NOTION_FETCHED_OK
```

Esse comando compara os quatro corpos lidos de volta; ainda não valida sozinho revisões, hierarquia e duplicatas.

## 8. Fechar as duas portas rigorosas

```sh
uv run python scripts/04_prepare_notion.py --verify-publication
```

Resultado esperado: `NOTION_PUBLICATION_OK`.

Depois execute:

```sh
uv run python verify.py --require-publication
```

Resultado esperado: `GATE_OK`.

Só declare a publicação concluída se ambos os marcadores aparecerem para o mesmo manifesto e os mesmos relatórios.

## Se der errado

Não ajuste JSON ou resposta bruta para fazê-los passar. Preserve o erro e procure a mensagem exata em [Solução de problemas](../troubleshooting.md). A [referência de evidências](../reference/notion-evidence.md) contém a árvore de arquivos e cada campo obrigatório.
