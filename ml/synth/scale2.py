"""Second synthetic batch: source types and edge cases synth_v0/v1 skip.

New templates: Canvas to-do list, syllabus/schedule HTML tables, Slack, an
Outlook/Teams invite, an X post card, a ticket page, Apple Reminders, a
dark-mode Gmail, and a terminal log. New probes: 24-hour times, "noon",
"by 5pm Friday", ranges that cross noon and midnight, multi-day all-day
spans, explicit next-year dates, recurring rules with BYDAY sets and UNTIL,
TBA times, undated rows that must NOT become events, and dated-but-not-event
text (order confirmations, past-tense news, logs).

Gold is exact by construction; rendered weekdays are derived from the date
objects so they can never disagree. Frozen fake now = Tue 2026-09-01 12:00.

Usage (from ml/):  uv run python -m synth.scale2 [--dest synth_v2] [--seed 11] [--force]
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta

from synth.generate import (
    ARTICLE_CSS, DATA, FLYER_CSS, NOW, TZ, WEEKDAY,
    discord, ev, flyer, gmail, groupme, imessage, page, render,
)
from synth.scale import MONTHS, fmt_time, iso, wd

TODAY = date(2026, 9, 1)  # Tuesday — must match NOW in generate.py


def d(m: int, day: int, y: int = 2026) -> date:
    return date(y, m, day)


def long(dt: date) -> str:          # "Tuesday, September 15"
    return f"{wd(dt)}, {MONTHS[dt.month - 1]} {dt.day}"


def long_y(dt: date) -> str:        # "Tuesday, September 15, 2026"
    return f"{long(dt)}, {dt.year}"


def abbr(dt: date) -> str:          # "Sep 8"
    return f"{dt.strftime('%b')} {dt.day}"


def wd3(dt: date) -> str:           # "Sat"
    return wd(dt)[:3]


def canvas_time(h: int, m: int) -> str:   # "11:59pm"
    return f"{h % 12 or 12}:{m:02d}{'am' if h < 12 else 'pm'}"


def until(dt: date) -> str:
    return f"{dt:%Y%m%d}T235959"


def shift_to_weekday(dt: date, weekday: int) -> date:
    """Next date on/after dt whose weekday() == weekday (Mon=0)."""
    return dt + timedelta(days=(weekday - dt.weekday()) % 7)


# ------------------------------------------------------------------ templates

CANVAS_CSS = (
    ".cv{display:flex;height:100vh;background:#fff;font-size:14px;color:#2d3b45}"
    ".cvnav{width:84px;background:#0b3d5c;color:#fff;padding:14px 0;text-align:center;font-size:10px}"
    ".cvnav div{padding:10px 0}"
    ".cvmain{flex:1;padding:22px 28px}"
    ".cvcrumb{font-size:13px;color:#0374b5;margin-bottom:8px}"
    ".cvh{font-size:24px;font-weight:400;margin-bottom:16px}"
    ".todoh{font-size:15px;font-weight:700;padding:10px 4px}"
    ".todo{border-top:1px solid #c7cdd1;background:#fff;padding:0 4px}"
    ".ti{display:flex;gap:12px;padding:12px 4px;border-bottom:1px solid #c7cdd1;align-items:flex-start}"
    ".tic{width:18px;height:18px;border:2px solid #0374b5;border-radius:3px;margin-top:2px;flex:none}"
    ".tit{font-weight:600;color:#0374b5}.tis{font-size:12.5px;color:#6b7780;margin-top:3px}"
)


def canvas(code, name, items, include_header):
    rows = "".join(
        f"<div class='ti'><div class='tic'></div><div><div class='tit'>{t}</div>"
        f"<div class='tis'>{s}</div></div></div>"
        for t, s in items
    )
    header = (f"<div class='cvcrumb'>{code} › Assignments</div>"
              f"<div class='cvh'>{code} {name}</div>")
    todo = f"<div class='todoh'>To Do</div><div class='todo'>{rows}</div>"
    crop = page(CANVAS_CSS, f"<div style='padding:14px 18px'>"
                            f"{header if include_header else ''}{todo}</div>")
    nav = "".join(f"<div>{n}</div>" for n in ["Account", "Dashboard", "Courses", "Calendar", "Inbox"])
    screen = page(CANVAS_CSS, f"<div class='cv'><div class='cvnav'>{nav}</div>"
                              f"<div class='cvmain'>{header}{todo}</div></div>")
    return crop, screen


TABLE_CSS = (
    ".syl{background:#fff;padding:26px;color:#1a1a1a;max-width:760px}"
    ".sylh{font-size:22px;font-weight:700;margin-bottom:4px}"
    ".syls{font-size:13px;color:#666;margin-bottom:16px}"
    ".sec{font-size:16px;font-weight:700;margin:14px 0 8px}"
    "table{border-collapse:collapse;width:100%;font-size:14px}"
    "th,td{border:1px solid #cfd4d9;padding:8px 10px;text-align:left}th{background:#f1f3f5}"
    ".tbar{background:#bf5700;color:#fff;padding:12px 20px;font-weight:700}"
)


def table_page(header_html, section, cols, rows, crop_with_header=True, bar="Canvas"):
    thead = "".join(f"<th>{c}</th>" for c in cols)
    tbody = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    tbl = f"<div class='sec'>{section}</div><table><tr>{thead}</tr>{tbody}</table>"
    crop = page(TABLE_CSS, f"<div class='syl'>{header_html if crop_with_header else ''}{tbl}</div>")
    screen = page(TABLE_CSS, f"<div class='tbar'>{bar}</div><div class='syl'>{header_html}{tbl}</div>")
    return crop, screen


SLACK_CSS = (
    ".sk{display:flex;height:100vh;font-size:15px}"
    ".sks{width:220px;background:#3f0e40;color:#cfc3cf;padding:14px 12px}"
    ".sks .w{color:#fff;font-weight:700;margin-bottom:14px;font-size:16px}"
    ".sks .c{padding:4px 8px;border-radius:5px}.sks .con{background:#1164a3;color:#fff}"
    ".skm{flex:1;background:#fff;display:flex;flex-direction:column}"
    ".skh{padding:12px 18px;border-bottom:1px solid #ddd;font-weight:700}"
    ".skl{padding:14px 18px;background:#fff}"
    ".msg{display:flex;gap:10px;margin-bottom:14px}"
    ".mav{width:36px;height:36px;border-radius:6px;flex:none}"
    ".mn{font-weight:700}.mt{color:#616061;font-size:12px;margin-left:6px}"
    ".mb{margin-top:2px;line-height:1.45}"
)


def slack(msgs, channel, others, workspace):
    colors = ["#e01e5a", "#2eb67d", "#ecb22e", "#36c5f0"]
    rows = "".join(
        f"<div class='msg'><div class='mav' style='background:{colors[i % 4]}'></div>"
        f"<div><span class='mn'>{n}</span><span class='mt'>{t}</span><div class='mb'>{m}</div></div></div>"
        for i, (n, t, m) in enumerate(msgs)
    )
    crop = page(SLACK_CSS, f"<div class='skl'>{rows}</div>")
    chans = f"<div class='c con'># {channel}</div>" + "".join(f"<div class='c'># {c}</div>" for c in others)
    screen = page(SLACK_CSS, f"<div class='sk'><div class='sks'><div class='w'>{workspace}</div>{chans}</div>"
                             f"<div class='skm'><div class='skh'># {channel}</div><div class='skl'>{rows}</div></div></div>")
    return crop, screen


OUTLOOK_CSS = (
    ".ol{background:#fff;padding:20px 24px;font-size:14px;color:#242424;max-width:720px}"
    ".olsub{font-size:20px;font-weight:600;margin-bottom:6px}"
    ".olfrom{color:#616161;margin-bottom:14px}"
    ".olbox{border:1px solid #e1dfdd;border-radius:4px;padding:12px 14px;background:#faf9f8;margin-bottom:14px}"
    ".olrow{margin-bottom:6px}.olrow b{display:inline-block;min-width:64px}"
    ".olbtn{display:inline-block;background:#0078d4;color:#fff;padding:7px 14px;border-radius:3px;font-weight:600;margin-right:8px}"
    ".olbar{background:#0f6cbd;color:#fff;padding:10px 18px;font-weight:700;font-size:16px}"
)


def outlook(subject, organizer, when, where, body):
    inner = (
        f"<div class='ol'><div class='olsub'>{subject}</div><div class='olfrom'>{organizer} invited you</div>"
        f"<div class='olbox'><div class='olrow'><b>When:</b> {when}</div>"
        f"<div class='olrow'><b>Where:</b> {where}</div></div>"
        f"<p style='margin-bottom:14px;line-height:1.5'>{body}</p>"
        "<span class='olbtn'>Accept</span><span class='olbtn' style='background:#605e5c'>Tentative</span>"
        "<span class='olbtn' style='background:#a4262c'>Decline</span></div>"
    )
    crop = page(OUTLOOK_CSS, inner)
    screen = page(OUTLOOK_CSS, "<div class='olbar'>Outlook</div>" + inner)
    return crop, screen


X_CSS = (
    "body{background:#000}"
    ".x{background:#000;color:#e7e9ea;min-height:100vh;padding:16px;font-size:15px}"
    ".xc{max-width:560px;border:1px solid #2f3336;border-radius:16px;padding:14px;background:#000}"
    ".xh{display:flex;gap:10px;align-items:center;margin-bottom:10px}"
    ".xav{width:40px;height:40px;border-radius:50%;background:#1d9bf0;flex:none}"
    ".xn{font-weight:700}.xu{color:#71767b;font-size:14px}"
    ".xb{line-height:1.45;font-size:17px}"
    ".xm{color:#71767b;font-size:14px;margin-top:10px}"
    ".xside{width:250px;color:#e7e9ea;padding:18px;font-size:19px;font-weight:700}.xside div{margin-bottom:22px}"
)


def xpost(name, handle, text, meta="10:14 AM · Sep 1, 2026 · 2,143 Views"):
    card = (f"<div class='xc'><div class='xh'><div class='xav'></div><div><div class='xn'>{name}</div>"
            f"<div class='xu'>@{handle}</div></div></div><div class='xb'>{text}</div>"
            f"<div class='xm'>{meta}</div></div>")
    crop = page(X_CSS, f"<div class='x'>{card}</div>")
    side = "".join(f"<div>{s}</div>" for s in ["X", "Home", "Explore", "Notifications", "Messages", "Profile"])
    screen = page(X_CSS, f"<div class='x' style='display:flex'><div class='xside'>{side}</div>"
                         f"<div style='flex:1;max-width:600px;border-left:1px solid #2f3336;"
                         f"border-right:1px solid #2f3336;padding:14px'>{card}</div></div>")
    return crop, screen


TICKET_CSS = (
    ".tk{background:#fff;color:#111;padding:26px;max-width:720px}"
    ".tkk{font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#777;margin-bottom:8px}"
    ".tkh{font-size:30px;font-weight:800;margin-bottom:6px}"
    ".tks{font-size:16px;color:#333;margin-bottom:14px}"
    ".tkd{font-size:18px;font-weight:600;margin-bottom:4px}"
    ".tkv{font-size:15px;color:#444;margin-bottom:16px}"
    ".tkb{display:inline-block;background:#026cdf;color:#fff;padding:10px 22px;border-radius:4px;font-weight:700}"
    ".tkbar{background:#026cdf;color:#fff;padding:12px 20px;font-weight:800;font-size:18px}"
)


def ticket(kicker, title, sub, dateline, venue, price):
    inner = (f"<div class='tk'><div class='tkk'>{kicker}</div><div class='tkh'>{title}</div>"
             f"<div class='tks'>{sub}</div><div class='tkd'>{dateline}</div><div class='tkv'>{venue}</div>"
             f"<span class='tkb'>Find tickets · {price}</span></div>")
    crop = page(TICKET_CSS, inner)
    screen = page(TICKET_CSS, "<div class='tkbar'>ticketmaster</div>" + inner)
    return crop, screen


REM_CSS = (
    ".rm{background:#fff;padding:20px;max-width:520px;font-size:16px}"
    ".rmh{font-size:30px;font-weight:800;color:#0a84ff;margin-bottom:14px}"
    ".ri{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #eee}"
    ".rc{width:22px;height:22px;border:2px solid #c7c7cc;border-radius:50%;flex:none;margin-top:1px}"
    ".rt{font-size:16px}.rd{font-size:13px;color:#8e8e93;margin-top:2px}"
    ".rshell{display:flex;height:100vh;background:#f2f2f7}"
    ".rside{width:220px;background:#e9e9ee;padding:16px;font-size:14px}"
    ".rside div{padding:8px 10px;border-radius:8px}.rside .on{background:#0a84ff;color:#fff}"
)


def reminders(list_name, items, other_lists):
    rows = "".join(
        f"<div class='ri'><div class='rc'></div><div><div class='rt'>{t}</div>"
        + (f"<div class='rd'>{s}</div>" if s else "") + "</div></div>"
        for t, s in items
    )
    inner = f"<div class='rm'><div class='rmh'>{list_name}</div>{rows}</div>"
    crop = page(REM_CSS, inner)
    side = f"<div class='on'>{list_name}</div>" + "".join(f"<div>{o}</div>" for o in other_lists)
    screen = page(REM_CSS, f"<div class='rshell'><div class='rside'>{side}</div>"
                           f"<div style='flex:1;padding:20px'>{inner}</div></div>")
    return crop, screen


DMAIL_CSS = (
    "body{background:#1f1f1f}"
    ".dmail{background:#1f1f1f;color:#e3e3e3;padding:22px;max-width:680px}"
    ".dsubj{font-size:20px;margin-bottom:14px;color:#fff}"
    ".dfrom{font-size:13px;color:#aaa;margin-bottom:18px;padding-bottom:12px;border-bottom:1px solid #333}"
    ".dfrom b{color:#fff}"
    ".dbody{font-size:14px;line-height:1.6}.dbody p{margin-bottom:12px}.dbody a{color:#8ab4f8}"
    ".dbar{background:#111;padding:10px 18px;font-size:18px;color:#bbb;border-bottom:1px solid #333}"
)


def gmail_dark(subject, sender, body_html):
    addr = sender.lower().replace(" ", ".")
    inner = (f"<div class='dmail'><div class='dsubj'>{subject}</div><div class='dfrom'><b>{sender}</b> "
             f"&lt;{addr}@utexas.edu&gt; — Tue, Sep 1, 2026, 8:41 AM</div>"
             f"<div class='dbody'>{body_html}</div></div>")
    crop = page(DMAIL_CSS, inner)
    screen = page(DMAIL_CSS, f"<div class='dbar'><b>M</b> Gmail — Inbox</div>{inner}")
    return crop, screen


TERM_CSS = (
    "body{background:#1e1e1e}"
    ".term{background:#1e1e1e;color:#d4d4d4;font-family:Menlo,Monaco,monospace;font-size:13px;"
    "padding:16px;line-height:1.6;min-height:100vh;white-space:pre}"
    ".ok{color:#6a9955}.err{color:#f14c4c}.ts{color:#9cdcfe}.warn{color:#dcdcaa}"
)


# ------------------------------------------------------------------ content pools

COURSES = [
    ("CS 429", "Computer Organization and Architecture"),
    ("M 362K", "Probability I"),
    ("EE 312", "Software Design and Implementation"),
    ("CS 331", "Algorithms and Complexity"),
    ("PHY 303K", "Engineering Physics I"),
]
ROOMS = ["GDC 2.216", "WEL 2.224", "JGB 2.216", "UTC 2.102A", "BUR 106", "EER 1.516"]
ASSIGNMENTS = [("HW 2", 23, 59), ("Quiz 1", 14, 0), ("Lab 3", 23, 59), ("Project Proposal", 17, 0),
               ("HW 3", 23, 59), ("Reading Response 2", 9, 0)]


# ------------------------------------------------------------------ builders

def b_canvas(rng, idx, variant):
    needs_context = variant == 1
    if variant == 0:
        code, name = COURSES[0]
        picks = [("HW 2", d(9, 8), 23, 59), ("Quiz 1", d(9, 10), 14, 0)]
    else:
        code, name = rng.choice(COURSES[1:])
        names = rng.sample(ASSIGNMENTS, 3 if variant == 2 else 2)
        day = TODAY + timedelta(days=rng.randint(3, 8))
        picks = []
        for n, h, m in names:
            picks.append((n, day, h, m))
            day = day + timedelta(days=rng.randint(2, 5))
    items = [(n, f"Due {abbr(dt)} at {canvas_time(h, m)} · {rng.choice([50, 100, 20])} points")
             for n, dt, h, m in picks]
    gold = [ev(f"{code} {n} due", iso(dt, h, m), end=iso(dt, h, m)) for n, dt, h, m in picks]
    crop, screen = canvas(code, name, items, include_header=not needs_context)
    tags = ["deadline", "multi_event"] + (["needs_context"] if needs_context else [])
    return dict(id=f"synth2-{idx:03d}-canvas{'x' if needs_context else ''}", crop=crop, screen=screen,
                crop_size=(600, 240 + 70 * len(items)), page_title=f"Assignments: {code}",
                page_url="https://utexas.instructure.com/courses/1411982/assignments",
                gold=gold, tags=tags)


def b_syllabus(rng, idx, variant):
    if variant == 0:
        code, name = COURSES[3]
        e1 = d(10, 1)
    else:
        code, name = COURSES[4]
        e1 = shift_to_weekday(TODAY + timedelta(days=rng.randint(24, 34)), rng.choice([1, 2]))
    e2 = e1 + timedelta(weeks=5)
    room = ROOMS[0] if variant == 0 else rng.choice(ROOMS[1:])
    rows = [["Exam 1", long(e1), "7:00–9:00 PM", room],
            ["Exam 2", long(e2), "7:00–9:00 PM", room],
            ["Final Exam", "TBA", "TBA", "TBA"]]
    header = f"<div class='sylh'>{code} {name}</div><div class='syls'>Fall 2026 · Syllabus</div>"
    crop, screen = table_page(header, "Exam Schedule", ["Exam", "Date", "Time", "Room"], rows)
    gold = [ev(f"{code} Exam 1", iso(e1, 19), end=iso(e1, 21), location=room),
            ev(f"{code} Exam 2", iso(e2, 19), end=iso(e2, 21), location=room)]
    return dict(id=f"synth2-{idx:03d}-syllabus", crop=crop, screen=screen, crop_size=(720, 330),
                page_title=f"{code} Syllabus", page_url="https://utexas.instructure.com/courses/1409811/assignments/syllabus",
                gold=gold, tags=["multi_event", "undated_row"])


def b_slack(rng, idx, variant):
    if variant == 0:
        msgs = [("Priya N.", "10:14 AM", "heads up — standup moved to 9:30am tomorrow, same link"),
                ("Devon", "10:15 AM", "ack"), ("Sam K.", "10:16 AM", "👍")]
        gold = [ev("Standup", iso(TODAY + timedelta(days=1), 9, 30))]
        tags = ["relative_date"]
    elif variant == 1:
        msgs = [("Marcus L.", "9:52 AM", "design review Thu 9/3 2–3pm in Room 4B. bring the latest mocks"),
                ("Priya N.", "9:55 AM", "will do")]
        gold = [ev("Design review", iso(d(9, 3), 14), end=iso(d(9, 3), 15), location="Room 4B")]
        tags = []
    else:
        msgs = [("Devon", "11:20 AM", "sprint retro fri 9/4 at 4pm in Room 2A — 30 min max i promise"),
                ("Sam K.", "11:21 AM", "lol ok")]
        gold = [ev("Sprint retro", iso(d(9, 4), 16), end=iso(d(9, 4), 16, 30), location="Room 2A")]
        tags = ["stated_duration"]
    crop, screen = slack(msgs, "eng-platform", ["general", "random", "deploys"], "Meridian Systems")
    return dict(id=f"synth2-{idx:03d}-slack", crop=crop, screen=screen, crop_size=(640, 200),
                page_title="eng-platform - Meridian Systems - Slack",
                page_url="https://app.slack.com/client/T01/C02", gold=gold, tags=tags)


def b_outlook(rng, idx, variant):
    if variant == 0:
        dt, h = d(9, 15), 14
        when = f"{long_y(dt)} {fmt_time(h, 0)}-{fmt_time(h, 30)} (UTC-05:00) Central Time (US & Canada)"
        subject, org, tz = "Intern project sync", "Rachel Moreno", None
        body = "Quick sync on the Q4 dashboard work. Agenda in the shared doc."
    else:
        dt, h = d(9, 18), 10
        when = f"{long_y(dt)} {fmt_time(h, 0)}-{fmt_time(h, 30)} (UTC-08:00) Pacific Time (US & Canada)"
        subject, org, tz = "Offer call with Recruiting", "Cobalt Labs Recruiting", "America/Los_Angeles"
        body = "We'd love to walk you through the details of your offer."
    crop, screen = outlook(subject, org, when, "Microsoft Teams Meeting", body)
    gold = [ev(subject, iso(dt, h), end=iso(dt, h, 30), timezone=tz, location="Microsoft Teams")]
    return dict(id=f"synth2-{idx:03d}-outlook", crop=crop, screen=screen, crop_size=(700, 300),
                page_title=f"{subject} - Outlook", page_url="https://outlook.office.com/mail/inbox",
                gold=gold, tags=["timezone"] if tz else ["same_timezone_stated"])


def b_xpost(rng, idx, variant):
    if variant == 0:
        dt = d(10, 3)
        text = f"NIGHT SIGNAL LIVE 🎸 {wd3(dt)} {dt.month}/{dt.day} · 8pm · Mohawk Austin. tix in bio"
        crop, screen = xpost("Night Signal", "nightsignalband", text)
        gold = [ev("Night Signal Live", iso(dt, 20), location="Mohawk Austin")]
        title, url = "Night Signal on X", "https://x.com/nightsignalband/status/1832"
    else:
        dt = d(9, 6)
        text = (f"POP-UP MARKET this {wd(dt)} {dt.month}/{dt.day} · 11am–3pm · Republic Square. "
                "40+ local vendors, free entry ☀️")
        crop, screen = xpost("Austin Makers Market", "atxmakersmkt", text)
        gold = [ev("Pop-Up Market", iso(dt, 11), end=iso(dt, 15), location="Republic Square")]
        title, url = "Austin Makers Market on X", "https://x.com/atxmakersmkt/status/1833"
    return dict(id=f"synth2-{idx:03d}-xpost", crop=crop, screen=screen, crop_size=(600, 230),
                page_title=title, page_url=url, gold=gold, tags=["relative_date"] if variant else [])


def b_ticket(rng, idx, variant):
    if variant == 0:
        dt, h, m = d(10, 17), 19, 30
        crop, screen = ticket("Concert", "The Ridgelines", "Fall Tour 2026 with special guest Lo Tide",
                              f"{wd3(dt)}, {abbr(dt)}, {dt.year} · {fmt_time(h, m)}",
                              "Moody Center · Austin, TX", "from $39")
        gold = [ev("The Ridgelines", iso(dt, h, m), location="Moody Center")]
    else:
        dt, h, m = d(11, 13), 20, 0
        crop, screen = ticket("Comedy", "Dana Reyes", "Nothing Personal Tour",
                              f"{wd3(dt)}, {abbr(dt)}, {dt.year} · {fmt_time(h, m)}",
                              "Paramount Theatre · Austin, TX", "from $45")
        gold = [ev("Dana Reyes", iso(dt, h, m), location="Paramount Theatre")]
    return dict(id=f"synth2-{idx:03d}-ticket", crop=crop, screen=screen, crop_size=(700, 300),
                page_title=f"{gold[0]['title']} Tickets", page_url="https://www.ticketmaster.com/event/3A00",
                gold=gold, tags=["explicit_year"])


def b_sports(rng, idx, variant):
    if variant == 0:
        team, venue = "Texas Volleyball", "Gregory Gym"
        r1 = (d(9, 12), "vs. Baylor", 19, 0)
        r2 = (d(9, 16), "vs. Rice")
    else:
        team, venue = "Texas Soccer", "Mike A. Myers Stadium"
        r1 = (d(9, 18), "vs. Oklahoma State", 19, 0)
        r2 = (d(9, 27), "vs. TCU")
    rows = [[f"{wd3(r1[0])}, {abbr(r1[0])}", r1[1], fmt_time(r1[2], r1[3]), venue],
            [f"{wd3(r2[0])}, {abbr(r2[0])}", r2[1], "TBA", venue]]
    header = f"<div class='sylh'>{team}</div><div class='syls'>2026 Schedule · Home games</div>"
    crop, screen = table_page(header, "September", ["Date", "Opponent", "Time", "Venue"], rows,
                              bar="Texas Longhorns")
    gold = [ev(f"{team} {r1[1]}", iso(r1[0], r1[2], r1[3]), location=venue),
            ev(f"{team} {r2[1]}", iso(r2[0]), all_day=True, location=venue)]
    return dict(id=f"synth2-{idx:03d}-sports", crop=crop, screen=screen, crop_size=(700, 280),
                page_title=f"{team} Schedule", page_url="https://texaslonghorns.com/sports/schedule",
                gold=gold, tags=["time_tba", "multi_event"])


def b_reminders(rng, idx, variant):
    if variant == 0:
        items = [("Dentist", f"{abbr(d(9, 22))}, {fmt_time(15, 0)}"),
                 ("Renew parking permit", abbr(d(9, 30))),
                 ("Call grandma", "")]
        gold = [ev("Dentist", iso(d(9, 22), 15)),
                ev("Renew parking permit", iso(d(9, 30)), all_day=True)]
    else:
        items = [("Oil change", f"{abbr(d(10, 2))}, {fmt_time(9, 0)}"),
                 ("Submit timesheet", abbr(d(9, 15))),
                 ("Buy printer ink", "")]
        gold = [ev("Oil change", iso(d(10, 2), 9)),
                ev("Submit timesheet", iso(d(9, 15)), all_day=True)]
    crop, screen = reminders("Reminders", items, ["Today", "Scheduled", "Groceries", "Work"])
    return dict(id=f"synth2-{idx:03d}-reminders", crop=crop, screen=screen, crop_size=(520, 260),
                page_title="Reminders", page_url="file:///Users/vedanth/Desktop/reminders.png",
                gold=gold, tags=["multi_event", "all_day", "undated_row"])


def b_recurring(rng, idx, variant):
    if variant == 0:
        code, name = COURSES[0]
        start = d(9, 2)
        body = (f"<p>Office hours this semester: <b>Mondays &amp; Wednesdays 2–3 PM in GDC 5.512</b>, "
                f"starting {long(start)}, Sept {start.day}. No appointment needed.</p>")
        header = f"<div class='sylh'>{code} {name}</div><div class='syls'>Announcement · posted Sep 1</div>"
        crop = page(TABLE_CSS, f"<div class='syl'>{header}{body}</div>")
        screen = page(TABLE_CSS, f"<div class='tbar'>Canvas</div><div class='syl'>{header}{body}</div>")
        gold = [ev("Office hours", iso(start, 14), end=iso(start, 15), location="GDC 5.512",
                   recurrence="RRULE:FREQ=WEEKLY;BYDAY=MO,WE")]
        title, url, size = f"{code} Announcements", "https://utexas.instructure.com/courses/1411982/announcements", (700, 220)
    elif variant == 1:
        start, last = d(9, 4), d(12, 4)
        crop, screen = flyer("free lunch · all majors", "LUNCH &amp; LEARN",
                             "Every Friday · 12–1 PM", f"{abbr(start)} through {abbr(last)} · EER 0.904",
                             ("#20303c", "#a8e0ff"),
                             f"Weekly industry talks over free lunch, every Friday from {abbr(start)} "
                             f"through {abbr(last)} in EER 0.904.", "cockrellcareers")
        gold = [ev("Lunch & Learn", iso(start, 12), end=iso(start, 13), location="EER 0.904",
                   recurrence=f"RRULE:FREQ=WEEKLY;BYDAY=FR;UNTIL={until(last)}")]
        title, url, size = "Cockrell Careers on Instagram", "https://www.instagram.com/p/LnL2026/", (520, 480)
    else:
        start = d(9, 8)
        crop, screen = flyer("all paces welcome", "RUN CLUB",
                             "Tuesdays · 6–7:30 PM", f"starting Sept {start.day} · Gregory Gym Annex",
                             ("#2d4739", "#f2ede3"),
                             f"Run club is back! Every Tuesday evening starting Sept {start.day}, "
                             "meet at Gregory Gym Annex.", "utrunclub")
        gold = [ev("Run Club", iso(start, 18), end=iso(start, 19, 30), location="Gregory Gym Annex",
                   recurrence="RRULE:FREQ=WEEKLY;BYDAY=TU")]
        title, url, size = "UT Run Club on Instagram", "https://www.instagram.com/p/RunClub26/", (520, 480)
    return dict(id=f"synth2-{idx:03d}-recurring", crop=crop, screen=screen, crop_size=size,
                page_title=title, page_url=url, gold=gold, tags=["recurrence"])


def b_midnight(rng, idx, variant):
    if variant == 0:
        dt = d(10, 31)
        crop, screen = flyer("costumes required", "HALLOWEEN BASH",
                             f"{wd3(dt)} {MONTHS[dt.month - 1][:3]} {dt.day} · 9 PM – 1 AM", "Union Ballroom · $5 at the door",
                             ("#101820", "#f2aa4c"),
                             "Halloween bash at the Union Ballroom. Costume contest at midnight 🎃", "utunionevents")
        gold = [ev("Halloween Bash", iso(dt, 21), end=iso(dt + timedelta(days=1), 1), location="Union Ballroom")]
        title, url, size = "Union Events on Instagram", "https://www.instagram.com/p/Hallow26/", (520, 480)
    else:
        dt = d(9, 11)
        crop, screen = discord(
            [("kai", f"late night LAN party {wd3(dt).lower()} {dt.month}/{dt.day} 10pm–2am in the ECJ basement lab, bring your own peripherals"),
             ("mira", "in. i'll bring the switch too")],
            "events", ["general", "lfg", "clips"])
        gold = [ev("LAN party", iso(dt, 22), end=iso(dt + timedelta(days=1), 2), location="ECJ basement lab")]
        title, url, size = "Discord | #events | Texas Esports", "https://discord.com/channels/44/55", (640, 240)
    return dict(id=f"synth2-{idx:03d}-midnight", crop=crop, screen=screen, crop_size=size,
                page_title=title, page_url=url, gold=gold, tags=["crosses_midnight"])


def b_multiday(rng, idx, variant):
    if variant == 0:
        a, b = d(10, 12), d(10, 13)
        rows = [["Fall Break", f"{long(a)} – {long(b)}", "No classes"]]
        header = "<div class='sylh'>Fall 2026 Academic Calendar</div><div class='syls'>Office of the Registrar</div>"
        crop, screen = table_page(header, "October", ["Event", "Dates", "Notes"], rows,
                                  crop_with_header=False, bar="Office of the Registrar")
        gold = [ev("Fall Break", iso(a), end=iso(b), all_day=True)]
        title, url, size = "Academic Calendar Fall 2026", "https://registrar.utexas.edu/calendars/26-27", (700, 160)
        tags = ["multi_day", "all_day", "needs_context"]
    else:
        a, b = d(11, 26), d(11, 27)
        crop, screen = gmail("Thanksgiving Break hours", "Campus Operations",
                             f"<p>Reminder: <b>Thanksgiving Break</b> is <b>{long(a)} – {long(b)}</b>. "
                             "Campus is closed both days; normal hours resume Monday.</p>")
        gold = [ev("Thanksgiving Break", iso(a), end=iso(b), all_day=True)]
        title, url, size = "Thanksgiving Break hours - Gmail", "https://mail.google.com/mail/u/0/#inbox", (700, 300)
        tags = ["multi_day", "all_day"]
    return dict(id=f"synth2-{idx:03d}-multiday", crop=crop, screen=screen, crop_size=size,
                page_title=title, page_url=url, gold=gold, tags=tags)


def b_nextyear(rng, idx, variant):
    if variant == 0:
        dt = d(1, 27, 2027)
        body = (f"<div class='art'><div class='ah'>Spring Career Expo 2027</div>"
                f"<div class='ab'>Texas Career Engagement</div>"
                f"<p><b>{long_y(dt)} · 11 AM–3 PM</b></p><p><b>Gregory Gym</b>, 2101 Speedway</p>"
                "<p>120+ employers across engineering, consulting, and CPG. Bring printed resumes.</p></div>")
        crop = page(ARTICLE_CSS, body)
        screen = page(ARTICLE_CSS, "<div style='background:#bf5700;color:#fff;padding:12px 20px;font-weight:700'>"
                                   "Texas Career Engagement</div>" + body)
        gold = [ev("Spring Career Expo", iso(dt, 11), end=iso(dt, 15), location="Gregory Gym")]
        title, url, size = "Spring Career Expo 2027", "https://careerengagement.utexas.edu/expo", (680, 320)
    else:
        dt = d(3, 6, 2027)
        crop, screen = gmail("Save the date: Alumni Reunion Weekend", "Texas Exes",
                             f"<p>Mark your calendar — <b>Alumni Reunion Weekend</b> kicks off "
                             f"<b>{long_y(dt)}, 10 AM–4 PM</b> at the Texas Union. Registration opens in January.</p>")
        gold = [ev("Alumni Reunion Weekend", iso(dt, 10), end=iso(dt, 16), location="Texas Union")]
        title, url, size = "Save the date: Alumni Reunion Weekend - Gmail", "https://mail.google.com/mail/u/0/#inbox", (700, 300)
    return dict(id=f"synth2-{idx:03d}-nextyear", crop=crop, screen=screen, crop_size=size,
                page_title=title, page_url=url, gold=gold, tags=["explicit_year"])


def b_discord24h(rng, idx, variant):
    if variant == 0:
        crop, screen = discord([("nova", "scrim tonight 19:30, be on"), ("jae", "on it")],
                               "scrims", ["general", "vods", "memes"])
        gold = [ev("Scrim", iso(TODAY, 19, 30))]
    else:
        crop, screen = discord([("nova", "vod review tomorrow 20:00 in the Strat VC"), ("jae", "👌")],
                               "vods", ["general", "scrims", "memes"])
        gold = [ev("VOD review", iso(TODAY + timedelta(days=1), 20), location="Strat VC")]
    return dict(id=f"synth2-{idx:03d}-discord24h", crop=crop, screen=screen, crop_size=(600, 200),
                page_title="Discord | Valorant Club", page_url="https://discord.com/channels/7/8",
                gold=gold, tags=["relative_date", "24h_time"])


def b_noon(rng, idx, variant):
    if variant == 0:
        convo = ("<div class='stamp'>Today 9:12 AM</div>"
                 "<div class='b in'>lunch friday at noon at Thai Kitchen?</div>"
                 "<div class='b out'>yesss</div>")
        crop, screen = imessage(convo, "Sam", ["Mom", "roomies", "Priya"])
        gold = [ev("Lunch", iso(d(9, 4), 12), location="Thai Kitchen")]
        title, url = "Screenshot.png", "file:///Users/vedanth/Desktop/Screenshot3.png"
    else:
        crop, screen = groupme([("Priya", "coffee chat thursday at noon, Medici on the Drag"),
                                ("Devon", "sounds good")], "PM Club Mentors")
        gold = [ev("Coffee chat", iso(d(9, 3), 12), location="Medici")]
        title, url = "GroupMe | PM Club Mentors", "https://web.groupme.com/chats"
    return dict(id=f"synth2-{idx:03d}-noon", crop=crop, screen=screen, crop_size=(560, 200),
                page_title=title, page_url=url, gold=gold, tags=["relative_date", "noon"])


def b_by5pm(rng, idx, variant):
    if variant == 0:
        crop, screen = gmail("Reimbursement forms", "Student Org Finance",
                             "<p>Please submit your reimbursement form <b>by 5pm Friday</b>. "
                             "Late submissions roll to next month's cycle.</p>")
        gold = [ev("Reimbursement form due", iso(d(9, 4), 17), end=iso(d(9, 4), 17))]
        title, url, size = "Reimbursement forms - Gmail", "https://mail.google.com/mail/u/0/#inbox", (700, 280)
    else:
        crop, screen = slack([("Marcus L.", "8:40 AM", "reminder: peer reviews are due by noon Thursday"),
                              ("Devon", "8:41 AM", "on it")],
                             "eng-platform", ["general", "random"], "Meridian Systems")
        gold = [ev("Peer reviews due", iso(d(9, 3), 12), end=iso(d(9, 3), 12))]
        title, url, size = "eng-platform - Slack", "https://app.slack.com/client/T01/C02", (640, 160)
    return dict(id=f"synth2-{idx:03d}-by5pm", crop=crop, screen=screen, crop_size=size,
                page_title=title, page_url=url, gold=gold, tags=["deadline", "relative_date"])


def b_zoom(rng, idx, variant):
    dt = d(9, 17)
    crop, screen = gmail("Research group meeting", "Prof. Ana Villarreal",
                         f"<p>Our next research group meeting is <b>{long(dt)} at 4:00 PM</b>.</p>"
                         "<p>Join Zoom Meeting<br><a href='#'>https://utexas.zoom.us/j/81234567890</a></p>")
    gold = [ev("Research group meeting", iso(dt, 16), location="Zoom")]
    return dict(id=f"synth2-{idx:03d}-zoom", crop=crop, screen=screen, crop_size=(700, 300),
                page_title="Research group meeting - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox",
                gold=gold, tags=["platform_venue"])


def b_range_noon(rng, idx, variant):
    dt = d(9, 9)
    crop, screen = flyer("all majors", "CAREER FAIR PREP", f"{wd3(dt)} {abbr(dt)} · 11am–1pm",
                         "WCP Legacy Room · resume reviews + mock interviews", ("#5b1a3c", "#ffe9f2"),
                         "Get ready for the fall career fair — drop in anytime between 11 and 1.",
                         "texascareers")
    gold = [ev("Career Fair Prep", iso(dt, 11), end=iso(dt, 13), location="WCP Legacy Room")]
    return dict(id=f"synth2-{idx:03d}-rangenoon", crop=crop, screen=screen, crop_size=(520, 460),
                page_title="Texas Careers on Instagram", page_url="https://www.instagram.com/p/CFP2026/",
                gold=gold, tags=["crosses_noon"])


def b_dark_gmail(rng, idx, variant):
    if variant == 0:
        dt = d(9, 22)
        crop, screen = gmail_dark("Thesis committee check-in", "Ana Villarreal",
                                  f"<p>Let's do the committee check-in <b>{long(dt)} at 10:00 AM</b> in "
                                  "<b>GDC 4.304</b>. Bring the updated results section.</p>")
        gold = [ev("Thesis committee check-in", iso(dt, 10), location="GDC 4.304")]
    else:
        dt = d(9, 26)
        crop, screen = gmail_dark("Volunteer briefing", "HackTX Organizers",
                                  f"<p>Volunteer briefing is <b>{long(dt)}, 9:00–10:30 AM</b> in <b>EER 1.516</b>. "
                                  "Shirts will be handed out there.</p>")
        gold = [ev("Volunteer briefing", iso(dt, 9), end=iso(dt, 10, 30), location="EER 1.516")]
    return dict(id=f"synth2-{idx:03d}-darkmail", crop=crop, screen=screen, crop_size=(700, 280),
                page_title=f"{gold[0]['title']} - Gmail", page_url="https://mail.google.com/mail/u/0/#inbox",
                gold=gold, tags=["dark_mode"])


def b_nonevent(rng, idx, variant):
    if variant == 0:
        crop, screen = gmail("Your order #48213 is confirmed", "Campus Store",
                             "<p><b>Order placed September 1, 2026</b></p>"
                             "<p>1 × TI-84 Plus CE — $124.99<br>2 × Composition notebook — $7.98<br>"
                             "Subtotal $132.97 · Shipping free</p><p>We'll email you when it ships.</p>")
        title, url, size = "Your order #48213 is confirmed - Gmail", "https://mail.google.com/mail/u/0/#inbox", (700, 300)
        kind = "order"
    elif variant == 1:
        body = ("<div class='art'><div class='ah'>Council approves downtown transit lane</div>"
                "<div class='ab'>By R. Okafor · Sep 1, 2026</div>"
                "<p>On August 20, the city council voted 7–2 to convert one lane of Guadalupe Street "
                "to bus-only service. The change took effect over the weekend and drew mixed reviews "
                "from drivers on Monday morning.</p></div>")
        crop = page(ARTICLE_CSS, body)
        screen = page(ARTICLE_CSS, "<div style='background:#111;color:#fff;padding:12px 20px;"
                                   "font-weight:800'>THE WIRE</div>" + body)
        title, url, size = "Council approves downtown transit lane — The Wire", "https://thewire.example.com/transit", (680, 300)
        kind = "news"
    elif variant == 2:
        lines = [
            "<span class='ts'>2026-09-01 11:42:07</span> <span class='ok'>INFO</span>  worker-3 started (pid 48213)",
            "<span class='ts'>2026-09-01 11:42:09</span> <span class='ok'>INFO</span>  connected to db at 10.0.0.12:5432",
            "<span class='ts'>2026-09-01 11:43:15</span> <span class='warn'>WARN</span>  retrying job 771 (attempt 2/5)",
            "<span class='ts'>2026-09-01 11:43:16</span> <span class='err'>ERROR</span> job 771 failed: timeout after 30s",
            "<span class='ts'>2026-09-01 11:43:16</span> <span class='ok'>INFO</span>  scheduled retry at 11:48:16",
        ]
        crop = page(TERM_CSS, "<div class='term'>" + "\n".join(lines) + "</div>")
        screen = page(TERM_CSS, "<div class='term'>$ tail -f logs/worker.log\n" + "\n".join(lines) + "\n</div>")
        title, url, size = "worker.log — Terminal", "file:///Users/vedanth/Desktop/terminal.png", (700, 200)
        kind = "log"
    else:
        crop, screen = gmail("Your package was delivered", "Shipping Updates",
                             "<p>Your package was delivered on <b>Monday, August 31 at 2:14 PM</b> and "
                             "left at the front door.</p><p>Tracking: 1Z 999 AA1 01 2345 6784</p>")
        title, url, size = "Your package was delivered - Gmail", "https://mail.google.com/mail/u/0/#inbox", (700, 260)
        kind = "delivered"
    return dict(id=f"synth2-{idx:03d}-nonevent-{kind}", crop=crop, screen=screen, crop_size=size,
                page_title=title, page_url=url, gold=[], tags=["nonevent"])


MIX = [
    (b_canvas, 3), (b_syllabus, 2), (b_slack, 3), (b_outlook, 2), (b_xpost, 2), (b_ticket, 2),
    (b_sports, 2), (b_reminders, 2), (b_recurring, 3), (b_midnight, 2), (b_multiday, 2),
    (b_nextyear, 2), (b_discord24h, 2), (b_noon, 2), (b_by5pm, 2), (b_zoom, 1), (b_range_noon, 1),
    (b_dark_gmail, 2), (b_nonevent, 4),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="synth_v2")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    idx = total_events = 0
    for builder, count in MIX:
        for variant in range(count):
            idx += 1
            rng = random.Random(args.seed * 10_000 + idx)
            sc = builder(rng, idx, variant)
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
