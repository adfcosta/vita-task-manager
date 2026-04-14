// ------------------------------------------------------------------
// Testes do Vita Router Plugin
//
// Testa classify.ts e vita-cli.ts sem depender do OpenClaw SDK.
// Rodar: npx tsx test.ts
// ------------------------------------------------------------------

import { classifyIntent } from "./classify.js";
import { executeCrud, checkAlerts, formatCrudResponse } from "./vita-cli.js";
import { execSync } from "child_process";
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
// executeCrud + checkAlerts (integração com CLI real)
// ------------------------------------------------------------------

console.log("\n=== Integração CLI ===\n");

// Setup: criar ledger temporário
const tmpDir = join("/tmp", `vita-plugin-test-${Date.now()}`);
const dataDir = join(tmpDir, "data", "historico");
mkdirSync(dataDir, { recursive: true });

const vitaSkillPath = join(tmpDir, "skill");
mkdirSync(vitaSkillPath, { recursive: true });

// Symlink scripts pro tmpDir
const realSkill = "/Users/adriano/Dev/vita-task-manager";
const cliConfig = { vitaSkillPath: realSkill, dataDir: join(tmpDir, "data") };

// Criar ledger da semana
const today = new Date();
const dd = String(today.getDate()).padStart(2, "0");
const mm = String(today.getMonth() + 1).padStart(2, "0");
const yy = String(today.getFullYear()).slice(-2);
const todayStr = `${dd}/${mm}`;
const year = today.getFullYear();

// Determinar domingo da semana (para nome do ledger)
const dayOfWeek = today.getDay(); // 0=dom
const sunday = new Date(today);
sunday.setDate(today.getDate() - dayOfWeek);
const saturdayDate = new Date(sunday);
saturdayDate.setDate(sunday.getDate() + 6);

function fmt(d: Date): string {
  return `${String(d.getDate()).padStart(2, "0")}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getFullYear()).slice(-2)}`;
}

const ledgerName = `${fmt(sunday)}_${fmt(saturdayDate)}_bruto.jsonl`;
const ledgerPath = join(dataDir, ledgerName);
writeFileSync(ledgerPath, "");

// Test: executeCrud add
try {
  const addIntent = classifyIntent("adiciona task: testar plugin vita");
  const addResult = executeCrud(addIntent, todayStr, year, cliConfig);
  assert(addResult.task_id !== undefined, "executeCrud add retorna task_id", `got: ${JSON.stringify(addResult)}`);
  assert(addResult.ok === true || addResult.description !== undefined, "executeCrud add succeeded");

  // Test: executeCrud complete
  const completeIntent = classifyIntent("completei testar plugin vita");
  const completeResult = executeCrud(completeIntent, todayStr, year, cliConfig);
  assert(
    completeResult.task_id !== undefined,
    "executeCrud complete retorna task_id",
    `got: ${JSON.stringify(completeResult)}`,
  );
} catch (err) {
  assert(false, `executeCrud: ${err}`);
}

// Test: checkAlerts
try {
  const alerts = checkAlerts(todayStr, year, cliConfig);
  assert(typeof alerts.has_alerts === "boolean", "checkAlerts retorna has_alerts");
  assert(typeof alerts.total === "number", "checkAlerts retorna total");
  assert(Array.isArray(alerts.alerts), "checkAlerts retorna array de alerts");
} catch (err) {
  assert(false, `checkAlerts: ${err}`);
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
