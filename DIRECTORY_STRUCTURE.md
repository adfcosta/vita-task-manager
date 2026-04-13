# Estrutura de Diretórios — vita-task-manager v2.3

## Estrutura Padrão (tudo dentro da skill)

```
vita/skills/vita-task-manager/
├── SKILL.md                      # Documentação pública
├── README.md                     # Documentação técnica interna
├── CHANGELOG.md                  # Histórico de versões
├── ROADMAP.md                    # Planejamento futuro
├── scripts/                      # Código Python
│   ├── cli.py
│   ├── scoring.py
│   ├── suggester.py
│   └── ...
├── data/                         # Dados da skill
│   └── historico/               # Ledger JSONL
│       └── DDMMYY_DDMMYY_bruto.jsonl
├── input/                        # Arquivos de entrada (leitura)
│   ├── rotina.md                # Rotina diária
│   └── agenda-semana.md         # Compromissos pontuais
└── output/                       # Arquivos de saída (escrita)
    └── diarias.txt              # Render diário (padrão WhatsApp)
```

## Alternativa: Paths Customizados

A skill aceita paths customizados via CLI, mas o **padrão** é tudo dentro da skill.

### Comando padrão (recomendado):
```bash
cli pipeline \
  --today 08/04 --year 2026 \
  --data-dir vita/skills/vita-task-manager/data \
  --output vita/skills/vita-task-manager/output/diarias.txt \
  --rotina vita/skills/vita-task-manager/input/rotina.md \
  --agenda-semana vita/skills/vita-task-manager/input/agenda-semana.md
```

### Comando mínimo (usa defaults internos):
```bash
cli pipeline --today 08/04 --year 2026 --data-dir vita/skills/vita-task-manager/data
```

## Governança de Arquivos

| Diretório | Permissão | Quem edita |
|-----------|-----------|------------|
| `input/` | Leitura | Usuário (Vita orienta) |
| `data/historico/` | Leitura/Escrita | Skill (append-only) |
| `output/` | Escrita | Skill (gera diarias.txt) |

## Para a Vita

### Arquivos que a Vita DEVE conhecer:

1. **Input (lê):**
   - `vita/skills/vita-task-manager/input/rotina.md`
   - `vita/skills/vita-task-manager/input/agenda-semana.md`

2. **Output (lê para contexto):**
   - `vita/skills/vita-task-manager/output/diarias.txt`

3. **Ledger (nunca lê diretamente — usa CLI):**
   - `vita/skills/vita-task-manager/data/historico/*.jsonl`

### Comando que a Vita deve usar:

```bash
cli pipeline \
  --today DD/MM --year YYYY \
  --data-dir vita/skills/vita-task-manager/data \
  --rotina vita/skills/vita-task-manager/input/rotina.md \
  --agenda-semana vita/skills/vita-task-manager/input/agenda-semana.md \
  --output vita/skills/vita-task-manager/output/diarias.txt
```