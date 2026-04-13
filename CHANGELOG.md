# Changelog

Todas as mudanças notáveis desta skill serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

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
