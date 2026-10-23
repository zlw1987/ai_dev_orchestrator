# DL-4B — Real Integration Boundary Design

**Status: DESIGN AMENDED (AMEND1) — PENDING INDEPENDENT REVIEW.**

| | |
|---|---|
| Baseline | `main` at `c0daaea072a4eeb1e2383df1a15aa671824e9563` (DL-1, DL-2, DL-3 + FU1, DL-4A + FU1) |
| AMEND1 baseline | `main` at `a3f8d60408ac6f23b0124a0584871bde55bf6b45` (this document as first proposed) |
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

### AMEND1 — evidence isolation and reviewer authority

AMEND1 corrects two authority boundaries the first proposal left open, and
keeps every other decision. Text it changes is marked **(AMEND1)**.

| Finding | First proposal | AMEND1 position |
|---|---|---|
| **F-1** Repository code controlled authoritative evidence | Repository-controlled code (T3) ran as the operator account. That account owned the state root, the store, the evidence blobs and the integration process. Session-only recorders and matching digests were presented as provenance, but T3 could rewrite rows and blobs consistently (old D-2), and a later signature could not make a forged record genuine. | Three distinct, non-administrative Windows accounts (FD-13). The **authority identity** owns the state root and runs the integration session. It runs no harness, no Git, no subprocess and no model. The **execution identity** runs everything that touches or executes repository content, and the OS denies it every write, delete and re-permission right over what the authority identity relies on (FD-14). What the execution identity returns is recorded as an **execution claim**: it can refuse a step but never prove one. Authority-plane evidence is limited to the authority identity's own records and its own observations of the clone (FD-15, FD-18). A refuses to open an integration session unless it mechanically re-proves the boundary, and there is no same-account mode (FD-16). |
| **F-2** Fifth model-calling surface | The Alpha driver called 5F2E in-process (old C-1). | The driver calls no model. The human runs the **existing, unchanged** `l2-review-approved-file-edit` as the execution identity. Its single 5F2D run and its packet answer both the VERIFYING and the REVIEWING dispatch (§5.6). The four-command rule holds without any `CLAUDE.md` change, and the double verification (old C-2) disappears. |

**Decisions already resolved (recorded, not re-opened).** C-8: the DL Alpha uses
a separate checkout and runbook, and ALPHA-1B S0 is preserved unchanged. C-9:
ALPHA-P1B acceptance must be verified from authoritative historical evidence,
and the gate stays pending until that is done. FIDO2 remains the proposed
approval mechanism, subject to its implementation prerequisites.

**A frozen-contract fact found during AMEND1 (C-10).** The frozen Git adapter
forwards no `HOME` or `USERPROFILE` and sets `GIT_CONFIG_NOSYSTEM`, so no
`safe.directory` entry can reach it. Git therefore refuses a repository that is
not owned by the invoking account. Every Git-using harness (P1B, 5F2C, 5F2D)
must run as the clone's owner. Because 5F2D must run as the execution identity,
the execution identity owns the clone. P1B and the 5F2C write therefore also
run as the execution identity, through their existing commands, and the
authority identity runs no Git at all.

---

## 0. Summary

DL-4A made every authority record *issued and bound*. It left five things
dependent on sources outside its reach. DL-4B closes them as follows.

| # | Boundary | DL-4B answer, one line |
|---|---|---|
| 1 | Human authentication | A FIDO2 hardware authenticator signs an AIDO challenge statement (OpenSSH `SSHSIG`, `sk-ssh-ed25519`, user-presence required). AIDO verifies in-process against an approver registry the AIDO account **cannot write**. The private key never exists in the AIDO process or account. |
| 2 | Verification evidence **(AMEND1)** | The human runs the existing `l2-review-approved-file-edit` as the execution identity. The authority identity's adapter publishes that command's inputs from the store and records its stdout as an **execution claim** bound to the dispatch. Separately, it records its **own** non-Git observation of the clone: the target's bytes, the `.git` control files and a working-tree manifest. Only that observation, together with the authority identity's own records, is authority-plane evidence. A claim that disagrees with it refuses the step. |
| 3 | Human acceptance lifecycle | In the integration store only, DL-2 **holds** a valid planner `RECOMMEND_STEP_ACCEPT` that lacks only human acceptance, as a persisted held decision, and stops. It does not escalate. A later process presents a signed acceptance over a subject that binds every piece of evidence the human saw. That subject labels which parts are execution claims. |
| 4 | Role-output origin **(AMEND1)** | The implementer, verifier and reviewer dispatches are answered only by authority-identity adapters that hold session-only recorders. Those recorders record claims and observations, never harness calls. The store refuses those role outputs without the matching claim **and** observation. The planner stays unauthenticated (deterministic AIDO rule for the Alpha). The Alpha policy profile **mechanically** requires human acceptance. |
| 5 | Workspace authority **(AMEND1)** | The model proposal (P1B, unchanged) and the human exact-diff approval come **before** the step attempt. The only workspace effect is the 5F2C write, run by the human through the existing `l2-apply-approved-file-edit` as the execution identity. It happens **inside** the EXECUTING dispatch, after a durable write intent and handoff. The authority identity's before/after observation decides what happened. Crash, refusal and indeterminacy all end in RECOVERY_REQUIRED, never in repair. |
| 6 | Execution isolation **(AMEND1)** | Authority (A), execution (X) and operator (O) are distinct, non-administrative Windows accounts. X has no write, delete or re-permission right over the state root, the AIDO install, the identity and approver anchors, A's processes, or the clone's `.git`. A re-proves this on every session open and every dispatch, and refuses otherwise (§5.8). |

The design introduces a new store schema (`aido-control-plane-store.v4`, the
*integration store*). It leaves `store.v2`, `store.v3`, every DL-1 model and
every frozen 5F2C/5F2D/5F2E/P1B contract unchanged. **(AMEND1)** It also leaves
every frozen command's execution semantics unchanged. Those commands are run by
the human, as the execution identity, exactly as they run today.

---

## 1. Scope

**In scope.** The authority, evidence and lifecycle design that lets the
accepted control plane (DL-1 → DL-4A) drive the accepted harnesses (5F2C,
5F2D, 5F2E, P1B) for one step, with a human at every authority boundary.
**(AMEND1)** "Drive" means: publish their inputs and receive their outputs.
The harnesses run through their existing commands, executed by the human as the
execution identity.

