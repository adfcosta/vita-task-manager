// ------------------------------------------------------------------
// Janus → Vita routing com sessions_send (Fase 1 + Fase 2)
//
// Snippet para o plugin/routing do Janus. Usa a sessão nomeada
// "vita-daily" criada pelo cron matinal e comunica via
// sessions_send (sem bootstrap repetido).
//
// A sessão "vita-daily" persiste entre runs do cron e reseta
// automaticamente às 04:00 (default do OpenClaw).
//
// Referência: patches/vita-SESSION-DESIGN.md (Camadas 1 e 4)
// ------------------------------------------------------------------

import { execSync } from "child_process";

// Paths da skill Vita — ajustar conforme ambiente
const VITA_SKILL_PATH = "/path/to/vita-task-manager";
const CLI = `python3 ${VITA_SKILL_PATH}/scripts/cli.py`;

// Session key fixa — criada pelo cron-daily.sh às 06:00
const VITA_SESSION_KEY = "session:vita-daily";

// ------------------------------------------------------------------
// Fase 1: Routing com sessão nomeada
// ------------------------------------------------------------------

/**
 * Roteia task para a Vita via sessão nomeada.
 *
 * Fluxo:
 * 1. Tenta sessions_send pra "session:vita-daily" (barato)
 * 2. Se falhar (sessão resetou/morreu), faz spawn efêmero
 *
 * O cron matinal (cron-daily.sh) cria a sessão às 06:00.
 * Reset automático às 04:00 garante ciclo diário limpo.
 */
async function routeToVita(
  task: string,
  // Estas funções vêm do SDK do OpenClaw — assinaturas ilustrativas
  sessions_send: (key: string, msg: string, opts?: { timeoutSeconds: number }) => Promise<{ ok: boolean; reply?: string }>,
  sessions_spawn: (agentId: string, task: string, opts?: Record<string, unknown>) => Promise<{ childSessionKey: string }>,
): Promise<{ ok: boolean; reply?: string }> {

  // Tenta sessão nomeada primeiro (barato: ~1-3k tokens, sem bootstrap)
  const result = await sessions_send(VITA_SESSION_KEY, task, {
    timeoutSeconds: 30,
  });

  if (result.ok) return result;

  // Fallback: spawn efêmero (caro: ~13k tokens com bootstrap)
  // Só acontece se a sessão nomeada ainda não foi criada (cron
  // não rodou, ou entre 04:00-06:00 quando não há sessão ativa)
  const spawn = await sessions_spawn("vita", task, {
    model: "haiku",
  });

  const spawnResult = await sessions_send(spawn.childSessionKey, task, {
    timeoutSeconds: 60,
  });
  return spawnResult;
}


// ------------------------------------------------------------------
// Fase 2: Plugin SDK — classificação de intenção + CRUD local
// ------------------------------------------------------------------

interface VitaIntent {
  type: "complete" | "add" | "cancel" | "start" | "progress" | "complex";
  params: Record<string, string>;
  confidence: number;
}

/**
 * Classifica a intenção do usuário SEM usar LLM.
 *
 * Usa keyword matching simples. Em caso de dúvida, retorna
 * type: "complex" para delegar à Vita via sessions_send.
 *
 * IMPORTANTE: Não tenta ser esperto demais. "terminei de pensar
 * sobre cancelar o dentista" NÃO deve virar "complete" nem "cancel".
 * Se a frase tem mais de um verbo de ação, é "complex".
 */
function classifyIntent(message: string): VitaIntent {
  const lower = message.toLowerCase().trim();

  // Padrões de alta confiança — frases curtas e diretas
  const patterns: Array<{ regex: RegExp; type: VitaIntent["type"]; extract: (m: RegExpMatchArray) => Record<string, string> }> = [
    {
      regex: /^(?:terminei|concluí|fiz|completei|feito|pronto)[:\s]+(.+)$/i,
      type: "complete",
      extract: (m) => ({ description: m[1].trim() }),
    },
    {
      regex: /^(?:adiciona|cria|nova)\s+task[:\s]+(.+)$/i,
      type: "add",
      extract: (m) => ({ description: m[1].trim() }),
    },
    {
      regex: /^(?:cancela|desiste|remove)[:\s]+(.+)$/i,
      type: "cancel",
      extract: (m) => ({ description: m[1].trim() }),
    },
    {
      regex: /^(?:comecei|iniciei|começando|starting)[:\s]+(.+)$/i,
      type: "start",
      extract: (m) => ({ description: m[1].trim() }),
    },
  ];

  for (const { regex, type, extract } of patterns) {
    const match = lower.match(regex);
    if (match) {
      return { type, params: extract(match), confidence: 0.9 };
    }
  }

  // Tudo que não é padrão claro → delega pra Vita
  return { type: "complex", params: {}, confidence: 0 };
}

/**
 * Constrói comando CLI a partir da intenção classificada.
 */
