---
name: vita-task-manager
description: Gerenciar tarefas pessoais via ledger JSONL e CLI dedicada.
---

# Vita Task Manager

Sistema de tasks pessoais com **ledger JSONL append-only** como fonte de verdade, otimizado para TDAH.

**Versão:** 2.6.0

## Regra de Ouro

Escrita só via `python3 scripts/cli.py ...`. Nunca use `write`, `edit` ou edição direta nos arquivos de `output/` ou `data/historico/`.

Exceção: `input/rotina.md` e `input/agenda-semana.md` são editados manualmente pelo usuário — a skill apenas lê.

## Estrutura de Arquivos

O repositório versiona apenas o código da skill e exemplos. Todos os dados pessoais e arquivos gerados ficam no `.gitignore` — use `examples/` como ponto de partida.

| Caminho | Papel | Quem edita | Versionado? |
|---|---|---|---|
| `input/rotina.md` | Rotina diária (entra todo dia no pipeline) | Usuário | ❌ gitignore |
| `input/agenda-semana.md` | Compromissos pontuais da semana | Usuário | ❌ gitignore |
| `data/historico/DDMMYY_DDMMYY_bruto.jsonl` | Ledger append-only (fonte de verdade) | CLI | ❌ gitignore |
| `data/historico-execucao.md` | Relatório de padrões de execução | CLI (execution-history) | ❌ gitignore |
| `data/word_weights.json` | Pesos por palavra para detecção de duplicatas | CLI (execution-history) | ❌ gitignore |
| `output/diarias.txt` | Render diário em formato WhatsApp | CLI (pipeline/render) | ❌ gitignore |
| `examples/rotina.md` | Exemplo de rotina (ponto de partida) | Mantenedores | ✅ versionado |

`output/diarias.md` **não existe por padrão** — só é gerado se você invocar `render --format markdown --output output/diarias.md` explicitamente.

## Arquivos de Input

### `input/rotina.md`

Lista achatada de tarefas diárias com horário:

```markdown
# Rotina

## Tarefas Diárias

- 06:00 | Meditação 10min
- 07:00 | Café da manhã
- 08:00 | Revisar e-mails
```

Cada linha: `- {HH:MM} | {descrição}`. Sem prioridade, sem checkbox — a skill injeta essas entradas no ledger todo dia via `sync-fixed` (chamado automaticamente pelo pipeline).

### `input/agenda-semana.md`

Compromissos pontuais agrupados por dia:

```markdown
# Agenda da Semana — 06/04 a 12/04/2026

## Domingo 06/04

## Segunda 07/04
- 14:00 — Médico
- 22:00 — Reunião

## Terça 08/04
- 10:00 — Dentista
```

Separador aceito: `—`, `-`, `–` ou `|`. Esses itens aparecem no render como **compromissos do dia** (informativo), não como tasks no ledger.

## Fluxo Diário (Pipeline)

Comando único que faz tudo:

```bash
python3 scripts/cli.py pipeline \
  --today 08/04 --year 2026 \
  --rotina input/rotina.md \
  --agenda-semana input/agenda-semana.md \
  --data-dir data \
  --output output/diarias.txt
```

O que acontece internamente:

1. **Rollover semanal** — se houver ledger da semana anterior com tasks pendentes, carrega pro novo ledger (automático, roda no primeiro dia da semana em que o pipeline for chamado)
2. **Sync da rotina** — injeta as entradas de `rotina.md` do dia no ledger (dedupe via hash, não duplica em re-runs)
3. **Avaliação de feedback** — decide se precisa pedir novo feedback à Vita (ver seção Feedback)
4. **Render** — gera `output/diarias.txt` em formato WhatsApp

Flags opcionais:

- `--force-feedback` — força `feedback_status=offer` mesmo quando nada mudou

### Sobre `--format`

⚠️ **O comando `pipeline` NÃO aceita `--format`** — ele sempre escreve formato WhatsApp em `output/diarias.txt`.

Se você precisar do formato markdown, use o comando `render` separadamente (ver seção Render).

### Retorno do pipeline

JSON com campos úteis:

```json
{
  "ledger_path": "data/historico/050426_110426_bruto.jsonl",
  "rollover": {"performed": false},
  "sync_fixed": {"inserted": [...], "skipped": [...]},
  "feedback_status": "required",
  "feedback_seed": {...},
  "last_feedback": null,
  "changes_since": [],
  "output_path": "output/diarias.txt",
  "summary": {"open": 7, "completed_today": 0, "cancelled_today": 0, "compromissos": 0}
}
```

