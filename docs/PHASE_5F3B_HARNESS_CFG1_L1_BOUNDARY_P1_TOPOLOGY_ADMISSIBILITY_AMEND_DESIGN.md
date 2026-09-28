# Phase 5F3B-HARNESS-CFG1-L1-BOUNDARY — P1 Candidate-Namespace Admissibility Correction (Design Amendment)

## 0. Reading rule and precedence

This is a **narrow, targeted** amendment to R6 Sec. 5 P1's `PATH`-entry walk
only. It is layered on top of, and does not edit:

- `PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md` ("R6") — **NOT EDITED**.
- `..._FU1_OC3_AMEND1_DESIGN.md` ("AMEND1") — **NOT EDITED**. AMEND1 Sec. 4
  states P1 is "preserved, unchanged" from R6; this document is the one
  explicit, narrow exception to that preservation, scoped to exactly the
  clause identified below.
- `..._FU1_Y6_AMEND2_DESIGN.md`, the OC-4 closure-totality design, and the
  OC-5 L3-baseline design — unrelated to `PATH` resolution; **NOT touched,
  NOT reopened**.

Where this document is silent, R6 + AMEND1 govern exactly as accepted.

## 1. The observed defect

The required read-only, static pre-A4 Pi identity proof (`prove_pi_identity`,
`experiments/pi_harness_cfg1/pi_identity.py`) failed on the real supported
Windows workstation with `PI_RESOLUTION_FAILED`, given the real `PATH`
topology:

- index 1: `C:\Program Files\Common Files\Oracle\Java\javapath` — a directory
  whose no-follow inspection classifies it `reparse_point` (unsafe);
- index 25: `C:\Program Files\nodejs` — safe; contains the intended
  `node.exe`;
- index 49: `C:\Users\<user>\AppData\Roaming\npm` — safe; contains the
  intended `pi.cmd`.

