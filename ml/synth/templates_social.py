"""Instagram feed / story pages and the flyer designs that live inside them,
plus chat apps. Every template marks the date cluster with id="tgt" so the
renderer can crop it. Modeled on real captures (feed posts from student orgs,
stories, bulleted / banner / two-column / big-date / pill-location flyers)."""
from __future__ import annotations

import random

from synth.styles import FONTS_BODY, FONTS_DISPLAY, PALETTES

RESET = ("*{margin:0;padding:0;box-sizing:border-box}"
         "body{font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased}"
         "sup{font-size:.55em;vertical-align:super}")


def page(css: str, body: str) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{RESET}{css}</style></head><body>{body}</body></html>"


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ------------------------------------------------------------------ helpers

def fake_qr(rng: random.Random, size: int = 110, fg: str = "#000", bg: str = "#fff") -> str:
    n = 21
    cells = []
    for y in range(n):
        for x in range(n):
            finder = (x < 7 and y < 7) or (x >= n - 7 and y < 7) or (x < 7 and y >= n - 7)
            if finder:
                on = (x in (0, 6) or y in (0, 6) or (2 <= x <= 4 and 2 <= y <= 4)) if x < 7 or y < 7 else False
                if x >= n - 7 and y < 7:
                    xx = x - (n - 7)
                    on = xx in (0, 6) or y in (0, 6) or (2 <= xx <= 4 and 2 <= y <= 4)
                if x < 7 and y >= n - 7:
                    yy = y - (n - 7)
                    on = x in (0, 6) or yy in (0, 6) or (2 <= x <= 4 and 2 <= yy <= 4)
            else:
                on = rng.random() < 0.45
            cells.append(f"<i style='background:{fg if on else bg}'></i>")
    return (f"<div style='display:grid;grid-template-columns:repeat({n},1fr);width:{size}px;height:{size}px;"
            f"background:{bg};padding:{size // 14}px;gap:0'>" + "".join(cells) + "</div>")


def photo_bg(rng: random.Random) -> str:
    """CSS background approximating a photo: layered gradients + grain."""
    hues = [rng.randint(0, 360) for _ in range(3)]
    return (f"background:"
            f"radial-gradient(circle at {rng.randint(10, 90)}% {rng.randint(10, 90)}%,hsla({hues[0]},60%,55%,.9),transparent 55%),"
            f"radial-gradient(circle at {rng.randint(10, 90)}% {rng.randint(10, 90)}%,hsla({hues[1]},50%,40%,.8),transparent 60%),"
            f"linear-gradient({rng.randint(0, 360)}deg,hsl({hues[2]},35%,25%),hsl({hues[2]},45%,60%));")


GRAIN = ("background-image:repeating-linear-gradient(0deg,rgba(255,255,255,.035) 0 1px,transparent 1px 3px),"
         "repeating-linear-gradient(90deg,rgba(0,0,0,.035) 0 1px,transparent 1px 2px);")


# ------------------------------------------------------------------ flyer designs
# Each design(rng, spec) -> inner html for a square/4:5 media box. spec keys:
# org, title, kicker, date_txt, time_txt, venue_txt (may be ''), extras (list),
# palette (bg, fg, accent), font_d, font_b, qr (bool)

def _fonts(rng):
    return rng.choice(FONTS_DISPLAY), rng.choice(FONTS_BODY)


def design_poster_banner(rng, s) -> str:
    bg, fg, acc = s["palette"]
    cols = [s["date_txt"], s["venue_txt"] or s["extras"][0] if s["extras"] else s["venue_txt"], s["time_txt"]]
    cols = [c for c in cols if c]
    bars = "".join(f"<div class='pc'>{c}</div>" for c in cols)
    return (f"<div class='fl' style='{photo_bg(rng)}color:{fg};justify-content:space-between;padding:34px 26px'>"
            f"<div><div class='t' style='font-family:{s['font_d']};color:{acc};font-size:44px'>{esc(s['title']).upper()}</div>"
            f"<div class='scr' style='font-family:{rng.choice(['Snell Roundhand','Brush Script MT','Apple Chancery','Zapfino'])},cursive;"
            f"font-size:{rng.randint(38, 52)}px;margin-top:10px'>{esc(s['org'])}</div></div>"
            f"<div id='tgt' class='pbar' style='font-family:{s['font_d']}'>{bars}</div></div>")


