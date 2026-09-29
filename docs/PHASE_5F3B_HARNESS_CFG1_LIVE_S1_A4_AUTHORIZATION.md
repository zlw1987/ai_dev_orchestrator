# Phase 5F3B-HARNESS-CFG1-LIVE-S1-A4-AUTH — Fresh Stage-1 Execution Authorization (R1)

```text
5F3B-HARNESS-CFG1-LIVE-S1-A4-AUTH CANDIDATE (R1)
PENDING CONTENT REVIEW + POST-COMMIT CLOSURE REVIEW
SOURCE BOUND        24a2c50a5492a001d207514020a33e609f508563
EXECUTION ID        CFG1-S1-A4   (NOT AUTHORIZED)
```

> **THIS DOCUMENT IS A CANDIDATE. IT IS NOT AN AUTHORIZATION.**
>
> It carries no execution authority of any kind. Authority can arise **only**
> through the procedure of §3, and **only** from the post-commit closure
> reviewer's record, which lives outside this file. Until that record exists,
> `CFG1-S1-A4` is **NOT AUTHORIZED**.
>
> **Disclosure of what the turn that authored this file did (exact).** It read
> the CFG1, AR2, qualification and `ai_dev_orchestrator` sources, the frozen
> design chain and the A1/A2/A3 authorizations; ran read-only Git commands;
> hashed the six historical evidence files; ran standard-library scripts
> located outside the checkout that parsed repository source with `ast`
> (without importing any of it) and walked the five source roots without
> following links; and ran the checkout's venv interpreter bare, under
> `-I -S -B`, only to print its own start-up facts. It imported no CFG1, AR2,
> qualification or `ai_dev_orchestrator` module; called neither
> `establish_stage_output_authority` nor `run_cfg1_stage` nor the Pi identity
> gate; launched no Node or Pi process; contacted no endpoint; opened no
> socket; sent no prompt; read no credential or endpoint value; created
> nothing under the CFG1 results root; modified no existing file; created
> exactly this one file; and committed nothing. Authoring this file is never
> permission to execute A4 in the same turn, session, or agent invocation.

---

## 0. Authority relationship

This document is subordinate to, and never amends, the following, all present
in the tree of `24a2c50a5492a001d207514020a33e609f508563`:

1. the frozen CFG1 base design,
   [`PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md);
2. CFG1-L16-FU2 R2 with erratum ERR1,
   [`..._L16_FU2_RUNTIME_CAPABILITY_OBSERVATION_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_L16_FU2_RUNTIME_CAPABILITY_OBSERVATION_DESIGN.md),
   [`..._L16_FU2_ERR1_R37_SIDECAR_TRANSPORT_ERRATUM.md`](PHASE_5F3B_HARNESS_CFG1_L16_FU2_ERR1_R37_SIDECAR_TRANSPORT_ERRATUM.md);
3. FU1 R6,
   [`..._L1_BOUNDARY_FU1_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md),
   with OC-3 AMEND1 (OC-3 closed by probe removal),
   [`..._FU1_OC3_AMEND1_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_OC3_AMEND1_DESIGN.md),
   and Y6 AMEND2 (retained-handle scrub),
   [`..._FU1_Y6_AMEND2_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_Y6_AMEND2_DESIGN.md);
4. the OC-4 closure-totality design,
   [`PHASE_5F3B_HARNESS_CFG1_OC4_CLOSURE_TOTALITY_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_OC4_CLOSURE_TOTALITY_DESIGN.md);
5. the P1 topology-admissibility amendment,
   [`..._L1_BOUNDARY_P1_TOPOLOGY_ADMISSIBILITY_AMEND_DESIGN.md`](PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_P1_TOPOLOGY_ADMISSIBILITY_AMEND_DESIGN.md);
6. the governance policy,
   [`AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md`](AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md);
7. the shipped production source at `24a2c50a5492a001d207514020a33e609f508563`
   (FU1 implementation, OC-4 implementation `fbc40c2…`, OC-5 implementation
   `a352d9a…`, P1 correction `24a2c50…`).

Where this document could be read as disagreeing with any of them, **they
govern and this document is wrong**. Where it could be read as disagreeing with
the shipped code, **the code's fail-closed refusal governs**. Nothing here
instructs any layer to accept an input it would refuse or to skip a proof it
would perform. Some of those files carry in-file "candidate" banners; their
acceptance, like this document's, is recorded outside the files.

### 0.1 Pre-A4 barrier sequence (FU1 R6 §17, as restated by AMEND1 §17/§19)

| Item | Subject | Status as supplied to this authoring turn |
|---|---|---|
| 1 | FU1 R6 + AMEND1 accepted/frozen | accepted / frozen (recorded outside this file) |
| 2 | OC-3 | CLOSED BY PROBE REMOVAL (AMEND1) |
| 3 | FU1 implementation reviewed/frozen (incl. Y6 AMEND2 corrective and the issuance authority surface) | accepted / frozen |
| 4 | OC-4 closure totality | CLOSED / FROZEN |
| 5 | OC-5 L3 exact-type/truthiness | CLOSED / FROZEN |
| 6 | operator restores the approved Pi environment | reported done by the operator |
| 7 | read-only static pre-A4 identity/seam verification | reported by the operator as `PI_IDENTITY_PROVEN` from the canonical gate on the supported workstation at `24a2c50…`, after the accepted P1 correction |
| 8 | a new A4 authorization separately reviewed and accepted | **this candidate** — binding in §3 |

These statuses are **not** re-derived by this file and are not authority. The
post-commit closure reviewer confirms them. Item 7's result is historical and is
**never** an admission input: the launcher re-runs the same canonical gate
itself (§8), and L1 re-proves from scratch (§8.4).

**AR2 live execution remains NO-GO** while OC-6 is unresolved, independent of
this document.

---

## 1. Harness-version scope

