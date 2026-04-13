"""Detecção de padrões de recorrência e gestão de regras de recorrência.

Analisa o histórico de ledger JSONL para identificar tasks que se repetem
com frequência e permite criar/desativar regras de recorrência automática.
"""

import re as _re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    from .ledger import (
        _merge_task_records,
        _parse_record_date,
        _slugify,
        append_record,
        get_ledger_path,
        get_week_start,
        load_ledger,
    )
except ImportError:
    from ledger import (
        _merge_task_records,
        _parse_record_date,
        _slugify,
        append_record,
        get_ledger_path,
        get_week_start,
        load_ledger,
    )

try:
    from .ledger_ops import _extract_words
except ImportError:
    from ledger_ops import _extract_words


WEEKDAY_NAMES_PT = [
    "segundas", "terças", "quartas", "quintas",
    "sextas", "sábados", "domingos",
]


def _now_iso() -> str:
    """Retorna timestamp ISO atual."""
    return datetime.now().replace(microsecond=0).isoformat()


def _date_from_ddmm(date_str: str, year: int) -> date:
    """Converte DD/MM em date."""
    try:
        from .utils import ddmm_to_date
    except ImportError:
        from utils import ddmm_to_date
    return ddmm_to_date(date_str, year)


def _collect_ledger_files(data_dir: Path, today: date, weeks: int) -> list[Path]:
    """Coleta todos os .jsonl dentro do período de análise."""
    historico_dir = data_dir / "historico"
    if not historico_dir.exists():
        return []

    cutoff = get_week_start(today) - timedelta(weeks=weeks - 1)
    files = []

    for path in sorted(historico_dir.glob("*_bruto.jsonl")):
        parts = path.stem.split("_")
        if len(parts) < 3:
            continue
        try:
            file_start = datetime.strptime(parts[0], "%d%m%y").date()
        except ValueError:
            continue

        if file_start >= cutoff and file_start <= today:
            files.append(path)

    return files


def _normalize_description(text: str) -> str:
    """Normaliza descrição para agrupamento: palavras extraídas ordenadas."""
    words = _extract_words(text)
    return " ".join(sorted(words))


def _detect_pattern(completion_dates: list[date]) -> tuple[Optional[str], list[int]]:
    """Detecta padrão de recorrência a partir de datas de conclusão.

    Retorna (tipo_padrão, lista_de_weekdays) onde weekday segue
    convenção Python: 0=Monday ... 6=Sunday.

    - Se ocorrências abrangem >= 5 dias diferentes: ("daily", [0..6])
    - Se 1-3 dias concentram >= 80% das ocorrências: ("weekly", esses_dias)
    - Caso contrário: (None, []) — padrão não claro
    """
    if not completion_dates:
        return (None, [])

    weekday_counts = Counter(d.weekday() for d in completion_dates)
    total = len(completion_dates)

    # Se espalha por 5+ dias diferentes → diário
    if len(weekday_counts) >= 5:
        return ("daily", [0, 1, 2, 3, 4, 5, 6])

    # Tenta encontrar 1-3 dias que concentrem >= 80%
    sorted_days = weekday_counts.most_common()
    for n_days in range(1, 4):  # 1, 2, 3 dias
        top_days = sorted_days[:n_days]
        top_count = sum(count for _, count in top_days)
        if top_count / total >= 0.80:
            days = sorted([day for day, _ in top_days])
            return ("weekly", days)

    return (None, [])


def _detect_time_mode(tasks: list[dict]) -> Optional[str]:
    """Detecta horário predominante das tasks.

    Extrai campo 'context' (formato HH:MM) e retorna o horário
    que representa >= 60% das ocorrências. Retorna None caso contrário.
    """
    time_re = _re.compile(r"\b(\d{2}:\d{2})\b")
    time_counts: Counter = Counter()

    for task in tasks:
        context = task.get("context") or ""
        match = time_re.search(context)
        if match:
            time_counts[match.group(1)] += 1

    if not time_counts:
        return None

    total = sum(time_counts.values())
    most_common_time, most_common_count = time_counts.most_common(1)[0]

    if most_common_count / total >= 0.60:
        return most_common_time

    return None


