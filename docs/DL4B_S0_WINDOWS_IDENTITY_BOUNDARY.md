# DL-4B S0 — Windows Identity Boundary

**Status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**

| | |
|---|---|
| Baseline | `main` at `67b60da6b095c745233597abbb2580a2f8299af0` (DL-4B AMEND1 design accepted for offline implementation) |
| FU1 | On `a3183924c06e670c88ec9bb72044008bb953a892`: closes the three identity-boundary bypasses confirmed by independent review (F1 ancestor take-over, F2 foreign non-interactive window station, F3 reparse entries on `PATH`) and two found in the FU1 self-review — see §6 B-13 to B-15 and §11 |
| Contract | `docs/DL4B_REAL_INTEGRATION_BOUNDARY_DESIGN.md` — FD-13, FD-14, FD-16 (§5.8), slice S0 (§11) |
| Kind | Offline implementation. No integration session, model, verifier, writer, reviewer, Git operation, subprocess, network request, account, ACL, scheduled task or system-directory change |
| Not authorized | Live Alpha, E-12 rehearsal, any other DL-4B slice |

S0 builds the **proof** the design requires before an integration session may
hold authoritative state: that the execution identity X cannot write, delete,
replace, re-permission or take ownership of anything on the authority
identity A's plane, cannot open A's process, thread or token, and does not
control A's code, import paths or executable search paths. The boundary itself
is Windows access control between three accounts; S0 does not create it and
cannot repair it. It reads what the OS reports and refuses unless every fact
proves the boundary.

---

## 1. Modules

All new, in a new package `ai_dev_orchestrator/integration/` (the A-side
package the design names in §10.1). `control_plane/` is untouched and does not
import it; no CLI command reaches it.

| Module | Role |
|---|---|
| `security_descriptor.py` | Pure. Parses and builds self-relative security descriptors, ACLs, ACEs and SIDs; the **upper-bound** rights evaluator; NTFS inheritance simulation; the transform that lets AuthZ compute the same bound |
| `boundary_facts.py` | The immutable fact records the proof consumes, and the `SecurityFacts` protocol |
| `windows_security.py` | `WindowsSecurityFacts`: the production, read-only Win32 fact source, and AuthZ as an independent evaluator |
| `identity_boundary.py` | `identity-boundary.v1` model and strict parser, the FD-14 object policies, the FD-16 composition, refusal categories, `IdentityBoundaryProof`, and the two entry points |

## 2. Public contract

```python
prove_identity_boundary(*, expected_boundary_sha256: str | None = None) -> IdentityBoundaryProof
prove_identity_boundary_from_facts(facts: SecurityFacts, *, expected_boundary_sha256=None, clock=None)
```

- **Production** `prove_identity_boundary` takes no facts source, no path and
  no boundary. Facts come from `WindowsSecurityFacts()`; the boundary from the
  code constant `%ProgramData%\AIDO\identity-boundary.v1.json`, with
  `%ProgramData%` resolved through `SHGetKnownFolderPath`, not the environment.
  `expected_boundary_sha256` can only narrow (FD-16 step 1: once a plan
  activation binds a digest, a different boundary refuses). Off Windows it
  refuses `platform_unsupported` before loading any Win32 code.
- **Library** `prove_identity_boundary_from_facts` runs the identical proof
  over any `SecurityFacts`. Its proof is **always** `facts_origin="injected"`
  and `is_production is False`, whatever the source is or claims to be. Only
  the production entry point can mint `facts_origin="windows"` (pinned by a
  static test), and it additionally **requires** the AuthZ evaluator on every
  rights result (`independent_evaluation=True`).
- **`IdentityBoundaryProof`** is a record of one successful run: minted only by
  the prover (private token), immutable, not subclassable, not copyable or
  picklable. It carries the parsed boundary, its SHA-256, the origin, whether
  every rights result was confirmed independently, the time and the number of
  objects examined. **It is not a capability.** Nothing is cached between
  runs; every call re-reads every fact, including the boundary file. The
  consumption boundary (S2's `open_integration_session`, every dispatch, claim
  read and proof) must call the prover again, never accept a proof object.
