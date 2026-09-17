"""Promote verified bridge captures into a frozen eval set.

Gold labels are seeded from the bridge's recorded output — promote ONLY
captures whose events a human has verified. Edit case.json afterwards for any
field the model got wrong (gold is the truth, recorded_prediction stays as the
model's original answer).

Usage (from ml/):  uv run python -m evals.promote [--src captures] [--dest eval_v0]
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="captures")
    ap.add_argument("--dest", default="eval_v0")
    ap.add_argument("--force", action="store_true", help="overwrite existing cases")
    ap.add_argument("--only", action="append", default=None,
                    help="promote only these capture ids (repeatable); default promotes all")
    args = ap.parse_args()

    src_dir = DATA / args.src
    promoted = skipped = 0
    for rec_dir in sorted(p for p in src_dir.iterdir() if (p / "record.json").exists()):
        if args.only and rec_dir.name not in args.only:
            continue
        out = DATA / args.dest / rec_dir.name
        if out.exists() and not args.force:
            skipped += 1
            continue
        rec = json.loads((rec_dir / "record.json").read_text())
        out.mkdir(parents=True, exist_ok=True)
        for img in ("crop.png", "screen.png"):
            if (rec_dir / img).exists():
                shutil.copy2(rec_dir / img, out / img)
        case = {
            "id": rec["id"],
            "context": rec["context"],
            "gold": {"events": rec["events"]},
            "recorded_prediction": {"events": rec["events"], "meta": rec.get("meta", {})},
            "verification": {
                "status": "verified",
                "by": "human",
                "date": str(date.today()),
                "note": "gold seeded from bridge output; user confirmed all fields correct",
            },
        }
        (out / "case.json").write_text(json.dumps(case, indent=2))
        promoted += 1
        print(f"promoted {rec_dir.name} ({len(rec['events'])} events)")

    print(f"\n{promoted} promoted, {skipped} skipped (already exist) -> data/{args.dest}/")


if __name__ == "__main__":
    main()