def design_bullets(rng, s) -> str:
    bg, fg, acc = s["palette"]
    marker = rng.choice(["▶", "•", "→", "★", "✦"])
    lines = [s["time_txt"], s["date_txt"]] if rng.random() < .5 else [s["date_txt"], s["time_txt"]]
    if s["venue_txt"]:
        lines.append(s["venue_txt"])
    lines += s["extras"][:2]
    items = "".join(f"<div class='bl'><span style='color:{acc}'>{marker}</span> {l}</div>" for l in lines if l)
    return (f"<div class='fl' style='background:{bg};color:{fg};align-items:flex-start;padding:30px'>"
            f"<div class='k' style='color:{acc}'>{esc(s['org']).upper()}</div>"
            f"<div class='t' style='font-family:{s['font_d']};font-size:{rng.randint(40, 54)}px'>{esc(s['title']).upper()}</div>"
            f"<div style='flex:1'></div><div id='tgt' style='font-family:{s['font_b']};font-weight:700;font-size:17px;"
            f"line-height:1.9;text-align:left'>{items}</div>"
            + (f"<div class='s' style='margin-top:14px;font-size:12px;letter-spacing:1px'>{esc(s['extras'][2]).upper()}</div>" if len(s['extras']) > 2 else "")
            + "</div>")


def design_two_col(rng, s) -> str:
    bg, fg, acc = s["palette"]
    right = [s["venue_txt"]] + s["extras"][:1]
    left = [s["date_txt"] + ",", s["time_txt"]]
    l = "".join(f"<div>{x}</div>" for x in left if x)
    r = "".join(f"<div>{x}</div>" for x in right if x)
    return (f"<div class='fl' style='background:{bg};color:{fg};{GRAIN}padding:28px;justify-content:flex-start;gap:22px'>"
            f"<div class='t' style='font-family:{s['font_d']};font-size:{rng.randint(30, 40)}px;line-height:1.25;letter-spacing:1px'>"
            f"{esc(s['title']).upper()}</div>"
            f"<div id='tgt' style='display:grid;grid-template-columns:1fr 1fr;gap:10px 18px;width:100%;font-family:{s['font_d']};"
            f"font-size:20px;letter-spacing:1px;text-align:left;line-height:1.3'><div>{l}</div><div>{r}</div></div>"
            f"<div style='display:flex;gap:16px;margin-top:auto;width:100%'>"
            f"<div style='flex:1;height:120px;{photo_bg(rng)}border-radius:6px'></div>"
            + (fake_qr(rng, 120) if s['qr'] else "") + "</div></div>")


def design_big_date(rng, s) -> str:
    bg, fg, acc = s["palette"]
    label = s.get("label") or rng.choice(["APPLICATION DEADLINE:", "SAVE THE DATE", "MARK YOUR CALENDARS", "WHEN:", "NEXT MEETING"])
    qr = ""
    if s["qr"]:
        qr = ("<div style='display:flex;gap:18px;justify-content:center;margin:10px 0 26px'>"
              + "".join(f"<div><div style='font-size:12px;letter-spacing:2px;font-weight:700;margin-bottom:8px'>{t}</div>{fake_qr(rng, 100)}</div>"
                        for t in rng.sample(["DUES:", "FLARE:", "TEAM APP:", "RSVP:", "INTEREST FORM:"], 3)) + "</div>")
    joiner = rng.choice([" at ", " · ", " | ", "<br>"])
    return (f"<div class='fl' style='background:{bg};color:{fg};align-items:flex-start;padding:30px;justify-content:flex-start'>"
            f"<div style='display:flex;justify-content:space-between;width:100%;font-size:13px'><span>{esc(s['org'])}</span>"
            f"<span style='color:{acc};font-weight:700'>{s.get('season', '')}</span></div>{qr}"
            f"<div class='k' style='letter-spacing:3px;font-weight:700;font-size:15px;margin-top:auto'>{label}</div>"
            f"<div id='tgt' style='font-family:{s['font_b']};font-weight:800;font-size:{rng.randint(40, 52)}px;color:{acc};"
            f"line-height:1.05;text-align:left;margin:8px 0'>{s['date_txt']}{joiner}{s['time_txt']}"
            + (f"<div style='font-size:22px;color:{fg};margin-top:8px'>{s['venue_txt']}</div>" if s['venue_txt'] else "") + "</div>"
            f"<div style='font-weight:700;font-size:15px;letter-spacing:1px'>{esc(s['extras'][0]) if s['extras'] else 'DM us with any questions!'}</div></div>")


