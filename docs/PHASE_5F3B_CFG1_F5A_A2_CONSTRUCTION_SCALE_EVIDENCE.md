# Phase 5F3B-CFG1-F5A — A2 Construction-Scale Evidence (safe subset)

```text
STATUS         NON-FROZEN, ADDITIVE evidence report. Amends nothing.
F5-A           NOT ACCEPTED, NOT FROZEN. HOLD (unchanged).
A2             NOT security-qualified. A2-3 INCOMPLETE. R-ALIAS UNRESOLVED.
LIVE LAUNCH    UNAUTHORIZED. No live Pi, Node, model, backend or credential touched.
BASE HEAD      a56a182f6eb53ebf74c2cd1c492bf6500abd9f6f   (tree clean at start)
PLATFORM       Windows 11 10.0.26200, NTFS (C:), Python 3.14.7, pytest 9.1.1
CHANGED        experiments/pi_harness_cfg1/tests/test_cfg1_f5a_a2_construction_scale.py (new)
               docs/PHASE_5F3B_CFG1_F5A_A2_CONSTRUCTION_SCALE_EVIDENCE.md (this file)
NOT CHANGED    pi_runtime_provision.py or any other production module; any frozen
               contract; CLAUDE.md; the live-launch barriers; L9; U126.
```

This report is **ordinary regression evidence about construction scale**. It is
**not** proof of containment beneath a converted parent and must never be cited
as such. No reparse point, junction, symlink, hard link or conversion was created,
and nothing was raced; every object is an ordinary directory or file inside an
owned disposable fixture.

## 1. What was run

```text
.venv/Scripts/python.exe -m pytest experiments/pi_harness_cfg1/tests/test_cfg1_f5a_a2_construction_scale.py -v -rP
  -> 10 passed in 546.66 s          (final run, on the committed test file)
```

An earlier full run of the same module had 1 failure — an assertion of mine,
`fetches >= 3` for the 362-entry directory, which was **my wrong assumption, not a
candidate defect**: the committed geometry's widest enumeration fits one 64 KiB
buffer (§4, row 2). The assertion was corrected to the measured value and a
separate long-name case was added to force the multi-buffer path. Two hand-derived
peak literals (444, 29) were also wrong by exactly the pin of the directory being
built; the ledger, OS and independent calculation all said 445 / 30 and the
literals were corrected (§3). No other test was weakened.

Regression around it (production code is unchanged, so this is a sweep check, not a
re-qualification): `test_cfg1_t_coverage`, `_composition`, `_stage_decision`,
`_adversarial`, `_f5a_executor_integration`, `_f5a_a2_offline_candidate`,
`_impl_fu1_findings`, `_fu1_authority_surface` → **313 passed, 4 skipped** (the four
pre-existing "not an adversarial case" skips), 0 failed.

**Not executed:** the full ~15-minute CFG1 suite (no production change);
`test_cfg1_f5a_windows_handle_probes.py` and `test_cfg1_f5a_r1_windows_premises.py`
(they create junctions / convert directories); the preserved FU4-A2 draft; the 16
installed-Pi/Node `test_cfg1_pi_conformance.py` tests.

Runtime: the module takes ~9 min (≈16.5k real creates; ~60 s fixture build, ~220 s
for the end-to-end case). Selection for a quick run:
`-k "not end_to_end and not close_failure and not foreign_name"`.

## 2. Provenance of every synthetic authority object

| Object | Origin | Consumed by |
|---|---|---|
| Run workspace / run root / root identity | `mint_cfg1_run_workspace` — the real frozen creator, a real Git repo, a real `CFG1-T1` tree | `_consume_authority` (admission and again before the first create) |
| Profile + inventory approval | Genuine PE-2b load of a **synthetic** sealed policy (`install_synthetic_policy`), approving the fixture's own payload; the committed profile is never used for writing | `_consume_authority` fingerprint equality |
| Source tree | Written by the test under pytest `tmp_path_factory`; **geometry from the committed inventory file, content synthetic** (tiny, plus one file at the committed 11,694,592-byte size, seeded bytes) | `observe_payload`, `_read_verified_source` (verify-before-persist) |
| Launch-derivation row | `install_synthetic_ldt_rows` (existing helper; the genuine row untouched) | `admit_runtime_provision` |
| Probe / spies | Pass-through wrappers; each calls the REAL function and returns its result unchanged | — |

The **only** injected seam is `_close_raw_handle` returning `False` for one named
object (the two close-failure cases). It shows the candidate's branches refuse and
keep truthful lifecycle state; it is not a native anomaly.

## 3. Geometry and measured peaks

Committed inventory (recomputed by test code that does **not** call the candidate):

| Quantity | Frozen | Committed (recomputed) | Fixture (re-measured from disk) |
|---|---|---|---|
| directories / files | 1 436 / — | 1 436 / 15 046 | 1 436 / 15 046 (per-directory counts and directory order **equal**) |
| max depth below `C` | 11 | 11 | 11 |
| max file children / dir children / entries in one directory | 360 / 80 / 362 | 360 / 80 / 362 | 360 / 80 / 362 |
| handle bound | 462 | — | — |

