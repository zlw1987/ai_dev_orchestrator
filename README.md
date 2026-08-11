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

## Current status: Phase 5F2A (design only) — latest shipped capability is still Phase 5F1, and nothing writes a target file

**Phase 5F2A is the latest completed phase, and it is design only**: it added
documentation and no code (see §26 of the design doc, and the note further down
this section). **Phase 5F1 remains the latest shipped runtime capability**, and
nothing in this repository can write a file into a target workspace.

Phase 5F0 typed the human approval a future file-editing phase would have to be
handed, and shipped nothing that consumes it. Phase 5F1 is the first consumer:
`build_file_edit_preview`, plus **one** new command, `l2-preview-file-edits`. It
validates one approved diff proposal against a project config and the **lexical**
Phase 1 write policy, and prints what a future write phase *would be allowed to
attempt*.

**This is not file editing.** It is not diff application, not an
apply-cleanliness check, not command execution, and not L2. A preview is a
description of a hypothetical, produced without touching the thing it describes.

- **It establishes three things.** That the Phase 5F0 approval is a real,
  exactly-worded file-edit approval of one concrete diff proposal; that the
  artifact is **this project's**, matched by exact string equality in all six
  places it records identity; and that every path it names passes the lexical
  `PathPolicy` **write** check, with no duplicates and a change count inside
  `workspace_policy.max_changed_files`.
- **It leaves everything else unknown, on purpose.** Whether any of those paths
  exists, what it currently contains, whether its canonical form resolves back
  inside the workspace root, and whether the diff would apply are all
  unanswered — because answering them means touching a target workspace. The
  report says so, `canonicalization_checked: false` included.
- **Protected paths are refused outright**, and there is no `--allow-protected`
  flag: permitting a protected write is a decision for a phase that actually
  writes. A forbidden, unlisted, traversal-escaping, or protected path fails the
  **whole** preview — `policy_result` is `"allowed"` and has no other member, so
  a report either describes a fully permitted change set or does not exist.
- **A diff is summarized as counts, never reprinted.** Bytes, lines, hunks,
  added, removed, context — computed by scanning the string the artifact already
  carried. `difflib` is not imported, the `--- `/`+++ ` headers are excluded from
  the added and removed counts, and nothing is normalized.
- **Empty changes are valid**: `paths_count` is 0 and a future phase would
  attempt no write.
- **No field exists** for unified diff text, source contents, an approval text,
  raw artifact text, a workspace path, a resolved absolute path, a command or its
  output, an apply result, an API key, a base URL, a branch, a commit, or a PR
  URL. The only branch/commit/push/PR mentions in the output are the `false`
  flags recording that none of them happened.
- **No workspace read, list, stat, glob, walk, resolve, or canonicalization, no
  file opened beyond the two named on the command line, no diff applied, no
  apply-cleanliness check, no file editing, no command execution, no model call,
  no network call, no environment read, no GitHub fetch or write, no branch,
  commit, push or PR, no artifact file written, and no approval stamping.**

**L2 is still not built.** A preview authorizes nothing.

**Phase 5F2A has since been completed as a design-only phase** — the safety
contract the first workspace-write phase would have to satisfy, written before
any writer exists. It **implements nothing**: no module, no function, no config
field, no CLI command, no CLI option, and no change to any shipped behavior. It
resolves the dirty-tree-check versus no-command-execution conflict (a
non-subprocess Git-state probe in its own prerequisite phase, with a fail-closed
tri-state verdict and no human attestation substitute), pins canonicalization
immediately before each write with `create` and `modify` handled differently,
freezes the authorized path set to the approved diff's own paths, defines
transaction semantics and backup/rollback, and splits the old single "Phase 5F2"
slot into 5F2B–5F2F. **Phase 5F2B, 5F2C, 5F2D, 5F2E and 5F2F all remain proposed
and not authorized**, and **nothing shipped in this repository edits a target
file.**

See
[docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md §25 and §26](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md)
and the usage section below.

### Phase 5F0 (file-edit write gate models and parser — library only)

Phase 5E3 generates a concrete diff proposal and prints it. Nobody has read it.
Phase 5F0 adds the `ai_dev_orchestrator.file_editing` package: typed models for
the **explicit human approval** any future file-editing phase would have to be
handed before writing a single byte into a target workspace, plus a strict JSON
parser. It adds **no command and no option**.

**This is not file editing.** It is not diff application, not an
apply-cleanliness check, not command execution, and not L2. There is no writer,
no applier, and no editor here — only a schema and a pure parser.

- **A second, separate approval.** Phase 5B's approval covers an *L1 plan* — a
  summary, a scope, a list of files that may change. Phase 5F0's covers the
  *concrete diff* generated from it, which the human had not seen when they
  approved the plan. The required sentence is a different one, matched with
  `==`:

  ```
  I approve this diff proposal for workspace file editing
  ```

  A paraphrase, a case variant, padded whitespace, trailing punctuation, and
  the Phase 5B plan sentence are all **not** approval.
- **Approval is never inferred** — not from the wrapped L1 plan approval (which
  is valid and approves something else), not from a diff proposal existing,
  parsing, or setting `requires_human_review` (which *requests* review and never
  records that it happened), not from a file being present, not from issue prose
  or an `Automation Authorization` heading, and not from model output. Nothing
  here stamps an approval: writing the block **is** the approval act.
- **The wrapped diff proposal is an untouched snapshot**, re-validated on every
  parse, and every invariant it already guarantees is **re-checked here** — the
  L1 level and human-approval requirement, `requires_human_review` and
  `diffs_generated` true, `files_edited` / `commands_run` /
  `applies_cleanly_checked` false, no duplicate paths, and every path exactly
  inside the approved plan's `files_likely_to_change` and outside its
  `files_forbidden_or_out_of_scope`. A write gate does not inherit its safety
  from a model it does not own, and pydantic does not re-validate an instance it
  is handed — so a mutated or hand-built object is checked again.
- **Identity is matched exactly**, in both directions: against the proposal's
  provenance and against the approved plan nested inside it. String equality
  only, so an approval given for one issue cannot be carried into another.
- **This does not prove a diff applies.** `applies_cleanly_checked` must still
  be false, because nobody asked. It does not authorize command execution, and
  it does not authorize commits, pushes, or PRs.
- **No field exists** for raw artifact text, source contents outside a diff,
  `before_content`/`after_content`, a prompt, a completion, an API key, a base
  URL, a workspace path, a command or its output, an apply result, `auto_apply`,
  a branch name, a commit id, or a PR URL. Each is rejected as an extra.
- **No file editing, no diff application, no apply-cleanliness check, no
  workspace access, no command execution, no model call, no network call, no
  environment read, no GitHub fetch or write, no branch, commit, push or PR, no
  agent logic or role wiring, no artifact file written, and no CLI behavior.**

**L2 is still not built**, and nothing here can invoke it. A parsed artifact is
data describing an approval — never permission to do anything. Phase 5F1 has
since added the **dry-run preview** described above, which reads such an
artifact and still edits nothing; **file editing** remains unauthorized.

See
[docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md §24](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md).

### Phase 5E3 (deterministic diff proposal generator — diff text, never applied)

Phase 5E3 adds the producer Phase 5E2 withheld:
`build_deterministic_diff_proposal`, plus **one** new command,
`generate-diff-proposal`. It is a pure function over four already-loaded objects
that runs `difflib` over strings and returns a validated Phase 5E2 artifact, and
a command that loads those objects from four **local files** and prints the
result to stdout.

The four inputs are the whole story, and **none of them is a workspace**: the
project config, a human-approved L1 plan artifact, a Phase 5D2
`l2-read-workspace-files` packet (which carries bounded, redacted original file
text as *data*), and a proposed-content JSON object giving each path's final
text.

- **It generates diff text and does nothing with it.** Nothing is applied,
  staged, or written, and **whether a diff would apply is never checked** —
  `applies_cleanly_checked` is false because the question was never asked. No
  patch tooling is invoked.
