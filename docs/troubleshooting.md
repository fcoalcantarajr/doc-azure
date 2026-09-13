# Solução de problemas

Corresponda à mensagem exata do terminal ou ao sintoma. Não exponha `.env`, valores de PAT, dados brutos de funcionários ou arquivos sob `out/` ao pedir ajuda.

## `uv: command not found`

Causa: o `uv` está ausente ou o terminal não recarregou o caminho do executável.

1. Instale o `uv` a partir do [guia oficial de instalação](https://docs.astral.sh/uv/getting-started/installation/).
2. Feche e reabra o terminal.
3. Execute `uv --version`.

## `SETUP_FAILED: local configuration is invalid`

Causa: `.env` está faltando, `AZDO_PAT` está vazio, ou uma linha que não é comentário em `.env` não contém `=`.

1. Copie `.env.example` para `.env`.
2. Mantenha exatamente uma configuração `AZDO_PAT=...` com um PAT real.
3. Execute `uv run --no-sync python scripts/setup.py` novamente.

O comando de setup oculta deliberadamente o valor detalhado e nunca imprime o PAT.

## `ModuleNotFoundError: No module named 'fcntl'`

Causa: o aplicativo foi iniciado no Windows nativo. O bloqueio de snapshots requer a interface Unix `fcntl`.

1. Instale o [WSL com Ubuntu](https://learn.microsoft.com/en-us/windows/wsl/install).
2. Abra o terminal Ubuntu.
3. Clone e execute o projeto novamente inteiramente dentro do WSL.

Não misture um ambiente virtual do Windows nativo com a pasta do projeto no WSL.

## Auditoria nova termina com `ACQUISITION_VALIDATION_FAILED`

Causa: o cliente não pôde adquirir ou validar um snapshot completo do Azure. As razões mais comuns são PAT expirado, escopo faltando, acesso ao projeto faltando, falha de rede, resposta do Azure alterada ou manter o valor de exemplo de `.env.example` sem substituição.

1. Abra `.env` e confirme que o placeholder de exemplo foi substituído. Não cole o valor real no terminal ou em uma mensagem de suporte.
2. Confirme que o PAT não expirou e é limitado a `bancodonordeste`.
3. Confirme os escopos **Wiki: Read** e **Work Items: Read**.
4. Confirme que você pode ver a Wiki do projeto fixo e o `Processo-Agil` no Azure DevOps com a mesma identidade.
5. Repita `uv run python scripts/run_audit.py --refresh` uma vez.
6. Se ainda falhar, preserve a mensagem sanitizada do terminal e peça a um mantenedor para inspecionar a validação de snapshot. Não envie o PAT ou arquivos brutos de `out/`.

Uma falha de refresh deixa as gerações de fonte completas selecionadas anteriormente inalteradas.

## Auditoria offline diz que a aquisição ou validação de snapshot falhou

Causa: um clone novo não tem snapshots em cache ignorados, ou os snapshots locais estão incompletos ou inválidos.

- Se o acesso atual ao Azure é permitido, execute `uv run python scripts/run_audit.py --refresh`.
- Se o acesso à rede é proibido, obtenha uma cópia privada aprovada das evidências completas de `out/wiki` e `out/process`. O Git não as contém.

Um operador apenas offline não precisa de `.env` nem de `scripts/setup.py`. Coloque os snapshots aprovados nos caminhos exatos acima e execute `--offline` diretamente.

## Auditoria imprime `DELTAS` e o shell reporta código de saída `1`

Esta é uma auditoria completada, não uma falha. O código de saída `1` significa que a cobertura está completa e pelo menos uma reivindicação avaliada não é `CONFIRMADO`.

Abra o `global.md` atual e os relatórios de página como descrito em [Ler os resultados](guides/run-audit.md#como-ler-o-resultado).

## Auditoria imprime `COVERAGE_GAP`

Causa: o texto atual da Wiki ou o inventário de processo difere da baseline de cobertura revisada.

Pare antes da publicação. Um mantenedor deve revisar a mudança exata, atualizar o catálogo de reivindicações ou as verificações determinísticas quando necessário, adicionar um teste de regressão e aprovar novas baselines. Não regenere uma baseline apenas para fazer a porta passar.

## `BUILD_FAILED: UNMAPPED_DOC_CHANGE: ...`

Causa: a construção independente de relatórios usou a baseline de cobertura revisada e encontrou texto alterado da Wiki que nenhuma reivindicação aprovada cobre.

Pare a publicação. Não reexecute sem `--coverage-baseline` e não atualize a baseline apenas para fazer o comando ter sucesso. Um mantenedor deve revisar o texto alterado, catálogo, testes e baseline. Outras mensagens `BUILD_FAILED:` significam que os snapshots, catálogo, seletores ou caminho de saída são inválidos; preserve a mensagem e não commit relatórios parcialmente investigados.

## `RUN_OUTPUT_FAILED: ...`

Causa: a auditoria classificou seu trabalho mas não pôde escrever o bundle local final. Causas comuns são pasta do projeto somente leitura, espaço em disco insuficiente, bloqueio de sistema de arquivos não suportado ou caminho danificado sob `out/audit`.

1. Confirme que a pasta do projeto e `out/` são graváveis pela sua conta.
2. Confirme que o disco tem espaço livre.
3. No Windows, confirme que o projeto está rodando dentro do WSL.
4. Preserve a evidência existente em `out/` e o tipo de erro exato depois dos dois-pontos.
5. Repita uma vez somente após corrigir o problema de sistema de arquivos identificado.

Não delete nem chmod o projeto inteiro como uma solução genérica.

## Porta não consegue reconstruir relatórios ou diz que a procedência é inverificável

Texto típico inclui `verified report rebuild failed`, `provenance is unverifiable`, `snapshot root has no complete CURRENT` ou `snapshot validation failed`.

Causa: `verify.py` é uma porta de procedência para mantenedores. Ela requer as gerações exatas de Wiki e processo ignoradas nomeadas dentro dos relatórios versionados atuais em `deltas/`. O Git não distribui esses snapshots, e um refresh novo cria IDs de geração diferentes.

- Na máquina de auditoria com evidência, confirme que as gerações nomeadas ainda existem sob `out/wiki/snapshots/` e `out/process/snapshots/`, depois repita.
- Em um clone sem essas gerações retidas, execute `uv run pytest -q` como verificação de saúde portátil do código. Não chame esse resultado de `GATE_OK`.
- Se a prova de procedência completa for necessária, obtenha as gerações históricas aprovadas pelo processo de transferência privada de evidências da organização.

Nunca fabrique ou renomeie uma geração para combinar com um relatório.

## `GATE_FAIL: Notion verification failed: ...`

Causa: `verify.py` encontrou um manifesto local `out/notion` e seus recibos externos estão faltando, obsoletos, malformados ou inconsistentes com os relatórios atuais.

1. Mova todo o diretório antigo `out/notion` para um local aprovado com timestamp fora do projeto. Isso preserva `review/` e `fetched/` juntos e evita que recibos antigos contaminem a nova execução.
2. Regenere os arquivos locais preparados com `uv run python scripts/04_prepare_notion.py --repository-url https://github.com/fcoalcantarajr/doc-azure`.
3. Se a publicação não for necessária, execute `uv run python verify.py` novamente.
4. Se a publicação for necessária, repita o fluxo completo de revisão, reconciliação, atualização, releitura e prova no [guia de publicação no Notion](guides/publish-notion.md). Não reutilize nem edite à mão um recibo antigo.

Nunca delete recibos externos que devem ser retidos sob uma política de auditoria ou registros. O diretório é ignorado pelo Git mas ainda pode ser evidência institucional.

## `NOTION_PREPARATION_FAILED: publication manifest is stale`

Causa: um relatório versionado mudou depois que os corpos locais do Notion foram preparados.

Execute:

```sh
uv run python scripts/04_prepare_notion.py --repository-url https://github.com/fcoalcantarajr/doc-azure
```

Depois reinicie ambas as revisões independentes de modelo. Revisões antigas estão vinculadas ao pacote antigo e não podem aprovar um novo.

## Modelo, esforço, página ou conector do Notion indisponível

Pare a publicação. O contrato proíbe substituição de modelo, esforço reduzido, páginas de reposição ou superfície diferente. Relatórios locais permanecem utilizáveis; apenas a porta de publicação externa é bloqueada.

## `GATE_FAIL` sem mensagem de Notion

Leia o texto após `GATE_FAIL:`. Ele nomeia o invariável que falhou sem imprimir corpos de fonte ou credenciais. A porta executa a suíte completa ao final, mas suprime a saída dos subprocessos para não vazar conteúdo sensível. Se a mensagem for `subprocess 'uv' failed with exit code <n>`, execute os testes separadamente para ver o diagnóstico:

```sh
uv run pytest -q
```

Se os testes separados falharem, corrija essa falha antes de repetir a porta. Se passarem, execute `uv run python verify.py` novamente uma vez. Persistindo a divergência, preserve as duas mensagens sanitizadas e peça ao mantenedor para comparar os ambientes; não envie `.env`, PAT nem arquivos brutos de `out/`. Qualquer outra mensagem após `GATE_FAIL:` identifica um invariável de repositório, evidência, relatório, segredo ou publicação. Não contorne a porta.

## O terminal imprime `Hello from doc-azure!`

Causa: você executou o `main.py` de placeholder, que não é o ponto de entrada do aplicativo. Execute `uv run python scripts/run_audit.py --refresh` para uma auditoria atualizada.
