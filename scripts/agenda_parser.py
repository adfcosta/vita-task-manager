"""Parser de agenda_da_semana.md — compromissos pontuais da semana."""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

try:
    from .models import AgendaEntry
except ImportError:
    from models import AgendaEntry


# Regex para linha de compromisso: "- 14:00 — Médico" ou "- 14:00 | Reunião"
AGENDA_LINE_RE = re.compile(r'^-\s*(\d{1,2}:\d{2})\s*[-–—|]\s*(.+)$')

# Regex para seção de dia: "## Segunda 07/04" ou "## Terça 08/04"
DAY_SECTION_RE = re.compile(r'^##\s*(.+?)\s+(\d{1,2}/\d{1,2})$')


def _parse_date(date_str: str, year: int) -> date:
    """Converte DD/MM em date (assume ano fornecido)."""
    day, month = map(int, date_str.split("/"))
    return date(year, month, day)


def parse_agenda_semana(path: str | Path, year: int) -> dict[date, list[AgendaEntry]]:
    """Parseia agenda_da_semana.md e retorna dict mapeando data → lista de entradas.

    Formato esperado:
        # Agenda da Semana — 06/04 a 12/04/2026

        ## Domingo 06/04

        ## Segunda 07/04
        - 14:00 — Médico
        - 22:00 — Reunião

        ## Terça 08/04
        - 10:00 — Dentista
    """
    entries_by_date: dict[date, list[AgendaEntry]] = {}
    lines = Path(path).read_text(encoding="utf-8").splitlines()

    current_date: Optional[date] = None

    for line in lines:
        line = line.rstrip()

        # Parse seção de dia
        section_match = DAY_SECTION_RE.match(line)
        if section_match:
            try:
                current_date = _parse_date(section_match.group(2), year)
                entries_by_date[current_date] = []
            except (ValueError, IndexError):
                current_date = None
            continue

        # Parse entrada de compromisso
        if line.startswith("-") and current_date:
            entry = _parse_agenda_line(line)
            if entry:
                entries_by_date[current_date].append(entry)

    return entries_by_date


def _parse_agenda_line(line: str) -> Optional[AgendaEntry]:
    """Parseia uma linha de agenda (- HH:MM — Descrição)."""
    match = AGENDA_LINE_RE.match(line)
    if not match:
        return None

    time_str = match.group(1)
    description = match.group(2).strip()

    # Normaliza horário para HH:MM
    if len(time_str.split(":")) == 2:
        try:
            hour, minute = map(int, time_str.split(":"))
            time_str = f"{hour:02d}:{minute:02d}"
        except ValueError:
            pass

    return AgendaEntry(
        time=time_str,
        description=description,
    )


def get_entries_for_date(entries_by_date: dict[date, list[AgendaEntry]], on_date: date) -> list[AgendaEntry]:
    """Retorna entradas para a data específica."""
    return entries_by_date.get(on_date, [])
