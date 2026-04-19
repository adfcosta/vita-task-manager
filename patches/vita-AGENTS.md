# Patch — Vita AGENTS.md (skill vita-task-manager)

Este patch instala o bloco operacional da skill `vita-task-manager`
no AGENTS vivo da Vita. Session Start, Scope, Safety, Memory e demais
seções ficam no AGENTS vivo e **não são tocadas** — o patch só injeta
o que é específico da skill.

## Onde instalar

Arquivo vivo: `~/.openclaw/workspace/vita/AGENTS.md`

### Primeira instalação

1. Localizar posição logo após `### Não inclui` (fim da seção `## Scope`).
2. Inserir o bloco delimitado por `<!-- BEGIN vita-task-manager ... -->`
   e `<!-- END vita-task-manager -->` deste arquivo.
3. Manter os marcadores no arquivo vivo — eles permitem update
   automático.

### Update (versão nova)

Substituir tudo entre os marcadores pelo conteúdo novo deste patch.

---

<!-- BEGIN vita-task-manager v2.18.0 -->
## Sistema de Tasks (via vita-task-manager)

**Regra de ouro:** escrita só via `python3 scripts/cli.py ...`. Nunca editar `output/`, `data/historico/*.jsonl`, `data/*.json`. `input/rotina.md` e `input/agenda-semana.md` são do usuário — ler, não escrever. Se o comando não existe pra operação pedida, não fazer — pergunta ou escala.

Detalhe completo de comandos em `SKILL.md`.

### Intenção → comando

| Intenção do usuário | Comando |
|---|---|
| "adiciona X" | `ledger-add` |
| "muda X pra Y" / "agora é até sexta" | `ledger-update` (nunca `ledger-add`) |
| "comecei / terminei / cancelei" | `ledger-start` / `ledger-complete` / `ledger-cancel` |
| Progresso com unidades | `ledger-progress --done N --total M --unit ...` |
| "anota aí, depois vejo" | `brain-dump`; promover com `dump-to-task` |
| "o que fazer hoje?" / sobrecarga | `suggest-daily` |
| "por que essa tá no topo?" | `explain-task` |
| "tem algo vencendo?" | `check-alerts` |
| Problema no ledger | `ledger-status` |
| Panorama do dia | `render` (ou `pipeline`) |
| Padrão de recorrência | `recurrence-detect` → **usuário aprova** → `recurrence-activate` |

### Duplicate Guardrail

Antes de `ledger-add`: pensar se é task nova ou refinamento. Refinamento → `ledger-update`.

Se `ledger-add` retornar `warning.type == "duplicate_suspect"`:
1. Parar.
2. Mostrar a task similar ao usuário.
3. Oferecer: atualizar (`ledger-update`), forçar (`--allow-duplicate`), ou cancelar.
4. Nunca decidir sozinha.

### Feedback do dia

Todo CRUD e `daily-tick` retornam `feedback_status`:

| Status | Ação |
|---|---|
| `required` | Gerar `panorama`/`foco`/`alerta`/`acao_sugerida` a partir de `feedback_seed` → `store-feedback` → `render` |
| `offer` | Perguntar "atualizo o panorama?". Se sim: idem `required` |
| `skip` | Nada a fazer |

`feedback_seed` traz `has_overdue`/`due_today`/`at_risk_tasks`/`suggested_focus`. Escrever em 1–3 frases curtas, tom direto. Sem re-render depois de `store-feedback`, o feedback não aparece pro usuário.

### Standing Orders

- **Morning Pipeline (06:00 Maceio):** `daily-tick` → verificar `ok: true` → entregar sumário breve. Escalar se `ok: false`, >3 tasks com `postpone_count>=3`, ou >15 abertas.
- **Weekly Reflection (dom 20:00):** `weekly-tick` → apresentar taxa de conclusão + candidatos de recorrência com `suggestion_reason`. Não sugerir recorrências se taxa < 40%. `recurrence-activate` exige aprovação explícita.

### Heartbeat proativo (tick 55min, 06–23h Maceio)

A cada tick:
```
python3 scripts/cli.py heartbeat-tick --today DD/MM --year YYYY --data-dir data
```

Se retorno tem `emit_text` não-vazio **e** `emit_target` não-null:
```
sessions_send(session: emit_target, message: emit_text)
```

Nudges já persistem em disco antes do retorno — se `sessions_send` falhar, próxima interação traz via `nudges-pending`. Cooldown 24h, consolidação por task, `max_nudges_per_tick=3`. Thresholds em `data/heartbeat-config.json`, efeito no próximo tick.

Template de HEARTBEAT.md: `examples/openclaw/vita-HEARTBEAT.md`.

### Tipos de alerta (condições)

| Tipo | Dispara |
|---|---|
| `overdue` | prazo no passado |
| `due_today` | prazo = hoje |
| `due_soon` | prazo hoje + `due_time` dentro da janela (default 4h) |
| `missed_routine` | rotina `!nudge` em `[ ]` passado horário + grace (default 1h) |
| `first_touch` | `[ ]` criada há ≥12h sem toque (qualquer `ledger-start/progress/update` zera) |
| `stalled` | `[~]` há ≥48h sem update |
| `blocked` | postpone_count ≥ threshold |
| `off_pace` | `done < (dias/total) * total * ratio` (só se `progress_total` definido) |

### Execute-Verify-Report

1. **Execute** — rodar (não prometer).
2. **Verify** — `ok: true`, arquivo atualizado, `task_id` presente.
3. **Report** — dizer o que foi feito *e verificado*. Max 3 tentativas antes de escalar.

### Proibido

- `recurrence-activate` sem aprovação do usuário.
- `ledger-add --allow-duplicate` sem perguntar.
- Editar `input/rotina.md` ou `input/agenda-semana.md`.
- `execution-history --weeks > 12` por conta própria.

<!-- END vita-task-manager -->

---

## Validação após aplicação

- [ ] Marcadores `<!-- BEGIN vita-task-manager v2.18.0 -->` e
      `<!-- END vita-task-manager -->` presentes no AGENTS vivo
- [ ] Seções fora do bloco (Session Start, Scope, Safety, Memory,
      Operating Rules, etc.) intactas
- [ ] `cli daily-tick` roda no Morning Pipeline sem intervenção
- [ ] `cli ledger-add` com task similar dispara pergunta ao usuário
      (Duplicate Guardrail)
