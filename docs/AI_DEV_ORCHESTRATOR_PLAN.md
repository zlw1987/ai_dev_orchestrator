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
- **Phase 5 — L2 implementer boundary.** Design plus, since Phase 5F2C, the
  first controlled single-file workspace write —
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
  artifact file written, and no approval stamping**; Phase 5F2A wrote the
  **first-workspace-write safety contract as design only** — the dirty-tree
  requirement met **without** command execution, canonicalization immediately
  before each write with `create` and `modify` handled differently, the exact
  authorized path set, transaction semantics and backup/rollback, and the
  stdout/stderr/exit-code contract — **implementing nothing**: no module, no
  function, no config field, no CLI command or option, no file edit, no diff
  applied, no apply-cleanliness check, no subprocess, no workspace touch, no
  model or network call, no branch/commit/push/PR, and no approval stamping);
  Phase 5F2B added the **create-aware canonical write-target guard, library
  only** — `canonicalize_write_target_under_workspace`, which validates one
  declared `modify` or `create` destination (the change type is never inferred
  from the filesystem), canonicalizes an existing destination with the Phase 5D0
  machinery or a `create` destination's **already-existing parent**, requires a
  genuine `ENOENT` established with `lstat` rather than `os.path.exists`,
  refuses a dangling link, and never permits the final component to be a symlink
  or reparse point in either `allow_symlinks` mode, with a follow-up (5F2B-FU1)
  adding write-target-only lexical rejection of NTFS alternate data streams,
  drive-relative `C:file` forms, reserved Windows device names and reserved
  characters — with **no config field, no
  CLI command or option, no caller, no directory or file created, no temp file,
  backup or journal, no diff applied, no file content read, no directory
  listing, no subprocess, no Git invocation, no model or network call, no
  environment read, and no approval stamping**, and with the result explicitly
  **not** a durable authorization to write.

  **The roadmap then changed.** After 5F2B the plan was independently reviewed
  and the project concluded that the safety philosophy was right but the
  sequencing had become imbalanced: too much generalized writer machinery was
  scheduled ahead of the first useful mutation. The old 5F2C–5F2F sequence
  (typed gate models → custom Git reader → standalone preflight → generalized
  transactional writer) was **superseded prospectively** by a minimum safe
  vertical slice — see §27 of the design doc, which supersedes §26.12 while
  preserving it as history. The rule now is: if a difficult case can safely be
  excluded from the supported input domain, prefer fail-closed refusal over
  building a generalized solution before the first useful vertical slice; and
  consume the existing safety primitives to prove the next useful capability
  before creating additional generalized ones.

  **Phase 5F2C then shipped the first controlled target-workspace write** —
  `l2-apply-approved-file-edit` (design doc §28). It applies **one** explicitly
  human-approved modification to **one** existing, Git-tracked, ordinary UTF-8
  file inside **one** wholly clean Windows Git repository whose top level is
  exactly the configured workspace root, transforming an exact approved
  pre-image into an exact approved post-image and leaving the change
  **uncommitted** for human review. To make that possible the concrete diff
  artifact was evolved to `diff-proposal.v2` / `approved-diff-proposal.v2`,
  binding `pre_image_sha256` and `post_image_sha256` per change; a **strict,
  no-fuzz** diff applier was added; a **fixed, read-only, shell-free** Git
  inspection adapter was added; and a `workspace_write` project opt-in
  (`enabled` + `max_file_bytes`, shipped disabled) gates the whole thing.
  Everything outside that narrow domain **fails closed**: no `create`, no
  delete, no rename, no second file, no protected or forbidden path, no fuzzy
  patching, no non-Windows platform, no dirty repository, no assume-unchanged or
  skip-worktree index entry, no submodule, no hard-linked or reparse-point or
  special-attribute target, no non-UTF-8 or mixed-line-ending or
  terminal-newline-less file. It runs **no project verification command** and no
  model-proposed command; the only subprocess it can cause is its own fixed Git
  plumbing. **No model call, no network call, no GitHub access, no branch, no
  commit, no push, no PR, no rollback and no journal**, and pre-write refusal
  (exit 1) is never conflated with a write whose final state could not be proved
  (exit 3).

  **Phase 5F2C-FU1** then corrected six findings from the pre-acceptance review
  of that writer, **without widening its supported domain**: `ReplaceFileW` is
  called with `dwReplaceFlags == 0` (the previously passed
  `REPLACEFILE_WRITE_THROUGH` is documented by Microsoft as *not supported*);
  temp-file cleanup is now **forbidden once the replacement call has been
  invoked**, because filename state may already have changed, so a failed
  replacement deletes, renames, restores and retries nothing and reports the
  indeterminate outcome instead; a **fail-closed Git configuration gate** now
  refuses any repository whose effective configuration could cause filter or
  helper execution or configuration indirection — the original "fixed argv plus
  `shell=False`" reasoning was **wrong**, since Git runs repository-configured
  clean/smudge/process filters from inside a fixed argv, including during
  `git status` on a clean tree, as reproduced against a real `git` binary in a
  synthetic repository; the Git gate order was changed so that nothing reading
  working-tree content runs before the configuration and index gates, and so
  gitlinks are refused **before** `status` could descend into one; the Git
  executable is resolved to an **absolute path once**, refused if inside the
  target workspace, and pinned for the run; stdout is now **bounded during
  capture** with the child killed on overflow and a watchdog on the timeout,
  with the residual resource-exhaustion limitation recorded explicitly; and the
  result schema no longer claims no file was created, since a successful write
  uses one ephemeral operational sibling temp file. **No journal, no backup, no
  rollback, and no generalized writer feature were added.**

  **L2 is still not complete.** Phase 5F2D (controlled verification) and Phase
  5F2E (reviewer integration) remain proposed and not authorized, so the
  complete implement → verify → review → human loop does not exist, and there is
  still no model-backed implementer, no commit, no push, and no PR.
- **Phase 6 — qwen reviewer.**
- **Phase 7 — fix loop.**
- **Phase 8 — local commit.**
- **Phase 9 — push + PR.**
- **Phase 10 — CI / Codex loop.**

## 8. Status

**Planning only.** Nothing in this document is implemented here. Implementation
happens one phase at a time, under explicit prompts, with tests and human
approval.