Handle peak on the committed shape (1 438 directories created incl. `RT` and `C`,
15 046 files, 16 485 ledger entries):

| Source | Peak |
|---|---|
| Independent recomputation from the committed inventory | **449** |
| `construction_handle_peak` (candidate's simulation) | 449 |
| Candidate ledger `peak_open`, observed | **449** |
| **Process handle count from the OS** (`GetProcessHandleCount`), max over 16 484 samples | **449** |
| Frozen bound | 462 (slack 13; 462 is a bound, never a measurement) |

The OS delta equalled the ledger's open count after **every one** of the 16 484
real creates (not only at the peak). The peak occurs at the gate of
`node_modules/@earendil-works/pi-ai/dist/providers` (362 entries) with 449
handles open — nested ancestry, 360 file pins, and the pending `node_modules`
sibling pins together. After the run the OS count was exactly baseline + 4 (the
four final pins) and returned to baseline after L27 release.

Shaped payloads (peaks derived by hand **and** compared with the four observations):
360 files + 80 dirs in one directory → **445** (3 + `node_modules` + `zz_wide` +
440); depth 11 with two pending sibling pins at each of 8 levels → **30**. Both
matched the ledger, the OS count and the independent calculation. (First-draft
literals 444 / 29 omitted the pin of the directory being built; corrected, and
recorded here because it is precisely the accounting error these tests exist to catch.)

## 4. Properties — PASS / FAIL / NOT RUN

| # | Property | Result | Observation |
|---|---|---|---|
| 1 | Exclusive handle-relative creation of dirs and files | **PASS** | 1 438 dirs + 15 046 files created; production requires `STATUS_SUCCESS` + `FILE_CREATED`; per-directory created-name sets equal the committed inventory's. Collision refusal remains covered by the existing `primitive` tests (not repeated at scale). |
| 2 | Returned-handle identity and parent-enumeration correspondence | **PASS** | Every created object's handle identity equals `os.stat` of its path (16 484 objects). Every gate's single enumeration returned exactly `.` + `..` + the created names (`entries_seen == n+2`, all 1 437 inventory-directory gates). **Widest enumeration = 364 entries in 2 kernel fetches (one buffer + terminator): the multi-buffer continuation is not reached at committed scale**; a separate case (300 × 100-char names, ≥ 3 fetches) forces it and passes. |
| 3 | One complete exact-set gate before any content write, per directory | **PASS** | 1 438 gates, one per directory, each enumeration real (count equals gates + 1 membership gate); 0 writes before the parent's gate; 15 046 writes. Non-vacuity: a stand-in gate that never enumerates is detected by the same accounting; the real gate refuses a planted name in the 362-entry directory (with 440+ handles open). |
| 4 | Byte identity and digest read-back | **PASS** | All 15 046 destination files equal the test's own expected bytes; no extra entries; 1 436 dirs; post-copy `observe_payload` fingerprint equals the source's; 15 046 read-backs; includes the 11 694 592-byte multi-chunk file. |
| 5 | Bounded actual peak handles, nested and sibling fan-out | **PASS** | §3. 449 ≤ 462; shaped peaks 445 / 30. |
| 6 | Children-before-parents release | **PASS** | Zero ordering violations in the full run, the mid-tree refusal (hundreds of handles) and both close-failure runs; zero file handles held across a descent. |
| 7 | Complete release, success and controlled failure | **PASS** | OS handle count back to baseline after success+L27 release, after a gate refusal at the pit, and after each close-failure case (exactly one leaked handle until the harness freed it). |
| 8 | Refusal and derived lifecycle truth under injected close failures | **PASS** | Failure on a file in the widest directory and on the deepest directory: `CONSTRUCTION_HANDLE_NOT_CLOSED`, one attempt (no retry, none at release), ledger = exactly 1 `CLOSE_FAILED` / 0 `OPEN` / rest `CLOSED`, `live_references_released` and `provision_live_references_proven_released` both `False`. |
| 9 | Teardown strictness | **PASS** | Workspace removal is performed (and asserted) inside the end-to-end test body; the fixture finaliser fails the test on any removal failure and on a surviving tree; the source fixture removes strictly. Nothing is swallowed. |

Longest destination path observed: 224 characters (run root 61 characters). A
deeper run root would approach MAX_PATH-dependent pathname steps (source reads,
final pins, post-pin walk); that environmental dimension was not varied.

## 5. Adversarial review of these tests and of the candidate (self)

| Question | Finding |
|---|---|
| Test that passes without the intended gate? | Closed: enumeration count equals gate count; a no-op gate is detected by a dedicated test; the planted-name refusal comes from the real gate (`PARENTAGE_GATE_FAILED`, with the hook proven to have fired at the 362-entry directory). |
| Calculated peak never compared with observed? | The old candidate test compared simulation to ledger only. Now four independent sources are compared, per create, plus the committed-inventory recomputation. |
| Sibling-pin / nesting accounting wrong? | My own hand literals were wrong twice (+1); the observations were right, so the literals were corrected — not the assertions loosened. The candidate's accounting held. |
| Partial failure leaving misleading success evidence? | Failure cases assert the ledger's own states and the OS count, not only the injected seam. `live_references_released` reads `False` for a `CLOSE_FAILED` entry and stays so. |
| Fixture teardown invalidating a pass? | New module: strict (above). **Observation, not changed (out of scope):** `test_cfg1_f5a_a2_offline_candidate.py::_remove_workspace` swallows removal errors, so a leaked tree there would not fail its test. |
| Assertions derived from injected values? | Expected sets come from the committed inventory or independent code; the only injected value is the close-failure victim, whose *consequences* are what is asserted. |
| Candidate defect at scale? | **None found.** No change to production code was warranted. |

## 6. Historical P-R1-4 versus A2

P-R1-4 (amendment §14; recorded in `f5a_p_r1_windows_premises_report.json`, 9/9
cases PASS under the **pathname** shape, while the same report's R1-FU3
disposition is `FAIL` / `HOLD`) required, for the construction shape: (i) child
directory create + same-shape pin, (ii) up to 360 share-0 zero-byte children
held with up to 80 child-directory pins, (iii) one single-pass enumeration with
file ids equal to each handle's, (iv) rename/delete/in-place junction conversion
of the pinned directories refused, (v) content through held child handles after
the gate.

| Part | Status under A2 | Evidence here |
|---|---|---|
| (i) create + pin | **Superseded as worded** (`CreateDirectoryW` then pin): A2 creates and pins in one `NtCreateFile`, so there is no create-then-pin interval. The *property* (child is a real directory, pinned, nested grandchild pinnable) is **covered** | PASS, depth 11, all dirs |
| (ii) 360 + 80 fan-out held together | **Applicable, scale subset** | PASS: 360 + 80 simultaneously (445 handles); committed shape 449. Original "`CREATE_NEW` pathname `CreateFileW`" wording superseded |
| (ii) other handle cannot read/write/delete a share-0 child; occupied name refused | Applicable in kind; **NOT RUN here** (not in this phase's enumerated list; exclusivity of creation is covered only by the small-scale `primitive` test) | — |
| (iii) enumeration + file-id correspondence | **Applicable** | PASS at scale (§4 row 2) |
| (iv) rename / delete refused | Applicable to native pins; **NOT RUN** (candidate doc §6 item 5 still open) | — |
| (iv) in-place junction conversion refused | **Empirically unresolved and disproven in its pathname form**: R1-FU3 showed an attribute-only open converts an *empty* pinned directory; W3 must not be reused | **NOT RUN, deliberately** |
| (v) content through held child handles after the gate | **Applicable** | PASS (0 writes before gate, 15 046 through creating handles) |

**P-R1-4 is not marked PASS.** An A2-specific acceptance amendment would need to
state: (a) the creation primitive is `NtCreateFile(RootDirectory, one component,
FILE_CREATE)` with the §1 access/share/option shapes of the candidate document;
(b) construction scale: depth 11, 360/80/362, peak ≤ 462 *measured by ledger and
OS* on the approved shape (this report, synthetic content); (c) native-pin
rename/delete refusals; (d) **no** claim of conversion refusal — replaced by the
explicit A2-3/A2-6 outcomes (create beneath a converted parent, racing conversion),
which stay unmeasured; (e) which of the 8.3/Unicode/long-path dimensions are
claimed. This report does not edit §14.

## 7. Remaining gaps

* **A2-3** INCOMPLETE; **A2-2** corrected predicate unrun; no racing-conversion
  measurement; no create beneath a converted parent; candidate-on-target-platform
  under those scenarios unrun.
* **R-ALIAS** unresolved; hard-link behaviour untouched.
* Native-pin rename/delete refusals and share-0 exclusivity at scale: NOT RUN.
* Content scale: total 123 MB not reproduced (one 11.7 MB file only); long run
  roots / MAX_PATH variants, 8.3 aliases, ReFS/Dev Drive, other builds, filter
  drivers: not varied. One host, one build.
* Synthetic payload passes the approvability floor but is not the real Pi payload;
  no real runtime was read.

## 8. Barriers

No production module was modified; `live_runtime_provisioning_not_qualified` and the
unconditional supervisor-builder refusal are byte-identical to `a56a182`, and the
regression sweep above (executor integration, adversarial, authority surface)
passes. Nothing here lifts either barrier or authorizes a launch.

## 9. Smallest remaining independent-review decision

Whether to authorize **one** narrowly scoped, ordinary (non-reparse) step: the
native-pin rename/delete and share-0 exclusivity refusals on this candidate's own
creates (P-R1-4 (ii)/(iv) minus conversion), recorded against the A2-specific
acceptance wording of §6. The conversion-dependent premises (A2-3 run, A2-6,
racing conversion) remain the separate, blocking security decision.
