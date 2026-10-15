# Phase 5F3B-CFG1-F5A — No-Redirect API Architecture Review (vs. PPS)

```text
STATUS         NON-FROZEN decision record. Amends nothing. Authorizes nothing. Grants no residual.
BASE HEAD      39d81bac799d33cba66c38e09fb6588122d39fb6 (tracked tree clean)
PRESERVED      docs/PHASE_5F3B_CFG1_F5A_AUTHORITY_ARCHITECTURE_SELECTION.md (PPS / TP-1 candidate) and
               docs/PHASE_5F3B_CFG1_F5A_FINAL_QUALIFICATION_DECISION.md (FU2) are untracked and UNCHANGED.
               PPS stays on record as the comparison candidate and as the fallback named in §8.
F5-A           NOT ACCEPTED, NOT FROZEN. HOLD.
DECISION       A. NO-REDIRECT API REDESIGN VIABLE, with one binding refinement (§2.4) and one
               reviewer decision (DEC-NR, §7). Recommended next: ONE bounded, document-only
               design-amendment phase (NR-A, §9). Implementation and live execution: NOT authorized.
LIVE           BARRED. Both barriers unchanged: run_executor.py:2153 (provision_runtime =
               live_runtime_provisioning_not_qualified) and run_executor.py:1970 (_build_supervisor refuses).
EXECUTED       No filesystem experiment of any kind. No junction, conversion, race, hard link, escape,
               service, ACL change, Pi, Node, model, backend or credential. No code, test, frozen-text or
               CLAUDE.md change. Code and document reads; the public documentation reads in §1; and one
               read-only GetProcAddress lookup of kernel32 export names on this host (§1.4), with no call
               to any of them.
```

## 0. The question, and the short answer

**Question.** Windows 11 24H2 added documented Win32 creation APIs that refuse path redirection. Do they give a simpler, mechanically supportable closure for F5-A, L9 and L11 than the Protected Provisioning Service (PPS)?

**Short answer.**

- **Yes, the no-redirect contract is the right tool.** It turns the one escape mechanism on record (R1-FU3: a pathname create through a converted empty directory lands outside `R`) into a documented **refusal**. It also dissolves FU2's irreducible first-child problem (DEC-FC) without an occupant, a link-set gate or a new residual.
- **But the 24H2 Win32 entry points are the weaker binding of that contract.** `CreateDirectory2W` and `CreateFile3` take only a full pathname. Each call therefore re-parses the DOS device namespace and every ancestor. Microsoft documents the **same** outcome contract for handle-relative creation through `OBJECT_ATTRIBUTES.OBJ_DONT_REPARSE`. That form needs neither premise, and it is the shape F5-A already uses (§2.4).
- **The 24H2 APIs add no concurrency statement that `OBJ_DONT_REPARSE` lacks.** So FU2's rejection of A-1 (P-B, "linearizability … assumed") must be decided the same way for both. §3 argues that P-B is **not a premise at all**. Only the reviewer can confirm that (DEC-NR). If the reviewer refuses it, the API route fails for both bindings and the result becomes **B, PPS preferred** (§8).

## 1. Authoritative API evidence

### 1.1 What the 24H2 pages publish (all `ms.date` 2025-04-10)

| Page | Normative text relied on |
|---|---|
| `CreateDirectory2W` | Signature returns `HANDLE`, with `dwDesiredAccess`, `dwShareMode`, `DirectoryFlags` and `lpSecurityAttributes`. `DIRECTORY_FLAGS_DISALLOW_PATH_REDIRECTS 0x00000001`: "Prevent *lpPathName* from being redirected by reparse points or symbolic links." `ERROR_ALREADY_EXISTS`: "The specified directory already exists." The security descriptor is applied to the new directory. Minimum: Windows 11 24H2 / Server 2025 |
| `DIRECTORY_FLAGS` | `DIRECTORY_FLAGS_DISALLOW_PATH_REDIRECTS`: "Prevent specified path name from being redirected by reparse points or symbolic links." |
| `CreateFile3` | "behaves exactly the same way as CreateFile2 with one exception; operations **can** fail if *lpFileName* is redirected via a reparse point or symbolic link." `ERROR_PATH_REDIRECTED`: "*lpFileName* was redirected by reparse points and/or symbolic links." `CREATE_NEW`: "If the specified file exists, the function fails … `ERROR_FILE_EXISTS` (80)." It cannot create directories ("only `OPEN_EXISTING` is valid" for that use) |
| `CREATEFILE3_EXTENDED_PARAMETERS` | `FILE_FLAG_DISALLOW_PATH_REDIRECTS 0x00010000`: "Prevent paths from being redirected by reparse points or symbolic links." `lpSecurityDescriptor` is applied on creation and ignored on open |
| `RemoveDirectory2W` / `DeleteFile2W` (read for completeness) | `RemoveDirectory2W`: "This function will fail if **any part** of *lpPathName* is redirected via a reparse point or symbolic link." This is the only page that says "any part" |

