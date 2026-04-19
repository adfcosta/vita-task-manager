"""Operações de negócio sobre o ledger (CRUD)."""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import re as _re

try:
    from .ledger import (
        _merge_task_records,
        _parse_record_date,
        append_record,
        find_task,
        get_ledger_path,
        get_week_start,
        load_ledger,
        make_task_id,
    )
except ImportError:
    from ledger import (
        _merge_task_records,
        _parse_record_date,
        append_record,
        find_task,
        get_ledger_path,
        get_week_start,
        load_ledger,
        make_task_id,
    )


TIMEZONE_OFFSET = timedelta(hours=-3)  # America/Maceio = UTC-3
DEFAULT_WIP_LIMIT = 2
DEFAULT_WIP_WARNING = (
    "Você já tem 2 tarefas em andamento. Que tal terminar uma antes de começar outra?"
)


def _now_iso() -> str:
    """Retorna timestamp ISO atual no fuso America/Maceio (UTC-3)."""
    return datetime.now().replace(microsecond=0).isoformat()


def _date_from_ddmm(date_str: str, year: int) -> date:
    """Converte DD/MM em date."""
    try:
        from .utils import ddmm_to_date
    except ImportError:
        from utils import ddmm_to_date
    return ddmm_to_date(date_str, year)


def _compact_record(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if v is not None}


def _load_word_weights_safe(ledger_path: Path) -> dict[str, float]:
    """Carrega word_weights.json do data_dir. Retorna {} se indisponível."""
    import json as _json
    # data_dir é o pai do diretório historico que contém o ledger
    data_dir = ledger_path.parent.parent
    weights_path = data_dir / "word_weights.json"
    if not weights_path.exists():
        return {}
    try:
        data = _json.loads(weights_path.read_text(encoding="utf-8"))
        return data.get("weights", {})
    except (ValueError, KeyError, OSError):
        return {}


_STOPWORDS = frozenset({
    "a", "o", "as", "os", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "um", "uma", "uns", "umas",
    "e", "ou", "com", "por", "para", "pra", "pro", "que", "se",
})


def _extract_words(text: str) -> set[str]:
    """Extrai palavras significativas de um texto, removendo acentos e stopwords."""
    text = text.lower().strip()
    for old, new in [('á', 'a'), ('à', 'a'), ('â', 'a'), ('ã', 'a'),
                     ('é', 'e'), ('ê', 'e'), ('í', 'i'), ('ó', 'o'),
                     ('ô', 'o'), ('õ', 'o'), ('ú', 'u'), ('ç', 'c')]:
        text = text.replace(old, new)
    words = set(_re.findall(r'[a-z0-9]+', text))
    return words - _STOPWORDS


def _weighted_similarity(
    words_a: set[str],
    words_b: set[str],
    weights: dict[str, float],
) -> float:
    """Calcula similaridade ponderada entre dois conjuntos de palavras.

    Retorna o maior ratio (em qualquer direção) usando pesos por palavra.
    Fallback pra peso 1.0 se a palavra não tiver peso registrado.
    """
    if not words_a or not words_b:
        return 0.0

    default_weight = 1.0
    overlap = words_a & words_b
    if not overlap:
        return 0.0

    overlap_weight = sum(weights.get(w, default_weight) for w in overlap)
    weight_a = sum(weights.get(w, default_weight) for w in words_a)
    weight_b = sum(weights.get(w, default_weight) for w in words_b)

    ratio_a = overlap_weight / weight_a if weight_a > 0 else 0.0
    ratio_b = overlap_weight / weight_b if weight_b > 0 else 0.0

    return max(ratio_a, ratio_b)


