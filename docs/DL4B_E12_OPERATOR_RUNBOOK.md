# DL-4B E-12 — Operator Execution Runbook

**Status: PREPARATION ONLY — NOT AUTHORIZED TO RUN.** Execute only after every
gating condition and decision in `DL4B_E12_ISOLATION_REHEARSAL_PREP.md` §8–§9 is
signed. Record outcomes in `DL4B_E12_EVIDENCE_MATRIX.md`.

Read `DL4B_E12_ISOLATION_REHEARSAL_PREP.md` first. This runbook assigns **every
action to exactly one identity**: **A** (`aido-a-rehearsal`), **X-R**
(throwaway `aido-x-rehearsal`), **O** (the human), or **admin** (elevated,
one-off provisioning). Each identity works in its **own logon session**.
`runas` / `Start-Process -Credential` / cross-desktop launches are
**forbidden** (FD-13).

Paths below: `<state_root>`, `<inbox>`, `<published>`, `<exchange>`, `<clone>`,
all declared in the rehearsal `identity-boundary.v1`. The hostile program is
`<hostile.exe>`, **outside** `<clone>`.

---

## Phase 0 — provisioning (admin, elevated, once)

| # | Who | Action | Confirms |
|---|---|---|---|
| 0.1 | admin | Confirm host policy allows local standard accounts, (if S4U) "log on as a batch job", and user switching. If not, **STOP — E-12 is blocked (D-17)** | `PRECOND-POLICY` |
| 0.2 | admin | Create standard accounts `aido-a-rehearsal`, `aido-x-rehearsal` (throwaway), confirm O exists. None in `Administrators`/`Backup Operators` | `FD13-SIDS`, `FD13-GROUPS` |
| 0.3 | admin | Write `%ProgramData%\AIDO\identity-boundary.v1.json` (rehearsal SIDs + paths) and `approver-registry.v1.json` at their code-constant paths; apply anchor ACLs (read-only to A/X-R/O) | `FD16-ANCHORS` |
| 0.4 | admin | Create `<state_root>` (A-owned, empty, non-Git), `<inbox>`, `<published>`, `<exchange>`; apply the FD-14 protected DACLs (prep §3.1) | `FD14-STATEROOT-ACL` |
| 0.5 | X-R | `git clone` the synthetic repo into `<clone>`, checkout **detached** at `base_head_oid`; confirm no hooks, no submodules | `HARNESS-DETACHED-SETUP` |
| 0.6 | admin | Apply the clone ACLs (prep §3.2): working tree X-R-modify + `OWNER RIGHTS`; `.git` X-R read+execute only via `OWNER RIGHTS`; root no DELETE/`WRITE_DAC`/`WRITE_OWNER` for X-R. **Before any harness runs** | `FD14-CLONE-ACL`, `HARNESS-OWNER` |
| 0.7 | admin | Provision A's launch: A's interactive session via secure logon UI, **or** an S4U task (no stored password, fixed `python -I` action, O granted run only) | `FD13-LAUNCH` |

A one-off AuthZ effective-rights spot check per FD-14 object (for X-R's SID) may
be run here by admin to pre-confirm `FD14-EFFECTIVE`.

---

## Phase 1 — Exercise ISO (adversarial isolation core)

### A1 (A) — open and prove

In A's session, `cmd.exe`, isolated:

```bat
"C:\AIDO\venv\Scripts\python.exe" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" status > "<published>\driver-001-status.json"
```

Expect exit `0` and no `isolation_unproven` refusal → `ISO-PROOF-PRE` PASS.
(If it refuses `IsolationUnprovenError:<category>`, provisioning is wrong — fix
as admin and re-run; do not proceed.)

### A2 (A) — time the proof

Repeat A1 a few times capturing wall time (PowerShell `Measure-Command`, or wrap
the `cmd.exe` line). Record seconds → `S7-DURATION`. (Offline a hold-stage
`status` is ~10 s; measure here.)

### A3 (A) — pre-rehearsal digest

Run this **isolated-Python helper** in A's session (A reads its own state root;
this is an operator measurement tool, not shipped code — F-E12-3):

```bash
python -I - "<state_root>" "<clone>\.git" > "%USERPROFILE%\aido-e12\digest-pre.txt" <<'PY'
import hashlib, os, sys
def manifest(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            p = os.path.join(dirpath, name)
            rel = os.path.relpath(p, root).replace("\\", "/")
            with open(p, "rb") as fh:
                data = fh.read()
            out.append(f"{rel}\t{len(data)}\t{hashlib.sha256(data).hexdigest()}")
    return "\n".join(out)
for root in sys.argv[1:]:
    print(f"=== {root} ===")
    print(manifest(root))
PY
```

Keep `digest-pre.txt` in O's or A's area (not in `<state_root>`). → `ISO-DIGEST-PRE` recorded.

### X1 (X-R) — launch the adversary

In X-R's session, fresh `cmd.exe`, **no** reviewer variables, run
`l2-verify-approved-file-edit` with the throwaway config whose
`controlled_verification` executable is `<hostile.exe>`:

```bat
ai-dev-orchestrator l2-verify-approved-file-edit --project-config "<cfg_hostile>" --approved-diff-proposal "<approved_diff>" --apply-approved-plan --verify-approved-file-edit
```

`<hostile.exe>` spawns a detached descendant that hammers the attack set
(prep §3.3) for the rehearsal window (D-E12-8). Leave it running through
Phase 2 and 3.

---

