# AI Dev Orchestrator

A **controlled** AI software development pipeline orchestrator.

## Purpose

This project coordinates a guarded, auditable pipeline for AI-assisted software
changes. The eventual design will:

- read GitHub issues,
- enforce project workspace boundaries,
- call **internal** LiteLLM models (e.g. `minimax-m2.7`, `qwen3.6-27b`),
- apply structured file changes,
- run allowlisted checks,
- produce review packets,
- support controlled automation levels.

The emphasis is on **control and review**, not autonomous action.

## Current status: Phase 4K (gated real model **smoke-test** command)

Phase 4K adds `real-llm-smoke-test`, a **separate, explicitly gated
connectivity check** — and the only command in this repo that can open a real
socket. It was explicitly authorized, and that authorization covers **this
command only**.

```bash
python -m ai_dev_orchestrator real-llm-smoke-test --project-config projects/mis_project.yaml.example --model minimax-m2.7 --real-model
```

- **Real model smoke-test command only.** It checks that the configured
  endpoint answers. It is **not** a planner.
- **Explicit separate command.** `generate-plan` and `llm-smoke-test` are
  unchanged and still cannot reach a real model; using the real path means
  typing a different command.
- **Requires `--real-model`.** Without the flag it fails closed with exit 1
  before reading any environment variable, building any client, or making any
  network call.
- **Uses the Phase 4J project allowlist gate.** The project's
  `real_model_planning.enabled` must be true and `--model` must appear
  **exactly** in `allowed_models`. Those checks run *before* any
  `AIDO_LITELLM_*` value is read; only the five Phase 3B names are ever read,
  and the explicit `--model` is sent, never the environment's default model.
- **Sends a fixed, harmless smoke prompt only** — a connectivity system message
  plus "Reply with exactly: AIDO_REAL_SMOKE_OK".
- **Sends no issue text**, no file or workspace contents, and no project data.
- **Performs no planning.** No `L1Plan` is produced.
- **No GitHub fetch and no GitHub write.** There is no `--issue`, `--body-file`,
  `--github`, or `--fetch` option.
- **No file editing, no command execution, no agent logic, and no target
  workspace access.** The only file read is the config named by
  `--project-config`; the configured `repo.workspace_path` is never touched.
- **No audit files.** There is no `--audit-dir` option in this phase.
- **Loud and secret-free.** A non-suppressible warning block goes to stderr
  before the call and a matching block after it, naming the endpoint **host
  only**, the model, and the project. The API key is never printed, and the JSON
  result on stdout carries no key, no base URL, and no prompt text.
- **Tests never open a socket or read a real environment value** — they inject a
  literal env mapping and an `httpx.MockTransport`-backed client.

**Phase 4L — a real model *plan* command — remains not authorized** and is not
implemented; it stays that way unless explicitly approved.

Phase 4J before it added the **fail-closed gate** that a real model-backed
planner would have to pass, as a **library function and nothing else**
(`plan/real_model_gate.py`): `check_real_model_planning_gate(...)`,
`create_real_model_l1_plan_with_gate(...)`, `endpoint_host_from_base_url(...)`,
`build_real_model_provenance(...)`, and the typed
`RealModelPlanningGateError`. Specifically:

- **Library gate only.** It is exported from `ai_dev_orchestrator.plan`; the
  Phase 4K smoke-test command is its only caller.
- **Injected environment mapping only.** `os.environ` is **never** read;
  `load_llm_client_config_from_env(...)` is called only with the injected
  mapping, and omitting the mapping is a gate error, not a fallback to the real
  process environment.
- **Injected client only.** No `LLMClient`, no `httpx.Client`, no transport is
  ever constructed — the module does not import `httpx`, so it has no code path
  that could build one.
- **Tests use `httpx.MockTransport` only**, with literal env dicts and fake
  `.invalid` base URLs. No `AIDO_LITELLM_*` value is read from the real
  environment anywhere in the suite.
