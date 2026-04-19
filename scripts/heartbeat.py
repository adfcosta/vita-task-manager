"""Heartbeat nudges engine — detecta alertas críticos e emite nudges proativos.

Lógica isolada do cli.py: recebe alertas (já construídos por _build_alerts),
filtra pra críticos, agrupa por task, aplica cooldown por task_id+alert_type,
respeita max_nudges_per_tick, e persiste nudges em
data/proactive-nudges.jsonl (append-only, seguindo padrão do ledger).

Thresholds, limite por tick e agrupamento: v2.12.0 (spec TDAH §9, §10).
"""

from datetime import datetime, timedelta
from pathlib import Path
import json
import uuid

try:
    from .ledger import load_ledger, append_record
    from . import nudge_copy
except ImportError:
    from ledger import load_ledger, append_record
    import nudge_copy  # type: ignore[no-redef]


NUDGES_FILENAME = "proactive-nudges.jsonl"
CONFIG_FILENAME = "heartbeat-config.json"

# Severidade: menor = mais crítico (emitido primeiro). Usado pra ordenar
# grupos quando excedem max_nudges_per_tick.
# first_touch fica entre blocked e stalled: task parada sem toque é
# dificuldade de iniciação (spec §5.1), urgente mas não passa na frente
# de coisa já adiada.
# off_pace é preventivo (task ainda não venceu) — fica depois de stalled,
# antes de due_today.
# due_soon (v2.17.0) entra alto: vencimento em poucas horas é mais
# urgente que adiamento crônico. Ranqueia depois de overdue e blocked
# mas antes de first_touch/stalled/off_pace.
SEVERITY_ORDER = {
    "overdue": 0,
    "blocked": 1,
    "due_soon": 2,
    "first_touch": 3,
    "stalled": 4,
    "off_pace": 5,
    "due_today": 6,
}


def _nudges_path(data_dir: Path) -> Path:
    return data_dir / NUDGES_FILENAME


def _config_path(data_dir: Path) -> Path:
    return data_dir / CONFIG_FILENAME


def load_heartbeat_config(data_dir: Path) -> dict:
    """Carrega config de heartbeat; se não existir, retorna defaults da spec TDAH §9.

    Defaults (spec-aligned):
      - cooldown_hours: 24
      - max_nudges_per_tick: 3
      - thresholds.overdue_min_days: 1
      - thresholds.stalled_min_hours: 24
      - thresholds.blocked_min_postpones: 2
      - thresholds.first_touch_min_hours: 12 (v2.14.0, spec §5.1)
      - thresholds.off_pace_ratio: 0.7 (v2.15.0, spec §5.6)
      - thresholds.due_soon_window_hours: 4 (v2.17.0, spec §5.2)
    """
    path = _config_path(data_dir)
    defaults = {
        "emit_target": None,
        "severity_floor": "critical",
        "cooldown_hours": 24,
        "max_nudges_per_tick": 3,
        "thresholds": {
            "overdue_min_days": 1,
            "stalled_min_hours": 24,
            "blocked_min_postpones": 2,
            "first_touch_min_hours": 12,
            "off_pace_ratio": 0.7,
            "due_soon_window_hours": 4,
        },
    }
    if not path.exists():
        return defaults
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return defaults
    merged = {**defaults, **data}
    # Deep-merge em thresholds pra permitir override parcial
    merged["thresholds"] = {**defaults["thresholds"], **(data.get("thresholds") or {})}
    return merged


def is_critical(alert: dict, thresholds: dict | None = None) -> bool:
    """Aplica threshold de criticidade. thresholds vem do config (v2.12.0).

    Se thresholds for None, usa defaults spec-aligned.
    """
    if thresholds is None:
        thresholds = {
            "overdue_min_days": 1,
            "stalled_min_hours": 24,
            "blocked_min_postpones": 2,
            "first_touch_min_hours": 12,
            "off_pace_ratio": 0.7,
            "due_soon_window_hours": 4,
        }
    t = alert.get("type")
    if t == "overdue":
        return alert.get("days_overdue", 0) >= thresholds.get("overdue_min_days", 1)
    if t == "stalled":
        return alert.get("hours_since_update", 0) >= thresholds.get("stalled_min_hours", 24)
    if t == "blocked":
        return alert.get("postpone_count", 0) >= thresholds.get("blocked_min_postpones", 2)
    if t == "first_touch":
        return alert.get("hours_since_created", 0) >= thresholds.get("first_touch_min_hours", 12)
    if t == "off_pace":
        # Threshold (off_pace_ratio) é aplicado em _build_alerts na construção
        # do alerta. Se o alerta chegou aqui com progresso < esperado * ratio,
        # já é crítico por construção.
        return True
    if t == "due_soon":
        # Janela (due_soon_window_hours) aplicada em _build_alerts.
        # Se o alerta existe, vencimento está iminente → crítico.
        return True
    # due_today e outros tipos não viram nudge crítico por padrão
    return False


