# ALPHA-P1A — DEC-SUP: Supervised Implementer Decision Proposal

> **DECIDED 2026-10-14 — OPTION A APPROVED** by the human/architect:
>
> - policy §3 is amended for a supervised `SUP-D` role with **no
>   qualification credit**;
> - the recommended answer is adopted for items 2–7 and 9 in §6. Item 8
>   (`CLAUDE.md`) had no recommended option and received no separate answer,
>   so **no `CLAUDE.md` modification is authorized** and the existing non-goal
>   staleness remains acknowledged (ALPHA-P1A-FU1 correction);
> - ALPHA-P1A proceeds **offline and library-only** per §5.
>
> The decision is recorded in
> [AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md](AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md)
> §8. It authorizes **no live request, no real client construction, no CLI
> command, and no real-workspace write**. The text below is the proposal as
> written, preserved unchanged.

> **DECISION PROPOSAL ONLY. AUTHORIZES NOTHING.**
>
> ALPHA-P1A asked for an offline foundation for a Qwen 3.8 (`qwen3.8-27b`)
> supervised Implementer, with the instruction: *if existing governance
> requires a new DEC-SUP decision first, produce the minimal decision proposal
> and stop at that authority boundary.* Governance requires it (§2). This
> document is that proposal, and P1A stops here.
>
> In the turn that wrote it: **no code was changed**, no test was added, no
> module, config field, CLI command or option was created, nothing was added to
> `CANDIDATE_MODEL_IDS`, no model request was made, no credential or environment
> value was read, no socket was opened, no source was transmitted, no target
> workspace was touched, the closed Alpha-0 run directory was not touched, and
> `CLAUDE.md` was not modified. **P1A is NOT complete.**

| | |
|---|---|
| Kind | Governance decision proposal (DEC-SUP) |
| Recorded | 2026-10-14 |
| Base commit | `39d81ba` (working tree also carries the uncommitted Alpha-0 runbook and F5A docs) |
| Authorizes | **Nothing** |
| Decides | **Nothing** — every item in §6 is for the human/architect to decide |

---

## 1. Current authoritative state

### 1.1 Implementer candidates

From [AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md](AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md)
§2 and the roadmap's 2026-09-24 CURRENT OPERATIONAL STATUS block:

| Candidate | Exact model id | Authoritative status |
|---|---|---|
| A | `qwen3-coder-next` | IMPLEMENTER NOT_QUALIFIED / frozen (Category-B compatibility only) |
| B | `minimax-m2.7` | IMPLEMENTER NOT_QUALIFIED / frozen (Category-B compatibility only) |
| C | `qwen3.6-27b` | Q3 identity/design exists; live qualification **NO-GO** |
| D | `qwen3.8-27b` | **PLANNED only.** No qualification credit, no live authorization, **not** in the production registry; "requires its own future design, implementation and live authorization" |

The code registry agrees:
`experiments/pi_implementer_qualification/qualification/records.py`
`CANDIDATE_MODEL_IDS = {"A", "B", "C"}`. D is absent, and this proposal does not
add it.

- **The frozen hard bar** is
  [PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md](PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md)
  §16. It qualifies the role *autonomous Pi implementer*. §20 Step 5: if no
  candidate clears it, "do not lower the safety or correctness bar … design
  either a separate next candidate round **or a supervision policy**."
- **No implementer is qualified.** No supervised-implementer policy exists. The
  string `DEC-SUP` appears in no document before this one.
- **Model discovery is not capability.** An authenticated HTTP 200 from
  `/v1/models` listing `qwen3.8-27b` proves that the endpoint routes that id. It
  proves nothing about implementer capability.
- **Operating experience from other products earns no credit.** Use of
  `qwen3.8-27b` on Product Intelligence and B300 Forecast is "motivating
  operational experience only" (policy §2) and "grants **zero** qualification
  credit" (policy §4).

### 1.2 Shipped L2 chain (what a supervised implementer would feed)

```text
approved-plan (5B, H2 exact phrase)
  → l2-read-workspace-files (5D2: bounded, redacted, printed packet)
  → proposed-content.v1   ← Alpha-0: externally supplied (the slot P1A targets)
  → generate-diff-proposal (5E3: difflib, pre/post SHA-256)
  → approved-diff (5F0, H6 exact phrase)
  → l2-apply-approved-file-edit (5F2C) → verify (5F2D) → review (5F2E…V2) → human
```

`build_deterministic_diff_proposal` already enforces exact identity, an L1-only
plan, scope narrowing (`files_likely_to_change` minus
`files_forbidden_or_out_of_scope`), refusal of redacted source, a secret-pattern
check, and pre-image/post-image digests. The writer re-pins both digests against
disk.

