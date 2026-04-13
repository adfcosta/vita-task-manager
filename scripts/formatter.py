try:
    from .models import Task, TaskFile
    from .calculator import daily_goal_text, progress_text, remaining_text
except ImportError:
    from models import Task, TaskFile
    from calculator import daily_goal_text, progress_text, remaining_text


STATUS_DISPLAY = {
    "[ ]": "▢",
    "[~]": "⏳",
    "[x]": "☑️",
    "[-]": "❌",
}


def _field_lines(task: Task) -> list[str]:
    lines: list[str] = []
    append = lines.append

    if task.source:
        append(f"  origem: {task.source}")

    if task.carried_from:
        append(f"  carried_from: {task.carried_from}")

    if task.due_date:
        append(f"  prazo: {task.due_date}")

    if (
        task.progress_percent is not None
        and task.progress_done is not None
        and task.progress_total is not None
        and task.unit
    ):
        progress_value = progress_text(
            task.progress_percent,
            task.progress_done,
            task.progress_total,
            task.unit,
        )
        if task.status == "[~]" and task.progress_bar:
            append(f"  progresso: {progress_value} {task.progress_bar}")
        else:
            append(f"  progresso: {progress_value}")

    if task.progress_bar and task.status != "[~]":
        append(f"  barra: {task.progress_bar}")

    if task.remaining_text:
        append(f"  restante: {task.remaining_text}")
    elif task.remaining_value is not None and task.unit:
        append(f"  restante: {remaining_text(task.remaining_value, task.unit)}")

    if task.daily_goal_text:
        append(f"  meta: {task.daily_goal_text}")
    elif task.daily_goal_value is not None and task.unit:
        append(f"  meta: {daily_goal_text(task.daily_goal_value, task.unit)}")

    if task.context:
        append(f"  contexto: {task.context}")

    if task.note:
        append(f"  observacao: {task.note}")

    if task.created_at:
        append(f"  criado: {task.created_at}")

    if task.updated_at:
        append(f"  atualizado_em: {task.updated_at}")

    if task.completed_at:
        append(f"  concluido_em: {task.completed_at}")

    if task.reason:
        append(f"  motivo: {task.reason}")

    return lines


def format_task(task: Task) -> str:
    status_symbol = STATUS_DISPLAY.get(task.status, task.status)
    return "\n".join([f"- {status_symbol} {task.priority} {task.description}", *_field_lines(task)])


def format_feedback(feedback: dict[str, str]) -> str:
    if not feedback:
        return ""

    priority_keys = ["panorama", "foco", "alerta", "acao_sugerida"]
    lines = ["feedback_do_dia:"]
    append = lines.append

    for key in priority_keys:
        value = feedback.get(key)
        if value:
            append(f"- {key}: {value}")

    for key, value in feedback.items():
        if key not in priority_keys:
            append(f"- {key}: {value}")

    return "\n".join(lines)


def _format_suggestion_135(task_file: TaskFile) -> list[str]:
    suggestions = task_file.suggestion_135 or {}
    total = sum(len(items) for items in suggestions.values())
    if total == 0:
        return []

    labels = {
        "big": "🔥 Big (1)",
        "medium": "⚡ Medium (3)",
        "small": "✅ Small (5)",
    }

    lines = ["---", "", "## 🎯 Sugestão 1-3-5", ""]
    append = lines.append

    for bucket in ("big", "medium", "small"):
        items = suggestions.get(bucket, [])
        append(f"### {labels[bucket]}")
        append("")
        if not items:
            append("_Sem sugestão nesta faixa._")
            append("")
            continue

        for item in items:
            append(f"- 👉 ({item.position}) {item.title} — score {item.score:.1f}")
            if item.explanation:
                append(f"  motivo: {item.explanation}")
        append("")

    return lines


def _append_task_section(parts: list[str], title: str, tasks: list[Task], empty_message: str) -> None:
    parts.extend([title, ""])
    if not tasks:
        parts.extend([empty_message, ""])
        return

    for task in tasks:
        parts.extend([format_task(task), ""])


def format_task_file(task_file: TaskFile) -> str:
    parts: list[str] = [f"# {task_file.title}", ""]

    _append_task_section(parts, "## Abertas", task_file.open_tasks, "_Sem tasks abertas._")
    _append_task_section(parts, "## Concluídas hoje", task_file.completed_tasks, "_Sem tasks concluídas hoje._")

    if task_file.cancelled_tasks:
        _append_task_section(parts, "## Canceladas/Adiadas hoje", task_file.cancelled_tasks, "")

    if task_file.compromissos_dia:
        parts.extend(["---", "", "## 📅 Compromissos do dia", ""])
        parts.extend(f"- {item.time} — {item.description}" for item in task_file.compromissos_dia)
        parts.append("")

    if task_file.brain_dumps:
        parts.extend(["---", "", "## 🧠 Brain Dump (não são tarefas ainda)", ""])
        for dump in task_file.brain_dumps:
            lines = dump.text.split("\n")
            due_marker = f" [📅 até {dump.due_date}]" if dump.due_date else ""
            parts.append(f"- ▢ ({dump.id}){due_marker} {lines[0]}")
            parts.extend(f"    {line}" for line in lines[1:])
        parts.extend([
            "",
            "> 💡 Dica TDAH: Escolha 1 item para virar próxima ação. O resto pode esperar.",
            "",
        ])

    parts.extend(_format_suggestion_135(task_file))

    if task_file.feedback_do_dia:
        parts.extend(["---", "", format_feedback(task_file.feedback_do_dia), ""])

    return "\n".join(parts).rstrip() + "\n"
