import { EVENT_SCHEMA, SYSTEM_PROMPT, buildContextText } from "../schema.js";

const API_URL = "https://api.anthropic.com/v1/messages";
export const DEFAULT_MODEL = "claude-opus-5";
export const DEFAULT_EFFORT = "medium";

// Server-side refusal fallbacks are supported (and recommended by default) on
// the Opus 5 / Fable 5 tier only.
const supportsFallbacks = (model) =>
  model.startsWith("claude-opus-5") || model.startsWith("claude-fable-5");

// output_config.effort is rejected (400) by Haiku 4.5.
const supportsEffort = (model) => !model.startsWith("claude-haiku-4-5");

const imageBlock = (data) => ({
  type: "image",
  source: { type: "base64", media_type: "image/png", data }
});

// Pure: builds the request so the shape can be unit-tested without fetch.
export function buildRequest(images, ctx, settings) {
  const model = settings.model || DEFAULT_MODEL;

  const headers = {
    "Content-Type": "application/json",
    "x-api-key": settings.apiKey,
    "anthropic-version": "2023-06-01",
    "anthropic-dangerous-direct-browser-access": "true"
  };

  const outputConfig = { format: { type: "json_schema", schema: EVENT_SCHEMA } };
  if (supportsEffort(model)) outputConfig.effort = settings.effort || DEFAULT_EFFORT;

  const body = {
    model,
    max_tokens: 16000,
    system: SYSTEM_PROMPT,
    output_config: outputConfig,
    messages: [
      {
        role: "user",
        content: [
          imageBlock(images.crop),
          imageBlock(images.screen),
          { type: "text", text: buildContextText(ctx) }
        ]
      }
    ]
  };

  if (supportsFallbacks(model)) {
    headers["anthropic-beta"] = "server-side-fallback-2026-07-01";
    body.fallbacks = "default";
  }

  return { headers, body };
}

export async function extractEvents(images, ctx, settings) {
  const { headers, body } = buildRequest(images, ctx, settings);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90_000);
  let res;
  try {
    res = await fetch(API_URL, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: controller.signal
    });
  } catch (err) {
    throw new Error(
      err.name === "AbortError" ? "Request timed out after 90s" : `Network error: ${err.message}`
    );
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    const message = detail?.error?.message || res.statusText;
    if (res.status === 401) throw new Error("Invalid API key — set it in CropCal options");
    if (res.status === 429) throw new Error("Rate limited by the API — try again shortly");
    throw new Error(`API error ${res.status}: ${message}`);
  }

  const data = await res.json();
  if (data.stop_reason === "refusal") {
    throw new Error("The model declined to process this image");
  }
  if (data.stop_reason === "max_tokens") {
    throw new Error("Model output was truncated — try a smaller region");
  }

  const text = data.content
    .filter((block) => block.type === "text")
    .map((block) => block.text)
    .join("");

  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error("Model returned unparseable output");
  }
  if (!Array.isArray(parsed.events)) {
    throw new Error("Model output missing events array");
  }
  return { events: parsed.events, usage: data.usage, model: data.model };
}

// Cheap text-only round trip used by the options page "Test connection" button.
export async function testConnection(settings) {
  const res = await fetch(API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": settings.apiKey,
      "anthropic-version": "2023-06-01",
      "anthropic-dangerous-direct-browser-access": "true"
    },
    body: JSON.stringify({
      model: settings.model || DEFAULT_MODEL,
      max_tokens: 256,
      messages: [{ role: "user", content: "Reply with the single word: ok" }]
    })
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.error?.message || `HTTP ${res.status}`);
  }
  return true;
}
