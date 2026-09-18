import * as anthropicProvider from "../lib/providers/anthropic.js";
import * as bridgeProvider from "../lib/providers/bridge.js";
import * as hostedProvider from "../lib/providers/hosted.js";

const $ = (id) => document.getElementById(id);
const status = $("status");

function setStatus(text, cls = "") {
  status.textContent = text;
  status.className = cls;
}

function syncVisibility() {
  const provider = $("provider").value;
  $("hostedSection").hidden = provider !== "hosted";
  $("bridgeSection").hidden = provider !== "bridge";
  $("apiSection").hidden = provider !== "api";
}

function bridgeUrl() {
  return $("bridgeUrl").value.trim() || bridgeProvider.DEFAULT_BRIDGE_URL;
}

// Only the default service host and api.anthropic.com are required
// permissions; localhost (bridge) and other workers.dev hosts (a custom service
// URL) are optional and requested here, from a user gesture, when chosen.
async function ensureHostPermission(url, what) {
  let origin;
  try {
    origin = `${new URL(url).origin}/*`;
  } catch {
    throw new Error(`${what} URL is not a valid URL`);
  }
  const perm = { origins: [origin] };
  if (await chrome.permissions.contains(perm)) return;
  let granted = false;
  try {
    granted = await chrome.permissions.request(perm);
  } catch (err) {
    throw new Error(`Cannot request access to ${origin} (${err.message})`);
  }
  if (!granted) throw new Error(`Permission to reach the ${what.toLowerCase()} was declined`);
}

const ensureBridgePermission = (url) => ensureHostPermission(url, "Bridge");

function proxyUrl() {
  return $("proxyUrl").value.trim() || hostedProvider.DEFAULT_PROXY_URL;
}

async function load() {
  const stored = await chrome.storage.local.get([
    "provider",
    "inviteToken",
    "proxyUrl",
    "apiKey",
    "bridgeUrl",
    "model",
    "effort"
  ]);
  $("provider").value = stored.provider || "hosted";
  $("inviteToken").value = stored.inviteToken || "";
  $("proxyUrl").value = stored.proxyUrl || hostedProvider.DEFAULT_PROXY_URL;
  $("bridgeUrl").value = stored.bridgeUrl || bridgeProvider.DEFAULT_BRIDGE_URL;
  $("apiKey").value = stored.apiKey || "";
  $("model").value = stored.model || anthropicProvider.DEFAULT_MODEL;
  $("effort").value = stored.effort || anthropicProvider.DEFAULT_EFFORT;
  syncVisibility();
}

$("provider").addEventListener("change", syncVisibility);

$("save").addEventListener("click", async () => {
  const provider = $("provider").value;
  const apiKey = $("apiKey").value.trim();
  const inviteToken = $("inviteToken").value.trim();
  if (provider === "api" && !apiKey) {
    setStatus("API key is required for the API provider.", "error");
    return;
  }
  if (provider === "hosted" && !inviteToken) {
    setStatus("Paste your invite code first.", "error");
    return;
  }
  try {
    if (provider === "bridge") await ensureBridgePermission(bridgeUrl());
    if (provider === "hosted" && proxyUrl() !== hostedProvider.DEFAULT_PROXY_URL) {
      await ensureHostPermission(proxyUrl(), "Service");
    }
  } catch (err) {
    setStatus(err.message, "error");
    return;
  }
  await chrome.storage.local.set({
    provider,
    inviteToken,
    proxyUrl: proxyUrl(),
    apiKey,
    bridgeUrl: bridgeUrl(),
    model: $("model").value,
    effort: $("effort").value
  });
  setStatus("Saved.", "ok");
});

$("test").addEventListener("click", async () => {
  const provider = $("provider").value;
  setStatus("Testing…");
  try {
    if (provider === "hosted") {
      if (proxyUrl() !== hostedProvider.DEFAULT_PROXY_URL) await ensureHostPermission(proxyUrl(), "Service");
      const me = await hostedProvider.testConnection({
        inviteToken: $("inviteToken").value.trim(),
        proxyUrl: $("proxyUrl").value.trim()
      });
      setStatus(`Connected as ${me.name} — ${me.used}/${me.limit} crops used today (${me.model}).`, "ok");
      return;
    }
    if (provider === "bridge") {
      await ensureBridgePermission(bridgeUrl());
      await bridgeProvider.testConnection({ bridgeUrl: bridgeUrl() });
    } else {
      const apiKey = $("apiKey").value.trim();
      if (!apiKey) {
        setStatus("Enter an API key first.", "error");
        return;
      }
      await anthropicProvider.testConnection({ apiKey, model: $("model").value });
    }
    setStatus("Connection OK.", "ok");
  } catch (err) {
    setStatus(`Failed: ${err.message}`, "error");
  }
});

load();
