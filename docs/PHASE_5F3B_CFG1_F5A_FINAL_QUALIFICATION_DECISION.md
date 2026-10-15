# Phase 5F3B-CFG1-F5A — Final Qualification Decision (FU2: P2/P3 Corrected, Closure Architecture Selected)

```text
STATUS         NON-FROZEN decision record, revision FU2. Amends nothing. Authorizes nothing. Grants no residual.
BASE HEAD      39d81bac799d33cba66c38e09fb6588122d39fb6 (tracked tree clean)
SUPERSEDES     Revision FU1 of this file (same path, never committed), and through it the first draft.
               FU1's HOLD/STOP disposition was accepted; its "only P1 is unproven" claim is CORRECTED here (§0).
F5-A           NOT ACCEPTED, NOT FROZEN. HOLD.
DECISION       HOLD — EXTERNAL AUTHORITY REQUIRED (§8).
               A concrete, bounded closure architecture is selected (§7), but it is NOT permitted by the frozen
               contracts. It needs the exact amendments in §9, plus one narrow reviewer decision (DEC-FC).
               No implementation is authorized.
L9 / L11       A SEPARATE live-enablement blocker (§5). Not modified.
LIVE           BARRED. Both barriers unchanged:
               run_executor.py:2153 (provision_runtime = live_runtime_provisioning_not_qualified)
               run_executor.py:1970 (_build_supervisor refuses unconditionally).
EXECUTED       Nothing. No junction, conversion, hard-link, race or escape experiment. No real Pi, Node,
               backend, model or credential. No production, test, frozen or CLAUDE.md change.
               Read-only code review plus three public documentation reads (§6.1).
ACCEPTED, NOT  Offline implementation (ed69cca, a56a182, 3bf223e), construction-scale evidence (68ae5b0),
REOPENED       ordinary-handle evidence (39d81ba), frozen Y-6 / AMEND2 (90d45ff).
```

## 0. What FU2 corrects

| FU1 claim | FU2 status | Why |
|---|---|---|
| Only P1 is open; P2 is "established at the gate" (FU1 §2) | **Withdrawn** | §2. Under the unresolved A2-3 condition, a hard link makes an escaped file pass the exact-set gate, and content is then written into an object whose creating name is outside `R`. Nothing in the frozen contracts or the code rules this out. **P2 is UNPROVEN** |
| P3 "established" for F5-A, with no qualification | **Refined** | P3 holds for F5-A only in the sense that L3R deletes nothing. For L9 and L11, a genuine creating handle is not namespace authority. Their handle-based dispositions can delete outside `R` (§3, §5) |
| L9-2 covers only the failed-gate disposition | **Widened** | The post-write failure path disposes too (`cfg1_pi_config.py:616-617`), and L11 has the same pattern (`cfg1_extension.py:385`) (§5) |
| A-1 is "the recommended path to examine first" | **Withdrawn as an authorization candidate** | Its concurrency property P-B can only be assumed, never established (§6.3). It also leaves L9 and L11 uncorrected |
| No architecture is proposed | **Superseded** | §7 selects one. It removes every disputed create from F5-A, and it reduces L9 and L11 to one precisely bounded create each |

FU1's other conclusions stand: the independent finding is valid; R-CREATE-ESCAPE, option G and F5A-G1 stay withdrawn; §37.3.3's last bullet is not a precedent; "the actor could do it anyway" is not a justification (FU15-D1); G-C1 alone does nothing for P1. They are restated in §1 only as far as FU2 relies on them.

## 1. Frozen standard (restated, unchanged)

| Frozen source | Requirement |
|---|---|
| FU15 §37.1 | "no endpoint-bearing byte is written outside CFG1's own owned, identity-proven disposable root", and "no cleanup ever deletes or mutates a resource whose ownership is not mechanically proven" |
| FU15 §37.3.2a | Precise-child cleanup must prove, at the moment of the operation, that the target "remains contained and identity-matched". No CFG1 path may act on what lies outside the owned root |
| FU15 §37.3.6 | R-WINDOW is "the one residual". Its sole justification is containment by file id inside `R`. It is "not an external/out-of-root config write" |
| AMEND2 AMD2-4, C-2 | Containment is relaxed **for the content scrub only**. The preserved half: no redirect is followed, "nothing outside the root is *deleted*", and only an object AIDO created is written |
| AMEND2 §13 | Outside zero-length names are accepted where "a same-user actor moved or linked the object". That is actor-authored names only |
| F5-A §7.4A.4/.5, §18 row 22, T-F5A-25 | "no write can leave `R`"; "zero objects or bytes outside `R`" |

