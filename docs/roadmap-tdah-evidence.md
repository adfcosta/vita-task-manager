# Roadmap — Vita orientada a evidências TDAH

Plano de execução pra alinhar a skill `vita-task-manager` com a
especificação técnica "Vita orientada por evidências para suporte
operacional ao TDAH" (spec v1.0).

**Documento base:** spec v1.0 (recorte não-farmacológico).  
**Última revisão:** 2026-04-18.  
**Versão atual da skill:** 2.11.3.

---

## Contexto e desvios vs. spec §17

A spec recomenda a sequência `thresholds → KPIs → first_touch →
due_soon → off_pace`. Duas descobertas no modelo atual mudam a
ordem:

1. `Task.due_date` só guarda data (`'DD/MM'`), sem hora. `due_soon`
   com `hours_left` exige evoluir o modelo → custo maior que o
   aparente na spec.
2. `Task.progress_done` e `Task.progress_total` **já existem**.
   `off_pace` tem base pronta → custo menor, sobe na ordem.

Por isso a ordem abaixo diverge da spec em três pontos:

- **copy** antecipa (item isolado, alto valor, baixo custo)
- **off_pace** antecipa (modelo já suporta)
- **due_soon** adia (exige mudança de modelo)
- **KPIs** adia (depende de `copy_variant` pra medir A/B)

---

## Roadmap

| Versão | Feature | Custo | Valor TDAH |
|---|---|---|---|
| v2.12.0 | Thresholds config + `max_nudges_per_tick` + agrupamento por task | baixo | médio (tuning) |
| v2.13.0 | Copy library refatorada + `copy_variant` + `cooldown_applied` | baixo | alto (linguagem acionável) |
| v2.14.0 | `first_touch` | médio | alto (alvo nº1 spec) |
| v2.15.0 | `off_pace` | médio | alto (fiasco silencioso) |
| v2.16.0 | KPIs + instrumentação completa | médio | alto (mensuração) |
| v2.17.0 | `due_soon` com janela horária (requer `due_time` no model) | alto | alto |
| v2.18.0 | `missed_routine` opt-in | médio | médio |
| v2.19.0 | Guardrail de segurança (§14.3) | baixo | alto (crítico) |

### Dependências

```
v2.12.0 (config infra)
   ↓
v2.13.0 (copy + copy_variant) ──┐
   ↓                             │
v2.14.0 (first_touch) ──────────┤
   ↓                             │
v2.15.0 (off_pace) ─────────────┤
   ↓                             ↓
v2.16.0 (KPIs depende de copy_variant)
   ↓
v2.17.0 (due_soon c/ hora) — requer evolução de model
   ↓
v2.18.0 (missed_routine) — requer evolução de FixedEntry

v2.19.0 (segurança) — paralelo, sem dependência
```

---

## v2.12.0 — Thresholds configuráveis + limite por tick + agrupamento

**Objetivo:** permitir experimentação comportamental sem deploy,
reduzir fadiga de cluster, agrupar múltiplos sinais da mesma task.

### Arquivos tocados

- `scripts/heartbeat.py` — substituir thresholds hardcoded por
  leitura de config, adicionar `_group_alerts_by_task`
- `examples/openclaw/heartbeat-config.json.example` — schema expandido
- `scripts/test_core.py` — +4 testes
- `patches/vita-AGENTS.md` — seção Heartbeat com thresholds config
- `CHANGELOG.md` + `SKILL.md` + `README.md` — bump

### Config schema (diff vs. atual)

```diff
  {
    "emit_target": "agent:main:whatsapp:direct:+XXX",
    "severity_floor": "critical",
-   "cooldown_hours": 24
+   "cooldown_hours": 24,
+   "max_nudges_per_tick": 3,
+   "thresholds": {
+     "overdue_min_days": 1,
+     "stalled_min_hours": 24,
+     "blocked_min_postpones": 2
+   }
  }
```

### Mudanças no código

1. `load_heartbeat_config()` ganha novos defaults (seguindo spec §9)
2. `is_critical(alert, thresholds)` lê do dict em vez de hardcode
3. Novo `_group_alerts_by_task(alerts)` — mescla múltiplos alert_types
   da mesma task num fragmento único
4. `build_heartbeat_nudges()` aplica threshold, agrupa por task,
   ordena por severidade e corta em `max_nudges_per_tick`
5. Record do nudge ganha `alert_types: list[str]` (plural)

### Testes

- `test_thresholds_from_config`: config com `overdue_min_days=5`
  não dispara pra overdue=3
- `test_max_nudges_per_tick`: 10 alertas → só 3 nudges
- `test_group_same_task_two_alerts`: task X com overdue+stalled →
  1 nudge combinado
- `test_cooldown_covers_group`: cooldown vale pro grupo todo

### Breaking change

Record migra de `alert_type: str` → `alert_types: list[str]`.
Leitura tolera ambos (compat).

### Acceptance

- [ ] Config em runtime altera comportamento sem restart
- [ ] Task com 3 alertas → 1 nudge com todos
- [ ] 4 críticas + max=3 → 3 emitidos, 1 persistido pra surface
  via `nudges-pending`
