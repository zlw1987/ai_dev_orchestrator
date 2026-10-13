# Phase 5F3B-CFG1-F5A — A2 Ordinary Handle Semantics and Qualification Disposition

```text
STATUS         NON-FROZEN, ADDITIVE evidence report. Amends nothing.
F5-A           NOT ACCEPTED, NOT FROZEN. HOLD (unchanged).
A2             NOT security-qualified. A2-3 INCOMPLETE. R-ALIAS UNRESOLVED.
LIVE LAUNCH    UNAUTHORIZED. No live Pi, Node, model, backend or credential touched.
BASE HEAD      68ae5b0327016f646df2e600592d0671e71eecc4   (tree clean at start)
PLATFORM       Windows 11 build 26200, NTFS (C:), Python 3.14.7. One host, one build.
CHANGED        experiments/pi_harness_cfg1/tests/test_cfg1_f5a_a2_ordinary_handle_semantics.py (new)
               experiments/pi_harness_cfg1/tests/ordinary_handle_actor.py (new, test-only helper)
               docs/PHASE_5F3B_CFG1_F5A_A2_ORDINARY_HANDLE_SEMANTICS.md (this file)
NOT CHANGED    pi_runtime_provision.py or any production module; the live-launch barriers;
               any frozen document; L9; U126; CLAUDE.md.
```

**Result: ORDINARY HANDLE EVIDENCE COMPLETE** for the three requested groups, on this host.
It is evidence about *ordinary sharing semantics* only. No reparse point, junction,
symlink, hard link or conversion was created, nothing was raced, `FILE_WRITE_ATTRIBUTES`
was never requested, and nothing outside owned disposable fixtures was touched. It is
**not** proof of containment beneath a converted parent and must never be cited as such.

## 1. What was run

```text
.venv/Scripts/python.exe -m pytest experiments/pi_harness_cfg1/tests/test_cfg1_f5a_a2_ordinary_handle_semantics.py -q -rP
  -> 62 passed in ~12-18 s   (10 consecutive clean runs after the final change; see §4 on two earlier intermittent failures)
```

Regression around it (production code is unchanged, so this is a sweep, not re-qualification):
`test_cfg1_t_coverage`, `_composition`, `_stage_decision`, `_adversarial`,
`_f5a_executor_integration`, `_f5a_a2_offline_candidate`, `_impl_fu1_findings`,
`_fu1_authority_surface`, `_fu1_static_identity` + the new module →
**447 passed, 4 skipped** (the four pre-existing "not an adversarial case" skips), 0 failed.

**Not executed:** the ~9-minute construction-scale module and the full ~15-minute CFG1
suite (no production change); `test_cfg1_f5a_windows_handle_probes.py` and
`test_cfg1_f5a_r1_windows_premises.py` (they create junctions/convert directories); the
preserved FU4-A2 draft; the 16 installed-Pi/Node conformance tests. **Skipped:** none by
this module on this host (it self-skips off Windows; a skip is not a pass).

Module layout: 11 tests group A, 35 group B (32 matrix rows), 15 group C, 1 provenance.

## 2. Provenance — which handles, and why they match the candidate

