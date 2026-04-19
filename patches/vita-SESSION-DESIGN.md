# Vita Session Optimization — Proposta de Design

> **Nota:** este é um documento de design (referência histórica, não aplicado como
> patch). A versão abaixo (**2.11.1**) é do próprio documento — marca a última vez
> que o design foi revisado — e é **independente da versão da skill**
> (atualmente 2.18.0). Não precisa bump a cada release da skill; só atualizar
> quando o desenho do modelo de sessão mudar.

**Status:** Em produção (Camadas 2, 3, 4); Camada 1 revisada em v2.11.1  
**Versão do documento:** 2.11.1 (design doc — independente da versão da skill)  
**Data:** 2026-04-18  
**Referências:**
- https://docs.openclaw.ai/automation/cron-jobs
- https://docs.openclaw.ai/gateway/heartbeat
- https://docs.openclaw.ai/concepts/multi-agent
- https://docs.openclaw.ai/reference/session-management-compaction
- https://docs.openclaw.ai/concepts/session-pruning
- https://docs.openclaw.ai/automation/standing-orders
- https://docs.openclaw.ai/plugins/architecture (Plugin SDK)

**Changelog:**
- **v2.11.1** — Camada 1 corrigida após descoberta em runtime: Gateway
  rejeita `--session main` para non-default agents (erro explícito:
  *"sessionTarget 'main' is only valid for the default agent"*). Crons
  da Vita passam a usar `--session isolated --message` (payload kind
  `agentTurn`) — mesmo padrão dos crons do Faber. Continuidade da Vita
  entre o tick e o uso vivo vem do **disco** (output/diarias.txt,
  ledger), não do histórico da main. Heartbeat continua aquecendo a
  main pra delegações via `sessions_send` do Janus.
- **v2.11.0** — Camada 1 reescrita: main session + heartbeat nativo
  substitui sessão isolada diária via cron. (Parcialmente revertido
  em v2.11.1 apenas pra parte de cron — restante do design continua.)
- **v2.10.0** — Camada 4 (Plugin SDK no Janus) implementada.
- **v2.9.0** — Proposta inicial.

---

## Problema

No modelo atual, toda interação com a Vita gera um `sessions_spawn`
isolado pelo Janus. Cada spawn paga o custo completo de bootstrap
(AGENTS.md, workspace, contexto) independente da complexidade da
operação.

**Dados reais (semana de 07-13/04/2026):**
- 49 sessões na semana
- ~13k tokens por sessão (bootstrap + execução + resposta)
- 675k tokens/semana total
- Dia pico (10/04): 27 sessões, 346k tokens
- Projeção mensal em operação plena: ~10.5M tokens

O bootstrap fixo de ~3-4k tokens se repete a cada spawn. Em 27
sessões no dia pico, são ~90-100k tokens gastos apenas em bootstrap
repetido.

## Solução: 4 camadas complementares

### Camada 1 — Main session permanente + heartbeat nativo

A Vita vive **na própria main session**, mantida aquecida pelo
heartbeat nativo do OpenClaw (feature `agents.list[].heartbeat`).
Janus delega via `sessions_send` diretamente pra essa main, sem
nunca fazer `spawn`.

Crons (daily/weekly tick) disparam **turnos isolados** na Vita
(`--session isolated --message`) — não injetam na main. O Gateway
restringe `--session main` ao agente default (Janus); non-default
agents (Vita, Faber) só podem receber cron via isolated + agentTurn.
Continuidade entre o tick e o uso vivo da Vita vem do disco:
`output/diarias.txt` e o ledger JSONL são fonte canônica, lidos pela
main quando precisa.

**Por que main e não sessão isolada diária:**

A proposta original (v2.9.0) usava cron diário criando sessão
isolada. Na implementação descobrimos três problemas:

1. **Daily reset do Gateway às 04:00** — o Gateway tem política
   `session.reset.mode: "daily"` por padrão. Sessões nomeadas,
   isoladas ou quaisquer outras são resetadas às 04:00 no fuso do
   host. Nenhuma estratégia de nomenclatura escapa disso.