A4, if eventually accepted, is authorized **only** against the current CFG1
historical qualification profile: the reviewed Pi Coding Agent **0.85.1** seam,
i.e. exactly the 20 entries of `preflight.PINNED_PI_SEAM_DIGESTS` (among them
the Pi root's own `package.json`) that `pi_identity.prove_pi_identity` proves.

- This is **not** a permanent Harness-version policy and **not** a product
  requirement that Pi stay at 0.85.1. It pins this one qualification run to the
  profile its frozen code can prove.
- A future Pi/Harness upgrade is expected to be handled as a **new
  Harness-version/profile qualification** in a separate Harness-evolution
  phase and, once accepted, adopted **without rewriting historical
  qualifications** (consistent with `AIDO_RUNTIME_HARNESS_ROADMAP.md` §2.1: a
  harness version change never silently carries a PASS forward, and the
  re-qualification decision is separate and per change).
- This document does **not** implement, design, or pre-authorize that evolution
  mechanism, and it makes no version-adoption decision for 0.85.1 or any other
  version.
- A static pass establishes **filesystem/package provenance only**: byte
  identity of the 20 files with the reviewed bytes, plus the two identities. It
  is **not** a runtime-reported Pi version and does **not** prove launchability
  (AMEND1 §13). No A4 text, console line or evidence field may call it an
  observed or reported version.

---

## 2. Git provenance of the code that will run

```text
24a2c50a5492a001d207514020a33e609f508563   accepted P1 topology-admissibility correction
        │                                  (the production source A4 proposes to execute)
        │
<A4_AUTH_COMMIT>                           exactly one commit adding exactly
                                           docs/PHASE_5F3B_HARNESS_CFG1_LIVE_S1_A4_AUTHORIZATION.md
```

Consequence: the tracked tree at `<A4_AUTH_COMMIT>` equals the tree at
`24a2c50…` plus one Markdown file. Every production byte is therefore the
`24a2c50…` byte.

Git provenance does **not** prove that the launcher process executes that
source: Python resolves imports from its import machinery, not from Git. The
source-origin gate of §7 closes that gap; without it, exact HEAD is necessary
but not sufficient.

**There is no equivalence class.** No descendant of `<A4_AUTH_COMMIT>`, no
sibling, no rebase, amend or cherry-pick of it, and no commit that "only
touches documentation" inherits anything. No operator or reviewer decides
semantic equivalence. Any other HEAD — including one that differs only by a
later docs-only commit, or by the post-commit acceptance record itself — is
outside this authorization and fails admission fact A1 (§10).

---

## 3. Two-step acceptance and the concrete post-commit binding

The candidate cannot contain its own future commit SHA or its own digest. The
binding is therefore established outside this file, in this exact order.

### 3.1 Step 1 — content review (grants nothing)

An independent reviewer reviews the exact candidate bytes and records, outside
the repository:

- `CANDIDATE_SHA256`: SHA-256 of the exact candidate file bytes reviewed;
- `CANDIDATE_BLOB`: the Git blob id of those bytes (`git hash-object --
  <path>` reads only and writes no object);
- `LAUNCHER_SHA256`: SHA-256 of the launcher text of §9.1, defined as the exact
  lines strictly between the opening fence line that is exactly ```` ```python ````
  (the only such line in this file) and its closing fence line, each line
  terminated by one LF, with no other bytes;
- the verdict.

The candidate is required to be **LF-only** (no CR byte) and its launcher text
**ASCII-only**. This checkout has `core.autocrlf=true`: an LF-only file is
stored unchanged, so the committed blob can be byte-identical to the reviewed
bytes. A candidate containing a CR byte, or any mismatch in §3.3, fails closed.

**Content acceptance grants NO live execution authority**, under any
circumstances.

### 3.2 Step 2 — the operator commits exactly this one file

The operator commits the content-reviewed file, unchanged, as **one** commit
whose **only parent is `24a2c50a5492a001d207514020a33e609f508563`**, and which
adds exactly `docs/PHASE_5F3B_HARNESS_CFG1_LIVE_S1_A4_AUTHORIZATION.md` and
nothing else. Its SHA becomes `<A4_AUTH_COMMIT>`. This step grants nothing.

### 3.3 Step 3 — post-commit closure review

An independent reviewer inspects `<A4_AUTH_COMMIT>` and verifies, mechanically
and read-only:

| # | Fact | Read-only method (illustrative) |
|---|---|---|
| P1 | exactly one parent, and it is `24a2c50a5492a001d207514020a33e609f508563` | `git rev-list --parents -n 1 <A4_AUTH_COMMIT>` |
| P2 | the commit adds exactly this one path and changes nothing else | `git diff-tree --no-commit-id -r --name-status <A4_AUTH_COMMIT>` → exactly `A` + this path |
| P3 | committed blob id == `CANDIDATE_BLOB` | `git rev-parse <A4_AUTH_COMMIT>:docs/PHASE_5F3B_HARNESS_CFG1_LIVE_S1_A4_AUTHORIZATION.md` |
| P4 | SHA-256 of the committed blob bytes == `CANDIDATE_SHA256` | `git cat-file blob <A4_AUTH_COMMIT>:<path>` redirected to a file outside the checkout, then `certutil -hashfile <that file> SHA256` |
| P5 | `LAUNCHER_SHA256` recomputed from the committed blob equals the content-review value | the §3.1 definition applied to the P4 file |
| P6 | the results tree in the commit is exactly the two tracked A3 files with their §5.1 blob ids — nothing under `CFG1-S1-A4`, no A1/A2 file | `git ls-tree -r <A4_AUTH_COMMIT> -- experiments/pi_harness_cfg1/results` |
| P7 | per the reviewed operator/authorization history, no `CFG1-S1-A4` establishment call is known or has been authorized (§4.2 (a)) | record review; no tool can prove it |

Any failure → **not accepted**. Nothing is repaired, amended, force-pushed, or
re-labelled into acceptance. A corrected file requires a new content review and
a new commit whose parent is still exactly `24a2c50…`.

### 3.4 Step 4 — the only source of authority

**Only the post-commit closure reviewer's record** may mark
`CFG1-S1-A4-AUTH` **ACCEPTED / FROZEN** and authorize the one A4 execution.
That record names, verbatim: `<A4_AUTH_COMMIT>` (full 40-hex SHA),
`A4_AUTH_BLOB` (== `CANDIDATE_BLOB`), `CANDIDATE_SHA256`, `LAUNCHER_SHA256`, and
P1–P7 as verified.

The record lives **outside** the branch being executed. Recording it as a
further commit on that branch would move HEAD off `<A4_AUTH_COMMIT>` and fail
A1 (§10) — the intended fail-closed result. This file contains no
self-acceptance clause, no conditional activation, and no "valid unless
objected to" wording.

---

## 4. The A4 identity

### 4.1 The literal

```text
CFG1-S1-A4
```

This is the **only** authorization-supplied value in this document. It is a
fixed, human-chosen ASCII literal of length 10 matching the frozen grammar
`[A-Za-z0-9_-]{1,64}` (`stage_output.STAGE_EXECUTION_ID_PATTERN`, applied by
`fullmatch` with `type(value) is str`). It contains no `/`, `\`, `.`, `:`,
whitespace, control or non-ASCII character, is passed verbatim, and encodes no
clock, counter, host or process value. Everything else A4 uses — stage schedule,
arms, model, provider, route class, task, prompt, fixture, seam table, settings,
bounds, record schemas — is owned by the frozen code (§11) and is **not**
supplied here.

### 4.2 What "unused" rests on — three grounds and one residual

**(a) Reviewed operator/authorization history (attestation).** `CFG1-S1-A4` has
never been authorized and no call with it is known. The post-commit record
states it (P7) and the operator re-attests it at admission (A0). It is the only
ground that speaks to calls that left no trace.

**(b) Filesystem and history (mechanical, limited).** Observed read-only at
authoring time:

| Check | Result |
|---|---|
| `RESULTS_ROOT\CFG1-S1-A4` | **absent** |
| any path containing `CFG1-S1-A4` in the working tree (excluding `.git`, `.venv`) | none |
| any path containing `CFG1-S1-A4` in any reachable commit | none |
| any file content containing `CFG1-S1-A4` in the working tree or any reachable commit | none (before this file) |
| `RESULTS_ROOT` directory listing | exactly `CFG1-S1-A1`, `CFG1-S1-A2`, `CFG1-S1-A3` |

This proves the absence of a **surviving** namespace or artifact, not that no
establishment call ever occurred.

**(c) Runtime exclusive create (mechanical, after namespace creation).** Once
an establishment call has created `RESULTS_ROOT\CFG1-S1-A4`, any later call with
the same literal refuses `EXECUTION_DIRECTORY_EXISTS` before any run.

**Residual (stated, not closed).** An establishment call that failed *before*
creating the execution directory (e.g. a `RESULTS_ROOT` provenance refusal, or
`EXECUTION_DIRECTORY_NOT_CREATED`) consumes A4 (§13) while leaving no durable
marker (frozen design §16.3.7 hard stop). Neither (b) nor (c) can detect it. If
the operator knows of, or has any indication of, any earlier `CFG1-S1-A4` call —
including console output naming no artifact — A4 is **consumed** and must not be
invoked. This document creates no ledger and requires no code change to close
this residual.

---

## 5. A1, A2, A3 — historical only

### 5.1 The six evidence files

Paths are relative to `RESULTS_ROOT` = `experiments\pi_harness_cfg1\results\`.
Digests are of AIDO's own emitted evidence, never of a credential or endpoint;
all six matched at authoring time, and all six are LF-only.

```text
SHA-256                                                           path                               git state
315e5780a07ab3da3fdee5dd38f61b6797690db389217e1b8275200b28219cec  CFG1-S1-A1/S1_01_Q.json            untracked
fee44394ed8a942bdaed805dd3336c8b90bf15e4d6075e768ac545aab22bcfb3  CFG1-S1-A1/S1_stage_closure.json   untracked
e9a50844f1eb03879c34c988de0e1a54983af1d44ef3546055c8c8953ea7b796  CFG1-S1-A2/S1_01_Q.json            untracked
7027c35ce023c229dfab6fb54b7ba75a4938797ce65ca628e92ca7404d10d783  CFG1-S1-A2/S1_stage_closure.json   untracked
0892027299c8725d98252e8fe502c885d9e55566ccef640763d0b77e8906f8bf  CFG1-S1-A3/S1_01_Q.json            tracked, blob 30adb81e5be65bf3a9a680eff7d02f1306cfe5b0
d19708cc85284e0532be985c02f05396561f65f3e4310bdb7d7b3381e26c16b2  CFG1-S1-A3/S1_stage_closure.json   tracked, blob 70c4b4d7f17c3dc3d60e458fc95711105e1e9b31
```

The A3 files were committed in `306493ac…` and are tracked at `24a2c50…`; their
working-tree bytes equal their HEAD blob bytes. The A1/A2 files are untracked
and hidden from ordinary `git status` by `.git/info/exclude`.

### 5.2 Required state (admission A5 and throughout)

- all six: present at their exact path as regular files (not a directory,
  symlink, or reparse point), byte-identical per §5.1;
- A1/A2: `git ls-files -- <path>` returns nothing;
- A3: `git ls-files -s -- <path>` returns exactly the §5.1 blob id at stage 0,
  and (with A2/A3 of §10) the working copy equals HEAD.

Ordinary `git status`, `.git/info/exclude`, `.gitignore` and
`core.excludesFile` are never evidence and never admission inputs, and are never
edited for admission.

### 5.3 Outcomes, recorded for distinction only

| Attempt | Source | Outcome (historical record) | Status |
|---|---|---|---|
| `CFG1-S1-A1` | `eea76c1…` | ordinal 1 refused at L4 (`CREDENTIAL_BOUNDARY_FAILED`); halted | consumed / historical only |
| `CFG1-S1-A2` | `eea76c1…` | ordinal 1 halted at L16 (`CONFIG_SHAPE_MISMATCH`); zero prompt writes | consumed / historical only |
| `CFG1-S1-A3` | `bfae384…` source at `596b5cd…` | v1 record: ordinal 1 / arm Q refused at L1 (`OFFLINE_PREFLIGHT_FAILED`, `pi_observed_version = UNRECOGNIZED`, L27 closure unproven); stage closed `LIFECYCLE_CLOSURE_UNPROVEN` after ordinal 1 | consumed / historical only |
| `CFG1-S1-A4` | `24a2c50…` source at `<A4_AUTH_COMMIT>`, proven imported by §7 | — | **not authorized** |

### 5.4 Non-participation

- A4 is a completely fresh Stage-1 execution beginning at ordinal 1 in a new
  namespace. It is not a retry, resume, replacement, continuation, replay,
  repair or conversion of A1, A2 or A3, and they contribute **zero samples**.
- A1/A2 records are v1; A3's records are `pi-harness-cfg1-run.v1` and
  `pi-harness-cfg1-stage-closure.v1` produced by the pre-FU1 implementation.
  They are never normalized, re-projected, re-validated as v2, or compared as
  though v1's retired `pi_observed_version` measured anything a v2 A4 record
  states. No A1/A2/A3 record participates in any A4 contrast, count, tally,
  classification, halt decision or closure predicate.
- No A1/A2/A3 file is read into, edited, re-serialized, renamed, moved, copied,
  deleted, or (A1/A2) committed — before, during or after A4. A4 writes nothing
  under `CFG1-S1-A1\`, `CFG1-S1-A2\` or `CFG1-S1-A3\`.
- The A1, A2 and A3 authorization documents and the A3 launcher text confer
  nothing on A4. Running any earlier launcher is not authorized by this
  document. Any disposable workspace tree an earlier attempt may have left in
  the user temp directory is never read, reused or removed by A4 (L27 removes
  only the tree A4's own registry minted, by identity).

---

## 6. What was re-derived from A3, and why

A3's authorization is reference material only. Every row below was re-checked
against current source.

| A3 element | A4 disposition | Reason |
|---|---|---|
| two-step acceptance; external post-commit record; exact-HEAD rule; no equivalence class; LF-only under `core.autocrlf=true` | **preserved** | still sound; parent changes to `24a2c50…` and the chain shortens to one commit |
| `-I -S -B -X pycache_prefix=…` invocation; G0–G6 mechanism (explicit `SourceFileLoader` binding of four packages, site-packages appended only after binding, full origin audit, bytecode isolation) | **preserved** | the four packages and their roots are unchanged (§7.4) |
| five source roots and the no-follow topology walk (A3 §7.2a) | **preserved** | FU1/Y6/OC-4/OC-5/P1 added modules only inside `experiments\pi_harness_cfg1` |
| A9 untracked-shadow check and its admitted set | **preserved** | same directories cover every import root |
| credential names, session-only CMD mapping, PRESENT/MISSING checks | **preserved** | frozen carrier model unchanged |
| consumption at the first establishment call; three "unused" grounds plus residual | **preserved** | frozen §16.3.7 unchanged |
| G4 lineage list | **changed** — adds `pi_harness_cfg1.pi_identity`, `pi_harness_cfg1.pi_fs_leaves`, `pi_harness_cfg1.config_issuance`, `pi_harness_cfg1.environment`, `ai_dev_orchestrator.file_editing.windows_write` | with A3's list, three modules of the current static closure could first load only **after** consumption; with A4's list the pre-consumption load covers the whole closure (§7.4) |
| G6 checks | **changed** — adds the checkout-root derivation of P, identity of the proof functions L1/L14 use, and the gate's closed vocabulary | answers "same canonical `prove_pi_identity`, genuine leaves" mechanically |
| launcher location / cwd | **changed** — new G0 launch-directory check; cwd pinned to a two-entry directory outside `<ROOT>` | Git resolution is `shutil.which`, cwd-first on Windows (OC-7); an unpinned cwd could make L1 refuse **after** consumption |
| — | **new** G7: the canonical `pre_consumption_pi_identity_gate`, exact `PI_IDENTITY_PROVEN` only | FU1 AM-7 / AMEND1 §12 require it for every future live authorization |
| — | **new** G8: re-audit after G7 | proves the Pi gate loaded no foreign code and wrote no bytecode |
| A3 launcher discarded `run_cfg1_stage`'s result | **changed** — bounded, pattern-filtered console reporting of the returned closed codes | hard-stop dispositions are console-only by design (§16.3.7); a launcher that discards them makes them invisible |
| A3 "launcher reads no environment variable value" | **retired** | the gate reads the `PATH` value by name (AMEND1 §12.2); the launcher itself still reads none |
| A3 "Pi exactly 0.85.1, re-proven at L1" / v1 record schema | **retired** | static identity only (§1); A4 emits `pi-harness-cfg1-run.v2` / `-refusal.v2` |
| A3 evidence set (A1/A2 only, all untracked) | **changed** — six files; A3's are tracked | `306493ac…` committed A3's records |
| — | **new** admission checks: temp directory outside `<ROOT>`; Git resolution sanity; no concurrent writer | §15 analysis (endpoint/token-bearing material must never land inside the checkout) |

---

## 7. Pre-consumption source-origin gate (G0–G6), re-derived

### 7.1 Which interpreter, and what runs before the first launcher line

Observed read-only at authoring time (bare interpreter, no lineage import):

| Fact | Observed |
|---|---|
| interpreter invoked | `<ROOT>\.venv\Scripts\python.exe` (the venv redirector); it starts the base CPython named by `.venv\pyvenv.cfg` `home` (`C:\Users\<user>\AppData\Local\Python\pythoncore-3.14-64`) |
| version | base CPython **3.14.7** running; `pyvenv.cfg` records creation under 3.14.3 (the base was upgraded in place). Recorded, not attested |
| `include-system-site-packages` | `false` |
| `.pth` files in `<ROOT>\.venv\Lib\site-packages` | exactly one, the editable install, one line `<ROOT>\src`; no `distutils-precedence.pth`, no `sitecustomize`/`usercustomize` there |
| flags under `-I -S -B` | `isolated=1`, `no_site=1`, `dont_write_bytecode=1`, `safe_path=True`, `ignore_environment=1`, `no_user_site=1` |
| `sys.prefix` / `sys.executable` | `<ROOT>\.venv` / `<ROOT>\.venv\Scripts\python.exe`; `sys.base_prefix` is the base install |
| initial `sys.path` | exactly four base entries (`python314.zip`, `DLLs`, `Lib`, base directory); no `<ROOT>`, venv, site-packages, cwd or script entry |
| import machinery | `meta_path = [BuiltinImporter, FrozenImporter, PathFinder]`; `path_hooks = [zipimporter, FileFinder.path_hook.<locals>.path_hook_for_FileFinder]`; importer cache values `None`/`FileFinder` |
| modules loaded at start | interpreter bootstrap, `encodings.*`, `os`, `ntpath`, `stat`, `codecs`, `winreg`, `zipimport` and similar — all base-interpreter; `site`, `sitecustomize`, `usercustomize`, `_distutils_hack` **not** loaded |
| `pycache_prefix` directory after start-up | still empty |

**What executes before the first launcher line**, exactly: the venv redirector
executable, the base CPython executable and its DLLs, the frozen/bootstrap
modules and `encodings` from the base install. Under `-S` no `site`, no `.pth`
line, no `sitecustomize`/`usercustomize`; under `-I` no `PYTHON*` variable
(including `PYTHONPATH`, `PYTHONSTARTUP`, `PYTHONHOME`, `PYTHONPYCACHEPREFIX`),
no user site, and neither the cwd nor the script directory on `sys.path`. **No
repository-derived code runs before G0**, and G0 refuses unless that is still
true. Outside AIDO's observation: OS-level injection (debugger/IFEO keys,
AppInit/AV hooks, the `cmd.exe` AutoRun key) and the bytes of the interpreter
itself (§17).

### 7.2 Invocation

```text
cd /d <LAUNCH_DIR>
<ROOT>\.venv\Scripts\python.exe -I -S -B -X pycache_prefix=<LAUNCH_DIR>\pycache <LAUNCH_DIR>\cfg1_s1_a4_launcher.py
```

- `<ROOT>` is `C:\dev\ai_dev_orchestrator`.
- `<LAUNCH_DIR>` is an absolute directory outside `<ROOT>`, with no space in its
  path, not a link and under no link, created fresh by the operator for A4, and
  containing **exactly two entries**: the regular file `cfg1_s1_a4_launcher.py`
  whose bytes are the §9.1 launcher (A10), and the **empty** directory
  `pycache`. The process cwd **is** `<LAUNCH_DIR>`.
- Why the cwd is pinned: the frozen L1 Git resolution
  (`resolve_git_executable(workspace_root=os.getcwd())`, `shutil.which("git")`)
  consults the cwd **first** on Windows (OC-7). A `git.*` in the cwd would be
  refused by the frozen containment check — but only at L1, **after**
  consumption. With a two-entry cwd nothing there can match. The cwd is never on
  `sys.path` (`-I`).
- `-B` plus an empty prefix outside `<ROOT>`: bytecode is looked up **only**
  under the prefix and nothing is written, so no stale or planted in-tree `.pyc`
  can execute.

### 7.3 Gate conditions

Inside the launcher, before any lineage import and before
`establish_stage_output_authority`, the gate refuses (prints one fixed code,
exits `2`, and does **not** call `establish_stage_output_authority`) unless all
hold. Class: **O** = operator-correctable, **T** = terminal (§10 rules).

| Gate | Condition | Class |
|---|---|---|
| G0 | isolated, no-site, no-bytecode flags; `site`/`sitecustomize`/`usercustomize` not loaded; `<ROOT>` is its own canonical path; `sys.prefix` is `<ROOT>\.venv`; base interpreter outside `<ROOT>`; launcher outside `<ROOT>`; `sys.pycache_prefix` set, an empty directory, outside `<ROOT>`; launch directory canonical, outside `<ROOT>`, equal to the cwd, holding exactly the launcher file (regular, not link-like) and the empty `pycache` directory (not link-like), with the prefix exactly `<LAUNCH_DIR>\pycache` | T for `G0_INTERPRETER_FLAGS`, `G0_SITE_LOADED`, `G0_ROOT_NOT_CANONICAL`; O otherwise. Flags and start-up modules are checked first, so every later G0 code is reached only in a process in which `site` did not run |
| G1 | default import machinery exactly (meta path, path hooks, importer cache types) | T |
| G2 | no lineage module preloaded; no empty `sys.path` entry; every initial entry under `sys.base_prefix` and none under `<ROOT>`; **no symlink, junction or other reparse point** anywhere in the five source roots or on the lexical path from `<ROOT>` to each (§7.5) | T |
| G3 | each of the four top-level packages loaded **explicitly** from its exact `__init__.py` by `SourceFileLoader`, search path pinned to exactly its directory — never found through `sys.path` | T |
| G3a | only after G2/G3: `<ROOT>\.venv\Lib\site-packages` (canonical directory) appended by one plain `sys.path.append` — no `site.main()`, no `addsitedir`, no `.pth` processing; `<ROOT>\src` never added | T |
| G4 | the lineage of §7.4 imports without error | T |
| G5 | every loaded module of the four packages: `SourceFileLoader`; canonical `.py` origin inside its package directory; bytecode path under the prefix; subpackage search path exactly its own directory. Every other module with a filesystem origin lies under the base install or venv site-packages; `httpx` under the latter | T |
| G6 | `stage_output._CAPTURED_PACKAGE_DIR` and `stage_runner._GENUINE_PACKAGE_DIRECTORY` equal `<ROOT>\experiments\pi_harness_cfg1` (so `RESULTS_ROOT` is the directory A5/A6 examined); `pi_identity._GENUINE_CHECKOUT_ROOT` equals `<ROOT>` (P's containment refusal is anchored to the audited checkout); `run_executor.prove_pi_identity`, `.genuine_pi_proof_leaves` and `.reprove_pi_identity_for_launch` **are** (identity) the `pi_identity` functions; the gate, `prove_pi_identity` and both genuine leaves are plain functions compiled from their audited module files; `PI_IDENTITY_GATE_PASSED == "PI_IDENTITY_PROVEN"` and `PI_IDENTITY_GATE_CODES` equals the launcher's closed five-code vocabulary; prefix still empty; start-up modules still absent; `sys.path` is exactly the initial entries plus site-packages | T |

G7 and G8 are in §8.

### 7.4 Import closure — what is covered, and when it loads

A static `ast` analysis of the current source (imports inside functions
included; imports guarded by `if TYPE_CHECKING:` excluded, since they never
execute; conservative about `from X import name` when a same-named submodule
file exists) from the entry points `pi_harness_cfg1.stage_output`,
`pi_harness_cfg1.stage_runner` and `pi_harness_cfg1.pi_identity` gives:

| Package | Modules in the static closure | Source root |
|---|---|---|
| `ai_dev_orchestrator` | 37 | `<ROOT>\src\ai_dev_orchestrator` |
| `ar2` | 18 | `<ROOT>\experiments\pi_external_runtime_ar2\ar2` |
| `qualification` | 24 | `<ROOT>\experiments\pi_implementer_qualification\qualification` |
| `pi_harness_cfg1` | 28 | `<ROOT>\experiments\pi_harness_cfg1` |
| **total** | **107** | four roots, all already covered by A3's gate |

Third-party packages in the closure: `httpx` and `pydantic` (with their own
dependencies), from venv site-packages only. Everything else is standard
library. No module in the closure uses `importlib.import_module`,
`__import__`, `runpy`, `exec`/`eval` of imported code, or `import site`.

- **No new source root.** Every production module added since A3's source
  (`cfg1_extension`, `extension_issuance`, `extension_pins`, `pi_fs_leaves`,
  `pi_identity`) lives in `experiments\pi_harness_cfg1`. `src`, `ar2` and
  `qualification` production files are byte-unchanged since `bfae384…`.
- **The Pi extension sources** (`ipc.ts`, `tools.ts`, `index.ts`,
  `package.json`) are **data** read at L11 from
  `<ROOT>\experiments\pi_external_runtime_ar2\extension` (derived from
  `ar2.__file__`, which G5 audits), by a no-follow single read accepted only on
  exact length and SHA-256 pins (`extension_pins`). That directory stays in the
  topology walk and in A9.
- **Coverage.** With A3's lineage the eager closure is 104 modules; the three
  that would first load after consumption are `pi_harness_cfg1.config_issuance`,
  `pi_harness_cfg1.environment` and
  `ai_dev_orchestrator.file_editing.windows_write`. With A4's lineage the eager
  closure is all **107**, so every statically reachable lineage module is loaded
  and origin-audited (G5, G8) **before** consumption, and every later
  function-level import of one of them is a `sys.modules` hit that reads no
  source. This is a static-analysis claim, reproducible by the reviewer; any
  module it missed would still be structurally pinned after consumption exactly
  as in A3 (parent search path pinned by G3, default finders by G1, link-free
  topology by §7.5, untracked content by A9).
- **Import-time behaviour of the closure** (audited statically for top-level
  calls): dataclass/constant construction, `Path(__file__).resolve()`,
  `ctypes.WinDLL` binding of the system `kernel32`/`advapi32` DLLs, and the one-shot in-memory
  code-object bindings `win_config_authority.bind_config_generator_authority()`
  and `bind_extension_writer_authority()` (a second bind is refused, so a
  foreign pre-bind cannot survive G2's "nothing preloaded" check). No module
  reads an environment variable, opens a network connection, starts a process,
  or writes a file at import.
- **Cannot a supported caller replace the executor or the leaves?**
  `run_cfg1_stage(authority, /)` takes nothing else and binds the genuine
  executor itself (`bind_genuine_cfg1_run_executor`, mint-registry identity of
  token and callable); a non-genuine executor is refused against the genuine
  package root (G6 proves the root is genuine). `genuine_pi_proof_leaves()`
  takes no parameter. The only way to substitute either is same-process code,
  and before consumption the only code in the process is the audited lineage and
  the reviewed launcher.

### 7.5 Source-tree topology (inside G2, before G3)

Unchanged from A3 §7.2a in mechanism and scope. The five roots are:

```text
<ROOT>\src
<ROOT>\experiments\pi_harness_cfg1
<ROOT>\experiments\pi_external_runtime_ar2\ar2
<ROOT>\experiments\pi_external_runtime_ar2\extension
<ROOT>\experiments\pi_implementer_qualification\qualification
```

Every entry at every depth — including `__pycache__`, `tests` and `results` —
is inspected as the lexical directory entry (`is_symlink`, `is_junction`, and
`FILE_ATTRIBUTE_REPARSE_POINT` from `stat(follow_symlinks=False)`); the walk
never enters a link; any link-like entry, missing attribute, missing component
or `OSError` refuses `G2_REPARSE_SOURCE_TREE`. At authoring time the walk saw
489 entries (206, 149, 51, 4, 79) and no reparse entry, and `git ls-files -s`
shows no mode-`120000` entry in these roots. `<ROOT>` and its ancestors are
covered only by G0's canonical-path check (link-type redirection), not for
other reparse types.

---

## 8. Canonical static Pi identity gate (G7) and post-gate audit (G8)

### 8.1 The call

After G6, and only then, the launcher calls:

```text
pi_harness_cfg1.pi_identity.pre_consumption_pi_identity_gate(os.environ)
```

- It is the **existing canonical** gate: it calls the **same**
  `prove_pi_identity` function object with the **same** genuine leaves
  (`genuine_pi_proof_leaves()`) that L1 and L14 use, and returns exactly one
  closed string. The launcher does not reimplement P, copy its resolver or seam
  table, call `prove_pi_identity` itself, or read any P internals.
- The launcher passes the process's own `os.environ` object — the same mapping
  `bind_genuine_cfg1_run_executor` later hands L1 — without copying or
  enumerating it. P0 reads exactly **one** name from it, `PATH`, by name; the
  `PATH` value is non-secret. The launcher itself reads no environment value.
- The gate starts no process, executes no Node, Pi or JavaScript, reads no
  credential or endpoint, writes nothing, never touches stage-output authority
  or `RESULTS_ROOT`, and returns nothing reusable (AMEND1 §12.3). Its only I/O is
  read-only, no-follow filesystem access to lexical paths derived from `PATH`;
  no claim is made that the OS performs no redirector I/O while servicing an
  open.

### 8.2 Decision — exact pass only

| Returned value | Launcher action | Class |
|---|---|---|
| exactly the `str` `PI_IDENTITY_PROVEN` | proceed to G8 | — |
| `PI_RESOLUTION_FAILED` or `PI_SEAM_UNPROVEN` | refuse `G7_<code>`; A4 **not consumed** | E (Pi environment) |
| `PI_IDENTITY_DRIFTED_DURING_PROOF` or `PI_IDENTITY_GATE_UNEXPECTED_FAILURE` | refuse `G7_<code>`; A4 not consumed | T |
| any other value, any non-`str`, a `str` subclass | refuse `G7_PI_GATE_MALFORMED_RETURN`; not consumed | T |
| the call raises anything | refuse `G7_PI_GATE_RAISED`; not consumed | T |

The comparison is `type(code) is str and code == "PI_IDENTITY_PROVEN"`. No
truthiness, prefix match, case-folding or membership test decides a pass. The
refusal codes are rendered only for the operator; nothing branches on them
except the E/T classification of §10.

### 8.3 G8 — re-audit after the gate

G5's full origin audit runs again over every loaded module; the prefix must
still be empty; `site`/`sitecustomize`/`usercustomize` must still be absent;
`sys.path` must be unchanged. Any failure → `G8_*`, T, not consumed.

### 8.4 What the pass does and does not carry forward

Nothing. The gate is **waste avoidance**: it returns a code, not an identity.
`run_cfg1_stage` has no parameter that could receive one. L1 runs P again from
scratch for every admitted ordinal, and L14 performs the complete uncached
20-seam re-walk, then the package-root identity, then the `node.exe` identity,
immediately before the first Node/Pi/JavaScript execution (`launch()`),
with nothing that reads the Pi tree, resolves a name or executes anything in
between. A pass means only: at that instant, `PATH` resolved admissibly to a
`node.exe` and a Pi root outside the checkout whose 20 pinned files were
byte-identical to the reviewed bytes.

---

## 9. The launcher

### 9.1 Normative text (bytes bound by `LAUNCHER_SHA256`)

```python
# CFG1-S1-A4 launcher. Normative text of the A4 authorization, section 9.1.
import importlib
import importlib.machinery as machinery
import importlib.util
import os
import re
import stat
import sys
import types
import zipimport

ROOT = r"C:\dev\ai_dev_orchestrator"
VENV = ROOT + r"\.venv"
SITE = VENV + r"\Lib\site-packages"
SRC = ROOT + r"\src"
CFG1 = ROOT + r"\experiments\pi_harness_cfg1"
PACKAGES = (
    ("ai_dev_orchestrator", SRC + r"\ai_dev_orchestrator"),
    ("ar2", ROOT + r"\experiments\pi_external_runtime_ar2\ar2"),
    ("qualification", ROOT + r"\experiments\pi_implementer_qualification\qualification"),
    ("pi_harness_cfg1", CFG1),
)
SOURCE_ROOTS = (
    SRC,
    CFG1,
    ROOT + r"\experiments\pi_external_runtime_ar2\ar2",
    ROOT + r"\experiments\pi_external_runtime_ar2\extension",
    ROOT + r"\experiments\pi_implementer_qualification\qualification",
)
LINEAGE = (
    "pi_harness_cfg1.stage_output",
    "pi_harness_cfg1.stage_runner",
    "pi_harness_cfg1.run_executor",
    "pi_harness_cfg1.pi_identity",
    "pi_harness_cfg1.pi_fs_leaves",
    "pi_harness_cfg1.config_issuance",
    "pi_harness_cfg1.environment",
    "ar2.supervisor",
    "ar2.protocol",
    "ar2.runtime_probe",
    "qualification.safety",
    "qualification.runtime_activity",
    "qualification.i2_b300_route_observation",
    "qualification.i2_secret_context",
    "qualification.semantic_live_adapters",
    "qualification.semantic_session",
    "ai_dev_orchestrator.file_editing.windows_write",
    "httpx",
)
EXECUTION_ID = "CFG1-S1-A4"
LAUNCHER_NAME = "cfg1_s1_a4_launcher.py"
PYCACHE_NAME = "pycache"
GATE_PASS = "PI_IDENTITY_PROVEN"
GATE_REFUSALS = (
    "PI_RESOLUTION_FAILED",
    "PI_SEAM_UNPROVEN",
    "PI_IDENTITY_DRIFTED_DURING_PROOF",
    "PI_IDENTITY_GATE_UNEXPECTED_FAILURE",
)
HOOK_QUALNAME = "FileFinder.path_hook.<locals>.path_hook_for_FileFinder"
STARTUP_MODULES = ("site", "sitecustomize", "usercustomize")
CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}(?::[A-Z][A-Z0-9_]{0,63})?")
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")


