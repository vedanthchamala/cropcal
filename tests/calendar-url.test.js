import test from "node:test";
import assert from "node:assert/strict";
import { buildCalendarUrl, parseLocal, isPastEvent } from "../extension/lib/calendar-url.js";

const baseEvent = {
  title: "Career Fair",
  start: "2026-09-05T14:00:00",
  end: "2026-09-05T17:00:00",
  all_day: false,
  timezone: null,
  location: "Student Union Ballroom",
  description: "Bring resumes",
  recurrence: null,
  confidence: "high",
  notes: null
};

const paramsOf = (url) => new URL(url).searchParams;

test("timed event with explicit end", () => {
  const p = paramsOf(buildCalendarUrl(baseEvent, { timezone: "America/Chicago" }));
  assert.equal(p.get("action"), "TEMPLATE");
  assert.equal(p.get("text"), "Career Fair");
  assert.equal(p.get("dates"), "20260905T140000/20260905T170000");
  assert.equal(p.get("ctz"), "America/Chicago");
  assert.equal(p.get("location"), "Student Union Ballroom");
});

test("missing end defaults to one hour", () => {
  const p = paramsOf(buildCalendarUrl({ ...baseEvent, end: null }));
  assert.equal(p.get("dates"), "20260905T140000/20260905T150000");
});

test("deadline: end equal to start stays zero-duration, no one-hour default", () => {
  const p = paramsOf(buildCalendarUrl({ ...baseEvent, end: baseEvent.start }));
  assert.equal(p.get("dates"), "20260905T140000/20260905T140000");
});

test("end before start is treated as missing", () => {
  const p = paramsOf(buildCalendarUrl({ ...baseEvent, end: "2026-09-05T09:00:00" }));
  assert.equal(p.get("dates"), "20260905T140000/20260905T150000");
});

test("one-hour default rolls over midnight", () => {
  const p = paramsOf(
    buildCalendarUrl({ ...baseEvent, start: "2026-09-05T23:30:00", end: null })
  );
  assert.equal(p.get("dates"), "20260905T233000/20260906T003000");
});

test("single-day all-day event uses exclusive end date", () => {
  const p = paramsOf(
    buildCalendarUrl({ ...baseEvent, all_day: true, start: "2026-09-05T00:00:00", end: null })
  );
  assert.equal(p.get("dates"), "20260905/20260906");
  assert.equal(p.get("ctz"), null);
});

test("multi-day all-day event converts inclusive end to exclusive", () => {
  const p = paramsOf(
    buildCalendarUrl({
      ...baseEvent,
      all_day: true,
      start: "2026-09-05T00:00:00",
      end: "2026-09-07T00:00:00"
    })
  );
  assert.equal(p.get("dates"), "20260905/20260908");
});

test("all-day end-of-month rolls over correctly", () => {
  const p = paramsOf(
    buildCalendarUrl({ ...baseEvent, all_day: true, start: "2026-01-31T00:00:00", end: null })
  );
  assert.equal(p.get("dates"), "20260131/20260201");
});

test("event timezone overrides user timezone", () => {
  const p = paramsOf(
    buildCalendarUrl({ ...baseEvent, timezone: "America/New_York" }, { timezone: "America/Chicago" })
  );
  assert.equal(p.get("ctz"), "America/New_York");
});

test("recurrence passes through with RRULE prefix added if missing", () => {
  const withPrefix = paramsOf(
    buildCalendarUrl({ ...baseEvent, recurrence: "RRULE:FREQ=WEEKLY;BYDAY=TU" })
  );
  assert.equal(withPrefix.get("recur"), "RRULE:FREQ=WEEKLY;BYDAY=TU");

  const withoutPrefix = paramsOf(
    buildCalendarUrl({ ...baseEvent, recurrence: "FREQ=WEEKLY;BYDAY=TU" })
  );
  assert.equal(withoutPrefix.get("recur"), "RRULE:FREQ=WEEKLY;BYDAY=TU");
});

test("details include description and source attribution", () => {
  const p = paramsOf(
    buildCalendarUrl(baseEvent, {
      sourceTitle: "GroupMe",
      sourceUrl: "https://web.groupme.com/chats"
    })
  );
  const details = p.get("details");
  assert.match(details, /Bring resumes/);
  assert.match(details, /Captured with CropCal from:/);
  assert.match(details, /https:\/\/web\.groupme\.com\/chats/);
});

test("overlong details are truncated", () => {
  const p = paramsOf(
    buildCalendarUrl({ ...baseEvent, description: "x".repeat(3000) })
  );
  assert.ok(p.get("details").length <= 1501);
});

test("unparseable start throws", () => {
  assert.throws(() => buildCalendarUrl({ ...baseEvent, start: "next Friday" }), /Unparseable/);
});

test("isPastEvent flags finished events, not upcoming or ongoing ones", () => {
  const now = new Date(2026, 8, 1, 12, 0, 0); // Sep 1 2026, noon

  assert.equal(isPastEvent(baseEvent, now), false); // Sep 5 is still upcoming
  assert.equal(
    isPastEvent({ ...baseEvent, start: "2026-08-23T14:00:00", end: "2026-08-23T17:00:00" }, now),
    true
  );
  assert.equal(
    isPastEvent({ ...baseEvent, start: "2026-09-01T11:30:00", end: "2026-09-01T13:00:00" }, now),
    false // ongoing right now
  );
  assert.equal(
    isPastEvent({ ...baseEvent, all_day: true, start: "2026-09-01T00:00:00", end: null }, now),
    false // today's all-day event isn't past
  );
  assert.equal(
    isPastEvent({ ...baseEvent, all_day: true, start: "2026-08-23T00:00:00", end: null }, now),
    true
  );
  assert.equal(isPastEvent({ ...baseEvent, start: "garbage" }, now), false);
});

test("parseLocal handles date-only and rejects garbage", () => {
  assert.equal(parseLocal("2026-09-05").getHours(), 0);
  assert.equal(parseLocal("2026-13-45T99:99"), null);
  assert.equal(parseLocal("garbage"), null);
});
