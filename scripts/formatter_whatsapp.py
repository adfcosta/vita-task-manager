"""Formatador WhatsApp para o render diário."""

from __future__ import annotations

from datetime import date, datetime

try:
    from .models import SuggestedTask, Task, TaskFile
except ImportError:
    from models import SuggestedTask, Task, TaskFile


SEPARATOR = "➖➖➖➖➖➖➖➖➖➖"
STATUS_DISPLAY = {
    "[ ]": "▢",
    "[~]": "⏳",
    "[x]": "☑️",
    "[-]": "❌",
}


def _parse_first_added_date(task: Task) -> date | None:
    for value in (task.first_added_date, task.created_at):
        if not value:
            continue
        try:
            if len(value) >= 10 and value[4] == '-':
                return datetime.fromisoformat(value[:19]).date()
        except Exception:
            continue
    return None


def _age_prefix(task: Task, today: date) -> str:
    first_added = _parse_first_added_date(task)
    if not first_added:
        return ""
    age_days = (today - first_added).days
    if age_days > 14:
        return "👻 "
    if age_days > 7:
        return "⚠️ "
    return ""


def _task_line(task: Task, today: date) -> list[str]:
    prefix = _age_prefix(task, today)
    symbol = STATUS_DISPLAY.get(task.status, task.status)
    lines = [f"{prefix}{symbol} {task.description}"]

    if task.status == "[~]" and task.progress_bar and task.progress_percent is not None:
        progress = f"  [{task.progress_bar}] {task.progress_percent}%"
        if task.progress_done is not None and task.progress_total is not None and task.unit:
            progress += f" ({task.progress_done}/{task.progress_total} {task.unit})"
        lines.append(progress)

    if task.remaining_text:
        lines.append(f"  restam {task.remaining_text}")
    elif task.remaining_value is not None and task.unit:
        lines.append(f"  restam {task.remaining_value} {task.unit}")

    return lines


def _render_open_tasks(taskfile: TaskFile, today: date) -> list[str]:
    lines: list[str] = []
    today_ddmm = today.strftime("%d/%m")
    urgent = [t for t in taskfile.open_tasks if t.status == "[ ]" and t.due_date == today_ddmm]
    in_progress = [t for t in taskfile.open_tasks if t.status == "[~]"]
    pending_red = [t for t in taskfile.open_tasks if t.status == "[ ]" and t.due_date != today_ddmm and t.priority == "🔴"]
    pending_yellow = [t for t in taskfile.open_tasks if t.status == "[ ]" and t.due_date != today_ddmm and t.priority == "🟡"]
    pending_green = [t for t in taskfile.open_tasks if t.status == "[ ]" and t.due_date != today_ddmm and t.priority == "🟢"]

    sections = [
        ("🔴 URGENTE (prazo hoje)", urgent),
        ("🟡 EM ANDAMENTO", in_progress),
        ("🔴 ALTA PRIORIDADE", pending_red),
        ("🟡 MÉDIA PRIORIDADE", pending_yellow),
        ("🟢 BAIXA PRIORIDADE", pending_green),
    ]

    first = True
    for title, tasks in sections:
        if not tasks:
            continue
        if not first:
            lines.append("")
        first = False
        lines.append(title)
        for task in tasks:
            lines.extend(_task_line(task, today))
        lines.append("")

    if not lines:
        return ["✅ Sem tasks abertas no momento.", ""]
    return lines[:-1] if lines[-1] == "" else lines


def _render_brain_dump(taskfile: TaskFile) -> list[str]:
    if not taskfile.brain_dumps:
        return []

    lines = ["🧠 BRAIN DUMP"]
    dumps_with_due = [dump for dump in taskfile.brain_dumps if dump.due_date]
    dumps_without_due = [dump for dump in taskfile.brain_dumps if not dump.due_date]

    if dumps_with_due:
        grouped: dict[str, list[str]] = {}
        for dump in dumps_with_due:
            grouped.setdefault(dump.due_date, []).append(dump.text)
        for due_date, items in grouped.items():
            lines.append(f"⏰ até {due_date}:")
            for item in items:
                for chunk in item.splitlines():
                    lines.append(f"• {chunk}")
            lines.append("")

    if dumps_without_due:
        for dump in dumps_without_due:
            for chunk in dump.text.splitlines():
                lines.append(f"• {chunk}")
        lines.append("")

    lines.append("💡 Dica: Escolha 1 pra virar próxima ação")
    return lines


def _render_suggestions(taskfile: TaskFile) -> list[str]:
    suggestions = taskfile.suggestion_135 or {}
    total = sum(len(items) for items in suggestions.values())
    if total == 0:
        return []

    labels = {
        "big": "🔥 BIG",
        "medium": "⚡ MEDIUM",
        "small": "✅ SMALL",
    }
    lines = ["🎯 SUGESTÃO 1-3-5"]
    for bucket in ("big", "medium", "small"):
        items = suggestions.get(bucket, [])
        for item in items:
            if isinstance(item, SuggestedTask):
                title = item.title
                score = item.score
                explanation = item.explanation
            else:
                title = item.get('title') or item.get('description') or ''
                score = float(item.get('score', 0.0))
                explanation = item.get('explanation', '')
            lines.append(f"{labels[bucket]}: 👉 {title} — score {score:.0f}")
            if explanation:
                lines.append(f"   Por quê: {explanation}")
    lines.append("")
    lines.append("💬 Quer seguir essa sugestão?")
    return lines


def format_task_file_whatsapp(taskfile: TaskFile, today: date) -> str:
    parts: list[str] = [f"📋 {taskfile.title}", ""]
    parts.extend(_render_open_tasks(taskfile, today))

    brain_dump_lines = _render_brain_dump(taskfile)
    suggestion_lines = _render_suggestions(taskfile)

    if taskfile.completed_tasks:
        if parts[-1] != "":
            parts.append("")
        parts.append("✅ CONCLUÍDAS HOJE")
        for task in taskfile.completed_tasks:
            parts.append(f"☑️ {task.description}")

    if taskfile.cancelled_tasks:
        if parts[-1] != "":
            parts.append("")
        parts.append("❌ CANCELADAS/ADIADAS")
        for task in taskfile.cancelled_tasks:
            parts.append(f"❌ {task.description}")

    if brain_dump_lines:
        if parts[-1] != "":
            parts.append("")
        parts.extend([SEPARATOR, "", *brain_dump_lines])

    if suggestion_lines:
        if parts[-1] != "":
            parts.append("")
        parts.extend([SEPARATOR, "", *suggestion_lines])

    return "\n".join(parts).rstrip() + "\n"
