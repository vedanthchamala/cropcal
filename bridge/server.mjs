// Local bridge: lets the extension extract events through Claude Code (covered
// by the Claude subscription) instead of a paid API key. Personal/dev use only —
// it spawns `claude -p` per request, so expect 10-30s latency per crop.
import http from "node:http";
import { execFile } from "node:child_process";
import { mkdtemp, writeFile, mkdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { SYSTEM_PROMPT, buildContextText } from "../extension/lib/schema.js";
import { parseEventsText } from "../extension/lib/parse.js";

const PORT = Number(process.env.BRIDGE_PORT || 48765);
const MODEL = process.env.BRIDGE_MODEL || "opus";
const MAX_BODY = 20 * 1024 * 1024;
const CLAUDE_TIMEOUT_MS = 150_000;

// Opt-in dataset collection (BRIDGE_LOG=1): saves each capture — crop, screen,
// context, and the model's output — as one record for Phase 1 training/evals.
const LOG_DIR = process.env.BRIDGE_LOG
  ? fileURLToPath(new URL("../ml/data/captures/", import.meta.url))
  : null;

const server = http.createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") return res.writeHead(204).end();

  try {
    if (req.method === "GET" && req.url === "/health") {
      return json(res, 200, { ok: true, model: MODEL });
    }
    if (req.method === "POST" && req.url === "/extract") {
      const body = JSON.parse(await readBody(req));
      if (!body.image) return json(res, 400, { error: "missing image" });
      const result = await extract(body.image, body.screen, body.context || {}, body.no_log);
      console.log(
        `[extract] ${result.events.length} event(s) in ${result.meta.duration_api_ms}ms`
      );
      return json(res, 200, result);
    }
    json(res, 404, { error: "not found" });
  } catch (err) {
    console.error("[error]", err.message);
    json(res, 500, { error: err.message });
  }
});

function json(res, code, obj) {
  res.writeHead(code, { "Content-Type": "application/json" });
  res.end(JSON.stringify(obj));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY) {
        reject(new Error("request too large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

async function extract(imageBase64, screenBase64, ctx, noLog = false) {
  const dir = await mkdtemp(join(tmpdir(), "cropcal-"));
  const cropPath = join(dir, "crop.png");
  const screenPath = join(dir, "screen.png");
  try {
    await writeFile(cropPath, Buffer.from(imageBase64, "base64"));
    if (screenBase64) {
      await writeFile(screenPath, Buffer.from(screenBase64, "base64"));
    }

    const imageLines = screenBase64
      ? [
          `Read the image at ${cropPath} — the FIRST image (the user's selected region).`,
          `Read the image at ${screenPath} — the SECOND image (the full screen, context only).`
        ]
      : [`Read the image at ${cropPath} — it is the cropped screenshot.`];

    const prompt = [
      SYSTEM_PROMPT,
      "",
      ...imageLines,
      buildContextText(ctx),
      'Reply with ONLY the JSON object {"events": [...]} — no markdown fences, no commentary.'
    ].join("\n");

    const envelope = await runClaude(prompt);
    if (envelope.is_error) throw new Error(envelope.result || "claude -p failed");

    const result = {
      events: parseEventsText(envelope.result),
      meta: {
        provider: "bridge",
        model: MODEL,
        duration_api_ms: envelope.duration_api_ms,
        num_turns: envelope.num_turns,
        // List-price cost from the claude -p envelope. Not billed under a
        // subscription, but it is the honest cost column for the eval harness.
        cost_usd: envelope.total_cost_usd ?? null
      }
    };
    if (LOG_DIR && !noLog) await logCapture(imageBase64, screenBase64, ctx, result);
    return result;
  } finally {
    rm(dir, { recursive: true, force: true }).catch(() => {});
  }
}

async function logCapture(imageBase64, screenBase64, ctx, result) {
  try {
    const id = new Date().toISOString().replace(/[:.]/g, "-");
    const dir = join(LOG_DIR, id);
    await mkdir(dir, { recursive: true });
    await writeFile(join(dir, "crop.png"), Buffer.from(imageBase64, "base64"));
    if (screenBase64) {
      await writeFile(join(dir, "screen.png"), Buffer.from(screenBase64, "base64"));
    }
    await writeFile(
      join(dir, "record.json"),
      JSON.stringify({ id, context: ctx, ...result }, null, 2)
    );
    console.log(`[log] saved capture ${id}`);
  } catch (err) {
    console.error("[log] failed to save capture:", err.message);
  }
}

function runClaude(prompt) {
  const args = [
    "-p", prompt,
    "--allowedTools", "Read",
    "--model", MODEL,
    "--output-format", "json"
  ];
  return new Promise((resolve, reject) => {
    execFile(
      "claude",
      args,
      { timeout: CLAUDE_TIMEOUT_MS, maxBuffer: 10 * 1024 * 1024 },
      (err, stdout, stderr) => {
        if (err) {
          return reject(
            new Error(err.killed ? "claude -p timed out" : stderr.trim() || err.message)
          );
        }
        try {
          resolve(JSON.parse(stdout));
        } catch {
          reject(new Error("claude -p returned an unparseable envelope"));
        }
      }
    );
  });
}

server.listen(PORT, "127.0.0.1", () => {
  console.log(`CropCal bridge on http://127.0.0.1:${PORT} (model: ${MODEL})`);
});
