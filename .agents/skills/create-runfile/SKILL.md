---
name: create-runfile
description: Use when authoring or repairing Kilroy run config YAML/JSON files, including DOT-to-provider backend alignment and runtime policy defaults.
---

# Create Runfile

## Scope

This skill owns run config authoring (`run.yaml` / `run.json`) for `kilroy attractor run` and `resume`.

In scope:
- Building config structure (`version: 1` schema).
- Aligning provider backends with DOT model/provider usage.
- Setting runtime, preflight, modeldb, git, and CXDB defaults.

Out of scope:
- DOT graph authoring and routing design. Use `create-dotfile` for graph work.

## Overview

Core principle:
- Keep execution policy in run config, not in DOT topology.
- Align run config with what the graph needs to execute now.
- Favor explicit, deterministic defaults over implicit behavior.

Default run-config source:
- `skills/create-runfile/reference_run_template.yaml`

## Workflow

1. Collect inputs.
- Read the target DOT graph and detect provider usage (`llm_provider` attrs and `model_stylesheet`).
- Capture user constraints for production/test mode and backend policy.

2. Choose run mode explicitly.
- Production mode: `llm.cli_profile: real` and no test-shim flags.
- Test mode: `llm.cli_profile: test_shim` with shim-compatible provider config.

3. Start from the template and fill required fields.
- Required: `version`, `repo.path`, `cxdb.binary_addr`, `cxdb.http_base_url`, `modeldb.openrouter_model_info_path`.
- Keep absolute paths for repo/modeldb/script entries.
- Emit only fields supported by `internal/attractor/engine/config.go`.
- Unknown keys are rejected at load time; do not emit unsupported keys.

4. Align providers with DOT.
- For every provider used by DOT, set `llm.providers.<provider>.backend` (`api` or `cli`).
- Do not edit DOT to force backend execution strategy.

4.5 Resolve model names deterministically when catalogs are unavailable.
- Model resolution order: user-specified model -> run snapshot/modeldb path -> `internal/attractor/modeldb/pinned/openrouter_models.json` -> `internal/attractor/modeldb/manual_models.yaml` -> `skills/shared/model_fallbacks.yaml`.
- Use `skills/shared/model_fallbacks.yaml` only as backup; never let backup entries override explicit user model/provider choices.
- Normalize known aliases through fallback mappings before emitting YAML (for example provider `zai`: `glm-5.0` -> `glm-5`).

5. Populate artifact_policy from skills/shared/profile_default_env.yaml.
- The engine applies only env overrides declared explicitly in the run config.
- Read `skills/shared/profile_default_env.yaml` for per-profile reference values.
- Emit all required env vars for each profile used by the DOT graph.
- Set `artifact_policy.checkpoint.exclude_globs` for checkpoint hygiene.
- Do not use deprecated `git.checkpoint_exclude_globs`.

5.5 Declare secrets the project needs at build/test time.
- If the project under construction needs API keys at test or build time (e.g. `GEMINI_API_KEY` for smoke tests that call a live LLM), declare them in `artifact_policy.env.overrides` so they pass through to the agent shell.
- The agent shell deny-lists env vars whose names contain `API_KEY`, `SECRET`, `TOKEN`, `PASSWORD`, or `CREDENTIAL` by default. Vars declared in `artifact_policy.env.overrides` bypass this deny list because they represent explicit operator intent.
- Store the actual secret values in a `.env` file at the repo root (gitignored). The engine loads `.env` at startup and declared override keys pick up the OS values automatically.
- Use an empty string as the override value — the engine substitutes the real value from the environment at resolve time:
  ```yaml
  artifact_policy:
    env:
      overrides:
        generic:
          GEMINI_API_KEY: ""   # value comes from .env / shell environment
  ```
- Never put actual secret values in the run config file.

6. Apply runtime defaults and safety guardrails.
- Set `git.run_branch_prefix`, `git.commit_per_node`, and `git.require_clean` intentionally.
- Keep `runtime_policy` explicit (`stage_timeout_ms`, `stall_timeout_ms`, retry cap).
- Enable `preflight.prompt_probes` and use a non-aggressive timeout baseline for real-provider runs.

7. Preserve local-run robustness.
- In this repo, keep `cxdb.autostart` launcher wiring when generating local CXDB configs.
- Keep artifact/checkpoint hygiene settings where relevant (for example managed tool-cache roots).

8. Validate alignment before handoff.
- Confirm every DOT provider has a run-config backend entry.
- Confirm mode consistency (`real` vs `test_shim`) with intended command flags.
- Confirm config has no unresolved placeholder paths.
- If graph prompts consume scratch artifacts, require run-scoped paths (`.ai/runs/$KILROY_RUN_ID/...`); root `.ai` is not implicitly ingested.

## Non-Negotiable Guardrails

- Backend policy lives in run config; do not encode it in DOT structure.
- Do not omit providers that are referenced by the graph.
- Do not use fragile preflight probe timeouts for real-provider runs.
- Do not emit local CXDB configs without `cxdb.autostart` wiring in this repository context.
- Do not emit unsupported keys (for example: `runtime_robustness`, `provider_capability_constraints`).

## References

- `docs/strongdm/attractor/attractor-spec.md`
- `docs/strongdm/attractor/unified-llm-spec.md`
- `README.md`
- `skills/create-runfile/reference_run_template.yaml`
- `skills/shared/profile_default_env.yaml`
- `skills/shared/model_fallbacks.yaml`
