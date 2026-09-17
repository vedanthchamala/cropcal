"""How dates, times, and venues look in the wild — phrasing library seeded
from real captures (Instagram flyers, Gmail, Canvas, event sites, chats).

Every function takes the RNG and returns text; the caller keeps the exact
parameters so gold stays exact by construction.
"""
from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
MON_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MON_ABBR2 = ["Jan.", "Feb.", "Mar.", "Apr.", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]
MON_SEPT = ["Jan", "Feb", "Mar", "Apr", "May", "June", "July", "Aug", "Sept", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

FONTS_DISPLAY = ["Impact, 'Arial Black', sans-serif", "'Arial Black', Arial, sans-serif",
                 "Futura, 'Trebuchet MS', sans-serif", "'Avenir Next Condensed', 'Arial Narrow', sans-serif",
                 "Georgia, serif", "'Copperplate', serif", "'Didot', serif", "'Baskerville', serif",
                 "'Marker Felt', 'Comic Sans MS', cursive", "'Chalkboard SE', cursive",
                 "'American Typewriter', serif", "'Helvetica Neue', Helvetica, sans-serif",
                 "Optima, sans-serif", "'Gill Sans', sans-serif", "Verdana, sans-serif",
                 "'Trebuchet MS', sans-serif", "'Courier New', monospace", "Papyrus, fantasy",
                 "'Bradley Hand', cursive", "Rockwell, serif", "'Hoefler Text', serif"]
FONTS_BODY = ["-apple-system, 'Helvetica Neue', sans-serif", "Arial, sans-serif",
              "Georgia, serif", "Verdana, sans-serif", "'Trebuchet MS', sans-serif",
              "'Gill Sans', sans-serif", "Optima, sans-serif", "Tahoma, sans-serif"]

PALETTES = [  # (background, foreground, accent)
    ("#1a2c5b", "#ffd9a0", "#ff8c42"), ("#2d4739", "#f2ede3", "#c9a227"), ("#5b1a3c", "#ffe9f2", "#ffb3c6"),
    ("#20303c", "#a8e0ff", "#ffd166"), ("#3c2f1a", "#ffefc2", "#e07a5f"), ("#101820", "#f2aa4c", "#ffffff"),
    ("#0b3d91", "#ffffff", "#ffcc00"), ("#7a1f1f", "#ffffff", "#f5c518"), ("#f4f1ea", "#1b1b1b", "#c8102e"),
    ("#fff7e6", "#3b2a1a", "#d97706"), ("#e8f1ff", "#0f2a4a", "#1d4ed8"), ("#111111", "#ffffff", "#ff3b30"),
    ("#4b2e83", "#ffffff", "#b7a57a"), ("#bf5700", "#ffffff", "#333f48"), ("#8c1d40", "#ffc627", "#ffffff"),
    ("#00274c", "#ffcb05", "#ffffff"), ("#c8e6c9", "#1b5e20", "#ff7043"), ("#fde2e4", "#5a189a", "#ff006e"),
    ("#0f766e", "#ecfeff", "#facc15"), ("#faf3dd", "#5b21b6", "#c1121f"), ("#dbeafe", "#1e3a8a", "#f97316"),
]

ORGS = [  # (name, handle, descriptor)
    ("Texas Rocket Engineering Lab", "texasrocketlab", "rocketry team"),
    ("Longhorn Racing", "longhornracing", "Formula SAE team"), ("Ion Racing", "ionracing.ut", "formula-electric team"),
    ("Sun Devil Motorsports", "sun_devil_motorsports", "racing team"), ("Sling Health at UT", "slinghealthut", "med-tech incubator"),
    ("Austin Bodybuilding", "austin.bodybuilding", "lifting club"), ("BiTE", "bite.wisc", "biotech entrepreneurship org"),
    ("IEEE TAMU", "ieee_tamu", "engineering society"), ("Artificial Intelligence Society", "utdais", "AI student org"),
    ("UT ECAC", "ut_ecac", "engineering career center"), ("Product Space", "productspace.atx", "product fellowship"),
    ("Data Science Society", "dss.utx", "data science club"), ("Women in Computing", "wic.tex", "CS community org"),
    ("Consulting Collective", "consultingcollective", "student consulting group"), ("Robotics Guild", "roboguild", "robotics club"),
    ("Quantum Club", "quantumclub.atx", "quantum computing org"), ("Case Craft", "casecraft.u", "case competition org"),
    ("Freetail Hackers", "freetailhackers", "hackathon org"), ("Texas Convergent", "txconvergent", "build team"),
    ("Longhorn Silicon", "longhornsilicon", "hardware org"), ("Guadaloop", "guadaloop", "hyperloop team"),
    ("Texas Blockchain", "texasblockchain", "web3 club"), ("ACM at UT", "acm_utexas", "computing society"),
    ("Solar Vehicles Team", "solarsteers", "solar car team"), ("HackTX", "hacktx", "hackathon"),
    ("Longhorn Gaming", "longhorngaming", "esports org"), ("Texas Aerial Robotics", "texasaerial", "drone team"),
    ("Investment Club", "utinvest", "finance org"), ("Pre-Med Society", "premed.utx", "pre-health org"),
    ("Filipino Students Association", "fsa.tx", "cultural org"), ("Texas Ballroom", "txballroom", "dance org"),
]
VENUES = ["GDC 2.216", "EER 0.904", "PCL Learning Lab", "Union Ballroom", "ETC 2.136", "Gregory Gym Annex",
          "WCP Legacy Room", "RLM 4.102", "the Engineering Quad", "Student Pavilion", "McCombs Atrium",
          "Materials Science and Engineering Building Rm 265", "WEB 236C", "Union 3.304", "the Union",
          "front of EER", "GDC atrium", "Speedway Plaza", "Gregory Plaza", "PAI 4.18", "ASE 1.126",
          "Moody Center", "Hogg Auditorium", "South Mall", "Zilker Park", "Mohawk Austin", "STATION Austin, ACL Room",
          "2420 Guadalupe St, Austin, TX 78705", "Nolan Catholic High School, 4501 Bridge St, Fort Worth, TX",
          "Starbucks, 4169 Lyndon B Johnson Fwy, Dallas, TX 75244", "South Side Ballroom", "Kins Market",
          "Gong Cha on Guad", "Union Starbucks", "PCL 3rd floor", "JES A121A", "BUR 106", "GEA 105",
          "CPE 2.218", "NHB 1.720", "SAC 2.302", "the Perry-Castañeda Library", "Blanton Museum"]
PLATFORMS = ["Zoom", "Google Meet", "Microsoft Teams", "Discord"]
CAMPUS = ["GDC 2.216", "EER 0.904", "PCL Learning Lab", "Union Ballroom", "ETC 2.136", "Gregory Gym Annex", "WCP Legacy Room",
          "RLM 4.102", "the Engineering Quad", "Student Pavilion", "McCombs Atrium", "Materials Science and Engineering Building Rm 265",
          "WEB 236C", "Union 3.304", "the Union", "front of EER", "GDC atrium", "Speedway Plaza", "Gregory Plaza", "PAI 4.18",
          "ASE 1.126", "South Mall", "JES A121A", "BUR 106", "GEA 105", "CPE 2.218", "NHB 1.720", "SAC 2.302", "Blanton Museum"]
OFFCAMPUS = ["Nolan Catholic High School, 4501 Bridge St, Fort Worth, TX", "Westlake High School, 4100 Westbank Dr, Austin, TX",
             "Hilton Garden Inn Downtown, 500 N Interstate 35, Austin, TX", "Plano Senior High School, 2200 Independence Pkwy, Plano, TX",
             "Marriott Dallas Las Colinas, 223 W Las Colinas Blvd, Irving, TX", "Houston Marriott Westchase, 2900 Briarpark Dr, Houston, TX",
             "Bowie High School, 4103 W Slaughter Ln, Austin, TX", "Round Rock Public Library, 200 E Liberty Ave, Round Rock, TX"]
COFFEE = ["Starbucks, 4169 Lyndon B Johnson Fwy, Dallas, TX 75244", "Panera Bread, 2900 Guadalupe St, Austin, TX",
          "Houndstooth Coffee, 401 Congress Ave, Austin, TX", "Gong Cha on Guad", "Union Starbucks", "Kins Market", "Odd Duck",
          "PCL 3rd floor", "the GDC atrium", "2420 Guadalupe St, Austin, TX 78705"]
CONCERT = ["South Side Ballroom", "Moody Center", "Mohawk Austin", "Stubb's", "ACL Live", "House of Blues Houston", "Emo's", "Hogg Auditorium"]
STARTUP = ["STATION Austin, ACL Room", "Capital Factory, 16th floor", "The Riveter", "Zilker Park", "Mohawk Austin"]
EVENT_NAMES = ["General Body Meeting", "Kickoff Meeting", "Info Session", "Resume Workshop", "Alumni Panel",
               "Tryouts", "Guest Speaker Night", "Project Demo Day", "Study Jam", "Volunteer Day",
               "Speedfriending", "Open House", "Tech Talk", "Coffee Chat", "Officer Q&A", "Mentorship Informational",
               "Meet the Officers", "Application Office Hours", "Hackathon Kickoff", "Design Review",
               "Career Fair Prep", "Game Night", "Movie Night", "Social", "Tabling", "Open Garage",
               "Workshop: Intro to CAD", "Workshop: Intro to PCB Design", "Lightning Talks", "Bake Sale",
               "Trivia Night", "Networking Mixer", "Fall Kickoff", "Spring Kickoff", "Welcome Back Social",
               "Panel: Life After Graduation", "Case Competition Info Session", "Founders Fireside",
               "Bouldering Social", "Sunrise Hike", "Potluck", "Hot Cocoa Social", "Pumpkin Carving"]
DEADLINE_NAMES = ["Applications Due", "Applications Close", "Application Deadline", "Apply by", "Deadline to Register",
                  "RSVP by", "Registration Closes", "Dues Due", "Team Apps Due", "Submissions Due", "Last day to sign up"]
KICKERS = ["fall '26 recruitment", "spring recruitment", "join us", "all majors welcome", "free food", "save the date",
           "we're back", "new member social", "open to everyone", "no experience needed", "RSVP required", "限定 free tacos"]


def ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def sup_ordinal(n: int) -> str:
    return f"{n}<sup>{ordinal(n)[-2:]}</sup>"


def wd(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def date_text(rng: random.Random, d: date, *, year: bool = False, weekday: str | None = None,
              style: str | None = None, caps: bool = False, wd_sep: str | None = None,
              wd_form: str | None = None) -> str:
    """weekday: None=random, 'yes'/'no'. Styles roughly mirror the reference set.
    wd_sep / wd_form pin the weekday separator (', ', ' ', ' | ') and form
    ('long'/'short') so several dates in one document look consistent."""
    if weekday is None:
        weekday = rng.choice(["yes", "yes", "no"])
    styles = ["full", "full", "abbr", "sept", "abbr_dot", "slash", "dot", "ord_full", "ord_sup", "ord_abbr",
              "abbr_comma_wd", "wd_after", "iso_like", "dmy"]
    style = style or rng.choice(styles)
    m, day = d.month, d.day
    if style == "full":
        s = f"{MONTHS[m - 1]} {day}"
    elif style == "abbr":
        s = f"{MON_ABBR[m - 1]} {day}"
    elif style == "sept":
        s = f"{MON_SEPT[m - 1]} {day}"
    elif style == "abbr_dot":
        s = f"{MON_ABBR2[m - 1]} {day}"
    elif style == "slash":
        s = f"{m}/{day}"
    elif style == "dot":
        s = f"{m}.{day}"
    elif style == "ord_full":
        s = f"{MONTHS[m - 1]} {ordinal(day)}"
    elif style == "ord_sup":
        s = f"{MON_SEPT[m - 1]} {sup_ordinal(day)}"
    elif style == "ord_abbr":
        s = f"{MON_ABBR2[m - 1]} {ordinal(day)}"
    elif style == "abbr_comma_wd":  # "Thu, Oct 8"
        return f"{wd(d)[:3]}, {MON_ABBR[m - 1]} {day}" + (f", {d.year}" if year else "")
    elif style == "wd_after":  # "Sept. 13th, Sunday"
        return f"{MON_ABBR2[m - 1]} {ordinal(day)}, {wd(d)}"
    elif style == "iso_like":
        return f"{d.year}-{m:02d}-{day:02d}"
    elif style == "dmy":  # "17 Sep 2026"
        return f"{day} {MON_ABBR[m - 1]} {d.year}"
    else:
        s = f"{MONTHS[m - 1]} {day}"
    if year and style not in ("slash", "dot"):
        s += f", {d.year}"
    elif year and style in ("slash", "dot"):
        s += f"{'/' if style == 'slash' else '.'}{d.year % 100:02d}"
    if weekday == "yes":
        wdn = wd(d)
        form = wd_form or rng.choice(["long", "long", "short"])
        s = f"{wdn if form == 'long' else wdn[:3]}{wd_sep or rng.choice([', ', ' ', ' | '])}{s}"
    return s.upper() if caps else s


def _h12(t: time, minutes_style: str, ampm_style: str) -> str:
    h = t.hour % 12 or 12
    if minutes_style == "always" or t.minute:
        core = f"{h}:{t.minute:02d}"
    else:
        core = f"{h}"
    ap = "am" if t.hour < 12 else "pm"
    if ampm_style == "AM":
        ap = ap.upper()
    elif ampm_style == "a.m.":
        ap = "a.m." if ap == "am" else "p.m."
    elif ampm_style == "a":
        ap = ap[0]
    elif ampm_style == "none":
        return core
    sep = " " if ampm_style in ("AM", "a.m.") and minutes_style != "tight" else ""
    return f"{core}{sep}{ap}"


def time_text(rng: random.Random, start: time, end: time | None, *, style: str | None = None,
              tz_label: str = "", allow_24h: bool = False) -> str:
    """'6-8PM', '6:00 PM - 9:00 PM', '9:30 a.m. - 2 p.m.', '12 – 1 p.m.', 'at 6:30pm', '9-11:30AM' ...
    24-hour clock only when allow_24h (chats, international senders)."""
    styles = ["tight", "spaced", "dash_long", "words", "at", "noon_words", "24h"]
    style = style or rng.choices(styles, weights=[30, 30, 15, 10, 10, 2, 4 if allow_24h else 0])[0]
    if style == "24h":
        s = f"{start.hour:02d}:{start.minute:02d}"
        if end:
            s += f"–{end.hour:02d}:{end.minute:02d}"
        return s + tz_label
    if style == "noon_words" and start == time(12, 0):
        return "noon" + (f" - {_h12(end, 'auto', 'am')}" if end else "")
    ampm_style = rng.choice(["AM", "AM", "am", "a.m.", "a"])
    minutes_style = rng.choice(["auto", "auto", "always"])
    if style == "tight":  # 6-8PM / 9-11:30AM: am/pm only on the end
        if end:
            same_half = (start.hour < 12) == (end.hour < 12)
            a = _h12(start, minutes_style, "none") if same_half else _h12(start, minutes_style, ampm_style)
            return f"{a}-{_h12(end, minutes_style, ampm_style)}{tz_label}"
        return f"{_h12(start, minutes_style, ampm_style)}{tz_label}"
    if style == "spaced":  # 6:00 PM - 9:00 PM
        dash = rng.choice([" - ", " – ", "–", " to "])
        s = _h12(start, minutes_style, ampm_style)
        if end:
            s += f"{dash}{_h12(end, minutes_style, ampm_style)}"
        return s + tz_label
    if style == "dash_long":  # 12 – 1 p.m.  (am/pm only on end when same half)
        if end:
            same_half = (start.hour < 12) == (end.hour < 12)
            a = _h12(start, minutes_style, "none") if same_half else _h12(start, minutes_style, ampm_style)
            return f"{a} – {_h12(end, minutes_style, ampm_style)}{tz_label}"
        return _h12(start, minutes_style, ampm_style) + tz_label
    if style == "words":  # from 6 to 8 pm
        if end:
            return f"from {_h12(start, minutes_style, 'none')} to {_h12(end, minutes_style, ampm_style)}{tz_label}"
        return f"at {_h12(start, minutes_style, ampm_style)}{tz_label}"
    if style == "at":
        s = f"at {_h12(start, minutes_style, ampm_style)}"
        if end:
            s += f" until {_h12(end, minutes_style, ampm_style)}"
        return s + tz_label
    return _h12(start, minutes_style, ampm_style) + tz_label


TZ_LABELS = {  # user-visible label -> IANA
    "CT": "America/Chicago", "CDT": "America/Chicago", "CST": "America/Chicago", "Central": "America/Chicago",
    "ET": "America/New_York", "EDT": "America/New_York", "EST": "America/New_York", "Eastern": "America/New_York",
    "PT": "America/Los_Angeles", "PDT": "America/Los_Angeles", "PST": "America/Los_Angeles", "Pacific": "America/Los_Angeles",
    "MT": "America/Denver", "MDT": "America/Denver", "Mountain": "America/Denver",
}
USER_TZS = [("America/Chicago", 50), ("America/New_York", 20), ("America/Los_Angeles", 15),
            ("America/Denver", 8), ("America/Phoenix", 4), ("America/Detroit", 3)]


def pick_user_tz(rng: random.Random) -> str:
    return rng.choices([t for t, _ in USER_TZS], weights=[w for _, w in USER_TZS])[0]


def relative_phrase(rng: random.Random, now: datetime, d: date) -> str | None:
    """'tomorrow', 'this friday', 'next thursday' … only when unambiguous."""
    delta = (d - now.date()).days
    if delta == 0:
        return rng.choice(["today", "tonight"]) if True else None
    if delta == 1:
        return "tomorrow"
    if 2 <= delta <= 6:
        return rng.choice([f"this {wd(d).lower()}", f"this {wd(d)}", wd(d)])
    if 7 <= delta <= 13 and rng.random() < 0.5:
        return f"next {wd(d)}"
    return None


def iso(d: date, t: time | None = None) -> str:
    t = t or time(0, 0)
    return f"{d.isoformat()}T{t.hour:02d}:{t.minute:02d}:00"


def fmt_now(now: datetime) -> str:
    """Matches background.js: toLocaleString('en-US', {hour12:false})."""
    return f"{now.month}/{now.day}/{now.year}, {now.hour:02d}:{now.minute:02d}:{now.second:02d}"


def age_label(rng: random.Random, now: datetime, posted: datetime) -> str:
    delta = now - posted
    hrs = delta.total_seconds() / 3600
    if hrs < 1:
        return f"{max(1, int(delta.total_seconds() // 60))}m"
    if hrs < 24:
        return f"{int(hrs)}h"
    days = delta.days
    if days < 7:
        return f"{days}d"
    if days < 60:
        return f"{days // 7}w"
    return f"{MON_ABBR[posted.month - 1]} {posted.day}"


def rand_time(rng: random.Random, kind: str = "evening") -> time:
    if kind == "morning":
        h = rng.choice([8, 9, 9, 10, 10, 11])
    elif kind == "midday":
        h = rng.choice([11, 12, 12, 13])
    elif kind == "any":
        h = rng.choice([9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 18, 19, 19, 20])
    else:
        h = rng.choice([17, 18, 18, 18, 19, 19, 19, 20])
    m = rng.choices([0, 30, 15, 45], weights=[70, 22, 4, 4])[0]
    return time(h, m)


def add_minutes(t: time, minutes: int) -> tuple[time, int]:
    """Returns (time, day_carry)."""
    total = t.hour * 60 + t.minute + minutes
    return time((total // 60) % 24, total % 60), total // (24 * 60)


def time_pair(rng: random.Random, start: time, end: time) -> tuple[str, str]:
    """Two times formatted identically ('5:45 PM', '8:15 PM') for When:-style lines."""
    ampm_style = rng.choice(["AM", "AM", "am", "a.m."])
    minutes_style = rng.choice(["auto", "always", "always"])
    return _h12(start, minutes_style, ampm_style), _h12(end, minutes_style, ampm_style)