def get_active_recurrence_rules(ledger: list[dict]) -> list[dict]:
    """Retorna regras de recorrência ativas do ledger.

    Filtra registros type=="recurrence_rule", agrupa por id,
    aplica last-write-wins por campo, e retorna apenas regras
    cuja última _operation != "deactivate".
    """
    rules_by_id: dict[str, dict[str, Any]] = {}

    for record in ledger:
        if record.get("type") != "recurrence_rule":
            continue

        rule_id = record.get("id")
        if not rule_id:
            continue

        current = rules_by_id.get(rule_id)
        if current is None:
            current = {"id": rule_id}
            rules_by_id[rule_id] = current

        # Last-write-wins para cada campo (exceto _ prefixados e type/id)
        for key, value in record.items():
            if not key.startswith("_") and key not in ("type", "id"):
                current[key] = value

        # Preserva _operation para verificar estado
        if "_operation" in record:
            current["_operation"] = record["_operation"]

    # Retorna apenas regras não desativadas
    active = []
    for rule in rules_by_id.values():
        if rule.get("_operation") != "deactivate":
            active.append(rule)

    return active


def get_rules_for_weekday(rules: list[dict], weekday: int) -> list[dict]:
    """Filtra regras aplicáveis a um dia da semana específico.

    - pattern=daily: sempre incluída
    - pattern=weekly: incluída se weekday está em rule["weekdays"]
    """
    result = []
    for rule in rules:
        pattern = rule.get("pattern")
        if pattern == "daily":
            result.append(rule)
        elif pattern == "weekly":
            if weekday in (rule.get("weekdays") or []):
                result.append(rule)
    return result


def _build_suggestion_reason(
    count: int,
    lookback_days: int,
    pattern: str,
    weekdays: list[int],
    time_range: Optional[str],
) -> str:
    """Constrói razão legível em português para a sugestão de recorrência."""
    if pattern == "daily":
        base = f"Concluída {count}x nos últimos {lookback_days} dias"
        if time_range:
            return f"{base}, sempre ~{time_range}"
        return base

    # weekly
    day_names = [WEEKDAY_NAMES_PT[d] for d in weekdays]
    if len(day_names) == 1:
        days_str = day_names[0]
    elif len(day_names) == 2:
        days_str = f"{day_names[0]} e {day_names[1]}"
    else:
        days_str = ", ".join(day_names[:-1]) + f" e {day_names[-1]}"

    base = f"Concluída {count}x: {days_str}"
    if time_range:
        return f"{base} ~{time_range}"
    return base


def detect_recurrence_candidates(
    data_dir: Path,
    today: date,
    min_occurrences: int = 5,
    lookback_weeks: int = 4,
) -> list[dict[str, Any]]:
    """Analisa ledgers recentes e detecta candidatos a recorrência.

    Retorna lista de candidatos ordenados por contagem decrescente,
    cada um com: description, count, pattern, weekdays, time_range,
    suggestion_reason, e task_ids das ocorrências.
    """
    # Coleta todos os registros do período
    all_records: list[dict[str, Any]] = []
    for path in _collect_ledger_files(data_dir, today, lookback_weeks):
        all_records.extend(load_ledger(path))

    if not all_records:
        return []

    # Merge task records
    merged = _merge_task_records(all_records)

    # Carrega regras ativas do ledger corrente para evitar duplicatas
    active_rules = get_active_recurrence_rules(all_records)
    active_rule_keys = set()
    for rule in active_rules:
        desc = rule.get("description", "")
        key = frozenset(_extract_words(desc))
        if key:
            active_rule_keys.add(key)

    # Filtra: concluídas, não de rotina
    completed_tasks: list[dict[str, Any]] = []
    for task in merged.values():
        if task.get("status") != "[x]":
            continue
        if task.get("source") == "rotina":
            continue
        completed_tasks.append(task)

    # Agrupa por descrição normalizada
    groups: dict[frozenset, list[dict[str, Any]]] = {}
    for task in completed_tasks:
        desc = task.get("description", "")
        key = frozenset(_extract_words(desc))
        if not key:
            continue
        groups.setdefault(key, []).append(task)

    lookback_days = lookback_weeks * 7
    candidates = []

    for key, tasks in groups.items():
        count = len(tasks)
        if count < min_occurrences:
            continue

        # Pega datas de conclusão
        completion_dates = []
        for t in tasks:
            cd = _parse_record_date(t.get("completed_at"))
            if cd:
                completion_dates.append(cd)

        if not completion_dates:
            continue

        # Detecta padrão
        pattern, weekdays = _detect_pattern(completion_dates)
        if pattern is None:
            continue

        # Verifica se já existe regra ativa
        if key in active_rule_keys:
            continue

        # Detecta horário predominante
        time_range = _detect_time_mode(tasks)

        # Usa a descrição original da primeira task como representante
        representative_desc = tasks[0].get("description", "")

        # Coleta task_ids
        task_ids = [t.get("id") for t in tasks if t.get("id")]

        suggestion_reason = _build_suggestion_reason(
            count, lookback_days, pattern, weekdays, time_range,
        )

        candidates.append({
            "description": representative_desc,
            "normalized_key": _normalize_description(representative_desc),
            "count": count,
            "pattern": pattern,
            "weekdays": weekdays,
            "time_range": time_range,
            "suggestion_reason": suggestion_reason,
            "task_ids": task_ids,
        })

    # Ordena por contagem decrescente
    candidates.sort(key=lambda c: -c["count"])
    return candidates