## Feedback

Se `feedback_status` for `required` ou `offer`:

1. Ler `feedback_seed` (tem `has_overdue`, `due_today`, `at_risk_tasks`, `suggested_focus`, etc.)
2. Gerar os 4 campos obrigatórios: `panorama`, `foco`, `alerta`, `acao_sugerida`
3. Salvar via `store-feedback`
4. Re-renderizar se quiser que o feedback apareça no `.txt`

Exemplo de `store-feedback`:

```bash
python3 scripts/cli.py store-feedback \
  --today 08/04 --year 2026 --data-dir data \
  --data '{"panorama":"Há 3 tasks urgentes","foco":"Relatório do cliente","alerta":"Prazo em 2 dias","acao_sugerida":"Bloquear 2h de foco agora"}'
```

Todos os 4 campos são obrigatórios — a CLI rejeita payloads incompletos.

Se `feedback_status=skip`, nada mudou desde o último feedback — não precisa gerar novo.

## Formato de Saída (WhatsApp)

O `output/diarias.txt` segue este layout:

```
📋 Tasks — 08/04/2026

🔴 URGENTE (prazo hoje)
▢ Revisar arquitetura

🟡 EM ANDAMENTO
⏳ Escrever documentação
  [█████░░░░░] 50% (5/10 páginas)
  restam 5 páginas

🟢 BAIXA PRIORIDADE
▢ Ligar dentista

➖➖➖➖➖➖➖➖➖➖

🧠 BRAIN DUMP
⏰ até 10/04:
• Trocar lâmpada
• Comprar café
💡 Dica: Escolha 1 pra virar próxima ação

➖➖➖➖➖➖➖➖➖➖

🎯 SUGESTÃO 1-3-5
🔥 BIG: 👉 Revisar arquitetura — score 38
   Por quê: prazo imediato; exige bloco de foco
⚡ MEDIUM: 👉 Responder emails — score 52
   Por quê: prazo hoje; rápido de fazer
...
```

Prefixos de idade:
- `⚠️` — task parada há mais de 7 dias
- `👻` — task parada há mais de 14 dias

## Comandos

### Captura rápida (TDAH)

```bash
# brain dump: captura texto livre sem criar task
python3 scripts/cli.py brain-dump \
  --text "Comprar café, ligar pro João" \
  --today 08/04 --year 2026 --data-dir data

# com prazo opcional (DD/MM/YYYY ou +N dias):
python3 scripts/cli.py brain-dump --text "..." --due +3 ...

# promover item do dump pra task formal
python3 scripts/cli.py dump-to-task \
  --dump-id 20260408_dump_001 \
  --item "Comprar café" \
  --priority 🟡 \
  --next-action "Passar no mercado antes das 18h" \
  --today 08/04 --year 2026 --data-dir data
```

`dump-to-task` também aceita `--due` (herda do dump se não passar).

### CRUD de tasks

```bash
ledger-add       --description "..." --priority 🔴 --due 10/04 ...
ledger-start     --task-id ID ...      # respeita WIP limit
ledger-progress  --task-id ID --done 5 --total 10 --unit "pgs" ...
ledger-complete  --task-id ID ...
ledger-cancel    --task-id ID --reason "..." ...
ledger-update    --task-id ID [--new-description "..."] [--context "..."] [--priority 🔴] [--due DD/MM] ...
```

Todos aceitam `--description` no lugar de `--task-id` pra resolução por texto.

`ledger-update` altera campos de uma task existente sem criar duplicata. Só os campos passados são modificados — o resto permanece intacto. Use em vez de `ledger-add` quando o usuário está refinando uma task (mudando contexto, renomeando, etc.).

### Priorização (scoring)

```bash
python3 scripts/cli.py score-task --task-id ID --today DD/MM --year YYYY --data-dir data
python3 scripts/cli.py suggest-daily --today DD/MM --year YYYY --data-dir data --limit 9
python3 scripts/cli.py explain-task --task-id ID --today DD/MM --year YYYY --data-dir data
```

Use `suggest-daily` quando o usuário perguntar "o que fazer hoje?" ou parecer sobrecarregado.

### Apoio

