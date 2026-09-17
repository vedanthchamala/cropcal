// CropCal hosted proxy: the extension's /extract contract in front of Gemini.
// Auth = invite token (KV), quota = per-token crops/day + a service-wide
// crops/day (KV), bursts = per-IP and per-token rate limits, model request =
// byte-for-byte what extension-gemini builds. Images are never stored or logged.
import { buildRequest, parseResponse } from "../../extension-gemini/lib/providers/gemini.js";
import {
  GLOBAL_TOKEN, bearer, bumpQuota, corsHeaders, geminiErrorMessage, isTokenShaped,
  rateLimitOk, readQuota, requestTooLarge, sanitizeContext, validateBody
} from "./lib.js";

const json = (obj, status, cors) =>
  new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", ...cors } });

async function callGemini(req, attempts = 3) {
  let res;
  for (let i = 0; i < attempts; i++) {
    res = await fetch(req.url, { method: "POST", headers: req.headers, body: JSON.stringify(req.body) });
    if (res.status !== 503 && res.status !== 429) return res;
    await new Promise((r) => setTimeout(r, 1500 * (i + 1)));
  }
  return res;
}

// Every gate a request must pass before it can cost anything, cheapest first:
// IP burst limit → token shape → token lookup → token burst limit → daily quotas.
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
  if (!(await rateLimitOk(env.RL_TOKEN, token))) {
    return { error: json({ error: "Too many requests for this invite code — slow down" }, 429, cors) };
  }
  const limit = Number(rec.limit || env.DAILY_LIMIT || 60);
  const quota = await readQuota(env.TOKENS, token, limit);
  const global = await readQuota(env.TOKENS, GLOBAL_TOKEN, Number(env.GLOBAL_DAILY_LIMIT || 500));
  return { token, rec, quota, global };
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
      return json(
        { ok: true, name: a.rec.name, used: a.quota.used, limit: a.quota.limit, model: env.GEMINI_MODEL },
        200,
        cors
      );
    }

    if (url.pathname === "/extract" && request.method === "POST") {
      if (requestTooLarge(request)) return json({ error: "Request too large" }, 413, cors);
      const a = await authorize(request, env, cors);
      if (a.error) return a.error;
      if (!a.quota.allowed) {
        return json({ error: `Daily limit reached (${a.quota.limit} crops/day) — resets at midnight UTC` }, 429, cors);
      }
      if (!a.global.allowed) {
        return json({ error: "The CropCal service has reached its daily limit — try again tomorrow" }, 429, cors);
      }
      let body;
      try {
        body = await request.json();
      } catch {
        return json({ error: "bad json" }, 400, cors);
      }
      const problem = validateBody(body);
      if (problem) return json({ error: problem }, 400, cors);

      const req = buildRequest({ crop: body.image, screen: body.screen }, sanitizeContext(body.context), {
        apiKey: env.GEMINI_API_KEY,
        model: env.GEMINI_MODEL,
        thinking: env.GEMINI_THINKING || ""
      });
      const res = await callGemini(req);
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        const { status, error } = geminiErrorMessage(res.status, detail);
        return json({ error }, status, cors);
      }
      let parsed;
      try {
        parsed = parseResponse(await res.json());
      } catch (err) {
        return json({ error: err.message }, 502, cors);
      }
      await bumpQuota(env.TOKENS, a.quota.key, a.quota.used);
      await bumpQuota(env.TOKENS, a.global.key, a.global.used);
      return json(
        {
          events: parsed.events,
          meta: {
            provider: "hosted",
            model: parsed.model || env.GEMINI_MODEL,
            used: a.quota.used + 1,
            limit: a.quota.limit,
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
