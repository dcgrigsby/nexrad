# AGENTS

## Project Overview

This repository is a **stage-based, multi-language project** orchestrated primarily via **Kilroy** and the **Attractor** pattern.

Authoritative references:

- Kilroy implementation: `https://github.com/danshapiro/kilroy`
- Attractor NL spec: `https://github.com/strongdm/attractor`

**Intent:** This repo uses Attractor **as a software factory**. Pipelines are not just “business workflows” — they are **engineering pipelines that design, build, and evolve a set of applications which together make a product**.

## How Agents Should Think About This Repo

- **Attractor-first, product-factory mindset**
  - Think of Attractor graphs as **product-building assembly lines**, not only as repeatable operational workflows.
  - Prefer designing and evolving **Attractor pipelines that create and refine applications** (services, CLIs, UIs, infra pieces, etc.) instead of only one-off edits.
  - When a task is multi-step or recurring, consider how it would map into:
    - Requirements ingestion,
    - Design/spec stages,
    - Implementation stages (possibly in different languages),
    - Testing/verification,
    - Packaging/deployment steps.

- **Multi-language, stage-based design**
  - The project is expected to include **multiple languages** across stages (e.g., Go, Python, TypeScript/JavaScript, or others).
  - **Do not force a single-language solution** across the project.
  - If a stage has a **strong existing library** in a particular language, prefer using that language/library for that stage instead of re-implementing it elsewhere.
  - It is **not a goal** to port every useful library into a single “canonical” language.

- **When choosing languages per stage**
  - Prefer:
    - Libraries with well-maintained ecosystems and good documentation.
    - Languages that fit the runtime/deployment environment expected for that stage.
  - Accept:
    - Mixing languages across different nodes in the pipeline.
  - Avoid:
    - Large-scale, speculative rewrites solely to unify languages.
    - Introducing exotic stacks without clear benefit.

## How To Use Skills In This Repo

This repo includes local skills (for example under `skills/`) that should be treated as **meta-workflow helpers around Attractor/Kilroy**, not as direct graph primitives:

- **Before/around pipelines (design & ops)**
  - Use `skills/starting-a-project` to structure a new target repo for Attractor.
  - Use `skills/build-dod` to turn specs/requirements into a clear Definition of Done and acceptance criteria for each product slice.
  - Use `skills/create-dotfile` to convert English requirements into a DOT graph (`*.dot`) describing the product-building pipeline.
  - Use `skills/create-runfile` to author `run.yaml` (or similar) for Kilroy.
  - Use `skills/using-kilroy` to run, validate, and resume pipelines.
  - Use `skills/investigating-kilroy-runs` to inspect CXDB artifacts, debug stuck/failed runs, and understand run history.

- **Inside Attractor nodes (execution phase)**
  - Attractor nodes are executed by the **coding-agent loop implemented by Kilroy**, not by the Cursor or Claude Code UIs.
  - Node prompts may explicitly instruct: “Follow the instructions in `skills/<name>/SKILL.md`” so the coding agent reads and obeys those skill files during node execution.
  - Human or human-gate nodes can be used when product decisions, UX reviews, or riskier changes require explicit human approval.

In short: **use skills to design and operate pipelines outside the graph**, and **reference those skills from within node prompts** so the internal coding-agent loop can follow them.

## Operating Model

Work in this repo flows through three phases. **The product is always built by Kilroy.** Never use superpowers execution skills to implement product features directly.

### Phase 1 — Requirements (Claude Code, superpowers)

Understand what to build and make product decisions.

- Use `brainstorming` (superpowers) to explore product intent with the human → produces spec / requirements doc

### Phase 2 — Factory Design (Claude Code, Kilroy design skills)

Translate requirements into a runnable pipeline. This is the Kilroy-intended design mechanism — not Claude Code execution.

- `skills/build-dod` → spec → acceptance criteria + integration test scenarios
- `skills/create-dotfile` → requirements + DoD → pipeline DOT graph
- `skills/create-runfile` → DOT graph → `run.yaml` config
- `skills/starting-a-project` → initialize target repo if needed

### Phase 3 — Factory Execution (Kilroy runner)

Run the pipeline. Failures feed back to Phase 2.

- `skills/using-kilroy` → validate + run pipeline
- `skills/investigating-kilroy-runs` → diagnose failures; repair DOT/runfile and re-run

### Superpowers Skill Boundaries

Claude Code ships with superpowers skills (brainstorming, writing-plans, executing-plans, etc.). Several of them can implement code directly — which is Kilroy's job. The rule:

| Skill | Use in this repo | Never use for |
|---|---|---|
| `brainstorming` | Phase 1 — product intent and decisions | — |
| `writing-plans` | Phases 1–2 — planning DOT/runfile/skill changes | Planning product features for direct Claude Code execution |
| `executing-plans` | Phases 1–2 — factory meta-work only (repo setup, repairing DOT) | Product implementation |
| `subagent-driven-development` | Phases 1–2 — factory meta-work only | Product implementation |
| `dispatching-parallel-agents` | Phases 1–2 — parallel factory ops (e.g., fix multiple broken nodes) | Product feature work |
| `test-driven-development` | Phases 1–2 — factory/infra code only | Product code (Kilroy's DoD handles this) |
| `systematic-debugging` | Any phase — debugging pipeline setup | — |
| `verification-before-completion` | Phase 2→3 — verifying pipeline setup before a run | — |
| `using-git-worktrees` | Any phase — isolating factory changes | — |

## Session Handoff and Run Monitoring

Long-running Kilroy pipelines span multiple Claude Code sessions. Use this pattern to hand off cleanly and stay informed without manual polling.

### Handoff prompt (end of session)

When wrapping up a session where a run was launched or is in progress, produce a self-contained handoff block that the next session can execute immediately:

```
**Handoff: <one-line intent>**
**What to do:**
  <exact shell command to resume or launch>
**Existing implementation (already merged):**
  <key files and what they do>
**How the graph works:**
  <routing logic — especially any detect/skip shortcuts>
**Key config details:**
  <env loading, model choices, any known gotchas>
**Reference docs:**
  <paths to spec, DoD, design docs>
```

The next session should be able to copy-paste the command and run it cold.

### Scheduled run monitoring

Instead of manually asking for status every few minutes, create a scheduled task (via the `anthropic-skills:schedule` skill) immediately after launching a detached run:

- **Frequency:** 5 minutes is the recommended default; use 10 minutes for low-risk runs.
- **Prompt must include:** run ID, logs root, repo path, expected graph stage sequence, and what to watch for (failures, key routing decisions, stalls).
- **Auto-disable:** the task prompt should instruct the agent to note when the run reaches a final state (`success` or terminal failure) so the task can be disabled.
- **Failure action:** if the task detects a failure or stall, it should surface the `failure_reason` from `status.json` and suggest whether to resume or investigate.

This pattern replaces the need to re-open a session and ask "status" — the monitoring task reports proactively.

**Where to read the output:** Monitoring task output appears in the **Scheduled** section of the Claude Code sidebar, not in the active chat session. The current conversation will not receive task output automatically. Check the sidebar to see status reports; each run appears as a separate entry, newest at the top.

### Monitoring task template

```
You are monitoring a Kilroy Attractor run.

Run ID: <id>
Logs root: <path>
Repo: <path>

Steps:
1. kilroy attractor status --logs-root <path>
2. tail -20 <path>/progress.ndjson  (extract node, completions, errors)
3. ls <path>/  (new stage directories = completed stages)
4. If state=failed: cat <path>/final.json

Report: state, current node, new completions, any failures with failure_reason.
If final state reached: note run is complete and disable task <task-id>.
```

## Agent Behavior and Safety

- **Bias for clarity over cleverness**
  - Explain trade-offs (especially language/library choices and pipeline structure) briefly when making non-obvious decisions.
  - Use comments/docstrings sparingly and only where intent is non-obvious.

- **Respect existing configuration & skills**
  - Treat any `AGENTS.md`, `.cursor/rules/**`, `skills/**`, `.agents/skills/**`, and `CLAUDE.md` (if present) as **authoritative guidance**.
  - When there is a conflict, **this `AGENTS.md` and `.cursor/rules/**` win** over older or generic instructions.

- **Testing and verification**
  - For non-trivial changes, recommend or add tests appropriate to the language and stage.
  - When describing Attractor nodes, be explicit about:
    - Inputs/outputs,
    - Expected artifacts,
    - How success/failure is detected (e.g., status files, test exit codes).

## How to Use Kilroy / Attractor Here

- Treat **Kilroy** as the primary way to:
  - Ingest English requirements into DOT graphs that describe **product-building pipelines**.
  - Validate graph structure and semantics.
  - Run pipelines that **generate, evolve, and glue together multiple applications** that form the product.
  - Resume and inspect runs via CXDB artifacts.

- Agents should:
  - Keep Kilroy/Attractor’s **software factory** role in mind when proposing new workflows.
  - Suggest updating or creating:
    - `*.dot` pipeline graphs,
    - `run.yaml`-style configs,
    - Project-specific skills that make Attractor runs smoother and more product-focused.

## Expectations for AI Assistants

- **Both Claude Code and GPT-based agents** should:
  - Read and follow this `AGENTS.md` at the start of any substantial task.
  - Honor the Attractor-first, multi-language, stage-based, **product-factory** design described above.
  - Avoid hard-coding assumptions that the project is “Go-only” or “Python-only,” or that Attractor is only for business process automation.

If behavior needs to change, update this file rather than scattering instructions across many places.