def design_pill_location(rng, s) -> str:
    bg, fg, acc = s["palette"]
    sep = rng.choice([" | ", " · ", " — ", "  "])
    return (f"<div class='fl' style='{photo_bg(rng)}color:#fff;justify-content:flex-start;padding:26px 20px'>"
            f"<div class='t' style='font-family:{s['font_d']};font-size:{rng.randint(50, 66)}px;line-height:.95;"
            f"text-shadow:0 3px 12px rgba(0,0,0,.5)'>{esc(s['title']).upper()}</div>"
            f"<div id='tgt' style='margin-top:{rng.randint(16, 48)}px'>"
            + (f"<div style='display:inline-block;background:{acc};color:#fff;padding:9px 20px;border-radius:9px;font-weight:800;"
               f"font-size:20px;letter-spacing:1px'>📍 {s['venue_txt'].upper()}</div>" if s['venue_txt'] else "")
            + f"<div style='font-style:italic;font-weight:700;font-size:21px;margin-top:12px;text-shadow:0 2px 8px rgba(0,0,0,.6)'>"
              f"{s['date_txt']}{sep}{s['time_txt']}</div></div>"
              f"<div style='margin-top:auto;align-self:flex-end;font-family:{s['font_d']};font-size:30px;letter-spacing:2px'>{esc(s['org']).split()[0].upper()}</div></div>")


def design_plain_card(rng, s) -> str:
    bg, fg, acc = ("#f7f5fb", "#1b1b1b", rng.choice(["#5b21b6", "#1d4ed8", "#0f766e", "#b91c1c"]))
    lead = rng.choice(["We will be hosting", "Join us for", "You're invited to", "Announcing"])
    return (f"<div class='fl' style='background:{bg};color:{fg};align-items:flex-start;padding:34px;justify-content:flex-start;text-align:left'>"
            f"<div style='display:flex;justify-content:space-between;width:100%;font-size:13px'><span>{esc(s['org'])}</span>"
            f"<span style='color:{acc};font-weight:700'>{s.get('season', '')}</span></div>"
            f"<div style='margin-top:{rng.randint(30, 70)}px;font-size:18px;letter-spacing:2px'>{lead}</div>"
            f"<div style='font-family:{s['font_b']};font-weight:800;font-size:{rng.randint(38, 48)}px;color:{acc};line-height:1.05;margin:6px 0 22px'>{esc(s['title'])}</div>"
            f"<div id='tgt' style='font-family:{s['font_b']};font-weight:700;font-size:21px;line-height:1.35'>{s['date_txt']}<br>{s['time_txt']}"
            + (f" in {s['venue_txt']}" if s['venue_txt'] else "") + "</div>"
            f"<div style='font-size:19px;line-height:1.35;margin-top:22px;font-weight:600'>{esc(s['extras'][0]) if s['extras'] else ''}</div></div>")


