#!/usr/bin/env bash
# ------------------------------------------------------------------
# Vita Weekly — Cron interno do OpenClaw, domingo 20:00
#
# Mesma mecânica do cron-daily.sh: turno isolado na Vita (único padrão
# suportado pelo Gateway para non-default agents). weekly-tick escreve
# resultados no disco da skill; a main session consulta depois.
#
# Ver cron-daily.sh para justificativa completa da restrição
# "isolated + agentTurn".
#
# Referência: patches/vita-SESSION-DESIGN.md (Camada 4)
# Standing Order: Weekly Reflection (patches/vita-AGENTS.md)
# ------------------------------------------------------------------

openclaw cron add \
  --name "Vita weekly" \
  --cron "0 20 * * 0" \
  --tz "America/Maceio" \
  --agent "vita" \
  --session isolated \
  --message "Execute o Weekly Reflection agora usando a data de hoje. Rode weekly-tick do CLI, apresente ao usuário a taxa de conclusão da semana. Se houver candidatos de recorrência, apresente com suggestion_reason mas NÃO ative sem aprovação explícita. Se a taxa de conclusão for < 40%, não sugira novas recorrências (semana difícil)."
