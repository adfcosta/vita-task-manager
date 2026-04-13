"""Sugestão diária 1-3-5 baseada em score dinâmico."""

from __future__ import annotations

from datetime import date
from typing import Any

try:
    from .scoring import calculate_total_score
except ImportError:
    from scoring import calculate_total_score


_LIMITS = {"big": 1, "medium": 3, "small": 5}
_BUCKET_ORDER = ("big", "medium", "small")


def _task_get(task: Any, field: str, default: Any = None) -> Any:
    if isinstance(task, dict):
        return task.get(field, default)
    return getattr(task, field, default)


def categorize_size(task: Any) -> str:
    complexity = int(_task_get(task, "complexity_score") or 5)
    if complexity >= 8:
        return "big"
    if complexity >= 4:
        return "medium"
    return "small"


def explain_suggestion(task: dict[str, Any]) -> str:
    breakdown = task.get("score_breakdown", {})
    reasons: list[str] = []

    urgency = breakdown.get("urgency_score", 0)
    if urgency >= 85:
        reasons.append("prazo imediato")
    elif urgency >= 50:
        reasons.append("prazo próximo")

    days = breakdown.get("days_in_list", 0)
    if days >= 14:
        reasons.append("está parada há bastante tempo")
    elif days >= 4:
        reasons.append("já está há alguns dias na lista")

    postpone_count = int(task.get("postpone_count") or 0)
    if postpone_count >= 3:
        reasons.append("muito adiada")
    elif postpone_count >= 1:
        reasons.append("já foi adiada")

    complexity = int(task.get("complexity_score") or 5)
    if complexity <= 3:
        reasons.append("rápida de executar")
    elif complexity >= 8:
        reasons.append("exige bloco de foco")
    else:
        reasons.append("complexidade administrável")

    if not reasons:
        reasons.append("bom equilíbrio entre urgência e esforço")

    return "; ".join(reasons)


def _as_task_dict(task: Any) -> dict[str, Any]:
    if isinstance(task, dict):
        return dict(task)
    return dict(getattr(task, "__dict__", {}))


def _enrich_task(task: Any, today: date) -> dict[str, Any]:
    enriched = _as_task_dict(task)
    enriched.update(calculate_total_score(enriched, today))
    enriched["size_category"] = categorize_size(enriched)
    enriched["explanation"] = explain_suggestion(enriched)
    return enriched


def _sort_key(item: dict[str, Any]) -> tuple[float, str]:
    return (-item["score"], item.get("description", "").lower())


def _select_top(tasks: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return sorted(tasks, key=_sort_key)[:limit]


def _copy_with_flag(task: dict[str, Any], flag: str | None = None) -> dict[str, Any]:
    copied = dict(task)
    if flag:
        copied[flag] = True
    return copied


def _consume_candidates(
    pool: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    used_ids: set[Any],
    limit: int,
    flag_map: dict[str, str],
) -> None:
    for candidate in pool:
        if len(selected) >= limit:
            break
        candidate_id = candidate.get("id")
        if candidate_id in used_ids:
            continue
        selected.append(_copy_with_flag(candidate, flag_map.get(candidate["size_category"])))
        used_ids.add(candidate_id)


def suggest_135(tasks: list[Any], today: date, limit: int = 9) -> dict[str, list[dict[str, Any]]]:
    """Retorna distribuição 1-3-5 com hard limits e backfill controlado."""
    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in _BUCKET_ORDER}

    for task in tasks:
        if _task_get(task, "status", "[ ]") not in ("[ ]", "[~]"):
            continue
        enriched = _enrich_task(task, today)
        buckets[enriched["size_category"]].append(enriched)

    for name in _BUCKET_ORDER:
        buckets[name].sort(key=_sort_key)

    selected = {
        "big": [_copy_with_flag(task) for task in buckets["big"][: _LIMITS["big"]]],
        "medium": [_copy_with_flag(task) for task in buckets["medium"][: _LIMITS["medium"]]],
        "small": [_copy_with_flag(task) for task in buckets["small"][: _LIMITS["small"]]],
    }

    used_ids = {item.get("id") for group in selected.values() for item in group}

    if not selected["big"]:
        for candidate in buckets["medium"]:
            candidate_id = candidate.get("id")
            if candidate_id in used_ids:
                continue
            selected["big"] = [_copy_with_flag(candidate, "promoted_to_big")]
            used_ids.add(candidate_id)
            break

    small_backfill_pool = _select_top(
        [*buckets["small"], *buckets["medium"], *buckets["big"]],
        999,
    )
    _consume_candidates(
        small_backfill_pool,
        selected["small"],
        used_ids,
        _LIMITS["small"],
        {"medium": "demoted_to_small", "big": "demoted_to_small"},
    )

    medium_backfill_pool = _select_top(
        [*buckets["medium"], *buckets["small"], *buckets["big"]],
        999,
    )
    _consume_candidates(
        medium_backfill_pool,
        selected["medium"],
        used_ids,
        _LIMITS["medium"],
        {"small": "promoted_to_medium", "big": "demoted_to_medium"},
    )

    for name in _BUCKET_ORDER:
        selected[name] = _select_top(selected[name], _LIMITS[name])

    if limit < 9:
        ordered: list[tuple[str, dict[str, Any]]] = []
        for bucket in _BUCKET_ORDER:
            ordered.extend((bucket, item) for item in selected[bucket])
        ordered.sort(key=lambda pair: _sort_key(pair[1]))

        trimmed = {name: [] for name in _BUCKET_ORDER}
        for bucket, item in ordered[: max(0, limit)]:
            trimmed[bucket].append(item)
        selected = trimmed

    for bucket in _BUCKET_ORDER:
        for position, item in enumerate(selected[bucket], start=1):
            item["position"] = position

    return selected
