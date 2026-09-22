# Phase 5F3B-HARNESS-CFG1-LIVE-S1-A3-AUTH — Fresh Stage-1 Execution Authorization (R5)

```text
5F3B-HARNESS-CFG1-LIVE-S1-A3-AUTH CANDIDATE (R5)
PENDING CONTENT REVIEW + POST-COMMIT CLOSURE REVIEW
```

> **THIS DOCUMENT IS A CANDIDATE. IT IS NOT AN AUTHORIZATION.**
>
> It carries no execution authority of any kind. Authority can arise **only**
> through the two-step procedure of §2, and **only** from the post-commit
> closure reviewer's record, which lives outside this file. Until that record
> exists, `CFG1-S1-A3` is **NOT AUTHORIZED**.
>
> The turns that authored this file imported no CFG1, AR2 or qualification
> module, called neither `establish_stage_output_authority` nor
> `run_cfg1_stage`, launched no Pi process, contacted no B300 endpoint, opened
> no socket, made no model call, read no credential or endpoint value, created
> nothing under the CFG1 results root, modified no other file, and committed
> nothing. Authoring this file is never permission to execute A3 in the same
> turn, session, or agent invocation.

Earlier candidate texts of this file (R1, R2, R3, R4) have no standing. Their
bytes, digests, launcher digests, status labels and wording are not authority,
and content acceptance of any of them grants nothing for this R5. §13 records
what R3, R4 and R5 changed.

---

## 0. Authority relationship

This document is subordinate to, in order:

1. the frozen design,
   [`PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md);
2. the accepted/frozen amendment **CFG1-L16-FU2 R2**,
   [`PHASE_5F3B_HARNESS_CFG1_L16_FU2_RUNTIME_CAPABILITY_OBSERVATION_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_L16_FU2_RUNTIME_CAPABILITY_OBSERVATION_DESIGN.md),
   with its accepted/frozen erratum **ERR1**,
   [`PHASE_5F3B_HARNESS_CFG1_L16_FU2_ERR1_R37_SIDECAR_TRANSPORT_ERRATUM.md`](PHASE_5F3B_HARNESS_CFG1_L16_FU2_ERR1_R37_SIDECAR_TRANSPORT_ERRATUM.md);
3. the shipped code at the frozen FU2 implementation commit
   `bfae384370246e0ab4073a28a6b6df0558153864`.

Where this document could be read as disagreeing with any of them, **they
govern and this document is wrong**. Where it could be read as disagreeing with
the shipped code, **the code's fail-closed refusal governs**. Nothing here
instructs any layer to accept an input it would refuse or to skip a proof it
would perform.

The A1 and A2 authorizations
([A1](PHASE_5F3B_HARNESS_CFG1_LIVE_S1_AUTHORIZATION.md),
[A2](PHASE_5F3B_HARNESS_CFG1_LIVE_S1_A2_AUTHORIZATION.md)) were bound to HEAD
`eea76c100895ca0be028ba474682a15487a53c2e`. FU2 changed production code in CFG1
and AR2, so **neither scope is reusable** (FU2 §12.3). A3 is not an extension of
either; it states its own bound in §6.

### 0.1 Frozen FU2 §14 prerequisites

| FU2 §14 item | Status |
|---|---|
| 1–2 — R2 design accepted | accepted / frozen (recorded outside this file) |
| 3–4 — FU2 implementation complete and independently accepted | accepted / frozen at `bfae384370246e0ab4073a28a6b6df0558153864` |
| 5 — documentation pointers in the frozen CFG1 design and AR2 docs | **satisfied** by DOCSYNC `820e8c58d63acc016df8c3f5762b3056beb3538e` (accepted / frozen) |
| 6 — new, separately reviewed A3 document, new id, bound to the new HEAD, A1/A2 consumed and non-participating | **this candidate**; binding defined in §2 |

Item 5 is satisfied. No waiver, exception, or reviewer discretion regarding
item 5 exists in this document.

---

## 1. Git provenance of the code that will run

The provenance chain is concrete, three commits long, and closed:

```text
bfae384370246e0ab4073a28a6b6df0558153864   frozen CFG1-L16-FU2 implementation
        │
820e8c58d63acc016df8c3f5762b3056beb3538e   accepted/frozen DOCSYNC
        │   (parent == bfae384…; changes exactly:
        │     docs/PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md
        │     experiments/pi_external_runtime_ar2/README.md
        │     experiments/pi_external_runtime_ar2/FINDINGS.md)
        │
<A3_AUTH_COMMIT>                           exactly one commit adding exactly
                                           docs/PHASE_5F3B_HARNESS_CFG1_LIVE_S1_A3_AUTHORIZATION.md
```

Consequence: the **tracked** source at `<A3_AUTH_COMMIT>` is exactly the FU2
implementation source at `bfae384…`, because every commit after it changes
Markdown only, and each such change is named above by path.

Git provenance alone does **not** prove that the launcher process executes that
source. Python resolves imports from the interpreter's import machinery, not
from Git. The pre-consumption source-origin gate of §7 closes that gap; without
it, exact HEAD is necessary but not sufficient.

**There is no equivalence class.** No descendant of `<A3_AUTH_COMMIT>`, no
sibling, no rebase or amend of it, no cherry-pick of it, and no commit whose
diff "only touches documentation" is covered. No caller, operator, or reviewer
decides semantic equivalence. Any other HEAD — including one that differs only
by a later docs commit — is outside this authorization, and execution there
requires a new authorization.

---

## 2. Two-step acceptance and the concrete post-commit binding

The candidate cannot contain its own future commit SHA or its own digest. The
binding is therefore established outside this file, in this exact order.

### 2.1 Step 1 — content review (grants nothing)

An independent reviewer reviews the exact candidate bytes and records, outside
the repository:

- the SHA-256 of the exact candidate file bytes reviewed, `CANDIDATE_SHA256`;
- the Git blob id of those bytes, `CANDIDATE_BLOB` (e.g. `git hash-object --
  <path>`, which reads only and writes no object);
