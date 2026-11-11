#!/usr/bin/env bash
# One-time deploy of the hosted proxy. Needs a Cloudflare account:
#   pnpm exec wrangler login          # interactive, once
#   ./proxy/scripts/setup.sh          # production: creates KV, sets the Gemini key secret, deploys
#   ./proxy/scripts/setup.sh staging  # the same for the staging environment
# Reads GEMINI_API_KEY from ml/.env unless it is already exported. For staging,
# export the eval project's key so staging traffic never draws on production's quota.
set -euo pipefail
cd "$(dirname "$0")/.."
W="pnpm exec wrangler"
TARGET="${1:-production}"
case "$TARGET" in
  production) ENV_FLAG="" ;;
  staging) ENV_FLAG="--env staging" ;;
  *) echo "usage: setup.sh [staging]"; exit 1 ;;
esac

# Production's id is already filled in, so the only placeholder left is staging's.
if [ "$TARGET" = "staging" ] && grep -q 'id = "REPLACE_ME"' wrangler.toml; then
  ID=$($W kv namespace create TOKENS $ENV_FLAG 2>&1 | grep -oE 'id = "[a-f0-9]+"' | head -1 | grep -oE '[a-f0-9]{32}')
  [ -n "$ID" ] || { echo "could not create KV namespace"; exit 1; }
  sed -i '' "s/id = \"REPLACE_ME\"/id = \"$ID\"/" wrangler.toml
  echo "KV namespace TOKENS ($TARGET) = $ID"
fi

KEY="${GEMINI_API_KEY:-$(sed -n 's/^GEMINI_API_KEY=//p' ../ml/.env 2>/dev/null || true)}"
[ -n "$KEY" ] || { echo "GEMINI_API_KEY not found (export it or put it in ml/.env)"; exit 1; }
printf '%s' "$KEY" | $W secret put GEMINI_API_KEY $ENV_FLAG

$W deploy $ENV_FLAG
echo
echo "Deployed ($TARGET). Create invite codes with ./proxy/scripts/invite.sh <name> [crops_per_day] [staging]."
