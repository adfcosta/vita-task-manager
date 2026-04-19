import re
from pathlib import Path

try:
    from .models import AgendaEntry, Task, TaskFile
    from .utils import parse_goal_text, parse_progress_text, parse_value_unit
except ImportError:
    from models import AgendaEntry, Task, TaskFile
    from utils import parse_goal_text, parse_progress_text, parse_value_unit


TASK_RE = re.compile(r"^- \[([ x~\-])\] ([🔴🟡🟢]) (.+)$")
FIELD_RE = re.compile(r"^\s{2}([a-zA-Z_çãõáéíóú]+):\s*(.+)$")
FEEDBACK_ITEM_RE = re.compile(r"^- ([a-zA-Z_]+):\s*(.+)$")
AGENDA_ITEM_RE = re.compile(r"^-\s*(\d{1,2}:\d{2})\s*[—-]\s*(.+)$")


def _status_from_inner(inner: str) -> str:
    if inner == " ":
        return "[ ]"
    return f"[{inner}]"


def parse_task_file(path: str | Path) -> TaskFile:
    lines = Path(path).read_text(encoding="utf-8").splitlines()

    task_file = TaskFile()
    section = None
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()

        if line.startswith("# "):
            task_file.title = line[2:].strip()
            i += 1
            continue

        if line.startswith("## "):
            heading = line[3:].strip().lower()
            if "abertas" in heading:
                section = "open"
            elif "conclu" in heading:
                section = "completed"
            elif "cancel" in heading or "adiad" in heading:
                section = "cancelled"
            elif "compromissos do dia" in heading:
                section = "agenda"
            else:
                section = None
            i += 1
            continue

        if line.strip() == "feedback_do_dia:":
            feedback = {}
            i += 1
            while i < len(lines):
                m = FEEDBACK_ITEM_RE.match(lines[i].rstrip())
                if not m:
                    break
                feedback[m.group(1)] = m.group(2).strip()
                i += 1
            task_file.feedback_do_dia = feedback
            continue

        if section == "agenda":
            agenda_match = AGENDA_ITEM_RE.match(line.strip())
            if agenda_match:
                task_file.compromissos_dia.append(
                    AgendaEntry(time=agenda_match.group(1), description=agenda_match.group(2).strip())
                )
                i += 1
                continue

        task_match = TASK_RE.match(line)
        if task_match:
            task = Task(
                status=_status_from_inner(task_match.group(1)),
                priority=task_match.group(2),
                description=task_match.group(3).strip(),
            )
            i += 1

            while i < len(lines):
                field_line = lines[i].rstrip()
                field_match = FIELD_RE.match(field_line)
                if not field_match:
                    break

                key = field_match.group(1).strip().lower()
                value = field_match.group(2).strip()

                if key == "origem":
                    task.source = value
                elif key == "carried_from":
                    task.carried_from = value
                elif key == "prazo":
                    task.due_date = value
                elif key == "hora_prazo":
                    task.due_time = value
                elif key == "progresso":
                    percent, done, total, unit = parse_progress_text(value)
                    task.progress_percent = percent
                    task.progress_done = done
                    task.progress_total = total
                    task.unit = unit
                elif key == "barra":
                    task.progress_bar = value
                elif key == "restante":
                    task.remaining_text = value
                    try:
                        remaining_value, _unit = parse_value_unit(value)
                        task.remaining_value = remaining_value
                    except Exception:
                        pass
                elif key == "meta":
                    task.daily_goal_text = value
                    try:
                        goal_value, _goal_unit = parse_goal_text(value)
                        task.daily_goal_value = goal_value
                    except Exception:
                        pass
                elif key == "contexto":
                    task.context = value
                elif key == "observacao":
                    task.note = value
                elif key == "criado":
                    task.created_at = value
                elif key == "atualizado_em":
                    task.updated_at = value
                elif key == "concluido_em":
                    task.completed_at = value
                elif key == "motivo":
                    task.reason = value

                i += 1

            if section == "completed" or task.status == "[x]":
                task_file.completed_tasks.append(task)
            elif section == "cancelled" or task.status == "[-]":
                task_file.cancelled_tasks.append(task)
            else:
                task_file.open_tasks.append(task)

            continue

        i += 1

    return task_file
