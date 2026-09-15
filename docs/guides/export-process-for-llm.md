# Exportar o processo para uma LLM

Este comando transforma o snapshot completo do `Processo-Agil` em Markdown
pronto para leitura por uma LLM. Ele não lê a Wiki, não calcula diferenças e não
altera o Azure DevOps.

## Escolha o modo

### Usar o snapshot local, sem rede

```sh
uv run python scripts/export_process_for_llm.py
```

Este é o modo recomendado quando `out/process/CURRENT` já existe. Ele valida o
manifesto e todos os artefatos antes de exportar. Não lê `.env`, não exige PAT e
faz zero requisições.

### Coletar o processo atual e exportar

```sh
uv run python scripts/export_process_for_llm.py --refresh
```

Este modo requer `AZDO_PAT` e acesso ao Azure DevOps. Ele faz somente as
requisições GET do processo já autorizadas para `02_fetch_process.py`. Não lê
Wiki, work items ou Notion e não gera deltas.

Para operar outra cópia do projeto, acrescente `--root DIRETORIO`. Veja todas as
opções sem credencial:

```sh
uv run python scripts/export_process_for_llm.py --help
```

## Resultado esperado

No sucesso, o comando retorna código `0` e imprime:

```text
LLM_EXPORT_OK
<caminho absoluto>/out/process-llm/snapshots/<geração>/bundle.md
<caminho absoluto>/out/process-llm/snapshots/<geração>/work-item-types
```

`out/process-llm/CURRENT` contém o identificador da exportação selecionada. Os
arquivos ficam nesta estrutura:

```text
out/process-llm/
├── CURRENT
└── snapshots/<geração>/
    ├── manifest.json
    ├── README.md
    ├── bundle.md
    ├── process-summary.md
    ├── provenance.json
    └── work-item-types/
        └── <referenceName>.md
```

Se a geração e o hash do snapshot de origem forem os mesmos, o comando reutiliza
a exportação existente byte a byte. Se ela já for a atual, `CURRENT` não muda; se
estiver no histórico, somente o ponteiro volta a selecioná-la. Quando a origem
muda e ainda não foi exportada, uma geração nova é publicada e as anteriores são
preservadas.

## Qual arquivo enviar

- Envie somente `bundle.md` quando a LLM aceitar um arquivo desse tamanho. Ele é
  autocontido e inclui processo, behaviors e todos os tipos.
- Envie `process-summary.md` com os arquivos necessários de `work-item-types/`
  quando houver limite de contexto ou quando a pergunta tratar de poucos tipos.
- Use `provenance.json` para registrar qual snapshot originou o conteúdo.
- Não envie `manifest.json` como substituto do conteúdo: ele contém hashes, não
  a configuração.

Cada conjunto informa o caminho do JSON de origem e seu JSON Pointer. Estados e
campos aparecem em tabelas; regras preservam condições e ações; layouts mantêm a
hierarquia; behaviors globais e associações por tipo também são incluídos. O
exportador distingue propriedade ausente, `null`, `false`, zero e string vazia.

## Limites e privacidade

A exportação descreve a configuração observada na API. Ela não prova intenção
institucional, governança, uso real ou correção. Um campo configurado não prova
que as equipes o preenchem; uma regra presente não prova sua efetividade prática.

Nomes, labels, defaults, condições e ações são preservados porque o destino
pressuposto é uma LLM corporativa aprovada. A propriedade de transporte chamada
exatamente `url` é removida recursivamente; outras propriedades, inclusive
extensões desconhecidas, são preservadas em `additional_properties`. Isso não é
anonimização. Antes do envio:

1. abra os arquivos que serão enviados;
2. procure nomes, defaults, identificadores ou regras que não devam sair do
   ambiente aprovado;
3. confirme a política de dados da ferramenta de destino;
4. envie apenas o subconjunto necessário.

Nunca envie `.env`, PAT, headers, corpos de erro ou diretórios inteiros de
evidência. Tudo sob `out/` é privado e ignorado pelo Git.

## Verificação rápida do conteúdo

Peça à LLM, usando apenas os arquivos escolhidos, para informar:

1. nome e ID do processo;
2. estado ativo/desabilitado do tipo analisado;
3. estados, campos, regras, layout e behaviors;
4. caminhos de origem e JSON Pointers;
5. limitações declaradas.

Se uma resposta não trouxer uma dessas dimensões, acrescente o arquivo individual
do tipo ou use `bundle.md`. Não peça que a LLM invente intenção ou prática a partir
da configuração.

## Falhas

Em falha, o comando retorna código `1`, imprime
`LLM_EXPORT_FAILED: <mensagem sanitizada>` no stderr e mantém a exportação anterior.

- `out/process/CURRENT está ausente`: execute com `--refresh` se tiver acesso ou obtenha uma
  cópia privada completa de `out/process/`.
- `out/process-llm/CURRENT está inválido; consulte o troubleshooting`: preserve
  o ponteiro com outro nome e gere novamente conforme a
  [recuperação documentada](../troubleshooting.md#llm_export_failed-).
- `o snapshot do processo está ausente, incompleto ou inválido`: não edite a
  evidência; faça uma coleta nova ou restaure a geração íntegra.
- `não foi possível publicar a exportação local com segurança`: confira espaço,
  permissões e se algum componente de `out/process-llm` virou link simbólico ou
  arquivo comum.
- `uma geração histórica mudou durante a validação; repita o comando`: preserve
  a geração para diagnóstico e repita; o exportador recusou selecionar bytes
  alterados durante a revalidação protegida por lock.
- `outra execução publicou uma fonte diferente; tente novamente`: espere que a
  outra execução termine e repita o comando.

Consulte também a [solução de problemas](../troubleshooting.md).

A publicação é atômica para leitores e execuções concorrentes, mas não promete
durabilidade contra queda de energia: o projeto não executa `fsync` de arquivos
e diretórios. Depois de desligamento abrupto, rode o comando novamente; se a
validação de `out/process-llm/CURRENT` falhar, use a recuperação acima.
