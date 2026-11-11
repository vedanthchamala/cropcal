import { createExecutionContext, reset, waitOnExecutionContext } from "cloudflare:test";
import { env } from "cloudflare:workers";
import { afterEach, beforeAll, beforeEach, expect, it, vi } from "vitest";
import worker from "../src/index.js";
import { withDb } from "../src/db.js";
import { GOOGLE_JWKS_URL, resetGoogleKeyCache } from "../src/google.js";
import { signSession } from "../src/session.js";
import { makeIssuer } from "../../tests/helpers/google-token.js";

const BASE = "https://proxy.test";
const CLIENT = "test-client.apps.googleusercontent.com";
const sql = (text, params) => withDb(env, (db) => db.query(text, params)).then((r) => r.rows);

let issuer;
let ipSeq = 100;
let ip;
let gemini;

const geminiOk = () =>
  Response.json({
    usageMetadata: { promptTokenCount: 10, candidatesTokenCount: 5, thoughtsTokenCount: 2 },
    candidates: [{ finishReason: "STOP", content: { parts: [{ text: '{"events":[{"title":"Demo","start":"2026-09-05T14:00:00"}]}' }] } }]
  });

async function call(path, { token, body } = {}) {
  const headers = { "CF-Connecting-IP": ip };
  if (token) headers.Authorization = `Bearer ${token}`;
  const init = { headers };
  if (body) {
    init.method = "POST";
    init.body = JSON.stringify(body);
    headers["Content-Type"] = "application/json";
  }
  const ctx = createExecutionContext();
  const res = await worker.fetch(new Request(BASE + path, init), env, ctx);
  await waitOnExecutionContext(ctx);
  return res;
}

const claims = (over = {}) => ({
  iss: "https://accounts.google.com", aud: CLIENT, sub: "g-1", email: "one@example.com",
  email_verified: true, exp: Math.floor(Date.now() / 1000) + 3600, ...over
});

async function signInAs(over) {
  const res = await call("/auth/google", { body: { id_token: await issuer.idToken(claims(over)) } });
  return { res, body: await res.json() };
}

const extract = (token) => call("/extract", { token, body: { image: "Y3JvcA==", screen: "c2NyZWVu", context: {} } });

beforeAll(async () => {
  issuer = await makeIssuer();
});

beforeEach(async () => {
  await reset();
  await sql("truncate usage_events, users restart identity cascade");
  resetGoogleKeyCache();
  ip = `10.0.1.${++ipSeq}`;
  gemini = vi.fn(async () => geminiOk());
  vi.spyOn(globalThis, "fetch").mockImplementation((url, init) =>
    String(url) === GOOGLE_JWKS_URL ? Promise.resolve(Response.json(issuer.jwks)) : gemini(url, init)
  );
});

afterEach(() => vi.restoreAllMocks());

it("Google sign-in creates the user once and returns a working session", async () => {
  const first = await signInAs();
  expect(first.res.status).toBe(200);
  expect(first.body).toMatchObject({ ok: true, email: "one@example.com", limit: 3 });

  const again = await signInAs({ email: "renamed@example.com" });
  expect(again.body.email).toBe("renamed@example.com");
  const users = await sql("select email, google_sub from users");
  expect(users).toEqual([{ email: "renamed@example.com", google_sub: "g-1" }]);

  const me = await (await call("/me", { token: again.body.token })).json();
  expect(me).toMatchObject({ ok: true, name: "renamed@example.com", used: 0, limit: 3 });
});

it("a token for another app, an unverified email or garbage does not sign in", async () => {
  expect((await signInAs({ aud: "other.apps.googleusercontent.com" })).res.status).toBe(401);
  expect((await signInAs({ email_verified: false })).res.status).toBe(401);
  expect((await call("/auth/google", { body: { id_token: "nope" } })).status).toBe(401);
  expect((await call("/auth/google", { body: {} })).status).toBe(401);
  expect(await sql("select count(*)::int as n from users")).toEqual([{ n: 0 }]);
});

