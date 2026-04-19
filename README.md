# Vita Task Manager

Uma skill de gerenciamento de tarefas desenhada pra pessoas com TDAH. Não é mais um "app de to-do": é o braço operacional de uma agente de IA (a **Vita**) que decide, acompanha, lembra e negocia prioridades com você ao longo do dia.

**Versão:** 2.18.0

---

## Por que essa skill existe

Ferramentas de produtividade genéricas falham pra quem tem TDAH por três motivos recorrentes:

1. **Exigem lembrar de abrir o app.** Se eu precisasse lembrar, eu não teria esquecido.
2. **Tratam prioridade como lista estática.** Na vida real, prioridade muda quando muda o clima mental, o nível de energia, ou o que vence antes.
3. **Não sabem como conversar.** "Você tem 42 tarefas pendentes" é ruído; "atacar hoje o remédio que tá atrasado há 3 dias, o resto pode esperar" é ação.

A Vita resolve isso delegando a parte chata (armazenar, calcular, priorizar, lembrar, medir) pra essa skill — um processo determinístico em Python — enquanto ela mesma cuida do que agente humano faz mal e IA faz bem: **interpretar o estado, escolher o que dizer, e dizer no momento certo**.

A skill não tem interface gráfica. Toda interação é via linguagem natural com a Vita, que traduz o que você pediu em comandos CLI, lê o resultado, e responde.

---

## Como ela foi projetada

### 1. Ledger append-only como fonte de verdade

Nada é editado em lugar. Toda mudança — criar uma task, marcar progresso, concluir, cancelar, registrar um feedback, disparar um nudge — é **um novo evento** adicionado no fim de um arquivo JSONL.

```jsonl
{"type":"task","_operation":"create","id":"20260408_tomar_remedios",...}
{"type":"task","_operation":"start","id":"20260408_tomar_remedios",...}
{"type":"task","_operation":"complete","id":"20260408_tomar_remedios",...}
{"type":"nudge","id":"nudge_abc","task_id":"20260408_tomar_remedios",...}
{"type":"feedback","timestamp":"...","data":{...}}
```

O estado atual de qualquer task é o resultado de **dobrar** (fold) todos os eventos daquela task. Concluiu por engano? O evento de conclusão continua lá — você adiciona um novo evento pra reabrir. Nada se perde, tudo é auditável.

Isso combina bem com TDAH por uma razão prática: **erros não são catastróficos**. Você pode inspecionar o histórico inteiro de uma task e entender por que ela foi adiada 5 vezes.

### 2. Regra de ouro: CLI-only

A Vita **nunca** edita arquivos diretamente. Toda escrita passa por `python3 scripts/cli.py <comando>`. Se não existe comando pra operação que você quer, ela não improvisa — pergunta ou escala.

Essa restrição existe pra garantir que:
- O ledger nunca fica inconsistente por causa de um edit malfeito.
- Todo efeito colateral (recalcular duplicatas, atualizar feedback status, gerar nudge) roda junto com a escrita.
- O comportamento da Vita é reproduzível: o mesmo input produz o mesmo comando produz o mesmo estado.

### 3. Prosa na IA, lógica na CLI

A skill é intencionalmente **burra em linguagem** e **inteligente em regras**. Ela:
- Calcula scores, detecta duplicatas, aplica cooldown, consolida alertas, mede KPIs.
- Retorna JSON com os fatos.

A Vita (a IA) é que:
- Lê o JSON e decide o que dizer.
- Compõe a frase com o tom certo pro momento.
- Pergunta quando está em dúvida.

Se você abrir o retorno de `check-alerts`, vai ver uma lista estruturada de condições — **não** uma mensagem pronta. A mensagem bonita é trabalho da Vita.

### 4. Fonte de verdade distribuída

