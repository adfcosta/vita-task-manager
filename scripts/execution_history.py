"""Relatório de padrões de execução a partir do ledger JSONL.

Gera métricas de completion rate, análise por source, tasks mais
adiadas e desempenho por dia da semana.
"""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    from .ledger import (
        get_week_start,
        get_week_end,
        load_ledger,
        _merge_task_records,
        _parse_record_date,
    )
except ImportError:
    from ledger import (
        get_week_start,
        get_week_end,
        load_ledger,
        _merge_task_records,
        _parse_record_date,
    )


WEEKDAY_NAMES = [
    "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo",
]

# Reordenado para começar no domingo (convenção do vita)
WEEKDAY_ORDER = [6, 0, 1, 2, 3, 4, 5]  # domingo, segunda, ..., sábado


def _collect_ledger_files(data_dir: Path, today: date, weeks: int) -> list[Path]:
    """Coleta todos os .jsonl dentro do período de análise."""
    historico_dir = data_dir / "historico"
    if not historico_dir.exists():
        return []

    cutoff = get_week_start(today) - timedelta(weeks=weeks - 1)
    files = []

    for path in sorted(historico_dir.glob("*_bruto.jsonl")):
        # Extrai data de início do nome: DDMMYY_DDMMYY_bruto.jsonl
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


def _merge_all_tasks(data_dir: Path, today: date, weeks: int) -> list[dict[str, Any]]:
    """Carrega e mergea tasks de todos os ledgers no período."""
    all_records: list[dict[str, Any]] = []
    for path in _collect_ledger_files(data_dir, today, weeks):
        all_records.extend(load_ledger(path))

    merged = _merge_task_records(all_records)
    return list(merged.values())


def _week_label(week_start: date, week_end: date, today: date) -> str:
    """Gera label legível para a semana."""
    ws = f"{week_start:%d/%m}"
    we = f"{week_end:%d/%m}"
    if week_start <= today <= week_end:
        return f"Atual ({ws}-{we})"
    return f"{ws}-{we}"


def _calculate_completion_rate(
    tasks: list[dict[str, Any]], today: date, weeks: int,
) -> dict[str, Any]:
    """Taxa de conclusão semanal."""
    weekly = []
    current_week_start = get_week_start(today)

    for i in range(weeks):
        ws = current_week_start - timedelta(weeks=weeks - 1 - i)
        we = get_week_end(ws)

        week_tasks = [
            t for t in tasks
            if _task_created_in_range(t, ws, we)
        ]
        total = len(week_tasks)
        completed = sum(1 for t in week_tasks if t.get("status") == "[x]")
        rate = completed / total if total > 0 else 0.0

        weekly.append({
            "label": _week_label(ws, we, today),
            "completed": completed,
            "total": total,
            "rate": round(rate, 2),
        })

    rates = [w["rate"] for w in weekly if w["total"] > 0]
    average = round(sum(rates) / len(rates), 2) if rates else 0.0

    return {"weekly": weekly, "average": average}


def _task_created_in_range(task: dict, start: date, end: date) -> bool:
    """Verifica se task foi criada dentro do range de datas."""
    created = _parse_record_date(task.get("created_at"))
    if not created:
        return False
    return start <= created <= end