## 2. Corrected property classifications

### 2.1 The P2 counterexample (conditional; not reproduced)

For one parent directory `D` with held handle `h_D`, and one file child `n`:

| t | Actor (same user) | AIDO | What the gate can see |
|---|---|---|---|
| t1 | Converts empty `D` to a mount point onto `X` (same volume). R1-FU3 measured that the pin does not prevent this | — | — |
| t2 | — | Creates `n`. **Assumed outcome O3:** the object `F` is created as `X\n`. Creating handle `h_n` (share 0) is held | — |
| t3 | Deletes `D`'s reparse point. `D` is empty again, so this succeeds | — | `D` is plain again |
| t4 | `CreateHardLinkW(D\n → X\n)`. Y-6 (frozen) says this succeeds against a share-0-held file | — | `D`'s own index now holds `n` with `F`'s file id |
| t5 | — | Exact-set gate on `h_D` | Name set exact; file id equals `h_n`'s; volume equal; a file; no reparse attribute or tag. **Passes** |
| t6 | — | Content written through `h_n` into `F` | `F` has an inside name `D\n` and an **AIDO-authored** outside name `X\n` |

**Do the frozen contracts or the code rule this out mechanically? No.**

- The F5-A gate (`pi_runtime_provision.py:986`) compares the name, the file id, the directory bit, and the reparse attribute and tag. A hard link matches all of them, because a hard link *is* the same file.
- The L9 gate (`win_config_authority.py:805`) compares names, file ids and volume. It is weaker still.
- Neither gate asks which directories hold the object's other names.
- AMEND2 §2 forbids relying on `NumberOfLinks` or alias exclusion. No frozen text requires the creating name to be the inside name.
- t3 restores plainness, so G-C1 would not refuse either.

**Limits of the counterexample.**

- It requires O3, which is exactly the unresolved A2-3 condition for F5-A's relative create. For L9's and L11's pathname create, the escape shape was **measured** (R1-FU3), although their exact sequence was never run against a conversion.
- It works for **file** children only. Directories cannot be hard-linked, and a junction alias fails the F5-A gate's reparse check. An escaped directory child therefore ends at a refusal plus a stranded empty directory (P1 only).

### 2.2 Classifications

| # | Property | F5-A (A2 as implemented) | L9 / L11 (frozen, as implemented) |
|---|---|---|---|
| P1 | AIDO creates no object outside an authorized namespace | **UNPROVEN** (A2-3) | **NOT ESTABLISHED.** The pathname shape is measured to escape (R1-FU3) |
| P2 | AIDO writes content only into objects whose AIDO-authored names are all inside an authorized namespace | **UNPROVEN** (§2.1). The consequence is approved public bytes in an object named outside `R` and never cleaned. Under token asymmetry (FU1 §1.3), that is a file with an approved name and content inside a directory only AIDO's token could write | **UNPROVEN, on a measured premise.** Endpoint bytes (L9) or token bytes (L11) are written into an object with an AIDO-authored outside name. That contradicts §37.1's endpoint-byte requirement directly. A later AMEND2 scrub truncates the content; it does not undo the write or the name |
| P3 | Deletion, disposition or scrub only under proven authority over the target **and its namespace** | **Holds vacuously:** L3R deletes, disposes and scrubs nothing. L27 stays within `R` and removes only an aliased object's inside name. The price is that escaped objects are stranded | **NOT ESTABLISHED.** There is a conditional code ↔ contract conflict (§5.2). A genuine creating handle proves object identity, not containment, and on a failed gate there is no containment proof at all |
| P4 | Lifecycle and refusal evidence is truthful | **Conditional.** Runtime facts are truthful as scoped. The frozen claims in §18 row 22, T-F5A-25 and §7.4A.4 cannot currently be asserted | **Conditional.** `endpoint_material_outstanding` remains a truthful object-content fact. FU15 §37.3.2b fact 7, §37.3.3, §37.3.4 rows 2 and 4, and the L9 docstrings ("no pathname-resolved victim is reachable") are false whenever an escape occurred |

