# Phase 5F3B-CFG1-F5A — A2 Offline Implementation Candidate

```text
STATUS            NON-FROZEN, ADDITIVE. An OFFLINE implementation candidate.
F5-A              NOT ACCEPTED, NOT FROZEN. HOLD for live authorization (unchanged).
A2                APPROVED AS THE IMPLEMENTATION DIRECTION (reviewer, after 09d62e5).
                  NOT security-qualified.
A2-3              INCOMPLETE (unchanged): fixture-teardown conflict, corrected draft
                  never validated. Nothing here clears it.
R-ALIAS           UNRESOLVED (unchanged). A2 does not solve hard-link aliasing.
LIVE LAUNCH       UNAUTHORIZED. No executor wiring, no L3R step, no launch path.
BASE HEAD         09d62e5d1cd0c550b0f7979cdfb28fb423db51a4
CODE              experiments/pi_harness_cfg1/pi_runtime_provision.py            (new)
TESTS             experiments/pi_harness_cfg1/tests/test_cfg1_f5a_a2_offline_candidate.py (new)
DOES NOT TOUCH    CLAUDE.md; the F5-A amendment (so the U126 evidence binding is
                  unaffected); U126 / P-R1 / FU3 / FU4-A2 evidence; the preserved
                  A2 draft and its UNRECONCILED JSON; win_config_authority.py;
                  cfg1_pi_config.py (L9); run_executor.py; records.py; lifecycle.py;
                  pi_identity.py; any frozen contract.
```

This document records a forward-looking correction to **one mechanism** of the
F5-A amendment and the offline code that implements it. It amends nothing. Where
it and the amendment differ, the amendment remains the reviewed text and this is
a proposal on top of it.

---

## 1. The correction, stated exactly

**Defective mechanism (amendment §7.4A.2 steps 1–2).** Pathname
`CreateDirectoryW` followed by a pathname pin, and pathname
`CreateFileW(CREATE_NEW | FILE_FLAG_OPEN_REPARSE_POINT)`. §7.4A.3 argued these
cannot escape `R` because a held share-READ directory pin cannot be converted in
place (W3). R1-FU3 (8343db1) measured that a `FILE_WRITE_ATTRIBUTES`-only open
converts an **empty** pinned directory into a junction under every share mode;
the next pathname create then resolves through it and lands **outside** `R`,
before any parentage gate. W3 does not hold for creation containment.

**Replacement.** One handle-relative native create per child:

```text
NtCreateFile(&h, access, OBJECT_ATTRIBUTES{ RootDirectory = <held parent handle>,
                                            ObjectName    = <ONE component>,
                                            Attributes    = OBJ_CASE_INSENSITIVE },
             &iosb, NULL, FILE_ATTRIBUTE_NORMAL, share, FILE_CREATE,
             options | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT, NULL, 0)
require  status == STATUS_SUCCESS  AND  iosb.Information == FILE_CREATED
```

| Child | access | share | options | The returned handle is |
|---|---|---|---|---|
| directory | `FILE_LIST_DIRECTORY \| FILE_READ_ATTRIBUTES \| SYNCHRONIZE` | `FILE_SHARE_READ` | `FILE_DIRECTORY_FILE` | the directory's construction pin `P_d` — there is **no create-then-pin interval** |
| file | `GENERIC_READ \| GENERIC_WRITE \| DELETE \| SYNCHRONIZE` | `0` | `FILE_NON_DIRECTORY_FILE` | the creating handle `h_f`, the only route for its content |

The directory shape is the one FU4-A2 measured (and the FU4 report §7 proposed),
not §7.4A.2's `GENERIC_READ`: both are read-only, share-READ directory opens. The
file shape is §7.4A.2 step 1's, unchanged.

