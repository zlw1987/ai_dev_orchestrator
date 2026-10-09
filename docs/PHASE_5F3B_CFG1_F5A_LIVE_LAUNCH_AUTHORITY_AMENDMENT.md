# Phase 5F3B-CFG1-F5A — Out-of-Tree Pi Startup Delete Authority (Design Amendment)

```text
5F3B-CFG1-F5A-LIVE-LAUNCH-AUTHORITY-AMENDMENT   R1-FU2 + U126 BYTE REVIEW (§8.10.8)
REVISION                                        R1 supersedes R0 (R0 rejected by the measured
                                                Q-probe results, §5; R0 was never implemented
                                                and never granted any authority).
                                                R1-FU1 corrects three R1 review blockers:
                                                (1) destination population escaped the run
                                                root's pinned authority (§7.4A);
                                                (2) unverified source bytes were persisted
                                                before their digest was proven (§7.4B);
                                                (3) 126 approved files had no classification
                                                from frozen evidence (§8.10).
                                                R1-FU2 corrects two R1-FU1 review blockers:
                                                (A) the read-relocation criterion was too weak;
                                                it is corrected and yields a NON-EMPTY set of 57
                                                reachable files whose reads frozen evidence does
                                                not bound -> HOLD (§8.10);
                                                (B) live_references_released was left as an
                                                unconditional True; it is now a derived fact
                                                (§7.8.1).
                                                R1-FU2 ADDENDUM (§8.10.8): approved bytes for
                                                exactly the 57 files were recovered from the
                                                public registry, each proven equal to its
                                                committed inventory entry (57/57), and
                                                statically reviewed. U126_READ_UNPROVEN is now
                                                EMPTY. This is new evidence recorded here, NOT
                                                yet independently reviewed or frozen; the HOLD
                                                stands until D-F5A-9 is accepted.
KIND                                            DESIGN AMENDMENT (additive, layered)
AUTHORIZES                                      NOTHING — no implementation, no test, no
                                                policy/profile change, no Node/Pi/npm, no E5,
                                                no E6, no PE-6, no live run
AUTHORITATIVE HEAD                              6fa2fd4aeec343da907a0013f2c131e197eff6d6
F5-A                                            OPEN — this document proposes a closure; it
                                                does NOT claim F5-A closed
F5-B                                            CLOSED BY EXISTING MECHANICAL AUTHORITY (§3)
F5-C                                            ACCEPTED NON-AUTHORITY / PRIVACY RESIDUAL —
                                                confirmed, NOT reopened (§4)
PE-3 / PE-4 / PE-5                              ACCEPTED / FROZEN — not edited, not reopened
```

> **This is a design candidate. It grants no implementation authority and no
> live authority.** It layers on top of the frozen CFG1 chain and HPP-1 and edits
> none of their documents. Where it is silent, the frozen documents govern
> exactly as accepted.

## 0. Reading rule, precedence and disclosure

1. **Effective design if accepted** = the frozen CFG1 chain (base launch
   configuration isolation design incl. FU15 §37, L16-FU2/ERR1, FU1 R6, OC-3
   AMEND1, Y6 AMEND2, OC-4, OC-5, the P1 topology admissibility amendment) +
   PE-0 R3 (HPP-1) + PE-1 R2 + **this amendment (R1)**. This amendment governs
   only the clauses it names in §11; every other clause is preserved (§12).
2. **R0 is superseded, not amended.** R0's held-slot design (occupant `Q`,
   write-capable derivation pins, conditional retention) is rejected by measured
   evidence (§5) and is **not** part of the effective design in any form. §5 keeps
   it only as the history explaining the rejection.
3. **Historical documents are immutable.** PE-4A F-4/F-5, the P1 amendment,
   FU15 §37 and every v1/v2/v3 artifact keep their bytes and their historical
   meaning. Where this amendment changes a forward-looking characterization it
   says so explicitly (§11.6) instead of editing the old text.
4. **Normative words** "must", "exactly", "only", "never" are normative. A
   refusal means fail closed with no partial result.
5. **Disclosure of what the R1 authoring turn did (exact).** It read repository
   documents and source inside `C:\dev\ai_dev_orchestrator`, including the
   untracked probe module `experiments/pi_harness_cfg1/tests/test_cfg1_f5a_windows_handle_probes.py`
   (read only, not executed by this turn, not edited). It statically read (never
   executed) installed Pi package files, and **relied on an installed file's
   content only after a standard-library SHA-256 showed its bytes equal the
   approved PE-3 inventory digest for that path** (§1.1). In doing so it found
   that the PATH-selected global installation **no longer equals the approved
   payload** (§1.2); files whose installed bytes now differ were not relied on,
   and for them this document uses only R0's digest-bound citations (recorded at
   R0 authoring time) or the frozen AIDO contracts. A read-only attempt to
   recover approved bytes for those files from the local npm cache was refused by
   the session's permission policy and was **not** pursued; nothing from that
   source is relied on. It ran read-only `git`, `grep`, `sed`, `ls`, `cat` and
   standard-library Python one-offs that only read files (digest comparison,
   inventory/manifest statistics, a regex scan of import specifiers, §8.2). It
   ran **no** Node, Pi, npm or JavaScript; ran no test; contacted no backend,
   model or B300; read no credential or endpoint value; modified only this file;
   staged and committed nothing.
6. **Disclosure of what the R1-FU1 authoring turn did (exact).** It read this
   document, the frozen PE-4A evidence document, FU15 §37 of the base design, the
   committed approved inventory and manifest bundle for profile `56651d0b…`, and
   `win_config_authority.py` (read only). It ran standard-library Python one-offs,
   kept in the session scratchpad **outside the repository**, that (a) hashed the
   installed global files against the approved inventory to enumerate the 126
   paths of §1.2, (b) re-implemented PE-4A Appendix B's partition and **checked
   the result against PE-4A §7.2's frozen group path-list digests** (§8.10.2), and
   (c) ran a keyword search over the *installed 1.1.0* copies of the reachable
   unavailable files as a **negative-search sanity check only**; no statement in
   this document cites those 1.1.0 bytes as evidence, and the one place they were
   used (edges out of the 126 files, as a hypothesis for (b)) is validated by the
   frozen digests, not by the bytes. **It also ran `npm root -g` once, in error,**
   while locating the global installation — contrary to this turn's "no npm"
   instruction. That command only prints the configured global prefix; it
   installed, fetched, updated and executed nothing, and its output was not used.
   It ran no Node, Pi or JavaScript; no test; contacted no network, backend,
   model or B300; read no credential or endpoint value; modified only this file;
   staged and committed nothing.
7. **Disclosure of what the R1-FU2 authoring turn did (exact).** It re-read this
   document and the frozen PE-4A evidence; read `run_contract.py`,
   `run_executor.py` and `stage_runner.py` (read only) for the
   `live_references_released` fact; and re-ran standard-library Python one-offs in
   the session scratchpad **outside the repository**. One of them listed, for
   each unavailable file, the importers that exist in the *available* approved
   set; it was **not** used as evidence, because it cannot see imports that come
   from unavailable files. It used **no** installed 1.1.0 bytes as evidence. It
   ran **no** Node, Pi, npm or JavaScript (the earlier `npm root -g` slip of the
   R1-FU1 turn was not repeated); no test; no network, backend, model or
   credential; modified only this file; staged and committed nothing.

---

## 1. Exact inherited frozen state

| Item | Frozen fact (inherited, not re-derived) |
|---|---|
| HEAD | `6fa2fd4aeec343da907a0013f2c131e197eff6d6` (`policy(cfg1): adopt first HPP-1 Pi profile`) |
| Working tree at start of R1 | exactly three untracked files: this document (R0), `experiments/pi_harness_cfg1/tests/test_cfg1_f5_startup_effects.py` (F5-B exploratory test, untouched), `experiments/pi_harness_cfg1/tests/test_cfg1_f5a_windows_handle_probes.py` (Q1–Q6 probe evidence, untouched) |
| APS head | `aps.r0002.json`, sha256 `606eca52…f6fda799`; eligible `{56651d0b2b6995e05b6de3aa012f5a82f276b2ac817dcce00844d1db2a9ffd67}` |
| Approved profile | `profile_id 56651d0b…`, `payload_fingerprint 66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc`, declared `1.0.3` (provenance only), approval `c9c31346…cbf6d1a`, class `C3_SEAM_CHANGED`, 31 `resolution_exposures` |
| Approved payload size | 16 482 inventory entries (1 436 `dir`, 15 046 `file`), 123 329 349 file bytes; 4 858 `.js/.mjs/.cjs` files; no `dist/package.json`; no `src`; exactly 4 directories named `node_modules`, all **descendants** of the payload root |
| P (PE-1 §11.1) | P0 reads exactly ambient `PATH`; P1 first admissible `node.exe` + `pi.cmd`-anchored package root (P1 amendment); P2 complete PI-PC1 walk; P2M exact membership; P2X exposure absence; P2R `I_r` then `I_n`. **P executes nothing and writes nothing.** |
| L1 | runs P from scratch before any resource exists; commits the profile family atomically; refuses before L4 (credentials) |
| L14 | `reprove_pi_identity_for_launch`: complete walk, **equality** with L1's matched profile fingerprint, exposures absent, `I_r`, `I_n`; nothing reads the Pi tree between its `True` and `Popen` |
| L21A | after L24, before L25: complete walk, exposures, `I_r` → `CHANGED`/`UNPROVEN`/`PROVEN_UNCHANGED` |
| Launch argv | frozen `ar2.launch.build_pi_argv` reads exactly `identity.node_executable` and `identity.pi_cli_js`; passes `--no-extensions --extension <AIDO entry> --offline …` |
| Child environment | `environment.build_cfg1_child_environment`: positive allowlist = 9 `BASE_WINDOWS_NAMES` + narrowed `PATH` + `PI_CODING_AGENT_DIR` + `PI_OFFLINE` + `PI_SKIP_VERSION_CHECK` + `PI_TELEMETRY` + one credential carrier; **T-4** pins its equality with I2's builder. No `PI_PACKAGE_DIR`, `PI_MANAGED_INSTALL_ROOT`, `NODE_OPTIONS`, `NODE_PATH` |
| Owned root | `ar2.fixtures.build_case_repository` → `mkdtemp` under the realpath'd temp scratch boundary + exclusive-create nonce marker; CFG1 registry + single-use claim; FU15 root identity; L27 = re-proof then frozen `remove_disposable_tree` |
| Namespace authority | FU15-D1 §37.3.2a: L27's root-namespace teardown authority covers any descendant of a minted root, never a redirect out of it; scoped to minted run roots only |
| Same-user adversary | FU15 §37.1: concurrent same-user filesystem tampering is **inside** the model, unnarrowed |
| Accepted residuals | PE-1 §27 incl. R-EXT-1…6, R-ABA, R-SLIVER, R-COST, R-SHARED, R-WINDOW (FU15) |
| v3 record vocabulary | `REFUSAL_STEPS = {L1…L18}` (`lifecycle.py`); `PRE_DISPATCH_REFUSAL_CODES_V2` and `REFUSAL_CODES_BY_STEP` shared by v2 and v3 validators (`records.py`); highest frozen v3 rule `R3-S14` |
| F-5 (PE-4A, L) | carried live-launch blocker for E5 / any full Pi CLI launch / PE-6 |

### 1.1 Approved bytes this document relies on

Every Pi source fact is cited at a payload-relative path and is bound to the
approved profile by content.

| Payload path | Approved sha256 | Size | Bound how |
|---|---|---|---|
| `dist/config.js` | `b53418ca3bc54b70e18ccb192eb471696f5211c5aa2e80d68fe6fe3851ff23ae` | 22684 | **re-verified R1** (installed bytes = approved digest) |
| `dist/utils/windows-self-update.js` | `adf0360878e285988f8d74ceb2897ef8359b80a1c2fda4965aa2152de5382485` | 2789 | **re-verified R1** |
| `dist/cli.js` | `8189b66abc4f9f431dbb70941dcba690d76d040de1fbfff212886be35a53639d` | 169 | **re-verified R1** |
| `dist/cli/setup.js` | `4a2a7a0dbf82e2e5d18cec90896b36cbedce78b3d09e78d4040ac94fa3fbeba8` | 501 | **re-verified R1** |
| `dist/core/extensions/loader.js` | `44a356da552c9cf2ea619c61944cfb28f81b45f09b325f152c91a914bfce1bc0` | 28872 | **re-verified R1** |
| `node_modules/@earendil-works/pi-ai/dist/env-api-keys.js` | `8166f316e3c8adaa8c089561c644169a89fdc9ef2d67a752bbba738a5415a616` | 7813 | **re-verified R1** |
| `node_modules/@earendil-works/pi-ai/dist/auth/context.js` | `5d0ea91a2fd2acf84e3b9717ce59e75006933c68d8efa91873894a9d963d41a0` | 1666 | **re-verified R1** |
| `node_modules/@earendil-works/pi-ai/dist/providers/google-vertex.js` | `26c13449ea7b57d40878742db956210e70af0c89638cb87a1d9b4739f2bac59a` | 4282 | **re-verified R1** |
| `package.json` | `4c4956a9a414f7fbc697f519515f2dc424d2c1c49df2d90d4201366e6227aaf1` | 4062 | committed manifest bundle (bytes bound to the inventory entry by size and SHA-256); frozen PE-4A §6.1/§6.2 (`piConfig` carries only `configDir`, so `APP_NAME = "pi"`; `bin.pi → dist/bundle/cli.js`) |
| `dist/main.js` | `060521b0b81f91948d8ded9139e423e5d0c9e6808a45c81750cc30519de4d2db` | 37764 | **frozen PE-4A** (Appendix C lists this exact digest; §7.3 row for `windows-self-update.js` cites `main.js:460-462`; §8.1; F-5). Installed bytes now differ, so nothing here is re-read from disk |
| `dist/core/system-prompt.js` | `83aa42fae07830d5a73431935af3390ec397d8333269d75cfe49c1afbc55369c` | 7787 | **frozen PE-4A** (Appendix C lists this digest; G-11; F-4). Not re-read from disk |
| `dist/modes/interactive/theme/theme.js` | `a7b93b9cc50d9f44c2a728c8df5de67dc41efead57d1554e0ff32b73bb358cf4` | 34689 | digest from the committed inventory; behavior bounded by **frozen PE-4A** §7.2 (D5 row: theme JSONs are read by `initTheme`, colors only) and §9.2 (`[FP-E]`). Not re-read from disk |

### 1.2 Observation: the ambient installation is no longer the approved payload

A full comparison of the PATH-selected global installation
(`<npm-prefix>\node_modules\@earendil-works\pi-coding-agent`) against the
approved inventory found **381 digest mismatches and 56 extra paths**; its
`package.json` declares `1.1.0`, rewritten 2026-10-07 17:20 local time. L1 would
therefore classify it as unapproved today. This is an environment fact, not a
design defect: P/L1 are unchanged and would refuse correctly. It does mean that
**any future E5 requires an approved source installation to be present** (§17,
condition 9); obtaining one is outside this document. Of the 4 858 approved JS
files, 4 732 still match their approved digests and **126 do not** (92 differ,
34 are absent). The 126 are the set `U126` (path-list SHA-256
`775a8f9d1d02ffdd9f31c518bbad88c8727df381d80abe1f8f67fac27d6e3dba` over the
sorted, newline-joined payload-relative paths). Their approved bytes are not
locally available, so **no statement in this document is derived from reading
them**; each of the 126 is classified from the frozen PE-4A evidence in §8.10:
69 are excluded (not loaded, or closed by a location-independent gate), and **57
are not** (`U126_READ_UNPROVEN`, §8.10.5). *(Superseded by §8.10.8: the 57 approved
files were later recovered and reviewed, and the set is now empty. The text above
is the state at the authoring instant and is kept as history.)*

---

## 2. F5-A threat model

### 2.1 The frozen fact

On `win32`, `dist/main.js:460-462` calls
`cleanupWindowsSelfUpdateQuarantine(getPackageDir())` on every start, before any
mode is selected and before any RPC command can be answered.

