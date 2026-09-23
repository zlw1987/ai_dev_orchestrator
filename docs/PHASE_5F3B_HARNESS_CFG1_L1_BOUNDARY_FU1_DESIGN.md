# Phase 5F3B-HARNESS-CFG1-L1-BOUNDARY-FU1 — L1 / Pre-Consumption Boundary Correction (Design)

```text
5F3B-HARNESS-CFG1-L1-BOUNDARY-FU1-DESIGN-R6   CANDIDATE — PENDING REVIEW
D-1 / D-3 / D-4 ACCEPTED (v2 run record; v2 refusal record; L14 pre-spawn re-proof)
D-2 CLOSED (R3): new field pi_identity_failure_code (§5.1, §9.4, §10)
OC-9 DECIDED BY REVIEWER: P supersedes preflight_pi_installed_offline for CFG1
OC-10 DECIDED (Option B, REWRITTEN R4/B13): a NEW live L9 actual-bytes check
  against the independent pinned arm digest; the move from pre-L4 (frozen L1)
  to post-L4 (L9) is a named temporal amendment, AM-11 (§3, §16)
R4 CORRECTED FOUR FURTHER FINDINGS AGAINST R3 (B11–B14); B11/B13/B14 CLOSED,
  B12 architecture accepted subject to B15; B13 AM-11 accepted; R-WINDOW-E ACCEPTED
R5 CORRECTS TWO FURTHER FINDINGS AGAINST R4 (B15, B16) AND FOLDS OC-11 INTO THIS
  FU (§3 AM-12/13/14, §9.2a/§9.2b/§9.2c, §10, §11 Tests Q/R/Y/Z, §13, §14, §17, §18)
R6 CORRECTS B17 (L24 ABSENCE AND HARD-LINK-ALIAS FALSE POSITIVES) AND B18 (GOLDEN VECTOR
  FROZEN); RECORDS THE FIVE STATIC-SOURCE/TEMPLATE PINS AS REVIEWER-CONFIRMED; FIXES THE
  STALE AM RANGE (§3 AM-12, §9.2c-C/D, §11 Tests Y/Z, §13, §17, §18)
PRIOR IDENTITIES (superseded, held for provenance only):
  R1  SHA-256 6f250658f559b15155b678027dd8546c83081314d252e71505b289d009fc1df8
      git blob f151bac9112a5df41d2d829249de833db428c1ff
  R2  SHA-256 bd335267231288d56bea3a38f64d70b064020a2e6beb7f050d87fb4aea47acce
      git blob 6497041923c52377ad029f8c4215c19eea8e032b
  R3  SHA-256 5d67e02684743aed6b72abacd59019fef0a42d87352d5be07a4c3174a4f29306
      git blob 86b9ec44c1dff3355869b1504cb023d167565e8b
  R4  SHA-256 1470c841238c4da76dc2cb616e257c33ccce3d738a1631942f3183246166fa1b
      git blob 5ebdd9c054cb84d85cca4b1a4973df50dbdf6540
  R5  SHA-256 d6702f72a36998d0bc5252081576216430d137b7c30785fe8e15edfcd4438841
      git blob f7d9906a8def627800a82ed9b5826dfad289a348
BLOCKED ON FINAL REVIEWER ACCEPTANCE OF R6; IMPLEMENTATION ADDITIONALLY BLOCKED
ON OC-3 (§5) AND THE PRE-A4 BARRIER SEQUENCE (§17)
```

> **THIS DOCUMENT IS A DESIGN CANDIDATE. IT GRANTS NOTHING.**
>
> - `CFG1-S1-A3` is permanently **CONSUMED** and historical-only. Nothing here
>   re-executes, resumes, repairs or reinterprets it.
> - No `A4`, no Stage 2, and no other identifier is authorized, drafted, or
>   reserved here.
> - No production code, test, `CLAUDE.md`, historical evidence file, or
>   authorization document was modified by the phase that wrote this file.
> - Pi remains pinned to **0.85.1**. Nothing here repins it to 0.87.0.
>
> The turns that wrote R1–R4 of this file imported no CFG1/AR2/qualification
> module, launched no Node or Pi process, read no credential or endpoint value,
> opened no socket, and read nothing outside `C:\dev\ai_dev_orchestrator`.
>
> **R5 disclosure (exact, not softened).** The R5 turn read frozen source text
> and hashed four tracked extension source files with `sha256sum`, and it
> **did import `ar2.pi_config` once**, read-only, in a throwaway Python
> interpreter, solely to hash the `_GENERATED_CONFIG_HEADER` string that §9.2c
> pins. That import loads the `ar2` package's `__init__` and `environment`
> modules (import-time code only). It launched no Node or Pi process, called no
> function of any module, read no credential or endpoint value, opened no
> socket, wrote no file outside this document, and read nothing outside
> `C:\dev\ai_dev_orchestrator`. The digests it produced were **later
> independently confirmed by the reviewer** (R6, §9.2c-D). The R6 turn again
> read frozen source text and computed the golden vector with a throwaway
> Python script that **parsed** `ar2/pi_config.py` with `ast` (no import of any
> AR2/CFG1/qualification module); it ran no writer, no Node/Pi process, opened
> no socket and read no credential.

