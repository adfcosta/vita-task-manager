"""Testes básicos do vita-task-manager."""

import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

try:
    from .formatter import format_task_file
    from .formatter_whatsapp import format_task_file_whatsapp
    from .ledger import (
        get_current_task_state,
        get_ledger_path,
        get_week_end,
        get_week_start,
        load_ledger,
        make_task_id,
    )
    from .ledger_ops import (
        add_task,
        can_start_new_task,
        check_wip_limit,
        complete_task,
        get_wip_count,
        start_task,
        sync_fixed_agenda,
        update_progress,
        update_task,
    )
    from .models import BrainDumpEntry, SuggestedTask, Task, TaskFile
    from .render import render_daily
    from .scoring import (
        calculate_age_boost,
        calculate_complexity_score,
        calculate_postpone_penalty,
        calculate_total_score,
        calculate_urgency,
    )
    from .suggester import explain_suggestion, suggest_135
    from .execution_history import build_execution_history, build_word_weights, load_word_weights, render_markdown as render_history_markdown, write_history_file, write_word_weights
    from .rollover import perform_rollover
    from .recurrence import (
        activate_recurrence_rule,
        deactivate_recurrence_rule,
        detect_recurrence_candidates,
        get_active_recurrence_rules,
        get_rules_for_weekday,
        _detect_pattern,
        _detect_time_mode,
    )
except ImportError:
    from formatter import format_task_file
    from formatter_whatsapp import format_task_file_whatsapp
    from ledger import (
        get_current_task_state,
        get_ledger_path,
        get_week_end,
        get_week_start,
        load_ledger,
        make_task_id,
    )
    from ledger_ops import (
        add_task,
        can_start_new_task,
        check_wip_limit,
        complete_task,
        get_wip_count,
        start_task,
        sync_fixed_agenda,
        update_progress,
        update_task,
    )
    from models import BrainDumpEntry, SuggestedTask, Task, TaskFile
    from render import render_daily
    from scoring import (
        calculate_age_boost,
        calculate_complexity_score,
        calculate_postpone_penalty,
        calculate_total_score,
        calculate_urgency,
    )
    from suggester import explain_suggestion, suggest_135
    from execution_history import build_execution_history, build_word_weights, load_word_weights, render_markdown as render_history_markdown, write_history_file, write_word_weights
    from rollover import perform_rollover
    from recurrence import (
        activate_recurrence_rule,
        deactivate_recurrence_rule,
        detect_recurrence_candidates,
        get_active_recurrence_rules,
        get_rules_for_weekday,
        _detect_pattern,
        _detect_time_mode,
    )


CLI_PATH = Path(__file__).parent / 'cli.py'


def test_week_start():
    """Semana começa no domingo."""
    wed = date(2026, 4, 8)
    sun = get_week_start(wed)
    assert sun.weekday() == 6, "Domingo deve ser weekday=6"
    assert sun.day == 5
    print("✓ test_week_start")


def test_week_end():
    """Semana termina no sábado."""
    wed = date(2026, 4, 8)
    sat = get_week_end(wed)
    assert sat.weekday() == 5, "Sábado deve ser weekday=5"
    assert sat.day == 11
    print("✓ test_week_end")


def test_ledger_path():
    """Geração correta do path do ledger."""
    data_dir = Path('/tmp/data')
    path = get_ledger_path(date(2026, 4, 8), 2026, data_dir)
    assert '050426_110426_bruto.jsonl' in str(path)
    print('✓ test_ledger_path')


def test_make_task_id():
    """IDs devem ser únicos mesmo com descrição repetida."""
    ledger = []

    id1 = make_task_id('Tomar remédios', date(2026, 4, 8), ledger)
    assert id1 == '20260408_tomar_remedios'

    ledger.append({'type': 'task', 'id': id1})

    id2 = make_task_id('Tomar remédios', date(2026, 4, 8), ledger)
    assert id2 == '20260408_tomar_remedios_2'

    ledger.append({'type': 'task', 'id': id2})

    id3 = make_task_id('Tomar remédios', date(2026, 4, 8), ledger)
    assert id3 == '20260408_tomar_remedios_3'

    print('✓ test_make_task_id')


def test_add_and_complete_task():
    """Ciclo completo de add → complete."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 8), 2026, data_dir)

        result = add_task(
            ledger_path=ledger_path,
            description='Teste',
            priority='🔴',
            today_ddmm='08/04',
            year=2026,
        )
        assert result['ok']
        task_id = result['task_id']

        result = complete_task(ledger_path, task_id, '08/04')
        assert result['ok']

        ledger = load_ledger(ledger_path)
        assert len(ledger) == 2

        complete_record = ledger[-1]
        assert complete_record['status'] == '[x]'
        assert complete_record['completed_at'] is not None

        print('✓ test_add_and_complete_task')


def test_progress_tracking():
    """Progresso deve calcular porcentagem e barra."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 8), 2026, data_dir)

        result = add_task(
            ledger_path=ledger_path,
            description='Leitura',
            priority='🟡',
            today_ddmm='08/04',
            year=2026,
        )
        task_id = result['task_id']

        result = update_progress(
            ledger_path=ledger_path,
            task_id=task_id,
            done=5,
            total=20,
            unit='pgs',
            today_ddmm='08/04',
            year=2026,
        )
        assert result['ok']
        assert result['percent'] == 25

        ledger = load_ledger(ledger_path)
        progress_record = [r for r in ledger if r.get('_operation') == 'progress'][0]
        assert progress_record['progress_percent'] == 25
        assert '▓' in progress_record['progress_bar']

        print('✓ test_progress_tracking')


def test_sync_fixed_dedup():
    """Sync não deve duplicar entradas."""
    rotina_content = """# Rotina

## Tarefas Diárias
- 06:00 | Tomar remédios
- 15:00 | Terapia
"""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        rotina_path = data_dir / 'rotina.md'
        rotina_path.write_text(rotina_content, encoding='utf-8')
        ledger_path = get_ledger_path(date(2026, 4, 8), 2026, data_dir)

        result1 = sync_fixed_agenda(rotina_path, ledger_path, '08/04', 2026)
        assert len(result1['inserted']) == 2

        # Valida conteúdo parseado, não só contagem
        ledger = load_ledger(ledger_path)
        rotina_tasks = [
            r for r in ledger
            if r.get('type') == 'task' and r.get('source') == 'rotina'
        ]
        descriptions = {r['description'] for r in rotina_tasks}
        contexts = {r['context'] for r in rotina_tasks}
        assert descriptions == {'Tomar remédios', 'Terapia'}, (
            f"Descriptions parseadas = {descriptions}. "
            "Se aparecer lixo tipo '[ ] 🔴 06:00 | Tomar remédios', "
            "o parser está aceitando formato antigo silenciosamente."
        )
        assert contexts == {'06:00', '15:00'}, (
            f"Contexts parseados = {contexts}. "
            "Se aparecer lixo tipo '[ ] 🔴 06:00 | Tomar remédios', "
            "o parser está aceitando formato antigo silenciosamente."
        )

        # Idempotência: segunda sync não duplica
        result2 = sync_fixed_agenda(rotina_path, ledger_path, '08/04', 2026)
        assert len(result2['inserted']) == 0
        assert len(result2['skipped']) == 2

        print('✓ test_sync_fixed_dedup')


def test_wip_limit():
    """WIP limit deve contar apenas tasks em andamento."""
    tasks = [
        {'status': '[~]'},
        {'status': '[ ]'},
        {'status': '[~]'},
        {'status': '[x]'},
    ]
    assert get_wip_count(tasks) == 2
    assert can_start_new_task(tasks, limit=2) is False
    assert can_start_new_task(tasks, limit=3) is True
    print('✓ test_wip_limit')


def test_check_wip_limit_payload():
    """Payload de check-wip deve trazer warning amigável."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 8), 2026, data_dir)
        a = add_task(ledger_path, 'Tarefa A', '🟡', '08/04', 2026)
        b = add_task(ledger_path, 'Tarefa B', '🟡', '08/04', 2026)
        assert start_task(ledger_path, a['task_id'], '08/04')['ok']
        assert start_task(ledger_path, b['task_id'], '08/04')['ok']

        result = check_wip_limit(ledger_path, limit=2)
        assert result['current_wip'] == 2
        assert result['limit'] == 2
        assert result['can_start'] is False
        assert result['warning'] == 'Você já tem 2 tarefas em andamento. Que tal terminar uma antes de começar outra?'
        print('✓ test_check_wip_limit_payload')


def test_ledger_start():
    """ledger-start deve iniciar task pendente."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 8), 2026, data_dir)
        created = add_task(ledger_path, 'Escrever docs', '🟡', '08/04', 2026)

        result = start_task(ledger_path, created['task_id'], '08/04')
        assert result['ok'] is True
        assert result['status'] == '[~]'

        state = get_current_task_state(load_ledger(ledger_path), created['task_id'])
        assert state['status'] == '[~]'
        print('✓ test_ledger_start')


def test_ledger_start_blocks_when_limit_reached():
    """Não deve iniciar terceira task se WIP já estiver no limite."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 8), 2026, data_dir)
        created = [add_task(ledger_path, f'Tarefa {i}', '🟡', '08/04', 2026) for i in range(3)]
        assert start_task(ledger_path, created[0]['task_id'], '08/04')['ok']
        assert start_task(ledger_path, created[1]['task_id'], '08/04')['ok']

        blocked = start_task(ledger_path, created[2]['task_id'], '08/04')
        assert blocked['ok'] is False
        assert blocked['can_start'] is False
        assert 'Que tal terminar uma antes de começar outra?' in blocked['warning']
        print('✓ test_ledger_start_blocks_when_limit_reached')


def test_scoring_functions():
    """Scoring deve refletir urgência, idade e adiamento."""
    today = date(2026, 4, 8)
    task = Task(
        status='[ ]',
        priority='🔴',
        description='Revisar PR crítico',
        due_date='08/04',
        first_added_date='2026-03-01',
        postpone_count=3,
        complexity_score=8,
    )

    assert calculate_urgency(task.due_date, today) == 95.0
    assert calculate_complexity_score(task) == 30.0
    assert calculate_age_boost(task.first_added_date, today) == 100.0
    assert calculate_postpone_penalty(task.postpone_count) == 60.0

    total = calculate_total_score(task, today)
    assert total['score'] > 40.0
    assert total['score_breakdown']['complexity_value'] == 8
    assert 'boost_age_21d' in total['score_breakdown']['overrides']
    assert 'boost_postpone_3x' in total['score_breakdown']['overrides']

    print('✓ test_scoring_functions')


def test_suggest_135_distribution():
    """Distribuição 1-3-5 deve respeitar limites duros e priorizar score."""
    today = date(2026, 4, 8)
    tasks = [
        Task(status='[ ]', priority='🔴', description='Projeto estratégico', due_date='09/04', complexity_score=9, first_added_date='2026-04-01'),
        Task(status='[ ]', priority='🟡', description='Revisar documentação', due_date='08/04', complexity_score=6, first_added_date='2026-04-04'),
        Task(status='[ ]', priority='🟡', description='Responder emails', due_date='09/04', complexity_score=4, first_added_date='2026-04-05'),
        Task(status='[ ]', priority='🟢', description='Organizar mesa', due_date='10/04', complexity_score=3, first_added_date='2026-04-02'),
        Task(status='[ ]', priority='🟢', description='Comprar café', due_date='08/04', complexity_score=1, first_added_date='2026-04-08'),
        Task(status='[ ]', priority='🟢', description='Tomar remédio', due_date='08/04', complexity_score=1, first_added_date='2026-04-08'),
        Task(status='[ ]', priority='🟡', description='Agendar reunião', due_date='10/04', complexity_score=3, first_added_date='2026-04-06'),
        Task(status='[ ]', priority='🟡', description='Atualizar planilha', due_date='11/04', complexity_score=5, first_added_date='2026-04-03', postpone_count=1),
        Task(status='[ ]', priority='🔴', description='Ligar para dentista', due_date='12/04', complexity_score=2, first_added_date='2026-03-20', postpone_count=3),
    ]

    suggestions = suggest_135(tasks, today)
    assert len(suggestions['big']) <= 1
    assert len(suggestions['medium']) <= 3
    assert len(suggestions['small']) <= 5
    assert len(suggestions['big']) + len(suggestions['medium']) + len(suggestions['small']) <= 9

    for bucket in ('big', 'medium', 'small'):
        scores = [item['score'] for item in suggestions[bucket]]
        assert scores == sorted(scores, reverse=True)

    explanation = explain_suggestion(suggestions['small'][0])
    assert explanation

    print('✓ test_suggest_135_distribution')


def test_render_includes_suggestion_section():
    """Render deve incluir sugestão 1-3-5 quando houver tasks sem complexidade explícita."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 8), 2026, data_dir)

        result = add_task(
            ledger_path=ledger_path,
            description='Escrever relatório curto',
            priority='🔴',
            today_ddmm='08/04',
            year=2026,
            due_date='08/04',
        )
        assert result['ok']

        taskfile, _ = render_daily(
            ledger_path=ledger_path,
            agenda_semana_path=None,
            today_ddmm='08/04',
            year=2026,
        )

        total_suggestions = sum(len(items) for items in taskfile.suggestion_135.values())
        assert total_suggestions >= 1
        assert taskfile.suggestion_135['medium'][0].explanation

        print('✓ test_render_includes_suggestion_section')


