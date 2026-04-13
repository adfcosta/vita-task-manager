"""Engine de ledger JSONL para o vita-task-manager.

O ledger é append-only, semanal (domingo a sábado), e serve como fonte de verdade.
Cada registro é uma linha JSON com tipo 'task' ou 'feedback'.
"""

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

TIMEZONE = "America/Maceio"  # UTC-3


def _slugify(text: str) -> str:
    """Converte descrição em slug seguro para ID."""
    text = text.lower().strip()
    text = re.sub(r'[àáâãä]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[ìíîï]', 'i', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'ç', 'c', text)
    text = re.sub(r'[^a-z0-9_]+', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')[:50]


def _task_record_items(record: dict[str, Any]):
    return (
        (k, v)
        for k, v in record.items()
        if not k.startswith("_") and k not in {"type", "id"}
    )


def _parse_record_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except Exception:
        return None


def _merge_task_records(
    ledger: list[dict[str, Any]],
    as_of_date: Optional[date] = None,
) -> dict[str, dict[str, Any]]:
    tasks_by_id: dict[str, dict[str, Any]] = {}

    for record in ledger:
        if record.get("type") != "task":
            continue

        if as_of_date is not None:
            created_date = _parse_record_date(record.get("created_at"))
            if created_date and created_date > as_of_date:
                continue

        task_id = record.get("id")
        if not task_id:
            continue

        current = tasks_by_id.get(task_id)
        if current is None:
            current = {"id": task_id}
            tasks_by_id[task_id] = current

        for key, value in _task_record_items(record):
            current[key] = value

        if "progress_snapshot" in record:
            current.setdefault("progress_history", []).append(record["progress_snapshot"])

    return tasks_by_id


def make_task_id(description: str, created_date: date, ledger: list[dict] | None = None) -> str:
    """Gera ID único de task: YYYYMMDD_slug ou YYYYMMDD_slug_2 se colidir."""
    base = f"{created_date:%Y%m%d}_{_slugify(description)}"
    if ledger is None:
        return base

    existing_ids = {r.get("id") for r in ledger if r.get("type") == "task"}
    if base not in existing_ids:
        return base

    for suffix in range(2, 1000):
        candidate = f"{base}_{suffix}"
        if candidate not in existing_ids:
            return candidate
    raise ValueError(f"Não foi possível gerar ID único para: {description}")


def get_week_start(today: date) -> date:
    """Retorna domingo da semana (início)."""
    days_since_sunday = (today.weekday() + 1) % 7
    return today - timedelta(days=days_since_sunday)


def get_week_end(today: date) -> date:
    """Retorna sábado da semana (fim)."""
    return get_week_start(today) + timedelta(days=6)


def get_ledger_filename(today: date) -> str:
    """Gera nome do arquivo de ledger: DDMMYY_DDMMYY_bruto.jsonl"""
    start = get_week_start(today)
    end = get_week_end(today)
    return f"{start:%d%m%y}_{end:%d%m%y}_bruto.jsonl"


def get_ledger_path(today: date, year: int, data_dir: Path) -> Path:
    """Retorna Path completo do ledger da semana."""
    if isinstance(today, str):
        try:
            from .utils import ddmm_to_date
        except ImportError:
            from utils import ddmm_to_date
        today = ddmm_to_date(today, year)
    return data_dir / "historico" / get_ledger_filename(today)


def load_ledger(path: Path) -> list[dict[str, Any]]:
    """Carrega ledger JSONL como lista de dicts."""
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _compute_checksum(record: dict) -> str:
    """Gera checksum SHA256 curto do registro."""
    clean = {k: v for k, v in record.items() if not k.startswith("_")}
    data = json.dumps(clean, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(data.encode()).hexdigest()[:12]


def append_record(path: Path, record: dict[str, Any]) -> None:
    """Append atômico de registro no ledger com metadados de auditoria."""
    import os
    import warnings

    is_test_path = "test" in str(path).lower() or "tmp" in str(path).lower()
    is_test_mode = os.environ.get("VITA_TEST_MODE") == "1"

    if is_test_mode and not is_test_path:
        warnings.warn(f"⚠️  Tentativa de escrever em path de produção durante teste: {path}")
        path = path.parent / f"TEST_{path.name}"

    record["_writer"] = "cli"
    record["_checksum"] = _compute_checksum(record)
    record["_appended_at"] = datetime.now().isoformat()

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def find_task(ledger: list[dict], task_id: str) -> Optional[dict]:
    """Encontra task por ID no ledger (última versão)."""
    for record in reversed(ledger):
        if record.get("type") == "task" and record.get("id") == task_id:
            return record
    return None


def find_all_task_versions(ledger: list[dict], task_id: str) -> list[dict]:
    """Retorna todas as versões de uma task (para histórico)."""
    return [r for r in ledger if r.get("type") == "task" and r.get("id") == task_id]


def get_current_task_state(ledger: list[dict], task_id: str) -> Optional[dict]:
    """Retorna estado atual mergeado de todas as versões da task."""
    return _merge_task_records(ledger).get(task_id)


def get_all_active_tasks(ledger: list[dict], as_of_date: Optional[date] = None) -> list[dict]:
    """Retorna todas as tasks ativas (não concluídas/canceladas) até a data.

    Se as_of_date é None, retorna estado atual.
    """
    active: list[dict[str, Any]] = []

    for task in _merge_task_records(ledger, as_of_date).values():
        status = task.get("status", "[ ]")
        if status not in ("[x]", "[-]"):
            active.append(task)
            continue

        if as_of_date is None:
            continue

        completed = task.get("completed_at") or task.get("cancelled_at")
        if _parse_record_date(completed) == as_of_date:
            active.append(task)

    return active


def get_tasks_completed_on(ledger: list[dict], on_date: date) -> list[dict]:
    """Retorna tasks concluídas/canceladas especificamente na data."""
    completed: list[dict[str, Any]] = []

    for task in _merge_task_records(ledger).values():
        status = task.get("status")
        if status == "[x]":
            timestamp = task.get("completed_at")
        elif status == "[-]":
            timestamp = task.get("cancelled_at")
        else:
            continue

        if _parse_record_date(timestamp) == on_date:
            completed.append(task)

    return completed


def get_latest_feedback(ledger: list[dict], on_date: Optional[date] = None) -> Optional[dict]:
    """Retorna último feedback do dia (ou último absoluto se sem data)."""
    if on_date is None:
        for record in reversed(ledger):
            if record.get("type") == "feedback":
                return record
        return None

    for record in reversed(ledger):
        if record.get("type") != "feedback":
            continue
        if _parse_record_date(record.get("timestamp")) == on_date:
            return record
    return None


def get_all_feedback_for_day(ledger: list[dict], on_date: date) -> list[dict]:
    """Retorna todos os feedbacks do dia (série temporal)."""
    return [
        record
        for record in ledger
        if record.get("type") == "feedback"
        and _parse_record_date(record.get("timestamp")) == on_date
    ]


def needs_rollover(current_ledger_path: Path, today: date) -> bool:
    """Verifica se precisa de rollover (domingo e ledger ainda é da semana anterior)."""
    if not current_ledger_path.exists():
        return False

    if today.weekday() != 6:
        return False

    match = re.search(r'(\d{6})_(\d{6})_bruto\.jsonl', current_ledger_path.name)
    if not match:
        return False

    start_str = match.group(1)
    start_date = datetime.strptime(start_str, "%d%m%y").date()
    current_week_sunday = get_week_start(today)
    return start_date != current_week_sunday


def get_carry_over_tasks(ledger: list[dict]) -> list[dict]:
    """Retorna tasks que devem ser carregadas para próxima semana (abertas ou em andamento)."""
    return [
        task
        for task in _merge_task_records(ledger).values()
        if task.get("status") in ("[ ]", "[~]")
    ]


def get_changes_since(ledger: list[dict], since: datetime) -> list[dict]:
    """Retorna todas as operações CRUD desde o timestamp."""
    changes = []
    for record in ledger:
        timestamp = record.get("_appended_at") or record.get("created_at")
        try:
            if timestamp and datetime.fromisoformat(timestamp) > since:
                changes.append({
                    "action": record.get("_operation", "unknown"),
                    "task_id": record.get("id"),
                    "description": record.get("description"),
                    "at": timestamp,
                })
        except Exception:
            continue
    return changes
