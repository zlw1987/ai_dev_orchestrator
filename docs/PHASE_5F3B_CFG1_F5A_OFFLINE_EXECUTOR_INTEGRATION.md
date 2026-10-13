# Phase 5F3B-CFG1-F5A — Offline Executor Integration (F5A-INT)

```text
STATUS            NON-FROZEN, ADDITIVE. An integration/evidence record.
F5-A              NOT ACCEPTED, NOT FROZEN. HOLD (unchanged).
A2                The implementation direction (unchanged). NOT security-qualified.
A2-3              INCOMPLETE (unchanged). Nothing here clears it.
R-ALIAS           UNRESOLVED (unchanged, not revisited).
LIVE LAUNCH       UNAUTHORIZED, and now MECHANICALLY UNREACHABLE through every
                  supported CFG1 entry point (section 2).
BASE HEAD         3bf223e0d84084db12e80df7dd6d8a027abb2e5a
FU1               on ed69cca: Barrier 2 closed against non-exact identities
                  (F5A-OI-FU1-1, section 2 and F-INT-9); one L21A coverage
                  test restored (section 6.3). Live launch still unauthorized.
CODE              run_executor.py, pi_runtime_provision.py, pi_identity.py,
                  records.py, lifecycle.py
TESTS             tests/test_cfg1_f5a_executor_integration.py (new);
                  tests/pe2c_support.py, tests/cfg1_doubles.py (test seams);
                  adapted existing tests listed in section 6.3
DOES NOT TOUCH    CLAUDE.md; any frozen design document (the F5-A amendment
                  included); win_config_authority.py; cfg1_pi_config.py (L9);
                  AR2; environment.py; pi_manifest.py; the HPP loader, policy,
                  APS and candidates; U126 / P-R1 / FU3 / FU4-A2 evidence; the
                  A2 creation mechanism (handle-relative NtCreateFile).
```

This document records the smallest offline integration of the accepted A2
offline provisioner (`pi_runtime_provision`, FU1 at `3bf223e`) with the CFG1
executor, as the F5-A amendment (R1-FU2) specifies in §7.3, §7.4, §7.6, §7.7,
§7.8/§7.8.1, §11, §15 and §16. It amends nothing. Where this record and the
amendment differ, the amendment remains the reviewed text.

---

## 1. What was integrated

| Amendment clause | Where it now lives |
|---|---|
| §11.2 — `L3R` inserted after L3, before L4; cursor advanced at entry | `run_executor._dispatch_phase` → `_l3r_provision_runtime` |
| §7.4 step 1 — bind inputs; `S` exact; workspace claimed by this run | `_l3r_provision_runtime` (exact `Cfg1PiIdentity`, `workspace_is_claimed_by`) |
| §16 — the `provision_runtime` port in `Cfg1RunPorts` / `default_cfg1_run_ports` | `Cfg1RunPorts.provision_runtime`; default binds `live_runtime_provisioning_not_qualified` (refuses) |
| §7.4 steps 1–2 (admission, LDT, topology, no write) | `pi_runtime_provision.admit_runtime_provision_for_source` → `admit_runtime_provision` (unchanged) |
| Consumption check of the port's return | `pi_runtime_provision.provision_is_admitted_for` (exact type, `ADMITTED`, unreleased, nonce still admitted, same workspace nonce and run root, same profile, same byte source) |
| §7.4 step 3 — write-ahead before the first create | `state.runtime_provision = provision`, only after the consumption check, before `run_runtime_provision` |
| §7.4 steps 4–8 | `run_runtime_provision` (unchanged A2 FU1 code; `_post_pin_validation` now shares `_reprove_topology` with L14, same checks, same reasons) |
| §7.6 item 2 (exposure absence from `C`) and §7.4 step 9 (bind `L`) | `pi_identity.bind_run_provisioned_launch_identity` — read-only, independently re-observes `C` |
| §7.4 step 9 — the provision records `L` | `pi_runtime_provision.record_launch_identity` (state `BOUND`) |
| §7.4 step 9 — `state.pi_identity` replaced by `L`; `S` dropped | `_l3r_provision_runtime` last line |
| §7.4 step 10 — refusal mapping | anticipated → `RUNTIME_PROVISIONING_FAILED` at `L3R`; other raise → `UNEXPECTED_STEP_FAILURE` at `L3R`; nothing deleted |
| §7.7 / §11.5 — L14 executor precondition, before `build_supervisor` | `_l14_runtime_provision_precondition` → `pi_runtime_provision.reprove_provision_for_launch`, then the unchanged `reprove_pi_identity_for_launch(L)` |
| §7.7 — L21A input is `L` | automatic: `state.pi_identity` **is** `L`; `reobserve_pi_profile_after_runtime` unchanged |
| §7.8 — release at L27 entry, unconditionally, once | `_closure_l27_release_runtime_provision`, first statement of `_closure_l27_workspace`, before the W check, the frozen re-proof and removal |
| §7.8.1 / §11.7 — derived `live_references_released` | `_derive_live_references_released` → `pi_runtime_provision.provision_live_references_proven_released` |
| §11.1 — v3-only vocabulary, R3-S15 | `lifecycle.REFUSAL_STEPS_V3`; `records.PRE_DISPATCH_REFUSAL_CODES_V3`, `REFUSAL_CODES_BY_STEP_V3`, R3-S15 in `_require_valid_cfg1_run_payload_v3` only |

