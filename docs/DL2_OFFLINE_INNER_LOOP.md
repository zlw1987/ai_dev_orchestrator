# DL-2 — Offline Single-Step Inner Loop

| Field | Value |
|---|---|
| Status | **IMPLEMENTED — PENDING INDEPENDENT REVIEW** (not accepted) |
| Date | 2026-10-22 |
| Base | `1a6dd24` (DL-1 + FU1, independently reviewed and accepted for offline use) |
| Roadmap mapping | M6 inner loop (`AIDO_RUNTIME_HARNESS_ROADMAP.md` §16), offline subset |
| Code | `src/ai_dev_orchestrator/control_plane/inner_loop.py` |
| Tests | `tests/test_control_plane_dl2.py` |
| Live execution | **None.** No model, endpoint, process, shell, socket, Git, Pi, Node, environment read, or target workspace |

## 1. What DL-2 is

DL-2 adds one controller, `StepInnerLoop`. It drives **one** recorded Step Run
through implementation, verification, review when the contract requires it,
and the Planner's decision. Every role is an injected port, and every state
change goes through DL-1.

It is a driver over DL-1 and nothing else. It adds no event, no rule, no
table, no state, and no store API. DL-1's validator, store, recovery gate,
cross-object proof and replay semantics are used unchanged.

It is **not** any of these:

- the outer project loop, step scheduling, re-planning, or project completion
  (DL-3);
- a real Pi, B300, Verifier or Reviewer adapter (DL-4);
- a human-approval capture or human-resolution path;
- a re-proof path out of RECOVERY_REQUIRED;
- a CLI command, a deployment, model qualification, or a token budget.

## 2. Public API

```python
from ai_dev_orchestrator.control_plane import (
    StepInnerLoop, InnerLoopOutcome, InnerLoopStop, InnerLoopInputError, RoleDispatch,
)

loop = StepInnerLoop(store, ports)          # ControlPlaneStore, RolePorts
outcome = loop.run(
    project_run=..., step_run=...,          # recorded runs (identity only)
    project_contract=..., execution_plan=..., step_contract=...,
)
```

`InnerLoopOutcome`:

| Field | Meaning |
|---|---|
| `stop` | Why the loop returned (`InnerLoopStop`, below) |
| `step_run`, `project_run` | The store's **authoritative** reads after the last transition. These are never a receipt and never a role's account |
| `cause`, `cause_role` | The first non-ordinary event, if any (closed vocabulary, below) |
| `refusal_code` | The last DL-1 `RefusalCode` the loop received, if any |
| `dispatches` | Every role call: role, attempt, the persisted `state_version` that authorized it, and `valid` / `raised` / `malformed` / `misbound` |

`InnerLoopStop`:

- **Terminal step states:** `step_complete`, `step_failed`,
  `step_human_required`, `step_recovery_required`. Each is derived from the
  final authoritative step state.
- **Non-terminal stops:**
  - `project_not_active`;
  - `step_not_ready` (PLANNED: scheduling is DL-3);
  - `transition_refused`;
  - `replayed_receipt`;
  - `iteration_bound_reached` (a backstop).

Causes:

- `role_raised`, `role_output_malformed`, `role_output_misbound`;
- `result_not_recorded`;
- `human_acceptance_unavailable`;
- `in_flight_not_dispatched_here`;
- `project_not_active`;
- `replayed_receipt`.

Errors raised before anything is consumed:

- `InnerLoopInputError`, when the caller's objects do not describe one
  recorded step;
- DL-1's own `RecoveryRequiredError` / `StateUntrustedError`, unchanged.

`step_request_id(step_run_id, expected_state_version, event)` is the
deterministic idempotency key the loop uses. It is exported from the module
for tests and audit.

## 3. Lifecycle

Each iteration first takes the authoritative step and project reads, then acts:

