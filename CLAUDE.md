# CropCal project instructions

- Read SPEC.md (product decisions, schema, phases) and STATUS.md (current state) first.
- The event JSON schema in SPEC.md is the contract shared by the extension, the
  dataset, and the eval harness. Changing it means versioning it and updating all three.
- `extension/` is plain ES modules, no build step, Manifest V3. Keep it that way for
  Phase 0 — no bundler unless a dependency truly forces it.
- Pure logic (URL building, date handling, schema) lives in `extension/lib/` and gets
  unit tests in `tests/` (`pnpm test` → `node --test`). Browser-API code
  (capture, overlay, storage) stays thin and untested for now.
- Never log or persist screenshot contents beyond the API call; privacy is a core
  product promise. Dataset collection, when it comes, is explicit opt-in.
- ML work (Phases 1–3) will live in `ml/` with uv; it does not import from
  `extension/` — the schema is the only shared contract.
