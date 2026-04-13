---
name: vita-task-manager
description: Gerenciar tarefas pessoais via ledger JSONL e CLI dedicada.
---

# Vita Task Manager

Fonte de verdade: `data/historico/DDMMYY_DDMMYY_bruto.jsonl`.

## Arquivos de Input

| Arquivo | Formato | Descrição |
|---------|---------|-----------|
| `input/rotina.md` | Lista de tarefas com horário | Tarefas que entram automaticamente todo dia |
| `input/agenda-semana.md` | Compromissos por dia da semana | Eventos pontuais da semana |

### Formato de rotina.md

```markdown
# Rotina

## Tarefas Diárias

- 06:00 | Meditação 10min
- 07:00 | Café da manhã
- 08:00 | Revisar e-mails
```

Cada linha: `- {HH:MM} | {descrição}`

- **Sem prioridade** — definida manualmente ou pelo CLI depois
- **Sem checkbox** — a rotina é apenas uma lista de atividades

## Regra central

Use **somente** `python3 scripts/cli.py ...` para escrever. Nunca use `write`, `edit` ou outra escrita direta nos arquivos da skill.

## Estrutura

| Caminho | Papel |
|---|---|
| `input/rotina.md` | rotina diária |
| `input/agenda-semana.md` | agenda pontual |
| `data/historico/*.jsonl` | ledger |
| `output/diarias.txt` | render do dia (padrão WhatsApp) |
| `output/diarias.md` | render do dia (markdown explícito) |

## Formatos de saída

| Formato | Uso | Comando |
|---------|-----|---------|
| `markdown` | Legível em editores | `--format markdown` |
| `whatsapp` | Padrão otimizado para mensagens mobile | `--format whatsapp` (default) |

## Convenções

| Item | Regra |
|---|---|
| Semana | domingo → sábado (`America/Maceio`) |
| IDs | `YYYYMMDD_slug`, com `_2`, `_3` se colidir |
| Limpeza | concluídas/canceladas antigas não aparecem no render |
| WIP padrão | `2` tasks em `[~]` |
| Render | `whatsapp` padrão, `markdown` opcional |

## Fluxo padrão

```bash
python3 scripts/cli.py pipeline \
  --today 08/04 --year 2026 \
  --rotina input/rotina.md \
  --agenda-semana input/agenda-semana.md \
  --data-dir data \
  --output output/diarias.txt
```

Retorno inclui `feedback_status`: `required`, `offer` ou `skip`.

> **Nota:** Como `whatsapp` é o formato padrão, use `output/diarias.txt`. Para markdown explícito, use `--format markdown` com `output/diarias.md`.

## Feedback

Se `feedback_status` for `required` ou `offer`:
1. Ler `feedback_seed`.
2. Gerar `panorama`, `foco`, `alerta`, `acao_sugerida`.
3. Salvar via `store-feedback`.
4. Re-renderizar se necessário.

## Comandos

| Grupo | Comando |
|---|---|
| fluxo | `pipeline`, `render`, `weekly-summary`, `rollover` |
| CRUD | `ledger-add`, `ledger-start`, `ledger-progress`, `ledger-complete`, `ledger-cancel` |
| apoio | `check-wip`, `sync-fixed`, `store-feedback` |
| captura | `brain-dump`, `dump-to-task` |
| priorização | `score-task`, `suggest-daily`, `explain-task` |
| legado | `validate`, `summary`, `add`, `progress`, `complete`, `cancel`, `resort` |

## Brain dump

```bash
python3 scripts/cli.py brain-dump --text "Comprar café, ligar pro João" \
  --today 08/04 --year 2026 --data-dir data

python3 scripts/cli.py dump-to-task --dump-id 20260408_dump_001 \
  --item "Comprar café" --priority 🟡 \
  --today 08/04 --year 2026 --data-dir data
```

## Scoring 1-3-5

- fórmula: `(urgency×0.35) + (complexity×0.25) + (age×0.20) - (postpone×0.20)`
- complexidade: `1-10`
- faixas: Big `8-10`, Medium `4-7`, Small `1-3`
- limite: `1/3/5`

```bash
python3 scripts/cli.py score-task --task-id ID --today DD/MM --year YYYY --data-dir data
python3 scripts/cli.py suggest-daily --today DD/MM --year YYYY --data-dir data --limit 9
python3 scripts/cli.py explain-task --task-id ID --today DD/MM --year YYYY --data-dir data
```

## WIP

```bash
python3 scripts/cli.py check-wip --today DD/MM --year YYYY --data-dir data
python3 scripts/cli.py ledger-start --task-id ID --today DD/MM --year YYYY --data-dir data
```

## WhatsApp

```bash
python3 scripts/cli.py render --today DD/MM --year YYYY --data-dir data \
  --output output/diarias.txt

# opcional: forçar markdown explicitamente
python3 scripts/cli.py render --today DD/MM --year YYYY --data-dir data \
  --output output/diarias.md --format markdown
```

## Teste

```bash
python3 scripts/test_core.py
```

## Arquivos-chave

`scripts/cli.py`, `scripts/ledger.py`, `scripts/ledger_ops.py`, `scripts/pipeline.py`, `scripts/render.py`, `scripts/test_core.py`