def refuse(code):
    print("A4_REFUSED_PRE_CONSUMPTION " + code)
    sys.exit(2)


def closed(value):
    if value is None:
        return "NONE"
    if type(value) is str and CODE.fullmatch(value):
        return value
    return "WITHHELD"


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


def launch_directory_clean(launch_dir, launcher, prefix):
    if not canonical(launch_dir) or under(launch_dir, ROOT):
        return False
    if norm(os.getcwd()) != norm(launch_dir):
        return False
    if os.path.normcase(os.path.basename(launcher)) != os.path.normcase(LAUNCHER_NAME):
        return False
    cache_dir = os.path.join(launch_dir, PYCACHE_NAME)
    if norm(prefix) != norm(cache_dir):
        return False
    names = sorted(os.path.normcase(name) for name in os.listdir(launch_dir))
    if names != sorted([os.path.normcase(LAUNCHER_NAME), os.path.normcase(PYCACHE_NAME)]):
        return False
    script = lexical_entry(launcher)
    cache = lexical_entry(cache_dir)
    if script is None or link_like(script) or not script.is_file(follow_symlinks=False):
        return False
    if cache is None or link_like(cache) or not cache.is_dir(follow_symlinks=False):
        return False
    return not os.listdir(cache_dir)


def audit_loaded(prefix):
    expected = dict(PACKAGES)
    for loaded, module in list(sys.modules.items()):
        spec = getattr(module, "__spec__", None)
        origin = getattr(spec, "origin", None)
        top = loaded.split(".")[0]
        if top in expected:
            if spec is None or type(spec.loader) is not machinery.SourceFileLoader:
                return "LINEAGE_LOADER"
            if type(origin) is not str or not origin.endswith(".py") or not canonical(origin):
                return "LINEAGE_ORIGIN"
            if not under(origin, expected[top]):
                return "LINEAGE_ORIGIN"
            if spec.cached and not under(spec.cached, prefix):
                return "LINEAGE_BYTECODE"
            locations = spec.submodule_search_locations
            if locations is not None and [norm(p) for p in locations] != [norm(os.path.dirname(origin))]:
                return "LINEAGE_SEARCH_PATH"
        elif origin is not None and type(origin) is not str:
            return "FOREIGN_MODULE_ORIGIN"
        elif origin is not None and os.path.isabs(origin):
            if not (under(origin, sys.base_prefix) or under(origin, SITE)):
                return "FOREIGN_MODULE_ORIGIN"
    return None


