import test from "node:test";
import assert from "node:assert/strict";
import {
  GLOBAL_TOKEN, MAX_REQUEST_BYTES, bearer, bumpQuota, corsHeaders, geminiErrorMessage, isTokenShaped,
  rateLimitOk, readQuota, requestTooLarge, sanitizeContext, todayKey, validateBody
} from "../proxy/src/lib.js";

class FakeKV {
  constructor() { this.m = new Map(); this.ttl = new Map(); }
  async get(k, type) { const v = this.m.get(k); return v === undefined ? null : type === "json" ? JSON.parse(v) : v; }
  async put(k, v, opts) { this.m.set(k, v); if (opts?.expirationTtl) this.ttl.set(k, opts.expirationTtl); }
}

test("bearer parses the Authorization header", () => {
  const req = (h) => ({ headers: new Map([["Authorization", h]]) });
  req.get = undefined;
  assert.equal(bearer({ headers: { get: () => "Bearer cc_abc" } }), "cc_abc");
  assert.equal(bearer({ headers: { get: () => "bearer cc_abc" } }), "cc_abc");
  assert.equal(bearer({ headers: { get: () => "" } }), null);
  assert.equal(bearer({ headers: { get: () => "Basic xyz" } }), null);
});

test("token shape", () => {
  assert.equal(isTokenShaped("cc_AbCdEfGhIjKlMnOpQrStUv"), true);
  assert.equal(isTokenShaped("cc_short"), false);
  assert.equal(isTokenShaped("sk-ant-xxxxxxxxxxxxxxxxxxxx"), false);
  assert.equal(isTokenShaped(null), false);
});

test("quota counts per token per UTC day and expires", async () => {
  const kv = new FakeKV();
  const now = new Date("2026-09-12T15:00:00Z");
  let q = await readQuota(kv, "cc_t", 2, now);
  assert.deepEqual([q.used, q.allowed, q.key], [0, true, "use:cc_t:2026-09-12"]);
  await bumpQuota(kv, q.key, q.used);
  await bumpQuota(kv, q.key, q.used + 1);
  q = await readQuota(kv, "cc_t", 2, now);
  assert.deepEqual([q.used, q.allowed], [2, false]);
  assert.equal(kv.ttl.get(q.key), 172800);
  const tomorrow = await readQuota(kv, "cc_t", 2, new Date("2026-09-13T01:00:00Z"));
  assert.equal(tomorrow.used, 0);
  assert.equal(todayKey(new Date("2026-12-31T23:59:59Z")), "2026-12-31");
});

test("context is sanitized and truncated; nothing else forwarded", () => {
  const c = sanitizeContext({ now: "9/12/2026, 10:00:00", weekday: "Saturday", timezone: "America/Chicago",
    pageTitle: "x".repeat(500), pageUrl: "https://a/", secret: "no" });
  assert.equal(c.pageTitle.length, 200);
  assert.equal(c.secret, undefined);
  assert.equal(sanitizeContext(null).timezone, "UTC");
});

test("body validation", () => {
  assert.equal(validateBody({ image: "a", screen: "b" }), null);
  assert.equal(validateBody({ image: "a" }), "missing screen image");
  assert.equal(validateBody({ screen: "b" }), "missing image");
  assert.equal(validateBody({ image: "a".repeat(6_000_001), screen: "b" }), "image too large");
  assert.equal(validateBody("nope"), "bad json");
});

test("gemini errors map to user-facing messages without leaking the key", () => {
  assert.equal(geminiErrorMessage(503, null).status, 503);
  assert.match(geminiErrorMessage(429, null).error, /rate-limited/);
  assert.match(geminiErrorMessage(400, { error: { message: "API key not valid" } }).error, /misconfigured/);
  assert.match(geminiErrorMessage(500, { error: { message: "boom" } }).error, /Model error 500: boom/);
});

test("CORS headers only for browser-extension origins", () => {
  const chrome = "chrome-extension://abcdefghijklmnopabcdefghijklmnop";
  assert.equal(corsHeaders(chrome)["Access-Control-Allow-Origin"], chrome);
  assert.ok(corsHeaders("moz-extension://0f1e2d3c-1234-5678-9abc-def012345678")["Access-Control-Allow-Origin"]);
  assert.deepEqual(corsHeaders("https://evil.example"), {});
  assert.deepEqual(corsHeaders("chrome-extension://abc/../evil"), {});
  assert.deepEqual(corsHeaders(null), {});
});

test("oversized uploads are rejected from Content-Length before parsing", () => {
  const req = (n) => ({ headers: { get: (h) => (h === "Content-Length" ? String(n) : null) } });
  assert.equal(requestTooLarge(req(MAX_REQUEST_BYTES)), false);
  assert.equal(requestTooLarge(req(MAX_REQUEST_BYTES + 1)), true);
  assert.equal(requestTooLarge({ headers: { get: () => null } }), false);
});

test("service-wide daily counter shares the quota path; a refused KV write is soft", async () => {
  const kv = new FakeKV();
  const now = new Date("2026-09-16T12:00:00Z");
  let g = await readQuota(kv, GLOBAL_TOKEN, 2, now);
  assert.equal(g.key, "use:global:2026-09-16");
  assert.equal(isTokenShaped(GLOBAL_TOKEN), false); // can never collide with a real code
  await bumpQuota(kv, g.key, g.used);
  await bumpQuota(kv, g.key, g.used + 1);
  g = await readQuota(kv, GLOBAL_TOKEN, 2, now);
  assert.deepEqual([g.used, g.allowed], [2, false]);
  const refusing = { get: async () => "1", put: async () => { throw new Error("KV put rate limited"); } };
  await bumpQuota(refusing, "use:global:x", 1); // must not throw
});

test("rate limiter wrapper: no binding allows, honours success, fails open on error", async () => {
  assert.equal(await rateLimitOk(undefined, "k"), true);
  assert.equal(await rateLimitOk({ limit: async () => ({ success: true }) }, "k"), true);
  assert.equal(await rateLimitOk({ limit: async () => ({ success: false }) }, "k"), false);
  assert.equal(await rateLimitOk({ limit: async () => { throw new Error("x"); } }, "k"), true);
  assert.equal(await rateLimitOk({ limit: async () => ({ success: false }) }, ""), true);
});