- `LAUNCHER_SHA256`: the SHA-256 of the launcher text of §7.3, defined as the
  exact lines strictly between the opening ` ```python ` fence line and its
  closing fence line, each terminated by one LF, with no other bytes;
- the verdict.

The candidate is required to be LF-only (no CR byte). This matters because this
checkout has `core.autocrlf=true`: an LF-only file is stored unchanged, so the
committed blob can be byte-identical to the reviewed bytes. A candidate
containing CR bytes, or any mismatch in §2.3, fails closed.

**Content acceptance grants NO live execution authority**, under any
circumstances, including if the operator later believes the commit is correct.

### 2.2 Step 2 — the operator commits exactly this one file

The operator commits the content-reviewed file, unchanged, as **one** commit
whose **direct parent is `820e8c58d63acc016df8c3f5762b3056beb3538e`**, and
which adds exactly `docs/PHASE_5F3B_HARNESS_CFG1_LIVE_S1_A3_AUTHORIZATION.md`
and nothing else. The commit's SHA becomes `<A3_AUTH_COMMIT>`. This step
grants nothing.

### 2.3 Step 3 — post-commit closure review

An independent reviewer inspects `<A3_AUTH_COMMIT>` and verifies, mechanically
and read-only:

| # | Fact | Read-only method (illustrative) |
|---|---|---|
| P1 | direct parent is exactly `820e8c58d63acc016df8c3f5762b3056beb3538e`, and it is the only parent | `git rev-list --parents -n 1 <A3_AUTH_COMMIT>` |
| P2 | the commit changes exactly one path, this file, as an addition | `git diff-tree --no-commit-id -r --name-status <A3_AUTH_COMMIT>` → exactly `A` + this path |
| P3 | committed blob id == `CANDIDATE_BLOB` | `git rev-parse <A3_AUTH_COMMIT>:docs/PHASE_5F3B_HARNESS_CFG1_LIVE_S1_A3_AUTHORIZATION.md` |
| P4 | SHA-256 of committed blob bytes == `CANDIDATE_SHA256` | `git cat-file blob <A3_AUTH_COMMIT>:<path>` written to a file outside the checkout, then `certutil -hashfile <that file> SHA256` |
| P5 | no A1/A2 (or any) result artifact is committed | `git ls-tree -r --name-only <A3_AUTH_COMMIT> -- experiments/pi_harness_cfg1/results` → empty |
| P6 | the parent chain above `820e8c…` is the frozen chain | `git rev-parse 820e8c58d63acc016df8c3f5762b3056beb3538e^` → `bfae384370246e0ab4073a28a6b6df0558153864` |

Any failure → **not accepted**; nothing is repaired, amended, or re-labelled
into acceptance. A corrected file requires a new content review and a new
commit.

### 2.4 Step 4 — the only source of authority

**Only the post-commit closure reviewer's record** may mark
`CFG1-S1-A3-AUTH` **ACCEPTED / FROZEN** and authorize the one A3 execution.
That record must name, verbatim:

- `<A3_AUTH_COMMIT>` (full 40-hex SHA);
- `A3_AUTH_BLOB` (the committed blob id, == `CANDIDATE_BLOB`);
- `CANDIDATE_SHA256`;
- `LAUNCHER_SHA256`;
- P1–P6 as verified;
- that, per the reviewed operator/authorization history, no `CFG1-S1-A3`
  invocation is known or has been authorized (§3.2 (a)).

The record lives **outside** the repository branch being executed. Recording it
as a further commit on that branch would move HEAD off `<A3_AUTH_COMMIT>` and
make admission fact A1 (§5) fail; that is the intended, fail-closed result, not
something to be reasoned around.

This file contains no self-acceptance clause, no conditional activation, and no
"valid unless objected to" wording.

---

## 3. The A3 identity

### 3.1 The literal

```text
CFG1-S1-A3
```

This is the only authorization-supplied value in this document. It is a fixed,
human-chosen ASCII literal of length 10 matching the frozen grammar
`[A-Za-z0-9_-]{1,64}` (`stage_output.STAGE_EXECUTION_ID_PATTERN`, applied by
`fullmatch` with `type(value) is str`). It contains no `/`, `\`, `.`, `:`,
whitespace, control or non-ASCII character. It is transmitted verbatim, never
normalized, and encodes no clock, counter, host or process value.

### 3.2 What "unused" rests on — three grounds and one residual

The literal already appears as a named future identifier in two frozen
documents (the FU2 R2 design and the DOCSYNC pointer in the frozen CFG1 design)
and in this file; none of those is a use. Whether `CFG1-S1-A3` has ever been
passed to `establish_stage_output_authority` rests on three distinct grounds,
each with its own strength:

**(a) Reviewed operator/authorization history (attestation, not mechanical
proof).** `CFG1-S1-A3` has never been authorized, and no invocation with it is
known. This is a human record: the post-commit acceptance record states it
(§2.4), and the operator re-attests it at admission (§5, A0). It is the only
ground that speaks to calls which left no trace.

**(b) Filesystem proof (mechanical, and limited).** No surviving A3 execution
directory or A3 run artifact exists (§5, A6). Observed at authoring time in
this checkout, read-only:

| Check | Result |
|---|---|
| `RESULTS_ROOT/CFG1-S1-A3` exists | **absent** |
| any path containing `CFG1-S1-A3` in the working tree (excluding `.git/`, `.venv/`) | none |
| any path containing `CFG1-S1-A3` in any reachable commit | none |
| `RESULTS_ROOT` contents (full untracked listing, no exclude rules) | exactly the four A1/A2 files of §4 |

This proves the absence of a **surviving** namespace or artifact. It does
**not** prove that no establishment call ever occurred.

**(c) Runtime exclusive create (mechanical, after namespace creation).** Once
an establishment call has created `RESULTS_ROOT/CFG1-S1-A3`, any later call
with the same literal is refused at `EXECUTION_DIRECTORY_EXISTS`, before any
run. This prevents reuse only for calls that got as far as creating the
namespace, and only while that directory survives.

**Residual (stated, not closed).** Frozen design §16.3.7 makes a stage-output
authority failure at establishment a console-only hard stop that writes
nothing to `results/`. A prior establishment call with `CFG1-S1-A3` that failed
**before** the execution directory was created — for example on a
`RESULTS_ROOT` provenance refusal, or `EXECUTION_DIRECTORY_NOT_CREATED` — would
have consumed A3 under §8 while leaving **no durable A3 consumption marker**.
"Never called" is therefore **not reconstructible from filesystem state
alone**, and neither (b) nor (c) can detect such a call.

Consequences, all fail-closed:

- The exactly-once rule is not weakened: the **first** call consumes A3 (§8),
  whether or not it leaves a trace.
- If the operator knows of, or has any indication of, any earlier call with
  `CFG1-S1-A3` — including console output from a stage-output refusal naming
  no artifact — A3 is **consumed** and must not be invoked. Absence of an A3
  directory does not override that knowledge.
- If the operator cannot truthfully make the A0 attestation, admission fails.
- This document creates no durable ledger and requires no implementation
  change to close this residual.

Nothing may be deleted, renamed, or moved to make any check pass.

### 3.3 Distinction from A1 and A2

| Attempt | Code | Outcome | Status |
|---|---|---|---|
| `CFG1-S1-A1` | `eea76c1…` | ordinal 1 `REFUSED_PRE_DISPATCH`, `CREDENTIAL_BOUNDARY_FAILED` at L4; halted | consumed / historical only |
| `CFG1-S1-A2` | `eea76c1…` | ordinal 1 halted at L16, `CONFIG_SHAPE_MISMATCH` (the FU2 root cause); zero prompt writes | consumed / historical only |
| `CFG1-S1-A3` | exactly `bfae384…` source at `<A3_AUTH_COMMIT>`, proven imported by §7 | — | **not authorized** |

A3 is a fresh execution starting at ordinal 1. It is not a retry, resume,
replacement, continuation, or replay of A1 or A2, and A1 and A2 contribute
**zero samples** to A3.

---

## 4. A1/A2 historical evidence

### 4.1 The four files

Paths are relative to `RESULTS_ROOT` = `experiments/pi_harness_cfg1/results/`.

```text
315e5780a07ab3da3fdee5dd38f61b6797690db389217e1b8275200b28219cec  CFG1-S1-A1/S1_01_Q.json
fee44394ed8a942bdaed805dd3336c8b90bf15e4d6075e768ac545aab22bcfb3  CFG1-S1-A1/S1_stage_closure.json
e9a50844f1eb03879c34c988de0e1a54983af1d44ef3546055c8c8953ea7b796  CFG1-S1-A2/S1_01_Q.json
7027c35ce023c229dfab6fb54b7ba75a4938797ce65ca628e92ca7404d10d783  CFG1-S1-A2/S1_stage_closure.json
```

These are digests of AIDO's own emitted evidence, not of any credential or
endpoint. All four matched at authoring time.

### 4.2 Required state

Each of the four must be, at admission and throughout:

1. **present** on the filesystem at its exact path, as a regular file (not a
   directory, symlink, or reparse point) — by direct filesystem test;
2. **byte-identical** — exact SHA-256 as in §4.1;
3. **not tracked** — `git ls-files -- <path>` returns no entry, and it is absent
   from the tree of HEAD.

### 4.3 Exclude mechanisms are not evidence

At authoring time all four files are untracked **and hidden from ordinary
`git status`** by entries in `.git/info/exclude`. Therefore:

- ordinary `git status` output is **never** proof that a file is untracked,
  tracked, present, or absent;
- `.git/info/exclude`, `.gitignore`, `core.excludesFile`, and any other exclude
  mechanism are local UI hygiene only — **never authority**, never an admission
  input, and never to be edited as part of admission;
- presence is proven by the filesystem, identity by SHA-256, and untracked
  status by `git ls-files`, which consults the index, not exclude rules.

### 4.4 Non-participation

- The runtime does not read A1/A2 evidence as execution authority, and nothing
  here instructs it to.
- No A1/A2 record participates in any A3 contrast, count, tally, outcome, or
  closure predicate.
- A1/A2 files must not be read-into, edited, normalized, re-serialized,
  renamed, moved, copied into A3, committed, or deleted — before, during, or
  after A3. A3 writes nothing under `CFG1-S1-A1/` or `CFG1-S1-A2/`.
- A2's `runtime_reported_model_reasoning = OTHER` stays a truthful record of the
  defective v1 projection (FU2 §13). It is never re-projected, upgraded, or
  compared against A3.

---

## 5. Operator admission checklist

Admission is performed immediately before invocation, from the one CMD launcher
session, after the post-commit acceptance record (§2.4) exists. All commands
are CMD-compatible; no PowerShell is used. `<ROOT>` is
`C:\dev\ai_dev_orchestrator`.

| # | Fact | Read-only method (illustrative, CMD) |
|---|---|---|
| A0 | **attestation (non-mechanical):** the operator knows of no earlier `CFG1-S1-A3` establishment call of any kind (§3.2 (a)) | operator statement; no tool can prove it |
| A1 | HEAD == `<A3_AUTH_COMMIT>` named in the acceptance record, compared as full 40-hex SHA | `git rev-parse HEAD` |
| A2 | tracked working tree clean relative to HEAD | `git --no-optional-locks diff --quiet HEAD --` exits 0 |
| A3 | index clean relative to HEAD | `git --no-optional-locks diff --cached --quiet HEAD --` exits 0 |
| A4 | HEAD's blob for this file == `A3_AUTH_BLOB` in the acceptance record | `git rev-parse HEAD:docs/PHASE_5F3B_HARNESS_CFG1_LIVE_S1_A3_AUTHORIZATION.md` |
| A5 | the four A1/A2 files: present as regular files, exact §4.1 SHA-256, and `git ls-files -- <path>` empty for each | `dir /a:-d-l <path>`; `certutil -hashfile <path> SHA256`; `git ls-files -- <path>` |
| A6 | no surviving A3 namespace or artifact: `RESULTS_ROOT\CFG1-S1-A3` absent, and no other A3 artifact under `RESULTS_ROOT` | `if exist <ROOT>\experiments\pi_harness_cfg1\results\CFG1-S1-A3 (echo PRESENT) else (echo ABSENT)`; `git ls-files --others -- experiments/pi_harness_cfg1/results` (no exclude rules applied) lists exactly the four §4.1 paths |
| A7 | `AIDO_LITELLM_BASE_URL` and `PI_QUALIFICATION_B300_ROUTE_KEY` are **PRESENT** in the launcher process; values never seen | name-only presence check (§8.3) |
| A8 | no admission check changed repository, index, or evidence state | methods above are read-only; `--no-optional-locks` avoids index-refresh writes; no CFG1, AR2 or qualification module is imported by checks A0–A10 (the §7 gate, which runs afterwards in the launcher process, is the only pre-boundary step that imports them, and it writes no bytecode) |
| A9 | **no untracked import-shadow state** in any repository directory the launcher can import from (§7.2) | `git --no-optional-locks ls-files --others -- src experiments/pi_harness_cfg1 experiments/pi_external_runtime_ar2/ar2 experiments/pi_external_runtime_ar2/extension experiments/pi_implementer_qualification/qualification` (no exclude rules applied) lists **only**: paths with a `/__pycache__/` component, paths under `src/ai_dev_orchestrator.egg-info/`, and the four §4.1 paths |
| A10 | the launcher file is outside `<ROOT>` and its bytes match `LAUNCHER_SHA256` in the acceptance record | `certutil -hashfile <LAUNCHER> SHA256` |

The source-origin gate of §7 then runs **inside the launcher process** and is
part of admission: it precedes the consumption boundary.

Rules:

- **Admission does not depend on `.git/info/exclude`** or on ordinary
  `git status` output for any fact.
- **If any check fails, A3 is not invoked**, and nothing is repaired
  automatically — no checkout, reset, stash, clean, file edit, file move, file
  deletion, hash "correction", or exclude edit.
- A failure of A0–A6, A8, A9, or of a §7 gate code marked *terminal* ends
  admission under this authorization; what to do next requires a fresh
  diagnosis outside this document.
- A failure of A7 only (a name MISSING) permits the operator to perform the
  session-scoped mapping of §8.2 and then re-run the **entire** checklist from
  A0. A failure of A10, or of a §7 gate code marked *operator-correctable*,
  permits only correcting the launcher file or the launcher invocation (§7.1)
  and then re-running the entire checklist from A0. Nothing else is permitted.
  Re-running admission is not a retry of A3: nothing has been consumed.
- Every admission and gate failure occurs before the consumption boundary (§9)
  and does not consume A3.

---

## 6. Live scope — granted only after final acceptance

If, and only if, §2.4's post-commit record exists and §5 and §7 pass, this
document authorizes exactly **one** fresh Stage-1 execution, bounded by the
frozen design, FU2 R2/ERR1, and the shipped code:

| Bound | Value (frozen fact, not selected here) |
|---|---|
| execution id | exactly `CFG1-S1-A3`, used once |
| stage | exactly `S1` |
| model | exactly `qwen3-coder-next` |
| provider id / gateway class | exactly `b300_pi_qualification` / `b300_litellm_proxy` (frozen B300 provider/backend) |
| Pi | exactly `0.85.1`; shipped `PINNED_PI_SEAM_DIGESTS`, re-proven at L1 |
| task / prompt / fixture | `CFG1-T1`; `fixture.CFG1_T1_PROMPT` verbatim; pinned revision |
| schedule | `Q, R, E, R, E, Q, E, Q, R` from `schedule.py`; never supplied, reordered, or subsetted |
| runs | at most **nine** admitted, strictly sequential, one per ordinal |
| AIDO prompt writes | at most **one** per admitted run. This bounds AIDO's semantic prompt writes; it does not bound the number of provider requests Pi itself issues while serving that one prompt (see retry row) |
| `/models` | at most **one** AIDO-issued, authenticated, non-inference `GET /models` per admitted run (L7) |
| L16 | frozen FU2 probe (§10) |
| retry policy | **AIDO:** no AIDO semantic retry — no second prompt write within a run, and no run replay, replacement, reorder, repetition, or re-invocation of the stage. **Pi:** the frozen generated `settings.json` retry block is retained **unchanged and byte-identical** — `retry.enabled = true`, `retry.maxRetries = 3`, `retry.baseDelayMs = 2000`, `retry.provider.maxRetries = 0` (frozen design "retry policy: no AIDO semantic retry; Pi settings retry block identical"). Under that block Pi may perform its own internal retries while serving the one AIDO prompt. AIDO does not suppress, bound, add to, or count those as AIDO retries; it observes them only through the frozen `auto_retry_events` runtime claim and its frozen classification effects |
| halt | stop; no resume |
| token policy | no AIDO `maxTokens` |
| output authority | exactly `RESULTS_ROOT/CFG1-S1-A3/`, where `RESULTS_ROOT` is proven by §7 to derive from the accepted checkout |
| lifecycle / evidence | frozen L0–L30 lifecycle, closure predicates, `HALT_REASON_CODES`, record schemas (`pi-harness-cfg1-run.v1`) |

### 6.1 The single covered invocation surface

The **only** covered surface is the §7.3 launcher, whose bytes are bound by
`LAUNCHER_SHA256`, run as specified in §7.1. After its source-origin gate
passes, it performs exactly:

```text
authority = stage_output.establish_stage_output_authority(
    stage_id="S1", stage_execution_id="CFG1-S1-A3")
