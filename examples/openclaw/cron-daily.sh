#!/usr/bin/env bash
# ------------------------------------------------------------------
# Vita Morning — Cron diário às 06:00 (Fase 1)
#
# Roda daily-tick na sessão nomeada "vita-daily". A sessão
# persiste entre runs, permitindo que o Janus comunique via
# sessions_send ao longo do dia sem bootstrap repetido.
#
# Reset automático: 04:00 (default do OpenClaw) — a sessão
# do dia anterior morre antes do cron das 06:00 criar a nova.
#
# Referência: patches/vita-SESSION-DESIGN.md (Camada 1)
# Standing Order: Morning Pipeline (patches/vita-AGENTS.md)
# ------------------------------------------------------------------

openclaw cron add \
  --name "Vita morning" \
  --cron "0 6 * * *" \
  --tz "America/Maceio" \
  --agent "vita" \
  --session "session:vita-daily" \
  --message "Execute o daily-tick da skill vita-task-manager:

python3 scripts/cli.py daily-tick \\
  --today \$(date +%d/%m) --year \$(date +%Y) \\
  --rotina input/rotina.md \\
  --agenda-semana input/agenda-semana.md \\
  --data-dir data \\
  --output output/diarias.txt \\
  --history-output data/historico-execucao.md

Após executar:
1. Verificar que o JSON retornado tem ok: true
2. Verificar que output/diarias.txt foi atualizado
3. Entregar diarias.txt ao usuário com sumário breve
4. Se ok: false em qualquer sub-step, escalar ao usuário com diagnóstico

Seguir o programa Morning Pipeline documentado em AGENTS.md." \
  --announce
