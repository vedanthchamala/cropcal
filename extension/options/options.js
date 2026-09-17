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

// The bridge lives on localhost, which is an optional host permission so the
// public install prompt never mentions it. Must be called from a user gesture.
async function ensureBridgePermission(url) {
  let origin;
  try {
    origin = `${new URL(url).origin}/*`;
  } catch {
    throw new Error("Bridge URL is not a valid URL");
  }
  const perm = { origins: [origin] };
  if (await chrome.permissions.contains(perm)) return;
  let granted = false;
  try {
    granted = await chrome.permissions.request(perm);
  } catch (err) {
    throw new Error(
      `Cannot request access to ${origin} — only the default bridge port is allowed (${err.message})`
    );
  }
  if (!granted) throw new Error("Permission to reach the bridge was declined");
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
  } catch (err) {
    setStatus(err.message, "error");
    return;
  }
  await chrome.storage.local.set({
    provider,
    inviteToken,
    proxyUrl: $("proxyUrl").value.trim() || hostedProvider.DEFAULT_PROXY_URL,
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
