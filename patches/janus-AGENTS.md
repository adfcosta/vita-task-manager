# Patch — main AGENTS.md (domínio Vita)

> Nota: o agente com display "Janus" tem `agentId = main` no OpenClaw.
> Workspace vivo: `~/.openclaw/workspace/janus/AGENTS.md`.
> Session keys: `agent:main:*`.

Este patch instrui o **Janus** sobre como operar o domínio de tasks pessoais
(Vita) usando os tools do plugin `vita-router` e a sessão permanente da Vita.
Sem este patch, Janus não sabe que os tools existem, tenta operar via
`sessions_spawn` (modelo antigo) e queima tokens à toa.

## Onde instalar

Arquivo vivo: `~/.openclaw/workspace/janus/AGENTS.md`

### Primeira instalação

1. **Remover** a subseção `### Sessão persistente da Vita` dentro de
   `## Protocolo de Delegação` — ela descreve o modelo antigo (cron
   diário com sessão isolada + fallback via `sessions_spawn`), que foi
   substituído em v2.11.0/v2.11.1 por main session permanente + heartbeat
   nativo (delegação via `sessions_send`) e cron nativo em turno isolado
   (ticks periódicos).
2. **Inserir** o bloco delimitado por `<!-- BEGIN ... -->` / `<!-- END ... -->`
   deste arquivo **logo depois** de `## Protocolo de Delegação`, antes da
   próxima seção (`## DEVE FAZER` ou equivalente).
3. Manter as linhas de marcador no arquivo vivo — elas permitem update
   automático a cada versão nova.

### Update (versão nova)

Substituir tudo entre os marcadores `<!-- BEGIN vita-task-manager ... -->` e
`<!-- END vita-task-manager -->` pelo conteúdo novo deste patch.

---

<!-- BEGIN vita-task-manager v2.17.0 -->
## Sistema de Tasks (via vita-router plugin)

Domínio de tasks pessoais pertence à Vita. Janus não executa — usa plugin `vita-router` ou delega.

**`sessions_spawn` para Vita: proibido.** Main session permanente em `agent:vita:main` (heartbeat 55m, 06-23h Maceio, idle 48h).

### Decisão

1. CRUD claro ("terminei X", "adiciona Y", "cancela Z") → `vita_quick_crud({message})`
2. Status/pendências ("tem algo vencendo?") → `vita_check_alerts({})`
3. Planejamento, análise, priorização, brain dump, 1-3-5 → `sessions_send("agent:vita:main", message)`

### Fallback de `vita_quick_crud`

- `handled: true` → devolver `reply` direto ao usuário
- `handled: false, reason: intent_complex` → `sessions_send` com mensagem original
- `handled: false, reason: duplicate_warning` → `sessions_send` com warning junto (Vita resolve)
- `handled: false, reason: cli_error` → `sessions_send` com mensagem + nota do erro

### Proativo

Janela apropriada (ocioso, transição, pedido de status) → `vita_check_alerts()` direto (barato). Julgamento além de ler alertas → `sessions_send`.

### Nudges proativos da Vita

Mensagens entrantes com prefixo `[VITA:NUDGE]` são alertas proativos emitidos pelo heartbeat da Vita, **não fala do usuário**. Tratamento:

1. Não responder perguntando de volta — reformular como aviso ao usuário.
2. Não ecoar o prefixo.
3. Ex: entrada `[VITA:NUDGE] Buscar remédio atrasado há 3 dias` → resposta `"🌿 Vita alertou: buscar remédio tá atrasado há 3 dias. Atacar hoje?"`.
4. Se chegar em janela inconveniente (madrugada, reunião conhecida), pode agrupar ou adiar — usar julgamento.

### Instrumentação de nudges (v2.16.0, spec §11)

Todo nudge que chega tem um `nudge_id` extraível do payload (`[VITA:NUDGE|id=nudge_abcd1234] ...`). Quando Janus emite pro usuário:

1. **Após envio bem-sucedido:** `cli nudge-delivery --nudge-id <id> --status success --data-dir <vita-data>` (via Vita main session ou exec direto se permitido).
2. **Após falha de envio:** mesmo comando com `--status failed`.
3. **Se decidir agrupar/adiar e não emitir:** `--status skipped`.

Quando usuário responde:

- "fiz agora / foi" → `cli nudges-ack --nudge-id <id> --source telegram_user --response-kind agora`
- "depois / mais tarde" → `--response-kind depois`
- "muda pra X / replaneja" → `--response-kind replanejar`
- Sem resposta em 24h / trata como passa-quieto → ledger registra `ignorado` implicitamente via `ignored_rate` no KPI (não precisa ack ativo).

KPIs consolidados via `cli nudge-kpis --window-days 7 --data-dir <vita-data>` — use em retro semanal pra ver taxa de ação/ignorado por alert_type e por variante A/B.

### Proibido

- `sessions_spawn` pra Vita (nem como fallback — se main cair, reportar ao usuário)
- Editar ledger/output da skill direto
- `exec` de `cli.py` no Janus (usa o plugin)

<!-- END vita-task-manager -->

---

## Validação após aplicação

- [ ] Subseção antiga `### Sessão persistente da Vita` removida do
      `## Protocolo de Delegação` do Janus
- [ ] Marcadores `<!-- BEGIN vita-task-manager v2.17.0 -->` e
      `<!-- END vita-task-manager -->` presentes no AGENTS vivo
- [ ] `openclaw plugin list` mostra `vita-router` ativo
- [ ] Rotina de sanity: mandar "terminei X" pro Janus via WhatsApp e
      confirmar que ele chamou `vita_quick_crud` (log do plugin), não
      `sessions_spawn`
- [ ] Heartbeat da Vita está vivo: `openclaw cron list` mostra os dois
      crons ("Vita morning", "Vita weekly") e main session da Vita
      aparece em `~/.openclaw/agents/vita/sessions/`