| Authoritative step state | Action |
|---|---|
| COMPLETE, FAILED, HUMAN_REQUIRED, RECOVERY_REQUIRED | Stop |
| EXECUTING / VERIFYING / REVIEWING, **owned** by this call, project ACTIVE | Spend the permission, then dispatch the Implementer / Verifier / Reviewer exactly once. A valid output is recorded with `implementation_returned` / `verification_observed` / `review_observed` |
| in flight, **not owned** (or project not ACTIVE) | `recover_interrupted`, which leads to RECOVERY_REQUIRED. Never resumed, never re-run |
| project not ACTIVE | Stop `project_not_active` |
| receipt already seen in this call | Stop `replayed_receipt` |
| PLANNED | Stop `step_not_ready` (no `mark_ready`; scheduling is DL-3) |
| READY | `begin_attempt` (the persisted intent). On a non-duplicate apply, this call owns the new EXECUTING version |
| ACCEPTANCE | Dispatch the Planner, then `decide_acceptance` with **no** human acceptance |

The validator chooses every target state:

- review is entered only for `verified` with `review_required`;
- `workspace-state-untrusted` leads to RECOVERY_REQUIRED, and the project
  becomes RECOVERY_REQUIRED too;
- RETRY at the budget leads to FAILED;
- ACCEPT without `verified`, or without `approve` when review is required,
  leads to HUMAN_REQUIRED;
- PROJECT_CONTRACT_CONFLICT makes both the step and the project
  HUMAN_REQUIRED;
- other recommendations lead to HUMAN_REQUIRED.

### 3.1 Dispatch ownership: at most one dispatch per persisted intent

A port is called only when **this `run()` call's own, non-duplicate**
transition produced the exact in-flight `(state, state_version)` that the
authoritative read now shows. That permission is cleared **before** the port is
called. Because `state_version` only ever increases, nothing can return a step
to an owned version.

Ownership is held in a per-call object. It is not kept on the controller
instance, so all of the following find the step in flight but not owned:

- a new controller instance;
- a second `run()` on the same instance;
- a re-entrant call from inside a port;
- a store reopen;
- a replayed receipt.

Each of these reduces the step to RECOVERY_REQUIRED.

### 3.2 Replay

Request ids are `sha256("dl2:{step_run_id}:{expected_state_version}:{event}")[:32]`,
so one logical request always has one id. Sending a recorded request again
returns DL-1's receipt (`duplicate=True`). Reusing the slot for different
content is refused as a duplicate conflict.

A receipt is never permission. On a receipt the loop clears ownership, sets
`receipt_seen`, and dispatches **no role again in this call**. An in-flight
step reached that way is reduced to RECOVERY_REQUIRED. A non-in-flight step
stops with `replayed_receipt`.

### 3.3 Failures

| Where | Failure | Result |
|---|---|---|
| EXECUTING / VERIFYING / REVIEWING | port raises `Exception`; output not exactly the expected model, not re-validating, or bound to another contract digest or attempt | `recover_interrupted` → RECOVERY_REQUIRED (the requested effect is unproven); project RECOVERY_REQUIRED unless already more severe |
| same | valid output, but recording it is refused (for example, the project left ACTIVE meanwhile) | role not called again; the next read finds an unowned in-flight step and reduces it |
| ACCEPTANCE | Planner raises or returns a malformed or mis-bound decision | `escalate` → HUMAN_REQUIRED; no decision recorded |
| ACCEPTANCE | facts support acceptance but the contract requires human acceptance | DL-1 refuses `human_acceptance_missing`; the loop never fabricates one and `escalate`s → HUMAN_REQUIRED (`human_acceptance_unavailable`) |
| any | port raises `BaseException` (a crash) | **not caught**; the persisted in-flight state stays, and `recover()` turns it into RECOVERY_REQUIRED on the next session |
| any | the store raises `StoreError` | propagates unchanged; nothing further is attempted |

No failure is retried. Every retry is a Planner `RECOMMEND_RETRY_IMPLEMENTATION`
that the validator authorizes within the contract's `max_attempts`.

## 4. Adversarial analysis (before coding)