def gate():
    here = os.path.abspath(__file__)
    launch_dir = os.path.dirname(here)
    # G0 - interpreter, no-site start-up, launch directory, bytecode isolation.
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
    if under(here, ROOT):
        refuse("G0_LAUNCHER_INSIDE_ROOT")
    prefix = sys.pycache_prefix
    if not prefix or not os.path.isdir(prefix) or os.listdir(prefix) or under(prefix, ROOT):
        refuse("G0_PYCACHE_PREFIX")
    try:
        launch_clean = launch_directory_clean(launch_dir, here, prefix)
    except BaseException:
        launch_clean = False
    if not launch_clean:
        refuse("G0_LAUNCH_DIRECTORY")
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
    # G2 - nothing preloaded; base-interpreter sys.path only; no reparse points.
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
    # G4 - import the complete authority/execution lineage.
    for dotted in LINEAGE:
        try:
            importlib.import_module(dotted)
        except BaseException:
            refuse("G4_LINEAGE_IMPORT")
    # G5 - audit the origin of every loaded module.
    failure = audit_loaded(prefix)
    if failure is not None:
        refuse("G5_" + failure)
    httpx_spec = getattr(sys.modules.get("httpx"), "__spec__", None)
    if httpx_spec is None or type(httpx_spec.origin) is not str or not under(httpx_spec.origin, SITE):
        refuse("G5_HTTPX_ORIGIN")
    # G6 - derivations, proof-function identity, gate vocabulary, isolation.
    stage_output = sys.modules["pi_harness_cfg1.stage_output"]
    stage_runner = sys.modules["pi_harness_cfg1.stage_runner"]
    run_executor = sys.modules["pi_harness_cfg1.run_executor"]
    pi_identity = sys.modules["pi_harness_cfg1.pi_identity"]
    pi_fs_leaves = sys.modules["pi_harness_cfg1.pi_fs_leaves"]
    if norm(stage_output._CAPTURED_PACKAGE_DIR) != norm(CFG1):
        refuse("G6_RESULTS_ROOT_DERIVATION")
    if norm(stage_runner._GENUINE_PACKAGE_DIRECTORY) != norm(CFG1):
        refuse("G6_RESULTS_ROOT_DERIVATION")
    if norm(pi_identity._GENUINE_CHECKOUT_ROOT) != norm(ROOT):
        refuse("G6_PI_CHECKOUT_ROOT")
    if run_executor.prove_pi_identity is not pi_identity.prove_pi_identity:
        refuse("G6_PROOF_BINDING")
    if run_executor.genuine_pi_proof_leaves is not pi_identity.genuine_pi_proof_leaves:
        refuse("G6_PROOF_BINDING")
    if run_executor.reprove_pi_identity_for_launch is not pi_identity.reprove_pi_identity_for_launch:
        refuse("G6_PROOF_BINDING")
    bound = (
        (pi_identity, pi_identity.pre_consumption_pi_identity_gate),
        (pi_identity, pi_identity.prove_pi_identity),
        (pi_fs_leaves, pi_fs_leaves.inspect_no_follow),
        (pi_fs_leaves, pi_fs_leaves.read_bounded_digest),
    )
    for module, function in bound:
        if type(function) is not types.FunctionType:
            refuse("G6_PROOF_BINDING")
        if norm(function.__code__.co_filename) != norm(module.__spec__.origin):
            refuse("G6_PROOF_BINDING")
    if pi_identity.PI_IDENTITY_GATE_PASSED != GATE_PASS:
        refuse("G6_GATE_VOCABULARY")
    if pi_identity.PI_IDENTITY_GATE_CODES != frozenset((GATE_PASS,) + GATE_REFUSALS):
        refuse("G6_GATE_VOCABULARY")
    if os.listdir(prefix):
        refuse("G6_PYCACHE_PREFIX_WRITTEN")
    for startup in STARTUP_MODULES:
        if startup in sys.modules:
            refuse("G6_SITE_LOADED")
    if list(sys.path) != initial_path + [SITE]:
        refuse("G6_SYS_PATH_CHANGED")
    # G7 - the canonical static Pi identity/seam gate. Exact pass only.
    try:
        code = pi_identity.pre_consumption_pi_identity_gate(os.environ)
    except BaseException:
        refuse("G7_PI_GATE_RAISED")
    if type(code) is not str or code != GATE_PASS:
        if type(code) is str and code in GATE_REFUSALS:
            refuse("G7_" + code)
        refuse("G7_PI_GATE_MALFORMED_RETURN")
    # G8 - re-audit after the Pi gate.
    failure = audit_loaded(prefix)
    if failure is not None:
        refuse("G8_" + failure)
    if os.listdir(prefix):
        refuse("G8_PYCACHE_PREFIX_WRITTEN")
    for startup in STARTUP_MODULES:
        if startup in sys.modules:
            refuse("G8_SITE_LOADED")
    if list(sys.path) != initial_path + [SITE]:
        refuse("G8_SYS_PATH_CHANGED")
    return stage_output, stage_runner


