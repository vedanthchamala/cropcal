"""Re-score a stored results file against the CURRENT gold (predictions are
kept in results JSON, so gold fixes never require re-running a model).

Usage (from ml/):  uv run python -m evals.rescore results/bridge-20260910T183636.json
Writes a sibling file with '-rescored' in the name and prints the summary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .score import FIELD_NAMES, aggregate, score_case

ML_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    for arg in sys.argv[1:]:
        src = Path(arg)
        d = json.loads(src.read_text())
        cases = []
        for c in d["cases"]:
            gold = json.loads((ML_DIR / "data" / d["set"] / c["case_id"] / "case.json").read_text())["gold"]["events"]
            r = score_case(c.get("prediction", []), gold)
            r.update({"case_id": c["case_id"], "meta": c.get("meta", {}), "prediction": c.get("prediction", [])})
            cases.append(r)
        agg = aggregate(cases)
        out = src.with_name(src.stem + "-rescored.json")
        out.write_text(json.dumps({"provider": d["provider"], "set": d["set"], "aggregate": agg, "cases": cases}, indent=2))
        src.unlink()
        det = agg["detection"]
        exact = sum(1 for c in cases for p in c["pairs"] if all(p[f] for f in FIELD_NAMES))
        print(f"{d['provider']} on {d['set']}: F1 {det['f1']:.1%}, exact {exact}/{det['tp'] + det['fn']}, "
              + " ".join(f"{f}={agg['fields'][f]:.0%}" for f in FIELD_NAMES) + f" -> {out.name}")


if __name__ == "__main__":
    main()
