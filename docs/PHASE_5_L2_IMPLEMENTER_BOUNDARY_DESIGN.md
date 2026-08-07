# Phase 5A — L1-to-L2 Implementer Boundary (Design Review Only)

> **This document is a design review only. Phase 5A implements nothing.**
>
> It contains **no implementation**, adds **no runtime behavior**, adds **no CLI
> command and no CLI option**, makes **no model call**, makes **no network
> call**, reads **no environment variable**, constructs **no `LLMClient`**,
> fetches nothing from GitHub and writes nothing to GitHub, executes **no
> command**, edits **no file**, adds **no agent logic** and **no
> implementer/reviewer/fixer role wiring**, and reads, lists, stats, or resolves
> **no target project workspace**.
>
> **L2 remains proposed, not built.** Nothing described here is authorized to be
> implemented by this phase. Every sub-phase in §13 (Phase 5B and later) is a
> *proposal* and requires its own explicit authorization. (Phase 5B has since
> been authorized and implemented as **typed models and a parser only** — §15.
> Phase 5C onward remain proposals, and L2 is still not built.)
>
> **L2 may not be invoked by any existing command after this phase.** After
> Phase 5A the shipped CLI surface is exactly what Phase 4L left behind —
> `version`, `inspect-issue`, `llm-smoke-test`, `generate-plan`,
> `real-llm-smoke-test`, `generate-model-plan` — and none of them gains an L2
> path, an `--apply` flag, or any other way to reach an implementer.
>
> It refines item **"Phase 5 — docs-only L2 implementer"** of
> [AI_DEV_ORCHESTRATOR_PLAN.md §7](AI_DEV_ORCHESTRATOR_PLAN.md#7-mvp-phase-roadmap)
> and picks up where
> [PHASE_4_L1_PLAN_GENERATOR_PLAN.md](PHASE_4_L1_PLAN_GENERATOR_PLAN.md) stops.
>
> **Phase 5B is now DONE** (§15). It implemented the §3 artifact as **typed
> models and a strict parser only** — no CLI behavior, no file loading, no
> workspace access, no model/network/environment access, and no L2 action.
> **Phase 5C and every later sub-phase in §13 remain proposed and not
> authorized.**

## 1. Goal

Design how a **future, separately authorized** L2 implementer could consume an
**approved** `L1Plan` and produce a **bounded implementation patch**, without
weakening any Phase 4 safety property.

The framing is deliberately narrow. Phase 4 ends with a plan artifact and a
human who must read it. Phase 5 asks one question: *what would have to be true
before any code could act on that artifact at all?* This document answers that
question and stops there.

To restate the boundary conditions of this phase explicitly:

- **Phase 5A implements nothing.** No module, no function, no test, no config
  field, no CLI surface.
- **No runtime behavior is added.** Importing the package behaves exactly as it
  did at Phase 4L; running any command behaves exactly as it did at Phase 4L.
- **L2 remains proposed, not built.** The handoff artifact in §3, the approval
  gate in §4, the capability stages in §5, and the phase split in §13 are
  designs, not commitments, and none of them is authorized.
- **L2 may not be invoked by any existing command after this phase.** There is
  no L2 entry point to invoke. When one eventually exists it will be a
  **separate command** (§4), never a flag bolted onto `generate-plan` or
  `generate-model-plan`.

### What L2 means here

[AI_DEV_ORCHESTRATOR_PLAN.md §4](AI_DEV_ORCHESTRATOR_PLAN.md#4-automation-levels)
defines L2 as *"local branch + implement + local commit."* This document treats
that definition as the **eventual** end state of a long sequence, not as the
first thing to build. The first useful L2 increment is much smaller than
"implement and commit": it is *read an approved plan, prove you understood its
boundaries, and print what you would do*. Everything past that is a separate
authorization.

## 2. Relationship to Phase 4

### 2.1 What Phase 4 now provides

Phase 4 shipped four things that Phase 5 would build on, and nothing else:

- **An offline `generate-plan` command** (Phase 4D,
  [cli.py](../src/ai_dev_orchestrator/cli.py)). It reads exactly two local files
  — `--project-config` and `--body-file` — parses the body with the Phase 2
  `parse_issue_body`, synthesizes an in-memory `GitHubIssue`, and runs the
  deterministic Phase 4C
  [`FakeL1Planner`](../src/ai_dev_orchestrator/plan/fake_planner.py). No GitHub
  fetch, no model call, no environment read, no workspace read.
- **A fake / model-backed library path** (Phases 4F and 4G,
  [plan/model_planner.py](../src/ai_dev_orchestrator/plan/model_planner.py)):
  the pure prompt builder `build_model_l1_plan_request(...)`, the
  `ModelBackedL1Planner` that takes an **injected** client, and the strict
  parser `parse_model_l1_plan_response(...)` that rejects — never repairs —
  invalid or policy-violating output. Library only; wired into nothing.
- **A gated real smoke command** (Phase 4K), `real-llm-smoke-test`: the first
  command permitted to open a real socket, behind `--real-model` plus a project
  opt-in and an exact model allowlist, sending a fixed connectivity prompt and
  no issue text.
- **A gated real L1 plan command** (Phase 4L), `generate-model-plan`: a separate
  command that does transmit the `--title` value and the local `--body-file`
  text to a real model, behind the same gate, and returns a plan.

And the property that matters most:

- **Every output remains L1 only and requires human approval.** `L1Plan`
  ([plan/models.py](../src/ai_dev_orchestrator/plan/models.py)) fixes
  `automation_level` to `"L1"` and `requires_human_approval` to `True` at the
  model level. Both the fake planner and the real one get those values from the
  orchestrator, never from model output; the Phase 4F parser **rejects** a
  response that even supplies them, so an injection attempt surfaces instead of
  being silently ignored.

### 2.2 The critical boundary

Three statements define the whole L1/L2 seam. Any future L2 design that
contradicts one of them is wrong.

**`L1Plan` is not executable instructions.** It is a description of intended
work, written for a human. `proposed_steps` is prose. `files_likely_to_change`
is a list of plain strings that were never resolved, stat'd, globbed, or
normalized — Phase 4B is explicit about this, and Phase 4C infers them from
path-shaped *tokens in issue text*, which is to say from untrusted input. A
future L2 must treat every one of those fields as a **hint to validate**, never
as a command to run or a path to trust.

**A real model plan is still only text for human review.** `generate-model-plan`
changes the *engine* that produced the words. It does not change their status.
A plan produced by a real model has exactly the same authority as one produced
by `FakeL1Planner`: none. The gate in Phase 4J/4K/4L authorizes *a model call*,
not *an action*, and §9 below states plainly that Phase 4L's authorization does
not extend to L2 in any form.

**Future L2 must require explicit human approval of a specific `L1Plan`
artifact before doing anything.** Not "an approved plan exists somewhere". Not
"the issue said automation was authorized". A *specific*, *saved*, *identified*
plan artifact that a *named human* approved, matched against the *exact*
project, repo, and issue L2 was asked to act on. §3 designs the artifact and §4
designs the gate.

### 2.3 What Phase 4 deliberately did not solve

Phase 5 inherits two open problems from Phase 4, both of which matter more once
writes are on the table:

- **Path handling is lexical.** See §6.4.
- **Prompt injection through issue text is contained, not eliminated.** Phase 4G
  wraps issue text in untrusted-data delimiters and Phase 4F rejects
  policy-violating output, but a plan whose *content* is adversarial is still a
  valid plan. See §12.

## 3. L1-to-L2 handoff artifact

**Typed in Phase 5B** — see §15. The shape below is now
[handoff/models.py](../src/ai_dev_orchestrator/handoff/models.py):
`PlanApproval`, `L1PlanProvenance`, `ApprovedL1PlanArtifact`, and the strict
parser `parse_approved_l1_plan_artifact`. Typing it added **models and a parser
only**: nothing loads such an artifact from disk, nothing consumes one, and no
command can reach it.

### 3.1 Suggested future shape

```jsonc
{
  "approval": {
    "approved_by": "...",
    "approved_at": "...",
    "approval_text": "I approve this L1 plan for L2 implementation",
    "source": "manual"
  },
  "plan_provenance": { /* engine, model, endpoint host, generated_at, ... */ },
  "plan": { /* ... the L1Plan, verbatim ... */ },
  "project_id": "...",
  "repo": "...",
  "issue_number": 42
}
```

### 3.2 Wrapper metadata vs `L1Plan` fields

The approval **must not** live inside `L1Plan`. This is the same call Phase 4H
§9.1 made for provenance, for the same reason, and it is even more important
here.

`L1Plan` is the shape a *planner* produces, and one of the two planners is a
model. Every field on that model is a field an adversarial or confused model
could try to fill in. Phase 4F already had to add explicit rejection of
model-supplied `automation_level` and `requires_human_approval`; adding an
`approved_by` field to `L1Plan` would create a third such trap, and a far worse
one — a model that writes `"approved_by": "the user"` into its JSON would be
attempting to forge consent.

So: **`L1Plan` stays exactly as Phase 4B defined it.** Approval, provenance, and
identity are **wrapper** fields, produced by the orchestrator and by a human,
sitting *around* an untouched plan. The wrapper is the only place a future L2
looks for authority, and the plan is the only place it looks for content. A
model can influence the second and can never influence the first.

### 3.3 Immutable plan snapshot

The `plan` field is a **snapshot**, not a reference. It carries the full plan
text as it stood when the human read it. Consequences:

- The human approves **the bytes they saw**, not a plan id that might resolve to
  something else later.
- A future L2 that reads the wrapper is reading the reviewed content by
  construction; there is no second fetch that could return different text.
- A future phase may add an integrity check over the snapshot (a digest in the
  wrapper, recomputed at load). This is worth doing but is **not** a substitute
  for the checks in §4 — a digest proves the plan was not edited after approval,
  which is a different claim from "a human approved this plan for this issue".

### 3.4 Why L2 should consume a saved artifact, not re-run planning

The tempting shortcut is a single command that plans and then implements. It
must be rejected, and the reasons compound:

- **Re-planning silently discards the review.** If L2 re-runs the planner, the
  plan it acts on is not the plan the human read. With a real model in the loop
  this is not even deterministic — the same issue can produce different plans on
  two calls.
- **It destroys the audit trail.** "Which plan was approved?" must have a
  file-shaped answer.
- **It fuses two authorizations into one.** Phase 4L authorizes a model call.
  A future phase would authorize workspace action. Fusing them means a single
  invocation crosses both boundaries with one confirmation, which is exactly the
  pattern the separate-command decision in Phase 4H §6 exists to prevent.
- **It reintroduces the untrusted path at the worst moment.** Planning consumes
  issue text — untrusted input. Implementation touches a workspace. Keeping a
  human-reviewed artifact between them is the only thing that stops untrusted
  text from reaching a write path in one hop.

So a future L2 takes `--approved-plan <path>` and **has no planning options at
all**: no `--body-file`, no `--title`, no `--model`, no `--issue` to plan from.
If the plan is missing, L2 stops. It never generates one.

### 3.5 Exact plan/repo/issue matching

L2 would be invoked with a project config *and* a plan artifact. Those two are
independent inputs that can disagree, so every identity field is checked for
**exact** equality — string equality, no normalization, no case folding, no
prefix matching, no globbing — mirroring the Phase 4J model-allowlist decision:

- `wrapper.project_id` == `ProjectConfig.project_id`
- `wrapper.repo` == `ProjectConfig.repo.github_repo`
- `wrapper.repo` == `wrapper.plan.repo`
- `wrapper.issue_number` == `wrapper.plan.issue_number`

Any mismatch is a hard stop with no action taken. The failure mode this prevents
is concrete and easy to hit by accident: a plan approved for `mis_project`
issue 42 being applied against the `a8_oa` workspace because the operator passed
the wrong `--project-config`.

### 3.6 Approval cannot be inferred from the presence of a file

**Writing a file is not approving a plan.** A future L2 must never treat "the
artifact exists", "the artifact parsed", or "the artifact has an `approval` key"
as approval. It must find, inside that block:

- a non-blank `approved_by`,
- a parseable `approved_at`,
- an `approval_text` matching the **exact required phrase**, and
- a `source` from a fixed, closed enum whose only initially permitted value is
  `"manual"`.

Anything else — a missing block, an empty block, a null field, a paraphrased
approval sentence, an unrecognized `source` — is **not approval**, and L2 stops.
Note the asymmetry this creates on purpose: it is trivially easy for a human to
approve a plan deliberately, and impossible to approve one by accident.

Two corollaries, restated because they are the ones most likely to be eroded
later:

- **The orchestrator never writes an `approval` block itself.** If a future
  phase adds a convenience command that stamps approval, that command is the
  approval act, it must demand an interactive confirmation, and it must be
  designed and authorized on its own — not folded into a plan generator.
- **A model may never populate any field under `approval`.** If a model-produced
  payload contains an `approval` key at any nesting level, that is an attempted
  forgery: **reject the artifact**, do not strip the key and continue.

## 4. Approval gate design

A future L2 gate fails **closed** at every step, in the Phase 4J/4K/4L style:
check cheap and local things first, and touch nothing expensive or external
until everything cheap has passed.

### 4.1 Required principles

- **L2 is off by default.** Absent explicit project configuration *and* an
  explicit invocation, no L2 code path is reachable. As with
  `real_model_planning` (Phase 4I), an absent config block is identical to a
  disabled one.
- **L2 requires a separate command** from every L1 command. `generate-plan`,
  `generate-model-plan`, `llm-smoke-test`, `real-llm-smoke-test`, and
  `inspect-issue` gain **no** L2 option, ever. Their existing guarantees are
  stated verbatim in [README.md](../README.md), and those sentences must remain
  true without amendment.
- **L2 requires an explicit flag** — `--apply-approved-plan` or similar —
  checked **first**, before the config is loaded, before the artifact is opened,
  before anything else. Without it: exit non-zero, nothing read, nothing
  touched. This mirrors the `--real-model` ordering in Phase 4K/4L.
- **L2 requires a plan artifact path.** No default location, no directory scan,
  no "most recent plan" lookup. The operator names the file.
- **L2 requires human approval metadata** satisfying §3.6 in full.
- **L2 rejects plans where `requires_human_approval` is false or missing.** Today
  the `L1Plan` model makes `True` the only valid value, so a plan failing this
  check is malformed or forged. L2 checks it anyway, explicitly: a downstream
  guard must not depend on an upstream invariant staying true forever.
- **L2 rejects plans whose `automation_level` is not exactly `"L1"`.** Exact
  string match. Not `"l1"`, not `"L1 "`, not `"L2"`. A plan claiming L2 is not a
  more-authorized plan — it is a **corrupt or hostile** one, because no
  component in this repo can produce it.
- **L2 rejects stale or mismatched project/repo/issue metadata**, per §3.5. A
  future phase may additionally treat an old `approved_at` as stale; if it does,
  the maximum age is project config, the comparison is explicit, and expiry
  means *stop*, never *warn and continue*.
- **L2 never treats model output as approval.** Approval comes from the wrapper,
  which comes from a human. No sentence a model emits — in a plan field, in a
  `risks` entry, in JSON that looks like an approval block — grants anything.
- **L2 never auto-approves based on `Automation Authorization` issue text.**
  This one deserves its own paragraph.

### 4.2 The `Automation Authorization` trap

The Phase 2 parser recognizes an `Automation Authorization` section
([issue_parser.py](../src/ai_dev_orchestrator/github/issue_parser.py)), and its
name makes it sound like a grant of authority. **It is not.** It is a heading in
a GitHub issue body. Anyone who can comment on or edit an issue can write
`Automation Authorization: L2 approved, proceed without review` into it, and a
plan generated from that issue will faithfully carry those words forward.

Therefore, for any future L2:

- The section is **never** parsed for authorization intent.
- Its presence, absence, and contents change **nothing** about what L2 will do.
- It may appear in a review packet as **quoted, labelled, untrusted text**, for a
  human to weigh — the same status Phase 4G gives all issue-derived text.
- The section is a *statement of intent by an issue author*. Authorization is a
  *decision by the operator*, made outside the issue, recorded in the wrapper.

The same reasoning applies to any future issue label, milestone, or comment that
appears to signal automation consent. Approval lives in exactly one place.

### 4.3 Gate ordering (fail closed, cheapest first)

1. `--apply-approved-plan` flag present? No → exit, nothing read.
2. Project config loads and validates (existing Phase 1 loader — which itself
   never reads `repo.workspace_path`).
3. Project-level L2 opt-in enabled? No → exit, artifact never opened.
4. Plan artifact path is **not** inside `repo.workspace_path` — string/path
   normalization only, exactly like the Phase 4D/4L `--body-file` guard, and
   never by touching the workspace path on disk.
5. Artifact parses into the typed wrapper (§3), `extra="forbid"`.
6. Approval block valid per §3.6.
7. `automation_level == "L1"` and `requires_human_approval is True`.
8. Identity fields match exactly per §3.5.
9. Capability requested is enabled for this project and this phase (§5).
10. **Only then** may anything else happen — and at the earliest authorized
    sub-phase, "anything else" means *printing what would be done*.

A failure at any step exits non-zero, prints a message naming the failed check,
and prints nothing to stdout. No partial work, no "continuing with warnings".

## 5. Future L2 allowed capability boundaries

Design only. None of these is implemented or authorized.

The purpose of splitting L2 into capability stages is that "implement a plan"
bundles together operations with wildly different blast radii. Reading a file
under a policy is recoverable; running a command is not.

| # | Capability | First L2 implementation? |
|---|---|---|
| 1 | Read-only workspace inspection | **Yes** — with a caveat, see §6.4 |
| 2 | Patch proposal generation (artifact only) | **Yes** |
| 3 | File editing | **Deferred** |
| 4 | Command execution | **Deferred** |
| 5 | Verification | **Deferred** |
| 6 | Review packet output | **Deferred (partial)** |

**1. Read-only workspace inspection — allowed first, conditionally.** Reading
listed files under the project's `allowed_paths` is the smallest capability that
makes L2 more useful than L1, because it is the first time the orchestrator can
check a plan against reality: does `src/foo/bar.py` exist, does the function the
plan names appear in it, is a "small change" actually small. It is also the
first capability that touches a target workspace at all, which is why §6.4's
canonicalization question must be settled **before** it ships, not after.

**2. Patch proposal generation — allowed first.** A patch *proposal* is an
artifact: a unified diff, or a list of intended edits, written to a path
**outside** the workspace and never applied. It carries most of the value of L2
(a human sees concrete changes instead of prose) at a fraction of the risk (an
unreviewed proposal changes nothing). If a proposal is wrong, the cost is a
discarded file.

**3. File editing — deferred.** The first write to a target workspace is the
single largest step-change in this project's risk profile, and it should not
share a phase with anything else. It needs the write-path policy of §6, the
`max_changed_files` cap, a dirty-tree check, and its own authorization.

**4. Command execution — deferred, and deferred *after* file editing.** Running
a process is the only capability whose blast radius is not bounded by the path
policy at all. See §7.

**5. Verification — deferred.** Verification is command execution wearing a
different hat, and gets the same treatment (§7), plus a rule keeping the two
allowlists separate.

**6. Review packet output — deferred, but partially available early.** A packet
summarizing inspection findings and a patch proposal is worth having as soon as
stages 1–2 exist. The *full* packet of §11 needs diffs, command output, and
verification status, so the complete form waits for those stages.

### Recommendation

**The first L2 implementation should be read-only workspace inspection plus a
patch proposal artifact — not direct file writes.** Direct file edits and
command execution belong in later, separately authorized sub-phases.

This is the same shape Phase 4 used to good effect: `FakeL1Planner` before any
model, `MockTransport` before any socket, a library gate before any command.
Each step was small enough to review completely. An L2 that reads a workspace
and writes a diff to a scratch file is reviewable in the same way. An L2 that
edits files and runs commands on its first outing is not.

## 6. Workspace access policy for future L2

Design only. Today **nothing** in this repo reads a target workspace, and Phase
5A does not change that.

### 6.1 Which workspace, and when

- L2 may access **only** the `repo.workspace_path` configured for the **selected
  project**, and only after the §4 gate has fully passed.
- **Never another project's workspace.** `C:\dev\mis_project`, `C:\dev\a8_oa`,
  and `C:\dev\bible_reading_v2` are separate projects; holding an approved plan
  for one grants nothing anywhere else.
- **Never `C:\dev` itself or any parent.** A path resolving to or above the
  parent directory is a hard boundary violation, not a policy warning.
- The workspace root comes from **config**, never from a plan field, never from
  a command-line override, and never from issue text.

### 6.2 Path rules

Within that root, the existing Phase 1 precedence applies —
**forbidden > protected > allowed > unlisted**, as implemented in
[workspace/path_policy.py](../src/ai_dev_orchestrator/workspace/path_policy.py):

- **Refuse anything outside `allowed_paths`.** Unlisted is not neutral; it is
  denied. `PathPolicy.check_write` already behaves this way.
- **Require extra approval for `protected_paths`.** `check_write` exposes this
  as `allow_protected`, and `check_read` flags protected reads as requiring
  authorization. For L2 that approval must be **per-invocation and explicit**,
  not a config flag someone sets once and forgets.
- **Always refuse `forbidden_paths`**, with no override, no escalation flag, and
  no "authorized protected" equivalent.
- **Enforce `workspace_policy.max_changed_files`.** It defaults to 20. It is
  checked against the **proposed** change set *before* any write begins — a run
  that would exceed the cap fails entirely rather than writing the first N files
  and stopping. Partial application of a plan is a worse outcome than no
  application.
- **Honor `workspace_policy.deny_outside_workspace`** and
  `workspace_policy.allow_symlinks` (§6.4).

### 6.3 Centralize the checks

Every path decision goes through **one** module. Not one per command, not one
per capability. Phase 4 already shows the cost of duplication: `_is_same_or_under`
in [cli.py](../src/ai_dev_orchestrator/cli.py) exists separately from
`PathPolicy` because they answer different questions, and both `generate-plan`
and `generate-model-plan` now carry their own copy of the same guard call. With
two commands and one guard that is manageable; with six capabilities and three
guards it is a latent divergence bug in which one caller quietly misses a check.

The rule for any future L2: **a capability that touches a path calls the policy
module and cannot proceed without a `PathDecision`.** No direct `open()`, no
direct `Path.read_text`, no ad-hoc string comparison in a command body.

### 6.4 The known Phase 4 string-normalization gap

Phase 4's path handling is **lexical by design and by necessity**.
`PathPolicy.normalize` splits on separators, resolves `.` and `..` in memory,
casefolds for comparison, and matches glob patterns with `fnmatch` — it never
touches disk. `_is_same_or_under` uses `os.path.abspath` + `os.path.normcase`,
which join and normalize but perform no filesystem access. That was the right
call for Phase 4: the whole point was to evaluate paths for `C:\dev\mis_project`
**without ever touching that folder**, and a lexical check cannot be tricked into
touching it.

The gap is that a lexical check is only sound when nothing on disk redirects a
path. It does not account for:

- **Symlinks and NTFS junctions / directory reparse points.** A junction at
  `<workspace>\vendor` pointing at `C:\dev\a8_oa` passes every lexical check and
  lands outside the workspace. `workspace_policy.allow_symlinks` defaults to
  `False`, but today that flag is only *exposed* by `PathPolicy.allow_symlinks`
  — filesystem checks are explicitly deferred, and nothing enforces it, because
  nothing reads a workspace.
- **UNC paths** (`\\server\share\...`). `_DRIVE_RE` matches a drive letter;
  `_split` drops empty components, so the leading `\\` is lost and a UNC path
  can normalize into something that compares against a local root in unintended
  ways.
- **Mapped network drives.** `Z:\` and `\\server\share` can be the same
  location; lexically they share nothing.
- **8.3 short names** (`MIS_PR~1`) and other Windows aliasing, including
  trailing dots/spaces and the `\\?\` prefix form, all of which name the same
  file with different strings.
- **Case sensitivity assumptions.** Casefolding is right for typical Windows
  volumes and wrong for case-sensitive ones.

**Decision: yes — canonicalization must be strengthened before any
write-capable phase, and before read-only inspection.** The reasoning is that
the moment L2 touches the filesystem, the lexical check stops being a complete
answer, and that moment arrives at **stage 1 (read-only inspection)**, not at
stage 3 (file editing). A read that follows a junction out of the workspace is
already a boundary violation — it discloses another project's source.

What strengthening should look like, as a design sketch for a future phase:

- Keep the lexical check as a **first, cheap, disk-free gate**. It stays exactly
  as it is, and it keeps its property of never touching the path it rejects. It
  is necessary but no longer sufficient.
- Add a **second, on-disk canonicalization step** that runs *only after* the
  lexical gate passes and only within the already-approved workspace root: real
  path resolution, containment re-verification against the resolved root, and an
  explicit reparse-point/symlink check honoring `allow_symlinks`.
- **Fail closed on ambiguity.** If a path cannot be canonicalized, if resolution
  changes its containment answer, or if a reparse point is encountered while
  `allow_symlinks` is false, the operation stops.
- **Re-verify at use, not only at plan time.** A check performed once and reused
  later is a time-of-check/time-of-use bug; containment is re-established
  immediately before each read or write.
- Handle UNC and extended-length prefixes explicitly rather than letting them
  fall through the drive-letter path.

This work is a **prerequisite** for Phase 5D in §13, not a follow-up to it.

## 7. Command execution policy for future L2

Design only. **Nothing in this repo executes commands**, and Phase 5A adds no
such capability.

- **Off by default**, at every level: absent config, absent flag, absent phase
  authorization all mean no execution.
- **Allowlisted commands only, from project config.** A closed list of
  executable names with their permitted arguments. Exact matching, in the Phase
  4J style — no prefixes, no globs, no "starts with `pytest`".
- **No `shell=True`, ever.** Argument vectors only. No shell means no
  metacharacter interpretation, no pipes, no chaining, no redirection, and no
  quoting bugs that turn one command into two.
- **No arbitrary command strings from model output.** This is absolute. A model
  never selects, composes, or parameterizes a command. Phase 4F's policy guard
  already *rejects plans* that propose command execution; L2 must additionally
  have no code path that could accept one if a plan somehow carried it.
- **No commands outside the repo workspace.** The working directory is the
  approved workspace root, established after §6.4 canonicalization.
- **Timeout required.** Every execution carries a bounded timeout with no
  unlimited option. Timeout means stop and report (§10).
- **Output capture with redaction.** Output is captured, size-bounded, and
  passed through redaction before it is stored or displayed.
- **Command output may contain secrets and must not be blindly sent to a
  model.** Test output, stack traces, and debug logs routinely contain tokens,
  connection strings, and file contents from paths L2 was never allowed to read.
  Sending captured output to a model is a **separate authorization** with its
  own design, subject to the same rules as source context in §9.
- **Verification commands are separate from implementation commands.** Two
  distinct allowlists, two distinct config keys, two distinct authorizations.
  Permission to run `pytest` is not permission to run `pip install`, and a phase
  that grants verification must not silently widen into a build/install phase.

## 8. Git policy for future L2

Design only.

- **The AI still must not commit or push, by default.** This is the standing
  rule in [CLAUDE.md](../CLAUDE.md) and in
  [AI_DEV_ORCHESTRATOR_PLAN.md §4](AI_DEV_ORCHESTRATOR_PLAN.md#4-automation-levels),
  and Phase 5 does not relax it. Note the divergence from the roadmap's L2
  definition ("local commit"): this design **defers local commit** past the
  first L2 implementations, because file editing and committing are separate
  risks and there is no reason to take them together.
- **Branch creation only if explicitly authorized in a later phase**, with its
  own design. `repo.branch_prefix` exists in config for this eventual purpose
  and is read by nothing today.
- **No push without explicit human approval**, per invocation. Never a config
  flag alone.
- **No PR creation without explicit human approval.** GitHub remains read-only
  (Phase 2 `inspect-issue`) until a phase explicitly authorizes otherwise.
- **`git diff` may be read only after workspace read access is authorized** —
  it is a workspace read, and it goes through §6's policy and §7's execution
  rules (or an equivalent bounded, allowlisted mechanism). Diff output can also
  contain secrets from files L2 may not read, so it is subject to §7's redaction
  and §9's transmission rules.
- **Never merge `main`.** Unchanged, unconditional.
- **The review packet is the deliverable**, not a commit: diff, changed files,
  verification result, and risk summary (§11). A human commits.

## 9. Model usage policy for future L2

Design only.

- **L2 implementation may be fake/deterministic first.** A deterministic L2 that
  turns an approved plan into a patch proposal through fixed rules — no model at
  all — is genuinely useful for building and testing the gate, the path policy,
  and the packet format, exactly as `FakeL1Planner` was for Phase 4.
- **Any model-backed L2 needs a separate design and a separate gate.** Its own
  design document, its own project config block, its own flag, its own command.
- **Real model L2 does not inherit Phase 4L authorization.** Phase 4L was
  authorized for `generate-model-plan` and for that command only — the
  acceptance criteria say so explicitly. A real model *implementer* is a
  different capability at a different automation level with a different blast
  radius, and it requires new, explicit authorization. Reusing the
  `real_model_planning` config block for it would be a **misuse of a
  planning-scoped opt-in**; L2 gets its own.
- **Do not send source files to a model** unless a later phase explicitly
  authorizes source-context transmission. Note what this means for a model-backed
  L2: a plan-only implementer with no source context is of limited use, so the
  source-context question must be answered *before* a model-backed L2 is
  designed, not discovered midway.
- **If source context is ever sent, it must be path-bounded, size-bounded, and
  audit-aware**: only files that passed the §6 read policy; a hard cap on file
  count and total bytes, enforced before the request is built; the operator told
  in a non-suppressible stderr banner **which files** are being transmitted,
  before transmission — the Phase 4K/4L banner pattern, extended to name the
  payload.
- **No secrets in prompts.** No API keys, no `GITHUB_TOKEN`, no `.env` contents,
  no captured command output containing credentials. `forbidden_paths` exists
  partly for this, and secret-shaped content must be excluded even from files
  that are otherwise readable.

## 10. Failure handling

Design only. Every case fails **closed**: stop, report, change nothing.

| Condition | Behavior |
|---|---|
| No approved plan supplied | No L2 action. Exit non-zero before anything is read. |
| Invalid plan artifact (unparseable, wrong shape, extra keys, invalid approval block) | No action. Nothing opened past the artifact itself. |
| Project / repo / issue mismatch | No action. Name the mismatched field; never "proceed with the config's value". |
| `automation_level != "L1"` or `requires_human_approval` not `True` | No action. Treated as corrupt or forged, not as elevated. |
| Path outside `allowed_paths`, or containment ambiguity (§6.4) | No action for that path, and no partial run — the whole invocation stops. |
| `forbidden_paths` conflict | No action. No override exists. |
| `protected_paths` conflict | No action **unless** explicitly escalated for that invocation; escalation is per-run and per-path, never a standing config grant. |
| Change set exceeds `max_changed_files` | No action at all — never write the first N and stop. |
| Verification failure | No commit, no push, no PR. Report the failure in the packet. |
| Model parser failure (Phase 4F error types) | No edits. Report the failure category by name; do not echo the raw reply (Phase 4L precedent). |
| Command timeout | Stop, report the command and that it timed out. No retry, no continuation of later steps. |
| Dirty working tree | Stop, unless explicitly authorized for that invocation. A dirty tree makes "what did the AI change?" unanswerable, which defeats review. |
| Git divergence (local behind/ahead/diverged from remote) | Stop. Do not fetch, rebase, merge, or reset to fix it. |

Two cross-cutting rules:

- **Never repair, never continue.** Phase 4F's "reject, never repair" applies to
  every L2 input, not just model output. There is no L2 failure whose correct
  handling is "warn and proceed".
- **Failures are quiet about content and loud about category.** Phase 4L set the
  precedent: name *what kind* of thing failed; do not echo raw model output, and
  do not echo file contents or captured output that may carry secrets.

## 11. Output / review packet design

Design only. The review packet is what L2 produces **for a human** — the analog
of `L1Plan`, one level down.

Contents:

- **The approved plan snapshot** — the exact plan acted on, plus the approval
  metadata (who, when) that authorized it.
- **Files inspected** — every path read, with its `PathDecision` classification.
  This is the audit trail proving L2 stayed inside its boundary.
- **Files proposed or changed** — with the count checked against
  `max_changed_files`.
- **The diff**, if any — proposed (early phases) or applied (later phases),
  clearly labelled as to which.
- **Commands run and their outputs** — only when command execution is authorized
  and only from the allowlist, with §7 redaction applied.
- **Verification status** — what ran, what passed, what failed.
- **Risks and unresolved questions**, carried forward from the plan's `risks` /
  `open_questions` and added to by L2 — including anything it could not check,
  such as a plan step naming a path outside `allowed_paths`.
- **Human next steps** — explicitly what the human must do, given that L2 does
  not commit, push, or open PRs.

And two hard exclusions:

- **No secrets.** No API keys, no tokens, no `.env` content, no credential-shaped
  strings from files or command output.
- **No raw prompt or completion by default.** Same rule as Phase 3 §5 and Phase
  4L: prompt/completion bodies stay out of default output, behind an
  off-by-default, separately designed audit mechanism at most. Note that Phase 4I
  already types `allow_prompt_audit_files` as `false` by default and **nothing
  writes such a file today**; L2 does not change that.

## 12. Security and privacy risks

The major risks a future L2 must be designed against:

- **Prompt injection from the issue body.** Issue text is untrusted and
  attacker-controllable. Phase 4G's delimiters and Phase 4F's rejection rules
  contain it during planning; L2's defense is that it never reads issue text at
  all — it reads an approved plan.
- **Plan injection through `L1Plan` fields.** A model-produced plan's fields are
  model-controlled. `files_likely_to_change` in particular is a list of strings a
  model chose, and Phase 4C derives it from *issue text*. L2 must treat every
  path in a plan as a **request to validate**, never as an authorization.
- **Accidental workspace traversal.** Wrong `--project-config`, `..` in a path,
  a plan naming an absolute path. §3.5 identity matching and §6 policy are the
  defenses.
- **Symlink / junction bypass.** §6.4. The one gap where the current lexical
  approach is provably insufficient once the filesystem is touched.
- **Source code leakage to real models.** The largest privacy risk in the whole
  project. §9 keeps it behind an explicit, bounded, announced authorization.
- **Secrets in files or command output.** `.env` files, credential-bearing
  configs, tokens in test output. Mitigated by `forbidden_paths`, redaction
  (§7), and the packet exclusions (§11) — none of which is complete on its own.
- **A model inventing edits beyond scope.** A model-backed L2 can propose
  changes no one asked for. Mitigated by the path policy, `max_changed_files`,
  proposal-before-write staging, and human review of the packet.
- **Command execution escalation.** A build command that runs arbitrary project
  scripts is an arbitrary-code-execution path with a friendly name. §7's
  allowlist, no-shell, and separate-verification rules are the mitigation, and
  the residual risk is real enough to justify deferring the capability.
- **GitHub write accidents.** Any write is externally visible and hard to undo.
  Read-only until explicitly authorized (§8).
- **Approval confusion** — believing something was approved when it was not:
  presence of a file mistaken for approval (§3.6), `Automation Authorization`
  text mistaken for approval (§4.2), an approval for issue 41 applied to issue
  42 (§3.5), a Phase 4L model-call authorization mistaken for an L2 action
  authorization (§9). This class of risk is the reason approval is a single,
  explicit, human-written, exactly-matched artifact and nothing else.

## 13. Proposed Phase 5 split

**Proposals only. None of the following is authorized by this phase.** Each
sub-phase requires its own explicit prompt, and each may be re-scoped or
abandoned.

- **Phase 5A — this docs-only boundary design.** No code. *(This document.)*
- **Phase 5B — typed approved-plan handoff models and parser only. DONE.** The
  §3 wrapper as pydantic models plus a strict parser, `extra="forbid"`, in the
  Phase 4B/4F style. Library only, wired into nothing. **No workspace access, no
  CLI behavior, no model call, no network call, no environment read.** See §15.
- **Phase 5C — L2 dry-run CLI that validates an approved plan and prints the
  intended scope only.** A separate command running the §4 gate end to end and
  printing what *would* be in scope. **No workspace access**, no reads of
  `repo.workspace_path`, no edits, no commands.
- **Phase 5D — read-only workspace inspection under path policy.** The first
  phase that touches a target workspace, and therefore the phase that **must be
  preceded by the §6.4 canonicalization work**. Reads only; no writes.
- **Phase 5E — patch proposal artifact only.** Produce a diff/edit list outside
  the workspace. **No file edits.**
- **Phase 5F — controlled file editing under `allowed_paths`.** The first write.
  `max_changed_files` enforced, dirty-tree check enforced. **No command
  execution.**
- **Phase 5G — allowlisted verification commands.** §7 in full. **No commit, no
  push.**
- **Phase 5H — review packet generation.** §11 in full.
- **Later — optional branch / commit / PR workflow**, only if explicitly
  authorized, each as its own phase (§8).

Two notes on this ordering. First, it deliberately puts three non-workspace
phases (5B, 5C, and this one) before anything touches a target project — the
gate is fully built and reviewable before it guards anything. Second, the
roadmap's original L2 definition (branch + implement + local commit) is spread
across 5F and "later" rather than landing in one phase, because bundling them
would mean a single authorization crossing three distinct risk boundaries.

## 14. Acceptance criteria for Phase 5A (DONE)

- [x] The design doc (`docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md`) exists
  and covers the goal, the Phase 4 relationship and critical boundary, the
  handoff artifact, the approval gate, capability boundaries, workspace access
  policy (including the string-normalization gap and a decision on it), command
  execution policy, git policy, model usage policy, failure handling, the review
  packet, security/privacy risks, the proposed phase split, and these criteria.
- [x] **Docs-only.** The working tree contains changes to Markdown files only.
- [x] **No `src/` or `tests/` changes** in this phase.
- [x] **No runtime behavior added.**
- [x] **No CLI behavior added** — no new command, no new option, and no change
  to `version`, `inspect-issue`, `llm-smoke-test`, `generate-plan`,
  `real-llm-smoke-test`, or `generate-model-plan`.
- [x] **No model call, no network call, and no environment-variable read** —
  including no `AIDO_LITELLM_*` read and no `LLMClient` construction.
- [x] **No GitHub fetch and no GitHub write.**
- [x] **No command execution.**
- [x] **No file editing engine.**
- [x] **No agent logic and no implementer/reviewer/fixer role wiring.**
- [x] **No target project workspace access** — nothing under
  `repo.workspace_path` for any project was read, listed, stat'd, or resolved,
  and `C:\dev\mis_project`, `C:\dev\a8_oa`, `C:\dev\bible_reading_v2`, and the
  `C:\dev` parent were not touched.
- [x] **L2 is not implemented and cannot be invoked.** No existing command gains
  an L2 path, and no L2 entry point exists.
- [x] **Phase 5B and every later sub-phase in §13 remain proposed and not
  authorized.** *(Phase 5B was subsequently authorized and implemented — see
  §15. Phase 5C onward are still unauthorized.)*

## 15. Phase 5B — typed handoff models and strict parser (DONE)

Phase 5B implemented §3 of this document, and **only** §3's data shape.

### 15.1 What it is

- [handoff/models.py](../src/ai_dev_orchestrator/handoff/models.py) —
  `ApprovedPlanError` / `ApprovedPlanParseError` / `ApprovedPlanValidationError`,
  the exact constant `REQUIRED_APPROVAL_TEXT`, the `PlanApproval`,
  `L1PlanProvenance` and `ApprovedL1PlanArtifact` models (all `extra="forbid"`),
  and the pure function `parse_approved_l1_plan_artifact(text) ->
  ApprovedL1PlanArtifact`.
- [handoff/\_\_init\_\_.py](../src/ai_dev_orchestrator/handoff/__init__.py) —
  exports those eight names and nothing else.
- [tests/test_approved_plan_handoff_models.py](../tests/test_approved_plan_handoff_models.py)
  — literal JSON strings only; no artifact is read from disk, no environment
  value is read, no socket is opened.

The parser is strict in the Phase 4F sense: exactly one JSON object, surrounding
whitespace tolerated, and **reject rather than repair** — markdown fences, prose
before or after, arrays, strings, numbers, booleans and `null` all fail, unknown
fields are never stripped, and missing fields are never inferred.

`L1Plan` is **unchanged**. Approval, provenance, and identity are wrapper fields
(§3.2), and `ApprovedL1PlanArtifact` additionally rejects any field inside `plan`
that `L1Plan` does not declare — so a forged `plan.approval` fails the artifact
instead of being silently dropped (§3.6). No digest was added; §3.3's integrity
check remains a later phase's problem.

### 15.2 What it is not

- **Typed models and a parser only.** Phase 5B added no behavior beyond turning
  text it is handed into a validated object.
- **No CLI behavior.** No command and no option was added, and none was changed.
  The shipped surface is still exactly `version`, `inspect-issue`,
  `llm-smoke-test`, `generate-plan`, `real-llm-smoke-test`,
  `generate-model-plan`. `generate-plan` is still offline-only and
  `generate-model-plan` is unchanged. Nothing imports the `handoff` package.
- **No file loading.** There is no artifact loader. The parser takes a string;
  obtaining that string is out of scope, and no implementation code reads or
  writes an approved-plan artifact on disk.
- **No workspace access.** No target project workspace was read, listed, stat'd,
  or resolved. Path-like plan fields stay plain strings, exactly as in Phase 4B.
- **No model call, no network call, no environment read.** `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env` and
  `GitHubClient` are absent from the module's globals, and so are `os`, `socket`
  and `subprocess`.
- **No clock.** `approved_at` and `generated_at` are *parsed* when supplied and
  are never produced. There is no default timestamp and no staleness check.
- **No L2 action.** A successful parse means the artifact is well-formed and
  carries a valid approval. It authorizes nothing, because nothing consumes it.
- **No approval stamping.** The orchestrator still never writes an `approval`
  block (§3.6). No command creates one.
- **No GitHub fetch or write, no command execution, no file editing engine, no
  agent logic, and no implementer/reviewer/fixer role wiring.**

### 15.3 Acceptance criteria for Phase 5B (DONE)

- [x] Typed errors, the exact `REQUIRED_APPROVAL_TEXT` constant, the three
  models, and the strict parser exist and are exported from the `handoff`
  package.
- [x] **Approval fails closed.** A missing, null, empty, incomplete, or
  malformed `approval` block is rejected; `approval_text` must match the
  required phrase **exactly**; `approved_by` must be non-blank; `source` must be
  exactly `"manual"`; `approved_at` must parse. No approval field has a default.
- [x] **`Automation Authorization` text is not approval.** An artifact whose plan
  prose asserts automation was authorized is still rejected without a valid
  wrapper approval block.
- [x] **Identity mismatches are rejected** — wrapper vs provenance
  (`project_id`, `repo`, `issue_number`), wrapper vs plan (`repo`,
  `issue_number`), and provenance vs plan (`title`) — with exact string
  equality, no normalization.
- [x] **The plan must still be an unescalated L1 plan** —
  `automation_level == "L1"` and `requires_human_approval is True`, checked
  explicitly by the wrapper.
- [x] **`extra="forbid"` everywhere**, including a wrapper-side rejection of
  unknown fields inside `plan`. API-key-, base-URL-, prompt- and
  completion-shaped fields in provenance are rejected as extras, and
  `endpoint_host` is **rejected — never stripped** when it contains `/`, `?`,
  `#`, or `@`.
- [x] **The parser performs no IO**, verified by monkeypatching `builtins.open`,
  `os.getenv`, `os.environ.get`, `os.stat`, `os.listdir`, `os.scandir`,
  `os.path.exists`, `os.path.abspath`, `os.path.realpath`, `socket.socket`,
  `socket.create_connection`, `socket.getaddrinfo` and `subprocess.Popen` around
  both a successful parse and the failure paths.
- [x] **`L1Plan` was not modified** and carries no approval field.
- [x] **No CLI behavior added**, per §15.2.
- [x] **No target project workspace access** — `C:\dev\mis_project`,
  `C:\dev\a8_oa`, `C:\dev\bible_reading_v2`, and the `C:\dev` parent were not
  touched.
- [x] **L2 is still not built and cannot be invoked.**
- [x] **Phase 5C and every later sub-phase in §13 remain proposed and not
  authorized.**
