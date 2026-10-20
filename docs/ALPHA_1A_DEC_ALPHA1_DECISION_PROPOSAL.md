# ALPHA-1A — DEC-ALPHA1 Minimal Supervised Alpha Authorization Design

> **PROPOSAL — NOT AUTHORIZED.**
>
> This is a decision proposal. It authorizes nothing. No model was called, no
> endpoint was contacted, no clone was created, no verification or review was
> run, and no workspace was touched while writing it. AIDO `src/`, the Alpha-0
> helper, the Alpha-0 runbook and `CLAUDE.md` are unchanged.
>
> Every decision in §2 needs explicit operator assent. ALPHA-1B can run only
> after (1) the operator approves DEC-ALPHA1, (2) the operator fills
> AUTH-ALPHA1B-01 (§2.3), and (3) each per-run human boundary in §5 is
> completed by a human at the moment it is reached.

> **REVIEW OUTCOME (2026-10-19): D-5 was answered IMPLEMENTATION_REQUIRED.**
> Procedural endpoint inspection plus `NO_PROXY=*` was not accepted as a
> source-egress guarantee. The correction is
> [ALPHA_1A_FU1_REVIEWER_EGRESS_AUTHORITY_CONTRACT.md](ALPHA_1A_FU1_REVIEWER_EGRESS_AUTHORITY_CONTRACT.md),
> and its §10 lists the amendments to D-3, D-6, §6.2 and G-1/G-2. The §6
> reviewer procedure and the §11 verdict below are superseded by it. The rest of
> this document is unchanged.

| | |
|---|---|
| Kind | Authorization and integration design (documentation only) |
| Recorded | 2026-10-19 |
| AIDO baseline | `38081af96f2464699b550edea087f0b648872b31`; `src/` + `pyproject.toml` identical to `b8ac9ea` (ALPHA-P1B + FU1) |
| Preceded by | ALPHA-P1D Write-and-Verify Pilot (ACCEPTED, CLOSED); the ALPHA-1 readiness assessment (directionally accepted, scope not approved) |
| Readiness assessment | Not present in this repository. It is addressed through the corrections listed in the ALPHA-1A brief |
| Verdict | **READY_FOR_HUMAN_DECISION** (§10) |

ALPHA-1B would be **one separately authorized, human-supervised pilot**. It does
not complete M4, M5A, M5 or M6, and it does not make AIDO v1 complete. `SUP-D`
stays unqualified for the autonomous Implementer role. The operational Reviewer
gets no qualification credit from this pilot. Every frozen hard bar, candidate
history and roadmap dependency is unchanged.

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
None of them needs a code change. Each is closed by an operating control:

| # | Hazard | Why it matters | Control (no code change) |
|---|---|---|---|
| HB-1 | **Verification imports the wrong copy.** The AIDO venv has an editable install whose `.pth` puts `C:\dev\ai_dev_orchestrator\src` on `sys.path`. Plain pytest run in a clone of AIDO itself imports the **runtime checkout**, not the clone's written file | A `verified` outcome would test unmodified code and say nothing about the approved change | The verification argv proves where the module was imported from, and checks the acceptance rule itself (§2.2 D-7) |
| HB-2 | **The reviewer destination has no AIDO-enforced pre-transmission binding.** The endpoint comes only from the environment. The reviewer client keeps httpx's default `trust_env=True`, so environment variables and the Windows per-user registry proxy can route the request through a proxy that AIDO neither controls nor records | Source-derived code could go to, or through, a destination nobody authorized | A dedicated reviewer window, `NO_PROXY=*`, an explicit-port base URL, a read-back that uses AIDO's own URL reducers, and a post-hoc comparison of the packet with the H9 record. These are **procedural** controls (D-5) |
| HB-3 | **An old approval can be replayed.** The writer, verifier and reviewer bind an approval to `project_id`, `repo`, the plan and the pre-image. They do not bind it to a run, a clone or a time. ALPHA-1B can reuse the P1C/P1D target at the same pre-image | An approved diff from P1D could pass AIDO's checks in the new run | A `project_id` never used before (D-2) |
| HB-4 | **The H10 commit runs the operator's Git.** The unsandboxed verification ran twice beforehand. It could have planted `.git/hooks/*`, `.git/config` keys or `.git/info/attributes` filters. Neither AIDO's postcondition nor the helper snapshot inspects those | A planted hook or filter would run with the operator's full environment | Record `.git` hook, config and attributes state after cloning, compare it before H10, and commit with hooks disabled (§5, S11) |

