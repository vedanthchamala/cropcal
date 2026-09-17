import test from "node:test";
import assert from "node:assert/strict";
import { parseEventsText } from "../extension/lib/parse.js";

const events = [{ title: "Demo", start: "2026-09-05T14:00:00" }];
const payload = JSON.stringify({ events });

test("parses bare JSON", () => {
  assert.deepEqual(parseEventsText(payload), events);
});

test("parses fenced JSON", () => {
  assert.deepEqual(parseEventsText("```json\n" + payload + "\n```"), events);
});

test("parses JSON wrapped in prose", () => {
  assert.deepEqual(
    parseEventsText(`Here is the extracted event:\n${payload}\nLet me know!`),
    events
  );
});

test("empty events array is valid", () => {
  assert.deepEqual(parseEventsText('{"events": []}'), []);
});

test("throws on garbage", () => {
  assert.throws(() => parseEventsText("I could not find any JSON"), /unparseable/);
});

test("throws when events key is missing", () => {
  assert.throws(() => parseEventsText('{"items": []}'), /unparseable/);
});
