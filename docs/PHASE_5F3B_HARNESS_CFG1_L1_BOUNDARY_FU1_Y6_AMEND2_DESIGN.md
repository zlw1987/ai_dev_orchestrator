# Phase 5F3B-HARNESS-CFG1-L1-BOUNDARY-FU1-Y6-AMEND2 — Handle-Bound Content Scrub Replaces the Link-Count Proof (Design Amendment)

```text
5F3B-HARNESS-CFG1-L1-BOUNDARY-FU1-Y6-AMEND2-DESIGN   CANDIDATE — PENDING REVIEW
AMENDS (does not edit) the FROZEN effective design:
  (1) 5F3B-HARNESS-CFG1-L1-BOUNDARY-FU1-DESIGN-R6
      docs/PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md
      SHA-256  f9287e8929fb0093f8e99a67b8a665387a249bf27ad5c414a465c0c067058bd0
      git blob c5d2f86ecbe6281afec5737b5d3592d4fd49d6ff
  (2) 5F3B-HARNESS-CFG1-L1-BOUNDARY-FU1-OC3-AMEND1
      docs/PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_OC3_AMEND1_DESIGN.md
      commit   e1910c9e4c9846686604d8607d67ca4c9d554ec8
      SHA-256  bd8569e460e5e2ffccb33d63f3d70e41ea3007246207a43ee27a754ba055c14e
      git blob 9b20c4631102ef3637005c4fb0d326524a7fb220
  and, narrowly and by name (§4), two clauses of the frozen CFG1 design
      docs/PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md
      SHA-256  011d540334fc96915b8aba8828f5caa435588eedb2a1877cd1bfc300393d5355
      git blob 7e319aeaef6573bc482204eac70e291e31e21495
  (all identities re-verified by this turn: sha256sum + git hash-object)
REPOSITORY ADMISSION OBSERVED: HEAD e1910c9e4c9846686604d8607d67ca4c9d554ec8
ACCEPTED FINDING: TEST Y-6 FAILS ON THE SUPPORTED HOST — AM-12's CONTINUITY ASSUMPTION IS FALSE
REVIEWER DIRECTION FROZEN HERE: HANDLE-BOUND CONTENT SCRUB OF THE EXACT AIDO-CREATED OBJECT
OS-TEMP WIN32 DERIVATION: 35/35 REQUIRED CHECKS PASSED (§3) — NO STOP CONDITION
EFFECTIVE DESIGN = R6 + AMEND1 + THIS AMENDMENT (AMD2-1 … AMD2-8)
GRANTS NOTHING. NO IMPLEMENTATION AUTHORITY.
```

