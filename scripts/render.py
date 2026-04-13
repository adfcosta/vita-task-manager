"""Renderização da saída diária limpa a partir do ledger."""

from datetime import date, datetime
from pathlib import Path
from typing import Optional

try:
    from .agenda_parser import parse_agenda_semana, get_entries_for_date as get_agenda_entries
    from .feedback_input import build_daily_summary
    from .ledger import get_latest_feedback, load_ledger
    from .models import AgendaEntry, BrainDumpEntry, SuggestedTask, Task, TaskFile
    from .sorter import sort_open_tasks
    from .suggester import suggest_135
    from .utils import ddmm_to_date
except ImportError:
    from agenda_parser import parse_agenda_semana, get_entries_for_date as get_agenda_entries
    from feedback_input import build_daily_summary
    from ledger import get_latest_feedback, load_ledger
    from models import AgendaEntry, BrainDumpEntry, SuggestedTask, Task, TaskFile
    from sorter import sort_open_tasks
    from suggester import suggest_135
    from utils import ddmm_to_date


TASK_OPEN_STATUSES = {"[ ]", "[~]"}


def _format_iso_to_ddmm_or_ddmm_hhmm(value: Optional[str]) -> Optional[str]:
    """Converte ISO para DD/MM ou DD/MM HH:MM."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
            return dt.strftime("%d/%m")
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return value


def _task_from_ledger(record: dict) -> Task:
    """Converte registro do ledger em objeto Task."""
    return Task(
        status=record.get("status", "[ ]"),
        priority=record.get("priority", "🟡"),
        description=record.get("description", ""),
        due_date=record.get("due_date"),
        progress_percent=record.get("progress_percent"),
        progress_done=record.get("progress_done"),
        progress_total=record.get("progress_total"),
        unit=record.get("unit"),
        progress_bar=record.get("progress_bar"),
        remaining_value=record.get("remaining_value"),
        remaining_text=record.get("remaining_text"),
        daily_goal_value=record.get("daily_goal_value"),
        daily_goal_text=record.get("daily_goal_text"),
        context=record.get("context"),
        note=record.get("note"),
        created_at=_format_iso_to_ddmm_or_ddmm_hhmm(record.get("created_at")),
        updated_at=_format_iso_to_ddmm_or_ddmm_hhmm(record.get("updated_at")),
        completed_at=_format_iso_to_ddmm_or_ddmm_hhmm(record.get("completed_at") or record.get("cancelled_at")),
        reason=record.get("reason"),
        source=record.get("source"),
        carried_from=record.get("carried_from"),
        id=record.get("id"),
        complexity_score=record.get("complexity_score"),
        complexity_source=record.get("complexity_source"),
        first_added_date=record.get("first_added_date"),
        postpone_count=int(record.get("postpone_count") or 0),
        energy_required=record.get("energy_required"),
        score_breakdown=record.get("score_breakdown", {}),
        total_score=record.get("total_score"),
    )


def _same_day_from_iso(value: Optional[str], today: date) -> bool:
    if not value:
        return False
    try:
        return datetime.fromisoformat(value).date() == today
    except Exception:
        return False


def _merge_task_record(current: dict, record: dict) -> None:
    for key, value in record.items():
        if key.startswith("_") or key in {"type", "id"}:
            continue
        if value is not None or key not in current:
            current[key] = value

    if "progress_snapshot" in record:
        current.setdefault("progress_history", []).append(record["progress_snapshot"])


def _collect_ledger_state(
    ledger: list[dict],
    today: date,
) -> tuple[list[Task], list[Task], list[Task], list[BrainDumpEntry]]:
    tasks_by_id: dict[str, dict] = {}
    dumps_by_id: dict[str, dict] = {}

    for record in ledger:
        record_type = record.get("type")

        if record_type == "task":
            task_id = record.get("id")
            if not task_id:
                continue
            current = tasks_by_id.setdefault(task_id, {"id": task_id})
            _merge_task_record(current, record)
            continue

        if record_type == "dump":
            dump_id = record.get("id")
            if not dump_id:
                continue
            current_dump = dumps_by_id.setdefault(dump_id, {})
            current_dump.update(record)

    open_tasks: list[Task] = []
    completed_today: list[Task] = []
    cancelled_today: list[Task] = []

    for task in tasks_by_id.values():
        status = task.get("status", "[ ]")
        if status in TASK_OPEN_STATUSES:
            open_tasks.append(_task_from_ledger(task))
        elif status == "[x]" and _same_day_from_iso(task.get("completed_at"), today):
            completed_today.append(_task_from_ledger(task))
        elif status == "[-]" and _same_day_from_iso(task.get("cancelled_at"), today):
            cancelled_today.append(_task_from_ledger(task))

    brain_dumps: list[BrainDumpEntry] = []
    for dump in dumps_by_id.values():
        if dump.get("converted_to_task"):
            continue

        created_at = dump.get("created_at")
        if not _same_day_from_iso(created_at, today):
            continue

        brain_dumps.append(
            BrainDumpEntry(
                id=dump["id"],
                text=dump["text"],
                created_at=created_at,
                due_date=dump.get("due_date"),
            )
        )

    return open_tasks, completed_today, cancelled_today, brain_dumps


def render_daily(
    ledger_path: Path,
    agenda_semana_path: Optional[Path],
    today_ddmm: str,
    year: int,
) -> tuple[TaskFile, dict]:
    """Gera TaskFile limpo para o dia a partir do ledger.

    Regra D+1:
    - abertas/em andamento sempre aparecem
    - concluídas/canceladas aparecem apenas se aconteceram hoje
    """
    today = ddmm_to_date(today_ddmm, year)
    ledger = load_ledger(ledger_path)

    open_tasks, completed_today, cancelled_today, brain_dumps = _collect_ledger_state(ledger, today)
    open_sorted = sort_open_tasks(open_tasks, today_ddmm, year)

    compromissos: list[AgendaEntry] = []
    if agenda_semana_path and agenda_semana_path.exists():
        try:
            agenda_entries = parse_agenda_semana(agenda_semana_path, year)
            compromissos = get_agenda_entries(agenda_entries, today)
        except Exception:
            compromissos = []

    taskfile = TaskFile(
        title=f"Tasks — {today:%d/%m/%Y}",
        open_tasks=open_sorted,
        completed_tasks=completed_today,
        cancelled_tasks=cancelled_today,
        compromissos_dia=compromissos,
        brain_dumps=brain_dumps,
    )

    if open_sorted and any(not task.score_breakdown.get("final_score") for task in open_sorted):
        suggestions = suggest_135(open_sorted, today)
        taskfile.suggestion_135 = {
            bucket: [
                SuggestedTask(
                    task_id=item.get("id", ""),
                    title=item.get("description", ""),
                    score=float(item.get("score", 0.0)),
                    size_category=item.get("size_category", bucket),
                    explanation=item.get("explanation", ""),
                    position=int(item.get("position", 0)),
                )
                for item in suggestions.get(bucket, [])
            ]
            for bucket in ("big", "medium", "small")
        }

    latest_feedback = get_latest_feedback(ledger, today)
    if latest_feedback:
        taskfile.feedback_do_dia = latest_feedback.get("data", {})

    feedback_seed = build_daily_summary(taskfile, today_ddmm, year)
    return taskfile, feedback_seed
