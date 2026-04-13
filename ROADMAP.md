# Roadmap — Vita Task Manager

Documento de implementações futuras organizado por versão.

---

## ✅ v2.2 — Scoring e 1-3-5 (IMPLEMENTADO)

**Objetivo:** Implementar algoritmo de priorização inteligente baseado no método 1-3-5.

### 2.2.1 Campos de Scoring

| Aspecto | Descrição | Dependências | Complexidade | Benefício TDAH |
|---------|-----------|--------------|--------------|----------------|
| Campos de complexidade | `complexity` (1-10), `complexity_source`, `confidence` | Migração de dados existentes | Média | Evita escolher tarefas grandes demais sem perceber |
| Campos de idade | `first_added_date`, `postpone_count`, `last_postponed_at` | Ledger ops update | Baixa | Tarefas "fantasma" não são esquecidas |
| Campos de energia | `energy_required`, `energy_predicted` | Inferência por IA ou palavras-chave | Média | Match entre energia disponível e tarefa |

### 2.2.2 Fórmula de Score

| Aspecto | Descrição | Dependências | Complexidade | Benefício TDAH |
|---------|-----------|--------------|--------------|----------------|
| Cálculo de urgência | Baseado em `due_date` (escala 0-100) | v2.2.1 | Baixa | Prazos curtos sobem na fila |
| Cálculo de complexidade | Invertida: complexa = menor score | v2.2.1 | Baixa | Quick wins aparecem primeiro |
| Cálculo de idade | Dias na lista (escala 0-100) | v2.2.1 | Baixa | Tarefas antigas não somem |
| Penalidade de adiamento | Exponencial por `postpone_count` | v2.2.1 | Baixa | Combate procrastinação crônica |
| Score final | Média ponderada: U(35%) + C(25%) + A(20%) - P(20%) | Todos acima | Média | Decisão objetiva, não emocional |

### 2.2.3 Algoritmo 1-3-5

| Aspecto | Descrição | Dependências | Complexidade | Benefício TDAH |
|---------|-----------|--------------|--------------|----------------|
| Categorização por tamanho | Big (7-10), Medium (4-6), Small (1-3) | v2.2.2 | Baixa | Limita escolhas do dia |
| Distribuição 1-3-5 | 1 big, 3 medium, 5 small por dia | v2.2.2 | Média | Evita sobrecarga de decisão |
| Promoção/demote automático | Preenche slots vazios com próximas melhores | v2.2.2 | Média | Sempre tem 9 tarefas sugeridas |
| Resolução de conflitos | Detecta urgente+complexa, muitas adiadas | v2.2.2 | Média | Alerta sobre padrões problemáticos |

### 2.2.4 Inferência de Complexidade

| Aspecto | Descrição | Dependências | Complexidade | Benefício TDAH |
|---------|-----------|--------------|--------------|----------------|
| Prompt de IA | Sistema prompt para avaliar complexidade | LLM disponível | Média | Classificação consistente |
| Fallback por palavras-chave | Regex para casos sem IA | v2.2.1 | Baixa | Funciona offline |
| Cache de inferências | Evita reprocessar mesmas tasks | v2.2.1 | Baixa | Performance |

### 2.2.5 CLI e Output

| Aspecto | Descrição | Dependências | Complexidade | Benefício TDAH |
|---------|-----------|--------------|--------------|----------------|
| Comando `suggest-135` | Retorna JSON com sugestões do dia | v2.2.3 | Média | Interface clara |
| Render com seção 1-3-5 | Visual separado por categoria | v2.2.3 | Baixa | Foco visual organizado |
| Explicação do score | Campo `why` em cada sugestão | v2.2.2 | Baixa | Transparência reduz ansiedade |

---

## ✅ v2.3 — WIP Limit e Feedback Visual (IMPLEMENTADO)

**Objetivo:** Evitar multitarefa e melhorar feedback para TDAH.

### 2.3.1 WIP Limit

| Aspecto | Descrição | Dependências | Complexidade | Benefício TDAH |
|---------|-----------|--------------|--------------|----------------|
| Configuração de limites | `wip_limit` (default: 2) | Config system | Baixa | Evita iniciar muitas coisas |
| Bloqueio de início | Alerta se tentar iniciar > limit | v2.3.1 | Baixa | Força terminar antes de nova |
| Fila de "próximas" | Tasks esperando para iniciar | v2.3.1 | Média | Visibilidade do que vem depois |

### 2.3.2 Estados Visuais

| Aspecto | Descrição | Dependências | Complexidade | Benefício TDAH |
|---------|-----------|--------------|--------------|----------------|
| Emojis de estado | 🆕 ⏳ ✅ ❌ para status | Render update | Baixa | Reconhecimento rápido |
| Barra de progresso | Visual para % completo | Render update | Baixa | Feedback de progresso |
| Cor por idade | Tons de vermelho para tasks antigas | Render update | Baixa | Alerta visual de "fantasmas" |

