// Hosted provider: CropCal's own proxy (Cloudflare Worker in proxy/) in front
// of Gemini Flash. Users only need an invite code. Same /extract contract as
// the bridge, plus /me for the options page.
export const DEFAULT_PROXY_URL = "https://cropcal-proxy.vedhuchamala.workers.dev";

function base(settings) {
  return (settings.proxyUrl || DEFAULT_PROXY_URL).replace(/\/+$/, "");
}

const friendly = (status, data) => {
  if (status === 401 || status === 403) return "Invite code not accepted — check it in CropCal options";
  if (status === 429) return data?.error || "Daily limit reached — try again tomorrow";
  if (status === 503) return data?.error || "The model is busy right now — try again in a minute";
  return data?.error || `Proxy error (HTTP ${status})`;
};

export async function extractEvents(images, ctx, settings) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90_000);
  let res;
  try {
    res = await fetch(`${base(settings)}/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${settings.inviteToken || ""}` },
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
    res = await fetch(`${base(settings)}/me`, {
      headers: { Authorization: `Bearer ${settings.inviteToken || ""}` }
    });
  } catch (err) {
    throw new Error(`Cannot reach the CropCal service (${err.message})`);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(friendly(res.status, data));
  return data;
}
