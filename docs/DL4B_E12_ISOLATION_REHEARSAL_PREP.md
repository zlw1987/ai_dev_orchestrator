# DL-4B E-12 — Windows Isolation Rehearsal Preparation

**Status: E-12 PREP UNDER CORRECTIVE REVIEW (FU2) — NOT AUTHORIZED TO EXECUTE.**
This document is being corrected by E-12 PREP FU2; it is PENDING INDEPENDENT
REVIEW and does not authorize E-12, E-6, or a live Alpha. FU2 repairs four
execution-contract defects against the frozen code: the filesystem topology
(five mutually disjoint roots per `BoundaryPaths._disjoint`, not a nested
layout), the measurement helper's object names (the real `control-plane.sqlite3`
/ `aido-state-root.json` / `evidence/verification/` / `handoff-<ticket>` /
`outbox-<ticket>` set), the hostile-verifier launch order (the frozen verifier
runs its configured executable only *after* the approved post-image is proved,
so the write must precede the verify), and the no-signing HARNESS gap (a
standalone, signing-free writer+verifier compatibility exercise).

| | |
|---|---|
| Baseline | `main` at `5b76d9c21e06cc37d127bbaa7c24206b22c78cd8` (FU2 corrective baseline; docs-only on top of the S0–S7 code). DL-4B **S0–S7 are implemented and independently ACCEPTED/FROZEN for offline scope** (code frozen at `c7f9e64873bbeddd8188582fcbcdbfdcc84c05c5`; no code changed since) |
| Contract | `docs/DL4B_REAL_INTEGRATION_BOUNDARY_DESIGN.md` (AMEND1), especially §5.8 and §5.8.10; the S7 obligations in `docs/DL4B_S7_ALPHA_DRIVER.md` §9–§10 and `docs/DL4B_S7_OPERATOR_RUNBOOK.md` §10 |
| Kind | **Preparation only.** No account/ACL provisioning, no scheduled task, no hostile program executed, no real target workspace, no model, no credential value, no branch/PR. Documentation-only |
| Deliverables | This prep document; `DL4B_E12_OPERATOR_RUNBOOK.md`; `DL4B_E12_EVIDENCE_MATRIX.md`; §9 (decisions requiring authorization); §10 (GO/NO-GO) |

This document prepares the separately authorized E-12 rehearsal. It does **not**
authorize it. Nothing here changes an accepted S0–S7 contract, and no
`CLAUDE.md` change is proposed. Where preparation revealed a material question,
it is raised in §7 (findings) and §8 (decisions), never silently resolved by a
code change.

---

## 1. What E-12 is, and what it is not

E-12 is the **live isolation rehearsal** of §5.8.10 item 2, run on a fully
provisioned Windows host with real, distinct, non-administrative A, X and O
accounts. Its single purpose is to confirm, against a running adversary, the
one invariant the whole DL-4B authority model rests on (§5.8.1):

> Repository-controlled code must not be able to create, rewrite, delete or
> consistently forge the authoritative state and evidence on which AIDO relies.

"Authoritative" is the store.v4 rows and blobs, the approver registry, the
identity boundary, the AIDO code A executes, A's process and token, and A's own
observations M0/M1/M2 (§5.8.1). Execution claims are explicitly **not**
authoritative and E-12 does not try to make them so.

E-12 is **not**: a live Alpha; a model call of any kind; a real target
repository; AUTH-PILOT; E-6 (the authenticator-interoperability acceptance
rehearsal); acceptance of S7. It uses its **own throwaway execution account**
(`X-R`), never the Alpha's fresh `X` (E-11, E-12 criteria). After E-12,
`identity-boundary.v1` is re-provisioned with the Alpha's real fresh `X` before
any approval binds its digest.

**Authenticator boundary (resolved by FU1 — read before §5 and §9).** E-12
makes **no model call** of any kind, in any exercise. The authenticator picture
is *not* uniform across the three exercises, and the earlier drafts were
self-contradictory (they said E-12 used no authenticator yet required O to sign
three approvals). The corrected boundary:

- **ISO and HARNESS use no authenticator and no model.** They need no consumed
  approval and no signing: ISO is `status` (the FD-16 proof), then an approved
  **write** applied by X-R, then a hostile `verify` run as X-R (the write must
  precede the verify — see §3.3); HARNESS is a standalone, signing-free
  writer+verifier compatibility run on its own disposable clone. Both run before
  any approval exists. **Because ISO and HARNESS do not depend on `PRECOND-SIGNING`,
  the frozen writer/verifier compatibility (detached HEAD, read-only `.git`) and
  the entire isolation core are tested even if signing is never authorized.**
- **S7 (the driver integration exercise) requires real approval signing.**
  Reaching the write and verify announcements, the exclusive-lock measurement
  and the expected RECOVERY_REQUIRED end *requires three real, S1-verified
  approvals* (contract, plan activation, exact diff). There is **no** non-signing
  path to a consumed approval: fabricating a signature, bypassing S1
  verification, or weakening the store are all forbidden, so S7 genuinely needs
  the real FIDO2 authenticator in **O's** session. This is declared as a
  **separately authorized prerequisite** (`PRECOND-SIGNING` / decision
  `D-E12-9`, §9), gated independently of E-12 execution.
- **Signing in S7 is not E-6 and does not satisfy E-6.** E-6 is the independent
  *format-interoperability acceptance gate* (one throwaway challenge signed and
  verified, plus the induced-negative battery, §8). E-12 using the authenticator
  operationally to consume three approvals neither performs nor accepts E-6; E-6
  remains **NOT PERFORMED** and separately gated. If the host is not yet
  provisioned to sign, ISO and HARNESS may still run in full; **the entire S7
  exercise is then `NOT TESTED` until `PRECOND-SIGNING` is met**, and no S7 row
  may be recorded PASS from an unsigned run.

Because E-12 permits **no model**, it uses the existing
`l2-verify-approved-file-edit` (5F2D, verifier only — no reviewer), not
`l2-review-approved-file-edit` (5F2E, which calls a model). One consequence
cascades through the whole plan and is stated once here: **a bare
`verification-result.v1` is not a `ReviewPacket`, so the S7 VERIFYING claim
classification raises "anything else" → RECOVERY_REQUIRED by design** (§5.2
step 5). E-12 therefore cannot and must not reach ACCEPTANCE or COMPLETE. That
is expected, not a failure (see §5, Exercise S7, and the matrix's NOT TESTED
rows).

The rehearsal has three coordinated exercises on one provisioned host, in order:

| Exercise | Clone (own disposable repo + preimage-bound artifact) | Proves | Frozen command used, as X-R |
|---|---|---|---|
| **ISO** — adversarial isolation core (§5.8.10 item 2) | `<clone_iso>` | T3 cannot create, rewrite, delete or forge any authority-plane object; A's FD-16 proof still passes; every authority digest and the `.git` control digest are unchanged — **and the adversary provably launched and ran** (§3.3) | `l2-apply-approved-file-edit` (the write), then `l2-verify-approved-file-edit` with a hostile configured executable |
| **HARNESS** — frozen-harness compatibility (§5.8.8, E-12 criterion) | `<clone_harness>` | The frozen writer and verifier accept a **detached HEAD** and a **`.git` that is read-only to X**, end to end to a `verified` outcome, **with no signing** | `l2-apply-approved-file-edit`, then `l2-verify-approved-file-edit` with a **benign** configured executable |
| **S7** — driver integration measurements (§9–§10 of the driver doc) | `<clone_s7>` | Per-invocation FD-16 proof duration; exclusive store lock across the long `run`; real-time announcement visibility; A's published reports readable by O, unreachable by X; the single-stream parse question | `alpha_driver` verbs (A) + the two X-R steps — **requires `PRECOND-SIGNING`** |