- **It reads no target workspace file directly.** The paths the approved plan
  names are never opened, stat'd, listed, globbed, walked, or resolved. Original
  text arrives inside the packet or the generation for that path **fails**.
- **Redacted source fails closed.** Phase 5D2 replaces secret-like values with a
  placeholder, so a diff built from redacted text would describe a file that
  does not exist. A misleading patch is worse than no patch.
- **A secret-like generated diff is refused, not redacted.** Redacting a diff
  would produce text that reads like a patch and could never apply, so the whole
  generation fails instead. The error names the category and the path and never
  echoes the value or the diff.
- **A no-op change is omitted, never fabricated.** A `modify` whose proposed text
  already matches the recorded original goes into `omitted_paths` instead of
  becoming an invented diff. `changes` may be empty, which is well-formed.
- **A `modify` needs a real read.** Missing, directory, too-large, binary, and
  skipped items cannot be modified; a `create` needs a `missing` item and is
  refused over a file that was actually read.
- **Scope only narrows.** Every proposed path must appear exactly in the approved
  plan's `files_likely_to_change`, must not appear in
  `files_forbidden_or_out_of_scope`, and must appear in the packet. Identity is
  matched by exact string equality against both the config and the packet.
- **Deterministic.** `generated_at` is `null`, provenance is
  `engine: "deterministic"` / `real_call: false` / `model: null`, and the same
  inputs always produce a byte-identical artifact. stdout is the artifact itself
  with no wrapper, so it parses with `parse_diff_proposal_artifact`.
- **No diff applied, no apply-cleanliness check, no file editing, no command
  execution, no artifact file written, no model call, no network call, no
  environment read, no GitHub fetch or write, no agent logic or role wiring, and
  no approval stamping.**

**L2 is not built, and this command is not it.** It writes a diff to stdout for
a human to read. Nothing shipped so far edits a file.

See
[docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md §23](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md)
and the usage section below.

### Phase 5E2 (unified diff proposal artifact models and parser — library only)

Phase 5E2 adds the `ai_dev_orchestrator.diff_proposal` package: typed models for
a **unified diff proposal artifact** plus a strict JSON parser. It lets a
diff-shaped artifact **exist as data** and be validated. It added **no command
and no option** of its own; Phase 5E3 above later added the producer and the one
command that prints its output.

- **This is not diff generation, and not diff application.** The parser half has
  no producer and no applier. Nothing in `models.py` creates, computes, or
  modifies a diff, and nothing anywhere applies, stages, or writes a patch — a
  parsed diff was written elsewhere. `applies_cleanly_checked` is
  `Literal[False]`: whether a diff *would* apply is a question **no** phase
  shipped so far asks, because asking it means touching a workspace. No patch
  tooling is invoked, and `difflib` is not imported by the parser.
- **A `unified_diff` field now exists, and may contain source lines as diff
  context** — that is what a diff is, and it is allowed **as data** in this
  artifact. It arrived in the text handed to the parser: nothing here opened a
  file to obtain it, and nothing here sends it anywhere. There is deliberately
  no separate `before_content`, `after_content`, `file_contents` or
  `source_contents` field — source text lives inside the diff or nowhere.
- **The accepted diff shape is deliberately narrow.** One single-file textual
  diff per change: exactly `--- a/<path>` and `+++ b/<path>` for a `modify`,
  exactly `--- /dev/null` and `+++ b/<path>` for a `create`, headers naming the
  change's own path exactly, and at least one `@@` hunk. Multi-file patches,
  `diff --git` envelopes, binary patches, renames, deletions, mode changes, NUL
  bytes, and payloads over 200 000 characters are all **rejected**. Line endings
  are never normalized, and the diff is carried through byte for byte.
- **It reads no file contents and touches no workspace.** Paths are validated as
  *strings*, lexically — relative only, no traversal, no absolute or UNC or
  device form, no trailing dot or space, no 8.3-like component. Nothing is
  joined to a workspace root, canonicalized, stat'd, or opened.
- **A proposal may narrow the approved scope, never widen it.** Every proposed
  path must appear exactly in the approved plan's `files_likely_to_change` and
  must not appear in `files_forbidden_or_out_of_scope`. Duplicate paths are
  rejected rather than merged.
- **A proposal cannot authorize itself.** It wraps an untouched approved-plan
  artifact, re-validated on every parse, and its provenance must match that plan
  exactly on `project_id`, `repo`, `issue_number` and `title`. It may optionally
  wrap the Phase 5E0 prose proposal the diffs were drafted from — which must then
  agree on the approved plan and on identity, and must already have named every
  path a diff touches.
- **`files_edited`, `commands_run` and `applies_cleanly_checked` must all be
  false**, `diffs_generated` must be true, and `requires_human_review` must be
  true. These are the *shape* of a legal artifact, not observations.
  `source_contents_read` is a recorded **claim** by whatever produced the
  artifact — the parser reads nothing either way.
- **`engine: "model"` is a recorded claim, not an instruction.** Parsing it calls
  nothing. A `deterministic` or `manual` engine must carry no model name and
  `real_call: false`.