def test_markdown_visual_states():
    """Render markdown deve usar símbolos visuais de status."""
    taskfile = TaskFile(
        title='Tasks — 08/04/2026',
        open_tasks=[Task(status='[ ]', priority='🔴', description='Planejar sprint')],
        completed_tasks=[Task(status='[x]', priority='🟢', description='Enviar email')],
        cancelled_tasks=[Task(status='[-]', priority='🟡', description='Adiar reunião')],
    )
    rendered = format_task_file(taskfile)
    assert '▢ 🔴 Planejar sprint' in rendered
    assert '☑️ 🟢 Enviar email' in rendered
    assert '❌ 🟡 Adiar reunião' in rendered
    print('✓ test_markdown_visual_states')


def test_markdown_in_progress_shows_bar():
    """Task em andamento no markdown deve exibir ⏳ e barra."""
    taskfile = TaskFile(
        title='Tasks — 08/04/2026',
        open_tasks=[
            Task(
                status='[~]',
                priority='🟡',
                description='Ler livro',
                progress_percent=50,
                progress_done=5,
                progress_total=10,
                unit='pgs',
                progress_bar='▓▓▓▓▓░░░░░',
                remaining_text='5 pgs',
            )
        ],
    )
    rendered = format_task_file(taskfile)
    assert '⏳ 🟡 Ler livro' in rendered
    assert 'progresso: 50% (5/10 pgs) ▓▓▓▓▓░░░░░' in rendered
    print('✓ test_markdown_in_progress_shows_bar')


def test_whatsapp_format():
    """Saída WhatsApp deve seguir layout esperado."""
    taskfile = TaskFile(
        title='Tasks — 08/04/2026',
        open_tasks=[
            Task(status='[ ]', priority='🔴', description='Revisar arquitetura', due_date='08/04', first_added_date='2026-04-08'),
            Task(status='[~]', priority='🟡', description='Escrever documentação', progress_percent=50, progress_done=5, progress_total=10, unit='páginas', progress_bar='█████░░░░░', remaining_text='5 páginas', first_added_date='2026-03-20'),
            Task(status='[ ]', priority='🟢', description='Ligar dentista', first_added_date='2026-03-30'),
        ],
        brain_dumps=[BrainDumpEntry(id='dump-1', text='Trocar lâmpada', created_at='2026-04-08T10:00:00', due_date='10/04')],
        suggestion_135={
            'big': [SuggestedTask(task_id='1', title='Revisar arquitetura', score=38, size_category='big', explanation='prazo imediato')],
            'medium': [SuggestedTask(task_id='2', title='Responder emails', score=52, size_category='medium', explanation='prazo hoje')],
            'small': [SuggestedTask(task_id='3', title='Ligar dentista', score=41, size_category='small', explanation='rápida de executar')],
        },
        feedback_do_dia={
            'panorama': 'Manhã pesada, tarde livre.',
            'foco': 'Fechar proposta até 14h.',
            'alerta': 'Reunião de 16h ainda sem pauta.',
            'acao_sugerida': 'Bloqueie 2h agora pra proposta.',
        },
    )
    rendered = format_task_file_whatsapp(taskfile, date(2026, 4, 8))
    assert '📋 Tasks — 08/04/2026' in rendered
    assert '🔴 URGENTE (prazo hoje)' in rendered
    assert '🟡 EM ANDAMENTO' in rendered
    assert '[█████░░░░░] 50% (5/10 páginas)' in rendered
    assert '👻 ⏳ Escrever documentação' in rendered
    assert '⚠️ ▢ Ligar dentista' in rendered
    assert '🧠 BRAIN DUMP' in rendered
    assert '🎯 SUGESTÃO 1-3-5' in rendered
    assert '💬 Quer seguir essa sugestão?' in rendered
    # Feedback renderizado
    assert '💬 Da Vita' in rendered
    assert 'Panorama: Manhã pesada, tarde livre.' in rendered
    assert 'Foco: Fechar proposta até 14h.' in rendered
    assert '⚠️ Alerta: Reunião de 16h ainda sem pauta.' in rendered
    assert '→ Bloqueie 2h agora pra proposta.' in rendered
    # Feedback vem antes das seções de tasks
    assert rendered.index('💬 Da Vita') < rendered.index('🔴 URGENTE')
    print('✓ test_whatsapp_format')


def test_whatsapp_omits_incomplete_feedback():
    """Feedback incompleto não deve gerar seção no WhatsApp."""
    base_task = Task(status='[ ]', priority='🟡', description='Task teste', due_date='09/04', first_added_date='2026-04-08')
    today = date(2026, 4, 8)

    scenarios = [
        {},  # vazio
        {'panorama': 'Algo'},  # só 1 de 4
        {'panorama': 'X', 'foco': 'Y', 'alerta': 'Z'},  # 3 de 4
        {'panorama': 'X', 'foco': 'Y', 'alerta': 'Z', 'acao_sugerida': ''},  # 4 mas um vazio
    ]
    for feedback in scenarios:
        taskfile = TaskFile(
            title='Tasks — 08/04/2026',
            open_tasks=[base_task],
            feedback_do_dia=feedback,
        )
        rendered = format_task_file_whatsapp(taskfile, today)
        assert '💬 Da Vita' not in rendered, (
            f"Feedback incompleto não deveria renderizar. feedback={feedback}"
        )
    print('✓ test_whatsapp_omits_incomplete_feedback')


def test_whatsapp_renders_complete_feedback():
    """Feedback completo deve gerar seção no topo do WhatsApp."""
    base_task = Task(status='[ ]', priority='🟡', description='Task teste', due_date='09/04', first_added_date='2026-04-08')
    today = date(2026, 4, 8)
    feedback = {
        'panorama': 'Dia tranquilo.',
        'foco': 'Resolver bug.',
        'alerta': 'Deploy às 17h.',
        'acao_sugerida': 'Comece pelo bug agora.',
    }
    taskfile = TaskFile(
        title='Tasks — 08/04/2026',
        open_tasks=[base_task],
        feedback_do_dia=feedback,
    )
    rendered = format_task_file_whatsapp(taskfile, today)
    assert '💬 Da Vita' in rendered
    assert 'Panorama: Dia tranquilo.' in rendered
    assert 'Foco: Resolver bug.' in rendered
    assert '⚠️ Alerta: Deploy às 17h.' in rendered
    assert '→ Comece pelo bug agora.' in rendered
    # Ordem: título → feedback → tasks
    assert rendered.index('📋 Tasks') < rendered.index('💬 Da Vita')
    assert rendered.index('💬 Da Vita') < rendered.index('Task teste')
    print('✓ test_whatsapp_renders_complete_feedback')