- Every refusal is `IdentityBoundaryError` with `.category` and a message
  starting `isolation_unproven:<category>:`. Messages name roles, SIDs, right
  names and paths relative to a declared root; never file or boundary contents.

## 3. Pre-implementation adversarial analysis

Questions asked of every object: can X reach or replace it through a parent
directory, a group ACE, an owner privilege, an alternate path, an inherited
permission or a supported caller?

| Mechanism | What it lets X do | How S0 answers it |
|---|---|---|
| **Ownership** | The owner is implicitly granted `READ_CONTROL \| WRITE_DAC` before any ACE is read; deny ACEs do not remove it | Evaluated. Authority objects must be owned by A (or by SYSTEM/Administrators/TrustedInstaller for anchors and code). X-owned objects (clone root, `.git`) must carry an effective `OWNER RIGHTS` ACE, which replaces the implicit grant |
| **OWNER RIGHTS (`S-1-3-4`)** | Present and effective → replaces implicit owner rights, allow and deny | Evaluated in ACE order; inherit-only copies do not count. Clone root and `.git` must have one that is also inherited by new files and directories |
| **DELETE vs DELETE_CHILD** | An object can be deleted or renamed with `DELETE` on it **or** `FILE_DELETE_CHILD` on its parent, whatever the child's DACL says (an explicit deny included); renaming then lets X recreate the name if it can add to the parent | Every component from the volume root to every declared object is checked for both routes, for X and O (and for A on anchors and install roots). A protected child DACL alone is never accepted |
| **Ancestor take-over** (FU1) | `WRITE_DAC` on any ancestor lets X grant itself `DELETE` or `FILE_DELETE_CHILD` there; `WRITE_OWNER` lets it take ownership, and an owner holds `WRITE_DAC` implicitly | Every ancestor, the volume root included, must grant X and O neither right, and must not be owned by a SID they may hold unless an **effective** `OWNER RIGHTS` ACE removes the implicit grant (the X-owned clone root above `.git` is that case). The object itself is limited by its own FD-14 row |
| **DACL inheritance** | Inherit-only ACEs are invisible on the directory itself but decide what every future child grants | Each authority and code directory's inheritance is simulated for a new file and a new directory (NTFS rules, `CREATOR OWNER` substitution, fallback to the creator's default DACL) |
| **Group membership** | Any ACE naming a group X is in | X's and O's groups are computed by the OS (AuthZ, `AUTHZ_COMPUTE_PRIVILEGES`), not enumerated by convention |
| **Logon-dependent SIDs** | `INTERACTIVE`, `NETWORK`, `BATCH`, `SERVICE`, `LOCAL`, logon session SIDs… are added by *how* a token logged on; AuthZ omits them; X can obtain more than one kind (e.g. a network token over loopback) | Added as **possibly held**. Allow ACEs match possible SIDs; deny ACEs match only SIDs **certainly** held. Every logon SID may match except A's own current one |
| **Privileges** | Backup, restore, take-ownership, debug, impersonate, load-driver, manage-volume… bypass or subvert the DACL | A's token, and X's and O's OS-computed privileges, must be within a five-privilege standard-user allowlist (disabled ones count: a process can enable them). Administrative groups refused, including a deny-only `Administrators` in A's (UAC-filtered) token and a high-integrity AuthZ context |
| **Reparse points, aliases** | Junctions, symlinks, mount points, short names, case and Unicode spellings redirect a path; Windows follows intermediate junctions even with `FILE_FLAG_OPEN_REPARSE_POINT` | Each component opened without following and refused if a reparse point; declared and code paths must equal the OS-reported final path. A reparse entry directly in a `PATH` or working directory is refused (FU1): a protected link says nothing about the image or DLL loaded through it |
| **Process / thread / token** | `OpenProcess`, `CreateRemoteThread`, `WriteProcessMemory`, handle duplication, token duplication | X and O must be granted **nothing** on A's process, current thread and primary token, nor through the token's default DACL (which every later thread and object A creates receives) |
| **Sessions** | A shared desktop allows input injection, hooks and window messages across accounts | A must be on its own interactive window station and desktop (both reporting its logon SID) or, for a Task Scheduler S4U launch, on the non-interactive station Windows creates for **A's own logon session**. In both cases X and O must neither own nor be granted anything on the station or the desktop (FU1) |
| **Code loading** | A writable import directory, `.pth` file, module, DLL search directory or working directory runs X's code as A; `PYTHONPATH` and the user site are read at interpreter start, **before** any proof can run | All import locations inside declared, admin-owned install roots, walked in full; the interpreter must be isolated (`-I`); `PATH` directories, their files and the working directory checked; DLLs for S0 itself loaded from System32 only |
| **Supported caller** | A caller builds facts, a proof, or skips the prover | Injected facts can never produce a production proof; the proof cannot be constructed, mutated, subclassed or copied; facts are type-checked and copied at consumption; nothing is cached |

