# Setup

Instruções pra IA instalar ou atualizar a skill. Não é usuário.

## Detectar modo

Ler marcadores em `~/.openclaw/workspace/vita/AGENTS.md`:

| Marcadores `<!-- BEGIN vita-task-manager vX.Y.Z -->` | Modo |
|---|---|
| Ausentes | **Install** |
| Versão < `SKILL.md` header | **Update** |
| Versão = `SKILL.md` header | **No-op — parar** |

## Install

```bash
# 1. Skill presente? Se não, delegar cópia ao Faber.
ls ~/.openclaw/workspace/vita/skills/vita-task-manager/SKILL.md || exit 1

cd ~/.openclaw/workspace/vita/skills/vita-task-manager

# 2. Inputs do usuário
cp -n examples/rotina.md input/rotina.md
touch input/agenda-semana.md

# 3. Heartbeat config (opcional — sem, só persiste, não emite)
cp -n examples/openclaw/heartbeat-config.json.example data/heartbeat-config.json
# editar emit_target com canal real
```

4. **Patches AGENTS** (ver `patches/README.md` pro regex de apply):
   - `patches/vita-AGENTS.md` → inserir bloco entre marcadores **depois de** `### Não inclui` em `~/.openclaw/workspace/vita/AGENTS.md`.
   - `patches/janus-AGENTS.md` → inserir bloco entre marcadores **depois de** `## Protocolo de Delegação` em `~/.openclaw/workspace/janus/AGENTS.md`. **Primeiro remover** subseção `### Sessão persistente da Vita` se existir (modelo antigo).

5. **Cron OpenClaw** (standing orders):

```bash
openclaw cron create --agent vita --spec "0 6 * * *"    --cmd "cli daily-tick ..."
openclaw cron create --agent vita --spec "0 20 * * 0"   --cmd "cli weekly-tick ..."
openclaw cron create --agent vita --spec "*/55 6-23 * * *" --cmd "cli heartbeat-tick ..."
```

Template completo em `examples/openclaw/`.

6. **Smoke test:**

```bash
VITA_TEST_MODE=1 python3 scripts/test_core.py
python3 scripts/cli.py pipeline --today $(date +%d/%m) --year $(date +%Y) \
  --rotina input/rotina.md --agenda-semana input/agenda-semana.md \
  --data-dir data --output output/diarias.txt
```

Ambos devem retornar `ok: true` / exit 0.

## Update

Patches são idempotentes — substituir entre marcadores.

```bash
cd ~/.openclaw/workspace/vita/skills/vita-task-manager && git pull
```

Re-aplicar patches via regex sobre marcadores (código em `patches/README.md`):

- `~/.openclaw/workspace/vita/AGENTS.md` ← `patches/vita-AGENTS.md`
- `~/.openclaw/workspace/janus/AGENTS.md` ← `patches/janus-AGENTS.md`

Verificar que versão nos marcadores bate com `SKILL.md`.

Smoke test:

```bash
VITA_TEST_MODE=1 python3 scripts/test_core.py
```

Ledger é append-only + forward-compat → **nenhuma migração** de dados.

## Rollback

- AGENTS: `git show HEAD~1:patches/vita-AGENTS.md` → re-aplicar.
- Código: `git checkout <tag-anterior>`.
- Dados: nunca reverter — ledger preserva tudo.

## Nunca

- Rodar "migração de dados" (não existe).
- Editar `input/rotina.md` ou `input/agenda-semana.md`.
- Aplicar patch sem checar marcadores antes.
- Skip smoke test após update.
