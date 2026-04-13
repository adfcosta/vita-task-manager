import datetime as dt
import math
import re
from typing import Optional


DDMM_RE = re.compile(r"^\d{2}/\d{2}$")
PROGRESS_RE = re.compile(r"^(\d+)% \((\d+)/(\d+) ([^)]+)\)$")
VALUE_UNIT_RE = re.compile(r"^(\d+)\s+(.+)$")
GOAL_RE = re.compile(r"^(\d+)\s+(.+?)/dia$")


def is_valid_ddmm(value: str) -> bool:
    if not DDMM_RE.match(value):
        return False
    day, month = map(int, value.split("/"))
    try:
        dt.date(2024, month, day)
    except ValueError:
        return False
    return True


def ddmm_to_date(value: str, year: int) -> dt.date:
    if not is_valid_ddmm(value):
        raise ValueError(f"Data inválida: {value}")
    day, month = map(int, value.split("/"))
    return dt.date(year, month, day)


def resolve_due_date(due_ddmm: str, today_ddmm: str, year: int) -> dt.date:
    """
    Resolve prazo considerando possível virada de ano.
    Se o prazo no mesmo ano ficar muito para trás em relação a hoje,
    assume ano seguinte.
    """
    due_this_year = ddmm_to_date(due_ddmm, year)
    today = ddmm_to_date(today_ddmm, year)

    if due_this_year < today and (today - due_this_year).days > 180:
        return dt.date(year + 1, due_this_year.month, due_this_year.day)

    return due_this_year


def days_remaining(today_ddmm: str, due_ddmm: str, year: int) -> int:
    today = ddmm_to_date(today_ddmm, year)
    due = resolve_due_date(due_ddmm, today_ddmm, year)
    return (due - today).days


def parse_progress_text(text: str) -> tuple[int, int, int, str]:
    m = PROGRESS_RE.match(text.strip())
    if not m:
        raise ValueError(f"Formato de progresso inválido: {text}")
    percent = int(m.group(1))
    done = int(m.group(2))
    total = int(m.group(3))
    unit = m.group(4).strip()
    return percent, done, total, unit


def parse_value_unit(text: str) -> tuple[int, str]:
    m = VALUE_UNIT_RE.match(text.strip())
    if not m:
        raise ValueError(f"Formato inválido: {text}")
    return int(m.group(1)), m.group(2).strip()


def parse_goal_text(text: str) -> tuple[int, str]:
    m = GOAL_RE.match(text.strip())
    if not m:
        raise ValueError(f"Formato de meta inválido: {text}")
    return int(m.group(1)), m.group(2).strip()


def safe_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def ceil_div(a: int, b: int) -> int:
    if b <= 0:
        raise ValueError("Divisor deve ser > 0")
    return math.ceil(a / b)


def clamp(n: int, smallest: int, largest: int) -> int:
    return max(smallest, min(n, largest))