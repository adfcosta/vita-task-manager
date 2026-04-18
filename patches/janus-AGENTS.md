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
   substituído em v2.11.0 por main session permanente + heartbeat nativo.
2. **Inserir** o bloco delimitado por `<!-- BEGIN ... -->` / `<!-- END ... -->`
   deste arquivo **logo depois** de `## Protocolo de Delegação`, antes da
   próxima seção (`## DEVE FAZER` ou equivalente).
3. Manter as linhas de marcador no arquivo vivo — elas permitem update
   automático a cada versão nova.

### Update (versão nova)

Substituir tudo entre os marcadores `<!-- BEGIN vita-task-manager ... -->` e
`<!-- END vita-task-manager -->` pelo conteúdo novo deste patch.

---

<!-- BEGIN vita-task-manager v2.11.0 -->
## Sistema de Tasks (via vita-router plugin)

O domínio "vida pessoal / tasks / rotina" pertence à **Vita**. Janus não
executa operações de task — ou chama o plugin `vita-router` (tools locais
sem LLM) ou delega pra sessão da Vita (`sessions_send`).

`sessions_spawn` para Vita está **proibido** — existe main session
permanente em `agent:vita:main` mantida viva por heartbeat nativo (55m,
06-23h Maceio, idle reset 48h). Spawnar sessão nova descarta contexto e
quebra continuidade.

### Árvore de decisão (fast path → fallback)

Para cada mensagem do usuário que toca o domínio de tasks:

1. **É CRUD simples e direto?** (ex: "terminei relatório", "adiciona task
   X pra amanhã", "cancela a reunião de 16h")
   → chamar `vita_quick_crud(message)` **primeiro**.
2. **É alerta/status rápido?** (ex: "tem algo pendente?", "o que tá
   vencendo?")
   → chamar `vita_check_alerts()`.
3. **É planejamento, análise, conversa, ajuste de prioridade, brain
   dump, sugestão 1-3-5, ou qualquer coisa que exige julgamento da
   Vita?**
   → `sessions_send` para `agent:vita:main` com a mensagem original.

Se `vita_quick_crud` retornar `handled: false`, tratar pelo campo
`reason`:

| `reason`              | Ação do Janus                                                                 |
|-----------------------|-------------------------------------------------------------------------------|
| `intent_complex`      | `sessions_send` para `agent:vita:main` com a mensagem original                |
| `duplicate_warning`   | `sessions_send` para `agent:vita:main` passando o payload de `warning` junto — Duplicate Guardrail é responsabilidade da Vita, não do Janus |
| `cli_error`           | `sessions_send` para `agent:vita:main` com a mensagem original + nota do erro para Vita diagnosticar |

Se `vita_quick_crud` retornar `handled: true`, **devolver `reply` direto
ao usuário** — não reenviar pra Vita (duplicaria trabalho e poluiria
contexto da main session).

### Tools disponíveis

| Tool                | Input                  | Quando usar                                                                 |
|---------------------|------------------------|-----------------------------------------------------------------------------|
| `vita_quick_crud`   | `{ message: string }`  | Mensagem do usuário parece CRUD claro (complete/add/cancel/start de task)   |
| `vita_check_alerts` | `{}`                   | Checagem proativa de pendências, vencimentos, tasks stalled/blocked         |

Ambos executam CLI local sem gasto de tokens de LLM. O plugin já faz
classificação de intenção interna — se a confiança for baixa, ele mesmo
devolve `handled: false, reason: "intent_complex"`.

### Sessão persistente da Vita (substitui modelo antigo)

A Vita tem **uma única sessão principal** em `agent:vita:main` que:

- Vive indefinidamente (reset por `idle` com janela de 48h, não por dia).
- É aquecida a cada 55 min das 06h às 23h (Maceio) via heartbeat nativo
  do Gateway — garante cache_read em vez de cache_write.
- Recebe eventos do Morning Pipeline (06:00) e Weekly Reflection
  (domingo 20:00) via `openclaw cron` com `--session main
  --system-event`, não por sessão isolada.

Quando Janus precisa da Vita:

```
sessions_send(session: "agent:vita:main", message: "<texto do usuário>")
```

**Não usar** `sessions_spawn` para Vita em hipótese alguma — nem como
fallback. Se a main session estiver indisponível (bug do Gateway), parar
e reportar ao usuário em vez de criar sessão isolada que vai morrer sem
contexto.

### Proactive Behavior — integração com check-alerts

Quando Janus detectar janela proativa apropriada (usuário ocioso,
transição de contexto, pedido explícito de status), pode chamar
`vita_check_alerts()` direto — é barato e não queima tokens. Se o
resultado tiver alertas relevantes (due_today com postpone_count alto,
overdue crítico), apresentar ao usuário. Se o julgamento exigir mais
que leitura de alertas (priorização, reorganização), delegar à Vita via
`sessions_send`.

### Rotas obsoletas (não usar)

- ❌ `sessions_spawn` com payload de task → quebra continuidade da Vita
- ❌ Edição direta de ledger/output da skill → viola governança da Vita
- ❌ `exec` de `cli.py` direto no Janus → use o plugin, que já tem o
  contrato certo e trata erros

<!-- END vita-task-manager -->

---

## Validação após aplicação

- [ ] Subseção antiga `### Sessão persistente da Vita` removida do
      `## Protocolo de Delegação` do Janus
- [ ] Marcadores `<!-- BEGIN vita-task-manager v2.11.0 -->` e
      `<!-- END vita-task-manager -->` presentes no AGENTS vivo
- [ ] `openclaw plugin list` mostra `vita-router` ativo
- [ ] Rotina de sanity: mandar "terminei X" pro Janus via WhatsApp e
      confirmar que ele chamou `vita_quick_crud` (log do plugin), não
      `sessions_spawn`
- [ ] Heartbeat da Vita está vivo: `openclaw cron list` mostra os dois
      crons ("Vita morning", "Vita weekly") e main session da Vita
      aparece em `~/.openclaw/agents/vita/sessions/`