**The correction FU2 makes:** P1 **and** P2 are unproven. P3 is unproven for L9 and L11. P4's document-level claims fail with them.

## 3. P3, separately

A handle-bound operation is authorized by two things together:

- **Object authority:** this handle descends from AIDO's creating handle, and its identity matches.
- **Namespace authority:** the target, and the name the operation affects, lie inside a namespace AIDO may mutate.

A genuine handle supplies the first only. The frozen texts separate the two deliberately:

- AMEND2 relaxed containment **for the content scrub only**, because a truncation alters the object's contents and no name.
- A disposition (`FileDispositionInfo`) is a **namespace** operation: it removes a name.

| Operation | Object authority | Namespace authority | Verdict |
|---|---|---|---|
| AMEND2 SCRUB-C / SCRUB-R (`win_config_authority.py:1496`, `:1529`) | Yes: creating-handle lineage plus identity | Not required (AMD2-4). It removes no name | **Within AMEND2.** Under an escape, the scrub truncates an object that also has an AIDO-authored outside name. That reduces exposure; it does **not** authorize, remediate or excuse the outside name or the earlier write. AMEND2 §13 covers actor-authored names only |
| L9 / L11 disposition through the creating handle | Yes | **No.** On a failed gate, containment is unproven by definition. After a passed gate, only the inside name is proven, not the name the creating handle was opened through | **Not authorized** (§5.2) |
| L27 `remove_disposable_tree` | n/a (namespace teardown) | Yes, for names inside `R` | **Authorized** for inside names only. It never reaches the outside name |

## 4. L9 code paths reviewed

| Path | Location | Effect under an escape (conditional) |
|---|---|---|
| Pathname `create_exclusive_child` | `win_config_authority.py:964`, called at `cfg1_pi_config.py:493` and `cfg1_extension.py:313` | **External create.** `CreateFileW(join(dir, name), CREATE_NEW, FILE_FLAG_OPEN_REPARSE_POINT)`. The flag governs only the last component, so a converted `D` is traversed and a zero-byte file is created at `X\name`. This shape was measured (R1-FU3) |
| `prove_config_parentage` | `win_config_authority.py:805` | Detects a plain escape: the name is absent from `D`'s index. It does **not** detect the §2.1 alias: names, file id and volume all match. Its docstring claim that only "a content-free file" can exist at an unproven location holds only when the gate refuses |
| `_dispose_children_by_handle` on a failed gate | `cfg1_pi_config.py:216`, called at `:506` | **External disposition.** The escaped child's only name is `X\name`, so a handle disposition deletes a name outside `R` |
| Disposition after endpoint bytes were attempted | `cfg1_pi_config.py:616-617` (`_dispose_quietly`), and L11 at `cfg1_extension.py:385` (on any known failure) | **External disposition, after a passed gate.** In the §2.1 alias case the object has two names. Which name a `FileDispositionInfo` on the creating handle removes is not established by this review. If it is the name the handle was opened through, it is the AIDO-authored outside name. Nothing proves otherwise |
| Endpoint-bearing content writes | `win_config_authority.py:1043` (`write_child_text`), `cfg1_pi_config.py:517`. L11's token write is at `cfg1_extension.py:325` | **External write (P2).** In the §2.1 alias case, endpoint or token bytes go into an object whose AIDO-authored name is outside `R` |
| AMEND2 handle-bound scrub | `win_config_authority.py:1496`, `:1529` | Object-bound truncation of AIDO's own object; no name is touched (§3). It is not an outside-root authority, and FU2 does not read it as one |

## 5. L9 / L11 security disposition

### 5.1 L9 is a separate live-enablement blocker

L9 (endpoint) and L11 (broker token) rest on FU15 fact 7 / W3, which R1-FU3 falsified. Their creates use the pathname shape that was measured to escape. Closing F5-A by any route leaves them exactly as they are.