- [ ] Defaults da spec honrados quando `thresholds` omitido

---

## v2.13.0 — Copy library + `copy_variant`

**Objetivo:** alinhar mensagens ao padrão spec §7.3 (**detecção +
janela + ação mínima**), permitir A/B.

### Arquivos

- `scripts/copy.py` (novo) — biblioteca por alert_type com variantes
- `scripts/heartbeat.py` — usar `render_nudge(alert, variant)`
- `scripts/test_core.py` — +3 testes

### Estrutura de `copy.py`

```python
COPY_LIBRARY = {
    "overdue": {
        "A": "🌿 \"{desc}\" atrasou {days_overdue}d. Em vez de terminar tudo, quer só destravar com uma subtarefa de 10–15min?",
        "B": "🌿 \"{desc}\" passou do prazo. Qual é o menor passo que conta como avanço hoje?",
    },
    "stalled": {
        "A": "🌿 \"{desc}\" está parada há {hours_since_update}h. Um bloco curto hoje reinicia?",
        "B": "🌿 \"{desc}\" ficou quieta há {hours_since_update}h. Qual a próxima ação concreta de 15min?",
    },
    "blocked": {
        "A": "🌿 Você adiou \"{desc}\" {postpone_count}x. O que conta como avanço real mínimo hoje?",
        "B": "🌿 \"{desc}\" foi adiada {postpone_count}x. Quer quebrar em algo de 5min que destrave o resto?",
    },
    # first_touch, due_soon, off_pace, missed_routine em versões futuras
}

def render_nudge(alert, variant="A"): ...
def pick_variant(task_id, alert_type): ...  # hash-determinística
```

### Record expandido (v2.13)

```diff
  {
    "type": "nudge",
    "id": "nudge_abc123",
    "task_id": "...",
    "alert_types": ["overdue"],
    "text_frag": "🌿 ...",
+   "copy_variant": "A",
+   "cooldown_applied": true,
    "created_at": "..."
  }
```

### Acceptance

- [ ] Nudge de overdue agora pergunta ação mínima, não descreve
- [ ] `copy_variant` preenchido em todo record
- [ ] `nudges-pending` exibe copy renderizado

---

## v2.14.0 — `first_touch`

**Objetivo:** spec §5.1 — atacar dificuldade de iniciação. Task
criada há 12h+ sem movimentação dispara nudge.

### Arquivos

- `scripts/cli.py` — `_build_alerts()` ganha bloco `first_touch`
- `scripts/heartbeat.py` — `is_critical` reconhece o novo tipo
- `scripts/copy.py` — copy pra first_touch
- `heartbeat-config.json.example` — `first_touch_min_hours: 12`
- `scripts/test_core.py` — +3 testes

### Lógica (pseudocódigo)

```python
if status == "[ ]" and not task.get("started_at") and not task.get("updated_at"):
    hours_since = hours_since(task["created_at"])
    if hours_since >= first_touch_min_hours:
        alerts.append({"type": "first_touch", ...})
```

### Copy

```python
"first_touch": {
    "A": "🌿 Vi que \"{desc}\" ainda não foi tocada ({hours_since_created}h). Faz só o primeiro passo: abrir e definir a próxima ação?",
    "B": "🌿 \"{desc}\" está na fila há {hours_since_created}h sem movimento. Define em 1 linha qual o primeiro passo?",
},
```

### Acceptance

- [ ] Task adicionada 06:00 sem toque dispara 18:00+
- [ ] Task com `started_at` não dispara
- [ ] Threshold configurável

---

## v2.15.0 — `off_pace`

**Objetivo:** spec §5.6 — detectar tasks longas andando devagar
antes de virar `overdue`.

### Pré-requisito já satisfeito

`Task.progress_done` + `progress_total` + `due_date` + `created_at`
→ calcula `expected = (days_passed / total_days) * total` e compara
com `done * ratio`.

### Lógica

```python
if done is not None and total and due:
    total_days = max((due_date - created.date()).days, 1)
    days_passed = (today - created.date()).days
    if days_passed > 0 and due_date >= today:
        expected = (days_passed / total_days) * total
        if done < expected * off_pace_ratio:
            alerts.append({"type": "off_pace", ...})
```

### Copy

```python
"off_pace": {
    "A": "🌿 \"{desc}\" está em {done_units}/{total_units} — esperado ~{expected_units}. Um bloco curto hoje recoloca no trilho?",
    "B": "🌿 Ritmo de \"{desc}\" ficou abaixo do esperado ({done_units}/{total_units}, faltam {days_remaining}d). Quer destravar com a próxima etapa menor?",
},
```

### Acceptance

- [ ] Task 30d, 10d passados, 0/10 done → dispara
- [ ] Sem `progress_total` não avalia
- [ ] Dentro do ritmo não dispara

---

## v2.16.0 — KPIs + instrumentação completa

**Objetivo:** spec §16 — responder "quantos nudges viraram ação útil?".

### Record expandido (v2.16)