def _find_similar_open_tasks(
    ledger: list[dict[str, Any]],
    new_description: str,
    today: date,
    word_weights: Optional[dict[str, float]] = None,
) -> list[dict[str, Any]]:
    """Encontra tasks abertas similares por similaridade ponderada.

    Busca tasks abertas criadas hoje ou ontem cujas palavras significativas
    tenham similaridade >= 50% com a nova descrição.

    Se word_weights for fornecido, usa pesos por palavra (3 fatores:
    distintividade × evitação × tempo de resolução). Caso contrário,
    todas as palavras têm peso 1.0 (comportamento original).
    """
    new_words = _extract_words(new_description)
    if not new_words:
        return []

    weights = word_weights or {}
    yesterday = today - timedelta(days=1)
    merged = _merge_task_records(ledger)
    similar = []

    for task in merged.values():
        status = task.get("status", "")
        if status in ("[x]", "[-]"):
            continue

        created = _parse_record_date(task.get("created_at"))
        if not created or created < yesterday:
            continue

        existing_words = _extract_words(task.get("description", ""))
        if not existing_words:
            continue

        similarity = _weighted_similarity(new_words, existing_words, weights)

        if similarity >= 0.5:
            similar.append({
                "task_id": task.get("id"),
                "description": task.get("description"),
                "similarity": round(similarity, 2),
            })

    return similar


def add_task(
    ledger_path: Path,
    description: str,
    priority: str,
    today_ddmm: str,
    year: int,
    source: Optional[str] = None,
    due_date: Optional[str] = None,
    due_time: Optional[str] = None,
    context: Optional[str] = None,
    carried_from: Optional[str] = None,
    allow_duplicate: bool = False,
    alert_on_miss: bool = False,
) -> dict[str, Any]:
    """Adiciona nova task ao ledger."""
    created_date = _date_from_ddmm(today_ddmm, year)
    ledger = load_ledger(ledger_path)
    task_id = make_task_id(description, created_date, ledger)

    # Detecção de duplicatas (apenas warning, não bloqueia)
    warning = None
    if not allow_duplicate:
        # Carrega pesos de palavra se disponíveis
        word_weights = _load_word_weights_safe(ledger_path)
        similar = _find_similar_open_tasks(ledger, description, created_date, word_weights)
        if similar:
            warning = {
                "type": "duplicate_suspect",
                "similar_to": similar,
                "hint": "Considere ledger-update em vez de criar task nova.",
            }

    append_record(ledger_path, _compact_record({
        "type": "task",
        "id": task_id,
        "_operation": "create",
        "status": "[ ]",
        "priority": priority,
        "description": description,
        "source": source,
        "due_date": due_date,
        "due_time": due_time,
        "context": context,
        "created_at": _now_iso(),
        "carried_from": carried_from,
        "first_added_date": created_date.isoformat(),
        "postpone_count": 0,
        "score_breakdown": {},
        "alert_on_miss": alert_on_miss if alert_on_miss else None,
    }))

    result: dict[str, Any] = {
        "ok": True,
        "action": "add",
        "task_id": task_id,
        "description": description,
    }
    if warning:
        result["warning"] = warning
    return result


def get_wip_count(tasks: list[dict[str, Any]]) -> int:
    """Conta quantas tasks estão em andamento ([~])."""
    return sum(1 for task in tasks if task.get("status") == "[~]")


def can_start_new_task(tasks: list[dict[str, Any]], limit: int = DEFAULT_WIP_LIMIT) -> bool:
    """Retorna se ainda é permitido iniciar nova task."""
    return get_wip_count(tasks) < limit


def _build_wip_warning(current_wip: int, limit: int) -> str | None:
    if current_wip < limit:
        return None
    if limit == DEFAULT_WIP_LIMIT and current_wip == DEFAULT_WIP_LIMIT:
        return DEFAULT_WIP_WARNING
    tarefa_label = "tarefas" if current_wip != 1 else "tarefa"
    return (
        f"Você já tem {current_wip} {tarefa_label} em andamento. "
        "Que tal terminar uma antes de começar outra?"
    )