| Group | Handle under test | Produced by (the candidate's own code) | Access / share / disposition |
|---|---|---|---|
| A | the four final read-only pins (`package.json`, `dist/cli.js`, `dist/main.js`, `dist/core/sdk.js` in the synthetic LDT row) — **reopened** handles | `run_runtime_provision` → `_acquire_final_pins`, after the creating handle was closed | `GENERIC_READ` (granted `0x120089`, read back from the OS) / `FILE_SHARE_READ` / `OPEN_EXISTING` / `OPEN_REPARSE_POINT` |
| B | construction directory pins `d`, `e`; run-root pin `P` | `_create_child(…, directory)`; `_pin_run_root` | `d`,`e`: `LIST_DIRECTORY\|READ_ATTRIBUTES\|SYNCHRONIZE` (granted `0x100081`) / share `READ` / `FILE_CREATE`. `P`: `LIST_DIRECTORY\|READ_ATTRIBUTES` / share `READ\|WRITE` / `OPEN_EXISTING` |
| C | share-zero file child — the **creating** handle | `_create_child(…, file)`, then the production `_gate_exact_set` and `_write_verified_content` | `GENERIC_READ\|GENERIC_WRITE\|DELETE\|SYNCHRONIZE` (granted `0x13019f`) / share `0` / `FILE_CREATE` |

Provenance is *checked*, not asserted: `test_the_shapes_measured_here_are_the_production_shapes`
reads `_DIRECTORY_SHAPE`, `_FILE_SHAPE` and the AST of the single `CreateFileW` call in
`_acquire_final_pins` and `_pin_run_root`, so a later change to a production shape breaks this
evidence's labels rather than silently outliving them. Share mode is not queryable from a handle;
its effect is what the refusals and controls measure. Group A uses a **real minted CFG1 workspace**
and a real `run_runtime_provision` over a small synthetic approved payload; groups B/C call the
private primitives directly under a test-owned directory, exactly as the candidate's own
`primitive` tests do.

The second actor is a plain Win32 call (`ordinary_handle_actor.py`) — in-process, and for one
case a **separate process** of the same user running the same functions. It records the real
`GetLastError`; nothing is mapped or fabricated.

## 3. Observed behavior

`32` = `ERROR_SHARING_VIOLATION`, `5` = `ERROR_ACCESS_DENIED`, `80` = `ERROR_FILE_EXISTS`.
Every refused row below was checked for **no effect** (same identity, same bytes, nothing
renamed, replacement file untouched) and then for a **matched control**: the identical call on
the identical object after the held handle(s) were closed through the candidate's own ledger —
and every control succeeded, with its effect checked.

### A. Final read-only pins (reopened handles, held)

| Operation by a second same-user actor | While held (4 files, in-process and separate process) | Control after release |
|---|---|---|
| `DeleteFileW`; `os.remove` | refused, 32 | succeeds |
| rename (`MoveFileExW`; `os.rename`) | refused, 32 | succeeds; same identity at new name |
| replace (`MoveFileExW(REPLACE_EXISTING)` onto the held file; `os.replace`) | refused, **5** | succeeds; a *different* object now owns the name |
| open `GENERIC_WRITE` / `TRUNCATE_EXISTING` / `CREATE_ALWAYS` (+write); `open(…,'wb'/'r+b')` | refused, 32 (Python: EACCES, no `winerror`) | succeeds; effect verified |
| open `GENERIC_READ`, `FILE_READ_DATA`, `FILE_READ_ATTRIBUTES` | **succeeds** (read is shared) | succeeds |
| open `DELETE` access; `GENERIC_READ\|WRITE` | refused, 32 | succeeds |
| `CREATE_NEW` on the occupied name | refused, 80 (a name error) | still 80 |
| rename of ancestors `dist`, `C`, `RT`, `R` | refused, **5** (all four) | succeeds; renamed back, identity restored |

### B. Native construction directory pins

Staged over *which* handles are held (32 rows, each its own fixture, each refused row followed
by a full-release control). Held-set letters: `P` run-root pin, `d`/`e` native directory pins,
`f` native share-0 file; any handle not listed was closed first.

| Question | Observation |
|---|---|
| Empty pinned directory `s`: rename / `rmdir` | both refused, 32; control (pin closed) renames, renames back, removes |
| Rename a pinned directory (`d` or `e`), whatever else is held | refused, 32 — its own pin |
| **Unheld ancestor of a held descendant** (e.g. rename `d` with only `e` or `f` held; rename `P`'s directory with only `d`/`e`/`f` held) | refused, **5** |
| Rename the directory `P` itself while `P` is held | refused, 32 |
| Nothing beneath held | with only `P` held, rename of `d`, `e`, `f` **succeeds**; with nothing held, rename of `d` and of `P`'s directory **succeeds** |
| Held file child `f` | rename, delete, overwrite, truncate, replace: all refused (32) |
| **Side effect, not a designed guarantee:** a held native directory pin also refuses rename of its *unheld* direct children (`Pd`→`e`; `d`→`e`; `Pde`→`f`; and replace-onto `f`) | refused, 32. The run-root pin (`P`, share `READ\|WRITE`) does **not** do this (`P`→`d`,`e`,`f` rename succeeds) |
| **Limit:** a *closed* file child in a *held* parent (`Pde`, `f` closed) | `delete`, `open_write_existing`, `truncate_existing` **succeed**; replace/rename refused (the parent effect above) |
| **Limit:** a new name created inside a held pinned directory | **succeeds**; the exact-set gate then refuses it (`PARENTAGE_GATE_FAILED`); the matched fixture without the intruder passes the gate |

### C. Share-zero file children (creating handle held; content already written through it)

| Question | Observation |
|---|---|
| Incompatible opens (read, read-data, write, read+write, delete-access) | refused, 32; Python `open()`/`os.remove`/`os.rename`: EACCES / 32; all succeed after release |
| **Recorded exception:** an open requesting only `FILE_READ_ATTRIBUTES` | **succeeds** (not subject to the share check on this build); it grants no data or delete access |
| Exclusive creation of an occupied name — same name, case variant, a *directory* at that name, a different occupied sibling | real `NTSTATUS` **`0xC0000035`** (`STATUS_OBJECT_NAME_COLLISION`) for all four; no handle returned; production wrapper → `NATIVE_CREATE_REFUSED`; directory listing unchanged; the status is identical after the child's handle is released (it is a *name* fact) |
| Delete / rename / replace / overwrite / truncate / `CREATE_ALWAYS` | all refused (32; replace is 32 with parents held but **5** with the child alone), in **two configurations**: all parent pins held, and the **child alone held** (every directory pin and the sibling closed first) so that the refusal cannot be a side effect of a parent pin. All succeed after release |
| Creating handle still refers to the original object | after every attempt: handle-derived `FileIdInfo` == recorded identity == identity at the path; `EndOfFile` unchanged; the bytes read back **through the creating handle** equal the written bytes and contain no second-actor bytes. After release the object at the path has the same identity and the same bytes |

Handle release: every ledger ended `CLOSED` with `open_count == 0`, and the **process** handle
count (`GetProcessHandleCount`, after `gc.collect()`) equals its pre-test baseline, in every test.

## 4. Adversarial review of this evidence

| Question | Finding |
|---|---|
| Did the intended production primitive run? | Yes. Group A reaches `STATE_PROVEN` through `run_runtime_provision`; the pins are read from the provision's own ledger and re-proven live (`_raw_identity(entry.raw) == entry.identity == identity at path`) before and after each batch. B/C use `_pin_run_root`, `_create_child`, `_gate_exact_set`, `_write_verified_content` unmodified. |
| Correct access/share? | AST + constant check of the production functions, plus the access mask the OS actually granted (above). Share is proven only by effect. |
| Still held at the second operation? | Asserted immediately before and after each attempt (ledger state `OPEN` and live identity). |
| Invalid fixture instead of sharing semantics? | The same path is opened for read by the second actor while held (positive control); every refusal has an identical-call control that succeeds after release. **A first draft of C failed exactly here:** its rename/replace control was refused because a held *parent* pin also refuses renaming a child, so the refusal was not attributable to the child's handle. C was restructured into the two configurations above. |
| Passed for the wrong reason? | Two cases caught and fixed: a directory handle's enumeration cursor is **single-pass**, so a second enumeration returned empty — one check passed trivially (the new-name test) and one failed spuriously (C). They now use a fresh pathname listing, and the new-name test has a matched fixture whose gate passes. |
| Non-vacuous? | Mutation, in-memory, scratch plugin only (production file untouched): final-pin share → `7` fails 12 tests; native directory/file shares → `7` fails 29; a `_close_raw_handle` that reports success without closing fails 61 teardown checks and 47 tests. |
| Flaky or invalid control? | Yes, twice, and it was fixed rather than hidden. Across the ~13 runs before the final change, the group-A ancestor test failed twice (once refusing the *control* rename of `R`, once refusing the *restore* of `RT`, both error 5). Both are positive operations that need every handle beneath to be closed, consistent with a transient handle taken by something outside the test (an indexer or scanner reading the fresh temporary tree); the cause was **not** positively identified. Positive controls and restores now go through `_positive` (≤ 5 attempts, 0.2 s apart, attempt count recorded). **Held-phase refusals are never retried.** 10/10 clean runs followed. Groups B and C showed no such failure. |
| Teardown could hide a leak? | Group A: workspace removed through the frozen remover, tree proven gone, test-owned trees removed, handle count at baseline. B/C: ledger closed, handle count at baseline, fixture trees removed — each a teardown **error** if not. One earlier +1 handle was traced to `sys.getwindowsversion()` (first call allocates a process-lifetime handle) and removed by computing it at import; it was a test-helper artifact, not the candidate. |
| Conclusions broader than measured? | Possibly, if read carelessly — see §4.1. |

### 4.1 Findings that bound the claims (none falsifies a required property)

1. **Replace is refused by *any* open handle, not by share mode.** With the final-pin share mutated
   to `READ\|WRITE\|DELETE`, rename/delete/overwrite refusals vanish but `replace_by_other` and the
   ancestor-rename refusals **persist**. So P-R1-1's "replace" and P-R1-2's ancestor-rename refusals
   rest on an NTFS rule about open handles, not on the pin's share word. It held on this build; it
   is not a documented guarantee.
2. **A held native directory pin blocks rename of its unheld children** as a side effect of its share
   mode (`READ`, no `WRITE`). Useful, undocumented, **must not be relied on**; the run-root pin does not do it.
3. **Construction pins protect names/rename, not the bytes of *closed* children.** A closed child of a
   held parent can be deleted or overwritten by a second actor. This is the already-documented
   posture (candidate §3 "post-validation mutation"): the **post-pin PI-PC1 walk** and the four final
   pins are what remain, and after the walk every non-LDT file is unpinned (inherited R-ABA/R-SLIVER).
4. **A pinned directory does not stop a new name inside it.** The exact-set gate is load-bearing.
5. **An attribute-only open bypasses sharing.** Recorded for share-0 (C). This is the same mechanism
   R1-FU3 used for in-place conversion, which was **not** tested here.

No measured result contradicts INV-F5A-R1, INV-F5A-W's construction-ordering claims, or any P-R1
property as worded for the *ordinary* operations tested.

## 5. P-R1 status for the A2 shapes

| Property | This phase | Status |
|---|---|---|
| P-R1-1 final pin cannot be deleted / renamed / replaced / overwritten | 6 ops × 4 files, in-process + separate process, with controls; **A2's own reopened pins** | **PASS for the operations measured.** Overall stays **PARTIAL**: the historical record has one `UNSUPPORTED` op (`FileRenameInfoEx` directory-replacing-file) and 14 op variants (`FileDispositionInfo[Ex]`, POSIX rename, `ReplaceFileW`, …) that were **not re-run** against A2's handles; they are carried only by shape identity |
| P-R1-2 `dist`/`C`/`RT`/`R` not renamable while pins held | `MoveFileExW` on all four, with controls | **PASS for `MoveFileExW`**; `FileRenameInfo`/`FileRenameInfoEx` variants **UNPROVEN under A2** (historical PASS by shape identity) |
| P-R1-3 walk + L14/L21A complete with pins held | not re-measured; the candidate's post-pin walk completed with the four pins held in every group-A run | **UNPROVEN in this phase** (supported by the accepted offline integration and construction-scale runs) |
| P-R1-4 construction shape | (ii) share-0 exclusivity + (iv) rename/delete refusal of **native** pins measured; (i)/(iii)/(v) at scale were accepted earlier | **Not marked PASS.** Ordinary parts PASS; the **in-place conversion** part of (iv) is **UNPROVEN, deliberately not tested** (R1-FU3 stands: FAIL / HOLD) |
| P-R1-FU3 conversion | not touched | **FAIL / HOLD unchanged** |

## 6. Proposed A2-specific replacement / qualification mapping (for reviewer consideration)

Not an amendment; the frozen §14 is untouched.

**Pathname-era assumptions that are obsolete for A2**

| # | Assumption | Disposition |
|---|---|---|
| O-1 | §7.4A.2 steps 1–2: pathname `CreateDirectoryW` then pin; pathname `CreateFileW(CREATE_NEW)` | replaced by one `NtCreateFile(FILE_CREATE)` relative to a held parent; P-R1-4(i) "create then pin" is **superseded as worded** (no interval) |
| O-2 | §7.4A.3: a held share-READ pin cannot be converted in place (W3), so creates cannot escape `R` | **disproven** by R1-FU3 for empty directories; **not carried forward**. Replaced by the explicit A2-3/A2-6 outcomes, which are unmeasured |
| O-3 | P-R1-4(iv) "in-place junction conversion is refused" | **dropped from A2's mandatory list**; it may only return as a measured A2-3/A2-6 fact |
| O-4 | R-WINDOW create-then-pin interval for construction objects | **eliminated** for construction objects; remains only for the creator→pin interval of the four final pins (pre-authority) |
| O-5 | Directory pin = `GENERIC_READ` share READ | A2 uses `LIST_DIRECTORY\|READ_ATTRIBUTES\|SYNCHRONIZE`, share READ (both read-only, no DELETE share) |
| O-6 | "ancestor rename is refused *because of the pin's share mode*" | the refusal rests on open handles beneath (error 5), shown by mutation (§4.1-1) |

**Guarantees that remain mandatory**

| # | Guarantee | Established? |
|---|---|---|
| M-1 | final-pin read-only/ordinary-op refusals (P-R1-1 shape) | ordinary ops yes; API-variant breadth no |
| M-2 | ancestor-rename refusal (P-R1-2 shape) | `MoveFileExW` yes |
| M-3 | walk completes with pins held (P-R1-3) | by earlier evidence; not re-measured |
| M-4 | native-pin rename/delete refusal; share-0 exclusivity; occupied-name refusal; creating handle keeps the object | **yes, this phase** |
| M-5 | 360/80/362, depth 11, peak ≤ 462 (measured 449) | yes (construction-scale report) |
| M-6 | exact-set gate before any content byte, and the post-pin walk as the only protection for closed non-LDT children | yes as mechanism; **limits in §4.1-3/4 are binding** |
| M-7 | **create beneath a converted parent; racing conversion (A2-3, A2-6)** | **no — blocking** |
| M-8 | A2-2 corrected predicate executed | **no** |
| M-9 | R-ALIAS disposition (hard-link aliasing, L9) | **no** |
| M-10 | 8.3/Unicode/long-path, ReFS/Dev Drive, other builds, filter drivers | **no** |

## 7. Established / still unresolved

**Established (not security qualification):** accepted A2 offline integration; construction-scale
evidence (449 ≤ 462, native handle-relative creation, exact-set gate ordering, truthful release);
**and, measured here:** the ordinary rename/delete/replace/overwrite refusals and their matched
controls for A2's final pins, native directory pins and share-zero children; real `0xC0000035`
for exclusive creation of an occupied name; that the creating handle keeps referring to the
original object; the limits in §4.1.

**Still unresolved:** A2-3 (INCOMPLETE); conversion/create concurrency (A2-6); A2-2's corrected
predicate; R-ALIAS; attribute-only-open reparse conversion (R1-FU3 FAIL stands); P-R1-1
API-variant breadth; P-R1-3 re-measurement; platform breadth; independent acceptance of
D-F5A-9/10; E5 conditions. The two live-launch barriers are byte-identical to `68ae5b0`.

## 8. Correctness of the mechanism versus the missing containment proof

The implemented A2 mechanism behaves as designed at the ordinary level: creating handles keep the
objects they created, share-zero children and native pins refuse the ordinary operations, and the
gate/ledger/release behave truthfully. That is *correctness of the implemented mechanism for
ordinary same-user operations*. It says nothing about whether a create relative to a **converted**
parent lands outside `R` (A2-3), and the one handle-shape that most obviously permits conversion —
an attribute-only open — is exactly what was **not** exercised. Closing that gap needs a
separately authorized, conversion-dependent step.

## 9. Smallest next independent-review decision

Whether to authorize the **single** conversion-dependent qualification step (A2-3 plus the
candidate's own construction under A2-3/A2-6), or to accept A2 as "mechanism-correct at the ordinary
level, containment unproven" with live enablement kept barred. This report does **not** recommend
another ordinary Windows-test expansion; none of §4.1 is a contradiction that would justify one.
