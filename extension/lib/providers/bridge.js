export const DEFAULT_BRIDGE_URL = "http://127.0.0.1:48765";

export async function extractEvents(images, ctx, settings) {
  const base = (settings.bridgeUrl || DEFAULT_BRIDGE_URL).replace(/\/+$/, "");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 160_000);

  let res;
  try {
    res = await fetch(`${base}/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: images.crop, screen: images.screen, context: ctx }),
      signal: controller.signal
    });
  } catch (err) {
    throw new Error(
      err.name === "AbortError"
        ? "Bridge request timed out"
        : "Bridge not reachable — run ./scripts/bridge.sh in the project folder first"
    );
  } finally {
    clearTimeout(timer);
  }

  const data = await res.json().catch(() => null);
  if (!res.ok || !data) {
    throw new Error(data?.error || `Bridge error (HTTP ${res.status})`);
  }
  if (!Array.isArray(data.events)) throw new Error("Bridge returned no events array");
  return { events: data.events, meta: data.meta };
}

export async function testConnection(settings) {
  const base = (settings.bridgeUrl || DEFAULT_BRIDGE_URL).replace(/\/+$/, "");
  let res;
  try {
    res = await fetch(`${base}/health`);
  } catch {
    throw new Error("Bridge not reachable — run ./scripts/bridge.sh first");
  }
  if (!res.ok) throw new Error(`Bridge health check failed (HTTP ${res.status})`);
  return true;
}
