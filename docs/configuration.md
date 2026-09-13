# Configuração

## Variável de ambiente

O aplicativo usa uma única variável de ambiente: `AZDO_PAT`.

`AZDO_PAT` é um Personal Access Token (PAT) do Azure DevOps. O token precisa dos seguintes escopos:

- **Wiki: Read** — leitura das páginas de Wiki aprovadas.
- **Work Items: Read** — consulta de itens de trabalho via WIQL.

O token deve ser de curta duração e limitado à organização `bancodonordeste`.

## Criar o PAT

Crie o token somente depois que sua conta tiver acesso à organização e ao
projeto:

1. Entre em `https://dev.azure.com/bancodonordeste`.
2. Abra **User settings** no canto superior direito.
3. Abra **Personal access tokens**.
4. Selecione **New Token**.
5. Em **Organization**, selecione `bancodonordeste`.
6. Escolha uma data de expiração curta, compatível com a política da organização.
7. Em **Scopes**, selecione **Custom defined**.
8. Marque somente **Wiki: Read** e **Work Items: Read**.
9. Crie o token e copie o valor uma única vez para o arquivo `.env` descrito abaixo.

Não marque **Full access**. Não coloque o token em URL, comando, issue, chat ou
documento. A Microsoft mantém o fluxo atualizado no
[guia oficial de PAT do Azure DevOps](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops).

## Arquivo .env

Copie o template:

```sh
cp .env.example .env
```

O conteúdo do `.env` deve ter esta forma exata:

```dotenv
AZDO_PAT=seu_token_real_aqui
```

Regras do arquivo:

- Uma única linha com `AZDO_PAT=` seguido do token.
- Não adicione aspas, a menos que o token as exija.
- Linhas em branco e linhas que começam com `#` são ignoradas.
- Não adicione outras variáveis; o aplicativo lê apenas `AZDO_PAT`.
- Nunca commit o arquivo `.env`. Ele está no `.gitignore`.

O aplicativo também aceita `AZDO_PAT` injetada pelo ambiente do processo. Esse
modo é destinado a automação que já usa um gerenciador de segredos; não cole o
PAT na linha de comando ou no histórico do shell. Se o shell já tiver
`AZDO_PAT` definida, esse valor tem prioridade sobre o arquivo `.env`. Execute
`unset AZDO_PAT` antes de usar o valor do arquivo.

## Lista de verificação de acesso

Você precisa de todos estes itens antes de uma execução de rede:

- Acesso ao repositório privado `fcoalcantarajr/doc-azure` no GitHub.
- Membro da organização `bancodonordeste` no Azure DevOps.
- Acesso de leitura ao projeto `Torre CCR - Concessão de Crédito`.
- Acesso de leitura às páginas de Wiki aprovadas e ao processo `Processo-Agil`.
- Permissão para criar um PAT no Azure DevOps.
- Um PAT limitado à organização, com data de expiração, escopos **Wiki: Read** e **Work Items: Read**.

Se algum item estiver faltando, envie este pedido ao administrador responsável:

> Preciso de acesso somente leitura à organização `bancodonordeste` no Azure DevOps, projeto `Torre CCR - Concessão de Crédito`, à Wiki do projeto e aos metadados do processo herdado `Processo-Agil`. Também preciso de permissão para criar um PAT de curta duração com apenas os escopos Wiki: Read e Work Items: Read. Não preciso de permissão para criar, atualizar ou deletar conteúdo no Azure DevOps.

## Configurações fixas

A organização, projeto, IDs de páginas e nome do processo são fixados no código. Você não pode alterá-los:

| Parâmetro | Valor |
| --- | --- |
| Organização | `bancodonordeste` |
| Projeto | `Torre CCR - Concessão de Crédito` |
| IDs de páginas | 35, 10, 9, 37 |
| Nome do processo | `Processo-Agil` |
| Versão da API | `7.1` |

## Modos de operação

O aplicativo tem três modos de execução:

### Auditoria atualizada

```sh
uv run python scripts/run_audit.py --refresh
```

Busca todas as quatro páginas de Wiki e o modelo completo de processo atual.
Requer um PAT válido e conexão de rede. Cria uma nova geração imutável e move o
ponteiro `CURRENT`; não sobrescreve a geração anterior.

### Auditoria offline

```sh
uv run python scripts/run_audit.py --offline
```

Usa snapshots locais completos sem acesso à rede. Falha se a cópia não contiver snapshots completos em `out/wiki/` e `out/process/`. Um clone novo não contém esses snapshots. Não precisa de `.env` nem de `scripts/setup.py`.

Para operação apenas offline, obtenha uma cópia privada aprovada de ambos os diretórios, coloque-os nos caminhos exatos e execute o comando offline diretamente.

Peça essa cópia à pessoa ou equipe que custodia a máquina de evidências. A transferência deve levar os diretórios `out/wiki/` e `out/process/` completos, preservando `CURRENT`, `snapshots/<identificador>/`, `manifest.json` e todos os artefatos manifestados. Use somente o canal privado aprovado pela organização; não envie as evidências por Git, issue, chat ou e-mail comum. Depois de colocar os dois diretórios na raiz do clone, confirme:

```sh
ls out/wiki/CURRENT out/process/CURRENT
uv run python scripts/run_audit.py --offline
```

O primeiro comando deve listar os dois ponteiros. O segundo valida manifests, hashes e conteúdo ao executar a auditoria; não edite nem renomeie arquivos para fazê-lo passar.

### Auditoria com cache

```sh
uv run python scripts/run_audit.py
```

Reusa evidências em cache completas e busca apenas partes faltantes. Use `--refresh` quando a decisão requer estado atual do Azure. Use `--offline` quando o acesso à rede é proibido. Use sem modo apenas para recuperação ou diagnóstico com cache.

## Validação da configuração

```sh
uv run --no-sync python scripts/setup.py
```

O comando imprime os três diretórios criados. A linha final esperada é:

```text
CONFIGURATION_OK
```

Esta etapa verifica apenas o formato do `.env` e cria os diretórios de saída necessários. Não prova que o PAT está atual ou tem permissão remota.
