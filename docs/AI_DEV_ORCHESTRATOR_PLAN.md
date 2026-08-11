# AI Dev Orchestrator — Plan

> **This document is planning only. It is not an implementation and describes no
> shipped behavior.** It records intent and roadmap for future phases.

## 1. Project purpose

A **controlled** AI software development pipeline orchestrator. It is designed to
coordinate a guarded, auditable pipeline that will eventually:

- read GitHub issues,
- enforce project workspace boundaries,
- call **internal** LiteLLM models (e.g. `minimax-m2.7`, `qwen3.6-27b`),
- apply structured file changes,
- run allowlisted checks,
- produce review packets,
- support controlled automation levels.

The emphasis is on **control and review**, not autonomous action.

## 2. Current verified workflow problem

Today the **user is the message bus**: they manually shuttle context and outputs
between ChatGPT (planning), Roo / minimax (implementation), Continue / qwen
(review), and GitHub. This is slow, error-prone, and hard to audit. The
orchestrator's job is to remove the human-as-message-bus bottleneck while keeping
the human in control of approvals.

## 3. Long-term target workflow

```
GitHub issue
  → orchestrator
    → minimax implementer
    → qwen reviewer
    → review / fix loop
  → PR / CI / final review packet
```

The orchestrator drives the loop; the human reviews and approves at gated points.

## 4. Automation levels

Progressive, opt-in levels of autonomy:

- **L1 — plan only.** Produce a plan; make no changes.
- **L2 — local branch + implement + local commit.** Work on a local branch and
  commit locally; nothing is pushed.
- **L3 — push + PR.** Push the branch and open a pull request.
- **L4 — review / CI / Codex fix loop.** Run the automated review/CI/fix loop.
- **Never merge `main`.** Merging to the main branch is always a human action.

## 5. Project config requirements

Per-project configuration (no secrets in these files) describes:

- `workspace_path` — absolute root the orchestrator may operate within.
- `github_repo` — target repository.
- `branch_prefix` — prefix for orchestrator-created branches.
- `allowed_paths` — paths the orchestrator may read/modify.
- `protected_paths` — sensitive paths requiring extra review / stronger guards.
- `forbidden_paths` — paths the orchestrator must never read or modify.

## 6. AI role config requirements

Model roles must be configurable. Each role specifies:

- `implementer` — model that proposes changes.
- `reviewer` — model that reviews changes.
- `fixer` — model that addresses review findings.
- `provider` — provider for the role (internal LiteLLM by default).
- `model` — model name (e.g. `minimax-m2.7`, `qwen3.6-27b`).
- **Connection config via environment variables** — base URLs and API keys come
  from the environment, never from committed files.

## 7. MVP phase roadmap

- **Phase 0 — bootstrap.** Complete.
- **Phase 1 — config + workspace policy.**
- **Phase 2 — GitHub issue reader.**
- **Phase 3 — LiteLLM client.**
- **Phase 4 — L1 plan generator.** Complete through Phase 4L —
  [PHASE_4_L1_PLAN_GENERATOR_PLAN.md](PHASE_4_L1_PLAN_GENERATOR_PLAN.md)
  (4A docs-only, through the gated real model `generate-model-plan` command).
- **Phase 5 — docs-only L2 implementer.** Design started —
  [PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md](PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md)
  (Phase 5A docs-only; Phase 5B typed the §3 approved-plan handoff models and
  strict parser, library only; Phase 5C added the `l2-dry-run` command, which
  validates an approved plan and prints intended scope with no workspace access
  and no implementation; Phase 5D0 added the §6.4 canonical path guard as a
  library with no caller — **not** workspace inspection, and no CLI behavior;
  Phase 5D1 added the `l2-inspect-workspace` command, the first code here that
  may touch a configured target workspace and only as `stat` — path existence,
  kind, and size for an approved plan's `files_likely_to_change`, behind a
  project-level opt-in, with **no file content reads, no directory listings, no
  patch proposal, no file editing, and no command execution**; Phase 5E0 typed
  the patch proposal artifact as models plus a strict parser, library only —
  **not** patch generation, with **no diff, no file content, no workspace
  access, and no CLI behavior**; Phase 5E1 added the deterministic, offline
  generator and the `generate-patch-proposal` command, which turns an approved
  plan into a prose-only proposal artifact printed to stdout — still **no diff,
  no file content, no workspace access, no artifact file written, no file
  editing, and no command execution**; Phase 5D2 added the
  `l2-read-workspace-files` command, the first code here whose output may
  contain target workspace source — bounded, redacted contents of an approved
  plan's `files_likely_to_change`, behind a **separate** project-level opt-in
  and file-count/per-file/total byte caps, with **no directory listings, no
  diff generation, no file editing, no command execution, no model call, and
  no file content sent to a model**; Phase 5E2 typed the unified diff proposal
  artifact as models plus a strict parser, library only — a diff may now be
  carried and validated **as data**, with **no diff generation, no diff
  application, no apply-cleanliness check, no workspace access, no file content
  read, and no CLI behavior**; Phase 5E3 added the deterministic, offline
  generator and the `generate-diff-proposal` command, which turns an approved
  plan, a Phase 5D2 content packet, and a proposed-content JSON object — all
  **local files** — into unified diff text printed to stdout, with **no target
  workspace file read directly, no diff applied, no apply-cleanliness check, no
  file editing, no command execution, no artifact file written, and no model
  call**; Phase 5F0 typed the **file-edit write gate** as models plus a strict
  parser, library only — the second, separately worded human approval of one
  *concrete diff proposal*, which is never inferred from the L1 plan approval,
  from a diff proposal existing or parsing, from a file being present, from
  issue prose, or from model output, with **no file editing, no diff
  application, no apply-cleanliness check, no workspace access, no command
  execution, no model call, no branch/commit/push/PR, no artifact file written,
  no approval stamping, and no CLI behavior**; Phase 5F1 added the first
  consumer of that approval and the `l2-preview-file-edits` command, a **dry-run
  preview** that validates an approved diff proposal against the project config
  and the **lexical** Phase 1 write policy and prints what a future write phase
  *would be allowed to attempt* — permitted paths, change types, and diff
  counts, with **no diff text, no source contents, no workspace read/list/stat/
  resolve/canonicalization, no diff applied, no apply-cleanliness check, no file
  editing, no command execution, no model call, no branch/commit/push/PR, no
  artifact file written, and no approval stamping**).
  **L2 is proposed, not built**, and no command can invoke it. Nothing shipped
  so far edits a file; Phase 5F2 and the file-editing phase beyond it remain
  proposed and not authorized.
- **Phase 6 — qwen reviewer.**
- **Phase 7 — fix loop.**
- **Phase 8 — local commit.**
- **Phase 9 — push + PR.**
- **Phase 10 — CI / Codex loop.**

## 8. Status

**Planning only.** Nothing in this document is implemented here. Implementation
happens one phase at a time, under explicit prompts, with tests and human
approval.
