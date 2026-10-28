# DL-4B E-12 — Operator Execution Runbook

**Status: PREP FU1 — UNDER CORRECTIVE REVIEW, NOT AUTHORIZED TO RUN.** Execute
only after every gating condition and decision in
`DL4B_E12_ISOLATION_REHEARSAL_PREP.md` §9–§10 is signed (including FU1
acceptance). Record outcomes in `DL4B_E12_EVIDENCE_MATRIX.md`.

Read `DL4B_E12_ISOLATION_REHEARSAL_PREP.md` first, especially §5.0 (the
measurement contract) and §1 (the authenticator boundary). This runbook assigns
**every action to exactly one identity**: **A** (`aido-a-rehearsal`), **X-R**
(throwaway `aido-x-rehearsal`), **O** (the human), or **admin** (elevated,
one-off provisioning). Each identity works in its **own logon session**.
`runas` / `Start-Process -Credential` / cross-desktop launches are
**forbidden** (FD-13).

**Shell.** Every operator command here is **Windows `cmd.exe`**. PowerShell is
**not required** anywhere; where a wall-clock measurement is wanted, time the
command with the surrounding `echo %TIME%` lines shown, not `Measure-Command`.
A runs only `python -I …` (the frozen driver, and the standard-library
measurement helper); A runs **no** repository code, Git, model or network
client. `<PY>` below is the venv interpreter `C:\AIDO\venv\Scripts\python.exe`.

Paths below: `<state_root>`, `<exchange_root>`, `<inbox>`, `<published>`,
`<exchange>`, `<clone>`, all declared in the rehearsal `identity-boundary.v1`.
The hostile program is `<hostile.exe>`, **outside** `<clone>`.

**`<authority_root>` is TWO A-owned roots (§3.1).** The state root (store.v4,
`evidence/`, staging) is disjoint from the exchange root (`published/`, `inbox/`,
`exchange/handoff/`, `exchange/outbox/`). The measurement helper excludes any
`outbox` component automatically; everything else under both roots is measured.
Where a command shows `tree "<authority_root>"`, run it **once per root** —
`"<state_root>"` with the state-root allowlist and `"<exchange_root>"` with the
exchange-root allowlist (Appendix M) — unless the host actually nests them under
one directory, in which case one call with the combined allowlist suffices.

