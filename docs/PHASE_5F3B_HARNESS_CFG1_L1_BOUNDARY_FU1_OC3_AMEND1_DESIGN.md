# Phase 5F3B-HARNESS-CFG1-L1-BOUNDARY-FU1-OC3-AMEND1 — Removal of the Live `--version` Probe (Design Amendment)

```text
5F3B-HARNESS-CFG1-L1-BOUNDARY-FU1-OC3-AMEND1-DESIGN   CANDIDATE — PENDING REVIEW
AMENDS (does not edit) the ACCEPTED / FROZEN base design:
  5F3B-HARNESS-CFG1-L1-BOUNDARY-FU1-DESIGN-R6
  docs/PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md
  SHA-256  f9287e8929fb0093f8e99a67b8a665387a249bf27ad5c414a465c0c067058bd0
  git blob c5d2f86ecbe6281afec5737b5d3592d4fd49d6ff
  (identity re-verified by this turn: sha256sum + git hash-object; 2458 LF, 0 CR)
REPOSITORY ADMISSION OBSERVED: HEAD 306493ac4ddd8a9a2ce180c5f4fa21bba5fe5715
OC-3 ARCHAEOLOGY: ACCEPTED — primary verdict OC2_PREVENTS_OC3_PROOF
REVIEWER DECISION FROZEN HERE: REMOVE THE LIVE --version PROBE
EFFECTIVE DESIGN = R6 + THIS AMENDMENT (AMD-1 … AMD-8)
GRANTS NOTHING. NO IMPLEMENTATION AUTHORITY.
```

> **THIS DOCUMENT IS A DESIGN CANDIDATE. IT GRANTS NOTHING.**
>
> - It does not edit, re-serialize, or re-hash-into-a-new-meaning the frozen R6
>   file. R6 stays the exact accepted base; this file is read **together with**
>   it.
> - It authorizes no implementation, no test change, no live run, no A4, no
>   Stage 2, and reserves no identifier. `CFG1-S1-A3` remains CONSUMED and
>   historical-only.
> - Pi remains pinned to **0.85.1** through the unchanged 20-entry
>   `PINNED_PI_SEAM_DIGESTS`. Nothing here adds, removes, or repins a seam.
>
> **Disclosure of what the turn that wrote this file did (exact).** It read the
> frozen R6 file, the frozen CFG1 design, the AR0 / AR0-FU1 design text, and
> source text under `experiments/pi_harness_cfg1/`,
> `experiments/pi_external_runtime_ar2/ar2/` (`launch.py`, `supervisor.py`),
> `experiments/pi_external_runtime_ar1/ar1/launch.py`, and
> `src/ai_dev_orchestrator/workspace/git_adapter.py`, with `sed`/`grep`/`Read`
> only. It hashed the frozen R6 file with `sha256sum` and `git hash-object`. It
> imported no Python module of this repository, executed no Node, Pi, or
> JavaScript, started no process other than the shell text tools named above
> and `git`, opened no socket, read no credential or endpoint value, installed
> or removed nothing, read nothing outside `C:\dev\ai_dev_orchestrator`, and
> wrote no file other than this one.

