"""Synthetic eval-case generator.

Renders realistic event sources (iMessage, GroupMe, Gmail, Discord, flyers,
event pages) as HTML via headless Chrome. Because the event content is
generated from parameters, the gold label is exact by construction — no human
verification needed. Every case uses the same frozen fake "now" so relative
dates ("this Friday", "tomorrow") have deterministic answers.

Synthetic cases test extraction *logic* (date resolution, timezones,
recurrence, multi-event, non-events); real captures remain the gold standard
for pixel-level messiness.

Usage (from ml/):  uv run python -m synth.generate [--dest synth_v0]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DATA = Path(__file__).resolve().parents[1] / "data"

# Frozen clock for every synthetic case: Tuesday, Sep 1 2026, noon, Austin TX.
NOW = "2026-09-01 12:00"
WEEKDAY = "Tuesday"
TZ = "America/Chicago"

RESET = (
    "*{margin:0;padding:0;box-sizing:border-box}"
    "body{font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased}"
)


def page(css: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<style>{RESET}{css}</style></head><body>{body}</body></html>"
    )


def ev(title, start, end=None, all_day=False, timezone=None, location=None,
       description=None, recurrence=None):
    return {
        "title": title, "start": start, "end": end, "all_day": all_day,
        "timezone": timezone, "location": location, "description": description,
        "recurrence": recurrence, "confidence": "high", "notes": None,
    }


# ---------------------------------------------------------------- templates

IMSG_CSS = (
    ".chat{background:#fff;padding:18px 14px;display:flex;flex-direction:column;gap:6px}"
    ".stamp{text-align:center;color:#8e8e93;font-size:11px;margin:6px 0}"
    ".b{max-width:72%;padding:9px 13px;border-radius:18px;font-size:15px;line-height:1.35}"
    ".in{background:#e9e9eb;color:#000;align-self:flex-start;border-bottom-left-radius:5px}"
    ".out{background:#0b93f6;color:#fff;align-self:flex-end;border-bottom-right-radius:5px}"
    ".shell{background:#f5f5f7;height:100vh;display:flex}"
    ".side{width:230px;background:#e8e8ed;border-right:1px solid #d1d1d6;padding:14px 10px;font-size:13px}"
    ".side .c{padding:9px 8px;border-radius:8px;color:#333}.side .on{background:#0b93f6;color:#fff}"
    ".main{flex:1;display:flex;flex-direction:column}"
    ".hdr{padding:12px;text-align:center;font-weight:600;font-size:14px;border-bottom:1px solid #e0e0e0;background:#fafafa}"
)


def imessage(convo_html: str, contact: str, sidebar: list[str]) -> tuple[str, str]:
    crop = page(IMSG_CSS, f"<div class='chat'>{convo_html}</div>")
    chats = f"<div class='c on'>{contact}</div>" + "".join(
        f"<div class='c'>{n}</div>" for n in sidebar
    )
    screen = page(
        IMSG_CSS,
        f"<div class='shell'><div class='side'>{chats}</div><div class='main'>"
        f"<div class='hdr'>{contact}</div><div class='chat'>{convo_html}</div></div></div>",
    )
    return crop, screen


GM_CSS = (
    ".gm{background:#fff;padding:14px}"
    ".m{display:flex;gap:10px;margin-bottom:14px}"
    ".av{width:34px;height:34px;border-radius:50%;background:#00aff0;color:#fff;display:flex;"
    "align-items:center;justify-content:center;font-weight:700;font-size:14px;flex:none}"
    ".who{font-size:12px;color:#888;margin-bottom:2px}.txt{font-size:14px;line-height:1.4}"
    ".ghdr{background:#00aff0;color:#fff;padding:14px;font-weight:600}"
    ".gshell{background:#f2f2f2;height:100vh}"
)


def groupme(msgs: list[tuple[str, str]], group: str) -> tuple[str, str]:
    rows = "".join(
        f"<div class='m'><div class='av'>{w[0]}</div><div><div class='who'>{w}</div>"
        f"<div class='txt'>{t}</div></div></div>"
        for w, t in msgs
    )
    crop = page(GM_CSS, f"<div class='gm'>{rows}</div>")
    screen = page(
        GM_CSS,
        f"<div class='gshell'><div class='ghdr'>{group}</div><div class='gm'>{rows}</div></div>",
    )
    return crop, screen


MAIL_CSS = (
    ".mail{background:#fff;padding:22px;max-width:680px}"
    ".subj{font-size:20px;margin-bottom:14px}"
    ".from{font-size:13px;color:#555;margin-bottom:18px;padding-bottom:12px;border-bottom:1px solid #eee}"
    ".from b{color:#202124}"
    ".body{font-size:14px;line-height:1.6;color:#202124}.body p{margin-bottom:12px}"
    ".gbar{background:#f6f8fc;padding:10px 18px;font-size:18px;color:#5f6368;border-bottom:1px solid #e0e0e0}"
    ".gbar b{color:#ea4335}"
)


def gmail(subject: str, sender: str, body_html: str) -> tuple[str, str]:
    inner = (
        f"<div class='mail'><div class='subj'>{subject}</div>"
        f"<div class='from'><b>{sender}</b> &lt;no-reply@{sender.lower().replace(' ', '')}.org&gt; "
        f"— Tue, Sep 1, 2026, 9:14 AM</div><div class='body'>{body_html}</div></div>"
    )
    crop = page(MAIL_CSS, inner)
    screen = page(MAIL_CSS, f"<div class='gbar'><b>M</b> Gmail — Inbox</div>{inner}")
    return crop, screen


FLYER_CSS = (
    ".fl{height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;"
    "text-align:center;gap:14px;padding:30px}"
    ".k{font-size:13px;letter-spacing:3px;text-transform:uppercase;opacity:.75}"
    ".t{font-size:40px;font-weight:800;line-height:1.05}"
    ".d{font-size:20px;font-weight:600}.s{font-size:15px;opacity:.85}"
    ".ig{background:#000;height:100vh;display:flex}"
    ".igpane{width:58%;display:flex;align-items:center;justify-content:center}"
    ".igside{flex:1;background:#111;color:#eee;padding:22px;font-size:14px;line-height:1.5}"
    ".igside b{display:block;margin-bottom:10px}"
    ".igframe{width:430px;height:520px;display:flex;flex-direction:column;align-items:center;"
    "justify-content:center;text-align:center;gap:14px;padding:26px}"
)


def flyer(kicker, title, dateline, sub, colors, caption, handle) -> tuple[str, str]:
    bg, fg = colors
    inner = (
        f"<div class='k'>{kicker}</div><div class='t'>{title}</div>"
        f"<div class='d'>{dateline}</div><div class='s'>{sub}</div>"
    )
    crop = page(FLYER_CSS, f"<div class='fl' style='background:{bg};color:{fg}'>{inner}</div>")
    screen = page(
        FLYER_CSS,
        f"<div class='ig'><div class='igpane'><div class='igframe' style='background:{bg};color:{fg}'>"
        f"{inner}</div></div><div class='igside'><b>{handle}</b>{caption}"
        "<div style='margin-top:14px;color:#777'>1d &nbsp; 87 likes</div></div></div>",
    )
    return crop, screen


DISCORD_CSS = (
    ".dc{background:#313338;color:#dbdee1;padding:16px;font-size:15px}"
    ".dm{display:flex;gap:12px;margin-bottom:16px}"
    ".dav{width:38px;height:38px;border-radius:50%;background:#5865f2;color:#fff;display:flex;"
    "align-items:center;justify-content:center;font-weight:700;flex:none}"
    ".dw{font-weight:600;color:#f2f3f5}.dt{color:#949ba4;font-size:12px;margin-left:6px}"
    ".dtxt{line-height:1.45;margin-top:2px}"
    ".dshell{display:flex;height:100vh;background:#313338}"
    ".dside{width:200px;background:#2b2d31;color:#949ba4;padding:14px;font-size:14px}"
    ".dside .ch{padding:5px 8px;border-radius:4px}.dside .chon{background:#404249;color:#fff}"
    ".dhdr{padding:12px 16px;border-bottom:1px solid #26272b;color:#f2f3f5;font-weight:600}"
)


def discord(msgs: list[tuple[str, str]], channel: str, others: list[str]) -> tuple[str, str]:
    rows = "".join(
        f"<div class='dm'><div class='dav'>{w[0]}</div><div><span class='dw'>{w}</span>"
        f"<span class='dt'>Today at 11:02 AM</span><div class='dtxt'>{t}</div></div></div>"
        for w, t in msgs
    )
    crop = page(DISCORD_CSS, f"<div class='dc'>{rows}</div>")
    chans = f"<div class='ch chon'># {channel}</div>" + "".join(
        f"<div class='ch'># {c}</div>" for c in others
    )
    screen = page(
        DISCORD_CSS,
        f"<div class='dshell'><div class='dside'>{chans}</div><div style='flex:1'>"
        f"<div class='dhdr'># {channel}</div><div class='dc'>{rows}</div></div></div>",
    )
    return crop, screen


ARTICLE_CSS = (
    ".art{background:#fff;max-width:660px;padding:30px;color:#1a1a1a}"
    ".ah{font-size:28px;font-weight:800;line-height:1.15;margin-bottom:8px}"
    ".ab{font-size:13px;color:#777;margin-bottom:18px}"
    ".art p{font-size:16px;line-height:1.6;margin-bottom:14px}"
)


# ---------------------------------------------------------------- scenarios

def build_scenarios() -> list[dict]:
    s: list[dict] = []

    # 1. iMessage, relative date + implicit pm + venue in reply
    convo = (
        "<div class='stamp'>Today 11:42 AM</div>"
        "<div class='b in'>hey are we still on for dinner this friday?</div>"
        "<div class='b out'>yes!! 7 works right</div>"
        "<div class='b in'>perfect, let's do Odd Duck</div>"
        "<div class='b out'>booked \U0001f44d</div>"
    )
    crop, screen = imessage(convo, "Maya", ["Mom", "Rahul", "CS study grp"])
    s.append(dict(
        id="synth-01-imessage-relative", crop=crop, screen=screen, crop_size=(560, 300),
        page_title="Screenshot 2026-09-01 at 11.48.02 AM.png",
        page_url="file:///Users/vedanth/Desktop/Screenshot%202026-09-01.png",
        gold=[ev("Dinner with Maya", "2026-09-04T19:00:00", location="Odd Duck")],
    ))

    # 2. GroupMe, "tomorrow" + time range + place
    crop, screen = groupme(
        [("Priya", "study session tomorrow 6-8pm in PCL 3rd floor, bring laptops"),
         ("Devon", "i'll be there"), ("Sam", "same, saving seats")],
        "CS 331 Study Group",
    )
    s.append(dict(
        id="synth-02-groupme-tomorrow", crop=crop, screen=screen, crop_size=(620, 300),
        page_title="GroupMe | CS 331 Study Group",
        page_url="https://web.groupme.com/chats",
        gold=[ev("CS 331 study session", "2026-09-02T18:00:00",
                 end="2026-09-02T20:00:00", location="PCL 3rd floor")],
    ))

    # 3. Gmail, explicit non-local timezone
    crop, screen = gmail(
        "Webinar invitation: Intro to RAG Systems",
        "AI Builders Guild",
        "<p>Hi Vedanth,</p><p>You're confirmed for our webinar <b>Intro to RAG"
        " Systems</b> on <b>Thursday, September 10 at 3:00 PM Eastern Time</b>."
        " The session runs one hour; a Zoom link will follow the day before.</p>",
    )
    s.append(dict(
        id="synth-03-gmail-timezone", crop=crop, screen=screen, crop_size=(700, 360),
        page_title="Webinar invitation: Intro to RAG Systems - Gmail",
        page_url="https://mail.google.com/mail/u/0/#inbox",
        gold=[ev("Intro to RAG Systems webinar", "2026-09-10T15:00:00",
                 end="2026-09-10T16:00:00", timezone="America/New_York",
                 location="Zoom")],
    ))

    # 4. Gmail digest, two distinct events
    crop, screen = gmail(
        "This Week at the Union",
        "Texas Union Events",
        "<p><b>Live at the Union: The Midnight Hour</b><br>Friday, September 4"
        " · 8:00 PM · Hogg Auditorium. Free with student ID.</p>"
        "<p><b>Trail Cleanup Volunteering</b><br>Saturday, September 5 · 10:00 AM"
        " – 1:00 PM · meet at the Zilker Park entrance. Gloves provided.</p>",
    )
    s.append(dict(
        id="synth-04-gmail-digest-multi", crop=crop, screen=screen, crop_size=(700, 380),
        page_title="This Week at the Union - Gmail",
        page_url="https://mail.google.com/mail/u/0/#inbox",
        gold=[
            ev("Live at the Union: The Midnight Hour", "2026-09-04T20:00:00",
               location="Hogg Auditorium"),
            ev("Trail Cleanup Volunteering", "2026-09-05T10:00:00",
               end="2026-09-05T13:00:00", location="Zilker Park entrance"),
        ],
    ))

    # 5. Flyer, weekly recurrence, explicit series start
    crop, screen = flyer(
        "free · all levels", "YOGA ON THE LAWN",
        "Every Tuesday · 6:00 PM", "starting September 8 · South Mall",
        ("#2d4739", "#f2ede3"),
        "Bring a mat and a friend. Every Tuesday evening on the South Mall,"
        " starting Sept 8. \U0001f9d8", "utrecsports",
    )
    s.append(dict(
        id="synth-05-flyer-recurrence", crop=crop, screen=screen, crop_size=(520, 480),
        page_title="UT RecSports on Instagram",
        page_url="https://www.instagram.com/p/AbCdEfGh123/",
        gold=[ev("Yoga on the Lawn", "2026-09-08T18:00:00", location="South Mall",
                 recurrence="RRULE:FREQ=WEEKLY;BYDAY=TU")],
    ))

    # 6. Flyer, year missing, date just PAST — context says fall '26
    crop, screen = flyer(
        "fall '26 welcome week", "KICKOFF MIXER",
        "August 28 · 5 PM", "Gregory Plaza · free tacos",
        ("#1a2c5b", "#ffd9a0"),
        "Welcome week is here!! Kickoff mixer Friday Aug 28, Gregory Plaza."
        " See you there \U0001f389", "utwelcomeweek",
    )
    s.append(dict(
        id="synth-06-flyer-year-past", crop=crop, screen=screen, crop_size=(520, 480),
        page_title="Welcome Week on Instagram",
        page_url="https://www.instagram.com/p/XyZaBcDe456/",
        gold=[ev("Kickoff Mixer", "2026-08-28T17:00:00", location="Gregory Plaza")],
    ))

    # 7. Discord, numeric date + evening time + voice channel
    crop, screen = discord(
        [("nova", "playtest session <b>Wed 9/9 at 8pm</b>, hop in the Game Night VC —"
                   " new build drops an hour before"),
         ("jae", "finally. i'm in")],
        "playtesting", ["general", "bug-reports", "art"],
    )
    s.append(dict(
        id="synth-07-discord-playtest", crop=crop, screen=screen, crop_size=(640, 260),
        page_title="Discord | #playtesting | Indie Game Club",
        page_url="https://discord.com/channels/812345/9098765",
        gold=[ev("Playtest session", "2026-09-09T20:00:00", location="Game Night VC")],
    ))

    # 8. Event page, fully specified (the easy control case)
    body = (
        "<div class='art'><div class='ah'>Austin Print Fair 2026</div>"
        "<div class='ab'>Presented by ATX Makers Collective</div>"
        "<p><b>Sunday, September 13, 2026 · 2:00 PM – 5:00 PM CDT</b></p>"
        "<p><b>Zilker Park</b>, 2100 Barton Springs Rd, Austin, TX</p>"
        "<p>Fifty local printmakers, live demos, and a zine swap. Tickets $5"
        " at the gate; kids free.</p></div>"
    )
    crop = page(ARTICLE_CSS, body)
    screen = page(
        ARTICLE_CSS,
        "<div style='background:#f05537;color:#fff;padding:12px 20px;font-weight:700'>"
        "eventbrite</div>" + body,
    )
    s.append(dict(
        id="synth-08-eventpage-full", crop=crop, screen=screen, crop_size=(680, 340),
        page_title="Austin Print Fair 2026 Tickets - Eventbrite",
        page_url="https://www.eventbrite.com/e/austin-print-fair-2026-tickets-1029",
        gold=[ev("Austin Print Fair 2026", "2026-09-13T14:00:00",
                 end="2026-09-13T17:00:00", location="Zilker Park")],
    ))

    # 9. Non-event: chat with a date-adjacent word but no event
    convo = (
        "<div class='stamp'>Today 10:15 AM</div>"
        "<div class='b in'>did you watch the finale last night</div>"
        "<div class='b out'>NO SPOILERS i'm two episodes behind</div>"
        "<div class='b in'>lmaooo ok hurry up</div>"
        "<div class='b out'>this weekend, promise</div>"
    )
    crop, screen = imessage(convo, "Rahul", ["Maya", "Mom", "roomies"])
    s.append(dict(
        id="synth-09-nonevent-chat", crop=crop, screen=screen, crop_size=(560, 290),
        page_title="Screenshot 2026-09-01 at 10.20.44 AM.png",
        page_url="file:///Users/vedanth/Desktop/Screenshot%20chat.png",
        gold=[],
    ))

    # 10. Non-event: news article paragraph
    body = (
        "<div class='art'><div class='ah'>Chipmakers double down on advanced"
        " packaging</div><div class='ab'>By T. Alvarez · Sep 1, 2026</div>"
        "<p>Advanced packaging has become the industry's favorite lever for"
        " squeezing more performance out of silicon without waiting for the"
        " next process node.</p><p>Analysts expect capacity to stay tight"
        " through next year as demand from AI accelerators outpaces new"
        " fab capacity.</p></div>"
    )
    crop = page(ARTICLE_CSS, body)
    screen = page(ARTICLE_CSS, "<div style='background:#111;color:#fff;padding:12px 20px;"
                  "font-weight:800;letter-spacing:2px'>THE WIRE</div>" + body)
    s.append(dict(
        id="synth-10-nonevent-article", crop=crop, screen=screen, crop_size=(680, 340),
        page_title="Chipmakers double down on advanced packaging — The Wire",
        page_url="https://thewire.example.com/2026/09/chip-packaging",
        gold=[],
    ))

    # 11. Non-event: meme-ish flyer parody with no real event info
    crop, screen = flyer(
        "breaking", "I AM ONCE AGAIN", "asking you to charge your laptop",
        "before section · thank you", ("#7a1f1f", "#fff"),
        "every TA ever \U0001f480", "utmemes",
    )
    s.append(dict(
        id="synth-11-nonevent-meme", crop=crop, screen=screen, crop_size=(520, 460),
        page_title="UT Memes on Instagram",
        page_url="https://www.instagram.com/p/MemePost789/",
        gold=[],
    ))

    return s


# ---------------------------------------------------------------- rendering

def render(html: str, out: Path, size: tuple[int, int]) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
        tmp = Path(f.name)
    try:
        subprocess.run(
            [CHROME, "--headless=new", f"--screenshot={out}",
             f"--window-size={size[0]},{size[1]}", "--hide-scrollbars",
             "--disable-gpu", f"file://{tmp}"],
            check=True, capture_output=True, timeout=60,
        )
        if not out.exists():
            raise RuntimeError(f"chrome produced no screenshot for {out.name}")
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="synth_v0")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    for sc in build_scenarios():
        out = DATA / args.dest / sc["id"]
        if out.exists() and not args.force:
            print(f"skip {sc['id']} (exists)")
            continue
        out.mkdir(parents=True, exist_ok=True)
        render(sc["crop"], out / "crop.png", sc["crop_size"])
        render(sc["screen"], out / "screen.png", (1440, 860))
        case = {
            "id": sc["id"],
            "context": {"now": NOW, "weekday": WEEKDAY, "timezone": TZ,
                        "pageTitle": sc["page_title"], "pageUrl": sc["page_url"]},
            "gold": {"events": sc["gold"]},
            "verification": {"status": "synthetic", "by": "generator",
                             "note": "gold derived from generation parameters"},
        }
        (out / "case.json").write_text(json.dumps(case, indent=2))
        print(f"generated {sc['id']} ({len(sc['gold'])} events)")

    print(f"\ndone -> data/{args.dest}/")

    from evals.report import build

    build()


if __name__ == "__main__":
    main()
