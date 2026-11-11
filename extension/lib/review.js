// Pure logic behind the in-page review card: EventJSON <-> the card's form
// fields, validation, and what the user changed. The card itself (content
// script) only moves strings around; everything here is unit-tested.
import { parseLocal } from "./calendar-url.js";

export const EDITABLE_FIELDS = ["title", "start", "end", "all_day", "location", "recurrence"];

export function toForm(event) {
  const start = event.start || "";
  const end = event.end || "";
  const allDay = Boolean(event.all_day);
  return {
    title: event.title || "",
    allDay,
    date: start.slice(0, 10),
    startTime: allDay ? "" : start.slice(11, 16),
    endDate: end.slice(0, 10),
    endTime: allDay ? "" : end.slice(11, 16),
    location: event.location || "",
    repeat: Boolean(event.recurrence)
  };
}

const WHEN_KEYS = ["allDay", "date", "startTime", "endDate", "endTime"];

// Builds the final event from the edited form. Anything the user left alone is
// taken from the model's event untouched, so an accepted event is byte-for-byte
// the prediction (it matters when these become training labels).
// Returns { event } or { error } with a message for the card.
export function fromForm(form, original) {
  const before = toForm(original);
  const event = { ...original };

  const title = String(form.title || "").trim();
  if (!title) return { error: "Add a title" };
  if (title !== before.title) event.title = title;

  if (WHEN_KEYS.some((k) => form[k] !== before[k])) {
    if (!form.date || !parseLocal(form.date)) return { error: "Pick a valid date" };
    if (form.allDay) {
      const endDate = form.endDate || "";
      if (endDate && !parseLocal(endDate)) return { error: "Pick a valid end date" };
      if (endDate && endDate < form.date) return { error: "The end date is before the start" };
      event.all_day = true;
      event.start = `${form.date}T00:00:00`;
      event.end = endDate && endDate !== form.date ? `${endDate}T00:00:00` : null;
    } else {
      if (!form.startTime) return { error: "Pick a start time, or mark it all-day" };
      const start = `${form.date}T${form.startTime}:00`;
      if (!parseLocal(start)) return { error: "Pick a valid start time" };
      let end = null;
      if (form.endTime) {
        end = `${form.endDate || form.date}T${form.endTime}:00`;
        if (!parseLocal(end)) return { error: "Pick a valid end time" };
        if (end < start) return { error: "The end is before the start" };
      }
      event.all_day = false;
      event.start = start;
      event.end = end;
    }
  }

  const location = String(form.location || "").trim();
  if (location !== before.location) event.location = location || null;
  if (!form.repeat) event.recurrence = null;

  if (!parseLocal(event.start)) return { error: "This event's date could not be read — pick a date" };
  return { event };
}

const same = (a, b) => (a ?? null) === (b ?? null);

// Names of the editable fields whose value differs between the model's event
// and the one the user accepted.
export function diffEvents(predicted, final) {
  return EDITABLE_FIELDS.filter((f) =>
    f === "all_day" ? Boolean(predicted[f]) !== Boolean(final[f]) : !same(predicted[f], final[f])
  );
}