def check_wip_limit(ledger_path: Path, limit: int = DEFAULT_WIP_LIMIT) -> dict[str, Any]:
    """Retorna status atual do WIP limit a partir do ledger."""
    try:
        from .ledger import get_all_active_tasks
    except ImportError:
        from ledger import get_all_active_tasks

    tasks = get_all_active_tasks(load_ledger(ledger_path))
    current_wip = get_wip_count(tasks)
    can_start = current_wip < limit

    return {
        "ok": True,
        "current_wip": current_wip,
        "limit": limit,
        "can_start": can_start,
        "warning": _build_wip_warning(current_wip, limit),
    }


def start_task(
    ledger_path: Path,
    task_id: str,
    today_ddmm: str,
    limit: int = DEFAULT_WIP_LIMIT,
) -> dict[str, Any]:
    """Inicia task pendente, respeitando o WIP limit."""
    try:
        from .ledger import get_all_active_tasks
    except ImportError:
        from ledger import get_all_active_tasks

    ledger = load_ledger(ledger_path)
    task = find_task(ledger, task_id)

    if not task:
        return {"ok": False, "error": f"Task não encontrada: {task_id}"}

    current_tasks = get_all_active_tasks(ledger)
    current_wip = get_wip_count(current_tasks)

    if task.get("status") == "[~]":
        return {
            "ok": True,
            "action": "start",
            "task_id": task_id,
            "status": "[~]",
            "current_wip": current_wip,
            "limit": limit,
            "can_start": True,
            "warning": None,
            "message": "Task já estava em andamento.",
        }

    if task.get("status") != "[ ]":
        return {
            "ok": False,
            "error": f"Task não pode ser iniciada no status atual: {task.get('status')}",
        }

    if current_wip >= limit:
        return {
            "ok": False,
            "action": "start",
            "task_id": task_id,
            "current_wip": current_wip,
            "limit": limit,
            "can_start": False,
            "warning": _build_wip_warning(current_wip, limit),
            "message": "Finalize uma task em andamento antes de iniciar outra.",
        }

    record = {
        "type": "task",
        "id": task_id,
        "_operation": "start",
        "status": "[~]",
        "updated_at": _now_iso(),
    }
    append_record(ledger_path, record)

    return {
        "ok": True,
        "action": "start",
        "task_id": task_id,
        "status": "[~]",
        "current_wip": current_wip + 1,
        "limit": limit,
        "can_start": True,
        "warning": None,
    }


def update_progress(
    ledger_path: Path,
    task_id: str,
    done: int,
    total: int,
    unit: str,
    today_ddmm: str,
    year: int,
) -> dict[str, Any]:
    """Atualiza progresso de task existente."""
    try:
        from .calculator import calculate_progress, build_progress_bar
        from .utils import days_remaining, ceil_div
    except ImportError:
        from calculator import calculate_progress, build_progress_bar
        from utils import days_remaining, ceil_div

    ledger = load_ledger(ledger_path)
    task = find_task(ledger, task_id)

    if not task:
        return {"ok": False, "error": f"Task não encontrada: {task_id}"}

    percent = calculate_progress(done, total)
    remaining = total - done

    # Calcula meta diária se houver prazo
    daily_goal = None
    daily_goal_text = None
    due = task.get("due_date")
    if due and remaining > 0:
        try:
            dr = days_remaining(today_ddmm, due, year)
            if dr > 0:
                daily_goal = ceil_div(remaining, dr)
                daily_goal_text = f"{daily_goal} {unit}/dia"
        except:
            pass

    # Determina novo status
    new_status = "[x]" if done >= total else "[~]"

    # Snapshot para histórico
    progress_snapshot = {
        "at": _now_iso(),
        "done": done,
        "total": total,
        "unit": unit,
        "percent": percent,
    }

    timestamp = _now_iso()
    append_record(ledger_path, _compact_record({
        "type": "task",
        "id": task_id,
        "_operation": "progress",
        "status": new_status,
        "progress_done": done,
        "progress_total": total,
        "progress_percent": percent,
        "progress_bar": build_progress_bar(percent),
        "unit": unit,
        "remaining_value": remaining,
        "remaining_text": f"{remaining} {unit}",
        "daily_goal_value": daily_goal,
        "daily_goal_text": daily_goal_text,
        "updated_at": timestamp,
        "completed_at": timestamp if done >= total else None,
        "progress_snapshot": progress_snapshot,
    }))

    return {
        "ok": True,
        "action": "progress",
        "task_id": task_id,
        "new_status": new_status,
        "percent": percent,
    }


