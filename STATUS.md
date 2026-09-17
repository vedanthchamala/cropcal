# Status

_Updated 2026-09-16_

## Hosted proxy deployed and verified live (2026-09-16 evening)
- `pnpm exec wrangler login` done (account `vedhuchamala@gmail.com`),
  workers.dev subdomain `vedhuchamala` registered, `./proxy/scripts/setup.sh`
  run by the user: KV namespace `fa47b3df…` written into `wrangler.toml`,
  `GEMINI_API_KEY` secret set, deployed 2026-09-17T00:45Z. The TLS cert for
  the new subdomain took ~3.5 min to issue (handshake alert 40 until then).
- **Live URL = `https://cropcal-proxy.vedhuchamala.workers.dev`**, which is
  already `DEFAULT_PROXY_URL` in `extension/lib/providers/hosted.js` — no
  code change needed.
- One invite code minted for the author (`invite.sh vedanth 200`); the code
  itself is not recorded here.
- **Live end-to-end** (scratch script, harness scorer): `/health` 200 with
  model; bad code → 403; `/me` → {vedanth, 0/200}; eval_v0 case
  `2026-09-10T16-11-59-526Z` (Bloomberg Day-in-the-Life panel, real) through
  `/extract` → **HTTP 200 in 3.9 s, 8/8 fields vs gold** (3,135 prompt /
  167 output / 582 thinking tokens); `/me` → 1/200 afterwards.
- Note: Cloudflare's edge returned a non-JSON error to Python's default
  `User-Agent`; a custom UA fixed it. Chrome's fetch is unaffected.
- **Hardening (2026-09-16, unit-tested + smoke-tested under `wrangler dev
  --local`, deploy pending):** service-wide `GLOBAL_DAILY_LIMIT` (500/day,
  KV counter `use:global:<day>`, same soft semantics as per-code); per-IP
  (30/min) and per-code (10/min) burst limits via Cloudflare's
  `[[ratelimits]]` binding (fail-open if the binding is missing); 413 on
  `Content-Length` > 13 MB before the body is read; CORS headers only for
  `chrome|moz|safari-web-extension://` origins (a web page cannot use a
  leaked code from inside a browser); `DISABLED = "1"` kill switch → 503;
  KV counter bumps swallow write errors (KV allows ~1 write/s per key).
  4 new tests (39 JS total). Local smoke: web origin → no ACAO, extension
  origin → reflected, preflight 204 without ACAO, 13.5 MB body → 413, burst
  → 429 after 10 `/me` calls, extract 8/8 with both counters = 1, second
  extract on a limit-1 code → 429 before Gemini. `ml/report.html` added to
  `.gitignore` (3.3 MB, regenerated, holds real-capture labels).
- The "Blocked on the user" list in the 09-12 section is cleared. Remaining
  before a tester build: reload the unpacked extension, paste the invite
  code in Options → Save → Test connection, click through flyer / relative-
  date chat / non-event; then `./scripts/package.sh`, first commit, GitHub
  release (RELEASING.md).

## Gemini 3.8 Flash: full suite on the billed key (2026-09-16)
- Billing enabled on the Gemini key's project; four back-to-back text calls
  returned 200 in ~1 s (paid tier confirmed). Full suite via
  `--provider gemini --model gemini-3.8-flash` (default thinking — the same
  request the proxy builds): **148 cases / 200 events in 10.8 min, $0.78
  list, 0 retries, 0 provider errors**. Results:
  ml/results/gemini-gemini-3.8-flash-20260916T17{2201,2302,2509,2545,3000}.json.
- **Synthetic (synth_v0/v1/v2, 114 cases / 152 events): 100% detection,
  100% every field, 0/12 false alarms** — identical to the teacher.
- **eval_v0 (12 real, human-verified): 18/18 exact.** Latency mean 5.0 s,
  $0.0059/crop.
- **eval_v1 (22 real, claude-labeled): 30/30 detected, 24/30 exact (80%)**
  vs the teacher's 28/30. The six imperfect events, adjudicated:
  1. `05-ig-ecac-dropin-hours` (2 events, tagged `ambiguous`): series start
     = Monday of the week shown vs gold's next weekday. Same judgment call
     the teacher misses; not a Flash defect.
  2. `13-web-hacktx-hero` all-day deadline: Flash `end == start`, gold
     `end: null`. The prompt's deadline rule and all-day rule collide for
     all-day deadlines; `buildCalendarUrl` produces the identical event for
     both (`addDays(end ?? start, 1)`). Scorer/prompt convention, not a
     product miss. Proposed: scorer treats all-day `end == start` as
     equivalent to null (or the prompt says all-day deadlines get null).
  3. `16-gmail-fau-apply-by` title: "Florida Atlantic University Admissions
     Decision Release" vs gold "FAU admission decision" — below the 0.6
     title threshold only because gold abbreviates here while spelling the
     university out in the sibling event. Gold inconsistency; proposed gold
     fix, not a model miss.
  4. `07-ig-sundevil-gbm`: timezone null vs gold `America/Phoenix`
     (venue-implied tz, adjudicated 2026-09-10). **Real miss** (2 h off for
     a Central user).
  5. `09-ig-abb-speedfriending`: "Thursday, September 9th" with 9/9/2026 a
     Wednesday — Flash trusted the numeral (and said so in `notes`), gold
     resolves by post age to Thu 9/10. **Real miss** on an adjudicated
     conflict.
  Net: **2 genuine Flash misses in 48 real events**; the teacher has 0 by the
  same standard (its 2 are the ambiguous case).
