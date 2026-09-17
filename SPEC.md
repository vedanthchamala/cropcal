# CropCal — Screenshot → Google Calendar

Drag-select any region of the screen containing event info (flyer, GroupMe screenshot,
syllabus, email) and turn it into a Google Calendar event. Cloud model first; a
self-fine-tuned ~2B vision-language model becomes the private/local backend later.

**Working name:** CropCal (rename before shipping).

## Product decisions (agreed 2026-08-31)

- **v0 is cloud-backed** (Claude as both the product backend and the future teacher).
  The local fine-tuned model is the Phase 2–3 payoff, shipped as an optional
  "local/private mode" only if it wins on the eval harness.
- **Inference backend is swappable** behind one interface:
  `extractEvents(imageBase64, context, settings) -> EventJSON[]`. Two providers exist:
  - `bridge` (default): local server (`bridge/server.mjs`, port 48765, started via
    `./scripts/bridge.sh`) that shells out to headless `claude -p` — covered by the
    user's Claude subscription, no API key. ~10–30s/crop; dev + dataset labeling.
  - `api`: direct Anthropic API with a key (faster, for when a key exists).
- **v0 calendar integration is the zero-OAuth template link**
  (`calendar.google.com/calendar/render?action=TEMPLATE&...`). Google's own event
  page is the review/edit UI. OAuth via `chrome.identity` comes later.
- **Eval harness has three contenders:** frontier VLM (teacher), fine-tuned ~2B VLM
  (student), OCR + small text LLM (baseline). Metrics: field-level accuracy
  (title / start / end / location / recurrence), latency, cost. Datetime resolution
  is scored separately — it's where Gmail/Apple parsers fail and where we win.

## Event JSON schema (v1)

The model returns `{ "events": [Event, ...] }`; empty array = no event found.

| Field        | Type            | Notes                                                            |
| ------------ | --------------- | ---------------------------------------------------------------- |
| `title`      | string          | Short human title                                                |
| `start`      | string          | `YYYY-MM-DDTHH:MM:SS`, **floating local time** (no offset)       |
| `end`        | string \| null  | Same format. All-day: last day of the event (inclusive)          |
| `all_day`    | boolean         | Time portion of start/end ignored when true                      |
| `timezone`   | string \| null  | IANA tz, only if the source explicitly implies a non-local tz    |
| `location`   | string \| null  |                                                                  |
| `description`| string \| null  | Extra details from the image (links, price, RSVP)                |
| `recurrence` | string \| null  | `RRULE:...` when the source indicates repetition                 |
| `confidence` | "high" \| "medium" \| "low" |                                                      |
| `notes`      | string \| null  | Ambiguities (e.g. "year not stated, assumed next occurrence")    |

Rules baked into the extraction prompt:
- Current datetime (with weekday) + user IANA tz + page title/URL are given as context;
  relative dates ("this Friday") resolve against them.
- Missing year → next future occurrence.
- Defaults applied by the extension, not the model: missing end → start + 1h (timed)
  or single-day (all-day).

## Architecture (Phase 0)

```
extension/
  manifest.json            MV3; activeTab + scripting + storage; host perm api.anthropic.com;
                           localhost bridge origins are optional_host_permissions
  icons/                   16/32/48/128 px PNGs (rendered from a headless-Chrome HTML icon)
  background.js            service worker (module): capture → crop → extract → open calendar tab
  content/overlay.js|.css  drag-select overlay + status toasts (plain JS, injected on action click)
  lib/
    schema.js              event JSON schema + system prompt
    calendar-url.js        EventJSON → Google Calendar template URL (pure, unit-tested)
    crop.js                dataURL + rect + dpr → cropped/downscaled base64 PNG (OffscreenCanvas)
    providers/anthropic.js Claude API call (raw fetch, structured outputs)
  options/                 API key (default provider), model, effort; bridge for developers;
                           test-connection button; opened automatically on first install
tests/                     node --test unit tests for pure lib code
```

Flow: toolbar click (or Alt/Option+Shift+C) → overlay injected → user drags region →
overlay hides itself → background `captureVisibleTab` → crop at devicePixelRatio →
Claude API (structured output against the schema above) → one prefilled Google
Calendar tab per event (max 3) → toast reports outcome.

API notes (verified against claude-api reference 2026-08-31):
- Default model `claude-opus-5`, adaptive thinking (default), `output_config.effort`
  user-configurable (default `medium` for interactive latency).
- Structured outputs: `output_config.format = {type: "json_schema", schema}`.
- Server-side refusal fallbacks enabled by default on Opus 5 / Fable 5
  (`anthropic-beta: server-side-fallback-2026-07-01`, `fallbacks: "default"`).
- Key stored in `chrome.storage.local`, never synced.

## Phases

- **Phase 0 (now):** extension skeleton, end-to-end cloud flow. Doubles as the
  data-collection tool (own usage, opt-in logging later).
- **Phase 1:** dataset pipeline (synthetic renders + real scraped flyers/emails,
  teacher-labeled); eval harness built BEFORE training — grades teacher and OCR
  baseline first to establish ceiling and floor. Teacher labeling runs through the
  bridge (`claude -p`, subscription-covered) at moderate scale; the bridge's `meta`
  (latency, turns) already feeds the harness's latency column.
- **Phase 2:** distill student (~2B VLM: shortlist Qwen2.5-VL-3B / Qwen3-VL-2B,
  SmolVLM2, Moondream — re-verify at phase start) via QLoRA on DGX Spark
  (128GB unified, ~273GB/s bandwidth is the constraint; fine at this scale).
- **Phase 3:** quantize; pick local runtime (WebGPU in-extension vs companion app)
  from measured latency, not hope.
- **Phase 4:** Chrome Web Store ship; dataset + weights on Hugging Face.