**Everything else is the amendment's, unchanged:** the A2-R1 topology
(`R\pi_runtime\pi-coding-agent`, T-NM, T-CANON, T-PLAIN, T-BUN, T-RT), the LDT
(profile-id-keyed, fail-closed), the run-root pin and identity proof (§7.4A.1),
the `RT` membership gate and the exact-set gate per directory (§7.4A.2 step 3),
content only after the gate and only through `h_f`, verify-before-persist (§7.4B
shape A), the handle ledger and its two-state close machine (§7.4A.5), files
closed before recursion, the read-only final pins (§7.6), post-pin validation,
`live_references_released` as a derived latch (§7.8.1), and "L3R deletes
nothing".

**§7.4A.4 R-WINDOW consequence (proposal).** For these creates the
create-then-pin interval does not exist: creation and the first identity-bearing
handle are one call. R-WINDOW then remains only for the creator→pin interval of
the four final pins (§7.6, pre-authority, unchanged). This rests on A2-1 (one
host, one run) and is the reviewer's to accept.

## 2. What the candidate implements, and what it deliberately does not

**Implemented (in `pi_runtime_provision.py`, offline, standalone):**

| Amendment step | Function |
|---|---|
| §7.4 steps 1–2 (bind inputs, LDT, topology admission, no write) | `admit_runtime_provision` |
| step 3 write-ahead (ledgers exist before the first open) | `run_runtime_provision` |
| step 4 source observation (PI-PC1 walk, fingerprint equality) | `run_runtime_provision` |
| step 5 run-root authority (§7.4A.1) | `_pin_run_root` |
| step 6 construction (§7.4A.2 with the §1 replacement, §7.4B) | `_construct`, `_create_child`, `_gate_membership`, `_gate_exact_set`, `_read_verified_source`, `_write_verified_content` |
| step 7 final read-only pins (§7.6) | `_acquire_final_pins` |
| step 8 post-pin validation, items 1, 3, 4, 5 | `_post_pin_validation` |
| §7.4A.5 ledger; §7.8 L27-entry release; §7.8.1 derived fact for **this provision's** handles | `_HandleLedger`, `release_at_l27_entry`, `RuntimeProvision.live_references_released` |
| §7.4A.6 handle-peak accounting | `construction_handle_peak` (449 on the committed inventory; bound 462) |

**Not implemented — executor integration, deferred (needs its own authorization;
none of it is required to inspect the creation mechanism):**

- the `L3R` executor step and `provision_runtime` port (`run_executor.py`);
- v3 vocabulary `L3R` / `RUNTIME_PROVISIONING_FAILED` / R3-S15 (`records.py`,
  `lifecycle.py`) — this candidate only *names* the refusal code;
- step 8 item 2 (`observe_exposure_absence` against the matched profile's
  resolution exposures) — it needs the profile object;
- step 9 (`pi_identity` binding the launch identity `L`, dropping `S`);
- the L14 precondition and topology re-proof; the L21A input change;
- the **executor-level** `live_references_released` derivation (§7.8.1) and its
  L30 consequence. The candidate computes the fact for its own handles only;
- binding `approved_inventory` to `profile_id`. The candidate accepts the pair
  from its caller; in the executor it must come from the sealed HPP snapshot.

Because none of this is wired, the module has no caller in production code and
cannot launch anything.

## 3. Trust boundary — pre-implementation adversarial analysis

The authority being protected: *AIDO creates objects, and writes content, only
inside the run root `R` it minted and proved.* Inputs that are **not** trusted as
evidence of containment: every pathname (run root, source root, package root),
every caller-supplied object, and anything the payload or a model says.

