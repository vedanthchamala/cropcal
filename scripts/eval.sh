#!/usr/bin/env bash
# Run the eval harness. Examples:
#   ./scripts/eval.sh                       # score cached outputs (sanity check)
#   ./scripts/eval.sh --provider bridge     # live regression run (bridge must be up)
set -euo pipefail
cd "$(dirname "$0")/../ml"
exec uv run python -m evals.run "$@"
