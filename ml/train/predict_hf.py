"""Score a fine-tuned adapter (or merged model) on an eval set, on the GPU box.

Runs greedy generation with the exact production prompt, parses the JSON,
and writes ml/results/<label>-<timestamp>.json in the harness format so
`uv run python -m evals.compare` shows it next to the teacher and the
zero-shot student.

Usage (on the Spark, from ~/cropcal/ml):
  python -m train.predict_hf --adapter runs/lora-v1/final --set eval_v1 --label hf:lora-v1
  python -m train.predict_hf --set eval_v1 --label hf:qwen3-vl-4b-base      # no adapter = zero-shot base
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import torch
from PIL import Image

from evals.score import FIELD_NAMES, aggregate, score_case
from train.train_lora import MODEL_ID, make_processor

ML_DIR = Path(__file__).resolve().parents[1]


def context_text(ctx: dict) -> str:
    """Mirror of extension/lib/schema.js buildContextText."""
    lines = [f"Current date/time: {ctx['now']} ({ctx['weekday']})", f"User timezone: {ctx['timezone']}"]
    if ctx.get("pageTitle"):
        lines.append(f"Captured from page: {ctx['pageTitle']}")
    if ctx.get("pageUrl"):
        lines.append(f"Page URL: {ctx['pageUrl']}")
    lines.append("Extract the calendar event(s) from this image.")
    return "\n".join(lines)


def system_prompt(data_dir: Path) -> str:
    """The prompt is identical in every training record; read it from the first."""
    with open(data_dir / "train.jsonl") as f:
        return json.loads(f.readline())["messages"][0]["content"]


def parse_events(text: str) -> list[dict]:
    """Accepts {"events": [...]} (what we train), a bare [...] list (what the
    untuned model tends to emit), fenced or wrapped in prose."""
    cands = [text.strip()]
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        cands.append(m.group(1))
    for open_, close in (("{", "}"), ("[", "]")):
        a, b = text.find(open_), text.rfind(close)
        if a != -1 and b > a:
            cands.append(text[a:b + 1])
    for c in cands:
        try:
            d = json.loads(c)
        except json.JSONDecodeError:
            continue
        events = d.get("events") if isinstance(d, dict) else d
        if isinstance(events, list):
            return [e for e in events if isinstance(e, dict) and isinstance(e.get("start"), str)]
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="")
    ap.add_argument("--merged", default="", help="path to a merged HF checkpoint instead of base+adapter")
    ap.add_argument("--set", dest="eval_set", default="eval_v1")
    ap.add_argument("--data", default="data/train_v1", help="where to read the system prompt from")
    ap.add_argument("--label", default="hf:model")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-new-tokens", type=int, default=768)
    args = ap.parse_args()

    from transformers import AutoModelForImageTextToText

    processor = make_processor(2_000_000, 65_536)
    model = AutoModelForImageTextToText.from_pretrained(args.merged or MODEL_ID, dtype=torch.bfloat16,
                                                        attn_implementation="sdpa").cuda().eval()
    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter).eval()
    sys_prompt = system_prompt(ML_DIR / args.data)

    set_dir = ML_DIR / "data" / args.eval_set
    case_dirs = sorted(p for p in set_dir.iterdir() if (p / "case.json").exists())
    if args.limit:
        case_dirs = case_dirs[: args.limit]
    results, lat = [], []
    for cd in case_dirs:
        case = json.loads((cd / "case.json").read_text())
        images = [Image.open(cd / "crop.png").convert("RGB")]
        if (cd / "screen.png").exists():
            images.append(Image.open(cd / "screen.png").convert("RGB"))
        msgs = [{"role": "system", "content": [{"type": "text", "text": sys_prompt}]},
                {"role": "user", "content": [{"type": "image"}] * len(images) + [{"type": "text", "text": context_text(case["context"])}]}]
        text = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=images, return_tensors="pt").to("cuda")
        t0 = time.time()
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
        gen = processor.tokenizer.decode(out[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        ms = round((time.time() - t0) * 1000)
        lat.append(ms)
        events = parse_events(gen)
        r = score_case(events, case["gold"]["events"])
        r["case_id"] = case["id"]
        r["meta"] = {"provider": args.label, "duration_api_ms": ms, "cost_usd": 0.0, "raw": gen[:2000]}
        r["prediction"] = events
        results.append(r)
        ok = sum(sum(p[f] for f in FIELD_NAMES) for p in r["pairs"])
        tot = len(r["pairs"]) * len(FIELD_NAMES)
        print(f"  {case['id'][:40]:<42} matched {r['matched']} fields {ok}/{tot} fp={r['false_positives']} fn={r['false_negatives']} {ms}ms", flush=True)

    agg = aggregate(results)
    det = agg["detection"]
    print(f"\n=== {args.label} on {args.eval_set} ({len(case_dirs)} cases) ===")
    print(f"detection: P={det['precision']:.1%} R={det['recall']:.1%} F1={det['f1']:.1%} (tp={det['tp']} fp={det['fp']} fn={det['fn']})")
    for f in FIELD_NAMES:
        print(f"  {f:<12} {agg['fields'][f]:.1%}")
    print(f"latency mean {sum(lat) / max(1, len(lat)):.0f}ms")
    out_dir = ML_DIR / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{args.label.replace(':', '-')}-{time.strftime('%Y%m%dT%H%M%S')}.json"
    out_file.write_text(json.dumps({"provider": args.label, "set": args.eval_set, "aggregate": agg, "cases": results}, indent=2))
    print("->", out_file)


if __name__ == "__main__":
    main()