def report(tag, exc):
    try:
        name = type(exc).__name__
        name = name if type(name) is str and NAME.fullmatch(name) else "WITHHELD"
        reason = closed(getattr(exc, "reason_code", None))
    except BaseException:
        name, reason = "WITHHELD", "WITHHELD"
    print(tag + " " + name + " " + reason)


def flag(value):
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "WITHHELD"


def ordinal(value):
    if value is None:
        return "NONE"
    if type(value) is int and 1 <= value <= 9:
        return str(value)
    return "WITHHELD"


def main():
    stage_output, stage_runner = gate()
    print("A4_PRE_CONSUMPTION_GATES_PASSED " + GATE_PASS)
    # Consumption boundary: the first call below consumes CFG1-S1-A4.
    try:
        authority = stage_output.establish_stage_output_authority(
            stage_id="S1", stage_execution_id=EXECUTION_ID
        )
    except Exception as exc:
        report("A4_CONSUMED_AUTHORITY_NOT_ESTABLISHED", exc)
        sys.exit(3)
    try:
        result = stage_runner.run_cfg1_stage(authority)
    except Exception as exc:
        report("A4_CONSUMED_STAGE_RAISED", exc)
        sys.exit(4)
    if type(result) is not stage_runner.Cfg1StageResult:
        print("A4_CONSUMED_STAGE_RESULT_MALFORMED")
        sys.exit(5)
    print(
        "A4_CONSUMED_STAGE_RESULT"
        + " disposition=" + closed(result.disposition)
        + " halted_after_ordinal=" + ordinal(result.halted_after_ordinal)
        + " halt_reason_code=" + closed(result.halt_reason_code)
        + " stage_closure_confirmed=" + flag(result.stage_closure_confirmed)
    )
    for entry in result.ordinal_status:
        if type(entry) is tuple and len(entry) == 2:
            print("A4_ORDINAL " + ordinal(entry[0]) + " " + closed(entry[1]))
        else:
            print("A4_ORDINAL WITHHELD")
    for console_code in result.console_codes:
        print("A4_CONSOLE_CODE " + closed(console_code))
    completed = type(result.disposition) is str and result.disposition == "STAGE_COMPLETED"
    sys.exit(0 if completed else 5)


