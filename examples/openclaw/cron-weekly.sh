#!/usr/bin/env bash
# ------------------------------------------------------------------
# Vita Weekly — Cron interno do OpenClaw, domingo 20:00
#
# Mesma mecânica do cron-daily.sh: evento injetado na main session da
# Vita via scheduler nativo do Gateway. Vita usa os tools do plugin/CLI
# para rodar weekly-tick, e o output fica no histórico da própria main
# session — disponível pra ela consultar ao longo da semana seguinte.
#
# Referência: patches/vita-SESSION-DESIGN.md (Camada 4)
# Standing Order: Weekly Reflection (patches/vita-AGENTS.md)
# ------------------------------------------------------------------

openclaw cron add \
  --name "Vita weekly" \
  --cron "0 20 * * 0" \
  --tz "America/Maceio" \
  --agent "vita" \
  --session main \
  --wake now \
  --system-event "Execute o Weekly Reflection agora usando a data de hoje. Rode weekly-tick do CLI, apresente ao usuário a taxa de conclusão da semana. Se houver candidatos de recorrência, apresente com suggestion_reason mas NÃO ative sem aprovação explícita. Se a taxa de conclusão for < 40%, não sugira novas recorrências (semana difícil)."
