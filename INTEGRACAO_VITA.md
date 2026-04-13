# Integração Vita + vita-task-manager

## Objetivo
Embutir no ecossistema Vita a necessidade de usar a skill `vita-task-manager` para operações de task, garantindo consistência entre o propósito da Vita (organização) e a execução técnica (skill).

## Arquivos a Modificar

### 1. vita/SOUL.md
**Adicionar seção:**
```markdown
## Sistema de Tasks (via Skill)

A organização prática é feita através da skill `vita-task-manager`:
- **Fonte de verdade:** Ledger JSONL em `vita/skills/vita-task-manager/data/`
- **Output diário:** `vita/tasks/atividades/diarias.md` (gerado, não editável)
- **Agenda fixa:** `vita/agenda-fixa.md` (compromissos recorrentes)
- **Agenda semana:** `vita/agenda_da_semana.md` (compromissos pontuais)

**Comandos principais:**
- `cli pipeline` — pipeline diário completo
- `cli brain-dump` — captura rápida TDAH
- `cli dump-to-task` — promove item para task

Vita orquestra, a skill executa.
```

### 2. vita/AGENTS.md
**Modificar seção "Sistema de Tasks":**
```markdown
## Sistema de Tasks (via vita-task-manager)

⚠️ **REGRA:** Vita NUNCA edita arquivos de task diretamente. 
Toda operação passa pela skill `vita-task-manager`.

### Fluxo de Trabalho
1. **Manhã:** Skill executa `pipeline` → gera diarias.md
2. **Durante dia:** Vita usa comandos da skill para modificar estado
3. **Brain dump:** Quando sobrecarga mental, captura via skill

### Comandos Vita → Skill
| Intenção | Comando Skill | Retorno Esperado |
|----------|---------------|------------------|
| Adicionar task | `ledger-add` | JSON com task_id |
| Completar task | `ledger-complete` | JSON confirmação |
| Cancelar task | `ledger-cancel` | JSON confirmação |
| Brain dump | `brain-dump` | dump_id |
| Promover dump | `dump-to-task` | task_id |

### Governança
- **Vita:** decide o quê (prioridade, descrição, contexto)
- **Skill:** decide como (IDs, timestamps, ledger)
- **Faber:** aplica atualizações de versão da skill
```

### 3. vita/IDENTITY.md
**Adicionar:**
```markdown
## Ferramenta Principal
Skill `vita-task-manager` — sistema de tasks com ledger JSONL, 
suporte TDAH (brain dump, scoring 1-3-5), e feedback inteligente.
```

### 4. vita/TOOLS.md (novo ou atualizar)
```markdown
### vita-task-manager

Skill instalada em: `vita/skills/vita-task-manager/`

**Uso típico:**
```bash
# Vita aciona via sessions_spawn ou equivalente
python3 -m vita.skills.vita-task-manager.scripts.cli brain-dump \
  --text "Lembrar de..." --today DD/MM --year YYYY --data-dir DATA_DIR
```

**Integração:** Vita sempre consulta skill para operações de task.
Nunca edita diarias.md diretamente.
```

## Checklist de Implementação

- [ ] Modificar SOUL.md (seção Sistema de Tasks)
- [ ] Modificar AGENTS.md (fluxo de trabalho + comandos)
- [ ] Modificar IDENTITY.md (ferramenta principal)
- [ ] Criar/atualizar TOOLS.md
- [ ] Validar que Vita entende: não editar arquivos diretamente
- [ ] Testar: Vita chama skill → skill retorna → Vita interpreta

## Notas

- Esta integração é conceitual — Vita não executa código diretamente,
  mas precisa "saber" que a skill existe e é a ferramenta correta.
- Em implementação real, Janus ou o Gateway orquestram a chamada.
- O importante é: nos arquivos de personalidade da Vita, a skill
  é mencionada como parte do "kit de ferramentas" oficial.
