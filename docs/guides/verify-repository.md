# Verificar o repositório

Há uma verificação portátil de testes e uma porta local de procedência. Os modos
de publicação acrescentam requisitos externos; não substituem as verificações
locais.

## Verificação portátil de um clone

Execute:

```sh
uv run pytest -q
```

Resultado esperado: todos os testes passam. Essa verificação funciona em um clone limpo depois de `uv sync --locked`, mas não prova a procedência dos relatórios versionados.

## Porta local de procedência

`verify.py` compara os relatórios com as gerações exatas de Wiki e processo
registradas neles. Esses snapshots ficam ignorados pelo Git, então o gate
completo requer as gerações citadas ou uma alternativa de procedência aceita
pela baseline. A baseline de processo schema 2 só pode ser originada de um
snapshot `full_api`; um snapshot `cache_assisted` nunca serve para criar ou
substituir a baseline. Se a geração de origem registrada na baseline não estiver
disponível, o gate só aceita o `out/process/CURRENT` quando ele também for
`full_api`, validar todos os hashes e rotas planejadas e produzir exatamente as
impressões aceitas. Essa alternativa não substitui os snapshots exatos citados
pelos relatórios ao reconstruí-los.

Execute a verificação local sem opções de publicação:

```sh
uv run python verify.py
```

Resultado esperado quando as fontes e os artefatos versionados são válidos:

```text
GATE_OK
```

Para verificar a publicação canônica nos quatro IDs originais, execute a porta
rigorosa:

```sh
uv run python verify.py --require-publication
```

Com a evidência atual, a porta canônica retorna erro de unicidade, como
`GATE_FAIL: Notion Search is not an exhaustive uniqueness proof; no independent
complete inventory evidence is present`. `GATE_OK` sem opção de publicação
cobre somente as verificações locais.

Para validar somente as quatro cópias sob Staging, use
`uv run python verify.py --require-draft-publication`. As opções
`--require-publication` e `--require-draft-publication` são mutuamente
exclusivas; Search como única evidência de ausência bloqueia ambas. Nenhum dos
dois modos altera páginas.

O script retorna `0` no sucesso. `GATE_FAIL: <mensagem>` e código `1` identificam o primeiro invariável violado. A porta executa `uv run pytest -q` como última etapa. Você ainda pode rodar esse comando separadamente para ver a saída completa dos testes ou verificar a saúde portátil de um clone.

Um `GATE_OK` sem flags de publicação não prova que páginas foram publicadas.

## O que a porta valida

Em ordem, `verify.py` verifica:

1. arquivos e layout obrigatórios;
2. cobertura do `.gitignore`;
3. baselines de cobertura;
4. allowlist REST somente leitura do Azure;
5. sintaxe e conteúdo executável dos módulos Python;
6. contrato documentado de status;
7. ausência de segredos literais em arquivos rastreados;
8. reconstrução e procedência dos quatro relatórios;
9. artefatos locais; com `--require-publication` ou
   `--require-draft-publication`, a evidência externa correspondente do Notion;
10. funcionamento de `--help` nos scripts públicos;
11. suíte completa com `uv run pytest -q`.

## Limite importante

Uma nova execução com `--refresh` cria novas gerações imutáveis. Ela não recria os IDs históricos citados nos relatórios atuais e não corrige, por si só, uma falha de procedência. Não renomeie, fabrique ou edite snapshots para fazer a porta passar.

## Se der errado

- `required files are missing`: restaure o arquivo versionado indicado; em clone parcial, refaça o clone.
- `coverage baseline files are missing`: restaure os três arquivos versionados em `config/`.
- `a secret environment file is tracked` ou `secret literal found`: remova o segredo do conteúdo e do índice Git sem imprimi-lo; depois rotacione a credencial exposta.
- `verified report rebuild failed`, `provenance is unverifiable` ou erro de snapshot histórico: restaure as gerações exatas de Wiki e processo citadas nos relatórios por transferência privada aprovada. A exceção de `CURRENT` `full_api` só valida a origem da baseline de processo quando as impressões coincidem; ela não substitui as gerações usadas para reconstruir os relatórios. Num clone sem essas fontes, limite a conclusão aos testes portáteis.
- `current process snapshot differs from coverage baseline`: o snapshot atual não corresponde à baseline aceita. Não trate isso como falta de cache nem aceite automaticamente o estado atual. Confira o modo e a proveniência e siga a [recuperação de baseline](../troubleshooting.md#current-process-snapshot-differs-from-coverage-baseline).
- `deltas/<arquivo> differs from verified rebuild`: não edite o relatório à mão. Reconstrua-o a partir das gerações corretas e da baseline obrigatória.
- `Notion verification failed`: preserve os recibos e siga o [guia de publicação](publish-notion.md) desde a preparação; não misture evidências de pacotes diferentes.
- `subprocess 'uv' failed with exit code <n>`: a suíte falhou dentro da porta. Rode `uv run pytest -q` separadamente para ver o diagnóstico completo.
- outra mensagem: procure o texto exato em [Solução de problemas](../troubleshooting.md).

## Próximo passo

Se a publicação externa estiver no escopo, siga [Publicar no Notion](publish-notion.md).

## Revisão adversarial de mudanças

Para mudanças materiais em comportamento de CLI, proveniência de evidências ou
baselines, segurança, gates de publicação ou contratos para operadores, faça
uma revisão hostil, somente de leitura, com OpenCode, OMO-Slim e o preset
`9router`. Abra uma execução nova no checkout que contém as alterações; não
reutilize uma janela ou sessão cujo diretório seja outro projeto.

Antes de enviar a revisão, confirme o caminho de `git rev-parse
--show-toplevel`, o SHA base, o SHA de `HEAD`, o estado com
`git status --short` e todo o diff. Execute `opencode run --agent orchestrator`
a partir da raiz do projeto com uma solicitação que mencione
`https://github.com/fcoalcantarajr/doc-azure`, os SHAs e a árvore de trabalho.
Peça conclusões separadas sobre conformidade com os padrões do repositório e
comportamento em relação ao requisito, com severidade, arquivo, linha e
evidência. Não autorize o revisor a alterar arquivos, chamar Azure/Notion ou
publicar.

Se os revisores especialistas delegados falharem por falta de crédito ou erro
de provedor, registre essa cobertura como ausente. Um passe direto do
orquestrador é parcial e não equivale a revisões especialistas independentes.
Não compre créditos nem troque modelo ou preset sem instrução do operador.
Resolva os achados sustentados por evidência e revise novamente o diff final.

Esta revisão de código e documentação não substitui as revisões Kimi K3 e Opus
5 exigidas pelo contrato de publicação no Notion. Para aquela publicação, siga
o [guia próprio](publish-notion.md).