- **No real network call and no real model call** in the gate module itself.
- **No CLI behavior of its own.** Phase 4J added no command and no option; the
  command came separately, in the authorized Phase 4K above.
- **Fails closed.** An absent or disabled `real_model_planning` block is
  refused; an empty `allowed_models` permits no model even when enabled; a blank
  model is refused; and the requested model must match an allowlist entry
  **exactly** — no prefixes, no case-folding, no globs.
- **The env default model cannot select what is planned with.** A differing
  `AIDO_LITELLM_DEFAULT_MODEL` is not fatal, but the config the gate returns has
  its `default_model` pinned to the allowlisted requested model, and that model
  is what is sent.
- **No filesystem access.** `audit_dir` is validated as a **flag only** —
  refused unless the project sets `allow_prompt_audit_files` — and is never
  created, read, stat'd, resolved, or listed. **Audit file writing is not
  implemented.**
- **No secret exposure.** `endpoint_host_from_base_url(...)` reduces a base URL
  to `host` or `host:port`, dropping userinfo, path, query, and fragment; no
  error message echoes the base URL or the API key.

Phase 4I before it added the **typed `real_model_planning` config model only** —
`RealModelPlanningConfig` (`enabled`, `allowed_models`,
`allow_prompt_audit_files`) plus the `ProjectConfig.real_model_planning` field,
defaulting to disabled, holding **no** credential, endpoint, or env value, with
`extra="forbid"` rejecting keys like `api_key`, `base_url`, and `endpoint`.

Phase 4H before that was a **design review only**
([docs/PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md](docs/PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md)),
adding no runtime code. Real model-backed **planning** remains **unauthorized
and unimplemented**; the shipped planning behavior is still Phase 4D's offline
`generate-plan` and Phase 4G's fake model-backed library path, described below.

What exists today: package layout and CLI; typed project-config loading and
workspace path-policy enforcement (Phase 1); **read-only** GitHub issue
inspection that fetches one issue and parses its Markdown sections (Phase 2);
**typed LLM request/response/config models** plus an environment-driven
`LLMClientConfig` loader (Phase 3B); a **mockable, OpenAI-compatible chat
client** (`LLMClient`) that consumes those models to POST one chat completion
to an internal LiteLLM endpoint with bounded retries and typed errors
(Phase 3C); a **CLI smoke-test command**, `llm-smoke-test`, that exercises
the Phase 3C `LLMClient` end-to-end against an in-process fake provider
(Phase 3D); a **typed `L1Plan` model** (`plan/models.py`) describing the
structured, human-reviewable plan-only output shape an L1 planner produces,
with field validation only (Phase 4B); a **deterministic, offline
`FakeL1Planner` engine** (`plan/fake_planner.py`) that transforms an
already-fetched `GitHubIssue` / parsed sections / `ProjectConfig` into an
`L1Plan` (Phase 4C); a **CLI command**, `generate-plan`, that wires
Phase 2's issue parser and the Phase 4C `FakeL1Planner` together to build and
print an `L1Plan` from two local files only (Phase 4D); **typed
model-planner errors plus a pure strict-JSON output parser**
(`plan/model_planner.py`) for a model-backed planner (Phase 4F); and a **pure
prompt builder plus a fake model-backed planner** in the same module
(Phase 4G); the **fail-closed real model planning gate**
(`plan/real_model_gate.py`) described above (Phase 4J); and the **gated real
model connectivity smoke test**, `real-llm-smoke-test`, the only command that
can contact a real model (Phase 4K).

Phase 4F is **library-only and entirely offline**:
`parse_model_l1_plan_response(...)` parses strict JSON **text it is handed**
into a validated `L1Plan`. It makes **no model call**, constructs **no**
`LLMClient`, imports **no** transport (`httpx`/`MockTransport`), makes **no
network call**, reads **no** environment variable, performs **no** file IO, and
performs **no** workspace path resolution. It adds **no CLI behavior** — no new
command, no new option, and no change to `generate-plan`, `llm-smoke-test`,
`inspect-issue`, or `version`. The trusted fields (`issue_number`, `repo`,
`title`, `automation_level`, `requires_human_approval`) are never read from
model output, and output proposing forbidden behavior — command execution, file
edits, branches, PRs, GitHub writes, workspace reads, automation escalation, or
skipping human approval — is **rejected, never repaired**.

