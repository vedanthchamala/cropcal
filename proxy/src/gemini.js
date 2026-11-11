// Gemini request/response for the hosted service. The prompt and event schema
// come from extension/lib/schema.js — the single source every provider and the
// eval harness share.
import { EVENT_SCHEMA, SYSTEM_PROMPT, buildContextText } from "../../extension/lib/schema.js";
import { parseEventsText } from "../../extension/lib/parse.js";

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

// Pure: the eval harness calls this too, so it scores exactly what production sends.
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
// Every message thrown here is written for the end user.
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
