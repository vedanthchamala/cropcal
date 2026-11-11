import { cropDataUrl, downscaleDataUrl } from "./lib/crop.js";
import { buildCalendarUrl, isPastEvent } from "./lib/calendar-url.js";
import { fromForm, toForm } from "./lib/review.js";
import * as anthropicProvider from "./lib/providers/anthropic.js";
import * as bridgeProvider from "./lib/providers/bridge.js";
import * as hostedProvider from "./lib/providers/hosted.js";

const PROVIDERS = { hosted: hostedProvider, api: anthropicProvider, bridge: bridgeProvider };
const DEFAULT_PROVIDER = "hosted";
// MV3 service workers are killed after ~30s idle; extension API calls reset the
// timer, so we ping one while a slow extraction (10-30s+) is in flight.
const KEEPALIVE_MS = 20_000;

async function getSettings() {
  const stored = await chrome.storage.local.get([
    "provider",
    "sessionToken",
    "email",
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
    (settings.provider === "hosted" && !hostedProvider.credential(settings)) ||
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
  if (msg.type === "cropcal-open") {
    openInCalendar(msg, sender.tab)
      .then((result) => sendResponse(result))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true;
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

  // The page shows these in the review card. Nothing is opened until the user
  // confirms, and the worker keeps no state in between (it may be suspended
  // while they read), so the card sends everything back.
  return {
    ok: true,
    timezone,
    items: events.map((event) => ({ event, form: toForm(event), past: isPastEvent(event) }))
  };
}

// The user confirmed the card: turn each edited form into the final event,
// check every one, and only then open the calendar tabs.
async function openInCalendar(msg, tab) {
  const items = Array.isArray(msg.items) ? msg.items : [];
  const errors = [];
  const urls = [];
  items.forEach((item, i) => {
    const built = fromForm(item.form || {}, item.event || {});
    if (built.error) {
      errors.push({ index: item.index ?? i, error: built.error });
      return;
    }
    try {
      urls.push(buildCalendarUrl(built.event, { timezone: msg.timezone, sourceTitle: tab.title, sourceUrl: tab.url }));
    } catch (err) {
      errors.push({ index: item.index ?? i, error: err.message });
    }
  });
  if (errors.length) return { ok: false, errors };
  if (urls.length === 0) return { ok: false, error: "Nothing selected" };
  for (const url of urls) {
    await chrome.tabs.create({ url, active: urls.length === 1 });
  }
  return { ok: true, count: urls.length };
}
