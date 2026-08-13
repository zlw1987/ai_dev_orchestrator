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

- **Phases 0 through 5F2D: complete.** See
  [docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md)
  — read its **CURRENT STATUS** block first; older sections in that file are
  design history and some of their status claims are deliberately stale.
- **Phase 5F2C shipped the first controlled target-workspace write**, and
  Phase 5F2C-FU1 corrected six review findings against it (§28.13).
- **Phase 5F2D shipped the first controlled verification execution** (§29) —
  the first separately authorized capability here to run repository-controlled
  code — and Phase 5F2D-FU1 corrected five review findings against it (§29.13):
  a wall-clock bound that was not actually a bound, an unpinned HEAD, globally
  scoped capability claims, an unprovable `next_step`, and an overstated
  environment-forwarding claim. **Phase 5F2D-FU2** (§29.14) then corrected three
  more: an output cap that was not enforced when it was passed, an imprecise
  timeout-versus-reap-grace contract, and an overstated abandoned-reader lifetime
  claim.
- **Phase 5F2E (Reviewer Integration) is next, and is NOT AUTHORIZED.**
- **L2 is not complete.** There is no commit, no push, no PR, no branch
  creation, no reviewer/fixer wiring, and no model-backed implementer.

```text
5F2C  Controlled Single-File Writer      DONE
5F2D  Controlled Verification            DONE
5F2E  Reviewer Integration               NEXT
→ first controlled implement → verify → review → human loop
```

Do **not** insert generalized writer work between 5F2D and 5F2E.

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

### What the verifier can and cannot do

A **separate** command, `l2-verify-approved-file-edit`, executes the project's
own configured verification process. The writer has no verification flag, and
the verifier writes nothing.

- **one** already-applied approved `modify`, bound on both sides: the target's
  bytes must hash to the approved `post_image_sha256`, the **HEAD object id must
  be exactly unchanged**, and the Git-visible dirty state must be **exactly**
  that one path as an unstaged modification — before the process runs and again
  after it terminates;
- **one** command, **once**: argv is exactly
  `[configured_absolute_executable, *configured_args]`, `shell=False`, cwd is the
  canonical workspace root, stdin is `DEVNULL`, with an output bound enforced
  during capture — at the moment the cap is passed, never waiting for a buffer to
  fill, and the over-limit bytes are dropped — and a bound on **AIDO's own
  wait**. No retry, no fallback, no PATH search;
- gated by a project opt-in (`controlled_verification`, ships disabled) plus two
  explicit CLI flags. The executable must be absolute, existing, a regular file,
  and **outside** the target workspace;
- the child environment is a fixed minimal allowlist — **no** `AIDO_*`, no
  `GITHUB_TOKEN`, no credential, and no way to configure forwarding. That is a
  claim about the *environment* only: configured `args` are trusted config data
  used verbatim, and AIDO does not prove they contain no sensitive literal;
- exit **1** refused before launch, **2** ran and did not pass, **3** ran and the
  repository is no longer provably the approved state (never called "failed", and
  never repaired).

> **Controlled invocation is not sandboxed execution.** The launched process is
> not confined, and its descendants are not tracked and may still be running
> after the command returns. Never write code or documentation claiming the
> verification made no network access, touched only allowed paths, spawned no
> children, had its children terminated, could not reach credentials, or was
> side-effect free.
>
> **Scope every AIDO-owned negative claim.** Fields like `committed: false` or
> `pushed: false` must never appear unscoped — the child may have done those
> things. Use the `orchestrator_` prefix, and keep child-scoped fields as
> `"not sandboxed"` strings rather than booleans.
>
> **The timeout bounds AIDO's wait, not the child's life.** A descendant holding
> the inherited output pipe must not be able to block the reader past the
> deadline (that was the 5F2D-FU1 defect), but nothing may claim descendants were
> stopped. Stated exactly: the configured timeout bounds the execution/capture
> wait, and after it AIDO may spend at most a fixed direct-child reap grace on
> that one process handle. The abandoned reader thread and its pipe handle may
> outlive the run indefinitely — that is a documented residual limitation, **not**
> something to fix with job objects, `taskkill`, process groups, `psutil`, or
> descendant enumeration.

The L1 plan's `required_verification` is **never** command authority. Do not
split it, parse it, run it, or turn it into argv.

Do **not** add any of the following without an explicit, separate prompt: a
shell or command string; command chaining, pipelines or redirection; multiple
command profiles, command ids, or before/after hooks; retries; automated repair,
`git restore`, or any cleanup of a failed verification; environment or secret
forwarding; installation or dependency commands; a generalized command executor;
a process-tree management framework (job objects, `taskkill`, process groups,
`psutil`); or any form of sandboxing or child-effect auditing.

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
- No **command execution engine**. There is no shell anywhere, no command string,
  no chaining, no pipeline, no redirection, no install or package-manager action,
  and no model-proposed command. `required_verification` remains planner prose
  and is **never** command authority. Exactly two subprocess capabilities exist,
  and neither is a general executor: the Phase 5F2C writer's **fixed, read-only**
  Git inspection set, which is part of that writer's own correctness contract;
  and Phase 5F2D's single project-config-authorized verification invocation.
  Neither may grow into a general executor here.
- **Project verification execution exists, in exactly one narrow form.** Phase
  5F2D's `l2-verify-approved-file-edit` launches **one** absolute executable
  named by the `controlled_verification` opt-in (ships disabled), with an exact
  configured argv, once, bounded. It runs repository-controlled code by design —
  **controlled invocation, not a sandbox** — and must never claim otherwise.
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
- Any test that exercises the writer, the verifier, or Git must use a **synthetic
  repository under pytest `tmp_path`**. Never test against a real target project.
  A verification test's program must likewise be a **synthetic script written
  under `tmp_path`**, never a real project executable.

## Safety principles

- **Workspace boundary enforcement is core** to this project.
- Model roles (implementer / reviewer / fixer) must be **configurable**.
- **No external paid AI API by default.** Internal LiteLLM is the intended
  default provider; OpenAI / Anthropic / Copilot / Codex are optional, future,
  and disabled by default.
- **Secrets must only come from environment variables** — never stored in files.