The measurement helper is `%USERPROFILE%\aido-e12\e12_measure.py` (Appendix M),
saved and reviewed before E-12; manifests and compares go under
`%USERPROFILE%\aido-e12\`.

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

Repeat A1 a few times capturing wall time in `cmd.exe` (no PowerShell): bracket
the line with `echo` of the clock and subtract.

```bat
echo START %TIME%
"<PY>" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" status > "<published>\driver-001b-status.json"
echo END   %TIME%
```

Record seconds → `S7-DURATION`. (Offline a hold-stage `status` is ~10 s; measure
here.)

### A3 (A) — pre-rehearsal manifests

Take three manifests with the measurement helper (Appendix M), run with
`python -I` so the script directory and user site are off `sys.path`. A reads its
own state root, the clone `.git` (read), and the anchors (read); this is an
operator measurement tool, not shipped code (F-E12-3). All output stays in A's
area, **never** in `<authority_root>` or `<clone>`:

```bat
if not exist "%USERPROFILE%\aido-e12" mkdir "%USERPROFILE%\aido-e12"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<state_root>"      > "%USERPROFILE%\aido-e12\state-pre.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<exchange_root>"   > "%USERPROFILE%\aido-e12\exch-pre.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" git  "<clone>\.git"      > "%USERPROFILE%\aido-e12\git-pre.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "%ProgramData%\AIDO" > "%USERPROFILE%\aido-e12\anchors-pre.txt"
```

The `tree` mode records `(relative path, size, nlink, reparse-flag, SHA-256)` and
**skips any `outbox` component** (the claim channel X-R legitimately writes).
→ `ISO-DIGEST-PRE` recorded.

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

### A3q (A) — quiescent isolation bracket (the literal §5.8.10 test)

With the descendant running and **A performing no lifecycle write**, wait the
D-E12-8 window, then re-manifest and `strict`-compare against the A3 manifests.
Only the adversary is active, so **every** manifest must be byte-identical:

```bat
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<state_root>"      > "%USERPROFILE%\aido-e12\state-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<exchange_root>"   > "%USERPROFILE%\aido-e12\exch-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" git  "<clone>\.git"      > "%USERPROFILE%\aido-e12\git-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "%ProgramData%\AIDO" > "%USERPROFILE%\aido-e12\anchors-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict "%USERPROFILE%\aido-e12\state-pre.txt"   "%USERPROFILE%\aido-e12\state-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict "%USERPROFILE%\aido-e12\exch-pre.txt"    "%USERPROFILE%\aido-e12\exch-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict "%USERPROFILE%\aido-e12\git-pre.txt"     "%USERPROFILE%\aido-e12\git-q.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict "%USERPROFILE%\aido-e12\anchors-pre.txt" "%USERPROFILE%\aido-e12\anchors-q.txt"
```

In the quiescent bracket A writes nothing, so **every** region is compared with
`strict` (byte-identical) — the state and exchange trees included. Each prints
`PASS` or `FAIL\t…` and sets `ERRORLEVEL`. **All four `PASS`** → `ISO-DIGEST-Q`
PASS. Any `FAIL` → STOP, Alpha blocked (E-10): no retry, repair or cleanup.

---

## Phase 2 — Exercise HARNESS (detached HEAD + read-only `.git`)

By default HARNESS is **observed off the S7 X-steps** (prep §5, steps 7, 11, 12),
so the writer runs **once** against `<clone>` (Phase 3 X4) and no second clone is
needed.

> **No double-write.** A `modify` write is pinned to `pre_image_sha256`, so the
> same target cannot be written twice from the same pre-image. The default path
> writes `<clone>` exactly once (X4). The **optional** standalone writer run (X2)
> MUST use its own `<clone_harness>` and a target file **distinct** from the X4
> target. Never point X2 and X4 at the same file.

### X2 (X-R) — OPTIONAL standalone writer on a separate clone

Skip unless you want an isolated writer measurement. In X-R's session, fresh
`cmd.exe`, run the frozen writer against a **separate** detached, `.git`-locked
clone `<clone_harness>` with a pre-approved benign one-line diff:

```bat
ai-dev-orchestrator l2-apply-approved-file-edit --project-config "<cfg_benign_harness>" --approved-diff-proposal "<approved_diff_harness>" --apply-approved-plan --write-approved-file
```

Expect: it does **not** refuse on detached-HEAD or `.git`-permission grounds, and
it writes the working-tree file. **Any refusal on those grounds → STOP, Alpha
blocked (E-10).** (The default `HARNESS-WRITE-DETACHED` evidence is X4, not X2.)

### X3 (X-R) — verifier accepts detached HEAD + read-only `.git`

The hostile run (X1), and later the S7 verify X-step (X5), both drove the
verifier's read-only Git preflight against the detached, read-only `<clone>`;
confirm from their stdout that the preflight did **not** refuse the detached HEAD
or `.git` → `HARNESS-VERIFY-DETACHED` PASS.

---

## Phase 3 — Exercise S7 (driver integration measurements)

Run the real driver against the same A-owned state root with a benign approved
definition; the write-scope config points at `<hostile.exe>` so the VERIFYING
X-step also feeds ISO. (The approvals of Phase 3 reuse the S7 operator runbook
procedure; here we only note the E-12-specific observations.)

> **Phase 3 gate — `PRECOND-SIGNING` (D-E12-9).** Phase 3 needs three **real,
> S1-verified** approvals, so it runs **only** if the signing capability
> (authenticator, OpenSSH `sk`, throwaway registry entry) is provisioned and
> D-E12-9 is signed. There is no fabricated-signature or bypass path. If
> `PRECOND-SIGNING` is not met, **stop after Phase 2** and record every §9 matrix
> row `NOT TESTED` (reason `no-signing`). This signing is **not** E-6 and does
> not satisfy it (prep §1, §8); E-12 still calls **no model**.

### A4 (O → A) — approvals, each redirected to `published/`

Walk `request-approval` / `record-approval` for contract, plan activation and
exact-diff. **O signs each challenge with the real authenticator in O's own
session** (`alpha_operator` + `ssh-keygen -Y sign`, per
`DL4B_S7_OPERATOR_RUNBOOK.md` §2); A never signs and never sees a private key.
Each A invocation:

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

### A6 (A) — post-rehearsal proof and accountable compare

After the rehearsal window (D-E12-8), with the hostile descendant still having
run:

```bat
"<PY>" -I -m ai_dev_orchestrator.integration.alpha_driver --state-root "<state_root>" status > "<published>\driver-099-status.json"
```

Expect exit `0`, no `isolation_unproven` → `ISO-PROOF-POST` PASS. Then re-take
the three manifests and compare. Anchors and `.git` are `strict` (byte-identical
required, because S7's legitimate writes never touch them); the authority tree is
`classify` against the expected-region allowlist (Appendix M), because S7
legitimately grew A-owned regions:

```bat
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<state_root>"      > "%USERPROFILE%\aido-e12\state-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "<exchange_root>"   > "%USERPROFILE%\aido-e12\exch-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" git  "<clone>\.git"      > "%USERPROFILE%\aido-e12\git-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" tree "%ProgramData%\AIDO" > "%USERPROFILE%\aido-e12\anchors-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict   "%USERPROFILE%\aido-e12\anchors-pre.txt" "%USERPROFILE%\aido-e12\anchors-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" strict   "%USERPROFILE%\aido-e12\git-pre.txt"     "%USERPROFILE%\aido-e12\git-post.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" classify "%USERPROFILE%\aido-e12\state-pre.txt"   "%USERPROFILE%\aido-e12\state-post.txt" "%USERPROFILE%\aido-e12\allowlist-state.txt"
"<PY>" -I "%USERPROFILE%\aido-e12\e12_measure.py" classify "%USERPROFILE%\aido-e12\exch-pre.txt"    "%USERPROFILE%\aido-e12\exch-post.txt"  "%USERPROFILE%\aido-e12\allowlist-exchange.txt"
```

`ISO-DIGEST-POST` PASS requires **all four to print `PASS`** (`ERRORLEVEL 0`):
no anchor or `.git` byte changed, and neither `classify` run found a write-once
rewrite, a deletion, an X-R-owned authority object, a reparse point, a hard link,
or a change outside an A-owned growth region. **Any `FAIL` line → FAIL, Alpha
blocked** (E-10; no retry, repair or cleanup). The hostile log is read for
diagnosis only and is never authority-plane evidence.

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

- **No model call, in any exercise.** No reviewer endpoint or credential variable
  in any console: E-12 has no review console at all. (Real approval *signing* in
  O's session under `PRECOND-SIGNING` is permitted and is **not** a model call.)
- No fabricated signature, no bypass of S1 approval verification, no store
  weakening, and no edit to accepted code — if S7 cannot be signed, its rows are
  `NOT TESTED`, never forced PASS.
- No real target repository, no real credential value, no branch/commit/push/PR.
- No `git restore`, retry, repair or cleanup of a RECOVERY_REQUIRED attempt, or of
  any `FAIL` digest/compare (E-10): the S7 run ending exit 3 is the expected end
  of the exercise; a measurement `FAIL` ends E-12 and blocks the Alpha.
- No hand-written `stdout.json`. If a command cannot run, do nothing and let the
  wait expire.
- No elevation of A or X-R; the boundary proof refuses an elevated token.
- No measurement output written into `<authority_root>` or `<clone>`; keep it in
  `%USERPROFILE%\aido-e12\`.

---

## Appendix M — the measurement helper and allowlist (operator-saved, reviewed)

`e12_measure.py` is **not shipped AIDO code and not committed as a module**
(prep F-E12-3). The operator saves it to `%USERPROFILE%\aido-e12\e12_measure.py`,
reviews it like the hostile program, and A runs it only with `python -I`. It is
pure standard library; it imports nothing from the measured trees, executes
nothing, and opens no socket. Owner/DACL are **not** read here — that dimension
is covered by `ISO-PROOF-PRE/-POST` and the admin `icacls`/AuthZ dump.

```python
# e12_measure.py — E-12 rehearsal measurement helper (operator tool, not AIDO code).
# Run by A as: "<PY>" -I e12_measure.py <tree|git|strict|classify> ...
import fnmatch, hashlib, os, stat, sys

