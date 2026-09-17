"""Field-level scoring for event extraction.

A prediction and a gold label are both {"events": [...]} using the schema in
SPEC.md. Events are first matched 1:1 (unmatched predictions are false
positives, unmatched gold events are false negatives), then each matched pair
is scored per field. `confidence` and `notes` are model self-reports, not
scored. `start_time` counts as correct for all-day gold events, where the time
portion is meaningless.
"""
from __future__ import annotations

import itertools
import re
from difflib import SequenceMatcher

SIM_THRESHOLD = 0.6
AFFINITY_FLOOR = 0.2

FIELD_NAMES = [
    "title",
    "start_date",
    "start_time",
    "end",
    "all_day",
    "location",
    "timezone",
    "recurrence",
]


def text_sim(a: str | None, b: str | None) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    norm = lambda s: " ".join(s.lower().split())
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def field_sim(pred: str | None, gold: str | None) -> float:
    """Similarity for text fields, asymmetric by design: a prediction that
    contains everything the gold says plus extra correct detail ("Zilker Park,
    2100 Barton Springs Rd" vs gold "Zilker Park") scores full marks, while a
    prediction missing gold content does not. Max of fuzzy ratio and
    gold-token containment. (A prediction could game containment by dumping
    the whole source; at eval scale that shows up on inspection.)"""
    if not pred and not gold:
        return 1.0
    if not pred or not gold:
        return 0.0
    gold_tokens = _tokens(gold)
    containment = (
        len(gold_tokens & _tokens(pred)) / len(gold_tokens) if gold_tokens else 1.0
    )
    return max(text_sim(pred, gold), containment)


def _date(s: str | None) -> str:
    return (s or "")[:10]


def _minute(s: str | None) -> str:
    return (s or "")[:16]


def _dt_eq(a: str | None, b: str | None) -> bool:
    if not a and not b:
        return True
    if not a or not b:
        return False
    return _minute(a) == _minute(b)


def affinity(pred: dict, gold: dict) -> float:
    same_date = 1.0 if _date(pred.get("start")) == _date(gold.get("start")) else 0.0
    return 0.6 * field_sim(pred.get("title"), gold.get("title")) + 0.4 * same_date


def match_events(preds: list[dict], golds: list[dict]) -> list[tuple[int, int]]:
    """Best 1:1 assignment maximizing total affinity; pairs below the affinity
    floor are dropped so junk predictions count as FP+FN instead of a match."""
    if not preds or not golds:
        return []
    n, m = len(preds), len(golds)
    if max(n, m) > 8:
        return _greedy_match(preds, golds)

    best_pairs: list[tuple[int, int]] = []
    best_total = -1.0
    if n <= m:
        for combo in itertools.permutations(range(m), n):
            pairs = list(zip(range(n), combo))
            total = sum(affinity(preds[p], golds[g]) for p, g in pairs)
            if total > best_total:
                best_total, best_pairs = total, pairs
    else:
        for combo in itertools.permutations(range(n), m):
            pairs = [(p, g) for g, p in enumerate(combo)]
            total = sum(affinity(preds[p], golds[g]) for p, g in pairs)
            if total > best_total:
                best_total, best_pairs = total, pairs
    return sorted(
        (p, g) for p, g in best_pairs if affinity(preds[p], golds[g]) >= AFFINITY_FLOOR
    )


def _greedy_match(preds: list[dict], golds: list[dict]) -> list[tuple[int, int]]:
    scored = sorted(
        ((affinity(p, g), i, j) for i, p in enumerate(preds) for j, g in enumerate(golds)),
        reverse=True,
    )
    used_p: set[int] = set()
    used_g: set[int] = set()
    out: list[tuple[int, int]] = []
    for a, i, j in scored:
        if a < AFFINITY_FLOOR:
            break
        if i in used_p or j in used_g:
            continue
        used_p.add(i)
        used_g.add(j)
        out.append((i, j))
    return sorted(out)


def rrule_key(s: str | None) -> dict | None:
    """Normalize an RRULE for comparison: key order and case are irrelevant,
    BYDAY is a set, UNTIL matches on its date part only (the model may write
    20261204, 20261204T235959, or 20261204T235959Z), and defaults that add no
    information (INTERVAL=1, WKST) are dropped."""
    if not s:
        return None
    body = s.strip()
    if body.upper().startswith("RRULE:"):
        body = body[6:]
    parts: dict[str, object] = {}
    for kv in body.split(";"):
        if "=" not in kv:
            continue
        k, v = kv.split("=", 1)
        k, v = k.strip().upper(), v.strip().upper()
        if k == "BYDAY":
            parts[k] = frozenset(x.strip() for x in v.split(",") if x.strip())
        elif k == "UNTIL":
            parts[k] = v[:8]
        elif k == "INTERVAL" and v == "1":
            continue
        elif k == "WKST":
            continue
        else:
            parts[k] = v
    return parts


def score_pair(pred: dict, gold: dict) -> dict:
    title_sim = field_sim(pred.get("title"), gold.get("title"))

    loc_p = pred.get("location") or None
    loc_g = gold.get("location") or None
    if loc_p is None and loc_g is None:
        loc_ok = True
    elif loc_p is None or loc_g is None:
        loc_ok = False
    else:
        loc_ok = field_sim(loc_p, loc_g) >= SIM_THRESHOLD

    gold_all_day = bool(gold.get("all_day"))
    return {
        "title": title_sim >= SIM_THRESHOLD,
        "title_similarity": round(title_sim, 3),
        "start_date": _date(pred.get("start")) == _date(gold.get("start")),
        "start_time": gold_all_day
        or _minute(pred.get("start"))[11:] == _minute(gold.get("start"))[11:],
        "end": True if gold_all_day and not gold.get("end") and not pred.get("end")
        else _dt_eq(pred.get("end"), gold.get("end")),
        "all_day": bool(pred.get("all_day")) == gold_all_day,
        "location": loc_ok,
        "timezone": (pred.get("timezone") or None) == (gold.get("timezone") or None),
        "recurrence": rrule_key(pred.get("recurrence")) == rrule_key(gold.get("recurrence")),
    }


def score_case(pred_events: list[dict], gold_events: list[dict]) -> dict:
    pairs = match_events(pred_events, gold_events)
    return {
        "matched": len(pairs),
        "false_positives": len(pred_events) - len(pairs),
        "false_negatives": len(gold_events) - len(pairs),
        "pairs": [score_pair(pred_events[p], gold_events[g]) for p, g in pairs],
    }


def aggregate(case_results: list[dict]) -> dict:
    tp = sum(r["matched"] for r in case_results)
    fp = sum(r["false_positives"] for r in case_results)
    fn = sum(r["false_negatives"] for r in case_results)
    all_pairs = [p for r in case_results for p in r["pairs"]]

    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    fields = {
        name: (sum(p[name] for p in all_pairs) / len(all_pairs) if all_pairs else 0.0)
        for name in FIELD_NAMES
    }
    title_sim = (
        sum(p["title_similarity"] for p in all_pairs) / len(all_pairs) if all_pairs else 0.0
    )
    return {
        "detection": {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
        "fields": fields,
        "title_similarity": title_sim,
    }