- **Overall: 194/200 exact = 97%, 0/12 false alarms; latency mean 4.3 s,
  median 3.4 s, p95 8.7 s, max 43 s; mean $0.0053/crop** (teacher: ~11 s,
  $0.15). Decision stands: ship on the Flash proxy. Neither real miss is
  worth a prompt change before testers; revisit if either pattern recurs in
  captures.
- Adjudication items 2–3 are proposed, not applied (gold and scorer
  unchanged this session).

## Decision: ship on a hosted Gemini Flash proxy; fine-tune stays a side track (2026-09-12)
- Rationale (agreed with user): zero setup for testers, ~$0.005/crop on the
  paid tier (no training on data, no 20/day cap), best accuracy per dollar,
  and the model behind it can change without an extension update. The local
  4B model remains the learning/private-mode track; it is not on the release
  path.
- **`proxy/` (Cloudflare Worker):** same `/extract` contract as the bridge +
  `/me` for the options page + `/health`. Auth = invite token in KV
  (`token:<cc_…>` → {name, limit}), quota = `use:<token>:<UTC day>` counter
  (soft, 2-day TTL), body validation (both images required, ≤6 MB b64 each),
  context sanitized to the 5 prompt fields, request built by
  `extension-gemini/lib/providers/gemini.js` (bundled by wrangler), 503/429
  retried 3×, user-facing error mapping, images never stored/logged.
  `scripts/setup.sh` (KV + secret + deploy), `scripts/invite.sh <name>
  [limit]`. 6 unit tests on the pure logic (35 JS tests total).
- **Local end-to-end via `wrangler dev`:** /health ok; bad code → 403; /me →
  {name, used, limit}; a real eval_v1 crop → correct event (org in title,
  right time/venue), counter 0→1. 110 s latency = free-tier load shedding
  (paid tier ≈ 6 s).
- **Extension:** new `lib/providers/hosted.js` (default provider), invite-code
  + service-URL fields in options, "Connected as <name> — n/limit used
  today" test button, host permission `https://*.workers.dev/*`; API key and
  bridge kept as advanced options. Docs updated (README, PRIVACY, store
  listing, RELEASING).
- ~~Blocked on the user: wrangler login, billing, setup.sh, DEFAULT_PROXY_URL~~
  — all done 2026-09-16; see the section above.

## Phase 2 training started on the DGX Spark (2026-09-11)
- **Training code (read these):** `ml/train/train_lora.py` is the whole
  learning loop in one file — JSONL → Qwen chat messages (system, [crop,
  screen, context], answer); processor + label masking (only the JSON answer
  carries labels; prompt/image tokens are -100); bf16 Qwen3-VL-4B-Instruct
  with LoRA (r=16, α=32, dropout 0.05) on the language model's
  q/k/v/o/gate/up/down projections only (vision tower + merger frozen;
  33.0M trainable of 4.47B = 0.74%); forward → loss/accum → `backward()` →
  clip 1.0 → AdamW → warmup+cosine LR; val loss every N steps; adapter
  checkpoints; `metrics.jsonl`. `ml/train/predict_hf.py` scores an adapter
  on a real set in the harness format; `ml/train/merge_lora.py` merges for
  vLLM/GGUF export; `ml/train/build_dataset.py` builds the JSONL.
- **Spark setup:** `~/cropcal` (uv venv, torch 2.14+cu130 on GB10 sm_121,
  transformers 5.17, peft 0.20); data + `ml/{train,evals}` rsynced to
  `~/cropcal/ml`. Two transformers-5 gotchas fixed: the Qwen3-VL processor
  needs torchvision (video processor import), and the model requires
  `mm_token_type_ids` from the processor for M-RoPE — the collate pads it.
  The image-size budget is a SizeDict (`longest_edge`), not a dict.
- **Smoke run (32 samples, 5 steps, effective batch 8):** loss 0.52 → 0.23,
  val 0.39, checkpoint saved; ~600 tok/s with gradient checkpointing at
  batch 2 (~2.2k tokens/sample: ~1.2k image tokens for crop+screen at native
  resolution, ~0.9k text, ~100 answer).
- **Full run launched in tmux session `train`:** `runs/lora-v1`, 2 epochs over
  3,776 samples, batch 4 × accum 4 = 16 effective, lr 1e-4, eval every 50
  steps, save every 100; log `~/cropcal/ml/runs/lora-v1.log`. ~236 steps/epoch,
  472 total; ETA several hours (bandwidth-bound Spark). Attach with
  `ssh spark -t tmux attach -t train`.
