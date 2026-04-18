# Patch — Janus AGENTS.md (domínio Vita)

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

<!-- BEGIN vita-task-manager v2.11.1 -->
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

### Proibido

- `sessions_spawn` pra Vita (nem como fallback — se main cair, reportar ao usuário)
- Editar ledger/output da skill direto
- `exec` de `cli.py` no Janus (usa o plugin)

<!-- END vita-task-manager -->

---

## Validação após aplicação

- [ ] Subseção antiga `### Sessão persistente da Vita` removida do
      `## Protocolo de Delegação` do Janus
- [ ] Marcadores `<!-- BEGIN vita-task-manager v2.11.1 -->` e
      `<!-- END vita-task-manager -->` presentes no AGENTS vivo
- [ ] `openclaw plugin list` mostra `vita-router` ativo
- [ ] Rotina de sanity: mandar "terminei X" pro Janus via WhatsApp e
      confirmar que ele chamou `vita_quick_crud` (log do plugin), não
      `sessions_spawn`
- [ ] Heartbeat da Vita está vivo: `openclaw cron list` mostra os dois
      crons ("Vita morning", "Vita weekly") e main session da Vita
      aparece em `~/.openclaw/agents/vita/sessions/`
