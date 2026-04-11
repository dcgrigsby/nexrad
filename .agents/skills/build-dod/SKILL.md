---
name: build-dod
description: Use when converting a spec, requirements document, or goal statement into a Definition of Done with acceptance criteria and integration test scenarios
---

# Build DoD

A DoD converts a spec into pass/fail gates. Its power is in **integration tests** — scenarios that prove the deliverable works by exercising it the way a user would.

## Core Principle

Tests aren't there to be passed. They're there to prove results. Verify the deliverable through integration scenarios that exercise it end-to-end, not through unit tests that verify internals.

## Process

1. Read the full spec
2. List deliverables — the artifacts that exist when done
3. If a digraph/flow diagram is provided, extract intended user journeys, decision points, and outcomes from it
4. Write acceptance criteria — one observable assertion per row
5. Inventory every user-facing message surface from the spec
6. Write integration test scenarios that prove the deliverable works end-to-end
7. Map each AC and each message to the scenario(s) that prove it
8. Crosscheck — confirm every AC and every message is covered and every scenario is sound

When this skill is used inside an Attractor run, scratch outputs should be written under `.ai/runs/$KILROY_RUN_ID/...`. Root `.ai` is not implicitly ingested.

## If a digraph is provided

Use the graph in two passes:

1. **Intent pass (primary):** Treat the graph as a map of product intent and user flow. Use it to identify the major journeys, decisions, and failure/recovery paths that matter to users.
2. **Flow sanity pass (secondary):** Do lightweight topology checks only to catch intent-breaking issues (for example, a required outcome has no reachable path).

## Acceptance Criteria

Each AC is a single, testable assertion using observable language: "exists", "returns", "displays", "produces", "exits 0".

Group by concern (e.g. Build, Output, Behavior, Integration). Number hierarchically: AC-1.1, AC-1.2, AC-2.1.

ACs describe *what* must be true. They are *proven* by integration test scenarios, not by individual unit tests.

## Integration Test Scenarios

Integration tests are the primary verification mechanism. Each scenario exercises the delivered artifact directly, proving multiple acceptance criteria simultaneously.

When a digraph exists, write scenarios around **high-level intent coverage**, not exhaustive graph traversal. Prefer:
- Primary happy paths
- High-risk branches and decision outcomes
- Critical error/recovery paths
- Mode transitions that change user experience (for example first run vs returning user)

**Test the delivered artifact in its delivery form.** At least one scenario must exercise the full delivery path:
- Browser app → serve it in a browser, confirm it loads and runs
- CLI tool → invoke the binary, check exit code and output
- Library → import it and call its public API
- Data file → consume it with its intended reader

If the deliverable is a browser app and no scenario loads it in a browser, the DoD is incomplete.

**Validate every user-facing message.** Help text, error messages, status displays, feedback strings, prompts, and warnings are promises to the user. Inventory all of them from the spec, then ensure each one is triggered and validated in at least one scenario:
- Trigger the condition that should display it
- Confirm the message appears
- Confirm what the message says is true (if help says "press ? for help", pressing ? must show help)

This means *all* messages, not a sample. If the spec describes 20 distinct message surfaces, 20 must be tested.

**When one artifact references another, verify both.** A source file that references an output is evidence of intent; confirm the output itself is present and valid.

For each primary way the deliverable is used, write a scenario with:
- **Starting state** — deterministic inputs (fixed seed, known data, clean environment)
- **Actions** — a sequence of operations a real user or consumer would perform
- **Expected outcomes** — observable results after each action

Scenarios should cross multiple AC groups. A browser app scenario might cover loading, display, input, and state persistence in one flow.

Each scenario is **self-contained** — it sets up its own preconditions within the test rather than depending on externally pre-computed inputs or manual preparation.

Each scenario becomes a named automated test in the DoD, with `test exits 0` as its verification.

**For checks that require judgment**, write a concrete semantic verification with:
- The question to answer
- The expected answer
- The evidence to examine (file paths, commands, artifacts)

## Test Evidence Contract (Required)

Every DoD must define deterministic, reviewable test artifacts for each integration scenario.

- Canonical root: `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/`
- Per-scenario folder: `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/IT-<id>/`
- Manifest file: `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/manifest.json`

Manifest entries must map each scenario ID to:
- scenario status (`pass`/`fail`)
- artifact list (type + path)
- missing/unreadable artifact notes (if any)

