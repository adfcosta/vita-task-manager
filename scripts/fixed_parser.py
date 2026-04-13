"""Parser de rotina.md — rotina diária."""

import re
from datetime import date
from pathlib import Path
from typing import Optional

try:
    from .models import FixedEntry
except ImportError:
    from models import FixedEntry


# Regex para horário no início: "06:00 |" ou "6:00|"
TIME_RE = re.compile(r'^(\d{1,2}:\d{2})\s*\|')


def parse_rotina(path: str | Path) -> list[FixedEntry]:
    """Parseia rotina.md e retorna lista de FixedEntry.

    Formato esperado:
        # Rotina

        ## Tarefas Diárias

        - 06:00 | Meditação 10min
        - 07:00 | Café da manhã
        - 08:00 | Revisar e-mails

    Cada linha que começa com "-" é uma entrada.
    Extrai: horário (HH:MM |), descrição (restante).
    Sem prioridade — a prioridade é definida manualmente ou pelo CLI depois.
    """
    entries: list[FixedEntry] = []
    lines = Path(path).read_text(encoding="utf-8").splitlines()

    in_tarefas_diarias = False

    for raw_line in lines:
        line = raw_line.rstrip()

        # Detecta início da seção de tarefas diárias
        if line.startswith("## "):
            # Normaliza acentos para comparação
            normalized_line = line.lower()
            for old, new in [('á', 'a'), ('ã', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u'), ('ç', 'c')]:
                normalized_line = normalized_line.replace(old, new)
            in_tarefas_diarias = "tarefas diarias" in normalized_line
            continue

        # Ignora linhas que não são itens de lista
        if not line.startswith("-"):
            continue

        # Só processa se estiver na seção de tarefas diárias
        if not in_tarefas_diarias:
            continue

        entry = _parse_entry_line(line)
        if entry:
            entries.append(entry)

    return entries


def _parse_entry_line(line: str) -> Optional[FixedEntry]:
    """Parseia uma linha de tarefa.

    Formato: "- 06:00 | Descrição da tarefa"
             "- 08:00|Revisar e-mails"
    """
    # Remove o prefixo "- "
    line = line.lstrip("- ").strip()

    # Extrai horário (HH:MM |)
    time_range = None
    time_match = TIME_RE.match(line)
    if time_match:
        time_range = time_match.group(1)
        line = line[time_match.end():].strip()

    # O restante é a descrição
    description = line.strip()
    if not description:
        return None

    return FixedEntry(
        description=description,
        recurrence="daily",
        time_range=time_range,
        priority="🟢",  # padrão neutro — user define depois
    )


def get_entries_for_date(entries: list[FixedEntry], on_date: date) -> list[FixedEntry]:
    """Retorna todas as entradas (são todas daily)."""
    return entries
