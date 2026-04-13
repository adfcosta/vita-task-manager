# Layout WhatsApp para vita-task-manager

## Formato Aprovado v2.2.0

```
📋 Tasks — 08/04/2026

🔴 URGENTE (prazo hoje)
▢ Revisar arquitetura do sistema

🟡 EM ANDAMENTO
⏳ Escrever documentação técnica
  [█████░░░░░] 50% (5/10 páginas)
  restam 5 páginas

🟢 PRÓXIMAS
▢ Responder emails pendentes
▢ Organizar mesa de trabalho
▢ Ligar para dentista

➖➖➖➖➖➖➖➖➖➖

🧠 BRAIN DUMP (ainda não são tasks)

⏰ até 10/04:
• Trocar lâmpada
• Ligar pro João sobre projeto
• Comprar café

💡 Dica: Escolha 1 pra virar próxima ação

➖➖➖➖➖➖➖➖➖➖

🎯 SUGESTÃO 1-3-5 (baseada no score)

🔥 BIG (1 tarefa exigente)
👉 Revisar arquitetura — score 38
   Por quê: prazo imediato; exige bloco de foco

⚡ MEDIUM (3 tarefas médias)
👉 Responder emails — score 52
   Por quê: prazo hoje; rápido de fazer
👉 Organizar mesa — score 43
   Por quê: prazo amanhã
👉 Documentação técnica — score 31
   Por quê: prazo distante; já começou

✅ SMALL (tarefas rápidas)
👉 Ligar para dentista — score 41
   Por quê: rápida de executar

💬 Quer seguir essa sugestão ou prefere ajustar?
```

## Legenda de Emojis

| Emoji | Significado | Uso |
|-------|-------------|-----|
| 📋 | Cabeçalho do dia | Sempre no topo |
| 🔴 | Alta prioridade / urgente | Seção de urgentes |
| 🟡 | Média prioridade | Seção em andamento |
| 🟢 | Baixa prioridade | Seção próximas |
| ▢ | Task aberta (não iniciada) | Checkbox vazio |
| ⏳ | Task em andamento + progresso | Antes da barra |
| ☑️ | Task concluída | Checkbox marcado |
| ❌ | Task cancelada | X vermelho |
| 🧠 | Brain dump | Seção separada |
| ⏰ | Prazo definido | Antes da data |
| 💡 | Dica TDAH | Ao final do brain dump |
| 🎯 | Sugestão do algoritmo | Seção 1-3-5 |
| 🔥 | Big task (complexa) | Categoria 1-3-5 |
| ⚡ | Medium task | Categoria 1-3-5 |
| ✅ | Small task (rápida) | Categoria 1-3-5 |
| 👉 | Aponta sugestão | Antes de cada task |
| 💬 | Pergunta ao usuário | Ao final |
| ➖ | Separador visual | Entre seções |

## Regras do Layout

1. **Cabeçalho sempre no topo** com data
2. **Seções por prioridade**: 🔴 → 🟡 → 🟢
3. **Brain dump separado** por ➖➖➖
4. **Sugestão 1-3-5 no final** com explicações
5. **Barra de progresso** apenas para tarefas `[~]`
6. **Separadores simples** (➖) entre seções principais
7. **Sem markdown complexo** (negrito/itálico opcional)

## Formato Compacto (opcional)

Para dias muito cheios ou mensagens rápidas:

```
📋 08/04 | 5 abertas | 1 urgente

🔴 ⏳ Revisar arquitetura [█████░░░░░] 50%
🟢 ▢ Ligar dentista
🟢 ▢ Organizar mesa

🎯 1-3-5: 🔥 Revisar | ⚡ Emails, Mesa, Doc | ✅ Dentista

🧠 Dump: Trocar lâmpada, Ligar João, Café
```

## Comando CLI

```bash
cli render \
  --today 08/04 --year 2026 \
  --data-dir vita/skills/vita-task-manager/data \
  --format whatsapp \
  --output /tmp/whatsapp.txt
```

## Implementação

- `formatter_whatsapp.py` — novo módulo
- Flag `--format {markdown|whatsapp}` no CLI
- Default: `markdown` (para arquivo)
- `whatsapp` (quando detectar canal mobile)
