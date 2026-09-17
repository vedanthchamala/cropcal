import { EVENT_SCHEMA, SYSTEM_PROMPT, buildContextText } from "../schema.js";
import { parseEventsText } from "../parse.js";

const API_BASE = "https://generativelanguage.googleapis.com/v1beta/models";
export const DEFAULT_MODEL = "gemini-3.8-flash";
// "" = leave thinking at the model default. Numeric budgets apply to the 2.5
// series only (0 disables thinking); 3.x models take a thinkingLevel instead.
export const DEFAULT_THINKING = "";

// Gemini's responseSchema is an OpenAPI 3.0 subset: nullability is a flag
// rather than anyOf-with-null, additionalProperties is not accepted, and key
// order must be stated explicitly or the model may reorder fields.
export function toGeminiSchema(schema) {
  if (schema.anyOf) {
    const nonNull = schema.anyOf.find((s) => s.type !== "null");
    return { ...toGeminiSchema(nonNull), nullable: true };
  }
  const out = { type: schema.type.toUpperCase() };
  if (schema.enum) out.enum = schema.enum;
  if (schema.items) out.items = toGeminiSchema(schema.items);
  if (schema.properties) {
    out.properties = Object.fromEntries(
      Object.entries(schema.properties).map(([k, v]) => [k, toGeminiSchema(v)])
    );
    out.propertyOrdering = Object.keys(schema.properties);
    if (schema.required) out.required = schema.required;
  }
  return out;
}

const imagePart = (data) => ({ inlineData: { mimeType: "image/png", data } });

function thinkingConfig(model, thinking) {
  if (thinking === "" || thinking === null || thinking === undefined) return null;
  if (model.startsWith("gemini-2.5")) return { thinkingBudget: Number(thinking) };
  if (typeof thinking === "string" && /^[a-z]+$/.test(thinking)) return { thinkingLevel: thinking };
  return null;
}

// Pure: builds the request so the eval harness can send exactly what the
// extension sends.
export function buildRequest(images, ctx, settings) {
  const model = settings.model || DEFAULT_MODEL;
  const generationConfig = {
    responseMimeType: "application/json",
    responseSchema: toGeminiSchema(EVENT_SCHEMA),
    maxOutputTokens: 16384
  };
  const tc = thinkingConfig(model, settings.thinking ?? DEFAULT_THINKING);
  if (tc) generationConfig.thinkingConfig = tc;

  return {
    url: `${API_BASE}/${model}:generateContent`,
    headers: {
      "Content-Type": "application/json",
      "x-goog-api-key": settings.apiKey
    },
    body: {
      systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
      contents: [
        {
          role: "user",
          parts: [
            imagePart(images.crop),
            imagePart(images.screen),
            { text: buildContextText(ctx) }
          ]
        }
      ],
      generationConfig
    }
  };
}

// Turns a generateContent response into events; throws on blocks/truncation.
export function parseResponse(data) {
  const blocked = data.promptFeedback?.blockReason;
  if (blocked) throw new Error(`Gemini declined to process this image (${blocked})`);
  const cand = data.candidates?.[0];
  if (!cand) throw new Error("Gemini returned no candidates");
  if (cand.finishReason === "MAX_TOKENS") {
    throw new Error("Model output was truncated — try a smaller region");
  }
  const text = (cand.content?.parts || [])
    .filter((p) => typeof p.text === "string" && !p.thought)
    .map((p) => p.text)
    .join("");
  if (!text) {
    throw new Error(`Gemini returned no text (finishReason: ${cand.finishReason || "unknown"})`);
  }
  return {
    events: parseEventsText(text),
    usage: data.usageMetadata,
    model: data.modelVersion,
    finishReason: cand.finishReason
  };
}

export async function extractEvents(images, ctx, settings) {
  const { url, headers, body } = buildRequest(images, ctx, settings);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90_000);
  let res;
  try {
    res = await fetch(url, {
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
    if (res.status === 400 && /API key/i.test(message)) {
      throw new Error("Invalid Gemini API key — set it in CropCal options");
    }
    if (res.status === 429) {
      throw new Error("Rate limited by Gemini — the free tier allows only a few requests per minute; try again shortly");
    }
    throw new Error(`Gemini API error ${res.status}: ${message}`);
  }

  return parseResponse(await res.json());
}

// Validates the key (and that the model exists) without generating anything.
export async function testConnection(settings) {
  const model = settings.model || DEFAULT_MODEL;
  const res = await fetch(`${API_BASE}/${model}`, {
    headers: { "x-goog-api-key": settings.apiKey }
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.error?.message || `HTTP ${res.status}`);
  }
  return true;
}
