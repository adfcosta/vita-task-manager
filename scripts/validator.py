try:
    from .calculator import calculate_progress
    from .models import Task, TaskFile, VALID_PRIORITIES, VALID_STATUSES
    from .utils import is_valid_ddmm
except ImportError:
    from calculator import calculate_progress
    from models import Task, TaskFile, VALID_PRIORITIES, VALID_STATUSES
    from utils import is_valid_ddmm


def validate_task(task: Task) -> list[str]:
    errors: list[str] = []

    if task.status not in VALID_STATUSES:
        errors.append(f"Status inválido em '{task.description}': {task.status}")

    if task.priority not in VALID_PRIORITIES:
        errors.append(f"Prioridade inválida em '{task.description}': {task.priority}")

    if not task.description.strip():
        errors.append("Task com descrição vazia")

    for label, value in [
        ("prazo", task.due_date),
        ("criado", task.created_at),
        ("atualizado_em", task.updated_at),
        ("concluido_em", task.completed_at),
    ]:
        if value and not is_valid_ddmm(value):
            errors.append(f"Data inválida em '{task.description}' para {label}: {value}")

    has_progress_bits = any(
        x is not None
        for x in [task.progress_percent, task.progress_done, task.progress_total]
    )
    if has_progress_bits:
        if task.progress_done is None or task.progress_total is None or not task.unit:
            errors.append(f"Progresso incompleto em '{task.description}'")
        else:
            if task.progress_total <= 0:
                errors.append(f"Total deve ser > 0 em '{task.description}'")
            if task.progress_done < 0:
                errors.append(f"Done deve ser >= 0 em '{task.description}'")
            if task.progress_done > task.progress_total:
                errors.append(f"Done > total em '{task.description}'")
            expected_percent = calculate_progress(task.progress_done, task.progress_total)
            if task.progress_percent is not None and task.progress_percent != expected_percent:
                errors.append(
                    f"Percentual inconsistente em '{task.description}': "
                    f"{task.progress_percent}% != {expected_percent}%"
                )

    if task.status == "[x]" and not task.completed_at:
        errors.append(f"Task concluída sem concluido_em: '{task.description}'")

    if task.status == "[-]" and not task.reason:
        errors.append(f"Task cancelada/adiada sem motivo: '{task.description}'")

    return errors


def validate_task_file(task_file: TaskFile) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()

    for task in task_file.all_tasks:
        errors.extend(validate_task(task))
        desc = task.description.strip().lower()
        if desc in seen:
            errors.append(f"Descrição duplicada: '{task.description}'")
        seen.add(desc)

    return errors