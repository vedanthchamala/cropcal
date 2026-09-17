#!/usr/bin/env bash
# Starts the CropCal local bridge (extension -> Claude Code, no API key needed).
# Env: BRIDGE_PORT (default 48765), BRIDGE_MODEL (default opus), BRIDGE_LOG=1 to save captures.
set -euo pipefail
cd "$(dirname "$0")/.."
exec node bridge/server.mjs "$@"
