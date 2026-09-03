# AIDO Roadmap — autonomous execution control plane, runtime qualification, and v1 sequencing

> **ROADMAP / ARCHITECTURE DOCUMENTATION ONLY.**
>
> This document authorizes nothing to execute. It creates no module, no config
> field, no CLI command, no harness abstraction, no database, no schema, no
> migration, and no qualification run. **No semantic prompt was sent, no
> candidate was run, no Pi/Node process was launched, no credential was read, no
> socket was opened, and B300 was not contacted** in the turns that wrote it. No
> qualification runtime code was modified, `CLAUDE.md` was not modified, and no
> frozen historical design document was rewritten.
>
> **Standing authority is unchanged by this document.**
> `5F3B-Q1: NO-GO. 5F3B-Q2: NO-GO. Real-workspace authority: NO-GO.`

| | |
|---|---|
| Kind | Roadmap / architecture documentation |
| Created | 2026-09-02 (post `5F3B-Q1-PRE1` ACCEPT / FREEZE) |
| Revised | 2026-09-02 — architecture alignment review against the autonomous-project-execution product vision |
| Live activity | **None** |
| Authorizes | **Nothing** |

## 0. Why this document exists, and what it is canonical for

AIDO is about to attempt its first **live semantic implementer qualification**
(5F3B-Q1 / Q2). Before that happens, the project needs one explicit statement of
what a qualification result will actually mean, what it will and will not
authorize, and where a second harness fits later. Writing that *after* a first
result exists would let the architecture be retrofitted to whatever AIDO
happened to observe — the same failure mode
[`PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md`](PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md)
§2 avoids by freezing the qualification policy before any candidate runs.

The **2026-09-02 revision** widened the document for a second reason. The
original text was accurate about the runtime-harness layer, but it sequenced the
project as though harness plurality were the next large problem after a first
qualified implementer. It is not. The durable product is an **autonomous
engineering control plane**, and the control plane — project contract authority,
execution planning, persistent step state, deterministic transitions — does not
exist yet, while harness plurality is an optimization on top of it. §9 states the
comparison; §4 states the corrected order.

### 0.1 The architectural verdict this document is built on

```text
AIDO IS:
    an autonomous engineering control plane / project execution orchestrator

AIDO IS NOT:
    another coding harness
    a generic multi-agent framework
    a Pi wrapper
    a Codex wrapper
```

Worker harnesses and models are **replaceable beneath AIDO**. What AIDO durably
owns — the part that is worth building and that no harness supplies — is:

```text
project-plan interpretation        capability boundaries
execution planning                 deterministic evidence
persistent project/step state      policy enforcement
step contracts                     retry / re-plan / escalation
role orchestration                 completion authorization
runtime qualification              audit trail
```

Everything already shipped or frozen in this repository that supports that list
is an **asset to extend, not a stage to pass through**. Nothing in this
document's revision replaces, deprecates, re-opens, or genericizes accepted
work.

### 0.2 Canonical scope

This document is canonical for two layers.

**Runtime / qualification layer:**

- **the four independent runtime axes** (§1);
- **the qualification identity tuple** (§2);
- **Pi's architectural status** (§3);
- **milestone sequencing M1–M11 and the inserted control-plane tranche** (§4);
- **the Codex / DeepSeek Harness position** (§5);
- **the AIDO v1 / v2 product milestones** (§6);
- **deferred progress-aware stall supervision** (§7).

**Control-plane architecture layer (added by the 2026-09-02 revision):**

- **the architecture comparison** — exists / extend / missing / defer (§9);
- **the formal authority layers** (§10);
- **Planner authority and the PlannerDecision vocabulary** (§11);
- **persistent ProjectRun / StepRun state** (§12) and its preferred
  implementation direction (§13);
- **the Step Contract** (§14);
- **the deterministic transition engine** (§15);
- **the two nested execution loops** (§16);
- **Test Authority** (§17) and the deferred independent **Tester** (§18);
- **reviewer evolution, claim audit and defect routing** (§19);
- **the project integration gate** (§20);
- **incident-to-qualification conversion** (§21);
- **risk-based workflow policy** (§22);
- **the minimum vertical slice** (§23).

It is **not** canonical for, and does not restate or supersede:

| Layer | Canonical document |
|---|---|
| Production capability phase list (Phases 0–10, 5F2x) | [`AI_DEV_ORCHESTRATOR_PLAN.md`](AI_DEV_ORCHESTRATOR_PLAN.md) §7 |
| Shipped L2 writer / verifier / reviewer contracts | [`PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md`](PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md) |
| Implementer qualification policy, corpus, hard bar | [`PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md`](PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md) |
| Semantic dispatch authority + evidence contract | [`PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md`](PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md) |
| Route / credential boundary | [`PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md`](PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md) |
| Pi runtime boundary / delegated authority | `PHASE_5F3A_AR0_*`, `PHASE_5F3A_AR2D_*` |

Those documents stay **historical, frozen, and Pi-specific**. This one does not
edit them to make their terminology retroactively generic, and no reader should
treat a generic term here as evidence that a frozen document meant it
generically.

---

## 1. The four independent axes

AIDO must model four axes that conversation has tended to conflate:

```text
ROLE      what job is being performed          implementer | reviewer | planner | tester (future)
HARNESS   the runtime executing that role      Pi | AIDO's own model client | (future) Codex | (watch-list) DeepSeek Harness
MODEL     the weights answering the prompts    qwen3-coder-next | minimax-m2.7 | ...
BACKEND   how those weights are served         B300 via LiteLLM proxy | direct vLLM | ...
```

One **runtime combination** is a point in that space, and it is the smallest
thing AIDO may qualify:

```text
implementer  ×  Pi  ×  qwen3-coder-next  ×  B300/LiteLLM route
```

### 1.0 HARNESS means "the runtime layer for that role", not "a coding agent"

The HARNESS axis is the execution layer through which a role is performed. For
an implementer that is a coding harness (Pi today). For a **reviewer** it is
already something else: the shipped 5F2E controlled reviewer runs through
**AIDO's own `LLMClient`**, over LiteLLM or direct vLLM, with no coding harness
anywhere. Both are values of the same axis.

This matters for sequencing. A role can reach production through an
AIDO-controlled model client without any harness work at all, so a *harness*
milestone is never automatically a prerequisite for a *role* milestone.

### 1.1 Why the axes are independent

Each axis can change while the other three are held constant, and each such
change can independently invalidate an observed result:

- **ROLE.** AIDO already holds its own proof that role does not transfer.
  `experiments/b300_reviewer_benchmark/` recorded a seeded reviewer **false
  negative** from `qwen3-coder-next` — it approved a change containing a seeded
  correctness regression. That is reviewer evidence about a model that is
  simultaneously the leading *implementer* candidate. Neither result predicts
  the other, in either direction
  ([qualification design §4.1](PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md)).
- **HARNESS.** The harness owns the agent loop, the tool schemas, the prompt
  contributions, the stopping behavior and the dispatch seam. AIDO's implementer
  tool surface (`aido_read`, `aido_edit`) and its budget constants are expressed
  *through* the harness. A model that stops cleanly under one agent loop is not
  thereby known to stop cleanly under another.
- **MODEL.** Self-evident, and the variable 5F3B exists to test — AR1/AR2/O1
  deliberately held it constant so that the broker and the runtime seam were the
  only architecture variables.
- **BACKEND.** Already frozen policy: *the same model name over a different
  route, gateway, quantization, or deployment is not automatically equivalent
  evidence*
  ([qualification design §15](PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md)).

### 1.2 The rule this produces

> **Do not model a model as globally qualified.**
> `qwen3-coder-next` is never "qualified". At most,
> `implementer × Pi × qwen3-coder-next × B300/LiteLLM` is qualified, under a
> named qualification policy revision, on AIDO-observed evidence.

Every future selection surface, record, artifact and human-facing statement must
name the combination, not the model. A sentence of the form "AIDO qualified
model X" is a defect in this project's vocabulary regardless of what motivates
it.

---

## 2. The qualification identity tuple

The long-term qualification identity is approximately:

```text
(
    role,
    harness,
    harness_version,
    model,
    backend,
    qualification_policy_revision
)
```

**`role` is an identity term, not merely a lookup key.** An earlier revision of
this document left role outside the tuple on the grounds that role selects
*which policy applies*. That is true and stays true — a reviewer qualification
and an implementer qualification are different policies, not two values of one
field — but it is not a reason to omit role from the identity. A record that
does not name its role can only be read later by inferring the role from the
policy revision, and inference is exactly what an identity exists to remove. So
role appears **both** in the identity and as the selector of the applicable
policy.

The qualification design's existing provenance rule —
`model × harness × route/deployment × qualification policy` — is the same idea;
this tuple makes three of its terms explicit rather than implied. **That frozen
section is not edited.**

### 2.1 Why `harness_version` is an identity term, not a model property

Because AIDO's correctness arguments are derived from a specific harness
version's observable seam, not from the harness as an abstraction.

