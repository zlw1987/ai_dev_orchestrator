# Phase 5F3B-CFG1-F5A — FU4-A2 Evidence Preservation and Review-Readiness Report

```text
STATUS            NON-FROZEN, ADDITIVE. Evidence preservation only.
F5-A              HOLD (unchanged).
A2                a SELECTED CANDIDATE. NOT an accepted design. NOT implemented.
A2-3              INCOMPLETE -- fixture failure; corrected draft not revalidated.
R-ALIAS           UNVERIFIED -- CONFLICTING EVIDENCE.
BASE HEAD         8343db1ecbca3a20c1d1e4c859b9574188a03c7c
TOUCHES           this file; one preserved draft test module; one preserved JSON.
DOES NOT TOUCH   production source, cfg1_pi_config.py, win_config_authority.py,
                  the F5-A amendment (so the U126 evidence binding is unaffected),
                  the frozen CFG1 design, historical evidence, CLAUDE.md.
EXECUTED HERE    nothing from the A2 module. No experiment was run, re-run, or
                  re-submitted by another route for this report.
```

This is a record, not an acceptance. It makes the FU4-A2 investigation
inspectable so a reviewer can decide the next step without commissioning another
open-ended investigation. It does not reopen U126 or re-audit any frozen phase.

---

## 1. Provenance legend

Every statement below carries one of these tags. They are deliberately not
merged, because they have very different evidential weight.

| Tag | Meaning |
|---|---|
| **[DOC]** | Stated on a Microsoft Learn page fetched while preparing this report (2026-10-12). |
| **[JSON]** | A value in the preserved machine-written file `f5a_fu4_a2_prior_run_report_UNRECONCILED.json`. Written by the draft module's own roll-up on a **prior run of unknown draft revision** (see §3). |
| **[NARR]** | The final summary of the prior investigation session (`Native handle-relative creation feasibility`). Secondary: a recollection by the previous assistant. Used only where **[JSON]** or **[SRC]** corroborates, or where marked uncorroborated. |
| **[SRC]** | Read directly from source in this task (the preserved draft, the F5-A amendment, `cfg1_pi_config.py`, the P-R1 helpers). Reading is not running. |
| **[INF]** | Engineering inference. May be wrong. Never a measurement. |

Nothing tagged **[NARR]** or **[INF]** is a test result.

## 2. What is preserved, and what is not

