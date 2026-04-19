# Vita Task Manager

Sistema de gerenciamento de tarefas pessoais com **ledger JSONL** como fonte de verdade, otimizado para TDAH.

**Versão:** 2.15.0  
**Localização:** `/home/node/.openclaw/workspace/vita/skills/vita-task-manager/`

---

## Arquitetura

### Visão Geral

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   rotina.md     │     │  agenda-semana  │     │  tasks manuais  │
│  (rotina diária)│     │   (lembretes)   │     │   (ad-hoc)      │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────────┐
                    │   LEDGER JSONL      │◄──── Fonte de verdade
                    │  (append-only)      │      append-only
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────┐    ┌──────────────┐
        │  Render  │    │ Feedback │    │   Weekly     │
        │ diarias  │    │  Vita    │    │   Summary    │
        │  .txt    │    │          │    │              │
        └──────────┘    └──────────┘    └──────────────┘
```

### Ledger JSONL

O ledger é um arquivo append-only onde cada linha é um evento JSON:

```jsonl
{"type":"task","_operation":"create","id":"20260408_tomar_remedios",...}
{"type":"task","_operation":"complete","id":"20260408_tomar_remedios",...}
{"type":"feedback","timestamp":"2026-04-08T09:00:00Z",...}
{"type":"brain_dump","id":"20260408_dump_001",...}
```

**Princípios:**
- **Imutabilidade:** Nunca editamos, apenas adicionamos eventos
- **Auditabilidade:** Histórico completo de todas as mudanças
- **Recuperação:** Estado atual = fold de todos os eventos

### Pipeline Diário

```bash
python3 scripts/cli.py pipeline \
  --today DD/MM --year YYYY \
  --rotina PATH \
  --agenda-semana PATH \
  --data-dir PATH \
  --output PATH
```

**Fluxo:**
1. **Rollover** — carrega tarefas pendentes da semana anterior (roda no primeiro dia da semana nova)
2. **Sync Fixed** — adiciona itens da rotina diária
3. **Merge** — combina com tasks manuais existentes
4. **Render** — gera `diarias.txt` limpo em formato WhatsApp (apenas leitura)
5. **Feedback Check** — determina se Vita deve dar feedback

---

## Formatos de Saída

O sistema gera dois formatos de saída:

| Arquivo | Formato | Uso |
|---------|---------|-----|
| `diarias.txt` | WhatsApp | Padrão do pipeline — layout otimizado para leitura em mobile |
| `diarias.md` | Markdown | Formato alternativo opcional, invocado via `--format markdown` no comando `render` |

**Implementação:** Os dois formatos são gerados por formatters independentes (`formatter_whatsapp.py` e `formatter.py`). O `.txt` **não** é derivado do `.md`; é gerado diretamente pelo `formatter_whatsapp` a partir do `TaskFile`.

---

## Comandos Disponíveis (CLI)

### Fluxo Principal

| Comando | Descrição |
|---------|-----------|
| `pipeline` | Executa o fluxo diário completo |
| `render` | Gera saída limpa sem alterar ledger |
| `weekly-summary` | Resumo da semana atual |

### CRUD de Tarefas

| Comando | Descrição |
|---------|-----------|
| `ledger-add` | Adiciona nova task ao ledger (com detecção de duplicatas) |
| `ledger-update` | Atualiza campos de task existente (descrição, contexto, prioridade, prazo) |
| `ledger-start` | Inicia uma tarefa (muda status para in_progress) |
| `ledger-progress` | Atualiza progresso (0-100%) |
| `ledger-complete` | Marca como concluída |
| `ledger-cancel` | Cancela com motivo |
| `ledger-status` | Diagnóstico do estado do ledger (saúde, rollover, issues) |
| `score-task` | Calcula score de prioridade para uma tarefa |
| `explain-task` | Explica o score de uma tarefa |
| `suggest-daily` | Sugere tarefas do dia (método 1-3-5) |
| `check-wip` | Verifica limite de WIP (tarefas em progresso) |

### Brain Dump (TDAH)

| Comando | Descrição |
|---------|-----------|
| `brain-dump` | Captura rápida de sobrecarga mental |
| `dump-to-task` | Promove item do dump para task formal |

### Sincronização

| Comando | Descrição |
|---------|-----------|
| `sync-fixed` | Sincroniza rotina diária |
| `store-feedback` | Salva feedback da Vita no ledger |
| `execution-history` | Relatório de padrões de execução + word weights |
| `rollover` | Rollover semanal manual |

### Recorrência

| Comando | Descrição |
|---------|-----------|
| `recurrence-detect` | Detecta padrões de recorrência no histórico |
| `recurrence-activate` | Ativa regra de recorrência (diária ou semanal) |
| `recurrence-deactivate` | Desativa regra existente (append-only) |
| `recurrence-list` | Lista regras ativas |

### Alertas

| Comando | Descrição |
|---------|-----------|
| `check-alerts` | Inspeciona ledger e retorna alertas acionáveis (due_today, overdue, stalled, blocked) |

### Heartbeat proativo (push)

| Comando | Descrição |
|---------|-----------|
| `heartbeat-tick` | Filtra alertas críticos, aplica cooldown, persiste nudges e retorna `emit_text` pronto pra `sessions_send` |
| `nudges-pending` | Lista nudges ainda não confirmados (fallback quando `sessions_send` falhar) |
| `nudges-ack` | Marca nudge como confirmado pelo usuário |

### Automação

| Comando | Descrição |
|---------|-----------|
| `daily-tick` | Pipeline + execution-history em uma invocação (idempotente) |
| `weekly-tick` | Execution-history + recurrence-detect + ledger-status em uma invocação |

---

## Fluxo de Trabalho Diário

### Manhã (início do dia)

```bash
# 1. Executar pipeline
python3 scripts/cli.py pipeline \
  --today 08/04 --year 2026 \
  --rotina ~/rotina.md \
  --agenda-semana ~/agenda_da_semana.md \
  --data-dir ./data \
  --output ./diarias.txt
