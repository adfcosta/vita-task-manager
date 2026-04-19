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
    from .execution_history import build_execution_history, build_word_weights, load_word_weights, render_markdown as render_history_markdown, write_history_file, write_word_weights
    from .recurrence import (
        activate_recurrence_rule,
        deactivate_recurrence_rule,
        detect_recurrence_candidates,
        get_active_recurrence_rules,
    )
    from .heartbeat import (
        build_heartbeat_nudges,
        load_heartbeat_config,
        get_pending_nudges,
        ack_nudge,
    )
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
    from execution_history import build_execution_history, build_word_weights, load_word_weights, render_markdown as render_history_markdown, write_history_file, write_word_weights
    from recurrence import (
        activate_recurrence_rule,
        deactivate_recurrence_rule,
        detect_recurrence_candidates,
        get_active_recurrence_rules,
    )
    from heartbeat import (
        build_heartbeat_nudges,
        load_heartbeat_config,
        get_pending_nudges,
        ack_nudge,
    )


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


def _build_ledger_status(data_dir: Path, today, year: int) -> dict[str, Any]:
    """Constrói dict de diagnóstico do ledger (função pura, sem I/O de emit)."""
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

    from datetime import date as date_type, timedelta

    if isinstance(today, str):
        today = _ddmm_to_date(today, year)

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
        has_rollover_ops = any(
            r.get("_operation") == "rollover"
            for r in load_ledger(prev_path)
        )
        if prev_pending and not has_rollover_ops:
            issues.append(f"Ledger atual existe mas {len(prev_pending)} tasks da semana anterior não foram migradas")

    result["issues"] = issues
    result["healthy"] = len(issues) == 0

    return result


def cmd_ledger_status(args) -> int:
    """Diagnóstico do estado atual do ledger."""
    result = _build_ledger_status(Path(args.data_dir), _ddmm_to_date(args.today, args.year), args.year)
    _emit(result, compact=False)
    return 0


