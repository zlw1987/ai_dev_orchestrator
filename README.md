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

## Current status: Phase 4D (L1 plan generator — offline CLI command)

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
`L1Plan` (Phase 4C); and a **CLI command**, `generate-plan`, that wires
Phase 2's issue parser and the Phase 4C `FakeL1Planner` together to build and
print an `L1Plan` from two local files only (Phase 4D).

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

There is currently **no CLI command that can call a real model.**
`generate-plan` has no `--model`, `--live`, `--real`, `--github`, `--fetch`,
or `--use-env` option. `llm-smoke-test` does have a `--model` option, but it
only names the **fake** model echoed back by the in-process mock transport —
it selects nothing real and calls no real model.

The following are intentionally **not** implemented yet:

- No CLI command that calls a real model (by design — see above).
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

**Phase 4E is complete and was a design review only** — see
[docs/PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md](docs/PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md),
which describes how an optional, explicitly-gated model-backed planner *could*
work in a future phase. It added **no runtime code, no CLI option, no model
call, no network call, and no environment-variable read**; the shipped runtime
behavior is still Phase 4D's offline `generate-plan`.

Next is **Phase 4F — typed prompt/output parser errors only**, still with no
model call. Any real model-backed planning remains off by default and behind
its own future authorization (proposed Phase 4H), continuing to avoid agent
automation, file editing, command execution, GitHub writes, and target project
workspace reads/writes unless explicitly authorized in a later sub-phase.
