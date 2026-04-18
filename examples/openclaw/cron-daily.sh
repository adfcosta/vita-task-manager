#!/usr/bin/env bash
# ------------------------------------------------------------------
# Vita Morning — Cron interno do OpenClaw, diário às 06:00
#
# Execute ESTE COMANDO uma única vez (dentro do container openclaw-gateway
# ou na máquina onde o gateway roda) para registrar o job no scheduler
# nativo. O job persiste em ~/.openclaw/cron/jobs.json.
#
# Como funciona:
#
#   • --session main  → o evento cai na main session da Vita, que já
#     está quente porque o heartbeat (configurado em vita-agent-config.json5)
#     aquece ela a cada 55 min durante 06-23h.
#
#   • --system-event  → injeta texto na fila da main session, não spawna
#     sessão isolada. Mantém continuidade de contexto: a Vita "vê" o que
#     ela mesma fez no daily-tick durante o resto do dia.
#
#   • --wake now  → processa imediatamente, sem esperar o próximo
#     heartbeat natural.
#
# A mensagem é curta porque SKILL.md e patches/vita-AGENTS.md já estão
# carregados na main session. "Morning Pipeline" é um Standing Order
# documentado; a Vita sabe o que fazer.
#
# Referência: patches/vita-SESSION-DESIGN.md (Camada 4)
# Standing Order: Morning Pipeline (patches/vita-AGENTS.md)
# ------------------------------------------------------------------

openclaw cron add \
  --name "Vita morning" \
  --cron "0 6 * * *" \
  --tz "America/Maceio" \
  --agent "vita" \
  --session main \
  --wake now \
  --system-event "Execute o Morning Pipeline agora usando a data de hoje. Rode daily-tick do CLI, verifique o resultado, e entregue diarias.txt ao usuário com um sumário breve. Se qualquer sub-step falhar (ok: false), escale com diagnóstico."
