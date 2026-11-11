import test from "node:test";
import assert from "node:assert/strict";
import { diffEvents, fromForm, toForm } from "../extension/lib/review.js";

const timed = {
  title: "Design review", start: "2026-11-20T14:00:00", end: "2026-11-20T15:30:00", all_day: false,
  timezone: null, location: "GDC 2.216", description: "Bring laptops", recurrence: null,
  confidence: "high", notes: null
};
const deadline = { ...timed, title: "Apps due", start: "2026-11-20T17:00:00", end: "2026-11-20T17:00:00", location: null };
const openEnded = { ...timed, end: null };
const allDay = { ...timed, title: "Fall break", start: "2026-11-25T00:00:00", end: "2026-11-27T00:00:00", all_day: true, location: null };
const allDayOne = { ...allDay, start: "2026-11-25T00:00:00", end: "2026-11-25T00:00:00" };
const weekly = { ...timed, recurrence: "RRULE:FREQ=WEEKLY;BYDAY=MO" };

test("an untouched form returns the model's event exactly, for every shape", () => {
  for (const e of [timed, deadline, openEnded, allDay, allDayOne, weekly, { ...timed, start: "2026-11-20T14:00:59" }]) {
    const out = fromForm(toForm(e), e);
    assert.deepEqual(out.event, e);
    assert.deepEqual(diffEvents(e, out.event), []);
  }
});

test("form fields mirror the event", () => {
  assert.deepEqual(toForm(timed), {
    title: "Design review", allDay: false, date: "2026-11-20", startTime: "14:00",
    endDate: "2026-11-20", endTime: "15:30", location: "GDC 2.216", repeat: false
  });
  assert.deepEqual(toForm(openEnded).endTime, "");
  assert.deepEqual(toForm(allDay), {
    title: "Fall break", allDay: true, date: "2026-11-25", startTime: "", endDate: "2026-11-27",
    endTime: "", location: "", repeat: false
  });
  assert.equal(toForm(weekly).repeat, true);
});

test("edits to title, time, location and repeat land in the event; the rest is kept", () => {
  const f = { ...toForm(weekly), title: "  Design sync ", startTime: "15:00", endTime: "16:00", location: "", repeat: false };
  const { event } = fromForm(f, weekly);
  assert.equal(event.title, "Design sync");
  assert.equal(event.start, "2026-11-20T15:00:00");
  assert.equal(event.end, "2026-11-20T16:00:00");
  assert.equal(event.location, null);
  assert.equal(event.recurrence, null);
  assert.equal(event.description, "Bring laptops");
  assert.equal(event.confidence, "high");
  assert.deepEqual(diffEvents(weekly, event), ["title", "start", "end", "location", "recurrence"]);
});

test("clearing the end time leaves the end open; a deadline keeps end == start when only moved", () => {
  assert.equal(fromForm({ ...toForm(timed), endTime: "" }, timed).event.end, null);
  const moved = fromForm({ ...toForm(deadline), startTime: "18:00", endTime: "18:00" }, deadline).event;
  assert.equal(moved.start, "2026-11-20T18:00:00");
  assert.equal(moved.end, moved.start);
});

test("an overnight end on the next day is kept; an end before the start is refused", () => {
  const late = fromForm({ ...toForm(timed), startTime: "21:00", endDate: "2026-11-21", endTime: "01:00" }, timed).event;
  assert.equal(late.end, "2026-11-21T01:00:00");
  assert.match(fromForm({ ...toForm(timed), endTime: "13:00" }, timed).error, /before the start/);
});

test("switching to all-day and back", () => {
  const day = fromForm({ ...toForm(timed), allDay: true, startTime: "", endTime: "" }, timed).event;
  assert.deepEqual([day.all_day, day.start, day.end], [true, "2026-11-20T00:00:00", null]);
  assert.deepEqual(diffEvents(timed, day), ["start", "end", "all_day"]);

  const span = fromForm({ ...toForm(allDay), endDate: "2026-11-28" }, allDay).event;
  assert.equal(span.end, "2026-11-28T00:00:00");
  assert.match(fromForm({ ...toForm(allDay), endDate: "2026-11-24" }, allDay).error, /before the start/);

  const back = fromForm({ ...toForm(allDay), allDay: false, startTime: "09:00", endDate: "", endTime: "" }, allDay).event;
  assert.deepEqual([back.all_day, back.start, back.end], [false, "2026-11-25T09:00:00", null]);
  assert.match(fromForm({ ...toForm(allDay), allDay: false }, allDay).error, /start time/);
});

test("invalid input is reported, never thrown", () => {
  assert.match(fromForm({ ...toForm(timed), title: "   " }, timed).error, /title/);
  assert.match(fromForm({ ...toForm(timed), date: "" }, timed).error, /valid date/);
  assert.match(fromForm({ ...toForm(timed), date: "2026-02-30" }, timed).error, /valid date/);
  const broken = { ...timed, start: "2026-11-20T14:00:00-06:00" };
  assert.match(fromForm(toForm(broken), broken).error, /could not be read/);
  assert.equal(fromForm({ ...toForm(broken), startTime: "14:30" }, broken).event.start, "2026-11-20T14:30:00");
});
