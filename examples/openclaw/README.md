# Exemplos de configuração OpenClaw

Artefatos prontos para copiar referentes à proposta de otimização
de sessão documentada em `patches/vita-SESSION-DESIGN.md`.

## Arquivos

| Arquivo | Fase | O que faz |
|---|---|---|
| `cron-daily.sh` | 1 | Cron matinal (06:00) — roda daily-tick na sessão `vita-daily` |
| `cron-weekly.sh` | 1 | Cron semanal (dom 20:00) — roda weekly-tick na sessão `vita-daily` |
| `vita-agent-config.json5` | 1 | Config `agents.defaults`: pruning + memoryFlush |
| `vita-router-plugin/` | 2 | Plugin OpenClaw: tools vita_quick_crud + vita_check_alerts |

## Modelo de sessão

```
04:00  reset automático (default OpenClaw) — sessão anterior morre
06:00  cron cria sessão "vita-daily" + roda daily-tick
  │
  ├─ 08:00  Janus → sessions_send("session:vita-daily", task)
  ├─ 11:00  Janus → sessions_send("session:vita-daily", task)
  ├─ 15:00  Janus → sessions_send("session:vita-daily", task)
  ├─ 20:00  cron weekly reutiliza a mesma sessão
  │
04:00  reset automático — ciclo recomeça
```

Sem `idleMinutes` extra. O reset diário às 04:00 já garante
que a sessão sobreviva das 06:00 até a madrugada seguinte.

## Ordem de aplicação

### Fase 1 (config-only, ~60-77% redução de tokens)

1. Aplicar `vita-agent-config.json5` em `agents.defaults` do gateway
2. Rodar `cron-daily.sh` para registrar o cron matinal
3. Rodar `cron-weekly.sh` para registrar o cron semanal
4. Ajustar routing do Janus: `sessions_send("session:vita-daily", ...)` quando domínio for Vita

### Fase 2 (Plugin SDK, ~15-20% redução adicional)

5. Instalar `vita-router-plugin/` no OpenClaw
6. Configurar `vitaSkillPath` no `openclaw.json`
7. Testar `classifyIntent` com exemplos reais antes de ativar
8. Ajustar AGENTS.md do Janus para usar `vita_quick_crud` antes de delegar

## Notas

- Os `.sh` são comandos `openclaw cron add` — rodar **uma vez**
- O `.json5` é merge em `agents.defaults`, não substituição
- A sessão `vita-daily` reseta automaticamente às 04:00 (default)
- Ajustar `America/Maceio` para o timezone correto se necessário
