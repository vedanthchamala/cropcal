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
No account, no analytics. Full policy: https://github.com/vedanthchamala/cropcal/blob/main/PRIVACY.md

Keyboard shortcut: Alt+Shift+C (Option+Shift+C on Mac).

## Privacy tab

- **Single purpose:** Convert a user-selected screen region into a prefilled Google Calendar event.
- **Permission justifications:**
  - `activeTab`: capture a screenshot of the current tab, only when the user clicks the action or presses the shortcut.
  - `scripting`: inject the drag-to-select overlay into the current tab on that click.
  - `storage`: persist the user's API key and model settings locally.
  - Host `https://cropcal-proxy.vedhuchamala.workers.dev/*`: send the selected region to the CropCal service (a Cloudflare Worker we run) which forwards it to the Gemini API; the default path.
  - Optional host `https://*.workers.dev/*`: requested at runtime only if the user enters a different service URL in options (self-hosted proxy).
  - Host `https://api.anthropic.com/*`: send the selected region to the Anthropic API with the user's own key (optional path chosen in options).
  - Optional host `http://127.0.0.1:48765/*`, `http://localhost:48765/*`: developer-only option to route through a local server; requested at runtime only if the user selects it.
- **Remote code:** No, I am not using remote code.
- **Data usage:** collects "Website content" (the screenshot of the selected region and page, sent to the CropCal service / the user's chosen AI provider) and "Authentication information" (invite code or the user's own API key, stored locally). Not sold, not used for unrelated purposes, not used for creditworthiness.
- **Privacy policy URL:** https://github.com/vedanthchamala/cropcal/blob/main/PRIVACY.md

## Assets

- Icon 128×128: `extension/icons/icon128.png` (done).
- Screenshots (1280×800 PNG, done — rendered from the project's synthetic pages
  with the real overlay/toast CSS; all content fictional):
  1. `store/screenshots/1-drag-select-flyer.png` — overlay mid-drag on a flyer.
  2. `store/screenshots/2-chat-relative-date-toast.png` — chat with "this
     sunday 6:00-8:00pm" and the success toast.
  3. `store/screenshots/3-options.png` — options page, connected.
  4. Optional, add by hand: the prefilled Google Calendar event page from a real
     crop (it shows your Google account, so crop or blur the avatar).
- Small promo tile 440×280: `store/screenshots/promo-440x280.png` (done).
- Homepage URL: https://github.com/vedanthchamala/cropcal
- Support URL: https://github.com/vedanthchamala/cropcal/issues

## Submit (click-by-click, ~15 min + review time)

1. https://chrome.google.com/webstore/devconsole → sign in with the Google
   account that should own the listing → accept the developer agreement → pay
   the one-time $5 registration fee.
2. **Items → New item** → upload `dist/cropcal-0.1.1.zip`.
3. **Store listing tab:** paste the name, summary, description and category
   from above; upload the three screenshots and the promo tile; set the
   homepage and support URLs.
4. **Privacy tab:** single purpose + the permission justifications above;
   "Remote code: No"; data usage = Website content + Authentication
   information, with the three "not sold / not for unrelated purposes / not for
   creditworthiness" certifications; privacy policy URL above.
5. **Distribution tab:** Visibility **Unlisted**; all regions; free.
6. **Submit for review.** Typical wait 1–3 business days; the dashboard emails
   the result. If rejected, the reason is almost always a permission
   justification — reply with the wording above.
7. After approval, share the store link with invite-code holders; installs
   auto-update on every future upload (each needs a higher `version`).

## Distribution alternatives

| Channel | Effort | Tester experience |
| --- | --- | --- |
| GitHub release zip + "Load unpacked" | `./scripts/package.sh`, create a release | Developer-mode nag on every Chrome start; manual updates |
| Web Store, Unlisted | $5, listing assets, 1–3 day review | One-click install, auto-updates, link-only visibility |
| Web Store, Public | same + polish | Discoverable |

Self-hosted `.crx` files are not installable on consumer Windows/macOS Chrome, so
that route is not an option.
