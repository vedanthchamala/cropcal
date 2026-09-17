# CropCal privacy policy

_Last updated: 2026-09-10_

CropCal is a Chrome extension that turns a region of your screen into a Google
Calendar event. This page explains exactly what data it touches.

## What CropCal collects

Nothing is collected by the developer. CropCal has no server of its own, no
analytics, no accounts, and no telemetry.

## What CropCal sends, and where

When you drag-select a region, CropCal:

1. Takes a screenshot of the current browser tab (only when you trigger it).
2. Crops it to your selection and creates a downscaled copy of the visible tab
   for context (so the model can resolve things like the year or the host
   organisation that sit just outside your selection).
3. Sends both images, the current date/time, your timezone, and the page's
   title and URL to the AI provider you configured in the options page:
   - **CropCal service** (default, invite code): a small server we run on
     Cloudflare Workers that forwards the request to Google's Gemini API on a
     paid plan (Google states paid-tier API data is not used to improve its
     products). The service keeps only per-code and service-wide counts of crops per
     day, plus short-lived rate-limit counters keyed by invite code and IP
     address; it never stores or logs the images, the page title, or the URL.
   - **Anthropic API** (`api.anthropic.com`), using the API key you entered.
     Anthropic's handling of that data is governed by
     [Anthropic's privacy policy](https://www.anthropic.com/privacy) and their
     API data-retention terms.
   - **Local bridge** (developer option): a server on your own machine at
     `127.0.0.1`. Nothing leaves your computer except through your own Claude
     Code session.
4. Opens a Google Calendar "create event" page prefilled with the result. The
   event description includes the source page title and URL so you can find
   the original later. Nothing is saved to your calendar until you click Save
   in Google Calendar.

## What CropCal stores

- Your provider choice, invite code or API key, model and effort settings,
  stored in `chrome.storage.local` on your device only. They are never synced or sent
  anywhere other than the provider's API endpoint.
- Screenshots are held in memory only for the duration of the request and are
  never written to disk or retained by the extension.

## Permissions

| Permission | Why |
| --- | --- |
| `activeTab` | Capture the tab you clicked the button on, only at that moment. |
| `scripting` | Inject the drag-select overlay into that tab. |
| `storage` | Save your settings locally. |
| `https://*.workers.dev/*` | Reach the CropCal service (Cloudflare Workers). |
| `https://api.anthropic.com/*` | Call the Anthropic API with your key, if you choose that option. |
| `http://127.0.0.1:48765/*` (optional, off by default) | Only requested if you choose the developer bridge option. |

## Contact

Questions: open an issue on the project's GitHub repository.
