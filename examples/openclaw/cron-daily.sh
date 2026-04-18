#!/usr/bin/env bash
# ------------------------------------------------------------------
# Vita Morning — Cron interno do OpenClaw, diário às 06:00
#
# Execute ESTE COMANDO uma única vez (dentro do container openclaw-gateway
# ou na máquina onde o gateway roda) para registrar o job no scheduler
# nativo. O job persiste em ~/.openclaw/cron/jobs.json.
#
# ------------------------------------------------------------------
# RESTRIÇÃO DO GATEWAY (descoberta em runtime):
#
#   sessionTarget "main" só é válido para o agente DEFAULT (Janus).
#   Para non-default agents (Vita, Faber, etc.), o Gateway exige:
#     --session isolated  +  --message (payload.kind "agentTurn")
#
# Consequência de design:
#
#   O cron dispara um TURNO ISOLADO da Vita — não injeta evento na
#   main session que o heartbeat mantém aquecida. A Vita executa o
#   daily-tick no turno isolado, escreve em output/diarias.txt, e
#   depois a main (quando acionada por mensagem ou heartbeat) LÊ o
#   arquivo como faz em qualquer outra interação.
#
#   A continuidade vem do DISCO (arquivos da skill), não da conversa.
#   "Vita se lembra do que fez no tick" via diarias.txt + ledger,
#   não via histórico de mensagens.
#
#   Mesmo padrão dos crons do Faber que já rodam no Gateway.
#
# Referência: patches/vita-SESSION-DESIGN.md (Camada 4)
# Standing Order: Morning Pipeline (patches/vita-AGENTS.md)
# ------------------------------------------------------------------

openclaw cron add \
  --name "Vita morning" \
  --cron "0 6 * * *" \
  --tz "America/Maceio" \
  --agent "vita" \
  --session isolated \
  --message "Execute o Morning Pipeline agora usando a data de hoje. Rode daily-tick do CLI, verifique o resultado, e entregue diarias.txt ao usuário com um sumário breve. Se qualquer sub-step falhar (ok: false), escale com diagnóstico."
