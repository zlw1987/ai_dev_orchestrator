# Phase 4 — L1 Plan Generator Plan

> **This document began as the Phase 4A design doc and is now maintained as
> the Phase 4 status/plan document.** It records both what has shipped and
> what remains planned across the Phase 4 sub-phases, mirroring how
> [PHASE_3_LITELLM_CLIENT_PLAN.md](PHASE_3_LITELLM_CLIENT_PLAN.md) staged
> Phase 3.
>
> - **Phase 4A** was **docs-only** — this plan, with no runtime code, module,
>   test, or network call.
> - **Phase 4B** added the typed **`L1Plan` model**
>   ([plan/models.py](../src/ai_dev_orchestrator/plan/models.py)) with field
>   validation only. No planning logic, no model calls, no network calls.
> - **Phase 4C** added the **`FakeL1Planner` engine**
>   ([plan/fake_planner.py](../src/ai_dev_orchestrator/plan/fake_planner.py)),
>   a deterministic, offline transformation from an already-fetched
>   `GitHubIssue` / `ParsedIssue` / `ProjectConfig` into an `L1Plan`. No model
>   calls, no network calls, no env var reads, no file/workspace reads, no
>   CLI command.

This plan refines item **"Phase 4 — L1 plan generator"** of
[AI_DEV_ORCHESTRATOR_PLAN.md](AI_DEV_ORCHESTRATOR_PLAN.md).

## 1. Phase 4 goal

Implement the **L1 "plan only"** workflow, in later sub-phases:

- L1 reads a GitHub issue and produces a structured implementation plan.
- L1 must make **no file changes**, **no commits**, **no pushes**, **no PRs**,
  and **no GitHub comments**.
- L1 must **not touch target project workspaces**
  (`C:\dev\mis_project`, `C:\dev\a8_oa`, `C:\dev\bible_reading_v2`, or any
  path outside this repo).
- L1 must **not run commands inside target workspaces**, or anywhere else.