## Phase 2 — Exercise HARNESS (detached HEAD + read-only `.git`)

> **No double-write.** A `modify` write is pinned to `pre_image_sha256`. Use a
> **separate** throwaway clone + state root for Phase 2, **or** skip X2 and let
> the driver-driven write in Phase 3 (X4) be the writer's detached-HEAD /
> read-only-`.git` confirmation. Never point X2 and X4 at the same target file.

### X2 (X-R) — writer accepts detached HEAD + read-only `.git`

In X-R's session, fresh `cmd.exe`, run the frozen writer against the detached,
`.git`-locked clone with a pre-approved benign one-line diff:

```bat
ai-dev-orchestrator l2-apply-approved-file-edit --project-config "<cfg_benign>" --approved-diff-proposal "<approved_diff>" --apply-approved-plan --write-approved-file
```

Expect: it does **not** refuse on detached-HEAD or `.git`-permission grounds,
and it writes the working-tree file → `HARNESS-WRITE-DETACHED` PASS.
**Any refusal on those grounds → STOP, Alpha blocked (E-10).**

### X3 (X-R) — verifier accepts detached HEAD + read-only `.git`

The hostile run (X1) already drove the verifier's read-only Git preflight
against the detached, read-only clone; confirm from its stdout that the
preflight did **not** refuse the detached HEAD or `.git` →
`HARNESS-VERIFY-DETACHED` PASS. (Optionally re-run once with a benign config to
confirm in isolation.)

---

## Phase 3 — Exercise S7 (driver integration measurements)

Run the real driver against a throwaway state root with a benign approved
definition; the write-scope config points at `<hostile.exe>` so the VERIFYING
X-step also feeds ISO. (The approvals of Phase 3 reuse the S7 operator runbook
procedure; here we only note the E-12-specific observations.)

### A4 (A) — approvals, each redirected to `published/`

Walk `request-approval` / `record-approval` for contract, plan activation and
exact-diff (O signs with `alpha_operator` + `ssh-keygen -Y sign` in O's session,
per `DL4B_S7_OPERATOR_RUNBOOK.md` §2). Each A invocation:

```bat
"C:\AIDO\venv\Scripts\python.exe" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" <verb> > "<published>\driver-<nnn>-<verb>.json"
```

→ confirm each file is created with the protected DACL inherited and readable by
O (`S7-PUBLISHED-ACL`); time them (`S7-DURATION`).

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
printed (frozen writer, then the marker), exactly as printed:

```bat
ai-dev-orchestrator l2-apply-approved-file-edit --project-config "...\project.yaml" --approved-diff-proposal "...\approved-diff-proposal.json" --apply-approved-plan --write-approved-file > "...\stdout.json"
type nul > "...\complete"
```

Create `complete` **only after** the command exits, whatever its exit code. Put
**nothing else** in the outbox. A continues: M1, `IMPLEMENTATION_RETURNED`, then
announces the **verify** step → `S7-ANNOUNCE-VERIFY` (O re-reads the growing
file). M1 shows exactly the target changed, `.git` unchanged → `FD18-M1`.

### X5 (X-R) — the verify X-step (substitution, D-E12-3)

Fresh `cmd.exe`. Run `l2-verify-approved-file-edit` with `<cfg_hostile>`,
redirect to the outbox, then `complete`:

```bat
ai-dev-orchestrator l2-verify-approved-file-edit --project-config "<cfg_hostile>" --approved-diff-proposal "<approved_diff>" --apply-approved-plan --verify-approved-file-edit > "...\stdout.json"
type nul > "...\complete"
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

### A6 (A) — post-rehearsal proof and digest

After the rehearsal window (D-E12-8), with the hostile descendant still having
run:

```bat
"C:\AIDO\venv\Scripts\python.exe" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" status > "<published>\driver-099-status.json"
```

Expect exit `0`, no `isolation_unproven` → `ISO-PROOF-POST` PASS. Re-run the A3
helper into `digest-post.txt`; `fc` / compare against `digest-pre.txt`:

```bat
fc "%USERPROFILE%\aido-e12\digest-pre.txt" "%USERPROFILE%\aido-e12\digest-post.txt"
```

**No differences** in any state-root byte, any `published/` bundle byte, or the
`.git` control digest → `ISO-DIGEST-POST` PASS. **Any difference → FAIL, Alpha
blocked.**

### A7 (A) — induced negatives (one each, to confirm detection is live)

- Have admin add a `Users:(R)` allow ACE to one state-root object, re-run
  `status`; expect `isolation_unproven:object_unprotected` (or `object_rights`)
  and exit 1 → `FD16-NEG`. Revert.
- (FD-17/FD-18 negatives above already recorded.)

### Z (admin) — teardown

Collect the hostile log (diagnostic only), archive the throwaway `<state_root>`
and digests, **disable/delete X-R**, and re-provision `identity-boundary.v1`
with the Alpha's fresh `X` **only when the Alpha itself is authorized** (not as
part of E-12 teardown unless AUTH-PILOT says so).

---

## What must never happen during E-12

- No model call, no reviewer variables in any console except where the Alpha
  would (and E-12 has none).
- No real target repository, no real credential value, no branch/commit/push/PR.
- No `git restore`, retry, repair or cleanup of a RECOVERY_REQUIRED attempt
  (E-10): the S7 run ending exit 3 is the expected end of the exercise.
- No hand-written `stdout.json`. If a command cannot run, do nothing and let the
  wait expire.
- No elevation of A or X-R; the boundary proof refuses an elevated token.