Três arquivos são editados pelo usuário (`input/rotina.md`, `input/agenda-semana.md`), um é a fonte de verdade dinâmica (o ledger), e o resto é **gerado** ou **somente-leitura**. Veja [`DIRECTORY_STRUCTURE.md`](DIRECTORY_STRUCTURE.md) pra o mapa completo.

---

## O dia com a Vita

### Manhã: o pipeline

Um cron (ou a própria Vita via heartbeat) roda o `daily-tick` por volta das 06:00. Ele faz quatro coisas em sequência:

1. **Rollover semanal** — se hoje é o primeiro dia de uma nova semana, as tasks pendentes da semana passada entram no ledger novo automaticamente. Nada é perdido, nada é duplicado.
2. **Sync da rotina** — cada linha de `input/rotina.md` (ex: `- 08:00 | Tomar remédio`) vira uma task no ledger do dia, com dedupe via hash. Rodar duas vezes não cria duplicata.
3. **Avaliação de feedback** — a skill decide se é hora da Vita gerar o "panorama do dia" pra você. Possíveis estados: `required` (primeiro feedback do dia), `offer` (houve mudança desde o último), ou `skip` (nada novo).
4. **Render** — escreve `output/diarias.txt` em formato otimizado pra WhatsApp, pronto pra Vita mandar.

O retorno do pipeline é um JSON que a Vita usa pra decidir o próximo passo:

```json
{
  "ledger_path": "data/historico/050426_110426_bruto.jsonl",
  "rollover": {"performed": false},
  "sync_fixed": {"inserted": [...], "skipped": [...]},
  "feedback_status": "required",
  "feedback_seed": {
    "has_overdue": true,
    "due_today": 2,
    "at_risk_tasks": [...],
    "suggested_focus": "..."
  },
  "output_path": "output/diarias.txt",
  "summary": {"open": 7, "completed_today": 0, "compromissos": 3}
}
```

Se `feedback_status` é `required`, a Vita pega o `feedback_seed`, escreve um panorama curto (4 campos: `panorama`, `foco`, `alerta`, `acao_sugerida`), chama `store-feedback`, e re-renderiza. O usuário abre o WhatsApp e vê o dia pronto.

### Durante o dia: CRUD conversacional

O usuário não digita comando. Ele manda mensagem: *"terminei o relatório", "adiciona comprar café pra amanhã", "adia a reunião pra sexta"*. A Vita (ou o Janus, agente de roteamento) traduz pra comandos:

- `ledger-complete --task-id 20260415_relatorio ...`
- `ledger-add --description "Comprar café" --due 16/04 ...`
- `ledger-update --task-id 20260415_reuniao --due 19/04 ...`

Cada comando retorna JSON com `ok`, o `task_id` afetado, e — importante — `feedback_status` atualizado. Se o status virar `offer`, a Vita pode perguntar *"atualizo o panorama?"* e regenerar o `diarias.txt` com o quadro novo.

Há uma proteção explícita: quando `ledger-add` detecta uma task muito parecida com uma existente, ele retorna `warning.type="duplicate_suspect"` com a task candidata. A Vita **para**, mostra pro usuário, e pergunta: atualizar a existente, forçar nova, ou cancelar. Nunca decide sozinha.

### Brain dump: captura sem compromisso

Um padrão TDAH clássico é ter 8 coisas na cabeça ao mesmo tempo. `brain-dump` captura texto livre sem criar tasks formais — o usuário solta tudo de uma vez:

```bash
cli brain-dump --text "Trocar lâmpada, ligar pro João, comprar café"
```

Esses itens aparecem em seção separada no render, com dica:

```
🧠 BRAIN DUMP
• Trocar lâmpada
• Ligar pro João
• Comprar café
💡 Dica: Escolha 1 pra virar próxima ação
```

Quando o usuário decide atacar um, `dump-to-task` promove aquele item específico pra task formal (com prioridade, prazo, próxima-ação) e remove do dump. Os outros ficam quietos até virarem a bola da vez.

### Priorização: 1-3-5 com boost TDAH