The concrete instance: `5F3B-Q1-PRE1-DESIGN-FU1` established AIDO's two-phase
semantic dispatch contract — `CONFIRMED_NOT_SENT | CONFIRMED_SENT |
SEND_STATE_INDETERMINATE`, and the rule that `semantic_prompts_sent` is fixed at
phase 1 and can never be rewritten by a phase-2 outcome — by reading the
**locally installed Pi `0.84.4`** RPC seam: `rpc-mode.js`, `jsonl.js`,
`agent-session.js`, `agent-loop.js`. The load-bearing fact is that Pi emits a
correlated `prompt` response **strictly before** `agent_start` and before any
inference. That ordering is a property of a version of a program, not of the
model and not of the backend.

A harness upgrade can therefore invalidate the *mechanical basis* of an accepted
qualification while model, backend and policy are all unchanged. So the version
belongs in the identity, and:

- a qualification record must state the observed harness version;
- a harness version change does **not** silently carry a PASS forward;
- whether a given change requires full re-qualification, a narrower
  compatibility re-check, or nothing at all is a **separate, explicitly
  authorized decision per change**. This document pre-authorizes none of the
  three and deliberately defines no semver range, no compatibility matrix, and
  no auto-revalidation rule.

### 2.2 Why `qualification_policy_revision` is an identity term

Because "PASS" has no meaning independent of the bar that produced it. AIDO's
implementer PASS is defined by a specific corpus (IQ-1/2/3), a specific hard bar
(H-1 … H-14), a specific outcome taxonomy, a specific one-shot prompt policy,
and specific prompt-fairness rules. Change any of those and the token `PASS`
denotes a different claim.

Consequences, stated so they cannot be quietly violated later:

- two candidates are comparable **only** under the same policy revision;
- an old record is **never re-scored** under a new policy, and a new policy
  never retroactively converts an old FAIL into a PASS or the reverse;
- the policy revision is recorded **with** the result, not in a changelog beside
  it, so a record stays self-describing after the policy moves on.

### 2.3 Two kinds of qualification, and neither implies the other

```text
RUNTIME_COMPATIBILITY qualification      harness × model × backend
      Can AIDO launch it, handshake it, drive it, observe it, and clean up?

ROLE_CAPABILITY qualification            role × harness × model × backend
      Is it good enough AT THAT JOB, under a named policy, on AIDO's evidence?
```

Where the current work sits:

- **Category-B live compatibility** (Candidate A, Candidate B — frozen) is
  **`RUNTIME_COMPATIBILITY` qualification**. It is a statement about the route
  and the runtime seam. It is never implementation quality, and no Category-B
  result is ever a candidate PASS. ("Category-B" is the historical term for
  *this specific compatibility check*; `RUNTIME_COMPATIBILITY` is this
  document's name for the *kind* of qualification it belongs to — the two are
  not renaming each other, and neither is changed by the other existing.)
- **Q1 / Q2** are **`ROLE_CAPABILITY` qualification, for the IMPLEMENTER role
  only.**

A successful IMPLEMENTER qualification does **not** imply TESTER, REVIEWER or
PLANNER qualification, and AIDO already owns direct evidence that role capability
does not transfer (§1.1). A model may be genuinely strong in one role and weak in
another. Every future role gets its own `ROLE_CAPABILITY` qualification, under
its own policy revision, with its own corpus (§21).

### 2.4 What this tuple is not

It is not a config schema, a registry key, a database identity, a
`RuntimeCombination` dataclass, or an input to a selection algorithm. **Nothing
in this document may be implemented as a type.** It is the vocabulary that
future phases must use when one of them is separately authorized to build a
record or a selection.

---

## 3. Pi's architectural status — frozen statement

```text
Pi is AIDO's FIRST implementer harness to undergo formal qualification.
Pi is NOT a permanent architectural dependency of AIDO.
```

That is the architectural position and it is frozen as the project's intent.
The wording is deliberately **"undergo formal qualification"**, not "formally
qualified": the former is true today and does not contradict §3's accuracy
requirement below; the latter would be an accepted-PASS claim this document
has no evidence for. **No wording anywhere in this document may say Pi
"is a qualified harness" or "is formally qualified" before a Q1/Q2 PASS
exists.**

One accuracy note, because this document must not overstate status: **no
implementer qualification result exists today.** Pi is the harness AIDO is
qualifying first; it *becomes* AIDO's first formally qualified implementer
harness — and only then may that stronger phrase be used — if and only if a
live Q1/Q2 sweep produces a PASS under the frozen policy. Candidate A and
Candidate B are **Category-B compatibility** qualified/frozen only
(`RUNTIME_COMPATIBILITY` in §2.3's vocabulary), which is a statement about the
route and the runtime seam, never about implementation quality. Until a PASS
exists, the accurate present-tense form is: *"Pi is AIDO's first implementer
harness candidate, undergoing formal qualification, and its qualification is
the sequencing dependency for everything in §4."*

The second line is unconditional and applies now: Pi is a **replaceable
component**, not part of AIDO's architecture. AIDO is the control plane; the
harness is a supervised external runtime that nominates operations AIDO
authorizes. Nothing in AIDO's authority model, evidence model, or workspace
boundary may come to depend on Pi being the harness.

### 3.1 Current 5F3B Q1/Q2 remain explicitly Pi-specific

Q1 and Q2 qualify **Pi**. They are not a generic harness qualification, and no
result from them may be described as qualifying "a coding agent", "an agent
runtime", or "the implementer harness layer".

### 3.2 Do not genericize before the evidence exists

**PRE1, Q1 and Q2 must not be refactored into a generic harness framework**, and
the current Pi implementation stays frozen and concrete through the live
qualification. This restates the qualification design's accepted deferral (*a
generic `AgentRuntime` abstraction stays deferred until evidence from a second
runtime makes its common boundary concrete*) as a sequencing rule; it does not
re-argue it.

The reason is specific rather than stylistic: an abstraction extracted from one
implementation encodes that implementation's accidents as though they were the
contract. AIDO already knows that some of Pi's seam facts are
**version-specific** (§2.1) and some are **Pi-specific** (the RPC framing, the
acknowledgement ordering, the event union). A contract extracted today could not
distinguish those from the genuinely common boundary, and the first real second
harness would then either be forced through Pi's shape or would silently
invalidate the abstraction.

**Only after real Pi Q1/Q2 completion** should AIDO extract the minimum generic
harness contract, and it must be extracted **from observed, working semantic
behavior** — what the seam actually had to provide for a real qualification to
run — never from a design exercise. That extraction is **M7**, and it is
separately authorized work.

The 2026-09-02 revision adds a second reason to hold M7 back: the control-plane
tranche (§4.1a) will itself change what a harness must provide, because a Step
Contract and a deterministic transition validator define the seam's obligations
from above. Extracting the contract before that exists would encode not only
Pi's accidents but also the *absence* of the control plane.

---

## 4. Milestone sequencing

The 2026-09-02 revision **preserves M1–M11 and their meanings** so existing
records and cross-references stay valid, and inserts the control-plane tranche
as lettered sub-milestones. Nothing was renumbered.

```text
M1    Runtime compatibility                            COMPLETE
        Pi + Qwen / Pi + MiniMax
M2    Semantic qualification infrastructure            COMPLETE / FROZEN
        5F3B-Q1-PRE1
M3    Pi semantic implementer qualification            NOT AUTHORIZED (Q1/Q2 NO-GO)
        Q1 Candidate A
        Q2 Candidate B
M4    Select first qualified implementer runtime combination

        --- control-plane tranche (inserted 2026-09-02, FU1-reordered) ---
M5A   PROJECT / STEP CONTROL PLANE FOUNDATION
        Project Contract, Execution Plan, Step Contract,
        ProjectRun / StepRun, persistent state, recovery,
        deterministic transition validator, PlannerDecision
M5    Authorize narrow real-workspace implementer operation
        (its authority contract is bound to the M5A model — §4.0)
M6    NARROW SINGLE-STEP REAL-WORKSPACE PILOT              <-- AIDO v1
        the §23 minimum vertical slice, on one real project
M6A   TEST AUTHORITY
M6B   INDEPENDENT TESTER + STRUCTURED REVIEW ROUTING
M6C   MULTI-STEP OUTER LOOP + PROJECT INTEGRATION GATE
        --- end control-plane tranche ---

M7    Extract minimal harness contract from actual Pi experience
M8    Integrate and separately qualify Codex as the next harness candidate
M9    DeepSeek Harness — only when sufficiently mature/stable
M10   Dynamic harness/model/backend routing
M11   Advanced progress-aware stall supervision
```

### 4.0 The corrected dependency order, stated explicitly

> **FU1 correction.** The original revision let M5 and M5A join only at M6,
> which would have allowed real-workspace implementer authority to be frozen
> independently of the control-plane authority model it must actually run
> inside. That is now tightened: M5 **consumes** M5A's accepted authority model
> rather than merely preceding M6 alongside it.

```text
M3 ──► M4 ──► M5A ──► M5 ──► M6 ──► M6A ──► M6B ──► M6C ──► M7 ──► M8 ──► M9 ──► M10

M5A depends on:  nothing live. It is offline control-plane work and MAY BE
                 DESIGNED while M3/M4/Q1/Q2 are still pending or unauthorized —
                 design work starting early is fine and does not violate this
                 graph.
M5  depends on:  M4 (a qualified combination) AND M5A's ACCEPTED authority
                 model (Project Contract / Step Contract / StepRun / transition
                 validator shapes). M5 may not freeze its real-workspace
                 authority contract independently of that model — real-workspace
                 write authority is exactly the kind of decision §10's formal
                 authority layers exist to bound, so it must be expressed in
                 those terms from the start, not bolted on afterward.
M6  depends on:  M5 (real-workspace authority, now M5A-shaped) alone; M4 and
                 M5A are already satisfied transitively through M5.
M11 depends on:  real traces from M6+, and is independent of M7–M10.
```