> **THIS DOCUMENT IS A DESIGN CANDIDATE. IT GRANTS NOTHING.**
>
> - It does not edit, re-serialize, or re-hash-into-a-new-meaning the frozen R6
>   file, the frozen AMEND1 file, or the frozen CFG1 design. Each stays exactly
>   as frozen; this file is read **together with** them.
> - It authorizes no implementation, no test change, no live run, no A4, no
>   Stage 2, and reserves no identifier. `CFG1-S1-A3` remains CONSUMED and
>   historical-only. Pi remains pinned to **0.85.1**.
> - The current FU1 working tree (R6 + AMEND1 implementation, uncommitted,
>   stopped at Test Y-6) is **not accepted**, is **not edited** by this phase,
>   and remains uncommitted. §18 only *identifies* the corrective areas.
>
> **Disclosure of what the turn that wrote this file did (exact).** It read the
> frozen R6 file, the frozen AMEND1 file and the frozen CFG1 design, and read
> (without modifying) source under `experiments/pi_harness_cfg1/` — in
> particular `win_config_authority.py`, `cfg1_pi_config.py`,
> `cfg1_extension.py`, `config_issuance.py`, `extension_issuance.py`,
> `run_executor.py`, `lifecycle.py`, `run_workspace.py`, `stage_runner.py` and
> `tests/test_cfg1_fu1_sensitive_material.py` — with `sed`/`grep`/`Read`, and
> ran `git status`/`git diff --stat`/`git hash-object`/`sha256sum`. It then ran
> **two OS-temp scratch scripts** (§3), `exp_amend2.py` and
> `exp_amend2_share.py`, with the system CPython 3.14.7 (not the repository
> venv), using **pure `ctypes` calls into `kernel32`**; they import no module
> of this repository, launch no process, open no socket, read no credential or
> endpoint value, and create files only beneath the session scratch directory
> under the OS temp directory (`%TEMP%\claude\…\scratchpad\`), all of which each
> script deletes before exiting (`cleanup_removed True` in both runs). No Node,
> Pi, JavaScript, model, network or credential operation occurred. No file of
> this repository other than this one was created or modified, and nothing was
> committed or pushed.

**Citation convention.** `R6 §n` / `R6 line n` = the frozen R6 blob;
`AMEND1 §n` / `AMEND1 line n` = the frozen AMEND1 blob; `CFG1 §n` /
`CFG1 line n` = the frozen CFG1 design blob (all line numbers are stable
because each blob is frozen). A bare `§n` is a section of this amendment.
Handle names used throughout: **H_c** — the `CREATE_NEW`, share-0 creating
handle a writer holds; **H_r** — the retained, zero-access, issuance-owned
handle introduced here; **H_s** — a scrub handle reopened from H_r at
retirement.

---

## 0. Reading rule and precedence

1. The effective FU1 design is **R6 + AMEND1 + this amendment**. Where this
   amendment names a clause as superseded (§4), this amendment governs; every
   other R6/AMEND1 clause is preserved exactly as frozen (§5).
2. Where this amendment amends a **frozen CFG1** clause (CFG1 §16.2's L24 row;
   CFG1 §17's generated-config resource row; the precise-child bullet of CFG1
   §37.3.2a), it names the clause and line, as R6 §3 and AMEND1 §3 do.
3. R6's historical self-review text (R6 §18.0 constructions 1–6, R6
   §18.0a/§18.0b/§18.1/§18.2) that describes the L24 *link-count* proof, its
   continuity, or the Y-6 stop rule is **superseded as normative text** and
   remains only as the record of why R6 was shaped as it was.
4. Nothing here reopens static P, AMEND1's AMD-1…AMD-8, the v2 identity
   semantics (R-S1…R-S6, `pi_identity_failure_code`), L14/AM-8/AMD-6,
   AM-11/step 9a, AM-14's pinned inputs, R-WINDOW / R-WINDOW-E, D-1/D-3, or
   OC-2…OC-11.
5. §21 records every contradiction the drafting found and how each is
   resolved. None required stopping.

---

## 1. The accepted Y-6 finding (exact)

R6 AM-12 (R6 line 239) and R6 §9.2c-C (R6 lines 1314–1336) made the L24 positive
proof depend on one OS claim, which R6 itself marked as a claim Test Y-6 had to
demonstrate (R6 lines 1328–1333):

> share-0 denies every other open of the object, and creating a hard link or
> renaming the object requires such an open.

The FU1 implementation ran Test Y-6 on the supported Windows 11 / NTFS host and
it **failed**. Accepted, exactly:

1. `CreateHardLinkW` **succeeds** against a file while a share-0
   `GENERIC_READ | DELETE` handle to it is held (the R6 L24 handle), and equally
   while the writer's share-0 `GENERIC_READ | GENERIC_WRITE | DELETE`
   `CREATE_NEW` handle is held. Rename is refused (`ERROR_SHARING_VIOLATION`).
2. Therefore "no alias can be added while the handle is held" (AM-12 step 4) is
   **false**. An alias created between the link-count read and the disposition
   survives: after the delete disposition and the close, the issued pathname
   disappears while the same sensitive file object remains reachable through
   the other link, with its bytes.
3. This is a **design** defect, not an implementation defect. The frozen stop
   rule (R6 §9.2c-C "stops and returns to design", preserved by AMEND1 §4 and
   AMEND1 line 585) fired correctly; the implementation did not improvise.

This turn's OS-temp derivation independently **reproduced** the finding
(§3, rows `Y6.*`): hard-link creation succeeded (`winerror 0`) and rename was
refused (`winerror 32`) while the share-0 creating handle was held. The
observed behavior is consistent with hard-link creation opening its source
without data or delete access — access that share modes do not govern — but
this amendment relies only on the observed behavior, not on that explanation.

**What follows from the finding.** Any proof of the form "the file has exactly
one name, therefore deleting it removes the object" requires excluding alias
creation for an interval, and Windows exposes alias creation (by path, and
through handle-based link information classes) outside share-mode control. The
reviewer's direction (§2) is therefore not to repair namespace exclusion but to
stop depending on it.

---

## 2. Reviewer direction frozen here, and what it rules out

**Frozen.** The L24 sensitive-material proof is replaced by a **handle-bound
content scrub of the exact AIDO-created file object**. Every hard link names
the same file object and therefore the same default data stream, so truncating
that stream through a handle to the object makes **every** name of it —
whatever it is called, wherever it now lives, whenever it was created —
observe zero bytes (§3, P7). Hard links and renames become irrelevant to
confidentiality. Namespace removal remains a separate concern, owned by L27.

**Ruled out (not adopted, and not to be re-proposed as a repair):**

- proving the file has exactly one pathname; any use of `NumberOfLinks` as a
  security invariant or a decision input;
- the sequence *count == 1 → delete pending → count == 1 again* as a primary
  proof;
- chasing, enumerating, deleting or "fixing up" alias pathnames;
- pathname reopening as the authority bridge between writer and L24;
- `OpenFileById` / file-id lookup as the authority bridge (the retained-handle
  design was proven possible, §3, so this fallback is not reached);
- deleting any pathname as part of the positive scrub proof;
- any claim of forensic or secure erasure.

---

## 3. Mandatory Windows primitive derivation (OS temp)

### 3.1 Method

Two scripts in the session scratch directory (OS temp), system CPython 3.14.7,
pure `ctypes` into `kernel32` (`CreateFileW`, `ReOpenFile`, `CloseHandle`,
`GetFileInformationByHandleEx`, `SetFileInformationByHandle`,
`FlushFileBuffers`, `ReadFile`/`WriteFile`, `CreateHardLinkW`, `MoveFileExW`,
`DeleteFileW`, `GetHandleInformation`, `DuplicateHandle`,
`CreateFileMappingW`/`MapViewOfFile`, `GetVolumeInformationByHandleW`). The
layout mirrors CFG1's: an `owned_root\config\models.json` target and an
`outside_root\` sibling on the same NTFS volume. Sensitive bytes were a
synthetic 89-byte `.invalid` document. Every tree was deleted afterwards.

| artifact (scratch, not in the repository) | SHA-256 |
|---|---|
| `exp_amend2.py` (final run) | `e5d72b77cc70397b2ce50510ff51df96ad089f2cc9213d0ad77ea905449d07fc` |
| `exp_amend2_share.py` | `de268a0cc9bc4f70f702f5e2f4b5516a20b1f1f21f209fe2b2fc2a3c383ce659` |
| `exp_amend2_run.txt` (transcript) | `859e7f20587a7941e61ff04f48b1ced9b1738d01f59d637194fafdd3bea33774` |
| `exp_amend2_results.json` | `38a873c8449b7ea20e8770f033057bda0c68ed0172bc448d1b15a154dcee2fab` |
| `exp_amend2_share_results.json` | `8ec6db1acd341e3265f8af0c3226f37cde4c76401cf871af80439072cd40f930` |

### 3.2 Required properties (the reviewer's nine) — all PASS

| # | Property required | Observation | Result |
|---|---|---|---|
| 1 | CREATE_NEW with the current exclusive creating-handle semantics | `CreateFileW(GENERIC_READ\|GENERIC_WRITE\|DELETE, share 0, CREATE_NEW, FILE_FLAG_OPEN_REPARSE_POINT)` succeeded; volume filesystem `NTFS`; a data open of the name while held refused `32`; a second `CREATE_NEW` refused `80`; sensitive bytes written and read back through H_c | **PASS** |
| 2 | `ReOpenFile(H_c, 0, broad share, …)` succeeds while H_c is open | `ReOpenFile(H_c, 0, FILE_SHARE_READ\|WRITE\|DELETE, FILE_FLAG_OPEN_REPARSE_POINT)` succeeded; H_r is **not inheritable** (`HANDLE_FLAG_INHERIT` clear); H_r itself cannot read, write or truncate (`5` each) | **PASS** |
| 3 | Both handles report the same volume/file identity | `FILE_ID_INFO(H_r) == FILE_ID_INFO(H_c)`; also equal to `os.stat` `st_dev`/`st_ino` (W13 re-observed) | **PASS** |
| 4 | After H_c closes, an ordinary pathname read works while H_r is held | H_c closed (`CloseHandle` true); Python `open(…,"rb")` read the bytes; a `GENERIC_READ`, **share-READ-only** reader opened; even an exclusive share-0 read/write open succeeded (H_r takes no part in sharing) | **PASS** |
| 5 | Rename / hard-link creation do not invalidate H_r's identity | links created inside and outside the root after issuance; the original renamed **out of the root**; a foreign file planted at the original name; `FILE_ID_INFO(H_r)` unchanged; every alias (pre-issuance, post-issuance in/out, renamed) resolves to the same identity; the foreign file does not | **PASS** |
| 6 | After runtime handles close, `ReOpenFile(H_r, write, …)` opens the SAME object despite rename and aliases | `ReOpenFile(H_r, GENERIC_WRITE\|FILE_READ_ATTRIBUTES, share 0, FILE_FLAG_OPEN_REPARSE_POINT)` succeeded; `FILE_ID_INFO(H_s) ==` issued identity | **PASS** |
| 7 | Truncate EOF=0 + flush ⇒ original link (if any) and every alias observe zero / no sensitive contents | `SetFileInformationByHandle(FileEndOfFileInfo, 0)` true; `FlushFileBuffers` true; every name — renamed original (outside root), pre-issuance alias, post-issuance aliases inside/outside, and an alias created **during** the scrub interval — reports size 0 and reads `b""`; the foreign same-name file is byte-identical to what was planted | **PASS** |
| 8 | `FILE_STANDARD_INFO.EndOfFile` from the exact scrub handle is 0 | `EndOfFile == 0` from H_s (`NumberOfLinks` was 5 at that moment — recorded, never used) | **PASS** |
| 9 | Each handle's release observable separately | `CloseHandle(H_s)` true while H_r stayed valid; then `CloseHandle(H_r)` true and `GetHandleInformation(H_r)` → `6` (`ERROR_INVALID_HANDLE`) | **PASS** |
| 10* | Writer failure: scrub through the still-held creating handle reaches an alias created while H_c was held | alias created during H_c (Y-6 behavior); truncate + flush through H_c; `EndOfFile == 0` from H_c; disposition + close; issued name gone, alias reads `b""` | **PASS** |

\* Row 10 derives the primitive behind the reviewer's §6 / test item 10; it was
run as a required check. **Total required checks: 35 / 35 PASS.**

### 3.3 Informational observations (not required; each informs a clause)

| key | observation | used in |
|---|---|---|
| `X1` | while the share-0 H_s is held, `GENERIC_READ` opens through **two different links** are refused (`32`, `32`); hard-link creation is still allowed and the new link reads `b""` after the scrub. A focused probe (`exp_amend2_share.py`) confirmed share-0 is enforced across links for both `CreateFileW` and `ReOpenFile` handles (`GENERIC_READ`/`GENERIC_WRITE` refused `32` via same name and other link; `FILE_READ_ATTRIBUTES` allowed) | §8 (why H_s is share-0) |
| `X2` | with a foreign `GENERIC_READ` handle (share all) open on an alias, `ReOpenFile(H_r, write, share 0)` is refused `32` | §12 (foreign data handle ⇒ `False`) |
| `X3` | after a foreign actor maps a view of an alias and closes its file handle, a share-0 reopen **succeeds** (share access is released at the last handle's cleanup; the section keeps only a reference) but truncation is refused `1224` (`ERROR_USER_MAPPED_FILE`) | §12 (mapped view ⇒ truncate failure ⇒ `False`) |
| `X4` | a foreign actor deletes the object's **only** name while H_r is held (allowed; `DeletePending 1`, `NumberOfLinks 0`); `ReOpenFile(H_r, write, share 0)` still succeeds and the truncate/flush/`EndOfFile == 0` scrub completes | §16 (unnamed object is still reached) |
| `X5` | the owned disposition after a creating-handle scrub removes only the issued name; the alias remains as a zero-length object | §9 |
| `X6` | original name deleted, alias remains: reopen from H_r reaches the object; scrub completes; alias reads `b""` | §16 |
| `X8` | an in-process `DuplicateHandle` of H_r refers to the same object and can itself be reopened for write; closing the duplicate leaves H_r valid | §19 (duplication analysis) |
| `Y6` | reproduction of the accepted finding (link created, rename refused) | §1 |

The first run's `X1` row printed `FAIL` only because the check read
`OSError.winerror` from Python's CRT-based `open()`, which carries `errno`,
not `winerror`; the rerun checks with `CreateFileW` directly. The `X3` row
prints `FAIL` because its *expectation* (a section blocks a share-0 reopen) was
wrong; the observed OS behavior is recorded above and the design relies on the
truncation refusal, not on the reopen refusal.

### 3.4 Primitive parameters, now frozen (the *what*)

| Handle | Obtained by | Desired access | Share mode | Flags | Required checks |
|---|---|---|---|---|---|
| **H_c** | `CreateFileW` — unchanged (FU15 step 6 / R6 E6) | `GENERIC_READ \| GENERIC_WRITE \| DELETE` | `0` | `CREATE_NEW`, `FILE_FLAG_OPEN_REPARSE_POINT` | unchanged |
| **H_r** | `ReOpenFile(H_c, …)` — **never** a pathname, **never** a file id | `0` | `FILE_SHARE_READ \| FILE_SHARE_WRITE \| FILE_SHARE_DELETE` | `FILE_FLAG_OPEN_REPARSE_POINT` | `FILE_ID_INFO(H_r) == FILE_ID_INFO(H_c)`, both read from handles; `HANDLE_FLAG_INHERIT` clear |
| **H_s** | `ReOpenFile(H_r, …)` — **never** a pathname | `GENERIC_WRITE \| FILE_READ_ATTRIBUTES` | `0` | `FILE_FLAG_OPEN_REPARSE_POINT` | `FILE_ID_INFO(H_s) ==` the issued identity; `HANDLE_FLAG_INHERIT` clear |

Scrub operations, on H_s at L24 or on H_c in a writer's failure path, in this
order: `SetFileInformationByHandle(FileEndOfFileInfo, EndOfFile = 0)`;
`FlushFileBuffers`; `GetFileInformationByHandleEx(FileStandardInfo)` whose
`EndOfFile` must be a type-exact `int` equal to `0` (a `bool` is not `0`).
`NumberOfLinks`, `DeletePending` and `AllocationSize` from the same structure
are **never decision inputs**.

*Why H_r has zero access.* A handle with no read, write, execute or delete
access takes no part in share-mode arbitration (§3.2 row 4: even an exclusive
open succeeds), so holding it cannot interfere with the runtime; and it can
neither read, write nor truncate (row 2), so it cannot leak or alter content
by itself. It is a pure, identity-proven reference to one object.

*Why H_s is share-0.* During truncate → flush → `EndOfFile` query, no other
handle with data access to the object exists or can be opened, through **any**
link (X1). The zero observation is therefore not interleaved with any other
reader or writer, and a lingering data handle (for example a surviving runtime
descendant, or a foreign reader) makes the reopen fail (X2) — `False`,
fail-closed — instead of silently racing it. Alias creation during the
interval remains possible and is harmless: the new name is the same object
(X1, P7).

*Why `FILE_FLAG_OPEN_REPARSE_POINT` on every reopen.* The reopen is relative to
an object AIDO already holds; the flag guarantees no reparse processing can
redirect it even if a same-user actor later attaches a reparse point to that
object. The identity check on every derived handle is the mechanical backstop.

### 3.5 What the derivation does not establish

It is one host, one volume, one Windows build (11, 10.0.26200) and NTFS only
(the platform CFG1 already requires). It establishes nothing about ReFS, FAT,
network redirectors, filter drivers that virtualize files, or future Windows
builds; the implementation phase's tests re-prove P1–P9 on the host they run
on, under `tmp_path`, and CFG1 continues to refuse off win32. It says nothing
about forensic recoverability (§6).

---

## 4. Clauses superseded (exact)

| Id | Supersedes | Narrow amendment |
|---|---|---|
| **AMD2-1** *(the positive L24 claim)* | R6 §3 **AM-12** in its entirety (R6 line 239); R6 §9.2c **G7** (R6 lines 1214–1219); R6 §9.2c-C in its entirety (R6 lines 1304–1366); R6 §4 diagram lines 275–278 (L24 as "exclusive interval … exactly one link … deletion-bearing handle CLOSED"); R6 §13's AM-12 allowed item (R6 lines 1693–1698); R6 §9.2a residual sentence "`identity_bound_unlink` verifies and disposes through one handle …" (R6 lines 1022–1023). **Frozen CFG1 §16.2 L24 row** (CFG1 line 2273: "verified unlink of … `models.json` … and … `ar2_config.ts` …, each after re-proving root authority and issuance"); **frozen CFG1 §17** generated-config row's cleanup cell (CFG1 line 4240: "L24 verified unlink of `models.json`"). | L24 no longer removes either file. It performs the **handle-bound content scrub** of §12 on the exact AIDO-created object, from the issuance-owned retained handle only, and its positive result means exactly §6's claim. No pathname is opened, deleted, or consulted by L24. Name removal is L27's (§13). The ordering "L24 before L26" (CFG1 G14, CFG1 line 5766) is **preserved**. |
| **AMD2-2** *(retained exact-object authority)* | R6 §3 **AM-9**'s mechanism clause (R6 line 236: "L24 removes `ar2_config.ts` only through that issuance's bound identity, by handle (`win_config_authority.identity_bound_unlink` …)"); R6 §9.2a **E10** (R6 lines 924–933) and step 10 of L9 (R6 §9.2b item 6, preserved in substance) as to *what issuance holds*. | Each **sensitive** issuance — the config issuance for `models.json`, the extension issuance for `ar2_config.ts` — additionally owns one private, retained, zero-access handle to the exact object, acquired from the creating handle by `ReOpenFile` before that handle is released (§7). Static extension children and `settings.json` get none. Everything else AM-9/E10/step 10 records is unchanged. |
| **AMD2-3** *(writer failure paths)* | R6 §3 **AM-13 item (ii)** (R6 line 240: "disposes `models.json` through its own creating handle, then closes that handle (G2)"); R6 §4 diagram lines 266–267; R6 §9.2c **G1**'s L24-side clause (R6 lines 1186–1187: "L24-side disposal acts only through a handle whose `os.stat(fd)` file id matched …"), **G2** (R6 lines 1188–1195), **G3** (R6 lines 1196–1204); R6 §9.2c-A's writer-local facts, release order, formula and table (R6 lines 1223–1269); R6 §9.2c-B's table (R6 lines 1294–1302); R6 §9.2a **E11** and the exception contract (R6 lines 934–965); R6 §9.2a executor-L11 item (3)'s meaning (R6 lines 972–976: "disposed through its own creating handle **and that handle then closed successfully**"); R6 §9.2b **item 5**'s "disposes … and computes … from BOTH results" (R6 lines 1116–1119). | "Not outstanding" requires a **content scrub** of the exact object through genuine handle authority **and** the successful release of every material handle (§9, §10, §15) — never a delete disposition. A disposition, where the writer genuinely owns one, is **namespace cleanup** only and is no longer an input to any bool. G3's "a failure first discovered during release cannot reach back" is replaced by the reclaim rule of §11: once H_r exists, it can. |
| **AMD2-4** *(L24 precondition)* | R6 §9.2a L24 paragraph (R6 lines 990–1011); R6 §9.2c-C's opening sentence (R6 lines 1306–1312: "re-verify the issuance against the workspace … → call `identity_bound_unlink`"); **frozen CFG1 §37.3.2a** precise-child bullet (CFG1 lines 6379–6389: "prove, at the moment of the operation, that the target remains contained and identity-matched") — **for the content scrub only**. | L24's authority is the genuine issuance registry entry bound to this run's workspace nonce (§12 step 1), and the target proof is **handle identity**, not pathname containment. L24 does **not** run `verify_config_issuance` / `verify_extension_issuance` (their pathname re-digests) as a scrub precondition, and does not re-prove the root against the filesystem as one: a namespace tamper can no longer redirect the scrub, and refusing to scrub because of one would leave sensitive content in place (§21 C-2). The **no-redirect-following** half of CFG1 §37.3.2a is preserved exactly: no reference is resolved, every reopen carries `FILE_FLAG_OPEN_REPARSE_POINT`, and nothing outside the root is *deleted*. L14/L15's `verify_*_issuance` consumption checks are **unchanged**. |
| **AMD2-5** *(durable meanings)* | R6 §10 row `extension_possibly_created — REMOVED; …` (R6 line 1550) as to how `extension_binding_scrub_verified` becomes `true`; R6 §10 row `generated_config_scrub_verified` (R6 line 1551) as to its v2 meaning. | §14. **No durable field is added, removed or renamed.** Only the v2 meaning of the two existing scrub facts is restated. No v2 artifact has ever been emitted (the FU1 implementation is unaccepted and nothing ran live), so no archived meaning changes; v1 is untouched. |
| **AMD2-6** *(tests)* | R6 §11 row **Y** in its entirety (R6 line 1599), and AMEND1 §16.3's preservation of **Y** "exactly as R6 §11" (AMEND1 lines 796–797); R6 §11 rows **Q**, **R**, **X** (R6 lines 1591, 1592, 1598) as to disposition/deletion expectations. | §17. Y-6's "alias creation and rename **fail** while the exclusive handle is held" assertion is **deleted**. |
| **AMD2-7** *(the Y-6 stop rule)* | R6 §9.2c-C's contingency (R6 lines 1328–1333); AMEND1 §4's preservation of "the Y-6 stop rule" (AMEND1 lines 199–201) and AMEND1 §11's table row (AMEND1 line 585). | The rule is **discharged**: it fired, and this amendment is the return to design it required. It is retired together with the assumption it guarded. The new design depends on **no** alias-exclusion property; §17 adds tests that exercise aliasing directly instead of forbidding it. |
| **AMD2-8** *(historical self-review)* | R6 §18.0 constructions 1–6 and its "Result and residuals" paragraph (R6 lines 1853–1944) as normative text. | Replaced by §19. Retained as design history only (§0 item 3). |

---

## 5. Clauses preserved (exact)

Preserved **unchanged**, by reference:

- **R6 AM-13** items (i), (iii), (iv): the write-ahead `False` before
  `write_config`; the executor's single exact-type/exact-bool rule; L27 never
  upgrading the fact. **R6 G4** (write-ahead, pessimistic), **G5** (L27's
  success never upgrades an individual scrub fact), **G6** (conservative
  reading: `True` only from an exact `False` on the exact genuine typed error).
- **R6 G1**'s governing rule and its writer-side clause (R6 lines 1182–1186):
  *a bool is evidence, never deletion authority; no pathname is ever deleted;
  no same-name foreign object is ever deleted (or, now, modified) as though
  AIDO created it; writer-side action goes only through the `CREATE_NEW`,
  share-0 handle.* AMD2-3 changes only what the writer does through that
  handle; its L24-side clause is superseded (AMD2-3 row), replaced by §12.
- **R6 AM-9 / AM-10** (CFG1-owned transactional extension writer; exactly two
  typed generator bindings; typed intervals; each issuance registry checks the
  kind), **AM-11** (step 9a), **AM-14** (pinned single read of the static
  sources and the template; golden vector).
- **R6 §9.2a E-1 … E9**, and E10's recorded identities and digests; L9 steps
  0–9a and step 10's registration contract (provenance first, parentage,
  child names, identities, read-back digests, the expected-digest binding of
  R6 §9.2b item 6) — every check that needs the creating handles still runs
  while they are held (§11 C-1).
- **L14/L15**: `verify_config_issuance` / `verify_extension_issuance` at their
  own consumption points, unchanged; they never touch the retained handle.
- **L26** requires L21 ∧ L23 ∧ L24 closed; any `False` L24 fact skips L26
  (`LIFECYCLE_UNPROVEN`). **L27**: whole-root namespace teardown after
  independent re-proof, unchanged (§13).
- The v2 closure predicate (`compute_lifecycle_closure_v2`) and its `"L24"`
  conjuncts; the stage-closure record; `_resolve_halt_reason_code`.
- The existing close-failure accounting (`_CLOSE_FAILURES`,
  `close_failure_count()`), extended with new kinds (§15), never weakened.
- Everything AMEND1 froze (static P, AMD-1 … AMD-8, R-S1 … R-S6, the
  pre-consumption gate reading `PATH` only, L14 as the first execution).
- R-WINDOW (FU15-D1) and R-WINDOW-E (R6), unchanged.

---

## 6. The scrub security claim (exact)

For the two sensitive CFG1 file objects — **L9 `models.json`** (endpoint-bearing)
and **L11 `ar2_config.ts`** (token-bearing) — the positive L24 claim is:

> **The exact AIDO-issued file object's sensitive default-stream contents are
> mechanically proven absent.**

Mechanically: through a handle descended by `ReOpenFile` from the creating
handle of that exact object, whose identity equals the issued identity, the
default data stream was set to `EndOfFile = 0`, flushed, and re-queried as
exactly `0` from the same handle, while no other data-access handle to the
object could exist; and every handle that had to be released was released
successfully (§15).

It does **not** mean, and no code, record, console line or document may say or
imply, that:

- every hard-link pathname of the object was deleted, or that the object has no
  name (after L24 it usually still has one or more, until L27 — and a name
  outside the owned root may persist indefinitely as a zero-length file);
- the bytes are forensically unrecoverable (truncation deallocates clusters but
  does not overwrite them; small NTFS files may be MFT-resident; journals,
  shadow copies and caches are out of scope) — **no secure-erase claim**;
- a same-user process could not have read or copied the bytes earlier — a copy
  is a **different object** (or a stream AIDO never wrote, §16 G′), outside
  this claim, and stays inside the existing same-user / no-confinement
  residual;
- the object is unmodified afterwards — a same-user actor can write new bytes
  into it after L24; if those are copies of the endpoint or token, that is the
  same copy residual.

---

## 7. Retained exact-object authority (the model)

**RA-1 — acquisition (RETAIN).** A writer acquires H_r **only** by
`ReOpenFile(H_c, 0, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
FILE_FLAG_OPEN_REPARSE_POINT)` on the genuine creating handle of the sensitive
child, **while H_c is still held**, and **only after** the sensitive bytes were
written, read back and pin-verified (L9 step 9a / L11 E9). No pathname is
reopened; no file id is looked up.

**RA-2 — identity and non-inheritance.** Immediately, from handles only:
`FILE_ID_INFO(H_r) == FILE_ID_INFO(H_c)`, and `HANDLE_FLAG_INHERIT` is clear on
H_r. Either failing ⇒ H_r is **never written through**; it is released
(RELEASE-R, §8) and the writer fails (§9/§10).

**RA-3 — typing and minting.** The retained authority is a mint-backed value
(the `_MintBacked` pattern already used for pins and children: authority is a
private registry entry, the value carries only a nonce, direct construction is
refused, the slot cannot be rebound). Its private entry records: the raw
Win32 `HANDLE` (never adopted into a CRT descriptor), the **kind**
(`config_models` | `extension_token`), the identity proven in RA-2, and the
minting generation-interval nonce. An issuance registry accepts only its own
kind, minted in the same typed interval as the children it is registering
(AM-10's typing, extended to this one new object). There is no third kind and
no generic retained-object API.

**RA-4 — privacy.** The raw handle exists only in that private entry. It is
never a field, attribute, `repr`/`str` fragment, pickle/copy payload, record
field, console line, exception text, port argument or return value of any
public object. The public L9/L11 results (`GeneratedCfg1Config`,
`GeneratedCfg1Extension`) carry only the existing random issuance token
string; the issuance record (module-private) refers to the retained authority
value, never to the raw handle.

**RA-5 — exactly one retirement owner, decidable from the registry.** From
RETAIN until retirement, the retained authority has exactly one owner:

- **the writer invocation** — from RETAIN until the issuance registry insert,
  and again after a RECLAIM (§11);
- **the issuance registry entry** — from the insert until L24 retires it or the
  writer reclaims it.

Ownership is decided by asking the issuance registry, keyed by the retained
authority value itself, "does an ACTIVE entry reference this retained
authority?" — never by a token string a caller holds, never by a path. So a
registration that committed without the writer learning its token (an
asynchronous interruption between the insert and `return`) is still found and
reclaimed.

**RA-6 — release authority belongs to the owner, and every retirement of an
identity-proven H_r either scrubs or follows a proven scrub.** There is **no**
operation that drops an identity-proven retained handle while its object may
still hold unscrubbed sensitive bytes and calls that clean: the owner either
runs SCRUB-R (§8), or — only in a writer failure path where the object was
already scrubbed through H_c — RELEASE-R. The existing pure-pop
`discard_config_issuance` / `discard_extension_issuance` therefore cannot
remain the retirement path for a sensitive issuance (a pure pop would strand
H_r); §18 names this.

**RA-7 — single-shot retirement.** Retirement **removes the registry entry
first**, then acts. A second retirement of the same token or retained
authority finds nothing, performs **no I/O**, and returns `False` — it is
idempotent in effect and fail-closed in result; it can never yield `True`.

**RA-8 — no other consumer.** L14/L15 never use, duplicate or release H_r.
Nothing duplicates H_r (no `DuplicateHandle` in CFG1). No child process can
inherit it, however L14 launches, because H_r is proven non-inheritable
(RA-2).

**RA-9 — registry-emptiness halt.** The run-scoped registries-empty check
(`stage_runner._run_scoped_registries_empty`, Sec. 19.1 item 4) gains the
retained-authority registry: any surviving retained entry is the same halt as a
surviving issuance.

---

## 8. Primitive contracts (the *what*; names illustrative)

**SCRUB-C — scrub through the creating handle** (writer failure paths only).
On the still-held H_c: truncate to `EndOfFile = 0`; `FlushFileBuffers`;
`FileStandardInfo.EndOfFile` type-exact `0`. Returns `True` iff all three
succeeded. It closes nothing. (§3.2 row 10.)

**RETAIN** — RA-1 + RA-2. Returns a retained authority owned by the writer, or
fails having released any H_r it obtained.

**SCRUB-R — scrub-retire through the retained handle** (L24; writer reclaim
after the creating handle was released). Given a retained authority and its
owner's right to retire it:

```text
1  remove the private retained entry (single-shot, RA-7); a malformed entry,
   wrong kind, or non-HANDLE value                        → False (release what exists)
2  H_s := ReOpenFile(H_r, GENERIC_WRITE | FILE_READ_ATTRIBUTES, 0,
                     FILE_FLAG_OPEN_REPARSE_POINT)        → failure: False
3  FILE_ID_INFO(H_s) == issued identity; H_s not inheritable
                                                          → else False, NOTHING written
4  SetFileInformationByHandle(H_s, FileEndOfFileInfo, 0)   → failure: False
5  FlushFileBuffers(H_s)                                   → failure: False
6  FileStandardInfo(H_s).EndOfFile is an int and == 0      → else False
7  CloseHandle(H_s) succeeds                               → else False ("scrub_handle")
8  CloseHandle(H_r) succeeds                               → else False ("retained")
   True only if 2–8 all succeeded.
```

Every handle that was obtained is closed exactly once whatever happened
earlier; a failed close is counted (§15), never retried, never swallowed.
Nothing in SCRUB-R names, opens, renames or deletes a path.

**RELEASE-R — release without writing.** `CloseHandle(H_r)` only. Used (a) when
RA-2 failed (the handle is not proven to be AIDO's object and is never written
through), and (b) in a writer failure path after SCRUB-C already scrubbed the
object through H_c. Returns the close result; a failure is counted
(`"retained"`).

**RECLAIM** — the writer's question to the issuance registry under RA-5: if an
ACTIVE entry references this retained authority, remove it (no I/O) and return
ownership to the writer. Idempotent.

---

## 9. L9 — `models.json` failure state machine

**Order inside `write_cfg1_pi_config`** (steps 0–9a and step 10's checks
unchanged):

```text
 8    endpoint_write_attempted := True  →  write models.json through H_c       (G4)
 9/9a read-back through H_c; actual bytes vs pins
10a   RETAIN: H_r := ReOpenFile(H_c, 0, share RWD, OPEN_REPARSE_POINT)        (RA-1)
10b   FILE_ID_INFO(H_r) == FILE_ID_INFO(H_c); not inheritable                  (RA-2)
10    register_config_issuance(…, retained = H_r authority)  — every existing
      check through the held H_c first; the registry insert, which takes
      ownership of H_r, is the LAST statement                                   (RA-5)
10c   build the public GeneratedCfg1Config BEFORE any release
11    release: interval first (as today); then
        K  a failure is known  → RECLAIM (if registered); if endpoint_write_attempted:
           SCRUB-C through H_c, then (namespace) disposition through H_c, best effort;
           close every child; RELEASE-R (if H_r was acquired); pins
        S  no failure known    → close every child; parentage discard; pins
           S′ any of those releases failed → RECLAIM; SCRUB-R; raise
           else                → return the object built at 10c; nothing else executes
```

**Writer-local facts** (never durable): `endpoint_write_attempted`;
`failure_known`; `scrubbed` (a SCRUB-C or SCRUB-R result); `models_closed` (H_c
close result); `retained_acquired`; `retained_released` (RELEASE-R result, or
subsumed in SCRUB-R's `True`).

**The one formula** (computed once, carried on every
`Cfg1PiConfigError(reason_code, endpoint_material_outstanding)`):

```text
endpoint_material_outstanding =
    endpoint_write_attempted
    ∧ ¬( scrubbed ∧ models_closed ∧ ( ¬retained_acquired ∨ retained_released ) )
```

where, on the SCRUB-R path, `scrubbed ∧ retained_released` is exactly SCRUB-R's
`True`. The reason-code precedence (a release-failure code replacing an
in-flight one) is unchanged; the bool does not depend on which code wins. The
disposition result is **not** an input.

| L9 exit | attempted | scrub authority | scrub | H_c close | H_r | outstanding | executor `generated_config_scrub_verified` |
|---|---|---|---|---|---|---|---|
| L9 never entered | — | — | — | — | — | — | initial `True` |
| raise before the models write (steps 0–7, gate, `settings.json` write) | `False` | — | — | — | — | `False` | `True` |
| raise after the write began, before 10a (partial write, 9, **9a**, unanticipated body exception) — scrub ok, close ok | `True` | H_c (SCRUB-C) | ok | ok | none | `False` | `True` |
| same — SCRUB-C fails (truncate / flush / query / `EndOfFile ≠ 0` / raises) | `True` | H_c | **fail** | (attempted) | none | `True` | stays `False` |
| same — scrub ok, **H_c close fails** | `True` | H_c | ok | **fail** | none | `True` | stays `False` |
| **10a RETAIN fails** | `True` | H_c | ok | ok | not acquired | `False` | `True` |
| **10b identity mismatch** or inheritable H_r | `True` | H_c (H_r never written) | ok | ok | RELEASE-R ok | `False` | `True` |
| same — RELEASE-R fails | `True` | H_c | ok | ok | **fail** | `True` | stays `False` |
| **10 registration raises before its insert** | `True` | H_c | ok | ok | RELEASE-R ok | `False` | `True` |
| **insert committed, then a raise before `return`** (10c construction, or an asynchronous interruption) | `True` | RECLAIM, then H_c | ok | ok | RELEASE-R ok | `False` | `True` |
| successful generation; at release **H_c close fails** (first discovered during release) | `True` | RECLAIM, then SCRUB-R (normally refused by sharing if H_c is in fact still open) | any | **fail** | SCRUB-R | `True` (H_c release failed) | stays `False` |
| successful generation; H_c closed ok; **another child close or a pin release fails** | `True` | RECLAIM, then SCRUB-R | SCRUB-R | ok | SCRUB-R | `¬SCRUB-R` | `True` iff SCRUB-R `True` |
| successful normal return | `True` | — (issuance owns H_r) | — | ok | owned by issuance | not reported | stays `False` (write-ahead) until L24 |
| non-`Cfg1PiConfigError`, malformed attribute, non-bool | — | — | — | — | — | — | stays `False` (G6) |

A leaked pin or a failed `settings.json` close remains its own existing
lifecycle fact (it makes L27 fail by construction), exactly as R6's
corresponding row said; it no longer forces the endpoint fact `False` when the
endpoint object itself was proven scrubbed.

---

## 10. L11 — `ar2_config.ts` failure state machine

Identical structure over the token child (the last child written, E8), with
`token_write_attempted` set immediately before the token write:

```text
E8    static children, then token_write_attempted := True → token write through H_c
E9    read-back; static digests vs pins
E9a   RETAIN from the TOKEN child's H_c only (static children get no retained handle)
E9b   FILE_ID_INFO(H_r) == FILE_ID_INFO(H_c); not inheritable
E10   register_extension_issuance(…, retained = H_r authority): all existing checks
      through the held handles first; the insert (taking ownership of H_r) is LAST
E10c  build GeneratedCfg1Extension BEFORE any release
E11   K: RECLAIM; if token_write_attempted: SCRUB-C on the token child's H_c; then
         dispositions (namespace; token child and, best effort, static children);
         close every child; RELEASE-R; directory pin; root pin
      S: close every child and pin; S′ any failed → RECLAIM; SCRUB-R; raise;
         else return the object built at E10c
```

```text
token_material_outstanding =
    token_write_attempted
    ∧ ¬( scrubbed ∧ token_closed ∧ ( ¬retained_acquired ∨ retained_released ) )
```

| L11 exit | attempted | scrub authority | outstanding | `extension_binding_scrub_verified` |
|---|---|---|---|---|
| E-1 pin refusal; E0–E7; E8 before the token write | `False` | — | `False` | `True` |
| failure after the token write began, before E9a — SCRUB-C ok, token close ok | `True` | H_c | `False` | `True` |
| same — SCRUB-C fails, or token-child close fails | `True` | H_c | `True` | `False` |
| E9a RETAIN fails / E9b mismatch (RELEASE-R ok) / E10 raises before insert | `True` | H_c | `False` iff SCRUB-C ∧ close ∧ (RELEASE-R if acquired) | per the bool |
| insert committed, then a raise before `return` | `True` | RECLAIM, H_c | as above | per the bool |
| success, then token-child close fails at E11 | `True` | RECLAIM, SCRUB-R | `True` | `False` |
| success, then a static-child close or pin release fails at E11 | `True` | RECLAIM, SCRUB-R | `¬SCRUB-R` | `True` iff SCRUB-R `True` |
| success | — | issuance owns H_r | not reported | `False` until L24 |
| non-typed / non-bool | — | — | — | `False` (G6) |

Nothing is ever deleted by pathname; the directory is never removed by the
writer (R-WINDOW-E and R6 E11's rule stand).

---

## 11. Success-path issuance transition (partial-failure analysis)

### 11.1 Decision on the reviewer's preferred order (C-1)

The reviewer's preferred transition was **B** RETAIN → **C** identity → **D**
release H_c → **E** register. Analyzed against the frozen registration
contract, **D-before-E conflicts** with preserved clauses: `register_config_issuance`
and `register_extension_issuance` prove issuance provenance against the
**open-child registry** (`require_production_issuance_provenance` /
`require_extension_issuance_provenance`, AM-10's typed interval), and read the
children's identities and bytes back **through the held creating descriptors**
(FU15 step 10; R6 §9.2b item 6's expected-digest binding; R6 E10). Releasing
H_c first would require redesigning that provenance and read-back contract —
not authorized here.

**Adopted: B → C → E → D**, with two added rules that deliver every property
D-before-E was meant to deliver: (i) the registry insert, taking ownership of
H_r, is the **last** statement of registration, and the public result object
is built **before** any release, so after a successful return nothing but
`return` executes; (ii) any release failure after registration **reclaims**
the entry and **scrubs through H_r** (SCRUB-R) before raising, so no raise can
leave an ACTIVE issuance. The rejected alternative — a prepare/commit split of
registration so H_c can close before the insert — is recorded in §21.

### 11.2 Boundary table

"Foreign modification" means a write, truncation, disposition or deletion
reaching any object AIDO did not create. In every row it is **impossible**:
the only writes are through H_c (a `CREATE_NEW`, share-0 handle to the object
this invocation created) or through an H_s reopened from an identity-proven
H_r and itself identity-checked; no pathname is ever used to write or delete.

| Boundary | Owner of the exact object | Authoritative handle | Can sensitive bytes remain? | Who may scrub | If a close fails | If registration raises |
|---|---|---|---|---|---|---|
| **T0** after 9a/E9, before RETAIN | writer | H_c | yes, pending | writer via H_c | n/a | n/a |
| **T1** RETAIN fails | writer | H_c | only if SCRUB-C or H_c close fails ⇒ outstanding `True` | writer via H_c | H_c fail ⇒ outstanding `True`, counted `"child"` | n/a |
| **T2** RETAIN ok, identity mismatch / inheritable | writer | H_c (H_r unproven, never written) | as T1 | writer via H_c | H_c or H_r close fail ⇒ `True` (`"child"` / `"retained"`) | n/a |
| **T3** identity ok, registration raises **before** insert | writer (RA-5: no entry references H_r) | H_c; H_r writer-owned | as T1 | writer via H_c, then RELEASE-R | as T2 | the case itself: K path |
| **T3′** insert committed, raise **before** `return` | registry → RECLAIM → writer | H_c; H_r after reclaim | as T1 | writer via H_c after RECLAIM | as T2 | reclaimed; no ACTIVE issuance survives the raise |
| **T4** releases after a successful registration; H_c close fails | registry → RECLAIM → writer | H_r (H_c state unknown) | **possibly** (SCRUB-R is normally refused by sharing if H_c is still open) ⇒ outstanding `True` always | writer via H_r | the case itself; counted `"child"` | n/a |
| **T5** releases; H_c ok, another child/pin release fails | registry → RECLAIM → writer | H_r | only if SCRUB-R `False` | writer via H_r | pin/other-child failure is its own lifecycle fact | n/a |
| **T6** all releases ok → `return` | issuance registry | H_r (ACTIVE) | yes — intentionally live for the runtime | **L24 only** (§12) | n/a | n/a |
| **T7** executor assigns the result (`state.generated_config` / `state.extension`) in the same statement as the call | issuance registry | H_r | as T6 | L24 only | n/a | n/a |

**Therefore a successful writer return implies**, mechanically: the issuance
is ACTIVE; its entry owns an identity-proven, non-inheritable H_r to the exact
object; H_c (and every other writer handle and pin) was closed successfully;
and nothing a caller supplies — a path, a mutated attribute, another token —
can stand in for that authority at L24 (§12 step 1). **A raise implies** no
ACTIVE issuance for that invocation (T3′/T4/T5 reclaim), and a truthful
outstanding bool.

**Residual, stated.** An asynchronous `BaseException` arriving *inside* the
writer's release/reclaim code, or between the writer's `return` and the
executor's assignment, is outside the supported failure model, exactly as
FU4-FU1 already states for the existing issuance ("for every SUPPORTED L9
failure"). It cannot yield a false `True` (the durable fact is written `False`
ahead of the call and only an exact typed `False` or a completed L24 SCRUB-R
raises it), and a surviving entry trips RA-9's registry-emptiness halt.

---

## 12. L24 — success / failure state machine

L24 runs, as today, iff L9 (resp. L11) returned (`state.generated_config` /
`state.extension` is not `None`). The two files are scrubbed **independently**:
a `False` on one never skips, upgrades or masks the other.

For each sensitive issuance:

```text
1  OWNERSHIP. The token (read from the executor's own state) is a str naming an
   ACTIVE entry of THIS issuance kind; the entry's run_workspace_nonce equals the
   nonce of the run's genuine Cfg1RunWorkspace (type-exact, still minted in the
   run-workspace registry). No filesystem re-proof of the root, no issuance path
   re-derivation, no re-digest is a precondition (AMD2-4).
   Failure → False; the entry (if any) is NOT touched, NO I/O.
2  RETIRE BEGINS. Remove the entry (RA-7); take its retained authority.
3–9  SCRUB-R (§8): reopen H_s from H_r; identity == issued identity; truncate to 0;
   FlushFileBuffers; EndOfFile type-exact 0 from H_s; close H_s; close H_r.
→ scrub_verified := True only if 1–9 all succeeded; otherwise False.
```

Only then may `generated_config_scrub_verified` /
`extension_binding_scrub_verified` become `True`. **No pathname can grant L24
authority**: the L24 scrub has no path parameter and reads no path field.

| L24 case | returns | what is touched | notes |
|---|---|---|---|
| token malformed / unknown / other kind / nonce mismatch / workspace not type-exact or not minted | `False` | nothing | an entry belonging to another run is never retired; this run's own entry, if orphaned, trips RA-9 |
| retained authority malformed, wrong kind, not genuine, non-HANDLE value | `False` | entry removed; any genuine handle closed | counted if a close fails |
| `ReOpenFile(H_r, …)` fails (e.g. a foreign data handle is open — X2; object inaccessible) | `False` | H_r closed | content may remain; lifecycle fails closed |
| H_s identity ≠ issued identity, or H_s inheritable | `False` | **nothing written**; H_s, H_r closed | |
| truncate fails (e.g. a user-mapped view — X3 `1224`) | `False` | H_s, H_r closed | content may remain |
| `FlushFileBuffers` fails | `False` | H_s, H_r closed | |
| `EndOfFile` query fails, non-`int`, a `bool`, or `≠ 0` | `False` | H_s, H_r closed | a concurrent writer is excluded by share-0, so `≠ 0` means the proof failed |
| H_s close fails | `False` | H_r close still attempted | counted `"scrub_handle"` |
| H_r close fails | `False` | — | counted `"retained"` |
| all succeeded | **`True`** | the object's default stream only | the only positive proof |
| a second retirement of the same token | `False` | nothing, no I/O | RA-7 |

Any `False` ⇒ `"L24"` ∈ `lifecycle_failure_steps` ⇒ `INDETERMINATE_LIFECYCLE`,
halt `LIFECYCLE_CLOSURE_UNPROVEN`, **L26 skipped** (`LIFECYCLE_UNPROVEN`). L27's
later success never upgrades it (G5). Nothing is ever `True` from a pathname
observation, from absence, or from `NumberOfLinks`.

---

## 13. L27 — namespace cleanup is separate

- **L24 is content scrub. L27 is whole-owned-root namespace cleanup.** L27 is
  unchanged: it removes the owned root only if whole-root authority re-proves
  independently (R6 §8, CFG1 §17), and its facts are its own.
- After a `True` L24, the zero-length issued names (`models.json`,
  `ar2_config.ts`) and any aliases **inside** the owned root are removed by
  L27 with the rest of the tree. L24 deliberately deletes no name, so the
  "optional deletion of the expected pathname" is **not** part of any proof and
  is not performed at L24.
- If a same-user actor moved or linked the object **outside** the owned root,
  AIDO does not chase, open, or delete that pathname — neither L24 nor L27 has
  authority outside the root (CFG1 §37.3.2a's "What this does NOT grant",
  preserved). That name may persist as a **zero-length, scrubbed** file object;
  this is accepted under the stated same-user namespace residual (§20).
- L27 success never upgrades a `False` L24 fact; an L27 failure never
  downgrades a `True` one (they are independent facts).

---

## 14. Final semantics of the four sensitive-material bools

| Bool | Kind | `False` / `True` meaning (exact) |
|---|---|---|
| `endpoint_material_outstanding` | writer-local; exact `bool` on `Cfg1PiConfigError` only; never durable | `False` **iff** no endpoint byte was ever attempted, **or** the `models.json` object this invocation created had its default stream scrubbed to `EndOfFile == 0` through genuine handle authority (SCRUB-C via H_c, or SCRUB-R via H_r) **and** H_c closed successfully **and** H_r, if acquired, was released successfully (RELEASE-R, or inside SCRUB-R). Otherwise `True`. A delete disposition and a close, alone, **never** make it `False`. |
| `token_material_outstanding` | writer-local; exact `bool` on `Cfg1ExtensionError` only; never durable | identical, for the `ar2_config.ts` object |
| `generated_config_scrub_verified` | **durable** (existing v2 field; no new field) | Written `False` immediately before L9 (write-ahead). `True` iff (a) L9 was never entered (initial value), or (b) L9 raised the exact `Cfg1PiConfigError` with `endpoint_material_outstanding is False`, or (c) L24's SCRUB-R for the config issuance returned `True`. v2 meaning: *"no endpoint-bearing default-stream content of the exact file object this invocation created is known to remain"*. It says nothing about names, aliases, copies, or forensic state (§6). L27 never sets it. |
| `extension_binding_scrub_verified` | **durable** (existing v2 field) | identical, for L11 / `token_material_outstanding` / the extension issuance |

**No redundant durable field is needed.** The scrub/close/release halves are
writer-local or L24-local; the durable facts already carry exactly the one
conclusion the lifecycle predicate consumes, and v2 records carry no handle,
identity, path or digest of unredacted material (R6 §10, unchanged).

---

## 15. Close / release semantics

**Content scrub and resource release are separate halves, and a positive fact
needs both.** The one conservative rule, for L24 and for both writers alike:

> A sensitive-material fact is positive (`scrub_verified == True`, or an
> outstanding bool `== False` after bytes were attempted) **only if** the
> exact-object scrub (truncate → flush → `EndOfFile == 0`) passed **and every
> handle that had to be retired for that object closed successfully** — H_s
> and H_r at L24; H_c and, if acquired, H_r in a writer.

A close failure therefore stays fail-closed **even if the contents probably
became empty**. Nothing retries a close, re-derives a handle, or reaches for a
pathname.

**Close-failure accounting remains mandatory** (`_CLOSE_FAILURES`,
`close_failure_count()`), extended — never weakened — with two kinds:
`"retained"` (an H_r close failed) and `"scrub_handle"` (an H_s close failed).
The existing `"child"` (H_c), `"pin"` and `"source"` kinds are unchanged. The
R6 kind `"unlink_handle"` disappears with the primitive it described
(`identity_bound_unlink` leaves CFG1's L24 call graph, §18).

---

## 16. Hard-link / rename adversarial cases (the reviewer's A–G)

| Case | Object relation | Outcome under this design |
|---|---|---|
| **A** hard link exists **before** successful issuance (created while the writer's H_c is held — the Y-6 behavior) | same object | H_r is reopened from H_c, so it references that object; L24's SCRUB-R reaches it; the alias reads `b""` (§3.2 P5/P7). In a writer failure, SCRUB-C through H_c reaches it (§3.2 row 10). |
| **B** hard link created **after** issuance | same object | same as A |
| **C** original pathname **renamed** after issuance (inside the directory, elsewhere in the root, or out of the root) | same object | H_r is unaffected by rename (P5); SCRUB-R reaches the renamed object; the expected pathname is not consulted |
| **D** original pathname **replaced** by a foreign file | different object at the old name | the foreign file is **never opened, written or deleted** by L24 (no pathname is used); the AIDO object — renamed, aliased, or unnamed (X4) — is scrubbed through H_r; the foreign bytes are byte-identical afterwards (P7) |
| **E** multiple aliases outside the owned root | same object | every alias reads `b""` after SCRUB-R; none is deleted; they may persist as zero-length names (§13) |
| **F** alias added **during** L24 | same object | allowed by the OS even during share-0 (X1); the new name is the same object and reads `b""` after the scrub; it cannot open the object for data during H_s (X1) |
| **G** same-user actor copied the bytes into a **different** file before L24 | different object | **outside** AIDO's object-scrub claim — the existing same-user / no-confinement residual. Also in this class: **G′** bytes copied into an alternate data stream of the same object (AIDO never writes an ADS; the claim is the default stream only), and bytes written back into the object after L24 |

No foreign replacement pathname is opened or deleted merely because it has
the old name — in any case, by any step.

---

## 17. Test-suite delta

All tests: Windows/NTFS, synthetic objects under pytest `tmp_path` (an
"outside the root" location is a sibling `tmp_path` directory on the same
volume), synthetic `.invalid` endpoint and synthetic token, no Node/Pi, no
socket, no credential. Hard links via `os.link`. Fault injection through
module seams only (retain, identity read, inheritance read, registration
insert, truncate, flush, `EndOfFile` query, H_s close, H_r close), never by
monkeypatching `kernel32`. **No test may claim, assert, or be named as proving
secure or forensic erasure.**

**Deleted.** R6 Test **Y** in its entirety, in particular **Y-6** ("alias
creation **and** rename **fail** while the exclusive handle is held"), **Y-7**
(link-count faults), **Y-3/Y-4** as "`False` with no disposition", **Y-2/Y-8**
as "`False`", and **Y-5** as "the object is gone". The current worktree's
failing `test_y6_alias_and_rename_are_refused_while_the_exclusive_handle_is_held`
is superseded, not "fixed"; it stays exactly as it is until the corrective
phase deletes it (§18).

**New Test Y (AMEND2)** — the reviewer's items 1–20, each for **both**
`models.json` (config issuance, genuine `write_cfg1_pi_config`) **and**
`ar2_config.ts` (extension issuance, genuine CFG1 extension writer), driven
through the real executor where a lifecycle fact is asserted:

| # | Scenario | Must prove |
|---|---|---|
| Y-1 | retained handle bridges writer → runtime → L24 | during the ACTIVE issuance, pathname reads succeed (a share-READ-only reader and a plain `open`); L24 `True`; the object's `EndOfFile == 0`; the scrub handle's identity equals the identity captured at creation; retained registry empty afterwards; `close_failure_count()` unchanged |
| Y-2 | alias **before** issuance (hook while H_c is held, after the sensitive write) | the link is created (the accepted Y-6 behavior — the test never asserts refusal); issuance succeeds; L24 `True`; the alias reads `b""` |
| Y-3 | alias **after** issuance | L24 `True`; alias reads `b""` |
| Y-4 | **rename** after issuance — within the directory, elsewhere in the root, out of the root | L24 `True`; the renamed object reads `b""`; no pathname opened by L24 (a `CreateFileW`/`os.open` spy records zero pathname opens during L24) |
| Y-5 | **foreign same-name replacement** after a rename | L24 `True`; the foreign file's bytes and file id are unchanged; the AIDO object reads `b""` |
| Y-6′ | aliases **inside and outside** the root at once | L24 `True`; every alias reads `b""`; no alias is deleted by L24; L27 removes only in-root names; the outside alias persists at length 0 |
| Y-7′ | alias created **during** L24 (hook between the H_s reopen and the truncate) | link creation succeeds; after L24 `True` the new alias reads `b""`; a data open through any alias during the hook is refused (sharing violation) |
| Y-8′ | all aliases observe `EndOfFile == 0` | enumerated over every name created in Y-2…Y-7′ (by metadata and by read) |
| Y-9′ | foreign replacement untouched | byte-identical and same file id before/after, in every case that plants one |
| Y-10 | writer failure after endpoint/token bytes, at every point of §9/§10 (partial write, 9/9a or E9, RETAIN failure, identity mismatch, registration failure before insert, a raise after insert, release failures), each with an alias created while H_c was held | the alias reads `b""` in every row whose outstanding bool is `False`; in `True` rows (injected scrub/close failures) the test asserts the fact stays `False` and does **not** assert the content is gone |
| Y-11 | RETAIN (`ReOpenFile`) failure | SCRUB-C through H_c; outstanding `False`; no issuance registered; executor fact `True` |
| Y-12 | retained identity **mismatch**; and inheritable H_r | zero writes and zero reopens through H_r (spy); SCRUB-C through H_c; RELEASE-R; outstanding `False`; a failing RELEASE-R flips it to `True` and counts `"retained"` |
| Y-13 | registration failure (i) before its insert; (ii) after the insert, before `return` (result-construction fault and an injected interruption) | no ACTIVE issuance survives (`issued_token_count()` unchanged); RECLAIM observed in (ii); retained registry empty; outstanding per §9/§10 |
| Y-14 | L24 **truncate** failure (seam), and a real user-mapped view on an alias (X3) | `False`; handles closed; `"L24"` in failure steps; L26 skipped; the test asserts nothing about the bytes being gone |
| Y-15 | `FlushFileBuffers` failure | `False`; as Y-14 |
| Y-16 | `EndOfFile` verification failure: query fails, returns `None`, a `bool` `False`, `1`, a non-`int` | each `False` |
| Y-17 | **H_s close** failure | `False`; counted `"scrub_handle"`; H_r close still attempted |
| Y-18 | **H_r close** failure | `False`; counted `"retained"` |
| Y-19 | repeated cleanup | a second L24 retirement of the same token returns `False` with **zero** I/O (reopen spy count 0) and raises nothing; the executor retires each issuance exactly once; a second RECLAIM finds nothing |
| Y-20 | L27 never upgrades | for every `False` row above, a subsequent L27 whole-root success leaves the fact `False`, `INDETERMINATE_LIFECYCLE`, halt `LIFECYCLE_CLOSURE_UNPROVEN` |
| Y-21 | privacy (RA-4) | `repr`/`str`/`vars`/`pickle`/`copy.copy`/`copy.deepcopy` of `GeneratedCfg1Config`, `GeneratedCfg1Extension` and every record/console output contain no integer equal to the raw H_r value and no retained-authority object |
| Y-22 | static discipline | every `ReOpenFile` call site passes `FILE_FLAG_OPEN_REPARSE_POINT`; no L24 code path reads `NumberOfLinks` as a decision input (fault-inject link count `0`, `2`, `None` with `EndOfFile == 0` ⇒ still `True`); `identity_bound_unlink` is unreachable from L24 |
| Y-23 | registries-empty halt (RA-9) | a stranded retained entry trips the halt exactly as a stranded issuance does |
| Y-24 | foreign data handle open during L24 (X2) | reopen refused ⇒ `False` |
| Y-25 | every name deleted by a same-user actor while ACTIVE (X4) | if L24 returns `True`, `EndOfFile == 0` was read from H_s; if the host refuses the reopen, `False` — never a pathname-based `True` |

**Amended rows (R6 §11).**

- **Q** (L9 matrix): "disposition … strictly before the same handle's close"
  becomes "**scrub** (truncate → flush → `EndOfFile == 0`) strictly before the
  same handle's close"; "`models.json` is gone-by-handle in the `False` rows and
  still on disk in every `True` row" becomes "the object's `EndOfFile == 0` in
  every `False` row (the name may or may not remain; the test does not assert
  name absence); a `True` row asserts only the fact"; cases for RETAIN failure,
  identity mismatch, registration-before/after-insert and the reclaim path are
  added (Y-10…Y-13). Everything else in Q is unchanged.
- **R** (L11 matrix): the same substitution for the token child;
  `token_disposed` disappears as an input.
- **X** (foreign same-name / directory swap): "L24 deletes **nothing**" stays,
  and "the foreign object still exists afterwards" stays; but the expected fact
  changes from "`extension_binding_scrub_verified == false`" to "**`true`**
  whenever SCRUB-R completes on the issued object, which still exists by
  handle" — the foreign object is untouched in every case. L27's independence
  is unchanged.

Existing T-155 (CFG1: "L24's scrub is identity-bound and never deletes a
non-matching object") remains true and is kept.

---

## 18. Impact on the current implementation (identified, not edited)

The current worktree is **not accepted** and stays **uncommitted**. After this
amendment is accepted, one corrective follow-up phase needs, at minimum:

| Module | Minimum corrective change |
|---|---|
| `win_config_authority.py` | add the private retained-authority registry and mint-backed type (RA-3), RETAIN, SCRUB-C, SCRUB-R, RELEASE-R, a retained-count accessor for RA-9, and the `"retained"` / `"scrub_handle"` close-failure kinds; `ReOpenFile`, `FlushFileBuffers` and `FileEndOfFileInfo` join the documented Win32 surface. **Remove `identity_bound_unlink`** and its link-count / dispose / close seams from CFG1's L24 call graph (deletion recommended: it has no other caller). `dispose_child_by_handle` remains for writer namespace cleanup only. |
| `cfg1_pi_config.py` | steps 10a/10b/10c; pass the retained authority to registration; the K/S/S′ release paths of §9 (SCRUB-C before any close; RECLAIM + SCRUB-R on release failure); the §9 formula replacing `models_disposed`/`models_closed`; no computation after the last release but `return`. |
| `cfg1_extension.py` | E9a/E9b/E10c and the §10 release paths for the token child; the §10 formula replacing `token_disposed`. |
| `config_issuance.py` | the record holds the retained authority (private; never rendered); registration verifies kind, interval and identity equality against the models child and makes the insert the last statement; a RECLAIM entry point (writer only) and a retire-with-scrub entry point (L24 only) replace the pure-pop `discard_config_issuance` as the retirement path for a live issuance. |
| `extension_issuance.py` | the same for the token child. |
| `run_executor.py` / L24 | `_scrub_generated_config` / `_scrub_extension_binding` call the retire-with-scrub entry point after the §12 step-1 ownership check; they no longer call `verify_*_issuance` or `identity_bound_unlink`; L9/L11 handlers (write-ahead, G6 exact-type rule) are unchanged. |
| `stage_runner.py` | RA-9: `_run_scoped_registries_empty` also requires the retained registry to be empty. |
| `lifecycle.py` | no predicate change; close-failure kinds only through `win_config_authority`. |
| tests | `tests/test_cfg1_fu1_sensitive_material.py` (Y rewritten per §17; Q/R/X amended); `tests/conftest.py` hygiene also asserts the retained registry empty and releases stragglers; builders/doubles as needed. |

Not touched by the correction: static P, AMEND1's gate and L14, v2 identity
semantics, L14's re-proof, the pins and golden vector, step 9a, the run/refusal
record schemas.

---

## 19. Adversarial self-review

| # | Construction | Closed or residual |
|---|---|---|
| 1 | **Alias created while the writer's H_c exists** (Y-6 behavior) | **Closed.** Same object; H_r descends from H_c; SCRUB-C (failure) or SCRUB-R (L24) reaches it (§3.2 row 10, P7). |
| 2 | **Alias created while H_r exists** (runtime window, or during L24) | **Closed.** Same object (P5, X1); scrub reaches every name. |
| 3 | **Pathname renamed / replaced** | **Closed.** H_r ignores names (P5); the foreign replacement is never opened or deleted (P7, §16 D). |
| 4 | **Pre-existing foreign handle** — (a) data handle open at L24; (b) data handle opened and closed before L24; (c) zero-access or attribute handle; (d) mapped view | (a) **fail-closed**: share-0 reopen refused (X2) ⇒ `False`. (b) **residual**: it may have read the bytes — the copy residual (G). (c) **closed**: takes no part in sharing; after the scrub it references an empty object. (d) **fail-closed**: truncation refused `1224` (X3) ⇒ `False`. During the writer, (a)/(d) cannot arise: H_c is share-0 from creation. |
| 5 | **Sensitive object moved outside the root** | **Content closed** (P5/P7); **namespace residual**: a zero-length name may persist outside the root; AIDO does not chase it (§13). |
| 6 | **Registry token genuine, caller fields mutated** | **Closed.** L24 reads no path/identity/digest field from any public object; the token is only a lookup key checked against the run's own workspace nonce; another run's token ⇒ `False`, that entry untouched; this run's orphaned entry ⇒ RA-9 halt. Never a scrub of a foreign object, never a false `True`. |
| 7 | **Retained OS handle duplicated / copied through supported APIs** | **Closed for supported callers**: no public object carries the handle (RA-4, Y-21); copying a public object copies a token string. `DuplicateHandle` needs the raw value, which lives only in the private registry. H_r is non-inheritable (P2), so no child inherits it. **Residual (same-user)**: a same-user process with `PROCESS_DUP_HANDLE` on AIDO could duplicate H_r — equivalent to opening the file by name before L24 (it gains no new capability). A foreign duplicate refers to the same object (X8), so it cannot hide the object from the scrub; as a zero-access handle it cannot block the scrub; if it reopens for data access and holds that open at L24, the scrub fails closed (4a). In-process introspection of module-private registries is not a supported caller path (the FU4-FU1 stance, unchanged). |
| 8 | **Partial failure after sensitive bytes, before issuance** | **Closed.** SCRUB-C through the still-held H_c before any close (§9 T0–T3); outstanding `False` only with the scrub and every material release proven. |
| 9 | **Successful issuance, then every L24 failure boundary** | **Fail-closed** at each (§12 table): `False`, L26 skipped, `INDETERMINATE_LIFECYCLE`, halt; handles released or counted. **Residual**: in those failed runs the content may remain on disk; the run halts and says so. |
| 10 | **Same-user byte copy into a distinct object** | **Residual**, outside the claim (§6, §16 G/G′). |
| 11 | *Registration committed but the writer never learned the token* | **Closed** by RA-5's reclaim keyed by the retained authority (T3′), not by the token. |
| 12 | *A release failure first discovered after a successful registration* (R6 G3's case) | **Closed / fail-closed**: RECLAIM + SCRUB-R; if H_c's own close failed, outstanding stays `True` (§15). |
| 13 | *A writer leaves a retained handle behind* | **Detected**: RA-9 halt; Y-23. |
| 14 | *Handle-value reuse after close* | **Closed**: the private entry is removed before the close (RA-7), so no stale value is ever used again. |
| 15 | *Same-user actor attaches a reparse point to the object* | **Closed by construction** (untested: needs a privileged tag): every reopen is relative to a held object with `FILE_FLAG_OPEN_REPARSE_POINT`, and every derived handle is identity-checked. |
| 16 | *All names deleted by an actor while ACTIVE* (X4) | **Closed on the observed host**: the object remains reachable through H_r and is scrubbed; if a host refused the reopen, `False` (fail-closed). |
| 17 | *L24 skipped because closure itself raised before L24* (OC-4) | **Residual, pre-existing**: tied to OC-4 closure totality (pre-A4 barrier item 4); the durable fact is already `False`, and RA-9 halts. |
| 18 | *Forensic recovery* (clusters, MFT-resident data, journals, shadow copies) | **Residual, explicitly not claimed** (§6). |

**Result.** No construction yields `True` except a completed SCRUB-R (L24) or
an exact typed `False` from a writer whose SCRUB-C/SCRUB-R and every material
release succeeded. None depends on the number of names an object has, on any
name at all, or on excluding alias creation.

---

## 20. Residuals (stated, not closed)

1. **Same-user copy / no-confinement** (unchanged): bytes read or copied
   before the scrub — into another file, an ADS, memory, or back into the
   object afterwards — are outside the claim.
2. **Namespace (new wording, same principle):** zero-length names of the
   scrubbed object may persist outside the owned root. L24 never removes names;
   L27 removes only in-root names.
3. **Forensic:** no secure-erase claim of any kind.
4. **Runtime window (unchanged in kind):** between issuance and L24 the
   sensitive bytes are intentionally live for Pi; a same-user actor can read
   them then (1).
5. **Failed-proof runs:** when L24 is `False`, content may remain; the run is
   `INDETERMINATE_LIFECYCLE` and halts.
6. **Asynchronous interruption** inside release/reclaim code or between return
   and assignment: outside the supported failure model (FU4-FU1 stance);
   cannot produce a false `True`; RA-9 detects a stranded entry.
7. **Platform scope:** NTFS on the supported Windows host only (§3.5); OC-4's
   closure totality remains a pre-A4 barrier.
8. **R6/AMEND1 residuals not touched here** stand as frozen (R-WINDOW,
   R-WINDOW-E, the L14/L15 re-digest check→use sliver, OC-2).

---

## 21. Contradictions found (and resolutions)

| Id | Contradiction | Resolution |
|---|---|---|
| **C-1** | The reviewer's preferred transition (release H_c **before** registration) vs. the preserved registration contract, which proves provenance against the open-child registry and reads identities/bytes back through the held creating descriptors (FU15 step 10, FU4, AM-10, R6 §9.2b item 6, R6 E10). | Adopted **RETAIN → identity → register (insert last) → release**, with RECLAIM + SCRUB-R on any post-registration release failure and the result object built before release (§11). Every property the reviewer required of the transition holds (§11.2). **Rejected alternative:** a prepare/commit split of registration so H_c can close before the insert — it would redesign FU4/FU15 provenance and add a third owner state; not needed. **Reviewer decision requested (AMD2-D1):** accept the adopted order. |
| **C-2** | Frozen CFG1 §37.3.2a (CFG1 lines 6379–6389) requires L24's precise-child operation to prove "the target remains **contained**", and frozen CFG1 §16.2 L24 (CFG1 line 2273) says "after re-proving root authority and issuance" — vs. the reviewer's direction that the scrub reach the exact object **regardless of name**, including an object moved **outside** the root (§8 cases C, E). | Amended **narrowly** (AMD2-1, AMD2-4): for the *content scrub*, containment is replaced by handle lineage + identity, and root re-proof is not a precondition. The clause's other half — never following a redirect, never acting on a foreign object at the far end of a reference, never deleting outside the root — is preserved exactly: the scrub resolves no reference, deletes nothing, and writes only to an object AIDO created. **Reviewer decision requested (AMD2-D2):** accept that L24's ownership check is registry-level (§12 step 1) rather than a filesystem re-proof. |
| **C-3** | AMEND1 §4 / line 585 preserve the Y-6 stop rule; this amendment retires it. | Not a conflict in substance: the stop rule's purpose was to force exactly this return to design; it is discharged (AMD2-7). |
| **C-4** | R6 §9.2c's G3 ("a failure first discovered during release cannot reach back") vs. the retained handle, which *can* reach back. | G3's premise ("the only handle that could dispose is the one being closed") no longer holds once H_r exists; replaced by §11's reclaim rule (AMD2-3). Where H_c's own close failed, the outcome is still outstanding (§15), preserving G3's conservatism. |

No contradiction was found with static P, AMEND1's AMD-1…AMD-8, the v2
identity semantics, L14, the pins, step 9a, the stage-closure schema, or the
halt vocabulary.

---

## 22. Remaining blockers after this amendment

1. **Reviewer acceptance / freeze of this amendment**, including decisions
   **AMD2-D1** (§11.1) and **AMD2-D2** (§21 C-2).
2. **FU1 corrective implementation** — one offline phase on the existing
   uncommitted worktree, under R6 + AMEND1 + AMEND2 (§18), and its independent
   review/freeze, including the new Test Y (Y-1 … Y-25) and the amended Q/R/X.
3. R6 §17 items 4–8 as restated by AMEND1 §19 (OC-4, OC-5, Pi 0.85.1 restored
   by the operator, the static pre-A4 verification, a new A4 authorization) —
   unchanged in order and content.

---

## Status

```text
5F3B-HARNESS-CFG1-L1-BOUNDARY-FU1-Y6-AMEND2-DESIGN   CANDIDATE — PENDING REVIEW
Base: R6 (SHA-256 f9287e89…58bd0) + AMEND1 (SHA-256 bd8569e4…c14e) — NOT EDITED
Y-6: ACCEPTED — hard links bypass share-0; AM-12 continuity FALSE; stop rule discharged
OS-temp derivation: 35/35 required checks PASS (ReOpenFile retained-handle scrub works)
AMD2-1  L24 = handle-bound CONTENT scrub of the exact object; no unlink; no link count
AMD2-2  each sensitive issuance privately owns ONE zero-access H_r from ReOpenFile(H_c)
AMD2-3  writer failure = SCRUB-C through H_c; disposition is namespace only; reclaim rule
AMD2-4  L24 authority = registry entry bound to the run nonce; identity, not containment
AMD2-5  no new durable field; v2 meanings of the two scrub facts restated (§14)
AMD2-6  Test Y rewritten (Y-1…Y-25); Q/R/X amended; Y-6 refusal assertion deleted
AMD2-7  Y-6 stop rule discharged and retired     AMD2-8  R6 §18.0 constructions historical
Reviewer decisions requested: AMD2-D1 (transition order), AMD2-D2 (registry-level ownership)
Current worktree: NOT ACCEPTED, NOT EDITED, UNCOMMITTED.  A4 / Stage 2 NOT AUTHORIZED.
NO IMPLEMENTATION AUTHORITY GRANTED.
```
