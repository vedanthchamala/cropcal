// CropCal hosted proxy: the extension's /extract contract in front of Gemini.
// Auth = a session token issued after Google sign-in (or, for one more release,
// a legacy invite code in KV). Limits = a Durable Object per caller (atomic
// crops/day + crops/minute) and one service-wide (crops/day), reserved BEFORE
// the model call and refunded if it fails. The prompt and schema are the
// extension's own (extension/lib/schema.js). Images are never stored or logged;
// Postgres holds accounts and usage metadata only.
import { buildRequest, parseResponse } from "./gemini.js";
import { dbConfigured, getUser, insertUsage, upsertUser, withDb } from "./db.js";
import { verifyGoogleIdToken } from "./google.js";
import {
  GLOBAL_NAME, bearer, corsHeaders, geminiErrorMessage, isTokenShaped, rateLimitOk,
  requestTooLarge, sanitizeContext, todayKey, validateBody
} from "./lib.js";
import { signSession, verifySession } from "./session.js";

export { QuotaCounter } from "./quota.js";

const json = (obj, status, cors) =>
  new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", ...cors } });

const counter = (env, name) => env.QUOTA.get(env.QUOTA.idFromName(name));

const BUSY = "The CropCal service is busy — try again in a minute";

// Per attempt, so a hung upstream cannot hold a reservation open indefinitely.
// Retries only follow fast 429/503 answers, which keeps the total under the
// extension's own 90 s abort.
const ATTEMPT_TIMEOUT_MS = 45_000;

async function callGemini(req, attempts = 3) {
  let res;
  for (let i = 0; i < attempts; i++) {
    res = await fetch(req.url, {
      method: "POST",
      headers: req.headers,
      body: JSON.stringify(req.body),
      signal: AbortSignal.timeout(ATTEMPT_TIMEOUT_MS)
    });
    if ((res.status !== 503 && res.status !== 429) || i === attempts - 1) return res;
    await new Promise((r) => setTimeout(r, 1500 * (i + 1)));
  }
  return res;
}

// A signed-in user. The token proves who they are without a database read; the
// read that follows picks up a per-user limit or a disabled flag. If the
// database is unreachable the defaults apply — the Durable Object still caps
// the user, so an outage cannot lift a limit.
async function authorizeUser(token, env, cors) {
  const session = await verifySession(token, env.SESSION_SECRET);
  if (!session) return { error: json({ error: "Sign in to CropCal again", code: "session" }, 401, cors) };
  let user = { id: session.uid, email: session.email, daily_limit: null, disabled: false };
  if (dbConfigured(env)) {
    try {
      const row = await withDb(env, (db) => getUser(db, session.uid));
      if (!row) return { error: json({ error: "Sign in to CropCal again", code: "session" }, 401, cors) };
      user = row;
    } catch {
      // defaults above
    }
  }
  if (user.disabled) return { error: json({ error: "This account has been disabled" }, 403, cors) };
  return {
    kind: "user",
    userId: user.id,
    name: user.email,
    counterName: `user:${user.id}`,
    limit: Number(user.daily_limit ?? env.USER_DAILY_LIMIT ?? 20)
  };
}

// Cheapest checks first; an unknown code never reaches a Durable Object, so
// guessing codes cannot create objects or touch the counters.
async function authorize(request, env, cors) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  if (!(await rateLimitOk(env.RL_IP, ip))) {
    return { error: json({ error: "Too many requests — slow down" }, 429, cors) };
  }
  const token = bearer(request);
  if (!token) return { error: json({ error: "Sign in to CropCal first", code: "session" }, 401, cors) };
  if (!token.startsWith("cc_")) return authorizeUser(token, env, cors);

  if (!isTokenShaped(token)) return { error: json({ error: "Invite code not recognized" }, 403, cors) };
  const rec = await env.TOKENS.get(`token:${token}`, "json");
  if (!rec || rec.disabled) return { error: json({ error: "Invite code not recognized" }, 403, cors) };
  return {
    kind: "invite",
    userId: null,
    name: rec.name,
    counterName: `code:${token}`,
    limit: Number(rec.limit ?? env.DAILY_LIMIT ?? 60)
  };
}

// Reserves one crop on the caller's counter, then on the service-wide one. Any
// counter failure refuses the request: a limit that fails open is not a limit.
async function reserve(env, a, day, cors) {
  const mine = counter(env, a.counterName);
  const all = counter(env, GLOBAL_NAME);
  let r;
  try {
    r = await mine.reserve({ day, limit: a.limit, burst: Number(env.BURST_PER_MIN || 10) });
  } catch {
    return { reason: "counter_error", error: json({ error: BUSY }, 503, cors) };
  }
  if (!r.ok) {
    const error =
      r.reason === "burst"
        ? "Too many crops in a minute — slow down"
        : `Daily limit reached (${a.limit} crops/day) — resets at midnight UTC`;
    return { reason: `quota_${r.reason}`, error: json({ error }, 429, cors) };
  }
  let g;
  try {
    g = await all.reserve({ day, limit: Number(env.GLOBAL_DAILY_LIMIT || 500), burst: 0 });
  } catch {
    g = null;
  }
  if (!g || !g.ok) {
    await mine.release(day).catch(() => {});
    return g
      ? { reason: "quota_global", error: json({ error: "The CropCal service has reached its daily limit — try again tomorrow" }, 429, cors) }
      : { reason: "counter_error", error: json({ error: BUSY }, 503, cors) };
  }
  // billed = Gemini answered (and charged) but the answer was unusable. The
  // caller gets the crop back; the service-wide count keeps it, because that
  // counter exists to bound spend.
  const refund = async ({ billed = false } = {}) => {
    await mine.release(day).catch(() => {});
    if (!billed) await all.release(day).catch(() => {});
  };
  return { used: r.used, refund };
}