stage_runner.run_cfg1_stage(authority)
```

each exactly once, in that order, in that one process. Nothing else is
covered: not `_run_cfg1_stage_with_injected_executor`, not any test double, not
any other entry point or launcher, not an interactive interpreter, not a second
call to either function, and not `stage_id="S2"`.

How the launcher process resolves Python modules **is** an authorization
parameter: it is fixed by §7 and is not left to `sys.path`, the current
directory, `PYTHONPATH`, an editable-install convention, or operator intent.

### 6.2 Explicitly NOT authorized

1. Stage 2, arm `H`, or `CFG1-LIVE-S2`.
2. `DX1` (NO-GO) and `M4` (HOLD / NO-GO).
3. `A4` or any other future identifier — not pre-authorized, not reserved.
4. Any execution, retry, resume, or reuse under `CFG1-S1-A1` or `CFG1-S1-A2`.
5. Any AIDO-initiated retry, replay, replacement, reorder, or repetition of an
   A3 run or prompt; any resumption after halt; any second A3 invocation.
   (Pi's own frozen settings retry block is neither an AIDO retry nor a new
   authorization, and this document neither adds to it nor alters it.)
6. Prompt, fixture, task, or schedule mutation.
7. Any alternate model, provider, backend, route, endpoint, or fallback.
8. Any change to production code, tests, frozen designs, FU2/ERR1, DOCSYNC
   pointers, the frozen Pi settings (including its retry block), the A1/A2
   authorizations, `CLAUDE.md`, OBS1, AR2, qualification code, or qualification
   artifacts.
9. Evidence repair of any kind — A1, A2, or A3.
10. Branch, commit, push, or PR automation; committing A3 artifacts is not
    authorized by this document.
11. Any authority derived from runtime claims, model output, or evidence
    content.
12. Any new capability: fixer, model-backed implementer, reviewer, agent loop,
    or GitHub write.

---

## 7. Pre-consumption source-origin gate

### 7.1 Why, and how the launcher is run

Exact HEAD proves which bytes Git tracks. It does not prove that the launcher
process imports them: the process could resolve `pi_harness_cfg1`, `ar2`,
`qualification` or `ai_dev_orchestrator` from another checkout or install, or an
untracked file inside the accepted checkout could shadow a tracked module. This
matters beyond code identity: `RESULTS_ROOT` is derived from
`stage_output.__file__` (`_CAPTURED_PACKAGE_DIR`), and the Pi extension source
directory is derived from `ar2.__file__`. A foreign import would move both away
from what admission A5, A6 and A9 examined.

Layout inspected read-only for this revision:

| Fact | Observed |
|---|---|
| interpreter | `<ROOT>\.venv\Scripts\python.exe`, CPython 3.14, `include-system-site-packages = false` |
| `.pth` files in `<ROOT>\.venv\Lib\site-packages` | exactly one, the editable install, one line: `<ROOT>\src`; **not processed** in the authorized launch (`-S`) |
| `sys.path` under `-I` **without** `-S` (not authorized) | base interpreter entries, `<ROOT>\.venv`, `<ROOT>\.venv\Lib\site-packages`, `<ROOT>\src` — `site` has already run, processed the `.pth`, and attempted `sitecustomize`/`usercustomize` before any launcher line executes |
| flags under `-I -S -B` | `isolated = 1`, `no_site = 1`, `dont_write_bytecode = 1`, `safe_path = True`, `ignore_environment = 1`, `no_user_site = 1` |
| `sys.prefix` / `sys.exec_prefix` under `-I -S` | `<ROOT>\.venv` (venv binding is established by interpreter start-up path calculation, not by `site`); `sys.base_prefix` is the base interpreter; `sys.executable` is `<ROOT>\.venv\Scripts\python.exe` |
| initial `sys.path` under `-I -S` | exactly four base-interpreter entries (`python314.zip`, `DLLs`, `Lib`, the base directory); **no** `<ROOT>` entry, no venv entry, no site-packages entry, no current or script directory |
| modules loaded at start under `-I -S` | interpreter bootstrap and encoding modules only; `site`, `sitecustomize`, `usercustomize` and `_distutils_hack` are **not** loaded |
| import machinery under `-I -S` | `sys.meta_path` = `[BuiltinImporter, FrozenImporter, PathFinder]`; `sys.path_hooks` = `[zipimporter, FileFinder path hook]`; `sys.path_importer_cache` values are `None` or `FileFinder` |
| lineage reliance on `site` | none: no lineage module imports `site` or uses a site-installed builtin (`exit`, `quit`, …) — static search |
| `pi_harness_cfg1`, `ar2`, `qualification` | **not** on the default `sys.path`; the offline suites add their parent directories by `sys.path.insert` in `conftest.py` |
| lineage packages | regular packages; every non-test subdirectory has `__init__.py` |
| third-party import in the lineage | `httpx`, from venv site-packages |

The launcher is run exactly as:

```text
<ROOT>\.venv\Scripts\python.exe -I -S -B -X pycache_prefix=<PYCACHE_DIR> <LAUNCHER>
```

- `-I` (isolated): `PYTHON*` environment variables (including `PYTHONPATH`,
  `PYTHONSTARTUP`, `PYTHONPYCACHEPREFIX`) are ignored, user site-packages are
  not added, and neither the current directory nor the script directory is put
  on `sys.path`. It does not clear or alter the process environment that
  carries the credential names. `-I` implies `-E`, `-P` and `-s`, but **not**
  `-S`.
- `-S` (no site): the `site` module is not imported at start-up, so **no**
  `.pth` file is read or executed, `sitecustomize` and `usercustomize` are not
  imported, and neither `<ROOT>\src` nor site-packages is placed on `sys.path`
  by site machinery. Without `-S`, all of that would happen **before** the
  first launcher line — before G0 — and any repository-derived code it reached
  (for example a `sitecustomize` under `<ROOT>\src`) would already have run
  when the gate later refused. `-S` removes that pre-gate execution path; G0
  proves it was in effect.
- `-B`: no bytecode is written.
- `-X pycache_prefix=<PYCACHE_DIR>`: `<PYCACHE_DIR>` is a directory the operator
  has just created, empty, outside `<ROOT>`. With a prefix set, Python looks up
  cached bytecode **only** under the prefix, never in in-tree `__pycache__`
  directories; with the prefix empty and `-B` set, every module is compiled from
  its source file and nothing is cached. Stale or planted in-tree `.pyc` files
  therefore cannot execute.
- `<LAUNCHER>` is a file outside `<ROOT>` whose bytes are exactly the §7.3
  launcher (A10).

### 7.2 What the gate proves, mechanically

Inside the launcher process, before any lineage import and before
`establish_stage_output_authority` is called, the gate refuses (prints one fixed
code, exits `2`, and **does not call** `establish_stage_output_authority`)
unless all of the following hold:

| Gate | Condition | On failure |
|---|---|---|
| G0 | isolated, **no-site** (`sys.flags.no_site == 1`) and no-bytecode flags set; `site`, `sitecustomize` and `usercustomize` are not loaded; `<ROOT>` is its own canonical path; `sys.prefix` is `<ROOT>\.venv`; the launcher file is outside `<ROOT>`; `sys.pycache_prefix` is set, exists, is empty, and is outside `<ROOT>`; the base interpreter is outside `<ROOT>` | operator-correctable, except three terminal codes: `G0_ROOT_NOT_CANONICAL`; `G0_INTERPRETER_FLAGS` and `G0_SITE_LOADED`, because a launch without `-S` has already run site start-up code before the gate, so what that code did cannot be excluded by relaunching. The flag and start-up-module checks run first, so every later G0 code is reached only in a process in which site did not run |
| G1 | `sys.meta_path` is exactly the three default finders; `sys.path_hooks` is exactly `[zipimporter, FileFinder path hook]`; every `sys.path_importer_cache` value is `None`, a `FileFinder`, or a `zipimporter` | terminal |
| G2 | no module named `pi_harness_cfg1`, `ar2`, `qualification`, `ai_dev_orchestrator`, or any submodule of them, is already loaded; no `sys.path` entry is empty; **every** initial `sys.path` entry lies under the base interpreter prefix (`sys.base_prefix`), so no `<ROOT>` path of any kind — not `<ROOT>\src`, not the venv, not site-packages — is on `sys.path`; and **no symlink, junction, or other reparse point** exists in any repository source root (§7.2a), proven before G3 without following any link (`G2_REPARSE_SOURCE_TREE`) | terminal |
| G3 | each of the four top-level packages is loaded **explicitly** from its exact expected `__init__.py` by `SourceFileLoader`, with its submodule search path pinned to exactly its expected directory — never found through `sys.path` | terminal |
| G3a | only **after** G2 and G3: `<ROOT>\.venv\Lib\site-packages`, which must be its own canonical path and a directory, is **appended** to `sys.path` by one direct `sys.path.append` — after the base-interpreter entries, so it cannot shadow the standard library — solely so third-party dependencies (`httpx` and its dependencies) resolve. No `site.main()`, no `site.addsitedir()`, and no other `.pth`-processing mechanism is called; a plain `sys.path` entry is searched by `FileFinder` only and its `.pth` files are never read. `<ROOT>\src` is **not** added: `ai_dev_orchestrator` is already bound by G3 | terminal |
| G4 | the authority/execution lineage imports without error: `pi_harness_cfg1.stage_output`, `pi_harness_cfg1.stage_runner`, `pi_harness_cfg1.run_executor`, `ar2.supervisor`, `ar2.protocol`, `ar2.runtime_probe`, `qualification.safety`, `qualification.runtime_activity`, `qualification.i2_b300_route_observation`, `qualification.i2_secret_context`, `qualification.semantic_live_adapters`, `qualification.semantic_session`, `httpx` | terminal |
| G5 | **every** loaded module of the four packages: loader is `SourceFileLoader`; origin is a `.py` file that is its own canonical path and lies inside its package's expected directory; its bytecode path, if any, lies under `<PYCACHE_DIR>`; a subpackage's search path is exactly its own directory. **Every** other loaded module with a filesystem origin lies under the base interpreter prefix or `<ROOT>\.venv\Lib\site-packages`; `httpx` lies under the latter | terminal |
| G6 | `stage_output._CAPTURED_PACKAGE_DIR` and `stage_runner._GENUINE_PACKAGE_DIRECTORY` both equal `<ROOT>\experiments\pi_harness_cfg1`, so `RESULTS_ROOT` is the directory A5/A6 examined; `<PYCACHE_DIR>` is still empty; `site`, `sitecustomize` and `usercustomize` are still not loaded; `sys.path` is exactly the initial base-interpreter entries plus the one appended site-packages entry | terminal |

Why this is mechanical rather than conventional:

- **Top-level resolution is not delegated to `sys.path`.** G3 binds each of the
  four packages to an exact file by path, and G5 re-proves every resulting
  origin. A second checkout, an installed copy, a `PYTHONPATH` entry, or a
  current-directory entry cannot supply them.
- **Lazy imports after the boundary stay pinned.** CFG1 imports several AR2 and
  qualification modules inside functions, after consumption. A submodule of a
  regular package is resolved only through its parent's search path, which G3
  pins and G5 re-proves, by the default finder (G1). No lineage submodule can
  be resolved from anywhere except its expected directory.
- **Untracked import shadows inside the checkout are excluded by A9.** A clean
  tracked tree does not exclude untracked files. Within a pinned package
  directory, an untracked `name/` package directory or `name.*.pyd` extension
  module would take precedence over a tracked `name.py`, and an untracked
  `name.pyc` would load if no source existed. A9 admits no untracked file in
  those directories except `__pycache__` content (never consulted, §7.1), the
  non-importable `ai_dev_orchestrator.egg-info` metadata (its name is not a
  valid module name), and the four evidence files (JSON, not importable). A9
  also covers the whole of `<ROOT>\src` (the `ai_dev_orchestrator` source root
  and the target of the editable `.pth`) and the AR2 `extension` directory,
  whose location derives from `ar2.__file__`.
- **No repository directory is on `sys.path` at all** (G2, G3a, G6). The
  launcher process's `sys.path` is the base-interpreter entries plus the one
  appended site-packages entry. A later top-level import that neither the
  standard library nor site-packages satisfies (for example an
  optional-dependency probe) finds nothing in the repository and fails, rather
  than reaching `<ROOT>\src` or any other repository path.
- **No start-up code runs before the gate** (G0). `-S` prevents `site`, `.pth`
  processing and `sitecustomize`/`usercustomize`; before G0 executes, only the
  interpreter's own bootstrap modules have been loaded from the base
  interpreter, and G0 refuses unless `no_site` is set and none of those three
  modules is loaded.
- **Tracked content equals HEAD** by A1–A3, and G5 proves the executing code was
  compiled from those files, not from cached bytecode.
- **Filesystem topology is proven by the launcher, not by Git** (§7.2a). A9
  sees only what Git enumerates as untracked files; it is not a proof that no
  symlink, junction or other reparse point exists.

### 7.2a Source-tree topology check (inside G2, before G3)

**Invariant.** Before any lineage module is loaded, and therefore before
`establish_stage_output_authority` is called, every repository source/import
root through which the genuine execution can later resolve repository code
contains **no** symlink, junction, or other entry carrying
`FILE_ATTRIBUTE_REPARSE_POINT`, at any depth. The lexical path from `<ROOT>`
down to each root is likewise free of such entries. The roots are exactly:

```text
<ROOT>\src
<ROOT>\experiments\pi_harness_cfg1
<ROOT>\experiments\pi_external_runtime_ar2\ar2
<ROOT>\experiments\pi_external_runtime_ar2\extension
<ROOT>\experiments\pi_implementer_qualification\qualification
```

**Mechanism (standard library only).**

- For each path component from `<ROOT>` down to the root, the component's own
  directory entry is obtained by listing its parent with `os.scandir` and
  matching the name. The entry must not be link-like and must be a directory
  without following links (`is_dir(follow_symlinks=False)`).
- Each root is then walked depth-first with `os.scandir`. **Every** entry
  encountered — file or directory, including `__pycache__`, `tests` and
  `results` content — is inspected as the lexical entry itself:
  `is_symlink()`, `is_junction()`, and the `st_file_attributes` of
  `stat(follow_symlinks=False)`, tested for `stat.FILE_ATTRIBUTE_REPARSE_POINT`.
  On Windows those attributes come from the directory listing's own record of
  the entry, so any reparse type is reported, not only symlinks and junctions,
  and no entry is opened or followed to decide whether it is safe.
- The walk descends only into entries that are directories without following
  links and that already passed the test. It never enters a link.
- Any link-like entry, any missing attribute, any missing path component, or
  any `OSError` → `G2_REPARSE_SOURCE_TREE`, exit `2`, A3 not consumed. There is
  no allow-list and no exception mechanism: the frozen tree contains no tracked
  symlink in these roots (`git ls-files -s` shows no mode `120000` entry), and
  a read-only standard-library walk at authoring time found no reparse entry
  among the 456 entries then present.

**Why it detects a junction or reparse shadow before import.** Python's
`FileFinder` resolves a submodule by listing the pinned package directory and
then opening `name/` or `name.<suffix>` **through** whatever that entry is. A
junction or symlink at `name/` (or at any directory above it inside the root)
would make a later lazy import read code from a foreign directory while the
lexical path still looks correct, and G5's origin check would not run again
after consumption. The topology check inspects that same lexical entry before
G3 and refuses on its reparse attribute alone, without resolving it, so no
redirect can exist in these roots at the moment the gate passes.

**Scope boundary.** `<ROOT>` itself and its ancestors are covered only by G0's
`<ROOT>`-is-its-own-canonical-path check, which detects link-type redirection
(symlinks, junctions) of `<ROOT>` or an ancestor, not other reparse types
above `<ROOT>`. The launcher does not list directories above `<ROOT>`.

### 7.3 The launcher (normative text; bytes bound by `LAUNCHER_SHA256`)

```python
# CFG1-S1-A3 launcher. Normative text of the A3 authorization, section 7.3.
import importlib
import importlib.machinery as machinery
import importlib.util
import os
import stat
import sys
import zipimport

