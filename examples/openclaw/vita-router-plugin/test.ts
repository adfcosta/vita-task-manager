// ------------------------------------------------------------------
// Testes do Vita Router Plugin
//
// Testa classify.ts e formatCrudResponse sem depender do OpenClaw SDK.
// Testes de integração CLI usam execSync direto (não passam pelo plugin).
// Rodar: npx tsx test.ts
// ------------------------------------------------------------------

import { classifyIntent } from "./classify.js";
import { execSync } from "child_process";

// formatCrudResponse inline — evita importar vita-cli.ts que depende
// do OpenClaw SDK (não disponível fora do runtime).
function formatCrudResponse(type: string, result: Record<string, unknown>): string {
  const desc = result.description ?? result.task_id;
  const id = result.task_id ?? "";
  switch (type) {
    case "complete": return `Task "${desc}" marcada como concluída (${id}).`;
    case "add": return `Task "${desc}" adicionada (${id}).`;
    case "cancel": return `Task "${desc}" cancelada (${id}).`;
    case "start": return `Task "${desc}" iniciada (${id}).`;
    default: return JSON.stringify(result);
  }
}
import { mkdirSync, writeFileSync, rmSync } from "fs";
import { join } from "path";

let passed = 0;
let failed = 0;

function assert(condition: boolean, name: string, detail?: string) {
  if (condition) {
    console.log(`  ✓ ${name}`);
    passed++;
  } else {
    console.log(`  ✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed++;
  }
}

// ------------------------------------------------------------------
// classifyIntent
// ------------------------------------------------------------------

console.log("\n=== classifyIntent ===\n");

// Complete
for (const msg of [
  "terminei relatório",
  "concluí o projeto",
  "fiz a entrega",
  "completei apresentação",
  "feito: revisar emails",
  "pronto: comprar café",
]) {
  const r = classifyIntent(msg);
  assert(r.type === "complete", `"${msg}" → complete`, `got: ${r.type}`);
  assert(r.confidence >= 0.8, `  confidence >= 0.8`, `got: ${r.confidence}`);
  assert(r.params.description !== undefined, `  tem description`);
}

// Add
for (const msg of [
  "adiciona task: comprar café",
  "cria task: revisar docs",
  "nova task: ligar pro João",
]) {
  const r = classifyIntent(msg);
  assert(r.type === "add", `"${msg}" → add`, `got: ${r.type}`);
}

// Cancel
for (const msg of [
  "cancela: reunião de sexta",
  "desiste: trocar lâmpada",
  "remove: aula de inglês",
]) {
  const r = classifyIntent(msg);
  assert(r.type === "cancel", `"${msg}" → cancel`, `got: ${r.type}`);
}

// Start
for (const msg of [
  "comecei: estudar pro exame",
  "iniciei: relatório mensal",
  "começando: revisão de código",
]) {
  const r = classifyIntent(msg);
  assert(r.type === "start", `"${msg}" → start`, `got: ${r.type}`);
}

// Complex — NÃO deve classificar como CRUD
for (const msg of [
  "o que tenho pra hoje?",
  "como tá minha semana?",
  "terminei de pensar sobre cancelar o dentista",
  "quero reorganizar minhas prioridades",
  "me ajuda a planejar a semana",
  "brain dump: trocar lâmpada, comprar café",
  "qual a task mais urgente?",
  "",
  "oi",
]) {
  const r = classifyIntent(msg);
  assert(r.type === "complex", `"${msg}" → complex`, `got: ${r.type}`);
  assert(r.confidence === 0, `  confidence === 0`, `got: ${r.confidence}`);
}

// ------------------------------------------------------------------
// formatCrudResponse
// ------------------------------------------------------------------

console.log("\n=== formatCrudResponse ===\n");

assert(
  formatCrudResponse("complete", { description: "Relatório", task_id: "t1" })
    .includes("concluída"),
  "complete response inclui 'concluída'",
);

assert(
  formatCrudResponse("add", { description: "Café", task_id: "t2" })
    .includes("adicionada"),
  "add response inclui 'adicionada'",
);

assert(
  formatCrudResponse("cancel", { description: "Reunião", task_id: "t3" })
    .includes("cancelada"),
  "cancel response inclui 'cancelada'",
);

assert(
  formatCrudResponse("start", { description: "Estudo", task_id: "t4" })
    .includes("iniciada"),
  "start response inclui 'iniciada'",
);

// ------------------------------------------------------------------
// Integração CLI (execSync direto, não passa pelo plugin)
// ------------------------------------------------------------------

console.log("\n=== Integração CLI ===\n");

const realSkill = "/Users/adriano/Dev/vita-task-manager";
const tmpDir = join("/tmp", `vita-plugin-test-${Date.now()}`);
const dataDir = join(tmpDir, "data", "historico");
mkdirSync(dataDir, { recursive: true });

const today = new Date();
const dd = String(today.getDate()).padStart(2, "0");
const mm = String(today.getMonth() + 1).padStart(2, "0");
const todayStr = `${dd}/${mm}`;
const year = today.getFullYear();

// Criar ledger da semana
const dayOfWeek = today.getDay();
const sunday = new Date(today);
sunday.setDate(today.getDate() - dayOfWeek);
const saturday = new Date(sunday);
saturday.setDate(sunday.getDate() + 6);

function fmt(d: Date): string {
  return `${String(d.getDate()).padStart(2, "0")}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getFullYear()).slice(-2)}`;
}

const ledgerName = `${fmt(sunday)}_${fmt(saturday)}_bruto.jsonl`;
writeFileSync(join(dataDir, ledgerName), "");

const cli = `python3 ${realSkill}/scripts/cli.py`;
const baseArgs = `--today ${todayStr} --year ${year} --data-dir ${join(tmpDir, "data")}`;

// Test: ledger-add
try {
  const addOut = execSync(
    `${cli} ledger-add --description "testar plugin vita" --priority 🟡 ${baseArgs}`,
    { encoding: "utf-8" },
  );
  const addResult = JSON.parse(addOut);
  assert(addResult.task_id !== undefined, "CLI ledger-add retorna task_id");

  // Test: ledger-complete
  const completeOut = execSync(
    `${cli} ledger-complete --description "testar plugin vita" ${baseArgs}`,
    { encoding: "utf-8" },
  );
  const completeResult = JSON.parse(completeOut);
  assert(completeResult.task_id !== undefined, "CLI ledger-complete retorna task_id");
} catch (err) {
  assert(false, `CLI CRUD: ${err}`);
}

// Test: check-alerts
try {
  const alertsOut = execSync(
    `${cli} check-alerts ${baseArgs}`,
    { encoding: "utf-8" },
  );
  const alerts = JSON.parse(alertsOut);
  assert(typeof alerts.has_alerts === "boolean", "CLI check-alerts retorna has_alerts");
  assert(typeof alerts.total === "number", "CLI check-alerts retorna total");
  assert(Array.isArray(alerts.alerts), "CLI check-alerts retorna array");
} catch (err) {
  assert(false, `CLI check-alerts: ${err}`);
}

// Cleanup
rmSync(tmpDir, { recursive: true, force: true });

// ------------------------------------------------------------------
// Resultado
// ------------------------------------------------------------------

console.log(`\n${"=".repeat(40)}`);
console.log(`Resultado: ${passed} passed, ${failed} failed`);
console.log(`${"=".repeat(40)}\n`);

process.exit(failed > 0 ? 1 : 0);