def _calculate_by_source(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Métricas agrupadas por source."""
    buckets: dict[str, dict[str, int]] = {}

    for task in tasks:
        source = task.get("source") or "manual"
        if source not in buckets:
            buckets[source] = {"created": 0, "completed": 0}
        buckets[source]["created"] += 1
        if task.get("status") == "[x]":
            buckets[source]["completed"] += 1

    result = []
    for source, counts in sorted(buckets.items()):
        rate = counts["completed"] / counts["created"] if counts["created"] > 0 else 0.0
        result.append({
            "source": source,
            "created": counts["created"],
            "completed": counts["completed"],
            "rate": round(rate, 2),
        })

    return result


def _calculate_top_postponed(
    tasks: list[dict[str, Any]], today: date, limit: int = 5,
) -> list[dict[str, Any]]:
    """Top tasks mais adiadas (ainda abertas)."""
    candidates = []

    for task in tasks:
        status = task.get("status", "")
        if status not in ("[ ]", "[~]"):
            continue

        postpone_count = int(task.get("postpone_count") or 0)
        if postpone_count < 1:
            continue

        first_added = _parse_record_date(
            task.get("first_added_date") or task.get("created_at")
        )
        days_in_list = (today - first_added).days if first_added else 0

        candidates.append({
            "description": task.get("description", "?"),
            "postpone_count": postpone_count,
            "days_in_list": days_in_list,
        })

    candidates.sort(key=lambda c: (-c["postpone_count"], -c["days_in_list"]))
    return candidates[:limit]


def _calculate_by_weekday(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Taxa de conclusão por dia da semana."""
    buckets: dict[int, dict[str, int]] = {i: {"total": 0, "completed": 0} for i in range(7)}

    for task in tasks:
        created = _parse_record_date(task.get("created_at"))
        if not created:
            continue
        wd = created.weekday()  # 0=Monday, 6=Sunday
        buckets[wd]["total"] += 1
        if task.get("status") == "[x]":
            buckets[wd]["completed"] += 1

    result = []
    for wd in WEEKDAY_ORDER:
        b = buckets[wd]
        rate = b["completed"] / b["total"] if b["total"] > 0 else 0.0
        result.append({
            "day": WEEKDAY_NAMES[wd],
            "rate": round(rate, 2),
            "sample": b["total"],
        })

    # Ordena por menor rate primeiro (piores dias no topo)
    result.sort(key=lambda x: x["rate"])
    return result


def build_execution_history(
    data_dir: Path,
    today: date,
    weeks: int = 4,
) -> dict[str, Any]:
    """Constrói relatório completo de padrões de execução."""
    tasks = _merge_all_tasks(data_dir, today, weeks)

    return {
        "generated_at": f"{today:%d/%m/%Y}",
        "weeks_analyzed": weeks,
        "completion_rate": _calculate_completion_rate(tasks, today, weeks),
        "by_source": _calculate_by_source(tasks),
        "top_postponed": _calculate_top_postponed(tasks, today),
        "by_weekday": _calculate_by_weekday(tasks),
    }


def render_markdown(history: dict[str, Any]) -> str:
    """Renderiza o dict de métricas como markdown."""
    lines: list[str] = []

    lines.append(f"Gerado em: {history['generated_at']}  ")
    lines.append(f"Período: últimas {history['weeks_analyzed']} semanas")
    lines.append("")

    # --- Completion Rate ---
    cr = history["completion_rate"]
    lines.append("### Taxa de Conclusão Semanal")
    lines.append("")
    lines.append("| Semana | Concluídas | Total | Taxa |")
    lines.append("|--------|-----------|-------|------|")
    for w in cr["weekly"]:
        lines.append(f"| {w['label']} | {w['completed']} | {w['total']} | {w['rate']:.0%} |")
    lines.append("")
    lines.append(f"**Média geral: {cr['average']:.0%}**")
    lines.append("")

    # --- By Source ---
    lines.append("### Por Origem")
    lines.append("")
    lines.append("| Origem | Criadas | Concluídas | Taxa |")
    lines.append("|--------|---------|-----------|------|")
    for s in history["by_source"]:
        lines.append(f"| {s['source']} | {s['created']} | {s['completed']} | {s['rate']:.0%} |")
    lines.append("")

    # --- Top Postponed ---
    top = history["top_postponed"]
    if top:
        lines.append("### Tasks Mais Adiadas")
        lines.append("")
        lines.append("| Task | Adiamentos | Dias na lista |")
        lines.append("|------|-----------|--------------|")
        for t in top:
            lines.append(f"| {t['description']} | {t['postpone_count']}x | {t['days_in_list']}d |")
        lines.append("")

    # --- By Weekday ---
    lines.append("### Desempenho por Dia da Semana")
    lines.append("")
    lines.append("| Dia | Taxa | Amostra |")
    lines.append("|-----|------|---------|")
    for d in history["by_weekday"]:
        lines.append(f"| {d['day']} | {d['rate']:.0%} | {d['sample']} tasks |")
    lines.append("")

    return "\n".join(lines)


BEGIN_MARKER = "<!-- BEGIN METRICS auto-gerado por `cli execution-history` -->"
END_MARKER = "<!-- END METRICS -->"

TEMPLATE_HEADER = """# Histórico de Execução

{begin_marker}
{{metrics}}
{end_marker}

## Observações

<!-- Espaço para anotações manuais. Não será sobrescrito pelo CLI. -->
""".format(begin_marker=BEGIN_MARKER, end_marker=END_MARKER)


def write_history_file(output_path: Path, history_markdown: str) -> None:
    """Escreve ou atualiza o arquivo de histórico de execução.

    Se o arquivo existir, substitui apenas o conteúdo entre os marcadores.
    Se não existir, cria usando o template.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        content = output_path.read_text(encoding="utf-8")
        begin_idx = content.find(BEGIN_MARKER)
        end_idx = content.find(END_MARKER)

        if begin_idx != -1 and end_idx != -1:
            before = content[:begin_idx]
            after = content[end_idx + len(END_MARKER):]
            new_content = (
                before
                + BEGIN_MARKER + "\n"
                + history_markdown
                + END_MARKER
                + after
            )
            output_path.write_text(new_content, encoding="utf-8")
            return

    # Arquivo não existe ou sem marcadores — cria do zero
    new_content = TEMPLATE_HEADER.replace("{metrics}", history_markdown)
    output_path.write_text(new_content, encoding="utf-8")