ROOT = r"C:\dev\ai_dev_orchestrator"
VENV = ROOT + r"\.venv"
SITE = VENV + r"\Lib\site-packages"
SRC = ROOT + r"\src"
PACKAGES = (
    ("ai_dev_orchestrator", SRC + r"\ai_dev_orchestrator"),
    ("ar2", ROOT + r"\experiments\pi_external_runtime_ar2\ar2"),
    ("qualification", ROOT + r"\experiments\pi_implementer_qualification\qualification"),
    ("pi_harness_cfg1", ROOT + r"\experiments\pi_harness_cfg1"),
)
SOURCE_ROOTS = (
    SRC,
    ROOT + r"\experiments\pi_harness_cfg1",
    ROOT + r"\experiments\pi_external_runtime_ar2\ar2",
    ROOT + r"\experiments\pi_external_runtime_ar2\extension",
    ROOT + r"\experiments\pi_implementer_qualification\qualification",
)
LINEAGE = (
    "pi_harness_cfg1.stage_output",
    "pi_harness_cfg1.stage_runner",
    "pi_harness_cfg1.run_executor",
    "ar2.supervisor",
    "ar2.protocol",
    "ar2.runtime_probe",
    "qualification.safety",
    "qualification.runtime_activity",
    "qualification.i2_b300_route_observation",
    "qualification.i2_secret_context",
    "qualification.semantic_live_adapters",
    "qualification.semantic_session",
    "httpx",
)
HOOK_QUALNAME = "FileFinder.path_hook.<locals>.path_hook_for_FileFinder"
STARTUP_MODULES = ("site", "sitecustomize", "usercustomize")


