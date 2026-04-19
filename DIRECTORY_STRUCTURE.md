# Estrutura de Diretórios — vita-task-manager v2.18.0

## Árvore

```
vita-task-manager/
├── SKILL.md                         # Instruções operacionais pra IA (Vita)
├── README.md                        # Overview humano
├── CHANGELOG.md                     # Histórico de versões
├── ROADMAP.md                       # Planejamento de longo prazo
├── WHATSAPP_LAYOUT.md               # Referência do layout de render
├── DIRECTORY_STRUCTURE.md           # Este arquivo
│
├── scripts/                         # Código Python da skill
│   ├── cli.py                       # Interface CLI (ponto de entrada)
│   ├── pipeline.py                  # Orquestrador do fluxo diário
│   ├── ledger.py                    # Engine do ledger JSONL
│   ├── ledger_ops.py                # CRUD, WIP, sync, feedback
│   ├── models.py                    # Dataclasses (Task, FixedEntry, etc.)
│   ├── parser.py                    # Parser de input antigo (markdown)
│   ├── fixed_parser.py              # Parser de rotina.md (+ sigil !nudge)
│   ├── agenda_parser.py             # Parser de agenda-semana.md
│   ├── scoring.py                   # Cálculo de score
│   ├── suggester.py                 # Algoritmo 1-3-5
│   ├── sorter.py                    # Ordenação por score
│   ├── render.py                    # Montagem do TaskFile
│   ├── formatter_whatsapp.py        # Formato WhatsApp (padrão)
│   ├── formatter.py                 # Formato markdown (opcional)
│   ├── execution_history.py         # Relatório de padrões + word weights
│   ├── recurrence.py                # Detecção e regras de recorrência
│   ├── rollover.py                  # Transição semanal
│   ├── heartbeat.py                 # Motor de nudges proativos
│   ├── nudge_copy.py                # Biblioteca de copy A/B determinístico
│   ├── kpis.py                      # Consolidação de KPIs de nudge
│   ├── feedback_input.py            # Validação de payload de feedback
│   ├── feedback_logic.py            # Decisão de feedback_status
│   ├── weekly_summary.py            # Resumo semanal
│   ├── calculator.py                # Utilitários de cálculo/datas
│   ├── updater.py                   # Operações de update in-place (legado)
│   ├── validator.py                 # Validação (legado)
│   ├── utils.py                     # Helpers compartilhados
│   └── test_core.py                 # Suíte de testes
│
├── input/                           # Entrada editada pelo usuário
│   ├── rotina.md                    # Rotina diária (- HH:MM | desc [!nudge])
│   └── agenda-semana.md             # Compromissos pontuais
│
├── data/                            # Estado gerenciado pela skill
│   ├── historico/                   # Ledger JSONL append-only (fonte de verdade)
│   │   └── DDMMYY_DDMMYY_bruto.jsonl
│   ├── historico-execucao.md        # Relatório lido pela Vita no Session Start
│   ├── word_weights.json            # Pesos p/ detecção de duplicatas
│   ├── proactive-nudges.jsonl       # Ledger de nudges (push proativo)
│   └── heartbeat-config.json        # Config do heartbeat (manual OK)
│
├── output/                          # Render diário
│   └── diarias.txt                  # Formato WhatsApp (padrão)
│
├── patches/                         # Blocos que a skill enxerta em AGENTS vivos
│   ├── README.md                    # Filosofia delta + como aplicar
│   ├── vita-AGENTS.md               # Bloco pro agente Vita
│   ├── janus-AGENTS.md              # Bloco pro agente Janus (router)
│   └── vita-SESSION-DESIGN.md       # Design do modelo de sessão (referência)
│
├── examples/                        # Pontos de partida versionados
│   ├── rotina.md                    # Exemplo de rotina
│   └── openclaw/                    # Configs de cron, heartbeat, HEARTBEAT.md
│
└── references/                      # Material de apoio (specs, artigos)
```

## Governança por arquivo

| Caminho | Quem escreve | Quando |
|---|---|---|
| `input/rotina.md` | **Usuário** | Edita manualmente |
| `input/agenda-semana.md` | **Usuário** | Edita manualmente |
| `data/historico/*.jsonl` | **CLI** (append-only) | Todo comando CRUD + `pipeline` |
| `data/historico-execucao.md` | **CLI** entre `<!-- BEGIN METRICS -->`/`<!-- END METRICS -->` | `execution-history` / `daily-tick` / `weekly-tick` |
| `data/word_weights.json` | **CLI** | Subproduto de `execution-history` |
| `data/proactive-nudges.jsonl` | **CLI** (append-only) | `heartbeat-tick`, `nudge-delivery`, `nudges-ack` |
| `data/heartbeat-config.json` | **Config manual** | Editar diretamente; efeito no próximo tick |
| `output/diarias.txt` | **CLI** (overwrite) | `render` / `pipeline` |
| `scripts/**` | **Mantenedores** | PR |
| `patches/**` | **Mantenedores** | PR — versionar junto com bump da skill |
| `examples/**`, `references/**` | **Mantenedores** | PR |
| `SKILL.md`, `README.md`, `CHANGELOG.md`, `ROADMAP.md`, `WHATSAPP_LAYOUT.md`, `DIRECTORY_STRUCTURE.md` | **Mantenedores** | PR |

## Regras pra Vita

| Arquivo | Ação permitida |
|---|---|
| `input/rotina.md`, `input/agenda-semana.md` | **Ler** (contexto). Nunca escrever — é do usuário. |
| `data/historico-execucao.md` | **Ler** no Session Start pra calibrar planejamento. Não escrever fora de `## Observações` (e mesmo essa seção só via edição manual, não via comando). |
| `output/diarias.txt` | **Ler** pra referenciar o panorama atual. Nunca escrever direto — chamar `render`. |
| `data/historico/*.jsonl`, `data/*.json`, `data/proactive-nudges.jsonl` | **Nunca ler ou escrever direto.** Toda operação passa por `scripts/cli.py`. |
| `data/heartbeat-config.json` | Leitura OK pra justificar comportamento; alteração só com ordem explícita do usuário. |

## Paths relativos vs absolutos

A skill roda sempre via `python3 scripts/cli.py` com flags de path explícitas. Sem defaults internos — os paths vêm dos argumentos:

```bash
python3 scripts/cli.py pipeline \
  --today DD/MM --year YYYY \
  --data-dir data \
  --rotina input/rotina.md \
  --agenda-semana input/agenda-semana.md \
  --output output/diarias.txt
```

No OpenClaw (workspace vivo do agente), substituir por caminhos absolutos conforme o layout do Domus.