## 2. DEC-ALPHA1 decisions requiring operator assent

### 2.1 Decisions

Each row needs an explicit answer. The recommended option is listed first.

| # | Decision | Recommended | Alternatives |
|---|---|---|---|
| D-1 | **Repository, target and step** | `zlw1987/ai_dev_orchestrator`, `src/ai_dev_orchestrator/github/issue_parser.py`, task 9101 (fence rule, P1C §2.1, unchanged). It has been validated offline twice. The fix is not on `main` (the file has no fence handling at `38081af`). It is low sensitivity: pure parsing with no I/O. The verification already exists (`tests/test_issue_parser.py`) | A different file or repository. That needs new eligibility, plan and verification preparation, which costs at least one more iteration |
| D-2 | **Identity and layout** | `project_id: aido-alpha1b-r01`. The operator confirms it was never used by P1C, P1D or Alpha-0. Clone `C:\aido_alpha1b_ws\r01`, new. Run directory `C:\aido_alpha1b_runs\r01`. Evidence at `<run dir>\evidence`. The **existing persistent ledger** `C:\aido_p1c_ledger\supervised_implementer` is reused, so that every spent run id stays in one place | A new ledger directory. That is allowed, but the old one must still be kept |
| D-3 | **Baseline commit** | Clone `HEAD` = AIDO runtime `HEAD` at execution. Today that is `38081af…`. The local tracking ref `origin/main` shows the same value. The operator re-confirms it with `git ls-remote` at S0. The helper is run with `--verified-commit <that HEAD>` | — |
| D-4 | **Implementer** | P1B exactly as accepted: `supervised_implementer` / `SUP-D` / `qwen3.8-27b` / `litellm`, structured output off, `attempt_timeout_seconds: 300.0`, no token cap, and plaintext acknowledgement if the endpoint is http. **One P1B transmission per run.** Exit 4 or 5 ends the run with no new `prepare` | — |
| D-5 | **Reviewer destination authority** | **Accept procedural destination authority for this one pilot** (§6): H9 record → dedicated window → read-back with AIDO's own reducers → banner → packet comparison. The operator accepts that AIDO itself does not bind the reviewer destination before transmission | Refuse it. In that case the verdict becomes IMPLEMENTATION_REQUIRED for one narrow phase: a reviewer per-run destination consent (scheme, host and port bound and checked by AIDO, as P1B does with H4S) plus `trust_env=False` for the reviewer client only |
| D-6 | **Reviewer identity** | The operator names provider `P_R` ∈ {`litellm`, `vllm`}, model `M_R` and endpoint (scheme, host, port) in AUTH-ALPHA1B. `M_R` must not be `qwen3.8-27b`, nor that string under case or whitespace folding. To the operator's knowledge, it must not serve the same weights. A different model family is preferred. A shared gateway with the implementer is **allowed**, but the run is labelled `shared-gateway` (§6.3) | Require a different host from the implementer. This is stronger on deployment separation, but proves nothing more about the weights |
| D-7 | **Verification argv** | AIDO's own venv interpreter, run as `-I -B -c <program>`. The program puts the clone's `src` first on `sys.path`. It fails unless `issue_parser` was imported from the clone. It then checks one operator-written acceptance assertion (the fence case) and runs `tests/test_issue_parser.py` under `-p no:cacheprovider` (§7). If P1D's accepted argv already proves import origin, it may be reused instead | A separate verification venv that does not have AIDO installed. A wrong import then fails closed, but the operator must install packages, which is a separate download decision |
| D-8 | **Reviewer settings** | `attempt_timeout_seconds: 300`, `compact_retry_on_unusable_output: false`, no `max_output_tokens`. For `vllm`: `vllm_structured_output: true` (V2 evidence). `vllm_allow_insecure_http` is true only if the reviewer endpoint is http, and it is never a security claim | Compact retry `true`. Allowed, but it cannot fix an envelope problem, and it adds a second semantic request |
| D-9 | **Review re-invocation** | At most **two** review-command invocations per run. A second one is allowed only if the first produced no packet **and** its stderr shows a refusal before any request (an environment or transport-config category), with a fresh H9 line. Never after `REVIEW STALLED`. Never after a request was issued and failed | Exactly one invocation. Simpler, but a typo in the reviewer environment then costs a whole new run |
| D-10 | **What counts as success** | `ALPHA1B_COMPLETED_COMMITTED` requires a valid review packet (any verdict) and H10 COMMIT. A COMMIT after `changes_requested` or `needs_human_review` requires a written reason, and the label carries `+HUMAN_OVERRODE_VERDICT` | Success requires `approve`. Stricter, but it makes an advisory verdict decisive, which conflicts with "verdict is advisory" |
| D-11 | **H10 scope** | COMMIT or RESTORE in the disposable clone only, with hooks disabled. Push, branch and PR are outside ALPHA-1B. A later push of the fix to `origin` is a separate human action and is not ALPHA-1B evidence | — |
| D-12 | **Retention and cleanup** | Keep the clone until a human has reviewed closure. Keep the run directory, the evidence and the ledger. Close windows B1 and B2 right after use. Delete nothing that holds a tombstone | — |