def test_cli_render_whatsapp():
    """CLI render --format whatsapp deve gerar arquivo válido."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp) / 'data'
        output = Path(tmp) / 'out.txt'
        ledger_path = get_ledger_path(date(2026, 4, 8), 2026, data_dir)
        add_task(ledger_path, 'Revisar arquitetura', '🔴', '08/04', 2026, due_date='08/04')

        result = subprocess.run(
            [
                sys.executable, str(CLI_PATH), 'render',
                '--today', '08/04',
                '--year', '2026',
                '--data-dir', str(data_dir),
                '--output', str(output),
                '--format', 'whatsapp',
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        content = output.read_text(encoding='utf-8')
        assert payload['ok'] is True
        assert payload['format'] == 'whatsapp'
        assert '📋 Tasks — 08/04/2026' in content
        print('✓ test_cli_render_whatsapp')


def test_cli_check_wip():
    """CLI check-wip deve retornar JSON esperado."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp) / 'data'
        ledger_path = get_ledger_path(date(2026, 4, 8), 2026, data_dir)
        created = add_task(ledger_path, 'Task A', '🟡', '08/04', 2026)
        start_task(ledger_path, created['task_id'], '08/04')

        result = subprocess.run(
            [
                sys.executable, str(CLI_PATH), 'check-wip',
                '--today', '08/04',
                '--year', '2026',
                '--data-dir', str(data_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        assert payload['current_wip'] == 1
        assert payload['limit'] == 2
        assert payload['can_start'] is True
        assert 'warning' not in payload or payload['warning'] is None
        print('✓ test_cli_check_wip')


def _create_test_ledger_record(
    task_id: str,
    description: str,
    status: str = "[ ]",
    source: str = "manual",
    created_at: str = "2026-04-06T09:00:00",
    first_added_date: str = "2026-04-06",
    postpone_count: int = 0,
    completed_at: str | None = None,
) -> dict:
    """Helper: cria um registro de task para testes de execution_history."""
    record = {
        "type": "task",
        "id": task_id,
        "_operation": "create",
        "status": status,
        "priority": "🟡",
        "description": description,
        "source": source,
        "created_at": created_at,
        "first_added_date": first_added_date,
        "postpone_count": postpone_count,
    }
    if completed_at:
        record["completed_at"] = completed_at
    return record


def _write_jsonl(path: Path, records: list[dict]) -> None:
    """Helper: escreve registros como JSONL."""
    import json as _json
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(_json.dumps(r, ensure_ascii=False) + "\n")


def test_execution_history_basic():
    """build_execution_history retorna métricas corretas para dados conhecidos."""
    from ledger import get_ledger_filename, get_week_start

    today = date(2026, 4, 8)  # quarta-feira
    ws = get_week_start(today)  # 05/04 (domingo)

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)

        records = [
            _create_test_ledger_record("t1", "Task A", "[x]", "rotina", f"{ws}T09:00:00", str(ws), completed_at=f"{ws}T17:00:00"),
            _create_test_ledger_record("t2", "Task B", "[x]", "manual", f"{ws}T09:00:00", str(ws), completed_at=f"{ws}T18:00:00"),
            _create_test_ledger_record("t3", "Task C", "[ ]", "rotina", f"{ws}T09:00:00", str(ws)),
            _create_test_ledger_record("t4", "Task D", "[ ]", "manual", f"{ws}T09:00:00", "2026-03-15", postpone_count=3),
        ]
        _write_jsonl(ledger_file, records)

        history = build_execution_history(data_dir, today, weeks=1)

        # Completion rate: 2 de 4 = 50%
        assert history["weeks_analyzed"] == 1
        assert len(history["completion_rate"]["weekly"]) == 1
        week = history["completion_rate"]["weekly"][0]
        assert week["completed"] == 2
        assert week["total"] == 4
        assert week["rate"] == 0.5

        # By source
        by_source = {s["source"]: s for s in history["by_source"]}
        assert by_source["rotina"]["created"] == 2
        assert by_source["rotina"]["completed"] == 1
        assert by_source["manual"]["created"] == 2
        assert by_source["manual"]["completed"] == 1

        # Top postponed: só Task D (postpone_count=3)
        assert len(history["top_postponed"]) == 1
        assert history["top_postponed"][0]["description"] == "Task D"
        assert history["top_postponed"][0]["postpone_count"] == 3

        # By weekday: todas criadas no domingo (ws é domingo)
        by_day = {d["day"]: d for d in history["by_weekday"]}
        assert by_day["Domingo"]["sample"] == 4
        assert by_day["Domingo"]["rate"] == 0.5

        print('✓ test_execution_history_basic')


def test_execution_history_render_markdown():
    """render_markdown gera markdown com seções esperadas."""
    history = {
        "generated_at": "08/04/2026",
        "weeks_analyzed": 1,
        "completion_rate": {
            "weekly": [{"label": "Atual (05/04-11/04)", "completed": 3, "total": 5, "rate": 0.6}],
            "average": 0.6,
        },
        "by_source": [
            {"source": "manual", "created": 5, "completed": 3, "rate": 0.6},
        ],
        "top_postponed": [
            {"description": "Ligar dentista", "postpone_count": 4, "days_in_list": 20},
        ],
        "by_weekday": [
            {"day": "Domingo", "rate": 0.4, "sample": 5},
        ],
    }
    md = render_history_markdown(history)
    assert "Taxa de Conclusão Semanal" in md
    assert "Por Origem" in md
    assert "Tasks Mais Adiadas" in md
    assert "Desempenho por Dia da Semana" in md
    assert "Ligar dentista" in md
    assert "60%" in md  # average
    print('✓ test_execution_history_render_markdown')


def test_execution_history_write_preserves_observations():
    """write_history_file preserva seção de observações manuais."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        output = Path(tmp) / "historico-execucao.md"

        # Primeira escrita — cria do zero
        write_history_file(output, "Metrics v1\n")
        content = output.read_text(encoding="utf-8")
        assert "Metrics v1" in content
        assert "## Observações" in content

        # Adiciona anotação manual na seção de observações
        content = content.replace(
            "<!-- Espaço para anotações manuais. Não será sobrescrito pelo CLI. -->",
            "Nota importante do usuário",
        )
        output.write_text(content, encoding="utf-8")

        # Segunda escrita — atualiza métricas, preserva observações
        write_history_file(output, "Metrics v2\n")
        updated = output.read_text(encoding="utf-8")
        assert "Metrics v2" in updated
        assert "Metrics v1" not in updated
        assert "Nota importante do usuário" in updated

        print('✓ test_execution_history_write_preserves_observations')


def test_execution_history_cli():
    """CLI execution-history gera arquivo e retorna JSON ok."""
    from ledger import get_ledger_filename, get_week_start

    today = date(2026, 4, 8)
    ws = get_week_start(today)

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        records = [
            _create_test_ledger_record("t1", "Task CLI", "[x]", "manual", f"{ws}T09:00:00", str(ws), completed_at=f"{ws}T17:00:00"),
        ]
        _write_jsonl(ledger_file, records)

        output_path = Path(tmp) / "historico-execucao.md"
        result = subprocess.run(
            [
                sys.executable, str(CLI_PATH), 'execution-history',
                '--today', '08/04',
                '--year', '2026',
                '--data-dir', str(data_dir),
                '--output', str(output_path),
                '--weeks', '1',
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        assert payload['ok'] is True
        assert payload['weeks_analyzed'] == 1
        assert output_path.exists()

        content = output_path.read_text(encoding="utf-8")
        assert "Task CLI" not in content  # task description doesn't appear in general metrics
        assert "Taxa de Conclusão Semanal" in content

        print('✓ test_execution_history_cli')


def test_ledger_update_fields():
    """ledger-update deve alterar campos sem criar duplicata."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 12), 2026, data_dir)

        created = add_task(ledger_path, 'Encontrar contrato de aluguel', '🟡', '12/04', 2026, context='juridico')
        task_id = created['task_id']

        # Atualiza context
        result = update_task(ledger_path, task_id, '12/04', context='jurídico residencial')
        assert result['ok'] is True
        assert result['updated_fields'] == ['context']

        state = get_current_task_state(load_ledger(ledger_path), task_id)
        assert state['context'] == 'jurídico residencial'
        assert state['description'] == 'Encontrar contrato de aluguel'

        # Atualiza description e priority ao mesmo tempo
        result2 = update_task(ledger_path, task_id, '12/04', description='Encontrar contrato', priority='🔴')
        assert result2['ok'] is True
        assert set(result2['updated_fields']) == {'description', 'priority'}

        state2 = get_current_task_state(load_ledger(ledger_path), task_id)
        assert state2['description'] == 'Encontrar contrato'
        assert state2['priority'] == '🔴'
        assert state2['context'] == 'jurídico residencial'  # intacto

        print('✓ test_ledger_update_fields')


def test_ledger_update_not_found():
    """ledger-update em task inexistente retorna erro."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 12), 2026, data_dir)

        result = update_task(ledger_path, 'inexistente_123', '12/04', description='Nova')
        assert result['ok'] is False
        assert 'não encontrada' in result['error'].lower() or 'não encontrada' in result['error']

        print('✓ test_ledger_update_not_found')


def test_ledger_update_no_fields():
    """ledger-update sem campos retorna erro."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 12), 2026, data_dir)

        add_task(ledger_path, 'Task qualquer', '🟡', '12/04', 2026)

        result = update_task(ledger_path, '20260412_task_qualquer', '12/04')
        assert result['ok'] is False
        assert 'nenhum campo' in result['error'].lower()

        print('✓ test_ledger_update_no_fields')


def test_ledger_update_cli():
    """CLI ledger-update deve funcionar via subprocess."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 12), 2026, data_dir)

        add_task(ledger_path, 'Avaliar contrato', '🟡', '12/04', 2026, context='juridico')

        result = subprocess.run(
            [
                sys.executable, str(CLI_PATH), 'ledger-update',
                '--task-id', '20260412_avaliar_contrato',
                '--context', 'jurídico residencial',
                '--today', '12/04',
                '--year', '2026',
                '--data-dir', str(data_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        assert payload['ok'] is True
        assert 'context' in payload['updated_fields']

        state = get_current_task_state(load_ledger(ledger_path), '20260412_avaliar_contrato')
        assert state['context'] == 'jurídico residencial'
        assert state['description'] == 'Avaliar contrato'

        print('✓ test_ledger_update_cli')


def test_duplicate_detection_warns():
    """add_task emite warning quando descrição é similar a task aberta."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 12), 2026, data_dir)

        add_task(ledger_path, 'Encontrar contrato de aluguel', '🟡', '12/04', 2026, context='juridico')

        # Descrição similar (subset de palavras)
        result = add_task(ledger_path, 'Encontrar contrato', '🟡', '12/04', 2026, context='juridico residencial')
        assert result['ok'] is True
        assert 'warning' in result, "Deveria emitir warning de duplicata"
        assert result['warning']['type'] == 'duplicate_suspect'
        assert len(result['warning']['similar_to']) >= 1
        assert result['warning']['similar_to'][0]['description'] == 'Encontrar contrato de aluguel'

        print('✓ test_duplicate_detection_warns')


def test_duplicate_detection_allow_flag():
    """add_task com allow_duplicate=True suprime warning."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 12), 2026, data_dir)

        add_task(ledger_path, 'Ligar para João', '🟡', '12/04', 2026)

        result = add_task(ledger_path, 'Ligar para João', '🟡', '12/04', 2026, allow_duplicate=True)
        assert result['ok'] is True
        assert 'warning' not in result

        print('✓ test_duplicate_detection_allow_flag')


def test_duplicate_detection_no_false_positive():
    """add_task não emite warning para tasks totalmente diferentes."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 12), 2026, data_dir)

        add_task(ledger_path, 'Encontrar contrato de aluguel', '🟡', '12/04', 2026)

        # Descrição totalmente diferente
        result = add_task(ledger_path, 'Comprar café', '🟢', '12/04', 2026)
        assert result['ok'] is True
        assert 'warning' not in result

        print('✓ test_duplicate_detection_no_false_positive')


def test_duplicate_detection_accent_normalization():
    """Detecção normaliza acentos: 'jurídico' e 'juridico' são iguais."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 12), 2026, data_dir)

        add_task(ledger_path, 'Avaliar contrato de aluguel', '🟡', '12/04', 2026)

        # Mesma task mas com acento diferente e palavras a menos
        result = add_task(ledger_path, 'Avaliar contrato', '🟡', '12/04', 2026)
        assert result['ok'] is True
        assert 'warning' in result, (
            "Deveria detectar 'Avaliar contrato' como similar a 'Avaliar contrato de aluguel'"
        )

        print('✓ test_duplicate_detection_accent_normalization')


def test_duplicate_detection_ignores_completed():
    """Detecção ignora tasks já concluídas."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 12), 2026, data_dir)

        created = add_task(ledger_path, 'Encontrar contrato', '🟡', '12/04', 2026)
        complete_task(ledger_path, created['task_id'], '12/04')

        # Mesma descrição, mas a anterior foi concluída
        result = add_task(ledger_path, 'Encontrar contrato', '🟡', '12/04', 2026)
        assert result['ok'] is True
        assert 'warning' not in result, "Não deveria alertar sobre task já concluída"

        print('✓ test_duplicate_detection_ignores_completed')


def test_rollover_on_sunday():
    """Rollover funciona normalmente quando chamado no domingo."""
    from ledger import get_ledger_filename, get_week_start

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        hist = data_dir / "historico"
        hist.mkdir()

        # Semana anterior: 05/04 (dom) a 11/04 (sáb)
        last_sunday = date(2026, 4, 5)
        old_ledger = hist / get_ledger_filename(last_sunday)
        records = [
            _create_test_ledger_record("t1", "Task pendente", "[ ]", "manual", "2026-04-06T09:00:00", "2026-04-06"),
            _create_test_ledger_record("t2", "Task concluída", "[x]", "manual", "2026-04-06T09:00:00", "2026-04-06", completed_at="2026-04-07T17:00:00"),
            _create_test_ledger_record("t3", "Task em andamento", "[~]", "manual", "2026-04-08T09:00:00", "2026-04-08"),
        ]
        _write_jsonl(old_ledger, records)

        # Domingo 12/04 — início da semana nova
        today = date(2026, 4, 12)
        result = perform_rollover(data_dir, today, 2026)

        assert result["performed"] is True
        assert result["carried_over"] == 2, f"Esperava 2 tasks carregadas, recebeu {result['carried_over']}"

        descriptions = {t["description"] for t in result["tasks"]}
        assert "Task pendente" in descriptions
        assert "Task em andamento" in descriptions
        assert "Task concluída" not in descriptions

        # Verifica que novo ledger foi criado
        new_ledger = hist / get_ledger_filename(today)
        assert new_ledger.exists(), f"Novo ledger deveria existir: {new_ledger}"

        print("✓ test_rollover_on_sunday")


def test_rollover_missed_sunday():
    """Rollover funciona quando chamado na segunda (domingo foi perdido)."""
    from ledger import get_ledger_filename, get_week_start

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        hist = data_dir / "historico"
        hist.mkdir()

        # Semana anterior: 05/04 a 11/04
        last_sunday = date(2026, 4, 5)
        old_ledger = hist / get_ledger_filename(last_sunday)
        records = [
            _create_test_ledger_record("t1", "Ligar pro dentista", "[ ]", "manual", "2026-04-07T09:00:00", "2026-04-07", postpone_count=2),
            _create_test_ledger_record("t2", "Revisar e-mails", "[x]", "rotina", "2026-04-06T08:00:00", "2026-04-06", completed_at="2026-04-06T10:00:00"),
        ]
        _write_jsonl(old_ledger, records)

        # Segunda-feira 13/04 — pipeline não rodou no domingo
        today = date(2026, 4, 13)
        result = perform_rollover(data_dir, today, 2026)

        assert result["performed"] is True, "Rollover deveria executar mesmo na segunda"
        assert result["carried_over"] == 1
        assert result["tasks"][0]["description"] == "Ligar pro dentista"

        # Verifica que o novo ledger pertence à semana certa (12/04-18/04)
        new_sunday = get_week_start(today)  # 12/04
        new_ledger = hist / get_ledger_filename(new_sunday)
        assert new_ledger.exists(), f"Ledger da semana 12-18/04 deveria existir"

        # postpone_count deve ter incrementado
        new_records = load_ledger(new_ledger)
        carried_task = [r for r in new_records if r.get("description") == "Ligar pro dentista"][0]
        assert carried_task["postpone_count"] == 3, f"postpone_count deveria ser 3, é {carried_task['postpone_count']}"

        print("✓ test_rollover_missed_sunday")


def test_rollover_no_duplicate():
    """Rollover não re-executa tasks que já foram migradas."""
    from ledger import get_ledger_filename

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        hist = data_dir / "historico"
        hist.mkdir()

        # Semana anterior com 1 task + marca de rollover já feito
        last_sunday = date(2026, 4, 5)
        old_ledger = hist / get_ledger_filename(last_sunday)
        _write_jsonl(old_ledger, [
            _create_test_ledger_record("t1", "Task X", "[ ]"),
            {"type": "task", "id": "t1", "_operation": "rollover",
             "carried_to": "t1_new", "rolled_at": "ledger_new"},
        ])

        # Ledger da semana nova já existe
        new_sunday = date(2026, 4, 12)
        new_ledger = hist / get_ledger_filename(new_sunday)
        _write_jsonl(new_ledger, [
            _create_test_ledger_record("t1_new", "Task X (carried)", "[ ]"),
        ])

        # Chama rollover — deve ser no-op (task já migrada)
        result = perform_rollover(data_dir, date(2026, 4, 14), 2026)
        assert result["performed"] is False
        assert result["carried_over"] == 0

        # Novo ledger não deve ter records duplicados
        new_records = load_ledger(new_ledger)
        assert len(new_records) == 1, "Não deveria duplicar tasks no rollover"

        print("✓ test_rollover_no_duplicate")


def test_rollover_late_migration():
    """Rollover migra tasks pendentes mesmo quando ledger da semana já existe."""
    from ledger import get_ledger_filename

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        hist = data_dir / "historico"
        hist.mkdir()

        # Semana anterior com 2 tasks abertas
        last_sunday = date(2026, 4, 5)
        old_ledger = hist / get_ledger_filename(last_sunday)
        _write_jsonl(old_ledger, [
            _create_test_ledger_record("t1", "Task A", "[ ]"),
            _create_test_ledger_record("t2", "Task B", "[~]"),
        ])

        # Ledger da semana nova já existe (pipeline rodou antes do rollover)
        new_sunday = date(2026, 4, 12)
        new_ledger = hist / get_ledger_filename(new_sunday)
        _write_jsonl(new_ledger, [
            _create_test_ledger_record("t3", "Task C (criada esta semana)", "[ ]"),
        ])

        # Rollover deve migrar t1 e t2 mesmo com ledger existente
        result = perform_rollover(data_dir, date(2026, 4, 14), 2026)
        assert result["performed"] is True, "Deveria migrar tasks pendentes"
        assert result["carried_over"] == 2, f"Esperava 2 migradas, got {result['carried_over']}"

        # Novo ledger deve ter 3 records: t3 original + 2 migradas
        new_records = load_ledger(new_ledger)
        assert len(new_records) == 3, f"Esperava 3 records, got {len(new_records)}"

        # Verifica que tasks migradas têm carried_from
        migrated = [r for r in new_records if r.get("carried_from")]
        assert len(migrated) == 2, "Deveria ter 2 tasks com carried_from"

        # Verifica que old ledger tem marcas de rollover
        old_records = load_ledger(old_ledger)
        rollover_marks = [r for r in old_records if r.get("_operation") == "rollover"]
        assert len(rollover_marks) == 2, "Deveria ter 2 marcas de rollover no ledger antigo"

        # Segundo rollover deve ser no-op (tudo já migrado)
        result2 = perform_rollover(data_dir, date(2026, 4, 15), 2026)
        assert result2["performed"] is False
        assert result2["carried_over"] == 0

        print("✓ test_rollover_late_migration")


def test_rollover_carries_pending_dumps(tmp_path):
    """Dump não convertido deve ser migrado para o novo ledger."""
    from scripts.ledger import append_record, get_ledger_path, get_week_start
    from scripts.rollover import perform_rollover
    from datetime import date, timedelta
    import json

    today = date.today()
    last_sunday = get_week_start(today) - timedelta(days=7)
    data_dir = tmp_path

    old_ledger_path = get_ledger_path(last_sunday, today.year, data_dir)
    old_ledger_path.parent.mkdir(parents=True, exist_ok=True)

    # Cria um dump pendente no ledger antigo
    append_record(old_ledger_path, {
        "type": "dump",
        "id": f"{last_sunday:%Y%m%d}_dump_001",
        "text": "Lembrar de ligar pro dentista",
        "created_at": last_sunday.isoformat(),
    })

    result = perform_rollover(data_dir, today, today.year)

    assert result["performed"] is True
    assert result["dumps_carried_over"] == 1

    new_ledger_path = get_ledger_path(get_week_start(today), today.year, data_dir)
    records = [json.loads(l) for l in new_ledger_path.read_text().splitlines() if l.strip()]
    dump_records = [r for r in records if r.get("type") == "dump"]

    assert len(dump_records) == 1
    assert dump_records[0]["text"] == "Lembrar de ligar pro dentista"
    assert dump_records[0]["carried_from_dump"] == f"{last_sunday:%Y%m%d}_dump_001"

    print("✓ test_rollover_carries_pending_dumps")


def test_rollover_skips_converted_dumps(tmp_path):
    """Dump já convertido em task não deve ser migrado."""
    from scripts.ledger import append_record, get_ledger_path, get_week_start
    from scripts.rollover import perform_rollover
    from datetime import date, timedelta
    import json

    today = date.today()
    last_sunday = get_week_start(today) - timedelta(days=7)
    data_dir = tmp_path

    old_ledger_path = get_ledger_path(last_sunday, today.year, data_dir)
    old_ledger_path.parent.mkdir(parents=True, exist_ok=True)

    dump_id = f"{last_sunday:%Y%m%d}_dump_001"

    # Cria dump e marca como convertido
    append_record(old_ledger_path, {
        "type": "dump",
        "id": dump_id,
        "text": "Comprar leite",
        "created_at": last_sunday.isoformat(),
    })
    append_record(old_ledger_path, {
        "type": "dump",
        "id": dump_id,
        "_operation": "convert",
        "converted_to_task": "20240101_comprar_leite",
        "converted_at": last_sunday.isoformat(),
    })

    result = perform_rollover(data_dir, today, today.year)

    assert result["dumps_carried_over"] == 0

    new_ledger_path = get_ledger_path(get_week_start(today), today.year, data_dir)
    if new_ledger_path.exists():
        records = [json.loads(l) for l in new_ledger_path.read_text().splitlines() if l.strip()]
        dump_records = [r for r in records if r.get("type") == "dump"]
        assert len(dump_records) == 0

    print("✓ test_rollover_skips_converted_dumps")


def test_word_weights_basic():
    """build_word_weights gera pesos com 3 fatores combinados."""
    from ledger import get_ledger_filename, get_week_start

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        hist = data_dir / "historico"
        hist.mkdir()

        sunday = date(2026, 4, 5)
        ledger_file = hist / get_ledger_filename(sunday)

        # Cria corpus com padrões distintos:
        # "reuniao" = rápida, sempre concluída → peso baixo
        # "dentista" = lenta, raramente concluída, muito adiada → peso alto
        records = []
        for i in range(10):
            # 10 reuniões, todas concluídas em 30min
            records.append({
                "type": "task", "id": f"reuniao_{i}", "_operation": "create",
                "status": "[x]", "priority": "🟢",
                "description": f"Reunião com equipe {i}",
                "source": "rotina", "created_at": f"2026-04-0{min(i+5,9)}T09:00:00",
                "completed_at": f"2026-04-0{min(i+5,9)}T09:30:00",
                "first_added_date": "2026-04-05", "postpone_count": 0,
            })
        for i in range(5):
            # 5 tentativas de "dentista", só 1 concluída (depois de 5 dias)
            status = "[x]" if i == 0 else "[ ]"
            completed = "2026-04-10T17:00:00" if i == 0 else None
            rec = {
                "type": "task", "id": f"dentista_{i}", "_operation": "create",
                "status": status, "priority": "🔴",
                "description": "Ligar pro dentista",
                "source": "manual", "created_at": f"2026-04-0{min(i+5,9)}T09:00:00",
                "first_added_date": "2026-04-05",
                "postpone_count": 3,
            }
            if completed:
                rec["completed_at"] = completed
            records.append(rec)

        _write_jsonl(ledger_file, records)

        ww = build_word_weights(data_dir, date(2026, 4, 11), weeks=1, min_corpus=5)

        assert ww["corpus_size"] >= 10
        assert "weights" in ww
        weights = ww["weights"]

        # "dentista" deve ter peso MUITO maior que "reuniao"
        assert "dentista" in weights, f"'dentista' não encontrada nos pesos: {list(weights.keys())}"
        assert "reuniao" in weights, f"'reuniao' não encontrada nos pesos: {list(weights.keys())}"
        assert weights["dentista"] > weights["reuniao"] * 2, (
            f"dentista ({weights['dentista']}) deveria ter pelo menos 2x o peso de "
            f"reuniao ({weights['reuniao']})"
        )

        print("✓ test_word_weights_basic")


def test_word_weights_min_corpus():
    """build_word_weights retorna vazio se corpus insuficiente."""
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        (data_dir / "historico").mkdir()

        ww = build_word_weights(data_dir, date(2026, 4, 11), weeks=1, min_corpus=50)
        assert ww["weights"] == {}
        assert "reason" in ww

        print("✓ test_word_weights_min_corpus")


def test_word_weights_write_and_load():
    """write_word_weights e load_word_weights fazem round-trip correto."""
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)

        ww = {
            "generated_at": "2026-04-12T00:00:00",
            "corpus_size": 100,
            "completed_count": 75,
            "word_count": 3,
            "weights": {"dentista": 12.5, "reuniao": 1.3, "email": 0.9},
        }

        path = write_word_weights(data_dir, ww)
        assert path.exists()

        loaded = load_word_weights(data_dir)
        assert loaded["dentista"] == 12.5
        assert loaded["reuniao"] == 1.3
        assert loaded["email"] == 0.9

        print("✓ test_word_weights_write_and_load")


def test_weighted_similarity_changes_outcome():
    """Pesos mudam o resultado da detecção de duplicatas."""
    from ledger_ops import _weighted_similarity, _extract_words

    # Sem pesos: "Ligar pro banco" vs "Ligar pro dentista"
    # overlap = {ligar}, words_a = {ligar, banco}, words_b = {ligar, dentista}
    # ratio = 1/2 = 0.5 → match!
    words_a = _extract_words("Ligar pro banco")
    words_b = _extract_words("Ligar pro dentista")

    # Sem pesos (peso 1.0 pra tudo)
    sim_no_weight = _weighted_similarity(words_a, words_b, {})
    assert sim_no_weight >= 0.5, f"Sem peso deveria ser >= 0.5, é {sim_no_weight}"

    # Com pesos: "ligar" vale pouco, "dentista" e "banco" valem muito
    weights = {"ligar": 1.0, "banco": 10.0, "dentista": 12.0}
    sim_weighted = _weighted_similarity(words_a, words_b, weights)
    assert sim_weighted < 0.5, (
        f"Com pesos deveria ser < 0.5 (ligar=1 vs banco=10+ligar=1), é {sim_weighted}"
    )

    # "Ligar pro dentista" vs "Ligar pro dentista" — sempre match
    sim_exact = _weighted_similarity(words_b, words_b, weights)
    assert sim_exact >= 0.99, f"Match exato deveria ser ~1.0, é {sim_exact}"

    print("✓ test_weighted_similarity_changes_outcome")


def test_ledger_status_cli():
    """ledger-status retorna diagnóstico correto via CLI."""
    from ledger import get_ledger_filename, get_week_start

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        hist = data_dir / "historico"
        hist.mkdir()

        # Semana anterior com tasks pendentes
        last_sunday = date(2026, 4, 5)
        old_ledger = hist / get_ledger_filename(last_sunday)
        _write_jsonl(old_ledger, [
            _create_test_ledger_record("t1", "Task pendente", "[ ]"),
            _create_test_ledger_record("t2", "Task feita", "[x]", completed_at="2026-04-07T17:00:00"),
        ])

        # Sem ledger da semana atual — rollover pendente
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "ledger-status",
             "--today", "13/04", "--year", "2026", "--data-dir", str(data_dir)],
            capture_output=True, text=True,
            env={**__import__('os').environ, "VITA_TEST_MODE": "1"},
        )
        assert result.returncode == 0, f"CLI falhou: {result.stderr}"
        status = json.loads(result.stdout)

        assert status["current_week"]["exists"] is False
        assert status["previous_week"]["exists"] is True
        assert status["previous_ledger"]["pending_tasks"] == 1
        assert status["previous_ledger"]["needs_rollover"] is True
        assert len(status["issues"]) > 0
        assert status["healthy"] is False

        print("✓ test_ledger_status_cli")