- **Quantization decision:** post-training quantization first (bf16 LoRA →
  merge → Q4_K_M GGUF for Ollama / AWQ for vLLM), measured on the real sets
  as a bf16 vs Q8 vs Q4 ablation; QAT only if PTQ costs >~3 points of exact
  rate or we go below 4-bit for WebGPU. QLoRA ≠ QAT (memory trick, unneeded
  on 128 GB).
- Baseline of the untuned model through the HF pipeline: the first eval_v1
  pass scored 0/30 because the untuned model answers with a bare JSON
  *array* in a code fence (`[ {...} ]`), not `{"events": [...]}`; reproduced
  on the Mac CPU (raw output was otherwise sensible: right date/time/venue,
  org missing from the title). `predict_hf.parse_events` now accepts both
  shapes; the stored `meta.raw` let the baseline be re-scored without
  regenerating: **untuned Qwen3-VL-4B on eval_v1 (HF greedy, no schema
  constraint): F1 80%, exact 8/30 = 27%**, end 55%, title 77%; on eval_v0:
  F1 97%, exact 7/18 = 39%. **Real-set floor for the LoRA: 15/48 = 31%
  exact** (teacher: 46/48 = 96%, the 2 misses on the `ambiguous` ECAC case).
  The Spark rebooted mid-session (offline ~2 h on Tailscale; venv, data,
  results survived); training relaunched 2026-09-11 20:34 CT: step 1 loss
  0.62 at ~470 tok/s, GPU 96% → ETA ~8–10 h for 472 steps.
  `evals/rescore.py` re-scores any stored results file against current gold
  (predictions are stored), so gold fixes never need a model re-run.
- **2026-09-12: the Spark went offline a second time**, within about an hour
  of the training launch (Tailscale "last seen 13 h ago"; the monitor never
  saw step 50). Two drops, both under sustained GPU load (baseline eval,
  then training at 96%), point at a hardware/power/thermal/driver problem on
  the box, not the code. When it returns, a monitor gathers evidence
  (`last -x reboot`, `journalctl -b -1 -p 3`, Xid/NVRM lines, GPU temp and
  power) and the training state. `train_lora.py` gained `--resume`: adapter
  + optimizer state are saved at every `step-N` checkpoint and training
  continues from the latest one (mid-epoch position restored), so the next
  run survives interruptions at the cost of ≤100 steps.