def _build_alerts(
    data_dir: Path,
    today,
    year: int,
    first_touch_min_hours: int = 12,
    off_pace_ratio: float = 0.7,
) -> dict[str, Any]:
    """Inspeciona o ledger e retorna alertas acionáveis (função pura, sem I/O de emit).

    Alertas detectados:
    - due_today: tasks com due_date = hoje
    - overdue: tasks com due_date < hoje
    - stalled: tasks em [~] há mais de 48h sem atualização
    - blocked: tasks com postpone_count >= 3
    - first_touch: tasks em [ ] criadas há first_touch_min_hours+ sem toque
      (sem updated_at) — spec TDAH §5.1
    - off_pace: tasks com progress_done/progress_total e due_date futuro
      cujo ritmo está abaixo de off_pace_ratio do esperado — spec §5.6
    """
    try:
        from .ledger import _merge_task_records, get_ledger_filename, get_week_start
    except ImportError:
        from ledger import _merge_task_records, get_ledger_filename, get_week_start

    from datetime import datetime, timedelta

    if isinstance(today, str):
        today = _ddmm_to_date(today, year)

    hist = data_dir / "historico"
    ledger_path = hist / get_ledger_filename(today)

    if not ledger_path.exists():
        return {
            "today": str(today),
            "has_alerts": False,
            "counts": {"due_today": 0, "overdue": 0, "stalled": 0, "blocked": 0},
            "alerts": [],
        }

    ledger = load_ledger(ledger_path)
    merged = _merge_task_records(ledger)

    # Filtrar apenas tasks abertas ([ ] ou [~])
    open_tasks = [t for t in merged.values() if t.get("status") in ("[ ]", "[~]")]

    alerts: list[dict[str, Any]] = []
    today_ddmm = f"{today.day:02d}/{today.month:02d}"

    for task in open_tasks:
        task_id = task.get("id", "?")
        desc = task.get("description", "?")
        due = task.get("due_date")
        status = task.get("status", "[ ]")
        postpone = int(task.get("postpone_count") or 0)

        # Due today
        if due and due == today_ddmm:
            alerts.append({
                "type": "due_today",
                "task_id": task_id,
                "description": desc,
                "due_date": due,
                "priority": task.get("priority"),
            })

        # Overdue (due_date < today)
        if due:
            try:
                day, month = map(int, due.split("/"))
                due_date = today.replace(month=month, day=day)
                if due_date < today:
                    alerts.append({
                        "type": "overdue",
                        "task_id": task_id,
                        "description": desc,
                        "due_date": due,
                        "days_overdue": (today - due_date).days,
                        "priority": task.get("priority"),
                    })
            except (ValueError, TypeError):
                pass

        # Stalled: [~] há mais de 48h sem atualização
        if status == "[~]":
            last_update = task.get("updated_at") or task.get("started_at") or task.get("created_at")
            if last_update:
                try:
                    last_dt = datetime.fromisoformat(last_update)
                    now = datetime.combine(today, datetime.min.time().replace(hour=23, minute=59))
                    hours_since = (now - last_dt).total_seconds() / 3600
                    if hours_since > 48:
                        alerts.append({
                            "type": "stalled",
                            "task_id": task_id,
                            "description": desc,
                            "hours_since_update": round(hours_since),
                            "last_update": last_update,
                        })
                except (ValueError, TypeError):
                    pass

        # Blocked: postpone_count >= 3
        if postpone >= 3:
            alerts.append({
                "type": "blocked",
                "task_id": task_id,
                "description": desc,
                "postpone_count": postpone,
            })

        # Off pace (spec §5.6): task com progress e due_date futuro andando
        # abaixo do ritmo esperado. Preventivo — dispara antes de virar overdue.
        done = task.get("progress_done")
        total = task.get("progress_total")
        created = task.get("created_at")
        if done is not None and total and due and created:
            try:
                day, month = map(int, due.split("/"))
                due_date = today.replace(month=month, day=day)
                created_date = datetime.fromisoformat(created).date()
                total_days = max((due_date - created_date).days, 1)
                days_passed = (today - created_date).days
                # Só avalia se ainda não venceu e já rodou pelo menos 1 dia
                if days_passed > 0 and due_date >= today and int(total) > 0:
                    expected = (days_passed / total_days) * int(total)
                    if int(done) < expected * off_pace_ratio:
                        days_remaining = (due_date - today).days
                        alerts.append({
                            "type": "off_pace",
                            "task_id": task_id,
                            "description": desc,
                            "done_units": int(done),
                            "total_units": int(total),
                            "expected_units": round(expected, 1),
                            "days_remaining": days_remaining,
                            "unit": task.get("unit"),
                            "priority": task.get("priority"),
                        })
            except (ValueError, TypeError):
                pass

        # First touch (spec §5.1): task em [ ] criada há N+ horas sem nenhum toque.
        # "Toque" = qualquer updated_at registrado (ledger-start/progress/update
        # sempre atualizam updated_at). Sem updated_at = nunca foi mexida.
        if status == "[ ]" and not task.get("updated_at"):
            created = task.get("created_at")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created)
                    now = datetime.combine(today, datetime.min.time().replace(hour=23, minute=59))
                    hours_since_created = (now - created_dt).total_seconds() / 3600
                    if hours_since_created >= first_touch_min_hours:
                        alerts.append({
                            "type": "first_touch",
                            "task_id": task_id,
                            "description": desc,
                            "hours_since_created": round(hours_since_created),
                            "created_at": created,
                        })
                except (ValueError, TypeError):
                    pass

    counts = {
        "due_today": len([a for a in alerts if a["type"] == "due_today"]),
        "overdue": len([a for a in alerts if a["type"] == "overdue"]),
        "stalled": len([a for a in alerts if a["type"] == "stalled"]),
        "blocked": len([a for a in alerts if a["type"] == "blocked"]),
        "first_touch": len([a for a in alerts if a["type"] == "first_touch"]),
        "off_pace": len([a for a in alerts if a["type"] == "off_pace"]),
    }

    return {
        "today": str(today),
        "has_alerts": len(alerts) > 0,
        "counts": counts,
        "total": len(alerts),
        "alerts": alerts,
    }


def cmd_check_alerts(args) -> int:
    """Inspeciona o ledger e retorna alertas acionáveis."""
    result = _build_alerts(Path(args.data_dir), _ddmm_to_date(args.today, args.year), args.year)
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

    # Gera word_weights.json como subproduto (usa 12 semanas de corpus)
    ww = build_word_weights(data_dir, today, weeks=max(weeks, 12))
    ww_path = write_word_weights(data_dir, ww)

    _emit({
        "ok": True,
        "output": str(output_path),
        "weeks_analyzed": weeks,
        "word_weights": str(ww_path),
        "word_weights_count": ww.get("word_count", 0),
    })
    return 0


