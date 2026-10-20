# ALPHA-1A — DEC-ALPHA1 Minimal Supervised Alpha Authorization Design

> **FINALIZED PROPOSAL (2026-10-20) — NOT AUTHORIZED.**
>
> This is a decision proposal. It authorizes nothing. No model was called, no
> endpoint was contacted, no clone was created, no verification or review was
> run, and no workspace was touched while writing it. AIDO `src/`, the Alpha-0
> helper, the Alpha-0 runbook and `CLAUDE.md` are unchanged by it.
>
> Every decision in §12 needs explicit operator assent. ALPHA-1B can run only
> after (1) the operator approves DEC-ALPHA1 (§12, OD-1..OD-5), (2) the operator
> fills AUTH-ALPHA1B-01 (§2.3), and (3) each per-run human boundary in §5 is
> completed by a human at the moment it is reached. Committing this document
> does **not** authorize ALPHA-1B.

> **REVISION HISTORY.**
>
> - **2026-10-19, first proposal** (baseline `38081af`). Verdict
>   READY_FOR_HUMAN_DECISION, conditional on D-5.
> - **2026-10-19, review outcome:** D-5 was answered IMPLEMENTATION_REQUIRED.
>   Procedural endpoint inspection plus `NO_PROXY=*` was not accepted as a
>   source-egress guarantee.
> - **ALPHA-1A-FU1 / FU2** implemented the correction as
>   [ALPHA_1A_FU1_REVIEWER_EGRESS_AUTHORITY_CONTRACT.md](ALPHA_1A_FU1_REVIEWER_EGRESS_AUTHORITY_CONTRACT.md)
>   (FU1 at `5a38a67`, FU2 at `44bf3be`).
> - **Independent GitHub review ACCEPTED FU1/FU2 at
>   `44bf3be05195a4fc050de7f0cad2407795d7c9b8`.** No FU3 is needed.
> - **2026-10-20, this finalization** applies the FU1 contract §10 amendments
>   and the FU2 correction to this document, replaces the obsolete procedural
>   D-5 control, re-pins the source baseline, and reconciles ALPHA-1B with the
>   existing Alpha-0 helper and preflight (§4). That reconciliation found one
>   material blocker (B-1, §4.3). Nothing else was reopened.
> - **2026-10-20, final helper compatibility and closure correction.** The
>   operator approved OD-2. An independent review of `dc807f4` found three narrow
>   issues, all closed here and in `docs/alpha0/`: **B-1** the helper now
>   recognizes exactly `review-packet.v4` and `review-packet.v5` (helper and tests
>   only); **B-2** S12 now writes the closure record **before** `inventory`, and
>   `inventory` is the last writer to the run directory (§5.3); **B-3** this
>   pilot allows exactly **one** H9 review-command invocation (D-9, §6.2).
>   DEC-ALPHA1 is still a proposal. OD-1 and OD-3..OD-6 are not decided.

| | |
|---|---|
| Kind | Authorization and integration design (documentation only) |
| Recorded | 2026-10-19; finalized 2026-10-20 |
| AIDO source pin (`aido_source_commit`) | `44bf3be05195a4fc050de7f0cad2407795d7c9b8` (ALPHA-1A-FU1 `5a38a67` + FU2 `44bf3be`). Applies to `src/` and `pyproject.toml`. **Subject to a fresh exact-HEAD and source-pin check at S0** (§4.1) |
| Preceded by | ALPHA-P1D Write-and-Verify Pilot (ACCEPTED, CLOSED); the ALPHA-1 readiness assessment (directionally accepted, scope not approved); ALPHA-1A-FU1/FU2 (ACCEPTED) |
| Readiness assessment | Not present in this repository. It is addressed through the corrections listed in the ALPHA-1A brief |
| Verdict | **READY_FOR_HUMAN_DECISION**. B-1, B-2 and B-3 are closed (§4.3, §5.3, D-9). No material blocker remains (§11) |

ALPHA-1B would be **one separately authorized, human-supervised pilot**. It does
not complete M4, M5A, M5 or M6, and it does not make AIDO v1 complete.

**Identities stay distinct and neither earns credit.** The Implementer is
`SUP-D` (`qwen3.8-27b`) in the `supervised_implementer` role. It stays
unqualified for the autonomous Implementer role. The Reviewer is a different,
operator-named model in the reviewer role, and gets no qualification credit from
this pilot either. Every frozen hard bar, candidate history and roadmap
dependency is unchanged.

---

## 1. Summary

The shipped commands, the Alpha-0 helper and the ALPHA-P1C/P1D operating
pattern already cover the whole chain. ALPHA-1B joins two procedures that have
both been accepted:

- **P1C, steps 1–7:** the live supervised implementer up to H6;
- **Alpha-0 runbook, steps 3–10:** write, verify, review, and commit or restore.

The two procedures run in **one run directory, against one clone, under one
config and one approved plan**.

Four hazards had to be closed before a truthful end-to-end claim is possible.
Three are closed by an operating control. **HB-2 is now closed by shipped,
independently accepted code.**

| # | Hazard | Why it matters | Control |
|---|---|---|---|
| HB-1 | **Verification imports the wrong copy.** The AIDO venv has an editable install whose `.pth` puts `C:\dev\ai_dev_orchestrator\src` on `sys.path`. Plain pytest run in a clone of AIDO itself imports the **runtime checkout**, not the clone's written file | A `verified` outcome would test unmodified code and say nothing about the approved change | The verification argv proves where the module was imported from, and checks the acceptance rule itself (§7, D-7) |
| HB-2 | **The reviewer destination had no AIDO-enforced pre-transmission binding, and the reviewer client inherited environment and Windows-registry proxies** | Source-derived code could go to, or through, a destination nobody authorized | **Closed in code by ALPHA-1A-FU1/FU2 (accepted at `44bf3be`).** `controlled_review.endpoint` authorizes scheme, host, port and base path in the pinned per-run config. AIDO checks it before any client exists and again on **every** outbound request, and the production transport is direct (`trust_env=False`). See §6 |
| HB-3 | **An old approval can be replayed.** The writer, verifier and reviewer bind an approval to `project_id`, `repo`, the plan and the pre-image. They do not bind it to a run, a clone or a time. ALPHA-1B can reuse the P1C/P1D target at the same pre-image | An approved diff from P1D could pass AIDO's checks in the new run | A `project_id` never used before (D-2) |
| HB-4 | **The H10 commit runs the operator's Git.** The unsandboxed verification ran twice beforehand. It could have planted `.git/hooks/*`, `.git/config` keys or `.git/info/attributes` filters. Neither AIDO's postcondition nor the helper snapshot inspects those | A planted hook or filter would run with the operator's full environment | Record `.git` hook, config and attributes state after cloning, compare it before H10, and commit with hooks disabled (§5, S11) |

## 2. DEC-ALPHA1 decisions requiring operator assent

### 2.1 Decisions

Each row needs an explicit answer (§12). The recommended option is listed first.

