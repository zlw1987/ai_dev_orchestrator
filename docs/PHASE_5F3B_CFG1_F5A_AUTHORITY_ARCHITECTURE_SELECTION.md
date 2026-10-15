# Phase 5F3B-CFG1-F5A — Final Authority Architecture Selection (TP-1: Protected Provisioning Service)

```text
STATUS         NON-FROZEN decision record. Amends nothing. Authorizes nothing. Grants no residual.
BASE HEAD      39d81bac799d33cba66c38e09fb6588122d39fb6 (tracked tree clean; the FU2 decision record
               docs/PHASE_5F3B_CFG1_F5A_FINAL_QUALIFICATION_DECISION.md is untracked and unchanged)
RELATION       Keeps FU2's HOLD / EXTERNAL AUTHORITY disposition and its §0–§6 analysis.
               SUPERSEDES FU2 §7.2, §7.3, §8 (DEC-FC), §9 (AMD-K-*, AMD-OSR-*) and §10.
F5-A           NOT ACCEPTED, NOT FROZEN. HOLD.
DECISION       ARCHITECTURE SELECTED: TP-1, a separately installed Protected Provisioning Service (PPS)
               running under its own service SID. It is genuinely capable of the required invariants,
               ON CONDITION of two trusted-platform capabilities AIDO cannot create for itself (§1.3).
               Adoption still needs the reviewer's amendment decision (§6) AND a platform administrator.
               Until both exist: HOLD.
LIVE           BARRED. Both barriers unchanged: run_executor.py:2153 (provision_runtime =
               live_runtime_provisioning_not_qualified) and run_executor.py:1970 (_build_supervisor refuses).
EXECUTED       Nothing. No filesystem experiment, no ACL change, no service, no Pi/Node/model/credential.
               Code and document reads, plus the public documentation reads in §1.4.
```

## 0. The two blockers, accepted

| Blocker | Accepted consequence |
|---|---|
| **B1.** A hard-link enumeration cannot prove the link set is stable. Y-6 allows link creation against a share-0 handle | FU2's **link-set gate (LG) is withdrawn**. No claim in this record depends on enumerating links, on `NumberOfLinks`, or on the absence of an alias at any instant |
| **B2.** A sentinel created in a directory that is itself in the conversion window cannot prove its own initial condition | FU2's **K2–K7 occupant sequence, R-FIRST-CHILD and DEC-FC are withdrawn**. No claim here depends on an AIDO-created occupant, or on any create into a directory a same-user actor could convert |

Both failures have the same cause. Every proof FU2 tried was a **post-create observation inside a namespace the adversary can also write**. A same-user actor holds the same token as AIDO, so DACLs are symmetric (FU2 §6.2), and an observation can only ever describe one instant. The only way out is to make the namespace **asymmetric before the first create**. Authority then comes from the access check the OS performs on every operation, not from anything AIDO observes afterwards.

## 1. Selected architecture: TP-1, Protected Provisioning Service (PPS)

### 1.1 Shape

```text
 operator logon session (SID S_op)                     | service logon session (SID S_svc)
                                                       |
 AIDO executor ── authenticated local pipe ──────────► | PPS (NT SERVICE\<name>, installed by an admin)
   · renders bytes (env-sourced secrets, unchanged)    |   · creates/writes/seals/tears down ONLY under P
   · verifies everything itself (§3, §2.4)             |   · opens nothing outside P, reads no user path
   · launches Pi as S_op (barriers unchanged)          |   · runs no code, spawns no process
                                                       |
 Pi (S_op) reads P\runs\<id>\{runtime,pi_agent,ext} ◄──┘   P = admin-created, protected DACL, owner S_svc
```

- **P** is a protected root created by an administrator at install time. It is owned by `S_svc`. Its DACL is protected (no inheritance) and grants `S_op` nothing that writes, deletes or relabels.
- **The PPS** is a minimal Windows service running as a virtual service account (`NT SERVICE\<name>`, with a distinct, documented service SID). It is the **only** principal that creates, writes, scrubs or removes anything under P.
- **The executor** stays the content authority. It renders the bytes, proves identity against the sealed profile, and checks every protection fact itself. It trusts **no claim** from the PPS, from Pi or from a model.
- **Pi** still runs as `S_op`, under the unchanged launch path and barriers. It consumes the provisioned resources **read-only**.

