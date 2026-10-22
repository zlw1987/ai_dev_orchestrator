# DL-3 — Offline Project Outer Loop

| Field | Value |
|---|---|
| Status | **IMPLEMENTED — PENDING INDEPENDENT REVIEW** (not accepted) |
| Date | 2026-10-22 |
| Base | `0af222f` (DL-2, independently reviewed and accepted within its offline scope) on top of `1a6dd24` (DL-1 + FU1) |
| Roadmap mapping | M6C outer loop (`AIDO_RUNTIME_HARNESS_ROADMAP.md` §16.1), offline subset. The §20 project integration gate is **assessed but not implemented**, because it has no evidence source (§5) |
| Code | `src/ai_dev_orchestrator/control_plane/outer_loop.py`, plus one read-only store method |
| Tests | `tests/test_control_plane_dl3.py` (82 tests) |
| Live execution | **None.** No model, endpoint, process, shell, socket, Git, Pi, Node, environment read, or target workspace |

## 1. What DL-3 is

DL-3 adds one controller, `ProjectOuterLoop`, and one assessment,
`assess_project_completion`. The controller coordinates the **recorded** Step
Runs of one **recorded** Project Run:

- it schedules them by the plan's recorded dependencies;
- it hands each schedulable step to the accepted DL-2 `StepInnerLoop`;
- it stops all scheduling when a step is blocked, or when the run's plan has
  been superseded;
- it assesses what the persisted state can prove about project completion.

It is a coordinator over DL-1 and DL-2 and nothing else:

- It adds **no** event, rule, state or table.
- It does **not** change the validator.
- It uses DL-1's `mark_ready` and project `escalate` events unchanged, and
  DL-2 unchanged.

It is **not** any of these:

- a plan issuer or activator;
- a run or step-run creator;
- a human-acceptance or human-resolution path;
- a re-proof path out of RECOVERY_REQUIRED;
- a project integration verifier;
- a real adapter;
- a CLI command.

## 2. Public API

```python
from ai_dev_orchestrator.control_plane import (
    ProjectOuterLoop, OuterLoopOutcome, OuterLoopStop, OuterLoopInputError,
    OuterLoopReentryError, ProjectCompletionAssessment, StepInvocation,
    assess_project_completion,
)

loop = ProjectOuterLoop(store, ports)            # ControlPlaneStore, RolePorts
outcome = loop.run(
    project_run=..., project_contract=..., execution_plan=...,  # identity only
    max_steps=None,                              # optional: can only lower the bound
)
assessment = assess_project_completion(store, project_run_id)  # read-only
```

`OuterLoopOutcome`:

| Field | Meaning |
|---|---|
| `stop` | Why the loop returned (`OuterLoopStop`, below). **No value means COMPLETE** |
| `project_run`, `step_runs`, `completion` | The store's **authoritative** reads, taken after the last transition |
| `invocations` | One `StepInvocation` per DL-2 call: step, state before, DL-2's `InnerLoopStop`, DL-2's authoritative state after, and the dispatch count. Audit only |
| `marked_ready` | Step ids this call moved PLANNED → READY |
| `escalation` | `step_blocked` / `plan_superseded`, if this call escalated the project |
| `refusal_code` | The last DL-1 `RefusalCode` the loop received, if any |
| `replan_recommended_step_ids` | HUMAN_REQUIRED steps whose last audit-log rule is a Planner RECOMMEND_REPLAN / PLAN_CONFLICT. **Advisory**; the loop acts identically on every blocked step |

`OuterLoopStop`:

- `project_not_active`;
- `step_blocked` (escalated);
- `plan_superseded` (escalated);
- `plan_work_complete_integration_gate_unavailable`;
- `no_schedulable_step`;
- `step_not_settled`;
- `step_budget_reached`;
- `transition_refused`;
- `replayed_receipt`;
- `iteration_bound_reached` (a backstop).