def _group_alerts_by_task(alerts: list[dict]) -> dict[str, list[dict]]:
    """Agrupa alerts por task_id. Spec §10.2: múltiplos alertas da mesma
    task viram uma única intervenção."""
    groups: dict[str, list[dict]] = {}
    for a in alerts:
        tid = a.get("task_id")
        if tid is None:
            continue
        groups.setdefault(tid, []).append(a)
    return groups


def _group_severity(alert_types: list[str]) -> int:
    """Menor = mais crítico. Grupos com overdue ordenam antes de grupos só stalled."""
    if not alert_types:
        return 99
    return min(SEVERITY_ORDER.get(t, 99) for t in alert_types)


def is_in_cooldown(
    task_id: str,
    alert_type: str,
    nudges: list[dict],
    cooldown_hours: int,
    now: datetime,
) -> bool:
    """Retorna True se o último nudge pra essa task+tipo foi há menos que cooldown_hours.

    Aceita records antigos com `alert_type` (string) e novos com `alert_types` (lista).
    """
    for rec in reversed(nudges):
        if rec.get("type") != "nudge":
            continue
        if rec.get("task_id") != task_id:
            continue
        # Backward compat: aceita tanto alert_type (v2.11) quanto alert_types (v2.12+)
        types = rec.get("alert_types")
        if types is None:
            legacy = rec.get("alert_type")
            types = [legacy] if legacy else []
        if alert_type not in types:
            continue
        try:
            created = datetime.fromisoformat(rec["created_at"])
        except (KeyError, ValueError, TypeError):
            continue
        if (now - created).total_seconds() < cooldown_hours * 3600:
            return True
    return False


def _last_nudge_for(task_id: str, alert_type: str, nudges: list[dict]) -> dict | None:
    """Retorna o nudge mais recente pra combinação task_id+alert_type, ou None.
    Mantido pra compat — uso interno de debug/inspect."""
    for rec in reversed(nudges):
        if rec.get("type") != "nudge":
            continue
        if rec.get("task_id") != task_id:
            continue
        types = rec.get("alert_types")
        if types is None:
            legacy = rec.get("alert_type")
            types = [legacy] if legacy else []
        if alert_type in types:
            return rec
    return None


def _render_nudge_text(group_alerts: list[dict]) -> tuple[str, str]:
    """Escolhe copy pro grupo. Retorna (text_frag, copy_variant).

    - Grupo de 1 alert → COPY_LIBRARY com variante A/B determinística
    - Grupo com 2+ alerts → render_grouped (copy_variant = "grouped")
    - Se render_nudge retornar vazio (alert_type sem copy na library),
      fallback pra render_grouped
    """
    if len(group_alerts) == 1:
        alert = group_alerts[0]
        variant = nudge_copy.pick_variant(alert.get("task_id", ""), alert["type"])
        text = nudge_copy.render_nudge(alert, variant)
        if text:
            return text, variant
        # alert_type sem copy definido → usa grouped como fallback
    return nudge_copy.render_grouped(group_alerts), nudge_copy.GROUPED_VARIANT


def _build_emit_text(new_nudges: list[dict]) -> str:
    """Monta mensagem pra enviar via sessions_send.

    Pra 1 nudge, text_frag já é copy completo (com 🌿 e convite à ação) — usa
    direto. Pra N nudges, lista em bullets removendo o 🌿 inicial de cada um.
    """
    if not new_nudges:
        return ""
    if len(new_nudges) == 1:
        return new_nudges[0]["text_frag"]
    bullets = "\n".join(f"• {nudge_copy.strip_prefix(n['text_frag'])}" for n in new_nudges)
    return f"🌿 Vita alertou — pendências:\n{bullets}"