def cmd_recurrence_detect(args) -> int:
    """Detecta candidatos a recorrência no histórico."""
    data_dir = Path(args.data_dir)
    today = _ddmm_to_date(args.today, args.year)

    candidates = detect_recurrence_candidates(
        data_dir=data_dir,
        today=today,
        min_occurrences=args.min_occurrences,
        lookback_weeks=args.weeks,
    )

    _emit({
        "ok": True,
        "candidates": candidates,
        "count": len(candidates),
    })
    return 0


def cmd_recurrence_activate(args) -> int:
    """Ativa uma regra de recorrência."""
    ledger_path = get_ledger_path(args.today, args.year, Path(args.data_dir))
    weekdays = json.loads(args.weekdays) if args.weekdays else []

    result = activate_recurrence_rule(
        ledger_path=ledger_path,
        description=args.description,
        pattern=args.pattern,
        weekdays=weekdays,
        priority=args.priority,
        time_range=args.time_range,
        today_ddmm=args.today,
        year=args.year,
        source_task_ids=json.loads(args.source_task_ids) if args.source_task_ids else None,
    )
    _emit(result)
    return 0 if result["ok"] else 1


def cmd_recurrence_deactivate(args) -> int:
    """Desativa uma regra de recorrência."""
    ledger_path = get_ledger_path(args.today, args.year, Path(args.data_dir))

    result = deactivate_recurrence_rule(
        ledger_path=ledger_path,
        rule_id=args.rule_id,
        reason=args.reason,
        today_ddmm=args.today,
    )
    _emit(result)
    return 0 if result["ok"] else 1


def cmd_recurrence_list(args) -> int:
    """Lista regras de recorrência ativas."""
    ledger_path = get_ledger_path(args.today, args.year, Path(args.data_dir))
    ledger = load_ledger(ledger_path)
    rules = get_active_recurrence_rules(ledger)

    _emit({
        "ok": True,
        "rules": rules,
        "count": len(rules),
    })
    return 0


def cmd_daily_tick(args) -> int:
    """Roda pipeline do dia + execution-history + word_weights.

    Agrega resultado em JSON único com ok=all sub-steps ok.
    Sub-falhas não interrompem o fluxo — cada passo é reportado
    independentemente.
    """
    results = {}
    overall_ok = True

    # Passo 1: pipeline (pipeline já roda sync-fixed, store-feedback, render)
    try:
        pipeline_result = daily_pipeline(
            today_ddmm=args.today,
            year=args.year,
            rotina_path=Path(args.rotina),
            agenda_semana_path=Path(args.agenda_semana) if args.agenda_semana else None,
            data_dir=Path(args.data_dir),
            output_path=Path(args.output),
            force_refresh=args.force_feedback,
        )
        results["pipeline"] = {**pipeline_result, "ok": True}
        if not pipeline_result.get("ok", True):
            overall_ok = False
    except Exception as exc:
        results["pipeline"] = {"ok": False, "error": str(exc)}
        overall_ok = False

    # Passo 2: execution-history (refresh de histórico + word_weights)
    try:
        data_dir = Path(args.data_dir)
        today = _ddmm_to_date(args.today, args.year)
        history = build_execution_history(data_dir, today, args.history_weeks)
        md = render_history_markdown(history)
        history_output = Path(args.history_output)
        write_history_file(history_output, md)
        ww = build_word_weights(data_dir, today, weeks=max(args.history_weeks, 12))
        ww_path = write_word_weights(data_dir, ww)
        results["execution_history"] = {
            "ok": True,
            "output": str(history_output),
            "weeks_analyzed": args.history_weeks,
            "word_weights_path": str(ww_path),
            "word_weights_count": ww.get("word_count", 0),
        }
    except Exception as exc:
        results["execution_history"] = {"ok": False, "error": str(exc)}
        overall_ok = False

    _emit({
        "ok": overall_ok,
        "action": "daily_tick",
        "today": args.today,
        "steps": results,
    })
    return 0 if overall_ok else 1


