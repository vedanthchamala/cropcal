// Robust parsing for providers that can't enforce structured output (the
// Claude Code bridge). Accepts bare JSON, fenced JSON, or JSON embedded in prose.
export function parseEventsText(text) {
  const candidates = [];
  const trimmed = text.trim();
  candidates.push(trimmed);

  const fence = /```(?:json)?\s*([\s\S]*?)\s*```/.exec(trimmed);
  if (fence) candidates.push(fence[1]);

  const first = trimmed.indexOf("{");
  const last = trimmed.lastIndexOf("}");
  if (first !== -1 && last > first) candidates.push(trimmed.slice(first, last + 1));

  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate);
      if (parsed && Array.isArray(parsed.events)) return parsed.events;
    } catch {
      // try the next candidate
    }
  }
  throw new Error("Model returned unparseable output");
}
