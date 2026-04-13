"""Lógica de decisão sobre refresh de feedback."""

from datetime import date, datetime, timedelta
from typing import Literal, Optional

try:
    from .ledger import get_all_feedback_for_day, get_changes_since, load_ledger
except ImportError:
    from ledger import get_all_feedback_for_day, get_changes_since, load_ledger


def should_offer_feedback_refresh(
    ledger: list[dict],
    today: date,
    now: Optional[datetime] = None,
) -> tuple[Literal["required", "offer", "skip"], dict]:
    """Determina se deve gerar/atualizar feedback.

    Retorna:
        - "required": primeiro feedback do dia (gerar sem perguntar)
        - "offer": condições atingidas, perguntar à Vita
        - "skip": nada mudou, manter existente

    E também retorna dict com contexto (last_feedback, changes_since, etc.)
    """
    if now is None:
        now = datetime.now()

    context = {
        "last_feedback": None,
        "changes_since": [],
        "hours_since_last": None,
        "feedbacks_today": [],
    }

    # Feedback de hoje
    feedbacks_today = get_all_feedback_for_day(ledger, today)
    context["feedbacks_today"] = feedbacks_today

    # Se não há feedback hoje → required (primeiro do dia)
    if not feedbacks_today:
        return "required", context

    # Último feedback
    last_feedback = feedbacks_today[-1]
    context["last_feedback"] = last_feedback

    # Calcula horas desde último feedback
    last_ts = last_feedback.get("timestamp", "")
    if last_ts:
        try:
            last_dt = datetime.fromisoformat(last_ts)
            hours_since = (now - last_dt).total_seconds() / 3600
            context["hours_since_last"] = hours_since
        except:
            hours_since = 0
    else:
        hours_since = 0

    # Houve mudanças desde o último feedback?
    if last_ts:
        try:
            last_dt = datetime.fromisoformat(last_ts)
            changes = get_changes_since(ledger, last_dt)
            context["changes_since"] = changes
        except:
            changes = []
    else:
        changes = []

    # Se passou +3h ou houve CRUD → offer (perguntar)
    if changes or hours_since >= 3:
        return "offer", context

    # Nada mudou significativamente → skip
    return "skip", context
