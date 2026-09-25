# Mapa da documentação

Comece com o documento que corresponde à sua tarefa. Você não precisa ler as referências técnicas para operar o aplicativo.

## Usar o aplicativo

1. [Início rápido](quickstart.md) — instalar, configurar e executar em 5 passos.
2. [Configuração](configuration.md) — variáveis de ambiente, `.env`, lista de acesso, modos de operação.
3. [Executar a auditoria](guides/run-audit.md) — executar, ler os resultados e repetir auditorias.
4. [Construir relatórios](guides/build-reports.md) — reconstruir os quatro relatórios versionados em `deltas/`.
5. [Exportar o processo para uma LLM](guides/export-process-for-llm.md) — gerar o snapshot processo-apenas e o delta desde a exportação anterior, sem consultar a Wiki.
6. [Verificar o repositório](guides/verify-repository.md) — porta de procedência, verificação de saúde e revisão hostil de mudanças.
7. [Publicar no Notion](guides/publish-notion.md) — prepare e revise os relatórios para publicação canônica ou edição das cópias autorizadas sob Staging.
8. [Solução de problemas](troubleshooting.md) — identifique um erro pela mensagem exata no terminal e siga um caminho de recuperação.
9. [Contrato de publicação no Notion](notion-publication.md) — referência completa do contrato de publicação.
10. [Referência de evidências do Notion](reference/notion-evidence.md) — caminhos locais exatos, campos JSON obrigatórios e envelopes de conector brutos para a porta rigorosa.

## Entender a auditoria

- [Método delta comprovado por evidências](reference/delta-method.md) explica o que é comparado e o que cada status significa.
- [Runtime determinístico](audit-runtime.md) explica o pipeline, saídas e códigos de saída.
- [Arquitetura da aplicação](architecture.md) explica limites, fluxo de dados e regras de manutenção.
- [Cobertura documental](document-coverage.md) explica como mudanças de Wiki não mapeadas bloqueiam a publicação.
- [Contrato da API Azure DevOps](reference/api-contract.md) lista cada endpoint aprovado e o limite de autenticação.

## Trilha de auditoria

Estas são evidências históricas, não instruções de operação:

- [Auditoria de conclusão — 2026-09-09](archive/completion-audit-2026-09-09.md)
- [Revisão independente de branch — 2026-09-08](archive/adversarial-review-2026-09-08.md)
- [Decisões](decisions.md)
- [Trabalho anterior](archive/prior-work.md)
- Receitas de sessão: [2026-08-24](archive/session-2026-08-24.md), [2026-08-26](archive/session-2026-08-26.md), e [2026-09-08](archive/session-2026-09-08.md)
- [Receita de publicação de branch no GitHub](archive/github-branch-publication-2026-09-09.md)

Arquivos históricos podem descrever um estado anterior incompleto. Para instruções de operação atuais, prefira o guia completo e o código atual.