def design_minimal(rng, s) -> str:
    bg, fg, acc = s["palette"]
    return (f"<div class='fl' style='background:{bg};color:{fg}'>"
            f"<div class='k' style='color:{acc}'>{esc(s['kicker'])}</div>"
            f"<div class='t' style='font-family:{s['font_d']};font-size:{rng.randint(36, 46)}px'>{esc(s['title']).upper()}</div>"
            f"<div id='tgt' style='font-size:22px;font-weight:600;line-height:1.5;margin-top:10px'>{s['date_txt']}<br>{s['time_txt']}"
            + (f"<br><span style='font-weight:400;opacity:.9'>{s['venue_txt']}</span>" if s['venue_txt'] else "") + "</div>"
            + (f"<div class='s'>{esc(s['extras'][0])}</div>" if s['extras'] else "") + "</div>")


def design_retro(rng, s) -> str:
    bg, fg, acc = ("#bfe0ea", "#4a3b1f", "#2f5233")
    return (f"<div class='fl' style='background:{bg};color:{fg};font-family:{rng.choice(['Luminari','Papyrus','Copperplate','Baskerville'])},serif'>"
            f"<div style='font-size:{rng.randint(64, 80)}px;line-height:.9;letter-spacing:2px'>{esc(s['title'])}</div>"
            f"<div id='tgt' style='font-size:22px;margin-top:20px;letter-spacing:1px'>{s['date_txt']}"
            + (f" · {s['time_txt']}" if s['time_txt'] else "") + (f" · {s['extras'][0]}" if s['extras'] else "") + "</div>"
            f"<div style='margin-top:30px;background:#fff;color:{fg};padding:10px 26px;transform:rotate(-4deg);font-size:26px;"
            f"box-shadow:2px 3px 0 rgba(0,0,0,.25)'>{rng.choice(['Apply Now', 'RSVP', 'Sign up', 'Register'])}</div></div>")


def design_schedule_rows(rng, s) -> str:
    """Multiple dated rows (recruitment timeline / week schedule)."""
    bg, fg, acc = s["palette"]
    rows = "".join(f"<div class='row'><div class='rd' style='color:{acc}'>{r['date_txt']}</div><div><div class='rn'>{esc(r['name'])}</div>"
                   + (f"<div class='rt'>{r['time_txt']}{(' · ' + r['venue_txt']) if r.get('venue_txt') else ''}</div>" if r.get('time_txt') else "")
                   + "</div></div>" for r in s["rows"])
    return (f"<div class='fl' style='background:{bg};color:{fg};justify-content:flex-start;gap:10px;padding:26px'>"
            f"<div class='k' style='color:{acc}'>{esc(s['kicker']).upper()}</div>"
            f"<div class='t' style='font-family:{s['font_d']};font-size:30px;margin-bottom:6px'>{esc(s['title']).upper()}</div>"
            f"<div id='tgt' style='width:100%;display:flex;flex-direction:column;gap:9px'>{rows}</div></div>")


DESIGNS = {
    "poster_banner": design_poster_banner, "bullets": design_bullets, "two_col": design_two_col,
    "big_date": design_big_date, "pill_location": design_pill_location, "plain_card": design_plain_card,
    "minimal": design_minimal, "retro": design_retro,
}

FLYER_CSS = (
    ".fl{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;"
    "text-align:center;gap:12px;padding:28px;overflow:hidden}"
    ".k{font-size:13px;letter-spacing:3px;text-transform:uppercase;opacity:.85;font-weight:700}"
    ".t{font-weight:900;line-height:1.02}.s{font-size:15px;opacity:.9;margin-top:6px}"
    ".pbar{display:flex;width:100%;justify-content:space-around;align-items:center;font-weight:900;font-size:22px;"
    "line-height:1.1;text-transform:uppercase;background:rgba(0,0,0,.35);padding:14px 8px;border-radius:4px}"
    ".pc{padding:0 12px;border-left:2px solid rgba(255,255,255,.8)}.pc:first-child{border-left:none}"
    ".bl{white-space:nowrap}.row{background:rgba(255,255,255,.94);color:#1b2430;border-radius:10px;padding:9px 14px;"
    "display:flex;gap:14px;align-items:center;text-align:left}.rd{font-weight:800;font-size:15px;white-space:nowrap;min-width:64px}"
    ".rn{font-size:14.5px;font-weight:600}.rt{font-size:12px;color:#54606e}"
)

# ------------------------------------------------------------------ Instagram feed page

