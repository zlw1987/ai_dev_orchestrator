# DL-4B — Real Integration Boundary Design

**Status: DESIGN COMPLETE — PENDING INDEPENDENT REVIEW.**

| | |
|---|---|
| Baseline | `main` at `c0daaea072a4eeb1e2383df1a15aa671824e9563` (DL-1, DL-2, DL-3 + FU1, DL-4A + FU1) |
| Kind | Design only. No code, no test, no live execution, no workspace write, no credential |
| Objective | The minimum real integration needed to run **one** bounded, human-supervised AIDO Alpha step against **one** disposable workspace |
| Not authorized by this document | Implementing any slice, a live Alpha, any model / verifier / implementer execution, any credential or key creation, any change to `CLAUDE.md` |

Read with: `docs/DL4A_REAL_INTEGRATION_AUTHORITY.md` §§2–5 and §§10–13, the
accepted `control_plane/` source at the baseline, and the frozen 5F2C
(`apply_approved_file_edit`), 5F2D (`verify_approved_file_edit`), 5F2E
(`run_controlled_review`, `review-packet.v5`) and ALPHA-P1B
(`run_supervised_implementation`) contracts as summarized in `CLAUDE.md`.

Sections marked **FD-n** are decisions that must be frozen by review before
coding. Everything not marked FD is an implementation detail Claude may choose
(collected in §10.1).

---

## 0. Summary

DL-4A made every authority record *issued and bound*. It left five things
dependent on sources outside its reach. DL-4B closes them as follows.

| # | Boundary | DL-4B answer, one line |
|---|---|---|
| 1 | Human authentication | A FIDO2 hardware authenticator signs an AIDO challenge statement (OpenSSH `SSHSIG`, `sk-ssh-ed25519`, user-presence required). AIDO verifies in-process against an approver registry the AIDO account **cannot write**. The private key never exists in the AIDO process or account. |
| 2 | Verification evidence | A verification adapter, constructed inside a new integration session and never exposing its recorder, calls the shipped `verify_approved_file_edit` on inputs it reads **from the store**, and records the exact report bytes. The store binds those bytes to the dispatch, the write scope, the workspace identity and the consumed exact-diff approval, re-checking the report's own target facts. |
| 3 | Human acceptance lifecycle | In the integration store only, DL-2 **holds** a valid planner `RECOMMEND_STEP_ACCEPT` that lacks only human acceptance, as a persisted held decision, and stops. It does not escalate. A later process presents a signed acceptance over a subject that binds every piece of evidence the human saw. |
| 4 | Role-output origin | The implementer, verifier and reviewer dispatches are answered only by AIDO adapters that hold session-only evidence recorders. The store refuses those role outputs without matching recorded evidence. The planner stays unauthenticated (deterministic AIDO rule for the Alpha). The Alpha policy profile **mechanically** requires human acceptance. |
| 5 | Workspace authority | The model proposal (P1B, unchanged, its own process) and the human exact-diff approval come **before** the step attempt. The only workspace effect, the 5F2C write, runs **inside** the EXECUTING dispatch after a durable write intent. Crash, refusal and indeterminacy all end in RECOVERY_REQUIRED, never in repair. |

The design introduces a new store schema (`aido-control-plane-store.v4`, the
*integration store*). It leaves `store.v2`, `store.v3`, every DL-1 model and
every frozen 5F2C/5F2D/5F2E/P1B contract unchanged.

---

## 1. Scope

**In scope.** The authority, evidence and lifecycle design that lets the
accepted control plane (DL-1 → DL-4A) drive the accepted harnesses (5F2C,
5F2D, 5F2E, P1B) for one step, with a human at every authority boundary.