`Cfg1PiIdentity` gained no slot (§11.4). `reprove_pi_identity_for_launch`,
`reobserve_pi_profile_after_runtime`, `build_pi_argv`, the child-environment
builder (T-4) and every v1/v2 object are unchanged.

---

## 2. The offline/live barrier — what prevents a real launch

A2-3 is not qualified, so this phase had to integrate provisioning **without**
making it reachable from production and without enabling any real Node/Pi
launch through the F5-A path. Two independent mechanical barriers do this.
Neither reads an environment variable, a flag, a configuration key or a caller
assertion; removing either is a code change under a separate authorization.

**Barrier 1 — the genuine executor cannot provision.**
`default_cfg1_run_ports` binds `provision_runtime =
pi_runtime_provision.live_runtime_provisioning_not_qualified`, whose whole body
is `_refuse(LIVE_PROVISIONING_NOT_QUALIFIED)`. It performs no I/O. Because L3R is
unconditional and precedes L4, every run through the genuine executor refuses at
`L3R` with `RUNTIME_PROVISIONING_FAILED` (console code
`F5A_LIVE_PROVISIONING_NOT_QUALIFIED`) **before** any credential read, route
contact, broker, config, extension, copy or process. `stage_runner.run_cfg1_stage`
accepts no executor and no ports; it binds `bind_genuine_cfg1_run_executor`,
which closes over `default_cfg1_run_ports`. So the production stage runner, the
genuine executor binding and `execute_cfg1_run(…, ports=default_cfg1_run_ports(…))`
all halt at L3R. (Consequence, stated plainly: the production path can no
longer launch Pi from the ambient installation either. That launch is the F5-A
hazard itself, and the amendment makes L3R mandatory.)

**Barrier 2 — the default supervisor builder has no construction path.**
*(Corrected by FU1, finding F5A-OI-FU1-1.)* As first committed, Barrier 2 was a
type guard — `default_cfg1_run_ports._build_supervisor` refused
`type(identity) is Cfg1PiIdentity` and then built a real `PiRpcSupervisor`. That
was not a barrier: the frozen AR2 `build_pi_argv` consumes plain attributes
(`node_executable`, `pi_cli_js`) and never enforces the CFG1 type, so a
duck-typed or malformed identity passed the guard and reached the real
constructor. The barrier now depends on **no** input: the body of
`_build_supervisor` is one unconditional `raise RuntimeError("cfg1 live pi launch
is not qualified")`, executed before any argument, the environment, a flag or a
caller claim is read, and the construction code itself (`PiRpcSupervisor`,
`build_pi_argv`, and their imports) is **absent** from `run_executor.py` — there
is nothing behind a guard to reach. A separately authorized, independently
accepted live-enablement phase must restore it (argv provider/model from the
frozen `PROVIDER_ID` / `CFG1_MODEL_ID`, per R-40). The L14 precondition still
admits **only** the genuine L3R launch identity
(`state.pi_identity is provision.launch_identity`), so a caller that composes the
genuine offline provisioner with the genuine builder reaches L14 and is refused
there: no real supervisor is constructed and `launch()` is never called
(`test_composing_the_offline_provisioner_with_the_genuine_builder_never_launches`).

