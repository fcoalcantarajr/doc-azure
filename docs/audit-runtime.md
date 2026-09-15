# Runtime determinístico

Comando canônico:

```sh
uv run python scripts/run_audit.py --refresh
```

`--refresh` busca as duas famílias de fontes pelos coletores REST Azure já
permitidos. Omita-o para priorizar a cache; `--offline` proíbe aquisição de rede
e exige snapshots locais completos. Para fixtures e reexecuções, o comando
aceita `--root`, `--catalog`, `--document-baseline` e `--process-baseline`. O
`.env`, ignorado pelo Git, fornece `AZDO_PAT` somente para execuções com rede.

## Pipeline e saídas

Aquisição -> validação de completude dos coletores -> cobertura documental ->
comparação do inventário de processo -> avaliador de reivindicações -> bundle de
resultado. Não há modelo, prompt, heurística semântica nem requisição ao Notion
nesse fluxo.

O `SnapshotWriter` imutável publica um bundle sob `out/audit`. Resolva o ponteiro
`CURRENT` para encontrar `run.json`, `global.md` e os quatro relatórios. Execuções
com erro ou lacuna também publicam um bundle de diagnóstico, claramente marcado
como incompleto; nunca substituem a evidência de fonte nem os relatórios
canônicos em `deltas/`.

Contrato de saída:

| Código | Significado |
| --- | --- |
| 0 | Todas as reivindicações avaliadas confirmadas, sem lacuna de cobertura |
| 1 | Cobertura completa, com pelo menos um achado não confirmado |
| 2 | Lacuna de cobertura ou contrato de cobertura ausente/inválido |
| 3 | Falha na aquisição ou validação de snapshots/entradas |
| 4 | Erro interno inesperado ou impossibilidade de publicar as saídas |

`logical_sha256` exclui IDs de geração e horários de coleta e criação da
execução. A procedência permanece registrada separadamente no JSON e nos
relatórios. Gerações imutáveis podem diferir numa reexecução mesmo quando os
resultados lógicos são iguais.

## Baseline do inventário de processo

`config/process-coverage.json` tem exatamente `schema_version: 1`,
`catalog_sha256` e `entries`. As entradas são impressões de `fingerprint_json`
sobre o mapa completo entre nomes de artefatos e respostas JSON interpretadas.
Cada nó tem uma impressão que preserva o tipo e é endereçada por JSON Pointer
escapado. Contêineres vazios e a ordem de arrays são preservados; a ordem das
chaves de objetos é normalizada.

A política atual é conservadora: toda variação do inventário é uma lacuna de
cobertura, mesmo quando reivindicações mapeadas ainda podem ser avaliadas. Isso
evita declarar cobertura de superfícies novas, mas pode exigir revisão por
mudanças de ordem ou metadados da API. Nenhuma propriedade é descartada como
supostamente volátil sem evidência. Uma baseline revisada não prova, por si só,
que todo texto relevante foi modelado.

## Baseline revisada e recibo atual

O pipeline completo é testado com fixtures sintéticas integrais dos coletores,
tanto offline quanto pela substituição do transporte HTTP nos coletores reais.
O teste de atualização observa 18 requisições GET e nenhuma escrita remota. A
CLI é exercitada como subprocesso. A primeira implementação revelou argumentos
de relógio ausentes e classificação incorreta de snapshots corrompidos; ambos
têm testes de regressão.

As baselines versionadas foram preparadas a partir dos snapshots completos e
verificados com `scripts/prepare_baselines.py`, depois conferidas byte a byte
antes de serem adicionadas a `config/`. Elas contêm 222 IDs de reivindicação,
inventários das quatro páginas (572, 361, 593 e 517 linhas) e 40.559 nós JSON de
processo em 110 artefatos. Os arquivos contêm hashes e seletores, não corpos
brutos de respostas Azure.

Valores SHA-256 das baselines:

- `config/document-coverage.json`: `2e0d956a8f74f3933779d297adfff1328267de1ccd8a04e555228b7edbf2990e`
- `config/process-coverage.json`: `4fe95039f993a9473677b98e4a652bc4d0d79c1ad1a6658d6598bdfce9cd2418`

A execução atualizada mais recente, em 2026-09-09 das 11:35:12 às 11:35:14 UTC,
coletou quatro páginas de Wiki com quatro GETs e 110 artefatos de processo a
partir de 109 GETs. Um dos artefatos é o mapa local do inventário, derivado das
respostas coletadas; por isso a quantidade de artefatos é uma unidade maior que
a de requisições. A geração Wiki foi `a4ae120c5e9d45c9839bd6323c30d719`;
a geração de processo foi `75963a4853a543f68cb49d5bcb97589f`. Ela retornou código 1
(`DELTAS`), cobertura completa, zero lacunas e 222 achados classificados: 123
`CONFIRMADO`, 59 `DIVERGENTE`, 31 `NAO_VERIFICAVEL_API_PROCESSO` e 9
`AMBIGUO`. Seu hash lógico foi
`3ea48dc27b83ba7ba1491f56538e893433f52eaf9df063affe099dbca0166369`.

O verificador de relatórios canonicaliza intencionalmente apenas os campos de
horário de coleta, ID da geração e hash do manifesto na seção de procedência.
Todos os achados lógicos e o texto estável continuam comparados byte a byte;
assim, uma coleta nova equivalente não cria falsa variação, enquanto uma
alteração real do relatório ainda falha na porta.

O ciclo de 2026-09-09 concluiu as revisões externas no Notion AI e a publicação
com releitura descrita em `docs/archive/completion-audit-2026-09-09.md`. Essa
conclusão histórica não aprova uma geração posterior. Toda nova publicação deve
repetir revisão, reconciliação, atualização, releitura e porta rigorosa conforme
`docs/notion-publication.md` e o [guia operacional](guides/publish-notion.md).

O recibo de implementação do runtime determinístico registrou 374 testes
aprovados, incluindo regressões de identificador duplicado, modo offline sem
rede, saídas limpa/interna e variação de processo. Revisões posteriores podem
adicionar testes; use o resultado atual de `uv run pytest -q`, não essa contagem
histórica. Uma execução atualizada comprova o caminho da aplicação, não a
conclusão das portas do Notion.

## Runtime da exportação para LLM

A exportação processo-apenas não integra o pipeline de auditoria acima. O modo
normal usa exclusivamente a geração completa selecionada por
`out/process/CURRENT` e faz zero requisições. `--refresh` chama o mesmo runtime
do coletor de processo, com um `httpx.AsyncClient`, uma execução assíncrona e a
mesma allowlist GET, sem iniciar os coletores de Wiki ou work items. O resultado
é derivado em `out/process-llm` e não altera baselines, deltas ou recibos Notion.