def refuse(code):
    print("A3_SOURCE_ORIGIN_REFUSED " + code)
    sys.exit(2)


def norm(path):
    return os.path.normcase(os.path.realpath(path))


def canonical(path):
    return norm(path) == os.path.normcase(os.path.abspath(path))


def under(path, directory):
    p = norm(path)
    d = norm(directory)
    return p == d or p.startswith(d + os.sep)


def link_like(entry):
    # Inspects the lexical directory entry itself; never follows it.
    if entry.is_symlink() or entry.is_junction():
        return True
    attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", None)
    return attributes is None or bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def lexical_entry(path):
    parent, name = os.path.split(path)
    with os.scandir(parent) as entries:
        for entry in entries:
            if os.path.normcase(entry.name) == os.path.normcase(name):
                return entry
    return None


def topology_clean():
    for root in SOURCE_ROOTS:
        current = ROOT
        for part in os.path.relpath(root, ROOT).split(os.sep):
            current = os.path.join(current, part)
            entry = lexical_entry(current)
            if entry is None or link_like(entry) or not entry.is_dir(follow_symlinks=False):
                return False
        pending = [root]
        while pending:
            with os.scandir(pending.pop()) as entries:
                for entry in entries:
                    if link_like(entry):
                        return False
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(entry.path)
    return True