main()
```

### 9.2 What the launcher is, and is not

- It imports only `importlib`, `os`, `re`, `stat`, `sys`, `types` and
  `zipimport` itself. It contains **no** `subprocess`, `os.system`,
  `os.startfile`, `os.spawn*`, `os.exec*`, `ctypes` or `CreateProcess` use, and
  **starts no Node, Pi, JavaScript, Git or other process** itself at any point.
  The first child process of the launcher process is the frozen L2 fixture Git,
  after consumption; the first Node/Pi/JavaScript execution is L14's `launch()`
  (§14).
- Before consumption it writes nothing (bytecode disabled, prefix proven empty
  at G0, G6 and G8) and reads no environment value; the gate reads `PATH`.
- It reads five module-level constants and compares the identities of six
  functions of audited CFG1 modules (G6); it modifies no module, injects nothing
  into the stage, and passes nothing to `run_cfg1_stage` but the authority.
- Its console output is bounded: fixed tags plus values that match a closed
  upper-case code pattern, a class-name pattern, an ordinal range or an exact
  `bool`; anything else prints `WITHHELD`. It prints no path, no exception text,
  no traceback for a caught `Exception`, no environment value, and never the
  authority object.
- Exit codes: `2` refused before consumption (**not consumed**); `3`
  establishment did not return an authority (consumed); `4`
  `run_cfg1_stage` raised (consumed); `5` returned with any disposition other
  than `STAGE_COMPLETED`, or a malformed result (consumed); `0` returned
  `STAGE_COMPLETED` (consumed). An exit code is a console fact, never evidence
  and never authority.
- It is authorization text executed by the operator, not frozen
  implementation. Passing its gates grants nothing beyond this document.

---

## 10. Operator admission checklist

Performed immediately before invocation, from the **one** fresh `cmd.exe`
session that will start the launcher, after the §3.4 record exists. All
commands are CMD-compatible and read-only; no PowerShell. `<ROOT>` is
`C:\dev\ai_dev_orchestrator`; `RESULTS_ROOT` is
`<ROOT>\experiments\pi_harness_cfg1\results`. Because the session's current
directory is `<LAUNCH_DIR>` (A13), every Git command runs as
`git -C <ROOT> …`, with repository-relative paths.

The launcher file is produced from the **committed blob**
(`git -C <ROOT> show <A4_AUTH_COMMIT>:docs/PHASE_5F3B_HARNESS_CFG1_LIVE_S1_A4_AUTHORIZATION.md`),
never from a working copy, by any method that writes nothing inside `<ROOT>` and
leaves only the two admitted entries in `<LAUNCH_DIR>`; A10 binds its bytes.

| # | Fact | Read-only method (illustrative, CMD) |
|---|---|---|
| A0 | **attestation:** no earlier `CFG1-S1-A4` establishment call of any kind is known (§4.2 (a)); no other process will write under `<ROOT>` or `<LAUNCH_DIR>`, or modify the Node/Pi installation, during admission and execution; no other CFG1, AR2 or qualification process is running | operator statement |
| A1 | HEAD == `<A4_AUTH_COMMIT>` from the §3.4 record, full 40-hex | `git -C <ROOT> rev-parse HEAD` |
| A2 | tracked working tree clean vs HEAD | `git -C <ROOT> --no-optional-locks diff --quiet HEAD --` exits 0 |
| A3 | index clean vs HEAD | `git -C <ROOT> --no-optional-locks diff --cached --quiet HEAD --` exits 0 |
| A4 | HEAD's blob for this file == `A4_AUTH_BLOB` | `git -C <ROOT> rev-parse HEAD:docs/PHASE_5F3B_HARNESS_CFG1_LIVE_S1_A4_AUTHORIZATION.md` |
| A5 | the six §5.1 files in the §5.2 state | `dir /a:-d-l <path>`; `certutil -hashfile <path> SHA256`; `git -C <ROOT> ls-files -s -- <path>` |
| A6 | no A4 namespace: `RESULTS_ROOT\CFG1-S1-A4` absent; `dir /a /b RESULTS_ROOT` lists exactly `CFG1-S1-A1`, `CFG1-S1-A2`, `CFG1-S1-A3`; `git -C <ROOT> ls-files --others -- experiments/pi_harness_cfg1/results` lists exactly the four A1/A2 paths; `git -C <ROOT> ls-files -- experiments/pi_harness_cfg1/results` lists exactly the two A3 paths | `if exist …\CFG1-S1-A4 (echo PRESENT) else (echo ABSENT)`; listings as stated |
| A7 | `AIDO_LITELLM_BASE_URL` and `PI_QUALIFICATION_B300_ROUTE_KEY` **PRESENT** in this session; values never seen | name-only checks (§12.3) |
| A8 | no admission step changes repository, index or evidence state | the methods above are read-only; `--no-optional-locks` avoids index refresh writes; no CFG1/AR2/qualification module is imported by A0–A13 |
| A9 | **no untracked import-shadow state** | `git -C <ROOT> --no-optional-locks ls-files --others -- src experiments/pi_harness_cfg1 experiments/pi_external_runtime_ar2/ar2 experiments/pi_external_runtime_ar2/extension experiments/pi_implementer_qualification/qualification` (no exclude rules applied) lists **only** paths with a `/__pycache__/` component, paths under `src/ai_dev_orchestrator.egg-info/`, and the four A1/A2 paths |
| A10 | `<LAUNCH_DIR>` per §7.2: outside `<ROOT>`, no space, fresh, exactly two entries; `cfg1_s1_a4_launcher.py` bytes match `LAUNCHER_SHA256`; `pycache` empty | `dir /a /b <LAUNCH_DIR>`; `dir /a /b <LAUNCH_DIR>\pycache`; `certutil -hashfile <LAUNCH_DIR>\cfg1_s1_a4_launcher.py SHA256` |
| A11 | the temp directory the run will use is outside `<ROOT>`: each of `TMPDIR`, `TEMP`, `TMP` is undefined or an absolute path not under `<ROOT>` (these are path values, not credentials) | `if defined TMPDIR (echo %TMPDIR%) else (echo TMPDIR UNDEFINED)`; `echo %TEMP%`; `echo %TMP%` |
| A12 | the Git the frozen L1 resolution will find is an ordinary `git.exe` outside `<ROOT>` and outside `<LAUNCH_DIR>` (OC-7 sanity only; not a pin) | from `<LAUNCH_DIR>`: `where git` — first line |
| A13 | the session's current directory is `<LAUNCH_DIR>` | `cd` |

The launcher's G0–G8 then run **inside the launcher process** and are part of
admission: they precede the consumption boundary.

Rules:

- **If any check fails, A4 is not invoked**, and nothing is repaired
  automatically — no checkout, reset, stash, clean, file edit, move, deletion,
  hash "correction", exclude edit, or Pi/Node change by AIDO.
- A failure of A0–A6, A8, A9, A11, or a **T**-class gate code ends admission
  under this authorization; what happens next requires a fresh diagnosis
  outside this document.
- A7 only (a name MISSING): the operator may perform the §12.2 mapping and then
  re-run the **entire** checklist from A0.
- A10, A12, A13, or an **O**-class gate code: the operator may correct only the
  launch directory, the launcher file copy, the session's current directory, or
  the invocation, and then re-run the entire checklist from A0. A12 failing
  because the first Git is inside `<ROOT>`/`<LAUNCH_DIR>` or is not `git.exe`
  may be corrected only by adjusting this CMD session's `PATH` (session-only, no
  `setx`), then re-running from A0.
- An **E**-class gate code (`G7_PI_RESOLUTION_FAILED`, `G7_PI_SEAM_UNPROVEN`):
  the operator may restore the approved Pi environment by operator means
  **outside AIDO** (AIDO executes nothing to diagnose it and nothing in the
  repository changes), then re-run the entire checklist from A0.
- Every admission and gate failure occurs before the consumption boundary and
  does not consume A4. Re-running admission is not a retry of A4: nothing has
  been consumed.

---

## 11. Live scope — granted only after final acceptance

If, and only if, the §3.4 record exists and §10 and G0–G8 pass, this document
authorizes exactly **one** fresh Stage-1 execution. Every value below is a
frozen fact of the code at `24a2c50…`, re-derived from source for this file —
**not** selected here.

| Bound | Frozen value (source) |
|---|---|
| execution id | exactly `CFG1-S1-A4`, used once (this document) |
| stage | exactly `S1` (`schedule.STAGE_IDS`) |
| schedule | ordinals 1–9, `Q, R, E, R, E, Q, E, Q, R`, blocks of 3, starting at ordinal 1 (`schedule._S1_SCHEDULE`, `declared_ordinals`, `LAST_ORDINAL`); never supplied, reordered, subsetted or resumed |
| arms | Q: no `compat`; R: `{"supportsDeveloperRole": false}`; E: `{"supportsReasoningEffort": false}` (`arms.ARM_COMPAT`); H is Stage 2 only and **not** reachable in S1 |
| model | exactly `qwen3-coder-next` (`identity.CFG1_MODEL_ID`), model entry `{"id": …, "reasoning": true}` |
| provider / route class | exactly `b300_pi_qualification` / `b300_litellm_proxy` (`identity.PROVIDER_ID`, `BACKEND_GATEWAY_CLASS`); API `openai-completions` |
| task / prompt / fixture | `CFG1-T1`; `fixture.CFG1_T1_PROMPT` verbatim, nothing prepended or appended; revision `32d8b7606e55bf0f8f00f3698f67f9c35188976272eba04bb5b066fe5d0f75d9`; verification argv `-B -m pytest -q -p no:cacheprovider -rf tests/test_banner.py` |
| tools | exactly `aido_read`, `aido_edit` (`identity.TOOL_ALLOWLIST`) |
| Pi profile | the 20-entry `PINNED_PI_SEAM_DIGESTS` (historical 0.85.1 profile, §1), proven statically by P at the gate, at L1, and by the L14 re-proof before every launch |
| generated settings | `arms.PINNED_SETTINGS_SHA256 = 235a1e1fdf5a2ef41f86d0c27507d5f468b50022985033b0fb6c60baadad59ff`; per-arm redacted `models.json` digests `arms.ARM_REDACTED_DIGEST` |
| runs | at most **nine** admitted, strictly sequential, one per ordinal |
| AIDO prompt writes | at most **one** per admitted run (L18) — bounds AIDO's semantic writes, not Pi's own provider requests |
| AIDO route check | at most **one** AIDO-issued, authenticated, non-inference `GET /models` per admitted run (L7), `trust_env=False`, no redirects, no retry, no fallback |
| retry policy | **AIDO:** no semantic retry, replay, replacement, reorder, repetition or re-invocation. **Pi:** the frozen generated `settings.json` retry block retained unchanged — `retry.enabled = true`, `retry.maxRetries = 3`, `retry.baseDelayMs = 2000`, `retry.provider.maxRetries = 0`. Pi may retry internally while serving the one AIDO prompt; AIDO neither suppresses nor counts those as AIDO retries and observes them only through the frozen `auto_retry_events` runtime claim |
| token policy | **no** AIDO `maxTokens` at any level; Pi's own default applies and is never an AIDO-requested cap |
| run bounds | frozen `ar2.supervisor.RunBounds`: start-up 60 s, turn 900 s, shutdown 20 s, stdout 32 MiB, stderr 1 MiB, 200 000 events, direct-child reap grace 5 s — bounds on AIDO's waits, not on backend inference |
| L16 | frozen FU2 probe: one `get_state`, four bounded runtime claims (§14.4) |
| halt | frozen L30; six `HALT_REASON_CODES` and their precedence; stop, no resume |
| output authority | exactly `RESULTS_ROOT\CFG1-S1-A4\`, `RESULTS_ROOT` proven by G6 to derive from the audited checkout and re-proven by the code at establishment and every consumption boundary |
| evidence | `S1_<nn>_<arm>.json` as `pi-harness-cfg1-run.v2` (or `pi-harness-cfg1-refusal.v2` in its place), `S1_stage_closure.json` as `pi-harness-cfg1-stage-closure.v1`; each ≤ 65 536 bytes; created by exclusive create |
| claim scope | the fixed `CLAIM_SCOPE` literal; `qualification_credit = false`, no verdict, ranking, selection, hard-bar input or real-workspace authority |

### 11.1 The single covered invocation surface

The **only** covered surface is the §9.1 launcher, bound by `LAUNCHER_SHA256`,
run as §7.2 specifies. After G0–G8 pass it performs exactly:

```text
authority = stage_output.establish_stage_output_authority(
    stage_id="S1", stage_execution_id="CFG1-S1-A4")
stage_runner.run_cfg1_stage(authority)
```

each exactly once, in that order, in that one process. Nothing else is covered:
not `_run_cfg1_stage_with_injected_executor`, not any test double, not any other
launcher or entry point (`run_ar2.py`, `run_i2b_live.py`,
`run_semantic_sweep_live.py`, the AIDO CLI), not an interactive interpreter, not
a second call to either function, and not `stage_id="S2"`.

### 11.2 Mandatory pre-consumption order

```text
A0–A13   operator admission: authorization / Git / workspace / evidence /
         launch directory / temp / Git-resolution sanity / names
   ↓
G0–G6    source-origin / import-provenance gate (launcher process)
   ↓
G7       pre_consumption_pi_identity_gate(os.environ)
         → proceed ONLY IF it returned exactly the str "PI_IDENTITY_PROVEN"
   ↓
G8       post-gate re-audit
   ↓
establish_stage_output_authority(stage_id="S1",
                                 stage_execution_id="CFG1-S1-A4")   ← consumption
   ↓