### 1.3 Alpha-0 (as reported, not re-observed here)

The P1A prompt reports that Alpha-0 completed its bounded workflow: a
human-approved plan, implementation content supplied externally by Claude Code,
AIDO's deterministic diff and approved write, verification (3 passed), a
Nemotron review returning `approve`, and human acceptance with evidence closure.

**Deviation, recorded honestly:** at H10 the operator chose **ACCEPT with the
target clone left dirty**. The runbook
([ALPHA0_CMD_RUNBOOK.md](ALPHA0_CMD_RUNBOOK.md) Step 10) offers only **COMMIT**
(§10.1) or **RESTORE** (§10.2). Alpha-0 therefore did not end in either
runbook-specified final state. Policy §5's Alpha definition requires a
"mechanically proven final/cleanup state", and that criterion was met only in
the sense that the final state was *recorded*. It was not committed or restored.

This session did not read, open or modify the Alpha-0 run directory. The facts
above come from the prompt.

---

## 2. Verdict: P1A implementation is blocked by frozen governance

Five authorities, read together, require a decision before any supervised
implementer code lands. The first two are dispositive.

| # | Authority | Text | Contradiction with P1A |
|---|---|---|---|
| **C1** | Policy §3, steps 2–5 | C is next. D is next "if C FAILS". "If C and D both FAIL … a separate supervised-implementer policy/design decision is opened." | Neither C nor D has run. P1A opens the supervised-implementer branch **two sequencing gates early**. That is a change to the policy's ordering, not something done under it. |
| **C2** | Qualification design §20 Step 5 (frozen) | A supervision policy is designed **after** "neither clears" the hard bar. | Same ordering, frozen at the design level. |
| **C3** | Policy §2, row D | D "requires its own future design, implementation and live authorization." | No D design exists. P1A would implement before any design. |
| **C4** | L2 design §9 | "Any model-backed L2 needs a separate design and a separate gate. Its own design document, its own project config block, its own flag, its own command." Source-context transmission "must be answered *before* a model-backed L2 is designed." | No such design exists, and the source-transmission question is unanswered. The shipped reviewer may send **never the full target file**. An implementer needs exactly that. |
| C5 | `CLAUDE.md` | "Do **not** implement … a model-backed implementer"; "nothing else may call a model" outside three gated commands. | The P1A prompt is an explicit prompt, so on its own C5 could arguably be satisfied. But P1A also forbids modifying `CLAUDE.md`. Landing a model-backed implementer would leave the operating guide asserting a false non-goal, which is a lifecycle-truthfulness defect. |

The policy itself states the bar for this situation: "Changing a frozen
dependency requires a separate, explicit architecture decision" (§6), and the
closure rule "never permits weakening … a frozen authority boundary" (§1).
Implementing P1A now would reorder the policy without recording a decision to do
so. Section 2 of the P1A prompt itself says to stop and name the contradiction
in that case, not to rewrite the rule silently.

**Not a contradiction:** a *supervised* implementer is not barred by the hard
bar itself. The hard bar governs *autonomous* qualification. A path in which a
human approves the exact diff before any write is a different role policy. DEC-SUP
can therefore authorize it **without lowering the hard bar**, but only by saying
so explicitly.

---

## 3. Pre-implementation adversarial analysis

This analysis covers each authority-bearing object a supervised implementer
would touch. "Observed" means AIDO checks it mechanically. "Convention" means it
holds only if callers behave.

