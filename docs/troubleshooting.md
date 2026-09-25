# Solução de problemas

## `LLM_EXPORT_FAILED: ...`

Esse marcador pertence somente a `scripts/export_process_for_llm.py`. A falha
não apaga nem troca uma exportação válida anterior.

- Se cita `out/process/CURRENT`, falta um snapshot de origem completo. Use
  `--refresh` somente se tiver PAT e acesso ou restaure `out/process/` por canal
  privado aprovado.
- Se cita `out/process-llm/CURRENT`, a exportação selecionada falhou na validação.
  Preserve o ponteiro para diagnóstico e gere uma seleção íntegra:

  ```sh
  mv out/process-llm/CURRENT out/process-llm/CURRENT.invalid
  uv run python scripts/export_process_for_llm.py
  ```

  O comando não apaga a geração adulterada. Ele reseleciona uma geração histórica
  que corresponda exatamente à fonte ou publica uma nova. Se
  `CURRENT.invalid` já existir, escolha outro nome explícito antes do `mv`.
- Se cita validação, não conserte JSON ou manifesto à mão. Uma alteração quebra
  os hashes intencionalmente; faça nova coleta.
- Se a mensagem indicar que o baseline da exportação anterior é inválido,
  preserve `out/process-llm/CURRENT` e as gerações de `out/process/`. Examine o
  manifesto, `provenance.json` e `delta.json` da exportação selecionada e a
  fonte imutável registrada por ela. O problema pode estar na exportação ou na
  fonte. Restaure a evidência íntegra por canal privado aprovado ou investigue
  antes de mover o ponteiro. Não substitua silenciosamente por uma pasta
  escolhida por data.
- Se cita escrita, confira espaço livre, permissões e tipos dos caminhos sob
  `out/process-llm`.
- Se informa que uma geração histórica mudou durante a validação, preserve a
  geração para diagnóstico e repita o comando. O exportador recusou selecionar
  bytes que mudaram entre a descoberta e a validação protegida por lock.
- Se cita concorrência, deixe a outra execução terminar e repita. O exportador
  recusa substituir uma geração que veio de fonte diferente.

O modo sem `--refresh` não acessa rede nem credenciais. Se ele parecer exigir
PAT, confirme que executou `export_process_for_llm.py`, e não `run_audit.py`.
Veja o [guia específico](guides/export-process-for-llm.md).

O rename e o lock impedem publicação parcial visível durante concorrência ou
queda do processo. Eles não garantem durabilidade contra queda de energia, pois
arquivos e diretórios não recebem `fsync`; nesse caso, valide novamente e siga a
recuperação de `out/process-llm/CURRENT` acima.

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

## `INTERNAL_ERROR: <hash>`

Causa: ocorreu uma exceção inesperada durante a auditoria, mas a aplicação conseguiu publicar um bundle de diagnóstico. O hash e o caminho de `CURRENT` aparecem nas duas linhas normais de saída.

1. Resolva `out/audit/CURRENT` conforme [Como ler o resultado](guides/run-audit.md#como-ler-o-resultado).
2. Abra `run.json` e anote apenas `error_type`, `status` e `logical_sha256`; não compartilhe evidências brutas.
3. Execute `uv run pytest -q` para verificar se existe uma regressão portátil.
4. Preserve a geração de auditoria e encaminhe esses dados sanitizados a um mantenedor.

Esse caso é diferente de `RUN_OUTPUT_FAILED`: em `INTERNAL_ERROR`, o bundle existe e deve ser usado no diagnóstico.

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

## Busca por marcador do Notion não retorna `highlight` válido

Causa: uma das quatro buscas de duplicatas por marcador encontrou uma resposta
sem `highlight`, com `highlight` vazio ou sem o marcador exato. A porta usa esse
campo para provar que o resultado corresponde ao conteúdo da página, e não
apenas a um título ou ID semelhante.

1. Preserve o resultado bruto exatamente como o conector o devolveu; não
   acrescente nem edite `highlight`.
2. Abra a página esperada e confirme, por releitura do conector, que seu corpo
   contém o marcador exato registrado no manifesto.
3. Repita somente a busca pelo marcador exato, limitada à página pai fixa, e
   salve o novo resultado bruto com seu horário real.
4. Se o conector continuar omitindo `highlight`, interrompa a publicação e
   preserve as duas respostas para investigação. Uma busca por título ou ID não
   substitui a prova por marcador.

Depois de obter um resultado com `highlight` válido, regenere o item
correspondente de `fetched/duplicate-search.json` a partir da resposta real e
repita as duas portas rigorosas. Não reutilize horários ou hashes anteriores.

## `--verify-fetched` não imprime `NOTION_FETCHED_OK`

Causa: o manifesto de publicação ficou obsoleto ou ao menos um dos quatro pares
`out/notion/fetched/<slug>.md` e `<slug>.json` está ausente, malformado ou não
corresponde ao corpo preparado atual. A mensagem
`NOTION_PREPARATION_FAILED: <detalhe>` identifica o primeiro invariável que
falhou.

1. Preserve a mensagem e todos os resultados brutos do conector.
2. Confirme que os quatro slugs têm um arquivo `.md`, um recibo `.json` e os
   resultados brutos de atualização e busca exigidos pela referência.
3. Se o manifesto estiver obsoleto, prepare um pacote novo e repita as duas
   revisões independentes; não reutilize recibos do pacote anterior.
4. Nos demais casos, repita a leitura da página afetada pelo conector e gere o
   recibo lateral a partir dessa resposta real. Não edite o corpo ou o resultado
   bruto para fazê-lo coincidir.
5. Execute novamente `uv run python scripts/04_prepare_notion.py
   --verify-fetched out/notion/fetched`.

Só prossiga quando a saída for exatamente `NOTION_FETCHED_OK`. Esse marcador
prova apenas a equivalência dos quatro corpos. No estado atual, as portas de
publicação continuam bloqueadas quando Search é a única evidência de
unicidade; consulte a [referência de evidências](reference/notion-evidence.md)
antes de interpretar `NOTION_PREPARATION_FAILED` ou `GATE_FAIL`.

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
