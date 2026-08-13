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

## Current status: Phase 5F2D — AIDO can now write **one** approved file and **verify** it, and that is all

**Phase 5F2D is the latest completed phase, and it is the first one that
executes repository-controlled code.** Two commands now exist where there were
none:

- `l2-apply-approved-file-edit` (Phase 5F2C) applies **one** explicitly
  human-approved modification to **one** existing, Git-tracked, ordinary UTF-8
  file inside **one** wholly clean Windows Git repository — transforming an exact
  approved pre-image into an exact approved post-image, proving the
  postcondition, and leaving the change **uncommitted** for a human to review.
- `l2-verify-approved-file-edit` (Phase 5F2D) proves the workspace still holds
  exactly that approved change, executes **one** project-configured verification
  process **once** under a wall-clock and output bound, captures and redacts its
  output, and then proves the Git-visible workspace state still contains only the
  approved modification.

They are **separately invokable**. The writer has no verification flag, and the
verifier writes nothing.

Everything outside those two sentences fails closed. There is no file creation,
no delete, no rename, no second file, no protected or forbidden path, no fuzzy
patching, no non-Windows support, no shell, no command chaining, no arbitrary or
model-proposed command, no model call, no orchestrator network call, no GitHub
access, no branch, no commit, no push, no PR, no retry, no automatic repair, no
rollback and no journal.

> **Controlled invocation is not sandboxed execution.** Phase 5F2D chooses which
> program runs, with which arguments, where, with which minimal environment, for
> how long and how loudly. It does **not** confine what that program then does,
> and the result report says so rather than claiming inertness it cannot
> establish.

**Why the roadmap changed.** The plan after Phase 5F2A was 5F2C typed gate
models → 5F2D custom Git-state reader → 5F2E standalone preflight → 5F2F
generalized transactional writer. After 5F2B shipped, the project was
independently reviewed and concluded that the safety philosophy remained
correct but the sequencing had become imbalanced: by then the repository held
twelve commands, four artifact schemas, two path guards, two human approvals and
a dry-run preview — and could not change a single character of a single file.
Generalized mutation-engine machinery (transactions, journals, rollback, crash
recovery, concurrency) was scheduled ahead of the first useful mutation, and
that machinery is itself reliability and security surface. The new rules are:

> If a difficult case can safely be excluded from the currently supported input
> domain, prefer **fail-closed refusal** over building a generalized solution
> before the first useful vertical slice.

> Once the supported domain is safe enough to prove a useful positive
> capability, **consume the existing safety primitives** before creating
> additional generalized ones.

The near-term sequence is now **5F2C controlled single-file writer → 5F2D
controlled verification → 5F2E reviewer integration → the first complete
controlled implement → verify → review → human loop**. Generalized writer
expansion resumes only after that. See
[§27 and §28 of the design doc](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md);
§26.12 is preserved as history and marked superseded prospectively.

### What Phase 5F2C actually ships

- **A project opt-in that ships disabled**, `workspace_write`, with exactly two
  fields — `enabled` and `max_file_bytes`. There is deliberately **no**
  `allow_protected_paths`, no create flag, no multi-file switch, no
  rollback/journal setting, no credential, no model and no command.
  `workspace_policy.max_changed_files` is not duplicated; the writer enforces it
  **and** its own hard rule of exactly one change, and a cap of `0` permits no
  write at all. While disabled, the command refuses before the workspace is
  touched.
- **A schema evolution that binds both ends of the transformation.**
  `diff-proposal.v1` became **`diff-proposal.v2`** and
  `approved-diff-proposal.v1` became **`approved-diff-proposal.v2`**: every
  change now carries `pre_image_sha256` (the whole original file's exact UTF-8
  bytes; `null` for a `create`) and `post_image_sha256`. A diff describes a
  transformation without saying which bytes it starts from — once a writer
  exists, that gap is the whole security question. The version was **raised
  rather than v1's meaning quietly changed**, so a v1 artifact is rejected, not
  upgraded. The human approval sentence is **unchanged** and there is no second
  approval artifact.
- **A strict, no-fuzz diff applier.** No `patch`, no `git apply`, no fuzzy
  engine. Headers must name the approved path exactly; hunk locations are exact;
  every context and deleted line must match byte for byte; there is no offset
  search, no fuzz, no nearest-match, no three-way merge and no repair; malformed,
  overlapping or self-inconsistent hunks fail closed. If the result does not hash
  to the approved post-image, that is an internal inconsistency and the write is
  refused.
- **A fixed Git adapter, which is not command execution.** The executable is
  resolved to an **absolute path once per run** and pinned for every invocation
  in it — never the bare name `"git"`, and refused if it lives inside the target
  workspace. Every argv comes from a closed set of read-only operations, which
  since 5F2C-FU1 also includes the two configuration probes that implement the
  filter gate (`config --list --local --no-includes --name-only` and
  `config --list --show-scope --name-only`); **repository configuration that
  could execute a program is refused before any content-reading Git operation
  runs**. No model, user, config file or artifact supplies an executable, a
  subcommand, a flag or a shell fragment; `shell=False` always; the environment
  is a **minimal allowlist** so no `AIDO_LITELLM_*` value, `GITHUB_TOKEN` or
  inherited `GIT_DIR` reaches the child; pager, prompting, askpass, external
  diff, textconv, fsmonitor and optional locking are all disabled; output is
  bounded **during capture** — the child is killed the moment the cap is passed
  — and a watchdog enforces the timeout. There is no `add`, `commit`,
  `checkout`, `restore`, `reset`, `branch`, `apply`, `fetch` or `push`, and no
  network operation at all. Fixed AIDO-owned Git plumbing is part of the
  **writer's own correctness contract**; repository-configured verification is a
  **separate capability, added later and separately by Phase 5F2D**.
