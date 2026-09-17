"""Turn case directories into fine-tuning JSONL.

Each record is the exact production conversation the extension sends:
system prompt, then [crop image, screen image, context text], and the
assistant's compact JSON answer. Output uses LLaMA-Factory's multimodal
"sharegpt"-style messages format (image placeholders + an images list), which
TRL-based scripts can also consume.

Usage (from ml/):
  uv run python -m train.build_dataset --sets train_v1 --out data/train_v1 --val-frac 0.05
  # real captures are NEVER included: eval_v0/eval_v1 stay the test split.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from evals.providers import export_prompt

ML_DIR = Path(__file__).resolve().parents[1]
FIELD_ORDER = ["title", "start", "end", "all_day", "timezone", "location", "description", "recurrence", "confidence", "notes"]
FORBIDDEN_SETS = {"eval_v0", "eval_v1"}


def compact_answer(events: list[dict]) -> str:
    ordered = [{k: e.get(k) for k in FIELD_ORDER} for e in events]
    return json.dumps({"events": ordered}, ensure_ascii=False, separators=(", ", ": "))


def record(case_dir: Path, case: dict, prompt_cache: dict) -> dict:
    ctx = case["context"]
    key = json.dumps(ctx, sort_keys=True)
    if key not in prompt_cache:
        prompt_cache[key] = export_prompt(ctx)
    p = prompt_cache[key]
    return {
        "id": case["id"],
        "messages": [
            {"role": "system", "content": p["system_prompt"]},
            {"role": "user", "content": "<image><image>\n" + p["context_text"]},
            {"role": "assistant", "content": compact_answer(case["gold"]["events"])},
        ],
        "images": [str(case_dir / "crop.png"), str(case_dir / "screen.png")],
        "tags": case.get("tags", []),
        "kind": case.get("kind", ""),
    }


def split_of(case_id: str, val_frac: float) -> str:
    h = int(hashlib.sha1(case_id.encode()).hexdigest(), 16) % 10_000
    return "val" if h < val_frac * 10_000 else "train"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", nargs="+", default=["train_v1"])
    ap.add_argument("--out", default="data/train_v1")
    ap.add_argument("--val-frac", type=float, default=0.05)
    args = ap.parse_args()
    for s in args.sets:
        if s in FORBIDDEN_SETS:
            raise SystemExit(f"{s} is a real-capture test set and must not be trained on")

    out_dir = ML_DIR / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt_cache: dict = {}
    files = {"train": open(out_dir / "train.jsonl", "w"), "val": open(out_dir / "val.jsonl", "w")}
    counts: Counter = Counter()
    kinds: dict[str, Counter] = {"train": Counter(), "val": Counter()}
    events = Counter()
    nonevent = Counter()
    for s in args.sets:
        for case_dir in sorted(p for p in (ML_DIR / "data" / s).iterdir() if (p / "case.json").exists()):
            case = json.loads((case_dir / "case.json").read_text())
            split = split_of(case["id"], args.val_frac)
            rec = record(case_dir, case, prompt_cache)
            files[split].write(json.dumps(rec, ensure_ascii=False) + "\n")
            counts[split] += 1
            kinds[split][case.get("kind", "?")] += 1
            events[split] += len(case["gold"]["events"])
            nonevent[split] += int(not case["gold"]["events"])
    for f in files.values():
        f.close()

    info = {
        "cropcal_train": {"file_name": "train.jsonl", "formatting": "sharegpt",
                          "columns": {"messages": "messages", "images": "images"},
                          "tags": {"role_tag": "role", "content_tag": "content", "user_tag": "user",
                                   "assistant_tag": "assistant", "system_tag": "system"}},
        "cropcal_val": {"file_name": "val.jsonl", "formatting": "sharegpt",
                        "columns": {"messages": "messages", "images": "images"},
                        "tags": {"role_tag": "role", "content_tag": "content", "user_tag": "user",
                                 "assistant_tag": "assistant", "system_tag": "system"}},
    }
    (out_dir / "dataset_info.json").write_text(json.dumps(info, indent=2))
    for split in ("train", "val"):
        print(f"{split}: {counts[split]} cases, {events[split]} events, {nonevent[split]} non-events "
              f"({nonevent[split] / max(1, counts[split]):.0%})")
        print("  kinds:", ", ".join(f"{k}={v}" for k, v in kinds[split].most_common()))
    print(f"-> {out_dir}/train.jsonl, val.jsonl, dataset_info.json")


if __name__ == "__main__":
    main()
