# Vita Router Plugin

Plugin OpenClaw para o Janus que intercepta operações CRUD de tasks e executa localmente via CLI da Vita, sem gastar tokens de LLM.

## O que faz

| Situação | Ação | Custo |
|---|---|---|
| CRUD claro ("terminei relatório") | Executa CLI direto | 0 tokens |
| Warning de duplicata | Retorna `handled: false` → Janus escala pra Vita | ~1-3k tokens |
| Intenção complexa | Retorna `handled: false` → Janus delega pra Vita | ~1-3k tokens |
| CLI falhou | Retorna `handled: false` → Janus delega pra Vita | ~1-3k tokens |

## Tools registradas

### `vita_quick_crud`

Recebe mensagem em linguagem natural, classifica intenção e executa CRUD se possível.

```
Janus chama vita_quick_crud("terminei relatório")
  → classifyIntent → type: "complete", confidence: 0.9
  → execSync("cli ledger-complete --description ...")
  → { handled: true, reply: "Task marcada como concluída" }
```

Se `handled: false`, Janus segue o routing normal (sessions_send/spawn pra Vita).

### `vita_check_alerts`

Verifica alertas pendentes (due_today, overdue, stalled, blocked). Janus pode chamar antes de delegar pra Vita para enriquecer o contexto.

## Instalação

```bash
# Opção 1: instalar do path local
openclaw plugins install /caminho/para/vita-router-plugin
openclaw plugins enable vita-router

# Opção 2: copiar para extensões do workspace
cp -r vita-router-plugin ~/.openclaw/extensions/
```

## Configuração

No `openclaw.json`:

```json5
{
  "plugins": {
    "entries": {
      "vita-router": {
        "enabled": true,
        "config": {
          "vitaSkillPath": "/home/node/.openclaw/workspace/vita/skills/vita-task-manager",
          "timezone": "America/Maceio"
        }
      }
    }
  }
}
```

## Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `index.ts` | Entry point — registra tools e hooks |
| `classify.ts` | Classificação de intenção via regex (sem LLM) |
| `vita-cli.ts` | Wrapper para execução de comandos CLI da Vita |

## Integração com Janus

O plugin registra tools que o Janus pode usar no seu routing. O fluxo recomendado no AGENTS.md do Janus:

1. Mensagem chega sobre tasks
2. Janus chama `vita_quick_crud` com a mensagem
3. Se `handled: true` → entrega resposta ao usuário
4. Se `handled: false` → segue routing normal (sessions_send pra sessão viva, ou sessions_spawn)

## Referências

- `patches/vita-SESSION-DESIGN.md` — design completo (Camada 4)
- `patches/vita-AGENTS.md` — standing orders (Duplicate Guardrail)
- `examples/openclaw/janus-routing.ts` — snippet original de referência
