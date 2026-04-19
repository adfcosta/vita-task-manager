# Roadmap — Vita Task Manager

**Versão atual da skill:** 2.18.0
**Última revisão:** 2026-04-19
**Spec base:** "Vita orientada por evidências para suporte operacional ao TDAH" (v1.0, recorte não-farmacológico).

Documento único consolidando retrospectiva (o que foi entregue), decisões de descope e planos futuros.

---

## Retrospectiva — v2.2 → v2.18

Duas ondas de trabalho: primeira (v2.2–v2.5) estruturou priorização, WIP e resiliência do ledger. Segunda (v2.12–v2.18) reorientou a skill para a spec TDAH v1.0 — heartbeat proativo com copy acionável, A/B determinístico, KPIs instrumentados e tipos de alerta orientados a evidência.

### Onda 1 — fundações (v2.2 → v2.5) ✅

| Versão | Entregue |
|---|---|
| v2.2 | Scoring 1-3-5 com campos de complexidade, idade e energia; fórmula ponderada (U 35% + C 25% + A 20% − P 20%); categorização big/medium/small; CLI `suggest-daily` e `explain-task`. |
| v2.3 | WIP limit (default 2) com bloqueio explícito; estados visuais no render; feedback contextual com triggers estendidos. |
| v2.4/2.5 | `ledger-update` in-place; detecção de duplicatas por intersecção de palavras; word weights em 3 fatores; rollover em qualquer dia; `ledger-status` para diagnóstico; 42 testes automatizados. |

### Onda 2 — evidence-based TDAH (v2.12 → v2.18) ✅

Sequência originalmente planejada (spec §17): `thresholds → KPIs → first_touch → due_soon → off_pace`. Duas descobertas mudaram a ordem:

1. `Task.due_date` só guardava data; `due_soon` com `hours_left` exigia evoluir o modelo → subiu custo.
2. `Task.progress_done/total` **já existiam** → `off_pace` ficou barato.

Resultado: **copy antecipa**, **off_pace antecipa**, **due_soon adia**, **KPIs adiam** (dependem de `copy_variant` pra medir A/B).

| Versão | Feature | Custo | Valor TDAH | Status |
|---|---|---|---|---|
| v2.12.0 | Thresholds config + `max_nudges_per_tick` + agrupamento por task | baixo | médio (tuning) | ✅ |
| v2.13.0 | Copy library refatorada + `copy_variant` + `cooldown_applied` | baixo | alto (linguagem acionável) | ✅ |
| v2.14.0 | `first_touch` (spec §5.1, alvo nº1) | médio | alto | ✅ |
| v2.15.0 | `copy_variant` A/B determinístico (hash de `task_id:alert_type`) | médio | alto | ✅ (ver nota) |
| v2.16.0 | KPIs + instrumentação (`nudge-delivery`, `nudge-kpis`, `response_kind`) | médio | alto (mensuração) | ✅ |
| v2.17.0 | `due_soon` com janela horária (requer `due_time` no model) | alto | alto | ✅ |
| v2.18.0 | `missed_routine` opt-in (sigil `!nudge`) + `off_pace` | médio | médio/alto | ✅ |

> **Nota v2.15/v2.18:** `off_pace` (originalmente previsto em v2.15.0) aterrissou em v2.18.0 porque `copy_variant` A/B determinístico precedeu pra destravar KPIs em v2.16.0. Cobertura final inalterada — só mudou a tag onde cada parte aterrissou.

### Dependências realizadas

```
v2.12 (config infra) ─► v2.13 (copy + variant) ─┬─► v2.14 (first_touch) ─┐
                                                │                         │
                                                └─► v2.15 (A/B hash) ─────┤
                                                                          ▼
                                                               v2.16 (KPIs + ack)
                                                                          │
                                                                          ▼
                                                               v2.17 (due_soon hora)
                                                                          │
                                                                          ▼
                                                       v2.18 (missed_routine + off_pace)
```

---

## Descope — v2.19.0 (Guardrail de segurança) ❌

**Decisão (2026-04-19):** não implementar nesta skill.

**Motivo:** safety de crise exige camada separada — roteamento humano, hotlines, protocolos clínicos — que não se beneficia de acoplamento com ledger de produtividade. O risco de falso negativo num detector keyword-based embutido aqui é mais perigoso do que não ter detector. Se a decisão voltar, trilha da spec §14.3 continua válida: seção obrigatória em AGENTS ("saia do modo tasks, encaminhe humano") + `scripts/safety.py` opcional com `safety-check` + `safety-routing.json` com destino humano configurado.

---

## Futuro — v3.0+

Objetivo: integrar com ferramentas externas e expandir modalidade.

### Timer integrado

Pomodoro flexível (10/3, 15/5, 20/5, 25/5) acoplado a `ledger-start`. Auto-log de início/fim de sessões no ledger. Alerta de pausa pra evitar burnout. Custo: médio. Benefício TDAH: foco em uma coisa, ciclo adaptável.

### Body doubling

Sessão síncrona com outra pessoa; notificação de início/fim; log de participação. Custo: alto (integração externa). Benefício TDAH: accountability social.

### Notificações ampliadas

Lembrete de próxima ação perto do prazo; "esvazie a cabeça" periódico; review de fim de dia. Custo: médio. Benefício TDAH: fechamento mental, prevenção de sobrecarga.

### Export / Import

CSV, JSON completo, importar de Todoist/Notion. Custo: baixo a alto conforme destino. Benefício TDAH: portabilidade, migração fácil.

---

## Backlog — ideias sem prioridade

| Ideia | Descrição | Complexidade | Benefício TDAH |
|---|---|---|---|
| Gamificação | Streaks, pontos, níveis | Média | Motivação extrínseca |
| Análise de padrões | "Você adia tarefas de X tipo" | Alta | Autoconhecimento |
| Sugestão de divisão | IA quebra tarefa grande | Alta | Reduz paralisia |
| Modo hiperfoco | Bloqueia novas tasks, foco em uma | Baixa | Aproveita momento |
| Integração calendário | Google/Outlook Calendar | Alta | Visão unificada |
| Tags inteligentes | Auto-tag por contexto | Média | Organização automática |
| Modo baixa energia | Só tasks complexidade 1-3 | Baixa | Dias difíceis |
| Multi-device | Ledger na nuvem | Alta | Acesso de qualquer lugar |
| Comandos por voz | "Adicionar comprar leite" | Média | Captura rápida |
| Relatório mensal | Análise de produtividade | Média | Longo prazo |

---

## Critérios de priorização

Para decidir o que entra em cada versão:

1. **Impacto TDAH** — quanto ajuda no dia a dia?
2. **Complexidade** — quanto esforço pra implementar?
3. **Dependências** — o que precisa estar pronto antes?
4. **Custo cognitivo** — adiciona complexidade de uso?

**Princípio:** preferir features que *reduzem* decisões do usuário, não aumentam.

---

## Histórico de revisões

- **2026-04-18** — Draft orientado à spec TDAH v1.0 criado (`docs/roadmap-tdah-evidence.md`). Ordem ajustada: copy antecipa, off_pace antecipa, due_soon atrasa, KPIs atrasam.
- **2026-04-19** — Onda 2 encerrada (v2.12 → v2.18 entregues). v2.19 descopada. Documento consolidado: histórico v2.2–v2.18, descope, futuro e backlog num só arquivo.
