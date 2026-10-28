# DL-4B E-12 — Operator Execution Runbook

**Status: PREP FU2 — UNDER CORRECTIVE REVIEW, NOT AUTHORIZED TO RUN.** Execute
only after every gating condition and decision in
`DL4B_E12_ISOLATION_REHEARSAL_PREP.md` §9–§10 is signed (including FU2
acceptance). Record outcomes in `DL4B_E12_EVIDENCE_MATRIX.md`.

Read `DL4B_E12_ISOLATION_REHEARSAL_PREP.md` first, especially §5.0 (the
measurement contract), §3.1–§3.3 (the five-root topology, the per-exercise
clones, and the hostile-program launch order) and §1 (the authenticator
boundary). This runbook assigns **every action to exactly one identity**: **A**
(`aido-a-rehearsal`), **X-R** (throwaway `aido-x-rehearsal`), **O** (the human),
or **admin** (elevated, one-off provisioning). Each identity works in its **own
logon session**. `runas` / `Start-Process -Credential` / cross-desktop launches
are **forbidden** (FD-13).

**Shell.** Every operator command here is **Windows `cmd.exe`**. PowerShell is
**not required** anywhere; where a wall-clock measurement is wanted, time the
command with the surrounding `echo %TIME%` lines shown, not `Measure-Command`.
A runs only `python -I …` (the frozen driver, and the standard-library
measurement helper); A runs **no** repository code, Git, model or network
client. `<PY>` below is the venv interpreter `C:\AIDO\venv\Scripts\python.exe`.

