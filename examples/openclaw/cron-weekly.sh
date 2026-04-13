#!/usr/bin/env bash
# ------------------------------------------------------------------
# Vita Weekly — Cron semanal domingo 20:00 (Fase 1)
#
# Cria sessão isolada da Vita, roda weekly-tick, apresenta
# taxa de conclusão e candidatos de recorrência.
#
# Referência: patches/vita-SESSION-DESIGN.md (Camada 1)
# Standing Order: Weekly Reflection (patches/vita-AGENTS.md)
# ------------------------------------------------------------------

openclaw cron add \
  --name "Vita weekly" \
  --cron "0 20 * * 0" \
  --tz "America/Maceio" \
  --agent "vita" \
  --session isolated \
  --message "Execute o weekly-tick da skill vita-task-manager:

python3 scripts/cli.py weekly-tick \\
  --today \$(date +%d/%m) --year \$(date +%Y) \\
  --data-dir data \\
  --history-output data/historico-execucao.md

Após executar:
1. Verificar que o JSON retornado tem ok: true
2. Apresentar ao usuário a taxa de conclusão da semana
3. Se steps.recurrence_candidates.candidates não estiver vazio,
   apresentar os candidatos com suggestion_reason
4. NÃO ativar regras de recorrência sem aprovação explícita do usuário
5. Se execution-history indicar taxa de conclusão < 40%, não sugerir
   novas recorrências (semana foi difícil)
6. Se ok: false em qualquer sub-step, escalar ao usuário

Seguir o programa Weekly Reflection documentado em AGENTS.md." \
  --announce