`outer_request_id(subject_id, expected_state_version, label)` is the
deterministic DL-3 idempotency key. Its `dl3:` namespace is disjoint from
DL-2's `dl2:` keys.

**Store extension (the only DL-1 change).**
`ControlPlaneStore.list_execution_plans(project_contract_sha256)` is a
read-only, additive method:

- It returns every recorded plan version of one Project Contract, oldest
  first.
- Each plan is re-proven like any contract load.
- The set must be the unbroken chain that `record_execution_plan` builds
  (versions 1..N, each superseding the previous one), or the read raises
  `StateUntrustedError`.

DL-1's schema makes that chain linear: `UNIQUE (kind, scope_sha256, step_id,
version)` allows one plan per version per Project Contract. Nothing else in
the store changed.

## 3. Architecture and lifecycle

### 3.1 Reconstruction

`run()` reconstructs the project from the store only:

1. Each caller object is re-parsed through its **exact** class. Subclasses,
   `model_construct` and non-models are refused with `OuterLoopInputError`.
2. The project run is re-read through the store's gated, re-proven
   `get_project_run`. Its five identity fields must equal the caller's.
3. The caller's Project Contract and Execution Plan must hash to the run's
   creation-bound digests.
4. From then on the caller's objects are never used again. Every iteration
   re-reads, from the store:
   - the project run;
   - every step run, via `list_step_runs`, which proves bindings, logs,
     contracts and the cross-object combination;
   - the plan, by the run's bound digest;
   - the recorded plan chain.

So individually valid objects that do not belong together are refused before
anything is read as authority. That covers another project's contract,
another plan version, another run, and forged identity fields. A snapshot's
state fields are never consulted: a caller copy claiming `COMPLETE` changes
nothing.

### 3.2 Scheduling (`_next_action`, pure and deterministic)

Each iteration takes exactly one action, chosen in this order from proven
state only:

| # | Condition | Action |
|---|---|---|
| 1 | Some step is EXECUTING / VERIFYING / REVIEWING | Hand it to DL-2, which never resumes it and reduces it to RECOVERY_REQUIRED (no dispatch). This applies **whatever the project state**, because the reduction is authority-reducing (§6, finding F-1). If DL-3 already handed this step to DL-2 in this call: stop `step_not_settled` |
| 2 | Project is not ACTIVE | Stop `project_not_active` |
| 3 | A later plan version is recorded for the run's Project Contract | `escalate` the project (`plan_superseded`), then stop |
| 4 | Some step is FAILED / HUMAN_REQUIRED / RECOVERY_REQUIRED | `escalate` the project (`step_blocked`), then stop |
| 5 | A step is READY or ACCEPTANCE, in plan order | Hand it to DL-2. This resumes scheduled work first. If already handed over in this call: `step_not_settled`. If the step budget is spent: `step_budget_reached` |
| 6 | A PLANNED step whose every `depends_on` step run is COMPLETE, in plan order | `mark_ready`. DL-1's validator independently re-proves each dependency's COMPLETE. If this step was already marked in this call: `step_not_settled`. If the budget is spent: `step_budget_reached` |
| 7 | Every plan step has a COMPLETE step run | Stop `plan_work_complete_integration_gate_unavailable` |
| 8 | Otherwise (for example, missing step runs or unsatisfiable dependencies) | Stop `no_schedulable_step` |

**Dependency authority.** The only source of dependencies is
`PlannedStep.depends_on` in the run's bound Execution Plan. Every Step Contract
must copy it verbatim (`validate_step_contract`), and DL-1's validator uses the
contract's copy for `mark_ready`. A step may depend only on earlier plan steps,
so plan order is a topological order and scheduling in plan order is
deterministic. Nothing is inferred from objectives, requirements or any other
prose. **No dependency gap was found:** the frozen models already express
exactly the data a safe scheduler needs.

**No blocked-step continuation.** The Project Contract, the plan and the step
contracts carry no policy that authorizes continuing independent steps after
one is blocked. So DL-3 schedules nothing further and records the stop as a
project escalation. It never skips a blocked step optimistically.

### 3.3 DL-2 integration

DL-3 never calls a role port. An AST test pins this: the module contains none
of `implement`, `verify`, `review`, `decide_step`, `planner`, and the other
port names.

- Each schedulable step gets a **fresh** `StepInnerLoop(store, ports)`.
- DL-2 receives the store's own reads of the run, the step run, the Project
  Contract, the plan and the step contract.
- DL-3 checks that DL-2's outcome names the same step run and project run.
- It records `outcome.step_run.state` for audit.
- It takes its next decision from a fresh store read, never from `cause`,
  `dispatches` or a receipt.

DL-2 is invoked **at most once per step run per `run()` call**. Step-run
creation is not DL-3's job. A plan step without a recorded step run cannot be
scheduled and blocks plan completion (`missing_step_ids`).

### 3.4 Bounds

| Bound | Value |
|---|---|
| Iterations | `2 × len(plan.steps) + 3`: at most one `mark_ready` and one DL-2 call per step, one escalation, and slack. `iteration_bound_reached` is a backstop that no test path reaches |
| DL-2 invocations for READY / ACCEPTANCE | ≤ `min(max_steps, len(plan.steps))`. `max_steps` must be a positive `int`; `bool`, `float`, `str`, `0` and negatives are refused. It can only lower the bound |
| Per step and per call | One `mark_ready`, one DL-2 invocation. A step that does not settle stops the loop instead of spinning it |
| Inside DL-2 | DL-2's own bound (`5 × max_attempts + 3`) and the contract's `max_attempts` |

## 4. Replay, restart and recovery

- **Deterministic requests.** `mark_ready` uses
  `outer_request_id(step_run_id, version, "mark_ready")`, and escalation uses
  `outer_request_id(project_run_id, version, "escalate:<code>")`, with a
  reason derived only from proven state. Re-sending one returns DL-1's
  receipt. Reusing the slot for other content is `duplicate_request_conflict`.
- **A receipt is not permission.** A duplicate `mark_ready` or escalation
  stops the loop (`replayed_receipt`). No step is handed to DL-2 because of
  one.
- **Reopen.** Every authoritative read goes through DL-1's per-session gate,
  so a reopened store raises `RecoveryRequiredError` from both `run()` and
  `assess_project_completion()` until the caller has run `recover()`. DL-3
  does not call `recover()` itself. The DL-1 recovery requirements are the
  caller's explicit act, exactly as for DL-2.
- **Restart preserves progress.** COMPLETE steps are terminal and never handed
  to DL-2 again, so a restarted run continues with the next schedulable step.
- **In-flight work is never resumed.**
  - After a crash (`BaseException`), `recover()` in the next session moves the
    in-flight step to RECOVERY_REQUIRED, and the project with it.
  - In the same session, the next DL-3 call hands the in-flight step to DL-2,
    which reduces it without dispatching.

  Either way the crashed role is dispatched exactly once.
- **Re-entry.** A module-level guard keyed by `(store, project_run_id)` is held
  for the duration of one `run()`. A port that re-enters DL-3 for the same
  project gets `OuterLoopReentryError` before anything is read or written. The
  outer DL-2 call then sees an ordinary role failure. A port that re-enters
  **DL-2 directly** is handled by DL-2's accepted ownership rules: the step is
  reduced, and nothing is dispatched twice.
- **Partial failure.**
  - Every transition is one DL-1 atomic act.
  - A `StoreError` propagates unchanged.
  - A refused transition stops the loop (`transition_refused`) with the
    refusal code.

  No stop value means COMPLETE, and the project is never COMPLETE.

## 5. The completion gate

`assess_project_completion(store, project_run_id)` reads only the store. It
takes no snapshot, flag, Planner output or role claim. It distinguishes the
four levels the prompt names:

| Level | Field | Can it be `True` in DL-3? |
|---|---|---|
| 1. Every recorded offline Step Run is COMPLETE | `all_recorded_step_runs_complete` | Yes, computed |
| 2. The recorded plan's work is complete: every plan step has a step run and each is COMPLETE | `plan_work_complete` | Yes, computed |
| 3. The Project Contract's acceptance criteria and protected invariants are authoritatively satisfied | `acceptance_criteria_satisfied`, `protected_invariants_satisfied` | **No, `Literal[False]` by type** |
| 4. The Project Run may enter COMPLETE | `complete_authorized` | **No, `Literal[False]` by type** |

Level 1 does not imply level 2, because a plan step may have no step run. The
test `test_the_completion_levels_are_distinct` exercises exactly that case.

Levels 3 and 4 cannot be proven because no offline evidence source exists.
Each step's verification is evidence only about that step's contract (roadmap
§20). Beyond that, DL-1 and DL-2 have:

- no project integration verification;
- no cross-step invariant check;
- no project-level review;
- no project-level human acceptance capture.

On top of that, the step-level evidence itself sits behind open hard gates
(§7). Inventing any of these sources is forbidden, so the model cannot express
a `True`.

When the plan's work is complete, DL-3 stops at
`plan_work_complete_integration_gate_unavailable` and leaves the project
**ACTIVE**:

- The persisted state stays truthful: not COMPLETE.
- A future, separately authorized integration gate can act on an ACTIVE run.
  Escalating would force it through HUMAN_REQUIRED, which has no exit.
- DL-3 never sends `request_complete`; an AST/source test pins this.
- DL-1's `request_complete` refusal (`unsupported_in_dl1`) is **unchanged** and
  remains the mechanical backstop, so even a faulty assessment could not
  complete a project.

`blockers` lists every reason, in a closed vocabulary:

- `project_not_active`;
- `plan_superseded`;
- `step_run_missing`;
- `step_not_complete`;
- `step_blocked`;
- `acceptance_criteria_unproven`, `protected_invariants_unproven` and
  `integration_gate_unavailable` (these three are always present).

## 5a. Re-planning and plan-version boundaries

- **A Planner recommendation installs nothing.** RECOMMEND_REPLAN and
  PLAN_CONFLICT still end the step at HUMAN_REQUIRED, by DL-1's frozen rule.
  DL-3 then escalates the project. `replan_recommended_step_ids` reports it,
  from the audit log, as advisory. No plan is recorded and no run is created.
- **A run executes only its creation-bound plan.** DL-1's `run_bindings`
  already make the plan digest and version immutable for a run. A different
  plan supplied to `run()` is refused. A Step Contract of another plan cannot
  join the run (`validate_step_contract` at `create_step_run`).
- **Superseded authority halts.** Before scheduling, DL-3 checks the recorded
  plan chain. If a later version than the run's is recorded, the run is on
  superseded authority. DL-3 escalates (`plan_superseded`) instead of
  scheduling, so at any moment **DL-3 advances only runs bound to the latest
  recorded plan version** of their Project Contract.
- **No activation path exists, and that is the fail-closed boundary.**
  Recording a plan in DL-1 needs no approval, and plans carry no issuance
  provenance. So "recorded" is not "authorized", and DL-3 never treats a
  recorded successor as something to execute. A replacement run on the new
  plan has to be created by the caller (`create_project_run`), and it starts
  with its own step runs. It never inherits the old run's progress, which
  `test_a_run_on_the_current_plan_proceeds_with_its_own_steps_only` pins.
  **Missing capability:** an authorized plan-activation / supersession decision
  that would let a human or a policy say "plan v2 replaces v1 for this
  project". It is not invented here.

## 6. Adversarial analysis

### 6.1 Before coding

| Object or transition | Who creates / mutates it | What proves it | Enforcement in DL-3 |
|---|---|---|---|
| Project Run | DL-1 `create_project_run`; only the store mutates it, via validated events | `run_bindings` + transition log + contract hashes | Re-read through the gated read every iteration; the caller's copy is identity-checked only |
| Step Runs | DL-1 `create_step_run` (caller). DL-3 creates none | Same, plus `validate_step_contract` against the run's contract and plan | `list_step_runs` proves all of them or raises |
| Execution Plan | Recorded by any caller (no provenance, gate 3) | Content digest; chain checked at record time and again by `list_execution_plans` | Loaded only by the run's bound digest; a successor halts the run |
| Step Contract | Recorded by any caller (policy provenance, gate 3) | Issuance rules re-run at record and at consumption | DL-3 passes the store's copy to DL-2 |
| `mark_ready` | DL-3 | Validator re-proves every dependency's COMPLETE | Deterministic id; once per step per call; a receipt stops the loop |
| Project `escalate` | DL-3 | Validator (authority-reducing) | Deterministic id and reason; a receipt stops the loop |
| DL-2 invocation | DL-3 | DL-2's ownership rules | Once per step per call; the outcome is identity-checked; decisions come from a fresh read |
| Completion | Nobody in DL-3 | Nothing offline can prove levels 3 and 4 | `Literal[False]`; DL-1's refusal stays the backstop |

The failure cases designed against before coding:

- caller-snapshot authority;
- prose-inferred dependencies;
- a double dispatch on replay, restart, re-instantiation or re-entry;
- unbounded spinning on a step that does not settle;
- optimistic skipping of blocked steps;
- a Planner or role claim counted as completion;
- a recorded-but-unauthorized plan being executed;
- one run consuming another run's steps;
- truthy or malformed inputs failing open.

### 6.2 Post-implementation self-review

Counterexamples were built through supported, public APIs. Each one has a
regression test.

- **F-1 (material, fixed).** The first draft checked "project not ACTIVE" and
  "plan superseded" before in-flight steps. Counterexample: a port escalates
  the project and then crashes (`BaseException`). The step stays EXECUTING
  behind a HUMAN_REQUIRED project, and every later DL-3 call stopped at
  `project_not_active` without reducing it. That left an unproven in-flight
  state stranded for the whole session. In-flight reduction is
  authority-reducing and dispatches nothing, so it now comes first, whatever
  the project state. The project's severity is never lowered. Tests:
  - `test_an_in_flight_step_behind_an_escalated_project_is_reduced_not_stranded`,
    confirmed to fail on the original ordering and pass after the fix;
  - `test_an_in_flight_step_is_reduced_before_a_supersession_escalation`.
- **Mismatched trusted objects.** Other contract, other plan, other run with
  these contracts, forged identity, plan v2 and an unknown run: each is refused
  before any write or dispatch. Another run's step runs are never driven.
- **Post-validation mutation.** A port that `object.__setattr__`s the caller's
  plan and run mid-run has no effect, because DL-3 never reads them again.
- **Re-entrant and nested orchestration.** Re-entering DL-3 is refused with no
  write. Re-entering DL-2 directly reduces the step, with no double dispatch.
- **Duplicate transitions and stale versions.**
  - A replaying store for `mark_ready` stops at `replayed_receipt` with no DL-2
    call.
  - A replaying store for escalation records exactly one escalation.
  - A reused DL-3 escalation id is a conflict.
- **Store tampering.** A forged COMPLETE/FAILED row makes `run()` and the
  assessment raise `StateUntrustedError`, and `recover()` escalates. A tampered
  plan-chain version column makes both `list_execution_plans` and `run()`
  raise.
- **Partial failure and interruption.** All three in-flight roles were crashed:
  each is dispatched once, and is never re-dispatched after a reopen and
  recovery or in the same session. A store that refuses `recover_interrupted`
  still terminates (`step_not_settled`).
- **Inconsistent stores.** A store that refuses `mark_ready`, one that refuses
  `begin_attempt`, and one that lies that `mark_ready` succeeded: all three
  terminate with at most one `mark_ready` and at most one DL-2 call.
- **Forged or insufficient completion evidence.** Tried:
  - a Planner with a project-complete method (never called);
  - implementer claims of project completion;
  - an assessment re-validated with `complete_authorized=True` (rejected by
    type);
  - `request_complete` after every step is COMPLETE (still
    `unsupported_in_dl1`).
- **Malformed inputs.** Rejected inputs: a `ProjectRun` subclass,
  `model_construct` with invalid fields, a dict, `None`, an unvalidated plan or
  contract, and `max_steps` of `0`, `-1`, `True`, `"1"` and `1.0`.

**Lower-priority improvements, recorded rather than fixed** (none falsifies
authority or causes uncontrolled execution):

- **L-1.** A recorded *successor Step Contract* for a step is not detected the
  way a successor plan is. The step run still executes its own creation-bound,
  re-validated contract. Deciding what supersession of a step contract should
  mean belongs to the policy-issuance gate.
- **L-2.** The supersession halt is a DL-3 rule. Driving a step of a superseded
  run directly through DL-2, which is unchanged, is not refused. The first DL-3
  call on such a run escalates it durably.
- **L-3.** More than one ACTIVE run on the same latest plan is still possible,
  as in DL-1. DL-1 has no API to list project runs, and runs of other sessions
  cannot be read without `recover()`.
- **L-4.** A broken plan chain makes the run undrivable by DL-3
  (`StateUntrustedError`), but DL-1's `recover()` does not check the plan
  chain, so it reports `integrity_ok=True`. This fails closed but is not
  escalated.

## 7. Known limitations and unresolved hard gates

**The four DL-1/DL-2 hard gates remain OPEN.** Each must be closed before DL-4
wires any real adapter, and DL-3 solves none of them:

1. **Human-approval provenance.** `ProjectContractApproval` and
   `HumanStepAcceptance` are exact-phrase checks that any in-process code can
   construct. DL-3 supplies no human acceptance and resolves no human state.
2. **Verification provenance and persisted evidence.** A
   `VerificationObservation` is authoritative by type, and its
   `evidence_sha256` is not persisted or resolved. DL-3's step COMPLETE states
   inherit this. It is one reason completion level 3 is unprovable.
3. **Policy-issuance provenance.** Plans and Step Contracts (`review_required`,
   `human_acceptance_required`, `max_attempts`) can be recorded by any caller.
   DL-3 schedules whatever was recorded. Plan supersession is detected, but
   cannot be authorized.
4. **Workspace/store containment and real-adapter authority.** The store path
   is only absolute with an existing parent. No workspace or adapter exists.

**The role-output binding gap is also OPEN.** It is a required pre-DL-4
closure item. Role outputs bind `(step_contract_sha256, attempt)`, not the Step
Run, so two project runs of one contract share bindings.
`test_known_limitation_role_outputs_do_not_name_the_project_run` pins the
precondition.

Other limitations:

- Project COMPLETE remains unreachable by design (§5).
- Nothing leaves HUMAN_REQUIRED or RECOVERY_REQUIRED.
- Recovery stays coarse (DL-1).
- At ACCEPTANCE, the Planner may be asked again after a crash (DL-2 §7). DL-3
  inherits that behavior unchanged.
- The re-entry guard is in-process and module-level. The store is not
  thread-shareable (`sqlite3` same-thread check).
- **Trust root.** The injected store and ports are trusted to be what they
  claim. Tests use store subclasses only to simulate replay, refusal and lies.
- **ALPHA-1B.** DL-3 adds and changes files under `src/`. As with DL-1 and
  DL-2, ALPHA-1B's S0 preflight STOPs while they are in the runtime checkout.

## 8. Frozen-contract contradictions

**None required stopping.** No DL-1 or DL-2 rule, model, event, state, schema
or behavior was changed. The only changes outside the new module are:

- the additive, read-only `ControlPlaneStore.list_execution_plans`. The store
  schema version is unchanged, because no table changed;
- additive exports and two docstring sentences in `control_plane/__init__.py`.

Boundaries found and kept, not crossed:

- Project completion needs an evidence source that does not exist (§5).
- Plan activation needs an authority that does not exist (§5a).
- DL-1 doc §5 says DL-3 "needs a rule for superseding step runs bound to the old
  plan". DL-3 implements this as a halt, not a migration: no step run is ever
  re-bound or carried across plans.

## 9. Test evidence

`tests/test_control_plane_dl3.py` has **82** tests (61 functions, some
parametrized). Coverage of the required cases:

| Required case | Tests |
|---|---|
| Independent steps complete in deterministic order | `test_independent_steps_complete_in_plan_order`, `test_the_schedule_is_deterministic` |
| Dependency-aware scheduling | `test_dependencies_are_scheduled_in_order` (diamond), `test_a_long_plan_completes_within_its_bound` |
| A step cannot run before its prerequisites | `test_a_step_never_runs_before_its_prerequisites`, `test_a_step_budget_stops_before_the_next_step_is_scheduled` |
| Completed steps not dispatched again | `test_already_completed_steps_are_not_dispatched_again` |
| Verification failure retried within its own budget | `test_a_failed_verification_retries_within_its_own_budget` |
| Failed or escalated step blocks completion | `test_a_failed_step_blocks_the_project_and_no_later_step_runs`, `test_an_escalated_step_blocks_project_completion` (×2), `test_a_required_human_acceptance_is_never_supplied` |
| HUMAN_REQUIRED / RECOVERY_REQUIRED never resolved | `test_human_and_recovery_required_are_never_resolved` (×2), `test_a_recovery_required_project_is_not_further_escalated` |
| Project escalation during a step stops scheduling | `test_a_project_escalated_during_a_step_stops_all_scheduling`, `test_a_project_contract_conflict_stops_the_project`, `test_a_project_that_is_not_active_is_never_scheduled` |
| Restart after a partial run preserves progress | `test_restart_after_a_partial_project_run_preserves_progress`, `test_a_reopened_store_is_not_consumed_before_recovery` |
| Restart during in-flight work does not repeat dispatch | `test_restart_during_in_flight_step_work_never_repeats_the_dispatch` (×3), `test_a_crash_in_the_same_session_is_reduced_not_resumed`, the two F-1 tests |
| Replayed scheduling or project transitions cannot duplicate execution | `test_a_replayed_scheduling_receipt_never_runs_the_step`, `test_re_sending_a_recorded_dl3_request_is_a_receipt`, `test_a_replayed_escalation_is_a_receipt_and_schedules_nothing`, `test_a_dl3_escalation_request_id_cannot_be_reused_for_other_content` |
| Cross-project or cross-plan substitution rejected | `test_cross_project_and_cross_plan_substitution_is_refused` (×6), `test_a_step_contract_of_another_plan_cannot_join_a_run`, `test_one_project_runs_steps_are_never_driven_by_another` |
| Malformed objects cannot bypass validation | `test_malformed_run_objects_cannot_bypass_validation` (×4), `test_malformed_contract_objects_cannot_bypass_validation` (×2), `test_a_malformed_step_budget_is_refused` (×5), `test_bad_constructor_arguments_are_refused`, `test_a_supplied_snapshot_state_is_never_consulted` |
| Plan-version conflicts and unauthorized replanning fail closed | `test_a_planner_replan_recommendation_installs_nothing`, `test_a_recorded_successor_plan_halts_the_superseded_run`, `test_a_successor_plan_recorded_mid_run_stops_further_scheduling`, `test_a_run_on_the_current_plan_proceeds_with_its_own_steps_only`, `test_the_recorded_plan_chain_is_re_proven`, `test_an_unrelated_project_contract_has_no_recorded_plans` |
| A Planner project-complete claim is insufficient | `test_a_planner_project_complete_claim_is_insufficient`, `test_a_role_claiming_project_completion_changes_nothing` |
| No COMPLETE on insufficient evidence | `test_plan_work_complete_is_not_project_complete`, `test_the_completion_levels_are_distinct`, `test_no_assessment_can_claim_unprovable_levels` (×3), `test_the_assessment_reads_only_the_store`, `test_a_forged_complete_row_is_untrusted_not_complete` |
| Bounds terminate under refusal or inconsistency | `test_the_loop_terminates_under_refusal_and_inconsistent_stores` (×3), `test_a_step_dl2_leaves_unsettled_is_not_invoked_twice`, `test_an_in_flight_step_whose_reduction_is_refused_still_terminates`, `test_the_step_budget_can_only_lower_the_bound` |
| No live execution path | `test_the_outer_loop_runs_with_every_execution_path_disabled`, `test_the_outer_loop_imports_nothing_that_executes`, `test_the_outer_loop_has_no_workspace_path_or_role_surface`, `test_the_outer_loop_never_requests_project_completion`, `test_no_cli_command_reaches_the_outer_loop`; DL-1's package-wide import guard also covers `outer_loop.py` |
| Adversarial (self-review) | `test_re_entering_dl3_for_the_same_project_is_refused_before_any_write`, `test_a_direct_inner_loop_reentry_from_a_port_cannot_double_dispatch`, `test_mutating_the_callers_objects_mid_run_changes_nothing`, `test_the_outcome_is_the_stores_read`, `test_known_limitation_role_outputs_do_not_name_the_project_run` |

### Validation

Run on Windows with the project venv, 2026-10-22, on top of `0af222f`.

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_control_plane_dl3.py -q -p no:cacheprovider` | 82 passed, 0 failed |
| `.venv/Scripts/python.exe -m pytest tests/test_control_plane_dl1.py tests/test_control_plane_dl2.py tests/test_control_plane_dl3.py -q -p no:cacheprovider` | 266 passed (DL-1 90, DL-2 94, DL-3 82), 0 failed; DL-1 and DL-2 test files unchanged |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` (`testpaths = ["tests"]`) | **4182 passed**, 0 skipped, 0 failed, 1 warning, 534.8 s (DL-2's 4100 + DL-3's 82) |

The one warning is the existing Pydantic serializer warning from
`tests/test_supervised_implementer.py::test_a_post_load_forged_block_is_refused_by_revalidation`,
which DL-2 also recorded. It is unrelated to DL-3.

The `experiments/` suites were not run. They are outside `testpaths` and
include Node/Pi-executing tests, which this phase forbids.

## 10. Recommended DL-4 entry conditions

1. Independent review accepts DL-3. This document's status changes only then.
2. All four hard gates in §7 are closed, each with its own design and tests:
   - authenticated human-approval capture;
   - persisted verification evidence that resolves `evidence_sha256` to a 5F2D
     `verification-result.v1` produced by AIDO;
   - policy-issuance provenance for plans and Step Contracts;
   - store and workspace containment plus real-adapter authorization.
3. The role-output binding gap is closed, by binding outputs to the Step Run
   identity (a DL-1 model change that needs its own authorization).
4. A plan-activation authority is designed if re-planning is wanted. Until
   then, the DL-3 halt-on-supersession boundary stays.
5. A project integration gate (§20) is designed with a real evidence source
   before any rule may authorize `request_complete`. The DL-1 refusal is
   lifted only by that design.
6. DL-4 consumes DL-3 outcomes only through their authoritative reads. It never
   treats `invocations`, `replan_recommended_step_ids` or a receipt as
   authority.
7. No automatic exit from HUMAN_REQUIRED or RECOVERY_REQUIRED is added without
   its own authorized design.
