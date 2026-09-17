"""Builds ml/report.html — a local, auto-refreshing dashboard over all eval
sets and results. Regenerated automatically by evals.run and synth.generate;
open it once (`open ml/report.html`) and watch live while work happens.

Standalone:  uv run python -m evals.report
"""
from __future__ import annotations

import html as html_mod
import json
import time
from pathlib import Path

ML_DIR = Path(__file__).resolve().parents[1]

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,'Helvetica Neue',sans-serif;background:#f4f4f6;color:#1c1c1e;padding:28px}
h1{font-size:21px;margin-bottom:4px}
.sub{color:#6e6e73;font-size:13px;margin-bottom:24px}
h2{font-size:17px;margin:26px 0 10px}
table{border-collapse:collapse;font-size:13px;background:#fff;border-radius:8px;overflow:hidden}
th,td{padding:7px 12px;text-align:left;border-bottom:1px solid #ececf0}
th{background:#fafafa;color:#6e6e73;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px;margin-top:12px}
.card{background:#fff;border-radius:10px;padding:12px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.card img{max-width:100%;max-height:150px;object-fit:contain;border:1px solid #eee;border-radius:6px;background:#fafafa;display:block;margin:0 auto 8px}
.cid{font-size:12px;color:#6e6e73;margin-bottom:4px;word-break:break-all}
.gold{font-size:13px;line-height:1.45}
.badge{display:inline-block;font-size:12px;font-weight:600;padding:2px 8px;border-radius:10px;margin-bottom:6px}
.ok{background:#e2f4e5;color:#1a7f37}.warn{background:#fdeaea;color:#b3261e}
.none{background:#eeeef2;color:#6e6e73}
details{margin-top:6px;font-size:12px}
pre{background:#f6f6f8;padding:8px;border-radius:6px;overflow-x:auto;font-size:11px;line-height:1.4}
summary{cursor:pointer;color:#4f6ef7}
"""


def _load_runs() -> list[dict]:
    runs = []
    for f in sorted((ML_DIR / "results").glob("*.json")):
        try:
            data = json.loads(f.read_text())
            data["_file"] = f.name
            runs.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return runs


def _discover_sets() -> dict[str, list[Path]]:
    sets: dict[str, list[Path]] = {}
    data = ML_DIR / "data"
    if data.exists():
        for set_dir in sorted(data.iterdir()):
            cases = sorted(p for p in set_dir.iterdir() if (p / "case.json").exists()) \
                if set_dir.is_dir() else []
            if cases:
                sets[set_dir.name] = cases
    return sets


def _esc(s: str) -> str:
    return html_mod.escape(str(s), quote=True)


def _event_line(e: dict) -> str:
    bits = [f"<b>{_esc(e.get('title', '?'))}</b>", _esc(e.get("start", "")[:16])]
    if e.get("end"):
        bits.append(f"→ {_esc(e['end'][11:16] or e['end'][:16])}")
    if e.get("all_day"):
        bits.append("(all-day)")
    if e.get("location"):
        bits.append(f"📍{_esc(e['location'])}")
    if e.get("timezone"):
        bits.append(f"🌐{_esc(e['timezone'])}")
    if e.get("recurrence"):
        bits.append("🔁")
    return " · ".join(bits)


def _case_card(set_name: str, case_dir: Path, latest: dict | None) -> str:
    case = json.loads((case_dir / "case.json").read_text())
    gold = case["gold"]["events"]
    gold_html = (
        "<br>".join(_event_line(e) for e in gold)
        if gold
        else "<i>no event (negative case)</i>"
    )

    badge = "<span class='badge none'>not evaluated yet</span>"
    detail = ""
    if latest is not None:
        ok = sum(sum(1 for k, v in p.items() if k != "title_similarity" and v)
                 for p in latest["pairs"])
        total = len(latest["pairs"]) * 8
        problems = []
        if latest["false_positives"]:
            problems.append(f"{latest['false_positives']} hallucinated")
        if latest["false_negatives"]:
            problems.append(f"{latest['false_negatives']} missed")
        bad_fields = sorted({k for p in latest["pairs"]
                             for k, v in p.items() if k != "title_similarity" and not v})
        if bad_fields:
            problems.append("✗ " + ", ".join(bad_fields))
        if problems:
            badge = f"<span class='badge warn'>{_esc('; '.join(problems))}</span>"
        elif gold:
            badge = f"<span class='badge ok'>✓ all fields ({ok}/{total})</span>"
        else:
            badge = "<span class='badge ok'>✓ correctly found nothing</span>"

    detail = (
        f"<details><summary>gold JSON</summary><pre>{_esc(json.dumps(gold, indent=1))}</pre></details>"
    )
    img = f"data/{set_name}/{case_dir.name}/crop.png"
    return (
        f"<div class='card'><img src='{_esc(img)}' loading='lazy'>"
        f"<div class='cid'>{_esc(case_dir.name)}</div>{badge}"
        f"<div class='gold'>{gold_html}</div>{detail}</div>"
    )


def build() -> Path:
    sets = _discover_sets()
    runs = _load_runs()

    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<meta http-equiv='refresh' content='10'>",
        f"<title>CropCal Evals</title><style>{CSS}</style></head><body>",
        "<h1>CropCal — datasets &amp; eval results</h1>",
        f"<div class='sub'>auto-refreshes every 10s · generated {time.strftime('%Y-%m-%d %H:%M:%S')}"
        f" · {sum(len(c) for c in sets.values())} cases across {len(sets)} sets</div>",
    ]

    if runs:
        parts.append("<h2>Run history</h2><table><tr><th>when</th><th>set</th>"
                     "<th>provider</th><th>events</th><th>detection F1</th>"
                     "<th>avg field acc</th><th>title sim</th></tr>")
        for run in reversed(runs[-12:]):
            agg = run["aggregate"]
            det = agg["detection"]
            fields = agg["fields"]
            avg_acc = sum(fields.values()) / len(fields) if fields else 0
            when = run["_file"].rsplit("-", 1)[-1].replace(".json", "")
            when = f"{when[9:11]}:{when[11:13]}:{when[13:15]}" if len(when) >= 15 else when
            parts.append(
                f"<tr><td>{_esc(when)}</td><td>{_esc(run.get('set', '?'))}</td>"
                f"<td>{_esc(run.get('provider', '?'))}</td>"
                f"<td>tp {det['tp']} · fp {det['fp']} · fn {det['fn']}</td>"
                f"<td>{det['f1']:.0%}</td><td>{avg_acc:.1%}</td>"
                f"<td>{agg['title_similarity']:.3f}</td></tr>"
            )
        parts.append("</table>")

    for set_name, case_dirs in sets.items():
        latest_run = next(
            (r for r in reversed(runs) if r.get("set") == set_name), None
        )
        by_id = (
            {c["case_id"]: c for c in latest_run["cases"]} if latest_run else {}
        )
        label = (
            f" · latest: {latest_run['provider']} @ {latest_run['_file'].rsplit('-', 1)[-1][9:15]}"
            if latest_run
            else " · never evaluated"
        )
        parts.append(f"<h2>{_esc(set_name)} — {len(case_dirs)} cases{_esc(label)}</h2><div class='grid'>")
        for case_dir in case_dirs:
            case_id = json.loads((case_dir / "case.json").read_text())["id"]
            parts.append(_case_card(set_name, case_dir, by_id.get(case_id)))
        parts.append("</div>")

    parts.append("</body></html>")
    out = ML_DIR / "report.html"
    out.write_text("".join(parts))
    return out


if __name__ == "__main__":
    print(f"wrote {build()}")