- **2026-09-14, Spark back after ~2 days (powered on 14:31).** Evidence from
  the crashed boot: three boots on record (Sep 9, Sep 11 20:27, Sep 14
  14:31), none with a shutdown entry; `journalctl -b -1 -p 3` empty; zero
  Xid/NVRM/thermal lines; the last journal line is an sshd disconnect at
  20:36:44 — ~2 min after the training launch, right after step 1 (the log
  has exactly one step line). The first outage also began under GPU load
  (baseline eval). Pattern = silent hard stop under sustained GPU load with
  no kernel or driver trace → power delivery or a hardware hang, not
  software. GB10 exposes no power-limit control (`nvidia-smi -pl` N/A).
  **Third drop:** the bounded 8-step smoke (batch 4, with `nvidia-smi dmon`
  logging to `runs/dmon.log`) took the box offline again within minutes
  (SSH lost 14:30, Tailscale offline). Verdict: the Spark cannot sustain GPU
  load in its current state; it is out of the training plan until the
  power path/hardware is checked (three silent stops, zero software trace).
  **Recorded curve (Spark back 2026-09-15, powered on by hand again):** 236 s
  of per-second samples at 96% SM utilization, GPU power flat at ~51 W (peak
  63 W; the GB10 is rated far higher), temperature 72–74 °C (peak 77 °C),
  then the log simply stops mid-second with no spike, no climb, no error.
  The GPU was neither hot nor drawing unusual power when the box died. That
  rules out GPU thermal/power throttling and points squarely at external
  power (adapter, outlet/strip, or the unit's power input) or a system-level
  hang — a hardware/support issue. Two training steps completed before the
  drop. Training alternatives stand: rented H100 (~2–3 h, script unchanged)
  or the Mac overnight at reduced settings.

## Phase 2 data: eval_v1 (real) + train_v1 (3,977 synthetic cases) (2026-09-10)
- **eval_v1 = 22 real capture pairs / 30 events** from the user's Instagram,
  Gmail, Canvas, and hacktx.com screenshots (Canvas headline fragments, "or"
  alternative dates, ECAC recurring drop-in hours, dotted "10.24 – 10.25 ·
  Apply by 9.11", visit-day lists sharing one time, Luma badge widget,
  "When:/Where:" blocks, a moved event, a flyer whose weekday contradicts its
  date). Labeled by Claude from the images (`verification.status:
  claude-labeled`), browser chrome stripped from screens, then Opus ran as a
  second opinion: 30/30 detected, 100% after four gold fixes (ASU venue →
  America/Phoenix; weekday/date conflict resolved by post age, not the
  numeral; campus visit location = the university; shorter session title).
  One judgment call kept and tagged `ambiguous` (series start for weekly
  drop-in hours). Real captures now total 34 cases / 48 events across
  eval_v0 + eval_v1 = the only test split that counts; never trained on
  (`train/build_dataset.py` refuses them).
- **train_v1 generator** (`ml/synth/train_gen.py` + `styles.py`,
  `templates_social.py`, `templates_mail.py`, `render.py`): Playwright renders
  each page once at a realistic viewport/DPR (MacBook 2x, Windows 1.25x,
  1080p 1x…), crops the jittered drag rectangle from that same capture, caps
  the crop at 1400 px and downsizes the screen to 1400 px — exactly what
  background.js sends. 19 scenario kinds: Instagram feed posts with 8 flyer
  designs (poster+banner, bullets, two-column, big-date, pill-location,
  plain card, minimal, retro), recruitment/schedule boards, stories, Gmail
  with 11 body layouts (admissions marketing, office-hours bullets, Luma
  widget, When/Where, concert listing, apply-by headline, visit days, moved
  notice, session blocks, "or" alternatives, digest, tz confirmation),
  Canvas announcements + to-do rows, event-site hero, iMessage/GroupMe/
  Discord/Slack, and 19% non-events. Every case randomizes now (2025-08 →
  2027-05), user tz (Central for anything at a Texas venue), fonts, palettes,
  phrasing (14 date styles incl. "Sept. 13th, Sunday", "10.24", "17 Sep
  2026"; 7 time styles incl. "9-11:30AM", "12 – 1 p.m.", "6:00–8:00 PM CT").
  Gold is exact by construction; tz gold only when a label is rendered;
  deadlines end==start; non-deadline flyers never draw deadline kinds.
  0.03 s/case with 6 workers (4,000 cases in 2 min); 3 render errors
  skipped.
- **train_v1 = 3,997 cases / 4,034 events, ~530 MB**: 3,776 train / 221 val
  (hash split), 18% non-events, ~430 multi-event, ~510 deadlines, ~300 with a
  tz label, ~250 past-dated with an age cue, ~250 relative-date chats.
  `data/train_v1/{train,val}.jsonl` + `dataset_info.json` in LLaMA-Factory
  sharegpt multimodal format (system prompt + `<image><image>` + context →
  compact JSON), built by `uv run python -m train.build_dataset`.
- Two policy notes learned from eval_v1 adjudication and baked into the
  generator: a weekday/date conflict is NOT a fixed "trust the date" rule
  (disabled in generation), and venue geography can imply a timezone (so
  Texas-venue cases are generated for a Central user only).
- **Label-quality check with the teacher** (Opus via bridge, 24 generated
  cases, ~$3.70 list): start date/time, end, all-day, timezone, recurrence
  all 100% agreement. Disagreements exposed two generator bugs — visit-day
  emails could mark two groups as the crop target while gold listed both,
  and loose vertical jitter let a neighbouring bullet into the crop so the
  teacher rightly found a second event — plus one policy gap (visit-day
  location = the university, as adjudicated on eval_v1). Fixed (single
  target group; `jitter="tight"` for single-line targets in bullets/digest/
  listing/sessions/canvas/chat), regenerated, and 12 targeted cases from the
  fixed layouts re-ran at 12/12 exact agreement. Remaining teacher
  disagreements were teacher wobble (once omitted the org from a title,
  once missed a venue in the crop).
- **Difficulty check**: Qwen3-VL 4B zero-shot on 60 generated cases scores
  like it does on the real sets — exact 45% (29/65), 8/8 false alarms on
  non-event crops, F1 89%, title 79%, end 75% — so the synthetic data is not
  trivially easy; the student's failure modes reproduce on it.
- Next: LoRA on Qwen3-VL-4B-Instruct (Spark) with LLaMA-Factory reading
  `data/train_v1/dataset_info.json`; evaluate on eval_v0 + eval_v1 (34 real
  cases / 48 events) against the zero-shot floor of 51% exact / 12 of 12
  false alarms.

## Phase 1 student floor: local 4B VLMs zero-shot through the harness (2026-09-10)
- Harness gained `--provider ollama --model <tag> [--think on|off] [--num-ctx]
  [--num-predict]`: sends the main extension's prompt/schema/context verbatim
  (`evals/prompt_export.mjs`) to a local Ollama model with JSON-schema
  structured output. `evals/compare.py` prints provider × set tables plus two
  product metrics: **exact** (gold events returned with all 8 fields right,
  i.e. no edits needed) and **false alarms** (non-event crops that produced an
  event), with a failure breakdown and examples.
- Ollama quirk (0.33.3, qwen3-vl:4b): with `think=false` + a format grammar the
  JSON lands in `message.thinking` and `content` is empty; the provider falls
  back to that channel (`meta.channel`). With thinking ON the model burns
  2–3k tokens, takes 40–56s, and gets *worse* (converted ET→CT on top of
  emitting the tz). Thinking OFF: ~8s/case on the M4 Pro, prompt ≈3.1k tokens.
- **Qwen3-VL 4B (Q4, zero-shot, thinking off) vs Opus teacher, 126 cases /
  170 events:** recall 169/170; precision hurt by hallucinations: **12/12
  non-event crops produced a fake event** (teacher 0/12). Field accuracy on
  matched events: start_date 92–100%, start_time 88–98%, all_day 89–100%,
  timezone 89–100%, recurrence 89–100%, title 80–89%, location 65–100%,
  **end 71–82%**. **Exact (no-edit) rate 51% overall (87/170), 28% on the
  real captures** vs 100% for Opus.
- Failure taxonomy (this is the fine-tuning target list):
  1. No "empty" behaviour: never returns `events: []` → policy/data.
  2. Deadline point-in-time rule inverted (end null on deadlines, end==start
     on timed events) → policy.
  3. Location discipline ("Online", "Canvas", routing text copied in) → policy.
  4. Org/host not pulled from the screen into the title (needs_context) →
     context use.
  5. Emits the user's own tz instead of null; invents RRULE UNTIL → policy.
  6. Genuine perception/arithmetic: "6:45 PM" → 06:45; "this friday" → Sat +
     all-day; Exam 3 with no date emitted as an event.
  Most failures are 1–5 (learnable from teacher labels); 6 is where the
  "distill perception, resolve dates in code" schema split would help.
- **Gemma 3 4B (Q4, zero-shot) is far worse:** exact 11% (19/170), 42
  hallucinations, 12/12 false alarms, start_time 32–51%, end 35–49%. Two
  extra failure modes Qwen doesn't have: it ignores the crop/context split
  and emits every event visible in the *screen* image (a one-event story
  crop → 4–7 events), and it mangles 12-hour times ("2:30 PM" → 23:30,
  "11:59 PM" → 11:59, ranges ending before they start). ~7s/case.
- Verdict for Phase 2: Qwen3-VL 4B is the student to fine-tune (Gemma 3 4B
  would need to learn perception, Qwen mostly needs policy). Zero-shot floor
  to beat: **51% exact / 12 of 12 false alarms**; teacher ceiling 100% / 0.
  Latency on the M4 Pro is already product-viable (~8s, 2 images, Q4).
- Local runs: `ollama pull qwen3-vl:4b gemma3:4b` (3.3 GB each), then e.g.
  `./scripts/eval.sh --provider ollama --model qwen3-vl:4b --think off
  --set synth_v2`; `uv run python -m evals.compare` for the table.

## Gemini experiment: isolated build done, eval blocked by free-tier quota (2026-09-10)
- Built `extension-gemini/` as a fully isolated copy (own `lib/schema.js`
  prompt, `lib/providers/gemini.js` with OpenAPI-style responseSchema
  converted from the shared EVENT_SCHEMA, Gemini-only options page with the
  free-tier data-use note, own manifest/host permission/teal icon). `extension/`
  untouched. `./scripts/package.sh extension-gemini` builds its zip.
- Harness: `--provider gemini --model <id> [--thinking] [--only <id>]` sends
  byte-for-byte what the Gemini extension builds (via
  `evals/gemini_request.mjs`), with 429/503 backoff, token + list-cost meta,
  and results now saved after every case (`partial: true` until the run ends).
  Key read from gitignored `ml/.env` (GEMINI_API_KEY). 29 JS tests pass.
- Docs (verified 2026-09-10): gemini-2.5-flash still served, but the current
  Flash is `gemini-3.8-flash` (free tier; paid $0.75/$3.75 per 1M through
  2026, doubling in 2027). Free tier: "content used to improve our products";
  paid: not. Rate limits are no longer published — only visible in AI Studio.
- Single-case probe on 3.8 Flash: correct extraction (synth-03: org in title,
  America/New_York, Zoom, end from stated duration), 5.9s, 3110 prompt /
  151 output / 422 thinking tokens ≈ $0.005 list. But 4 of 5 attempts
  returned 503 "high demand".
- **Blocker:** the 429 body names the quota:
  `GenerateRequestsPerDayPerProjectPerModel-FreeTier = 20` for
  gemini-3.8-flash. Probes + 2 eval cases exhausted today's 20. A 126-case
  suite is impossible on the free tier for this model (≈7 days at 20/day);
  full run aborted, no results saved. Quota resets daily (midnight Pacific).
  Product implication: a free-tier 3.8 Flash key = 20 crops/day per user —
  fine for personal use, useless for evals/iteration.
- Options (user decision pending): (a) enable billing on the AI Studio
  project → Tier 1 limits; whole suite ≈ $0.60 list and paid tier is not
  used for training; (b) run a curated 20-case diagnostic subset per day on
  free tier; (c) another free Flash model with a bigger daily bucket
  (quotas are per model; check aistudio.google.com/rate-limit).

## Release prep + final accuracy check (2026-09-10)
- **Distribution decision:** tester release = GitHub release zip + "Load unpacked"
  (no review, developer-mode nag), then Chrome Web Store as *Unlisted* (one-time
  $5, 1–3 day review, one-click install + auto-update). Self-hosted .crx is not
  installable on consumer Chrome. Procedure in RELEASING.md; listing copy,
  permission justifications, and asset specs in store/listing.md; PRIVACY.md is
  the policy the store requires (screenshots go only to the configured provider,
  nothing to us). `./scripts/package.sh` builds dist/cropcal-<version>.zip
  (validates manifest, runs tests). README.md written for testers.
- **Public users bring their own Anthropic key** (bridge stays a developer
  option). DEFAULT_PROVIDER flipped bridge→api; first install opens the options
  page; with no key the toolbar click opens options instead of failing. The
  localhost bridge origins moved from host_permissions to
  optional_host_permissions and are requested only when Bridge is saved/tested
  in options, so the public install prompt never mentions localhost.
  NOTE: after reloading the extension, re-save Options once (Bridge selected) to
  grant the localhost permission, or the bridge shows "not reachable".
- **Bugs fixed in the review:**
  1. The "Extracting event…" toast was drawn before captureVisibleTab ran, so it
     appeared inside the screen-context image sent to the model (visible in the
     09-10 Bloomberg capture) and could overlap a crop near the bottom center.
     Background now captures first, then messages the tab (`cropcal-progress`)
     to show the spinner.
  2. Haiku 4.5 rejects `output_config.effort` (400); effort is now only sent for
     models that support it. Request construction extracted to a pure
     `buildRequest()` with 4 unit tests (25 JS tests total).
  3. MV3 service-worker idle kill during slow extractions: a keepalive
     (`chrome.runtime.getPlatformInfo` every 20s) runs while the provider call
     is in flight.
  4. Icons: none existed (Chrome showed the puzzle piece; the store requires
     128px). Rendered icons/icon{16,32,48,128}.png via headless Chrome.
  5. bridge.sh header said default port 8765; it is 48765.
- **Accuracy: full live regression on Opus via the bridge, all sets 100%.**
  eval_v0 (12 real cases / 18 events, rerun after promoting case 12), synth_v0
  (11 / 9), synth_v1 (62 / 96), synth_v2 (41 / 47): detection 100%, every
  scored field 100%, title similarity 0.97–0.99, mean latency 9.6–12.1s, mean
  list cost $0.15–0.17/crop. Results: ml/results/bridge-20260910T11{2533,2802,3743,4442,4847}.json.
- **Real capture verified + promoted:** 09-10 Instagram story (Bloomberg
  "Day in the Life" panel) — crop held only date/time/room; title, org, and
  year (Oct 9 2026 is a Friday) came from the screen. Every field checked
  against the images → eval_v0 case 12 (tags real, needs_context).
- **synth_v2 shipped: 41 cases / 47 events, 100% first pass, no adjudication
  needed.** `ml/synth/scale2.py` adds 10 templates (Canvas to-do, syllabus and
  sports tables, Slack, Outlook/Teams invite, X post, ticket page, Reminders,
  dark-mode Gmail, terminal log). Policy probes all resolved as intended: time
  "TBA" with a date → all-day; undated rows ("Final · TBA", "Call grandma")
  skipped; "(UTC-05:00) Central" for a Chicago user → timezone null; Pacific
  variant → America/Los_Angeles; Canvas crop without course header pulls the
  course from the screen; BYDAY=MO,WE and UNTIL=20261204T235959 exact; 9 PM–1 AM
  → next-day end; Fall Break → all-day with inclusive end; 24h "19:30", "noon",
  "by 5pm Friday" deadlines, order-confirmation / past-tense news / terminal log
  non-events all correct.
- Scorer: recurrence now compared as a normalized RRULE (key order, BYDAY set,
  UNTIL date-only, INTERVAL=1/WKST dropped) instead of raw string equality;
  4 new tests (15 Python tests total).
- Totals: 125 cases / 170 gold events across eval_v0 (12), synth_v0, synth_v1,
  synth_v2. Teacher (Opus via bridge) at 100% on every set.
- Not verifiable from a session: the browser tool cannot open chrome-extension://
  pages, so the reload + click-through (Options → Save → Test connection; one
  flyer, one chat, one non-event) is a manual step before cutting the release.
- Repo has no commits yet; the release needs a first commit + `gh repo create`
  (commands in RELEASING.md). Not done — user's call.

## Deadline point-in-time policy (first real-world UX fix from live use)
- User's LDOS crop: model output was correct (end=null) but the extension's
  1-hour default rendered a "5–6pm" block for a 5pm deadline — confusing
  (someone might hold out until 6 to submit).
- Policy: a timed deadline/due-time/cutoff is a point in time → model sets
  end == start (new prompt rule in schema.js); buildCalendarUrl passes equal
  dates through, so Google Calendar shows "5pm" with no block. The 1-hour
  default remains for genuinely open-ended events. All-day deadlines
  (no time stated) stay all-day.
- Rolled through the whole contract: prompt rule, unit test (zero-duration
  URL), synth generators (27 timed-deadline golds now end=start; synth_v1
  regenerated, same seed), eval_v0 gold amended (2 timed deadline events,
  noted in verification), LDOS capture promoted as eval_v0 case 11.
- promote.py gained --only <id> (a bare run promoted 10 unverified captures
  as "verified"; moved to data/unpromoted_holding/, review before promoting).
- Regression: LDOS crop re-run through bridge → end == start, 100% fields.
- Full-suite iteration 1 (84 cases / 122 events): detection 100% everywhere,
  two single-field misses, both adjudicated as collateral of the new rules:
  (1) Canvas "Videos: Lecture 0" due item — model now correctly end==start,
  gold was stale (keyword script missed a due item without "due" in title) →
  gold fixed; (2) "Zoom"-venue flyer — location rule overshot, model nulled a
  stated platform venue → prompt amended (named platform stated as venue DOES
  count as location). Iteration 2 full re-run in progress.
- Eval runs no longer pollute captures/: eval provider sends no_log, bridge
  skips logCapture (verified). The 85 eval-run capture dirs from today moved
  to data/captures_eval_runs/.
- Iteration 2: end 100% everywhere; 3 location flips on previously-perfect
  sets, all adjudicated as gold updates consistent with the amended rule:
  synth-03 webinar email states "a Zoom link will follow" → gold location
  "Zoom" (fixed in generate.py too); CS314 exam gold locations relabeled to
  plain room lists ("WEL 2.224; WEL 1.316"), unique-number section routing
  moved to description — location holds the place. Both re-verified via
  bridge → 100%.
- run.py now stores raw prediction events in results JSON (adjudication no
  longer requires a re-run to see what the model said).
- FINAL: 84 cases / 122 gold events, 100% detection and 100% on every scored
  field across eval_v0 (11), synth_v0 (11), synth_v1 (62). ~$0.15/crop list,
  mean latency 10.6-14.6s per set.

## synth_v1 shipped: 62 cases / 96 events, two loop iterations to 100%
- `ml/synth/scale.py`: parameterized engine (seeded RNG, reproducible) — org
  recruitment timelines, flyers, chats (iMessage/GroupMe/Discord), internship
  emails (OA deadline + interview), digests, TZ invites, job postings,
  overnight hackathons, non-events. Content patterns seeded from real
  recruiting-timeline research. Tags in case.json: needs_context, multi_event,
  relative_date, timezone, deadline, overnight_range, nonevent.
- NEW axis per user: context-dependent crops (timeline steps with no org; bare
  date banners with the title only in the screen) — all passed.
- Loop iteration 1 (batch 2): F1 97.9%, location 84.8%, end 93.5%. Adjudicated:
  1 real model miss (stated duration not applied), 1 product-judgment gap
  (hackathon split into kickoff+closing), 1 generator gold bug (hackathon venue
  missing), plus location noise ("video call", office city on deadlines).
- Fixes: 3 prompt rules in schema.js (compute end from stated durations; one
  spanning event for named multi-part events; location discipline) + gold fix.
- Iteration 2: synth_v1 batch 100% all fields; eval_v0 regression 100%.
- Totals: 83 cases / 121 gold events across eval_v0, synth_v0, synth_v1.
  Teacher (opus via bridge) at 100% on all sets. ~$0.15/crop list, ~11-15s.
- NOTE: extension users get the new prompt only after reloading the extension;
  bridge users after restarting the bridge.

## Observability: local dashboard
- `ml/report.html` (open once, auto-refreshes every 10s): run-history table,
  every case in every set with crop thumbnail + gold + latest verdict badge
  (green all-fields / red per-field failures / hallucinated / missed).
  Regenerated automatically by `evals.run` and `synth.generate`
  (`uv run python -m evals.report` to rebuild manually).

## Synthetic pipeline + self-eval loop live
- `ml/synth/generate.py`: renders realistic sources (iMessage, GroupMe, Gmail,
  Discord, Instagram flyers, event pages, articles) as HTML → headless-Chrome
  screenshots. Gold is exact by construction (derived from generation params);
  frozen fake now = Tue 2026-09-01 12:00 America/Chicago so relative dates are
  deterministic. `synth_v0` = 11 cases: relative dates, explicit TZ (ET),
  RRULE recurrence, multi-event digest, year-missing-past, 3 non-events.
- Self-eval loop ran twice: iter 1 = 9/9 events detected, 0 hallucinations on
  non-events, 2 field misses; both were SCORER bugs (model answers were more
  complete than gold). Fixed with `field_sim` (fuzzy ∨ gold-token containment —
  asymmetric: extra correct detail free, missing gold content penalized).
  Iter 2 = 100% all fields on synth_v0 AND eval_v0. 11 unit tests.
- Loop commands: `uv run python -m synth.generate` (from ml/) to add cases;
  `./scripts/eval.sh --provider bridge --set synth_v0` to self-evaluate.
- Human spot-check duty: audit synth gold labels (generator-authored) and any
  future "scorer bug" judgment calls; real captures remain the gold standard.

## Phase 1 started: eval harness live, eval_v0 frozen
- First real test session: 10 crops (Instagram flyers/stories, Canvas dashboard,
  CS314 syllabus), 16 events, ALL fields verified correct by user. Context
  mechanism proven (times/locations pulled from captions outside the crop;
  undated Exam 3 correctly omitted). Latency 10–19s via bridge.
- `ml/` (uv, stdlib-only): `evals/promote.py` (verified captures → frozen gold),
  `evals/score.py` (1:1 event matching + per-field accuracy; 9 unit tests),
  `evals/run.py` (providers: cached, bridge; reports detection P/R/F1, per-field
  accuracy, latency, cost). Run via `./scripts/eval.sh [--provider bridge]`.
- `eval_v0` = those 10 cases / 16 events. Cached run: 100% (sanity). Live bridge
  rerun: 100% fields, title similarity 0.980 (wording drift, above threshold).
- Bridge now reports `cost_usd` (list price from claude -p envelope) in meta —
  restart the bridge to pick it up; it feeds the harness's cost column.
- Eval-set gaps to collect next: Gmail, GroupMe/Discord, explicit-timezone
  ("7pm ET"), recurrence ("every Monday"), and non-event crops (gold = []).

## Latest: two-image context extraction + year policy
- First real-browser crop (Instagram flyer, Guadaloop fall '26 recruitment) exposed
  the year bug: crop said only "08/23", old "always next future occurrence" rule
  produced 2027. Fix: extension now sends BOTH the tight crop (extract from this)
  and a downscaled full-screen capture (context only — year/org/venue resolution).
  Regression-tested on the exact failing crop: now returns 2026 with high
  confidence, org attributed in title, context events correctly NOT extracted.
- Year policy (agreed with user): visible context wins; with no context, default
  to next future occurrence (confidence low + note); if the final date is already
  past, the toast warns "double-check the year" (`isPastEvent` in calendar-url.js).
- Planned next UX (discussed, not built): single in-page review card when
  confidence is low or multiple events found (checkbox list beats N tabs); user
  corrections there become labeled fine-tuning data. NOT a multi-step popup series.

## Done
- SPEC.md written: product decisions, event JSON schema v1, phase plan.
- Phase 0 extension built: toolbar/shortcut → drag-crop overlay → captureVisibleTab
  → crop at DPR → extraction provider → prefilled Google Calendar tab(s) → toast.
- Two swappable extraction providers:
  - **bridge (default):** `bridge/server.mjs` on 127.0.0.1:48765 shells out to
    headless `claude -p --model opus` — covered by the Max subscription, no API key.
    Started with `./scripts/bridge.sh`. Port 8765 was taken by another local service
    ("PharmaSynapse"), hence 48765.
  - **api:** direct Anthropic API (`claude-opus-5`, structured outputs) for when a
    key exists. Model/effort configurable in options.
- **Live-tested end to end (minus the browser step):** synthetic flyer PNG →
  bridge `/extract` → correct event JSON (year inferred from weekday match:
  Sep 18, 2026 is a Friday) in ~15s → valid prefilled calendar URL.
- 19 unit tests passing (`pnpm test`): calendar-url/date logic + robust JSON parsing.

## Dataset collection (opt-in)
- `BRIDGE_LOG=1 ./scripts/bridge.sh` saves each capture to `ml/data/captures/<ts>/`
  (crop.png, screen.png, record.json with context + model output). Off by default;
  gitignored. These records are teacher labels — unverified until reviewed — and
  are the seed of the Phase 1 dataset/eval set.

## Next
1. **User:** reload the unpacked extension, re-save Options (Bridge) once, and
   click through: flyer, chat with a relative date, non-event. Then
   `./scripts/package.sh`, first commit, GitHub release (RELEASING.md).
2. Decide the Gemini eval path (billing vs 20/day subset) — see the Gemini
   section; the isolated build is ready either way.
3. Phase 2 prep: scale synth generation to low thousands of cases (scale.py /
   scale2.py are seeded; new seeds = new cases), teacher-label real captures,
   freeze the real-capture test split. Then QLoRA Qwen3-VL 4B on the Spark
   against the 51%-exact floor. Consider the "perception fields + code
   resolves dates" schema split (versioned) if arithmetic misses persist.

## Known gaps / deliberate v0 cuts
- Bridge latency ~10–30s per crop (spawns a full claude -p run); acceptable for
  dev, not the ship experience. Bridge is personal-use only — shipped users get
  bring-your-own-key or (the goal) the local model.
- Bridge binds to localhost but is unauthenticated — any local process could use it.
- Testers pay per crop with their own key (~$0.15–0.30 on Opus 5); no hosted backend.
- No OAuth calendar insert (template link only, by design).
- Capture limited to the visible viewport; no chrome:// pages, Web Store, or PDFs.
- Working name "CropCal" not final (icons done).