`_first_candidate()` (R6 Sec. 5 P1's implementation) walked `PATH` entries in
order and, on meeting the FIRST entry whose own directory topology could not
be proven safe by the no-follow walk, returned a refusal for the **entire**
search — not only for that one entry. Because index 1 is unrelated to both
Node and Pi and precedes both index 25 and index 49, both `_resolve_node` and
`_resolve_package_root` refused before ever inspecting index 25 or 49. This is
a supported-real-environment compatibility defect: an operator does not
control, and did not misconfigure, the presence of an unrelated vendor
`PATH` entry ahead of Node/npm's own entries, and no invariant this design
accepts requires that an unrelated inadmissible entry veto every later one.

## 2. Authorized semantic amendment

**R6 Sec. 5 P1's `PATH`-entry walk is amended, exactly as follows, and no
further:**

> A `PATH` entry whose directory topology cannot be proven safe by the
> existing no-follow walk (§7.2, unchanged) is **inadmissible** as a
> candidate namespace. For such an entry: it is never followed; it is never
> resolved through; nothing is ever executed from it; it is never used to
> derive the Node or Pi identity. The entire entry is **skipped**, and the
> search continues at the next `PATH` entry — exactly as a missing entry is
> already skipped today.
>
> P1 therefore selects the **first admissible** candidate, not necessarily
> the first candidate an untrusted/reparse namespace might otherwise cause a
> Windows shell name lookup to find.

This is safe only because, unchanged from R6/AMEND1: CFG1 never executes
Node or Pi by a bare `PATH`-resolved name. The accepted identity continues to
carry exact absolute paths (`node_executable`, `pi_cli_js`), and L14's
`launch()` continues to use exactly those proven absolute paths. **No bare
`node`, `pi`, `pi.cmd`, PATHEXT, shell, or PATH-based execution is
introduced by this amendment, at any stage.**

### 2.1 Fail-closed boundary that is explicitly NOT widened

This is **not** "skip anything suspicious." Once an **admissible** (safely
no-follow-walked) `PATH` directory is reached:

- if the exact `node.exe`/`pi.cmd` candidate is **absent**, the search
  continues to a later entry — unchanged from today;
- if the exact candidate **exists** but is a reparse point, a directory, a
  symlink-like object, `other`, or otherwise not the required regular file,
  the **whole search refuses outright** (`PI_RESOLUTION_FAILED`) — unchanged
  from today, and this amendment does **not** add a fallthrough to a later
  entry in this case.

After an admissible `pi.cmd` anchor is selected, the existing strict
package-root layout/topology rules (the two AR2 layouts, each walked
component-by-component with §7.2, `return None`/refuse outright on any unsafe
component) are **completely unchanged** — this amendment touches only the
outer `PATH`-entry admissibility walk in `_first_candidate`, never the
post-anchor package-root walk in `_resolve_package_root`.

The complete 20-file seam proof (P2), the P2R identity re-proof, and the L14
complete re-proof immediately before launch are **all unchanged**.

### 2.2 The child environment does not, and did not, forward ambient `PATH`

Separately from P1 itself: the CFG1 child environment
(`experiments/pi_harness_cfg1/environment.py`,
`build_cfg1_child_environment` / `_narrowed_path`) does not copy, filter, or
derive from ambient `PATH` at all. It constructs an entirely NEW, narrow
`PATH` for the launched child from exactly three sources — the directory of
the P-proven absolute `node_executable`, the directory of the resolved Git
executable, and `SystemRoot`/`SystemRoot\System32` — and nothing else. No
ambient `PATH` entry, admissible or inadmissible, skipped or selected, is
ever a source for the child's `PATH`. This was true before this amendment and
remains true unchanged after it: this amendment affects only which
directories P1 is willing to inspect for Node/Pi identity, and does not
change, and does not need to change, how the launch environment's `PATH` is
built. There is therefore no path by which a `PATH` entry P1 skipped as
inadmissible could be reintroduced into the child's runtime `PATH`.

## 3. Why a skipped, inadmissible namespace cannot regain execution authority

1. P1 never records *which* entries were skipped, and never retains a name
   or path resolved "through" an inadmissible entry — an inadmissible entry
   contributes nothing to the returned identity, exactly as a missing entry
   contributes nothing today.
2. `Cfg1PiIdentity` (§10, AMEND1) carries only the two exact, no-follow
   inspected, §7.2-identity-pinned absolute paths captured from the
   admissible entry that won. It is constructible only by a passing P
   (`_P_ONLY` sentinel), immutable, and never re-derived from `PATH` again.
3. L14's `reprove_pi_identity_for_launch` re-walks and re-classifies exactly
   those two absolute paths — never `PATH`, never a bare name, never the
   skipped entry — immediately before `launch()`.
4. `ar2.launch.build_pi_argv` (frozen; Test AG) reads exactly
   `node_executable` and `pi_cli_js` off that object and nothing else.
5. Therefore an inadmissible namespace skipped at P1 has no path back into
   argv, launch, or any later stage: it is removed from consideration
   entirely, not merely deprioritized, and nothing downstream ever
   re-consults `PATH` or that entry's lexical name again.

**On PATH shadowing.** Skipping an inadmissible entry does not change which
directory's candidate is authoritative when multiple *admissible* entries
hold a candidate: the first admissible entry (in `PATH` order) with a
regular-file candidate still wins, or an admissible entry with an invalid
candidate object still refuses the whole search outright, exactly as before.
An inadmissible entry cannot win that race for or against a later entry — it
was never a participant, the same as a `missing` entry already is not.

## 4. Distinguishing the three post-anchor cases (unchanged partition)

This amendment touches exactly one of these three, already-separated cases,
and leaves the other two exactly as accepted:

| Case | Where | Behavior |
|---|---|---|
| An unrelated/unprovable `PATH` entry, before any admissible candidate | `_first_candidate`'s outer `_walk_directories(entry)` | **Amended**: skip the entry, continue to the next |
| A safely walked directory with an invalid candidate object (`node.exe`/`pi.cmd` present but not a regular file) | `_first_candidate`'s candidate `_observe` | **Unchanged**: refuse the whole search outright, no fallthrough |
| A safely selected `pi.cmd` anchor whose package-root topology is later unsafe | `_resolve_package_root`'s `_walk_directories(layout)` | **Unchanged**: refuse the whole search outright, no fallthrough |

## 5. Implementation

The correction is confined to `_first_candidate()` in
`experiments/pi_harness_cfg1/pi_identity.py`: the outer-entry branch that
previously read `if status == _WALK_UNSAFE: return None` now treats
`_WALK_UNSAFE` exactly like `_WALK_MISSING` — `continue` to the next entry.
No other function changed. `_resolve_node`, `_resolve_package_root`'s layout
walk, `_complete_seam_set_matches`, `_identity_still_holds`,
`reprove_pi_identity_for_launch`, the pre-consumption gate, and every
containment/outside-checkout check are untouched.

## 6. Regression coverage added

`experiments/pi_harness_cfg1/tests/test_cfg1_fu1_static_identity.py` gained a
new adversarial section (Test AH) proving, over synthetic Pi trees under
`tmp_path` only:

1. An unrelated synthetic junction/reparse `PATH` entry placed before valid
   Node and Pi directories is skipped without being followed, and the
   complete static proof (identity + all 20 seams) passes.
2. No `realpath`, digest, or further inspection reaches anything *under* the
   skipped inadmissible namespace. The inadmissible entry itself IS
   classified (topology-inspected) — that classification is exactly how its
   inadmissibility is established — but never more than once per independent
   `PATH` walk: `_resolve_node` and `_resolve_package_root` each walk
   `entries` from scratch (pre-existing "first candidate only" discipline,
   unaffected by this amendment), so a run that resolves both Node and Pi
   classifies a shared leading inadmissible entry exactly twice, never once
   and never more. Nothing beneath it is ever touched either way.
3. A safely walked `PATH` directory containing an invalid/reparse
   `node.exe` still refuses the whole search outright and does not fall
   through to a later, otherwise-valid Node directory.
4. A safely walked `PATH` directory containing an invalid/reparse/directory
   `pi.cmd` still refuses the whole search outright and does not fall
   through to a later, otherwise-valid Pi directory.
5. Multiple inadmissible entries (one before Node's entry only, one before
   Pi's entry only, and both together) are all skipped and the proof still
   passes.
6. A repo-local candidate directory remains refused by containment even when
   it is not itself a reparse point (pre-existing Test J coverage,
   unaffected, re-verified).
7. No `PATHEXT` behavior exists anywhere in the module (pre-existing static
   and dynamic coverage, re-verified).

**Two pre-existing Test J cases were RENAMED and their comments corrected**,
because their original names/comments were written under the superseded rule
that any unsafe `PATH` entry vetoed the whole search — under the amended
semantics that framing is no longer accurate, even though neither test's
assertions changed in strength:

- `test_j_a_junction_path_entry_is_refused_before_realpath` →
  `test_j_a_junction_path_entry_is_skipped_and_never_followed_or_realpathd`.
  The junction is now demonstrably SKIPPED (the search mechanically continues
  and inspects the surviving entry's `node.exe` candidate), not itself a
  cause of the refusal; the refusal comes from that surviving entry
  genuinely lacking `node.exe`. The pre-existing proof that the junction is
  never `realpath`'d is unchanged and unweakened.
- `test_j_a_repo_local_lexical_junction_resolving_outside_is_still_refused` →
  `test_j_repo_local_candidates_are_refused_by_skip_or_by_containment`. This
  test exercises two DIFFERENT mechanisms that its original single name
  conflated: (a) a reparse junction inside the checkout, which is now
  refused by the same skip-and-continue path as the test above (never by a
  containment check on the junction itself, since an inadmissible namespace
  never reaches that check); (b) a plain, non-reparse repo-local directory,
  which IS admissible topology and is refused by the unchanged containment
  check — exactly as before, unaffected by this amendment.

In both renamed tests, the surviving `PATH` entry after the
inadmissible/junction entry does not itself contain the sought binary (the
synthetic tree's `node_dir` holds only `node.exe`, and `npm_dir` holds only
`pi.cmd`), which is why `PI_RESOLUTION_FAILED` is still the correct outcome
under the amended semantics — now proven by construction rather than merely
asserted by final code.

## 7. Invariants explicitly preserved (unchanged by this amendment)

- P reads exactly ambient `PATH`, by name.
- No `PATHEXT` expansion.
- No Node/Pi/JavaScript execution during P.
- `pi.cmd` is never read or executed.
- No process creation in P.
- No credential or endpoint reads in P.
- No filesystem writes in P.
- No network authority is added.
- No reparse point is followed, at any point.
- Node and Pi roots inside the AIDO checkout remain refused.
- Exact filesystem identities (§7.2) remain required.
- All 20 pinned seams remain required, unchanged, for the qualification
  chain currently frozen at Pi Coding Agent 0.85.1.
- L14's complete re-proof immediately before launch is unchanged.
- Malformed types / Python truthiness remain fail-closed throughout.
- OC-3 is closed by AMEND1; **OC-4 and OC-5 each remain CLOSED/FROZEN**,
  exactly as accepted by their own designs; A4 remains **NO-GO**. This
  document reopens none of them and discharges none of them.

**On Pi 0.85.1 and future Harness versions.** Pi Coding Agent 0.85.1 is
**only the currently frozen historical qualification target** for this
already-accepted chain — the specific version this 20-file seam table and
`package.json` pin were reviewed and frozen against. This document must not
be read as stating, and does not state, that AIDO **permanently** locks the
Harness/Pi version: it makes no version-adoption decision of any kind, for
0.85.1 or any other version. Qualifying and adopting a different Harness
version — replacing the pinned seam table, the pinned `package.json` digest,
or the version this qualification chain targets — is **out of scope here**
and remains a **separate, later qualification/evolution phase**, exactly as
already stated outside this document (see `CLAUDE.md`'s "Current phase":
*"A separate later phase will replace permanent version pinning with
qualified Harness-version/profile adoption"*). This amendment neither
advances nor blocks that separate phase; it corrects a `PATH`-resolution
compatibility defect only, for whichever version is currently pinned.

## 8. Adversarial counterexamples checked against the corrected implementation

- Multiple unsafe `PATH` entries (before Node only; before Pi only; before
  both) — all skipped; resolution still finds the genuine candidates when
  present, and still fails closed on the true failure mode when injected.
- Duplicate candidates across two admissible entries — the first admissible
  entry with a valid candidate still wins; a later one is never consulted
  (pre-existing "first candidate only" behavior, unaffected).
- A safe directory holding a reparse-point candidate — refuses outright, no
  fallthrough (Section 4, case 2).
- A safe candidate followed by a later, also-valid candidate — the first
  found is authoritative; the later one is never reached (pre-existing
  behavior, unaffected).
- A package-root reparse encountered after a valid `pi.cmd` anchor —
  refuses outright via `_resolve_package_root`'s own unchanged
  `_walk_directories` call (Section 4, case 3).
- Repo-local paths — a junction/reparse namespace inside the checkout remains
  inadmissible and is skipped without being followed or used; a plain
  non-reparse repo-local candidate remains refused by the unchanged
  containment check (pre-existing Tests J).
- Malformed `PATH` values (absent, wrong type, relative/rooted-without-drive
  entries, device-namespace entries) — all remain refused or lexically
  skipped exactly as before; this amendment does not touch `_path_entries`
  or `_plain_absolute_entry`.
- Post-P1 filesystem mutation — remains caught by P2/P2R (seam proof and
  identity re-proof), and independently by L14's own complete re-proof
  immediately before `launch()`; this amendment does not touch either.

No boundary bypass was found. No fix beyond Section 5 was required.

## 9. Remaining blockers (unaffected by this document)

Unchanged from AMEND1 Sec. 19, items 1–7: this document does not discharge,
reopen, or reorder any of them. It removes exactly one supported-environment
compatibility defect that was mechanically blocking item 6 (the read-only,
static pre-A4 identity/seam verification) on the real workstation `PATH`
topology described in Section 1. A4 remains NO-GO pending a separately
reviewed and accepted authorization.

---

## Status

```text
5F3B-HARNESS-CFG1-L1-BOUNDARY-P1-TOPOLOGY-ADMISSIBILITY-AMEND   IMPLEMENTED
Base: FU1-DESIGN-R6 (ACCEPTED/FROZEN) — NOT EDITED
Base: FU1-OC3-AMEND1-DESIGN (ACCEPTED) — NOT EDITED
Scope: _first_candidate()'s outer PATH-entry admissibility walk ONLY
Change: an inadmissible (unsafe-topology) PATH entry is now SKIPPED, not a
        whole-search veto — exactly like a missing entry already is
Unchanged: candidate-object validity check (still refuses outright, no
           fallthrough); package-root layout walk; P2; P2R; L14 re-proof;
           containment/outside-checkout refusal; no PATHEXT; no bare-name
           execution anywhere; OC-3/OC-4/OC-5/A4 status
```
