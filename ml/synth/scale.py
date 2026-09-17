"""Parameterized synthetic-case engine (scale-up of synth.generate).

Content pools are seeded from real-world recruiting/event patterns (university
org recruitment timelines, career-fair formats, internship OA waves) but org
names are fictionalized. Every rendered string and its gold label derive from
the same parameters, so gold stays exact by construction. Seeded RNG makes any
batch reproducible.

Case tags: "needs_context" marks cases whose crop alone lacks the event
identity (a bare date banner, a timeline step without the org) — the model
must pull title/org from the full-screen image.

Usage (from ml/):  uv run python -m synth.scale --count 62 --seed 7 [--dest synth_v1]
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, datetime, timedelta

from synth.generate import (
    ARTICLE_CSS, DATA, FLYER_CSS, NOW, TZ, WEEKDAY,
    discord, ev, flyer, gmail, groupme, imessage, page, render,
)

TODAY = date(2026, 9, 1)  # must match NOW in generate.py

# ------------------------------------------------------------- content pools

ORGS = [
    ("Ion Racing", "formula-electric design team", "ionracing.ut"),
    ("Solar Steers", "solar car team", "solarsteers"),
    ("Texas Orbit Labs", "smallsat research org", "orbitlabs.tx"),
    ("Product Space", "product management fellowship", "productspace.atx"),
    ("Data Science Society", "data science club", "dss.utx"),
    ("Women in Computing", "CS community org", "wic.tex"),
    ("Consulting Collective", "student consulting group", "consultingcollective"),
    ("Robotics Guild", "combat robotics club", "roboguild"),
    ("Quantum Club", "quantum computing org", "quantumclub.atx"),
    ("Case Craft", "case competition org", "casecraft.u"),
]
COMPANIES = ["Meridian Systems", "Cobalt Labs", "Northwind Robotics", "Helios Compute", "Bluegrain AI"]
VENUES = ["GDC 2.216", "EER 0.904", "PCL Learning Lab", "Union Ballroom", "ETC 2.136",
          "Gregory Gym Annex", "WCP Legacy Room", "Zoom", "RLM 4.102", "the Engineering Quad"]
CHAT_VENUES = ["PCL 3rd floor", "the GDC atrium", "Union Starbucks", "Gong Cha on Guad", "Kins Market"]
STEP_SETS = [
    ["Applications Open", "Info Session 1", "Info Session 2", "Applications Due", "Decisions Released"],
    ["Kickoff Social", "Info Session", "Applications Due", "Interviews", "Offers Out"],
    ["Open House", "Tech Talk", "Applications Close", "Coffee Chats"],
    ["Info Session 1", "Open Garage", "Applications Due", "New Member Orientation"],
]
SINGLE_EVENTS = [
    ("General Body Meeting", (18, 20)), ("Resume Workshop", (17, 19)),
    ("Alumni Panel", (18, 30)), ("Tryouts", (19, 0)), ("Guest Speaker Night", (18, 30)),
    ("Project Demo Day", (17, 0)), ("Study Jam", (18, 0)), ("Volunteer Day", (10, 0)),
]
FLYER_COLORS = [("#1a2c5b", "#ffd9a0"), ("#2d4739", "#f2ede3"), ("#5b1a3c", "#ffe9f2"),
                ("#20303c", "#a8e0ff"), ("#3c2f1a", "#ffefc2"), ("#101820", "#f2aa4c")]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def iso(d: date, h: int = 0, m: int = 0) -> str:
    return f"{d.isoformat()}T{h:02d}:{m:02d}:00"


def wd(d: date) -> str:
    return d.strftime("%A")


def phrase_date(rng: random.Random, d: date, style: str | None = None) -> str:
    style = style or rng.choice(["slash", "abbr", "full", "wd_full", "wd_slash"])
    if style == "slash":
        return f"{d.month}/{d.day}"
    if style == "abbr":
        return f"{d.strftime('%b')} {d.day}"
    if style == "full":
        return f"{MONTHS[d.month - 1]} {d.day}"
    if style == "wd_full":
        return f"{wd(d)}, {MONTHS[d.month - 1]} {d.day}"
    return f"{wd(d)[:3]} {d.month}/{d.day}"


def fmt_time(h: int, m: int) -> str:
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ampm}" if m else f"{h12} {ampm}"


def near_date(rng: random.Random, lo: int = 1, hi: int = 40) -> date:
    return TODAY + timedelta(days=rng.randint(lo, hi))


# ------------------------------------------------------------- new templates

TL_CSS = FLYER_CSS + (
    ".tl{height:100vh;display:flex;flex-direction:column;justify-content:center;gap:12px;padding:34px}"
    ".hd{font-size:26px;font-weight:800;margin-bottom:4px}.seas{font-size:14px;opacity:.8;"
    "letter-spacing:2px;text-transform:uppercase}"
    ".step{background:rgba(255,255,255,.94);color:#1b2430;border-radius:12px;padding:11px 16px;"
    "display:flex;gap:14px;align-items:center}"
    ".dt{font-weight:800;font-size:16px;white-space:nowrap}.nm{font-size:15px;font-weight:600}"
    ".tm{font-size:12.5px;color:#54606e}"
)

JOB_CSS = ARTICLE_CSS + (
    ".jrow{font-size:14px;margin-bottom:8px}.jrow b{display:inline-block;min-width:150px}"
    ".apply{display:inline-block;background:#0a66c2;color:#fff;padding:9px 22px;border-radius:18px;"
    "font-weight:600;margin-top:12px}"
)


def timeline_post(rng, org_name, handle, season, steps, colors, caption):
    bg, fg = colors
    rows = "".join(
        f"<div class='step'><div class='dt'>{s['datestr']}</div>"
        f"<div><div class='nm'>{s['name']}</div>"
        + (f"<div class='tm'>{s['timestr']}</div>" if s.get("timestr") else "")
        + "</div></div>"
        for s in steps
    )
    # crop deliberately omits the org name — identity must come from the screen
    inner = f"<div class='seas'>{season} recruitment</div>{rows}"
    crop = page(TL_CSS, f"<div class='tl' style='background:{bg};color:{fg}'>{inner}</div>")
    screen = page(
        TL_CSS,
        f"<div class='ig'><div class='igpane'><div class='igframe' style='background:{bg};"
        f"color:{fg};height:640px;width:470px;justify-content:center'>{inner}</div></div>"
        f"<div class='igside'><b>{handle}</b>{caption}"
        "<div style='margin-top:14px;color:#777'>2d &nbsp; 214 likes</div></div></div>",
    )
    return crop, screen


def job_posting(company, role, deadline_str, extras):
    body = (
        f"<div class='art'><div class='ah'>{role} — Summer 2027</div>"
        f"<div class='ab'>{company} · Austin, TX (hybrid) · Internship</div>"
        f"<div class='jrow'><b>Application deadline:</b> {deadline_str}</div>"
        + "".join(f"<div class='jrow'><b>{k}:</b> {v}</div>" for k, v in extras)
        + "<div class='apply'>Apply now</div></div>"
    )
    crop = page(JOB_CSS, body)
    screen = page(JOB_CSS, "<div style='background:#0a66c2;color:#fff;padding:12px 20px;"
                  "font-weight:700'>CareerBoard</div>" + body)
    return crop, screen


# ------------------------------------------------------------- scenario builders

def b_timeline(rng, idx):
    org, desc, handle = rng.choice(ORGS)
    steps_names = rng.choice(STEP_SETS)[: rng.randint(3, 4)]
    d = near_date(rng, -4, 12)
    steps, gold = [], []
    for name in steps_names:
        d = d + timedelta(days=rng.randint(1, 4))
        timed = ("Session" in name or "Social" in name or "House" in name
                 or "Garage" in name or "Orientation" in name or "Talk" in name)
        step = {"name": name, "datestr": phrase_date(rng, d, "slash")}
        if "Due" in name or "Close" in name:
            step["timestr"] = "11:59 PM"
            gold.append(ev(f"{org} {name}", iso(d, 23, 59), end=iso(d, 23, 59)))
        elif timed:
            h = rng.choice([17, 18, 19])
            dur = rng.choice([1, 2])
            step["timestr"] = f"{fmt_time(h, 0)}–{fmt_time(h + dur, 0)} · {rng.choice(VENUES)}"
            venue = step["timestr"].split("· ")[1]
            gold.append(ev(f"{org} {name}", iso(d, h), end=iso(d, h + dur), location=venue))
        else:
            gold.append(ev(f"{org} {name}", iso(d), all_day=True))
        steps.append(step)
    caption = (f"{org} fall 2026 recruitment is HERE. We're a {desc} — no experience"
               f" needed. Questions? DM us. \U0001f918")
    crop, screen = timeline_post(rng, org, handle, "fall 2026", steps,
                                 rng.choice(FLYER_COLORS), caption)
    return dict(id=f"synth1-{idx:03d}-timeline", crop=crop, screen=screen,
                crop_size=(540, 520), page_title=f"{org} on Instagram",
                page_url=f"https://www.instagram.com/p/T{idx:07d}/",
                gold=gold, tags=["needs_context", "multi_event"])


def b_flyer_single(rng, idx, needs_context=False):
    org, _, handle = rng.choice(ORGS)
    name, (h, m) = rng.choice(SINGLE_EVENTS)
    d = near_date(rng)
    venue = rng.choice(VENUES)
    datestr = phrase_date(rng, d, rng.choice(["wd_full", "abbr", "full"]))
    dateline = f"{datestr} · {fmt_time(h, m)}"
    gold = [ev(name if not needs_context else f"{org} {name}",
               iso(d, h, m), location=venue)]
    caption = f"Join {org} for our {name.lower()}! {datestr}, {venue}. All majors welcome."
    if needs_context:
        # crop shows ONLY the date/time/venue banner; the event name lives in
        # the screen (flyer title + caption).
        crop = page(FLYER_CSS, "<div class='fl' style='background:#111;color:#fff'>"
                    f"<div class='d'>{dateline}</div><div class='s'>{venue}</div></div>")
        _, screen = flyer("save the date", name.upper(), dateline, venue,
                          rng.choice(FLYER_COLORS), caption, handle)
        tags = ["needs_context"]
    else:
        crop, screen = flyer(org, name.upper(), dateline, venue,
                             rng.choice(FLYER_COLORS), caption, handle)
        tags = []
    return dict(id=f"synth1-{idx:03d}-flyer{'x' if needs_context else ''}",
                crop=crop, screen=screen, crop_size=(520, 420),
                page_title=f"{org} on Instagram",
                page_url=f"https://www.instagram.com/p/F{idx:07d}/",
                gold=gold, tags=tags)


def b_chat(rng, idx):
    kind = rng.choice(["imessage", "groupme", "discord"])
    # cap at +5 days: "this monday" said on a Tuesday is ambiguous, never gold-able
    offset = rng.randint(1, 5)
    d = TODAY + timedelta(days=offset)
    h = rng.choice([11, 12, 17, 18, 19])
    venue = rng.choice(CHAT_VENUES)
    activity = rng.choice(["study session", "project meeting", "dinner", "review session",
                           "movie night", "gym session"])
    when_phrase = "tomorrow" if offset == 1 else f"this {wd(d).lower()}" if offset < 7 else phrase_date(rng, d)
    line = f"{activity} {when_phrase} at {fmt_time(h, 0).lower()}, {venue}?"
    gold = [ev(activity.title(), iso(d, h), location=venue)]
    if kind == "imessage":
        convo = ("<div class='stamp'>Today 10:02 AM</div>"
                 f"<div class='b in'>{line}</div><div class='b out'>i'm down</div>"
                 "<div class='b in'>bet, see you there</div>")
        crop, screen = imessage(convo, rng.choice(["Sam", "Priya", "Jordan", "Alex"]),
                                ["Mom", "roomies", "CS group"])
        title, url = "Screenshot.png", "file:///Users/vedanth/Desktop/Screenshot.png"
    elif kind == "groupme":
        crop, screen = groupme([("Priya", line), ("Devon", "works for me"), ("Sam", "+1")],
                               "Project Group")
        title, url = "GroupMe | Project Group", "https://web.groupme.com/chats"
    else:
        crop, screen = discord([("nova", line), ("jae", "count me in")],
                               "general", ["announcements", "memes"])
        title, url = "Discord | #general", "https://discord.com/channels/1/2"
    return dict(id=f"synth1-{idx:03d}-chat-{kind}", crop=crop, screen=screen,
                crop_size=(600, 280), page_title=title, page_url=url,
                gold=gold, tags=["relative_date"])


def b_chat_nonevent(rng, idx):
    convo = ("<div class='stamp'>Today 9:41 AM</div>"
             "<div class='b in'>bro the midterm average was a 61</div>"
             "<div class='b out'>oh that's rough</div>"
             "<div class='b in'>curve better save us</div>")
    crop, screen = imessage(convo, "Jordan", ["Maya", "Mom"])
    return dict(id=f"synth1-{idx:03d}-nonevent-chat", crop=crop, screen=screen,
                crop_size=(560, 260), page_title="Screenshot.png",
                page_url="file:///Users/vedanth/Desktop/Screenshot2.png",
                gold=[], tags=["nonevent"])


def b_email(rng, idx):
    kind = rng.choice(["invite_tz", "internship", "digest"])
    if kind == "invite_tz":
        d = near_date(rng, 3, 20)
        h = rng.choice([10, 13, 15, 16])
        tzname, tziana = rng.choice([("Eastern", "America/New_York"),
                                     ("Pacific", "America/Los_Angeles")])
        topic = rng.choice(["Intro to Distributed Training", "Break Into Product",
                            "Grad School Q&A", "Systems Design Crash Course"])
        body = (f"<p>You're confirmed for <b>{topic}</b> on <b>{phrase_date(rng, d, 'wd_full')}"
                f" at {fmt_time(h, 0)} {tzname} Time</b>. Runs 90 minutes; link to follow.</p>")
        crop, screen = gmail(f"Registration confirmed: {topic}", "Event Desk", body)
        end_h, end_m = (h + 1, 30)
        gold = [ev(topic, iso(d, h), end=iso(d, end_h, end_m), timezone=tziana)]
        tags = ["timezone"]
    elif kind == "internship":
        company = rng.choice(COMPANIES)
        oa = near_date(rng, 4, 10)
        interview = oa + timedelta(days=rng.randint(4, 8))
        ih = rng.choice([10, 14, 15])
        body = (f"<p>Thanks for applying to the {company} SWE Internship (Summer 2027).</p>"
                f"<p>Your online assessment must be completed by <b>{phrase_date(rng, oa, 'wd_full')}"
                f" at 11:59 PM</b>.</p><p>If selected, your final interview is scheduled for"
                f" <b>{phrase_date(rng, interview, 'wd_full')} at {fmt_time(ih, 0)}</b> (45 minutes,"
                f" video call).</p>")
        crop, screen = gmail(f"{company} SWE Intern — next steps", f"{company} Recruiting", body)
        gold = [ev(f"{company} online assessment due", iso(oa, 23, 59), end=iso(oa, 23, 59)),
                ev(f"{company} final interview", iso(interview, ih), end=iso(interview, ih, 45))]
        tags = ["multi_event", "internship"]
    else:
        d1, d2 = near_date(rng, 2, 8), near_date(rng, 9, 16)
        e1 = rng.choice(["Open Mic Night", "Farmers Market on the Plaza", "Career Fair Prep Night"])
        e2 = rng.choice(["Trail Cleanup", "Blood Drive", "Board Game Marathon"])
        v1, v2 = rng.sample(VENUES, 2)
        h1, h2 = rng.choice([18, 19]), rng.choice([10, 11])
        body = (f"<p><b>{e1}</b><br>{phrase_date(rng, d1, 'wd_full')} · {fmt_time(h1, 0)} · {v1}</p>"
                f"<p><b>{e2}</b><br>{phrase_date(rng, d2, 'wd_full')} · {fmt_time(h2, 0)}"
                f" – {fmt_time(h2 + 3, 0)} · {v2}</p>")
        crop, screen = gmail("This Week on Campus", "Campus Events", body)
        gold = [ev(e1, iso(d1, h1), location=v1),
                ev(e2, iso(d2, h2), end=iso(d2, h2 + 3), location=v2)]
        tags = ["multi_event"]
    return dict(id=f"synth1-{idx:03d}-email-{kind}", crop=crop, screen=screen,
                crop_size=(700, 380), page_title="Inbox - Gmail",
                page_url="https://mail.google.com/mail/u/0/#inbox", gold=gold, tags=tags)


def b_webpage(rng, idx):
    kind = rng.choice(["job", "hackathon"])
    if kind == "job":
        company = rng.choice(COMPANIES)
        role = rng.choice(["Software Engineering Intern", "ML Infrastructure Intern",
                           "Embedded Systems Intern"])
        d = near_date(rng, 5, 30)
        deadline = f"{phrase_date(rng, d, 'wd_full')}, 2026 at 11:59 PM CT"
        crop, screen = job_posting(company, role, deadline,
                                   [("Start date", "June 2027"), ("Pay", "$45/hr"),
                                    ("Location", "Austin, TX")])
        gold = [ev(f"{company} {role} application due", iso(d, 23, 59), end=iso(d, 23, 59))]
        tags = ["deadline"]
    else:
        d = near_date(rng, 10, 35)
        # skew to a weekend-feeling overnight event; exact weekday doesn't matter
        d2 = d + timedelta(days=1)
        name = rng.choice(["HackATX", "MakeUT", "DataDash 24hr"])
        venue = rng.choice(VENUES)
        body = (f"<div class='art'><div class='ah'>{name} 2026</div>"
                f"<div class='ab'>36-hour hackathon · free food · $8k in prizes</div>"
                f"<p><b>Kickoff:</b> {phrase_date(rng, d, 'wd_full')} · 10:00 AM · {venue}</p>"
                f"<p><b>Closing ceremony:</b> {phrase_date(rng, d2, 'wd_full')} · 5:00 PM</p>"
                "<p>Teams of up to 4. Beginners welcome.</p></div>")
        crop = page(ARTICLE_CSS, body)
        screen = page(ARTICLE_CSS, "<div style='background:#5b21b6;color:#fff;padding:12px 20px;"
                      f"font-weight:800'>{name.lower()}.io</div>" + body)
        gold = [ev(f"{name} 2026", iso(d, 10), end=iso(d2, 17), location=venue)]
        tags = ["overnight_range"]
    return dict(id=f"synth1-{idx:03d}-web-{kind}", crop=crop, screen=screen,
                crop_size=(680, 340), page_title=f"{kind} page",
                page_url="https://example.org/x", gold=gold, tags=tags)


def b_article_nonevent(rng, idx):
    topic = rng.choice([
        ("Local coffee roasters bet on lighter blends",
         "Tasting rooms across the city report younger customers asking for fruitier profiles."),
        ("The quiet comeback of the campus radio station",
         "Streaming did not kill it; it made the archive the star."),
    ])
    body = (f"<div class='art'><div class='ah'>{topic[0]}</div>"
            f"<div class='ab'>Sep 1, 2026</div><p>{topic[1]}</p>"
            "<p>More reporting to come as the semester unfolds.</p></div>")
    crop = page(ARTICLE_CSS, body)
    screen = page(ARTICLE_CSS, "<div style='background:#111;color:#fff;padding:12px 20px;"
                  "font-weight:800'>THE WIRE</div>" + body)
    return dict(id=f"synth1-{idx:03d}-nonevent-article", crop=crop, screen=screen,
                crop_size=(660, 300), page_title=topic[0],
                page_url="https://thewire.example.com/a", gold=[], tags=["nonevent"])


MIX = [
    (b_timeline, 10),
    (lambda rng, i: b_flyer_single(rng, i, needs_context=False), 9),
    (lambda rng, i: b_flyer_single(rng, i, needs_context=True), 6),
    (b_chat, 9),
    (b_chat_nonevent, 3),
    (b_email, 15),
    (b_webpage, 8),
    (b_article_nonevent, 2),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="synth_v1")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    idx = 0
    total_events = 0
    for builder, count in MIX:
        for _ in range(count):
            idx += 1
            rng = random.Random(args.seed * 10_000 + idx)
            sc = builder(rng, idx)
            out = DATA / args.dest / sc["id"]
            if out.exists() and not args.force:
                print(f"skip {sc['id']}")
                continue
            out.mkdir(parents=True, exist_ok=True)
            render(sc["crop"], out / "crop.png", sc["crop_size"])
            render(sc["screen"], out / "screen.png", (1440, 860))
            case = {
                "id": sc["id"],
                "context": {"now": NOW, "weekday": WEEKDAY, "timezone": TZ,
                            "pageTitle": sc["page_title"], "pageUrl": sc["page_url"]},
                "gold": {"events": sc["gold"]},
                "tags": sc.get("tags", []),
                "verification": {"status": "synthetic", "by": "generator",
                                 "note": "gold derived from generation parameters"},
            }
            (out / "case.json").write_text(json.dumps(case, indent=2))
            total_events += len(sc["gold"])
            print(f"generated {sc['id']} ({len(sc['gold'])} events)")

    print(f"\n{idx} cases, {total_events} events -> data/{args.dest}/")

    from evals.report import build

    build()


if __name__ == "__main__":
    main()
