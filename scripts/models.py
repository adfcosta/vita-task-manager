"""Modelos de dados do vita-task-manager."""

from dataclasses import dataclass, field
from typing import Any, Optional


VALID_STATUSES = {"[ ]", "[~]", "[x]", "[-]"}
VALID_PRIORITIES = {"🔴", "🟡", "🟢"}
VALID_SOURCES = {"rotina", "agenda_semana", "manual", "brain_dump", None}
VALID_COMPLEXITY_SOURCES = {"user", "ai", "inferred", None}
VALID_ENERGY_LEVELS = {"high", "medium", "low", None}


@dataclass
class Task:
    status: str
    priority: str
    description: str

    due_date: Optional[str] = None

    progress_percent: Optional[int] = None
    progress_done: Optional[int] = None
    progress_total: Optional[int] = None
    unit: Optional[str] = None
    progress_bar: Optional[str] = None

    remaining_value: Optional[int] = None
    remaining_text: Optional[str] = None

    daily_goal_value: Optional[int] = None
    daily_goal_text: Optional[str] = None

    context: Optional[str] = None
    note: Optional[str] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    reason: Optional[str] = None

    source: Optional[str] = None        # "rotina" | "agenda_semana" | "manual" | "brain_dump" | None
    carried_from: Optional[str] = None  # ID do bruto anterior se veio de rollover
    id: Optional[str] = None

    complexity_score: Optional[int] = None
    complexity_source: Optional[str] = None
    first_added_date: Optional[str] = None
    postpone_count: int = 0
    energy_required: Optional[str] = None
    score_breakdown: dict[str, Any] = field(default_factory=dict)
    total_score: Optional[float] = None


@dataclass
class FixedEntry:
    """Entrada parseada de rotina.md."""
    description: str
    recurrence: str          # "daily" | "weekly:segunda" | "weekly:quarta" etc.
    time_range: Optional[str] = None  # "19:30 – 21:30"
    priority: str = "🔴"     # compromissos fixos = alta prioridade


@dataclass
class AgendaEntry:
    """Entrada parseada de agenda_da_semana.md."""
    time: str                # "14:00"
    description: str         # "Médico"


@dataclass
class BrainDumpEntry:
    """Entrada de brain dump — captura rápida de sobrecarga mental."""
    id: str
    text: str
    created_at: str
    due_date: Optional[str] = None  # DD/MM/YYYY ou similar
    converted_to_task: Optional[str] = None  # ID da task se promovido


@dataclass
class SuggestedTask:
    task_id: str
    title: str
    score: float
    size_category: str
    explanation: str
    position: int = 0


@dataclass
class TaskFile:
    title: str = "Tasks"
    open_tasks: list[Task] = field(default_factory=list)
    completed_tasks: list[Task] = field(default_factory=list)
    cancelled_tasks: list[Task] = field(default_factory=list)
    feedback_do_dia: dict[str, str] = field(default_factory=dict)
    compromissos_dia: list[AgendaEntry] = field(default_factory=list)
    brain_dumps: list[BrainDumpEntry] = field(default_factory=list)
    suggestion_135: dict[str, list[SuggestedTask]] = field(
        default_factory=lambda: {"big": [], "medium": [], "small": []}
    )

    @property
    def all_tasks(self) -> list[Task]:
        return self.open_tasks + self.completed_tasks + self.cancelled_tasks
