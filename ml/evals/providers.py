"""Prediction providers the eval runner can score.

- cached: the model output recorded at capture time (sanity check — scores 100%
  on a set whose gold was seeded from those same outputs and fully verified).
- bridge: live call through the local CropCal bridge (claude -p). Use after
  prompt/model changes to regression-test against the frozen gold.
- gemini: direct Gemini API call using the request that extension-gemini/
  builds (via evals/gemini_request.mjs), so the isolated Gemini extension and
  its prompt are what gets scored. Needs GEMINI_API_KEY (ml/.env or env).
- ollama: a local open-weights VLM served by Ollama (127.0.0.1:11434), sent the
  main extension's prompt/schema/context verbatim (evals/prompt_export.mjs)
  with Ollama's JSON-schema structured output. This is the Phase 1 "student
  floor": what a small model does zero-shot before any fine-tuning.

Adding a contender (OCR baseline, student VLM) = one function returning
({"events": [...]}, meta_dict).
"""
from __future__ import annotations

import base64
import json
import random
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

GEMINI_REQUEST_MJS = Path(__file__).resolve().parent / "gemini_request.mjs"
PROMPT_EXPORT_MJS = Path(__file__).resolve().parent / "prompt_export.mjs"

# Paid-tier list prices per 1M tokens (input, output incl. thinking), from
# ai.google.dev/gemini-api/docs/pricing on 2026-09-10. Free tier bills $0 but
# this is the honest cost column, comparable to the Anthropic list price.
GEMINI_PRICES = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.5-flash-lite": (0.30, 2.50),
}


def predict(name: str, case_dir: Path, case: dict, bridge_url: str,
            gemini: dict | None = None, ollama: dict | None = None) -> tuple[dict, dict]:
    if name == "cached":
        rp = case["recorded_prediction"]
        return {"events": rp["events"]}, rp.get("meta", {})
    if name == "bridge":
        return _bridge(case_dir, case, bridge_url)
    if name == "gemini":
        return _gemini(case_dir, case, gemini or {})
    if name == "ollama":
        return _ollama(case_dir, case, ollama or {})
    raise ValueError(f"unknown provider: {name}")


def _bridge(case_dir: Path, case: dict, bridge_url: str) -> tuple[dict, dict]:
    payload: dict = {
        "image": base64.b64encode((case_dir / "crop.png").read_bytes()).decode(),
        "context": case["context"],
        "no_log": True,
    }
    screen = case_dir / "screen.png"
    if screen.exists():
        payload["screen"] = base64.b64encode(screen.read_bytes()).decode()

    req = urllib.request.Request(
        f"{bridge_url.rstrip('/')}/extract",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=180) as res:
        data = json.load(res)
    meta = data.get("meta", {})
    meta["wall_ms"] = round((time.monotonic() - t0) * 1000)
    return {"events": data["events"]}, meta


def _images(case_dir: Path) -> dict:
    images = {"crop": base64.b64encode((case_dir / "crop.png").read_bytes()).decode()}
    screen = case_dir / "screen.png"
    if screen.exists():
        images["screen"] = base64.b64encode(screen.read_bytes()).decode()
    return images


def _extract_json_events(text: str) -> list[dict]:
    """Mirror of extension/lib/parse.js: bare, fenced, or prose-wrapped JSON."""
    candidates = [text.strip()]
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        candidates.append(fence.group(1))
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last > first:
        candidates.append(text[first:last + 1])
    for c in candidates:
        try:
            parsed = json.loads(c)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("events"), list):
            return parsed["events"]
    raise ValueError("unparseable model output: " + text[:200])