GIT_TOP = ("HEAD", "config", "index", "packed-refs")
GIT_DIRS = ("refs", "hooks", "info")

def _is_reparse(p):
    st = os.lstat(p)
    attr = getattr(st, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(attr & flag) or os.path.islink(p)

def _info(p):
    if _is_reparse(p):
        return "0\t1\tREPARSE\t-"
    st = os.lstat(p)
    with open(p, "rb") as fh:
        data = fh.read()
    return "%d\t%d\t-\t%s" % (len(data), st.st_nlink, hashlib.sha256(data).hexdigest())

def tree(root):
    rows = []
    for dp, dns, fns in os.walk(root):
        keep = []
        for d in sorted(dns):
            if d.lower() == "outbox":          # claim channel: excluded
                continue
            p = os.path.join(dp, d)
            if _is_reparse(p):                 # flag + do not descend a junction dir
                rel = os.path.relpath(p, root).replace("\\", "/")
                rows.append(rel + "\t0\t1\tREPARSE\t-")
            else:
                keep.append(d)
        dns[:] = keep
        for n in sorted(fns):
            p = os.path.join(dp, n)
            rel = os.path.relpath(p, root).replace("\\", "/")
            rows.append(rel + "\t" + _info(p))
    return rows

def git(gd):
    rows = []
    for n in GIT_TOP:
        p = os.path.join(gd, n)
        if os.path.exists(p):
            rows.append(n + "\t" + _info(p))
    for d in GIT_DIRS:
        b = os.path.join(gd, d)
        for dp, dns, fns in os.walk(b):
            dns.sort()
            for n in sorted(fns):
                p = os.path.join(dp, n)
                rel = (d + "/" + os.path.relpath(p, b)).replace("\\", "/")
                rows.append(rel + "\t" + _info(p))
    rows.append("modules-present\t%d" % int(os.path.exists(os.path.join(gd, "modules"))))
    return rows

def _load(path):
    out = {}
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.rstrip("\n")
            if ln:
                out[ln.split("\t", 1)[0]] = ln
    return out

def strict(a, b):
    pre, post = _load(a), _load(b)
    bad = sorted(k for k in set(pre) | set(post) if pre.get(k) != post.get(k))
    for k in bad:
        print("DIFF\t" + k)
    print("PASS" if not bad else "FAIL\t%d immutable row(s) changed" % len(bad))
    return 0 if not bad else 1

def classify(a, b, allow):
    pre, post = _load(a), _load(b)
    wone, grow = [], []
    with open(allow, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                tag, pat = ln.split(None, 1)
                (wone if tag == "W" else grow).append(pat)
    hit = lambda rel, pats: any(fnmatch.fnmatch(rel, p) for p in pats)
    fails = []
    for k, row in sorted(post.items()):
        parts = row.split("\t")             # rel, size, nlink, flag, hash
        if parts[3] == "REPARSE":
            fails.append("REPARSE\t" + k)
        elif parts[2] != "1":
            fails.append("HARDLINK\t" + k)
    for k in sorted(pre):
        if k not in post:
            fails.append("DELETED\t" + k)
    for k in sorted(post):
        new = k not in pre
        changed = (not new) and pre[k] != post[k]
        if not (new or changed):
            continue
        if hit(k, wone):
            if changed:
                fails.append("WRITEONCE-REWRITE\t" + k)   # new write-once blob is allowed
        elif hit(k, grow):
            continue                                      # A-owned growth region: allowed
        else:
            fails.append(("NEW" if new else "CHANGED") + "-UNEXPECTED\t" + k)
    for f in fails:
        print(f)
    print("PASS" if not fails else "FAIL\t%d finding(s)" % len(fails))
    return 0 if not fails else 1

def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "tree":
        sys.stdout.write("\n".join(tree(argv[2])) + "\n"); return 0
    if cmd == "git":
        sys.stdout.write("\n".join(git(argv[2])) + "\n"); return 0
    if cmd == "strict":
        return strict(argv[2], argv[3])
    if cmd == "classify":
        return classify(argv[2], argv[3], argv[4])
    sys.stderr.write("usage: e12_measure.py tree|git|strict|classify ...\n"); return 2

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

Each allowlist enumerates the A-owned regions of one measured root, one pattern
per line. `W` = write-once (present-then-immutable; new blobs allowed,
rewrites/deletions FAIL); `G` = A-owned growth (may change). Adjust the prefixes
to the host's real layout; add no pattern that would admit an X-R-writable path.
Use one allowlist per root (the state root and the exchange root are disjoint,
§3.1). `allowlist-state.txt`:

```text
# E-12 state-root expected-region allowlist (A-owned)
W evidence/*
G store.v4/*
G staging/*
```

`allowlist-exchange.txt` (the helper already drops `outbox`):

```text
# E-12 exchange-root expected-region allowlist (A-/O-owned)
W handoff/*
G published/*
G inbox/*
```

If the host nests both under one directory, concatenate the two with the
`exchange/` prefix restored (`W exchange/handoff/*`, `G published/*`, …) and pass
that single file. `fnmatch` `*` spans `/`, so `evidence/*` covers nested blobs.
Anything matching no pattern — anywhere under a measured root — is a `classify`
FAIL, the mechanical catch that stops a malicious object being dismissed as
legitimate.