| # | Decision | Recommended | Alternatives |
|---|---|---|---|
| D-1 | **Repository, target and step** | `zlw1987/ai_dev_orchestrator`, `src/ai_dev_orchestrator/github/issue_parser.py`, task 9101 (fence rule, P1C §2.1, unchanged). It has been validated offline twice. The fix is not on `main` (the file has no fence handling). It is low sensitivity: pure parsing with no I/O. The verification already exists (`tests/test_issue_parser.py`). FU1/FU2 changed only the reviewer path, so the target and its tests are unaffected | A different file or repository. That needs new eligibility, plan and verification preparation, which costs at least one more iteration |
| D-2 | **Identity and layout** | `project_id: aido-alpha1b-r01`. The operator confirms it was never used by P1C, P1D or Alpha-0. Clone `C:\aido_alpha1b_ws\r01`, new. Run directory `C:\aido_alpha1b_runs\r01`. Evidence at `<run dir>\evidence`. The **existing persistent ledger** `C:\aido_p1c_ledger\supervised_implementer` (the one the P1C live run used) is reused, so that every spent run id stays in one place | A new ledger directory. That is allowed, but the old one must still be kept |
| D-3 | **Baseline and source pin** *(amended per FU1 §10)* | The helper is run with `--verified-commit 44bf3be05195a4fc050de7f0cad2407795d7c9b8`. That pin covers `src/` and `pyproject.toml` only. The clone's `HEAD` is the AIDO runtime `HEAD` at execution, which is **a descendant of the pin whose `src/` and `pyproject.toml` are byte-identical to it** (docs-only commits after the pin, including the one that adds this document, are allowed). The operator re-confirms the HEAD, the descendant relation, the source identity and the remote value at S0 (§4.1). Any difference in `src/` or `pyproject.toml`: STOP and re-pin by a new decision | — |
| D-4 | **Implementer** | P1B exactly as accepted: `supervised_implementer` / `SUP-D` / `qwen3.8-27b` / `litellm`, structured output off, `attempt_timeout_seconds: 300.0`, no token cap, and plaintext acknowledgement if the endpoint is http. **One P1B transmission per run.** Exit 4 or 5 ends the run with no new `prepare` | — |
| D-5 | **Reviewer destination authority** *(RESOLVED — superseded by FU1/FU2)* | **Implemented, not procedural.** The destination is authorized by `controlled_review.endpoint` (scheme, host, explicit port, base path) in the per-run config, which the helper pins by hash. The environment's base URL must match it exactly. AIDO checks the match once before any client exists and again on **every** outbound request, before the network transport sees it. A mismatch exits 4 with `reviewer-egress-refused` and no packet. The production transport is direct (`trust_env=False`), so no environment or Windows-registry proxy is inherited. The earlier procedural chain (H9 record, dedicated window, read-back, post-hoc comparison) is **no longer the control** (§6). Residuals the operator accepts by approving this document are listed in §6.3 | — (the earlier "refuse it" alternative produced FU1/FU2) |
| D-6 | **Reviewer identity** *(amended per FU1 §10)* | The operator names provider `P_R` ∈ {`litellm`, `vllm`}, model `M_R` and endpoint (scheme, host, port, base path) in AUTH-ALPHA1B. **They are written into the per-run config** (`controlled_review.provider`, `.model`, `.endpoint`), outside this repository, and reviewed at H0. They are never written into this repository. `M_R` must not be `qwen3.8-27b`, nor that string under case or whitespace folding. To the operator's knowledge, it must not serve the same weights. A different model family is preferred. A shared gateway with the implementer is **allowed**, but the run is labelled `+SHARED_GATEWAY` (§6.1) | Require a different host from the implementer. This is stronger on deployment separation, but proves nothing more about the weights |
| D-7 | **Verification argv** | AIDO's own venv interpreter, run as `-I -B -c <program>`. The program puts the clone's `src` first on `sys.path`. It fails unless `issue_parser` was imported from the clone. It then checks one operator-written acceptance assertion (the fence case) and runs `tests/test_issue_parser.py` under `-p no:cacheprovider` (§7). If P1D's accepted argv already proves import origin, it may be reused instead | A separate verification venv that does not have AIDO installed. A wrong import then fails closed, but the operator must install packages, which is a separate download decision |
| D-8 | **Reviewer settings** | `attempt_timeout_seconds: 300`, `compact_retry_on_unusable_output: false`, no `max_output_tokens`. For `vllm`: `vllm_structured_output: true` (V2 evidence). `vllm_allow_insecure_http` is true only if the reviewer endpoint is http (and then `endpoint.scheme: http` is required as well, never instead), and it is never a security claim | Compact retry `true`. Allowed, but it cannot fix an envelope problem, and it adds a second semantic request |
| D-9 | **Review invocation** *(amended twice; supersedes the two-invocation rule)* | Exactly **one** `l2-review-approved-file-edit` invocation per run, covered by exactly **one** H9 consent. There is no second invocation and no second H9 record. If H9 is refused, fails verification, ends in `reviewer-egress-refused`, `ReviewerEnvironmentError`, a stall (`REVIEW STALLED`), unusable output, or any other non-success, **the review is over for this run**: do not re-run it, do not write another H9 consent, do not use a `09b_…` step. Preserve the failure evidence and close by the frozen runbook outcome for that `report` class (§8.2). A command-line usage error also consumes the invocation, so the exact command text is checked against runbook 9.2 and the S0 option-set re-check **before** it is run. **Do not confuse this with RS1.** One CLI invocation may contain up to two *internal* semantic attempts only when the project enabled `compact_retry_on_unusable_output` (D-8 keeps it `false`); those are RS1 supervision inside the one invocation, they are unchanged, and they are not a second H9 | Two invocations. Rejected: it contradicts the frozen runbook's "at a stop, do not retry" rule and lets a failed attempt be bypassed by a new consent |
| D-10 | **What counts as success** | `ALPHA1B_COMPLETED_COMMITTED` requires a valid review packet (any verdict) and H10 COMMIT. A COMMIT after `changes_requested` or `needs_human_review` requires a written reason, and the label carries `+HUMAN_OVERRODE_VERDICT` | Success requires `approve`. Stricter, but it makes an advisory verdict decisive, which conflicts with "verdict is advisory" |
| D-11 | **H10 scope** | COMMIT or RESTORE in the disposable clone only, with hooks disabled. Push, branch and PR are outside ALPHA-1B. A later push of the fix to `origin` is a separate human action and is not ALPHA-1B evidence | — |
| D-12 | **Retention and cleanup** | Keep the clone until a human has reviewed closure. Keep the run directory, the evidence and the ledger. Close windows B1 and B2 right after use. Delete nothing that holds a tombstone | — |

### 2.2 Notes on D-5 and D-7

**D-5** is no longer a decision about a procedure. By approving this document the
operator accepts the implemented authority and the residuals in §6.3. The
authority is **project policy**, not per-run consent: the per-run consent is
still the human H9 act.

**D-7** answers HB-1. The import-origin guard is part of the single configured
command, so `outcome: verified` implies the guard passed in the same process.
Without the guard, the claim "verification passed against the written
post-image" cannot be supported.

### 2.3 AUTH-ALPHA1B draft

