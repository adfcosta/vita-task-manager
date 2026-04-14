#!/usr/bin/env bash
# ------------------------------------------------------------------
# Vita Weekly — Cron semanal domingo 20:00 (Fase 1)
#
# Roda weekly-tick na mesma sessão nomeada "vita-daily".
# Reutiliza a sessão do dia (se ainda viva) para ter contexto
# das interações da semana. Se a sessão já resetou (após 04:00),
# cria uma nova automaticamente.
#
# Referência: patches/vita-SESSION-DESIGN.md (Camada 1)
# Standing Order: Weekly Reflection (patches/vita-AGENTS.md)
# ------------------------------------------------------------------

openclaw cron add \
  --name "Vita weekly" \
  --cron "0 20 * * 0" \
  --tz "America/Maceio" \
  --agent "vita" \
  --session "session:vita-daily" \
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