```diff
  {
    "type": "nudge",
    ...
+   "emitted_at": "...",       // quando sessions_send completou
+   "delivery_status": "success",  // success | failed | skipped
+   "next_task_update_at": null    // preenchido retroativamente
  }
```

### `nudge_ack` expandido

```diff
  {
    "type": "nudge_ack",
    "nudge_id": "...",
    "acked_at": "...",
    "ack_source": "telegram_user",
+   "response_kind": "agora"  // agora | depois | replanejar | ignorado
  }
```

### Novo comando

```bash
python3 scripts/cli.py nudge-kpis --data-dir data --window-days 7
```

Retorna: `action_within_2h`, `action_within_24h`, `median_hours_to_update`,
`by_alert_type`, `ignored_rate_by_type`, `cluster_rate_by_tick`.

### Arquivos

- `scripts/kpis.py` (novo)
- `scripts/heartbeat.py` — registra `emitted_at`, `delivery_status`
- `scripts/cli.py` — comando `nudge-kpis`
- `scripts/ledger_ops.py` — função `link_nudge_to_next_update`
- `patches/janus-AGENTS.md` — Janus registra `delivery_status`

### Acceptance

- [ ] Após 7d de uso, `nudge-kpis` retorna números consistentes
- [ ] Nudge falhado marcado `delivery_status: failed`
- [ ] Ack captura `response_kind`

---

## v2.17.0 — `due_soon` com janela horária

**Objetivo:** spec §5.2 — dispara 4h antes do vencimento real.

### Pré-requisito: evoluir modelo

1. `Task.due_time: Optional[str]` (`'HH:MM'`)
2. Parser aceita `"DD/MM HH:MM"` ou `"+N HH:MM"`
3. Fallback: tasks legadas sem hora caem em 23:59 do dia

### Lógica

```python
if due and due_time:
    due_dt = datetime.combine(due_date, time(h, m))
    hours_left = (due_dt - now).total_seconds() / 3600
    if 0 < hours_left <= due_soon_window_hours:
        alerts.append({"type": "due_soon", ...})
```

### Nota sobre `due_today`

**Manter** o atual (sem hora) pra render/panorama. `due_soon` é
trigger de nudge, só ativo se houver `due_time`.

### Breaking change

Ledger antigo continua funcionando (sem `due_time` = sem `due_soon`).
CLI `ledger-add` ganha `--due-time "HH:MM"`.

### Acceptance

- [ ] Task `due "18/04" + due_time "20:00"` dispara às 16:00
- [ ] Sem `due_time` não dispara (evita falso positivo)
- [ ] Migration path indolor pra tasks antigas

---

## v2.18.0 — `missed_routine` opt-in

**Objetivo:** spec §5.7 + §14.4 — rotina crítica não executada
até horário-limite dispara nudge, mas só se opt-in.

### Pré-requisito: flag em rotina

`FixedEntry.alert_on_miss: bool = False`.  
Sintaxe em `input/rotina.md`:
```markdown
- [🔴] Tomar remédio manhã @08:00 !nudge
```

### Lógica

```python
if task.get("source") == "rotina" and task.get("alert_on_miss") and status == "[ ]":
    limit_dt = start_time + timedelta(hours=1)
    if now > limit_dt:
        alerts.append({"type": "missed_routine", ...})
```

### Copy

```python
"missed_routine": {
    "A": "🌿 A rotina \"{desc}\" ficou para trás (esperada {expected_at}). Quer fazer a versão mínima agora?",
    "B": "🌿 \"{desc}\" não rodou hoje. Mesmo a versão reduzida ajuda — topa 5min?",
},
```

### Acceptance

- [ ] Rotina `!nudge` dispara 1h após horário
- [ ] Rotina sem flag nunca dispara (spec §14.4)
- [ ] Cooldown vale por task_id+alert_type

---

## v2.19.0 — Guardrail de segurança

**Objetivo:** spec §14.3 — detectar menção a crise e sair do modo
produtividade.

### Camada 1 — AGENTS

Adicionar seção obrigatória no patch:

> Se o input do usuário contiver ideação suicida, autoagressão,
> psicose, dor torácica, palpitações persistentes, síncope ou
> privação grave de sono, Vita sai do modo tasks e entra em modo
> roteamento. Resposta curta reconhecendo + encaminhamento humano/
> urgente (número em `data/safety-routing.json`). NUNCA dar conselho
> de produtividade nesses casos.

### Camada 2 — CLI (hardening opcional)

`scripts/safety.py` com detector de keywords + comando
`safety-check --text "..."`. Vita pode chamar antes de processar
inputs sensíveis.

### Arquivos

- `patches/vita-AGENTS.md` — seção Guardrail
- `scripts/safety.py` (novo)
- `scripts/cli.py` — comando `safety-check`
- `examples/openclaw/safety-routing.json.example`

### Acceptance

- [ ] "quero sumir" dispara roteamento, não gera task
- [ ] False positives baixos (contexto considerado)
- [ ] Config de destino humano obrigatória

---

## Histórico de revisões

- **2026-04-18** — Draft inicial com base em spec v1.0. Ordem
  ajustada: copy antecipa, off_pace antecipa, due_soon atrasa,
  KPIs atrasam.
