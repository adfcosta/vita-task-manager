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
    from .execution_history import build_execution_history, render_markdown as render_history_markdown, write_history_file
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
    from execution_history import build_execution_history, render_markdown as render_history_markdown, write_history_file


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
    print('✓ test_whatsapp_format')


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
    print('\n✓ Todos os testes passaram!\n')


if __name__ == '__main__':
    run_all_tests()
