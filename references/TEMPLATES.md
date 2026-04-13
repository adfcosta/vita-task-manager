# Templates de Tarefas

## Simples (sem prazo)
```markdown
- [ ] {prioridade} {descricao}
  criado: {data_atual}
```

Exemplo:
```markdown
- [ ] 🟡 Comprar leite
  criado: 05/04
```

## Com Prazo
```markdown
- [ ] {prioridade} {descricao}
  prazo: {data_limite}
  criado: {data_atual}
```

Exemplo:
```markdown
- [ ] 🔴 Entregar relatório
  prazo: 10/04
  criado: 05/04
```

## Com Contexto
```markdown
- [ ] {prioridade} {descricao}
  prazo: {data_limite}
  contexto: {contexto_adicional}
  criado: {data_atual}
```

Exemplo:
```markdown
- [ ] 🟡 Comprar ozempic
  contexto: Farmácia Popular, levar receita
  criado: 05/04
```

## Com Progresso (nova)
```markdown
- [~] {prioridade} {descricao}
  prazo: {data_limite}
  progresso: {porcentagem}% ({feito}/{total} {unidade})
  barra: {barra_visual}
  restante: {restante} {unidade}
  meta: {meta_diaria} {unidade}/dia
  criado: {data_atual}
```

Exemplo:
```markdown
- [~] 🔴 Leitura CAPS Vol. 7
  prazo: 15/04
  progresso: 45% (18/40 pgs)
  barra: ▓▓▓▓░
  restante: 22 pgs
  meta: 3 pgs/dia
  criado: 05/04
```

## Com Observação
```markdown
- [ ] {prioridade} {descricao}
  prazo: {data_limite}
  observacao: {nota_livre}
  criado: {data_atual}
```

Exemplo:
```markdown
- [ ] 🟡 Pesquisar hotéis
  prazo: 20/04
  observacao: Verificar política de cancelamento
  criado: 05/04
```

## Concluída
```markdown
- [x] {prioridade} {descricao}
  criado: {data_criacao}
  concluido_em: {data_conclusao}
```

Exemplo:
```markdown
- [x] 🔴 Tomar remédios
  criado: 05/04
  concluido_em: 05/04
```

## Cancelada/Adiada
```markdown
- [-] {prioridade} {descricao}
  motivo: {motivo}
  atualizado_em: {data_atual}
```

Exemplo:
```markdown
- [-] 🟢 Ir ao cinema
  motivo: Mudança de planos, reagendar para próxima semana
  atualizado_em: 06/04
```

## Prioridades

Use as prioridades para indicar urgência:

- `🔴` **Alta**: Fazer primeiro. Prazo curto, alto impacto, ou bloqueante.
- `🟡` **Média**: Fazer depois das altas. Importante mas sem urgência imediata.
- `🟢` **Baixa**: Fazer quando sobrar tempo. Desejável mas não crítica.

## Dicas

1. **Seja específico** na descrição: "Ler capítulo 1" é melhor que "Ler livro"
2. **Defina prazos realistas** e revise conforme necessário
3. **Atualize o progresso** regularmente para manter as metas diárias precisas
4. **Use contexto** para informações que ajudam na execução
5. **Cancele com motivo** para manter histórico de decisões