```

**Retorno JSON inclui:**
```json
{
  "feedback_status": "required",  // required | offer | skip
  "feedback_seed": { ... },
  "tasks_count": 5,
  "rendered_to": "./diarias.txt"
}
```

### Quando `feedback_status` ≠ skip

1. Vita lê `feedback_seed` + contexto do usuário
2. Vita escreve feedback criativo (panorama, foco, alerta, acao_sugerida)
3. Vita chama `store-feedback`
4. Re-render se necessário

### Durante o Dia

```bash
# Marcar progresso
python3 scripts/cli.py ledger-progress \
  --id 20260408_tarefa_xyz \
  --progress 50 \
  --today 08/04 --year 2026 --data-dir ./data

# Completar
python3 scripts/cli.py ledger-complete \
  --id 20260408_tarefa_xyz \
  --today 08/04 --year 2026 --data-dir ./data

# Brain dump rápido (TDAH)
python3 scripts/cli.py brain-dump \
  --text "Lembrar de trocar lâmpada, ligar pro João" \
  --today 08/04 --year 2026 --data-dir ./data
```

### Promoção de Brain Dump

```bash
# Converter 1 item do dump em task formal
python3 scripts/cli.py dump-to-task \
  --dump-id 20260408_dump_001 \
  --item "Trocar lâmpada" \
  --priority 🔴 \
  --next-action "Ir na loja comprar LED 9W" \
  --today 08/04 --year 2026 --data-dir ./data
```

---

## Estrutura de Dados

### Task

```typescript
interface Task {
  // Identificação
  id: string;                    // YYYYMMDD_description_slug
  title: string;
  description?: string;
  
  // Estado
  status: "todo" | "in_progress" | "waiting" | "done" | "cancelled";
  priority?: "low" | "medium" | "high";  // 🟢 🟡 🔴
  progress: number;              // 0-100
  
  // Tempo
  due_date?: string;             // ISO 8601
  created_at: string;
  updated_at: string;
  completed_at?: string;
  
  // Categorização
  tags?: string[];
  source?: "fixed" | "manual" | "brain_dump";
  
  // TDAH (v2.1+)
  next_action?: string;          // Próxima ação física
}
```

### Brain Dump

```typescript
interface BrainDump {
  id: string;                    // YYYYMMDD_dump_NNN
  items: string[];               // Lista de itens capturados
  created_at: string;
  converted?: {                  // Se promovido para task
    item: string;
    task_id: string;
    converted_at: string;
  }[];
}
```

### Feedback

```typescript
interface Feedback {
  type: "feedback";
  timestamp: string;
  trigger: "morning" | "crud" | "time_elapsed";
  data: {
    panorama: string;            // Visão geral
    foco: string;                // Onde concentrar energia
    alerta?: string;             // O que pode dar errado
    acao_sugerida: string;       // Próximo passo concreto
  };
}
```

### Eventos do Ledger

```typescript
type LedgerEvent =
  | { type: "task"; _operation: "create"; ...Task }
  | { type: "task"; _operation: "update"; id: string; changes: Partial<Task> }
  | { type: "task"; _operation: "complete"; id: string; completed_at: string }
  | { type: "task"; _operation: "cancel"; id: string; reason?: string }
  | { type: "feedback"; ...Feedback }
  | { type: "brain_dump"; ...BrainDump }
  | { type: "brain_dump"; _operation: "convert"; dump_id: string; item: string; task_id: string };