Phase 4G is a **fake model-backed library path only**. It adds
`build_model_l1_plan_request(...)`, a **pure, deterministic** prompt builder
(identical inputs produce an identical `LLMRequest`), and
`ModelBackedL1Planner`, which wires prompt builder → an **injected** chat
client → the Phase 4F parser → `L1Plan`. Specifically:

- **Fake / `MockTransport` provider only.** The planner never constructs a
  client — one is always handed to it — and its module imports neither `httpx`
  nor `LLMClient` at runtime, so it has no code path that could build a real
  one. Every test injects an `httpx.MockTransport`-backed client.
- **No real model call** and **no real network call** anywhere. No socket is
  opened by the suite.
- **No environment-variable read.** No `AIDO_LITELLM_*`, no other variable, and
  no call to `load_llm_client_config_from_env`.
- **No CLI behavior added** — no new command, no new option, and no change to
  `generate-plan`, `llm-smoke-test`, `inspect-issue`, or `version`.
- **No file, workspace, or GitHub access.** The prompt conveys the project's
  allowed/protected/forbidden path patterns and workspace policy flags as
  **patterns and names only**; target workspace file contents, directory
  listings, and the configured `repo.workspace_path` itself are never included.
- Issue text is wrapped in explicit untrusted-data delimiters and labelled as
  data to summarize, never instructions to follow; the trusted fields come from
  the caller's own objects, and `project.forbidden_paths` is merged into the
  result verbatim.

`llm-smoke-test` is **fake-provider / dry-run only**: it builds its own fake
`LLMClientConfig` and an `httpx.MockTransport` internally, reads **no**
`AIDO_LITELLM_*` (or any other) environment variables, and makes **no real
network call or real model call**.

`generate-plan` is **offline-only**: it reads only the two local files given
via `--project-config` and `--body-file`. It does not fetch the issue from
GitHub, does not call any model, does not read `AIDO_LITELLM_*` or any other
environment variable, does not read the project's configured
`repo.workspace_path`, does not edit files, does not execute commands, and
does not write to GitHub.

`real-llm-smoke-test` (Phase 4K) is the **only** command that can call a real
model, and it is a **connectivity smoke test, not a planner** — see the status
section above. Every other command remains offline: `generate-plan` has no
`--model`, `--live`, `--real`, `--github`, `--fetch`, or `--use-env` option, and
`llm-smoke-test` does have a `--model` option, but it only names the **fake**
model echoed back by the in-process mock transport — it selects nothing real and
calls no real model.

The following are intentionally **not** implemented yet:

- No CLI command that **plans** with a real model. The only real-model command
  is the Phase 4K connectivity smoke test, which sends a fixed prompt and no
  issue text.
- No **GitHub writes** (read-only issue access only — no comments, labels,
  branches, or PRs).
- No agent logic.
- No file editing or command execution.
- No reads or writes of configured **target project workspaces**.
- No agent framework (LangGraph / CrewAI / AutoGen / n8n).

## Provider policy

- **No external paid AI APIs are used by default.**
- The intended **default provider is an internal LiteLLM OpenAI-compatible
  endpoint**.
- **OpenAI, Anthropic, GitHub Copilot/Codex, and other external AI integrations
  are disabled by default** and are treated as **optional, future** integrations.
  They will only be usable when explicitly enabled.
- **No secrets in files.** Configure credentials via environment variables
  (see [`.env.example`](.env.example)); never commit a real `.env`.