### 1.2 Why a separate identity, and only that, works

| Candidate | Why it fails or works |
|---|---|
| A helper under `S_op` | Same token as the actor, so its DACLs and handles are symmetric. **Not a solution** (task rule; FU2 §6.2) |
| An elevated helper under the same user (UAC High IL) | Microsoft's servicing criteria: UAC is "defense-in-depth", **not a security boundary**, and "administrative processes and users are considered part of the TCB". A same-user actor's path to elevation is therefore not a boundary AIDO may rest on |
| AppContainer / restricted token for the **actor** | AIDO cannot impose a token on an arbitrary same-user process. It does not bound the §37.1 actor |
| **A different user principal** (`S_svc`) | **The user boundary is a serviced security boundary** (servicing criteria). `S_op` cannot obtain `S_svc`'s token, cannot open its process, cannot set an object's owner to `S_svc` without `SeRestorePrivilege`, and is refused by the kernel's access check on every object whose DACL grants it nothing. **Selected** |

### 1.3 Trusted-platform capabilities (preconditions AIDO cannot supply)

| Id | Capability | Who provides it | How AIDO checks it (mechanically, refusing on doubt) |
|---|---|---|---|
| **TPC-1** | A PPS installed by an administrator who is **not** the operator's identity. Service binary, interpreter, every import path, service config, service registry key and P's DACL are writable only by Administrators, SYSTEM or `S_svc`. The service's SCM DACL denies `S_op` `SERVICE_CHANGE_CONFIG` | Platform administrator (out-of-band) | Pipe owner == `S_svc` (§2.2 F1). Admission (§3) of P and its chain. The service's own code integrity is **TCB by installation**, not by AIDO proof; this is stated, not hidden |
| **TPC-2** | The operator account is a **standard user**: no `BUILTIN\Administrators` membership in any form (enabled or deny-only), no linked token (`TokenElevationType` must be `Default`, `TokenElevation` false), and none of `SeBackup`, `SeRestore`, `SeTakeOwnership`, `SeDebug`, `SeTcb`, `SeManageVolume`, `SeLoadDriver`, `SeImpersonate`, `SeAssignPrimaryToken`, `SeCreateToken`, `SeRelabel`, `SeSecurity` present in the token at all | Platform administrator | `GetTokenInformation` (`TokenGroups`, `TokenPrivileges`, `TokenElevationType`, `TokenElevation`) on the executor's own token, and on the pipe client's token at the PPS. Any hit refuses. This replaces FU2's E-TOKEN with a strictly stronger rule |

**If either capability is unavailable on the target machine, the result is a definitive HOLD**, and the missing capability is exactly: *a principal distinct from the operator that the operator cannot assume, administer or elevate into, which owns the namespace where AIDO's protected objects are created.* No AIDO-side mechanism substitutes for it. Whether the current development account meets TPC-2 was **not checked** here.

§37.1's scope is unchanged: different-user and elevated actors stay out of scope. `S_svc` is **trusted infrastructure**, not a new actor class. TPC-2 exists so that "elevated actor" cannot be reached silently from the in-scope same-user actor.

### 1.4 Public documentation relied on (read in this session)

