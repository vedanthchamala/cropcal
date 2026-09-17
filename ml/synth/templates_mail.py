"""Gmail reading pane (many body layouts), Canvas dashboard, and event-site
hero — modeled on real captures. The date cluster carries id="tgt"."""
from __future__ import annotations

import random

from synth.templates_social import esc, page, photo_bg, fake_qr

GMAIL_CSS = (
    "body{background:#f6f8fc;color:#202124;overflow:hidden}"
    ".top{display:flex;align-items:center;gap:26px;padding:10px 18px;height:64px}.logo{font-size:22px;color:#444;display:flex;align-items:center;gap:10px}"
    ".logo b{color:#ea4335;font-size:26px}.search{flex:0 0 720px;background:#e9eef6;border-radius:24px;padding:12px 18px;color:#5f6368;font-size:16px}"
    ".nav{position:fixed;left:0;top:64px;bottom:0;width:256px;padding:8px 12px;font-size:14px}"
    ".compose{background:#c2e7ff;border-radius:16px;padding:16px 22px;font-weight:600;display:inline-block;margin:6px 0 14px}"
    ".ni{display:flex;justify-content:space-between;padding:7px 14px;border-radius:16px;color:#202124}.ni.on{background:#d3e3fd;font-weight:700}"
    ".pane{margin:0 16px 0 262px;background:#fff;border-radius:16px;height:calc(100vh - 80px);overflow:hidden;position:relative}"
    ".tb{display:flex;gap:22px;padding:14px 20px;color:#444;font-size:16px;border-bottom:1px solid #eee}.tb .pg{margin-left:auto;font-size:12px;color:#5f6368}"
    ".subj{font-size:22px;padding:18px 70px 6px;display:flex;align-items:center;gap:10px}.chip{font-size:12px;background:#eee;border-radius:4px;padding:2px 6px;color:#444}"
    ".from{display:flex;align-items:center;gap:12px;padding:10px 70px 16px}.fav{width:40px;height:40px;border-radius:50%;background:#7b7b7b;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700}"
    ".from b{font-size:14px}.from .em{color:#5f6368;font-size:13px}.from .when{margin-left:auto;font-size:12px;color:#5f6368}"
    ".body{padding:0 70px 20px;font-size:14px;line-height:1.55}.body p{margin:0 0 12px}.body a{color:#1a0dab;text-decoration:underline}"
    ".mk{max-width:640px;margin:0 auto;background:#fff}.mkbar{padding:18px 26px;color:#fff;font-weight:700;font-size:22px}"
    ".mkbody{padding:26px 34px;font-size:15px;line-height:1.55}.btn{display:inline-block;padding:12px 26px;color:#fff;font-weight:600;border-radius:4px;margin:14px 0}"
    ".foot{position:absolute;bottom:0;left:0;right:0;padding:16px 70px;display:flex;gap:10px;background:#fff}.foot span{border:1px solid #ccc;border-radius:22px;padding:9px 18px;font-size:14px}"
    ".lst{display:flex;gap:26px;margin:24px 0}.lst .im{width:200px;height:150px;border-radius:4px;flex:none}.lst .nm{font-size:28px;font-weight:700;color:#d0021b}"
    ".lst .dt{font-size:20px;font-weight:700}.lst .ds{font-size:15px;color:#333;margin:6px 0 12px}"
    ".lw{display:flex;gap:16px;align-items:center;padding:10px 0}.badge{width:56px;height:56px;border:1px solid #ddd;border-radius:10px;text-align:center;font-size:11px;color:#777;overflow:hidden}"
    ".badge b{display:block;font-size:22px;color:#222;line-height:1.1}.lw .d1{font-size:18px;font-weight:600}.lw .d2{color:#666;font-size:15px}"
    ".ib{width:56px;height:56px;border:1px solid #ddd;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:24px}"
    ".dk{display:flex}.dk .col{width:calc(50% - 320px);background:#0b2545;min-height:calc(100vh - 80px)}"
)

