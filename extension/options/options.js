import * as anthropicProvider from "../lib/providers/anthropic.js";
import * as bridgeProvider from "../lib/providers/bridge.js";
import * as hostedProvider from "../lib/providers/hosted.js";
import { signIn, signInConfigured, signOut } from "../lib/auth.js";

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

// Only the default service host is a required permission; api.anthropic.com,
// localhost (bridge) and other workers.dev hosts (a custom service URL) are
// optional and requested here, from a user gesture, when chosen.
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

const ANTHROPIC_URL = "https://api.anthropic.com";

function setAccountStatus(text, error = false) {
  $("accountStatus").textContent = text;
  $("accountStatus").style.color = error ? "#b3261e" : "";
}

async function renderAccount() {
  const { sessionToken, email, proxyUrl: storedUrl } = await chrome.storage.local.get(["sessionToken", "email", "proxyUrl"]);
  $("signedOut").hidden = Boolean(sessionToken);
  $("signedIn").hidden = !sessionToken;
  $("signIn").disabled = !signInConfigured();
  if (!signInConfigured() && !sessionToken) setAccountStatus("Sign-in is not set up in this build — use an invite code under Advanced.");
  if (!sessionToken) return;
  $("email").textContent = email || "";
  $("usage").textContent = "";
  try {
    const me = await hostedProvider.testConnection({ sessionToken, email, proxyUrl: storedUrl });
    $("usage").textContent = `${me.used} of ${me.limit} crops used today`;
  } catch (err) {
    $("usage").textContent = err.message;
  }
}

$("signIn").addEventListener("click", async () => {
  setAccountStatus("Opening Google sign-in…");
  try {
    if (proxyUrl() !== hostedProvider.DEFAULT_PROXY_URL) await ensureHostPermission(proxyUrl(), "Service");
    await signIn(hostedProvider.base({ proxyUrl: proxyUrl() }));
    await chrome.storage.local.set({ provider: "hosted", proxyUrl: proxyUrl() });
    $("provider").value = "hosted";
    syncVisibility();
    setAccountStatus("");
  } catch (err) {
    setAccountStatus(err.message, true);
  }
  await renderAccount();
});

$("signOut").addEventListener("click", async () => {
  await signOut();
  setAccountStatus("");
  await renderAccount();
});

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
  $("advanced").open = $("provider").value !== "hosted" || Boolean(stored.inviteToken);
  syncVisibility();
  await renderAccount();
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
  try {
    if (provider === "api") await ensureHostPermission(ANTHROPIC_URL, "Anthropic API");
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
      const { sessionToken, email } = await chrome.storage.local.get(["sessionToken", "email"]);
      const me = await hostedProvider.testConnection({
        sessionToken,
        email,
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
      await ensureHostPermission(ANTHROPIC_URL, "Anthropic API");
      await anthropicProvider.testConnection({ apiKey, model: $("model").value });
    }
    setStatus("Connection OK.", "ok");
  } catch (err) {
    setStatus(`Failed: ${err.message}`, "error");
  }
});

load();