def cmd_weekly_tick(args) -> int:
    """Refresh semanal: execution-history + recurrence-detect + ledger-status.

    Projetado pra rodar domingo à noite (ou qualquer dia). Retorna
    JSON agregado com:
    - execution_history: path do markdown e contagem de weights
    - recurrence_candidates: lista de candidatos detectados
    - ledger_status: healthy + issues

    Sub-falhas não interrompem — cada passo reportado independente.
    """
    results = {}
    overall_ok = True
    data_dir = Path(args.data_dir)
    today = _ddmm_to_date(args.today, args.year)

    # Passo 1: execution-history (full refresh)
    try:
        history = build_execution_history(data_dir, today, args.history_weeks)
        md = render_history_markdown(history)
        history_output = Path(args.history_output)
        write_history_file(history_output, md)
        ww = build_word_weights(data_dir, today, weeks=max(args.history_weeks, 12))
        ww_path = write_word_weights(data_dir, ww)
        results["execution_history"] = {
            "ok": True,
            "output": str(history_output),
            "weeks_analyzed": args.history_weeks,
            "word_weights_path": str(ww_path),
            "word_weights_count": ww.get("word_count", 0),
        }
    except Exception as exc:
        results["execution_history"] = {"ok": False, "error": str(exc)}
        overall_ok = False

    # Passo 2: recurrence-detect
    try:
        candidates = detect_recurrence_candidates(
            data_dir=data_dir,
            today=today,
            min_occurrences=args.min_occurrences,
            lookback_weeks=args.recurrence_weeks,
        )
        results["recurrence_candidates"] = {
            "ok": True,
            "count": len(candidates),
            "candidates": candidates,
        }
    except Exception as exc:
        results["recurrence_candidates"] = {"ok": False, "error": str(exc)}
        overall_ok = False

    # Passo 3: ledger-status
    try:
        status = _build_ledger_status(data_dir, today, args.year)
        results["ledger_status"] = status
    except Exception as exc:
        results["ledger_status"] = {"ok": False, "error": str(exc)}
        overall_ok = False

    _emit({
        "ok": overall_ok,
        "action": "weekly_tick",
        "today": args.today,
        "steps": results,
    }, compact=False)
    return 0 if overall_ok else 1


def cmd_heartbeat_tick(args) -> int:
    """Detecta alertas críticos, aplica cooldown, persiste nudges, retorna emit info."""
    data_dir = Path(args.data_dir)
    today = _ddmm_to_date(args.today, args.year)
    config = load_heartbeat_config(data_dir)
    cooldown_hours = args.cooldown_hours if args.cooldown_hours is not None else config["cooldown_hours"]
    thresholds = config.get("thresholds") or {}
    first_touch_min_hours = thresholds.get("first_touch_min_hours", 12)
    off_pace_ratio = thresholds.get("off_pace_ratio", 0.7)

    alerts_result = _build_alerts(
        data_dir,
        today,
        args.year,
        first_touch_min_hours=first_touch_min_hours,
        off_pace_ratio=off_pace_ratio,
    )
    heartbeat_result = build_heartbeat_nudges(
        data_dir=data_dir,
        alerts=alerts_result["alerts"],
        cooldown_hours=cooldown_hours,
        config=config,
    )

    _emit({
        "ok": True,
        "action": "heartbeat_tick",
        "today": args.today,
        "alerts_total": alerts_result.get("total", len(alerts_result["alerts"])),
        "nudges_new": heartbeat_result["nudges_new"],
        "suppressed_by_cooldown": heartbeat_result["suppressed_by_cooldown"],
        "non_critical_skipped": heartbeat_result["non_critical_skipped"],
        "emit_text": heartbeat_result["emit_text"],
        "emit_target": config["emit_target"],
    })
    return 0


def cmd_nudges_pending(args) -> int:
    """Lista nudges pendentes (não acked)."""
    pending = get_pending_nudges(Path(args.data_dir))
    _emit({
        "ok": True,
        "count": len(pending),
        "nudges": pending,
    })
    return 0


def cmd_nudges_ack(args) -> int:
    """Marca um nudge como acked."""
    record = ack_nudge(
        Path(args.data_dir),
        args.nudge_id,
        source=args.source,
        response_kind=args.response_kind,
    )
    _emit({"ok": True, "ack": record})
    return 0


def cmd_nudge_delivery(args) -> int:
    """Registra resultado da entrega de um nudge (spec §11)."""
    try:
        from .heartbeat import mark_delivery
    except ImportError:
        from heartbeat import mark_delivery  # type: ignore[no-redef]
    record = mark_delivery(Path(args.data_dir), args.nudge_id, args.status)
    _emit({"ok": True, "delivery": record})
    return 0