Quando o usuário pergunta *"o que faço hoje?"*, a Vita chama `suggest-daily --limit 9`. A skill aplica o algoritmo 1-3-5:

- **1 BIG** (complexidade 8-10) — a tarefa do bloco de foco do dia
- **3 MEDIUM** (4-7)
- **5 SMALL** (1-3) — quick wins que destravam o cérebro

O score por task combina urgência (35%), simplicidade (25%), idade da task (20%) e penalidade por adiamento (20%). Por cima disso vêm os boosts TDAH:

- Task parada há mais de 21 dias: `+10` (não deixa envelhecer no fundo)
- Task adiada 3 vezes ou mais: `+15` (força conversa sobre por quê)

Se uma faixa fica vazia (nenhuma task BIG disponível, por exemplo), o `suggest-daily` promove/rebaixa candidatos pra preencher os 9 slots com o que há de melhor. O render escreve as sugestões com o motivo de cada escolha — o usuário vê não só *o quê*, mas *por quê*.

### Fim do dia / domingo: a retrospectiva

Um cron semanal (tipicamente domingo 20:00) roda `weekly-tick`, que faz:

1. Atualiza `data/historico-execucao.md` com métricas agregadas (taxa de conclusão, top tasks adiadas, desempenho por dia da semana).
2. Detecta candidatos a **recorrência**: tasks que apareceram 5+ vezes no histórico viram sugestões de regra automática.
3. Roda um diagnóstico do ledger (`ledger-status`) pra alertar sobre rollover perdido, semana sem fechamento, etc.

A Vita apresenta os candidatos de recorrência com um motivo (*"você executou 'treino' em 6 dias diferentes das últimas 4 semanas"*), e **pergunta** antes de ativar. Nada vira automação sem autorização.

Se a taxa de conclusão da semana foi abaixo de 40%, a Vita **não** sugere recorrências — o critério é "não mecanizar hábitos que ainda não existem de verdade".

---

## O sistema de nudges (push proativo)

A peça mais TDAH-específica da skill é o heartbeat: a Vita não espera você perguntar. Um cron dispara `heartbeat-tick` a cada 55 minutos, das 06h às 23h (horário de Maceio).

Cada tick:

1. Lê o estado do ledger.
2. Gera alertas (ver 8 tipos abaixo).
3. Filtra só os **críticos**, aplica cooldown de 24h por task+tipo, consolida múltiplos sinais da mesma task num único nudge, e corta em `max_nudges_per_tick=3`.
4. Persiste cada nudge em `data/proactive-nudges.jsonl` **antes** de tentar entregar (se o envio falhar, nada vaza).
5. Retorna `emit_text` e `emit_target`. A Vita (ou Janus) chama `sessions_send(emit_target, emit_text)` pra pôr a mensagem no WhatsApp do usuário.

O texto do nudge não é gerado pela Vita em tempo real — vem de uma **biblioteca de copy** em `scripts/nudge_copy.py`, com duas variantes (A/B) por tipo de alerta. A escolha de variante é determinística (hash de `task_id:alert_type`), então a mesma task sempre recebe o mesmo estilo até ser resolvida. Isso permite medir qual copy funciona melhor sem contaminar o experimento.

### Os oito tipos de alerta

Cada tipo representa um padrão de falha reconhecível em TDAH:

| Tipo | O que captura | Dispara quando |
|---|---|---|
| `overdue` | Prazo estourou, você não viu | `due_date` no passado |
| `due_today` | Prazo é hoje (ruído, nunca vira nudge) | `due_date` = hoje |
| `due_soon` | Prazo é hoje e tá chegando a hora | hoje + `due_time` dentro da janela (default 4h) |
| `missed_routine` | Rotina crítica que não rodou | opt-in via `!nudge` em `rotina.md`, passou horário + grace |
| `first_touch` | Criou e nunca tocou — bloqueio de iniciação | task em `[ ]` há ≥12h sem nenhum `updated_at` |
| `stalled` | Começou e travou | task em `[~]` há ≥48h sem update |
| `blocked` | Adia repetidamente — sinal de aversão | `postpone_count ≥ 3` |
| `off_pace` | Projeto longo andando devagar | `done < (dias_passados/total_dias) × total × ratio` |

