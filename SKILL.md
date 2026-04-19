---
name: vita-task-manager
description: Gerenciar tarefas pessoais via ledger JSONL e CLI dedicada.
metadata:
  openclaw:
    requires:
      bins:
        - python3
---

# Vita Task Manager

Sistema de tasks pessoais via ledger JSONL append-only.

**Versão:** 2.18.0

## Regra de ouro

Toda escrita passa por `python3 scripts/cli.py ...`. Nunca editar `output/`, `data/historico/*.jsonl`, `data/*.json`.
`input/rotina.md` e `input/agenda-semana.md` são editados pelo usuário — você só lê.

Se um comando não existe pra operação que o usuário pediu, **não fazer** — pergunte ou escale.

## Arquivos

| Caminho | Quem edita |
|---|---|
| `input/rotina.md` | Usuário |
| `input/agenda-semana.md` | Usuário |
| `data/historico/*.jsonl` | CLI (fonte de verdade) |
| `data/historico-execucao.md` | CLI entre `<!-- BEGIN METRICS -->`/`<!-- END METRICS -->`; `## Observações` é seu |
| `data/word_weights.json` | CLI |
| `data/proactive-nudges.jsonl` | CLI |
| `data/heartbeat-config.json` | Config manual OK |
| `output/diarias.txt` | CLI |

## Formato dos inputs

### `input/rotina.md`

```markdown
- 06:00 | Meditação 10min
- 07:00 | Café da manhã
- 08:00 | Tomar remédio !nudge
```

- `- HH:MM | descrição` → entra no ledger todo dia via `sync-fixed` (dedupe por hash).
- `!nudge` no fim da linha → opt-in pra alerta `missed_routine` se não executar.

### `input/agenda-semana.md`

```markdown
## Segunda 07/04
- 14:00 — Médico
```

Separadores aceitos: `—`, `-`, `–`, `|`. Compromissos aparecem como informativo no render, **não** viram task.

## Intenção → comando

Use sempre `--today DD/MM --year YYYY --data-dir data` (omito nas tabelas por brevidade).

### Fluxo diário

| Intenção | Comando |
|---|---|
| Rodar o dia (rollover + sync rotina + render) | `pipeline` |
| Manhã (pipeline + histórico + pesos) | `daily-tick` |
| Domingo/segunda (histórico + candidatos recorrência + diagnóstico) | `weekly-tick` |
| Só renderizar, sem alterar ledger | `render` |

- `pipeline` escreve `output/diarias.txt` em WhatsApp. Markdown só via `render --format markdown`.
- `pipeline` **não aceita** `--format`.

### CRUD

| Intenção | Comando |
|---|---|
| Criar task | `ledger-add` |
| Refinar task existente (mudar contexto, prioridade, prazo) | `ledger-update` — **nunca** `ledger-add` |
| Iniciar (respeita WIP=2) | `ledger-start` |
| Progresso com unidades | `ledger-progress --done N --total M --unit "..."` |
| Concluir | `ledger-complete` |
| Cancelar | `ledger-cancel --reason "..."` |

Todos aceitam `--description` no lugar de `--task-id` (resolve por texto).

**Duplicate guardrail:** se `ledger-add` retornar `warning.type == "duplicate_suspect"`, parar, mostrar a task similar ao usuário, oferecer: atualizar a existente (`ledger-update`), criar mesmo assim (`--allow-duplicate`), ou cancelar. Nunca decidir sozinha.

### Captura rápida (TDAH)

| Intenção | Comando |
|---|---|
| Texto livre (não cria task) | `brain-dump --text "..."` (opcional `--due +N` ou `DD/MM/YYYY`) |
| Promover item pra task | `dump-to-task --dump-id ID --item "..." --priority 🟡 --next-action "..."` |

### Priorização

| Intenção | Comando |
|---|---|
| "O que fazer hoje?" / usuário sobrecarregado | `suggest-daily --limit 9` |
| "Por que essa task tá aí?" | `explain-task --task-id ID` |
| Score bruto | `score-task --task-id ID` |

### Diagnóstico e alertas passivos

| Intenção | Comando |
|---|---|
| Estado do ledger (troubleshooting) | `ledger-status` |
| Quantas em andamento | `check-wip` |
| Alertas acionáveis (passivo) | `check-alerts` |

### Heartbeat (push proativo)

