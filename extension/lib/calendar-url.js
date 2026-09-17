const LOCAL_DT = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2}))?)?$/;

export function parseLocal(s) {
  const m = LOCAL_DT.exec(s);
  if (!m) return null;
  const [, y, mo, d, h = "0", mi = "0", se = "0"] = m;
  const date = new Date(+y, +mo - 1, +d, +h, +mi, +se);
  // Date rolls over out-of-range components (month 13 → next year); reject those.
  const roundTrips =
    date.getFullYear() === +y &&
    date.getMonth() === +mo - 1 &&
    date.getDate() === +d &&
    date.getHours() === +h &&
    date.getMinutes() === +mi;
  return roundTrips ? date : null;
}

const pad = (n) => String(n).padStart(2, "0");

function fmtDate(d) {
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
}

function fmtDateTime(d) {
  return `${fmtDate(d)}T${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

const addHours = (d, h) => new Date(d.getTime() + h * 3600_000);

function addDays(d, days) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + days);
}

// Builds a Google Calendar event-template URL. Opening it shows Google's own
// prefilled "create event" page — the user reviews, edits, and saves there.
export function buildCalendarUrl(event, opts = {}) {
  const start = parseLocal(event.start);
  if (!start) throw new Error(`Unparseable start time: ${event.start}`);
  let end = event.end ? parseLocal(event.end) : null;
  if (end && end.getTime() < start.getTime()) end = null;

  let dates;
  if (event.all_day) {
    // Google expects an exclusive end date; the schema's end is inclusive.
    const endExclusive = addDays(end ?? start, 1);
    dates = `${fmtDate(start)}/${fmtDate(endExclusive)}`;
  } else {
    dates = `${fmtDateTime(start)}/${fmtDateTime(end ?? addHours(start, 1))}`;
  }

  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: event.title || "Event",
    dates
  });

  const tz = event.timezone || opts.timezone;
  if (tz && !event.all_day) params.set("ctz", tz);
  if (event.location) params.set("location", event.location);

  const details = buildDetails(event, opts);
  if (details) params.set("details", details);

  if (event.recurrence) {
    const rrule = event.recurrence.startsWith("RRULE:")
      ? event.recurrence
      : `RRULE:${event.recurrence}`;
    params.set("recur", rrule);
  }

  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

// True when the event is already over at `now` — used to warn the user that a
// year guess may have landed in the past (or that they cropped an old date).
export function isPastEvent(event, now = new Date()) {
  const start = parseLocal(event.start);
  if (!start) return false;
  if (event.all_day) {
    const lastDay = event.end ? parseLocal(event.end) ?? start : start;
    return addDays(lastDay, 1) <= now;
  }
  const end = event.end ? parseLocal(event.end) : null;
  return (end ?? addHours(start, 1)) <= now;
}

function buildDetails(event, opts) {
  const parts = [];
  if (event.description) parts.push(event.description);
  if (opts.sourceTitle || opts.sourceUrl) {
    const source = ["Captured with CropCal from:", opts.sourceTitle, opts.sourceUrl]
      .filter(Boolean)
      .join("\n");
    parts.push(source);
  }
  const details = parts.join("\n\n");
  return details.length > 1500 ? `${details.slice(0, 1500)}…` : details;
}
