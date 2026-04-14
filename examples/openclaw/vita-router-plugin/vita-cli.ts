// ------------------------------------------------------------------
// Wrapper para execução de comandos CLI da Vita
//
// Usa process-runtime do Plugin SDK (não child_process) para
// execução segura aprovada pelo scanner de segurança do OpenClaw.
// Todos os comandos retornam JSON parseado.
// ------------------------------------------------------------------

import { runExec } from "openclaw/plugin-sdk/process-runtime";
import type { VitaIntent } from "./classify.js";

const TIMEOUT_MS = 15_000;

export interface VitaCliConfig {
  vitaSkillPath: string;
  dataDir: string;
}

/**
 * Executa subcomando do CLI e retorna JSON parseado.
 */
async function runCli(
  config: VitaCliConfig,
  subcommand: string,
  args: string[],
): Promise<Record<string, unknown>> {
  const { stdout } = await runExec(
    "python3",
    [`${config.vitaSkillPath}/scripts/cli.py`, subcommand, ...args],
    { timeoutMs: TIMEOUT_MS, cwd: config.vitaSkillPath },
  );
  return JSON.parse(stdout);
}

/**
 * Constrói e executa comando CLI a partir da intenção classificada.
 */
export async function executeCrud(
  intent: VitaIntent,
  today: string,
  year: number,
  config: VitaCliConfig,
): Promise<Record<string, unknown>> {
  const baseArgs = [
    "--description", intent.params.description,
    "--today", today,
    "--year", String(year),
    "--data-dir", config.dataDir,
  ];

  switch (intent.type) {
    case "complete":
    case "start":
      return runCli(config, `ledger-${intent.type}`, baseArgs);
    case "add":
      return runCli(config, "ledger-add", [...baseArgs, "--priority", "🟡"]);
    case "cancel":
      return runCli(config, "ledger-cancel", [
        ...baseArgs,
        "--reason", "Cancelado via Janus",
      ]);
    default:
      throw new Error(`Cannot build CLI for type: ${intent.type}`);
  }
}

/**
 * Roda check-alerts localmente (0 tokens).
 *
 * Retorna alertas acionáveis para enriquecer o contexto
 * do sessions_send quando a operação for complexa.
 */
export async function checkAlerts(
  today: string,
  year: number,
  config: VitaCliConfig,
): Promise<{
  today: string;
  has_alerts: boolean;
  counts: Record<string, number>;
  total: number;
  alerts: Array<Record<string, unknown>>;
}> {
  const result = await runCli(config, "check-alerts", [
    "--today", today,
    "--year", String(year),
    "--data-dir", config.dataDir,
  ]);
  return result as any;
}

/**
 * Formata resposta de CRUD para o usuário.
 */
export function formatCrudResponse(
  type: string,
  result: Record<string, unknown>,
): string {
  const desc = result.description ?? result.task_id;
  const id = result.task_id ?? "";

  switch (type) {
    case "complete":
      return `Task "${desc}" marcada como concluída (${id}).`;
    case "add":
      return `Task "${desc}" adicionada (${id}).`;
    case "cancel":
      return `Task "${desc}" cancelada (${id}).`;
    case "start":
      return `Task "${desc}" iniciada (${id}).`;
    default:
      return JSON.stringify(result);
  }
}