- **Strict, never repairing.** Markdown fences (including a ```` ```diff ````
  block), prose around the JSON, arrays, numbers, booleans and `null` are
  rejected; unknown fields are never stripped and missing fields are never
  inferred. Error messages name fields, never the diff.
- **No model call, no network call, no environment read, no GitHub fetch or
  write, no command execution, no file editing, no file loading, no branch,
  commit, push or PR, no agent logic or role wiring, and no approval stamping.**

See
[docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md §22](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md).

### Phase 5D2 (bounded read-only file-content inspection)

Phase 5D2 adds **one** command, `l2-read-workspace-files`. Phase 5D1 answered
*does this path exist and how big is it*; this answers the strictly larger
question *what does it say*, and is the **first command whose output may
contain target workspace source**.

```bash
python -m ai_dev_orchestrator l2-read-workspace-files --project-config projects/my_project.yaml --approved-plan path/to/approved_plan.json --apply-approved-plan --read-contents
```

- **L2 is still not built.** This command diffs nothing, patches nothing, edits
  nothing, runs nothing, and commits nothing. It reads and prints.
- **It needs its own project opt-in**, `read_only_workspace_content.enabled`,
  which ships **disabled** and is **separate** from Phase 5D1's metadata
  opt-in: agreeing that a project's path names may be stat'd is not agreeing
  that its source may be printed. While disabled, the command refuses to touch
  the workspace at all — it fails before the approved-plan artifact is opened.
- **The read is bounded three ways**: `max_files` distinct candidates (default
  10, checked before the workspace is touched), `max_file_bytes` per file
  (default 50 000), and `max_total_bytes` across the run (default 200 000). The
  per-file cap is enforced at the read itself, so a file that grows between the
  `stat` and the open is still refused.
- **Redaction is mandatory and cannot be turned off.** Every byte printed
  passes through basic secret-like redaction — `Bearer <token>`,
  `api_key`/`token`/`secret`/`password`/`passwd`/`pwd` assignment values, and
  `sk-…` keys — and the output reports `redacted`, `redaction_count` and
  `redaction_kinds`. There is no config field and no flag that disables it.
  It is a deterministic backstop, **not** reliable secret detection.
- **It reads only what the plan named.** Candidates come from the approved
  plan's `files_likely_to_change` and nowhere else, deduplicated preserving
  order. `files_forbidden_or_out_of_scope` is never read, and `proposed_steps`,
  `required_verification`, `risks` and `open_questions` are prose that is never
  treated as a path.
- **It lists no directory.** No `listdir`, no `scandir`, no `walk`, no glob, no
  tree walk. A candidate that *is* a directory is reported as
  `directory_no_content` and its entries are neither enumerated nor named.
- **It generates no diff and edits nothing.** No unified diff, no hunk, no
  patch, no before/after pair, and no write to any target workspace.
- **It calls no model, and sends no content to one.** What it reads goes to
  stdout, redacted, and nowhere else. No socket, no environment read, no GitHub
  fetch or write, no command execution, no branch/commit/push/PR, no agent
  logic or role wiring, and no approval stamping.
- **It fails closed in order**, all before the workspace is touched:
  `--apply-approved-plan`, then `--read-contents` (missing either reads no file
  at all — not even the config), then the config, then the content opt-in, then
  a string check rejecting an `--approved-plan` inside the workspace *before* it
  is read, then the strict artifact parse, then exact `project_id`/`repo`
  matching, then the candidate caps, then the lexical path policy for **every**
  candidate. One refused path abandons the whole run. Only then does the Phase
  5D0 canonical guard run. Missing, oversize, over-budget, directory and
  binary/non-UTF-8 candidates are reported with a null `content_text` and the
  run continues; a containment, symlink, ambiguity or resolution failure stops
  everything with empty stdout.
- **Output omits** the configured `workspace_path`, every resolved absolute
  path, the raw artifact text, `approval_text`, `required_verification`, any
  diff, any command output and any credential. File content appears in exactly
  one place: `workspace_content.items[].content_text`.
- **No other command changed.** `version`, `inspect-issue`, `llm-smoke-test`,
  `generate-plan`, `real-llm-smoke-test`, `generate-model-plan`, `l2-dry-run`,
  `l2-inspect-workspace` and `generate-patch-proposal` are exactly as they were.

See
[docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md §21](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md).

### Phase 5E1 (deterministic patch proposal generator — prose only, no diff)

Phase 5E1 added the one thing Phase 5E0 deliberately withheld: a **deterministic,
offline generator** that turns an approved L1 plan into a patch **proposal**
artifact, plus **one** command, `generate-patch-proposal`, that prints it.

```bash
python -m ai_dev_orchestrator generate-patch-proposal --project-config projects/my_project.yaml --approved-plan path/to/approved_plan.json --apply-approved-plan --generate-proposal
```

- **This is not a diff and not file editing.** The artifact carries no unified
  diff, no patch, no hunk, no edit script, no command, no command output, and no
  file content or before/after text. Each change is a path, a rationale, and
  prose steps for a **human**. There is nothing applyable in it.
- **It reads no file contents and touches no workspace.** No target workspace is
  read, listed, stat'd, globbed, walked, or resolved. Paths stay strings and are
  never joined to a workspace root or canonicalized.
- **It writes no file.** The proposal goes to **stdout only**, with no wrapper
  around it, so the output parses with `parse_patch_proposal_artifact`. There is
  no `--output` option.
- **It calls no model.** The generator is a pure function over two already-loaded
  objects. Its provenance records `engine: "deterministic"`, `real_call: false`,
  `model: null`, and `generated_at: null` — the same inputs always produce a
  byte-identical artifact.
- **It proposes less than the plan allowed, never more.** Candidates come from
  the approved plan's `files_likely_to_change` and nowhere else, deduplicated
  preserving order. `files_forbidden_or_out_of_scope` is never a candidate, and
  `proposed_steps`, `required_verification`, `risks` and `open_questions` are
  prose that is never read as a path. Every path is `change_type: "modify"`,
  because nothing was stat'd or opened to establish otherwise — recorded as an
  assumption in the artifact rather than guessed at.
- **It fails closed**: on a `project_id`/`repo` mismatch against the project
  config (exact string equality, no case folding), on a plan that is not an
  unescalated L1 plan, on a plan naming a path as both likely-to-change and
  forbidden, on more distinct paths than `workspace_policy.max_changed_files`
  allows, and on any unsafe path. Failures exit non-zero with stderr only,
  nothing on stdout, and never echo the artifact text or the plan prose.
- **It cannot authorize itself.** The proposal wraps the untouched approved-plan
  artifact, so the human approval travels with the thing it approved and is
  re-validated, never authored.
- **No GitHub fetch or write, no environment read, no socket, no command
  execution, no file editing, no branch, commit, push or PR, no agent logic or
  role wiring, and no approval stamping.**
- **No other command changed.** `version`, `inspect-issue`, `llm-smoke-test`,
  `generate-plan`, `real-llm-smoke-test`, `generate-model-plan`, `l2-dry-run`
  and `l2-inspect-workspace` are exactly as they were.

See
[docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md §20](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md).

### Phase 5E0 (patch proposal artifact models and parser — library only)

Phase 5E0 added the `ai_dev_orchestrator.patch_proposal` package: typed models
for a **patch proposal artifact** plus a strict JSON parser, and no producer.

- **The artifact carries no diff.** No unified diff, no patch, no hunk, no edit
  script, no command, and no file content or before/after text. A change is a
  path, a rationale, and prose steps for a **human**. There is nothing applyable
  in it, so it cannot be applied by mistake.
- **It reads no file contents and touches no workspace.** Paths are validated as
  *strings*, lexically — relative only, no traversal, no absolute or UNC or
  device form, no trailing dot or space, no 8.3-like component. Nothing is
  joined to a workspace root, canonicalized, stat'd, or opened.
- **A proposal may narrow the approved scope, never widen it.** Every proposed
  path must appear exactly in the approved plan's `files_likely_to_change` and
  must not appear in `files_forbidden_or_out_of_scope`. Duplicate paths are
  rejected rather than merged.
- **A proposal cannot authorize itself.** It wraps an untouched approved-plan
  artifact, re-validated on every parse, and its provenance must match that plan
  exactly on `project_id`, `repo`, `issue_number` and `title`.
- **`file_contents_read`, `files_edited` and `commands_run` must all be false**,
  and `requires_human_review` must be true. These are the *shape* of a legal
  artifact, not observations: a payload claiming otherwise is rejected.
- **`engine: "model"` is a recorded claim, not an instruction.** Parsing it
  calls nothing. A `deterministic` or `manual` engine must carry no model name
  and `real_call: false`.
- **Strict, never repairing.** Markdown fences, prose around the JSON, arrays,
  numbers, booleans and `null` are rejected; unknown fields are never stripped
  and missing fields are never inferred.
- **No model call, no network call, no environment read, no GitHub fetch or
  write, no command execution, no file editing, no file loading, no branch,
  commit, push or PR, no agent logic or role wiring, and no approval stamping.**

See
[docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md §19](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md).

### Phase 5D1 (read-only workspace metadata inspection)

Phase 5D1 adds **one** command, `l2-inspect-workspace`. It is the **first
command here that may touch a configured target workspace**, and the touch it
makes is the smallest one available: for each path an approved plan lists under
`files_likely_to_change`, it canonicalizes the path against the workspace root
and calls `stat`, reporting whether the path exists, whether it is a file or a
directory, and how large a regular file is.

- **L2 is still not built.** This command proposes nothing, patches nothing,
  edits nothing, runs nothing, and commits nothing. It is `l2-dry-run` plus one
  question: *do the paths in this plan actually exist, and how big are they?*
- **It reads no file contents.** No workspace file is opened or read. Checking
  that `src/foo.py` exists and checking what `src/foo.py` says are different
  disclosures, and only the first is shipped.
- **It lists no directory.** A candidate that *is* a directory is reported as
  one and its entries are never enumerated. Nothing globs, and nothing walks a
  tree — candidates come from the approved plan, one string at a time.
- **Off by default, per project.** A new `read_only_workspace_inspection` block
  gates it, and an absent block is identical to a disabled one. While it is
  disabled the command refuses to touch the workspace at all, failing before the
  approved-plan artifact is even opened. The example config ships it disabled.
- **Two explicit flags are required**, `--apply-approved-plan` and
  `--inspect-workspace`. Approving a plan and permitting a workspace to be
  examined are separate consents; without either, the command exits non-zero
  having read nothing at all.
- **The workspace is touched last.** Both flags, the project opt-in, the
  approved-plan-outside-the-workspace check, the strict artifact parse, exact
  `project_id`/`repo` matching, the `max_inspected_files` and
  `max_changed_files` caps, and the lexical Phase 1 path policy for **every**
  candidate all pass first. One refused path abandons the whole run — there is
  no partial inspection.
- **Only `files_likely_to_change` is inspected.**
  `files_forbidden_or_out_of_scope` is not, and `proposed_steps`,
  `required_verification`, `risks` and `open_questions` are prose that is never
  treated as a path.
- **The Phase 5D0 canonical guard now has its first caller**, honoring
  `workspace_policy.allow_symlinks`. A missing path is reported as `missing` and
  the run continues; a containment, symlink, ambiguity, or resolution failure
  stops the whole run with nothing on stdout.
- **The output is metadata only.** No configured `workspace_path`, no resolved
  absolute path, no file contents, no directory listing, no raw artifact text,
  no `approval_text`, no API key or base URL. `required_verification` is left
  out entirely — this command did not run it.
- **No model call, no network call, no environment read, no GitHub fetch or
  write, no command execution, no file editing, no patch proposal, no branch,
  commit, push or PR, no agent logic or role wiring, and no approval stamping.**
- **No other command changed.** `version`, `inspect-issue`, `llm-smoke-test`,
  `generate-plan`, `real-llm-smoke-test`, `generate-model-plan`, and
  `l2-dry-run` are exactly as they were, and none of them gained an
  `--inspect-workspace` path.

See
[docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md §18](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md).

### Phase 5D0 (canonical path guard library — no CLI behavior)

Phase 5D0 adds a **library-only** canonical path guard,
`ai_dev_orchestrator.workspace.canonical`: given a workspace root and one
candidate path, it canonicalizes both on disk and proves the candidate is
genuinely inside the root. It exists because the Phase 5A design §6.4 requires
path canonicalization to be strengthened **before** any read-only workspace
inspection, so the prerequisite is built and reviewable ahead of the phase that
would use it.

- **L2 is still not built.** No implementer exists, and Phase 5D0 does not move
  toward one — it hardens a check.
- **No workspace inspection exists yet.** This is not it. The guard reads no
  file contents, lists no directory, globs nothing, and walks no tree; it
  answers one question about one path the caller already named.
- **The guard was library-only when it shipped.** Phase 5D0 added no command and
  no option, and nothing in the shipped code called it. *(Phase 5D1 later made
  `l2-inspect-workspace` its first and only caller — see the status section
  above.)*
- **`l2-dry-run` remains validation and printing only**, exactly as Phase 5C
  left it, and `generate-plan`, `generate-model-plan`, `version`,
  `inspect-issue`, `llm-smoke-test` and `real-llm-smoke-test` are unchanged.
- **No target project workspace was touched by any shipped command** at Phase
  5D0. The guard's tests create and inspect pytest `tmp_path` directories only.
- **Fails closed.** Unsafe or ambiguous path forms — UNC (`\\server\share\...`),
  extended-length (`\\?\C:\...`), device (`\\.\...`), components ending in a
  space or a dot, and 8.3-short-name-looking components (`PROGRA~1`) — are
  refused **before any filesystem call**, never normalized or repaired. This is
  deliberately conservative and may reject strings that name a real file on
  Windows. Containment is re-verified after resolution with
  `os.path.commonpath`, not a string prefix test, so a sibling sharing a prefix
  (`repo` vs `repo_evil`) is outside; a drive mismatch is refused as ambiguous
  rather than guessed.
- **Symlinks, NTFS junctions, and other reparse points are refused by default.**
  With `allow_symlinks=False` a symlinked workspace root, any linked component
  between the root and the candidate, and link-mediated entry into the workspace
  are all rejected — before the path is accepted, even when the link points back
  inside. With `allow_symlinks=True` links are followed and containment is still
  re-checked, so a link resolving outside the workspace is rejected anyway.
- **Containment is not authorization.** A successful result says a path is inside
  a root. Whether it is *allowed* remains the Phase 1 `PathPolicy` question, and
  a future caller must satisfy both. The lexical policy is unchanged.
- **No model call, no network call, no environment read, no GitHub fetch or
  write, no command execution, no file editing, no agent logic or role wiring,
  and no approval stamping.**

See
[docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md §17](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md).

### Phase 5C (L2 dry-run validation command — no implementation)

Phase 5C adds **one** command, `l2-dry-run`. It reads a project config and a
human-approved L1 plan artifact, validates them, and prints the scope a
**future** L2 would be bounded by. It is a read-and-report command in the
`generate-plan` style, one level down.

- **L2 is still not built.** No implementer exists, and `l2-dry-run` cannot
  become one — it validates and prints, and that is the whole command.
- **It reads exactly two files, in this order:** the `--project-config` YAML and
  the `--approved-plan` artifact. Nothing else is opened.
- **No workspace access.** The configured `repo.workspace_path` is never read,
  listed, stat'd, or resolved, and an `--approved-plan` inside it is rejected
  **before the artifact is read or stat'd**, by string/path normalization only.
  No path named in the plan is read, stat'd, resolved, globbed, or checked for
  existence — plan paths stay plain strings.
- **No implementation.** Nothing is inspected, proposed, patched, edited, or
  applied; no `required_verification` entry is executed; no branch, commit, or
  PR is created.
- **No model call, no network call, no environment read, no GitHub fetch or
  write, and no command execution.**
- **No approval stamping.** The command never writes an artifact and never
  writes an `approval` block. Approval remains a human act performed outside
  this tool, and an artifact merely existing — or merely parsing — is not
  approval.
- **No other command changed.** `version`, `inspect-issue`, `llm-smoke-test`,
  `generate-plan`, `real-llm-smoke-test`, and `generate-model-plan` are exactly
  as Phase 4L left them, and none of them gained an `--apply` or
  `--approved-plan` path.

See
[docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md §16](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md).

### Phase 5B (typed approved-plan handoff models, library only)

Phase 5B added the `ai_dev_orchestrator.handoff` package: typed
**approved-plan handoff models** and a strict parser for artifact text it is
handed. It is a schema, in the Phase 4B/4F style; `l2-dry-run` is its only
caller.

- **Approved-plan artifacts are parsed as data only.** A successful parse means
  the text is well-formed and carries a valid human approval. It authorizes
  nothing — the only consumer prints a dry run.
- **The parser itself does no IO.** It takes a string; obtaining that string is
  the caller's problem, and `l2-dry-run` does it with one explicit read of the
  path named on the command line.
- **No model call, no network call, no environment read, and no clock.**
  `approved_at` and `generated_at` are parsed when supplied and never produced.
- **Approval is never inferred.** Not from an artifact existing, not from it
  parsing, and not from `Automation Authorization` text in an issue or in plan
  prose. It requires a non-blank `approved_by`, a parseable `approved_at`, an
  `approval_text` equal to `"I approve this L1 plan for L2 implementation"`
  **exactly**, and `source: "manual"`. The orchestrator never writes that block.
- **`L1Plan` is unchanged.** Approval, provenance, and identity are wrapper
  fields sitting *around* an untouched plan snapshot, and a forged `approval`
  key inside `plan` is **rejected**, not stripped.
- **Every model is `extra="forbid"`**, and the project/repo/issue/title identity
  fields are compared with exact string equality.

See
[docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md §15](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md).

### Phase 4L (gated real model **L1 plan** command)

Phase 4L adds `generate-model-plan`, a **separate, explicitly gated real model
L1 planner**. It was explicitly authorized, and that authorization covers **this
command only**.

```bash
python -m ai_dev_orchestrator generate-model-plan --project-config projects/my_project.yaml --issue 42 --title "Add currency formatting helper" --body-file path\to\issue_body.md --model minimax-m2.7 --real-model
```

- **Real model L1 plan command only.** It produces a plan for a human to read.
  It implements nothing.
- **Explicit separate command.** `generate-plan` is unchanged and still
  offline-only; using the real path means typing a different command.
- **Requires `--real-model`.** Without the flag it fails closed with exit 1
  before reading the project config, the issue body, or any environment
  variable, building any client, or making any network call.
- **Uses the Phase 4J project allowlist gate.** The project's
  `real_model_planning.enabled` must be true and `--model` must appear
  **exactly** in `allowed_models`. Those checks run *before* any
  `AIDO_LITELLM_*` value is read and *before* the issue body is read; only the
  five Phase 3B names are ever read, and the explicit `--model` is sent, never
  the environment's default model.
- **Sends the explicitly provided local issue body text** — the `--title` value,
  the text of `--body-file`, and its parsed issue sections — to the real model,
  wrapped in untrusted-data delimiters. The stderr banner says so before
  anything leaves the machine.
- **Sends no source files**, no workspace contents, no directory listings, no
  git history, no GitHub token, and no API key. Project path rules travel as
  **patterns and names only**.
- **No GitHub fetch and no GitHub write.** The issue is synthesized in memory
  from the command line and the local body file; there is no option to reach
  GitHub.
- **No file editing, no command execution, no agent logic, no
  implementer/reviewer/fixer role wiring, and no target workspace access.** The
  only files read are the two named on the command line, and a `--body-file`
  inside the configured `repo.workspace_path` is rejected before it is read.
- **No audit files.** There is no `--audit-dir` option in this phase.
- **Output is an L1 plan only.** `automation_level: "L1"` and
  `requires_human_approval: true` are set by the orchestrator, never read from
  model output. **No L2/L3 automation is authorized.**
- **Tests never open a socket or read a real environment value** — they inject a
  literal env mapping and an `httpx.MockTransport`-backed client.

Phase 4K before it added `real-llm-smoke-test`, a **separate, explicitly gated
connectivity check** — and the first command in this repo that could open a real
socket. It too was explicitly authorized for **that command only**.

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

Phase 4J before that added the **fail-closed gate** that a real model-backed
planner would have to pass, as a **library function and nothing else**
(`plan/real_model_gate.py`): `check_real_model_planning_gate(...)`,
`create_real_model_l1_plan_with_gate(...)`, `endpoint_host_from_base_url(...)`,
`build_real_model_provenance(...)`, and the typed
`RealModelPlanningGateError`. Specifically:

- **Library gate only.** It is exported from `ai_dev_orchestrator.plan`; the
  Phase 4K smoke-test and Phase 4L plan commands are its only callers.
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
  commands came separately, in the authorized Phase 4K and 4L above.
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
adding no runtime code. It is the design Phase 4L implements; the offline
planning behavior it describes as the safe default — Phase 4D's `generate-plan`
and Phase 4G's fake model-backed library path — is unchanged and described below.

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
(`plan/real_model_gate.py`) described above (Phase 4J); the **gated real
model connectivity smoke test**, `real-llm-smoke-test` (Phase 4K); and the
**gated real model L1 plan command**, `generate-model-plan` — the only two
commands that can contact a real model (Phase 4L).

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

`real-llm-smoke-test` (Phase 4K) and `generate-model-plan` (Phase 4L) are the
**only** commands that can call a real model, each requires `--real-model` plus
an allowlisting project config, and each is described in the status section
above. Every other command remains offline: `generate-plan` has no `--model`,
`--live`, `--real`, `--real-model`, `--github`, `--fetch`, or `--use-env`
option, and `llm-smoke-test` does have a `--model` option, but it only names the
**fake** model echoed back by the in-process mock transport — it selects nothing
real and calls no real model.

The following are intentionally **not** implemented yet:

- No **GitHub fetch** in either real-model command. `generate-model-plan` reads
  the issue body from a local file named on the command line; combining a GitHub
  fetch with a real model call in one command remains unimplemented.
- No **GitHub writes** (read-only issue access only — no comments, labels,
  branches, or PRs).
- No **L2/L3 automation**. The real-model planner produces an L1 plan that
  requires human approval, and nothing acts on it.
- No agent logic.
- No **file editing or command execution**. Nothing writes a file, applies a
  diff, runs `required_verification`, creates a branch, commits, pushes, or
  opens a PR.
- No **writes** of any kind to a configured **target project workspace**. Two
  commands may *read* one, both read-only and both only for paths an approved
  plan already named: `l2-inspect-workspace` (Phase 5D1) canonicalizes and
  `stat`s them, and `l2-read-workspace-files` (Phase 5D2) additionally opens
  regular files, within per-file/total byte caps and behind its own project
  opt-in, and prints their contents redacted. Neither lists a directory, globs,
  or walks a tree.
- No **patch or diff application**. Proposals themselves *do* exist now:
  `generate-patch-proposal` (Phase 5E1) prints a prose-only patch proposal, and
  `generate-diff-proposal` (Phase 5E3) prints real unified diff text. Both are
  **deterministic, offline, and stdout only** — the output is **data describing
  suggested work, never permission to do it**. Nothing applies, stages, or
  writes a diff; **whether a diff would even apply is never checked**
  (`applies_cleanly_checked` is always false, because asking means touching a
  workspace); no artifact file is written; and no approval is stamped. Phase 5F0
  types the separate human approval a future file-editing phase would need, as
  library-only models and a parser with no command — recording that approval
  still edits nothing.
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

Phase 4K adds `real-llm-smoke-test`, the first command that can contact a
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

### Real model L1 plan (Phase 4L, gated — opens a real socket, sends issue text)

```bash
python -m ai_dev_orchestrator generate-model-plan \
  --project-config projects/my_project.yaml \
  --issue 42 \
  --title "Add currency formatting helper" \
  --body-file path/to/local/issue_body.md \
  --model minimax-m2.7 \
  --real-model
```

Phase 4L adds `generate-model-plan`, a **separate** command that plans with a
real model. It requires **both** the explicit `--real-model` flag **and** a
project config whose `real_model_planning` block sets `enabled: true` and lists
`--model` in `allowed_models` — either alone is not enough. `generate-plan` is
untouched and still offline-only.

In order, before anything leaves the machine: the flag is checked, the config is
loaded, `--body-file` is checked against the configured `repo.workspace_path`,
the project opt-in and the model allowlist are enforced, **then** the five
`AIDO_LITELLM_*` variables are read, **then** the body file is read, **then** a
warning block naming the endpoint host, model, project, repo, and issue is
written to stderr — stating plainly that the issue text will be transmitted —
and only then is a real client built. Any failure before the call exits non-zero
with nothing on stdout.

What **is** sent: the `--title` value, the text of `--body-file`, its parsed
issue sections (all wrapped in untrusted-data delimiters and labelled as data,
never instructions), and the project's allowed/protected/forbidden path
**patterns** and workspace policy flags.

`generate-model-plan` **does not**:

- send source files, workspace contents, directory listings, git history, the
  GitHub token, or the API key,
- fetch anything from GitHub or write anything to GitHub — the issue is
  synthesized in memory from the command line and the local body file, and there
  is no option to reach GitHub,
- read the project's configured `repo.workspace_path` or any target project
  workspace — the only files read are the `--project-config` YAML and the
  `--body-file`, and a body file inside the configured workspace path is
  rejected with exit code 1 **before it is read or stat'd**, by string/path
  normalization only,
- edit files, execute commands, run agent logic, or wire up
  implementer/reviewer/fixer roles,
- write prompt/completion audit files — there is no `--audit-dir` option,
- print the API key or the full base URL — the endpoint is reported as a
  **host** only, in both the stderr banner and the stdout JSON,
- echo the raw prompt or the raw model reply, including on parser, validation,
  and policy failures (which are still identified by type, so the three are
  distinguishable).

The explicit `--model` value is what gets planned with; `AIDO_LITELLM_DEFAULT_MODEL`
supplies connection defaults and can never select the model. On success the JSON
on stdout carries `provenance.engine: "real-model"`,
`provenance.operation: "l1-plan"`, `real_call: true`, the model, the endpoint
host, the project id, the repo, the issue number and title, a UTC `generated_at`,
the `L1Plan` under `plan`, and token usage under `usage`.

The plan is an **L1 (plan-only) artifact**: `automation_level: "L1"` and
`requires_human_approval: true` are set by the orchestrator and are never read
from model output, and the `notice` states that a human must review and approve
before any implementation work proceeds. **No L2/L3 automation is authorized by
this command**, and nothing in this repo acts on the plan.

### L2 dry run (Phase 5C, offline — validates an approved plan, does nothing else)

```bash
python -m ai_dev_orchestrator l2-dry-run \
  --project-config projects/my_project.yaml \
  --approved-plan path/to/approved_plan.json \
  --apply-approved-plan
```

`l2-dry-run` validates a human-approved L1 plan artifact and prints the scope a
**future** L2 would be bounded by. **L2 is not built**, and this command is not
it: it inspects nothing, proposes nothing, and changes nothing.

The gate fails closed in order. `--apply-approved-plan` is checked **first** —
without it the command exits non-zero having read nothing at all, not even the
project config. Then the config loads. Then `--approved-plan` is checked against
the configured `repo.workspace_path` and rejected if it is that path or sits
under it — **before the artifact is read or stat'd**, by string/path
normalization only, never by touching the workspace path on disk. Then the
artifact is read and parsed with the Phase 5B strict parser. Then `project_id`,
`repo`, `plan.repo`, and `plan_provenance.repo` must match the config with
**exact** string equality. The issue number comes from the artifact alone.

Any failure exits non-zero with stderr only and **nothing on stdout**, names the
failure category, and never echoes the artifact text or the plan prose.

On success, stdout carries one JSON object: a `notice` stating no workspace was
read, no file was edited, no command was run and no implementation occurred;
`mode: "l2-dry-run"`; the project id, repo, and workspace policy flags; the
approval's `approved_by` / `approved_at` / `source`, the plan engine, its
`real_call` flag and model, and the issue number and title; an `intended_scope`
block copying `files_likely_to_change`, `files_forbidden_or_out_of_scope`,
`required_verification`, `proposed_steps`, `risks` and `open_questions`
**verbatim** from the approved plan, labelled as plan text that was not acted
on; and a statement that any later phase must be explicitly authorized.

`l2-dry-run` **does not**:

- read, list, stat, or resolve the project's configured `repo.workspace_path` or
  any target project workspace, or read, stat, resolve, glob, or existence-check
  any path the plan names — plan paths stay plain strings,
- run any `required_verification` entry or any other command,
- generate or apply a patch, edit a file, or create a branch, commit, or PR,
- fetch anything from GitHub or write anything to GitHub — there is no option to
  reach it,
- call a model, open a socket, construct an `LLMClient`, or read
  `AIDO_LITELLM_*` or any other environment variable — there is no `--model` and
  no `--real-model`,
- write an artifact or stamp an approval — the approval block must already have
  been written by a human,
- print the raw artifact text, the plan's `approval_text`, an API key, a base
  URL, the configured workspace path, or any source file contents.

### L2 workspace metadata inspection (Phase 5D1, read-only — `stat` and nothing more)

```bash
python -m ai_dev_orchestrator l2-inspect-workspace --project-config projects/my_project.yaml --approved-plan path/to/approved_plan.json --apply-approved-plan --inspect-workspace
```

`l2-inspect-workspace` is the **only** command that may touch a configured
target workspace, and the only thing it does there is canonicalize and `stat`.
For each path the approved plan lists under `files_likely_to_change` it reports
existence, kind (`file` / `directory` / `other`), size for a regular file, and
the canonical path relative to the workspace root. **L2 is not built**, and this
command is not it: it proposes nothing, edits nothing, and runs nothing.

It requires a project config that opts in:

```yaml
read_only_workspace_inspection:
  enabled: false          # must be true for this command to touch the workspace
  max_inspected_files: 20 # 1..100; a plan naming more fails before any touch
  allow_protected_paths: false
```

An absent block is identical to a disabled one, and the example config ships it
disabled.

The gate fails closed in order. `--apply-approved-plan` and
`--inspect-workspace` are checked **first** — without either, the command exits
non-zero having read nothing at all, not even the project config. Then the
config loads. Then the project opt-in must be enabled — otherwise the run stops
before the artifact is even opened. Then `--approved-plan` is rejected if it is
the configured `repo.workspace_path` or sits under it, **before it is read or
stat'd**. Then the artifact is read, parsed with the Phase 5B strict parser, and
matched against the config for exact `project_id` / `repo` / `plan.repo` /
`plan_provenance.repo` equality. Then the candidate count is checked against
both `max_inspected_files` and `workspace_policy.max_changed_files`. Then the
Phase 1 lexical path policy runs for **every** candidate — forbidden, outside,
traversal-escaping and unlisted paths always refused, protected paths refused
unless `allow_protected_paths` is true — and one refusal abandons the whole run.

**Only after all of that** is the workspace touched: the root is canonicalized
first, then each candidate goes through the Phase 5D0 guard honoring
`workspace_policy.allow_symlinks`, then a single `stat`. A path that does not
exist is reported as `missing` and the run continues. A containment, symlink,
ambiguity, or resolution failure stops the whole run with nothing on stdout.

`l2-inspect-workspace` **does not**:

- read or open any file's contents in a target workspace,
- list, glob, or walk any directory — a candidate that *is* a directory is
  reported as one and its entries are never enumerated,
- inspect anything outside `files_likely_to_change`, including
  `files_forbidden_or_out_of_scope`, or treat `proposed_steps`,
  `required_verification`, `risks`, or `open_questions` as paths,
- run any `required_verification` entry or any other command,
- generate or apply a patch, edit or write any file, or create a branch, commit,
  or PR,
- fetch anything from GitHub or write anything to GitHub,
- call a model, open a socket, construct an `LLMClient`, or read
  `AIDO_LITELLM_*` or any other environment variable,
- write an artifact or stamp an approval,
- print the configured workspace path, any resolved absolute path, any file
  contents, the raw artifact text, `approval_text`, an API key, or a base URL.

### L2 file-content inspection (Phase 5D2, read-only — bounded and redacted)

```bash
python -m ai_dev_orchestrator l2-read-workspace-files --project-config projects/my_project.yaml --approved-plan path/to/approved_plan.json --apply-approved-plan --read-contents
```

`l2-read-workspace-files` is the **only** command whose output may contain a
target project's source. For each path the approved plan lists under
`files_likely_to_change` it runs everything `l2-inspect-workspace` runs — the
lexical path policy, the Phase 5D0 canonical guard, a `stat` — and then, only
for a regular file inside the configured byte caps, opens it, decodes it as
UTF-8, redacts obvious secret-like text, and prints it.

It requires **both** `--apply-approved-plan` and `--read-contents`, and it
requires this block in the project config — shipped **disabled**, and separate
from Phase 5D1's `read_only_workspace_inspection`:

```yaml
read_only_workspace_content:
  enabled: false
  max_files: 10
  max_file_bytes: 50000
  max_total_bytes: 200000
  allow_protected_paths: false
```

Each candidate ends in exactly one status: `read` (with `content_text`),
`missing`, `directory_no_content`, `other_no_content`, `too_large`,
`skipped_total_limit`, or `binary_or_non_utf8`. Every status but the first
carries a null `content_text` and `bytes_read: 0`, and the run continues. A
containment, symlink, ambiguity, or resolution failure stops the whole run with
nothing on stdout.

**Redaction is mandatory.** `Bearer <token>`, assignment values for
`api_key`/`apikey`/`token`/`secret`/`password`/`passwd`/`pwd`, and OpenAI-style
`sk-…` strings are replaced before anything is printed, and the output reports
`redacted`, `redaction_count` and `redaction_kinds`. No config field and no flag
disables it. It is a small deterministic backstop, **not** a guarantee that the
output is secret-free — treat printed contents accordingly.

`l2-read-workspace-files` **does not**:

- list, glob, or walk any directory — a candidate that *is* a directory is
  reported as `directory_no_content` and its entries are never enumerated,
- read anything outside `files_likely_to_change`, including
  `files_forbidden_or_out_of_scope`, or treat `proposed_steps`,
  `required_verification`, `risks`, or `open_questions` as paths,
- run any `required_verification` entry or any other command,
- generate a diff or a patch, apply anything, or edit or write any file,
- write an artifact file (stdout only) or stamp an approval,
- create a branch, commit, or PR, or fetch from or write to GitHub,
- call a model, **send any file content to a model**, open a socket, construct
  an `LLMClient`, or read `AIDO_LITELLM_*` or any other environment variable,
- print the configured workspace path, any resolved absolute path, the raw
  artifact text, `approval_text`, `required_verification`, any diff, any command
  output, an API key, or a base URL.

### Generating a patch proposal (Phase 5E1, offline — prose only, no diff)

```bash
python -m ai_dev_orchestrator generate-patch-proposal --project-config projects/my_project.yaml --approved-plan path/to/approved_plan.json --apply-approved-plan --generate-proposal
```

`generate-patch-proposal` turns a human-approved L1 plan into a **proposal-only**
patch proposal artifact, generated deterministically from two local files and
printed to stdout. For each path the approved plan lists under
`files_likely_to_change` it emits one `modify` change carrying a rationale,
prose review steps, and risks. The same inputs always produce a byte-identical
artifact, and stdout is the artifact itself with no wrapper, so it parses with
`parse_patch_proposal_artifact`.

**L2 is not built, and this command is not it.** It proposes in prose; it
implements nothing.

The gate fails closed in order. `--apply-approved-plan` and
`--generate-proposal` are checked **first** — without either, the command exits
non-zero having read nothing at all, not even the project config. Then the
config loads. Then `--approved-plan` is rejected if it is the configured
`repo.workspace_path` or sits under it, **before it is read or stat'd**. Then
the artifact is read and parsed with the Phase 5B strict parser. Then the
generator matches `project_id` / `repo` / `plan.repo` / `plan_provenance.repo`
against the config for exact equality, re-checks that the plan is an unescalated
L1 plan, refuses a plan naming a path as both likely-to-change and forbidden,
and enforces `workspace_policy.max_changed_files` on the deduplicated candidate
count. Any failure exits non-zero with stderr only and nothing on stdout.

`generate-patch-proposal` **does not**:

- generate a diff, a patch, a hunk, or an edit script — the artifact has no
  field for one,
- read any file's contents beyond the two files named on the command line,
- read, list, stat, glob, walk, or resolve any target workspace, or check
  whether any path the plan names exists,
- propose anything outside `files_likely_to_change`, or treat `proposed_steps`,
  `required_verification`, `risks`, or `open_questions` as paths,
- run any `required_verification` entry or any other command,
- edit or write any file — including the proposal itself, which is printed and
  never saved,
- create a branch, commit, or PR, or fetch anything from or write anything to
  GitHub,
- call a model, open a socket, construct an `LLMClient`, or read
  `AIDO_LITELLM_*` or any other environment variable,
- stamp an approval — the approval must already have been written by a human and
  travels through unchanged inside the embedded plan snapshot,
- print the configured workspace path, any absolute path, any file contents, the
  raw artifact text, an API key, or a base URL.

### Generating a diff proposal (Phase 5E3, offline — diff text, never applied)

```bash
python -m ai_dev_orchestrator generate-diff-proposal --project-config projects/my_project.yaml --approved-plan path/to/approved_plan.json --workspace-content path/to/workspace_content.json --proposed-content path/to/proposed_content.json --apply-approved-plan --generate-diff
```

`generate-diff-proposal` turns four **local files** into a **proposal-only**
unified diff proposal artifact, printed to stdout. `--workspace-content` is JSON
you previously produced with `l2-read-workspace-files`; it supplies the original
text to diff against. `--proposed-content` is a `proposed-content.v1` object
(mode `proposal-only`) giving each path's final text, prepared by a human or an
external tool. For each proposed path the command runs `difflib` between the two
and emits one single-file unified diff. The same inputs always produce a
byte-identical artifact, and stdout is the artifact itself with no wrapper, so it
parses with `parse_diff_proposal_artifact`.

**L2 is not built, and this command is not it.** It writes a diff for a human to
read; it applies nothing and implements nothing.

The gate fails closed in order. `--apply-approved-plan` and `--generate-diff`
are checked **first** — without either, the command exits non-zero having read
nothing at all, not even the project config. Then the config loads. Then **all
three** input paths are rejected if any is the configured `repo.workspace_path`
or sits under it, **before any of them is read or stat'd**. Then the approved
plan is read and parsed with the Phase 5B strict parser; then the content
packet; then the proposed content. Then the generator matches identity against
both the config and the packet for exact equality, re-checks that the plan is an
unescalated L1 plan, and keeps every proposed path inside the approved scope.
Generation also fails closed when a proposed path is absent from the packet, when
a `modify`'s recorded content is missing, redacted, or not a regular file's, when
a `create` names a path that was actually read or carries no content, and when a
generated diff matches a secret-like pattern. Any failure exits non-zero with
stderr only and nothing on stdout.

`generate-diff-proposal` **does not**:

- apply, stage, or write a patch, or check whether any generated diff would
  apply — `applies_cleanly_checked` is false because the question is never asked,
- read any file's contents beyond the four files named on the command line — in
  particular it never opens the paths the approved plan names,
- read, list, stat, glob, walk, or resolve any target workspace,
- propose anything outside `files_likely_to_change`, or treat `proposed_steps`,
  `required_verification`, `risks`, or `open_questions` as paths,
- run any `required_verification` entry or any other command,
- edit or write any file — including the proposal itself, which is printed and
  never saved,
- create a branch, commit, or PR, or fetch anything from or write anything to
  GitHub,
- call a model, open a socket, construct an `LLMClient`, or read
  `AIDO_LITELLM_*` or any other environment variable,
- stamp an approval — the approval must already have been written by a human and
  travels through unchanged inside the embedded plan snapshot,
- print the configured workspace path, any absolute path, the raw text of any
  input, any command output, any apply result, an API key, or a base URL.

### Previewing file edits (Phase 5F1, offline — a dry run that writes nothing)

```bash
python -m ai_dev_orchestrator l2-preview-file-edits --project-config projects/my_project.yaml --approved-diff-proposal path/to/approved_diff_proposal.json --apply-approved-plan --preview-file-edits
```

`l2-preview-file-edits` reads two **local files** — the project config and a
human-approved Phase 5F0 diff proposal artifact — and prints a JSON report
describing what a future, separately authorized write phase *would* be permitted
to attempt. For each permitted path it reports the change type and **counts**
summarizing the diff: bytes, lines, hunks, added, removed, context. It carries no
unified diff text and no source contents. stdout is the report itself with no
wrapper.

**Nothing is written.** The report's `files_edited`, `commands_run`,
`applies_cleanly_checked` and `workspace_touched` are all false, and
`checks_not_performed` states every one of the thirteen things this command did
not do — including `canonicalization_checked`, because the path policy applied
here is **lexical only**: a path that passes it could still resolve, on a real
filesystem, somewhere the policy would refuse. Closing that gap requires touching
the workspace, which this command does not do.

The gate fails closed in order. `--apply-approved-plan` and
`--preview-file-edits` are checked **first** — without either, the command exits
non-zero having read nothing at all, not even the project config. Then the config
loads. Then the artifact path is rejected if it is the configured
`repo.workspace_path` or sits under it, **before it is read or stat'd**. Then the
artifact is parsed with the Phase 5F0 strict parser. Then identity is matched
against the config by exact string equality in all six places the artifact
records it, paths are re-checked for duplicates, the change count is checked
against `workspace_policy.max_changed_files`, and every path is run through the
Phase 1 `PathPolicy` **write** check. A forbidden, unlisted, traversal-escaping,
or **protected** path fails the whole preview rather than appearing as a denied
row — and there is no flag to permit a protected write. Any failure exits
non-zero with stderr only and nothing on stdout.

`l2-preview-file-edits` **does not**:

- write, edit, or create any file, in a workspace or anywhere else,
- apply, stage, or check a diff — `applies_cleanly_checked` is false because the
  question is never asked,
- read, list, stat, glob, walk, resolve, or **canonicalize** any target
  workspace, or open any path the approved diff names,
- check whether any of those paths exists or what it currently contains,
- run any `required_verification` entry or any other command,
- write the report to a file — it is printed and never saved,
- create a branch, commit, or PR, or fetch anything from or write anything to
  GitHub,
- call a model, open a socket, construct an `LLMClient`, or read
  `AIDO_LITELLM_*` or any other environment variable,
- stamp, widen, or infer an approval — the file-edit approval must already have
  been written by a human in the exact Phase 5F0 wording, and it is never
  inferred from the wrapped L1 plan approval, from the diff proposal parsing,
  from `requires_human_review`, or from the file simply existing,
- print the configured workspace path, any absolute path, the raw artifact text,
  the approval text, any diff, any source line, any command output, any apply
  result, an API key, or a base URL.

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

Phase 4L then added the **explicitly authorized** real model *plan* command,
`generate-model-plan`, also described above. It is the second and last command
permitted to open a real socket, it transmits only the issue title and the local
body file text explicitly named on the command line, and its output is an L1 plan
that still requires human approval.

**Phase 5A** is a **design review only** — see
[docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md),
which designs the L1-to-L2 boundary: an approved-plan handoff artifact whose
approval metadata sits *around* an untouched `L1Plan` snapshot, a fail-closed
approval gate on a separate command (off by default, exact project/repo/issue
matching, and approval that can never be inferred from a file's existence or
from an issue's `Automation Authorization` text), staged capability boundaries
that put read-only inspection and patch *proposals* ahead of any file write, the
workspace/command/git/model policies a future L2 would need, and a decision that
the known lexical path-normalization gap (symlinks, junctions, UNC, mapped
drives, 8.3 names) must be closed **before** anything touches a target
workspace. Phase 5A added **no runtime code, no CLI behavior, no model call, no
network call, and no environment-variable read**.

**Phase 5B** then typed that design's §3 handoff artifact — the
`ai_dev_orchestrator.handoff` package described in the status section above.
It is **models and a strict parser only**, wired into nothing: no CLI behavior,
no artifact loader and no disk read, no workspace access, no model call, no
network call, no environment read, no clock, and no L2 action. `L1Plan` is
unchanged, approval can never be inferred, and a parsed artifact is data
describing an approval — never permission to do anything.

**Phase 5C** then added the `l2-dry-run` command described in the status and
usage sections above — the first code here that reads an approved-plan artifact
from disk, and the first command named for L2. It is a **validator and a
printer**: it reads two explicitly named local files, checks the artifact against
the config, and reports the scope a future implementer *would* be bounded by. It
adds **no workspace access, no implementation, no model call, no network call,
no environment read, no GitHub fetch or write, no command execution, no file
editing, no agent logic or role wiring, and no approval stamping**, and it
changed none of the six commands Phase 4L left behind.

**Phase 5D0** then built the path canonicalization work that design §6.4 named as
a prerequisite — the library-only guard described in the status section above.
It is **not** workspace inspection: it adds no command and no option, no shipped
code path calls it, and its tests use pytest `tmp_path` directories only.

**Phase 5D1** then added the `l2-inspect-workspace` command described in the
status and usage sections above — the first code here permitted to touch a
configured target workspace, and the guard's first caller. It touches it as
`stat` and nothing else: existence, kind, and size for the paths an approved
plan already named, behind two explicit flags, a project-level opt-in, artifact
validation, exact identity matching, candidate-count caps, the lexical path
policy, and the canonical guard. It adds **no file content reads, no directory
listings, no patch proposal, no file editing, no command execution, no model
call, no network call, no environment read, no GitHub fetch or write, no agent
logic or role wiring, and no approval stamping**, and it changed none of the
seven commands that came before it.

**Phase 5E0** then typed the **patch proposal artifact** — the
`ai_dev_orchestrator.patch_proposal` package described in the status section
above. It is **not patch generation**: there is no generator, and the artifact
carries no unified diff and no file content. Library only, wired into nothing —
no command, no option, no workspace access, no model/network/environment access,
and no approval stamping.

**Phase 5E1** added the generator and the `generate-patch-proposal` command
described in the status and usage sections above. It turns an approved plan into
a prose-only proposal artifact, deterministically and offline, and prints it. It
is still **not a diff and not file editing**: no unified diff, no file content,
no command, and no command output. It adds **no workspace access, no file
content reads, no artifact file writing, no file editing, no command execution,
no model call, no network call, no environment read, no GitHub fetch or write,
no agent logic or role wiring, and no approval stamping**, and it changed none
of the eight commands that came before it.

**Phase 5D2** added the `l2-read-workspace-files` command described in the
status and usage sections above — the content half of the capability Phase 5D1
split in two, shipped as its own command behind its own project opt-in rather
than as a flag on the metadata one. It re-runs every Phase 5D1 gate, adds a
second consent flag and a separate opt-in in front of them, bounds the read by
file count and by per-file and total bytes, and redacts every byte it prints.
It adds **no directory listings, no diff generation, no patch, no file editing,
no command execution, no model call, no file content sent to a model, no
network call, no environment read, no GitHub fetch or write, no agent logic or
role wiring, and no approval stamping**, and it changed none of the nine
commands that came before it.

**Phase 5E2** then typed the **unified diff proposal artifact** — the
`ai_dev_orchestrator.diff_proposal` package described in the status section
above. It is the inert half of "carrying a real diff": a diff may now be carried
and validated **as data**, but nothing generates one, modifies one, or applies
one, and whether a diff would apply is never checked. Library only, wired into
nothing — no command, no option, no workspace access, no file content reads, no
file editing, no command execution, no model/network/environment access, no
GitHub fetch or write, and no approval stamping.

**Phase 5E3** added the producer and the `generate-diff-proposal` command
described in the status and usage sections above. It generates unified diff text
deterministically and offline, from a Phase 5D2 content packet and a
proposed-content input supplied as local files, and prints it. It **reads no
target workspace file directly**, and it **generates diff text and does nothing
with it**: no diff applied, no apply-cleanliness check, no file editing, no
command execution, no artifact file writing, no model call, no network call, no
environment read, no GitHub fetch or write, no agent logic or role wiring, and
no approval stamping. It changed none of the ten commands that came before it.

**Phase 5F0** then typed the **file-edit write gate** — the second, separately
worded human approval of one *concrete diff proposal*, described in the status
section above. Library only, wired into nothing: no command, no option, no
workspace access, no file editing, no diff application, no apply-cleanliness
check, no command execution, no model/network/environment access, no
branch/commit/push/PR, no artifact file written, and no approval stamping.

**Phase 5F1** then added the first consumer of that approval and the
`l2-preview-file-edits` command described in the status and usage sections above.
It validates an approved diff proposal against a project config and the
**lexical** Phase 1 write policy and prints what a future write phase *would be
allowed to attempt* — permitted paths, change types, and diff **counts**, with no
diff text and no source contents. It is a description of a hypothetical: **no
workspace read, list, stat, resolve, or canonicalization, no diff applied, no
apply-cleanliness check, no file editing, no command execution, no artifact file
written, no model call, no network call, no environment read, no GitHub fetch or
write, no branch/commit/push/PR, and no approval stamping.** It changed none of
the eleven commands that came before it.

**Phase 5F2A** then wrote the safety contract a first workspace-write phase would
have to satisfy, **as design only** — documentation, no code — and split the old
single "Phase 5F2" slot into five smaller phases.

**L2 is proposed, not built.** No command can invoke it, and every later Phase 5
sub-phase remains unauthorized — **Phase 5F2B** (create-aware canonical
write-target guard, library only), **Phase 5F2C** (typed workspace-write gate
models, library only), **Phase 5F2D** (read-only Git-state probe), **Phase 5F2E**
(read-only write preflight), and **Phase 5F2F** (the first controlled workspace
write). Nothing in the repository ships any of them, and **nothing shipped edits
a target file**. Until one is explicitly authorized, the project continues to
avoid agent automation, patch application, file editing, command execution,
GitHub writes, GitHub issue fetching inside a real model command, and target
project workspace writes.