Each exercise binds its **own** disposable clone (and its own preimage-bound
approved artifact) into `identity-boundary.v1`; the admin re-provisions the
boundary's `clone` and re-binds the digest between exercises. The four A-owned
plane roots (§3.1) are provisioned once and reused. Because each clone and its
pinned `pre_image_sha256` are distinct, no target ever receives the same
preimage-bound write twice (§4, "No double-write").

---

## 2. Host prerequisites — the three identities

All three are **local standard accounts**, none in `Administrators`,
`Backup Operators`, or any group another of the three is in (FD-13, §5.8.2).
Provisioning is an **elevated human prerequisite** (§5.8.2); AIDO never creates
an account and runs non-elevated throughout.

| Identity | Account (rehearsal) | SID | Runs during E-12 | Logon session |
|---|---|---|---|---|
| **A** authority | `aido-a-rehearsal` | `<A-R SID>` | `alpha_driver` only, with `python -I`; and A's pre/post digest helper (reads A's own state root) | A's own interactive session (secure logon UI), or an admin-provisioned S4U task |
| **X-R** execution | `aido-x-rehearsal` (**throwaway; destroyed after E-12**) | `<X-R SID>` | `l2-apply-approved-file-edit`, `l2-verify-approved-file-edit`; owns the clone; runs the hostile program (T3) | X-R's own interactive session |
| **O** operator | the human's own account | `<O SID>` | reads `published/`; `certutil`/viewer | O's own interactive session |

### 2.1 Launch and session rules (FD-13)