### 1.2 Documentation defects (recorded, not resolved)

| # | Defect | Consequence |
|---|---|---|
| D-1 | The `CreateDirectory2W` signature returns `HANDLE`, but its *Return value* section says "nonzero" / "zero". The `A` variant says "nonzero" / `INVALID_HANDLE_VALUE` | Success and failure detection for the Win32 directory binding rests on an inconsistent page |
| D-2 | The sample passes **six** arguments to a five-parameter function. It also uses `DIRECTORY_FLAGS_NONE` plus a `CreateFile3` **without** the flag, while its comment claims the directory "can't be deleted and redirected" | Non-normative. What the comment describes comes from the share mode, not from the flag |
| D-3 | `CreateDirectory2W` omits `ERROR_PATH_REDIRECTED`. The `A` page lists it against a parameter that does not exist (`lpNewDirectory`) | The refusal code for directory creation is not stated consistently |
| D-4 | Modal strength varies: "**can** fail" (CreateFile3 remarks), "Prevent" (flag tables), "**will** fail if any part" (RemoveDirectory2W) | The CreateFile3 contract is read here as the flag-table *outcome* statement. §3 states that reading explicitly as DEC-NR |
| D-5 | "Symbolic links" is undefined. Microsoft's own `DefineDosDevice` remarks say "MS-DOS device names are stored as **junctions in the object namespace**" | Whether the flag covers object-manager links (drive letters, device map) is **not** established (§2.3) |
| D-6 | The `CreateDirectory2W` access table lists only `FILE_LIST_DIRECTORY`, `FILE_TRAVERSE` and `SYNCHRONIZE` | F5-A's directory pin also needs `FILE_READ_ATTRIBUTES`; that is not documented for this API |

### 1.3 What the published contract guarantees, and what it does not

| Guaranteed by published text | **Not** guaranteed by any published text |
|---|---|
| With the flag, a call that would be redirected by a reparse point or symbolic link fails (`ERROR_PATH_REDIRECTED`) instead of being redirected | **Atomicity or concurrency.** No sentence addresses a conversion racing the call. (§3 explains why containment does not need one) |
| `CREATE_NEW` refuses an existing name, including a pre-planted link name | **Hard links.** A hard link is not a redirect. The flag says nothing about aliases added before or after the call |
| A handle is returned with the caller's access and share mode, and the security descriptor is applied at birth | **Ordinary-directory substitution.** A renamed-and-replaced plain directory is not a redirect. The flag does not detect it |
| Minimum Windows 11 24H2 / Server 2025 | **Object-manager namespace.** Device-map and drive-letter links are not addressed (D-5) |
| — | **Filter-driver virtualization** (bind links, ProjFS, cloud files) and remote file systems. The support tables list SMB/CsvFS/ReFS but say nothing about redirect semantics there |
| — | **Parent identity.** Nothing says the new object's parent is a particular directory **object**, only that the **name** was not redirected |

### 1.4 Host facts (read-only)

On this host (Windows 11 Enterprise, build **26200**), `kernel32` exports `CreateDirectory2W`, `CreateDirectory2A`, `CreateFile3`, `DeleteFile2W` and `RemoveDirectory2W`. This was checked by `GetProcAddress` only; none of them was called. The Windows SDK headers are not installed, so constant values come from the pages above.

### 1.5 The handle-relative sibling (already in the record)

