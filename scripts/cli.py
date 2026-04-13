"""CLI do Vita Task Manager."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .feedback_input import build_daily_summary
    from .ledger import get_all_active_tasks, get_current_task_state, get_ledger_path, load_ledger, make_task_id
    from .ledger_ops import (
        add_task as ledger_add_task,
        cancel_task as ledger_cancel_task,
        check_wip_limit,
        complete_task as ledger_complete_task,
        start_task as ledger_start_task,
        store_feedback as ledger_store_feedback,
        sync_fixed_agenda,
        update_progress as ledger_update_progress,
        update_task as ledger_update_task,
    )
    from .models import Task
    from .parser import parse_task_file
    from .pipeline import daily_pipeline
    from .render import render_daily
    from .rollover import perform_rollover
    from .scoring import calculate_total_score
    from .sorter import sort_task_file
    from .suggester import explain_suggestion, suggest_135
    from .updater import (
        add_task as legacy_add_task,
        cancel_task as legacy_cancel_task,
        complete_task as legacy_complete_task,
        load_task_file,
        save_task_file,
        update_progress as legacy_update_progress,
    )
    from .validator import validate_task_file
    from .weekly_summary import build_weekly_summary, render_weekly_summary_markdown
    from .execution_history import build_execution_history, render_markdown as render_history_markdown, write_history_file
except ImportError:
    from feedback_input import build_daily_summary
    from ledger import get_all_active_tasks, get_current_task_state, get_ledger_path, load_ledger, make_task_id
    from ledger_ops import (
        add_task as ledger_add_task,
        cancel_task as ledger_cancel_task,
        check_wip_limit,
        complete_task as ledger_complete_task,
        start_task as ledger_start_task,
        store_feedback as ledger_store_feedback,
        sync_fixed_agenda,
        update_progress as ledger_update_progress,
        update_task as ledger_update_task,
    )
    from models import Task
    from parser import parse_task_file
    from pipeline import daily_pipeline
    from render import render_daily
    from rollover import perform_rollover
    from scoring import calculate_total_score
    from sorter import sort_task_file
    from suggester import explain_suggestion, suggest_135
    from updater import (
        add_task as legacy_add_task,
        cancel_task as legacy_cancel_task,
        complete_task as legacy_complete_task,
        load_task_file,
        save_task_file,
        update_progress as legacy_update_progress,
    )
    from validator import validate_task_file
    from weekly_summary import build_weekly_summary, render_weekly_summary_markdown
    from execution_history import build_execution_history, render_markdown as render_history_markdown, write_history_file


def _compact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _compact(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_compact(v) for v in value]
    return value


def _emit(payload: Any, *, default=str, compact: bool = True) -> None:
    data = _compact(payload) if compact else payload
    print(json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=default))


def _ddmm_to_date(today: str, year: int):
    try:
        from .utils import ddmm_to_date
    except ImportError:
        from utils import ddmm_to_date
    return ddmm_to_date(today, year)


def _find_task(ledger: list[dict], task_id: str):
    try:
        from .ledger import find_task
    except ImportError:
        from ledger import find_task
    return find_task(ledger, task_id)


def _format_output(taskfile, output_format: str, today: str, year: int) -> str:
    if output_format == "whatsapp":
        try:
            from .formatter_whatsapp import format_task_file_whatsapp
        except ImportError:
            from formatter_whatsapp import format_task_file_whatsapp
        return format_task_file_whatsapp(taskfile, _ddmm_to_date(today, year))

    try:
        from .formatter import format_task_file
    except ImportError:
        from formatter import format_task_file
    return format_task_file(taskfile)


def _write_output(path: str, content: str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _resolve_task_id(ledger_path: Path, description: str | None, task_id: str | None, today: str, year: int) -> str:
    if task_id:
        return task_id

    ledger = load_ledger(ledger_path)
    resolved = make_task_id(description, _ddmm_to_date(today, year))
    if _find_task(ledger, resolved) or not description:
        return resolved

    desc = description.lower()
    for record in reversed(ledger):
        if record.get("type") == "task" and record.get("description", "").lower() == desc:
            return record["id"]
    return resolved


def _load_task_state(task_id: str, today: str, year: int, data_dir: str) -> tuple[Path, dict | None]:
    ledger_path = get_ledger_path(today, year, Path(data_dir))
    return ledger_path, get_current_task_state(load_ledger(ledger_path), task_id)


def _task_not_found(task_id: str) -> int:
    _emit({"ok": False, "error": f"Task não encontrada: {task_id}"})
    return 1


def _legacy_save(args, task_file, *, date_value: str) -> None:
    save_task_file(
        args.file,
        task_file,
        today_ddmm=date_value,
        year=args.year,
        refresh_feedback_block=args.refresh_feedback,
    )


def cmd_validate(args) -> int:
    errors = validate_task_file(parse_task_file(args.file))
    _emit({"ok": not errors, "errors": errors or []}, compact=False)
    return 0 if not errors else 1


def cmd_summary(args) -> int:
    task_file = sort_task_file(parse_task_file(args.file), args.today, args.year)
    _emit(build_daily_summary(task_file, args.today, args.year), compact=False)
    return 0


def cmd_add_legacy(args) -> int:
    task_file = load_task_file(args.file)
    legacy_add_task(
        task_file,
        Task(
            status=args.status,
            priority=args.priority,
            description=args.description,
            due_date=args.due,
            context=args.context,
            created_at=args.created,
        ),
    )
    _legacy_save(args, task_file, date_value=args.today or args.created)
    _emit({"ok": True, "action": "add", "task": args.description})
    return 0


def cmd_progress_legacy(args) -> int:
    task_file = load_task_file(args.file)
    legacy_update_progress(task_file, args.description, args.done, args.total, args.unit, args.today, args.year)
    _legacy_save(args, task_file, date_value=args.today)
    _emit({"ok": True, "action": "progress", "task": args.description})
    return 0


def cmd_complete_legacy(args) -> int:
    task_file = load_task_file(args.file)
    legacy_complete_task(task_file, args.description, args.date)
    _legacy_save(args, task_file, date_value=args.date)
    _emit({"ok": True, "action": "complete", "task": args.description})
    return 0


def cmd_cancel_legacy(args) -> int:
    task_file = load_task_file(args.file)
    legacy_cancel_task(task_file, args.description, args.reason, args.date)
    _legacy_save(args, task_file, date_value=args.date)
    _emit({"ok": True, "action": "cancel", "task": args.description})
    return 0


def cmd_resort_legacy(args) -> int:
    task_file = load_task_file(args.file)
    sort_task_file(task_file, args.today, args.year)
    _legacy_save(args, task_file, date_value=args.today)
    _emit({"ok": True, "action": "resort"})
    return 0


def cmd_pipeline(args) -> int:
    _emit(
        daily_pipeline(
            today_ddmm=args.today,
            year=args.year,
            rotina_path=Path(args.rotina),
            agenda_semana_path=Path(args.agenda_semana) if args.agenda_semana else None,
            data_dir=Path(args.data_dir),
            output_path=Path(args.output),
            force_refresh=args.force_feedback,
        )
    )
    return 0


def cmd_ledger_add(args) -> int:
    result = ledger_add_task(
        ledger_path=get_ledger_path(args.today, args.year, Path(args.data_dir)),
        description=args.description,
        priority=args.priority,
        today_ddmm=args.today,
        year=args.year,
        source=args.source,
        due_date=args.due,
        context=args.context,
        allow_duplicate=args.allow_duplicate,
    )
    _emit(result)
    return 0 if result["ok"] else 1


def cmd_ledger_progress(args) -> int:
    ledger_path = get_ledger_path(args.today, args.year, Path(args.data_dir))
    result = ledger_update_progress(
        ledger_path=ledger_path,
        task_id=_resolve_task_id(ledger_path, args.description, args.task_id, args.today, args.year),
        done=args.done,
        total=args.total,
        unit=args.unit,
        today_ddmm=args.today,
        year=args.year,
    )
    _emit(result)
    return 0 if result["ok"] else 1


def cmd_ledger_complete(args) -> int:
    ledger_path = get_ledger_path(args.today, args.year, Path(args.data_dir))
    result = ledger_complete_task(
        ledger_path=ledger_path,
        task_id=_resolve_task_id(ledger_path, args.description, args.task_id, args.today, args.year),
        today_ddmm=args.today,
    )
    _emit(result)
    return 0 if result["ok"] else 1


def cmd_ledger_cancel(args) -> int:
    ledger_path = get_ledger_path(args.today, args.year, Path(args.data_dir))
    result = ledger_cancel_task(
        ledger_path=ledger_path,
        task_id=_resolve_task_id(ledger_path, args.description, args.task_id, args.today, args.year),
        reason=args.reason,
        today_ddmm=args.today,
    )
    _emit(result)
    return 0 if result["ok"] else 1


def cmd_ledger_update(args) -> int:
    ledger_path = get_ledger_path(args.today, args.year, Path(args.data_dir))
    result = ledger_update_task(
        ledger_path=ledger_path,
        task_id=_resolve_task_id(ledger_path, args.description, args.task_id, args.today, args.year),
        today_ddmm=args.today,
        description=args.new_description,
        context=args.context,
        priority=args.priority,
        due_date=args.due,
    )
    _emit(result)
    return 0 if result["ok"] else 1


def cmd_sync_fixed(args) -> int:
    result = sync_fixed_agenda(
        rotina_path=Path(args.rotina),
        ledger_path=get_ledger_path(args.today, args.year, Path(args.data_dir)),
        today_ddmm=args.today,
        year=args.year,
    )
    _emit(result)
    return 0 if result["ok"] else 1


def cmd_store_feedback(args) -> int:
    result = ledger_store_feedback(
        ledger_path=get_ledger_path(args.today, args.year, Path(args.data_dir)),
        feedback_data=json.loads(args.data),
        today_ddmm=args.today,
    )
    _emit(result)
    return 0 if result["ok"] else 1


def cmd_check_wip(args) -> int:
    _emit(check_wip_limit(get_ledger_path(args.today, args.year, Path(args.data_dir)), limit=args.limit))
    return 0


def cmd_ledger_start(args) -> int:
    ledger_path = get_ledger_path(args.today, args.year, Path(args.data_dir))
    result = ledger_start_task(
        ledger_path=ledger_path,
        task_id=_resolve_task_id(ledger_path, args.description, args.task_id, args.today, args.year),
        today_ddmm=args.today,
        limit=args.limit,
    )
    _emit(result)
    return 0 if result["ok"] else 1


def cmd_render(args) -> int:
    taskfile, feedback_seed = render_daily(
        ledger_path=get_ledger_path(args.today, args.year, Path(args.data_dir)),
        agenda_semana_path=Path(args.agenda_semana) if args.agenda_semana else None,
        today_ddmm=args.today,
        year=args.year,
    )
    output_path = _write_output(args.output, _format_output(taskfile, args.format, args.today, args.year))
    _emit(
        {
            "ok": True,
            "output_path": str(output_path),
            "feedback_seed": feedback_seed,
            "format": args.format,
            "summary": {
                "open": len(taskfile.open_tasks),
                "completed_today": len(taskfile.completed_tasks),
                "cancelled_today": len(taskfile.cancelled_tasks),
                "compromissos": len(taskfile.compromissos_dia),
            },
        }
    )
    return 0


def cmd_rollover(args) -> int:
    _emit(perform_rollover(Path(args.data_dir), _ddmm_to_date(args.today, args.year), args.year))
    return 0


def cmd_ledger_status(args) -> int:
    """Diagnóstico do estado atual do ledger."""
    try:
        from .ledger import (
            _merge_task_records,
            get_carry_over_tasks,
            get_ledger_filename,
            get_week_end,
            get_week_start,
        )
    except ImportError:
        from ledger import (
            _merge_task_records,
            get_carry_over_tasks,
            get_ledger_filename,
            get_week_end,
            get_week_start,
        )

    from datetime import timedelta

    data_dir = Path(args.data_dir)
    today = _ddmm_to_date(args.today, args.year)
    hist = data_dir / "historico"

    current_sunday = get_week_start(today)
    current_saturday = get_week_end(today)
    current_file = get_ledger_filename(today)
    current_path = hist / current_file

    prev_sunday = current_sunday - timedelta(days=7)
    prev_file = get_ledger_filename(prev_sunday)
    prev_path = hist / prev_file

    result: dict[str, Any] = {
        "today": str(today),
        "current_week": {
            "start": str(current_sunday),
            "end": str(current_saturday),
            "file": current_file,
            "exists": current_path.exists(),
        },
        "previous_week": {
            "start": str(prev_sunday),
            "end": str(prev_sunday + timedelta(days=6)),
            "file": prev_file,
            "exists": prev_path.exists(),
        },
    }

    # Estado do ledger atual
    if current_path.exists():
        ledger = load_ledger(current_path)
        merged = _merge_task_records(ledger)
        open_tasks = [t for t in merged.values() if t.get("status") in ("[ ]", "[~]")]
        done_tasks = [t for t in merged.values() if t.get("status") == "[x]"]
        cancelled = [t for t in merged.values() if t.get("status") == "[-]"]
        carried = [t for t in merged.values() if t.get("carried_from")]

        result["current_ledger"] = {
            "total_tasks": len(merged),
            "open": len(open_tasks),
            "in_progress": len([t for t in open_tasks if t.get("status") == "[~]"]),
            "completed": len(done_tasks),
            "cancelled": len(cancelled),
            "carried_from_previous": len(carried),
            "open_tasks": [
                {
                    "id": t.get("id"),
                    "description": t.get("description"),
                    "status": t.get("status"),
                    "postpone_count": t.get("postpone_count", 0),
                    "carried_from": t.get("carried_from"),
                }
                for t in open_tasks
            ],
        }
    else:
        result["current_ledger"] = None

    # Estado do ledger anterior
    if prev_path.exists():
        prev_ledger = load_ledger(prev_path)
        pending = get_carry_over_tasks(prev_ledger)
        result["previous_ledger"] = {
            "pending_tasks": len(pending),
            "needs_rollover": len(pending) > 0 and not current_path.exists(),
            "tasks": [
                {
                    "id": t.get("id"),
                    "description": t.get("description"),
                    "status": t.get("status"),
                    "postpone_count": t.get("postpone_count", 0),
                }
                for t in pending
            ],
        }
    else:
        result["previous_ledger"] = None

    # Diagnóstico
    issues = []
    if not current_path.exists() and prev_path.exists():
        pending = get_carry_over_tasks(load_ledger(prev_path))
        if pending:
            issues.append(f"Rollover pendente: {len(pending)} tasks da semana anterior não foram migradas")
    if result["current_ledger"] and result["current_ledger"]["carried_from_previous"] == 0 and prev_path.exists():
        prev_pending = get_carry_over_tasks(load_ledger(prev_path))
        # Verifica se o ledger anterior tem tasks que não foram rolled over
        has_rollover_ops = any(
            r.get("_operation") == "rollover"
            for r in load_ledger(prev_path)
        )
        if prev_pending and not has_rollover_ops:
            issues.append(f"Ledger atual existe mas {len(prev_pending)} tasks da semana anterior não foram migradas")

    result["issues"] = issues
    result["healthy"] = len(issues) == 0

    _emit(result, compact=False)
    return 0


def cmd_weekly_summary(args) -> int:
    summary = build_weekly_summary(Path(args.ledger))
    if args.output:
        _write_output(args.output, render_weekly_summary_markdown(summary))
    if args.format == "md":
        print(render_weekly_summary_markdown(summary))
    else:
        _emit(summary)
    return 0


def cmd_brain_dump(args) -> int:
    try:
        from .ledger_ops import brain_dump
    except ImportError:
        from ledger_ops import brain_dump

    result = brain_dump(
        ledger_path=get_ledger_path(args.today, args.year, Path(args.data_dir)),
        text=args.text,
        today_ddmm=args.today,
        year=args.year,
        due_date=args.due,
    )
    _emit(result)
    return 0 if result["ok"] else 1


def cmd_dump_to_task(args) -> int:
    try:
        from .ledger_ops import dump_to_task
    except ImportError:
        from ledger_ops import dump_to_task

    result = dump_to_task(
        ledger_path=get_ledger_path(args.today, args.year, Path(args.data_dir)),
        dump_id=args.dump_id,
        extracted_item=args.item,
        today_ddmm=args.today,
        year=args.year,
        priority=args.priority,
        next_action=args.next_action,
        due_date=args.due,
    )
    _emit(result)
    return 0 if result["ok"] else 1


def cmd_score_task(args) -> int:
    _, task = _load_task_state(args.task_id, args.today, args.year, args.data_dir)
    if not task:
        return _task_not_found(args.task_id)

    scored = calculate_total_score(task, _ddmm_to_date(args.today, args.year))
    task.update(scored)
    _emit(
        {
            "ok": True,
            "task_id": task.get("id"),
            "description": task.get("description"),
            "score": scored["score"],
            "complexity_score": scored["complexity_score"],
            "complexity_source": scored["complexity_source"],
            "energy_required": scored["energy_required"],
            "score_breakdown": scored["score_breakdown"],
        }
    )
    return 0


def cmd_suggest_daily(args) -> int:
    today = _ddmm_to_date(args.today, args.year)
    ledger_path = get_ledger_path(args.today, args.year, Path(args.data_dir))
    tasks = get_all_active_tasks(load_ledger(ledger_path))
    suggestions = suggest_135(tasks, today, limit=args.limit)
    selected = [item for bucket in ("big", "medium", "small") for item in suggestions[bucket]]
    average = round(sum(item["score"] for item in selected) / len(selected), 2) if selected else 0.0

    _emit(
        {
            "ok": True,
            "today": f"{today:%d/%m/%Y}",
            "ledger_path": str(ledger_path),
            "summary": {
                "tasks_available": len([task for task in tasks if task.get("status") in ("[ ]", "[~]")]),
                "tasks_selected": len(selected),
                "average_score": average,
                "slots": {bucket: len(items) for bucket, items in suggestions.items()},
                "limit": args.limit,
            },
            "recommendations": {
                bucket: [
                    {
                        "position": item.get("position"),
                        "task_id": item.get("id"),
                        "title": item.get("description"),
                        "score": item.get("score"),
                        "size_category": item.get("size_category"),
                        "complexity_score": item.get("complexity_score"),
                        "complexity_source": item.get("complexity_source"),
                        "energy_required": item.get("energy_required"),
                        "why": item.get("explanation"),
                        "score_breakdown": item.get("score_breakdown"),
                    }
                    for item in suggestions[bucket]
                ]
                for bucket in ("big", "medium", "small")
            },
        }
    )
    return 0


def cmd_explain_task(args) -> int:
    _, task = _load_task_state(args.task_id, args.today, args.year, args.data_dir)
    if not task:
        return _task_not_found(args.task_id)

    scored = calculate_total_score(task, _ddmm_to_date(args.today, args.year))
    task.update(scored)
    _emit(
        {
            "ok": True,
            "task_id": task.get("id"),
            "description": task.get("description"),
            "score": scored["score"],
            "explanation": explain_suggestion(task),
            "score_breakdown": scored["score_breakdown"],
        }
    )
    return 0


def cmd_execution_history(args) -> int:
    data_dir = Path(args.data_dir)
    today = _ddmm_to_date(args.today, args.year)
    weeks = args.weeks

    history = build_execution_history(data_dir, today, weeks)
    md = render_history_markdown(history)

    output_path = Path(args.output)
    write_history_file(output_path, md)

    _emit({"ok": True, "output": str(output_path), "weeks_analyzed": weeks})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI do Vita Task Manager.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("pipeline", help="Pipeline diário completo")
    p.add_argument("--today", required=True, help="Data de hoje (DD/MM)")
    p.add_argument("--year", type=int, required=True, help="Ano atual (YYYY)")
    p.add_argument("--rotina", required=True, help="Caminho de rotina.md")
    p.add_argument("--agenda-semana", help="Caminho de agenda_da_semana.md")
    p.add_argument("--data-dir", required=True, help="Diretório de dados")
    p.add_argument("--output", required=True, help="Caminho de saída")
    p.add_argument("--force-feedback", action="store_true", help="Força refresh de feedback")
    p.set_defaults(func=cmd_pipeline)

    p = sub.add_parser("validate", help="[LEGADO] Valida arquivo")
    p.add_argument("file", help="Caminho do arquivo")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("summary", help="[LEGADO] Gera resumo")
    p.add_argument("file", help="Caminho do arquivo")
    p.add_argument("--today", required=True, help="Data de hoje (DD/MM)")
    p.add_argument("--year", type=int, required=True, help="Ano atual (YYYY)")
    p.set_defaults(func=cmd_summary)

    p = sub.add_parser("add", help="[LEGADO] Adiciona tarefa no markdown")
    p.add_argument("--file", required=True, help="Caminho do arquivo")
    p.add_argument("--status", required=True, choices=["[ ]", "[~]", "[x]", "[-]"])
    p.add_argument("--priority", required=True, choices=["🔴", "🟡", "🟢"])
    p.add_argument("--description", required=True)
    p.add_argument("--due", help="Prazo (DD/MM)")
    p.add_argument("--context", help="Contexto")
    p.add_argument("--created", required=True, help="Data de criação (DD/MM)")
    p.add_argument("--today", help="Data de hoje (DD/MM)")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--refresh-feedback", action="store_true")
    p.set_defaults(func=cmd_add_legacy)

    p = sub.add_parser("progress", help="[LEGADO] Atualiza progresso no markdown")
    p.add_argument("--file", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--done", type=int, required=True)
    p.add_argument("--total", type=int, required=True)
    p.add_argument("--unit", required=True)
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--refresh-feedback", action="store_true")
    p.set_defaults(func=cmd_progress_legacy)

    p = sub.add_parser("complete", help="[LEGADO] Marca como concluída no markdown")
    p.add_argument("--file", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--refresh-feedback", action="store_true")
    p.set_defaults(func=cmd_complete_legacy)

    p = sub.add_parser("cancel", help="[LEGADO] Cancela/adia no markdown")
    p.add_argument("--file", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--refresh-feedback", action="store_true")
    p.set_defaults(func=cmd_cancel_legacy)

    p = sub.add_parser("resort", help="[LEGADO] Reordena tarefas")
    p.add_argument("--file", required=True)
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--refresh-feedback", action="store_true")
    p.set_defaults(func=cmd_resort_legacy)

    p = sub.add_parser("ledger-add", help="Adiciona task ao ledger")
    p.add_argument("--description", required=True)
    p.add_argument("--priority", required=True, choices=["🔴", "🟡", "🟢"])
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.add_argument("--source", choices=["rotina", "agenda_semana", "manual"], default="manual")
    p.add_argument("--due", help="Prazo (DD/MM)")
    p.add_argument("--context", help="Contexto")
    p.add_argument("--allow-duplicate", action="store_true", help="Suprime warning de duplicata")
    p.set_defaults(func=cmd_ledger_add)

    p = sub.add_parser("ledger-progress", help="Atualiza progresso no ledger")
    p.add_argument("--task-id", help="ID da task")
    p.add_argument("--description", help="Descrição para resolver ID")
    p.add_argument("--done", type=int, required=True)
    p.add_argument("--total", type=int, required=True)
    p.add_argument("--unit", required=True)
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_ledger_progress)

    p = sub.add_parser("ledger-complete", help="Conclui task no ledger")
    p.add_argument("--task-id", help="ID da task")
    p.add_argument("--description", help="Descrição para resolver ID")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_ledger_complete)

    p = sub.add_parser("ledger-cancel", help="Cancela task no ledger")
    p.add_argument("--task-id", help="ID da task")
    p.add_argument("--description", help="Descrição para resolver ID")
    p.add_argument("--reason", required=True)
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_ledger_cancel)

    p = sub.add_parser("ledger-update", help="Atualiza campos de task existente")
    p.add_argument("--task-id", help="ID da task")
    p.add_argument("--description", help="Descrição para resolver ID")
    p.add_argument("--new-description", help="Nova descrição")
    p.add_argument("--context", help="Novo contexto")
    p.add_argument("--priority", choices=["🔴", "🟡", "🟢"], help="Nova prioridade")
    p.add_argument("--due", help="Novo prazo (DD/MM)")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_ledger_update)

    p = sub.add_parser("ledger-start", help="Inicia task respeitando WIP")
    p.add_argument("--task-id", help="ID da task")
    p.add_argument("--description", help="Descrição para resolver ID")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.add_argument("--limit", type=int, default=2, help="Limite de tasks em andamento")
    p.set_defaults(func=cmd_ledger_start)

    p = sub.add_parser("check-wip", help="Verifica limite atual de WIP")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.add_argument("--limit", type=int, default=2, help="Limite de tasks em andamento")
    p.set_defaults(func=cmd_check_wip)

    p = sub.add_parser("sync-fixed", help="Sincroniza rotina no ledger")
    p.add_argument("--rotina", required=True)
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_sync_fixed)

    p = sub.add_parser("store-feedback", help="Armazena feedback no ledger")
    p.add_argument("--data", required=True, help="JSON do feedback")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_store_feedback)

    p = sub.add_parser("render", help="Gera saída do dia")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.add_argument("--agenda-semana", help="Caminho de agenda_da_semana.md")
    p.add_argument("--output", required=True)
    p.add_argument("--format", choices=["markdown", "whatsapp"], default="whatsapp")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("rollover", help="Executa rollover semanal")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_rollover)

    p = sub.add_parser("ledger-status", help="Diagnóstico do estado do ledger")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_ledger_status)

    p = sub.add_parser("weekly-summary", help="Gera resumo semanal")
    p.add_argument("--ledger", required=True, help="Caminho do arquivo bruto JSONL")
    p.add_argument("--format", choices=["json", "md"], default="json")
    p.add_argument("--output", help="Salvar markdown em arquivo")
    p.set_defaults(func=cmd_weekly_summary)

    p = sub.add_parser("brain-dump", help="Captura rápida de sobrecarga mental")
    p.add_argument("--text", required=True, help="Texto do dump")
    p.add_argument("--due", help="Prazo: DD/MM/YYYY ou +N")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_brain_dump)

    p = sub.add_parser("dump-to-task", help="Promove item do brain dump")
    p.add_argument("--dump-id", required=True, help="ID do dump")
    p.add_argument("--item", required=True, help="Item que vira task")
    p.add_argument("--priority", default="🟡", choices=["🔴", "🟡", "🟢"])
    p.add_argument("--next-action", help="Próxima ação física")
    p.add_argument("--due", help="Prazo (sobrescreve o do dump)")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_dump_to_task)

    p = sub.add_parser("score-task", help="Calcula score dinâmico")
    p.add_argument("--task-id", required=True)
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_score_task)

    p = sub.add_parser("suggest-daily", help="Sugere tarefas pelo método 1-3-5")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.add_argument("--limit", type=int, default=9, help="Máximo total de sugestões")
    p.set_defaults(func=cmd_suggest_daily)

    p = sub.add_parser("explain-task", help="Explica o score de uma task")
    p.add_argument("--task-id", required=True)
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_explain_task)

    p = sub.add_parser("execution-history", help="Gera relatório de padrões de execução")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.add_argument("--output", required=True, help="Caminho do arquivo de saída (.md)")
    p.add_argument("--weeks", type=int, default=4, help="Semanas para analisar (padrão: 4)")
    p.set_defaults(func=cmd_execution_history)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
