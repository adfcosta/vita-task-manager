# Formato de Arquivo de Tarefas

## Estrutura

O arquivo de tarefas é um documento Markdown estruturado com seções específicas.

```markdown
# {título}

## Abertas

{tarefas em aberto ordenadas por prioridade}

## Concluídas

{tarefas concluídas ordenadas por data}

## Canceladas/Adiadas

{tarefas canceladas ordenadas por data}

---

feedback_do_dia:
- panorama: {visão geral}
- foco: {tarefa mais importante}
- alerta: {principal risco}
- acao_sugerida: {próximo passo}
```

## Campos de Tarefa

### Campos Obrigatórios

Toda tarefa deve ter:
- `status`: `[ ]`, `[~]`, `[x]`, ou `[-]`
- `priority`: `🔴`, `🟡`, ou `🟢`
- `description`: texto descritivo

### Campos Opcionais

- `prazo`: data no formato DD/MM
- `progresso`: porcentagem e fração (ex: "45% (9/20 pgs)")
- `barra`: representação visual (ex: "▓▓▓▓░")
- `restante`: quantidade restante (ex: "11 pgs")
- `meta`: meta diária calculada (ex: "6 pgs/dia")
- `contexto`: contexto adicional
- `observacao`: notas livres
- `criado`: data de criação (DD/MM)
- `atualizado_em`: data da última atualização (DD/MM)
- `concluido_em`: data de conclusão (DD/MM)
- `motivo`: motivo do cancelamento

## Exemplos

### Tarefa Simples
```markdown
- [ ] 🟡 Comprar leite
  criado: 05/04
```

### Tarefa com Prazo
```markdown
- [ ] 🔴 Entregar relatório
  prazo: 10/04
  criado: 05/04
```

### Tarefa em Andamento
```markdown
- [~] 🔴 Ler livro
  prazo: 15/04
  progresso: 45% (9/20 pgs)
  barra: ▓▓▓▓░
  restante: 11 pgs
  meta: 2 pgs/dia
  criado: 05/04
  atualizado_em: 06/04
```

### Tarefa Concluída
```markdown
- [x] 🟢 Ligar para João
  criado: 05/04
  concluido_em: 05/04
```

### Tarefa Cancelada
```markdown
- [-] 🟡 Ir ao cinema
  motivo: Mudança de planos
  atualizado_em: 06/04
```

## Validação

O arquivo é validado quanto a:
- Status válidos
- Prioridades válidas
- Formato de datas (DD/MM)
- Estrutura de seções
- Presença de campos obrigatórios
