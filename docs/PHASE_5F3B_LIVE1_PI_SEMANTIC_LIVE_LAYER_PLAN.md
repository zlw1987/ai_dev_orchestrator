# Phase 5F3B-LIVE1 — Pi semantic live adapter + sweep runner — PLANNING NOTES

> **DESIGN / PLANNING ONLY. THIS DOCUMENT AUTHORIZES NOTHING.**
>
> It creates no module, no adapter, no entry point, no config field, no CLI
> command, no schema, and no run. It does not authorize `5F3B-LIVE1-DESIGN`,
> `5F3B-LIVE1-I1`, `5F3B-Q1`, `5F3B-Q2`, any Pi/Node launch, any broker or named
> pipe, any credential read, any B300 contact, or any semantic prompt. Each of
> those needs its own explicit prompt.
>
> **No live activity of any kind occurred in the turn that wrote this file.**
> Semantic prompts sent: **0**.

| | |
|---|---|
| Kind | Phase planning notes (pre-design) |
| Created | 2026-09-02, after the Q1 execution attempt recorded in §1 |
| Milestone | M2.5, inserted between M2 and M3 |
| Canonical sequencing | [`AIDO_RUNTIME_HARNESS_ROADMAP.md`](AIDO_RUNTIME_HARNESS_ROADMAP.md) §4.5 |
| Live activity | **None** |
| Authorizes | **Nothing** |
| Status | NOT YET IMPLEMENTED; not yet designed |

This file exists so that the M2.5 insertion has somewhere to grow into without
touching any frozen document. Where it and the roadmap disagree, **the roadmap
is canonical** and this file is the error.

---

## 1. The originating fact

A controlled attempt to execute `5F3B-Q1` stopped **before any semantic attempt
was invoked**:

```text
Q1 execution attempt:       BLOCKED BEFORE ATTEMPT
semantic prompts sent:      0
semantic dispatch attempts: 0
Candidate-A task attempt:   NOT CONSUMED
Q1 candidate result:        NONE
```

Nothing was spent. No dispatch adapter was called, no send state was
established, no one-shot attempt was consumed, and no qualification or attempt
artifact was produced. This is **not** a Q1 FAIL, **not** an indeterminate
dispatch, and **not** a candidate result.

The blocker was established mechanically from the repository:

- `5F3B-Q1-PRE1` froze the semantic **orchestration** around four **injected**
  ports — `dispatch_semantic_prompt`, `observe_semantic_turn`,
  `collect_broker_activity`, `collect_final_report_claims` — and the repository
  contains **no real implementation of any of them**;
- there is **no live Q1/Q2 sweep entry point**. `run_primary_sweep` is frozen
  and has no non-test caller;
- the existing live entry point drives the **zero-prompt Category-B** attempt
  only.

Injected ports are a design boundary, not an implementation. M2 delivered
orchestration; M3 assumed a seam that was never built.

---

## 2. What LIVE1 is

> **LIVE1 connects already-frozen orchestration to an already-frozen runtime
> seam. It decides nothing.**

Its only role is to bind PRE1's four semantic ports to the real Pi runtime seam
and to provide one deliberately explicit live sweep entry point.

It does **not** redefine, reopen, reinterpret, extend, relax or tune:

```text
the qualification corpus            run validity
task prompts                        the hard bar
dispatch semantics                  ranking
prompt count policy                 record schemas
outcome taxonomy                    evidence policy
workspace policy                    verification authority
candidate routes                    Category-B policy
                    real-workspace authority
```

If the implementation appears to require changing any of those, that is a
**finding to report**, resolved by review under its own prompt — never by an
adjustment made inside LIVE1.

---

## 3. Sequencing

```text
5F3B-LIVE1-DESIGN
    source inspection of the real Pi prompt/response and event seam,
    plus the exact live semantic seam design
    ZERO live activity

5F3B-LIVE1-I1
    implementation of the real Pi semantic adapter and live sweep runner
    synthetic / offline tests ONLY
    ZERO semantic prompts

independent adversarial review  (+ correction phases if required)

5F3B-LIVE1  ACCEPT / FREEZE

then a NEW, EXPLICIT authorization for:
    5F3B-Q1 — Candidate A actual live sweep

    Q2 (Candidate B) remains SEPARATELY authorized; Q1 acceptance is not Q2
    authorization, and neither result informs the other.
```

Freezing LIVE1 is an infrastructure acceptance, exactly as PRE1's was. It
authorizes a live attempt to be *requested*; it never authorizes the attempt.

---

## 4. Responsibilities LIVE1 must eventually discharge

Recorded at architecture level only. Exact shapes are `5F3B-LIVE1-DESIGN`'s job.

1. **Phase-1 semantic prompt dispatch** against Pi's *correlated
   prompt-response* seam, preserving the frozen three-way send state exactly:
   `CONFIRMED_NOT_SENT` | `CONFIRMED_SENT` | `SEND_STATE_INDETERMINATE`. The
   send fact may be established only by a returned, well-typed,
   provenance-matched observation carrying a bounded evidence code — never by
   having called a function, and never by an exception. Prompt-count truth is
   fixed once, in phase 1, and is never rewritten downstream.