def test_detect_recurrence_daily_pattern():
    """_detect_pattern identifica padrão diário (>= 5 dias diferentes)."""
    from datetime import date

    # 7 datas cobrindo 5+ dias diferentes da semana
    dates = [
        date(2026, 4, 6),   # Monday
        date(2026, 4, 7),   # Tuesday
        date(2026, 4, 8),   # Wednesday
        date(2026, 4, 9),   # Thursday
        date(2026, 4, 10),  # Friday
        date(2026, 4, 11),  # Saturday
        date(2026, 4, 12),  # Sunday
    ]
    pattern, weekdays = _detect_pattern(dates)
    assert pattern == "daily", f"Esperava 'daily', recebeu '{pattern}'"
    assert weekdays == [0, 1, 2, 3, 4, 5, 6]
    print("✓ test_detect_recurrence_daily_pattern")


def test_detect_recurrence_weekly_pattern():
    """_detect_pattern identifica padrão semanal (1-3 dias concentram >= 80%)."""
    from datetime import date

    # Sempre segunda-feira (weekday=0)
    dates = [
        date(2026, 3, 16),  # Monday
        date(2026, 3, 23),  # Monday
        date(2026, 3, 30),  # Monday
        date(2026, 4, 6),   # Monday
        date(2026, 4, 8),   # Wednesday (outlier)
    ]
    pattern, weekdays = _detect_pattern(dates)
    assert pattern == "weekly", f"Esperava 'weekly', recebeu '{pattern}'"
    assert 0 in weekdays, f"Monday (0) deveria estar em weekdays: {weekdays}"
    print("✓ test_detect_recurrence_weekly_pattern")