it("requests without a valid session are refused before the model is called", async () => {
  expect((await extract(null)).status).toBe(401);
  expect((await extract("not-a-session")).status).toBe(401);
  const forged = await signSession({ uid: "00000000-0000-0000-0000-000000000001", email: "x@example.com" }, "wrong-secret");
  expect((await extract(forged)).status).toBe(401);
  const ghost = await signSession({ uid: "00000000-0000-0000-0000-000000000001", email: "x@example.com" }, env.SESSION_SECRET);
  expect((await extract(ghost)).status).toBe(401);
  expect(gemini).not.toHaveBeenCalled();
});

it("a parallel burst from one user gets exactly the daily limit, and users are isolated", async () => {
  const a = (await signInAs()).body.token;
  const b = (await signInAs({ sub: "g-2", email: "two@example.com" })).body.token;

  const statuses = (await Promise.all(Array.from({ length: 12 }, () => extract(a)))).map((r) => r.status);
  expect(statuses.filter((s) => s === 200)).toHaveLength(3);
  expect(statuses.filter((s) => s === 429)).toHaveLength(9);

  expect((await extract(b)).status).toBe(200);
  expect((await (await call("/me", { token: b })).json()).used).toBe(1);
  expect((await (await call("/me", { token: a })).json()).used).toBe(3);
});

it("a per-user limit and the disabled flag in the database take effect", async () => {
  const { token } = (await signInAs()).body;
  await sql("update users set daily_limit = 1");
  expect((await extract(token)).status).toBe(200);
  expect((await extract(token)).status).toBe(429);

  await sql("update users set disabled = true");
  expect((await extract(token)).status).toBe(403);
  expect((await signInAs()).res.status).toBe(403);
});

it("each attempt writes one usage row with metadata only", async () => {
  const { token } = (await signInAs()).body;
  await sql("update users set daily_limit = 1");
  await extract(token);
  await extract(token);
  const rows = await sql("select caller, status, model, prompt_tokens, output_tokens, thought_tokens, event_count, latency_ms is not null as timed, user_id is not null as has_user from usage_events order by id");
  expect(rows).toEqual([
    { caller: "user", status: "ok", model: "gemini-3.8-flash", prompt_tokens: 10, output_tokens: 5, thought_tokens: 2, event_count: 1, timed: true, has_user: true },
    { caller: "user", status: "quota_daily", model: "gemini-3.8-flash", prompt_tokens: null, output_tokens: null, thought_tokens: null, event_count: null, timed: false, has_user: true }
  ]);
  const cols = (await sql("select column_name from information_schema.columns where table_name = 'usage_events'")).map((r) => r.column_name);
  expect(cols.some((c) => /image|screen|title|url|content/.test(c))).toBe(false);
});

it("legacy invite codes still work and are logged as invite callers", async () => {
  const code = "cc_AbCdEfGhIjKlMnOpQrStUv";
  await env.TOKENS.put(`token:${code}`, JSON.stringify({ name: "tester", limit: 2 }));
  expect((await extract(code)).status).toBe(200);
  expect(await sql("select caller, status, user_id from usage_events")).toEqual([{ caller: "invite", status: "ok", user_id: null }]);
});

it("a database outage does not lift the limit or block a signed-in user", async () => {
  const { token } = (await signInAs()).body;
  const broken = { ...env, HYPERDRIVE: { connectionString: "postgres://postgres:postgres@127.0.0.1:1/none" } };
  const go = async () => {
    const ctx = createExecutionContext();
    const res = await worker.fetch(
      new Request(`${BASE}/extract`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "CF-Connecting-IP": ip, "Content-Type": "application/json" },
        body: JSON.stringify({ image: "Y3JvcA==", screen: "c2NyZWVu", context: {} })
      }),
      broken,
      ctx
    );
    await waitOnExecutionContext(ctx);
    return res.status;
  };
  expect([await go(), await go(), await go(), await go()]).toEqual([200, 200, 200, 429]);
});
