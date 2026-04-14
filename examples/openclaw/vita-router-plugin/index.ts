// ------------------------------------------------------------------
// Vita Router Plugin — Plugin SDK para OpenClaw (Fase 2)
//
// Intercepta mensagens no Janus, classifica intenção CRUD sem LLM
// e executa localmente via CLI quando possível. Operações complexas
// passam direto para a sessão da Vita via routing normal.
//
// Usa process-runtime do SDK (não child_process) para execução
// de comandos — aprovado pelo scanner de segurança.
//
// Referência: patches/vita-SESSION-DESIGN.md (Camada 4)
// ------------------------------------------------------------------

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { classifyIntent } from "./classify.js";
import { executeCrud, checkAlerts, formatCrudResponse } from "./vita-cli.js";
import type { VitaCliConfig } from "./vita-cli.js";

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------

function getTodayAndYear(timezone: string): { today: string; year: number } {
  const now = new Date(
    new Date().toLocaleString("en-US", { timeZone: timezone }),
  );
  const dd = String(now.getDate()).padStart(2, "0");
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  return { today: `${dd}/${mm}`, year: now.getFullYear() };
}

// ------------------------------------------------------------------
// Plugin
// ------------------------------------------------------------------

export default definePluginEntry({
  id: "vita-router",
  name: "Vita Router",
  description:
    "Classifica intenções CRUD de tasks e executa localmente, " +
    "delegando operações complexas para a sessão da Vita.",

  register(api) {
    const pluginCfg = api.pluginConfig as {
      vitaSkillPath?: string;
      timezone?: string;
    };

    if (!pluginCfg.vitaSkillPath) {
      api.logger.error("vitaSkillPath não configurado — plugin desativado");
      return;
    }

    const vitaSkillPath = pluginCfg.vitaSkillPath;
    const timezone = pluginCfg.timezone ?? "America/Maceio";
    const cliConfig: VitaCliConfig = {
      vitaSkillPath,
      dataDir: `${vitaSkillPath}/data`,
    };

    // ----------------------------------------------------------------
    // Tool: vita_check_alerts
    // ----------------------------------------------------------------
    api.registerTool({
      name: "vita_check_alerts",
      description:
        "Verifica alertas pendentes de tasks (due_today, overdue, stalled, blocked). " +
        "Execução local sem tokens de LLM.",
      parameters: {
        type: "object" as const,
        properties: {},
        additionalProperties: false,
      },
      async execute() {
        try {
          const { today, year } = getTodayAndYear(timezone);
          const alerts = await checkAlerts(today, year, cliConfig);
          return {
            content: [{ type: "text", text: JSON.stringify(alerts, null, 2) }],
          };
        } catch (err) {
          return {
            content: [
              { type: "text", text: `Erro ao verificar alertas: ${err}` },
            ],
          };
        }
      },
    });

    // ----------------------------------------------------------------
    // Tool: vita_quick_crud
    // ----------------------------------------------------------------
    api.registerTool({
      name: "vita_quick_crud",
      description:
        "Executa operação CRUD rápida em tasks (complete, add, cancel, start) " +
        "diretamente via CLI, sem gastar tokens de LLM. Usar quando a " +
        "intenção do usuário for clara e direta. Se retornar warning de " +
        "duplicata, escalar para a Vita via sessão.",
      parameters: {
        type: "object" as const,
        properties: {
          message: {
            type: "string",
            description:
              "Mensagem do usuário em linguagem natural (ex: 'terminei relatório')",
          },
        },
        required: ["message"],
        additionalProperties: false,
      },
      async execute(_id: string, params: { message: string }) {
        const { today, year } = getTodayAndYear(timezone);
        const intent = classifyIntent(params.message);

        // Não é CRUD claro → recusa, Janus deve delegar pra Vita
        if (intent.type === "complex" || intent.confidence < 0.8) {
          return {
            content: [
              {
                type: "text",
                text: JSON.stringify({
                  handled: false,
                  reason: "intent_complex",
                  message:
                    "Intenção não é CRUD simples. Delegar para sessão da Vita.",
                }),
              },
            ],
          };
        }

        try {
          const result = await executeCrud(intent, today, year, cliConfig);

          // Duplicate Guardrail: warning → Janus deve escalar pra Vita
          if (
            (result as Record<string, any>).warning?.type ===
            "duplicate_suspect"
          ) {
            return {
              content: [
                {
                  type: "text",
                  text: JSON.stringify({
                    handled: false,
                    reason: "duplicate_warning",
                    warning: (result as Record<string, any>).warning,
                    message:
                      "Possível duplicata detectada. Escalar para Vita " +
                      "apresentar opções ao usuário (Duplicate Guardrail).",
                  }),
                },
              ],
            };
          }

          return {
            content: [
              {
                type: "text",
                text: JSON.stringify({
                  handled: true,
                  reply: formatCrudResponse(intent.type, result),
                  result,
                }),
              },
            ],
          };
        } catch (err) {
          // CLI falhou → Janus deve delegar pra Vita como fallback
          return {
            content: [
              {
                type: "text",
                text: JSON.stringify({
                  handled: false,
                  reason: "cli_error",
                  error: String(err),
                  message: "CLI falhou. Delegar para sessão da Vita.",
                }),
              },
            ],
          };
        }
      },
    });

    api.logger.info(
      `Vita Router ativo — skill: ${vitaSkillPath}, tz: ${timezone}`,
    );
  },
});