```bash
check-wip         # quantas tasks estão em [~] e se pode iniciar mais
sync-fixed        # injeta rotina.md do dia (chamado automaticamente pelo pipeline)
store-feedback    # salva feedback da Vita (ver seção Feedback)
rollover          # rollover semanal manual (automático no pipeline)
ledger-status     # diagnóstico do estado do ledger (semana atual, anterior, issues)
```

### Render (único que aceita `--format`)

```bash
# padrão: WhatsApp → output/diarias.txt
python3 scripts/cli.py render \
  --today DD/MM --year YYYY --data-dir data \
  --output output/diarias.txt

# opcional: markdown explícito
python3 scripts/cli.py render \
  --today DD/MM --year YYYY --data-dir data \
  --output output/diarias.md --format markdown
```

`render` não altera o ledger — só lê o estado atual e escreve o arquivo.

### Resumo semanal

```bash
python3 scripts/cli.py weekly-summary \
  --ledger data/historico/050426_110426_bruto.jsonl \
  --format md  # ou json
```

### Histórico de execução

```bash
python3 scripts/cli.py execution-history \
  --today DD/MM --year YYYY --data-dir data \
  --output data/historico-execucao.md \
  --weeks 4
```

Gera relatório de padrões de execução lido pela Vita no Session Start para calibrar planejamento. Métricas: taxa de conclusão semanal, análise por origem (rotina/manual/brain_dump), top 5 tasks mais adiadas, desempenho por dia da semana.

O arquivo usa marcadores `<!-- BEGIN METRICS -->` / `<!-- END METRICS -->` — re-runs atualizam só as métricas, preservando a seção `## Observações` (anotações manuais).

**Subproduto:** também gera `data/word_weights.json` com pesos por palavra para detecção inteligente de duplicatas (ver seção Detecção de Duplicatas).

### Diagnóstico do ledger

```bash
python3 scripts/cli.py ledger-status \
  --today DD/MM --year YYYY --data-dir data
```

Retorna JSON com estado de saúde: semana atual/anterior, tasks abertas, rollover pendente, issues detectados. Use quando suspeitar de problemas no ledger (tasks sumindo, rollover perdido, etc.).

### Detecção de duplicatas

O `ledger-add` detecta automaticamente tasks similares e retorna `warning.type == "duplicate_suspect"` quando encontra.

**Sem pesos (fallback):** comparação por intersecção simples de palavras (>= 50%).

**Com pesos (word_weights.json):** similaridade ponderada usando 3 fatores por palavra:

| Fator | O que mede | Efeito |
|-------|-----------|--------|
| Distintividade | Raridade em tasks completadas (log IDF) | Palavras genéricas pesam menos |
| Evitação | Taxa de conclusão + postpone_count | Palavras de tasks evitadas pesam mais |
| Tempo de resolução | Horas entre criação e conclusão | Palavras de tasks lentas pesam mais |

`peso(palavra) = distintividade x evitacao x resolucao`

Os pesos são gerados semanalmente pelo `execution-history` a partir do histórico completo do ledger. Se `word_weights.json` não existir, todas as palavras têm peso 1.0 (comportamento original).

### Recorrência

Detecta padrões de recorrência no histórico e permite criar regras automáticas.

```bash
# Detectar candidatos (analisa últimas 4 semanas)
python3 scripts/cli.py recurrence-detect \
  --today DD/MM --year YYYY --data-dir data \
  --min-occurrences 5 --weeks 4

# Ativar regra (diária ou semanal)
python3 scripts/cli.py recurrence-activate \
  --description "Tomar remédios" --pattern daily \
  --priority 🟢 --time-range 08:00 \
  --today DD/MM --year YYYY --data-dir data

# Ativar regra semanal (seg/qua/sex)
python3 scripts/cli.py recurrence-activate \
  --description "Estudar inglês" --pattern weekly \
  --weekdays "[0,2,4]" --priority 🟡 \
  --today DD/MM --year YYYY --data-dir data

# Listar regras ativas
python3 scripts/cli.py recurrence-list \
  --today DD/MM --year YYYY --data-dir data

# Desativar regra (append-only, não destrutivo)
python3 scripts/cli.py recurrence-deactivate \
  --rule-id rule_20260413_tomar_remedios \
  --reason "Mudou a rotina" \
  --today DD/MM --year YYYY --data-dir data
```

**Como funciona:**

