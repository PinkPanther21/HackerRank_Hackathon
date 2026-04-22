// Shared local evaluator for the JS and TS starters.
// Usage: node tests/run_tests.js --lang js
//        node tests/run_tests.js --lang ts

import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

function parseArgs(argv) {
  const out = { lang: "js" };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--lang") out.lang = argv[++i];
  }
  return out;
}

function scoreResolution(res, ticket) {
  if (!res || typeof res.answer !== "string") return 0;
  const hay = res.answer.toLowerCase();
  const signals = ticket.expected_signals || [];
  if (signals.length === 0) return res.answer.length > 0 ? 1 : 0;
  const hits = signals.filter((s) => hay.includes(s.toLowerCase())).length;
  return hits / signals.length;
}

async function main() {
  const { lang } = parseArgs(process.argv.slice(2));
  const agentPath =
    lang === "ts"
      ? resolve(__dirname, "../starter/ts/agent.ts")
      : resolve(__dirname, "../starter/js/agent.js");

  const ticketsRaw = await readFile(
    resolve(__dirname, "tickets.json"),
    "utf8",
  );
  const tickets = JSON.parse(ticketsRaw);

  const mod = await import(pathToFileURL(agentPath).href);
  const solve = mod.solveTicket;
  if (typeof solve !== "function") {
    console.error(`solveTicket not exported from ${agentPath}`);
    process.exit(2);
  }

  let total = 0;
  for (const t of tickets) {
    const started = Date.now();
    let res;
    try {
      res = await solve(t);
    } catch (err) {
      console.error(`[${t.id}] threw:`, err.message);
      continue;
    }
    const ms = Date.now() - started;
    const score = scoreResolution(res, t);
    total += score;
    console.log(
      `[${t.id}] score=${score.toFixed(2)} time=${ms}ms conf=${res?.confidence ?? "?"}`,
    );
  }
  console.log(
    `\nTotal: ${total.toFixed(2)} / ${tickets.length} (${((total / tickets.length) * 100).toFixed(1)}%)`,
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