INBOX_COUNTS = [("Inbox", "13,256"), ("Starred", ""), ("Snoozed", ""), ("Important", ""), ("Sent", ""), ("Drafts", "70"),
                ("Purchases", "121"), ("Social", "1,561"), ("Updates", "14,761"), ("Forums", "6"), ("Promotions", "20,336")]


def gmail(rng: random.Random, subject: str, sender: str, sender_email: str, when: str, body_html: str, *,
          search: str = "", dark_columns: bool = False, unsubscribe: bool = False) -> str:
    nav = "<div class='nav'><div class='compose'>✎ Compose</div>" + "".join(
        f"<div class='ni {'on' if n == 'Inbox' else ''}'><span>{n}</span><span>{c}</span></div>" for n, c in INBOX_COUNTS) + "</div>"
    body = (f"<div class='top'><div class='logo'>≡ <b>M</b> Gmail</div><div class='search'>{esc(search) if search else '⌕ Ask Gmail'}</div></div>{nav}"
            f"<div class='pane'><div class='tb'>← ▢ ⓘ 🗑 ✉ ▤ ⋮ <span class='pg'>{rng.randint(1, 80)} of {rng.choice(['15,179', 'many', '13,256'])} ‹ ›</span></div>"
            f"<div class='subj'>{esc(subject)} <span class='chip'>Inbox ×</span></div>"
            f"<div class='from'><div class='fav'>{esc(sender)[0].upper()}</div><div><b>{esc(sender)}</b> <span class='em'>&lt;{esc(sender_email)}&gt;</span>"
            + (" <span style='color:#1a73e8;font-size:13px;margin-left:8px'>Unsubscribe</span>" if unsubscribe else "")
            + f"<div class='em'>to me ▾</div></div><div class='when'>{esc(when)} ☆ ☺ ↩ ⋮</div></div>"
            + (f"<div class='dk'><div class='col'></div><div style='flex:1'>{body_html}</div><div class='col'></div></div>" if dark_columns else f"<div class='body'>{body_html}</div>")
            + "<div class='foot'><span>↩ Reply</span><span>↪ Forward</span><span>☺</span></div></div>")
    return page(GMAIL_CSS, body)


# --- body builders. Each returns html with <span id='tgt'> around the date cluster.

def body_marketing_centered(rng, org: str, greeting: str, intro: str, lines: list[str], venue_lines: list[str], cta: str, color: str) -> str:
    return (f"<div class='mk'><div class='mkbar' style='background:{color}'>{esc(org)}</div><div class='mkbody'>"
            f"<p>{greeting}</p><p>{intro}</p>"
            f"<p style='text-align:center;font-style:italic;font-weight:700;font-size:16px'><span id='tgt'>{'<br>'.join(lines)}</span></p>"
            + (f"<p style='text-align:center;font-style:italic'>{'<br>'.join(esc(v) for v in venue_lines)}</p>" if venue_lines else "")
            + f"<p style='text-align:center'><a style='font-weight:700;font-style:italic'>{esc(cta)}</a></p>"
            f"<p>{rng.choice(['If you are unable to attend, we encourage you to explore our other events this fall.', 'We look forward to seeing you!', 'Questions? Just reply to this email.'])}</p>"
            f"<p>{esc(rng.choice(['Angela Betz', 'Jonathan Zavaleta', 'Priya Natarajan', 'Marcus Lee']))}<br>Assistant Director<br>{esc(org)}</p></div></div>")


def body_plain_bullets(rng, greeting: str, paras: list[str], bullets: list[str], target_index: int, closing: str, signoff: str) -> str:
    items = "".join(f"<li{' id=\"tgt\"' if i == target_index else ''}><b>{b}</b> - <a>Register here</a></li>" for i, b in enumerate(bullets))
    return (f"<p>{greeting}</p>" + "".join(f"<p>{p}</p>" for p in paras)
            + f"<ul style='margin:0 0 14px 24px;line-height:1.9'>{items}</ul><p>{closing}</p><p>{signoff}</p>"
            f"<p style='font-size:12px;color:#666'>This message is confidential and subject to terms at: <a>https://www.example.com/emaildisclaimer</a> including on confidential, privileged or legal entity information.</p>")


