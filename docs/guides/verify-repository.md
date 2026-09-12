# Verificar o repositório

Há duas verificações diferentes. Escolha a que corresponde à evidência disponível; uma não substitui a outra.

## Verificação portátil de um clone

Execute:

```sh
uv run pytest -q
```

Resultado esperado: todos os testes passam. Essa verificação funciona em um clone limpo depois de `uv sync --locked`, mas não prova a procedência dos relatórios versionados.

## Porta de procedência

`verify.py` compara os relatórios com as gerações históricas exatas de Wiki e processo registradas neles. Esses snapshots ficam ignorados pelo Git. Portanto, a porta só pode retornar `GATE_OK` na máquina que os retém ou depois de uma transferência privada aprovada.

Se `out/notion/fetched/hierarchy.json` não existe, execute:

```sh
uv run python verify.py
```

Se esse arquivo existe, há uma tentativa de publicação registrada. Use obrigatoriamente a porta rigorosa:

```sh
uv run python verify.py --require-publication
```

Resultado esperado em ambos os casos válidos:

```text
GATE_OK
```

O script retorna `0` no sucesso. `GATE_FAIL: <mensagem>` e código `1` identificam o primeiro invariável violado. A porta não executa `pytest`; rode os testes separadamente.

## O que a porta valida

Em ordem, `verify.py` verifica:

1. arquivos e layout obrigatórios;
2. cobertura do `.gitignore`;
3. baselines de cobertura;
4. allowlist REST somente leitura do Azure;
5. sintaxe e conteúdo executável dos módulos Python;
6. contrato documentado de status;
7. ausência de segredos literais em arquivos rastreados;
8. reconstrução e procedência dos quatro relatórios;
9. artefatos locais ou, com `--require-publication`, toda a evidência externa do Notion;
10. funcionamento de `--help` nos scripts públicos.

## Limite importante

Uma nova execução com `--refresh` cria novas gerações imutáveis. Ela não recria os IDs históricos citados nos relatórios atuais e não corrige, por si só, uma falha de procedência. Não renomeie, fabrique ou edite snapshots para fazer a porta passar.

## Se der errado

- `required files are missing`: restaure o arquivo versionado indicado; em clone parcial, refaça o clone.
- `coverage baseline files are missing`: restaure os três arquivos versionados em `config/`.
- `a secret environment file is tracked` ou `secret literal found`: remova o segredo do conteúdo e do índice Git sem imprimi-lo; depois rotacione a credencial exposta.
- `verified report rebuild failed`, `provenance is unverifiable` ou erro de snapshot histórico: use a máquina de evidência ou uma transferência privada aprovada. Num clone comum, limite a conclusão aos testes portáteis.
- `deltas/<arquivo> differs from verified rebuild`: não edite o relatório à mão. Reconstrua-o a partir das gerações corretas e da baseline obrigatória.
- `Notion verification failed`: preserve os recibos e siga o [guia de publicação](publish-notion.md) desde a preparação; não misture evidências de pacotes diferentes.
- outra mensagem: procure o texto exato em [Solução de problemas](../troubleshooting.md).

## Próximo passo

Se a publicação externa estiver no escopo, siga [Publicar no Notion](publish-notion.md).