IG_CSS = FLYER_CSS + (
    "body{background:#000;color:#f5f5f5;overflow:hidden}"
    ".rail{position:fixed;left:0;top:0;bottom:0;width:72px;border-right:1px solid #262626;display:flex;flex-direction:column;"
    "align-items:center;padding-top:26px;gap:22px;font-size:22px;color:#fff}"
    ".feed{width:470px;margin:0 auto;padding-top:14px;transform:translateX(-100px)}"
    ".ph{display:flex;align-items:center;gap:10px;padding:10px 0 8px}.av{width:34px;height:34px;border-radius:50%;"
    "background:linear-gradient(45deg,#f9ce34,#ee2a7b,#6228d7);padding:2px}.av i{display:block;width:100%;height:100%;border-radius:50%;background:#222}"
    ".hn{font-weight:600;font-size:14px}.age{color:#a8a8a8;font-size:14px}.sug{color:#a8a8a8;font-size:12px}"
    ".follow{margin-left:auto;background:#363636;color:#fff;font-weight:600;font-size:14px;padding:7px 16px;border-radius:8px}"
    ".dots{color:#fff;font-size:18px;padding-left:14px}.media{width:470px;border-radius:4px;overflow:hidden;background:#111}"
    ".acts{display:flex;gap:14px;padding:10px 0 6px;font-size:22px;align-items:center}.acts .cnt{font-size:14px;margin-left:-8px}"
    ".acts .bm{margin-left:auto}.likes{font-size:14px;font-weight:600;padding:2px 0}.cap{font-size:14px;line-height:1.35;padding:2px 0 14px}"
    ".cap b{font-weight:600}.cap .more{color:#a8a8a8}.msg{position:fixed;right:44px;bottom:44px;background:#1a1a1a;color:#fff;"
    "padding:14px 18px;border-radius:14px;font-weight:600;font-size:16px;box-shadow:0 2px 12px rgba(0,0,0,.4)}"
    ".story{background:#000;height:100vh;display:flex;align-items:center;justify-content:center}"
    ".sc{width:414px;height:736px;border-radius:14px;overflow:hidden;position:relative;display:flex;flex-direction:column;padding:16px}"
    ".sbar{display:flex;gap:3px;margin-bottom:10px}.sbar i{flex:1;height:2px;background:rgba(255,255,255,.4)}.sbar i.on{background:#fff}"
    ".shd{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;color:#fff;text-shadow:0 1px 3px rgba(0,0,0,.5)}"
    ".stx{background:rgba(0,0,0,.72);color:#fff;padding:8px 12px;border-radius:8px;font-weight:600;display:inline-block}"
    ".reply{margin-top:auto;border:1px solid rgba(255,255,255,.7);border-radius:22px;padding:11px 16px;color:#fff;font-size:14px;display:flex;justify-content:space-between}"
)

RAIL = "<div class='rail'>◎<div style='margin-top:120px'>⌂</div>▶<div>◇</div>♡<div>＋</div>●<div style='margin-top:auto;margin-bottom:26px'>≡</div></div>"


