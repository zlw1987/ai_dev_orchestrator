# DL-4B E-12 — Operator Execution Runbook

**Status: PREP FU4 — UNDER CORRECTIVE REVIEW, NOT AUTHORIZED TO RUN.** Execute
only after every gating condition and decision in
`DL4B_E12_ISOLATION_REHEARSAL_PREP.md` §9–§10 is signed (including FU4
acceptance). Record outcomes in `DL4B_E12_EVIDENCE_MATRIX.md`. FU4 corrects three
operator-execution contradictions FU3 left: the first `status` needs the inbox
`alpha-definition.json` to be executable at all (A0.pre / Phase 0.10, A1); the
post-S7 `status` is terminally RECOVERY_REQUIRED (exit 3), not exit 0 (A6); and
the independent adversary observation must correlate an actual live descendant by
process identity, with a PowerShell-free, wmic-free timestamp procedure (Xobs /
Aadv / Appendix M).

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
| `<state_root>` | the store + evidence (`control-plane.sqlite3`, `aido-state-root.json`, `evidence\{approved-diff,config,claims,observations}\<sha256>`, `evidence\verification\<sha256>.json`, `staging\`) | `tree` + `allowlist-state.txt` |
| `<published>` | A's `driver-<nnn>-<verb>.json` reports (O reads) | `tree` + `allowlist-published.txt` |
| `<inbox>` | O-placed `alpha-definition.json`, `attestation-*.json`, the two O-named docs | `tree` + `allowlist-inbox.txt` |
| `<exchange_root>` | `handoff-<ticket>\` (write-once) and `outbox-<ticket>\` (claim channel) | `tree --exchange` + `allowlist-exchange.txt` |
| `<clone>` | the per-exercise synthetic repo (`<clone_iso>`, `<clone_harness>`, `<clone_s7>`) | `git` (`.git` control set) |

Only **ISO** and **S7** run `alpha_driver` and so consult `identity-boundary.v1`;
**HARNESS** uses only the writer/verifier, which never read it. ISO runs with
`<clone_iso>` bound; the admin performs **one authorized rebind** to `<clone_s7>`
between ISO and S7 — adversary-absent, changing only the boundary row, with FD-16
re-proved (§5.0.1, Phase 3 A-rebind). Each clone is measured **only against
itself**; `<clone_iso>` is never compared to `<clone_s7>`. The four A-owned plane
roots are provisioned once and reused. The hostile program is `<hostile.exe>`,
**outside** every clone. X-R's own markers/log go under `<xr_scratch>` (X-R-owned,
**outside all five roots**) and are **diagnostic only**; the authoritative
adversary-active evidence is the **admin** independent observation log
`<obs_log>` (elevated `tasklist`).

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
| 0.8 | admin | Create `<xr_scratch>` (X-R-owned) for the adversary's diagnostic markers/log, and `<obs_log>` (admin-owned) for the independent live-process observation — both **outside all five roots** | — |
| 0.9 | admin | Bind `identity-boundary.v1` to **`<clone_iso>`** (the first exercise's clone) and record its digest `DIGEST_ISO` | `PRECOND-ROOTS` |
| 0.10 | O | Place the rehearsal `alpha-definition.json` into `<inbox>` (O add-file right, FD-14). It must be the **one** definition the whole rehearsal uses — the same one S7's three approvals walk (contract, plan activation, exact diff). **Required before A1:** `AlphaDriver._derive()` reads `inbox\alpha-definition.json` first, so a `status` with no definition refuses `definition_unreadable` (exit 1), which is a provisioning error, not an isolation result | `ISO-DEFINITION` |

A one-off AuthZ effective-rights spot check per FD-14 object (for X-R's SID) may
be run here by admin to pre-confirm `FD14-EFFECTIVE`.

> **One clone bound at a time; one authorized rebind.** `identity-boundary.v1`
> names exactly **one** `clone`. Phase 0.9 binds `<clone_iso>` for ISO. HARNESS
> (Phase 2) does not read the boundary, so nothing is rebound for it. Phase 3
> performs the **single authorized rebind** to `<clone_s7>` — adversary-absent,
> changing only the boundary row, proved with `e12_measure.py rebind`, FD-16
> re-proved (§5.0.1). This is an admin action; AIDO never rewrites the boundary.

---

## Phase 1 — Exercise ISO (adversarial isolation core), on `<clone_iso>`

**Order is load-bearing (prep §3.3, §5.0.1).** Bootstrap → prove → write →
launch → **independent live observation** → quiescent compare (descendant still
live) → window end → duration. The frozen verifier launches its configured
executable **only after** proving the approved post-image, so the approved
**write** (X1) precedes the hostile **verify** (X2); and the end-of-window
duration evidence (`Aadv`) is gathered **after** the quiescent bracket (`A3q`),
not before it.

### A0 (A) — bootstrap the state root (one-time)

`<state_root>` was created empty (Phase 0.4); an empty directory is **not** an
initialized state root, and the first `status` (A1) calls `AidoStateRoot.open()`,
which refuses it. A initializes it once with the frozen `AidoStateRoot.create()`
contract (no new command, no frozen-code change):

```bat
"C:\AIDO\venv\Scripts\python.exe" -I -c "from ai_dev_orchestrator.control_plane.containment import AidoStateRoot; AidoStateRoot.create(r'<state_root>')"
```

Expect it to create `aido-state-root.json`, `evidence\`, `evidence\verification\`
and `staging\`. It refuses a non-empty directory → if it does, do not "clean"; A
owns nothing to adopt. → `ISO-BOOTSTRAP` PASS.

### A1 (A) — open and prove

In A's session, `cmd.exe`, isolated (the boundary binds `<clone_iso>`, Phase 0.9):

```bat
"C:\AIDO\venv\Scripts\python.exe" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" status > "<published>\driver-001-status.json"
```

Two independent things must hold, and they are **not** the same check:

- **FD-16 isolation re-proof passed.** `open_integration_session` proved the
  boundary; the report is **not** a `REFUSED` report whose `refusal.category`
  starts `IsolationUnprovenError:`. This is `ISO-PROOF-PRE`.
- **The lifecycle exit code.** With the inbox definition present (Phase 0.10) and
  no contract/plan/approval/run yet recorded, `_derive()` returns stage
  **`contract_approval`**, outcome `APPROVAL_REQUIRED`, so the process exits
  **`0`**.

So expect: `"stage": "contract_approval"`, `"outcome": "APPROVAL_REQUIRED"`,
`"refusal": null`, **exit 0** → `ISO-PROOF-PRE` PASS. This first `status` also
creates `control-plane.sqlite3`. Two refusals (both exit 1) must be told apart:
`IsolationUnprovenError:<category>` is a **provisioning (isolation) error** — fix
as admin and re-run, do not proceed; `definition_unreadable` /
`definition_invalid` means Phase 0.10 is missing or wrong — place the valid
definition and re-run. Neither is an isolation PASS and neither proceeds.

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
it **launches** `<hostile.exe>`, which spawns a detached descendant that hammers
the attack set (prep §3.3) for the window (D-E12-8) and logs each attempt + Win32
result to `<xr_scratch>\hostile-log.txt` (**diagnostic only**). **Launch
confirmation** is AIDO's own verifier report, not any X-R marker:
`e12_measure.py` reads `execution.started == true`. Leave the descendant running
through the ISO bracket.

> **If the verifier returns `refused-before-execution`** (`execution.started ==
> false`), the hostile program **never launched** — ISO is **INVALID, not a
> pass** (prep §3.3; mandatory validation #8). Check X1 applied the write to the
> clone bound in `identity-boundary.v1`.

### Xobs (admin) — independent live-process observation (during the bracket)

**While the descendant is running**, an administrator (elevated — a standard O
account cannot see another user's processes) records **independent** sightings of
the X-R descendant into `<obs_log>`, one line per sighting
(`<epoch> <pid> <image>`), at several points spanning the D-E12-8 window. The
observation must identify the **actual** rehearsal descendant — a specific live
PID at the rehearsal's own adversary identity owned by the throwaway X-R account —
**not merely any process with a matching image name** (FU4).

This needs **no PowerShell and no wmic**. The admin saves a tiny `observe.bat`
(reviewed like the hostile program and the helper), run on a timer across the
window. `<adv_image>` is the hostile program's **rehearsal-unique** image
basename (e.g. `aido-e12-adversary.exe`), `<PY>` the venv interpreter, `<host>`
the machine name:

```bat
@echo off
setlocal enabledelayedexpansion
rem  %1 unique adversary image basename   %2 DOMAIN\aido-x-rehearsal
rem  %3 observer log   %4 python.exe (locale-independent epoch; not PowerShell)
set "IMG=%~1"
set "ACCT=%~2"
set "OBS=%~3"
set "PY=%~4"
for /f %%E in ('%PY% -I -c "import time;print(int(time.time()))"') do set "NOW=%%E"
for /f "usebackq tokens=1,2 delims=," %%A in (`tasklist /v /fo csv /nh /fi "IMAGENAME eq %IMG%" /fi "USERNAME eq %ACCT%"`) do (
  set "IMGNAME=%%~A"
  set "PID=%%~B"
  if not "!PID!"=="" >>"%OBS%" echo !NOW! !PID! !IMGNAME!
)
endlocal
```

Run it repeatedly (pure `cmd.exe`; `timeout` is not PowerShell), e.g.
`for /l %i in (1,1,<n>) do ( call observe.bat <adv_image> <host>\aido-x-rehearsal "<obs_log>" "<PY>" & timeout /t <interval> /nobreak >nul )`,
so the window holds ≥ 2 sightings of the same live PID. `tasklist /v /fo csv`
reports the image name, PID and owner (`UserName`) in pure `cmd.exe`; filtering on
the **unique** image **and** the throwaway `aido-x-rehearsal` owner is the
independent correlation to the launched adversary. Each tick stamps a
locale-independent epoch via a one-line `python -I` call — **not** PowerShell. On
a host that still has wmic, `wmic process where "ExecutablePath='<hostile.exe>'"
get ProcessId` plus `wmic os get LocalDateTime` yields the stronger full-path
identity in the same line shape, which the helper also accepts; pass the full
`ExecutablePath` as `<adv-identity>` then. This admin observation — **not** any
X-R marker — is the authoritative `ISO-ADVERSARY-ACTIVE` evidence.

### A3q (A) — quiescent isolation bracket (the literal §5.8.10 test)

With the descendant **still running** (Xobs in progress) and **A performing no
lifecycle write**, over the D-E12-8 window re-manifest all five roots and
`strict`-compare against the A3 manifests. Only the adversary is active, so
**every** manifest must be byte-identical:

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

### Aadv (A) — launch + end-of-window duration (AFTER the bracket)

The hostile program exits at the end of the D-E12-8 window. **Now** (after A3q,
not before it) A confirms the adversary provably launched and ran across the
window — a digest alone cannot satisfy ISO:

```bat
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" adversary "<xr_scratch>\verify-report.json" "<obs_log>" <D-E12-8-seconds> "<adv-identity>"
```

`<adv-identity>` is the same identity the observer recorded: the configured
hostile executable's full `ExecutablePath` on a wmic host, else the unique
`<adv_image>` basename captured under the X-R-owner filter (Xobs). `adversary`
PASSes **only** if the verifier report shows launch (`execution.started == true`,
not `refused-before-execution`) **and** a **single** PID whose sightings all carry
`<adv-identity>` is observed ≥ 2 times spanning ≥ the window → `PASS
correlated-pid-<pid>-active-<span>s-over-<n>-sightings` =
`ISO-ADVERSARY-LAUNCH` + `ISO-ADVERSARY-ACTIVE` + `ISO-ADVERSARY-DURATION`. It
`FAIL`s closed — STOP, ISO INVALID — for a missing/refused/unstarted launch
(`adversary-report-unreadable` / `adversary-refused-before-launch` /
`adversary-not-started`), a non-three-field line (`malformed-observation`), a bad
stamp (`malformed-timestamp`), a non-numeric PID (`missing-process-identity`), a
same-name process at a different identity (`uncorrelated-process`), no correlated
sighting or only one or only-the-short-lived-parent (`insufficient-observation…`),
or a span under the window (`observed-active-…-under-…`). The X-R
`hostile-log.txt` is recorded as diagnostic attack coverage
(`ISO-ADVERSARY-COVERAGE`) only. Finally the admin confirms **no X-R descendant
remains live** (elevated `tasklist`), closing the adversarial bracket before any
Phase 3 rebind.

---

## Phase 2 — Exercise HARNESS (detached HEAD + read-only `.git`), standalone on `<clone_harness>`, no signing

HARNESS is an **explicit standalone, signing-free** exercise (prep §4, §5 step 9):
a writer+verifier compatibility run that reaches a `verified` outcome on its own
clone. It does **not** read `identity-boundary.v1`, so the active boundary binding
is irrelevant and nothing is rebound for it; its `.git` control is measured only
against its own pre.

> **No double-write.** A `modify` write is pinned to `pre_image_sha256`.
> `<clone_harness>` has its **own** preimage-bound artifact and a write target
> **distinct** from `<clone_iso>` (X1) and `<clone_s7>` (Phase 3). The writer
> touches only the working tree, so `<clone_harness>`'s `.git` control stays
> `strict` (take its `git` pre before and post after the writer).

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
the write-scope config points at `<hostile.exe>` so the VERIFYING X-step runs the
verifier against a hostile executable. (The approvals reuse the S7 operator
runbook procedure; here we note only the E-12-specific observations.)

> **Phase 3 gate — `PRECOND-SIGNING` (D-E12-9).** Phase 3 needs three **real,
> S1-verified** approvals, so it runs **only** if the signing capability
> (authenticator, OpenSSH `sk`, throwaway registry entry) is provisioned and
> D-E12-9 is signed. There is no fabricated-signature or bypass path. If
> `PRECOND-SIGNING` is not met, **skip Phase 3 entirely** (no rebind, no
> `<clone_s7>` measurement) and record every §9 matrix row `NOT TESTED` (reason
> `no-signing`); the close (Phase 4) then uses ISO's own post, never an unrun
> `<clone_s7>`. ISO (Phase 1) and HARNESS (Phase 2) have already covered the
> isolation core and the writer/verifier compatibility without it. This signing
> is **not** E-6 and does not satisfy it (prep §1, §8); E-12 still calls **no
> model**.

### A-rebind (admin, then A) — authorized boundary rebind to `<clone_s7>`, adversary absent

Only reached if `PRECOND-SIGNING` is met. The ISO adversary is already gone
(Aadv confirmed no X-R descendant remains). An administrator rewrites
`identity-boundary.v1` to bind `<clone_s7>`, records the new digest `DIGEST_S7`,
and A proves the transition changed **only** the boundary row:

```bat
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "%ProgramData%\AIDO" > "%USERPROFILE%\aido-e12\anchors-s7-pre.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" rebind "%USERPROFILE%\aido-e12\anchors-pre.txt" "%USERPROFILE%\aido-e12\anchors-s7-pre.txt" "identity-boundary.v1.json"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" git "<clone_s7>" > "%USERPROFILE%\aido-e12\git-s7-pre.txt"
```

`rebind` must print `PASS\trebind-changed-only\tidentity-boundary.v1.json`
(`ANCHOR-REBIND`); any `UNAUTHORIZED-ANCHOR-CHANGE` (e.g. the approver registry
also changed) → STOP, Alpha blocked. Then A re-runs the FD-16 proof against the
**new** boundary — it must pass before any S7 write/verify (`S7-PROOF-PRE`):

```bat
"C:\AIDO\venv\Scripts\python.exe" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" status > "<published>\driver-010-status.json"
```

No approval is recorded yet at this point, so expect `refusal == null`, `stage ==
"contract_approval"`, `outcome APPROVAL_REQUIRED`, **exit 0**. An
`IsolationUnprovenError:<category>` refusal (exit 1) is the only isolation
failure; `definition_unreadable` means the inbox definition (Phase 0.10) is
missing.

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
`S7-VERIFY-RECOVER` PASS (this is expected). RECOVERY_REQUIRED is **terminal**:
the step state never leaves it, so every later `status` — including the A6 close
(`driver-099-status.json`) — also derives `recovery_required` and exits **3**
with `refusal == null`. That is the expected terminal lifecycle, not an isolation
failure (A6); do not re-run, repair or `git restore` it (E-10).

### Spot-check deviations (X-R, disposable outbox) — optional but recommended

- Add an extra file beside `stdout.json`+`complete` → `claim_refused:unexpected_entry` → `FD17-UNEXPECTED`.
- Plant a junction named `stdout.json` → `claim_refused:reparse_point` → `FD17-REPARSE`.
- Plant a junction inside the working tree, re-drive M1 → `ObservationError:reparse_point` → `FD18-REPARSE`.

---

## Phase 4 — close and verify (A, then admin)

### A6 (A) — exercise-scoped post-rehearsal proof and accountable compare

Each artifact is compared **only against the baseline of the exercise that owns
it**; a clone is never compared to a different clone. Re-prove FD-16 for the
active boundary:

```bat
"<PY>" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" status > "<published>\driver-099-status.json"
```

**This `status` re-proves FD-16 and reports the terminal lifecycle; its exit code
depends on the path, and the two must not be conflated (FU4).** Every `status`
opens a fresh session, so FD-16 is re-proved each time; but the exit code is the
lifecycle's, and after S7 the lifecycle is terminally `recovery_required`. Read
`driver-099-status.json` and classify it four ways:

| Observation in the report | Meaning | Verdict |
|---|---|---|
| `refusal == null`; `stage == "contract_approval"`, `outcome APPROVAL_REQUIRED`, **exit 0** | FD-16 re-proof passed; no-signing path (no approval signed, nothing ran) — the lifecycle never left contract approval | `ISO-PROOF-POST` **PASS** (no-signing) |
| `refusal == null`; `stage == "recovery_required"`, `outcome RECOVERY_REQUIRED`, **exit 3** | FD-16 re-proof passed; S7 path — the D-E12-3 verifier-for-reviewer substitution ended the attempt in RECOVERY_REQUIRED, which every later `status` maps to exit 3 | `ISO-PROOF-POST` **PASS** (S7); this is the **expected terminal lifecycle**, not a failure |
| `outcome REFUSED`, `refusal.category` starts `IsolationUnprovenError:` (exit 1) | the FD-16 re-proof itself **failed** | **actual isolation failure** → FAIL, Alpha blocked |
| `outcome REFUSED`, any other category (e.g. `definition_unreadable`, `foreign_record`, `state_unreadable`, exit 1), or any stage/exit not matching the path above | provisioning/state went wrong | **unexpected refusal / state** → FAIL, investigate |

**Exit 3 is not read as PASS by itself.** It is a PASS **only** when the report's
`stage` is `recovery_required` with `refusal == null` on the S7 path (where
RECOVERY_REQUIRED is the designed end — see X5 / `S7-VERIFY-RECOVER`). On the
no-signing path the post `status` must be exit 0 / `contract_approval`, and an
exit 3 there would be an unexpected state. The only isolation FAIL is an
`IsolationUnprovenError:` refusal at **exit 1**; a passing FD-16 proof never
produces exit 3 by itself — the RECOVERY_REQUIRED exit 3 comes from the lifecycle,
with the proof having passed.

**A6-ISO (always).** The ISO clone and the ISO-phase anchors are closed against
their **own** ISO baselines (boundary bound to `<clone_iso>` throughout ISO):

```bat
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" git    "<clone_iso>"              > "%USERPROFILE%\aido-e12\git-iso-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict "%USERPROFILE%\aido-e12\git-pre.txt"     "%USERPROFILE%\aido-e12\git-iso-post.txt"
```

**A6-S7 (only if Phase 3 ran).** The S7 clone and the S7 anchors are closed
against their **own** S7 baselines (`git-s7-pre.txt`, `anchors-s7-pre.txt` from
A-rebind), and the shared plane roots are `classify`-ed against the ISO pre
baseline (the plane is one resource that grew legitimately during S7):

```bat
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" git      "<clone_s7>"                 > "%USERPROFILE%\aido-e12\git-s7-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict   "%USERPROFILE%\aido-e12\git-s7-pre.txt"  "%USERPROFILE%\aido-e12\git-s7-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<state_root>"                > "%USERPROFILE%\aido-e12\state-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<published>"                 > "%USERPROFILE%\aido-e12\pub-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<inbox>"                     > "%USERPROFILE%\aido-e12\inbox-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<exchange_root>" --exchange  > "%USERPROFILE%\aido-e12\exch-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "%ProgramData%\AIDO"          > "%USERPROFILE%\aido-e12\anchors-s7-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict   "%USERPROFILE%\aido-e12\anchors-s7-pre.txt" "%USERPROFILE%\aido-e12\anchors-s7-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" classify "%USERPROFILE%\aido-e12\state-pre.txt"   "%USERPROFILE%\aido-e12\state-post.txt" "%USERPROFILE%\aido-e12\allowlist-state.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" classify "%USERPROFILE%\aido-e12\pub-pre.txt"     "%USERPROFILE%\aido-e12\pub-post.txt"   "%USERPROFILE%\aido-e12\allowlist-published.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" classify "%USERPROFILE%\aido-e12\inbox-pre.txt"   "%USERPROFILE%\aido-e12\inbox-post.txt" "%USERPROFILE%\aido-e12\allowlist-inbox.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" classify "%USERPROFILE%\aido-e12\exch-pre.txt"    "%USERPROFILE%\aido-e12\exch-post.txt"  "%USERPROFILE%\aido-e12\allowlist-exchange.txt"
```

> **If Phase 3 was skipped (`no-signing`)**, A6-S7 is **not** run. The boundary
> stayed bound to `<clone_iso>`, A wrote nothing after bootstrap, so the final
> plane/anchor state equals the ISO quiescent state: close the plane roots with
> `classify` (or `strict`) against the `*-pre.txt` baselines, and the anchors
> with `strict` against `anchors-pre.txt`. **Never** manifest or reference
> `<clone_s7>` — it was never bound and never written.

`ISO-DIGEST-POST` PASS requires **every** compare that was run to print `PASS`
(`ERRORLEVEL 0`): no anchor or clone `.git` byte changed against its own baseline,
and no `classify` run found a write-once rewrite, a deletion, an unexpected-name
object, a reparse point, or a hard link. **Any `FAIL` line → FAIL, Alpha blocked**
(E-10; no retry, repair or cleanup). The hostile log is read for diagnosis only
and is never authority-plane evidence.

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
- No ISO PASS from X-R's own markers/log alone — the authoritative active-interval
  evidence is the **independent admin observation** `<obs_log>`, and it must
  correlate an **actual** live descendant: a single persistent PID at the
  rehearsal's own `<adv-identity>` under the throwaway X-R owner, not merely any
  same-name process. A missing, uncorrelated, malformed or insufficient
  observation is FAIL, never PASS.
- No reading a post-S7 `status` exit **3** as an isolation failure: after the X5
  substitution RECOVERY_REQUIRED is terminal, so exit 3 with `stage ==
  "recovery_required"` and `refusal == null` is the **expected** lifecycle and a
  PASS for the FD-16 re-proof. The only isolation FAIL is an
  `IsolationUnprovenError:` refusal at exit 1. Equally, no reading exit 3 as PASS
  on the no-signing path, where the post `status` must be exit 0 /
  `contract_approval`.
- No boundary rebind while the adversary is live, and no rebind that changes
  anything other than `identity-boundary.v1.json`. Any anchor change inside an
  exercise, or an extra changed row during the rebind, is a FAIL — never excused
  as administrator activity. FD-16 is re-proved after the rebind (`S7-PROOF-PRE`).
- No comparing one clone against another; each clone is measured only against its
  own pre. On the no-signing path, never manifest or reference `<clone_s7>`.
- No broad `evidence/**` growth rule — every evidence object must match an
  enumerated write-once kind; a rewrite or deletion of any existing blob is a FAIL.
- No `git restore`, retry, repair or cleanup of a RECOVERY_REQUIRED attempt, or of
  any `FAIL` digest/compare (E-10): the S7 run ending exit 3 is the expected end
  of the exercise; a measurement `FAIL` ends E-12 and blocks the Alpha.
- No hand-written `stdout.json`. If a command cannot run, do nothing and let the
  wait expire.
- No elevation of A or X-R; the boundary proof refuses an elevated token.
- No measurement output or adversary marker written into any of the five roots;
  keep A's measurement in `%USERPROFILE%\aido-e12\`, X-R's diagnostic markers in
  `<xr_scratch>`, and the independent observation in `<obs_log>`.

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
# Run by A as: "<PY>" -I e12_measure.py <tree|git|strict|classify|rebind|adversary> ...
import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime

_REPARSE = 0x400
_GIT_TOP = ("HEAD", "config", "index", "packed-refs")
_GIT_DIRS = ("refs", "hooks", "info")
_TICKET = "[0-9a-f]{32}"
_SHA256 = "[0-9a-f]{64}"
_OUTBOX_DIR = re.compile(r"^outbox-[0-9a-f]{32}$")
_WMIC_STAMP = re.compile(r"^(\d{14})(?:\.\d+)?(?:[+-]\d{1,4})?$")
_EPOCH_STAMP = re.compile(r"^\d{1,13}(?:\.\d+)?$")


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


def _diff_keys(a, b):
    ma, mb = _load(a), _load(b)
    return sorted(rel for rel in set(ma) | set(mb) if ma.get(rel) != mb.get(rel))


def strict(a, b):
    findings = _diff_keys(a, b)
    if findings:
        sys.stdout.write("\n".join("DIFF\t%s" % r for r in findings) + "\nFAIL\n")
        return 1
    sys.stdout.write("PASS\n")
    return 0


def rebind(a, b, expected_relpath):
    # The authorized identity-boundary.v1 rebind between exercises must change
    # exactly one anchor row — the boundary file — and nothing else.
    changed = _diff_keys(a, b)
    unexpected = [r for r in changed if r != expected_relpath]
    if expected_relpath not in changed:
        sys.stdout.write("FAIL\trebind-did-not-change\t%s\n" % expected_relpath)
        return 1
    if unexpected:
        sys.stdout.write("\n".join("UNAUTHORIZED-ANCHOR-CHANGE\t%s" % r for r in unexpected) + "\nFAIL\n")
        return 1
    sys.stdout.write("PASS\trebind-changed-only\t%s\n" % expected_relpath)
    return 0


def _compile(glob):
    # '*' does NOT span '/', '**' spans, '<ticket>'=32 hex, '<sha256>'=64 hex.
    out, i = ["^"], 0
    while i < len(glob):
        if glob.startswith("<ticket>", i):
            out.append(_TICKET)
            i += len("<ticket>")
        elif glob.startswith("<sha256>", i):
            out.append(_SHA256)
            i += len("<sha256>")
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


def _parse_stamp(token):
    # The observer's wall-clock stamp, as epoch seconds. Two PowerShell-free
    # shapes are accepted: a plain integer/float epoch (what `python -I -c
    # "import time;print(int(time.time()))"` prints — the primary procedure,
    # which needs no wmic), and wmic's LocalDateTime (14 digits YYYYMMDDHHMMSS
    # with an optional fraction and UTC offset) where wmic is present. The span
    # is a difference, so a consistent clock within one log is all that matters;
    # a token of neither shape is malformed.
    m = _WMIC_STAMP.match(token)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").timestamp()
        except (ValueError, OverflowError, OSError):
            return None
    if _EPOCH_STAMP.match(token):
        return float(token)
    return None


def adversary(report_path, observer_log, min_seconds, expected_image_path):
    min_seconds = float(min_seconds)
    expected = os.path.normcase(os.path.normpath(expected_image_path))
    # 1. Launch evidence is AIDO's OWN frozen verifier report. A pre-launch
    #    refusal (refused-before-execution) never started the configured
    #    executable, and a report that does not record a start is no launch
    #    (mandatory validation #8). A missing report is missing launch evidence.
    try:
        with open(report_path, "r", encoding="utf-8") as handle:
            report = json.load(handle)
    except (OSError, ValueError):
        sys.stdout.write("FAIL\tadversary-report-unreadable\n")
        return 1
    if report.get("outcome") == "refused-before-execution" or report.get("category") == "refused-before-execution":
        sys.stdout.write("FAIL\tadversary-refused-before-launch\n")
        return 1
    if not bool(report.get("execution", {}).get("started")):
        sys.stdout.write("FAIL\tadversary-not-started\n")
        return 1
    # 2. Active/duration evidence is the INDEPENDENT observer log (admin,
    #    elevated; a standard O account cannot see another user's processes),
    #    NOT any X-R-authored marker. Each sighting is one line
    #       <epoch-or-wmic-stamp> <pid> <ExecutablePath-or-unique-image>
    #    whitespace-split into exactly three fields (the identity, last, may
    #    hold spaces). The observed process is correlated to the LAUNCHED
    #    adversary by identity: it must be the SAME unique rehearsal adversary
    #    the verifier launched (passed here as expected_image_path — the
    #    configured hostile executable's full path where wmic is present, else
    #    its unique rehearsal image basename, captured under the throwaway X-R
    #    owner filter). A same-name process at a different identity is NOT this
    #    rehearsal's adversary.
    by_pid = {}
    try:
        with open(observer_log, "r", encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                fields = line.split(None, 2)
                if len(fields) != 3:
                    sys.stdout.write("FAIL\tmalformed-observation\t%s\n" % line)
                    return 1
                stamp_token, pid_token, path_token = fields
                dt = _parse_stamp(stamp_token)
                if dt is None:
                    sys.stdout.write("FAIL\tmalformed-timestamp\t%s\n" % stamp_token)
                    return 1
                if not pid_token.isdigit():
                    sys.stdout.write("FAIL\tmissing-process-identity\t%s\n" % line)
                    return 1
                if os.path.normcase(os.path.normpath(path_token)) != expected:
                    sys.stdout.write("FAIL\tuncorrelated-process\t%s\n" % path_token)
                    return 1
                by_pid.setdefault(pid_token, []).append(dt)
    except OSError:
        sys.stdout.write("FAIL\tobserver-log-unreadable\n")
        return 1
    if not by_pid:
        sys.stdout.write("FAIL\tinsufficient-observation\t0-sighting(s)\n")
        return 1
    # 3. The persistent descendant is the single PID whose correlated sightings
    #    span the longest. The short-lived parent cannot span the window, so an
    #    observation of only the parent fails here, not by accident.
    best_pid, best_span, best_count = None, -1.0, 0
    for pid, stamps in by_pid.items():
        span = max(stamps) - min(stamps)
        if span > best_span:
            best_pid, best_span, best_count = pid, span, len(stamps)
    if best_count < 2:
        sys.stdout.write("FAIL\tinsufficient-observation\tpid-%s-%d-sighting(s)\n" % (best_pid, best_count))
        return 1
    if best_span < min_seconds:
        sys.stdout.write("FAIL\tobserved-active-%.1fs-under-%.1fs\n" % (best_span, min_seconds))
        return 1
    sys.stdout.write("PASS\tcorrelated-pid-%s-active-%.1fs-over-%d-sightings\n" % (best_pid, best_span, best_count))
    return 0


def main(argv):
    if len(argv) < 2:
        raise SystemExit("usage: tree|git|strict|classify|rebind|adversary ...")
    mode = argv[1]
    if mode == "tree":
        return tree(argv[2], exchange=("--exchange" in argv[3:]))
    if mode == "git":
        return git(argv[2])
    if mode == "strict":
        return strict(argv[2], argv[3])
    if mode == "classify":
        return classify(argv[2], argv[3], argv[4])
    if mode == "rebind":
        return rebind(argv[2], argv[3], argv[4])
    if mode == "adversary":
        return adversary(argv[2], argv[3], argv[4], argv[5])
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

`allowlist-state.txt` (the frozen `AidoStateRoot` layout; every write-once
evidence kind, no WAL, **no broad `evidence/**` rule**). `<sha256>` expands to
exactly 64 lowercase hex — the DL-4B blobs are bare-hex, only `verification`
carries `.json`:

```text
# <state_root> — the frozen AidoStateRoot + store.v4 evidence layout
S aido-state-root.json
G control-plane.sqlite3
G control-plane.sqlite3-journal
W evidence/approved-diff/
W evidence/approved-diff/<sha256>
W evidence/config/
W evidence/config/<sha256>
W evidence/claims/
W evidence/claims/<sha256>
W evidence/observations/
W evidence/observations/<sha256>
W evidence/verification/<sha256>.json
G staging/*.partial
```

`evidence/`, `evidence/verification/` and `staging/` exist from
`AidoStateRoot.create()` (baseline, unchanged → no rule needed); the four DL-4B
blob kind directories are created lazily, so each kind directory line is listed
`W` (new allowed, never deleted). A file under any `evidence/<kind>/` that is not
a 64-hex SHA-256 (e.g. a planted `not-a-sha.txt`), or a rewrite/deletion of an
existing blob, is a `classify` FAIL.

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

The helper's `*` does **not** span `/`, `<ticket>` matches exactly
`[0-9a-f]{32}` and `<sha256>` exactly `[0-9a-f]{64}`, so a directory named
`outbox-evil` (non-hex) is **not** excluded — it is measured and, being
unexpected, fails. The `rebind` mode proves the one authorized between-exercise
transition changed only `identity-boundary.v1.json`.

The `adversary` mode takes **four** arguments —
`adversary <verify-report> <obs_log> <window-seconds> <adv-identity>` — and is
mechanically meaningful about *which* process it accepts (FU4):

- **launch** comes from AIDO's own verifier report (`execution.started == true`,
  never `refused-before-execution`); a missing report or an unstarted one FAILs;
- **active/duration** comes from the **independent** admin observer log
  `<obs_log>` (never an X-R marker). Each sighting is one whitespace-split line
  `<stamp> <pid> <identity>`: a monotonic wall-clock `<stamp>` (epoch seconds —
  the primary, wmic-free form — or wmic `LocalDateTime` where present), the
  OS-reported `<pid>`, and the observed process `<identity>`;
- **correlation to the launched adversary** is by `<identity>`: every sighting's
  identity must equal `<adv-identity>` (the configured hostile executable's full
  `ExecutablePath` where wmic is present, otherwise the unique rehearsal image
  basename captured under the throwaway X-R-owner filter). A same-name process at
  a different identity is **not** this rehearsal's adversary;
- **persistence** is required of a **single** PID: the helper takes the PID whose
  correlated sightings span the longest and requires ≥ 2 of them spanning ≥ the
  window. The short-lived parent cannot span the window, so observing only the
  parent FAILs.

It **fails closed** (and never PASSes) for: a missing/refused/unstarted launch
report (`adversary-report-unreadable` / `adversary-refused-before-launch` /
`adversary-not-started`); a line that is not three fields
(`malformed-observation`); a bad stamp (`malformed-timestamp`); a non-numeric PID
(`missing-process-identity`); a same-name process at a different identity
(`uncorrelated-process`); no correlated sighting (`insufficient-observation
0-sighting(s)`); a single correlated sighting or only-the-parent
(`insufficient-observation pid-…`); and a span under the window
(`observed-active-…-under-…`). X-R's own markers/log remain **diagnostic only**.

Substitute the two O-named docs (`approved_diff_name`, `project_config_name`)
with the names the rehearsal's `alpha-definition.json` actually declares.