**Out of scope, deliberately.** Multi-step plans; more than one attempt;
re-planning or activating a plan for an existing run; project completion
(DL-1's `request_complete` refusal stands); any exit from HUMAN_REQUIRED or
RECOVERY_REQUIRED; Pi or any qualified harness; an autonomous implementer; a
fixer; branch, commit, push or PR; any product-level model token cap; any
sandbox; any new subprocess capability.

---

## 2. Trust model

### 2.1 What changes when integration becomes real

DL-4A's trust root is "the operator account and the composition root". That
was sufficient offline, because nothing else ran as the operator. **Real
integration changes this.** 5F2D runs repository-controlled code as the
operator account, unsandboxed, and its descendants may outlive the run
(`CLAUDE.md`, 5F2D). From the first VERIFYING dispatch onward, *code chosen by
the target repository* can do anything the AIDO account can do:

- read and write the state root, the store and the evidence blobs;
- read the AIDO process's memory and environment block;
- write any file the AIDO account can write, including any trust anchor stored
  there;
- race any AIDO path check (R-5).

DL-4B therefore treats the **repository-controlled verification process and
its descendants** as an explicit adversary (T3 below). It does not pretend to
contain them; it places the authorities that matter where they cannot reach.

### 2.2 Threats in scope

| Id | Adversary | What it must not be able to do |
|---|---|---|
| T1 | AIDO operator-side code (composition root, adapters, loops), through a bug or a model-steered input | Produce any human approval; record verification or review evidence that no shipped harness produced; make a role output count without its dispatch |
| T2 | A model (implementer, reviewer) or any role output | Select a path, command, workspace, state, policy or approval; be mistaken for AIDO-observed evidence |
| T3 | Repository-controlled verification code and its descendants (same account) | Forge a human approval; replace the approver registry; cause a second workspace write; turn an untrusted run into a trusted one that re-proves |
| T4 | A supported library caller | Present a caller-built JSON report, a digest, or a constructed model as proof of execution or approval |
| T5 | A crash or kill at any instruction | Leave a state from which a resumed action can repeat an external effect or appear proven |

### 2.3 Out of scope, stated rather than claimed

A malicious human approver; a malicious operator with administrative rights;
the AIDO source at the reviewed, pinned commit being itself malicious (code
review is that control); kernel or admin compromise; physical attack on the
authenticator; a deliberate consistent rewrite **plus** rollback of the
state root by an actor who also holds a valid authenticator (R-4, narrowed in
§13); and in-process code reaching private attributes (DL-4A §2, unchanged).

### 2.4 Trust sources DL-4B relies on

| Source | Why it is trusted | What it anchors |
|---|---|---|
| FIDO2 authenticator with user presence | The private key is non-exportable; each signature needs a physical touch | Every human approval (FD-1) |
| Approver registry not writable by the AIDO account | Provisioned with elevation into a fixed admin-owned path. AIDO refuses it if writable or replaceable by its own token, and refuses to run elevated | Which public keys are approvers (FD-2) |
| The shipped 5F2C / 5F2D / 5F2E / P1B code at the pinned commit | Independently accepted contracts; called, never reimplemented | Write, verification and review facts |
| The integration session's construction | The only place recorders are minted, and they never leave the adapters | Evidence origin (FD-6) |
| SQLite + NTFS semantics, host clock | Inherited from DL-1 / DL-4A | Atomicity, expiry |

---

## 3. Adversarial boundary analysis

Each row answers the eight required questions. "Revalidate" means checked at
the **consumption boundary** by the store, not by a convention of normal
callers.

### 3.1 Authority-bearing objects

| Object | Creator / mutator | Independent provenance | Supported-caller bypass? | Can valid objects disagree? | Revalidated at consumption | Crash / partial effect | Untrusted claim mistaken for evidence? | Diagnostic disclosure |
|---|---|---|---|---|---|---|---|---|
| **Approver registry** (`approver-registry.v1`) | The human, elevated, once. Never AIDO | Its location: admin-owned, AIDO-unwritable (checked) | Repointing via config is impossible: the path is a code constant, not config. Editing it needs elevation, and AIDO refuses to run elevated | A revoked key vs an earlier attestation by it → revocation is total (FD-3) | Re-read on every verification and every proof; never cached across calls | Read-only to AIDO | Registry contents are not evidence; only a signature checked against it is | Fingerprints only; never the full key blob in refusals |
| **Human attestation** (`human-attestation.v2`) | The human's authenticator; the store consumes it | The `SSHSIG` signature over the exact statement bytes, verified against the registry | A constructed attestation has no valid signature. A typed phrase alone is nothing | DL-1 approval block (`approved_by`/`approved_at`) vs the attested ones; the `DiffEditApproval` inside the artifact vs the attestation → must be equal | Signature, registry status, challenge state, subject recomputed from the actual objects, window, approval block. Re-verified on **every** proof (FD-4) | Challenge consumption shares the transaction with what it authorizes | No: a role cannot produce it | Never echo `proof`. Name the failed check category |
| **Plan activation v2** (plan + policy + workspace + write scope + config digest) | The human | Consumed `plan_activation` challenge; `plan_issuances` row | `record_execution_plan` stays refused | Config's configured workspace root vs the activated workspace; write-scope path vs the L1 plan's allowed paths | Store recomputes the v2 subject. Adapters re-check config digest and workspace identity on each use | One transaction | No | No workspace absolute path in refusals beyond what DL-4A already prints |
| **Write scope** (`write-scope.v1`) | The human (inside activation) | Its digest inside the activation subject | No API records one outside activation | Scope pre-image vs the artifact's `pre_image_sha256`; scope HEAD vs observed HEAD; scope path vs the report's `target.path` | At exact-diff approval, write intent, verification record, review record | Immutable | No | Repo-relative path and digests only |
| **Exact-diff approval** (H6, `exact_diff_approval` subject) | The human signs; the human also writes the frozen `DiffEditApproval` | Signature over a subject binding the activation, step id, write scope and `sha256(artifact bytes)` | The artifact bytes come from the store, never from the adapter's caller | The artifact's `DiffEditApproval` vs the attestation; the artifact's single change vs the scope | Write intent claims it only if unconsumed, matching the step and attempt. Single-use, globally | Claimed in the write-intent transaction, **before** the writer runs | The P1B proposal is untrusted content; only the signed approval is authority | Artifact bytes are source-derived and stay in the state root |
| **Write intent** (`write-intent.v1`) | The write harness, through the store | Row bound to the implementer ticket and the consumed exact-diff approval | No API writes to the workspace without one | — | Writer runs only after the intent commits | Intent committed, then crash → step EXECUTING → `recover()` → RECOVERY_REQUIRED; approval already spent, so no second write is possible | — | — |
| **Write evidence** (`workspace-write-result.v1` bytes) | The write harness's session-only recorder | Exact bytes returned by `apply_approved_file_edit` | Recorder not exposed (FD-6) | Report `target.path`, `approved_by`/`approved_at` vs scope and H6 → store checks | Re-hashed and re-parsed on every proof | Publish-then-insert (DL-4A pattern) | An `ImplementationReport`'s claims are never consulted; only the recorded write evidence counts | `git.target_diff` is repository text; stored, never logged |
| **Verification evidence v2** (`verification-result.v1` bytes) | The verification adapter's recorder | Exact bytes returned by `verify_approved_file_edit` on store-supplied inputs | Recorder not exposed; store.v4 cannot be opened by DL-4A's session (schema mismatch) | Report `target.path` / approval identity vs write scope and H6. 5F2E's second verification vs this one | Outcome re-derived (DL-4A); **plus** the report's target and approval identity re-checked against the step's write intent | DL-4A pattern | No: a caller-provided report or digest has no recorder | Output is 5F2D-redacted (a backstop, not a guarantee) |
| **Review evidence** (`review-packet.v5` bytes) | The reviewer adapter's recorder | Exact bytes of the packet `run_controlled_review` returned | Same as above | The packet's embedded verification vs recorded verification evidence; the packet's target vs scope | Verdict re-derived from `packet.review.verdict`; embedded verification must be `verified` with the same target and approval identity | DL-4A pattern | The verdict is advisory: it moves REVIEWING→ACCEPTANCE only, as today | The packet holds the diff; stored, never printed beyond the 5F2E banner |
| **Dispatch ticket** | Store (DL-4A, unchanged) | Persisted row | DL-4A closed | — | DL-4A + store.v4 evidence requirement per role | DL-4A | A ticket proves intent, never the producer (§5.4) | — |
| **Held planner decision** | DL-2 through `hold_acceptance_decision`; nobody mutates it | Ticket row marked held with the envelope bytes | A second planner ticket per version is refused (DL-4A); the decision is read back from the store, never from the caller | Held envelope vs a presented one → canonical equality required | At acceptance: the presented envelope must equal the held one | Persisted; ACCEPTANCE is not in flight, so `recover()` leaves it | The planner's recommendation never completes a step without a signed human acceptance | — |
| **Step acceptance v2** | The human signs | Signature over a subject binding attempt, version, write, verification, review and planner evidence digests | DL-4A closed | Every digest is recomputed from store rows | DL-4A + v2 subject | One transaction | — | — |

### 3.2 Lifecycle transitions

| Transition | Who causes it | External effect | Crash before / after | Revalidated |
|---|---|---|---|---|
| P1B proposal (outside the control plane) | Operator runs the existing `l2-supervised-implementer-run` | One model request (P1B ledger) | P1B's own semantics; the control plane has nothing to resume | Nothing in it is authority |
| Exact-diff approval recorded | Human + store | None | Atomic | Subject recomputed from stored artifact bytes |
| READY → EXECUTING | DL-2 `BEGIN_ATTEMPT` | None | DL-1 unchanged | DL-1 |
| EXECUTING dispatch: intent → 5F2C write | Write harness | **Workspace write** | After intent, before or after write → RECOVERY_REQUIRED; no retry | Intent requires an unconsumed matching H6 approval and a re-proven workspace |
| EXECUTING → VERIFYING | `IMPLEMENTATION_RETURNED` | None | DL-1 unchanged | store.v4: write evidence for this ticket required |
| VERIFYING dispatch: 5F2D | Verification adapter | **Repository-controlled execution** | → RECOVERY_REQUIRED | Inputs from the store only |
| VERIFYING → REVIEWING / ACCEPTANCE / RECOVERY_REQUIRED | `VERIFICATION_OBSERVED` | None | DL-1 unchanged | DL-4A + v2 binding |
| REVIEWING dispatch: 5F2E | Reviewer adapter | **Second repository-controlled execution; one or two model requests (RS1)** | → RECOVERY_REQUIRED | Inputs from the store only |
| REVIEWING → ACCEPTANCE | `REVIEW_OBSERVED` | None | DL-1 unchanged | store.v4: review evidence required |
| ACCEPTANCE: planner dispatch → hold | DL-2 | None | Held row persisted atomically, or not at all | Dry-run validator must refuse with exactly `HUMAN_ACCEPTANCE_MISSING` |
| ACCEPTANCE → COMPLETE | Human, new process | None | Atomic | Signed v2 acceptance; held envelope equality |
| ACCEPTANCE → HUMAN_REQUIRED | Human declines (`ESCALATE`) | None | Atomic | DL-1 unchanged; carries no attestation (FU1) |

---

## 4. Recommended architecture

```text
 SIGNING DEVICE (human)          AIDO HOST — operator account, NOT elevated
 ┌──────────────────┐      ┌────────────────────────────────────────────────────────┐
 │ FIDO2 key + touch│      │ %ProgramData%\AIDO\approver-registry.v1.json  (read-only│
 │ ssh-keygen -Y    │      │   to AIDO; checked unwritable; code-constant path)      │
 │  sign            │      │                                                         │
 └───────▲───┬──────┘      │ integration session (store.v4)                          │
   statement  SSHSIG       │  ├─ RegistryHumanAttestationVerifier  (pure, in-process)│
   (text)     (text)       │  ├─ WriteHarnessAdapter    ─ holds write recorder       │
         │   │             │  │     └─ apply_approved_file_edit (5F2C, unchanged)    │
         │   ▼             │  ├─ VerificationAdapter    ─ holds verification recorder│
 ┌──────────────────┐      │  │     └─ verify_approved_file_edit (5F2D, unchanged)   │
 │ human operator   │◄────►│  ├─ ReviewerAdapter        ─ holds review recorder      │
 └──────────────────┘      │  │     └─ run_controlled_review (5F2E, unchanged)       │
                           │  └─ AlphaPlannerRule       ─ deterministic, no recorder │
                           │                                                         │
                           │ DL-3 → DL-2 → bound ports → store (all checks here)     │
                           │                                                         │
                           │ AIDO STATE ROOT   store.v4 · evidence/{verification,    │
                           │                   write,review,approved-diff} · staging │
                           └───────────────┬────────────────────────────────────────┘
                                           │ authorized_target_workspace() only
                                           ▼
                           DISPOSABLE CLONE (Git, Windows, clean at the scope's HEAD)

 Separate, earlier process (unchanged ALPHA-P1B):
   l2-supervised-implementer-prepare / -run  →  diff-proposal.v2  →  human writes
   approved-diff-proposal.v2 (frozen DiffEditApproval)  →  signed exact-diff approval
```

**Process separation (FD-9).** Three operator invocations, split only at
non-in-flight boundaries:

1. **Proposal**: the existing P1B commands, unchanged. This is the only
   process that reads implementer credentials.
2. **Attempt**: one integration-session invocation that drives the step from
   READY to the held ACCEPTANCE. It reads **no** credential before 5F2D runs.
   5F2E reads reviewer credentials only after its own verification, as frozen.
3. **Acceptance**: a fresh integration-session invocation that presents the
   human's signed acceptance. It runs no harness.

Approvals (project contract, plan activation, exact diff) are recorded before
invocation 2 in short invocations that run no harness.

---

## 5. Boundary designs

### 5.1 Human authentication and approval

**FD-1 Mechanism.** An approval is an OpenSSH `SSHSIG` signature (armored,
`ssh-keygen -Y sign` format) with:

- key type exactly `sk-ssh-ed25519@openssh.com`, a FIDO2 resident or
  non-resident key whose private part never leaves the authenticator;
- SSHSIG namespace exactly `aido-approval@v1`, which prevents reuse of a git or
  login signature made with the same key;
- hash algorithm exactly `sha512`;
- authenticator flags with **user presence** (`0x01`) set. User verification
  (PIN, `0x04`) is required if the registry entry says so;
- the message is exactly the canonical bytes of an `attestation-statement.v1`
  (§8), which binds: `state_root_id`, `challenge_id`, `subject_kind`,
  `subject_sha256`, `approver_id`, the key fingerprint, `attested_at`,
  `expires_at` and the exact approval phrase.

`human-attestation.v2.proof` carries the armored signature. The human signs;
**AIDO never runs `ssh-keygen`**, so no subprocess capability is added.
Verification is a pure, in-process function: parse SSHSIG, require exact
equality of the public-key blob and the application string with the registry
entry, rebuild the SSHSIG signed-data and the FIDO `sk` signed-data
(`sha256(application) ‖ flags ‖ counter ‖ sha256(signed-data)`), and verify
Ed25519.

**FD-1a Dependency.** Ed25519 verification uses the `cryptography` package,
added as a pinned runtime dependency. AIDO must not hand-roll curve
arithmetic. This is a new dependency and needs explicit approval.

**Why not the alternatives.** An HMAC key, a software private key, a password,
a typed phrase, or Windows Hello without a separate presence gesture are all
readable or invocable by the AIDO account, and so by T1 and T3. A remote
approval service would be stronger, but it is not the shortest path.

**FD-2 Identity provisioning and credential custody.**

| Item | Rule |
|---|---|
| Key generation | By the human, on the signing device, with their authenticator (`ssh-keygen -t ed25519-sk -O application=ssh:aido-approval`). AIDO never sees, creates or stores a private key or key handle |
| Registry | `approver-registry.v1` at the code-constant path `%ProgramData%\AIDO\approver-registry.v1.json`, written by the human with elevation. Entries: `approver_id`, `public_key` (OpenSSH sk blob), `application`, `fingerprint_sha256`, `require_user_verification`, `not_before`, `not_after`, `revoked` |
| Anchor protection, checked mechanically on every read | (a) path is the constant, not config; (b) not a reparse point in any component; (c) the current token has neither write, append, delete nor `WRITE_DAC`/`WRITE_OWNER` on the file, and neither add-file nor delete-child on its directory (Win32 access check); (d) the AIDO process token is **not elevated**. Any failure → the verifier refuses everything |
| Signing device | **Recommended: a device other than the AIDO host.** This defeats T3 swapping the statement between display and signing. The AUTH-PILOT must state which device is used. Same-host signing is permitted only with that residual acknowledged (D-5) |
| Rehearsal | Before the Alpha, the human signs one throwaway challenge in a throwaway state root, proving format interoperability with the real authenticator (entry criterion E-6) |

**FD-3 Replay, expiry and revocation.**

- *Replay*: the challenge is single-use and consumed atomically (DL-4A). The
  statement binds the `state_root_id`, so an attestation cannot be carried to
  another state root. The namespace binds the protocol. The `sk` counter is
  recorded for audit but is **not** a security property, because some
  authenticators do not increment it.
- *Expiry*: the challenge TTL stays 60 minutes (DL-4A, R-8). An approver entry
  outside `[not_before, not_after]` refuses.
- *Revocation is total*: a `revoked` entry refuses every attestation by that
  key, including **re-proofs of already-consumed attestations**. A completed
  run whose acceptance was signed by a revoked key becomes untrusted, and
  `recover()` escalates it to HUMAN_REQUIRED. A signer-supplied `attested_at`
  cannot be trusted to separate pre- from post-compromise signatures, so there
  is no partial revocation.

**FD-4 Re-verification on every proof.** The store persists the full consumed
attestation (DL-4A already does). Every authoritative read and every
`recover()` re-verifies the stored signature against the current registry.
This is what makes a DB rewrite by T3 unable to *fabricate* an approval: it can
corrupt (fail closed), but not forge.

**FD-5 R-7 resolution.** The verifier is consulted **before** the write
transaction, with fresh copies. Inside the transaction the store re-checks
that the challenge is unconsumed and unexpired and that the attestation's
digest equals the digest just verified. A slow verifier therefore never holds
the store lock. The verifier is pure anyway: no network, no subprocess, no
environment read.

**Failure behavior.** Every failure is a refusal (`AUTHORITY_UNPROVEN`),
nothing is consumed, and the refusal names the failed check category
(`registry_unprotected`, `key_unknown`, `key_revoked`, `signature_invalid`,
`presence_missing`, `namespace_mismatch`, `statement_mismatch`,
`challenge_spent`, `challenge_expired`). It never echoes the proof or the key
blob, only the fingerprint. An unreadable or unprotected registry makes the
verifier approve nothing, which is DL-4A's default behavior, preserved.

**New subject kind.** The exact-diff approval needs a fourth subject kind,
`exact_diff_approval`, whose phrase is exactly 5F2C's
`REQUIRED_DIFF_EDIT_APPROVAL_TEXT`. Because `ApprovalSubjectKind` is a closed
set inside the v1 models, adding a value would silently widen
`approval-challenge.v1` and `human-attestation.v1`. DL-4B therefore defines
`approval-challenge.v2` and `human-attestation.v2` for store.v4 only (§8).

### 5.2 Real verification evidence

**FD-6 Recorders exist only inside adapters.** `open_integration_session`
(new; DL-4A's `open_authority_session` is unchanged) opens a **store.v4** and
constructs the three evidence-producing adapters itself. Each recorder is
minted and handed directly to its adapter. The session exposes the store, the
bound role ports and nothing else. There is **no** `verification_recorder`
attribute. Because store.v3 and store.v4 cannot open each other's files
(DL-4A's mechanism), DL-4A's session cannot be pointed at an integration store
to obtain a recorder.

**Verification adapter algorithm** (`verify(step_contract, attempt, dispatch)`):

1. Read from the store, never from the caller: the step's write scope, the
   write intent consumed by this attempt's implementer ticket, the
   approved-diff artifact bytes that intent names, and
   `authorized_target_workspace(project_run_id)`.
2. Check that the session's project config bytes hash to the scope's
   `project_config_sha256`, and that the config's configured workspace root
   resolves to the authorized workspace by canonical path **and** directory
   identity.
3. Parse the artifact with the frozen `parse_approved_diff_proposal_artifact`.
4. Call the shipped `verify_approved_file_edit(approved_diff=…, project=…)`
   unchanged. It is imported, not injected.
5. On `VerificationRefusedError`, record nothing and raise. DL-2 reduces the
   step to RECOVERY_REQUIRED.
6. On a returned report, record exactly `report.model_dump_json().encode()`
   for `dispatch`, then return a `BoundRoleOutput` of a
   `VerificationObservation` built from the **receipt**, never from the report
   object.

**Store-side binding (v2), enforced at record time and on every proof.** In
addition to DL-4A's checks, `_record_verification_evidence` in store.v4:

- parses the bytes with an extended mirror reader that also returns
  `target.path`, `target.change_type`, `approved_by`, `approved_at` and the
  identity tuple (`project_id`, `repo`, `issue_number`, `title`);
- requires `target.path == write_scope.path` and `change_type == "modify"`;
- requires `approved_by`/`approved_at` to equal the consumed exact-diff
  approval's attested approver and time;
- requires the identity tuple to equal the approved artifact's identity;
- requires the ticket's step to have a **completed write intent** for this
  attempt;
- records, in the evidence row: ticket, step run, attempt, write-intent id,
  write-scope digest, the workspace identity digest re-proven at record time,
  evidence digest and outcome.

A caller-provided JSON report, or a matching SHA-256 alone, has no path into
this: only a recorder can record, and only the adapter holds one.

**Frozen semantics preserved.** `verification-result.v1` bytes are stored
exactly as produced. 5F2D's exit classes map exactly as DL-1 already maps them
(`workspace-state-untrusted` → RECOVERY_REQUIRED). 5F2D's environment policy,
timeout semantics and "not sandboxed" claims are untouched. AIDO adds no claim
about the child.

### 5.3 Human acceptance lifecycle

**FD-7 Hold, do not escalate (store.v4 only).**

DL-2's `_decide` gains one integration-mode branch:

1. **On entering ACCEPTANCE**, before requesting a ticket, ask the store for a
   held decision at `(step_run_id, state_version)`. If one exists, return
   `InnerLoopStop.AWAITING_HUMAN_ACCEPTANCE` (additive enum value) with no
   dispatch and no ticket request.
2. **Otherwise**, dispatch the planner under its ticket as today. If
   `apply_step_transition(DECIDE_ACCEPTANCE)` raises exactly
   `HUMAN_ACCEPTANCE_MISSING`, call
   `store.hold_acceptance_decision(step_run_id, expected_state_version=…, role_output=bound)`
   and stop with `AWAITING_HUMAN_ACCEPTANCE`. DL-2 does **not** escalate.

`hold_acceptance_decision` is an authority-consuming entry under the FU1 rule:
consume or refuse, never ignore. Inside one transaction it:

- re-proves the step and requires ACCEPTANCE at the expected version;
- validates the envelope against its unconsumed planner ticket (DL-4A checks);
- runs the **unchanged** DL-1 validator as a dry run with the payload and
  requires it to refuse with exactly `HUMAN_ACCEPTANCE_MISSING`. Any other
  outcome refuses the hold: a planner decision the validator would apply is
  applied by DL-2 normally;
- marks the ticket **held**, storing the canonical envelope bytes and digest.
  No step transition is written and the step version does not change.

An identical repeat is a receipt. A different envelope for the same ticket is
refused.

**The hold persists.** ACCEPTANCE is not an in-flight state, so `recover()`
leaves the step and its held decision intact across crashes and sessions.
DL-3 needs **no change**: it already treats a step DL-2 left at ACCEPTANCE as
`STEP_NOT_SETTLED` without escalating. On a later DL-3 call, DL-2 stops at the
held check and never asks the planner again.

**What remains available to the human.** `held_acceptance_bundle(step_run_id)`
is a re-proven read returning the held envelope, the step contract, the write
scope, and the write, verification and review evidence digests, outcome and
verdict, with paths to the write-once blobs. It is the human's review
material.

**Completion.** In a fresh session:

1. `request_step_acceptance(step_run_id)` (store.v4) refuses without a held
   decision and computes **`step-acceptance-subject.v2`**: DL-4A's fields plus
   `write_scope_sha256`, `write_evidence_sha256`, `review_evidence_sha256` and
   `planner_envelope_sha256`. The signature thus covers everything the human
   was shown.
2. The human signs; the driver calls `apply_step_transition(DECIDE_ACCEPTANCE,
   planner_decision=held.output, human_acceptance=…, role_output=<held
   envelope>, human_attestation=…)`.
3. The store requires the presented envelope to equal the held one
   canonically, consumes the held ticket and the challenge in the transition's
   transaction, and lets the unchanged validator decide (COMPLETE).

**Decline.** The human applies `ESCALATE` → HUMAN_REQUIRED (DL-1 unchanged;
authority-reducing; no attestation, per FU1). The held ticket stays
unconsumed and becomes stale.

**Preserved.** HUMAN_REQUIRED and RECOVERY_REQUIRED stay terminal with no exit.
A held decision is never applied without a signature. No automatic
escalation, and no repeated planner dispatch, by construction (ticket
uniqueness plus the held check). In store.v2 and store.v3, DL-2's R-9 escalation
is byte-for-byte unchanged.

### 5.4 Role-output origin

A dispatch ticket proves AIDO issued an intent. It does not authenticate the
producer. DL-4B makes origin a **held capability** where a deterministic
harness exists, and leaves it unauthenticated where none exists.

| Role | Authorized answering component (FD-8) | Origin evidence the store requires at consumption | Residual |
|---|---|---|---|
| implementer (EXECUTING) | `WriteHarnessAdapter` only | A completed write intent **and** write evidence for this ticket, recorded by the write recorder | The proposal content's origin (P1B) is unauthenticated, but it is not authority: the signed exact-diff approval is |
| verifier (VERIFYING) | `VerificationAdapter` only | Verification evidence v2 for this ticket | §13 D-2 |
| reviewer (REVIEWING) | `ReviewerAdapter` only | Review evidence for this ticket; `ReviewProposal.evidence_sha256` must equal it, and its verdict must equal the verdict re-derived from the packet bytes | The verdict is model output, advisory by contract |
| planner (ACCEPTANCE) | `AlphaPlannerRule`: deterministic. `RECOMMEND_STEP_ACCEPT` iff verification is `verified` and review is `approve`; otherwise `HUMAN_REQUIRED`. No model | None (R-3 stands) | A store holder can mint and answer a planner ticket. Backstop: a signed human acceptance over the planner envelope digest |
| tester | Not dispatched (no tester execution in DL-1) | — | — |

**Mechanical Alpha profile (FD-8a).** store.v4 refuses any plan activation
whose policy is not exactly `{review_required: true,
human_acceptance_required: true, max_attempts: 1}`, and any plan with more
than one step or any write scope with more than one entry. So "require human
acceptance regardless of role-origin evidence" is a store refusal, not a
policy someone remembers to set.

**ROLE ≠ HARNESS ≠ BACKEND ≠ MODEL.**

| Role | Harness that produces content | Backend | Model | Recorded where |
|---|---|---|---|---|
| implementer (proposal) | ALPHA-P1B live supervised implementer (outside the control plane) | LiteLLM (P1B requires it) | `SUP-D` from P1B's registry | P1B's own evidence; optionally referenced by digest, non-authoritative |
| implementer (dispatch) | 5F2C writer via the write harness | none | none | write evidence |
| verifier | 5F2D | none | none | verification evidence |
| reviewer | 5F2E | `controlled_review.provider` | `controlled_review.model` | inside `review-packet.v5` provenance |
| planner | AIDO deterministic rule | none | none | the envelope |

No control-plane record names a backend, a provider, a model or an endpoint,
preserving DL-4A §6. Those facts live only inside the harness's own evidence.

### 5.5 Workspace authority

**FD-9 Ordering.** The frozen sequence *proposal → human exact-diff approval →
authorized write → verification* maps onto the control plane as follows.

```text
before the attempt (not in flight)        │ inside one attempt (DL-2, in flight)
──────────────────────────────────────────┼───────────────────────────────────────
P1B proposal  →  human writes frozen       │ BEGIN_ATTEMPT → EXECUTING:
DiffEditApproval → signed exact_diff       │   claim H6 in a write intent → 5F2C write
approval recorded against the write scope  │ → VERIFYING: 5F2D → REVIEWING: 5F2E
                                           │ → ACCEPTANCE: planner → hold
```

The workspace side effect, the write, is entered under a persisted in-flight
state exactly as DL-1 requires. The model request precedes the step's intent,
but it changes no workspace and is governed by P1B's own durable ledger. This
is a deliberate deviation from DL-4A §12's sketch: see §9 C-4.

**FD-10 Write scope.** `write-scope.v1` is approved inside the plan
activation (`plan-activation-subject.v2`) and keyed by `step_id`:

```text
{ schema_version, step_id, path (repo-relative POSIX, exactly one),
  change_type: "modify", pre_image_sha256, base_head_oid,
  project_config_sha256 }
```

StepContract v1 is unchanged. DL-4A §11 suggested a Step Contract version with
write scope. For a one-step Alpha, an activation-bound scope is sufficient,
and it avoids reopening DL-1's model, validator and contract rules (§9 C-5).

**How adapters obtain bounded authority.** An adapter receives no path, no
artifact and no config from its caller. It reads, through the store:

- the workspace from `authorized_target_workspace(project_run_id)`, which
  re-proves canonical path, identity and disjointness on each call;
- the scope from the run's plan issuance;
- the artifact bytes from the store's write-once `evidence/approved-diff/`;
- the config from the session's single in-memory copy, whose digest must equal
  the scope's. A later on-disk edit of the config file, including one by T3,
  does not reach it.

**Write harness algorithm** (`implement(step_contract, attempt, dispatch)`):

1. Re-prove the workspace and the config binding (as in §5.2 step 2).
2. Observe HEAD with the **existing** read-only P1B helper
   `observe_clean_workspace_head` (no new Git operation) and require it to
   equal `base_head_oid` and the tree to be clean.
3. In one store transaction, `claim_write_intent(ticket)`: require an
   unconsumed exact-diff approval for this plan issuance and step, whose
   artifact matches the scope. Mark the approval consumed by this ticket and
   insert the intent as `pending`. **Commit before the writer runs.**
4. Call `apply_approved_file_edit(approved_diff=<parsed store bytes>,
   project=<session config>)` unchanged.
5. On a returned report: record its exact bytes as write evidence (the store
   checks `target.path`, `approved_by`/`approved_at` and identity against the
   scope and approval), mark the intent `completed`, and return an
   `ImplementationReport` whose summary is AIDO's fixed text. Claims are empty
   and never consulted.
6. On `WorkspaceWriteRefusedError` (nothing replaced, per 5F2C), mark the
   intent `refused` and raise.
7. On `WorkspaceWriteIndeterminateError`, mark the intent `indeterminate` and
   raise.
8. In both failure cases DL-2 reduces the step to RECOVERY_REQUIRED.

**Substitution, partial writes, cleanup and recovery — all fail closed.**

| Event | Detection | Result |
|---|---|---|
| Workspace directory swapped or junctioned | `authorized_target_workspace` identity check (path-based, R-5) | Refusal → RECOVERY_REQUIRED |
| Target file substituted before the write | 5F2C pre-image SHA-256 and its own filesystem checks | 5F2C refusal → RECOVERY_REQUIRED |
| Substitution between write and verification | 5F2D precondition (post-image hash, HEAD unchanged, exactly one dirty path) | 5F2D refusal or `workspace-state-untrusted` → RECOVERY_REQUIRED |
| Substitution during or after verification | 5F2D postcondition; 5F2E's second verification | `workspace-state-untrusted`, or no packet → RECOVERY_REQUIRED |
| Partial or indeterminate write | 5F2C `WorkspaceWriteIndeterminateError` | intent `indeterminate` → RECOVERY_REQUIRED; no retry, no rollback |
| Crash after intent commit | `recover()` sees EXECUTING | RECOVERY_REQUIRED; the approval is spent, so a second write is impossible |
| Cleanup | — | **None.** No API restores, cleans or deletes anything in the workspace. DL-4A's single removal (own staging file) is the only removal in DL-4B code, pinned by a static test |

**DL-4A containment is not a sandbox.** Every check above is a detection
before or after an action, not a confinement. A concurrent same-account actor
between a check and the next system call is not excluded (R-5). 5F2C's and
5F2D's own detection limits apply unchanged.

### 5.6 Reviewer integration and the double verification

`run_controlled_review` runs the 5F2D verification **itself** and accepts no
prior result (frozen: no `--verification-result` input). So each Alpha attempt
executes repository-controlled code **twice**: once at VERIFYING (authority)
and once inside REVIEWING (as 5F2E's precondition). DL-4B accepts this
instead of changing 5F2E. The reviewer adapter:

1. obtains inputs from the store exactly like the verification adapter;
2. calls `run_controlled_review` with the production
   `build_reviewer_network_transport` and a provider-scoped `read_env`
   (5F2E-V1-FU1 semantics);
3. on a packet: records exactly `packet.model_dump_json().encode()` as review
   evidence. The store requires that `packet.verification.outcome ==
   "verified"`, that the packet's target and approval identity equal the
   scope's and H6's, and re-derives the verdict;
4. on no packet (the second verification did not verify, or the reviewer stage
   failed or stalled): records nothing authoritative and raises → RECOVERY_REQUIRED.
   It may store the second verification report as **non-authoritative audit
   evidence** for the human.

The two verification reports may disagree, for example with a flaky test.
Disagreement fails closed and is visible to the human.

RS1, V1, V2 and ALPHA-1A-FU1 semantics are unchanged. AIDO adds no
`max_tokens`, so `max_output_tokens` stays optional and unset unless the
project configures it.

### 5.7 Credentials and process state

- The attempt invocation reads no model credential before either 5F2D run.
  The implementer's credentials are read only in the separate P1B process.
  This preserves 5F2E's rule that reviewer credentials never coexist in AIDO's
  process state with repository-controlled execution, which would otherwise
  be broken in substance: P1B and a LiteLLM reviewer read the **same**
  `AIDO_LITELLM_*` names.
- The process environment block may still contain persistent `AIDO_*`
  variables. 5F2D's child environment is a fixed allowlist, so they are not
  forwarded. They remain readable from process memory by a same-account child
  (inherited residual D-4).
- The approver verifier reads no environment variable. The registry path is a
  constant.

---

## 6. End-to-end authority and evidence flow

```text
 #   Invocation         Actor            Action                                 Authority consumed / evidence produced
 1   setup              operator         AidoStateRoot.create (empty dir)       state-root id
 2   approve-contract   human (sign)     project contract                       challenge(project_contract)
 3   approve-activation human (sign)     plan + Alpha policy + workspace +      challenge(plan_activation v2)
                                         write scope + config digest
 4   proposal           operator         l2-supervised-implementer-prepare/run  P1B ledger (outside control plane)
 5   approve-diff       human            writes frozen DiffEditApproval;        challenge(exact_diff_approval);
                        (sign)           store stores artifact bytes            artifact bytes write-once
 6   attempt            operator         issue step contract, create project    —
                                         run + step run (activation required)
                        DL-3/DL-2        MARK_READY, BEGIN_ATTEMPT              ticket(implementer)
                        write harness    claim intent → 5F2C write              H6 consumed; write evidence
                        DL-2             IMPLEMENTATION_RETURNED                ticket consumed (needs write evidence)
                        verification     5F2D                                   verification evidence v2
                        DL-2             VERIFICATION_OBSERVED                  ticket consumed (needs evidence)
                        reviewer         5F2E (re-verifies, then model)         review evidence
                        DL-2             REVIEW_OBSERVED                        ticket consumed (needs evidence)
                        planner rule     RECOMMEND_STEP_ACCEPT                  ticket HELD
                        DL-2             AWAITING_HUMAN_ACCEPTANCE stop         —
 7   accept             human (sign)     reviews bundle; signs subject v2       challenge(step_acceptance v2);
                        driver           DECIDE_ACCEPTANCE                      held ticket consumed → COMPLETE
 8   close-out          operator         fresh session: recover(); archive      project ACTIVE, PLAN_WORK_COMPLETE
```

---

## 7. Lifecycle and failure-state model

| Phase / state | Failure or crash | Resulting state | Retry? | Human action |
|---|---|---|---|---|
| Approvals (2, 3, 5) | Any refusal; crash mid-transaction | Nothing recorded | Re-request a new challenge | Re-sign |
| Proposal (4) | P1B refusal, stall or rejection | No artifact; control plane untouched | Per P1B: a new authorization | Decide whether to re-run P1B |
| READY | `BEGIN_ATTEMPT` refused | Step stays READY; DL-2 stops `TRANSITION_REFUSED` | No | Inspect |
| EXECUTING before intent | Implementer ticket refused; workspace, config or HEAD check fails | RECOVERY_REQUIRED (DL-4A / DL-2 rule); approval unspent but the attempt budget is spent | No (`max_attempts` 1) | Inspect; a new plan activation is needed for a new attempt |
| EXECUTING after intent | Refused, indeterminate, crash | RECOVERY_REQUIRED; approval spent | No | Inspect the clone; never `git restore` by AIDO |
| VERIFYING | 5F2D refusal; adapter binding failure; crash | RECOVERY_REQUIRED | No | Inspect |
| VERIFYING | `verification-failed` | ACCEPTANCE (DL-1) → planner `HUMAN_REQUIRED` → HUMAN_REQUIRED | No | Inspect |
| VERIFYING | `workspace-state-untrusted` | RECOVERY_REQUIRED (DL-1) | No | Inspect |
| REVIEWING | No packet, stall, egress refusal, crash | RECOVERY_REQUIRED | No (RS1 retry is internal to 5F2E, unchanged) | Inspect |
| REVIEWING | Verdict `changes_requested` / `needs_human_review` | ACCEPTANCE → planner `HUMAN_REQUIRED` → HUMAN_REQUIRED | No | Read the packet |
| ACCEPTANCE | Hold refused | HUMAN_REQUIRED (DL-2's existing planner-failure escalation) | No | Inspect |
| ACCEPTANCE (held) | Crash; restart | Held, unchanged | — | Continue at 7 |
| ACCEPTANCE (held) | Challenge expired | Held, unchanged | New challenge | Re-sign |
| ACCEPTANCE (held) | Human declines | HUMAN_REQUIRED via `ESCALATE` | — | — |
| Any | Registry unprotected, key revoked, signature fails re-proof, evidence tampered | Run untrusted → `recover()` → HUMAN_REQUIRED (integrity escalation) | No | Investigate |
| COMPLETE | — | Project ACTIVE, `PLAN_WORK_COMPLETE`; completion refused (DL-1) | — | Archive the state root |

Every failure is terminal for the Alpha. Nothing is retried, repaired, rolled
back or cleaned.

---

## 8. Required versioned contract extensions

All are new identifiers. No existing identifier changes meaning.

| Identifier | Kind | Content | Replaces / coexists |
|---|---|---|---|
| `aido-control-plane-store.v4` | store schema | v3 tables plus: `write_scopes`, `exact_diff_approvals`, `write_intents`, `write_evidence`, `review_evidence`, held-ticket columns, verification-evidence v2 columns, approver-key audit (fingerprint, counter) | Coexists. v2 and v3 unchanged; none opens another's file |
| `open_integration_session` | API | Opens store.v4 only; builds verifier and adapters; exposes store + bound ports; no recorder | Coexists with `open_authority_session` |
| `approval-challenge.v2` / `human-attestation.v2` | models | v1 fields; subject kinds + `exact_diff_approval`; `proof` = armored SSHSIG | store.v4 only; v1 unchanged |
| `attestation-statement.v1` | signed bytes | Canonical JSON: `schema_version`, `namespace`, `state_root_id`, `challenge_id`, `subject_kind`, `subject_sha256`, `approver_id`, `key_fingerprint_sha256`, `attested_at`, `expires_at`, `approval_text` | new |
| `approver-registry.v1` | file | §5.1 FD-2 | new |
| `write-scope.v1` | model | §5.5 FD-10 | new |
| `plan-activation-subject.v2` | digest | v1 fields + `write_scopes_sha256` + `project_config_sha256` | store.v4 only |
| `exact-diff-approval-subject.v1` | digest | plan-issuance digest, `step_id`, `write_scope_sha256`, `approved_diff_artifact_sha256` | new |
| `write-intent.v1` | record | ticket, approval, scope, artifact digest, workspace identity digest, observed HEAD, state ∈ {pending, completed, refused, indeterminate} | new |
| `step-acceptance-subject.v2` | digest | v1 fields + `write_scope_sha256`, `write_evidence_sha256`, `review_evidence_sha256`, `planner_envelope_sha256` | store.v4 only |
| Mirror readers | code | `workspace-write-result.v1` binding reader; `verification-result.v1` binding reader (extends DL-4A's); `review-packet.v5` binding reader. Each pinned by test to the shipped model | additive |
| `InnerLoopStop.AWAITING_HUMAN_ACCEPTANCE` | enum value | §5.3 | additive; never produced for v2/v3 stores |
| `hold_acceptance_decision`, `held_acceptance_bundle`, `request_exact_diff_approval`, `record_exact_diff_approval`, `claim_write_intent` | store APIs | store.v4 only; refused in v3 / v2 | additive |
| `cryptography` | runtime dependency | Ed25519 verification only | new (FD-1a) |

**Unchanged and pinned:** every DL-1 model and validator rule; StepContract v1;
`execution-policy.v1`; `dispatch-ticket.v1`; `bound-role-output.v1`; DL-3;
DL-2's offline and DL-4A call shapes; `approved-diff-proposal.v2`,
`diff-proposal.v2`, `workspace-write-result.v1`, `verification-result.v1`,
`review-packet.v5`; every P1B artifact.

---

## 9. Contradictions and tensions with frozen contracts

| Id | Contract | Tension | Resolution proposed | Needs |
|---|---|---|---|---|
| C-1 | `CLAUDE.md`: real model calls exist only behind four gated commands | The attempt invocation calls 5F2E in-process from a new entry point: a fifth model-calling surface | Make the Alpha driver a separately gated command (two explicit flags + project opt-in), reusing 5F2E's own gates. A subprocess invocation of the existing command is **not** an alternative: it adds a subprocess capability, and its output would be a caller-provided report | **User decision and `CLAUDE.md` update by the user.** DL-4B does not edit `CLAUDE.md` |
| C-2 | 5F2E: verify first, no `--verification-result` | Two repository-controlled executions per attempt | Accept; bind both; disagreement fails closed (§5.6) | Reviewer acknowledgement |
| C-3 | DL-2 R-9 (escalate at ACCEPTANCE when human acceptance is missing) | DL-4B requires hold-and-stop | Versioned by store: store.v4 holds; v2 and v3 unchanged | FD-7 |
| C-4 | DL-1 §12.4 intent-before-effect for the "worker request"; DL-4A §12 sketch (H6 + write outside the control plane) | The model request precedes EXECUTING. The write moves **inside** EXECUTING | The workspace effect is the one the control plane must record before acting. P1B's model request has its own durable ledger intent. DL-4A §12 was a non-frozen sketch whose "write outside the control plane" would let verification check a write the control plane never authorized | FD-9 |
| C-5 | DL-4A §11.3 (Step Contract version with write scope; roadmap §14.1) | DL-4B binds write scope in plan activation v2 instead | Deviation from a recommendation, not a frozen contract; step-contract.v2 is deferred until multi-step | FD-10 |
| C-6 | DL-4A §2 trust root ("operator account") and R-4 | Repository code now runs as that account | Threat T3 made explicit. Approvals are re-verified against an AIDO-unwritable registry (FD-2, FD-4). Remaining tamper surface: D-2 | Reviewer acknowledgement |
| C-7 | `ApprovalSubjectKind` closed in `*.v1` | A fourth kind is needed | `*.v2` models, store.v4 only | — |
| C-8 | DL-1 §7: ALPHA-1B's S0 preflight STOPs while DL files are in `src/` | The DL Alpha and ALPHA-1B cannot share one checkout pin | The DL Alpha needs its own runbook and pin; ALPHA-1B is unaffected | User decision |
| C-9 | `CLAUDE.md`: ALPHA-P1B listed as "IMPLEMENTED (awaiting review)" | The Alpha depends on P1B's live path | Confirm P1B acceptance before E-1 | User confirmation |

No frozen contract is silently changed. C-1 and C-8 cannot be resolved inside
this design.

---

## 10. Frozen decisions (must be accepted before coding)

| FD | Decision |
|---|---|
| FD-1 | Human approval = SSHSIG, `sk-ssh-ed25519@openssh.com`, namespace `aido-approval@v1`, `sha512`, user presence required, over `attestation-statement.v1` bytes; verified in-process; AIDO never signs and never runs `ssh-keygen` |
| FD-1a | Add `cryptography` (pinned) for Ed25519 verification only |
| FD-2 | Registry at a code-constant admin-owned path; mechanically refused if writable or replaceable by the AIDO token; AIDO refuses to run elevated; separate signing device recommended and named in AUTH-PILOT |
| FD-3 | Challenge single-use, 60-minute TTL, bound to the state root id; revocation is total, including re-proofs |
| FD-4 | Every proof and `recover()` re-verifies stored signatures against the current registry |
| FD-5 | Verify before the write transaction; re-check challenge state and attestation digest inside it |
| FD-6 | store.v4 + `open_integration_session`; recorders minted only into adapters; no recorder on the session |
| FD-7 | Hold-and-stop at ACCEPTANCE in store.v4; acceptance subject v2; decline = `ESCALATE` |
| FD-8 | Role-to-component mapping of §5.4; the store requires recorded evidence for implementer, verifier and reviewer outputs; deterministic Alpha planner rule |
| FD-8a | The Alpha policy profile is enforced by the store (one step, one scope entry, review + human acceptance required, one attempt) |
| FD-9 | Proposal and exact-diff approval before the attempt; durable write intent then the 5F2C write inside EXECUTING; three-invocation process split |
| FD-10 | `write-scope.v1` inside `plan-activation-subject.v2`; StepContract v1 unchanged |
| FD-11 | No cleanup, restore, retry, rollback or repair anywhere; every failure is terminal for the Alpha |
| FD-12 | No new subprocess capability, no new Git operation, no model token cap, no sandbox claim, no CLI option that names a path, model, endpoint, key or timeout |

### 10.1 Implementation details Claude may choose

Module layout (adapters live **outside** `control_plane/`, which must stay free
of executing imports, for example `ai_dev_orchestrator/integration/`); SQL
table and column shapes; the Win32 access-check implementation (`AccessCheck`
or `GetEffectiveRightsFromAcl` via `ctypes`); the elevation check; the SSHSIG
parser structure; how the statement is presented to the human (file or
stdout); refusal message wording within the categories of §5.1; the
non-authoritative audit record of 5F2E's second verification; helper
conveniences that build requests (never checks); test fixture structure.

---

## 11. Minimum implementation slices and acceptance gates

Each slice needs its own prompt and its own independent review. None runs
anything live.

| Slice | Content | Acceptance gate |
|---|---|---|
| **S1** Attestation verifier | `RegistryHumanAttestationVerifier`, SSHSIG/sk parser, registry reader with anchor protection, elevation refusal, `attestation-statement.v1`, `*.v2` models | Known-answer vectors (test-only software Ed25519 key emulating the `sk` format); every refusal category; registry-writable refused; elevated refused; no env, network or subprocess surface (static test) |
| **S2** Integration store | store.v4, `open_integration_session`, Alpha policy profile, write scope, activation subject v2, FD-4 re-verification in proofs, FD-5 ordering | v2/v3 suites unchanged and green; v3↔v4 cross-open refused; no recorder reachable from the session; tamper matrix → untrusted |
| **S3** Exact diff + write harness | `request/record_exact_diff_approval`, `claim_write_intent`, write recorder, `WriteHarnessAdapter` | Synthetic Git repo under `tmp_path`; crash-at-every-point matrix; second write impossible; target bytes unchanged on every refusal |
| **S4** Verification adapter | Verification evidence v2 binding, `VerificationAdapter` | Synthetic repo + synthetic verification script under `tmp_path`; caller-provided JSON/digest refused; binding mismatches refused |
| **S5** Reviewer adapter | Review recorder, binding reader, `ReviewerAdapter` | `httpx.MockTransport` only; no socket; double-verification disagreement → RECOVERY_REQUIRED; verdict re-derived |
| **S6** Acceptance lifecycle | DL-2 hold branch (store.v4 only), `hold_acceptance_decision`, `held_acceptance_bundle`, acceptance subject v2, `AlphaPlannerRule` | Hold survives crash and restart; no second planner dispatch; DL-3 unchanged and does not escalate; decline path; v2/v3 R-9 behavior byte-identical |
| **S7** Alpha driver (needs C-1 resolved) | Gated entry point that wires S1–S6 for the three invocations; an offline dry run end to end with mocks and synthetic repo | Full chain COMPLETE offline; every abort rule; banner names provider, host, transport (5F2E) |

**Then, separately authorized:** AUTH-PILOT (E-1…E-10), then one live Alpha.

S1 and S2 can proceed in parallel. S3–S5 depend on S2. S6 depends on S2. S7
depends on all of them.

---

## 12. Adversarial test strategy

Every refusal test asserts an unchanged snapshot of all store tables **and**
the workspace bytes, and that no harness function was called (spies on the
imported 5F2C/5F2D/5F2E entry points).

| Category | Representative cases |
|---|---|
| Forged approvals | Wrong key; registry-unknown key; revoked key (fresh and re-proof); missing presence flag; wrong namespace; wrong application; signature over a different statement; statement for another state root; replayed consumed attestation; expired challenge; a typed phrase with an empty proof |
| Registry attacks | Writable file; writable directory (add file, delete child); reparse point; elevated process; registry replaced between two proofs |
| Caller-supplied proof | JSON report bytes passed to any public API; a matching digest; a `VerificationObservation`, `ReviewProposal` or `ImplementationReport` without evidence; a recorder obtained through `open_authority_session` against a v4 file |
| Mismatched valid objects | Config digest ≠ scope; config workspace ≠ activated workspace; artifact pre-image ≠ scope; artifact path ≠ scope; HEAD ≠ `base_head_oid`; report `target.path` ≠ scope; report `approved_by` ≠ H6; packet's embedded verification ≠ `verified`; presented envelope ≠ held |
| Crash matrix | `BaseException` injected before and after every commit in claim → write → record → transition, for each dispatch; each restart must end in RECOVERY_REQUIRED or held, never resume, never write twice |
| Double effect | A second exact-diff approval for the same step; re-entrant port; a second DL-3 call; a second session on the same root |
| Lifecycle | Hold with each non-accept recommendation (must apply, not hold); hold at a stale version; acceptance with a re-signed or different attestation; decline then accept; escalation carrying the held envelope (refused) |
| Filesystem | Workspace junction swap between check and adapter use (detected or refused); staging substitution (DL-4A); evidence blob tampered after record |
| Disclosure | Refusal strings never contain a proof, key blob, base URL, credential, workspace absolute path beyond DL-4A's existing outputs, or artifact/diff content (scanned in tests) |
| Boundaries | Static tests: no subprocess, network or environment import in `control_plane/`; the only removal is DL-4A's; no `max_tokens` introduced; no CLI option naming path, model, endpoint, key or timeout |
| Both paths | Every refusal reached through the direct store API **and** through DL-3 → DL-2 → adapters |

No test uses a real model, a socket, a real authenticator, a real target
project or a real verification executable.

---

## 13. Explicit deferred risks

| Id | Risk | Alpha mitigation | Owner |
|---|---|---|---|
| D-1 | Planner output origin is unauthenticated (R-3) | Deterministic planner; the human signs the planner envelope digest; the Alpha profile forces human acceptance | Post-Alpha |
| D-2 | T3 can rewrite evidence blobs and rows consistently **before** the human reviews them; the signature covers what the human was shown, which may already be forged | Trusted target repository named in AUTH-PILOT; disposable clone; the human inspects the clone directly; approvals cannot be forged (FD-4) | Accepted for Alpha; needs account separation later |
| D-3 | Path-based containment races (R-5) | 5F2C/5F2D detection; fail closed | Accepted residual |
| D-4 | Persistent `AIDO_*` values in the process environment block are readable by a same-account child | 5F2D allowlist; confirm environment hygiene (E-8) | Inherited (5F2E) |
| D-5 | Same-host signing lets T3 swap the statement before the touch | Separate signing device recommended (FD-2) | AUTH-PILOT |
| D-6 | Verification descendants and abandoned reviewer workers outlive the invocation | Documented 5F2D/RS1 limits; never claimed stopped | Inherited |
| D-7 | Restore of an older state root (R-4) | Archived evidence; re-proof checks signatures, not freshness | Accepted residual |
| D-8 | Host clock and challenge TTL (R-8) | Operator trust root | Accepted residual |
| D-9 | Two verification runs may disagree (flaky project tests) | Fail closed | Accepted |
| D-10 | P1B's live path requires LiteLLM; vLLM is refused there | Availability is an entry criterion (E-7) | Infrastructure |
| D-11 | Revocation is total and can retroactively untrust completed runs | Intended fail-closed behavior | Accepted |
| D-12 | Step-contract.v2 (write scope, baseline identity) deferred | One-step Alpha only (FD-8a) | Multi-step phase |

---

## 14. One-step human-supervised Alpha entry criteria

All must hold, each evidenced, before a live Alpha is authorized:

- **E-1** DL-4A and FU1 independently accepted; ALPHA-P1B acceptance confirmed (C-9).
- **E-2** This design accepted, with FD-1…FD-12 frozen, and C-1 and C-8
  decided by the user, including any `CLAUDE.md` update the user makes.
- **E-3** Slices S1–S7 implemented, independently accepted, full suite green, offline dry run COMPLETE.
- **E-4** AUTH-PILOT signed by the human, naming: the repository (trusted for
  T3), the disposable clone path, the one file, the write scope (pre-image
  hash, base HEAD), the project config digest, the verification argv, the
  reviewer provider, endpoint and model, P1B's model, and the signing device.
- **E-5** Approver registry provisioned with elevation; the integration session's protection check passes; AIDO runs non-elevated.
- **E-6** Real-authenticator rehearsal: one throwaway challenge signed and verified in a throwaway state root.
- **E-7** LiteLLM reachable for P1B, and the reviewer endpoint matches `controlled_review.endpoint`.
- **E-8** Environment hygiene re-checked (no unexpected persistent credentials; the ALPHA-1B prep facts revisited).
- **E-9** The state root is an empty, non-Git, operator-owned directory, disjoint from the clone; the clone is clean at the scope's HEAD.
- **E-10** Abort rules acknowledged: any refusal, RECOVERY_REQUIRED, HUMAN_REQUIRED, containment error or untrusted proof ends the Alpha, with no retry, repair or cleanup. No branch, commit, push or PR.

---

## 15. Final report

1. **Recommended architecture.** An integration store (store.v4) with:
   hardware-signed human attestations verified against an AIDO-unwritable
   registry; three deterministic harness adapters (5F2C write, 5F2D verify,
   5F2E review) that alone hold session-only evidence recorders and take every
   input from the store; a durable write intent before the single write; a
   persisted hold at ACCEPTANCE; and a three-invocation process split, so that
   no model credential is in AIDO's process state when repository code runs.
2. **Required trust sources and prerequisites.** A FIDO2 authenticator with
   user presence; an elevated, one-time registry provisioning; a
   non-elevated AIDO process; the `cryptography` dependency; the accepted
   harness code at a pinned commit; LiteLLM availability for P1B; and a
   trusted target repository in a disposable clone.
3. **Contradictions with frozen contracts.** None changed silently. Nine
   tensions are listed in §9. C-1 (a fifth model-calling surface versus
   `CLAUDE.md`) and C-8 (DL files versus ALPHA-1B's S0 pin) need user
   decisions. C-2 (double verification), C-3 (R-9 versus hold), C-4 (ordering
   versus DL-4A's sketch), C-5 (write scope placement), C-6 (widened trust
   root) and C-7 (closed subject enum) are resolved by versioning or explicit
   acknowledgement.
4. **Proposed implementation phases.** S1 verifier ∥ S2 integration store →
   S3 exact diff + write harness, S4 verification adapter, S5 reviewer adapter,
   S6 acceptance lifecycle → S7 gated Alpha driver and offline dry run → AUTH-PILOT
   → live Alpha. Each step needs separate authorization.
5. **Remaining blockers to a real Alpha.** E-1…E-10. Specifically: DL-4A
   acceptance; this design's acceptance; the C-1 and C-8 user decisions;
   S1–S7; the authenticator and registry; P1B acceptance confirmation;
   LiteLLM availability; and AUTH-PILOT.

**Final status: DESIGN COMPLETE — PENDING INDEPENDENT REVIEW.**