def body_luma(rng, host: str, title: str, mon: str, day: int, date_line: str, time_line: str, where: str, blurb: str) -> str:
    return (f"<div style='max-width:760px;margin:0 auto;font-size:15px'><p style='color:#555'>👤 {esc(host)}</p>"
            f"<p style='color:#888;font-size:22px;margin-bottom:2px'>You're invited to</p><p style='font-size:24px;font-weight:700;border-bottom:1px solid #ddd;padding-bottom:12px'>{esc(title)}</p>"
            f"<div class='lw' id='tgt'><div class='badge'>{mon}<b>{day}</b></div><div><div class='d1'>{date_line}</div><div class='d2'>{time_line}</div></div></div>"
            f"<div class='lw' style='border-bottom:1px solid #ddd;padding-bottom:16px'><div class='ib'>{'▭' if where in ('Zoom', 'Google Meet', 'Microsoft Teams') else '📍'}</div><div class='d1'>{esc(where)}</div></div>"
            f"<p style='margin-top:16px;font-size:17px;line-height:1.6'>{blurb}</p><p>If you can't make it live, sign up anyway and we'll send you the recording after.</p>"
            f"<p><span class='btn' style='background:#555'>Accept Invite</span> <span class='btn' style='background:#eee;color:#333'>View Event</span></p></div>")


def body_when_where(rng, brand: str, name: str, when_txt: str, where_txt: str, organizer: str, color: str) -> str:
    return (f"<div class='mk'><div class='mkbar' style='background:{color};height:120px'>{esc(brand)}<div style='font-size:14px;font-weight:400'>Let's create experiences that matter</div></div>"
            f"<div class='mkbody'><p style='font-weight:700;font-size:18px'>We look forward to seeing you!</p><p><b>Hi {esc(name)},</b></p>"
            f"<p>Thanks for confirming your attendance! We look forward to having you at our upcoming event.</p>"
            f"<p><b>Event Details</b></p><p id='tgt'><b>When:</b> {when_txt}</p><p><b>Where:</b> {where_txt}</p><p><b>Organizer:</b> {esc(organizer)}</p>"
            f"<p>Best regards,<br>{esc(brand)} Talent Acquisition</p></div></div>")


def body_listing(rng, heading: str, rows: list[dict], target_index: int) -> str:
    items = "".join(f"<div class='lst'><div class='im' style='{photo_bg(rng)}'></div><div><div class='nm'>{esc(r['name'])}</div>"
                    f"<div class='dt'{' id=\"tgt\"' if i == target_index else ''}>{r['date_txt']}</div><div class='ds'>{esc(r['desc'])}</div>"
                    f"<span class='btn' style='background:#d0021b'>GET TICKETS</span></div></div>" for i, r in enumerate(rows))
    return f"<div class='mk'><div style='text-align:center;color:#d0021b;font-size:34px;font-weight:900;padding:20px'>{esc(heading).upper()}</div><div style='text-align:center;font-size:40px;font-weight:900;color:#222'>JUST FOR YOU</div>{items}</div>"


def body_headline_cta(rng, org: str, headline_html: str, cta: str, color: str) -> str:
    return (f"<div class='mk'><p style='text-align:center;font-size:12px;letter-spacing:1px;padding:14px'>{esc(org).upper()}</p>"
            f"<div style='height:260px;{photo_bg(rng)}'></div><div class='mkbody'><p style='font-size:30px;font-weight:800;color:#0b2545;line-height:1.2' id='tgt'>{headline_html}</p>"
            f"<p style='text-align:center'><span class='btn' style='background:{color}'>{esc(cta)}</span></p></div></div>")


def body_visit_days(rng, greeting: str, intro: str, groups: list[dict], cta: str, color: str) -> str:
    blocks = "".join(f"<p style='text-align:center;font-size:17px;line-height:1.55'><span{' id=\"tgt\"' if g.get('target') else ''}><b>{esc(g['name'])}</b><br>{'<br>'.join(g['date_lines'])}<br><i>{g['time_line']}</i></span></p>" for g in groups)
    return (f"<div class='mk'><div class='mkbody'><p>{greeting}</p><p>{intro}</p>{blocks}"
            f"<p style='text-align:center'><span class='btn' style='background:{color}'>{esc(cta)} ›</span></p>"
            f"<p>Choosing the right school is a big decision, and we're here to help.</p></div></div>")


