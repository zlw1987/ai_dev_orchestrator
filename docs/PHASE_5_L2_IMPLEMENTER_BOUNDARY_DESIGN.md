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
> been authorized and implemented as **typed models and a parser only** — §15 —
> Phase 5C as a **dry-run validation command only** — §16, Phase 5D0 as a
> **canonical path guard library only** — §17, Phase 5D1 as **read-only
> workspace metadata inspection only** — §18, Phase 5E0 as **patch proposal
> artifact models and a parser only** — §19, Phase 5E1 as a **deterministic,
> offline proposal generator and one CLI command** — §20, Phase 5D2 as
> **bounded read-only file-content inspection only** — §21, Phase 5E2 as
> **unified diff proposal artifact models and a parser only** — §22, Phase
> 5E3 as a **deterministic, offline diff proposal producer and one CLI command**
> — §23, and Phase 5F0 as **file-edit write gate models and a parser only** —
> §24. Phase 5F1 onward remain proposals, nothing edits a file, and L2 is still
> not built.)
>
> **L2 may not be invoked by any existing command after this phase.** After
> Phase 5A the shipped CLI surface is exactly what Phase 4L left behind —
> `version`, `inspect-issue`, `llm-smoke-test`, `generate-plan`,
> `real-llm-smoke-test`, `generate-model-plan` — and none of them gains an L2
> path, an `--apply` flag, or any other way to reach an implementer. (Phase 5C
> later added one **new** command, `l2-dry-run`, which validates and prints and
> takes no action; Phase 5D1 added a second, `l2-inspect-workspace`, which
> reports path metadata and takes no action. Neither changed any of the six
> above, and neither implements anything. Phase 5E1 added a third,
> `generate-patch-proposal`, which generates a prose-only proposal artifact
> offline and prints it; Phase 5D2 added a fourth,
> `l2-read-workspace-files`, which prints bounded, redacted file contents and
> takes no action; Phase 5E3 added a fifth, `generate-diff-proposal`, which
> generates unified diff text offline from local JSON inputs and prints it,
> applying nothing. None of them changed any of the others, and none implements
> anything.)
>
> It refines item **"Phase 5 — docs-only L2 implementer"** of
> [AI_DEV_ORCHESTRATOR_PLAN.md §7](AI_DEV_ORCHESTRATOR_PLAN.md#7-mvp-phase-roadmap)
> and picks up where
> [PHASE_4_L1_PLAN_GENERATOR_PLAN.md](PHASE_4_L1_PLAN_GENERATOR_PLAN.md) stops.
>
> **Phase 5B is now DONE** (§15). It implemented the §3 artifact as **typed
> models and a strict parser only** — no CLI behavior, no file loading, no
> workspace access, no model/network/environment access, and no L2 action.
>
> **Phase 5C is now DONE** (§16). It added the `l2-dry-run` command: it reads a
> project config and an approved-plan artifact, validates them, and prints the
> scope a future L2 *would* be bounded by. **No workspace access, no
> implementation, no model/network/environment access, no GitHub fetch or
> write, no command execution, no file editing, and no approval stamping.**
>
> **Phase 5D0 is now DONE** (§17). It implemented the §6.4 canonicalization
> sketch as a **library-only** path guard —
> `workspace/canonical.py` — and nothing else. **It is not workspace
> inspection**: no CLI command was added or changed, no shipped code path calls
> it, and its tests use pytest `tmp_path` directories only. It is the
> **prerequisite** §6.4 requires before Phase 5D.
>
> **Phase 5D1 is now DONE** (§18). It added the `l2-inspect-workspace` command
> and is the **first shipped code that may touch a configured target
> workspace** — as `stat` and nothing more. For each path an approved plan lists
> under `files_likely_to_change` it reports existence, kind, and size, after two
> explicit flags, a project-level opt-in, artifact validation, exact identity
> matching, candidate-count caps, the lexical Phase 1 path policy, and the Phase
> 5D0 canonical guard. **It reads no file contents, lists no directory, runs no
> command, edits no file, proposes no patch, and calls no model.**
>
> **Phase 5E0 is now DONE** (§19). It typed the **patch proposal artifact** as
> pydantic models plus a strict parser — `ai_dev_orchestrator.patch_proposal` —
> and nothing else. **It is not patch generation**: there is no generator, and
> the artifact deliberately carries **no unified diff**, no patch, no edit
> script, no command, and no file content. Library only — no CLI behavior, no
> workspace access, no file contents read, no file edited, no command run, no
> model / network / environment access, and no approval stamped.
>
> **Phase 5E1 is now DONE** (§20). It added the one thing Phase 5E0 withheld: a
> **deterministic, offline generator**, `build_deterministic_patch_proposal`,
> plus the `generate-patch-proposal` command that reads a project config and an
> approved plan, generates the artifact, and prints it to stdout. **It is still
> not a diff and still not file editing**: the artifact carries **no unified
> diff**, no patch, no edit script, no file content, no command, and no command
> output — only prose about paths the approved plan already named. **No
> workspace access, no file contents read, no file edited, no command run, no
> model / network / environment access, no GitHub fetch or write, no artifact
> file written, and no approval stamped.**
>
> **Phase 5D2 is now DONE** (§21). It added the `l2-read-workspace-files`
> command — the first phase whose **output may contain target workspace
> source**. For each path an approved plan lists under `files_likely_to_change`
> it canonicalizes, stats, and — only for a regular file inside the configured
> byte caps — reads, decodes as UTF-8, and prints the text after **mandatory**
> secret-like redaction. Gated by two explicit flags, a **separate**
> project-level opt-in from Phase 5D1's, artifact validation, exact identity
> matching, candidate-count caps, the lexical Phase 1 path policy, and the Phase
> 5D0 canonical guard. **It lists no directory, generates no diff, edits no
> file, runs no command, calls no model, and sends no content to one.**
>
> **Phase 5E2 is now DONE** (§22). It typed the **unified diff proposal
> artifact** as pydantic models plus a strict parser —
> `ai_dev_orchestrator.diff_proposal` — and nothing else. It lets a diff-shaped
> artifact **exist as data** and be validated for shape: one single-file textual
> diff per change, headers naming exactly the declared path, at least one hunk,
> and no binary/rename/delete/mode payload. **It is not diff generation and not
> diff application**: nothing here produces a diff, modifies one, applies one, or
> asks whether one would apply. Library only — no CLI behavior, no workspace
> access, no file contents read, no file edited, no command run, no model /
> network / environment access, and no approval stamped.
>
> **Phase 5E3 is now DONE** (§23). It added the producer Phase 5E2 withheld:
> `build_deterministic_diff_proposal`, plus the `generate-diff-proposal` command
> that reads four local files — a project config, an approved plan, a Phase 5D2
> `l2-read-workspace-files` packet, and a proposed-content JSON object — runs
> `difflib` over strings, and prints a Phase 5E2 artifact to stdout. **It reads
> no target workspace file directly**: original text arrives inside the packet
> or the generation for that path fails. **It generates diff text and does
> nothing with it** — no diff applied, no apply-cleanliness checked, no file
> edited, no command run, no model / network / environment access, no GitHub
> fetch or write, no artifact file written, and no approval stamped.
>
> **Phase 5F0 has since been authorized and implemented as file-edit write gate
> models and a strict parser only** — the second, separate human approval a
> future file-editing phase would need, typed as data (§24). It edits nothing,
> applies nothing, checks no apply-cleanliness, runs nothing, adds no command,
> and stamps no approval.
>
> **Phase 5F1 and every later sub-phase in §13 remain proposed and not
> authorized. Nothing shipped so far edits a file.**

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

*Phase 5D1 has since shipped the first half of this capability* (§18): the
**metadata** half — existence, kind, and size — and not the content half. The
split was not in the original plan and is worth recording. "Does `src/foo.py`
exist and is it 40 lines or 4000" is a genuinely different disclosure from "here
is what `src/foo.py` says", and it is enough to check a plan's most common
failure mode (a path that is simply wrong) while disclosing almost nothing.

*Phase 5D2 has since shipped the content half* (§21), as its own command behind
its own project opt-in rather than as a flag on the metadata one — bounded by a
file-count cap, a per-file byte cap and a total-byte cap, and with mandatory
secret-like redaction on everything it prints. It reads and prints; it still
diffs nothing, edits nothing, runs nothing, and sends nothing to a model.

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

**Phase 5D0 has since implemented this sketch as a library** — see §17. The
lexical gate is unchanged, and the new module adds the on-disk second gate,
the reparse-point check, the fail-closed ambiguity handling, and explicit
UNC/extended-length/device/trailing-dot-or-space/8.3 rejection. It is **not**
wired into anything: the prerequisite is now built, and Phase 5D itself remains
unauthorized.

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
  intended scope only. DONE.** A separate command running the §4 gate as far as
  this phase is authorized to go and printing what *would* be in scope. **No
  workspace access**, no reads of `repo.workspace_path`, no edits, no commands.
  See §16.
- **Phase 5D0 — canonical path guard library only. DONE.** The §6.4
  canonicalization step as a reusable library: strict on-disk canonicalization,
  robust containment re-verification, a symlink/junction/reparse-point policy,
  and a fail-closed lexical precheck for ambiguous Windows path forms. **Library
  only** — no CLI behavior, no command, no option, and no caller. **It is not
  workspace inspection**, and its tests use pytest `tmp_path` only. See §17.
- **Phase 5D1 — read-only workspace *metadata* inspection. DONE.** The first
  phase that touches a target workspace, and only through the Phase 5D0 guard
  plus `stat`: existence, kind, and size for the paths an approved plan lists
  under `files_likely_to_change`. **No file contents, no directory listing, no
  glob, no tree walk, no writes, no commands, no model.** See §18.
- **Phase 5D2 — bounded read-only file *contents* under the path policy. DONE.**
  The disclosure Phase 5D1 deliberately stopped short of: "does
  `src/foo/bar.py` exist and how big is it" and "what does `src/foo/bar.py`
  say" are different questions, and this phase answers the second — bounded by
  a per-file cap, a total-bytes cap, and a file-count cap, behind its **own**
  project opt-in, and with mandatory secret-like redaction on every byte
  printed. **No directory listing, no glob, no tree walk, no diff, no writes,
  no commands, no model, and no content sent to a model.** See §21.
- **Phase 5E0 — patch proposal artifact models and parser only. DONE.** The
  proposal artifact as pydantic models plus a strict parser, `extra="forbid"`,
  in the Phase 4B/4F/5B style. **Library only, wired into nothing**, and **not a
  generator**: nothing produces a proposal, and the artifact carries **no
  unified diff**, no patch, no edit script, no command, and no file content —
  only prose describing suggested work on paths the approved plan already named.
  **No workspace access, no file contents read, no CLI behavior, no model call,
  no network call, no environment read, no file editing, no command execution,
  and no approval stamping.** See §19.
- **Phase 5E1 — a deterministic patch proposal generator. DONE.** The thing
  that actually *produces* a Phase 5E0 artifact from an approved plan:
  `build_deterministic_patch_proposal`, a pure offline function over two
  already-loaded objects, plus the `generate-patch-proposal` command that prints
  its result to stdout. It restates the plan's own `files_likely_to_change` as
  one prose `modify` change each, and **generates no diff** and carries no file
  content — carrying a real diff is Phase 5E2, which has since shipped the
  *artifact* for one but still no producer. **No workspace access, no
  file contents read, no file editing, no command execution, no model/network/
  environment access, no artifact file written, and no approval stamped.**
  See §20.
- **Phase 5E2 — unified diff proposal artifact models and parser only. DONE.**
  The half of "carrying a real diff" that can be built without producing one:
  the diff-bearing artifact as pydantic models plus a strict parser,
  `extra="forbid"`, in the Phase 5E0 style. A `unified_diff` field now exists and
  may contain source lines as diff context — that is what a diff is, and it is
  allowed **as data** — but **nothing generates it, modifies it, or applies it**,
  and `applies_cleanly_checked` is `Literal[False]` because asking whether a diff
  applies means touching a workspace. **Library only, wired into nothing.** **No
  workspace access, no file contents read, no CLI behavior, no model call, no
  network call, no environment read, no file editing, no command execution, and
  no approval stamping.** See §22.
- **Phase 5E3 — a deterministic producer for the Phase 5E2 artifact. DONE.**
  Something that actually *generates* a unified diff — from a Phase 5D2 content
  packet and a proposed-content input supplied as **local JSON files**, never
  from a direct workspace read of its own — behind its own gate. It ships
  `build_deterministic_diff_proposal` and the `generate-diff-proposal` command.
  The remaining decision that Phase 5E2 left open is answered here in the
  restrictive direction: a diff generated from **redacted** source is refused
  outright, and a generated diff that looks like it carries a credential is
  discarded rather than redacted, because a redacted diff reads like a patch and
  could never apply. **No diff applied, no apply-cleanliness checked, no
  workspace read, no file edits, no commands, no model, no artifact file
  written.** See §23.
- **Phase 5F0 — file-edit write gate models and parser (DONE).** The explicit,
  separately worded human approval of one **concrete diff proposal**, typed as
  data. It is the gate a write would have to pass, built and reviewable before
  anything can write. **No file edit, no diff application, no apply-cleanliness
  check, no workspace read, no commands, no model, no CLI command, no artifact
  file written, no approval stamped.** See §24.
- **Phase 5F1 — proposed, not authorized.** May add a separately gated
  **dry-run apply plan** — what a write *would* touch — but **not file editing**
  unless explicitly authorized.
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

*(Statements in this sub-section describe the tree as Phase 5B left it. Phase 5C
later added the `l2-dry-run` command, which is the first and only caller of this
package and the first code that reads an approved-plan artifact from disk — see
§16. Everything else below still holds.)*

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
  authorized.** *(Phase 5C was subsequently authorized and implemented — see
  §16. Phase 5D onward are still unauthorized.)*

## 16. Phase 5C — L2 dry-run validation command (DONE)

Phase 5C added **one** command, `l2-dry-run`. It runs the §4 gate as far as this
phase is authorized to go and **prints what a future L2 would be bounded by**.
It is the analog of `generate-plan`, one level down: a read-and-report command
that changes nothing.

### 16.1 What it is

```bash
python -m ai_dev_orchestrator l2-dry-run \
  --project-config projects/my_project.yaml \
  --approved-plan path/to/approved_plan.json \
  --apply-approved-plan
```

- [cli.py](../src/ai_dev_orchestrator/cli.py) — the private helper
  `_run_l2_dry_run(...)` and the `l2-dry-run` command wrapping it. Options:
  `--project-config`, `--approved-plan`, `--apply-approved-plan`, and
  `--format json`. There is no `--model`, `--real-model`, `--body-file`,
  `--issue`, `--title`, `--github`, `--fetch`, `--workspace`, `--file`,
  `--context-file`, `--command`, `--edit`, or `--audit-dir`.
- [tests/test_cli_l2_dry_run.py](../tests/test_cli_l2_dry_run.py) — literal
  artifacts under pytest's `tmp_path` only; no environment value is read, no
  socket is opened, no command is run, and no configured workspace is touched.

**It reads exactly two files, in this order:** the `--project-config` YAML and
the `--approved-plan` artifact. Nothing else. The artifact is validated with the
Phase 5B parser `parse_approved_l1_plan_artifact`, then cross-checked against the
config for exact `project_id`, `repo`, `plan.repo`, and `plan_provenance.repo`
equality (§3.5). The issue number comes from the artifact alone — GitHub is not
contacted to confirm it.

**Gate ordering (§4.3, fail closed, cheapest first):**

1. `--apply-approved-plan` present? No → exit 1, **nothing read at all** — not
   the artifact, and not even the project config.
2. Project config loads and validates. On failure → exit 1, artifact never
   opened.
3. `--approved-plan` is not `repo.workspace_path` itself and does not sit under
   it → checked with the existing `_is_same_or_under` string/path normalization,
   **before** the artifact is read or stat'd. This is why `--approved-plan`
   carries no Typer `exists=`/`readable=` check: those would touch the path
   before the guard could run, exactly as for Phase 4L's `--body-file`.
4. The artifact is read. A missing or unreadable file → exit 1.
5. Strict parse. `ApprovedPlanParseError` and `ApprovedPlanValidationError` are
   reported **by category and by name**, and the artifact text and plan prose are
   never echoed (Phase 4L precedent).
6. Exact identity matching against the config. A mismatch names the field and
   both values, and stops.
7. Only then is the scope JSON printed to stdout.

Every failure exits non-zero, writes to **stderr only**, and prints **no stdout
JSON**. There is no partial output and no "continuing with warnings".

**Output.** One JSON object carrying: a `notice` stating no workspace was read,
no file was edited, no command was run and no implementation occurred; `mode:
"l2-dry-run"`; the project's `project_id`, `repo` and `workspace_policy` flags;
the approval's `approved_by` / `approved_at` / `source`, the plan's engine, its
`real_call` flag and model, and the issue number and title; an `intended_scope`
block copying `files_likely_to_change`, `files_forbidden_or_out_of_scope`,
`required_verification`, `proposed_steps`, `risks` and `open_questions`
**verbatim** from the approved plan snapshot, under a `note` labelling them as
plan text that was not acted on; and `next_authorization_required`.

Deliberately **not** in the output: the raw artifact text, any prompt or
completion, any API key or base URL, the configured `workspace_path`, any source
file content, and `approval_text` (it is required to equal a fixed phrase, so
echoing it adds nothing to the `approved_by`/`approved_at` pair).

### 16.2 What it is not

- **No workspace access.** The configured `repo.workspace_path` is never read,
  listed, stat'd, or resolved; nothing under it is opened; and no path named in
  `files_likely_to_change` is read, stat'd, resolved, globbed, or checked for
  existence. Plan paths remain plain strings — hints a later phase would have to
  validate, exactly as §12 requires.
- **No implementation.** Nothing is inspected, proposed, patched, edited, or
  applied. No branch, commit, or PR. No `required_verification` entry is run —
  they are carried as labelled plan text.
- **No command execution, no file editing engine, no agent logic, and no
  implementer/reviewer/fixer role wiring.**
- **No model call, no network call, no environment read.** No `AIDO_LITELLM_*`
  read, no `LLMClient` construction, no `httpx`/`requests` import in the command
  path, no socket.
- **No GitHub fetch and no GitHub write.** There is no option to reach GitHub.
- **No artifact writing and no approval stamping.** The command reads the
  artifact and never rewrites it; the orchestrator still never writes an
  `approval` block (§3.6). Approval remains a human act performed outside this
  tool.
- **No change to any other command.** `version`, `inspect-issue`,
  `llm-smoke-test`, `generate-plan`, `real-llm-smoke-test`, and
  `generate-model-plan` are untouched, and none of them gained an `--apply`,
  `--approved-plan`, or any other L2 path.
- **Not a project-level L2 opt-in.** Step 3 of §4.3 — an L2 config block, the
  analog of `real_model_planning` — is deliberately **not** implemented here:
  this command takes no L2 action, so there is nothing for a project to opt into
  yet. It belongs with the phase that first touches a workspace, and Phase 5C
  added no config field. *(Phase 5D1 is that phase, and it added
  `read_only_workspace_inspection` — see §18. `l2-dry-run` still does not read
  the block for any purpose beyond ordinary config loading.)*

### 16.3 Acceptance criteria for Phase 5C (DONE)

- [x] Exactly one new command, `l2-dry-run`, exposing `--project-config`,
  `--approved-plan`, `--apply-approved-plan`, and `--format`, and none of the
  forbidden options.
- [x] **Fails closed without `--apply-approved-plan`**, before any file is read —
  including before the project config.
- [x] **An `--approved-plan` inside `repo.workspace_path` is rejected before the
  artifact is read or stat'd**, by string/path normalization only, and its
  content never surfaces on stdout or stderr.
- [x] **A missing or unreadable artifact fails cleanly** with exit code 1 after
  the config load and the path guard.
- [x] **Parse and validation failures fail closed** with the category named, no
  stdout JSON, and no echo of artifact text or plan prose.
- [x] **Identity mismatches fail** — `project_id`, `repo`, `plan.repo`,
  `plan_provenance.repo` — with exact string equality, no case folding.
- [x] **A valid artifact prints the dry-run scope JSON**, including the notice,
  the approval metadata, the issue number and title, the intended scope copied
  from the plan, and the next-authorization statement.
- [x] **Output excludes** raw artifact text, `approval_text`, API keys, base
  URLs, `workspace_path`, and source file contents.
- [x] **Exactly two files are read on success**, in order: config, then artifact.
- [x] **No target project workspace access** — verified by tracking every path
  passed to `builtins.open`, `os.stat`, `os.listdir`, `os.scandir`,
  `os.path.exists` and `os.path.realpath`, and by detonating those entry points
  around a run. `os.path.abspath` is left working because `_is_same_or_under`
  needs it and it touches no filesystem.
- [x] **No environment read, no socket, no subprocess, no `LLMClient`, no
  `httpx`/`requests`, no `GitHubClient`.**
- [x] **No artifact writing and no approval stamping.**
- [x] **No CLI behavior changed except adding `l2-dry-run`.**
- [x] **Phase 5D and every later sub-phase in §13 remain proposed and not
  authorized.** Phase 5D is the first phase that might touch a workspace and is
  blocked on the §6.4 canonicalization work.

## 17. Phase 5D0 — canonical path guard library (DONE)

Phase 5D0 implemented the §6.4 design sketch as a **library**, and nothing else.
It exists because §6.4 decided that canonicalization must be strengthened
**before** read-only workspace inspection, not after it — so the prerequisite is
built and reviewable on its own, ahead of the phase that would use it.

**Phase 5D0 is not Phase 5D.** It performs no workspace inspection, adds no
command, and is called by nothing.

*(§17 describes the tree as Phase 5D0 left it. Phase 5D1 later became the
guard's first and only caller — see §18 — so the "called by nothing" statements
below record what shipped in 5D0, not what is true today. Everything else in
§17 still holds: the guard itself is unchanged, adds no command of its own, and
still reads no file contents and lists no directory.)*

### 17.1 What it is

- [workspace/canonical.py](../src/ai_dev_orchestrator/workspace/canonical.py) —
  the error family `CanonicalPathError` /  `CanonicalPathInputError` /
  `CanonicalPathResolutionError` / `CanonicalPathContainmentError` /
  `CanonicalPathSymlinkError` / `CanonicalPathAmbiguityError`, the frozen
  data-only `CanonicalWorkspacePath`, and the single entry point
  `canonicalize_existing_path_under_workspace(workspace_root, candidate, *,
  allow_symlinks=False)`.
- [workspace/\_\_init\_\_.py](../src/ai_dev_orchestrator/workspace/__init__.py) —
  exports those eight names alongside the existing Phase 1 path-policy names.
- [tests/test_workspace_canonical_path_guard.py](../tests/test_workspace_canonical_path_guard.py)
  — pytest `tmp_path` directories and files only.

The function proves one claim about one path: *this existing candidate is
genuinely inside this existing workspace root*. It runs in this order, cheapest
and most conservative first:

1. **Type and blank checks** on both inputs, and on `allow_symlinks`.
2. **A fail-closed lexical precheck**, before any filesystem call: UNC
   (`\\server\share\...`), extended-length (`\\?\C:\...`), device (`\\.\...`),
   any component ending in a space or a dot, and any 8.3-short-name-looking
   component (`PROGRA~1`, `LONGFI~1.TXT`) are **refused, never normalized or
   repaired**. Both separators are treated alike, so the forward-slash spellings
   are refused too. This is deliberately **conservative** and may reject strings
   that name a real file on Windows: every form here can denote the same
   location as some other string, which is exactly what makes containment
   reasoning unsound.
3. **Existence and kind checks** — `os.lstat` for existence (so a dangling
   symlink surfaces as a *symlink* decision, not a missing path), and the
   workspace root must resolve to a directory.
4. **The symlink / reparse-point policy** (§17.2).
5. **Strict canonicalization** of both paths, `Path.resolve(strict=True)`.
6. **Containment re-verification** of the resolved candidate against the
   resolved root, via `os.path.commonpath` on `os.path.normcase`-normalized
   paths — **not** a string prefix test. A sibling sharing a string prefix
   (`repo` vs `repo_evil`) is outside. A comparison that cannot be made at all —
   a drive mismatch — raises `CanonicalPathAmbiguityError` rather than being
   guessed.

A relative candidate is joined to the workspace root before resolution; an
absolute candidate is never joined and is validated against the root as given.
`relative_path` is returned relative to the resolved root. A candidate **equal
to** the workspace root is **accepted as inside**, reporting `relative_path ==
"."` — a deliberate choice, documented on the function: "inside the workspace"
and "is a file" are different questions, and a future caller that needs a file
must check the kind separately.

Inputs are not mutated, nothing is created, and nothing is deleted.

### 17.2 Symlink, junction, and reparse-point policy

With `allow_symlinks=False` (the default) the guard refuses:

- a workspace root that is itself a symlink or reparse point;
- any component between the root and the candidate that is one;
- and a candidate that is not *lexically* under the root — so a link cannot be
  used to **enter** the workspace either.

Rejection happens **before** the path is accepted, even when the link points
back inside the workspace. Note the guard never inspects components *above* the
workspace root: the root is the boundary, and walking above it would make the
check depend on the ancestors of whatever directory the operator configured.

With `allow_symlinks=True` links are followed and containment is then re-checked
against the resolved root: a link resolving outside the workspace is still
rejected, and one resolving inside may be accepted.

Detection is best-effort and platform-aware. POSIX symlinks appear in
`st_mode`. Windows junctions and directory mount points are reparse points that
`stat` follows silently and that `S_ISLNK` does not report, so
`st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT` and `st_reparse_tag` are
checked as well.

**Time of check is not time of use.** A returned decision describes the
filesystem as it was during the call. Per §6.4 a future caller must re-establish
containment immediately before each read — never cache one answer and reuse it.

### 17.3 What it is not

- **Not workspace inspection.** Phase 5D is still proposed and unauthorized.
  This module reads no file contents, lists no directory, globs nothing, and
  walks no tree. It answers one question about one path the caller already
  named.
- **No CLI behavior.** No command and no option was added, and none was changed.
  The shipped surface is exactly what Phase 5C left: `version`,
  `inspect-issue`, `llm-smoke-test`, `generate-plan`, `real-llm-smoke-test`,
  `generate-model-plan`, `l2-dry-run`. `l2-dry-run`, `generate-plan` and
  `generate-model-plan` behave identically to before.
- **Not wired in.** No shipped module imports `workspace.canonical` or calls
  `canonicalize_existing_path_under_workspace`; only the package `__init__`
  re-exports it, and a test asserts that.
- **No target workspace access by any shipped command.** Nothing under any
  configured `repo.workspace_path` was read, listed, stat'd, or resolved, and
  no path named by an approved plan was inspected.
- **Not a permission decision.** Containment is not authorization. A returned
  `CanonicalWorkspacePath` says the path is inside the root; whether the path is
  *allowed* remains `PathPolicy`'s question (§6.2), and a future caller must
  satisfy **both** gates. The lexical Phase 1 policy is unchanged and stays the
  cheap first gate.
- **No model call, no network call, no environment read, no command execution,
  no file editing, no agent logic, and no implementer/reviewer/fixer role
  wiring.** `httpx`, `requests`, `LLMClient`, `LLMClientConfig`,
  `load_llm_client_config_from_env`, `GitHubClient`, `typer`, `socket` and
  `subprocess` are absent from the module's globals.
- **No GitHub fetch and no GitHub write.**
- **No approved-plan artifact was created or modified, and no approval was
  stamped.**
- **No config change.** No new config field, and `workspace_policy.allow_symlinks`
  is **not** read by this module — `allow_symlinks` is an explicit keyword
  argument, so nothing here silently inherits a project setting. Connecting the
  two belongs to the phase that first calls the guard.

### 17.4 Acceptance criteria for Phase 5D0 (DONE)

- [x] The six-error hierarchy, the frozen data-only `CanonicalWorkspacePath`,
  and `canonicalize_existing_path_under_workspace` exist and are exported from
  the `workspace` package — those eight names and nothing else added.
- [x] **Happy paths pass**: an existing file under the workspace, an existing
  directory, a relative candidate, and an absolute candidate are all accepted;
  `relative_path` is relative and stable across spellings; and
  `resolved_candidate` is inside `resolved_workspace_root`.
- [x] **Input failures fail closed**: blank or wrongly-typed `workspace_root`
  or `candidate`, a missing workspace root, a workspace root that is a file, and
  a missing candidate.
- [x] **Escapes fail closed**: a relative candidate escaping via `..`, an
  absolute candidate outside the workspace, the workspace parent, and sibling
  prefix confusion (`repo` vs `repo_evil`) — all rejected, with and without
  `allow_symlinks`.
- [x] **Containment is commonpath-based, not prefix-based**, case handling
  follows `os.path.normcase`, and a drive mismatch fails closed as ambiguity.
  Case behavior is tested in a platform-aware way only.
- [x] **The symlink policy is tested**: a symlink inside the workspace pointing
  inside is rejected with `allow_symlinks=False` and accepted with
  `allow_symlinks=True`; one pointing outside is rejected either way; an
  intermediate directory symlink is rejected; a symlinked workspace root is
  rejected with `allow_symlinks=False`; and a dangling symlink fails closed.
  Symlink tests skip gracefully where the platform or user cannot create one.
  Windows junctions need no admin rights to create but do need a subprocess, so
  reparse-point detection is covered instead by exercising the detector against
  fabricated `st_file_attributes` / `st_reparse_tag` stat results, plus two
  end-to-end runs with `os.lstat` faked to report a reparse point on the root
  and on an intermediate component.
- [x] **Unsafe lexical forms are rejected before any disk touch** — UNC,
  extended-length, device, trailing-dot, trailing-space, and 8.3-like
  components, in both separator spellings, for both the workspace root and the
  candidate — proven by detonating `os.stat`, `os.lstat`, `Path.resolve`,
  `os.path.realpath`, `os.path.exists`, `os.listdir`, `os.scandir` and
  `builtins.open` around the call. `.` and `..` are not mistaken for
  trailing-dot components.
- [x] **No forbidden behavior**, verified by test: the forbidden names are absent
  from module globals; the happy path and the failure paths run with
  `builtins.open`, `os.getenv`, `os.environ.get`, `os.listdir`, `os.scandir`,
  `os.walk`, `os.system`, `subprocess.Popen`, `subprocess.run`,
  `socket.socket`, `socket.create_connection` and `socket.getaddrinfo` all
  detonating.
- [x] **Every path touched is under `tmp_path`**, asserted by tracking every
  argument passed to `os.lstat`, `os.stat` and `Path.resolve` during a run; and
  neither the implementation nor the test module names a real `C:\dev` project
  workspace.
- [x] **No CLI behavior changed.** Root help still lists exactly the seven
  Phase 5C commands and gains no canonicalization command; `l2-dry-run`,
  `generate-plan` and `generate-model-plan` help are unchanged and gain no
  `--allow-symlinks` or equivalent option.
- [x] **Nothing calls the guard.** Asserted across the whole package.
- [x] **Phase 5D and every later sub-phase in §13 remain proposed and not
  authorized.** Phase 5D0 satisfies the §6.4 prerequisite; it does not authorize
  the phase that would use it.

## 18. Phase 5D1 — read-only workspace metadata inspection (DONE)

Phase 5D1 added **one** command, `l2-inspect-workspace`. It is the **first
shipped code that may touch a configured target workspace**, and the touch it
makes is the smallest one available: canonicalize a path the approved plan
already named, then `stat` it.

**Phase 5D1 is not L2.** It proposes nothing, patches nothing, edits nothing,
runs nothing, and commits nothing. It is the analog of `l2-dry-run` with one
capability added — the dry run says "the plan claims it will change
`src/foo.py`"; this command says "and that path exists, is a file, and is 1,240
bytes." That is the whole difference.

### 18.1 What it is

```bash
python -m ai_dev_orchestrator l2-inspect-workspace \
  --project-config projects/my_project.yaml \
  --approved-plan path/to/approved_plan.json \
  --apply-approved-plan \
  --inspect-workspace
```

- [models.py](../src/ai_dev_orchestrator/models.py) — the new
  `ReadOnlyWorkspaceInspectionConfig` block and the
  `ProjectConfig.read_only_workspace_inspection` field, defaulting to disabled.
- [cli.py](../src/ai_dev_orchestrator/cli.py) — the private helpers
  `_run_l2_inspect_workspace(...)`, `_stat_kind_and_size(...)` and
  `_dedupe_preserving_order(...)`, and the `l2-inspect-workspace` command
  wrapping the first. Options: `--project-config`, `--approved-plan`,
  `--apply-approved-plan`, `--inspect-workspace`, and `--format json`. There is
  no `--model`, `--real-model`, `--body-file`, `--issue`, `--title`,
  `--github`, `--fetch`, `--workspace`, `--file`, `--context-file`,
  `--command`, `--edit`, `--audit-dir`, or `--allow-symlinks`.
- [projects/mis\_project.yaml.example](../projects/mis_project.yaml.example) —
  the new block, shipped **disabled**.
- [tests/test\_cli\_l2\_inspect\_workspace.py](../tests/test_cli_l2_inspect_workspace.py)
  — pytest `tmp_path` only. The "workspace" every test configures is a directory
  the test created moments earlier; no real project path is named.

This is the first caller the Phase 5D0 guard has ever had, and it remains the
only one. The Phase 1 lexical policy is unchanged and still runs first.

### 18.2 The project-level opt-in

`read_only_workspace_inspection` is the §4.3 step-3 block that Phase 5C
deliberately deferred, added now because this is the phase that first touches a
workspace and therefore the first phase with something to opt into:

```yaml
read_only_workspace_inspection:
  enabled: false
  max_inspected_files: 20
  allow_protected_paths: false
```

`enabled` defaults to `false`; an absent block is identical to a disabled one,
in the Phase 4I `real_model_planning` style. `max_inspected_files` must be
`1..100`. `allow_protected_paths` defaults to `false`. `extra="forbid"`, and the
block holds **no credentials**: no API key, no base URL, no endpoint, no model
name, and no environment-variable name. It is a separate block rather than a
reuse of `real_model_planning` for the reason §9 gives: a planning-scoped opt-in
must not silently authorize a workspace-touching capability.

No other command reads this block for any purpose beyond ordinary config
loading, and `l2-inspect-workspace` refuses to touch the workspace at all while
it is disabled — failing before the approved-plan artifact is even opened.

### 18.3 Gate ordering (fail closed, cheapest first)

Ordering *is* the safety property here, because the last step is the one that
touches another project's files.

1. `--apply-approved-plan` present? No → exit 1, **nothing read at all**.
2. `--inspect-workspace` present? No → exit 1, **nothing read at all**. Two
   flags rather than one on purpose: approving a plan and permitting a workspace
   to be examined are separate consents, and this command needs both.
3. Project config loads and validates. The first file read.
4. `read_only_workspace_inspection.enabled` is true → otherwise exit 1, with the
   artifact never opened and the workspace never touched.
5. `--approved-plan` is not `repo.workspace_path` and does not sit under it —
   the existing `_is_same_or_under` string/path check, **before** the artifact is
   read or stat'd, which is why the option carries no Typer `exists=`/`readable=`
   check.
6. The artifact is read. The second and final file read.
7. Strict Phase 5B parse. Failures are reported by category and by name; the
   artifact text and the plan prose are never echoed.
8. Exact identity matching against the config — `project_id`, `repo`,
   `plan.repo`, `plan_provenance.repo` (§3.5). This check matters more here than
   in Phase 5C: getting it wrong would mean stat'ing another project's files.
9. Candidates are taken from `plan.files_likely_to_change` **only**, exact
   duplicates dropped with order preserved. `files_forbidden_or_out_of_scope` is
   never inspected — naming a path as out of scope must not become a way to have
   it examined — and `proposed_steps`, `required_verification`, `risks`, and
   `open_questions` are prose that is never treated as a path. An empty list
   succeeds with an empty result and touches nothing. The count must not exceed
   `read_only_workspace_inspection.max_inspected_files` **or**
   `workspace_policy.max_changed_files`.
10. The lexical Phase 1 `PathPolicy.check_read` runs for **every** candidate.
    Forbidden, outside-the-workspace, traversal-escaping, and unlisted paths are
    refused always; protected paths are refused unless `allow_protected_paths`
    is true. One refusal abandons the **whole** run — a plan naming one
    forbidden path gets no partial inspection of its other paths, per §10's
    no-partial-run rule.
11. **Only now** is the workspace touched. The configured root is canonicalized
    first, which proves it exists, is a directory, and satisfies the symlink
    policy before any candidate is resolved against it. Then each candidate goes
    through `canonicalize_existing_path_under_workspace(...)` with
    `allow_symlinks=project.workspace_policy.allow_symlinks` — the connection
    §17.3 said belonged to "the phase that first calls the guard" — and, on
    success, through a single `os.stat`.

### 18.4 What is reported

One JSON object on stdout carrying: the `notice`; `mode:
"l2-inspect-workspace"`; the project's `project_id`, `repo`, `workspace_policy`
flags, and `inspection_policy` flags; the approval metadata, plan engine,
`real_call`, model, issue number and title; a `workspace_inspection` block; and
`next_authorization_required`.

Each inspected item carries `original_plan_path`, `canonical_relative_path`,
`status`, `kind` (`file` / `directory` / `other`), `size_bytes` (regular files
only), and `symlinks_allowed`. The block also carries the literal
`candidate_source`, and `file_contents_read`, `directories_listed` and
`commands_run` — all three permanently `false`, stated rather than implied.

A candidate that does not exist is reported as `status: "missing"` and the run
continues: a plan naming a file that has not been created yet is ordinary, not a
boundary violation. A containment, symlink, ambiguity, or resolution failure is
a boundary violation and stops the **whole** run with no stdout output. A `stat`
that fails after canonicalization stops the run too, except for a
`FileNotFoundError`, which is the time-of-check/time-of-use race §17.2 describes
and is recorded as `missing`.

Deliberately **not** in the output: the configured `workspace_path`, any
resolved absolute path, any file content, any directory listing, the raw
artifact text, `approval_text`, any prompt or completion, and any API key or
base URL. `required_verification` is absent too — this command did not run it,
and reprinting it here would only invite someone to.

Every failure exits non-zero, writes to **stderr only**, and prints **no stdout
JSON**.

### 18.5 What it is not

- **Not file content access.** No workspace file is opened or read. Verified by
  replacing `Path.read_text` and `builtins.open` with guards that raise for any
  workspace path while leaving the config and artifact reads working.
- **Not directory listing.** A candidate that *is* a directory is reported as
  one and its entries are never enumerated. Verified with `os.listdir`,
  `os.scandir` and `os.walk` detonating around a run that inspects a directory.
- **Not globbing or tree walking.** Candidates come from the plan, one string at
  a time. Nothing is discovered.
- **Not patch proposal, file editing, or command execution.** No diff is
  produced, no file is written, and no `required_verification` entry — or any
  other command — is run. `subprocess.Popen`, `subprocess.run` and `os.system`
  detonate during the tests.
- **Not model-backed.** No model call, no network call, no environment read, no
  `LLMClient`, no `httpx`/`requests` in the command path, no socket.
- **No GitHub fetch and no GitHub write.** There is no option to reach it.
- **No branch, commit, push, or PR.**
- **No artifact writing and no approval stamping.** The command reads the
  artifact and never rewrites it; the orchestrator still never writes an
  `approval` block (§3.6).
- **No agent logic and no implementer/reviewer/fixer role wiring.**
- **No change to any other command.** `version`, `inspect-issue`,
  `llm-smoke-test`, `generate-plan`, `real-llm-smoke-test`,
  `generate-model-plan`, and `l2-dry-run` are untouched, and none of them gained
  an `--inspect-workspace` path or any other L2 option.

### 18.6 Acceptance criteria for Phase 5D1 (DONE)

- [x] Exactly one new command, `l2-inspect-workspace`, exposing
  `--project-config`, `--approved-plan`, `--apply-approved-plan`,
  `--inspect-workspace`, and `--format`, and none of the forbidden options.
- [x] `ReadOnlyWorkspaceInspectionConfig` exists, defaults to disabled, bounds
  `max_inspected_files` to `1..100`, defaults `allow_protected_paths` to false,
  forbids extra fields, holds no secrets, and is absent-means-disabled. The
  example YAML ships it **disabled**.
- [x] **Both confirmation flags fail closed before any file is read** — not the
  artifact, and not even the project config.
- [x] **A disabled or absent config block fails before the artifact is read and
  before the workspace is touched.**
- [x] **An `--approved-plan` inside `repo.workspace_path` is rejected before the
  artifact is read or stat'd**, and its content never surfaces.
- [x] **Parse, validation, and identity failures all occur before any workspace
  touch**, verified by tracking every path passed to `os.stat`, `os.lstat`,
  `os.listdir`, `os.scandir`, `os.path.exists`, `os.path.realpath` and
  `builtins.open`.
- [x] **Candidate-count caps fail before any workspace touch**, for both
  `max_inspected_files` and `max_changed_files`.
- [x] **Lexical `PathPolicy` refusals happen before any canonicalization or
  stat** — forbidden, unlisted, traversal-escaping, absolute-outside, and
  (without `allow_protected_paths`) protected — proven by detonating `os.stat`,
  `os.lstat`, `os.listdir`, `os.scandir`, `os.walk`, `os.path.exists`,
  `os.path.realpath`, `Path.resolve` and `builtins.open` around the call. One
  refusal abandons the whole run.
- [x] **A valid run reports metadata** for existing files (kind, size, canonical
  relative path), existing directories (kind `directory`, null size, contents
  not listed), and missing paths (`status: "missing"`, run continues).
  Duplicates are deduplicated with order preserved.
- [x] **Only `files_likely_to_change` is inspected.**
  `files_forbidden_or_out_of_scope` is not, and `proposed_steps`,
  `required_verification`, `risks` and `open_questions` are never treated as
  paths — asserted by tracking every `os.stat` argument and by checking that
  path-shaped sentinels in those fields never reach stdout.
- [x] **Output omits** `workspace_path`, resolved absolute paths, file contents,
  raw artifact text, `approval_text`, prompt/completion, and any API key or base
  URL.
- [x] **The Phase 5D0 guard is used for every existing candidate**, the root is
  canonicalized first, and `workspace_policy.allow_symlinks` is passed through —
  asserted by spying on the guard. A symlink inside the workspace is rejected
  when `allow_symlinks` is false; one pointing outside is rejected even when it
  is true; and containment/symlink/ambiguity/resolution errors fail closed with
  no stdout.
- [x] **No forbidden behavior**, verified by test: workspace file contents are
  never opened or read; no directory is listed; no command is executed; no
  environment variable, socket, `LLMClient` or `GitHubClient` is reached; no
  file in the workspace or in `tmp_path` is created, modified, or deleted; and
  no artifact is written and no approval stamped.
- [x] **Tests use pytest `tmp_path` only** and name no real target workspace.
- [x] **No CLI behavior changed except adding `l2-inspect-workspace`.**
- [x] **Phase 5D2, Phase 5E, and every later sub-phase in §13 remain proposed
  and not authorized.** Reading file *contents*, proposing a patch, editing a
  file, executing a command, committing, pushing, and opening a PR all still
  require their own explicit authorization. *(Phase 5E has since been split, and
  only its first slice — Phase 5E0, the proposal artifact's models and parser,
  with no generator and no diff — has been authorized and implemented. See §19.
  Phase 5D2 — bounded, redacted file-content reads behind their own project
  opt-in — has since been authorized and implemented too; see §21. Everything
  else on this line is unchanged.)*

## 19. Phase 5E0 — patch proposal artifact models and parser (DONE)

Phase 5E0 is the **first slice** of §13's "Phase 5E — patch proposal artifact
only", and it is deliberately the slice with nothing executable in it: the
artifact's **shape**, as typed models plus a strict parser, and nothing that
produces one.

It ships `src/ai_dev_orchestrator/patch_proposal/` — `models.py` and
`__init__.py` — plus `tests/test_patch_proposal_artifact_models.py`. It is
**library only, wired into nothing**, in the Phase 4B/4F/5B/5D0 tradition.

### 19.1 What it is

- **An error hierarchy.** `PatchProposalError`, and under it
  `PatchProposalParseError` (the text was not one strict JSON object) and
  `PatchProposalValidationError` (the object failed the model). Parser and model
  errors only — there is no apply error, edit error, or command error, because
  there is no apply, edit, or command.
- **Two constants.** `PATCH_PROPOSAL_SCHEMA_VERSION = "patch-proposal.v1"` and
  `PATCH_PROPOSAL_MODE = "proposal-only"`, both enforced as `Literal` on the
  artifact. A different version is a *different artifact* and is rejected, not
  upgraded. There is one mode and it is the harmless one; adding an "apply" mode
  would be a separately authorized phase, not a new enum member.
- **`PatchProposalChange`** — one file a proposal suggests a **human** change:
  `path`, `change_type` (`"modify"` or `"create"`), `rationale`,
  `proposed_steps`, `risks`, and `requires_human_review: Literal[True]` with no
  default. `path` is validated as a **string**: relative, non-blank, no parent
  traversal, no absolute or drive-lettered form, no UNC, no extended-length or
  device prefix, no `:` (so no drive-relative form and no NTFS alternate data
  stream), no `.` or `..` component (so not `"."` either), no empty component,
  no component ending in a dot or a space, and nothing that looks like an 8.3
  short name. The check is **lexical**, mirroring the Phase 5D0 precheck's
  conservatism without importing it — nothing is joined to a workspace root,
  canonicalized, stat'd, or read to decide it.
- **`PatchProposalProvenance`** — `engine` (`"deterministic"`, `"manual"`, or
  `"model"`), `operation` (fixed to `"patch-proposal"`), `real_call`, optional
  `model`, optional `generated_at`, and the identity fields `project_id`,
  `repo`, `issue_number`, `title`. A non-model engine must carry `model: null`
  and `real_call: false` — an engine that does not call a model has no model
  name and made no call, and claiming otherwise is a contradiction rather than
  extra detail. `"model"` must name a model, but that is a **record of a claim**
  about something that happened elsewhere: parsing it calls nothing.
- **`PatchProposalArtifact`** — `schema_version`, `mode`, `provenance`, an
  **untouched `ApprovedL1PlanArtifact` snapshot**, `changes`, `omitted_paths`,
  `assumptions`, `risks`, `open_questions`, the three `Literal[False]` flags
  `file_contents_read` / `files_edited` / `commands_run`,
  `requires_human_review: Literal[True]`, and a non-blank
  `next_authorization_required`.
- **`parse_patch_proposal_artifact(text)`** — a pure strict-JSON parser.
  Surrounding whitespace is tolerated; markdown fences, prose before or after,
  arrays, strings, numbers, booleans and `null` all fail. It **rejects rather
  than repairs**: unknown fields are never stripped and missing fields are never
  inferred. Pydantic's `ValidationError` is wrapped as
  `PatchProposalValidationError`, summarized to field locations and messages so
  a failure never echoes plan prose, rationales, or provenance.

Three cross-field rules carry the safety weight:

- **The approval travels with the thing it approved.** The proposal wraps a full
  `ApprovedL1PlanArtifact`, re-validated on every parse, so a proposal cannot
  restate its own authorization — it can only carry one a human already gave.
  `automation_level == "L1"` and `requires_human_approval is True` are
  re-checked explicitly even though the wrapped model already guarantees both.
- **Exact identity matching** between `provenance` and the approved plan —
  `project_id`, `repo`, `issue_number`, and `title` against the plan's title.
  String equality only, per §3.5.
- **Scope containment: a proposal may narrow, never widen.** Every
  `changes[].path` must appear **exactly** in the plan's
  `files_likely_to_change` and must **not** appear in
  `files_forbidden_or_out_of_scope` — checked forbidden-first, so a
  self-contradicting plan is never resolved in the permissive direction.
  `omitted_paths` carry the same path-safety checks.

**Duplicate paths are rejected, not merged.** This was a deliberate choice: two
changes for one file have no defined precedence, and silently keeping one would
discard work a human was meant to read.

### 19.2 Why there is no diff

The central shape decision is that `PatchProposalChange` carries a *rationale*
and *prose steps* and has **no field for a unified diff**, a hunk, a patch, an
edit script, a command, before/after content, or any other applyable payload.
That is not an omission to be filled in later by adding a key — a payload
carrying one is rejected as an extra field, at every model level.

Two reasons. First, a real diff requires reading file **contents**, which is
Phase 5D2 and is not authorized; a proposal artifact that could carry one would
quietly create demand for that read. Second, an artifact with nothing applyable
in it cannot be applied by mistake: there is no payload for a future bug, a
future command, or a confused operator to feed to a patch tool.

The three `Literal[False]` flags work the same way. In Phase 5E0 they are not
*observations* — they are the **shape of a legal artifact**. Nothing in this
repository can produce a proposal for which any of them would be true, so a
payload claiming one is describing something this phase does not do, and it is
rejected.

### 19.3 What it is not

- **Not patch generation.** There is no generator, deterministic or otherwise.
  Nothing here produces a proposal; a parsed one was written elsewhere.
- **Not a diff.** See §19.2.
- **Not file editing, not command execution.** Nothing is applied, run, or
  written.
- **No file contents read.** No source text, excerpt, or command output has a
  field here, and the parser opens nothing.
- **No workspace access.** No target project workspace is read, listed, stat'd,
  or resolved. Paths are strings, validated lexically, never canonicalized.
- **No file loading.** The parser is handed a string; there is no loader.
- **No CLI behavior.** No command, no option, and nothing in `cli.py` changed or
  imports the package.
- **No model, network, or environment access.** `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `os`, `pathlib`, `socket` and `subprocess` are not
  imported, so no code path can reach any of them.
- **No clock.** `generated_at` is parsed when supplied and never produced.
- **No approval stamping.** Nothing writes an approved-plan artifact or creates
  an approval; the wrapped one is re-validated, never authored.
- **Not authorization.** A parsed proposal is data describing suggested work.
  L2 remains unbuilt, and nothing consumes this.

### 19.4 Acceptance criteria for Phase 5E0 (DONE)

- [x] `PatchProposalError` / `PatchProposalParseError` /
  `PatchProposalValidationError` exist, share one base, and cover parsing and
  validation only.
- [x] `PATCH_PROPOSAL_SCHEMA_VERSION` and `PATCH_PROPOSAL_MODE` exist and are
  enforced exactly — a near-miss version or mode is rejected, and neither has a
  default.
- [x] A valid artifact parses, carries an **unchanged** `ApprovedL1PlanArtifact`
  snapshot, and may have **empty** `changes` (meaning "no patch proposed yet").
  One `modify` change and one `create` change each parse.
- [x] `provenance` identity must match the approved plan exactly on
  `project_id`, `repo`, `issue_number`, and `title`; matching is not normalized.
- [x] `provenance` rejects `endpoint_host`, `base_url`, `api_key`, `prompt`,
  `completion`, `messages`, `raw_response` and `workspace_path` as extras, and
  the rejection never echoes what the field held.
- [x] `"deterministic"` and `"manual"` require `real_call: false` and
  `model: null`; `"model"` requires a non-blank model name and still performs no
  model call — asserted with `socket` and `os.getenv` detonated.
- [x] Every `changes[].path` must be exactly one of the plan's
  `files_likely_to_change`; a path in `files_forbidden_or_out_of_scope` is
  rejected even when the plan also lists it as likely to change.
- [x] **Duplicate change paths are rejected**, deliberately, and documented.
- [x] Unsafe paths are rejected for both `changes[].path` and `omitted_paths`:
  blank, absolute, drive-lettered, parent traversal, UNC, extended-length,
  device, `:`-bearing, trailing dot, trailing space, 8.3-like, `"."`, `"./x"`,
  and empty components — refused **lexically**, with `os.stat`,
  `os.path.realpath` and `builtins.open` detonated.
- [x] `rationale` non-blank, `proposed_steps` non-empty and non-blank, `risks`
  entries non-blank, `requires_human_review` true with no default.
- [x] `file_contents_read`, `files_edited` and `commands_run` are rejected when
  true and have no defaults; `requires_human_review` false is rejected;
  `next_authorization_required` is required and non-blank.
- [x] **Extra fields are rejected at every model level**, including
  diff/patch/hunk/edit, file-content, before/after, command and command-output,
  prompt/completion, API-key/base-URL, `workspace_path`, raw-artifact-text, and
  a top-level `approval`. No such field exists on any model.
- [x] The parser accepts surrounding whitespace and rejects empty text, invalid
  JSON, markdown-fenced JSON, prose before or after the object, and JSON arrays,
  strings, numbers, booleans and `null`.
- [x] **The parser performs no file, network, process, environment or workspace
  IO**, on both success and failure paths, verified by detonating
  `builtins.open`, `os.getenv`, `os.environ.get`, `os.stat`, `os.lstat`,
  `os.listdir`, `os.scandir`, `os.walk`, `os.path.exists`, `os.path.abspath`,
  `os.path.realpath`, `socket.socket`, `socket.create_connection`,
  `socket.getaddrinfo` and `subprocess.Popen`. It prints nothing and writes no
  file.
- [x] The implementation module's globals contain none of `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `Path`, `os`, `socket`, `subprocess`.
- [x] The package exports exactly the nine Phase 5E0 names, and no generator,
  applier, loader, or implementer.
- [x] **No CLI behavior added.** Root help still lists exactly `version`,
  `inspect-issue`, `llm-smoke-test`, `generate-plan`, `real-llm-smoke-test`,
  `generate-model-plan`, `l2-dry-run`, `l2-inspect-workspace`; `cli.py` is
  unchanged and does not import the package; and `l2-inspect-workspace`,
  `l2-dry-run`, `generate-plan` and `generate-model-plan` keep their exact
  options. *(Phase 5E1 has since added a ninth command,
  `generate-patch-proposal`, which imports the package lazily inside its own
  body. Nothing else in this list changed. See §20.)*
- [x] **No forbidden behavior**: no workspace access, no file contents read, no
  patch generated, no file edited, no command executed, no GitHub fetch or
  write, no model or network or environment access, no agent logic or role
  wiring, no approved-plan artifact written, and no approval stamped.
- [x] **Phase 5D2, Phase 5E1, Phase 5E2, and every later sub-phase in §13 remain
  proposed and not authorized.** Generating a proposal, carrying a real diff,
  reading file contents, editing a file, executing a command, committing,
  pushing, and opening a PR all still require their own explicit authorization.
  *(Phase 5E1 — generating a proposal, deterministically and offline, with no
  diff and no file contents — has since been authorized and implemented. See
  §20. So has Phase 5D2 — bounded, redacted file-content reads printed to
  stdout, still with no diff and no edits; see §21. So has Phase 5E2 — typing a
  diff-bearing artifact and parsing it, with no generator and no applier; see
  §22. Everything else on this line is unchanged.)*

## 20. Phase 5E1 — deterministic patch proposal generator (DONE)

Phase 5E0 shipped the proposal artifact's shape and deliberately no producer.
Phase 5E1 is the producer, and it is deliberately the dullest one that could
exist.

It ships `src/ai_dev_orchestrator/patch_proposal/generator.py`, the one new CLI
command `generate-patch-proposal`, and
`tests/test_patch_proposal_generator.py` plus
`tests/test_cli_generate_patch_proposal.py`.

### 20.1 What it is

- **`build_deterministic_patch_proposal(*, approved_plan, project)`** — a
  **pure function** over two already-loaded objects, an `ApprovedL1PlanArtifact`
  and a `ProjectConfig`, returning a validated `PatchProposalArtifact`. No file
  IO, no workspace access, no environment read, no model, no network, no
  GitHub, no clock, no command, no file edit, no diff, and no artifact file
  written. It prints nothing.
- **`PatchProposalGenerationError`** — one error, for an identity mismatch, a
  self-contradicting plan, a candidate count above the cap, or a failure of the
  Phase 5E0 artifact validation. There is deliberately **no apply error, edit
  error, or command error**, because there is no apply, no edit, and no command.
  Its messages name the failed field and the category and never echo the
  artifact text, the plan prose, or any supplied value.
- **`generate-patch-proposal`** — exactly one new command, with exactly five
  options: `--project-config`, `--approved-plan`, `--apply-approved-plan`,
  `--generate-proposal`, and `--format json`. There is no `--output`, no
  `--model`, no `--real-model`, no `--diff`, no `--apply-patch`, no
  `--read-contents`, no `--inspect-workspace`, no `--command`, no `--edit`, and
  no `--github`.

**What it proposes.** Candidates come from the approved plan's
`files_likely_to_change` and **nowhere else**. Exact duplicates are deduplicated
preserving order; `files_forbidden_or_out_of_scope` is never a candidate source;
and `proposed_steps`, `required_verification`, `risks` and `open_questions` are
prose that is never read as a path. Each surviving path becomes one `modify`
change carrying a fixed rationale, two prose review steps, one risk, and
`requires_human_review: true`. An empty `files_likely_to_change` produces a
valid artifact with `changes: []` and an assumption saying so — a well-formed
statement about a plan, not a defect.

**Determinism is a property, not a nicety.** The same inputs produce a
byte-identical artifact, which is why `generated_at` is `None` and why every
rationale, step, assumption and risk is fixed prose. A generator that stamped a
timestamp would be impossible to diff or re-verify.

**The generated provenance describes the generator, not its input.** `engine:
"deterministic"`, `real_call: false`, `model: null` — facts about this function.
The wrapped plan's own provenance may well record a real model call; that claim
stays inside the untouched snapshot and is never promoted to the proposal.

### 20.2 How it fails closed

In order, before anything is produced: exact identity matching of
`project_id`, `repo`, `plan.repo` and `plan_provenance.repo` against the project
config (string equality only — no normalization, no case folding, no prefix
matching, per §3.5); a re-check that the plan is `automation_level == "L1"` with
`requires_human_approval is True`, even though `ApprovedL1PlanArtifact`
guarantees both; refusal of a plan that lists a path as **both** likely-to-change
and forbidden, rather than resolving the contradiction in the permissive
direction; and the `workspace_policy.max_changed_files` cap on distinct
candidates.

The artifact is then assembled and handed to `PatchProposalArtifact` validation
rather than constructed field by field, so an unsafe path, an out-of-scope path,
a duplicate, or an identity slip is caught by the **same** rules that guard a
proposal arriving from outside this repository. The generator gets no privileged
path around them.

The command's gate ordering mirrors `l2-dry-run`'s with one more consent in
front: `--apply-approved-plan` and `--generate-proposal` both first — with **no
file read at all** if either is missing — then the project config, then a
string/path check rejecting an `--approved-plan` inside the configured workspace
**before** the artifact is opened or stat'd, then the strict Phase 5B parse,
then the generator. Any failure exits non-zero with stderr only and nothing on
stdout.

### 20.3 What it is not

- **Not a diff.** §19.2 applies unchanged. `PatchProposalChange` still has no
  field for a unified diff, a hunk, a patch, an edit script, before/after
  content, a command, or command output, so the generator has nothing applyable
  to emit.
- **No file contents read.** Nothing is opened, which is exactly why
  `change_type` is always `"modify"`: telling "create" from "modify" would need
  workspace metadata this phase does not gather. That limit is recorded as an
  *assumption in the artifact* rather than guessed at.
- **No workspace access.** No target project workspace is read, listed, stat'd,
  globbed, walked, or resolved. Paths stay strings and are never joined to a
  workspace root or canonicalized; the Phase 5D0 guard is not called.
- **No artifact file written.** The command prints to **stdout only**, with no
  wrapper around the artifact, so its output parses with
  `parse_patch_proposal_artifact`. There is no `--output` option.
- **Not file editing, not command execution.** Nothing is applied, run, or
  written. `required_verification` travels inside the embedded plan snapshot as
  the plan prose it always was, and is never executed.
- **No model, network, environment, or GitHub access.** `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `Path`, `os`, `socket` and `subprocess` are not
  importable in the generator module.
- **No agent logic, no role wiring, no approval stamping.** The approval inside
  the wrapped `ApprovedL1PlanArtifact` travels through unchanged and is
  re-validated, never authored.
- **Not authorization.** A generated proposal is data describing suggested work.
  L2 remains unbuilt.

### 20.4 Acceptance criteria for Phase 5E1 (DONE)

- [x] `build_deterministic_patch_proposal` is a pure keyword-only function over
  an `ApprovedL1PlanArtifact` and a `ProjectConfig`, and returns a
  `PatchProposalArtifact` that round-trips through
  `parse_patch_proposal_artifact`.
- [x] The wrapped approved-plan snapshot travels through **unchanged**, and the
  input object is not mutated.
- [x] Generation is **deterministic**: the same inputs produce byte-identical
  JSON.
- [x] One path yields one `modify` change; multiple paths preserve order;
  duplicates are deduplicated preserving first position; an empty
  `files_likely_to_change` yields `changes: []` plus an explanatory assumption.
- [x] `files_forbidden_or_out_of_scope` is never proposed, and `proposed_steps`,
  `required_verification`, `risks` and `open_questions` are never treated as
  paths.
- [x] Fails closed on: a path listed as both likely and forbidden, an unsafe
  path, more distinct paths than `workspace_policy.max_changed_files`, and a
  `project_id` or `repo` mismatch (including a case-folded repo).
- [x] Generated provenance is `engine: "deterministic"`, `real_call: false`,
  `model: null`, `generated_at: null`, and does not inherit the wrapped plan's
  real-model claim.
- [x] `file_contents_read`, `files_edited` and `commands_run` are all false;
  `requires_human_review` is true; `next_authorization_required` names Phase
  5D2/5E2 and the actions still unauthorized.
- [x] No diff, content, or command field exists on the artifact or on any
  change, and each change carries exactly `path`, `change_type`, `rationale`,
  `proposed_steps`, `risks`, `requires_human_review`.
- [x] **The generator performs no file, environment, network, process, or
  workspace IO**, on both success and failure paths, verified by detonating
  `builtins.open`, `os.getenv`, `os.environ.get`, `os.stat`, `os.listdir`,
  `os.scandir`, `os.walk`, `os.path.exists`, `os.path.abspath`,
  `os.path.realpath`, `socket.*` and `subprocess.*`. It prints nothing and
  writes no file.
- [x] The generator module's globals contain none of `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `Path`, `os`, `socket`, `subprocess`, and the CLI
  helper's source names none of them either.
- [x] `generate-patch-proposal` appears in root help alongside the eight
  existing commands; its help exposes only `--project-config`,
  `--approved-plan`, `--apply-approved-plan`, `--generate-proposal`,
  `--format` and `--help`, and rejects `--output`, `--model`, `--real-model`,
  `--diff`, `--apply-patch`, `--read-contents`, `--inspect-workspace`,
  `--command`, `--edit`, `--body-file`, `--issue`, `--title`, `--github`,
  `--fetch`, `--workspace`, `--file`, `--context-file` and `--audit-dir`.
- [x] A missing `--apply-approved-plan` or `--generate-proposal` fails **before
  any file is read** — not the artifact, and not even the config — with stderr
  only and empty stdout.
- [x] An `--approved-plan` inside the configured workspace is rejected **before
  it is read or stat'd**, and only the config had been read at that point.
- [x] An invalid approved artifact fails before generation; an identity
  mismatch, a self-contradicting plan, an over-cap path count and an unsafe path
  all fail closed with empty stdout and without echoing plan prose or the
  approval text.
- [x] The command reads **exactly two files**, both named on the command line,
  config first.
- [x] Stdout is the artifact itself with no wrapper and parses with
  `parse_patch_proposal_artifact`; it omits `workspace_path`, absolute paths,
  raw artifact text, API keys and base URLs, source contents, diffs and command
  output. `approval_text` appears only inside the embedded snapshot.
- [x] **No CLI behavior changed except adding `generate-patch-proposal`.**
  `l2-inspect-workspace`, `l2-dry-run`, `generate-plan`, `generate-model-plan`
  and `real-llm-smoke-test` keep their exact options, and no other command
  gained `--generate-proposal`, `--diff`, or `--apply-patch`.
- [x] **No forbidden behavior**: no workspace access, no file contents read, no
  diff generated, no file edited, no command executed, no GitHub fetch or write,
  no model / network / environment access, no agent logic or role wiring, no
  artifact file written, and no approval stamped.
- [x] **Tests use pytest `tmp_path` and literal data only**, and name no real
  target workspace.
- [x] **Phase 5D2, Phase 5E2, and every later sub-phase in §13 remain proposed
  and not authorized.** Reading file contents, carrying a real diff, editing a
  file, executing a command, committing, pushing, and opening a PR all still
  require their own explicit authorization. *(Phase 5D2 — bounded, redacted
  file-content reads — has since been authorized and implemented; see §21. It
  supplies the reads Phase 5E2 would need and authorizes none of the rest. Phase
  5E2 has since been implemented as **models and a parser only** — a diff may
  now be carried and validated as data, but still not generated, modified, or
  applied; see §22.)*

## 21. Phase 5D2 — bounded read-only file-content inspection (DONE)

Phase 5D1 shipped the first command that may *touch* a target workspace. Phase
5D2 adds **one** command, `l2-read-workspace-files`, and it is the first phase
whose **output may contain that workspace's source**.

That is the whole of the increase, and it is deliberately treated as a bigger
step than it looks. §18 draws the line between "does `src/foo/bar.py` exist and
how big is it" and "what does `src/foo/bar.py` say"; this phase crosses it, and
so it re-runs every Phase 5D1 gate, adds a second consent flag and a **separate**
project opt-in in front of them, bounds the read three ways, and redacts
everything it prints.

**Phase 5D2 is not L2.** It proposes nothing, diffs nothing, patches nothing,
edits nothing, runs nothing, and calls no model. It ships
`tests/test_cli_l2_read_workspace_files.py`, a new config block, and no new
module.

### 21.1 What it is

- **`l2-read-workspace-files`** — exactly one new command, with exactly five
  options: `--project-config`, `--approved-plan`, `--apply-approved-plan`,
  `--read-contents`, and `--format json`. There is no `--output`, no `--model`,
  no `--real-model`, no `--diff`, no `--apply-patch`, no `--generate-proposal`,
  no `--inspect-workspace`, no `--workspace`, no `--file`, no `--command`, no
  `--edit`, no `--run`, no `--verify`, and no `--github`.
- **`ReadOnlyWorkspaceContentConfig`** — a project-level opt-in block,
  `read_only_workspace_content`, holding `enabled` (default false), `max_files`
  (default 10, ≤ 50), `max_file_bytes` (default 50 000, ≤ 1 000 000),
  `max_total_bytes` (default 200 000, ≤ 5 000 000), and `allow_protected_paths`
  (default false). `extra="forbid"`; no credential, endpoint, model name, or
  environment-variable name may appear in it. An absent block is identical to a
  disabled one, and the shipped example config ships it **disabled**.

**It is a separate opt-in from Phase 5D1's on purpose.** A project that has
agreed to have its path names stat'd has not thereby agreed to have its source
printed. `read_only_workspace_inspection.enabled: true` grants nothing here, and
this command refuses to touch the workspace at all until
`read_only_workspace_content.enabled` is true — failing before the approved-plan
artifact is even opened.

**What it reads.** Candidates come from the approved plan's
`files_likely_to_change` and **nowhere else**. Exact duplicates are deduplicated
preserving order; `files_forbidden_or_out_of_scope` is never read — naming a
path as out of scope must not become a way to have it printed — and
`proposed_steps`, `required_verification`, `risks` and `open_questions` are
prose that is never treated as a path. An empty `files_likely_to_change`
succeeds with `items: []` and an explanatory note, and the workspace is not
touched at all.

**How the read is bounded.** Three caps, each enforced separately: at most
`max_files` distinct candidates (checked *before* the workspace is touched); at
most `max_file_bytes` for any single file; and at most `max_total_bytes` across
the whole invocation. The per-file cap is enforced at the read itself — the
helper asks for `limit + 1` bytes and refuses anything longer — so a file that
grew between the `stat` and the open is still refused rather than slurped
whole.

**Redaction is mandatory.** Every byte that reaches stdout passes through
`_redact_secret_like_text`, which blanks `Bearer <token>`, `key = value` pairs
for `api_key`/`apikey`/`token`/`secret`/`password`/`passwd`/`pwd`, and
OpenAI-style `sk-…` strings. It is deliberately three simple deterministic
patterns and **does not claim to be reliable secret detection** — the output
says as much, reports `redacted`, `redaction_count` and `redaction_kinds`, and
there is **no configuration option and no flag that turns redaction off**.

### 21.2 How it fails closed

Before the workspace is touched at all, in order: `--apply-approved-plan`, then
`--read-contents` (a plain invocation missing either reads **no file at all** —
not the artifact, and not even the config); then the project config; then
`read_only_workspace_content.enabled`; then a string/path check rejecting an
`--approved-plan` inside the configured workspace **before** it is read or
stat'd; then the artifact read; then the strict Phase 5B parse; then exact
`project_id`/`repo`/`plan.repo`/`plan_provenance.repo` matching against the
config; then the `max_files` and `max_changed_files` candidate caps; then the
lexical Phase 1 path policy for **every** candidate, with forbidden, outside and
unlisted paths always refused and protected paths refused unless
`allow_protected_paths` is true. One refused candidate abandons the whole run —
a plan naming one forbidden path does not get the contents of its other paths
printed.

Only then is the workspace touched, root first, through the Phase 5D0 guard
honoring `workspace_policy.allow_symlinks`. Per candidate the outcomes split
into two kinds. **Reportable, run continues:** `missing`,
`directory_no_content`, `other_no_content`, `too_large`, `skipped_total_limit`,
`binary_or_non_utf8` — each with a null `content_text` and `bytes_read: 0`.
**Fatal, whole run abandoned with empty stdout:** any containment, symlink,
ambiguity or resolution failure from the guard, and any read error after the
`stat` other than a `FileNotFoundError` race, which is recorded as `missing`.

Every failure exits non-zero with stderr only, prints no stdout JSON, and never
echoes the artifact text, the plan prose, the approval text, or any file
content.

### 21.3 What it is not

- **Not directory listing.** `os.listdir`, `os.scandir` and `os.walk` are never
  called, and no glob or tree walk exists. A candidate that *is* a directory is
  reported as `directory_no_content`; its entries are neither enumerated nor
  named.
- **Not diff generation.** Nothing produces a unified diff, a hunk, a patch, or
  a before/after pair, and no item carries a field that could hold one.
- **Not file editing, not command execution.** Nothing is written, applied, or
  run. `required_verification` is not output and not executed.
- **Not model-backed, and not a path to a model.** No `LLMClient`, no `httpx`,
  no socket, no environment read. The content this command reads goes to stdout
  and nowhere else; **file content is never sent to a model.**
- **Not full L2.** It creates no branch, no commit, no PR, writes no artifact
  file, stamps no approval, and adds no agent logic or implementer/reviewer/
  fixer role wiring.
- **Not authorization.** Printing what a file says is not permission to change
  it. L2 remains unbuilt.

### 21.4 Output shape

Stdout is one JSON object: a `notice`, `mode: "l2-read-workspace-files"`, the
`project` block (identity, `workspace_policy`, and the `content_policy` caps
including `redaction: "mandatory_basic_secret_like_redaction"`), the
`approved_plan` provenance summary, a `workspace_content` block, and
`next_authorization_required`.

`workspace_content` carries the note, `candidate_source`, the four false flags
`directories_listed` / `commands_run` / `model_called` / `diffs_generated` /
`files_edited`, `file_contents_read: true`, `total_bytes_read`, and `items`.
Deliberately absent everywhere: the configured `workspace_path`, any resolved
absolute path, any directory listing, any diff, any command or command output,
the raw artifact text, `approval_text`, `required_verification`, any prompt or
completion, and any API key or base URL. **File content appears in exactly one
place** — `workspace_content.items[].content_text` — after the byte caps and
after redaction.

### 21.5 Acceptance criteria for Phase 5D2 (DONE)

- [x] `l2-read-workspace-files` appears in root help alongside the nine existing
  commands; its help exposes only `--project-config`, `--approved-plan`,
  `--apply-approved-plan`, `--read-contents`, `--format` and `--help`, and
  rejects `--output`, `--model`, `--real-model`, `--body-file`, `--issue`,
  `--title`, `--github`, `--fetch`, `--workspace`, `--file`, `--context-file`,
  `--command`, `--edit`, `--audit-dir`, `--inspect-workspace`,
  `--generate-proposal`, `--diff`, `--apply-patch`, `--run` and `--verify`.
- [x] `read_only_workspace_content` defaults to disabled when absent, rejects
  unknown fields, and rejects out-of-range or non-integer caps. The shipped
  example config carries the block **explicitly disabled**.
- [x] A missing `--apply-approved-plan` or `--read-contents` fails **before any
  file is read** — not the artifact, and not even the config — with stderr only
  and empty stdout, with every filesystem entry point detonated.
- [x] A disabled or absent config block fails **before the artifact read and
  before any workspace touch**, and Phase 5D1's opt-in does not substitute for
  it.
- [x] An `--approved-plan` inside the configured workspace is rejected **before
  it is read or stat'd**, with only the config read at that point.
- [x] Artifact parse failure, artifact validation failure, identity mismatch,
  and both candidate caps each fail **before any workspace touch**.
- [x] Lexical path-policy refusals — forbidden, unlisted, escaping, absolute-
  outside, and protected without `allow_protected_paths` — happen **before any
  canonicalization, stat, or open**, and one refusal abandons the whole run.
- [x] An existing small UTF-8 file under an allowed path reports `read` with its
  `content_text`; multiple files preserve plan order; duplicates are
  deduplicated preserving first position; an empty candidate list succeeds
  without touching the workspace.
- [x] `missing`, `directory_no_content`, `too_large`, `skipped_total_limit` and
  `binary_or_non_utf8` are each reported with a null `content_text` and
  `bytes_read: 0`, and the run continues. A NUL byte and invalid UTF-8 are both
  refused, and neither file's bytes appear in the output.
- [x] Only `files_likely_to_change` is read: `files_forbidden_or_out_of_scope`
  and the prose fields are never opened and never printed, verified with real
  files present at those paths.
- [x] Redaction blanks Bearer tokens, `api_key`/`token`/`secret`/`password`/
  `passwd`/`pwd` assignment values (including underscore-prefixed names) and
  `sk-…` keys, reports `redacted`, `redaction_count` and `redaction_kinds`, and
  **cannot be disabled** by any config field or flag.
- [x] The Phase 5D0 guard is used for every candidate, the root is proven first,
  `workspace_policy.allow_symlinks` is passed through, a symlink inside the
  workspace is rejected when symlinks are disallowed, one pointing outside is
  rejected even when they are allowed, and containment/symlink/ambiguity/
  resolution failures fail closed with empty stdout.
- [x] **No forbidden behavior**: no directory listed (`os.listdir`,
  `os.scandir`, `os.walk` detonated), no command executed (`subprocess.Popen`,
  `subprocess.run`, `os.system` detonated), no environment/network/model access
  (`os.getenv`, `os.environ.get`, `socket.*`, `LLMClient`,
  `load_llm_client_config_from_env` detonated), no GitHub access
  (`GitHubClient.__init__`/`get_issue` detonated), no diff generated, no file
  edited (workspace and tmp bytes snapshotted before and after), no artifact
  written and no approval stamped.
- [x] The command reads **exactly** the config, the artifact, and the approved
  candidate files — the first two as text in that order, the candidates as
  bytes through one bounded helper — and the command's source names none of
  `httpx`, `requests`, `LLMClient`, `load_llm_client_config_from_env`,
  `GitHubClient`, `subprocess`, `os.environ`, `getenv`, `difflib`,
  `unified_diff`, `apply_patch`, `git commit`, `git push`, or any write call.
- [x] Output omits `workspace_path`, resolved absolute paths, raw artifact text,
  `approval_text`, `required_verification`, diffs, command output and
  credentials; file content appears only under `items[].content_text`.
- [x] **No CLI behavior changed except adding `l2-read-workspace-files`.**
  `generate-patch-proposal`, `l2-inspect-workspace`, `l2-dry-run`,
  `generate-plan` and `generate-model-plan` keep their exact options, and no
  other command gained `--read-contents`.
- [x] **Tests use pytest `tmp_path` only**, and name no real target workspace.
- [x] **Phase 5E2 and every later sub-phase in §13 remain proposed and not
  authorized.** Generating a diff, editing a file, executing a command,
  committing, pushing, opening a PR, and sending source contents to a model all
  still require their own explicit authorization. *(Phase 5E2 — typing a
  diff-bearing artifact and parsing it, with no generator and no applier — has
  since been authorized and implemented as §22. It authorizes none of the
  actions above.)*

## 22. Phase 5E2 — unified diff proposal artifact models and parser (DONE)

Phase 5E0 typed a proposal that deliberately carried **prose only**. Its
`PatchProposalChange` had a `rationale` and `proposed_steps` and no field a diff
could live in, because a real diff meant reading file contents, which was
unauthorized then. Phase 5D2 has since shipped bounded, redacted content reads
behind their own project opt-in and two explicit flags.

Phase 5E2 is the next step and is deliberately the inert half of it: it lets a
unified-diff-shaped artifact **exist as data** and be validated. It ships
`ai_dev_orchestrator.diff_proposal` — `DiffProposalFileChange`,
`DiffProposalProvenance`, `DiffProposalArtifact`, the three-error hierarchy, and
`parse_diff_proposal_artifact` — and **nothing else**.

**Phase 5E2 is not diff generation, and not diff application.** There is no
generator here and no applier. Nothing produces a diff, modifies one, applies
one, or asks whether one would apply — a parsed diff was written by something
outside this repository, and the producer is Phase 5E3, which is proposed and not
authorized.

### 22.1 What the artifact carries, and what it refuses to carry

The wrapper is Phase 5E0's, one field wider:

- an **untouched** `ApprovedL1PlanArtifact` snapshot, re-validated on every parse
  and matched **exactly** on `project_id`, `repo`, `issue_number` and `title`;
- an **optional, untouched** Phase 5E0 `PatchProposalArtifact` snapshot — the
  prose proposal the diffs were drafted from. When present, its approved plan
  must match this one by `model_dump`, its identity must match, and no diff may
  name a path the prose proposal did not (unless it named none at all, which
  means "no paths chosen yet", not "no paths permitted");
- `changes`, each carrying a **`unified_diff`**;
- the same scope containment as 5E0: every `changes[].path` **exactly** in
  `files_likely_to_change`, never in `files_forbidden_or_out_of_scope`, no
  duplicates (rejected, never merged), and the same conservative lexical path
  safety on every path string;
- flags describing what did and did not happen: `diffs_generated` is
  `Literal[True]`, `files_edited` / `commands_run` / `applies_cleanly_checked`
  are `Literal[False]` with no defaults, and `source_contents_read` is a plain
  `bool` because a producer plausibly *did* read contents to draft a diff — the
  parser records that **claim** and reads nothing itself.

The `unified_diff` string may contain source lines as diff context. That is what
a diff is, and it is allowed **as data in this artifact**. It arrived in the text
handed to the parser; nothing here opened a file to obtain it and nothing here
sends it anywhere. There is deliberately **no** separate `before_content`,
`after_content`, `file_contents` or `source_contents` field: source text lives
inside the diff or nowhere. There is likewise no `command`, `command_output`,
`apply`, `auto_apply`, `workspace_path`, `prompt`, `completion`, `api_key`,
`base_url`, `approval`, or `raw_artifact_text` field, and every model is
`extra="forbid"`, so a payload carrying one is **rejected**, not stored.

### 22.2 What "a valid diff" means here — shape, never applicability

The accepted shape is the narrowest thing that is still a real diff:

```
--- a/<path>        (or '--- /dev/null' when change_type is 'create')
+++ b/<path>
@@ ... @@
...
```

Exactly one `---` line and one `+++` line, the second immediately after the
first, both equal to the expected header **exactly** — no timestamp suffix, no
`a/`-less form, no substituted path — followed by at least one `@@` hunk header.
`change_type` is `modify` or `create` only.

Refused outright, as substrings anywhere in the payload: `GIT binary patch`,
`Binary files `, `rename from `, `rename to `, `similarity index `,
`delete file mode`, `old mode `, `new mode `, and `diff --git`. The first two are
not reviewable text; the next four move or destroy a path, and a path the plan
listed as changeable is not thereby a path it authorized removing; mode changes
are invisible in a reviewed diff body; and `diff --git` is the *envelope* that
carries all of them and that multi-file patches are built from. A multi-file
patch therefore fails on the header count, and so — conservatively, on purpose —
does a diff whose body happens to contain a line starting with `--- ` or `+++ `.
A NUL byte is refused, and the payload is capped at 200 000 characters.

**Applicability is never checked.** Whether the hunk counts are arithmetically
consistent, whether the context matches any real file, and whether the diff would
apply are all questions this phase does not ask, because the last two require
touching a workspace. No patch tooling is invoked, `difflib` is not imported, and
line endings inside a diff are **not normalized** — the string is carried through
byte for byte.

### 22.3 Acceptance criteria for Phase 5E2 (DONE)

- [x] A valid artifact parses; a `modify` diff and a `create` diff each parse;
  an artifact with **empty** `changes` parses ("no diff proposed yet" is
  well-formed); surrounding whitespace is tolerated.
- [x] The wrapped `ApprovedL1PlanArtifact` round-trips unchanged, and the
  optional `PatchProposalArtifact` snapshot may be absent, null, or present —
  and when present must match by `model_dump` and by identity.
- [x] `schema_version` is exactly `diff-proposal.v1` and `mode` exactly
  `proposal-only`; `diffs_generated` must be true; `files_edited`,
  `commands_run` and `applies_cleanly_checked` must be false; each has no
  default; `requires_human_review` must be true; `next_authorization_required`
  is required and non-blank.
- [x] Provenance identity must match the approved plan exactly, `operation` is
  `diff-proposal` only, non-model engines carry no model and no real call, a
  `model` engine must name one — and parsing it **calls nothing**, with sockets
  and the environment detonated. `generated_at` is parsed, never produced.
- [x] Provenance rejects `endpoint_host`, `base_url`, `api_key`, `prompt`,
  `completion`, `messages`, `raw_response` and `workspace_path` as extras, and
  the rejection never echoes what they held.
- [x] Scope containment holds: paths outside `files_likely_to_change` are
  rejected, forbidden paths are rejected (and forbidden wins over a
  self-contradicting plan), duplicates are rejected, and a diff for a path the
  wrapped patch proposal did not name is rejected.
- [x] The full unsafe-path set — blank, absolute, drive-lettered, colon/ADS,
  traversal, UNC, extended-length, device, trailing dot, trailing space,
  8.3-like, `.`, `./x`, doubled separator — is refused for `changes[].path` and
  `omitted_paths`, lexically, even when the plan itself lists the unsafe path.
- [x] Diff shape is enforced: exact `--- a/<path>` / `+++ b/<path>` for
  `modify`, exact `--- /dev/null` / `+++ b/<path>` for `create`, mismatched or
  unsafe header paths rejected, missing `---` / `+++` / `@@` rejected, headers
  out of order rejected, multi-file rejected, `diff --git` rejected, binary /
  rename / delete / mode metadata rejected, NUL rejected, over-long rejected.
- [x] **No apply check is performed**: an arithmetically nonsense diff whose
  context matches nothing parses fine, with `subprocess` and `open` detonated.
  Line endings and source lines are carried through verbatim.
- [x] Artifact-level and change-level payload extras are rejected —
  `raw_artifact_text`, `source_contents`, `file_contents`, `before_content`,
  `after_content`, `command`, `commands`, `command_output`, `prompt`,
  `completion`, `api_key`, `base_url`, `workspace_path`, `approval`, `apply`,
  `auto_apply` — and no rejection echoes the value.
- [x] The parser rejects empty text, invalid JSON, markdown-fenced JSON (both a
  JSON fence and a `diff` fence), prose before or after, and JSON arrays /
  strings / numbers / booleans / `null`; it wraps `ValidationError` as
  `DiffProposalValidationError`, never repairs, never strips unknown fields, is
  deterministic, and **prints nothing**.
- [x] **The parser performs no IO**: `builtins.open`, `os.getenv`,
  `os.environ.get`, `os.stat`, `os.lstat`, `os.listdir`, `os.scandir`,
  `os.walk`, `os.path.exists/abspath/realpath`, `socket.*`, `subprocess.run`
  and `subprocess.Popen` are all detonated across a successful parse and across
  failure paths, and no file is written.
- [x] The implementation module's globals contain none of `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `Path`, `os`, `socket`, `subprocess`, `yaml`,
  `difflib`, and its source names no transport, CLI, workspace, or clock import.
- [x] The package exports exactly the nine Phase 5E2 names, and no generator, no
  applier, no loader, and no writer.
- [x] **No CLI behavior added.** Importing `diff_proposal` registers no command;
  `l2-read-workspace-files`, `generate-patch-proposal`, `l2-inspect-workspace`,
  `l2-dry-run`, `generate-plan` and `generate-model-plan` keep their exact
  options and gain no `--diff`, `--diff-proposal`, `--apply-patch`,
  `--edit-files` or `--implement`. *(Phase 5E3 has since added an eleventh
  command, `generate-diff-proposal`, which produces this artifact and prints it;
  it changed none of the ten above — see §23.)*
- [x] **Tests use literal dicts and hand-typed diffs only** — no real file, no
  real environment, no network, no target workspace created or named.
- [x] **Phase 5E3 and every later sub-phase in §13 remain proposed and not
  authorized.** Generating a diff, applying one, editing a file, executing a
  command, committing, pushing, opening a PR, and sending source contents to a
  model all still require their own explicit authorization. *(Phase 5E3 —
  generating a diff, deterministically and offline, from local JSON inputs, with
  nothing applied and no workspace read — has since been authorized and
  implemented; see §23. Applying a diff, editing a file, executing a command,
  committing, pushing, opening a PR, and sending source contents to a model all
  still require their own explicit authorization.)*

## 23. Phase 5E3 — deterministic diff proposal generator (DONE)

Phase 5E2 typed the diff proposal artifact and shipped no producer. Phase 5E3 is
that producer, and it is deliberately the dullest one that could exist:
`build_deterministic_diff_proposal`, a **pure function over four already-loaded
objects** that runs `difflib` over strings and returns a validated
`DiffProposalArtifact`, plus the `generate-diff-proposal` command that loads
those four objects from local files and prints the result.

The four inputs are the whole story, and **none of them is a workspace**:

1. an `ApprovedL1PlanArtifact` — the human approval and the path scope;
2. a `ProjectConfig` — the identity the approval must match;
3. a **Phase 5D2 workspace-content packet** — JSON a human previously printed
   with `l2-read-workspace-files`, carrying bounded, redacted original file text
   as *data*;
4. a **proposed-content input** (`proposed-content.v1`, mode `proposal-only`) —
   the final text a human or an external tool wants each file to have.

### 23.1 What it does, and the four things it deliberately cannot do

It generates diff text and **does nothing with it**. In particular:

- **It does not read target workspace files.** Original text arrives inside the
  packet or the generation for that path fails. The paths the approved plan
  names are never opened, stat'd, listed, globbed, walked, or resolved, and no
  path is joined to a workspace root or canonicalized.
- **It does not apply a diff, and it does not check whether one applies.** No
  patch tooling is invoked and nothing is staged. `applies_cleanly_checked` is
  `false` because the question was never asked — asking it means touching the
  workspace this phase refuses to touch.
- **It does not edit files, run commands, or call a model.** `httpx`,
  `requests`, `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `Path`, `os`, `socket` and `subprocess` are absent
  from the generator module's globals, so no code path there can reach one.
  `required_verification` is plan prose that is never executed.
- **It does not write an artifact file.** stdout only, with no wrapper, so the
  output parses with `parse_diff_proposal_artifact`. Nothing stamps an approval:
  the wrapped `ApprovedL1PlanArtifact` travels through unchanged.

`generated_at` is `None` and every assumption and risk is fixed prose, so the
same inputs always produce a byte-identical artifact. Provenance is
`engine="deterministic"`, `real_call=false`, `model=null` — facts about the
function, not claims copied from an input — and `patch_proposal` is always
`null`: these diffs were drafted from a content packet, not from a Phase 5E0
prose proposal.

### 23.2 Where it fails closed

Scope narrows and never widens: every proposed path must appear **exactly** in
`files_likely_to_change`, must **not** appear in `files_forbidden_or_out_of_scope`
(checked first, so a self-contradicting plan resolves restrictively), and must
appear in the packet. Identity is matched with exact string equality against
both the project config and the packet — `project_id`, `repo`, `issue_number`,
`title` — and the L1 invariants are re-checked rather than assumed.

The interesting refusals are the ones about *source text*:

- **Redacted source is refused.** Phase 5D2 replaces secret-like values with a
  placeholder, so a diff built from redacted text describes a file that does not
  exist. A misleading patch is worse than no patch.
- **A `modify` whose packet item is not a successfully read regular file** —
  missing, a directory, too large, skipped by the total cap, binary — is refused
  rather than guessed at, and so is a read item carrying no `content_text`.
- **A `create` whose path was actually read is refused**: this phase does not
  overwrite an existing file under the name "create". A `create` with empty
  content is refused too, because no hunk can express it and silently dropping
  it would misreport the proposal.
- **A generated diff matching a secret-like pattern is refused, not redacted.**
  The Phase 5D2 regexes are reused **detection-only**: redacting a diff would
  produce text that reads like a patch and could never apply. The error names
  the category and the path and never echoes the value or the diff.

A `modify` whose proposed text already matches the recorded original produces no
diff at all: the path goes into `omitted_paths` rather than being emitted as a
fabricated one. `changes` may therefore be **empty**, which is well-formed.
Because the artifact is validated through the Phase 5E2 model rather than
constructed field by field, a generated diff that would not parse — the awkward
case being a source line beginning `--` or `++`, which prefixes into something
that reads like a second file header — is discarded rather than emitted.

### 23.3 The command's gate ordering

`generate-diff-proposal` takes `--project-config`, `--approved-plan`,
`--workspace-content`, `--proposed-content`, the two consent flags
`--apply-approved-plan` and `--generate-diff`, and `--format`. It fails closed in
order: **both flags first** (without either, *nothing* is read, not even the
config), then the config, then a string/path check rejecting **any** of the
three inputs that sits inside the configured `repo.workspace_path` — checked for
all three together, **before any of them is opened**, which is why none carries a
Typer `exists=`/`readable=` check — then the strict Phase 5B parse, then the
packet, then the proposed content, then generation. Any failure exits non-zero
with stderr only and nothing on stdout, and never echoes the artifact text, the
plan prose, the proposed content, any file content, any diff text, or any
secret-like value.

### 23.4 Acceptance criteria for Phase 5E3 (DONE)

- [x] A valid `modify` and a valid `create` each generate a
  `DiffProposalArtifact`, and the generated artifact re-parses with
  `parse_diff_proposal_artifact`. Generation is byte-for-byte deterministic.
- [x] The wrapped `ApprovedL1PlanArtifact` travels through unchanged, and the
  input object is not mutated.
- [x] A no-op `modify` is reported in `omitted_paths`, never emitted as a
  fabricated diff; an empty proposed-content input yields `changes == []`;
  multiple changes preserve the input's order.
- [x] Duplicate proposed paths, paths outside `files_likely_to_change`, paths in
  `files_forbidden_or_out_of_scope`, and paths absent from the packet are all
  rejected. Plan prose is never read as a path.
- [x] A `modify` requires a packet item with status `read`, kind `file`, a
  non-null `content_text` and `redacted == false`; **a redacted source fails
  closed**. A `create` requires status `missing`, and a `create` over a read
  item fails closed. `too_large`, `binary_or_non_utf8`, `directory_no_content`,
  `other_no_content` and `skipped_total_limit` items cannot be changed.
- [x] Identity mismatches fail on `project_id`, `repo`, `issue_number` and
  `title`, against both the config and the packet, by exact string equality, and
  the message names the field without echoing the values.
- [x] Provenance is `deterministic` / `diff-proposal` / `real_call=false` /
  `model=null` / `generated_at=null`; `source_contents_read` reflects whether
  recorded original content was consulted; `diffs_generated` is true and
  `files_edited`, `commands_run` and `applies_cleanly_checked` are false.
- [x] **No apply-cleanliness check is performed**, with `builtins.open`,
  `subprocess` and the `os` filesystem entry points detonated across a
  successful generation.
- [x] A secret-like generated diff fails closed and the message never echoes the
  value or the diff.
- [x] Both input parsers reject empty text, invalid JSON, markdown fences, prose
  around the object, and non-object JSON; the proposed-content models reject
  unsafe paths, duplicates, oversized or NUL-bearing content, and every
  forbidden extra (`unified_diff`, `diff`, `command`, `apply`, `workspace_path`,
  `before_content`/`after_content`, `approval`, `prompt`, `completion`,
  `api_key`, `base_url`, `command_output`); the packet parser rejects a wrong
  `mode` or `candidate_source`, a broken identity, duplicates, unknown item
  statuses, unsafe item paths, and unexpected item fields.
- [x] **The generator performs no IO**: no file, environment, network, or
  process access on the success path or on any failure path, and no file is
  written. The plan's paths are never opened.
- [x] The command reads **exactly the four files named on its command line**, in
  order, and fails before reading anything when a flag is missing, before
  reading any input when one of the three sits inside the workspace, and before
  reading the next input when an earlier one is invalid.
- [x] stdout is the artifact with no wrapper and carries no `workspace_path`, no
  absolute path, no raw input text, no API key or base URL, no command output,
  and no apply result; source text appears only as diff context inside the
  generated diffs, and `approval_text` only inside the embedded plan snapshot.
- [x] **No CLI behavior changed except the added command.**
  `l2-read-workspace-files`, `generate-patch-proposal`, `l2-inspect-workspace`,
  `l2-dry-run`, `generate-plan` and `generate-model-plan` keep their exact
  options, and none gains `--generate-diff` or `--proposed-content`.
- [x] **Tests use pytest `tmp_path` and literal JSON only** — no real
  environment, no network, no target workspace read, and no real `C:\dev` path.
- [x] **Phase 5F and every later sub-phase in §13 remain proposed and not
  authorized. Phase 5F is the first phase that could edit a file.** Applying a
  diff, editing a file, executing a command, committing, pushing, opening a PR,
  and sending source contents to a model all still require their own explicit
  authorization. *(Phase 5F0 — typing the human approval a write would have to
  pass — has since been implemented as **models and a parser only**; see §24.
  Nothing edits a file.)*

## 24. Phase 5F0 — file-edit write gate models and parser (DONE)

Phase 5E3 produces a concrete `DiffProposalArtifact` deterministically and
offline, and prints it. Nobody has read it. Phase 5F0 types the **explicit human
approval** that any future file-editing phase would have to be handed before it
could write a single byte into a target workspace — and ships nothing that
writes.

**Phase 5F0 is file-edit write gate models and a strict parser only.** It is
**not** file editing, **not** diff application, **not** apply-cleanliness
checking, **not** command execution, **not** model-backed L2, and **not** L2. It
is a library: `src/ai_dev_orchestrator/file_editing/`, wired into no command.

### 24.1 Why a second approval exists

Phase 5B's `REQUIRED_APPROVAL_TEXT` records that a human approved an **L1 plan**
for L2 implementation. That is an approval of *intent* — a summary, a scope, a
list of files that may change. It is not an approval of the **concrete diff**
Phase 5E3 later generated from that plan, which the human had not seen when they
approved the plan.

So Phase 5F0 introduces a second, differently worded sentence:

```
REQUIRED_DIFF_EDIT_APPROVAL_TEXT = "I approve this diff proposal for workspace file editing"
```

It is compared with `==`. A paraphrase, a case variant, padded whitespace,
trailing punctuation, and the Phase 5B plan sentence are all **not** approval.

The orchestrator must never infer this approval from:

- the approved L1 plan artifact wrapped inside the proposal — a different
  approval of a different thing, re-validated here and never reused;
- the diff proposal artifact existing, parsing, or setting
  `requires_human_review`, which *requests* review and never records that it
  happened;
- a file being present on disk;
- issue prose or an `Automation Authorization` heading, which anyone who can
  edit an issue can write;
- model output of any kind.

Nothing in this phase stamps an approval. Writing the block **is** the approval
act, and it is a human's.

### 24.2 What the artifact carries, and what it refuses to carry

`ApprovedDiffProposalArtifact` is `schema_version`
(`"approved-diff-proposal.v1"`), `mode` (`"file-edit-approval-only"`),
`approval` (a `DiffEditApproval`), `diff_proposal` (an **untouched** Phase 5E2
snapshot), `project_id`, `repo`, `issue_number`, `title`, and
`next_authorization_required`. Every model is `extra="forbid"`.

Identity is matched **exactly**, in both directions — against
`diff_proposal.provenance` and against `diff_proposal.approved_plan` (whose
title lives on `.plan.title`). String equality only; no normalization, no case
folding. The failure this prevents is an approval given for one issue being
carried into another.

Every invariant the proposal already guarantees is **re-checked here**: the plan
is still `automation_level == "L1"` with `requires_human_approval` true; the
proposal still has `requires_human_review` true and `diffs_generated` true, with
`files_edited`, `commands_run` and `applies_cleanly_checked` all false; no
duplicate `changes[].path`; every path exactly inside `files_likely_to_change`
and none inside `files_forbidden_or_out_of_scope`. A write gate must not inherit
its safety from a model it does not own, and pydantic does not re-validate a
model instance it is handed — so an object mutated or hand-built after
validation reaches the gate, and the gate checks it again. An optional wrapped
patch proposal keeps Phase 5E2's consistency rules unchanged and unloosened.

`diff_proposal.changes` may be **empty**: a human may approve a proposal that
proposes nothing, in which case a future apply phase would have nothing to edit.
That is well-formed, and it authorizes no write.

There is **no field** for raw artifact text, source contents outside a diff,
`before_content`/`after_content`, a prompt, a completion, an API key, a base
URL, a workspace path, a command or its output, an apply result, `auto_apply`, a
branch name, a commit id, or a PR URL. Each is rejected as an extra. Source text
appears only as diff context inside the wrapped diffs.

**This model does not prove a diff applies** — `applies_cleanly_checked` must
still be false, because nobody asked. It does not authorize command execution,
and it does not authorize commits, pushes, or PRs. It records a human approval
that a future, separately authorized file-editing phase may consider, and no
such phase exists.

### 24.3 Acceptance criteria for Phase 5F0 (DONE)

- [x] A valid artifact parses into `ApprovedDiffProposalArtifact`, carries a
  `DiffEditApproval`, and carries the wrapped `DiffProposalArtifact` snapshot
  unchanged. It may wrap a `modify` diff, a `create` diff, or empty changes.
  Surrounding whitespace is accepted; the three constants are the exact strings
  above; the three error types share one base.
- [x] The approval block is required; `approved_by` must be non-blank,
  `approved_at` parseable, `source` `"manual"` only, and `approval_text` an
  exact match. Lowercase variants, a trailing period, padded whitespace,
  paraphrases, `"I approve this L1 plan for L2 implementation"` and
  `"Automation Authorization: approved"` are all rejected, as are missing
  fields, extra fields, and `model`/`automatic`/`github`/`issue` sources.
- [x] **Approval is never inferred** — not from the wrapped L1 plan approval
  (which is valid and approves something else), not from
  `diff_proposal.requires_human_review`, and not from a file being present.
  There is no loader, no writer, and nothing that stamps an approval.
- [x] Wrapper `project_id`/`repo`/`issue_number`/`title` must match the
  proposal's provenance **and** its nested approved plan exactly; case
  differences are rejected. `repo` must look like `owner/repo`, `issue_number`
  must be positive, and `project_id`, `title` and `next_authorization_required`
  must be non-blank. `schema_version` and `mode` are exact.
- [x] `diff_proposal` is required, a malformed one is rejected through nested
  validation, and every proposal invariant is re-checked — through JSON **and**
  on a mutated object handed in directly: the flags, the L1 level and human
  approval requirement, duplicate paths, out-of-scope paths, and forbidden
  paths. A positive control proves the direct-construction path itself works.
- [x] Every forbidden artifact-level extra is rejected (`raw_artifact_text`,
  `source_contents`, `file_contents`, `before_content`/`after_content`,
  `command`/`commands`/`command_output`, `prompt`, `completion`, `api_key`,
  `base_url`, `workspace_path`, `apply`/`auto_apply`, `branch`, `commit`,
  `push`, `pr_url`), as is every forbidden approval-level extra
  (`endpoint_host`, `base_url`, `api_key`, `prompt`, `completion`, `messages`,
  `raw_response`, `workspace_path`). No apply/edit/command/git field exists on
  either model, and error messages never echo the diff, the approval text, or a
  secret-like value.
- [x] The parser accepts surrounding whitespace and rejects empty text, invalid
  JSON, markdown fences, prose before or after the object, non-object JSON, and
  non-string input. It wraps `ValidationError`, never repairs, never strips
  unknown fields, never infers missing ones, prints nothing, and is
  deterministic.
- [x] **The parser performs no IO** — no file, environment, network, or process
  access on the success path or on any failure path, and no file is written. The
  implementation module's globals contain none of `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `Path`, `os`, `socket`, `subprocess`, `difflib`.
- [x] The package exports exactly the nine Phase 5F0 names and no editor,
  applier, loader, writer, runner, or git helper.
- [x] **No CLI behavior added.** Root help still lists exactly the eleven Phase
  5E3 commands; importing `file_editing` adds none; `generate-diff-proposal`,
  `l2-read-workspace-files`, `generate-patch-proposal`, `l2-inspect-workspace`,
  `l2-dry-run`, `generate-plan` and `generate-model-plan` keep their exact
  options and none gains an approve/apply/edit flag. No workspace access, no
  GitHub fetch or write, no command execution, no file editing, no branch,
  commit, push or PR, no agent logic, no implementer/reviewer/fixer role wiring,
  no artifact writing, and no approval stamping.
- [x] **Tests use literal dicts and JSON only** — no real environment, no
  network, no target workspace read, and no real `C:\dev` path.
- [x] **Phase 5F1 and every later sub-phase in §13 remain proposed and not
  authorized.** Phase 5F1 may add a separately gated **dry-run apply plan**, but
  **not file editing** unless explicitly authorized. Applying a diff, editing a
  file, executing a command, committing, pushing, opening a PR, and sending
  source contents to a model all still require their own explicit authorization.