| Page | Normative text relied on |
|---|---|
| `OBJECT_ATTRIBUTES` (ntdef, `ms.date` 2023-08-09) | `OBJ_DONT_REPARSE`: "If this flag is set, no reparse points will be followed when parsing the name of the associated object. If any reparses are encountered the attempt will fail and return an `STATUS_REPARSE_POINT_ENCOUNTERED` result. This can be used to determine if there are any reparse points in the object's path, **in security scenarios**." `RootDirectory`: if non-NULL, "*ObjectName* specifies an object name relative to the *RootDirectory* directory" |
| `NtCreateFile` (winternl, updated 2025-08-15) | "the user-mode equivalent to the `ZwCreateFile` function". `RootDirectory`: "the `ObjectName` member specifies a file name relative to this directory". `FILE_CREATE`: "If the file already exists, fail the request and do not create or open the given file". "`NtCreateFile` never returns `STATUS_REPARSE`." The winternl page lists only `OBJ_CASE_INSENSITIVE` among file-object attributes, so the `OBJ_DONT_REPARSE` binding rests on the `OBJECT_ATTRIBUTES` page plus the Zw equivalence (obligation Q-3) |
| `DefineDosDevice` / *Defining an MS-DOS Device Name* | "Drive letters and device names defined at system boot time are protected from redefinition and deletion unless the user is an administrator." A non-LocalSystem caller cannot define a local name "if that device name already exists in your Local or Global MS-DOS Device namespaces." These are contracts of **that API**, not of the namespace |
| `CreateBindLink` | "can only be called by a user with Administrator privileges". Bind links are a non-reparse redirect, so they sit in §37.1's unchanged **out-of-scope** (elevated) class |

## 2. The two bindings

### 2.1 NR-W: 24H2 Win32 pathname binding

`CreateDirectory2W(path, …, DISALLOW_PATH_REDIRECTS, SA)` returns the directory's pin. `CreateFile3(path, …, CREATE_NEW, {FILE_FLAG_DISALLOW_PATH_REDIRECTS | FILE_FLAG_OPEN_REPARSE_POINT, SA})` creates each file.

### 2.2 NR-N: handle-relative binding (recommended)

`NtCreateFile(RootDirectory = held parent handle, ONE validated component, FILE_CREATE, OBJ_CASE_INSENSITIVE | OBJ_DONT_REPARSE, …)`. This is exactly F5-A's existing `_native_relative_create` (`pi_runtime_provision.py:871`) plus one documented attribute bit. A directory create returns its own pin, as F5-A already does.

### 2.3 Why NR-W is the weaker binding

| Premise needed for "the new object is in `D`" | NR-W | NR-N |
|---|---|---|
| No reparse is followed | Flag (§1.1, with D-4) | `OBJ_DONT_REPARSE` (§1.5) |
| The DOS device namespace resolves the drive letter to `R`'s volume and path | **Needed on every create.** Same-user shadowing through the documented API is refused (§1.5), but native object-manager operations on the per-logon namespace are undocumented, and D-5 leaves open whether the flag covers object-manager links | **Not needed.** No name above `D` is parsed |
| Every ancestor of `D` is the expected object | W2 (held `R`, held `D`) plus W6 (no ancestor rename while a descendant handle is open), both frozen | **Not needed.** The parse starts at the `D` **object** |
| Success and failure detection is unambiguous | D-1/D-3 for directories | Documented `NTSTATUS` plus `IoStatusBlock.Information == FILE_CREATED` (already checked at `pi_runtime_provision.py:922`) |
| Directory pin access includes `FILE_READ_ATTRIBUTES` | D-6 | Documented |

**Consequence.** The 24H2 APIs confirm that Microsoft supports no-redirect creation as a security primitive, and NR-W is a coherent fallback. NR-N establishes the same property with **fewer** premises and **less** code change. The recommendation is NR-N, with NR-W recorded as the alternative if the reviewer will not accept a native API (§7, DEC-NR-B).

### 2.4 Binding refinement, stated once

The redesign **adapts** the existing native construction. It does **not** replace it with `CreateFile3`/`CreateDirectory2W`. Replacing it would trade a handle anchor for hundreds of full-path parses per run (F5-A peak 449 entries). It would also add the device-namespace premise and the D-1/D-6 defects, and buy nothing in return.