| Source | Content relied on |
|---|---|
| *CreateDirectoryW* (fileapi, ms.date 2018-12-05) | "The **lpSecurityDescriptor** member … specifies a security descriptor for the new directory." So the object is born with that DACL. Without it, ACLs "are inherited from its parent directory" |
| *CreateHardLinkW* (winbase, ms.date 2018-12-05) | "The security descriptor belongs to the file … You cannot give a file different security descriptors on a per-hard-link basis." "Use DeleteFile to delete hard links. You can delete them in any order" |
| *Microsoft Security Servicing Criteria for Windows* | User boundary and session boundary are serviced. UAC is not a security boundary. Administrators are TCB |
| *The Old New Thing*, 2005-08-18 (Microsoft blog, **non-normative**) | `WRITE_OWNER` lets you set the owner only to yourself or to a SID in your token with `SE_GROUP_OWNER`. Only `SeRestorePrivilege` lets you assign another principal as owner. **To be confirmed against normative docs in AMD-PPS review** |
| *FSCTL_SET_REPARSE_POINT* (ntifs; read in FU2) | Not relied on by any PPS proof. P's chain never needs the non-empty precondition (§2.1 F2) |

## 2. Mechanical proof that the first creation is in the authorized namespace

### 2.1 Facts

| # | Fact | Mechanism | Depends on an observation by AIDO? |
|---|---|---|---|
| **F1** | The pipe peer is the PPS | The executor reads the pipe's owner SID from the connected handle (`GetSecurityInfo`, `OWNER_SECURITY_INFORMATION`) and requires it to equal `S_svc`, resolved by `LookupAccountNameW("NT SERVICE\<name>")`. A pipe squatter running as `S_op` cannot make `S_svc` the owner without `SeRestorePrivilege`, which TPC-2 excludes. The executor connects with `SECURITY_SQOS_PRESENT \| SECURITY_IDENTIFICATION`, so the PPS can identify the executor but never impersonate it | An identity fact about a kernel object, stable for its lifetime |
| **F2** | P is actor-immutable | **Forward-only access rule** on P and every PPS-created descendant: `S_op`'s **granted** mask, computed by the OS access check (`AccessCheck` / `AuthzAccessCheck` with `MAXIMUM_ALLOWED` against the operator's real token), intersects `W = {FILE_ADD_FILE, FILE_ADD_SUBDIRECTORY, FILE_WRITE_ATTRIBUTES, FILE_WRITE_EA, FILE_DELETE_CHILD, DELETE, WRITE_DAC, WRITE_OWNER}` in **∅**. The owner is `S_svc`, so there are no implicit owner rights for `S_op`. Not a reparse point (no-follow open). **Chain rule** for each ancestor `A` of P: `S_op` holds no `DELETE`, `WRITE_DAC`, `WRITE_OWNER` or `FILE_WRITE_ATTRIBUTES` on `A`, no `FILE_DELETE_CHILD` on `parent(A)`, is not `A`'s owner, and `A` is not a reparse point. TPC-1 requires the admin to place P so that the chain rule holds **without** relying on any directory being non-empty (for example under `%ProgramFiles%`) | Evaluated by the OS access check against **policy state set by an administrator before AIDO runs**. It never rests on an AIDO-created occupant |
| **F3** | No DACL-bypass capability exists in the actor's token | TPC-2, read from the token | Token facts are fixed for the token's lifetime |
| **F4** | Every PPS object is **born** actor-immutable | Every PPS create (`CreateDirectoryW` / `CreateFileW(CREATE_NEW)`) passes an explicit `SECURITY_ATTRIBUTES`: owner `S_svc`, protected DACL, no write-class ACE for any operator SID. The documented contract applies that descriptor to the new object. So there is **no instant** at which the new object grants `S_op` anything in `W` | Documented creation semantics; no post-create observation |
| **F5** | The PPS chooses every name | The protocol (§4.3) carries **no destination path**. Run ids are minted by the PPS (128-bit random). Leaf names come from a closed enumeration. Runtime-relative names are validated against a closed grammar: relative, no `..`, no `:`, no ADS, no reserved device name, depth, count and length bounds | Code property, reviewable |

### 2.2 Proof (induction over PPS creates)

