# Phase 4 — L1 Plan Generator Plan

> **This document is the Phase 4A design doc: planning only.** No runtime
> code, module, test, or network call is added in Phase 4A. It records the
> intended design for the future **L1 — plan only** automation level and
> proposes how Phase 4 should be split into sub-phases, mirroring how
> [PHASE_3_LITELLM_CLIENT_PLAN.md](PHASE_3_LITELLM_CLIENT_PLAN.md) staged
> Phase 3.

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

Proposed **future** typed output model (pydantic `BaseModel`, consistent with
[`github/models.py`](../src/ai_dev_orchestrator/github/models.py) and
[`llm/models.py`](../src/ai_dev_orchestrator/llm/models.py)). **Not
implemented in Phase 4A** — described here for Phase 4B to build.

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
- `automation_level: str` — always `"L1"` for this generator's output.
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

- **Phase 4A — design doc only.** *(this document)* No runtime code.
- **Phase 4B — typed `L1Plan` models + validation.** Add the pydantic model
  from §3 (proposed `plan/models.py`, mirroring the `llm/` and `github/`
  subpackage layout) with field validation. No planning logic, no model
  calls.
- **Phase 4C — fake planner engine.** A deterministic function from a parsed
  issue (§2) to an `L1Plan` (§3), with no model call — the plan-generation
  analog of the Phase 3C mockable client. Unit tests only, fully offline.
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

## 8. Acceptance criteria for Phase 4A

- [x] The design doc (`docs/PHASE_4_L1_PLAN_GENERATOR_PLAN.md`) exists.
- [x] **No `src/` or `tests/` changes** in this phase.
- [x] **No runtime behavior added.**
- [x] **No model calls.**
- [x] **No network calls** beyond existing commands if manually run.
- [x] Working tree contains **docs-only** changes.