**Frozen provenance (R1-FU1).** This fact is recorded in the accepted PE-4A
evidence, not only in superseded R0: §7.3's gate table row
"`cleanupWindowsSelfUpdateQuarantine(getPackageDir())` runs on every `win32`
start (`main.js:460-462`)" → **EXECUTES AT STARTUP (F-5)**, file
`dist/utils/windows-self-update.js`; §7.3 "Startup-executed behaviors" item (i)
("on `win32` Pi recursively deletes `<enclosing node_modules>/.pi-native-quarantine`
if present — a delete *outside* both the payload root and AIDO's workspace");
§8.1 (`windows-self-update.js`, depth **whole**: "recursive delete of
`<node_modules>/.pi-native-quarantine` on every win32 start (F-5)"); §14 **F-5**
(severity **L**, the carried live-launch blocker). `dist/main.js` itself has the
frozen digest above (PE-4A Appendix C). The derivation in §2.2 below was
re-verified in R1 against the approved bytes of `dist/config.js` and
`dist/utils/windows-self-update.js`, which still match their approved digests.

### 2.2 The exact derivation (profile `56651d0b…`, static, R1-re-verified bytes)

```text
getPackageDir()                                  dist/config.js:315-326
  1. process.env.PI_PACKAGE_DIR, if non-empty    -> normalizePath(value)
  2. isBunBinary (config.js:18: import.meta.url contains "$bunfs" | "~BUN" | "%7EBUN")
                                                 -> dirname(process.execPath)
  3. findNodePackageDir(__dirname of config.js)  dist/config.js:299-314
       walk up from <__dirname>: first dir holding package.json; a dir named
       "dist" whose parent also holds package.json yields the parent;
       none found -> startDir (= __dirname itself)

getQuarantineRoot(packageDir)                    dist/utils/windows-self-update.js:9-21
  current = resolve(packageDir)            (lexical; touches no filesystem)
  loop: if basename(current).toLowerCase() === "node_modules"
           -> join(current, ".pi-native-quarantine")
        if dirname(current) === current -> undefined
        current = dirname(current)
  (the loop tests packageDir ITSELF first, then every lexical ancestor)

cleanupWindowsSelfUpdateQuarantine               windows-self-update.js:44-55
  quarantineRoot = getQuarantineRoot(packageDir)
  if (!quarantineRoot) return;                    <- NO DELETE
  rmSync(quarantineRoot, { recursive: true, force: true }) inside try { } catch { }
```

For the PATH-selected global npm installation the target is
`<npm-prefix>\node_modules\.pi-native-quarantine`: outside the payload, outside
every AIDO-minted root, inside a **shared** directory (R-SHARED).

### 2.3 Threat statement

AIDO's L14 `launch()` is the act that causes this code to run. Whatever the
genuine, approved Pi code deletes at startup is therefore deleted **under AIDO's
launch authority**. The frozen invariant AIDO must keep is FU15 §37.1's: *no
cleanup ever deletes or mutates a resource whose ownership is not mechanically
proven* — and Pi's startup quarantine cleanup is a recursive cleanup. At the
external target AIDO cannot rule out: another Pi process's genuine quarantine;
anything any tool or person put at that name (**the name is not provenance**);
a same-user reparse point there, whose traversal by Node's recursive `rmSync`
this design does not assume either way.

### 2.4 R1 safety invariant (the closure criterion)

R0's invariant ("the target is an AIDO-held object the cleanup cannot remove")
is **withdrawn**: its premises Q2/Q3/Q4 are falsified (§5). R1 replaces it with
an invariant based on **target nonexistence**:

> **INV-F5A-R1.** Immediately before launch of the proven RPR launch identity
> `L`, AIDO proves that the approved profile's genuine startup cleanup
> derivation (§2.2, as recorded for that profile in the LDT, §7.3) yields **no
> quarantine target** under the selected run-private topology: (a) the child
> environment carries no `PI_PACKAGE_DIR`; (b) the Bun branch is false; and
> (c) **no component** of the lexical path from the volume root to
> `C\dist\config.js` is named `node_modules` (case-insensitively), and every one
> of those components is a plain, non-reparse object, so the module URL Node
> assigns to the genuine `dist/config.js` carries that same component chain.

No name-only ownership argument is needed, because **no destructive target is
derived**: there is no object whose provenance AIDO must prove. The proof is a
proof at an instant (L14, §7.7); changes after it are governed by §9 (inherited
R-SLIVER/R-ABA), never claimed resisted.

### 2.5 What is not F5-A

- **Code substitution.** A same-user actor that rewrites or redirects payload
  objects after the last AIDO proof (R-SLIVER / R-ABA) can make Pi run
  *arbitrary* code, which may delete anything. That is the existing accepted
  residual of every launch, not narrowed or widened here. F5-A is about
  **genuine** code on the **proven** topology.
- **The second startup delete** `cleanupManagedInstall()` (`main.js:463`) is
  gated on `PI_MANAGED_INSTALL_ROOT` (`dist/package-manager-cli.js:23-27`), which
  the positive allowlist never forwards (T-4). Unchanged and still unreachable.
  (Provenance: the call and its gate are **not** in the frozen PE-4A record;
  they come from the approved-byte-bound R0 authoring evidence, together with
  the frozen T-4 allowlist. **ACCEPTED BY INDEPENDENT REVIEW** — §8.10.7 item 3,
  **D-F5A-8**.)

---

## 3. F5-B — CLOSED BY EXISTING MECHANICAL AUTHORITY

Disposition recorded as received, not redesigned. Pi's startup writes
(`auth.json`, `models-store.json`, `proper-lockfile` `*.lock` entries) land under
`PI_CODING_AGENT_DIR`, whose only source is the verified issuance record's
`config_dir`, a direct child of the minted root; L27's namespace teardown removes
them without following a reparse point.

Interaction with R1: the agent-directory variable name is
`${APP_NAME}_CODING_AGENT_DIR` (`config.js:471-476`), and `APP_NAME` comes from
the launched payload's own `package.json` (`config.js:456-471`). Under R1 that
file is `C\package.json`, proven byte-equal to the approved `package.json`
(`piConfig = {"configDir": ".pi"}` → `APP_NAME = "pi"`), so the variable remains
exactly `PI_CODING_AGENT_DIR`. `getPackageDir()` resolves to `C` (§8.3). F5-B's
premise is unchanged; its disposition remains pending only the separate byte
review of the exploratory regression test, which this document does not touch.

---

## 4. F5-C — ACCEPTED RESIDUAL (confirmed, not reopened)

Each condition of the review disposition was checked against the
approved-digest-bound source (§1.1; the three `pi-ai` files were re-verified in
R1). All hold; **F5-C remains an accepted non-authority / privacy residual and no
`USERPROFILE` redirect is designed.**

| Condition | Verdict | Evidence |
|---|---|---|
| only existence is probed | **holds** | `env-api-keys.js:39-66`: `_existsSync(GOOGLE_APPLICATION_CREDENTIALS)` or `_existsSync(join(homedir(), ".config","gcloud","application_default_credentials.json"))`; `auth/context.js:25-38`: `fs.access(resolved)` only |
| no credential content is read | **holds** | no read of the ADC path on the startup/availability path; other references are reached only via `pi login`-style commands or a selected-and-resolved Vertex provider |
| no credential value is forwarded | **holds** | the child environment is a positive allowlist; no Google name is in it |
| `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` cannot reach the child | **holds** | not in the allowlist |
| the result cannot make Vertex usable or select CFG1's model/provider | **holds** | the bit feeds only `hasCredentials && hasProject && hasLocation` (`env-api-keys.js:140`) and `hasCredentials && project && location` (`google-vertex.js:75`), both constant-false; CFG1's argv fixes `--provider`/`--model` |
| not emitted to the model/backend | **holds** | both consumers are constant-false: no data dependency to emit |
| not used in any AIDO authority decision | **holds** | AIDO never observes it |

R1 does not alter this residual (the probe is relative to the OS-resolved home,
never to the package directory).

---

## 5. R0 rejection — measured probe results (historical evidence)

R0 proposed a run-provisioned copy at `R\pi_runtime\node_modules\@earendil-works\pi-coding-agent`,
a held regular-file occupant `Q = R\pi_runtime\node_modules\.pi-native-quarantine`
(share 0) as the cleanup's undeletable target, and four write-capable
`FILE_SHARE_READ` derivation pins kept from their creating handles. Its closure
rested on six Windows premises, Q1–Q6. The target-Windows probes in the
untracked module `experiments/pi_harness_cfg1/tests/test_cfg1_f5a_windows_handle_probes.py`
(attacker's own Win32 operations against synthetic `tmp_path` trees, each refusal
paired with a released-pin control) produced:

| Id | Premise | Result | Measured fact |
|---|---|---|---|
| Q1 | a share-0 held regular file cannot be deleted, renamed, replaced or overwritten | **PASS** | every supported delete / rename / replace / overwrite operation was refused while held and succeeded in the released control |
| Q2 | no admitted second handle can convert the held file into a reparse point | **FAIL** | `FILE_WRITE_ATTRIBUTES`-only second handles are **admitted** by share mode 0 and can apply a reparse point to the held file. `Q` therefore cannot be an invariantly undeletable / non-redirectable target |
| Q3 | the held derivation files cannot be deleted, renamed, replaced or converted, and no ancestor can be renamed | **FAIL as a whole** | the derivation files can likewise be reparse-converted. **Sub-premise PASS:** while the child files were held, renames of every required ancestor (`dist`, `pi-coding-agent`, `@earendil-works`, `node_modules`, `pi_runtime`, and the synthetic root) were refused, and the same renames succeeded after release. A gap-free `ReOpenFile` successor keeping share READ was not obtainable |
| Q4 | the genuine PI-PC1 readers succeed on the held derivation files | **FAIL for the R0 pin shape** | the **write-capable** creating handles conflict with the genuine PI-PC1 readers. Cause-isolating control: a **read-only-access** (`GENERIC_READ`), share-READ pin acquired after population **permits** the genuine PI-PC1 walk |
| Q5 | pin-time reparse refusal during construction | **PASS** | a just-created directory turned into a redirect is refused at its pin; `CREATE_NEW` with open-reparse-point does not follow a planted file symlink |
| Q6 | after release, frozen teardown removes the root without following planted redirects | **PASS** | the frozen CFG1 teardown removed the owned root without following planted redirects and preserved outside bytes, attributes and mtimes; the `os.chmod` retry path **was exercised** against redirect paths and did not mutate the outside targets |

**Disposition.** R0 was **not implemented and granted no authority.** Q2 removes
the only property that made `Q` a safe target, and the Q-occupant design is not
repaired: R1 removes the target instead of trying to make it undeletable. The
probe module is **evidence only**; R1 does not edit it and does not cite Q1/Q2
as implementation premises. Two measured facts are carried forward as evidence
for R1's narrower pin design (§7.6): the Q3 ancestor-rename sub-premise, and the
Q4 read-only-pin control. Q5 and Q6 remain relevant as regressions (§13).

---

## 6. Option comparison

### 6.1 Summary

| # | Family | Satisfies INV-F5A-R1? | Frozen surfaces it must amend | Verdict |
|---|---|---|---|---|
| **A2-R1** | **Per-run AIDO-provisioned runtime copy at `R\pi_runtime\pi-coding-agent`: no `node_modules` component anywhere above the package root, so no target is derived** | **yes** (§8) | executor step `L3R`; one read-only constructor in `pi_identity`; v3 refusal vocabulary (+1 step, +1 code); L14 executor precondition; L27 entry release | **CHOSEN** |
| A2-R0 | Same copy under `RT\node_modules\@earendil-works\…` plus held occupant `Q` | **no** — Q2/Q3 FAIL (§5) | as R1 plus occupant lifecycle | **rejected by measured evidence** |
| A1 | One-time persistent AIDO-managed installation | yes in principle (same topology) | P0 or a new selector; a persistent cross-process ownership authority; update/GC lifecycle; shared-install concurrency | rejected — larger authority surface (§6.2) |
| B | `PI_PACKAGE_DIR` redirection to an AIDO shadow dir | only by splitting code root from asset root | T-4/I2 equality; agent-dir premise; profile coverage (second root); PE-4A F-4 | rejected (§6.3) |
| C | Process-level confinement (write-restricted token) | yes for deletes | AR2 launch, AR2 broker DACL, AR0-FU1 stance; empirical Node compatibility | rejected — not smallest; a future hardening |
| D | Explicit acceptance of the external delete | **no** | weakens FU15 §37.1 | not chosen |
| E1 | Occupy-and-hold the **external** slot in the npm prefix | **no** — the held object is reparse-convertible exactly as `Q` (Q2) | first AIDO write/delete authority in a foreign shared namespace | rejected |
| E2 | Hold a handle on an existing external quarantine dir | **no** | — | rejected |
| E3 | Pre-launch absence check of the external slot | **no** (TOCTOU) | — | rejected (prohibited) |
| E4 | A Pi flag/env to skip the cleanup | n/a | — | does not exist: the only gate is `process.platform === "win32"` (`main.js:460`) |
| E5 | Link-based relocation (symlink/junction/`--preserve-symlinks-main`) | **no** | argv/env | rejected: Node realpaths the main module, so a link maps `getPackageDir()` back into the foreign tree and **restores** the foreign target |

### 6.2 A1 vs A2 (unchanged reasoning, R1 topology)

A2 reuses the frozen mint + marker + claim + FU15 root identity + §37.3.2a
namespace authority; needs no selector (the copy path is a constant under the
verified run root); has no shared-install concurrency, no retained install whose
approval could be silently inherited, and no update/garbage-collection
lifecycle. A1 differs from A2 only by adding a new authority, lifecycle or
selection surface in every row. Rejected.

### 6.3 Why B is still not chosen, although R1 relies on the same rule

R0 noted that B's "no `node_modules` ancestor → no delete" was "one profile's
code path". R1 relies on exactly that rule, but **explicitly**: it is recorded,
by profile id, in a reviewed CFG1 Launch Derivation Table (§7.3), and every
profile without an entry fails closed. B's other defects are independent of that
rule and stand: a new child-environment name breaks **T-4**; Pi's code would
still run from the shared global tree while `package.json`, themes and docs are
read from an AIDO-written second root (two-root profile coverage; the
agent-directory-name premise would depend on a file outside the payload);
model-visible documentation paths would point at a shadow root.

### 6.4 Representation: exact byte copy only

| Representation | Verdict | Why |
|---|---|---|
| **Exact byte copy** (`CreateDirectoryW` + `CreateFileW CREATE_NEW`) | **chosen** | every object in the copy is AIDO-created inside the minted root; profile identity is content-only (§8.7) |
| NTFS hard links to the source files | rejected | the copy's files would *be* the foreign shared objects (R-SHARED restored); `CreateHardLinkW` mutates foreign link-count metadata |
| Symlinks / junctions | rejected | PI-PC1 refuses reparse points; Node's realpath would restore the foreign package directory and its foreign target |
| `--preserve-symlinks-main`, `NODE_OPTIONS`, bundles/archives | rejected | change frozen argv / env / launch target |

No `pi.cmd` is created (A2 never selects through PATH), and none of Pi's own
managed-install names (`PI_MANAGED_INSTALL_ROOT`, `managed-install.json`,
`releases-v1`) is used.

---

## 7. Chosen mechanism — A2-R1 "run-provisioned Pi runtime" (RPR)

### 7.1 Overview

```text
L1   P proves the ambient PATH-selected installation          (UNCHANGED)
       -> source identity S: node.exe I_n, source root, matched profile X
L2   mint + claim the run root R                              (UNCHANGED)
L3   workspace baseline                                       (UNCHANGED)
L3R  RUN-PROVISIONED PI RUNTIME                               (NEW, pre-credential)
       topology admission; construct X's payload at C = R\pi_runtime\pi-coding-agent
       UNDER A CONTINUOUSLY PINNED, PARENTAGE-PROVEN DIRECTORY CHAIN (§7.4A), writing
       only source bytes already proven equal to the approved inventory (§7.4B);
       close every write-capable handle and release the construction pins; acquire
       the final READ-ONLY pins; post-pin validation (content = X, exposures,
       topology); bind launch identity L (node from S, root = C); drop S
L4.. credentials, route, capability, config, broker, extension, env (UNCHANGED)
L14  executor precondition: provision bound + pins held + topology re-proof (NEW)
     then build_supervisor(L) + reprove_pi_identity_for_launch(L) + launch  (code UNCHANGED, input = L)
L21A reobserve_pi_profile_after_runtime(L)                    (code UNCHANGED, input = L)
L27  release the final pins (unconditional, exactly once), then the frozen re-proof + removal
```

The PATH-selected installation becomes **only** a byte supply, the source of
`node.exe` and the stage's profile commitment. Pi never runs from it.

### 7.2 Fixed topology (CFG1 constants, never a parameter)

```text
R  = verify_cfg1_run_workspace(...)'s experiment_root   (realpath'd at mint, re-proved)
RT = R\pi_runtime                                       (AIDO-created plain directory)
C  = RT\pi-coding-agent                                 (AIDO-created; = copy payload root)

C\package.json, C\dist\…, C\docs\…, C\examples\…, C\node_modules\…   (exact PI-PC1 copy)
```

Topology rules, each enforced at L3R admission, at post-pin validation, and again
in the L14 precondition:

- **T-NM (no `node_modules` ancestor).** No component of the lexical path from
  the volume root through `C\dist\config.js` satisfies
  `component.lower() == "node_modules"` or
  `component.casefold() == "node_modules"`. The scan covers the **entire**
  chain — the volume root's children, every ancestor of the temp scratch
  boundary, the scratch boundary, `R`, `RT`, `C` and `dist` — not merely `RT` and
  `R`. If the OS temp/scratch ancestry itself contains a `node_modules`
  component, L3R refuses. (JS `toLowerCase` maps only ASCII capitals onto the
  letters of `node_modules`; testing both Python folds is a fail-closed superset.)
  `C`'s own **descendant** `C\node_modules` is irrelevant: the derivation walks
  only upward from the package directory.
- **T-CANON.** The path is drive-letter absolute (`X:\…`; no UNC, `\\?\`, device
  or relative form), `ntpath.normpath(p) == p`, and no component is `.`/`..` or
  ends in `.` or a space.
- **T-PLAIN.** Every component from the volume root's first child through
  `C\dist`, inspected with the existing no-follow leaf, is a plain directory with
  no reparse attribute; `C\dist\cli.js`, `C\dist\main.js`, `C\dist\config.js` and
  `C\package.json` are plain regular files with no reparse attribute. A reparse
  component anywhere (including one the user's profile legitimately contains)
  refuses — an availability effect only.
- **T-BUN.** The path contains none of `$bunfs`, `~bun`, `%7ebun`
  (case-insensitive superset of `config.js:18`).
- **T-RT.** `RT`'s child set is exactly `{pi-coding-agent}`; `RT\node_modules`
  and `R\node_modules` are no-follow `MISSING`.

There is **no** `RT\node_modules`, **no** `@earendil-works` parent, and **no**
`.pi-native-quarantine` object of any kind.

### 7.3 Launch Derivation Table (LDT) — the profile-bound part

F5-A's closure depends on how a given profile derives its delete target, so it
is bound to the profile **by profile id**, in CFG1 code (not HPP policy):

```text
LDT = {
  "56651d0b2b6995e05b6de3aa012f5a82f276b2ac817dcce00844d1db2a9ffd67": {
      "quarantine_rule": "NO_NODE_MODULES_ANCESTOR_MEANS_NO_TARGET",
      "derivation_chain": ("dist/cli.js", "dist/main.js", "dist/config.js"),
      "package_manifest": "package.json",
      "forbidden_path_substrings": ("$bunfs", "~bun", "%7ebun"),   # case-insensitive
      "withheld_env": ("PI_PACKAGE_DIR", "PI_MANAGED_INSTALL_ROOT"),
  },
}
```

- The key is the **profile id**, never declared version text.
- A matched profile with **no LDT entry refuses at L3R** (fail closed). An
  HPP-approved profile without a reviewed LDT entry remains ineligible for any
  full CLI launch.
- `derivation_chain` is the module chain whose resolved URLs decide
  `config.js`'s `import.meta.url` (`cli.js:3` imports `./main.js`; `main.js:21`
  imports `./config.js`). `windows-self-update.js` is **not** an input: it
  receives `packageDir` as an argument and its own location is irrelevant.
- The entry's paths must be `file` entries of the committed approved inventory
  (checked by a repo-local test, §13).
- `quarantine_rule` names the reviewed static fact of §2.2/§8.4: the target is
  `undefined` whenever no component of `resolve(getPackageDir())` is named
  `node_modules`.

### 7.4 Provisioning (L3R), in fixed order

1. **Bind inputs.** `S` = the executor's L1 identity (exact type); the
   workspace re-proved with `verify_cfg1_run_workspace`; `R`'s identity re-proved
   from a handle against `registered_root_identity` (FU15 §37.3.1 step 2 shape);
   the LDT entry for `S.matched_profile_id` exists.
2. **Topology admission.** T-NM, T-CANON, T-BUN on the full constant path of
   `C\dist\config.js`; T-PLAIN on the existing chain through `R`; `RT` absent.
   Any failure refuses **before any write**.
3. **Write-ahead.** `state.runtime_provision` is set to an attempted provision
   object **before** the first create, so L27 always knows what to release. The
   object carries the **handle ledger** of §7.4A.5: every directory pin and every
   zero-byte child handle AIDO opens during construction is entered in it at the
   moment of acquisition.
4. **Source observation.** A complete PI-PC1 walk of `S.pi_package_root` with the
   genuine leaves; it must be complete and its fingerprint must **equal** `X`'s.
   Its in-memory inventory `I` — which, by that equality, **is** `X`'s approved
   inventory — is the copy manifest; names are PI-PC1-grammar-validated before
   any join; nothing else from the source tree is trusted. **The walk is an
   observation only. It authorizes no byte transfer:** it does not tell AIDO that
   a *later* pathname open of any source file will reach the same object (§7.4B).
5. **Root authority.** `R` is re-proved by identity and pinned (§7.4A.1, FU15
   §37.3.1 step 2 shape) before anything is created inside it.
6. **Construction.** `RT`, `C` and every descendant of `I` are constructed
   depth-first by the pinned-parent procedure of §7.4A.2: every directory is
   created and pinned while its parent's pin is held; every file is created
   zero-byte with `CREATE_NEW|FILE_FLAG_OPEN_REPARSE_POINT`, share 0, and kept as
   a handle; **no content byte is written to any file of a directory until that
   directory's parentage gate has passed**; content is the source bytes already
   proven equal to the approved entry (§7.4B) and is written **only** through the
   file's own creating handle; the creating handle's file id is recorded for the
   four LDT files. **Every write-capable handle is closed when its file is
   complete, and every construction pin is released when its directory is
   complete; none survives step 6.**
7. **Final pins** (§7.6).
8. **Post-pin validation** (§7.6). Authority begins only after it passes.
9. **Bind.** `pi_identity` constructs the launch identity `L` (sentinel-only,
   exact `Cfg1PiIdentity`, same six slots): `node_executable`/`node_identity`
   copied from `S`; `pi_package_root = C`; `pi_cli_js = C\dist\cli.js`;
   `package_root_identity = I_c` (from post-pin validation); `matched_profile_id
   = X`. The provision object records `L`, the pins and the workspace nonce.
   `state.pi_identity` is **replaced** by `L`; no reference to `S` remains in
   executor state.
10. Any failure in 1–9 → `RUNTIME_PROVISIONING_FAILED` at cursor `L3R` (§11.1);
    a raise of any other kind → `UNEXPECTED_STEP_FAILURE` at `L3R`. L3R **deletes
    nothing** — not a partial copy, not a created directory; everything it created
    stays inside `R` for L27.

### 7.4A Destination write authority (R1-FU1; corrects R1 step 6)

**What was wrong.** R1 checked a destination directory, released
pathname-only control, and later created that directory's descendants by
pathname. That is the FU15 directory-level TOCTOU class: *checked parent → a
same-user actor replaces or converts the parent → a later child pathname create
follows the substituted ancestor → AIDO writes outside its owned root.*
`FILE_FLAG_OPEN_REPARSE_POINT` on the **final** component does not prove the
ancestor chain. R1-FU1 removes the class; it does not narrow it.

**INV-F5A-W (destination write containment).**

> No destination **content** byte is written until the exact destination child
> object has been mechanically proven, **from a pinned parent handle and not by
> pathname**, to be an entry of a directory that is, at that moment, held under
> AIDO's proven run-root authority. Content is written **only** through the
> already-proven child handle, and a destination child is **never reopened by
> pathname for content writing**.

The semantic precedent is FU15 §37.3.1 (accepted, frozen): pin the parent with
share semantics that refuse rename, removal and reparse conversion; create
children `CREATE_NEW` + `FILE_FLAG_OPEN_REPARSE_POINT` with **zero** content;
obtain identity from the child's **own** handle; prove parentage by enumerating
the **pinned parent handle** (W8/W9: from the handle, one pass per handle); only
then write. R1-FU1 applies that shape at every level of the destination tree.

**7.4A.1 Run-root authority.** Before anything is created, `R` is re-proved
exactly as FU15 §37.3.1 steps 1–2: `verify_cfg1_run_workspace`, then a pin of
`R` (`CreateFileW(OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS |
FILE_FLAG_OPEN_REPARSE_POINT)`, share `FILE_SHARE_READ | FILE_SHARE_WRITE`,
omitting only `FILE_SHARE_DELETE`), then proof **from the handle** that it is not
a reparse point and that its `FileIdInfo` equals the identity recorded at L2.
A mismatch refuses before any create. This is the *proven run-root authority*
that every later step chains to.

**7.4A.2 Pinned-parent construction.** Let `build(D, P_D)` construct directory
`D`, whose pin `P_D` is held and whose own parentage was proven by its parent's
gate. For `D = RT` the parent is `R` and the gate is **membership** (an entry
named `pi_runtime` in the single enumeration of `R`'s pin whose file id equals
`P_RT`'s); for every other `D` the gate is **exact set** (below).

1. **Zero-byte file creation.** For every `file` child `f` of `D` in `I`:
   `CreateFileW(path(f), GENERIC_READ | GENERIC_WRITE | DELETE, share 0,
   CREATE_NEW, FILE_FLAG_OPEN_REPARSE_POINT)`; keep the handle `h_f`; record its
   identity from `h_f` itself. **Zero content bytes are written.** An occupied
   name — ordinary file, planted symlink, dangling or not — refuses
   (`ERROR_FILE_EXISTS`; W10 as corrected by FU16) and creates nothing at any
   link target.
2. **Child directory creation and pin.** For every `dir` child `d` of `D`:
   `CreateDirectoryW(path(d))`, then immediately pin it
   (`GENERIC_READ`, share `FILE_SHARE_READ` only, `OPEN_EXISTING`,
   `FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT`) and prove **from
   the handle**: a directory, `FILE_ATTRIBUTE_REPARSE_POINT` absent,
   `ReparseTag == 0`. Capture its identity. (Q5 measured this refusal pattern.)
3. **Parentage gate (pre-write).** Enumerate `P_D` **once**, from the handle
   (W8, W9). Require the entry set to equal **exactly**
   `{".", "..", every f name, every d name}` and each entry's `FileId` and volume
   serial to equal the identity of **its own handle** (`h_f` or `P_d`). The
   exact-set requirement also refuses a foreign name planted in `D` (W11).
   Failure → `RUNTIME_PROVISIONING_FAILED`; **no content byte has been written to
   any file of `D` or below**.
4. **Content.** Only after step 3 passes: for each `f`, write the bytes of
   §7.4B through `h_f` and nothing else, flush, compare the digest **read back
   through `h_f`** (seek 0) with the approved entry, then close `h_f`.
5. **Recurse.** For each `d`: `build(d, P_d)`; when it returns, release `P_d`.
   `P_D` is released by the caller of `build(D, …)` after `D` is complete.

`build(C, P_C)` is invoked from the construction of `RT` (created under `P_R`,
pinned, gated by membership in `P_R`'s enumeration, then given its own exact-set
gate `{".", "..", "pi-coding-agent"}` once `C` has been created and pinned
beneath it).

**7.4A.3 Why a pathname create beneath the pinned chain cannot escape `R`.**
Every pathname create in steps 1–2 resolves a path whose every existing
component is a directory that is **currently held**: `P_R` and each `P_D`
beneath it. A held directory pin (share `FILE_SHARE_READ`, no
`FILE_SHARE_DELETE`) cannot be renamed or removed (W2) and cannot be converted
in place to a junction (W3); while **any** descendant handle is open, **no
ancestor at any depth** — including the ancestors above `R` — can be renamed, and
a non-empty ancestor can be neither removed nor converted (W5, W6). So the
pathname cannot be re-pointed away from the pinned chain: R1's flaw was
releasing the control *between* the check and the later create, and R1-FU1 never
does. The new directory's **own** pin is acquired before anything is created
inside it, so the chain is continuous from `R` to the current directory.

**7.4A.4 The one pre-pin residual (R-WINDOW, FU15 class, accepted).** Between a
`CreateDirectoryW` and the acquisition of that directory's first
identity-bearing pin, a same-user actor can substitute an ordinary directory at
that name (W4). Stated exactly, as FU15 §37.3.6 states it: nothing proves the
pinned object is the one `CreateDirectoryW` created. What **is** proven: it is a
real directory, not a reparse point, an entry of the **pinned parent** by file
id (step 3 of the parent's `build`), and — by its own exact-set gate — holds
nothing but the children whose handles receive the bytes. Consequences: a
substituted directory is still an entry of a pinned directory beneath `R`, so
**no write can leave `R`**; **no content byte exists in that window** (no
content is ever written before the gate of the directory it goes into); a
substitute pre-populated with foreign names is refused by the exact-set gate;
names added after the gate are caught by the post-pin complete walk (§7.6).
Cleanup authority over a substituted directory is the **root-namespace**
authority of FU15 §37.3.2a, never a claim that AIDO created it.

**7.4A.5 Provisioning provenance and partial-failure handle lifecycle.**

- **Own provenance.** The provisioning mechanism may reuse or factor the
  established low-level Win32 *semantics* (the `CreateFileW` shapes above,
  handle-derived `FileIdInfo`, single-pass handle enumeration, handle
  disposition), but it has its **own non-transferable provisioning provenance**:
  provisioning pins and child handles are typed objects that only the
  provisioning routine can mint and consume, bound by a provisioning-only
  binding that is **distinct from** `bind_config_generator_authority` and
  `bind_extension_writer_authority`. It must not mint a config-issuance token, a
  config-generation interval, a retained authority or an extension-issuance
  authority, and must not be accepted by any function that consumes those. It is
  never returned, never placed in a record, never passed to a port, and never
  rendered in a `repr`. `win_config_authority.py` is **not modified** by this
  amendment: F5A-IMPL either imports only provenance-free helpers that module
  already exports, or carries its own thin layer; changing the frozen module
  needs a separate reviewer decision.
- **Handle ledger.** `state.runtime_provision` carries a ledger entered at the
  moment of acquisition for every **active directory pin** and every **zero-byte
  or in-progress child handle**. Each entry is a two-state machine
  `OPEN → CLOSED | CLOSE_FAILED`; `CloseHandle` is called **only** from `OPEN`,
  so no handle is closed twice, and `CLOSE_FAILED` is **never retried, forced,
  or re-derived from a name**.
- **Closed before L27.** The provisioning routine closes its ledger in a
  `finally` on **every** exit path (success; every refusal; every injected
  failure) before control leaves L3R, children before the directories that
  contain them, deepest first. L27 entry additionally closes any entry still
  `OPEN` (defence against abnormal control flow) in the same ledger, so the
  total is exactly once per handle, always before the frozen re-proof and
  `remove_disposable_tree`. The four final read-only pins (§7.6) are outside
  this ledger and keep their own unconditional L27-entry release (§7.8).
- **Construction-handle close failure is lifecycle-significant.** A close
  failure refuses L3R (`RUNTIME_PROVISIONING_FAILED`) *and* degrades the
  lifecycle evidence, because a leaked handle makes L27's removal fail by
  construction (W2, W6): `INDETERMINATE_LIFECYCLE`, as FU15 T-151 freezes for
  L9's pins. **It also makes the run's `live_references_released` fact
  `False`** (§7.8.1): a `CLOSE_FAILED` ledger entry is an OS handle that is
  *not proven closed*, and no later event turns that into `True`. It never
  causes a pathname-based cleanup of any kind.
- **No emergency cleanup, by pathname or by handle.** L3R removes nothing: not
  by pathname, and not by handle disposition either. The zero-byte children of a
  failed gate, the directories, and any foreign residue stay inside `R` — every
  one of them an entry of a pinned directory beneath `R` (§7.4A.3) — for L27's
  namespace teardown (FU15 §37.3.2a), which does not follow a reparse point out
  of `R` (Q6).

**7.4A.6 Bounds (computed from the committed inventory, asserted by test).**
Depth: 11 path components below `C`. Largest directory: 362 entries; no
directory has more than 360 file children or more than 80 sub-directories. With files closed before
recursion, the construction holds at most **462** handles at once under the
accounting above (the future test recomputes the exact peak from the committed
inventory and fails if the implementation's ledger ever exceeds it). Handles are
raw `CreateFileW` handles, not C-runtime descriptors. Only the current
depth-first ancestry and the pending sibling pins are held — never all 1 436
directories.

### 7.4B Source-byte ordering (R1-FU1; corrects R1 step 6)

**What was wrong.** R1 streamed source bytes into the destination while hashing
them, and compared size and SHA-256 with the approved inventory only
afterwards. After the source PI-PC1 observation, a same-user substitution of a
source ancestor can make one **later** source pathname open reach unrelated host
content. The digest mismatch would refuse the launch, but the unapproved bytes
would already be persisted inside `R` — and stranded there if L27 then failed.

**INV-F5A-S (verify-before-persist).**

> **No byte read from the external source is written to ANY destination file,
> temporary file, diagnostic, artifact or log until that exact file's complete,
> stable size and SHA-256 have been proven equal to its approved inventory
> entry.** Unverified source bytes are never spilled to disk.

**Specified shape (A).** For each `file` entry `e` of `I` (= the approved
inventory): read the file in full through one no-follow, regular-file-only
byte-returning leaf, bounded by `e.size + 1` bytes (so growth is detected and
memory is bounded by the approved size); require `len(data) == e.size` and
`sha256(data) == e.sha256`; **only then** write `data` through `h_f` (§7.4A.2
step 4). The bytes that are hashed are the bytes that are written — the same
buffer — so "stability" between hashing and writing is not a separate question.
Mismatch, short read, over-long read, non-regular file or reparse source →
`RUNTIME_PROVISIONING_FAILED` with that file's `h_f` left zero-byte.

**Permitted alternative (B).** Keep **one** no-follow source handle open (share
mode that prevents content replacement), hash it completely and prove
size/stability/digest, rewind **the same still-held handle**, and copy from it.
Any shape is acceptable if it satisfies INV-F5A-S; none that writes first and
verifies second is.

**Consequences, stated exactly.** A source race that redirects an open to
unrelated content: (i) the content exists only in bounded transient memory (at
most the approved size of that entry; the largest approved file is
11 694 592 bytes); (ii) fails the digest; (iii) writes **zero** bytes of that
content anywhere under `R`; (iv) influences no runtime or authority decision —
the only outputs are the refusal and its closed code; (v) leaves no
secret-bearing residue if L27 later fails, because nothing but approved bytes
(and zero-byte files) is ever written. The refusal diagnostic carries the
approved payload-relative path of the entry and a closed reason, and **never**
the observed bytes, a prefix, or a digest or size of the foreign content.

**R-SRC-MEM (stated, not closed).** The foreign bytes of a failed read exist in
the AIDO process's memory until released. AIDO does not persist, log, transmit
or interpret them and does **not** claim memory scrubbing; operating-system
paging, crash dumps and debuggers are outside this phase's observation
boundary. This is a different thing from a write by AIDO into `R`, which INV-F5A-S
forbids.

### 7.5 What R1 does not need

Because no target is derived, R1 needs none of: an occupant, an occupant handle,
an occupant lifecycle, an undeletable object, a write-capable pin, a gap-free
`ReOpenFile` successor, retention of anything across L27, or any proof of who
created an object at a quarantine name.

### 7.6 Final pins and post-pin validation

**Pin set (read-only).** After step 6, AIDO opens, for each of
`C\package.json`, `C\dist\cli.js`, `C\dist\main.js`, `C\dist\config.js`:

```text
CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING,
            FILE_FLAG_OPEN_REPARSE_POINT)            -- no write, no delete access
```

and refuses unless the opened object is a regular file, carries no reparse
attribute/tag, and its file id equals the id recorded from its creating handle
(step 6). This is exactly the Q4 control shape that was measured compatible with
the genuine PI-PC1 walk. The **creator→pin interval is pre-authority**: it need
not be gap-free, because anything substituted in it is either refused here (id,
reparse, kind) or by the content walk below.

**What the pins are for, stated exactly.** They are *stability* pins, not
safety barriers:

- share READ without `FILE_SHARE_WRITE`/`FILE_SHARE_DELETE` refuses other
  writers and deleters of the four pinned files (delete / rename / replace /
  overwrite by another handle) while held — to be re-measured for the read-only
  shape (P-R1-1, §14);
- open handles beneath them block renames of every ancestor directory — measured
  for write-capable pins (Q3 sub-premise), to be re-measured for the read-only
  shape (P-R1-2);
- they keep the L3R proof, the L14 re-proof and Node's module resolution
  referring to the same four objects and the same ancestor chain.

**They do not prevent `FILE_WRITE_ATTRIBUTES` reparse conversion** of the pinned
files (Q2/Q3 measured that such opens are admitted regardless of share mode).
That case is decided in §9.2. **INV-F5A-R1 does not depend on the pins**: it
rests on the L14 topology re-proof (§7.7) plus the inherited post-proof boundary
(§9).

**Post-pin validation** (read-only, in `pi_identity` and the topology checker;
no write):

1. complete PI-PC1 walk of `C` → fingerprint **equal** to `X`'s;
2. `observe_exposure_absence(C, X.resolution_exposures)` →
   `EXPOSURES_PROVEN_ABSENT` (§8.8);
3. topology rules T-NM, T-CANON, T-PLAIN, T-BUN, T-RT (§7.2) on the now-complete
   chain;
4. for each pin, the no-follow identity of its path equals the pinned handle's
   identity;
5. `I_c` = `C`'s identity from a no-follow open.

### 7.7 L14 and L21A under RPR

- **L14** gains one executor precondition, run immediately before
  `build_supervisor` and the frozen re-proof:
  `type(state.runtime_provision)` is exact; its workspace nonce equals the
  claimed workspace's; its four pins report held; `state.pi_identity is
  state.runtime_provision.launch_identity`; the LDT entry for `X` exists; and the
  **topology re-proof** — T-NM, T-CANON, T-PLAIN, T-BUN, T-RT and pin-identity
  equality, all re-observed now. Then the **unchanged**
  `reprove_pi_identity_for_launch(L)` (walk of `C` = `X`, exposures from `C`,
  `I_c`, `I_n`). Any failure → `RUNTIME_LAUNCH_FAILED`, no launch (existing
  code). **This precondition plus the frozen re-proof is the instant at which
  INV-F5A-R1 is proven.** The child environment is built at L12 from the frozen
  allowlist (T-4), which supplies clause (a); clause (b) follows from T-BUN and
  `I_n` (Node, not Bun).
- **L21A** runs the **unchanged** `reobserve_pi_profile_after_runtime(L)` at its
  frozen position, pins still held. `PROVEN_UNCHANGED` now means the run-private
  copy was identical at L14 and at L21A and the direct child had exited — no
  other project can modify a run-private copy (R-SHARED no longer reaches it).
- `build_pi_argv` is unchanged and now yields `C\dist\cli.js`.

### 7.8 Release (L27 entry)

At L27 entry the four pins are released, each exactly once, by handle, never by
name, no retry, no force — **unconditionally**. Then the frozen L27 re-proof and
`remove_disposable_tree`, which removes the copy and anything planted in `R`
without following a reparse point (Q6, F5-B's existing proof). A failed release
(`CloseHandle` failure) leaves the handle open, so removal fails by construction
→ existing L27 failure → `INDETERMINATE_LIFECYCLE` — **and the run's
`live_references_released` fact is `False`** (§7.8.1). No new lifecycle
vocabulary and no conditional retention: R0's retention existed only to protect
`Q`, and nothing in R1 protects a target. (R1 and R1-FU1 said
`live_references_released` was *unchanged*. That was wrong for a design in which a
close failure can leave a live OS handle; §7.8.1 corrects it.)

#### 7.8.1 `live_references_released` is a derived fact (R1-FU2)

*Today.* `run_executor.py` returns `Cfg1RunOutcome(live_references_released=True)`
unconditionally, and the L30 admission decision in `stage_runner.py`
(`_run_scoped_registries_empty`, Sec. 19.1 item 4) requires
`outcome.live_references_released is True`. Under this design that constant would
let a run that left an RPR handle open report that every live reference was
released.

*Corrected rule, for F5A-IMPL.* The executor's unconditional `True` is replaced
by a mechanically derived state fact, computed once at the end of closure:

```text
live_references_released == True
  IFF  every CFG1 executor-owned live reference / handle for the run is PROVEN
       released, including
         - every RPR construction directory pin   (R, RT, C and each descendant)
         - every RPR construction child handle
         - every final RPR read-only pin          (the four of §7.6)
       and the executor-owned references it already tracks (it must not weaken
       them; one with no recorded release fact is reported to review, not
       assumed True)
  where PROVEN means: the release record (a ledger entry for construction
       handles; the equivalent record for each final pin) reads CLOSED because
       CloseHandle returned success for that handle - or the resource was never
       opened. A final pin's record is part of the same latch.
```

Provisioning never attempted (the run refused before L3R) is vacuously `True`.

- **Any** `CloseHandle` / release failure on any of those resources sets the
  fact `False` for the run, **permanently** for that run (a latch). It remains
  lifecycle-significant (`INDETERMINATE_LIFECYCLE` follows from the blocked
  removal where the failure blocks it) and **causes stage closure to fail
  closed under the existing L30 check** — no new halt code, no new record key.
- It is **never repaired to `True`**: not because L27's namespace removal
  happened to succeed or fail, not because the process-level registries are
  empty, not because Python lost the object reference (a handle whose ledger
  entry is not `CLOSED` stays unproven however the Python object is
  garbage-collected or its handle value reused), and not because the process
  later exits. AIDO makes no claim that process exit closes a handle.
- `lifecycle_all_closed` / `workspace_removed_verified` (L27's re-proof and
  removal) are separate facts; both can be `False`, and neither implies the other.
- **No** safety-leak retention registry, **no** retry cleanup, **no** force-close,
  and **no later run may adopt the leaked handle or root** (the mint registry
  and single-use claim are unchanged).
- Scope: the field already exists in `Cfg1RunOutcome`; this changes only how the
  executor computes it. It adds no record key and does not alter any v1/v2
  serialized contract.

### 7.9 Cost

Per ordinal, added: one source walk (123 MB hashed), one copy, one post-pin walk
(123 MB), one topology re-proof at L14 (a few dozen no-follow inspections). The
copy is, per file, **read in full into memory and hashed (123 MB read + hashed
once more) before it is written** (§7.4B, INV-F5A-S), then written once (123 MB
written) through the file's own handle and read back once through that handle for
the digest compare (123 MB). It is **not** a streaming copy-while-hashing: the
price of never persisting unverified bytes is that each file is held in memory
once — **peak transient memory = the largest approved file, 11 694 592 bytes**
(plus ordinary interpreter overhead), not 123 MB. Creates: 15 046 zero-byte file
creates, plus 1 438 directory creates and pins (the 1 436 inventory directories,
`C` and `RT`), with all 16 482 + 2 parentage entries proven by 1 439 single-pass
handle enumerations (one per constructed directory, plus `R`'s). The
destination construction holds at most the handle peak of §7.4A.6 (462 under the
stated accounting). Peak disk ≈ 123 MB per live run in the temp scratch area,
removed at L27. Within PE-1 §4.4 bounds; R-COST is widened accordingly. An
on-access scanner holding a new file may make a walk refuse — availability only.

---

## 8. Mandatory static analysis

### 8.1 Node/Pi do not require the package root to be beneath `node_modules`

- **Node.** ESM/CJS resolution has no rule requiring a module's package to sit
  under a `node_modules` directory. A relative specifier resolves against the
  importing module's URL; a bare specifier walks upward from the importing
  module's directory, trying `<dir>\node_modules\<name>` at each ancestor that is
  not itself named `node_modules`; a self-reference uses the nearest
  `package.json` scope. The main entry is an absolute argv path. `type: "module"`
  is read from the nearest `package.json` scope, which for every file under `C`
  is inside `C`.
- **Pi.** Every `getPackageDir()` consumer reached in CFG1's RPC launch (R0 §5.3
  rows 1, 3, 5, 7: `package.json`, themes, docs paths, cleanup) uses
  `getPackageDir()` only as a base for joins **inside** the package, plus the
  upward cleanup walk of §2.2. The location-sensitive helpers
  `detectInstallMethod` and `getInferredNpmInstall` (`config.js:44-83`) feed only
  self-update / version-check text, which CFG1 excludes (`--offline`,
  `PI_SKIP_VERSION_CHECK`); under R1 they would classify the install as
  "unknown", affecting only advisory update text. Package discovery
  (`package-manager.js`) uses `cwd\.pi` and the agent dir, never the package dir.
- **One location-sensitive read was found** in the approved extension loader
  (`dist/core/extensions/loader.js:37-84`, re-verified R1):
  `packagesRoot = path.resolve(__dirname, "../../../../")` — the **parent of the
  package root** — is probed with `existsSync` for monorepo workspace entries
  (`agent/dist/index.js`, `tui/dist/index.js`, `ai/dist/compat.js`,
  `ai/dist/oauth.js`, `ai/dist/providers/all.js`); a present file becomes a jiti
  alias target, otherwise `import.meta.resolve(<package>)` from inside `C` is
  used. Under the global topology `packagesRoot` is the **shared** npm scope
  directory `<npm-prefix>\node_modules\@earendil-works`; under R1 it is the
  **AIDO-created `RT`**, whose child set T-RT proves to be exactly
  `{pi-coding-agent}`, so all five probes miss and every alias resolves inside
  `C`. The aliases are consumed only by modules the loaded extension imports;
  CFG1's pinned extension imports `typebox` at runtime (aliased via
  `require.resolve` from inside `C` to the contained `C\node_modules\typebox`)
  and `@earendil-works/pi-coding-agent` **type-only** (erased). R1 therefore
  *narrows* this path from a shared foreign directory to an AIDO-owned one.

**Conclusion:** no rule of Node or of the approved Pi code requires a
`node_modules` parent for CFG1's launch.

### 8.2 Dependency resolution from `C`

**Generic argument (frozen contracts, location-independent).** Node's bare
resolution is a first-match upward walk. The part of that walk **inside `C`** is
identical in both topologies (same inventory, same relative structure); only the
part **above `C`** changes. Therefore:

1. every resolution that terminates inside `C` is unchanged by the move;
2. every **declared** dependency of every package root is, by the frozen
   `compute_resolution_exposures` (`pi_manifest.py`), either **contained** (an
   inventory directory with a `package.json` on an in-payload candidate path,
   which by construction precedes any above-`C` path) or one of the profile's 31
   `resolution_exposures`;
3. every exposure is proven **absent** at every non-`node_modules` ancestor of
   `C` by `observe_exposure_absence` at L3R and L14 (§8.8), so it is "not found"
   in both topologies;
4. everything else — undeclared or dynamic upward resolution — is **R-EXT-1**
   in both topologies (PE-1 §6.6: undeclared and dynamic resolution are not
   brought into HPP-1).

**Static scan (approved bytes, R1).** A regex scan of `import … from`,
`import()`, `import "…"`, `require()`, `require.resolve()` and
`import.meta.resolve()` string-literal specifiers over the **4 732 approved JS
files whose installed bytes equal their approved digests**, classifying each bare
name by an inventory-only model of Node's walk (in-payload candidates, then
self-reference via the scope's `name` + `exports`), found:

- **no `@earendil-works/*` specifier escapes `C`.** The root package's own name
  self-references (its `package.json` has `exports`); the nested
  `pi-agent-core`, `pi-ai`, `pi-tui`, `pi-codemode`, `pi-mcp`, `chord`,
  `pi-telemetry` are contained. The committed manifest bundle shows no nested
  **runtime** package declaring `@earendil-works/pi-coding-agent` (only
  `examples/plugins/pi-example-plugin`, which is not a package root and is never
  loaded: `--no-extensions`);
- names that escape `C` are only: **recorded exposures** (`zod`,
  `@modelcontextprotocol/sdk`, `@smithy/hash-node`, `bufferutil`,
  `utf-8-validate`, `kerberos`); **test/dev files** of dependencies (`mocha`,
  `nock`, `sinon`, `tape`, `express`, `cors`, `tmp`, `ncp`, `mv`, `multiparty`,
  `pack-n-play`, `tap`, `rimraf`, `mkdirp`, `benchmark`, `@stablelib/benchmark`,
  `deep-diff`, `ieee754`, `@eslint/js`, `globals`, `typescript-eslint`);
  **optional or try-guarded** loads (`supports-color` in `debug`,
  `@aws-sdk/signature-v4-crt`, `@aws-sdk/signature-v4a`, `pnpapi` in
  `esbuild`); and **string-literal false positives** in comments/docs (`apiKey`,
  `after`, `b`, `fake`, `foo.com`, `properties`, `queued`, `some-module`). All are
  R-EXT-1 in both topologies; none is a required runtime dependency that only an
  above-`C` directory could satisfy.
- **126 approved JS files could not be re-scanned** (`U126`, §1.2; installed
  bytes now differ). For their **module resolution** the bound is the frozen
  PE-4A §6.3 statement, made over all approved bytes: *"A literal-specifier scan
  of all code reachable from `dist/cli.js` (2 106 files) finds that the only
  specifiers that resolve **outside** the payload are three *optional*
  `require()` calls — `bufferutil`, `utf-8-validate` … and `supports-color`"*.
  Every reachable member of `U126` is inside that 2 106; so for it, too, every
  literal specifier resolves **inside** the payload (and therefore identically
  from `C`) except those three optional, absent-tolerated requires. The
  non-literal loaders are the five sites of PE-4A §7.5, none of which is in
  `U126` (§8.10). The unreachable members of `U126` are not loaded at all
  (§8.10.4 class A: U-BUNDLE, U-OTHER, U-TP).

**Classification of what remains.** After the frozen §6.3 result, the residual
module-resolution risk is limited to (a) the three optional requires (guarded;
absence is the already-observed state, PE-4A F-13) and (b) non-literal and
dynamic resolution, which is PE-4A's own HPP-1 residual (§12, "undeclared
upward resolution" / "constructed-path loads"). Either can at worst make Pi fail
to resolve or start — a **fail-closed E5 availability effect**, not a
semantic/profile premise: profile identity, containment and exposures are
location-independent by construction (PE-1 §4.5/§4.7/§6.6). It does not reopen
PE-4. Under R1 it also cannot create a delete target, because the target
derivation does not depend on module resolution of any bare name (§8.4).
**This is R-E5-COMPAT's whole remaining scope** (§9); it is no longer used to
absorb any other relocation effect of the 126 files — those are classified, file
by file, in §8.10. **No runtime success is claimed without E5.**

### 8.3 `getPackageDir()` resolves to `C`

- `PI_PACKAGE_DIR` is absent: the positive allowlist never forwards it (T-4,
  re-checked by T-F5A-19).
- `isBunBinary` is false: `config.js:18` tests `import.meta.url` for three
  substrings; T-BUN refuses any `C` path containing them (case-insensitively),
  and `node.exe` is the L1-proven `I_n` (Node, not Bun).
- `findNodePackageDir(C\dist)`: `C\dist\package.json` is absent (approved
  inventory has no `dist/package.json`), so the walk continues to `C`;
  `C\package.json` is present (inventory file, proven by content, pinned);
  `basename(C) = "pi-coding-agent"`, not `"dist"` → returns **`C`**.
- A post-proof `C\dist\package.json` plant still yields `C`
  (`config.js:303-308`: a `dist` directory whose parent holds `package.json`
  yields the parent). The approved payload has no `src`, so the themes probe is
  unchanged.

### 8.4 `getQuarantineRoot(C)` cannot find a `node_modules` ancestor

`getQuarantineRoot` is **purely lexical** (`resolve` + `basename` + `dirname`;
no filesystem access). Its input is `getPackageDir()`, which with (a) and (b)
withheld is `findNodePackageDir(__dirname)`. That function returns either an
ancestor-or-self of `__dirname` or `__dirname` itself; in every case the returned
path's component chain is a prefix of `__dirname`'s. Hence:

> the target is `undefined` **iff** no component of `dirname(fileURLToPath(config.js's import.meta.url))`
> is named `node_modules` (case-insensitively) — **whatever** `findNodePackageDir`
> finds on disk.

This is stronger than "package root == C": even an absent or substituted
`C\package.json` cannot produce a target, because every candidate lies on
`__dirname`'s own chain. `config.js`'s URL is produced by Node from AIDO's argv
string `C\dist\cli.js` through relative resolution (`./main.js`, `./config.js`)
and the ESM loader's realpath. With every component plain (T-PLAIN), realpath
does not rewrite the string, so the URL's chain is exactly the chain AIDO checked
under T-NM — **from the volume root, not merely `RT` and `R`**. A SUBST drive
cannot defeat this either: AIDO's realpath of `R` resolves the substitution, so a
`node_modules` component behind it appears in AIDO's string and refuses, while
Node keeps the drive letter, which can only remove components.

### 8.5 What must be pinned, and why it is enough

From §8.4, the derivation's only filesystem-sensitive inputs are the objects
whose realpath decides `config.js`'s URL: the three derivation-chain modules and
their ancestor directories. `C\package.json` decides `getPackageDir() == C`
(asset paths, `APP_NAME`; F5-B) though not the target. R1 therefore pins exactly
those four files, read-only, share READ (§7.6), which:

- refuses replacement of the four objects by delete+recreate or rename+plant
  (P-R1-1);
- blocks renaming of every ancestor (P-R1-2; measured for write pins in Q3),
  which removes the "rename an ancestor and plant a junction that aliases `C`
  under a `node_modules` path" route while held;
- is compatible with the genuine PI-PC1 walk (Q4 control; generalized as
  P-R1-3).

No directory pin is needed: `I_c` is re-proved by the frozen L14 re-proof, and
ancestor stability follows from the file pins beneath. The write-capable
derivation pins of R0 are removed (§10).

### 8.6 Post-validation file→reparse conversion: inherited

**Decision: inherited within R-SLIVER/R-ABA; not a new F5-A blocker.**

- **What it can do.** A same-user actor opening a pinned file with
  `FILE_WRITE_ATTRIBUTES` (admitted, Q2/Q3) can turn `cli.js`, `main.js` or
  `config.js` into a symlink to a file of its choice. Node then binds that
  module to the link target's realpath — **a different code object at a
  different URL**. If the target lies under some `X\node_modules\…`, the code that
  runs computes `X\node_modules\.pi-native-quarantine`.
- **Why that is the inherited capability.** (1) It requires write access to an
  object inside `R` after the last AIDO proof — exactly the actor and window of
  R-SLIVER/R-ABA; under FU15 §37.1 the same user who can set a reparse point on a
  file in `R` can write the contents of any of the ~16 000 **unpinned** files in
  `C`. (2) Unpinned modules run before `main.js:460`: `cli.js` calls `setupCli()`
  from the unpinned `dist/cli/setup.js` before `main()`, and every static import
  of `main.js` is evaluated before its body. Writing `rmSync(<anything>)` into
  any of them is strictly more powerful than a reparse conversion, which can only
  select **which** code object (genuine or not) is loaded. (3) The conversion
  derives no AIDO authority: AIDO computes nothing from Pi's target and deletes
  nothing on Pi's behalf; the delete is performed by code whose identity the
  actor selected after the proof. "Genuine bytes at a foreign URL" is a subset of
  "arbitrary code", which the frozen boundary already concedes.
- **Why the bar is met and not merely asserted.** The conversion alters only
  what code/object Node executes after the last proof; it confers no destructive
  capability that arbitrary post-L14 JS substitution does not already confer to
  the same actor. Before L14 it is **caught**: T-PLAIN in the L14 precondition
  refuses any reparse component or reparse-attributed derivation file.
- **What is not claimed.** R1 does not claim the read-only pins prevent the
  conversion, does not claim resistance to arbitrary same-user post-proof
  substitution, and does not claim Node's `rmSync` behaviour on any object.

### 8.7 Provisioning, launch identity, L14 and L21A under R1

- **Same profile by content.** PE-1 §4.5:
  `payload_fingerprint = SHA-256(b"aido.pi-payload.v1\x00" || canonical_json_bytes(inventory))`
  over `{kind, path(relative), sha256, size}` entries; absolute location, volume,
  file ids, timestamps and attributes are excluded. PE-1 §4.7: `profile_id`
  hashes `{payload_contract, payload_fingerprint, resolution_exposures}`, and the
  exposures are computed from committed inventory + manifest bytes. A
  byte-identical tree at `C` therefore yields fingerprint `66cf8a81…` and profile
  `56651d0b…` — the **same** approved profile. R1 uses **equality** with L1's
  matched profile (the L14 rule), never fresh membership.
- **Launch identity** `L` = node fields from `S`; root `C`; `pi_cli_js =
  C\dist\cli.js`; `I_c`; `X`. No new slot.
- **L14** binds to the object provisioned at L3R (`I_c`), to `X` by equality and
  to `I_n` from L1, with the R1 precondition (§7.7) proving INV-F5A-R1 at the same
  instant.
- **L21A** is unchanged in code and meaning.

### 8.8 Exposure proof from `C`

`observe_exposure_absence(C, X.resolution_exposures)` (`pi_manifest.py`) checks
`<A>\node_modules\<exposure>` for **every** proper lexical ancestor `A` of `C`
whose basename is not `node_modules`. Under R1 no ancestor is named
`node_modules` (T-NM), so **every** ancestor is checked: `RT`, `R`, the scratch
boundary, each temp ancestor, up to the volume root. Under the global topology
the walk covered `<npm-prefix>\node_modules\@earendil-works`, `<npm-prefix>` and
its ancestors. The **new** upward directories are `RT\node_modules` and
`R\node_modules` (AIDO-owned; T-RT proves them absent entirely, a stronger check
than exposure absence) and the temp-scratch ancestry (user-writable, the same
R-EXT-1 class as the `<npm-prefix>` ancestry it replaces). The populated shared
directory `<npm-prefix>\node_modules` leaves the upward path entirely. No
unreviewed **class** of external dependency path is introduced; the concrete
upward set changes and is fully covered by the existing exposure observer plus
T-RT.

### 8.9 PE-4A F-4 — model-visible documentation paths

`getReadmePath`/`getDocsPath`/`getExamplesPath` become `C\README.md`, `C\docs`,
`C\examples` under the run root. They are:

- **arm-independent**: both arms draw `R` by the identical frozen `mkdtemp`
  procedure and the suffix `\pi_runtime\pi-coding-agent` is a constant;
- **secret-free**: `R`'s full path, including its `mkdtemp` name, is already
  model-visible through the frozen `cwd` (the workspace repository is built
  inside `R`), so the three paths disclose nothing the frozen design does not
  already disclose; the only added text is the constant suffix; and they no
  longer embed the operator's npm-prefix path. (If review finds the run-root
  name used as secret material anywhere, that would already be a defect of the
  frozen `cwd` exposure, not one introduced here.)

They vary per run exactly as `cwd` does. Classification B unchanged; not a CC1
change. Reviewer acknowledgement required (**D-F5A-4**).

### 8.10 The 126 unavailable approved files — classification and read-relocation closure (R1-FU2)

> **Result of §8.10.1–§8.10.7 as submitted: `U126_READ_UNPROVEN` was NOT empty
> (57 files), so R1-FU2 was marked HOLD (§8.10.6).** 69 of the 126 files are
> excluded by frozen evidence; 57 were not, and are listed explicitly in §8.10.5.
> **§8.10.8 supersedes that result:** the approved bytes of exactly those 57 were
> recovered (57/57 exact against the committed inventory) and reviewed, and the
> set is now **empty**. §8.10.5 and §8.10.6 are kept as the record of what the
> frozen evidence alone could and could not establish.

**What R1-FU1 got wrong.** It defined "side effect" so that a filesystem *read*
was excluded, then argued from the absence of a PE-4A capability row that a
reachable unavailable file was harmless. That criterion is withdrawn. A
location-sensitive read can matter with no mutation at all:

```text
module / package location -> derived filesystem path -> host state is read
   -> the value influences a prompt, a provider/model choice, a request
      payload, configuration, an authority decision, backend-visible data
      or a sensitive diagnostic
```

PE-4A's frozen capability scan (Appendix B) covers spawn / network / fs-write /
`process.env` / home-directory lookup / non-literal import / eval / wasm /
worker / `createRequire` / `jiti`. It is **not** a general filesystem-read scan
and not an `import.meta.url` / `__dirname` / `process.execPath` scan. This
document therefore no longer lets the absence of a capability row stand in for
a read analysis.

**8.10.1 The criterion (corrected; stated before the result).** A *location-
sensitive read* is a read whose target, or whose result, depends on where the
package, the module or the process sits (a path derived from the module URL,
the package directory, `process.execPath` or `process.argv[1]`, an upward
traversal from any of them, or an absolute path text that reaches a consumer).
A reachable `U126` file is acceptable **only** if frozen evidence establishes
one of:

- **A.** it is not loaded;
- **B.** it is loaded, but the invocation that could perform a read is closed
  by a location-independent frozen gate;
- **C.** it has no filesystem-read / path-derivation route capable of consuming
  host state;
- **D.** every such read/path route is already individually bounded to an
  AIDO-owned, in-payload, config-directory or `cwd` resource, and its
  downstream semantic use is already frozen;
- **E.** the read can only cause fail-closed availability, and its bytes,
  boolean or value cannot influence a prompt, a model/provider choice, a
  backend request, an AIDO authority decision or a sensitive diagnostic.

"A read is not a side effect" is **not** a ground. The set to be derived is

```text
U126_READ_UNPROVEN = { f in U126 :  f is reachable
                                   AND f is not closed by a location-independent
                                       frozen gate (A or B)
                                   AND frozen evidence does not establish C, D or E }
```

"Frozen evidence" here means PE-4A and the other committed frozen evidence.
Installed 1.1.0 bytes are not evidence and were not used. A file name is not
evidence either: no class below is assigned from what a file is *called* or
what directory it sits in.

**8.10.2 How the reachability groups were derived and verified.** PE-4A
Appendix B gives the partition rules and §7.2 freezes the SHA-256 of each
group's sorted path list. The partition was re-implemented from the committed
inventory and manifest bundle and its first-party JavaScript groups recomputed.
After excluding the 17 PI-SC1 files (PE-4A §7: the non-seam groups), all four
reproduce the frozen digests exactly:

| Group | files | recomputed digest equals frozen §7.2 digest |
|---|---:|---|
| FP-I | 54 | `a2dfa5ac…` ✓ |
| FP-E | 359 | `cbc9f3c7…` ✓ |
| FP-L | 50 | `2de76f29…` ✓ |
| FP-U | 152 | `eac672bb…` ✓ |

The edges *out of* the unavailable files could not be read from approved bytes,
so they were supplied as a hypothesis; the hypothesis is accepted **only**
because it makes all four frozen digests reproduce. The third-party groups did
not reproduce, so the four third-party members of `U126` rest on PE-4A Appendix
A. The reproduction needs the 1.1.0 copies for those edges and is therefore a
one-time authoring verification, not a repo-local test. What it supports is
*group membership* (FP-U vs FP-I/FP-E/FP-L vs seam), which is what A and the
group column of §8.10.5 use; it supports **nothing** about what any file reads.

**8.10.3 What the frozen evidence can and cannot establish.**

| Element | Frozen evidence available | Consequence |
|---|---|---|
| **A** | PE-4A §7.1 (partition total and disjoint); §7.2 FP-U / TP-U membership (digest-verified, §8.10.2); Appendix A (`@babel/runtime`: e/l/u = 0/0/123); §7.5 (the only five non-literal import sites, each a fixed-specifier switch gated by a flow AIDO does not run); §7.3 (the only two reachable first-party `worker` users, `image-resize.js` and `host.js`, both gated) | establishes A for the FP-U and TP-U members |
| **B** | PE-4A §7.3 gate rows (NOT LOADED / NOT INVOKED, each a predicate on argv, environment, mode or `model.api`, none on location); §8.5 and N-06 for the `--no-skills` lookup surface | establishes B for exactly the files those rows and that surface name |
| **C** | **None for any first-party file.** §7.2's FP-E statement ("the only module-load file read is `config.js`") speaks of *module evaluation*, not of later invocation. §12 lists real-home lookups and constructed-path loads as HPP-1 residuals `NOT_IDENTIFIED_BY_PROFILE` — a statement that nothing identifies them, not that they are absent. §8.1 says a *region* inspection "is not a whole-file audit and is not claimed to be" | cannot place any file outside the subset |
| **D** | Only *partial* file-specific statements exist (listed in 8.10.5): §7.6 for `settings-manager.js` / `resource-loader.js`, §7.2's D5 row for the built-in theme JSON data, F-4 for the docs-path *text* in `system-prompt.js`. Each names a route; none enumerates the file's routes | a partial statement bounds the route it names and says nothing about unnamed routes, so it cannot place the file outside the subset |
| **E** | None | — |

**The `config.js` getters (a tool for the future review, not an exclusion).**
`dist/config.js` is available and its bytes equal the approved digest
(`b53418ca…`). Its package-location-derived exports are: `getPackageDir`,
`getThemesDir`, `getExportTemplateDir`, `getPackageJsonPath`, `getReadmePath`,
`getDocsPath`, `getExamplesPath`, `getChangelogPath`, `getInteractiveAssetsDir`,
`getBundledInteractiveAssetPath`, `getQuickJSWasmPath`, `detectInstallChange`
and the advisory `detectInstallMethod`/`getSelfUpdate*`. Every one returns a path
inside `getPackageDir()` (= `C`, §8.3) or reads `package.json`; none writes. A
read through one of them targets an in-payload resource whose bytes are
inventory-identical at `C`, so its **result** is not relocation-sensitive; when
the unproven files' bytes are reviewed (8.10.6), such a route is classed D by
construction and only its downstream use needs a frozen statement. **Routes the
getters do not cover** — a direct `import.meta.url` / `import.meta.resolve` /
`new URL(…, import.meta.url)` / `process.execPath` / `process.argv[1]`
derivation, or an upward traversal from any of them — are exactly the
relocation-sensitive ones and each must be individually bounded. This is a
statement about what to look for. It excludes no file now, because without the
bytes it is unknown which route type any file uses.

**8.10.4 Excluded by frozen evidence: 69 files.**

*A — not loaded (54).*

| Class | n | Frozen evidence |
|---|---:|---|
| **U-BUNDLE** — every path under `dist/bundle/` | 44 | §7.2 FP-U row (`dist/bundle/**`, "75 JS files"; the inventory has exactly 75); §7.5 final paragraph (`bin.pi → dist/bundle/cli.js`; "AIDO launches none of them"); §6.2 row 2 and **F-7**; argv launches `C\dist\cli.js` (§7.4 step 9). PE-4A makes no claim about the bundle's behavior and none is needed: it is not loaded |
| **U-OTHER** — FP-U, no literal edge from `dist/cli.js`: `dist/utils/image-resize-worker.js`, `pi-codemode/dist/runtime/worker.js`, `pi-ai/dist/api/bedrock-converse-stream.js`, `pi-ai/dist/auth/oauth/{anthropic,openai-chatgpt,openai-codex}.js` | 6 | §7.2 FP-U row; §7.5 rows 2 and 3 (the OAuth flow modules and the Bedrock implementation are reached only by the gated non-literal loaders — "OAuth login/refresh only", "only for `api: bedrock-converse-stream`"); the two worker entries are reached only by `new Worker(URL)`, whose only first-party reachable users are the gated `image-resize.js` and `host.js` (§7.3 rows) |
| **U-TP** — `@babel/runtime/helpers/{interopRequireWildcard,toPrimitive}.js` and their `esm/` twins | 4 | PE-4A Appendix A: `@babel/runtime` 123 JS, e/l/u = 0/0/123; `helpers/esm` 122 JS, 0/0/122 |

*B — loaded, invocation closed by a location-independent frozen gate (15).*

| File | Capabilities (frozen) | Gate → status (frozen, PE-4A §7.3 verbatim) |
|---|---|---|
| `dist/core/mcp-servers.js` | net_http | built-in extension; excluded by `--no-extensions` → NOT LOADED |
| `dist/extensions/mcp/oauth.js` | net_http, fs_write | same → NOT LOADED |
| `dist/modes/interactive/interactive-mode.js` | child_process, net_http, fs_write | InteractiveMode only (`appMode === "interactive"`; AIDO's `--mode rpc`) → NOT INVOKED |
| `dist/package-manager-cli.js` | net_http, fs_write | `handlePackageCommand`/`handleConfigCommand`/`mcp` subcommands only (`main.js:469-488`) → NOT INVOKED. The startup call `cleanupManagedInstall()` is separately dispositioned in 8.10.7 |
| `dist/utils/clipboard.js` | fs_write | image/clipboard/browser helpers reached from tools or interactive mode → NOT INVOKED |
| `dist/utils/image-resize.js` | worker | same → NOT INVOKED |
| `pi-agent-core/dist/proxy.js` | net_http | `streamProxy` client; `sdk.js` wires `streamFn` to `ModelRuntime` → NOT INVOKED |
| `pi-ai/dist/api/openai-codex-responses.js` | net_http | selected only by another `model.api` value → NOT INVOKED |
| `pi-codemode/dist/runtime/host.js` | wasm_native, worker | backing library of the MCP/codemode built-in extensions → NOT LOADED |
| `pi-codemode/dist/runtime/prelude-source.js` | net_http | same → NOT LOADED |
| `pi-mcp/dist/oauth/discovery.js` | net_http | same → NOT LOADED |
| `pi-mcp/dist/transports/streamable-http.js` | net_http | same → NOT LOADED |
| `pi-tui/dist/terminal-image.js` | child_process | TUI library; interactive components, clipboard and terminal-image helpers only → NOT INVOKED |
| `pi-tui/dist/terminal.js` | fs_write | same → NOT INVOKED |
| `dist/core/skills.js` | — | argv `--no-skills` (N-06); §8.5 "new filesystem/config lookup surfaces … `~/.agents/skills` (skills disabled by `--no-skills`)". The skill-discovery reads are the lookup surface that row names and closes; `skills.js` is a §9.2 `[FP-E]` import of `system-prompt.js` |

The 14 gate-row files are closed because their *gating predicate* is a
property of argv, environment, mode or `model.api`, none of which relocation
changes. For these files B closes the read-performing invocation along with
the rest.

**8.10.5 `U126_READ_UNPROVEN` — 57 files, listed explicitly.** Each is
reachable, is named by no §7.3 gate row and no §7.5 loader target, and is not
established C, D or E by any frozen statement. The two right-hand columns are
what the frozen record *does* say about the file; "group membership only" means
the record says nothing file-specific.

| # | Path | PE-4A group | File-specific frozen mention |
|---:|---|---|---|
| 1 | `dist/cli/args.js` | FP-I | §8.1 (region), §9, §9.2, App.C |
| 2 | `dist/core/agent-session.js` | SEAM | §3, §9.2, App.C |
| 3 | `dist/core/bash-executor.js` | FP-E | §9.2 |
| 4 | `dist/core/export-html/tool-renderer.js` | FP-E | §9.2 |
| 5 | `dist/core/model-runtime.js` | SEAM | §3, §9.2, App.C |
| 6 | `dist/core/nested-tool-calls.js` | FP-E | §9.2 |
| 7 | `dist/core/resource-loader.js` | FP-I | §8.1 (region), §9, §9.2, App.C |
| 8 | `dist/core/sdk.js` | SEAM | §3, §9.2, App.C |
| 9 | `dist/core/settings-manager.js` | FP-I | §7.3, §8.1 (region), §9, §9.2, App.C |
| 10 | `dist/core/system-prompt.js` | SEAM | §3, §9.2, App.C |
| 11 | `dist/core/tools/read.js` | FP-E | — (group membership only) |
| 12 | `dist/core/tools/renderers/bash.js` | FP-E | — (group membership only) |
| 13 | `dist/core/tools/renderers/edit.js` | FP-E | — (group membership only) |
| 14 | `dist/extensions/codemode/execute.js` | FP-L | — (group membership only) |
| 15 | `dist/extensions/codemode/index.js` | FP-I | §8.1 (whole) |
| 16 | `dist/extensions/codemode/tool.js` | FP-E | — (group membership only) |
| 17 | `dist/extensions/llama/provider.js` | FP-E | — (group membership only) |
| 18 | `dist/extensions/mcp/cli.js` | FP-L | — (group membership only) |
| 19 | `dist/extensions/mcp/index.js` | FP-E | — (group membership only) |
| 20 | `dist/extensions/mcp/resources.js` | FP-E | — (group membership only) |
| 21 | `dist/extensions/mcp/runtime.js` | FP-L | — (group membership only) |
| 22 | `dist/extensions/mcp/tools.js` | FP-E | — (group membership only) |
| 23 | `dist/extensions/mcp/ui.js` | FP-E | — (group membership only) |
| 24 | `dist/main.js` | SEAM | §3, §9.2, F-5, App.C |
| 25 | `dist/modes/interactive/components/bash-execution.js` | FP-E | — (group membership only) |
| 26 | `dist/modes/interactive/components/branch-summary-message.js` | FP-E | — (group membership only) |
| 27 | `dist/modes/interactive/components/compaction-summary-message.js` | FP-E | — (group membership only) |
| 28 | `dist/modes/interactive/components/custom-entry.js` | FP-E | — (group membership only) |
| 29 | `dist/modes/interactive/components/custom-message.js` | FP-E | — (group membership only) |
| 30 | `dist/modes/interactive/components/settings-selector.js` | FP-E | — (group membership only) |
| 31 | `dist/modes/interactive/components/skill-invocation-message.js` | FP-E | — (group membership only) |
| 32 | `dist/modes/interactive/components/tool-execution.js` | FP-E | — (group membership only) |
| 33 | `dist/modes/interactive/theme/theme.js` | FP-E | §9.2 |
| 34 | `dist/utils/ansi.js` | FP-E | — (group membership only) |
| 35 | `dist/utils/image-resize-core.js` | FP-E | — (group membership only) |
| 36 | `dist/utils/syntax-highlight.js` | FP-E | — (group membership only) |
| 37 | `node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js` | SEAM | §3, §9.2, App.C |
| 38 | `node_modules/@earendil-works/pi-ai/dist/api/cloudflare-workers-ai-system-one.js` | FP-L | — (group membership only) |
| 39 | `node_modules/@earendil-works/pi-ai/dist/api/lazy.js` | FP-I | §8.1 (whole), §9.2 |
| 40 | `node_modules/@earendil-works/pi-ai/dist/api/llama-cpp-classify.js` | FP-L | — (group membership only) |
| 41 | `node_modules/@earendil-works/pi-ai/dist/api/mistral-conversations.js` | FP-L | — (group membership only) |
| 42 | `node_modules/@earendil-works/pi-ai/dist/api/system-one-shared.js` | FP-L | — (group membership only) |
| 43 | `node_modules/@earendil-works/pi-ai/dist/api/typesafe-system-one.js` | FP-L | — (group membership only) |
| 44 | `node_modules/@earendil-works/pi-ai/dist/models.js` | SEAM | §3, §9.2, App.C |
| 45 | `node_modules/@earendil-works/pi-ai/dist/providers/faux.js` | FP-E | — (group membership only) |
| 46 | `node_modules/@earendil-works/pi-ai/dist/providers/openai.js` | FP-E | — (group membership only) |
| 47 | `node_modules/@earendil-works/pi-ai/dist/providers/radius.js` | FP-E | — (group membership only) |
| 48 | `node_modules/@earendil-works/pi-ai/dist/utils/estimate.js` | FP-L | §9.2 |
| 49 | `node_modules/@earendil-works/pi-ai/dist/utils/event-stream.js` | FP-E | §9.2 |
| 50 | `node_modules/@earendil-works/pi-ai/dist/utils/model-operations.js` | FP-E | §9.2 |
| 51 | `node_modules/@earendil-works/pi-ai/dist/utils/provider-retry.js` | FP-I | §8.1 (whole), §9, §9.2, App.C |
| 52 | `node_modules/@earendil-works/pi-ai/dist/utils/retry.js` | FP-E | — (group membership only) |
| 53 | `node_modules/@earendil-works/pi-mcp/dist/oauth/flow.js` | FP-L | — (group membership only) |
| 54 | `node_modules/@earendil-works/pi-tui/dist/components/box.js` | FP-E | — (group membership only) |
| 55 | `node_modules/@earendil-works/pi-tui/dist/components/text.js` | FP-E | — (group membership only) |
| 56 | `node_modules/@earendil-works/pi-tui/dist/index.js` | FP-E | §9.2 |
| 57 | `node_modules/@earendil-works/pi-tui/dist/tui-alt-screen.js` | FP-E | — (group membership only) |

Sorted-path SHA-256 of this set: `e55241b9a056a27d5ea4a10905edba4149c02bfc7d362b42bbef59e36369033a`.
By PE-4A group: seam 7, FP-I 6, FP-E 34, FP-L 10.

**What the frozen record says about the files that have partial statements —
and why it does not place them outside the set.**

- *Seam files* (`main.js`, `agent-session.js`, `model-runtime.js`, `sdk.js`,
  `system-prompt.js`, `agent-loop.js`, `models.js`): PE-4A §5 and §9.1 re-derive
  the specific premises AIDO relies on, line-cited, and F-5 (i)–(iii) records the
  startup filesystem effects found. That is a statement about premises and
  about writes, not an enumeration of every read or path derivation in these
  files. The `docs` section of `system-prompt.js` embeds absolute README / docs /
  examples **paths as text** (F-4, G-11; accepted as **D-F5A-4**) — a
  path-derivation route whose use is frozen; any *other* route in that file is
  not covered.
- *`settings-manager.js`, `resource-loader.js`, `args.js`* (FP-I, depth
  *region*): §7.6 ("configuration discovery", "filesystem behavior relevant to
  CFG1") records that discovery uses the pinned config directory and `cwd`, that
  project configuration is excluded by `trust=false` (`--no-approve`) and that no
  auto-discovered resource survives the flags (N-06, N-08). That bounds the
  named routes; §8.1 states that a region inspection is not a whole-file audit.
- *`codemode/index.js`, `pi-ai/api/lazy.js`, `pi-ai/utils/provider-retry.js`*
  (FP-I, depth *whole*): read end to end; the recorded outcome is "no
  counter-example to the E1 derivations", which is not a statement about
  filesystem reads.
- *`theme.js`* (FP-E): §7.2's D5 row records that the built-in theme JSONs "are
  read by `initTheme` (colors only)". That names one in-payload route and its
  frozen use; it is a statement about the data files, not an enumeration of the
  module's routes.
- *All other files*: group membership only (and, for some, a §9.2 import
  listing, which records that a seam file imports it, not what it does).

**8.10.6 Consequence: R1-FU2 HOLD** *(as submitted; the recovery and review it required are recorded in §8.10.8, which empties the set — the HOLD is lifted only by independent acceptance of §8.10.8)*.

- The amendment is **not** a design candidate while the set is non-empty. Its
  other parts are unaffected and are not reopened.
- **Exact approved bytes for ONLY these 57 files must be recovered and
  statically reviewed before design freeze.** The other 69 are not to be
  re-reviewed, and the review is not to be broadened to the 126 again.
  Recovering them requires an installation whose payload equals the approved
  profile for those paths; obtaining one is outside this document and is not
  authorized here.
- For each of the 57 the review must enumerate **every** filesystem read and
  every path derivation (module URL, `import.meta.*`, `process.execPath`,
  `process.argv[1]`, `config.js` getters, upward traversal, home lookups), and
  classify each route C, D or E with the frozen statement that supports it, or
  report it as relocation-sensitive and unbounded — which would reopen the
  design. A route through a `config.js` getter is D by construction (8.10.3);
  its downstream use still needs a frozen statement.
- **R-E5-COMPAT may retain only** behavior proven capable of nothing worse than
  fail-closed resolution, start or read availability: the three optional literal
  requires of PE-4A §6.3 / F-13 and non-literal or dynamic resolution (PE-4A
  §12). It retains nothing about the 57.
- What is **not** claimed: that any of the 57 was read; that any of them is
  harmless; that any of them runs correctly from `C` (that is E5).

**8.10.7 Individually dispositioned items.**

1. **`dist/main.js:460-462` — `cleanupWindowsSelfUpdateQuarantine(getPackageDir())`.**
   Recorded in frozen PE-4A (§7.3 row, F-5). Bounded by INV-F5A-R1: the target is
   `undefined` on the proven topology (§2.2–§2.4, §8.4).
2. **`dist/core/system-prompt.js` — docs paths.** F-4, G-11; model-visible text
   only; **D-F5A-4**.
3. **`dist/main.js:463` — `cleanupManagedInstall()`, defined in
   `dist/package-manager-cli.js`.** **ACCEPTED BY INDEPENDENT REVIEW.** *Basis:*
   the earlier R0 authoring evidence, which was explicitly approved-byte-bound
   and recorded the startup call and its `PI_MANAGED_INSTALL_ROOT` gate
   (`package-manager-cli.js:23-27`), **plus** the frozen T-4 / current CFG1 child
   environment, a **positive** allowlist (`BASE_WINDOWS_NAMES`, a narrowed
   `PATH`, `PI_CODING_AGENT_DIR`, `PI_OFFLINE`, `PI_SKIP_VERSION_CHECK`,
   `PI_TELEMETRY`, one credential carrier; `environment.py`
   `build_cfg1_child_environment`) that never includes
   `PI_MANAGED_INSTALL_ROOT`. **This document does not claim that PE-4A itself
   recorded that startup call**: PE-4A's §7.3 row for `package-manager-cli.js`
   describes only the command handlers. The item is closed and is not carried as
   an open reviewer decision.

**8.10.8 Recovery and byte review of the 57 (R1-FU2 addendum) — result: `U126_READ_UNPROVEN` is EMPTY.**

> This subsection is **new evidence recorded in this amendment**. It is a static
> review of recovered bytes by the same author as the rest of this document. It is
> not frozen, not independently reviewed, and grants no authority. Per 8.10.6 the
> HOLD is lifted only if independent review accepts it (D-F5A-9).

*(1) Source acquisition (data only).* The approved profile declares
`@earendil-works/pi-coding-agent` 1.0.3 with `pi-agent-core`, `pi-ai` 1.0.3
(`package.json` in the committed manifest bundle; the nested `pi-mcp` and `pi-tui`
manifests declare 1.0.3 too). The five packages that hold the 57 files —
`pi-coding-agent`, `pi-agent-core`, `pi-ai`, `pi-mcp`, `pi-tui`, all `@1.0.3` —
were fetched from `registry.npmjs.org` over HTTPS with public, read-only,
unauthenticated requests, using Python standard-library `urllib`, `tarfile` and
`hashlib` only. Nothing was executed: no Node, Pi, npm, package script, downloaded
JavaScript or model backend. The global Pi installation was not read, changed or
downgraded. Tarballs and the 57 staged files live only in the session scratch
directory; **nothing was written to the repository or to any run workspace.**
All downloaded bytes, member names and archive metadata were treated as untrusted:
only regular-file members under a `package/` prefix were accepted; absolute
paths, backslashes, drive/stream colons, `..` components, symlinks, hardlinks,
reparse-style or other non-regular members, and duplicate or case-colliding
paths were rejected (rejections: **0**); contents were hashed in memory.

*(2) Acceptance rule.* Version text, package name, the `latest` tag and registry
provenance are **not** evidence. Each file is accepted only if its
payload-relative path, regular-file type, exact size and exact SHA-256 equal its
entry in the committed PE-5-approved PI-PC1 inventory
(`pi_profile_policy/inventories/66cf8a81…664dc.json`). The registry's
`dist.integrity` (sha512) and `dist.shasum` (sha1) matched the downloaded bytes
for all five tarballs; that only shows the download was intact.

*(3) Recovery result.*

| Quantity | Value |
|---|---:|
| members in the five tarballs (all regular files) | 2 367 |
| equal to their committed inventory entry (path, size, SHA-256) | **2 367** |
| digest or size mismatches | **0** |
| members absent from the committed inventory | **0** |
| of the 57: recovered and exactly equal | **57 / 57** |
| of the 57: failed or still unavailable | **0** |
| sorted-path SHA-256 of the 57 recovered paths | `e55241b9…69033a` (equals §8.10.5) |

Of the other 69 files of `U126`, 62 were incidentally recovered and verified and
**were not re-reviewed**; 7 are not in the five packages fetched and remain on
their frozen basis A / B with no new evidence: `pi-codemode/dist/runtime/{host,prelude-source,worker}.js`
and the four `@babel/runtime` helper files (`helpers/{interopRequireWildcard,toPrimitive}.js`
and their `esm/` twins). Recovered bytes outside the 57 were consulted only to
confirm a cited gate, and only these were: `dist/package-manager-cli.js`
(`getActiveManagedInstallRoot()` returns `undefined` when `PI_MANAGED_INSTALL_ROOT`
is unset, so `cleanupManagedInstall()` returns before any filesystem work — this
confirms §8.10.7 item 3 from approved bytes), `dist/extensions/index.js` (four
built-in factories) and the `*.lazy.js` loaders. They contradict no frozen
statement.

*(4) What was reviewed, and how completely.* A pattern sweep covered all 57
files for every route type below, then the surrounding code of every hit was
read. The sweep results are part of the evidence:

| Route type | Occurrences in the 57 |
|---|---|
| `import.meta`, `__dirname`, `__filename`, `fileURLToPath` | **0** |
| `process.execPath`, `process.argv` | **0** |
| `createRequire`, `require(`, `module.paths`, `require.main` | **0** |
| `new URL(` | **0**; `pathToFileURL` 1 (`mcp/runtime.js:295`, over `cwd`) |
| `import(` | 1 (`syntax-highlight.js:55`, fixed specifier) |
| `child_process`, spawn / exec, `new Worker`, `worker_threads`, `eval`, `new Function`, `vm`, `WebAssembly`, native `.node`, `Bun` / `Deno` | **0** |
| `fs` / `node:fs` / `fs/promises` import | 6 files: `agent-session`, `resource-loader`, `settings-manager`, `tools/read`, `mcp/cli`, `theme` |
| `homedir()` | 1 (`mcp/runtime.js:44-47`) |
| `process.cwd()` | 3 live (`sdk.js:69`, `main.js:464`, `mcp/index.js:212`) + 1 doc comment |
| `config.js` getter calls (`getAgentDir`, `getPackageDir`, `getThemesDir`, `getCustomThemesDir`, `getReadmePath`, `getDocsPath`, `getExamplesPath`, `getQuickJSWasmPath`, `getCodemodeWorkerSpecifier`) | 9 files: `model-runtime`, `sdk`, `settings-manager`, `system-prompt`, `codemode/execute`, `codemode/tool`, `mcp/index`, `main`, `theme` |

Module resolution: every bare specifier in the 57 (ten package roots —
`@earendil-works/{pi-agent-core,pi-ai,pi-codemode,pi-mcp,pi-tui}`, `chalk`,
`highlight.js`, `marked`, `proper-lockfile`, `typebox`) was resolved against the
committed inventory's directory set by Node's nearest-`node_modules`-ancestor rule.
All resolve to a `node_modules/<package>` directory **inside the payload** (the
payload has four `node_modules` directories; the three nested ones belong to
`@aws-sdk/credential-provider-sso`, `gaxios` and `proper-lockfile` and shadow
none of these). This independently agrees with the PE-4A §6.3 statement already
relied on in §8.2. Subpath `exports` entries are payload bytes and are the same at
any location; whether they all exist is an E5 start-availability matter
(R-E5-COMPAT), not a relocation difference.

*(5) Byte-confirmed gates used below.*

| Id | Gate (location-independent) | Evidence in recovered bytes |
|---|---|---|
| G1 | `--no-extensions`: built-in extension factories are never constructed | `resource-loader.js:244-246` (built-in factories go to a separate map, not the inline list), `:403-407` and `:500` (`extensionPaths = cliEnabledExtensions`), `:524-531` (a factory is constructed only for a `builtin:` path in that list) |
| G2 | `--tools` allowlist: a non-named built-in is neither registered nor active | `agent-session.js:1099-1100`, `:2787`, `:2829`; `sdk.js:145` |
| G3 | `pi mcp` subcommand only | `main.js:484` |
| G4 | `--no-context-files` | `resource-loader.js:461` |
| G5 | `--no-skills` | `resource-loader.js:419-421` |
| G6 | project settings are not read while untrusted (`--no-approve`) | `settings-manager.js:233-235` |
| G7 | `PI_MANAGED_INSTALL_ROOT` unset (the child environment is a positive allowlist, T-4) | `package-manager-cli.js` `getActiveManagedInstallRoot()` |
| G8 | `--mode rpc` | `main.js:81-83`, `:774`; theme watcher only for interactive (`:735`) |

*(6) Confirmed location-sensitive routes.* These are the only routes in the 57
whose target or result depends on where the package sits:

| Route | Where | Target at `C` | Disposition |
|---|---|---|---|
| `getPackageDir()` into `cleanupWindowsSelfUpdateQuarantine` | `main.js:461` | a quarantine path, `undefined` on the proven topology | frozen F-5; INV-F5A-R1; §8.10.7 item 1. Unchanged |
| `cleanupManagedInstall()` | `main.js:463` | none (G7) | §8.10.7 item 3, now byte-confirmed |
| `getReadmePath` / `getDocsPath` / `getExamplesPath` | `system-prompt.js:87-89` | path **text** only | F-4, G-11, D-F5A-4. Unchanged |
| `getThemesDir()` then `readFileSync` of `dark.json` / `light.json` | `theme.js:274-279` | `C\dist\modes\interactive\theme\*.json`, inventory-pinned, no `src` directory | in-payload; colours only (D5) |
| `getDocsPath()` string | `codemode/tool.js:54` | `C\docs\codemode.md` text, no read | not constructed (G1) |
| `getQuickJSWasmPath()` / `getCodemodeWorkerSpecifier()` | `codemode/execute.js:366-367` | in-payload `quickjs.wasm` | not invoked (G1) |
| dynamic `import("highlight.js/lib/index.js")` | `syntax-highlight.js:55` | in-payload `node_modules/highlight.js` | failure swallowed; rendering only |
| static and dynamic bare-specifier resolution | the 57 | in-payload packages (see (4)) | §8.2, PE-4A §6.3 |

Every other filesystem read in the 57 is rooted at `cwd`, at `agentDir`
(`PI_CODING_AGENT_DIR`, T-4 / N-07), at a CLI-supplied path or at a tool-argument
path. None of those is derived from the package location, so none changes when
the package moves.

*(7) Downstream trace of the relevant values.*

| Sink | What reaches it from a location-sensitive route | Frozen / byte basis |
|---|---|---|
| prompt / model-visible text | the three docs paths (now `R\pi_runtime\pi-coding-agent\...` instead of the operator's npm-prefix path, which removes an operator-path disclosure); `cwd` text unchanged; **no** context file (G4), no skills (G5) | F-4, G-11, D-F5A-4, §8.9 |
| provider / model configuration | none: `models.json`, `models-store.json` and `settings.json` are under `agentDir`, never the package directory; `APP_NAME` comes from the payload's `package.json`, inventory-pinned | `model-runtime.js:80`, `settings-manager.js:99`, N-07 |
| backend requests | none: the provider code in the 57 has no fs, path or env API | sweep (4) |
| AIDO authority decisions | none: authority rests on L14 / L21A, outside Pi; nothing in the 57 returns a value to AIDO | §7.7, §7.5 |
| sensitive diagnostics | `settings-manager.js` error messages carry settings paths (`agentDir`, `cwd`); a module-not-found error would carry run-private `C` paths; neither carries a secret or an operator path | `settings-manager.js:233-250` |

*(8) Material-difference determination.* The target is a relocation-induced
trust, authority or privacy difference under the actual CFG1 invocation path
(`--mode rpc`, `--no-extensions --extension <AIDO entry>`, `--tools
aido_read,aido_edit`, `--no-builtin-tools`, `--no-skills`, `--no-prompt-templates`,
`--no-themes`, `--no-context-files`, `--no-approve`, `--offline`). **None found.**
The relocation-induced differences that exist are the ones already recorded and
accepted in principle: the docs-path text (D-F5A-4, a privacy improvement), the
nearest-ancestor fallthrough set for module resolution (§8.2, §8.8) and the
absent F-5 delete target (INV-F5A-R1). No route in the 57 reads outside the
approved payload and the AIDO-owned config, workspace and CLI-supplied
locations because of where the package sits.

*(9) Path-by-path disposition of the 57.* Basis letters are §8.10.1 (**B** gate,
**C** no route, **D** bounded route; **E** is not used). Evidence class is **R**:
recovered-byte review (this subsection). Gates G1–G8 are in (5).

| # | Path | Basis | Grounds |
|---:|---|---|---|
| 1 | `dist/cli/args.js` | **C** | Imports only `chalk` and `config.js` name constants; argument parsing; no fs, path, env, URL or process API. |
| 2 | `dist/core/agent-session.js` | **D** | One `readFileSync` (`:1639`) of a loader-discovered skill file, reachable only for a registered skill (`--no-skills` leaves none, N-06); `dirname`/`basename` (`:2605`, `:2621`) are string derivation on extension paths AIDO supplies. No package-derived target. |
| 3 | `dist/core/bash-executor.js` | **C** | No fs, path, env or URL API of its own; delegates to sibling modules. |
| 4 | `dist/core/export-html/tool-renderer.js` | **C** | Pure rendering; no fs, path, env or URL API. |
| 5 | `dist/core/model-runtime.js` | **D** | `models.json` and `models-store.json` under `getAgentDir()` (`:80`, `:84`): the AIDO-owned config directory, selected by `PI_CODING_AGENT_DIR` (N-07). No package-derived path. |
| 6 | `dist/core/nested-tool-calls.js` | **C** | No fs, path, env or URL API. |
| 7 | `dist/core/resource-loader.js` | **D** | Reads are rooted at `cwd`, `agentDir`, CLI-supplied paths and extension package roots from package-manager metadata (`:36-39`). The upward ancestor walk (`:166-190`) lives only in `loadProjectContextFiles`, skipped by `--no-context-files` (`:461`); SYSTEM.md / APPEND_SYSTEM.md discovery (`:940-956`) is `agentDir` or trust-gated `cwd`. No `config.js` getter, no `import.meta`. |
| 8 | `dist/core/sdk.js` | **D** | `getAgentDir()` (`:31`), `process.cwd()` (`:69`) and `join` under `agentDir` (`:72-76`). No package-derived path. |
| 9 | `dist/core/settings-manager.js` | **D** | Global `settings.json` in `agentDir` (`:99`, `:204`); the project `.pi/settings.json` is not read while untrusted (`:233-235`; `--no-approve`, N-06); lock files beside them (F-5 (ii)). No package-derived path. |
| 10 | `dist/core/system-prompt.js` | **D** | No fs read. `getReadmePath` / `getDocsPath` / `getExamplesPath` (`:87-89`) yield model-visible path **text** only: F-4, G-11, D-F5A-4. |
| 11 | `dist/core/tools/read.js` | **B** | Tool body reads a tool-argument path relative to `cwd` (`:20-21`, `:56`). The built-in `read` definition is dropped from the registry and the active set unless named (`agent-session.js:1099-1100`, `:2787`, `:2829`); AIDO names only `aido_read,aido_edit` (G2). Not package-derived either way. |
| 12 | `dist/core/tools/renderers/bash.js` | **C** | Rendering only; no fs, path, env or URL API. |
| 13 | `dist/core/tools/renderers/edit.js` | **C** | Rendering only; no fs, path, env or URL API. |
| 14 | `dist/extensions/codemode/execute.js` | **B** | The only package-location routes are `getQuickJSWasmPath()` (`:366`) and `getCodemodeWorkerSpecifier()` (`:367`). Reached only through the `execute.lazy.js` dynamic import on a first codemode script; the built-in codemode extension is never constructed (G1). Were it, `quickjs-wasi/quickjs.wasm` is an in-payload inventory file. |
| 15 | `dist/extensions/codemode/index.js` | **C** | Extension factory only; no fs, path, env or URL API of its own. |
| 16 | `dist/extensions/codemode/tool.js` | **D** | `CODEMODE_DOCS_PATH = join(getDocsPath(), "codemode.md")` (`:54`) is a module-evaluation **string derivation** of an in-payload path (`docs/codemode.md` is an inventory file); no read. Its only consumer is the codemode tool description, which is never built (G1). |
| 17 | `dist/extensions/llama/provider.js` | **C** | Only `process.env.LLAMA_BASE_URL` (`:120`, `:122`) inside an interactive login prompt; no fs, path or location-derived value; extension never constructed (G1). |
| 18 | `dist/extensions/mcp/cli.js` | **B** | `existsSync(projectConfig)` (`:137`) and joins under `cwd` / `agentDir` (`:129`). Runs only for the `pi mcp` subcommand (`main.js:484`; AIDO's first argument is `--mode`), loaded through the `cli.lazy.js` dynamic import. |
| 19 | `dist/extensions/mcp/index.js` | **B** | `getAgentDir()` / `process.cwd()` derivations (`:212`, `:257`, `:610`, `:792`, `:1098`); the built-in MCP extension is never constructed (G1). No package-derived target. |
| 20 | `dist/extensions/mcp/resources.js` | **C** | No fs, path, env or URL API. |
| 21 | `dist/extensions/mcp/runtime.js` | **B** | `homedir()` expansion of MCP server config (`:44-47`) and `pathToFileURL(cwd)` (`:295`); loaded only via `runtime.lazy.js` on first MCP use; extension never constructed (G1). No package-derived target. |
| 22 | `dist/extensions/mcp/tools.js` | **C** | Only `createHash`; no fs, path, env or URL API. |
| 23 | `dist/extensions/mcp/ui.js` | **C** | Rendering only; no fs, path, env or URL API. |
| 24 | `dist/main.js` | **D** | The only package-derived routes: `getPackageDir()` at `:461` (INV-F5A-R1, §8.10.7 item 1) and `cleanupManagedInstall()` at `:463` (env-gated, §8.10.7 item 3, now byte-confirmed). Everything else is `cwd` (`:464`), `agentDir` (`:465`), the session directory (`:548-551`) or gates (G3, G8). `fetch(` occurs only in a comment (`:473`). |
| 25 | `dist/modes/interactive/components/bash-execution.js` | **C** | TUI component; no fs, path, env or URL API. |
| 26 | `dist/modes/interactive/components/branch-summary-message.js` | **C** | TUI component; no fs, path, env or URL API. |
| 27 | `dist/modes/interactive/components/compaction-summary-message.js` | **C** | TUI component; no fs, path, env or URL API. |
| 28 | `dist/modes/interactive/components/custom-entry.js` | **C** | TUI component; no fs, path, env or URL API. |
| 29 | `dist/modes/interactive/components/custom-message.js` | **C** | TUI component; no fs, path, env or URL API. |
| 30 | `dist/modes/interactive/components/settings-selector.js` | **C** | TUI component; no fs, path, env or URL API. |
| 31 | `dist/modes/interactive/components/skill-invocation-message.js` | **C** | TUI component; no fs, path, env or URL API. |
| 32 | `dist/modes/interactive/components/tool-execution.js` | **C** | TUI component; no fs, path, env or URL API. |
| 33 | `dist/modes/interactive/theme/theme.js` | **D** | Package-derived: `getThemesDir()` (`:274`, `:288`) -> `dark.json` / `light.json` in `C\dist\modes\interactive\theme` (both inventory file entries; the payload has no `src`, so `dist`). Custom themes: `getCustomThemesDir()` = `agentDir/themes` (`:314`, `:373`, `:600`). The default `system` theme reads nothing, a failed load falls back silently (`:541-553`), the watcher is off outside interactive mode (`main.js:735`); colours only (PE-4A §7.2 D5). |
| 34 | `dist/utils/ansi.js` | **C** | No imports, no fs, path, env or URL API. |
| 35 | `dist/utils/image-resize-core.js` | **C** | No fs, path, env or URL API of its own (its sibling `photon.js` is outside the 57 and behind the frozen image-helper gate). |
| 36 | `dist/utils/syntax-highlight.js` | **D** | Fixed-specifier `import("highlight.js/lib/index.js")` (`:55`); nearest-ancestor resolution lands in the in-payload `node_modules/highlight.js`; a failure is swallowed (`:56-58`). Rendering colour spans only. |
| 37 | `node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js` | **C** | Agent loop; imports `pi-ai` and `./stream-fn.js` only; no fs, path, env or URL API. |
| 38 | `node_modules/@earendil-works/pi-ai/dist/api/cloudflare-workers-ai-system-one.js` | **C** | Provider API; no fs, path, env or URL API. |
| 39 | `node_modules/@earendil-works/pi-ai/dist/api/lazy.js` | **C** | Lazy stream wrapper; no fs, path, env or URL API. |
| 40 | `node_modules/@earendil-works/pi-ai/dist/api/llama-cpp-classify.js` | **C** | Provider API; no fs, path, env or URL API. |
| 41 | `node_modules/@earendil-works/pi-ai/dist/api/mistral-conversations.js` | **C** | Provider API; no fs, path, env or URL API. |
| 42 | `node_modules/@earendil-works/pi-ai/dist/api/system-one-shared.js` | **C** | Provider API; no fs, path, env or URL API. |
| 43 | `node_modules/@earendil-works/pi-ai/dist/api/typesafe-system-one.js` | **C** | Provider API; no fs, path, env or URL API. |
| 44 | `node_modules/@earendil-works/pi-ai/dist/models.js` | **C** | Model catalog / stream dispatch; imports `auth/context.js` (whose ADC probe is the already-recorded F-5 (ii) item, outside the 57); no fs, path, env or URL API of its own. |
| 45 | `node_modules/@earendil-works/pi-ai/dist/providers/faux.js` | **C** | Provider; no fs, path, env or URL API. |
| 46 | `node_modules/@earendil-works/pi-ai/dist/providers/openai.js` | **C** | Provider definition; no fs, path, env or URL API. |
| 47 | `node_modules/@earendil-works/pi-ai/dist/providers/radius.js` | **C** | Provider definition; no fs, path, env or URL API. |
| 48 | `node_modules/@earendil-works/pi-ai/dist/utils/estimate.js` | **C** | Token estimation; no fs, path, env or URL API. |
| 49 | `node_modules/@earendil-works/pi-ai/dist/utils/event-stream.js` | **C** | No imports, no fs, path, env or URL API. |
| 50 | `node_modules/@earendil-works/pi-ai/dist/utils/model-operations.js` | **C** | No fs, path, env or URL API. |
| 51 | `node_modules/@earendil-works/pi-ai/dist/utils/provider-retry.js` | **C** | No imports, no fs, path, env or URL API. |
| 52 | `node_modules/@earendil-works/pi-ai/dist/utils/retry.js` | **C** | No imports, no fs, path, env or URL API. |
| 53 | `node_modules/@earendil-works/pi-mcp/dist/oauth/flow.js` | **C** | Protocol logic over sibling modules; no fs, path, env or URL API. |
| 54 | `node_modules/@earendil-works/pi-tui/dist/components/box.js` | **C** | TUI component; no fs, path, env or URL API. |
| 55 | `node_modules/@earendil-works/pi-tui/dist/components/text.js` | **C** | TUI component; no fs, path, env or URL API. |
| 56 | `node_modules/@earendil-works/pi-tui/dist/index.js` | **C** | Re-export barrel; no fs, path, env or URL API of its own. |
| 57 | `node_modules/@earendil-works/pi-tui/dist/tui-alt-screen.js` | **C** | Only terminal-capability env reads (`TERM`, `TMUX`, `ZELLIJ`, `STY`, `TERM_PROGRAM`, `WEZTERM_PANE`: `:179-184`, `:822`, `:1463`); no fs, path or location-derived value. |

*(10) Result.* Every one of the 57 now has basis B (5), C (42) or D (10) with
evidence class R. **`U126_READ_UNPROVEN` = ∅ (0 files).** Sorted-path SHA-256 of
the new sets (Appendix U126): `B/R` `eea3a75a366ebe6abb98e9c4f96af0ed4c6addb9fe80f25a3174f06d7d587005`, `C/R` `7f47a89245f670553fe7bbaf4dd7338af46771b2af090415a32df007eaccd121`, `D/R` `34e755cbb37b23c971832d4cd5e8e38d87a8dd6ef8746b001ea30666e5bf6d6c`.
A (54) and B/F (15) are unchanged.

*(11) Not claimed.* That any of the 57 was read or runs correctly from `C` (that
is E5); that callees outside the 57 were re-reviewed (they are in the 4 732
available files re-scanned in R1, the 69 excluded files, or `config.js`);
that the analysis covers anything but the CFG1 argv and environment above; or
that the recovered 2 367 files are a complete approved installation. They are
not: **12 679 of the 15 046 approved files are not in these five tarballs** —
`@earendil-works/{chord (119), pi-codemode (42), pi-telemetry (26)}` and 110
third-party package directories (12 492 files). All 1 248 files of
`pi-coding-agent` itself and the whole of `pi-agent-core`, `pi-ai`, `pi-mcp` and
`pi-tui` are covered. A complete approved source installation for the eventual E5
(§17 condition 9) therefore does **not** yet exist, and nothing here places any
recovered file in an installation.

---

## 9. Residuals (stated, not closed)

| Id | Residual |
|---|---|
| R-SLIVER / R-ABA (unchanged; scope made explicit) | content substitution inside `C`, **file→reparse conversion of any payload file** (including the pinned four, Q2/Q3), and any post-proof redirection of the chain are arbitrary-code-object capability after the last proof, exactly as for any payload (§8.6). Before L14 they are caught by the L14 precondition/re-proof; after it they are inherited |
| R-EXT-1 (concrete path moved, class unchanged) | undeclared/dynamic upward resolution from `C` now meets `RT\node_modules` and `R\node_modules` (proved absent at L3R and L14) and the temp-scratch ancestry, instead of the shared npm prefix siblings (§8.2, §8.8) |
| R-EXT-2 (narrowed) | the loader's `packagesRoot` workspace probes now target AIDO-owned `RT` (proved to hold only `C`) instead of the shared npm scope directory (§8.1) |
| R-E5-COMPAT (new; availability only; **narrowed in R1-FU1, restated in R1-FU2**) | May retain **only** behavior proven capable of nothing worse than fail-closed resolution, start or read availability: the three optional literal requires of PE-4A §6.3 / F-13 and non-literal or dynamic resolution (PE-4A §12). It retains **nothing** about the 57 files of `U126_READ_UNPROVEN` and nothing about the 69 excluded ones; it is not a catch-all. First observable at E5; fails closed; cannot create a delete target (§8.2) |
| **R-U126-READ (byte review recorded; awaiting independent review)** | Was: 57 reachable approved files whose location-sensitive reads frozen evidence did not bound (§8.10.5). §8.10.8 recovered their approved bytes (57/57 exact) and classed every one B, C or D with no relocation-induced trust, authority or privacy difference. Still **not** an accepted residual and still **blocks design freeze** until independent review accepts §8.10.8 (D-F5A-9); no residual is carried by it if accepted |
| R-COST (widened) | §7.9 (per-file in-memory verification; peak transient memory = largest approved file) |
| R-WINDOW (FU15 class; restated in R1-FU1) | between each `CreateDirectoryW` and the acquisition of that directory's first identity-bearing pin (§7.4A.4), and the creator→pin interval for the four final pins: pre-authority. **No content byte is written in either window**; a substituted directory is still a pinned-parent entry beneath `R`, so no write leaves `R` |
| R-SRC-MEM (new, R1-FU1) | foreign bytes read by a raced source open exist transiently in process memory until released; never persisted, logged or interpreted by AIDO; no memory-scrubbing claim; paging/crash dumps outside the observation boundary (§7.4B) |
| PE-4A F-4 delta | §8.9, §11.6 |

**Removed from R0:** R-F5A-UNOBSERVED-EXIT (the controller-death /
surviving-child handle residual existed only because an unprotected `Q` would
become a target after AIDO exited; under R1 there is no target, before or after
AIDO's exit).

---

## 10. R0 machinery (and R1 step 6) removed from the normative design

| R0 element | R1 disposition |
|---|---|
| occupant `Q` (`RT\node_modules\.pi-native-quarantine`) and its handle | **removed** — no target exists to occupy |
| Q1 / Q2 as implementation premises | **removed** — historical evidence only (§5) |
| `RT\node_modules` and `@earendil-works` parent directories | **removed** — they are the `node_modules` ancestor R1 eliminates |
| write-capable derivation pins kept from creating handles; gap-free `ReOpenFile` successor | **removed** — replaced by post-population read-only pins (§7.6) |
| R1 step 6: destination directory checked, pathname-only control released, descendants later created by pathname; streaming copy-while-hashing | **removed in R1-FU1** — replaced by the continuously pinned, parentage-gated construction (§7.4A) and verify-before-persist (§7.4B) |
| conditional retention at L27 (`runtime_created` / `runtime_exit_observed` gate) | **removed** — unconditional release (§7.8) |
| R-F5A-UNOBSERVED-EXIT; controller-death-with-surviving-child handle residual | **removed** (§9) |
| post-run protection of `Q`; any safety-leak retention registry; conditional retention for `live_references_released` | **removed** / never adopted. The derived fact of §7.8.1 is **not** retention: it records a failure, it protects and retains nothing |
| `NEAREST_NODE_MODULES_OF_PACKAGE_ROOT` LDT rule | **replaced** by `NO_NODE_MODULES_ANCESTOR_MEANS_NO_TARGET` |
| `PI_RUNTIME_PROVISIONING_FAILED` | **renamed** `RUNTIME_PROVISIONING_FAILED` (§11.1) |

---

## 11. Required frozen-contract amendments (narrow)

### 11.1 v3 refusal vocabulary — v3 only

- `refused_at_step` gains exactly one value, **`L3R`**, ordered after `L3` and
  before `L4` in every step-order relation.
- `pre_dispatch_refusal_code` gains exactly one value,
  **`RUNTIME_PROVISIONING_FAILED`**.
- v3 gets its **own** extended objects (`REFUSAL_STEPS_V3`,
  `PRE_DISPATCH_REFUSAL_CODES_V3`, `REFUSAL_CODES_BY_STEP_V3`), with
  `"L3R": {RUNTIME_PROVISIONING_FAILED, UNEXPECTED_STEP_FAILURE}`.
- New rule **R3-S15** (next free number after the frozen R3-S14):
  `K == "L3R"` ⇒ `C ∈ {RUNTIME_PROVISIONING_FAILED, UNEXPECTED_STEP_FAILURE}` ∧
  `RC is False`. R3-S5 applies unchanged.
- The v1/v2 domains — `REFUSAL_STEPS`, `PRE_DISPATCH_REFUSAL_CODES`,
  `PRE_DISPATCH_REFUSAL_CODES_V2`, `REFUSAL_CODES_BY_STEP` — and their
  validators stay **byte-identical objects** (`is`-identical, T-F5A-16). Today
  v2 and v3 share `PRE_DISPATCH_REFUSAL_CODES_V2` and `REFUSAL_CODES_BY_STEP`;
  only the v3 validator switches to the new objects.
- No new key, no new halt code, no lifecycle-step change.

**Why `RUNTIME_PROVISIONING_FAILED`.** `pre_dispatch_refusal_code` is a
step-failure vocabulary whose members are all `<SUBJECT>_FAILED` /
`<CONDITION>` names (`RUNTIME_LAUNCH_FAILED`, `CONFIG_GENERATION_FAILED`, …).
The `PI_*` names (`PI_RESOLUTION_FAILED`, `PI_SEAM_UNPROVEN`, …) belong to the
separate proof-family field `pi_identity_failure_code`, which v2/v3 rules
R-S1…R-S6 deliberately keep **out** of the refusal-code domain. A `PI_*` refusal
code would look like a P proof outcome and invite confusion with that field;
nothing in the v3 vocabulary mechanically requires the prefix. L3R's failure is
a provisioning-step failure, named like its neighbour `RUNTIME_LAUNCH_FAILED`.
Reusing `WORKSPACE_BASELINE_FAILED` was rejected: it would misattribute a
profile/copy/topology failure to L2/L3. (**D-F5A-2**.)

### 11.2 Executor step table (CFG1 §16.2, R6 §9) — one inserted step

`L3R RUN-PROVISIONED PI RUNTIME` between L3 and L4, cursor advanced at entry
before its first side effect; refusal mode exactly like L2–L13. L3R is retained
because provisioning must precede credentials (L4) and must be attributable.

### 11.3 Launch root (PE-1 §4.1) — for launch only

For profile-aware **launch**, the L14/L21A payload root is the L3R copy `C`, not
the P1-selected root. P, the gate and L1 keep PE-1 §4.1 exactly; "P never
searches onward for a matching installation" is untouched (L3R does not search;
it creates).

### 11.4 Identity construction (AMEND1 §10, PE-1 §11.3)

`Cfg1PiIdentity` gains **no** slot. One additional sentinel-holding, read-only
function in `pi_identity` may construct an instance, only from an exact `S` and
an exact post-pin-validated copy (§7.4 step 9). "Constructible only by a passing
P" becomes "constructible only by a passing P or by the L3R copy proof over P's
own result".

### 11.5 L14 executor precondition; resource rows (CFG1 §17, §18)

- L14 gains the executor precondition of §7.7 (no change to
  `reprove_pi_identity_for_launch`).
- §17 rows: *Run-provisioned runtime copy* (created L3R; namespace + content
  authority; torn down by L27); *Final read-only pins* (opened L3R; no
  authority over any target; released unconditionally at L27 entry);
  *Construction pins and zero-byte child handles* (opened L3R, §7.4A.5 ledger;
  no authority outside the provisioning routine; closed exactly once in L3R's
  `finally`, L27 entry as backstop; a close failure degrades the lifecycle).
- §18 row: *L3R fails* → prompt not sent; resources: workspace (+ any partial
  copy / pins inside it); stage halts;
  `REFUSED_PRE_DISPATCH(RUNTIME_PROVISIONING_FAILED)` or
  `INDETERMINATE_LIFECYCLE`.

### 11.6 Forward-looking characterization deltas (no evidence edited)

- **PE-4A F-4 / G-row 2** ("arm-independent shared constant"): §8.9.
  (**D-F5A-4**.)
- **PE-4A F-5 item (i)** remains a true historical description of the
  npm-prefix launch; this amendment is its proposed resolution.
- **PE-1 §27 R-SHARED (F-3)** no longer applies to the launched payload (only to
  the byte source at L1/L3R).

### 11.7 Executor outcome fact: `live_references_released` (R1-FU2; narrow, forward-looking)

`Cfg1RunOutcome.live_references_released` keeps its name, type and place, and the
L30 check `outcome.live_references_released is True` is unchanged. The executor
stops returning the literal `True` and returns the derived fact of §7.8.1
instead. No record key is added; v1/v2 serialized contracts are untouched; the
halt and lifecycle vocabularies are unchanged.

---

## 12. Contracts explicitly NOT changed

- P0, P1 (incl. the P1 admissibility amendment), P2, P2M, P2X, P2R; the
  pre-consumption gate; L1's sequence, commit and stage-profile rule.
- `reprove_pi_identity_for_launch` and `reobserve_pi_profile_after_runtime`
  (code and meaning; only their input object changes).
- `Cfg1PiIdentity`'s slots; `PiProofResult`; the proof codes, the stage code and
  the gate codes.
- AR2 entirely: `build_pi_argv`, the supervisor, the broker,
  `remove_disposable_tree`, `build_case_repository`, `_verify_root_authority`.
- The child environment builder and **T-4** (no new name).
- `pi_manifest.compute_resolution_exposures` and `observe_exposure_absence`
  (reused, not modified).
- HPP-1, PI-PC1, PI-SC1, CFG1-CC1, the loader, the sealed snapshot, APS r0001
  and r0002, the inventories, bundles and candidates; PE-3/PE-4/PE-5 evidence.
- v1/v2 records and validators; v3 key sets; halt vocabularies; lifecycle-step
  vocabulary; OC-3/OC-4/OC-5; FU15 §37 mechanisms. (`live_references_released`:
  its field, type, record position and the L30 check are unchanged; **only the
  executor's unconditional `True` is replaced** by the derived fact of §7.8.1 —
  §11.7.)
- `win_config_authority.py` and every config-issuance, generation-interval,
  retained-authority and extension-issuance token: provisioning (§7.4A.5) reuses
  Win32 *semantics* only, mints none of them, and is accepted by none of their
  consumers.
- `CLAUDE.md`, the roadmap, the F5 exploratory test, the F5A probe module.

---

## 13. Test plan (for a future, separately authorized implementation)

All offline, pure Python, synthetic trees under pytest `tmp_path`; **no Node, Pi,
npm, network, model or credential**. The 16-test installed-Pi deselection of the
offline suite stays in force.

### 13.1 Regression tests

| Id | Proves |
|---|---|
| T-F5A-01 | the topology is exactly `R\pi_runtime\pi-coding-agent`: `RT`'s child set is `{pi-coding-agent}`; no `RT\node_modules`, no `R\node_modules`, no `@earendil-works` parent, no `.pi-native-quarantine`, no `pi.cmd`, no Pi managed-install names |
| T-F5A-02 | T-NM scans the **whole** lexical chain: a synthetic `R` path with `node_modules` (and `Node_Modules`, `NODE_MODULES`) at each position — volume-root child, mid-ancestry, scratch boundary, `R`, `RT` — refuses before any write |
| T-F5A-03 | a synthetic workspace whose **outer temp ancestry** contains a `node_modules` component (scratch boundary created under `tmp_path\node_modules\…`) refuses at L3R before any write |
| T-F5A-04 | T-CANON: UNC, `\\?\`, relative, `.`/`..`, trailing-dot and trailing-space components refuse |
| T-F5A-05 | T-PLAIN: a junction or directory symlink at any chain component (inside and above `R`) refuses at L3R and, planted after L3R, at the L14 precondition |
| T-F5A-06 | T-BUN: `$bunfs` / `~BUN` / `%7EBUN` (any case) anywhere in the path refuses |
| T-F5A-07 | `PI_PACKAGE_DIR` and `PI_MANAGED_INSTALL_ROOT` are absent from the child environment; T-4 name-set equality with I2 still holds |
| T-F5A-08 | exact profile-directed reconstruction: a synthetic payload is copied byte-identically; copy fingerprint equals source and synthetic profile; every create is inside `RT` (spy: lexical containment and parent identity) **and its parent is, at that instant, a held pin of the §7.4A chain** |
| T-F5A-09 | source walk ≠ L1's profile → refuse before any content is written; source mutated between walk and copy-read → digest mismatch → refuse **with zero bytes of the mutated content written (T-F5A-28)**; reparse in source → refuse, nothing followed |
| T-F5A-10 | no write-capable handle and no construction pin survives population: the §7.4A.5 ledger is empty (every entry `CLOSED`) when step 6 returns, on success and on every refusal path (handle-access audit of the provision object) |
| T-F5A-11 | read-only pins are acquired only after population, with `GENERIC_READ` / share READ / `OPEN_EXISTING` / open-reparse-point; **fresh** post-pin validation runs after them; a substitute planted in the creator→pin gap (different file id, reparse file, directory) refuses |
| T-F5A-12 | the genuine PI-PC1 walk, the L14 re-proof leaves and the L21A leaves complete over `C` while the final pins are held (Q4-control generalization) |
| T-F5A-13 | ancestor rename (`RT`, `C`, `dist`, `R`) by `MoveFileExW` and POSIX `FileRenameInfoEx` is refused while the final read-only pins are held, and succeeds in the released control |
| T-F5A-14 | post-pin reparse conversion of a pinned file via a `FILE_WRITE_ATTRIBUTES` handle: **characterized** (expected to succeed, Q2/Q3) and, when done before L14, **refused by the L14 precondition** (T-PLAIN); the test records it as the inherited residual of §8.6 and asserts no AIDO component treats it as safe |
| T-F5A-15 | LDT static mapping: the entry for `56651d0b…` has rule `NO_NODE_MODULES_ANCESTOR_MEANS_NO_TARGET`; its paths are `file` entries of the **committed** approved inventory; the inventory has no `dist/package.json` and no `src` (repo-local, no installed Pi) |
| T-F5A-16 | v3 validators accept `L3R` / `RUNTIME_PROVISIONING_FAILED` only per R3-S15; v1/v2 domain objects are `is`-identical to before |
| T-F5A-17 | full destination proofs at post-pin validation and L14: fingerprint equality, `EXPOSURES_PROVEN_ABSENT` with an exposure planted under `RT\node_modules`, `R\node_modules` or a temp ancestor → refuse |
| T-F5A-18 | launch identity: root = `C`, `pi_cli_js = C\dist\cli.js`, node fields equal `S`'s, profile equal; `build_pi_argv(L)` yields `C\dist\cli.js`; after L3R no reference to `S` remains; AST audit: L14 and L21A consume `state.pi_identity`, which `is` the provision's launch identity |
| T-F5A-19 | L14 precondition: foreign provision (other workspace nonce), malformed provision, released pin, pin identity ≠ path identity, `RT` gaining a child, or `state.pi_identity` not the provision's → `RUNTIME_LAUNCH_FAILED`, no launch |
| T-F5A-20 | a matched profile with **no LDT entry** refuses at L3R (synthetic second profile id) |
| T-F5A-21 | L3R refusal records `L3R` / `RUNTIME_PROVISIONING_FAILED`, `RC False`, L21A `NOT_APPLICABLE`, L27 runs and removes `R`; any other raise → `UNEXPECTED_STEP_FAILURE` at `L3R`, nothing deleted by L3R |
| T-F5A-22 | L27 releases each final pin exactly once, unconditionally, before the frozen re-proof; injected release failure → no retry, no force, removal fails → `INDETERMINATE_LIFECYCLE` **and `live_references_released` is `False` (T-F5A-33)** |
| T-F5A-23 | Q6 / F5-B regressions retained: planted junctions and file symlinks inside `R` (incl. under `C`) are not followed by L27; outside bytes, attributes and mtimes are preserved, including on the `os.chmod` retry path |
| T-F5A-24 | AST/import audit: `pi_identity` and the topology checker import no writer and perform no write; the provisioning module's pin/child types are minted only through the provisioning-only binding, are accepted by none of the config-issuance / generation-interval / retained-authority / extension-issuance consumers, and never appear in a record, port, return value or `repr` |
| T-F5A-25 | **destination parent substituted after an earlier pathname check** (§7.4A.3): in a synthetic tree, the pinned parent `P_D` is the target of a rename, delete and in-place junction-conversion attempt between the previous step and the next child create — each refused while the pin is held, so **zero** objects are created outside `R` and zero bytes written outside `R`; with the pin released (matched control) the same attempts succeed and a following pathname create **does** land outside — proving the pin, not luck, is what prevents it. An injected junction planted at a *not-yet-created* child name is refused by `CREATE_NEW` + `OPEN_REPARSE_POINT`, writing nothing at its target |
| T-F5A-26 | **parentage from the pinned parent's handle, before the first content byte** (§7.4A.2 step 3): an I/O spy over the whole of L3R proves, for every directory, that the handle enumeration of `P_D` (exact set, file ids equal each child's own handle) is performed, and passes, **before** the first content write to any file of `D`; a forced exact-set failure (foreign name planted in `D`) refuses with the content-write count for `D` and below **equal to zero** |
| T-F5A-27 | **destination bytes only through a proven child handle** (§7.4A, INV-F5A-W): the I/O spy proves zero pathname-based opens-for-write, writes, truncations or reopens of any destination child; every content byte, and every digest read-back, goes through the creating handle whose id the parentage gate matched |
| T-F5A-28 | **no unverified source byte is persisted** (§7.4B, INV-F5A-S): after the source observation, a source ancestor is redirected to a synthetic foreign file whose bytes are deliberately different and contain a sentinel `SECRET` marker. The test proves: the digest compare refuses; **zero** `SECRET` bytes (searched under `R` recursively, in every file, in any name, and in the record/artifact/log/diagnostic outputs) exist anywhere; no observed digest, size or prefix of the foreign file appears in any diagnostic; the refusal carries only the approved path and a closed reason; no runtime or authority decision changed. Matched control: with the genuine source, the same file is written |
| T-F5A-29 | the T-F5A-28 scenario **plus forced L27 removal failure** (injected): the stranded residue under `R` contains **no** unverified source content (only approved bytes and zero-byte files), and the failure classifies `INDETERMINATE_LIFECYCLE` as before |
| T-F5A-30 | **construction-handle close failure is lifecycle-significant** (§7.4A.5): a close failure is injected for a directory pin and, separately, for a child handle. L3R refuses `RUNTIME_PROVISIONING_FAILED`; no retry, force-close or re-derivation from a name occurs; **zero** pathname-based remove/unlink/rmdir calls occur anywhere in L3R; the lifecycle evidence degrades (`workspace_removed_verified` false → `INDETERMINATE_LIFECYCLE`); **`live_references_released` is `False` (T-F5A-33)**; each handle's close is called exactly once (ledger state machine) |
| T-F5A-31 | **read-relocation classification of the 126** (§8.10, Appendix U126) — a repo-local static test, no installed Pi: (i) exactly 126 rows whose sorted-path SHA-256 equals `775a8f9d…`, and the A (54), B/F (15), B/R (5), C/R (42) and D/R (10) sets equal their Appendix digests and there are **zero** `UNPROVEN` rows; (ii) every path is a `file` entry of the **committed** approved inventory and none is a path of the available set; (iii) every row has exactly one basis in {A, B, C, D, E} or `UNPROVEN` and one evidence class (`F` frozen evidence, `R` the §8.10.8 byte review), and every non-`UNPROVEN` row cites its evidence; (iv) A rows: the `dist/bundle/` prefix members (the inventory has 75 JS files under that prefix), the `@babel/runtime` members (PE-4A Appendix A `0/0/123`), and the FP-U members; (v) `B/F` rows ⊂ the PE-4A §7.3 tables or the §8.5 `--no-skills` row (parsed from the committed PE-4A document); `B/R` rows equal the five §8.10.8 paths; (vi) seam rows equal `U126 ∩ PI-SC1` with their Appendix C digests; (vii) **the acceptance suite FAILS while any row is `UNPROVEN`** — the table reached this state by the §8.10.8 byte review replacing each `UNPROVEN` basis with B, C or D and class `R`. Adding a file to `U126` without a basis fails the test |
| T-F5A-32 | **inventory-derived construction bounds** (§7.4A.6, §7.4B): from the committed inventory — maximum depth 11, maximum directory size 362, at most 360 file children and at most 80 directory children of any directory, largest file 11 694 592 bytes, handle peak 462 under the stated accounting; the implementation's ledger never exceeds the recomputed peak, and no single source read allocates more than its entry's `size + 1` |
| T-F5A-33 | **`live_references_released` is derived, not constant** (§7.8.1, §11.7) — an executor-level regression with injected `CloseHandle` failures: (a) successful closure of a full synthetic provision → `True`; (b) injected failure closing a **construction directory pin** → `False`; (c) injected failure closing a **construction child handle** → `False`; (d) injected failure closing a **final read-only pin** → `False`; (e) in each of (b)–(d) the L30 admission decision (`_run_scoped_registries_empty`, Sec. 19.1 item 4) receives `False` and refuses / halts per the existing path, with no new halt code and no new record key; (f) the fact stays `False` when L27's removal then **succeeds**, when it **fails**, when the process-level registries are empty, and when the Python reference to the failed handle is dropped (the ledger entry, not the object, decides); (g) provisioning never attempted (refusal before L3R) → `True`; (h) no retry, force-close, retention registry or adoption by a later run occurs |

### 13.2 Acceptance criteria

All T-F5A tests (01–33) pass; P-R1-1…3 established and recorded as evidence, and P-R1-4 likewise (§14); full
offline suite green with the standard deselection; no file outside §16 changed.

---

## 14. Required empirical premises for R1 (target platform, Python ctypes probes only)

R1 carries forward Q3's ancestor-rename sub-premise and Q4's read-only control as
**measured evidence**, but both were measured with shapes that differ from R1's
final pin set. These must be re-established, with matched released-pin controls,
in a future separately authorized evidence step:

| Id | Fact required |
|---|---|
| P-R1-1 | a file held with `GENERIC_READ`, share READ only, cannot be deleted, renamed, replaced or overwritten by another same-user handle (the operations of Q1) |
| P-R1-2 | while such read-only pins are held on files beneath them, `dist`, `C`, `RT` and `R` cannot be renamed (the Q3 sub-premise, re-measured for the read-only shape) |
| P-R1-3 | the genuine PI-PC1 walk and the L14/L21A leaves complete over a full synthetic copy while the four read-only pins are held (the Q4 control, generalized) |
| P-R1-4 (R1-FU1; the only new premise) | the **construction shape** of §7.4A on the target platform, with matched released-pin controls: inside a directory pinned `GENERIC_READ` / share `FILE_SHARE_READ` / `BACKUP_SEMANTICS \| OPEN_REPARSE_POINT`, (i) `CreateDirectoryW` of a child directory succeeds and the child can then be pinned the same way, (ii) up to 360 `CREATE_NEW \| OPEN_REPARSE_POINT`, share-0 zero-byte children can be created and held together with up to 80 child-directory pins, (iii) one single-pass handle enumeration of the pinned parent returns exactly the created names with each entry's file id equal to its own handle's, (iv) while that stack is held, rename of, deletion of and in-place junction conversion of the pinned directories are refused, (v) writing content through the held child handles after the gate succeeds. This is FU15's W2/W3/W5–W9 (frozen, measured for one pinned directory and two children) extended to **nested** pins, **child directories** and **fan-out**; those rows are cited, not re-assumed |

Not required (and not claimed): any property preventing `FILE_WRITE_ATTRIBUTES`
reparse conversion of a held file. INV-F5A-R1 does not depend on P-R1-1…3 (§7.6);
they establish that the pins deliver the stability they are described as
delivering. **INV-F5A-W (§7.4A), by contrast, does depend on P-R1-4**: it is the
premise that the construction shape holds on the target platform, and the
implementation may not rely on it before it is measured. **If any P-R1 fails,
implementation acceptance and E5 stop for the reviewer; no fallback is
pre-authorized.** P-R1-1…3 are kept exactly as already specified. None of these proves Node
compatibility, which is first observable at E5 (fail closed).

---

## 15. Lifecycle / state machine and selection authority

### 15.1 Provision lifecycle

```text
NOT_ATTEMPTED
  -- L3R entry: LDT entry + topology admission (no write) --------> ADMITTED
ADMITTED -- write-ahead -------------------------------------------> ATTEMPTED
ATTEMPTED -- source walk == X ------------------------------------> SOURCE_PROVEN
SOURCE_PROVEN -- R pinned + identity-proven; RT, C created, pinned, -> CHAIN_CREATED
                 non-reparse, parentage-proven from the pinned parent (§7.4A)
CHAIN_CREATED -- per directory: zero-byte children + child pins -> exact-set
                 parentage gate -> verified bytes written through child handles
                 (§7.4A.2, §7.4B); every construction handle CLOSED  -> POPULATED
POPULATED -- four read-only pins acquired, kind/reparse/id checked -> PINNED
PINNED -- copy walk == X, exposures absent, topology rules, pin ids, I_c -> PROVEN
PROVEN -- L bound, S dropped --------------------------------------> BOUND
BOUND -- L14 precondition (incl. topology re-proof) + reprove(L) -> REPROVED
REPROVED -- launch() ----------------------------------------------> LAUNCHED
LAUNCHED -- L21 / L21A (unchanged) --------------------------------> OBSERVED
{any state with pins} -- L27 entry --------------------------------> RELEASED
RELEASED -- frozen L27 removal ------------------------------------> REMOVED | RESIDUAL
any of ADMITTED..PROVEN -- failure -------------------------------> L3R refusal
                                                                     (nothing deleted; ledger closed
                                                                     in L3R's finally; L27 as above)
```

Partial failure never causes AIDO to delete a resource it did not create: L3R
deletes nothing — by pathname **or** by handle disposition — and the only removal
is L27's frozen namespace teardown of the minted root. Every construction pin and
zero-byte child handle is in the §7.4A.5 ledger, closed exactly once before L27's
re-proof and removal; a close failure is lifecycle-significant, sets
`live_references_released` `False` (§7.8.1) and never causes a path-based cleanup.

### 15.2 Selection authority — answers

| Question | Answer |
|---|---|
| Who creates the runtime? | The executor at L3R, through the provisioning port, inside the run's own minted root, after re-proving it. |
| When relative to L1? | After L1, L2 and L3; before L4. |
| Registry / ownership record? | None persistent. Namespace authority is the frozen mint registry; the provision object is executor-local. No object authority over any target is needed. |
| How is the root chosen without PATH? | `C = R\pi_runtime\pi-coding-agent`, a constant under the verified `R`. |
| Must P0's "read PATH only" rule change? | **No.** |
| Can an untrusted caller select another installation? | No: no parameter names a root; `L` is sentinel-constructed after post-pin validation; L14 requires the provision bound to this workspace nonce and `state.pi_identity is provision.launch_identity`. |
| What if the copy is altered after validation? | Before L14: refused by the L14 precondition or the frozen re-proof. After L14: inherited R-SLIVER/R-ABA (§8.6); persistent content change → L21A `CHANGED`/`UNPROVEN`. |
| How do L14 and L21A bind to the same object? | To the L3R-provisioned `C` (`I_c`), to L1's `X` by equality, and to `I_n` from L1. |

---

## 16. Implementation scope (future phase "F5A-IMPL", not authorized here)

| File | Change |
|---|---|
| `experiments/pi_harness_cfg1/pi_runtime_provision.py` (new) | topology constants and checks (T-NM, T-CANON, T-PLAIN, T-BUN, T-RT), LDT, the pinned-parent constructor (§7.4A) with its **own** provisioning-only provenance and handle ledger, the verify-before-persist byte path (§7.4B), read-only final pins, provision object, release. It reuses `pi_payload`/`pi_fs_leaves` reads and the established low-level Win32 *semantics*; it must **not** mint or accept any `win_config_authority` mint-backed type (config issuance, generation interval, retained authority, extension issuance). `win_config_authority.py` itself is **not** modified |
| `experiments/pi_harness_cfg1/pi_identity.py` | one read-only sentinel function binding `L` from `S` and a post-pin-validated copy; no write, no new writer import |
| `experiments/pi_harness_cfg1/run_executor.py` | `L3R` step + port (`provision_runtime`) in `Cfg1RunPorts`/`default_cfg1_run_ports`; L14 precondition; L27 entry release; **replace the unconditional `live_references_released=True` with the derived fact of §7.8.1** |
| `experiments/pi_harness_cfg1/records.py` (+ `lifecycle.py` for `REFUSAL_STEPS_V3`) | v3-only vocabulary, R3-S15 |
| `experiments/pi_harness_cfg1/tests/…` | T-F5A-01…33; a separate P-R1 evidence module covering P-R1-1…4 (the existing F5A probe module stays untouched) |

Out of scope: AR2, `environment.py`, `pi_manifest.py`, HPP loader/policy/APS,
candidates, P0–P2R, the gate, v1/v2 records, `CLAUDE.md`, roadmap, the F5
exploratory test, the F5A probe module.

---

## 17. E5 authorization conditions

E5 (the first full Pi CLI launch) may be **considered** only when all hold; this
document authorizes none of them:

1. This amendment (R1) is accepted by independent review, including decisions
   D-F5A-1…D-F5A-10 (§19).
2. F5A-IMPL is separately authorized, implemented within §16, and accepted.
3. P-R1-1…4 are established on the target platform and accepted as evidence.
3a. **`U126_READ_UNPROVEN` is empty**: approved bytes for the 57 files of §8.10.5
   have been recovered and statically reviewed, every read / path-derivation
   route is classed B, C, D or E with its evidence, and the Appendix U126
   table has no `UNPROVEN` row (T-F5A-31). *(Established by §8.10.8, subject to
   independent acceptance of that evidence under D-F5A-9.)*
4. The LDT entry for `56651d0b…` (§7.3) is accepted as a reviewed static
   derivation over the approved bytes.
5. The full offline suite is green with the standard deselection.
6. The F5-B exploratory regression test has had its own byte review and
   disposition.
7. F5-C is recorded as an accepted residual (§4) and has not been reopened.
8. A separately reviewed live authorization binds the exact APS head and source
   commit per PE-1 §24; E5, E6 and PE-6 remain unauthorized until then.
9. An installation whose payload equals the approved profile is present as the
   L1 byte source; the ambient installation observed in §1.2 is not.

**F5-A is not closed by this document.**

---

## 18. Adversarial review of R1

| # | Counterexample | Outcome | Caught at |
|---|---|---|---|
| 1 | attacker-controlled first `pi.cmd` on ambient PATH | its tree is only a byte source: unapproved bytes → L1 refuses; approved bytes → copied into `C`; Pi never runs from it | L1 / L3R |
| 2 | byte-identical but non-AIDO installation | acceptable as a source; never a launch root | L3R step 9, L14 |
| 3 | scratch boundary or temp ancestry contains `node_modules` | T-NM refuses before any write | L3R step 2 |
| 4 | ancestry contains a junction / symlink / other reparse component | T-PLAIN refuses (availability only) | L3R, L14 |
| 5 | SUBST / mapped drive hiding a `node_modules` component | AIDO's realpath'd `R` exposes it → refuse; Node keeps the drive letter, which can only remove components | L3R |
| 6 | `C` path containing a Bun marker | T-BUN refuses | L3R |
| 7 | `PI_PACKAGE_DIR` / `PI_MANAGED_INSTALL_ROOT` / `NODE_OPTIONS` injected | not in the positive allowlist | L12 (T-4) |
| 8 | substitute planted in the creator→pin gap | id / kind / reparse check at the pin, or content walk | L3R step 8 |
| 9 | `RT\agent\dist\index.js` (loader workspace probe) planted | before L14: T-RT refuses; after: R-EXT-2/R-SLIVER, and CFG1's extension never imports the aliased packages | L3R, L14 |
| 10 | exposure package planted under `RT\node_modules`, `R\node_modules` or a temp ancestor | T-RT / exposure observer refuses | L3R, L14 |
| 11 | ancestor renamed and a junction aliasing `C` under a `node_modules` path planted | blocked while pins are held (P-R1-2); before L14 also refused by T-PLAIN; any residual is inherited (§8.6) | pins, L14 |
| 12 | `config.js` / `main.js` / `cli.js` reparse-converted after L14 | inherited R-SLIVER/R-ABA: equivalent to arbitrary post-proof code (§8.6) | — (inherited) |
| 13 | same, before L14 | T-PLAIN refuses | L14 precondition |
| 14 | `C\package.json` deleted or `C\dist\package.json` planted | cannot create a target (§8.4); `package.json` held; content change caught by the L14 walk | §8.4, L14 |
| 15 | other payload content replaced after L14 | R-SLIVER/R-ABA; persistent change → L21A `CHANGED`/`UNPROVEN` | L21A |
| 16 | undeclared dependency satisfied only by the shared npm prefix | frozen PE-4A §6.3 finds only three optional literal requires resolving outside the payload; anything else (non-literal / dynamic) fails to resolve from `C`: E5 availability failure, fail closed, no target | E5 (R-E5-COMPAT, narrowed) |
| 17 | a future approved profile with a different cleanup derivation | no LDT entry → refuse | L3R |
| 18 | partial provisioning | L3R refusal; nothing deleted by L3R; L27 namespace teardown | L3R, L27 |
| 19 | two authority objects for different installs (`S` vs `L`; `L` of another run) | `S` dropped at L3R; L14 requires identity and workspace-nonce binding | L3R, L14 |
| 20 | concurrent AIDO runs | separate roots and copies; nothing shared | by construction |
| 21 | AIDO's own L27 deletes something it did not create | only via the frozen namespace authority over the minted root; no redirect followed | L27 (frozen, Q6) |
| 22 | a destination parent is renamed, replaced or junction-converted after an earlier pathname check and before a later child create (the R1 flaw) | the parent is held under a share-`READ` pin from before its first child to after its last; rename / delete / in-place conversion are refused (W2, W3, W5, W6); no existing component of any create path is un-held; zero objects or bytes outside `R` | §7.4A.3, T-F5A-25 |
| 23 | a foreign name is planted in a directory AIDO is populating | the exact-set parentage gate refuses before any content byte of that directory or below | §7.4A.2 step 3, T-F5A-26 |
| 24 | an ordinary directory is substituted between `CreateDirectoryW` and its first pin | accepted R-WINDOW: it is still a pinned-parent entry beneath `R`, empty-or-refused, and **no content byte exists in the window**; no write leaves `R` | §7.4A.4 |
| 25 | a source ancestor is redirected after the source observation so a later open reaches a foreign file with different (secret) bytes | read into bounded transient memory only; digest ≠ approved → refuse; **zero** foreign bytes written under `R`, none in diagnostics; nothing stranded if L27 then fails | §7.4B, T-F5A-28/29 |
| 26 | a construction pin, zero-byte child handle or final pin fails to close | refuses L3R (construction) or fails L27 by construction; degrades lifecycle evidence (`INDETERMINATE_LIFECYCLE`); **`live_references_released` becomes `False` and stays `False`**, so L30 fails closed; no retry / force / path-based cleanup / retention registry | §7.4A.5, §7.8.1, T-F5A-30, T-F5A-33 |
| 27 | provisioning authority is mistaken for, or used to mint, config / extension issuance authority | own provisioning-only provenance; no mint-backed type produced or accepted; `win_config_authority.py` unmodified | §7.4A.5, T-F5A-24 |
| 28 | one of the 126 unavailable files performs a location-sensitive **read** (module / package location → derived path → host state → prompt, provider/model choice, request, configuration, authority, backend-visible data or diagnostic) | excluded: frozen evidence establishes A or B for 69; the recovered and verified approved bytes of the other 57 were reviewed (B 5, C 42, D 10) and show no relocation-induced read difference. *(Was: not excluded for 57 files; HOLD.)* Awaiting independent acceptance | §8.10.8, T-F5A-31 |
| 29 | the unavailable set changes (another installation, another mismatch) and a new file is unclassified | the static table's digest and per-class checks fail | T-F5A-31 |

No case was found in which **genuine** approved code, launched under R1 on the
topology proven at L14, derives a quarantine target at all.

---

## 19. Reviewer decisions requested

| Id | Decision |
|---|---|
| D-F5A-1 | Accept A2-R1 (run-provisioned copy with no `node_modules` ancestor; target nonexistence) and the rejection of A2-R0 and E1 on the measured Q2/Q3 evidence (§5, §6). |
| D-F5A-2 | Accept the v3-only vocabulary extension `L3R` / `RUNTIME_PROVISIONING_FAILED` / R3-S15 and the naming rationale (§11.1). |
| D-F5A-3 | Accept a CFG1-owned, profile-id-keyed Launch Derivation Table with rule `NO_NODE_MODULES_ANCESTOR_MEANS_NO_TARGET`, failing closed for unlisted profiles (§7.3). |
| D-F5A-4 | Acknowledge the PE-4A F-4 characterization delta (per-run documentation paths, no operator npm path) as non-CC1 (§8.9). |
| D-F5A-5 | Accept that post-proof file→reparse conversion and post-proof chain aliasing are inherited within R-SLIVER/R-ABA (§8.6), and that the read-only pins are stability pins on which INV-F5A-R1 does not depend (§7.6). |
| D-F5A-6 | Accept INV-F5A-W and the continuously pinned, parentage-gated destination construction with its own non-transferable provisioning provenance and handle ledger (§7.4A), including the restated R-WINDOW (§7.4A.4), the 462-handle bound under the stated accounting, and the added premise P-R1-4 (§14). |
| D-F5A-7 | Accept INV-F5A-S and verify-before-persist per file with bounded in-memory verification as the specified shape, option B as a permitted alternative, and R-SRC-MEM as a stated residual (§7.4B). |
| D-F5A-8 | **`cleanupManagedInstall()` startup call: ACCEPTED BY INDEPENDENT REVIEW.** Basis: the approved-byte-bound R0 source derivation (the startup call and its `PI_MANAGED_INSTALL_ROOT` gate) plus the frozen T-4 positive child-environment allowlist, which never includes that variable (§8.10.7 item 3). This document does not claim PE-4A recorded the call. |
| D-F5A-9 | Accept the corrected read-relocation criterion A–E (§8.10.1), the evidence inventory of §8.10.3, the exclusion of 69 files (§8.10.4), the 57-file set as submitted (§8.10.5) **and its resolution in §8.10.8**: approved bytes for exactly those 57 recovered with 57/57 exact inventory equality, a bounded static review classing each B, C or D, and a now-**empty** `U126_READ_UNPROVEN`. Acceptance lifts the HOLD of §8.10.6; rejection of any row of (9) keeps it. |
| D-F5A-10 | Accept `live_references_released` as a derived, latched fact (§7.8.1, §11.7, T-F5A-33): `True` iff every executor-owned reference — every RPR construction pin, construction child handle and final pin included — is proven released; any release failure makes it `False` for the run; the L30 check is unchanged; no retention registry, retry or adoption. |

*Independent-review status after R1-FU1:* **D-F5A-1 … D-F5A-7 ACCEPTED IN PRINCIPLE** (A2-R1 topology and target nonexistence; v3-only `L3R` vocabulary; profile-id-keyed LDT; docs-path characterization; post-proof reparse conversion as inherited R-SLIVER/R-ABA; INV-F5A-W; INV-F5A-S). R1-FU1 stayed HOLD for exactly two corrections, made here as D-F5A-9 and D-F5A-10.

---

## Appendix U126 — the 126 unavailable approved files (read-relocation basis table)

Paths are payload-relative, from the committed approved inventory. Each row is
`<basis> <path>`. **Basis** is the §8.10.1 element that frozen evidence
establishes for the file: `A` (not loaded) or `B` (invocation closed by a
location-independent frozen gate), with the evidence in §8.10.4; or `UNPROVEN`
(`U126_READ_UNPROVEN`, §8.10.5 — frozen evidence establishes none of A–E).
Rows are now `<basis>/<evidence> <path>`: evidence `F` is frozen evidence
(§8.10.4) and `R` is the §8.10.8 recovered-byte review. The 57 rows that were
`UNPROVEN` at submission are now `B/R`, `C/R` or `D/R`; **no `UNPROVEN` row
remains**, and `E` is unused. Rows already `A` or `B` keep their text and their
digests; an **unsuffixed** `A` / `B` row is evidence class `F`. Sorted-path SHA-256 of each set:

```text
A         54   c24e9e60992d3a03a2accd8dbfd35eebe4559ba108ce0cde51447f65f32f6f7c
B (F)     15   a03d99ba4d805b0303ae816b0a910b4a954cd64a02be0bb060c293894c08b23c
B (R)      5   eea3a75a366ebe6abb98e9c4f96af0ed4c6addb9fe80f25a3174f06d7d587005
C (R)     42   7f47a89245f670553fe7bbaf4dd7338af46771b2af090415a32df007eaccd121
D (R)     10   34e755cbb37b23c971832d4cd5e8e38d87a8dd6ef8746b001ea30666e5bf6d6c
UNPROVEN   0   (empty)
(historic: the 57 as submitted: e55241b9a056a27d5ea4a10905edba4149c02bfc7d362b42bbef59e36369033a)
U126      126  775a8f9d1d02ffdd9f31c518bbad88c8727df381d80abe1f8f67fac27d6e3dba
```

Membership of `U126` itself: the 4 858 `.js/.mjs/.cjs` inventory entries whose
installed bytes at the authoring instant were absent or did not equal the
approved SHA-256 (92 differ, 34 absent). It is an environment fact about one
machine, not a property of the profile; T-F5A-31 fails if the set changes
without a basis being assigned, and fails while any row is `UNPROVEN`.

```text
C/R       dist/cli/args.js
D/R       dist/core/agent-session.js
C/R       dist/core/bash-executor.js
C/R       dist/core/export-html/tool-renderer.js
D/R       dist/core/model-runtime.js
C/R       dist/core/nested-tool-calls.js
D/R       dist/core/resource-loader.js
D/R       dist/core/sdk.js
D/R       dist/core/settings-manager.js
D/R       dist/core/system-prompt.js
B/R       dist/core/tools/read.js
C/R       dist/core/tools/renderers/bash.js
C/R       dist/core/tools/renderers/edit.js
B/R       dist/extensions/codemode/execute.js
C/R       dist/extensions/codemode/index.js
D/R       dist/extensions/codemode/tool.js
C/R       dist/extensions/llama/provider.js
B/R       dist/extensions/mcp/cli.js
B/R       dist/extensions/mcp/index.js
C/R       dist/extensions/mcp/resources.js
B/R       dist/extensions/mcp/runtime.js
C/R       dist/extensions/mcp/tools.js
C/R       dist/extensions/mcp/ui.js
D/R       dist/main.js
C/R       dist/modes/interactive/components/bash-execution.js
C/R       dist/modes/interactive/components/branch-summary-message.js
C/R       dist/modes/interactive/components/compaction-summary-message.js
C/R       dist/modes/interactive/components/custom-entry.js
C/R       dist/modes/interactive/components/custom-message.js
C/R       dist/modes/interactive/components/settings-selector.js
C/R       dist/modes/interactive/components/skill-invocation-message.js
C/R       dist/modes/interactive/components/tool-execution.js
D/R       dist/modes/interactive/theme/theme.js
C/R       dist/utils/ansi.js
C/R       dist/utils/image-resize-core.js
D/R       dist/utils/syntax-highlight.js
C/R       node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js
C/R       node_modules/@earendil-works/pi-ai/dist/api/cloudflare-workers-ai-system-one.js
C/R       node_modules/@earendil-works/pi-ai/dist/api/lazy.js
C/R       node_modules/@earendil-works/pi-ai/dist/api/llama-cpp-classify.js
C/R       node_modules/@earendil-works/pi-ai/dist/api/mistral-conversations.js
C/R       node_modules/@earendil-works/pi-ai/dist/api/system-one-shared.js
C/R       node_modules/@earendil-works/pi-ai/dist/api/typesafe-system-one.js
C/R       node_modules/@earendil-works/pi-ai/dist/models.js
C/R       node_modules/@earendil-works/pi-ai/dist/providers/faux.js
C/R       node_modules/@earendil-works/pi-ai/dist/providers/openai.js
C/R       node_modules/@earendil-works/pi-ai/dist/providers/radius.js
C/R       node_modules/@earendil-works/pi-ai/dist/utils/estimate.js
C/R       node_modules/@earendil-works/pi-ai/dist/utils/event-stream.js
C/R       node_modules/@earendil-works/pi-ai/dist/utils/model-operations.js
C/R       node_modules/@earendil-works/pi-ai/dist/utils/provider-retry.js
C/R       node_modules/@earendil-works/pi-ai/dist/utils/retry.js
C/R       node_modules/@earendil-works/pi-mcp/dist/oauth/flow.js
C/R       node_modules/@earendil-works/pi-tui/dist/components/box.js
C/R       node_modules/@earendil-works/pi-tui/dist/components/text.js
C/R       node_modules/@earendil-works/pi-tui/dist/index.js
C/R       node_modules/@earendil-works/pi-tui/dist/tui-alt-screen.js
B         dist/core/mcp-servers.js
B         dist/core/skills.js
B         dist/extensions/mcp/oauth.js
B         dist/modes/interactive/interactive-mode.js
B         dist/package-manager-cli.js
B         dist/utils/clipboard.js
B         dist/utils/image-resize.js
B         node_modules/@earendil-works/pi-agent-core/dist/proxy.js
B         node_modules/@earendil-works/pi-ai/dist/api/openai-codex-responses.js
B         node_modules/@earendil-works/pi-codemode/dist/runtime/host.js
B         node_modules/@earendil-works/pi-codemode/dist/runtime/prelude-source.js
B         node_modules/@earendil-works/pi-mcp/dist/oauth/discovery.js
B         node_modules/@earendil-works/pi-mcp/dist/transports/streamable-http.js
B         node_modules/@earendil-works/pi-tui/dist/terminal-image.js
B         node_modules/@earendil-works/pi-tui/dist/terminal.js
A         dist/bundle/chunks/anthropic-messages-Y22YDKSW.js
A         dist/bundle/chunks/anthropic.js
A         dist/bundle/chunks/azure-openai-responses-YJDJIIDQ.js
A         dist/bundle/chunks/bedrock-converse-stream.js
A         dist/bundle/chunks/chunk-2VBQLN7Y.js
A         dist/bundle/chunks/chunk-6DBOMCBS.js
A         dist/bundle/chunks/chunk-7TP2J6F2.js
A         dist/bundle/chunks/chunk-A3JYRWB6.js
A         dist/bundle/chunks/chunk-AXOERKKW.js
A         dist/bundle/chunks/chunk-BFNE7BHG.js
A         dist/bundle/chunks/chunk-C47CLQZK.js
A         dist/bundle/chunks/chunk-HQHD6PZI.js
A         dist/bundle/chunks/chunk-J52J6TFP.js
A         dist/bundle/chunks/chunk-KJUDFE6Y.js
A         dist/bundle/chunks/chunk-LD2P6SFZ.js
A         dist/bundle/chunks/chunk-PSQJVYXD.js
A         dist/bundle/chunks/chunk-TAOL3JFA.js
A         dist/bundle/chunks/chunk-UBHCV62G.js
A         dist/bundle/chunks/chunk-WE4MXUQS.js
A         dist/bundle/chunks/chunk-ZSQEXT6X.js
A         dist/bundle/chunks/cli-HTJP6F6Z.js
A         dist/bundle/chunks/cloudflare-workers-ai-system-one-NM3JRRWQ.js
A         dist/bundle/chunks/codemode-worker.js
A         dist/bundle/chunks/easter-egg-3d-6YCNESG3.js
A         dist/bundle/chunks/execute-JRUOLYDA.js
A         dist/bundle/chunks/github-copilot.js
A         dist/bundle/chunks/google-generative-ai-XMFHGQC5.js
A         dist/bundle/chunks/google-vertex-4XRRNP74.js
A         dist/bundle/chunks/image-resize-worker.js
A         dist/bundle/chunks/llama-cpp-classify-XT44PI3C.js
A         dist/bundle/chunks/mistral-conversations-Q22M3IBG.js
A         dist/bundle/chunks/openai-chatgpt.js
A         dist/bundle/chunks/openai-codex-responses-4MYQSO5E.js
A         dist/bundle/chunks/openai-codex.js
A         dist/bundle/chunks/openai-completions-OSRCWAAA.js
A         dist/bundle/chunks/openai-responses-UHF3DHNG.js
A         dist/bundle/chunks/openrouter-images-ZVXWCSIM.js
A         dist/bundle/chunks/pi-messages-TM5SOOIW.js
A         dist/bundle/chunks/runtime-NW7GPWKS.js
A         dist/bundle/chunks/typesafe-system-one-PRR5K6CI.js
A         dist/bundle/chunks/virtual-modules-CFHJO5SY.js
A         dist/bundle/cli-runtime.js
A         dist/bundle/index.js
A         dist/bundle/rpc-entry.js
A         dist/utils/image-resize-worker.js
A         node_modules/@babel/runtime/helpers/esm/interopRequireWildcard.js
A         node_modules/@babel/runtime/helpers/esm/toPrimitive.js
A         node_modules/@babel/runtime/helpers/interopRequireWildcard.js
A         node_modules/@babel/runtime/helpers/toPrimitive.js
A         node_modules/@earendil-works/pi-ai/dist/api/bedrock-converse-stream.js
A         node_modules/@earendil-works/pi-ai/dist/auth/oauth/anthropic.js
A         node_modules/@earendil-works/pi-ai/dist/auth/oauth/openai-chatgpt.js
A         node_modules/@earendil-works/pi-ai/dist/auth/oauth/openai-codex.js
A         node_modules/@earendil-works/pi-codemode/dist/runtime/worker.js
```

---

## Status

```text
5F3B-CFG1-F5A-LIVE-LAUNCH-AUTHORITY-AMENDMENT   R1-FU2 + U126 BYTE REVIEW (§8.10.8)
HOLD:       as submitted, U126_READ_UNPROVEN was NON-EMPTY (57 files, §8.10.5).
            ADDENDUM (§8.10.8): approved bytes for exactly those 57 were recovered
            from the public registry (data only; 57/57 equal to the committed PE-5
            inventory by path, size and SHA-256; 2367/2367 tarball members equal,
            0 mismatches) and statically reviewed: B 5, C 42, D 10, E 0.
            U126_READ_UNPROVEN = EMPTY. No relocation-induced read, host-state,
            privacy or authority difference was found. This is NEW evidence, not yet
            independently reviewed: the HOLD is lifted only if D-F5A-9 is accepted.
            The recovery is NOT a complete approved installation (12679 of 15046
            approved files are not in the five tarballs; no E5 source exists).
Chosen:     A2-R1 run-provisioned Pi runtime at R\pi_runtime\pi-coding-agent (L3R);
            no node_modules component anywhere above the package root => no quarantine
            target; read-only post-population pins; LDT rule
            NO_NODE_MODULES_ANCESTOR_MEANS_NO_TARGET
R1-FU1:     INV-F5A-W (continuously pinned, parentage-gated destination, §7.4A) and
            INV-F5A-S (verify-before-persist, §7.4B) - ACCEPTED IN PRINCIPLE
R1-FU2:     (A) read-relocation criterion corrected (A-E); "a read is not a side effect"
                withdrawn; result HOLD (§8.10)
            (B) live_references_released is a derived, latched fact: True iff every
                executor-owned reference (RPR construction pins, construction child
                handles, final pins included) is proven released; any release failure
                => False => L30 fails closed (§7.8.1, §11.7, T-F5A-33)
            (C) cleanupManagedInstall: ACCEPTED BY INDEPENDENT REVIEW (approved-byte-bound
                R0 derivation + frozen T-4 allowlist); PE-4A is not claimed to record it
Rejected:   A2-R0 (held occupant; Q2/Q3 FAIL, Q4 FAIL for its pin shape), A1, B, C, D,
            E1 (same Q2 defect), E2-E5
Invariants: INV-F5A-R1; INV-F5A-W; INV-F5A-S
Amends:     v3 refusal vocabulary (+L3R, +RUNTIME_PROVISIONING_FAILED, R3-S15);
            executor step table (+L3R); L14 executor precondition; launch root for
            L14/L21A; identity construction path (no new slot); CFG1 §17/§18 rows;
            executor outcome fact live_references_released (derived, §11.7)
Unchanged:  P0-P2R, gate, L1, L14/L21A proof code, AR2, T-4/env builder, pi_manifest,
            HPP/APS/profiles, v1/v2, PE-3/4/5 evidence, CLAUDE.md, both untracked tests,
            win_config_authority.py, A2-R1 topology, INV-F5A-R1/-W/-S, LDT rule, L3R,
            D-F5A-1..7, F5-B, F5-C, R-SLIVER/R-ABA, R-SRC-MEM
Evidence:   Q1 PASS, Q2 FAIL, Q3 FAIL (ancestor-rename sub-premise PASS),
            Q4 FAIL for R0 (read-only control compatible), Q5 PASS, Q6 PASS;
            still needed: P-R1-1..3 (as specified) and P-R1-4 (construction shape)
Reviewer:   D-F5A-1..7 accepted in principle; D-F5A-8 accepted; D-F5A-9, D-F5A-10 pending
F-5/F5-A:   OPEN (closure proposed, not claimed)
F5-B:       CLOSED by existing mechanical authority
F5-C:       ACCEPTED RESIDUAL (confirmed, not reopened)
E5 / E6 / PE-6:  NOT AUTHORIZED
F5A-IMPL:        NOT AUTHORIZED
```
