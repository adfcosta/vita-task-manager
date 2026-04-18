"""Heartbeat nudges engine — detecta alertas críticos e emite nudges proativos.

Lógica isolada do cli.py: recebe alertas (já construídos por _build_alerts),
filtra pra críticos, aplica cooldown por task_id+alert_type, e persiste nudges
em data/proactive-nudges.jsonl (append-only, seguindo padrão do ledger).
"""

from datetime import datetime, timedelta
from pathlib import Path
import json
import uuid

try:
    from .ledger import load_ledger, append_record
except ImportError:
    from ledger import load_ledger, append_record


NUDGES_FILENAME = "proactive-nudges.jsonl"
CONFIG_FILENAME = "heartbeat-config.json"


def _nudges_path(data_dir: Path) -> Path:
    return data_dir / NUDGES_FILENAME


def _config_path(data_dir: Path) -> Path:
    return data_dir / CONFIG_FILENAME


def load_heartbeat_config(data_dir: Path) -> dict:
    """Carrega config de heartbeat; se não existir, retorna defaults seguros.

    Formato esperado:
      {
        "emit_target": "agent:main:whatsapp:direct:+558296607300",
        "severity_floor": "critical",
        "cooldown_hours": 24
      }
    """
    path = _config_path(data_dir)
    defaults = {
        "emit_target": None,
        "severity_floor": "critical",
        "cooldown_hours": 24,
    }
    if not path.exists():
        return defaults
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {**defaults, **data}
    except (json.JSONDecodeError, OSError):
        return defaults


def is_critical(alert: dict) -> bool:
    """Aplica threshold de criticidade."""
    t = alert.get("type")
    if t == "overdue":
        return alert.get("days_overdue", 0) >= 2
    if t == "stalled":
        return alert.get("hours_since_update", 0) >= 48
    if t == "blocked":
        return alert.get("postpone_count", 0) >= 3
    return False  # due_today não vira nudge crítico por padrão


def _last_nudge_for(task_id: str, alert_type: str, nudges: list[dict]) -> dict | None:
    """Retorna o nudge mais recente (type == 'nudge') pra combinação task_id+alert_type, ou None."""
    for rec in reversed(nudges):
        if rec.get("type") != "nudge":
            continue
        if rec.get("task_id") == task_id and rec.get("alert_type") == alert_type:
            return rec
    return None


def is_in_cooldown(task_id: str, alert_type: str, nudges: list[dict], cooldown_hours: int, now: datetime) -> bool:
    """Retorna True se o último nudge pra essa task+tipo foi há menos que cooldown_hours."""
    last = _last_nudge_for(task_id, alert_type, nudges)
    if last is None:
        return False
    try:
        created = datetime.fromisoformat(last["created_at"])
    except (KeyError, ValueError, TypeError):
        return False
    return (now - created).total_seconds() < cooldown_hours * 3600


def _format_nudge_fragment(alert: dict) -> str:
    """Uma linha curta pra um alerta, pra usar no emit_text."""
    t = alert["type"]
    desc = alert.get("description", "?")
    if t == "overdue":
        return f"{desc} — atrasada há {alert['days_overdue']} dias"
    if t == "stalled":
        return f"{desc} — parada há {alert['hours_since_update']}h"
    if t == "blocked":
        return f"{desc} — adiada {alert['postpone_count']}x (bloqueio)"
    return desc


def _build_emit_text(new_nudges: list[dict]) -> str:
    """Monta mensagem pra enviar via sessions_send."""
    if not new_nudges:
        return ""
    if len(new_nudges) == 1:
        frag = new_nudges[0]["text_frag"]
        return f'🌿 Vita alertou: "{frag}". Atacar hoje?'
    bullets = "\n".join(f"• {n['text_frag']}" for n in new_nudges)
    return f"🌿 Vita alertou — pendências:\n{bullets}"


def build_heartbeat_nudges(
    data_dir: Path,
    alerts: list[dict],
    cooldown_hours: int = 24,
    now: datetime | None = None,
) -> dict:
    """Filtra alertas críticos, aplica cooldown, persiste novos nudges.

    Retorna dict com nudges_new (int), suppressed_by_cooldown (int),
    emit_text (str), nudges_records (list dos records apendados).
    """
    if now is None:
        now = datetime.now()

    nudges_file = _nudges_path(data_dir)
    existing = load_ledger(nudges_file)

    new_records: list[dict] = []
    suppressed = 0
    non_critical = 0

    for alert in alerts:
        if not is_critical(alert):
            non_critical += 1
            continue
        task_id = alert["task_id"]
        alert_type = alert["type"]
        if is_in_cooldown(task_id, alert_type, existing, cooldown_hours, now):
            suppressed += 1
            continue
        record = {
            "type": "nudge",
            "id": f"nudge_{uuid.uuid4().hex[:8]}",
            "task_id": task_id,
            "alert_type": alert_type,
            "text_frag": _format_nudge_fragment(alert),
            "created_at": now.isoformat(),
        }
        # Inclui campos contextuais do alerta pra debug
        for k in ("days_overdue", "hours_since_update", "postpone_count", "priority", "due_date"):
            if k in alert:
                record[k] = alert[k]
        append_record(nudges_file, record)
        new_records.append(record)

    return {
        "nudges_new": len(new_records),
        "suppressed_by_cooldown": suppressed,
        "non_critical_skipped": non_critical,
        "emit_text": _build_emit_text(new_records),
        "nudges_records": new_records,
    }


def get_pending_nudges(data_dir: Path) -> list[dict]:
    """Retorna nudges ainda não 'acked' (sem registro type='nudge_ack' correspondente)."""
    nudges_file = _nudges_path(data_dir)
    records = load_ledger(nudges_file)
    acked_ids = {r["nudge_id"] for r in records if r.get("type") == "nudge_ack"}
    return [r for r in records if r.get("type") == "nudge" and r.get("id") not in acked_ids]


def ack_nudge(data_dir: Path, nudge_id: str, source: str = "manual") -> dict:
    """Marca um nudge como acked (append-only)."""
    nudges_file = _nudges_path(data_dir)
    record = {
        "type": "nudge_ack",
        "nudge_id": nudge_id,
        "acked_at": datetime.now().isoformat(),
        "ack_source": source,
    }
    append_record(nudges_file, record)
    return record
