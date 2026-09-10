# Guia completo do usuário

Este guia pressupõe nenhuma experiência em Python. Siga as seções em ordem para uma primeira execução. Os comandos são seguros para copiar exatamente, a menos que um passo diga explicitamente para substituir um valor.

## O que este aplicativo faz

`doc-azure` responde uma pergunta fixa: onde as quatro páginas aprovadas da Wiki do Azure DevOps concordam com, diferem de, ou vão além do que a configuração herdada do `Processo-Agil` pode comprovar?

É um aplicativo de linha de comando, não um site. Você executa comandos em um terminal. Uma execução nova lê uma organização e projeto fixos no Azure DevOps, salva evidências locais privadas, avalia 222 reivindicações revisadas e escreve relatórios. Nunca edita o Azure DevOps.

## Lista de verificação de acesso

Você precisa de todos estes itens antes de uma execução de rede nova:

- Acesso ao repositório privado `fcoalcantarajr/doc-azure` no GitHub;
- Membro da organização `bancodonordeste` no Azure DevOps;
- Acesso de leitura ao projeto `Torre CCR - Concessão de Crédito`;
- Acesso de leitura às páginas de Wiki aprovadas e ao processo `Processo-Agil`;
- Permissão para criar um PAT no Azure DevOps;
- Um PAT limitado à organização, com data de expiração, escopos **Wiki: Read** e **Work Items: Read**.

Se algum item estiver faltando, envie este pedido ao administrador responsável:

> Preciso de acesso somente leitura à organização `bancodonordeste` no Azure DevOps, projeto `Torre CCR - Concessão de Crédito`, à Wiki do projeto e aos metadados do processo herdado `Processo-Agil`. Também preciso de permissão para criar um PAT de curta duração com apenas os escopos Wiki: Read e Work Items: Read. Não preciso de permissão para criar, atualizar ou deletar conteúdo no Azure DevOps.

