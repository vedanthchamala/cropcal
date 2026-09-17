#!/usr/bin/env bash
# One-time deploy of the hosted proxy. Needs a Cloudflare account:
#   pnpm exec wrangler login          # interactive, once
#   ./proxy/scripts/setup.sh          # creates KV, sets the Gemini key secret, deploys
# Reads GEMINI_API_KEY from ml/.env unless it is already exported.
set -euo pipefail
cd "$(dirname "$0")/.."
W="pnpm exec wrangler"

if grep -q 'id = "REPLACE_ME"' wrangler.toml; then
  ID=$($W kv namespace create TOKENS 2>&1 | grep -oE 'id = "[a-f0-9]+"' | head -1 | grep -oE '[a-f0-9]{32}')
  [ -n "$ID" ] || { echo "could not create KV namespace"; exit 1; }
  sed -i '' "s/id = \"REPLACE_ME\"/id = \"$ID\"/" wrangler.toml
  echo "KV namespace TOKENS = $ID"
fi

KEY="${GEMINI_API_KEY:-$(sed -n 's/^GEMINI_API_KEY=//p' ../ml/.env 2>/dev/null || true)}"
[ -n "$KEY" ] || { echo "GEMINI_API_KEY not found (export it or put it in ml/.env)"; exit 1; }
printf '%s' "$KEY" | $W secret put GEMINI_API_KEY

$W deploy
echo
echo "Deployed. Put the workers.dev URL printed above into extension/lib/providers/hosted.js (DEFAULT_PROXY_URL),"
echo "then create invite codes with ./proxy/scripts/invite.sh <name> [crops_per_day]."