Quando duas condições disparam pra mesma task, a ordem de severidade decide qual vira o nudge:

`overdue → blocked → missed_routine → due_soon → first_touch → stalled → off_pace → due_today`

Assim o usuário recebe **um** recado por task, não um bombardeio.

### Por que esses tipos

Eles derivam da observação de que TDAH não tem um único padrão de falha — tem vários, e precisam ser tratados com linguagens diferentes. `first_touch` é sobre iniciação; a copy pergunta pela **primeira ação concreta**. `blocked` é sobre aversão; a copy reconhece e propõe um passo mínimo. `off_pace` é sobre fiasco silencioso; dispara antes de virar `overdue`, quando ainda há tempo de recolocar no trilho.

### Ciclo completo: delivery → ack → KPIs

Quando a Vita emite um nudge via `sessions_send`, o Janus (agente de mensagem) registra o resultado via `nudge-delivery --status success|failed|skipped`. Se o usuário responder, vira `nudges-ack --response-kind agora|depois|replanejar`. Sem resposta em 24h → conta como `ignorado` implícito no KPI.

O comando `nudge-kpis --window-days 7` fecha o ciclo: retorna taxa de ação, ignorados, e mix de resposta por tipo de alerta e variante A/B. Essa é a retro semanal — permite ver se uma copy específica é melhor que a outra, se um tipo de alerta tá virando spam, ou se um tipo de resposta predomina (ex: "sempre 'depois'" = o formato não tá convencendo).

### Configuração viva

Todos os thresholds vivem em `data/heartbeat-config.json`:

```json
{
  "emit_target": "agent:main:whatsapp:direct:+XXYYYYYYYYYY",
  "severity_floor": "critical",
  "cooldown_hours": 24,
  "max_nudges_per_tick": 3,
  "thresholds": {
    "overdue_min_days": 1,
    "stalled_min_hours": 24,
    "blocked_min_postpones": 2,
    "first_touch_min_hours": 12,
    "off_pace_ratio": 0.7,
    "due_soon_window_hours": 4,
    "missed_routine_grace_hours": 1
  }
}
```

Editar o arquivo tem efeito no próximo tick, sem restart. Sem arquivo: `emit_target=null` (a skill persiste mas não emite), o resto cai nos defaults acima.

---

## Detecção de duplicatas

Um tema recorrente em TDAH é criar a mesma task 3 vezes porque esqueceu que já tinha criado. A skill detecta similares automaticamente quando você chama `ledger-add`.

**Modo simples (fallback):** intersecção de palavras — se 50% das palavras da task nova batem com uma existente, warning.

**Modo com pesos (word_weights.json):** similaridade ponderada por 3 fatores:

| Fator | O que mede | Por que importa |
|---|---|---|
| Distintividade | Raridade em tasks concluídas (log IDF) | "Comprar" tem peso baixo; "escandinávia" tem peso alto |
| Evitação | Taxa de conclusão + postpone_count | Palavras de tasks que você sempre adia pesam mais |
| Tempo de resolução | Horas entre criação e conclusão | Palavras de tasks que você leva muito tempo pra fechar pesam mais |

Os pesos são regenerados semanalmente por `execution-history` a partir do histórico completo. Isso significa que **a detecção aprende com você** — quanto mais histórico, melhor identifica o que é duplicata real vs coincidência de vocabulário.

---

## Comandos CLI (referência)

### Fluxo diário

| Comando | O que faz |
|---|---|
| `pipeline` | Rollover + sync rotina + feedback check + render (WhatsApp) |
| `daily-tick` | `pipeline` + refresh de execution-history e word weights |
| `weekly-tick` | Execution-history + candidatos a recorrência + diagnóstico |
| `render` | Gera saída sem alterar ledger (único que aceita `--format`) |
| `weekly-summary` | Resumo textual da semana atual |