Three consequences worth stating so they cannot drift:

1. **M5A may be *designed* early, but M5 may not be *frozen* early.** Starting
   M5A's design while M3/Q1/Q2 are still NO-GO is fine and encouraged — it is
   offline. What is not permitted is authorizing or freezing M5's real-workspace
   authority contract before M5A's model is accepted, even if M4 has already
   produced a qualified combination.
2. **M5A is not blocked by Q1/Q2.** The control-plane foundation needs no model,
   no harness and no live activity. It is, however, *not authorized here* — it
   needs its own prompt like everything else, same as M5.
3. **The harness-plurality tranche (M7–M10) now sits after the entire
   control-plane tranche.** That is the substantive reordering the original
   revision made, and §4.3 gives the reason.

### 4.1 Milestone notes (M1–M6)

- **M1 — runtime compatibility. COMPLETE.** Category-B live compatibility
  attempts established that Pi can be launched, handshaked and driven over the
  qualification route for both first-round candidates. **Compatibility is not
  implementation quality**, and no Category-B result is ever a candidate PASS.
  It is `RUNTIME_COMPATIBILITY` qualification in §2.3's terms.
- **M2 — semantic qualification infrastructure. COMPLETE / FROZEN.** See §8.
- **M3 — Pi semantic implementer qualification.** The first live semantic
  activity in this line of work, and **the immediate next implementation work
  after this roadmap review** (§4.4). Q1 and Q2 are independent, neither is
  informed by the other, and each remains **NO-GO until separately authorized**.
  Under the frozen one-shot policy each candidate has exactly one authorized
  prompt per task, and an indeterminate dispatch **consumes** it.
- **M4 — select the first qualified combination.** A §2 tuple, chosen under the
  frozen selection policy from AIDO-observed evidence only; external prior
  evidence orders *which candidates are tested first* and contributes nothing to
  a verdict. M4 may legitimately conclude that **no** candidate qualified — that
  is a valid outcome, not a blocked one, and it must never be resolved by
  lowering the bar.
- **M5A — project/step control-plane foundation.** *(Sits before M5 — §4.0 FU1
  correction.)* The genuinely missing core: Project Contract authority (§10),
  the AIDO-mutable Execution Plan (§10), the Step Contract (§14), `ProjectRun` /
  `StepRun` with persistence and recovery (§12, §13), the deterministic
  transition validator (§15), and the `PlannerDecision` vocabulary (§11).
  Offline; no new model authority; extends existing abstractions rather than
  replacing them (§9). Its **design** may start alongside M3, but M5 may not
  freeze its authority contract until this milestone's model is **accepted**.
