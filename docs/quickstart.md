# Início rápido

Este guia leva você da instalação à primeira auditoria em 5 passos. Se encontrar um erro, consulte a [solução de problemas](troubleshooting.md).

O **terminal** é o aplicativo em que você digita os comandos mostrados neste
guia: Terminal no macOS ou Ubuntu no Linux e no WSL.

## 1. Instalar as ferramentas

### Git

Execute `git --version`. Se imprimir uma versão, continue.

- **macOS:** executar `git --version` abre o instalador do Command Line Tools quando o Git está ausente.
- **Windows com WSL:** abra o Ubuntu e execute `sudo apt update && sudo apt install git`.
- **Debian ou Ubuntu:** execute `sudo apt install git`.
- **Outros sistemas:** use o [guia oficial de instalação do Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git).

### uv

```sh
# macOS ou Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Feche e reabra o terminal. Execute `uv --version`. Se o comando ainda não for encontrado, siga o [guia oficial de instalação do uv](https://docs.astral.sh/uv/getting-started/installation/).

Você não precisa instalar o Python separadamente. O projeto solicita Python 3.13 em `.python-version`; a versão mínima suportada é Python 3.11. O `uv` baixa um Python compatível quando necessário.

## 2. Clonar o repositório

Clone o repositório por HTTPS:

```sh
git clone https://github.com/fcoalcantarajr/doc-azure.git
cd doc-azure
```

Se o Git solicitar autenticação por causa das permissões atuais do repositório, use o GitHub CLI instalado a partir das [instruções oficiais](https://cli.github.com/) e execute `gh auth login`, ou configure SSH seguindo o [guia de autenticação do GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github). Uma senha de conta não é aceita para operações Git via HTTPS. Nunca coloque um token do GitHub na URL de clone.

Já tem a pasta? Abra um terminal nela e confirme:

```sh
git rev-parse --show-toplevel
```

O caminho impresso deve terminar em `doc-azure`.

## 3. Instalar dependências bloqueadas

```sh
uv sync --locked
```

Resultado esperado: o `uv` cria ou atualiza `.venv` e completa sem erro. Você não precisa ativar este ambiente; todo comando do projeto começa com `uv run`.

## 4. Configurar o arquivo privado

Ainda não tem um PAT? Siga [Criar o PAT](configuration.md#criar-o-pat) antes de
copiar o arquivo.

```sh
cp .env.example .env
```

Abra `.env` em um editor de texto. Substitua o placeholder após `AZDO_PAT=` pelo seu PAT. Mantenha a configuração em uma linha:

```dotenv
AZDO_PAT=seu_token_real_aqui
```

Não adicione aspas, a menos que o token as exija. Nunca compartilhe o arquivo ou seu conteúdo. O aplicativo aceita `AZDO_PAT` do ambiente do processo, mas o `.env` é mais fácil para uma primeira execução.

Para abrir o arquivo pelo terminal, use `open -e .env` no macOS ou `nano .env` no Linux e WSL. Salve e feche o editor antes de continuar.

Se você operará apenas offline com snapshots aprovados, não precisa de um PAT. Pule esta etapa e a validação abaixo.

## 5. Validar e executar

### Validar a configuração

```sh
uv run --no-sync python scripts/setup.py
```

Linha final esperada:

```text
CONFIGURATION_OK
```

Esta etapa verifica apenas o formato local e cria diretórios de saída ignorados. Não prova que o PAT está atual ou tem permissão remota.

### Executar uma auditoria atualizada

```sh
uv run python scripts/run_audit.py --refresh
```

A saída final mostra um status, um hash SHA-256 lógico e o caminho para `out/audit/CURRENT`. Exemplo:

```text
DELTAS: <hash de 64 caracteres>
.../doc-azure/out/audit/CURRENT
```

`DELTAS` e código de saída `1` são um resultado válido: a auditoria completou e encontrou diferenças. Consulte [Ler os resultados](guides/run-audit.md#como-ler-o-resultado) para interpretar.

## Próximos passos

| Precisa de... | Consulte |
| --- | --- |
| Explicar os códigos de saída | [Ler os resultados](guides/run-audit.md#como-ler-o-resultado) |
| Executar offline | [Modos de operação](configuration.md#modos-de-operação) |
| Corrigir um erro | [Solução de problemas](troubleshooting.md) |
| Publicar no Notion | [Guia de publicação](guides/publish-notion.md) |