## Install (dev)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
```

## Usage

```bash
python -m ai_dev_orchestrator --help
python -m ai_dev_orchestrator version
```

### Inspecting a GitHub issue (Phase 2, read-only)

```bash
python -m ai_dev_orchestrator inspect-issue --repo owner/repo --issue 1
```

Phase 2 adds **read-only** GitHub issue inspection: it fetches one issue and
reports its parsed Markdown sections (and any missing required sections). It
**does not write to GitHub**, **does not call LiteLLM**, and **does not touch
configured project workspaces**. A `GITHUB_TOKEN` is used if present
(public repos may be readable without one).

### LLM smoke test (Phase 3D, fake-provider / dry-run only)

```bash
python -m ai_dev_orchestrator llm-smoke-test
python -m ai_dev_orchestrator llm-smoke-test --model qwen3.6-27b --message "hello"
```

Phase 3D adds `llm-smoke-test`, a **dry-run smoke test** of the Phase 3C
`LLMClient`. It builds a fake `LLMClientConfig` and an `httpx.MockTransport`
in-process and sends one `LLMRequest` through the real client code path. It
**reads no environment variables**, **makes no real network call**, and
**never calls a real model** — the response is a deterministic fake generated
locally. Output states clearly that it is a dry-run, that no real model was
called, and reports the model name, response content, and token usage.

### Generating an L1 plan (Phase 4D, offline only)

```bash
python -m ai_dev_orchestrator generate-plan \
  --project-config projects/mis_project.yaml.example \
  --repo zlw1987/mis_project \
  --issue 42 \
  --title "Add currency formatting helper" \
  --body-file path/to/local/issue_body.md
```

Phase 4D adds `generate-plan`, an **offline-only** CLI command. It reads
**only the two local files explicitly given**: the `--project-config` YAML
and the `--body-file` issue body text. It parses the body with the Phase 2
`parse_issue_body`, builds a synthetic in-memory `GitHubIssue` from
`--repo`/`--issue`/`--title`/the body file, loads the project config with the
existing config loader, and calls the Phase 4C `FakeL1Planner` to produce an
`L1Plan`, printed as deterministic pretty JSON.

`generate-plan` **does not**:

- fetch the issue from GitHub (no network call at all),
- call any model (fake or real) — it has no `--model`, `--live`, `--real`,
  `--github`, `--fetch`, or `--use-env` option,
- read `AIDO_LITELLM_*` or any other environment variable,
- read the project's configured `repo.workspace_path` or any target project
  workspace,
- edit files, execute commands, or write to GitHub.

A `--body-file` that **is** the configured `repo.workspace_path` or sits
**under** it is rejected with exit code 1 before the file is read. The check
is string/path normalization only — the configured workspace path is treated
as an opaque string and is never read, listed, stat'd, or resolved on disk.

The printed output always includes `automation_level: "L1"` and
`requires_human_approval: true`, plus a `notice` field stating that it is a
plan-only artifact, not executable instructions, and requires human review
and approval before any implementation work proceeds.

### Real model smoke test (Phase 4K, gated — opens a real socket)

```bash
python -m ai_dev_orchestrator real-llm-smoke-test \
  --project-config projects/my_project.yaml \
  --model minimax-m2.7 \
  --real-model
