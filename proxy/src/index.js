// CropCal hosted proxy: the extension's /extract contract in front of Gemini.
// Auth = invite token (KV). Limits = a Durable Object per invite code (atomic
// crops/day + crops/minute) and one service-wide (crops/day), reserved BEFORE
// the model call and refunded if it fails. Model request = byte-for-byte what
// extension-gemini builds. Images are never stored or logged.
import { buildRequest, parseResponse } from "../../extension-gemini/lib/providers/gemini.js";
import {
  GLOBAL_NAME, bearer, corsHeaders, geminiErrorMessage, isTokenShaped, rateLimitOk,
  requestTooLarge, sanitizeContext, todayKey, validateBody
} from "./lib.js";

export { QuotaCounter } from "./quota.js";

const json = (obj, status, cors) =>
  new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", ...cors } });

const counter = (env, name) => env.QUOTA.get(env.QUOTA.idFromName(name));

async function callGemini(req, attempts = 3) {
  let res;
  for (let i = 0; i < attempts; i++) {
    res = await fetch(req.url, { method: "POST", headers: req.headers, body: JSON.stringify(req.body) });
    if (res.status !== 503 && res.status !== 429) return res;
    await new Promise((r) => setTimeout(r, 1500 * (i + 1)));
  }
  return res;
}

// Cheapest checks first; an unknown code never reaches a Durable Object, so
// guessing codes cannot create objects or touch the counters.
async function authorize(request, env, cors) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  if (!(await rateLimitOk(env.RL_IP, ip))) {
    return { error: json({ error: "Too many requests — slow down" }, 429, cors) };
  }
  const token = bearer(request);
  if (!token) return { error: json({ error: "Missing invite code" }, 401, cors) };
  if (!isTokenShaped(token)) return { error: json({ error: "Invite code not recognized" }, 403, cors) };
  const rec = await env.TOKENS.get(`token:${token}`, "json");
  if (!rec || rec.disabled) return { error: json({ error: "Invite code not recognized" }, 403, cors) };
  return { token, rec, limit: Number(rec.limit || env.DAILY_LIMIT || 60) };
}

// Reserves one crop on the code's counter, then on the service-wide one. Any
// counter failure refuses the request: a limit that fails open is not a limit.
async function reserve(env, a, day, cors) {
  const mine = counter(env, `code:${a.token}`);
  const all = counter(env, GLOBAL_NAME);
  let r;
  try {
    r = await mine.reserve({ day, limit: a.limit, burst: Number(env.BURST_PER_MIN || 10) });
  } catch {
    return { error: json({ error: "The CropCal service is busy — try again in a minute" }, 503, cors) };
  }
  if (!r.ok) {
    const error =
      r.reason === "burst"
        ? "Too many crops in a minute for this invite code — slow down"
        : `Daily limit reached (${a.limit} crops/day) — resets at midnight UTC`;
    return { error: json({ error }, 429, cors) };
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
      ? { error: json({ error: "The CropCal service has reached its daily limit — try again tomorrow" }, 429, cors) }
      : { error: json({ error: "The CropCal service is busy — try again in a minute" }, 503, cors) };
  }
  const refund = async () => {
    await mine.release(day).catch(() => {});
    await all.release(day).catch(() => {});
  };
  return { used: r.used, refund };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = corsHeaders(request.headers.get("Origin"));
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (env.DISABLED === "1") {
      return json({ error: "The CropCal service is paused — try again later" }, 503, cors);
    }
    if (url.pathname === "/health") return json({ ok: true, model: env.GEMINI_MODEL }, 200, cors);

    if (url.pathname === "/me" && request.method === "GET") {
      const a = await authorize(request, env, cors);
      if (a.error) return a.error;
      let used = 0;
      try {
        used = await counter(env, `code:${a.token}`).used(todayKey());
      } catch {
        return json({ error: "The CropCal service is busy — try again in a minute" }, 503, cors);
      }
      return json({ ok: true, name: a.rec.name, used, limit: a.limit, model: env.GEMINI_MODEL }, 200, cors);
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
      if (slot.error) return slot.error;

      let parsed;
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
          return json({ error }, status, cors);
        }
        parsed = parseResponse(await res.json());
      } catch (err) {
        await slot.refund();
        return json({ error: err.message || "Model call failed" }, 502, cors);
      }
      return json(
        {
          events: parsed.events,
          meta: {
            provider: "hosted",
            model: parsed.model || env.GEMINI_MODEL,
            used: slot.used,
            limit: a.limit,
            tokens: parsed.usage
              ? { prompt: parsed.usage.promptTokenCount, output: parsed.usage.candidatesTokenCount, thoughts: parsed.usage.thoughtsTokenCount }
              : null
          }
        },
        200,
        cors
      );
    }
    return json({ error: "not found" }, 404, cors);
  }
};
