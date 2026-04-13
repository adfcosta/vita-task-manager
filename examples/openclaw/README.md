# Exemplos de configuração OpenClaw

Artefatos prontos para copiar referentes à proposta de otimização
de sessão documentada em `patches/vita-SESSION-DESIGN.md`.

## Arquivos

| Arquivo | Fase | O que faz |
|---|---|---|
| `cron-daily.sh` | 1 | Cron matinal (06:00) — spawna Vita, roda daily-tick |
| `cron-weekly.sh` | 1 | Cron semanal (dom 20:00) — spawna Vita, roda weekly-tick |
| `vita-agent-config.json5` | 1 | Config do agente Vita: idleMinutes, pruning, memoryFlush |
| `janus-routing.ts` | 1+2 | Routing do Janus: sessions_send + Plugin SDK CRUD |

## Ordem de aplicação

### Fase 1 (config-only, ~60-77% redução de tokens)

1. Aplicar `vita-agent-config.json5` na config do agente Vita
2. Rodar `cron-daily.sh` para registrar o cron matinal
3. Rodar `cron-weekly.sh` para registrar o cron semanal
4. Integrar `routeToVita()` de `janus-routing.ts` no routing do Janus

### Fase 2 (Plugin SDK, ~15-20% redução adicional)

5. Integrar `routeToVitaWithPlugin()` de `janus-routing.ts`
6. Ajustar `VITA_SKILL_PATH` no arquivo para o caminho real
7. Testar `classifyIntent` com exemplos reais antes de ativar

## Notas

- Os `.sh` são comandos `openclaw cron add` — rodar **uma vez**
- O `.json5` é merge na config existente, não substituição
- O `.ts` é snippet — adaptar às interfaces reais do Janus
- Ajustar `America/Maceio` para o timezone correto se necessário
