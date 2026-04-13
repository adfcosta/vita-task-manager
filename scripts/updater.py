from pathlib import Path

try:
    from .calculator import (
        build_progress_bar,
        calculate_daily_goal,
        calculate_progress,
        calculate_remaining,
        daily_goal_text,
        remaining_text,
    )
    from .formatter import format_task_file
    from .models import Task, TaskFile
    from .parser import parse_task_file
    from .sorter import sort_task_file
    from .validator import validate_task_file
    from .feedback_input import build_daily_summary, build_feedback_seed, validate_feedback
    from .utils import days_remaining
except ImportError:
    from calculator import (
        build_progress_bar,
        calculate_daily_goal,
        calculate_progress,
        calculate_remaining,
        daily_goal_text,
        remaining_text,
    )
    from formatter import format_task_file
    from models import Task, TaskFile
    from parser import parse_task_file
    from sorter import sort_task_file
    from validator import validate_task_file
    from feedback_input import build_daily_summary, build_feedback_seed, validate_feedback
    from utils import days_remaining


def find_task(task_file: TaskFile, description: str) -> tuple[str, int, Task] | None:
    target = description.strip().lower()

    for section_name, tasks in [
        ("open", task_file.open_tasks),
        ("completed", task_file.completed_tasks),
        ("cancelled", task_file.cancelled_tasks),
    ]:
        for idx, task in enumerate(tasks):
            if task.description.strip().lower() == target:
                return section_name, idx, task

    return None


def _remove_task(task_file: TaskFile, section_name: str, idx: int) -> Task:
    if section_name == "open":
        return task_file.open_tasks.pop(idx)
    if section_name == "completed":
        return task_file.completed_tasks.pop(idx)
    if section_name == "cancelled":
        return task_file.cancelled_tasks.pop(idx)
    raise ValueError(f"Seção inválida: {section_name}")


def add_task(task_file: TaskFile, task: Task) -> TaskFile:
    if task.status == "[x]":
        task_file.completed_tasks.append(task)
    elif task.status == "[-]":
        task_file.cancelled_tasks.append(task)
    else:
        task_file.open_tasks.append(task)
    return task_file


def update_task(task_file: TaskFile, description: str, **updates) -> TaskFile:
    found = find_task(task_file, description)
    if not found:
        raise ValueError(f"Task não encontrada: {description}")

    section_name, idx, task = found

    for key, value in updates.items():
        if not hasattr(task, key):
            raise ValueError(f"Campo inexistente: {key}")
        setattr(task, key, value)

    # mover de seção se status mudou
    if section_name != "completed" and task.status == "[x]":
        _remove_task(task_file, section_name, idx)
        task_file.completed_tasks.append(task)
    elif section_name != "cancelled" and task.status == "[-]":
        _remove_task(task_file, section_name, idx)
        task_file.cancelled_tasks.append(task)
    elif section_name != "open" and task.status in {"[ ]", "[~]"}:
        _remove_task(task_file, section_name, idx)
        task_file.open_tasks.append(task)

    return task_file


def update_progress(
    task_file: TaskFile,
    description: str,
    done: int,
    total: int,
    unit: str,
    today_ddmm: str,
    year: int,
) -> TaskFile:
    found = find_task(task_file, description)
    if not found:
        raise ValueError(f"Task não encontrada: {description}")

    section_name, idx, task = found

    task.status = "[~]" if done < total else "[x]"
    task.progress_done = done
    task.progress_total = total
    task.unit = unit
    task.progress_percent = calculate_progress(done, total)
    task.progress_bar = build_progress_bar(task.progress_percent)

    remaining = calculate_remaining(done, total)
    task.remaining_value = remaining
    task.remaining_text = remaining_text(remaining, unit)

    if task.due_date:
        dr = days_remaining(today_ddmm, task.due_date, year)
        goal = calculate_daily_goal(remaining, dr)
        task.daily_goal_value = goal
        task.daily_goal_text = daily_goal_text(goal, unit)
    else:
        task.daily_goal_value = None
        task.daily_goal_text = None

    if task.status == "[x]":
        task.completed_at = today_ddmm
        task.updated_at = None
        if section_name != "completed":
            _remove_task(task_file, section_name, idx)
            task_file.completed_tasks.append(task)
    else:
        task.updated_at = today_ddmm
        if section_name != "open":
            _remove_task(task_file, section_name, idx)
            task_file.open_tasks.append(task)

    return task_file


def complete_task(task_file: TaskFile, description: str, completed_at: str) -> TaskFile:
    found = find_task(task_file, description)
    if not found:
        raise ValueError(f"Task não encontrada: {description}")

    section_name, idx, task = found
    task.status = "[x]"
    task.completed_at = completed_at
    task.updated_at = None

    if section_name != "completed":
        _remove_task(task_file, section_name, idx)
        task_file.completed_tasks.append(task)

    return task_file


def cancel_task(task_file: TaskFile, description: str, reason: str, updated_at: str) -> TaskFile:
    found = find_task(task_file, description)
    if not found:
        raise ValueError(f"Task não encontrada: {description}")

    section_name, idx, task = found
    task.status = "[-]"
    task.reason = reason
    task.updated_at = updated_at

    if section_name != "cancelled":
        _remove_task(task_file, section_name, idx)
        task_file.cancelled_tasks.append(task)

    return task_file


def refresh_feedback(task_file: TaskFile, today_ddmm: str, year: int) -> TaskFile:
    """
    Atualiza o feedback_do_dia baseado no estado atual das tarefas.
    
    ⚠️ FEEDBACK É OBRIGATÓRIO: toda modificação em tarefas deve
    atualizar o feedback para manter o usuário informado sobre
    prioridades e riscos.
    
    Valida o feedback gerado e lança erro se estiver incompleto.
    """
    summary = build_daily_summary(task_file, today_ddmm, year)
    task_file.feedback_do_dia = build_feedback_seed(summary)
    
    # Validar feedback gerado
    feedback_errors = validate_feedback(task_file.feedback_do_dia)
    if feedback_errors:
        raise ValueError("Feedback inválido:\n- " + "\n- ".join(feedback_errors))
    
    return task_file


def save_task_file(
    path: str,
    task_file: TaskFile,
    today_ddmm: str | None = None,
    year: int | None = None,
    refresh_feedback_block: bool = False,
) -> list[str]:
    """
    Salva o arquivo de tarefas com ordenação e feedback atualizados.
    
    Args:
        path: caminho do arquivo
        task_file: objeto TaskFile a ser salvo
        today_ddmm: data de hoje no formato DD/MM
        year: ano atual
        refresh_feedback_block: se True, atualiza o feedback_do_dia
    
    Returns:
        Lista de erros de validação (vazia se válido)
    
    Raises:
        ValueError: se houver erros de validação no arquivo ou feedback
    """
    if today_ddmm and year:
        sort_task_file(task_file, today_ddmm, year)
        if refresh_feedback_block:
            refresh_feedback(task_file, today_ddmm, year)

    errors = validate_task_file(task_file)
    if errors:
        raise ValueError("Arquivo inválido:\n- " + "\n- ".join(errors))

    Path(path).write_text(format_task_file(task_file), encoding="utf-8")
    return errors


def load_task_file(path: str) -> TaskFile:
    """Carrega arquivo de tarefas do disco."""
    return parse_task_file(path)
