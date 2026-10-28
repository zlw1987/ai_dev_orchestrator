# DL-4B E-12 — Pass / Fail Evidence Matrix

**Status: PREPARATION ONLY — all rows start NOT TESTED.** Fill in during a
separately authorized E-12 (see `DL4B_E12_ISOLATION_REHEARSAL_PREP.md` §9–§10).

Every row has one of three states: **PASS** (the mechanical check met its
stated expectation), **FAIL** (it did not — any FAIL blocks the Alpha, E-10),
or **NOT TESTED** (not exercised in this run, with the reason given). A row with
no evidence recorded is NOT TESTED by default.

Legend for "Reason if NOT TESTED": `no-model` = unreachable because E-12 runs no
model; `offline` = covered by the offline suite instead; `optional` = a
recommended spot-check that may be skipped.

---

## 1. Preconditions

| Id | Check | Expected | Evidence source | State |
|---|---|---|---|---|
| `PRECOND-POLICY` | Host policy permits local standard accounts, (if S4U) batch-logon, user switching (D-17) | permitted | admin confirmation | NOT TESTED |
| `PRECOND-SUITE` | Full offline suite green at baseline `c7f9e64` (E-3) | all pass | `pytest -q` | NOT TESTED |
| `PRECOND-REVIEW` | S0–S7 independently accepted (E-2/E-3) | accepted | review record | NOT TESTED |

## 2. FD-13 — identities and launch

| Id | Check | Expected | Evidence | State / Reason |
|---|---|---|---|---|
| `FD13-SIDS` | A, X-R, O have three distinct SIDs | distinct | `whoami /user` per session | NOT TESTED |
| `FD13-GROUPS` | None in `Administrators`/`Backup Operators`; no shared group | none | `whoami /groups`, `net localgroup` | NOT TESTED |
| `FD13-SESSIONS` | Each identity in its own logon session / desktop | separate | `query session`, `whoami /logonid` | NOT TESTED |
| `FD13-LAUNCH` | A launched via `-I` (interactive or S4U); dropping `-I` refuses | `interpreter_not_isolated` when `-I` absent | driver refusal | NOT TESTED |
| `FD13-NOCROSS` | No `runas`/`-Credential` cross-desktop launch used | not used | operator attestation | NOT TESTED |

## 3. FD-14 — access rights (OS-enforced)

| Id | Check | Expected | Evidence | State / Reason |
|---|---|---|---|---|
| `FD14-STATEROOT-ACL` | State root / `published/` / `inbox/` / handoff DACLs per prep §3.1 | as table | `icacls` dump | NOT TESTED |
| `FD14-OUTBOX-OWNERRIGHTS` | Outbox `OWNER RIGHTS` caps A to list/read; X-R add/write/delete own | as table | `icacls` dump | NOT TESTED |
| `FD14-CLONE-ACL` | Working tree X-R-modify + `OWNER RIGHTS`; `.git` X-R read+execute only; root no DELETE/`WRITE_DAC`/`WRITE_OWNER` | as table | `icacls` dump | NOT TESTED |
| `FD14-EFFECTIVE` | AuthZ effective rights for X-R's SID within the table for every object | within table | AuthZ spot check | NOT TESTED |
| `FD14-HOSTILE-DENIED` | Every hostile write/delete/rename/chown/re-permission on every FD-14 object fails `ACCESS_DENIED` | all denied (5) | hostile log (diagnostic) + `ISO-DIGEST-POST` | NOT TESTED |
| `FD14-PROC-DENIED` | Hostile `OpenProcess`/token open on A denied | denied | hostile log | NOT TESTED |
| `FD14-LOADPATH-DENIED` | Hostile writes to A's install / `sys.path` / `PATH` dirs denied | denied | hostile log + `ISO-DIGEST-POST` | NOT TESTED |

## 4. FD-16 — mechanical re-proof

| Id | Check | Expected | Evidence | State / Reason |
|---|---|---|---|---|
| `ISO-PROOF-PRE` | FD-16 proof passes before the rehearsal | exit 0, no `isolation_unproven` | `driver-001-status.json` | NOT TESTED |
| `ISO-PROOF-POST` | FD-16 proof passes **after** the adversary ran | exit 0, no `isolation_unproven` | `driver-099-status.json` | NOT TESTED |
| `FD16-ANCHORS` | Registry + `identity-boundary.v1` at constant paths, anchor checks pass | pass | proof result | NOT TESTED |
| `FD16-NEG` | One induced violation yields the exact category | `isolation_unproven:object_unprotected` (or `object_rights`), exit 1 | induced ACE + re-run | NOT TESTED |
| `FD16-ENV` | A's environment holds no `AIDO_LITELLM_*`/`AIDO_VLLM_*`/`GITHUB_TOKEN`/`PYTHON*` | absent | proof passes | NOT TESTED |

> Note: the full set of FD-16 categories
> (`src/ai_dev_orchestrator/integration/identity_boundary.py` `IsolationCategory`)
> is asserted **offline** (S0 suite). E-12 confirms the live positive and one
> induced negative; the rest are `offline`.

## 5. FD-17 — claim protocol

| Id | Check | Expected | Evidence | State / Reason |
|---|---|---|---|---|
| `FD17-VALID` | The write X-step delivers exactly `stdout.json`+`complete`, X-R-owned, 1 link, no reparse, within `MAX_WRITE_CLAIM_BYTES` (4 MiB) | received | M1 recorded; `IMPLEMENTATION_RETURNED` | NOT TESTED |
| `FD17-UNEXPECTED` | Extra file in outbox refuses | `claim_refused:unexpected_entry` | disposable-outbox spot check | NOT TESTED / optional |
| `FD17-REPARSE` | Junction as `stdout.json` refuses | `claim_refused:reparse_point` | spot check | NOT TESTED / optional |
| `FD17-DEADLINE` | No `complete` within 7200 s → RECOVERY_REQUIRED | deadline refusal | (long; usually `offline`) | NOT TESTED / offline |
| `FD17-WAIT-CONST` | `CLAIM_WAIT_SECONDS` = 7200 confirmed in announcement `a_waits_seconds` | 7200 | `driver-012-run.json` | NOT TESTED |