### CRUD

| Comando | O que faz |
|---|---|
| `ledger-add` | Cria task (com detecção de duplicata) |
| `ledger-update` | Altera task existente (nunca use `ledger-add` pra refinar) |
| `ledger-start` | Marca em progresso (respeita WIP=2) |
| `ledger-progress` | Atualiza `done`/`total`/`unit` |
| `ledger-complete` | Conclui |
| `ledger-cancel` | Cancela com motivo |
| `ledger-status` | Diagnóstico do ledger |
| `check-wip` | Consulta limite |

### Priorização

| Comando | O que faz |
|---|---|
| `suggest-daily` | Algoritmo 1-3-5 com boosts TDAH |
| `score-task` | Score bruto de uma task |
| `explain-task` | Por que ela tem esse score |

### Captura TDAH

| Comando | O que faz |
|---|---|
| `brain-dump` | Captura texto livre, não cria task |
| `dump-to-task` | Promove item do dump pra task formal |

### Alertas e heartbeat

| Comando | O que faz |
|---|---|
| `check-alerts` | Inspeção passiva — 8 tipos de alerta acionáveis |
| `heartbeat-tick` | Push proativo — filtra críticos, aplica cooldown, retorna `emit_text` |
| `nudges-pending` | Lista nudges ainda sem ack (fallback se envio falhou) |
| `nudge-delivery` | Registra resultado do envio (success/failed/skipped) |
| `nudges-ack` | Registra resposta do usuário (agora/depois/replanejar) |
| `nudge-kpis` | Consolida taxa de ação e mix de resposta por tipo/variante |

### Recorrência (detectar → aprovar → ativar)

| Comando | O que faz |
|---|---|
| `recurrence-detect` | Analisa 4 semanas, sugere padrões diários/semanais |
| `recurrence-activate` | Ativa (**só após aprovação explícita do usuário**) |
| `recurrence-list` | Regras ativas |
| `recurrence-deactivate` | Desativa com motivo |

### Feedback e manutenção

| Comando | O que faz |
|---|---|
| `store-feedback` | Salva panorama/foco/alerta/acao_sugerida (4 campos obrigatórios) |
| `sync-fixed` | Injeta rotina do dia (chamado pelo pipeline) |
| `rollover` | Rollover semanal manual |
| `execution-history` | Relatório de padrões + word_weights.json |

Veja [`SKILL.md`](SKILL.md) pra a tabela canônica usada pela Vita no runtime (instruções operacionais diretas) e [`DIRECTORY_STRUCTURE.md`](DIRECTORY_STRUCTURE.md) pra governança de arquivos.

---

## Convenções

- **Semana:** domingo → sábado, fuso `America/Maceio` (UTC-3).
- **IDs:** `YYYYMMDD_slug` com sufixo `_2`, `_3` em colisão. IDs de regra de recorrência: `rule_YYYYMMDD_slug[_HHMM]`.
- **Limpeza D+1:** tasks concluídas/canceladas somem do render a partir do dia seguinte (o evento continua no ledger pra sempre).
- **Rollover:** automático no primeiro `pipeline` de uma nova semana. Roda em qualquer dia — não precisa ser domingo.
- **WIP default:** 2 tasks em `[~]` simultaneamente. `ledger-start` bloqueia além disso.

---

## Primeiro uso

```bash
# 1. Copie o exemplo de rotina
cp examples/rotina.md input/rotina.md

# 2. Edite com sua rotina real
$EDITOR input/rotina.md

# 3. Rode o primeiro pipeline
python3 scripts/cli.py pipeline \
  --today $(date +%d/%m) --year $(date +%Y) \
  --rotina input/rotina.md \
  --agenda-semana input/agenda-semana.md \
  --data-dir data \
  --output output/diarias.txt
```

