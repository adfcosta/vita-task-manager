# Vita Session Optimization — Proposta de Design

**Status:** Proposta  
**Versão:** 2.9.0  
**Data:** 2026-04-13  
**Referências:**
- https://docs.openclaw.ai/automation/cron-jobs
- https://docs.openclaw.ai/tools/subagents
- https://docs.openclaw.ai/reference/session-management-compaction
- https://docs.openclaw.ai/concepts/session-pruning
- https://docs.openclaw.ai/automation/standing-orders
- https://docs.openclaw.ai/plugins/architecture (Plugin SDK)

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

### Camada 1 — Sessão isolada diária via cron

Em vez de múltiplos spawns efêmeros, um único cron cria uma sessão
isolada por dia. O Janus comunica via `sessions_send` ao longo do
dia, reutilizando a mesma sessão sem pagar bootstrap novamente.

```bash
openclaw cron add \
  --name "Vita morning" \
  --cron "0 6 * * *" \
  --tz "America/Maceio" \
  --agent "vita" \
  --session isolated \
  --message "Rodar daily-tick com os paths da skill. Entregar diarias.txt." \
  --announce
```

**Por que isolada e não `session:vita-daily` (nomeada)?**

Sessões nomeadas persistem contexto entre dias. Isso causa:
- Acúmulo lossy: cada compactação perde detalhes. Após 5 dias,
  o contexto é um resumo de resumo de resumo.
- Confusão temporal: Vita pode misturar o que aconteceu segunda
  com o que aconteceu quarta.
- Divergência: se algo muda no ledger fora da sessão, a Vita não
  sabe — confia na memória em vez de verificar.

Sessão isolada por dia evita todos esses problemas. Cada dia
começa limpo. A memória intra-dia é suficiente e confiável.

**Ciclo de vida:**

```
06:00  Cron cria sessão isolada → Vita nasce, roda daily-tick
       Sessão fica viva aguardando mensagens

08:30  Janus: sessions_send → mesma sessão (~1-3k tokens, sem bootstrap)
09:15  Janus: sessions_send → mesma sessão
14:00  Janus: sessions_send → mesma sessão
...

Próx. dia 06:00  Cron cria sessão nova → sessão anterior é limpa
                  via sessionRetention configurado
```

**Persistência intra-dia:**

A sessão isolada criada pelo cron segue as regras padrão de sessão
(não `archiveAfterMinutes` de subagent). Para garantir que a sessão
sobrevive o dia:

```json5
// Config da Vita (agent-level)
{
  "session": {
    "reset": {
      "idleMinutes": 720  // 12h — cobre 06:00-18:00 mesmo sem interação
    }
  }
}
```

**Fallback no Janus:**

Se `sessions_send` falhar (sessão expirou, restart do gateway),
o Janus faz spawn efêmero como fallback:

```typescript
async routeToVita(task: string) {
  if (this.vitaSessionKey) {
    const result = await sessions_send(this.vitaSessionKey, task, {
      timeoutSeconds: 30
    });
    if (result.ok) return result;
    this.vitaSessionKey = null;
  }

  // Fallback: spawn efêmero (raro — só em falha)
  const spawn = await sessions_spawn("vita", task, {
    model: "haiku"  // fora do horário = operação simples
  });
  return spawn;
}
```

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

### Risco 1: Sessão expira durante o dia

**Causa:** `idleMinutes` muito baixo, restart do gateway, falha de rede.

**Mitigação:** Fallback no Janus re-spawna automaticamente. Custo:
um bootstrap extra (~13k tokens). Raro — estimativa de 1-2x/semana.

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

### Config do agente Vita

```json5
{
  "session": {
    "reset": {
      "idleMinutes": 720
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
    }
  }
}
```

### Cron do OpenClaw

```bash
# Daily tick — cria sessão isolada da Vita às 06:00
openclaw cron add \
  --name "Vita morning" \
  --cron "0 6 * * *" \
  --tz "America/Maceio" \
  --agent "vita" \
  --session isolated \
  --message "Rodar daily-tick com os paths configurados. Entregar diarias.txt via canal configurado. Se ok: false em qualquer sub-step, escalar ao usuário." \
  --announce

# Weekly tick — domingo 20:00
openclaw cron add \
  --name "Vita weekly" \
  --cron "0 20 * * 0" \
  --tz "America/Maceio" \
  --agent "vita" \
  --session isolated \
  --message "Rodar weekly-tick. Apresentar taxa de conclusão e candidatos de recorrência. NÃO ativar regras sem aprovação do usuário." \
  --announce
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
