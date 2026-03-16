#!/bin/sh
set -e
trap 'echo "KILROY_VALIDATE_FAILURE: validate-build.sh crashed at line $LINENO"' EXIT

echo "=== [validate-build] Running uv sync ==="
uv sync

echo "=== [validate-build] Checking nexrad-fetch --help ==="
uv run nexrad-fetch --help

echo "=== [validate-build] Checking nexrad-transform --help ==="
uv run nexrad-transform --help

echo "=== [validate-build] Building viewer ==="
cd viewer && npm install && npx vite build && cd ..

trap - EXIT
echo "All build checks passed"