**The five mutually disjoint roots (FD-16 `BoundaryPaths._disjoint`).** All
declared in the rehearsal `identity-boundary.v1`; none may equal, contain or be
contained by another. There is **no nested layout** (`published\` / `inbox\` /
`exchange\` are **not** under `<state_root>` — that was the FU1 error):

| Placeholder | Root | Measured as |
|---|---|---|
| `<state_root>` | the store + evidence (`control-plane.sqlite3`, `aido-state-root.json`, `evidence\verification\`, `staging\`) | `tree` + `allowlist-state.txt` |
| `<published>` | A's `driver-<nnn>-<verb>.json` reports (O reads) | `tree` + `allowlist-published.txt` |
| `<inbox>` | O-placed `alpha-definition.json`, `attestation-*.json`, the two O-named docs | `tree` + `allowlist-inbox.txt` |
| `<exchange_root>` | `handoff-<ticket>\` (write-once) and `outbox-<ticket>\` (claim channel) | `tree --exchange` + `allowlist-exchange.txt` |
| `<clone>` | the per-exercise synthetic repo (`<clone_iso>`, `<clone_harness>`, `<clone_s7>`) | `git` (`.git` control set) |

Each exercise binds its **own** disposable clone into `identity-boundary.v1`
(the admin re-provisions the boundary's `clone` and re-binds the digest between
exercises). The four A-owned plane roots are provisioned once and reused. The
hostile program is `<hostile.exe>`, **outside** every clone. The adversary's
markers go under `<xr_scratch>` (X-R-owned, **outside all five roots**).

The measurement helper is `%USERPROFILE%\aido-e12\e12_measure.py` (Appendix M),
saved and reviewed before E-12; manifests, compares and the five allowlists live
under `%USERPROFILE%\aido-e12\`. All measurement output stays in A's area,
**never** in any root or clone.

---

## Phase 0 — provisioning (admin, elevated, once)

| # | Who | Action | Confirms |
|---|---|---|---|
| 0.1 | admin | Confirm host policy allows local standard accounts, (if S4U) "log on as a batch job", and user switching. If not, **STOP — E-12 is blocked (D-17)** | `PRECOND-POLICY` |
| 0.2 | admin | Create standard accounts `aido-a-rehearsal`, `aido-x-rehearsal` (throwaway), confirm O exists. None in `Administrators`/`Backup Operators` | `FD13-SIDS`, `FD13-GROUPS` |
| 0.3 | admin | Write `%ProgramData%\AIDO\identity-boundary.v1.json` (rehearsal SIDs + the five disjoint paths for the active clone) and `approver-registry.v1.json` at their code-constant paths; apply anchor ACLs (read-only to A/X-R/O) | `FD16-ANCHORS` |
| 0.4 | admin | Create the **four** A-owned plane roots `<state_root>` (empty, non-Git), `<published>`, `<inbox>`, `<exchange_root>` as **mutually disjoint sibling** directories; apply the per-root FD-14 protected DACLs (prep §3.1). `<state_root>` is left empty for `AidoStateRoot.create` | `FD14-STATEROOT-ACL`, `FD14-PUBLISHED-ACL`, `FD14-INBOX-ACL`, `FD14-EXCHANGE-ACL` |
| 0.5 | X-R | `git clone` each exercise's synthetic repo into `<clone_iso>` / `<clone_harness>` / `<clone_s7>`, checkout **detached** at `base_head_oid`; confirm no hooks, no submodules. Each has its own write target + preimage-bound artifact | `HARNESS-DETACHED-SETUP` |
| 0.6 | admin | Apply the clone ACLs (prep §3.2) to each clone: working tree X-R-modify + `OWNER RIGHTS`; `.git` X-R read+execute only via `OWNER RIGHTS`; root no DELETE/`WRITE_DAC`/`WRITE_OWNER` for X-R. **Before any harness runs** | `FD14-CLONE-ACL`, `HARNESS-OWNER` |
| 0.7 | admin | Provision A's launch: A's interactive session via secure logon UI, **or** an S4U task (no stored password, fixed `python -I` action, O granted run only) | `FD13-LAUNCH` |
| 0.8 | admin | Create `<xr_scratch>` (X-R-owned), **outside all five roots**, for the adversary's markers and log | — |

A one-off AuthZ effective-rights spot check per FD-14 object (for X-R's SID) may
be run here by admin to pre-confirm `FD14-EFFECTIVE`.

> **Boundary re-provisioning between exercises.** `identity-boundary.v1` names
> exactly **one** `clone`. Before ISO, bind `<clone_iso>` and its digest; before
> HARNESS, re-bind `<clone_harness>`; before S7, re-bind `<clone_s7>`. The four
> plane roots do not change. This is an admin action; AIDO never rewrites the
> boundary.

---

## Phase 1 — Exercise ISO (adversarial isolation core), on `<clone_iso>`

**Order is load-bearing (prep §3.3).** The frozen verifier launches its
configured executable **only after** proving the approved post-image. So the
approved **write** (X1) must precede the hostile **verify** (X2); otherwise the
verifier refuses before launch and the adversary never runs.

### A1 (A) — open and prove

In A's session, `cmd.exe`, isolated:

```bat
"C:\AIDO\venv\Scripts\python.exe" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" status > "<published>\driver-001-status.json"
```

Expect exit `0` and no `isolation_unproven` refusal → `ISO-PROOF-PRE` PASS.
(If it refuses `IsolationUnprovenError:<category>`, provisioning is wrong — fix
as admin and re-run; do not proceed.)

### A2 (A) — time the proof

Repeat A1 a few times capturing wall time in `cmd.exe` (no PowerShell): bracket
the line with `echo` of the clock and subtract.

```bat
echo START %TIME%
"<PY>" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" status > "<published>\driver-001b-status.json"
echo END   %TIME%
```

Record seconds → `S7-DURATION`. (Offline a hold-stage `status` is ~10 s; measure
here.)

### A3 (A) — pre-rehearsal manifests (five roots)

Take the manifests with the helper (Appendix M), run with `python -I` so the
script directory and user site are off `sys.path`. A reads its own plane roots,
the clone `.git` (read), and the anchors (read); operator measurement tool, not
shipped code (F-E12-3):

```bat
if not exist "%USERPROFILE%\aido-e12" mkdir "%USERPROFILE%\aido-e12"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<state_root>"                > "%USERPROFILE%\aido-e12\state-pre.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<published>"                 > "%USERPROFILE%\aido-e12\pub-pre.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<inbox>"                     > "%USERPROFILE%\aido-e12\inbox-pre.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<exchange_root>" --exchange  > "%USERPROFILE%\aido-e12\exch-pre.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" git  "<clone_iso>"                 > "%USERPROFILE%\aido-e12\git-pre.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "%ProgramData%\AIDO"          > "%USERPROFILE%\aido-e12\anchors-pre.txt"
```

The `tree` mode records `(relative path, size, nlink, reparse-flag, SHA-256)`;
`--exchange` on `<exchange_root>` prunes **only** a top-level directory matching
`^outbox-[0-9a-f]{32}$` (the claim channel X-R legitimately writes). →
`ISO-DIGEST-PRE` recorded.

### X1 (X-R) — apply the approved write (so the verify can launch)

In X-R's session, fresh `cmd.exe`, **no** reviewer variables. Apply the ISO
clone's approved single-file `modify` with the frozen writer:

```bat
ai-dev-orchestrator l2-apply-approved-file-edit --project-config "<cfg_iso>" --approved-diff-proposal "<approved_diff_iso>" --apply-approved-plan --write-approved-file
```

Expect it applies the modify (no detached-HEAD or `.git`-permission refusal). The
working tree now holds exactly the approved post-image as a single `" M"` on the
pinned detached HEAD.

### X2 (X-R) — launch the adversary (hostile verify)

Fresh `cmd.exe`. Run `l2-verify-approved-file-edit` with the throwaway config
whose `controlled_verification` executable is `<hostile.exe>`, capturing the
report:

```bat
ai-dev-orchestrator l2-verify-approved-file-edit --project-config "<cfg_hostile>" --approved-diff-proposal "<approved_diff_iso>" --apply-approved-plan --verify-approved-file-edit > "<xr_scratch>\verify-report.json"
```

Because X1 established the approved state, the verifier's preflight **passes** and
it **launches** `<hostile.exe>`, which spawns a detached descendant that writes
`<xr_scratch>\hostile-start.txt`, `<xr_scratch>\descendant-start.txt` and (on
exit) `<xr_scratch>\descendant-end.txt` (monotonic epoch seconds), hammers the
attack set (prep §3.3) for the window (D-E12-8), and logs each attempt + Win32
result to `<xr_scratch>\hostile-log.txt`. Leave it running through Phase 2 and 3.

> **If the verifier returns `refused-before-execution`** (`execution.started ==
> false`), the hostile program **never launched** — ISO is **INVALID, not a
> pass** (prep §3.3; mandatory validation #8). Check X1 applied the write to the
> clone bound in `identity-boundary.v1`.

### Aadv (A) — confirm the adversary provably launched and ran

After the window, A confirms positive execution evidence (a digest alone cannot
satisfy ISO):

```bat
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" adversary "<xr_scratch>\verify-report.json" "<xr_scratch>" <D-E12-8-seconds>
```

Expect `PASS\tadversary-active-<n>s` → `ISO-ADVERSARY-LAUNCH` + `ISO-ADVERSARY-ACTIVE`.
A `FAIL` (`adversary-refused-before-launch`, `adversary-not-started`,
`missing-marker`, or active interval under the window) → STOP, ISO INVALID. O
also corroborates the descendant was live during the window (`tasklist` in O's
session).

### A3q (A) — quiescent isolation bracket (the literal §5.8.10 test)

With the descendant running and **A performing no lifecycle write**, wait the
D-E12-8 window, then re-manifest all five roots and `strict`-compare against the
A3 manifests. Only the adversary is active, so **every** manifest must be
byte-identical:

```bat
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<state_root>"                > "%USERPROFILE%\aido-e12\state-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<published>"                 > "%USERPROFILE%\aido-e12\pub-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<inbox>"                     > "%USERPROFILE%\aido-e12\inbox-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<exchange_root>" --exchange  > "%USERPROFILE%\aido-e12\exch-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" git  "<clone_iso>"                 > "%USERPROFILE%\aido-e12\git-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "%ProgramData%\AIDO"          > "%USERPROFILE%\aido-e12\anchors-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict "%USERPROFILE%\aido-e12\state-pre.txt"   "%USERPROFILE%\aido-e12\state-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict "%USERPROFILE%\aido-e12\pub-pre.txt"     "%USERPROFILE%\aido-e12\pub-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict "%USERPROFILE%\aido-e12\inbox-pre.txt"   "%USERPROFILE%\aido-e12\inbox-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict "%USERPROFILE%\aido-e12\exch-pre.txt"    "%USERPROFILE%\aido-e12\exch-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict "%USERPROFILE%\aido-e12\git-pre.txt"     "%USERPROFILE%\aido-e12\git-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict "%USERPROFILE%\aido-e12\anchors-pre.txt" "%USERPROFILE%\aido-e12\anchors-q.txt"
```

In the quiescent bracket A writes nothing, so **every** root is compared with
`strict` (byte-identical). Each prints `PASS` or `DIFF…`+`FAIL` and sets
`ERRORLEVEL`. **All six `PASS`** → `ISO-DIGEST-Q` PASS. Any `FAIL` → STOP, Alpha
blocked (E-10): no retry, repair or cleanup.

---

## Phase 2 — Exercise HARNESS (detached HEAD + read-only `.git`), standalone on `<clone_harness>`, no signing

HARNESS is an **explicit standalone, signing-free** exercise (prep §4, §5 step 8):
a writer+verifier compatibility run that reaches a `verified` outcome on its own
clone. It does **not** depend on S7 or `PRECOND-SIGNING`.

> **No double-write.** A `modify` write is pinned to `pre_image_sha256`.
> `<clone_harness>` has its **own** preimage-bound artifact and a write target
> **distinct** from `<clone_iso>` (X1) and `<clone_s7>` (X4). Re-provision
> `identity-boundary.v1` to bind `<clone_harness>` before this phase.

### X2h (X-R) — writer, then benign verifier → `verified`

In X-R's session, fresh `cmd.exe`, run the frozen writer against the detached,
`.git`-read-only `<clone_harness>`, then the verifier with a **benign**
`controlled_verification` executable that exits 0:

```bat
ai-dev-orchestrator l2-apply-approved-file-edit --project-config "<cfg_benign_harness>" --approved-diff-proposal "<approved_diff_harness>" --apply-approved-plan --write-approved-file
ai-dev-orchestrator l2-verify-approved-file-edit --project-config "<cfg_benign_harness>" --approved-diff-proposal "<approved_diff_harness>" --apply-approved-plan --verify-approved-file-edit > "%USERPROFILE%\aido-e12\harness-verify.json"
```

Expect: the writer applies the modify without a detached-HEAD or
`.git`-permission refusal (`HARNESS-WRITE-DETACHED` PASS), and the verifier's
report shows **`"outcome": "verified"`** (`HARNESS-VERIFY-DETACHED` PASS) —
proving the read-only Git preflight accepted the detached HEAD and the read-only
`.git` end to end. **Any refusal on detached-HEAD or `.git`-permission grounds,
or an outcome that is not `verified`, → STOP, Alpha blocked (E-10).** This is the
authoritative writer+verifier compatibility evidence; ISO's X1/X2 corroborate the
same preflight under an adversarial executable.

---

## Phase 3 — Exercise S7 (driver integration measurements), on `<clone_s7>`

Run the real driver against the A-owned plane with a benign approved definition;
the write-scope config points at `<hostile.exe>` so the VERIFYING X-step also
feeds ISO's descendant. (The approvals reuse the S7 operator runbook procedure;
here we note only the E-12-specific observations.) Re-provision
`identity-boundary.v1` to bind `<clone_s7>` before this phase.

> **Phase 3 gate — `PRECOND-SIGNING` (D-E12-9).** Phase 3 needs three **real,
> S1-verified** approvals, so it runs **only** if the signing capability
> (authenticator, OpenSSH `sk`, throwaway registry entry) is provisioned and
> D-E12-9 is signed. There is no fabricated-signature or bypass path. If
> `PRECOND-SIGNING` is not met, **skip Phase 3 entirely** and record every §9
> matrix row `NOT TESTED` (reason `no-signing`). ISO (Phase 1) and HARNESS
> (Phase 2) have already covered the isolation core and the writer/verifier
> compatibility without it. This signing is **not** E-6 and does not satisfy it
> (prep §1, §8); E-12 still calls **no model**.

### A4 (O → A) — approvals, each redirected to `published/`

Walk `request-approval` / `record-approval` for contract, plan activation and
exact-diff. **O signs each challenge with the real authenticator in O's own
session** (`alpha_operator` + `ssh-keygen -Y sign`, per
`DL4B_S7_OPERATOR_RUNBOOK.md` §2); A never signs and never sees a private key.
Each A invocation:

```bat
"C:\AIDO\venv\Scripts\python.exe" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" <verb> > "<published>\driver-<nnn>-<verb>.json"
```

→ confirm each file is created under `<published>` and readable by O
(`S7-PUBLISHED-ACL`); time them (`S7-DURATION`).

### A5 (A) — the long `run`

```bat
"C:\AIDO\venv\Scripts\python.exe" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" run > "<published>\driver-012-run.json"
```

`run` announces the **write** step, flushes it, then waits (up to 7200 s).

- **O:** open `<published>\driver-012-run.json` **now**; confirm the write
  announcement is present while `run` still blocks → `S7-ANNOUNCE-WRITE`. Treat
  the file as a **stream of JSON documents split on the blank line**; read the
  **last** document (F-E12-1).
- **A (second console):** start another `alpha_driver` invocation; expect
  `StoreLockedError` → `S7-LOCK`.

### X4 (X-R) — the write X-step

Fresh `cmd.exe`, **no** reviewer variables. Run the two lines the announcement
printed (frozen writer against `<clone_s7>`, then the marker), exactly as
printed:

```bat
ai-dev-orchestrator l2-apply-approved-file-edit --project-config "...\project.yaml" --approved-diff-proposal "...\approved-diff-proposal.json" --apply-approved-plan --write-approved-file > "<exchange_root>\outbox-<ticket>\stdout.json"
type nul > "<exchange_root>\outbox-<ticket>\complete"
```

Create `complete` **only after** the command exits, whatever its exit code. Put
**nothing else** in the outbox. A continues: M1, `IMPLEMENTATION_RETURNED`, then
announces the **verify** step → `S7-ANNOUNCE-VERIFY` (O re-reads the growing
file). M1 shows exactly the target changed, `.git` unchanged → `FD18-M1`.

### X5 (X-R) — the verify X-step (substitution, D-E12-3)

Fresh `cmd.exe`. Run `l2-verify-approved-file-edit` with `<cfg_hostile>`,
redirect to the outbox, then `complete`:

```bat
ai-dev-orchestrator l2-verify-approved-file-edit --project-config "<cfg_hostile>" --approved-diff-proposal "...\approved-diff-proposal.json" --apply-approved-plan --verify-approved-file-edit > "<exchange_root>\outbox-<ticket>\stdout.json"
type nul > "<exchange_root>\outbox-<ticket>\complete"
```

The bare verified `verification-result.v1` is **not** a `ReviewPacket`, so A
classifies "anything else" → **RECOVERY_REQUIRED**. `run` returns exit **3** →
`S7-VERIFY-RECOVER` PASS (this is expected).

### Spot-check deviations (X-R, disposable outbox) — optional but recommended

- Add an extra file beside `stdout.json`+`complete` → `claim_refused:unexpected_entry` → `FD17-UNEXPECTED`.
- Plant a junction named `stdout.json` → `claim_refused:reparse_point` → `FD17-REPARSE`.
- Plant a junction inside the working tree, re-drive M1 → `ObservationError:reparse_point` → `FD18-REPARSE`.

---

## Phase 4 — close and verify (A, then admin)

### A6 (A) — post-rehearsal proof and accountable compare

After the rehearsal window (D-E12-8), with the hostile descendant still having
run:

```bat
"<PY>" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" status > "<published>\driver-099-status.json"
```

Expect exit `0`, no `isolation_unproven` → `ISO-PROOF-POST` PASS. Then re-take
the six manifests and compare. Anchors and `.git` are `strict` (byte-identical
required, because S7's legitimate writes never touch them); each A-owned plane
root is `classify` against its own expected-name allowlist (Appendix M), because
S7 legitimately grew A-owned regions:

```bat
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<state_root>"                > "%USERPROFILE%\aido-e12\state-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<published>"                 > "%USERPROFILE%\aido-e12\pub-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<inbox>"                     > "%USERPROFILE%\aido-e12\inbox-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<exchange_root>" --exchange  > "%USERPROFILE%\aido-e12\exch-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" git  "<clone_s7>"                  > "%USERPROFILE%\aido-e12\git-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "%ProgramData%\AIDO"          > "%USERPROFILE%\aido-e12\anchors-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict   "%USERPROFILE%\aido-e12\anchors-pre.txt" "%USERPROFILE%\aido-e12\anchors-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict   "%USERPROFILE%\aido-e12\git-pre.txt"     "%USERPROFILE%\aido-e12\git-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" classify "%USERPROFILE%\aido-e12\state-pre.txt"   "%USERPROFILE%\aido-e12\state-post.txt" "%USERPROFILE%\aido-e12\allowlist-state.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" classify "%USERPROFILE%\aido-e12\pub-pre.txt"     "%USERPROFILE%\aido-e12\pub-post.txt"   "%USERPROFILE%\aido-e12\allowlist-published.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" classify "%USERPROFILE%\aido-e12\inbox-pre.txt"   "%USERPROFILE%\aido-e12\inbox-post.txt" "%USERPROFILE%\aido-e12\allowlist-inbox.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" classify "%USERPROFILE%\aido-e12\exch-pre.txt"    "%USERPROFILE%\aido-e12\exch-post.txt"  "%USERPROFILE%\aido-e12\allowlist-exchange.txt"
```

> **If Phase 3 was skipped (`no-signing`)**, use the quiescent-bracket manifests
> as the post manifests (A wrote nothing after ISO), so every compare above is
> also `strict`-clean. The S7-specific rows are `NOT TESTED`, not PASS.

`ISO-DIGEST-POST` PASS requires **every** compare to print `PASS`
(`ERRORLEVEL 0`): no anchor or `.git` byte changed, and no `classify` run found a
write-once rewrite, a deletion, an unexpected-name object, a reparse point, or a
hard link. **Any `FAIL` line → FAIL, Alpha blocked** (E-10; no retry, repair or
cleanup). The hostile log is read for diagnosis only and is never authority-plane
evidence.

### A7 (A) — induced negatives (one each, to confirm detection is live)

- Have admin add a `Users:(R)` allow ACE to one state-root object, re-run
  `status`; expect `isolation_unproven:object_unprotected` (or `object_rights`)
  and exit 1 → `FD16-NEG`. Revert.
- (FD-17/FD-18 negatives above already recorded.)

### Z (admin) — teardown

Collect the hostile log (diagnostic only), archive the throwaway roots and
digests, **disable/delete X-R**, and re-provision `identity-boundary.v1` with the
Alpha's fresh `X` **only when the Alpha itself is authorized** (not as part of
E-12 teardown unless AUTH-PILOT says so).

---

## What must never happen during E-12

- **No model call, in any exercise.** No reviewer endpoint or credential variable
  in any console: E-12 has no review console at all. (Real approval *signing* in
  O's session under `PRECOND-SIGNING` is permitted and is **not** a model call.)
- No fabricated signature, no bypass of S1 approval verification, no store
  weakening, and no edit to accepted code — if S7 cannot be signed, its rows are
  `NOT TESTED`, never forced PASS, and the verdict never claims HARNESS or S7
  coverage from an exercise that did not run.
- No real target repository, no real credential value, no branch/commit/push/PR.
- No hostile `verify` without the approved write first — a `refused-before-execution`
  result means the adversary never launched and ISO is INVALID, not a pass.
- No `git restore`, retry, repair or cleanup of a RECOVERY_REQUIRED attempt, or of
  any `FAIL` digest/compare (E-10): the S7 run ending exit 3 is the expected end
  of the exercise; a measurement `FAIL` ends E-12 and blocks the Alpha.
- No hand-written `stdout.json`. If a command cannot run, do nothing and let the
  wait expire.
- No elevation of A or X-R; the boundary proof refuses an elevated token.
- No measurement output or adversary marker written into any of the five roots;
  keep A's measurement in `%USERPROFILE%\aido-e12\` and the markers in
  `<xr_scratch>`.

---

## Appendix M — the measurement helper and allowlists (operator-saved, reviewed)

`e12_measure.py` is **not shipped AIDO code and not committed as a module**
(prep F-E12-3). The operator saves it to `%USERPROFILE%\aido-e12\e12_measure.py`,
reviews it like the hostile program, and A runs it only with `python -I`. It is
pure standard library; it imports nothing from the measured trees, executes
nothing, and opens no socket. Owner/DACL are **not** read here — that dimension
is covered by `ISO-PROOF-PRE/-POST` and the admin `icacls`/AuthZ dump. The rules
are keyed to the frozen object names, and the only transient tolerated inside the
state root is `control-plane.sqlite3-journal` (there is no WAL —
`PRAGMA locking_mode = EXCLUSIVE`).

```python
# e12_measure.py — E-12 rehearsal measurement helper (operator tool, not AIDO code).
# Run by A as: "<PY>" -I e12_measure.py <tree|git|strict|classify|adversary> ...
import hashlib
import json
import os
import re
import stat
import sys

_REPARSE = 0x400
_GIT_TOP = ("HEAD", "config", "index", "packed-refs")
_GIT_DIRS = ("refs", "hooks", "info")
_TICKET = "[0-9a-f]{32}"
_OUTBOX_DIR = re.compile(r"^outbox-[0-9a-f]{32}$")


def _is_reparse(path):
    info = os.lstat(path)
    return (
        os.path.islink(path)
        or getattr(os.path, "isjunction", lambda _p: False)(path)
        or bool(getattr(info, "st_file_attributes", 0) & _REPARSE)
    )


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_line(rel, path):
    info = os.lstat(path)
    if _is_reparse(path):
        return "%s\t0\t1\tREPARSE\t-" % rel
    return "%s\t%d\t%d\t-\t%s" % (rel, info.st_size, info.st_nlink, _sha256(path))


def _dir_line(rel, path):
    if _is_reparse(path):
        return "%s/\t0\t0\tREPARSE\t-" % rel
    return "%s/\t0\t0\tDIR\t-" % rel


def tree(root, exchange=False):
    root = os.path.abspath(root)
    if not os.path.isdir(root) or _is_reparse(root):
        sys.stderr.write("root is missing or a reparse point: %s\n" % root)
        raise SystemExit(2)
    lines = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
        # Prune the claim channel ONLY at the top level of exchange_root, and
        # ONLY when its name matches outbox-<32hex> exactly.
        if exchange and rel_dir == ".":
            dirnames[:] = [d for d in dirnames if not _OUTBOX_DIR.match(d)]
        kept = []
        for d in sorted(dirnames):
            rel = d if rel_dir == "." else "%s/%s" % (rel_dir, d)
            p = os.path.join(dirpath, d)
            lines.append(_dir_line(rel, p))
            if _is_reparse(p):          # record but do not descend
                continue
            kept.append(d)
        dirnames[:] = kept
        for f in sorted(filenames):
            rel = f if rel_dir == "." else "%s/%s" % (rel_dir, f)
            lines.append(_file_line(rel, os.path.join(dirpath, f)))
    sys.stdout.write("\n".join(sorted(lines)) + ("\n" if lines else ""))
    return 0


def git(clone):
    gitdir = os.path.join(os.path.abspath(clone), ".git")
    if not os.path.isdir(gitdir) or _is_reparse(gitdir):
        sys.stderr.write(".git is missing or a reparse point: %s\n" % gitdir)
        raise SystemExit(2)
    lines = []
    for name in _GIT_TOP:
        p = os.path.join(gitdir, name)
        if os.path.exists(p):
            lines.append(_file_line(name, p))
    for sub in _GIT_DIRS:
        base = os.path.join(gitdir, sub)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames.sort()
            for f in sorted(filenames):
                rel = os.path.relpath(os.path.join(dirpath, f), gitdir).replace("\\", "/")
                lines.append(_file_line(rel, os.path.join(dirpath, f)))
    lines.append("modules/\tPRESENT" if os.path.isdir(os.path.join(gitdir, "modules"))
                 else "modules/\tABSENT")
    sys.stdout.write("\n".join(sorted(lines)) + "\n")
    return 0


def _load(path):
    out = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            rel = line.split("\t", 1)[0]
            out[rel] = line
    return out


def strict(a, b):
    ma, mb = _load(a), _load(b)
    findings = []
    for rel in sorted(set(ma) | set(mb)):
        if ma.get(rel) != mb.get(rel):
            findings.append("DIFF\t%s" % rel)
    if findings:
        sys.stdout.write("\n".join(findings) + "\nFAIL\n")
        return 1
    sys.stdout.write("PASS\n")
    return 0


def _compile(glob):
    # '*' does NOT span '/', '**' spans, '<ticket>' is 32 lowercase hex.
    out, i = ["^"], 0
    while i < len(glob):
        if glob.startswith("<ticket>", i):
            out.append(_TICKET)
            i += len("<ticket>")
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def _rules(path):
    rules = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            kind, glob = line.split(None, 1)
            if kind not in ("S", "W", "G"):
                raise SystemExit("bad allowlist rule kind: %r" % kind)
            rules.append((kind, _compile(glob)))
    return rules


def _match(rel, rules):
    for kind, rx in rules:
        if rx.match(rel):
            return kind
    return None


def classify(a, b, allowlist):
    ma, mb = _load(a), _load(b)
    rules = _rules(allowlist)
    findings = []
    for rel in sorted(mb):
        parts = mb[rel].split("\t")             # rel, size, nlink, flag, sha
        flag = parts[3]
        if flag == "REPARSE":
            findings.append("REPARSE\t%s" % rel)
            continue
        if flag == "-" and parts[2] != "1":     # a file; check hard links
            findings.append("HARDLINK\t%s" % rel)
            continue
        kind = _match(rel, rules)
        in_a = rel in ma
        changed = in_a and ma[rel] != mb[rel]
        if kind is None:
            if not in_a:
                findings.append("NEW-UNEXPECTED\t%s" % rel)
            elif changed:
                findings.append("CHANGED-UNEXPECTED\t%s" % rel)
            # unchanged baseline object with no rule: fine
        elif kind == "S":
            if not in_a or changed:
                findings.append("STRICT-VIOLATION\t%s" % rel)
        elif kind == "W":
            if in_a and changed:
                findings.append("WRITEONCE-REWRITE\t%s" % rel)
        # kind == 'G': new or changed both accepted
    for rel in sorted(ma):
        if rel in mb:
            continue
        kind = _match(rel, rules)
        if kind in (None, "S", "W"):
            findings.append("DELETED\t%s" % rel)
        # kind == 'G': transient object may vanish
    if findings:
        sys.stdout.write("\n".join(findings) + "\nFAIL\n")
        return 1
    sys.stdout.write("PASS\n")
    return 0


def adversary(report_path, markers_dir, min_seconds):
    min_seconds = float(min_seconds)
    try:
        with open(report_path, "r", encoding="utf-8") as handle:
            report = json.load(handle)
    except (OSError, ValueError):
        sys.stdout.write("FAIL\tadversary-report-unreadable\n")
        return 1
    # A pre-launch refusal (exit 1 / refused-before-execution) never launched the
    # configured executable, so it can NEVER be counted as the adversary having
    # run (mandatory validation #8).
    outcome = report.get("outcome")
    started = bool(report.get("execution", {}).get("started"))
    if outcome == "refused-before-execution" or report.get("category") == "refused-before-execution":
        sys.stdout.write("FAIL\tadversary-refused-before-launch\n")
        return 1
    if not started:
        sys.stdout.write("FAIL\tadversary-not-started\n")
        return 1
    stamps = {}
    for name in ("hostile-start.txt", "descendant-start.txt", "descendant-end.txt"):
        p = os.path.join(markers_dir, name)
        try:
            with open(p, "r", encoding="utf-8") as handle:
                stamps[name] = float(handle.read().strip())
        except (OSError, ValueError):
            sys.stdout.write("FAIL\tmissing-marker\t%s\n" % name)
            return 1
    active = stamps["descendant-end.txt"] - stamps["descendant-start.txt"]
    if active < min_seconds:
        sys.stdout.write("FAIL\tdescendant-active-%.1fs-under-%.1fs\n" % (active, min_seconds))
        return 1
    sys.stdout.write("PASS\tadversary-active-%.1fs\n" % active)
    return 0


def main(argv):
    if len(argv) < 2:
        raise SystemExit("usage: tree|git|strict|classify|adversary ...")
    mode = argv[1]
    if mode == "tree":
        return tree(argv[2], exchange=("--exchange" in argv[3:]))
    if mode == "git":
        return git(argv[2])
    if mode == "strict":
        return strict(argv[2], argv[3])
    if mode == "classify":
        return classify(argv[2], argv[3], argv[4])
    if mode == "adversary":
        return adversary(argv[2], argv[3], argv[4])
    raise SystemExit("unknown mode: %r" % mode)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

**Allowlists — one per A-owned plane root**, each enumerating that root's real
expected object names. `S` = strict immutable (must be byte-identical); `W` =
write-once (new allowed; rewrite or deletion FAIL); `G` = A-owned growth (new or
changed allowed). An object matching **no** rule is a `NEW-UNEXPECTED` /
`CHANGED-UNEXPECTED` FAIL even inside a broadly named root — that is the catch
that stops a malicious object being dismissed as legitimate. Add no rule that
would admit an X-R-writable name.

`allowlist-state.txt` (the frozen `AidoStateRoot` layout; no WAL):

```text
# <state_root> — the frozen AidoStateRoot layout
S aido-state-root.json
G control-plane.sqlite3
G control-plane.sqlite3-journal
W evidence/verification/*.json
G staging/*.partial
```

`allowlist-published.txt`:

```text
# <published> — A's cmd.exe-redirected driver reports (O reads)
G driver-*.json
```

`allowlist-inbox.txt` (O-placed documents; the two O-named docs use the names the
Alpha definition declares):

```text
# <inbox> — O-placed driver inputs
G alpha-definition.json
G attestation-project-contract.json
G attestation-plan-activation.json
G attestation-exact-diff-approval.json
G approved-diff-proposal.json
G project.yaml
```

`allowlist-exchange.txt` (the helper's `--exchange` already prunes
`outbox-<32hex>`; `<ticket>` expands to exactly 32 lowercase hex):

```text
# <exchange_root> — per-ticket handoff (write-once); outbox-<ticket> is excluded at manifest time
W handoff-<ticket>/
W handoff-<ticket>/approved-diff-proposal.json
W handoff-<ticket>/project.yaml
```

The helper's `*` does **not** span `/`, and `<ticket>` matches exactly
`[0-9a-f]{32}`, so `evidence/verification/*.json` covers only the blob files
there and a directory named `outbox-evil` (non-hex) is **not** excluded — it is
measured and, being unexpected, fails. Substitute the two O-named docs
(`approved_diff_name`, `project_config_name`) with the names the rehearsal's
`alpha-definition.json` actually declares.