def body_moved(rng, poster: str, group: str, title: str, new_date_sentence: str, venue_line: str, dt_line: str) -> str:
    return (f"<div style='max-width:820px;margin:0 auto;font-size:16px'><p style='color:#555'><b>{esc(poster)}</b> (Organizer) posted a new announcement in <b>{esc(group)}</b></p>"
            f"<p style='color:#555;border-bottom:1px solid #ddd;padding-bottom:14px'>Quick update: {new_date_sentence}</p><p>Hi there!</p>"
            f"<p>A quick update: <b>{esc(title)} {new_date_sentence}</b></p><p>Same time, same place.</p>"
            f"<p>📍 <b>{esc(venue_line)}</b></p><p id='tgt'>⏰ <b>{dt_line}</b></p>"
            f"<p>If you've already RSVP'd, please update your calendar invite to the new date.</p><p>Hope to see you there!</p><p>Cheers,<br>{esc(poster)}</p></div>")


def body_sessions(rng, blocks: list[dict], target_index: int, footer: str) -> str:
    html = "".join(f"<p style='font-weight:700;font-size:16px'{' id=\"tgt\"' if i == target_index else ''}>{b['time_txt']}</p><ul style='margin:0 0 20px 40px'>"
                   + "".join(f"<li>{esc(x)}</li>" for x in b['items']) + "</ul>" for i, b in enumerate(blocks))
    return f"<div class='mk'><div class='mkbody'>{html}<p style='text-align:center;font-weight:700;font-size:20px'>{footer}</p></div></div>"


def body_invite_or(rng, greeting: str, intro: str, date_lines: list[str], venue_lines: list[str], cta: str, duration_line: str, signoff: str) -> str:
    return (f"<p>{greeting}</p><p>{intro}</p><p>Appointments are limited and filling quickly—so if you haven't booked your time yet, now's the moment to do it.</p>"
            f"<p><span id='tgt'><b>{'</b> <i>or</i><br><b>'.join(date_lines)}</b></span><br>{'<br>'.join(esc(v) for v in venue_lines)}</p>"
            f"<p><a>{esc(cta)}</a></p><p>{duration_line}</p><p>All my best,</p><p>{esc(signoff)}</p>")


def body_digest(rng, heading: str, items: list[dict], target_index: int) -> str:
    html = "".join(f"<p><b>{esc(it['name'])}</b><br><span{' id=\"tgt\"' if i == target_index else ''}>{it['line']}</span>{(' ' + esc(it['extra'])) if it.get('extra') else ''}</p>" for i, it in enumerate(items))
    return f"<p style='font-size:20px;font-weight:700'>{esc(heading)}</p>{html}<p style='color:#666;font-size:12px'>You are receiving this because you subscribed to campus updates.</p>"


def body_paragraph(rng, paras: list[str]) -> str:
    return "".join(f"<p>{p}</p>" for p in paras)


# ------------------------------------------------------------------ Canvas

