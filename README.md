# CropCal — screenshot to Google Calendar

Drag a box around any event on your screen (a flyer on Instagram, a GroupMe
message, a syllabus row, an email) and CropCal opens a prefilled Google Calendar
event for you to review and save. A frontier vision model reads the crop, and
also sees a downscaled copy of the page so it can fill in the year, host, and
venue that usually sit just outside the part you selected.

## Install (testers)

1. Download `cropcal-<version>.zip` from the latest GitHub release and unzip it.
2. Open `chrome://extensions`, turn on **Developer mode** (top right), click
   **Load unpacked**, and pick the unzipped folder.
3. The options page opens automatically. Paste the invite code you were
   given, click **Save**, then **Test connection**. (Advanced: you can use
   your own Anthropic API key instead, or the local developer bridge.)
4. Pin CropCal to the toolbar (puzzle-piece icon → pin).

Chrome will show a "Disable developer mode extensions" nag on each launch
until the extension is published on the Web Store. That is expected.

## Use

- Click the CropCal toolbar icon, or press **Alt+Shift+C** (Option+Shift+C on
  Mac), then drag a rectangle around the event. Esc cancels.
- A spinner shows while the model reads the crop (a few seconds on the API).
- One Google Calendar tab opens per event found (up to three). Review the
  fields and press Save in Google Calendar; nothing is saved automatically.
- The toast warns you if the model was unsure about a date or if the date is
  already in the past (usually a missing year on a flyer).

Tips: include the date, time, and title in the crop when you can; the page
around it is used for context, so a tight crop of just the date line still
works if the title is visible on screen.

Cost: with an invite code, nothing — the CropCal service forwards crops to
Gemini Flash on a paid plan (roughly half a cent each) and each code has a
daily limit. With your own Anthropic key, each crop is roughly $0.15–0.30 on
Claude Opus 5 (the most accurate option) or a third of that on Sonnet 5.

Limits: only the visible part of the page is captured (scroll first).
`chrome://` pages, the Chrome Web Store, and PDF viewers cannot be captured.

## Gemini build (experimental)

`extension-gemini/` is an isolated copy of the extension that uses the Gemini
API (`gemini-3.8-flash` by default) instead of Anthropic, so it can be tuned
without touching the main build. A Gemini key comes from
https://aistudio.google.com/apikey with a plain Google account and has a free
tier. Note the free tier's terms let Google use prompts to improve its
products; a key on a billed project is not used that way. Build it with
`./scripts/package.sh extension-gemini`; load it the same way. Accuracy
numbers for this build versus the Anthropic build are tracked in STATUS.md.

## Privacy

See [PRIVACY.md](PRIVACY.md). Short version: no server, no analytics; the
crop and page context go only to the API provider you configured, and settings
live only in your browser.

## Hosted service (proxy/)

`proxy/` is a Cloudflare Worker that speaks the same `/extract` contract as
the bridge: it checks an invite code, enforces a per-code daily limit, sends
the crop to Gemini with the request `extension-gemini/` builds, and returns
the events. It stores nothing but counters. Limits are hard caps held in a
Durable Object per invite code (crops/day and crops/minute) plus one for the
whole service (`GLOBAL_DAILY_LIMIT` in `proxy/wrangler.toml`); a crop is
reserved before the model call and refunded if it fails. `DISABLED = "1"`
pauses the service. Deploy once with
`pnpm exec wrangler login` then `./proxy/scripts/setup.sh`; mint codes with
`./proxy/scripts/invite.sh <name> [crops_per_day]`. Local run:
`cd proxy && ../node_modules/.bin/wrangler dev --local`.

## Development

```
pnpm install         # nothing to install, but sets up the lockfile
pnpm test            # unit tests for the pure lib code (node --test)
./scripts/bridge.sh  # optional: local Claude Code bridge instead of an API key
./scripts/package.sh # builds dist/cropcal-<version>.zip
```

- `extension/` is plain ES modules, Manifest V3, no build step.
- `bridge/` lets contributors with Claude Code route extraction through
  `claude -p` (covered by a subscription). Select "Local Claude Code bridge" in
  the options page; saving asks for permission to reach localhost.
- `ml/` holds the eval harness and synthetic dataset generators (`uv`). See
  `SPEC.md` for the event schema and roadmap, `STATUS.md` for current state.

To run the accuracy suite against the live bridge:

```
./scripts/bridge.sh                      # terminal 1
./scripts/eval.sh --provider bridge --set synth_v1   # terminal 2
```