**Out of scope, deliberately.** Multi-step plans; more than one attempt;
re-planning or activating a plan for an existing run; project completion
(DL-1's `request_complete` refusal stands); any exit from HUMAN_REQUIRED or
RECOVERY_REQUIRED; Pi or any qualified harness; an autonomous implementer; a
fixer; branch, commit, push or PR; any product-level model token cap; any
sandbox; any new subprocess capability. **(AMEND1)** Also out of scope: any
change to how 5F2C, 5F2D, 5F2E or P1B launch or execute (no token, integrity
level, job object, AppContainer or environment change); any process launched by
AIDO under any identity; process-tree management; and the act of Windows
account provisioning itself, which is an elevated human prerequisite (§5.8.2).

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

**(AMEND1)** As first proposed, "where they cannot reach" was false. The state
root, the evidence blobs and the integration process all lived in the same
account as T3. Recorders and digests prove which code path *wrote* a record
only while no one else can write it. A human signature over a forged record
proves only that the human saw the forgery. AMEND1 therefore makes "cannot
reach" an OS-enforced fact. Repository content is touched and executed only by
a separate execution identity (X). Every authority-plane object belongs to an
authority identity (A) that X cannot write, delete, re-permission or open
(§5.8). A same-account deployment is not a weaker mode of this design; it is
refused (FD-16).

### 2.2 Threats in scope

| Id | Adversary | What it must not be able to do |
|---|---|---|
| T1 | AIDO operator-side code (composition root, adapters, loops), through a bug or a model-steered input | Produce any human approval; record verification or review evidence that no shipped harness produced; make a role output count without its dispatch. **(AMEND1)** Under AMEND1: record a claim from anywhere but the outbox A created for that ticket, or an observation A did not itself take |
| T2 | A model (implementer, reviewer) or any role output | Select a path, command, workspace, state, policy or approval; be mistaken for AIDO-observed evidence |
| T3 **(AMEND1)** | Repository-controlled code run by 5F2D (inside the existing review command) and all its descendants, which may outlive the run indefinitely. It always runs as the execution identity X, and it may run before, during and after any later X invocation | Create, rewrite, delete or consistently forge any authority-plane record, blob or observation. Read or alter the integration process, its token or its code. Alter the clone's `.git` (HEAD, refs, index, config, hooks). Forge a human approval. Replace the approver registry or the identity boundary. Cause a second AIDO-authorized write. Turn an untrusted run into a trusted one that re-proves. Reach O's or A's desktop, profile or credentials |
| T4 | A supported library caller | Present a caller-built JSON report, a digest, or a constructed model as proof of execution or approval |
| T5 | A crash or kill at any instruction | Leave a state from which a resumed action can repeat an external effect or appear proven |

**(AMEND1) What T3 can still do, stated rather than hidden.** T3 controls the
verification outcome by construction: it *is* the project's verification. Under
the frozen 5F2E contract it also runs inside the process that calls the
reviewer, so it can reach the review packet and the reviewer credential of that
one invocation. It can write the clone's working tree, which X owns. These
outputs are therefore **execution claims** (FD-15). They can refuse a step and
they inform the human, but they never establish an authority-plane fact. The
threat model is not narrowed: T3 is still a full adversary. What changes is the
classification of what it can touch. Moving these outputs onto the authority
plane would need a change to frozen 5F2D/5F2E execution semantics (C-11), which
this amendment does not propose.

### 2.3 Out of scope, stated rather than claimed

A malicious human approver; a malicious operator with administrative rights;
the AIDO source at the reviewed, pinned commit being itself malicious (code
review is that control); kernel or admin compromise; physical attack on the
authenticator; a deliberate consistent rewrite **plus** rollback of the
state root by an actor who also holds a valid authenticator (R-4, narrowed in
§13); and in-process code reaching private attributes (DL-4A §2, unchanged).
**(AMEND1)** Also out of scope: any administrator account or SYSTEM-level
actor, since the boundary is ordinary Windows access control and an
administrator can change it. Also out of scope: a human who deliberately runs
repository-controlled code **as the authority identity**, for example by
opening the clone in an IDE while signed in as A. That hands A's authority to
the repository. The runbook forbids it, A is a dedicated account that runs
nothing but AIDO, and A detects only the parts it can (§5.8.6). Running
repository code as the operator identity is **not** out of scope. It is a
residual confined to O's resources (D-16).

### 2.4 Trust sources DL-4B relies on

| Source | Why it is trusted | What it anchors |
|---|---|---|
| FIDO2 authenticator with user presence | The private key is non-exportable; each signature needs a physical touch | Every human approval (FD-1) |
| Approver registry not writable by the AIDO account | Provisioned with elevation into a fixed admin-owned path. AIDO refuses it if writable or replaceable by its own token, and refuses to run elevated | Which public keys are approvers (FD-2) |
| The shipped 5F2C / 5F2D / 5F2E / P1B code at the pinned commit | Independently accepted contracts; run unchanged by their existing commands, never reimplemented | **(AMEND1)** The *content* of execution claims, never authority-plane facts |
| The integration session's construction | The only place recorders are minted, and they never leave the adapters | Evidence origin (FD-6) |
| **(AMEND1)** Windows account separation: A ≠ X ≠ O, none administrative | OS access checks on files, directories, processes and tokens, and per-logon-session window stations. These are kernel-enforced, not AIDO conventions. They are provisioned once with elevation, and A re-proves them mechanically | That X cannot write, delete, re-permission or open anything on the authority plane (FD-13, FD-14, FD-16) |
| **(AMEND1)** `identity-boundary.v1` at a code-constant admin-owned path | Same anchor protection as the approver registry | Which SIDs are A, X and O, and which paths are the state root, exchange root and clone (FD-16) |
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
| **Write intent** (`write-intent.v1`) **(AMEND1)** | The write handoff adapter (A), through the store | Row bound to the implementer ticket and the consumed exact-diff approval | No API publishes a write handoff without one | — | The handoff is published only after the intent commits; A's before/after observation decides the intent's final state | Intent committed, then crash → step EXECUTING → `recover()` → RECOVERY_REQUIRED; approval already spent, so no second AIDO-authorized write is possible | — | — |
| **Execution claim** (`execution-claim.v1`) **(AMEND1)** | Produced inside X by a human-run existing command (T3-reachable once repository code has run). Received by A's claim recorder from the store-computed per-ticket outbox | **None beyond receipt.** A records *that* these stdout bytes arrived for this ticket, under the FD-17 protocol, at this time. It does not record that 5F2C, 5F2D or 5F2E produced them | No API accepts claim bytes from a caller; the receiver reads only the outbox it created for the ticket | Claim's target path, approval identity and pre/post-image hashes vs scope, H6 and A's observation; any disagreement refuses | Re-parsed and re-bound on every proof | Write-once; a second, partial, late or extra-file claim is refused | **This is the point.** A claim is never authority-plane evidence. It can refuse a step, and it can only move a step toward a human | Stdout is 5F2D-redacted and 5F2E-bounded (a backstop, not a guarantee); stored, never printed |
| **Authority observation** (`authority-observation.v1`, M0/M1/M2) **(AMEND1)** | A's observation recorder (session-only), with no Git and no subprocess | A's own reads: target bytes, `.git` control-file digests, detached-HEAD oid, and a working-tree manifest, all refusing reparse points and multiply-linked files (FD-18) | Recorder never exposed; no API accepts an observation from a caller | M0→M1 must differ in exactly the target, pre→post. M1→M2 must leave every M1 path and `.git` unchanged | Re-derived on every proof from the stored manifests | Publish-then-insert | No | Repo-relative paths, sizes and digests only |
| **Write evidence** **(AMEND1)** | The write claim (stdout of `l2-apply-approved-file-edit`) plus observations M0 and M1 | M0/M1 are authority-plane. The `workspace-write-result.v1` bytes are a claim | Recorders not exposed (FD-6) | Claim `target.path`, `approved_by`/`approved_at` and hashes vs scope, H6 and M1 → store checks | Re-hashed and re-parsed on every proof | Publish-then-insert (DL-4A pattern) | An `ImplementationReport`'s claims are never consulted. M1 decides whether the write happened | `git.target_diff` is repository text; stored, never logged |
| **Verification and review observations** **(AMEND1)** | Derived by A from **one** execution claim (stdout of `l2-review-approved-file-edit`) plus observation M2 | M2 is authority-plane. The `verification-result.v1` bytes (embedded in `review-packet.v5`, or bare on exit 2/3) and the verdict are claims | Recorders not exposed; store.v4 cannot be opened by DL-4A's session (schema mismatch) | Claim target, approval identity and post-image vs scope, H6 and M2 | Outcome and verdict re-derived from the stored claim bytes on every proof. The review observation must reference the same claim as the verification observation of the same attempt | DL-4A pattern | A forged `verified` or `approve` can only bring a step to a human-held ACCEPTANCE. It cannot cause a write, an approval or COMPLETE | The packet holds the diff; stored, never printed |
| **Identity boundary** (`identity-boundary.v1`) **(AMEND1)** | The human, elevated, once. Never AIDO | Code-constant admin-owned path; same anchor checks as the registry | Not config, not CLI | — | Re-read and re-proven on every session open and before every dispatch | Read-only to A and X | — | SIDs and fingerprints only |
| **Dispatch ticket** | Store (DL-4A, unchanged) | Persisted row | DL-4A closed | — | DL-4A + store.v4 evidence requirement per role | DL-4A | A ticket proves intent, never the producer (§5.4) | — |
| **Held planner decision** | DL-2 through `hold_acceptance_decision`; nobody mutates it | Ticket row marked held with the envelope bytes | A second planner ticket per version is refused (DL-4A); the decision is read back from the store, never from the caller | Held envelope vs a presented one → canonical equality required | At acceptance: the presented envelope must equal the held one | Persisted; ACCEPTANCE is not in flight, so `recover()` leaves it | The planner's recommendation never completes a step without a signed human acceptance | — |
| **Step acceptance v2** | The human signs | Signature over a subject binding attempt, version, write, verification, review and planner evidence digests | DL-4A closed | Every digest is recomputed from store rows | DL-4A + v2 subject | One transaction | — | — |

### 3.2 Lifecycle transitions

| Transition | Who causes it | External effect | Crash before / after | Revalidated |
|---|---|---|---|---|
| P1B proposal (outside the control plane) **(AMEND1)** | The human runs the existing `l2-supervised-implementer-run` **as X**, before any repository code has run in X (C-10) | One model request (P1B ledger) | P1B's own semantics; the control plane has nothing to resume | Nothing in it is authority |
| Exact-diff approval recorded | Human + store | None | Atomic | Subject recomputed from stored artifact bytes |
| READY → EXECUTING | DL-2 `BEGIN_ATTEMPT` | None | DL-1 unchanged | DL-1 |
| EXECUTING dispatch: M0 → intent → write handoff → human-run 5F2C as X → M1 **(AMEND1)** | Write handoff adapter (A); the human (X) | **Workspace write** (by X) | After intent, at any point → RECOVERY_REQUIRED; no retry | Intent requires an unconsumed matching H6 approval, a re-proven boundary and workspace, and M0 equal to the scope's pre-image and base HEAD |
| EXECUTING → VERIFYING | `IMPLEMENTATION_RETURNED` | None | DL-1 unchanged | store.v4: write claim **and** M1 for this ticket required |
| VERIFYING dispatch: review handoff → human-run `l2-review-approved-file-edit` as X → M2 **(AMEND1)** | Execution claim adapter (A); the human (X) | **One repository-controlled execution; one or two model requests (RS1)**, all inside X | → RECOVERY_REQUIRED | Inputs published from the store only; claim bound to scope, H6 and M2 |
| VERIFYING → REVIEWING / ACCEPTANCE / RECOVERY_REQUIRED | `VERIFICATION_OBSERVED` | None | DL-1 unchanged | DL-4A + v2 binding + M2 |
| REVIEWING dispatch **(AMEND1)** | Execution claim adapter (A), answering from the claim already recorded for this attempt | **None.** No second execution and no second model call | → RECOVERY_REQUIRED | The claim must be the one whose verification part produced the VERIFYING observation |
| REVIEWING → ACCEPTANCE | `REVIEW_OBSERVED` | None | DL-1 unchanged | store.v4: review evidence required |
| ACCEPTANCE: planner dispatch → hold | DL-2 | None | Held row persisted atomically, or not at all | Dry-run validator must refuse with exactly `HUMAN_ACCEPTANCE_MISSING` |
| ACCEPTANCE → COMPLETE | Human, new process | None | Atomic | Signed v2 acceptance; held envelope equality |
| ACCEPTANCE → HUMAN_REQUIRED | Human declines (`ESCALATE`) | None | Atomic | DL-1 unchanged; carries no attestation (FU1) |

---

## 4. Recommended architecture

**(AMEND1)** The diagram is redrawn around three identities. Every arrow that
crosses an identity line is a file in a directory whose ACL fixes the
direction (FD-14). No process of one identity starts, opens or signals a
process of another.

```text
 SIGNING DEVICE (human)     ADMIN-OWNED, READ-ONLY TO A, X, O
 ┌──────────────────┐       %ProgramData%\AIDO\approver-registry.v1.json
 │ FIDO2 key + touch│       %ProgramData%\AIDO\identity-boundary.v1.json   (SIDs of A, X, O; paths)
 │ ssh-keygen -Y    │       AIDO install / venv / interpreter (read+execute only)
 │  sign            │
 └──▲───────┬───────┘
    │stmt   │SSHSIG
 ┌──┴───────▼─────────────┐     inbox/ (O: add-file; A: read)
 │ O  OPERATOR (human's   │ ───────────────────────────────────────┐
 │    own interactive     │ ◄── published/ (A: write; O: read) ──┐ │
 │    account)            │                                      │ │
 │  reads bundles; never  │                                      │ ▼
 │  runs repository code  │     ┌──────────────────────────────────────────────────────────┐
 └────────────────────────┘     │ A  AUTHORITY (dedicated, non-admin, own logon session)   │
                                │  integration session (store.v4) — no harness, no Git,    │
                                │  no subprocess, no network, no model, no credential      │
                                │  ├─ BoundaryProof (FD-16)        re-proven every dispatch │
                                │  ├─ RegistryHumanAttestationVerifier (pure)              │
                                │  ├─ WriteHandoffAdapter    ─ claim + observation recorder │
                                │  ├─ ExecutionClaimAdapter  ─ claim + observation recorder │
                                │  └─ AlphaPlannerRule       ─ deterministic, no recorder   │
                                │  DL-3 → DL-2 → bound ports → store (all checks here)     │
                                │  STATE ROOT (A-only DACL): store.v4 · evidence/ · staging │
                                └──────┬───────────────────────────▲───────────────────────┘
                     exchange/handoff/<ticket>/ (A: write;  exchange/outbox/<ticket>/
                       X: read) — artifact + config bytes   (X: add-file; A: read only)
                                       ▼                           │ stdout claim + marker
                                ┌──────────────────────────────────┴───────────────────────┐
                                │ X  EXECUTION (dedicated, non-admin, own logon session)    │
                                │  human runs EXISTING commands, unchanged:                 │
                                │   l2-supervised-implementer-prepare / -run   (P1B)        │
                                │   l2-apply-approved-file-edit                (5F2C)       │
                                │   l2-review-approved-file-edit  (5F2D, then 5F2E)         │
                                │  T3 lives here from the first 5F2D run onward             │
                                └──────┬───────────────────────────────────────────────────┘
                                       │ owns working tree; .git is READ-ONLY to X
                                       ▼
                     DISPOSABLE CLONE (owner X; detached HEAD at base_head_oid; A: read)
```

**Process separation (FD-9, AMEND1).** All invocations are split only at
non-in-flight boundaries, except the attempt, which stays alive across its two
human-run executions:

1. **Approvals** (A): project contract, plan activation (which now binds the
   identity-boundary digest) and exact diff. They are short and run no harness.
   O places signatures and the approved artifact in A's inbox.
2. **Proposal** (X, human-run): the existing P1B commands, unchanged. This runs
   before any repository code has run in X (E-11). P1B's LiteLLM values exist
   only in that console's environment, never persistently in X's profile.
3. **Attempt** (A, one long-lived invocation): drives the step from READY to
   the held ACCEPTANCE. Inside EXECUTING it publishes the write handoff and
   waits for the write claim. Inside VERIFYING it publishes the review handoff
   and waits for the review claim. It reads **no** credential, ever.
   - 3a. **Write** (X, human-run): `l2-apply-approved-file-edit`, stdout to
     the outbox.
   - 3b. **Verify + review** (X, human-run): `l2-review-approved-file-edit`,
     stdout to the outbox. 5F2E reads reviewer credentials only after its own
     verification, as frozen, and only in X.
4. **Acceptance** (A, fresh invocation): presents the human's signed
   acceptance. It runs nothing.

A's invocations run either as admin-provisioned Task Scheduler tasks with an
S4U principal (non-interactive, no stored password, fixed action), or in A's
own interactive session reached through the Windows secure logon UI. X's
commands run only in X's own interactive session. Starting any identity's
process on another identity's desktop (`runas`, `Start-Process -Credential`) is
forbidden, because one desktop shares input, hooks and window messages across
accounts (§5.8.2).

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
| Anchor protection, checked mechanically on every read | (a) path is the constant, not config; (b) not a reparse point in any component; (c) the current token has neither write, append, delete nor `WRITE_DAC`/`WRITE_OWNER` on the file, and neither add-file nor delete-child on its directory (Win32 access check); (d) the AIDO process token is **not elevated**; **(AMEND1)** (e) the same rights are evaluated for the execution identity's SID from `identity-boundary.v1`, through an AuthZ client context with X's real group memberships, and must be absent. Any failure → the verifier refuses everything |
| Signing device | **Recommended: a device other than the AIDO host.** This defeats T3 swapping the statement between display and signing. The AUTH-PILOT must state which device is used. Same-host signing is permitted only with that residual acknowledged (D-5). **(AMEND1)** On the host, signing happens in O's session, which X cannot reach while the boundary holds; never in X's session |
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
corrupt (fail closed), but not forge. **(AMEND1)** Under FD-14, T3 cannot write
the DB at all. FD-4 remains as defense in depth against A-side (T1) corruption,
against restoration of an older state root (D-7), and against revocation.

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
constructs the evidence-producing adapters itself. Each recorder is
minted and handed directly to its adapter. The session exposes the store, the
bound role ports and nothing else. There is **no** `verification_recorder`
attribute. Because store.v3 and store.v4 cannot open each other's files
(DL-4A's mechanism), DL-4A's session cannot be pointed at an integration store
to obtain a recorder. **(AMEND1)** There are two recorder kinds. The **claim
recorder** records the bytes received under FD-17. The **observation recorder**
records A's own FD-18 observations. Neither records the result of a harness
call, because no harness runs in A. `open_integration_session` runs the FD-16
boundary proof first and opens nothing if it fails.

**(AMEND1) Why the first algorithm is withdrawn.** It called
`verify_approved_file_edit` in-process. That launches repository code as the
calling account, so the descendants would share A's identity and could rewrite
everything the recorder had just written. It is replaced by a handoff to X and
an A-side observation.

**Execution claim adapter, VERIFYING half** (`verify(step_contract, attempt,
dispatch)`, AMEND1):

1. Re-run the FD-16 boundary proof. Read from the store, never from the caller:
   the step's write scope, the completed write intent of this attempt, the
   approved-diff artifact bytes, and `authorized_target_workspace(project_run_id)`.
2. Check that the session's project config bytes hash to the scope's
   `project_config_sha256`, and that the config's configured workspace root
   resolves to the authorized workspace by canonical path **and** directory
   identity. Check also that the config's `controlled_verification` and
   `controlled_review` blocks are enabled. A does not read their values
   further: it never launches anything.
3. Create `exchange/handoff/<dispatch-ticket-id>/` holding exactly two files:
   the approved artifact bytes and the session's config bytes. Then create
   `exchange/outbox/<dispatch-ticket-id>/`, each with the FD-14 DACL set at
   creation. Refuse if either already exists. Record an `execution-handoff.v1`
   row (ticket, both digests, directory identities, `created_at`) and
   **commit before waiting**.
4. Wait, to a fixed code-constant bound (FD-17), for exactly one complete claim
   in the outbox. The human runs the existing `l2-review-approved-file-edit`
   with `--project-config` and `--approved-diff-proposal` pointing into the
   handoff directory and both explicit flags, as X, and places its stdout
   there under the FD-17 protocol. Deadline, protocol violation or empty
   stdout → record nothing authoritative and raise → RECOVERY_REQUIRED.
5. Classify the claim by **strict** parse of the stdout bytes, and by nothing
   else (the exit code is not trusted either):
   - a `ReviewPacket` → exit-0 shape; verification `verified`;
   - a bare `VerificationResultReport` with outcome `verification-failed` →
     exit-2 shape;
   - outcome `workspace-state-untrusted` → exit-3 shape;
   - anything else → raise.
6. Record the claim bytes with the claim recorder. Take observation **M2**
   (FD-18) and record it with the observation recorder.
7. Return a `BoundRoleOutput` of a `VerificationObservation` built from the
   **receipt**, never from the parsed object.

**Store-side binding (v2), enforced at record time and on every proof.** In
addition to DL-4A's checks, store.v4:

- parses the claim with the extended mirror reader, which also returns
  `target.path`, `target.change_type`, `approved_by`, `approved_at`, the
  post-image digest and the identity tuple (`project_id`, `repo`,
  `issue_number`, `title`). For an exit-0 shape it reads the embedded
  `packet.verification`;
- requires `target.path == write_scope.path` and `change_type == "modify"`;
- requires `approved_by`/`approved_at` to equal the consumed exact-diff
  approval's attested approver and time;
- requires the identity tuple to equal the approved artifact's identity;
- requires the ticket's step to have a **completed write intent** for this
  attempt;
- **(AMEND1)** requires M2 to hold: target bytes equal to the scope's
  post-image; `.git` control digest and detached HEAD equal to M1; every M1
  path present and unchanged. Additions are recorded for the human, not
  refused (an ignored test cache is legitimate, and A cannot evaluate
  `.gitignore` without Git). An outcome of `verified` with a failing M2 is
  refused, and the step goes to RECOVERY_REQUIRED;
- records, in the evidence row: ticket, step run, attempt, write-intent id,
  write-scope digest, the workspace identity digest re-proven at record time,
  claim digest, M2 digest, the classified outcome and the fixed provenance
  label `execution_claim`.

A caller-provided JSON report, or a matching SHA-256 alone, has no path into
this. Only a recorder can record, only the adapter holds one, and the adapter
reads only the outbox it created. **(AMEND1)** Even a correctly received claim
is not authority-plane evidence (FD-15). What AIDO relies on as fact is M2 and
its own records. The claimed outcome decides only which way the step proceeds
toward a human.

**Frozen semantics preserved (AMEND1).** 5F2D runs exactly as the existing
command runs it. It runs inside the process the human starts as X, so the child
gets X's token because that is what `subprocess` does today. AIDO adds no
launch, no `CreateProcessAsUser`, no restricted token, no integrity level, no
job object, no AppContainer and no environment change. 5F2D's exit classes map
exactly as DL-1 already maps them (`workspace-state-untrusted` →
RECOVERY_REQUIRED). Its environment policy, timeout semantics and "not
sandboxed" statements are untouched and remain literally true. AIDO adds no
claim about the child. The `verification-result.v1` bytes are stored exactly as
they arrived.

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
material. **(AMEND1)** A publishes a copy into `published/`, which O can read
and X cannot reach, so T3 cannot swap what the human is shown after A
published it.

**Completion.** In a fresh session:

1. `request_step_acceptance(step_run_id)` (store.v4) refuses without a held
   decision and computes **`step-acceptance-subject.v2`**: DL-4A's fields plus
   `write_scope_sha256`, `write_evidence_sha256`, `review_evidence_sha256` and
   `planner_envelope_sha256`. The signature thus covers everything the human
   was shown. **(AMEND1)** It also binds `identity_boundary_sha256`, the
   digests of observations M0, M1 and M2, and a fixed
   `claim_provenance: "execution_identity_unauthenticated"` label. The
   bundle's fixed AIDO text states which facts A observed and which values
   (verification outcome and output, review packet and verdict, both harness
   reports) are execution claims that repository code could have produced.
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
| implementer (EXECUTING) **(AMEND1)** | `WriteHandoffAdapter` (A) only; the effect is the human-run `l2-apply-approved-file-edit` as X | A completed write intent, the write claim **and** observations M0 and M1 for this ticket | The proposal content's origin (P1B) is unauthenticated, but it is not authority: the signed exact-diff approval is. The write report is a claim; M1 decides |
| verifier (VERIFYING) **(AMEND1)** | `ExecutionClaimAdapter` (A) only; the execution is the human-run `l2-review-approved-file-edit` as X | The execution claim and observation M2 for this ticket | §13 D-2′ |
| reviewer (REVIEWING) **(AMEND1)** | `ExecutionClaimAdapter` (A) only, answering from the claim already recorded under this attempt's verifier ticket. No second execution | That claim must be an exit-0 shape; `ReviewProposal.evidence_sha256` must equal the claim digest, and its verdict must equal the verdict re-derived from the packet bytes | The verdict is model output, advisory by contract, **and** an execution claim (D-2′) |
| planner (ACCEPTANCE) **(AMEND1)** | `AlphaPlannerRule`: deterministic. `RECOMMEND_STEP_ACCEPT` iff M0/M1/M2 all held, the claimed verification is `verified` and the claimed verdict is `approve`; otherwise `HUMAN_REQUIRED`. No model | None (R-3 stands) | A store holder can mint and answer a planner ticket. Backstop: a signed human acceptance over the planner envelope digest |
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
| implementer (proposal) | ALPHA-P1B live supervised implementer (outside the control plane), run as X | LiteLLM (P1B requires it) | `SUP-D` from P1B's registry | P1B's own evidence; optionally referenced by digest, non-authoritative |
| implementer (dispatch) | 5F2C writer, through its existing command run as X | none | none | write claim + M0/M1 |
| verifier | 5F2D, inside the existing review command run as X | none | none | execution claim + M2 |
| reviewer | 5F2E, the same invocation | `controlled_review.provider` | `controlled_review.model` | inside `review-packet.v5` provenance (itself part of the claim) |
| planner | AIDO deterministic rule | none | none | the envelope |

No control-plane record names a backend, a provider, a model or an endpoint,
preserving DL-4A §6. Those facts live only inside the harness's own evidence.

### 5.5 Workspace authority

**FD-9 Ordering.** The frozen sequence *proposal → human exact-diff approval →
authorized write → verification* maps onto the control plane as follows.

```text
before the attempt (not in flight)        │ inside one attempt (DL-2, in flight)
──────────────────────────────────────────┼───────────────────────────────────────
P1B proposal (X) → human writes frozen    │ BEGIN_ATTEMPT → EXECUTING (A):
DiffEditApproval → signed exact_diff       │   M0 → claim H6 in a write intent → handoff
approval recorded against the write scope  │   → human runs 5F2C as X → M1
                                           │ → VERIFYING: handoff → human runs 5F2D+5F2E
                                           │   as X → M2 → REVIEWING (same claim)
                                           │ → ACCEPTANCE: planner → hold
```

The workspace side effect, the write, is entered under a persisted in-flight
state exactly as DL-1 requires. **(AMEND1)** The human performs it as X, and only
after A has committed the intent and published the handoff. Nothing in A
performs it. The model request precedes the step's intent,
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
  does not reach it. **(AMEND1)** X receives exactly these bytes, copied by A
  into a handoff directory X can read but not write.

**(AMEND1) Write handoff algorithm** (`implement(step_contract, attempt,
dispatch)`). It replaces the in-process write harness, which ran 5F2C and its
Git preflight in A. That is impossible under C-10, because Git refuses an
X-owned repository to A.

1. Re-run the FD-16 boundary proof. Re-prove the workspace and the config
   binding (as in §5.2 step 2).
2. Take observation **M0** (FD-18). Require: target bytes equal to the scope's
   `pre_image_sha256`; `.git/HEAD` equal to exactly `base_head_oid` (detached);
   `.git` control digest equal to the one A recorded at plan activation. A
   reads no Git output and runs no Git operation.
3. In one store transaction, `claim_write_intent(ticket)`: require an
   unconsumed exact-diff approval for this plan issuance and step, whose
   artifact matches the scope. Mark the approval consumed by this ticket,
   insert the intent as `pending` with the M0 digest, and record the
   `execution-handoff.v1` row. **Commit before anything is published.**
4. Publish `exchange/handoff/<ticket>/` (artifact and config bytes) and create
   `exchange/outbox/<ticket>/` (FD-14, FD-17).
5. Wait for one complete claim. The human, as X, runs the existing
   `l2-apply-approved-file-edit` with the handoff paths and its explicit flags.
6. Take observation **M1** and record it. Then decide the effect from M1, never
   from the claim:
   - M1 differs from M0 in **exactly** the target, now equal to the scope's
     post-image, with `.git` unchanged → the write happened as approved;
   - M1 equals M0 → no effect observed;
   - anything else → indeterminate.
7. If the effect is "as approved" **and** the claim strictly parses as
   `workspace-write-result.v1` and binds (`target.path`, `approved_by`/
   `approved_at`, identity and both hashes against the scope, H6 and M1):
   record the claim, mark the intent `completed`, and return an
   `ImplementationReport` whose summary is AIDO's fixed text. Its claims are
   empty and never consulted.
8. Otherwise mark the intent `refused` (no effect observed) or
   `indeterminate` (any other case, including an "as approved" observation with
   a missing or contradicting claim), and raise. DL-2 reduces the step to
   RECOVERY_REQUIRED.

The approval is spent at step 3, so whatever the human or T3 does afterwards,
AIDO never publishes a second write handoff for the step.

**Substitution, partial writes, cleanup and recovery — all fail closed.**

| Event | Detection | Result |
|---|---|---|
| Workspace directory swapped or junctioned | `authorized_target_workspace` identity check (path-based, R-5). **(AMEND1)** X has no DELETE on the clone root and no add-subdirectory on its parent, so X cannot rename the root away | Refusal → RECOVERY_REQUIRED |
| Target file substituted before the write | **(AMEND1)** M0 (authority); 5F2C pre-image SHA-256 (claim) | Refusal → RECOVERY_REQUIRED |
| Substitution between write and verification | **(AMEND1)** M2 compares against M1 (authority); 5F2D precondition (claim) | RECOVERY_REQUIRED |
| Substitution during or after verification | **(AMEND1)** M2 (authority, at its observation time); 5F2D postcondition (claim) | RECOVERY_REQUIRED. A change after M2 is residual D-13 |
| HEAD, ref, index, config or hook change by T3 **(AMEND1)** | **Prevented**, not detected: `.git` is read-only to X (FD-14). M1/M2 `.git` digests confirm it | OS refusal inside X; nothing reaches A |
| Partial or indeterminate write | **(AMEND1)** M1 is neither M0 nor the exact approved change | intent `indeterminate` → RECOVERY_REQUIRED; no retry, no rollback |
| Crash after intent commit | `recover()` sees EXECUTING | RECOVERY_REQUIRED; the approval is spent, so a second AIDO-authorized write is impossible |
| Cleanup | — | **None.** No API restores, cleans or deletes anything in the workspace. DL-4A's single removal (own staging file) is the only removal in DL-4B code, pinned by a static test. **(AMEND1)** A never deletes a handoff or outbox directory either |

**DL-4A containment is not a sandbox.** Every check above is a detection
before or after an action, not a confinement. A concurrent same-account actor
between a check and the next system call is not excluded (R-5). 5F2C's and
5F2D's own detection limits apply unchanged. **(AMEND1)** The only confinement
in this design is the FD-14 access boundary, and it confines what X can do *to
A*. It does not confine what X does to its own working tree, its own profile or
the network, and it claims nothing about them.

### 5.6 Reviewer integration: one execution, existing command, no fifth surface (AMEND1)

**What was wrong.** The first proposal's `ReviewerAdapter` called
`run_controlled_review` in-process from the Alpha driver. That made a fifth
model-calling surface, against `CLAUDE.md`'s four-command rule (old C-1). It
was also wrong twice over under F-1: 5F2E runs 5F2D itself, so the call would
have launched repository code inside A.

**Alternatives considered and rejected.**

| Alternative | Why it fails the frozen contract |
|---|---|
| Driver calls `run_controlled_review` in-process, in A | Fifth model-calling surface; executes repository code as A (destroys F-1) |
| A new X-side "worker" entry point that calls 5F2E | Still a fifth model-calling surface, plus a new entry point that would hold reviewer credentials |
| A launches the existing command as a subprocess | A new subprocess capability (FD-12). Launching it *as X* would also need `CreateProcessAsUser` or `CreateProcessWithLogonW`, so A would hold X's credential |
| A 5F2E variant that takes a verification result from A | Contradicts frozen 5F2E: no `--verification-result`, verify first |

**Compatible integration (adopted).** The human runs the **existing**
`l2-review-approved-file-edit`, unchanged, as X. It keeps its own project
opt-in (`controlled_review`) and its two explicit flags
(`--verify-approved-file-edit`, `--real-reviewer`), with inputs from the
handoff directory. Its frozen behavior already gives A everything it needs on
stdout:

| Exit | Stdout (frozen) | A's classification | Step result |
|---|---|---|---|
| 0 | `review-packet.v5`, which **embeds** the full `verification-result.v1` | verification `verified` + review verdict | VERIFYING → REVIEWING (answered from the same claim) → ACCEPTANCE |
| 2 | bare `verification-result.v1`, outcome `verification-failed` | verification failed | ACCEPTANCE → planner `HUMAN_REQUIRED` |
| 3 | bare report, outcome `workspace-state-untrusted` | untrusted | RECOVERY_REQUIRED |
| 1, 4, other | nothing usable | no claim | RECOVERY_REQUIRED |

So each attempt executes repository-controlled code **once**, not twice
(old C-2 is resolved), and makes at most RS1's two semantic requests. The
REVIEWING dispatch is answered by the same `ExecutionClaimAdapter` from the
claim it recorded under the verifier ticket. The store requires that claim to be
an exit-0 shape from the same attempt. It re-derives the verdict from the packet
bytes, and requires `packet.verification` to be the bytes the VERIFYING
observation was derived from.

**What this preserves.**

- **Model-call gates:** exactly the existing command's gates, typed by the
  human. A calls no model, reads no `AIDO_*` provider name, imports no `llm`
  client and opens no socket (static test).
- **Capability semantics:** RS1, V1, V2 and ALPHA-1A-FU1 are unchanged. AIDO
  adds no `max_tokens`, so `max_output_tokens` stays optional and unset unless
  the project configures it. Credential ordering inside 5F2E is unchanged.
- **Reviewer provenance:** `review-packet.v5`'s own fields, untouched. The
  control plane still records no provider, model or endpoint (DL-4A §6).
- **No new subprocess:** AIDO launches nothing. The OS starts the human's
  command in X's session.
- **Four commands:** unchanged. The A-side driver (S7) is a new **non-model**
  entry point. It is not one of the model-calling commands `CLAUDE.md` limits,
  so the rule needs no change. S7 still needs its own implementation
  authorization.

**Is a new model-calling entry point unavoidable?** No. One would only become
necessary if a reviewer later required the review *verdict* to be
authority-plane evidence rather than an execution claim. Under frozen 5F2E that
is impossible from any entry point, because the reviewer runs in the same
process as repository code (C-11). Making it possible would need a change to
5F2E's execution semantics, not a new command, and needs explicit human
authorization.

### 5.7 Credentials and process state

**(AMEND1)** Credential placement now follows identities:

| Identity | Credentials it may hold | Reachable by T3? |
|---|---|---|
| A | **None.** FD-16 refuses to open a session if any `AIDO_LITELLM_*`, `AIDO_VLLM_*` or `GITHUB_TOKEN` name is present in A's environment block | No |
| O | None for the Alpha. Signing uses the hardware authenticator, whose key is not on the host | No |
| X, P1B console | `AIDO_LITELLM_*`, set only in that console's environment, for the P1B run, before any repository code has run in X. The console is closed afterwards | Only if T3 already exists in X, which E-11 rules out |
| X, review console | The configured reviewer provider's names, set only in that console's environment | **Yes**: by the 5F2D run inside that same command, and by any surviving X process. This is 5F2E's inherited residual (D-4), now **confined to X** |

- No provider value may be persistent in X's or A's user environment (E-11).
  A persistent value in X's profile would be readable from X's registry hive by
  every repository process ever run as X.
- **Recommended:** a reviewer endpoint that needs no secret (vLLM's
  non-secret `no_api_key` placeholder), or a dedicated, revocable reviewer key
  that is rotated after the Alpha. AUTH-PILOT names which (E-4).
- P1B and a LiteLLM reviewer read the same `AIDO_LITELLM_*` names. They now
  run in separate X consoles at different times, and only the reviewer's
  console coexists with repository code.
- The approver verifier reads no environment variable. The registry path is a
  constant.

### 5.8 Execution-identity isolation (AMEND1)

#### 5.8.1 Invariant

> Repository-controlled code must not be able to create, rewrite, delete or
> consistently forge the authoritative state and evidence on which AIDO relies.

"Authoritative" is defined, not assumed (FD-15). It means the store.v4 rows and
blobs, the approver registry, the identity boundary, the AIDO code A executes,
A's process and token, and A's own observations M0/M1/M2. Execution claims are
explicitly **not** authoritative, so the invariant does not depend on them.
That classification is enforced in code: no transition to a more-trusted state
is justified by a claim alone (§5.8.4).

The invariant is held by **access control between Windows accounts**. It is not
held by recorders, digests or conventions inside one account; those remain,
but only as defense against T1 and T4.

#### 5.8.2 FD-13 Identities and how they are launched

| Identity | Kind | Runs | Never |
|---|---|---|---|
| **A** authority | Dedicated local standard account; not in Administrators, Backup Operators or any group that X or O is in | The integration session: store.v4, DL-3/DL-2, the attestation verifier, adapters, recorders, the planner rule, and boundary proof | Repository code, any harness, Git, a subprocess, a network connection, a model call, a credential; an interactive login used for anything else |
| **X** execution | Dedicated local standard account, **fresh (new SID) for each Alpha** (E-11) | The human-run existing commands: P1B, `l2-apply-approved-file-edit`, `l2-review-approved-file-edit`. It owns the clone. T3 lives here | Anything on the authority plane; any session but its own |
| **O** operator | The human's own interactive account | Reading published bundles; preparing statements; placing signatures and the approved artifact in A's inbox | Repository code (runbook; residual D-16); A's or X's work |

**Launch rules.** A's invocations run either as admin-provisioned Task
Scheduler tasks (S4U principal A, "run whether logged on or not", no stored
password, fixed action, O granted run permission only), or in A's own
interactive session reached through the secure logon UI. X's commands run only
in X's own interactive session, reached the same way (fast user switching or a
sequential sign-in). Each identity therefore has its own logon session and its
own window station and desktop. `runas`, `Start-Process -Credential` and any
other start of one identity's process on another identity's desktop are
**forbidden**. A shared desktop lets processes of different accounts at the
same integrity level inject input, install low-level hooks and send window
messages to each other. A password typed there could be captured by a T3
process sharing that desktop.

The account names and SIDs, and the launch mechanism chosen, are recorded in
`identity-boundary.v1` and named in AUTH-PILOT. If the host's policy forbids
creating local accounts, granting "log on as a batch job", or switching users,
the DL Alpha is **blocked**. There is no same-account fallback (D-17).

#### 5.8.3 FD-14 Access rights

Rights are stated as what the OS grants. "None" means no allow ACE applies to
that SID, directly or through any group it is in. Every authority-plane object
has a **protected** DACL (inheritance from its parent disabled), so no inherited
`Users`, `Authenticated Users`, `Everyone` or `INTERACTIVE` ACE can apply.

| Object | A | X | O |
|---|---|---|---|
| State root (store.v4, `evidence/`, staging) | owner, full | **none** | none |
| `published/` (bundles for the human) | owner, full | **none** | read |
| `inbox/` (signatures, approved artifact) | read | **none** | add-file, write own files |
| `exchange/handoff/<ticket>/` | owner; writes once at creation | read only | none |
| `exchange/outbox/<ticket>/` | owner, but an `OWNER RIGHTS` ACE limits A to list, read and `READ_CONTROL` (A cannot add, alter or re-permission) | add-file, write and delete own files | read |
| `%ProgramData%\AIDO\` (registry, identity boundary) | read | read | read |
| AIDO install, venv, interpreter, every `sys.path` entry and every `PATH` directory of A | read and execute | read and execute only: no write, append, delete, `WRITE_DAC` or `WRITE_OWNER` | read and execute |
| A's profile (`HOME`, `TEMP`, user site, gitconfig) | full | none | none |
| A's processes, threads and primary token | default DACL: A, SYSTEM, A's logon SID | **none** | none |
| Clone root directory object | read | contents: modify; the root object itself: no DELETE, `WRITE_DAC` or `WRITE_OWNER`. On the root's parent: traverse only | read |
| Clone working tree (excluding `.git`) | read | owner; modify. An inheritable `OWNER RIGHTS` ACE removes the owner's implicit `WRITE_DAC`, so files X creates cannot be re-permissioned against A's read either | read |
| Clone `.git` subtree | read | owner (Git's ownership check, C-10), but **read and execute only**: an `OWNER RIGHTS` ACE limits X to `READ_CONTROL`, so X can neither write `HEAD`, refs, index, config, hooks or objects, nor re-permission them | read |

The clone is created by X with `git clone`. That runs no repository code; no
hooks are cloned. It is checked out detached at `base_head_oid`. An
administrator then applies the `.git` and root ACLs above **before** P1B runs,
because P1B also binds the clean HEAD. A records the resulting `.git` control
digest when the plan activation is consumed. A file X *creates* can carry any
DACL X specifies at creation. One that denies A read makes the next manifest
fail closed; it can never reach the authority plane.

**Why this suffices without a sandbox.** Every right T3 would need to reach
the authority plane (write or delete an authority object, change its DACL or
owner, open A's process or token, plant code on A's load path, change the
clone's committed state) is absent from X's access. The kernel enforces that
regardless of what X runs, how many descendants it has, or how long they live.
Nothing about X's own behavior needs to be confined.

#### 5.8.4 FD-15 Evidence classes, and FD-17 the claim protocol

| Class | Examples | May do | May never do |
|---|---|---|---|
| **Authority-plane** | Approvals and their consumption; activation, scope, intent and handoff rows; observations M0/M1/M2; receipts of claims (that bytes arrived, when, for which ticket) | Prove; refuse | — |
| **Execution claim** | stdout of the three human-run commands, including verification outcome and output, the review packet and verdict, and the 5F2C report | Refuse a step (any disagreement with scope, H6 or an observation); inform the human; select between DL-1's existing branches toward a human | Prove a write, an observation, an approval or COMPLETE. Be relabeled as authority-plane evidence. Be retried, repaired or merged |

**FD-17 Claim protocol.**

1. A creates the per-ticket handoff and outbox directories only after the
   ticket is issued and the handoff row is committed. A pre-existing directory
   for that ticket is refused.
2. The human runs the existing command as X, with the handoff paths. In X's own
   shell, the human redirects its stdout to `outbox\<ticket>\stdout.json`. Only
   after the command exits does the human create an empty
   `outbox\<ticket>\complete`. The redirection is the human's shell in X's
   session, like the human's `ssh-keygen -Y sign`. AIDO contains no shell and
   launches nothing.
3. A waits for `complete` to a **fixed code-constant bound**. The bound is not
   config and not a CLI option. AUTH-PILOT records its value. Expiry →
   RECOVERY_REQUIRED.
4. A then requires the outbox to hold **exactly** `stdout.json` and `complete`.
   Each must be a regular file, not a reparse point, with link count 1, owned by
   X's SID. `stdout.json` must be within a fixed size cap. A opens it once,
   denying write sharing, and hashes and strictly parses it from that same
   handle. Any deviation, including a sharing violation, refuses.
5. Exactly one claim is recorded per ticket. Nothing else in that outbox is
   ever read again. A claim arriving after the step left the in-flight state is
   never read.

T3 can always write a wrong, stale or replayed claim into the current outbox.
FD-17 does not try to prevent that, and cannot. It guarantees only that what A
records is exactly what it read, read once, for the right ticket. A wrong claim
either disagrees with an observation and refuses, or reaches a human labeled as
a claim.

#### 5.8.5 FD-18 Authority observation without Git

A runs no Git (C-10), so it observes with plain, reparse-refusing file reads:

- **Target**: SHA-256 of the target's bytes.
- **HEAD**: `.git/HEAD` must be exactly `base_head_oid` followed by a line feed
  (detached). A symbolic ref, a different oid, or any other content refuses.
  A does not resolve refs.
- **`.git` control digest**: SHA-256 over a canonical list of (relative path,
  size, SHA-256) for `HEAD`, `config`, `index`, `packed-refs`, every file under
  `refs/`, `hooks/` and `info/`, and the presence or absence of `modules/`.
  A `modules/` directory, or a `.gitmodules` file in the tree at M0, refuses
  (no submodules in the Alpha).
- **Working-tree manifest**: (relative path, size, SHA-256) of every regular
  file outside `.git`, bounded by a fixed entry and byte cap. A reparse point,
  a multiply-linked file or an over-cap tree refuses.

| Observation | Taken | Must hold |
|---|---|---|
| M0 | Before the write intent | Target = pre-image; HEAD = `base_head_oid`; `.git` digest = the activation-time digest |
| M1 | After the write claim | M1 − M0 = exactly the target, now the post-image; `.git` unchanged |
| M2 | After the review claim | Target = post-image; every M1 path present and unchanged; `.git` unchanged. Additions are listed, not refused |

Because `.git` is read-only to X (FD-14), the `.git` and HEAD checks confirm a
fact the OS already enforces. They do not merely detect a change. Each manifest
is stored as a write-once blob and re-derived on every proof.

#### 5.8.6 FD-16 Mechanical re-proof, and what fails closed

`open_integration_session` runs this proof, and every dispatch, claim read and
authoritative proof re-runs it. Any failure refuses with
`isolation_unproven:<category>`:

1. `identity-boundary.v1` is read from its code-constant path with the
   registry's anchor checks (§5.1 FD-2 (a)–(e)). Once a plan activation exists,
   its digest must equal the one bound in that activation.
2. The process token's user SID is `authority_sid`. The token is not elevated
   and holds no `SeDebug`, `SeBackup`, `SeRestore`, `SeTakeOwnership` or
   `SeImpersonate` privilege. The three SIDs are distinct. Neither A nor X is in
   `Administrators` or `Backup Operators`, as far as a standard user can check
   (local group enumeration); the remainder is attested in AUTH-PILOT.
3. The process is not on another identity's desktop. Its session belongs to A,
   or it runs in a non-interactive window station.
4. A's process and primary-token DACLs grant nothing to X's SID, `Everyone`,
   `Users`, `Authenticated Users` or `INTERACTIVE`.
5. For every object in the FD-14 table, the owner is as stated, the DACL is
   protected where required, and the rights an AuthZ client context built for
   X's SID (with X's real groups) would receive are within the table. This
   includes every `sys.path` entry and every `PATH` directory A loads from.
6. A's environment block contains no `AIDO_LITELLM_*`, `AIDO_VLLM_*` or
   `GITHUB_TOKEN` name, and no `PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP` or
   `PYTHONUSERBASE`.

Effective-rights checks are evaluated for X, not just for A's own token,
because the question is what X can do. T3 cannot invalidate a proof after it
passes: no object is X-writable and none is X-re-permissionable, so only A,
an administrator or SYSTEM could change it.

**Fail closed.** No integration session opens and no dispatch proceeds without
the proof. A failure before the attempt is a refusal with nothing consumed. A
failure inside an in-flight state raises, and DL-2 reduces the step to
RECOVERY_REQUIRED. There is **no** same-account mode, no flag, no config key
and no environment variable that skips the proof. The production composition
root has no injection point for a different boundary (static test). Offline
tests build the library-level session with a synthetic boundary over `tmp_path`
objects, the same pattern as the registry in S1. If accounts cannot be
provisioned on the host, the DL Alpha does not run.

#### 5.8.7 Descendants that survive verification

They are never claimed stopped, and nothing here depends on their stopping.
They hold exactly X's rights, for as long as they live:

- **They can:** write the working tree, write X's profile (including autostart
  entries), reach the network, read the current handoff, write the current
  outbox, read the reviewer credential of a review console they coexist with,
  and tamper with any later X process.
- **They cannot:** do anything FD-14 denies X, at any time, from any
  descendant.

Consequences, made explicit:

- **X is compromised after its first review run.** It is fresh for each Alpha
  (new SID), it is never reused for another repository, and after the Alpha the
  human disables it (an administrator action, not AIDO) (D-14).
- **The working tree can change after M2** (D-13). A records M2's time. The
  human's inspection may show later changes, which themselves indicate T3
  activity.
- **No process enumeration, job object, `taskkill` or process-group mechanism
  is added.** The boundary is access control, so descendant lifetime is
  irrelevant to it.

#### 5.8.8 Using the frozen harnesses without changing them

- 5F2D and 5F2E are used only through `l2-review-approved-file-edit`, and 5F2C
  only through `l2-apply-approved-file-edit`. They are run by the human, as X,
  with unchanged arguments, flags, config gates, environment policy, timeouts,
  exit codes and stdout. Their child processes get X's token because the
  calling process is X's; that is their current behavior, not a new one.
- **C-10, Git ownership.** The frozen Git adapter forwards neither `HOME` nor
  `USERPROFILE` and sets `GIT_CONFIG_NOSYSTEM=1`, so no `safe.directory` can
  apply. Each Git-using harness must therefore run as the clone's owner, X. A
  runs no Git, and observes as in FD-18.
- **Detached HEAD.** No frozen harness inspects the branch: there is no
  `symbolic-ref` and no `--abbrev-ref` in the fixed Git set. A detached checkout
  is therefore expected to be accepted unchanged. E-12 confirms it. If any
  harness refuses it, the Alpha is blocked; no harness change is implied.
- **Read-only `.git` for X.** The fixed Git set is read-only and uses
  `--no-optional-locks`, so it should run against a `.git` that X cannot write.
  E-12 confirms that too. If it does not, the Alpha is blocked.

#### 5.8.9 Adversarial review of the boundary

| Attack | Path | Result under AMEND1 |
|---|---|---|
| **Supported-caller bypass** (T1/T4 in A) | Call a recorder; pass claim bytes or an observation to a store API; write a forged claim into the outbox | No API accepts claim or observation bytes. A cannot write the outbox (`OWNER RIGHTS`). A forged claim would still be only a claim |
| **Cross-process trust** | A trusting X's process, exit code or report | A never opens, launches or signals an X process. It trusts no exit code, and treats claims as claims. X trusts only the handoff, which it cannot write |
| **Child-process survival** | A descendant keeps running after the review command returns | It is bounded by X's rights (§5.8.7). It can corrupt later claims and the working tree, never the authority plane |
| **Process injection** | `OpenProcess` / `CreateRemoteThread` / `WriteProcessMemory` on A; DLL planting on A's load path; input injection or hooks into A's desktop | A's process DACL grants X nothing. A's load path is X-unwritable (FD-16 step 5). A and X share no desktop (FD-13) |
| **TOCTOU on the boundary** | Change an ACL or owner between proof and use | X has no `WRITE_DAC` or `WRITE_OWNER` on any checked object, so the proof cannot be invalidated by T3 |
| **TOCTOU on observations** | Change the tree during or after M2 | During: A opens each file once and hashes from that handle, so a change shows as a mismatch or a sharing refusal. After: D-13 |
| **TOCTOU on claims** | Swap `stdout.json` while A reads it | A opens once, denying write sharing; a sharing violation refuses |
| **Link and reparse tricks** | Junction or hard link in the outbox or tree pointing at A's files | Refused: reparse points and link count above 1 |
| **Committed-state forgery** | Commit, move HEAD, rewrite refs or index, plant `core.fsmonitor`/hooks | OS-denied (`.git` is read-only to X). A runs no Git, so even a planted config could not execute in A |
| **Credential disclosure** | Read A's or O's credentials; read reviewer credentials | A and O hold none (FD-16 step 6; §5.7). The reviewer credential in X's review console is reachable: inherited, confined (D-4) |
| **Forged evidence** | Fabricate a `verified` report or an `approve` packet | Possible, as a claim. It cannot pass a failing M1/M2, cannot write, approve or complete, and is labeled to the human (D-2′) |
| **Forged authority** | Write store rows, blobs, registry, boundary file, published bundle | OS-denied (FD-14) |
| **Crash recovery** | Kill A while it waits for a claim; kill X mid-command | A: `recover()` reduces EXECUTING or VERIFYING to RECOVERY_REQUIRED, and a late claim is never read. X: no `complete` → deadline → RECOVERY_REQUIRED |
| **Restoration of stale state** | Replay an old claim; restore an old state root; reuse an old handoff | Old claims are claims, and M0/M1/M2 are fresh. X cannot write the state root; a restore by A's holder is D-7. Handoff and outbox directories are per-ticket and refused if they pre-exist |
| **Denial of service** | Fill the disk, flood the outbox, hold a file open, delete X's own files | Fails closed; availability is out of scope |

#### 5.8.10 Testing the claim under adversarial conditions

1. **Offline, in the suite (S0, S3, S4).** Tests build security descriptors on
   `tmp_path` objects, granting or denying synthetic SIDs. They evaluate them
   through AuthZ contexts built for those SIDs with
   `AUTHZ_SKIP_TOKEN_GROUPS`, and assert every `isolation_unproven` category.
   They cover every FD-17 deviation (missing marker, extra entry, reparse
   point, hard link, oversize, wrong owner, sharing violation, pre-existing
   directory, second claim, late claim) and every FD-18 mismatch. Claims are
   produced by calling the frozen library functions under the test's own
   account, against a synthetic repository and a synthetic verification
   script, with `httpx.MockTransport` for the reviewer. That is legitimate
   because a claim's origin is never trusted anyway. No test creates an
   account, needs elevation, or opens a socket.
2. **Live isolation rehearsal (E-12, separately authorized, no model, no real
   target).** On the provisioned host, with real A, X and O accounts, a
   throwaway synthetic repository cloned by X, and the existing
   `l2-verify-approved-file-edit` as X. Its configured executable is a
   synthetic **hostile verification program**, written outside the clone. That
   program spawns a detached descendant that repeats every attempt below for
   the rest of the rehearsal. It attempts to:
   - write, delete, rename, take ownership of or re-permission every FD-14
     object;
   - write `.git/HEAD`, `config`, `index`, a ref and a hook;
   - open A's process and token for VM read and write, thread creation and
     handle duplication;
   - write into A's install, `sys.path` and `PATH` directories;
   - add files to `inbox/`, `handoff/` and `published/`;
   - plant a junction and a hard link in the outbox;
   - send input or hooks to A's desktop;
   - read A's and O's environments and profiles.

   **Pass** means A's FD-16 proof passes after the rehearsal, and every
   store.v4 row, blob and published bundle byte is unchanged against a
   pre-rehearsal digest taken by A. The `.git` control digest must also be
   unchanged. The hostile program's own log is an X claim, kept for diagnosis
   only. **Fail** blocks the Alpha.

---

## 6. End-to-end authority and evidence flow

**(AMEND1)** The identity column is new. Every step not marked **X** runs as A
or O, and none of those executes or touches repository content.

```text
 #   Invocation         Identity  Actor / action                              Authority consumed / evidence produced
 0   provisioning       admin     accounts A, X (fresh), O; identity-boundary  boundary digest (named in AUTH-PILOT)
                                  .v1; registry; FD-14 ACLs; A's tasks
     clone              X, admin  X: git clone, detached at base HEAD;        —
                                  admin: apply .git / root ACLs
 1   setup              A         AidoStateRoot.create; FD-16 proof            state-root id
 2   approve-contract   O → A     signed project contract                      challenge(project_contract)
 3   approve-activation O → A     plan + Alpha policy + workspace + scope +     challenge(plan_activation v2);
                                  config digest + boundary digest               activation-time .git digest
 4   proposal           X         l2-supervised-implementer-prepare / -run      P1B ledger (outside control plane)
                                  (no repository code has run in X yet)
 5   approve-diff       O → A     frozen DiffEditApproval; signed               challenge(exact_diff_approval);
                                                                                artifact bytes write-once
 6   attempt            A         contract, run, step; MARK_READY, BEGIN        ticket(implementer)
                        A         M0; claim intent; publish write handoff       H6 consumed; intent pending
 6a  write              X         l2-apply-approved-file-edit → outbox          write claim
                        A         M1; bind; IMPLEMENTATION_RETURNED             M1; intent completed; ticket consumed
                        A         publish review handoff                        ticket(verifier)
 6b  verify + review    X         l2-review-approved-file-edit → outbox         execution claim (one 5F2D run,
                                  (T3 exists from here on)                      ≤ 2 model requests)
                        A         M2; bind; VERIFICATION_OBSERVED               M2; ticket consumed
                        A         REVIEW_OBSERVED from the same claim           ticket consumed
                        A         planner rule → RECOMMEND_STEP_ACCEPT          ticket HELD
                        A         AWAITING_HUMAN_ACCEPTANCE stop; publish       bundle in published/
 7   accept             O → A     reviews bundle; signs subject v2              challenge(step_acceptance v2);
                        A         DECIDE_ACCEPTANCE                             held ticket consumed → COMPLETE
 8   close-out          A         fresh session: recover(); archive             project ACTIVE, PLAN_WORK_COMPLETE
                        admin     disable X                                     —
```

---

## 7. Lifecycle and failure-state model

| Phase / state | Failure or crash | Resulting state | Retry? | Human action |
|---|---|---|---|---|
| Approvals (2, 3, 5) | Any refusal; crash mid-transaction | Nothing recorded | Re-request a new challenge | Re-sign |
| Any, before the attempt **(AMEND1)** | FD-16 boundary proof fails | No session opens; nothing consumed | Only after the boundary is fixed by an administrator, and re-proven | Fix provisioning |
| Proposal (4) | P1B refusal, stall or rejection | No artifact; control plane untouched | Per P1B: a new authorization | Decide whether to re-run P1B |
| READY | `BEGIN_ATTEMPT` refused | Step stays READY; DL-2 stops `TRANSITION_REFUSED` | No | Inspect |
| EXECUTING before intent | Implementer ticket refused; boundary, workspace, config or M0 check fails | RECOVERY_REQUIRED (DL-4A / DL-2 rule); approval unspent but the attempt budget is spent | No (`max_attempts` 1) | Inspect; a new plan activation is needed for a new attempt |
| EXECUTING after intent **(AMEND1)** | Claim deadline; FD-17 violation; M1 shows no effect or an indeterminate effect; claim contradicts M1; boundary fails; A crash | RECOVERY_REQUIRED; approval spent | No | Inspect the clone; never `git restore` by AIDO |
| VERIFYING **(AMEND1)** | Claim deadline; FD-17 violation; no usable stdout (exit 1 or 4); binding failure; M2 fails; boundary fails; A crash | RECOVERY_REQUIRED | No | Inspect |
| VERIFYING | Claimed `verification-failed` (exit-2 shape) with M2 holding | ACCEPTANCE (DL-1) → planner `HUMAN_REQUIRED` → HUMAN_REQUIRED | No | Inspect |
| VERIFYING | Claimed `workspace-state-untrusted` (exit-3 shape) | RECOVERY_REQUIRED (DL-1) | No | Inspect |
| REVIEWING **(AMEND1)** | The recorded claim is not an exit-0 shape of this attempt; verdict re-derivation mismatch; A crash | RECOVERY_REQUIRED | No (RS1's retry is internal to 5F2E, unchanged; there is no second execution) | Inspect |
| REVIEWING | Claimed verdict `changes_requested` / `needs_human_review` | ACCEPTANCE → planner `HUMAN_REQUIRED` → HUMAN_REQUIRED | No | Read the packet |
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
| `aido-control-plane-store.v4` | store schema | v3 tables plus: `write_scopes`, `exact_diff_approvals`, `write_intents`, `write_evidence`, `review_evidence`, held-ticket columns, verification-evidence v2 columns, approver-key audit (fingerprint, counter). **(AMEND1)** Plus `execution_handoffs`, `execution_claims`, `authority_observations`, and the activation-time `.git` control digest. A v4 "evidence" row means *claim + authority observation*, not "a recorder called the shipped harness". That is a deliberate semantic difference from v3, scoped to v4 | Coexists. v2 and v3 unchanged; none opens another's file |
| `open_integration_session` | API | Opens store.v4 only, **(AMEND1)** after the FD-16 proof; builds verifier and adapters; exposes store + bound ports; no recorder | Coexists with `open_authority_session` |
| `identity-boundary.v1` **(AMEND1)** | file | `schema_version`, `authority_sid`, `execution_sid`, `operator_sid`, account names, launch mechanism, and the canonical paths of the state root, `published/`, `inbox/`, the exchange root, the clone, and the install roots. Admin-owned at `%ProgramData%\AIDO\identity-boundary.v1.json` | new |
| `execution-handoff.v1` **(AMEND1)** | record | ticket, artifact digest, config digest, handoff and outbox directory identities, `created_at` | new |
| `execution-claim.v1` **(AMEND1)** | record + write-once blob | ticket, exact stdout bytes and digest, classified shape (`write-result`, `review-packet`, `verification-failed`, `workspace-untrusted`), `received_at`, fixed label `execution_claim` | new |
| `authority-observation.v1` **(AMEND1)** | record + write-once manifest blob | kind (M0, M1 or M2), target digest, detached HEAD oid, `.git` control digest, manifest digest, entry count, `observed_at` | new |
| `approval-challenge.v2` / `human-attestation.v2` | models | v1 fields; subject kinds + `exact_diff_approval`; `proof` = armored SSHSIG | store.v4 only; v1 unchanged |
| `attestation-statement.v1` | signed bytes | Canonical JSON: `schema_version`, `namespace`, `state_root_id`, `challenge_id`, `subject_kind`, `subject_sha256`, `approver_id`, `key_fingerprint_sha256`, `attested_at`, `expires_at`, `approval_text` | new |
| `approver-registry.v1` | file | §5.1 FD-2 | new |
| `write-scope.v1` | model | §5.5 FD-10 | new |
| `plan-activation-subject.v2` | digest | v1 fields + `write_scopes_sha256` + `project_config_sha256` + **(AMEND1)** `identity_boundary_sha256` | store.v4 only |
| `exact-diff-approval-subject.v1` | digest | plan-issuance digest, `step_id`, `write_scope_sha256`, `approved_diff_artifact_sha256` | new |
| `write-intent.v1` | record | ticket, approval, scope, artifact digest, workspace identity digest, **(AMEND1)** M0 digest (in place of a Git-observed HEAD), state ∈ {pending, completed, refused, indeterminate} | new |
| `step-acceptance-subject.v2` | digest | v1 fields + `write_scope_sha256`, `write_evidence_sha256`, `review_evidence_sha256`, `planner_envelope_sha256` + **(AMEND1)** `identity_boundary_sha256`, M0/M1/M2 digests, `claim_provenance` | store.v4 only |
| Mirror readers | code | `workspace-write-result.v1` binding reader; `verification-result.v1` binding reader (extends DL-4A's); `review-packet.v5` binding reader. Each pinned by test to the shipped model. **(AMEND1)** They parse claims; they import only the frozen *models*, never an executing function | additive |
| `InnerLoopStop.AWAITING_HUMAN_ACCEPTANCE` | enum value | §5.3 | additive; never produced for v2/v3 stores |
| `hold_acceptance_decision`, `held_acceptance_bundle`, `request_exact_diff_approval`, `record_exact_diff_approval`, `claim_write_intent` | store APIs | store.v4 only; refused in v3 / v2. **(AMEND1)** None of them accepts claim or observation bytes from a caller | additive |
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
| C-1 **(AMEND1: resolved)** | `CLAUDE.md`: real model calls exist only behind four gated commands | The first proposal's attempt invocation called 5F2E in-process: a fifth model-calling surface | **Withdrawn.** A calls no model. The human runs the existing `l2-review-approved-file-edit` as X (§5.6). The A-side driver is a non-model entry point | No `CLAUDE.md` change. S7's own authorization |
| C-2 **(AMEND1: resolved)** | 5F2E: verify first, no `--verification-result` | The first proposal executed repository code twice per attempt | One execution: the review command's own 5F2D run answers VERIFYING, and its packet answers REVIEWING (§5.6) | — |
| C-3 | DL-2 R-9 (escalate at ACCEPTANCE when human acceptance is missing) | DL-4B requires hold-and-stop | Versioned by store: store.v4 holds; v2 and v3 unchanged | FD-7 |
| C-4 **(AMEND1)** | DL-1 §12.4 intent-before-effect for the "worker request"; DL-4A §12 sketch (H6 + write outside the control plane) | The model request precedes EXECUTING. The write happens **inside** EXECUTING, performed by the human as X after A's intent and handoff | The workspace effect is the one the control plane must record before acting, and A's M0/M1 decide what it was. P1B's model request has its own durable ledger intent. DL-4A §12 was a non-frozen sketch whose "write outside the control plane" would let verification check a write the control plane never authorized | FD-9 |
| C-5 | DL-4A §11.3 (Step Contract version with write scope; roadmap §14.1) | DL-4B binds write scope in plan activation v2 instead | Deviation from a recommendation, not a frozen contract; step-contract.v2 is deferred until multi-step | FD-10 |
| C-6 **(AMEND1)** | DL-4A §2 trust root ("operator account") and R-4 | Repository code would run as that account | The trust root becomes the **authority identity**, and repository code runs only as X, which the OS denies every authority-plane right (FD-13, FD-14, FD-16). Remaining surface: D-2′ (claims) | Reviewer acknowledgement |
| C-7 | `ApprovalSubjectKind` closed in `*.v1` | A fourth kind is needed | `*.v2` models, store.v4 only | — |
| C-8 **(decided)** | DL-1 §7: ALPHA-1B's S0 preflight STOPs while DL files are in `src/` | The DL Alpha and ALPHA-1B cannot share one checkout pin | **Decided:** the DL Alpha uses a separate checkout and runbook; ALPHA-1B S0 is preserved unchanged | E-13 |
| C-9 **(procedure decided; gate pending)** | `CLAUDE.md`: ALPHA-P1B listed as "IMPLEMENTED (awaiting review)" | The Alpha depends on P1B's live path | **Decided:** verify P1B acceptance from authoritative historical evidence; until proven, the gate stays pending | E-1 |
| C-10 **(AMEND1, new)** | Frozen Git adapter: `HOME`/`USERPROFILE` not forwarded, `GIT_CONFIG_NOSYSTEM=1`, fixed `-c` set without `safe.directory` | Git refuses a repository the invoking account does not own, so one clone cannot serve Git-using harnesses in two accounts | X owns the clone. P1B, 5F2C and 5F2D all run as X through their existing commands. A runs no Git and observes without it (FD-18). `.git` is read-only to X through `OWNER RIGHTS` | Reviewer acknowledgement. The alternative, an exact-path `-c safe.directory=` in the frozen adapter so that A could run 5F2C, is a frozen change and is **not** proposed |
| C-11 **(AMEND1, new)** | Frozen 5F2D/5F2E launch semantics: the child runs as the calling account, and 5F2E calls the reviewer in that same process after verification | No OS boundary can make the verification outcome or the review packet T3-proof without changing how they launch | They are classified as execution claims (FD-15): they can refuse but never prove, and they are labeled to the human. Making them authority-plane would require changing 5F2D's launch (a separate identity or a lower integrity level for the child) or 5F2E's process structure | **Requires explicit human authorization if wanted. Not proposed.** The Alpha proceeds on the claim classification only if the reviewer accepts it (E-2) |
| C-12 **(AMEND1, new)** | FD-12 "no new subprocess capability"; `CLAUDE.md` "no shell anywhere" | The human redirects stdout in X's own shell to deliver a claim | AIDO contains no shell and launches nothing. The redirection is a human action in X's session, like `ssh-keygen -Y sign` | Reviewer acknowledgement |
| C-13 **(AMEND1, new)** | DL-4B's "no elevated AIDO" rule | Provisioning needs an administrator: accounts, rights assignments, ACLs, `%ProgramData%\AIDO\`, Task Scheduler tasks, disabling X afterwards | Provisioning is a human prerequisite, outside AIDO. AIDO still refuses to run elevated. Host policy that forbids it blocks the Alpha (D-17) | User action; named in AUTH-PILOT |

No frozen contract is silently changed. **(AMEND1)** C-1 and C-2 are resolved, and
C-8 and C-9 are decided as recorded above. C-11 is the one remaining
frozen-contract contradiction that only a human can resolve. AMEND1 does not
resolve it; it routes around it by classification.

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
| FD-6 **(AMEND1)** | store.v4 + `open_integration_session` (after the FD-16 proof); claim and observation recorders minted only into adapters; no recorder on the session; no harness call in A |
| FD-7 | Hold-and-stop at ACCEPTANCE in store.v4; acceptance subject v2 (with AMEND1's boundary, observation and provenance fields); decline = `ESCALATE` |
| FD-8 **(AMEND1)** | Role-to-component mapping of §5.4. The implementer is answered by `WriteHandoffAdapter`; verifier and reviewer by `ExecutionClaimAdapter`, from **one** claim. The store requires claim **and** observation for each. Deterministic Alpha planner rule over observations and claims |
| FD-8a | The Alpha policy profile is enforced by the store (one step, one scope entry, review + human acceptance required, one attempt) |
| FD-9 **(AMEND1)** | Proposal (X) and exact-diff approval before the attempt. Durable write intent and handoff, then the human-run 5F2C write as X, inside EXECUTING. The process split of §4 (approvals, proposal, one long-lived attempt with two human-run X executions, acceptance) |
| FD-10 | `write-scope.v1` inside `plan-activation-subject.v2`; StepContract v1 unchanged |
| FD-11 | No cleanup, restore, retry, rollback or repair anywhere; every failure is terminal for the Alpha |
| FD-12 **(AMEND1)** | No new subprocess capability, no new Git operation, no model token cap, no sandbox claim, no CLI option that names a path, model, endpoint, key or timeout. Also: AIDO launches no process under any identity; no token, integrity-level, job-object, AppContainer or process-tree mechanism; A runs no harness, no Git, no network and no model |
| FD-13 **(AMEND1)** | Three distinct non-administrative accounts A, X (fresh per Alpha) and O, each in its own logon session and desktop, launched as §5.8.2 states; cross-desktop launches forbidden |
| FD-14 **(AMEND1)** | The access-rights table of §5.8.3, including X-owned clone with `.git` read-only to X through `OWNER RIGHTS`, and protected A-only DACLs on the authority plane |
| FD-15 **(AMEND1)** | Two evidence classes. Authority-plane evidence proves; execution claims can only refuse or inform. No transition to a more-trusted state rests on a claim alone; the acceptance subject labels claims |
| FD-16 **(AMEND1)** | Mechanical boundary re-proof (§5.8.6) on session open, every dispatch, every claim read and every proof; `isolation_unproven` refusal; no same-account mode or bypass |
| FD-17 **(AMEND1)** | Claim protocol (§5.8.4): per-ticket handoff and outbox created by A after the ticket; closed entry set with a completion marker; fixed code-constant wait bound and size cap; read once with write sharing denied; one claim per ticket |
| FD-18 **(AMEND1)** | Git-free authority observation (§5.8.5): target digest, detached HEAD, `.git` control digest, working-tree manifest; M0/M1/M2 rules; no submodules |

### 10.1 Implementation details Claude may choose

Module layout (adapters live **outside** `control_plane/`, which must stay free
of executing imports, for example `ai_dev_orchestrator/integration/`); SQL
table and column shapes; the Win32 access-check implementation (`AccessCheck`
or `GetEffectiveRightsFromAcl` via `ctypes`); the elevation check; the SSHSIG
parser structure; how the statement is presented to the human (file or
stdout); refusal message wording within the categories of §5.1; the
non-authoritative audit record of 5F2E's second verification; helper
conveniences that build requests (never checks); test fixture structure.
**(AMEND1)** Also: the AuthZ and `ctypes` structure of the boundary proof; the
exact `.git` control-file list beyond the FD-18 minimum; the manifest
encoding; the values of the FD-17 wait bound and size cap and the FD-18 manifest
caps (fixed constants, recorded in AUTH-PILOT); the exchange-root layout; the
runbook's wording of the human's X-session commands. The "audit record of 5F2E's
second verification" item no longer applies, because there is no second
verification.

---

## 11. Minimum implementation slices and acceptance gates

Each slice needs its own prompt and its own independent review. None runs
anything live.

| Slice | Content | Acceptance gate |
|---|---|---|
| **S0** Identity boundary **(AMEND1)** | `identity-boundary.v1` reader with anchor checks; AuthZ effective-rights evaluator for a named SID; token, privilege, session, process-DACL and environment checks; FD-16 composition with no bypass | Synthetic security descriptors on `tmp_path` with synthetic SIDs; every `isolation_unproven` category; production composition root has no injection point (static test); no subprocess, network or model surface (static test) |
| **S1** Attestation verifier | `RegistryHumanAttestationVerifier`, SSHSIG/sk parser, registry reader with anchor protection, elevation refusal, `attestation-statement.v1`, `*.v2` models | Known-answer vectors (test-only software Ed25519 key emulating the `sk` format); every refusal category; registry-writable refused; elevated refused; **(AMEND1)** registry writable by the synthetic X SID refused; no env, network or subprocess surface (static test) |
| **S2** Integration store | store.v4, `open_integration_session` (requires S0), Alpha policy profile, write scope, activation subject v2 with boundary digest, FD-4 re-verification in proofs, FD-5 ordering, **(AMEND1)** handoff, claim and observation tables | v2/v3 suites unchanged and green; v3↔v4 cross-open refused; no recorder reachable from the session; tamper matrix → untrusted; no API accepts claim or observation bytes |
| **S3** Exact diff + write handoff **(AMEND1)** | `request/record_exact_diff_approval`, `claim_write_intent`, FD-18 observer (M0/M1), FD-17 claim receiver, `WriteHandoffAdapter` | Synthetic Git repo under `tmp_path`; the human-run step is simulated in-test by calling the frozen library `apply_approved_file_edit` and writing its stdout bytes to the outbox; every FD-17 deviation; M1 effect classification (as approved / none / indeterminate); crash-at-every-point matrix; no second handoff; A-side module imports no executing harness function (static test) |
| **S4** Execution claim adapter, VERIFYING **(AMEND1)** | Review handoff, claim classification, M2, verification binding | Synthetic repo + synthetic verification script under `tmp_path`; claims produced by the frozen library `run_controlled_review` with `httpx.MockTransport` inside the test; every exit shape; caller-provided JSON or digest refused; binding and M2 mismatches refused; a `verified` claim with a failing M2 → RECOVERY_REQUIRED |
| **S5** Execution claim adapter, REVIEWING **(AMEND1)** | Review observation from the recorded claim; verdict re-derivation; same-claim rule | No network in A at all; the REVIEWING dispatch performs no execution; a claim of another attempt or a non-exit-0 shape refused |
| **S6** Acceptance lifecycle | DL-2 hold branch (store.v4 only), `hold_acceptance_decision`, `held_acceptance_bundle`, acceptance subject v2, `AlphaPlannerRule`, **(AMEND1)** bundle publication | Hold survives crash and restart; no second planner dispatch; DL-3 unchanged and does not escalate; decline path; v2/v3 R-9 behavior byte-identical; the subject binds the boundary, observation and provenance fields |
| **S7** Alpha driver **(AMEND1)** | A non-model A-side entry point that wires S0–S6 for the approval, attempt and acceptance invocations; an offline dry run end to end with the X steps simulated by library calls, mocks and a synthetic repo | Full chain COMPLETE offline; every abort rule; the driver imports no `llm` client, no harness executing function and no `subprocess` (static test) |

**Then, separately authorized:** the isolation rehearsal (E-12), AUTH-PILOT
(E-1…E-13), then one live Alpha.

S0 and S1 can proceed in parallel. S2 depends on S0. S3–S5 depend on S2. S6
depends on S2. S7 depends on all of them.

---

## 12. Adversarial test strategy

Every refusal test asserts an unchanged snapshot of all store tables **and**
the workspace bytes. **(AMEND1)** It also asserts that A published no further
handoff. Instead of spying on harness calls, a static test asserts that the
A-side package imports no harness executing function at all.

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
| Boundaries | Static tests: no subprocess, network or environment import in `control_plane/`; the only removal is DL-4A's; no `max_tokens` introduced; no CLI option naming path, model, endpoint, key or timeout. **(AMEND1)** The A-side integration package imports no `subprocess`, `socket`, `httpx`, `llm` client, Git adapter, or 5F2C/5F2D/5F2E/P1B executing function |
| Isolation **(AMEND1)** | Each FD-16 category on synthetic descriptors: state root, `.git`, install, `sys.path`, `PATH` or registry writable by the X SID; missing `OWNER RIGHTS` on `.git` or the outbox; unprotected DACL inheriting `Users`; process DACL granting `Everyone`; elevated or privileged token; a provider credential name in the environment; boundary digest ≠ activation |
| Claim protocol **(AMEND1)** | Missing marker; extra entry; reparse point; link count 2; oversize; wrong owner; sharing violation; pre-existing directory; second claim; claim after the step left the in-flight state; stale claim of another ticket placed in this outbox (bound and refused or labeled); deadline expiry |
| Observation **(AMEND1)** | M0 target ≠ pre-image; symbolic `HEAD`; `.git` digest drift; `modules/` or `.gitmodules` present; M1 with an extra changed path; M1 = M0 with a "success" claim; M2 with a modified or removed M1 path; manifest over its cap; a reparse point in the tree |
| Both paths | Every refusal reached through the direct store API **and** through DL-3 → DL-2 → adapters |

No test uses a real model, a socket, a real authenticator, a real target
project or a real verification executable. **(AMEND1)** No test creates a
Windows account or needs elevation. The cross-account behavior is proven only
by the separately authorized E-12 rehearsal (§5.8.10).

---

## 13. Explicit deferred risks

| Id | Risk | Alpha mitigation | Owner |
|---|---|---|---|
| D-1 | Planner output origin is unauthenticated (R-3) | Deterministic planner; the human signs the planner envelope digest; the Alpha profile forces human acceptance | Post-Alpha |
| ~~D-2~~ **(AMEND1: withdrawn)** | *First proposal:* T3 can rewrite evidence blobs and rows consistently before the human reviews them, mitigated by a "trusted target repository" | **Withdrawn.** T3 has no write, delete or re-permission right on any authority-plane object (FD-14), and A re-proves that (FD-16). The Alpha no longer relies on the repository being trusted for its authority plane | — |
| D-2′ **(AMEND1)** | Execution claims (both harness reports, the verification outcome and output, the review packet and verdict) are produced inside X. Repository code can forge them, consistently, at production time. A forged `verified` + `approve` can bring a step to a human-held ACCEPTANCE | Claims never prove (FD-15); M1/M2 refuse anything inconsistent with A's own observation; the acceptance subject and the bundle label every claim; the planner only recommends; COMPLETE needs a signature. Closing this needs C-11 | Accepted for the Alpha **only** with the reviewer's explicit acknowledgement (E-2) |
| D-3 | Path-based containment races (R-5) | 5F2C/5F2D detection; fail closed. **(AMEND1)** X cannot rename the clone root (FD-14) | Accepted residual |
| D-4 **(AMEND1)** | Reviewer credential values in the X review console's environment block are readable by the 5F2D run inside that command and by any surviving X process | Confined to X; nothing persistent in any profile (E-11); keyless endpoint or dedicated revocable key, rotated after the Alpha (E-4); A and O hold none | Inherited (5F2E), narrowed |
| D-5 **(AMEND1)** | Same-host signing lets T3 swap the statement before the touch | Separate signing device recommended (FD-2). On the host, signing happens in O's session, which X cannot reach while FD-13 holds | AUTH-PILOT |
| D-6 | Verification descendants and abandoned reviewer workers outlive the invocation | Documented 5F2D/RS1 limits; never claimed stopped. **(AMEND1)** Their reach is X's rights only (§5.8.7) | Inherited |
| D-7 | Restore of an older state root (R-4) | Archived evidence; re-proof checks signatures, not freshness | Accepted residual |
| D-8 | Host clock and challenge TTL (R-8) | Operator trust root | Accepted residual |
| ~~D-9~~ **(AMEND1: withdrawn)** | *First proposal:* two verification runs may disagree | There is one run per attempt (§5.6) | — |
| D-10 | P1B's live path requires LiteLLM; vLLM is refused there | Availability is an entry criterion (E-7) | Infrastructure |
| D-11 | Revocation is total and can retroactively untrust completed runs | Intended fail-closed behavior | Accepted |
| D-12 | Step-contract.v2 (write scope, baseline identity) deferred | One-step Alpha only (FD-8a) | Multi-step phase |
| D-13 **(AMEND1)** | Working-tree TOCTOU: a surviving X process can change the tree after M2, or while holding handles opened earlier | M2 is timestamped and bound into the acceptance subject; `.git` cannot change; a later difference is itself evidence of T3 | Accepted residual |
| D-14 **(AMEND1)** | X is persistently compromised after its first review run (autostart entries in its profile, surviving processes) | Fresh X (new SID) per Alpha; never reused for another repository; disabled by an administrator afterwards | Operator / AUTH-PILOT |
| D-15 **(AMEND1)** | P1B and the 5F2C write run as X (C-10). Their outputs are claims, and P1B's ledger and evidence are X-writable once T3 exists | Both run before any repository code (E-11); M0/M1 decide the write; the P1B proposal is never authority; LiteLLM values are not present in X after the P1B console closes | Accepted |
| D-16 **(AMEND1)** | The human's inspection of the clone could execute repository code as O (an IDE task, an extension, a script) | Runbook: inspect with non-executing viewers, or in X's session. O holds no credential and no authority, so the damage is confined to O's own files | Operator |
| D-17 **(AMEND1)** | Host policy may forbid local accounts, batch-logon rights or user switching | No fallback: the DL Alpha is blocked (FD-16) | Infrastructure |
| D-18 **(AMEND1)** | The human could run X's commands on O's desktop (for example through `runas`), exposing O's session to T3 | Forbidden by FD-13. A detects only A-side violations (FD-16 step 3). The damage is confined to O, never A | Operator |

---

## 14. One-step human-supervised Alpha entry criteria

All must hold, each evidenced, before a live Alpha is authorized:

- **E-1** DL-4A and FU1 independently accepted. ALPHA-P1B acceptance **proven
  from authoritative historical evidence**: the recorded independent-review
  acceptance identifying the accepted commit. Until that is shown, this gate
  stays pending (C-9).
- **E-2 (AMEND1)** This design and AMEND1 accepted, with FD-1…FD-18 frozen. C-10
  and C-12 acknowledged. The D-2′ claim classification explicitly accepted by
  the reviewer, or C-11 separately authorized and implemented. No `CLAUDE.md`
  change is required by this design.
- **E-3** Slices S0–S7 implemented, independently accepted, full suite green, offline dry run COMPLETE.
- **E-4 (AMEND1)** AUTH-PILOT signed by the human, naming: the repository (no
  longer "trusted for T3": it is an adversary throughout), the disposable clone
  path, the one file, the write scope (pre-image hash, base HEAD), the project
  config digest, the verification argv, the reviewer provider, endpoint and
  model and its credential arrangement (§5.7), P1B's model, the signing device,
  the A, X and O account names and SIDs, the launch mechanism, the
  `identity-boundary.v1` digest, and the FD-17/FD-18 constant values.
- **E-5 (AMEND1)** Approver registry and `identity-boundary.v1` provisioned with elevation; FD-14 ACLs applied; A's FD-16 proof passes; AIDO runs non-elevated.
- **E-6** Real-authenticator rehearsal: one throwaway challenge signed and verified in a throwaway state root.
- **E-7** LiteLLM reachable for P1B, and the reviewer endpoint matches `controlled_review.endpoint`.
- **E-8** Environment hygiene re-checked (no unexpected persistent credentials; the ALPHA-1B prep facts revisited).
- **E-9 (AMEND1)** The state root is an empty, non-Git directory owned by A with the FD-14 DACL, disjoint from the clone and the exchange root. The clone is created by X, owned by X, detached and clean at the scope's HEAD, with no submodules, and has its `.git` locked before P1B runs.
- **E-10** Abort rules acknowledged: any refusal, RECOVERY_REQUIRED, HUMAN_REQUIRED, containment or isolation error, or untrusted proof ends the Alpha, with no retry, repair or cleanup. No branch, commit, push or PR.
- **E-11 (AMEND1)** X is a fresh account (new SID) created for this Alpha, after the E-12 rehearsal. No repository code has run as X before step 6b. No provider value is persistent in A's or X's user environment.
- **E-12 (AMEND1)** Isolation rehearsal (§5.8.10) passed on the provisioned host, separately authorized, with no model and no real target. It uses its own throwaway execution account, never the Alpha's X. It also confirms that the frozen harnesses accept a detached HEAD and a `.git` that is read-only to X. Then `identity-boundary.v1` is re-provisioned with the Alpha's fresh X, before any approval binds its digest.
- **E-13 (AMEND1)** The DL Alpha runs from its own checkout and runbook. ALPHA-1B S0 is untouched (C-8).

---

## 15. Final report

1. **Recommended architecture (AMEND1).** An integration store (store.v4),
   owned and run by a dedicated **authority identity** that executes no
   repository code, no harness, no Git, no subprocess and no model. It has:
   hardware-signed human attestations verified against an AIDO-unwritable
   registry; a mechanically re-proven Windows identity boundary that denies the
   **execution identity** every write, delete, re-permission and process-access
   right over the authority plane; two adapters that hand store-derived inputs
   to the human-run existing commands and record what returns as execution
   claims; Git-free authority observations (M0/M1/M2) that alone establish
   workspace facts; a durable write intent before the single write; a
   persisted hold at ACCEPTANCE; and one repository execution per attempt,
   through the existing `l2-review-approved-file-edit`, so no fifth
   model-calling surface exists.
2. **Required trust sources and prerequisites.** A FIDO2 authenticator with
   user presence; one-time elevated provisioning of the registry, the identity
   boundary, three accounts and their ACLs; a non-elevated AIDO process; the
   `cryptography` dependency; the accepted harness code at a pinned commit;
   LiteLLM availability for P1B; a disposable clone owned by the execution
   identity. **(AMEND1)** The target repository is **not** trusted.
3. **Contradictions with frozen contracts.** None changed silently. Thirteen
   items are listed in §9. C-1 and C-2 are resolved by AMEND1 without a
   `CLAUDE.md` change. C-8 and C-9 are decided (separate checkout and runbook;
   P1B acceptance to be proven from historical evidence). C-3, C-4, C-5, C-6,
   C-7, C-10, C-12 and C-13 are resolved by versioning, placement or explicit
   acknowledgement. **C-11 remains:** the frozen 5F2D/5F2E launch semantics make
   the verification outcome and review verdict unprovable against T3. AMEND1
   classifies them as claims instead of changing those contracts, and any
   change there needs explicit human authorization.
4. **Proposed implementation phases.** S0 identity boundary ∥ S1 verifier →
   S2 integration store → S3 exact diff + write handoff, S4/S5 execution claim
   adapter, S6 acceptance lifecycle → S7 non-model Alpha driver and offline dry
   run → E-12 isolation rehearsal → AUTH-PILOT → live Alpha. Each step needs
   separate authorization.
5. **Remaining blockers to a real Alpha.** E-1…E-13. Specifically: DL-4A
   acceptance; P1B acceptance proven from historical evidence; this design's
   and AMEND1's acceptance, including the D-2′ acknowledgement; S0–S7; account
   provisioning permitted by host policy; the authenticator and registry; the
   isolation rehearsal; LiteLLM availability; and AUTH-PILOT.

**Final status: DESIGN AMENDED — PENDING INDEPENDENT REVIEW.**