A publicação no Notion tem pré-requisitos adicionais. Leia [Publicar no Notion](#publicar-no-notion) somente se a publicação fizer parte da sua tarefa.

## Instalar as ferramentas

O aplicativo roda nativamente no macOS e Linux. No Windows, primeiro instale o [WSL com Ubuntu](https://learn.microsoft.com/en-us/windows/wsl/install), abra o terminal Ubuntu e execute todas as etapas do projeto lá. O PowerShell e o Command Prompt nativos do Windows não são suportados porque o bloqueio de snapshots usa a interface Unix `fcntl`.

### 1. Instalar Git

Execute `git --version`. Se imprimir uma versão, continue.

- **macOS:** executar `git --version` abre o instalador do Command Line Tools quando o Git está ausente.
- **Windows com WSL:** abra o Ubuntu e execute `sudo apt update && sudo apt install git`.
- **Debian ou Ubuntu:** execute `sudo apt install git`.
- **Outros sistemas:** use o [guia oficial de instalação do Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git).

### 2. Instalar uv

Use uma opção oficial:

```sh
# macOS ou Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Feche e reabra o terminal. Execute `uv --version`. Se o comando ainda não for encontrado, siga o [guia oficial de instalação do uv](https://docs.astral.sh/uv/getting-started/installation/).

Você não precisa instalar o Python separadamente. O projeto solicita Python 3.13 em `.python-version`; a versão mínima suportada é Python 3.11. O `uv` baixa um Python compatível quando necessário.

## Baixar e preparar o projeto

### 1. Clonar o repositório privado

O caminho recomendado é o GitHub CLI. Instale-o a partir das [instruções oficiais](https://cli.github.com/), depois execute:

```sh
gh auth login
```

Escolha GitHub.com, HTTPS, autenticação no navegador e permita que o GitHub CLI configure as credenciais do Git. Confirme que a conta tem acesso ao repositório privado, depois clone:

```sh
gh repo clone fcoalcantarajr/doc-azure
cd doc-azure
```

Se sua organização proíbe o GitHub CLI, use o token HTTPS aprovado ou o método SSH do [guia de autenticação do GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github). Uma senha de conta não é aceita para operações Git via HTTPS. Nunca coloque um token do GitHub na URL de clone.

Já tem a pasta? Abra um terminal nela e confirme:

```sh
git rev-parse --show-toplevel
```

O caminho impresso deve terminar em `doc-azure`.

### 2. Instalar as dependências bloqueadas

```sh
uv sync --locked
```

Resultado esperado: o `uv` cria ou atualiza `.venv` e completa sem erro. Você não precisa ativar este ambiente; todo comando do projeto começa com `uv run`.

### 3. Criar o arquivo de configuração privado

```sh
cp .env.example .env
```

Abra `.env` em um editor de texto. Substitua o placeholder após `AZDO_PAT=` pelo seu PAT. Mantenha a configuração em uma linha:

```dotenv
AZDO_PAT=seu_token_real_aqui
```

Não adicione aspas, a menos que o token as exija. Nunca compartilhe o arquivo ou seu conteúdo. O aplicativo aceita `AZDO_PAT` do ambiente do processo, mas o `.env` é mais fácil para uma primeira execução.

Para abrir o arquivo pelo terminal, use `open -e .env` no macOS ou `nano .env` no Linux e WSL. Salve e feche o editor antes de continuar.

Se você operará apenas offline com snapshots aprovados, não precisa de um PAT. Pule esta etapa de configuração e a validação abaixo.

### 4. Validar a configuração

```sh
uv run --no-sync python scripts/setup.py
```

Linha final esperada:

```text
CONFIGURATION_OK
```

Esta etapa verifica apenas o formato local e cria diretórios de saída ignorados. Não prova que o PAT está atual ou tem permissão remota.

## Executar a auditoria

### Auditoria atualizada

```sh
uv run python scripts/run_audit.py --refresh
```

`--refresh` busca as quatro páginas de Wiki e o modelo completo de processo atual. O aplicativo registra caminhos de requisição sanitizados, valida cada resposta e publica uma nova execução local somente após a evidência estar completa.

A saída final tem um status, um hash SHA-256 lógico e o caminho para `out/audit/CURRENT`. Exemplo:

```text
DELTAS: <hash de 64 caracteres>
.../doc-azure/out/audit/CURRENT
```

Não assuma que algum código de saída diferente de zero significa uma falha. Interprete o status usando a próxima seção.

### Auditoria offline

Execute com snapshots completos existentes sem acesso à rede:

```sh
uv run python scripts/run_audit.py --offline
```

O modo offline nunca contata o Azure DevOps. Falha se esta cópia do projeto não contiver snapshots completos ignorados em `out/wiki` e `out/process`. Um clone novo não os contém.

Para operação apenas offline, obtenha uma cópia privada aprovada de ambos os diretórios, coloque-os nos caminhos exatos e execute o comando offline diretamente. Não crie `.env` nem execute `scripts/setup.py`; nenhum é necessário no modo offline.

### Auditoria com cache

Reutilize evidências em cache completas e busque apenas partes faltantes:

```sh
uv run python scripts/run_audit.py
```

Use `--refresh` quando a decisão requer estado atual do Azure. Use `--offline` quando o acesso à rede é proibido. Use sem modo apenas para recuperação ou diagnóstico com cache.

## Ler os resultados

### 1. Interpretar o status no terminal

| Saída | Status | Significado | Próxima ação |
| ---: | --- | --- | --- |
| 0 | `CLEAN` | A cobertura está completa e toda reivindicação avaliada concorda. | Revisar e reter os relatórios. |
| 1 | `DELTAS` | A execução completou; pelo menos um achado é divergente, ambíguo ou não verificável pela API de processo. | Ler `global.md`, depois os quatro relatórios de página. |
| 2 | `COVERAGE_GAP` | Uma mudança de Wiki ou processo está fora do contrato de cobertura revisado. | Parar a publicação e pedir a um mantenedor para revisar a fonte e a baseline alteradas. |
| 3 | `ACQUISITION_VALIDATION_FAILED` | O acesso Azure, rede, resposta ou validação de snapshot falhou. | Usar [Solução de problemas](troubleshooting.md). |
| 4 | `INTERNAL_ERROR` | O aplicativo não pôde completar ou publicar sua saída local. | Preservar a mensagem do terminal e usar [Solução de problemas](troubleshooting.md). |

`DELTAS` é o resultado normal quando a auditoria encontra diferenças úteis. Não é uma falha de execução.

### 2. Encontrar a execução atual

`out/audit/CURRENT` contém o identificador da execução selecionada. Para imprimir o diretório do relatório atual em qualquer sistema operacional suportado, execute:

```sh
uv run python -c "from pathlib import Path; p=Path('out/audit'); print(p/'snapshots'/(p/'CURRENT').read_text().strip())"
```

Abra `global.md` nesse diretório primeiro. Ele resume a cobertura e os quatro relatórios. Depois abra `leiame.md`, `politicas.md`, `changelog.md`, e `apendice.md` para evidências detalhadas. `run.json` contém a mesma execução em formato legível por máquina.

### 3. Interpretar cada achado

| Status do achado | O que a evidência sustenta |
| --- | --- |
| `CONFIRMADO` | Os valores documentados e implementados concordam exatamente. |
| `DIVERGENTE` | Os valores são comparáveis e diferem. |
| `NAO_VERIFICAVEL_API_PROCESSO` | A API de processo atual não representa a dimensão documental. Isso não é prova de ausência. |
| `AMBIGUO` | A evidência disponível sustenta mais de uma interpretação material. |

Todo achado aponta para evidência Wiki local exata. Achados comparáveis também apontam para JSON de processo exato. Trate nomes de funcionários e evidências brutas como privados.

## Construir os relatórios versionados

O runtime completo cria um bundle de diagnóstico ignorado. Para reconstruir os quatro relatórios versionados em `deltas/` a partir de snapshots verificados, execute:

```sh
uv run python scripts/03_build_delta.py --coverage-baseline config/document-coverage.json
```

Resultado esperado: os quatro caminhos sob `deltas/`. Este comando não faz requisição de rede. Se detectar mudanças de fonte não mapeadas ou evidência inválida, para antes de substituir os relatórios. Uma falha de substituição restaura backups verificados para arquivos já tocados.

## Verificar o repositório

Esta é uma porta de procedência para mantenedores, não uma verificação de saúde de clone limpo. Só pode retornar `GATE_OK` em uma máquina que retenha as gerações exatas de Wiki e processo ignoradas nomeadas nos arquivos atuais em `deltas/`. Um `--refresh` novo cria novas gerações e não restaura aquela evidência histórica.

Se você tem as gerações retidas, execute:

```sh
uv run python verify.py
```

Marcador de sucesso esperado nessa máquina com evidência:

```text
GATE_OK
```

Para um clone sem os snapshots históricos, execute `uv run pytest -q` como verificação de saúde do código portátil e espere que todos os testes passem. Não chame esse resultado de `GATE_OK`; ele não prova procedência de relatório ou publicação.

A porta completa executa testes, valida o limite de requisição Azure, reconstrói e compara relatórios, verifica arquivos ignorados e escaneia por valores secretos rastreados. Se existir um manifesto de publicação local `out/notion`, a porta também o valida. Portanto um recibo externo obsoleto pode falhar este comando mesmo quando os testes Python passam; siga a mensagem correspondente em [Solução de problemas](troubleshooting.md).

## Publicar no Notion

Pule esta seção se você só precisa da auditoria local. A publicação altera quatro páginas existentes no Notion, então requer o contrato e a cadeia de provas separados.

Pré-requisitos:

- Acesso de edição ao hub `Azure` fixo e às suas quatro páginas de delta existentes;
- O workspace Notion conectado via MCP;
- O navegador integrado ao ChatGPT conectado ao Notion AI;
- Kimi K3 e Opus 5 disponíveis com esforço máximo;
- Acesso à URL do repositório privado do GitHub usada no pacote de revisão.

### 1. Preparar arquivos locais de publicação

```sh
uv run python scripts/04_prepare_notion.py --repository-url https://github.com/fcoalcantarajr/doc-azure
```

Este comando escreve apenas arquivos ignorados sob `out/notion`. Não contata o Notion e não publica.

### 2. Completar a porta externa

Siga o [contrato de publicação no Notion](notion-publication.md) exatamente. Resumidamente:

1. Envie o pacote idêntico para dois chats separados de Kimi K3 e Opus 5 com esforço máximo no navegador integrado.
2. Preserve o modelo, esforço, chat, pacote, prompt, resposta e recibos de tempo.
3. Reconcilie cada achado material contra a evidência de fonte; acordo por voto é insuficiente.
4. Atualize apenas os quatro IDs de página fixos pelo conector do Notion, depois busque-os e verifique o pai comum e duplicatas.

Use os caminhos e campos JSON exatos na [referência de evidências do Notion](notion-evidence-reference.md); a porta rigorosa rejeita campos faltantes e extras.

Se o modelo exato, esforço, sessão conectada ou identidade da página fixa não estiver disponível, pare. Não substitua um modelo nem crie páginas de reposição.

### 3. Provar a publicação

```sh
uv run python scripts/04_prepare_notion.py --verify-publication
uv run python verify.py --require-publication
```

Os marcadores de sucesso necessários são `NOTION_PUBLICATION_OK` e `GATE_OK`. Um arquivo preparado, veredicto, resposta de atualização ou marcador por si só não é prova de publicação atual.

## Repetir uma auditoria de rotina

1. Abra um terminal em `doc-azure`.
2. Execute `git status --short` e não descarte alterações que não reconheça.
3. Execute `uv sync --locked` após puxar uma nova revisão.
4. Execute `uv run python scripts/run_audit.py --refresh`.
5. Leia o status e o `global.md` atual; publique somente quando o contrato de publicação fizer parte da tarefa.

## Proteger e remover dados locais

- Revogue ou rotacione o PAT conforme a política da sua organização.
- Delete `.env` quando este computador não deve mais reter a credencial.
- Trate `out/` como evidência privada. Removê-lo deleta snapshots em cache, relatórios gerados e recibos de publicação; faça um backup aprovado primeiro se a trilha de auditoria precisar ser retida.
- Não commit `.env` nem `out/`. Execute `git status --short` antes de cada commit.
- Antes de commitar `deltas/` regenerados ou enviar corpos preparados ao Notion, inspecione o texto exato por nomes de funcionários, detalhes de contato, credenciais, identificadores pessoais ou outro material não aprovado para ambos os destinos.

O aplicativo não tem operação de limpeza remota porque não cria ou altera dados do Azure DevOps. As alterações de páginas do Notion são externas e são governadas pelo contrato de publicação de páginas fixas.