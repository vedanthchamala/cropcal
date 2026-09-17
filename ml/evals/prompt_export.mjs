// Exports the main extension's prompt contract for Python providers that call
// a model directly (e.g. a local Ollama model), so they send the same system
// prompt, schema, and context text the extension sends.
// stdin: {"ctx": {...}}  stdout: {"system_prompt", "schema", "context_text"}
import { EVENT_SCHEMA, SYSTEM_PROMPT, buildContextText } from "../../extension/lib/schema.js";

let input = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) input += chunk;
const { ctx } = JSON.parse(input);
process.stdout.write(
  JSON.stringify({ system_prompt: SYSTEM_PROMPT, schema: EVENT_SCHEMA, context_text: buildContextText(ctx) })
);
