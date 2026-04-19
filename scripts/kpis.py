"""KPIs de nudges (spec TDAH §16).

Responde "quantos nudges viraram ação útil?" a partir do
`data/proactive-nudges.jsonl` e dos ledgers de tasks em
`data/historico/*.jsonl`.

Modelo de eventos (append-only):
- `nudge` — emissão do nudge (criado pelo heartbeat)
- `delivery` — resultado do envio (success/failed/skipped)
- `link` — linka nudge ao próximo update da task (retroativo)
- `nudge_ack` — usuário reconheceu o nudge (opcional `response_kind`)

Leitura consolida os eventos por `nudge_id` antes de calcular KPIs.
"""

from __future__ import annotations

from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any

try:
    from .ledger import load_ledger, get_ledger_filename
except ImportError:
    from ledger import load_ledger, get_ledger_filename  # type: ignore[no-redef]


NUDGES_FILENAME = "proactive-nudges.jsonl"


def _nudges_path(data_dir: Path) -> Path:
    return data_dir / NUDGES_FILENAME


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def consolidate_nudges(records: list[dict]) -> list[dict]:
    """Agrupa eventos `nudge/delivery/link/nudge_ack` em um registro consolidado
    por `nudge_id`. Último evento vence (append-only semantics)."""
    by_id: dict[str, dict] = {}
    for r in records:
        t = r.get("type")
        if t == "nudge":
            nid = r.get("id")
            if not nid:
                continue
            by_id.setdefault(nid, {}).update({
                "nudge_id": nid,
                "task_id": r.get("task_id"),
                "alert_types": r.get("alert_types") or (
                    [r["alert_type"]] if r.get("alert_type") else []
                ),
                "copy_variant": r.get("copy_variant"),
                "created_at": r.get("created_at"),
                "emitted_at": r.get("emitted_at"),
                "delivery_status": r.get("delivery_status", "pending"),
                "next_task_update_at": r.get("next_task_update_at"),
                "acked_at": None,
                "response_kind": None,
            })
        elif t == "delivery":
            nid = r.get("nudge_id")
            if not nid or nid not in by_id:
                continue
            by_id[nid]["delivery_status"] = r.get("delivery_status")
            by_id[nid]["emitted_at"] = r.get("emitted_at") or by_id[nid].get("emitted_at")
        elif t == "link":
            nid = r.get("nudge_id")
            if not nid or nid not in by_id:
                continue
            by_id[nid]["next_task_update_at"] = r.get("next_task_update_at")
        elif t == "nudge_ack":
            nid = r.get("nudge_id")
            if not nid or nid not in by_id:
                continue
            by_id[nid]["acked_at"] = r.get("acked_at")
            if "response_kind" in r:
                by_id[nid]["response_kind"] = r["response_kind"]
    return list(by_id.values())


def _task_updates_after(
    data_dir: Path,
    task_id: str,
    after: datetime,
) -> datetime | None:
    """Varre ledgers de histórico procurando o primeiro update (progress/
    complete/update/start) de `task_id` depois de `after`. Retorna o
    timestamp do evento, ou None se não houver."""
    hist = data_dir / "historico"
    if not hist.exists():
        return None
    earliest: datetime | None = None
    for p in sorted(hist.glob("*.jsonl")):
        for rec in load_ledger(p):
            if rec.get("type") != "task":
                continue
            if rec.get("id") != task_id:
                continue
            op = rec.get("_operation")
            if op == "create":
                continue
            ts = _parse_iso(rec.get("updated_at") or rec.get("completed_at"))
            if ts is None or ts <= after:
                continue
            if earliest is None or ts < earliest:
                earliest = ts
    return earliest


