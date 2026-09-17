#!/usr/bin/env bash
# Creates an invite code: ./proxy/scripts/invite.sh <name> [crops_per_day]
# Revoke with: pnpm exec wrangler kv key delete --binding TOKENS "token:<code>" --remote
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?name required}"; LIMIT="${2:-60}"
TOKEN="cc_$(openssl rand -base64 24 | tr '+/' '-_' | tr -d '=' | cut -c1-22)"
pnpm exec wrangler kv key put --binding TOKENS --remote "token:$TOKEN" \
  "{\"name\":\"$NAME\",\"limit\":$LIMIT,\"created\":\"$(date -u +%Y-%m-%d)\"}" > /dev/null
echo "$TOKEN"
