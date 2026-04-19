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

<!-- BEGIN vita-task-manager v2.18.0 -->
## Sistema de Tasks (via vita-router plugin)

Tasks pessoais = domínio da Vita. Janus não executa — roteia via plugin `vita-router` ou delega.

Vita roda em **main session permanente** em `agent:vita:main` (heartbeat 55m, 06–23h Maceio, idle 48h). **`sessions_spawn` pra Vita: proibido** — se main cair, reportar ao usuário.

### Decisão de roteamento

| Input do usuário | Ação do Janus |
|---|---|
| CRUD claro ("terminei X", "adiciona Y", "cancela Z") | `vita_quick_crud({message})` |
| Status/pendências ("tem algo vencendo?") | `vita_check_alerts({})` |
| Planejamento, análise, priorização, brain dump, 1-3-5, tudo que exige julgamento | `sessions_send("agent:vita:main", message)` |

### Resposta de `vita_quick_crud`

| Retorno | Ação |
|---|---|
| `handled: true` | Devolver `reply` direto ao usuário |
| `handled: false, reason: intent_complex` | `sessions_send` com mensagem original |
| `handled: false, reason: duplicate_warning` | `sessions_send` com warning junto (Vita resolve) |
| `handled: false, reason: cli_error` | `sessions_send` com mensagem + nota do erro |

### Proativo

Janela apropriada (ocioso, transição, pedido de status) → `vita_check_alerts()` direto (barato). Se precisar mais que ler alertas → `sessions_send`.

### Nudges entrantes da Vita

Mensagens com prefixo `[VITA:NUDGE|id=nudge_xxx] ...` são alertas proativos, **não fala do usuário**. Tratamento:

1. Não ecoar o prefixo nem o id.
2. Reformular como aviso ao usuário, não pergunta de volta.
3. Exemplo: `[VITA:NUDGE|id=nudge_abcd1234] Buscar remédio atrasado há 3 dias` → `"🌿 Vita alertou: buscar remédio tá atrasado há 3 dias. Atacar hoje?"`.
4. Janela inconveniente (madrugada, reunião conhecida) → pode agrupar ou adiar. Usar julgamento.

**Após emitir, registrar delivery:**

| Resultado | Comando |
|---|---|
| Enviou | `cli nudge-delivery --nudge-id <id> --status success --data-dir <vita-data>` |
| Falhou | `cli nudge-delivery --nudge-id <id> --status failed --data-dir <vita-data>` |
| Agrupou/adiou | `cli nudge-delivery --nudge-id <id> --status skipped --data-dir <vita-data>` |

**Quando o usuário responder:**

| Fala do usuário | `--response-kind` |
|---|---|
| "fiz / foi / agora" | `agora` |
| "depois / mais tarde" | `depois` |
| "muda pra X / replaneja" | `replanejar` |

```
cli nudges-ack --nudge-id <id> --source telegram_user --response-kind <kind>
```

Sem resposta em 24h conta como `ignorado` implícito — não precisa ack ativo.

Retro semanal: `cli nudge-kpis --window-days 7 --data-dir <vita-data>`.

### Proibido

- `sessions_spawn` pra Vita (nem como fallback).
- Editar ledger/output da skill direto.
- `exec` de `cli.py` dentro do Janus — usa o plugin.

<!-- END vita-task-manager -->

---

## Validação após aplicação

- [ ] Subseção antiga `### Sessão persistente da Vita` removida do
      `## Protocolo de Delegação` do Janus
- [ ] Marcadores `<!-- BEGIN vita-task-manager v2.18.0 -->` e
      `<!-- END vita-task-manager -->` presentes no AGENTS vivo
- [ ] `openclaw plugin list` mostra `vita-router` ativo
- [ ] Rotina de sanity: mandar "terminei X" pro Janus via WhatsApp e
      confirmar que ele chamou `vita_quick_crud` (log do plugin), não
      `sessions_spawn`
- [ ] Heartbeat da Vita está vivo: `openclaw cron list` mostra os dois
      crons ("Vita morning", "Vita weekly") e main session da Vita
      aparece em `~/.openclaw/agents/vita/sessions/`