function buildCliCommand(intent: VitaIntent, today: string, year: number): string {
  const base = `${CLI} --today ${today} --year ${year} --data-dir ${VITA_SKILL_PATH}/data`;

  switch (intent.type) {
    case "complete":
      return `${CLI} ledger-complete --description "${intent.params.description}" ${base.replace(CLI, "")}`;
    case "add":
      return `${CLI} ledger-add --description "${intent.params.description}" --priority 🟡 ${base.replace(CLI, "")}`;
    case "cancel":
      return `${CLI} ledger-cancel --description "${intent.params.description}" --reason "Cancelado via Janus" ${base.replace(CLI, "")}`;
    case "start":
      return `${CLI} ledger-start --description "${intent.params.description}" ${base.replace(CLI, "")}`;
    default:
      throw new Error(`Cannot build CLI for type: ${intent.type}`);
  }
}

/**
 * Roda check-alerts localmente (0 tokens).
 *
 * Projetado para ser chamado pelo plugin antes de rotear para
 * a Vita, enriquecendo o contexto do sessions_send com alertas.
 */
function checkAlerts(today: string, year: number): {
  has_alerts: boolean;
  counts: Record<string, number>;
  alerts: Array<Record<string, unknown>>;
} {
  const cmd = `${CLI} check-alerts --today ${today} --year ${year} --data-dir ${VITA_SKILL_PATH}/data`;
  const output = execSync(cmd, { encoding: "utf-8" });
  return JSON.parse(output);
}

/**
 * Routing completo com Plugin SDK (Fase 2).
 *
 * Fluxo:
 * 1. Classifica intenção (sem LLM)
 * 2. Se CRUD simples → executa CLI direto (0 tokens)
 * 3. Se warning de duplicata → escala pra Vita (Duplicate Guardrail)
 * 4. Se complexo → sessions_send pra Vita
 * 5. Opcionalmente enriquece com alertas de check-alerts
 */
async function routeToVitaWithPlugin(
  message: string,
  today: string,
  year: number,
  sessions_send: (key: string, msg: string, opts?: { timeoutSeconds: number }) => Promise<{ ok: boolean; reply?: string }>,
  sessions_spawn: (agentId: string, task: string, opts?: Record<string, unknown>) => Promise<{ childSessionKey: string }>,
): Promise<{ ok: boolean; reply?: string; source: "plugin" | "vita" }> {

  const intent = classifyIntent(message);

  // CRUD simples — execução local, 0 tokens
  if (intent.type !== "complex" && intent.confidence >= 0.8) {
    try {
      const cmd = buildCliCommand(intent, today, year);
      const output = execSync(cmd, { encoding: "utf-8" });
      const result = JSON.parse(output);

      // Duplicate Guardrail: warning → escala pra Vita
      if (result.warning?.type === "duplicate_suspect") {
        const vitaTask = `O usuário pediu: "${message}". O ledger-add retornou warning de duplicata: ${JSON.stringify(result.warning)}. Apresente as opções ao usuário conforme o Duplicate Guardrail.`;
        const vitaResult = await routeToVita(vitaTask, sessions_send, sessions_spawn);
        return { ...vitaResult, source: "vita" };
      }

      return {
        ok: true,
        reply: formatCrudResponse(intent.type, result),
        source: "plugin",
      };
    } catch (error) {
      // CLI falhou → delega pra Vita como fallback
      const vitaResult = await routeToVita(message, sessions_send, sessions_spawn);
      return { ...vitaResult, source: "vita" };
    }
  }

  // Complexo — sessions_send pra Vita
  // Opcionalmente enriquece com alertas
  let enrichedMessage = message;
  try {
    const alerts = checkAlerts(today, year);
    if (alerts.has_alerts) {
      enrichedMessage += `\n\n[ALERTAS VITA: ${JSON.stringify(alerts.counts)}]`;
    }
  } catch {
    // check-alerts falhou — não bloqueia o fluxo
  }

  const vitaResult = await routeToVita(enrichedMessage, sessions_send, sessions_spawn);
  return { ...vitaResult, source: "vita" };
}

/**
 * Formata resposta de CRUD para o usuário.
 */
function formatCrudResponse(type: string, result: Record<string, unknown>): string {
  switch (type) {
    case "complete":
      return `Task "${result.description}" marcada como concluída (${result.task_id}).`;
    case "add":
      return `Task "${result.description}" adicionada (${result.task_id}).`;
    case "cancel":
      return `Task "${result.description}" cancelada (${result.task_id}).`;
    case "start":
      return `Task "${result.description}" iniciada (${result.task_id}).`;
    default:
      return JSON.stringify(result);
  }
}

// ------------------------------------------------------------------
// Exports
// ------------------------------------------------------------------

export {
  routeToVita,
  routeToVitaWithPlugin,
  classifyIntent,
  buildCliCommand,
  checkAlerts,
};
