"""Rollover semanal — transição de uma semana para outra."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any

try:
    from .ledger import (
        append_record,
        get_carry_over_dumps,
        get_carry_over_tasks,
        get_ledger_path,
        get_week_start,
        load_ledger,
        make_task_id,
    )
except ImportError:
    from ledger import (
        append_record,
        get_carry_over_dumps,
        get_carry_over_tasks,
        get_ledger_path,
        get_week_start,
        load_ledger,
        make_task_id,
    )


def perform_rollover(
    data_dir: Path,
    today: date,
    year: int,
) -> dict[str, Any]:
    """Executa rollover da semana anterior para a atual.

    1. Fecha ledger da semana anterior (read-only implicito)
    2. Cria novo ledger para semana atual
    3. Carrega tasks abertas/em andamento da semana anterior
    4. Copia para novo ledger com flag carried_from

    Retorna relatório da operação.
    """
    # Ledger anterior (domingo da semana passada)
    current_sunday = get_week_start(today)
    last_sunday = current_sunday - timedelta(days=7)
    old_ledger_path = get_ledger_path(last_sunday, year, data_dir)

    # Ledger atual (semana que começa no domingo corrente)
    new_ledger_path = get_ledger_path(current_sunday, year, data_dir)

    if not old_ledger_path.exists():
        return {
            "performed": False,
            "reason": "Nenhum ledger da semana anterior encontrado",
            "carried_over": 0,
        }

    # Carrega tasks da semana anterior
    old_ledger = load_ledger(old_ledger_path)
    carry_tasks = get_carry_over_tasks(old_ledger)

    # Filtra tasks que já foram migradas (têm _operation: "rollover" no ledger antigo)
    already_rolled = {
        r["id"]
        for r in old_ledger
        if r.get("_operation") == "rollover"
    }
    carry_tasks = [t for t in carry_tasks if t["id"] not in already_rolled]

    if new_ledger_path.exists() and not carry_tasks:
        # Ledger atual já existe e não há tasks pendentes de migração
        return {
            "performed": False,
            "reason": "Ledger da semana atual já existe e todas as tasks foram migradas",
            "carried_over": 0,
        }

    carried = []

    for task in carry_tasks:
        old_id = task["id"]

        # Gera novo ID para a semana atual (nova data de criação)
        new_id = make_task_id(task["description"], today)

        # Cria registro no novo ledger
        record = {
            "type": "task",
            "id": new_id,
            "_operation": "create",
            "status": task.get("status", "[ ]"),
            "priority": task.get("priority", "🟡"),
            "description": task.get("description", ""),
            "source": task.get("source"),
            "due_date": task.get("due_date"),
            "context": task.get("context"),
            "created_at": task.get("created_at"),  # mantém original
            "updated_at": None,
            "completed_at": None,
            "cancelled_at": None,
            "reason": None,
            "progress_percent": task.get("progress_percent"),
            "progress_done": task.get("progress_done"),
            "progress_total": task.get("progress_total"),
            "unit": task.get("unit"),
            "progress_bar": task.get("progress_bar"),
            "remaining_value": task.get("remaining_value"),
            "remaining_text": task.get("remaining_text"),
            "daily_goal_value": task.get("daily_goal_value"),
            "daily_goal_text": task.get("daily_goal_text"),
            "note": task.get("note"),
            "carried_from": old_id,
            "complexity_score": task.get("complexity_score"),
            "complexity_source": task.get("complexity_source"),
            "first_added_date": task.get("first_added_date") or task.get("created_at"),
            "postpone_count": int(task.get("postpone_count") or 0) + 1,
            "energy_required": task.get("energy_required"),
            "score_breakdown": task.get("score_breakdown", {}),
        }

        append_record(new_ledger_path, record)

        # Marca no ledger antigo que foi carregada
        append_record(old_ledger_path, {
            "type": "task",
            "id": old_id,
            "_operation": "rollover",
            "carried_to": new_id,
            "rolled_at": new_ledger_path.name,
        })

        carried.append({
            "old_id": old_id,
            "new_id": new_id,
            "description": task["description"],
        })

    # Migra dumps pendentes
    carry_dumps = get_carry_over_dumps(old_ledger)
    carried_dumps = []

    for dump in carry_dumps:
        old_dump_id = dump["id"]

        append_record(new_ledger_path, {k: v for k, v in {
            "type": "dump",
            "id": old_dump_id,
            "text": dump.get("text"),
            "created_at": dump.get("created_at"),
            "due_date": dump.get("due_date"),
            "carried_from_dump": old_dump_id,
        }.items() if v is not None})

        append_record(old_ledger_path, {
            "type": "dump",
            "id": old_dump_id,
            "_operation": "dump_rollover",
            "carried_to": new_ledger_path.name,
        })

        carried_dumps.append({"id": old_dump_id, "text": dump.get("text")})

    return {
        "performed": True,
        "from": old_ledger_path.name,
        "to": new_ledger_path.name,
        "carried_over": len(carried),
        "tasks": carried,
        "dumps_carried_over": len(carried_dumps),
        "dumps": carried_dumps,
    }
