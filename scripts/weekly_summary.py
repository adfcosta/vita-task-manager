"""Geração de resumo semanal a partir do ledger JSONL."""

from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .ledger import load_ledger
except ImportError:
    from ledger import load_ledger


def _merge_tasks(ledger: list[dict]) -> dict[str, dict]:
    tasks: dict[str, dict] = {}
    for record in ledger:
        if record.get("type") != "task":
            continue
        tid = record["id"]
        if record.get("_operation") == "create" or tid not in tasks:
            tasks[tid] = {k: v for k, v in record.items() if not k.startswith("_")}
        else:
            tasks[tid].update({
                k: v for k, v in record.items()
                if not k.startswith("_") and k not in ("type", "id") and v is not None
            })
    return tasks


def build_weekly_summary(ledger_path: Path) -> dict[str, Any]:
    ledger = load_ledger(ledger_path)
    tasks = _merge_tasks(ledger)

    completed = []
    cancelled = []
    open_tasks = []
    by_priority = {"🔴": 0, "🟡": 0, "🟢": 0}

    for task in tasks.values():
        by_priority[task.get("priority", "🟢")] = by_priority.get(task.get("priority", "🟢"), 0) + 1
        status = task.get("status", "[ ]")
        if status == "[x]":
            completed.append(task)
        elif status == "[-]":
            cancelled.append(task)
        else:
            open_tasks.append(task)

    return {
        "ledger_path": str(ledger_path),
        "total_tasks": len(tasks),
        "completed": len(completed),
        "cancelled": len(cancelled),
        "open": len(open_tasks),
        "by_priority": by_priority,
        "completed_tasks": [
            {
                "description": t.get("description"),
                "priority": t.get("priority"),
                "completed_at": t.get("completed_at"),
            }
            for t in completed
        ],
        "cancelled_tasks": [
            {
                "description": t.get("description"),
                "priority": t.get("priority"),
                "reason": t.get("reason"),
            }
            for t in cancelled
        ],
    }


def render_weekly_summary_markdown(summary: dict[str, Any]) -> str:
    parts = [f"# Resumo Semanal", ""]
    parts.append(f"- Total: {summary['total_tasks']}")
    parts.append(f"- Concluídas: {summary['completed']}")
    parts.append(f"- Canceladas: {summary['cancelled']}")
    parts.append(f"- Abertas: {summary['open']}")
    parts.append("")
    parts.append(
        f"- Por prioridade: 🔴 {summary['by_priority'].get('🔴', 0)} | 🟡 {summary['by_priority'].get('🟡', 0)} | 🟢 {summary['by_priority'].get('🟢', 0)}"
    )
    parts.append("")

    if summary["completed_tasks"]:
        parts.append("## Concluídas")
        parts.append("")
        for item in summary["completed_tasks"]:
            parts.append(f"- {item['priority']} {item['description']} — {item.get('completed_at') or 'sem data'}")
        parts.append("")

    if summary["cancelled_tasks"]:
        parts.append("## Canceladas")
        parts.append("")
        for item in summary["cancelled_tasks"]:
            reason = item.get("reason") or "sem motivo"
            parts.append(f"- {item['priority']} {item['description']} — {reason}")
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"