def activate_recurrence_rule(
    ledger_path: Path,
    description: str,
    pattern: str,
    weekdays: list[int],
    priority: str,
    time_range: Optional[str],
    today_ddmm: str,
    year: int = 0,
    source_task_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Ativa uma regra de recorrência no ledger.

    Gera rule_id no formato rule_YYYYMMDD_slug e appenda registro
    type="recurrence_rule" com _operation="create".
    """
    if year == 0:
        year = datetime.now().year
    created_date = _date_from_ddmm(today_ddmm, year)

    # Gera slug
    slug = _slugify(description)
    if time_range:
        time_slug = time_range.replace(":", "")
        slug = f"{slug}_{time_slug}"

    base_id = f"rule_{created_date:%Y%m%d}_{slug}"

    # Verifica colisão no ledger
    ledger = load_ledger(ledger_path)
    existing_ids = {
        r.get("id") for r in ledger
        if r.get("type") == "recurrence_rule"
    }

    rule_id = base_id
    if rule_id in existing_ids:
        for suffix in range(2, 1000):
            candidate = f"{base_id}_{suffix}"
            if candidate not in existing_ids:
                rule_id = candidate
                break

    # Normaliza weekdays para daily
    if pattern == "daily":
        weekdays = [0, 1, 2, 3, 4, 5, 6]

    rule = {
        "description": description,
        "pattern": pattern,
        "weekdays": weekdays,
        "priority": priority,
        "time_range": time_range,
        "created_at": _now_iso(),
        "created_date": created_date.isoformat(),
    }

    if source_task_ids:
        rule["source_task_ids"] = source_task_ids

    record: dict[str, Any] = {
        "type": "recurrence_rule",
        "id": rule_id,
        "_operation": "create",
        **rule,
    }

    append_record(ledger_path, record)

    return {
        "ok": True,
        "rule_id": rule_id,
        "rule": rule,
    }


def deactivate_recurrence_rule(
    ledger_path: Path,
    rule_id: str,
    reason: str,
    today_ddmm: str,
) -> dict[str, Any]:
    """Desativa uma regra de recorrência existente.

    Appenda registro type="recurrence_rule" com _operation="deactivate".
    """
    ledger = load_ledger(ledger_path)

    # Verifica que a regra existe
    rule_exists = any(
        r.get("type") == "recurrence_rule" and r.get("id") == rule_id
        for r in ledger
    )

    if not rule_exists:
        return {
            "ok": False,
            "error": f"Regra não encontrada: {rule_id}",
        }

    record = {
        "type": "recurrence_rule",
        "id": rule_id,
        "_operation": "deactivate",
        "reason": reason,
        "deactivated_at": _now_iso(),
    }

    append_record(ledger_path, record)

    return {
        "ok": True,
        "rule_id": rule_id,
        "deactivated": True,
    }