- **A clean-baseline requirement with no exceptions.** The Git top level must be
  exactly the configured workspace root, `HEAD` must exist, and `git status`
  must report **nothing** — staged, unstaged, untracked, deleted, renamed,
  unmerged and dirty-submodule state all refuse the run. Any assume-unchanged or
  skip-worktree entry, any unmerged entry, and any gitlink refuse the **whole
  repository**: if the simple contract cannot be proved, this is not a
  repository the writer supports. **No custom Git index parser was built.**
- **A narrow target contract.** Lexical write policy (protected, forbidden and
  unlisted all refused, with no override anywhere), then the Phase 5F2B
  canonical write-target guard, then an existing regular file, supported Windows
  attributes only (an allowlist — read-only, hidden, system, reparse, sparse,
  encrypted, compressed, offline and temporary all refuse), and a hard-link
  count of exactly **one**, read via `GetFileInformationByHandle` and refused
  when it cannot be established.
- **A narrow text domain.** Strict UTF-8, no NUL bytes, one uniform line-ending
  style preserved as found, and a required terminal newline — which is what makes
  the split/rejoin round trip byte-exact. Mixed endings, bare CR, missing
  terminal newline, non-UTF-8 and oversize files are all **refused**, with no
  detection, conversion, normalization or repair.
- **Full revalidation immediately before the write.** Nothing established
  earlier is reused as durable authority: the canonical guard, the file kind,
  the reparse state, the link count, the attribute mask, the bytes, the
  pre-image digest and the Git baseline are **all** re-established immediately
  before the mutation.
- **A metadata-preserving replacement.** `os.replace` is deliberately not used —
  it would give the destination the *new* file's ACLs and attributes, turning an
  approved content-only edit into an uncontrolled metadata change. The writer
  uses `ReplaceFileW` with `dwReplaceFlags == 0` — no "write through" (which
  `ReplaceFileW` does not support), no "ignore merge errors", no "ignore ACL
  errors" — and **no backup file**, after staging the bytes into one
  exclusively-created sibling temp file that is flushed and `fsync`ed. Durability
  comes from that `fsync`, and from nothing else. No directory is ever created.
- **Machine verification after the write.** A successful API call is not proof:
  the bytes are re-read and must hash to the approved post-image, the attribute
  mask must be unchanged, and Git must report **exactly** the approved path as
  dirty and nothing else. Git's own diff text is *not* required to match the
  approved `difflib` text — those are two renderings of one change, and the
  digest is the correctness invariant.
- **Two distinct failure kinds.** Exit **1** means refused before any write and
  the target is unchanged. Exit **3** means a replacement was attempted and its
  final state could not be proved — which is **never** reported as "nothing
  changed". On exit 3 nothing is retried, nothing is rolled back, no
  `git restore` is run, and the human is told that repository inspection is
  required against the clean baseline the run proved beforehand.
- **A quiescent single-writer contract, stated rather than solved.** Phase 5F2C
  supports one AIDO writer against a workspace nobody else is editing. There is
  no lock, no watcher and no concurrency protocol; interference is detected by
  revalidation and means failing closed. **Concurrency is not solved.**

### Phase 5F2C-FU1 — corrections found in review

Phase 5F2C was reviewed before acceptance and six findings were returned. All
six are fixed. **Nothing was widened to fix them** — every one was closed by
refusing an unsupported case, which is exactly what §27's rules ask for.

- **`ReplaceFileW` was passing an unsupported flag.** The code set
  `REPLACEFILE_WRITE_THROUGH`, which Microsoft documents as **not supported** by
  `ReplaceFileW`, so the call claimed a durability guarantee the API does not
  offer. `dwReplaceFlags` is now **exactly `0`**, and durability is described
  accurately: it comes from the `fsync` on the temp file *before* the
  replacement, and from nothing else. `os.replace` did **not** replace
  `ReplaceFileW` — the metadata-preserving design is deliberate and remains.
- **Cleanup after a failed replacement was unsafe.** The old code deleted the
  temp file even after `ReplaceFileW` had been invoked and failed — a moment
  when filename state may already have changed, so deleting could discard the
  only intact copy of the new content. Cleanup is now **asymmetric**: safe
  before the replacement call, and **forbidden after it**. A failed replacement
  deletes nothing, renames nothing, restores nothing, retries nothing, and runs
  no Git mutation; it reports the exit-3 indeterminate outcome and names the
  leftover temp file so a human can find it.
- **The fixed argv did not prevent repository-controlled execution.** This was
  the serious one, and the original reasoning was simply wrong. Git runs clean,
  smudge and process **filters** — commands configured by the repository through
  `filter.<driver>.*` and selected by `.gitattributes` — from inside a perfectly
  fixed argv. Reproduced against a real `git` binary in a temporary repository,
  a configured `filter.evil.clean` executes during `git diff`, **and during
  `git status` on a wholly clean tree** whenever a tracked file's cached stat
  data is stale (a bare `touch` is enough, because Git must re-hash the file to
  prove it is unchanged). That fires during the writer's very first preflight.
  The fix is a **fail-closed configuration gate**, not a Git reimplementation
  and not a generic executor: a repository whose effective Git configuration can
  execute a program or indirect to configuration that could is **refused**
  before anything reads working-tree content. Only key *names* are read
  (`--name-only`), so no configuration value ever enters the process and a
  refusal cannot leak one. The local scan runs with `--no-includes`, so the
  decision about whether indirection is permitted is not itself made by
  following it. The gate is deliberately over-broad in one direction: a machine
  with git-lfs configured globally will have its repositories refused.