- Each identity works in its **own logon session, window station and desktop**.
  Reached by the Windows **secure logon UI**, fast user switching, or (for A
  only) an admin-provisioned Task Scheduler S4U task ("run whether logged on or
  not", no stored password, fixed action, O granted run permission only).
- `runas`, `Start-Process -Credential`, and any start of one identity's process
  on another identity's desktop are **forbidden**. A shared desktop lets
  same-integrity processes inject input, install low-level hooks and send window
  messages across accounts, and could capture a typed password (§5.8.2).
- A must be started with `python -I` (isolated). The driver refuses otherwise
  (`interpreter_not_isolated`).

### 2.2 Host-policy preconditions (D-17)

E-12 is **blocked with no fallback** if host policy forbids any of: creating
local accounts; granting "log on as a batch job" (for the S4U option); user
switching / multiple interactive sessions. There is no same-account mode
(FD-16: no flag, config key or environment variable skips the boundary proof).
Confirm these before provisioning — see the matrix row `PRECOND-POLICY`.

### 2.3 Anchors and install (read-only to all three)

| Object | Path | Owner | A / X-R / O |
|---|---|---|---|
| Approver registry | `%ProgramData%\AIDO\approver-registry.v1.json` | admin | read / read / read |
| Identity boundary | `%ProgramData%\AIDO\identity-boundary.v1.json` | admin | read / read / read |
| AIDO install, venv, interpreter, every `sys.path` and `PATH` dir of A | code-constant install root(s) | admin | read+execute / **read+execute only** / read+execute |

`identity-boundary.v1` is written at the **code-constant** admin-owned path
(not config, not CLI), carries the SIDs of A, X-R and O and the **five
mutually disjoint** `BoundaryPaths` the frozen
`integration.identity_boundary.BoundaryPaths._disjoint` enforces — `state_root`,
`published`, `inbox`, `exchange_root` and `clone` (plus `install_roots`); none
may equal, contain or be contained by another — and is subject to the same
anchor checks
as the registry: path is the constant; no reparse point in any component;
neither A nor X-R has write/append/delete/`WRITE_DAC`/`WRITE_OWNER` on the file
nor add-file/delete-child on its directory; the token is not elevated (FD-2
(a)–(e), §5.1).

---

## 3. The throwaway rehearsal state — exactly what to build

Everything E-12 touches is disposable and synthetic (no real target, E-9/E-12).

### 3.1 The five disjoint roots (real FD-16 topology)

The frozen `BoundaryPaths._disjoint` requires `state_root`, `published`,
`inbox`, `exchange_root` and `clone` to be **five mutually disjoint absolute
paths** — none equal to, inside, or containing another (checked case-foldingly,
erring toward refusal). **A nested layout (for example `published/` or
`exchange/` *under* the state root) is refused by the frozen identity boundary.**
They are therefore provisioned as five sibling directories (e.g.
`D:\e12\state`, `D:\e12\published`, `D:\e12\inbox`, `D:\e12\exchange`,
`D:\e12\clone`), each with its own FD-14 protected DACL (inheritance disabled,
so no inherited `Users`/`Authenticated Users`/`Everyone`/`INTERACTIVE` ACE can
apply — §5.8.3):

| Root | A | X-R | O | What it holds (real frozen names) |
|---|---|---|---|---|
| **`state_root`** | owner, full | **none** | **none** | exactly the frozen `AidoStateRoot` layout — see §3.1.1 |
| **`published`** | owner, full | **none** | read | `driver-<nnn>-<verb>.json` (A's `cmd.exe`-redirected reports); outside E-12, write-once acceptance-bundle files `<kind>-<sha256>` |
| **`inbox`** | read | **none** | add-file, write own files | O-placed `alpha-definition.json`, `attestation-*.json`, and the two O-named docs (`approved_diff_name`, `project_config_name`) |
| **`exchange_root`** | owner, full | **none at the root** | **none at the root** | per-ticket `handoff-<ticket>\` and `outbox-<ticket>\` (§3.1.2) |
| **`clone`** | read | owner of the tree and `.git`, but `.git` read-only (§3.2) | read | the synthetic Git repo (§3.2) |

`<ticket>` is AIDO's own 32-lowercase-hex id (`ticket_directories` refuses
anything else), so the per-ticket names are fixed and unambiguous.

#### 3.1.1 Inside `state_root` — exactly the frozen `AidoStateRoot` layout

`AidoStateRoot.create` makes an **empty, non-Git** directory the state root and
the driver then holds it to a fixed top-level entry set — `verify()` refuses the
root if it holds **anything** AIDO did not create (`_ROOT_ENTRIES`):

```text
state_root\
  aido-state-root.json          marker (root id); created once, never rewritten
  control-plane.sqlite3         the store (store.v4); PRAGMA locking_mode=EXCLUSIVE
  control-plane.sqlite3-journal transient SQLite rollback journal (crash-survivable)
  evidence\verification\<sha256>.json   write-once verification-result.v1 blobs
  staging\<uuid>.partial        A's own transient write-once staging files
```

There is **no** WAL: the store uses the default rollback journal, so the only
transient the frozen root tolerates is `control-plane.sqlite3-journal`. A
`-wal`/`-shm` file, or any other top-level name, is itself a frozen-runtime
refusal and a measurement FAIL (§5.0). `store.v4`, `published/`, `inbox/` and
`exchange/` are **not** names inside the state root — that was the FU1 topology
error FU2 corrects.

#### 3.1.2 Inside `exchange_root` — the per-ticket handoff and outbox (FD-17)

For one dispatch A creates two sibling directories directly under
`exchange_root` (frozen `integration.exchange`):

| Object | A | X-R | O | Contents |
|---|---|---|---|---|
| `handoff-<ticket>\` | owner; **write-once at creation**, protected | read only | none | exactly `approved-diff-proposal.json` + `project.yaml`, each written once |
| `outbox-<ticket>\` | owner, **capped by an `OWNER RIGHTS` ACE to list/read** (A cannot add, alter or re-permission) | list + add files; read/write/delete **its own** files | read | the X-R write/review **claim** (the claim channel) |

### 3.2 Synthetic repository (X-R-owned clone), one per exercise

Each exercise (ISO, HARNESS, S7) uses its **own** disposable clone
(`<clone_iso>`, `<clone_harness>`, `<clone_s7>`) bound into `identity-boundary.v1`
for that exercise; the admin re-provisions the boundary's `clone` and re-binds
the digest between exercises. Each clone is:

- A tiny synthetic Git repository created **by X-R** with `git clone`, checked
  out **detached** at `base_head_oid` (so HARNESS can confirm detached-HEAD
  acceptance). No hooks are cloned. **No submodules** (a `modules/` dir or a
  `.gitmodules` file at M0 refuses — FD-18, §5.8.5).
- It contains **one** ordinary UTF-8 tracked file as the write target, plus a
  handful of other small tracked files so the working-tree manifest is
  non-trivial. Total tree well under the FD-18 caps (§4.2). Each clone's write
  target and its approved artifact's `pre_image_sha256` are **distinct** across
  exercises, so no preimage-bound write is ever repeated (§4, "No double-write").
- After the clone, an **administrator** applies the clone ACLs **before** any
  harness runs (FD-14, §5.8.3):

| Clone object | A | X-R | O |
|---|---|---|---|
| clone root directory object | read | contents: modify; the root itself: **no DELETE/`WRITE_DAC`/`WRITE_OWNER`**; on the parent: traverse only | read |
| working tree (excluding `.git`) | read | owner; modify; an inheritable `OWNER RIGHTS` ACE removes the owner's implicit `WRITE_DAC` | read |
| `.git` subtree | read | owner (Git's ownership check, C-10) **but read+execute only**: an `OWNER RIGHTS` ACE limits X-R to `READ_CONTROL`, so X-R can neither write `HEAD`/refs/index/config/hooks/objects nor re-permission them | read |

### 3.3 The hostile verification program (T3 simulation) — and why the write must come first

A synthetic program **written outside the clone** (5F2D requires the executable
to be absolute, existing, a regular file, and outside the target workspace). It
is the `controlled_verification` executable in the throwaway project config
(the opt-in must be enabled).

**The frozen verifier launches it only after the approved post-image is proved.**
`verify_approved_file_edit` runs every gate *before* `run_configured_verification`:
it proves the target's current bytes hash to the approved `post_image_sha256`,
that the Git-visible dirty state is **exactly** that one path as an unstaged
modification (`" M"`), and that HEAD resolves — and only then launches the
configured executable. If the workspace does **not** already hold the approved
modification, the verifier raises `VerificationRefusedError`
(`refused-before-execution`, `execution.started == false`) and **the hostile
program never runs** (this was the FU1 defect: ISO invoked the verifier against
a clone with no applied write, so the adversary could never start). FU2 corrects
the order:

1. **(X-R)** `l2-apply-approved-file-edit` applies the approved single-file
   `modify` to `<clone_iso>`'s target. The working tree now holds exactly the
   approved post-image as a single `" M"` on the pinned detached HEAD.
2. **(X-R)** `l2-verify-approved-file-edit` with the hostile executable now
   **passes preflight and launches it** as X-R, with X-R's token, cwd the clone,
   and the fixed minimal environment (no `AIDO_*`, no credential).

The launched program **spawns a detached descendant that repeats every attack
below for the rest of the rehearsal** (§5.8.10).

**Positive adversary-execution evidence is mandatory (a digest comparison alone
cannot satisfy ISO).** The program and its descendant write monotonic
timestamp + result markers into an **X-R-owned scratch directory outside all
five roots** (so they neither pollute nor depend on the authority plane, and
survive clone teardown). ISO PASS requires, in addition to the digest/proof
results, that `e12_measure.py adversary` confirms all of:

- **launched** — the verifier report has `execution.started == true` and is
  **not** `refused-before-execution` (a pre-launch refusal is never counted as a
  launch, mandatory validation #8);
- **detached descendant started** — a `descendant-start.txt` marker (its pid);
- **remained active for the required interval** — `descendant-end.txt` −
  `descendant-start.txt` ≥ the D-E12-8 window (and O corroborates with
  `tasklist` during the window — matrix `ISO-ADVERSARY-ACTIVE`);
- **the prescribed access attempts occurred** — the program's log records each
  enumerated target and the Win32 result (expected `ERROR_ACCESS_DENIED` = 5, or
  the NT status equivalent). The log is an **X claim**, kept for diagnosis only —
  never authority-plane evidence.

The attack set (§5.8.10 item 2), each to be attempted repeatedly:

1. write / delete / rename / take ownership of / re-permission **every** FD-14
   object across all four A-owned plane roots (§3.1) and the clone (§3.2);
2. write `.git/HEAD`, `config`, `index`, a `refs/` entry, and a `hooks/` file;
3. `OpenProcess` A for VM read, VM write, thread creation and handle
   duplication; open A's primary token;
4. write into A's install, every `sys.path` entry and every `PATH` directory
   A loads from;
5. add files to `inbox\`, `exchange_root\handoff-<ticket>\` and `published\`;
6. plant a **junction** and a **hard link** in the current
   `exchange_root\outbox-<ticket>\`;
7. send input / install hooks into A's desktop;
8. read A's and O's environment blocks and profiles.

> **Safety for the rehearsal itself.** The descendant must be launchable, but
> the rehearsal host is itself disposable or isolated. The program performs
> only the enumerated access attempts and logs results; it must not exfiltrate,
> encrypt, or damage anything outside the throwaway tree. It is a benign
> prober, not malware. This is a program the operator writes under the
> AUTH-PILOT, reviewed before E-12 — it is not shipped in this repository, and
> this document does not provide its body.

---

## 4. Frozen-harness compatibility: detached HEAD and read-only `.git`

Required by E-12's criterion and §5.8.8. Grounded in the frozen contracts:

- **Detached HEAD.** No frozen harness inspects the branch: the fixed Git set
  contains no `symbolic-ref` and no `--abbrev-ref` (§5.8.8). A detached checkout
  is therefore *expected* to be accepted unchanged. **If any harness refuses it,
  the Alpha is blocked** — no harness change is implied or permitted here.
- **Read-only `.git` for X.** The fixed Git set is read-only and uses
  `--no-optional-locks`, so it should run against a `.git` X cannot write
  (§5.8.8). **If it does not, the Alpha is blocked.**
- **Both harnesses, as a standalone signing-free run.** The E-12 criterion says
  "the frozen harnesses" (plural). HARNESS exercises **both** the writer
  (`l2-apply-approved-file-edit`, which writes only the working-tree file X-R
  owns — it needs no `.git` write) and the verifier
  (`l2-verify-approved-file-edit`) on its **own** disposable clone
  `<clone_harness>`, with a **benign** `controlled_verification` executable that
  exits 0, so the verifier reaches a `verified` outcome. This is the successful
  writer+verifier **compatibility** test, and it needs **no signing and no S7**.
  ISO's write-then-hostile-verify (§3.3) exercises the same preflight under an
  adversarial executable and corroborates it, but HARNESS is the authoritative
  compatibility evidence. **Because HARNESS does not depend on `PRECOND-SIGNING`,
  the E-12 verdict can claim writer/verifier compatibility even when signing is
  not authorized — and conversely it must not claim HARNESS coverage from an S7
  run that never happened (§10).**

### 4.1 Git ownership (C-10)

The frozen Git adapter forwards neither `HOME` nor `USERPROFILE` and sets
`GIT_CONFIG_NOSYSTEM=1`, so no `safe.directory` entry can reach it. Git refuses
a repository not owned by the invoking account. Therefore **every Git-using
harness runs as the clone's owner, X-R**, and **A runs no Git at all** (it
observes with the FD-18 reparse-refusing reads). Confirm X-R owns the clone
before HARNESS (matrix `HARNESS-OWNER`).

### 4.2 FD-18 observation caps (so the synthetic tree stays legal)

A's Git-free observation refuses an over-cap tree. Keep the synthetic clone well
inside these implemented constants
(`src/ai_dev_orchestrator/integration/workspace_observation.py`):

| Constant | Value |
|---|---|
| `MAX_TREE_ENTRIES` | 50 000 files outside `.git` |
| `MAX_TREE_BYTES` | 1 GiB total tree |
| `MAX_FILE_BYTES` | 64 MiB per file |
| `MAX_GIT_CONTROL_ENTRIES` | 10 000 under `HEAD`/`config`/`index`/`packed-refs`/`refs`/`hooks`/`info` |
| `MAX_GIT_CONTROL_BYTES` | 256 MiB of `.git` control files |
| `MAX_HEAD_BYTES` | 256 (`.git/HEAD` must be exactly `base_head_oid` + LF) |

---

## 5. The three exercises, with identity on every action

Full keystroke-level steps are in `DL4B_E12_OPERATOR_RUNBOOK.md`. The shape and
the identity assignment follow §5.0's measurement contract.

### 5.0 The digest / evidence measurement contract (repaired by FU1; topology-corrected by FU2)

The §5.8.10 pass test is: **A's FD-16 proof passes after the rehearsal, and no
authority-plane object is created, rewritten, deleted or re-permissioned by the
adversary.** The naive implementation — hash the *entire* state root before the
rehearsal and require it byte-identical after — is **wrong for this plan**,
because the same rehearsal legitimately runs the S7 driver against the **same
A-owned authority plane**, and A's own lifecycle (`control-plane.sqlite3` rows,
new write-once `evidence\verification\` blobs, `published\driver-*.json` reports,
`handoff-<ticket>` directories) **must** change those bytes. A whole-tree
equality test would either falsely FAIL on legitimate A activity, or — worse —
invite the operator to *dismiss a genuine difference as "just AIDO activity."*
FU1 forbids both; FU2 re-keys every rule to the real five-root topology and the
real frozen object names, and keeps a `classify` from excusing an unexpected
object just because it landed in a broadly named root.

The repair distinguishes categories **mechanically** across the **five disjoint
roots** (each manifested separately — state_root, published, inbox,
exchange_root, and the clone's `.git`), with no operator judgement. Every rule
is keyed to a **real frozen object name**:

| Category | What it is (real names) | Mechanical rule (PASS requires) |
|---|---|---|
| **Immutable anchors + Git control** | `%ProgramData%\AIDO\approver-registry.v1.json`, `identity-boundary.v1.json`; `state_root\aido-state-root.json` (the write-once marker); and the clone's FD-18 `.git` **control set** (`HEAD`, `config`, `index`, `packed-refs`, `refs/**`, `hooks/**`, `info/**`, `modules/` presence) | **Byte-identical** at every checkpoint (`strict` / `S`). Any single differing row → FAIL |
| **Write-once authority blobs** | `state_root\evidence\verification\<sha256>.json`; each `exchange_root\handoff-<ticket>\` directory and its exactly-two files (`approved-diff-proposal.json`, `project.yaml`) | A blob present earlier is **byte-identical** later; **none is ever deleted** (`W`). A rewrite or deletion → FAIL. New blobs/handoffs are permitted *only* under these enumerated A-owned names |
| **A-owned growth** | `state_root\control-plane.sqlite3` (+ transient `control-plane.sqlite3-journal`); `state_root\staging\*.partial`; `published\driver-*.json`; `inbox\` O-placed docs (`alpha-definition.json`, `attestation-*.json`, the two O-named docs) | May change/grow (`G`), but **only along the enumerated expected names**, and only A (or O, for `inbox\`) can create or write here — each root's protected DACL grants X-R nothing (FD-14), re-verified by `ISO-PROOF-POST` and the one-shot `icacls`/AuthZ dump. **Any object not matching an enumerated name → `NEW-UNEXPECTED`/`CHANGED-UNEXPECTED` FAIL**; any reparse point → FAIL; any hard link (`nlink>1`) → FAIL |
| **Claim channel (excluded, exact match only)** | `exchange_root\outbox-<ticket>\` where `<ticket>` is **exactly** 32 lowercase hex | X-R writes here **by design** (FD-17). The `tree --exchange` manifest prunes a top-level directory matching `^outbox-[0-9a-f]{32}$` **only** — a directory merely containing the word "outbox", or `outbox-` with a non-hex suffix, is **not** excluded and is measured normally, so the exclusion can never hide an unrelated authority object. What A trusts from the outbox is governed by FD-17 (link count 1, no reparse, X-R-owned, within cap), not by this digest |

**Two complementary measurements, both required:**

1. **Quiescent isolation bracket (the literal §5.8.10 test, strongest single
   evidence).** Immediately after the adversary is launched, A performs **no
   lifecycle write at all** for the D-E12-8 window. Over that A-idle interval the
   **entire** authority plane — all five roots' manifests (`tree` of state_root,
   published, inbox and exchange_root, `--exchange` excluded, plus `git` of the
   clone and the anchors) — **must be byte-identical** (`strict` compare,
   `ISO-DIGEST-Q`). Because the **only** actor touching the plane in this bracket
   is the hostile descendant, *any* difference is unauthorized — there is no
   "legitimate activity" to hide behind. This is the faithful §5.8.10 comparison
   and it is unambiguous.
2. **Full-window accountable comparison (isolation survives concurrent
   legitimate activity).** Across the whole rehearsal — including S7's legitimate
   A writes — the immutable-anchor and Git rows stay byte-identical; write-once
   blobs are never rewritten or deleted; every new/changed object matches an
   enumerated A-owned growth name (never X-R-produced), with no reparse point and
   no hard link (`ISO-DIGEST-POST`). The classification is enforced by the
   `classify` compare of **each root against its own pre-enumerated expected-name
   allowlist**, not by eye.

**Why this cannot dismiss a malicious change as legitimate.** A change is
accepted as legitimate **only** when it both (a) matches an enumerated expected
name for its root and (b) sits in a root whose protected DACL denies X-R every
write/add/delete/`WRITE_DAC`/`WRITE_OWNER` right (FD-14), a fact `ISO-PROOF-POST`
re-proves for X-R's SID. X-R therefore cannot create a file in those roots at
all, cannot forge A's ownership, and cannot rewrite a write-once blob or an
anchor. So every object the operator would ever classify "legitimate" is provably
A- (or O-) authored **and** of an expected name; anything the adversary could
produce lands in the immutable, write-once, unexpected-name, reparse or hard-link
findings, each of which is a FAIL. A broadly named directory is **not** a free
pass: an object only clears if its name matches a rule. The comparison is done by
the helper, which prints `PASS` or `FAIL\t<finding>` and sets `ERRORLEVEL` — the
operator records the token, it does not adjudicate it.

Owner/DACL is read **in-process by A's FD-16 proof** (`ISO-PROOF-PRE/-POST`,
§5.8.6 step 5) and confirmed once by an admin `icacls`/AuthZ dump (matrix
`FD14-*`); the byte/structure dimension (existence, size, hash, reparse,
`nlink`) is read by A's **standard-library** measurement helper
(`e12_measure.py`, runbook §A3 / §4; operator tool, not shipped code, F-E12-3).
Neither reads owner SIDs through PowerShell, and A executes no repository code,
no Git, no model and no network client.

**Adversarial review of the measurement (counterexamples that must not pass).**

- *"All steps succeed but the adversary never actually ran, so of course nothing
  changed."* This is the FU1 defect and the most important counterexample. If the
  verifier refused before launch (`refused-before-execution`,
  `execution.started == false`), the hostile executable never started, and a
  byte-identical plane proves nothing. `e12_measure.py adversary` **requires**
  positive launch + detached-descendant + active-interval evidence (§3.3, matrix
  `ISO-ADVERSARY-*`); without it ISO is INVALID, not PASS. FU2's write-then-verify
  ordering is what makes the launch reachable at all.
- *"All steps succeed but a hostile file was dismissed as AIDO activity."* The
  helper never asks the operator to judge a diff. A new object clears only if it
  **matches an enumerated expected name** for its root *and* lands in a root whose
  protected DACL `ISO-PROOF-POST` proves X-R cannot write; so the only objects
  that clear are A/O-authored and expected. A hostile object would be X-R-owned
  (impossible in those roots), of an unexpected name (`NEW-UNEXPECTED` FAIL), or
  outside every root.
- *"The adversary dropped a file into a broadly named growth root (e.g.
  `published\`)."* A `G` rule matches only enumerated names (`driver-*.json`), so
  a `forged-review.json` in `published\` is `NEW-UNEXPECTED` → FAIL. Breadth of
  the directory name is not a pass.
- *"The adversary rewrote an evidence blob or an anchor to forge a prior fact."*
  Those are write-once / immutable; the `strict` (`S`) and write-once (`W`) rules
  flag any byte change → FAIL. The quiescent bracket also catches it with
  whole-plane equality.
- *"The adversary hid a write under a fake `outbox` directory."* The exclusion
  matches `^outbox-[0-9a-f]{32}$` **exactly**; `outbox-evil`, `my-outbox` or a
  nested `handoff-<ticket>\outbox-...` is measured normally → FAIL if unexpected.
- *"The adversary wrote a forged `verified`+`approve` into the real outbox."* The
  outbox is the claim channel (excluded from the sweep). A forged reviewer packet
  is only a *claim*: it cannot pass M1/M2, cannot write/approve/complete, and in
  E-12 the bare verifier output is classified RECOVERY_REQUIRED anyway (§5.8.9).
- *"The adversary re-permissioned an object between the proof and the digest."*
  X-R holds no `WRITE_DAC`/`WRITE_OWNER` on any checked object (FD-14), and
  `ISO-PROOF-POST` re-evaluates X-R's effective rights, so a changed DACL fails
  the proof.
- *"The helper itself was swapped or fed a planted module."* It lives outside all
  five roots (A-owned area, X-R-unwritable) and is run with `python -I`, so the
  script directory and user site are off `sys.path`. A reparse point or hard link
  planted in the tree is itself a `classify` FAIL.
- *"A `classify` PASS alone was taken as isolation."* It is not sufficient by
  itself: PASS requires `ISO-PROOF-POST` **and** the adversary-execution evidence
  **and** the quiescent-bracket `strict` equality **and** the full-window
  `strict`+`classify` result together (§10 fail conditions).

### Exercise ISO (the §5.8.10 core) — on `<clone_iso>`

The order is load-bearing: the frozen verifier runs the hostile executable
**only after** the approved write is proved (§3.3), so the write precedes the
verify.

1. **(A)** Open a throwaway store (`control-plane.sqlite3`) in the rehearsal
   `state_root` and run the FD-16 proof (`alpha_driver … status`, or
   `open_integration_session`). It must pass. Record it (matrix `ISO-PROOF-PRE`).
2. **(A)** Take the **pre-rehearsal manifests** with `e12_measure.py` (runbook
   §A3): a `tree` manifest of each of `state_root`, `published`, `inbox` and
   `exchange_root` (the last with `--exchange`, pruning `outbox-<ticket>`), the
   `git` `.git`-control manifest of `<clone_iso>`, and the anchors manifest. A
   owns/reads all of this. → `ISO-DIGEST-PRE` recorded.
3. **(X-R)** Run `l2-apply-approved-file-edit` once, as X-R, to apply the ISO
   clone's approved single-file `modify`. The working tree now holds exactly the
   approved post-image as a single `" M"` on the pinned detached HEAD
   (`HARNESS-WRITE-DETACHED` corroboration; the authoritative writer+verifier
   success is HARNESS, step 8).
4. **(X-R)** Run `l2-verify-approved-file-edit` once, as X-R, with the throwaway
   project config whose `controlled_verification` executable is the hostile
   program (§3.3). Its preflight now **passes** (the write of step 3 satisfies
   the post-image/dirty/HEAD gates) and it **launches** the hostile program,
   which spawns its detached descendant to hammer the attack set for the rest of
   the rehearsal. Capture the verifier report and the adversary markers; confirm
   launch with `e12_measure.py adversary` (`ISO-ADVERSARY-LAUNCH`). **If the
   verifier instead returns `refused-before-execution`, the adversary did not
   run and ISO is INVALID — not a pass.**
5. **(A)** **Quiescent bracket.** A stays idle (no lifecycle write) for the
   D-E12-8 window while the descendant runs, then re-takes all five manifests and
   runs `strict` compares against the step-2 manifests. **All must be
   byte-identical** → `ISO-DIGEST-Q` PASS. Any difference → FAIL, Alpha blocked.
   O corroborates the descendant is still live (`tasklist`) across the window
   (`ISO-ADVERSARY-ACTIVE`).
6. Let the descendant keep running through S7.
7. **(A)** After the full rehearsal window, re-run the FD-16 proof
   (`ISO-PROOF-POST`) and re-take all five manifests. **Pass** (`ISO-DIGEST-POST`)
   = the proof still passes **and** the adversary-execution evidence is present
   (step 4, step 5) **and** the `strict` anchors/`.git` compares show no
   difference **and** the `classify` compare of **each** A-owned root prints
   `PASS` (no write-once rewrite or deletion, no unexpected-name object, no
   reparse, no hard link, no change outside an enumerated A-owned growth name).
   The hostile log is read only for diagnosis.

### Exercise HARNESS (detached HEAD + read-only `.git`) — standalone, on `<clone_harness>`, no signing

The frozen writer and verifier must accept a **detached HEAD** and a `.git` that
is **read-only to X**. FU2 makes HARNESS an **explicit standalone exercise** that
needs **no signing and no S7**, so writer/verifier compatibility is obtained even
if `PRECOND-SIGNING` is never authorized:

8. **(X-R)** On its own disposable clone `<clone_harness>` (own preimage-bound
   artifact, write target **distinct** from `<clone_iso>` and `<clone_s7>`), run
   `l2-apply-approved-file-edit` (the writer), then `l2-verify-approved-file-edit`
   with a **benign** `controlled_verification` executable that exits 0. Confirm
   from the writer's result that it applied the `modify` to the detached,
   `.git`-read-only clone (`HARNESS-WRITE-DETACHED`), and from the verifier's
   report that it reached **`outcome: verified`** — proving the read-only Git
   preflight accepted the detached HEAD and the read-only `.git` end to end
   (`HARNESS-VERIFY-DETACHED`). If either refuses on detached-HEAD or
   `.git`-permission grounds → Alpha blocked. **This is the authoritative
   writer+verifier compatibility PASS; the ISO write/hostile-verify (steps 3–4)
   only corroborates the preflight.**

> **No double-write.** A `modify` write is pinned to a `pre_image_sha256`, so the
> same target cannot be written twice from the same pre-image. The three
> exercises therefore use **three distinct clones** (`<clone_iso>`,
> `<clone_harness>`, `<clone_s7>`), each with its own approved artifact and its
> own write-target file. No target ever receives the same preimage-bound write
> twice.

### Exercise S7 (driver integration measurements) — on `<clone_s7>`, requires `PRECOND-SIGNING`

Run the real `alpha_driver` against the A-owned authority plane with a benign
approved definition, the write scope pointed at `<clone_s7>` (the write-scope
config's `controlled_verification` points at the hostile executable so that the
VERIFYING X-step also feeds ISO's descendant). **S7 requires `PRECOND-SIGNING`**
(D-E12-9): the three approvals below are real and S1-verified. If signing is not
authorized, **skip S7 entirely and record every S7 row `NOT TESTED`** — ISO and
HARNESS have already covered the isolation core and the writer/verifier
compatibility without it.

9. **(O → A)** Walk the approval verbs (`status`, `request-approval`,
   `record-approval` ×3 for contract, plan activation and exact diff), each A
   invocation redirected by `cmd.exe` into `published\driver-<nnn>-<verb>.json`.
   O signs each challenge with the real authenticator in **O's own session**
   (`PRECOND-SIGNING`; runbook §A4). **Time each invocation** — the per-invocation
   FD-16 re-proof cost (`S7-DURATION`; offline a hold-stage `status` is ~10 s,
   §9 driver doc — measure on host).
10. **(A)** `run` (the long invocation). It announces the **write** step, flushes
    it to the redirected `published/` file, then blocks up to
    `CLAIM_WAIT_SECONDS` = **7200 s** waiting for the outbox.
    - **(A, second console)** While `run` waits, start a second `alpha_driver`
      invocation. Expect `StoreLockedError` — DL-1's exclusive lock
      (`S7-LOCK`).
    - **(O)** Confirm the write announcement is **readable in `published/` now**,
      before `run` returns (`S7-ANNOUNCE-WRITE`, and the single-stream finding,
      §7.1).
11. **(X-R)** In a fresh `cmd.exe` with **no** reviewer variables, run the two
    printed lines (frozen writer against `<clone_s7>`, then
    `type nul > …\outbox-<ticket>\complete`). A continues: M1,
    `IMPLEMENTATION_RETURNED`, announces the **verify** step. (This exercises the
    writer inside the real dispatch; the standalone HARNESS run, step 8, remains
    the authoritative compatibility evidence.)
12. **(X-R)** In a fresh `cmd.exe`, run `l2-verify-approved-file-edit` with the
    **hostile** config, redirect to the outbox, then `complete`. (This is the
    substitution of §1: the announced command is the review command, which E-12
    forbids because it calls a model; the operator runs the **verifier** instead
    — explicit decision `D-E12-3`, never a silent authority claim. The verifier
    really runs; it produces an execution *claim*, which A then classifies.) The
    bare verified `verification-result.v1` is **not** a `ReviewPacket`, so A
    classifies "anything else" → **RECOVERY_REQUIRED** (`S7-VERIFY-RECOVER`,
    expected).
13. **(A)** `run` returns exit **3** (RECOVERY_REQUIRED). Confirm the verify
    announcement and the final report are both in the one redirected file
    (`S7-ANNOUNCE-VERIFY`, and §7.1).
14. **(O)** Confirm every `published/driver-*.json` is readable by O and that
    X-R cannot open, add to, or alter `published/` (part of ISO's measurement;
    matrix `S7-PUBLISHED-ACL`).

ACCEPTANCE, the held planner decision, and the published acceptance **bundle**
are **NOT TESTED** by E-12 (they need a `verified` + `approve` claim, i.e., a
model, which E-12 never calls — signing the approvals does not provide one).
They are covered offline by the S7 suite. The matrix records them NOT TESTED
with that reason.

---

## 6. Mechanical pass/fail evidence by FD (summary; full table in the matrix)

| FD | What E-12 proves mechanically | Primary evidence |
|---|---|---|
| **FD-13** (identities & launch) | Three distinct SIDs; none in `Administrators`/`Backup Operators`; separate logon sessions; A started with `-I` | `whoami /user` and `/groups` per session; `query session`; the driver's `interpreter_not_isolated` refusal when `-I` is dropped |
| **FD-14** (access rights) | The adversary **provably launched and ran** (`ISO-ADVERSARY-*`); every hostile write/delete/rename/chown/re-permission attempt on every FD-14 object fails `ACCESS_DENIED`; the AuthZ effective rights for X-R's SID are within the table | `ISO-ADVERSARY-LAUNCH`/`-ACTIVE` (positive execution proof — a digest alone is insufficient); hostile-program log (diagnostic); `ISO-DIGEST-POST` reports no finding (no unexpected-name object, no write-once rewrite/deletion); an induced AuthZ check per object |
| **FD-16** (mechanical re-proof) | The proof passes before and after the rehearsal; one induced violation yields the exact `isolation_unproven:<category>` and exit 1 | `ISO-PROOF-PRE`/`-POST`; one negative induction (e.g., add a `Users` allow ACE → `object_unprotected`/`object_rights`) |
| **FD-17** (claim protocol) | A valid write claim is received (`stdout.json` + `complete`, X-R-owned, 1 link, no reparse, within cap); at least two live deviations refuse with the right `claim_refused:<category>` | the successful write-step M1; X-R plants an extra file (`unexpected_entry`) and a junction (`reparse_point`) in a disposable outbox |
| **FD-18** (observation) | M1−M0 = exactly the target (post-image); `.git` digest unchanged M0→M1; a planted junction/hard link in the tree refuses | the write-step observations in the bundle/`published/`; one induced reparse/hard-link → `ObservationError` |

The **negative** cases for FD-16/FD-17/FD-18 are exhaustively covered **offline**
in the suite (S0, S3, S4; §5.8.10 item 1). E-12 re-confirms the headline
positives and spot-checks a few deviations **live**, because the live question
is whether the OS enforces what the suite asserts on synthetic descriptors.

---

## 7. Findings from preparation (material questions raised, not resolved by code)

### 7.1 F-E12-1 — the `run` stdout is a single concatenated stream (material: observability)

`alpha_driver.main` installs `emit()`, which does `sys.stdout.write(json…)`
**followed by `sys.stdout.flush()`** for **every** announced X step and for the
final report
(`src/ai_dev_orchestrator/integration/alpha_driver.py:953`). The runbook
redirects that one stdout stream, once, into a single
`published\driver-<nnn>-run.json`.

Two consequences E-12 must confirm and the human must accept:

1. **Liveness is OK.** Because each announcement is explicitly flushed, its
   bytes reach the redirected file **before** `run` blocks on the 7200 s wait.
   O, reading `published/` concurrently (A owns, O reads), can therefore see the
   write announcement, and later the verify announcement, while `run` is still
   running. E-12 must confirm this empirically on the host (`S7-ANNOUNCE-WRITE`,
   `S7-ANNOUNCE-VERIFY`) — Windows file-redirection buffering across a
   concurrent reader is the open question, not the Python flush.
2. **One file holds several JSON documents.** The write announcement, the verify
   announcement and the final report are concatenated (separated by `\n\n`) in
   **one** file. A reader that `json.load`s the whole file will fail once a
   second document is appended. This is exactly the design's open S7 item
   ("whether the `run` stdout stream needs a documented separation between
   announcements and the final report", driver doc §10 / runbook §10).

**Minimal corrective options (for the human to choose — see D-E12-5):**
- **(a) Documentation only, preferred for now.** The runbook instructs O to
  treat `driver-*-run.json` as a **stream of JSON documents** split on the blank
  line, and to read the newest document; and instructs the operator that the
  announced X-step is the *last* document present while `run` is still blocked.
  No code change; stays within "preparation only".
- **(b) A later, separately authorized, additive change** to have the driver
  also write each announcement to its own `published\announce-<ticket>.json`
  (distinct file per X step) so the human never parses a growing multi-document
  file. This is a **code change and out of scope here**; recorded as a candidate
  only.

E-12 should gather the evidence (does (a) suffice on the host?) so the human can
decide between (a) and (b). Recommendation: ship (a); revisit (b) only if the
host rehearsal shows (a) is error-prone.

### 7.2 F-E12-2 — E-12 cannot reach the hold without a model (expected, not a defect)

Stated in §1 and §5. The hold, the planner recommendation, and the published
acceptance **bundle** (as opposed to the driver **reports**, which E-12 does
exercise) are not reachable in E-12. They are offline-covered. The human must
accept that `published/`-bundle ACL behavior for the **acceptance bundle
specifically** is confirmed by the general `published/` ACL check plus the
offline suite, not by a live bundle publication (matrix NOT TESTED rows).

### 7.3 F-E12-3 — A needs a measurement tool it does not ship

The §5.8.10 pass test and §5.0's measurement contract require A to manifest the
authority plane and classify any difference. `alpha_driver` has no such verb.
A can read its own plane roots (`state_root`, `published`, `inbox`,
`exchange_root`), the clone's `.git` (read), and the anchors (read), so A runs a
**standard-library measurement helper**, `e12_measure.py` (full body in the
runbook, §A3), with `python -I`. It has **five** modes: `tree` (per-root
manifest, recording path, size, `nlink`, reparse flag and SHA-256; with
`--exchange` it prunes **only** a top-level directory matching
`^outbox-[0-9a-f]{32}$`), `git` (the FD-18 `.git` control-set manifest), `strict`
(byte-identical-or-FAIL compare, for anchors / `.git` / the quiescent bracket),
`classify` (the full-window compare of one root against its own enumerated
expected-name allowlist, flagging write-once rewrites, deletions, unexpected-name
objects, reparse points and hard links), and `adversary` (confirms, from the
verifier report and the descendant's markers, that the hostile program actually
launched — not `refused-before-execution` — and stayed active ≥ the required
interval; §3.3, mandatory validation #8). The helper's rules are keyed to the
real frozen object names (`control-plane.sqlite3`, `aido-state-root.json`,
`evidence/verification/*.json`, `handoff-<ticket>/`, …) and it treats the SQLite
rollback journal `control-plane.sqlite3-journal` as the only tolerated transient
(there is no WAL).

This is a **rehearsal measurement tool the operator saves and reviews before
E-12** (like the hostile program), *not* a change to accepted code and *not*
committed as a module. It is invoked with `python -I` so the script directory
and user site are not on `sys.path` (no planted-module import), it reads bytes
only (it imports, executes and connects to nothing), and the owner/DACL
dimension it cannot read in the standard library is supplied instead by
`ISO-PROOF-PRE/-POST` and the admin `icacls`/AuthZ dump. Recorded so the
reviewer knows the measurement is operator-run, not driver-run.

### 7.4 Non-findings (confirmed consistent with the frozen contracts)

- The verifier's FD-14 `.git` read-only requirement and C-10 Git ownership are
  mutually satisfiable: X-R **owns** `.git` (passing Git's ownership check) but
  an `OWNER RIGHTS` ACE caps X-R at `READ_CONTROL`, so X-R still cannot write it
  (§5.8.3). E-12 confirms the frozen read-only Git set tolerates this.
- `CLAIM_WAIT_SECONDS` = 7200 s and the claim size caps
  (`MAX_WRITE_CLAIM_BYTES` 4 MiB, `MAX_REVIEW_CLAIM_BYTES` 16 MiB) are
  code constants; AUTH-PILOT records their values (FD-17). E-12 does not change
  them.

---

## 8. E-6 real-authenticator interoperability prerequisites (identified, not performed)

E-6 is a **separate** criterion from E-12: one throwaway challenge signed with
the real FIDO2 authenticator and verified in a throwaway state root, **plus the
induced-negative battery**, as the format-interoperability *acceptance* gate
(§5.1 FD-2 "Rehearsal"; E-6; driver doc §10). This document only **identifies
its prerequisites** so they can be provisioned alongside E-12; it does **not**
perform or satisfy E-6, which remains NOT PERFORMED and separately gated.

E-12 makes **no model call** in any exercise. It is *not* authenticator-free,
however: its S7 exercise requires three real, S1-verified approvals and so uses
the real authenticator in O's session (`PRECOND-SIGNING` / `D-E12-9`, §1 and
§9). That operational use is **not** E-6 and does not accept it — E-6's
induced-negative battery and acceptance verdict are out of E-12's scope. ISO and
HARNESS use no authenticator at all.

| Prerequisite | Detail (grounded in FD-1 / FD-2) |
|---|---|
| FIDO2 authenticator with user presence | A hardware key enrolled by the human: `ssh-keygen -t ed25519-sk -O application=ssh:aido-approval`. Private part never leaves the key. Key type exactly `sk-ssh-ed25519@openssh.com` |
| OpenSSH with `sk` support | `ssh-keygen -Y sign` available (OpenSSH ≥ 8.2) with the FIDO2 middleware/`libfido2` the key needs. AIDO never runs `ssh-keygen` — the human does |
| `cryptography` dependency installed | Ed25519 verification uses the pinned `cryptography` package (FD-1a); the attestation verifier is pure in-process |
| Approver registry entry | `approver-registry.v1` (throwaway, for E-6) at the constant path with the key's `public_key`, `application` = `ssh:aido-approval`, `fingerprint_sha256`, `require_user_verification`, `not_before`/`not_after`, `revoked=false`, provisioned with elevation and AIDO-unwritable |
| Protocol constants | SSHSIG namespace exactly `aido-approval@v1`; hash `sha512`; authenticator flag **user presence** (`0x01`); user verification (`0x04`) only if the registry entry requires it |
| Throwaway state root + driver/operator | A disposable `store.v4` state root; `alpha_driver request-approval` presents the challenge; `alpha_operator` builds the statement bytes; the human signs; `alpha_driver record-approval`/verifier rebuilds and verifies |
| Signing device decision (D-5) | **Recommended:** a device other than the AIDO host, to defeat T3 swapping the statement between display and signing. Same-host signing permitted only with the residual acknowledged; on the host, signing is in O's session, never X's |

Mechanical E-6 pass (for when it is authorized, not now): the verifier **accepts**
one real signature over the exact statement bytes, and **refuses** induced
negatives with the right category (`presence_missing`, `namespace_mismatch`,
`statement_mismatch`, `key_unknown`, `challenge_expired`, …). E-6 proves format
interoperability with the real authenticator; the offline suite already proves
the verifier logic with synthetic signatures.

---

## 9. Decisions requiring human authorization (deliverable 4)

Each must be signed in the AUTH-PILOT (or an E-12-specific authorization) before
execution. E-12 itself is **separately authorized** (§5.8.10, E-12 criterion).

| Id | Decision | Why it is the human's |
|---|---|---|
| **D-E12-1** | Authorize conducting E-12 at all, on a named provisioned host. | §5.8.10 requires separate authorization; it provisions accounts and runs a hostile program. |
| **D-E12-2** | Approve the **hostile verification program**'s exact behavior and confirm it is a benign prober (enumerated access attempts + logging only; no exfiltration, encryption or out-of-tree damage). | AIDO does not ship or author it; it runs repository-controlled code as X-R by design. |
| **D-E12-3** | Approve the **verifier-for-reviewer substitution** at the VERIFYING step (run `l2-verify-approved-file-edit` where the Alpha would run `l2-review-approved-file-edit`), accepting that the S7 attempt ends RECOVERY_REQUIRED and never reaches ACCEPTANCE. | Deviates from the announced command; required because E-12 permits no model. |
| **D-E12-4** | Name the rehearsal accounts and SIDs (A `aido-a-rehearsal`, **throwaway** X-R `aido-x-rehearsal`, O), the A launch mechanism (interactive vs S4U task), the **five mutually disjoint** boundary paths (`state_root`, `published`, `inbox`, `exchange_root`, and a per-exercise `clone`: `<clone_iso>`, `<clone_harness>`, `<clone_s7>`), and the rehearsal `identity-boundary.v1` digest for each exercise's clone. | FD-13/FD-16/`BoundaryPaths._disjoint`; E-12 must use a throwaway X-R, never the Alpha's X; the boundary is re-provisioned per clone. |
| **D-E12-5** | Choose the single-stream remedy of F-E12-1: **(a)** documentation-only now, or **(b)** schedule the additive per-announcement-file change later. | Observability contract for the human operator; (b) would be a separately authorized code change. |
| **D-E12-6** | Confirm host policy permits local standard accounts, (if S4U) batch-logon rights, and user switching — else E-12 is **blocked, no fallback** (D-17). | Infrastructure precondition outside AIDO's control. |
| **D-E12-7** | Decide the FD-14 ACL application mechanism and operator (elevated `icacls`/PowerShell, by an administrator), and who destroys X-R and archives the throwaway state root afterward. | Elevated actions AIDO never performs. |
| **D-E12-8** | Set the rehearsal **duration window** the hostile descendant runs (and so the quiescent bracket length, the `e12_measure.py adversary` minimum active interval, and the moment A takes the post manifests). | Determines coverage; longer windows exercise more descendant races; the window is the active-interval floor the adversary evidence is checked against. |
| **D-E12-9** (`PRECOND-SIGNING`) | Authorize provisioning the real FIDO2 signing capability (authenticator, OpenSSH `sk`, throwaway approver-registry entry) so **O signs the three S7 approvals** in O's session. This is the sole prerequisite that lifts the S7 rows out of `NOT TESTED`. | Reaching S7's write/verify/lock/RECOVERY_REQUIRED needs real S1-verified approvals; fabricating or bypassing them is forbidden. It is **not** E-6 and does not accept it (§1, §8); if not authorized, **ISO and HARNESS still run in full** (isolation core + writer/verifier compatibility are not signing-gated) and all S7 rows stay `NOT TESTED`. |

The following are **not** E-12 decisions and must not be bundled into it: any
real target repository, any model/endpoint/credential arrangement, the Alpha's
fresh X, AUTH-PILOT's E-4 content beyond the rehearsal, or **E-6's acceptance
battery and verdict** (distinct from D-E12-9, which authorizes only the
operational S7 approval signing). D-E12-9 does not perform or satisfy E-6.

---

## 10. GO / NO-GO recommendation (deliverable 5)

**Recommendation: NO-GO to execute E-12 today; GO to execute once the gating
conditions below are each met and signed.** Preparation is **under corrective
review (FU2)** and is not complete until FU2 is accepted.

**Scope coverage, by exercise (what a GO would and would not establish):**

| Exercise | Depends on signing? | On a no-signing host |
|---|---|---|
| **ISO** (isolation core, §5.8.10) | No | Runs in full; PASS/FAIL recorded |
| **HARNESS** (writer+verifier compatibility) | No | Runs in full to a `verified` outcome; PASS/FAIL recorded |
| **S7** (driver integration) | **Yes** (`PRECOND-SIGNING`) | **Skipped; every S7 row `NOT TESTED`** |

The overall verdict **must not** claim full HARNESS coverage from an S7 run that
did not happen, and **must not** claim S7 coverage on a no-signing host. HARNESS
coverage comes only from the standalone step-8 run reaching `verified`
(mandatory validation #9).

**Gating conditions (all required):**

1. **E-12 PREP FU2 accepted** (matrix `PRECOND-FU2`). These three documents are
   under corrective review; running against an unreviewed prep would measure an
   unsettled procedure. (This is the prep-side blocker. **S7 is not a blocker**:
   S0–S7 are independently **ACCEPTED/FROZEN for offline scope**, code frozen at
   `c7f9e64`.)
2. **The design + AMEND1 accepted (E-2)** and **S0–S7 accepted (E-3)** — already
   true for offline scope; confirm no code has changed since `c7f9e64`.
3. **D-E12-1 … D-E12-8 signed** (§9).
4. **`PRECOND-SIGNING` / D-E12-9** decided (§9). If authorized, the real signing
   capability is provisioned and S7 can run; if not, ISO and HARNESS run in full
   and **all S7 rows stay `NOT TESTED`**.
5. **Host policy confirmed** (D-E12-6 / §2.2); provisioning done with elevation
   (E-5): registry, `identity-boundary.v1` (its **five disjoint** paths per the
   active clone), the three accounts, the per-root FD-14 ACLs, A's task; AIDO runs
   non-elevated; A's FD-16 proof passes (`ISO-PROOF-PRE`).
6. **Each exercise's disposable clone + preimage-bound artifact, the hostile
   program, the benign HARNESS verifier script, and the `e12_measure.py` helper
   with its five per-root expected-name allowlists prepared and reviewed**
   (§3.1–§3.3, §5.0, D-E12-2), outside any real workspace.
7. **The full offline suite green at the baseline** (E-3). The S7 doc records
   5681 passed at `b9312195`; re-confirm at `c7f9e64` (do **not** re-run the full
   ~1h43m suite for this documentation-only FU2).

**Why GO is the right outcome once gated:** E-12 is the only place the OS-level
isolation the entire DL-4B authority model depends on is tested against a *real*
adversary rather than synthetic descriptors. The adversarial boundary analysis
(§3, §5.8.9) is thorough and the offline suite already asserts every category;
E-12's residual risk is confined to *provisioning correctness on the specific
host*, which is exactly what the rehearsal measures. The exercise is disposable
(throwaway accounts, synthetic repos, no model, no real target), so its blast
radius is contained.

**Fail conditions that end E-12 and block the Alpha** (no retry, repair or
cleanup — E-10):

- the adversary did **not** provably launch and run — the verifier returned
  `refused-before-execution`, or `e12_measure.py adversary` cannot confirm the
  descendant launched and stayed active ≥ the D-E12-8 window (`ISO-ADVERSARY-*`);
  a byte-identical plane with no running adversary is **INVALID, not a pass**;
- the FD-16 proof fails post-rehearsal (`ISO-PROOF-POST`);
- the quiescent bracket shows **any** difference across the five-root manifests
  (`ISO-DIGEST-Q`);
- the full-window `strict` compare shows any anchor or `.git`-control difference,
  or any root's `classify` compare reports a finding — a write-once rewrite or
  deletion, an unexpected-name object in any root, a reparse point, a hard link,
  or a change outside an enumerated A-owned growth name (`ISO-DIGEST-POST`);
- the standalone HARNESS writer or verifier refuses the detached HEAD or
  read-only `.git`, or the verifier does not reach `verified`;
- the host cannot provision the accounts or the five disjoint roots.

A failed attempt is **not** retried, repaired or cleaned up; the rehearsal ends.

**Final status: E-12 PREP FU2 IMPLEMENTED — PENDING INDEPENDENT REVIEW.
E-12 is NOT authorized or executable; E-6 NOT PERFORMED; AUTH-PILOT NOT
AUTHORIZED.**