> **AUTH-ALPHA1B-01 — DRAFT, NOT APPROVED.** It becomes effective only when the
> operator fills the approval line, after the S0 checks pass in the same sitting.
> It grants no per-run consent: H4S, H6, H7, H8, H9 and H10 remain separate
> human acts. It is void if any bound value below differs at execution.
>
> | Field | Value |
> |---|---|
> | AIDO source pin | `44bf3be05195a4fc050de7f0cad2407795d7c9b8`. `src/` and `pyproject.toml` at the runtime HEAD are byte-identical to it |
> | AIDO runtime | `C:\dev\ai_dev_orchestrator` at `<HEAD>` (a descendant of the pin), clean |
> | Helper | `docs/alpha0/a0_helper.py` at git blob `<HELPER_BLOB>`, **recorded at S0** (the helper changed after the source pin, so its blob is separate from it), copied unchanged into the run directory (its SHA-256 is pinned at preflight) |
> | Repository / clone / HEAD | `zlw1987/ai_dev_orchestrator` → `C:\aido_alpha1b_ws\r01` at `<HEAD>`. Any other value: STOP |
> | Target / task | `src/ai_dev_orchestrator/github/issue_parser.py` (blob and SHA-256 recorded at preflight); task 9101, P1C §2.1 body |
> | `project_id` | `aido-alpha1b-r01` (never used before) |
> | Implementer | `SUP-D` / `qwen3.8-27b` / `litellm`; endpoint scheme, host and port typed at H4S; one P1B transmission |
> | Reviewer | provider `<P_R>`, model `<M_R>`, endpoint `<scheme>://<host>:<port><base_path>`, all written into `controlled_review` in the per-run config (never into this repository) |
> | Verification | §7 argv, run twice (H8 and inside the review) |
> | Grants | Each listed command at most as often as §5 allows (the review command exactly once, D-9), against this clone and target only |
> | Does not grant | A second implementer request; a second H9 or review-command invocation, or a review after any failure or stall; any other file, repository or clone; push, branch or PR; a fixer or review/fix loop; a fallback or second reviewer; reuse of any P1C/P1D approval or consent; any qualification credit |
>
> **Approval:** `I approve AUTH-ALPHA1B-01` — `<OPERATOR_NAME>`, `<ISO-8601 with offset>`

## 3. Existing components reused unchanged

| Component | Used for | Source of the procedure |
|---|---|---|
| `generate-plan`, `l2-dry-run` | H2 plan | runbook step 2; P1C step 3 |
| `l2-supervised-implementer-prepare`, `-run` | the one implementer transmission | P1C steps 4–7 |
| Persistent authorization ledger | single use of H4S | P1C §4.3, unchanged |
| `l2-read-workspace-files` | packet for the generator | runbook step 3 |
| `generate-diff-proposal` | deterministic diff from the implementer's content | runbook step 5 |
| `l2-preview-file-edits` | offline check of H6 | runbook step 6 |
| `l2-apply-approved-file-edit` | H7 write | runbook step 7 |
| `l2-verify-approved-file-edit` | H8 verification | runbook step 8 |
| `l2-review-approved-file-edit` | H9 review (verification runs again internally) | runbook step 9, with §6.2 replacing 9.1 |
| Helper `preflight`, `plan-draft`, `approval-check`, `packet-check`, `proposed-assemble`, `proposed-check`, `diff-draft`, `report`, `snapshot`, `inventory` | pins, state proofs, closure | runbook; `docs/alpha0/a0_helper.py`, copied unchanged into the run directory (v4/v5 recognition in `report`: B-1, closed, §4.3) |
| P1D implementer-to-helper hand-off (H4′) | turning the accepted P1B reply into `proposed-content.v1` | §5 S5 |

Variable names. The ALPHA-1B environment file defines the runbook's `A0_*`
names, so runbook commands can be pasted unchanged. It defines no `review` mode:
**every** window clears every `AIDO_*` provider variable first.

**CLI surface re-check at the pin (2026-10-20, offline `--help`).** The option
sets of `l2-supervised-implementer-prepare`, `l2-supervised-implementer-run`,
`l2-review-approved-file-edit` and the other seven commands used here match the
sets recorded in P1C §1 and runbook Appendix B. FU1/FU2 changed the review
command's wording only. The operator repeats this check at S0.

## 4. Source and version binding, and what remains to prepare

### 4.1 Source pin reconciliation (ALPHA-1B vs. the Alpha-0 helper and preflight)

The helper's `preflight` (a) refuses a non-clean `src/` or `pyproject.toml` in
the AIDO repository and (b) requires `git diff --quiet <verified-commit> HEAD --
src pyproject.toml`. The pin is therefore a statement about `src/` and
`pyproject.toml`, not about HEAD. That is what lets docs-only commits follow the
pin without invalidating it.

| Pin | Value | Status for ALPHA-1B |
|---|---|---|
| Alpha-0 runbook / helper default `VERIFIED_AIDO_COMMIT` | `39d81bac…` | **Historical. Unchanged and never edited.** If `--verified-commit` is omitted the preflight STOPs against the current source. That is intended |
| ALPHA-P1C | `b8ac9ea…` | **Historical.** Its C-2 (clone HEAD exactly `b8ac9ea`) does not carry over |
| ALPHA-P1D | `38081af…` | **Historical.** `src/` differs from the pin (FU1/FU2 changed 8 files). Its snapshots stay true statements about P1D |
| **ALPHA-1B** | **`44bf3be05195a4fc050de7f0cad2407795d7c9b8`** | **The new source pin.** Passed explicitly as `--verified-commit`. Nothing earlier authorizes the newer source |

S0 checks (operator, window A; `AIDO_REPO` is the runtime checkout):

```bat
git -C "%AIDO_REPO%" rev-parse HEAD
git -C "%AIDO_REPO%" status --porcelain=v1 --untracked-files=all
git -C "%AIDO_REPO%" merge-base --is-ancestor 44bf3be05195a4fc050de7f0cad2407795d7c9b8 HEAD
git -C "%AIDO_REPO%" diff --quiet 44bf3be05195a4fc050de7f0cad2407795d7c9b8 HEAD -- src pyproject.toml
git -C "%AIDO_REPO%" ls-remote origin refs/heads/main
git -C "%AIDO_REPO%" rev-parse HEAD:docs/alpha0/a0_helper.py
```

Required: the status is empty; the next two commands return 0; `ls-remote`
equals HEAD (so the clone gets exactly the runtime HEAD — the P1C B-1 lesson);
the last value is recorded in AUTH as `<HELPER_BLOB>`. Anything else: STOP, no
clone, nothing sent.

### 4.2 Operator preparation (preparation, not implementation)

1. `a1_env.cmd`, with no secrets. It is the runbook's `a0_env.cmd` without the
   `review` branch. It also does the following:
   - prepends `C:\Program Files\Git\mingw64\bin` to `PATH`, so every window
     resolves the same Git (P1D finding);
   - defines `A1_EVID`, `A1_LEDGER` and `A1_RUN_ID` (the last one is filled
     after `prepare`);
   - clears every `AIDO_LITELLM_*` and `AIDO_VLLM_*` name (this window hygiene
     stays);
   - optionally clears `HTTP_PROXY`, `HTTPS_PROXY` and `ALL_PROXY` and sets
     `NO_PROXY=*`. This is now **hygiene only**: proxy isolation of the reviewer
     is enforced by AIDO (§6), and the implementer already uses
     `trust_env=False`.