def gate():
    # G0 - interpreter, no-site start-up, launcher location, bytecode isolation.
    if sys.flags.isolated != 1 or sys.flags.no_site != 1 or sys.flags.dont_write_bytecode != 1:
        refuse("G0_INTERPRETER_FLAGS")
    for startup in STARTUP_MODULES:
        if startup in sys.modules:
            refuse("G0_SITE_LOADED")
    if not canonical(ROOT):
        refuse("G0_ROOT_NOT_CANONICAL")
    if norm(sys.prefix) != norm(VENV):
        refuse("G0_INTERPRETER_NOT_CHECKOUT_VENV")
    if under(sys.base_prefix, ROOT):
        refuse("G0_BASE_INTERPRETER_INSIDE_ROOT")
    if under(os.path.abspath(__file__), ROOT):
        refuse("G0_LAUNCHER_INSIDE_ROOT")
    prefix = sys.pycache_prefix
    if not prefix or not os.path.isdir(prefix) or os.listdir(prefix) or under(prefix, ROOT):
        refuse("G0_PYCACHE_PREFIX")
    # G1 - default import machinery only.
    if list(sys.meta_path) != [machinery.BuiltinImporter, machinery.FrozenImporter, machinery.PathFinder]:
        refuse("G1_META_PATH")
    hooks = list(sys.path_hooks)
    if len(hooks) != 2 or hooks[0] is not zipimport.zipimporter:
        refuse("G1_PATH_HOOKS")
    if getattr(hooks[1], "__qualname__", None) != HOOK_QUALNAME:
        refuse("G1_PATH_HOOKS")
    for finder in list(sys.path_importer_cache.values()):
        if finder is not None and type(finder) not in (machinery.FileFinder, zipimport.zipimporter):
            refuse("G1_PATH_IMPORTER_CACHE")
    # G2 - nothing preloaded; the initial sys.path is base-interpreter only.
    names = tuple(name for name, _ in PACKAGES)
    for loaded in list(sys.modules):
        if loaded.split(".")[0] in names:
            refuse("G2_LINEAGE_PRELOADED")
    initial_path = list(sys.path)
    for entry in initial_path:
        if not entry:
            refuse("G2_EMPTY_SYS_PATH_ENTRY")
        if not under(entry, sys.base_prefix) or under(entry, ROOT):
            refuse("G2_SYS_PATH_ENTRY")
    # G2 - no symlink, junction or other reparse point in any source root.
    try:
        clean = topology_clean()
    except BaseException:
        clean = False
    if not clean:
        refuse("G2_REPARSE_SOURCE_TREE")
    # G3 - explicit load of the four top-level packages from exact paths.
    for name, directory in PACKAGES:
        init = os.path.join(directory, "__init__.py")
        if not canonical(directory) or not os.path.isfile(init) or not canonical(init):
            refuse("G3_PACKAGE_PATH")
        spec = importlib.util.spec_from_file_location(
            name, init, submodule_search_locations=[directory]
        )
        if spec is None or type(spec.loader) is not machinery.SourceFileLoader:
            refuse("G3_PACKAGE_SPEC")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            refuse("G3_PACKAGE_EXEC")
    # G3a - append venv site-packages directly; no site machinery, no .pth.
    if not canonical(SITE) or not os.path.isdir(SITE):
        refuse("G3A_SITE_PACKAGES_PATH")
    sys.path.append(SITE)
    # G4 - import the authority/execution lineage.
    for dotted in LINEAGE:
        try:
            importlib.import_module(dotted)
        except BaseException:
            refuse("G4_LINEAGE_IMPORT")
    # G5 - audit the origin of every loaded module.
    expected = dict(PACKAGES)
    for loaded, module in list(sys.modules.items()):
        spec = getattr(module, "__spec__", None)
        origin = getattr(spec, "origin", None)
        top = loaded.split(".")[0]
        if top in expected:
            if spec is None or type(spec.loader) is not machinery.SourceFileLoader:
                refuse("G5_LINEAGE_LOADER")
            if not origin or not origin.endswith(".py") or not canonical(origin):
                refuse("G5_LINEAGE_ORIGIN")
            if not under(origin, expected[top]):
                refuse("G5_LINEAGE_ORIGIN")
            if spec.cached and not under(spec.cached, prefix):
                refuse("G5_LINEAGE_BYTECODE")
            locations = spec.submodule_search_locations
            if locations is not None and [norm(p) for p in locations] != [norm(os.path.dirname(origin))]:
                refuse("G5_LINEAGE_SEARCH_PATH")
        elif origin and os.path.isabs(origin):
            if not (under(origin, sys.base_prefix) or under(origin, SITE)):
                refuse("G5_FOREIGN_MODULE_ORIGIN")
    httpx_spec = getattr(sys.modules.get("httpx"), "__spec__", None)
    if httpx_spec is None or not httpx_spec.origin or not under(httpx_spec.origin, SITE):
        refuse("G5_HTTPX_ORIGIN")
    # G6 - RESULTS_ROOT derivation and bytecode isolation still hold.
    stage_output = sys.modules["pi_harness_cfg1.stage_output"]
    stage_runner = sys.modules["pi_harness_cfg1.stage_runner"]
    if norm(stage_output._CAPTURED_PACKAGE_DIR) != norm(expected["pi_harness_cfg1"]):
        refuse("G6_RESULTS_ROOT_DERIVATION")
    if norm(stage_runner._GENUINE_PACKAGE_DIRECTORY) != norm(expected["pi_harness_cfg1"]):
        refuse("G6_RESULTS_ROOT_DERIVATION")
    if os.listdir(prefix):
        refuse("G6_PYCACHE_PREFIX_WRITTEN")
    for startup in STARTUP_MODULES:
        if startup in sys.modules:
            refuse("G6_SITE_LOADED")
    if list(sys.path) != initial_path + [SITE]:
        refuse("G6_SYS_PATH_CHANGED")
    return stage_output, stage_runner


def main():
    stage_output, stage_runner = gate()
    print("A3_SOURCE_ORIGIN_VERIFIED")
    # Consumption boundary: the first call below consumes CFG1-S1-A3.
    authority = stage_output.establish_stage_output_authority(
        stage_id="S1", stage_execution_id="CFG1-S1-A3"
    )
    stage_runner.run_cfg1_stage(authority)