**Proof surface (tests, all offline).**
`test_the_default_binding_refuses_provisioning_before_any_io`,
`test_the_genuine_executor_binding_halts_at_l3r_before_credentials_or_any_process`
(default ports with only Git resolution, the synthetic PATH, the L3
verification and repository observation replaced; `read_connection` never
called; a process tripwire sees no Node),
`test_the_genuine_supervisor_builder_refuses_every_genuine_cfg1_identity`
(a `PiRpcSupervisor` tripwire is never constructed),
`test_the_default_supervisor_builder_refuses_duck_typed_and_malformed_identities_before_construction`
(FU1: a genuine-class object, a slotted lookalike, a `SimpleNamespace`, a dict,
a class literally named `Cfg1PiIdentity`, `None`, `object()`, an int, a string,
an empty tuple and an attribute-recording object all raise; `PiRpcSupervisor`
and `build_pi_argv` are replaced with recorders and never called; a
non-delegating process tripwire sees nothing; `os.environ` is replaced with a
read spy and sees nothing; the extension/environment/identity arguments are
never even attribute-read),
`test_the_default_supervisor_builder_refusal_is_independent_of_environment_and_flags`,
the composition test above, and `test_static_audit_of_the_barrier` (AST: the
default binding names the refusing port; that port is a single unconditional
refusal; the builder body is exactly one `raise`; `PiRpcSupervisor` and
`build_pi_argv` are not named anywhere in `run_executor.py`, imports included;
exactly one `.launch()` call exists and it follows the L14 precondition; L3R
precedes `read_connection`; the provisioner reads no environment). The first
two new tests fail against the type-guard form of the barrier (verified by
restoring it).

**What the barrier does not cover (stated, not closed).** A caller who writes
its *own* process-launching supervisor (or calls AR2's `build_pi_argv` and
`subprocess` itself) and passes it as `build_supervisor` is authoring a new live
harness; that is not a supported CFG1 entry point, and same-process code
authorship is outside the CFG1 threat model exactly as monkeypatching is. The
offline suite's `FakeSupervisor` launches nothing.

---

## 3. Authority binding, as the code enforces it

| Object | Bound to | Checked where (consumption) |
|---|---|---|
| Workspace / run root `R` | the run's own minted, claimed `Cfg1RunWorkspace`; root and identity derived, never supplied | L3R entry (`workspace_is_claimed_by`); admission and before the first create (`_consume_authority`, unchanged); L14 (`verify_cfg1_run_workspace`, claim, nonce equality) |
| Profile `X` | `S.matched_profile_id`; eligible in the sealed snapshot | admission and before the first create; `provision_is_admitted_for`; the binder (`eligible_profile_view`); L14 frozen re-proof |
| Inventory `I` | the source's own complete walk, accepted only when its content-derived fingerprint equals `X`'s sealed one | admission and before the first create; the run's second source walk |
| Byte source | `S.pi_package_root`, read only, every byte verified before persist | `provision_is_admitted_for` (same root as `S`); §7.4B (unchanged) |
| Launch identity `L` | `C`, `C\dist\cli.js`, `I_c`, `X`, node from `S` | binder re-observes `C` (walk = `X`, exposures absent, identity = `I_c`, root ≠ `S`'s); `record_launch_identity` (names exactly this provision's root, cli, `I_c`, profile; once); L14 (`state.pi_identity is provision.launch_identity`, `launch is provision._launch_identity`) |
| Final pins | the four LDT files of this provision | L14 re-proves each FROM ITS HANDLE (plain regular file, same id) and by path (same id), plus T-NM/T-CANON/T-PLAIN/T-BUN/T-RT and `RT`/`C` identities |