| Object | Creator / mutator | Provenance established by | Bypass or disagreement risk | Validated at consumption? |
|---|---|---|---|---|
| Approved plan (5B) | Human-typed approval of the exact phrase | Strict parser + exact phrase + identity match | Plan paths are model-chosen strings (L2 §12). They are requests to validate, never authorizations. | **Observed** (5E3 rechecks L1 level and identity) |
| Project config | Operator file | Loader + strict model | The wrong `--project-config` is caught by exact identity match | **Observed** |
| 5D2 content packet | `l2-read-workspace-files` stdout, **saved by the operator** | Mode/flag literals + identity match. **No binding to the read invocation.** | **F-3**: a hand-edited packet passes validation. The writer's disk pre-image check stops a *wrong write*, but nothing stops *transmission* of whatever text the packet holds. | Shape: observed. Origin: **convention** |
| Implementer request | (future) AIDO | (future) built only from in-scope, unredacted `read` items | **F-4/F-5**: full-file source over the transport; redaction is a backstop, not a guarantee | — |
| Model response | Untrusted model | None. It is data. | Path, change type, review flag or extra fields could be asserted by the model | Must be a strict parser that rejects and never repairs |
| proposed-content.v1 | Today: any supplier | Strict schema. **Records no author.** | **F-1**: the downstream diff artifact says `engine: deterministic`, `real_call: false`, `model: null`. That is true of the *diff generator*, but a model-authored change becomes indistinguishable from a human-authored one. | Shape: observed. Authorship: **not recorded** |
| Diff artifact (5E2/5E3) | `build_deterministic_diff_proposal` | Digests over the exact bytes | **F-2**: supplier prose (`rationale`, `risks`, `assumptions`, `open_questions`) is copied verbatim into the artifact the human approves. Model-authored persuasion would sit inside the approval surface. (Verified: the reviewer prompt does **not** include change rationale, only plan prose and the diff.) | **Observed** |
| Approved diff (5F0) | Human, exact phrase, `source: "manual"` | Strict parser, wraps the artifact | No model path can author it: the approval phrase is human-typed | **Observed** |
| Workspace write | 5F2C writer only | Pre/post SHA-256, clean tree, HEAD, opt-in, two flags | The implementer gets no write capability. Its content reaches disk only through 5E3 → H6 → 5F2C | **Observed** |

Further findings that DEC-SUP must settle:

- **F-1 (authorship laundering, material for truthfulness).** Without a separate
  record, model-authored content enters the L2 chain under artifacts whose
  provenance truthfully names only deterministic tools. A human at H6 cannot
  tell from the artifacts that a model wrote the change.
- **F-2 (approval-surface injection).** Model prose reaches the H6 approval
  artifact verbatim.
- **F-3 (packet origin is convention).** The shipped reviewer set the precedent:
  "no saved report is trusted as authority". It runs the verifier itself. The
  analogous rule here is for the implementer to perform the 5D2 bounded read
  **in-process** rather than consume a saved packet. The 5D2 read currently lives
  inside `cli.py` (`_run_l2_read_workspace_files`), so reusing it needs a narrow
  extraction, not a second reader.
- **F-4 (full-file egress).** This is a new data-egress class. Redaction-refused
  files must be refused **before** any request is built. A file that passes
  redaction is still not proven secret-free.
- **F-5 (plaintext transport).** The operator's internal endpoint is plaintext
  HTTP. The shipped insecure-HTTP refusal applies **only** to the vLLM reviewer
  provider. A LiteLLM-shaped implementer path would send full source files over
  plaintext with no acknowledgement gate unless DEC-SUP requires one for every
  provider.
- **F-6 (writer domain).** `proposed-content.v1` permits `create`. The writer
  supports `modify` only. AIDO, not the model, must fix `change_type: modify`.
- **F-7 (truthiness).** The existing models use `Literal[True]`/`Literal[False]`
  and exact-string `Literal`s, so Python truthiness does not fail open on the
  shipped path. A new response model must follow the same pattern: no `bool`
  fields a model can set, and no defaults that grant anything.

---

## 4. Options

| Option | What it means | Cost |
|---|---|---|
| **A. Authorize a supervised-implementer branch now, in parallel** | Amend policy §3: a *supervised* (proposal-only, human-approved-diff) implementer role may proceed for D before C/D autonomous qualification. The hard bar is unchanged, and the role earns no autonomous credit. | Requires the explicit amendment in §6 |
| B. Keep sequencing: qualify C first | C live qualification needs its own authorization, behind the CFG1 / pre-A4 chain (A4 NO-GO) | Longest path to replacing the manual supplier |
| C. Qualify D autonomously first | D design, `CANDIDATE_MODEL_IDS` addition, and live authorization under the frozen harness | Same long chain, and it skips C contrary to §3 step 2 |

**Recommendation: A.** Alpha-0 showed that the human-gated L2 chain works with
an untrusted external supplier. In option A the model *replaces that supplier*
and changes no gate. Safety rests on H2/H6/H7, digest pinning and the single
writer, not on the model clearing the autonomous bar. Policy §1's closure
discipline favours end-to-end product progress. Option A is acceptable **only**
if DEC-SUP says in writing that it lowers no bar, grants no qualification credit,
and authorizes no live run.

---

## 5. Proposed P1A shape, if DEC-SUP is approved

This section is a design sketch, not an implementation. It shows the minimum
that would satisfy P1A's acceptance criteria.