def complete_task(
    ledger_path: Path,
    task_id: str,
    today_ddmm: str,
) -> dict[str, Any]:
    """Marca task como concluída."""
    ledger = load_ledger(ledger_path)
    task = find_task(ledger, task_id)

    if not task:
        return {"ok": False, "error": f"Task não encontrada: {task_id}"}

    append_record(ledger_path, _compact_record({
        "type": "task",
        "id": task_id,
        "_operation": "complete",
        "status": "[x]",
        "completed_at": _now_iso(),
        "updated_at": None,
    }))

    return {
        "ok": True,
        "action": "complete",
        "task_id": task_id,
    }


def cancel_task(
    ledger_path: Path,
    task_id: str,
    reason: str,
    today_ddmm: str,
) -> dict[str, Any]:
    """Marca task como cancelada."""
    ledger = load_ledger(ledger_path)
    task = find_task(ledger, task_id)

    if not task:
        return {"ok": False, "error": f"Task não encontrada: {task_id}"}

    record = {
        "type": "task",
        "id": task_id,
        "_operation": "cancel",
        "status": "[-]",
        "cancelled_at": _now_iso(),
        "updated_at": _now_iso(),
        "reason": reason,
    }

    append_record(ledger_path, record)

    return {
        "ok": True,
        "action": "cancel",
        "task_id": task_id,
    }


def update_task(
    ledger_path: Path,
    task_id: str,
    today_ddmm: str,
    description: Optional[str] = None,
    context: Optional[str] = None,
    priority: Optional[str] = None,
    due_date: Optional[str] = None,
    due_time: Optional[str] = None,
) -> dict[str, Any]:
    """Atualiza campos de uma task existente sem criar duplicata.

    Só os campos passados (não-None) são alterados. O merge de estado
    em _merge_task_records já faz o fold correto — basta appendar
    um registro com _operation: "update" e os campos novos.
    """
    ledger = load_ledger(ledger_path)
    task = find_task(ledger, task_id)

    if not task:
        return {"ok": False, "error": f"Task não encontrada: {task_id}"}

    updates: dict[str, Any] = {}
    if description is not None:
        updates["description"] = description
    if context is not None:
        updates["context"] = context
    if priority is not None:
        updates["priority"] = priority
    if due_date is not None:
        updates["due_date"] = due_date
    if due_time is not None:
        updates["due_time"] = due_time

    if not updates:
        return {"ok": False, "error": "Nenhum campo para atualizar."}

    record: dict[str, Any] = {
        "type": "task",
        "id": task_id,
        "_operation": "update",
        "updated_at": _now_iso(),
        **updates,
    }

    append_record(ledger_path, record)

    return {
        "ok": True,
        "action": "update",
        "task_id": task_id,
        "updated_fields": list(updates.keys()),
    }


