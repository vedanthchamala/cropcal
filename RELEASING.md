# Releasing CropCal

## 0. Hosted service (once, and on proxy changes)

```
pnpm exec wrangler login                 # once, interactive
./proxy/scripts/setup.sh                 # creates KV, sets GEMINI_API_KEY secret, deploys
./proxy/scripts/invite.sh alice 60       # one code per tester; prints cc_...
```
The Gemini key must belong to a project with billing enabled (paid tier: no
20/day cap, data not used for training). Put the deployed workers.dev URL in
`extension/lib/providers/hosted.js` (DEFAULT_PROXY_URL) before packaging.

Limits live in `proxy/wrangler.toml`: `DAILY_LIMIT` (default per code),
`GLOBAL_DAILY_LIMIT` (all codes), per-IP / per-code burst limits, and the
`DISABLED` kill switch. Redeploy after changing them
(`pnpm exec wrangler deploy --config proxy/wrangler.toml`). Revoke a code with
`pnpm exec wrangler kv key delete --binding TOKENS "token:<code>" --remote`
from `proxy/`.

## 1. Cut a tester build (GitHub release, "Load unpacked")

```
# bump "version" in extension/manifest.json and package.json (same value)
pnpm test
./scripts/package.sh                 # -> dist/cropcal-<version>.zip
git add -A && git commit -m "chore: release v<version>"
gh repo create cropcal --private --source . --push   # first time only
gh release create v<version> dist/cropcal-<version>.zip \
  --title "CropCal v<version>" --notes "Tester build. See README for install steps."
```

Share the release URL. Testers follow README → Install.

## 2. Chrome Web Store (unlisted)

1. https://chrome.google.com/webstore/devconsole → pay the one-time $5 fee.
2. New item → upload `dist/cropcal-<version>.zip`.
3. Fill the listing from `store/listing.md` (description, category, screenshots,
   privacy tab, permission justifications, privacy policy URL pointing at
   PRIVACY.md on GitHub).
4. Visibility: **Unlisted**. Submit for review (typically 1–3 business days).
5. After approval, share the store link; installs auto-update on future uploads.

Each Web Store upload must have a higher `version` than the last.

## 3. Before every release

- `./scripts/eval.sh --provider bridge --set eval_v0` (and synth sets) after any
  prompt change in `extension/lib/schema.js`; the accuracy suite must stay at 100%
  or the miss must be adjudicated in STATUS.md.
- Reload the unpacked extension and click through once: options → Save → Test
  connection; crop an Instagram flyer; crop a chat message with a relative date;
  crop a non-event and confirm the "No event found" toast.
