# Chrome Web Store listing (draft)

Fill these into the developer dashboard (https://chrome.google.com/webstore/devconsole).
One-time $5 developer registration; review usually takes 1–3 business days for
a listing with these permissions. Publish as **Unlisted** first so only people
with the link can install, then flip to Public later.

## Store listing

**Name:** CropCal — Screenshot to Calendar

**Summary (≤132 chars):**
Drag-select any event on your screen — flyer, chat, syllabus, email — and it opens prefilled in Google Calendar.

**Category:** Productivity → Tools

**Language:** English

**Description:**

Stop retyping event details. CropCal lets you draw a box around any event you
see in Chrome — an Instagram flyer, a GroupMe or Discord message, a row in a
syllabus, a Canvas due date, an email — and opens a Google Calendar event with
the title, date, time, location, and details already filled in. You review and
press Save; nothing is added to your calendar automatically.

What makes it accurate:
• It reads the crop with a frontier vision model, and also sees the page around
  your selection, so it can fill in the year, the host organisation, or the
  venue that a flyer leaves implicit.
• Relative dates ("this Friday", "tomorrow at 6") resolve against your clock
  and timezone. "7pm ET" becomes the right time in your calendar.
• Deadlines become a point in time, not a fake one-hour block. Recurring events
  ("every Tuesday through Dec 12") become recurring calendar events.
• Several events in one crop (a recruitment timeline, a weekly digest) each get
  their own calendar tab.

Works with an invite code (crops go through the CropCal service to Google's
Gemini API on a paid plan, nothing stored) or with your own Anthropic API key.
No account, no analytics. Full policy: <PRIVACY URL>.

Keyboard shortcut: Alt+Shift+C (Option+Shift+C on Mac).

## Privacy tab

- **Single purpose:** Convert a user-selected screen region into a prefilled Google Calendar event.
- **Permission justifications:**
  - `activeTab`: capture a screenshot of the current tab, only when the user clicks the action or presses the shortcut.
  - `scripting`: inject the drag-to-select overlay into the current tab on that click.
  - `storage`: persist the user's API key and model settings locally.
  - Host `https://*.workers.dev/*`: send the selected region to the CropCal service (Cloudflare Worker) which forwards it to the Gemini API; the default path.
  - Host `https://api.anthropic.com/*`: send the selected region to the Anthropic API with the user's own key (optional path).
  - Optional host `http://127.0.0.1:48765/*`, `http://localhost:48765/*`: developer-only option to route through a local server; requested at runtime only if the user selects it.
- **Remote code:** No, I am not using remote code.
- **Data usage:** collects "Website content" (the screenshot of the selected region and page, sent to the CropCal service / the user's chosen AI provider) and "Authentication information" (invite code or the user's own API key, stored locally). Not sold, not used for unrelated purposes, not used for creditworthiness.
- **Privacy policy URL:** link to PRIVACY.md on GitHub (raw or rendered).

## Assets

- Icon 128×128: `extension/icons/icon128.png` (done).
- Screenshots (required, 1–5): 1280×800 or 640×400 PNG/JPEG, no transparency.
  Suggested set:
  1. Overlay mid-drag over an Instagram flyer.
  2. The resulting prefilled Google Calendar event.
  3. A GroupMe message with "this Friday 7pm" → calendar with the resolved date.
  4. Options page.
- Small promo tile 440×280 (optional but improves discoverability).

## Distribution alternatives

| Channel | Effort | Tester experience |
| --- | --- | --- |
| GitHub release zip + "Load unpacked" | `./scripts/package.sh`, create a release | Developer-mode nag on every Chrome start; manual updates |
| Web Store, Unlisted | $5, listing assets, 1–3 day review | One-click install, auto-updates, link-only visibility |
| Web Store, Public | same + polish | Discoverable |

Self-hosted `.crx` files are not installable on consumer Windows/macOS Chrome, so
that route is not an option.