| Artifact | Path | SHA-256 | Status |
|---|---|---|---|
| Draft evidence module (byte-identical copy of the prior session's scratchpad file) | `experiments/pi_harness_cfg1/tests/unvalidated_f5a_fu4_a2_native_relative_creation.py` | `2952d2f036eeb148a1bdc2f9d38c79db213e28ccd634d92b3ca99b84d512de42` | **NOT VALIDATED.** 49,036 bytes. Last modified 2026-10-09 17:45 in the scratchpad. |
| Prior-run report (byte-identical copy) | `experiments/pi_harness_cfg1/evidence/f5a_fu4_a2_prior_run_report_UNRECONCILED.json` | `dac860f5595cc570cff601c7d0812462d51e6a4fdc5dc692d2cfd89f6b400a51` | **Unreconciled** with the draft's final revision and with [NARR] (§3). 35,869 bytes. Last modified 17:44, **one minute before** the draft's last edit. |

- The draft was **not edited** during preservation, so the hash above is the
  hash of what the prior session left. Its filename deliberately does **not**
  match `test_*.py`, so default `pytest` collection of the directory will not
  collect it. A reviewer who authorizes a run passes the path explicitly.
- It imports `cfg1_win_probe`, `test_cfg1_f5a_r1_windows_premises` and
  `test_cfg1_f5a_windows_handle_probes` from the same directory. Those helpers
  exist (`_empty_it`, `_make_run_root`, `_Outside`, `_enumerate_once`,
  `_attempt_conversion`, `_tag_info`, `_handle_identity`, `BLOCKING_ERRORS`,
  `_symlink_reparse_buffer`, `_generic_reparse_buffer`, `FSCTL_SET_REPARSE_POINT`,
  `set_mount_point_reparse`, `inspect_no_follow`) **[SRC]**. Syntax was checked by
  parsing only.
- Three scratch exploration scripts (`a2_explore*.py`) exist only in the prior
  session's scratchpad. They are **not** preserved: they were throwaway probes,
  their outputs were not saved, and nothing in this report depends on them.
  Whatever they printed is therefore represented only by **[NARR]**.

## 3. A provenance conflict that is NOT resolved

| Source | What it says about A2-3 |
|---|---|
| Task statement and **[NARR]** | A2-3 "ended in a fixture error, not a pass or fail." The module "ran once." |
| **[JSON]** | `A2_3...` status **PASS**, 12 of 18 scenarios converted, `cases_not_run: []`, and the only FAIL in the file is A2-2. |

These cannot both describe one clean run of one revision. The report is
produced by `test_zz_rollup_and_report` only when the case results are
registered, and a case body that raised before `_finish` would appear in
`cases_not_run`, not as PASS **[SRC]**.

**One reading that fits both, offered as [INF] only:** the A2-3 test *body*
reached `_finish(..., "PASS")` and registered PASS in the in-memory results, and
the autouse `_no_leaked_handles` fixture then failed the test at **teardown**
(`assert not leaked`), which pytest reports as an ERROR of the test, not a
pass. That matches [NARR]'s own diagnosis ("a test-side handle leak") and
would explain a PASS in the JSON alongside a fixture failure. It is a
hypothesis about two artifacts; I could not read the run's output (the session
transcript tool exposes no tool output) and did not re-run it.

**Consequence, independent of which reading is right:** the JSON's A2-3 PASS
must not be read as validation. (a) pytest would count the test as errored, not
passed; (b) the JSON came from an earlier draft revision than the preserved
file; (c) the corrected revision was never run. **A2-3 stays INCOMPLETE.** No
evidence available to this task independently establishes the missing guarantee.

## 4. Case-by-case status (A2-1 … A2-8)

The suite is **not** labelled passing. "Recorded" means [JSON] recorded it on the
prior run of unknown revision; it does not mean the preserved file produces it.

