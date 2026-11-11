#!/usr/bin/env bash
# Creates an invite code: ./proxy/scripts/invite.sh <name> [crops_per_day] [staging]
# Revoke with: pnpm exec wrangler kv key delete --binding TOKENS "token:<code>" --remote
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?name required}"; LIMIT="${2:-60}"; TARGET="${3:-production}"
[[ "$NAME" =~ ^[A-Za-z0-9._-]{1,40}$ ]] || { echo "name: letters, digits, . _ - only"; exit 1; }
[[ "$LIMIT" =~ ^[0-9]+$ ]] || { echo "crops_per_day must be a number"; exit 1; }
ENV_FLAG=""; [ "$TARGET" = "staging" ] && ENV_FLAG="--env staging"
TOKEN="cc_$(openssl rand -base64 24 | tr '+/' '-_' | tr -d '=' | cut -c1-22)"
pnpm exec wrangler kv key put --binding TOKENS --remote $ENV_FLAG "token:$TOKEN" \
  "{\"name\":\"$NAME\",\"limit\":$LIMIT,\"created\":\"$(date -u +%Y-%m-%d)\"}" > /dev/null
echo "$TOKEN"