| Question | Answer and enforcement point |
|---|---|
| Who creates the contracts and role results? | Contracts are recorded through DL-1 beforehand. DL-2 issues none and uses the **store's** copy, loaded by the step run's bound digest. Role results come only from the port call the loop itself made |
| Mismatched but individually valid objects? | `_bind` re-parses each object through its **exact** class (no subclasses, no `model_construct`). It re-proves both runs through the store's gated reads, then requires: the step to belong to the project run, every identity field to match the recorded run, and each contract digest to equal the run's bound digest. Any mismatch raises `InnerLoopInputError` before a write or a dispatch. A supplied run's *state* fields are never consulted |
| Malformed or stale port output? | `_role_output`: exact type, a JSON round trip through that class, then digest and attempt equal to the step's **current** binding. Otherwise a role failure. The validator re-checks the binding as a backstop |
| A port throws before or after producing a result? | `Exception`: no result is recorded, and the step is reduced (in flight) or escalated (ACCEPTANCE). `BaseException`: propagates, and the persisted intent is left for `recover()` |
| A retry after a partially recorded attempt? | There is no loop-level retry. A partial attempt is in flight and unowned, so it is reduced. Only a validator-authorized READY begins another attempt, and the attempt counter is persisted |
| Can a restart dispatch the same implementation twice? | No. Ownership never survives the call that produced it. Restart also needs DL-1 `recover()`, which already moves in-flight steps to RECOVERY_REQUIRED |
| A review-required step reaching COMPLETE without review? | The validator routes `verified` + `review_required` into REVIEWING, and refuses COMPLETE without `approve`. DL-2 uses the stored contract, so a weaker caller copy is refused at `_bind` (digest mismatch) |
| Failed verification represented as verified? | The outcome comes only from the Verifier's re-validated observation. Implementer claims are never read |
| A non-active project continuing? | The loop checks the authoritative project before every dispatch. The validator refuses progress events. A project escalated mid-call leads to the result being refused and the step reduced |
| A duplicate request triggering another role call? | A receipt clears ownership and blocks every later dispatch in the call |
| Truthy or invalid Python types bypassing a decision? | Re-validation through exact classes with `StrictBool` / `StrictInt` / enums and JSON mode, so `review_required=0`, `recommendation=True`, `attempt="1"` and `outcome="passed"` are all rejected |

## 5. Post-implementation adversarial self-review

These attacks were attempted through supported public APIs. Each one has a
regression test.

- **Unauthorized COMPLETE.** Tried: a boastful implementer report, an accept
  over failed verification, over `changes_requested` or over
  `needs_human_review`, a forged COMPLETE snapshot from the caller, a
  weaker-policy contract copy, and a required human acceptance. Each is
  refused or escalated.
- **Unbounded retries.** Tried: a Planner that always retries
  (`max_attempts` 1, 3 and 5), and a store that refuses every recovery. The
  first case ends FAILED with exactly `max_attempts` implementer calls. The
  second ends at `iteration_bound_reached` after a single dispatch.
- **Duplicate dispatch.** Tried, with zero additional dispatches each time:
  - a replayed `begin_attempt`, `implementation_returned`,
    `verification_observed` and `decide_acceptance` (a test store subclass
    that applies the request twice);
  - a port that pre-records its own result;
  - a re-entrant nested `run()`;
  - instance reuse after a crash;
  - a new controller in the same session.
- **Bypassed recovery.** A reopened store refuses the run until `recover()`.
  After recovery, in-flight steps are RECOVERY_REQUIRED and are not
  dispatched.
- **Cross-step authority confusion.** Tried a contract of another step, a
  project run, a step run or a plan version of another run, and forged
  identities. All raise `InnerLoopInputError` with no write.
- **A role claim treated as evidence.** Implementer claims are never
  consulted. A port raising a store exception type
  (`RecoveryRequiredError`) is a role failure, not a store verdict.
- **A real execution path.** `socket`, `subprocess`, `os.system` and
  `os.getenv` are patched to fail during a full retry-then-complete run.
  AST checks pin the module's imports and its identifier surface. No CLI
  reference exists.

**One material finding was fixed.** The first draft passed ports the very
`StepContract` and `StepRun` objects the loop later decides with. A port can
change a "frozen" pydantic model with `object.__setattr__`. The validator
still decides from the stored contract, so this failed closed. But it could
change the loop's binding digest and its iteration bound. Every port call now
receives fresh re-parsed copies
(`test_a_port_that_mutates_its_frozen_inputs_cannot_change_the_loops_decisions`).

## 6. Test evidence

`tests/test_control_plane_dl2.py` has **94** tests. Each acceptance item
maps to tests as follows:

