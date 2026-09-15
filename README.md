# doc-azure

Compare quatro páginas de Wiki aprovadas no Azure DevOps com a configuração atual do Processo-Agil. O aplicativo lê o Azure DevOps, cria evidências locais e produz quatro relatórios de auditoria. Não altera o Azure DevOps.

## Comece aqui

Escolha o caminho que corresponde ao que você precisa:

| Objetivo | Ler ou executar |
| --- | --- |
| Instalar e executar a primeira auditoria | [Início rápido](docs/quickstart.md) |
| Reusar as evidências locais sem acesso ao Azure | [Modos de operação](docs/configuration.md#modos-de-operação) |
| Executar uma auditoria Azure atualizada | `uv run python scripts/run_audit.py --refresh` |
| Exportar somente o processo para uma LLM | [Guia de exportação](docs/guides/export-process-for-llm.md) |
| Entender um resultado ou código de saída | [Ler os resultados](docs/guides/run-audit.md#como-ler-o-resultado) |
| Corrigir um erro | [Solução de problemas](docs/troubleshooting.md) |
| Preparar, revisar e verificar a publicação no Notion | [Guia de publicação no Notion](docs/guides/publish-notion.md) |
| Manter o aplicativo | [Mapa da documentação técnica](docs/README.md) |

Se for sua primeira visita, siga o início rápido em ordem. Não inicie com um script em `scripts/` a menos que o guia indique.

## O que você precisa

- Um computador com macOS ou Linux e um terminal. No Windows, execute o aplicativo dentro do WSL; o Windows nativo não é suportado porque o bloqueio de snapshots usa a interface Unix `fcntl`.
- Git e `uv`. O GitHub CLI (`gh`) é o caminho recomendado para clonar o repositório, mas HTTPS com token aprovado e SSH também funcionam. O projeto requer Python 3.11+; o `uv` instala e seleciona a versão necessária, então uma instalação Python separada é opcional.
- Acesso de leitura à organização, projeto, Wiki e processo herdado do Azure DevOps.
- Um Personal Access Token (PAT) do Azure DevOps, de curta duração e com permissões mínimas, com escopos **Wiki: Read** e **Work Items: Read**.
- Acesso ao repositório privado.
- Somente para publicação: workspace do Notion, Notion AI, Codex com o conector
  Notion conectado, navegador integrado autenticado e os modelos Kimi K3 e
  Opus 5 disponíveis com esforço máximo. Veja todos os pré-requisitos no
  [guia de publicação](docs/guides/publish-notion.md#antes-de-começar).

Você não resolve permissões de organização ou projeto faltando com um comando. A [lista de verificação de acesso](docs/configuration.md) diz exatamente o que pedir a um administrador.

O aplicativo usa `httpx>=0.25.0` em produção. O grupo de desenvolvimento usa
`pytest>=8.0.0`. `uv sync --locked` instala as versões fixadas em `uv.lock`.

## Primeira execução

Siga o [início rápido](docs/quickstart.md). Ele apresenta uma ação por vez,
mostra o resultado esperado e explica como obter o acesso necessário. Ao final,
`DELTAS` e código de saída `1` significam que a auditoria terminou e encontrou
diferenças; não são falha do programa.

## Limite de segurança

O cliente Azure falha fechado fora da lista de permissões explícita. A coleta usa requisições GET para leituras de Wiki e processo; apenas as duas rotas POST de consulta (WIQL e workitemsbatch) estão permitidas pelo contrato de segurança compartilhado. Criação, atualização, deleção, URLs absolutas e overrides de método são rejeitados antes do transporte. Redirecionamentos não são seguidos e qualquer resposta 3xx é recusada.

Mantenha `.env` e tudo em `out/` privado. São ignorados pelo Git porque evidências podem incluir dados de funcionários e `.env` contém um segredo. Nunca cole um PAT em um comando, issue, chat, log, relatório ou página do Notion. Antes de commitar ou publicar arquivos regenerados em `deltas/`, inspecione-os por nomes de funcionários, detalhes de contato, identificadores, credenciais ou outro conteúdo não aprovado para o repositório e as quatro páginas de destino.

A publicação no Notion é separada da auditoria principal. Ela atualiza apenas quatro páginas fixas existentes após revisões independentes de Kimi K3 e Opus 5, reconciliação, releitura pelo conector e a porta de publicação rigorosa. Preparar arquivos locais do Notion não publica nada.

## O que o aplicativo produz

- `out/wiki/` e `out/process/`: snapshots imutáveis de fontes ignorados.
- `out/audit/`: bundles de diagnóstico e resultado por execução, ignorados.
- `out/process-llm/`: exportações Markdown do processo, ignoradas e independentes da Wiki.
- `deltas/`: quatro relatórios em português brasileiro versionados.
- `out/notion/`: corpos de publicação, pacotes de revisão e recibos, ignorados.

A auditoria avalia 222 reivindicações explícitas. Cada conclusão tem um ponteiro de fonte Wiki exato; achados comparáveis também têm um ponteiro de evidência de processo exato. Consulte [Método delta comprovado por evidências](docs/reference/delta-method.md) para as regras técnicas.
