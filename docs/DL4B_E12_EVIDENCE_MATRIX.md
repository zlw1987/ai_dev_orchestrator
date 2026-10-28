# DL-4B E-12 — Pass / Fail Evidence Matrix

**Status: PREP FU2 — UNDER CORRECTIVE REVIEW, all rows NOT TESTED.** Fill in only
during a separately authorized E-12 (see `DL4B_E12_ISOLATION_REHEARSAL_PREP.md`
§9–§10), after FU2 is accepted. E-12 is NOT authorized or executable; E-6 NOT
PERFORMED; AUTH-PILOT NOT AUTHORIZED. Every PASS below requires a **real
observation** recorded in the stated evidence source; a requirement not
exercised stays `NOT TESTED` with its reason.

Every row has one of three states: **PASS** (the mechanical check met its
stated expectation), **FAIL** (it did not — any FAIL blocks the Alpha, E-10),
or **NOT TESTED** (not exercised in this run, with the reason given). A row with
no evidence recorded is NOT TESTED by default.

Legend for "Reason if NOT TESTED": `no-model` = unreachable because E-12 runs no
model; `no-signing` = S7 row not reached because `PRECOND-SIGNING` (D-E12-9) was
not authorized, so no real approval was signed; `offline` = covered by the
offline suite instead; `optional` = a recommended spot-check that may be skipped.

---

## 1. Preconditions

| Id | Check | Expected | Evidence source | State |
|---|---|---|---|---|
| `PRECOND-POLICY` | Host policy permits local standard accounts, (if S4U) batch-logon, user switching (D-17) | permitted | admin confirmation | NOT TESTED |
| `PRECOND-SUITE` | Full offline suite green at baseline `c7f9e64` (E-3); do not re-run the full suite for the docs-only FU1 | all pass | `pytest -q` | NOT TESTED |
| `PRECOND-REVIEW` | Design+AMEND1 (E-2) and S0–S7 (E-3) accepted — S0–S7 are **ACCEPTED/FROZEN for offline scope**; confirm no code changed since `c7f9e64` | accepted | review record | NOT TESTED |
| `PRECOND-FU2` | E-12 PREP FU2 (these three docs, topology/helper/launch-order/no-signing corrections) independently accepted | accepted | review record | NOT TESTED |
| `PRECOND-ROOTS` | The five boundary paths (`state_root`, `published`, `inbox`, `exchange_root`, active `clone`) are mutually disjoint and load into `identity-boundary.v1` (no nested layout `BoundaryPaths._disjoint` would reject) | disjoint, loads | admin + `status` | NOT TESTED |
| `PRECOND-SIGNING` | D-E12-9: real signing capability provisioned so O signs the three S7 approvals. If not authorized, all §9 S7 rows are `NOT TESTED / no-signing`; ISO and HARNESS are unaffected. **Not E-6, does not satisfy E-6** | provisioned or deferred | admin + O | NOT TESTED |

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
| `FD14-STATEROOT-ACL` | `<state_root>` DACL per prep §3.1: A full; X-R/O none | as table | `icacls` dump | NOT TESTED |
| `FD14-PUBLISHED-ACL` | `<published>` DACL: A full; O read; X-R none | as table | `icacls` dump | NOT TESTED |
| `FD14-INBOX-ACL` | `<inbox>` DACL: A read; O add-file + write own; X-R none | as table | `icacls` dump | NOT TESTED |
| `FD14-EXCHANGE-ACL` | `<exchange_root>` DACL; `handoff-<ticket>` write-once (X-R read only); `outbox-<ticket>` `OWNER RIGHTS` caps A to list/read, X-R add/write/delete own only | as table | `icacls` dump | NOT TESTED |
| `FD14-CLONE-ACL` | Working tree X-R-modify + `OWNER RIGHTS`; `.git` X-R read+execute only; root no DELETE/`WRITE_DAC`/`WRITE_OWNER` | as table | `icacls` dump | NOT TESTED |
| `FD14-EFFECTIVE` | AuthZ effective rights for X-R's SID within the table for every object across the five roots | within table | AuthZ spot check | NOT TESTED |
| `FD14-HOSTILE-DENIED` | Every hostile write/delete/rename/chown/re-permission on every FD-14 object fails `ACCESS_DENIED` | all denied (5) | hostile log (diagnostic) + `ISO-DIGEST-Q`/`-POST` (no unexpected-name object, no rewrite/deletion) + `ISO-ADVERSARY-*` (proof the adversary actually ran) | NOT TESTED |
| `FD14-PROC-DENIED` | Hostile `OpenProcess`/token open on A denied | denied | hostile log | NOT TESTED |
| `FD14-LOADPATH-DENIED` | Hostile writes to A's install / `sys.path` / `PATH` dirs denied | denied | hostile log + `ISO-PROOF-POST` (step 5 re-evaluates X-R rights on every `PATH`/`sys.path` dir) | NOT TESTED |

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
| `ISO-ADVERSARY-LAUNCH` | The hostile verifier **actually launched**: the X2 report has `execution.started == true` and is **not** `refused-before-execution` (a pre-launch refusal is never a launch). Requires the X1 approved write first | launched | `e12_measure.py adversary` on `verify-report.json` (runbook X2/Aadv) | NOT TESTED |
| `ISO-ADVERSARY-ACTIVE` | The detached descendant started and stayed active ≥ the D-E12-8 window; the attack set was attempted | active ≥ window | `adversary` markers (`hostile-start`/`descendant-start`/`descendant-end`) + O `tasklist` + hostile log | NOT TESTED |
| `ISO-DIGEST-PRE` | A's pre-rehearsal manifests: `state_root`, `published`, `inbox`, `exchange_root` (`--exchange`, outbox excluded), `.git` control of `<clone_iso>`, anchors (prep §5.0, runbook §A3) | recorded | `*-pre.txt` (6 manifests) | NOT TESTED |
| `ISO-DIGEST-Q` | **Quiescent bracket** (A idle, only the adversary active): all six manifests `strict`-identical to pre (the literal §5.8.10 test) | all `strict` PASS | `e12_measure.py strict` ×6 (runbook §A3q) | NOT TESTED |
| `ISO-DIGEST-POST` | **Full-window accountable compare**: anchors + `.git` `strict`-identical; each of the four A-owned plane roots `classify`-clean (no write-once rewrite/deletion, no unexpected-name object, no reparse, no hard link) | all PASS | `strict` ×2 + `classify` ×4 (runbook §A6) | NOT TESTED |
| `ISO-PUBLISHED-UNCHANGED` | No `published` object is rewritten/forged by X-R; growth matches only `driver-*.json` (covered by `ISO-DIGEST-POST` published `classify` + `S7-PUBLISHED-ACL`) | expected names only | `classify` + `icacls` | NOT TESTED |
| `ISO-OVERALL` | `ISO-ADVERSARY-LAUNCH`+`-ACTIVE` PASS **and** `ISO-PROOF-POST` PASS **and** `ISO-DIGEST-Q` PASS **and** `ISO-DIGEST-POST` PASS **and** `FD18-GIT-UNCHANGED` PASS. A byte-identical plane with no proven adversary run is **INVALID, not PASS** | all PASS | the rows above | NOT TESTED |