## 3. Independent security reasoning: why no linearizability premise is needed

FU2 rejected A-1 because P-B, "linearizability of a create against a concurrent conversion", is "assumed, never establishable". The 24H2 pages publish no concurrency statement either. **If P-B were truly required, both bindings would fail identically.** It is not required, for the following reason.

**Claim (NR-N).** A successful `NtCreateFile(RootDirectory = h_D, n, FILE_CREATE, OBJ_DONT_REPARSE)`, with `n` one validated component, creates an object whose only AIDO-authored name is `n` in `D`'s own index. A failed call creates nothing that AIDO authored.

1. **Published:** the name is parsed relative to the directory represented by `h_D`, a fixed object. A held handle is never rebound to another directory.
2. **Validated:** `n` is a single component, with no `..`, `:`, separator or device name (`require_single_component`, `pi_runtime_provision.py:151`). The parse has exactly one step, from `D`.
3. **Published:** to place the object anywhere other than `D`, that step would have to be **re-issued against another name**. That is precisely what a reparse is, and `OBJ_DONT_REPARSE` forbids following one ("If any reparses are encountered the attempt will fail").
4. Hence, **in every interleaving** with a concurrent conversion of `D`, one of two things happens. Either the call fails, or it completes without following a reparse, which places the object in `D`. No ordering assumption is used. The contract constrains the call's **outcome**, not a check that could be raced.
5. **Published (FU2 §6.1):** a non-empty directory cannot be converted. Once any child exists, `D` stays as it is.
6. **The odd interleaving, closed by a check.** It is conceivable that `D` acquired a reparse point while the first child was being inserted. The child is still in `D`'s own index, so containment is unaffected. `D` would then **redirect pathname consumers**, though. The gate therefore re-checks "`D` is plain", **from `h_D`**, after the last child exists (FU2's G-C1). After that, (5) keeps `D` plain for as long as it is non-empty.

The same argument holds for NR-W **per component**, with two extra premises: the device namespace, and the ancestors W2/W6 protect (§2.3).

**What this replaces.** A2-3 (O1 vs O3) and A2-6 (racing conversion) stop being qualification gates. O3, the escape, is excluded by contract, not by measurement. R1-FU3 stands unchanged as a fact. Under NR its consequence is a **refusal** (zero objects created), not an escape.

This is the one point the reviewer must accept or reject: **DEC-NR** (§7).

## 4. The three consumers

### 4.1 F5-A (L3R runtime construction)

| Requirement | Under NR-N |
|---|---|
| AIDO-minted root authority | Unchanged: `_consume_authority`, a registry-minted workspace, and the `R` identity proof at `_pin_run_root` (`:939`) |
| Exact creation identity | Unchanged: `STATUS_SUCCESS` **and** `FILE_CREATED`, then the object's identity from its own handle (`:902`–`:937`) |
| Exact-set parentage gates | **Kept** (`:967`, `:986`). Their role changes from *escape detector* to *foreign-name and kind refusal*. Escape is excluded by §3 |
| Creating-handle byte writes plus digest verification | Unchanged (`:1040`) |
| Sealed-profile identity | Unchanged: the PI-PC1 walk and post-pin re-walk |
| Lifecycle and cleanup truth | Unchanged. L3R still deletes nothing. §18 row 22, T-F5A-25 and §7.4A.4 ("no write can leave `R`") become **assertable by construction**, where FU2 §2.2 had to call them unassertable |
| Construction geometry and bounded handles | Unchanged: the same create count, the same held handles, peak 449 ≤ 462 (68ae5b0) |
| R-ALIAS for runtime files | Only **actor-authored** aliases can exist (Y-6, after creation). That is AMEND2 §13's accepted class, and it carries approved public bytes. FU2 §2.1 needs an AIDO-authored outside name (O3), which no longer exists |
| Code delta | One documented attribute bit in `_native_relative_create` (`:890`), plus the G-C1 re-check where not already present |

No OSR, no PE-1 selection change and no PPS staging are needed. RPR (A2-R1) is kept.

### 4.2 L9 (endpoint writer, FU15 §37.3.1)