| Threat | How the candidate prevents it | What it does NOT establish |
|---|---|---|
| Create through a substituted or converted directory | No create ever resolves a pathname: each is relative to the parent **object** held by a ledger handle. Parent rename/delete is refused while its pin is held (share without DELETE); a non-empty parent cannot be converted (W5). After a create, the **exact-set gate enumerates the held parent handle** and requires the child's own file id — so even if a create were ever redirected, the child is expected to be absent from the parent's own enumeration and the gate to refuse before any **content byte** (an inference, not a measurement). | That a create relative to an already-**converted** parent creates nothing anywhere. FU4-A2 recorded `0xC0000280`/`0xC0000279` for that case, but A2-3 is INCOMPLETE, undocumented by Microsoft, single-host, and no racing conversion was measured. The gate bounds *content*; it cannot un-create a zero-byte object that a hypothetical redirect placed outside. |
| Multi-component name escape (A2-4) | `require_single_component` (PI-PC1 segment grammar) runs **before** the native call: no `\`, `/`, `:`, control/NUL, lone surrogate, `.`/`..`, trailing dot/space, device stem, over-length. Tested: the native call is never reached. | Behaviour of names PI-PC1 accepts but that were never measured (8.3 alias collisions, Unicode normalization) — each can only collide (refuse) inside the same directory. |
| Arbitrary parent-handle injection | The only route from a parent to a raw handle is `_HandleLedger.raw_handle(entry, kind)`, which refuses a raw int, `None`, an entry of another ledger, a `CLOSED` entry or a file entry. Tested with each. | Same-process memory manipulation (monkeypatching, `ctypes` pokes), which is outside the CFG1 threat model, as everywhere else in CFG1. |
| Mismatched trusted objects | Child kind, reparse attribute/tag, volume serial and (file) zero length proven **from the returned handle**; parentage by file id in the parent's own enumeration; final pins require the id recorded from the creating handle; `I_c` and `RT` re-proven equal to their creating handles' ids. | — |
| Forged or transferred provisioning authority | `RuntimeProvision` / `_HandleLedger` constructible only with module-private keys; admission nonce consumed on the first run (a provision runs once; a copy cannot run); `copy`, `deepcopy`, `pickle` refuse; immutable from outside; not a `_MintBacked` subclass; refused by `require_production_issuance_provenance` and `require_extension_issuance_provenance`; the module imports nothing from `win_config_authority`, `config_issuance`, `extension_issuance`, `run_executor` or `cfg1_pi_config`. | — |
| Post-validation mutation invalidating consumption | Files are share 0 (no other data/delete open; rename needs DELETE); content goes only through `h_f`, is read back through the same rewound handle and digest-compared, then the handle is re-proven plain. Foreign names planted after a gate get no content and fail the post-pin PI-PC1 walk (fingerprint equality). | Attribute-only reparse conversion of a held file after its last check (Q2; inherited R-SLIVER/R-ABA, §8.6); hard-link aliasing (R-ALIAS). |
| Content before provenance verification | `_write_verified_content` refuses unless that child's `gate_passed` is set by its directory's gate and it has received no content; bytes are verified (size + SHA-256 over the exact buffer) before any write, so the hashed bytes are the written bytes. | Memory scrubbing (R-SRC-MEM, unchanged). |
| Cleanup of resources AIDO did not create | No delete, rename, truncate, disposition or delete-on-close call exists in the module (AST-audited). A refused create leaves the object in place for L27's frozen namespace teardown. | — |
| Leaked handles / false completion | Every handle is entered in a ledger **before any check** that can fail; `CloseHandle` only from `OPEN`, once; `CLOSE_FAILED` terminal; `close_all` on every exit, reverse acquisition order (children before directories); state `PROVEN` only after post-pin validation; `package_root_identity` unavailable otherwise; `live_references_released` is `False` while any entry is `OPEN` or `CLOSE_FAILED`. | Python-level asynchronous interruption in the bytecodes between `NtCreateFile` returning and `ledger.enter` (see §4 F-3). |

## 4. Post-implementation adversarial self-review (of the actual code)

| # | Finding | Disposition |
|---|---|---|
| F-1 | **Real defect, fixed.** `_create_child` validated `kind` only inside `ledger.enter`, *after* the native create. An unknown kind would create a file and then refuse at ledger entry, leaving a created object **and an untracked handle**. | Kind is now validated before the call in `_create_child` and again in `_native_relative_create`. Regression: `test_an_unknown_kind_is_refused_before_the_native_call` (the native spy records zero calls, the ledger gains no entry, nothing is created). |
| F-2 | **Draft defect, not inherited.** The preserved draft set `UNICODE_STRING.Length = len(name) * 2` (code points). A supplementary-plane name would be truncated by one UTF-16 unit — to a **different** name. | The candidate uses the UTF-16 byte length. Regression: an astral-plane file name round-trips with its full identity, and its case-variant collides. (The exact-set gate would also have refused the truncated name, before content.) |
| F-3 | Residual: an asynchronous Python exception (e.g. `KeyboardInterrupt`) delivered between `NtCreateFile` returning and `ledger.enter`, or a `MemoryError` inside `enter`, would leave one handle untracked. | Not closable in Python. Stated, not fixed. It cannot produce a false `True`: the derived fact covers ledger entries only, and the executor-level §7.8.1 derivation (not implemented here) must not treat an absent entry as proof. |
| F-4 | The gate is the containment *backstop* for content, not for objects. If a create relative to a converted parent ever followed the reparse point (the open A2-3 question), a zero-byte object could exist outside `R`, and the gate would refuse with no content written. | This is why A2-3 remains a hard bar for INV-F5A-W's "no object outside `R`" reading. Not a new blocker; recorded. |
| F-5 | R-ALIAS chain: a hard link from outside to a held share-0 child was *recorded* (supplemental, same process). Under that observation an outside name can alias approved runtime bytes written through `h_f`. Combined with F-4 it could also place a link to an escaped object back into `D` so that `D`'s gate matches. | Not prevented, and no link-count gate is added (directive §7). Content is approved runtime bytes; L9 impact is separate (see the L9 note). |
| F-6 | Directory construction pins use the FU4-A2 shape, not §7.4A.2's `GENERIC_READ`. | Both are read-only, share READ, no DELETE. Recorded as a deliberate, reviewer-visible difference (§1). |
| F-7 | The run-root pin keeps §7.4A.1's share `READ \| WRITE`; R1-FU3 showed it does not refuse conversion of an **empty** `R`. | `R` is non-empty at L3R (the workspace from L3), and relative creates do not resolve `R` by name. Not changed (frozen shape). |
| F-8 | Post-pin item 2 (exposure absence) and the `inventory`↔`profile_id` pairing are not checked by the candidate. | Deferred to executor integration (§2), because both need the matched profile object. |
| F-9 | Source reads and final pins, and the post-pin walk, still use pathnames. | Intended: source reads are **reads** verified before persist (§7.4B); final pins are opens of existing objects checked against creating-handle ids (pre-authority, §7.6). No pathname **creation** remains. |
| F-10 | `construction_handle_peak` is a simulation of the code's order, and the test asserts the ledger's observed peak equals it on the synthetic payload. On the committed approved inventory it gives **449** (≤ 462). | The synthetic run does not exercise 360-file fan-out; that is P-R1-4 (ii) territory. |

| F-11 | The first full-suite run failed the frozen package-wide sweep **T-125** (`test_cfg1_stage_decision.py`): no CFG1 callable may take a parameter named `ledger`, which is reserved for the runner-local stage-ordinal ledger. The candidate's helpers used that name. | The candidate's parameters were renamed (`handles`; the entry back-reference is `owner`). T-125 itself is untouched and now passes. No semantic change. |

No other bypass within scope was found. Speculative defence-in-depth (link
counts, `FileLinksInformation` cross-checks, extra `..` id checks) was
deliberately not added.

## 5. Tests — what they show and what they do not

`test_cfg1_f5a_a2_offline_candidate.py` (76 tests). Kinds of evidence:

- **Pure logic (any platform):** single-component validation, T-CANON / T-NM /
  T-BUN, ledger state machine (with a replaced close seam), static AST audit (no
  pathname creation, no deletion, every `CreateFileW` is `OPEN_EXISTING`, one
  native call site with `FILE_CREATE`, allowed imports only), committed-inventory
  LDT paths and construction bounds.
- **Real handle-relative creation under `tmp_path` (Windows):** byte-identical
  synthetic copy with exact topology; ledger closed; peak equal to the
  simulation; four final pins held until release; identity mismatch, planted
  `RT`, foreign name before the gate, case collisions, astral names, parent
  injection, content-before-gate — each refusing with no content written and
  nothing deleted.
- **Injected seams (named in each test):** native export unavailable;
  `Information != FILE_CREATED`; `CloseHandle` failures (child, directory pin,
  final pin); T-PLAIN via a patched no-follow leaf; source mutation after
  observation (T-F5A-28 shape). These show the candidate's own branches refuse
  and keep truthful lifecycle state. They do **not** show a real native anomaly.

**Executed on this host (Windows 10.0.26200, NTFS), 2026-10-12:**
`experiments/pi_harness_cfg1/tests` — **3518 passed, 4 skipped** (the four
pre-existing `test_cfg1_impl_fu1_findings.py` "not an adversarial case" skips),
**0 failed**, with the standard **16** installed-Pi / Node deselections of
`test_cfg1_pi_conformance.py`. **Not executed** in that run:
`test_cfg1_f5a_windows_handle_probes.py` (frozen Q1–Q6 evidence; 13 known
premise FAILs) and `test_cfg1_f5a_r1_windows_premises.py` (P-R1 evidence), both of
which create junctions and convert directories and are unrelated to this
candidate; and the preserved, uncollected FU4-A2 draft. This is ordinary
regression evidence. **It is not Windows authority qualification and does not
clear the A2-3 hard bar.**

**Not exercised, by design:** no reparse point is created, no directory or file is
converted, and no conversion races a create. Those are the FU4-A2 experiments;
the A2-3 re-run was blocked by a safety classifier and is **not** repeated,
relocated or re-routed here.

## 6. Remaining empirical qualification obligations

1. **A2-3** — one validated run of the preserved draft (unmodified, revision
   `2952d2f0…`) with **no teardown error**, reconciling §3 of the FU4 report.
2. **A2-2** — the corrected status predicate executed (and preferably narrowed to
   a named status set).
3. **Racing conversion** — a create concurrent with an attribute-only conversion
   of its parent; currently inference only.
4. **A2-5** — real (not injected) native anomalies, where producible.
5. **A2-8 / P-R1-4** — construction on the **approved** inventory shape
   (360-file fan-out, 80 child pins, depth 11, peak ≤ 462) with this candidate's
   create shapes, plus the P-R1-4 (iv) refusals for natively created pins.
6. **Candidate-on-target-platform** — this module's own construction under the
   same conversion scenarios as A2-3/A2-6 (FU4-A2 measured a test-local wrapper,
   not this code).
7. **Platform breadth** — other Windows builds, ReFS / Dev Drive, filter drivers;
   the stability of `0xC0000280`/`0xC0000279` (undocumented) and of user-mode
   `NtCreateFile` across versions.
8. **R-ALIAS** — actor/share semantics of `CreateHardLinkW` against a held
   share-0 handle from another process (separate decision; does not block F5-A
   offline work).
9. **P-R1-1 PARTIAL** stays PARTIAL; P-R1-2/3 as recorded.

## 7. Remaining authoritative acceptance blockers

- A2-3 INCOMPLETE; A2-2 correction unrun; no racing-conversion evidence (§6 1–3).
- Independent acceptance of this candidate and of the §1 correction to §7.4A.2/3/4.
- Executor integration (§2), separately authorized, with T-F5A-01…33 completed.
- D-F5A-9 and D-F5A-10 independent acceptance (amendment §19).
- R-ALIAS disposition for **L9** (see the L9 note); not a blocker for F5-A
  offline work.
- E5 conditions of amendment §17 — untouched. **No live launch is authorized.**

## 8. Smallest next step

Authorize **one** run of the preserved FU4-A2 draft, unmodified, in a session
where it is permitted (FU4 report §10). If A2-3 then passes with no teardown
error, the next step is a narrowly scoped qualification run of **this
candidate's** construction under the A2-3/A2-6 conversion scenarios (§6 item 6),
before any executor integration is authorized.