## 4. What is proven, in order

1. **Platform.** `is_windows()` must be exactly `True`.
2. **Environment** (FD-16 step 6). No name `AIDO_LITELLM_*`, `AIDO_VLLM_*`,
   `GITHUB_TOKEN`, `PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`,
   `PYTHONUSERBASE`, `PYTHONBREAKPOINT`, `PYTHONPLATLIBDIR`,
   `PYTHONEXECUTABLE`, `PYTHONINSPECT` (case-insensitive), read from both
   `os.environ` and the process environment block. Names only, never values.
3. **Token** (step 2). Not elevated, elevation type *default* (a full or
   filtered UAC token is an administrator), integrity ≤ medium, privileges ⊆
   the standard-user allowlist, no administrative group in any attribute,
   exactly one logon SID, a parseable default DACL.
4. **Anchor** (step 1, FD-2 (a)–(e)). The boundary file is read from one handle
   that denies write sharing; not a reparse point; one hard link; at its exact
   final path; owned by SYSTEM, Administrators or TrustedInstaller; its
   directory admin-owned with a protected DACL. Strict parse: UTF-8, no BOM,
   no duplicate keys, no non-standard constants, no unknown fields.
5. **Identities** (step 2). Three distinct ordinary user SIDs (RID ≥ 1000; A
   and X local accounts of this computer in one domain; O may also be an
   Entra ID account), each resolving to the declared `DOMAIN\name` and
   `SidTypeUser`; the process user is A; no account in an administrative
   group or holding a non-standard privilege; A shares no non-baseline group
   with X or O. Then the anchor's rights: A, X and O at most read on the file
   and directory, on new files created there, and none can remove, rename,
   re-permission or take over it or any ancestor.
6. **Session** (step 3), per the declared launch mechanism:
   - `interactive_session`: the visible `WinSta0`, station and desktop both
     reporting A's current logon SID;
   - `task_scheduler_s4u`: a non-interactive station other than `WinSta0`;
     its reported SID, if any, is A's logon SID; its name is exactly
     `Service-0x<high>-<low>$` for A's own logon session LUID (read from the
     token's `TOKEN_STATISTICS.AuthenticationId`, compared folding ASCII only),
     so a SID-less station that is SYSTEM's (`…-3e7$`), another service's or
     another session's is refused; the desktop's SID, if any, is A's;
   - in both cases the station's and the desktop's owners are not SIDs X or O
     may hold, and their DACLs grant X and O nothing.
7. **Process** (step 4).
8. **FD-14 objects** (step 5), each also non-replaceable through every
   ancestor for X and O (no `DELETE` on any component, no `FILE_DELETE_CHILD`
   on any parent, and no `WRITE_DAC`, `WRITE_OWNER` or implicit owner
   `WRITE_DAC` on any ancestor from the volume root down):