| Case | Recorded in [JSON] | Source-backed status | Limits found in the draft's source ([SRC]) |
|---|---|---|---|
| **A2-1** directory child created relative to a held parent, identity-bearing handle | PASS, all three parent shapes. Parent enumeration lists the child with its handle's id; the child's own link record names the parent's file reference; a second `FILE_CREATE` returns `0xC0000035`; rename refused (Win32 32) while held, succeeds after release. | **OBSERVED on one run, one host.** Corroborated by [NARR]. | Parent-reference check uses the same helper the wrapper uses. No concurrent actor. |
| **A2-2** file child; occupied names refuse | **FAIL** recorded. Every observed status was an error: `0xC0000035` ×7 and `0xC00000BA` for a file create over a junction. No object appeared outside; zero bytes at create; a second actor's read open got Win32 32. | **ORIGINAL FAIL attributable to an over-restrictive expected-status rule, per [NARR]; the recorded values are consistent with that** (the one status that differs from `0xC0000035` is `0xC00000BA`). The corrected predicate is in the preserved draft; **correction not revalidated.** | The corrected predicate accepts any status with the error-severity bits `0xC0…`, so it would also accept an unrelated failure (e.g. access denied). It is looser than a named allow-set. Re-evaluating the corrected predicate on the recorded values by hand gives "true"; that is arithmetic on an old file, not a test run. |
| **A2-3** the FU3 case: converted held parent, relative create, matched controls | PASS recorded (but see §3). 18 scenarios = 3 pin shapes × 3 tags × 2 open masks; **12 converted**, 6 not (all six: `GENERIC_WRITE` against a share-READ pin, open refused, Win32 32). Every converted scenario: `0xC0000280` for mount-point and symlink tags, `0xC0000279` for tag `0x8000FFFF`, no handle returned, nothing created inside or outside. Pathname matched controls (mount-point, symlink tag): `CreateDirectoryW` and `CreateFileW(CREATE_NEW)` both succeeded and `pi_runtime`, `zero.bin` appeared **outside**. Unconverted matched controls: both relative creates succeeded on all three shapes. | **INCOMPLETE — fixture failure; corrected draft not revalidated.** | Only the **first** create into an emptied, already-converted parent is exercised; no conversion *racing* a create. The generic-tag pathname control was not run (only mount-point and symlink). The pass predicate checks the candidate's reason *prefix*, not the exact status. The final draft's A2-3 helpers appear to close every handle they open, but I could not identify what the earlier leak was, and "appears to" is not validation. |
| **A2-4** name forms | PASS recorded. Raw kernel call: `j\via_junction` (junction child) **created outside**; `..\dotdot`, `.`, `fwd/slash` → `0xC0000033`; `a:stream` → `0xC0000103`; absolute forms → `0xC000000D`; `trailingdot.` created (`0x0`) inside the root. The wrapper refused all eight before any call. | **OBSERVED. The escape is the load-bearing result:** a multi-component relative name resolved through a junction child lands outside. **A single-component restriction is therefore mandatory** for any A2 use. | Wrapper validator is a test-local reject-list. Not exercised: reserved device names, 8.3 short names, trailing space, over-length names, embedded NUL, Unicode normalization. This is a statement of what was not measured, not a new requirement. The trailing-dot object proves the kernel itself would accept a name Win32 cannot address, so the wrapper's refusal is policy, not kernel-derived. |
| **A2-5** fail-closed, no pathname fallback | PASS recorded. Four refusals, zero handles left open, zero pathname-API spy hits. Parent entries afterwards: `collide`, `proof`, `unexpected`. | **PARTIAL; NOT established as production fail-closed behavior.** See below. | (1) Of the four sub-cases only the **name collision** is a real kernel outcome; "export unavailable" (`resolver=lambda: None`), "success without `FILE_CREATED`" and "handle-proof failure" are driven by **test-only hooks inside the test-local wrapper**. They show the wrapper's own branches refuse, not that a real native anomaly is handled. (2) The pathname spies patch only `r1._W.CreateDirectoryW` and `q._K.CreateFileW`. The wrapper's source references neither, so the spies **cannot fire**; they are a consistency check, not independent evidence. `os.mkdir`, `Path.mkdir`, `open()` and this module's own `_K` are not spied. A direct source read of the wrapper finds no pathname-creation call, which is the stronger (and still static) basis. (3) A refusal after an unexpected success **leaves the object in the held parent** (visible in the entries above); only L27 removes it. |
| **A2-6** the same window one level down | PASS recorded. A created empty child converted attribute-only (`converted`, 0); later relative dir and file creates into it → `0xC0000280`; nothing outside. `GENERIC_WRITE` conversion of a sibling was refused (Win32 32). | **OBSERVED** (one run). The conversion itself is **not** prevented (no share mode governs attribute-only opens, consistent with R1-FU3); only the subsequent creates are refused. | The draft discards the return value of one `_pin(...)` call and relies on a close-every-tracked-handle loop; that hides the very leak the fixture exists to detect. Hygiene deviation, not a finding about the OS. |
| **A2-7** content stays in the object | PASS recorded. A zero-byte child converted to a symlink tag after creation: bytes written through the creating handle read back identical, identity unchanged, outside sentinel unchanged; the child handle *sees* the reparse attribute. | **OBSERVED** (one run). Detection only; the write was not redirected. | Read-back is through the creating handle, not by name. Nothing about a later by-name reader. |
| **A2-8** nested construction | PASS recorded. 19 gates, 432 files, peak 366 open handles, depth 11, one directory of 360 files + 2 dirs (362 entries), `NTFS`, nothing outside changed. | **OBSERVED for the reported synthetic shape ONLY.** | **Not the approved Pi payload** and not the §7.4A.6 inventory. The gate count (19) is hard-coded; the observed peak (366) is recorded but **not asserted against the 462 bound** in §7.4A.6. No claim about the real payload is made. |

