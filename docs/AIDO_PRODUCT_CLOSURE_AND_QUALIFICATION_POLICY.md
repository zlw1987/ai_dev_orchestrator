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
| Amended | 2026-10-14 — §8 DEC-SUP: opens the supervised-implementer branch (`SUP-D`, no qualification credit). Offline, library-only ALPHA-P1A only; nothing live |
| Amended | 2026-10-15 — §9 DEC-SUP-LIVE: authorizes the two live supervised-implementer commands (ALPHA-P1B), implemented and tested offline only. No live request is authorized by this amendment; the first one needs a separate AUTH-PILOT decision |
| Amended | 2026-11-10 — §10 ALPHA-2B: PO-1/PO-2/PO-3, one human-initiated correction round (ALPHA-2B-T1), implemented and tested offline only. No live correction round is authorized |
| Amended | 2026-11-18 — §12 P0-RECOVERY-T2: the supervised implementer's reply may use one of exactly two envelopes, the default `json_content_text` or the opt-in `delimited_file`; PO-2's byte-identity applies to the default. Prospective, implemented and tested offline only. No live request is authorized |

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

## 8. DEC-SUP amendment (2026-10-14) — supervised implementer branch

> **Appended amendment. §1–§7 above are unchanged and still in force.** This
> section records a human/architect decision, DEC-SUP option A, taken on the
> proposal
> [ALPHA_P1A_DEC_SUP_DECISION_PROPOSAL.md](ALPHA_P1A_DEC_SUP_DECISION_PROPOSAL.md).

**What changes in §3.** §3 opened the supervised-implementer branch only after
C and D had both failed the frozen hard bar. DEC-SUP opens **one** supervised
branch now, **in parallel** with that sequence and without replacing it. §3's
autonomous sequencing (C next, then D, and the hard bar never lowered) is
otherwise unchanged.

**The supervised role.**

- Role `supervised_implementer` is distinct from the autonomous (Pi)
  implementer role. Its output is **untrusted proposed content only**, and it
  reaches a workspace only through the unchanged L2 chain: deterministic diff,
  exact human diff approval (H6), then the single 5F2C writer.
- Candidate `SUP-D` is bound to the exact model id `qwen3.8-27b`. `SUP-D` is
  **not** added to `CANDIDATE_MODEL_IDS`, carries **no** qualification credit
  in either direction, and is not Candidate D's autonomous qualification. A
  supervised result is never evidence for the §16 hard bar, and no
  autonomous-qualification record may reference it.
- Role, harness, backend and model separation (§4) is unchanged. A supervised
  PASS of any kind grants zero autonomous-implementer and zero reviewer
  authority.

**Item answers (proposal §6).** Items 2–7 and 9 adopt the recommended
options. Item 8 was **not decided**: the proposal offered it with no
recommended option, and the operator gave no separate answer.

| # | Decision |
|---|---|
| 2 | Role `supervised_implementer`; candidate `SUP-D` = `qwen3.8-27b`, outside `CANDIDATE_MODEL_IDS`, no credit |
| 3 | One in-scope, unredacted, cap-bounded file per request, announced before transmission; multi-file and repository-wide transmission stay forbidden |
| 4 | The Phase 5D2 bounded read runs **in-process**; a saved packet is never transmission authority |
| 5 | Plaintext HTTP requires an explicit acknowledgement opt-in for **every** provider, shipping `false`, worded as an acknowledgement and never as a security claim |
| 6 | A separate implementer-provenance record; AIDO-fixed rationale prose in the diff artifact, never model prose |
| 7 | Zero semantic retries and zero transport retries |
| 8 | **Not authorized.** No permission to modify `CLAUDE.md` was given. Its existing non-goal wording ("no model-backed implementer", "nothing else may call a model") is acknowledged as stale relative to the authorized offline supervised library. Updating `CLAUDE.md` requires a separate, explicit operator authorization |
| 9 | ALPHA-P1A is **offline and library-only**: no CLI command, no real client construction, no live request |

