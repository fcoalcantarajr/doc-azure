# Runtime determinístico

Comando canônico:

```sh
uv run python scripts/run_audit.py --refresh
```

`--refresh` busca as duas famílias de fontes pelos coletores REST Azure já
permitidos. Sem essa opção, o comando reutiliza cache completa e pode buscar
pela API partes ausentes; portanto, o modo padrão não é offline. `--offline`
proíbe aquisição de rede e exige snapshots locais completos. Para fixtures e
reexecuções, o comando aceita `--root`, `--catalog`, `--document-baseline` e
`--process-baseline`. O
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

`config/process-coverage.json` usa schema 2 e contém exatamente
`schema_version`, `catalog_sha256`, `source` e `entries`. `source` vincula a
baseline a uma geração imutável, ao hash do manifesto, ao horário, às contagens
de artefatos e requisições e ao modo `full_api`. Esse modo só é marcado quando
nenhum estado anterior foi reutilizado e todos os GETs planejados foram feitos.
`scripts/prepare_baselines.py` valida essa origem e grava candidatos ignorados;
não chama a API nem modifica a baseline aprovada. Um snapshot `cache_assisted`
pode ser usado em uma auditoria normal se a rota completa e todas as impressões
forem idênticas à baseline aceita, mas não pode originar uma baseline nova.

As entradas são impressões de `fingerprint_json` sobre o mapa completo entre
nomes de artefatos e respostas JSON interpretadas. Cada nó tem uma impressão
que preserva o tipo e é endereçada por JSON Pointer escapado. Contêineres vazios
e a ordem de arrays são preservados; a ordem das chaves de objetos é
normalizada.

A política atual é conservadora: toda variação do inventário é uma lacuna de
cobertura, mesmo quando reivindicações mapeadas ainda podem ser avaliadas. Isso
evita declarar cobertura de superfícies novas, mas pode exigir revisão por
mudanças de ordem ou metadados da API. Nenhuma propriedade é descartada como
supostamente volátil sem evidência. Uma baseline revisada não prova, por si só,
que todo texto relevante foi modelado. A origem `full_api` e seus hashes
atestam consistência do snapshot local; não são assinatura remota do Azure nem
aprovação institucional do conteúdo observado.

## Baseline revisada e recibo atual

O pipeline completo é testado com fixtures sintéticas integrais dos coletores,
tanto offline quanto pela substituição do transporte HTTP nos coletores reais.
O teste de atualização observa 18 requisições GET e nenhuma escrita remota. A
CLI é exercitada como subprocesso. A primeira implementação revelou argumentos
de relógio ausentes e classificação incorreta de snapshots corrompidos; ambos
têm testes de regressão.

As baselines versionadas foram preparadas a partir de snapshots completos e
verificados com `scripts/prepare_baselines.py`, depois conferidas byte a byte
antes de serem adicionadas a `config/`. Elas contêm 222 IDs de reivindicação,
inventários das quatro páginas (`leiame`: 572, `politicas`: 361, `changelog`:
593 e `apendice`: 517 linhas) e 41.543 nós JSON de processo em 115 artefatos.
Os arquivos contêm hashes e seletores, não corpos brutos de respostas Azure.

Valores SHA-256 das baselines:

- `config/document-coverage.json`: `0591ca80a9150d78b777ab79e46a538bf2b3a37141078e6315b95ed131da2efa`
- `config/process-coverage.json`: `a4d076b2f135c08a9896065b3b1555c225d9b7de677a7786ef7f01fa5a8972fc`

## Recibo local atual — 2026-09-25

As quatro páginas versionadas citam a geração Wiki
`2e9fbf43c9a048e28bde264fca1cdaa1`, coletada em
`2026-09-15T17:38:39.995018+00:00`, e a geração de processo
`e1445692d82e4ed688a637cb34c1ebc0`, coletada por API em
`2026-09-25T01:51:36.130901+00:00`. O snapshot de processo usa schema 2, modo
`full_api`, 115 artefatos e 114 rotas GET únicas permitidas; um artefato é o
mapa local derivado do inventário. O manifesto do processo tem SHA-256
`dffc602b1263e3d7009c6d24b917f8880b2c5324b18088ca0ffa0ae840f48c35`. As fontes
não são contemporâneas; há cerca de 9 dias e 8 horas entre as coletas.

O recibo de auditoria criado em `2026-09-25T10:49:34.786502+00:00` está
selecionado por `out/audit/CURRENT` na geração
`67ae1ff279b94570bb7afa8041475940`: status `DELTAS`, código `1`, cobertura
completa, zero lacunas e 222 achados: 120 `CONFIRMADO`, 62 `DIVERGENTE`, 31
`NAO_VERIFICAVEL_API_PROCESSO` e 9 `AMBIGUO`. O hash lógico é
`5d6bc43b50667080b80df61acf46e3a11dcef70c6325cb6179b47e72f5b16af3`.
`DELTAS` é o resultado válido de uma auditoria completa com pelo menos um
achado não confirmado. O `run.json` preserva resultado e proveniência das
fontes, mas não registra argumentos de CLI nem contagem de chamadas de rede;
este recibo, sozinho, não prova se `--offline` foi usado. Consulte o código e
preserve evidência de execução específica ao precisar comprovar modo sem rede.
Este recibo é local e pontual; use `out/audit/CURRENT` para a seleção mais
recente.

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
é derivado em `out/process-llm`: contém o snapshot atual e o delta desde a fonte
da exportação anterior. Não altera as baselines nem os quatro relatórios de
Wiki em `deltas/`, e não cria recibos Notion.