**Totals as recorded in [JSON]:** 7 PASS, 1 FAIL (A2-2), 0 unsupported, verdict
`FAIL`, `closure_claimed: false`. **This is not "7 of 8 validated."** The file
is of unknown revision, A2-2's correction and A2-3's fix were never run, and
A2-5 is partly injected.

**Documentation base ([DOC]):** `NtCreateFile` is documented as accepting a name
relative to the directory in `RootDirectory`; `FILE_CREATE` errors if the name
exists; `NtCreateFile` "never returns `STATUS_REPARSE`." The page (dated
2025-01-23 as fetched; [NARR] said 2025-08-15) is a driver-reference page. It
says **nothing** about what happens when the `RootDirectory` object is itself a
reparse point, nor about concurrent reparse conversion. The `0xC0000280` /
`0xC0000279` refusals are **measured, not documented**, and their stability
across builds is unknown. The documentation alone does **not** prove
containment under concurrent conversion, and this report does not claim it does.

## 5. The recommended A2 mechanism (a conditional design candidate)

Conditional on the open items in §9, and **not** to be implemented in production
on the strength of this report:

1. Directory and file children are created **relative to an already
   authoritative parent handle**, with **exclusive creation** (`FILE_CREATE`)
   and the **identity-bearing handle returned by that same call**.
2. Every name is validated as **exactly one safe relative component** *before* any
   native call. This is not optional: A2-4 shows a multi-component name escapes
   through a junction child.
3. **No pathname-based creation fallback exists**, in any branch.
4. Any native-API failure — unavailable export, error status, success without
   "created", failed handle proof — **fails closed** (`RUNTIME_PROVISIONING_FAILED`
   at L3R), removing nothing, per the existing amendment.
5. Content continues to be written **only through independently verified
   creating handles**, preserving the existing provenance, digest verification,
   handle ledger, lifecycle and L27 cleanup rules.

Not claimed: that this is safe under *concurrent* reparse conversion. The
evidence is "after a conversion has completed, a create is refused." Whether a
conversion racing a create can ever slip through is **[INF]** only (NTFS
serialization of creates in a directory, and a non-empty directory refusing
conversion per W5) and was not measured.

## 6. R-ALIAS — recorded as a conflict, not resolved

**The reported observation ([JSON], supplemental, "feeds no verdict").** A hard
link to a held, share-0 child was created from outside the root; the link count
went 1 → 2; the handle's own link list showed both names; bytes later written
through the held handle read back through the outside name.

**The documentation ([DOC], `CreateHardLinkW` Remarks).** Sharing specified at
open operates per file: an application cannot create a new hard link to a file
that another open disallowed sharing for. (Paraphrased; see the URL below.)
Reference: <https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createhardlinkw>

**Source-only inspection of the draft's supplemental test ([SRC]):**

| Question | Finding |
|---|---|
| Is the operation `CreateHardLinkW`? | **Yes.** `_K.CreateHardLinkW(str(alias), str(root / "models.json"), None)` — new name first (outside directory), existing file second, parameter order matches the documented signature. |
| Was the child handle still held? | **Yes.** The handle from the native create is held across the call and closed in a `finally` afterwards. |
| Were the share-mode conditions the documented case? | Share mode on that handle was `0` (the file shape: `GENERIC_READ \| GENERIC_WRITE \| DELETE \| SYNCHRONIZE`, share 0). That share-0 was **really in force for data opens** is shown by A2-2, which uses the same create shape on a different object in the same recorded run: a second actor's read open got Win32 32. (The supplemental test itself does not assert it for its own object.) |
| Does the actor match "another application"? | **No — not literally.** The linking call runs in the **same process and thread** that holds the handle. The documentation sentence says "another application." Whether share-mode conflicts are evaluated differently for a same-process opener is **not** established here; ordinary NT share checks are per-open, not per-process **[INF]**. |