def test_detect_recurrence_no_clear_pattern():
    """_detect_pattern retorna None quando não há padrão claro."""
    from datetime import date

    # 4 dias diferentes, nenhum concentra >= 80%
    dates = [
        date(2026, 4, 6),   # Monday
        date(2026, 4, 7),   # Tuesday
        date(2026, 4, 8),   # Wednesday
        date(2026, 4, 9),   # Thursday
    ]
    pattern, weekdays = _detect_pattern(dates)
    assert pattern is None, f"Esperava None, recebeu '{pattern}'"
    assert weekdays == []
    print("✓ test_detect_recurrence_no_clear_pattern")


def test_detect_time_mode():
    """_detect_time_mode extrai horário predominante."""
    tasks = [
        {"context": "09:00"},
        {"context": "09:00"},
        {"context": "09:00"},
        {"context": "14:00"},
        {"context": None},
    ]
    time = _detect_time_mode(tasks)
    assert time == "09:00", f"Esperava '09:00', recebeu '{time}'"

    # Sem predominância
    tasks_mixed = [
        {"context": "09:00"},
        {"context": "14:00"},
        {"context": "18:00"},
    ]
    time_mixed = _detect_time_mode(tasks_mixed)
    assert time_mixed is None, f"Esperava None, recebeu '{time_mixed}'"
    print("✓ test_detect_time_mode")


def test_detect_recurrence_skips_already_rule():
    """detect_recurrence_candidates ignora tasks que já têm regra ativa."""
    from ledger import get_ledger_filename, get_week_start

    today = date(2026, 4, 13)
    ws = get_week_start(today)

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)

        # Cria 6 tasks "Tomar remédios" concluídas em 6 dias diferentes → daily
        records = []
        for i in range(6):
            d = date(2026, 4, 6 + i)
            records.append({
                "type": "task", "id": f"remedios_{i}", "_operation": "create",
                "status": "[x]", "priority": "🟢",
                "description": "Tomar remédios",
                "source": "manual",
                "created_at": f"{d}T08:00:00",
                "completed_at": f"{d}T08:05:00",
                "first_added_date": str(d),
                "postpone_count": 0,
            })
        # Regra ativa para "Tomar remédios"
        records.append({
            "type": "recurrence_rule", "id": "rule_20260413_tomar_remedios",
            "_operation": "create",
            "description": "Tomar remédios",
            "pattern": "daily", "weekdays": [0,1,2,3,4,5,6],
            "priority": "🟢",
        })
        _write_jsonl(ledger_file, records)

        candidates = detect_recurrence_candidates(data_dir, today, min_occurrences=3, lookback_weeks=2)
        descs = [c["description"] for c in candidates]
        assert "Tomar remédios" not in descs, "Não deveria sugerir task que já tem regra ativa"
        print("✓ test_detect_recurrence_skips_already_rule")


def test_detect_recurrence_skips_rotina_source():
    """detect_recurrence_candidates ignora tasks de fonte rotina."""
    from ledger import get_ledger_filename, get_week_start

    today = date(2026, 4, 13)

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)

        records = []
        for i in range(6):
            d = date(2026, 4, 6 + i)
            records.append({
                "type": "task", "id": f"rotina_{i}", "_operation": "create",
                "status": "[x]", "priority": "🟢",
                "description": "Meditação 10min",
                "source": "rotina",
                "created_at": f"{d}T06:00:00",
                "completed_at": f"{d}T06:15:00",
                "first_added_date": str(d),
                "postpone_count": 0,
            })
        _write_jsonl(ledger_file, records)

        candidates = detect_recurrence_candidates(data_dir, today, min_occurrences=3, lookback_weeks=2)
        descs = [c["description"] for c in candidates]
        assert "Meditação 10min" not in descs, "Não deveria sugerir task de rotina"
        print("✓ test_detect_recurrence_skips_rotina_source")


def test_activate_and_get_active_rules():
    """activate_recurrence_rule cria regra e get_active_recurrence_rules a retorna."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 13), 2026, data_dir)

        result = activate_recurrence_rule(
            ledger_path=ledger_path,
            description="Tomar remédios",
            pattern="daily",
            weekdays=[0,1,2,3,4,5,6],
            priority="🟢",
            time_range="08:00",
            today_ddmm="13/04",
            year=2026,
        )
        assert result["ok"] is True
        assert result["rule_id"].startswith("rule_20260413_")

        ledger = load_ledger(ledger_path)
        rules = get_active_recurrence_rules(ledger)
        assert len(rules) == 1
        assert rules[0]["description"] == "Tomar remédios"
        assert rules[0]["pattern"] == "daily"
        print("✓ test_activate_and_get_active_rules")


def test_deactivate_rule_is_not_destructive():
    """deactivate_recurrence_rule appenda, não remove. Regra some do get_active."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 13), 2026, data_dir)

        created = activate_recurrence_rule(
            ledger_path=ledger_path,
            description="Estudar inglês",
            pattern="weekly",
            weekdays=[0, 2, 4],
            priority="🟡",
            time_range=None,
            today_ddmm="13/04",
            year=2026,
        )
        rule_id = created["rule_id"]

        result = deactivate_recurrence_rule(
            ledger_path=ledger_path,
            rule_id=rule_id,
            reason="Não faz mais sentido",
            today_ddmm="13/04",
        )
        assert result["ok"] is True
        assert result["deactivated"] is True

        # Regra não aparece mais nas ativas
        ledger = load_ledger(ledger_path)
        rules = get_active_recurrence_rules(ledger)
        assert len(rules) == 0

        # Mas os registros estão no ledger (append-only)
        rule_records = [r for r in ledger if r.get("type") == "recurrence_rule"]
        assert len(rule_records) == 2  # create + deactivate
        print("✓ test_deactivate_rule_is_not_destructive")


def test_deactivate_rule_not_found():
    """deactivate_recurrence_rule retorna erro para regra inexistente."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_path = get_ledger_path(date(2026, 4, 13), 2026, data_dir)
        # Create empty ledger
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.touch()

        result = deactivate_recurrence_rule(
            ledger_path=ledger_path,
            rule_id="rule_inexistente",
            reason="Teste",
            today_ddmm="13/04",
        )
        assert result["ok"] is False
        assert "não encontrada" in result["error"].lower()
        print("✓ test_deactivate_rule_not_found")


def test_get_rules_for_weekday():
    """get_rules_for_weekday filtra corretamente por dia da semana."""
    rules = [
        {"id": "r1", "pattern": "daily", "description": "Diária"},
        {"id": "r2", "pattern": "weekly", "weekdays": [0, 2, 4], "description": "Seg/Qua/Sex"},
        {"id": "r3", "pattern": "weekly", "weekdays": [1, 3], "description": "Ter/Qui"},
    ]

    # Monday (weekday=0): daily + r2
    monday_rules = get_rules_for_weekday(rules, 0)
    ids = [r["id"] for r in monday_rules]
    assert "r1" in ids
    assert "r2" in ids
    assert "r3" not in ids

    # Tuesday (weekday=1): daily + r3
    tuesday_rules = get_rules_for_weekday(rules, 1)
    ids = [r["id"] for r in tuesday_rules]
    assert "r1" in ids
    assert "r3" in ids
    assert "r2" not in ids

    # Sunday (weekday=6): daily only
    sunday_rules = get_rules_for_weekday(rules, 6)
    ids = [r["id"] for r in sunday_rules]
    assert ids == ["r1"]
    print("✓ test_get_rules_for_weekday")


def test_sync_fixed_injects_recurrence_rules():
    """sync_fixed_agenda injeta tasks de regras de recorrência ativas."""
    rotina_content = """# Rotina

## Tarefas Diárias
- 06:00 | Meditação
"""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        rotina_path = data_dir / "rotina.md"
        rotina_path.write_text(rotina_content, encoding="utf-8")

        # Monday 13/04/2026 (weekday=0)
        ledger_path = get_ledger_path(date(2026, 4, 13), 2026, data_dir)

        # Ativa regra diária
        activate_recurrence_rule(
            ledger_path=ledger_path,
            description="Tomar remédios",
            pattern="daily",
            weekdays=[0,1,2,3,4,5,6],
            priority="🟢",
            time_range="08:00",
            today_ddmm="13/04",
            year=2026,
        )

        result = sync_fixed_agenda(rotina_path, ledger_path, "13/04", 2026)
        assert result["ok"] is True
        assert "Meditação" in result["inserted"]
        assert "Tomar remédios" in result["inserted"]
        assert result["sources"]["rotina"]["inserted"] == 1
        assert result["sources"]["recurrence"]["inserted"] == 1

        # Idempotência: segunda sync não duplica
        result2 = sync_fixed_agenda(rotina_path, ledger_path, "13/04", 2026)
        assert result2["sources"]["rotina"]["skipped"] == 1
        assert result2["sources"]["recurrence"]["skipped"] == 1
        assert result2["sources"]["rotina"]["inserted"] == 0
        assert result2["sources"]["recurrence"]["inserted"] == 0
        print("✓ test_sync_fixed_injects_recurrence_rules")


def test_sync_fixed_weekly_respects_weekday():
    """sync_fixed_agenda só injeta regra weekly no dia correto."""
    rotina_content = """# Rotina