```

Phase 4K adds `real-llm-smoke-test`, the **only** command that can contact a
real model. It is a **connectivity check, not a planner**: it sends a fixed,
harmless prompt ("Reply with exactly: AIDO_REAL_SMOKE_OK") and prints what came
back. It requires **both** the explicit `--real-model` flag **and** a project
config whose `real_model_planning` block sets `enabled: true` and lists
`--model` in `allowed_models` — either alone is not enough.

In order, before anything leaves the machine: the flag is checked, the config is
loaded, the project opt-in and the model allowlist are enforced, **then** the
five `AIDO_LITELLM_*` variables are read, **then** a warning block naming the
endpoint host, model, and project is written to stderr, and only then is a real
client built. Any failure before the call exits non-zero with nothing on stdout.

`real-llm-smoke-test` **does not**:

- send issue text, file contents, workspace contents, or project data — the
  prompt is fixed and the only variable part of the request is the model name,
- fetch anything from GitHub or write anything to GitHub — it has no `--issue`,
  `--body-file`, `--github`, or `--fetch` option,
- generate a plan, edit files, execute commands, or run agent logic,
- read the project's configured `repo.workspace_path` or any target project
  workspace — the only file it reads is the `--project-config` YAML,
- write prompt/completion audit files — there is no `--audit-dir` option,
- print the API key or the full base URL — the endpoint is reported as a
  **host** only, in both the stderr banner and the stdout JSON.

The explicit `--model` value is what gets sent; `AIDO_LITELLM_DEFAULT_MODEL`
supplies connection defaults and can never select the model. On success the JSON
on stdout carries `provenance.engine: "real-model"`,
`provenance.operation: "smoke-test"`, `real_call: true`, the model, the endpoint
host, the project id, the response content, and token usage.

## Tests

```bash
pytest
```

## Configuration

Per-project workspace boundaries are described by YAML files under `projects/`.
See [`projects/mis_project.yaml.example`](projects/mis_project.yaml.example) for
the expected shape. These files describe boundaries only — they contain **no
secrets**.

## Next phase

Phase 4 adds an **L1 plan generator**
([docs/PHASE_4_L1_PLAN_GENERATOR_PLAN.md](docs/PHASE_4_L1_PLAN_GENERATOR_PLAN.md)).
Phase 4A was a design doc only; Phase 4B added the typed `L1Plan` model with
validation; Phase 4C added the deterministic, offline `FakeL1Planner` engine;
Phase 4D added the offline `generate-plan` CLI command described above.

Phase 4E was a design review only — see
[docs/PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md](docs/PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md),
which describes how an optional, explicitly-gated model-backed planner *could*
work in a future phase. Phase 4F then implemented the offline half of that
design — the typed planner errors and the strict output parser described above.
Phase 4G completed the fake path: the pure prompt builder and
`ModelBackedL1Planner`, exercised through the real `LLMClient` code path with
an injected `httpx.MockTransport`. Neither added a runtime real-model call or
any CLI behavior; the shipped CLI behavior is still Phase 4D's offline
`generate-plan`.

Phase 4H was a design review only — see
[docs/PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md](docs/PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md),
which specifies the fail-closed gate a future *real* model planner would need:
opt-in only and never default, a separate command rather than a `--real` flag
on `generate-plan`, a project-local `real_model_planning` allowlist, a
non-suppressible warning naming the endpoint host and model (never the API key),
`GitHubIssue` / `ParsedIssue` / `ProjectConfig` as the only inputs, explicit
engine provenance as wrapper metadata around `L1Plan`, and no silent fallback in
either direction. Phase 4H added **no runtime code, no CLI behavior, no model
call, no network call, and no environment-variable read**.

Phase 4I then typed the `real_model_planning` block described in that design —
config shape only, defaulting to disabled, with no env read, no CLI behavior, no
real model call, no network call, and no gate function. Phase 4J then
implemented that design's §3.4 preconditions and §10 failure taxonomy as the
**library gate** described in the status section above: injected env mapping,
injected client, `httpx.MockTransport` in tests only, and **no real network
call, no real env read, and no CLI behavior**.

Phase 4K then added the **explicitly authorized** real model *smoke-test*
command described in the status section above — the first code here permitted to
open a real socket, and only for a fixed connectivity prompt behind the full
gate.

Next would be **Phase 4L**: a gated real model *plan* command, which remains
**proposed and not authorized** and will not be built unless explicitly
approved. Phase 4K's authorization does not extend to it. Until then, real
model-backed **planning** stays off everywhere, and the project continues to
avoid agent automation, file editing, command execution, GitHub writes, and
target project workspace reads/writes unless explicitly authorized in a later
sub-phase.