| Object | Owner | Protected | X may hold | O may hold | Also |
|---|---|---|---|---|---|
| state root | A | yes | nothing | nothing | walked: every descendant owned by A, one hard link, same limits; new children inherit nothing for X/O |
| `published/` | A | yes | nothing | read | walked, same |
| `inbox/` | A | yes | nothing | read + add file | files only; each owned by A or O, one link, nothing for X; new O files grant X nothing |
| exchange root | A | yes | read | read | new children grant X/O at most read (per-ticket directories are S3's) |
| clone root's parent | — | — | read | — | (design: "traverse only") |
| clone root | **X** | yes | read, add file/subdirectory, write EA/attributes — **never** `DELETE`, `FILE_DELETE_CHILD`, `WRITE_DAC`, `WRITE_OWNER` | read | effective + inheritable `OWNER RIGHTS`; new working-tree children never grant X `WRITE_DAC`/`WRITE_OWNER` |
| clone `.git` | **X** | yes | read | read | must be a directory (a gitfile is refused); effective + inheritable `OWNER RIGHTS`; walked: every descendant owned by X, read-only to X and O |
| each install root | SYSTEM / Administrators / TrustedInstaller | — | read | read | **A also read only**; walked in full: no reparse point anywhere, every descendant admin-owned and read-only to A, X and O; new children likewise |

9. **Code-load locations** (step 5). The interpreter is isolated (`-I`, or
   `-E -s -P`). Every executable, prefix, `sys.path` entry and the AIDO package
   directory lies, by the OS-reported final path, inside a declared install
   root (a missing entry such as `python3XX.zip` is safe only there, where
   nobody can create it). Each `PATH` directory: X and O at most read, owner
   not held by X/O, new files grant them at most read, every file directly in
   it likewise, no entry directly in it (file or directory) a reparse point,
   not replaceable; a missing `PATH` entry must not be creatable by X or O,
   which also means its nearest existing ancestor grants them neither add
   rights nor `WRITE_DAC`/`WRITE_OWNER`. The working directory is checked the
   same way. A's profile,
   `TEMP`, `TMP`, roaming and local app data: X and O nothing, owner not held
   by them, new children grant nothing, not replaceable.

Rights are always an **upper bound** over every token the account could hold,
computed twice in production — by the pure evaluator and by
`AuthzAccessCheck(MAXIMUM_ALLOWED)` over an in-memory descriptor — and the
union is used. The pure evaluator maps `GENERIC_*` bits (AuthZ does not);
the transform maps them before AuthZ sees the descriptor.

## 5. Refusal categories

`platform_unsupported`, `security_fact_unavailable`, `environment_unsafe`,
`token_identity_mismatch`, `token_elevated`, `token_privileged`,
`boundary_unreadable`, `boundary_malformed`, `boundary_unprotected`,
`boundary_digest_mismatch`, `identity_invalid`, `account_privileged`,
`principal_unverifiable`, `session_foreign`, `process_access`,
`object_missing`, `object_kind`, `object_not_canonical`, `object_reparse`,
`object_linked`, `object_owner`, `object_unprotected`, `owner_rights_missing`,
`descriptor_unsupported`, `object_rights`, `object_replaceable`,
`object_inheritance`, `code_path_untrusted`, `examination_limit`.

Any exception from a facts source, any fact of the wrong exact type, any
malformed descriptor (no owner, NULL or absent DACL, an object, callback,
conditional, label or attribute ACE, an unknown flag, a bad length, offset or
SID) refuses. There is no same-account mode, flag, configuration key or
environment variable that skips any step.

## 6. Discovered bypasses and their regressions

| Id | Found | Bypass | Regression |
|---|---|---|---|
| B-1 | analysis | `FILE_DELETE_CHILD` on the clone root lets X rename the read-only `.git` away and create its own; parent `DELETE_CHILD` overrides an explicit deny on the child | `test_b1_*` |
| B-2 | analysis | A user-created directory under `C:\` inherits "Authenticated Users: Modify" (DELETE), and `C:\` lets them add subdirectories: X renames the ancestor and recreates it | `test_b2_*` |
| B-3 | analysis | Inherit-only ACEs on a code directory make every new file X-writable while the directory looks clean | `test_b3_*` |
| B-4 | analysis | A missing `PATH` or `sys.path` entry under an X-addable ancestor can be created by X | `test_b4_*` |
| B-5 | analysis | Owner-implicit `WRITE_DAC` on X-owned `.git` objects without `OWNER RIGHTS` | `test_b5_*` |
| B-6 | analysis | A deny ACE for a logon-dependent SID (`INTERACTIVE`) does not bind X's network or batch tokens | `test_b6_*`, evaluator tests |
| B-7 | analysis | An allow ACE to an unknown logon SID may be one of X's sessions | `test_b7_*` |
| B-8 | analysis | AuthZ's computed groups omit logon-type SIDs | `test_b8_*` |
| B-9 | **second review** | Windows follows a junction in an **intermediate** component even when the last is opened without following; a code path through a junction into an install root looked clean while depending on a junction outside every root | `test_b9_*` (synthetic, and the real-API behaviour on a `tmp_path` junction). Verified to fail with the check disabled |
| B-10 | **second review** | Full Unicode lowering equates names NTFS keeps apart (Kelvin sign vs `k`); per-directory case-sensitive folders make `INSTALL` ≠ `install`. Identity now folds ASCII only, overlap detection uses `casefold` (broader), install-root containment compares OS-reported spellings exactly | `test_b10_*` |
| B-11 | second review | Python reads `PYTHONPATH`, the user site and the script directory at start-up, before any proof; an environment check after the fact is too late | `test_the_interpreter_must_be_isolated` |
| B-12 | second review | A directory entry ending in a dot or space, or named like a device, is opened as a different object by Win32 path parsing | `test_an_entry_win32_cannot_address_exactly_refuses` |
| B-13 | **FU1 review (F1)** | `WRITE_DAC` or `WRITE_OWNER` on an ancestor (or ownership of it without an effective `OWNER RIGHTS` ACE) lets X grant itself `DELETE`/`FILE_DELETE_CHILD` and rename a protected descendant away; only `DELETE` and `DELETE_CHILD` were checked. Minimum case: X holds `WRITE_DAC` on `C:\AIDO`, no delete right, state root protected | `test_b13_*`: the minimum case; `WRITE_OWNER`, O, group and logon-type SIDs, X/O ownership; every protected path (state, published, inbox, exchange, clone, install, anchor incl. the volume root, `PATH`, profile incl. an intermediate ancestor) moved under an ancestor of its own; the `OWNER RIGHTS` boundary; the leaf rights of 17 protected objects; the randomized search re-checks every ancestor of accepted worlds |
| B-13a | **FU1 self-review** | The nearest existing ancestor of a missing `PATH` entry was checked only for add rights; `WRITE_DAC`/`WRITE_OWNER` on it grants them | `test_b13_a_missing_search_path_refuses_a_takeover_of_its_nearest_ancestor` |
| B-14 | **FU1 review (F2)** | In the S4U branch, a non-interactive station merely had to not be `WinSta0`; its SID was never consumed, so A placed on X's station (with an absent or A-looking desktop SID) passed | `test_b14_a_foreign_non_interactive_window_station_refuses` (X logon SID, X user SID, SYSTEM; desktop SID absent or A's), `test_b14_a_sid_less_station_not_named_*` (SYSTEM's, LocalService's, another session's, padded, prefixed, long-s and other look-alike names), genuine S4U accepted, malformed LUID |
| B-14a | **FU1 self-review** | The name binding alone would accept a SID-less station that someone else created under the name Windows gives A's; and nothing checked who could open the station or desktop in either mechanism | `test_b14_x_or_o_able_to_use_the_station_or_desktop_refuses` (squatted, group, foreign-logon and O-owned stations; hook-capable, Everyone and INTERACTIVE-owned desktops; both mechanisms) |
| B-15 | **FU1 review (F3)** | A reparse file directly in a protected `PATH` directory was checked by its own descriptor only, while the DLL or executable loaded through it is its target (X-writable in the regression); directory entries were not examined at all | `test_b15_*` (`.dll`, `.exe` and directory links to an X-writable target; a Windows app execution alias; a reparse point reported by either the listing or the handle) |
| B-15a | **FU1 self-review, on this host** | Not a bypass but a correction that would have broken every real proof: 13 subdirectories of the real `System32` (`config` among them), 9 of `Windows` and 1 of `Wbem` deny a standard user even `READ_CONTROL`. Subdirectories of a `PATH` directory are therefore classified from the listing (`DirectoryEntry.is_reparse_point`, from the find data, no open) and never opened | `test_b15_subdirectories_of_a_search_directory_are_classified_without_being_opened`, `test_real_facts_describe_a_junction_without_following_it` |
| — | analysis | NULL/absent DACL grants everyone everything; conditional/object ACEs are evaluated against claims S0 cannot see; generic bits unmapped by AuthZ; short names; user-planted `ProgramData\AIDO`; `WRITE_ATTRIBUTES` turning an empty directory into a junction; `os.environ` vs the real environment block; `ctypes` DLL search | parser tests, `test_a_short_name_alias_*`, `test_a_user_planted_boundary_*`, `test_write_attributes_*`, static tests |

## 7. Tests

`tests/test_dl4b_s0_identity_boundary.py`, 425 cases (303 before FU1):

- descriptor, ACL and SID parsing, malformed and unsupported forms;
- evaluator semantics (owner rights, `OWNER RIGHTS`, order, inherit-only,
  generic mapping, allow/deny asymmetry, logon SIDs, creator and AppContainer
  SIDs) and inheritance;
- **differential** checks against real Windows AuthZ: 400 seeded random
  descriptors, plus owner cases, all equal; the full proof with AuthZ as the
  independent evaluator;
- the boundary document (30+ malformed forms);
- a correctly provisioned synthetic world (realistic `C:\`, `ProgramData`,
  System32, profile and install descriptors) that proves, and one test per
  refusal path in every category;
- the bypass regressions of §6;
- a **randomized counterexample search**: 400 seeded worlds with 1–3 random
  ACE, owner, protection or link mutations, each refused cleanly or, if
  accepted, re-checked object by object against the FD-14 limits;
- facts-source misbehaviour (exceptions, wrong types, subclasses, malformed
  listings, lying principals) and caller bypass attempts (constructing,
  mutating, subclassing, copying a proof; injected facts claiming Windows);
- the production entry point (no injection parameter; refuses off Windows;
  on this host refuses at the environment step **before touching the file
  system**) and the real read-only fact reader on `tmp_path`, this process's
  token, process, session and AuthZ group computation;
- static boundaries: no subprocess, socket, HTTP, model, Git, harness,
  `control_plane` or CLI import; no file-writing, ACL-setting, token-adjusting,
  process-creating or process-enumerating Win32 call; DLLs from System32 only;
  only the production entry point mints a Windows-origin proof; no CLI
  command or control-plane module reaches S0.

No test creates or modifies an account, ACL, task or system directory; the
only file-system objects created are files, directories and junctions under
`tmp_path`. AuthZ evaluates in-memory descriptors.

## 8. Implementation choices the reviewer should confirm

These are within §10.1's latitude but constrain later slices or provisioning:

1. **Isolated interpreter.** A must run Python with `-I` (or `-E -s -P`). S7's
   launch and the AUTH-PILOT task action must say so.
2. **Privileges and groups are OS-computed, and unverifiable means refused.**
   FD-16 step 2 allowed "the remainder attested in AUTH-PILOT". S0 instead
   asks AuthZ (`AUTHZ_COMPUTE_PRIVILEGES`) for X's and O's groups and
   privileges and refuses if it cannot (`principal_unverifiable`), as the S0
   prompt requires. On this development host AuthZ computed both for a domain
   account; whether it does for the real accounts is an E-12 question.
3. **Anchors and install roots must be owned by SYSTEM, Administrators or
   TrustedInstaller**, not by an individual administrator's SID. Provisioning
   must set the owner explicitly if the host's "default owner for objects
   created by administrators" policy is "object creator".
4. **A user-created top-level directory cannot host the authority plane**
   (B-2). Every declared path must sit under an administrator-created,
   protected ancestor chain (e.g. `C:\AIDO`).
5. **The clone root's "modify" for X excludes `FILE_DELETE_CHILD`** (B-1). This
   is Windows' own "Modify" (it never includes `DELETE_CHILD`); provisioning
   must not use "Full control".
6. **`.git` descendants must stay owned by X** (Git's ownership check, C-10);
   an administrator applying the `.git` ACL must not replace owners.
7. **O's limits are enforced as in the FD-14 table**, not only X's: O-side
   compromise (D-16) must not reach A either.
8. **The exchange root is checked, not walked.** Per-ticket handoff and outbox
   directories are S3's.

FU1 adds these provisioning prerequisites:

9. **No ancestor of any declared, code, `PATH` or profile location** may grant
   X or O `WRITE_DAC` or `WRITE_OWNER`, or be owned by them (or by a group
   they belong to) without an effective `OWNER RIGHTS` ACE. Stock Windows
   ACLs on `C:\`, `C:\ProgramData`, `C:\Users` and `C:\Windows` satisfy this.
10. **A's `PATH` must hold no directory with a reparse entry directly in it.**
    In particular `%LOCALAPPDATA%\Microsoft\WindowsApps` (app execution
    aliases are reparse points) must be removed from the dedicated authority
    account's user `PATH`. S0 refuses rather than following a link to prove
    its target.
11. **An S4U launch must run on the station Windows creates for A's own logon
    session**, not on a shared or system station (no task configuration that
    places A's process on another desktop).

No frozen contract prevented a correct implementation; nothing frozen was
changed, in S0 or in FU1.

## 9. Platform limitations and residuals

- **Non-Windows** is never isolated (`platform_unsupported`), and the
  production prover imports no Win32 code there.
- **A proof is a moment.** It shows that, when it ran, no right X or O holds
  could change what it examined; only A, an administrator or SYSTEM could
  invalidate it afterwards. Consumers re-prove; S0 cannot make them.
- **In-process code** reaching private attributes (the proof token, module
  constants) is out of scope, as in DL-4A §2.
- **Not examined by S0:** A's Task Scheduler task definition and its
  security (who may modify the task's action) — Task Scheduler COM, not a file;
  A's registry hive (`HKCU\Environment`) and the system environment key — the
  next proof's environment, `PATH`, profile checks and `-I` cover their
  effects, but not their DACLs; the object-manager namespace of A's session;
  A's profile subtree below the checked directories (e.g. the Startup folder);
  subdirectories of `PATH` directories (never searched); the SACL and integrity
  labels (they can only remove access). E-12 must attack these.
- **Hard links inside install roots and `.git`** are not refused (local clones
  and some installers create them); content is protected by the file's own
  descriptor, which is checked. Authority-plane files must have one link.
- **AuthZ availability.** Production requires AuthZ for every rights result
  and for X's and O's groups and privileges. A host where a standard user
  cannot compute them refuses (§8 item 2).
- **Cost.** Every proof walks every install root, the state root,
  `published/`, `inbox/` and `.git` in full, bounded at 400,000 objects
  (`examination_limit`). Its duration on a real install is an E-12 measurement.
- **Upper bounds can over-refuse.** An ACE naming `PRINCIPAL SELF`, a
  logon-dependent SID or an unknown logon SID counts as X's. That is the
  intended direction.
- **Reparse files on `PATH` are refused, never proven** (FU1). A host whose
  `System32` holds WOF-compressed (CompactOS) or deduplicated files, which
  are reparse points, therefore refuses. This development host's `System32`,
  `Windows`, `Wbem` and `WindowsPowerShell\v1.0` hold none; its
  `WindowsApps` holds 38 app execution aliases.
- **The S4U station rule rests on Windows' naming of service window stations**
  after the logon session LUID, and on `GetSecurityInfo` being able to read
  the station and desktop descriptors from A's own handles. Neither was
  observed for an S4U process here: a different name, or an unreadable
  descriptor, refuses (fail closed). This host's interactive `WinSta0` and
  `Default` are Administrators-owned and grant a non-administrator X nothing.

## 10. What E-12 must still establish (live, separately authorized)

S0 proves the boundary from facts; only the live rehearsal shows that the OS
enforces it against a hostile X. In addition to §5.8.10 of the design, E-12
must confirm:

1. On the provisioned host with real A, X and O accounts, the production
   `prove_identity_boundary()` **passes** (the S0 suite proves only that it
   refuses on this development host), and how long it takes.
2. AuthZ computes the real accounts' groups and privileges as a standard user,
   and the S4U or interactive launch yields a token with exactly the
   standard-user privileges and the expected window station.
3. After the hostile program and its detached descendant have run every
   attack, the proof still passes **and** every store row, blob, published
   byte and the `.git` control digest are unchanged.
4. The residuals in §9 (task definition, registry, object namespace, profile
   subtree) are attacked and fail.
5. The frozen harnesses accept the detached HEAD and the read-only `.git` that
   S0 requires (design §5.8.8).
6. (FU1) An S4U-launched A process reports the station
   `Service-0x<high>-<low>$` for its own logon LUID, with readable station and
   desktop descriptors that grant X and O nothing. A hostile X cannot create a
   station under A's predicted name, cannot open A's station or desktop, and
   cannot obtain `WRITE_DAC` or ownership of any ancestor on the provisioned
   host.
7. (FU1) The provisioned `System32` and every other `PATH` directory of A
   hold no reparse entry, and `WindowsApps` is off A's `PATH`.
8. (FU1) The documented behaviours §11 relies on hold against X: a non-empty
   directory cannot become a reparse point, and changing per-directory case
   sensitivity needs `FILE_DELETE_CHILD`.

## 11. FU1 — adversarial analysis of the corrections

| Route considered | Outcome |
|---|---|
| `WRITE_DAC`, `WRITE_OWNER`, owner-implicit `WRITE_DAC` on any ancestor, including the volume root and intermediate ancestors such as `AppData` below a checked profile | Refused for X and O (and A where A is checked) |
| Those rights reached through a group, a logon-type SID, a foreign logon SID, a generic or `MAXIMUM_ALLOWED` bit, or an ACE that a deny for a logon-dependent SID does not bind | Refused: the same upper-bound evaluator (and AuthZ in production) is used |
| An adversary-owned ancestor with an effective `OWNER RIGHTS` ACE (the clone root above `.git`) | Accepted: Windows then grants the owner only that ACE. An inherit-only `OWNER RIGHTS` ACE does not count, and one granting `WRITE_OWNER` refuses |
| `WRITE_ATTRIBUTES` on an ancestor | Not a take-over: a non-empty directory cannot be made a reparse point, and enabling per-directory case sensitivity also requires `FILE_DELETE_CHILD`, which is already refused on every parent. Both are documented OS behaviour, not observed here; E-12 must attack them |
| `ACCESS_SYSTEM_SECURITY`, take-ownership and restore privileges | Need a privilege; X and O hold only the standard-user allowlist |
| A station reporting another logon session's, X's or SYSTEM's SID, with any desktop facts | Refused |
| A SID-less station that is SYSTEM's, LocalService's or another session's, or a look-alike name (zero-padded, prefixed, no `$`, a Unicode letter that case-folds to ASCII) | Refused; names are compared folding ASCII only (B-10) |
| A SID-less station with A's name created by someone else, or a station or desktop X or O can open (hook, input, clipboard, create desktop) | Refused by the owner and DACL check |
| A reparse file or directory directly in a `PATH` or working directory, whatever its own descriptor; a directory link whose target is a file | Refused without following it |
| A hard link, short name or alternate stream of a file in a `PATH` directory | Same file, same descriptor: checked |
| Subdirectories of `PATH` directories | Never searched, never opened (B-15a); a reparse subdirectory entry is refused from the listing's own attributes. A walked authority, `.git` or install-root entry refuses if either the listing or its handle reports a reparse point |
| New facts FU1 reads | `TOKEN_STATISTICS.AuthenticationId` of A's token; the owner and DACL of A's window station and desktop (`GetSecurityInfo`, `SE_WINDOW_OBJECT`); each listing entry's reparse attribute. All read-only; nothing is set, created or followed |

**Final status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**