- **M5 — narrow real-workspace implementer authority.** A separate authority
  decision with its own opt-ins, gates and human approvals, on the pattern the
  shipped 5F2C/5F2D/5F2E capabilities already follow. **Synthetic qualification
  evidence never authorizes real-workspace operation** — the qualification
  design states this as a binding boundary, and M4 completing does not soften
  it. **M5's authority contract must be expressed in M5A's accepted terms**
  (§10's formal authority layers) — it is not authorized independently of them,
  because real-workspace write authority is exactly the kind of decision those
  layers exist to bound.
- **M6 — the narrow single-step real-workspace pilot.** One real project, one
  step, the §23 vertical slice end to end, human approval at every boundary the
  current L2 path already requires. This is the **AIDO v1** milestone (§6.1).

### 4.1a Milestone notes (the remaining control-plane tranche)

- **M6A — Test Authority.** The authority classification, provenance and
  baseline-mode model (§17). It must exist **before** any independent Tester
  runs, because without it a Tester's output is just more unattributed code.
- **M6B — independent Tester + structured review routing.** A Tester role with
  its own `ROLE_CAPABILITY` qualification (§2.3, §18), plus the reviewer's three
  semantic views, deterministic claim audit and defect routing (§19).
- **M6C — multi-step outer loop + project integration gate.** The outer loop of
  §16 and the project-level acceptance gate of §20. This is where "AIDO executes
  a project" first becomes literally true.

### 4.2 The binding sequencing rules

> **M7 and M8 are NOT prerequisites for AIDO v1.**

AIDO v1 is reached at **M6** (§6.1). Harness-contract extraction and a second
harness are later work. Nothing may be blocked, deferred, or re-scoped on the
grounds that the generic harness contract does not exist yet — §3.2 is precisely
the position that it should not exist yet.

> **The control-plane tranche is NOT gated on harness plurality either.**

That statement needs one distinction inside it, so it does not itself
contradict §4.0's ordering:

```text
M5A       requires NO qualified implementer combination.
            It is offline, depends on nothing live, and — if separately
            authorized — its design and construction may proceed before
            M4, in parallel with M3/Q1/Q2 (§4.0).

M5, M6,   require the M4-qualified implementer combination to do any real
M6A–M6C     execution against it — there is nothing to run a step with
            otherwise. M5 additionally consumes M5A's ACCEPTED authority
            model (§4.0); M6 onward inherit both.
```

So: **at most one harness is ever required** across the whole tranche — the
tranche never needed *plurality* — but M5 onward do require *one* qualified
combination to exist, while M5A alone does not.

### 4.3 Why M7–M10 moved after the control-plane tranche

The pre-revision ladder went from the first real-project pilot more or less
straight into harness-contract extraction, Codex, DSH and routing. That order
optimizes the wrong axis. Stated plainly:

- **A second harness multiplies capacity AIDO cannot yet direct.** Routing among
  harnesses is valuable only once there is an execution plan to route *work
  from*, persistent step state to route *against*, and a deterministic
  authorization path to route *into*. Without those, M8–M10 produce a more
  sophisticated way to run one-shot tasks.
- **The generic harness contract is defined from above, not from below.** What a
  harness must provide is determined by the Step Contract, the evidence
  contract, and the transition validator's inputs. Extracting the contract
  before those exist bakes in today's absence of a control plane (§3.2).
- **Single-harness autonomy is the credible v1 story.** "One qualified worker,
  driven by a control plane that can plan, persist, verify, review, recover and
  authorize completion" is a product. "Several harnesses, no control plane" is a
  benchmark rig.

This is a reordering of *emphasis and dependency*, not a cancellation. M7–M10
remain on the roadmap with their original meanings.

### 4.4 What remains the immediate next implementation work

```text
5F3B-Q1 (Candidate A) and 5F3B-Q2 (Candidate B) — M3 — remain the immediate
next implementation work, unchanged and unpostponed by this revision, and both
remain NO-GO until separately authorized.
```

Nothing in the control-plane architecture added here invalidates, delays,
re-scopes, or reprioritizes Q1/Q2. M5A may be designed in parallel; it does not
precede M3.

---

## 5. Codex and the DeepSeek Harness

### 5.1 Codex — likely second formal harness candidate (M8)

- Codex is recorded as the **likely** second formal harness candidate. It is not
  selected, not integrated, not designed, and not authorized here.
- It must receive its **own** harness + model + backend qualification, under the
  §2 identity, with its own compatibility evidence and its own semantic
  qualification runs.
- **A Pi qualification never automatically authorizes Codex with the same
  model.** `implementer × Pi × M × B` says nothing about
  `implementer × Codex × M × B` — that is exactly what §1.1's HARNESS axis
  means. The harness owns the agent loop, the tool seam and the stopping
  behavior, and those are among the properties an implementer qualification
  measures.
- Per §4.3, Codex integration now sits **after** the control-plane tranche.

### 5.2 DeepSeek Harness — experimental / watch-list (M9)

DSH stays on the watch list. The reason is an engineering assessment of current
maturity, not a verdict on the project:

- current maturity does not justify making it a v1 dependency;
- Windows behavior is not established for AIDO's environment;
- subagent overhead is a cost AIDO's bounded-supervision model would have to
  absorb;
- stability is not yet demonstrated at the level AIDO's evidence contracts
  assume.

DSH **may** become a later harness candidate if its runtime stabilizes. That
would be a separately authorized M9, under the same own-qualification
requirement as Codex.

### 5.3 Not authorized here

Neither integration is implemented, designed, prototyped, configured, or
scheduled by this document. No harness registry, no harness plugin interface, no
harness capability list, and no harness selection surface exists or is
authorized.

---

## 6. Product milestones

### 6.1 AIDO v1 — Controlled Autonomous Single-Step Execution

Reached at **M6**, which now requires M4 → M5A → M5 in that order (§4.0). The
pre-revision v1 definition — one qualified worker plus safe real-workspace
operation — was too thin to be the product described in §0.1: it would have
demonstrated a supervised one-shot edit, not a controlled autonomous execution
lifecycle. The corrected definition requires **at least**:

1. **one qualified implementer runtime combination** (§2), role-specific (§2.3);
2. **Project Contract authority** — a human-approved snapshot of product intent
   that the planner may not silently change (§10);
3. **persistent single-step state** — `ProjectRun` / `StepRun` persisted outside
   model context, surviving process exit and restart (§12);
4. **a Step Contract** binding objective, scope, invariants, baseline identity
   and verification authority for the one step (§14);
5. **deterministic transition authorization** — no state reaches COMPLETE
   because a model said so (§15);
6. **narrow, safe real-workspace authority** — narrow in the shipped sense: a
   bounded domain that fails closed outside it, never a general editor;
7. **AIDO-owned workspace / tool / credential boundaries** — the runtime
   nominates, AIDO authorizes, per operation, re-deciding from scratch; runtime
   claims are never repository authority;
8. **authoritative verification / evidence** — AIDO-owned, run after
   implementation, with AIDO's own observation authoritative over any
   runtime-reported or broker-recorded claim;
9. **controlled review where policy requires** — the shipped bounded reviewer
   path;
10. **one real-project end-to-end controlled pilot** (M6);
11. **human final authority** at every boundary policy requires.

> **AIDO v1 does NOT require:** multiple harnesses, a generic harness
> abstraction, multi-harness routing, an independent Tester, a multi-step outer
> loop, a project integration gate, a fixer, a review/fix loop, or automatic
> model selection. One qualified combination, driven by a real control plane
> over one step, is v1.

That boundary is chosen to be the **simplest honest one**: everything in the
list above is required for the sentence "AIDO autonomously executed a step and
authorized its completion" to be true, and nothing beyond it is.

### 6.1a Between v1 and v2 — M6A, M6B, M6C

Test Authority (M6A), the independent Tester with structured review routing
(M6B), and the multi-step outer loop with the project integration gate (M6C) are
staged **after v1 and before v2**. They are the difference between "AIDO can
execute a step" and "AIDO can execute a project", and they are deliberately not
folded into v1 — inflating v1 until it becomes unreachable is a worse error than
shipping a narrow v1.

Whether these are labelled `v1.1 / v1.2 / v1.3` or held as unnumbered tranche
work is not decided here.

### 6.2 AIDO v2 — Adaptive Orchestrator

Adds — none of it authorized here:

- multiple qualified harnesses;
- multiple models / backends;
- task-aware routing;
- historical-performance routing;
- availability- and resource-aware routing;
- progress / stall supervision (§7);
- fallback / handoff policy.

Every v2 item routes among **qualified combinations only**. Routing is never a
way to reach an unqualified combination, and a fallback is a second qualified
combination or it does not happen.

---

## 7. Deferred: advanced progress-aware stall supervision (M11)

**Recorded as a later roadmap item. It is not part of PRE1, Q1 or Q2, and must
not be invented in the current Pi Q1 implementation.**

### 7.0 The split this section now enforces

The pre-revision text grouped two different things under one heading. They are
separated because one is core correctness and the other is a heuristic needing
evidence AIDO does not have:

```text
EARLIER — M5A, core correctness (§12)
    persistence
    crash / restart recovery
    resumability
    reconstructing execution after AIDO, harness, model or verification failure

LATER — M11, heuristic supervision (this section)
    repeated semantic activity with no new files
    no new commands
    no new findings
    high semantic repetition
    a bounded STALLED outcome
```

Recovery is not a stall heuristic and must not wait for one. A crashed AIDO that
cannot say what step it was on is broken regardless of how good its stall
detection is.

### 7.1 What M11 would eventually supervise

AIDO should eventually supervise agent and reviewer *progress* using bounded,
observable telemetry:

- tool calls;
- files inspected;
- tests executed;
- new findings;
- repeated semantic patterns;
- time to first useful finding;
- actionable final output.

A future circuit breaker may detect the pattern

```text
repeated reasoning / semantic activity
  with no new files
  no new tools
  no new findings
  and high repetition
```

and produce a **bounded STALLED outcome**, with at most **one** explicitly
authorized compact retry or handoff.

### 7.2 The distinction that must survive into that phase

```text
AIDO wait ended
  != worker stopped
  != request cancelled
  != backend inference stopped
```

This is the accepted 5F2E-RS1-FU1/FU2 result and a progress-supervision phase
does not renegotiate it. A future circuit breaker may bound **AIDO's own wait
and AIDO's own issuance**; it may not claim to have stopped a worker, cancelled
a request, or ended backend inference, and it may not acquire that claim by
adding a thread kill, a socket close, a process group, or a cancellation call.

The same distinction constrains recovery in §12: after a crash AIDO may know
what it *had authorized*, and it may not assume that an in-flight worker,
request, or backend inference stopped when AIDO did.

### 7.3 Why it is deferred rather than designed now

Two concrete reasons:

1. **AIDO owns no evidence that would justify a threshold.** The qualification
   design records the numeric stall thresholds as an explicit open question
   precisely because inventing a number is worse than not having one. The first
   live traces are the input to that design.
2. **Today's supervision is deliberately narrower in kind.** What exists is
   *observable resource supervision*, not *agent-progress supervision*: response
   returned, typed client error, `finish_reason`, reported usage, empty or
   non-empty content, strict-parser acceptance. Extending it to progress
   telemetry introduces per-tool and per-file observation into a layer that
   currently makes no such claims — a change of kind, needing its own
   authorization rather than an incremental widening.

Nothing here authorizes reasoning inspection, chain-of-thought capture, or any
telemetry beyond what a future phase separately establishes as observable.

---

## 8. PRE1 status of record

```text
5F3B-Q1-PRE1:  ACCEPTED / FROZEN
```

Its final offline validation, as recorded at acceptance:

```text
pi_implementer_qualification   1751 passed
pi_external_runtime_ar1           96 passed
pi_external_runtime_ar2          298 passed
pi_external_runtime_ar2_o1        89 passed

root tests                      3503 passed
                                   1 known environment-specific failure
```

The root failure is:

```text
tests/test_writer_execution_isolation.py::
test_no_project_verification_command_runs_after_the_refactor
```

on a machine where Git resolves under `C:\Program Files\Git\cmd\git.exe`.

> **Do not call the root suite fully passing.** It is 3503 passed with one known
> environment-specific failure, and it must be reported that way wherever it is
> reported.

That test is **unrelated to the qualification package** and is deliberately
**not fixed here** — this is a roadmap document, and correcting it is separate
work under its own prompt. No revision of this document ran any test: the counts
above are transcribed from the acceptance record, not re-measured.

### 8.1 Standing authority after PRE1

```text
Q1                          NO-GO   (until separately authorized)
Q2                          NO-GO   (until separately authorized)
Real-workspace authority    NO-GO
```

**No semantic prompt has ever been sent. No candidate implementer PASS/FAIL
exists.** Candidate A and Candidate B are Category-B **compatibility**
qualified/frozen only. PRE1 acceptance authorizes the *infrastructure* for a
live semantic attempt; it does not authorize the attempt.

---

## 9. Architecture comparison — exists / extend / missing / defer

This section is the justification for everything in §10–§23. The control plane
is not being started from nothing: most of its *authority primitives* already
exist and were built to a higher standard than a greenfield version would be.
What is missing is almost entirely **statefulness and multi-step composition**.

### 9.1 ALREADY EXISTS — do not rebuild

| Control-plane concern | What already implements it |
|---|---|
| Human product approval, exact-text, non-forgeable | `PlanApproval` (`handoff/models.py`) — `approval_text` must match the required phrase exactly; a paraphrase is not approval |
| Approved-plan snapshot with identity binding | `ApprovedL1PlanArtifact` — plan carried as a snapshot, not a reference; exact project/repo/issue matching; forged nested fields rejected |
| A structured plan object a model may propose but not self-authorize | `L1Plan` — `automation_level` pinned to `"L1"`, `requires_human_approval` always `True` |
| Workspace boundary / path authority | `PathPolicy`, canonical path guard, allowed/protected/forbidden path rules |
| Bounded, gated write authority | 5F2C `l2-apply-approved-file-edit` — one file, exact diff, pre/post SHA-256 pinning, fails closed |
| Deterministic verification with AIDO-owned facts | 5F2D `l2-verify-approved-file-edit` — HEAD pinned, dirty state proven exactly, distinct exit codes for refused / did-not-pass / no-longer-provable |
| Immutable evidence artifacts with schema versions | `verification-result.v1`, `review-packet.v4`, `pi-implementer-qualification.v1` |
| Controlled reviewer with a strict, non-repairing parser | 5F2E + RS1/V1/V2 — one model, one advisory verdict, rejected-never-repaired output |
| Bounded request issuance and AIDO-owned wait deadlines | 5F2E-RS1 (+FU1/FU2) |
| One-shot attempt authority and send-state proof | PRE1 semantic dispatch — `CONFIRMED_NOT_SENT / CONFIRMED_SENT / SEND_STATE_INDETERMINATE`, `semantic_prompts_sent` fixed at phase 1 |
| Exactly-one-artifact-per-attempt rule | `pi-implementer-qualification.v1` / `-attempt.v1` — never zero, never both |
| Invariant gates at record construction | `qualification/records.py` — an internally impossible record is rejected, never coerced |
| Frozen task identity by content digest | `QualificationTask.task_revision` — `<task_id>@<digest>` over files, prompt, verification argv, protected patterns, expected changed paths and baseline contract |
| Structured baseline expectations as data | `BaselineContract` — `SEEDED_FAILURE` / `ALREADY_PASSING` with declared expected-failure patterns |
| Evidence lineage without mutation | `qualification/lineage.py` — a defect finding is new linked evidence, never an edit |
| Safe single-choke-point artifact emission | `qualification/safety.py` — `O_CREAT` \| `O_EXCL`, no overwrite possible |
| Delegated-authority runtime boundary | AR1 / AR2 / AR2-O1, I1 / I2 / I2B — the runtime nominates, AIDO authorizes |

### 9.2 EXTEND — evolve these, do not fork parallel versions

| Target concept | Existing ancestor to evolve |
|---|---|
| **Project Contract** (§10) | `ApprovedL1PlanArtifact` + `PlanApproval` — already a human-approved, identity-bound, non-self-escalating snapshot. A Project Contract is that, scoped to a project rather than an issue, with protected invariants and acceptance criteria added |
| **Execution Plan** (§10) | `L1Plan`'s `proposed_steps` / `files_likely_to_change` / `risks`, promoted from prose to an AIDO-mutable, versioned structure |
| **Planner role** (§11) | The Phase 4E/4H model-backed planner and its gated `generate-model-plan` command — the ancestor of the semantic planner, not something to replace |
| **Step Contract** (§14) | `QualificationTask` + `BaselineContract` + the approved-diff/target-hash binding in 5F2C/5F2D — all three are step contracts for narrow domains already |
| **Verification authority** (§14, §15) | 5F2D's configured-argv, once, bounded execution. `required_verification` stays planner prose and never becomes command authority |
| **Reviewer views** (§19) | The 5F2E reviewer request builder and transmission boundary; the three views are different *inputs*, not a different reviewer architecture |
| **Evidence references** (§12) | Existing schema-versioned artifacts + `qualification/lineage.py` |
| **Role qualification** (§2.3) | The frozen Pi implementer qualification policy, re-instantiated per role — **never genericized in place** |
| **Attempt accounting** (§12) | PRE1 one-shot attempt authority and the attempt-record artifact |

### 9.3 GENUINELY MISSING — the real gap

1. **Persistent orchestration state.** Nothing in AIDO survives a process exit as
   *state*. Every shipped command is a single stateless invocation; every
   artifact is evidence about the past, not a resumable position.
2. **A step abstraction above one file edit.** There is no object meaning "this
   unit of project work" with its own lifecycle.
3. **A deterministic transition engine.** Verification produces exit codes and
   the reviewer produces an advisory verdict, but nothing combines
   planner judgment + verification facts + review result + policy + human
   authority into an authorized state change (§15).
4. **A project-level plan AIDO may evolve.** `L1Plan` is approved and then
   frozen; nothing may legitimately change it as execution reveals reality.
5. **A `PlannerDecision` vocabulary** distinct from a plan document (§11).
6. **Test Authority** — classification, provenance and baseline mode for tests
   (§17).
7. **Multi-step composition** — dependency ordering, readiness, and a project
   integration gate (§16, §20).
8. **Recovery** — reconstructing an interrupted run (§12).

### 9.4 DEFER — named, not designed here

- Independent Tester execution (§18) — until §17 exists.
- Automated production-reachability proof (§17.6) — guidance and qualification
  corpus material first.
- Risk-dimension-driven workflow selection (§22).
- Incident-management tooling (§21) — the *conversion discipline* is roadmap;
  a system is not.
- Stall heuristics and circuit breakers (§7).
- Harness contract extraction, Codex, DSH, routing (M7–M10).
- A permanent fixer role — **not deferred but rejected** (§19.3).

---

## 10. Formal authority layers

Every future control-plane decision must be placeable in exactly one of these
layers, and authority never flows upward.

```text
    HUMAN PRODUCT AUTHORITY
            |
            v
    PROJECT CONTRACT                    human-authoritative, AIDO-immutable
            |
            v
    AIDO-MUTABLE EXECUTION PLAN         AIDO-controlled, may evolve autonomously
            |
            v
    DERIVED STEP CONTRACTS              derived, versioned, per unit of work
            |
            v
    WORKER PROPOSALS / CHANGES / TESTS / REVIEWS    proposals only, never authority
```

### 10.1 The Project Contract

Human-authoritative product intent. It carries at least:

- the project goal;
- approved requirements;
- protected invariants;
- authoritative acceptance criteria;
- human-only decision boundaries.

**The Planner may not silently change any of it.** If implementation evidence
shows that product intent itself must change, that is not a re-plan — it is an
escalation:

```text
PROJECT_CONTRACT_CONFLICT
        ->
HUMAN_REQUIRED
```

The precedent is already shipped: `PlanApproval` requires an exact approval
phrase and rejects paraphrase, and `ApprovedL1PlanArtifact` binds the approval to
one identity and rejects forged nested fields. A Project Contract is that
discipline at project scope.

### 10.2 The Execution Plan

AIDO-controlled, and the layer that is *allowed* to evolve autonomously. It may
contain:

- step decomposition;
- dependency ordering;
- implementation strategy;
- worker selection;
- retry strategy;
- verification strategy;
- newly discovered execution steps.

Evolving the Execution Plan is ordinary autonomous behavior and needs no human
approval by itself. It is versioned, and every `StepRun` records which version it
was derived under (§12).

### 10.3 The boundary that makes the split load-bearing

The distinction is not stylistic. It is what lets AIDO be autonomous *and* safe:

```text
"the ordering of these three steps was wrong"          -> Execution Plan change, autonomous
"this step needs a helper module nobody planned"       -> Execution Plan change, autonomous
"the requirement itself is wrong / underspecified"     -> PROJECT_CONTRACT_CONFLICT -> HUMAN_REQUIRED
"the acceptance criterion cannot be satisfied as written" -> PROJECT_CONTRACT_CONFLICT -> HUMAN_REQUIRED
```

A control plane that cannot tell these apart will either stall on every surprise
or quietly redefine the product. Both are failures.

---

## 11. Planner authority — proposal, not authority

> **The general AIDO principle is unchanged: LLM output is a proposal, never
> authority.** The Planner is not an exception, and it is not promoted to one by
> being AIDO's own role rather than an external worker's.

**Do NOT define the Planner as the authority that marks a step COMPLETE.**

### 11.1 What the Planner produces

Structured semantic decisions — a closed vocabulary, not prose, and not a state
transition:

```text
RECOMMEND_STEP_ACCEPT
RECOMMEND_RETRY_IMPLEMENTATION
RECOMMEND_RETRY_TEST
RECOMMEND_REPLAN
PLAN_CONFLICT
PROJECT_CONTRACT_CONFLICT
HUMAN_REQUIRED
```

Names are indicative, not frozen. What *is* fixed is the shape: a
`PlannerDecision` is an input to authorization, carrying

```text
recommendation                  one of the closed-vocabulary tokens above
bounded rationale                a short, user-visible justification
relevant evidence / contract references     what the recommendation is grounded in
```

and it never names a state to enter.

> **No private reasoning.** "Bounded rationale" is a short, user-visible
> justification the recommendation is expressed with — not a transcript. AIDO
> must **not** require, persist, transmit, or make any authority decision depend
> on a Planner's private chain-of-thought or hidden reasoning trace. This is the
> same boundary §7.1/§19's reviewer supervision already draws for observable
> resource supervision (no reasoning inspection, no chain-of-thought capture) —
> applied here to what a `PlannerDecision` is allowed to carry, not to what may
> be observed about the process that produced it. Nothing here authorizes a
> reasoning-telemetry system.

### 11.2 What the Planner is responsible for

Semantic planning and project coherence:

- interpreting the Project Contract into an Execution Plan;
- decomposing work into steps and ordering their dependencies;
- judging whether a completed step's evidence semantically satisfies its Step
  Contract;
- recognizing when the plan itself is wrong (`PLAN_CONFLICT`) versus when the
  product intent is wrong (`PROJECT_CONTRACT_CONFLICT`).

### 11.3 What the Planner is explicitly NOT

- **not repository authority** — it does not decide what the working tree
  contains; AIDO observes that mechanically;
- **not test authority** — it does not decide whether tests passed; the verifier
  does (§15, §19.2);
- **not state-machine authority** — it cannot cause a transition; the
  deterministic validator authorizes transitions (§15).

### 11.4 The existing planner is the ancestor

The Phase 4E/4H model-backed planner, its strict `L1Plan` parsing, its gated
`generate-model-plan` command and its real-model gate are **the Planner role's
ancestor**, not something to discard for a new subsystem. The evolution required
is: from *one plan document produced once* to *a role that emits successive
structured decisions against persistent state*. The strictness, the gating and
the "a plan may not self-escalate its automation level" invariant carry forward
unchanged.

The Planner is also subject to §2.3: **planner is a role, and it needs its own
`ROLE_CAPABILITY` qualification.** An implementer PASS says nothing about
planning quality.

---

## 12. Persistent project and step state

This is the core missing capability (§9.3), and it moves **earlier** than the
pre-revision roadmap placed it — into M5A, as a prerequisite of v1.

### 12.1 The requirement

AIDO must eventually be able to reconstruct execution after:

- AIDO process crash;
- machine restart;
- harness crash;
- model failure;
- partial implementation;
- interrupted verification;
- partial Tester output;
- Reviewer failure;
- an interrupted retry / re-plan loop.

### 12.2 The logical distinction

```text
ProjectRun
    Project Contract reference
    Execution Plan version
    project state

    StepRun[]
        Step Contract version
        state
        attempt number
        selected runtime combination        (the §2 tuple, recorded not inferred)
        evidence references
```

**No exhaustive schema is locked here.** Field lists are illustrative.

### 12.3 A minimal state model to begin from

```text
PLANNED
READY
EXECUTING
VERIFYING
REVIEWING
ACCEPTANCE
COMPLETE
FAILED
HUMAN_REQUIRED
RECOVERY_REQUIRED
```

**Exact names are not frozen**, and the set will change. The invariant that *is*
fixed:

> **State is persisted outside model context.**
>
> Not in a prompt, not in a transcript, not in a conversation, not in an agent's
> memory, and not reconstructed by asking a model what it was doing.

### 12.4 Recovery is bounded by what AIDO can prove, not by what it hopes

§7.2's distinction applies directly to recovery, and this must not be softened:

```text
AIDO restarted
  != the worker stopped
  != the request was cancelled
  != backend inference stopped
  != the workspace is in the state AIDO last authorized
```

So recovery re-proves rather than assumes. The shipped 5F2D pattern is the
precedent: HEAD object id pinned, dirty state proven to be *exactly* the expected
path, post-image hash matched — and a state that is no longer provably the
approved one is reported as such (`exit 3`), never repaired. A recovered
`StepRun` whose workspace no longer matches its recorded evidence goes to
`RECOVERY_REQUIRED`, not to "resume and hope".

Attempt accounting recovers the same way, and PRE1 already establishes the hard
case: when AIDO cannot prove whether an attempt was spent, the unprovable fact is
recorded as **absent and unestablished**, never as a sentinel value that later
reads as proven. Recovery must preserve that discipline.

---

## 13. Persistent-state implementation direction — SQLite preferred

> **SQLite is recorded as the PREFERRED current implementation direction for
> persistent orchestration state. It is NOT implemented, NOT designed in
> detail, and NOT authorized by this document.** No database, schema, migration,
> table, index or ORM is created here.

### 13.1 Rationale

- atomic state transitions;
- crash-safe transactions;
- unique identifiers;
- attempt counters;
- recovery;
- event / history records;
- consistency constraints;
- materially easier reconstruction than ad-hoc mutable JSON state.

The decisive one is the first two. A step transition that must update state, bump
an attempt counter and link evidence is a single logical act; doing it across
several JSON files makes a crash mid-transition indistinguishable from a
completed one — precisely the ambiguity §12.4 exists to eliminate.

### 13.2 The separation this preserves

```text
SQLite                              = orchestration / STATE authority
                                      mutable, transactional, current position

immutable JSON artifacts + hashes   = evidence / PROVENANCE authority
                                      append-only, schema-versioned, never edited
```

These are different kinds of truth and must not merge. The existing evidence
discipline is unchanged by adopting a database: artifacts stay immutable, stay
emitted through a single choke point that cannot overwrite, and a correction
stays *new linked evidence* rather than an edit (`qualification/lineage.py`).
The database stores **references** to evidence, never a second mutable copy of
it.

### 13.3 Location

```text
The SQLite database lives under an AIDO-OWNED STATE ROOT.
It must NOT live in the target project repository.
```

Orchestration state is not a project artifact. Putting it in the target
repository would make AIDO's own bookkeeping part of the workspace it must
observe cleanly — and the shipped writer and verifier both depend on the
Git-visible dirty state being *exactly* what AIDO approved.

### 13.4 Not decided here

No tables, no columns, no keys, no indexes, no migration strategy, no ORM
choice, no concurrency model, no retention policy. If a future design turn shows
an illustrative table sketch, it is **non-frozen example material** and carries
no authority.

---

## 14. Step Contract

A first-class future control-plane concept: the derived, versioned statement of
what one unit of work is, and what would make it done.

> **The example YAML schema from architecture discussion is NOT frozen and is
> deliberately not reproduced here.** What follows is the binding list, not a
> file format.

### 14.1 What a Step Contract should eventually bind

- Project Contract version / reference;
- Execution Plan version;
- step objective;
- dependencies;
- step requirements;
- protected invariants;
- baseline repository identity;
- authorized write scope;
- verification authority;
- test authority;
- risk dimensions (§22);
- required roles;
- human escalation conditions.

### 14.2 Architectural precedents — evolve these, do not fork

AIDO has already built step contracts three times, each for a narrow domain:

| Precedent | What it already binds |
|---|---|
| `QualificationTask` + `task_revision` | Frozen identity by content digest over files, prompt, verification argv, protected patterns and expected changed paths — a step contract with an immutable version |
| `BaselineContract` | Structured baseline expectation as *data*, interpreted in exactly one place, and included in the revision digest so a baseline change cannot leave the revision identical |
| 5F2C approved diff + 5F2D verification binding | Baseline repository identity (HEAD object id, pre-image SHA-256), authorized write scope (exactly one path), and verification authority (exact configured argv) |
| `ApprovedL1PlanArtifact` | Human approval bound to one identity, with a snapshot rather than a reference |

The Step Contract generalizes these **upward into the control plane**; it does
not replace them, and it must not become a second parallel implementation of a
binding one of them already performs.

### 14.3 Two rules carried forward unchanged

- **`required_verification` is planner prose and never command authority.** A
  Step Contract's *verification authority* names a project-configured
  verification, on the shipped 5F2D pattern. It is never a command string
  derived from a model's text.
- **A contract is versioned by content, not by a mutable label.** The
  `task_revision` digest pattern exists because a contract change that leaves
  the version identical is silent drift.

---

## 15. Deterministic transition engine

An explicit roadmap capability, and one of the control plane's core
responsibilities.

### 15.1 Rules that must NOT exist

```text
REVIEWER PASS        ->  COMPLETE          FORBIDDEN as a direct rule
PLANNER SAYS DONE    ->  COMPLETE          FORBIDDEN as a direct rule
```

Neither a reviewer verdict nor a planner recommendation is a transition. Both are
inputs.

### 15.2 The required shape

```text
    Planner semantic judgment           (§11, advisory)
  + deterministic verifier facts        (AIDO-observed, authoritative)
  + required review result              (when policy requires it)
  + policy requirements                 (§22)
  + required human approval             (when policy requires it)
            |
            v
    DETERMINISTIC TRANSITION VALIDATOR
            |
            v
    COMPLETE | RETRY | REPLAN | HUMAN_REQUIRED | FAILURE
```

The validator is ordinary deterministic code. It is not a model, it does not call
one, and it does not accept a state name from any model output.

### 15.3 Precedent

This is the shipped discipline generalized, not a new idea:

- the 5F2D verifier already separates *refused* / *ran and did not pass* /
  *no longer provably the approved state* into distinct deterministic exit
  codes, and never repairs;
- the 5F2E reviewer's verdict is already **advisory and terminal at a human** —
  `approve`, `changes_requested` and `needs_human_review` all exit 0, and none of
  them causes an action;
- `qualification/records.py` already rejects internally impossible records at
  construction rather than coercing them.

A transition validator is the same posture applied to state.

### 15.4 Refusal is a legitimate outcome

Consistent with the project's standing preference for fail-closed refusal over
generalization: a combination of inputs the validator does not recognize
produces `HUMAN_REQUIRED`, never a best guess. Adding a permissive default to
"unblock" a run is the failure mode this engine exists to prevent.

---

## 16. The two nested execution loops

Target concept only. **Neither loop is implemented or authorized here**, and §23
requires the single-step vertical slice to be proven before the outer loop is
built.

### 16.1 Outer project loop (M6C)

```text
select ready step                    (dependencies satisfied, §12/§14)
derive or update Step Contract       (§14)
execute inner loop                   (§16.2)
acceptance                           (§15)
persist evidence and state           (§12, §13)
update Execution Plan                (§10.2)
continue until project completion    (§20)
```

### 16.2 Inner step loop (M6)

```text
qualified worker execution           (§2 combination, recorded on the StepRun)
deterministic verification           (AIDO-owned, authoritative)
reviewer when required               (§19, §22)
correction / retry / re-plan         (§19.3 — Implementer corrects; no fixer role)
Planner semantic acceptance judgment (§11, advisory)
deterministic transition authorization (§15)
```

### 16.3 The sequencing rule

> **Prove the inner loop on a single step before building the outer loop.**

The §23 vertical slice *is* the inner loop with a single step, and it is where
every hard problem shows up first: contract derivation, evidence, recovery, and
the transition validator's real inputs. An outer loop built before that would be
iteration over an unproven body.

---

## 17. Test Authority

A dedicated concept that must exist **before** independent Tester execution
(M6A precedes M6B).

### 17.1 Authority classes

Approximately — **exact enum names are not frozen**:

```text
CONTRACT_ACCEPTANCE      tests that encode authoritative acceptance criteria
PROTECTED_REGRESSION     tests protecting established behavior
IMPLEMENTATION_OWNED     tests owned by the implementation of a step
TESTER_SUPPORTING        Tester's own supporting tests
```

### 17.2 The core principle

> **Freeze authority, not an entire `tests/` directory.**

Freezing a whole directory is both too strong (it blocks legitimate work) and too
weak (it says nothing about *why* a given test may not be weakened). Authority is
the property worth protecting.

### 17.3 The critical non-equivalence

```text
Tester creates a test        !=        the test becomes authoritative
```

Authority is **issued by AIDO**, never claimed by the role that wrote the test:

```text
Tester proposes test
        ->
AIDO validates provenance / scope / baseline / contract relationship
        ->
AIDO issues (or refuses) the authority classification and freezes provenance
        ->
the test may become authoritative
```

The precedent is exact: `qualification/records.py` is an **invariant gate, not a
formatter**, and it rejects records that assert things the run cannot support. An
authority issuer is the same gate applied to tests.

### 17.4 Disputing an authoritative test

A worker that believes an authoritative test is wrong does not edit it:

```text
TEST_CONTRACT_AMENDMENT_REQUEST
        ->
Planner evaluates the semantic issue
        ->
    ordinary test defect
        -> authorize Tester amendment
        -> establish NEW provenance / hash

    requirement or product conflict
        -> PROJECT_CONTRACT_CONFLICT
        -> HUMAN_REQUIRED
```

**The Reviewer must not directly rewrite authoritative acceptance criteria.** A
reviewer that can rewrite the criteria it reviews against is not a check.

### 17.5 Baseline provenance modes

```text
MUST_RED                 the test must fail on the baseline
MUST_GREEN               the test must pass on the baseline
RED_OR_GREEN_ALLOWED     either is legitimate for this test
```

**Do not globally require every new acceptance test to fail on baseline.** That
rule is right for one class of work and wrong for another:

- bug fix / genuinely new behavior — often `MUST_RED`;
- refactor / behavior-preserving migration / strengthening an existing guarantee
  — legitimately `MUST_GREEN`.

A blanket MUST_RED rule pressures a worker into weakening the production code, or
into writing a test that fails for an irrelevant reason, purely to satisfy the
gate.

> **Baseline outcome must be AIDO-OBSERVED, never Tester-reported.**

The precedent is shipped and structural: `BaselineContract` holds the expected
shape as data, `evaluate_baseline_contract` is its single interpreter, and the
contract participates in the task revision digest so it cannot drift silently.

### 17.6 Production reachability (guidance, not automation)

For authoritative acceptance tests, fixtures should normally prove that the
tested state is **reachable through production architecture**. Prefer real:

- constructors;
- factories;
- APIs;
- middleware;
- codecs;
- persistence layers;
- transactions;
- orchestration boundaries.

Direct construction of an internally impossible state does not count as proof —
unless the test *intentionally* targets corrupt or invalid input behavior, which
is a legitimate and explicitly different case.

**Do not attempt generic automated reachability proof.** There is no general
mechanical test for "could production reach this state". Treat reachability as:

- test-authority guidance (§17.1–§17.3);
- Tester qualification corpus material (§18, §21);
- Reviewer qualification corpus material (§19, §21);
- incident-driven regression material (§21).

---

## 18. Independent Tester — deferred until its authority foundation exists

TESTER is recorded as an eventual independent role (M6B).

> **It is explicitly NOT the immediate next implementation.** The immediate next
> implementation work is Q1/Q2 (§4.4).

### 18.1 Why it is deferred

Tester depends on:

```text
Step Contract               (§14)
persistent StepRun state    (§12)
deterministic verifier      (shipped, extended in §15)
Test Authority model        (§17)
```

Without those, a Tester is **merely another unconstrained coding agent** writing
files into a repository, with no mechanism deciding whether what it wrote means
anything. That is a capability regression dressed as a feature.

It also needs its own `ROLE_CAPABILITY` qualification (§2.3): an implementer PASS is not a
tester PASS.

### 18.2 Eventual Tester boundary

**READ:**

- the Step Contract;
- the relevant portion of the Project Contract;
- architecture;
- the baseline repository;
- existing tests;
- the test-authority manifest.

**WRITE:**

- authorized Tester test paths;
- proposed acceptance tests;
- Tester-supporting tests.

**MUST NOT independently modify:**

- production implementation;
- the Project Contract;
- frozen acceptance tests;
- protected regression tests;
- policy configuration;
- existing authority manifests.

Everything a Tester writes is a **proposal** until AIDO issues authority (§17.3).

---

## 19. Reviewer evolution

The current controlled reviewer architecture is **preserved**: one
project-configured model, one advisory verdict, a strict non-repairing parser,
bounded issuance, and a verdict that ends at a human. The evolution below changes
what the reviewer is *shown* and how its output is *routed* — not the reviewer's
authority, and not RS1's supervision contract.

### 19.1 Three semantic reviewer views

```text
A. Implementation Review     the diff against the Step Contract
B. Test Review               the tests against the Step Contract
C. Cross Review              Step Contract <-> Implementation <-> Tests
```

For medium/high-risk work, **Stage A should be blind to the Implementer's
rationale and final report where practical.** A reviewer primed with the author's
narrative tends to check the narrative rather than the code.

Stage A should receive:

- the Step Contract;
- relevant architecture;
- the authoritative diff;
- deterministic verifier evidence;
- the tests.

And should adversarially inspect for:

- green-but-broken cases;
- unreachable fixtures (§17.6);
- production-boundary bypass;
- duplicated authority;
- stale or mismatched provenance;
- concurrency and time-of-check-time-of-use defects;
- misleading tests;
- implementation/test mutual blind spots.

**Only after independent technical review** may the Implementer's semantic claims
be shown, where useful.

The 5F2E transmission boundary discipline carries forward: the reviewer receives
a deliberately selected set of material, and widening it is a design decision
with its own justification — never a convenience.

### 19.2 Claim audit — deterministic first

> **Do NOT assign mechanically verifiable Implementer claims to a Reviewer AI.**

These are repository facts AIDO can decide itself, and must:

```text
clean worktree
exact test counts
exact files changed
no tests deleted
collection count
no unexpected commits
```

AIDO already proves facts of exactly this kind mechanically — HEAD pinning, exact
dirty-path proof, post-image hashing, verification exit classification. Spending
reviewer inference on them is wasteful *and* strictly worse: a model's opinion
about whether the worktree is clean is weaker evidence than `git` output.

The Reviewer audits only claims that are **not mechanically decidable**:

```text
requirement completeness
compatibility interpretation
architectural meaning
semantic coverage
```

### 19.3 Defect routing

The Reviewer may classify likely defect ownership:

```text
IMPLEMENTATION_DEFECT
TEST_DEFECT
PLAN_DEFECT
CONTRACT_CONFLICT_SUSPECTED
UNKNOWN
```

**Classification is advisory semantic evidence.** AIDO's policy and state-machine
logic performs the actual routing (§15):

```text
IMPLEMENTATION_DEFECT              -> Implementer correction
TEST_DEFECT on a supporting test   -> Tester correction
authoritative test dispute         -> TEST_CONTRACT_AMENDMENT_REQUEST (§17.4)
PLAN_DEFECT                        -> Planner
product intent change              -> HUMAN_REQUIRED
```

> **Do NOT create a separate permanent FIXER role.** Implementation correction is
> an Implementer responsibility. This is consistent with the standing project
> position that a fixer is unauthorized, and it is not a deferral: a fixer is a
> third party with write authority over code it did not plan or implement, which
> adds an authority boundary without adding a check.

### 19.4 What does not change — and where the reviewer's terminal boundary sits, now vs. later

**Two different things carry the word "terminal" here, and they must not be
conflated.**

```text
CURRENT — the shipped 5F2E command (l2-review-approved-file-edit)
    the review packet's verdict is advisory
    the COMMAND is terminal at a human: it makes no routing decision,
      calls nothing else, and its exit code is the end of that invocation
    frozen shipped semantics — unchanged by this document, unchanged by §19.1–§19.3

FUTURE — M6B orchestrated review, inside the control plane
    the Reviewer's output remains advisory semantic evidence
    it does NOT directly mutate state and is never itself a transition
    AIDO's deterministic policy / transition validator (§15) MAY route it to:
        Implementer      (§19.3 IMPLEMENTATION_DEFECT)
        Tester            (§19.3 TEST_DEFECT on a supporting test)
        Planner           (§19.3 PLAN_DEFECT)
        Human             (§19.3 CONTRACT_CONFLICT_SUSPECTED / product intent)
    according to the Step Contract (§14) and policy (§22)
```

So: for the command that exists **today**, "terminal at a human" is literally
true — nothing downstream of `l2-review-approved-file-edit` consumes its exit
code automatically, and this document does not change that command's
implementation or claim it already performs the M6B routing above. §19.3's
defect-routing table describes the **future, M6B** flow, not current behavior.

What stays true in both the present and the M6B future:

- the reviewer's verdict is **advisory**, never authority — a verdict never
  itself performs a state transition (§15.1);
- the strict parser stays strict — invalid output is rejected, never repaired;
- RS1's bounds are untouched: `max_retries = 0`, at most two semantic requests,
  one HTTP/model request per attempt, a terminal stall, AIDO's own monotonic wait
  deadline, and no claim that a worker or backend was stopped;
- no second reviewer, no consensus, no voting, no fallback model, no provider
  failover.

Reviewer is a role under §2.3 and needs its own `ROLE_CAPABILITY` qualification
— and AIDO already holds a recorded reviewer **false negative** from its leading
implementer candidate model (§1.1), which is exactly why.

---

## 20. Project integration gate

A future project-level acceptance gate (M6C).

> **Do not assume:** every individual step COMPLETE **⇒** the project is
> COMPLETE.

Steps are verified in isolation against their own contracts. Cross-step
interactions, integration behavior and project-wide invariants are, by
construction, not what any single step's verification observed.

After all required steps are complete, AIDO should run:

```text
required full verification
cross-step invariant checks
project integration verification
final architecture / regression review where required
Planner project-level semantic acceptance judgment       (advisory, §11)
deterministic Project COMPLETE transition authorization  (§15)
final evidence / report
human review according to policy
```

**Keep the initial implementation simple.** The first version may legitimately be
little more than "run the project's full configured verification, plus one
project-level review, plus a human". The gate's existence is the point; its
sophistication can grow.

---

## 21. Incident corpus — incident-to-qualification conversion

A permanent roadmap capability: real engineering incidents become frozen
qualification material, so that a failure observed once becomes a failure the
qualification bar can detect afterwards.

### 21.1 The conceptual flow

```text
real engineering incident
        ->
incident intake
        ->
remove proprietary / unnecessary context
        ->
minimized reproduction
        ->
identify affected role(s)
        ->
freeze fixture / hashes / expected behavior
        ->
add corpus case
        ->
qualification policy revision            (§2.2 — a new revision, never a re-score)
```

### 21.2 Example incident classes

Drawn from real experience:

```text
TEST_DELETE              a worker deletes a failing test
TEST_WEAKEN              a worker weakens an assertion to pass
FIXTURE_IMPOSSIBLE       a fixture constructs a state production cannot reach
AUTOUSE_HIDE             an autouse fixture hides a real failure
REPORT_FALSE             a worker's final report asserts something untrue
AUTHORITY_DUPLICATION    a second copy of an authoritative expectation appears
CROSS_LAYER              a change bypasses a production boundary
HARNESS_FAIL             the runtime itself fails in a way AIDO must classify
```

**One real incident may produce several role-specific cases.** `TEST_WEAKEN` is
an implementer corpus case (did the worker do it?) *and* a reviewer corpus case
(did the reviewer catch it?) *and* eventually a tester corpus case. Each is
scored under its own role policy (§2.3).

### 21.3 Precedent and constraint

AIDO has already done this once: the seeded reviewer false negative recorded in
`experiments/b300_reviewer_benchmark/` is exactly an incident converted into
role-specific evidence, and the IQ-1/2/3 corpus is a frozen, digest-versioned
fixture set of the shape §21.1 describes.

Two constraints:

- a corpus addition is a **policy revision** (§2.2). It never re-scores an
  existing record, and it never retroactively converts a FAIL into a PASS or the
  reverse;
- **do not implement an incident-management system now.** What is roadmap here is
  the *conversion discipline*. Tracking, intake tooling and workflow are not.

---

## 22. Risk-based workflow policy

An eventual policy layer (post-M6B), recorded so the roles above are not applied
uniformly to work that does not need them.

> **Do NOT require Tester + Reviewer for every trivial change.** A control plane
> that costs the same for a typo fix as for an auth change will be bypassed.

### 22.1 Preserve the dimensions, not a single label

```text
security                permission             public contract
authentication          persistence            authority / provenance
authorization           migration              destructive filesystem / Git
concurrency             money / calculation    blast radius
                                               reversibility
```

**Do not store only a single HIGH / MEDIUM / LOW label.** The label is derivable
from the dimensions; the dimensions are not derivable from the label, and it is
the dimensions that tell a reviewer *what to look at*. A step marked HIGH tells a
reviewer nothing; a step marked "authorization + reversibility" tells it
everything.

### 22.2 Eventual workflow selection

```text
LOW
    Implementer -> Verifier -> acceptance

MEDIUM
    Tester + Implementer -> Verifier -> Reviewer -> acceptance

HIGH
    Tester authority establishment
      -> Implementer
      -> Verifier
      -> blind Reviewer (§19.1 Stage A)
      -> claim audit (§19.2)
      -> acceptance
      -> Human where policy requires
```

**This is not a near-term implementation requirement.** The v1 slice (§23) runs
one fixed workflow, and risk dimensions may be recorded on a Step Contract (§14.1)
long before anything selects a workflow from them.

---

## 23. The minimum vertical slice

The first autonomous-control-plane implementation after Q1/Q2 and runtime
selection must **not** attempt the complete final architecture.

### 23.1 The recommended slice (M6 / AIDO v1)

```text
Human-approved Project Contract snapshot
        ->
Planner PROPOSES / derives Step Contract content        (§11, advisory only)
        ->
AIDO validates it against Project Contract, Execution
  Plan, policy, and baseline/authority inputs, then
  ISSUES and version-binds the Step Contract            (§14 — AIDO authority)
        ->
persist StepRun
        ->
qualified Implementer                       (the §2 combination selected at M4)
        ->
deterministic Verifier                      (AIDO-owned, authoritative)
        ->
existing Reviewer when required             (shipped 5F2E path)
        ->
Planner semantic acceptance recommendation  (advisory, §11)
        ->
deterministic transition authorization      (§15)
        ->
COMPLETE / RETRY / HUMAN_REQUIRED
        ->
persisted evidence
```

> **The Planner does not issue a Step Contract; it proposes one.** This is the
> same non-equivalence §17.3 fixes for Tester-authored tests, applied to the
> Planner: a Planner-drafted Step Contract is a proposal until AIDO validates it
> against the Project Contract, the current Execution Plan, policy, and baseline
> identity, and issues the accepted, version-bound contract. §11.3 already states
> the Planner is not state-machine authority; this makes explicit that Step
> Contract issuance is one of the authorities §11.3 withholds.

Each box's actual status, stated so this document does not overclaim:

```text
ALREADY SHIPPED
    deterministic Verifier                shipped 5F2D
    Reviewer when required                shipped 5F2E (+ RS1/V1/V2)
    evidence / authority primitives        §9.1 — approval, path policy,
                                            writer, verification and review
                                            artifacts

EXISTING QUALIFICATION / RUNTIME FOUNDATION, NOT YET A QUALIFIED IMPLEMENTER
    Pi implementer harness infrastructure  under live M3 qualification
                                            (Q1/Q2 — currently NO-GO, §8.1);
                                            no PASS exists and no qualified
                                            implementer combination exists yet

FUTURE, REQUIRED, NOT YET AUTHORIZED
    M5A control-plane foundation           Project/Step Contract, ProjectRun /
                                            StepRun, transition validator (§12–§15)
    M5 real-workspace implementer          authority to write into a real
      authority                            workspace at all — still NO-GO (§8.1)
```

**No box above claims a qualified Implementer or real-workspace implementation
capability already exists.** The "qualified Implementer" box in the slice
diagram names *what M4 would select if Q1/Q2 produce a PASS*, not a shipped
capability — the harness infrastructure it would run through is present and
under qualification, but qualification, selection, and real-workspace
authorization are all still ahead of this slice, not behind it. Nothing in the
slice requires a second harness, a second reviewer, or a new model role beyond
the Planner.

### 23.2 Explicitly deferred from this first slice

```text
independent Tester                      multi-step project loop
parallel roles                          Codex
DeepSeek Harness                        dynamic routing
automatic fallback                      advanced stall detection
OS sandbox                              generalized test-framework support
```

### 23.3 Why a single step, and why end-to-end

A vertical slice through every layer surfaces the integration problems that a
horizontal layer cannot: what the transition validator actually needs as input,
what recovery actually has to re-prove, what a Step Contract actually has to
carry, and where the Planner's judgment is and is not usable. Building all of
M5A's layers broadly before running one step end-to-end would produce a complete
architecture validated by nothing.

---

## 24. What this document does NOT authorize

- Implementing Q1 or Q2, or any part of them.
- Running Pi, launching a Pi/Node process, or sending any semantic or model
  prompt.
- Reading, injecting, or forwarding any credential; contacting B300 or any other
  backend.
- Modifying qualification runtime code, or any frozen AR1 / AR2 / AR2-O1 / I1 /
  I2 / I2B / PRE1 module.
- Refactoring PRE1, Q1 or Q2 into a generic harness framework; adding an
  `AgentRuntime` abstraction, a harness registry, a harness plugin interface, a
  provider/harness capability list, or a routing surface.
- Implementing the §2 tuple as a type, a config schema, a record schema, or a
  selection algorithm.
- **Implementing SQLite, any database, schema, table, migration, ORM, or state
  store** (§13). The preference is recorded; nothing is built.
- **Implementing the Project Contract, Execution Plan, Step Contract,
  `ProjectRun`, `StepRun`, `PlannerDecision`, the transition validator, either
  execution loop, Test Authority, the Tester role, reviewer view routing, the
  project integration gate, an incident corpus system, or a risk-policy engine**
  (§10–§23). All are roadmap concepts; none is authorized, designed in detail, or
  frozen as a schema.
- Changing the shipped reviewer's authority, its strict parser, or RS1's
  supervision contract.
- Codex integration, DeepSeek Harness integration, or any second-harness work.
- Real-workspace or sibling-project implementation authority.
- A fixer, a review/fix loop, a second reviewer, reviewer failover (RS2), or an
  automatic continuation policy.
- Progress-supervision telemetry, a circuit breaker, streaming, cancellation, or
  any mechanism implying a worker or a backend was stopped.
- Editing frozen historical design documents to make their terminology
  retroactively generic, or genericizing the Pi-specific Q1/Q2 qualification
  work.
- Commits, pushes, branches, or PRs.

Each of the above requires its own explicit prompt.