Today they are unreachable live only **incidentally**: in the default binding, L3R refuses before L4, L9 and L11 run. Any future change to the L3R barrier must therefore come with an **explicit** L9/L11 condition. It must never inherit that shielding by accident.

### 5.2 Issues (L9 and L11 are not modified)

| Id | Issue | Kind |
|---|---|---|
| L9-1 | FU15 fact 7 (W3) is false for the empty config directory, and so for L11's extension directory. Every claim resting on it is unsupported: §37.3.3 bullets 1–2, §37.3.4 rows 2 and 4, §37.3.6's "not a post-pin in-place reparse conversion" | Contract |
| L9-2 | Handle-based disposition on the failed-gate path (`:506`) **and** on the post-write failure paths (`:616-617`; L11 `:385`) can delete a name outside `R`. This conflicts with §37.3.2a (precise-child containment) and with AMEND2 C-2's preserved "nothing outside the root is deleted". §37.3.2 row 10's justification held only under W3 | Code ↔ contract (P3) |
| L9-3 | §2.1 puts endpoint and token bytes into an object with an AIDO-authored outside name | Contract (P2; §37.1) |
| L9-4 | Under an escape that is detected and refused, a zero-byte AIDO-authored file is stranded outside `R` | Contract (P1) |

## 6. Architecture evaluation

### 6.1 Published sources added in FU2

| Source | Content relied on |
|---|---|
| Microsoft Learn, *FSCTL_SET_REPARSE_POINT control code* (ntifs, ms.date 2023-03-13, updated 2024-02-01) | `STATUS_DIRECTORY_NOT_EMPTY`: "A reparse point cannot be set on a nonempty directory." This is unconditional as published |
| *_FILE_LINK_ENTRY_INFORMATION* (ntifs, ms.date 2018-04-16) | `ParentFileId`: "The ID of the parent directory of the link." Each entry describes one hard link |
| *FSCTL_SET_REPARSE_POINT* (Win32, ms.date 2018-12-05) | Read, **not relied on.** It states no emptiness precondition, and its privilege remark is not reconciled with R1-FU3's measurement |

The `CreateFileW` share-mode contract (a later open requesting `DELETE` fails while a handle without `FILE_SHARE_DELETE` is held) is already used by frozen W2 and W6.

### 6.2 The structural fact behind every option

Every directory AIDO creates starts empty (documented), and a same-user actor may convert it while it is empty (measured). Once a directory holds an entry that cannot be removed, the published precondition forbids converting it. Therefore:

- **A create into a directory that is held non-empty from before the create starts** depends on no undocumented premise. Its parse starts at a directory that is plain and cannot be converted.
- **The first create into a fresh directory** is irreducibly exposed, unless the A-1 premises are granted. No ordering, gate, DACL (symmetric for a same-user actor), oplock (FU1 §5.3), or extended attribute (removable through an attribute-class open, which share modes do not govern) changes that.

The question is therefore not how to qualify more creates, but how to **eliminate** first-child creates.

### 6.3 Options

