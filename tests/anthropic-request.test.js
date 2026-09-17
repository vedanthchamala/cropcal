import test from "node:test";
import assert from "node:assert/strict";
import { buildRequest, DEFAULT_MODEL } from "../extension/lib/providers/anthropic.js";
import { EVENT_SCHEMA } from "../extension/lib/schema.js";

const images = { crop: "Y3JvcA==", screen: "c2NyZWVu" };
const ctx = {
  now: "9/10/2026, 11:11:44",
  weekday: "Thursday",
  timezone: "America/Chicago",
  pageTitle: "Stories • Instagram",
  pageUrl: "https://www.instagram.com/stories/x/1/"
};

test("default request: opus 5, medium effort, structured output, fallbacks on", () => {
  const { headers, body } = buildRequest(images, ctx, { apiKey: "sk-test" });
  assert.equal(body.model, DEFAULT_MODEL);
  assert.equal(body.output_config.effort, "medium");
  assert.deepEqual(body.output_config.format, { type: "json_schema", schema: EVENT_SCHEMA });
  assert.equal(body.fallbacks, "default");
  assert.equal(headers["anthropic-beta"], "server-side-fallback-2026-07-01");
  assert.equal(headers["x-api-key"], "sk-test");
  assert.equal(headers["anthropic-dangerous-direct-browser-access"], "true");
  assert.equal(body.max_tokens, 16000);
});

test("user message carries crop first, screen second, then context text", () => {
  const { body } = buildRequest(images, ctx, { apiKey: "k" });
  const content = body.messages[0].content;
  assert.equal(content.length, 3);
  assert.equal(content[0].type, "image");
  assert.equal(content[0].source.data, images.crop);
  assert.equal(content[1].source.data, images.screen);
  assert.equal(content[2].type, "text");
  assert.match(content[2].text, /Current date\/time: 9\/10\/2026, 11:11:44 \(Thursday\)/);
  assert.match(content[2].text, /User timezone: America\/Chicago/);
  assert.match(content[2].text, /Captured from page: Stories • Instagram/);
});

test("haiku 4.5: no effort parameter and no fallback header", () => {
  const { headers, body } = buildRequest(images, ctx, {
    apiKey: "k",
    model: "claude-haiku-4-5",
    effort: "high"
  });
  assert.equal(body.output_config.effort, undefined);
  assert.equal(body.fallbacks, undefined);
  assert.equal(headers["anthropic-beta"], undefined);
});

test("sonnet 5: effort kept, fallbacks off", () => {
  const { headers, body } = buildRequest(images, ctx, {
    apiKey: "k",
    model: "claude-sonnet-5",
    effort: "high"
  });
  assert.equal(body.output_config.effort, "high");
  assert.equal(body.fallbacks, undefined);
  assert.equal(headers["anthropic-beta"], undefined);
});