def cmd_nudge_kpis(args) -> int:
    """Calcula KPIs dos nudges (spec §16)."""
    try:
        from .kpis import compute_kpis
    except ImportError:
        from kpis import compute_kpis  # type: ignore[no-redef]
    result = compute_kpis(Path(args.data_dir), window_days=args.window_days)
    _emit({"ok": True, "kpis": result})
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

    p = sub.add_parser("recurrence-detect", help="Detecta candidatos a recorrência")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.add_argument("--min-occurrences", type=int, default=5, help="Mínimo de ocorrências (padrão: 5)")
    p.add_argument("--weeks", type=int, default=4, help="Semanas de lookback (padrão: 4)")
    p.set_defaults(func=cmd_recurrence_detect)

    p = sub.add_parser("recurrence-activate", help="Ativa regra de recorrência")
    p.add_argument("--description", required=True, help="Descrição da task recorrente")
    p.add_argument("--pattern", required=True, choices=["daily", "weekly"], help="Padrão: daily ou weekly")
    p.add_argument("--weekdays", help="JSON array de weekdays (0=Mon..6=Sun), ex: [0,2,4]")
    p.add_argument("--priority", required=True, choices=["🔴", "🟡", "🟢"])
    p.add_argument("--time-range", help="Horário (HH:MM)")
    p.add_argument("--source-task-ids", help="JSON array de task_ids originais")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_recurrence_activate)

    p = sub.add_parser("recurrence-deactivate", help="Desativa regra de recorrência")
    p.add_argument("--rule-id", required=True, help="ID da regra")
    p.add_argument("--reason", required=True, help="Motivo da desativação")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_recurrence_deactivate)

    p = sub.add_parser("recurrence-list", help="Lista regras de recorrência ativas")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_recurrence_list)

    p = sub.add_parser("check-alerts", help="Inspeciona ledger e retorna alertas acionáveis")
    p.add_argument("--today", required=True, help="Data de hoje (DD/MM)")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_check_alerts)

    p = sub.add_parser("daily-tick", help="Comando composto: pipeline + execution-history")
    p.add_argument("--today", required=True, help="Data de hoje (DD/MM)")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--rotina", required=True, help="Caminho de rotina.md")
    p.add_argument("--agenda-semana", help="Caminho de agenda_da_semana.md")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--output", required=True, help="Caminho do diarias.txt")
    p.add_argument("--history-output", required=True, help="Caminho do historico-execucao.md")
    p.add_argument("--history-weeks", type=int, default=4)
    p.add_argument("--force-feedback", action="store_true")
    p.set_defaults(func=cmd_daily_tick)

    p = sub.add_parser("weekly-tick", help="Comando composto: execution-history + recurrence + status")
    p.add_argument("--today", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.add_argument("--history-output", required=True)
    p.add_argument("--history-weeks", type=int, default=4)
    p.add_argument("--min-occurrences", type=int, default=5)
    p.add_argument("--recurrence-weeks", type=int, default=4)
    p.set_defaults(func=cmd_weekly_tick)

    p = sub.add_parser("heartbeat-tick", help="Detecta alertas críticos e emite nudges proativos")
    p.add_argument("--today", required=True, help="Data de hoje (DD/MM)")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--data-dir", required=True)
    p.add_argument("--cooldown-hours", type=int, default=None, help="Override do cooldown do config")
    p.set_defaults(func=cmd_heartbeat_tick)

    p = sub.add_parser("nudges-pending", help="Lista nudges pendentes (não acked)")
    p.add_argument("--data-dir", required=True)
    p.set_defaults(func=cmd_nudges_pending)

    p = sub.add_parser("nudges-ack", help="Marca nudge como acked")
    p.add_argument("--nudge-id", required=True)
    p.add_argument("--data-dir", required=True)
    p.add_argument("--source", default="manual", help="Origem do ack (emit, user, etc.)")
    p.add_argument(
        "--response-kind",
        default=None,
        choices=["agora", "depois", "replanejar", "ignorado"],
        help="Classificação da resposta (spec §11)",
    )
    p.set_defaults(func=cmd_nudges_ack)

    p = sub.add_parser("nudge-delivery", help="Registra status de entrega de um nudge (spec §11)")
    p.add_argument("--nudge-id", required=True)
    p.add_argument("--data-dir", required=True)
    p.add_argument("--status", required=True, choices=["success", "failed", "skipped"])
    p.set_defaults(func=cmd_nudge_delivery)

    p = sub.add_parser("nudge-kpis", help="KPIs dos nudges na janela (spec §16)")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--window-days", type=int, default=7)
    p.set_defaults(func=cmd_nudge_kpis)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
