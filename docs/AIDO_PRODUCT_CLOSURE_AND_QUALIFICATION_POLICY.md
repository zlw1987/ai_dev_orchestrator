# AIDO Product Closure and Qualification Policy

> **STABLE GOVERNANCE POLICY — DOCUMENTATION ONLY.**
>
> This document is **not** a phase authorization and **not** a
> qualification-policy revision. It authorizes nothing to execute.
>
> It does **not**:
>
> - modify any frozen qualification hard bar;
> - modify any frozen evidence semantics;
> - add a model to `CANDIDATE_MODEL_IDS`;
> - authorize any live run;
> - authorize any real-workspace write;
> - reinterpret any historical candidate result;
> - modify any role qualification policy;
> - modify, delete or overrule any frozen design, authorization or roadmap
>   dependency.

| | |
|---|---|
| Kind | Governance policy (stable) |
| Recorded | 2026-09-24 |
| Recorded after | CFG1 FU1 implementation ACCEPTED / FROZEN at `7f31217580b21027556b2061d5e765c7eef162c0` |
| Authorizes | **Nothing** |

## 1. Closure discipline

AIDO optimizes for **project closure and end-to-end product progress**, not
maximum local proof depth.

A newly discovered issue **blocks an active phase** only when it can materially:

- falsify authoritative evidence;
- violate an authority/trust boundary;
- leak or corrupt a real workspace or sensitive state;
- cause uncontrolled execution; or
- make a required lifecycle/correctness claim mechanically false.

Y-6 and FU1-AUTH-1 / FU1-AUTH-2 were correct blockers because they met those
conditions.

Defense-in-depth improvements, diagnostics, speculative/theoretical hardening and
unrelated safety enhancements **normally go to backlog** rather than expanding the
active phase.

**This rule never permits weakening** a frozen safety invariant, a frozen
authority boundary, a frozen hard bar, required mechanical evidence, or lifecycle
truthfulness. It governs only what is *added* to an active phase.

Once a candidate clears the frozen autonomous implementer hard bar, priority
shifts to authoritative selection, bounded real-workspace authority, and a
human-supervised end-to-end Alpha — rather than continued candidate hunting or
endless refinement of the qualification harness before Alpha.

## 2. Model-candidate history is append-only

Historical candidates and their outcomes remain frozen. New candidates are
appended; nothing already recorded is rewritten.

| Candidate | Exact model id | Status |
|---|---|---|
| A | `qwen3-coder-next` | IMPLEMENTER NOT_QUALIFIED / historical frozen. Separately, Category-B runtime compatibility QUALIFIED / FROZEN (compatibility only; not implementer role capability) |
| B | `minimax-m2.7` | IMPLEMENTER NOT_QUALIFIED / historical frozen. Separately, Category-B runtime compatibility QUALIFIED / FROZEN (compatibility only; not implementer role capability) |
| C | `qwen3.6-27b` | Identity/design named by the existing Q3 design; live qualification requires separate authorization; currently **NO-GO** (not currently authorized); production candidate registry **not changed** by this document |
| D | `qwen3.8-27b` | **NEW PLANNED candidate.** No qualification credit. No live authorization. Not in the production candidate registry. Requires its own future design, implementation and live authorization |

The exact currently planned served model id for D is `qwen3.8-27b`. Do not infer
from it: weight identity with any other Qwen model, context size, backend
deployment identity, provider id, performance score, or qualification status.

The operator's successful use of `qwen3.8-27b` on Product Intelligence and B300
Forecast is **motivating operational experience only**. It is rationale for
testing order, not AIDO qualification evidence, and belongs in no authoritative
qualification table. Candidate D is neither qualified nor implemented.

## 3. Implementer sequencing

1. Complete the current CFG1 / pre-A4 chain.
2. Candidate C remains the next planned implementer qualification candidate.
3. If **C PASSES** the frozen autonomous implementer hard bar: D is **not** a
   prerequisite for Alpha. Proceed toward authoritative selection, bounded
   real-workspace authority and a human-supervised Alpha. D may still be
   qualified later as an alternate implementer.
4. If **C FAILS** the frozen hard bar: D is the next planned implementer
   candidate.
5. If **C and D both FAIL**: the hard bar is **not lowered**. A separate
   supervised-implementer policy/design decision is opened.

"C and D both fail → supervised policy" **only selects the next design branch**.
It does not itself authorize real-workspace execution and does not bypass the
existing M4/M5 authority graph.

## 4. Implementer and reviewer authority are independent

`qwen3.8-27b` is also added to the **future reviewer** qualification candidate
pool. Nevertheless:

- an implementer PASS gives **zero** reviewer authority;
- a reviewer PASS gives **zero** implementer authority;
- reviewer qualification uses its own role-capability policy, corpus and hard
  bar;
- evidence from Product Intelligence, B300 Forecast, subjective operator
  preference, or any other role may choose testing order but grants **zero**
  qualification credit.

ROLE / HARNESS / BACKEND / MODEL separation is preserved.

## 5. Alpha definition

The first meaningful Alpha is defined narrowly:

- one real, low-risk repository/project;
- one bounded implementation step;
- explicit real-workspace authority;
- deterministic verification;
- independent review;
- explicit human approval at the required boundary;
- mechanically proven final/cleanup state.

Alpha does **not** require first completing every future role, harness
plurality, dynamic routing, full multi-step autonomy, advanced stall
supervision, or a complete generalized autonomous-project framework.

**Existing frozen authority does not already permit this Alpha.** Reaching it
requires the separately authorized steps in the roadmap.

## 6. Control-plane / persistence closure rule

The roadmap's larger Project Contract / Step Contract / persistent-state
architecture is **not deleted or overruled** by this policy.

The closure principle: do not expand pre-Alpha implementation scope merely to
maximize completeness of a generalized control plane. Implement only the minimum
authority/state the accepted Alpha path needs, while preserving every frozen
dependency that is actually required.

If a frozen roadmap explicitly makes a component a prerequisite (for example the
M5A authority model that M5 consumes), **this policy alone does not remove that
prerequisite.** Changing a frozen dependency requires a separate, explicit
architecture decision.

## 7. Explicit non-authorizations

This document does not authorize: any live run; qualification of any candidate;
any addition to `CANDIDATE_MODEL_IDS`; any real-workspace write; A4; Stage 2; AR2
live; any change to a hard bar, evidence semantic, or role qualification policy;
or any removal of a frozen roadmap prerequisite.