| Comando | Quando |
|---|---|
| `heartbeat-tick` | Cada tick do cron (55min, 06–23h Maceio) |
| `nudge-delivery --nudge-id ID --status success\|failed\|skipped` | Janus após emitir |
| `nudges-ack --nudge-id ID --source SRC --response-kind agora\|depois\|replanejar` | Quando usuário responde |
| `nudges-pending` | Fallback se `sessions_send` falhar — próxima interação recupera |
| `nudge-kpis --window-days 7` | Retro semanal |

### Recorrência

Nunca ativar sem aprovação explícita do usuário.

| Intenção | Comando |
|---|---|
| Detectar candidatos (4sem) | `recurrence-detect` |
| Ativar (após aprovação) | `recurrence-activate --pattern daily\|weekly [--weekdays "[0,2,4]"] --priority 🟡 --time-range "HH:MM"` |
| Listar regras ativas | `recurrence-list` |
| Desativar | `recurrence-deactivate --rule-id ID --reason "..."` |

`sync-fixed` (chamado pelo pipeline) injeta tasks das regras ativas respeitando dia da semana.

### Feedback do dia

Comandos CRUD e `daily-tick` retornam `feedback_status` + `feedback_seed`:

| `feedback_status` | Ação |
|---|---|
| `required` | Gerar `panorama`/`foco`/`alerta`/`acao_sugerida` a partir do seed → `store-feedback` → `render` |
| `offer` | Perguntar "atualizo o panorama?". Se sim: idem `required` |
| `skip` | Nada a fazer |

Os 4 campos de `store-feedback` são obrigatórios. `--force-feedback` força `offer` em debug.

## Alertas

### Tipos

| Tipo | Dispara quando |
|---|---|
| `overdue` | prazo no passado |
| `due_today` | prazo = hoje |
| `due_soon` | prazo hoje + `due_time` dentro da janela |
| `missed_routine` | rotina com `!nudge` em `[ ]` passado horário + grace |
| `first_touch` | task em `[ ]` criada há ≥12h sem toque |
| `stalled` | task em `[~]` há ≥48h sem update |
| `blocked` | postpone_count ≥ threshold |
| `off_pace` | `done` < `(dias_passados/dias_totais) * total * ratio` |

### Severidade e consolidação

Ordem: `overdue` → `blocked` → `missed_routine` → `due_soon` → `first_touch` → `stalled` → `off_pace` → `due_today`.
Múltiplos sinais da mesma task → **um** nudge consolidado por tick.

### Cooldown e limite

- Cooldown 24h por `task_id + alert_type`.
- Limite `max_nudges_per_tick=3`.
- Config viva em `data/heartbeat-config.json`, efeito no próximo tick (sem restart).

```json
{
  "emit_target": "agent:main:whatsapp:direct:+XXYYYYYYYYYY",
  "severity_floor": "critical",
  "cooldown_hours": 24,
  "max_nudges_per_tick": 3,
  "thresholds": {
    "overdue_min_days": 1,
    "stalled_min_hours": 24,
    "blocked_min_postpones": 2,
    "first_touch_min_hours": 12,
    "off_pace_ratio": 0.7,
    "due_soon_window_hours": 4,
    "missed_routine_grace_hours": 1
  }
}
```

Sem arquivo: `emit_target=null` (persiste mas não emite).

### Comportamento do `heartbeat-tick`

1. Lê alertas, filtra críticos, aplica cooldown, consolida por task, corta em `max_nudges_per_tick`.
2. Persiste em `data/proactive-nudges.jsonl` **antes** de retornar (falha de envio não vaza estado).
3. Retorna JSON; se `emit_text` não-vazio **e** `emit_target` não-null → chamar `sessions_send(emit_target, emit_text)`.
4. Após enviar → `nudge-delivery` com status apropriado.

## WIP

Default: 2 tasks em `[~]`. `ledger-start` bloqueia além disso com mensagem ao usuário.

## Convenções

- Semana: domingo → sábado, `America/Maceio` (UTC-3).
- IDs de task: `YYYYMMDD_slug` (`_2`, `_3` em colisão).
- IDs de regra: `rule_YYYYMMDD_slug[_HHMM]`.
- Limpeza D+1: tasks concluídas/canceladas somem do render a partir do dia seguinte.
- Rollover: automático no primeiro `pipeline` da semana nova.

## Testes

```bash
VITA_TEST_MODE=1 python3 scripts/test_core.py
```

Flag ativa proteção anti-contaminação (redireciona escritas fora de tmp pra `TEST_*` + warning).