def _gemini(case_dir: Path, case: dict, opts: dict) -> tuple[dict, dict]:
    api_key = opts.get("api_key")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY missing — put it in ml/.env or the environment")
    model = opts.get("model", "gemini-3.8-flash")
    settings = {"apiKey": api_key, "model": model, "thinking": opts.get("thinking", "")}
    built = subprocess.run(
        ["node", str(GEMINI_REQUEST_MJS)],
        input=json.dumps({"images": _images(case_dir), "ctx": case["context"], "settings": settings}),
        capture_output=True, text=True, check=True,
    )
    req = json.loads(built.stdout)

    data = None
    retries = 0
    waited_s = 0.0
    t0 = time.monotonic()
    # Free-tier 3.x models shed load with 503 "high demand" in bursts (4 of 5
    # attempts during the 2026-09-10 probe), so be patient rather than clever.
    for attempt in range(40):
        r = urllib.request.Request(req["url"], data=json.dumps(req["body"]).encode(),
                                   headers=req["headers"])
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(r, timeout=180) as res:
                data = json.load(res)
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            transient = e.code in (429, 500, 502, 503, 504)
            if transient and attempt < 39:
                m = re.search(r'"retryDelay":\s*"(\d+)s"', body)
                if m:
                    delay = int(m.group(1)) + 1
                elif e.code == 429:
                    delay = 20
                else:
                    delay = min(30.0, 4 * 1.4 ** min(attempt, 6)) + random.uniform(0, 3)
                print(f"    gemini HTTP {e.code}, retry {attempt + 1} in {delay:.0f}s", flush=True)
                time.sleep(delay)
                retries += 1
                waited_s += delay
                continue
            raise RuntimeError(f"gemini HTTP {e.code}: {body[:400]}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 39:
                print(f"    gemini network error ({e}), retry {attempt + 1} in 10s", flush=True)
                time.sleep(10)
                retries += 1
                waited_s += 10
                continue
            raise
    wall_ms = round((time.monotonic() - t0) * 1000)

    usage = data.get("usageMetadata", {})
    out_tokens = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
    price_in, price_out = GEMINI_PRICES.get(model, (0.0, 0.0))
    meta = {
        "provider": "gemini",
        "model": data.get("modelVersion", model),
        "duration_api_ms": wall_ms,
        "prompt_tokens": usage.get("promptTokenCount"),
        "output_tokens": usage.get("candidatesTokenCount"),
        "thoughts_tokens": usage.get("thoughtsTokenCount", 0),
        "cost_usd": round((usage.get("promptTokenCount", 0) * price_in + out_tokens * price_out) / 1e6, 6),
        "retries": retries,
        "retry_wait_s": round(waited_s),
    }
    cand = (data.get("candidates") or [{}])[0]
    meta["finish_reason"] = cand.get("finishReason")
    blocked = (data.get("promptFeedback") or {}).get("blockReason")
    text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", [])
                   if not p.get("thought"))
    if blocked or not text:
        meta["error"] = f"blocked:{blocked}" if blocked else f"empty:{cand.get('finishReason')}"
        print(f"    gemini returned nothing ({meta['error']})")
        return {"events": []}, meta
    try:
        events = _extract_json_events(text)
    except ValueError as err:
        meta["error"] = str(err)
        print(f"    {err}")
        return {"events": []}, meta
    return {"events": events}, meta


def export_prompt(ctx: dict) -> dict:
    out = subprocess.run(["node", str(PROMPT_EXPORT_MJS)], input=json.dumps({"ctx": ctx}),
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def _ollama(case_dir: Path, case: dict, opts: dict) -> tuple[dict, dict]:
    model = opts.get("model") or "qwen3-vl:4b"
    base = (opts.get("url") or "http://127.0.0.1:11434").rstrip("/")
    prompt = export_prompt(case["context"])
    images = _images(case_dir)
    payload = {
        "model": model,
        "stream": False,
        "format": prompt["schema"],
        "keep_alive": "30m",
        "options": {"temperature": 0, "num_ctx": int(opts.get("num_ctx") or 8192),
                    "num_predict": int(opts.get("num_predict") or 2048)},
        "messages": [
            {"role": "system", "content": prompt["system_prompt"]},
            {"role": "user", "content": prompt["context_text"],
             "images": [images["crop"]] + ([images["screen"]] if "screen" in images else [])},
        ],
    }
    if opts.get("think") is not None:
        payload["think"] = bool(opts["think"])
    req = urllib.request.Request(f"{base}/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=600) as res:
            data = json.load(res)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"ollama HTTP {e.code}: {body[:300]}") from None
    except urllib.error.URLError as e:
        raise SystemExit(f"ollama not reachable at {base} ({e.reason}) — is `ollama serve` running?")
    wall_ms = round((time.monotonic() - t0) * 1000)

    meta = {
        "provider": "ollama",
        "model": model,
        "duration_api_ms": round(data.get("total_duration", 0) / 1e6) or wall_ms,
        "wall_ms": wall_ms,
        "prompt_tokens": data.get("prompt_eval_count"),
        "output_tokens": data.get("eval_count"),
        "eval_ms": round(data.get("eval_duration", 0) / 1e6),
        "cost_usd": 0.0,
        "done_reason": data.get("done_reason"),
    }
    msg = data.get("message") or {}
    text = msg.get("content", "")
    thinking = msg.get("thinking") or ""
    meta["thinking_chars"] = len(thinking)
    meta["channel"] = "content"
    # Ollama's Qwen3-VL template routes the whole reply into `thinking` when
    # think=false is combined with a format grammar (observed 2026-09-10), so
    # fall back to that channel when it holds the JSON.
    if not text.strip() and "{" in thinking:
        text = thinking
        meta["channel"] = "thinking"
    if not text:
        meta["error"] = f"empty:{data.get('done_reason')}"
        print(f"    ollama returned nothing ({meta['error']})", flush=True)
        return {"events": []}, meta
    try:
        events = _extract_json_events(text)
    except ValueError as err:
        meta["error"] = str(err)
        print(f"    {err}", flush=True)
        return {"events": []}, meta
    # Constrained decoding guarantees shape, not sanity: drop entries with no
    # parseable start so the scorer sees a miss instead of crashing.
    events = [e for e in events if isinstance(e, dict) and isinstance(e.get("start"), str)]
    return {"events": events}, meta
