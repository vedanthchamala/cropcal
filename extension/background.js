import { cropDataUrl, downscaleDataUrl } from "./lib/crop.js";
import { buildCalendarUrl, isPastEvent } from "./lib/calendar-url.js";
import * as anthropicProvider from "./lib/providers/anthropic.js";
import * as bridgeProvider from "./lib/providers/bridge.js";
import * as hostedProvider from "./lib/providers/hosted.js";

const PROVIDERS = { hosted: hostedProvider, api: anthropicProvider, bridge: bridgeProvider };
const DEFAULT_PROVIDER = "hosted";
const MAX_TABS = 3;
// MV3 service workers are killed after ~30s idle; extension API calls reset the
// timer, so we ping one while a slow extraction (10-30s+) is in flight.
const KEEPALIVE_MS = 20_000;

async function getSettings() {
  const stored = await chrome.storage.local.get([
    "provider",
    "inviteToken",
    "proxyUrl",
    "apiKey",
    "bridgeUrl",
    "model",
    "effort"
  ]);
  return {
    provider: DEFAULT_PROVIDER,
    model: anthropicProvider.DEFAULT_MODEL,
    effort: anthropicProvider.DEFAULT_EFFORT,
    ...stored
  };
}

chrome.runtime.onInstalled.addListener(({ reason }) => {
  if (reason === "install") chrome.runtime.openOptionsPage();
});

chrome.action.onClicked.addListener(async (tab) => {
  const settings = await getSettings();
  const needsSetup =
    (settings.provider === "hosted" && !settings.inviteToken) ||
    (settings.provider === "api" && !settings.apiKey);
  if (needsSetup) {
    chrome.runtime.openOptionsPage();
    return;
  }
  try {
    await chrome.scripting.insertCSS({
      target: { tabId: tab.id },
      files: ["content/overlay.css"]
    });
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content/overlay.js"]
    });
  } catch (err) {
    // chrome:// pages, the Web Store, and PDFs refuse injection; nothing we can do there.
    console.warn("CropCal: cannot run on this page:", err.message);
  }
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "cropcal-capture") {
    handleCapture(msg, sender.tab)
      .then((result) => sendResponse(result))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true; // async sendResponse
  }
});

async function handleCapture(msg, tab) {
  const settings = await getSettings();
  const provider = PROVIDERS[settings.provider] || hostedProvider;

  const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
  // The progress toast is only drawn once the screenshot is taken, so it can
  // never end up inside the image sent to the model.
  chrome.tabs.sendMessage(tab.id, { type: "cropcal-progress" }).catch(() => {});

  const images = {
    crop: await cropDataUrl(dataUrl, msg.rect, msg.dpr),
    screen: await downscaleDataUrl(dataUrl)
  };

  const now = new Date();
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const ctx = {
    now: now.toLocaleString("en-US", { hour12: false }),
    weekday: now.toLocaleDateString("en-US", { weekday: "long" }),
    timezone,
    pageTitle: tab.title,
    pageUrl: tab.url
  };

  const keepAlive = setInterval(() => chrome.runtime.getPlatformInfo(), KEEPALIVE_MS);
  let events;
  try {
    ({ events } = await provider.extractEvents(images, ctx, settings));
  } finally {
    clearInterval(keepAlive);
  }
  if (events.length === 0) {
    return { ok: false, error: "No event found in the selected region" };
  }

  const opened = events.slice(0, MAX_TABS);
  for (const event of opened) {
    const url = buildCalendarUrl(event, {
      timezone,
      sourceTitle: tab.title,
      sourceUrl: tab.url
    });
    await chrome.tabs.create({ url, active: opened.length === 1 });
  }

  const skipped = events.length - opened.length;
  return {
    ok: true,
    count: opened.length,
    skipped,
    lowConfidence: opened.some((e) => e.confidence === "low"),
    pastCount: opened.filter((e) => isPastEvent(e)).length
  };
}
