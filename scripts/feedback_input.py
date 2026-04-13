try:
    from .models import Task, TaskFile
    from .sorter import sort_open_tasks
    from .utils import days_remaining
except ImportError:
    from models import Task, TaskFile
    from sorter import sort_open_tasks
    from utils import days_remaining


def _risk_for_task(task: Task, today_ddmm: str, year: int) -> tuple[str, str] | None:
    if task.status not in {"[ ]", "[~]"} or not task.due_date:
        return None

    dr = days_remaining(today_ddmm, task.due_date, year)
    if dr < 0:
        return ("alto", "task atrasada")

    if task.progress_done is not None and task.progress_total is not None:
        remaining = task.progress_total - task.progress_done
        if remaining <= 0:
            return None
        if dr == 0:
            return ("alto", "prazo hoje e ainda há trabalho pendente")
        if dr > 0:
            daily_goal = -(-remaining // dr)
            if daily_goal >= 25:
                return ("alto", "carga diária necessária está alta")
            if daily_goal >= 10:
                return ("medio", "ritmo diário necessário exige constância")

    if dr <= 1:
        return ("alto", "prazo muito próximo")
    if dr <= 3:
        return ("medio", "prazo se aproximando")
    return None


def build_daily_summary(task_file: TaskFile, today_ddmm: str, year: int) -> dict:
    open_sorted = sort_open_tasks(task_file.open_tasks, today_ddmm, year)
    overdue_tasks: list[str] = []
    due_today: list[str] = []
    high_priority_open: list[str] = []
    at_risk_tasks: list[dict[str, str]] = []

    for task in open_sorted:
        if task.priority == "🔴":
            high_priority_open.append(task.description)

        if task.due_date:
            dr = days_remaining(today_ddmm, task.due_date, year)
            if dr < 0:
                overdue_tasks.append(task.description)
            elif dr == 0:
                due_today.append(task.description)

        risk = _risk_for_task(task, today_ddmm, year)
        if risk:
            level, reason = risk
            at_risk_tasks.append({"description": task.description, "risk": level, "reason": reason})

    return {
        "has_overdue": bool(overdue_tasks),
        "overdue_tasks": overdue_tasks,
        "due_today": due_today,
        "high_priority_open": high_priority_open,
        "at_risk_tasks": at_risk_tasks,
        "suggested_focus": open_sorted[0].description if open_sorted else None,
        "open_count": len(task_file.open_tasks),
        "completed_count": len(task_file.completed_tasks),
        "cancelled_count": len(task_file.cancelled_tasks),
    }


def build_feedback_seed(summary: dict) -> dict[str, str]:
    panorama = "Há tasks abertas no dia."
    foco = summary.get("suggested_focus") or "Manter avanço nas tasks abertas."
    alerta = "Sem alertas relevantes no momento."
    acao = "Atacar primeiro a task mais urgente."

    if summary["has_overdue"]:
        panorama = "Há tasks atrasadas e isso pede reorganização imediata."
        alerta = "Existem pendências vencidas."
        acao = "Resolver primeiro a mais crítica entre as atrasadas."
    elif summary["due_today"]:
        panorama = "Há tasks com vencimento hoje."
        alerta = "O prazo curto reduz a margem para adiar."
        acao = "Fechar primeiro as tasks que vencem hoje."
    elif summary["at_risk_tasks"]:
        panorama = "Há tasks abertas e pelo menos uma merece atenção especial."
        alerta = summary["at_risk_tasks"][0]["reason"]
        acao = "Garantir avanço hoje na task com maior risco."

    return {
        "panorama": panorama,
        "foco": summary.get("suggested_focus") or foco,
        "alerta": alerta,
        "acao_sugerida": acao,
    }


def validate_feedback(feedback: dict[str, str]) -> list[str]:
    required = ("panorama", "foco", "alerta", "acao_sugerida")
    return [f"Campo obrigatório ausente no feedback: {field}" for field in required if not feedback.get(field)]