`S`, `L`, the profile and the workspace stay distinct objects: `S` is only ever
the byte source and the node supplier; `L` is constructible only by P or by the
binder; a provision is not a launch identity and grants nothing until `L` is
recorded in it and re-proved at L14. A port return that is foreign
(another workspace, profile or byte source), already run, released,
uninitialised or not a provision is **never adopted**, so the executor never runs
it and never releases it.

---

## 4. Lifecycle and release truth

* **Write-ahead.** The provision is adopted (stored) after its consumption check
  and before its first create; from then on every exit path — refusal at L3R,
  any later refusal, L14 precondition failure, an unexpected raise, success —
  reaches L27, whose first statement releases it.
* **Release.** `release_at_l27_entry` (A2 FU1, unchanged): construction entries
  still `OPEN` (backstop) then the four final pins, each once, by handle; no
  retry, no force, guarded against a concurrent or re-entrant run.
* **Derived fact.** `live_references_released` is `True` iff no provision was
  adopted, or the adopted provision was released through that path, did not end
  `FAILED_UNEXPECTED`, and every ledger entry reads `CLOSED`. A `CLOSE_FAILED` or
  still-`OPEN` entry latches `False`; L27's removal outcome, empty registries and
  dropped references never repair it; L30's unchanged check
  (`_run_scoped_registries_empty`) then fails closed. No record key, halt code or
  lifecycle step was added.
* **`FAILED_UNEXPECTED` is not proven released.** An unexpected interruption can
  fall between a native create returning and its ledger entry (candidate §4
  F-3); an absent entry is never proof. This is the conservative reading of
  §7.8.1's "PROVEN", applied only to that one terminal state.
* **Scope of the fact.** It covers the provision's handles. The
  config/extension issuance and retained-authority handles remain proven by
  their own registries at L30, exactly as before; no executor-owned reference
  without a release record was assumed released.
* **Nothing deleted by L3R**, by pathname or by handle; L27's frozen namespace
  teardown is the only removal, after release.

---

## 5. Versioned records

v3 only (§11.1): `REFUSAL_STEPS_V3 = REFUSAL_STEPS ∪ {L3R}`,
`PRE_DISPATCH_REFUSAL_CODES_V3 = … _V2 ∪ {RUNTIME_PROVISIONING_FAILED}`,
`REFUSAL_CODES_BY_STEP_V3 = REFUSAL_CODES_BY_STEP ∪ {L3R: {RUNTIME_PROVISIONING_FAILED,
UNEXPECTED_STEP_FAILURE}}` (every inherited step's code set is the identical
object), and R3-S15 (`K == L3R ⇒ C ∈ {…} ∧ RC is False`). Only
`_require_valid_cfg1_run_payload_v3` reads the v3 objects (AST-tested). The v1/v2
objects and validators are byte-identical; the v2 validator refuses the L3R
vocabulary as a schema violation. No new key; no change to the v3 refusal or
stage-closure records.

---

## 6. Tests

### 6.1 New module — `test_cfg1_f5a_executor_integration.py`

44 tests, all passing in run 2 (section 6.4). All are Windows-only (`skipif`
otherwise: a skip is not a pass).

