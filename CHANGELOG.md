# Changelog

Todas as mudanças notáveis desta skill serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [2.13.0] - 2026-04-18

### Adicionado
- **Copy library com variantes A/B (spec TDAH §8, §7.3):** novo
  `scripts/nudge_copy.py` com biblioteca de copy por `alert_type`
  seguindo estrutura **detecção + janela + ação mínima**. Templates
  específicos pra overdue/stalled/blocked (first_touch/due_soon/off_pace/
  missed_routine entram em versões futuras).
- **`copy_variant` no record (spec §11):** cada nudge registra qual
  variante foi usada ("A", "B" ou "grouped"). Seleção determinística
  por hash MD5 de `(task_id, alert_type)` — mesma task sempre mesma
  variante, diferentes tasks distribuem razoavelmente entre A/B.
- **`cooldown_applied` no record (spec §11):** booleano explicitando
  que o nudge passou pela checagem de cooldown (sempre `true` pros
  persistidos). Redundante mas exigido pela spec de instrumentação.
- **`render_grouped`:** renderiza copy pra task com múltiplos sinais
  num prompt único ("... está em risco — atrasada há 3d; parada há
  48h. Quer destravar com a menor ação possível?").

### Mudado
- **`emit_text` pra single-nudge:** agora usa copy completo direto
  (ex: "🌿 'X' atrasou 3d. Em vez de terminar tudo, quer só destravar
  com uma subtarefa de 10-15min?") em vez do wrapper antigo
  "🌿 Vita alertou: '...'. Atacar hoje?". Alinha com spec §7.3.
- **`emit_text` pra múltiplos nudges:** bullets sem `🌿` por item
  (só no header), evitando emoji-spam.
- **`_render_nudge_text`:** nova função em `heartbeat.py` que seleciona
  single vs grouped com fallback pra grouped quando copy library não
  cobre o tipo.

### Removido
- **`_format_alert_part` e `_format_group_fragment` em heartbeat.py:**
  substituídos pelos equivalentes em `nudge_copy.py` (lógica de copy
  centralizada fora do engine).

### Contexto
- Segunda fase do roadmap `docs/roadmap-tdah-evidence.md`. Destrava
  experimentação de A/B via `copy_variant` sem mudança de infra de
  emissão — mensura em v2.16.0 (KPIs).
- Módulo batizado `nudge_copy` e não `copy` pra evitar colisão com
  stdlib `copy` no `sys.path` do script runner.
- 3 testes novos em `test_core.py` (total: 81 testes passando):
  `test_copy_variant_deterministic`,
  `test_copy_renders_all_library_types`,
  `test_heartbeat_emit_text_uses_copy_library`. Teste antigo
  `test_heartbeat_tick_critical_overdue` ajustado (assert muda de
  "3 dias" → "3d" por causa do novo formato curto no copy).

## [2.12.0] - 2026-04-18

### Adicionado
- **Thresholds configuráveis (spec TDAH §9):** `data/heartbeat-config.json`
  agora aceita bloco `thresholds` com `overdue_min_days`,
  `stalled_min_hours`, `blocked_min_postpones`. Edita → próximo tick já
  aplica, sem restart. Defaults spec-aligned: `overdue≥1d`,
  `stalled≥24h`, `blocked≥2` (antes eram 2d / 48h / 3 postpones).
- **`max_nudges_per_tick` (spec §10.1):** config ganha campo, default 3.
  Excedentes ficam em `over_limit_deferred` no payload e reaparecem no
  tick seguinte, preservando contexto sem spam.
- **Agrupamento por task (spec §10.2):** `_group_alerts_by_task` mescla
  múltiplos alert_types da mesma task num único nudge. Ex: task com
  overdue+stalled → 1 record com `alert_types: ["overdue", "stalled"]`
  e `text_frag: "… — atrasada há Xd; parada há Yh"`.
- **Ordenação por severidade:** grupos com alert mais crítico
  (overdue > blocked > stalled) emitidos antes quando exceder
  `max_nudges_per_tick`.

### Mudado
- **Record de nudge:** campo `alert_type: str` migrou pra
  `alert_types: list[str]`. Compat retroativa em `is_in_cooldown` e
  `_last_nudge_for` (aceitam ambos formatos na leitura).
- **`is_critical(alert, thresholds)`:** ganha 2º parâmetro; default
  spec-aligned preservado quando omitido.
- **`build_heartbeat_nudges`:** ganha parâmetro opcional `config=`
  pra testes; carrega `load_heartbeat_config(data_dir)` por padrão.
- **`patches/vita-AGENTS.md` v2.12.0:** seção Heartbeat reescrita com
  bloco de defaults de config em JSON + menção explícita a
  agrupamento e limite por tick.

### Contexto
- Primeira fase do roadmap `docs/roadmap-tdah-evidence.md`. Destrava
  experimentação comportamental: mudar threshold agora é ajustar JSON,
  não editar Python.
- 4 testes novos em `test_core.py` (total: 78 testes passando):
  `test_heartbeat_thresholds_from_config`,
  `test_heartbeat_max_nudges_per_tick`,
  `test_heartbeat_groups_same_task_alerts`,
  `test_heartbeat_cooldown_covers_group`.

## [2.11.3] - 2026-04-18

### Mudado
- **`patches/vita-AGENTS.md`:** adicionada seção **Feedback do dia**
  instruindo a Vita a reagir aos campos `feedback_status` e
  `feedback_seed` retornados por todo comando CRUD (`ledger-add` /
  `ledger-update` / `ledger-start` / `ledger-progress` /
  `ledger-complete` / `ledger-cancel`) e pelo `daily-tick`. Inclui
  tabela `required` / `offer` / `skip` → ação, e lembrete de
  re-renderizar após `store-feedback` pra o bloco `💬 Da Vita`
  aparecer no `diarias.txt`.
- Linha `Feedback do dia | store-feedback` adicionada à tabela
  "Operações → comando" do patch.
- Bump dos marcadores para `v2.11.3` em `patches/vita-AGENTS.md`.

### Contexto
- O código Python já emitia `feedback_status` + `feedback_seed` desde
  versões anteriores (ver `scripts/feedback_logic.py` e `SKILL.md`
  seção Feedback). A lacuna era **documental**: o AGENTS patch não
  instruía a Vita a consumir esses campos, então ela só gerava
  feedback quando o usuário pedia explicitamente. Sem mudança de
  código — só do patch AGENTS.

## [2.11.2] - 2026-04-18

### Adicionado
- **Heartbeat proativo com nudges ao usuário:** A Vita agora detecta
  alertas críticos a cada tick do heartbeat (55min) e emite nudges
  proativos via WhatsApp do Janus (`sessions_send` para
  `agent:main:whatsapp:direct:<peer>`). Não depende mais do usuário
  iniciar conversa pra surfacing.
  - Novo `scripts/heartbeat.py` com lógica de cooldown e persistência
  - Novos subcomandos CLI:
    - `heartbeat-tick` — detecta + filtra crítico + cooldown +
      persiste + retorna `emit_text` / `emit_target` pra Vita emitir
    - `nudges-pending` — lista nudges não-acked
    - `nudges-ack` — marca nudge como entregue
  - Store `data/proactive-nudges.jsonl` (JSONL append-only, padrão
    da skill)
  - Config `data/heartbeat-config.json` com `emit_target`,
    `severity_floor`, `cooldown_hours`
  - Thresholds críticos padrão: `overdue ≥ 2 dias`,
    `stalled ≥ 48h`, `blocked ≥ 3 postpones`
  - Cooldown padrão: 24h por `task_id + alert_type`
  - 5 testes novos em `test_core.py` (total: 75 testes passando)
- **`examples/openclaw/vita-HEARTBEAT.md`:** template minimalista
  (cache-friendly) pra substituir o HEARTBEAT.md vivo
- **`examples/openclaw/heartbeat-config.json.example`:** template
  de config

### Mudado
- **Patches bump para v2.11.2:**
  - `patches/janus-AGENTS.md`: adicionado parágrafo "Nudges proativos
    da Vita" com handling do prefixo `[VITA:NUDGE]`. Nota no
    preâmbulo esclarece que `agentId = main` (display "Janus").
  - `patches/vita-AGENTS.md`: adicionada seção "Heartbeat proativo"
    com fluxo `heartbeat-tick` → `sessions_send`. Tabela
    "intenção → comando" ganhou linha de nudges.

### Notas
- Fallback quando `sessions_send` não disponível: nudges já estão no
  disco, próxima interação natural com a Vita surfaces via
  `cli nudges-pending`.
- Se quiser desligar completamente os nudges, basta não configurar
  `emit_target` no `heartbeat-config.json` — emit_text continua
  sendo gerado (útil pra debug) mas não há target pra emitir.

## [2.11.1] - 2026-04-18

### Mudado
- **`patches/vita-AGENTS.md`:** reescrito como delta patch enxuto (~113
  linhas total, bloco BEGIN/END de ~75 linhas). Versão anterior era
  um AGENTS.md completo com seções duplicadas do arquivo vivo
  (Session Start, Scope, Safety, Memory, Operating Rules, Governança,
  etc.). Novo formato contém apenas o que é específico da skill:
  regra de ouro, paths, tabela "intenção → comando", Duplicate
  Guardrail, 3 Standing Orders em bullets, Execute-Verify-Report,
  não-autorizado.
- **`patches/janus-AGENTS.md`:** bloco BEGIN/END condensado
  (~95 → ~25 linhas). Mantém: árvore de decisão (3 caminhos),
  tabela de fallback de `vita_quick_crud`, proibidos. Corta:
  explicações extensas e tabela redundante de tools.
- Ambos patches mantêm marcador `<!-- BEGIN vita-task-manager
  v2.11.1 -->` — aplicação via substituição entre os marcadores
  continua compatível com AGENTS vivos instalados em v2.11.0.

### Notas
- Princípio: AGENTS.md do agente vivo carrega personalidade/contexto
  (SOUL, Operating Rules, Safety, Memory). Patch da skill carrega só
  instruções operacionais da skill. Nada duplicado.
- Detalhes expandidos de comandos, flags e exemplos vivem em
  `SKILL.md` — o patch referencia mas não duplica.
- Crons de Morning Pipeline e Weekly Reflection permanecem
  funcionando inalterados (ver `examples/openclaw/cron-*.sh`).

## [2.10.1] - 2026-04-14

### Corrigido
- **Rollover de brain dumps:** Dumps não convertidos agora são corretamente
  transportados para o ledger da semana seguinte durante o rollover semanal.
  Dumps já convertidos em tasks são ignorados corretamente.
  - Adicionada `get_carry_over_dumps()` em `scripts/ledger.py`
  - Atualizado `perform_rollover()` em `scripts/rollover.py`
  - Adicionados 2 testes: `test_rollover_carries_pending_dumps` e
    `test_rollover_skips_converted_dumps`

## [2.10.0] - 2026-04-13

### Adicionado
- **`check-alerts`:** Novo comando CLI que inspeciona o ledger e retorna
  alertas acionáveis em JSON: tasks vencendo hoje (`due_today`), vencidas
  (`overdue` com `days_overdue`), em progresso paradas há >48h (`stalled`),
  e bloqueadas com `postpone_count >= 3` (`blocked`)
- Função pura `_build_alerts` extraída para reuso interno
- 7 novos testes cobrindo todos os tipos de alerta + CLI (68 testes total)
- Linha na tabela de governança em `vita-AGENTS.md`
- Documentação do comando na seção Apoio do SKILL.md

### Notas
- Único código novo previsto na Fase 2 do `vita-SESSION-DESIGN.md`
- Projetado para execução local pelo Plugin SDK do Janus (zero tokens)

## [2.9.0] - 2026-04-13

### Adicionado
- `patches/vita-SESSION-DESIGN.md`: proposta de otimização de sessão
  com 4 camadas complementares:
  - Sessão isolada diária via cron (elimina bootstrap repetido)
  - Session pruning cache-ttl (impede acúmulo de tool results)
  - Memory flush pré-compactação (preserva estado crítico em disco)
  - Plugin SDK no Janus (resolve operações atômicas sem LLM)
- Projeção de custos baseada em dados reais da semana 07-13/04/2026
  (49 sessões, 675k tokens → estimativa de ~130k/semana com as 4 camadas)
- Plano de implementação em 3 fases (config → plugin → ajuste fino)
- Referência à proposta na seção Automação do SKILL.md

### Notas
- Nenhum código novo. PR puramente documental.
- Fase 1 (sessão diária + pruning) é config-only no OpenClaw.
- Fase 2 (Plugin SDK) requer implementação no Janus + `cli check-alerts` na Vita.
- A proposta é complementar aos Standing Orders de v2.8.0.

## [2.8.0] - 2026-04-13

### Adicionado
- Seção "Programas (Standing Orders)" em patches/vita-AGENTS.md
  formalizando 3 programas no formato OpenClaw:
  - Morning Pipeline (daily-tick automático de manhã)
  - Weekly Reflection (weekly-tick + curadoria de candidatos
    de recorrência aos domingos)
  - Duplicate Guardrail (intercepta warning de ledger-add)
- Princípio Execute-Verify-Report explicitado no patch
- Referência ao padrão OpenClaw standing orders na SKILL.md

### Notas
- Nenhum código novo. PR puramente documental.
- Standing orders ativam quando o Faber aplicar o patch no
  vita-AGENTS.md vivo do Domus — a Vita passa a ter autoridade
  permanente para operar dentro dos programas.

## [2.7.0] - 2026-04-13

### Adicionado
- **`daily-tick`:** Comando composto que roda `pipeline` + `execution-history` + `word_weights` em sequência, com relatório unificado de sucesso/falha por passo
- **`weekly-tick`:** Comando composto que roda `execution-history` + `recurrence-detect` + `ledger-status` em sequência, com relatório unificado
- **`_build_ledger_status`:** Função pura extraída de `cmd_ledger_status` para reuso interno (usado por `weekly-tick`)
- 5 novos testes cobrindo daily-tick, weekly-tick e refactor do ledger-status (61 testes total)
- Seção "Automação" no SKILL.md com exemplos de crontab

### Mudado
- `cmd_ledger_status` refatorado: lógica movida para `_build_ledger_status`, comando agora é thin wrapper
- Tabela de governança em `vita-AGENTS.md` atualizada com tick commands

## [2.6.1] - 2026-04-13

### Adicionado
- `.gitignore` para dados pessoais do usuário
- Diretório `examples/` com rotina de exemplo
- `.gitkeep` em data/historico, input e output

### Mudado
- `input/rotina.md` não é mais versionado; a versão de exemplo foi movida para `examples/rotina.md`
- README.md e SKILL.md documentam a separação entre código da skill e dados do usuário

### Removido
- `data/historico/*.jsonl` do tracking (preservados no git history)
- `data/historico-execucao.md` do tracking
- `output/diarias.txt` do tracking
- `data/word_weights.json` do tracking (se existia)

### Notas de migração
Quem já tem o repo clonado localmente:
- Dados pessoais continuam no disco (remoção foi --cached)
- Próximo `git pull` não reintroduz os arquivos
- Para primeira instalação em máquina nova: `cp examples/rotina.md input/rotina.md` antes de rodar o pipeline

## [2.6.0] - 2026-04-13

### Adicionado
- **Detecção de recorrência:** `recurrence-detect` analisa histórico do ledger e identifica tasks que se repetem com frequência, sugerindo padrões daily/weekly com horário predominante
- **Regras de recorrência:** `recurrence-activate` e `recurrence-deactivate` para criar/desativar regras append-only no ledger (`type="recurrence_rule"`)
- **`recurrence-list`:** Lista regras de recorrência ativas
- **Injeção automática:** `sync-fixed` (via pipeline) agora injeta tasks tanto de `rotina.md` quanto de regras de recorrência ativas, respeitando dia da semana e deduplicando por hash
- **`scripts/recurrence.py`:** Novo módulo com 8 funções para detecção de padrões e gestão de regras
- Retorno de `sync_fixed_agenda` agora inclui `sources` com breakdown por `rotina` e `recurrence`
- 14 novos testes cobrindo detecção de padrões, ativação/desativação de regras, filtragem por weekday, injeção via sync, e CLI end-to-end (56 testes total)

## [2.5.0] - 2026-04-13

### Adicionado
- **Detecção inteligente de duplicatas:** `ledger-add` detecta tasks similares usando similaridade ponderada com 3 fatores (distintividade x evitação x tempo de resolução)
- **Word weights:** `execution-history` gera `data/word_weights.json` como subproduto semanal — palavras de tasks frequentemente adiadas ou nunca concluídas pesam mais na detecção
- **`ledger-status`:** Comando de diagnóstico do ledger (semana atual/anterior, tasks abertas, rollover pendente, issues)
- **`ledger-update`:** Atualização in-place de campos de task existente (descrição, contexto, prioridade, prazo) sem criar duplicata
- **`execution-history`:** Relatório de padrões de execução (completion rate, por source, top postponed, por dia da semana)
- **Feedback no WhatsApp:** `feedback_do_dia` renderizado no topo da saída quando todos os 4 campos obrigatórios estão presentes
- Testes de rollover, detecção de duplicatas, word weights, ledger-update, ledger-status, execution-history (42 testes total)

### Corrigido
- **Rollover resiliente:** Migração de tasks agora funciona em qualquer dia da semana, não apenas domingo. Se o pipeline não rodou no domingo, o rollover acontece no primeiro dia em que for chamado
- **Cálculo do ledger anterior:** `perform_rollover()` agora usa `get_week_start(today)` em vez de `today - 7` para encontrar o ledger correto independente do dia
- Falso positivo no `test_sync_fixed_dedup` (formato de rotina obsoleto)

### Removido
- Arquivos de notas de trabalho obsoletos

## [2.3.1] - 2026-04-08

### Corrigido
- `render`: `--format whatsapp` agora é o padrão efetivo no CLI
- `test_core.py`: validação ajustada para garantir render WhatsApp mesmo sem `--format`
- **SKILL.md:** Estrutura e fluxo padrão agora referenciam `diarias.txt` como saída principal
- **SKILL.md:** Adicionada nota explicando uso de `.txt` (padrão) vs `.md` (explícito)
- **SKILL.md:** Documentação agnóstica — removidas instruções específicas para agentes
- **Patches:** `vita-AGENTS.md` e `vita-SOUL.md` atualizados para usar `diarias.txt`
- Descrição da skill simplificada (sem referências a agentes específicos)

## [2.3.0] - 2026-04-08

### Adicionado
- WIP limit padrão de 2 tarefas em andamento com helpers `get_wip_count()` e `can_start_new_task()`
- Novos comandos CLI: `check-wip` e `ledger-start`
- Novo formatador `scripts/formatter_whatsapp.py` com layout otimizado para WhatsApp
- Novo layout documentado em `references/WHATSAPP_LAYOUT.md`
- Novos testes cobrindo WIP limit, render WhatsApp, `ledger-start` e estados visuais

### Mudado
- `render` agora aceita `--format {markdown|whatsapp}`
- Render markdown agora mostra estados visuais: `▢`, `⏳`, `☑️`, `❌`
- Tasks em andamento exibem barra de progresso também no markdown
- Render WhatsApp aplica prefixos de idade (`⚠️`, `👻`) para destacar tarefas antigas
- Fluxo de início de task agora bloqueia quando o WIP já atingiu o limite configurado

## [2.2.1] - 2026-04-08

### Corrigido
- **Isolamento de testes:** Proteção contra escrita em diretório de produção durante execução de testes
- `ledger.py`: `append_record()` agora detecta modo teste e previne contaminação de dados
- `test_core.py`: Adiciona `VITA_TEST_MODE=1` e mensagens de confirmação
- Ledger de produção limpo após contaminação acidental durante instalação

## [2.2.0] - 2026-04-08

### Adicionado
- Sistema de scoring dinâmico TDAH-friendly com breakdown explicável
- Novos campos de task: `complexity_score`, `complexity_source`, `first_added_date`, `postpone_count`, `energy_required`, `score_breakdown`
- Novo módulo `scripts/scoring.py` com cálculo de urgência, complexidade invertida, idade e penalidade por adiamento
- Novo módulo `scripts/suggester.py` com sugestão diária 1-3-5 e explicações legíveis
- Novos comandos CLI: `score-task`, `suggest-daily`, `explain-task`
- Seção `🎯 Sugestão 1-3-5` no render diário quando houver tasks abertas sem complexidade explícita
- Continuidade de scoring no rollover semanal, preservando `first_added_date` e acumulando `postpone_count`
- Testes cobrindo score, sugestão e integração do render

### Mudado
- Tasks novas no ledger passam a nascer com metadados prontos para scoring
- Tasks sem complexidade explícita agora usam inferência heurística com fallback neutro 5
- Sugestões priorizam score dentro de cada faixa e respeitam hard limits 1-3-5

## [2.1.0] - 2026-04-08

### Adicionado
- **Brain Dump** (`brain-dump`, `dump-to-task`) — captura rápida de sobrecarga mental TDAH
- Seção `🧠 Brain Dump` no render diário com dica TDAH
- Campo `next_action` para próxima ação física ao promover dump
- Dump convertido some automaticamente da lista após virar task
- **Prazo no brain dump** (`--due`): aceita `+N` (dias) ou `DD/MM/YYYY`
- Herança de prazo: dump → task (afeta scoring futuro)

### Para TDAH
- Esvaziamento mental rápido sem criar tarefas formais imediatamente
- Promoção seletiva: escolhe 1 item do dump para virar próxima ação
- Reduz paralisia por excesso de opções
- Prazo visual no dump ajuda priorização mesmo antes de virar task

## [2.0.0] - 2026-04-08

### Adicionado
- Arquitetura de ledger JSONL como fonte de verdade
- Pipeline diário automático (`cli pipeline`)
- Sincronização de rotina fixa (`agenda-fixa.md`)
- Agenda semanal como lembretes simbólicos
- Feedback versionado (série temporal)
- IDs únicos com sufixo incremental (`_2`, `_3`) para evitar colisões
- Deduplicação por hash SHA256 no sync-fixed
- Testes automatizados (`scripts/test_core.py`)
- Comando `weekly-summary` para resumo semanal

### Mudado
- Formato de armazenamento: de markdown editável para JSONL append-only
- Estratégia de IDs: agora inclui verificação de colisão no ledger
- Deduplicação: de comparação textual para hash de descrição + horário

### Removido
- Suporte à edição direta de `diarias.md` (agora é output gerado)

## [1.0.0] - 2026-04-06

### Adicionado
- Sistema básico de gerenciamento de tarefas em markdown
- CLI com comandos: validate, summary, add, progress, complete, cancel, resort
- Priorização com emojis (🔴 🟡 🟢)
- Cálculo automático de progresso e metas diárias
- Feedback obrigatório estruturado

---

## Convenções de Versão

- **MAJOR**: Mudanças incompatíveis na API ou arquitetura
- **MINOR**: Funcionalidades adicionadas de forma compatível
- **PATCH**: Correções de bugs e melhorias internas