def _entry_hash(description: str, time_range: str | None) -> str:
    """Gera hash normalizada para deduplicação robusta."""
    import hashlib
    normalized = f"{description.lower().strip()}|{time_range or ''}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def sync_fixed_agenda(
    rotina_path: Path,
    ledger_path: Path,
    today_ddmm: str,
    year: int,
) -> dict[str, Any]:
    """Sincroniza rotina do dia e regras de recorrência no ledger.

    Injeta entradas de rotina.md e tasks de recurrence_rules ativas
    no ledger do dia atual. Deduplica por hash(description + time_range).
    """
    try:
        from .fixed_parser import parse_rotina, get_entries_for_date
    except ImportError:
        from fixed_parser import parse_rotina, get_entries_for_date

    try:
        from .recurrence import get_active_recurrence_rules, get_rules_for_weekday
    except ImportError:
        from recurrence import get_active_recurrence_rules, get_rules_for_weekday

    created_date = _date_from_ddmm(today_ddmm, year)

    # Carrega entradas da rotina
    rotina_entries = parse_rotina(rotina_path)
    today_entries = get_entries_for_date(rotina_entries, created_date)

    # Carrega ledger para deduplicação
    ledger = load_ledger(ledger_path)

    # Constrói set de hashes existentes (rotina + recurrence)
    existing_hashes = {
        _entry_hash(r.get("description", ""), r.get("context"))
        for r in ledger
        if r.get("type") == "task" and r.get("source") in ("rotina", "recurrence")
    }

    rotina_inserted = []
    rotina_skipped = []

    for entry in today_entries:
        entry_hash = _entry_hash(entry.description, entry.time_range)

        if entry_hash in existing_hashes:
            rotina_skipped.append(entry.description)
            continue

        # Cria task
        result = add_task(
            ledger_path=ledger_path,
            description=entry.description,
            priority=entry.priority,
            today_ddmm=today_ddmm,
            year=year,
            source="rotina",
            context=entry.time_range,
            alert_on_miss=getattr(entry, "alert_on_miss", False),
        )

        if result["ok"]:
            rotina_inserted.append(entry.description)
            existing_hashes.add(entry_hash)

    # Injeta tasks de regras de recorrência ativas
    recurrence_inserted = []
    recurrence_skipped = []

    active_rules = get_active_recurrence_rules(ledger)
    weekday = created_date.weekday()  # 0=Monday ... 6=Sunday
    todays_rules = get_rules_for_weekday(active_rules, weekday)

    for rule in todays_rules:
        desc = rule.get("description", "")
        time_range = rule.get("time_range")
        entry_hash = _entry_hash(desc, time_range)

        if entry_hash in existing_hashes:
            recurrence_skipped.append(desc)
            continue

        result = add_task(
            ledger_path=ledger_path,
            description=desc,
            priority=rule.get("priority", "🟡"),
            today_ddmm=today_ddmm,
            year=year,
            source="recurrence",
            context=time_range,
            allow_duplicate=True,
        )

        if result["ok"]:
            recurrence_inserted.append(desc)
            existing_hashes.add(entry_hash)

    # Retrocompatível: inserted/skipped agregam tudo
    all_inserted = rotina_inserted + recurrence_inserted
    all_skipped = rotina_skipped + recurrence_skipped

    return {
        "ok": True,
        "action": "sync_fixed",
        "inserted": all_inserted,
        "skipped": all_skipped,
        "sources": {
            "rotina": {
                "inserted": len(rotina_inserted),
                "skipped": len(rotina_skipped),
            },
            "recurrence": {
                "inserted": len(recurrence_inserted),
                "skipped": len(recurrence_skipped),
            },
        },
    }


def store_feedback(
    ledger_path: Path,
    feedback_data: dict[str, str],
    today_ddmm: str,
) -> dict[str, Any]:
    """Armazena feedback gerado pela Vita no ledger.

    feedback_data deve conter: panorama, foco, alerta, acao_sugerida
    """
    required = ["panorama", "foco", "alerta", "acao_sugerida"]
    missing = [f for f in required if f not in feedback_data or not feedback_data[f]]

    if missing:
        return {
            "ok": False,
            "error": f"Campos obrigatórios ausentes: {', '.join(missing)}"
        }

    record = {
        "type": "feedback",
        "timestamp": _now_iso(),
        "data": {
            "panorama": feedback_data["panorama"],
            "foco": feedback_data["foco"],
            "alerta": feedback_data["alerta"],
            "acao_sugerida": feedback_data["acao_sugerida"],
        }
    }

    append_record(ledger_path, record)

    return {
        "ok": True,
        "action": "store_feedback",
        "timestamp": record["timestamp"],
    }


