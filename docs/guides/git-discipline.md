# Disciplina Git para commits de agentes

Este repositório valida a forma dos commits e procura segredos antes de cada
commit. A política de projeto também proíbe operações comuns de reescrita ou
descarte de histórico no Codex.

## Instalação local

Pré-requisitos: `uv`, Git, `gitleaks` disponível no `PATH` e acesso ao GitHub
para instalar o hook de Conventional Commits.

Na raiz do repositório:

```sh
uv sync --locked
uv run pre-commit install --install-hooks
```

O instalador registra os hooks locais de `pre-commit` e `commit-msg`. A varredura
Gitleaks lê somente o conteúdo staged e redige os segredos detectados na saída.
O hook de mensagem exige Conventional Commits. Se um hook bloquear um commit,
corrija o conteúdo e crie um commit novo; não use `--no-verify`, `-n` ou
`SKIP`.

## Escrever a mensagem

Use `.gitmessage` como modelo explícito:

```sh
git commit --template=.gitmessage
```

Cada commit deve conter um resumo imperativo Conventional Commit, explicar por
que a mudança é necessária, apontar a especificação ou decisão e incluir os
trailers `Agent:` e `Model:`. Faça um commit pequeno por gate verificado, não
um commit acumulado ao fim da sessão.

## Verificações Python

Os hooks Ruff e mypy estão configurados no estágio manual enquanto a dívida
existente for tratada. A comparação entre a base `e37435bb31fcb0867c1e313ddd9e311e4f6d72f1`
e esta árvore, em 2026-10-20, encontrou os mesmos 170 diagnósticos Ruff, os
mesmos 47 arquivos que precisam de formatação e os mesmos 78 erros mypy em 15
módulos. Esses diagnósticos já existiam na base; a árvore atual não adiciona
falhas a essas verificações. Torná-los gates automáticos agora bloquearia
commits por problemas preexistentes e exigiria alterações amplas sem relação
com esta entrega. A decisão e os links para a documentação oficial estão em
`docs/decisions.md`.

Para executar essas verificações deliberadamente:

```sh
uv run pre-commit run --hook-stage manual --all-files
```

Esse estágio pode terminar com falha até a linha de base ser corrigida. Não use
isso como substituto para a revisão de código ou para os testes exigidos por
uma mudança de comportamento.

## Regras Codex e limites

`.codex/rules/git-safety.rules` bloqueia, na camada de regras do Codex, os
comandos explícitos de bypass de hook, force-push, rebase, hard reset e filtros
de reescrita listados ali. Prefixos Codex não são um parser completo das opções
Git: variantes não listadas, uma variável `SKIP=...` antes do comando ou outro
valor em `git -c core.hooksPath=...` podem não corresponder à regra. Não use
essas formas equivalentes de bypass. Regras locais só são aplicadas quando o
projeto está marcado como confiável no Codex; essa camada não substitui as
permissões do servidor GitHub nem protege outros clientes Git. Use push normal
somente quando autorizado e respeite as proteções remotas.

Nunca versione `.env`, arquivos privados ou qualquer caminho sob `out/`.
