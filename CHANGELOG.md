# Changelog

Todas as mudanças notáveis desta skill serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

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
