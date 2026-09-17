"""Run a provider over an eval set and report field-level accuracy.

Usage (from ml/):
  uv run python -m evals.run --provider cached
  uv run python -m evals.run --provider bridge   # bridge must be running
  uv run python -m evals.run --provider gemini --model gemini-3.8-flash  # GEMINI_API_KEY in ml/.env
  uv run python -m evals.run --provider ollama --model qwen3-vl:4b        # local model via Ollama

Writes full results to ml/results/<provider>-<timestamp>.json.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path

from . import providers
from .score import FIELD_NAMES, aggregate, score_case

ML_DIR = Path(__file__).resolve().parents[1]


def load_dotenv() -> None:
    env = ML_DIR / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", dest="eval_set", default="eval_v0")
    ap.add_argument("--provider", default="cached", choices=["cached", "bridge", "gemini", "ollama"])
    ap.add_argument("--bridge-url", default="http://127.0.0.1:48765")
    ap.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    ap.add_argument("--model", default=None, help="model id (gemini: default gemini-3.8-flash; ollama: default qwen3-vl:4b)")
    ap.add_argument("--thinking", default="", help="gemini provider: thinkingBudget (2.5) or thinkingLevel (3.x)")
    ap.add_argument("--think", default=None, choices=["on", "off"], help="ollama provider: force thinking on/off")
    ap.add_argument("--num-ctx", type=int, default=8192, help="ollama provider: context window")
    ap.add_argument("--num-predict", type=int, default=2048, help="ollama provider: max output tokens")
    ap.add_argument("--only", action="append", default=None, help="run only these case ids (repeatable)")
    ap.add_argument("--limit", type=int, default=0, help="evaluate only the first N cases")
    ap.add_argument("--offset", type=int, default=0, help="skip the first N cases")
    args = ap.parse_args()
    load_dotenv()
    if args.model is None:
        args.model = {"gemini": "gemini-3.8-flash", "ollama": "qwen3-vl:4b"}.get(args.provider)
    gemini_opts = {"api_key": os.environ.get("GEMINI_API_KEY"), "model": args.model,
                   "thinking": args.thinking}
    ollama_opts = {"url": args.ollama_url, "model": args.model, "num_ctx": args.num_ctx,
                   "num_predict": args.num_predict,
                   "think": None if args.think is None else args.think == "on"}
    label = f"{args.provider}:{args.model}" if args.provider in ("gemini", "ollama") else args.provider

    set_dir = ML_DIR / "data" / args.eval_set
    case_dirs = sorted(p for p in set_dir.iterdir() if (p / "case.json").exists())
    if not case_dirs:
        raise SystemExit(f"no cases in {set_dir} — run evals.promote first")
    if args.only:
        case_dirs = [p for p in case_dirs if p.name in args.only]
    if args.offset:
        case_dirs = case_dirs[args.offset:]
    if args.limit:
        case_dirs = case_dirs[: args.limit]

    case_results = []
    latencies: list[float] = []
    costs: list[float] = []
    rows = []
    out_dir = ML_DIR / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{label.replace(':', '-')}-{time.strftime('%Y%m%dT%H%M%S')}.json"

    def save(partial: bool) -> None:
        # Written after every case so a quota-limited or interrupted run keeps
        # its progress; the final write flips partial to false.
        out_file.write_text(json.dumps({
            "provider": label, "set": args.eval_set, "partial": partial,
            "aggregate": aggregate(case_results), "cases": case_results,
        }, indent=2))

    for case_dir in case_dirs:
        case = json.loads((case_dir / "case.json").read_text())
        try:
            pred, meta = providers.predict(args.provider, case_dir, case, args.bridge_url,
                                           gemini_opts, ollama_opts)
        except Exception as err:
            save(True)
            print(f"\naborted at {case['id']} after {len(case_results)} cases: {err}")
            print(f"partial results -> {out_file.relative_to(ML_DIR.parent)}")
            raise
        result = score_case(pred["events"], case["gold"]["events"])
        result["case_id"] = case["id"]
        result["meta"] = meta
        result["prediction"] = pred["events"]
        case_results.append(result)

        if meta.get("duration_api_ms") is not None:
            latencies.append(meta["duration_api_ms"])
        if meta.get("cost_usd") is not None:
            costs.append(meta["cost_usd"])

        fields_ok = sum(sum(p[f] for f in FIELD_NAMES) for p in result["pairs"])
        fields_total = len(result["pairs"]) * len(FIELD_NAMES)
        flags = []
        if result["false_positives"]:
            flags.append(f"FP:{result['false_positives']}")
        if result["false_negatives"]:
            flags.append(f"FN:{result['false_negatives']}")
        rows.append(
            f"  {case['id'][:23]:<25} events {result['matched']:>2} matched   "
            f"fields {fields_ok:>2}/{fields_total:<3} {' '.join(flags)}"
        )
        print(rows[-1], flush=True)
        save(True)

    agg = aggregate(case_results)
    det = agg["detection"]

    print(f"\n=== {label} on {args.eval_set} ({len(case_dirs)} cases) ===\n")
    print("\n".join(rows))
    print(
        f"\ndetection: P={det['precision']:.2%} R={det['recall']:.2%} "
        f"F1={det['f1']:.2%}  (tp={det['tp']} fp={det['fp']} fn={det['fn']})"
    )
    print("field accuracy (matched events):")
    for name in FIELD_NAMES:
        print(f"  {name:<12} {agg['fields'][name]:.2%}")
    print(f"  title similarity avg: {agg['title_similarity']:.3f}")
    if latencies:
        print(
            f"latency: mean {statistics.mean(latencies):.0f}ms, "
            f"median {statistics.median(latencies):.0f}ms, max {max(latencies):.0f}ms"
        )
    if costs and sum(costs) > 0:
        print(f"cost (list price): total ${sum(costs):.4f}, mean ${statistics.mean(costs):.4f}/crop")

    save(False)
    print(f"\nfull results -> {out_file.relative_to(ML_DIR.parent)}")

    from .report import build

    build()


if __name__ == "__main__":
    main()