**What would reconcile it, and why none of it is concluded here.** A candidate
explanation **[INF]** is that `CreateHardLinkW` opens the existing file with an
attribute-only access, and R1-FU3 already measured that attribute-only opens
are not governed by any share mode (share 0 included). That would make the
observation and the documentation both literally true. But the access mask
`CreateHardLinkW` uses internally is undocumented and was **not measured**. The
other candidate explanations — the documentation sentence being narrower than
it reads, a build-specific behavior, or a defect in this fixture — are not
excluded either. **R-ALIAS therefore stays UNVERIFIED — CONFLICTING EVIDENCE.**
No new link-creation experiment was run, and none is requested by this report.
No link-count check is proposed as a security gate: its concurrency properties
were not established (a count read from a handle is a snapshot).

**Security impact, kept separate and unweakened:**

- **F5-A.** The payload being provisioned is **approved runtime bytes**. An
  adversary-created external alias of one of those files does not by itself show
  that AIDO created an external directory entry, nor that AIDO modified any
  unrelated pre-existing file. Nothing here changes INV-F5A-W as written. It
  does **not** by itself block F5-A, and this report does not dismiss it either:
  whether an external alias of approved runtime bytes matters to a reviewer is a
  reviewer decision.
- **L9.** The frozen model (§37.1) requires that **no endpoint-bearing byte is
  written outside CFG1's own owned, identity-proven disposable root**. A
  persistent external alias of a file that later holds endpoint-bearing content
  could violate that requirement. §37.1's disclaimer that confidentiality
  against a same-user process was never promised **does not answer this**:
  the requirement is about *where the bytes are written*, not about who can
  read them. **Not dismissed.** Also not established: this report does **not**
  claim any endpoint byte has escaped, and no such measurement exists.

Neither frozen invariant is broadened or weakened by this report.

## 7. Minimal F5-A correction candidate (§7.4A) — a proposal, not an amendment

Recorded in this separate, additive file because editing
`PHASE_5F3B_CFG1_F5A_LIVE_LAUNCH_AUTHORITY_AMENDMENT.md` would invalidate the
evidence binding U126 depends on.

**Why a correction is wanted.** §7.4A.3 argues a pathname create beneath the
pinned chain cannot escape, citing W3 (a held share-READ directory pin cannot be
converted in place). R1-FU3 (8343db1) measured that a `FILE_WRITE_ATTRIBUTES`-only
open converts an **empty** pinned directory under every share mode, after which
the pathname `CreateDirectoryW` / `CreateFileW(CREATE_NEW)` of §7.4A.2 land
outside the root **before any parentage gate runs**. W3 does not hold for
creation containment.

**Smallest change, if the reviewer accepts A2:**

- §7.4A.2 steps 1–2: replace "pathname `CreateFileW(CREATE_NEW)`" and
  "`CreateDirectoryW` then pin" with one handle-relative
  `NtCreateFile(RootDirectory = P_D, ONE component, FILE_CREATE,
  FILE_OPEN_REPARSE_POINT | FILE_SYNCHRONOUS_IO_NONALERT)` per child.
  Directory: list/read-attributes/synchronize, share READ; the returned handle
  **is** the pin `P_d`. File: `GENERIC_READ | GENERIC_WRITE | DELETE |
  SYNCHRONIZE`, share 0. Require `STATUS_SUCCESS` **and** "created", then prove
  kind and absence of a reparse attribute/tag **from the returned handle**.
- Names: exactly one safe component, before any call.
- Any native failure → `RUNTIME_PROVISIONING_FAILED`; no fallback; L3R removes
  nothing.
- §7.4A.3: re-base the containment argument on handle-relative resolution and
  withdraw W3 as the basis for *creation* containment.
- §7.4A.4: R-WINDOW does not arise for these creates (creation and first
  identity-bearing handle are one call). The reviewer should still decide
  whether to say so, since it rests on A2-1 only.

