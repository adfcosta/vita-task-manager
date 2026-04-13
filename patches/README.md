# Patch para Integração Vita + vita-task-manager

## Versão
v2.2.0 — Scoring e Sugestão 1-3-5

## Estrutura de Diretórios (tudo dentro da skill)

```
vita/skills/vita-task-manager/
├── input/                    # Arquivos de entrada (Vita lê)
│   ├── agenda-fixa.md
│   └── agenda-semana.md
├── output/                   # Arquivos de saída (skill gera)
│   └── diarias.md
├── data/                     # Ledger JSONL (skill gerencia)
│   └── historico/
└── ...scripts e docs
```

## Arquivos de Patch (em `patches/`)

| Arquivo | Destino | Mudança Principal |
|---------|---------|-------------------|
| `vita-SOUL.md` | `vita/SOUL.md` | Seção "Sistema de Tasks (via Skill)" + paths |
| `vita-AGENTS.md` | `vita/AGENTS.md` | Fluxo de trabalho + paths da skill |
| `vita-IDENTITY.md` | `vita/IDENTITY.md` | Ferramenta principal + integração |

## Resumo das Mudanças v2.2.0

### SOUL.md
- Nova seção: Sistema de Tasks (via Skill vita-task-manager)
- Arquitetura explicada (ledger JSONL, output diarias.md)
- Comandos principais listados (incluindo `score-task`, `suggest-daily`, `explain-task`)
- Seção para TDAH: brain dump + scoring inteligente + 1-3-5
- Fórmula de score documentada
- Relationships atualizados (Faber, Prometheus)

### AGENTS.md
- Seção "Sistema de Tasks (via vita-task-manager)"
- Tabela de governança: operação → método correto vs incorreto (inclui comandos de scoring)
- Fluxo detalhado: Manhã, Durante o Dia, Revisão
- **Novo fluxo:** Sugestão 1-3-5 (quando perguntar "o que fazer hoje?")
- **Novo fluxo:** Explicar score (quando questionar prioridade)
- Regras de ouro: nunca editar arquivos diretamente
- Coordination atualizado (solicita Faber para updates)

### IDENTITY.md
- Campo "Ferramenta Principal" adicionado
- Descrição da skill vita-task-manager
- Regra de integração: Vita orquestra, skill executa

## Instruções de Aplicação (para Faber)

### 1. Criar estrutura de diretórios
```bash
mkdir -p /home/node/.openclaw/workspace/vita/skills/vita-task-manager/input
mkdir -p /home/node/.openclaw/workspace/vita/skills/vita-task-manager/output
mkdir -p /home/node/.openclaw/workspace/vita/skills/vita-task-manager/data/historico
```

### 2. Backup dos arquivos originais da Vita
```bash
cp /home/node/.openclaw/workspace/vita/SOUL.md /home/node/.openclaw/workspace/vita/SOUL.md.bak
cp /home/node/.openclaw/workspace/vita/AGENTS.md /home/node/.openclaw/workspace/vita/AGENTS.md.bak
cp /home/node/.openclaw/workspace/vita/IDENTITY.md /home/node/.openclaw/workspace/vita/IDENTITY.md.bak
```

### 3. Aplicar patches
cp /home/node/.openclaw/workspace/prometheus/producao/vita-task-manager/patches/vita-SOUL.md /home/node/.openclaw/workspace/vita/SOUL.md
cp /home/node/.openclaw/workspace/prometheus/producao/vita-task-manager/patches/vita-AGENTS.md /home/node/.openclaw/workspace/vita/AGENTS.md
cp /home/node/.openclaw/workspace/prometheus/producao/vita-task-manager/patches/vita-IDENTITY.md /home/node/.openclaw/workspace/vita/IDENTITY.md
```

## Validação Pós-Aplicação

- [ ] Vita entende que não deve editar `output/diarias.md` diretamente
- [ ] Vita conhece comandos `brain-dump`, `dump-to-task`, `ledger-*`
- [ ] Vita conhece comandos `score-task`, `suggest-daily`, `explain-task`
- [ ] Vita sabe usar `suggest-daily` quando Adriano pedir "o que fazer hoje?"
- [ ] Vita sabe usar `explain-task` para justificar prioridades
- [ ] Vita sabe os paths: `input/`, `output/`, `data/historico/`
- [ ] Vita sabe que Faber aplica atualizações da skill
- [ ] Vita sabe que Prometheus desenvolve a skill

## Para a Skill: O que Vita deve fazer

Quando a skill vita-task-manager for instalada, ela espera que a Vita:

1. **Nunca edite arquivos diretamente** — use sempre os comandos CLI
2. **Para adicionar task:** use `ledger-add` com descrição, prioridade, prazo opcional
3. **Para completar task:** use `ledger-complete` com task_id
4. **Para brain dump:** use `brain-dump` quando Adriano estiver sobrecarregado
5. **Para sugestão 1-3-5:** use `suggest-daily` quando pedir "o que fazer hoje?"
6. **Para explicar:** use `explain-task` quando questionar prioridades
7. **Ler output:** `diarias.md` é o render diário — ler para contexto

## Notas

- Estes patches são **conceituais** — não alteram comportamento técnico
- O objetivo é: nos arquivos de personalidade da Vita, a skill é mencionada como ferramenta oficial
- A execução real continua sendo via Gateway/Janus orquestrando
