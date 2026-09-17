import test from "node:test";
import assert from "node:assert/strict";
import {
  buildRequest,
  toGeminiSchema,
  parseResponse,
  DEFAULT_MODEL
} from "../extension-gemini/lib/providers/gemini.js";
import { EVENT_SCHEMA } from "../extension-gemini/lib/schema.js";

const images = { crop: "Y3JvcA==", screen: "c2NyZWVu" };
const ctx = {
  now: "9/10/2026, 11:11:44",
  weekday: "Thursday",
  timezone: "America/Chicago",
  pageTitle: "Stories • Instagram",
  pageUrl: "https://www.instagram.com/stories/x/1/"
};

test("schema conversion: nullable flags, uppercase types, ordering, no additionalProperties", () => {
  const g = toGeminiSchema(EVENT_SCHEMA);
  assert.equal(g.type, "OBJECT");
  assert.deepEqual(g.propertyOrdering, ["events"]);
  const item = g.properties.events.items;
  assert.equal(item.type, "OBJECT");
  assert.deepEqual(item.properties.end, { type: "STRING", nullable: true });
  assert.deepEqual(item.properties.all_day, { type: "BOOLEAN" });
  assert.deepEqual(item.properties.confidence, { type: "STRING", enum: ["high", "medium", "low"] });
  assert.deepEqual(item.required, EVENT_SCHEMA.properties.events.items.required);
  assert.deepEqual(item.propertyOrdering, Object.keys(EVENT_SCHEMA.properties.events.items.properties));
  assert.equal(JSON.stringify(g).includes("additionalProperties"), false);
  assert.equal(JSON.stringify(g).includes("anyOf"), false);
});

test("default request: 3.8 flash, JSON mode with schema, no thinking override", () => {
  const { url, headers, body } = buildRequest(images, ctx, { apiKey: "AIza-test" });
  assert.equal(url, `https://generativelanguage.googleapis.com/v1beta/models/${DEFAULT_MODEL}:generateContent`);
  assert.equal(headers["x-goog-api-key"], "AIza-test");
  assert.equal(body.generationConfig.responseMimeType, "application/json");
  assert.equal(body.generationConfig.responseSchema.type, "OBJECT");
  assert.equal(body.generationConfig.thinkingConfig, undefined);
  assert.match(body.systemInstruction.parts[0].text, /extract calendar events/i);
  const parts = body.contents[0].parts;
  assert.equal(parts.length, 3);
  assert.deepEqual(parts[0], { inlineData: { mimeType: "image/png", data: images.crop } });
  assert.deepEqual(parts[1], { inlineData: { mimeType: "image/png", data: images.screen } });
  assert.match(parts[2].text, /Current date\/time: 9\/10\/2026, 11:11:44 \(Thursday\)/);
});

test("thinking: budget on 2.5, level on 3.x, ignored when mismatched", () => {
  assert.deepEqual(
    buildRequest(images, ctx, { apiKey: "k", model: "gemini-2.5-flash", thinking: "0" }).body
      .generationConfig.thinkingConfig,
    { thinkingBudget: 0 }
  );
  assert.deepEqual(
    buildRequest(images, ctx, { apiKey: "k", model: "gemini-3.8-flash", thinking: "low" }).body
      .generationConfig.thinkingConfig,
    { thinkingLevel: "low" }
  );
  assert.equal(
    buildRequest(images, ctx, { apiKey: "k", model: "gemini-3.8-flash", thinking: "1024" }).body
      .generationConfig.thinkingConfig,
    undefined
  );
});

test("parseResponse: extracts events, skips thought parts, surfaces blocks and truncation", () => {
  const ok = parseResponse({
    modelVersion: "gemini-2.5-flash",
    usageMetadata: { promptTokenCount: 10, candidatesTokenCount: 5, thoughtsTokenCount: 3 },
    candidates: [
      {
        finishReason: "STOP",
        content: {
          parts: [
            { text: "hidden", thought: true },
            { text: '{"events": [{"title": "Demo", "start": "2026-09-05T14:00:00"}]}' }
          ]
        }
      }
    ]
  });
  assert.equal(ok.events.length, 1);
  assert.equal(ok.events[0].title, "Demo");
  assert.equal(ok.usage.thoughtsTokenCount, 3);

  assert.throws(
    () => parseResponse({ promptFeedback: { blockReason: "SAFETY" }, candidates: [] }),
    /declined/
  );
  assert.throws(
    () => parseResponse({ candidates: [{ finishReason: "MAX_TOKENS", content: { parts: [{ text: "{" }] } }] }),
    /truncated/
  );
  assert.throws(() => parseResponse({ candidates: [] }), /no candidates/);
});
