try:
    from .models import Task, TaskFile
    from .utils import days_remaining
except ImportError:
    from models import Task, TaskFile
    from utils import days_remaining


# Pesos de prioridade: menor número = maior prioridade
PRIORITY_WEIGHT = {"🔴": 0, "🟡": 1, "🟢": 2}

# Pesos de status: em andamento vem antes de pendente
STATUS_WEIGHT = {"[~]": 0, "[ ]": 1, "[x]": 2, "[-]": 3}


def _task_sort_key(task: Task, today_ddmm: str, year: int):
    """
    Gera chave de ordenação para tarefas.
    
    Ordem de priorização:
    1. Atrasadas primeiro (prazo < hoje)
    2. Prazo mais próximo (menor due_rank)
    3. Prioridade: 🔴 > 🟡 > 🟢
    4. Status: [~] (em andamento) > [ ] (pendente)
    5. Descrição (alfabética)
    """
    overdue_flag = 1  # 0 = atrasada, 1 = não atrasada (0 vem primeiro)
    due_rank = 999999  # número de dias até o prazo

    if task.status in {"[ ]", "[~]"} and task.due_date:
        dr = days_remaining(today_ddmm, task.due_date, year)
        overdue_flag = 0 if dr < 0 else 1
        due_rank = dr if dr >= 0 else 0  # Atrasadas ficam com due_rank=0 para ordenar entre si

    return (
        overdue_flag,                           # 0=atrasada, 1=não atrasada
        due_rank,                               # menor = prazo mais próximo
        PRIORITY_WEIGHT.get(task.priority, 99), # 🔴=0, 🟡=1, 🟢=2
        STATUS_WEIGHT.get(task.status, 99),     # [~]=0, [ ]=1
        task.description.lower(),               # alfabética
    )


def sort_open_tasks(tasks: list[Task], today_ddmm: str, year: int) -> list[Task]:
    """
    Ordena tarefas abertas por prioridade e prazo.
    
    Prioridade de ordenação:
    1. Tarefas atrasadas (prazo < hoje)
    2. Tarefas com prazo hoje
    3. Tarefas 🔴 (alta prioridade)
    4. Tarefas 🟡 (média prioridade)
    5. Tarefas 🟢 (baixa prioridade)
    6. Dentro da mesma prioridade: em andamento > pendente
    7. Dentro do mesmo status: ordem alfabética
    """
    return sorted(tasks, key=lambda t: _task_sort_key(t, today_ddmm, year))


def sort_task_file(task_file: TaskFile, today_ddmm: str, year: int) -> TaskFile:
    """
    Ordena todas as tarefas do arquivo:
    - Abertas: por prioridade e prazo
    - Concluídas: por data de conclusão
    - Canceladas: por data de atualização
    """
    task_file.open_tasks = sort_open_tasks(task_file.open_tasks, today_ddmm, year)
    task_file.completed_tasks = sorted(
        task_file.completed_tasks, 
        key=lambda t: (t.completed_at or "", t.description.lower())
    )
    task_file.cancelled_tasks = sorted(
        task_file.cancelled_tasks, 
        key=lambda t: (t.updated_at or "", t.description.lower())
    )
    return task_file