2. **Phase-2 turn observation**, in which **`agent_settled` is completion** and
   **`agent_end` alone is not completion**. `agent_end` may recur and may carry
   a retry flag; it must never be promoted into a settle.
3. **Broker-activity collection from the same run/session** the semantic turn
   ran in — never a second session, never a reconstruction.
4. **Bounded, optional final-report-claims collection**, remaining
   **non-authoritative** and never gating. A runtime's self-report is a claim to
   be audited, not evidence.
5. **Live assembly** of the frozen PRE1 controller and sweep with the existing
   live compatibility / route / resource primitives, reused unmodified — never
   forked into parallel versions.
6. **One deliberately explicit live sweep entry point** that cannot silently run
   Q2, another candidate, another route, or a real workspace.
7. **The same execution path for Candidate A and Candidate B**, differing only in
   the frozen candidate / model / route identity.
8. **The existing unlimited AIDO output-token policy**, unchanged:
   `aido_requested_max_output_tokens = null`, `maxTokens` omitted entirely.
   `null` means *AIDO requested no cap* — never `0`, `-1`, or "unlimited".
9. **No semantic retry, no continuation, no fallback** model, provider or route.
10. **Fresh synthetic workspace, runtime, broker, session and capability per
    task**, with no state carried between tasks.
11. **A same-run Category-B-equivalent compatibility PREFIX before each
    semantic task**, never inherited from an earlier frozen result: the SAME
    frozen 13 `CompatibilityFacts` (§5) must be re-established, on the SAME
    live runtime/broker session that will go on to receive the semantic
    prompt, before that prompt is dispatched.

    **This does NOT mean invoking `run_category_b_controller` before the
    semantic task.** That controller is one atomic, zero-prompt function: it
    establishes Category-B compatibility and unconditionally tears the runtime
    and broker down before it ever returns — correct for Category-B, which
    sends zero prompts by definition, but it exposes no not-yet-torn-down
    session to hand off, because closure is baked into that one function body.
    A semantic task instead reuses the frozen `CompatibilityFacts` shape and
    the same lower-level typed/resource primitives through the semantic
    controller's own orchestration — never the whole Category-B controller as
    a pre-gate that would close the session before a prompt could be sent.
    There is exactly one set of 13 compatibility facts; LIVE1 does not invent a
    second compatibility policy.
12. **The exact cleanup and evidence order already frozen by PRE1**, and exactly
    one retained artifact per invoked attempt — never zero, never two.

---

## 5. Boundaries

- **LIVE1 is Pi-specific.** No generic `AgentRuntime` / `Harness` interface, no
  harness registry, no plugin seam, no capability list, and no generalization of
  PRE1 for Codex or the DeepSeek Harness. The minimum generic harness contract
  stays deferred to M7, until real Pi semantic qualification has produced
  observed evidence of what the seam actually had to provide.
- **`LiveCategoryBAdapters` is intentionally zero-prompt.** It must not simply
  be widened into a semantic adapter in a way that destroys its accepted
  Category-B structural contract. How the semantic ports are supplied without
  damaging that contract is a **`5F3B-LIVE1-DESIGN` question**, deliberately
  left open here.
- **The four-axis model is preserved:** `ROLE / HARNESS / MODEL / BACKEND`.
- **The control/authority stack is preserved:**

  ```text
  AIDO control plane
      -> Pi harness/runtime
          -> B300 provider/backend
              -> candidate model
  ```

  AIDO remains the authority over workspace, operation authorization,
  candidate/route selection, the credential boundary, verification, evidence and
  the qualification verdict. **Pi remains an untrusted agent-loop runtime.**
  Adding a semantic path into it does not make it trusted — it makes the
  untrusted surface *reachable*, which is why the gating, bounded observation
  and non-authoritative self-report rules above are load-bearing.

---

## 6. Standing authority

```text
5F3B-Q1-PRE1                ACCEPTED / FROZEN
Candidate A Category-B      QUALIFIED / FROZEN   (compatibility only)
Candidate B Category-B      QUALIFIED / FROZEN   (compatibility only)
5F3B-LIVE1 (M2.5)           NOT YET IMPLEMENTED
Q1                          NO-GO
Q2                          NO-GO
Real workspace              NO-GO
```

**No semantic prompt has ever been sent, and no candidate implementer PASS/FAIL
exists.** Category-B is compatibility qualification only and is never a
candidate PASS.

---

## 7. What this document does NOT authorize

- Implementing LIVE1, its adapter, its ports, or its entry point.
- `5F3B-LIVE1-DESIGN` or `5F3B-LIVE1-I1` — each needs its own prompt.
- Q1, Q2, or any part of either.
- Launching Pi or Node, opening a broker or named pipe, reading any credential,
  contacting B300, or sending any prompt.
- Modifying qualification runtime code, tests, or any frozen AR1 / AR2 / AR2-O1 /
  I1 / I2 / I2B / PRE1 module.
- Widening `LiveCategoryBAdapters`, or reopening the accepted Category-B
  structural contract.
- Any generic harness abstraction, registry, or routing surface.
- Real-workspace or sibling-project authority.
- Rewriting frozen historical qualification or design documents.
- Commits, pushes, branches, or PRs.