main()
```

The launcher reads no environment variable value, prints no path, and writes
nothing before the consumption boundary. It reads two module-level constants of
frozen CFG1 modules; it modifies no production code and injects nothing into
the stage.

### 7.4 What the gate does not prove (residual, stated)

- **Interpreter, venv executable and third-party bytes.** In the authorized
  launch no `.pth` file is processed and no `sitecustomize`/`usercustomize` is
  imported (`-S`, G0, G6). The gate proves *where* stdlib and third-party
  modules were loaded from (base interpreter; `<ROOT>\.venv\Lib\site-packages`
  after G3a), not that their bytes are unmodified. It does not cryptographically
  attest the base interpreter, the venv executable, third-party package bytes in
  site-packages, or the Pi/Node installation beyond L1's frozen seam digests.
  This phase is not an interpreter supply-chain attestation.
- **Loads after the boundary are covered structurally, not audited.** Lineage
  submodules are pinned by G3/G5; other top-level imports resolve through the
  default machinery (G1) over a `sys.path` holding only base-interpreter entries
  and site-packages (G2, G3a, G6). No per-module audit runs after consumption.
- **The frozen verification child is outside `-S`.** After consumption, the
  frozen executor runs verification as `sys.executable` (the venv interpreter)
  with the frozen fixture arguments; that child starts with ordinary site
  processing, so it reads the editable `.pth` and may import a
  `sitecustomize`/`usercustomize` reachable on its own path. This is frozen,
  post-consumption behavior of the controlled verification step (not
  sandboxed), not pre-gate execution. Repository-derived start-up code for it is
  excluded at gate time by A9 and §7.2a over `<ROOT>\src`, subject to the TOCTOU
  residual below; this document does not change it.
- **Time of check versus time of use.** A9 and A1–A3 run shortly before the
  launcher, and the §7.2a topology walk runs before G3; a concurrent writer in
  the same account could alter files, or create a link or junction, in between
  or after the gate passes — including before a lazy import after the
  consumption boundary. The gate narrows but does not close this; the operator
  must not run other writers against `<ROOT>` during admission and execution.
  Nothing here turns the local filesystem into an OS sandbox.
- **Above `<ROOT>`.** Non-link reparse types on `<ROOT>` or its ancestors are
  outside the §7.2a walk (§7.2a scope boundary).
- The gate is authorization text executed by the operator, not frozen
  implementation. Its passing grants nothing beyond this document's scope.

---

## 8. Credential boundary

### 8.1 Names

The only live environment inputs the harness reads are the frozen names:

```text
AIDO_LITELLM_BASE_URL
PI_QUALIFICATION_B300_ROUTE_KEY
```

No generic key name is authorized in CFG1 code. CFG1 must not read
`AIDO_LITELLM_API_KEY` or any alias, fallback, `.env`, config file, CLI flag, or
prompt. Credential values enter CFG1 only at the frozen **L4** boundary, after
L1–L3. The §7 launcher reads no environment value.

### 8.2 Session-scoped operator mapping (preserved from A2 §4)

When `PI_QUALIFICATION_B300_ROUTE_KEY` is MISSING, the operator may populate it
from the existing operator-controlled generic source `AIDO_LITELLM_API_KEY`,
outside the harness, in the one CMD launcher session only — and only after the
source is confirmed PRESENT, because an undefined CMD reference can leave the
literal reference text in place, which would pass L4 and fail only at L7 after
consumption. Illustrative form:

```text
if defined AIDO_LITELLM_API_KEY set "PI_QUALIFICATION_B300_ROUTE_KEY=%AIDO_LITELLM_API_KEY%"
```

- No `setx`, no user/system environment change, no script, batch, `.env`,
  profile, or config file, nothing in the repository — no persistence.
- The endpoint `AIDO_LITELLM_BASE_URL` is used as already present; this
  document sets or selects no endpoint.
- The launcher is started from this same CMD session, so it inherits the
  session environment; `-I` does not remove these names.

### 8.3 Presence checks

Presence is observed as **PRESENT/MISSING only**, e.g.
`if defined PI_QUALIFICATION_B300_ROUTE_KEY (echo PRESENT) else (echo MISSING)`.
No value is printed, echoed, logged, copied, written, hashed, measured
(length), or partially rendered, and no value-printing enumeration (bare `set`)
is used.

### 8.4 Child handoff and residuals

- The Pi child environment is built from the frozen positive allowlist into
  which the frozen carrier is explicitly inserted; the generic name is not on it
  and is not forwarded. This document changes no child-environment policy.
- No credential name or value is granted a durable-evidence field.
- Redaction and scrubbing are a backstop; nothing here claims any artifact is
  provably secret-free.

---

## 9. Consumption boundary

`CFG1-S1-A3` is **consumed by the first call** to:

```text
establish_stage_output_authority(stage_id="S1", stage_execution_id="CFG1-S1-A3")
```

whatever happens afterwards — an authority refusal (including a §16.3.7
console-only hard stop that leaves no artifact), a preflight refusal, a
credential or route refusal, a Pi failure, an L16 refusal, a halt, an evidence
failure, a teardown failure, a process crash, or completion — and whether or not
any prompt is ever written, and whether or not any durable trace remains
(§3.2 residual).

- A failure **before** that call — any §5 admission failure or any §7 gate
  refusal — does not consume A3.
- A failure **at or after** that call consumes A3.
- No resume, repair, replay, or second invocation is authorized. A later
  attempt requires a fresh diagnosis, a new authorization, and a new identifier.

---

## 10. L16 — recognized, not redesigned

L16 uses the frozen FU2 behavior: `PiRpcSupervisor.probe_runtime_capabilities()`
on the exact L14-launched supervisor, one call, producing only the four bounded
facts — one `bool` (H2) and three closed-domain `str` (reasoning, compat shape,
thinking level) — from the **one correlated** `get_state` response.

- Raw reasoning-bearing structure is still scrubbed through normal AR2
  ingestion before publication.
- No raw response hook, generic response visibility, state tree, or container
  crosses the boundary, and this document authorizes none.
- Every probe, correlation, and domain failure remains fail-closed under the
  frozen FU2 §8 mapping (`H2_MISMATCH`, `CONFIG_SHAPE_MISMATCH`,
  `RUNTIME_CORRELATION_FAILED`). No refusal code, enum, or predicate is added or
  relaxed.
- The four facts are **runtime claims**. Correlation makes them attributable to
  one response, not true; they confer no authority (§12).

---

## 11. Evidence, failure, and teardown semantics

- Frozen CFG1 evidence rules apply unchanged; durable evidence is written only
  under `RESULTS_ROOT/CFG1-S1-A3/`, created once by exclusive create.
- No raw secret, endpoint, host, URL, reasoning subtree, or unrestricted runtime
  response may enter evidence.
- Teardown and cleanup failures remain visible and **cannot produce a pass**.
  Nothing here claims Pi was sandboxed, descendants were stopped, a request was
  cancelled, or backend inference stopped.
- Partial A3 artifacts are never deleted, rewritten, completed, or repaired.
- **No evidence artifact authorizes any later action** — including any S1
  closure outcome that the frozen design would treat as input to a Stage-2
  decision. Stage 2 requires its own separate authorization.
- No A1/A2 record participates in the A3 outcome.

---

## 12. Adversarial analysis

### 12.1 Threat summary

| Threat | Disposition |
|---|---|
| Code differs from what was reviewed | HEAD pinned to one concrete commit (A1); chain `bfae384 → 820e8c → <A3_AUTH_COMMIT>` verified P1/P2/P6; later commits void admission |
| Executed code differs from tracked code | §7 gate: explicit package binding, origin audit, bytecode isolation; A9 untracked-shadow check; §7.2a no-follow topology check for symlinks, junctions and reparse points |
| Authorization or launcher text differs from what was reviewed | blob id + SHA-256 bound by P3/P4, re-checked at A4; launcher bytes bound by `LAUNCHER_SHA256`, re-checked at A10; LF-only under `core.autocrlf=true` |
| "Docs-only descendant" argument | no equivalence class exists (§1) |
| Candidate acceptance mistaken for authority | content review grants nothing (§2.1); only the post-commit record authorizes (§2.4) |
| Id reuse / A1-A2 confusion | fixed new literal; three grounds plus stated residual (§3.2); runtime exclusive create where a namespace exists |
| Hidden untracked state | `git status` and exclude files are not evidence; `git ls-files`, filesystem, SHA-256 (§4.3, A9) |
| Evidence tampering or accidental commit | A5 hashes; P5 and A5 untracked checks |
| Admission check mutates state | `--no-optional-locks`; no lineage import during admission; `-B` and an out-of-tree empty prefix in the launcher |
| Credential exposure / literal carrier | PRESENT/MISSING only; mapping guarded by `if defined`; no persistence (§8) |
| Route substitution | frozen provider/gateway/model; one AIDO `/models` at L7; no alternate route |
| L16 widened into generic visibility | frozen four-fact probe only; no hook (§10) |
| Partial failure laundered into a pass | consumption at first call; teardown failures visible; no repair (§9, §11) |
| Stage-2 escape | S1 only; no evidence authorizes S2 (§6.2, §11) |
| Runtime/model claims treated as fact or authority | recorded as claims only; never authority (§10) |

### 12.2 Required scenarios, tested against this text

1. **An earlier A3 establishment call failed before execution-directory
   creation.** It left no A3 directory and no artifact (§16.3.7), so A6 passes
   and exclusive create cannot fire. §9 says that call consumed A3. §3.2 states
   that the filesystem cannot show this and makes history (a) the governing
   ground: an operator who knows of the call cannot make the A0 attestation,
   admission fails, and A3 is not invoked. If the call is unknown to everyone,
   a second call could occur; §3.2 records this as a residual the filesystem
   cannot close, and the document does not claim otherwise.
2. **HEAD is exact but Python would import CFG1/AR2 from another checkout or
   install.** G3 never resolves the four packages through `sys.path`; it binds
   them to exact files. A pre-imported foreign copy fails G2; a foreign origin
   for any loaded lineage module fails G5; a foreign `RESULTS_ROOT` derivation
   fails G6. Each refusal happens before `establish_stage_output_authority`, so
   A3 is not consumed.
3. **HEAD is exact but an untracked import-shadow module would affect
   imports.** A clean tracked tree does not exclude it. An untracked file or
   directory in a pinned package directory, in `<ROOT>\src`, or in the AR2
   extension directory fails A9 before launch. A planted or stale in-tree `.pyc`
   is never consulted (§7.1). A shadow in the venv or base interpreter is
   outside the repository: G5 still refuses a lineage module that resolves there,
   and §7.4 states the residual for venv contents.
4. **Pi keeps the frozen retry block while AIDO performs zero semantic
   retries.** §6 states both at once: `retry.enabled = true`,
   `retry.maxRetries = 3`, `retry.baseDelayMs = 2000`,
   `retry.provider.maxRetries = 0` are retained unchanged, Pi may retry
   internally while serving the one AIDO prompt, and AIDO issues no second
   prompt write and replays, replaces or re-invokes nothing. "At most one prompt
   write per run" bounds AIDO's writes, not Pi's provider requests. Nothing here
   claims the Pi retry block is zero or absent.

The following import-shadow cases are tested against A2, A9, §7.2a and G5,
using `ar2.broker` as the example (it is tracked as
`experiments/pi_external_runtime_ar2/ar2/broker.py`, and CFG1 reaches it):

5. **An untracked ordinary `ar2/broker.py` shadow.** The path is tracked, so
   replacing its bytes is a tracked modification and fails A2. Any other
   ordinary file able to take precedence over it or stand in for it —
   `broker.<tag>.pyd`, a sourceless `broker.pyc` beside it — is untracked and
   fails A9. Rejected before consumption.
6. **An untracked `ar2/broker/` normal package directory.** Its
   `__init__.py` (or any file in it) is an untracked file and fails A9. A
   `broker/` directory containing no file at all is not listed by Git but
   cannot shadow: `FileFinder` treats a directory without `__init__.py` only as
   a possible namespace portion and still returns the tracked `broker.py` found
   in the same directory. Rejected before consumption where it could matter.
7. **An untracked `ar2/broker/` junction to a foreign directory.** Whether or
   not Git enumerates anything behind it, the §7.2a walk inspects the lexical
   `broker` entry in `ar2/`, finds a junction and the reparse attribute, and
   refuses `G2_REPARSE_SOURCE_TREE` before G3. Rejected before consumption.
8. **A symlink or reparse point nested under a pinned source root.** The walk
   descends every non-link directory of every root and inspects every entry at
   every depth, so a nested link is found wherever it sits, including under
   `__pycache__`, `tests` or `results`. `G2_REPARSE_SOURCE_TREE`. Rejected
   before consumption.
9. **A reparse entry that Git does not enumerate as an ordinary untracked
   file.** The topology check does not consult Git. It reads the reparse
   attribute from the directory listing itself, so an entry Git skips,
   ignores, or reports as something other than an untracked file is still
   refused. A9 is not relied on for this fact. Rejected before consumption.
10. **Concurrent writer (TOCTOU).** A writer that creates a shadow file, link
    or junction after the checks, or after the boundary and before a lazy
    import, is not detected. This remains the stated §7.4 residual; the
    operator must not run concurrent writers against `<ROOT>`.

The following start-up cases are tested against the `-I -S` launch, G0–G6,
A9 and §7.2a. For cases 11–17, the requirement is that no repository-derived
unauthorized code executes before the source-origin gate:

11. **An ordinary untracked `src/sitecustomize.py`.** Under `-S`, `site` never
    runs, so nothing imports `sitecustomize`; `<ROOT>\src` is never on the
    launcher's `sys.path` (G2, G6), so no later import can reach it either. It
    also fails A9 before launch. Nothing executes; rejected before consumption.
12. **`src/sitecustomize/` with `__init__.py`.** Same as case 11: not imported
    under `-S`, not reachable through `sys.path`, and its `__init__.py` fails
    A9. Nothing executes; rejected before consumption.
13. **`src/sitecustomize/` as a junction or other reparse point to foreign
    code.** Not imported under `-S` and not reachable through `sys.path`, so the
    foreign code never runs in the launcher process. The §7.2a walk of
    `<ROOT>\src` finds the reparse entry and refuses `G2_REPARSE_SOURCE_TREE`
    before G3, whether or not Git lists anything behind it. Nothing executes;
    rejected before consumption.
14. **Executable or import-bearing content in the editable `.pth`.** `.pth`
    files are read only by `site` (`site.main()`/`site.addsitedir()`), which
    `-S` suppresses and which the launcher never calls. G3a adds site-packages
    by a plain `sys.path.append`, which `FileFinder` only searches for modules
    and never uses to read `.pth` files. Whatever the `.pth` contains — a path
    line or an `import` line — is never executed in the launcher process. (The
    frozen post-consumption verification child is a separate process; §7.4.)
15. **A foreign `PYTHONPATH`.** `-I` ignores every `PYTHON*` variable, so it
    never reaches `sys.path`; G2 would refuse any initial entry outside the base
    interpreter, and G3 does not use `sys.path` for the four packages anyway.
    Nothing executes.
16. **A foreign script-directory or current-directory package.** `-I` (via
    `-P`) puts neither the current directory nor the launcher's directory on
    `sys.path`; G2 refuses an empty entry or any entry outside the base
    interpreter; the launcher itself lies outside `<ROOT>` (G0) and its bytes
    are bound (A10). A same-named package in either directory is never found.
    Nothing executes.
17. **A later lazy CFG1/AR2 import.** After consumption, a function-level
    import of a lineage submodule resolves only through its parent's pinned
    search path (G3, G5) by the default finder (G1), over directories whose
    topology §7.2a proved link-free and whose untracked content A9 excluded;
    any other top-level import resolves only over base-interpreter entries and
    site-packages (G6). No start-up hook runs at that point.
18. **Concurrent modification after the gate.** Not detected; this is the
    stated §7.4 TOCTOU residual, unchanged. It is distinct from the start-up
    order gap R5 closes, which concerned initial state before the gate.

### 12.3 Observations recorded for the reviewer

- `experiments/pi_external_runtime_ar2/experiment_config.json` is an untracked,
  `.gitignore`d AR2-local operator file present in this checkout. By static
  search it is referenced only by AR2's own `run_ar2.py` entry point and tests,
  not by the CFG1 package. It was not opened. It lies outside every A9 directory
  and outside every `sys.path` entry the launcher permits, so it cannot be
  imported through the launcher. It is not an admission input, not authority,
  and must not be modified or deleted for A3.
- The in-file status banners of the FU2 R2 design still read as candidate text;
  its acceptance, like this document's, is recorded outside the file.

---

## 13. Changelog — R3 against R2

| Finding | Change |
|---|---|
| B1 — filesystem absence overclaimed as "never called" | §3.2 rewritten into history (a), filesystem (b), exclusive create (c), and the §16.3.7 residual; A0 attestation added; §2.4 record names (a); §9 and §12 aligned. Exactly-once rule unchanged |
| B2 — import provenance not closed | §1 states Git provenance is necessary, not sufficient; §6.1 removes "how the operator makes the package importable … selects nothing" and binds the one launcher; new §7 source-origin gate (G0–G6) with normative launcher text; A9 untracked-shadow check and A10 launcher-bytes check added; `LAUNCHER_SHA256` added to §2.1/§2.4 |
| B3 — "retries: zero, at every layer" contradicted the frozen Pi retry block | §6 retry row states AIDO has no semantic retry while the frozen Pi `settings.json` retry block stays unchanged; prompt-write row scoped to AIDO; §6.2 items 5 and 8 scoped by layer |
| M1 — PowerShell hash command | replaced by `certutil -hashfile <path> SHA256`; all admission commands CMD-compatible |

Section numbers changed: the credential boundary moved to §8, consumption to
§9, L16 to §10, evidence to §11, adversarial analysis to §12.

### 13.1 Changelog — R4 against R3

| Finding | Change |
|---|---|
| Untracked filesystem reparse/junction import shadow — A9's Git view is not a topology proof | new §7.2a: a standard-library, no-follow walk of the five repository source roots, and of the lexical path from `<ROOT>` to each, runs inside G2 before G3 and refuses `G2_REPARSE_SOURCE_TREE` on any symlink, junction or `FILE_ATTRIBUTE_REPARSE_POINT` entry; §7.2 G2 row and rationale, §7.3 launcher text (hence `LAUNCHER_SHA256`), §7.4 TOCTOU residual, §12.1, and §12.2 cases 5–10 updated |

Nothing else changed in substance. R3's closures — the §3.2 grounds and
residual, A0, the Git provenance chain, the two-step acceptance, the exact-HEAD
rule, A1/A2 evidence handling, the retry-layer distinction, CMD-only commands,
the credential boundary, L16, the exclusions, explicit package binding, the
external launcher hash binding, and the venv and TOCTOU residuals — are
unchanged.

### 13.2 Changelog — R5 against R4

| Finding | Change |
|---|---|
| Python site processing preceded the R4 topology gate: `-I` does not imply `-S`, so `site` processed the editable `.pth` and attempted `sitecustomize` before any launcher line ran | §7.1: authorized invocation is now `-I -S -B -X pycache_prefix=…`, with observed `-I -S` start-up facts recorded read-only; G0 requires `sys.flags.no_site == 1` and that `site`, `sitecustomize`, `usercustomize` are not loaded (terminal on failure); G2 requires every initial `sys.path` entry to lie under the base interpreter; new G3a appends `<ROOT>\.venv\Lib\site-packages` by direct `sys.path.append` only after G2 and G3, with no `site.main()`/`site.addsitedir()`; `<ROOT>\src` is never on `sys.path`; G6 re-checks the start-up modules and the exact final `sys.path`; §7.3 launcher text (hence `LAUNCHER_SHA256`); §7.4 replaces the `.pth` start-up residual with a bounded non-attestation statement and records the frozen verification child's normal start-up; §12.2 cases 11–18 |

A9, the §7.2a topology walk, and every other R4 closure are unchanged in
substance.

---

## Status

```text
CFG1 DESIGN — ACCEPTED / FROZEN
CFG1-L16-FU2 DESIGN/ERR1/IMPL — ACCEPTED / FROZEN
CFG1-L16-FU2-DOCSYNC — ACCEPTED / FROZEN (820e8c...)
CFG1-S1-A1 — CONSUMED / HISTORICAL ONLY
CFG1-S1-A2 — CONSUMED / HISTORICAL ONLY
CFG1-S1-A3-AUTH — CANDIDATE / PENDING CONTENT + POST-COMMIT REVIEW
CFG1-S1-A3 — NOT AUTHORIZED
CFG1-LIVE-S2 — NO-GO
DX1 — NO-GO
M4 — HOLD / NO-GO
```
