# Regras de Feedback - OBRIGATÓRIO

## ⚠️ FEEDBACK É OBRIGATÓRIO

Toda operação que modifica tarefas **DEVE** atualizar o `feedback_do_dia`.

Sem feedback, o usuário perde visibilidade sobre:
- Prioridades atualizadas
- Riscos identificados
- Próximos passos recomendados

## Formato Obrigatório

```yaml
feedback_do_dia:
- panorama: {visão geral do estado}
- foco: {tarefa mais importante agora}
- alerta: {principal risco ou problema}
- acao_sugerida: {próximo passo recomendado}
```

## Quando Gerar/Atualizar Feedback

### SEMPRE atualizar feedback ao:
- ➕ Adicionar nova tarefa
- 📊 Atualizar progresso
- ✅ Completar tarefa
- ❌ Cancelar tarefa
- 🔄 Reordenar tarefas

### Usar flag `--refresh-feedback` em:
- `add`
- `progress`
- `complete`
- `cancel`
- `resort`

## Ordem de Análise

Ao gerar feedback, analisar tarefas nesta ordem de prioridade:

1. **Tarefas atrasadas** (prazo < hoje)
   - Maior prioridade
   - Alerta: "Existem pendências vencidas"
   - Ação: Resolver a mais crítica

2. **Tarefas com prazo hoje** (prazo = hoje)
   - Prioridade alta
   - Alerta: "O prazo curto reduz a margem para adiar"
   - Ação: Fechar as que vencem hoje

3. **Tarefas 🔴 (alta prioridade)**
   - Verificar se há riscos
   - Considerar como foco potencial

4. **Tarefas em andamento** `[~]`
   - Verificar progresso vs. prazo
   - Calcular meta diária necessária

5. **Tarefas com risco de acúmulo**
   - Meta diária ≥ 25 unidades = risco alto
   - Meta diária ≥ 10 unidades = risco médio

## Níveis de Risco

### Risco Alto
- Tarefa atrasada
- Prazo hoje com trabalho pendente
- Meta diária necessária ≥ 25 unidades
- Prazo muito próximo (≤ 1 dia)

**Alerta típico:** "task atrasada", "prazo hoje e ainda há trabalho pendente", "carga diária necessária está alta"

### Risco Médio
- Prazo se aproximando (≤ 3 dias)
- Meta diária necessária ≥ 10 unidades

**Alerta típico:** "prazo se aproximando", "ritmo diário necessário exige constância"

### Risco Baixo
- Demais tarefas sem problemas identificados

**Alerta típico:** "Sem alertas relevantes no momento"

## Determinando o Foco

O foco deve ser:
- A primeira tarefa da lista ordenada (mais prioritária)
- Ou uma tarefa específica que demanda atenção imediata

**Exemplos de foco:**
- "Leitura CAPS Vol. 7" (tarefa mais prioritária)
- "Resolver tarefas atrasadas" (quando há atrasos)
- "Fechar tarefas que vencem hoje" (quando prazo é hoje)

## Exemplos de Feedback por Situação

### Situação: Tarefas Atrasadas
```yaml
panorama: Há tasks atrasadas e isso pede reorganização imediata.
foco: {descrição da tarefa mais crítica atrasada}
alerta: Existem pendências vencidas.
acao_sugerida: Resolver primeiro a mais crítica entre as atrasadas.
```

### Situação: Prazo Hoje
```yaml
panorama: Há tasks com vencimento hoje.
foco: {descrição da tarefa que vence hoje}
alerta: O prazo curto reduz a margem para adiar.
acao_sugerida: Fechar primeiro as tasks que vencem hoje.
```

### Situação: Risco Identificado
```yaml
panorama: Há tasks abertas e pelo menos uma merece atenção especial.
foco: {descrição da tarefa com maior risco}
alerta: {motivo específico do risco}
acao_sugerida: Garantir avanço hoje na task com maior risco.
```

### Situação: Normal
```yaml
panorama: Há tasks abertas no dia.
foco: {descrição da tarefa mais prioritária}
alerta: Sem alertas relevantes no momento.
acao_sugerida: Atacar primeiro a task mais urgente.
```

## Regras de Estilo

1. **Seja breve**: cada linha deve ser curta e direta
2. **Seja objetivo**: evite frases genéricas
3. **Aponte ação concreta**: o usuário deve saber o que fazer
4. **Não repita a lista**: o feedback resume, não lista
5. **Priorize o crítico**: atrasos e prazos iminentes vêm primeiro

## Validação

O sistema valida que todo feedback contenha:
- `panorama` (não vazio)
- `foco` (não vazio)
- `alerta` (não vazio)
- `acao_sugerida` (não vazio)

Feedback incompleto gera erro e impede salvamento.