1. **Complete with review:** `test_a_step_completes_with_verification_and_required_review`.
2. **Complete without review:** `test_a_step_completes_without_review_when_its_contract_permits`.
3. **Verification failure, retry, success:** `test_a_failed_verification_is_retried_and_then_succeeds`.
4. **Attempt-budget exhaustion:** `test_the_attempt_budget_is_never_exceeded`, and
   `test_a_planner_that_always_retries_is_bounded_by_the_contract` with
   `max_attempts` 1, 3 and 5.
5. **Reviewer rejection or changes requested:**
   `test_a_review_that_does_not_approve_cannot_be_accepted` (both verdicts) and
   `test_changes_requested_can_lead_to_an_authorized_retry`.
6. **Planner inconsistent with the facts:**
   `test_an_accept_recommendation_against_failed_verification_escalates`,
   `test_recommendations_dl2_cannot_act_on_end_at_a_human` (×4) and
   `test_a_project_contract_conflict_escalates_the_project`.
7. **Human acceptance required but unavailable:**
   `test_a_required_human_acceptance_is_never_fabricated` and
   `test_a_human_acceptance_step_may_still_retry_without_a_human`.
8. **Project escalation during the loop:**
   `test_a_non_active_project_is_not_advanced`,
   `test_a_project_escalated_while_the_implementer_runs_stops_the_step`,
   `test_a_project_escalated_by_the_planner_leaves_the_step_at_acceptance` and
   `test_an_untrusted_workspace_stops_the_step_and_the_project`.
9. **Exception from each port:**
   `test_an_in_flight_role_that_raises_requires_recovery` (×3),
   `test_a_planner_that_raises_escalates_without_a_decision` and
   `test_a_crash_leaves_the_persisted_intent_and_restart_never_reruns_it` (×3).
10. **Restart after persisted EXECUTING, VERIFYING and REVIEWING:**
    `test_a_reopened_store_must_be_recovered_and_in_flight_work_is_not_resumed` (×3),
    `test_a_new_controller_in_the_same_session_never_resumes_in_flight_work` (×3),
    and the ACCEPTANCE, READY, terminal and PLANNED resume tests.
11. **Replay without repeated dispatch:**
    `test_a_replayed_receipt_never_dispatches_a_role` (×3),
    `test_a_replayed_decision_does_not_start_another_attempt`,
    `test_re_sending_a_recorded_request_is_a_receipt_and_dispatches_nothing` and
    `test_a_role_that_pre_records_its_own_result_gets_no_further_dispatch`.
12. **Mismatched binding:**
    `test_objects_that_do_not_belong_together_are_refused` (×7),
    `test_a_contract_that_is_not_exactly_a_validated_step_contract_is_refused` (×3),
    `test_a_weaker_policy_copy_of_the_contract_is_refused` and
    `test_a_supplied_snapshot_state_is_never_consulted`.
13. **Malformed outputs:**
    `test_a_malformed_or_misbound_in_flight_output_requires_recovery` (×15),
    `test_a_malformed_or_misbound_planner_decision_escalates` (×6),
    `test_a_stale_verification_from_the_previous_attempt_is_not_accepted` and
    `test_implementer_claims_never_stand_in_for_verification`.
14. **No live execution:**
    `test_the_loop_runs_with_every_execution_path_disabled`,
    `test_the_inner_loop_imports_nothing_that_executes`,
    `test_the_inner_loop_has_no_workspace_or_path_surface` and
    `test_no_cli_command_reaches_the_inner_loop`. DL-1's package-wide import
    guard also now covers `inner_loop.py`.
15. **DL-1 regression:** `tests/test_control_plane_dl1.py`, unchanged, 90 passed.

## 7. Limitations

- **The DL-1 hard gates remain open, and each is a hard gate before DL-4.**
  Fake-agent tests do not solve any of them:
  1. human-approval provenance;
  2. verification provenance and persisted evidence;
  3. policy-issuance provenance;
  4. workspace/store containment and real-adapter authorization.

  In DL-2 the `VerifierPort` output **is** the verification fact, by type. The
  loop cannot prove the port is AIDO's deterministic 5F2D verification.
