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
> - **Phase 4D** added the **`generate-plan` CLI command**
>   ([cli.py](../src/ai_dev_orchestrator/cli.py)), an offline-only command
>   wiring the Phase 2 issue parser and the Phase 4C `FakeL1Planner` together
>   from two local files (`--project-config`, `--body-file`) into a printed
>   `L1Plan`. No GitHub fetch, no model call, no env var reads, no
>   `repo.workspace_path` reads, no file editing, no command execution, no
>   GitHub writes.
> - **Phase 4E** was **docs-only** — a design review for a *future* optional
>   model-backed planner
>   ([PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md](PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md)),
>   with no runtime code, module, test, CLI option, model call, network call,
>   or env var read.
> - **Phase 4F** added the **typed model-planner errors and the pure strict
>   output parser**
>   ([plan/model_planner.py](../src/ai_dev_orchestrator/plan/model_planner.py)) —
>   `ModelPlannerError` and its `ParseError`/`ValidationError`/`PolicyError`
>   subclasses plus `parse_model_l1_plan_response(...)`, which turns strict
>   JSON *text it is handed* into a validated `L1Plan`. No model call, no
>   `LLMClient` construction, no `httpx`/`MockTransport`, no network call, no
>   env var read, no file/workspace IO, and no CLI wiring.
> - **Phase 4G** added the **pure prompt builder and the fake model-backed
>   planner** ([plan/model_planner.py](../src/ai_dev_orchestrator/plan/model_planner.py))
>   — `build_model_l1_plan_request(...)` and `ModelBackedL1Planner`, a
>   **library-only** path wiring prompt builder → an **injected** `LLMClient`
>   → the Phase 4F parser → `L1Plan`. Tested with `httpx.MockTransport` only:
>   no real model, no real network call, no env var read, no
>   `load_llm_client_config_from_env` call, no file/workspace IO, and no CLI
>   behavior.
> - **Phase 4H** was **docs-only** — a design review for a *future*, optional,
>   explicitly gated **real** model planner
>   ([PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md](PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md)),
>   with no runtime code, module, test, CLI option, model call, network call, or
>   env var read. Real model-backed planning remains **unauthorized and
>   unimplemented**.
> - **Phase 4I** added the **typed `real_model_planning` config model only**
>   ([models.py](../src/ai_dev_orchestrator/models.py)) — `enabled: false` by
>   default, an absent block identical to a disabled one, and **no gate
>   function, no env read, no client, no network call, and no CLI behavior**.
>   Real model-backed planning remains **unauthorized and unimplemented**.
> - **Phase 4J** added the **real model planning gate as a library function**
>   ([plan/real_model_gate.py](../src/ai_dev_orchestrator/plan/real_model_gate.py))
>   — `check_real_model_planning_gate(...)`,
>   `create_real_model_l1_plan_with_gate(...)`,
>   `endpoint_host_from_base_url(...)`, `build_real_model_provenance(...)`, and
>   `RealModelPlanningGateError`. It reads an **injected** env mapping (never
>   `os.environ`), plans with an **injected** client (never one it builds), and
>   validates `audit_dir` as a **flag only** — no file is created, read, stat'd,
>   or resolved. Tested with `httpx.MockTransport` and literal env dicts only:
>   **no real model call, no real network call, no real env read, and no CLI
>   behavior.** A **real** model-backed *command* remains **unauthorized and
>   unimplemented**.
> - **Phase 4K** added the **gated real model smoke-test command**,
>   `real-llm-smoke-test` ([cli.py](../src/ai_dev_orchestrator/cli.py)) — the
>   first and only command that may open a **real socket**, and only after
>   `--real-model`, a loaded project config, the project opt-in, the model
>   allowlist, and the Phase 4J gate all pass. It sends a **fixed, harmless
>   connectivity prompt** and **no issue text**, does **no planning**, fetches
>   and writes **nothing** on GitHub, reads no workspace, and writes no audit
>   file. Tests use `httpx.MockTransport` and literal env dicts only and open no
>   socket.
> - **Phase 4L** added the **gated real model L1 *plan* command**,
>   `generate-model-plan` ([cli.py](../src/ai_dev_orchestrator/cli.py)) — a
>   **separate** command from `generate-plan`, requiring `--real-model`, a
>   project config that opts in and allowlists `--model`, and a `--body-file`
>   outside the configured `repo.workspace_path`. It **does** transmit the
>   `--title` value and the local body file's text to a real model; it sends
>   **no** source files, workspace contents, directory listings, git history,
>   GitHub token, or API key. There is **no GitHub fetch and no GitHub write**,
>   no file editing, no command execution, no agent logic, no role wiring, and
>   no target workspace access, and no prompt/completion audit file is written.
>   The output is an **L1 plan only**, always `automation_level: "L1"` with
>   `requires_human_approval: true`. Tests use `httpx.MockTransport` and literal
>   env dicts only and open no socket.

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
- **Phase 4D — CLI command for fake/offline plan generation. (DONE.)** Added
  the `generate-plan` command
  ([cli.py](../src/ai_dev_orchestrator/cli.py)), which wires Phase 2's
  `parse_issue_body` and the Phase 4C `FakeL1Planner` together, mirroring how
  `llm-smoke-test` wired Phase 3C. It reads only two local files explicitly
  passed in — `--project-config` (a project config YAML) and `--body-file`
  (local issue body text) — and builds a synthetic in-memory `GitHubIssue`
  from `--repo`/`--issue`/`--title`/the body file. The project config is
  loaded **first**, with the existing `load_project_config` loader (which
  itself never reads `repo.workspace_path`); the command then rejects a
  `--body-file` that is, or sits under, the configured `repo.workspace_path`
  **before reading the body file** — a string/path normalization check only,
  never touching that path on disk — and never reads that path itself either.
  It makes **no GitHub fetch**, **no model call**, **no `AIDO_LITELLM_*` or
  other environment-variable read**, **no file edit**, **no command
  execution**, and **no GitHub write**. `--format` accepts only `json`
  (enforced via a `click`/`typer` enum choice). Output is deterministic
  pretty-printed JSON that always includes `automation_level: "L1"`,
  `requires_human_approval: true`, and a `notice` field stating the output is
  a plan-only artifact requiring human review and approval — not executable
  instructions. `generate-plan` has no
  `--live`/`--real`/`--github`/`--fetch`/`--model`/`--use-env` (or
  equivalent) option. Unit tests
  ([tests/test_cli_generate_plan.py](../tests/test_cli_generate_plan.py))
  cover success with temp files, JSON/`L1Plan` validation, expected field
  content, the `L1`/human-approval guarantees, missing-required-section
  fallback behavior, no real network call, no required env vars, no
  `repo.workspace_path` reads, rejection of a body file inside
  `repo.workspace_path` before it is read, `--format` rejection of non-`json`
  values, absence of live/model options from `generate-plan --help`, presence
  of all existing commands, and no command execution / GitHub writes.
