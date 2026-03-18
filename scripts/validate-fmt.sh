#!/bin/sh
set -e
trap 'echo "KILROY_VALIDATE_FAILURE: validate-fmt.sh crashed at line $LINENO"' EXIT

echo "=== [validate-fmt] Ensuring venv is up to date ==="
uv sync --dev

echo "=== [validate-fmt] Running ruff check ==="
uv run ruff check src/

echo "=== [validate-fmt] Running ruff format --check ==="
uv run ruff format --check src/

trap - EXIT
echo "Format checks passed"