def ig_feed(rng: random.Random, media_html: str, handle: str, age: str, caption: str, *, likes: int | None = None,
            prev_caption: str = "", next_handle: str = "", media_h: int = 470, suggested: bool = True) -> str:
    likes_line = f"<div class='likes'>{likes:,} likes</div>" if likes else f"<div class='likes' style='font-weight:400'>Liked by <b>{rng.choice(['sylvia.reynaaa', 'eshaansheth', 'maya.k', 'rahul_p'])}</b> and <b>others</b></div>"
    prev = (f"<div class='cap' style='color:#ddd'><b>{esc(rng.choice(['cristiano', 'therock', 'scribe_hq', 'nasa']))}</b> {esc(prev_caption)} <span class='more'>… more</span></div>"
            if prev_caption else "")
    nxt = f"<div class='ph'><div class='av'><i></i></div><div><div class='hn'>{esc(next_handle)}</div><div class='sug'>Suggested for you</div></div><div class='follow'>Follow</div><div class='dots'>···</div></div>" if next_handle else ""
    body = (RAIL + f"<div class='feed'>{prev}"
            f"<div class='ph'><div class='av'><i></i></div><div><div><span class='hn'>{esc(handle)}</span> <span class='age'>• {age}</span></div>"
            + (f"<div class='sug'>Suggested for you</div>" if suggested else "") + "</div>"
            + (f"<div class='follow'>Follow</div>" if suggested else "") + "<div class='dots'>···</div></div>"
            f"<div class='media' style='height:{media_h}px'>{media_html}</div>"
            f"<div class='acts'>♡ <span class='cnt'>{rng.randint(5, 400)}</span> ◯ <span class='cnt'>{rng.randint(0, 9)}</span> ➤ <span class='cnt'>{rng.randint(0, 12)}</span> ▷ <span class='bm'>⌂</span></div>"
            f"{likes_line}<div class='cap'><b>{esc(handle)}</b> {caption} <span class='more'>… more</span></div>{nxt}</div>"
            f"<div class='msg'>▽ Messages</div>")
    return page(IG_CSS, body)


def ig_story(rng: random.Random, handle: str, age: str, blocks: list[str], *, bg_css: str | None = None) -> str:
    """blocks: html snippets rendered as story text pills; the caller marks tgt inside one of them."""
    bg = bg_css or photo_bg(rng)
    inner = "".join(f"<div style='margin-top:{rng.randint(10, 40)}px;text-align:{rng.choice(['left', 'center'])}'>{b}</div>" for b in blocks)
    body = (f"<div class='story'><div class='sc' style='{bg}'><div class='sbar'>" + "".join(f"<i class='{'on' if i == 0 else ''}'></i>" for i in range(rng.randint(1, 6))) + "</div>"
            f"<div class='shd'><div class='av' style='width:30px;height:30px'><i></i></div>{esc(handle)} <span style='font-weight:400;opacity:.8'>{age}</span></div>"
            f"<div style='margin-top:{rng.randint(40, 120)}px'>{inner}</div>"
            f"<div class='reply'><span>Reply to {esc(handle)}…</span><span>♡ ➤</span></div></div></div>")
    return page(IG_CSS, body)


# ------------------------------------------------------------------ chats

CHAT_CSS = (
    ".imsg{background:#f5f5f7;height:100vh;display:flex}.side{width:240px;background:#e8e8ed;border-right:1px solid #d1d1d6;padding:14px 10px;font-size:13px}"
    ".side .c{padding:9px 8px;border-radius:8px;color:#333}.side .on{background:#0b93f6;color:#fff}.main{flex:1;display:flex;flex-direction:column;background:#fff}"
    ".hdr{padding:12px;text-align:center;font-weight:600;font-size:14px;border-bottom:1px solid #e0e0e0;background:#fafafa}"
    ".chat{padding:18px 14px;display:flex;flex-direction:column;gap:6px}.stamp{text-align:center;color:#8e8e93;font-size:11px;margin:6px 0}"
    ".b{max-width:70%;padding:9px 13px;border-radius:18px;font-size:15px;line-height:1.35}.in{background:#e9e9eb;color:#000;align-self:flex-start;border-bottom-left-radius:5px}"
    ".out{background:#0b93f6;color:#fff;align-self:flex-end;border-bottom-right-radius:5px}"
    ".gm{background:#f2f2f2;height:100vh}.ghdr{background:#00aff0;color:#fff;padding:14px;font-weight:600}.gbody{background:#fff;padding:14px}"
    ".m{display:flex;gap:10px;margin-bottom:14px}.gav{width:34px;height:34px;border-radius:50%;background:#00aff0;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex:none}"
    ".who{font-size:12px;color:#888;margin-bottom:2px}.txt{font-size:14px;line-height:1.4}"
    ".dc{display:flex;height:100vh;background:#313338;color:#dbdee1}.dside{width:220px;background:#2b2d31;color:#949ba4;padding:14px;font-size:14px}"
    ".dside .ch{padding:5px 8px;border-radius:4px}.dside .chon{background:#404249;color:#fff}.dmain{flex:1}.dhdr{padding:12px 16px;border-bottom:1px solid #26272b;color:#f2f3f5;font-weight:600}"
    ".dm{display:flex;gap:12px;padding:8px 16px;font-size:15px}.dav{width:38px;height:38px;border-radius:50%;background:#5865f2;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;flex:none}"
    ".dw{font-weight:600;color:#f2f3f5}.dt{color:#949ba4;font-size:12px;margin-left:6px}.dtxt{line-height:1.45;margin-top:2px}"
    ".sl{display:flex;height:100vh}.slside{width:240px;background:#3f0e40;color:#cfc3cf;padding:14px;font-size:14px}.slside .ch{padding:5px 8px;border-radius:4px}.slside .chon{background:#1164a3;color:#fff}"
    ".slmain{flex:1;background:#fff;color:#1d1c1d}.slhdr{padding:12px 16px;border-bottom:1px solid #ddd;font-weight:700}"
    ".slm{display:flex;gap:10px;padding:8px 16px;font-size:15px}.slav{width:36px;height:36px;border-radius:6px;background:#e01e5a;flex:none}"
    ".slw{font-weight:700}.slt{color:#616061;font-size:12px;margin-left:6px}.sltxt{line-height:1.45;margin-top:2px}"
)