**Claim.** At the instant of every PPS create, every component of the parse path (P's ancestors, P, and every PPS-created intermediate) is a plain directory that no same-user operation can rename, delete, replace, re-ACL, convert or add an entry to.

- **Base case.** P and its chain satisfy F2 before the first request. This was established by an administrator and is re-checked by the PPS at start and by the executor at admission. Every operation that could rebind or convert a component needs a right in `W` on that component, or `FILE_DELETE_CHILD` on its parent, or a privilege excluded by F3. The OS access check refuses each of them for `S_op`. This holds for directory rename, delete, replace, ACL or owner change, `FSCTL_SET_REPARSE_POINT` (which needs a write-class handle), and hard-link creation into P (which needs `FILE_ADD_FILE` on the target directory).
- **Step.** A PPS-created directory is born under F4 inside a parent satisfying the claim. Because of F5, its name comes from the PPS. So it satisfies the claim from birth. There is no window between creation and protection, because there is no "protect" step: the protection **is** the creation's own security descriptor.

**Consequence.** The disputed behaviour (a create whose parent was converted after AIDO last looked) **cannot arise**, because no parent can be converted by the in-scope actor at any instant. P1 holds **without** OBJ_DONT_REPARSE, without NtCreateFile relative creates, without R-WINDOW, without a pin, and without any statement about what Windows would do if the parent *were* converted. PPS creates may use plain documented Win32 pathname calls: names inside P cannot be rebound.

### 2.3 What P2 now means, and why B1 no longer bites

- **AIDO-authored names.** By F4/F5, every name the PPS authors is inside P. No AIDO component creates protected objects anywhere else (§5.1), so **P2 holds for every AIDO-authored name by construction**.
- **Actor-authored aliases.** After a read grant (§3.3), `S_op` may be able to open a PPS file and hard-link it into an operator-writable directory. **No proof here claims otherwise.** That alias is actor-authored, the class AMEND2 §13 already accepts. By the documented hard-link contract, the alias carries the **same** security descriptor, so it gives `S_op` no write, delete-of-object, ACL or owner right it lacked. Integrity therefore rests on the **object's** DACL, which no name can change, and never on the link set. That is the precise answer to B1: link-set stability is **not needed**.
- **Hygiene, not proof.** Sensitive content is written before the operator read grant is applied. **No claim rests on this ordering.**

### 2.4 What the executor proves independently (no PPS claim trusted)

Before consumption, the executor re-establishes F1–F3 and, for every consumed object and directory, the F2 access rule, owner == `S_svc` and no reparse attribute. It does this through its own no-follow, read-only opens and the OS access check under its **own** token. A PPS bug that produced an object outside P, or an object writable by `S_op`, is therefore **refused at admission**, not trusted.

The one thing the executor cannot observe is a PPS create *elsewhere*. That is excluded by F5 plus the closed protocol (§4.3), and it is the declared TCB content of TPC-1.

## 3. Protected runtime provenance and consumption rules

### 3.1 Staging (supersedes RPR and OSR)

| Step | Rule |
|---|---|
| RT-1 Source | The executor reads the candidate tree (from the ambient install or an operator path) **read-only, no-follow**, as `S_op`. The PPS **never opens a user path** and does not impersonate. So it has no read-amplification (confused-deputy) surface |
| RT-2 Transfer | The executor streams `(validated relative name, bytes)` records over the authenticated pipe, within the construction-scale bounds (68ae5b0: peak 449 ≤ 462 entries) plus byte caps |
| RT-3 Create | The PPS writes them into `P\runs\<id>\runtime\` under F4/F5. It computes no approval: **content authority is not the PPS's** |
| RT-4 Seal | The PPS applies the read/execute grant (§3.3) and reports `SEALED` plus a digest list (advisory only) |
| RT-5 Identity | The executor performs the **complete PI-PC1 walk** of the sealed copy (P2M exact membership, P2X exposure absence) and requires equality with the sealed HPP-1 profile fingerprint. `node.exe` still comes from L1 (`I_n`), unchanged |
| RT-6 Topology | INV-F5A-R1 (T-CANON, T-NM over the whole chain, T-PLAIN, T-BUN, no `PI_PACKAGE_DIR`) is evaluated over `P\runs\<id>\runtime`. FU2's at-instant "ancestor `node_modules` is MISSING" (OSR-7 / T-RT) is **replaced by an access rule**: for each ancestor `A`, either `S_op` lacks `FILE_ADD_SUBDIRECTORY` on `A`, or `A\node_modules` exists as a plain, `S_svc`/admin-owned, F2-immutable directory with no entries. Where the platform default permits operator folder creation (e.g. a volume root), TPC-1 makes the administrator pre-occupy that name |

### 3.2 Why this is stronger than RPR or OSR

The bytes the executor verifies at RT-5 sit in an object that **`S_op` cannot modify afterwards**. So the R-SLIVER / R-ABA substitution class (F5-A §2.5) **no longer applies to runtime payload bytes**. The proof is no longer "at an instant": it holds until PPS teardown. R-ABA for `node.exe` (L1) is **unchanged**.

### 3.3 Consumption rules

- **Grant.** Read and execute only (`FILE_GENERIC_READ \| FILE_GENERIC_EXECUTE`, plus `FILE_LIST_DIRECTORY`/`FILE_TRAVERSE` on directories). The grant goes to the **logon SID of the requesting connection's token** (narrower than `S_op`). It is never applied to anything in `W`.
- **Launch.** The executor launches from `P\runs\<id>\runtime` through the unchanged L14 re-proof (re-run RT-5/RT-6 plus §2.4) and L21A. Records never carry an absolute path, as before.
- **PPS-PO-1, write absence.** A byte-bound static proof (PE-4A class) that the approved profile, under the T-4 environment, creates, writes, renames or deletes **nothing** under the runtime root, `PI_CODING_AGENT_DIR` or the extension directory. This includes caches such as a TS-loader cache. If any such effect exists, the profile is **refused**, never accommodated by a writable grant inside P. This keeps P free of operator-authored entries, so PPS teardown never recurses into an actor-writable subtree.
- **PPS-PO-2.** The model-visible documentation paths now point into P. This needs a PE-4A F-4 re-disposition. D-F5A-9 (U126 read relocation) must be re-examined for this topology.

## 4. L9 / L11 secret-writing and cleanup authority

### 4.1 Writing

| Item | Rule |
|---|---|
| Source of secrets | **Unchanged.** The endpoint comes only from environment variables (L9). The broker `pipe_name`/`capability_id`/`token` are in memory (L11). T-1 byte identity of `settings.json`/`models.json` and the verified-template rendering of `ar2_config.ts` are unchanged |
| Who writes | **The PPS only**, into `P\runs\<id>\pi_agent\{settings.json, models.json}` and `P\runs\<id>\ext\{verified sources…, ar2_config.ts}`. The names come from a closed enumeration |
| Transit | The authenticated pipe only (F1, `PIPE_REJECT_REMOTE_CLIENTS`, `FILE_FLAG_FIRST_PIPE_INSTANCE`, a pipe DACL denying `S_op` `FILE_CREATE_PIPE_INSTANCE`). **No secret byte is sent before F1 passes** |
| PPS handling | No logging, no echo, no persistence outside the named file, no retention by reference after the write. **No claim of memory erasure** (Python cannot make one). The reply carries only status and digests |
| Executor verification | The executor reads each file back through its own read-only no-follow open, compares digests, and re-applies §2.4. The PPS's digest is never authority |
| Integrity after write | `S_op` cannot modify or replace the files (F2). This is an improvement over FU15, where W11 left the files unprotected after L9 |
| Confidentiality | **Unchanged non-claim** (§37.1): Pi must read the files, so `S_op` can read them |
| Removed from AIDO's executor | `create_exclusive_child`, both parentage gates, every handle disposition (`cfg1_pi_config.py:506`, `:616-617`; `cfg1_extension.py:385`), R-WINDOW, and the `<root>/cfg1_pi_config` location. L9-1…L9-4 (FU2 §5.2) **dissolve**, because the code that carried them is no longer on the provisioning path. CFG1-K1 is therefore **off the critical path** |

### 4.2 Cleanup

| Item | Rule |
|---|---|
| Who may delete | **Only the PPS, and only under `P\runs\<id>`.** The executor deletes nothing under P and cannot (F2) |
| Triggers | (a) `TEARDOWN` on the owning connection; (b) loss of that connection (executor death); (c) PPS start, which tears down every ledgered run that has no live connection (orphan recovery) |
| Order | After Pi has exited, under the existing frozen lifecycle ordering. Sensitive files first get an **AMEND2-style object scrub** (truncate through a handle opened by its inside name). Every name is then removed **bottom-up**, by name, inside P |
| Why name removal is sound | Every name in P was authored by the PPS (F2: `S_op` cannot add names). The documented hard-link contract says DeleteFile removes the named link, in any order. So an actor-authored outside alias is never removed or followed; the object survives under that alias, scrubbed. Under F2/PPS-PO-1 there is no actor-writable subtree in P to recurse into, so the A2-3 relative-open question never arises in teardown either |
| Truthful lifecycle | The executor verifies removal itself: after `TEARDOWN`, an open of `P\runs\<id>` must return not-found. In an actor-immutable namespace with never-reused ids, **absence is stable**: only the PPS could recreate it. `endpoint_material_outstanding` / `token_material_outstanding` become `NOT removal_verified_by_executor`, which is conservative and does not rest on PPS reports. A failure is `TEARDOWN_INCOMPLETE` at the PPS, which retains it in its ledger and retries it. Retrying is safe because the namespace cannot be rebound. The executor records `INDETERMINATE_LIFECYCLE` → halt (§18 row 10, unchanged) |
| Quotas | Per operator: at most N concurrent runs, plus byte and entry caps per run. Exceeding a cap refuses. This bounds what a same-user caller can make the PPS store |
| Not covered | The L2 case repository `R` (Pi's writable workspace) stays with L2/L27, unchanged. **L2-Q** (FU2 §11) remains an open inherited observation, outside this decision. No run-wide P1 claim is made |

### 4.3 What an untrusted caller can and cannot obtain

Any `S_op` process can connect, because `S_op` must be allowed to. The closed protocol is `OPEN_RUN`, `PUT_RUNTIME_ENTRY`, `PUT_CONFIG(enum leaf, bytes)`, `PUT_EXTENSION(enum leaf, bytes)`, `SEAL`, `TEARDOWN`. With it a caller obtains at most:

- a run of its own, under PPS-chosen names, holding bytes it chose, readable by its own logon session, and deleted when its connection ends.

It obtains **no** destination path, no write or delete outside its own run, no write or delete of another connection's run, no ACL operation, no read of any path, and no process execution. It **cannot plant a trusted runtime**: identity is the executor's own walk against the sealed profile. It **cannot redirect a genuine run**: the executor consumes only the run bound to its own connection. The PPS executes nothing, so it is not a command executor (CLAUDE.md non-goals preserved).

**Explicit non-claim.** The PPS does not defend the executor process against a same-user debugger or injector. That is outside §37.1's filesystem-tampering actor and is not introduced here. Even with a compromised executor, F2/F4/F5 still hold, because they hold against **every** caller.

## 5. Frozen-contract amendments required

| Id | Frozen surface | Change |
|---|---|---|
| AMD-PPS-0 | FU15 §37.1 | Add the trusted base: an admin-installed PPS under `S_svc`, plus TPC-1/TPC-2 as **refusing preconditions**. Actor set and out-of-scope list unchanged |
| AMD-PPS-1 | F5-A §6.1, §7.1–§7.8.1, §11.1–§11.2, §18 row 22, T-F5A-25, D-F5A-1, D-F5A-10 | RPR (A2-R1) is replaced by PPS staging (§3.1). L3R becomes "request staging + admission". T-RT is replaced by the RT-6 access rule. The construction ledger and native relative creates are retired. `live_references_released` is re-scoped to admission handles. Row 22 and T-F5A-25 hold by F4/F5. R-SLIVER/R-ABA are narrowed for runtime payload bytes (§3.2) |
| AMD-PPS-2 | PE-1 §11.1 P1/P2; `pi_identity._PI_PACKAGE_PARTS` (`pi_identity.py:161`) | The package root comes from the PPS run binding (supersedes FU2's AMD-OSR-4) |
| AMD-PPS-3 | FU15 §37.2 (relocation rejection), §37.3.1–§37.3.7, §37.3.2a/b | The config location moves to `P\runs\<id>\pi_agent`. §37.2's rejection premise ("equally reachable by a same-user process") is false for P and is reversed. Steps 2–11, R-WINDOW and D-A are retired. Fact 7 is replaced by F2/F4. Precise-child authority (§37.3.2a) becomes PPS-held. Namespace teardown for this resource becomes PPS teardown |
| AMD-PPS-4 | L11 frozen E-sequence (R6 / FU1 AM-10) | The same, for `P\runs\<id>\ext` |
| AMD-PPS-5 | AMEND2 §9/§10 (RETAIN, SCRUB-C/R, RELEASE-R, bool formulas) | The scrub moves to the PPS teardown. The `*_material_outstanding` formulas are redefined as `NOT removal_verified_by_executor` |
| AMD-PPS-6 | L12 (`PI_CODING_AGENT_DIR` target), L24, L27 scope | L12 points into P. L24 becomes PPS `TEARDOWN` plus executor absence verification. L27 is scoped to `R` only |
| AMD-PPS-7 | PE-4A F-4; D-F5A-9 | PPS-PO-2 re-disposition |
| Withdrawn | FU2 AMD-OSR-1..5, AMD-K-1..3, DEC-FC, LG, K2–K8 | Superseded. No residual is proposed for external object creation; the design creates none |

New authority also requires an explicit CLAUDE.md-level authorization for a **separately installed Windows service**. That is a new capability class, and this record does not grant it.

## 6. Smallest implementable phase and its hard acceptance bar

**Prerequisite (external):** the reviewer adopts AMD-PPS-0…7 in principle. Platform availability of TPC-1/TPC-2 is **not** needed for this first phase.

### PPS-1: executor-side protection admission verifier (offline, read-only)

This is the non-trusting half of the boundary, and it is needed whoever implements the service. It creates, deletes and re-ACLs nothing, launches nothing, and is **not wired** into live paths.

| Component | Content |
|---|---|
| Pure decision core | Input: typed facts (token facts; per-object `{owner SID, granted mask for the operator token, reparse attr/tag, kind}`; per-ancestor facts; pipe owner SID; expected `S_svc`). Output: `ADMITTED` or one closed refusal code. No I/O |
| Read-only adapters | `GetTokenInformation`; `GetSecurityInfo` on no-follow read-only handles; `AccessCheck` with `MAXIMUM_ALLOWED` against a duplicated identification token of the executor's own process; `LookupAccountNameW`; `GetFileInformationByHandleEx` (attribute/tag). All of these are documented Win32 |

**Hard acceptance bar (all required):**

1. **The pure core refuses** each of the following (synthetic facts):
   - owner == operator;
   - any bit of `W` granted on any object or on P;
   - each chain-rule violation;
   - any reparse attribute or tag;
   - each TPC-2 group, privilege or elevation condition;
   - pipe owner ≠ `S_svc`;
   - an unresolvable `S_svc`;
   - a missing logon SID;
   - every malformed or partial fact set (all-or-nothing, as in §37.4.1).

   It admits exactly one well-formed fully compliant fact set. The tests enumerate every refusal code.
2. **The adapter on synthetic `tmp_path` objects returns `REFUSED`** (owner == operator), and on the test runner's token reports TPC-2 facts **without refusing to run the test**. This proves that **no same-user helper or test fixture can ever be admitted**. The verifier itself becomes a structural barrier against the rejected "helper under the same identity".
3. No call in PPS-1 creates, writes, renames, deletes, sets security on, or converts any object. A static sweep test asserts the absence of the corresponding Win32 names in the module.
4. Both live barriers are unchanged (`run_executor.py:2153`, `:1970`) and asserted by an existing test. The full offline suite stays green with the standard deselections.
5. No real Pi, Node, model, credential, service, junction, conversion or hard link. Synthetic `tmp_path` only.

### Later phases, in order (each separately authorized)

1. **PPS-2: service core, offline.** Closed protocol, ledger, F4 creates, seal, scrub/teardown, orphan recovery, quotas. Exercised in-process on `tmp_path` in tests, where **PPS-1 must refuse every result**. That is the evidence that the boundary is never claimed without the platform.
2. **PPS-3: service host and installer package**, run by an **administrator**, never by AIDO. Read-only deployment admission evidence on a TPC-1/TPC-2 machine.
3. **PPS-4: executor integration, offline.** L3R → PPS staging, L9/L11 → PPS writes, L24 → teardown request. Barriers unchanged.
4. **PPS-5: adversarial qualification** on the provisioned machine, under explicit authorization.
5. A fresh live authorization, which must also state the L9/L11 condition (FU2 §5.1).

## 7. Existing offline AIDO work that can be reused

| Work | Reuse |
|---|---|
| Sealed HPP-1 policy loader, PI-PC1 walk, P2M/P2X, `pi_identity` binding | RT-5 identity over the staged copy (unchanged) |
| `pi_runtime_provision.py` admission, exact-set membership and verify-before-persist logic | Executor-side post-seal verification. Its **native relative create path is superseded**, not reused |
| `run_executor` L3R step, `provision_runtime` port, L14 re-proof, L27-entry release, derived `live_references_released`, v3 vocabulary | Port shape kept; a PPS-backed implementation replaces the A2 one in PPS-4. Both barriers stay as they are |
| `win_config_authority` no-follow opens, reparse attribute/tag checks, handle-based enumeration | PPS-1 adapters (read-only parts only) |
| `config_issuance` rendering (T-1), `cfg1_extension` verified-template rendering | Unchanged: they produce the bytes sent to the PPS |
| AMEND2 scrub semantics and `*_material_outstanding` vocabulary | Moved to PPS teardown and redefined (AMD-PPS-5) |
| AR2 `winpipe` (`FILE_FLAG_FIRST_PIPE_INSTANCE`, `PIPE_REJECT_REMOTE_CLIENTS`, `SECURITY_ATTRIBUTES` builder) and AR2D-FU1 broker lifecycle states and deadlines | PPS pipe server and lifecycle model. The DACL changes from current-user to `S_svc` + operator logon SID. **F1 owner verification is new** |
| Construction-scale evidence (peak 449 ≤ 462) | RT-2 entry bound |
| Synthetic `tmp_path` test harness patterns | PPS-1/PPS-2 tests |
| **Not reused** | NtCreateFile relative creates, R-WINDOW machinery, FU2 LG/K-sequence (never implemented), OSR in-place consumption, CFG1-K1 (off the critical path) |

## 8. Adversarial review

| Challenge | Answer |
|---|---|
| Is this just "trust the operator" again? | No. The operator supplies nothing the proofs rest on. The **administrator** supplies TPC-1/TPC-2, which is declared TCB, and the executor re-checks every observable part of it (§2.4) |
| Does F2 secretly rely on the non-empty precondition (B2)? | No. The chain rule is stated without it, and TPC-1 requires P to be placed where it holds. No AIDO-created object is ever the initial condition |
| Does anything rely on link enumeration (B1)? | No. Integrity rests on the object DACL, which the documented contract makes identical across all links |
| Can a same-user squatter impersonate the PPS? | Not past F1: making `S_svc` the pipe owner needs `SeRestorePrivilege`, which TPC-2 excludes. No secret is sent before F1 |
| Can a same-user caller misuse the PPS? | Only inside its own run, with PPS-chosen names, under quotas (§4.3) |
| Is a new residual introduced for external object creation? | No. The PPS creates nothing outside P, and the executor creates no protected object at all |
| What if the platform cannot provide TPC-1/TPC-2? | Definitive HOLD, with the missing capability named in §1.3. No fallback to a same-user helper is permitted |
| Did this record execute anything or edit a frozen text? | No. Reads only; this file is the only change |
