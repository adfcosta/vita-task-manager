"""Copy library para nudges do heartbeat.

Estrutura segue spec TDAH §7.3: **detecção + janela + ação mínima**.
Cada alert_type tem 2 variantes (A/B) selecionadas deterministicamente
por hash de (task_id, alert_type) — mesma task sempre mesma variante,
mas diferentes tasks distribuem entre A e B (base pra A/B testing em
v2.16.0 via campo `copy_variant` no record).

Para nudges agrupados (múltiplos alert_types na mesma task), usa
`render_grouped` — fallback com os sinais combinados + convite
genérico à menor ação.

Princípios (spec §7.2, §14.1):
- Curto, concreto
- Não punitivo, sem vergonha implícita
- Pede UMA ação, não várias
- Foca em destravar, não em terminar
"""

import hashlib


COPY_LIBRARY: dict[str, dict[str, str]] = {
    "overdue": {
        "A": '🌿 "{description}" atrasou {days_overdue}d. Em vez de terminar tudo, quer só destravar com uma subtarefa de 10–15min?',
        "B": '🌿 "{description}" passou do prazo ({days_overdue}d). Qual é o menor passo que conta como avanço hoje?',
    },
    "stalled": {
        "A": '🌿 "{description}" está parada há {hours_since_update}h. Um bloco curto hoje reinicia?',
        "B": '🌿 "{description}" ficou quieta há {hours_since_update}h. Qual a próxima ação concreta de 15min?',
    },
    "blocked": {
        "A": '🌿 Você adiou "{description}" {postpone_count}x. O que conta como avanço real mínimo hoje?',
        "B": '🌿 "{description}" foi adiada {postpone_count}x. Quer quebrar em algo de 5min que destrave o resto?',
    },
    "first_touch": {
        "A": '🌿 Vi que "{description}" ainda não foi tocada ({hours_since_created}h). Faz só o primeiro passo: abrir e definir a próxima ação?',
        "B": '🌿 "{description}" está na fila há {hours_since_created}h sem movimento. Define em 1 linha qual o primeiro passo?',
    },
    "off_pace": {
        "A": '🌿 "{description}" está em {done_units}/{total_units} — esperado ~{expected_units}. Um bloco curto hoje recoloca no trilho?',
        "B": '🌿 Ritmo de "{description}" ficou abaixo do esperado ({done_units}/{total_units}, faltam {days_remaining}d). Quer destravar com a próxima etapa menor?',
    },
    # due_soon, missed_routine entram em versões futuras (v2.17, v2.18).
}

VARIANTS: tuple[str, ...] = ("A", "B")
GROUPED_VARIANT = "grouped"


def render_nudge(alert: dict, variant: str = "A") -> str:
    """Renderiza copy pra um alerta único.

    Se `alert.type` não tiver entrada em COPY_LIBRARY (ex: due_today
    ainda sem copy definido), retorna string vazia — caller decide
    fallback.
    """
    t = alert.get("type")
    if t not in COPY_LIBRARY:
        return ""
    lib = COPY_LIBRARY[t]
    template = lib.get(variant) or lib.get("A") or next(iter(lib.values()))
    try:
        return template.format(**alert)
    except KeyError:
        # Faltou campo obrigatório no alert — retorna sem render
        return ""


def pick_variant(task_id: str, alert_type: str) -> str:
    """Escolhe A ou B deterministicamente (hash MD5 estável).

    Garantia: mesma task + mesmo alert_type → sempre mesma variante.
    Diferentes tasks distribuem razoavelmente entre A e B.
    """
    h = hashlib.md5(f"{task_id}:{alert_type}".encode()).hexdigest()
    return VARIANTS[int(h, 16) % len(VARIANTS)]


def _format_alert_part(alert: dict) -> str:
    """Fragmento curto por alerta, usado em copy grouped."""
    t = alert.get("type")
    if t == "overdue":
        return f"atrasada há {alert.get('days_overdue', '?')} dias"
    if t == "stalled":
        return f"parada há {alert.get('hours_since_update', '?')}h"
    if t == "blocked":
        return f"adiada {alert.get('postpone_count', '?')}x (bloqueio)"
    if t == "first_touch":
        return f"sem toque há {alert.get('hours_since_created', '?')}h"
    if t == "off_pace":
        return f"ritmo baixo ({alert.get('done_units', '?')}/{alert.get('total_units', '?')}, esperado ~{alert.get('expected_units', '?')})"
    if t == "due_today":
        return "vence hoje"
    return t or ""


def render_grouped(group_alerts: list[dict]) -> str:
    """Renderiza copy pra task com múltiplos alert_types.

    Formato: detecção combinada + convite a destravar.
    """
    if not group_alerts:
        return ""
    desc = group_alerts[0].get("description", "?")
    parts = [p for p in (_format_alert_part(a) for a in group_alerts) if p]
    if not parts:
        return ""
    combined = "; ".join(parts)
    return f'🌿 "{desc}" está em risco — {combined}. Quer destravar com a menor ação possível?'


def strip_prefix(text: str) -> str:
    """Remove emoji 🌿 e espaço inicial pra usar o fragmento em bullets."""
    if text.startswith("🌿 "):
        return text[len("🌿 "):]
    if text.startswith("🌿"):
        return text[len("🌿"):]
    return text