// Usage metadata, written after the response so it never adds latency and a
// database failure never fails a crop.
function logUsage(ctx, env, a, fields) {
  if (!dbConfigured(env)) return;
  const row = { userId: a.userId, caller: a.kind, model: env.GEMINI_MODEL, ...fields };
  ctx.waitUntil(withDb(env, (db) => insertUsage(db, row)).catch(() => {}));
}

async function signIn(request, env, cors) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  if (!(await rateLimitOk(env.RL_IP, ip))) return json({ error: "Too many requests — slow down" }, 429, cors);
  if (!dbConfigured(env) || !env.SESSION_SECRET || !env.GOOGLE_CLIENT_ID) {
    return json({ error: "Sign-in is not available yet" }, 503, cors);
  }
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "bad json" }, 400, cors);
  }
  let identity;
  try {
    identity = await verifyGoogleIdToken(body?.id_token, { clientId: env.GOOGLE_CLIENT_ID });
  } catch (err) {
    return json({ error: err.message }, 401, cors);
  }
  let user;
  try {
    user = await withDb(env, (db) => upsertUser(db, identity));
  } catch {
    return json({ error: BUSY }, 503, cors);
  }
  if (user.disabled) return json({ error: "This account has been disabled" }, 403, cors);
  const token = await signSession({ uid: user.id, email: user.email }, env.SESSION_SECRET);
  return json(
    { ok: true, token, email: user.email, limit: Number(user.daily_limit ?? env.USER_DAILY_LIMIT ?? 20) },
    200,
    cors
  );
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const cors = corsHeaders(request.headers.get("Origin"));
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (env.DISABLED === "1") {
      return json({ error: "The CropCal service is paused — try again later" }, 503, cors);
    }
    if (url.pathname === "/health") return json({ ok: true, model: env.GEMINI_MODEL }, 200, cors);

    if (url.pathname === "/auth/google" && request.method === "POST") return signIn(request, env, cors);

    if (url.pathname === "/me" && request.method === "GET") {
      const a = await authorize(request, env, cors);
      if (a.error) return a.error;
      let used = 0;
      try {
        used = await counter(env, a.counterName).used(todayKey());
      } catch {
        return json({ error: BUSY }, 503, cors);
      }
      return json({ ok: true, name: a.name, used, limit: a.limit, model: env.GEMINI_MODEL }, 200, cors);
    }

    if (url.pathname === "/extract" && request.method === "POST") {
      if (requestTooLarge(request)) return json({ error: "Request too large" }, 413, cors);
      const a = await authorize(request, env, cors);
      if (a.error) return a.error;
      let body;
      try {
        body = await request.json();
      } catch {
        return json({ error: "bad json" }, 400, cors);
      }
      const problem = validateBody(body);
      if (problem) return json({ error: problem }, 400, cors);

      const day = todayKey();
      const slot = await reserve(env, a, day, cors);
      if (slot.error) {
        logUsage(ctx, env, a, { status: slot.reason });
        return slot.error;
      }

      const started = Date.now();
      const latencyMs = () => Date.now() - started;
      let data;
      try {
        const req = buildRequest({ crop: body.image, screen: body.screen }, sanitizeContext(body.context), {
          apiKey: env.GEMINI_API_KEY,
          model: env.GEMINI_MODEL,
          thinking: env.GEMINI_THINKING || ""
        });
        const res = await callGemini(req);
        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          const { status, error } = geminiErrorMessage(res.status, detail);
          await slot.refund();
          logUsage(ctx, env, a, { status: `model_${res.status}`, latencyMs: latencyMs() });
          return json({ error }, status, cors);
        }
        data = await res.json();
      } catch (err) {
        await slot.refund();
        const timedOut = err?.name === "TimeoutError";
        logUsage(ctx, env, a, { status: timedOut ? "timeout" : "unreachable", latencyMs: latencyMs() });
        return timedOut
          ? json({ error: "The model took too long to answer — try again" }, 504, cors)
          : json({ error: "Could not reach the model — try again in a minute" }, 502, cors);
      }
      const usage = data?.usageMetadata;
      const tokens = usage
        ? { prompt: usage.promptTokenCount, output: usage.candidatesTokenCount, thoughts: usage.thoughtsTokenCount }
        : null;
      const tokenFields = {
        promptTokens: tokens?.prompt, outputTokens: tokens?.output, thoughtTokens: tokens?.thoughts
      };
      let parsed;
      try {
        parsed = parseResponse(data);
      } catch (err) {
        await slot.refund({ billed: true });
        logUsage(ctx, env, a, { status: "unusable", latencyMs: latencyMs(), ...tokenFields });
        return json({ error: err.message || "Model call failed" }, 502, cors);
      }
      logUsage(ctx, env, a, {
        status: "ok", latencyMs: latencyMs(), eventCount: parsed.events.length, ...tokenFields
      });
      return json(
        {
          events: parsed.events,
          meta: { provider: "hosted", model: parsed.model || env.GEMINI_MODEL, used: slot.used, limit: a.limit, tokens }
        },
        200,
        cors
      );
    }
    return json({ error: "not found" }, 404, cors);
  }
};
