# Auditoria Processo-Agil x Wiki — Design

**Data:** 2026-08-21  
**Status:** aprovado em conversa para detalhamento e execução  
**Organização Azure DevOps:** `bancodonordeste`  
**Processo:** `Processo-Agil` (`9d82e632-9028-4a6b-86f8-3edb3281cb15`)

## Objetivo

Comparar quatro páginas da wiki da Torre CCR com a configuração atual do
processo herdado `Processo-Agil`, usando exclusivamente operações documentadas
como somente leitura na API REST do Azure DevOps. O resultado deve ser
reproduzível localmente e publicado no Notion em quatro páginas irmãs, uma por
documento de origem.

## Fontes documentais

| ID | Página |
|---:|---|
| 35 | Leia-me - Processo da Organização Única |
| 10 | Template de políticas explícitas |
| 9 | Changelog |
| 37 | Apêndice Técnico - Processo Organização Única |

A wiki tem o identificador
`87014e24-4977-4d27-8e12-c05208008d95` e pertence ao projeto
`Torre CCR - Concessão de Crédito`.

## Princípios da comparação

### Fonte de verdade e recorte temporal

- A API do processo é a fonte de verdade para a configuração vigente no
  instante da coleta.
- A página da wiki é a fonte de verdade para aquilo que o documento afirma,
  não para a implementação.
- A API atual não demonstra quando uma configuração foi criada. Alegações
  históricas do changelog só podem ser confirmadas como estado atual, a menos
  que outra evidência temporal esteja disponível.
- A data/hora UTC da coleta, os URLs GET consultados e metadados de resposta
  serão registrados.

### Classes de resultado

Cada afirmação material receberá exatamente uma classe:

1. `CONFIRMADO`: a API atual fornece evidência direta compatível com a página.
2. `DIVERGENTE`: a API atual fornece evidência direta incompatível com a página.
3. `NAO_VERIFICAVEL_API_PROCESSO`: a afirmação trata de prática humana,
   governança, histórico, board de equipe, automação externa ou outro elemento
   que o modelo do processo não representa.
4. `AMBIGUO`: a linguagem da página ou a resposta da API permite mais de uma
   interpretação relevante; o relatório explicará a incerteza.

Ausência de representação na API não será convertida em divergência. Isso é
essencial para o Template de Políticas Explícitas: papéis, cadências, DoR, DoD,
classes de serviço e acordos de equipe não são campos do processo herdado.

## Escopo técnico da extração

O coletor consultará:

- lista de wikis e as quatro páginas com `includeContent=true`;
- lista de processos e seleção exata de `Processo-Agil`;
- metadados e estado habilitado/desabilitado de todos os Work Item Types;
- behaviors/backlogs do processo e associação de WITs aos behaviors;
- estados, campos, regras e layout de cada WIT de negócio ativo;
- tipos herdados desabilitados e tipos sistêmicos, em grupos separados.

### Allowlist semântica de operações HTTP

O método HTTP isolado não define se uma operação altera estado. A documentação
do Azure DevOps registra que `POST` pode criar recursos **ou** recuperar dados
por consultas avançadas. Por isso, o cliente aplicará uma allowlist por
combinação de método e rota:

- `GET`: páginas da wiki e metadados de processo, WIT, behavior, estados,
  campos, regras e layout;
- `POST .../_apis/wit/wiql`: execução não persistente de WIQL, apenas se uma
  afirmação exigir evidência sobre itens ou links reais;
- `POST .../_apis/wit/workitemsbatch`: leitura em lote, limitada aos IDs e
  campos necessários obtidos pela WIQL, apenas se essa segunda etapa for
  necessária.

Não serão permitidos `POST` de criação, `PUT`, `PATCH`, `DELETE` nem
`X-HTTP-Method-Override`. Uma operação de consulta opcional só será executada se
reduzir uma incerteza material; a definição do processo continuará sendo a
fonte principal desta auditoria.

Os doze WITs de negócio documentados serão tratados como o conjunto funcional
principal. Tipos de teste sistêmicos não serão contados como WITs de negócio;
tipos-base desabilitados serão mostrados como contexto, não como falsa
divergência na contagem de doze.

## Arquitetura local

O projeto usará Python 3.13 e somente a biblioteca padrão:

- `src/doc_azure/azure_client.py`: autenticação, construção de URLs e operações
  JSON restritas pela allowlist semântica, com mensagens seguras e sem registrar
  o PAT.
- `src/doc_azure/collect.py`: descoberta do processo e coleta completa das
  páginas e facetas da configuração.
- `src/doc_azure/compare.py`: avaliação determinística de afirmações contra o
  snapshot normalizado.
- `src/doc_azure/render.py`: geração de inventário e dos quatro relatórios
  Markdown.
- `config/wiki_claims.json`: catálogo versionado de afirmações auditáveis,
  trechos de origem e seletores de evidência.
- `scripts/setup.py`: preparação idempotente e validação local, executável com
  um único comando.
- `scripts/run_audit.py`: coleta, comparação e renderização, executável com um
  único comando.
- `tests/`: testes unitários e de integração local com respostas HTTP
  representativas e completas.

O catálogo de afirmações guardará o trecho-fonte e uma impressão do documento.
Se a página mudar e o trecho não existir mais, a execução falhará de forma
explicativa em vez de comparar silenciosamente uma especificação antiga.

## Artefatos

### Versionados

- `README.md`: início rápido e limites da auditoria.
- `docs/audit/README.md`: o que foi feito e como interpretar os resultados.
- `docs/audit/decisions.md`: decisões, razões e alternativas descartadas.
- `docs/audit/methodology.md`: escopo, taxonomia e limites epistêmicos.
- `docs/audit/delta-page-35-readme.md`.
- `docs/audit/delta-page-10-template-politicas.md`.
- `docs/audit/delta-page-9-changelog.md`.
- `docs/audit/delta-page-37-apendice-tecnico.md`.
- especificação e plano das skills Superpowers.
- código, configuração e testes necessários para reprodução.

### Regeneráveis e ignorados

- `out/raw/`: respostas JSON brutas da API.
- `out/normalized/`: snapshots normalizados.
- `out/reports/`: cópias regeneradas dos relatórios.
- caches, cobertura, ambientes virtuais, builds e logs.

Nenhum segredo será escrito nos artefatos. URLs poderão conter organização,
projeto e identificadores, mas nunca credenciais ou cabeçalhos de autorização.

## Fluxo de dados

1. `setup.py` verifica Python, cria diretórios regeneráveis e informa se
   `AZDO_PAT` está ausente, sem exibir seu valor.
2. `run_audit.py` carrega `.env`, descobre wiki e processo por nome/ID e executa
   apenas operações de leitura presentes na allowlist.
3. O coletor preserva resposta bruta e cria uma projeção estável, ordenada e
   sem dados de autenticação.
4. O comparador valida que cada trecho catalogado continua presente na wiki e
   avalia o seletor correspondente na configuração atual.
5. O renderizador produz inventário, resumo e quatro deltas separados.
6. O conteúdo validado é publicado no Notion pelo conector autenticado da
   sessão; o Python gera o Markdown, mas não recebe nem persiste credenciais do
   Notion.

## Publicação no Notion

Será criada uma página-hub filha da página existente `Azure`
(`2a1412e0-8c26-803b-a988-dc619a396e45`), com título
`Auditoria Processo-Agil x Wiki — 2026-08-21`.

As quatro páginas de delta serão filhas diretas desse hub, portanto terão a
mesma localização. Cada uma conterá:

- origem, horário da coleta e escopo;
- resumo executivo sem ocultar divergências;
- tabela de achados com classe, afirmação, implementação e evidência;
- seção específica para itens não verificáveis;
- limitações e próximos passos, sem converter recomendação em fato.

Antes de criar as páginas será lida a especificação Markdown do conector. Após
a criação, hub e páginas serão buscados novamente e conferidos por título,
parentesco e marcadores essenciais de conteúdo.

## Estratégia de testes e evidência

O desenvolvimento seguirá RED → GREEN → REFACTOR:

- carregamento seguro de `.env` e rejeição de PAT ausente;
- cliente limitado à allowlist método-rota, URL encoding e tratamento de
  paginação/erros;
- aceitação dos `POST` de WIQL e leitura em lote, com rejeição de qualquer
  `POST` mutante, `PUT`, `PATCH`, `DELETE` ou override de método;