2. **Sessão isolada perde o benefício do cache** — cada spawn
   paga `cache_write` do bootstrap. Com main aquecida por heartbeat,
   todas as interações pagam `cache_read` (~10% do custo).

3. **Cron externo competindo com heartbeat** — shell cron
   disparando `openclaw run --session isolated` é exatamente o que
   o heartbeat nativo substitui com mais eficiência. Nota: o cron
   interno da Vita **também** roda em isolated (restrição do
   Gateway para non-default agents), mas como passa pelo scheduler
   nativo participa do mesmo ciclo de execução e respeita a política
   de sessão configurada — diferente do shell cron que era cego ao
   Gateway.

**Solução em 3 configs:**

```json5
// 1. Desabilitar reset diário, usar reset por ociosidade
{
  "session": {
    "reset": {
      "mode": "idle",
      "idleMinutes": 2880  // 48h — só morre se sem atividade mesmo
    }
  }
}
```

```json5
// 2. Heartbeat SÓ na Vita (outros agentes não pagam overhead)
{
  "agents": {
    "list": [{
      "id": "vita",
      "heartbeat": {
        "every": "55m",              // abaixo do TTL de 1h do cache
        "session": "main",            // aquece a sessão de delegação
        "isolatedSession": false,     // preserva contexto entre turnos
        "target": "none",             // não envia msg pra canal
        "activeHours": {
          "start": "06:00",
          "end": "23:00",
          "timezone": "America/Maceio"
        },
        "timeoutSeconds": 45
      }
    }]
  }
}
```

```bash
# 3. Crons via scheduler nativo do OpenClaw
#    (non-default agents como Vita exigem --session isolated --message)
openclaw cron add --name "Vita morning" --cron "0 6 * * *" \
  --tz "America/Maceio" --agent "vita" --session isolated \
  --message "Execute o Morning Pipeline agora..."

openclaw cron add --name "Vita weekly" --cron "0 20 * * 0" \
  --tz "America/Maceio" --agent "vita" --session isolated \
  --message "Execute o Weekly Reflection agora..."
```

**Ciclo de vida:**

```
06:00  Cron interno dispara TURNO ISOLADO da Vita (agentTurn)
       Vita roda daily-tick no turno, escreve output/diarias.txt + ledger
       Turno termina — sessão isolada é descartada
       Main session da Vita segue aquecida em paralelo via heartbeat

06:55  Heartbeat na main (55m) — turno interno leve, mantém cache
07:50  Heartbeat — idem
...

09:15  Mensagem real: usuário → Janus → classifica:
       CRUD simples → vita_quick_crud (plugin, 0 tokens, não toca main)
       Complexo    → sessions_send → main da Vita
                     Main LÊ output/diarias.txt como faz em qualquer
                     interação → "sabe" o que o tick produziu de manhã
                     Entrada na main quente = cache_read (~10%)

...

20:00  Cron semanal (só domingos) — turno isolado, weekly-tick
       Resultado (execution-history, recurrence-candidates) vai pra disco

22:55  Último heartbeat antes de 23:00
23:00  Heartbeat desliga via activeHours
       Main fica dormente, mas viva (idleMinutes: 2880 = 48h)

Dia seguinte 06:00  Cron isolado de novo; heartbeat volta após activeHours
                    Main continua a mesma — contexto do dia anterior
                    ainda acessível se necessário
```

**Por que o tick em isolated não é um problema:**

O output do tick é **sempre arquivo** (`diarias.txt`, `ledger.jsonl`,
`historico-execucao.md`). A Vita nunca consultou o histórico da sessão
pra saber "o que o daily-tick fez" — sempre leu `diarias.txt`. Então a
perda de continuidade conversacional entre o turno do cron e a main é
inexistente: a fonte de verdade é o disco, não a conversa.

**Por que usuário não perde contexto:**

- `idleMinutes: 2880` (48h) > 7h de janela noturna → sessão não
  morre durante a noite
- Main session é append-only em `~/.openclaw/agents/vita/sessions/`
  → estado persiste mesmo em restart do Gateway
