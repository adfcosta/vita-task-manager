# Patch — Vita AGENTS.md (skill vita-task-manager)

Este patch instala o bloco operacional da skill `vita-task-manager`
no AGENTS vivo da Vita. Session Start, Scope, Safety, Memory e demais
seções ficam no AGENTS vivo e **não são tocadas** — o patch só injeta
o que é específico da skill.

## Onde instalar

Arquivo vivo: `~/.openclaw/workspace/vita/AGENTS.md`

### Primeira instalação

1. Localizar posição logo após `### Não inclui` (fim da seção `## Scope`).
2. Inserir o bloco delimitado por `<!-- BEGIN vita-task-manager ... -->`
   e `<!-- END vita-task-manager -->` deste arquivo.
3. Manter os marcadores no arquivo vivo — eles permitem update
   automático.

### Update (versão nova)

Substituir tudo entre os marcadores pelo conteúdo novo deste patch.

---

<!-- BEGIN vita-task-manager v2.11.2 -->
## Sistema de Tasks (via vita-task-manager)

**Regra de ouro:** Vita nunca edita arquivos de task direto. Toda
escrita passa por `python3 scripts/cli.py ...` (skill em
`skills/vita-task-manager/`). Detalhe de comandos, flags e formato
vive em `SKILL.md`.

### Paths

- **Leitura (contexto):** `input/rotina.md`, `input/agenda-semana.md`,
  `output/diarias.txt`, `data/historico-execucao.md`
- **Gerenciado pela skill (não tocar):** `data/historico/*.jsonl`,
  `data/word_weights.json`, `output/*`
- `input/rotina.md` e `input/agenda-semana.md` são editados pelo
  usuário — skill apenas lê.

### Operações → comando

| Intenção | Comando |
|---|---|
| Adicionar task | `ledger-add` |
| Refinar task existente | `ledger-update` (não `ledger-add`) |
| Iniciar / progredir / concluir / cancelar | `ledger-start` / `ledger-progress` / `ledger-complete` / `ledger-cancel` |
| Captura rápida (TDAH) | `brain-dump`; promover com `dump-to-task` |
| Priorização | `score-task`, `suggest-daily`, `explain-task` |
| WIP / diagnóstico | `check-wip`, `ledger-status` |
| Alertas | `check-alerts` |
| Render | `render` (ou incluso em `pipeline`) |
| Tick diário / semanal | `daily-tick` / `weekly-tick` |
| Heartbeat / nudges | `heartbeat-tick`, `nudges-pending`, `nudges-ack` |
| Recorrência | `recurrence-detect` → **usuário aprova** → `recurrence-activate` / `recurrence-list` / `recurrence-deactivate` |

### Duplicate Guardrail

Se `ledger-add` retornar `warning.type == "duplicate_suspect"`:

1. Parar.
2. Apresentar a task similar ao usuário.
3. Oferecer: atualizar a existente (`ledger-update`), criar mesmo
   assim (`--allow-duplicate`), ou cancelar.
4. Nunca decidir sozinha.

Antes de `ledger-add`, perguntar: task nova de verdade ou refinamento
de algo que já existe? Refinamento → `ledger-update`.

### Standing Orders

- **Morning Pipeline** (06:00 Maceio): rodar `daily-tick`, verificar
  `ok: true`, entregar `output/diarias.txt` com sumário breve.
  Escalar se: `ok: false`, > 3 tasks com `postpone_count >= 3`, ou
  > 15 tasks abertas.
- **Weekly Reflection** (dom 20:00): rodar `weekly-tick`, apresentar
  taxa de conclusão e candidatos de recorrência com `suggestion_reason`.
  **`recurrence-activate` exige aprovação explícita.** Não sugerir
  recorrências se taxa de conclusão < 40% na semana.
- **Duplicate Guardrail** (event-triggered): ver acima. Warning =
  pergunta obrigatória, sem caminho silencioso.

### Heartbeat proativo

A cada tick do heartbeat (55min, 06–23h Maceio), Vita executa:

```
python3 scripts/cli.py heartbeat-tick --today DD/MM --year YYYY --data-dir data
```

Se o JSON retornado tiver `emit_text` não-vazio **e** `emit_target`
não-null, emitir imediatamente:

```
sessions_send(session: emit_target, message: emit_text)
```

O CLI já persiste novos nudges em `data/proactive-nudges.jsonl` e
respeita cooldown de 24h. Thresholds críticos: `overdue ≥ 2 dias`,
`stalled ≥ 48h`, `blocked ≥ 3 postpones`.

Backup de surfacing: se `sessions_send` falhar ou estiver
indisponível, o nudge já está no disco — próxima interação normal
pode trazê-lo à tona via `cli nudges-pending`.

O template do HEARTBEAT.md vive em
`examples/openclaw/vita-HEARTBEAT.md`.

### Execute-Verify-Report

Todo comando:

1. **Execute** — rodar de fato (não prometer "vou fazer X").
2. **Verify** — `ok: true`, arquivo atualizado, `task_id` retornado.
3. **Report** — dizer o que foi feito *e verificado*. Máximo 3
   tentativas antes de escalar.

### Não autorizado

- `recurrence-activate` sem aprovação
- `ledger-add --allow-duplicate` sem perguntar
- Editar `input/rotina.md` ou `input/agenda-semana.md` (read-only)
- `execution-history --weeks > 12` por conta própria

<!-- END vita-task-manager -->

---

## Validação após aplicação

- [ ] Marcadores `<!-- BEGIN vita-task-manager v2.11.2 -->` e
      `<!-- END vita-task-manager -->` presentes no AGENTS vivo
- [ ] Seções fora do bloco (Session Start, Scope, Safety, Memory,
      Operating Rules, etc.) intactas
- [ ] `cli daily-tick` roda no Morning Pipeline sem intervenção
- [ ] `cli ledger-add` com task similar dispara pergunta ao usuário
      (Duplicate Guardrail)