- seleção exata e não ambígua do processo;
- normalização de WITs ativos, desabilitados e sistêmicos;
- comparação das quatro classes de resultado;
- detecção de drift do trecho-fonte;
- renderização separada e determinística das quatro páginas;
- teste de integração local com fixtures completas das respostas REST.

A verificação final incluirá testes completos, compilação Python, execução real
contra a API, inspeção dos quatro relatórios, busca de segredos, `git diff` e
releitura das cinco páginas criadas no Notion.

## Tratamento de falhas

- Falha HTTP, JSON inválido ou processo ausente interrompe a execução com
  operação, endpoint sanitizado e ação sugerida.
- Zero ou mais de um processo com nome exato é erro; não haverá escolha por
  aproximação.
- Endpoint sem resposta útil será documentado. Antes de recorrer à interface,
  serão avaliadas operações REST documentadas como somente leitura, ainda que
  usem `POST`. Computer Use só será empregado
  se a API não responder à dúvida necessária e nunca para editar o Azure.
- Afirmação não coberta pelo modelo do processo será registrada como
  `NAO_VERIFICAVEL_API_PROCESSO`, não inferida.
- Falha ao publicar uma página no Notion não será apresentada como publicação
  concluída; páginas criadas serão verificadas individualmente.

## Git e segurança

- Todos os arquivos já presentes são considerados trabalho do usuário.
- Não haverá commit, push, branch, rebase ou PR sem autorização específica.
- `.gitignore` cobrirá segredos por nome e extensão, ambientes virtuais,
  caches, builds, logs, bancos locais e arquivos de editor/SO.
- O verificador procurará padrões de PAT/token/credencial apenas em arquivos
  versionáveis, sem imprimir o conteúdo de `.env`.

## Referências oficiais da API

- [Get started with the REST APIs for Azure DevOps](https://learn.microsoft.com/en-us/azure/devops/integrate/how-to/call-rest-api?view=azure-devops)
  — distingue `POST` de criação de `POST` para consultas avançadas.
- [WIQL — Query By Wiql](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/wiql/query-by-wiql?view=azure-devops-rest-7.1)
  — `POST` que retorna `WorkItemQueryResult` sem salvar uma query.
- [Work Items — Get Work Items Batch](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/get-work-items-batch?view=azure-devops-rest-7.1)
  — `POST` que recupera até 200 work items.
- [Wiki Pages — Get Page By Id](https://learn.microsoft.com/en-us/rest/api/azure/devops/wiki/pages/get-page-by-id?view=azure-devops-rest-7.1).
- [Process Behaviors — List](https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/behaviors/list?view=azure-devops-rest-7.1).
- [Work Item Type Behaviors — List](https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/work-item-types-behaviors/list?view=azure-devops-rest-7.1).
- [Process Rules — List](https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/rules/list?view=azure-devops-rest-7.1).
- [Process Fields — List](https://learn.microsoft.com/en-us/rest/api/azure/devops/processes/fields/list?view=azure-devops-rest-7.1).

## Alternativas descartadas

1. **Relatório apenas manual:** não permite atualizar a auditoria com confiança.
2. **Somente dump das APIs:** preserva dados, mas não explica o significado do
   delta nem separa ausência de representação de divergência.
3. **Parser irrestrito de linguagem natural:** criaria comparações instáveis e
   falsos positivos. O catálogo explícito torna decisões auditáveis.
4. **Automação Python do Notion com token local:** exigiria um novo segredo e
   duplicaria o conector autenticado já disponível.
5. **Computer Use desde o início:** seria menos determinístico e contrariaria a
   preferência pela API REST enquanto ela responde.

## Critérios de conclusão

O trabalho só estará concluído quando:

- as quatro páginas tiverem sido lidas pela API;
- todas as facetas relevantes do processo tiverem snapshot atual;
- houver quatro relatórios locais distintos e rastreáveis;
- o projeto contiver setup idempotente e execução de auditoria com um comando;
- testes e verificações de segurança passarem com evidência fresca;
- `.gitignore` cobrir todas as categorias solicitadas;
- o hub e as quatro páginas irmãs existirem e forem relidos no Notion;
- nenhuma escrita tiver sido feita no Azure.
