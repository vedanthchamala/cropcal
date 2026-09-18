import test from "node:test";
import assert from "node:assert/strict";
import {
  BURST_WINDOW_MS, GLOBAL_NAME, MAX_REQUEST_BYTES, bearer, corsHeaders, geminiErrorMessage, isTokenShaped,
  rateLimitOk, releaseIn, requestTooLarge, reserveIn, sanitizeContext, todayKey, usedIn, validateBody
} from "../proxy/src/lib.js";

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

test("daily cap: exactly `limit` reservations succeed, then it resets on a new UTC day", () => {
  let state = null;
  const results = [];
  for (let i = 0; i < 8; i++) {
    const r = reserveIn(state, { day: "2026-09-17", limit: 3, now: 1_000 + i });
    state = r.state;
    results.push(r.ok ? r.used : r.reason);
  }
  assert.deepEqual(results, [1, 2, 3, "daily", "daily", "daily", "daily", "daily"]);
  assert.equal(usedIn(state, "2026-09-17"), 3);
  assert.equal(usedIn(state, "2026-09-18"), 0);
  const next = reserveIn(state, { day: "2026-09-18", limit: 3, now: 9_000 });
  assert.deepEqual([next.ok, next.used], [true, 1]);
  assert.equal(todayKey(new Date("2026-12-31T23:59:59Z")), "2026-12-31");
});

test("burst cap: N per window, frees up as the window slides, survives the day change", () => {
  let state = null;
  const at = (now, day = "2026-09-17") => {
    const r = reserveIn(state, { day, limit: 100, burst: 2, now });
    state = r.state;
    return r.ok ? "ok" : r.reason;
  };
  assert.deepEqual([at(0), at(10), at(20)], ["ok", "ok", "burst"]);
  assert.equal(usedIn(state, "2026-09-17"), 2); // a refused request is not counted
  assert.equal(at(BURST_WINDOW_MS - 1), "burst");
  assert.equal(at(BURST_WINDOW_MS + 5), "ok"); // the t=0 entry aged out
  // the window still holds t=10 and t=60005; a new UTC day does not clear it
  assert.equal(at(BURST_WINDOW_MS + 6, "2026-09-18"), "burst");
});

test("release refunds the daily count but not the burst slot, and never goes negative", () => {
  let state = reserveIn(null, { day: "d", limit: 1, burst: 5, now: 1 }).state;
  assert.equal(reserveIn(state, { day: "d", limit: 1, burst: 5, now: 2 }).reason, "daily");
  state = releaseIn(state, "d");
  assert.equal(usedIn(state, "d"), 0);
  assert.equal(state.recent.length, 1);
  assert.equal(reserveIn(state, { day: "d", limit: 1, burst: 5, now: 3 }).ok, true);
  assert.equal(usedIn(releaseIn(releaseIn(state, "d"), "d"), "d"), 0);
  assert.equal(releaseIn(null, "d"), null);
  assert.equal(usedIn(releaseIn(state, "other-day"), "d"), 0);
});

test("service-wide counter: no burst bookkeeping, name cannot collide with a code", () => {
  let state = null;
  for (let i = 0; i < 50; i++) state = reserveIn(state, { day: "d", limit: 1000, burst: 0, now: i }).state;
  assert.equal(state.used, 50);
  assert.deepEqual(state.recent, []);
  assert.equal(isTokenShaped(GLOBAL_NAME), false);
});

test("rate limiter wrapper: no binding allows, honours success, fails open on error", async () => {
  assert.equal(await rateLimitOk(undefined, "k"), true);
  assert.equal(await rateLimitOk({ limit: async () => ({ success: true }) }, "k"), true);
  assert.equal(await rateLimitOk({ limit: async () => ({ success: false }) }, "k"), false);
  assert.equal(await rateLimitOk({ limit: async () => { throw new Error("x"); } }, "k"), true);
  assert.equal(await rateLimitOk({ limit: async () => ({ success: false }) }, ""), true);
});