- Compactação (Camada 3) + memoryFlush garantem que dias muito
  carregados não percam task_ids críticos

**Fallback no Janus (Camada 4):**

O plugin `vita-router` (Camada 4) trata o caso de main indisponível:
se `sessions_send` falhar, tenta novamente uma vez; se persistir,
escala pro usuário com mensagem explícita. Spawn efêmero foi
**removido do design** — era um fallback que mascarava problemas
reais de infra sem resolver.

### Camada 2 — Session pruning (cache-ttl)

Cada comando CLI da Vita retorna JSON que ocupa ~500-2k tokens.
Esses resultados são úteis por segundos (para formular a resposta)
e depois viram peso morto no contexto. Pruning remove tool results
antigos automaticamente.

```json5
// Config da Vita
{
  "agents": {
    "defaults": {
      "contextPruning": {
        "mode": "cache-ttl",
        "ttl": "2m"
      }
    }
  }
}
```

**Efeito:**
- Tool results expiram em 2 min
- Contexto cresce apenas pelo texto da conversa (~200 tokens por turno)
- 27 interações × ~200 tokens = ~5.4k tokens de conversa acumulada
- Compactação raramente (ou nunca) é necessária num dia normal
- Se compactação nunca roda, os riscos de perda lossy não existem

**Pruning vs compactação:**

| | Pruning | Compactação |
|---|---|---|
| O que remove | Tool results (JSON de CLI) | Conversa antiga inteira |
| Quando | A cada chamada ao modelo | Quando contexto excede limiar |
| Reversível? | Não afeta transcript | Irreversível |
| Conversa | Intacta | Sumarizada (lossy) |

Pruning é a primeira linha de defesa. Se funcionar bem, compactação
não chega a acontecer.

### Camada 3 — Memory flush (backup pré-compactação)

Se apesar do pruning a compactação for necessária (dia atípico com
muitas interações longas), o memory flush salva estado crítico em
disco antes de compactar.

```json5
// Config da Vita
{
  "agents": {
    "defaults": {
      "compaction": {
        "memoryFlush": {
          "enabled": true,
          "softThresholdTokens": 4000,
          "systemPrompt": "Antes de compactar, salve em memory/YYYY-MM-DD.md: (1) tasks completadas hoje com task_ids, (2) tasks em progresso com task_ids e último status, (3) alertas pendentes, (4) contexto relevante das interações do dia. Use formato JSONL ou markdown estruturado. Priorize task_ids — são irrecuperáveis sem consulta ao ledger."
        }
      }
    }
  }
}
```

**O que o memory file preserva:**

```markdown
# memory/2026-04-13.md

## Tasks completadas
- 20260413_meditacao — completada 08:30
- 20260413_emails — completada 09:45

## Tasks em progresso
- 20260413_relatorio_cliente — prioridade 🔴, sem progresso reportado

## Alertas pendentes
- 20260412_dentista — vencida ontem, postpone_count: 2

## Contexto
- Usuário mudou prioridade do relatório de 🟡 para 🔴 às 09:30
- Usuário mencionou que está sobrecarregado às 14:00
```

Após compactação, a Vita pode ler `memory/2026-04-13.md` para
recuperar o que o resumo compactado perdeu.

**Limitações:**
- O agente decide o que salvar — pode omitir algo relevante
- Depende de workspace com permissão de escrita
- Ninguém garante que a Vita lê o memory file após compactação
  (reforçar no AGENTS.md)

### Camada 4 — Plugin SDK no Janus