### 2.2 Notes on D-5 and D-7

**D-5** is the only decision whose rejection changes the verdict. The procedural
control is adequate for one supervised pilot: one operator, on their own machine,
typing the destination into a fresh window that has been cleared. It is **not**
adequate for unattended, scripted or multi-operator use. That use stays out of
scope and is listed in backlog §9.

**D-7** answers HB-1. The import-origin guard is part of the single configured
command, so `outcome: verified` implies the guard passed in the same process.
Without the guard, the claim "verification passed against the written
post-image" cannot be supported.

### 2.3 AUTH-ALPHA1B draft

> **AUTH-ALPHA1B-01 — DRAFT, NOT APPROVED.** It becomes effective only when the
> operator fills the approval line. It grants no per-run consent: H4S, H6, H7,
> H8, H9 and H10 remain separate human acts.
>
> | Field | Value |
> |---|---|
> | AIDO runtime | `C:\dev\ai_dev_orchestrator` at `<HEAD>`, clean; `src/` identical to `b8ac9ea` |
> | Repository / clone / HEAD | `zlw1987/ai_dev_orchestrator` → `C:\aido_alpha1b_ws\r01` at `<HEAD>`. Any other value: STOP |
> | Target / task | `src/ai_dev_orchestrator/github/issue_parser.py` (blob and SHA-256 recorded at preflight); task 9101, P1C §2.1 body |
> | `project_id` | `aido-alpha1b-r01` (never used before) |
> | Implementer | `SUP-D` / `qwen3.8-27b` / `litellm`; endpoint scheme, host and port typed at H4S; one P1B transmission |
> | Reviewer | provider `<P_R>`, model `<M_R>`, endpoint `<scheme>://<host>:<port>` (host and port only; never written into this repository) |
> | Verification | §7 argv, run twice (H8 and inside the review) |
> | Grants | Each listed command at most as often as §5 allows, against this clone and target only |
> | Does not grant | A second implementer request; a review after a stall; any other file, repository or clone; push, branch or PR; a fixer or review/fix loop; a fallback or second reviewer; reuse of any P1C/P1D approval or consent; any qualification credit |
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
| `l2-review-approved-file-edit` | H9 review (verification runs again internally) | runbook step 9, with the §6 window rules replacing 9.1 |
| Helper `preflight`, `plan-draft`, `approval-check`, `packet-check`, `proposed-assemble`, `proposed-check`, `diff-draft`, `report`, `snapshot`, `inventory` | pins, state proofs, closure | runbook; `docs/alpha0/a0_helper.py`, copied unchanged into the run directory |
| P1D implementer-to-helper hand-off (H4′) | turning the accepted P1B reply into `proposed-content.v1` | §5 S5 |

Variable names. The ALPHA-1B environment file defines the runbook's `A0_*`
names, so runbook commands can be pasted unchanged. It defines no `review` mode:
**every** window clears every `AIDO_*` provider variable first.

## 4. Minimal remaining work

**AIDO and helper code: none.**

Before S0, the operator prepares the following inputs (this is preparation, not
implementation):

1. `a1_env.cmd`, with no secrets. It is the runbook's `a0_env.cmd` without the
   `review` branch. It also does the following:
   - prepends `C:\Program Files\Git\mingw64\bin` to `PATH`, so every window
     resolves the same Git (P1D finding);
   - clears `HTTP_PROXY`, `HTTPS_PROXY` and `ALL_PROXY`;
   - sets `NO_PROXY=*`;
   - defines `A1_EVID`, `A1_LEDGER` and `A1_RUN_ID` (the last one is filled
     after `prepare`).
