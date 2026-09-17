import * as geminiProvider from "../lib/providers/gemini.js";

const $ = (id) => document.getElementById(id);
const status = $("status");

function setStatus(text, cls = "") {
  status.textContent = text;
  status.className = cls;
}

async function load() {
  const stored = await chrome.storage.local.get(["apiKey", "model", "thinking"]);
  $("apiKey").value = stored.apiKey || "";
  $("model").value = stored.model || geminiProvider.DEFAULT_MODEL;
  $("thinking").value = stored.thinking ?? geminiProvider.DEFAULT_THINKING;
}

$("save").addEventListener("click", async () => {
  const apiKey = $("apiKey").value.trim();
  if (!apiKey) {
    setStatus("A Gemini API key is required.", "error");
    return;
  }
  await chrome.storage.local.set({
    apiKey,
    model: $("model").value,
    thinking: $("thinking").value
  });
  setStatus("Saved.", "ok");
});

$("test").addEventListener("click", async () => {
  const apiKey = $("apiKey").value.trim();
  if (!apiKey) {
    setStatus("Enter an API key first.", "error");
    return;
  }
  setStatus("Testing…");
  try {
    await geminiProvider.testConnection({ apiKey, model: $("model").value });
    setStatus("Connection OK.", "ok");
  } catch (err) {
    setStatus(`Failed: ${err.message}`, "error");
  }
});

load();
