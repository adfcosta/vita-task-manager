#!/usr/bin/env bash
# ------------------------------------------------------------------
# Vita Morning — Cron diário às 06:00 (Fase 1)
#
# Cria sessão isolada da Vita, roda daily-tick e entrega
# diarias.txt via canal configurado.
#
# Referência: patches/vita-SESSION-DESIGN.md (Camada 1)
# Standing Order: Morning Pipeline (patches/vita-AGENTS.md)
# ------------------------------------------------------------------

openclaw cron add \
  --name "Vita morning" \
  --cron "0 6 * * *" \
  --tz "America/Maceio" \
  --agent "vita" \
  --session isolated \
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