- **Role-output binding omits the step run.** DL-1 binds an output to
  `(step_contract_sha256, attempt)`, so two project runs of the same contract
  share bindings. DL-2 accepts only what its own dispatch returns, but it
  cannot tell a port's cached output for another run from a fresh one. The
  test `test_known_limitation_role_output_binding_does_not_name_the_step_run`
  pins this. Fixing it would change a frozen DL-1 model, which DL-2 does not
  do; it belongs to the evidence-provenance gate.
- **Human acceptance is unavailable by design.** A step whose contract
  requires one cannot complete in DL-2; it ends HUMAN_REQUIRED. Nothing leaves
  HUMAN_REQUIRED or RECOVERY_REQUIRED (unchanged from DL-1).
- **Recovery is coarse.** A role failure in flight always means
  RECOVERY_REQUIRED, even when the effect provably did not happen.
- **The Planner may be asked again at ACCEPTANCE after a crash.** ACCEPTANCE
  is not an in-flight state in DL-1, because no external effect was
  requested. So a crash during `decide_step` lets a later call ask again.
  `begin_attempt` is never repeated that way.
- **Trust root.** The injected store and ports are trusted to be what they
  claim. A store subclass can lie (the tests use subclasses only to simulate
  replay and refusal). DL-2 executes whatever port object the caller injects,
  and it ships no real adapter.
- **Unused roles.** The Tester is not dispatched (DL-1 has no Tester
  authority, and `RECOMMEND_RETRY_TEST` ends at a human).
  `PlannerPort.propose_step_contract` is not used, because contracts are
  pre-recorded.
- **ALPHA-1B.** DL-2 adds a file under `src/`. As with DL-1, ALPHA-1B's S0
  preflight STOPs while it is present in the runtime checkout.

## 8. Frozen-contract contradictions

**None that required stopping.** No DL-1 code, contract, rule or persistence
behavior was changed. The only DL-1 package edits are additive exports in
`__init__.py` and two docstring sentences in `ports.py` that said no code
calls a port.

Noted divergences:

- **DL-1 doc §5 versus the DL-2 prompt.** DL-1's foundation doc §5 lists, as
  things "DL-2 must also add":
  - a human-resolution path;
  - a RECOVERY_REQUIRED re-proof path;
  - per-transition evidence references.

  The DL-2 prompt explicitly forbids the first two and scopes provenance out.
  DL-2 follows the prompt, so those items remain open for a later, separately
  authorized phase.
- **Contract derivation.** DL-1 §5 step 1 (Planner proposal → issue → record)
  is likewise not in DL-2, which accepts pre-recorded contracts.
- **Binding.** The step-run omission in role-output binding (§7) is a property
  of the frozen DL-1 model, not something DL-2 introduced.

## 9. Recommended DL-3 entry conditions

1. Independent review accepts DL-2 (this document's status changes only then).
2. DL-3 consumes `InnerLoopOutcome` only through its authoritative
   `step_run` / `project_run`. It never uses `cause`, `dispatches` or a
   receipt as authority.
3. Scheduling (`mark_ready`), re-planning and the project integration gate
   are added as DL-1-style validator rules and events. DL-2's "only advance a
   READY step" boundary stays.
4. DL-3 does not add automatic exits from HUMAN_REQUIRED or RECOVERY_REQUIRED.
   Those need their own authorized design.
5. The four hard gates and the step-run binding limitation stay listed as
   open, and are closed before DL-4 wires any real adapter.

## 10. Validation

Run on Windows with the project venv, 2026-10-22, on top of `1a6dd24`.

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_control_plane_dl2.py -q -p no:cacheprovider` | 94 passed, 0 skipped, 0 failed |
| `.venv/Scripts/python.exe -m pytest tests/test_control_plane_dl1.py -q -p no:cacheprovider` | 90 passed, 0 skipped, 0 failed |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` (`testpaths = ["tests"]`) | **4100 passed**, 0 skipped, 0 failed, 1 warning, 533.6 s |

The one warning is a Pydantic serializer warning from the existing
`tests/test_supervised_implementer.py::test_a_post_load_forged_block_is_refused_by_revalidation`.
It is unrelated to DL-2.

The `experiments/` suites were not run. They are outside `testpaths` and
include Node/Pi-executing tests, which this phase forbids.