| Current step | Under NR-N | Effect |
|---|---|---|
| Step 3: pathname `mkdir` (`cfg1_pi_config.py`, `Path(config_dir_str).mkdir`), then step 4 pins it | `D` is created **relative to `h_R`**, returning its own pin (FU2 K3's shape) | **R-WINDOW retired.** There is no create→pin interval. §37.3.6's "one residual" and D-A dissolve |
| Step 6: `create_exclusive_child` (`win_config_authority.py:964`), a pathname `CreateFileW(CREATE_NEW, OPEN_REPARSE_POINT)` | Relative `FILE_CREATE` from `h_D`, share 0, the same access | **External create (L9-1, L9-4) excluded by contract.** A converted empty `D` yields a refusal with nothing created |
| Step 7: `prove_config_parentage` (`:805`) | Kept, plus "`D` plain from `h_D`" after the last child | The §2.1 alias needs an AIDO-authored outside name, and none can exist. **L9-3 closed** |
| Step 8: endpoint bytes through `models.json`'s creating handle | Unchanged | Credentials are written only into an object whose AIDO-authored name is proven inside `D` |
| Dispositions (`:506`, `:616-617`) | **Removed** (CFG1-K1 / AMD-K-3, pure subtraction) | **L9-2 closed.** Which link a handle disposition removes is undocumented, so NR does not rely on it |
| AMEND2 RETAIN / SCRUB-C / SCRUB-R / RELEASE-R and the bool formulas | **Unchanged.** The scrub is object-bound through the creating-handle lineage (AMD2-4) | Frozen failure semantics preserved, except "then dispositions" (AMD-NR-4) |

### 4.3 L11 (token-bearing extension writer)

L11 differs from L9 in four ways. It has more children (the verified sources plus `ar2_config.ts`). The **token is written last** (E8). Only the token child is retained (E9a). Issuance registration takes ownership of the retained handle (E10).

| Current step | Under NR-N |
|---|---|
| E3 pathname `mkdir` (`cfg1_extension.py`) → E4 pin | `D_ext` created relative to `h_R`, returning its own pin. R-WINDOW-E retired |
| E6 every child via `create_exclusive_child` | Every child relative from `h_D_ext`, share 0. The token child is still created last and stays empty until E8 |
| E7 gate | Kept, plus "`D_ext` plain" after the last child |
| E8–E10 content, read-back, RETAIN (token only), issuance | Unchanged. The ordering (verified sources, then token last) and the issuance/scrub lifecycle are untouched |
| E11 dispositions (`:385`) | **Removed.** The token scrub through the creating handle stays first, exactly as frozen |

The token is never written into an object that has an AIDO-authored outside name. After E8, `D_ext` holds the token object under its inside name only, plus any actor-added alias. That alias is R-ALIAS, actor-authored and accepted, and the token is scrubbed through the creating lineage on failure, as today.

## 5. Per-approach security answers

| Question | NR-N (recommended) | PPS (TP-1) |
|---|---|---|
| Who creates every resource? | The AIDO executor (`S_op`), relative to handles it holds, under the registry-minted `R` | The PPS (`S_svc`), under admin-created `P`. The executor creates nothing protected |
| Who can mutate it **before** creation? | Any same-user process can add names to `R`/`D`. A collision makes `FILE_CREATE` fail. Foreign names fail the exact-set gate. Conversion of an empty `D` makes the create fail | No one but `S_svc` (F2), **if** TPC-1/TPC-2 hold |
| … **during** creation? | A conversion race leaves the object in `D` or the call fails (§3). The odd interleaving is caught by the plain re-check | No same-user path (DACL) |
| … **after** creation? | Held share-0 files cannot be opened for write or delete. The actor can read them, and can add hard-link aliases (Y-6). After release: R-SLIVER/R-ABA at-instant residual, unchanged | The actor can read after the grant, and can alias (same DACL). It cannot write |
| What proves identity and authorized parent? | Identity: the creating handle plus `FILE_CREATED`. Parent: published relative-parse semantics plus `OBJ_DONT_REPARSE` (§3). Membership and kind: the exact-set gate on the held parent | Identity: the executor's own walk. Parent: F4/F5 inside `P` plus the access check. Service identity: F1, which rests on a **non-normative** source (PPS §1.4) |
| Can a create reach an out-of-root target before a later gate? | **No**, given DEC-NR. Without DEC-NR: unproven, exactly as in FU2 | No, given TPC-1/TPC-2, F1 and the PPS code (TCB by installation) |
| Can ordinary-directory substitution bypass it? | NR-N: no name above `D` is parsed, so there is nothing to substitute. NR-W: excluded only via W2/W6, plus the device-namespace premise | No: `S_op` cannot rename inside `P` (DACL) |
| What does a hard-link alias change? | An alias added by the actor is actor-authored (AMEND2 §13). It cannot redirect a `FILE_CREATE`. It exposes content, which is already a non-claim. No AIDO-authored outside name can exist | The same. The alias carries the same DACL, so it grants no write |
| Can cleanup affect an unauthorized object? | No disposition (K1). The scrub touches only AIDO's creating lineage (AMD2-4). L27 removes names inside `R` only (frozen, unchanged) | The PPS deletes by name inside `P` only. That ownership depends on the PPS ledger, its restart and orphan recovery, and its code (TCB) |
| Are credentials ever written to an unproven target? | No. They are written after the gate, through the creating handle, into an object whose only AIDO-authored name is in `D` | No, provided F1 holds before any secret byte. F1's proof source is non-normative |
| Can a supported caller misuse a trusted service? | **No trusted service exists.** The creation primitives stay private; there is no public path-accepting callable (existing static guarantee) | **Yes, within its own run.** Every `S_op` process is a legitimate client, indistinguishable from the executor. It can open runs, consume quota (DoS) and read its own grants. Per-connection run binding and cross-run isolation must be **designed and proven**; TPC-1/TPC-2 do not prove an IPC request is authorized |
| What must the consumption boundary revalidate? | L14 re-proof and L21A, unchanged. For config dirs: `D` plain and non-empty, the exact set, and child ids equal to the retained identities | Executor admission §2.4 (F1–F3, the access rule, owner == `S_svc`), plus that the run is bound to its **own** connection |

## 6. Comparison against PPS

| Dimension | NR-N | PPS |
|---|---|---|
| Security proof obligations | Q-1…Q-5 (§7). One evidentiary decision (DEC-NR); no measurement | F1–F5, TPC-1, TPC-2, plus the gaps this review adds: genuine service authentication (F1 rests on a non-normative owner-setting claim); binary, interpreter, import-path, SCM-DACL and registry provenance; pipe-instance squatting before service start; same-user client indistinguishability; per-connection run binding; cross-run isolation; ledger, restart and orphan-cleanup ownership; quotas |
| New trusted components | **None** | A Windows service (new capability class needing CLAUDE.md-level authorization), an installer, an admin-created `P` and a service SID |
| Frozen-contract changes | AMD-NR-0…5 (§9). Narrow: one evidentiary rule, a mechanism swap inside the existing L3R/L9/L11 steps, and disposition removal | AMD-PPS-0…7. Broad: §37.1 trusted base, F5-A §6–§11, PE-1, FU15 §37.2–§37.3, the L11 E-sequence, AMEND2 §9/§10, L12, L24 and L27 |
| OS and deployment prerequisites | A Windows build where `OBJ_DONT_REPARSE` is honored (Q-3/Q-4), and `R` on a **local NTFS** volume. No admin; the operator's privileges are unchanged (§37.1 excludes elevated actors, as frozen) | An admin-installed service, a standard-user operator (TPC-2; **not checked** for the target account), and a protected path layout |
| Implementation complexity | Small. F5-A: one attribute bit. L9/L11: two pathname calls each become relative creates (reusing the F5-A primitive), dispositions are deleted, and one gate re-check is added | Large: a service core, protocol, ledger, staging, a pipe server with owner verification, an installer, executor integration, and an admission verifier |
| Review and qualification cost | One document amendment plus one offline phase. **No** conversion, race or hard-link qualification run is needed for acceptance | PPS-1…PPS-5, including adversarial qualification on an administrator-provisioned machine |
| Impact on reaching a human-supervised Alpha | Removes the F5-A, L9 and L11 blockers by contract once DEC-NR is adopted. Live still needs E5 conditions 1, 6, 8, 9 and a fresh live authorization | Blocked until a platform administrator provisions TPC-1/TPC-2 on the target host. If that is unavailable, a definitive HOLD (PPS §1.3) |

The 5F2C → 5F2D → 5F2E → human path does not depend on any of this, under either candidate.

## 7. Remaining obligations of NR (explicit)

| Id | Obligation | Kind | How it closes |
|---|---|---|---|
| **DEC-NR** | Accept that a published per-call **no-redirect outcome contract** (`OBJ_DONT_REPARSE`; for NR-W, the 24H2 flag), combined with published relative-parse semantics, is sufficient for P1/P2 of a single-component create under concurrent same-user mutation, **without** a linearizability premise (§3) | Reviewer decision | Yes → A stands. **No → NR fails for both bindings → B** (§8) |
| DEC-NR-B | Binding choice: NR-N (recommended), or NR-W if a native API is unacceptable. NR-W additionally needs a decision on the device-namespace premise (§2.3) and acceptance of D-1/D-3/D-6 | Reviewer decision | Recorded in NR-A |
| Q-1 | Every create in L3R, L9 and L11 is relative, single-component, `FILE_CREATE`, with `OBJ_DONT_REPARSE`. No pathname create survives in the three writers | Static (code review plus sweep test) | NR-1 tests |
| Q-2 | `D` is re-checked plain **from `h_D`** after the last child exists, before any content (§3 step 6) | Static plus synthetic `tmp_path` test | NR-1 |
| Q-3 | Documentation chain: `OBJ_DONT_REPARSE` is documented on `OBJECT_ATTRIBUTES` for `ZwCreateFile`, and `NtCreateFile` is its documented user-mode equivalent. The winternl page lists only `OBJ_CASE_INSENSITIVE` | Reviewer acceptance of the citation chain | NR-A |
| Q-4 | **No silent ignore.** An OS that did not honor the bit would void the guarantee without any visible error. NR-A must choose one: (a) a version floor (for example ≥ 24H2 build 26100) taken as sufficient; or (b) a read-only runtime positive control that refuses on doubt (for example, opening a pre-existing OS junction with the bit must fail with `STATUS_REPARSE_POINT_ENCOUNTERED`). (b) creates and converts nothing, and is **not** executed here | Reviewer decision | NR-A |
| Q-5 | Admission refuses unless `R`'s volume is **local NTFS** (`GetVolumeInformationByHandleW` on `R`'s pin, plus a remote-protocol refusal). This removes the remote and filter semantics §1.3 leaves undocumented | Static plus synthetic test | NR-1 |
| — | **Out of scope, unchanged (§37.1):** administrator-only redirectors (bind links, global DOS devices, mount manager, filter drivers) and elevated actors. FU2's E-TOKEN stays as **hygiene, not justification** | — | Stated, not amended |
| — | L2-Q (the L2 creator's pathname creates) remains an inherited observation, not decided here | — | Unchanged |

## 8. Decision

**A. NO-REDIRECT API REDESIGN VIABLE.**

- The no-redirect contract gives a coherent, documentation-backed argument for P1, P2 and P3 across F5-A, L9 and L11. It needs no new trusted component, no occupant, no link-set gate and no new residual (§3–§5).
- **The binding is NR-N**, the documented handle-relative `OBJ_DONT_REPARSE`. The 24H2 `CreateDirectory2W`/`CreateFile3` (NR-W) are a valid fallback with two extra premises. They are the evidence that prompted this review, but not the best implementation of it (§2).
- **It rests on exactly one reviewer decision, DEC-NR.** If the reviewer holds that an outcome contract still needs a linearizability proof, the exact contradiction is this: the property P1 requires (no AIDO-authored object outside `R`, under concurrent conversion) would then need a concurrency statement **that no published page for either binding provides**. The API approach would be unable to establish P1, and the decision becomes **B. PPS PREFERRED**, subject to its own authorization, TPC-1/TPC-2, and the additional obligations in §5–§6.
- Nothing is implemented, and nothing live is authorized.

**Superseded on adoption:** FU2's DEC-FC, R-FIRST-CHILD, the K2–K8 occupant sequence and OSR; A2-3/A2-6 as qualification gates; AMD-PPS-0…7 (PPS kept as the fallback). **Kept:** CFG1-K1 (disposition removal), AMEND2's scrub, and every accepted offline implementation and evidence commit.

## 9. Next phase

### NR-A: No-Redirect Design Amendment (document-only)

**Deliverable.** One non-frozen amendment proposal with the following parts:

| Id | Content |
|---|---|
| AMD-NR-0 | The DEC-NR evidentiary rule, worded exactly as in §7 and scoped to single-component relative creates |
| AMD-NR-1 | F5-A §7.4A.2: `OBJ_DONT_REPARSE` is added to the native relative create. A2-3/A2-6 are retired as gates. P-R1-4(iv) is re-disposed. §18 row 22, T-F5A-25 and §7.4A.4 are re-based on §3 |
| AMD-NR-2 | FU15 §37.3.1 steps 3–7: a relative directory create returns the pin; relative children; fact 7 → fact 7″ (§3); §37.3.3 and §37.3.4 rows 2 and 4 are re-based; R-WINDOW and D-A are withdrawn |
| AMD-NR-3 | L11 E3–E7: the same change. The token ordering, RETAIN and issuance stay unchanged |
| AMD-NR-4 | AMEND2 §9 "K": "then dispositions" is removed (= FU2 AMD-K-3). SCRUB, RELEASE-R and the bool formulas are unchanged |
| AMD-NR-5 | Admission: local NTFS (Q-5); the Q-4 choice; E-TOKEN as hygiene |

**Hard acceptance bar (all required):**

1. Every P1/P2/P3 step cites either a published Microsoft sentence (page and date) or a frozen W-fact. **No step cites a measurement**, and none assumes linearizability.
2. DEC-NR is posed as **one yes/no reviewer question**, with both consequences written out (A → NR-1; no → B).
3. Every frozen surface touched is listed with its exact before and after. Nothing outside AMD-NR-0…5 changes. The AMEND2 scrub and frozen failure codes are untouched except "then dispositions".
4. The out-of-scope redirect classes (§7) are enumerated under the **unchanged** §37.1. No threat-model narrowing, and no new residual.
5. NR-1 (the later offline implementation) is specified to the test level. It must include: the static sweep (Q-1); no disposition call in L9/L11; the plain re-check (Q-2); the local-NTFS refusal (Q-5); synthetic `tmp_path` only; **no junction, conversion, race or hard-link fixture**; both live barriers asserted unchanged; and the full offline suite green with the standard deselections.
6. No code, test, frozen-text or CLAUDE.md change, and no Windows experiment, in NR-A itself.

**Recommended model:** Claude Opus 5.5, high effort. The phase edits a security argument across frozen surfaces, where precision of wording is the deliverable.

## 10. Adversarial review of this record

| Challenge | Answer |
|---|---|
| Isn't this A-1 again, rejected in FU2? | A-1 was framed as **measured** P-A/P-C plus an **assumed** P-B. NR uses no measurement, and §3 shows P-B is not a premise: escape requires following a reparse, which the documented contract forbids in every interleaving. Whether that reading is acceptable is put to the reviewer as DEC-NR, not presumed |
| Does the 24H2 page prove more than `OBJ_DONT_REPARSE`? | No. Both are outcome statements without a concurrency clause. The 24H2 pages are thinner and partly inconsistent (D-1…D-6) |
| Does the flag stop hard-link aliasing? | No, and no claim here says it does. Aliases are not redirects. NR's point is narrower: AIDO never **authors** an outside name, so only actor-authored aliases (AMEND2 §13) remain |
| Ordinary-directory substitution? | NR-N parses no name above the held `D`. NR-W relies on frozen W2/W6 for it, plus the device-namespace premise. That is why NR-W is not recommended |
| Can the actor convert `D` and break a run? | Yes, before the first child. The result is a **refusal** with nothing created, which is a legitimate fail-closed answer, never an escape |
| Unsupported file systems? | Refused at admission (Q-5). No claim is made for them |
| Was anything executed or edited? | No experiment; no code, test, frozen or CLAUDE.md change. One `GetProcAddress` lookup of export names (§1.4). This file is the only change |