A partir daí, os demais arquivos (`data/historico/*.jsonl`, `output/diarias.txt`, `data/historico-execucao.md`, etc.) são criados e mantidos pela CLI. `input/rotina.md` e `input/agenda-semana.md` continuam sendo editados por você — o resto não.

Todos os arquivos de dados pessoais estão no `.gitignore`, então updates da skill não contaminam seu ledger e seu ledger não vaza no repositório.

---

## Testes

```bash
VITA_TEST_MODE=1 python3 scripts/test_core.py
```

A flag `VITA_TEST_MODE=1` ativa proteção anti-contaminação: se algum teste tentar escrever fora de path temporário, o `append_record` redireciona pra arquivo `TEST_*` e emite warning. Útil pra garantir que testes não sujam seu ledger real durante desenvolvimento.

---

## Features implementadas (v2.2 → v2.18)

- **Scoring 1-3-5 com boosts TDAH** — prioridade dinâmica que considera idade, adiamento e complexidade.
- **Detecção de duplicatas ponderada** — pesos por palavra aprendidos do histórico.
- **Brain dump + promoção seletiva** — captura sem compromisso, converte item a item.
- **WIP limit** — 2 simultâneas, bloqueio explícito com mensagem amigável.
- **Rollover resiliente** — nunca perde task pendente na virada da semana.
- **Execução observada** — `historico-execucao.md` com taxa de conclusão, top adiadas, padrões por dia.
- **Regras de recorrência detectadas** — sugeridas só com aprovação, nunca automáticas.
- **Heartbeat proativo** — 8 tipos de alerta, cooldown, consolidação, limite por tick.
- **Copy A/B determinístico** — biblioteca por tipo de alerta, variante escolhida por hash.
- **Instrumentação completa** — delivery + ack + KPIs com `response_kind` (agora/depois/replanejar).
- **Opt-in de rotina** (`!nudge`) — rotina entra em `missed_routine` só quando marcada explicitamente.

Roadmap detalhado e status versão a versão em [`docs/roadmap-tdah-evidence.md`](docs/roadmap-tdah-evidence.md).

---

## Próximos passos (v3.0+)

- **Timer integrado:** Pomodoro flexível (10/3, 15/5, 20/5) acoplado ao `ledger-start`.

---

## Arquitetura em 30 segundos

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   rotina.md     │     │  agenda-semana  │     │  tasks manuais  │
│  (usuário edita)│     │  (usuário edita)│     │   (via Vita)    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────────┐
                    │   LEDGER JSONL      │◄──── fonte de verdade
                    │   (append-only)     │      (fold de eventos)
                    └──────────┬──────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
  ┌──────────────┐    ┌──────────────┐      ┌──────────────┐
  │    Render    │    │   Scoring    │      │   Heartbeat  │
  │  diarias.txt │    │   1-3-5      │      │  (8 alertas, │
  │  (WhatsApp)  │    │  + boosts    │      │   push Vita) │
  └──────────────┘    └──────────────┘      └──────────────┘
```

---

## Documentação relacionada

- [`SKILL.md`](SKILL.md) — instruções operacionais diretas pra IA (runtime da Vita).
- [`DIRECTORY_STRUCTURE.md`](DIRECTORY_STRUCTURE.md) — árvore + governança por arquivo.
- [`CHANGELOG.md`](CHANGELOG.md) — histórico de versões.
- [`ROADMAP.md`](ROADMAP.md) — planejamento de longo prazo.
- [`WHATSAPP_LAYOUT.md`](WHATSAPP_LAYOUT.md) — referência do formato de render.
- [`docs/roadmap-tdah-evidence.md`](docs/roadmap-tdah-evidence.md) — plano orientado à spec TDAH (v1.0), status por versão.
- [`patches/`](patches/) — blocos que a skill enxerta nos AGENTS vivos da Vita e do Janus.