**Still not authorized:** any live Qwen 3.8 request; any real-source
transmission; any real-workspace execution; a CLI command for the supervised
implementer; a fixer; a review/fix loop; a fallback model; or provider
failover. The first live supervised pilot requires its own separate
authorization (proposal §7).

## 9. DEC-SUP-LIVE amendment (2026-10-15) — live supervised implementer authority

> **Appended amendment. §1–§8 above are unchanged and still in force**,
> including every DEC-SUP item answer in §8. This section does not retroactively
> alter any P1A decision. It records the operator's decisions D-1 to D-10 on
> [PHASE_ALPHA_P1B_LIVE_IMPLEMENTER_AUTHORITY_DESIGN.md](PHASE_ALPHA_P1B_LIVE_IMPLEMENTER_AUTHORITY_DESIGN.md)
> (§11 there is authoritative).

**What it authorizes.** The two ALPHA-P1B commands,
`l2-supervised-implementer-prepare` and `l2-supervised-implementer-run`, as
designed, **implemented and tested offline only**. That narrows §8's "Still not
authorized" item "a CLI command for the supervised implementer" to exactly these
two commands. §8 item 8 (`CLAUDE.md`) is now answered by D-1 for the P1B entry
point only: a narrow `CLAUDE.md` update that distinguishes the supervised,
proposal-only implementer from the still-absent autonomous one.

**Decisions.**

| # | Decision |
|---|---|
| D-1 | Narrow `CLAUDE.md` update for the supervised entry point; no unrelated operating rule changes |
| D-2 | The live path uses the existing `litellm` provider contract only |
| D-3 | It reads the existing `AIDO_LITELLM_*` environment family only |
| D-4 | An explicitly configured wait deadline is required; there is no default |
| D-5 | The request and an accepted response are retained as local evidence; no secret or authorization header is ever retained |
| D-6 | Workspace and source state must be independently verified by AIDO at the live consumption boundary; an operator's clean-clone claim alone is insufficient |
| D-7 | A per-run authorization expires 60 minutes after it is prepared |
| D-8 | The maximum buffered response is 16 MiB, a transport safety limit and not a product token budget |
| D-9 | Structured output is disabled for the initial pilot until its exact supported mode is established and separately authorized; the strict local response contract is always enforced |
| D-10 | The pilot repository, clone and file are selected by a separate live-pilot authorization |

**Unchanged.** `SUP-D` = `qwen3.8-27b` stays outside `CANDIDATE_MODEL_IDS` and
earns no qualification credit, in either direction. §3's frozen C → D
autonomous sequencing, every hard bar, and every historical candidate record
are unchanged. Nothing here implies that Qwen 3.8 is qualified for any role.

**Still not authorized:** any live model request; any real source
transmission; any real-workspace access by the live commands; any H6 approval,
write, verification, commit or push following a supervised proposal; an
autonomous model-backed implementer; a fixer; a review/fix loop; a fallback
model; provider failover; a live `vllm` provider; structured output on the live
path. The first live supervised run needs a separate AUTH-PILOT decision (D-10)
**and** a human-completed per-run consent.

## 10. ALPHA-2B amendment (2026-11-10) — one human-supervised bounded correction round

> **Appended amendment. §1–§9 above are unchanged and still in force**,
> including every DEC-SUP (§8) and DEC-SUP-LIVE (§9) decision, except for the
> three narrow, Alpha 2B-specific exceptions recorded here. It records the
> Product Owner's acceptance of ALPHA-2B-D1 Option C, at baseline
> `0ebd9f65034686c4fdc05b39713cd315e0a39b87`, and its decisions PO-1 to PO-3.
> Implementation: ALPHA-2B-T1 (`docs/ALPHA_2A_TASK_COORDINATOR.md` §9),
> implemented and tested offline only.