## Tarefas Diárias
- 06:00 | Acordar
"""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        rotina_path = data_dir / "rotina.md"
        rotina_path.write_text(rotina_content, encoding="utf-8")

        # Monday 13/04/2026 (weekday=0)
        ledger_path = get_ledger_path(date(2026, 4, 13), 2026, data_dir)

        # Regra só para terça e quinta (weekdays=[1, 3])
        activate_recurrence_rule(
            ledger_path=ledger_path,
            description="Inglês",
            pattern="weekly",
            weekdays=[1, 3],
            priority="🟡",
            time_range=None,
            today_ddmm="13/04",
            year=2026,
        )

        # Sync na segunda — regra não se aplica
        result = sync_fixed_agenda(rotina_path, ledger_path, "13/04", 2026)
        assert result["sources"]["recurrence"]["inserted"] == 0, (
            "Regra de terça/quinta não deveria ser injetada na segunda"
        )

        # Sync na terça 14/04 — regra se aplica
        ledger_path_tue = get_ledger_path(date(2026, 4, 14), 2026, data_dir)
        # Copia a regra pro ledger da terça (mesma semana, mesmo arquivo)
        result_tue = sync_fixed_agenda(rotina_path, ledger_path_tue, "14/04", 2026)
        assert "Inglês" in result_tue["inserted"], (
            f"Regra deveria ser injetada na terça. inserted={result_tue['inserted']}"
        )
        assert result_tue["sources"]["recurrence"]["inserted"] == 1
        print("✓ test_sync_fixed_weekly_respects_weekday")


def test_cli_recurrence_detect():
    """CLI recurrence-detect retorna JSON esperado."""
    from ledger import get_ledger_filename

    today = date(2026, 4, 13)

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)

        # Cria 6 tasks "Comprar café" em 6 dias diferentes
        records = []
        for i in range(6):
            d = date(2026, 4, 6 + i)
            records.append({
                "type": "task", "id": f"cafe_{i}", "_operation": "create",
                "status": "[x]", "priority": "🟢",
                "description": "Comprar café",
                "source": "manual",
                "created_at": f"{d}T10:00:00",
                "completed_at": f"{d}T10:30:00",
                "first_added_date": str(d),
                "postpone_count": 0,
            })
        _write_jsonl(ledger_file, records)

        result = subprocess.run(
            [
                sys.executable, str(CLI_PATH), "recurrence-detect",
                "--today", "13/04", "--year", "2026",
                "--data-dir", str(data_dir),
                "--min-occurrences", "3",
                "--weeks", "2",
            ],
            capture_output=True, text=True,
            env={**__import__("os").environ, "VITA_TEST_MODE": "1"},
        )
        assert result.returncode == 0, f"CLI falhou: {result.stderr}"
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["count"] >= 1
        assert any(c["description"] == "Comprar café" for c in payload["candidates"])
        print("✓ test_cli_recurrence_detect")


def test_cli_recurrence_activate_and_deactivate():
    """CLI recurrence-activate e recurrence-deactivate funcionam end-to-end."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        env = {**__import__("os").environ, "VITA_TEST_MODE": "1"}

        # Activate
        result = subprocess.run(
            [
                sys.executable, str(CLI_PATH), "recurrence-activate",
                "--description", "Estudar Python",
                "--pattern", "weekly",
                "--weekdays", "[0,2,4]",
                "--priority", "🟡",
                "--today", "13/04", "--year", "2026",
                "--data-dir", str(data_dir),
            ],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0, f"Activate falhou: {result.stderr}"
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        rule_id = payload["rule_id"]

        # List
        result = subprocess.run(
            [
                sys.executable, str(CLI_PATH), "recurrence-list",
                "--today", "13/04", "--year", "2026",
                "--data-dir", str(data_dir),
            ],
            capture_output=True, text=True, env=env,
        )
        list_payload = json.loads(result.stdout)
        assert list_payload["count"] == 1
        assert list_payload["rules"][0]["description"] == "Estudar Python"

        # Deactivate
        result = subprocess.run(
            [
                sys.executable, str(CLI_PATH), "recurrence-deactivate",
                "--rule-id", rule_id,
                "--reason", "Mudou de prioridade",
                "--today", "13/04", "--year", "2026",
                "--data-dir", str(data_dir),
            ],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0, f"Deactivate falhou: {result.stderr}"
        deact_payload = json.loads(result.stdout)
        assert deact_payload["ok"] is True
        assert deact_payload["deactivated"] is True

        # List again — should be empty
        result = subprocess.run(
            [
                sys.executable, str(CLI_PATH), "recurrence-list",
                "--today", "13/04", "--year", "2026",
                "--data-dir", str(data_dir),
            ],
            capture_output=True, text=True, env=env,
        )
        final_payload = json.loads(result.stdout)
        assert final_payload["count"] == 0
        print("✓ test_cli_recurrence_activate_and_deactivate")


def test_daily_tick_success():
    """daily-tick com ambos sub-steps ok retorna JSON agregado com ok=True."""
    rotina_content = """# Rotina

## Tarefas Diárias
- 06:00 | Meditação
"""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        rotina_path = data_dir / "rotina.md"
        rotina_path.write_text(rotina_content, encoding="utf-8")
        output = Path(tmp) / "diarias.txt"
        history_output = Path(tmp) / "historico-execucao.md"
        ledger_path = get_ledger_path(date(2026, 4, 13), 2026, data_dir)
        add_task(ledger_path, "Task teste tick", "🟡", "13/04", 2026)

        result = subprocess.run(
            [
                sys.executable, str(CLI_PATH), "daily-tick",
                "--today", "13/04", "--year", "2026",
                "--rotina", str(rotina_path),
                "--data-dir", str(data_dir),
                "--output", str(output),
                "--history-output", str(history_output),
                "--history-weeks", "1",
            ],
            capture_output=True, text=True,
            env={**__import__("os").environ, "VITA_TEST_MODE": "1"},
        )
        assert result.returncode == 0, f"daily-tick falhou: {result.stderr}"
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["action"] == "daily_tick"
        assert payload["steps"]["pipeline"]["ok"] is not False
        assert payload["steps"]["execution_history"]["ok"] is True
        assert output.exists(), "diarias.txt deveria existir"
        assert history_output.exists(), "historico-execucao.md deveria existir"
        print("✓ test_daily_tick_success")


def test_daily_tick_partial_failure():
    """daily-tick com pipeline falhando mas execution-history ok retorna ok=False."""
    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        rotina_path = data_dir / "rotina.md"
        rotina_path.write_text("## 06:00 - Acordar\n- Tomar água\n", encoding="utf-8")
        # Cria DIRETÓRIO onde o output file deveria ser escrito → pipeline crash no write_text
        output = Path(tmp) / "diarias.txt"
        output.mkdir()
        history_output = Path(tmp) / "historico-execucao.md"

        result = subprocess.run(
            [
                sys.executable, str(CLI_PATH), "daily-tick",
                "--today", "13/04", "--year", "2026",
                "--rotina", str(rotina_path),
                "--data-dir", str(data_dir),
                "--output", str(output),
                "--history-output", str(history_output),
                "--history-weeks", "1",
            ],
            capture_output=True, text=True,
            env={**__import__("os").environ, "VITA_TEST_MODE": "1"},
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is False, "overall ok deveria ser False quando pipeline falha"
        assert payload["steps"]["pipeline"]["ok"] is False
        assert "error" in payload["steps"]["pipeline"]
        # execution-history ainda roda (independente)
        assert payload["steps"]["execution_history"]["ok"] is True
        print("✓ test_daily_tick_partial_failure")


def test_weekly_tick_success():
    """weekly-tick com todos sub-steps ok retorna JSON agregado com ok=True."""
    from ledger import get_ledger_filename

    today = date(2026, 4, 13)

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        history_output = Path(tmp) / "historico-execucao.md"

        # Cria ledger com ao menos uma task pra ter dados
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        _write_jsonl(ledger_file, [
            _create_test_ledger_record("t1", "Task semanal", "[x]", "manual",
                                       "2026-04-12T09:00:00", "2026-04-12",
                                       completed_at="2026-04-12T17:00:00"),
        ])

        result = subprocess.run(
            [
                sys.executable, str(CLI_PATH), "weekly-tick",
                "--today", "13/04", "--year", "2026",
                "--data-dir", str(data_dir),
                "--history-output", str(history_output),
                "--history-weeks", "1",
                "--min-occurrences", "99",
                "--recurrence-weeks", "1",
            ],
            capture_output=True, text=True,
            env={**__import__("os").environ, "VITA_TEST_MODE": "1"},
        )
        assert result.returncode == 0, f"weekly-tick falhou: {result.stderr}"
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["action"] == "weekly_tick"
        assert "execution_history" in payload["steps"]
        assert "recurrence_candidates" in payload["steps"]
        assert "ledger_status" in payload["steps"]
        assert payload["steps"]["execution_history"]["ok"] is True
        assert payload["steps"]["recurrence_candidates"]["ok"] is True
        print("✓ test_weekly_tick_success")


def test_weekly_tick_includes_status():
    """weekly-tick steps.ledger_status tem campos healthy, issues, current_week, previous_week."""
    from ledger import get_ledger_filename

    today = date(2026, 4, 13)

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        history_output = Path(tmp) / "historico-execucao.md"

        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        _write_jsonl(ledger_file, [
            _create_test_ledger_record("t1", "Task status", "[ ]", "manual",
                                       "2026-04-13T09:00:00", "2026-04-13"),
        ])

        result = subprocess.run(
            [
                sys.executable, str(CLI_PATH), "weekly-tick",
                "--today", "13/04", "--year", "2026",
                "--data-dir", str(data_dir),
                "--history-output", str(history_output),
                "--history-weeks", "1",
            ],
            capture_output=True, text=True,
            env={**__import__("os").environ, "VITA_TEST_MODE": "1"},
        )
        payload = json.loads(result.stdout)
        status = payload["steps"]["ledger_status"]

        # Shape deve ser compatível com cmd_ledger_status
        assert "healthy" in status, f"ledger_status missing 'healthy': {status.keys()}"
        assert "issues" in status
        assert "current_week" in status
        assert "previous_week" in status
        assert "today" in status
        print("✓ test_weekly_tick_includes_status")


def test_ledger_status_refactor_preserves_output():
    """_build_ledger_status retorna mesmo shape que cmd_ledger_status emitia."""
    from cli import _build_ledger_status
    from ledger import get_ledger_filename

    today = date(2026, 4, 13)

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        _write_jsonl(ledger_file, [
            _create_test_ledger_record("t1", "Refactor test", "[ ]", "manual",
                                       "2026-04-13T09:00:00", "2026-04-13"),
            _create_test_ledger_record("t2", "Done task", "[x]", "manual",
                                       "2026-04-12T09:00:00", "2026-04-12",
                                       completed_at="2026-04-12T17:00:00"),
        ])

        result = _build_ledger_status(data_dir, today, 2026)

        # Verifica todos os campos top-level esperados
        expected_keys = {"today", "current_week", "previous_week",
                         "current_ledger", "previous_ledger", "issues", "healthy"}
        assert expected_keys == set(result.keys()), (
            f"Keys divergem: esperado {expected_keys}, recebido {set(result.keys())}"
        )

        # current_week shape
        cw = result["current_week"]
        assert "start" in cw and "end" in cw and "file" in cw and "exists" in cw

        # current_ledger shape (quando existe)
        cl = result["current_ledger"]
        assert cl is not None
        assert "total_tasks" in cl and "open" in cl and "completed" in cl

        print("✓ test_ledger_status_refactor_preserves_output")


def test_check_alerts_no_alerts():
    """check-alerts sem alertas retorna has_alerts=False e lista vazia."""
    from ledger import get_ledger_filename

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        record = _create_test_ledger_record("t1", "Task normal", "[ ]",
                                             created_at="2026-04-13T09:00:00")
        record["updated_at"] = "2026-04-13T10:00:00"  # task já foi tocada → sem first_touch
        _write_jsonl(ledger_file, [record])

        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from cli import _build_alerts
        result = _build_alerts(data_dir, today, 2026)

        assert result["has_alerts"] is False
        assert result["total"] == 0
        assert result["alerts"] == []
        assert result["counts"]["due_today"] == 0
        print("✓ test_check_alerts_no_alerts")


def test_check_alerts_due_today():
    """check-alerts detecta tasks com due_date = hoje."""
    from ledger import get_ledger_filename

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        record = _create_test_ledger_record("t1", "Task urgente", "[ ]",
                                             created_at="2026-04-13T09:00:00")
        record["due_date"] = "13/04"
        _write_jsonl(ledger_file, [record])

        from cli import _build_alerts
        result = _build_alerts(data_dir, today, 2026)

        assert result["has_alerts"] is True
        assert result["counts"]["due_today"] == 1
        assert result["alerts"][0]["type"] == "due_today"
        assert result["alerts"][0]["task_id"] == "t1"
        print("✓ test_check_alerts_due_today")


def test_check_alerts_overdue():
    """check-alerts detecta tasks com due_date no passado."""
    from ledger import get_ledger_filename

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        record = _create_test_ledger_record("t1", "Task atrasada", "[ ]",
                                             created_at="2026-04-10T09:00:00")
        record["due_date"] = "10/04"
        _write_jsonl(ledger_file, [record])

        from cli import _build_alerts
        result = _build_alerts(data_dir, today, 2026)

        assert result["has_alerts"] is True
        assert result["counts"]["overdue"] == 1
        overdue = [a for a in result["alerts"] if a["type"] == "overdue"][0]
        assert overdue["days_overdue"] == 3
        print("✓ test_check_alerts_overdue")


def test_check_alerts_stalled():
    """check-alerts detecta tasks em [~] paradas há mais de 48h."""
    from ledger import get_ledger_filename

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        record = _create_test_ledger_record("t1", "Task parada", "[~]",
                                             created_at="2026-04-10T08:00:00")
        record["started_at"] = "2026-04-10T08:00:00"
        _write_jsonl(ledger_file, [record])

        from cli import _build_alerts
        result = _build_alerts(data_dir, today, 2026)

        assert result["has_alerts"] is True
        assert result["counts"]["stalled"] == 1
        stalled = [a for a in result["alerts"] if a["type"] == "stalled"][0]
        assert stalled["hours_since_update"] > 48
        print("✓ test_check_alerts_stalled")


def test_check_alerts_blocked():
    """check-alerts detecta tasks com postpone_count >= 3."""
    from ledger import get_ledger_filename

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        _write_jsonl(ledger_file, [
            _create_test_ledger_record("t1", "Task bloqueada", "[ ]",
                                       created_at="2026-04-06T09:00:00",
                                       postpone_count=4),
        ])

        from cli import _build_alerts
        result = _build_alerts(data_dir, today, 2026)

        assert result["has_alerts"] is True
        assert result["counts"]["blocked"] == 1
        blocked = [a for a in result["alerts"] if a["type"] == "blocked"][0]
        assert blocked["postpone_count"] == 4
        print("✓ test_check_alerts_blocked")


def test_check_alerts_multiple():
    """check-alerts com múltiplos alertas simultâneos conta corretamente."""
    from ledger import get_ledger_filename

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)

        r1 = _create_test_ledger_record("t1", "Vence hoje", "[ ]",
                                         created_at="2026-04-12T09:00:00")
        r1["due_date"] = "13/04"
        r1["updated_at"] = "2026-04-12T10:00:00"  # tocada, sem first_touch

        r2 = _create_test_ledger_record("t2", "Atrasada e bloqueada", "[ ]",
                                         created_at="2026-04-06T09:00:00",
                                         postpone_count=5)
        r2["due_date"] = "08/04"
        r2["updated_at"] = "2026-04-08T09:00:00"  # tocada, sem first_touch

        r3 = _create_test_ledger_record("t3", "Em progresso parada", "[~]",
                                         created_at="2026-04-09T08:00:00")
        r3["started_at"] = "2026-04-09T10:00:00"

        r4 = _create_test_ledger_record("t4", "Task completada", "[x]",
                                         created_at="2026-04-06T09:00:00",
                                         completed_at="2026-04-12T17:00:00")
        r4["due_date"] = "10/04"  # vencida mas completada — NÃO deve gerar alerta

        _write_jsonl(ledger_file, [r1, r2, r3, r4])

        from cli import _build_alerts
        result = _build_alerts(data_dir, today, 2026)

        assert result["has_alerts"] is True
        assert result["counts"]["due_today"] == 1
        assert result["counts"]["overdue"] == 1
        assert result["counts"]["stalled"] == 1
        assert result["counts"]["blocked"] == 1
        # t1=due_today, t2=overdue+blocked, t3=stalled, t4=nada (completada)
        assert result["total"] == 4
        print("✓ test_check_alerts_multiple")


def test_check_alerts_cli():
    """check-alerts funciona via CLI e retorna JSON válido."""
    from ledger import get_ledger_filename

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        record = _create_test_ledger_record("t1", "Task urgente", "[ ]",
                                             created_at="2026-04-13T09:00:00")
        record["due_date"] = "13/04"
        _write_jsonl(ledger_file, [record])

        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "check-alerts",
             "--today", "13/04", "--year", "2026",
             "--data-dir", str(data_dir)],
            capture_output=True, text=True,
            env={**__import__("os").environ, "VITA_TEST_MODE": "1"},
        )
        assert result.returncode == 0, f"CLI falhou: {result.stderr}"
        payload = json.loads(result.stdout)
        assert payload["has_alerts"] is True
        assert payload["counts"]["due_today"] == 1
        assert "alerts" in payload
        print("✓ test_check_alerts_cli")