> All other FD-17 deviations (missing marker, hard link, oversize, wrong owner,
> sharing violation, pre-existing directory, second claim, late claim) are
> `offline` (S3/S4 suite).

## 6. FD-18 — authority observation

| Id | Check | Expected | Evidence | State / Reason |
|---|---|---|---|---|
| `FD18-M0` | M0 = pre-image, HEAD = `base_head_oid`, `.git` digest = activation-time | holds | bundle/`published/` observations | NOT TESTED |
| `FD18-M1` | M1 − M0 = exactly the target (post-image); `.git` unchanged | holds | observation blobs | NOT TESTED |
| `FD18-GIT-UNCHANGED` | `.git` control digest unchanged across the whole rehearsal | unchanged | `ISO-DIGEST-PRE`/`-POST` | NOT TESTED |
| `FD18-REPARSE` | Planted junction in tree refuses | `ObservationError:reparse_point` | spot check | NOT TESTED / optional |
| `FD18-M2` | M2 (post-review observation) | — | — | NOT TESTED / no-model |

## 7. ISO — the §5.8.10 pass test

| Id | Check | Expected | Evidence | State / Reason |
|---|---|---|---|---|
| `ISO-DIGEST-PRE` | A's pre-rehearsal manifest of state root + `.git` control | recorded | `digest-pre.txt` | NOT TESTED |
| `ISO-DIGEST-POST` | Post-rehearsal manifest **identical** to pre | no diff | `fc` output | NOT TESTED |
| `ISO-PUBLISHED-UNCHANGED` | Every `published/` bundle byte unchanged | unchanged | digest diff | NOT TESTED |
| `ISO-OVERALL` | `ISO-PROOF-POST` PASS **and** `ISO-DIGEST-POST` PASS **and** `FD18-GIT-UNCHANGED` PASS | all PASS | the three above | NOT TESTED |

## 8. HARNESS — detached HEAD + read-only `.git`

| Id | Check | Expected | Evidence | State / Reason |
|---|---|---|---|---|
| `HARNESS-OWNER` | X-R owns the clone (C-10) | owned | `icacls` / Git ownership check | NOT TESTED |
| `HARNESS-WRITE-DETACHED` | Frozen writer accepts detached HEAD + read-only `.git` and writes | accepted, written | writer stdout + working-tree change | NOT TESTED |
| `HARNESS-VERIFY-DETACHED` | Frozen verifier preflight accepts detached HEAD + read-only `.git` | accepted | verifier stdout (from X1/X5) | NOT TESTED |

## 9. S7 — driver integration measurements

| Id | Check | Expected | Evidence | State / Reason |
|---|---|---|---|---|
| `S7-DURATION` | Per-invocation FD-16 re-proof wall time measured (esp. a hold-stage `status`) | recorded | `Measure-Command` | NOT TESTED |
| `S7-LOCK` | A second A invocation during the long `run` is refused | `StoreLockedError` | second-console output | NOT TESTED |
| `S7-ANNOUNCE-WRITE` | Write announcement readable in `published/` **before** `run` returns | visible live | O reading `driver-012-run.json` | NOT TESTED |
| `S7-ANNOUNCE-VERIFY` | Verify announcement readable before `run` returns | visible live | O reading the growing file | NOT TESTED |
| `S7-STREAM-SEPARATION` | The single `run` stdout file holds multiple JSON docs split on blank line; documentation remedy (a) is sufficient on the host (F-E12-1) | (a) sufficient | O's read experience | NOT TESTED |
| `S7-PUBLISHED-ACL` | Every `driver-*.json` created with inherited protected DACL, readable by O, unreachable by X-R | created, readable, X-R denied | `icacls` + O read + hostile log | NOT TESTED |
| `S7-VERIFY-RECOVER` | S7 `run` ends RECOVERY_REQUIRED (bare verify is not a `ReviewPacket`) | exit 3 | `driver-012-run.json` | NOT TESTED / expected |

## 10. Explicitly NOT TESTED by E-12 (covered elsewhere)

| Id | Item | Reason |
|---|---|---|
| `NT-ACCEPT` | ACCEPTANCE / COMPLETE / held planner decision | no-model (needs `verified`+`approve` claim); offline suite covers it |
| `NT-BUNDLE` | Live publication of the acceptance **bundle** to `published/` | no-model; `S7-PUBLISHED-ACL` + offline suite cover the ACL |
| `NT-M2` | M2 observation | no-model (no review X-step reaches it) |
| `NT-E6` | Real-authenticator signing | E-6, separately authorized (see prep §E-6 prerequisites) |
| `NT-FD16-CATS` | FD-16 categories beyond the one induced negative | offline (S0 suite) |
| `NT-FD17-DEVS` | FD-17 deviations beyond the two live spot-checks | offline (S3/S4 suite) |

---

## 11. Overall E-12 verdict (fill at close)

E-12 **PASSES** iff: all §1 preconditions PASS; `ISO-OVERALL` PASS; both
`HARNESS-*-DETACHED` PASS; and no row is FAIL. Any FAIL, or a frozen harness
refusing the detached HEAD or read-only `.git`, **blocks the live Alpha**
(E-10) — no retry, repair or cleanup.

> Overall verdict: **NOT TESTED** (preparation only).
