try:
    from .utils import ceil_div, clamp
except ImportError:
    from utils import ceil_div, clamp


def calculate_progress(done: int, total: int) -> int:
    if total <= 0:
        raise ValueError("total deve ser > 0")
    if done < 0:
        raise ValueError("done deve ser >= 0")
    if done > total:
        raise ValueError("done não pode ser maior que total")
    return int((done / total) * 100)


def build_progress_bar(percent: int) -> str:
    percent = clamp(percent, 0, 100)
    filled = round(percent / 10)
    return "▓" * filled + "░" * (10 - filled)


def calculate_remaining(done: int, total: int) -> int:
    if done > total:
        raise ValueError("done não pode ser maior que total")
    return total - done


def calculate_daily_goal(remaining: int, days_remaining: int) -> int:
    if remaining <= 0:
        return 0
    if days_remaining <= 0:
        return remaining
    return ceil_div(remaining, days_remaining)


def progress_text(percent: int, done: int, total: int, unit: str) -> str:
    return f"{percent}% ({done}/{total} {unit})"


def remaining_text(remaining: int, unit: str) -> str:
    return f"{remaining} {unit}"


def daily_goal_text(goal: int, unit: str) -> str:
    return f"{goal} {unit}/dia"