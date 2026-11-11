// Hosted provider: CropCal's own proxy (Cloudflare Worker in proxy/) in front
// of Gemini Flash. Users sign in with Google; a legacy invite code still works.
// Same /extract contract as the bridge, plus /me for the options page.
import { signIn } from "../auth.js";

export const DEFAULT_PROXY_URL = "https://cropcal-proxy.vedhuchamala.workers.dev";

export function base(settings) {
  return (settings.proxyUrl || DEFAULT_PROXY_URL).replace(/\/+$/, "");
}

export const credential = (settings) => settings.sessionToken || settings.inviteToken || "";

const friendly = (status, data) => {
  if (status === 401) return "Sign in to CropCal again (open CropCal options)";
  if (status === 403) return data?.error || "Not allowed — check CropCal options";
  if (status === 429) return data?.error || "Daily limit reached — try again tomorrow";
  if (status === 503) return data?.error || "The model is busy right now — try again in a minute";
  return data?.error || `Proxy error (HTTP ${status})`;
};

// One request with the current credential; if a session has expired, renews it
// silently once and retries.
async function authed(settings, path, init = {}) {
  const send = (token) =>
    fetch(`${base(settings)}${path}`, { ...init, headers: { ...init.headers, Authorization: `Bearer ${token}` } });
  let res = await send(credential(settings));
  if (res.status === 401 && settings.sessionToken) {
    try {
      const renewed = await signIn(base(settings), { interactive: false, loginHint: settings.email || "" });
      res = await send(renewed.sessionToken);
    } catch {
      // keep the 401
    }
  }
  return res;
}

export async function extractEvents(images, ctx, settings) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90_000);
  let res;
  try {
    res = await authed(settings, "/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: images.crop, screen: images.screen, context: ctx }),
      signal: controller.signal
    });
  } catch (err) {
    throw new Error(err.name === "AbortError" ? "Request timed out after 90s" : `Network error: ${err.message}`);
  } finally {
    clearTimeout(timer);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(friendly(res.status, data));
  if (!data || !Array.isArray(data.events)) throw new Error("Proxy returned no events array");
  return { events: data.events, meta: data.meta };
}

// Returns {name, used, limit, model} for the options page.
export async function testConnection(settings) {
  let res;
  try {
    res = await authed(settings, "/me");
  } catch (err) {
    throw new Error(`Cannot reach the CropCal service (${err.message})`);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(friendly(res.status, data));
  return data;
}
