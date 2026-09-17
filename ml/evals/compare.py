"""Side-by-side comparison of the latest complete run per provider on each set.

Usage (from ml/):  uv run python -m evals.compare [--providers bridge ollama:qwen3-vl:4b ...]
Prints detection F1, per-field accuracy, latency, cost per provider per set,
then a failure breakdown (which fields fail, and on which cases) for every
provider other than the teacher.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from .score import FIELD_NAMES

ML_DIR = Path(__file__).resolve().parents[1]
SETS = ["eval_v0", "eval_v1", "synth_v0", "synth_v1", "synth_v2", "train_smoke", "train_v1"]


def latest_runs() -> dict[tuple[str, str], dict]:
    runs: dict[tuple[str, str], dict] = {}
    for f in sorted((ML_DIR / "results").glob("*.json")):
        d = json.loads(f.read_text())
        if d.get("partial"):
            continue
        key = (d.get("provider", "?"), d.get("set", "?"))
        runs[key] = d | {"_file": f.name}
    return runs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--providers", nargs="*", default=None)
    ap.add_argument("--examples", type=int, default=6, help="misses to print per provider")
    args = ap.parse_args()

    runs = latest_runs()
    providers = args.providers or sorted({p for p, _ in runs})

    print(f"{'provider':<22} {'set':<9} {'cases':>5} {'F1':>7} " + " ".join(f"{f[:8]:>8}" for f in FIELD_NAMES)
          + f" {'exact':>6} {'falarm':>7} {'lat_s':>6} {'$/crop':>7}")
    print("  exact = gold events returned with all 8 fields right (no edits needed); "
          "falarm = non-event crops that produced an event")
    totals: dict[str, list] = defaultdict(lambda: [0, 0, 0, 0])  # exact, gold, falarm, nonevent
    for p in providers:
        for s in SETS:
            r = runs.get((p, s))
            if not r:
                continue
            agg = r["aggregate"]
            lat = [c["meta"].get("duration_api_ms") for c in r["cases"] if c["meta"].get("duration_api_ms")]
            cost = [c["meta"].get("cost_usd") for c in r["cases"] if c["meta"].get("cost_usd") is not None]
            gold_n = sum(len(json.loads((ML_DIR / "data" / s / c["case_id"] / "case.json").read_text())["gold"]["events"])
                         for c in r["cases"])
            exact = sum(1 for c in r["cases"] for pair in c["pairs"] if all(pair[f] for f in FIELD_NAMES))
            nonevent = [c for c in r["cases"]
                        if not json.loads((ML_DIR / "data" / s / c["case_id"] / "case.json").read_text())["gold"]["events"]]
            falarm = sum(1 for c in nonevent if c["false_positives"])
            t = totals[p]; t[0] += exact; t[1] += gold_n; t[2] += falarm; t[3] += len(nonevent)
            print(f"{p:<22} {s:<9} {len(r['cases']):>5} {agg['detection']['f1']:>7.1%} "
                  + " ".join(f"{agg['fields'][f]:>8.0%}" for f in FIELD_NAMES)
                  + f" {exact / gold_n if gold_n else 0:>6.0%} {f'{falarm}/{len(nonevent)}':>7}"
                  + f" {statistics.mean(lat) / 1000 if lat else 0:>6.1f} {statistics.mean(cost) if cost else 0:>7.3f}")
    print()
    for p, (exact, gold_n, falarm, nonevent) in totals.items():
        if gold_n:
            print(f"{p:<22} ALL       exact {exact}/{gold_n} = {exact / gold_n:.0%}   false alarms {falarm}/{nonevent} non-event crops")

    for p in providers:
        if p == "bridge":
            continue
        fails: Counter = Counter()
        fn = fp = tp = 0
        examples = []
        errors: Counter = Counter()
        for s in SETS:
            r = runs.get((p, s))
            if not r:
                continue
            for c in r["cases"]:
                tp += c["matched"]; fn += c["false_negatives"]; fp += c["false_positives"]
                if c["meta"].get("error"):
                    errors[c["meta"]["error"].split(":")[0]] += 1
                bad = [f for pair in c["pairs"] for f in FIELD_NAMES if not pair[f]]
                fails.update(bad)
                if (bad or c["false_negatives"] or c["false_positives"]) and len(examples) < args.examples:
                    examples.append((s, c["case_id"], bad, c["false_negatives"], c["false_positives"], c["prediction"]))
        if not tp and not fn and not fp:
            continue
        print(f"\n=== {p}: matched {tp}, missed {fn}, hallucinated {fp}; provider errors: {dict(errors) or 'none'}")
        print("field failures on matched events:", ", ".join(f"{k}={v}" for k, v in fails.most_common()) or "none")
        for s, cid, bad, fns, fps, pred in examples:
            gold = json.loads((ML_DIR / "data" / s / cid / "case.json").read_text())["gold"]["events"]
            print(f"\n  {s}/{cid}: fields_wrong={bad} fn={fns} fp={fps}")
            for e in gold:
                print(f"    gold: {e['title']} | {e['start']} → {e['end']} | all_day={e['all_day']} | {e['location']} | tz={e['timezone']} | {e['recurrence']}")
            for e in pred:
                print(f"    pred: {e.get('title')} | {e.get('start')} → {e.get('end')} | all_day={e.get('all_day')} | {e.get('location')} | tz={e.get('timezone')} | {e.get('recurrence')}")


if __name__ == "__main__":
    main()