**Citation convention.** `R6 §n` = the frozen FU1 R6 design; `R6 line n` = a
line of that frozen blob (stable, because the blob is frozen); `CFG1 §n` = the
frozen CFG1 design
[`PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md);
a bare `§n` = a section of this amendment. **Label collision warning:** R6
§9.2c-D uses the labels `P0…P6` for the **extension source provenance chain**
(R6 lines 1370–1378). That chain is **not** the canonical Pi identity proof P
and is **entirely preserved**; every `P0/P1/P2/P2R` in this amendment means the
canonical Pi identity proof of R6 §5.

---

## 0. Reading rule and precedence

1. The effective FU1 design is **R6 + this amendment**. Where this amendment
   names an R6 clause as superseded (§3), this amendment governs; every R6
   clause not named in §3 is preserved exactly as frozen (§4).
2. Where this amendment amends a **frozen CFG1** clause (CFG1 §16.2 L1's
   `--version` item; CFG1 §22.2's identity field set **for v2 only**), it says
   so in §3 by clause, in the same style as R6 §3's AM-1…AM-14.
3. R6's historical self-review sections (R6 §18.0 … §18.2) and changelogs are
   design history. Statements there that describe P3/P4/P5, the probe child, or
   `pi_version_probe_attempted` are **superseded as normative text** and remain
   only as the record of why earlier revisions were shaped as they were.
4. Nothing here reopens a decision R6 recorded as accepted/closed (D-1, D-2's
   field, D-3, D-4, B1–B18, AM-9…AM-14, OC-9, OC-10/AM-11, OC-11, R-WINDOW-E),
   except where §3 names the specific probe-dependent text of that decision.
5. If any clause below were found to contradict another accepted frozen
   contract, the amendment would stop; §17 records that the contradiction
   search was performed and found none.

---

## 1. The accepted OC-3 finding

R6 §5.1 (R6 lines 464–472) and R6 §14 OC-3 (R6 line 1749) required, before
implementation, a derivation from the pinned 0.85.1 bytes of whether
`node dist/cli.js --version` reads Pi settings/auth, reads project-local state,
writes, or attempts network access before printing — and R6 D-6 (R6 line 1747)
required the implementation to stop and return to design if it did.

The OC-3 archaeology is **ACCEPTED** with primary verdict
**`OC2_PREVENTS_OC3_PROOF`**. Its authoritative decisive finding:

- the exact locally cached Pi 0.85.1 candidate was bound to the frozen seam
  **20/20**;
- the frozen, pinned `dist/cli.js` **statically imports** `./cli/setup.js`;
- `dist/cli/setup.js` is **outside** `PINNED_PI_SEAM_DIGESTS`;
- therefore **unpinned Pi-controlled JavaScript necessarily evaluates before
  the `cli.js` body, and before any `--version` handling can protect the
  boundary.**

Supporting candidate-source analysis found further pre-version modules and
possible side effects; those contents are **unpinned** and are therefore **risk
evidence only, never frozen authority** — this amendment cites none of them as
a fact about what Pi does.

**Consequence.** R6 §5's P3 asked the pinned seam proof to make a
pre-consumption execution safe. The finding shows the seam proof cannot bound
what that execution runs: ES-module static imports are linked and evaluated
before the importing module's body, so the probe's first evaluated code is
code no AIDO check has bound. The `--version` side-effect derivation R6
required is **not completable from pinned bytes at all**, because the code that
runs first is not among them. That is OC-2 (R6 line 1748) preventing an OC-3
proof — hence the verdict.

---

## 2. Reviewer decision frozen here, and what it rules out

**Decision.** All Node/Pi/JavaScript execution is **removed** from the
pre-consumption identity gate and from L1. The **first** Pi-controlled
JavaScript execution — and the first execution of the resolved `node.exe` — in
a CFG1 live run is **L14**, immediately after L14's full re-proof.

**Ruled out, explicitly (none of these may be introduced to preserve a
probe):** expanding the seam set to the full pre-version import closure;
pinning hundreds of Pi or third-party modules; authorizing native-addon
execution; a disposable user profile; sandboxing the version probe; adding
environment variables until `--version` works; executing Pi earlier through any
alternative entry point (a different script, `--help`, a `require` of a
sub-module, a Node REPL, a `pi.cmd` shim, or a Node `--check` of the package).

---

## 3. Clauses superseded (exact)

### 3.1 Amendment clauses

| Id | Supersedes | Narrow amendment |
|---|---|---|
| **AMD-1** *(P is static)* | R6 §3 **AM-1** (R6 line 228: "… → secret-free version probe → post-probe re-proof → version → Git resolution"); R6 §4 diagram L1 row (R6 lines 258–260); R6 §5 intro sentence "ports … supply only leaf effects: a filesystem view … and the one probe process runner" (R6 lines 293–296); R6 §5 table rows **P0** (the `SystemRoot` read), **P3**, **P4**, **P5**, **P6**; R6 §5 "Who creates each fact" (R6 lines 320–334). **Frozen CFG1 §16.2 L1** item "Node/Pi identity probe (`--version`, provenance)": the `--version` part is **removed, not relocated**; provenance is kept, statically. | L1's normative internal order becomes **P0 inputs → P1 resolve + capture → P2 complete seam proof → P2R final identity-consistency re-proof → P-result (atomic family commit) → Git resolution** (§5). No stage executes anything; P has **no** process-creation leaf. A failure at any stage executes nothing later in the list. |
| **AMD-2** *(P2R redefined)* | R6 §5 row **P2R** (R6 line 314) — the R4/B11 "final pre-`CreateProcess` proof" definition, including its complete seam re-walk and its failure code name. | P2R is the **final identity-consistency re-proof** of P: the package-root and `node.exe` §7.2 identities re-checked against P1's captures, **after** P2's complete walk. It performs no second seam walk, because no execution follows it; B11's "complete seam set before first execution" obligation moves, whole, to L14 (AMD-6). Reasoning in §5.2. |
| **AMD-3** *(probe environment retired)* | R6 §6 in its entirety (R6 lines 476–524); R6 §3 **AM-2** (R6 line 229); R6 §16 row "Environment forbidden-fragment audit", its "second, independent instance" (R6 line 1787). | There is **no** identity/version child and therefore **no** identity/version child environment. AM-2 is **withdrawn**: frozen CFG1 §16.1 principle 5 stands exactly as frozen, with no identity-probe child added to it. The L12 runtime child environment is **untouched** (§11). |
| **AMD-4** *(v2 identity fields)* | R6 §3 **AM-4**'s `pi_observed_version` domain item (R6 line 231); R6 §10 rows `pi_observed_version` domain (R6 line 1544), `pi_version_probe_attempted` (R6 line 1545), `pi_identity_failure_code` (R6 line 1547), `PRE_DISPATCH_REFUSAL_CODES`' "six" (R6 line 1552), filesystem identities "between P1/P2R/P4" (R6 line 1554). **Frozen CFG1 §22.2** identity group's `pi_observed_version`, **for v2 only**. | `pi_observed_version` is **absent** from v2 (v1 keeps it, unchanged). `pi_version_probe_attempted` is **absent** from v2 (it was never emitted). `pi_identity_failure_code` has a **three**-code domain. No replacement version field is added (§7). |
| **AMD-5** *(v2 validator)* | R6 §5.1 in its entirety except the boolean-algebra-discipline paragraph (R6 lines 336–449, 457–472); R6 §9.4 paragraph "Plus, for B1/B7/B14" (R6 lines 1493–1507); R6 §10 "new invariants" row's reference to R-P1…R-P6 (R6 line 1553). | Replaced by rules **R-S1…R-S6** (§8), each a pure function of the durable fields `refused_at_step`, `pre_dispatch_refusal_code`, `pi_identity_failure_code`, `pi_seam_digests_match` — none refers to an execution or probe event. |
| **AMD-6** *(first execution at L14)* | R6 §3 **AM-8** (R6 line 235) wording "the pair P3 proved"; R6 §4 diagram L14 row (R6 line 272); R6 §5 P6's identity-object shape "`ar2.launch.RuntimeIdentity`'s shape … `reported_version`" (R6 line 318); R6 §7.1 TOCTOU rows 3–5 and closing paragraph (R6 lines 575–587); R6 §12.1 rows "version and seam facts from different roots", "pair L14 launches", "individually valid Node and Pi objects" (R6 lines 1616, 1617, 1620). | AM-8's re-proof is **preserved and becomes the sole pre-first-execution proof**, in a fixed order (complete seam set → package-root identity → `node.exe` identity) with nothing that reads the Pi tree, resolves a name, or executes anything between it and `Popen` (§9). L14 consumes a **CFG1-owned static identity object** with no version or "reported" attribute (§10). |
| **AMD-7** *(gate ambient)* | R6 §7.1 "Semantics" bullets on the probe child (R6 lines 537–549) and "Placement" sentence "The launcher text will read `PATH` and `SystemRoot`" (R6 lines 555–557); R6 §3 **AM-7** as to what the gate reads. | The gate reads exactly **one** ambient name, `PATH`, by name (§12). AM-7's placement and every other AM-7 obligation are preserved. |
| **AMD-8** *(temporal trade, named)* | R6 §5.1 "Why the probe is kept at all" (R6 lines 457–462); R6 §12.2 items 4 and 5 (R6 §12.2); R6 §14 **D-6** (R6 line 1747); R6 §14 **OC-3** (R6 line 1749); R6 §17 item 2 text (R6 line 1825); R6 header/Status lines "Implementation additionally blocked on OC-3" (R6 lines 29–30, Status block). | Executability of the Node/Pi pair is learned at L14/L15, after consumption and after the credential read — accepted **by name** (§13). OC-3 is **closed by removal** (§14). D-6 is **withdrawn** (it had no object once no `--version` runs). |

### 3.2 Superseded R6 minimum-suite rows and review text (details in §16)

R6 §11 rows **E, K, M** are deleted; rows **A, D, F, G, H, O, S, U, V** and the
§11 intro sentence ("injected leaf doubles for resolution/digest/probe"; "use a
synthetic script … as the 'node' executable") are rewritten; row **P** is
extended; R6 §12.2 items 1, 4, 5, 7, 10, 11, R6 §13's "identity-probe
environment builder" and probe-dependent allowed items, and R6 §16 rows "Seam
digests", "`preflight_pi_installed_offline`" (obligation (4)'s P5 sentence),
"Environment forbidden-fragment audit" and "Node/Pi identity/version/provenance"
are restated in §17 of this amendment.

---

## 4. Clauses preserved (exact)

Preserved **unchanged**, by reference:

- **CFG1 §14.2 / `PINNED_PI_SEAM_DIGESTS`**: the complete 20-entry table,
  including all three pinned `package.json` files; `PINNED_PI_VERSION =
  "0.85.1"` as a design literal (§7.4 constrains its use).
- **R6 §7.2** no-follow topology primitive, in full: `FILE_FLAG_OPEN_REPARSE_POINT
  | FILE_FLAG_BACKUP_SEMANTICS`; the five classifications; `reparse_point`
  refused unconditionally before any resolution; `(volume serial, 128-bit file
  id)` identity; re-proof by re-classification plus identity comparison; no
  containment inside the primitive. Its user list becomes **P1, P2, P2R, L14**.
- **R6 §5 P1** resolution rules, all of them: `PATH` walked in order; empty and
  non-absolute entries skipped; current directory never consulted; `node.exe`
  exact name, no `PATHEXT`; `pi.cmd` exact name, regular file only, never read,
  never executed, anchoring the two AR2 layouts; every lexical component
  inspected no-follow before use; containment checked on the **lexical** form
  and on the realpath'd destination; realpath only to confirm, never to launder;
  **first candidate only**; both §7.2 identities captured in memory.
- **R6 §5 P2**: every key of the table, never a subset; no-follow at every
  component; regular file; bounded size; one-handle digest; compare; only
  pinned relative keys ever rendered. Its warning that a 20-file digest walk is
  **not** proof that the package-root object is the one P1 resolved is
  preserved and is the reason P2R exists (§5.2).
- **R6 §5 closed-code note (B7)**: P-stage codes live only in
  `pi_identity_failure_code`; an anticipated P refusal is recorded as
  `refused_at_step = "L1"`, `pre_dispatch_refusal_code =
  "OFFLINE_PREFLIGHT_FAILED"`; P **returns** a typed result for anticipated
  failures and never raises for them; L1 validates the result's exact shape and
  commits P's family atomically; an unexpected raise inside P commits nothing of
  P's family and is recorded `UNEXPECTED_STEP_FAILURE`; no exception text,
  `repr`, or absolute path crosses P's boundary.
- **R6 §5.1 boolean-algebra discipline** paragraph (R6 lines 450–455).
- **R6 §4** "two proofs, one definition": the gate and L1 call the **same
  function object** with the same genuine leaf bindings; L1 never consumes the
  gate's result; `run_cfg1_stage` has no parameter through which it could.
- **R6 §7.1** gate properties other than those AMD-7 names: read-only,
  non-consuming, never calls `establish_stage_output_authority`, never touches
  `RESULTS_ROOT`, mints nothing, returns one closed code and nothing reusable;
  the rejection of enforcing the gate inside `establish_stage_output_authority`.
- **R6 §3 AM-3, AM-5, AM-6, AM-9 … AM-14**; **AM-7** except what the gate
  reads; **AM-8** as strengthened by AMD-6.
- **R6 §8** (W), **§9.1** (cursor), **§9.2** (three modes), **§9.2a** (category
  A/B; with `pi_observed_version` no longer a v2 field and no P fact being
  category B), **§9.2b**, **§9.2c** (A–D, including its own `P0…P6` provenance
  chain and the Y-6 stop rule, which stands on its own and no longer cites D-6
  as precedent), **§9.3**, **§9.4**'s step/code table and three-mode paragraph.
- **R6 §10** D-1 (run-record v2, v1 byte-for-byte retained), D-3 (refusal
  record v2), every v2 row not named in AMD-4.
- **R6 §11** rows **B, C, I, J, L, N, P, Q, R, T, W, X, Y, Z** (J and P
  extended, never weakened; §16).
- **R6 §13** prohibited list, entire; **R6 §14** D-1…D-5, OC-2 (restated, §14),
  OC-4…OC-11, R-WINDOW-E; **R6 §16** rows not named in §3.2; **R6 §17** numbering
  and order.
- **Frozen CFG1**: every §16.2 row other than L1's `--version` item — in
  particular **L12** (runtime child environment) and **L14** (`build_pi_argv`,
  `PiRpcSupervisor`, `RUNTIME_LAUNCH_FAILED`, closure L21-if-process/L23/L24/L27);
  §16.1 principles 1–5 exactly as frozen; §17; §18; §19; §21; §22 (§22.2 for v1
  entirely, and for v2 except AMD-4); AR0 **U-1** Node-direct launch shape
  (preserved at L14 — `build_pi_argv` launches the resolved `node.exe` with
  `dist/cli.js`).
- **`ar2.*` and the qualification package**: unmodified. CFG1 continues not to
  use `ar2.launch.resolve_runtime_identity` (OC-6 unchanged; AR2 live execution
  remains **NO-GO**).
- **Historical evidence**: A1/A2/A3 records, stage-closure records and
  authorization documents are not edited, re-validated into a new meaning, or
  re-labelled. Their `pi_observed_version` values keep **v1** meaning.

---

## 5. The static canonical Pi identity proof P

### 5.1 Stages

One CFG1-owned function; helper and module decomposition is **not** frozen by
this amendment. The **order lives in P's own body**; injectable leaves are
**only**: (i) the §7.2 inspection/identity primitive, (ii) a one-handle bounded
digest reader, (iii) an explicit ambient mapping. **There is no process-runner
leaf, no environment-builder leaf, and no leaf whose genuine binding can create
a process** — so neither a genuine binding nor a double supplied through P's
interface can make P execute anything, and a double cannot reorder P.

| Stage | Action | Executes anything? | Anticipated failure → `pi_identity_failure_code` |
|---|---|---|---|
| **P0 inputs** | Exactly one ambient name, `PATH`, read **by name** from the explicit mapping. No iteration, no other name (`SystemRoot` is no longer read). The checkout root, derived from the executing CFG1 package's own location (as G6 proves), for containment refusal only. | no | — |
| **P1 resolve + capture** | Exactly R6 §5 P1 (preserved, §4; no resolution rule is added or changed). Captures in memory: lexical `node.exe` path; lexical package-root path; lexical `<root>\dist\cli.js`; the §7.2 identity of `node.exe` (**Iₙ**); the §7.2 identity of the package root (**Iᵣ**). | no | `PI_RESOLUTION_FAILED` |
| **P2 complete seam proof** | Exactly R6 §5 P2 (preserved), over **all 20** keys, walked lexically from the package-root path P1 captured. Stages `pi_seam_digests_match`. | no | `PI_SEAM_UNPROVEN` |
| **P2R final identity-consistency re-proof** | Only if P2 passed. In fixed order: (b) the package root re-proved against **Iᵣ** by §7.2 re-proof; (c) `node.exe` re-proved against **Iₙ**. No seam re-walk (§5.2). Stages nothing new: `pi_seam_digests_match` stays P2's staged `true`. | no | `PI_IDENTITY_DRIFTED_DURING_PROOF` |
| **P-result** | Returns **one** typed result object. **Pass**: the static identity object of §10 (paths + Iₙ + Iᵣ, in memory only) and the durable family `pi_seam_digests_match = true`, `pi_identity_failure_code = null`. **Anticipated refusal**: `pi_identity_failure_code` ∈ the three codes (never `null`) and the staged `pi_seam_digests_match`; no identity object. L1 validates the object's exact shape, then commits `pi_seam_digests_match` and `pi_identity_failure_code` together — and, for a refusal, `refused_at_step`/`pre_dispatch_refusal_code` — as one sequence of plain assignments of already-validated values in which nothing can raise (R6 B14 discipline, preserved). | no | — |

After a pass, L1 proceeds to Git resolution (`ports.git_executable()`,
`resolve_git_executable`, unchanged — resolves by name, launches nothing; OC-7
unchanged).

**P never:** creates a process, loads or evaluates JavaScript, loads a Node
native addon, runs `node.exe`, reads or executes `pi.cmd`'s content, builds a
child environment, reads any ambient name except `PATH`, reads a credential or
endpoint, opens a socket or issues any network protocol request of its own,
writes, creates, renames, or deletes any file, or retains any byte it read
beyond the digest comparison.

**Who creates each fact.** P1 creates the three lexical paths and Iₙ/Iᵣ from
filesystem metadata alone. P2 creates the staged seam result from AIDO-read
bytes. P2R creates no fact; it can only refuse. **No fact in P comes from
anything Pi-controlled code produced**, because no Pi-controlled code runs. The
only version-bearing input is the pinned `package.json` bytes digested at P2
(§7).

### 5.2 What P2R means now that no `CreateProcess` follows it

R4/B11 made P2R "the last operation before P3's `CreateProcess`", which is why
it had to re-walk the complete seam set: an in-place edit after P2 would
otherwise have been **executed**. With P3 removed, nothing executes on P's
result before L14, and L14 re-walks the complete seam set and re-proves both
identities itself, immediately before the first execution (AMD-6). A second
seam walk inside P would only move P's "as of" instant a few milliseconds
later; any edit after it is exactly as possible, and exactly as caught, as an
edit after P2. A redundant walk would also invite the misreading that P2R still
guards an execution. It is therefore **not** retained.

What P2R **must** still guarantee is that **P never returns an internally
inconsistent identity** — a result whose Iᵣ names one directory object while
its seam proof was taken over a different one, or whose Iₙ is no longer the
object at the lexical `node.exe` path when P returns. The bracket is:

```text
P1 captures Iᵣ, Iₙ  ──►  P2 walks all 20 seams via the lexical root path  ──►  P2R re-proves Iᵣ, Iₙ
```

- A **persistent** replacement of the package root (for example, a directory
  holding byte-identical copies of the 20 pinned files but different unpinned
  code) made at any time between P1's capture and P2R is caught: the lexical
  root path now answers with a different identity at P2R.
- A **persistent** replacement of `node.exe` after P1's capture is caught at
  P2R.
- **For seam content, object origin is harmless:** every accepted seam file's
  bytes individually equal the pinned bytes, so the content claim holds
  whichever object supplied them. Object origin matters only for the unpinned
  remainder (OC-2) and for L14 launching from the same root — which L14
  re-proves from Iᵣ/Iₙ.
- **Residual, stated, not claimed closed:** a transient swap-and-restore
  wholly inside P1-capture → P2R (ABA) is not detected by P. It is harmless to
  execution — nothing executes on P's result, and L14 independently re-walks
  and re-proves identities against Iᵣ/Iₙ before the first execution — and it is
  the same residual class R6 §7.1 already states for every check→use window.
  Closing it would need share-mode locking of the Pi tree for the proof's
  duration, a new mechanism this amendment does not add.

P2R is kept because without it a persistent mid-proof root swap would pass L1
with an Iᵣ that describes a different object from the one walked, and be caught
only at L14 — **after** consumption, the credential read and the route check.
P2R moves that detection to pre-consumption (gate) and pre-credential (L1),
which is the reason to keep a final stage at all.

---

## 6. Order model after amendment

```text
 operator admission A0–A10 (unchanged)
 launcher source-origin gate G0–G6 (unchanged; G4/G5 lineage includes the P module)
 ┌─ pre-consumption Pi identity gate (§12) ──────────────────────────────────┐
 │   the ONE canonical static proof P: P0 → P1 → P2 → P2R → result           │
 │   reads PATH only · starts NO process · executes NO Node/Pi/JavaScript    │
 │   no credential · no network request · no write · no stage-output         │
 │   authority · returns one closed code, nothing reusable                   │
 └───────────────────────────────────────────────────────────────────────────┘
 ═════════════ consumption boundary: establish_stage_output_authority(...) ═════════════
 run_cfg1_stage(authority)            (signature unchanged; accepts no identity object)
   L0  admission
   L1  P again, FROM SCRATCH (same function object) → commit S, F → Git resolution
       starts NO process · executes NO Node/Pi/JavaScript          [cursor = L1, W = NOT_ATTEMPTED]
   L2–L13  exactly as R6 (W, baseline, L4 credential read, L7 route check, L9/9a,
           L11 pinned extension writer, L12 runtime environment, L13 broker READY)
   L14 build the supervisor in memory (argv from the §10 static identity object)
       → FULL re-proof: (a) all 20 seams  (b) root vs Iᵣ  (c) node.exe vs Iₙ
       → launch(): Popen  ◄── FIRST execution of node.exe / Pi-controlled JavaScript
   L15 … L30 exactly as R6 / frozen CFG1
```

---

## 7. Truthful version representation

### 7.1 What is established, and by what

`package.json` (the Pi package root's own) is one of the 20 pinned seam files
(`preflight.py:30`; CFG1 §14.2). A successful P2 establishes that the bytes at
`<root>\package.json` are byte-identical to the reviewed bytes whose SHA-256 is
`f1738e4b…a94c`. That those reviewed bytes declare version `0.85.1` is a fact
of the **design review** — CFG1 §1.2/§14.2 record the table as taken from
installed Pi 0.85.1, and the accepted OC-3 archaeology bound the exact 0.85.1
candidate to the table 20/20 — not a fact AIDO re-derives at run time. So the
truthful statement is:

> **Static package identity:** the package root L1 proved contains, among the
> 20 pinned files, a `package.json` byte-identical to the reviewed 0.85.1
> `package.json`. **Nothing ran, and nothing reported a version.**

It is **never** a runtime-observed, runtime-reported, or "Pi says" version, and
no text, field, console line, or record may describe it as one.

### 7.2 Fate of the two fields (decided)

| Field | v1 (archived) | v2 after this amendment | Why |
|---|---|---|---|
| `pi_observed_version` | unchanged: the v1 field, its v1 domain and v1 meaning (a bounded projection of AR2's `reported_version`); v1 validator byte-for-byte as shipped | **ABSENT.** The v2 exact-key set does not contain it; a v2 payload carrying the key fails validation | Its name and v1 meaning are "Pi executed and reported this". Nothing in a v2 run executes Pi before L14, and nothing after L14 reports a version, so every value it could hold in v2 would either be a static fact under an execution-claiming name (forbidden) or a constant. |
| `pi_version_probe_attempted` | did not exist | **ABSENT** (never emitted by any artifact) | It recorded entry into P3. P3 does not exist; a field that is `false` in every reachable record is dead schema. |

### 7.3 No replacement version field (decided, with the rejected alternative)

A static field such as `pi_identity_version = "0.85.1"` was considered and is
**rejected**:

1. **It carries no information.** AIDO never reads the version string; the
   value would be copied from the design literal whenever
   `pi_seam_digests_match == true` and meaningless otherwise, i.e. a pure
   function of fields already present — requiring one more cross-field
   invariant to keep it honest, and adding nothing a validator or reader can use.
2. **It is the misreading surface.** A later consumer seeing a version string in
   the identity group of a run record is the most likely way static identity
   gets mistaken for runtime observation (§18, question 7). Absence closes that
   by construction.
3. **The static identity is already mechanically carried:** a v2 record with
   `pi_seam_digests_match == true` asserts the complete 20-file proof, which
   includes the pinned `package.json`; the pin table is part of the audited
   source lineage (G4/G5).

The final v2 identity/version surface is therefore exactly two fields:
`pi_seam_digests_match` (unchanged meaning, R6 B14) and
`pi_identity_failure_code` (three-code domain).

### 7.4 `PINNED_PI_VERSION`

The shipped constant (`identity.py:40`) remains a **design literal** naming the
release the seam table was taken from. It has **no runtime consumer** in the
amended L1 (nothing is compared with it), and it must never be serialized into a
v2 record, compared with any child output, or rendered in a console line that
implies observation. The implementation may drop the executor's import of it;
removing the constant itself is not required.

---

## 8. Identity failure-code domain and v2 validator (AMD-4, AMD-5)

### 8.1 The closed domain

`pi_identity_failure_code ∈ {PI_RESOLUTION_FAILED, PI_SEAM_UNPROVEN,
PI_IDENTITY_DRIFTED_DURING_PROOF} ∪ {null}` — **three** codes.

| R6 code | Fate | Reason |
|---|---|---|
| `PI_RESOLUTION_FAILED` | **kept** | P1 still refuses |
| `PI_SEAM_UNPROVEN` | **kept** | P2 still refuses |
| `PI_IDENTITY_DRIFTED_BEFORE_PROBE` | **replaced** by `PI_IDENTITY_DRIFTED_DURING_PROOF` | the state survives (P2R still refuses on identity drift) but "before probe" names an event that no longer exists; its seam-byte variant is gone with P2R's seam walk (§5.2) |
| `PI_PROBE_FAILED` | **deleted** | P3 does not exist |
| `PI_SEAM_CHANGED_DURING_PROBE` | **deleted** | P4 does not exist |
| `PI_VERSION_MISMATCH` | **deleted** | P5 does not exist; a different `package.json` is a seam failure (`PI_SEAM_UNPROVEN`) |

None of the deleted names may appear in a v2 domain constant, builder, or
validator; none was ever emitted (no v2 artifact exists), so no archived
meaning is disturbed. `PRE_DISPATCH_REFUSAL_CODES` is unchanged by this
amendment (still no P code in it; still `UNEXPECTED_STEP_FAILURE` added by R6).

### 8.2 Reachable states (explanatory — **not** validator input)

Notation: `K` = `refused_at_step`, `C` = `pre_dispatch_refusal_code`, `F` =
`pi_identity_failure_code`, `S` = `pi_seam_digests_match`. `S` keeps R6 B14's
meaning exactly: *"the last seam walk P completed matched, and P's family was
committed"*; `false` means "not proven to match", never by itself "measured
mismatch". There is **no** category-B P fact any more: P's whole durable family
is `(S, F)`, committed atomically or not at all. `S` starts `false` (as shipped).

| Case | Internal stage (not durable) | `S` | `F` | `C` |
|---|---|---|---|---|
| Resolution failure | P1 refuses | `false` (never measured) | `PI_RESOLUTION_FAILED` | `OFFLINE_PREFLIGHT_FAILED` |
| Seam failure | P2 refuses | `false` (measured) | `PI_SEAM_UNPROVEN` | `OFFLINE_PREFLIGHT_FAILED` |
| Mid-proof identity drift | P2R (b) or (c) refuses | `true` (P2's walk passed) | `PI_IDENTITY_DRIFTED_DURING_PROOF` | `OFFLINE_PREFLIGHT_FAILED` |
| P success, Git resolution refuses | after P's commit | `true` | `null` | `OFFLINE_PREFLIGHT_FAILED` |
| P success, run continues | after P's commit | `true` | `null` | absent, or an L2–L18 code |
| Unexpected raise before P's commit | P0–P2R, result construction, or result-shape validation | `false` (not committed) | `null` | `UNEXPECTED_STEP_FAILURE` |
| Unexpected raise after P's commit | Git resolution | `true` | `null` | `UNEXPECTED_STEP_FAILURE` |

`Allowed(F)`: `PI_RESOLUTION_FAILED → {false}`; `PI_SEAM_UNPROVEN → {false}`;
`PI_IDENTITY_DRIFTED_DURING_PROOF → {true}`.

### 8.3 Validator rules — each a pure function of `K`, `C`, `F`, `S`

- **R-S1 (domains and key set).** `F ∈` the three codes `∪ {null}`; `S` an
  exact bool; the v2 exact-key set contains **neither**
  `pi_observed_version` **nor** `pi_version_probe_attempted`.
- **R-S2 (anticipated P refusal).** `F ≠ null ⇒ K == "L1" ∧ C ==
  OFFLINE_PREFLIGHT_FAILED ∧ S ∈ Allowed(F)`.
- **R-S3 (anticipated L1 refusal P does not own).** `K == "L1" ∧ C ==
  OFFLINE_PREFLIGHT_FAILED ∧ F == null ⇒ S == true` — the Git-resolution
  refusal, the only meaning this conjunction can have.
- **R-S4 (unexpected L1 failure).** `K == "L1" ∧ C == UNEXPECTED_STEP_FAILURE
  ⇒ F == null`. `S` is either value: `false` says only "before P's commit",
  `true` only "after P's commit". The rule claims nothing about which internal
  stage raised.
- **R-S5 (past L1).** `K` absent, or `K ≠ "L1"` ⇒ `F == null ∧ S == true`.
- **R-S6 (L1 code domain).** `K == "L1" ⇒ C ∈ {OFFLINE_PREFLIGHT_FAILED,
  UNEXPECTED_STEP_FAILURE}` (R6 §9.4 table, restated).

**Exhaustive and mutually exclusive:** `F ≠ null` → only R-S2; `F == null ∧ K
== "L1"` → by R-S6 exactly one of R-S3 / R-S4; `F == null ∧ K ≠ "L1"` (incl.
absent) → R-S5. A record satisfying none fails self-validation
(`RECORD_INVARIANT`, halt), exactly as R6 prescribes.

**Every mode reachable, none ambiguous.** Each of the three codes is reachable
(P1, P2, P2R); REFUSAL, POST_DISPATCH_UNEXPECTED and NO_DISPATCH_FAILURE (R6
§9.2) are all unchanged and reachable; `(K="L1", C=OFFLINE_PREFLIGHT_FAILED,
F=null)` has exactly one meaning.

### 8.4 Validator invariant delta (R6 → effective)

| R6 | Effective |
|---|---|
| τ = `(A, S, V)`; σ = `(true, true, PIN)` | the P tuple is `S` alone; P success is `S == true ∧ F == null` |
| R-P1: six codes; `A`, `S` bools; `V` domain incl. `NOT_OBSERVED`/`UNRECOGNIZED` | R-S1: three codes; `S` bool; both removed keys **forbidden** |
| R-P2 with six `Allowed(F)` tuple sets | R-S2 with three singleton sets |
| R-P3: `τ == σ` | R-S3: `S == true` |
| R-P4: `τ ∈ U = {(false,false,NO), (true,false,NO), σ}`; `A` separated "Pi code may have run" | R-S4: `F == null`, `S` free. The "Pi code may have run at L1" distinction is **gone because it is impossible by construction** (§16 Tests AA/AB), not because it was dropped |
| R-P5: `F == null ∧ τ == σ` (incl. `V == PIN`) | R-S5: `F == null ∧ S == true` |
| R-P6 | R-S6, identical |
| category-B P fact `A` (write-ahead at P3) | none |
| every other v2 invariant (W, three modes, direct iff, step/code table, closure predicate) | **unchanged** |

---

## 9. L14 first-execution semantics (AMD-6)

L14 is where the resolved `node.exe` first runs and where Pi-controlled
JavaScript is first evaluated in a CFG1 live run. In fixed order:

1. **Construct the supervisor in memory.** `build_pi_argv` (frozen, unedited)
   over the §10 static identity object, the L11 extension entry taken from a
   fresh `verify_extension_issuance` (R6, unchanged), the frozen allowlist,
   provider and model; `PiRpcSupervisor(...)` with the L12 environment. This
   reads no Pi file and starts nothing. A raise here is `RUNTIME_LAUNCH_FAILED`
   with no process (shipped behavior).
2. **Full re-proof, against L1's captures, in this order:** (a) the complete
   20-key seam set re-walked from the lexical package-root path with exactly
   P2's rules — never a subset, never cached; (b) package root vs **Iᵣ**; (c)
   `node.exe` vs **Iₙ**. The two identity checks sit nearest the use. Any
   failure → `RUNTIME_LAUNCH_FAILED` at L14, **no `launch()` call**, no
   process, `runtime_created` stays `false`.
3. **`launch()`** — `Popen` of `[node.exe, <root>\dist\cli.js, …]`, `shell=False`,
   cwd the workspace root, environment exactly L12's. Between (2c) and `Popen`
   there is **no** operation that reads the Pi tree, resolves a name, or
   executes anything.

**What (2) now carries.** It is the **sole** pre-first-execution proof. It
inherits B11's full burden (an in-place edit or same-directory replacement of
any pinned seam file under an unchanged root is caught by (a)), B3/B8's
(a same-path different-object swap of the root or `node.exe` is caught by (b)/(c),
even when bytes collide), and D-4's. Residual, unchanged in kind: the
check→use sliver from each item's read in (2) to `Popen`; stated, not closed.

**How the two executability failure classes surface (shipped supervisor
behavior, read from `ar2/supervisor.py:398–443`; not changed here).**
`launch()` returns once `Popen` succeeds.

| Failure | Where observed | Record |
|---|---|---|
| `CreateProcess` fails (e.g. `node.exe` not a valid executable image, missing dependency DLL of the image loader, access denied) | L14 `launch()` raises (`OSError` → supervisor error) | `RUNTIME_LAUNCH_FAILED` at L14; `runtime_created` `false` (no `process`); closure **L23, L24, L27** (frozen L14 row) |
| Process is created, then Node or Pi fails at start-up (module-resolution failure, a throwing pre-version import, immediate exit, hang) | **L15** — the run-unique `get_commands` correlation is never satisfied within the frozen bound | the frozen L15 correlation failure (`RUNTIME_CORRELATION_FAILED`); `runtime_created` `true`; closure **L21–L27** |

The second row matters: R6 would have caught most of those at P3/P5
pre-consumption; after this amendment they are **not** L14 failures and must
never be described as such. Both are closed, fail-closed pre-dispatch refusals
(`dispatch_state = NOT_ATTEMPTED`, `prompt_writes == 0`).

**Durable indistinguishability, accepted.** The v2 record does not distinguish
"L14 re-proof refused (the Pi tree or `node.exe` drifted)" from "`CreateProcess`
failed": both are `RUNTIME_LAUNCH_FAILED` at L14 with `runtime_created ==
false` and identical lifecycle, classification, and halt. R6 had the same
property. No new field or console code is added; tests distinguish them by call
recording (§16 Test AD).

**Runtime environment.** Unchanged. The L12 environment governed by the frozen
CFG1 runtime contract (positive allowlist: Windows baseline, narrowed `PATH`,
the Pi-owned variables, exactly one credential carrier; `NODE_OPTIONS`/`NODE_PATH`
and every forbidden-fragment name withheld; re-audited by name) is the
environment of the first Node/Pi execution. No contradiction with the accepted
runtime model was found (§17).

---

## 10. The L14 static identity object

A CFG1-owned, frozen, in-memory object produced only by a **passing** P and
consumed by L12 and L14. Name and module not frozen. Exactly these attributes:

| Attribute | Content | Consumer |
|---|---|---|
| `node_executable` | P1's confirmed absolute `node.exe` path | L12 (`PATH` narrowing, unchanged); L14 argv via `build_pi_argv`; L14 re-proof (c) |
| `pi_cli_js` | `<root>\dist\cli.js`, the lexical path P2 digested | L14 argv via `build_pi_argv` |
| `pi_package_root` | P1's confirmed package-root path | L14 re-proof (a)/(b) |
| `node_identity` | Iₙ | L14 re-proof (c) |
| `package_root_identity` | Iᵣ | L14 re-proof (b) |

**No** `reported_version`, no `version`, no `launch_shape`, and no other
attribute. The object is never durable, never rendered, never returned by the
gate, and never accepted by `run_cfg1_stage`.

**Compatibility with frozen `build_pi_argv`.** The frozen function is annotated
`identity: RuntimeIdentity` but its body reads **exactly**
`identity.node_executable` and `identity.pi_cli_js`
(`ar2/launch.py:141–142`); Python does not enforce the annotation. CFG1 passes
its own object; `ar2.launch` is not edited and `ar2.launch.RuntimeIdentity` is
not constructed by CFG1 (constructing it would require populating
`reported_version`, which AMD-6 forbids). Test AG pins this: an object exposing
**only** the five attributes (e.g. `__slots__`, no `__getattr__`) yields exactly
the expected argv, and if the frozen function ever reads any other attribute the
test fails and the implementation **stops and returns to design** — it never
adds a placeholder attribute.

---

## 11. Retired probe mechanisms vs. the preserved runtime environment

| Retired (must not exist in the implemented FU1, not even unreachable) | Preserved (unchanged) |
|---|---|
| R6 §6 identity/version child environment builder and its four-name allowlist (`SystemRoot`, `PI_OFFLINE`, `PI_SKIP_VERSION_CHECK`, `PI_TELEMETRY`) | the **L12** runtime child environment builder (`environment.py`), its positive allowlist, `FORBIDDEN_NAME_FRAGMENTS` audit, and credential carrier |
| the P3 probe runner leaf (bounded-wait, output-capped, `DEVNULL` child runner) and its "refuse a `None` environment" rule | the L14 `PiRpcSupervisor` and its frozen bounds |
| P3 argv `[node, cli.js, "--version"]`; P4 post-probe re-proof; P5 version projection and its stdout grammar (`\n`/`\r\n`, `UNRECOGNIZED`, `NOT_OBSERVED`) | P1, P2, P2R (redefined), L14 re-proof |
| the category-B write-ahead of `pi_version_probe_attempted` | the six R6 §9.2a category-B families (W, dispatch, broker, runtime, verification, L9/L11 scrub facts) |
| the second, identity-probe instance of the forbidden-fragment audit (R6 §16) | the L12 instance |
| any genuine CFG1 port whose binding executes Node or Pi before L14 (in particular `resolve_runtime_identity`, whose genuine binding was `ar2.launch.resolve_runtime_identity`) | `ar2.launch.resolve_runtime_identity` itself, unedited, for AR2's own callers (OC-6) |
| D-6 (contingency on `--version` behavior) | the R6 §9.2c Y-6 stop-and-return rule, which stands on its own |
| R6 §6's `SystemRoot` lookup-case requirement and its test | — |

"Retired" means: no symbol, constant, port field, or configuration requirement
for these remains in `experiments/pi_harness_cfg1/`, and no launcher or
authorization text requires `SystemRoot` for identity. It is **not** a
statement about AR2.

---

## 12. The pre-consumption gate after amendment (AMD-7)

### 12.1 What it is

A purely static filesystem identity check: one read-only public entry that
calls **the same P function object** with the same genuine leaf bindings L1
uses. Unchanged from R6 §7.1 except as stated here.

### 12.2 Ambient names

Exactly **`PATH`**, read by name, once. Mechanically sufficient: P0 needs
nothing else (the checkout root comes from the executing package's location;
§7.2 and the digest reader need no environment). `SystemRoot` was required only
to start the probe child and is no longer read. The future authorization's
launcher text must state that it reads the `PATH` value (non-secret) — A3's
text stays historical.

### 12.3 Properties (each mechanically tested, §16)

- **no child process** — zero process-creation calls on every outcome;
- **no Node, Pi, or JavaScript execution** — a corollary of the above plus P's
  leaf set;
- **read-only / write-free** — no create, write, rename, delete (the launcher
  already runs `-B` with an empty pycache prefix);
- **non-consuming** — never calls `establish_stage_output_authority`, never
  touches `RESULTS_ROOT`, mints nothing;
- **credential-free** — reads no ambient name but `PATH`;
- **network, stated exactly** — P itself creates no socket and issues no network
  protocol request. Its only I/O is read-only filesystem access to lexical paths
  derived from `PATH`. That access may cause OS-level filesystem/redirector I/O
  depending on operator-controlled `PATH`, drive mappings, or filesystem
  topology. **No claim is made that the OS cannot perform network I/O while
  servicing a filesystem open**, and no drive-type, mapping, or remote-path
  detector is added by this amendment; P1's candidate-resolution rules are
  exactly R6's.
- **no stage-output authority and nothing reusable** — returns one closed code
  (pass, or one of the three P codes) and no identity object, token, digest,
  path, or timestamp. L1 re-proves from scratch.

The gate remains **waste avoidance**: skipping it wastes an authorization but
bypasses no security invariant, because L1 (pre-credential) and L14
(pre-execution) carry the security claims.

---

## 13. The named temporal trade (AMD-8)

**R6 intended** to learn, at the pre-consumption gate and again at L1 (after
consumption, before L2 and before the L4 credential read): that
this `node.exe` can launch this `cli.js`, and that the running `cli.js` reports
the pinned version.

**After this amendment**, the gate and L1 establish **only** filesystem and
package provenance: resolution, identities, the complete 20-file seam proof,
and the static `package.json` identity. Actual Node/Pi **executability** is
learned at **L14** (process creation) or **L15** (start-up/correlation).

**Consequence, stated without softening.** A broken `node.exe`, a Pi start-up
failure, or a module-resolution failure in unpinned code now:

1. **consumes the authorization** (it passed the pre-consumption gate; L1's
   static proof follows consumption and passes as well);
2. mints and populates the workspace (L2) and runs baseline verification (L3);
3. **reads the credential and endpoint** (L4) and builds the secret context (L5);
4. performs the **one authenticated non-inference route check** (L7) — one of
   the stage's at most 9;
5. mints the capability (L8), writes the **endpoint-bearing** generated config
   (L9), constructs the broker (L10), writes the **token-bearing** extension
   (L11), builds the **credential-carrying** child environment (L12), starts
   the broker pipe (L13);
6. then refuses — `RUNTIME_LAUNCH_FAILED` at L14 if `CreateProcess` fails, or
   the L15 correlation failure if the process was created — with **every**
   closure obligation for those resources exercised (L21 if a process exists,
   L23, L24's identity-bound scrubs, L27), classification and halt per frozen
   §12/§19 (a fully closed refusal is `REFUSED_PRE_DISPATCH` / halt
   `PRE_DISPATCH_REFUSAL`; any unproven closure is `INDETERMINATE_LIFECYCLE` /
   `LIFECYCLE_CLOSURE_UNPROVEN`), and the stage halts.
7. In the L15 case, **a Pi process was started with the L12 credential-carrying
   environment** and ran code that then failed. That is the accepted runtime
   trust model applied to a broken installation, not a new exposure class (below).

**The guarantees are not identical, and this amendment does not claim they
are.** Pre-consumption, credential-free detection of launchability is given up.

**Why accepting this is safer than executing a provenance-incomplete closure
before consumption:**

- **The probe was never proof against the risk that matters.** OC-3's finding
  is that `--version` evaluates unpinned code (`dist/cli/setup.js` and what it
  imports) before `cli.js`'s body. Unpinned code that has been **modified** but
  still prints `0.85.1` passes P3/P5 and then runs at L14 with the credential
  environment anyway (R6 §12.2 item 1 already said the seam proof does not make
  the probe safe). The probe's only unique detection is **accidental** breakage.
- **It would have multiplied unbound executions.** Under R6, one Stage-1
  execution performs **one** pre-consumption gate probe; then, after
  consumption and before the L4 credential read, **one** L1 probe for each
  reached run; then **one** L14 runtime execution for each reached run that gets
  to L14 — all unpinned Pi code, in the launcher's process tree, whose
  environment block holds the live credential names (R6 §6's same-user honest
  limit). No fixed total is stated, because the stage may halt before all
  ordinals are reached. The amendment removes the pre-consumption gate execution
  and each reached run's post-consumption / pre-credential L1 execution. The
  intended L14 runtime execution remains — the one execution the experiment
  exists to perform, immediately after the strongest re-proof.
- **Its side effects are unprovable.** Because the first evaluated code is
  unpinned, whether `--version` reads `~/.pi/agent` settings/auth, reads
  project-local state, writes, or touches the network **cannot** be derived from
  pinned bytes (the verdict). Keeping the probe would mean deliberately running
  code with unproven side effects before any authority exists to account for
  them.
- **The lost signal fails closed.** Every launchability failure now lands in an
  existing, fully specified refusal path with existing closure obligations; no
  failure can produce a false pass, a dispatch, or a qualification claim.

**No new cleanup or secret-lifecycle mechanism is required** (§18 question 9):
every resource reached before L14/L15 already has frozen closure obligations for
an L14/L15 refusal. What changes is **frequency**: a class that used to end at
L1 with nothing to close now exercises full closure — which raises the practical
importance of OC-4 (closure totality), already pre-A4 barrier item 4; its order
is not changed.

---

## 14. OC-2, OC-3 and D-6 after amendment

- **OC-3 — CLOSED BY REMOVAL** (subject to acceptance of this amendment). The
  derivation it demanded concerned a `--version` execution that no longer
  exists. It was **not completed**; it was **made unnecessary**. The accepted
  verdict `OC2_PREVENTS_OC3_PROOF` stands as the reason.
- **D-6 — WITHDRAWN** (no object).
- **OC-2 — REMAINS OPEN as a stated residual, and does not expand.** Exactly:
  - OC-2 **no longer blocks L1 or pre-consumption**, because no Pi code
    executes there;
  - OC-2 **remains a stated residual for the actual runtime beginning at L14**:
    the L14 runtime executes unpinned transitive Pi code (including
    `dist/cli/setup.js` and everything else outside the 20-file table) and an
    unpinned `node.exe` binary, under the existing accepted CFG1 runtime trust
    model — R6's I-1 holds relative to "the frozen identity CFG1 requires", not
    relative to all executed code;
  - this amendment creates **no** whole-package manifest, **no** Node pin, and
    **no** new blocker. Removing the probe exposes no separate contradiction
    with the accepted L14 runtime model: that model already launched unpinned
    transitive code at L14 with the credential environment (R6 line 1748), and
    this amendment changes neither what L14 launches nor with what environment.
- **R6 §1 invariants.** **I-1** is strengthened: no Pi-package-controlled code
  runs before L14 at all, and at L14 only after the full re-proof. **I-2**
  ("identity/version children are secret-free by construction") holds
  vacuously and is re-stated as a prohibition: **no** identity/version child may
  be introduced.

---

## 15. Durable-schema delta (v2 only; v1 untouched)

| R6 §10 row | Effective |
|---|---|
| `pi_observed_version` domain adds `NOT_OBSERVED`; `UNRECOGNIZED` meaning | **Removed from v2** (key absent; forbidden by R-S1). v1: unchanged field, domain, meaning, validator |
| new field `pi_version_probe_attempted` | **Not added** |
| `pi_seam_digests_match` meaning (R4/B14) | **Unchanged** |
| new field `pi_identity_failure_code`, six codes | Added, domain **three** codes (§8.1); every other property of the row unchanged (atomic commit; never written into `pre_dispatch_refusal_code`; `null` on P success and on every unexpected L1 failure) |
| `PRE_DISPATCH_REFUSAL_CODES` | Unchanged from R6 (no P code; `UNEXPECTED_STEP_FAILURE` added) — "six P-identity codes" reads "three" |
| new invariants | R6's list with R-P1…R-P6 replaced by R-S1…R-S6 (§8.3); everything else unchanged |
| filesystem identities | Still **not** durable; held in memory from P1 to L14 (P2R, L14 re-proof) |
| every other v2 row (`workspace_mint_state`, v2 closure predicate, `unexpected_failure_step`, removed/retracted fields, `generated_config_scrub_verified` semantics) | **Unchanged** |

Refusal record v2 (D-3) and the stage-closure record (v1) are unaffected: neither
carries a version field (`records.py:879–894` for the refusal key set).

---

## 16. Test-suite reconciliation

All offline, `tmp_path` only, no real Node or Pi, no socket, no credential.
R6 §11's intro is rewritten: "injected leaf doubles for resolution and digest";
the "synthetic script as the 'node' executable" sentence applies only to L14
tests (AD, AG), never to P.

### 16.1 Deleted (the probe no longer exists)

| R6 test | Reason |
|---|---|
| **E** (P3 failures: `0.87.0`/garbage/oversize/non-zero/timeout) | no probe. The `0.87.0` scenario survives as a seam case (a different `package.json` ⇒ `PI_SEAM_UNPROVEN`), covered by D and H. |
| **K** (P4: probe rewrites a seam; root identity changes during probe) | no probe, no P4. The identity-change half survives as U. |
| **M** (probe descendant holds stdout past the deadline) | no probe child. (The runtime child's bounds at L14 are frozen supervisor behavior, not re-tested here.) |

### 16.2 Rewritten for static P

| R6 test | Must now prove |
|---|---|
| **A** | L1 refusal for resolution, seam, P2R identity drift, and `git_executable` — each separately — through the real executor and the stage-runner offline seam: mint-leaf count 0; W `NOT_ATTEMPTED`; closed lifecycle; `REFUSED_PRE_DISPATCH`; halt `PRE_DISPATCH_REFUSAL`; ordinals 2–9 `NOT_EXECUTED`; `(S, F)` per §8.2 and `S ∈ Allowed(F)`; `C == OFFLINE_PREFLIGHT_FAILED` throughout; Git case `F == null ∧ S == true`; **process-creation tripwire count 0** in every case; v2 validates. |
| **D** | P2 failures (mismatch, missing file, reparse component, non-regular, oversize, and a `package.json` from another release): credential resolver, route observer counts 0; tripwire count 0; `S == false`, `F == PI_SEAM_UNPROVEN`; record carries no `pi_observed_version` / `pi_version_probe_attempted` key. |
| **F** | P reads **only** `PATH`: an access-recording mapping holding decoys for every excluded name (incl. `SystemRoot`, `NODE_OPTIONS`, `PI_QUALIFICATION_B300_ROUTE_KEY`, `AIDO_LITELLM_API_KEY`, `AIDO_LITELLM_BASE_URL`, `AWS_SECRET_ACCESS_KEY`) records exactly one lookup, of `PATH`, for both the gate and L1; no mapping iteration. (The child-side assertions are deleted — there is no child.) |
| **G** | Unexpected raise at L2, L5, L9, L10, L11, L14, L18 (post-write), L20 — unchanged — and inside P at: before P1 completes; after P1, before P2 completes; after P2, before P2R completes; after P2R, during result construction or shape validation; after P's commit (Git resolution). Inside P: REFUSAL mode, `C = UNEXPECTED_STEP_FAILURE`, `F == null`, `S == false` for the first four boundaries and `S == true` after the commit; the v2 validator run on the serialized record alone accepts each; tripwire count 0 for every L1 case. |
| **H** | Gate with drifted seams (incl. a `0.87.0` `package.json`), drifted identity, and a resolution failure: closed refusal code; stage-output mint registry and `RESULTS_ROOT` unchanged; no credential read; **tripwire count 0 on every outcome, including pass**. |
| **O** | Forged records each fail by durable fields alone: `F` set at `K = "L7"`; `(L1, OFFLINE_PREFLIGHT_FAILED, F = null, S = false)`; `F = PI_IDENTITY_DRIFTED_DURING_PROOF ∧ S = false`; `F = PI_SEAM_UNPROVEN ∧ S = true`; `(L1, UNEXPECTED_STEP_FAILURE, F ≠ null)`; a post-L1 record with `S = false`; `pre_dispatch_refusal_code = PI_SEAM_UNPROVEN`; `F` = any deleted R6 code; a v2 payload carrying a `pi_observed_version` or `pi_version_probe_attempted` key; plus R6's `(L1, ROUTE_UNAVAILABLE)` and code-without-step cases. |
| **S** | Unchanged scenario, re-worded trigger: `node.exe` or the package root replaced (same path, new record, bytes kept) **after L1 passes**, before L14 — L14 re-proof (b)/(c) refuses; `RUNTIME_LAUNCH_FAILED`; `launch()` count 0; `runtime_created == false`. |
| **U** | `node.exe` replaced, and separately the package root replaced by a directory whose 20 pinned files are byte-identical, **between P1's capture and P2R** (hook during/after P2): P2R refuses; `F == PI_IDENTITY_DRIFTED_DURING_PROOF`, `S == true`; tripwire count 0; exercised through **both** the gate and L1. |
| **V** | Retargeted to L14 (B11's burden, §9): L1 passes; then, with root and `node.exe` records unchanged, `dist/cli.js` is (i) modified in place, (ii) replaced by a new file in the same directory; (iii) any other pinned seam file modified in place: L14 re-proof (a) refuses; `launch()` count 0; `RUNTIME_LAUNCH_FAILED`; call-order recording shows (a)→(b)→(c) complete before `launch()` and nothing that reads the Pi tree between (c) and `Popen`. |

### 16.3 Unchanged (still minimum requirements)

**B, C, I, J** (extended below), **L, N, P** (extended below), **Q, R, T, W, X,
Y, Z** — exactly as R6 §11. **J** unchanged from R6 §11 (no remote-form case is added). **L** additionally: P's injectable leaf set contains no process-creation or
environment-builder leaf (asserted structurally). **P** additionally: call-order
recording of the L14 re-proof order.

### 16.4 New regressions

| # | Maps to | Scenario | Must prove |
|---|---|---|---|
| **AA** | A | The gate, genuine leaves over a synthetic `tmp_path` Pi tree, on pass and on each refusal, under a **process-creation tripwire** patched at `_winapi.CreateProcess`, `subprocess.Popen`, `os.system`, `os.startfile`, `os.spawn*`, `os.exec*`, and `multiprocessing.Process.start` | tripwire count **0** on every outcome; **plus** a static AST audit of the gate module, the P module, and the §7.2/digest leaf modules: no import of `subprocess`, `multiprocessing`, `asyncio.subprocess`, and no reference to `CreateProcess*`, `ShellExecute*`, `WinExec`, `os.system`, `os.startfile`, `os.spawn*`, `os.exec*` (catches a `ctypes` route the dynamic tripwire cannot) |
| **AB** | B | The executor with the tripwire armed from L1 entry to L2 entry (cursor-driven), for an L1 pass that proceeds (L2 via a double) and for every L1 refusal | tripwire count **0** within L1; Git resolution spawns nothing |
| **AC** | C | Successful static P over a synthetic tree whose 20 files match a **test-owned** pin table | result carries `S == true`, `F == null`; the digest-reader recording shows every one of the 20 keys, including `package.json`, read once each through one handle; the identity object's attribute set equals exactly §10's five; no attribute or field name contains `version` or `reported`; no JSON parse of `package.json` occurs |
| **AD** | G | (i) L14 `CreateProcess` failure — the real supervisor launching a synthetic `tmp_path` file named `node.exe` that is not a valid image; (ii) a created process that exits immediately / never answers (supervisor double, and a synthetic script where feasible); (iii) L14 re-proof refusal | (i) `RUNTIME_LAUNCH_FAILED` at L14, `runtime_created == false`, closure L23/L24/L27 performed; (ii) the L15 correlation failure, `runtime_created == true`, L21 performed; (iii) as S/V. In every case the record shows the boundaries actually reached: W `AUTHORITY_RETURNED`, route observation performed (L7), `broker_reached_ready` (L13), `generated_config_scrub_verified` / `extension_binding_scrub_verified` from L24's identity-bound results, `dispatch_state == NOT_ATTEMPTED`, `prompt_writes == 0`, lifecycle / classification / halt per frozen §12/§19; the credential-read port was called exactly once; no record or console line says or implies L1 failed; (i) and (iii) carry identical durable facts and are distinguished only by call recording |
| **AE** | H | v2 emission and validation | the v2 domain constant is exactly the three codes; the v2 builder refuses to serialize any other value; the validator refuses each deleted R6 code; a static scan finds none of `PI_PROBE_FAILED`, `PI_SEAM_CHANGED_DURING_PROBE`, `PI_VERSION_MISMATCH`, `PI_IDENTITY_DRIFTED_BEFORE_PROBE` in `experiments/pi_harness_cfg1/` production modules |
| **AF** | I | Probe mechanisms unreachable | static: no module under `experiments/pi_harness_cfg1/` imports `ar2.launch.resolve_runtime_identity`; the run-ports structure has no `resolve_runtime_identity` (or other Node/Pi-executing pre-L14) field; no identity-probe environment builder or runner symbol exists; dynamic: across a full offline genuine-path run with doubles, a tripwire classifying each creation by executable finds **no** creation whose image is the resolved `node.exe` before L14 and exactly **one** at L14 |
| **AG** | — (AMD-6) | frozen `build_pi_argv` over the CFG1 identity object | an object exposing only §10's five attributes (`__slots__`, no `__getattr__`) yields exactly the expected argv tuple; any read of another attribute fails the test (implementation stops and returns to design) |
| **N** | J | v1 compatibility (retained R6 N) | synthetic v1 payloads, including an A3-shaped one with `pi_observed_version`, validate/refuse exactly as before; v1 closure outputs unchanged |

Mapping to the reviewer's list: **A**→AA; **B**→AB; **C**→AC; **D**→A, D, U, O;
**E**→I; **F**→P, S, V; **G**→AD; **H**→AE, O; **I**→AF; **J**→N.

---

## 17. Restated R6 text (so no probe-dependent sentence is left normative)

- **R6 §7.1 TOCTOU table.** Row "persistent drift after T₀" unchanged. Row
  "transient swap between T₀ and T₁" unchanged. Row "swap or in-place edit
  between P1/P2 and P3's `CreateProcess`" → **"between L1 and L14's first
  execution"**: caught by L14 re-proof (a)/(b)/(c); residual: L14 re-proof →
  `Popen` sliver. Row "same-pathname, different-file swap" → identity bound at
  P1, re-checked at **P2R** and **L14** (P4 removed). Row "swap between L1 and
  L14" unchanged, except "the pair P3 proved" reads "the pair L1's P proved and
  L14 re-proved". Closing paragraph: the check→use residuals are now (i) inside
  P (ABA, harmless to execution, §5.2) and (ii) L14 re-proof → `Popen`; "P4 is
  post-probe tamper detection" is deleted.
- **R6 §12.1.** "Who creates each fact": no fact comes from child output.
  "Who can mutate": no Pi-executed code exists before L14. "Version and seam
  facts from different roots": there is no version observation; the only
  version-bearing input is `package.json` inside P2's walk; P2R bounds root
  consistency up to ABA (§5.2). "Pair L14 launches": L14 re-proves against L1's
  Iᵣ/Iₙ. "Individually valid Node and Pi disagree": observable only at L14/L15.
  "Child regains secrets": no pre-L14 child exists. "Raw exception escapes":
  P emits closed codes and pinned relative keys only.
- **R6 §12.2.** Item 1: the seam proof never made the probe safe — the probe is
  removed (OC-3 verdict). Item 4 (minimal environment too small): moot.
  Item 5 (running Pi pre-consumption is new): **no Pi code runs
  pre-consumption.** Item 7 (P4 persistent-only): moot. Item 10: the gate reads
  `PATH` only. Item 11 (D-6 derivation cannot be done): superseded by §14.
- **R6 §13 allowed scope.** Remove "the identity-probe environment builder",
  "including the P2R final pre-execution proof — complete seam set plus both
  identities", and "`pi_version_probe_attempted`"; read "P2R final
  identity-consistency re-proof (AMD-2)", "the CFG1 static identity object
  (§10)", "R-S1…R-S6", "three-code `pi_identity_failure_code`". Prohibited list
  unchanged, plus: no identity/version child, no pre-L14 execution of the
  resolved `node.exe` or of the Pi package by any path.
- **R6 §16 reconciliation rows.** *Seam digests* → owners **P2** (gate, L1) and
  the **L14 re-proof**; tests D, U, V, P. *`preflight_pi_installed_offline`*
  → obligations (1)–(4) still subsumed at parity or better by P1/P2; the
  sentence "and P5 additionally runs `--version` …" is **retracted** (P now
  matches the old helper's own "never that it runs, and never a version
  comparison" posture, while remaining strictly stronger through the pinned
  `package.json` digest). *Environment forbidden-fragment audit* → L12's
  instance only. *Node/Pi identity/version/provenance* → superseded by static
  P (P1/P2/P2R) plus the L14 re-proof; tests A, D, J, S, U, V, AA–AF.
- **R6 §17 pre-A4 barrier sequence.** Numbering and order **unchanged**. Item 1
  reads "This FU1 design (R6) **and AMEND1** accepted/frozen". Item 2 reads
  "OC-3 archaeology accepted with verdict `OC2_PREVENTS_OC3_PROOF`, and OC-3
  closed by the AMEND1 probe removal" — satisfied only when the reviewer accepts
  this amendment. Item 7 ("read-only pre-A4 identity/seam verification")
  must itself be static: it executes no Node or Pi.

**Contradiction search (result: none found).** Checked against: frozen CFG1
§16.1 principles 1–5 (AM-2's withdrawal returns principle 5 to its frozen
text); §16.2 L4 (the credential read receives no version gate result —
`run_executor.py:549–553`); §16.2 L12 (unchanged environment; `NODE_OPTIONS`
already withheld); §16.2 L14 (`build_pi_argv(identity, …)` — the identity's
type is not frozen by the row; AR0 U-1 launch shape preserved); §14.1 item 2
("Pi 0.85.1 with the §14.2 digests" — satisfied by the digest proof); §22.2/§22.5
(v1 untouched; v2 dispatch gains no new version); R6 D-1…D-4, B1–B18, AM-3…AM-14;
L16-FU2 R2 + ERR1 (no version dependency); the refusal and stage-closure records
(no version field).

---

## 18. Adversarial design analysis

### 18.1 Round 1 — the required questions

| # | Question | Answer |
|---|---|---|
| 1 | Is `package.json`'s pinned digest genuinely sufficient for the static version identity claimed? | For **byte identity with the reviewed file**: yes, under SHA-256 second-preimage resistance. For "**that file declares 0.85.1**": that is a fact of the design review (CFG1 §1.2/§14.2; the accepted archaeology's 20/20 bind), not re-derived at run time — which is why the claim is phrased as "byte-identical to the reviewed 0.85.1 `package.json`" and never as an observed version (§7.1). It says nothing about which code runs: `package.json`'s `version` is data, not executed code, and OC-2 is untouched. |
| 2 | Can P return a root/version fact assembled from different filesystem objects? | Not persistently: P1 captures Iᵣ before P2's walk; P2R re-proves Iᵣ after it. A persistent root replacement at any point in between refuses `PI_IDENTITY_DRIFTED_DURING_PROOF`. An ABA swap-and-restore wholly inside that window is a stated residual, harmless to execution (L14 re-proves before the first execution) (§5.2). For seam **content** object origin is immaterial — each accepted file equals its pin. |
| 3 | Can mutation during P cause an internally inconsistent returned identity? | Only through the ABA residual. A persistent root or `node.exe` swap after P1 is caught at P2R; an in-place seam edit during P2 either lands before that file's read (mismatch → `PI_SEAM_UNPROVEN`) or after it (P's "as of" claim is still true for that read, and L14 re-walks). |
| 4 | Can any supported caller reintroduce a pre-L14 execution path? | The gate and L1 reach one P whose leaf set has no process-creation leaf; the genuine run ports lose `resolve_runtime_identity`; no CFG1 module imports `ar2.launch.resolve_runtime_identity`; L2–L13 contain no Node/Pi launch (L3 runs the AIDO-authored Python fixture verification and Git, both frozen and unchanged). Offline doubles are refused against the genuine package root (CFG1-IMPL-FU1 guard). Tests AA, AB, AF. A **launcher** could run Pi itself outside AIDO — that is outside the audited lineage and would be caught by G4/G5 only if it is in the launcher's bytes; the authorization review (barrier item 8) must check that no launcher line executes Node or Pi. |
| 5 | Does removal of the probe accidentally bypass seam verification? | No. The seam proof never depended on the probe: complete 20-file walks remain at P2 (gate), P2 (L1) and L14 (a). The only probe-dependent seam activity removed is P4's post-probe re-walk, which existed only because the probe could have edited seams. |
| 6 | Can the gate and L1 disagree because they use different proof implementations? | No: the same function object with the same genuine leaves (R6 §4, Test L). They disagree only when the filesystem changed in between — the intended Test I behavior. |
| 7 | Can a later caller mistake static package identity for runtime observation? | Minimized by construction: no v2 field, identity-object attribute, or console code named `observed`, `reported`, or `version` exists (§7.2, §10); R-S1 forbids the old keys in v2; `PINNED_PI_VERSION` is not serialized (§7.4); archived v1 `pi_observed_version` keeps v1 meaning and must not be compared with any v2 fact as if they measured the same thing. |
| 8 | Does any v2 validator mode become unreachable or ambiguous? | No (§8.3): all three codes are reachable, R-S3's conjunction has one meaning, R-S4 no longer needs `U` because no L1 path can execute Pi code, and R6's three dispatch modes are untouched. No rule refers to a probe or execution event. |
| 9 | Does moving executability detection to L14 create any new cleanup or secret-lifecycle requirement? | No new **kind**: every resource reached before L14/L15 already carries frozen closure obligations for an L14/L15 refusal (L21-if-process, L23, L24 identity-bound scrubs, L27). New **frequency** only; it raises OC-4's practical importance (barrier item 4, unchanged order). No secret is held longer than in any run that reaches L14 today. |
| 10 | Does any frozen test/contract require Node-direct `--version` specifically for authority rather than diagnostics? | No. AR0 U-1 concerns the **launch shape** (Node-direct vs `cmd.exe` shim) and is preserved at L14. CFG1 §16.2 L1's `--version` listing is amended here by name (AMD-1). CFG1 §14.1 item 2 requires "Pi 0.85.1 with the §14.2 digests", which the digest proof satisfies. The shipped CFG1 tests that touch `pi_observed_version` (`tests/cfg1_builders.py`, `test_cfg1_containment.py`, `test_cfg1_emission_phases.py`) exercise **v1** payloads and remain v1 tests; AR2's own tests of `resolve_runtime_identity` are untouched. |

### 18.2 Round 2 — adversarial self-review of this amendment

1. *"Dropping P2R's seam re-walk weakens B11."* **Rejected, with reasoning on
   the record (§5.2).** B11 protected an execution; the execution moved to L14,
   and L14 (a) is a complete, uncached re-walk placed nearer the use than R4's
   P2R ever was. The only thing lost is detecting a seam edit made in the
   milliseconds between P2 and P's return at L1 rather than at L14 — the same
   edit made one millisecond later is caught identically. Kept honest by Test V
   (retargeted) and Test P.
2. *"`S == true` on a drift refusal reads as 'Pi proven'."* `S`'s meaning is
   unchanged since R4 ("the last completed walk matched"); `F ≠ null`
   dominates and R-S2 binds the pair. Changing `S`'s meaning for one case would
   reopen B14. Accepted as is.
3. *"The durable record cannot tell a drifted tree from a broken `node.exe` at
   L14."* True (§9); identical to R6; both fail closed with identical closure.
   No field added — the smaller schema is kept, as R6 decided for P's progress.
   If the reviewer wants the distinction, a console-only code is the minimal
   form; this amendment does not add one.
4. *"L15 absorbs start-up failures the reviewer expected at L14."* Stated
   precisely in §9 and §13 instead of forcing them into `RUNTIME_LAUNCH_FAILED`;
   changing L14/L15 semantics would amend the frozen supervisor contract, which
   this amendment does not do. Test AD (ii) pins it.
5. *"Passing a non-`RuntimeIdentity` to `build_pi_argv` relies on duck typing."*
   It relies on the frozen function's two attribute reads, pinned by Test AG
   with a stop-and-return rule. The alternative — constructing
   `RuntimeIdentity` — would require a `reported_version` value, which is
   exactly the misleading claim item 10 forbids.
6. *"The gate's network statement overclaims."* It does not: §12.3 states only
   that P itself creates no socket and issues no network protocol request, and
   expressly makes no claim about OS-level filesystem/redirector I/O. No
   detector is added.
7. *"The tripwire can be bypassed by `ctypes`."* Yes for the dynamic tripwire,
   which is why Test AA adds a static AST audit of the P/gate/leaf modules.
   Neither claims anything about a same-user process outside AIDO.
8. *"The gate's value shrinks."* It still catches the D1 class (a different Pi
   release installed — its `package.json` fails the seam proof) and any
   resolution or identity problem before consumption. Launchability was its
   only lost signal.
9. *"`PINNED_PI_VERSION` becomes dead."* It has no runtime consumer; it remains
   a design literal and is forbidden from any observation-implying use (§7.4).
   Not removing it avoids churn in a shipped module that nothing requires.
10. *"R6 §9.2c-D's `P3/P4/P5` labels could be read as superseded."* Explicitly
    excluded by the citation convention at the top; the provenance chain is
    preserved in full (§4).
11. *"No clause was left normative that mentions the probe."* §3 names every
    R6 clause and line range found to depend on P3/P4/P5, the probe child,
    `SystemRoot`, `reported_version`, `pi_observed_version` (v2), or D-6/OC-3;
    §17 restates the prose ones. R6's historical self-review sections are
    non-normative (§0 item 3).

---

## 19. Remaining blockers after this amendment

1. **Reviewer acceptance / freeze of this amendment** (R6 §17 item 1 as
   restated in §17; also discharges item 2 as restated).
2. **FU1 implementation** — one offline phase under R6 + AMEND1 — and its
   independent review/freeze (item 3), including Tests AA–AG and the
   retargeted U/V.
3. **OC-4** closure totality (item 4) — now exercised by a larger class of
   refusals (§13).
4. **OC-5** L3 exact-type correction (item 5).
5. **Operator restores the approved Pi 0.85.1 environment** (item 6), outside
   AIDO.
6. **Read-only, static pre-A4 identity/seam verification passes** (item 7) —
   executing no Node or Pi.
7. **A new A4 authorization** separately reviewed and accepted (item 8), whose
   launcher reads only `PATH` for the gate and executes no Node or Pi itself.

Not blockers, stated: **OC-2** (runtime residual from L14); **OC-6** (AR2 live
execution remains NO-GO); OC-7 (Git resolution, unchanged). **OC-3** is closed
by removal upon acceptance of this amendment.

---

## Status

```text
5F3B-HARNESS-CFG1-L1-BOUNDARY-FU1-OC3-AMEND1-DESIGN   CANDIDATE — PENDING REVIEW
Base: FU1-DESIGN-R6 (ACCEPTED/FROZEN; SHA-256 f9287e89…58bd0; blob c5d2f86e…d6ff) — NOT EDITED
OC-3 archaeology: ACCEPTED, OC2_PREVENTS_OC3_PROOF
AMD-1  P is a pure static proof: P0 (PATH only) → P1 → P2 → P2R → result; no process, ever
AMD-2  P2R = final identity-consistency re-proof (root vs Iᵣ, node.exe vs Iₙ); no seam re-walk
AMD-3  identity/version child environment RETIRED; AM-2 WITHDRAWN; L12 runtime env untouched
AMD-4  v2: pi_observed_version ABSENT; pi_version_probe_attempted ABSENT; no replacement field;
       pi_identity_failure_code ∈ {PI_RESOLUTION_FAILED, PI_SEAM_UNPROVEN,
                                   PI_IDENTITY_DRIFTED_DURING_PROOF}
AMD-5  validator R-S1…R-S6 replace R-P1…R-P6
AMD-6  FIRST Node/Pi/JavaScript execution = L14 launch(), after full re-proof
       (20 seams → root identity → node.exe identity); CFG1 static identity object, no version
AMD-7  gate reads PATH only
AMD-8  temporal trade NAMED: executability learned at L14/L15, after consumption and L4
OC-3 CLOSED BY REMOVAL (on acceptance).  D-6 WITHDRAWN.  OC-2 OPEN as L14 runtime residual.
v1 archived semantics UNCHANGED.  CFG1-S1-A3 CONSUMED.  A4 / Stage 2 NOT AUTHORIZED.
NO IMPLEMENTATION AUTHORITY GRANTED.
```