### 2.3.3 Feedback Contextual

| Aspecto | Descrição | Dependências | Complexidade | Benefício TDAH |
|---------|-----------|--------------|--------------|----------------|
| Triggers estendidos | Além de morning/crud/time: wip_exceeded, stale_task | Feedback logic | Média | Feedback no momento certo |
| Mensagens TDAH-específicas | "Você tem 3 tarefas em progresso — termine uma primeiro" | Copywriting | Baixa | Linguagem empática |
| Celebração de vitórias | Feedback positivo ao completar | Feedback logic | Baixa | Reforço positivo |

---

## v3.0 — Integrações

**Objetivo:** Conectar com ferramentas externas e expandir funcionalidades.

### 3.0.1 Timer Integrado

| Aspecto | Descrição | Dependências | Complexidade | Benefício TDAH |
|---------|-----------|--------------|--------------|----------------|
| Pomodoro flexível | 10/3, 15/5, 20/5, 25/5 | Timer backend | Média | Adapta ao ciclo de foco |
| Comando `start-timer` | Inicia timer vinculado a task | v3.0.1 | Média | Foco em uma coisa |
| Auto-log no ledger | Registra início/fim de sessões | v3.0.1 | Média | Histórico de produtividade |
| Alerta de pausa | Notifica quando descansar | v3.0.1 | Média | Evita burnout |

### 3.0.2 Body Doubling

| Aspecto | Descrição | Dependências | Complexidade | Benefício TDAH |
|---------|-----------|--------------|--------------|----------------|
| Modo foco compartilhado | Sessão síncrona com outra pessoa | Integração externa | Alta | Accountability externa |
| Notificação de início/fim | Alerta parceiro de body doubling | v3.0.2 | Média | Compromisso social |
| Log de sessões | Registra participação | v3.0.2 | Baixa | Rastreabilidade |

### 3.0.3 Notificações

| Aspecto | Descrição | Dependências | Complexidade | Benefício TDAH |
|---------|-----------|--------------|--------------|----------------|
| Lembrete de próxima ação | Alerta quando tarefa próxima do prazo | Scheduler | Média | Não esquece deadlines |
| Lembrete de brain dump | "Esvazie a cabeça" períodico | Scheduler | Média | Prevenção de sobrecarga |
| Lembrete de review | Fim de dia: o que foi feito? | Scheduler | Média | Fechamento mental |

### 3.0.4 Export/Import

| Aspecto | Descrição | Dependências | Complexidade | Benefício TDAH |
|---------|-----------|--------------|--------------|----------------|
| Export CSV | Para análise externa | Formatter | Baixa | Dados portáteis |
| Export JSON completo | Backup portátil | Ledger | Baixa | Portabilidade |
| Import de outras ferramentas | Todoist, Notion, etc | Parsers | Alta | Migração fácil |

---

## Backlog — Ideias Sem Prioridade

Ideias interessantes mas sem data definida.

| Ideia | Descrição | Complexidade | Benefício TDAH |
|-------|-----------|--------------|----------------|
| **Gamificação** | Streaks, pontos, níveis por conclusão | Média | Motivação extrínseca |
| **Análise de padrões** | "Você costuma adiar tarefas de X tipo" | Alta | Autoconhecimento |
| **Sugestão de divisão** | IA sugere como quebrar tarefa grande | Alta | Reduz paralisia |
| **Modo hiperfoco** | Bloqueia novas tasks, foco em uma só | Baixa | Aproveita o momento |
| **Integração calendário** | Ler/escrever em Google/Outlook Calendar | Alta | Visão unificada |
| **Tags inteligentes** | Auto-tag por contexto (casa, trabalho, rua) | Média | Organização automática |
| **Modo baixa energia** | Só mostra tasks de complexidade 1-3 | Baixa | Dias difíceis |
| **Sincronização multi-device** | Ledger na nuvem | Alta | Acesso de qualquer lugar |
| **Comandos por voz** | "Adicionar task comprar leite" | Média | Captura rápida |
| **Relatório mensal** | Análise de produtividade | Média | Visão de longo prazo |

---

## Critérios de Priorização

Para decidir o que entra em cada versão:

1. **Impacto TDAH** — Quanto ajuda no dia a dia?
2. **Complexidade** — Quanto esforço para implementar?
3. **Dependências** — O que precisa estar pronto antes?
4. **Custo cognitivo** — Adiciona complexidade de uso?

**Princípio:** Preferir features que *reduzem* decisões do usuário, não aumentam.

---

## Notas de Implementação

- **v2.2** depende da especificação completa em `vita-scoring-system-spec.md`
- **v2.3** pode ser paralelizado parcialmente com v2.2
- **v3.0** requer decisões arquiteturais sobre integrações externas
- **Backlog** deve ser revisado a cada minor release

---

**Atualizado:** 2026-04-08  
**Versão do Documento:** 1.0
