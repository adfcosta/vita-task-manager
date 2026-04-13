"""Pipeline diário — orquestrador completo."""

from pathlib import Path
from typing import Any, Optional

try:
    from .feedback_logic import should_offer_feedback_refresh
    from .ledger import get_ledger_path, load_ledger
    from .ledger_ops import sync_fixed_agenda
    from .render import render_daily
    from .rollover import perform_rollover
    from .utils import ddmm_to_date
except ImportError:
    from feedback_logic import should_offer_feedback_refresh
    from ledger import get_ledger_path, load_ledger
    from ledger_ops import sync_fixed_agenda
    from render import render_daily
    from rollover import perform_rollover
    from utils import ddmm_to_date


def daily_pipeline(
    today_ddmm: str,
    year: int,
    rotina_path: Path,
    agenda_semana_path: Optional[Path],
    data_dir: Path,
    output_path: Path,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Executa pipeline completo do dia.

    Passos:
    1. Rollover dominical (se couber)
    2. Sync rotina fixa
    3. Avalia estado do feedback
    4. Render saída do dia
    """
    today = ddmm_to_date(today_ddmm, year)
    ledger_path = get_ledger_path(today, year, data_dir)

    results = {
        "ledger_path": str(ledger_path),
        "rollover": {"performed": False},
        "sync_fixed": {"inserted": [], "skipped": []},
        "feedback_status": "skip",
        "feedback_seed": {},
        "last_feedback": None,
        "changes_since": [],
        "output_path": str(output_path),
        "summary": {},
    }

    # 1. Domingo: tenta rollover antes de qualquer coisa.
    # A própria função decide se precisa ou não.
    if today.weekday() == 6:  # domingo
        results["rollover"] = perform_rollover(data_dir, today, year)

    # Recalcula ledger_path porque rollover pode ter criado o da semana nova
    ledger_path = get_ledger_path(today, year, data_dir)
    results["ledger_path"] = str(ledger_path)

    # 2. Sync rotina
    if rotina_path.exists():
        results["sync_fixed"] = sync_fixed_agenda(
            rotina_path=rotina_path,
            ledger_path=ledger_path,
            today_ddmm=today_ddmm,
            year=year,
        )

    # 3. Estado do feedback
    ledger = load_ledger(ledger_path)
    status, context = should_offer_feedback_refresh(ledger, today)
    if force_refresh and status == "skip":
        status = "offer"
    results["feedback_status"] = status
    results["last_feedback"] = context.get("last_feedback")
    results["changes_since"] = context.get("changes_since", [])

    # 4. Render saída do dia
    taskfile, feedback_seed = render_daily(
        ledger_path=ledger_path,
        agenda_semana_path=agenda_semana_path,
        today_ddmm=today_ddmm,
        year=year,
    )
    results["feedback_seed"] = feedback_seed

    try:
        from .formatter_whatsapp import format_task_file_whatsapp
    except ImportError:
        from formatter_whatsapp import format_task_file_whatsapp
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        format_task_file_whatsapp(taskfile, today), encoding="utf-8"
    )

    results["summary"] = {
        "open": len(taskfile.open_tasks),
        "completed_today": len(taskfile.completed_tasks),
        "cancelled_today": len(taskfile.cancelled_tasks),
        "compromissos": len(taskfile.compromissos_dia),
    }

    return results