- **Phase 4E — optional model-backed planner design review. (DONE.)** A
  **design review only**, not an implementation — see
  [PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md](PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md).
  It describes how a future model-backed planner could produce the same typed
  `L1Plan` from the same three inputs (`GitHubIssue` / `ParsedIssue` /
  `ProjectConfig`) via a pure prompt builder, the existing Phase 3C
  `LLMClient`, and a strict-JSON output parser that rejects (never repairs)
  invalid or policy-violating output; the prompt-safety rules (path patterns
  only, never workspace file contents, non-goals and forbidden paths
  prominent, strict JSON required, shell/file-edit/GitHub-write/branch/
  escalation proposals forbidden); the model-call gate; typed failure
  handling; still-open security questions; and the recommended 4F/4G/4H
  split. Phase 4E itself added **no runtime code, no module, no test, no CLI
  option, no model call, no network call, and no env var read**. Real model
  calls remain opt-in and off by default everywhere until a later sub-phase
  explicitly implements and authorizes them.
- **Phase 4F — typed planner errors + strict output parser only, no model
  call. (DONE.)** Added
  [`plan/model_planner.py`](../src/ai_dev_orchestrator/plan/model_planner.py)
  with the §6 typed error hierarchy — `ModelPlannerError` and its
  `ModelPlannerParseError` / `ModelPlannerValidationError` /
  `ModelPlannerPolicyError` subclasses — and the pure output parser
  `parse_model_l1_plan_response(text, *, issue_number, repo, title,
  project_forbidden_paths=None) -> L1Plan` described in
  [PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md §3.4](PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md#34-output-parser--pure-function).
  It parses **text it is handed**: no model call, no `LLMClient`
  construction, no `httpx`/`MockTransport`, no network call, no env var read,
  no file IO, and no workspace path resolution/stat/normalization. Strict
  shape only — exactly one JSON object (markdown fences, prose before/after,
  arrays and scalars are rejected), no extra top-level keys, no missing
  required model-controlled fields (`summary`, `scope_summary`, `non_goals`,
  `proposed_steps`, `files_likely_to_change`,
  `files_forbidden_or_out_of_scope`, `required_verification`, `risks`,
  `open_questions`). The trusted fields `issue_number` / `repo` / `title` come
  from the caller's arguments and `automation_level` / `requires_human_approval`
  are fixed to `"L1"` / `True`; a response that supplies any of the five is
  **rejected**, not silently ignored, so injection attempts surface.
  `project_forbidden_paths` are merged into
  `files_forbidden_or_out_of_scope` verbatim and deduplicated, order-preserving,
  as plain strings. The final object is validated through the Phase 4B `L1Plan`
  model, whose `ValidationError` is re-raised as `ModelPlannerValidationError`.
  A small, deterministic policy guard rejects obvious proposals of automation
  escalation, skipping human approval, command execution, direct file edits,
  branch creation, PRs, GitHub comment/label/issue writes, or target workspace
  reads with `ModelPlannerPolicyError` — conservative by design, with no
  negation handling, so a response that merely mentions a forbidden action is
  rejected for human review rather than sanitized ("reject, never repair",
  §3.5). Only model-controlled values are scanned; caller-supplied forbidden
  paths are merged afterwards and never scanned. `plan/__init__.py` exports the
  parser and the four error classes; **nothing is wired into the CLI**. Unit
  tests
  ([tests/test_model_planner_output_parser.py](../tests/test_model_planner_output_parser.py))
  cover all of the above plus an IO/network/env guard and a check that the
  existing CLI commands are unchanged. No prompt builder was added in this
  phase.
- **Phase 4G — fake model-backed planner using `httpx.MockTransport` only.
  (DONE.)** Added, to
  [`plan/model_planner.py`](../src/ai_dev_orchestrator/plan/model_planner.py),
  the two remaining boxes of
  [PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md §3](PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md#3-future-architecture):
  - **`build_model_l1_plan_request(issue, parsed, project, *, model) ->
    LLMRequest`** — the §3.2 **pure** prompt builder. Deterministic (identical
    inputs produce an identical `LLMRequest.model_dump()`); no clock, no
    randomness, no env reads, no file/workspace reads, no network, and no
    client or transport, so it cannot send what it builds. It emits a system
    message and a user message using the existing `LLMRequest` / `LLMMessage`
    models. The system message leads with the project's **forbidden paths**,
    then protected and allowed paths and the `workspace_policy` flags (as
    **patterns, names, and flags only** — never target workspace file contents,
    never `repo.workspace_path` itself), then the issue's **Non-goals**, then
    the untrusted-input rule, then the forbidden-proposal list, and ends with
    the output contract. The user message carries the issue title, body, all
    canonical parsed sections in fixed order, and the missing-required-section
    report. Every issue-derived value is wrapped in explicit
    `<<<UNTRUSTED_ISSUE_TEXT>>>` / `<<<END_UNTRUSTED_ISSUE_TEXT>>>` markers and
    labelled as data to summarize, never instructions to follow; markers
    appearing *inside* issue text are neutralized so the block cannot be closed
    early. The prompt requires **exactly one strict JSON object** with exactly
    the nine model-controlled fields, **forbids** the five trusted fields
    (`issue_number`, `repo`, `title`, `automation_level`,
    `requires_human_approval`), forbids shell commands, file edits, diffs,
    branches, PRs, GitHub writes, workspace reads, automation escalation and
    skipping human approval, and requires explicit uncertainty in `risks` /
    `open_questions`.
  - **`ModelBackedL1Planner(client)`** with
    `create_plan(issue, parsed, project, *, model) -> L1Plan` — builds the
    request, calls `self.client.chat(request)`, and parses `response.content`
    with the Phase 4F `parse_model_l1_plan_response(...)`, passing the
    caller-trusted `issue.number` / `project.repo.github_repo` / `issue.title`
    and `project.forbidden_paths` as `project_forbidden_paths`. The client is
    **always injected**: the planner constructs none, loads no config, reads no
    env var, never calls `load_llm_client_config_from_env`, and the module
    imports neither `httpx` nor `LLMClient` at runtime (the annotation is
    `TYPE_CHECKING`-only) — so there is no code path here that can build a real
    client. No retry logic beyond the injected client's own, and no
    prompt/completion logging.

  `plan/__init__.py` exports both; **nothing is wired into the CLI**. Unit
  tests
  ([tests/test_model_backed_l1_planner.py](../tests/test_model_backed_l1_planner.py))
  use `httpx.MockTransport` only — every `LLMClient` is built by the test from
  literal config against a fake `.invalid` base URL and injected — and cover
  prompt determinism, prompt content, path-patterns-without-file-contents,
  untrusted marking (including marker-injection), the forbidden trusted fields
  and actions, an end-to-end valid `L1Plan`, caller-trusted field precedence,
  rejection of model-supplied trusted fields, rejection of
  command/GitHub-write/escalation proposals, forbidden-path merging, plus
  no-socket, no-env-read, no-file/workspace-read, injected-client-required, and
  unchanged-CLI guards. The Phase 4F module guard
  ([tests/test_model_planner_output_parser.py](../tests/test_model_planner_output_parser.py))
  was narrowed from forbidding `LLMRequest` in the module's globals to
  forbidding only what could construct a client (`httpx`, `LLMClient`,
  `LLMClientConfig`, `requests`), because building an `LLMRequest` is exactly
  what the newly authorized prompt builder does.
- **Phase 4H — gated real model planner design review. (DONE.)** A **design
  review only**, not an implementation — see
  [PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md](PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md).
  It designs the fail-closed real-call gate (opt-in only, never default; an
  explicit entry point plus a project-local opt-in; a non-suppressible
  before/after warning naming the endpoint **host** and model but never the API
  key; every precondition checked before any client is constructed; no silent
  fake→real or real→fake fallback; explicit engine provenance); a proposed
  `real_model_planning` project-config block (`enabled: false` by default, an
  exact-match `allowed_models` list where empty means none, and
  `allow_prompt_audit_files: false`) that is **not implemented** and would be
  rejected by today's `extra="forbid"` loader; env rules reusing the existing
  Phase 3B `AIDO_LITELLM_*` names, read **only** in the future real path and
  never by the fake/offline paths, with keys never logged; a CLI comparison
  recommending a **separate command** over a `--real` flag on `generate-plan`,
  so `generate-plan` keeps its offline-only guarantee verbatim; a
  doubly-opt-in prompt/completion audit design whose path must pass the Phase 4D
  workspace guard; the allowed inputs (`GitHubIssue` / `ParsedIssue` /
  `ProjectConfig` only — never workspace tree or file contents); provenance as
  **wrapper metadata around** `L1Plan` rather than new `L1Plan` fields; the
  fail-closed failure table reusing the Phase 4F error hierarchy; the remaining
  open questions; and the 4I/4J/4K/4L implementation split. Phase 4H itself
  added **no runtime code, no module, no test, no CLI option, no model call, no
  network call, and no env var read**. Real model planning remains
  **unauthorized**, and there is still **no CLI command that can call a real
  model**.
- **Phase 4I — typed `real_model_planning` config model only. (DONE.)**
  `RealModelPlanningConfig` in
  [models.py](../src/ai_dev_orchestrator/models.py) — `enabled: bool = False`,
  `allowed_models: list[str] = []` (non-blank entries, duplicates rejected),
  and `allow_prompt_audit_files: bool = False` — plus an optional
  `real_model_planning` field on `ProjectConfig` that defaults to a disabled
  instance, so configs omitting the block keep loading and are behaviorally
  indistinguishable from ones that set `enabled: false`. It is `extra="forbid"`
  like every other config model, so credential-shaped keys (`api_key`,
  `base_url`, `endpoint`) are rejected as unknown fields, and it holds **no**
  credential, endpoint, or env-var value. Nothing reads it yet: **no allowlist
  check function, no env read, no client construction, no audit file writing,
  no CLI command or option, no model call, and no network call.**
  [projects/mis_project.yaml.example](../projects/mis_project.yaml.example)
  documents the block in its explicitly disabled form.
- **Phase 4J — real planner gate as a library function. (DONE.)**
  [plan/real_model_gate.py](../src/ai_dev_orchestrator/plan/real_model_gate.py)
  implements the design §3.4 preconditions and §10 failure taxonomy over an
  **injected** env mapping and an **injected** client:
  `RealModelPlanningGateError` (a `ModelPlannerError` subclass, gate failures
  only), `endpoint_host_from_base_url(...)` (pure URL parsing to `host` or
  `host:port`, dropping userinfo/path/query/fragment),
  `check_real_model_planning_gate(...)` (project opt-in → non-blank requested
  model → non-empty allowlist → exact match → audit flag → injected env →
  endpoint shape, returning an `LLMClientConfig` whose `default_model` is pinned
  to the requested model), `build_real_model_provenance(...)` (pure,
  clock-free, key-free), and `create_real_model_l1_plan_with_gate(...)`, which
  runs the gate first and then calls the Phase 4G `ModelBackedL1Planner` with
  the **caller's** client. It reads **no** `os.environ` (a missing mapping is a
  gate error, never a fallback), constructs **no** client or transport (`httpx`
  is not imported; `LLMClient` is `TYPE_CHECKING`-only), makes **no** network
  call, touches **no** filesystem (`audit_dir` is a flag, never created, read,
  stat'd, or resolved — audit writing stays unimplemented), and adds **no CLI
  behavior**. Tested with `httpx.MockTransport` and literal env dicts only.
  A real model-backed **plan** command remains **unauthorized** (Phase 4L).
- **Phase 4K — gated real model smoke-test command. (DONE — explicitly
  authorized.)** `real-llm-smoke-test` in
  [cli.py](../src/ai_dev_orchestrator/cli.py): a **separate** command (design
  §6 Option B), requiring an explicit `--real-model` flag, `--project-config`,
  and `--model`. In order: the flag is checked, the config is loaded, the
  Phase 4J gate is probed with an **empty** mapping so a project-opt-in or
  allowlist failure surfaces **before any environment value is read**, then and
  only then are the five `AIDO_LITELLM_*` names read and the gate run for real,
  then the §3.3 warning block is written to stderr, and only then is a real
  `LLMClient` built. It sends a **fixed connectivity prompt** — no issue text,
  no file or workspace contents, no project data — with the explicit `--model`,
  never the env default. A matching post-call block reports success or failure;
  JSON with `provenance.operation: "smoke-test"` goes to stdout. The API key is
  never printed and the endpoint appears as a **host only**. No `--issue`,
  `--body-file`, `--github`, `--fetch`, `--audit-dir`, or `--message` option
  exists; no audit file is written; no plan is produced. Tests use
  `httpx.MockTransport` and literal env dicts only and open no socket.
- **Phase 4L — gated real model *plan* command. (DONE — explicitly
  authorized.)** `generate-model-plan` in
  [cli.py](../src/ai_dev_orchestrator/cli.py): a **separate** command (design
  §6 Option B), requiring `--real-model`, `--project-config`, `--issue`,
  `--title`, `--body-file`, and `--model`. `generate-plan` is untouched and
  still offline-only. In order: the flag is checked, the config is loaded, the
  `--body-file` workspace guard runs, the Phase 4J gate is probed with an
  **empty** mapping so a project-opt-in or allowlist failure surfaces **before
  any environment value is read**, then the five `AIDO_LITELLM_*` names are read
  and the gate runs for real, then — and only then — the body file is read, the
  §3.3 warning block is written to stderr, and a real `LLMClient` is built. The
  Phase 4G `ModelBackedL1Planner` does the planning with the explicit `--model`,
  never the env default. Sent: the title, the body text, its parsed sections,
  and the project's path **patterns** and policy flags. Not sent: source files,
  workspace contents, directory listings, git history, the GitHub token, the API
  key. A matching post-call block reports success or failure — distinguishing
  parser, validation, and policy failures by name without echoing the reply —
  and JSON with `provenance.operation: "l1-plan"` plus the `L1Plan` and token
  usage goes to stdout. No `--github`, `--fetch`, `--repo`, or `--audit-dir`
  option exists; no audit file is written; no GitHub call is made. Tests use
  `httpx.MockTransport` and literal env dicts only and open no socket.
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

## 11. Acceptance criteria for Phase 4D (DONE)

- [x] A `generate-plan` CLI command exists in
  [cli.py](../src/ai_dev_orchestrator/cli.py) with required options
  `--project-config`, `--repo`, `--issue`, `--title`, `--body-file`, and an
  optional `--format` (default/only `json`).
- [x] Reads **only** the two local files explicitly passed in
  (`--project-config`, `--body-file`); does not scan the `projects/`
  directory, list directories, or read the configured `repo.workspace_path`.
- [x] Loads the project config with the existing `load_project_config`
  **first**; parses the body file with the Phase 2 `parse_issue_body`; builds
  a synthetic `GitHubIssue` from `--repo`/`--issue`/`--title`/body; calls the
  Phase 4C `FakeL1Planner.create_plan(...)`.
- [x] Rejects (exit code 1, clear stderr message) a `--body-file` that is, or
  sits under, the configured `repo.workspace_path` — checked **before** the
  body file is read, using string/path normalization only, never reading,
  listing, stat'ing, or resolving that path on disk.
- [x] Prints the resulting `L1Plan` as deterministic pretty JSON that
  validates against the `L1Plan` model and always carries
  `automation_level: "L1"` and `requires_human_approval: true`, plus a
  `notice` field stating the output is a plan-only artifact requiring human
  review and approval.
- [x] **No GitHub fetch, no model call, no network call, no
  `AIDO_LITELLM_*`/other environment-variable read, no file editing, no
  command execution, and no GitHub write** anywhere in the command.
- [x] `generate-plan` has no
  `--live`/`--real`/`--github`/`--fetch`/`--model`/`--use-env` (or
  equivalent) option, and **no CLI command can call a real model**. (The
  pre-existing `llm-smoke-test` does expose a `--model` option, but it only
  names the fake model echoed by its in-process mock transport — it selects
  nothing real and calls no real model.)
- [x] `--format` rejects values other than `json`.
- [x] Missing required issue sections still produce valid, non-crashing JSON
  (fallback `risks`/`open_questions`, per the Phase 4C planner).
- [x] Unit tests
  ([tests/test_cli_generate_plan.py](../tests/test_cli_generate_plan.py))
  cover all of the above plus a no-real-network-call guard, an env-var
  guard, a `repo.workspace_path` read guard, a guard proving a body file
  inside `repo.workspace_path` is rejected before being read,
  existing-commands presence, and a no-command-execution / no-GitHub-write
  guard.
- [x] No agent logic, implementer/reviewer/fixer role wiring, or file editing
  engine added.

## 12. Acceptance criteria for Phase 4E (DONE)

- [x] The design doc
  ([PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md](PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md))
  exists and covers goal, non-goals, future architecture, prompt safety, the
  model call gate, failure handling, open security questions, and the
  post-4E phase split.
- [x] **No `src/` or `tests/` changes** in this phase.
- [x] **No runtime behavior added.**
- [x] **No model calls, no network calls, no environment-variable reads.**
- [x] **No CLI behavior added** — no new command or option, and no change to
  `generate-plan`, `llm-smoke-test`, `inspect-issue`, or `version`.
- [x] No GitHub fetch/write, command execution, file editing engine, agent
  logic, role wiring, or target project workspace access added.
- [x] Working tree contains **docs-only** changes.

## 13. Acceptance criteria for Phase 4F (DONE)

- [x] [`plan/model_planner.py`](../src/ai_dev_orchestrator/plan/model_planner.py)
  defines the typed error hierarchy `ModelPlannerError` with
  `ModelPlannerParseError`, `ModelPlannerValidationError`, and
  `ModelPlannerPolicyError` subclasses.
- [x] It defines the **pure** parser
  `parse_model_l1_plan_response(text, *, issue_number, repo, title,
  project_forbidden_paths=None) -> L1Plan`, with no file IO, no env reads, no
  network, no model client, and no workspace path operations.
- [x] Accepts exactly one strict JSON object; rejects markdown fences, prose
  before/after the object, arrays, strings, numbers, booleans, and null.
- [x] Invalid JSON raises `ModelPlannerParseError`.
- [x] Unexpected extra top-level keys, missing required model-controlled
  fields, and wrong field types raise `ModelPlannerValidationError`.
- [x] Trusted fields are never taken from model output: `issue_number` /
  `repo` / `title` come from the arguments, `automation_level` is always
  `"L1"`, `requires_human_approval` is always `True`, and a response
  containing any of the five is rejected with
  `ModelPlannerValidationError`.
- [x] `project_forbidden_paths` are merged into
  `files_forbidden_or_out_of_scope` verbatim and deduplicated as plain
  strings, with no path resolution, `stat`, globbing, or normalization.
- [x] The final object is validated through the Phase 4B `L1Plan`; a pydantic
  `ValidationError` is re-raised as `ModelPlannerValidationError`.
- [x] Obvious proposals of automation escalation, no-human-approval, command
  execution, direct file edits, branch creation, PRs, GitHub
  comment/label/issue writes, or target workspace reads raise
  `ModelPlannerPolicyError`.
- [x] `plan/__init__.py` exports the parser and all four error classes;
  **nothing is wired into the CLI** and no existing CLI command changed.
- [x] Unit tests
  ([tests/test_model_planner_output_parser.py](../tests/test_model_planner_output_parser.py))
  cover every rule above plus a file/network/process/env IO guard, a
  path-resolution guard, and an existing-CLI-commands check.
- [x] **No model call, no `LLMClient` construction, no `httpx`/`MockTransport`,
  no network call, no environment-variable read, no file IO, no workspace
  access, no GitHub fetch/write, no command execution, no file editing engine,
  no agent logic, and no implementer/reviewer/fixer role wiring** anywhere in
  this phase.
- [x] No prompt builder added (optional in the 4E split; deferred to Phase 4G).

## 14. Acceptance criteria for Phase 4G (DONE)

- [x] [`plan/model_planner.py`](../src/ai_dev_orchestrator/plan/model_planner.py)
  defines the **pure** prompt builder
  `build_model_l1_plan_request(issue, parsed, project, *, model) -> LLMRequest`,
  built on the existing `LLMRequest` / `LLMMessage` models.
- [x] The prompt builder is deterministic — identical inputs produce an
  identical `LLMRequest.model_dump()` — and constructs no `LLMClient`, reads no
  environment variable, makes no network call, performs no file or workspace
  read, and uses no clock or randomness.
- [x] The prompt includes the issue **title**, **body**, all canonical **parsed
  sections** (in fixed canonical order), and the missing-required-section
  report.
- [x] The prompt includes `allowed_paths` / `protected_paths` /
  `forbidden_paths` and the `workspace_policy` flags **as patterns, names and
  flags only** — and includes **no** target workspace file contents, directory
  listing, file tree, git history, or `repo.workspace_path` value.
- [x] The issue's **Non-goals** and the project's **forbidden paths** appear
  prominently and early in the **system** message, ahead of the output
  contract.
- [x] All issue-derived text is clearly marked as **untrusted data, not
  instructions**, inside explicit delimiters; delimiters occurring within issue
  text are neutralized so the untrusted block cannot be closed early.
- [x] The prompt requires **exactly one strict JSON object** with exactly the
  nine model-controlled fields (`summary`, `scope_summary`, `non_goals`,
  `proposed_steps`, `files_likely_to_change`,
  `files_forbidden_or_out_of_scope`, `required_verification`, `risks`,
  `open_questions`), and explicitly **forbids** the trusted fields
  `issue_number` / `repo` / `title` / `automation_level` /
  `requires_human_approval`.
- [x] The prompt **forbids** proposing shell commands, file edits, diffs or
  patches, branch creation, pull requests, GitHub writes, workspace reads,
  automation escalation, and skipping human approval — and requires explicit
  uncertainty in `risks` / `open_questions`.
- [x] `ModelBackedL1Planner.__init__(self, client)` stores an **injected**
  client; `create_plan(issue, parsed, project, *, model) -> L1Plan` builds the
  request, calls `self.client.chat(request)`, and parses `response.content`
  with the Phase 4F `parse_model_l1_plan_response(...)`.
- [x] The planner passes the caller-trusted `issue.number`,
  `project.repo.github_repo` and `issue.title`, and passes
  `project.forbidden_paths` as `project_forbidden_paths`; trusted fields are
  never taken from model output, and output supplying them is rejected.
- [x] The planner **constructs no `LLMClient`**, loads no config, reads no
  environment variable, never calls `load_llm_client_config_from_env`, and the
  module imports neither `httpx` nor `LLMClient` at runtime — it has no way to
  build a real client. No retry logic beyond the injected client's own, and no
  prompt/completion logging.
- [x] `plan/__init__.py` exports `build_model_l1_plan_request` and
  `ModelBackedL1Planner`; **nothing is wired into the CLI** and no existing CLI
  command changed.
- [x] Unit tests
  ([tests/test_model_backed_l1_planner.py](../tests/test_model_backed_l1_planner.py))
  use `httpx.MockTransport` only, never call real LiteLLM, never read
  `AIDO_LITELLM_*`, use only fake/`.invalid` URL strings, and never inspect a
  target workspace. They cover every rule above plus no-socket,
  no-environment-read, no-file/workspace-read, injected-client-required, and
  unchanged-CLI guards.
- [x] **No real model call, no real network call, no environment-variable read,
  no file/workspace IO, no CLI behavior, no GitHub fetch or write, no command
  execution, no file editing engine, no agent logic, and no
  implementer/reviewer/fixer role wiring** anywhere in this phase.
- [x] Phase 4H (optional gated **real** model planner) remains **proposed and
  not authorized**. *(Phase 4H has since shipped as a **design review only** —
  see §15 — and real model planning remains unauthorized and unimplemented.)*

## 15. Acceptance criteria for Phase 4H (DONE)

- [x] The design doc
  ([PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md](PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md))
  exists and covers the goal, non-goals, the fail-closed real-call gate, the
  project allowlist, env/config design, CLI options with an explicit
  recommendation, prompt/audit design, input sources, output provenance,
  failure handling, remaining open questions, and the post-4H implementation
  split.
- [x] **No `src/` or `tests/` changes** in this phase.
- [x] **No runtime behavior added.**
- [x] **No model calls, no network calls, no environment-variable reads**, and
  no call to `load_llm_client_config_from_env`.
- [x] **No CLI behavior added** — no new command, no new option, no
  real/live/model option, and no change to `generate-plan`, `llm-smoke-test`,
  `inspect-issue`, or `version`.
- [x] No GitHub fetch/write, command execution, file editing engine, agent
  logic, implementer/reviewer/fixer role wiring, or target project workspace
  access added.
- [x] Phase 4H is clearly marked **design-only**; real model planning is
  **not authorized** and **not implemented**, and there is still no CLI command
  that can call a real model.
- [x] Working tree contains **docs-only** changes.

## 16. Acceptance criteria for Phase 4I (DONE)

- [x] `RealModelPlanningConfig` exists in
  [models.py](../src/ai_dev_orchestrator/models.py) with `enabled: bool = False`,
  `allowed_models: list[str] = []`, and
  `allow_prompt_audit_files: bool = False`.
- [x] `ProjectConfig.real_model_planning` defaults to a disabled instance, so a
  config **omitting** the block still loads and is behaviorally identical to one
  that sets `enabled: false`. All other config behavior is unchanged.
- [x] Validation: blank/whitespace-only model names are rejected; duplicate
  `allowed_models` entries are **rejected** (not silently deduplicated) so
  config mistakes surface; an empty `allowed_models` is valid config that
  permits no model; unknown fields are rejected (`extra="forbid"`), which is
  what rejects credential-shaped keys such as `api_key`, `base_url`, and
  `endpoint`.
- [x] **No credential, endpoint, or environment-variable value** appears in the
  model or in the example YAML.
- [x] [projects/mis_project.yaml.example](../projects/mis_project.yaml.example)
  documents the block in its explicitly disabled form.
- [x] **No gate logic**: no allowlist-checking function, no env loading, no real
  model client construction, no audit file writing, and no real-model CLI,
  smoke-test, or planner command.
- [x] **No model call, no network call, no `httpx`/`MockTransport` use, no
  `LLMClient` construction, and no environment-variable read** — asserted by
  tests that monkeypatch `os.getenv` / `os.environ.get` / `socket` /
  `subprocess.Popen`.
- [x] **No CLI behavior added** — root `--help` still exposes only `version`,
  `inspect-issue`, `llm-smoke-test`, and `generate-plan`; `generate-plan` and
  `llm-smoke-test` are unchanged and still have no real/live/model option.
- [x] No GitHub fetch/write, command execution, file editing engine, agent
  logic, implementer/reviewer/fixer role wiring, or target project workspace
  access added.
- [x] Tests in [tests/test_config_loader.py](../tests/test_config_loader.py)
  cover the absent block, the explicit disabled block, enabled-with-models,
  enabled-with-empty-list, blank names, duplicates, extra fields,
  credential-like extras, the defaults, and the guards above; the existing
  config tests still pass.
- [x] Real model planning remains **unauthorized and unimplemented**, and there
  is still no CLI command that can call a real model.

## 17. Acceptance criteria for Phase 4J (DONE)

- [x] [plan/real_model_gate.py](../src/ai_dev_orchestrator/plan/real_model_gate.py)
  exists and is **library-only**: `RealModelPlanningGateError`,
  `endpoint_host_from_base_url(...)`, `check_real_model_planning_gate(...)`,
  `build_real_model_provenance(...)`, and
  `create_real_model_l1_plan_with_gate(...)`, all exported from
  [plan/__init__.py](../src/ai_dev_orchestrator/plan/__init__.py) and wired into
  **nothing**.
- [x] `RealModelPlanningGateError` subclasses `ModelPlannerError` and is raised
  for **gate/precondition failures only** — never for parser failures (Phase 4F
  types) or transport failures (Phase 3C `LLMClientError` family), both of which
  propagate unchanged.
- [x] **Fails closed** (design §3.4/§4): an absent or `enabled: false`
  `real_model_planning` block is refused; an empty `allowed_models` permits no
  model even when enabled; a blank requested model is refused; and the requested
  model must match an `allowed_models` entry **exactly** — prefixes, suffixes,
  case differences, surrounding whitespace, and glob-looking names are all
  refused. Duplicate model names remain **Phase 4I config-level** validation,
  so the gate needs no dedupe logic.
- [x] **The environment is injected, never read.** `os.environ` is never
  touched, `load_llm_client_config_from_env(...)` is called **only** with the
  injected mapping, and a missing mapping is a gate error rather than a silent
  fallback to the process environment. Missing or blank required
  `AIDO_LITELLM_*` values raise `LLMConfigError` **before the client is used**.
- [x] **`AIDO_LITELLM_DEFAULT_MODEL` cannot select the planning model.** A
  differing env default is not fatal; instead the returned `LLMClientConfig` has
  `default_model` **pinned to the allowlisted `requested_model`**, and
  `create_real_model_l1_plan_with_gate(...)` passes `requested_model` to the
  planner explicitly. The env supplies *connection* details; the project config
  supplies *permission* (design §4.3).
- [x] `endpoint_host_from_base_url(...)` is **pure string/URL parsing**: it
  returns `host` or `host:port` and never returns userinfo, an API key, a path,
  a query string, or a fragment. A blank, schemeless, unparseable, or
  invalid-port URL raises `RealModelPlanningGateError`, and **no error message
  echoes the base URL** (which may itself embed a credential).
- [x] **No client is ever constructed.** `httpx` is not imported by the module,
  `LLMClient` appears only under `TYPE_CHECKING`, the validated config is used
  for validation/provenance only, and the **injected** client is the only one
  used. Every test injects an `httpx.MockTransport`-backed client.
- [x] **No real model call and no real network call** — asserted by tests that
  monkeypatch `socket.socket` / `socket.create_connection` /
  `socket.getaddrinfo` / `socket.gethostbyname` / `subprocess.Popen`.
- [x] **No filesystem or workspace IO.** `audit_dir` is validated as a **flag
  only**: refused when `allow_prompt_audit_files` is false (and when blank), and
  otherwise never created, read, stat'd, resolved, or listed. **Audit file
  writing is not implemented in this phase.** Asserted by tests that
  monkeypatch `builtins.open`, `os.stat`, `os.listdir`, `os.scandir`,
  `os.makedirs`, `os.path.exists`, `os.path.abspath`, and `os.path.realpath`.
- [x] `build_real_model_provenance(...)` is **pure and deterministic** with
  `engine: "real-model"`, `real_call: true`, the requested model, a **host-only**
  endpoint, and issue/repo/title/project id from trusted inputs. It carries
  **no `generated_at`** (clock use is not authorized here) and **no API key**,
  and it is wired into no command.
- [x] **No CLI behavior added** — root `--help` still exposes only `version`,
  `inspect-issue`, `llm-smoke-test`, and `generate-plan`; `generate-plan` still
  has no `--real`/`--live`/`--model`/`--use-env`/`--github`/`--fetch`/
  `--audit-dir` option, and `llm-smoke-test` is unchanged (its pre-existing
  `--model` still names a *fake* model for the in-process fake provider).
- [x] No GitHub fetch/write, command execution, file editing engine, agent
  logic, implementer/reviewer/fixer role wiring, or target project workspace
  access added; the gate module imports no GitHub client.
- [x] Tests in
  [tests/test_real_model_planner_gate.py](../tests/test_real_model_planner_gate.py)
  cover all of the above, use `httpx.MockTransport` and literal env dicts only,
  and never read `AIDO_LITELLM_*` from the real process environment.
- [x] A **real** model-backed command remains **unauthorized and
  unimplemented**: there is still no CLI command that can call a real model.
  Phase 4K (a gated real model smoke-test command) is **not authorized** unless
  explicitly approved. *(Phase 4K was subsequently authorized and has since
  shipped — see §18. The gate above is unchanged by it.)*

## 18. Acceptance criteria for Phase 4K (DONE)

- [x] A **separate** command, `real-llm-smoke-test`, exists in
  [cli.py](../src/ai_dev_orchestrator/cli.py) (design §6 Option B — not a flag
  on an existing command), exposing exactly `--project-config`, `--model`, and
  `--real-model`.
- [x] **Explicitly authorized.** The user authorized Phase 4K and authorized
  opening a real socket when *manually* running this command. That
  authorization covers **this command only** — not a real planner, issue text,
  GitHub access, file edits, command execution, agent logic, role wiring, or
  target workspace access.
- [x] **Fails closed without `--real-model`**: the flag is checked first, so a
  plain invocation reads **no** environment variable, builds **no** client, and
  makes **no** network call, exiting 1 with a clear stderr message.
- [x] **Ordering is enforced.** Flag → project config load → project opt-in →
  model allowlist → *then* environment read → gate → banner → client. The
  opt-in/allowlist checks run by probing the Phase 4J gate with an **empty**
  mapping, so those failures surface with the gate's own message while the real
  environment is still untouched.
- [x] **Only the five Phase 3B `AIDO_LITELLM_*` names are read**, only inside
  this command, and only after the checks above. No value is printed, and the
  API key is never read into any output path.
- [x] **The Phase 4J gate is authoritative**: a disabled project, an empty
  `allowed_models`, a non-allowlisted model, and missing/blank required
  environment values all fail with exit 1, **before** any client is built.
- [x] **Non-suppressible stderr banner before the call** naming the endpoint
  **host only**, the model, the project id, and stating that no issue text is
  sent and no files/workspaces/GitHub are read or written (design §3.3); a
  matching **after-call** block reports completion or failure and is printed
  **only** when a real call was actually attempted.
- [x] **A fixed, harmless prompt only** — a connectivity system message plus
  "Reply with exactly: AIDO_REAL_SMOKE_OK", with `temperature=0.0` and a small
  `max_tokens`. No issue text, no file or workspace contents, and no project
  data are transmitted; the explicit `--model` is sent, never the env default.
- [x] **JSON to stdout on success only**, carrying `provenance.engine:
  "real-model"`, `provenance.operation: "smoke-test"`, `real_call: true`, the
  model, the endpoint **host**, the project id, the response content, and usage.
  No API key, no base URL, and no prompt text. Nothing is printed to stdout on
  any failure path.
- [x] **No audit files** are written, and no `--audit-dir` option exists.
- [x] **No other CLI behavior changed**: `generate-plan` stays offline-only with
  no `--real`/`--real-model`/`--live`/`--model`/`--use-env`/`--github`/
  `--fetch`/`--audit-dir`; `llm-smoke-test` stays fake-provider only, with its
  pre-existing `--model` still naming a fake model; `inspect-issue` and
  `version` are untouched.
- [x] **No `--issue`, `--body-file`, `--github`, `--fetch`, or `--message`
  option**, so there is no way to supply issue text or reach GitHub from this
  command, and no GitHub client is used by it.
- [x] **Only the explicitly named project config file is read.** The configured
  `repo.workspace_path` is never read, listed, stat'd, or resolved.
- [x] **Tests never open a real socket and never read a real environment
  value**: [tests/test_cli_real_llm_smoke_test.py](../tests/test_cli_real_llm_smoke_test.py)
  injects a literal env mapping and an `httpx.MockTransport`-backed client into
  a private helper, monkeypatches `socket.*`/`subprocess.Popen` to raise, and
  drives fail-closed and help behavior through the CLI.
- [x] The real model **plan** command was left for Phase 4L, along with agent
  logic, role wiring, file editing, command execution, GitHub writes, and target
  workspace access. *(Phase 4L has since shipped the plan command — and only
  that; the rest remain unimplemented.)*

## 19. Acceptance criteria for Phase 4L (DONE)

- [x] A **separate** command, `generate-model-plan`, exists in
  [cli.py](../src/ai_dev_orchestrator/cli.py) (design §6 Option B — not a flag
  on `generate-plan`), exposing `--project-config`, `--issue`, `--title`,
  `--body-file`, `--model`, `--real-model`, and `--format`.
- [x] **Explicitly authorized.** The user authorized Phase 4L and authorized
  opening a real socket when *manually* running this command, and authorized
  sending the explicitly provided local issue body text to the real model after
  all gates pass. That authorization covers **this command only** — not GitHub
  writes, file edits, command execution, agent logic, role wiring, target
  workspace access, or using real project source files as model context.
- [x] **Fails closed without `--real-model`**: the flag is checked first, so a
  plain invocation reads **no** environment variable, **no** project config,
  **no** body file, builds **no** client, and makes **no** network call, exiting
  1 with a clear stderr message and nothing on stdout.
- [x] **Ordering is enforced.** Flag → project config load → `--body-file`
  workspace guard → project opt-in → model allowlist → *then* environment read →
  gate → **body file read** → banner → client. The opt-in/allowlist checks run
  by probing the Phase 4J gate with an **empty** mapping, so those failures
  surface with the gate's own message while the real environment and the issue
  body are both still untouched.
- [x] **The `--body-file` guard runs before the file is touched.** A body file
  that is the configured `repo.workspace_path` or sits under it is rejected with
  exit 1 before it is read or stat'd. `--body-file` deliberately carries **no**
  Typer `exists=`/`readable=` check, because those would stat the path before
  the guard could run. The check is string/path normalization only
  (`_is_same_or_under`); the configured workspace path is never read, listed,
  stat'd, or resolved.
- [x] **Only the two explicitly named files are read**, in that order: the
  `--project-config` YAML, then the `--body-file`. Nothing else on disk is
  opened, listed, or resolved, and a missing/unreadable body file after the gate
  exits 1 with no client built and no call made.
- [x] **Only the five Phase 3B `AIDO_LITELLM_*` names are read**, only inside
  this command, and only after the checks above. No value is printed, and the
  API key never reaches any output path.
- [x] **The Phase 4J gate is authoritative**: a disabled project, an empty
  `allowed_models`, a non-allowlisted model, and missing/blank required
  environment values all fail with exit 1, **before** the body file is read and
  before any client is built.
- [x] **Non-suppressible stderr banner before the call** naming the endpoint
  **host only**, the model, the project id, the repo, and the issue number and
  title, and stating plainly that the issue title and body text **will be
  transmitted** and that no source files, workspace contents, GitHub writes, or
  commands are involved (design §3.3); a matching **after-call** block reports
  completion or failure and is printed **only** when a real call was actually
  attempted.
- [x] **The explicit `--model` is sent, never the env default.**
  `AIDO_LITELLM_DEFAULT_MODEL` supplies connection details only; the gate pins
  the returned config's `default_model` to the allowlisted request, and the
  model name is passed to the Phase 4G planner explicitly.
- [x] **No GitHub fetch and no GitHub write.** The `GitHubIssue` is synthesized
  in memory from `--issue`/`--title`/the body file, with an `html_url` that says
  so; no GitHub client is constructed or called, and no option could reach one.
- [x] **JSON to stdout on success only**, carrying `provenance.engine:
  "real-model"`, `provenance.operation: "l1-plan"`, `real_call: true`, the
  model, the endpoint **host**, the project id, the repo, the issue number, the
  title, a UTC `generated_at`, the `L1Plan` under `plan`, and token usage under
  `usage`. No API key, no base URL, no raw prompt, no raw completion, no source
  files, and no workspace path. Nothing is printed to stdout on any failure path.
- [x] **The plan is L1 only**: `plan.automation_level` is `"L1"` and
  `plan.requires_human_approval` is `true`, both set by the orchestrator and
  never read from model output, with the notice stating a human must review and
  approve before any implementation work proceeds. No L2/L3 automation is
  authorized.
- [x] **Failures after a call was attempted are loud and quiet at once**: the
  after-call failure block names the endpoint host, the model, and — for
  `ModelPlannerParseError` / `ModelPlannerValidationError` /
  `ModelPlannerPolicyError` — the failure category by type name, while the raw
  model reply is never echoed (a validation error's message is withheld entirely,
  because pydantic embeds the offending input values in it).
- [x] **No audit files** are written, and no `--audit-dir` option exists.
- [x] **No other CLI behavior changed**: `generate-plan` stays offline-only with
  no `--real`/`--real-model`/`--live`/`--model`/`--use-env`/`--github`/
  `--fetch`/`--audit-dir`; `llm-smoke-test` stays fake-provider only;
  `real-llm-smoke-test` stays a smoke test with no `--issue`/`--body-file`/
  `--title`; `inspect-issue` and `version` are untouched.
- [x] **Tests never open a real socket and never read a real environment
  value**: [tests/test_cli_generate_model_plan.py](../tests/test_cli_generate_model_plan.py)
  injects a literal env mapping and an `httpx.MockTransport`-backed client into
  a private helper, monkeypatches `socket.*`/`subprocess.Popen` to raise, tracks
  every `Path.read_text` call, and drives fail-closed and help behavior through
  the CLI.
- [x] **No file editing, command execution, agent logic, implementer/reviewer/
  fixer role wiring, GitHub writes, or target project workspace access** was
  added. L2 remains out of scope.