```text
library only (no CLI command, no real client construction in P1A):

build_supervised_implementer_request(approved_plan, project, read_item, path)
    path    ∈ plan.files_likely_to_change, ∉ files_forbidden_or_out_of_scope
    item    status == "read", kind == "file", redacted is False   (else refuse pre-request)
    exactly one path, modify only
    → LLMRequest(model = config.model, max_tokens = None, response_format = generated schema)

parse_supervised_implementer_response(text)          strict; reject, never repair
    → { content_text }  only (no path, no change_type, no flags)

assemble_proposed_content(path, content_text)        AIDO-authored wrapper
    path / change_type="modify" / requires_human_review=True / rationale = fixed AIDO prose
    → ProposedContentInput  → existing build_deterministic_diff_proposal  → STOP (H6)

implementer-provenance sidecar (new, separate artifact)
    role="supervised_implementer", candidate="SUP-D", model="qwen3.8-27b",
    provider, endpoint_scheme, request/response content digests,
    pre_image_sha256, proposed post_image_sha256, attempts=1, retries=0
```

- **Identity:** a new supervised-candidate identity (for example `SUP-D`) bound
  to `qwen3.8-27b`, kept **separate from** `CANDIDATE_MODEL_IDS`. Frozen A/B/C
  are untouched, and no autonomous-qualification record can reference it.
- **Transport:** reuse `LLMClient` with `max_retries=0`. The provider is exactly
  `litellm` or `vllm`, matched exactly. The endpoint and key come from the
  environment only, the model from config only. Plaintext requires an explicit
  acknowledgement opt-in for **both** providers. The real endpoint is never
  written into code or docs.
- **No retry, no fallback:** one semantic request in P1A. Any failure is
  terminal. A future RS1-style bounded retry would need its own decision.
- **Token policy:** unchanged. No `max_tokens` is sent unless an operator sets
  a positive cap.
- **Tests:** synthetic `tmp_path` repos and `httpx.MockTransport` only. Bypass
  tests would cover a model-asserted path or change type, extra fields, fenced
  JSON, an out-of-scope path, a redacted item, mismatched identity, an altered
  digest, post-validation mutation (frozen models), and transport failure with
  zero retries.

---

## 6. What DEC-SUP must decide (minimal)

1. **Sequencing.** Adopt option A (amend policy §3) or keep B/C.
2. **Role identity.** `supervised_implementer` as a role distinct from the
   autonomous implementer. Candidate `SUP-D` = `qwen3.8-27b`, outside
   `CANDIDATE_MODEL_IDS`, with no qualification credit in either direction.
3. **Source transmission (L2 §9, F-4).** Authorize sending **one** in-scope,
   unredacted, cap-bounded file per request, announced in a stderr banner naming
   the file. Full-repository and multi-file transmission stay forbidden.
4. **Read provenance (F-3).** In-process 5D2 read (recommended) or saved packet.
5. **Plaintext (F-5).** A required acknowledgement opt-in for every provider,
   shipping `false`, worded as an acknowledgement and never as a security claim.
6. **Authorship (F-1, F-2).** A separate implementer-provenance sidecar, and
   AIDO-fixed `rationale` prose in the diff artifact (model prose shown to the
   human only in the sidecar), versus a diff-proposal schema bump.
7. **Retry policy.** Zero semantic retries for P1A (recommended).
8. **`CLAUDE.md`.** Authorize the implementing phase to update the non-goal
   lines it would falsify, or accept the documented staleness.
9. **Scope of P1A.** Library-only and offline. No CLI command, no real client
   construction, no live request.

## 7. Conditions for the first live Qwen 3.8 supervised pilot

These all come **after** DEC-SUP and an accepted offline P1A:

- a separate live-pilot authorization naming the model, provider, transport
  scheme and plaintext acknowledgement;
- a dedicated, disposable clean clone of a low-risk repository: never a real
  working checkout, and never the Alpha-0 clone;
- one file, `modify` only, from an H2-approved plan;
- a per-run consent flag for source transmission, plus the banner;
- H6 exact-diff approval, then the unchanged 5F2C/5F2D/5F2E gates and their own
  consents (H7/H8/H9);
- an H10 that ends in COMMIT or RESTORE, unlike Alpha-0;
- evidence that records what AIDO observed (digests, exit codes, HEAD, status)
  and treats any model claim as non-evidence;
- an explicit statement that the pilot qualifies nothing.

## 8. Recommended next phase

**DEC-SUP review and decision** (human/architect). If option A is chosen, then
**ALPHA-P1A (offline, library-only)** as sketched in §5.

Suggested Claude Code setting: **Opus, high effort**. The work is small in code
but authority-dense, and needs careful bypass testing.