- `recurrence-detect` analisa tasks concluídas no período e detecta padrões:
  - **daily**: task aparece em >= 5 dias diferentes da semana
  - **weekly**: 1-3 dias concentram >= 80% das ocorrências
  - Detecta horário predominante se >= 60% das ocorrências têm mesmo HH:MM
  - Ignora tasks de `source=rotina` e tasks que já possuem regra ativa
- Regras são armazenadas no ledger como `type="recurrence_rule"` (append-only)
- `sync-fixed` (chamado pelo pipeline) injeta automaticamente tasks das regras ativas, respeitando dia da semana e deduplicando por hash
- IDs de regra: `rule_YYYYMMDD_slug[_HHMM]` com sufixo `_2`/`_3` se colidir

### Legado (não usar)

`validate`, `summary`, `add`, `progress`, `complete`, `cancel`, `resort` — operam no formato markdown antigo (pré-ledger). Mantidos apenas por compatibilidade. **A Vita não deve invocar esses.**

## Scoring 1-3-5

**Fórmula:**

```
score = (urgency × 0.35)
      + (complexity_invertida × 0.25)
      + (age × 0.20)
      − (postpone_penalty × 0.20)
```

Todos os componentes vão de 0 a 100. `complexity_invertida` = tarefas simples pontuam mais (quick wins sobem na fila).

**Boosts TDAH:**
- Task parada há mais de 21 dias: `+10`
- Task adiada 3 vezes ou mais: `+15`

**Faixas de tamanho (complexidade 1-10):**

| Categoria | Faixa | Papel no 1-3-5 |
|---|---|---|
| Big 🔥 | 8-10 | 1 por dia (tarefa de bloco de foco) |
| Medium ⚡ | 4-7 | 3 por dia |
| Small ✅ | 1-3 | 5 por dia |

Quando uma faixa fica vazia, o `suggest-daily` faz promoção/demoção automática pra preencher os slots com as próximas melhores candidatas.

## WIP Limit

Padrão: **2 tasks em `[~]`** simultaneamente.

```bash
python3 scripts/cli.py check-wip --today DD/MM --year YYYY --data-dir data
python3 scripts/cli.py ledger-start --task-id ID --today DD/MM --year YYYY --data-dir data --limit 2
```

Se já houver 2 em andamento, `ledger-start` bloqueia com mensagem: *"Você já tem 2 tarefas em andamento. Que tal terminar uma antes de começar outra?"*

## Convenções

| Item | Regra |
|---|---|
| Semana | Domingo → sábado, timezone `America/Maceio` (UTC-3) |
| IDs de task | `YYYYMMDD_slug`, com sufixo `_2`, `_3` se colidir |
| IDs de dump | `YYYYMMDD_dump_NNN` (sequencial por dia) |
| IDs de regra | `rule_YYYYMMDD_slug[_HHMM]`, com sufixo `_2`, `_3` se colidir |
| WIP padrão | 2 tasks em `[~]` |
| Limpeza D+1 | Tasks concluídas/canceladas só aparecem no render **no próprio dia** — somem a partir do dia seguinte |
| Rollover | Automático no primeiro pipeline da semana nova (qualquer dia) |

## Testes

```bash
VITA_TEST_MODE=1 python3 scripts/test_core.py
```

A flag `VITA_TEST_MODE=1` ativa proteção anti-contaminação: se algum teste tentar escrever fora de path temporário, o `append_record` redireciona pra um arquivo `TEST_*` e emite warning.

## Arquivos-chave

| Arquivo | Responsabilidade |
|---|---|
| `scripts/cli.py` | Interface de linha de comando |
| `scripts/pipeline.py` | Orquestrador do fluxo diário |
| `scripts/ledger.py` | Engine do ledger JSONL (leitura, merge, IDs) |
| `scripts/ledger_ops.py` | Operações de negócio (CRUD, WIP, sync, feedback) |
| `scripts/scoring.py` | Cálculo de score dinâmico |
| `scripts/suggester.py` | Algoritmo 1-3-5 |
| `scripts/render.py` | Montagem do TaskFile a partir do ledger |
| `scripts/formatter_whatsapp.py` | Formato WhatsApp (padrão) |
| `scripts/formatter.py` | Formato markdown (opcional) |
| `scripts/execution_history.py` | Relatório de padrões de execução + word weights |
| `scripts/recurrence.py` | Detecção de padrões e regras de recorrência |
| `scripts/rollover.py` | Transição semanal de ledger |
| `scripts/test_core.py` | Suíte de testes |