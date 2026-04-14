// ------------------------------------------------------------------
// Wrapper para execução de comandos CLI da Vita
//
// Executa localmente via execSync (0 tokens de LLM).
// Todos os comandos retornam JSON parseado.
// ------------------------------------------------------------------

import { execSync } from "child_process";
import type { VitaIntent } from "./classify.js";

export interface VitaCliConfig {
  vitaSkillPath: string;
  dataDir: string;
}

function cli(config: VitaCliConfig): string {
  return `python3 ${config.vitaSkillPath}/scripts/cli.py`;
}

function dateArgs(today: string, year: number): string {
  return `--today ${today} --year ${year} --data-dir`;
}

/**
 * Constrói e executa comando CLI a partir da intenção classificada.
 */
export function executeCrud(
  intent: VitaIntent,
  today: string,
  year: number,
  config: VitaCliConfig,
): Record<string, unknown> {
  const base = `${cli(config)} ledger-${intent.type}`;
  const args = `--description "${intent.params.description}" ${dateArgs(today, year)} ${config.dataDir}`;

  let cmd: string;
  switch (intent.type) {
    case "complete":
    case "start":
      cmd = `${base} ${args}`;
      break;
    case "add":
      cmd = `${base} ${args} --priority 🟡`;
      break;
    case "cancel":
      cmd = `${base} ${args} --reason "Cancelado via Janus"`;
      break;
    default:
      throw new Error(`Cannot build CLI for type: ${intent.type}`);
  }

  const output = execSync(cmd, { encoding: "utf-8" });
  return JSON.parse(output);
}

/**
 * Roda check-alerts localmente (0 tokens).
 *
 * Retorna alertas acionáveis para enriquecer o contexto
 * do sessions_send quando a operação for complexa.
 */
export function checkAlerts(
  today: string,
  year: number,
  config: VitaCliConfig,
): {
  today: string;
  has_alerts: boolean;
  counts: Record<string, number>;
  total: number;
  alerts: Array<Record<string, unknown>>;
} {
  const cmd = `${cli(config)} check-alerts ${dateArgs(today, year)} ${config.dataDir}`;
  const output = execSync(cmd, { encoding: "utf-8" });
  return JSON.parse(output);
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