def compute_kpis(
    data_dir: Path,
    window_days: int = 7,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Calcula KPIs dos nudges dos últimos `window_days`.

    Retorna:
      - total_nudges: total na janela
      - action_within_2h: nudges com update de task nas primeiras 2h
      - action_within_24h: nudges com update nas primeiras 24h
      - median_hours_to_update: mediana de horas entre nudge → update
      - by_alert_type: contagens e ação por alert_type
      - ignored_rate: % sem ack e sem update em 24h
      - delivery: success/failed/skipped counts
      - response_kinds: contagem por response_kind (se registrado)
      - variants: contagem por copy_variant (base pra A/B)
    """
    if now is None:
        now = datetime.now()
    cutoff = now - timedelta(days=window_days)

    nudges_file = _nudges_path(data_dir)
    if not nudges_file.exists():
        return _empty_kpis(window_days)

    raw = load_ledger(nudges_file)
    consolidated = consolidate_nudges(raw)

    in_window = []
    for n in consolidated:
        created = _parse_iso(n.get("created_at"))
        if created is None or created < cutoff:
            continue
        in_window.append(n)

    if not in_window:
        return _empty_kpis(window_days)

    # Preenche next_task_update_at lazy pros que ainda não têm link
    for n in in_window:
        if n.get("next_task_update_at") is not None:
            continue
        created = _parse_iso(n.get("created_at"))
        if created is None or not n.get("task_id"):
            continue
        ts = _task_updates_after(data_dir, n["task_id"], created)
        if ts is not None:
            n["next_task_update_at"] = ts.isoformat()

    total = len(in_window)
    hours_deltas: list[float] = []
    within_2h = 0
    within_24h = 0
    ignored = 0
    by_type: dict[str, dict[str, int]] = {}
    delivery = {"success": 0, "failed": 0, "skipped": 0, "pending": 0}
    response_kinds: dict[str, int] = {}
    variants: dict[str, dict[str, int]] = {}

    for n in in_window:
        ds = n.get("delivery_status") or "pending"
        delivery[ds] = delivery.get(ds, 0) + 1

        cv = n.get("copy_variant") or "unknown"
        variants.setdefault(cv, {"total": 0, "action_24h": 0})
        variants[cv]["total"] += 1

        rk = n.get("response_kind")
        if rk:
            response_kinds[rk] = response_kinds.get(rk, 0) + 1

        created = _parse_iso(n.get("created_at"))
        upd = _parse_iso(n.get("next_task_update_at"))
        acked = _parse_iso(n.get("acked_at"))

        had_action_24h = False
        if created and upd:
            delta_h = (upd - created).total_seconds() / 3600
            if delta_h >= 0:
                hours_deltas.append(delta_h)
                if delta_h <= 2:
                    within_2h += 1
                if delta_h <= 24:
                    within_24h += 1
                    had_action_24h = True
                    variants[cv]["action_24h"] += 1

        if not had_action_24h and not acked:
            ignored += 1

        for at in n.get("alert_types") or []:
            by_type.setdefault(at, {"total": 0, "action_24h": 0, "ignored": 0})
            by_type[at]["total"] += 1
            if had_action_24h:
                by_type[at]["action_24h"] += 1
            if not had_action_24h and not acked:
                by_type[at]["ignored"] += 1

    median_hours = _median(hours_deltas) if hours_deltas else None

    return {
        "window_days": window_days,
        "total_nudges": total,
        "action_within_2h": within_2h,
        "action_within_24h": within_24h,
        "median_hours_to_update": median_hours,
        "ignored_count": ignored,
        "ignored_rate": round(ignored / total, 3) if total else 0.0,
        "by_alert_type": by_type,
        "delivery": delivery,
        "response_kinds": response_kinds,
        "variants": variants,
    }


def _empty_kpis(window_days: int) -> dict:
    return {
        "window_days": window_days,
        "total_nudges": 0,
        "action_within_2h": 0,
        "action_within_24h": 0,
        "median_hours_to_update": None,
        "ignored_count": 0,
        "ignored_rate": 0.0,
        "by_alert_type": {},
        "delivery": {"success": 0, "failed": 0, "skipped": 0, "pending": 0},
        "response_kinds": {},
        "variants": {},
    }


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return round((s[mid - 1] + s[mid]) / 2, 2)
    return round(s[mid], 2)
