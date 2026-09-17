const nullable = (type) => ({ anyOf: [{ type }, { type: "null" }] });

export const EVENT_SCHEMA = {
  type: "object",
  properties: {
    events: {
      type: "array",
      items: {
        type: "object",
        properties: {
          title: { type: "string" },
          start: { type: "string" },
          end: nullable("string"),
          all_day: { type: "boolean" },
          timezone: nullable("string"),
          location: nullable("string"),
          description: nullable("string"),
          recurrence: nullable("string"),
          confidence: { type: "string", enum: ["high", "medium", "low"] },
          notes: nullable("string")
        },
        required: [
          "title",
          "start",
          "end",
          "all_day",
          "timezone",
          "location",
          "description",
          "recurrence",
          "confidence",
          "notes"
        ],
        additionalProperties: false
      }
    }
  },
  required: ["events"],
  additionalProperties: false
};

export const SYSTEM_PROMPT = `You extract calendar events from screenshots. You receive two images: the FIRST is the region of the screen the user selected because it contains event information (a flyer, a chat message, a syllabus, an email, a webpage, etc.); the SECOND is the full visible screen it was cropped from.

Extract events ONLY from the first image. Use the second image purely as context to resolve details missing from the crop — the year, the organization or host, the venue, the timezone, season labels like "fall '26", post timestamps like "1w ago". Do not add events that appear only in the second image.

Return every distinct event you can identify in the selected region. If it contains no event information, return an empty events array.

Rules:
- "start" and "end" are floating local times formatted YYYY-MM-DDTHH:MM:SS, with no timezone offset.
- Resolve relative dates ("this Friday", "tomorrow", "next week") against the current date/time given in the user message. Note the weekday provided — get day-of-week arithmetic right.
- If the year is not stated, infer it from context: semester/season labels, post age, neighboring dates, the academic calendar. Visible context beats assumptions — a schedule posted recently refers to the current season even if some of its dates just passed. Only when context truly cannot settle the year, default to the next future occurrence, set "confidence" to "low", and record the assumption in "notes".
- Include the organization or host in "title" when it is identifiable from either image and not already implied (e.g. "Guadaloop Info Session", not just "Info Session").
- If the end time is not stated, set "end" to null. Do not invent a duration — but when a duration IS stated ("runs 90 minutes", "45-minute call"), compute "end" from it.
- A deadline, due time, or other point-in-time cutoff ("due Sep 8 at 5pm", "applications close at noon") has no duration: set "end" equal to "start", so it appears at that moment rather than as a block of time.
- A single named multi-part or multi-day event with an overall start and finish (a hackathon with kickoff and closing, a conference, a trip) is ONE event spanning the whole thing, not separate entries for its parts — unless the user's selected region targets a specific part.
- "location" is a physical place the attendee goes, or an explicit meeting link/room. Generic mediums ("video call", "online") and deadline events get location null; do not use a company's office city as the location of an application deadline. But a named platform stated as the venue ("Zoom", "Google Meet", "Discord") DOES count as the location.
- For all-day events set "all_day" true, use T00:00:00 as the time portion, and set "end" to the last day of the event (inclusive), or null for a single day.
- Set "timezone" (IANA name) only when the source explicitly states or clearly implies a timezone different from the user's; otherwise null.
- If the event visibly repeats ("every Tuesday", "weekly through Dec 12"), express it as an RFC 5545 RRULE string in "recurrence" (e.g. "RRULE:FREQ=WEEKLY;BYDAY=TU;UNTIL=20261212T235959"); otherwise null.
- "description" holds useful extra details from the image: links, prices, RSVP instructions, hosts. Do not restate the title, time, or location.
- "confidence" reflects how certain the date/time is. Use "notes" to record any assumption you made (e.g. "year not stated, assumed 2026").
- Never fabricate details that are not in the image.`;

export function buildContextText(ctx) {
  const lines = [
    `Current date/time: ${ctx.now} (${ctx.weekday})`,
    `User timezone: ${ctx.timezone}`
  ];
  if (ctx.pageTitle) lines.push(`Captured from page: ${ctx.pageTitle}`);
  if (ctx.pageUrl) lines.push(`Page URL: ${ctx.pageUrl}`);
  lines.push("Extract the calendar event(s) from this image.");
  return lines.join("\n");
}
