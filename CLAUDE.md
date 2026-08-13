# CLAUDE.md

This file is the **operating guide for Claude Code** in this repository. Read it
before doing any work here.

## Workspace boundary

- **Allowed:** `C:\dev\ai_dev_orchestrator` — operate only inside this folder.
- **Forbidden** (do not read, search, list, or modify):
  - `C:\dev\mis_project`
  - `C:\dev\a8_oa`
  - `C:\dev\bible_reading_v2`
  - any parent directory above `C:\dev\ai_dev_orchestrator`

## Current phase

- **Phases 0 through 5F2C: complete.** See
  [docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md)
  — read its **CURRENT STATUS** block first; older sections in that file are
  design history and some of their status claims are deliberately stale.
- **Phase 5F2C shipped the first controlled target-workspace write**, and
  Phase 5F2C-FU1 corrected six review findings against it (§28.13).
- **Phase 5F2D (Controlled Verification) is next, and is NOT AUTHORIZED.**
- **Phase 5F2E (Reviewer Integration) is NOT AUTHORIZED.**
- **L2 is not complete.** There is no commit, no push, no PR, no branch
  creation, and no model-backed implementer.

### What the writer can and cannot do

One command, `l2-apply-approved-file-edit`, writes a file. It is deliberately
narrow, and the narrowness is the design — not a gap to fill in:

- **one** file per invocation, **`modify` only**, on an existing Git-tracked
  ordinary UTF-8 file, in a **wholly clean Windows Git repository** whose top
  level is exactly the configured workspace root;
- gated by a project opt-in (`workspace_write`, ships disabled) plus two
  explicit CLI flags plus an exactly-worded human approval of the concrete diff;
- the diff is applied **exactly** — no fuzz, no offset search, no repair — and
  both the pre-image and post-image are pinned by SHA-256;
- everything outside that domain **fails closed**.

Do **not** add any of the following without an explicit, separate prompt: file
creation, deletion or renaming; multi-file writes; protected-path writes; a
transaction framework; a journal; rollback; crash recovery; a concurrency
framework; or a generalized Git executor.

## Role split

- **ChatGPT** = architect / planner / reviewer / prompt writer.
- **Claude Code** = implementation tool for this orchestrator project.
- Claude Code **must not broaden scope** beyond the current prompt. Do exactly
  what the active task asks — no speculative extras.

## Current non-goals

None of the following are implemented, and none may be added unless a future
prompt explicitly asks:

- No **GitHub writes**. Read-only issue inspection exists; nothing posts,
  labels, branches, commits, pushes, or opens a PR.
- No **general file editing engine**. The Phase 5F2C writer applies **one**
  approved `modify` diff to **one** tracked file and refuses everything else; it
  is not a general editor and must not grow into one here.
- No **command execution engine**. `required_verification`, pytest, npm, make,
  build scripts and model-proposed commands are all unreachable. The only
  subprocess capability in the repository is the writer's **fixed, read-only**
  Git inspection set, which is part of that writer's own correctness contract —
  it is not a general executor and must not become one.
- No **project verification execution**. That is Phase 5F2D, and it is not
  authorized.
- No **agent logic**, and no reviewer/fixer role wiring.
- No LangGraph / CrewAI / AutoGen / n8n (no agent framework).

Real LiteLLM calls exist only behind the two explicitly gated commands
(`real-llm-smoke-test`, `generate-model-plan`); nothing else may call a model,
and no model output may ever select a path, a command, or an executable.

## Coding discipline

- One phase at a time.
- Do not implement future phases early.
- Tests are required for implementation phases.
- **Do not commit or push unless the user explicitly asks.** The user handles
  git commit and push manually.
- Prefer **fail-closed refusal of an unsupported case** over generalizing (see
  the design doc §27). Rejecting an input is a legitimate, preferred answer.
- Any test that exercises the writer or Git must use a **synthetic repository
  under pytest `tmp_path`**. Never test against a real target project.

## Safety principles

- **Workspace boundary enforcement is core** to this project.
- Model roles (implementer / reviewer / fixer) must be **configurable**.
- **No external paid AI API by default.** Internal LiteLLM is the intended
  default provider; OpenAI / Anthropic / Copilot / Codex are optional, future,
  and disabled by default.
- **Secrets must only come from environment variables** — never stored in files.