def imessage(rng, convo: list[tuple[str, str]], contact: str, others: list[str]) -> str:
    bubbles = f"<div class='stamp'>Today {rng.randint(8, 11)}:{rng.randint(0, 59):02d} AM</div>" + "".join(
        f"<div class='b {who}'>{txt}</div>" for who, txt in convo)
    return page(CHAT_CSS, f"<div class='imsg'><div class='side'><div class='c on'>{esc(contact)}</div>"
                + "".join(f"<div class='c'>{esc(o)}</div>" for o in others)
                + f"</div><div class='main'><div class='hdr'>{esc(contact)}</div><div class='chat'>{bubbles}</div></div></div>")


def groupme(rng, msgs: list[tuple[str, str]], group: str) -> str:
    rows = "".join(f"<div class='m'><div class='gav'>{w[0]}</div><div><div class='who'>{esc(w)}</div><div class='txt'>{t}</div></div></div>" for w, t in msgs)
    return page(CHAT_CSS, f"<div class='gm'><div class='ghdr'>{esc(group)}</div><div class='gbody'>{rows}</div></div>")


def discord(rng, msgs: list[tuple[str, str]], channel: str, others: list[str]) -> str:
    rows = "".join(f"<div class='dm'><div class='dav'>{w[0]}</div><div><span class='dw'>{esc(w)}</span><span class='dt'>Today at {rng.randint(9, 11)}:{rng.randint(0, 59):02d} AM</span><div class='dtxt'>{t}</div></div></div>" for w, t in msgs)
    chans = f"<div class='ch chon'># {esc(channel)}</div>" + "".join(f"<div class='ch'># {esc(c)}</div>" for c in others)
    return page(CHAT_CSS, f"<div class='dc'><div class='dside'>{chans}</div><div class='dmain'><div class='dhdr'># {esc(channel)}</div>{rows}</div></div>")


def slack(rng, msgs: list[tuple[str, str]], channel: str, others: list[str], workspace: str) -> str:
    rows = "".join(f"<div class='slm'><div class='slav'></div><div><span class='slw'>{esc(w)}</span><span class='slt'>{rng.randint(9, 11)}:{rng.randint(0, 59):02d} AM</span><div class='sltxt'>{t}</div></div></div>" for w, t in msgs)
    chans = f"<div style='font-weight:700;color:#fff;margin-bottom:14px'>{esc(workspace)}</div><div class='ch chon'># {esc(channel)}</div>" + "".join(f"<div class='ch'># {esc(c)}</div>" for c in others)
    return page(CHAT_CSS, f"<div class='sl'><div class='slside'>{chans}</div><div class='slmain'><div class='slhdr'># {esc(channel)}</div>{rows}</div></div>")