Covered: authorized binding through L3R and `S` dropped; cross-run,
cross-profile and cross-source provisions refused and never adopted; malformed
and contradictory port returns; an unclaimed workspace refusing before the port;
L3R refusal reaching no credential, capability or launch; unexpected port raise;
provisioning failure minting no `L`; post-pin binder failure (returns `None` /
raises) minting no `L` and still releasing the pins; an exposure above `C`
refused by the binder (injected seam); the binder's own refusals and its
no-writer AST audit (exactly two `Cfg1PiIdentity` construction sites); the L14
precondition (RT gains a child, `R\node_modules`, identity swapped, a pin
closed) with no supervisor built, and its unit rules; the barrier (section 2);
release after a later refusal; `FAILED_UNEXPECTED` latching `False`; final-pin
close failure latching `False` whether L27's removal then fails (a genuinely
leaked pin → `INDETERMINATE_LIFECYCLE`) or succeeds (L30 refuses); construction
close failure; the vacuous `True`; the non-constant AST check; v1/v2 identity
and the v3-only readers; R3-S15; the v2 validator refusing L3R; and refusal
evidence carrying no path and no foreign byte (a `SECRET` marker never reaches
`R`, the observations or the console).

**Injected seams** (named in each test): the provisioning port itself (test
doubles standing in for a hostile or failing port), `bind_run_provisioned_launch_identity`,
`observe_profile_exposures` for `C`, `_post_pin_validation`, the ledger's close,
`read_payload_file_bytes` (source redirect), and `workspace_is_claimed_by`.
They show the integration's own branches; they are not native anomalies.

### 6.2 Test seams added to support code

* `pe2c_support.install_synthetic_policy` now also installs a **test-local LDT
  row** for each approved synthetic profile (`install_synthetic_ldt_rows`). The
  synthetic payload has no `dist/config.js`, so the synthetic row's derivation
  chain is `dist/cli.js, dist/main.js, dist/core/sdk.js`. The genuine row is
  untouched and still checked against the committed inventory.
* `cfg1_doubles.build_doubled_ports` binds the genuine offline adapter
  `admit_runtime_provision_for_source`, so every doubled executor run now
  provisions a real run-private copy of the synthetic tree inside its own minted
  workspace (this is why the offline suite is slower).

### 6.3 Existing tests adapted

The first full run after wiring (section 6.4, run 1) had **13 failures**. Eleven
are one predicted class: tests that mutate the ambient source tree `S` between
L1 and L14 (or during the runtime) and expect L14 / L21A to notice. Under §11.3
the root those steps prove is the run-private copy `C`; a change to `S` after L3R
is correctly irrelevant to launch. Each was **retargeted to `C`**, keeping its
intent ("a change after the proof refuses"). The other two encode the new
mechanisms themselves (AD(i) and Barrier 2; the OC-4 helper audit and the L27
entry release). No test was deleted. One L21A row (`I_r` drift during the
runtime) was **converted**, not kept, because RPR's held pins make it
unproducible; that is stated in its row below.

