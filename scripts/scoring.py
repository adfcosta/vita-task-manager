"""Sistema de scoring dinâmico para priorização TDAH-friendly."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any, Optional

try:
    from .utils import ddmm_to_date
except ImportError:
    from utils import ddmm_to_date


SCORING_WEIGHTS = {
    "urgency": 0.35,
    "complexity": 0.25,
    "age": 0.20,
    "postpone_penalty": 0.20,
}

_COMPLEXITY_KEYWORDS = {
    "very_complex": (
        8,
        "high",
        (
            "arquitet", "estruturar", "negoci", "contrato", "proposta",
            "migra", "refator", "planejar", "estratég", "apresenta",
        ),
    ),
    "complex": (
        6,
        "medium",
        (
            "desenvolv", "escrever", "criar", "projet", "analis", "revis",
            "estud", "implementar", "debug", "test", "documenta",
        ),
    ),
    "simple": (
        4,
        "medium",
        (
            "responder", "email", "pagar", "agendar", "confirmar", "levar",
            "enviar", "atualizar", "organizar",
        ),
    ),
    "trivial": (
        2,
        "low",
        (
            "ligar", "mandar mensagem", "tomar", "beber", "pegar", "devolver",
            "comprar", "abrir", "fechar",
        ),
    ),
}

_URGENCY_THRESHOLDS = (
    (0, 100.0),
    (1, 95.0),
    (2, 85.0),
    (4, 70.0),
    (8, 50.0),
    (15, 30.0),
    (31, 15.0),
)

_AGE_THRESHOLDS = (
    (30, 100.0),
    (14, 80.0),
    (7, 60.0),
    (3, 40.0),
    (1, 20.0),
)

_POSTPONE_THRESHOLDS = {
    1: 15.0,
    2: 35.0,
    3: 60.0,
    4: 85.0,
}

_TEXT_FIELDS = ("description", "title", "context", "note")


def _task_get(task: Any, field: str, default: Any = None) -> Any:
    if isinstance(task, dict):
        return task.get(field, default)
    return getattr(task, field, default)


def _task_to_dict(task: Any) -> dict[str, Any]:
    if isinstance(task, dict):
        return dict(task)
    if is_dataclass(task):
        return asdict(task)
    data = getattr(task, "__dict__", None)
    return dict(data or {})


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except Exception:
        return None


def _parse_due_date(value: Optional[str], today: date) -> Optional[date]:
    if not value:
        return None

    parsed_iso = _parse_iso_date(value)
    if parsed_iso:
        return parsed_iso

    if isinstance(value, str) and len(value) == 5 and value.count("/") == 1:
        try:
            return ddmm_to_date(value, today.year)
        except Exception:
            return None

    return None


def _energy_from_complexity(complexity: int) -> str:
    if complexity >= 8:
        return "high"
    if complexity >= 4:
        return "medium"
    return "low"


def _complexity_score_from_value(complexity: int) -> float:
    return float((11 - complexity) * 10)


def infer_task_complexity(task: Any) -> dict[str, Any]:
    """Infere complexidade e energia por heurística simples."""
    explicit = _task_get(task, "complexity_score")
    explicit_source = _task_get(task, "complexity_source")
    explicit_energy = _task_get(task, "energy_required")

    if explicit is not None:
        complexity = max(1, min(10, int(explicit)))
        return {
            "complexity_score": complexity,
            "complexity_source": explicit_source or "user",
            "energy_required": explicit_energy or _energy_from_complexity(complexity),
        }

    text = " ".join(str(_task_get(task, field, "")) for field in _TEXT_FIELDS).lower()

    for score, energy, patterns in _COMPLEXITY_KEYWORDS.values():
        if any(pattern in text for pattern in patterns):
            return {
                "complexity_score": score,
                "complexity_source": "inferred",
                "energy_required": explicit_energy or energy,
            }

    return {
        "complexity_score": 5,
        "complexity_source": explicit_source or "inferred",
        "energy_required": explicit_energy or "medium",
    }


def calculate_urgency(due_date: Optional[str], today: date) -> float:
    """Calcula urgência em escala 0-100 com base no prazo."""
    due = _parse_due_date(due_date, today)
    if due is None:
        return 5.0

    days_remaining = (due - today).days
    if days_remaining < 0:
        return 100.0

    for upper_bound, score in _URGENCY_THRESHOLDS:
        if days_remaining < upper_bound:
            return score
    return 5.0


def calculate_complexity_score(task: Any) -> float:
    """Inverte complexidade 1-10 para score 0-100."""
    return _complexity_score_from_value(infer_task_complexity(task)["complexity_score"])


def calculate_age_boost(first_added: Optional[str], today: date) -> float:
    """Calcula boost por idade da tarefa no backlog em escala 0-100."""
    added_date = _parse_iso_date(first_added)
    if added_date is None:
        return 5.0

    days_in_list = (today - added_date).days
    for minimum_days, score in _AGE_THRESHOLDS:
        if days_in_list > minimum_days:
            return score
    return 5.0


def calculate_postpone_penalty(postpone_count: Optional[int]) -> float:
    """Penalidade exponencial simples por histórico de adiamentos."""
    count = int(postpone_count or 0)
    if count <= 0:
        return 0.0
    return _POSTPONE_THRESHOLDS.get(count, 100.0)


def calculate_total_score(task: Any, today: date) -> dict[str, Any]:
    """Calcula score final e breakdown explicável."""
    task_data = _task_to_dict(task)
    inferred = infer_task_complexity(task_data)

    urgency_score = calculate_urgency(task_data.get("due_date"), today)
    complexity_value = inferred["complexity_score"]
    complexity_score = _complexity_score_from_value(complexity_value)
    age_score = calculate_age_boost(task_data.get("first_added_date"), today)
    postpone_penalty = calculate_postpone_penalty(task_data.get("postpone_count"))

    added_date = _parse_iso_date(task_data.get("first_added_date"))
    days_in_list = max(0, (today - added_date).days) if added_date is not None else 0

    final_score = (
        (urgency_score * SCORING_WEIGHTS["urgency"])
        + (complexity_score * SCORING_WEIGHTS["complexity"])
        + (age_score * SCORING_WEIGHTS["age"])
        - (postpone_penalty * SCORING_WEIGHTS["postpone_penalty"])
    )

    overrides: list[str] = []
    if days_in_list > 21:
        final_score += 10
        overrides.append("boost_age_21d")
    if int(task_data.get("postpone_count") or 0) >= 3:
        final_score += 15
        overrides.append("boost_postpone_3x")

    final_score = round(max(0.0, min(100.0, final_score)), 2)

    breakdown = {
        "urgency_score": round(urgency_score, 2),
        "complexity_score": round(complexity_score, 2),
        "age_score": round(age_score, 2),
        "postpone_penalty": round(postpone_penalty, 2),
        "final_score": final_score,
        "weights": dict(SCORING_WEIGHTS),
        "complexity_value": complexity_value,
        "complexity_source": inferred["complexity_source"],
        "energy_required": inferred["energy_required"],
        "days_in_list": days_in_list,
        "overrides": overrides,
    }

    return {
        "score": final_score,
        "score_breakdown": breakdown,
        "complexity_score": complexity_value,
        "complexity_source": inferred["complexity_source"],
        "energy_required": inferred["energy_required"],
    }
