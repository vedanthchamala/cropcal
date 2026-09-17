"""Training-data generator: realistic, encounterable screens with exact gold.

Every case randomizes the clock ("now"), the user's timezone, the viewport,
the source app, the flyer/email layout, and the phrasing of dates/times, so
the student learns the task rather than one calendar. Gold is derived from
the same parameters that rendered the text. Cases are written in the eval-set
format (crop.png, screen.png, case.json) so the harness can score them.

Usage (from ml/):
  uv run python -m synth.train_gen --count 40 --seed 1 --dest train_smoke
  uv run python -m synth.train_gen --count 4000 --seed 100 --dest train_v1 --workers 6
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import time as _time
from datetime import date, datetime, time, timedelta
from pathlib import Path

from synth import styles as S
from synth.templates_mail import (body_digest, body_headline_cta, body_invite_or, body_listing, body_luma,
                                  body_marketing_centered, body_moved, body_paragraph, body_plain_bullets,
                                  body_sessions, body_visit_days, body_when_where, canvas, gmail, hero)
from synth.templates_social import (DESIGNS, FLYER_CSS, RESET, design_schedule_rows, discord, esc, groupme,
                                    ig_feed, ig_story, imessage, page, photo_bg, slack)

DATA = Path(__file__).resolve().parents[1] / "data"
WEEKDAYS = S.WEEKDAYS
FIRST_NAMES = ["Vedanth", "Maya", "Priya", "Jordan", "Alex", "Sam", "Devon", "Nova", "Rahul", "Chloe", "Marcus", "Ana"]
COMPANIES = ["Meridian Systems", "Cobalt Labs", "Northwind Robotics", "Helios Compute", "Bluegrain AI", "JPMorganChase",
             "Adobe", "Micron", "Saronic", "Bloomberg Engineering", "Capital One", "Dell Technologies"]
SCHOOLS = ["Creighton University", "Florida Atlantic University", "University of Notre Dame", "UNLV", "Rice University",
           "Texas A&M", "Baylor University", "SMU", "University of Houston"]


def ev(title, start, end=None, all_day=False, timezone=None, location=None, description=None, recurrence=None,
       confidence="high", notes=None):
    return {"title": title, "start": start, "end": end, "all_day": all_day, "timezone": timezone,
            "location": location, "description": description, "recurrence": recurrence,
            "confidence": confidence, "notes": notes}


def rand_now(rng: random.Random) -> datetime:
    start = datetime(2025, 8, 15)
    span_days = (datetime(2027, 5, 31) - start).days
    d = start + timedelta(days=rng.randint(0, span_days))
    return d.replace(hour=rng.randint(7, 23), minute=rng.randint(0, 59), second=rng.randint(0, 59))


def season(d: date) -> str:
    if d.month >= 8:
        return f"fall {d.year}"
    if d.month <= 5:
        return f"spring {d.year}"
    return f"summer {d.year}"


def context(now: datetime, tz: str, title: str, url: str) -> dict:
    return {"now": S.fmt_now(now), "weekday": WEEKDAYS[now.weekday()], "timezone": tz,
            "pageTitle": title, "pageUrl": url}


def cap_first(s: str) -> str:
    return s[:1].upper() + s[1:]


# ------------------------------------------------------------------ core event spec

def make_event(rng: random.Random, now: datetime, tz_user: str, *, kind: str | None = None,
               day_offset: tuple[int, int] = (-20, 70), allow_past: bool = True, allow_tz: bool = True,
               venues: list[str] | None = None) -> dict:
    """Random event parameters + every phrasing decision, in one place.
    allow_tz=False for builders that render their own time text without a
    timezone label (gold must never carry a tz the text does not show)."""
    lo, hi = day_offset
    if not allow_past:
        lo = max(lo, 1)
    d = now.date() + timedelta(days=rng.randint(lo, hi))
    kind = kind or rng.choices(["timed", "timed_range", "allday"], weights=[30, 45, 15])[0]
    venues = venues or S.CAMPUS
    spec = {"date": d, "kind": kind, "start": None, "end": None, "end_date": None, "tz_label": "",
            "tz_iana": None, "venue": None, "notes": None, "confidence": "high", "tags": []}
    if kind in ("timed", "timed_range"):
        spec["start"] = S.rand_time(rng, rng.choice(["evening", "evening", "any", "morning", "midday"]))
        if kind == "timed_range":
            dur = rng.choice([60, 60, 90, 120, 120, 150, 180, 240, 360])
            spec["end"], carry = S.add_minutes(spec["start"], dur)
            if carry:
                spec["end_date"] = d + timedelta(days=1)
                spec["tags"].append("crosses_midnight")
        if rng.random() < 0.65:
            spec["venue"] = rng.choice(venues)
    elif kind == "deadline":
        spec["start"] = rng.choices([time(23, 59), time(17, 0), time(12, 0), time(18, 30), time(23, 0), time(11, 59)],
                                    weights=[45, 15, 10, 10, 10, 10])[0]
        spec["end"] = spec["start"]
        spec["tags"].append("deadline")
    elif kind == "deadline_allday":
        spec["tags"] += ["deadline", "all_day"]
    else:
        spec["tags"].append("all_day")
        if rng.random() < 0.5:
            spec["venue"] = rng.choice(venues)
    # timezone suffix on the time (rare); gold tz only when it differs from the user's
    if allow_tz and spec["start"] is not None and kind != "deadline" and rng.random() < 0.07:
        label = rng.choice(["CT", "CDT", "ET", "EDT", "PT", "PDT", "MT", "Central", "Eastern", "Pacific"])
        spec["tz_label"] = f" {label}"
        iana = S.TZ_LABELS[label]
        spec["tz_iana"] = None if iana == tz_user else iana
        spec["tags"].append("timezone_stated")
    return spec


def phrase(rng: random.Random, spec: dict, *, year_prob: float = 0.15, caps: bool = False,
           style: str | None = None) -> dict:
    """Text for date/time/venue + flags about what is visible."""
    d = spec["date"]
    show_year = rng.random() < year_prob
    fake_wd = None
    weekday_mode = rng.choice(["yes", "yes", "no"])
    if weekday_mode == "yes" and rng.random() < 0.0:  # disabled: teacher resolves such conflicts from context, not a fixed rule
        fake_wd = WEEKDAYS[(d.weekday() + rng.choice([-1, 1, 2])) % 7]
    style = style or rng.choice(["full", "full", "abbr", "sept", "abbr_dot", "slash", "dot", "ord_full", "ord_sup", "ord_abbr",
                                 "abbr_comma_wd", "wd_after"])  # no ISO / day-month-year on social flyers
    if fake_wd:
        core = S.date_text(rng, d, year=show_year, weekday="no", style=style, caps=caps)
        date_txt = f"{fake_wd.upper() if caps else fake_wd}, {core}"
        spec["tags"].append("weekday_mismatch")
        spec["confidence"] = "low"
        spec["notes"] = f"flyer says {fake_wd} but {d.strftime('%B %-d')} is a {WEEKDAYS[d.weekday()]}; used the date"
    else:
        date_txt = S.date_text(rng, d, year=show_year, weekday=weekday_mode, style=style, caps=caps)
    time_txt = ""
    if spec["start"] is not None:
        time_txt = S.time_text(rng, spec["start"], spec["end"] if spec["kind"] != "deadline" else None,
                               tz_label=spec["tz_label"])
        if caps:
            time_txt = time_txt.upper()
    elif spec["kind"] == "allday" and rng.random() < 0.15:
        time_txt = rng.choice(["Time TBA", "time TBD", "all day"])
        spec["tags"].append("time_tba")
    venue_txt = spec["venue"] or ""
    if caps:
        venue_txt = venue_txt.upper()
    return {"date_txt": date_txt, "time_txt": time_txt, "venue_txt": venue_txt, "year_shown": show_year}


def gold_for(spec: dict, title: str, *, description: str | None = None, location_override=None,
             recurrence: str | None = None, notes_extra: str | None = None) -> dict:
    d = spec["date"]
    if spec["kind"] in ("allday", "deadline_allday"):
        start = S.iso(d)
        end = S.iso(spec["end_date"]) if spec.get("end_date") else None
        all_day = True
    else:
        start = S.iso(d, spec["start"])
        end = S.iso(spec.get("end_date") or d, spec["end"]) if spec["end"] else None
        all_day = False
    loc = None if spec["kind"] in ("deadline", "deadline_allday") else (spec["venue"] if location_override is None else location_override)
    notes = "; ".join(x for x in [spec.get("notes"), notes_extra] if x) or None
    return ev(title, start, end, all_day, spec["tz_iana"], loc, description, recurrence, spec["confidence"], notes)


def past_note(spec: dict, now: datetime, cue: str) -> None:
    if spec["date"] < now.date():
        spec["tags"].append("past_date")
        spec["notes"] = "; ".join(x for x in [spec.get("notes"), f"year inferred from {cue}"] if x)


# ------------------------------------------------------------------ scenario builders
# each returns dict(html, target, gold, tags, page_title, page_url, kind, screen_kind)

def flyer_spec(rng, org, title, ph, extras, *, label=None, season_txt=""):
    return {"org": org, "title": title, "kicker": rng.choice(S.KICKERS), "date_txt": ph["date_txt"],
            "time_txt": ph["time_txt"], "venue_txt": ph["venue_txt"], "extras": extras,
            "palette": rng.choice(S.PALETTES), "font_d": rng.choice(S.FONTS_DISPLAY), "font_b": rng.choice(S.FONTS_BODY),
            "qr": rng.random() < 0.35, "label": label, "season": season_txt}


def s_ig_flyer(rng, now, tz):
    org, handle, desc = rng.choice(S.ORGS)
    is_deadline = rng.random() < 0.22
    posted = now - timedelta(hours=rng.randint(1, 24 * 21))
    spec = make_event(rng, posted, tz, kind=rng.choice(["deadline", "deadline_allday"]) if is_deadline else None,
                      day_offset=(0, 45), venues=S.CAMPUS)
    caps = rng.random() < 0.5
    ph = phrase(rng, spec, caps=caps)
    if is_deadline:
        name = rng.choice(S.DEADLINE_NAMES)
        design = rng.choice(["big_date", "minimal", "bullets"])
        extras = [rng.choice(["DM us with any questions!", "Link in bio", "Apply at the link in our bio", "Questions? DM us"])]
        title = f"{org} {name}" if name[0].isupper() else f"{org} — {name} {ph['date_txt']}"
        title = f"{org} {rng.choice(['Application Deadline', 'Applications Due', 'Registration Deadline'])}"
        fs = flyer_spec(rng, org, name.upper() if design != 'big_date' else title, ph, extras,
                        label=rng.choice(["APPLICATION DEADLINE:", "APPLICATIONS DUE", "DEADLINE TO REGISTER", "APPLY BY"]),
                        season_txt=rng.choice(["", f"{spec['date'].year}-{spec['date'].year + 1}", season(spec['date']).upper()]))
        if design == "big_date":
            fs["title"] = ""
    else:
        name = rng.choice(S.EVENT_NAMES)
        design = rng.choice([k for k in DESIGNS if k not in ("retro",)])
        extras = rng.sample(["OPEN TO EVERYONE!", "FREE FOOD", "Free Canes!", "All majors welcome", "Bring a friend",
                             "No experience needed", "RSVP in bio", "Snacks provided", "Free pizza 🍕", "Merch giveaway"], 2)
        if rng.random() < 0.5:
            extras = extras[:1]
        title = f"{org} {name}"
        fs = flyer_spec(rng, org, name, ph, extras, season_txt=rng.choice(["", season(spec['date']).upper()]))
    media_html = f"<div style='width:100%;height:100%'>{DESIGNS[design](rng, fs)}</div>"
    age = S.age_label(rng, now, posted)
    rel = S.relative_phrase(rng, now, spec["date"])
    when_words = rel if rel and rng.random() < 0.6 else (S.date_text(rng, spec["date"], weekday="yes") if rng.random() < 0.5 else "")
    tt = S.time_text(rng, spec["start"], None) if spec["start"] else ""
    caption_opts = [
        f"{esc(org)} {season(spec['date'])} recruitment is HERE. We're a {desc} — no experience needed. Questions? DM us. 🤘",
        f"Come join us for our {esc(name.lower())} to kick off this semester! Make new friends and meet the team {when_words} {tt}".strip(),
        f"{esc(name)} is {when_words}!!" if when_words else f"{esc(name)} — see you there!",
        f"Interested in joining our team? Stop by {when_words} {tt}".strip(),
        "What's happening this week? 📣", "🚀 Big things coming. Details on the flyer.",
        f"Stop by our booth at {esc(name)} {when_words} {tt}! 🚀💫".strip(),
    ]
    caption = rng.choice(caption_opts)
    html = ig_feed(rng, media_html, handle, age, caption, likes=rng.choice([None, rng.randint(20, 400)]),
                   prev_caption=rng.choice(["Another day at work 💪", "Okaay cool & unexpected!", "Congratulations to the 2027 National Merit Semifinalists!", ""]),
                   next_handle=rng.choice(["rudy.arora", "nn.jen", "getnavan", "teamcongo.rdc", ""]),
                   media_h=rng.choice([470, 470, 588, 540]))
    past_note(spec, now, "post age")
    description = "; ".join(cap_first(x.lower()) if x.isupper() else x for x in extras) if (extras and design in ("bullets", "two_col", "minimal")) else None
    gold = gold_for(spec, title, description=description)
    tags = ["ig_feed", design] + spec["tags"] + (["needs_context"] if design in ("big_date", "pill_location", "poster_banner", "two_col", "plain_card", "bullets", "minimal") else [])
    return dict(html=html, target="#tgt", gold=[gold], tags=tags, page_title="Instagram", page_url="https://www.instagram.com/?hl=en", kind="ig_flyer")


def s_ig_schedule(rng, now, tz):
    org, handle, desc = rng.choice(S.ORGS)
    posted = now - timedelta(hours=rng.randint(2, 24 * 10))
    n = rng.randint(2, 5)
    d = posted.date() + timedelta(days=rng.randint(0, 6))
    rows, gold = [], []
    names = rng.sample(["Info Session 1", "Info Session 2", "Open House", "Coffee Chats", "Applications Due", "Applications Close",
                        "Tech Talk", "Interviews", "Decisions Released", "Kickoff Social", "Open Garage", "New Member Orientation",
                        "Lobby Day", "Workshop", "Resume Review"], n)
    dstyle = rng.choice(["slash", "abbr", "sept", "full"])
    for name in names:
        d = d + timedelta(days=rng.randint(1, 4))
        if "Due" in name or "Close" in name:
            spec = {"date": d, "kind": "deadline", "start": time(23, 59), "end": time(23, 59), "end_date": None,
                    "tz_label": "", "tz_iana": None, "venue": None, "notes": None, "confidence": "high", "tags": ["deadline"]}
            rows.append({"date_txt": S.date_text(rng, d, style=dstyle, weekday=rng.choice(["yes", "no"])), "name": name, "time_txt": "11:59 PM"})
        elif name in ("Decisions Released", "Interviews"):
            spec = {"date": d, "kind": "allday", "start": None, "end": None, "end_date": None, "tz_label": "", "tz_iana": None,
                    "venue": None, "notes": None, "confidence": "high", "tags": ["all_day"]}
            rows.append({"date_txt": S.date_text(rng, d, style=dstyle, weekday=rng.choice(["yes", "no"])), "name": name})
        else:
            spec = make_event(rng, posted, tz, kind="timed_range", day_offset=(0, 0), allow_tz=False)
            spec["date"] = d
            spec["venue"] = rng.choice(S.CAMPUS)
            rows.append({"date_txt": S.date_text(rng, d, style=dstyle, weekday=rng.choice(["yes", "no"])), "name": name,
                         "time_txt": S.time_text(rng, spec["start"], spec["end"], style="tight"), "venue_txt": spec["venue"]})
        past_note(spec, now, "post age")
        gold.append(gold_for(spec, f"{org} {name}"))
    fs = {"org": org, "title": rng.choice([f"{season(d)} recruitment", "this week", "recruitment timeline", "what's next"]).upper(),
          "kicker": org if rng.random() < 0.6 else season(d), "rows": rows, "palette": rng.choice(S.PALETTES),
          "font_d": rng.choice(S.FONTS_DISPLAY), "font_b": rng.choice(S.FONTS_BODY)}
    media = f"<div style='width:100%;height:100%'>{design_schedule_rows(rng, fs)}</div>"
    caption = rng.choice([f"{esc(org)} {season(d)} recruitment is HERE 🤘 We're a {desc} — no experience needed.",
                          "What's happening this week? 📣", f"Mark your calendars — {esc(org)} is back for {season(d)}."])
    html = ig_feed(rng, media, handle, S.age_label(rng, now, posted), caption, media_h=588)
    return dict(html=html, target="#tgt", gold=gold, tags=["ig_feed", "schedule", "multi_event", "needs_context"],
                page_title="Instagram", page_url="https://www.instagram.com/?hl=en", kind="ig_schedule")


def s_ig_story(rng, now, tz):
    org, handle, desc = rng.choice(S.ORGS)
    posted = now - timedelta(hours=rng.randint(1, 23))
    spec = make_event(rng, posted, tz, day_offset=(0, 40), kind=rng.choice(["timed", "timed_range", "timed_range", "deadline", "allday"]), venues=S.CAMPUS)
    ph = phrase(rng, spec)
    name = rng.choice(S.EVENT_NAMES) if spec["kind"] not in ("deadline", "deadline_allday") else rng.choice(["Applications Due", "Apps close"])
    title_pill = f"<span class='stx' style='font-size:24px'>{esc(org)} · {esc(name)}</span>"
    body_pill = (f"<span class='stx' style='font-size:20px'>{rng.choice(['📅 ', '', '🗓 '])}{ph['date_txt']}"
                 + (f"<br>{rng.choice(['⏰ ', '🕕 ', ''])}{ph['time_txt']}" if ph['time_txt'] else "")
                 + (f"<br>📍 {ph['venue_txt']}" if ph['venue_txt'] else "") + "</span>")
    blocks = [title_pill, f"<div id='tgt' style='display:inline-block'>{body_pill}</div>"]
    if rng.random() < 0.5:
        blocks.append(f"<span class='stx' style='font-size:16px'>{rng.choice(['these often lead to interviews', 'free food 🍕', 'bring a friend!', 'link in bio to RSVP'])}</span>")
    html = ig_story(rng, handle, S.age_label(rng, now, posted), blocks)
    past_note(spec, now, "story age")
    gold = gold_for(spec, f"{org} {name}")
    return dict(html=html, target="#tgt", gold=[gold], tags=["ig_story", "needs_context"] + spec["tags"],
                page_title="Stories • Instagram", page_url=f"https://www.instagram.com/stories/{handle}/{rng.randint(10**18, 10**19)}/", kind="ig_story")


def email_when(rng, now):
    sent = now - timedelta(hours=rng.randint(1, 24 * 12))
    if (now - sent) < timedelta(hours=24):
        w = f"{sent.hour % 12 or 12}:{sent.minute:02d} {'AM' if sent.hour < 12 else 'PM'} ({max(1, int((now - sent).total_seconds() // 3600))} hours ago)"
    else:
        w = f"{WEEKDAYS[sent.weekday()][:3]}, {S.MON_ABBR[sent.month - 1]} {sent.day}, {sent.hour % 12 or 12}:{sent.minute:02d} {'AM' if sent.hour < 12 else 'PM'} ({(now - sent).days} days ago)"
    return sent, w


def s_gmail_marketing(rng, now, tz):
    school = rng.choice(SCHOOLS)
    sent, when = email_when(rng, now)
    spec = make_event(rng, sent, tz, kind=rng.choice(["timed", "timed_range"]), day_offset=(1, 60))
    spec["venue"] = rng.choice(S.OFFCAMPUS)
    if spec["start"].hour < 9 or spec["start"].hour > 19:
        spec["start"] = time(rng.choice([18, 18, 19, 10]), rng.choice([0, 30]))
        if spec["end"]:
            spec["end"], _ = S.add_minutes(spec["start"], rng.choice([60, 90, 120]))
    ph = phrase(rng, spec, year_prob=0.5)
    name = rng.choice([f"{school.split()[0]} on the Road", "Preview Day", "Admitted Students Reception", "Regional Info Session", "Engineering Open House"])
    venue_lines = spec["venue"].split(", ")
    body = body_marketing_centered(rng, f"{school} Office of Undergraduate Admissions", f"Dear {rng.choice(FIRST_NAMES)},",
                                   f"You and your family are invited to an <b><i>{esc(name)}</i></b> event presented by {esc(school)} Admissions. The event will include information on academic, community, and spiritual life, as well as insights into the admissions and financial aid processes.",
                                   [ph["date_txt"], ph["time_txt"]], venue_lines, "Register Here", rng.choice(["#0b2545", "#7a1f1f", "#00274c", "#4b2e83"]))
    html = gmail(rng, f"You're invited: {name}", f"{school} Admissions", f"admissions@{school.split()[0].lower()}.edu", when, body, dark_columns=rng.random() < 0.5)
    gold = gold_for(spec, f"{school} {name}")
    return dict(html=html, target="#tgt", gold=[gold], tags=["gmail", "marketing"] + spec["tags"] + (["needs_context"]),
                page_title="Inbox - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox", kind="gmail_marketing")


def s_gmail_bullets(rng, now, tz):
    company = rng.choice(COMPANIES)
    sent, when = email_when(rng, now)
    n = rng.randint(2, 4)
    bullets, specs = [], []
    d = sent.date() + timedelta(days=rng.randint(1, 5))
    for _ in range(n):
        d = d + timedelta(days=rng.randint(2, 9))
        spec = make_event(rng, sent, tz, kind="timed_range", day_offset=(0, 0), allow_tz=False)
        spec["date"] = d
        spec["venue"] = None
        spec["start"] = S.rand_time(rng, "any")
        spec["end"], _ = S.add_minutes(spec["start"], 60)
        style = rng.choice(["ord_sup", "ord_full", "full"])
        bullets.append(f"{S.date_text(rng, d, style=style, weekday='yes')}: {S.time_text(rng, spec['start'], spec['end'], style=rng.choice(['tight', 'spaced']))}")
        specs.append(spec)
    ti = rng.randrange(n)
    program = rng.choice(["Code for Good Hackathon - Software Engineer Program - 2027 Summer Internship", "Software Engineering Internship (Summer 2027)", "Early Insights Program"])
    body = body_plain_bullets(rng, "Good morning,",
                              [f"Thank you for applying to the {esc(program)} and for your interest in {esc(company)}. We wanted to provide a quick update that applications are currently under review.",
                               "If you have any quick questions, I will be hosting optional office hours on the following dates:"],
                              bullets, ti, "Attendance is completely optional, and you're welcome to join any session that fits your schedule.",
                              f"Best regards,<br>{esc(rng.choice(['Paola Ortiz', 'Dana Whitfield', 'Kevin Tran']))}")
    html = gmail(rng, f"{company} — office hours", f"{company.lower().split()[0]} campus sourcing", f"campus.sourcing@{company.lower().split()[0]}.com", when, body, search=rng.choice(["", "dates", "9/"]))
    spec = specs[ti]
    past_note(spec, now, "email date")
    gold = gold_for(spec, f"{company} office hours")
    return dict(html=html, target="#tgt", gold=[gold], tags=["gmail", "bullets", "needs_context"] + spec["tags"],
                page_title="Inbox - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox", kind="gmail_bullets", jitter="tight")


def s_gmail_luma(rng, now, tz):
    sent, when = email_when(rng, now)
    spec = make_event(rng, sent, tz, kind="timed_range", day_offset=(1, 30), allow_tz=False)
    spec["end"], _ = S.add_minutes(spec["start"], rng.choice([60, 60, 90, 120]))
    spec["venue"] = rng.choice(["Zoom", "Google Meet", "Zoom", rng.choice(S.STARTUP)])
    tz_label = rng.choice(["CDT", "CST", "EDT", "PDT", "CT", "ET", ""]) if rng.random() < 0.8 else ""
    spec["tz_label"] = f" {tz_label}" if tz_label else ""
    if tz_label:
        iana = S.TZ_LABELS[tz_label]
        spec["tz_iana"] = None if iana == tz else iana
        spec["tags"].append("timezone_stated")
    host = rng.choice(["Neha Varshneya", "Moss", "Luma Events", "Arturo Piña", "Sarah Chen"])
    title = rng.choice(["Built with Moss: How Aside Gives AI Agents Memory", "Founders Fireside: Seed to Series A", "Intro to RAG Systems",
                        "Design Systems at Scale", "Austin RAW Conversations", "Hardware Happy Hour"])
    d = spec["date"]
    body = body_luma(rng, host, title, S.MON_ABBR[d.month - 1].upper(), d.day, S.date_text(rng, d, style="full", weekday="yes"),
                     S.time_text(rng, spec["start"], spec["end"], style="spaced", tz_label=spec["tz_label"]), spec["venue"],
                     "AI agents are getting better at doing things, but remembering what they did is still a challenge. Join us for a live demo and Q&A.")
    html = gmail(rng, f"You're invited to {title}", host, f"usr-{rng.randint(1000, 9999)}@user.luma-mail.com", when, body, unsubscribe=True)
    gold = gold_for(spec, title)
    return dict(html=html, target="#tgt", gold=[gold], tags=["gmail", "luma", "needs_context"] + spec["tags"],
                page_title="Inbox - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox", kind="gmail_luma")


def s_gmail_when_where(rng, now, tz):
    brand = rng.choice(COMPANIES)
    sent, when = email_when(rng, now)
    spec = make_event(rng, sent, tz, kind="timed_range", day_offset=(1, 30), allow_tz=False)
    spec["end"], _ = S.add_minutes(spec["start"], rng.choice([60, 60, 90, 120, 150]))
    d = spec["date"]
    fmt = rng.choice(["dmy", "iso_like", "full"])
    dtxt = S.date_text(rng, d, style=fmt, year=True, weekday='no')
    t1, t2 = S.time_pair(rng, spec["start"], spec["end"])
    when_txt = f"{dtxt} {t1} - {dtxt} {t2}"
    where_kind = rng.choice(["link", "venue", "platform"])
    if where_kind == "link":
        where_txt, spec["venue"] = "<a>Event Link</a>", None
    elif where_kind == "platform":
        spec["venue"] = rng.choice(["Zoom", "Microsoft Teams"]); where_txt = spec["venue"]
    else:
        spec["venue"] = rng.choice(S.CAMPUS + S.OFFCAMPUS); where_txt = esc(spec["venue"])
    body = body_when_where(rng, brand, rng.choice(FIRST_NAMES), when_txt, where_txt, rng.choice(["No organizer", "Talent Acquisition", brand]), rng.choice(["#e11d2b", "#0a66c2", "#111"]))
    title = rng.choice([f"{brand} event", f"{brand} virtual info session", f"{brand} campus event"])
    html = gmail(rng, f"{brand}: We look forward to seeing you!", f"{brand} Talent", f"noreply@{brand.lower().split()[0]}.com", when, body, dark_columns=True)
    gold = gold_for(spec, title)
    return dict(html=html, target="#tgt", gold=[gold], tags=["gmail", "when_where", "explicit_year", "needs_context"] + spec["tags"],
                page_title="Inbox - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox", kind="gmail_when_where")


def s_gmail_listing(rng, now, tz):
    sent, when = email_when(rng, now)
    n = rng.randint(2, 3)
    rows, specs = [], []
    for _ in range(n):
        spec = make_event(rng, sent, tz, kind=rng.choice(["allday", "allday", "timed"]), day_offset=(3, 90), allow_tz=False)
        if spec["start"]:
            spec["start"] = time(rng.choice([19, 19, 20, 21]), rng.choice([0, 30]))
        spec["venue"] = rng.choice(S.CONCERT)
        artist = rng.choice(["Suki Waterhouse", "Wave To Earth", "Men I Trust", "Khruangbin", "Laufey", "Clairo", "Cigarettes After Sex"])
        dt = S.date_text(rng, spec["date"], style="abbr_comma_wd")
        if spec["start"]:
            dt += f" · {S.time_text(rng, spec['start'], None, style='spaced')}"
        rows.append({"name": artist, "date_txt": dt, "desc": f"{rng.choice(['KXT Presents', 'Live Nation Presents', 'C3 Presents'])} - {artist}: The {rng.choice(['Loveland', 'Daydream', 'Midnight'])} Tour at {spec['venue']}"})
        specs.append((spec, artist))
    ti = rng.randrange(n)
    spec, artist = specs[ti]
    body = body_listing(rng, "Live Nation", rows, ti)
    html = gmail(rng, "Just for you: shows near Austin", "Live Nation Concerts", "reply@email.livenation.com", when, body, unsubscribe=True, search=rng.choice(["", "9/"]))
    gold = gold_for(spec, f"{artist}: The {rows[ti]['desc'].split('The ')[1].split(' Tour')[0]} Tour")
    return dict(html=html, target="#tgt", gold=[gold], tags=["gmail", "listing", "needs_context"] + spec["tags"],
                page_title="Inbox - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox", kind="gmail_listing", jitter="tight")


def s_gmail_headline(rng, now, tz):
    school = rng.choice(SCHOOLS)
    sent, when = email_when(rng, now)
    spec = make_event(rng, sent, tz, kind="deadline_allday", day_offset=(10, 90))
    name = rng.choice(FIRST_NAMES)
    dl = S.date_text(rng, spec["date"], style="full", weekday="no")
    two = rng.random() < 0.5
    gold = [gold_for(spec, f"{school} application deadline")]
    if two:
        d2 = spec["date"] + timedelta(days=rng.randint(30, 60))
        spec2 = {"date": d2, "kind": "allday", "start": None, "end": None, "end_date": None, "tz_label": "", "tz_iana": None,
                 "venue": None, "notes": None, "confidence": "medium", "tags": ["all_day"]}
        headline = f"{esc(name)}, apply to {esc(school)} by <span style='color:#d9534f'>{dl}</span> and get a decision on {S.date_text(rng, d2, style='full', weekday='no')}!"
        gold.append(gold_for(spec2, f"{school} admission decision"))
    else:
        headline = f"{esc(name)}, apply to {esc(school)} by <span style='color:#d9534f'>{dl}</span>{rng.choice([' — no application fee!', '!', ' to be considered for early scholarships!'])}"
    body = body_headline_cta(rng, f"{school} Office of Undergraduate Admissions", headline, f"Apply to {school}", "#c8102e")
    html = gmail(rng, f"{name}: Apply by {S.MON_ABBR[spec['date'].month - 1]} {spec['date'].day}", f"{school.split()[0]} Admissions", f"admissions@{school.split()[0].lower()}.edu", when, body, unsubscribe=True, search=rng.choice(["", "dates"]))
    return dict(html=html, target="#tgt", gold=gold, tags=["gmail", "headline", "deadline"] + (["multi_event"] if two else []),
                page_title="Inbox - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox", kind="gmail_headline")


def s_gmail_visit_days(rng, now, tz):
    school = rng.choice(SCHOOLS)
    sent, when = email_when(rng, now)
    groups, gold = [], []
    d = sent.date() + timedelta(days=rng.randint(7, 20))
    tzl = rng.choice(["", " CT", " CT", " ET"])
    target_group = rng.randrange(2)
    for gi, gname in enumerate(rng.sample(["Preview Day", "Campus Visit Day", "Engineering Visit Day", "Honors Preview", "Transfer Visit Day", "Admitted Students Day"], 2)):
        k = 1 if gi == 0 else rng.randint(2, 4)
        st = S.rand_time(rng, "morning")
        en, _ = S.add_minutes(st, rng.choice([240, 270, 330]))
        dates = []
        for _ in range(k):
            d = d + timedelta(days=rng.randint(1, 12))
            dates.append(d)
        target = gi == target_group
        groups.append({"name": gname, "date_lines": [S.date_text(rng, x, style="full", weekday="yes", wd_sep=", ", wd_form="long") for x in dates],
                       "time_line": S.time_text(rng, st, en, style="spaced", tz_label=tzl), "target": target})
        if target:
            for x in dates:
                spec = {"date": x, "kind": "timed_range", "start": st, "end": en, "end_date": None, "tz_label": tzl,
                        "tz_iana": (None if not tzl or S.TZ_LABELS[tzl.strip()] == tz else S.TZ_LABELS[tzl.strip()]),
                        "venue": school, "notes": None, "confidence": "high", "tags": []}
                gold.append(gold_for(spec, f"{school} {gname}"))
    body = body_visit_days(rng, f"Hi {rng.choice(FIRST_NAMES)},", f"We're thrilled to invite you and your family to join us this fall for a firsthand experience of life at {esc(school)}! Choose from these visit options:", groups, "Register for a fall event", "#0b2545")
    html = gmail(rng, f"Visit {school} this fall", f"{school} Admissions", f"visit@{school.split()[0].lower()}.edu", when, body, dark_columns=True, search=rng.choice(["", "dates"]))
    tags = ["gmail", "visit_days", "needs_context"] + (["multi_event"] if len(gold) > 1 else []) + (["timezone_stated"] if tzl else [])
    return dict(html=html, target="#tgt", gold=gold, tags=tags, page_title="Inbox - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox", kind="gmail_visit_days")


def s_gmail_moved(rng, now, tz):
    sent, when = email_when(rng, now)
    spec = make_event(rng, sent, tz, kind="timed_range", day_offset=(3, 30), allow_tz=False)
    spec["start"] = time(rng.choice([17, 18, 18, 19]), rng.choice([0, 30]))
    spec["end"], _ = S.add_minutes(spec["start"], rng.choice([90, 120, 120]))
    spec["venue"] = rng.choice(["STATION Austin | ACL Room", "Capital Factory, 16th floor", "The Riveter", "Gregory Gym Annex"])
    title = rng.choice(["Austin RAW Conversations", "Founders Breakfast", "Monthly Demo Night", "Startup Office Hours"])
    dline = f"{S.date_text(rng, spec['date'], style='full', weekday='yes')} | {S.time_text(rng, spec['start'], spec['end'], style='spaced')}"
    body = body_moved(rng, rng.choice(["Arturo Pina", "Jess Ramos", "Neil Patel"]), rng.choice(["ATX Startup Network", "Austin Founders", "Texas Product Guild"]), title,
                      f"has moved to {S.date_text(rng, spec['date'], style='full', weekday='yes')}.", spec["venue"], dline)
    html = gmail(rng, f"Update: {title} has moved", "Meetup", "info@meetup.com", when, body)
    gold = gold_for(spec, title, location_override=spec["venue"].replace(" | ", ", "))
    return dict(html=html, target="#tgt", gold=[gold], tags=["gmail", "moved", "rescheduled", "needs_context"] + spec["tags"],
                page_title="Inbox - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox", kind="gmail_moved")


def s_gmail_sessions(rng, now, tz):
    school = rng.choice(SCHOOLS)
    sent, when = email_when(rng, now)
    explicit = rng.random() < 0.7
    if explicit:
        d = sent.date() + timedelta(days=rng.randint(2, 14))
        footer = f"Schedule for {S.date_text(rng, d, style='full', weekday='yes')}"
        conf, note = "high", None
    else:
        days_ahead = (7 - now.weekday()) % 7 or 7
        d = now.date() + timedelta(days=days_ahead)
        footer = "We hope to see you next Monday!"
        conf, note = "low", "date resolved from 'next Monday' relative to the current date"
    blocks, specs = [], []
    t = time(9, 0)
    for _ in range(rng.randint(3, 4)):
        en, _ = S.add_minutes(t, 60)
        blocks.append({"time_txt": S.time_text(rng, t, en, style="dash_long"), "items": rng.sample(["Honors College", "College of Education", "School of Public Health", "College of Hospitality", "Lee Business School", "College of Fine Arts", "College of Engineering", "College of Sciences and Pre-Professional Advising Center", "School of Nursing", "College of Liberal Arts"], rng.randint(3, 4))})
        specs.append((t, en))
        t, _ = S.add_minutes(en, rng.choice([30, 60]))
    ti = rng.randrange(len(blocks))
    st, en = specs[ti]
    spec = {"date": d, "kind": "timed_range", "start": st, "end": en, "end_date": None, "tz_label": "", "tz_iana": None,
            "venue": None, "notes": note, "confidence": conf, "tags": []}
    body = body_sessions(rng, blocks, ti, footer) if explicit else body_sessions(rng, blocks, ti, footer)
    if explicit:
        body = f"<p style='text-align:center;font-weight:700'>{footer}</p>" + body
    html = gmail(rng, f"{school} Visit Day schedule", f"{school} Admissions", f"visit@{school.split()[0].lower()}.edu", when, body, dark_columns=True, search=rng.choice(["", "9/"]))
    gold = gold_for(spec, f"{school} sessions: {', '.join(blocks[ti]['items'])}")
    return dict(html=html, target="#tgt", gold=[gold], tags=["gmail", "sessions", "needs_context"] + (["relative_date", "ambiguous"] if not explicit else []),
                page_title="Inbox - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox", kind="gmail_sessions", jitter="tight")


def s_gmail_or(rng, now, tz):
    school = rng.choice(SCHOOLS)
    sent, when = email_when(rng, now)
    d1 = sent.date() + timedelta(days=rng.randint(5, 20))
    d2 = d1 + timedelta(days=1)
    timed = rng.random() < 0.4
    st = S.rand_time(rng, "any") if timed else None
    venue = rng.choice(["Starbucks, 4169 Lyndon B Johnson Fwy, Dallas, TX 75244", "Panera Bread, 2900 Guadalupe St, Austin, TX", "Houndstooth Coffee, 401 Congress Ave, Austin, TX"])
    vlines = venue.split(", ", 1)
    sep, form = rng.choice([", ", " | "]), rng.choice(["long", "short"])
    lines = [S.date_text(rng, x, style="full", weekday="yes", caps=True, wd_sep=sep, wd_form=form) for x in (d1, d2)]
    if timed:
        lines = [f"{l} at {S.time_text(rng, st, None, style='spaced')}" for l in lines]
    body = body_invite_or(rng, f"Hi {rng.choice(FIRST_NAMES)},",
                          f"I wanted to reach out and personally invite you to schedule an in-person <a>Connect to {esc(school.split()[0])} Informational Interview</a> with me while I'm in your area.",
                          lines, [vlines[0], vlines[1] if len(vlines) > 1 else ""], "Schedule your meeting time now.",
                          "This 30-minute meeting is your chance to receive personalized guidance about the admission process, scholarships, and campus life.", rng.choice(["Jonathan", "Maria", "Devin"]))
    html = gmail(rng, f"Connect to {school.split()[0]} — let's meet", f"{rng.choice(['Jonathan Zavaleta', 'Maria Lopez'])}, {school}", f"admissions@{school.split()[0].lower()}.edu", when, body)
    gold = []
    for d in (d1, d2):
        if timed:
            en, _ = S.add_minutes(st, 30)
            spec = {"date": d, "kind": "timed_range", "start": st, "end": en, "end_date": None, "tz_label": "", "tz_iana": None, "venue": venue, "notes": "one of two alternative dates offered; 30-minute meeting", "confidence": "medium", "tags": []}
        else:
            spec = {"date": d, "kind": "allday", "start": None, "end": None, "end_date": None, "tz_label": "", "tz_iana": None, "venue": venue, "notes": "one of two alternative dates offered; by appointment, time not stated", "confidence": "medium", "tags": []}
        gold.append(gold_for(spec, f"{school} informational interview"))
    return dict(html=html, target="#tgt", gold=gold, tags=["gmail", "alternatives", "multi_event", "needs_context"] + ([] if timed else ["all_day"]),
                page_title="Inbox - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox", kind="gmail_or")


def s_gmail_digest(rng, now, tz):
    sent, when = email_when(rng, now)
    items, specs = [], []
    for _ in range(rng.randint(2, 3)):
        spec = make_event(rng, sent, tz, kind=rng.choice(["timed", "timed_range"]), day_offset=(1, 12), allow_tz=False)
        spec["venue"] = rng.choice(S.CAMPUS)
        name = rng.choice(["Open Mic Night", "Farmers Market on the Plaza", "Career Fair Prep Night", "Trail Cleanup", "Blood Drive", "Board Game Marathon", "Live at the Union: The Midnight Hour", "Yoga on the Lawn"])
        items.append({"name": name, "line": f"{S.date_text(rng, spec['date'], style='full', weekday='yes')} · {S.time_text(rng, spec['start'], spec['end'], style='spaced')} · {esc(spec['venue'])}",
                      "extra": rng.choice(["Free with student ID.", "Gloves provided.", "", "Snacks provided."])})
        specs.append((spec, name))
    ti = rng.randrange(len(items))
    body = body_digest(rng, rng.choice(["This Week at the Union", "This Week on Campus", "Weekend Roundup"]), items, ti)
    html = gmail(rng, "This Week at the Union", "Texas Union Events", "events@union.utexas.edu", when, body)
    spec, name = specs[ti]
    gold = gold_for(spec, name, description=items[ti]["extra"] or None)
    return dict(html=html, target="#tgt", gold=[gold], tags=["gmail", "digest", "needs_context"] + spec["tags"],
                page_title="Inbox - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox", kind="gmail_digest", jitter="tight")


def s_gmail_confirmation(rng, now, tz):
    sent, when = email_when(rng, now)
    spec = make_event(rng, sent, tz, kind="timed", day_offset=(2, 25))
    label, iana = rng.choice([("Eastern", "America/New_York"), ("Pacific", "America/Los_Angeles"), ("Central", "America/Chicago"), ("Mountain", "America/Denver")])
    spec["tz_iana"] = None if iana == tz else iana
    spec["tags"].append("timezone_stated")
    dur = rng.choice([60, 90, 45, 30])
    spec["end"], _ = S.add_minutes(spec["start"], dur)
    spec["tags"].append("stated_duration")
    spec["venue"] = rng.choice(["Zoom", "Google Meet", None])
    topic = rng.choice(["Intro to Distributed Training", "Break Into Product", "Grad School Q&A", "Systems Design Crash Course", "Intro to RAG Systems"])
    body = body_paragraph(rng, [f"Hi {rng.choice(FIRST_NAMES)},",
                                f"You're confirmed for <b>{esc(topic)}</b> on <span id='tgt'><b>{S.date_text(rng, spec['date'], style='full', weekday='yes')} at {S.time_text(rng, spec['start'], None, style='spaced')} {label} Time</b></span>. "
                                f"The session runs {dur} minutes; " + ("a Zoom link will follow the day before." if spec["venue"] == "Zoom" else "a Google Meet link will follow." if spec["venue"] else "dial-in details to follow."),
                                "See you there!<br>Event Desk"])
    html = gmail(rng, f"Registration confirmed: {topic}", "Event Desk", "no-reply@eventdesk.org", when, body)
    gold = gold_for(spec, f"{topic} webinar")
    return dict(html=html, target="#tgt", gold=[gold], tags=["gmail", "confirmation"] + spec["tags"],
                page_title="Inbox - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox", kind="gmail_confirmation")


def s_canvas(rng, now, tz):
    school = rng.choice(["The University Of Texas at Austin", "Texas A&M University", "Arizona State University"])
    n_ann = rng.randint(1, 2)
    anns, gold, tags = [], [], ["canvas"]
    d_base = now.date()
    target_done = False
    for i in range(n_ann):
        d = d_base + timedelta(days=rng.randint(1, 20))
        is_dl = rng.random() < 0.4
        org = rng.choice(["HackTX 2026", "Longhorn Gaming", "Texas Convergent", "ACM", "Engineering Career Fair", "UTeach"])
        target = not target_done and (i == n_ann - 1 or rng.random() < 0.6)
        if is_dl:
            spec = {"date": d, "kind": "deadline_allday", "start": None, "end": None, "end_date": None, "tz_label": "", "tz_iana": None, "venue": None, "notes": None, "confidence": "high", "tags": ["deadline", "all_day"]}
            title = f"{esc(org)} needs YOU! | Deadline to Register: {S.date_text(rng, d, style='slash', weekday='yes')}"
            body = f"{esc(org)} is coming <b>{S.date_text(rng, d + timedelta(days=rng.randint(20, 50)), style='full', weekday='no')}</b>! Join 1,000+ students to collaborate, innovate, build, and enjoy free food. <b>Apply by {S.date_text(rng, d, style='full', weekday='no')}</b>!"
            g = gold_for(spec, f"{org} registration deadline")
        else:
            spec = make_event(rng, now, tz, kind="timed_range", day_offset=(0, 0), allow_tz=False); spec["date"] = d
            spec["venue"] = rng.choice(["the Union", "Union 3.304", "GDC 2.216", "EER Atrium"])
            name = rng.choice(["Kickoff/Expo", "Info Session", "Networking Night", "Workshop"])
            title = f"{esc(org)} {name} | {S.date_text(rng, d, style='slash', weekday='yes')}, {S.time_text(rng, spec['start'], spec['end'], style='tight')} at {esc(spec['venue'])}"
            body = f"Explore the world of {rng.choice(['competitive esports', 'product design', 'systems engineering'])} and more at {esc(org)}'s {esc(name)}, {S.date_text(rng, d, style='abbr_dot', weekday='yes')}, {S.time_text(rng, spec['start'], spec['end'], style='tight')} at {esc(spec['venue'])}. Develop essential skills while networking and finding community."
            g = gold_for(spec, f"{org} {name}")
        anns.append({"title": title, "body": body, "target": target})
        if target:
            gold.append(g); tags += spec["tags"]; target_done = True
    days = []
    dd = now.date() + timedelta(days=rng.randint(1, 4))
    for _ in range(rng.randint(2, 4)):
        dd = dd + timedelta(days=rng.randint(1, 4))
        it = rng.choice([{"course": "UTeach Canvas Community", "kind": "calendar event", "name": "Wed Workshop : The realities of first year teaching", "room": "PAI 4.18", "time": "6:00 PM to 7:00 PM"},
                         {"course": "UTeach Canvas Community", "kind": "calendar event", "name": "Summer 2026 and Fall 2026 registration Ends", "time": "ALL DAY"},
                         {"course": "CS 314", "kind": "assignment", "name": "Homework 3", "time": "Due 11:59 PM"},
                         {"course": "M 427J", "kind": "calendar event", "name": "Discussion Session", "room": "RLP 0.126", "time": "9:00 AM to 10:00 AM"}])
        days.append({"label": S.date_text(rng, dd, style="full", weekday="yes"), "items": [it]})
    html = canvas(rng, anns, days, school)
    return dict(html=html, target="#tgt", gold=gold, tags=tags, page_title="Dashboard", page_url="https://utexas.instructure.com/", kind="canvas", jitter="tight")


def s_hero(rng, now, tz):
    name = rng.choice(["HackTX", "MakeUT", "HackUTD", "TAMUhack", "DataDash", "HealthHack ATX"])
    yr = now.year if now.month < 11 else now.year + 1
    d = now.date() + timedelta(days=rng.randint(20, 80))
    d2 = d + timedelta(days=1)
    dl = now.date() + timedelta(days=rng.randint(3, 19))
    two = rng.random() < 0.7
    sep = rng.choice([" – ", "–", " - "])
    line = f"{d.month}.{d.day}{sep}{d2.month}.{d2.day}" if rng.random() < 0.6 else f"{S.MON_ABBR[d.month - 1]} {d.day}{sep}{d2.day}"
    if two:
        line += f" · Apply by {dl.month}.{dl.day}" if "." in line else f" · Apply by {S.MON_ABBR[dl.month - 1]} {dl.day}"
    font = rng.choice(["'Luminari', fantasy", "Papyrus, fantasy", "Copperplate, serif", "Impact, sans-serif", "'Didot', serif"])
    html = hero(rng, f"{name} {yr % 100}", line, rng.choice(["Apply Now", "Register", "Sign Up"]), font,
                rng.choice([("#bfe0ea", "#4a3b1f"), ("#101820", "#f2aa4c"), ("#f4f1ea", "#1b1b1b"), ("#1a2c5b", "#ffd9a0")]),
                badge=rng.choice(["MLH<br>OFFICIAL<br>2027<br>SEASON", ""]))
    spec = {"date": d, "kind": "allday", "start": None, "end": None, "end_date": d2, "tz_label": "", "tz_iana": None, "venue": None, "notes": None, "confidence": "high", "tags": ["all_day", "multi_day"]}
    gold = [gold_for(spec, f"{name} {yr % 100}")]
    if two:
        spec2 = {"date": dl, "kind": "deadline_allday", "start": None, "end": None, "end_date": None, "tz_label": "", "tz_iana": None, "venue": None, "notes": None, "confidence": "high", "tags": ["deadline", "all_day"]}
        gold.append(gold_for(spec2, f"{name} {yr % 100} application deadline"))
    return dict(html=html, target="#tgt", gold=gold, tags=["hero", "multi_day", "needs_context"] + (["multi_event", "deadline"] if two else []),
                page_title=f"{name} {yr % 100}", page_url=f"https://{name.lower()}.com/", kind="hero")


def s_chat(rng, now, tz):
    kind = rng.choice(["imessage", "groupme", "discord", "slack"])
    offset = rng.randint(0, 6)
    d = now.date() + timedelta(days=offset)
    rel = S.relative_phrase(rng, now, d) or S.date_text(rng, d, style="slash", weekday="yes")
    st = S.rand_time(rng, rng.choice(["evening", "any", "midday"]))
    ranged = rng.random() < 0.4
    en, _ = S.add_minutes(st, rng.choice([60, 90, 120])) if ranged else (None, 0)
    venue = rng.choice(["PCL 3rd floor", "the GDC atrium", "Union Starbucks", "Gong Cha on Guad", "Kins Market", "Odd Duck", "Room 4B", "the Game Night VC", None, None])
    activity = rng.choice(["study session", "project meeting", "dinner", "review session", "movie night", "gym session", "standup", "design review", "playtest", "scrim", "coffee"])
    tt = S.time_text(rng, st, en, style=rng.choice(["tight", "spaced", "at", None]), allow_24h=True)
    line = rng.choice([f"{activity} {rel} {tt}{', ' + venue if venue else ''}?", f"reminder: {activity} moved to {tt} {rel}{' in ' + venue if venue else ''}",
                       f"are we still on for {activity} {rel}? {tt} works", f"{activity} {rel} {tt} — {venue if venue else 'same place'}"])
    line = f"<span id='tgt'>{esc(line)}</span>"
    if kind == "imessage":
        html = imessage(rng, [("in", line), ("out", rng.choice(["i'm down", "yes!! see you there", "bet"])), ("in", rng.choice(["perfect", "bring your laptop", "🙌"]))], rng.choice(FIRST_NAMES), ["Mom", "roomies", "CS group"])
        title, url = "Screenshot.png", "file:///Users/user/Desktop/Screenshot.png"
    elif kind == "groupme":
        html = groupme(rng, [("Priya", line), ("Devon", "works for me"), ("Sam", "+1")], rng.choice(["Project Group", "CS 331 Study Group", "Apt 4B"]))
        title, url = "GroupMe | Project Group", "https://web.groupme.com/chats"
    elif kind == "discord":
        html = discord(rng, [("nova", line), ("jae", "count me in")], rng.choice(["general", "playtesting", "announcements"]), ["memes", "bug-reports", "art"])
        title, url = "Discord | #general", "https://discord.com/channels/1/2"
    else:
        html = slack(rng, [("Dana Whitfield", line), ("Kevin Tran", "sounds good 👍")], rng.choice(["team-platform", "design", "general"]), ["random", "eng-announcements"], rng.choice(["Cobalt Labs", "Meridian"]))
        title, url = "Slack | #team-platform | Cobalt Labs", "https://app.slack.com/client/T1/C2"
    spec = {"date": d, "kind": "timed_range" if ranged else "timed", "start": st, "end": en, "end_date": None, "tz_label": "", "tz_iana": None,
            "venue": None if venue in (None,) else (venue if not venue.startswith("the ") else venue[4:]), "notes": None, "confidence": "high", "tags": ["relative_date"]}
    gold = gold_for(spec, cap_first(activity))
    return dict(html=html, target="#tgt", gold=[gold], tags=["chat", kind] + spec["tags"], page_title=title, page_url=url, kind="chat", jitter="tight")


NONEVENT_IG = [
    ("Congratulations to the 2027 National Merit Semifinalists!", "wakelandhs_fisd"),
    ("Undocumented workflows and critical steps live inside your experts' heads....", "scribe_hq"),
    ("Another day at work 💪", "cristiano"),
    ("New colorway. Available now at the link in bio.", "getnavan"),
    ("Okaay cool & unexpected! ... ", "therock"),
    ("Thank you to everyone who came out last weekend — 300+ of you!! Recap video soon 🎥", "utdais"),
    ("What a season. Proud of this team. Onto the next one.", "longhornracing"),
    ("we don't do 'quick sync's here. we do 47-minute deep dives about nothing.", "utmemes"),
]
NONEVENT_MAIL = [
    ("Your order has been placed", "Amazon", "order-update@amazon.com", "<p>Order #114-4821 placed {d}, {y}.</p><p><b>Items:</b> USB-C hub (1) · Notebook, dotted (2)</p><p>Total: $48.12 · Payment: Visa ending 6411</p>"),
    ("Reset your password", "GitHub", "noreply@github.com", "<p>We received a request to reset your password. If you didn't make this request, you can ignore this email.</p><p><a>Reset password</a></p><p>This link expires in 24 hours.</p>"),
    ("Your weekly digest", "Medium", "noreply@medium.com", "<p><b>Why most dashboards fail</b><br>Six patterns that separate dashboards people use from ones they ignore. 7 min read</p><p><b>The quiet comeback of the campus radio station</b><br>Streaming did not kill it; it made the archive the star. 5 min read</p>"),
    ("Take our 2-minute survey", "UT Dining", "dining@utexas.edu", "<p>Hi there,</p><p>We'd love your feedback on the dining halls this semester. Your answers are anonymous.</p><p><a>Start the survey</a></p><p>Thanks for helping us improve!</p>"),
    ("Grades posted: Quiz 2", "Canvas", "notifications@instructure.com", "<p>Grades for <b>Quiz 2</b> have been posted in CS 314. You scored 18/20.</p><p>View the quiz in Canvas to see instructor comments.</p>"),
    ("Chipmakers double down on advanced packaging", "The Wire", "daily@thewire.example.com", "<p>Advanced packaging has become the industry's favorite lever for squeezing more performance out of silicon without waiting for the next process node.</p><p>Analysts expect capacity to stay tight through next year as demand from AI accelerators outpaces new fab capacity.</p>"),
]


def s_nonevent(rng, now, tz):
    kind = rng.choice(["ig", "ig", "mail", "mail", "chat", "canvas"])
    if kind == "ig":
        cap, handle = rng.choice(NONEVENT_IG)
        posted = now - timedelta(hours=rng.randint(1, 300))
        bg, fg, acc = rng.choice(S.PALETTES)
        quote = rng.choice(["Undocumented workflows and critical steps live inside your experts' heads.", "I AM ONCE AGAIN asking you to charge your laptop before section.",
                            "Congratulations to our 2027 National Merit Semifinalists!", "300+ hackers. 48 hours. One unforgettable weekend. Recap ⬇️", "Season recap: 4 podiums, 1 championship 🏆"])
        media = (f"<div class='fl' style='background:{bg};color:{fg}'><div id='tgt' style='font-family:{rng.choice(S.FONTS_DISPLAY)};font-size:{rng.randint(28, 40)}px;line-height:1.15;font-weight:900'>{esc(quote)}</div>"
                 f"<div class='s' style='color:{acc}'>{esc(handle)}</div></div>")
        html = ig_feed(rng, media, handle, S.age_label(rng, now, posted), esc(cap), likes=rng.randint(10, 5000))
        title, url = "Instagram", "https://www.instagram.com/?hl=en"
    elif kind == "mail":
        subj, sender, em, body = rng.choice(NONEVENT_MAIL)
        sent, when = email_when(rng, now)
        body = body.format(d=S.date_text(rng, sent.date(), style="full", weekday="no"), y=sent.year)
        html = gmail(rng, subj, sender, em, when, f"<span id='tgt'>{body}</span>")
        title, url = "Inbox - Gmail", "https://mail.google.com/mail/u/0/#inbox"
    elif kind == "chat":
        convo = rng.choice([[("in", "bro the midterm average was a 61"), ("out", "oh that's rough"), ("in", "curve better save us")],
                            [("in", "did you watch the finale last night"), ("out", "NO SPOILERS i'm two episodes behind"), ("in", "lmaooo ok hurry up")],
                            [("in", "can you send me the notes from lecture"), ("out", "yeah one sec"), ("in", "ty ty")]])
        convo = [(w, f"<span id='tgt'>{t}</span>" if i == 0 else t) for i, (w, t) in enumerate(convo)]
        html = imessage(rng, convo, rng.choice(FIRST_NAMES), ["Maya", "Mom"])
        title, url = "Screenshot.png", "file:///Users/user/Desktop/Screenshot2.png"
    else:
        anns = [{"title": "<span id='tgt'>Grades for Quiz 2 are posted</span>", "body": "You can view instructor comments in the Grades tab. The class average was 84%.", "target": False}]
        html = canvas(rng, anns, [], "The University Of Texas at Austin")
        title, url = "Dashboard", "https://utexas.instructure.com/"
    return dict(html=html, target="#tgt", gold=[], tags=["nonevent", kind], page_title=title, page_url=url, kind=f"nonevent_{kind}")


MIX = [
    (s_ig_flyer, 28), (s_ig_schedule, 5), (s_ig_story, 7), (s_gmail_marketing, 5), (s_gmail_bullets, 4),
    (s_gmail_luma, 4), (s_gmail_when_where, 3), (s_gmail_listing, 3), (s_gmail_headline, 3), (s_gmail_visit_days, 3),
    (s_gmail_moved, 2), (s_gmail_sessions, 2), (s_gmail_or, 2), (s_gmail_digest, 3), (s_gmail_confirmation, 3),
    (s_canvas, 5), (s_hero, 2), (s_chat, 6), (s_nonevent, 19),
]


# Scenarios whose venues are Texas places are generated for a Central-time
# user, so "timezone" gold never depends on knowing where a room number is.
GEO_BUILDERS = {s_ig_flyer, s_ig_schedule, s_ig_story, s_gmail_marketing, s_gmail_listing, s_gmail_moved,
                s_gmail_or, s_gmail_digest, s_canvas, s_hero, s_gmail_visit_days, s_gmail_sessions}


def build_case(seed: int, idx: int) -> dict:
    rng = random.Random(seed * 1_000_003 + idx)
    now = rand_now(rng)
    builder = rng.choices([b for b, _ in MIX], weights=[w for _, w in MIX])[0]
    tz = "America/Chicago" if builder in GEO_BUILDERS else S.pick_user_tz(rng)
    sc = builder(rng, now, tz)
    sc["context"] = context(now, tz, sc["page_title"], sc["page_url"])
    sc["id"] = f"train-{seed}-{idx:05d}-{sc['kind']}"
    sc["rng_state_seed"] = seed * 1_000_003 + idx
    return sc


_RENDERER = None


def _init_worker():
    global _RENDERER
    from synth.render import Renderer
    _RENDERER = Renderer()


def _run_one(args):
    seed, idx, dest, force = args
    global _RENDERER
    if _RENDERER is None:
        _init_worker()
    out = DATA / dest / f"train-{seed}-{idx:05d}"
    existing = list((DATA / dest).glob(f"train-{seed}-{idx:05d}-*")) if (DATA / dest).exists() else []
    if existing and not force:
        return ("skip", existing[0].name, 0)
    try:
        sc = build_case(seed, idx)
        rng = random.Random(sc["rng_state_seed"] + 7)
        r = _RENDERER.render(sc["html"], sc["target"], rng, jitter=sc.get("jitter", "normal"))
    except Exception as e:  # noqa: BLE001
        return ("error", f"{seed}-{idx}: {type(e).__name__}: {e}", 0)
    out = DATA / dest / sc["id"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "crop.png").write_bytes(r.crop_png)
    (out / "screen.png").write_bytes(r.screen_png)
    case = {"id": sc["id"], "context": sc["context"], "gold": {"events": sc["gold"]}, "tags": sorted(set(sc["tags"])),
            "kind": sc["kind"], "crop_rect": r.rect,
            "verification": {"status": "synthetic", "by": "train_gen", "note": "gold derived from generation parameters; randomized clock and timezone"}}
    (out / "case.json").write_text(json.dumps(case, indent=1))
    return ("ok", sc["id"], len(sc["gold"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--start", type=int, default=0, help="first index (resume)")
    ap.add_argument("--dest", default="train_smoke")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    jobs = [(args.seed, i, args.dest, args.force) for i in range(args.start, args.start + args.count)]
    t0 = _time.time()
    ok = skip = err = events = 0
    if args.workers > 1:
        import multiprocessing as mp
        ctx = mp.get_context("spawn")
        with ctx.Pool(args.workers, initializer=_init_worker) as pool:
            for status, msg, n in pool.imap_unordered(_run_one, jobs, chunksize=4):
                ok, skip, err, events = _tally(status, msg, n, ok, skip, err, events)
    else:
        for job in jobs:
            status, msg, n = _run_one(job)
            ok, skip, err, events = _tally(status, msg, n, ok, skip, err, events)
    print(f"\n{ok} generated, {skip} skipped, {err} errors, {events} gold events -> data/{args.dest}/ "
          f"({_time.time() - t0:.0f}s, {(_time.time() - t0) / max(1, ok):.2f}s/case)")


def _tally(status, msg, n, ok, skip, err, events):
    if status == "ok":
        ok += 1; events += n
        if ok % 25 == 0:
            print(f"  {ok} done", flush=True)
    elif status == "skip":
        skip += 1
    else:
        err += 1
        print("  ERROR", msg, flush=True)
    return ok, skip, err, events


if __name__ == "__main__":
    main()
