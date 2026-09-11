# doc-azure

Compare quatro páginas de Wiki aprovadas no Azure DevOps com a configuração atual do Processo-Agil. O aplicativo lê o Azure DevOps, cria evidências locais e produz quatro relatórios de auditoria. Não altera o Azure DevOps.

## Comece aqui

Escolha o caminho que corresponde ao que você precisa:

| Objetivo | Ler ou executar |
| --- | --- |
| Instalar e executar a primeira auditoria | [Guia completo do usuário](docs/user-guide.md) |
| Reusar as evidências locais sem acesso ao Azure | [Modos de operação](docs/configuration.md#modos-de-operação) |
| Executar uma auditoria Azure atualizada | `uv run python scripts/run_audit.py --refresh` |
| Entender um resultado ou código de saída | [Ler os resultados](docs/user-guide.md#ler-os-resultados) |
| Corrigir um erro | [Solução de problemas](docs/troubleshooting.md) |
| Preparar ou verificar a publicação no Notion | [Contrato de publicação no Notion](docs/notion-publication.md) |
| Manter o aplicativo | [Mapa da documentação técnica](docs/README.md) |

Se for sua primeira visita, siga o guia completo em ordem. Não inicie com um script em `scripts/` a menos que o guia indique.

## O que você precisa

- Um computador com macOS ou Linux e um terminal. No Windows, execute o aplicativo dentro do WSL; o Windows nativo não é suportado porque o bloqueio de snapshots usa a interface Unix `fcntl`.
- Git, GitHub CLI, `uv`, e Python 3.11+. O `uv` instala e seleciona a versão Python necessária, então uma instalação Python separada é opcional.
- Acesso de leitura à organização, projeto, Wiki e processo herdado do Azure DevOps.
- Um Personal Access Token (PAT) do Azure DevOps, de curta duração e com permissões mínimas, com escopos **Wiki: Read** e **Work Items: Read**.
- Acesso ao repositório privado. O Notion workspace e o acesso Notion AI são necessários apenas para publicação.

Você não resolve permissões de organização ou projeto faltando com um comando. A [lista de verificação de acesso](docs/user-guide.md#lista-de-verificação-de-acesso) diz exatamente o que pedir a um administrador.

## Primeira execução

Execute estes comandos no terminal. Substitua apenas o passo de clonagem do repositório se já tiver esta pasta.

```sh
gh auth login
gh repo clone fcoalcantarajr/doc-azure
cd doc-azure
uv sync --locked
cp .env.example .env
```

No Windows, execute esses comandos Linux dentro do WSL, não no PowerShell. Abra `.env`, substitua o placeholder pelo seu PAT, salve o arquivo, e então execute:

```sh
uv run --no-sync python scripts/setup.py
uv run python scripts/run_audit.py --refresh
```

`DELTAS` e código de saída `1` são um resultado de auditoria válido: o aplicativo completou e encontrou diferenças ou limites de evidência. Não significa que o programa falhou. Consulte [Ler os resultados](docs/user-guide.md#ler-os-resultados) antes de decidir o que fazer.

## Limite de segurança

O cliente Azure falha fechado fora da lista de permissões explícita. A coleta usa requisições GET para leituras de Wiki e processo; apenas as duas rotas POST de consulta (WIQL e workitemsbatch) estão permitidas pelo contrato de segurança compartilhado. Criação, atualização, deleção, redirecionamentos, URLs absolutas e overrides de método são rejeitados antes do transporte.

Mantenha `.env` e tudo em `out/` privado. São ignorados pelo Git porque evidências podem incluir dados de funcionários e `.env` contém um segredo. Nunca cole um PAT em um comando, issue, chat, log, relatório ou página do Notion. Antes de commitar ou publicar arquivos regenerados em `deltas/`, inspecione-os por nomes de funcionários, detalhes de contato, identificadores, credenciais ou outro conteúdo não aprovado para o repositório e as quatro páginas de destino.

A publicação no Notion é separada da auditoria principal. Ela atualiza apenas quatro páginas fixas existentes após revisões independentes de Kimi K3 e Opus 5, reconciliation, read-back do conector, e a porta de publicação rigorosa. Preparar arquivos locais do Notion não publica nada.

## O que o aplicativo produz

- `out/wiki/` e `out/process/`: snapshots imutáveis de fontes ignorados.
- `out/audit/`: bundles de diagnóstico e resultado por execução, ignorados.
- `deltas/`: quatro relatórios em português brasileiro versionados.
- `out/notion/`: corpos de publicação, pacotes de revisão e recibos, ignorados.

A auditoria avalia 222 reivindicações explícitas. Cada conclusão tem um ponteiro de fonte Wiki exato; achados comparáveis também têm um ponteiro de evidência de processo exato. Consulte [Método delta comprovado por evidências](docs/reference/delta-method.md) para as regras técnicas.