Example manifest shape:
```json
{
  "version": 1,
  "scenarios": [
    {
      "id": "IT-1",
      "status": "pass",
      "artifacts": [
        { "type": "log", "path": ".ai/runs/$KILROY_RUN_ID/test-evidence/latest/IT-1/test.log" }
      ],
      "notes": []
    }
  ]
}
```

Artifact requirements:
- Every `IT-*` scenario must produce at least one artifact.
- Each scenario must declare one surface type in evidence metadata:
  - `surface=ui`: visually rendered user interface is exercised.
  - `surface=non_ui`: no visually rendered user interface is exercised.
  - `surface=mixed`: both visual UI and non-UI interfaces are exercised.
- Scenarios that exercise a visual UI (`surface=ui` or `surface=mixed`) must include screenshot artifacts (`.png` or `.jpg`) proving key states.
- Scenarios that do not exercise visual UI (`surface=non_ui`) must include text or structured evidence artifacts (for example logs, stdout captures, JSON reports).
- On test failure, emit best-effort artifacts and a manifest entry anyway; missing artifacts must be explicit in the manifest and treated as findings.

Framework policy:
- Do not require a specific browser/test framework in the DoD. Require outcomes and evidence, not tool brand.

### Scenario sanity checks

Before finalizing each scenario, confirm:
- **Automatable** — the test can set up its own state, run, and assert without human intervention or external artifacts
- **Bounded** — the scenario has a finite, predictable number of steps (a test that must "play until winning" is unbounded; a test that exercises 5 specific levels via setup commands is bounded)
- **Proportional** — effort to implement the test is proportional to the confidence it provides (testing 3 representative cases from a category provides nearly as much confidence as testing all 50)
- **Independent** — the scenario produces the same result regardless of execution order or environment state
- **Intent-complete** — collectively, scenarios prove the intended user journeys and outcomes described by the spec (and digraph, if present)
- **Evidence-complete** — scenario defines deterministic artifact paths and required artifact types under `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/IT-<id>/`

## The Crosscheck

After writing all ACs and integration scenarios, review:

**Per scenario:**
1. Confirm the scenario exercises the delivered artifact, not just internal components
2. Confirm the scenario is automatable, bounded, proportional, and independent
3. Confirm the scenario crosses multiple AC groups
4. Confirm the scenario declares required evidence artifacts and deterministic paths

**Per AC:**
5. Confirm at least one scenario proves this AC
6. If no scenario covers an AC, add coverage or justify the gap

**Overall:**
7. Confirm at least one scenario tests the deliverable in its delivery form
8. Confirm every user-facing message from the inventory is triggered and validated by at least one scenario
9. Confirm the scenarios collectively cover every AC group
10. Confirm `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/manifest.json` covers every scenario ID with at least one artifact path
11. If a digraph exists, confirm no required intent path is missing or unreachable

## Output Format

~~~markdown
# [Project] — Definition of Done

## Scope

### In Scope
[What the deliverable covers]

### Out of Scope
[Explicit exclusions]

### Assumptions
[Prerequisites and environment]

## Deliverables

| Artifact | Location | Description |
|----------|----------|-------------|
| ... | ... | ... |

## Acceptance Criteria

### [Concern Area]

| ID | Criterion | Covered by |
|----|-----------|------------|
| AC-N.M | [Observable assertion] | IT-X, IT-Y |

## User-Facing Message Inventory

| ID | Message surface | Trigger condition | Covered by |
|----|----------------|-------------------|------------|
| MSG-N | [What the user sees] | [What causes it] | IT-X |

## Test Evidence Contract

| Item | Requirement |
|------|-------------|
| Evidence root | `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/` |
| Scenario folder pattern | `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/IT-<id>/` |
| Manifest | `.ai/runs/$KILROY_RUN_ID/test-evidence/latest/manifest.json` |
| UI scenarios (`surface=ui` or `surface=mixed`) | Include screenshot evidence proving key states |
| Non-UI scenarios (`surface=non_ui`) | Include text/structured evidence (log/stdout/json) |
| Failure behavior | Emit best-effort artifacts and manifest entry; record missing artifacts explicitly |

## Integration Test Scenarios

| ID | Scenario | Steps | Verification | Evidence Artifacts |
|----|----------|-------|--------------|--------------------|
| IT-N | [User journey name] | 1. [action] → [expected] 2. [action] → [expected] ... | `test command` exits 0 | `surface=<ui|non_ui|mixed>`; `[type:path, ...]` |
~~~