2. The project config. It is runbook Appendix A with `project_id`
   `aido-alpha1b-r01`, the §7 verification block, the D-6/D-8 reviewer block
   **plus the `controlled_review.endpoint` block**, and the P1C §4.2
   `supervised_implementer` block with the D-2 ledger path. **All authorities
   are in the config from the start.** The helper pins it at preflight, and
   there is no mid-run amendment. Runbook Appendix A on its own has **no**
   `endpoint` block, and a review gate without one refuses before verification
   (exit 1), so the block is mandatory:

   ```yaml
   controlled_review:
     enabled: true
     provider: "<P_R>"              # exactly litellm | vllm
     model: "<M_R>"
     endpoint:                      # authorizes; it is not the base URL
       scheme: "<http|https>"
       host: "<lowercase ASCII LDH host or canonical dotted-quad>"
       port: <1..65535>             # required, never inferred
       base_path: "<'' or /seg[/seg]*>"
     attempt_timeout_seconds: 300
     compact_retry_on_unusable_output: false
     vllm_allow_insecure_http: false    # true only for an http vllm endpoint
     vllm_structured_output: <true|false>  # vllm only
   ```

   No base URL string and no credential belong in the config. The values stay
   outside this repository.
3. The issue body: P1C §2.1, verbatim.

### 4.3 Reconciliation findings against the frozen helper and runbook

Reconciliation was done by inspection of `docs/alpha0/a0_helper.py`, the runbook
and the shipped CLI at the pin, plus the helper's own offline test suite. The
only helper change is the B-1 fix below (its suite is now 152 tests, up from
73). The runbook is **not modified**.

| # | Finding | Effect | Disposition |
|---|---|---|---|
| **B-1** *(closed 2026-10-20)* | `cmd_report` classified a review result as `REVIEWED` only if `schema_version == "review-packet.v4"`, while the pinned source writes **`review-packet.v5`** | Without a fix, a successful review would be classified `UNEXPECTED_STOP` at S10 and the run could not close | **Fixed (OD-2 approved).** `cmd_report` now accepts the exact members of `REVIEW_PACKET_SCHEMAS = ("review-packet.v4", "review-packet.v5")`, no prefix test, and still requires rc 0, embedded verification `verified`, the state's target path and `human_decision_required is True`. Unknown, missing or malformed versions and every other classification are unchanged. 79 new offline regression tests cover it. `src/` and the source pin are untouched; the new helper blob is recorded at S0 |
| R-1 | Runbook Appendix A has no `controlled_review.endpoint` | The review gate refuses before verification | Covered by §4.2 item 2 |
| R-2 | Runbook step 9.1 uses `a0_env.cmd review` and a procedural destination check | Superseded by FU1/FU2 | §6.2 replaces step 9.1. `a1_env.cmd` has no `review` mode |
| R-3 | Runbook step 9 table and Appendix text say `review-packet.v4` | Stale for the pinned source | The packet is `v5`; E-4 uses `v5` (§8). The runbook text is not edited |
| R-4 | Runbook 9.2 allows a re-run with the next suffix after `REVIEWER_STAGE_FAILED` or `USAGE_ERROR` | Stricter for this pilot | D-9 governs: exactly one invocation. Runbook 9.2's re-run rows do **not** apply to ALPHA-1B |
| R-5 | Runbook header says it was verified against `39d81ba` | True for Alpha-0 | Unchanged. ALPHA-1B passes `--verified-commit` explicitly |

No other conflict was found: the helper checks no `controlled_review` content,
no endpoint value, and no packet field other than `schema_version`, the embedded
verification outcome, the target path and `human_decision_required`.

**B-2 and B-3 were found by independent review of `dc807f4`** and are closed in
§5.3 and D-9 respectively. B-2: `inventory` hashes every run file and then closes
the run, so a closure record written after it is not covered by the hashes. B-3:
the frozen runbook says that at a stop one does not retry, so a second H9 after a
failed one contradicted it.

## 5. ALPHA-1B execution sequence

Window **A** never holds a provider variable. The helper preflight enforces this
for `AIDO_LITELLM_*` and `AIDO_VLLM_*`. Window **B1** exists only for S4c, and
window **B2** only for S10. Every helper `STOP` ends the run (runbook Appendix C).