CANVAS_CSS = (
    "body{background:#fff;color:#2d3b45;overflow:hidden}"
    ".cn{position:fixed;left:0;top:0;bottom:0;width:90px;background:#bf5700;color:#fff;display:flex;flex-direction:column;align-items:center;gap:22px;padding-top:16px;font-size:12px;text-align:center}"
    ".cn div{display:flex;flex-direction:column;align-items:center;gap:4px}.cn i{font-style:normal;font-size:22px}"
    ".cm{margin-left:90px;padding:20px 48px}"
    ".ann{border:2px solid #0374b5;border-radius:4px;display:flex;margin-bottom:16px}.ann .ic{width:56px;background:#0374b5;color:#fff;display:flex;align-items:center;justify-content:center;font-size:20px}"
    ".ann .ab{padding:14px 18px;flex:1;font-size:15px;line-height:1.5}.ann .at{font-size:17px;font-weight:700;margin-bottom:8px}.ann .as{font-size:12px;color:#555;margin-top:8px}"
    ".ann .x{padding:14px;color:#555}"
    "h1{font-size:34px;font-weight:700;margin:18px 0 26px;display:flex;align-items:center}h1 span{margin-left:auto;font-size:14px;border:1px solid #ccc;border-radius:4px;padding:6px 12px;font-weight:400}"
    ".day{font-weight:700;font-size:16px;margin:26px 0 12px}.todo{display:flex;align-items:center;gap:20px;border-top:1px solid #e5e5e5;border-bottom:1px solid #e5e5e5;padding:12px 0}"
    ".cb{width:200px;height:90px;background:#6a8f74;color:#fff;display:flex;align-items:center;justify-content:center;font-size:11px;text-align:center;font-weight:700;border:1px solid #ccc}"
    ".cb b{background:#fff;color:#2d3b45;padding:4px 8px}.chk{width:18px;height:18px;border:2px solid #666;border-radius:3px}"
    ".tt{flex:1}.tt .k{font-size:11px;letter-spacing:.5px;color:#555}.tt .n{color:#0374b5;font-size:16px;margin:4px 0}.tt .r{font-size:14px}.tm{font-size:13px;color:#555;white-space:nowrap}"
)


def canvas(rng: random.Random, announcements: list[dict], days: list[dict], school: str) -> str:
    nav = "<div class='cn'><div><i>🏛</i>canvas</div><div><i>◯</i>Account</div><div><i>◔</i>Dashboard</div><div><i>▤</i>Courses</div><div><i>▦</i>Calendar</div><div><i>✉</i>Inbox</div><div><i>◷</i>History</div><div><i>ⓘ</i>Resources</div></div>"
    anns = "".join(f"<div class='ann'><div class='ic'>▦</div><div class='ab'><div class='at'{' id=\"tgt\"' if a.get('target') else ''}>{a['title']}</div>{a['body']}"
                   f"<div class='as'>This is an announcement from <b>{esc(school)}</b></div></div><div class='x'>×</div></div>" for a in announcements)
    dayrows = "".join(f"<div class='day'>{d['label']}</div>" + "".join(
        f"<div class='todo'><div class='cb'>{esc(it['course']).upper()}<br><b>{esc(it['course'][:6])}</b></div><div class='chk'></div><div class='tt'><div class='k'>{esc(it['course']).upper()} {esc(it['kind']).upper()}</div>"
        f"<div class='n'{' id=\"tgt\"' if it.get('target') else ''}>{it['name']}</div>" + (f"<div class='r'>{esc(it['room'])}</div>" if it.get('room') else "")
        + f"</div><div class='tm'{' id=\"tgt\"' if it.get('target_time') else ''}>{it['time']}</div></div>" for it in d['items']) for d in days)
    return page(CANVAS_CSS, nav + f"<div class='cm'>{anns}<h1>Dashboard <span>Today</span></h1>{dayrows}</div>")


# ------------------------------------------------------------------ event site hero

HERO_CSS = ("body{overflow:hidden;height:100vh}.hero{height:100vh;position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}"
            ".badge{position:absolute;top:0;right:40px;background:#111;color:#fff;font-weight:900;padding:14px 12px;font-size:13px;line-height:1.2;text-align:center}"
            ".ht{font-weight:900;line-height:.95}.hd{font-size:26px;margin-top:22px;letter-spacing:1px}.hb{margin-top:40px;background:#fff;padding:12px 32px;font-size:26px;transform:rotate(-3deg);box-shadow:3px 4px 0 rgba(0,0,0,.25)}")


def hero(rng: random.Random, title: str, date_line: str, cta: str, font: str, colors: tuple[str, str], badge: str = "") -> str:
    bg, fg = colors
    return page(HERO_CSS, f"<div class='hero' style='background:{bg};color:{fg};font-family:{font}'>"
                + (f"<div class='badge'>{badge}</div>" if badge else "")
                + f"<div class='ht' style='font-size:{rng.randint(90, 130)}px'>{esc(title)}</div><div class='hd' id='tgt'>{date_line}</div>"
                f"<div class='hb' style='color:{bg}'>{esc(cta)}</div></div>")