def brain_dump(
    ledger_path: Path,
    text: str,
    today_ddmm: str,
    year: int,
    due_date: Optional[str] = None,
) -> dict[str, Any]:
    """Captura rápida de sobrecarga mental — brain dump TDAH.

    Cada item do dump pode ser promovido para task depois.
    due_date pode ser: 'DD/MM' (data específica) ou '+N' (N dias a partir de hoje)
    """
    from datetime import datetime, timedelta

    created_date = _date_from_ddmm(today_ddmm, year)
    ledger = load_ledger(ledger_path)

    # Normaliza due_date se for relativo (+N)
    # Formato de saída: DD/MM (compatível com resto do sistema)
    normalized_due = due_date
    if due_date and due_date.startswith("+"):
        try:
            days = int(due_date[1:])
            due_dt = created_date + timedelta(days=days)
            normalized_due = due_dt.strftime("%d/%m")
        except ValueError:
            normalized_due = None
    elif due_date and len(due_date) == 10 and due_date.count("/") == 2:
        # Converte DD/MM/YYYY → DD/MM (assume ano atual do contexto)
        try:
            normalized_due = due_date[:5]  # Pega só DD/MM
        except Exception:
            normalized_due = due_date

    # Gera ID sequencial para dumps do dia
    dump_count = sum(
        1 for r in ledger
        if r.get("type") == "dump" and r.get("created_at", "").startswith(f"{created_date:%Y-%m-%d}")
    )
    dump_id = f"{created_date:%Y%m%d}_dump_{dump_count + 1:03d}"

    record: dict[str, Any] = {
        "type": "dump",
        "id": dump_id,
        "text": text,
        "created_at": _now_iso(),
    }
    if normalized_due:
        record["due_date"] = normalized_due

    append_record(ledger_path, record)

    return {
        "ok": True,
        "action": "brain_dump",
        "dump_id": dump_id,
        "text": text,
        "due_date": normalized_due,
    }


def dump_to_task(
    ledger_path: Path,
    dump_id: str,
    extracted_item: str,
    today_ddmm: str,
    year: int,
    priority: str = "🟡",
    next_action: Optional[str] = None,
    due_date: Optional[str] = None,
) -> dict[str, Any]:
    """Promove um item do brain dump para task formal.

    O item extraído vira descrição da task; o dump original é marcado como convertido.
    Se due_date não fornecido, usa o do dump original (se existir).
    """
    ledger = load_ledger(ledger_path)

    # Encontra dump (último registro com esse ID)
    dump_record = None
    for r in ledger:
        if r.get("type") == "dump" and r.get("id") == dump_id:
            dump_record = r

    if not dump_record:
        return {"ok": False, "error": f"Dump não encontrado: {dump_id}"}

    # Usa due_date do dump se não foi sobrescrito
    task_due_date = due_date if due_date else dump_record.get("due_date")

    # Cria task
    result = add_task(
        ledger_path=ledger_path,
        description=extracted_item,
        priority=priority,
        today_ddmm=today_ddmm,
        year=year,
        source="brain_dump",
        context=next_action,
        due_date=task_due_date,
    )

    if not result["ok"]:
        return result

    # Marca dump como convertido
    append_record(ledger_path, {
        "type": "dump",
        "id": dump_id,
        "_operation": "convert",
        "converted_to_task": result["task_id"],
        "converted_at": _now_iso(),
    })

    return {
        "ok": True,
        "action": "dump_to_task",
        "dump_id": dump_id,
        "task_id": result["task_id"],
        "description": extracted_item,
        "due_date": task_due_date,
    }