| Option | F5-A first-child creates per run | Rests on | Verdict |
|---|---|---|---|
| **A-1** Evidence-standard amendment (OBJ_DONT_REPARSE + P-A/P-C measured, P-B assumed) | Hundreds, each followed by content | **P-B, linearizability of a create against a concurrent conversion: assumed, never establishable.** A racing test can falsify it, never prove it | **Rejected as an immediate authorization.** Its critical concurrency property rests only on an assumption. It does not touch L9 or L11 |
| A-2 Accept AIDO-authored outside objects as a new residual | Hundreds, with content (§2.1) | An authority amendment of unbounded count, carrying content | Rejected: P2 is lost, not only P1 |
| A-3 Narrow §37.1 | — | Narrowing the threat model | Rejected (FU1) |
| A-4a **Consume an operator-staged runtime in place (OSR)** | **Zero** | Content identity by complete walk against the sealed profile; topology by INV-F5A-R1; no AIDO write | **Selected for F5-A** (§7.1) |
| A-4b Persistent AIDO-managed installation (F5-A §6.1 "A1") | Zero per run, but AIDO-owned | Cross-process ownership, update and GC lifecycle | Rejected, as before |
| A-4c Occupant-anchored per-run copy (§7.2's technique applied to RPR) | One per payload directory (hundreds), each detected before content | DEC-FC at scale | Rejected: OSR needs none |
| TP-1 A separate principal (service account) owns the staging and config directories | Zero exposure to a same-user actor | A trusted-platform capability and a new launch identity | Not selected. Larger than the problem. Recorded as the only route to zero residual for L9/L11 without A-1 or R-DIRECT |
| R-DIRECT Pi's agent directory becomes `R` itself, so no fresh config directory exists | Zero for L9 | A Pi byte-level review of agent-directory semantics over `R`'s other entries; it reopens G4/G5/PE-4A analyses | Not selected. Recorded as the alternative to DEC-FC (§8) |

## 7. Selected closure architecture: "consume, don't construct" plus occupant-anchored writers

### 7.1 F5-A → OSR (operator-staged runtime, consumed in place)

The operator stages the approved payload tree once, at a plain path with no `node_modules` component anywhere in its chain. AIDO **creates, writes, renames, deletes and pins-for-write nothing** there. It proves the tree, then launches from it. INV-F5A-R1 is unchanged in form and is evaluated over the staged root's chain.

Nothing about the operator or the staging process is trusted. Authority rests only on mechanical proofs.

| Id | Proof obligation | Source of authority |
|---|---|---|
| OSR-1 Selection | One project-config absolute path. It ships unset, and unset refuses. It is never taken from a model, a caller, a run parameter, an environment variable or PATH. It is never recorded as an absolute path | Project config (operator); refusal by default |
| OSR-2 Identity | A complete PI-PC1 walk of the staged root, with P2M exact membership and P2X exposure absence, whose fingerprint equals the **sealed profile's** loader-bound fingerprint. `node.exe` still comes from L1 (`I_n`). Where the bytes came from is irrelevant: identity is content against reviewed policy, exactly as the ambient source is treated today | Sealed HPP-1 policy (unchanged) |
| OSR-3 Topology | T-CANON, T-NM over the whole chain, T-PLAIN, T-BUN; no `PI_PACKAGE_DIR`; the staged root lies outside every AIDO-minted root, the checkout and the ambient npm prefix | INV-F5A-R1 (unchanged in form) |
| OSR-4 Immutability is **not** assumed | Proofs are at an instant only: the walk, then the final read-only pins (share `READ`) on the four LDT files, the post-pin re-walk, the L14 re-proof, and the L21A re-observation. Same-user substitution after the last proof is the existing R-SLIVER / R-ABA residual (F5-A §2.5), unchanged in kind. A persistent root gives an actor more **time**, not a different capability, against an at-instant proof standard | Existing accepted residual |
| OSR-5 Consumption boundary | Read-only, no-follow opens only. No ownership claim; L27 never touches it; no lifecycle | — |
| OSR-6 Runtime write-absence | A byte-bound static proof that the approved profile, under the T-4 environment, creates, writes, renames or deletes nothing under `getPackageDir()` beyond F-5, which INV-F5A-R1 nulls. If any such effect exists, OSR refuses that profile. Reason: under RPR such writes landed inside `R`; under OSR they would mutate a resource AIDO does not own | PE-4A-class byte review (read-only) |
| OSR-7 Resolution closure | F5-A §8.2 re-derived from the staged root: every module resolves inside the root's own `node_modules`, and every ancestor's `node_modules` child is no-follow `MISSING` (the T-RT analogue) | Static review plus a read-only check |
| OSR-8 Concurrency | Several runs may consume one root. Read-only pins are mutually compatible. OSR-6 rules out interference by genuine Pi | — |
| OSR-9 Privacy | Model-visible documentation paths point into the staged root, which needs a PE-4A F-4 re-disposition. The operator chooses a non-identifying path. Records never carry it | Reviewer |
| OSR-10 | D-F5A-9 (U126 read relocation) re-examined for the staged-root topology | Reviewer |

**What OSR removes:** every L3R create, so P1 and P2 hold vacuously for F5-A. It also removes the construction ledger, the native relative create, A2-3, and R-ALIAS for runtime files. The amendments shrink to a selection change plus a read-only admission step.

**What OSR does not remove:** E5 condition 9. An approved 1.0.3 tree is still required. OSR makes the requirement concrete: the staged root **is** that tree.

### 7.2 L9 and L11 → occupant-anchored writers (CFG1-K)

| Step | Change | Basis |
|---|---|---|
| K1 | **No handle-based disposition, anywhere in L9 or L11** (remove `:506`'s call, `:616-617` and L11 `:385`). Zero-byte and partial children are left for L27 if inside `R`, or stranded if not. Never deleted through an unproven name | Pure subtraction. AMEND2 already excludes disposition from `endpoint_material_outstanding` |
| K2 | **Hold `R` occupied** before creating `D`. Open one existing entry of `R` without `FILE_SHARE_DELETE`, and prove by file id from `R`'s pin enumeration that it is in `R`'s own index. An open never creates, and a mismatch refuses | Share contract (W2/W6); published non-empty precondition |
| K3 | **Create `D` relative to `h_R`** with `FILE_CREATE`, holding the returned handle as `D`'s pin (F5-A's directory shape). This **retires R-WINDOW**: there is no create → pin interval | Accepted ordinary-handle evidence (39d81ba); `R` cannot be converted (K2) |
| K4 | Create the **non-sensitive** first child (`settings.json`; L11's first verified source) relative to `h_D`, zero bytes, share 0, held. **This is the one exposed create (DEC-FC)** | — |
| K5 | **Occupant gate**, before any sensitive create: `D`'s exact set and file ids from `h_D`; **then** `D` is plain from `h_D` (G-C1 is now meaningful, because `D` cannot change after this point); **link-set gate (LG)**: the child's complete link set (`FileHardLinkInformation` from its creating handle) has every `ParentFileId` equal to `D`'s id. Any failure refuses. Nothing is written or deleted, and a P4 fact records that an AIDO-created zero-byte object may exist outside `R` | Published `ParentFileId` semantics. A creating name cannot be removed while the share-0 handle is held, so an escaped creating name is still present at LG. Links added later by an actor are R-ALIAS (accepted, AMEND2) |
| K6 | Create the **sensitive** child (`models.json`; `ar2_config.ts`) relative to `h_D`. `D` is plain, non-empty from before the create, and cannot be converted, so the parse starts at a plain directory with a single component, and the object lands in `D`'s own index. **No undocumented premise** | §6.2 |
| K7 | Final gate: exact set, file ids, `D` plain, LG on **every** child. Only then content | — |
| K8 | **E-TOKEN** precondition: refuse if AIDO's token is elevated (`TokenElevation`, documented). This bounds DEC-FC's harm; it is not offered as a justification (FU15-D1) | Documented token query |

**Result for L9 and L11:**

- P2 is **established** for every byte. Sensitive bytes go only into objects created where no escape is possible. Non-sensitive bytes go only into objects whose creating name LG proved inside `D`.
- P3 is **established**: nothing is ever deleted by handle.
- P4 is truthful, given the new fact.
- P1 is established for everything **except K4's single zero-byte, content-free create per writer**. Under O3 that create may author one empty file, with a fixed approved name, in an actor-chosen directory. It is detected before any content, refused, stranded and reported.

### 7.3 Proof obligations for CFG1-K

| Id | Obligation |
|---|---|
| K-PO1 | Id domains agree. `ParentFileId` is 64-bit, while the current enumeration yields 128-bit `FILE_ID_128`. Obtain `D`'s 64-bit id from its own handle (`FileInternalInformation`), and compare like with like |
| K-PO2 | The K2 occupant is chosen without conflicting with any frozen consumer. The AR2 marker's re-read is a read open, which is compatible with share `READ` |
| K-PO3 | K5's order is fixed: membership first, then plainness, both from `h_D`. Plainness observed after an undeletable entry is proven present persists (§6.2) |
| K-PO4 | Synthetic `tmp_path` regression tests, in a separately authorized phase: LG refuses a handle whose object also has a link in a sibling directory; no disposition on any path; the relative sensitive create; E-TOKEN. A synthetic hard link is used only to construct the predicate's input. **No conversion, junction or race** |

## 8. Decision

**HOLD — EXTERNAL AUTHORITY REQUIRED.**

- **The selected architecture is §7.** OSR for F5-A, and CFG1-K for L9 and L11. Both are bounded, and both remove the dependency on undocumented relative-create semantics except at K4.
- **It is not permitted by the frozen contracts.** It changes F5-A's chosen mechanism, PE-1 selection, and FU15 §37.3. So nothing is authorized.
- **One narrow decision cannot be avoided: DEC-FC.** No supported mechanism makes the first create into a fresh directory P1-safe for a same-user actor (§6.2). The reviewer must choose one of:
  - **(a) grant R-FIRST-CHILD** with exactly these terms: at most one per writer per run (L9 and L11); zero bytes, content-free, created with an approved fixed name; detected by LG before any content; refused; never deleted; reported as a P4 fact; authorship explicitly acknowledged as AIDO's; E-TOKEN in force;
  - **(b) authorize the R-DIRECT review** (§6.3);
  - **(c) adopt TP-1.**

  Without one of these, L9 and L11 have **no supportable path** under the current threat model short of A-1.
- **Recommendation for that decision:** (a). Its worst case is one detected, content-free, zero-byte file per writer, with no token asymmetry. A-1, by contrast, rests every one of hundreds of content-bearing creates per run on an assumption that cannot be tested. This is a recommendation for the reviewer's decision. **It is not granted here.**

## 9. Exact frozen-contract amendments required

| Id | Frozen surface | Change |
|---|---|---|
| AMD-OSR-1 | F5-A amendment §6.1, §7.1, §7.2, D-F5A-1 | The chosen mechanism A2-R1 (RPR) is replaced by OSR. The topology constant `C` becomes the OSR-1 binding. T-RT is replaced by the OSR-7 ancestor rule. The A1 rejection is restated to distinguish OSR (no AIDO ownership or lifecycle) |
| AMD-OSR-2 | F5-A §7.4, §7.4A, §7.4B, §11.1, §11.2 | L3R "provisioning" becomes a read-only "staged-runtime admission". The construction, gate and content sections are removed. The refusal vocabulary is reduced accordingly |
| AMD-OSR-3 | F5-A §7.6–§7.8, §7.8.1, §18 row 22, T-F5A-25 | Final pins move to the staged root. There is no construction ledger. `live_references_released` is re-scoped to the final pins (D-F5A-10). Row 22 and T-F5A-25 hold trivially |
| AMD-OSR-4 | PE-1 §11.1 P1/P2; `pi_identity._PI_PACKAGE_PARTS` (`pi_identity.py:161`) | The package root comes from the OSR-1 binding, not from the `pi.cmd`-anchored `node_modules\@earendil-works\pi-coding-agent` layout. That layout makes INV-F5A-R1(c) fail by construction. `node.exe` selection is unchanged |
| AMD-OSR-5 | PE-4A F-4 | Model-visible documentation paths are re-disposed (OSR-9) |
| AMD-K-1 | FU15 §37.3.1 steps 3–7; §37.3.2 rows 9–10 and the "how cleanup proves" row; §37.3.2b fact 7 → fact 7′ (non-empty-held directory + published precondition); §37.3.3; §37.3.4 rows 2 and 4; §37.3.6 (R-WINDOW retired by K3) | K1–K7 for L9 |
| AMD-K-2 | L11's frozen E-sequence (R6 / FU1 AM-10 extension-writer design) | The same K1–K7 for L11 |
| AMD-K-3 | AMEND2 §9 "K" and §10 | "then dispositions" is removed. The scrub, RELEASE-R and the bool formula are unchanged |
| DEC-FC | FU15 §37.1 / §37.3.6 | One of (a), (b) or (c) in §8 |

## 10. Smallest implementable phase once authorized

**CFG1-K1: remove handle-based disposition from L9 and L11.** It is pure subtraction and needs only AMD-K-3 plus the §37.3.2 row 9–10 part of AMD-K-1. It restores P3 under every option, including A-1, so it does not prejudge the architecture. It is offline, and its tests use synthetic `tmp_path` only.

The next phases, in order:

1. **CFG1-K2:** K2–K8 plus K-PO1..PO4, after AMD-K and DEC-FC.
2. **F5A-OSR:** after AMD-OSR-1..5 and an approved byte tree (E5 condition 9). The offline A2 construction code is superseded then, never silently.

Recommended model for each: Claude Opus 5.5, high effort.

## 11. Work that can advance independently toward Alpha

1. **Reviewer decisions:** AMD-OSR, AMD-K, DEC-FC; D-F5A-10 (independent; re-scoped to final pins only under OSR); D-F5A-9 (needs re-examination only if OSR is chosen, per OSR-10).
2. **E5 condition 9:** obtain an approved 1.0.3 tree from any source. Under OSR it becomes the staged root, and identity is proven by content. If no tree is obtainable, a new profile goes through PE-3…PE-5.
3. **Read-only static reviews on approved bytes:** OSR-6 and OSR-7, once bytes are available.
4. **The existing human-supervised path (5F2C write → 5F2D verify → 5F2E review → human)** does not depend on F5-A, L9 or L11, and is usable for Alpha under its own gates.

**Inherited observation, not decided here (L2-Q).** The frozen L2 creator (`build_case_repository`) populates freshly created directories by pathname. The P1 standard applied here would question those creates too. They carry no sensitive bytes, and a converted root is refused at registration. This is recorded only so that no document claims run-wide P1 on the strength of F5-A and L9 corrections alone.

## 12. Live authorization

**Barred.** Nothing here lifts either barrier, changes a refusal, or authorizes any phase. Both barriers are verified unchanged at `run_executor.py:2153` and `run_executor.py:1970`.

Live authorization still requires all of:

- F5-A ACCEPTED / FROZEN under an adopted architecture;
- L9 and L11 corrected (§5) under an adopted DEC-FC;
- E5 conditions 1, 6, 8 and 9;
- a fresh live authorization that explicitly lifts both barriers and states the L9/L11 condition (§5.1).

## 13. Adversarial review of FU2

| Challenge | Answer |
|---|---|
| Is §2.1 reproduced? | No. It is conditional on O3, which is the unresolved A2-3 condition, and it was not run. The claim is only that nothing **rules it out** mechanically, which is the frozen standard |
| Does Y-6 really permit t4? | Y-6 is frozen: `CreateHardLinkW` succeeds against a share-0-held file. FU2 uses that and nothing more |
| Is LG an alias-exclusion argument, which AMEND2 §2 forbids? | No. LG never claims that no alias exists or will exist. It refuses when an **outside** parent is present at a moment when an AIDO-authored creating name, if escaped, cannot have been removed. Later actor-added links remain R-ALIAS |
| Does K6 smuggle in an undocumented premise? | It rests on: published `STATUS_DIRECTORY_NOT_EMPTY`; the share contract already frozen in W2/W6; handle-observed plainness after an undeletable entry is present; and the accepted ordinary relative-create evidence for a **plain** root. The disputed case (a converted root) cannot arise. The published precondition is unconditional; tag-level nuances beyond it are not assumed, and K7 re-checks `D`'s tag regardless |
| Is DEC-FC (a) R-CREATE-ESCAPE again? | No. R-CREATE-ESCAPE was unbounded, content-bearing, presented as an existing residual, and justified by "no capability gained". DEC-FC (a) is one zero-byte, content-free create per writer, detected before content, put to the reviewer as a **new** amendment, bounded by E-TOKEN, and not pre-accepted |
| Is OSR "trusting the operator"? | No. Selection is operator config, but authority is the sealed-profile content walk, INV-F5A-R1, and the at-instant pins and re-proofs. The same accepted residual applies as for every launch. OSR-6 rules out AIDO-caused mutation of the shared root |
| Why not A-1, if O1 is probably the truth? | A-1 needs P-B, which can only be assumed, and RPR exposes hundreds of content-bearing creates per run to it. OSR needs no such premise. The task's rule rejects A-1 as an immediate authorization on exactly that basis |
| Did FU2 run experiments or edit frozen text? | No. It made three public documentation reads plus code reads. Only this non-frozen file changed |