run_cfg1_stage(authority)
```

---

## 12. Credential and route boundary

### 12.1 Names

The only live credential/endpoint inputs are the frozen names, read **only** by
the harness at its frozen **L4** boundary (`read_connection`), after L1–L3:

```text
AIDO_LITELLM_BASE_URL
PI_QUALIFICATION_B300_ROUTE_KEY
```

The launcher and the Pi gate read neither. CFG1 reads no `AIDO_LITELLM_API_KEY`
or other alias, fallback, `.env`, config file, CLI flag, or prompt; this
document adds none and does not modify CFG1 to accept a generic name. No
alternate route, provider, backend, model or fallback exists or is authorized.

### 12.2 Session-scoped operator mapping (preserved from A2 §4 / A3 §8.2)

When `PI_QUALIFICATION_B300_ROUTE_KEY` is MISSING, the operator may populate it
from the existing operator-controlled generic source, outside the harness, in
the one CMD launcher session only — and only when the source is PRESENT,
because an undefined CMD reference leaves the literal reference text in place,
which would pass L4 and fail only at L7, after consumption:

```text
if defined AIDO_LITELLM_API_KEY set "PI_QUALIFICATION_B300_ROUTE_KEY=%AIDO_LITELLM_API_KEY%"
```

- CMD session only. No `setx`, no user/system environment change, no script,
  batch file, `.env`, profile, config file, or repository write — no
  persistence and no alternate credential source.
- The endpoint `AIDO_LITELLM_BASE_URL` is used as already present; this document
  sets or selects no endpoint.
- The launcher inherits this session's environment; `-I` does not remove these
  names.
- After the launcher exits, the operator closes this CMD session so the
  session-only carrier ends with it.

### 12.3 Presence checks

Name-only, **PRESENT/MISSING** only, e.g.
`if defined PI_QUALIFICATION_B300_ROUTE_KEY (echo PRESENT) else (echo MISSING)`.
No value is printed, echoed, logged, copied, written, hashed, measured
(length), or partially rendered, and no value-printing enumeration (bare
`set`, `set <prefix>`) is used.

### 12.4 Where the credential and endpoint exist, and residuals

| Material | Where AIDO puts it | Closure |
|---|---|---|
| credential value | launcher process memory from L4; the L12 Pi child environment (explicit positive allowlist with the one carrier inserted); the CMD session | never written to disk by AIDO: the generated `models.json` carries only the reference `$PI_QUALIFICATION_B300_ROUTE_KEY` |
| endpoint value | process memory from L4; the generated `models.json` (L9), beside the repository child in the run's own temp root | L24 content scrub through the retained handle of that exact object (AMEND2), then L27 identity-proven root removal |
| broker token / pipe name / capability id | process memory; the generated `ar2_config.ts` (L11) | L24 content scrub through the retained handle, then L27 |

- The generic name is not on the Pi child allowlist and is not forwarded.
  Forbidden-fragment names are re-audited by name at L12.
- No credential name or value has a durable-evidence field; records are scrubbed
  against the run's `ArtifactSafetyContext`. Redaction and scrubbing are a
  backstop; nothing here claims any artifact is provably secret-free.
- The same-user Pi child and its descendants can, by ordinary OS means, read the
  parent's memory, environment block and user files. AIDO gives them no secret
  through any channel it controls beyond the one carrier; nothing claims they
  cannot obtain more.
- The route may be plain `http` under the frozen L5 rule; nothing here claims
  TLS, privacy, or company approval of the transport.

---

## 13. Consumption semantics

`CFG1-S1-A4` is **consumed by the first call** to:

```text
establish_stage_output_authority(stage_id="S1", stage_execution_id="CFG1-S1-A4")
```

whatever happens afterwards — an authority refusal (including a console-only
§16.3.7 hard stop that leaves no artifact), an L1–L18 refusal, a credential or
route refusal, a launch failure, an L16 refusal, a halt, an evidence failure,
a closure failure, a process crash, an operator interrupt, or completion — and
whether or not any prompt is written, and whether or not any durable trace
remains (§4.2 residual).

- A failure **before** that call — any §10 admission failure or any G0–G8
  refusal — does not consume A4.
- A failure **at or after** that call consumes A4.
- No resume, repair, replay, re-run of a later ordinal, or second invocation is
  authorized. A later attempt requires a fresh diagnosis, a new authorization
  and a new identifier.

---

## 14. Failure, closure and evidence semantics (frozen; recognized, not redesigned)

### 14.1 Per ordinal

1. **L0** re-proves the authority and requires the ordinal's output path absent
   (else `OUTPUT_NAMESPACE_PREOCCUPIED` hard stop).
2. **L1** runs P from scratch (`prove_pi_identity`, same function object as the
   gate) and validates its exact result shape before committing
   `pi_seam_digests_match` / `pi_identity_failure_code`; then resolves Git
   (OC-7). No process.
3. **L2** mints the disposable workspace under the user temp directory (write-ahead
   W before the port) — first process: fixture Git. **L3** runs the frozen
   Python fixture verification child, before any credential exists; OC-5 exact
   projection (`type(return_code) is int`, `passed is False`).
4. **L4** reads the two names; **L5** secret context; **L6** compat detection;
   **L7** one route check — before any live resource.
5. **L8–L13** capability, endpoint-bearing config (L9, scrub fact written
   `false` first), broker, token-bearing extension (L11, same), child
   environment, broker pipe.
6. **L14**: construct the supervisor in memory; then the complete re-proof (20
   seams → package-root identity → `node.exe` identity); only on exact `True`,
   `launch()` — **the first Node/Pi/JavaScript execution** of the run. `Popen`
   uses the absolute `node.exe` and `cli.js` from the static identity object,
   `shell=False`.
7. **L15** H1; **L16** H2 and the manipulation check; **L17** baseline;
   **L18** at most one prompt write; **L19** wait; **L20** projection.
8. **Closure L21→L27** in fixed order, each obligation given exactly one
   opportunity, skipped only by its own applicability predicate, with
   step-local containment (OC-4 I-1…I-10). `compute_lifecycle_closure_v2`
   finalizes `lifecycle_all_closed`.
9. **L29** emits one v2 record (or a v2 refusal in its place); **L30** decides
   continue / halt / complete by the frozen admission conditions and precedence.

### 14.2 Named failure cases

| Case | Frozen behaviour | Consumed |
|---|---|---|
| any §10 / G0–G8 refusal | exit 2; nothing established; nothing written | no |
| establishment refuses (e.g. `EXECUTION_DIRECTORY_EXISTS`, `RESULTS_ROOT_*`) | exit 3, closed reason printed; nothing written under `RESULTS_ROOT\CFG1-S1-A4` unless the directory was already created | **yes** |
| L1 refusal (P failure or Git resolution) | `OFFLINE_PREFLIGHT_FAILED` at L1 with the P code or `null`; no resource created; record; halt `PRE_DISPATCH_REFUSAL` if closure proven | yes |
| L3 refusal | `WORKSPACE_BASELINE_FAILED`; L26 skip semantics; L27 removes the registered root; reaped fact recorded exactly | yes |
| L14 launch failure | `RUNTIME_LAUNCH_FAILED`; every obligation for L9–L13 resources exercised (L23, L24, L27; L21 if a process exists); halt | yes |
| partial runtime creation | `runtime_created` true when a process object exists after `launch()`; L21 must observe direct-child exit and both reader EOFs, else `LIFECYCLE_CLOSURE_UNPROVEN` | yes |
| closure-step exception / malformed port value | contained step-locally; fact stays unproven; later steps still run; the run halts `LIFECYCLE_CLOSURE_UNPROVEN` (or a higher-precedence code); `RUN_EXECUTOR_RAISED` only for out-of-domain events | yes |
| surviving run-scoped registry entry | stage never admits the next ordinal (`RUN_SCOPED_REGISTRY_NOT_EMPTY` or a higher-precedence code) | yes |
| evidence emission failure / collision | frozen writer phases; no fallback after final-path create; halt codes by precedence; console code | yes |
| exception out of `run_cfg1_stage` | exit 4; closed class name and reason code only | yes |
| operator interrupt / process death | out of OC-4's domain: resources may remain (live process, broker thread, unscrubbed endpoint/token file, orphan temp tree) and no record may exist | yes |

### 14.3 Evidence rules

- Durable evidence is written only under `RESULTS_ROOT\CFG1-S1-A4\`, created
  once by exclusive create; nothing else under `RESULTS_ROOT` is touched.
- No raw secret, endpoint, host, URL, reasoning subtree, exception text, path
  outside the fixture vocabulary, or unrestricted runtime response enters
  evidence.
- Teardown and cleanup failures remain visible and **cannot produce a pass**.
- Partial A4 artifacts are never deleted, rewritten, completed, normalized or
  repaired. A4 artifacts are not committed by this document.
- **No evidence artifact authorizes any later action**, including any S1
  outcome the frozen design would treat as input to a Stage-2 decision.

### 14.4 AIDO-observed facts versus runtime/model claims

| AIDO-observed (by AIDO's own handle or read) | Runtime / model / route claims (recorded, never authority) |
|---|---|
| P's filesystem facts: resolution, identities, the 20 digests | the four L16 facts (H2 bool; reasoning, compat shape, thinking level) — correlation makes them attributable to one response, not true |
| stage-output provenance; workspace mint/removal by identity; issuance registries; retained-handle scrubs | `runtime_reported_*` tool-activity counts, stop reasons, `auto_retry_events`, extension errors |
| direct child exit status and both reader EOFs (L21) | anything about backend inference, GPU work, descendants, or what Pi actually sent on the wire |
| Git observations of the fixture repository; verification child return code / counts | H1 command list content; `/models` listing content (the route's claim that the model is served) |
| AIDO's own prompt-write count and dispatch state | the model's output and edits (observed only through Git and verification) |

No runtime or model claim is authority for anything.

---

## 15. Authority-bearing objects and transitions — adversarial analysis over current source

| Object / resource | Created by | Mutated by | Provenance proof | Bypass by a supported caller? | Disagreement / validation at consumption | Cleanup targets only own? |
|---|---|---|---|---|---|---|
| A4 authorization | post-commit record (§3.4) | nobody | P1–P7; A1/A4 | no: HEAD pinned; no equivalence class | candidate vs committed bytes → P3/P4/A4 | n/a |
| launcher process state | §9.1 text | the launcher only | `LAUNCHER_SHA256` (A10); G0 | a different launcher is outside §11.1 | G0–G8 | writes nothing pre-consumption |
| imported lineage | G3 explicit binding + G4 | nobody (same-process tampering out of scope) | G3/G5/G8 origin audit; §7.5; A2/A3/A9 | a foreign copy, `PYTHONPATH`, cwd, `.pth`, stale `.pyc`, junction: all refused pre-consumption (§16) | G5/G8 run over **every** loaded module | n/a |
| Pi gate result | `pre_consumption_pi_identity_gate` | nobody | G6 identity checks; same `prove_pi_identity` | skipping it wastes A4 only; L1/L14 carry the security claims | exact `str` equality; no object flows to L1 | n/a |
| `PiProofResult` / `Cfg1PiIdentity` | P only (`_P_ONLY` sentinel) | immutable (`__setattr__`/`__reduce__` refuse) | L1 `require_pi_proof_result_shape`; L14 re-proof | `run_cfg1_stage` has no identity parameter; forged objects cannot enter L1 | L1 exact shape; L14 re-proof against the filesystem | n/a |
| `CFG1StageOutputAuthority` | `establish_stage_output_authority` (mint registry) | frozen; registry re-check catches `object.__setattr__` | Level A/B root proof; exclusive create; re-lstat | `__post_init__` refuses unregistered/mismatched mints | `verify_stage_output_authority` at L0, every writer, sealing | retired on every exit path; never deletes a directory |
| genuine run executor | `bind_genuine_cfg1_run_executor` inside `run_cfg1_stage` | nobody | token → exact callable identity, re-checked per `invoke` | injected executors refused against the genuine package root | per-invoke identity re-check | n/a |
| run workspace (temp tree) | L2 mint registry | claim is single-use per `run_id` | registered root file identity | ownership is not a port | L3/L8/L25/L26/L27 re-verify; L8 requires claimed-by this run | L27 removes only the registered root after identity re-proof; unregistered orphans never deleted |
| generated config / extension issuance | L9 / L11 bound writer code objects | nobody | issuance registry bound to workspace; pins | only the bound code object may open an interval | `verify_*_issuance` at L12/L14/L15/L24 | L24 scrubs exact objects via retained handles, removes no name |
| broker | L10 own instance | L13 start; L23 shutdown | adapter over the run's own server | — | L22/L23 exact-type reads | shuts down only its own instance |
| Pi runtime | L14 `Popen` of the identity's absolute paths | L21 teardown | re-proof immediately before `launch()` | no pre-L14 execution port exists | H1/H2 correlation to this run's supervisor | L21 acts on its own handle only; never by PID or name; descendants not tracked |
| stage decision / closure | nested sealing in `run_cfg1_stage` only | nobody | seal-history + decision registry | no reachable name | frozen validator | n/a |
| credential / endpoint material | L4 read; L9/L11/L12 placements | L24 scrub | §12.4 | the launcher and gate never read it | L5 validation; L12 by-name audit | §12.4; residual on process death |

Python truthiness and malformed values: exact-type checks govern every
authority- and closure-bearing fact (FU15, OC-4 I-4, OC-5); the launcher itself
decides only by `type(...) is` and exact equality. Known dispatch-phase items
recorded by OC-4 §15 as backlog (B-1, B-3, B-6) remain contained by the
dispatch catch-all and fail closed; A4 does not reopen them.

Raw diagnostics: every step reduces exceptions to closed codes (§21.1); no
exception text crosses a step; the launcher prints only pattern-filtered codes.
An uncaught `BaseException` (e.g. an operator interrupt) prints a standard
traceback with local file paths and no value CFG1 holds; a test-double
finalizer's unraisable hook output is the OC-4 R-3 residual.

---

## 16. Adversarial scenarios, tested against this text

| # | Scenario | Result |
|---|---|---|
| 1 | stale or foreign Python imports (another checkout, installed copy, `PYTHONPATH`, cwd package, editable `.pth`) | never consulted for the four packages (G3 binds exact files); `-I` drops `PYTHON*`, cwd and script dir; `-S` drops `.pth`; G2 refuses any non-base initial entry; G5/G8 refuse any foreign origin. Pre-consumption |
| 2 | dirty tracked source | A2/A3 refuse. Pre-consumption |
| 3 | untracked import shadow (`broker.pyd`, sourceless `broker.pyc`, `broker/__init__.py`, `src/sitecustomize.py`) | A9 refuses; `.pyc` never consulted (empty prefix); `sitecustomize` never imported (`-S`) and `<ROOT>\src` never on `sys.path`. Pre-consumption |
| 4 | reparse / junction source redirect at any depth, including Git-invisible ones | §7.5 walk refuses `G2_REPARSE_SOURCE_TREE` before G3, on the attribute alone, without following |
| 5 | A4 id reuse | A0/A6 before; `EXECUTION_DIRECTORY_EXISTS` at runtime; §4.2 residual for trace-less failures |
| 6 | pre-existing `RESULTS_ROOT\CFG1-S1-A4` | A6 refuses; if created between A6 and launch, establishment refuses (consumed — fail closed); its content is never read or merged |
| 7 | A3 artifacts mistaken for A4 authority | nothing reads them as authority; A4 is bound only by §3.4; the A3 launcher is not a covered surface |
| 8 | candidate bytes ≠ committed bytes | P3/P4/P5 refuse acceptance; A4 re-checks the blob at admission |
| 9 | HEAD differs by a later docs-only commit | A1 refuses; no equivalence class |
| 10 | Pi changed between the operator's earlier proof and A4 | irrelevant as input: G7 re-runs P; a change fails there, pre-consumption |
| 11 | Pi changed between G7 and L1 | L1 re-proves from scratch → L1 refusal, consumed (waste), no credential read, no Pi code run |
| 12 | Pi changed between L1 and L14 (or between ordinals) | L14 re-proof fails → `RUNTIME_LAUNCH_FAILED` with full closure, consumed; each ordinal's L1 and L14 re-prove again |
| 13 | malformed gate return | exact `str` equality only; anything else refuses `G7_*`, not consumed |
| 14 | failure before consumption | exit 2; nothing written; re-admission rules of §10 |
| 15 | failure during establishment | consumed; exit 3; closed reason printed; nothing else runs |
| 16 | L1 / L3 / L14 refusal; partial runtime creation; closure-step exceptions | §14.2 |
| 17 | credential material surviving cleanup | §12.4; on in-domain failures the scrub/removal facts are truthfully unproven and the stage halts; on process death material may remain in the temp root (A11 keeps it outside the checkout) |
| 18 | a launcher line invoking Node/Pi before L14 | the launcher contains no process-creation surface (§9.2); P has no process leaf (AMEND1 Test AA); L2–L13 start only Git and the Python fixture verification child |
| 19 | a later bare-name `node`, `pi`, or `pi.cmd` resolution regaining ambient `PATH` authority | no CFG1 code path resolves `node`/`pi` by name: CFG1 imports only `build_pi_argv` from `ar2.launch`, and the `shutil.which("node"/"pi")` resolvers in `ar2.launch` and `qualification.i2b_live_adapters` are never called on the CFG1 path; P uses exact candidate names with no `PATHEXT`; L14 launches absolute paths with `shell=False`. The Pi child's `PATH` is narrowed to the proven Node directory, the resolved Git directory and the system directories. Git itself is resolved by name over the ambient `PATH` at L1 (OC-7) — not Node/Pi, sanity-checked by A12 |
| 20 | concurrent filesystem mutation / TOCTOU | narrowed (A0 attestation, pre-consumption loading of the whole closure, L1/L14 re-proofs, exclusive create, identity-based cleanup), not closed — §17 |
| 21 | cwd planted `git.exe` | the cwd is the two-entry launch directory (G0, A13); even otherwise the frozen containment check refuses a cwd Git |
| 22 | temp directory inside the checkout | A11 refuses; otherwise endpoint/token-bearing files would transiently exist inside `<ROOT>` |
| 23 | same-process replacement of the executor or leaves | only audited lineage and the reviewed launcher run before consumption; G6 checks function identity; beyond that, same-process tampering is out of the frozen threat model |

---

## 17. Residuals (stated, not closed)

- **No supply-chain attestation.** The gate proves *where* stdlib and
  third-party modules load from, not their bytes. The base interpreter, the venv
  redirector, site-packages (`httpx`, `pydantic`, their dependencies), Git, and
  `node.exe` bytes are not attested; `node.exe` is identity-pinned (volume
  serial + file id) between P1 and L14, not digest-pinned.
- **OC-2.** The 20-seam proof does not prove which code Pi loads at run time;
  unpinned Pi/Node code runs from L14 with the credential-carrying environment.
- **Launchability is learned only at L14/L15** (AMEND1 §13): a broken Node/Pi
  consumes A4 after the credential read and one route check, with full closure.
- **Check→use slivers.** From each item's read in the L14 re-proof to `Popen`;
  from A0–A13 to the launcher; from §7.5 and G5 to consumption and to any
  post-consumption import the static analysis missed. The operator must not run
  concurrent writers. Nothing here is an OS sandbox.
- **Above `<ROOT>`**: non-link reparse types on `<ROOT>` or its ancestors are
  outside the §7.5 walk.
- **Venv content** and the frozen **verification children** (L3, L26) start with
  ordinary site processing (editable `.pth`, possible site-packages
  `sitecustomize`) and the allowlisted ambient `PATH`; L26 executes fixture code
  the model may have edited. Controlled invocation, not sandboxed execution.
- **Git (OC-7)** is resolved by name over the ambient `PATH` (cwd-first) at L1
  and again for each `observe_repository` call, and runs with the frozen fixture
  environment (`GIT_CONFIG_NOSYSTEM=1`, no profile variables) or the production
  adapter's fixed `-c` flags. Any process Git itself might start from
  configuration AIDO does not control is not observed.
- **Descendants, abandoned readers, backend inference and GPU lifetime** are not
  bounded or observed; a closed runtime means only the direct child's exit and
  both reader EOFs. No cancellation, termination or backend stop is claimed.
- **Out-of-domain events** (OC-4 §4.3): operator interrupt, process/OS crash,
  resource exhaustion, hangs — resources may remain and no record may exist.
- **Trace-less consumption** (§4.2).
- **OS-level injection** into `cmd.exe` or the interpreter (AutoRun, IFEO,
  AppInit, security products) is outside AIDO's observation.
- **Route transport** may be plaintext under the frozen L5 rule.

---

## 18. Explicitly NOT authorized

1. Anything before the §3.4 record exists; any HEAD but `<A4_AUTH_COMMIT>`.
2. Stage 2, arm `H`, or `CFG1-LIVE-S2` — **NO-GO**.
3. Q1/Q2 qualification authority, any qualification credit, verdict, ranking,
   selection, or hard-bar input — **NO-GO**.
4. Real-workspace authority of any kind — **NO-GO**.
5. AR2 live execution, or any widening of AR2 live authority — unchanged,
   **NO-GO** while OC-6 is unresolved. CFG1's composition of AR2 modules inside
   A4 is not AR2 live execution.
6. `DX1` (NO-GO), `M4` (HOLD / NO-GO), Candidate C/D live qualification, or any
   other future identifier; nothing is reserved.
7. Any execution, retry, resume, reuse, repair or conversion under
   `CFG1-S1-A1`, `-A2` or `-A3`.
8. Any AIDO retry, replay, replacement, reorder or repetition of an A4 run or
   prompt; any resumption after halt; any second A4 invocation.
9. Prompt, fixture, task, schedule, arm, model, provider, route, endpoint or
   settings mutation; any fallback.
10. Any change to production code, tests, frozen designs and amendments, the
    A1/A2/A3 authorizations, `CLAUDE.md`, roadmap/policy documents, or
    historical evidence.
11. Evidence repair of any kind; committing A4 artifacts.
12. Branch, commit, push, or PR automation by any agent.
13. Any authority derived from runtime claims, model output, or evidence
    content.
14. Any new capability: fixer, model-backed implementer, reviewer, agent loop,
    or GitHub write.
15. Any Node/Pi execution outside L14 of an admitted A4 run, including
    `--version`/`--help` probes, and any Harness-version adoption decision.

---

## Status

```text
CFG1 DESIGN                          ACCEPTED / FROZEN
CFG1-L16-FU2 R2 + ERR1               ACCEPTED / FROZEN
FU1 R6 + AMEND1 + Y6 AMEND2          ACCEPTED / FROZEN
OC-3                                 CLOSED BY PROBE REMOVAL
OC-4                                 CLOSED / FROZEN
OC-5                                 CLOSED / FROZEN
P1 TOPOLOGY CORRECTION               ACCEPTED / FROZEN (24a2c50…)
PRE-A4 STATIC IDENTITY/SEAM GATE     PI_IDENTITY_PROVEN (operator-reported; historical, not an input)
CFG1-S1-A1 / A2 / A3                 CONSUMED / HISTORICAL ONLY
CFG1-S1-A4-AUTH                      CANDIDATE R1 / PENDING CONTENT + POST-COMMIT REVIEW
CFG1-S1-A4                           NOT AUTHORIZED
HARNESS VERSION                      0.85.1 historical profile for this run only; no permanent policy
CFG1-LIVE-S2                         NO-GO
Q1 / Q2 QUALIFICATION AUTHORITY      NO-GO
REAL-WORKSPACE AUTHORITY             NO-GO
AR2 LIVE                             NO-GO (OC-6)
DX1                                  NO-GO
M4                                   HOLD / NO-GO
```
