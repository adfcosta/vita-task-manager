# Heartbeat da Vita — prompt minimalista

Este arquivo é lido pela Vita em cada tick do heartbeat nativo do
Gateway (~55min, 06–23h Maceio). Mantenha **curto**: o conteúdo vira
prompt de LLM a cada 18+ ticks por dia.

## Onde instalar

Arquivo vivo: `~/.openclaw/workspace/vita/HEARTBEAT.md`

Substitua o conteúdo existente (geralmente template genérico com
Self-Improving Check / Proactivity Check comentados) pelo bloco
abaixo.

Pré-requisitos antes de ativar:

1. Skill `vita-task-manager` instalada em
   `~/.openclaw/workspace/vita/skills/vita-task-manager/`
2. Config de heartbeat em
   `~/.openclaw/workspace/vita/skills/vita-task-manager/data/heartbeat-config.json`
   com `emit_target` válido (ver `heartbeat-config.json.example`)
3. Tool `sessions_send` disponível para o agente vita (verificar na
   primeira execução — se faltar, ajustar allowlist do Gateway)

---

## Conteúdo do HEARTBEAT.md

```markdown
# Heartbeat

Execute exatamente estes passos, sem variar:

1. `exec`:
   `cd skills/vita-task-manager && python3 scripts/cli.py heartbeat-tick --today $(date +%d/%m) --year $(date +%Y) --data-dir data`

2. Ler o JSON retornado.

3. Se `emit_text` não vazio **e** `emit_target` não null:
   `sessions_send(session: emit_target, message: emit_text)`

4. Responder apenas: `HEARTBEAT_OK nudges=<nudges_new> emitted=<true|false>`

Não faça mais nada. Não leia memórias, não analise, não proponha.
Qualquer erro: retornar `HEARTBEAT_ERROR <mensagem curta>` e parar.
```

---

## Por que tão curto

- **Cache-friendly**: prompt estável = `cache_read` em vez de
  `cache_write` em todo tick (~$0.006 vs ~$0.03)
- **Determinístico**: toda lógica de filtro/cooldown está no CLI
  (Python), LLM apenas executa e roteia
- **Não polui contexto**: resposta de 1 linha, sem análise embebida

## O que o tick faz por baixo

```
heartbeat-tick
  ├─ chama _build_alerts() internamente
  ├─ filtra críticos: overdue≥2d, stalled≥48h, blocked≥3 postpones
  ├─ checa cooldown (24h padrão) contra data/proactive-nudges.jsonl
  ├─ persiste novos nudges (append-only)
  ├─ formata emit_text (1 linha para 1 nudge, bullets para muitos)
  └─ retorna JSON com emit_target lido de data/heartbeat-config.json
```

Se o Gateway não permitir `sessions_send` cross-agent pra Vita, o
emit_text falha mas o nudge **já foi persistido** — próxima
interação do usuário com a Vita surfa via
`cli nudges-pending`.

## Debug

Verificar nudges registrados:

```bash
python3 scripts/cli.py nudges-pending --data-dir data
```

Forçar ack manual (ex: se a Vita emitiu mas você quer silenciar):

```bash
python3 scripts/cli.py nudges-ack --nudge-id nudge_abc123 --data-dir data --source manual
```

Thresholds e cooldown vivem em `scripts/heartbeat.py` e no config
JSON — ajustar lá, não no HEARTBEAT.md.