| # | Decision | What it narrows |
|---|---|---|
| PO-1 | Exactly **one** human-initiated correction round after an eligible round-1 result: a valid `changes_requested` review packet, or verification exit 2 with a valid `verification-failed` report and a trusted workspace. A reviewer verdict may make the round available; it never authorizes a model call, a file modification or a human approval. | §8's and §9's "Still not authorized: … a fixer; a review/fix loop", for this one round only |
| PO-2 | The supervised implementer request may carry one optional, bounded `correction` data object: the previous approved diff, AIDO-observed verification facts and the reviewer's findings, labelled untrusted data, never instructions or authority. Absent, the request is byte-identical to Alpha 2A. Round 2 needs a NEW, independently consented, single-use authorization; reusing the original is forbidden. | DEC-SUP item 3 / the P1A request contract (one file per request still holds: the correction describes the same one file) |
| PO-3 | The human operator may restore the one target file to its original Git baseline between rounds. AIDO never restores. AIDO preserves the round-1 evidence, explains that `git restore` discards uncommitted changes to the target, and independently verifies the clean workspace, original HEAD and original source bytes before preparing the next authorization. | the writer's "no rollback / restore" rules, which stay AIDO-scoped |

**Unchanged.** No autonomous approval, consent or write; no automatic retry
after a completed verdict; no third implementer round; DEC-SUP item 7 (zero
semantic and transport retries per authorization) still holds, because round
2 is a separately consented request, not a retry; one HTTP request per
authorization; the P1B ledger alone decides single use; the authorization,
writer, verifier, reviewer and RS1 contracts are unchanged; `SUP-D` earns no
qualification credit. No automatic Git write, commit, push, branch, reset,
stash, clone or deployment is authorized.

**Still not authorized:** a fixer that runs without a human decision; any
review/fix loop beyond the one round; patch generation by AIDO from findings;
an AIDO-performed restore; a second reviewer or fallback model; any live
correction round, which needs its own separately authorized live acceptance.


## 11. P0-UX amendment (D-2′) — interactive approval and consent

> **Appended amendment. §1–§10 above are unchanged and still in force,**
> except for the narrow exceptions recorded here.
>
> It records the Product Owner's acceptance of D-2′ (P0-UX1-FU1), subject to
> the H2 rule that the operator independently types the expected endpoint, at
> baseline `dc2222d2cebdf504a0362f7e7fb8e5457ab35090`.
>
> Implementation: P0-UX1-T1 (`docs/ALPHA_2A_TASK_COORDINATOR.md` §10). It is
> implemented and tested offline only.

