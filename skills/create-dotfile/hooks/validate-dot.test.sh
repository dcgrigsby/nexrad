#!/usr/bin/env bash
# validate-dot.test.sh — integration tests for validate-dot.sh
#
# Usage: bash skills/create-dotfile/hooks/validate-dot.test.sh [kilroy-binary]
#
# Requires the kilroy binary. Pass the binary path as the first argument, or set
# KILROY_CLAUDE_PATH, or ensure kilroy is in PATH.
#
# Exit 0: all tests pass
# Exit 1: one or more tests failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$SCRIPT_DIR/validate-dot.sh"

# Locate kilroy binary.
KILROY_BIN="${1:-${KILROY_CLAUDE_PATH:-kilroy}}"

if ! command -v "$KILROY_BIN" &>/dev/null && [[ ! -x "$KILROY_BIN" ]]; then
    echo "SKIP: kilroy binary not found (looked for '$KILROY_BIN'). Pass path as first arg or set KILROY_CLAUDE_PATH." >&2
    exit 0
fi

export KILROY_CLAUDE_PATH="$KILROY_BIN"

PASS=0
FAIL=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

run_test() {
    local name="$1"
    local input_json="$2"
    local expect_empty="$3"   # "yes" = expect no feedback, "no" = expect feedback (exit 2 + stderr)

    local stderr_output exit_code
    stderr_output=$(printf '%s' "$input_json" | bash "$HOOK" 2>&1 >/dev/null; true)
    exit_code=$(printf '%s' "$input_json" | bash "$HOOK" 2>/dev/null; echo $?)

    if [[ "$expect_empty" == "yes" ]]; then
        # Expect: exit 0 and no stderr output
        if [[ -z "$stderr_output" && "$exit_code" == "0" ]]; then
            echo "PASS: $name"
            PASS=$((PASS + 1))
        else
            echo "FAIL: $name — expected no feedback (exit 0, no stderr), got exit=$exit_code:"
            printf '  %s\n' "$stderr_output"
            FAIL=$((FAIL + 1))
        fi
    else
        # Expect: exit 2 and non-empty stderr output
        if [[ -n "$stderr_output" && "$exit_code" == "2" ]]; then
            echo "PASS: $name"
            PASS=$((PASS + 1))
        else
            echo "FAIL: $name — expected exit 2 + stderr feedback, got exit=$exit_code, stderr='$stderr_output'"
            FAIL=$((FAIL + 1))
        fi
    fi
}

make_input_json() {
    local tool_name="$1"
    local file_path="$2"
    python3 -c "import json,sys; print(json.dumps({'tool_name': sys.argv[1], 'tool_input': {'file_path': sys.argv[2]}}))" \
        "$tool_name" "$file_path"
}

# ---------------------------------------------------------------------------
# Set up temp directory for test dot files.
# ---------------------------------------------------------------------------

TMPDIR_TEST=$(mktemp -d)
trap 'rm -rf "$TMPDIR_TEST"' EXIT

# ---------------------------------------------------------------------------
# Test 1: Non-.dot file — hook must be a no-op (no output, exit 0).
# ---------------------------------------------------------------------------

NONDOT="$TMPDIR_TEST/somefile.txt"
printf 'hello\n' > "$NONDOT"

run_test "non-dot file is a no-op" \
    "$(make_input_json Write "$NONDOT")" \
    "yes"

# ---------------------------------------------------------------------------
# Test 2: Non-file tool (e.g., Bash) — hook must be a no-op.
# ---------------------------------------------------------------------------

DOTFILE="$TMPDIR_TEST/noop.dot"
printf 'digraph{}' > "$DOTFILE"

run_test "non-Write/Edit tool is a no-op" \
    "$(make_input_json Bash "$DOTFILE")" \
    "yes"

# ---------------------------------------------------------------------------
# Test 3: Clean .dot file — hook exits 0 with no output.
# Construct a minimal valid graph with all required attributes.
# ---------------------------------------------------------------------------

CLEAN_DOT="$TMPDIR_TEST/clean.dot"
cat > "$CLEAN_DOT" <<'DOT'
digraph clean {
    graph [model_stylesheet="* { llm_provider: anthropic; llm_model: claude-sonnet-4-6; }"];
    start [shape=Mdiamond];
    work [shape=box,
          prompt="Do the work. Write {\"status\":\"success\"} to $KILROY_STAGE_STATUS_PATH."];
    done [shape=Msquare];
    start -> work;
    work -> done;
}
DOT

run_test "clean dot file produces no output" \
    "$(make_input_json Write "$CLEAN_DOT")" \
    "yes"

# ---------------------------------------------------------------------------
# Test 4: Broken .dot file (missing start node) — hook outputs error feedback.
# ---------------------------------------------------------------------------

BROKEN_DOT="$TMPDIR_TEST/broken.dot"
cat > "$BROKEN_DOT" <<'DOT'
digraph broken {
    graph [provenance_version="test"];
    node_a [shape=box, llm_provider=anthropic, llm_model=claude-sonnet-4-6,
            prompt="do something. Write {\"status\":\"success\"} to $KILROY_STAGE_STATUS_PATH."];
    node_a -> exit;
    exit [shape=Msquare];
}
DOT
# Note: no start node (Mdiamond/circle) — triggers start_node ERROR

run_test "broken dot file produces error feedback" \
    "$(make_input_json Write "$BROKEN_DOT")" \
    "no"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Results: $PASS passed, $FAIL failed"

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