def test_heartbeat_tick_no_alerts():
    """heartbeat-tick com ledger vazio: nudges_new=0, emit_text vazio."""
    from heartbeat import build_heartbeat_nudges

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        result = build_heartbeat_nudges(data_dir=data_dir, alerts=[])
        assert result["nudges_new"] == 0
        assert result["suppressed_by_cooldown"] == 0
        assert result["emit_text"] == ""
        assert result["nudges_records"] == []
        print("✓ test_heartbeat_tick_no_alerts")


def test_heartbeat_tick_critical_overdue():
    """heartbeat-tick detecta task overdue 3 dias, gera nudge e emit_text."""
    from ledger import get_ledger_filename
    from heartbeat import build_heartbeat_nudges
    from cli import _build_alerts

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        record = _create_test_ledger_record("t1", "Task atrasada", "[ ]",
                                             created_at="2026-04-10T09:00:00")
        record["due_date"] = "10/04"  # 3 dias atrás
        record["updated_at"] = "2026-04-10T10:00:00"  # tocada, isola alerta overdue puro
        _write_jsonl(ledger_file, [record])

        alerts_res = _build_alerts(data_dir, today, 2026)
        result = build_heartbeat_nudges(data_dir=data_dir, alerts=alerts_res["alerts"])

        assert result["nudges_new"] == 1
        assert result["suppressed_by_cooldown"] == 0
        assert "Task atrasada" in result["emit_text"]
        # v2.13.0: copy library usa "{days_overdue}d" (curto), não "N dias"
        assert "3d" in result["emit_text"]
        assert result["nudges_records"][0]["task_id"] == "t1"
        # v2.12.0: record migrou de alert_type (str) → alert_types (list)
        assert result["nudges_records"][0]["alert_types"] == ["overdue"]
        # v2.13.0: record ganha copy_variant e cooldown_applied
        assert result["nudges_records"][0]["copy_variant"] in ("A", "B")
        assert result["nudges_records"][0]["cooldown_applied"] is True
        # Persistência
        nudges_path = data_dir / "proactive-nudges.jsonl"
        assert nudges_path.exists()
        records = load_ledger(nudges_path)
        assert len([r for r in records if r.get("type") == "nudge"]) == 1
        print("✓ test_heartbeat_tick_critical_overdue")


def test_heartbeat_cooldown_suppresses():
    """Segunda run dentro de 24h suprime o nudge."""
    from ledger import get_ledger_filename
    from heartbeat import build_heartbeat_nudges
    from cli import _build_alerts

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        record = _create_test_ledger_record("t1", "Task atrasada", "[ ]",
                                             created_at="2026-04-10T09:00:00")
        record["due_date"] = "10/04"
        record["updated_at"] = "2026-04-10T10:00:00"  # tocada, isola alerta overdue puro
        _write_jsonl(ledger_file, [record])

        alerts_res = _build_alerts(data_dir, today, 2026)

        # Run 1
        result1 = build_heartbeat_nudges(data_dir=data_dir, alerts=alerts_res["alerts"])
        assert result1["nudges_new"] == 1

        # Run 2 imediata
        result2 = build_heartbeat_nudges(data_dir=data_dir, alerts=alerts_res["alerts"])
        assert result2["nudges_new"] == 0
        assert result2["suppressed_by_cooldown"] == 1
        assert result2["emit_text"] == ""
        print("✓ test_heartbeat_cooldown_suppresses")


def test_heartbeat_non_critical_ignored():
    """Alerta due_today (não crítico por padrão) não gera nudge."""
    from ledger import get_ledger_filename
    from heartbeat import build_heartbeat_nudges
    from cli import _build_alerts

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        record = _create_test_ledger_record("t1", "Task vence hoje", "[ ]",
                                             created_at="2026-04-13T09:00:00")
        record["due_date"] = "13/04"  # due = hoje → alerta due_today, não crítico
        record["updated_at"] = "2026-04-13T10:00:00"  # tocada, isola due_today
        _write_jsonl(ledger_file, [record])

        alerts_res = _build_alerts(data_dir, today, 2026)
        due_today_alerts = [a for a in alerts_res["alerts"] if a["type"] == "due_today"]
        assert len(due_today_alerts) == 1

        result = build_heartbeat_nudges(data_dir=data_dir, alerts=alerts_res["alerts"])
        assert result["nudges_new"] == 0
        assert result["non_critical_skipped"] >= 1
        assert result["emit_text"] == ""
        print("✓ test_heartbeat_non_critical_ignored")


def test_heartbeat_thresholds_from_config():
    """v2.12.0: config com overdue_min_days=5 filtra task com 3 dias overdue."""
    from ledger import get_ledger_filename
    from heartbeat import build_heartbeat_nudges
    from cli import _build_alerts

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        record = _create_test_ledger_record("t1", "Task 3 dias atrasada", "[ ]",
                                             created_at="2026-04-10T09:00:00")
        record["due_date"] = "10/04"
        record["updated_at"] = "2026-04-10T10:00:00"  # tocada, isola overdue
        _write_jsonl(ledger_file, [record])

        # Config com threshold alto filtra o alerta
        config_path = data_dir / "heartbeat-config.json"
        config_path.write_text(json.dumps({"thresholds": {"overdue_min_days": 5}}))

        alerts_res = _build_alerts(data_dir, today, 2026)
        # Sanity: alerta existe com 3 dias
        assert [a for a in alerts_res["alerts"] if a["type"] == "overdue"][0]["days_overdue"] == 3

        result = build_heartbeat_nudges(data_dir=data_dir, alerts=alerts_res["alerts"])
        assert result["nudges_new"] == 0
        assert result["non_critical_skipped"] == 1
        print("✓ test_heartbeat_thresholds_from_config")


def test_heartbeat_max_nudges_per_tick():
    """v2.12.0: com max=2 e 5 tasks críticas, só 2 nudges saem, 3 deferidas."""
    from ledger import get_ledger_filename
    from heartbeat import build_heartbeat_nudges
    from cli import _build_alerts

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        records = []
        for i in range(5):
            r = _create_test_ledger_record(f"t{i}", f"Task {i}", "[ ]",
                                             created_at="2026-04-10T09:00:00")
            r["due_date"] = "10/04"  # 3 dias atrás (crítico com default min=1)
            r["updated_at"] = "2026-04-10T10:00:00"  # tocada, isola overdue
            records.append(r)
        _write_jsonl(ledger_file, records)

        config_path = data_dir / "heartbeat-config.json"
        config_path.write_text(json.dumps({"max_nudges_per_tick": 2}))

        alerts_res = _build_alerts(data_dir, today, 2026)
        assert len([a for a in alerts_res["alerts"] if a["type"] == "overdue"]) == 5

        result = build_heartbeat_nudges(data_dir=data_dir, alerts=alerts_res["alerts"])
        assert result["nudges_new"] == 2
        assert result["over_limit_deferred"] == 3
        print("✓ test_heartbeat_max_nudges_per_tick")


def test_heartbeat_groups_same_task_alerts():
    """v2.12.0: task com overdue + stalled → 1 nudge com ambos alert_types."""
    from datetime import datetime
    from ledger import get_ledger_filename
    from heartbeat import build_heartbeat_nudges
    from cli import _build_alerts

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        # Task [~] (em progresso) há 5 dias sem update e com due_date passada
        record = _create_test_ledger_record("t1", "Task travada", "[~]",
                                             created_at="2026-04-05T09:00:00")
        record["due_date"] = "10/04"  # overdue 3 dias
        record["updated_at"] = "2026-04-06T09:00:00"  # parada ~7d = >24h stalled
        _write_jsonl(ledger_file, [record])

        alerts_res = _build_alerts(data_dir, today, 2026)
        types = sorted({a["type"] for a in alerts_res["alerts"] if a.get("task_id") == "t1"})
        assert "overdue" in types
        assert "stalled" in types

        result = build_heartbeat_nudges(data_dir=data_dir, alerts=alerts_res["alerts"])
        assert result["nudges_new"] == 1
        rec = result["nudges_records"][0]
        assert rec["task_id"] == "t1"
        assert set(rec["alert_types"]) == {"overdue", "stalled"}
        # Fragmento mescla os dois sinais
        assert "atrasada" in rec["text_frag"]
        assert "parada" in rec["text_frag"]
        print("✓ test_heartbeat_groups_same_task_alerts")