- **Gate ordering let `status` run too early.** `git status
  --ignore-submodules=none` ran before the index was known to be gitlink-free,
  so the walk could descend into a submodule the writer was about to refuse. The
  order is now data (`ordered_preflight_operations()`) and asserted by test:
  safe metadata → configuration gate → index gate → *only then* working-tree
  cleanliness.
- **Executable selection was ambient.** `GIT_EXECUTABLE = "git"` let the OS pick
  the program. Git is now resolved to **one absolute executable path before any
  Git invocation or child process is launched**, refused if it lives **inside the
  target workspace**, and the same resolved path is reused throughout the run.
  The executable argument is required with no default, so there is no silent
  fallback to `"git"`. (An earlier phrasing said "before any target-workspace
  use", which the implementation does not do: the writer canonicalizes and stats
  the approved target first, and those probes launch nothing. The claim was
  corrected rather than the code moved.)
- **Output was measured after capture, not bounded during it.** The adapter now
  reads stdout in chunks and **kills the child the moment the cap is passed**,
  with a watchdog enforcing the timeout; stderr goes to `DEVNULL` (it was never
  used for a decision, and Git's stderr can carry paths and content). The bound
  is real. The **residual limitation is stated rather than hidden**: it bounds
  output volume and wall time, not everything a hostile local repository could
  make Git do — this is a single-writer tool for a locally trusted repository,
  not a sandbox.
- **The report claimed no file was created.** A successful write always creates
  one ephemeral sibling temp file. `files_created: false` became target-scoped
  `target_files_created: false`, and a new `operational_files` block states the
  truth: one temp sibling used, consumed by the replacement, none left behind,
  no directory created, no backup or journal. **No journal and no backup were
  added.**

### What Phase 5F2D actually ships

Phase 5F2C's writer runs a fixed, AIDO-owned, read-only Git inspection set as
part of its own correctness contract. **Phase 5F2D crosses a genuinely new
boundary**: it launches a program the *project* chose. Those two things are kept
apart in the code, in the report schema, and in this document.

- **A second project opt-in that ships disabled**, `controlled_verification`,
  with exactly five fields — `enabled`, `executable`, `args`, `timeout_seconds`
  and `max_output_bytes`. There is deliberately **no** shell command string, no
  working-directory override, no PATH lookup, no executable default, no
  interpolation or `{path}` templating, no environment or secret forwarding
  switch, no second command profile, no command id, and no before/after hook.
  An absent block is identical to a disabled one.
- **Exactly one command, and its argv is `[executable, *args]`.** The executable
  must be an absolute path to an existing regular file that resolves **outside**
  the target workspace — the repository being verified may not supply the program
  that launches its own verification, because that would make the executable's
  identity part of the very state this phase is pinning down. Args are used
  verbatim: nothing is split, quoted, expanded, or read as shell syntax.
- **`required_verification` is never command authority.** The L1 plan carries it,
  a model may have written it, and this phase never splits it, parses it, runs
  it, or turns it into argv. A plan saying `pytest tests/foo.py`, `rm -rf …` or
  `curl …` changes **nothing** about which process runs. It is counted in the
  report and ignored as authority, and a test proves a hostile sentinel value
  never reaches a command line and never executes.
- **A minimal child environment, with no way to widen it.** A fixed allowlist of
  OS/runtime variables only. No `AIDO_LITELLM_*`, no `GITHUB_TOKEN`, no API key,
  no database or cloud credential, and no project-configurable forwarding. A
  project whose tests need credentials is outside this first supported domain and
  may simply fail — that is the accepted trade.
- **Pre-execution state binding.** Before anything is launched: identity matched
  in all six places, exactly one `modify` change, the lexical write policy, the
  Phase 5F2B canonical guard, an existing regular file, an absolute pinned Git
  executable, the Git configuration gate, a simple submodule-free index, the
  target tracked as one ordinary stage-0 blob, the file's exact bytes hashing to
  the approved `post_image_sha256`, and a Git-visible dirty state that is
  **exactly** the approved target as a plain unstaged modification. Not the
  pre-image, not "the diff still applies", not a partially edited file.
- **A baseline that deliberately differs from the writer's.** The writer requires
  **zero** dirty paths; the verifier requires **exactly one** — the approved
  target. The distinction is the point and is not weakened anywhere.
- **One bounded invocation.** `shell=False`, cwd is the canonical workspace root,
  stdin is `DEVNULL`, stderr is merged into stdout so a single pipe makes bounded
  reading deadlock-free, output is capped **during** capture with a kill the
  moment the cap is passed, and **AIDO's wait is bounded by the configured
  timeout plus a fixed direct-child reap grace** — see the FU1 and FU2 notes
  below for what that does and does not mean. One execution: no retry, no
  fallback executable, no second attempt.
- **Bounded first, redacted second, never claimed complete when it isn't.**
  Output is redacted through the **same** helper Phase 5D2 uses — extracted to
  `ai_dev_orchestrator/redaction.py` rather than reimplemented, because two
  detectors drift. Redaction remains a best-effort backstop, not a guarantee. If
  the cap is passed the child is killed, the verification does not pass, and the
  report's `output.complete` is `false`; truncated output is never presented as
  the whole of it.
- **A non-zero exit is a verification outcome, not an AIDO error.** It produces a
  structured `verification-result.v1` report, exit code **2**.
- **Post-execution workspace proof.** After the process terminates — including
  after a timeout or output-cap kill — the target is re-canonicalized, its bytes
  are re-read and re-hashed against the approved post-image, the **HEAD object id
  must be exactly the one the run started from**, every Git gate runs again, and
  the Git-visible state must still be exactly one unstaged modification of the
  approved path. Anything else is exit **3**.
- **Three distinct exit codes.** **1** = refused before any process started,
  stdout empty, workspace untouched. **2** = a process ran and verification did
  not pass, with the workspace still exactly the approved change. **3** = a
  process ran and the repository is no longer provably the approved state. Exit 3
  is **never** reported as "verification failed": nothing is repaired, nothing is
  restored, no `git restore` is run, nothing is retried, and a human must inspect
  the repository. A failing test that changes nothing stays at 2; a failing test
  that dirties the tree becomes 3.
- **An honest capability block.** Every AIDO-owned field carries an
  `orchestrator_` prefix and is hard `false`: no model call, no orchestrator
  network call, no GitHub, no shell, no Git mutation, no branch, commit, push or
  PR, no retry, no repair, no rollback, no reviewer. The child-scoped fields are
  **strings**, every one of them reading `"not sandboxed"` — because a boolean
  would invite `false`, and `network_called: false` as a claim about the whole
  invocation would be a lie.

**What Phase 5F2D explicitly does not claim.** That verification made no network
access; that it touched only allowed paths; that it launched no child processes;
that its child processes were terminated; that it could not reach credentials;
that it was side-effect free. The post-execution check proves the **Git-visible**
state of the repository. It does not detect changes to Git-ignored files, changes
outside the repository, pushes or other remote operations, network activity,
registry or system changes, services the verification left running, or any
filesystem effect Git does not report. That limitation is carried in the report
itself, not just here.

### Phase 5F2D-FU1 — corrections found in review

Phase 5F2D was reviewed before acceptance and five findings were returned. All
five are fixed, and — as in 5F2C-FU1 — **nothing was widened to fix them**. Two
were real defects; three were claims the implementation could not support.

- **The "hard wall-clock bound" was not a bound.** The runner read the output
  pipe on the main thread and relied on a `threading.Timer` that killed the
  direct child at the deadline. But the direct child is explicitly permitted to
  spawn descendants, and a descendant launched with inherited standard handles
  holds the **write end of the same pipe** — so killing or exiting the direct
  parent does not close it, and the main thread stayed blocked in `read()` until
  the descendant let go. Reproduced in this repository against a synthetic
  parent/descendant pair: **a 1.0s configured timeout returned after 60.30s**.
  The fix is narrow: the blocking read moved to a daemon thread, and the main
  thread waits on an event with a monotonic deadline; at expiry it kills the
  direct child, takes what was captured, and **returns** — abandoning the reader
  rather than waiting for it. Same pair, same timeout, after the fix: **1.03s**.
  The bound is on *AIDO's wait*, and the report now says exactly that:
  `aido_wait_bounded: true`, `direct_child_killed`, and
  `descendant_processes_terminated: "not tracked; descendants may still be
  running"`. **No process-tree management, job object, or `taskkill` was added**,
  and nothing claims descendants were stopped.
- **HEAD identity was not bound across the run.** The Git proof checked only that
  *a* HEAD existed before and after. A verification process running `git commit
  --allow-empty` moves the baseline commit while leaving the approved target as
  an unstaged modification — so the exact bytes, the single dirty path and the
  `" M"` status all still held, and the run reported success against a repository
  whose history had changed underneath it. The exact HEAD object id is now
  captured before launching, held in memory only, and required to be **exactly
  equal** afterwards; a moved or unreadable HEAD is exit **3**. The id is never
  reported — only `head_unchanged: true/false` — and nothing is reset, checked
  out, or restored.
- **Capability claims were globally scoped.** The block mixed correctly-scoped
  `orchestrator_*` fields with unscoped `committed`, `pushed`, `branch_created`,
  `git_mutation_performed` and others set to `false`. Under this phase's own
  model that was misleading: the child is not sandboxed and may run Git itself,
  and a `git push` leaves no trace in the final working tree. **Every** AIDO-owned
  negative claim now carries an `orchestrator_` prefix, and a test asserts that
  every key in the block starts with `orchestrator_` or `child_process_`. No
  attempt is made to *detect* the child's Git or network effects — that would be
  sandbox and process-audit scope, and it is not authorized.
- **`next_step` made unprovable global claims.** It said "Nothing was committed,
  nothing was pushed, no branch was created…", which cannot be established about
  an unsandboxed child. It now scopes what AIDO did, and states plainly that the
  child was not sandboxed and that effects outside the post-execution Git-visible
  state are not comprehensively observed.
- **`project_configured_secret_forwarding: false` overstated what was proved.**
  The environment really is a non-configurable minimal allowlist — that part was
  correct — but the configured argv is passed verbatim, so a project config could
  in principle place a literal credential in `args`. The field is now
  `environment_forwarding_configurable: false`, which is exactly what is proved,
  alongside a `configured_args_trust_note` stating that args are trusted
  configuration data, that AIDO does not prove an arbitrary argument string
  contains no sensitive literal, and that args are never echoed into the report.
  **No heuristic argv secret scanner was added.**

### Phase 5F2D-FU2 — corrections found in review

A final review of the same process runner returned three more findings: one
runtime defect and two claims that were not literally true. All three are fixed,
and again **nothing was widened**.

- **The output cap was not enforced when it was passed.** The reader called
  `stream.read(64 * 1024)` and tested the cap only *after* that call returned.
  `BufferedReader.read(n)` blocks until it has `n` bytes or reaches EOF, so a
  child that emitted more than the cap and then stopped writing was not detected
  — the read sat waiting for a 64 KiB buffer that would never fill. The
  documented contract ("the child is killed the moment the cap is passed") was
  therefore false, and the existing flood regression could not catch it because
  megabytes fill the request immediately. Measured against a real Windows pipe
  with a child that wrote 5001 bytes and slept: `read(65536)` returned after
  **30.1s** (only once the child exited); `read1(5001)` returned after
  **0.078s**. End to end with a 5,000-byte cap and a 20s timeout, the old
  strategy never detected the overflow at all and the run would have ended as a
  **timeout**; the fixed runner returns in **0.09s** with
  `output_limit_exceeded: true` and `timed_out: false`. The fix is a read
  *strategy*, not a framework: each iteration requests
  `min(remaining_allowance + 1, 64 KiB)` via `read1`, which performs one
  underlying read and returns as soon as any data is available, so the arrival of
  the single sentinel byte is itself the proof of overflow. **No asyncio, no
  selectors, no polling, no non-blocking mode.** The over-limit bytes are now
  **dropped rather than retained**, so the reported output is at most the
  configured cap exactly.
- **The configured timeout was not literally the whole worst-case wait.** After
  the deadline the runner sends one kill and may spend up to a fixed
  direct-child reap grace waiting for that one process handle. Rather than add
  process management to remove the grace, the contract is now stated exactly —
  *the configured timeout bounds the execution/capture wait; after it AIDO may
  spend at most the fixed reap grace on the direct child's handle; it never waits
  for descendants and never waits for the abandoned reader* — and the report
  carries `configured_timeout_seconds`, `direct_child_reap_grace_seconds` and the
  policy text. No measured timing and no process id is exposed.
- **The abandoned reader's lifetime was described as bounded.** It is not.
  Abandoning the daemon reader stops it from extending the *AIDO invocation*,
  which is the property FU1 added — but the thread and the pipe's read end may
  themselves stay alive as long as a descendant retains the inherited write
  handle, possibly indefinitely. Calling that "a bounded, known cost" conflated
  the two. It is now recorded as a **documented residual limitation**, and it was
  *not* "fixed" by killing, enumerating, or grouping descendants: **no job
  object, `taskkill`, process group, `psutil`, or process-tree manager exists.**

**L2 is still not complete.** Phase 5F2E (reviewer integration) remains
**unauthorized**, so the complete implement → verify → review → human loop does
not exist. There is still no model-backed implementer, no reviewer, no commit, no
push and no PR.

```text
5F2C  Controlled Single-File Writer      DONE
5F2D  Controlled Verification            DONE
5F2E  Reviewer Integration               NEXT
→ first controlled implement → verify → review → human loop
```

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
slot into 5F2B–5F2F.

**Phase 5F2B has since been completed as a library-only phase** — the
create-aware canonical write-target guard §26.3 showed was missing. The shipped
Phase 5D0 guard, `canonicalize_existing_path_under_workspace`, resolves with
`strict=True` and therefore cannot be handed a destination that does not exist
yet, so a `create` target had no guard at all.
`canonicalize_write_target_under_workspace` is the second entry point in
`ai_dev_orchestrator.workspace.canonical`:

- **The change type is declared, never inferred.** Exactly `"modify"` or
  `"create"`; delete, rename, mkdir, chmod and ownership changes are refused as
  inputs. `modify` against a path that has since vanished fails, and `create`
  against a path that already exists fails — the world disagreeing with an
  approval is a reason to stop, not to reinterpret.
- **`modify`** requires an existing **regular file** and runs the whole Phase
  5D0 machinery on it: the fail-closed lexical precheck before any filesystem
  use, root and intermediate reparse-point policy, strict resolution, and
  `commonpath`-based containment.
- **Win32 namespace aliases are refused on the string, before any filesystem
  call** (added by the 5F2B-FU1 follow-up, and applied to write targets only so
  Phase 5D0 read behavior is untouched): NTFS alternate data streams
  (`file.py:stream`, `file.py::$DATA`, never normalized to the base file),
  drive-relative `C:file.py` forms, reserved device names (`CON`, `NUL`,
  `COM1`–`COM9`, `LPT1`–`LPT9` and friends, case-insensitively and including
  with an extension), and the reserved characters `< > " | ? *` plus control
  characters. A fully-qualified `C:\repo\...` destination is unaffected —
  exactly one colon, the drive designator, is legitimate. Nothing is repaired,
  stripped, or probed.
- **`create`** canonicalizes the **parent directory** instead, which must
  already exist — **no directory is ever created** — requires the final
  component to be one plain file name, and establishes absence with `lstat`,
  requiring a genuine `ENOENT`. `os.path.exists` is deliberately not the
  decision: it calls a **dangling** symlink absent, and writing through one
  would leave the workspace.
- **The final component of a destination may never be a symlink or reparse
  point, in either `allow_symlinks` mode.** `allow_symlinks` is a policy about
  *traversal*; this is a rule about *destinations*.
- **The result is not authorization.** `CanonicalWriteTarget` is frozen and
  data-only — canonical root, canonical parent, destination, relative
  destination, change type, and whether the target existed. It describes the
  filesystem at the moment of the call; §26.3 requires a future writer to
  re-canonicalize immediately before each individual write. Phase 5F2B does not
  solve time-of-check/time-of-use and does not claim to.
- **No config field, no CLI command, no CLI option, no caller, no file created,
  no directory created, no temp file, no backup, no journal, no diff applied,
  no apply-cleanliness check, no file content read, no directory listing, no
  glob or tree walk, no subprocess, no Git invocation or Git-state inspection,
  no model call, no network call, no environment read, no GitHub access, and no
  approval stamping.** The Phase 5D0 entry point is unchanged, and its one
  caller behaves exactly as before.

**Phase 5F2C has since shipped the first controlled workspace write**, and
**Phase 5F2D the first controlled verification execution** — both described at
the top of this document. So the old statement that "5F2F remains the first
controlled workspace write" is history, not current status, and so is
"nothing here runs a project's own checks". **Phase 5F2E (reviewer integration)
remains proposed and not authorized**, and **L2 is still not complete**: nothing
here calls a model to implement, reviews, commits, pushes, or opens a PR.

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
a human to read; applying one is a separate act, behind a separate human
approval and the separate Phase 5F2C command described in the status section
above.

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
- No **complete L2 automation loop**, and no L3 automation at all. This is no
  longer "nothing acts on the plan": two commands do act, and only on artifacts a
  human approved in the exact required wording. `l2-apply-approved-file-edit`
  (Phase 5F2C) applies one approved modification to one tracked file, and
  `l2-verify-approved-file-edit` (Phase 5F2D) runs one project-configured
  verification process against it. Each requires its own project opt-in (both
  ship disabled) plus its own explicit consent flag, and each is invoked by a
  human, one step at a time. What is missing is the **loop**: Phase 5F2E reviewer
  integration is not authorized, so there is no reviewer, no fixer, no
  model-backed implementer, and no branch, commit, push or PR.
- No agent logic.
- No **general command execution**. Nothing creates a branch, commits, pushes, or
  opens a PR. There is no shell anywhere, no command string, no chaining, no
  pipeline, no redirection, no install or package-manager action, and nothing
  runs a model-proposed command or the L1 plan's `required_verification` — that
  field is planner prose and is **never** command authority. Exactly two
  subprocess capabilities exist, and both are narrow: the Phase 5F2C writer's
  **fixed, read-only** Git inspection set, which is part of that writer's own
  correctness contract and cannot be pointed at another program; and Phase
  5F2D's `l2-verify-approved-file-edit`, which launches **one** absolute
  executable named by a `controlled_verification` project opt-in that ships
  disabled, with an exact configured argv, once, bounded. That second one runs
  repository-controlled code by design — **it is controlled invocation, not a
  sandbox** — and the report never claims otherwise.
- No **general file editing**. Exactly one command writes into a configured
  target workspace — `l2-apply-approved-file-edit` (Phase 5F2C) — and it applies
  **one** approved modification to **one** tracked UTF-8 file in **one** clean
  Windows Git repository, behind its own project opt-in, with no create, no
  delete, no rename, no second file, no protected path and no fuzzy patching.
  Two other commands may *read* a workspace, both read-only and both only for
  paths an approved plan already named: `l2-inspect-workspace` (Phase 5D1)
  canonicalizes and `stat`s them, and `l2-read-workspace-files` (Phase 5D2)
  additionally opens regular files, within per-file/total byte caps and behind
  its own project opt-in, and prints their contents redacted. None of the three
  lists a directory, globs, or walks a tree.
- No **general patch or diff application**, and no fuzzy patch engine anywhere.
  Exactly one command applies a diff: `l2-apply-approved-file-edit` (Phase
  5F2C), which applies **one** human-approved `modify` diff to **one** tracked
  UTF-8 file **exactly** — no fuzz, no offset search, no nearest-match, no
  three-way merge, no repair — and refuses if the result does not hash to the
  approved post-image. `patch`, `git apply` and every other fuzzy applier are
  absent by design.
  **The proposal-generating commands still never apply their own output.**
  `generate-patch-proposal` (Phase 5E1) prints a prose-only patch proposal and
  `generate-diff-proposal` (Phase 5E3) prints real unified diff text; both are
  **deterministic, offline, and stdout only**, both leave
  `applies_cleanly_checked` false because they never ask, neither writes an
  artifact file, and neither stamps an approval. Their output is **data
  describing suggested work, never permission to do it** — turning it into a
  write takes a separate human approval in the exact Phase 5F0 wording, a
  project that has opted in via `workspace_write`, and a separate command.
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

### Applying one approved file edit (Phase 5F2C — the only command that writes)

```bash
python -m ai_dev_orchestrator l2-apply-approved-file-edit --project-config projects/my_project.yaml --approved-diff-proposal path/to/approved_diff_proposal.json --apply-approved-plan --write-approved-file
```

`l2-apply-approved-file-edit` is the **only** command in this repository that
modifies a file in a target project workspace. It reads two **local files** — the
project config and a human-approved `approved-diff-proposal.v2` artifact — and
applies **one** approved modification to **one** file.

It requires this block in the project config, shipped **disabled** and separate
from the two read-only opt-ins:

```yaml
workspace_write:
  enabled: false      # must be true; absent is identical to false
  max_file_bytes: 200000
```

There is deliberately no `allow_protected_paths`, no create flag, no multi-file
switch, and no rollback or journal setting — none of those capabilities exists
here to be turned on.

**The supported domain is exactly this.** Windows; a local Git working tree whose
top level *is* the configured `repo.workspace_path`; a valid `HEAD`; a **wholly
clean** repository; exactly one change; `change_type: "modify"`; a target that is
already tracked as one ordinary stage-0 blob; an existing regular file with no
reparse point, no unsupported Windows attribute and a hard-link count of exactly
one; a project with `allow_symlinks: false` and `deny_outside_workspace: true`; a
non-protected, non-forbidden, policy-allowed path; ordinary UTF-8 text with one
uniform line-ending style and a terminal newline, inside `max_file_bytes`; the
on-disk bytes hashing to the approved `pre_image_sha256`; and the strictly
applied diff hashing to the approved `post_image_sha256`. **Everything else fails
closed.**

The gate fails closed in order. `--apply-approved-plan` and
`--write-approved-file` are checked **first** — without either, the command exits
non-zero having read nothing at all. Then the config loads. Then
`workspace_write.enabled`. Then the Windows-only platform check (all three before
any workspace touch). Then `--approved-diff-proposal` is rejected if it is the
configured `repo.workspace_path` or sits under it, **before it is read or
stat'd**. Then the strict parse. Then identity matching in all six places the
artifact records it, the exactly-one-`modify` rule, the lexical write policy, the
canonical write-target guard, the file's kind/attributes/link count, the clean
Git baseline, the simple-index contract, the tracked-target proof, the pre-image
digest, the strict diff application, and the post-image digest — and then all of
the filesystem and Git facts are **re-established from scratch immediately before
the write**.

**The diff is applied exactly.** No `patch`, no `git apply`, no fuzzy engine.
Hunk locations are exact, every context and deleted line must match byte for
byte, and there is no offset search, no fuzz, no nearest-match, no three-way
merge and no repair. If the result does not hash to the approved post-image, the
write is refused as an internal inconsistency.

**After the write**, the bytes are re-read and must hash to the approved
post-image, the file's Windows attributes must be unchanged, and Git must report
**exactly** the approved path as an unstaged modification and nothing else.

`l2-apply-approved-file-edit` **does not**:

- create, delete, rename, or move any file, or create any directory,
- write more than one file, whatever `workspace_policy.max_changed_files` allows,
- write a protected or forbidden path — there is no flag and no config field that
  permits one,
- apply a diff with fuzz, offset, or repair,
- run `required_verification`, pytest, npm, make, a build script, or any other
  project-configured or model-proposed command — the only subprocess it can cause
  is its own closed set of fixed, read-only Git inspection commands. Verification
  is a **separate** command with its own opt-in and its own consent flag; the
  writer gained no verification flag in Phase 5F2D and never will,
- invoke a shell, or run any program other than `git`,
- call a model, send source to a model, open a socket, or contact GitHub,
- create a branch, commit, push, or open a PR — the change is left
  **uncommitted** for human review,
- roll back, retry, write a backup or a journal, or run `git restore`,
- print the configured workspace path, any absolute path, the raw artifact text,
  the approval text, the approved diff, any unrelated source file, any digest,
  an API key, or a base URL.

**Exit codes are distinct on purpose:**

| Code | Meaning |
| --- | --- |
| `0` | The write happened **and** every postcondition was proved. stdout is the result report. |
| `1` | **Refused before any write.** The target is unchanged. stderr names the category; stdout is empty. |
| `3` | **A write was attempted and its final state could not be proved.** This is *not* a claim that nothing changed. Nothing was retried or rolled back — a human must inspect the repository against the clean baseline the run proved beforehand. |

**Concurrency is not solved.** Phase 5F2C supports one AIDO writer against a
quiescent workspace. There is no lock, no watcher and no cross-process protocol;
a concurrent edit is *detected* by revalidation and causes a failure, which is
not the same as being safe against one.

### Verifying one approved file edit (Phase 5F2D — the only command that executes project code)

```bash
python -m ai_dev_orchestrator l2-verify-approved-file-edit --project-config projects/my_project.yaml --approved-diff-proposal path/to/approved_diff_proposal.json --apply-approved-plan --verify-approved-file-edit
```

`l2-verify-approved-file-edit` is the **only** command in this repository that
executes repository-controlled code. It reads the same two **local files** — the
project config and the human-approved `approved-diff-proposal.v2` artifact whose
modification has **already been applied** — proves the workspace is exactly that
approved state, runs the project's configured verification process **once**, and
proves the workspace state again afterwards.

It requires this block in the project config, shipped **disabled** and separate
from every other opt-in:

```yaml
controlled_verification:
  enabled: false                                   # must be true; absent is identical to false
  executable: "C:\\absolute\\path\\to\\python.exe" # absolute, existing, regular file, OUTSIDE the workspace
  args:                                            # the exact ordered argv tail, used verbatim
    - "-m"
    - "pytest"
    - "tests/test_targeted.py"
    - "-q"
  timeout_seconds: 120
  max_output_bytes: 200000
```

There is deliberately no shell command string, no working-directory override, no
PATH lookup, no executable default, no interpolation or `{path}` templating, no
environment or secret forwarding field, no second command profile, no command id,
and no before/after hook. The resulting argv is exactly
`[executable, *args]` and nothing else.

> **This is controlled invocation, not sandboxing.** The launched process can
> import arbitrary project modules, execute `conftest.py`, create files, open
> network connections and spawn children — and those children are **not tracked
> and may still be running** after the command returns. AIDO does not confine it.
> What AIDO controls is *which* program runs, with *which* arguments, in *which*
> directory, with *which* minimal environment, how long **AIDO waits**, and how
> much output it may produce.

**`required_verification` is never command authority.** The L1 plan carries it,
a model may have written it, and this command never splits it, parses it as shell
syntax, runs it, or turns it into argv. It is counted in the report and otherwise
ignored.

**The child environment is a fixed minimal allowlist** of OS/runtime variables.
No `AIDO_LITELLM_*`, no `GITHUB_TOKEN`, no API key, no database or cloud
credential, and **no project-configurable environment forwarding mechanism
exists**. A project whose tests require credentials is outside this first
supported domain and may fail; that is accepted. That claim is about the
*environment*: the configured `args` are trusted configuration data used
verbatim, and AIDO does **not** prove that an arbitrary argument string contains
no sensitive literal. It does not scan them, and it never echoes them into the
report — only their count.

**Before anything is launched**, the command proves: exactly one `modify` change
matching this project in all six identity places; the lexical write policy; the
canonical write-target guard; an existing regular file; an absolute Git
executable pinned for the run; the Git configuration gate; a simple,
submodule-free index; the target tracked as one ordinary stage-0 blob; the file's
exact bytes hashing to the approved `post_image_sha256`; and a Git-visible dirty
state that is **exactly** the approved target, as a plain unstaged modification.
The exact `HEAD` object id is captured at the same time.

```text
writer baseline:        zero dirty paths
verification baseline:  exactly one dirty path — the approved target,
                        on a pinned HEAD commit
```

**After the process terminates** — including after a timeout or output-cap kill —
all of it is re-proved, including that `HEAD` is **exactly** the commit the run
started from. Any additional staged, unstaged, untracked, deleted, renamed,
unmerged or submodule state, or any movement of `HEAD`, means the workspace is no
longer trustworthy. A `git commit --allow-empty` inside the verification is exit
**3** even though the target's bytes and dirty status are untouched.


**Output is bounded during capture and redacted before it is reported.** stderr
is merged into stdout so one pipe makes bounded reading deadlock-free; passing
the cap kills the direct child **at the moment it is passed**, fails the
verification, and sets `output.complete` to `false` — truncated output is never
presented as complete, and the over-limit bytes are dropped rather than kept, so
the reported output is at most the configured cap exactly.

**The timeout bounds AIDO's wait, not the child's life.** Precisely: the
configured timeout bounds the execution and output-capture wait; after that
deadline AIDO sends one kill to the direct child and may spend at most a fixed
direct-child reap grace on that one process handle. It never waits for
descendants, and never for the abandoned output reader. AIDO does not enumerate,
signal, or track descendants — they may still be running afterwards, and the
report says so instead of claiming they were terminated. The abandoned reader
thread and its pipe handle may likewise remain alive for as long as a descendant
holds the inherited write handle; that is a documented residual limitation, not
something this phase closes.

`l2-verify-approved-file-edit` **does not**:

- write, create, delete, rename or move any file in the workspace,
- run anything other than the one configured executable — no shell, no second
  command, no fallback, no retry, no PATH search, and no command taken from an
  artifact, a plan, a model, or the command line,
- accept a `--command`, `--executable`, `--args`, `--shell`, `--force`,
  `--repair`, `--retry`, `--commit`, `--push`, `--pr` or `--model` option, because
  none exists,
- repair, restore, clean, `git restore`, `git checkout`, stage, commit, push,
  branch, or open a PR,
- call a model, open a socket from the orchestrator, or contact GitHub,
- claim the verification process made no network access, touched only allowed
  paths, spawned no children, had its children terminated, could not reach
  credentials, or was side-effect free.

Every negative claim the report *does* make about branches, commits, pushes, PRs,
Git mutation, retries and repair is explicitly scoped to AIDO with an
`orchestrator_` prefix. The child may have done any of those things; AIDO does
not observe them and does not pretend to.

**Exit codes are distinct on purpose:**

| Code | Meaning |
| --- | --- |
| `0` | Verification **passed**, and the workspace still holds exactly the approved change. stdout is the result report. |
| `1` | **Refused before any process started.** Nothing was launched; stderr names the category, stdout is empty. |
| `2` | **A process ran and verification did not pass** — non-zero exit, timeout, or output cap. The workspace is still exactly the approved change. stdout is the structured result. |
| `3` | **A process ran and the repository is no longer provably the approved state.** Never reported as "verification failed". Nothing was repaired, restored, or retried; a human must inspect the repository. |

**What the post-execution check does not detect:** changes to Git-ignored files,
changes outside the repository, pushes or other remote operations, network
activity, registry or system changes, services or child processes the
verification left running, and any filesystem effect Git does not report. That
limitation is carried in the report itself.

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

**Phase 5F2B** then added the first of those five, **library only**: the
create-aware canonical write-target guard described in the status section above.
It extends the Phase 5D0 module with `canonicalize_write_target_under_workspace`
so a `create` destination can be validated at all, and it is wired into nothing
— no command, no option, no config field, no caller, **no file or directory
created, and no write**.

**Phase 5F2C** then superseded that roadmap and shipped the **first controlled
workspace write**, `l2-apply-approved-file-edit`, described in the status and
usage sections above. The old plan — 5F2C typed gate models, 5F2D custom
Git-state reader, 5F2E standalone preflight, 5F2F generalized transactional
writer — was replaced by a minimum safe vertical slice after an independent
roadmap review (design doc §27, which supersedes §26.12 while preserving it as
history). Phase 5F2C evolved the concrete diff artifact to bind exact pre-image
and post-image identities, added a strict no-fuzz applier and a fixed read-only
Git adapter, gated the whole thing behind a `workspace_write` opt-in that ships
disabled, and refuses every case outside its narrow domain.

**Phase 5F2D** then shipped the **first controlled verification execution**,
`l2-verify-approved-file-edit` — the first separately authorized capability to
run repository-controlled code, bound on both sides to the exact already-applied
approved change, with the command coming only from a `controlled_verification`
project opt-in that ships disabled.

**L2 is not complete.** The near-term sequence is:

```text
5F2C  Controlled Single-File Writer      DONE
5F2D  Controlled Verification            DONE
5F2E  Reviewer Integration               NEXT
→ first controlled implement → verify → review → human loop
```

**Phase 5F2E remains unauthorized**, so the complete
implement → verify → review → human loop does not exist. Until it is explicitly
authorized, the project continues to avoid agent automation, arbitrary command
execution, model-backed implementation, reviewer/fixer wiring, GitHub writes,
GitHub issue fetching inside a real model command, branches, commits, pushes, and
PRs. Project verification execution is now available, but only in the single,
config-authorized, bounded form Phase 5F2D describes. Generalized writer expansion
— multi-file, `create`, protected-path writes, transactions, journals, rollback,
crash recovery and concurrency — resumes only after that loop exists, and **no
generalized writer work is inserted between 5F2D and 5F2E**.
