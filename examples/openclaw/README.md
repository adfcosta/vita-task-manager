# Exemplos de configuração OpenClaw

Artefatos prontos para copiar referentes à arquitetura de sessão
documentada em `patches/vita-SESSION-DESIGN.md`.

## Arquivos

| Arquivo | Fase | O que faz |
|---|---|---|
| `cron-daily.sh` | 1 | Cron matinal (06:00 Maceio) — turno isolado da Vita que roda `daily-tick` |
| `cron-weekly.sh` | 1 | Cron semanal (dom 20:00 Maceio) — turno isolado da Vita que roda `weekly-tick` |
| `vita-agent-config.json5` | 1 | Merge em `agents.defaults`: pruning, memoryFlush, heartbeat, session.reset idle |
| `vita-router-plugin/` | 2 | Plugin OpenClaw: tools `vita_quick_crud` + `vita_check_alerts` (execução local, sem LLM) |

## Modelo de sessão

```
agent:vita:main   ◀── permanente, reset por idle 48h
  │
  ├─ 06:00 Mac    heartbeat nativo (55min, 06-23h) mantém cache quente
  ├─ 06:55        heartbeat
  ├─ 07:50        heartbeat
  ├─ ...
  └─ 23:05        heartbeat (última do dia)

cron nativo do Gateway   ◀── disparos independentes
  ├─ 06:00 Mac    turno ISOLADO: daily-tick → escreve output/diarias.txt
  └─ dom 20:00    turno ISOLADO: weekly-tick → escreve ledger JSONL

Janus → agent:vita:main via sessions_send  (nunca sessions_spawn)
Janus → plugin vita-router tools           (fast path, sem LLM)
```

### Por que turno isolado para cron?

O Gateway do OpenClaw restringe `sessionTarget: "main"` ao agente
**default** (Janus). Agentes non-default (Vita, Faber, etc.) só
aceitam `--session isolated --message` (payload `agentTurn`).

Consequência: os crons **não injetam** evento na `main` que o
heartbeat mantém. Eles rodam em turno próprio, escrevem em disco
(`output/diarias.txt`, ledger JSONL), e a `main` consulta o disco
quando a conversa chega. **Continuidade vem do disco, não da
conversa.**

## Ordem de aplicação

### Fase 1 (config + crons)

1. Merge `vita-agent-config.json5` no `~/.openclaw/openclaw.json`
   (blocos `session.reset`, `agents.defaults`, `heartbeat`)
2. Rodar `cron-daily.sh` dentro do container do Gateway (uma vez)
3. Rodar `cron-weekly.sh` dentro do container do Gateway (uma vez)
4. Confirmar com `openclaw cron list`

### Fase 2 (plugin + patches)

5. Plugin `vita-router` já é auto-loaded em
   `~/.openclaw/extensions/vita-router/` se estiver presente
6. Aplicar `patches/janus-AGENTS.md` em
   `~/.openclaw/workspace/janus/AGENTS.md` — Janus passa a usar
   `vita_quick_crud` / `vita_check_alerts` / `sessions_send` para
   `agent:vita:main`
7. Aplicar `patches/vita-AGENTS.md` em
   `~/.openclaw/workspace/vita/AGENTS.md` — Vita ganha o bloco
   operacional da skill

## Notas

- Os `.sh` são comandos `openclaw cron add` — rodar **uma vez**
  dentro do container onde o Gateway roda
- O `.json5` é merge em `~/.openclaw/openclaw.json`, **não**
  substituição
- Ajustar `America/Maceio` para o timezone correto se necessário
- `sessions_spawn` para a Vita é **proibido** — o patch do Janus
  formaliza isso