**Unchanged:** the A2-R1 topology, the approved payload, provisioning
provenance, verify-before-persist (§7.4B), the parentage checks including the
exact-set gate, the handle ledger, closed-before-L27, L27 cleanup, and the
refusal codes.

## 8. Separate potential L9 correction — a different finding

**Fact ([SRC]).** `cfg1_pi_config.py` creates the config directory by pathname
(`Path(config_dir_str).mkdir(parents=False, exist_ok=False)`, step 3), pins it
afterwards (step 4), then creates `settings.json` and `models.json` by pathname
(`win.create_exclusive_child`, step 6), and only then runs the handle-relative
parentage gate (step 7). Content is written after the gate (step 8).

**Status of the frozen guarantee.** The frozen design's W3 (§37.2: an in-place
conversion of a pinned directory is impossible) is the reason steps 4–6 were
accepted. The R1-FU3 measurement (commit 8343db1) shows that an **attribute-only** open
converts an **empty** pinned directory; A2-6 records the same for a directory
created by A2. The "post-pin W3 guarantee" is
therefore **invalidated for the zero-byte creation interval**.

**What this does and does not establish.**

- Established as a risk: step 6's pathname creates can be redirected before the
  gate.
- **Not established:** that L9's exact sequence has been shown to land
  zero-byte files outside the root; it was not run. The gate precedes step 8, so
  **no endpoint byte has been shown to escape**, and none is claimed to have.
- Combined with R-ALIAS (§6, unreconciled), it is a possible violation of the
  §37.1 "no endpoint-bearing byte outside the owned root" requirement, and is
  therefore a reviewer decision, not a dismissal.

**Smallest candidate, if authorized:** `Path.mkdir` + `acquire_config_pin`
becomes one handle-relative directory create from `root_pin`; pathname
`create_exclusive_child` becomes a handle-relative file create from the config
pin. Step 7 and everything after it are unchanged. One provenance-free low-level
primitive (parent handle, one name, kind) could serve both F5-A and L9 while
keeping their authority tokens separate; placing it in `win_config_authority.py`
needs its own reviewer decision. **Nothing in `cfg1_pi_config.py` or
`win_config_authority.py` was modified.**

## 9. Unresolved blockers

1. **A2-3** has no validated run of the corrected draft; the §3 conflict between
   [JSON] and [NARR] is unreconciled.
2. **A2-2**'s correction is unrun, and its predicate is looser than a named
   status set.
3. **A2-5** is partly injected and its no-fallback evidence is largely static.
4. **R-ALIAS** is UNVERIFIED — the documented sentence and the observation
   conflict, and the internal access mask of `CreateHardLinkW` is unmeasured.
5. **No racing-conversion measurement** exists; concurrency safety of the
   create is inference.
6. **Single host, single build** (Windows 10.0.26200, NTFS). Other builds,
   ReFS/Dev Drive, filter drivers, network paths unmeasured. The `0xC0000280`
   behavior is undocumented.
7. **A2-8** covers a synthetic shape only.
8. `ntdll!NtCreateFile` is documented on a driver-reference page; the
   stability of calling it from user mode across Windows versions was not
   assessed here.

## 10. The smallest remaining step for independent acceptance

**One authorization:** permission for the reviewer (or the user) to run **the
preserved draft, unmodified**, in a session where the safety classifier does not
block it, with `F5A_FU4_A2_REPORT_PATH` set to write a fresh report:

```bash
.venv/Scripts/python.exe -m pytest experiments/pi_harness_cfg1/tests/unvalidated_f5a_fu4_a2_native_relative_creation.py -q -s
```

That single run would settle, in one go: whether A2-3 passes with **no teardown
error** (§3), whether A2-2's corrected predicate passes, and whether the
revision hash `2952d2f0…` produces the recorded pattern. It would **not**
settle R-ALIAS, the racing-conversion question, or other builds. Those need
separate, explicitly scoped decisions.

Until that run exists and is reviewed, **the authoritative outcome is HOLD.**