| Step | Human boundary | Actions (window A unless stated) | Required result |
|---|---|---|---|
| S0 | — | The §4.1 commands, then the CLI option-set re-check (§3) | Pin, HEAD, source identity, remote and helper blob as §4.1 requires |
| S1 | **H0** | Create the run directory and copy the helper (runbook 0.1–0.3), then write the config. H0 checks the runbook H0 list plus: `controlled_review.model` ≠ `supervised_implementer.model` (exact, case-folded and whitespace-folded); `project_id` is new; the verification argv matches §7; **`controlled_review.endpoint` equals the destination the operator intends to consent to at H9, and no base URL or key is in the config** | config saved |
| S2 | (H1 within H0) | `git clone -c core.autocrlf=false …`, then the helper `preflight --verified-commit 44bf3be05195a4fc050de7f0cad2407795d7c9b8`. Then record the `.git` baseline into `logs\01_git_baseline.txt`: `dir /a /b "%A0_WS%\.git\hooks"`, `certutil -hashfile "%A0_WS%\.git\config" SHA256`, and `if exist "%A0_WS%\.git\info\attributes" echo ATTRIBUTES_PRESENT` | `PREFLIGHT_PASS`; hooks dir holds only `*.sample`; no attributes file |
| S3 | **H2** | Runbook 2.2–2.5 with the P1C body. **One** approved plan, `02_approved_plan.json`, serves P1B and the whole writer chain | `PLAN_DRAFT_READY`, `APPROVAL_CONSISTENT kind=plan`, dry-run rc 0 (this also proves the config, including `endpoint`, loads), `SNAPSHOT_OK` |
| S4a | — | P1C step 4 (`prepare`; evidence `%A1_EVID%`) | rc 0; exactly one new `<run_id>.issued.json` |
| S4b | **H4S** | P1C step 5 | consent typed by the operator |
| S4c | (B1) | P1C step 6. `call a1_env.cmd`, type the three `AIDO_LITELLM_*` values, run, `exit` | banner matches H4S; rc recorded |
| S4d | — | P1C step 7: snapshot `--expect baseline`; ledger listing | `SNAPSHOT_OK`; `<run_id>.consumed.json` present, no issued record; rc 0, outcome `diff_proposed`. **rc 1 with no tombstone:** retry S4c before `expires_at`. **Anything else:** the run ends (label §8) |
| S5 | **H4** (supplier = this run's P1B evidence) | Extract the content (§5.1). Write `04_rationale.txt` as fixed operator prose ("content taken verbatim from SUP-D evidence of run `<run_id>`; no model prose"). Then `proposed-assemble` and `proposed-check` (runbook 4.1-alt and 4.2). Record X-2 in `logs\04_supplier.txt` | `PROPOSED_CONTENT_OK`; expected post = P1B post-image (X-2) |
| S6 | — | Runbook step 3 (read + `packet-check`), step 5 (`generate-diff-proposal`), then 6.1 (`diff-draft`). Record X-1 and X-3 | `PACKET_OK`, `OK`, `DIFF_DRAFT_READY`; X-1 and X-3 hold |
| S7 | **H6** | Runbook 6.2–6.3 | `APPROVAL_CONSISTENT kind=diff`, preview rc 0, `SNAPSHOT_OK` |
| S8 | **H7** | Runbook 7.1–7.3 | `WRITTEN`; snapshot `--expect written` OK |
| S9 | **H8** | Runbook step 8 | `VERIFIED`; snapshot `--expect written` OK |
| S10 | **H9** (B2) | §6.2 procedure. **One invocation only** (D-9) | `REVIEWED verdict=…` (the helper recognizes `review-packet.v4` and `v5`); snapshot `--expect written` OK; X-4 and E-5 hold. Any other result: no second invocation; close per §8.2 |
| S11 | **H10** | Repeat the S2 `.git` baseline commands into `logs\10_git_check.txt` and compare them. Then COMMIT (§5.2) or RESTORE (runbook 10.2) | final snapshot `--expect committed` or `restored` OK |
| S12 | — | §5.3, in order S12a..S12e. `inventory` (S12d) is the **last** writer to the run directory | S12a..S12c complete before S12d; S12e reads only |

### 5.1 S5 extraction (window A)

```bat
"%AIDO_PY%" -I -c "import json,sys; d=json.loads(open(sys.argv[1],'rb').read().decode('utf-8')); open(sys.argv[2],'xb').write(d['content_text'].encode('utf-8'))" "%A1_EVID%\%A1_RUN_ID%\response-content.txt" "%A0_IN%\04_final_content.txt"
certutil -hashfile "%A0_IN%\04_final_content.txt" SHA256
```

The hash must equal `changes[0].post_image_sha256` in
`%A1_EVID%\%A1_RUN_ID%\diff-proposal.json`. The extraction only decodes text
that AIDO's strict parser already accepted, and it opens the output with
`'xb'`, so an existing file is refused. It adds no authority. The rationale is
never taken from the model.

### 5.2 S11 COMMIT with hooks disabled (window A)

```bat
mkdir "%A0_RUN%\state\nohooks"
git -C "%A0_WS%" status --porcelain=v1 --untracked-files=all
git -C "%A0_WS%" -c core.hooksPath="%A0_RUN%\state\nohooks" add -- "%A0_TARGET%"
git -C "%A0_WS%" -c core.hooksPath="%A0_RUN%\state\nohooks" commit -m "<COMMIT_MESSAGE>"
set "A0_RC=%ERRORLEVEL%"
"%AIDO_PY%" "%A0_H%" snapshot --run-dir "%A0_RUN%" --step 10-final-commit --rc %A0_RC% --expect committed
```

If S11's `.git` comparison shows a change, **do not commit**. Restore by hand
only after a human has inspected the clone. Label the run
`FINAL_STATE_UNPROVEN` or `COMPLETED_RESTORED`, as appropriate.

### 5.3 S12 closure order (B-2)

`inventory` hashes every other file in the run directory and its existence closes
the run: after it, every helper command refuses, and any file written afterwards
is **not covered** by the recorded hashes. So nothing may be written into the run
directory after it.

| Step | Action | Rule |
|---|---|---|
| S12a | Complete the X-1..X-4 comparisons and the E-2..E-6 checks | Reads only, except the writes of S12b |
| S12b | Determine the terminal label (§8.2) and write `logs\12_closure.txt` **once**: the label, the X-1..X-4 values, and the line `inventory: NOT YET RUN` | The record **must not** claim that `inventory` ran or succeeded, and must not state a `final_state` or an inventory hash. It cannot be edited later |
| S12c | Verify every intended run artifact exists and is final: `dir /s /b "%A0_RUN%"`, and `type` of the ledger. Expected: `01_git_baseline.txt`, `04_supplier.txt`, `09_consent.txt`, `10_git_check.txt`, `10_decision.txt`, `12_closure.txt`, the helper outputs, and `09_incident.txt` if one was recorded | Anything missing or wrong is fixed **now**, before S12d. After S12d nothing can be fixed |
| S12d | `"%AIDO_PY%" "%A0_H%" inventory --run-dir "%A0_RUN%"` | The **last** writer. Console output only: never redirect its output into the run directory (the file would be created before the hashing and change the tree). Run nothing else that writes into the run directory afterwards |
| S12e | Read-only confirmation (below) | Reads only. Notes, if any, go **outside** the run directory |

```bat
"%AIDO_PY%" -I -B -c "import json,hashlib,sys; r=sys.argv[1]; i=json.load(open(r+'\\logs\\99_inventory.json','rb')); l=open(r+'\\logs\\a0_ledger.jsonl','rb').read(); print('final_state', i['final_state']); print('files', len(i['files'])); print('ledger_hash_matches', i['files'].get('logs/a0_ledger.jsonl')==hashlib.sha256(l).hexdigest()); print('last_ledger_step', json.loads(l.splitlines()[-1].decode('utf-8')).get('step'))" "%A0_RUN%"
```

Required: the S12d console shows `A0 RESULT: INVENTORY_WRITTEN`; `final_state
LAST_SNAPSHOT_OK`; `ledger_hash_matches True`; `last_ledger_step 99-inventory`.
`LAST_SNAPSHOT_OK` only describes the last snapshot, as in runbook step 10.4; it
is not a proof about the clone.

If S12e fails or `final_state` is anything else, the run directory is already
closed and is **not** amended. The pre-inventory label is superseded and the
operator records `FINAL_STATE_UNPROVEN` **outside** the run directory.

## 6. Reviewer independence and destination authority

### 6.1 Identities

| Field | Implementer (P1B) | Reviewer (5F2E/V1/V2 + FU1/FU2) | Nature |
|---|---|---|---|
| Role and invocation | `supervised_implementer`; its own command, process, window and consent | reviewer; its own command, process, window and consent, after verification | AIDO-enforced (separate commands; `transmission_boundary` literals) |
| Requested model | registry `qwen3.8-27b` | `controlled_review.model` only | AIDO-observed (config/registry → request) |
| Server-reported model | Recorded (`response_model_field`). A mismatch is rejected as `model_substitution`. **An absent field cannot be detected**, because the client substitutes the requested model (`llm/client.py`, `data.get("model") or request.model`) | **Neither recorded nor checked** | A runtime claim in every case. Even an exact match does not identify weights |
| Endpoint scheme, host, port | bound at H4S and checked by AIDO before transmission | authorized by `controlled_review.endpoint` (pinned config); the environment's base URL must match it; checked before any client exists and before **every** request. The packet records scheme, `endpoint_host`, `endpoint_port` and `endpoint_base_path` | **Both AIDO-enforced** |
| Network path | `trust_env=False`: AIDO ignores proxies | production transport `ReviewerDirectNetworkTransport` (`retries=0`, `trust_env=False`): no environment or Windows-registry proxy is inherited | **Both AIDO-enforced.** The packet's `transport_proxy_mode` is derived from the transport actually used |
| What the reviewer receives | — | approved diff, selected plan prose, redacted verification output. **No** implementer prompt, reply, rationale or transcript | AIDO-enforced by the prompt builder |
| Weights, serving backend, gateway routing | — | — | Unobservable. Operator attestation only |

**Independence, as claimed.** Different requested model ids (IR-1). No
implementer material reaches the reviewer except the code in the approved diff
itself (IR-2). Separate invocation and consent (IR-4). The deployment is
recorded and labelled (IR-3). Neither identity earns qualification credit.

**Not claimed.** That the reviewer ran different weights. That the backend
honored the requested model. That a shared gateway routed the two requests to
different deployments. The diff is model-authored code, and its comments reach
the reviewer verbatim. The verdict stays advisory, and the human reads the diff
at H6 and H10.

### 6.2 S10 procedure (replaces runbook step 9.1)

1. **H9 record** (window A), written into `%A0_LOG%\09_consent.txt` **before**
   window B2 opens:
   `CONSENT <name> <time> run=aido-alpha1b-r01 provider=<P_R> model=<M_R> scheme=<s> host=<h> port=<p> base_path=<b> tls=<yes|no> structured=<none|json_schema>`.
   It is the human consent and must equal the `controlled_review` block that H0
   reviewed. It is not a machine-checked binding (see R-A below).
2. **Window B2.** Run `call a1_env.cmd`. This clears every `AIDO_*` provider
   variable, overriding the persistent Windows values on this machine. Then type
   **only** `P_R`'s variables. The base URL must match `controlled_review.endpoint`
   (scheme, host, port, base path; a trailing `/` is accepted; an explicit port is
   not required because the effective port is compared). For `litellm`, set
   `AIDO_LITELLM_DEFAULT_MODEL` to `<M_R>` (the value is required but ignored).
   Never use `set AIDO_` to inspect the variables, because it prints the key.
3. **Review** (runbook 9.2, step suffix `09a` only). This is the **only** review-command
   invocation of the run (D-9): there is no `09b`, no second H9 record and no
   re-run after any failure. Read the banner. Its provider, endpoint line
   (scheme, host, port, base path), `Network path:` line, TLS line, model and
   structured mode must equal the H9 record. The expected network line is
   `direct; no environment or platform proxy inherited`.
4. **Packet check** (window A, after B2 is closed). In `09a_review_packet.json`
   (`review-packet.v5`) the `reviewer` block must show: `provider`, `model`,
   `endpoint_scheme`, `endpoint_host`, `endpoint_port`, `endpoint_base_path` and
   `structured_output_mode` equal to the H9 record;
   `endpoint_authority_source` = `project_config.controlled_review.endpoint`;
   `endpoint_matched_authority_before_each_request` = `true`; and
   `transport_proxy_mode` = `direct_no_inherited_proxy`. Read it, for example, with:

   ```bat
   "%AIDO_PY%" -I -c "import json,sys; r=json.load(open(sys.argv[1],'rb'))['reviewer']; [print(k, r.get(k)) for k in ('provider','model','endpoint_scheme','endpoint_host','endpoint_port','endpoint_base_path','structured_output_mode','endpoint_authority_source','endpoint_matched_authority_before_each_request','transport_proxy_mode')]" "%A0_ART%\09a_review_packet.json"
   ```

   A mismatch with the H9 record is recorded in `09_incident.txt` and labelled
   `REVIEW_DESTINATION_MISMATCH`. The run cannot be labelled successful.

### 6.3 Residuals (stated, not hidden)

G-1 and G-2 of the first proposal (reviewer destination read at use; reviewer
proxy discovery not recorded) are **closed mechanically** by FU1/FU2 for the CLI
path. G-3..G-7 are unchanged and listed below.

| # | Residual | Who can trigger it | What remains true | Disposition |
|---|---|---|---|---|
| R-A | The H9 record is human consent, not machine-bound to the config | Operator error, a mistyped H9 line | AIDO sends only to the config-authorized destination; the packet records what was used | Closure compares them (§6.2 step 4); label `REVIEW_DESTINATION_MISMATCH` |
| R-B | DNS answers, the hosts file and routing are not observed. The authority is the host as text. Over `https` the certificate is verified against the host with httpx's default trust store (`SSL_CERT_*` is not consulted: a private-CA https reviewer fails closed). Over `http` nothing authenticates the server | An environment that resolves an authorized name elsewhere | AIDO hands source-derived material only to the authorized scheme, host, port and path | Accepted. `vllm_allow_insecure_http` stays an acknowledgement, never a security claim |
| R-C | In-process code could open its own socket; the egress check is not a sandbox against it | Code in the AIDO process | Same as P1B A-19 | Accepted |
| R-D | A library caller that injects a non-production transport gets `injected_transport_not_established` in the packet | A non-CLI caller | The CLI path is always the direct transport | Not applicable to the pilot; E-5 requires `direct_no_inherited_proxy` |
| G-3 | The helper cannot see which `--project-config` a CLI call used. Pins detect a **modified** pinned file, not use of **another** file | Operator error | Every report carries `project_id`/`repo`; the packet carries the reviewer identity and endpoint authority; a write to another workspace leaves this clone at baseline (snapshot STOP) | Control: one `%A0_CFG%` variable, plus report cross-checks at S12 |
| G-4 | AIDO does not compare `controlled_review.model` with `supervised_implementer.model` | Config error | H0 checks it; the preflight pins it; the packet confirms it | Accepted; BL-4 |
| G-5 | AIDO keeps no memory of a stall or failure across invocations | A re-run of the review command (D-9 forbids it) | Every invocation is a separate helper `report` step in the ledger. More than one `kind=review` entry, or any `09b`, is a visible protocol violation | A run with a second review invocation cannot carry a success label |
| G-6 | The verification postcondition does not see ignored files, `.git` internals or paths outside the clone | The unsandboxed verification child, run twice | HEAD, the status and the target bytes are proven | S2/S11 `.git` comparison plus hooks-disabled commit (HB-4); other effects are outside the claim |
| G-7 | A new P1B `prepare` after a spent or failed run is mechanically possible | A supported caller | The ledger records every issuance and consumption | D-4: one transmission per run; S12 confirms exactly one record family since H0 |

## 7. Verification argv (D-7, recommended shape)

```yaml
controlled_verification:
  enabled: true
  executable: "C:/dev/ai_dev_orchestrator/.venv/Scripts/python.exe"
  args:
    - "-I"
    - "-B"
    - "-c"
    - |-
      import os, sys
      src = os.path.join(os.getcwd(), 'src')
      sys.path.insert(0, src)
      import ai_dev_orchestrator.github.issue_parser as m
      if not os.path.normcase(os.path.abspath(m.__file__)).startswith(os.path.normcase(src) + os.sep):
          sys.exit('ALPHA1B: issue_parser was not imported from the clone')
      r = m.parse_issue_body('## Scope\n```\n## Goal\n```\n')
      if 'Goal' in r.sections or '## Goal' not in r.sections.get('Scope', ''):
          sys.exit('ALPHA1B: fence acceptance check failed')
      import pytest
      sys.exit(pytest.main(['-q', '-p', 'no:cacheprovider', 'tests/test_issue_parser.py']))
  timeout_seconds: 300
  max_output_bytes: 200000
```

- **The argv is trusted operator config**, used verbatim. It holds no secret
  and no shell syntax. `args` forbids only NUL, so the multi-line program loads.
  S3's `l2-dry-run` proves that the config loads.
- `-B` and `no:cacheprovider` keep `__pycache__` and `.pytest_cache` out of the
  clone (otherwise exit 3).
- The acceptance assertion fails on the current file and passes only when the
  fence rule holds for this case. `outcome: verified` therefore means three
  things: the clone's module was tested, this case passed, and the existing
  parser tests passed. It does **not** mean the fix is correct in general.

## 8. Acceptance evidence and truthful labels

### 8.1 Evidence required for `ALPHA1B_COMPLETED_COMMITTED`

| # | Evidence | Where |
|---|---|---|
| E-1 | Preflight PASS with `--verified-commit 44bf3be…`. Every snapshot `SNAPSHOT_OK`. The last snapshot is `10-final-commit expect=committed`. After S12d, `inventory` reports `final_state: LAST_SNAPSHOT_OK` and S12e's read-only checks pass. This is the **only** evidence that is confirmed after the closure record was written | `logs\a0_ledger.jsonl`, `logs\99_inventory.json` (S12e) |
| E-2 | P1B rc 0 with outcome `diff_proposed`. The evidence set is complete. The ledger holds `<run_id>.consumed.json` and no issued record, and that is the only family created since H0 | evidence dir; ledger listing |
| E-3 | Write rc 0 (`written-and-verified`); verification rc 0 (`verified`) | `07_…`, `08_…` |
| E-4 | Review rc 0, **`review-packet.v5`**, embedded verification `verified`, no stall, verdict recorded | `09a_…` (the only review step, D-9) |
| E-5 | The packet's v5 reviewer fields equal the H9 record and show `endpoint_authority_source` = `project_config.controlled_review.endpoint`, `endpoint_matched_authority_before_each_request` = `true` and `transport_proxy_mode` = `direct_no_inherited_proxy` (§6.2 step 4) | `09_consent.txt`, packet |
| E-6 | The `.git` comparison is unchanged; the H10 decision is COMMIT with a reason | `10_git_check.txt`, `10_decision.txt` |
| E-7 | The cross-run bindings X-1..X-4 hold, recorded in `12_closure.txt` **before** inventory (S12b). The record states that inventory had not yet run | `12_closure.txt` |

**Cross-run bindings.** These are the only comparisons between the P1B evidence
and the helper chain. They compare semantic bindings, never whole files: the
approval metadata, provenance timestamps and rationale prose legitimately
differ.

| # | Binding | Equality required |
|---|---|---|
| X-1 | Plan | The P1B authorization's bound `approved_plan_sha256` = the helper-pinned SHA-256 of `02_approved_plan.json`. It is the same file, so the bytes are identical |
| X-2 | Proposed content | SHA-256 of the extracted `content_text` = P1B `diff-proposal.json` post-image = `proposed-check` expected post = the approved diff's post-image = the committed blob (E-1) |
| X-3 | Source | P1B pre-image = preflight `pre_image_sha256` = the approved diff's pre-image. The target path, `change_type: modify`, `project_id`, `repo` and `issue_number` are equal in both |
| X-4 | Identities | P1B provenance model `qwen3.8-27b`, and its recorded `response_model_field`. Packet `reviewer.model` = `M_R`, which is not equal to `qwen3.8-27b`. Packet provider and endpoint = H9 |

The unified-diff text is **not** separately required. Given the same path,
pre-image and post-image, the deterministic generator produces it. If the two
diffs differ while X-2 and X-3 hold, record it as an anomaly. It does not block.

### 8.2 Labels

Exactly one terminal label is written to `12_closure.txt`, before `inventory` (§5.3). The same
order holds when the run ends early: write the record, verify (S12c), then `inventory`.

| Label | When | Truthful scope |
|---|---|---|
| `ALPHA1B_COMPLETED_COMMITTED[+HUMAN_OVERRODE_VERDICT][+SHARED_GATEWAY]` | E-2..E-7 hold at S12b. E-1's inventory part is confirmed at S12e; if it fails the label is superseded (§5.3) | One supervised, human-approved change, proposed by SUP-D, was written, passed the configured verification, received an advisory review from the requested reviewer model, and was committed by a human in a disposable clone |
| `ALPHA1B_COMPLETED_RESTORED` | A valid review, then H10 RESTORE, then snapshot `restored` OK | The chain ran end to end, and the change was not adopted |
| `STOPPED_BEFORE_TRANSMISSION` | A STOP before S4c | Nothing was sent |
| `IMPLEMENTER_NO_PROPOSAL` | P1B rc 0 `no_change_proposed`, or rc 4/5 | The source was sent (on rc 4/5). There was no proposal. No second request |
| `STOPPED_AT_H6` | The human declined the diff | The workspace was never written |
| `WRITE_REFUSED` / `WRITE_INDETERMINATE` | Writer rc 1 / rc 3 | As in runbook 7.3 |
| `VERIFICATION_FAILED` / `WORKSPACE_UNTRUSTED` | Verifier rc 2 / rc 3, at S9 or inside S10 | No reviewer contact when verification fails |
| `REVIEW_UNAVAILABLE` | The single review invocation (D-9) ended with rc 4 (reviewer-stage failure of any kind, including `REVIEW STALLED`, a refused environment or `reviewer-egress-refused`), rc 1 (refused), or a usage error | No retry, no second H9. AIDO stopped waiting or refused before any network transport. After a stall the request, the worker and backend inference were **not** observed to stop. The runbook outcome that applies (runbook 9.2 table) decides whether the human may go on to step 10; COMMIT is not available without a valid review (D-10), so only RESTORE or hand inspection |
| `REVIEW_DESTINATION_MISMATCH` | E-5 fails: the packet's endpoint fields differ from the H9 record | The destination AIDO used was the one the config authorized, but not the one the human consented to at H9. An incident; the run cannot be labelled successful |
| `FINAL_STATE_UNPROVEN` | Any `STOP_STATE_*`, a `.git` comparison failure, or a missing final snapshot | The clone is inspected by hand. Nothing is claimed |

### 8.3 Claims that are always forbidden

- That SUP-D, `qwen3.8-27b` or `M_R` is qualified, or earned any credit.
- That M4, M5A, M5 or M6 is complete, or that AIDO v1 is.
- That anything here is autonomous.
- That the reviewer's or implementer's **weights** were identified.
- That verification proved the fix correct.
- That any process was sandboxed or free of side effects.
- That any request, worker or backend inference was cancelled or stopped.
- That an http transmission was encrypted, private or authenticated.
- That DNS, routing or the hosts file were controlled or observed.
- That cleanup is complete beyond the AIDO- and helper-observed repository
  state, the ledger, and the closed windows.

## 9. Backlog: excluded from ALPHA-1A and ALPHA-1B

**Done since the first proposal:** BL-1 (reviewer endpoint authority, enforced
before every request) and BL-2 (`trust_env=False` for the reviewer transport)
were implemented by ALPHA-1A-FU1/FU2. Note that BL-1 shipped as project
**authority** and not as a per-run reviewer consent: the H9 act stays human.

**Deferred improvements.** None of these blocks ALPHA-1B:

| # | Item |
|---|---|
| BL-3 | Record the reviewer's server-reported model, with an optional mismatch refusal. Distinguish an absent `model` field from a matching one in `LLMClient` |
| BL-4 | A config-level refusal when the reviewer model equals the supervised-implementer model |
| BL-5 | An argv digest in the verification report (today it records only `arg_count`) |
| BL-6 | A helper re-check of `.git` hooks, config and attributes at snapshot time |
| BL-7 | A P1B evidence export directly to `proposed-content.v1` (replacing the S5 extraction) |
| BL-8 | A single closure command or record format |
| BL-9 | The helper checks the review packet's v5 reviewer fields itself (ALPHA-1B does this by reading the packet, §6.2 step 4) |

**Explicitly not part of this work:**

- an autonomous implementer, or any qualification run or credit;
- a fixer, a review/fix loop, or patching from findings;
- a second, fallback or consensus reviewer, or provider failover;
- a second implementer request, or a retry after a stall;
- multi-file or repository-wide transmission;
- branch, push or PR by AIDO;
- a generic closure framework, state database, lifecycle abstraction or
  execution framework;
- process-tree management, sandboxing or child-effect auditing;
- changes to `src/`, the runbook or `CLAUDE.md` (the only helper change is the
  B-1 v4/v5 recognition and its tests, authorized by OD-2 and done);
- the M5A authority model, or any change to a frozen roadmap dependency.

## 10. Adversarial analysis: summary

| Scenario | Blocked by | Class |
|---|---|---|
| Mismatched project, workspace or approved diff | The writer, verifier and reviewer check `project_id`/`repo`, the plan, the pre-image and the post-image. The helper preflight checks `workspace_path` against the clone. A write elsewhere shows up as a baseline STOP. G-3 | Covered, plus operating control |
| Old approval reused for a new run | New `project_id` (HB-3); P1B 60-minute expiry and ledger tombstone; `approval-check` requires an approval drafted in this run | Hard blocker → closed by D-2 |
| Implementer/reviewer identity mismatch, or alias | H0, pin, packet (G-4). The weights are unobservable, so they are not claimed | Covered within the stated claim |
| Reviewer endpoint substitution, or proxy inheritance | `controlled_review.endpoint` authority, pre-client check, per-request check, direct transport; mismatch exits 4 with no packet and nothing sent | Hard blocker → **closed in code (FU1/FU2, accepted)**; R-B and R-C stated |
| Source baseline drift | The helper requires `src/` and `pyproject.toml` to equal the pin and be clean; S0 repeats it; AUTH is void on any difference | Covered |
| Helper cannot recognize the shipped packet version, or recognizes the wrong one | B-1: exact `v4`/`v5` membership; v3, v6, prefixes, wrong types and malformed packets stay `UNEXPECTED_STOP` | Closed and tested |
| Artifact written after the final inventory | §5.3: the closure record precedes `inventory`; `inventory` is the last writer; S12e only reads | Closed (B-2) |
| Review retried after a failure, or second consent | D-9: exactly one invocation and one H9; a second `kind=review` ledger entry voids the success label | Closed (B-3) |
| RS1 internal attempt mistaken for a second H9 | D-9 names the difference; the compact retry stays off in D-8 and is unchanged | Covered |
| Server-reported model differs from the request | Implementer: rejected (`model_substitution`), but an absent field cannot be seen. Reviewer: not observed (BL-3) | Deferrable; the labels do not claim it |
| Missing or failed review | No success label. D-9: no re-invocation | Covered |
| Verification changes the workspace | AIDO exit 3 for HEAD, status and target; G-6 for the rest; HB-4 at H10 | Covered within scope, plus operating control |
| Verification tests the wrong code | HB-1, D-7 argv guard | Hard blocker → closed by D-7 |
| Repeated consent, or retry after a terminal stall | P1B ledger single use, D-4; reviewer D-9 (one invocation) and G-5 | Covered (procedural for the reviewer invocation count) |
| Invalid final commit or incomplete cleanup | Snapshot `committed` (one parent = baseline, exactly the target, blob = post-image, tree clean); `inventory`; hooks disabled | Covered |

## 11. Verdict

**READY_FOR_HUMAN_DECISION.**

The shipped, independently accepted commands, the Alpha-0 helper (now recognizing
`review-packet.v4` and `v5`) and the accepted P1C/P1D operating pattern suffice
for one human-supervised end-to-end ALPHA-1B. The three issues found by review of
`dc807f4` are closed: **B-1** the helper's v4/v5 recognition, **B-2** the
inventory-last closure order (§5.3), **B-3** the single H9 invocation (D-9). No
material blocker remains, and no new architecture is proposed.

HB-1, HB-3 and HB-4 are closed by operating controls. HB-2 is closed in
accepted code.

Stopping here. Nothing is authorized and nothing was executed.

## 12. Remaining operator decisions

This document signs and approves nothing. The operator answers each row. Safe
defaults are proposed, not applied.

| # | Decision | Safe default (proposed) | What the operator must supply |
|---|---|---|---|
| OD-1 | **Approve DEC-ALPHA1 as finalized**, including D-1..D-12 as amended (D-9: exactly one review invocation) and the §6.3 residuals | Approve every recommended option; override a row only by naming it | `I approve DEC-ALPHA1 (finalized 2026-10-20)` with name and ISO-8601 time, or per-row overrides |
| OD-2 | **Helper amendment for B-1.** *Approved by the operator on 2026-10-20 and implemented.* Scope as approved: `docs/alpha0/a0_helper.py` recognizes exactly `review-packet.v4` and `review-packet.v5` in the review success classifier, plus offline regression tests; nothing else in the helper, nothing in `src/`, the runbook or `CLAUDE.md` | Done | Nothing further. S0 records the resulting helper blob |
| OD-3 | **Reviewer identity and endpoint:** `P_R`, `M_R` (not `qwen3.8-27b`), `scheme`, `host`, `port`, `base_path`, whether the endpoint is http and `vllm_allow_insecure_http` (an acknowledgement only), `vllm_structured_output` for `vllm`, and whether it shares a gateway with the implementer | No safe default for the values. Defaults for the settings follow D-8 | The values, typed into the per-run config and the H9 record only. Never into this repository |
| OD-4 | **Implementer endpoint facts:** scheme, host and effective port are known to the operator; the endpoint accepts the model id `qwen3.8-27b` exactly as written; a key is or is not required; if http, the plaintext acknowledgement | Confirm only | A yes, and the values typed at H4S in S4b/S4c. Not in this repository |
| OD-5 | **Layout and identity:** `project_id` `aido-alpha1b-r01` never used; clone `C:\aido_alpha1b_ws\r01` and run directory `C:\aido_alpha1b_runs\r01` do not yet exist; ledger `C:\aido_p1c_ledger\supervised_implementer` exists and is kept | Accept D-2 | A yes, or replacement paths and id |
| OD-6 | **When to sign AUTH-ALPHA1B-01:** only after OD-1..OD-5 are answered, and the S0 checks pass (including the recorded helper blob) in the same sitting. The authorization is void if the HEAD, source pin, helper blob or config hash differs from the filled values | Sign no earlier than that; one run only; void at the end of the same calendar day unless the operator writes an expiry | The filled approval line of §2.3 |

**Not decisions now, and not decided by this document:** the per-run human acts.
H0 (config review), H2 (plan approval), H4S (transmission consent), H4 (content
supplier), H6 (exact-diff approval), H7 (write go/no-go), H8 (verification
consent), H9 (reviewer transmission consent) and H10 (COMMIT or RESTORE) are each
completed by a human at the moment they are reached. No earlier approval,
including this document's, stands in for any of them.