def build_heartbeat_nudges(
    data_dir: Path,
    alerts: list[dict],
    cooldown_hours: int | None = None,
    now: datetime | None = None,
    config: dict | None = None,
) -> dict:
    """Filtra alertas críticos, agrupa por task, aplica cooldown,
    respeita max_nudges_per_tick, persiste nudges.

    v2.12.0: thresholds lidos do config (não mais hardcoded), agrupamento
    por task_id, limite por tick.

    Retorna dict com nudges_new (int), suppressed_by_cooldown (int),
    non_critical_skipped (int), over_limit_deferred (int), emit_text (str),
    nudges_records (list dos records apendados).
    """
    if now is None:
        now = datetime.now()
    if config is None:
        config = load_heartbeat_config(data_dir)
    thresholds = config.get("thresholds") or {}
    if cooldown_hours is None:
        cooldown_hours = config.get("cooldown_hours", 24)
    max_per_tick = config.get("max_nudges_per_tick", 3)

    nudges_file = _nudges_path(data_dir)
    existing = load_ledger(nudges_file)

    # 1. Filtra críticos
    critical_alerts = [a for a in alerts if is_critical(a, thresholds)]
    non_critical_skipped = len(alerts) - len(critical_alerts)

    # 2. Agrupa por task (spec §10.2)
    groups = _group_alerts_by_task(critical_alerts)

    # 3. Pra cada grupo, filtra alert_types em cooldown; mantém só os frescos
    fireable: list[tuple[str, list[dict]]] = []
    suppressed = 0
    for task_id, group in groups.items():
        fresh = [
            a for a in group
            if not is_in_cooldown(task_id, a["type"], existing, cooldown_hours, now)
        ]
        if not fresh:
            suppressed += 1
            continue
        fireable.append((task_id, fresh))

    # 4. Ordena por severidade (spec §10.1: sort por severidade e acionabilidade)
    fireable.sort(key=lambda x: _group_severity([a["type"] for a in x[1]]))

    # 5. Corta em max_per_tick; leftover vai como "deferred" (reaparece no próximo tick)
    to_emit = fireable[:max_per_tick]
    over_limit_deferred = len(fireable) - len(to_emit)

    # 6. Persiste records e monta emissão
    new_records: list[dict] = []
    for task_id, group_alerts in to_emit:
        alert_types = [a["type"] for a in group_alerts]
        # Injeta task_id nos alerts pra pick_variant usar
        for a in group_alerts:
            a.setdefault("task_id", task_id)
        text_frag, copy_variant = _render_nudge_text(group_alerts)
        record = {
            "type": "nudge",
            "id": f"nudge_{uuid.uuid4().hex[:8]}",
            "task_id": task_id,
            "alert_types": alert_types,
            "text_frag": text_frag,
            "copy_variant": copy_variant,
            "cooldown_applied": True,
            "created_at": now.isoformat(),
            # v2.16.0 instrumentação (spec §11). Preenchidos em runtime:
            #  - emitted_at: quando sessions_send confirma entrega
            #  - delivery_status: success | failed | skipped | pending
            #  - next_task_update_at: retrospectivo, via link_nudge_to_next_update
            "emitted_at": None,
            "delivery_status": "pending",
            "next_task_update_at": None,
        }
        # Contexto: campos do primeiro alerta com severidade mais alta no grupo
        primary = min(group_alerts, key=lambda a: SEVERITY_ORDER.get(a["type"], 99))
        for k in (
            "days_overdue", "hours_since_update", "postpone_count",
            "hours_since_created", "done_units", "total_units",
            "expected_units", "days_remaining", "priority", "due_date",
            "due_time", "hours_left",
        ):
            if k in primary:
                record[k] = primary[k]
        append_record(nudges_file, record)
        new_records.append(record)

    return {
        "nudges_new": len(new_records),
        "suppressed_by_cooldown": suppressed,
        "non_critical_skipped": non_critical_skipped,
        "over_limit_deferred": over_limit_deferred,
        "emit_text": _build_emit_text(new_records),
        "nudges_records": new_records,
    }


def get_pending_nudges(data_dir: Path) -> list[dict]:
    """Retorna nudges ainda não 'acked' (sem registro type='nudge_ack' correspondente)."""
    nudges_file = _nudges_path(data_dir)
    records = load_ledger(nudges_file)
    acked_ids = {r["nudge_id"] for r in records if r.get("type") == "nudge_ack"}
    return [r for r in records if r.get("type") == "nudge" and r.get("id") not in acked_ids]


def ack_nudge(
    data_dir: Path,
    nudge_id: str,
    source: str = "manual",
    response_kind: str | None = None,
) -> dict:
    """Marca um nudge como acked (append-only).

    v2.16.0: `response_kind` (spec §11) — classifica a resposta do usuário:
      agora | depois | replanejar | ignorado | None (desconhecido)
    """
    nudges_file = _nudges_path(data_dir)
    record = {
        "type": "nudge_ack",
        "nudge_id": nudge_id,
        "acked_at": datetime.now().isoformat(),
        "ack_source": source,
    }
    if response_kind is not None:
        record["response_kind"] = response_kind
    append_record(nudges_file, record)
    return record


def mark_delivery(
    data_dir: Path,
    nudge_id: str,
    status: str,
    emitted_at: datetime | None = None,
) -> dict:
    """Registra resultado da entrega de um nudge (spec §11).

    status: success | failed | skipped
    Emite registro separado `type=delivery` pra manter append-only;
    leitura do nudge consolidado consulta o último delivery do id.
    """
    nudges_file = _nudges_path(data_dir)
    if emitted_at is None:
        emitted_at = datetime.now()
    record = {
        "type": "delivery",
        "nudge_id": nudge_id,
        "delivery_status": status,
        "emitted_at": emitted_at.isoformat(),
    }
    append_record(nudges_file, record)
    return record


def link_nudge_to_next_update(
    data_dir: Path,
    nudge_id: str,
    task_update_at: datetime,
) -> dict:
    """Linka retroativamente um nudge ao próximo update da task alvo
    (preenche `next_task_update_at`). Append-only via registro `link`.
    """
    nudges_file = _nudges_path(data_dir)
    record = {
        "type": "link",
        "nudge_id": nudge_id,
        "next_task_update_at": task_update_at.isoformat(),
    }
    append_record(nudges_file, record)
    return record