def test_heartbeat_cooldown_covers_group():
    """v2.12.0: depois de nudge com overdue, stalled na mesma task fica em cooldown."""
    from datetime import datetime, timedelta
    from ledger import get_ledger_filename
    from heartbeat import build_heartbeat_nudges
    from cli import _build_alerts

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        record = _create_test_ledger_record("t1", "Task travada", "[~]",
                                             created_at="2026-04-05T09:00:00")
        record["due_date"] = "10/04"
        record["updated_at"] = "2026-04-06T09:00:00"
        _write_jsonl(ledger_file, [record])

        alerts_res = _build_alerts(data_dir, today, 2026)

        # Primeira run — emite 1 nudge com overdue+stalled
        now1 = datetime(2026, 4, 13, 14, 0, 0)
        r1 = build_heartbeat_nudges(data_dir=data_dir, alerts=alerts_res["alerts"], now=now1)
        assert r1["nudges_new"] == 1
        assert set(r1["nudges_records"][0]["alert_types"]) == {"overdue", "stalled"}

        # Segunda run 2h depois — mesmos alerts, todos em cooldown
        now2 = datetime(2026, 4, 13, 16, 0, 0)
        r2 = build_heartbeat_nudges(data_dir=data_dir, alerts=alerts_res["alerts"], now=now2)
        assert r2["nudges_new"] == 0
        assert r2["suppressed_by_cooldown"] == 1
        print("✓ test_heartbeat_cooldown_covers_group")


def test_copy_variant_deterministic():
    """v2.13.0: mesma task+alert_type sempre retorna mesma variante."""
    from nudge_copy import pick_variant, VARIANTS

    v1 = pick_variant("task_abc", "overdue")
    v2 = pick_variant("task_abc", "overdue")
    v3 = pick_variant("task_abc", "stalled")  # diferente alert_type, pode mudar
    assert v1 == v2
    assert v1 in VARIANTS
    assert v3 in VARIANTS
    print("✓ test_copy_variant_deterministic")


def test_copy_renders_all_library_types():
    """v2.13.0: COPY_LIBRARY formata sem KeyError com campos esperados do alerta."""
    from nudge_copy import COPY_LIBRARY, render_nudge

    fixtures = {
        "overdue": {"type": "overdue", "description": "X", "days_overdue": 3, "task_id": "t1"},
        "stalled": {"type": "stalled", "description": "X", "hours_since_update": 48, "task_id": "t1"},
        "blocked": {"type": "blocked", "description": "X", "postpone_count": 3, "task_id": "t1"},
        "first_touch": {"type": "first_touch", "description": "X", "hours_since_created": 15, "task_id": "t1"},
    }
    assert set(COPY_LIBRARY.keys()) == set(fixtures.keys()), "library deve cobrir todos fixtures"
    for t, alert in fixtures.items():
        for variant in ("A", "B"):
            text = render_nudge(alert, variant)
            assert text, f"{t} variant {variant} retornou vazio"
            assert "X" in text, f"{t} variant {variant} não renderiza description"
            assert "🌿" in text, f"{t} variant {variant} não tem emoji"
    print("✓ test_copy_renders_all_library_types")


def test_heartbeat_emit_text_uses_copy_library():
    """v2.13.0: emit_text single-nudge usa copy completo com convite à ação."""
    from ledger import get_ledger_filename
    from heartbeat import build_heartbeat_nudges
    from cli import _build_alerts

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        record = _create_test_ledger_record("t1", "Comprar remédio", "[ ]",
                                             created_at="2026-04-10T09:00:00")
        record["due_date"] = "10/04"
        record["updated_at"] = "2026-04-10T10:00:00"  # tocada, isola overdue
        _write_jsonl(ledger_file, [record])

        alerts_res = _build_alerts(data_dir, today, 2026)
        result = build_heartbeat_nudges(data_dir=data_dir, alerts=alerts_res["alerts"])
        assert result["nudges_new"] == 1
        emit = result["emit_text"]
        # Copy spec §7.3: detecção + convite a menor ação
        assert "Comprar remédio" in emit
        assert emit.startswith("🌿")
        assert emit.endswith("?"), "copy deve terminar com convite (pergunta)"
        # Não usa mais o wrapper antigo 'Vita alertou: "..."'
        assert "Vita alertou:" not in emit
        print("✓ test_heartbeat_emit_text_uses_copy_library")


def test_first_touch_alert_fires():
    """v2.14.0 spec §5.1: task [ ] criada há 12h+ sem updated_at dispara first_touch."""
    from ledger import get_ledger_filename

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        # Criada ontem 06:00 → ~42h atrás, sem updated_at → first_touch
        record = _create_test_ledger_record("t1", "Abrir projeto novo", "[ ]",
                                             created_at="2026-04-12T06:00:00")
        _write_jsonl(ledger_file, [record])

        from cli import _build_alerts
        result = _build_alerts(data_dir, today, 2026)

        ft = [a for a in result["alerts"] if a["type"] == "first_touch"]
        assert len(ft) == 1
        assert ft[0]["task_id"] == "t1"
        assert ft[0]["hours_since_created"] >= 12
        assert result["counts"]["first_touch"] == 1
        print("✓ test_first_touch_alert_fires")


def test_first_touch_ignored_when_touched():
    """v2.14.0: task com updated_at (qualquer toque) não dispara first_touch."""
    from ledger import get_ledger_filename

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        record = _create_test_ledger_record("t1", "Task tocada", "[ ]",
                                             created_at="2026-04-10T09:00:00")
        record["updated_at"] = "2026-04-10T10:00:00"  # já foi tocada
        _write_jsonl(ledger_file, [record])

        from cli import _build_alerts
        result = _build_alerts(data_dir, today, 2026)

        ft = [a for a in result["alerts"] if a["type"] == "first_touch"]
        assert len(ft) == 0
        assert result["counts"]["first_touch"] == 0
        print("✓ test_first_touch_ignored_when_touched")


def test_first_touch_respects_threshold():
    """v2.14.0: threshold configurável — first_touch_min_hours=24 não dispara em 15h."""
    from ledger import get_ledger_filename
    from heartbeat import build_heartbeat_nudges
    from cli import _build_alerts

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        # Criada hoje 08:00 → ~16h atrás até 23:59, sem toque
        record = _create_test_ledger_record("t1", "Task fresca", "[ ]",
                                             created_at="2026-04-13T08:00:00")
        _write_jsonl(ledger_file, [record])

        # Default 12h dispara
        result_default = _build_alerts(data_dir, today, 2026)
        assert result_default["counts"]["first_touch"] == 1

        # Threshold 24h não dispara (passa via CLI arg)
        result_strict = _build_alerts(data_dir, today, 2026, first_touch_min_hours=24)
        assert result_strict["counts"]["first_touch"] == 0

        # Via config do heartbeat: threshold 24h → nenhum first_touch emitido
        config_path = data_dir / "heartbeat-config.json"
        config_path.write_text(json.dumps({"thresholds": {"first_touch_min_hours": 24}}))

        # Simula o fluxo do cmd_heartbeat_tick: passa threshold do config pra _build_alerts
        alerts_res = _build_alerts(data_dir, today, 2026, first_touch_min_hours=24)
        hb = build_heartbeat_nudges(data_dir=data_dir, alerts=alerts_res["alerts"])
        assert hb["nudges_new"] == 0
        print("✓ test_first_touch_respects_threshold")


def test_nudges_pending_and_ack():
    """get_pending_nudges retorna não-acked; ack_nudge remove da pending."""
    from ledger import get_ledger_filename
    from heartbeat import build_heartbeat_nudges, get_pending_nudges, ack_nudge
    from cli import _build_alerts

    with tempfile.TemporaryDirectory(prefix="vita_test_") as tmp:
        data_dir = Path(tmp)
        today = date(2026, 4, 13)
        ledger_file = data_dir / "historico" / get_ledger_filename(today)
        record = _create_test_ledger_record("t1", "Task atrasada", "[ ]",
                                             created_at="2026-04-10T09:00:00")
        record["due_date"] = "10/04"
        record["updated_at"] = "2026-04-10T10:00:00"  # tocada, isola overdue
        _write_jsonl(ledger_file, [record])

        alerts_res = _build_alerts(data_dir, today, 2026)
        result = build_heartbeat_nudges(data_dir=data_dir, alerts=alerts_res["alerts"])
        assert result["nudges_new"] == 1
        nudge_id = result["nudges_records"][0]["id"]

        pending_before = get_pending_nudges(data_dir)
        assert len(pending_before) == 1
        assert pending_before[0]["id"] == nudge_id

        ack_nudge(data_dir, nudge_id, source="test")

        pending_after = get_pending_nudges(data_dir)
        assert len(pending_after) == 0
        print("✓ test_nudges_pending_and_ack")


def run_all_tests():
    """Executa todos os testes."""
    print('\n=== Testes vita-task-manager ===\n')
    test_week_start()
    test_week_end()
    test_ledger_path()
    test_make_task_id()
    test_add_and_complete_task()
    test_progress_tracking()
    test_sync_fixed_dedup()
    test_wip_limit()
    test_check_wip_limit_payload()
    test_ledger_start()
    test_ledger_start_blocks_when_limit_reached()
    test_scoring_functions()
    test_suggest_135_distribution()
    test_render_includes_suggestion_section()
    test_markdown_visual_states()
    test_markdown_in_progress_shows_bar()
    test_whatsapp_format()
    test_whatsapp_omits_incomplete_feedback()
    test_whatsapp_renders_complete_feedback()
    test_cli_render_whatsapp()
    test_cli_check_wip()
    test_execution_history_basic()
    test_execution_history_render_markdown()
    test_execution_history_write_preserves_observations()
    test_execution_history_cli()
    test_ledger_update_fields()
    test_ledger_update_not_found()
    test_ledger_update_no_fields()
    test_ledger_update_cli()
    test_duplicate_detection_warns()
    test_duplicate_detection_allow_flag()
    test_duplicate_detection_no_false_positive()
    test_duplicate_detection_accent_normalization()
    test_duplicate_detection_ignores_completed()
    test_rollover_on_sunday()
    test_rollover_missed_sunday()
    test_rollover_no_duplicate()
    test_rollover_late_migration()
    test_ledger_status_cli()
    test_word_weights_basic()
    test_word_weights_min_corpus()
    test_word_weights_write_and_load()
    test_weighted_similarity_changes_outcome()
    test_detect_recurrence_daily_pattern()
    test_detect_recurrence_weekly_pattern()
    test_detect_recurrence_no_clear_pattern()
    test_detect_time_mode()
    test_detect_recurrence_skips_already_rule()
    test_detect_recurrence_skips_rotina_source()
    test_activate_and_get_active_rules()
    test_deactivate_rule_is_not_destructive()
    test_deactivate_rule_not_found()
    test_get_rules_for_weekday()
    test_sync_fixed_injects_recurrence_rules()
    test_sync_fixed_weekly_respects_weekday()
    test_cli_recurrence_detect()
    test_cli_recurrence_activate_and_deactivate()
    test_daily_tick_success()
    test_daily_tick_partial_failure()
    test_weekly_tick_success()
    test_weekly_tick_includes_status()
    test_ledger_status_refactor_preserves_output()
    test_check_alerts_no_alerts()
    test_check_alerts_due_today()
    test_check_alerts_overdue()
    test_check_alerts_stalled()
    test_check_alerts_blocked()
    test_check_alerts_multiple()
    test_check_alerts_cli()
    test_heartbeat_tick_no_alerts()
    test_heartbeat_tick_critical_overdue()
    test_heartbeat_cooldown_suppresses()
    test_heartbeat_non_critical_ignored()
    test_heartbeat_thresholds_from_config()
    test_heartbeat_max_nudges_per_tick()
    test_heartbeat_groups_same_task_alerts()
    test_heartbeat_cooldown_covers_group()
    test_copy_variant_deterministic()
    test_copy_renders_all_library_types()
    test_heartbeat_emit_text_uses_copy_library()
    test_first_touch_alert_fires()
    test_first_touch_ignored_when_touched()
    test_first_touch_respects_threshold()
    test_nudges_pending_and_ack()
    print('\n✓ Todos os testes passaram!\n')


if __name__ == '__main__':
    run_all_tests()