| Test | Change |
|---|---|
| `test_cfg1_pe2c_proof.py` C-5: payload change, different-but-approved profile, exposure appearing, identity drift (root) | the mutation hook now receives the launch root `C`; the exposure is planted under `RT` (`C`'s nearest qualifying ancestor); the approved-variant test now proves the mutated `C` *is* the variant payload and is still refused (equality, not re-membership); a rename of `C` is **refused by the held final pins** and that refusal is recorded (`blocked == ["root"]`) — the hook's raise is itself the L14 refusal |
| `test_cfg1_pe2c_proof.py::test_c5_nothing_reads_the_pi_tree_between_the_reproof_and_launch` | the last two inspections are `C` then `node.exe`; three complete walks precede launch through the run's proof leaves (L1 over `S`, the L3R binder over `C`, L14 over `C`) |
| `test_cfg1_fu1_static_identity.py::test_p_…` (same audit, FU1 shape) | as above |
| `test_cfg1_fu1_static_identity.py::test_s_v_and_p_…` (5 params) | mutations target `C`; `cli_in_place`, `cli_replaced` (a pinned file) and `root_identical_copy` (an ancestor of the pins) are refused by the platform and recorded; `other_seam_in_place` (unpinned) is caught by the frozen re-proof's walk; `node_same_bytes` unchanged |
| `test_cfg1_fu1_static_identity.py::test_ad_i_…` | the genuine builder now refuses the genuine identity (Barrier 2): still L14 / `RUNTIME_LAUNCH_FAILED`, no runtime, and now **zero** `CreateProcess` attempts of `node.exe` (was one, refused by the OS) |
| `test_cfg1_fu1_static_identity.py::test_ad_i_and_iii_…` | its zero-argument mutate lambda would have raised `TypeError` inside the hook and **passed for the wrong reason**; it now takes the root argument and mutates `node.exe` as intended |
| `test_cfg1_pe2c_executor.py::test_c6_each_result_row` | L21A rows mutate `C` (unpinned file) / plant the exposure under `RT` / make `RT\node_modules` a file; the `I_r`-drift row became an observation that the move-aside of `C` is refused while the pins are held (`PROVEN_UNCHANGED`), because it cannot be produced during the runtime under RPR |
| `test_cfg1_f5a_executor_integration.py::test_l21a_a_root_identity_mismatch_alone_is_unproven_by_injected_observation` (FU1, new) | restores explicit coverage of the frozen "`I_r` drifted → `UNPROVEN`" branch that the converted row above no longer exercises: genuine walk and exposures, but the root's inspected file id (or classification, or observability) is injected to differ → `UNPROVEN`, with a genuine-leaves control → `PROVEN_UNCHANGED`. Nothing is renamed, converted or made a reparse point; L21A semantics are untouched |
| `test_cfg1_l16_fu2.py::test_r40_…` (FU1) | the old test drove a duck-typed `StaticIdentityShape` through the default builder and read the real supervisor's argv — that was the Barrier-2 bypass. It is now a refusal test; the R-40 requirement (argv and H2 expectations from the same frozen constants) binds the future live-enablement phase |
| `test_cfg1_pe2c_executor.py::test_c6_counterexample_11_aba_…` | mutate-then-restore applied to `C` (still the documented R-ABA residual) |
| `test_cfg1_oc4_closure_totality.py::test_x3_…` | one allowed helper relationship added: `_closure_l27_workspace → _closure_l27_release_runtime_provision` (L27's own entry action, not another step) |

The pin refusals recorded above are observations of this host under ordinary
tests, not new empirical qualification: P-R1-1 stays PARTIAL and P-R1-2/4 are
not re-measured here.

### 6.4 Executed

Host: Windows 10.0.26200, NTFS, project venv interpreter, 2026-10-12. Command
(from `experiments/pi_harness_cfg1`):

```text
python -m pytest tests -p no:cacheprovider -q
  --ignore=tests/test_cfg1_f5a_windows_handle_probes.py
  --ignore=tests/test_cfg1_f5a_r1_windows_premises.py
  --deselect experiments/pi_harness_cfg1/tests/test_cfg1_pi_conformance.py::<16 ids>
```

The 16 deselected ids are the standard installed-Pi / Node set: the eleven
`test_t3_*` tests (one of them parametrized twice, so twelve items) and
`test_the_installed_pi_payload_is_an_approved_hpp1_profile`,
`test_the_installed_get_state_shape_matches_the_frozen_derivation`,
`test_r31_the_installed_rpc_mode_echoes_the_probe_id_and_command_exactly`,
`test_the_unregistered_tool_name_derivation_still_holds_in_the_installed_loop`.
The two `--ignore`d probe modules (they create junctions and convert
directories) are **not collected** — distinct from deselection. The preserved
FU4-A2 draft is not a `test_*` module and is never collected.

| Run | Collected / selected / deselected | Passed | Failed | Skipped | Wall |
|---|---|---|---|---|---|
| run 1 (wiring, before 6.3) | 3556 / 3540 / 16 | 3523 | 13 (section 6.3) | 4 | 857.6 s |
| run 2 (final) | 3600 / 3584 / 16 | **3580** | **0** | 4 | 853.0 s |

The 4 skips are the four pre-existing `test_cfg1_impl_fu1_findings.py` "not an
adversarial case for this helper" parametrizations (unchanged). Run 1's selected
set is exactly the base commit's (the new module did not exist yet and no
parametrization changed), so the base selection is 3540 and this phase adds 44
(the new module). Consistency with the previous accepted candidate: the A2
candidate at `177ddc6` recorded 3518 passed + 4 skipped under the same
selection, and FU1 added the remaining base tests. The FU1 report's "3,395
passed" for its second broad run cannot be reconciled with that from the
available records (likely a different selection) and is noted, not explained.

The full run is now about 14 minutes (it was about 6): every doubled executor
run provisions a real copy and walks it independently at L3R, L14 and L21A.

---

## 7. The earlier 341-failure anomaly

The FU1 report recorded a first broad run with 341 failures beginning with a
workspace-root rename `PermissionError`, and a second broad run fully green.
This phase ran the full offline selection twice (section 6.4). **Neither run
produced a `PermissionError`, a rename failure or any cascading failure**: run 1's
13 failures were the deterministic classes of section 6.3 (each reproduced on
re-run and fixed there), and run 2 was green. The historical failure
therefore **did not recur and remains UNEXPLAINED, not resolved**. One plausible
trigger is recorded for whoever sees it next, but it is a hypothesis, not a
finding: `test_admission_followed_by_loss_of_authority_refuses_at_consumption`
renames a freshly minted run root (`root.rename(aside)`), and on Windows that
rename fails with `PermissionError` while *any* handle is open beneath the root
(an indexer or on-access scanner touching the new Git fixture would suffice).
Why one such failure would cascade into 341 is not explained by that alone.
No broad investigation was started: it did not affect this integration's
correctness or evidence.

---

## 8. Adversarial review

### 8.1 Before coding (design-level)

| Question | Answer in the code |
|---|---|
| Can a supported caller bypass the barrier? | No supported entry point provisions (Barrier 1) or hands a genuine identity to a real supervisor (Barrier 2); section 2. |
| Can workspace, inventory, profile or launch identities from different runs mix? | Every pairing is checked at consumption (section 3); a foreign provision is never adopted. |
| Can an unproven provision become a launch identity? | `package_root_identity` exists only after post-pin validation; the binder re-observes `C` itself; `record_launch_identity` requires `PROVEN`; L14 requires `BOUND` and identity-equality. |
| Can a failed L3R reach launch or produce success evidence? | L3R refusal raises into closure; R3-S15 forbids `RC` at L3R; the derived fact is computed from the ledger. |
| Can a refusal before L27 strand final pins? | Adoption precedes the first create; L27's first statement releases, independent of W and of earlier closure steps. |
| Repeated/concurrent release? | Guarded, exactly once (A2 FU1); the executor calls it once; a refused release leaves entries `OPEN` → `False`. |
| v1/v2 changed? | No (section 5, tested by identity). |
| Cleanup outside the owned namespace? | L3R deletes nothing; never-adopted provisions are never released by this run; L27 removal is the frozen no-follow teardown. |
| Raw diagnostics or credentials in records? | Only closed codes; one constant console code; tested with a sentinel. |

### 8.2 After coding — findings on the actual implementation

| # | Finding on the actual code | Disposition |
|---|---|---|
| F-INT-1 | **Design defect avoided before coding.** A port that admitted *and ran* the provision would hand the executor nothing to release if it refused after the final pins were acquired (the A2 run keeps pins held across a post-pin refusal, by design) — stranded pins. | The port returns an **ADMITTED, never-run** provision; the executor adopts it (write-ahead) and runs it itself. Regression: `test_a_copy_validation_failure_after_the_final_pins_mints_no_l_and_releases_them`. |
| F-INT-2 | **Real, fixed during self-review.** Factoring post-pin validation's topology checks into `_reprove_topology` first changed post-pin's `TOPOLOGY_NOT_PLAIN` refusal reason to `POST_PIN_VALIDATION_FAILED` — a silent change to accepted A2 behaviour. | Reverted: the plain-chain check keeps its own reason; the A2 candidate suite is unchanged and green. |
| F-INT-3 | **Real, fixed.** After §11.3 the 13 source-mutation tests (section 6.3) did not merely fail — several would have been *vacuous* once "fixed" naively, and `test_ad_i_and_iii_…` would have passed for the wrong reason (a `TypeError` in the hook is itself an L14 refusal). | Retargeted to `C`; the mechanism that stops each mutation is asserted (`blocked == …`). |
| F-INT-4 | **Residual made truthful.** Candidate F-3: an unexpected interruption between a native create and its ledger entry leaves an untracked handle that no ledger can show. | `provision_live_references_proven_released` is `False` for a `FAILED_UNEXPECTED` provision. Regression: `test_an_unexpected_failure_inside_the_provision_latches_unproven_release`. |
| F-INT-5 | A port that runs its *own* provision and returns it: the executor refuses to adopt it (never-run check) and so never releases it; its held pins then block L27's removal. | Accepted as truthful: the run reports `INDETERMINATE_LIFECYCLE`; releasing an object this run did not adopt would be cleanup of a resource it does not own. Regression: `…[already_run]`. |
| F-INT-6 | Concurrency: a port keeping a reference could release or re-record the provision concurrently. | Every mutating entry (`run`, `release`, `record_launch_identity`) and the L14 re-proof take the provision's non-blocking guard; a second record is refused (L3R fails closed); a foreign early release makes L14 refuse (pins not held) and the derived fact reads the ledger truthfully. No new mechanism was needed. |
| F-INT-7 | Barrier coverage: a caller-authored process-launching supervisor passed as `build_supervisor`. | Not a supported entry point; stated as a residual in section 2 rather than "hardened" speculatively. |
| F-INT-8 | Closure ordering: an implementation defect raising out of L21–L26, or a `BaseException` (e.g. `KeyboardInterrupt`) in the dispatch phase, would skip L27 and its release. | Pre-existing and identical for every CFG1 resource (OC-4 I-8 forbids a laundering `try` around closure); not changed here. Such a run produces no outcome at all, so no false `True` is possible. |

| F-INT-9 (FU1, F5A-OI-FU1-1) | **Real, found by independent review.** Barrier 2 was a `type(identity) is Cfg1PiIdentity` guard in front of a real `PiRpcSupervisor(...)`; `build_pi_argv` does not enforce the type, so a duck-typed or malformed identity reached the real constructor through the default port. A pre-existing R-40 test exercised exactly that path. | The builder is one unconditional `raise`; the construction code is removed from the module; the R-40 test became a refusal test; regressions above. |

No other bypass within scope was found.

---

## 9. Remaining A2 qualification and E5 blockers (unchanged in kind)

* **A2-3** — one validated run of the preserved FU4-A2 draft with no teardown
  error; A2-2's corrected predicate executed; a racing-conversion measurement.
  None was attempted here.
* **Candidate-on-target-platform qualification** of this module's construction
  under the A2-3/A2-6 scenarios; **A2-8 / P-R1-4** on the approved inventory
  shape (360-file fan-out, 80 child pins, depth 11, peak ≤ 462); **P-R1-1**
  stays PARTIAL.
* **R-ALIAS** unresolved (L9 dependency note unchanged).
* **Independent acceptance** of the A2 §1 correction, of this integration, and
  of D-F5A-9/D-F5A-10.
* **E5 conditions** of amendment §17 untouched — notably condition 9 (the ambient
  installation is no longer the approved payload, §1.2) and condition 8 (a
  separately reviewed live authorization). E5, E6 and PE-6 remain unauthorized.
* Lifting either barrier of section 2 is itself a separately authorized change.

## 10. Smallest next step

Run the A2-3 qualification step that is already specified (the preserved FU4-A2
draft, unmodified, in a session where it is permitted). If it passes cleanly,
the next step is one target-platform qualification run of **this** module's
construction under the A2-3/A2-6 scenarios and the P-R1-4 fan-out shape. Only
then does it make sense to author the live authorization that would replace the
two barriers with an operator-supervised E5 path bound to an approved byte
source.