L1 corresponds to the first automation level described in
[AI_DEV_ORCHESTRATOR_PLAN.md §4](AI_DEV_ORCHESTRATOR_PLAN.md#4-automation-levels):
*"L1 — plan only. Produce a plan; make no changes."* Everything in this
document describes how that plan is produced, not how it is later acted on.

## 2. Inputs

The future L1 planner is designed to consume:

- **GitHub issue**, fetched read-only by the Phase 2 reader
  ([`github/client.py`](../src/ai_dev_orchestrator/github/client.py)) as a
  [`GitHubIssue`](../src/ai_dev_orchestrator/github/models.py) (`number`,
  `title`, `body`, `state`, `html_url`, `labels`).
- **Parsed issue sections**, produced by the Phase 2
  [`issue_parser.parse_issue_body`](../src/ai_dev_orchestrator/github/issue_parser.py)
  into a `ParsedIssue`, using the existing canonical section names:
  - `Goal`
  - `Current Context`
  - `Scope`
  - `Non-goals`
  - `Acceptance Criteria`
  - `Required Verification`
  - `AI Instructions`
  - `Automation Authorization`
- **Project config**, from Phase 1
  ([`models.ProjectConfig`](../src/ai_dev_orchestrator/models.py)) — supplies
  `allowed_paths` / `protected_paths` / `forbidden_paths`, `workspace_policy`,
  and `repo` metadata. The planner reads this config object; it never reads
  files from `repo.workspace_path` itself (see §6).
- **Optional model config**, from Phase 3B/3C
  ([`llm/models.py`](../src/ai_dev_orchestrator/llm/models.py),
  [`llm/config.py`](../src/ai_dev_orchestrator/llm/config.py)) — the typed
  `LLMRequest`/`LLMResponse`/`LLMClientConfig` shapes a later model-backed
  planner would use. **No real model call happens in Phase 4A**, and none of
  the sub-phases through 4D make one either (see §5, §7).

## 3. Output: `L1Plan`

**Phase 4A proposed** this typed output model (pydantic `BaseModel`,
consistent with [`github/models.py`](../src/ai_dev_orchestrator/github/models.py)
and [`llm/models.py`](../src/ai_dev_orchestrator/llm/models.py)). **Phase 4B
has implemented it** in
[`plan/models.py`](../src/ai_dev_orchestrator/plan/models.py), with field
validation for every rule described below (see §9). No sub-phase through 4D
generates an `L1Plan` from a real issue yet — Phase 4B adds only the typed
shape and its validation; the fields below still describe the intended
schema and safety meaning of `L1Plan`.

### `L1Plan`

- `issue_number: int` — source issue number.
- `repo: str` — `owner/name`, from `RepoConfig.github_repo`.
- `title: str` — issue title, carried through unchanged.
- `summary: str` — short restatement of what the issue is asking for.
- `scope_summary: str` — restatement of the issue's `Scope` section.
- `non_goals: list[str]` — restated from the issue's `Non-goals` section.
- `proposed_steps: list[str]` — ordered, human-readable implementation steps.
  **Descriptive text, not executable instructions** (see below).
- `files_likely_to_change: list[str]` — workspace-relative paths the plan
  expects to touch, for human review only.
- `files_forbidden_or_out_of_scope: list[str]` — paths the plan explicitly
  flags as out of bounds, cross-referenced against
  `ProjectConfig.forbidden_paths` / `protected_paths`.
- `required_verification: list[str]` — restated from the issue's
  `Required Verification` section.
- `risks: list[str]` — plan-author-identified risks or ambiguities.
- `open_questions: list[str]` — points the plan could not resolve from the
  issue text alone.
- `automation_level: Literal["L1"]` — always `"L1"` for this generator's
  output.
- `requires_human_approval: bool` — always `True` for L1 output (see §6).

*Reasoning:* the same normalized-output principle as
[`LLMResponse`](PHASE_3_LITELLM_CLIENT_PLAN.md#4-proposed-typed-models) — callers
depend on a small typed shape, not raw model text, so the planner's internals
(fake or real) can change without breaking consumers.

**This is a plan artifact only, not executable instructions.** `L1Plan` is
data describing intended work for a human (or a later, separately authorized
phase) to review and act on. Nothing in Phase 4 interprets, applies, or
executes any field of an `L1Plan`.

## 4. Prompting strategy

Design for a **future** L1 planner prompt (relevant starting Phase 4E, when a
model-backed planner is explicitly authorized — see §5, §7). Not implemented
in Phase 4A.

- Include the issue **title**, **body**, and **parsed sections** (§2) as the
  primary content the model reasons over.
- Include a **project boundary summary** — the `allowed_paths` /
  `protected_paths` / `forbidden_paths` glob lists and workspace policy flags
  from `ProjectConfig` — but **never** the actual contents of target
  workspace files. The planner describes boundaries by name/pattern only.
- Include the issue's `Non-goals` section and the project's
  `forbidden_paths` **prominently**, near the top of the prompt, so the model
  weighs them before proposing steps.
- Require the model's output in **strict structured JSON**, or a validated
  markdown/JSON hybrid, that maps directly onto the `L1Plan` fields in §3.
  Free-form prose responses are not an acceptable output shape.
- Force the model to **state uncertainty and open questions** explicitly
  (the `open_questions` field) rather than silently guessing when the issue
  is ambiguous or under-specified.
- **Forbid** the model, in the prompt itself, from proposing: implementation
  it should perform directly, shell/CLI commands to run, file edit
  operations, or GitHub write actions. The model's only job is to describe a
  plan in the `L1Plan` shape — it is never asked to act.

## 5. Model call policy

- The **first implementation supports a fake/mocked planner only** — a
  deterministic function from a parsed issue (§2) to an `L1Plan` (§3), with
  no model call at all. This mirrors how
  [`llm-smoke-test`](PHASE_3_LITELLM_CLIENT_PLAN.md#7-phase-split-recommendation)
  used an in-process fake provider rather than a real endpoint.
- Any **real model-backed planning must be behind explicit future
  authorization** — a later sub-phase (proposed Phase 4E, §7) with its own
  design review, not an implicit upgrade of the fake planner.
- **Tests must not call real models.** As in Phase 3C/3D, any test exercising
  a model-backed code path uses a faked transport
  (`httpx.MockTransport`) or a fake planner function; no socket is opened.
- **No environment variable requirement for fake-planner tests** — the fake
  planner and its tests read no `AIDO_LITELLM_*` or other env vars, matching
  the `llm-smoke-test` precedent.
- **No prompt/body logging by default** — if a future model-backed planner
  logs anything, prompt and completion bodies stay out of logs unless an
  explicit, off-by-default debug flag is set (same policy as
  [§5 of the Phase 3 plan](PHASE_3_LITELLM_CLIENT_PLAN.md#5-future-client-behavior)).
- **No API key logging, ever**, under any flag.

## 6. Safety / boundary rules

Explicit rules for the L1 planner, now and in every future sub-phase:

- The L1 planner **cannot edit files**.
- The L1 planner **cannot execute commands**.
- The L1 planner **cannot read target workspace files** — it reasons only
  over the issue text and the project's *configured* path rules (glob
  patterns and policy flags), never actual file contents from
  `repo.workspace_path`.
- The L1 planner **cannot write GitHub** — no comments, labels, issue edits,
  branches, or PRs.
- The L1 planner **cannot create branches**.
- The L1 planner **cannot escalate its own automation level** — its output
  `automation_level` is always `"L1"`, and it has no path to trigger L2+
  behavior itself.
- **A human must approve** before any later L2 implementation phase acts on
  an `L1Plan`. Every `L1Plan.requires_human_approval` is `True`; nothing in
  Phase 4 treats a plan as self-executing.

These rules are additive to, and consistent with, the existing workspace
boundary enforcement in
[`workspace/path_policy.py`](../src/ai_dev_orchestrator/workspace/path_policy.py)
and the provider policy in
[PHASE_3_LITELLM_CLIENT_PLAN.md §2](PHASE_3_LITELLM_CLIENT_PLAN.md#2-provider-policy).

## 7. Phase split recommendation

- **Phase 4A — design doc only. (DONE.)** *(this document)* No runtime code.
- **Phase 4B — typed `L1Plan` models + validation. (DONE.)** Added
  [`plan/models.py`](../src/ai_dev_orchestrator/plan/models.py) with the §3
  `L1Plan` pydantic model (plus an optional `L1PlanSource` helper), mirroring
  the `llm/` and `github/` subpackage layout, and field validation for every
  rule in §3/§6 (positive `issue_number`, `owner/repo`-shaped `repo`,
  non-blank required strings, non-empty `proposed_steps` /
  `required_verification`, non-blank list items, `automation_level` fixed to
  `"L1"`, `requires_human_approval` fixed to `True`). Path-like fields
  (`files_likely_to_change`, `files_forbidden_or_out_of_scope`) are plain
  strings only — never resolved, stat'd, or normalized. No planning logic, no
  model calls, no file/network/command IO. Unit tests
  ([tests/test_l1_plan_models.py](../tests/test_l1_plan_models.py)) cover
  every validation rule plus an import-time IO/network guard.
- **Phase 4C — fake planner engine. (DONE.)** Added
  [`plan/fake_planner.py`](../src/ai_dev_orchestrator/plan/fake_planner.py)
  with `FakeL1Planner.create_plan(issue, parsed, project) -> L1Plan`: a
  deterministic function from a parsed issue (§2) to an `L1Plan` (§3), with
  no model call — the plan-generation analog of the Phase 3C mockable
  client. `summary`/`scope_summary` come from the issue's `Goal`/`Scope`
  sections (falling back to the issue title / safe fallback text);
  `non_goals`/`required_verification` are parsed bullet lists;
  `files_likely_to_change` and the non-goals half of
  `files_forbidden_or_out_of_scope` are inferred only from explicit path-like
  tokens in section text (plain string matching — never resolved, stat'd, or
  normalized); `files_forbidden_or_out_of_scope` also always includes
  `ProjectConfig.forbidden_paths` verbatim; missing required sections and
  configured `protected_paths` surface as `risks`; vague/unresolvable scope
  surfaces as `open_questions`; `proposed_steps` are four fixed, descriptive
  (non-executable) review steps; `automation_level` and
  `requires_human_approval` are left to the `L1Plan` model's own fixed
  defaults. No model/network/env/file/workspace IO, no CLI command. Unit
  tests ([tests/test_fake_l1_planner.py](../tests/test_fake_l1_planner.py))
  cover every mapping rule, missing-section fallbacks, determinism, and an
  IO guard. Unit tests only, fully offline.
- **Phase 4D — CLI command for fake/offline plan generation.** A command
  (e.g. `generate-plan`) that wires Phase 2's issue reader/parser to the
  Phase 4C fake planner and prints an `L1Plan`, mirroring how
  `llm-smoke-test` wired Phase 3C. No real model call, no env vars required,
  no GitHub writes.
- **Phase 4E — optional model-backed planner**, behind an explicit dry-run /
  gated flag. Only introduced with its own design review; real model calls
  remain opt-in and off by default everywhere else.
- **Later — Phase 5: docs-only L2 implementer.** Out of scope for all of
  Phase 4, per
  [AI_DEV_ORCHESTRATOR_PLAN.md §7](AI_DEV_ORCHESTRATOR_PLAN.md#7-mvp-phase-roadmap).

## 8. Acceptance criteria for Phase 4A (DONE)

- [x] The design doc (`docs/PHASE_4_L1_PLAN_GENERATOR_PLAN.md`) exists.
- [x] **No `src/` or `tests/` changes** in this phase.
- [x] **No runtime behavior added.**
- [x] **No model calls.**
- [x] **No network calls** beyond existing commands if manually run.
- [x] Working tree contains **docs-only** changes.

## 9. Acceptance criteria for Phase 4B (DONE)

- [x] `plan/models.py` defines `L1Plan` (and the optional `L1PlanSource`
  helper) as pydantic `BaseModel`s with every field from §3.
- [x] Validation enforces: positive `issue_number`; non-blank `repo` shaped
  like `owner/repo`; non-blank `title` / `summary` / `scope_summary`;
  non-empty `proposed_steps` and `required_verification`; every list field
  rejects blank/whitespace-only items; `automation_level` accepts only
  `"L1"`; `requires_human_approval` accepts only `True`.
- [x] Path-like fields (`files_likely_to_change`,
  `files_forbidden_or_out_of_scope`) remain plain strings — no path
  resolution, `stat`, or normalization performed.
- [x] `plan/__init__.py` exports `L1Plan` and `L1PlanSource`; **not wired into
  the CLI**.
- [x] Unit tests (`tests/test_l1_plan_models.py`) cover every validation rule
  and confirm importing `ai_dev_orchestrator.plan` performs no
  network/process IO.
- [x] **No file reads, workspace path checks, command execution, GitHub
  writes, or model/network calls** anywhere in this phase.
- [x] No CLI plan-generation command and no fake planner engine added (both
  deferred to Phase 4C/4D).

## 10. Acceptance criteria for Phase 4C (DONE)

- [x] `plan/fake_planner.py` defines `FakeL1Planner` with
  `create_plan(issue, parsed, project) -> L1Plan`, mapping every §3 field per
  the rules described in §7.
- [x] `plan/__init__.py` exports `FakeL1Planner` alongside `L1Plan` /
  `L1PlanSource`; **not wired into the CLI**.
- [x] Deterministic: identical inputs produce identical `L1Plan.model_dump()`.
- [x] **No file reads, workspace path resolution/stat/normalization, command
  execution, GitHub writes, or model/network/environment-variable calls**
  anywhere in this phase.
- [x] Missing required issue sections never crash the planner — they produce
  safe fallback text plus a `risks`/`open_questions` entry.
- [x] `files_forbidden_or_out_of_scope` always includes
  `ProjectConfig.forbidden_paths` verbatim as plain strings.
- [x] Configured `protected_paths` produce a `risks` entry.
- [x] `automation_level` is always `"L1"` and `requires_human_approval` is
  always `True` (enforced by the underlying `L1Plan` model, per §9).
- [x] Unit tests (`tests/test_fake_l1_planner.py`) cover valid-plan
  construction, Goal/Scope mapping, bullet-list parsing, missing-section
  fallbacks, forbidden/protected path handling, path inference from Scope,
  a file/network/process/env IO guard, determinism, and confirm no CLI
  plan command exists.
- [x] No CLI plan-generation command added (deferred to Phase 4D).