Usando o Plugin SDK do OpenClaw
(https://docs.openclaw.ai/plugins/architecture), o Janus
intercepta operações determinísticas via hooks de runtime
(`message:received`, `before_tool_call`) e executa o CLI da Vita
diretamente em TypeScript — sem envolver LLM, zero tokens. Isso
elimina ~70% dos `sessions_send`.

**Operações que o plugin resolve (0 tokens):**

| Intenção | Comando |
|---|---|
| "terminei X" | `cli ledger-complete --description "X" ...` |
| "adiciona task Y" | `cli ledger-add --description "Y" ...` |
| "cancela Z" | `cli ledger-cancel --description "Z" ...` |
| "comecei W" | `cli ledger-start --description "W" ...` |
| "progresso: 5 de 10" | `cli ledger-progress --task-id ID --done 5 --total 10 ...` |

**Operações que vão pra Vita via `sessions_send`:**

| Intenção | Por que precisa de LLM |
|---|---|
| "o que fazer hoje?" | Interpretar suggest-daily + contexto |
| "tô sobrecarregado" | Raciocinar sobre prioridades |
| "como foi minha semana?" | Analisar weekly-tick + formular reflexão |
| Feedback do dia | Gerar panorama, foco, alerta, ação sugerida |
| Recurrence suggestions | Apresentar candidatos com raciocínio |

**Arquitetura do plugin (Plugin SDK do OpenClaw):**

```typescript
// Plugin SDK hook no Janus — TypeScript puro, 0 tokens

interface VitaIntent {
  type: "complete" | "add" | "cancel" | "start" | "progress" | "complex";
  params: Record<string, string>;
}

function classifyIntent(task: string): VitaIntent {
  // Classificação baseada em padrões de texto
  // NÃO usa LLM — regex ou keyword matching
  // Em caso de dúvida, retorna type: "complex"
}

async function routeToVita(task: string) {
  const intent = classifyIntent(task);

  if (intent.type !== "complex") {
    // CRUD direto — executa CLI sem LLM
    const cmd = buildCliCommand(intent);
    const result = execSync(cmd);
    const parsed = JSON.parse(result);

    // Duplicate guardrail: se warning, escala pra sessão Vita
    if (parsed.warning?.type === "duplicate_suspect") {
      return sendToVitaSession(task);  // LLM decide
    }

    return formatResponse(parsed);
  }

  // Complexo — sessions_send pra Vita
  return sendToVitaSession(task);
}
```

**Nota sobre separação de domínios:**

O plugin do Janus executa CLI da Vita diretamente para operações
CRUD atômicas. Isso tecnicamente cruza a fronteira de domínio —
o Janus opera ferramentas da Vita sem delegar.

Justificativa: operações CRUD são determinísticas, idempotentes e
verificáveis pelo JSON de retorno. O plugin não toma decisões —
traduz intenção em comando e reporta resultado. O Duplicate
Guardrail (standing order) é respeitado: warnings sempre escalam
pra sessão Vita com LLM.

Operações que envolvem julgamento (priorização, feedback, reflexão
semanal) continuam sendo delegadas via `sessions_send`.

## Projeção de custo

Baseado nos dados reais de 07-13/04/2026 (49 sessões, 675k tokens/semana).

### Dia pico (27 interações)

| Cenário | Tokens | Redução |
|---|---|---|
| Atual (27 spawns × 13k) | 346k | — |
| Camada 1 (sessão diária + sends) | ~91k | -74% |
| + Camada 2 (pruning) | ~78k | -77% |
| + Camada 4 (plugin CRUD) | ~37k | -89% |

### Semana (base real)

| Cenário | Tokens/semana | Tokens/mês | Redução |
|---|---|---|---|
| **Atual** | **675k** | **~2.7M** | — |
| Camada 1 + 2 | ~280k | ~1.1M | -60% |
| Camada 1 + 2 + 4 | ~130k | ~520k | -81% |

### Decomposição do ganho por camada

| Camada | O que elimina | Redução |
|---|---|---|
| 1. Sessão diária | Bootstrap repetido (~3-4k × N spawns) | ~60% |
| 2. Pruning | Tool results acumulados no contexto | ~15% adicional |
| 3. Memory flush | Não reduz tokens — é segurança | 0% (mitigação) |
| 4. Plugin SDK | 70% dos sends (operações determinísticas) | ~20% adicional |

## Riscos e mitigações

### Risco 1: Main session expira ou Gateway reinicia

**Causa:** Restart do Gateway, host host reinicia, falha de rede
prolongada. `idleMinutes: 2880` garante que não expira por ociosidade
dentro de qualquer janela realista.

**Mitigação:** Session store vive em disco (`~/.openclaw/agents/vita/
sessions/`), então restart do Gateway recarrega a mesma main com
histórico intacto. No pior caso (arquivo corrompido), próximo
heartbeat às 06:00 cria main nova; usuário perde contexto de dias
anteriores mas não perde nada do ledger (fonte de verdade).

### Risco 2: Compactação perde task_ids

**Causa:** Dia atípico com muitas interações longas ultrapassa o
limiar de compactação mesmo com pruning.

**Mitigação:**
- Pruning agressivo (ttl: 2m) impede acúmulo → compactação rara
- Memory flush salva task_ids em disco antes de compactar
- Execute-Verify-Report: Vita consulta ledger em vez de confiar
  na memória para operações

### Risco 3: Divergência memória vs ledger

**Causa:** Algo muda no ledger fora da sessão da Vita (edição
manual, pipeline disparado por outro trigger).

**Mitigação:** Princípio Execute-Verify-Report no AGENTS.md:
após qualquer operação, verificar o resultado no JSON de retorno.
Para queries sobre estado ("quantas tasks tenho?"), sempre
consultar o ledger via CLI em vez de responder de memória.

Reforço no AGENTS.md:

```
REGRA: A memória da sessão é auxiliar para contexto conversacional.
O ledger JSONL é a fonte de verdade para estado de tasks. Em caso
de dúvida ou após compactação, SEMPRE consultar o ledger antes de
responder sobre estado de tasks.
```

### Risco 4: Plugin classifica intenção errada

**Causa:** Regex/keyword matching interpreta mal a mensagem do
usuário. Ex: "terminei de pensar sobre cancelar o dentista"
→ plugin entende como "complete" ou "cancel".

**Mitigação:**
- Em caso de ambiguidade, `classifyIntent` retorna `"complex"`
  e delega pra Vita via `sessions_send`
- Plugin só atua em intenções de alta confiança
- Duplicate Guardrail sempre escala warnings pra LLM
- Usuário pode corrigir: "não, eu quis dizer X" → Janus re-roteia

### Risco 5: Plugin no Janus cruza fronteira de domínio

**Causa:** Janus executa CLI da Vita diretamente para CRUD.

**Mitigação:**
- Restrito a operações atômicas e determinísticas
- Standing orders (Duplicate Guardrail) são respeitados
- Operações com julgamento (feedback, priorização, reflexão)
  nunca passam pelo plugin — sempre `sessions_send`
- JSON de retorno do CLI é verificado antes de entregar ao usuário

## Configuração completa

### openclaw.json — Janus (sem mudanças no subagents)

```json5
{
  "subagents": {
    "maxConcurrent": 8,
    "archiveAfterMinutes": 30,
    "runTimeoutSeconds": 300
  }
}
```

### Config global (top-level) e da Vita

```json5
{
  // Top-level: desativa reset diário às 04:00 do Gateway
  "session": {
    "reset": {
      "mode": "idle",
      "idleMinutes": 2880
    }
  },
  "agents": {
    "defaults": {
      "contextPruning": {
        "mode": "cache-ttl",
        "ttl": "2m"
      },
      "compaction": {
        "memoryFlush": {
          "enabled": true,
          "softThresholdTokens": 4000,
          "systemPrompt": "Antes de compactar, salve em memory/YYYY-MM-DD.md: (1) tasks completadas hoje com task_ids, (2) tasks em progresso com task_ids e último status, (3) alertas pendentes, (4) contexto relevante das interações do dia. Use formato estruturado. Priorize task_ids."
        }
      }
    },
    "list": [
      {
        "id": "vita",
        // ... outros campos (model, tools, prompt) ...
        "heartbeat": {
          "every": "55m",
          "session": "main",
          "isolatedSession": false,
          "target": "none",
          "activeHours": {
            "start": "06:00",
            "end": "23:00",
            "timezone": "America/Maceio"
          },
          "timeoutSeconds": 45
        }
      }
    ]
  }
}
```

### Cron interno do OpenClaw (turno isolado, agentTurn)

> **Restrição do Gateway:** non-default agents (Vita, Faber, …) só
> aceitam cron via `--session isolated --message` (payload kind
> `agentTurn`). `--session main` é reservado ao agente default (Janus).
> O mesmo padrão já é usado pelos crons do Faber em produção.

```bash
# Daily tick — turno isolado na Vita às 06:00
openclaw cron add \
  --name "Vita morning" \
  --cron "0 6 * * *" \
  --tz "America/Maceio" \
  --agent "vita" \
  --session isolated \
  --message "Execute o Morning Pipeline agora usando a data de hoje. Rode daily-tick do CLI, verifique o resultado e entregue diarias.txt ao usuário com sumário breve."

# Weekly tick — domingo 20:00
openclaw cron add \
  --name "Vita weekly" \
  --cron "0 20 * * 0" \
  --tz "America/Maceio" \
  --agent "vita" \
  --session isolated \
  --message "Execute o Weekly Reflection agora. Apresente taxa de conclusão e candidatos de recorrência. NÃO ative regras sem aprovação."
```

## Implementação por fases

### Fase 1 — Sessão diária + pruning (imediata, config only)

- Configurar cron `Vita morning` como descrito
- Ativar `contextPruning` com `ttl: 2m`
- Ativar `memoryFlush`
- Ajustar routing no Janus para `sessions_send` quando sessão existe
- **Ganho esperado: ~60-77% redução de tokens**
- **Esforço: configuração, sem código novo**

### Fase 2 — Plugin SDK no Janus (médio prazo)

- Implementar plugin usando o Plugin SDK do OpenClaw
  (https://docs.openclaw.ai/plugins/architecture)
- Hook `message:received` para classificar intenções CRUD
- `classifyIntent` via regex/keyword matching (sem LLM)
- Mapear intenções CRUD para comandos CLI da Vita
- `cli check-alerts` já implementado (v2.10.0) — pronto para uso pelo plugin
- Respeitar Duplicate Guardrail (warnings escalam pra LLM)
- **Ganho esperado: ~15-20% redução adicional**
- **Esforço: plugin TypeScript (Plugin SDK) no Janus**

### Fase 3 — Ajuste fino (após 2 semanas de operação)

- Analisar logs: quantas vezes a sessão expirou? Quantas compactações?
- Ajustar `idleMinutes` e `ttl` baseado em dados reais
- Avaliar eficácia do `check-alerts` no plugin (já implementado, medir uso real)
- Revisar `classifyIntent` para reduzir falsos positivos/negativos

## Relação com Standing Orders

Os programas documentados em `patches/vita-AGENTS.md` continuam
válidos e são complementares:

| Programa | Relação com esta proposta |
|---|---|
| Morning Pipeline | Executado pelo cron `Vita morning`. Sessão isolada diária é o veículo de execução. |
| Weekly Reflection | Executado pelo cron `Vita weekly`. Sessão isolada separada (não reutiliza a diária). |
| Duplicate Guardrail | Respeitado pelo plugin CRUD: warnings de `ledger-add` sempre escalam pra sessão Vita com LLM. |

## Dependências da Vita (código novo necessário)

A proposta é primariamente de configuração e infraestrutura.
O único código novo na Vita é:

**`cli check-alerts`** (Fase 2) — comando que retorna JSON com:
- Tasks com `due_date` = hoje
- Tasks com `due_date` < hoje (vencidas)
- Tasks em `[~]` há mais de 48h sem progresso
- Tasks com `postpone_count >= 3`

Este comando seria usado pelo plugin do Janus para enriquecer o
contexto de spawns/sends sem gastar tokens de LLM na detecção.

## O que esta proposta NÃO cobre

- Implementação do plugin no Janus via Plugin SDK
  (responsabilidade do Janus — a Vita só fornece os comandos CLI)
- Configuração de canais de entrega (Telegram, Discord, etc.)
- Mudanças no AGENTS.md vivo do Domus (aplicação do patch)
- Monitoramento event-driven profundo via `before_tool_call` do
  Plugin SDK (a camada 4 usa hooks mais simples como
  `message:received`; interceptação granular de tool calls é
  possível mas adiciona complexidade sem ganho proporcional)
