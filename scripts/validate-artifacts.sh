#!/bin/sh
# validate-artifacts.sh — checks that test evidence manifest.json is present and complete
set -e
trap 'echo "KILROY_VALIDATE_FAILURE: validate-artifacts.sh crashed at line $LINENO"' EXIT

RUN_ID="${KILROY_RUN_ID:-unknown}"
# If KILROY_RUN_ID is not in env, detect it from existing .ai/runs/ directories
if [ "$RUN_ID" = "unknown" ] && [ -d ".ai/runs" ]; then
  for _d in .ai/runs/*/; do
    _name=$(basename "$_d")
    if [ "$_name" != "unknown" ] && [ -d "$_d" ]; then
      RUN_ID="$_name"
      break
    fi
  done
fi

MANIFEST=".ai/runs/${RUN_ID}/test-evidence/latest/manifest.json"
echo "Checking manifest at: $MANIFEST"

if ! test -f "$MANIFEST"; then
  echo "KILROY_VALIDATE_FAILURE: manifest.json missing — postmortem must ensure test evidence is written"
  exit 1
fi

echo "Manifest exists"
python3 -c "
import json, sys
m = json.load(open(sys.argv[1]))
ids = set(s['id'] for s in m['scenarios'])
required = {'IT-1', 'IT-2', 'IT-3', 'IT-4', 'IT-5', 'IT-6', 'IT-7'}
missing = required - ids
assert not missing, f'Missing scenarios: {missing}'
print('All scenario IDs present:', sorted(ids))
" "$MANIFEST" || { echo "KILROY_VALIDATE_FAILURE: manifest.json incomplete — postmortem must ensure test evidence is written"; exit 1; }

trap - EXIT
echo "Artifact check passed"