| # | Decision | What it narrows |
|---|---|---|
| PO-UX-1 | The per-run consent may be made interactively at `task-approve` (D-2′).<br><br>**What the human does.** The human types `approve`, then the endpoint they expect as `scheme://host:port`. AIDO never displays it, prefills it, or derives it from the environment. `task-approve` reads exactly one environment value, `AIDO_LITELLM_BASE_URL`. It never reads the key and never displays the URL. It compares the typed value with P1B's own `check_live_endpoint`, and a mismatch records nothing.<br><br>**What AIDO serializes.** Only after every confirmation succeeds, and only inside `task-continue`, AIDO serializes the consent block:<br>- `consented_by`: the observed local account, not an authenticated identity;<br>- `consented_at`: AIDO's clock at the decision;<br>- `source: "manual"`;<br>- `binding_sha256`: from the bound section displayed, replacing the human echo;<br>- `consent_text`: the fixed phrase;<br>- the human-typed endpoint;<br>- `plaintext_acknowledgement`: if and only if it was separately confirmed. | §9 (P1B design §11): "human-completed consent", the typed consent phrase and the echoed binding digest. The endpoint stays typed by the human (A-2 unchanged). |
| PO-UX-2 | H2 needs separate explicit confirmations, in order:<br>- the consent decision, made on a disclosure of provider, model, the one file's path, size, digest and HEAD, the request's contents (including round-2 correction data), the request digest and the expiry;<br>- the typed endpoint;<br>- `transmit`, after the resolved destination and TLS status are shown;<br>- for `http`, `plaintext`, under a `NOT TLS-ENCRYPTED` banner.<br><br>Cancelling any of them records nothing. Transmission still happens only in `task-continue --transmit-approved-source --real-implementer`. | — |
| PO-UX-3 | Plan (H2 in DEC-SUP numbering, H1 in the coordinator) and diff (H6 / H3) approvals may be decided the same way. AIDO serializes `approved_by` (the observed account), `approved_at` (AIDO's clock), the fixed `approval_text` and `source: "manual"`.<br><br>`reject` is a recorded decision. It ends the task in round 1, or the correction round in round 2. Cancel records nothing. | D-2 ("approval stays a human file edit") and the docstring sentence "the orchestrator does not write this block" |

**Unchanged:**
- every strict parser, `Literal` and phrase constant;
- P1B's single environment read at run, and its run-time comparison of the
  endpoint with the consented one, which refuses before consumption;
- the 60-minute TTL and the `consented_at` window;
- single use, decided by the ledger;
- one request per authorization;
- `allow_insecure_http`;
- every PO-1 to PO-3 rule. Round 2 needs its own fresh authorization and its
  own decisions;
- the manual file-edit path;
- each stage's `task-continue` flags.

Decision records are write-once. They are bound to the run, the config, the
round, the stage and the exact draft bytes displayed, and they are
re-validated before any consequential action. A stale, mismatched, replayed
or unreadable record fails closed.

**Not claimed:**
- that the account name identifies a person;
- that a TTY proves a human is present;
- that a same-account process cannot forge a decision (A-19).


## 12. P0-RECOVERY-T2 amendment (2026-11-18) — supervised implementer reply envelope

> **Appended, prospective amendment. §1–§11 above are unchanged and still in
> force,** except for the narrow output-format exception recorded here. It
> records the Product Owner's approval, given with the P0-RECOVERY-T2 task at
> baseline `c6e992c4c4989118cabd0ebcd3e2e28b2df31e5d`, after the P0-RECOVERY-T1
> diagnosis. A1 was rejected as `post_image_unreachable`, but its exact cause
> is unknown because the rejected response content was not retained. A2
> produced an applicable diff containing a missing closing quote. The
> JSON-escaped full-file envelope is a plausible contributor, not a confirmed
> common root cause. Restoring the missing quote in A2 allowed its logic to
> pass the independent tests.
>
> Implementation: P0-RECOVERY-T2
> ([PHASE_ALPHA_P1B_SUPERVISED_IMPLEMENTER_LIVE.md](PHASE_ALPHA_P1B_SUPERVISED_IMPLEMENTER_LIVE.md)
> §"Reply envelope"). It is implemented and tested offline only.
>
> It rewrites no historical result: the A1/A2 runs, every qualification record
> and every earlier decision keep their recorded meaning.

| # | Decision | What it narrows |
|---|---|---|
| REC-1 | The supervised implementer's reply may use one of **exactly two** envelopes, chosen only by the project config field `supervised_implementer.output_envelope`. The match is exact and case-sensitive.<br>- `json_content_text` (default when absent) is the accepted one-key JSON object.<br>- `delimited_file` (opt-in) is the complete file as plain text between two fixed AIDO marker lines.<br><br>Both are strictly parsed and **rejected, never repaired**. The delimited parser trims, normalizes and appends nothing inside the markers. It tolerates whitespace only outside them, as the JSON parser does around its object.<br><br>The extracted text must end in the target's own uniform line ending, so an LF file needs its final LF. `delimited_file` cannot be combined with `structured_output`. A marker already present in the request refuses the run before anything is sent. | the DEC-SUP / P1A output contract ("exactly `{"content_text": ...}`") |
| REC-2 | PO-2's guarantee ("absent, the request is byte-identical to Alpha 2A") applies to the **default** `json_content_text` envelope. In that mode the JSON-mode instructions, the golden request digests and the default project-config serialization are unchanged. So the P1B project-config digest, and every authorization binding derived from it, is unchanged too.<br><br>The `delimited_file` envelope is explicitly identified and separately authorized:<br>- by the project config;<br>- through the existing H2 binding, since both `project_config_sha256` and `request_sha256` cover it;<br>- by the H2 display and the run banner, which name it;<br>- by the provenance, which records it. | §10 PO-2 (scope clarification only) |
| REC-3 | Evidence change is the smallest truthful one. Both provenance records gain one field, `output_envelope`: offline v1 at top level, and live v2 under `aido_requested`. The field is serialized **only** when it is not the default, so a default-mode record is byte-identical to its pre-amendment form, and an absent field means `json_content_text`.<br><br>No schema version is bumped. The run-outcome record is unchanged. A rejected reply is still recorded by digest and length only, with its failure category. | DEC-SUP item 6 / D-5 records |

**Unchanged:**
- `SUP-D` = `qwen3.8-27b` and its zero qualification credit;
- one request per authorization;
- zero semantic and transport retries, and no fallback;
- no token cap by default;
- D-9: no structured output on the live path;
- `SupervisedImplementerOutput`, the 5E3 diff generator, the post-image reachability proof, the 5F2C writer and every human approval (H1, H2, H3, and round 2's own);
- the ledger, the TTL and every PO-1 to PO-3 and PO-UX rule.

**Still not authorized:** any live request, including a smoke test; a new P0-UX3 run; a new model candidate or model substitution; retries, fallback or automatic code repair; output normalization; a third envelope; a CLI option for the envelope; structured output on the live path.


## 13. P0-MODEL-1 amendment (2026-11-23) — a second supervised candidate and explicit reviewer choice

> **Appended, prospective amendment. §1–§12 above are unchanged and still in
> force,** except for the narrow identity exception recorded here. It records
> the Product Owner's P0-MODEL-1 assignment at baseline
> `55239e1ac035e0c280ed309a6b55bace4f413d4f`. That assignment asked for
> MiniMax M3 as a separately identified implementer candidate and a separately
> selectable reviewer, with no automatic fallback or substitution.
>
> Implementation:
> [PHASE_ALPHA_P1B_SUPERVISED_IMPLEMENTER_LIVE.md](PHASE_ALPHA_P1B_SUPERVISED_IMPLEMENTER_LIVE.md)
> §10, with the handoff in [P0_MODEL_1_HANDOFF.md](P0_MODEL_1_HANDOFF.md). It is
> implemented and tested offline only.
>
> It rewrites no historical result. §2's autonomous candidate table, every
> qualification record and every earlier run keep their recorded meaning.

| # | Decision | What it narrows |
|---|---|---|
| MOD-1 | The supervised candidate registry is **append-only**. It now holds `SUP-D` = `qwen3.8-27b` (unchanged) and `SUP-M3` = `minimax-m3` (exact served id, matched exactly and case-sensitively).<br><br>`SUP-M3`:<br>- is outside `CANDIDATE_MODEL_IDS`;<br>- earns no qualification credit in either direction;<br>- is never an alias, substitute or fallback for `SUP-D`. | §8 item 2 and §9 "Unchanged" (`SUP-D` as the only supervised candidate) |
| MOD-2 | A project selects exactly one candidate by naming both `candidate` and `model` in its own `supervised_implementer` block. A mixed pair is refused.<br><br>The pair is bound at H2, through `project_config_sha256`, the bound `candidate`/`model` and `request_sha256`, and it is the `model` the one request carries.<br><br>Every strict record (authorization, offline and live provenance) refuses a mixed pair. A reply naming another model is rejected as `model_substitution`. | — |
| MOD-3 | The reviewer may be explicitly configured as `minimax-m3` through the existing `controlled_review.model`. Nothing about the reviewer contract changes, including its strict parser, RS1 and egress authority. `gpt-oss-20b` stays the operational default until role evidence supports a change. | — |

**Unchanged:**
- every DEC-SUP, DEC-SUP-LIVE, PO, PO-UX and REC decision;
- the `litellm`-only live provider (D-2);
- D-9: no structured output on the live path;
- one request per authorization, with zero semantic and transport retries;
- no token cap by default;
- the ledger and the TTL;
- every human approval;
- every schema version.

A `SUP-D` config, request or record serializes byte-identically.

**Not claimed:**
- that `minimax-m3` is qualified for any role;
- that listing an alias proves the backend's weights, quantization or
  reasoning configuration.

**Still not authorized:**
- any live request with either model;
- using one model as both implementer and reviewer on an initial acceptance
  task;
- automatic model selection, fallback, failover or substitution;
- a CLI model option;
- streaming;
- any change to LiteLLM, Run:AI or cluster settings.