```

---

## Para TDAH

### Brain Dump (v2.1.0)

**Problema:** Sobrecarga mental com muitas ideias/tarefas simultâneas.

**Solução:** Capture tudo rapidamente sem criar tarefas formais:

```bash
cli brain-dump --text "Trocar lâmpada, ligar pro João, comprar café"
```

No render aparece em seção separada com dica TDAH:

```
🧠 BRAIN DUMP

• Trocar lâmpada
• Ligar pro João
• Comprar café

💡 Dica: Escolha 1 pra virar próxima ação
```

**Promoção seletiva:**
```bash
cli dump-to-task --dump-id ... --item "Trocar lâmpada" --next-action "Ir na loja"
```

O item convertido some automaticamente do brain dump.

### Features Implementadas (v2.2 - v2.11)

- ✅ **Scoring automático:** Algoritmo 1-3-5 sugere quais tarefas fazer
- ✅ **Complexidade inferida:** IA avalia dificuldade (1-10)
- ✅ **WIP limit:** Limite de tarefas em progresso (1-2)
- ✅ **Detecção de duplicatas:** Similaridade ponderada por dificuldade de execução (3 fatores)
- ✅ **Ledger-update:** Atualização in-place de tasks existentes
- ✅ **Histórico de execução:** Relatório semanal de padrões + word weights
- ✅ **Rollover resiliente:** Migração de tasks em qualquer dia da semana
- ✅ **Diagnóstico:** `ledger-status` para troubleshooting
- ✅ **Heartbeat proativo (v2.11.2):** Nudges críticos via WhatsApp sem depender de pergunta do usuário

### Próximas Features (v3.0+)

- **Timer integrado:** Pomodoro flexível (10/3, 15/5, 20/5)

---

## Governança

### Regra Fundamental

**A Vita NUNCA usa `write`, `edit` ou ferramentas de escrita direta nos arquivos de tarefas.**

Toda modificação passa **exclusivamente** pela CLI. Se a CLI não tem comando para a operação, **não fazer**.

### Convenções

- **Semana:** domingo a sábado (America/Maceio, UTC-3)
- **Ledger:** `data/historico/DDMMYY_DDMMYY_bruto.jsonl`
- **IDs:** `YYYYMMDD_description_slug` com sufixo `_2`, `_3` se colidir
- **Limpeza D+1:** concluídas/canceladas de dias anteriores não aparecem no render

---

## Arquivos

```
vita-task-manager/
├── SKILL.md              # Documentação da skill
├── CHANGELOG.md          # Histórico de versões
├── README.md             # Documentação técnica
├── ROADMAP.md            # Implementações futuras
├── .gitignore            # Ignora dados pessoais e artefatos
├── examples/
│   └── rotina.md        # Exemplo de rotina (ponto de partida)
├── scripts/
│   ├── cli.py           # Interface principal
│   ├── ledger.py        # Engine JSONL
│   ├── ledger_ops.py    # CRUD
│   ├── pipeline.py      # Orquestrador
│   ├── render.py        # Geração de saída
│   ├── recurrence.py    # Detecção de padrões e regras de recorrência
│   ├── feedback_logic.py # Lógica de feedback
│   ├── execution_history.py # Padrões de execução + word weights
│   ├── rollover.py      # Transição semanal
│   ├── heartbeat.py     # Motor de nudges proativos (cooldown, emit_text)
│   └── test_core.py     # Testes automatizados
├── input/               # Arquivos pessoais do usuário (gitignore)
├── data/
│   └── historico/       # Ledgers JSONL (gitignore)
└── output/              # Render diário (gitignore)
```

### Dados do usuário

O repositório versiona apenas o código da skill e exemplos. Todos os dados pessoais e arquivos gerados ficam no `.gitignore`:

- `input/rotina.md` — rotina diária pessoal
- `input/agenda-semana.md` — compromissos pontuais da semana
- `data/historico/*.jsonl` — ledger JSONL append-only
- `data/historico-execucao.md` — métricas de execução
- `data/word_weights.json` — pesos de palavras (gerado)
- `output/diarias.txt` — render diário

Esses arquivos ficam no `.gitignore` para que updates da skill não contaminem os dados do usuário, e para que os dados do usuário não poluam o repositório da skill.

### Primeiro uso

Copie os exemplos pro lugar certo antes de rodar o pipeline:

```bash
cp examples/rotina.md input/rotina.md
# cp examples/agenda-semana.md input/agenda-semana.md  # quando disponível
```

Edite `input/rotina.md` com sua rotina real. A partir daí, os comandos do CLI vão criar e atualizar os outros arquivos automaticamente.

---

## Testes

```bash
python3 scripts/test_core.py
```

---

## Referências

- [Especificação de Scoring](vita-scoring-system-spec.md) — Algoritmo 1-3-5 para TDAH