Subordinate to, in order: the frozen CFG1 design
[`PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md)
(cited as **§n**), the frozen L16-FU2 R2 design and its ERR1 erratum, and the
accepted DIAG1 findings D1–D6. Where this document amends a frozen clause it
says so explicitly in §3; everything not listed there is preserved.

**R2 changelog.** R1 (identity above) was returned HOLD with
five blocking findings, B1–B5. R2 revises only this document, corrects each,
and preserves the R1 architecture (run-record v2; the canonical
pre-consumption identity gate; the same canonical proof re-run at L1; the
secret-free identity child environment; workspace mint write-ahead state; the
step cursor; the L18 dispatch write-ahead; the L14 pre-spawn re-proof;
historical v1 semantics) exactly where R1 already had it right. Nothing here
was implemented, run, committed, or pushed. Section-by-section:

| Finding | What was wrong in R1 | Where it is corrected in R2 |
|---|---|---|
| **B1** | `pi_observed_version == NOT_OBSERVED` was defined as "probe never ran" and simultaneously required by `pi_seam_digests_match == false` — false for a P4 (post-probe) failure, where the probe demonstrably ran. | §5 (P1/P5 rows, new §5.1), §9.4, §10 |
| **B2** | `refused_at_step` was claimed to "always equal the step cursor" while also being claimed absent for post-dispatch failures, and tied to refusal-code presence by an unconditional iff — the three claims cannot all hold together. | §9.2, §9.4, §10 |
| **B3** | Node/Pi resolution `realpath`'d before checking for reparse points, so a repo-local junction pointing outside the checkout could pass containment; no runtime (file) identity was bound, so "the pair L14 launches is exactly the pair P3 proved" was asserted, not proven. | §5 (P1, P6), new §7.2, §11 |
| **B4** | "A step stages its observation writes and commits them only when the step completes" was stated as a blanket rule, which — read literally — contradicts the write-ahead discipline §8 and §9.3 already require for authority/lifecycle facts. | new §9.2a, §11 |
| **B5** | OC-8 (full §16.2 L1 reconciliation) was left open even though this phase redesigns L1. | new §16 |

Also added: the pre-A4 barrier sequence as its own section (§17, reproduced
verbatim from the reviewer's ordering) and a final adversarial self-review
against R2 itself (§18), as required before this candidate can be resubmitted.

**R3 changelog.** R2 (identity above) was returned HOLD with
five further blocking findings, B6–B10. R3 revises only this document and
preserves every R2/R1 mechanism B6–B10 did not require changing — in
particular D-1/D-3/D-4's acceptance, the whole of §7.2, W (§8), the dispatch
write-ahead (§9.3), and §16's reconciliation methodology.

| Finding | What was wrong in R2 | Where it is corrected in R3 |
|---|---|---|
| **B6** | §9.4's closing invariant used an unconditional `refused_at_step present ⇔ unexpected_failure_step absent`, which rejects a clean run where all three failure fields are absent. | §9.2, §9.4 |
| **B7** | §5.1 used the five P-stage codes (`PI_RESOLUTION_FAILED` etc.) as if they were `pre_dispatch_refusal_code` values, contradicting §9.4's own (correct, shipped-code-matching) `L1 → OFFLINE_PREFLIGHT_FAILED` mapping. The three original durable identity facts also cannot mechanically distinguish a resolution failure from an initial seam failure — both produce `false`/`false`/`NOT_OBSERVED`. | §5.1, §9.4, §10, new field `pi_identity_failure_code` |
| **B8** | Node/Pi filesystem identity was captured at P1 but never re-proven before P3 actually executes the probe — only before the *second* execution, at L14. A swap between P1 and P3 (including a package-root swap that still passes P2's digest subset) was undetected pre-execution. | §5 (new P2R stage), §7.1, §11 |
| **B9** | R2 modeled L9 partial creation from an arbitrary injected double, not the genuine `write_cfg1_pi_config`, which already retires its issuance transactionally (FU4-FU1) on every supported exit path — `config_issuance_possibly_created` was unnecessary and, worse, inert. For L11, `extension_possibly_created` was evidence only, with no cleanup authority behind it. | §9.2a, §11 |
| **B10** | OC-9/OC-10 were left as "separate follow-up" instead of decided, even though B5's own reconciliation had already surfaced them as genuine gaps. | §14, §16, §17 |

**R4 changelog.** R3 (identity above) was returned HOLD with
four further blocking findings, B11–B14. R4 revises only this document and
preserves every R3 mechanism B11–B14 did not require changing — in particular
D-1…D-4, §6, §7.2's primitive, W (§8), the step cursor and the three modes
(§9.1/§9.2), the dispatch write-ahead (§9.3), OC-9, and §17's numbering. Where
R4 retracts an R3 claim it says so at the place the claim was made.

| Finding | What was wrong in R3 | Where it is corrected in R4 |
|---|---|---|
| **B11** | P2R re-proved only the `node.exe` and package-root **object** identities. An in-place edit or same-directory replacement of a pinned seam file (e.g. `dist/cli.js`) after P2 leaves both identities unchanged, so P3 would execute the changed file and only P4 — after execution — would notice. | §3 AM-1, §5 (P2R redefined as the **final** pre-`CreateProcess` proof: complete seam set **and** both identities), §7.1, §11 new Test V |
| **B12** | R3's L11 failure wrapper called the frozen `scrub_generated_extension_config`, which derives `ar2_config.ts` **by pathname** and unlinks whatever answers there — no issuance, no identity, no handle. R3 called that "genuine cleanup authority"; it is not. The success-path L24 scrub had the same pathname-only shape. | §3 new AM-9/AM-10, §9.2a (L11 row and the whole L11 design rewritten: a CFG1-owned **transactional extension writer and issuance**, consumed by an identity-bound L24), §10 (`extension_failure_path_scrub_verified` **retracted**), §11 Test R rewritten, new Test X |
| **B13** | OC-10 claimed current L9 already proves "actual generated `models.json` redacted digest == `ARM_REDACTED_DIGEST[arm]`". It does not: `register_config_issuance` hashes the **raw** actual bytes; `redacted_models_digest()` hashes a separately built **in-memory** expected document; `GeneratedCfg1Config.models_redacted_sha256` is that expected value; `records.py` writes the pinned constant directly. Nothing compares redacted **actual** bytes to the pin. | §3 new AM-11, §9.2a L9 row, new §9.2b (the new L9 step 9a), §14 OC-10, §16, §11 new Test W, §18 |
| **B14** | The v2 validator prose used hidden facts ("the raise occurred before P2R passed", "P5 not reached") while also saying P's cursor is not durable; it claimed `pi_identity_failure_code == null ∧ OFFLINE_PREFLIGHT_FAILED` could describe a P6 pass (which has no refusal code at all); and it said "five" P codes where R3 has six. | §5 (P6 row, "who creates each fact"), §5.1 rewritten as **pure-durable** rules with an atomic P-family commit, §9.4, §10, §11 Tests A/G/O |

**R5 changelog.** R4 (identity above) was returned HOLD. B11,
B13 and B14 are closed; B12's architecture is accepted subject to B15; AM-11 is
accepted; R-WINDOW-E is accepted under the exact R4 conditions (zero bytes
before the gate, ordinary non-reparse object, file-id containment, no claim that
CFG1 necessarily created the directory). R5 revises only this document and
preserves every R4 decision B15/B16/OC-11 did not require changing — in
particular the B11 final P2R seam+identity proof, the B13 step 9a check and the
AM-11 temporal amendment, the B14 pure-durable validator R-P1…R-P6, and the
AM-9/AM-10 transactional extension writer with typed provenance.

| Finding | What was wrong in R4 | Where it is corrected in R5 |
|---|---|---|
| **B15** | `win_config_authority.identity_bound_unlink` returns the `SetFileInformationByHandle(FileDispositionInfo)` result from inside a `try`, and its `finally` then `os.close`s the deletion-bearing descriptor and **swallows an `OSError`**. `True` therefore proves a successful delete *disposition*, not successful completion of the deletion-bearing handle's close; a close failure can leave the handle leaked and the sensitive object unproven gone while a scrub fact reads `True`. R4's extension-writer own-handle disposal (`token_material_outstanding == false`) inherited the same gap, and R4's E11 wording could be read as letting a release failure discovered *during* a close retroactively trigger disposal before that same close. | §3 new AM-12, §9.2c (governing rules G2/G3), §9.2a (L24 and E11 rewritten), §11 new Test Y, §18.0 |
| **OC-11** | The reviewer required disposition **now**. `generated_config_scrub_verified` starts `True`; L9 may write the endpoint-bearing `models.json` and then raise before returning; nothing sets the fact `False` (only `run_executor.py:623`, after a *successful* L9), and the precise L24 scrub has no `state.generated_config` to act on. That durable `True` is false evidence, and L27's whole-root removal does not prove an individual L24 scrub. | §3 new AM-13, §9.2b (OC-11 paragraph replaced), new §9.2c (the L9 endpoint-material state machine, `endpoint_material_outstanding`), §10, §11 Test Q rewritten, §14 (OC-11 closed), §17, §18.0 |
| **B16** | R4's transactional writer proves *output* authority and later integrity, but still **reads the live AR2 extension sources at L11**. An issuance that records whatever bytes L11 copied proves `later bytes == issued bytes`, not `issued bytes == reviewed/frozen bytes`: a same-user writer that edits `extension/tools.ts` between admission and L11 gets the modified bytes written, read back, issued, and launched with a credential-bearing child environment. The generated-file template had the same shape (comparing the new writer to the frozen writer over one mutable runtime template would be tautological agreement). | §3 new AM-14, §9.2a (writer inputs and E8/E9/E10 rewritten), §9.2c (provenance chain, pin table), §11 new Test Z, §13, §18.0 |

**R6 changelog (this revision).** R5 (identity above) was returned HOLD: B15
closed; OC-11 closed at the L9 writer/failure-path boundary subject to the L24
issue below; B16's static pins **independently confirmed**; R-WINDOW-E accepted.
R6 revises only this document and preserves every R5 decision B17/B18 did not
require changing — B15's close-completing deletion, AM-12's close-failure
accounting, AM-13's L9 write-ahead + `endpoint_material_outstanding`, L27 never
upgrading an individual scrub fact, AM-14's verified-buffer provenance, B11/B13/
B14, AM-9/AM-10/AM-11, R-WINDOW-E, and the no-pathname-deletion rule.

| Finding | What was wrong in R5 | Where it is corrected in R6 |
|---|---|---|
| **B17** | R5's L24 primitive still returned `True` on **absence at open**, which is unsound twice over. **(A) rename race:** after issuance verification a same-user actor renames the issued `models.json`/`ar2_config.ts` to `leak.bin`; the expected pathname is absent; the object still exists; L24 would read `True` and L26 could run. **(B) NTFS hard-link alias:** after L9/L11 release their creating handles, a same-user actor adds another hard link to the issued file; the expected path still has the issued file id and digest, accepts disposition and closes, yet the object stays reachable through the other link. Pathname absence is not object absence, and deleting one name is not deleting the object. | §3 AM-12 (rewritten), §9.2a (L24 sentence), §9.2c new G7 and rewritten section C, §10, §11 Test Y (rewritten), §18.0 |
| **B18** | The `ar2_config.ts` golden vector was left for the implementation to select and compute. | §9.2c-D freezes the four non-secret input literals and the expected SHA-256 as **design literals**; §11 Test Z uses them |
| *pins* | R5 called the four source pins and the template pin "candidates". | §9.2c-D, §9.2a residual 2, §17: recorded as **independently reviewer-confirmed** against frozen commit `bfae384370246e0ab4073a28a6b6df0558153864` |
| *range* | §13 said the frozen-design amendment pointer covers AM-1…AM-11. | §13: **AM-1…AM-14** |

---

## 1. Root cause and the invariants being corrected

| DIAG1 | Mechanical root cause (shipped code at `bfae384…`) | Invariant corrected |
|---|---|---|
| **D6** | The genuine L1 port is `ar2.launch.resolve_runtime_identity` (`run_executor.py:1472`). It runs `subprocess.run([node, cli.js, "--version"])` with **no `env=`** — so the child inherits the entire parent environment — and it runs **before** `verify_pi_seam_digests` (`run_executor.py:486-497`). Node and the Pi shim are found by `shutil.which`, which on Windows searches the current directory first and applies `PATHEXT`, so `node` may resolve to a `.cmd`. | **I-1** no Pi-package-controlled code before Pi provenance; **I-2** identity/version children are secret-free by construction. |
| **D2** | `_initial_observations()` sets `workspace_authority_reproved = workspace_removed_verified = False` (`run_executor.py:303-305`); L27 runs only `if state.workspace is not None` (`:1051`); `compute_lifecycle_closure` requires both facts **unconditionally** (`lifecycle.py:82-88`). An L1 refusal therefore always yields `lifecycle_failure_steps == ["L27"]` → `INDETERMINATE_LIFECYCLE` → halt `LIFECYCLE_CLOSURE_UNPROVEN` (exactly the A3 record). `lifecycle.py`'s own docstring claims workspace facts carry an "or nothing was minted" meaning "in the executor that sets them"; the executor never implemented that, and the v1 field set cannot express it (§10). | **I-4** "never created" and "partially created" are distinct, mechanically. |
| **D3** | T-11's L1 rows (`tests/test_cfg1_lifecycle.py:124-156`) assert only the refusal code and step, never lifecycle, classification, or halt. | **I-6** the real L1 path is mechanically proven end to end. |
| **D4** | `execute_cfg1_run`'s broad `except Exception` writes `OFFLINE_PREFLIGHT_FAILED` / `L1` for **any** uncaught dispatch-phase exception (`run_executor.py:451-454`). | **I-5** the recorded step is the executor boundary actually reached. |
| **D5** | A3's A0–A10 and G0–G6 contain no Pi identity check; drift is first observable at L1, after `establish_stage_output_authority` consumed the authorization. | **I-3** drift is detectable before consumption, by the same proof L1 uses. |
| **D1** | Installed Pi is 0.87.0, not the frozen 0.85.1. | Not "corrected" — drift is a fact about the machine. The correction is that drift is caught before any Pi code runs and before consumption. |

**D4 is broader than "a later failure may be labelled L1".** Three concrete
paths in the shipped executor, each reachable by one malformed port value:

1. **A post-credential failure recorded as pre-credential.** `ArtifactSafetyContext(...)`
   at L5 (`run_executor.py:566`) and L10 (`:630`) sits outside every step
   guard. A raise there is recorded as `L1` — a record that implies no
   credential was ever read, after it was.
2. **A written prompt recorded as never written.** In `_write_one_prompt`,
   `response.get("success")` (`:788`) runs after `send_command` returned. A
   correlated response that is not a `dict` raises `AttributeError`, which
   escapes as `L1` with `dispatch_state` still `NOT_ATTEMPTED` and
   `prompt_writes == 0` — a durable claim that no prompt reached Pi, after one
   did.
3. **A post-dispatch failure recorded as a pre-dispatch refusal.** L20's
   projection (`:736-762`) is unguarded. A raise there writes an L1 refusal
   code onto a record whose `dispatch_state` is `CONFIRMED_SENT`; that record
   then fails its own validator (`REFUSAL_DISAGREES_WITH_DISPATCH_STATE`).

---

## 2. Frozen clauses preserved (unchanged, by reference)

- **§14.2 / `PINNED_PI_SEAM_DIGESTS`** — the complete 20-entry seam set, exactly
  as shipped, and `PINNED_PI_VERSION = "0.85.1"`. No entry is added, removed,
  re-derived, or repinned. "A mismatch refuses before any credential read. It
  means the derivation must be re-reviewed, not that Pi is incompatible."
- **§16.1 principles 1–5** — ownership by in-memory handle, closure always runs
  L21→L27, no durable write before L29, credential consumers exactly L7/L12/L29.
- **§16.2 L0 and L2–L30** — every step, precondition, and transfer, except the
  L1 ordering made normative (AM-1) and the L18 write-ahead (AM-5). In
  particular L2's "if raised before returning an authority →
  `INDETERMINATE_LIFECYCLE` (orphan unprovable, never deleted)" and L1's
  "`REFUSED_PRE_DISPATCH`; nothing to close" are preserved **as intent** —
  this design makes both true at once, which v1 could not.
- **§17** — every ownership row and the whole "Never, by construction" list:
  no deletion of an unproven root, no ownership inferred from a path, name,
  PID or file content.
- **§18** — every row, including row 13 (partial mint: orphan never deleted,
  `INDETERMINATE_LIFECYCLE`, halt) and row 14.
- **§12** classification rows and order; **§19** admission, halt, the six
  `HALT_REASON_CODES`, and `_resolve_halt_reason_code`'s precedence;
  **§16.3** stage output authority, including the frozen signatures of
  `establish_stage_output_authority` and `run_cfg1_stage`.
- **§21** reduction and containment rules; **§22.5** post-hoc verifiers.
- **L16-FU2 R2 + ERR1** in full; arms, the Stage-1 schedule, Q/R/E meanings,
  provider/model/backend identity, the prompt, and the retry policy.
- **`ar2.launch`**, **`ar2.*`** generally, and the qualification package:
  unmodified. CFG1 stops *using* `ar2.launch.resolve_runtime_identity`; it does
  not edit it (see OC-6). Likewise (R4, AM-9) CFG1 stops *using*
  `ar2.pi_config.write_disposable_extension` and
  `ar2.pi_config.scrub_generated_extension_config`; both stay byte-for-byte as
  shipped for AR2's own callers, and CFG1 reads only the frozen static
  extension source files and the frozen generated-file template from that
  package, never editing either — and (R5, AM-14) reads each of them **once**,
  only to compare it with a CFG1-owned independent SHA-256 pin, using only the
  bytes that matched.
- **Historical evidence**: the A1/A2/A3 records and stage-closure records, and
  the A1/A2/A3 authorization documents, are not edited, re-serialized,
  re-validated into a new meaning, or re-labelled.

---

## 3. Frozen clauses requiring amendment (narrow, explicit)

| Id | Frozen text | Contradiction | Narrow amendment |
|---|---|---|---|
| **AM-1** | §16.2 L1 lists "seam digests … Node/Pi identity probe (`--version`, provenance)" without an order; §14.2 requires "refuses before any credential read". | The shipped port executes `cli.js` first, with the full inherited environment. The frozen list does not forbid it. | L1's internal order becomes normative: **resolve (no execution) → complete seam proof → final pre-execution proof (complete seam set + `node.exe` identity + package-root identity, R4/B11) → secret-free version probe → post-probe re-proof → version → Git resolution** (§5). A failure at any stage executes nothing later in that list. |
| **AM-2** | §16.1 principle 5: "No Git, fixture, or verification child environment ever carries a credential or endpoint." | The identity-probe child is not named, and in fact carried everything. | Principle 5 gains the identity-probe child, and for that child the rule is a **positive allowlist** (§6), not "no credential". |
| **AM-3** | §17 workspace row: closed iff `workspace_authority_reproved ∧ removed ∧ residual == 0`. §22.3: `lifecycle_all_closed` is the conjunction "with 'not created' counting as closed". §16.2 L1: "nothing to close". | §17's workspace predicate has no "not created" clause, and v1 has no field that can carry one. The three clauses cannot all hold for an L1 refusal. | The workspace predicate is conditioned on an explicit, executor-owned **workspace mint state** (§8): not attempted → nothing to close; attempted without a returned authority → **always** unproven (L27); authority returned → the existing predicate, unchanged. Applies to **v2 records only** (§10). |
| **AM-4** | §22.2 field set; `PRE_DISPATCH_REFUSAL_CODES`; `pi_observed_version` domain. | See §10. | Run record `pi-harness-cfg1-run.v2` (decision D-1). |
| **AM-5** | §16.2 L18 / §18 row 4a: "prompt write raised … → `SEND_STATE_INDETERMINATE`". | The shipped code only reaches that state for exceptions it anticipates; an unanticipated one after the write records `NOT_ATTEMPTED`. | The "possibly written" fact is written **ahead** of the write (§9.3). |
| **AM-6** | §21.1 "failures become one closed code" (step implied). | The catch-all names a step it did not observe. | `refused_at_step` is always the executor's own step cursor (§9). |
| **AM-7** | §14.1 item 2 (what a LIVE authorization must contain). | No pre-consumption identity check is required. | Every future live authorization's launcher MUST call the canonical pre-consumption Pi identity gate (§7) after its source-origin gate and before `establish_stage_output_authority`. This amends the template for **future** documents; A3's text is historical and unchanged. |
| **AM-8** *(decision D-4, extended by B3)* | §16.2 L14 re-uses L1's identity object with no re-proof. | Between L1 and L14 (seconds, spanning the L4 credential read) the seam files, and the Node/Pi filesystem objects themselves, are unobserved. | Accepted: immediately before L14 spawns Pi, re-run the same canonical seam proof **and** re-check the §7.2 filesystem identity of the resolved `node.exe` and package root against what P1 captured; either mismatch → the existing `RUNTIME_LAUNCH_FAILED` at L14, no spawn. The identity re-check is what makes the seam re-proof alone insufficient against a same-digest replacement (§7.1's TOCTOU table). |
| **AM-9** *(R4, B12)* | Frozen CFG1 §7.4 lists `ar2.pi_config.scrub_generated_extension_config` among modules CFG1 reuses unmodified; §16.2 L11 generates the extension through the frozen `write_disposable_extension`; L24 scrubs `ar2_config.ts` through the frozen scrubber after a realpath containment check (`run_executor.py:1099-1134`). | Neither frozen function has issuance, file identity, or handle-bound deletion. A pathname plus containment is not authority over the object currently answering at that name, so neither the L11 failure path nor the L24 success path can truthfully claim it removed **the file AIDO wrote**. | For CFG1 only: L11 uses a **CFG1-owned transactional extension writer** that returns an **extension issuance** (§9.2a), and L24 removes `ar2_config.ts` only through that issuance's bound identity, by handle (`win_config_authority.identity_bound_unlink`, the FU15 precise-child mechanism L24 already uses for `models.json`). The two frozen AR2 functions are no longer called by CFG1 and are not edited. Frozen §7.4's reuse listing and §16.2 L11/L24 wording are amended accordingly. |
| **AM-10** *(R4, B12)* | CFG1-IMPL-FU4 binds **exactly one** code object — `write_cfg1_pi_config` — as the only opener of a generation interval (`win.bind_config_generator_authority()`, `cfg1_pi_config.py:480`); every pin/child primitive requires such an interval. | The AM-9 writer needs the same pin/child primitives, and so an interval, but must not be able to mint **config** issuance provenance (nor the config generator extension provenance). | The provenance binding admits exactly **two** bound generator code objects — the genuine config generator and the genuine extension writer — each opening a **typed** interval. An interval's type is checked by each issuance registry: a config interval can never produce extension issuance provenance and vice versa. No third binding, no generic registry of generators. This is an amendment to a CFG1 (not AR2) contract and is named here so it is not introduced silently. |
| **AM-11** *(R4, B13; the narrow OC-10 amendment)* | Frozen §16.2 L1 lists "generator self-check on synthetic URL", a check that — **had it been wired** — would run before L4, i.e. with no credential in memory and before L7's route observation. | CFG1 never wired it (§16); and the only CFG1 check proposed in its place (§9.2b) is at L9, which is **after** L4 and L7. The two guarantees are **not** identical and R4 does not claim they are. | Frozen L1's pre-credential generator self-check is **removed, not relocated**. CFG1's generated-config shape guarantee is instead established at **L9** (post-L4, post-L7) by a new mechanical comparison of the **actual on-disk** generated bytes against the independent pinned per-arm digest (§9.2b), plus retained offline regression. **Temporal consequence, accepted by name:** a generator shape defect is now detected after a credential has been read (L4) and a route observed (L7) — and so after the authorization was consumed — refusing `CONFIG_GENERATION_FAILED` at L9, instead of refusing credential-free at L1. |
| **AM-12** *(R5, B15; strengthened R6, B17)* | CFG1-IMPL-FU15's precise-child contract for `win_config_authority.identity_bound_unlink` (and the executor's `_verified_unlink` that fronts it): it returns `True` "only when nothing the issuance authorized remains: either the object was absent already, or it was identity-matched and disposed of". Used by L24 for `models.json` and (AM-9) `ar2_config.ts`. | **(R5, B15)** the `True` was the disposition result, and the `finally` swallowed an `OSError` from closing the deletion-bearing descriptor. **(R6, B17)** two further false positives. **(A) Absence:** failing to open the expected pathname *because it is absent* returned `True`; a same-user actor can rename the issued file after issuance verification and before the open, leaving the pathname absent and the issued object intact. **(B) Hard-link alias:** a second hard link created after the creating handle was released leaves the expected path with the exact issued file id and digest, accepting disposition and closing, while the same file object stays reachable through the other link. Also: `_verified_unlink` returns `True` early for a non-string/empty path and, without an identity, unlinks by pathname. | The primitive's required contract for FU1 (the **what**, not a fixed API). It returns `True` **iff** **one uninterrupted exclusive-handle interval** — from the open to the close of a single share-0 handle — proves and does, in order: (1) the expected pathname opened successfully, no-follow, share-0, delete access; (2) that handle's file identity equals the issued identity; (3) the issued file has **exactly one** hard link (directory reference), read from that same handle as an `int` equal to 1; (4) (2), (3) and the disposition all occur while that same handle remains held, so no other actor can open, rename or **add a hard link** in between; (5) the disposition succeeds; (6) the deletion-bearing handle **closes successfully**. **Any** failure to open — sharing violation, reparse point, denial **and absence** — is `False`; a link count that is unreadable, malformed, a non-`int`, or not exactly 1 is `False` **with no disposition**; there is **no** pathname-based positive result of any kind, no pathname fallback, no retry, no search for a renamed object, and no early `True` for an empty path. The identity-less pathname branch and the non-string early `True` are removed from L24's call graph. A close failure remains `False` and counted `"unlink_handle"` (R5). The claim is about **aliases of the exact file object AIDO created** only — it is not anti-copy secrecy: a separately copied file is outside this object-identity claim and stays inside the already-stated same-user/no-confinement residual. Applies to **both** L24 uses. Writer-side *failure* cleanup through the still-held `CREATE_NEW`/share-0 creating handle is unchanged from R5 (that handle is held continuously since creation, so no alias can exist). |
| **AM-13** *(R5, OC-11)* | Frozen §16.2 L9 / L24 and the shipped executor: `generated_config_scrub_verified` initialises `True` (`run_executor.py:300`), is set `False` only after L9 **returns** (`:623`), and has a precise-scrub path only when `state.generated_config` exists. FU4's writer leaves an endpoint-bearing `models.json` on disk on any failure after its write. | An L9 raise after the endpoint bytes were attempted leaves the durable fact `True` with an endpoint-bearing object present — false evidence — and L27's whole-root removal is a different authority that does not prove an individual scrub. | (i) The fact is written `False` **immediately before** `ports.write_config(...)` (write-ahead, category B, §9.2a). (ii) The genuine writer gains one closed failure fact, `endpoint_material_outstanding`, carried on its typed error, and its failure-path release **disposes `models.json` through its own creating handle, then closes that handle** (G2). (iii) The executor sets the fact `True` after an L9 failure **only** from an exact `False` of that bool on the exact genuine error type; every other outcome leaves it `False`. (iv) L27's success never upgrades it. No new durable field (§9.2c, §10). |
| **AM-14** *(R5, B16)* | Frozen §16.2 L11 and the AR2 `write_disposable_extension`: static extension sources are read from the live AR2 `extension/` directory at L11 and copied; the `_GENERATED_CONFIG_HEADER` template is read from the live module. R4's transactional writer read the same mutable sources and bound issuance to whatever it read. | Issuance then proves *later bytes == issued bytes*, never *issued bytes == reviewed bytes*. A same-user edit between admission and L11 flows through E8–E10 to a credential-bearing launch. Comparing the new writer to the frozen writer over one mutable source would be tautological. | For CFG1 only: the writer takes its inputs from **CFG1-owned independent SHA-256 literals** (per source file: exact size and digest; for the template: a digest and structure rule; plus a golden output vector for the derived `ar2_config.ts`). L11 reads each source once, compares those very bytes with the pin, buffers **only** matching bytes in memory, and E8 writes the buffer — the source pathname is never reopened. Issuance's recorded digests are asserted equal to the pin literals (§9.2c). |

---

## 4. Authority and order model

```text
 operator admission A0–A10 (read-only; unchanged in kind)
 launcher source-origin gate G0–G6 (unchanged in kind; G4/G5 lineage includes the identity module)
 ┌─ NEW  pre-consumption Pi identity gate  (§7) ─────────────────────────────┐
 │   calls the ONE canonical proof P (§5) with the genuine leaf bindings     │
 │   no credential read · no network by AIDO · no repository write ·         │
 │   no stage-output authority · returns one closed code, nothing reusable   │
 └───────────────────────────────────────────────────────────────────────────┘
 ═════════════ consumption boundary: establish_stage_output_authority(...) ═════════════
 run_cfg1_stage(authority)            (signature unchanged; accepts no identity object)
   L0  admission
   L1  P again, from scratch:  resolve → seam proof → FINAL proof (seams + identities)
       → probe(secret-free) → post-probe re-proof → version;
       then Git resolution                                    [cursor = L1, W = NOT_ATTEMPTED]
   L2  W := ATTEMPTED_NO_AUTHORITY ; mint ; W := AUTHORITY_RETURNED iff genuine   [cursor = L2]
   L3  baseline (repository code; still pre-credential)
   L4  credential read  ← first point any credential value is read by AIDO
   …
   L9  config generation; (R4/B13) step 9a: ACTUAL bytes vs pinned arm digest, before issuance
       (R5/OC-11) scrub fact := False BEFORE the call; failure path disposes models.json by
       its creating handle THEN closes it; True only from that proven result (§9.2c)
   …
   L11 (R5/B16) pinned single read of the static sources + template, BEFORE anything is created
       (R4/B12) CFG1 transactional extension writer → extension issuance (never a bare path)
   …
   L14 (D-4/B3) seam re-proof → §7.2 identity re-proof → spawn Pi with the L12 environment
   …
   L18 dispatch write-ahead → one prompt write
   L21–L27 closure (L24 scrubs only through issuance-bound identity, and a scrub is True only
                    only after ONE exclusive interval proved identity + exactly one link and the
                    deletion-bearing handle CLOSED successfully; absence is False — AM-12;
                    L24 extension scrub only through the L11 issuance's bound identity;
                    L27 obligation decided by W, never by a path or by refused_at_step)
   L28–L30 unchanged
```

Two proofs, one definition: the gate and L1 call the **same function object**;
L1 never consumes the gate's result (there is no parameter through which it
could). The gate exists to avoid wasting an authorization; the **security**
invariants rest on L1 (and D-4) alone.

---

## 5. The canonical Pi identity proof (P)

One CFG1-owned function. Names below are illustrative, not frozen. The
**ordering lives in P's own body**, which no port can replace; ports (for
offline doubles) supply only leaf effects: a filesystem view for resolution and
digesting, and the one probe process runner. A double can therefore observe
that a leaf was never called; it cannot reorder P.

**Closed-code note (B7).** Every "On failure" entry below is P's own
**internal** identity subreason — the new durable field `pi_identity_failure_code`
(§5.1, §9.4, §10) — never `pre_dispatch_refusal_code` directly. For an
anticipated P-stage refusal the executor still writes exactly what shipped
code and §9.4 already require: `refused_at_step = "L1"`,
`pre_dispatch_refusal_code = "OFFLINE_PREFLIGHT_FAILED"` (R4/B14: P's
anticipated refusal is **returned** as one typed result object, not raised;
L1 validates its shape and commits the outer code and
`pi_identity_failure_code` together with the rest of P's family — §5 P6 row). R1/R2 conflated these two fields; that
conflation was B7.

| Stage | Action | Executes anything? | On failure (`pi_identity_failure_code`, illustrative) |
|---|---|---|---|
| **P0 inputs** | An explicit ambient mapping, read **by name** for exactly `PATH` (resolution) and `SystemRoot` (probe env). No iteration of values, no other name. The checkout root (derived from the executing CFG1 package's own location, as G6 already proves) for containment refusal only. | no | — |
| **P1 resolve** *(B3, revised)* | Walk `PATH` entries in order; skip empty or non-absolute entries (current directory **never** consulted). **Every lexical component below is inspected with the §7.2 no-follow primitive before it is used for anything** — a symlink, junction, or any `FILE_ATTRIBUTE_REPARSE_POINT` entry is refused **as that candidate**, outright, at the point it is found; it is never realpath'd first and judged by where it points. Containment ("must lie outside the checkout") is likewise checked on the **lexical** candidate path itself, not only on its realpath'd destination — a repository-local or otherwise forbidden lexical path is refused even when its final realpath'd target happens to sit outside the checkout. realpath is used only to confirm one final destination for a candidate that has already passed every lexical/no-follow check, never to launder one that has not. **Node:** within a surviving `PATH` entry, the first name matching exactly `node.exe` — no `PATHEXT` expansion; `.cmd`/`.bat`/`.ps1` never match; the candidate is §7.2-inspected before realpath; a surviving candidate is realpath'd only to confirm one existing regular file whose realpath basename is `node.exe`; its §7.2 stable filesystem identity (volume serial number + 128-bit file id) is captured now and retained in memory for P2R (below) and L14 (§7.1). **Pi:** within a surviving `PATH` entry, the first name matching exactly `pi.cmd`; §7.2-inspected before use — **a directory or reparse point at that name is refused outright as an anchor; `pi.cmd` must resolve, no-follow, to an allowed regular-file type, or it never anchors anything** (still never read, never executed). A surviving `pi.cmd` anchors the two AR2 candidate layouts (`<dir>\node_modules\@earendil-works\pi-coding-agent`, `<dir>\..\node_modules\…`); each path component from the anchor to the first existing candidate with a `package.json` is walked component-by-component with §7.2 — any reparse component refuses that candidate before realpath is ever called on it; the surviving candidate is realpath'd only to confirm the final package root, whose §7.2 identity is captured now and retained. **First candidate only — never search later candidates for one that passes P2.** | no | `PI_RESOLUTION_FAILED` |
| **P2 seam proof** | For **every** key of `PINNED_PI_SEAM_DIGESTS` (the whole table, never a subset): walk the lexical path from the package root, requiring each directory component to be a directory and no component or final entry to be a symlink, junction, or any `FILE_ATTRIBUTE_REPARSE_POINT` entry (inspected without following, §7.2's mechanism); the final entry is a regular file of bounded size; digest its bytes read through one handle; compare. Only the pinned relative keys may ever be rendered — never an absolute path. Stages P's seam result (R4/B14: **staged** in P's own result, never committed on its own — the whole P family is committed atomically at P's return, §5.1). **This is a byte-digest check of 20 specific pinned files only — it is not, and does not substitute for, a proof that the package-root directory object itself is still the one P1 resolved** (an attacker-substituted root containing byte-identical copies of exactly those 20 files, but different unpinned transitive JS elsewhere, passes P2 undetected — this is exactly why P2R, next, exists). | no | `PI_SEAM_UNPROVEN` |
| **P2R final pre-execution proof** *(new B8; **redefined R4/B11**)* | Only if P2 passed. **The last operation before P3's `CreateProcess`** — it re-proves, in one stage, **every** fact the first execution depends on. *R3 retraction:* R3's P2R re-proved only the two object identities, "no second digest walk". That missed B11's counterexample: the package-root directory object is unchanged, `node.exe` is unchanged, but `dist/cli.js` inside that same root is edited in place (same file id) or replaced (new file id, same directory) after P2 — both identities still match, P3 executes the changed file, and only P4 notices, *after* execution. **Preconditions arranged before P2R starts**, so nothing but P3's entry separates P2R from `CreateProcess`: the §6 environment is built and audited, and the argv `[node, <root>\dist\cli.js, "--version"]` and cwd are fixed. **P2R, in this fixed order:** (a) **the complete frozen seam set** — every key of `PINNED_PI_SEAM_DIGESTS`, re-walked from the package root with exactly P2's rules (§7.2 no-follow at every component, regular file, bounded size, one-handle digest, compare) — **never a subset, never cached from P2**; (b) the package root's §7.2 identity against P1's capture; (c) `node.exe`'s §7.2 identity against P1's capture. The two fast identity checks are placed last so they sit nearest the use. Any failure → refuse; nothing is executed. Then control passes **directly** to P3's entry (whose only work before `CreateProcess` is the in-memory write-ahead of `pi_version_probe_attempted`). **What this closes:** an in-place edit or replacement of any pinned seam file (a); a `node.exe` swapped at any time after P1, including mid-P2 (c); a package root swapped for a different directory object whose 20 pinned files are byte-identical (b) — all **before** any of it executes. **What remains, stated as residual, not claimed closed:** the check→use sliver from each item's own read in P2R to `CreateProcess` — for a seam file, from the moment P2R (a) read its bytes; for the identities, from (b)/(c). P4 remains **post-probe tamper detection only** and is never credited with protecting the first execution. `pi_version_probe_attempted` stays `false` throughout P2R. P2R's seam walk is the seam result P stages if P2R refuses (§5.1). | no | `PI_IDENTITY_DRIFTED_BEFORE_PROBE` — meaning, as of R4, *"the Pi identity proven by P1/P2 (object identities **or** pinned seam bytes) no longer held at the final pre-execution proof"* |
| **P3 probe** *(B1: sets `pi_version_probe_attempted`)* | Only if P2R passed. Entry into this stage durably sets `pi_version_probe_attempted = true` — a write-ahead fact (§9.2a) set at entry, not on any outcome: a start error, non-zero exit, timeout, or output-cap overflow inside this stage leaves it `true` (an attempt was made) and never reverts it. argv exactly `[node, <root>\dist\cli.js, "--version"]` (fixed before P2R started), where `<root>\dist\cli.js` is the **same lexical path** P2 and P2R digested, under the **same §7.2 package-root identity** P1 captured and P2R just re-confirmed; executable pinned (no search); `shell=False`; cwd explicitly the proven package root (never inherited, never inside the checkout); stdin/stderr `DEVNULL`; stdout captured under a small byte cap; environment exactly §6; one attempt; AIDO's wait bounded **even if a descendant inherits the output handle** (the 5F2D-FU1 lesson — `subprocess.run(timeout=)`'s post-kill `communicate()` is not a bound). | **yes — first Pi code** | `PI_PROBE_FAILED` (start error, non-zero exit, timeout, cap) |
| **P4 post-probe re-proof** *(B3: identity-bound)* | Only if P3 ran. In this fixed order: (a) re-runs P2's complete seam walk via §7.2; (b) re-checks the package root's §7.2 identity against P1's capture — a root swapped for a same-named replacement between P2R and P4 fails (b) even if the replacement's seam bytes happen to match. P4's seam walk (a) replaces P's staged seam result (R4/B14: `pi_seam_digests_match` means exactly *"the last seam walk P completed matched"*; it is **not** a conjunction with identity, so a P4 refusal on (b) alone stages `true` — §5.1 lists both P4 tuples). Detects a persistent change to any seam file made while (or by) code executing in the probe, before any credential exists in memory. This remains strictly **post-probe tamper detection**; it does not and cannot substitute for P2R's pre-execution proof (B8/B11: "do not claim post-P3 detection closes a pre-P3 execution boundary" — P4 only ever runs after P3 has already executed something). | no | `PI_SEAM_CHANGED_DURING_PROBE` (seam walk **or** root identity failed after the probe) |
| **P5 version** *(B1, revised)* | Reached **only** if P1, P2, P2R, P3 and P4 all passed. stdout bytes must equal the ASCII pinned literal, optionally followed by one `\n` or `\r\n`, nothing else. The durable projection is a bounded literal: the pinned value, any other `x.y.z` literal, or `UNRECOGNIZED` (this stage was reached; output not a version literal) — or, when this stage is **never reached**, `NOT_OBSERVED`. **`NOT_OBSERVED` means exactly "no version projection was ever produced" — not "the probe never ran."** Those are two different, separately durable facts: `pi_observed_version == NOT_OBSERVED` records the first; `pi_version_probe_attempted` (set at P3, above) records the second. A P4 failure therefore truthfully yields `pi_version_probe_attempted == true` **and** `pi_observed_version == NOT_OBSERVED` at once (§5.1) — R1 conflated these two facts into one and that conflation was B1. Raw stdout is never retained. | no | `PI_VERSION_MISMATCH` |
| **P6 result** | A pass carries the identity object L14's `build_pi_argv` needs (`node_executable`, `pi_cli_js`, `pi_package_root`, `reported_version` — `ar2.launch.RuntimeIdentity`'s shape, constructed, not edited) plus the durable facts `pi_seam_digests_match`, `pi_version_probe_attempted`, `pi_observed_version` and (B7) `pi_identity_failure_code` (`null` on a pass), plus (B3) the §7.2 filesystem identities captured for `node.exe` and the package root — carried **in memory only**, for L14's re-proof (§7.1), and **never added to the durable schema** (§10). A refusal carries `pi_identity_failure_code` (one of the **six** table values above — `PI_RESOLUTION_FAILED`, `PI_SEAM_UNPROVEN`, `PI_IDENTITY_DRIFTED_BEFORE_PROBE`, `PI_PROBE_FAILED`, `PI_SEAM_CHANGED_DURING_PROBE`, `PI_VERSION_MISMATCH` — never `null`) plus P's staged seam result and version projection. *R3 said "five" in several places after adding the sixth code; every such count is corrected to six in R4.* **Commit discipline (R4/B14).** Pass or anticipated refusal, P **returns** one result object; it never raises for an anticipated failure. L1 validates that object's exact shape and then commits `pi_seam_digests_match`, `pi_observed_version` and `pi_identity_failure_code` **together**, as one sequence of plain assignments of already-validated values in which nothing can raise; for a refusal, `refused_at_step`/`pre_dispatch_refusal_code` are assigned in the same sequence. `pi_version_probe_attempted` is the one P fact that is **not** in that family: it is category B (§9.2a), written ahead at P3's entry and never reverted. **A genuinely unexpected exception inside P (or a result object of the wrong shape) is different: nothing of P's family is committed, the raise reaches L1's outer catch-all, and the record carries `pre_dispatch_refusal_code = "UNEXPECTED_STEP_FAILURE"` with `pi_identity_failure_code = null`** — the six codes are for P's six *anticipated* stage failures only (§5.1, §9.4). No exception text, `repr`, stdout, stderr, or absolute path crosses P's boundary. | — | — |

**Who creates each fact.** P1 creates the three paths and (B3) the two §7.2
filesystem identities, from filesystem metadata only. P2, P2R and P4 each
**stage** a seam result from AIDO-read bytes; the last one completed is the one
P returns (R4/B14 — staged, never committed piecemeal). P2R (B8/B11) creates no
durable fact of its own beyond that staged seam result — a P2R refusal is
recorded through `pi_identity_failure_code = PI_IDENTITY_DRIFTED_BEFORE_PROBE`
plus `pi_version_probe_attempted` staying `false` (§5.1). P3 creates
`pi_version_probe_attempted` (B1) at entry, from the fact of entry itself —
never from an outcome, and it is the only P fact written ahead rather than
committed with the family. P5 stages `pi_observed_version` from bytes the child wrote — a **claim by Pi-controlled
code**, attributable (same root, same `cli.js` that P2/P2R/P4 digested, same §7.2
identity) but not proof; its authority is only as a cross-check, because
`package.json`'s pinned digest already fixes the version string in the file.
Nothing in P takes a value from the environment other than `PATH` and
`SystemRoot`, from a CLI, from config, or from an authorization document.

### 5.1 Cross-field invariants by outcome (B1, corrected by B7/B8, rewritten R4/B14)

**R4 rewrite (B14).** R3's validator prose used facts no artifact carries —
"the raise occurred before P2R passed", "P5 was not reached" — while also
stating that P's internal cursor is not durable. A post-hoc validator cannot
check a fact that is not in the artifact. R4 therefore splits this section in
two, and **only the second half is validator input**:

- the **explanatory case table** says which internal stage produces which
  durable tuple — it is design rationale for implementers and reviewers, and
  its "stage reached" column is never read by any validator;
- the **validator rules R-P1…R-P6** are each a pure function of durable fields
  only.

R3's derived-invariant bullets that referenced hidden facts, and R3's
statement that `pi_identity_failure_code == null ∧ pre_dispatch_refusal_code
== OFFLINE_PREFLIGHT_FAILED` could describe "a P6 pass" (a pass has no refusal
code at all, so that conjunction cannot describe it), are **retracted**.

**Notation (durable fields only).** `K` = `refused_at_step`; `C` =
`pre_dispatch_refusal_code`; `F` = `pi_identity_failure_code`; and the P tuple
`τ = (A, S, V)` with `A` = `pi_version_probe_attempted`, `S` =
`pi_seam_digests_match`, and `V` the class of `pi_observed_version`:
`NO` (`NOT_OBSERVED`), `PIN` (exactly `PINNED_PI_VERSION`), `LIT` (any other
bounded `x.y.z` literal), `UNR` (`UNRECOGNIZED`). The P success tuple is
**σ = (true, true, PIN)**.

**Meanings that make the rules sound.** `S == false` means *"no committed seam
walk is known to have matched"* — either a walk was committed and did not
match, or nothing of P's family was committed at all; it never by itself means
"measured mismatch" (R3's resolution row already used it this way). `V == NO`
means *"no version projection was committed"*. `A` is category B (§9.2a):
written ahead at P3's entry, never reverted, and — unlike `S`/`V`/`F` — not
part of P's atomically committed family (§5 P6 row). Those three facts plus the
atomic commit are what make the reachable tuple sets below closed.

**Explanatory case table (rationale only — not validator input).**

| Case | Internal stage (not durable) | `A` | `S` | `V` | `F` | `C` |
|---|---|---|---|---|---|---|
| Resolution failure | P1 refuses | `false` | `false` (never measured) | `NO` | `PI_RESOLUTION_FAILED` | `OFFLINE_PREFLIGHT_FAILED` |
| Initial seam failure | P2 refuses | `false` | `false` (measured) | `NO` | `PI_SEAM_UNPROVEN` | `OFFLINE_PREFLIGHT_FAILED` |
| Drift before probe, seam bytes *(B8, widened B11)* | P2R step (a) refuses | `false` | `false` (P2R's walk, measured) | `NO` | `PI_IDENTITY_DRIFTED_BEFORE_PROBE` | `OFFLINE_PREFLIGHT_FAILED` |
| Drift before probe, object identity *(B8)* | P2R step (b) or (c) refuses | `false` | `true` (P2R's walk passed) | `NO` | `PI_IDENTITY_DRIFTED_BEFORE_PROBE` | `OFFLINE_PREFLIGHT_FAILED` |
| Probe failure | P3 refuses (start, exit, timeout, cap) | `true` | `true` (P2R's walk) | `NO` | `PI_PROBE_FAILED` | `OFFLINE_PREFLIGHT_FAILED` |
| Post-probe seam change | P4 step (a) refuses | `true` | `false` (P4's walk) | `NO` | `PI_SEAM_CHANGED_DURING_PROBE` | `OFFLINE_PREFLIGHT_FAILED` |
| Post-probe root identity change | P4 step (b) refuses | `true` | `true` (P4's walk passed) | `NO` | `PI_SEAM_CHANGED_DURING_PROBE` | `OFFLINE_PREFLIGHT_FAILED` |
| Version mismatch | P5 refuses | `true` | `true` | `LIT` or `UNR` | `PI_VERSION_MISMATCH` | `OFFLINE_PREFLIGHT_FAILED` |
| P success, then Git resolution refuses | after P's success commit | `true` | `true` | `PIN` | `null` | `OFFLINE_PREFLIGHT_FAILED` |
| P success, run continues | after P's success commit | `true` | `true` | `PIN` | `null` | absent, or an L2–L18 code |
| Unexpected raise before P3's entry | P1, P2, P2R, or between P2R and P3's entry | `false` | `false` (family not committed) | `NO` | `null` | `UNEXPECTED_STEP_FAILURE` |
| Unexpected raise at/after P3's entry, before P's commit | P3, P4, P5, P6 construction, or result-shape validation | `true` | `false` (family not committed) | `NO` | `null` | `UNEXPECTED_STEP_FAILURE` |
| Unexpected raise after P's success commit | rest of L1 (Git resolution) | `true` | `true` | `PIN` | `null` | `UNEXPECTED_STEP_FAILURE` |

**Allowed tuples per P code (the durable table the validator uses).**

| `F` | `Allowed(F)` |
|---|---|
| `PI_RESOLUTION_FAILED` | `{(false, false, NO)}` |
| `PI_SEAM_UNPROVEN` | `{(false, false, NO)}` |
| `PI_IDENTITY_DRIFTED_BEFORE_PROBE` | `{(false, false, NO), (false, true, NO)}` |
| `PI_PROBE_FAILED` | `{(true, true, NO)}` |
| `PI_SEAM_CHANGED_DURING_PROBE` | `{(true, false, NO), (true, true, NO)}` |
| `PI_VERSION_MISMATCH` | `{(true, true, LIT), (true, true, UNR)}` |

and the closed unexpected-L1 set **U = {(false, false, NO), (true, false, NO), σ}**.

**Validator rules — each a pure function of `K`, `C`, `F`, `τ`.**

- **R-P1 (domains).** `F ∈` the six codes `∪ {null}`; `A`, `S` exact bools;
  `V` in its closed domain (§10).
- **R-P2 (EXPECTED P REFUSAL).** `F ≠ null ⇒ K == "L1" ∧ C ==
  OFFLINE_PREFLIGHT_FAILED ∧ τ ∈ Allowed(F)`.
- **R-P3 (anticipated L1 refusal P does not own).** `K == "L1" ∧ C ==
  OFFLINE_PREFLIGHT_FAILED ∧ F == null ⇒ τ == σ`. This is the Git-resolution
  refusal, the only anticipated L1 refusal after P's success commit; it is the
  **only** meaning `F == null ∧ C == OFFLINE_PREFLIGHT_FAILED` can have.
- **R-P4 (UNEXPECTED L1 FAILURE).** `K == "L1" ∧ C == UNEXPECTED_STEP_FAILURE
  ⇒ F == null ∧ τ ∈ U`. The validator checks membership in a closed set of
  three reachable tuples and **claims nothing about which hidden internal P
  stage raised**: `(false, false, NO)` says only "before P3's entry",
  `(true, false, NO)` only "at or after P3's entry, before P's commit", `σ` only
  "after P's success commit".
- **R-P5 (P SUCCESS, run past L1).** `K` absent, or `K ≠ "L1"` ⇒ `F == null ∧
  τ == σ`. Covers every REFUSAL-mode record at L2–L18 and every
  POST_DISPATCH_UNEXPECTED and NO_DISPATCH_FAILURE record (§9.2): nothing past
  L1 is reachable without P's success commit.
- **R-P6 (L1 code domain).** `K == "L1" ⇒ C ∈ {OFFLINE_PREFLIGHT_FAILED,
  UNEXPECTED_STEP_FAILURE}` — already §9.4's step/code table; restated so
  R-P2…R-P5 are visibly exhaustive.

**Exhaustive and mutually exclusive.** For any record: `F ≠ null` → only R-P2
applies (and it forces `K`, `C`); `F == null ∧ K == "L1"` → by R-P6 exactly one
of R-P3 / R-P4; `F == null ∧ K ≠ "L1"` (incl. absent) → R-P5. Any record that
satisfies none — e.g. `F = PI_PROBE_FAILED` with `A == false`,
`F = PI_SEAM_UNPROVEN` with `C = UNEXPECTED_STEP_FAILURE`, `F ≠ null` at `K =
"L7"`, `C = UNEXPECTED_STEP_FAILURE` at L1 with `τ = (true, true, NO)`, or a
post-L1 record whose `V ≠ PIN` — fails self-validation (`RECORD_INVARIANT`,
halt).

**Why no progress field is added.** A `pi_identity_progress` enum would let the
validator name the exact internal stage of an unexpected raise. No consumer
needs that: the lifecycle, classification and halt outcome of every U tuple is
identical (§8 case A), and the three U tuples already separate "Pi code never
ran" from "Pi code may have run" — the one distinction with safety meaning,
carried by `A`. The smaller schema is kept.

**What distinguishes a resolution failure from an initial seam failure
(B7's second finding, closed in R3, unchanged).** The three original facts
alone produce the **identical** tuple `(false, false, NO)` for both — and, as
of R4, for a seam-byte P2R failure and for an unexpected raise before P3 too.
Only `F` (and, for the unexpected case, `C`) distinguishes them. This is why B7
required the field.

**Boolean-algebra discipline (B6, restated here because §5.1 is exactly where
R2's earlier flawed pattern originated).** None of the rules above is written
as an unconditional two-way iff across an *absence* the way R2's §9.4 bullet
was; each rule is an implication from a fully specified `(K, C, F)` premise,
and the premises partition the record space as shown. §9.4 restates this
discipline in general form for the three top-level failure-shape fields.

**Why the probe is kept at all.** The pinned `package.json` digest already
implies version `0.85.1` in the file. The probe's remaining, frozen value
(§16.2 L1, AR0 U-1) is: Node-direct launch of this `cli.js` by this `node.exe`
works, and the running `cli.js` reports the version of the root P2 proved. It
may run only after P2 and the final P2R proof, and nothing it says can widen
what they proved.

**Derivation obligation (blocking for implementation, OC-3).** Whether 0.85.1's
`--version` path reads Pi settings/models/auth (under `~/.pi/agent`, which the
OS resolves from the account token even with no `USERPROFILE`), reads
project-local `.pi/` under cwd, writes anything, or attempts any network access
before printing, has **not** been derived: the frozen §1.2 inspection did not
cover it, and 0.85.1 is not currently installed. The implementation phase must
derive it from the pinned `dist/cli.js`/`dist/main.js` bytes. If `--version`
touches any of those before printing, the implementation **stops and returns to
design** (decision D-6) rather than improvising a disposable agent directory.

---

## 6. Secret-free identity/version child environment

The probe child receives a **freshly constructed** mapping, passed explicitly
as the process environment. "Inherit" is not a reachable state: the runner leaf
refuses to start if handed anything but an exact `dict` built by this builder
(a `None` environment means inheritance and is refused, not defaulted).

| Name | Value | Why it is required |
|---|---|---|
| `SystemRoot` | copied **by name** from the ambient mapping; absent → refuse | Windows system-component resolution for any Win32 process (system DLL paths, crypto/RNG providers used at Node/OpenSSL start-up). Its absence could only make the probe fail — a closed failure before consumption, never a pass. |
| `PI_OFFLINE` | literal `1` | Pi's own request-offline control, identical to L12. Non-secret. |
| `PI_SKIP_VERSION_CHECK` | literal `1` | Pi's own update-check suppression, identical to L12. Non-secret. |
| `PI_TELEMETRY` | literal `0` | identical to L12. Non-secret. |

Nothing else, and specifically **not**: `PATH` (Node is invoked by absolute
path; `--version` needs no spawn; an absent `PATH` makes an unexpected spawn
fail rather than resolve something), `PATHEXT`/`ComSpec` (shell only),
`TEMP`/`TMP`, `USERPROFILE`/`HOME`/`APPDATA`/`LOCALAPPDATA`/`HOMEDRIVE`/`HOMEPATH`,
every `NODE_*` name (`NODE_OPTIONS` would execute `--require`/`--import` code
**before** `cli.js` — code the seam proof never saw; `NODE_PATH` redirects module
resolution), `AIDO_LITELLM_BASE_URL`, `PI_QUALIFICATION_B300_ROUTE_KEY`,
`AIDO_LITELLM_API_KEY`, every other `AIDO_*`, every `*_API_KEY`/`*TOKEN*`/
`*SECRET*`/`*PASSWORD*`/`*CREDENTIAL*` name, cloud/database credentials, and
proxy settings. Adding any name requires a failing offline derivation and a
review; it is never added to make a probe pass.

**Mechanical, not conventional.** (1) The allowlist is positive: exclusion
needs no knowledge of the excluded names, so no ambient value is ever read to
decide anything — the builder performs exactly one lookup, by name, for
`SystemRoot`. (2) After construction the name set is asserted **equal** to the
allowlist and re-audited against `environment.FORBIDDEN_NAME_FRAGMENTS` by
name. (3) The leaf is the only code that starts the probe, and it takes the
built object, not a mapping. (4) Windows name-case: `os.environ` lookups are
case-insensitive and a plain `dict` copy is not; the builder must look up
`SystemRoot` in a way that is correct for both, and a test pins it.

**Other inherited channels, and the honest limit.** Command line: no secret.
Handles: Python on Windows starts children with `close_fds=True`; only the three
standard handles are passed (stdin/stderr `DEVNULL`, stdout a pipe). cwd: set
explicitly, never inside the checkout (a `.env` or `.pi/` there is unreachable
by relative lookup). **This is a statement about what AIDO hands the child, not
confinement.** The child runs as the same user and can, by ordinary OS means,
open the parent process and read its memory — including the parent's own
environment block, which does contain the credential names in a live launch —
or read the user's files and registry. Nothing here claims the child *cannot*
obtain a secret; it claims AIDO gives it none through any channel AIDO
controls. What bounds that exposure is §5's order: only after P2 has proved,
and P2R has finally re-proved, the pinned seam set may any Pi code run at all
(and see OC-2 for what neither covers).

---

## 7. Pre-consumption Pi identity gate

### 7.1 Gate semantics, placement, TOCTOU

**Semantics.** One read-only public entry in the CFG1 package that calls P with
the genuine leaf bindings — the **same** bindings `default_cfg1_run_ports`
gives L1, reached through the same function object, so the two cannot disagree
by construction. It:

- reads no credential or endpoint (P reads only `PATH` and `SystemRoot`);
- performs no network operation itself, and gives the probe child neither
  endpoint nor credential; it does **not** claim the child made no network
  attempt (not a network sandbox);
- writes nothing (the launcher already runs `-B` with an empty pycache prefix;
  P writes nothing; the probe child's own writes are covered by the D-6
  derivation);
- never calls `establish_stage_output_authority`, never touches `RESULTS_ROOT`,
  never mints a run workspace, config issuance, or executor binding;
- returns one closed code — pass or a P code — and **nothing reusable**: no
  identity object, token, digest set, or timestamp leaves it. `run_cfg1_stage`
  has no parameter that could accept one, so a stale admission observation
  cannot be trusted by construction.

**Placement** (AM-7): in a future authorization's launcher, after G6 and before
the consumption boundary; a refusal prints the one closed code, exits non-zero,
and does not call `establish_stage_output_authority`, so the authorization is
not consumed. The gate's module is part of the audited lineage (G4/G5). The
launcher text will read `PATH` and `SystemRoot` values (non-secret) — the
future authorization must say so, since A3's launcher "reads no environment
variable value".

**Why not enforce it inside `establish_stage_output_authority`?** It would make
the gate unbypassable by a supported caller, but (a) it changes a frozen §16.3
signature/contract, and (b) under the A-series consumption definition the first
call to that function consumes the authorization even when it refuses — so the
gate would stop protecting the thing it exists to protect. Skipping the gate is
not a safety failure: L1 still refuses before any Pi code or credential; it
only wastes the authorization, which is the status quo. Rejected for this phase.

**TOCTOU, stated.** Between the gate (T₀) and L1 (T₁ — authority
establishment plus L0, typically well under a second) a same-user process can
change the Pi installation. Cases:

| Mutation | Consequence |
|---|---|
| persistent drift after T₀ | L1 re-proof refuses at L1 before any Pi code or credential. Authorization **consumed** — the unavoidable cost. Record: `REFUSED_PRE_DISPATCH` at L1, lifecycle closed, halt `PRE_DISPATCH_REFUSAL`. |
| transient swap between T₀ and T₁, restored by T₁ | invisible and harmless: nothing executes Pi in that window. |
| swap **or in-place edit** between P1/P2 and P3's `CreateProcess` *(B8, closed; widened R4/B11)* | **No longer executes undetected.** R2 only had P4 (post-probe) and L14 (pre-second-execution) — neither protects the probe's own *first* execution (B8). R3's P2R re-checked only the two object identities, so an in-place edit or same-directory replacement of a pinned seam file under an unchanged package root still reached P3 (B11). R4's P2R (§5) is the **final** pre-`CreateProcess` proof and covers **both** kinds of fact: (a) the complete pinned seam set, re-walked and re-digested; (b) the package-root identity; (c) the `node.exe` identity. Caught before execution: a changed `dist/cli.js` (or any pinned seam file) under the same root; a `node.exe` swap anywhere after P1; a package-root swap whose 20 pinned files are byte-identical. Residual, stated and not claimed closed: the sliver from each P2R read to `CreateProcess` — for an early-walked seam file, from the moment P2R (a) read it — the same honest shape as every other check→use gap in this table. |
| **same-pathname, different-file swap, any time up to and including L14** *(B3, closed)* | Caught, **including when the replacement's bytes are made to collide with the pinned digest**: §7.2's captured file identity (volume serial + 128-bit file id) is bound at P1 and re-checked, not just re-hashed, at P2R (before the first execution), at P4, and again at L14 (below). A delete-and-recreate at the identical path yields a new file id on NTFS even when the new file's bytes are identical to the old one's, so this class of swap is detected by identity mismatch even where a seam-digest-only re-proof would not have caught it. |
| swap between L1 and L14 (seconds, spans the credential read) | **with D-4, and now with B3's identity binding**: immediately before L14 spawns Pi, AIDO re-runs P2's seam check **and** re-checks §7.2 identity for both the resolved `node.exe` and the package root against what P1 captured — a mismatch on either refuses `RUNTIME_LAUNCH_FAILED` at L14, no spawn (§5 P4 row; AM-8). The window in which an undetected swap-and-restore could occur shrinks to "L14's own re-proof → `CreateProcess`" (milliseconds). This is what makes the claim "the pair L14 launches is exactly the pair P3 proved" mechanically true, up to that residual millisecond window — the design must never claim more than that. |

Closing the **residual** windows (transient swap-and-restore fully inside a
check→use gap, at either P2R's final proof→P3's `CreateProcess` or at L14's own
re-proof→spawn)
needs OS-level locking of the Pi tree for the run's lifetime (share-mode
handles), a private copy of the package, or confinement — each a new mechanism
this phase does not add. The operator rule stays: no other writer against the
Pi installation or the checkout during admission and execution. The gate is
waste avoidance; L1's P2R (first execution), D-4 (second execution) and §7.2
carry the pre-execution security claims; P4 is post-probe tamper detection.

### 7.2 No-follow filesystem inspection primitive (B3)

One CFG1-owned, offline-testable leaf primitive, used by P1 (resolution), P2,
P2R and P4 (seam proof, final pre-execution proof, and post-probe re-proof),
and L14's pre-spawn re-proof (AM-8) — the
single mechanism every no-follow/identity claim in §5 and §7.1 depends on.
Referenced elsewhere in this document as **§7.2**.

**Contract.** Given one lexical path, without ever following a reparse point
and without executing anything:

1. **Topology, no-follow.** Open the path with reparse-point-aware,
   backup-semantics flags (`FILE_FLAG_OPEN_REPARSE_POINT |
   FILE_FLAG_BACKUP_SEMANTICS`) so a symlink, junction, or mount point is
   observed **as itself**, never transparently traversed. Classify the result
   as exactly one of: `regular_file`, `directory`, `reparse_point`, `missing`,
   or `other` (device, pipe, or any type outside those four). A caller that
   requires `regular_file` (e.g. `node.exe`, `pi.cmd`, a seam file) or
   `directory` (a `PATH` entry, a package-root candidate, a seam-walk
   component) treats every other classification as a refusal for that
   candidate — **including `reparse_point`, unconditionally, before any
   attempt to resolve where it points.**
2. **Stable identity, only for a classification the caller accepted.** For a
   candidate that passed step 1 as `regular_file` or `directory`,
   `GetFileInformationByHandleEx` with `FileIdInfo` returns the volume serial
   number and the 128-bit file id. This pair is the captured "§7.2 identity"
   referenced throughout §5 and §7.1. It identifies the on-disk file/directory
   **record**, not its pathname and not its content — a delete-and-recreate at
   the same path is a different identity; an in-place content edit of the same
   record is the same identity (caught instead by the seam digest, §5
   P2/P2R/P4 — which is exactly why R4's P2R must re-digest and not only
   re-check identity, B11).
3. **Re-proof.** Given a previously captured identity and a lexical path,
   re-run steps 1–2 and compare the newly captured identity to the one held;
   equal ⇒ match, anything else (including a classification change, e.g. the
   path now resolves to `missing` or `reparse_point`) ⇒ mismatch.

**Explicitly required by this contract, not left implicit:**

- No step above opens the target for execution, and no step follows a reparse
  point to reach what it points to — a `reparse_point` classification is a
  terminal answer about that one lexical entry, never a hop to another check.
- `pi.cmd` and `node.exe` candidates are held to exactly `regular_file`; a
  directory or reparse point at either name is refused as that candidate, with
  no fallback search (§5 P1's "first candidate only" rule still applies — a
  refused candidate is never retried against a later `PATH` entry inside the
  **same** resolution pass for the **same** name).
- Every `PATH` entry and every seam-walk directory component is held to
  exactly `directory`.
- This primitive performs **no** containment check of its own (§5 P1 does that
  separately, on both the lexical and the realpath'd form); it answers only
  "what, mechanically and without following anything, is at this one lexical
  path, and is it still the same on-disk record as before."

**Offline testability.** Like every other leaf in P, this primitive is
injected, not hard-coded — a double can substitute a synthetic
junction/reparse/identity-change scenario under `tmp_path` without a real
`node.exe` or Pi installation (§11 tests I, J).

**Scope, stated once.** §7.2 binds *filesystem record identity*, not file
*content* beyond what §5 P2/P4 already digest, and not Node's own binary
content or version. **A full Node content/version pin is NOT required by this
finding and is not added here** — see OC-2, which already scopes "the frozen
Pi identity is the 20-file seam set; everything else under the package root
(and Node itself) is unpinned yet executes." §7.2 closes the *swap* class of
attack (a different file answering at a proven-good path); it does not
re-open, and must not be read as re-opening, OC-2's separate, larger, and
explicitly deferred question of pinning Node or the rest of the Pi package.

---

## 8. Workspace lifecycle state model

One executor-owned, in-memory, write-ahead fact **W**, projected durably in v2:

| W | Set when | Meaning | L27 obligation | Lifecycle |
|---|---|---|---|---|
| `NOT_ATTEMPTED` | initial value | the mint port was never called | none — nothing to close | workspace conjunct holds |
| `ATTEMPTED_NO_AUTHORITY` | assigned **immediately before** the mint port is invoked, before any of its side effects | a tree may exist; no genuine authority reached the run | L27 records failure; **nothing deleted, ever**; nothing inferred from a path | `L27` failure → `INDETERMINATE_LIFECYCLE` |
| `AUTHORITY_RETURNED` | the port returned exactly a 2-tuple whose first member is exactly a `Cfg1RunWorkspace` owned by the `run_workspace` registry (registry membership, never a path) | the run holds a genuine ownership handle | L27 re-proves and removes, exactly as today | existing predicate: `reproved ∧ removed ∧ residual == 0` |

Rules:

- **Write-ahead, not inference.** W moves to `ATTEMPTED_NO_AUTHORITY` before
  the call, so an exception, a partial tree, a malformed return, or a crash
  inside the port can never leave `NOT_ATTEMPTED` behind. W never moves
  backwards.
- **Shape failures are partial mints.** A malformed return (wrong arity, a
  foreign workspace type, a genuine workspace inside a malformed tuple) stays
  `ATTEMPTED_NO_AUTHORITY`: the executor never "extracts" a handle from a
  malformed result. If the port did register a genuine record, the independent
  process-level fact `minted_workspace_count() != 0` already halts the stage
  (§19.1 item 4) — a second, independent witness.
- **Ownership is only ever the registry's.** `AUTHORITY_RETURNED` never grants
  deletion by itself: L27 still re-proves against the filesystem marker, and a
  re-proof failure is a lifecycle failure with the tree left in place.
- **L27's decision reads W, never `refused_at_step`.** The durable record
  carries both, and the v2 validator requires them to agree (§10).
- **Other resources are unchanged.** Runtime, broker, scrub and verification
  facts already carry "not created" semantics (`runtime_created`,
  `broker_resource_created`, the scrub facts initialised true,
  `verification_child_reaped_or_not_started`). W brings the workspace into line
  with them; no other lifecycle fact changes.

Outcome per DIAG1 case: **A** (L1 refusal) → W `NOT_ATTEMPTED`, closed,
`REFUSED_PRE_DISPATCH`, halt `PRE_DISPATCH_REFUSAL`. **B** (mint raises) → W
`ATTEMPTED_NO_AUTHORITY`, `L27`, `INDETERMINATE_LIFECYCLE`, halt
`LIFECYCLE_CLOSURE_UNPROVEN`, orphan untouched. **C** (genuine workspace, later
refusal) → W `AUTHORITY_RETURNED`; teardown success → closed; teardown or
re-proof failure → `L27`, unproven.

---

## 9. Failure-attribution model

### 9.1 Step cursor

The executor owns one monotonic cursor over `L1…L20`. It is advanced at each
step's **entry, before that step's first side effect**, and is written by
nothing else — never from an exception, a port return, or a refusal object.
Consequences that make attribution trustworthy:

- **`refused_at_step`, when present, is always the cursor's value** *(B2:
  narrowed from "always present" to "present iff a genuine refusal occurred,
  and correct whenever it is present")*. A `_PreDispatchRefusal`'s own `step`
  argument becomes redundant when the field is written; if the two ever
  differ, the cursor wins and the record fails its own v2 validator via the
  step/code table below (→ `RECORD_INVARIANT`, halt). An executor bug can make
  a record refuse; it cannot make one lie about how far the run got. The
  field's presence is governed by §9.2's two categories, not by the cursor's
  mere existence — the cursor itself is tracked at every step, always, but it
  is only ever **copied into this durable field** for a genuine refusal.
- Because L2 is entered before the mint and L4 before the credential read, a
  refusal at `L1` proves no mint was attempted, and a refusal at `L1`–`L3`
  proves no credential value was read — as a property of the ordering, backed
  for the workspace by W.

### 9.2 Unexpected exceptions *(B2: two mutually exclusive durable fields, never both)*

The catch-all remains (the executor stays total) but writes no L1 claim, and —
corrected from R1 — a post-dispatch unexpected failure now has its **own**
bounded durable field rather than being silently unrepresentable:

| Where the cursor is | Category (§9.2a) | Durable result | Mode (below) |
|---|---|---|---|
| `L1…L18`, dispatch **not yet** attempted, **and an unexpected raise occurred** | anticipated-refusal-shaped: an **unexpected** failure, but one that is mechanically indistinguishable from a genuine pre-dispatch refusal because nothing was dispatched | `refused_at_step = cursor`, `pre_dispatch_refusal_code = UNEXPECTED_STEP_FAILURE` (new closed code, valid at any refusal step; v2). `unexpected_failure_step` is **absent**. | **REFUSAL** |
| `L18` **with** dispatch already attempted (write-ahead already fired, §9.3), or cursor ∈ `{L19, L20}`, **and an unexpected raise occurred** | genuinely post-dispatch: a prompt write may already have reached Pi, or the turn already ran | **no** refusal code, `refused_at_step` **absent**; `unexpected_failure_step = cursor` (**new** v2 field, nullable, closed domain `{"L18","L19","L20"}` — bounded to the dispatch/turn-observation/projection steps this field exists for; a closure-phase (`L21`+) unexpected failure is D-5/OC-4's separate, already-tracked concern and is deliberately **not** folded into this field). `dispatch_state` stays as written ahead; every observation the failing step had not yet committed stays at its fail-closed initial value (§9.2a category A); every authority/lifecycle fact already write-ahead-committed (§9.2a category B) is unaffected. Classification follows §12 (e.g. `INDETERMINATE_DISPATCH` or `INDETERMINATE_NO_ACTIVITY_EVIDENCE`). | **POST_DISPATCH_UNEXPECTED** |
| any step, **no exception at all** — dispatch either never needed to run (an anticipated `_PreDispatchRefusal` also lands here, see below) or ran and the turn completed normally | no exception occurred in `_dispatch_phase`; either an anticipated refusal (its own typed object, not this catch-all) or a clean pass to closure | See "Three modes" below — this is **not** a row of the catch-all table (nothing unexpected happened), listed here only so the table is visibly exhaustive against §9.4's field triple. | **NO_DISPATCH_FAILURE** (clean pass) or **REFUSAL** (anticipated) |

**Three exact, mutually exclusive modes (B6 — replaces R2's flawed
unconditional iff chain).** R2's §9.4 stated
`pre_dispatch_refusal_code present ⇔ refused_at_step present ⇔ unexpected_failure_step absent`
as if it were one chain of biconditionals. It is not: read as written, the
second `⇔` forces `refused_at_step` **absent** to imply
`unexpected_failure_step` **present** — which rejects a clean run, where all
three fields are legitimately absent at once. (This flaw was introduced in
R2 itself, fixing B2; it was not present in R1, which had no
`unexpected_failure_step` field to state an iff over.) The corrected model is
three modes, exactly one of which holds for every terminal `_dispatch_phase`
outcome:

1. **REFUSAL** — `pre_dispatch_refusal_code` present, `refused_at_step`
   present, `unexpected_failure_step` **absent**. Covers both an anticipated
   `_PreDispatchRefusal` (any of the codes in §9.4's step/code table) and the
   row-1 catch-all case (`UNEXPECTED_STEP_FAILURE`).
2. **POST_DISPATCH_UNEXPECTED** — `pre_dispatch_refusal_code` **absent**,
   `refused_at_step` **absent**, `unexpected_failure_step` present. The
   row-2 catch-all case only.
3. **NO_DISPATCH_FAILURE** — all three fields **absent**. The ordinary clean
   pass through `_dispatch_phase` into closure, with no refusal and no
   unexpected raise at all. **R2 rejected this mode**; it is the specific
   defect B6 requires fixing.

**The only direct iff, stated once and never generalized further:**
`pre_dispatch_refusal_code` present ⇔ `refused_at_step` present (both are
written together, by the same code path, in every REFUSAL-mode record — this
much of R2's chain was correct and is kept). **Do not infer REFUSAL merely
from `unexpected_failure_step` being absent** — `unexpected_failure_step`
being absent is also true of NO_DISPATCH_FAILURE, which is not a refusal.
Presence/absence of `unexpected_failure_step` alone never determines which of
the other two fields hold; the three modes above are checked as a whole
triple, never pairwise.

Always: the existing console code `RUN_STEP_RAISED_UNEXPECTEDLY`; no exception
type, text, `repr`, traceback, or attribute of the exception is read or kept;
no truthiness of a port value decides anything. **Step-local commit — scoped
to category-A semantic observations only (§9.2a):** a step stages its
semantic-observation writes and commits them only when the step completes, so
a raise mid-step cannot leave a half-projected observation family that reads
as observed. This rule **does not** apply to category-B authority/lifecycle
facts, which are write-ahead by design and are never rolled back merely
because the step that guards them did not complete — §9.2a states the two
categories explicitly, because R1's blanket phrasing of this sentence
contradicted §8's and §9.3's own write-ahead mechanisms (B4).

### 9.2a Semantic observations vs. authority/lifecycle facts (B4)

R1 stated "a step stages its observation writes and commits them only when
the step completes" as if it were one universal rule. It is not, and stating
it that way contradicted two mechanisms R1's own design already required: W
(§8) moves to `ATTEMPTED_NO_AUTHORITY` **before** the mint call, and dispatch
write-ahead (§9.3) sets `dispatch_state = SEND_STATE_INDETERMINATE`
**before** `send_command`. Both are commits that happen *before* the step
they describe even attempts its side effect — the opposite of "only when the
step completes." B4 requires this design to say explicitly, by name, which
facts follow which rule.

**Category A — semantic observations.** Facts *about* the environment or
inputs that a step reasons over, where a half-formed observation would be
actively misleading (e.g. "one of three seam digests matched" is not a
meaningful intermediate state). Staged during the step, **committed
atomically only on that step's own successful completion**; a raise mid-step
leaves the whole family at its fail-closed initial value. Examples:
`pi_seam_digests_match`, `pi_observed_version`, `h1_extension_identity_matched`,
`h2_provider_model_identity_matched`, `manipulation_check_agrees`, baseline
verification results, config-shape checks.

**Category B — authority/lifecycle/write-ahead facts.** Facts about whether
AIDO **itself may have caused a side effect that now needs cleanup or
accounting** — a resource creation, a registry entry, a dispatch attempt.
These are **monotonic**: written before or at the moment of the side effect
they guard, **never** reset to a "safe" value by a later failure, and they
**survive** the step that was attempting the effect raising partway through.
"Partial creation must always increase cleanup obligations, never erase
them" is the governing rule; a category-B fact is written pessimistically
(assume the effect may have happened) rather than optimistically (assume it
did not, absent proof). Mechanically, exactly six families, with their
write-ahead point and shipped-executor status as of the `bfae384…` baseline
this design corrects:

| Family | Write-ahead point | Field(s) | Status against shipped `run_executor.py` |
|---|---|---|---|
| Workspace mint | immediately before `ports.mint_workspace(...)` | `workspace_mint_state` (W, §8) | **already correct** in R1's design (§8); shipped v1 had no equivalent and DIAG1 D2 is exactly this gap for workspace |
| Dispatch attempt | immediately before `send_command` | `dispatch_state`, `prompt_writes` (§9.3, AM-5) | **already correct**, confirmed against the shipped L18 code path (DIAG1 D4 path 2) |
| Broker resource | on exception from `server.start()`, before re-raising, **and** on success | `broker_resource_created` | **already correct**: shipped code (`run_executor.py:663-668`) sets it `True` inside the `except` block before re-raising, so no exception path leaves it at its fail-closed `False` after a `start()` that may have bound the pipe |
| Runtime process | on exception from `build_supervisor`/`launch()` (conditioned on whether a `process` attribute is observably set), and on success | `runtime_created` | **already correct**, same pattern (`run_executor.py:679-683`) |
| Verification child | on exception from `ports.run_verification(...)` (caught, then the field is set to the conservative "not reaped" value), and from the observed return code otherwise | `verification_child_reaped_or_not_started` | **already correct in effect** (fail-closed on the caught-exception path, `run_executor.py:965-973`), though it is set **after** the call returns/raises rather than strictly before it — acceptable here only because the call is itself already bounded and reaped-or-abandoned per the accepted 5F2D/5F2D-FU1/FU2 contract, which this design does not reopen |
| **Config issuance/creation (L9)** | *(B9, corrected — R2's model was wrong)* N/A — no CFG1-side write-ahead needed | **no new field; `config_issuance_possibly_created` is REMOVED** | **not a gap.** R2 modeled L9 from an arbitrary injected `write_config` double raising arbitrarily and treated that as evidence about the genuine generator. It is not: the real implementation, `cfg1_pi_config.py::write_cfg1_pi_config`, registers its issuance (`config_issuance.register_config_issuance`) as the **very last operation before `return`**, and — per its own `finally` block (`cfg1_pi_config.py:398-454`, citing `CFG1-IMPL-FU4-FU1`) — if a *genuine* token was registered and any subsequent release step then fails, that `finally` block calls `config_issuance.discard_config_issuance(token)` **before** raising its own closed code, on **every** supported exit path. `register_config_issuance` itself (`config_issuance.py:250-267`) is transactionally sound at its own boundary too: the registry dict write `_ISSUED[token] = _IssuanceRecord(...)` is the last statement before `return token`, so no code path registers an entry and then raises before returning it. **The existing caller-visible handle already is the correct authority signal**: `state.generated_config is not None` ⟺ L9 returned normally ⟺ (by FU4-FU1) an issuance may genuinely be ACTIVE and owed cleanup; `state.generated_config is None` (any L9 raise) ⟺ (by the same guarantee) no issuance is ACTIVE, so nothing needs discarding. A caller-side boolean would have been, at best, redundant with this and, at worst (as B9 states), "evidence only" with no cleanup authority of its own — R2's field was both unnecessary and inert. **R4 scope note (B13):** this row is about *issuance authority only*. It proves nothing about whether the written bytes equal the pinned arm shape — R3's OC-10 claim that it did is retracted, and the new step 9a (§9.2b) supplies that proof. **R5 scope note (OC-11):** the issuance-authority finding in this row stands unchanged, but it is *not* the whole L9 story — a failure after the endpoint bytes were attempted leaves an endpoint-bearing `models.json` that no issuance covers. That is a separate category-B fact with its own write-ahead, closed in §9.2c (`generated_config_scrub_verified := False` before the call; the writer's own `endpoint_material_outstanding`). |
| **Extension creation (L11)** | *(B9; **redesigned R4/B12**)* `extension_binding_scrub_verified := False` immediately before the writer is called; inside the writer, a writer-local `token_write_attempted := True` immediately before the token-bearing write | **no new durable field.** R2's `extension_possibly_created` stays removed; **R3's `extension_failure_path_scrub_verified` is RETRACTED** (§10). The existing `extension_binding_scrub_verified` carries the obligation, set only from handle-bound actions (below) | **genuine gap, and R3's fix was not authority.** The frozen `write_disposable_extension` (`ar2/pi_config.py:156-193`) has no transactional discipline: `mkdir`, per-file `shutil.copyfile`, then a plain `Path.write_text` of the **token-bearing** `ar2_config.ts`, with no `finally`, no registry, no identity. The frozen `scrub_generated_extension_config` (`:196-218`) derives `ar2_config.ts` **by pathname**, `is_file`/`chmod`/`unlink`s whatever answers there, and "verifies" by pathname absence — no issuance, no identity, no handle. Feeding it a path precomputed from a genuine root does **not** make the pathname authority over the object now at that name. R4 replaces both, for CFG1 only, with a CFG1-owned transactional writer and an extension issuance (below, AM-9/AM-10). |

**L11/L24 design, R4 (B12): a CFG1-owned transactional extension writer, an
extension issuance, and an identity-bound L24.**

*R3 retraction.* R3 had L11's failure path call the frozen
`scrub_generated_extension_config(extension_dir)` and record its
`generated_binding_file_removed` bool, and called that "genuine cleanup
authority". It is not: the call deletes whatever object answers at
`<root>\pi_extension\ar2_config.ts`, including a same-name replacement AIDO
never wrote, and the bool is the scrubber's own pathname observation. R3 also
left the **success-path** L24 scrub on the same pathname-only helper
(`run_executor.py:1099-1134`: realpath containment, then the frozen scrubber).
Both are withdrawn. Governing rules for R4, in every path: **a bool is
evidence, never deletion authority; no same-name replacement is ever deleted
as though AIDO created it; partial creation can only increase obligations.**

*Mechanism (names illustrative; all CFG1-owned, e.g.
`experiments/pi_harness_cfg1/cfg1_extension.py` and `extension_issuance.py`).*
The writer mirrors the accepted L9 discipline (Sec. 37.3.1, FU15/FU4/FU4-FU1),
using the same `win_config_authority` primitives, so it introduces no new kind
of Win32 authority — only a second, separately bound user of it (AM-10).

- **Inputs.** A genuine ACTIVE `Cfg1RunWorkspace` — never a path; the extension
  directory is derived from its re-verified `experiment_root` plus the fixed
  literal `pi_extension`, in one derivation function with no path parameter
  (the `derive_cfg1_config_paths` pattern). The broker binding values
  (`pipe_name`, `capability_id`, token) in memory only.
- **Frozen static material — independently pinned, read once, never re-read
  (R5/B16, AM-14).** The static sources are exactly the frozen
  `EXTENSION_SOURCE_FILES` — the strict four-name set `ipc.ts`, `tools.ts`,
  `index.ts`, `package.json` — never a directory listing, a glob, or an extra
  name. For **each** name CFG1 owns an **independent literal**: the exact byte
  size and the SHA-256 of the reviewed bytes (table in §9.2c). For the
  generated file, CFG1 owns the SHA-256 of the UTF-8 encoding of the frozen
  `_GENERATED_CONFIG_HEADER` template plus a structure rule (exactly one `%s`,
  no other `%`), and a **golden output vector** for the derived
  `ar2_config.ts` (fixed synthetic inputs → pinned digest). The `ar2_config.ts`
  text is then `template % json.dumps(config, indent=2, ensure_ascii=True)`,
  produced by CFG1's own code from the **verified** template. Everything is
  read, verified and serialized **before** anything is created (E-1, below).
  An offline regression (tmp_path only) still pins that, *for the pinned
  inputs*, the resulting tree is byte-for-byte what the frozen
  `write_disposable_extension` would have produced — but that comparison is
  **not** the proof of provenance (both sides would consume the same mutable
  source); the pins are.
- **E-1 (R5/B16) pinned source read — before E0, before any provenance
  interval, before any object exists.** For each of the four names, in a fixed
  order: derive the source path with the single no-parameter derivation the
  frozen binding already uses (the `extension` directory beside the frozen
  `ar2` package — the *location* is deliberately **not** authority; the pin
  is, so any location whose bytes match is the reviewed extension and none
  that differs can pass); open it **once**; read **at most `pinned_size + 1`**
  bytes through that one open; refuse unless the length equals the pinned size
  **and** the SHA-256 of *those very bytes* equals the pinned digest; on a
  match keep the bytes in an immutable in-memory `bytes` value; close. The
  template attribute is read exactly **once** into a local `str` (immutable),
  verified against its pin and structure rule, and that local — never the
  module attribute again — is what E8 formats. Any failure raises a typed
  `Cfg1ExtensionError` (`EXTENSION_SOURCE_UNPINNED` or
  `EXTENSION_TEMPLATE_UNPINNED`) with `token_material_outstanding == False`
  (no token byte can have existed: nothing has been created), so **no
  extension byte is ever written from an unverified input**. The source
  pathnames are never opened again in the run.
- **E0** open this generation's **extension-typed** provenance interval (AM-10).
- **E1–E2** root pin, by the workspace's registered root identity.
- **E3** `CreateDirectoryW` of `pi_extension` (never `exist_ok`). **R-WINDOW-E**
  opens here and closes at E4: exactly L9's accepted `R-WINDOW` shape — a
  same-user actor may substitute another *ordinary* directory at that name;
  whichever object wins is proven non-reparse and contained by file id in the
  identity-proven root, and receives zero bytes before the gate. **R-WINDOW-E is
  ACCEPTED (reviewer decision on R4), under exactly these conditions:** zero
  bytes before the gate; whichever object wins is an ordinary non-reparse
  directory; contained by file id in the identity-proven root; and **no claim,
  anywhere, that CFG1 necessarily created the directory** (the writer never
  deletes it — only L27's independently re-proven whole-root teardown may).
- **E4–E5** pin it (`FILE_SHARE_READ` only, no-follow) and prove it is the
  root's child entry by file id. A refusal from here on leaves the directory
  untouched: only L27's whole-root teardown may remove it.
- **E6** one exclusive child per static source name and one for
  `ar2_config.ts`: `CREATE_NEW`, `dwShareMode = 0`,
  `FILE_FLAG_OPEN_REPARSE_POINT`, zero content bytes.
- **E7 THE GATE** — handle-relative parentage of every child in the pinned
  directory. Refusal → dispose every child through its own creating handle
  (all zero-byte), raise.
- **E8** content through the proven descriptors: every static source first
  (the **already-verified buffered bytes** from E-1, verbatim, through a
  bytes-mode sibling of `write_child_text`, so no newline translation alters a
  copied file and **no source pathname is reopened**), and the **token-bearing
  `ar2_config.ts` last**, preceded immediately by `token_write_attempted :=
  True`. The token therefore never reaches disk unless the gate passed and
  every static child was written.
- **E9** read-back of every child through the same descriptors, compared with
  the buffered material (text under the declared newline translation). For each
  static child the read-back SHA-256 is additionally required to equal the
  **CFG1-owned pin literal** — not merely the buffer — so a mechanical chain
  pin → verified buffer → written child → read-back is checked end to end.
- **E10 extension issuance.** `register_extension_issuance(...)` re-proves the
  interval type and child provenance, then records — as the **last** statement
  before returning a token, exactly as `register_config_issuance` does — the
  `run_workspace_nonce`, the derived directory and entry path, the directory's
  and **every child's** `(volume_serial, file_id)`, and every child's raw
  read-back SHA-256. It **refuses registration** unless each static child's
  recorded digest equals its pin literal and `ar2_config.ts`'s equals the
  digest of the verified-template output E8 produced. The returned token is the
  **authority object** L14/L15/L24 re-prove and L24 consumes. Nothing about it
  is durable.
- **E11 release, on every exit path — two cases that are never blurred
  (R5/B15).** *E11a — a failure already known before release begins* (any raise
  out of E-1…E10, including an E10 refusal): the interval is retired first; if
  `token_write_attempted`, the token child is **disposed through its own
  creating descriptor and only then closed** (the W12 mechanism step 7 already
  uses) — `token_disposed` records the disposition result; every static child
  is disposed the same way (best effort; static bytes are not token material);
  then every child is closed, recording the **token child's close result**
  (`token_closed`); then the directory pin, then the root pin. *E11b — no
  failure known before release* (the success exit): **nothing is disposed** —
  the files are meant to persist — and children and pins are closed. A close or
  pin-release failure first discovered **during** E11b is a *new* failure found
  *during* release: it **cannot retroactively dispose**, because the disposal
  point for a failure is *before* the close of that handle, and a handle whose
  close just failed is in an unknown state that nothing here will guess about;
  so the genuine issuance is **discarded** (the FU4-FU1 rule), the token is
  reported **outstanding/unproven**, and the run fails. The same holds for a
  failure known before E11 whose disposition succeeded but whose close then
  failed. In every case the disposal object is provably the object this
  invocation created — only this invocation ever held a `CREATE_NEW`,
  share-mode-0 handle to it — and **nothing is ever deleted by pathname**.
- **Exception contract.** Every anticipated failure raises exactly one
  CFG1-owned typed `Cfg1ExtensionError(reason_code, token_material_outstanding)`,
  where `token_material_outstanding` is an exact bool equal to
  `token_write_attempted ∧ ¬(token_disposed ∧ token_closed)`: **BOTH** a
  successful disposition **and** a successful close of the deletion-bearing
  token-child handle are required for "not outstanding". A disposition that
  succeeded followed by a close that failed is **OUTSTANDING/UNPROVEN, never
  clean** (the failed close is already counted by `close_child`'s existing
  `"child"` close-failure accounting). On an E11b failure `token_disposed` is `False` by
  construction, so the value is `token_write_attempted`. No path, token, or
  exception text crosses the boundary.

*Executor, L11.* (1) `extension_binding_scrub_verified := False` immediately
before the call — this keeps the fix for the pre-existing defect R3 found
(`run_executor.py:301` initialises it `True` and `:646` sets it `False` only
after success, so an L11 raise used to leave a misleading `True`). (2) Success
→ `state.extension_issuance := token`; the field stays `False` until L24.
(3) A `Cfg1ExtensionError` whose `token_material_outstanding` is **exactly**
`False` → the field is set `True`, meaning *"no token-bearing object this run
wrote remains"*: either no token byte was ever written, or the token child was
disposed through its own creating handle **and that handle then closed
successfully** (R5/B15). (4) Anything else — the bool exactly
`True`, a non-bool, a malformed attribute, or any other exception type (an
unanticipated raise inside the writer is assumed to leave token material) → the
field stays `False`. (5) `EXTENSION_GENERATION_FAILED` at L11, as today.
Reading the one closed bool in (3) is done by L11's own handler for a
CFG1-owned typed exception, exactly as L1 handles P's typed result; §9.2's rule
that the **catch-all** reads nothing of an exception is unchanged. The bool
read in (3) authorizes **no** deletion; it only records that a handle-bound
action the writer already took discharged the obligation. After an unproven
partial write, **CFG1 performs no individual deletion of anything**: the
directory, and any child whose handle disposal failed, are left for L27, which
removes them only if it independently re-proves whole-root authority (§8, §17),
and otherwise leaves them in place.

*Executor, L24 (success path — reconciled with the same principle).* When
`state.extension_issuance` is set: `verify_extension_issuance(token,
workspace)` re-derives every path from the workspace (never from a
caller-mutable attribute — the FU2 Finding 2 rule L24 already applies to
`models_path`), checks the nonce, proves the directory not redirected **and
still the issued directory object by file id**, and re-digests every
still-present child against its issued digest. Then
`extension_binding_scrub_verified := win.identity_bound_unlink(token_path,
expected_identity=issued ar2_config.ts identity)` — the existing FU15
precise-child primitive **as strengthened by AM-12 (R6/B17)**: ONE uninterrupted
share-0 handle interval that opens the expected path without following (**any**
open failure, *including absence*, yields `False`), proves the file id equals
the issued identity, proves the link count is **exactly 1**, disposes through
that same handle, and closes it — `True` only if every step succeeded
(§9.2c-C). A mismatch, a link count other than 1, an absent path, a failed
disposition or a failed close each yield `False`, and every refusal before the
disposition deletes nothing. A failed
issuance verification yields `False` with no deletion. The issuance is then
discarded unconditionally (consumed). `_scrub_extension_binding` and its frozen
pathname scrubber leave CFG1's call graph. **L14/L15** likewise take the
extension entry path from a fresh `verify_extension_issuance` at their own
consumption point.

*Lifecycle and evidence consequences, exactly.*

| L11 outcome | `extension_binding_scrub_verified` | Lifecycle effect | Record |
|---|---|---|---|
| success | `False` until L24; then the identity-bound result | L24 conjunct = that result | as today |
| typed failure, `token_material_outstanding == False` | `True` | no L24 obligation from L11 | `refused_at_step = "L11"`, `EXTENSION_GENERATION_FAILED`; classification per the other closure facts (e.g. `REFUSED_PRE_DISPATCH` / halt `PRE_DISPATCH_REFUSAL` when everything else closes) |
| typed failure with the bool `True`, malformed, or any other exception | `False` | `"L24" ∈ lifecycle_failure_steps` → `INDETERMINATE_LIFECYCLE`, halt `LIFECYCLE_CLOSURE_UNPROVEN` — **even if** L27 later removes the whole root, which is recorded separately in L27's own facts and does not retroactively prove an individual scrub | `refused_at_step = "L11"`, `EXTENSION_GENERATION_FAILED`; no new field |

*Residuals, named.* R-WINDOW-E (above). The registry is process-local, like
config issuance. `identity_bound_unlink` verifies and disposes through one
handle, so the delete itself has no check→use sliver; the identity cannot tell
whether the issued object was modified in place (same file id) — the re-digest
in `verify_extension_issuance` covers that at each consumption point, up to
that re-digest's own check→use sliver, stated not closed. This design
is at **L9-grade** pre-write authority; it does not claim confinement of the
Pi process that later loads the extension.

*Source provenance residuals (R5/B16), stated not closed.* (1) There is **no**
source-read → use sliver for content: the four sources and the template are
read **once**, verified against CFG1-owned pins, and E8 writes the buffered,
verified bytes — nothing re-reads a source pathname. (2) The four static-source pins and the template pin were
**independently confirmed by the reviewer** against frozen commit
`bfae384370246e0ab4073a28a6b6df0558153864`; the implementation phase still
records them from git blobs under the `lf` policy, and the golden vector is a
frozen design literal (§9.2c-D). (3) The
pin module is CFG1 code; an edit to it is a source-lineage change to be caught
by the launcher's source-origin gate (G4/G5), which the implementation phase
must extend to cover it. (4) Between E8's write and Pi's later load, integrity
rests on `verify_extension_issuance`'s re-digest and its own stated check→use
sliver, unchanged from R4. (5) A source-pin drift now refuses at L11 — after
the L4 credential read, unlike a pre-consumption check — which is the same
temporal trade AM-11 names for step 9a; adding a credential-free pre-L4 source
check is **not** proposed here. (6) The buffered bytes and the token live in
process memory; same-user memory tampering is out of scope, as it is for the
token today. (7) Pi's own transitive imports under its package root remain
OC-2.

§11 adds regression tests (R4: Test R for the transactional writer, new Tests
W and X; **R5:** Q rewritten as the L9 endpoint-material matrix, R extended with
the close-failure and pinned-input cases, new Tests Y (the B15 primitive) and Z
(the B16 pinned inputs)) on top of the existing Test B (workspace) and Test G
(dispatch/runtime) coverage.

**What B4 does not do, and what B9 corrects about it.** B4 (R2) correctly
established the two-category framework and correctly found four of six
families already correct in the shipped executor. Its two "confirmed gaps"
(L9, L11) were mis-diagnosed: L9 was never actually an *issuance* gap (B9,
above — its on-disk residue, OC-11, is closed in R5, §9.2c), and L11's fix needed real
authority, not a bare bool. R3's answer to the latter (a pathname scrub) was
still not authority; R4's is the extension issuance above (B12). Every other
category-B fact in this table is unchanged from R2 and needed only the
explicit two-category framing, not a code change, to stop contradicting
§9.2's general sentence.

### 9.2b L9 actual-output shape check (R4, B13 — new step 9a)

*R3 retraction.* R3's OC-10 row and §16 said current L9 already proves
"actual generated `models.json` redacted digest == `ARM_REDACTED_DIGEST[arm]`".
Source review of the `bfae384…` baseline shows it does not:

- `config_issuance.register_config_issuance` reads the **actual** bytes through
  the held descriptors and records their **raw** SHA-256
  (`config_issuance.py:245-262`) — endpoint included, never redacted, never
  compared with any pin;
- `cfg1_pi_config.redacted_models_digest()` hashes a **separately constructed
  in-memory expected** document (`cfg1_pi_config.py:133-142`), and
  `GeneratedCfg1Config.models_redacted_sha256` is exactly that expected value
  (`:471`);
- `records.py` writes `ARM_REDACTED_DIGEST[arm_id]` into
  `models_json_redacted_sha256` directly (`records.py:1112`) and its validator
  compares the record with the same constant (`:744`).

No existing step compares **redacted actual on-disk bytes** with the
independent per-arm pin. R4 adds one.

**Step 9a, inside `write_cfg1_pi_config`, after step 9 and strictly before step
10** (names illustrative):

1. **Actual bytes, from the proven object.** Read `models.json` through the held
   `models_child` descriptor (`win.read_child_bytes`) — the `CREATE_NEW`,
   `dwShareMode = 0` descriptor steps 6–9 used, so no other actor can hold the
   object open for write meanwhile, and no pathname is re-opened.
2. **Exactly the declared newline translation, nothing else.** Step 8 writes
   through `io.TextIOWrapper`, which maps `\n` to `os.linesep` — `\r\n` on
   win32, the only platform L9 supports. Require every `\r` to be immediately
   followed by `\n` and every `\n` to be immediately preceded by `\r`; then map
   `\r\n` → `\n`. A bare `\r` or bare `\n` refuses. No whitespace, BOM,
   key-order or JSON re-serialization normalization — the bytes are never
   parsed.
3. **Redact exactly one slot.** Let `E` = `json.dumps(base_url)` as UTF-8 — the
   JSON string literal of the base URL L9's caller passed in memory. Require
   `E` to occur **exactly once** in the canonical bytes, and that occurrence to
   be immediately preceded by `b'"baseUrl": '`. Replace it with
   `json.dumps(REDACTED_BASE_URL)`. Zero or several occurrences refuse.
4. **Compare with the independent pin.** `sha256(redacted) ==
   ARM_REDACTED_DIGEST[arm_id]` — the literal in `arms.py`, which that module
   documents as deliberately **not** recomputed from the generator. Mismatch
   refuses. The same comparison, with no redaction step (the document carries
   no endpoint), is applied to `settings.json` against `PINNED_SETTINGS_SHA256`,
   because the frozen self-check this replaces covered both generated files;
   nothing further is added.
5. **Refusal path.** Raise one closed code (e.g.
   `GENERATED_CONFIG_SHAPE_MISMATCH`). This is a *failure known before
   release*: the writer's single failure-path release (§9.2c) disposes
   `models.json` — and `settings.json` — through their own creating
   descriptors and **then** closes them, and computes
   `endpoint_material_outstanding` from BOTH results. Step 9a performs no
   disposal of its own, so exactly one place decides that fact. Step 10 never
   runs, so no issuance ever exists; the executor reduces it to
   `CONFIG_GENERATION_FAILED` at L9, unchanged.
6. **Issuance binds the checked bytes.** Step 10 receives the raw SHA-256 of the
   bytes 9a checked as an expected value and refuses registration if its own
   read-back digest differs. Share mode 0 already makes equality expected; this
   makes it mechanical.

**Why this is not tautological.** The expected side is a pinned literal, never
produced by the generator under test. The actual side is the on-disk bytes of
the proven object. The only transformations applied to the actual side are the
one declared newline mapping and a one-slot substitution keyed by the caller's
own input. Any change to the generator, the serializer, the write path, the
compat subtree, key order, indentation, or the encoding of the URL slot changes
the digest or the occurrence count and refuses. `redacted_models_digest()` and
`GeneratedCfg1Config.models_redacted_sha256` play **no** part and are never
cited as evidence of actual output.

**No endpoint enters evidence.** `E`, the canonical bytes and the redacted
bytes are locals of step 9a; only a closed code can leave it. The durable field
`models_json_redacted_sha256` keeps its existing meaning — the arm's pinned
redacted digest, written from the constant — and does **not** become a
measurement. What changes is only that every run which **passed L9** has now
mechanically proven its actual bytes equal that pin. A record refused before L9
proves nothing about generated bytes, exactly as in v1.

**Temporal guarantee — not identical, and named (AM-11).** Frozen L1's
generator self-check, had it been wired, ran before L4. Step 9a runs at L9,
after the credential read (L4) and the route observation (L7), and after the
authorization was consumed. R4 does **not** claim the old and new guarantees
are the same: CFG1 gives up pre-credential detection of a generator shape
defect, and gains a proof about the actual bytes of the actual arm that the
frozen self-check (against another generator and a placeholder URL) never gave.

**Offline regression, retained and extended.** The existing pin-agreement
regression (`tests/test_cfg1_composition.py:110-113`: the generator's
expected digest equals `ARM_REDACTED_DIGEST` for every arm) and the malformed
input refusals (`UNKNOWN_ARM_ID`, `MALFORMED_BASE_URL`, `MALFORMED_MODEL_ID`)
stay; new §11 Test W drives step 9a itself with actual bytes that disagree
with the pin while the in-memory expected digest still agrees.

**OC-11 — CLOSED in R5 (folded into this FU, not deferred).** R4 recorded, but
did not correct, that a genuine L9 failure after step 8 leaves an
endpoint-bearing `models.json` on disk while `generated_config_scrub_verified`
stays at its initial `True`. The reviewer required the disposition now. The
correction — a write-ahead `False` before the call, a writer-owned
`endpoint_material_outstanding` derived from a handle-bound disposition **and**
a successful close, and an executor rule that can only ever move the fact to
`True` from that proven result — is specified in §9.2c and AM-13; L27's
whole-root success never upgrades it. Step 9a's own refusal path is reconciled
in item 5 above.

### 9.2c Sensitive-material state machines (R5 — OC-11, B15, B16)

This section consolidates the three places AIDO deliberately puts sensitive
bytes on disk — the endpoint in `models.json` (L9), the broker token in
`ar2_config.ts` (L11) — and the one place it removes them (L24), and it fixes
the provenance of the extension bytes. Every rule below is a *design*
statement about code to be written; nothing here was implemented or run.

**Governing rules.**

- **G1 — a bool is evidence, never deletion authority** (retained from R4). No
  pathname is ever deleted. A same-name foreign object can never be deleted as
  though AIDO created it: writer-side disposal acts only through a handle this
  invocation opened with `CREATE_NEW` and `dwShareMode = 0` (so no other actor
  could hold that object), and L24-side disposal acts only through a handle
  whose `os.stat(fd)` file id matched the issued identity at open.
- **G2 — "not outstanding" requires BOTH halves (B15).** After sensitive bytes
  were *attempted*, a fact may claim they are gone only if (a) the object was
  disposed **through the creating handle** *and* (b) that **deletion-bearing
  handle then closed successfully**. A disposition that succeeded followed by a
  failed close is **OUTSTANDING/UNPROVEN, never clean**: on Windows the delete
  completes when the last handle closes, and the state after a failed close is
  unknown. This is a statement about the handle protocol, not a pathname
  observation, and it says nothing about what answers at that name later.
- **G3 — disposal precedes the close of the same handle, and a failure first
  discovered during release cannot reach back (B15).** Distinguish, always:
  *failure known before release begins* → dispose by own handle, **then**
  close; *failure first discovered during release/close* (a close or pin
  release failing on a run that had no prior failure, or a close failing after
  a disposition already succeeded) → **no retroactive disposal** — the only
  handle that could dispose has just failed to close — so the result is
  **outstanding/unproven** and the lifecycle fails. Nothing retries, guesses,
  or reaches for a pathname.
- **G4 — write-ahead, pessimistic.** "Attempted" is set **before** the single
  call that can carry the sensitive bytes, and is never reset.
- **G5 — L27's whole-root success never upgrades** an individual scrub fact.
  L27 re-proves authority over the whole root independently and is recorded in
  its own facts; it is a different authority object.
- **G6 — conservative reading.** The executor sets a scrub fact `True` only
  from an **exact** `False` of a writer's outstanding bool on the **exact**
  genuine typed error. A non-bool, a malformed attribute, another exception
  type, or an unanticipated raise leaves the fact `False`.
- **G7 — no pathname-based positive scrub (R6/B17).** A scrub fact may become
  `True` on the L24 path only from the exclusive-interval proof of AM-12.
  Pathname absence is **never** object absence (the issued object may have been
  renamed), and a single expected name accepting a deletion is **never**
  object removal (another hard link may keep the object reachable). Any
  failure to open the expected pathname, including absence, is `False`.

#### A. L9 — `models.json` (endpoint material), the OC-11 state machine

Writer-local facts in `write_cfg1_pi_config` (none durable):

- `endpoint_write_attempted` — set `True` **immediately before**
  `win.write_child_text(models_child, models_text)` (step 8, `models.json` is
  written second, after `settings.json`, which carries no endpoint). It is set
  even if that call raises partway, and endpoint bytes can reach disk **only**
  through that one call.
- `failure_known` — a raise from steps 0–10, including step 9a's
  `GENERATED_CONFIG_SHAPE_MISMATCH` and a step-10 refusal; an unanticipated
  non-`Cfg1PiConfigError` exception raised in the body is caught, marked, and
  re-raised as `Cfg1PiConfigError("CONFIG_WRITER_UNEXPECTED_FAILURE")` `from
  None` (no exception text, as everywhere).
- `models_disposed`, `models_closed` — the two G2 halves.

**One release, one decider (step 11, extended).** Interval retired first, as
today. Then, **iff** `failure_known ∧ endpoint_write_attempted`:
`models_disposed := win.dispose_child_by_handle(models_child)` (and, best
effort, `settings.json`'s child — not sensitive), **strictly before** any child
is closed. Then every child is closed, recording `models_closed` from the
`models.json` child's own close result; then the proven-parentage discard, the
config-directory pin and the root pin exactly as today, every release attempted
before any failure is raised. FU4-FU1's issuance discard is unchanged. Finally
the writer computes, once,

```text
endpoint_material_outstanding =
    endpoint_write_attempted ∧ ¬( failure_known ∧ models_disposed ∧ models_closed )
```

and raises exactly one `Cfg1PiConfigError(reason_code, endpoint_material_outstanding)`
— an exact bool, no path/URL/text — with the existing precedence for the
reason code (a release-failure code still replaces an in-flight one; the bool
is unaffected by which code wins). On a normal return the fact is not reported:
the object is intentionally live, owned by the just-registered issuance.

| L9 exit | attempted | disposition | models close | `endpoint_material_outstanding` | executor `generated_config_scrub_verified` | lifecycle |
|---|---|---|---|---|---|---|
| L9 never entered (L1–L8 refusal) | — | — | — | — | initial `True`; nothing generated, no obligation | unchanged |
| raise before the models write (steps 0–7 incl. the gate refusal; a `settings.json` write failure) | `False` | — | — | `False` | `True` (no endpoint byte can exist) | no L24 obligation from L9 |
| raise after the models write began (partial write, step 9, **9a**, step-10 refusal, unanticipated body exception): disposition ok, models close ok | `True` | ok | ok | `False` | `True` — handle-bound, both halves | closes |
| same, **disposition fails** | `True` | fail | (attempted) | `True` | stays `False` | `"L24"` ∈ failure steps → `INDETERMINATE_LIFECYCLE`, halt `LIFECYCLE_CLOSURE_UNPROVEN` |
| same, disposition ok, **models close fails** | `True` | ok | **fail** | `True` (G2) | stays `False` | same; the failed close is counted (`"child"`) |
| same, disposition ok, models close ok, but only `settings.json` close / a pin release fails | `True` | ok | ok | `False` | `True` (endpoint object proven gone) | the leaked handle/pin is a separate, existing lifecycle fact — it makes L27's removal fail by construction |
| the disposal call itself raises unanticipatedly | `True` | unknown | — | `True` | stays `False` | as the disposition-fails row |
| **successful** return, then step-11 release failure (config pin, root pin, any child close) — a failure *first discovered during release* (G3) | `True` | **none attempted** | — | `True` | stays `False`; issuance discarded (FU4-FU1) | `"L24"` ∈ failure steps; L27 acts separately and does not upgrade it (G5) |
| successful normal return | `True` | — | — | not reported | stays `False` (the write-ahead value) until L24 | L24 = the precise identity-bound scrub (AM-12) |
| a non-`Cfg1PiConfigError`, a malformed/absent attribute, or a non-bool from a test double | — | — | — | — | stays `False` (G6) | as the disposition-fails row |

**Executor, L9 (exact).** (1) `generated_config_scrub_verified := False`
**immediately before** `ports.write_config(...)`; (2) on return the value is
already `False` and stays so (the existing post-return assignment becomes
redundant and harmless); (3) on any exception the handler makes **one**
decision — `type(exc) is Cfg1PiConfigError and exc.endpoint_material_outstanding
is False` → the fact becomes `True`, meaning exactly *"no endpoint-bearing
object this invocation produced is known to remain"* — and then raises the
unchanged `_PreDispatchRefusal("CONFIG_GENERATION_FAILED", "L9") from None`.
Reading that one closed bool from one exact CFG1-owned type is not "reading an
exception" in §9.2's sense, exactly as for L11's typed error; the catch-all
still reads nothing. **Consequence stated:** an offline double that raises an
untyped exception at L9 now leaves the fact `False` and lands in
`INDETERMINATE_LIFECYCLE` — a test modelling "nothing was written" must raise
the typed error with `False`. **No** durable field is added (§10), and a v2
validator cannot distinguish the two admissible values at `refused_at_step ==
"L9"`; it does not need to, because lifecycle classification is a function of
the fact itself.

#### B. L11 — `ar2_config.ts` (token material)

The L11 state machine is §9.2a's E-1…E11 with R5's two changes: the pinned
input stage E-1, and G2/G3 in E11.

| L11 exit | attempted | token disposition | token close | `token_material_outstanding` | `extension_binding_scrub_verified` | lifecycle |
|---|---|---|---|---|---|---|
| E-1 pin refusal (source or template) | `False` | — | — | `False` | `True` | closes; `EXTENSION_GENERATION_FAILED` at L11; **zero bytes ever written** |
| failure in E0–E7, or E8 before the token write | `False` | — | — | `False` | `True` | closes |
| failure after the token write began; disposition ok, close ok | `True` | ok | ok | `False` | `True` | closes |
| same, **disposition fails** | `True` | fail | (attempted) | `True` | `False` | `"L24"` ∈ failure steps |
| same, disposition ok, **token-child close fails** | `True` | ok | **fail** | `True` (G2) | `False` | same |
| success, then E11b release failure (G3) | `True` | none | — | `True` | `False`; issuance discarded | same; L27 never upgrades (G5) |
| non-typed exception / non-bool | — | — | — | — | `False` | same |

#### C. L24 — the only removal of either sensitive file (rewritten R6/B17)

For `models.json` (the config issuance's `models_identity`) and `ar2_config.ts`
(the extension issuance's identity): re-verify the issuance against the
workspace (paths re-derived, never read from a mutable attribute) → call
`identity_bound_unlink(path, expected_identity=…)` under AM-12's contract →
`scrub_verified := result` → discard the issuance unconditionally. Each file's
scrub is independent: a `False` on one never causes the other to be skipped or
upgraded.

**The positive-scrub contract (frozen as the *what*).** A `True` requires one
**uninterrupted exclusive-handle interval**, from the open to the close of a
single share-0 handle:

```text
1  open the expected pathname: no-follow, share-0, delete access, OPEN_EXISTING
2  handle identity  == issued identity                        (else False, no disposition)
3  link count read from THIS handle == exactly 1 (an int)      (else False, no disposition)
4  2, 3 and 5 happen while THIS handle stays held — so no other actor can open,
   rename, or add a hard link to the object between the proof and the disposition
5  disposition through THIS handle succeeds
6  THIS handle closes successfully                             → only now True
```

Step 4 is what makes the proof **continuous** rather than a check-then-act:
share-0 denies every other open of the object, and creating a hard link or
renaming the object requires such an open. That is a **mechanical claim about
the target OS that Test Y-6 must demonstrate**; if alias creation or rename
*succeeds* while the handle is held, the implementation phase **stops and
returns to design** (as D-6 does) rather than improvising. The 8.3 short name
is not a separate link. An unreadable, malformed, non-`int` (a `bool` is not 1)
or ≠ 1 link count, or a change that cannot be mechanically excluded, is
`False` with **no disposition and no pathname fallback**.

| `identity_bound_unlink` case | returns | notes |
|---|---|---|
| expected pathname **absent** (never written, deleted, or **renamed away**) | **`False`** | R5's "absent ⇒ `True`" is **withdrawn**: pathname absence is not object absence; the issued object may exist as `leak.bin` |
| open fails for any other reason (sharing violation, reparse, denial) | `False` | |
| identity **mismatch** (foreign same-name object, replaced file, other type) | `False` | **nothing deleted**; a close failure here is also counted |
| identity match ∧ link count **≠ 1** (alias in the same directory or elsewhere on the volume), unreadable, malformed | **`False`** | **no disposition**; every link stays; no "delete one name" partial removal |
| link count 1 ∧ disposition **fails** | `False` | close still attempted; a close failure is counted |
| link count 1 ∧ disposition ok ∧ close **fails** | **`False`** | AM-12/R5: not swallowed; `"unlink_handle"` in `_CLOSE_FAILURES`; no retry |
| link count 1 ∧ disposition ok ∧ close **ok** | **`True`** | the only positive proof |
| issuance verification failed | `False` | no unlink attempted |

Any `False` puts `"L24"` in `lifecycle_failure_steps` →
`INDETERMINATE_LIFECYCLE`, halt `LIFECYCLE_CLOSURE_UNPROVEN`, **and L26 is
skipped** (`LIFECYCLE_UNPROVEN` — L26 requires L21 ∧ L23 ∧ L24 closed), so no
model-influenced code runs while an issued sensitive object may still exist. It
holds whether or not L27 later removes the whole root (G5). Nothing in AIDO
removes either file before L24, so a legitimately absent file is not expected;
if it ever occurs the cost is an indeterminate lifecycle, an accepted
fail-closed outcome.

**What this proves and what it does not.** It proves that a `True` scrub
removed the exact issued object and that no other hard link to *that object*
existed when it was removed. It does **not** prove global secrecy: a
byte-copy made by a same-user actor at any time before L24 is a separate file,
outside this object-identity claim, and remains part of the same-user /
no-confinement residual. Residual windows between issuance verification and the
open are safe by construction — a rename yields absence (`False`), a
replacement yields an identity mismatch (`False`), an alias added before the
open yields a link count ≠ 1 (`False`) — none can yield `True`.

#### D. Extension source provenance chain (B16 — final)

```text
P0  reviewed bytes                     ── CFG1-owned literals, never derived at run time
P1  L11 E-1: one open, ≤ pinned_size+1 bytes read, len == pinned_size,
    sha256(those bytes) == literal    ── else refuse; nothing created, nothing written
P2  immutable in-memory buffer         ── only verified bytes are ever buffered
P3  E8 writes the buffer               ── source pathname never reopened
P4  E9 read-back == buffer, and static read-back sha256 == literal
P5  E10 issuance digests == literals (static) / == verified-template output
P6  L14/L15/L24 re-digest against the issuance (R4, residual sliver stated)
```

Independent literals for the four static sources — **independently confirmed by
the reviewer (R6) against frozen commit
`bfae384370246e0ab4073a28a6b6df0558153864`** (they were first recorded here as
candidates in R5; git shows `lf` line endings for all four and each `HEAD` blob
hashes to the same value):

| name | size (bytes) | SHA-256 |
|---|---|---|
| `ipc.ts` | 8589 | `789831482abf353254aa2ff5af20d90634f2caad1fa7366bfe7776c4a35c2024` |
| `tools.ts` | 5896 | `c03de727ae73d58babef459c753852a7b53439ddd1c0db571a2f0443abe9f5b4` |
| `index.ts` | 2182 | `ffc2dee8198d51f0f914a67a2370e1149040e0616f8789526b9253f53bcfcb3c` |
| `package.json` | 295 | `4571c0f2552eefaadd40a99885f4d73930bfb540fe9ece4f23fed6a4a05058fc` |

Template literal — **reviewer-confirmed**: the UTF-8 encoding of the frozen
`_GENERATED_CONFIG_HEADER` is **748 bytes** with SHA-256
`819f1f1d7909020a701d9527f37138ecaab08494d3ad06923863bf407043094f`,
containing exactly one `%s` and no other `%` (the structure rule).

**Golden vector for the derived `ar2_config.ts` — FROZEN (R6/B18).** These are
**design literals**, not values the implementation selects or derives. The
inputs are deterministic, non-secret and synthetic (the real experiment id is
deliberately not used):

| input | literal |
|---|---|
| `experiment_id` | `golden_vector_experiment` |
| `pipe_name` | `\\.\pipe\golden_vector_pipe` (27 characters: two backslashes, `.`, a backslash, `pipe`, a backslash, `golden_vector_pipe`) |
| `capability_id` | `golden-capability-0001` |
| `token` | `golden-vector-token-not-a-secret-0000` |

The config mapping is built in the frozen key order `experiment`, `pipeName`,
`capabilityId`, `token`. The document is
`verified_template % json.dumps(config, indent=2, ensure_ascii=True)`, whose
substituted JSON text is exactly:

```text
{
  "experiment": "golden_vector_experiment",
  "pipeName": "\\\\.\\pipe\\golden_vector_pipe",
  "capabilityId": "golden-capability-0001",
  "token": "golden-vector-token-not-a-secret-0000"
}
```

Encoding and newline rule (declared): UTF-8, all characters ASCII, and on
win32 the text-mode write maps every `\n` to `\r\n` (`os.linesep`), exactly as
`write_child_text` does. The document is 937 characters and **962 bytes as
written** (25 line breaks, no bare `\r`, no BOM, no trailing content after the
final `\n`).

| quantity | value |
|---|---|
| **expected SHA-256 of the 962 on-disk (CRLF) bytes** — the frozen literal | `e7916cd3c878626369684cde06e0919d15affaea80f9700871024999ee163715` |
| reference only (non-normative): SHA-256 of the same 937-byte text with bare `\n` | `4dceba5bbd8611f1f39d5da8fc61e14d2e927437abfad655835fd11ace8e88db` |

Independence: the expected digest is a literal in the design and is **never**
computed at test runtime from the production serializer; a test may build the
same document independently from the four frozen literals (as this design's
author did — once with `json.dumps`, once with a hand-assembled JSON body whose
backslashes are doubled by hand, the two texts comparing equal), but it compares
the result to the literal. The template used to produce the literal was read by
**parsing** `ar2/pi_config.py`'s source with `ast` (no module import) and was
checked against the confirmed 748-byte / `819f1f1d…` pin before use.

The pin table lives in a CFG1-owned module that must join the launcher's
source-origin lineage (G4/G5); the implementation phase adds it and Test Z
asserts membership. Nothing under `ar2/` is edited.

**What this proves and what it does not.** It proves that every byte AIDO
writes into `pi_extension\` (other than the per-run token document) is
byte-identical to the pinned reviewed bytes, and that the token document is
the pinned template applied to the per-run values — independent of what the
live AR2 source directory held at run time. It does not prove the pins are the
right bytes (review does), that Pi will load only these files (OC-2), or
anything about a transient swap after E9 (the R4 re-digest sliver).

### 9.3 Dispatch write-ahead (AM-5)

Immediately before `send_command`, the executor records `dispatch_state =
SEND_STATE_INDETERMINATE` and `prompt_writes = 1` ("a write may have reached
Pi's stdin"), and refines to `CONFIRMED_SENT`/`CONFIRMED_NOT_SENT` only after a
correlated response of exactly the expected shape. A non-`dict` response, or
any raise after the write attempt, leaves the truthful indeterminate state —
§18 row 4a's existing meaning. This closes D4 path 2 and keeps the existing
v1 invariant `(prompt_writes == 0) == (dispatch_state == NOT_ATTEMPTED)`.

### 9.4 Step/code table (v2 validator invariant)

`refused_at_step` → admissible `pre_dispatch_refusal_code`, derived from the
shipped executor: L1 `OFFLINE_PREFLIGHT_FAILED`; L2, L3 `WORKSPACE_BASELINE_FAILED`;
L4 `CREDENTIAL_BOUNDARY_FAILED`; L5 `SECRET_CONTEXT_FAILED`; L6
`BASE_URL_COMPAT_DETECTION_TRIGGERED`; L7 `ROUTE_UNAVAILABLE`; L8
`CAPABILITY_MINT_FAILED`; L9 `CONFIG_GENERATION_FAILED`; L10
`BROKER_CONSTRUCTION_FAILED`; L11 `EXTENSION_GENERATION_FAILED`; L12
`CHILD_ENVIRONMENT_FAILED`; L13 `BROKER_NOT_READY`; L14 `RUNTIME_LAUNCH_FAILED`;
L15 `RUNTIME_CORRELATION_FAILED`, `H1_MISMATCH`; L16 `RUNTIME_CORRELATION_FAILED`,
`H2_MISMATCH`, `CONFIG_SHAPE_MISMATCH`; L17 `PRE_DISPATCH_BASELINE_FAILED`; L18
`PROMPT_REFUSED_BY_RUNTIME`; and `UNEXPECTED_STEP_FAILURE` at every step.

Plus, corrected for B6 (R2's version of this paragraph asserted an
unconditional `refused_at_step` present ⇔ `unexpected_failure_step` absent,
which rejects a clean run where all three fields are absent — see §9.2's
"Three exact, mutually exclusive modes"): **the only direct iff is**
`pre_dispatch_refusal_code` present ⇔ `refused_at_step` present. Every record
is in exactly one of three modes: **REFUSAL** (`refused_at_step` and
`pre_dispatch_refusal_code` both present, `unexpected_failure_step` absent —
anticipated or `UNEXPECTED_STEP_FAILURE`-shaped); **POST_DISPATCH_UNEXPECTED**
(`unexpected_failure_step` present alone, the other two absent); or
**NO_DISPATCH_FAILURE** (all three absent — the ordinary clean pass, which R2
could not represent and B6 restores). `unexpected_failure_step`'s presence or
absence is never used, alone, to infer which of the other two fields hold.

Plus, for B1/B7/B14: the v2 validator applies §5.1's rules **R-P1…R-P6
verbatim** — every one a pure function of the durable fields
`refused_at_step`, `pre_dispatch_refusal_code`, `pi_identity_failure_code`,
`pi_version_probe_attempted`, `pi_seam_digests_match` and
`pi_observed_version`. *R3 retraction:* this paragraph previously conditioned
two rules on "the raise preceded P2R's pass" and "P5 not reached" — facts no
artifact carries — and said `pi_identity_failure_code == null ∧
pre_dispatch_refusal_code == OFFLINE_PREFLIGHT_FAILED` could be "a P6 pass",
which is impossible (a pass carries no refusal code). The correct statement is
R-P3: that conjunction occurs **only** at `refused_at_step == "L1"`, **only**
for the Git-resolution refusal after P's success commit, and **only** with the
P success tuple σ. It also said "the five P codes"; there are **six**. A record
violating any R-P rule fails self-validation (`RECORD_INVARIANT`, halt)
exactly as the workspace W⇔`L1` invariant already does (§8, §12.2 item 2).

---

## 10. Durable-schema impact — the stop point

**Finding: v1 cannot represent the corrected semantics truthfully.**

1. For an L1 refusal to validate as `lifecycle_all_closed = true` under the
   unchanged v1 predicate, the record would have to carry
   `workspace_authority_reproved = true` and `workspace_removed_verified = true`
   — statements that a re-proof and a removal happened when no workspace ever
   existed. That is redefining two fields under misleading names; refused.
2. Amending the v1 predicate in place (e.g. "exempt L27 when
   `refused_at_step == "L1"`") would change the meaning of an already-emitted
   v1 artifact: A3's `S1_01_Q.json` (`refused_at_step "L1"`,
   `lifecycle_all_closed false`, `["L27"]`) would stop satisfying the validator
   that the frozen §22.5 verifier (`verify_cfg1_run_artifact_binding`) runs
   over its bytes. That retroactively alters historical evidence; refused. It
   would also key the distinction solely on `refused_at_step`, which D4 shows
   is not yet trustworthy.

**Required change (decision D-1):** a new run-record version,
`pi-harness-cfg1-run.v2`, emitted by the corrected executor; **v1's validator,
closure function, and meaning remain byte-for-byte as shipped**, retained only
so historical v1 artifacts keep verifying exactly as they do today. An archived
v1 record must never be read as though v2's rules applied to it — in
particular, A3's `INDETERMINATE_LIFECYCLE` / `LIFECYCLE_CLOSURE_UNPROVEN` is the
truthful output of v1's rules and is not re-labelled.

v2 differs from v1 in exactly (each addition is marked with the finding that
required it; an entry marked "R2, corrected R3" was added in R2 but its shape
changed again here):

| Change | Detail |
|---|---|
| new field `workspace_mint_state` | closed enum `NOT_ATTEMPTED` / `ATTEMPTED_NO_AUTHORITY` / `AUTHORITY_RETURNED` (§8) |
| v2 closure predicate | workspace conjunct per §8; every other conjunct identical to v1 |
| `pi_observed_version` domain | adds `NOT_OBSERVED`, meaning precisely **"no version projection was ever produced"** (B1, §5.1 — not "the probe never ran"; that fact is `pi_version_probe_attempted`, below). `UNRECOGNIZED` keeps its meaning "P5 was reached; output not a version literal" |
| **new field `pi_version_probe_attempted`** *(B1, R2; domain widened R3/B8)* | exact bool; category B — written ahead at P3's entry (P2 **and** the final P2R proof both passed), never reverted, and **not** part of P's atomically committed family (§5 P6, R4/B14); `false` in every record whose run never entered P3 (§5.1 `Allowed(F)` and U) |
| `pi_seam_digests_match` meaning *(clarified R4/B14)* | unchanged field; in v2 it means exactly *"the last seam walk P completed matched, and P's family was committed"* — `false` is "not proven to match", never by itself "measured mismatch" (§5.1). Not a conjunction with any identity check |
| **new field `pi_identity_failure_code`** *(new, R3/B7)* | nullable, closed domain of exactly **six** codes `{PI_RESOLUTION_FAILED, PI_SEAM_UNPROVEN, PI_IDENTITY_DRIFTED_BEFORE_PROBE, PI_PROBE_FAILED, PI_SEAM_CHANGED_DURING_PROBE, PI_VERSION_MISMATCH}`; committed atomically with P's family (§5 P6); **never** written into `pre_dispatch_refusal_code`, which stays uniformly `OFFLINE_PREFLIGHT_FAILED` for every anticipated L1 refusal (matching shipped code and closing D-2). `null` whenever P's family was committed as a success (every record past L1, and the L1 Git-resolution refusal) and whenever nothing of P's family was committed (every `UNEXPECTED_STEP_FAILURE` at L1) — §5.1 R-P2…R-P5 |
| **new field `unexpected_failure_step`** *(B2, R2)* | nullable string, closed domain `{"L18","L19","L20"}` when present; mutually exclusive with `refused_at_step`/`pre_dispatch_refusal_code` per the corrected B6 mode set (§9.2, §9.4) — **not** the flawed unconditional iff R2 stated |
| **`config_issuance_possibly_created` — REMOVED** *(R2 field, retracted R3/B9)* | Not needed: the genuine L9 generator (`cfg1_pi_config.py::write_cfg1_pi_config`) already retires any registered issuance transactionally on every raise (FU4-FU1); `state.generated_config is not None` is already the correct, existing authority signal. R2's field was based on an inaccurate model (an arbitrary injected double, not the genuine generator) and is dropped rather than kept as dead schema |
| **`extension_possibly_created` — REMOVED; `extension_failure_path_scrub_verified` — RETRACTED** *(R2 field removed in R3; R3 field retracted in R4/B12)* | **Neither field is in v2.** R3's replacement recorded the frozen pathname scrubber's own bool — evidence produced by an action that had no authority over the object it deleted (B12). v2 instead keeps the existing `extension_binding_scrub_verified`, now written ahead `false` before L11 and set `true` only from a handle-bound action: the transactional writer's own-handle disposal **and the successful close of that deletion-bearing handle** (reported as `token_material_outstanding == false`, R5/B15) on the failure path, or `identity_bound_unlink` against the extension issuance at L24 on the success path (§9.2a). The extension issuance itself (tokens, identities, digests) is in memory only and **never** durable |
| **`generated_config_scrub_verified` — semantics tightened, NO new field** *(R5, OC-11/B15)* | The existing durable field. v2 writes it `False` **immediately before** L9's `write_config` call (category B, write-ahead), and it becomes `True` only from (i) an L9 failure whose typed error carries an exact `endpoint_material_outstanding == False` — meaning no endpoint byte was attempted, or `models.json` was disposed through its creating handle **and** that handle closed successfully — or (ii) L24's precise scrub under AM-12's `identity_bound_unlink` (which is `True` only after the exclusive-interval proof of exactly one link and an identity match, the disposition, and a successful close — **never** from pathname absence). Its v2 meaning is exactly *"no endpoint-bearing object this invocation produced is known to remain"*. `endpoint_material_outstanding`, `endpoint_write_attempted`, `models_disposed` and `models_closed` are writer-local and **never durable**. L27's success never sets it. Archived v1 records keep v1's meaning (v1's initial `True` was never a measurement) and are not reinterpreted |
| `PRE_DISPATCH_REFUSAL_CODES` | adds `UNEXPECTED_STEP_FAILURE` (R2). Otherwise exactly the existing L1–L18 codes of §9.4's step/code table — the **six** P-identity codes are **not** members of this set; they live only in `pi_identity_failure_code`'s own domain (R3/B7). *(R3 described the existing set as "eleven" codes; §9.4's table lists more, and R4 no longer states a count.)* |
| new invariants | §9.4's full invariant set (superseding both R1's single flawed bullet and R2's flawed iff chain, B1/B2/B6/B7); W=`NOT_ATTEMPTED` ⇔ `refused_at_step == "L1"`; W=`NOT_ATTEMPTED` ⇒ workspace facts false, residual 0, no other resource-creation fact true, no Git observation, no verification; W=`ATTEMPTED_NO_AUTHORITY` ⇒ `refused_at_step == "L2"`, workspace facts false, `"L27"` ∈ failure steps; §5.1's pure-durable rules **R-P1…R-P6** (R4/B14 — replacing R3's rules that referenced non-durable internal stages); `pre_dispatch_refusal_code` present ⇔ `refused_at_step` present, with the three REFUSAL/POST_DISPATCH_UNEXPECTED/NO_DISPATCH_FAILURE modes exactly as §9.2/§9.4 state them (B6, corrected from R2's flawed chain). **Every v2 invariant is a function of fields in the artifact; none may reference an in-memory fact** |
| filesystem identities (§7.2) | **explicitly NOT added to the schema** — held in memory only, between P1/P2R/P4 and L14, never durable (§5 P6). Likewise no issuance token, child identity, digest of unredacted generated bytes, or extension path is added (§9.2a/§9.2b) |

Knock-on (decision D-3): the refusal record's closed `refused_record_kind`
enum names `pi-harness-cfg1-run.v1`. Recommended: `pi-harness-cfg1-refusal.v2`
naming run v2, with refusal v1 retained unchanged (no refusal artifact exists in
history, but the rule "a version keeps its meaning" is simpler to review than an
additive widening). The **stage-closure record is unchanged (v1)**: its fields,
halt vocabulary, and precedence do not change — only which code a given run
produces. Validator dispatch and the §22.5 run-path verifier gain the v2 pairs.

---

## 11. Minimum regression suite (implementation phase)

All offline: synthetic workspaces under `tmp_path`, injected leaf doubles for
resolution/digest/probe, no real Node or Pi, no socket, no credential.
Identity-probe tests that need a real child use a **synthetic script under
`tmp_path`** as the "node" executable. Numbering is illustrative.

| # | Scenario | Must prove |
|---|---|---|
| **A** | L1 refusal (resolution, seam, **P2R identity-drift**, probe, version, and `git_executable` failures — each separately) through the real executor **and** the stage-runner offline seam | mint-leaf call count 0; W `NOT_ATTEMPTED`; `lifecycle_failure_steps == []`, `lifecycle_all_closed`; `REFUSED_PRE_DISPATCH`; halt `PRE_DISPATCH_REFUSAL`; ordinals 2–9 `NOT_EXECUTED`; registries empty; v2 record validates; **(B1/B7/B8)** each P case's tuple is a member of §5.1's `Allowed(F)` for its own code — **both** P2R variants (seam-byte drift → `S == false`; identity drift → `S == true`) are exercised — and `pre_dispatch_refusal_code == "OFFLINE_PREFLIGHT_FAILED"` for every one of them (never a P-stage code directly); **(R4/B14)** the `git_executable` case carries `pi_identity_failure_code == null` and exactly σ (R-P3) |
| **B** | mint creates a tree then raises; mint returns a malformed tuple (incl. one wrapping a genuine workspace); mint returns a foreign type | W `ATTEMPTED_NO_AUTHORITY`; `L27`; `INDETERMINATE_LIFECYCLE`; halt `LIFECYCLE_CLOSURE_UNPROVEN`; the tree still exists afterwards; no remover call |
| **C** | genuine workspace, later refusal at L3/L4/L7/L12 | W `AUTHORITY_RETURNED`; teardown success → closed, tree gone; injected re-proof failure or residual → `L27`, tree untouched |
| **D** | any seam mismatch / missing seam file / reparse component / non-regular file / oversize (P2 failures) | probe-runner call count 0; credential resolver call count 0; route observer call count 0; `pi_observed_version == "NOT_OBSERVED"`; **(B1)** `pi_version_probe_attempted == false`; **(B7)** `pi_identity_failure_code == "PI_SEAM_UNPROVEN"`, `pre_dispatch_refusal_code == "OFFLINE_PREFLIGHT_FAILED"` |
| **E** | valid seams, P2R passes, probe reports `0.87.0` / garbage / oversize / non-zero exit / timeout (P3 failures) | probe env name set **equals** §6's allowlist; bounded literal recorded; refusal before L2; credential resolver never called; **(B1)** `pi_version_probe_attempted == true`, `pi_seam_digests_match == true` (P2/P2R passed; P4 never ran since these are P3-stage failures); **(B7)** `pi_identity_failure_code == "PI_PROBE_FAILED"` |
| **F** | parent mapping holds decoys for every excluded name (incl. `NODE_OPTIONS`, `PI_QUALIFICATION_B300_ROUTE_KEY`, `AIDO_LITELLM_API_KEY`, `AIDO_LITELLM_BASE_URL`, `AWS_SECRET_ACCESS_KEY`) | none reach the child (checked in the child, via the synthetic script's own report of its environment names); an access-recording mapping shows **only** `PATH` and `SystemRoot` were ever read; a `None`/foreign env object makes the runner refuse |
| **G** | unexpected raise injected at L2 (after mint), L5 (after credential), L9, L10, L11, L14, L18 (after write, via a non-`dict` response), L20, **and inside P itself at every boundary (R4/B14)**: before P2 completes; after P2, before P2R completes; after P2R, before P3's entry; after P3's entry; inside P4; inside P5; during P6 construction or result-shape validation; and after P's success commit (Git resolution) | never `L1` with a P-stage code; step equals cursor; **(B2/B6)** L18(post-write)/L20 fall in **POST_DISPATCH_UNEXPECTED** mode — **no** `refused_at_step`/`pre_dispatch_refusal_code`, `unexpected_failure_step` equals the cursor instead (never both present — Test T formalizes this); an unexpected raise inside P falls in **REFUSAL** mode with `pre_dispatch_refusal_code = "UNEXPECTED_STEP_FAILURE"`, **(B7)** `pi_identity_failure_code == null` (never one of the six typed codes), and **(R4/B14)** a tuple in U — exactly `(false, false, NO)` for the four boundaries before P3's entry, `(true, false, NO)` for the four at/after it and before P's commit, and σ after P's commit; the v2 validator is run on the serialized record **alone**, with no access to the executor's state, and accepts each; `dispatch_state` is `SEND_STATE_INDETERMINATE`/as observed; lifecycle obligations match what was created (W, `runtime_created`, `broker_resource_created`); every record validates under v2; no needle text in any sink |
| **H** | pre-consumption gate with drifted seams / version | gate returns a closed refusal; stage-output mint registry and `RESULTS_ROOT` unchanged (no execution directory); no credential read; probe count 0 on seam drift |
| **I** | gate passes on state S₀; the double switches to drifted S₁; then the stage runs | L1 refuses; the gate's leaf observations are provably not consulted by L1 (L1 re-invokes every leaf); record as in A |
| J | resolution adversaries **(B3, exhaustive)**: `node.exe`/`pi.cmd` planted in the current directory; `node.cmd` earlier on `PATH`; relative and empty `PATH` entries; Node or Pi root inside the checkout; a second, valid Pi root later on `PATH` when the first fails P2; **a `PATH` entry itself is a junction**; **`pi.cmd` is a reparse point or a directory** at that exact name; **a package-root candidate directory component is a junction/reparse point**; **a `node.exe` candidate is a reparse point** | cwd never selected; `.cmd` never selected; later candidates never tried; **every §7.2 `reparse_point` classification refuses that candidate outright, before realpath is called on it**; a repo-local lexical junction resolving (via realpath) to a location outside the checkout is still refused (containment is checked on the lexical form, not only the realpath'd destination) |
| K | a probe that rewrites a seam file (synthetic runner side effect, i.e. a P4 failure) | P4 refuses before L2; credential resolver never called; **(B1)** `pi_version_probe_attempted == true` **and** `pi_observed_version == "NOT_OBSERVED"` simultaneously — the exact case R1's schema could not represent; **(B7)** `pi_identity_failure_code == "PI_SEAM_CHANGED_DURING_PROBE"` with `pi_seam_digests_match == false`; **(R4/B14)** a second case in which only the package-root identity changes during the probe (seam bytes intact) yields the same code with `pi_seam_digests_match == true` — both tuples in `Allowed(PI_SEAM_CHANGED_DURING_PROBE)` |
| L | gate and L1 share P | the same function object is reached from both (identity check), and P's stage order is fixed with only leaves injectable |
| M | a probe child that spawns a descendant holding stdout open past the deadline | AIDO's wait returns by its own bound; no claim that the descendant stopped |
| N | v1 compatibility | synthetic v1 payloads (never the real results files) validate/refuse exactly as before; the v1 closure function's outputs are unchanged on a golden set including an A3-shaped payload |
| O | step/code table | a forged `(L1, ROUTE_UNAVAILABLE)` or a refusal code without a step fails v2 validation → `RECORD_INVARIANT`, halt; a forged `(pi_identity_failure_code=PI_PROBE_FAILED, pi_version_probe_attempted=false)` likewise fails (§5.1/§9.4); a forged `pre_dispatch_refusal_code=PI_SEAM_UNPROVEN` (a P-code written into the wrong field) fails (B7); **(R4/B14)** each of these forged records fails R-P2…R-P6 by durable fields alone: `pi_identity_failure_code` set at `refused_at_step = "L7"`; `(L1, OFFLINE_PREFLIGHT_FAILED, F = null)` with any tuple ≠ σ; `(L1, UNEXPECTED_STEP_FAILURE)` with `(true, true, NO)` or with a non-null `F`; a clean or post-L1 record with `pi_observed_version ≠ PINNED_PI_VERSION` |
| P *(D-4)* | seam changed between L1 and L14 | no spawn; `RUNTIME_LAUNCH_FAILED` at L14; full closure of what exists |
| **Q** *(B9 retained; R5/OC-11 + B15 — rewritten as the L9 endpoint-material matrix)* | The **genuine** `cfg1_pi_config.write_cfg1_pi_config` (tmp_path, synthetic workspace, synthetic `.invalid` endpoint — never an injected double) through the real executor. **Q-a (retained from R4):** a step-11 release failure (config-dir pin, root pin, each child close) after step-10's `register_config_issuance` genuinely succeeded; a `register_config_issuance` validation failure before its own registry write. **Q-b (new):** a failure injected at **every** point after `endpoint_write_attempted` — (1) the models write raising partway; (2) step 9; (3) step 9a, in each Test W perturbation; (4) a step-10 refusal; (5) an unanticipated body exception; (6) the disposal call returning `False`; (7) the disposal call raising; (8) disposition ok and the **models child's** close failing; (9) disposition ok, models close ok, only the `settings.json` child's close failing; (10) config-pin and (11) root-pin release failures — cases (1)–(11) each once as a failure *already known* and cases (8)–(11) again as a release failure first discovered after a **successful** generation (G3); plus pre-write controls: a failure at each of steps 0–7, and a `settings.json` write failure | **Q-a:** `config_issuance.discard_config_issuance` is observably called with the genuine token **before** the closed code is raised; the pre-registration failure leaves `_ISSUED` unchanged; `state.generated_config` is unset on every path. **Q-b:** for every row, the raised error's `endpoint_material_outstanding` equals §9.2c's table **as an exact bool**; a recording double shows `generated_config_scrub_verified` is `False` at the instant `write_config` is entered; afterwards it is `True` **only** for the exact-`False` rows; call-order recording shows disposition **strictly before** the same handle's close; `unlink`/`os.remove` call count is 0; `models.json` is gone-by-handle in the `False` rows and **still on disk** in every `True` row; a post-success release failure leaves the fact `False` with the issuance discarded; **an L27 whole-root success following a `True`-outstanding row leaves the fact `False`** and lifecycle `INDETERMINATE_LIFECYCLE` with `"L24"` in the failure steps (G5); an untyped, non-bool or malformed error from a double leaves it `False`; the pre-write controls yield `False` outstanding and the fact `True`; no endpoint, URL, path or exception text appears in any exception, record or console line |
| **R** *(B9; rewritten R4/B12)* | the CFG1 transactional extension writer, failure injected at: E0–E5 (before any child exists); E6 (after some children exist); E7 (gate refusal); E8 after static children but **before** the token write; E8 **after** the token write; E9; E10; and each E11 release failure after a genuine E10 registration; plus an **unanticipated** raise inside the writer | no pathname deletion anywhere (`unlink`/`os.remove`/frozen `scrub_generated_extension_config` call count 0 — the frozen AR2 writer and scrubber are never called by CFG1); every disposal goes through the creating handle; `token_material_outstanding` is exactly `false` before the token write and after a verified token-child disposal **followed by a successful close** (R5/B15), exactly `true` after an E11 release failure following a genuine registration; `extension_binding_scrub_verified` is `false` before the call (write-ahead), becomes `true` **only** for an exact `false` outstanding flag, and stays `false` for the bool `true`, a non-bool, or the unanticipated raise; the last group lands in `INDETERMINATE_LIFECYCLE` / halt `LIFECYCLE_CLOSURE_UNPROVEN` with `"L24"` in the failure steps; no issuance remains registered after any failure; `EXTENSION_GENERATION_FAILED` at L11; the directory is never removed by the writer; an offline tmp_path comparison proves the successful tree is byte-identical to the frozen writer's output *for the pinned inputs* (**R5:** that comparison is not the provenance proof — Test Z is); **(R5/B15)** two further cases — the token child's disposition succeeds and its **close then fails** → `token_material_outstanding` exactly `true`, `extension_binding_scrub_verified` `false`, `"L24"` in the failure steps; and a release failure first discovered during E11b on a **success** exit → outstanding `true`, **no disposal attempted** (call recording), issuance discarded, run fails — with call-order recording proving disposition strictly precedes the same handle's close in every disposed case |
| **S** *(B3, new)* | `node.exe` replaced (same path, new file, matching seam-adjacent bytes where applicable) after P4 passes, before L14; package root replaced the same way | L14's §7.2 identity re-check (AM-8) detects the mismatch even though the lexical path is unchanged; `RUNTIME_LAUNCH_FAILED` at L14; no spawn; distinguished from Test P (which changes seam *bytes*) by changing the filesystem *record* while keeping bytes constant |
| **T** *(B2, corrected B6)* | exhaustive check of the `refused_at_step`/`pre_dispatch_refusal_code`/`unexpected_failure_step` triple across every row of §9.2's table, every step, **and the clean-pass (no exception at all) case** | every record falls into exactly one of the three modes (**REFUSAL** / **POST_DISPATCH_UNEXPECTED** / **NO_DISPATCH_FAILURE**, §9.2/§9.4); a clean run with **all three fields absent** validates successfully (the case R2 rejected and B6 restores); a record with two of the three families present simultaneously fails v2 validation; a record with `refused_at_step` absent and `pre_dispatch_refusal_code` present (or vice versa) fails the one direct iff |
| **U** *(B8, new)* | `node.exe` replaced between P1's capture and P3's `CreateProcess` (i.e. during or immediately after P2); package root replaced the same way, with the replacement crafted to pass P2's 20-file digest subset while differing elsewhere | P2R refuses **before** `CreateProcess` is ever called for the probe; probe-runner call count 0 for both scenarios; `pi_version_probe_attempted == false`; `pi_identity_failure_code == "PI_IDENTITY_DRIFTED_BEFORE_PROBE"`; distinguished from Test S (which targets the window before L14's *second* execution) by targeting the window before P3's *first* |
| **V** *(R4/B11, new)* | P2 passes; then, with the package-root directory object **and** `node.exe` left unchanged, `dist/cli.js` is (i) modified in place (same file id) and (ii) replaced by a new file in the same directory; separately (iii) any other pinned seam file is modified in place | the final pre-P3 proof (P2R step a) refuses in every case; **probe-runner call count remains 0**; `pi_identity_failure_code == "PI_IDENTITY_DRIFTED_BEFORE_PROBE"`, `pi_version_probe_attempted == false`, `pi_seam_digests_match == false`; P4 is never reached; a double that records call order proves P2R's seam walk and both identity checks complete before the runner is invoked and that nothing but P3's write-ahead sits between them |
| **W** *(R4/B13, new)* | the genuine `write_cfg1_pi_config` (tmp_path, synthetic workspace, synthetic `.invalid` endpoint), with the models child's step-8 write perturbed so the **actual** bytes differ from the pinned arm shape (one extra space; a swapped key order; a bare `\n`; the URL written twice; the URL written with non-ASCII escaping) while `redacted_models_digest(arm_id=…)` still equals `ARM_REDACTED_DIGEST[arm]`; and each arm Q/R/E/H unperturbed | every perturbed case refuses at step 9a before step 10 (`issued_token_count()` unchanged, both children disposed by handle, `CONFIG_GENERATION_FAILED` at L9 through the executor); every unperturbed arm passes; no endpoint or unredacted digest in any exception, record, or console line; the retained pin-agreement and malformed-input regressions still pass |
| **X** *(R4/B12, new)* | (i) successful L11, then — before L24 — `ar2_config.ts` is deleted and a same-name file created in its place (new file id, arbitrary bytes, including byte-identical ones); (ii) same, but the replacement is a reparse point; (iii) successful L11, then the `pi_extension` directory is swapped for another ordinary directory holding a same-name file | L24 deletes **nothing** in every case (the foreign object still exists afterwards); `extension_binding_scrub_verified == false`; `"L24"` in the failure steps; `INDETERMINATE_LIFECYCLE`; the extension issuance is discarded; L27 then removes the tree only if whole-root authority re-proves, independently — and an L27 success does not change the L24 fact |
| **Y** *(R5/B15, rewritten R6/B17)* | `win_config_authority.identity_bound_unlink` on a synthetic file under `tmp_path` (Windows/NTFS only); executor-level cases drive the real L24 for **both** `models.json` (config issuance) **and** `ar2_config.ts` (extension issuance). **Y-1 close failure (R5):** with the close of *that* descriptor fault-injected: (i) match ∧ one link ∧ disposition ok ∧ close **fails**; (ii) disposition fails ∧ close fails; (iii) identity mismatch ∧ close fails; (iv) `open_osfhandle` fails. **Y-2 rename:** issuance verification passes, then — via a hook between verification and the unlink — the issued file is renamed (`models.json`→`leak.bin`; `ar2_config.ts`→`leak.bin`), once inside the directory and once to a different directory on the volume; a variant also plants a foreign same-name file. **Y-3 alias, same directory:** the issued file has a second hard link in its directory. **Y-4 alias elsewhere:** a second hard link in another directory on the same volume. **Y-5 control:** one link, identity match, disposition ok, close ok. **Y-6 continuity:** after the exclusive L24 handle is acquired and before the disposition (a hook at that exact point), attempt `CreateHardLinkW`/`os.link` to the object and a rename of it. **Y-7 link-count faults:** the link-count query returns unreadable, `None`, `0`, `2`, `True`, a non-`int`. **Y-8:** the object **absent** with nothing renamed. **Y-9:** repeat Y-2…Y-7 through the L24 path of **both** files | **Y-1:** (i) returns **`False`**, never `True`; `close_failure_count()` increments with kind `"unlink_handle"`; no retry and no pathname unlink (count 0); (ii)–(iv) `False`. **Y-2:** `False`; the **renamed issued object still exists with its original bytes**; the disposition spy count is 0; no pathname unlink of any kind; the foreign same-name file, if planted, is untouched. **Y-3 / Y-4:** `False` with **no disposition** (spy count 0) — every link still exists and the bytes are intact. **Y-5:** `True`, the object is gone, exactly one disposition. **Y-6:** alias creation **and** rename **fail** (sharing violation); the link count read afterwards is still exactly 1; the disposition then proceeds normally — and if either *succeeds* the test fails and the implementation stops and returns to design. **Y-7:** every fault → `False`, no disposition (a `bool` never satisfies "exactly 1"). **Y-8:** `False` (R5's "absent ⇒ `True`" is withdrawn). At L24, for **both** files and every `False` case, the corresponding scrub fact (`generated_config_scrub_verified` / `extension_binding_scrub_verified`) is `False`, `"L24"` is in `lifecycle_failure_steps`, classification `INDETERMINATE_LIFECYCLE`, halt `LIFECYCLE_CLOSURE_UNPROVEN`, **L26 is skipped** (`LIFECYCLE_UNPROVEN`, verification child never started), and **a subsequent L27 whole-root success leaves every `False` fact `False`**; Test X's foreign-object cases still leave the foreign file present |
| **Z** *(R5/B16, new)* | The CFG1 transactional extension writer, tmp_path only, over a **synthetic** extension source directory reached through the writer's single source-directory derivation leaf. The test carries its **own** literal pin table and template pin, independent of the writer's pin module. (1) After admission and **before L11**, each of `tools.ts`, `index.ts`, `package.json`, `ipc.ts` in turn is modified: one byte changed, one appended, truncated, replaced by a same-size different file, replaced by a longer file; (2) a source is modified **after its pinned read** but before E8 (hook after E-1 / at E6); (3) the runtime template differs from its pin: one character changed, an extra `%s`, an extra bare `%`; (4) unperturbed run; (5) an extra file present in the source directory; (6) a source that is a directory / reparse point / oversize | (1) refuses at E-1 with `EXTENSION_SOURCE_UNPINNED` **before E0**: no `pi_extension` directory, `token_write_attempted` never set, **zero extension bytes written anywhere**, `token_material_outstanding == false`, `extension_binding_scrub_verified` `true`, `EXTENSION_GENERATION_FAILED` at L11; (2) the output is still **byte-identical to the pinned bytes** — a read-recording leaf shows exactly **one** open per source and none afterwards — and issuance succeeds; (3) refuses with `EXTENSION_TEMPLATE_UNPINNED` before E0; (4) every written static child's read-back **and** issuance digest equals the **test's own literal**, and `ar2_config.ts` hashes to the **frozen §9.2c-D golden-vector literal** (the test rebuilds the document independently from the four frozen input literals and compares to the literal; it never derives the expected digest from the production serializer): the issued bytes are shown to descend from independently pinned inputs, not from whatever was present at run time; (5) the extra file is neither read nor copied; (6) refuses; the pin module is asserted to be a member of the G4/G5 lineage set |

Existing T-11 rows are kept and extended (lifecycle, classification, halt), not
rewritten to accommodate new behavior.

---

## 12. Adversarial review

### 12.1 Round 1 — the required questions

| Question | Answer |
|---|---|
| Who creates each identity/provenance fact? | §5 "who creates each fact": paths from filesystem metadata (P1), seam match from AIDO-read bytes (P2/P4), version from child stdout (P3, a Pi claim used only as a cross-check). W and the cursor are written only by the executor, write-ahead. |
| Who can mutate the Pi installation between checks? | Any same-user process, an npm/nvm operation, and — during P3 and after L14 — Pi-executed code itself. Covered before the first execution by P2R's final proof (R4/B11 — seam bytes **and** identities), before the second by D-4; persistent changes during the probe detected afterwards by P4; changes between gate and L1 by L1's from-scratch re-proof. Not covered: transient swap-and-restore inside a check→use window (§7 TOCTOU). |
| Can a supported caller bypass the canonical proof? | Not for L1: the genuine ports are bound inside `bind_genuine_cfg1_run_executor` with no parameter, and the order lives in P's body. A launcher can skip the *gate* — which wastes an authorization but bypasses no security invariant. Offline injected ports are refused against the genuine package root (existing CFG1-IMPL-FU1 guard). |
| Can version and seam facts come from different roots? | No by construction: P3 executes the exact lexical `cli.js` path P2 digested and P2R — the final operation before `CreateProcess` — re-digested (R4/B11), under the same root object P2R re-proved by identity, and P4 re-proves that root afterwards **against the §7.2 identity P1 captured, not merely against the lexical path** (B3) — so a same-path replacement is caught even when its bytes are made to collide with the pinned digest. Residual: a change inside the P2R-final-proof→`CreateProcess` sliver, or inside L14's own re-proof→`CreateProcess` window (§7.1's TOCTOU table); both are stated, not claimed closed. |
| Can the pair L14 launches be a different pair than the one P3 proved? | Not without detection, as of B3: L14 (AM-8) re-checks both the seam digests and the §7.2 filesystem identity of the resolved Node and package-root objects against what P1 captured, immediately before `CreateProcess`. The claim "the pair L14 launches is exactly the pair P3 proved" is therefore mechanically true up to the residual millisecond re-proof→spawn window — and the design states that residual explicitly rather than asserting unconditional equality (§7.1). |
| Can the child regain stripped secrets through inherited mechanisms? | Not through environment, command line, handles, or cwd (§6). It can by non-inherited same-user OS means (reading the parent's memory, the user's files/registry); stated, not denied. |
| Can PATH/PATHEXT/cwd select a different executable after validation? | No: resolution happens once, never consults cwd or `PATHEXT`, and the probe and L14 use the resolved absolute path with the executable pinned — nothing is resolved by name again. Git resolution (`shutil.which`, cwd-first on Windows) is unchanged and out of scope (OC-7). |
| Can individually valid Node and Pi objects disagree? | Node is not a frozen CFG1 identity (no pin exists; adding one is a re-derivation, OC-2). What is bound: the *pair* L14 launches is exactly the pair the probe proved launches and reports the pinned version, via one identity object. Node and Pi may come from different installs; that is observable only as a probe failure. |
| Can a partial mint be mistaken for no mint? | No: W is set before the port call; only a return of the exact genuine shape advances it further; the registry-emptiness halt is an independent second witness. |
| Can post-validation mutation invalidate cleanup authority? | Yes, and it fails closed: L27 re-proves against the marker; a changed root is never deleted and yields `L27`. W never authorizes deletion by itself. |
| Can a raw exception or secret-bearing diagnostic escape? | P and the catch-all read no exception content; P emits closed codes and pinned relative seam keys at most; probe stdout is compared then dropped, stderr is never captured. AR2's exception strings (which embed the reported version) are no longer on the path. |

### 12.2 Round 2 — adversarial review of this design

1. *"The seam proof makes the probe safe."* **False, and the design must not
   say it.** The 20-file seam set is not a whole-package manifest: `cli.js
   --version` loads transitive, unpinned JavaScript under the package root
   before printing, and L14 does the same with the credential present. P2
   guarantees only that the frozen seams are the frozen bytes. → OC-2.
2. *W could be set correctly while `refused_at_step` is wrong, or the reverse.*
   The v2 validator's bidirectional W⇔L1 invariant turns any disagreement into
   a self-validation refusal and a halt — never an admissible record.
3. *`UNEXPECTED_STEP_FAILURE` could become a dumping ground that hides
   anticipated failures.* Anticipated port failures keep their specific codes
   (T-11 retained), and the catch-all fires only for exceptions no step
   reduced. Test O ensures the code cannot be paired with an invented step.
4. *The minimal environment might be too small for Node on some machine.* Its
   only failure mode is a probe failure — a closed refusal that, at the gate,
   is discovered before consumption. It can never produce a false pass.
5. *Running Pi code pre-consumption is new.* True: the gate executes the same
   post-seam probe L1 does, in the launcher process, whose environment holds
   the credential names. The child receives none; §6's same-user limit
   applies equally at L1, which already ran this probe in the same process
   before this design. Net exposure strictly decreases (before: unproven code
   with the full environment; after: seam-proven entry with a four-name
   environment).
6. *First-candidate-only resolution may refuse a legitimate multi-install
   machine.* Accepted: a closed refusal the operator fixes by `PATH` order,
   before consumption. Searching for "a candidate that passes" would let any
   seam-matching copy anywhere on `PATH` be selected — a repair by search.
7. *P4 detects only persistent changes.* Correct and stated; it exists to catch
   probe-executed code that edits the pinned seams, not to close TOCTOU.
8. *The v2 bump could make new code emit v1 by mistake.* The corrected executor
   emits v2 only; v1 is reachable only through validation/verification of
   existing bytes. Test N pins v1 behavior; a test pins that the payload
   builder emits exactly v2.
9. *Stage-closure v1 reused with v2 run records.* Its schema and meanings are
   unchanged; what changes is the input facts. No stage-closure field names or
   depends on the run-record version. Accepted.
10. *The gate reads `PATH`.* `PATH` is non-secret configuration; it is read by
    name, never forwarded to the probe, never recorded.
11. *The D-6 derivation cannot be done yet (0.85.1 not installed, and the Pi
    installation lies outside this repository's boundary).* The implementation
    phase therefore cannot complete the `--version` side-effect derivation
    without operator-provided pinned bytes. Stated as a blocker (OC-3), not
    assumed away.

---

## 13. Implementation scope

**Allowed (one offline implementation phase, after acceptance and D-1…D-6):**

- `experiments/pi_harness_cfg1/`: the canonical proof P with injectable leaf
  effects, **including the P2R final pre-execution proof — complete seam set
  plus both §7.2 identities (§5, B8, redefined R4/B11)** — and P's single
  result object with its atomic family commit (§5 P6, R4/B14); the §7.2
  no-follow/identity primitive; the identity-probe environment builder; the
  pre-consumption gate entry; executor changes for the cursor, W, dispatch
  write-ahead, the category-A/category-B write-ahead split (§9.2a) —
  **`config_issuance_possibly_created` is explicitly NOT added** (B9) and
  **`extension_failure_path_scrub_verified` is explicitly NOT added** (R4/B12,
  retracted) — and the catch-all; **(R4/B12, AM-9/AM-10)** a new CFG1-owned
  transactional extension writer and extension-issuance module, the
  typed-interval extension of `win_config_authority`'s generator binding to
  exactly two bound generators, a bytes-mode child write sibling of
  `write_child_text`, the identity-bound L24 extension scrub, and removal of
  `_scrub_extension_binding` and of the `write_disposable_extension` port
  binding from CFG1's call graph; **(R4/B13, AM-11)** step 9a in
  `write_cfg1_pi_config` and the expected-digest binding in
  `register_config_issuance` (§9.2b); **(R5/B15, AM-12)** `identity_bound_unlink` returns `True` only after one
  exclusive-handle interval proved identity and exactly one hard link and the
  deletion-bearing handle closed successfully, returns `False` on **any** open
  failure including absence, and records a close failure (`"unlink_handle"`) —
  with the identity-less pathname branch and the non-string early `True` removed
  from L24's path **(R6/B17)**; **(R5/OC-11, AM-13)** `endpoint_material_outstanding` on
  `Cfg1PiConfigError`, the writer's single failure-path release that disposes
  `models.json` by its creating handle then closes it, and the executor's
  write-ahead plus one exact-type/exact-bool rule for
  `generated_config_scrub_verified`; **(R5/B16, AM-14)** a CFG1-owned pin
  module (four sources, the template, the golden vector) and the single pinned
  read E-1; the genuine port binding switched from
  `ar2.launch.resolve_runtime_identity` to P; v2 run-record (and, per D-3,
  refusal-record) builders/validators — including `pi_version_probe_attempted`,
  `pi_identity_failure_code` (B7), `unexpected_failure_step`, the three-mode
  validator (B6), and §5.1's pure-durable rules R-P1…R-P6 (R4/B14) — the v2
  closure function, dispatch-table entries; D-4/AM-8's L14 re-proof (seam
  **and** §7.2 identity); **removal** of the live
  `preflight_config_generator_self_check`-equivalent step from frozen L1
  (there was none in CFG1's own shipped code to remove — see §16 — so that
  removal is documentation-only; the replacement proof is step 9a, which **is**
  code). **Not** allowed here: calling into, or editing,
  `qualification/i2b_live_adapters.py` (OC-9/OC-10 are resolved by *not*
  wiring it in, §16); editing any file under `ar2/` — CFG1 only *reads* the
  frozen extension source files and the frozen `_GENERATED_CONFIG_HEADER`
  template, **once**, against CFG1-owned pins (AM-9, AM-14). (OC-11 is now *in*
  scope — §9.2c — and is no longer excluded.)
- `experiments/pi_harness_cfg1/tests/`: §11, plus extension (not weakening) of
  existing tests whose expectations encode the corrected defects.
- The frozen CFG1 design: a pointer/amendment section for AM-1…AM-14 as
  accepted, in the style of prior FU sections.

**Prohibited:** repinning Pi or changing the seam table; editing any `ar2` or
`qualification` module; changing arms, schedule, Q/R/E, L16-FU2/ERR1,
provider/model/backend, prompt, retry policy, or stage-closure schema;
editing, re-validating into a new meaning, moving or deleting A1/A2/A3
evidence or authorization documents; any live run, Node/Pi execution against
the real installation, network access, credential read, or real B300 contact;
job objects, `taskkill`, process-group or `psutil` process-tree management;
sandboxing or network-denial claims; a whole-package Pi manifest (OC-2);
`CLAUDE.md` edits; authorizing or drafting A4 or Stage 2; commit, push,
branch, or PR automation.

---

## 14. Open contradictions and reviewer decisions

| Id | Item | Status / Recommendation |
|---|---|---|
| **D-1** | v1 cannot represent the corrected semantics truthfully (§10). Accept a run-record **v2** with v1 retained unchanged? | **ACCEPTED** by the reviewer for R2. |
| **D-2** | Durable projection of L1 sub-failures: only `pi_seam_digests_match` + `pi_observed_version` (+ console codes), or also a closed durable sub-code? | **CLOSED (R3, B7).** A closed durable sub-code: new field `pi_identity_failure_code` (§5.1, §9.4, §10). R2's claim that the three original facts alone already distinguish every P-stage was itself wrong — resolution failure and initial seam failure both produce the identical `false`/`false`/`NOT_OBSERVED` triple; only the new field actually distinguishes them. |
| **D-3** | Refusal record: `pi-harness-cfg1-refusal.v2` vs additive widening of v1's `refused_record_kind`. | **ACCEPTED** (v2 refusal-record format) by the reviewer for R2. |
| **D-4** | L14 pre-launch seam re-proof (AM-8). | **ACCEPTED**, and **extended by B3** to also re-prove §7.2 filesystem identity, not seam digests alone. |
| **D-5** | Closure-phase totality (OC-4). | May remain a separate follow-up phase, but is now an **explicit pre-A4 barrier** (§17 item 4) rather than an unordered "unless the reviewer wants it folded in." |
| D-6 | Contingency if 0.85.1's `--version` reads config/auth or writes before printing. | Unchanged: if pinned 0.85.1's `--version` behavior contradicts this design's assumptions, the implementation phase **stops and returns to design**; it does not improvise. |
| **OC-2** | The frozen Pi identity is the 20-file seam set; everything else under the package root (and Node itself) is unpinned yet executes at P3 and L14. I-1 holds relative to "the frozen identity CFG1 requires", not relative to all executed code. §7.2 (B3) binds filesystem *record* identity, not content, and explicitly does not close this OC (§7.2's own "Scope, stated once" paragraph). | A separate re-derivation phase if a whole-package manifest and/or Node pin is wanted. Not this phase. |
| **OC-3** | The `--version` side-effect derivation (§5) needs pinned 0.85.1 bytes, which are not installed and lie outside this repository's boundary. | **Remains a blocker to implementation** (unchanged) and is an explicit **pre-A4 barrier** (§17 item 2). Operator supplies/restores pinned 0.85.1 (outside AIDO) before implementation completes; or reviewer re-scopes. |
| OC-4 | `_closure_phase` is not total: e.g. a non-`dict` from `supervisor.shutdown()` (`run_executor.py:825`) or `shutdown_for_cfg1()` (`:872`) raises out of `execute_cfg1_run`, skipping remaining closure (incl. L27) and producing no record (`RUN_EXECUTOR_RAISED`). Fail-closed for deletion, but evidence is lost. | May remain a separate follow-up, but is now an **explicit pre-A4 barrier** (§17 item 4), same disposition as D-5 (this is D-5's own subject). |
| OC-5 | L3 gates on `getattr(baseline_verification, "passed", True)` truthiness (`run_executor.py:544`): a malformed falsy `passed` proceeds as "failed as seeded". | May remain a separate follow-up, but is now an **explicit pre-A4 barrier** (§17 item 5). |
| OC-6 | `ar2.launch.resolve_runtime_identity` retains the D6 ordering and inherited environment for AR2's own callers. | Leave frozen; flag if AR2 is ever run live again. AR2 live execution remains **NO-GO** while OC-6 is unresolved (reviewer's explicit statement, §17). |
| OC-7 | Git resolution (`resolve_git_executable`) uses `shutil.which` (cwd-first on Windows). Confirmed (B5, §16) to run inside L1's boundary in this design (§4), but is not a Pi identity and spawns nothing at resolution. | Out of scope; note only (unchanged by B5's reconciliation — §16's table row for Git resolution states this explicitly rather than leaving it a bare cross-reference). |
| **OC-8** | Frozen §16.2 L1 lists further checks (fixture revision pin, generator self-check, arm↔schedule binding, `preflight_pi_installed_offline`, environment audit) not all performed inside the shipped executor's L1. | **RESOLVED for this phase** by the complete reconciliation in new §16 (B5). Two genuine gaps were found and are newly tracked as OC-9/OC-10 below; every other item is accounted for (preserved elsewhere, or moved-in-label-only). |
| **OC-9** | `preflight_pi_installed_offline` (`qualification/i2b_live_adapters.py:1361`) is listed in frozen §16.2 L1's text but is **not imported or called anywhere in `pi_harness_cfg1/*.py`**. | **DECIDED BY REVIEWER (R3, B10): do NOT wire it in.** Frozen §16.2 L1 is explicitly amended so that canonical proof P **supersedes** this named helper for CFG1 — one canonical Pi resolution/provenance definition, not two independent AR2-based resolvers running in parallel. §16 states exactly which of the helper's four documented obligations P subsumes, and how. |
| **OC-10** | `preflight_config_generator_self_check` (`qualification/i2b_live_adapters.py:1517`, the frozen text's "generator self-check on synthetic URL") validates the **qualification** generator's own write/verify round trip against a fixed `.invalid` placeholder URL — not CFG1's `write_cfg1_pi_config` at all — and is never called by CFG1. | **DECIDED: Option B, REWRITTEN R4 (B13).** *R3 retraction:* R3 said L9 "already" digest-pins actual output against the pinned arm digest; it does not (§9.2b lists the four source facts). R4's Option B is: (i) a **new** L9 step 9a comparing the **actual** on-disk `models.json` bytes — read through the proven descriptor, with only the declared newline mapping and a one-slot endpoint redaction applied — with the independent pinned `ARM_REDACTED_DIGEST[arm]` (and `settings.json` with `PINNED_SETTINGS_SHA256`), before issuance, with no endpoint entering evidence and no expected value recomputed from the generator; plus (ii) the retained offline pin-agreement and malformed-input regressions and new Test W. **Temporal change, named as AM-11:** frozen L1's check would have run pre-L4; step 9a runs post-L4/L7. The guarantees are not identical; the design accepts pre-credential detection being given up in exchange for a proof about actual bytes. If the reviewer rejects that trade, the alternative is a CFG1-specific credential-free pre-L4 self-proof, which R4 does not propose. |
| **OC-11** *(new R4; **CLOSED R5**)* | A genuine L9 failure after step 8 (other than step 9a's own) left an endpoint-bearing `models.json` on disk with no handle disposition, while `generated_config_scrub_verified` stayed at its initial `True` (`run_executor.py:300, 623`); L27's whole-root removal does not prove an individual scrub. | **CLOSED (R5) — reviewer disposition: fold into FU1 now.** Specified in §9.2c-A and AM-13: write-ahead `False` before `write_config`; writer-owned `endpoint_material_outstanding` (`endpoint_write_attempted ∧ ¬(failure_known ∧ disposed ∧ closed)`); an exact-type/exact-bool executor rule; L27 never upgrades the fact; tested by Test Q. No new durable field. **Removed from the open list.** |
| **R-WINDOW-E** *(R4)* | The extension directory's create→pin window (a same-user actor may substitute another ordinary directory at that name). | **ACCEPTED** (reviewer, on R4) under the exact conditions in §9.2a: zero bytes before the gate; ordinary non-reparse object; file-id containment in the identity-proven root; no claim CFG1 necessarily created the directory. |

---

## 15. Recommended implementation model/effort

Claude Code, **Opus 5.5 at High** effort (xhigh acceptable for the v2
validator/invariant work). One offline implementation phase; no live
component. Resolve D-1 through D-6 and OC-3 first.

---

## 16. Frozen §16.2 L1 reconciliation (B5)

OC-8 left this open even though this phase redesigns L1. R2 closes it with a
complete reconciliation, grounded in source inspection of the shipped
`bfae384…` baseline (`experiments/pi_harness_cfg1/*.py`,
`experiments/pi_implementer_qualification/qualification/*.py`) performed for
this revision — not asserted from the frozen prose alone. Every item the
frozen §16.2 L1 row lists is covered, plus Git resolution (which this FU1
design's own §4 places inside the L1 boundary, so B5 requires it here too).

| Frozen §16.2 L1 item | Current shipped enforcement point | Exists today? | Disposition | Canonical owner after FU1 | Required regression proof |
|---|---|---|---|---|---|
| Seam digests (§14.2) | `run_executor.py` `_dispatch_phase`, calling `preflight.verify_pi_seam_digests()` — but, per DIAG1 D6, **after** the version probe, with the probe's child inheriting the full parent environment | Yes, misordered | **PRESERVED + MOVED**: same pinned digest table and comparison logic, folded into P2 (initial), P2R (final pre-execution re-proof, R4/B11) and P4 (post-probe re-proof) inside canonical proof P (§5), now strictly ordered before any Pi code executes | P2 / P2R / P4 (§5) | §11 Tests D, K, V |
| Fixture revision pin | `records.py::_require_literal(payload, "fixture_revision", CFG1_T1_REVISION)` — a **write-time (L29 emission)** payload validator; the value itself is computed by `fixture.py::_compute_fixture_revision()`. **Not an L1 gate in the shipped code**, despite its listing under frozen L1's text | Yes, but not at L1 | **PRESERVED, UNCHANGED** — wholly outside this phase's scope (P is Node/Pi identity only). The frozen L1 text's listing does not match the item's actual shipped enforcement point; this is a pre-existing discrepancy in the base design, not one this phase creates or is authorized to silently correct | Unchanged: `fixture.py` (computation) / `records.py` at L29 (validation) | None added by FU1 |
| Generator self-check on synthetic URL (T-1/T-2) | `qualification/i2b_live_adapters.py::preflight_config_generator_self_check` (line 1517) — exists in the **qualification/AR2 package**; confirmed by grep **never imported or called** anywhere under `pi_harness_cfg1/*.py`. Its own docstring/behavior: exercises `preflight_qualification`'s (not CFG1's) generator against a fixed, never-real `.invalid` placeholder URL and a fixed candidate model id — a self-test of the **qualification generator's** write/verify round trip | Exists in qualification package; **did not exist as a CFG1 L1 check** | **RESOLVED (Option B; rewritten R4/B13): narrowly amended out of frozen L1 (AM-11).** This was never a check of CFG1's own generator — it validates a *different* generator. *R3 retraction:* R3 said CFG1 "already" had a stronger run-time guarantee because L9 requires the generated `models.json`'s redacted digest to equal the pinned arm digest. Shipped code has no such comparison of **actual** bytes: `redacted_models_digest` hashes an in-memory expected document, issuance hashes the raw actual bytes, and `records.py` writes the pin (§9.2b). R4 **adds** that comparison as L9 step 9a — actual on-disk bytes via the proven descriptor, declared newline mapping, one-slot redaction, compared with the independent pinned literal, before issuance. **Not identical to the removed check:** that one (had it been wired) was pre-L4; step 9a is post-L4/L7 — AM-11 names the trade. The residual concern (generator logic on inputs a real run never exercises) stays covered offline. Frozen L1's text is narrowly amended: remove "generator self-check on synthetic URL". | L9 step 9a (new, §9.2b) **plus** the retained offline pin-agreement and malformed-input regressions of `write_cfg1_pi_config` | §11 Test W (new), Test Q (confirmatory issuance behavior), existing `test_cfg1_composition.py` pin agreement |
| Arm↔schedule binding | `_schedule_arm_for` is **re-derived fresh, never cached**, at multiple points: L0 admission (`stage_runner.py:499`, matching the frozen L0 row's own text), broker-binding construction (`binding.py:190`), and L29 emission (`records.py`, several sites) | Yes, at L0/binding-construction/L29 — not as a distinct L1-specific check | **PRESERVED, UNCHANGED** — outside P's scope; the frozen L1 text's listing does not correspond to a separate L1-only mechanism distinct from L0's own derivation (a pre-existing imprecision in the base design's L1 prose, not created here) | Unchanged: L0 (`stage_runner.py`), the binding module, L29 | None added by FU1 |
| `preflight_pi_installed_offline` | `qualification/i2b_live_adapters.py::preflight_pi_installed_offline` (line 1361) — exists in the **qualification/AR2 package**; confirmed by grep **never imported or called** anywhere under `pi_harness_cfg1/*.py`. Its own docstring names exactly four obligations: (1) Node resolves via `ar2.launch._resolve_node_executable`; (2) the Pi package root resolves via `ar2.launch._resolve_pi_package_root`; (3) `dist/cli.js` exists (`os.path.isfile` on a realpath'd path); (4) `package.json`'s `version` field is read by a plain file read — "never that it runs, and never a version comparison" (its own docstring) | Exists in qualification package; **did not exist as a CFG1 L1 check** | **RESOLVED (R3, B10): frozen §16.2 L1 explicitly amended — P (§5) supersedes this helper for CFG1, and does not merely overlap it.** Reason: there must be one canonical Pi resolution/provenance definition; wiring the old helper in alongside P would reintroduce a second, independent AR2-based resolver disagreeing in principle with the canonical one. **Exactly what P subsumes, obligation by obligation:** (1)+(2) — P1 resolves both, and does so **more strongly**: no-follow reparse checks at every lexical component (the old helper has none), lexical **and** realpath'd containment (the old helper checks neither), first-candidate-only, and §7.2 stable filesystem identity capture (B3/B8). (3) — P2 digests `dist/cli.js`'s **exact pinned bytes** (`preflight.py:31`, part of `PINNED_PI_SEAM_DIGESTS`), which is strictly stronger than the old helper's bare `os.path.isfile` existence check: a digest match implies existence, but not the reverse. (4) — `package.json` is **itself** one of the pinned seam files (`preflight.py:30`, and the nested `pi-ai`/`pi-agent-core` package.jsons too), so P2's digest match already implies the `version` field's exact bytes match the pinned value — strictly stronger than a bare field read — **and** P5 additionally runs `--version` and cross-checks the **executing** code's own reported version, which the old helper's own docstring says it explicitly never does ("never that it runs, and never a version comparison"). All four obligations are subsumed at parity or better; none is weakened. | P (§5) — P1 for (1)/(2), P2 for (3)/(4), P5 additionally for the version cross-check the old helper never performed | §11 Tests A, D, E, J, K, S, U, V |
| Environment forbidden-fragment audit | `environment.py::FORBIDDEN_NAME_FRAGMENTS`, checked by `audit_withheld_names`/the child-environment builder — confirmed by grep **never referenced in `run_executor.py`**; it runs at **L12** (Pi-runtime child construction), not L1, despite the frozen L1 text's listing | Yes, but at L12, not L1 | **PRESERVED, and this phase ADDS a second, independent instance** — §6's four-name allowlist for the identity/version-probe child is asserted equal to itself and separately re-audited against the **same** `FORBIDDEN_NAME_FRAGMENTS` constant by name (§6, "Mechanical, not conventional" ¶2); no new constant, no code moved | L12's existing audit (Pi-runtime child, unchanged) **plus** §6's new audit (identity-probe child, new in FU1) | Existing L12 coverage (unchanged, not re-verified here) plus §11 Test F for the new identity-probe child |
| Node/Pi identity/version/provenance | `run_executor.py` → `ports.resolve_runtime_identity()` (= `ar2.launch.resolve_runtime_identity`) — DIAG1 D6's exact root cause: full inherited environment, wrong order relative to the seam proof | Yes (the defect this whole phase corrects) | **SUPERSEDED** end to end by canonical proof P (§5: P1 resolve, P2/P4 seam, P3/P5 probe/version) plus B3's filesystem-identity binding (§7.2) | P (§5), the canonical Pi identity proof | §11 Tests A, D, E, J, K, S |
| Git resolution *(FU1-introduced into the L1 boundary, §4 — B5 confirms it belongs in this table)* | `run_executor.py` → `ports.git_executable()` (= `resolve_git_executable`, `shutil.which`-based, cwd-first on Windows per OC-7), called immediately after the identity/seam checks, still inside L1 | Yes | **PRESERVED, UNCHANGED** — this FU1 phase's own architecture (§4) places the call after P, but does not alter `resolve_git_executable`'s own logic (OC-7, unchanged) | Unchanged: `ports.git_executable()` / `resolve_git_executable` (OC-7) | Existing §11 Test A `git_executable`-failure row; no new proof added |

**Summary (updated R3; corrected R4).** Five of the seven frozen items are
accounted for exactly as shipped (three genuinely at L1 — seam digests,
Node/Pi identity, Git resolution — and two elsewhere in the executor, which is
a pre-existing imprecision in the base design's L1 prose rather than something
FU1 introduces). One item (environment forbidden-fragment audit) gains a
second, independent instance scoped to the new identity-probe child. The two
items R2 left as genuinely missing are both decided (B10):
`preflight_pi_installed_offline` is superseded by canonical proof P,
obligation for obligation, at parity or better (OC-9); the generator
self-check is narrowly removed from frozen L1's text (OC-10, Option B), and —
corrected in R4 (B13) — its replacement is a **new** L9 actual-bytes check,
not an existing one, at a **later** point in the run (AM-11). **No frozen L1
item is left ambiguous or silently dropped.**

---

## 17. Pre-A4 barrier sequence

The eight-item sequence's **numbering and order are unchanged** from R2, per
the reviewer's original ordering; R3 made item 1 precise per B10's explicit
instruction to "update the pre-A4/pre-implementation barrier sequence
accordingly" for OC-9/OC-10. **A4 MUST NOT be drafted or authorized until all
of these are complete:**

1. This FU1 design (**now R6**) accepted/frozen — which includes the OC-9
   amendment (P supersedes `preflight_pi_installed_offline` for CFG1), the
   OC-10 amendment (Option B as rewritten in R4: the live generator self-check
   is narrowly removed from frozen L1 and replaced by the new L9 step 9a
   actual-bytes check plus offline regression, with the pre-L4 → post-L4
   temporal change accepted by name as AM-11, §9.2b/§16), and the AM-9/AM-10
   extension-authority amendments (R4/B12) and the AM-12/AM-13/AM-14 amendments (R5: the close-completing unlink contract, the
   L9 endpoint-material state machine, the pinned extension inputs), as part of the one design being
   accepted/frozen — not a separate, later barrier item, since both are
   textual amendments to this same document, not independent deliverables.
2. OC-3 pinned-0.85.1 `--version` derivation completed and accepted.
3. FU1 implementation independently reviewed/frozen — which, per B10, now
   includes review of the offline regression coverage OC-10's resolution
   assigns to the generator's own test suite (§16, §11 Tests Q, W, Y and Z), since
   that coverage is part of what makes OC-10's removal of a live check safe
   to accept; and (R6) nothing further on the pins: the four static-source pins and the
   template pin are **reviewer-confirmed**, and the golden vector is a frozen
   design literal (§9.2c-D) that the reviewer recomputes independently. OC-11 is **closed inside this design** and R-WINDOW-E is
   **accepted**, so neither remains a pending decision. Nothing here adds a
   numbered item.
4. OC-4 closure-totality correction completed/frozen.
5. OC-5 L3 exact-type/truthiness correction completed/frozen.
6. Operator restores the approved Pi 0.85.1 environment.
7. Read-only pre-A4 identity/seam verification passes.
8. A new A4 authorization is separately reviewed and accepted.

**AR2 live execution remains NO-GO while OC-6 is unresolved** — stated exactly
as the reviewer required, independent of this barrier sequence's own numbered
items, and independent of A4/Stage-2 authorization status.

Nothing in R2, R3, R4, R5 or R6 shortens, reorders, or drops any of these eight items,
and no revision itself satisfies any of them beyond item 1 (which the
reviewer, not this document, ultimately decides).

---

## 18. Final self-review

### 18.0 R6 self-review (current — the six required constructions)

Adversarial re-test of **this R6 design itself** on the L24 positive scrub. In
every construction the object is the file AIDO created and issued —
`models.json` (authority: the config issuance's `models_identity`) or
`ar2_config.ts` (authority: the extension issuance's identity), each a
`(volume_serial, file_id)` pair — and the eight questions are answered in the
same order: exact file object; exact authority; link/alias state; whether
deletion is permitted; the scrub bool; the L24/L27 classification; whether L26
may run; and why no foreign object is deleted. **Section-number note:** the R5
and R4 self-reviews are now §18.0a and §18.0b; references to "R4's §18.0" in
older text read §18.0b.

**1. Verification succeeds → the issued file is renamed → the expected pathname
is absent** (Test Y-2).

- *Object:* the issued file, now named `leak.bin` (same directory or elsewhere on
  the volume); it still exists.
- *Authority:* the issuance identity — but it cannot be exercised, because no
  handle to the object can be obtained through the expected name.
- *Link state:* one link, under a name AIDO does not know.
- *Deletion permitted?* **No** — nothing is opened, no disposition, no pathname
  fallback, no search for the renamed object.
- *Bool:* **`False`**. R5's "absent at open ⇒ `True`" is **withdrawn**.
- *L24 / L27:* `"L24"` ∈ failure steps → `INDETERMINATE_LIFECYCLE`, halt
  `LIFECYCLE_CLOSURE_UNPROVEN`; an independently proven L27 whole-root removal
  may later remove a `leak.bin` inside the root but **never** upgrades the fact.
- *L26:* **skipped** (`LIFECYCLE_UNPROVEN`).
- *No foreign deletion because:* nothing is deleted. If the actor also plants a
  foreign file at the expected name, the open succeeds, the file id **mismatches**
  the issued identity, and the result is `False` with no disposition.

**2. An extra hard link in the same directory** (Test Y-3).

- *Object:* the issued file, reachable as two names in one directory.
- *Authority:* identity matches at open.
- *Link state:* link count **2**.
- *Deletion permitted?* **No** — refused before any disposition, so neither name
  is removed and there is no partial "delete one link" outcome.
- *Bool:* **`False`**. *L24/L27:* as construction 1. *L26:* skipped.
- *No foreign deletion because:* the object is ours but is left entirely intact.

**3. An extra hard link elsewhere on the same volume** (Test Y-4).

- Identical to construction 2 in every field; the alias's directory is
  irrelevant because the proof is the file object's link count, read from the
  exclusive handle, not a directory scan. A link on **another volume** cannot
  exist (hard links do not cross volumes).

**4. Alias creation (or rename) attempted while the exclusive L24 handle is held**
(Test Y-6).

- *Object:* the issued file, opened share-0 by L24.
- *Authority:* the held handle, whose identity matched.
- *Link state:* stays exactly 1 — creating a hard link or renaming the object
  needs an open of it, which share-0 denies (sharing violation); the link count
  read afterwards is still 1, so the proof is **continuous**.
- *Deletion permitted?* Yes, through that handle, only after steps 2 and 3.
- *Bool:* `True` only if the disposition and the close succeed.
- *Contingency:* if the target OS lets either succeed while the handle is held,
  Test Y-6 fails and the implementation **stops and returns to design** — it
  does not improvise a weaker proof.
- *No foreign deletion because:* the only object touched is the one behind the
  identity-matched handle.

**5. Normal one-link deletion** (Test Y-5).

- *Object:* the issued file; *authority:* identity match; *link state:* exactly 1.
- *Deletion permitted?* Yes — one disposition through the held handle.
- *Bool:* **`True`** after a successful close. *L24:* closes; *L27:* independent.
  *L26:* may run **iff** L21 ∧ L23 ∧ L24 all closed.
- *No foreign deletion because:* identity matched by file id; no pathname
  deletion exists.

**6. Both `models.json` and `ar2_config.ts`** (Test Y-9).

- Each file has its own issuance, identity and independent scrub; constructions
  1–5 apply to each. A `False` for one never skips, and a `True` for the other
  never masks it: `generated_config_scrub_verified` and
  `extension_binding_scrub_verified` are separate facts, and either `False`
  puts `"L24"` in the failure steps and skips L26. Neither variant's alias or
  rename can be made to look like a success by the other's outcome.

**Result and residuals, stated not closed.** No construction reaches `True`
except a proven single-link, identity-matched, exclusively held, disposed and
cleanly closed object. Residuals: (a) a same-user actor may have read or
**copied** the bytes at any time before L24 — a copy is a different file, outside
this object-identity claim, and remains part of the same-user/no-confinement
residual; (b) `True` says nothing about a name recreated afterwards; (c) Step 4's
continuity is an OS behavior Test Y-6 must demonstrate, with a stop-and-return
contingency; (d) the R5/R4 residuals stand (re-digest check→use sliver, OC-2,
source-pin drift detected after L4).

**Retractions R6 makes in the retained reviews below.** R5's AM-12 wording
"(a) the object was absent at open" as a `True` case, §9.2a's "absence yields
`True`", §9.2c-C's "absent at open ⇒ `True`" row and Test Y's "absent ⇒ `True`"
control are **withdrawn**; §18.0a's closing "Result" paragraph statements that
the candidate pins are "unconfirmed" and the golden vector "not yet computed"
are **superseded** (pins reviewer-confirmed; vector frozen, §9.2c-D).

### 18.0a R5 self-review (retained — corrected by R6 where §18.0 says)

Adversarial re-test of **this R5 design itself**. For every construction the
same seven questions are answered: who created the resource or fact; the exact
authority object; the exact cleanup obligation; whether deletion is permitted;
the durable scrub value; the lifecycle classification; and why no foreign
same-name object can be deleted. Table references are to §9.2c.

**1. `identity_bound_unlink`: disposition succeeds, close fails** (B15; Test Y).

- *Created by:* the writer — L9's `write_cfg1_pi_config` made `models.json`, the
  L11 extension writer made `ar2_config.ts`, each with a `CREATE_NEW`
  share-mode-0 handle. The **deletion-bearing handle** in question was opened
  by L24's scrub call itself (`GENERIC_READ | DELETE`, share 0, no-follow).
- *Authority object:* the config issuance's `models_identity`, or the extension
  issuance's `ar2_config.ts` identity — a `(volume_serial, file_id)` pair — plus
  that one open handle.
- *Cleanup obligation:* none further. The obligation is **accounting**: a failed
  close leaves the handle and therefore the delete's completion in an unknown
  state, so nothing may claim removal.
- *Deletion permitted?* The one disposition through that identity-matched
  handle already happened and was permitted. **No** retry, second disposition,
  pathname unlink or fallback is.
- *Durable value:* the primitive returns **`False`** (AM-12) and counts
  `"unlink_handle"`; `generated_config_scrub_verified` /
  `extension_binding_scrub_verified` stay **`False`**.
- *Lifecycle:* `"L24"` ∈ `lifecycle_failure_steps` → `INDETERMINATE_LIFECYCLE`,
  halt `LIFECYCLE_CLOSURE_UNPROVEN`, **even if** L27 later removes the whole
  root (G5).
- *No foreign deletion because:* the disposition is issued only through a handle
  whose `os.stat(fd)` matched the issued file id at open; a same-name foreign
  or replaced object mismatches, is never disposed, and yields `False`
  (Test X). No code path deletes by pathname.

**2. L9: endpoint bytes written, then each possible post-write failure,
including a release failure** (OC-11; Test Q; §9.2c-A table).

- *Created by:* `write_cfg1_pi_config` — `models.json` via `CREATE_NEW`,
  share-mode-0, no-follow, in the pinned, parentage-proven config directory.
- *Authority object:* the **creating handle** (`models_child`) — not a path, and
  not an issuance (none exists before step 10, and FU4-FU1 discards it on
  release failure).
- *Cleanup obligation:* on a failure **known before release**, dispose
  `models.json` through `models_child`, **then** close it, and report
  `endpoint_material_outstanding = attempted ∧ ¬(known ∧ disposed ∧ closed)`.
  Cases: (a) the models write raises partway; (b) step-9 read-back fails;
  (c) step 9a mismatch; (d) step-10 refusal; (e) an unanticipated body
  exception; (f) the disposal call returns `False`; (g) the disposal call
  raises; (h) disposition ok, models close fails; (i) disposition ok, models
  close ok, another handle or pin release fails; (j) **success, then a
  release failure first discovered during release** — for (a)–(e) the
  outstanding bool is `False` iff disposition and close both succeeded;
  (f)–(h) and (j) are `True`; (i) is `False`.
- *Deletion permitted?* Only (a)–(e), (i): by handle, disposition before that
  handle's close. In (j) **no** disposal is attempted — the success path
  intends the file to persist and a handle whose close just failed cannot be
  reasoned about (G3) — and nothing is invented: L27 acts separately.
- *Durable value:* `generated_config_scrub_verified` is `False` at the instant
  the call is entered; it becomes `True` only for exact-`False` rows (and for
  pre-write failures, where no endpoint byte was ever attempted); otherwise it
  stays `False`. **L27 never changes it.**
- *Lifecycle:* a `False` fact → `"L24"` ∈ failure steps → `INDETERMINATE_LIFECYCLE` /
  `LIFECYCLE_CLOSURE_UNPROVEN`; a `True` fact closes.
- *No foreign deletion because:* `CREATE_NEW` refuses an occupied name, so the
  object behind `models_child` is provably the one this invocation created;
  disposal is through that handle and therefore cannot reach whatever a name
  resolves to later. R-WINDOW at L9 (a substituted ordinary config directory)
  affects only *where* the object lives, never *which* object the handle is.

**3. Extension writer: token disposition succeeds, token-child close fails**
(B15; Test R; §9.2c-B).

- *Created by:* the L11 extension writer — `ar2_config.ts` via `CREATE_NEW`,
  share-mode-0, no-follow, inside the pinned `pi_extension` directory.
- *Authority object:* the token child's creating descriptor (before E10) or the
  extension issuance identity (after).
- *Cleanup obligation:* dispose through the descriptor, then close it; report
  `token_material_outstanding = attempted ∧ ¬(disposed ∧ closed)`.
- *Deletion permitted?* By own handle only, before that handle's close. Here it
  happened; the failed close is an outstanding/unproven outcome, not a reason
  for a second attempt.
- *Durable value:* `token_material_outstanding == true` →
  `extension_binding_scrub_verified` stays **`False`** (R4's E11 could be read as
  "disposition succeeded, therefore clean"; **R5 withdraws that reading**).
- *Lifecycle:* `"L24"` ∈ failure steps → `INDETERMINATE_LIFECYCLE` /
  `LIFECYCLE_CLOSURE_UNPROVEN`, `EXTENSION_GENERATION_FAILED` at L11.
- *No foreign deletion because:* as construction 2 — only the handle this
  invocation created; no pathname deletion anywhere; the directory is never
  removed by the writer.
- *E11 wording, fixed:* a release failure **first discovered during** E11's
  close cannot retroactively dispose before that same close; it is
  outstanding/unproven (G3, §9.2a E11a/E11b).

**4. Extension source `tools.ts` / `index.ts` modified after admission, before
L11** (B16; Test Z-1).

- *Created by:* nothing — E-1 runs before E0; no directory, child or byte
  exists.
- *Authority object:* the CFG1-owned pin literal (size + SHA-256); the bytes
  read once are compared to it.
- *Cleanup obligation:* none.
- *Deletion permitted?* Nothing exists to delete.
- *Durable value:* `token_material_outstanding == false` →
  `extension_binding_scrub_verified` `True` (write-ahead `False` then set from
  the exact-`False` typed error).
- *Lifecycle:* closes; `refused_at_step = "L11"`, `EXTENSION_GENERATION_FAILED`.
  **Temporal cost named:** refused after the L4 credential read (§9.2a
  residual 5).
- *No foreign deletion because:* no object is created, and the source pathname
  is only ever **read**.

**5. Extension source modified after its verified read but before E8**
(B16; Test Z-2).

- *Created by:* E-1 produced an immutable `bytes` buffer of the **verified**
  bytes; E6–E8 create and write the children from it.
- *Authority object:* the buffer (P2) and the pin literal (P0).
- *Cleanup obligation:* the ordinary E11 rules for children this invocation
  creates.
- *Deletion permitted?* Same as construction 3.
- *Durable value / lifecycle:* unchanged from a normal run — the written bytes
  equal the pin, issuance digests equal the pin (E10), the run proceeds.
- *Why the swap is harmless:* the modified source is never read again (Test Z-2
  counts exactly one open per source), so **no content-level source-read → use
  sliver remains**. A same-user actor can still alter the *written child*; that
  is what E9 and `verify_extension_issuance`'s re-digest, with the R4
  check→use sliver, address.
- *No foreign deletion because:* unchanged — handle-bound only.

**6. Template: the runtime `_GENERATED_CONFIG_HEADER` differs from the pinned
expectation** (B16; Test Z-3).

- *Created by:* nothing — the template is verified in E-1, before E0.
- *Authority object:* the CFG1-owned template digest and structure rule
  (exactly one `%s`, no other `%`), plus the golden vector for the derived
  file; **not** a comparison against the frozen writer, which would consume
  the same mutable template.
- *Cleanup obligation / deletion:* none.
- *Durable value:* `token_material_outstanding == false` →
  `extension_binding_scrub_verified` `True`; `EXTENSION_TEMPLATE_UNPINNED` is
  writer-local and reduces to `EXTENSION_GENERATION_FAILED` at L11.
- *Lifecycle:* closes.
- *Why the immutable local matters:* once verified, the single `str` object is
  what E8 formats; the module attribute is never re-read, so a later attribute
  reassignment cannot change the output.
- *No foreign deletion because:* nothing is created.

**Result.** No construction yields a `True` scrub fact without a handle-bound
proof that includes a successful close, none deletes anything by pathname or
on a name match, and none lets an L27 whole-root success upgrade an individual
fact. **Residuals, stated not closed:** the candidate pins are unconfirmed
until the reviewer (and the implementation, from git blobs) confirm them; the
golden vector is not yet computed; source-pin drift is detected after L4;
`identity_bound_unlink`'s `True` is a handle-protocol result, not a claim about
the name afterwards; the R4 re-digest check→use sliver and OC-2 (Pi's unpinned
transitive imports) are unchanged.

**Retractions R5 makes in the retained reviews below.** §18.0b construction 2's
`token_material_outstanding == false` "after a verified disposal" now also
requires a successful close of the deletion-bearing handle; §18.0b's E11
description is superseded by §9.2a E11a/E11b; R4's statement that OC-11 was
"recorded, not corrected" is superseded by its closure (§9.2c, AM-13); and R4's
description of the extension inputs as "frozen static material, read not
edited" is superseded by the pinned single read (AM-14).

### 18.0b R4 self-review (retained — corrected by R5/R6 where §18.0 / §18.0a say)

Adversarial re-test of **this R4 design itself** against the five
constructions the reviewer required for this round. Each names the counterexample
and the exact authority or invariant that rejects it. §18.1 (R3) and §18.2 (R2)
follow, retained, with R4's corrections marked where they apply.

1. **Same package-root object; `dist/cli.js` changed after P2.**
   *Counterexample:* P1 captures the root's and `node.exe`'s §7.2 identities;
   P2 digests all 20 pinned seams and passes; a same-user process then (a)
   rewrites `dist/cli.js` in place (same file id) or (b) deletes it and writes a
   new `dist/cli.js` into the same, unchanged `dist\` directory. The root
   directory object and `node.exe` are untouched, so any identity-only check
   passes — R3's P2R would have let P3 execute the changed file.
   *Rejected by:* R4's P2R step (a) (§5, AM-1) — the **complete** seam set is
   re-walked and re-digested as part of the final operation before
   `CreateProcess`; `dist/cli.js` is one of the pinned keys, so its digest
   mismatches in both (a) and (b) → `PI_IDENTITY_DRIFTED_BEFORE_PROBE`, tuple
   `(false, false, NO)` ∈ `Allowed(F)`; probe-runner call count 0. P4 is never
   reached and is not credited. Residual: a change landing after P2R (a) read
   that file and before `CreateProcess` (§7.1). §11 Test V.

2. **Same-pathname extension child replaced by a foreign object before the
   failure-path scrub.**
   *Counterexample:* L11's writer has written the token into its
   `ar2_config.ts` child; E9 then fails; meanwhile a same-user process tries to
   substitute a foreign `pi_extension\ar2_config.ts`, hoping AIDO's cleanup will
   delete it (or will "verify removal" by checking the name).
   *Rejected by:* the transactional writer (§9.2a, AM-9). The child was created
   `CREATE_NEW` with `dwShareMode = 0`, so while the writer holds it no other
   actor can delete, rename or write it — the substitution cannot happen while
   AIDO still holds authority; once the writer disposes the child **through its
   own creating handle** and closes it, a foreign object may appear at the name,
   but no CFG1 code will ever touch it: there is **no pathname deletion** on any
   L11 path, and the frozen pathname scrubber is no longer called. The durable
   fact comes only from the handle disposal (`token_material_outstanding ==
   false` → `extension_binding_scrub_verified = true`); the foreign file is left
   for L27, which removes it only under independently re-proven whole-root
   authority — the §17 rule that L27's namespace teardown may truthfully reach
   descendants CFG1 did not create, while an individual deletion may not. If
   the handle disposal itself fails, `token_material_outstanding == true` and
   the record is `INDETERMINATE_LIFECYCLE` with `"L24"` failed — obligations
   increased, never erased. §11 Test R.

3. **Successful L11, then a same-name replacement before the normal L24.**
   *Counterexample:* L11 returns an extension issuance; before L24, a same-user
   process deletes `ar2_config.ts` and creates a new file of the same name
   (possibly byte-identical, possibly a reparse point), or swaps the whole
   `pi_extension` directory for another ordinary directory with a same-name
   file.
   *Rejected by:* L24's `verify_extension_issuance` (directory identity by file
   id, children re-digested) and `win.identity_bound_unlink` against the
   **issued** `ar2_config.ts` identity: the replacement has a different file id
   (a directory swap also fails the directory-identity check first), so nothing
   is deleted and `extension_binding_scrub_verified = false` →
   `INDETERMINATE_LIFECYCLE`. The issuance is consumed regardless. §11 Test X.

4. **Actual `models.json` bytes differ from the pinned arm shape while the
   expected in-memory digest is still correct.**
   *Counterexample:* the write path (serializer, text wrapper, or an injected
   defect) produces `models.json` bytes with an extra space, a reordered key, a
   bare `\n`, or the endpoint written twice — while
   `redacted_models_digest(arm_id)` (computed from the in-memory expected
   document) still equals `ARM_REDACTED_DIGEST[arm]`, and `records.py` would
   still write that constant.
   *Rejected by:* L9 step 9a (§9.2b, AM-11): the **actual** bytes, read through
   the proven share-mode-0 descriptor, are line-ending-canonicalized under the
   one declared translation (a bare `\n` refuses outright), the endpoint slot is
   redacted only if it occurs exactly once after `"baseUrl": ` (twice refuses),
   and the SHA-256 of the result is compared with the **pinned literal** — so
   the extra space or reordered key changes the digest and refuses. Both
   children are disposed by handle, step 10 never registers an issuance, and
   the executor records `CONFIG_GENERATION_FAILED` at L9. The in-memory
   expected digest plays no part. §11 Test W.

5. **Unexpected exception inside P at each boundary — the validator uses only
   durable fields.**
   *Counterexample set:* an unanticipated raise (i) before P2 completes;
   (ii) after P2, before P2R completes; (iii) after P2R, before P3's entry;
   (iv) after P3's entry (during the probe); (v) inside P4; (vi) inside P5;
   (vii) during P6 construction or result-shape validation; (viii) after P's
   success commit, during Git resolution.
   *Rejected-from-misrepresentation by:* P's atomic family commit (§5 P6) plus
   the category-B write-ahead of `A`. In (i)–(iii) nothing of P's family is
   committed and `A` was never written → `τ = (false, false, NO)`; in
   (iv)–(vii) `A` was written ahead at P3's entry and nothing else committed →
   `(true, false, NO)`; in (viii) P's success family was committed → `σ`. In all
   eight, `refused_at_step = "L1"`, `pre_dispatch_refusal_code =
   UNEXPECTED_STEP_FAILURE`, `pi_identity_failure_code = null`. The validator
   applies **R-P4 only**: `F == null ∧ τ ∈ U` — a pure function of `K`, `C`,
   `F`, `A`, `S`, `V`. It never asks which of (i)–(viii) happened, and cannot be
   made to: a record claiming `(true, true, NO)` under
   `UNEXPECTED_STEP_FAILURE`, or any non-null `F` with it, fails R-P4/R-P2.
   §11 Tests G and O.

**Retractions R4 makes in the retained reviews below.** §18.1 scenario 2's
"five typed codes" is **six**; §18.1 scenarios 6 and 7 remain correct, but the
P2R they cite is now the final proof over seams **and** identities; §18.1
scenario 9's claim that the frozen pathname scrubber is "genuine cleanup
*authority*" is **withdrawn** (B12 — superseded by construction 2 above);
§18.1 scenario 11's claim that L9 already digest-pins actual output is
**withdrawn** (B13 — superseded by construction 4 above).

### 18.1 R3 self-review (retained — corrected by R4 where §18.0 says)

Adversarial re-test of the **R3 design** — not the shipped code — against
the eleven scenarios the reviewer required for R3's round, each with
a constructed counterexample and the exact invariant/authority object that
makes it fail closed. §18.2 retains R2's own review below, superseded where a
finding here corrects it and otherwise still valid.

1. **Clean success with all three failure fields absent.**
   *Counterexample:* every step L1–L20 completes with no refusal and no
   unexpected exception — the single most common run.
   *Rejected-from-being-unrepresentable by:* §9.2's **NO_DISPATCH_FAILURE**
   mode (B6) — `refused_at_step`, `pre_dispatch_refusal_code` and
   `unexpected_failure_step` all absent, and the v2 validator accepts this
   triple. R2's flawed iff chain would have rejected exactly this record;
   §9.4's corrected "the only direct iff is `pre_dispatch_refusal_code`
   present ⇔ `refused_at_step` present" admits it. §11 Test T.

2. **Unexpected L1 exception before P3.**
   *Counterexample:* an unanticipated `TypeError` inside P1's own lexical
   walk (not one of P's six anticipated stage failures) — e.g. a leaf
   double misbehaves in a way no anticipated code path checks for.
   *Rejected-from-misrepresentation by:* the raise is not caught by any of
   P's typed per-stage refusal handling (§5's "unexpected exception inside
   P" row), so it propagates to L1's outer catch-all: `refused_at_step =
   "L1"`, `pre_dispatch_refusal_code = "UNEXPECTED_STEP_FAILURE"`,
   **`pi_identity_failure_code = null`** (never one of the **six** typed
   codes — R4 correction; validated by §5.1's pure-durable rule R-P4,
   tuple `(false, false, NO)`). §11 Test G's "inside P"
   injection point.

3. **Expected `PI_RESOLUTION_FAILED`.**
   *Counterexample:* `node.exe` does not exist under any `PATH` entry.
   *Rejected/represented by:* §5.1's "Resolution failure" row —
   `pi_version_probe_attempted = false`, `pi_seam_digests_match = false`
   (fail-closed, unmeasured), `pi_observed_version = NOT_OBSERVED`,
   **`pi_identity_failure_code = "PI_RESOLUTION_FAILED"`**,
   `pre_dispatch_refusal_code = "OFFLINE_PREFLIGHT_FAILED"`. §11 Test A/D.

4. **Expected `PI_SEAM_UNPROVEN`.**
   *Counterexample:* `node.exe`/`pi.cmd` both resolve cleanly, but one pinned
   seam file's bytes do not match `PINNED_PI_SEAM_DIGESTS`.
   *Rejected/represented by:* §5.1's "Initial seam failure" row — the
   **identical** `pi_version_probe_attempted`/`pi_seam_digests_match`/
   `pi_observed_version` triple as scenario 3 (`false`/`false`/`NOT_OBSERVED`)
   — which is exactly B7's second finding: those three facts alone cannot
   distinguish scenarios 3 and 4. What distinguishes them is
   **`pi_identity_failure_code = "PI_SEAM_UNPROVEN"`**, the field this
   revision added for precisely this reason. §11 Test A/D.

5. **P3 attempted, P4 fails.**
   *Counterexample:* seam files match at P1's resolved root and P2R's
   identity re-check also passes; the probe launches and would print
   `0.85.1`; but between P3 starting and P4 running, a background process
   rewrites one pinned seam file back to a different byte sequence.
   *Rejected/represented by:* P4 re-runs P2's digest comparison via §7.2 and
   finds a mismatch → `PI_SEAM_CHANGED_DURING_PROBE`. The record carries
   `pi_version_probe_attempted == true` (P3 was entered — P2R already
   confirmed identity, so this is a **post**-execution detection, correctly)
   **and** `pi_observed_version == NOT_OBSERVED` (P5 never ran)
   simultaneously — the exact combination B1 required this design to be able
   to state truthfully. §11 Test K.

6. **`node.exe` replaced between P2 and P3.**
   *Counterexample:* P1 resolves and captures the §7.2 identity of
   `C:\Tools\node\node.exe`; P2 passes (it never touches Node at all); before
   P3's `CreateProcess`, that exact path is deleted and a different
   `node.exe` is written in its place.
   *Rejected by:* P2R (§5, B8) — **strictly before** `CreateProcess` — re-checks
   §7.2 identity for `node.exe` against what P1 captured; a delete-and-recreate
   yields a new file id even with identical bytes, so the comparison fails →
   `PI_IDENTITY_DRIFTED_BEFORE_PROBE`, `pi_version_probe_attempted` **stays
   `false`** (P3 is never entered — this is a pre-execution refusal, not a
   post-execution detection, which is exactly what B8 required and R2 did not
   have). §11 Test U.

7. **Pi root replaced between P2 and P3, with matching pinned seams but
   altered unpinned JS.**
   *Counterexample:* the package root is deleted and replaced by a different
   directory object, deliberately constructed so all 20 `PINNED_PI_SEAM_DIGESTS`
   files are byte-identical to the originals (P2 would pass a re-check), but
   the *unpinned* transitive JS the probe would actually load differs.
   *Rejected by:* P2R re-checks §7.2 **identity** (volume serial + file id),
   not digests, for the package root — a different directory object fails
   this check regardless of whether its 20 pinned files pass a digest
   comparison, because identity and digest-match are independent facts
   (§5's P2 row explicitly states this is exactly why P2R exists). Refused
   `PI_IDENTITY_DRIFTED_BEFORE_PROBE` before P3 ever loads anything from the
   replacement root — **B8's explicit requirement that post-P3 detection
   (P4) must not be claimed to close a pre-P3 execution boundary** is honored
   because P2R runs, and refuses, before P3 is ever entered. §11 Test U.

8. **Genuine `write_cfg1_pi_config` raises on every supported pre-return
   boundary.**
   *Counterexample, exhaustively across its own documented exit points
   (`cfg1_pi_config.py` Sec. 37.3.1 steps 0–11):* a failure injected at
   step 0 (provenance interval), steps 1–2 (root pin), step 3 (`mkdir`),
   steps 4–5 (config pin/parentage), step 6 (exclusive children), step 7
   (the gate), steps 8–9 (content/finalization), step 10 (issuance
   registration itself failing inside `register_config_issuance`, before its
   own `_ISSUED[token] = ...` write), and step 11 (each of the three release
   failures, **after** step 10 has genuinely succeeded).
   *Rejected-from-leaving-an-orphan by:* for every failure **before** step
   10's registry write completes, `_ISSUED` gains no entry — nothing to
   discard. For step 11's release failures **after** a genuine registration,
   the `finally` block (`cfg1_pi_config.py:429-454`, `CFG1-IMPL-FU4-FU1`)
   calls `config_issuance.discard_config_issuance(token)` **before** raising
   its own closed code — every supported path retires a genuine issuance
   before the function's raise reaches its caller. `state.generated_config`
   is unset on every one of these paths, confirming it as the sufficient
   caller-side signal (B9). §11 Test Q.

9. **Extension writes token-bearing `ar2_config.ts` then raises before
   return.**
   *Counterexample:* `write_disposable_extension`'s `mkdir` succeeds, the
   static source copies succeed, `(extension_dir / "ar2_config.ts").write_text(...)`
   succeeds — and then, hypothetically, `GeneratedExtension(...)`'s
   construction raises (or any other step after the token-bearing write but
   before `return`).
   **[WITHDRAWN IN R4 — B12.]** R3 answered this with a wrapper that, on
   failure, called the frozen `scrub_generated_extension_config` on a
   precomputed pathname and recorded its bool in a new field, and described
   that as cleanup authority. R4 withdraws the description and the field: the
   frozen scrubber deletes whatever answers at the name, with no issuance,
   identity, or handle, so it is not authority over the object AIDO wrote.
   R3 also treated L9-grade transactional discipline as reachable only by
   editing the frozen AR2 writer; R4 instead reaches it with a CFG1-owned
   writer (AM-9/AM-10) that leaves the frozen module untouched. The current
   answer to this scenario is §18.0 construction 2 and §9.2a. §11 Test R.

10. **OC-9 canonical-P supersession.**
    *Counterexample:* does superseding `preflight_pi_installed_offline`
    silently drop any of its four obligations?
    *Rejected-from-silent-drop-by:* §16's OC-9 row states all four
    obligations explicitly and shows each is subsumed at parity or better —
    (1)/(2) resolution, stronger (no-follow, dual containment, first-candidate,
    §7.2 identity); (3) `dist/cli.js` existence, stronger (byte-digest, not
    mere existence); (4) `package.json` version field, stronger (digest match
    implies field match, **plus** P5's runtime cross-check the old helper's
    own docstring says it never performs). No obligation is weakened; none is
    silently left uncovered.

11. **Chosen OC-10 resolution.**
    *Counterexample:* does narrowly removing the live generator self-check
    leave CFG1 with a weaker guarantee than before?
    **[CORRECTED IN R4 — B13. L9 did not already compare actual bytes with
    the pin; §9.2b adds that comparison as step 9a, and AM-11 names the
    pre-L4 → post-L4 temporal change. See §18.0 construction 4.]**
    *Still true from R3:* the self-check it replaces validated a *different*
    generator (the qualification package's own), against a fixed `.invalid`
    placeholder — never CFG1's real generator against a real arm; and the
    residual concern (generator logic misbehaving on untested inputs) stays
    covered offline. *Withdrawn:* R3's statement that an existing L9 digest
    pin already proved real output — `redacted_models_digest` hashes an
    in-memory expected document, not the written bytes.

No item on the reviewer's list of eleven was merely asserted as covered; each
maps to a specific mechanism (§5.1/§9.4's corrected case table and modes,
§5's new P2R stage, §9.2a's corrected L9/L11 analysis, or §16's reconciliation)
and a specific §11 regression-test row.

### 18.2 R2 self-review (retained; corrected where R3 requires it)

The eight scenarios R2's own self-review covered. Scenarios 1 (P2/P3/P4),
mapped above into scenario 5; a `node.exe`/Pi-root-replacement scenario,
refined above into scenarios 6/7 (the *pre-P3* window, B8's addition — R2's
original review only covered the *pre-L14* window, reproduced unchanged
below as items 4/5); and the L9/L11 partial-creation scenario, corrected
above into scenario 8/9 (B9). The three items below are unchanged from R2 and
still hold as stated:

1. **Post-dispatch L20 unexpected exception.**
   *Counterexample:* the run reaches L20 (Φ4 projection); `sanitized_events`
   contains an object whose `.stop_reason` attribute access raises an
   unanticipated `AttributeError` inside the projection logic.
   *Rejected by:* §9.2's **POST_DISPATCH_UNEXPECTED** mode fires:
   `unexpected_failure_step = "L20"`, **no** `refused_at_step`, **no**
   `pre_dispatch_refusal_code`. §9.4's corrected invariant makes a record
   that instead wrote `refused_at_step = "L20"` fail its own v2 validation
   (`RECORD_INVARIANT`), because `"L20"` is not in the step/code table's
   admissible-refusal domain. §11 Test G/Test T.

2. **Repo-local junction resolving outside the repo.**
   *Counterexample:* an attacker (or a careless prior run) places a junction
   at `<checkout>\evil_node_dir` pointing to a real, legitimate, out-of-tree
   Node installation; that junction's realpath'd destination is genuinely
   outside the checkout and would, under a realpath-only containment check,
   pass.
   *Rejected by:* §7.2's step-1 no-follow classification observes
   `<checkout>\evil_node_dir` itself as `reparse_point` and refuses it **as
   that candidate**, before realpath is ever invoked. §11 Test J.

3. **`node.exe`/Pi-root replaced between L1 and L14 (the pre-*second*-execution
   window — distinct from scenarios 6/7's pre-*first*-execution window).**
   *Counterexample:* both pass P1–P5 genuinely; between L1's completion and
   L14's spawn, `node.exe` (or the package root) is deleted and replaced,
   same path, new on-disk record.
   *Rejected by:* AM-8/D-4's L14 pre-spawn re-proof re-captures §7.2 identity
   and compares it to what P1 captured; a delete-and-recreate yields a new
   file id even with identical bytes → `RUNTIME_LAUNCH_FAILED` at L14, no
   spawn. §11 Test S — kept distinct from Test U (scenarios 6/7's pre-P3
   window) because they protect two different executions.

4. **Malformed resource-return types.**
   *Counterexample:* the workspace-mint port returns a 2-tuple whose first
   element is a plain `dict` with the right-looking keys rather than a
   genuine `Cfg1RunWorkspace` instance from the `run_workspace` registry.
   *Rejected by:* §8's rule that `AUTHORITY_RETURNED` requires "exactly a
   2-tuple whose first member is exactly a `Cfg1RunWorkspace` owned by the
   `run_workspace` registry" — a foreign type never advances W past
   `ATTEMPTED_NO_AUTHORITY`, and the independent `minted_workspace_count() !=
   0` halt is a second witness. §11 Test B.

---

## Status

```text
5F3B-HARNESS-CFG1-L1-BOUNDARY-FU1-DESIGN-R6   CANDIDATE — PENDING REVIEW
D-1 / D-3 / D-4 ACCEPTED.  D-2 CLOSED (pi_identity_failure_code).
B1–B5 corrected in R2; B6–B10 in R3; B11–B14 in R4; B15/B16 + OC-11 in R5;
B17/B18 in R6.
B11, B13, B14, B15 CLOSED; OC-11 CLOSED at the L9 writer boundary; B12
architecture accepted; AM-11 accepted; R-WINDOW-E ACCEPTED (§9.2a conditions).
Static-source pins (4) and the template pin: INDEPENDENTLY REVIEWER-CONFIRMED.
B17: L24 positive scrub = ONE exclusive share-0 handle interval proving identity
     + exactly one hard link, then disposition and a successful close (AM-12);
     ANY open failure, including absence, is False; no pathname-based positive
     scrub remains; L27 never upgrades a False fact; L26 skipped on False.
B18: ar2_config.ts golden vector FROZEN as a design literal (§9.2c-D).
§13 amendment pointer: AM-1..AM-14.
OC-9: P supersedes preflight_pi_installed_offline (decided).
OC-10: Option B (decided; AM-11).
BLOCKED ON FINAL REVIEWER ACCEPTANCE OF R6.
Implementation additionally blocked on OC-3 and the full pre-A4 barrier
sequence (§17).
CFG1-S1-A3: CONSUMED / historical-only.  A4: not authorized.  Stage 2: not authorized.
```