## 8. HARNESS — detached HEAD + read-only `.git`

| Id | Check | Expected | Evidence | State / Reason |
|---|---|---|---|---|
| `HARNESS-OWNER` | X-R owns each clone (C-10) | owned | `icacls` / Git ownership check | NOT TESTED |
| `HARNESS-WRITE-DETACHED` | Frozen writer accepts detached HEAD + read-only `.git` and writes | accepted, written | **standalone** writer run on `<clone_harness>` (runbook Phase 2 X2h); corroborated by ISO X1 and S7 X4 | NOT TESTED |
| `HARNESS-VERIFY-DETACHED` | Frozen verifier accepts detached HEAD + read-only `.git` **end to end to a `verified` outcome** (benign executable, no signing) | `outcome: verified` | **standalone** verifier run on `<clone_harness>` (`harness-verify.json`, runbook Phase 2 X2h); corroborated by ISO X2 preflight | NOT TESTED |

## 9. S7 — driver integration measurements

> **Every S7 row requires `PRECOND-SIGNING` (D-E12-9):** reaching `run`'s write
> and verify steps needs three real, S1-verified approvals. Without it, **skip
> Phase 3 entirely** and record every row below `NOT TESTED / no-signing` — ISO
> and HARNESS have already covered the isolation core and the writer/verifier
> compatibility without signing, so a no-signing run still yields a meaningful
> ISO+HARNESS verdict, and the overall verdict never claims S7 (or HARNESS)
> coverage from an exercise that did not run. Signing is real authenticator use
> in O's session; it is **not** a model call and **not** E-6.

| Id | Check | Expected | Evidence | State / Reason |
|---|---|---|---|---|
| `S7-DURATION` | Per-invocation FD-16 re-proof wall time measured (esp. a hold-stage `status`) | recorded | `echo %TIME%` bracket in `cmd.exe` (runbook §A2) | NOT TESTED |
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
| `NT-E6` | E-6 format-interoperability acceptance (one throwaway signature + induced-negative battery + verdict) | E-6, separately authorized (prep §8). **NOT PERFORMED.** E-12's S7 approval signing under `PRECOND-SIGNING` is operational only and does **not** perform or satisfy E-6 |
| `NT-FD16-CATS` | FD-16 categories beyond the one induced negative | offline (S0 suite) |
| `NT-FD17-DEVS` | FD-17 deviations beyond the two live spot-checks | offline (S3/S4 suite) |

---

## 11. Overall E-12 verdict (fill at close)

E-12 **PASSES** iff: all §1 preconditions PASS (`PRECOND-FU2` and `PRECOND-ROOTS`
included); `ISO-OVERALL` PASS (which requires `ISO-ADVERSARY-LAUNCH` and
`-ACTIVE` — the adversary provably ran — plus `ISO-PROOF-POST`, the quiescent
`ISO-DIGEST-Q`, the full-window `ISO-DIGEST-POST` and `FD18-GIT-UNCHANGED`); both
`HARNESS-*-DETACHED` PASS from the **standalone** `<clone_harness>` run reaching
`verified`; and no row is FAIL. The S7 rows PASS only if `PRECOND-SIGNING` was
met; otherwise they are `NOT TESTED / no-signing` and E-12 still passes on
ISO + HARNESS, with S7 deferred — **the verdict must not claim HARNESS coverage
from an S7 run that did not happen, nor S7 coverage on a no-signing host**
(mandatory validation #9). An ISO run in which the hostile verifier was
`refused-before-execution` (adversary never launched) is **INVALID, not a pass**.
Any FAIL, any measurement `FAIL` line, or a frozen harness refusing the detached
HEAD or read-only `.git` (or not reaching `verified` in HARNESS), **blocks the
live Alpha** (E-10) — no retry, repair or cleanup.

> Overall verdict: **NOT TESTED** (preparation under corrective review; E-12 not
> authorized or executed).
