#!/usr/bin/env bash
# Builds a distributable zip of an extension folder:
#   ./scripts/package.sh                   -> dist/cropcal-<version>.zip        (extension/, Anthropic)
#   ./scripts/package.sh extension-gemini  -> dist/cropcal-gemini-<version>.zip (extension-gemini/)
# Upload it to the Chrome Web Store dashboard, or attach it to a GitHub release
# for "Load unpacked" installs. Excludes OS junk; validates the manifest first.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC="${1:-extension}"
NAME="cropcal"
[ "$SRC" = "extension" ] || NAME="cropcal-${SRC#extension-}"
VERSION=$(node -p "JSON.parse(require('fs').readFileSync('$SRC/manifest.json','utf8')).version")
node -e "
const m = JSON.parse(require('fs').readFileSync('$SRC/manifest.json','utf8'));
const fs = require('fs');
for (const p of [...Object.values(m.icons), m.background.service_worker, m.options_page]) {
  if (!fs.existsSync('$SRC/' + p)) { console.error('missing file referenced by manifest: ' + p); process.exit(1); }
}
"
node --test "tests/*.test.js" >/dev/null

mkdir -p dist
OUT="dist/${NAME}-${VERSION}.zip"
rm -f "$OUT"
(cd "$SRC" && zip -qr "../$OUT" . -x '.DS_Store' '*/.DS_Store' '__MACOSX/*')
echo "built $OUT ($(du -h "$OUT" | cut -f1))"
unzip -Z1 "$OUT" | sed "s/^/  /"
