import { reset } from "cloudflare:test";
import { env, exports } from "cloudflare:workers";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const BASE = "https://proxy.test";
const CODE = "cc_AbCdEfGhIjKlMnOpQrStUv";
const day = () => new Date().toISOString().slice(0, 10);
const globalUsed = () => env.QUOTA.get(env.QUOTA.idFromName("global")).used(day());

let ipSeq = 0;
let ip;
let gemini;

const geminiOk = () =>
  Response.json({
    modelVersion: "gemini-test",
    usageMetadata: { promptTokenCount: 10, candidatesTokenCount: 5, thoughtsTokenCount: 2 },
    candidates: [
      {
        finishReason: "STOP",
        content: { parts: [{ text: '{"events":[{"title":"Demo","start":"2026-09-05T14:00:00"}]}' }] }
      }
    ]
  });

function call(path, { code = CODE, body, origin } = {}) {
  const headers = { "CF-Connecting-IP": ip };
  if (code) headers.Authorization = `Bearer ${code}`;
  if (origin) headers.Origin = origin;
  const init = { headers };
  if (body) {
    init.method = "POST";
    init.body = JSON.stringify(body);
    headers["Content-Type"] = "application/json";
  }
  return exports.default.fetch(new Request(BASE + path, init));
}

const extract = (opts) =>
  call("/extract", { body: { image: "Y3JvcA==", screen: "c2NyZWVu", context: {} }, ...opts });
const used = async (code = CODE) => (await (await call("/me", { code })).json()).used;

beforeEach(async () => {
  await reset();
  ip = `10.0.0.${++ipSeq}`;
  await env.TOKENS.put(`token:${CODE}`, JSON.stringify({ name: "tester", limit: 3 }));
  gemini = vi.fn(async () => geminiOk());
  vi.spyOn(globalThis, "fetch").mockImplementation((...args) => gemini(...args));
});

afterEach(() => vi.restoreAllMocks());

it("health needs no code", async () => {
  const res = await call("/health", { code: null });
  expect(res.status).toBe(200);
  expect(await res.json()).toMatchObject({ ok: true, model: "gemini-3.8-flash" });
});

it("rejects a missing or unknown code before the model is called", async () => {
  expect((await extract({ code: null })).status).toBe(401);
  expect((await extract({ code: "cc_ZZZZZZZZZZZZZZZZZZZZZZ" })).status).toBe(403);
  expect((await extract({ code: "not-a-code" })).status).toBe(403);
  expect(gemini).not.toHaveBeenCalled();
});

it("extract returns events and counts one crop", async () => {
  const res = await extract();
  expect(res.status).toBe(200);
  const out = await res.json();
  expect(out.events[0].title).toBe("Demo");
  expect(out.meta).toMatchObject({ provider: "hosted", used: 1, limit: 3, tokens: { prompt: 10, output: 5, thoughts: 2 } });
  expect(await used()).toBe(1);
  expect(await globalUsed()).toBe(1);

  const [url, init] = gemini.mock.calls[0];
  expect(String(url)).toContain("gemini-3.8-flash:generateContent");
  expect(init.headers["x-goog-api-key"]).toBe("test-key");
  expect(init.signal).toBeInstanceOf(AbortSignal);
});

it("a parallel burst on one code gets exactly `limit` successes", async () => {
  const statuses = (await Promise.all(Array.from({ length: 12 }, () => extract()))).map((r) => r.status);
  expect(statuses.filter((s) => s === 200)).toHaveLength(3);
  expect(statuses.filter((s) => s === 429)).toHaveLength(9);
  expect(gemini).toHaveBeenCalledTimes(3);
  expect(await used()).toBe(3);
});

it("codes have independent counters", async () => {
  const other = "cc_ZyXwVuTsRqPoNmLkJiHgFe";
  await env.TOKENS.put(`token:${other}`, JSON.stringify({ name: "other", limit: 1 }));
  expect((await extract({ code: other })).status).toBe(200);
  expect((await extract({ code: other })).status).toBe(429);
  expect((await extract()).status).toBe(200);
  expect(await used()).toBe(1);
});

it("a limit of 0 blocks the code instead of falling back to the default", async () => {
  await env.TOKENS.put(`token:${CODE}`, JSON.stringify({ name: "tester", limit: 0 }));
  expect((await extract()).status).toBe(429);
  expect(gemini).not.toHaveBeenCalled();
});

it("a disabled code is refused", async () => {
  await env.TOKENS.put(`token:${CODE}`, JSON.stringify({ name: "tester", limit: 3, disabled: true }));
  expect((await extract()).status).toBe(403);
});

it("an upstream error refunds both counters and hides the upstream message", async () => {
  gemini.mockImplementation(async () =>
    Response.json({ error: { message: "internal secret detail" } }, { status: 500 })
  );
  const res = await extract();
  expect(res.status).toBe(502);
  expect((await res.json()).error).not.toContain("secret");
  expect(await used()).toBe(0);
  expect(await globalUsed()).toBe(0);
});

it("a timeout answers 504 and refunds both counters", async () => {
  gemini.mockImplementation(async () => {
    throw new DOMException("The operation timed out", "TimeoutError");
  });
  const res = await extract();
  expect(res.status).toBe(504);
  expect(await used()).toBe(0);
  expect(await globalUsed()).toBe(0);
});

it("a billed but unusable answer refunds the caller, not the service-wide count", async () => {
  gemini.mockImplementation(async () => Response.json({ promptFeedback: { blockReason: "SAFETY" }, candidates: [] }));
  const res = await extract();
  expect(res.status).toBe(502);
  expect((await res.json()).error).toMatch(/declined/);
  expect(await used()).toBe(0);
  expect(await globalUsed()).toBe(1);
});

it("bad bodies are refused without spending a crop", async () => {
  expect((await call("/extract", { body: { image: "a" } })).status).toBe(400);
  expect(await used()).toBe(0);
  expect(gemini).not.toHaveBeenCalled();
});

it("CORS headers go to extension origins only", async () => {
  const ext = "chrome-extension://abcdefghijklmnopabcdefghijklmnop";
  expect((await call("/health", { origin: ext })).headers.get("Access-Control-Allow-Origin")).toBe(ext);
  expect((await call("/health", { origin: "https://evil.example" })).headers.get("Access-Control-Allow-Origin")).toBeNull();
});
