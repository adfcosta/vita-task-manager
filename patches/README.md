# Patches — vita-task-manager

Esta pasta contém **deltas** que a skill `vita-task-manager` enxerta nos arquivos
do agente Vita no Domus. São blocos de conteúdo, não arquivos completos.

**Versão atual dos patches:** v2.16.0

## Filosofia: delta, não substituição

Cada arquivo aqui contém **apenas** o bloco que a skill adiciona ao arquivo vivo
do agente. O resto do arquivo da Vita (Session Start, Scope, Operating Rules,
Safety, Memory, etc.) é responsabilidade do agente e **não é tocado**.

Essa separação garante que:

- Atualizações da skill não sobrescrevem customizações do agente
- Atualizações do agente não conflitam com a skill
- O Faber pode reaplicar o patch a cada update da skill sem medo

## O que tem aqui

| Arquivo | Destino no Domus | Conteúdo |
|---------|------------------|----------|
| `vita-AGENTS.md` | `vita/AGENTS.md` | Bloco `## Sistema de Tasks (via vita-task-manager)` com governança, paths, fluxo e scoring |
| `janus-AGENTS.md` | `janus/AGENTS.md` | Bloco `## Sistema de Tasks (via vita-router plugin)` — decision tree para Janus, tools do plugin, substitui modelo antigo de `sessions_spawn` |
| `vita-SESSION-DESIGN.md` | (referência, não aplicado) | Design do modelo de sessão: session.reset idle, heartbeat per-agent, cron interno, pruning e memory flush |

**Só AGENTS.** Não há patch de SOUL nem de IDENTITY porque:

- **SOUL** é filosofia/comportamento — identidade pura. Nada técnico ali.
- **IDENTITY** é metadata (nome, vibe, emoji). Nada procedural ali.
- Tudo que é **procedimento** (comandos, paths, governança) vive no AGENTS, que é o único lugar onde a skill precisa aparecer.

## Como aplicar

Cada patch usa marcadores HTML para delimitar o bloco a enxertar:

```
<!-- BEGIN vita-task-manager v2.16.0 -->
...conteúdo do bloco...
<!-- END vita-task-manager -->
```

Cada arquivo de patch traz no topo suas próprias instruções de onde
inserir no arquivo vivo e, se for update, o que remover antes (caso
substitua subseções antigas). Os passos abaixo descrevem o fluxo
genérico — use-os em conjunto com o preâmbulo de cada patch.

### Primeira instalação

Ainda não há marcadores no AGENTS vivo da Vita. Aplicação manual:

1. Abrir `vita/AGENTS.md` no Domus
2. Localizar a posição correta para inserir (após `### Não inclui`)
3. Copiar do patch **tudo entre `<!-- BEGIN ... -->` e `<!-- END ... -->` inclusive** (os marcadores entram junto)
4. Colar no AGENTS vivo
5. Salvar

Os marcadores ficam no AGENTS vivo pra sempre, pra permitir updates automáticos.

### Update (versão nova da skill)

A partir da segunda aplicação, os marcadores já existem. O update é:

1. Abrir `vita/AGENTS.md` no Domus
2. Procurar `<!-- BEGIN vita-task-manager ... -->` e `<!-- END vita-task-manager -->`
3. Substituir **tudo entre os dois marcadores (inclusive as próprias linhas de marcador)** pelo conteúdo do patch novo
4. Salvar

O Faber pode automatizar isso com um regex simples:

```python
import re
with open("vita/AGENTS.md") as f:
    current = f.read()
with open("patches/vita-AGENTS.md") as f:
    patch = f.read()

# Extrai o bloco BEGIN→END do patch (ignorando o preâmbulo de instruções)
block = re.search(
    r"<!-- BEGIN vita-task-manager.*?<!-- END vita-task-manager -->",
    patch, re.DOTALL
).group(0)

# Substitui o bloco no arquivo vivo (ou insere se não existir)
pattern = r"<!-- BEGIN vita-task-manager.*?<!-- END vita-task-manager -->"
if re.search(pattern, current, re.DOTALL):
    new = re.sub(pattern, block, current, flags=re.DOTALL)
else:
    # Primeira instalação: inserir após `### Não inclui`
    new = current.replace(
        "### Não inclui",
        "### Não inclui",  # placeholder — ajustar inserção conforme fluxo do Faber
    )
with open("vita/AGENTS.md", "w") as f:
    f.write(new)
```

## Versionamento

A versão no marcador BEGIN (`v2.16.0`) deve sempre casar com a versão da skill.
Se divergir, é sinal de update pendente — o Faber pode detectar isso comparando
o marcador do AGENTS vivo com a versão atual da skill.

## Validação após aplicação

- [ ] Marcadores `<!-- BEGIN vita-task-manager vX.Y.Z -->` e `<!-- END vita-task-manager -->` existem no AGENTS vivo
- [ ] Versão do marcador casa com a versão da skill
- [ ] Seções fora do bloco (Session Start, Scope, Safety, etc.) não foram alteradas
- [ ] Comando CLI de exemplo funciona: `cli pipeline --today DD/MM --year YYYY --rotina input/rotina.md --data-dir data --output output/diarias.txt`