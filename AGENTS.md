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