2. The project config. It is runbook Appendix A with `project_id`
   `aido-alpha1b-r01`, the §7 verification block, and the D-6/D-8 reviewer
   block, plus the P1C §4.2 `supervised_implementer` block with the D-2 ledger
   path. **All four authorities are in the config from the start.** The helper
   pins it at preflight, and there is no mid-run amendment.
3. The issue body: P1C §2.1, verbatim.

## 5. ALPHA-1B execution sequence

Window **A** never holds a provider variable. The helper preflight enforces this
for `AIDO_LITELLM_*` and `AIDO_VLLM_*`. Window **B1** exists only for S4c, and
window **B2** only for S10. Every helper `STOP` ends the run (runbook Appendix C).

| Step | Human boundary | Actions (window A unless stated) | Required result |
|---|---|---|---|
| S0 | — | `git -C %AIDO_REPO% rev-parse HEAD` and `status --porcelain`. `git ls-remote origin refs/heads/main` | HEAD = AUTH value; clean; remote `main` = the same value |
| S1 | **H0** | Create the run directory and copy the helper (runbook 0.1–0.3), then write the config. H0 checks the runbook H0 list plus: `controlled_review.model` ≠ `supervised_implementer.model` (exact, case-folded and whitespace-folded); `project_id` is new; the verification argv matches §7; the reviewer endpoint is **not** in the config | config saved |
| S2 | (H1 within H0) | `git clone -c core.autocrlf=false …`, then the helper `preflight --verified-commit <HEAD>`. Then record the `.git` baseline into `logs\01_git_baseline.txt`: `dir /a /b "%A0_WS%\.git\hooks"`, `certutil -hashfile "%A0_WS%\.git\config" SHA256`, and `if exist "%A0_WS%\.git\info\attributes" echo ATTRIBUTES_PRESENT` | `PREFLIGHT_PASS`; hooks dir holds only `*.sample`; no attributes file |
| S3 | **H2** | Runbook 2.2–2.5 with the P1C body. **One** approved plan, `02_approved_plan.json`, serves P1B and the whole writer chain | `PLAN_DRAFT_READY`, `APPROVAL_CONSISTENT kind=plan`, dry-run rc 0, `SNAPSHOT_OK` |
| S4a | — | P1C step 4 (`prepare`; evidence `%A1_EVID%`) | rc 0; exactly one new `<run_id>.issued.json` |
| S4b | **H4S** | P1C step 5 | consent typed by the operator |
| S4c | (B1) | P1C step 6. `call a1_env.cmd`, type the three `AIDO_LITELLM_*` values, run, `exit` | banner matches H4S; rc recorded |
| S4d | — | P1C step 7: snapshot `--expect baseline`; ledger listing | `SNAPSHOT_OK`; `<run_id>.consumed.json` present, no issued record; rc 0, outcome `diff_proposed`. **rc 1 with no tombstone:** retry S4c before `expires_at`. **Anything else:** the run ends (label §8) |
| S5 | **H4** (supplier = this run's P1B evidence) | Extract the content (§5.1). Write `04_rationale.txt` as fixed operator prose ("content taken verbatim from SUP-D evidence of run `<run_id>`; no model prose"). Then `proposed-assemble` and `proposed-check` (runbook 4.1-alt and 4.2). Record X-2 in `logs\04_supplier.txt` | `PROPOSED_CONTENT_OK`; expected post = P1B post-image (X-2) |
| S6 | — | Runbook step 3 (read + `packet-check`), step 5 (`generate-diff-proposal`), then 6.1 (`diff-draft`). Record X-1 and X-3 | `PACKET_OK`, `OK`, `DIFF_DRAFT_READY`; X-1 and X-3 hold |
| S7 | **H6** | Runbook 6.2–6.3 | `APPROVAL_CONSISTENT kind=diff`, preview rc 0, `SNAPSHOT_OK` |
| S8 | **H7** | Runbook 7.1–7.3 | `WRITTEN`; snapshot `--expect written` OK |
| S9 | **H8** | Runbook step 8 | `VERIFIED`; snapshot `--expect written` OK |
| S10 | **H9** (B2) | §6 procedure | `REVIEWED verdict=…`; snapshot `--expect written` OK; X-4 holds |
| S11 | **H10** | Repeat the S2 `.git` baseline commands into `logs\10_git_check.txt` and compare them. Then COMMIT (§5.2) or RESTORE (runbook 10.2) | final snapshot `--expect committed` or `restored` OK |
| S12 | — | `inventory`; write `logs\12_closure.txt` holding the §8 label and the X-1..X-4 values | `final_state: LAST_SNAPSHOT_OK` |

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

## 6. Reviewer independence and destination-authority contract

### 6.1 Identities

| Field | Implementer (P1B) | Reviewer (5F2E/V1/V2) | Nature |
|---|---|---|---|
| Role and invocation | `supervised_implementer`; its own command, process, window and consent | reviewer; its own command, process, window and consent, after verification | AIDO-enforced (separate commands; `transmission_boundary` literals) |
| Requested model | registry `qwen3.8-27b` | `controlled_review.model` only | AIDO-observed (config/registry → request) |
| Server-reported model | Recorded (`response_model_field`). A mismatch is rejected as `model_substitution`. **An absent field cannot be detected**, because the client substitutes the requested model (`llm/client.py`, `data.get("model") or request.model`) | **Neither recorded nor checked** | A runtime claim in every case. Even an exact match does not identify weights |
| Endpoint scheme, host, port | bound at H4S and checked by AIDO before transmission | read from the environment at use. The packet records scheme and `endpoint_host` (`host:port` only when the URL carries an explicit port) | Implementer: AIDO-enforced. Reviewer: AIDO-recorded after the fact |
| Network path | `trust_env=False`: AIDO ignores proxies | httpx defaults: environment proxies, and the Windows registry proxy when no proxy variable is set | Implementer: AIDO-enforced. Reviewer: operator-controlled (`NO_PROXY=*`) |
| What the reviewer receives | — | approved diff, selected plan prose, redacted verification output. **No** implementer prompt, reply, rationale or transcript | AIDO-enforced by the prompt builder |
| Weights, serving backend, gateway routing | — | — | Unobservable. Operator attestation only |

**Independence, as claimed.** Different requested model ids (IR-1). No
implementer material reaches the reviewer except the code in the approved diff
itself (IR-2). Separate invocation and consent (IR-4). The deployment is
recorded and labelled (IR-3).

**Not claimed.** That the reviewer ran different weights. That the backend
honored the requested model. That a shared gateway routed the two requests to
different deployments. The diff is model-authored code, and its comments reach
the reviewer verbatim. The verdict stays advisory, and the human reads the diff
at H6 and H10.

### 6.2 S10 procedure: destination authority before transmission

1. **H9 record** (window A), written into `%A0_LOG%\09_consent.txt` **before**
   window B2 opens:
   `CONSENT <name> <time> run=aido-alpha1b-r01 provider=<P_R> model=<M_R> scheme=<s> host=<h> port=<p> tls=<yes|no> structured=<none|json_schema>`.
2. **Window B2.** Run `call a1_env.cmd`. This clears every `AIDO_*` provider
   variable, overriding the persistent Windows values on this machine; it also
   clears the proxy variables and sets `NO_PROXY=*`. Then type **only**
   `P_R`'s variables. The base URL **must carry an explicit port**, so that the
   packet records the port. For `litellm`, set `AIDO_LITELLM_DEFAULT_MODEL` to
   `<M_R>` (the value is required but ignored).
3. **Read-back**, using AIDO's own reducers. Nothing is sent, and neither the
   key nor the full URL is printed. Replace `VAR` with `AIDO_VLLM_BASE_URL` or
   `AIDO_LITELLM_BASE_URL`:

   ```bat
   "%AIDO_PY%" -I -c "import os; from ai_dev_orchestrator.plan.real_model_gate import endpoint_host_from_base_url as h; from ai_dev_orchestrator.review import endpoint_scheme_from_base_url as s; from httpx._utils import get_environment_proxies as p; u=os.environ['VAR']; print('A1 DEST', s(u), h(u), 'proxies=', p())"
   ```

   Required: the scheme and `host:port` equal the H9 record, and `proxies= {}`.
   Anything else: fix the window, or `exit` and STOP. Never use `set AIDO_` to
   inspect the variables, because it prints the key.
4. **Review** (runbook 9.2). Read the banner. Its provider, host:port, scheme
   and TLS line, model and structured mode must equal the H9 record.
5. **Packet comparison** (window A, after B2 is closed). In
   `09a_review_packet.json`, `reviewer.provider`, `reviewer.model`,
   `reviewer.endpoint_host`, `reviewer.endpoint_scheme` and
   `reviewer.structured_output_mode` must equal the H9 record. A mismatch is
   recorded in `09_incident.txt` and labelled `REVIEW_DESTINATION_MISMATCH`. The
   run cannot be labelled successful.

### 6.3 Check/use gaps and bypasses (stated, not hidden)

| # | Gap | Who can trigger it | What remains true | Disposition |
|---|---|---|---|---|
| G-1 | The reviewer destination is read from the environment when it is used. The H9 record and the read-back happen earlier, in time and in a different process | Anything that changes window B2's environment between steps 3 and 4. A supported caller can also run the review command with **no** H9 record at all | The packet records what AIDO actually used, and the post-hoc comparison detects a mismatch, **after** transmission | Accepted for one pilot (D-5); backlog item BL-1 |
| G-2 | Reviewer proxy discovery is not recorded by AIDO | A proxy variable or a registry proxy, if `NO_PROXY=*` was not in effect | The read-back shows `proxies= {}` for window B2's environment | Accepted (D-5); BL-2 |
| G-3 | The helper cannot see which `--project-config` a CLI call used. Pins detect a **modified** pinned file, not use of **another** file | Operator error | Every report carries `project_id`/`repo`; the packet carries the reviewer identity; a write to another workspace leaves this clone at baseline (snapshot STOP) | Control: one `%A0_CFG%` variable, plus report cross-checks at S12 |
| G-4 | AIDO does not compare `controlled_review.model` with `supervised_implementer.model` | Config error | H0 checks it; the preflight pins it; the packet confirms it | Accepted; BL-4 |
| G-5 | AIDO keeps no memory of a stall across invocations | A re-run of the review command | Every invocation is a separate helper `report` step (`09a`, `09b`, …) in the ledger, so a violation is visible | D-9; a packet produced after a stall is labelled not countable |
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
| E-1 | Preflight PASS. Every snapshot `SNAPSHOT_OK`. The last snapshot is `10-final-commit expect=committed`. `inventory` reports `final_state: LAST_SNAPSHOT_OK` | `logs\a0_ledger.jsonl`, `logs\99_inventory.json` |
| E-2 | P1B rc 0 with outcome `diff_proposed`. The evidence set is complete. The ledger holds `<run_id>.consumed.json` and no issued record, and that is the only family created since H0 | evidence dir; ledger listing |
| E-3 | Write rc 0 (`written-and-verified`); verification rc 0 (`verified`) | `07_…`, `08_…` |
| E-4 | Review rc 0, `review-packet.v4`, embedded verification `verified`, no stall, verdict recorded | `09a_…` (or `09b_…` under D-9) |
| E-5 | H9 record equals the packet's reviewer fields (§6.2 step 5) | `09_consent.txt`, packet |
| E-6 | The `.git` comparison is unchanged; the H10 decision is COMMIT with a reason | `10_git_check.txt`, `10_decision.txt` |
| E-7 | The cross-run bindings X-1..X-4 hold | `12_closure.txt` |

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

Exactly one terminal label is written to `12_closure.txt`.

| Label | When | Truthful scope |
|---|---|---|
| `ALPHA1B_COMPLETED_COMMITTED[+HUMAN_OVERRODE_VERDICT][+SHARED_GATEWAY]` | E-1..E-7 hold | One supervised, human-approved change, proposed by SUP-D, was written, passed the configured verification, received an advisory review from the requested reviewer model, and was committed by a human in a disposable clone |
| `ALPHA1B_COMPLETED_RESTORED` | A valid review, then H10 RESTORE, then snapshot `restored` OK | The chain ran end to end, and the change was not adopted |
| `STOPPED_BEFORE_TRANSMISSION` | A STOP before S4c | Nothing was sent |
| `IMPLEMENTER_NO_PROPOSAL` | P1B rc 0 `no_change_proposed`, or rc 4/5 | The source was sent (on rc 4/5). There was no proposal. No second request |
| `STOPPED_AT_H6` | The human declined the diff | The workspace was never written |
| `WRITE_REFUSED` / `WRITE_INDETERMINATE` | Writer rc 1 / rc 3 | As in runbook 7.3 |
| `VERIFICATION_FAILED` / `WORKSPACE_UNTRUSTED` | Verifier rc 2 / rc 3, at S9 or inside S10 | No reviewer contact when verification fails |
| `REVIEW_UNAVAILABLE` | Review rc 4 that is not retryable under D-9, including `REVIEW STALLED` | AIDO stopped waiting. The request, the worker and backend inference were **not** observed to stop |
| `REVIEW_DESTINATION_MISMATCH` | E-5 fails | Source-derived code went to an unrecorded or unauthorized destination: an incident |
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
- That cleanup is complete beyond the AIDO- and helper-observed repository
  state, the ledger, and the closed windows.

## 9. Backlog: excluded from ALPHA-1A and ALPHA-1B

**Deferred improvements.** None of these blocks ALPHA-1B under D-5:

| # | Item |
|---|---|
| BL-1 | An AIDO-enforced reviewer per-run destination consent (scheme, host and port bound before transmission, as in P1B's H4S) |
| BL-2 | `trust_env=False` for the reviewer client only (the generic `LLMClient` stays unchanged) |
| BL-3 | Record the reviewer's server-reported model, with an optional mismatch refusal. Distinguish an absent `model` field from a matching one in `LLMClient` |
| BL-4 | A config-level refusal when the reviewer model equals the supervised-implementer model |
| BL-5 | An argv digest in the verification report (today it records only `arg_count`) |
| BL-6 | A helper re-check of `.git` hooks, config and attributes at snapshot time |
| BL-7 | A P1B evidence export directly to `proposed-content.v1` (replacing the S5 extraction) |
| BL-8 | A single closure command or record format |

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
- changes to `src/`, the helper, the runbook or `CLAUDE.md`;
- the M5A authority model, or any change to a frozen roadmap dependency.

## 10. Adversarial analysis: summary

| Scenario | Blocked by | Class |
|---|---|---|
| Mismatched project, workspace or approved diff | The writer, verifier and reviewer check `project_id`/`repo`, the plan, the pre-image and the post-image. The helper preflight checks `workspace_path` against the clone. A write elsewhere shows up as a baseline STOP. G-3 | Covered, plus operating control |
| Old approval reused for a new run | New `project_id` (HB-3); P1B 60-minute expiry and ledger tombstone; `approval-check` requires an approval drafted in this run | Hard blocker → closed by D-2 |
| Implementer/reviewer identity mismatch, or alias | H0, pin, packet (G-4). The weights are unobservable, so they are not claimed | Covered within the stated claim |
| Reviewer endpoint substitution | §6.2 procedural chain; post-hoc packet comparison; `REVIEW_DESTINATION_MISMATCH` | Hard blocker → closed procedurally by D-5 (BL-1/BL-2 if D-5 is rejected) |
| Server-reported model differs from the request | Implementer: rejected (`model_substitution`), but an absent field cannot be seen. Reviewer: not observed (BL-3) | Deferrable; the labels do not claim it |
| Missing or failed review | No success label. D-9 limits re-invocation | Covered |
| Verification changes the workspace | AIDO exit 3 for HEAD, status and target; G-6 for the rest; HB-4 at H10 | Covered within scope, plus operating control |
| Verification tests the wrong code | HB-1, D-7 argv guard | Hard blocker → closed by D-7 |
| Repeated consent, or retry after a terminal stall | P1B ledger single use, D-4; reviewer D-9 and G-5 | Covered (procedural for the reviewer) |
| Invalid final commit or incomplete cleanup | Snapshot `committed` (one parent = baseline, exactly the target, blob = post-image, tree clean); `inventory`; hooks disabled | Covered |

## 11. Verdict

**READY_FOR_HUMAN_DECISION.**

The shipped commands, the frozen helper and the accepted P1C/P1D operating
pattern suffice for one human-supervised end-to-end ALPHA-1B. Every material
hazard found (HB-1..HB-4) is closed by an operating control, and none needs a
code change.

The verdict depends on **D-5**. If the operator does not accept procedural
reviewer destination authority for this one pilot, the verdict becomes
**IMPLEMENTATION_REQUIRED**, limited to BL-1 plus BL-2.

Stopping here. Nothing is authorized and nothing was executed.
