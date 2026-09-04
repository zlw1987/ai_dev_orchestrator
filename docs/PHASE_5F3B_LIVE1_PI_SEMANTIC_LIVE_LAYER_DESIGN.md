# Phase 5F3B-LIVE1-DESIGN-FU4A — Pi semantic live adapter + sweep runner — EXACT DESIGN

> **Revision `5F3B-LIVE1-DESIGN-FU4A` — final authority + canonical-consistency
> closure.** This document supersedes `5F3B-LIVE1-DESIGN` and its `-FU1` /
> `-FU2` / `-FU3` / `-FU4` revisions in place. FU1 closed four review blockers;
> FU2 five closure items; FU3 three blockers plus a provenance clarification;
> FU4 three cross-layer items; **FU4A closes five authority and
> canonical-consistency items** (§0.1) — two of which withdraw FU4's own
> overclaims.
>
> **This revision reopened no Pi-seam analysis.** The 0.84.4 seam, prompt
> acknowledgement ordering, `agent_settled` completion, the dispatch/turn split
> and stream ownership are untouched; §§2.1–2.5 and §§3–8 were not edited.

> **DESIGN / SOURCE INSPECTION ONLY. NOTHING WAS IMPLEMENTED IN THIS TURN.**
>
> No runtime module, no test, and no frozen AR1 / AR2 / AR2-O1 / I1 / I2 / I2B /
> PRE1 file was modified. **No semantic prompt was sent (0), no model was
> called (0), no Pi or Node process was launched (0), no broker or named pipe
> was opened (0), no credential was read (0), no socket was opened and B300 was
> not contacted (0).** Q1 and Q2 were not run. Nothing was committed, pushed,
> branched, or opened as a PR. `CLAUDE.md` was not modified, and no real
> workspace was touched.
>
> **Standing status is unchanged by this document.** No model qualification has
> occurred. No candidate implementer PASS/FAIL exists. Candidate A and Candidate
> B are Category-B **compatibility** qualified/frozen only.
> **5F3B-Q1: NO-GO. 5F3B-Q2: NO-GO. Real-workspace authority: NO-GO.**

| | |
|---|---|
| Kind | Phase design (implementation-readiness), source-derived |
| Phase | `5F3B-LIVE1-DESIGN-FU4A` (supersedes `5F3B-LIVE1-DESIGN`, `-FU1`…`-FU4`) |
| Milestone | M2.5 |
| Canonical sequencing | [`AIDO_RUNTIME_HARNESS_ROADMAP.md`](AIDO_RUNTIME_HARNESS_ROADMAP.md) §4.5 |
| Planning notes | [`PHASE_5F3B_LIVE1_PI_SEMANTIC_LIVE_LAYER_PLAN.md`](PHASE_5F3B_LIVE1_PI_SEMANTIC_LIVE_LAYER_PLAN.md) |
| Live activity | **None** |
| Authorizes | **Nothing** |
| Requires before I1 | `5F3B-LIVE1-C1`, `5F3B-LIVE1-C2`, `5F3B-LIVE1-C4`, `5F3B-LIVE1-C3` (§18.2) |
| Policy revision required | **Yes** — R-2 buckets **frozen** (§9.4.5) and **AIDO-derived** (§9.4.8), R-3 `NOT_EVALUABLE` with a symmetric rule (§10.6.2a), and a revision identifier at the ranking boundary (§10A.3); all before Q1 (§18.3) |
| Record schema change | **Yes, and required before Q1** — `pi-implementer-qualification.v2`, `-attempt.v2` **and `-refusal.v2`** carry `qualification_policy_revision` (§10A.2b), owned by `5F3B-LIVE1-C4` |
| C1 production modules | **three**: `i2b_workspace`, `i2b_live_adapters`, `semantic_workspace` (§2.6.6) |
| Reported open gaps | **none** — FU3's one open gap is closed by C4 (§10A.4) |
| **VERDICT** | **`DESIGN READY FOR C1`** — see §18.1 |

---

## 0. Executive summary

### 0.1 FU4A — authority and canonical consistency

> **FU4A scope.** Not another Pi-seam review. Five items: one authority
> tightening, one scope correction, one provenance hole, one **withdrawn
> overclaim**, and a consistency pass over normative text that earlier
> revisions left contradicting themselves. Every accepted item — the Pi 0.84.4
> seam analysis, acknowledgement ordering, `agent_settled` completion, the
> dispatch/turn split, stream ownership, C2's pair projection and six dynamic
> reason sources, the R-2 thresholds, R-3 `NOT_EVALUABLE` symmetry,
> final-report `UNAVAILABLE`, no sweep-level artifact, no
> retry/continuation/fallback, and real-workspace NO-GO — is preserved
> unchanged.

| # | Item | Resolution |
|---|---|---|
| **1** | Make the C1 module boundary consistent **everywhere**, and tighten P12a | **Done.** FU4 established C1-P12a but left §2.6.5a, §2.6.6, §18.2 and §18.5 still saying `semantic_workspace` was untouched. The exact C1 production boundary is now stated identically in all of them: **`i2b_workspace` + `i2b_live_adapters` + `semantic_workspace`**, with `semantic_controller` and `semantic_sweep` closed. **P12a is tightened to EXACT STRING EQUALITY** — `supplied_git_executable == trusted_git`, never `realpath(supplied) == realpath(trusted)` or any alias test — because the controller keeps using its *original spelling* afterwards, so only exact equality makes that unchanged local **be** `trusted_git` and thereby bind the later child-PATH and `REPOSITORY_OBSERVATION` consumers without reopening the controller |
| **2** | `QUALIFICATION_POLICY_REVISION` must identify the **whole** policy | **Corrected.** FU4's C3-PR-4 scoped it to "R-1..R-4 definitions", which is too narrow: roadmap §2.2 defines a PASS under the frozen corpus, the hard bar H-1..H-14, the outcome taxonomy, the one-shot prompt policy and the fairness rules **plus** ranking. The identifier now covers the complete implementer ROLE_CAPABILITY policy and must change whenever meaning, eligibility, classification, ranking or comparability changes — and explicitly **not** for refactors, non-policy tests, docs or renames. It stays one stable declared literal; automatic policy hashing is refused, because a computed identifier changes on every refactor and stops meaning "the policy changed" |
| **3** | Close the **safety-refusal** policy-provenance hole | **Confirmed at source and closed.** `emit_evidence_or_refuse` writes `build_refusal_record(...)` **instead of** the primary/attempt record when the scrub rejects a payload — so in that fallback the refusal artifact is the **only** durable artifact that invoked one-shot attempt will ever have, and FU4 left it non-self-describing. C4 now also binds the revision there as fixed metadata, bumping `REFUSAL_RECORD_VERSION` → `pi-implementer-qualification-refusal.v2`, and **reopens `qualification.safety`** for that field and version only. Nothing else enters the refusal record. **Lineage needs no field**: source shows it imports the `RECORD_VERSION` *symbol*, so it follows the bump automatically, and it binds records by digest |
| **4** | **WITHDRAWN:** `PrimarySweepResult` is not an issued sweep authority | **FU4 overclaimed; corrected.** Each `SemanticTaskAttemptResult` is genuinely issuance-backed and its `scope_result` cannot be swapped — that part stands. But `PrimarySweepResult` is a **public, constructible** frozen dataclass whose `__post_init__` consumes **no** token: it proves consistency and immutability, not issuance. A caller holding three genuine task results can compose a new, internally consistent aggregate — e.g. mixing tasks from two sweeps of one candidate. So "the whole graph is already unforgeable" and "C3 has complete in-process ranking authority" are withdrawn. **`semantic_sweep` is not reopened and no sweep token is invented.** Instead: **C3 owns policy mechanics only** (the R-2 resolver, malformed-input checks, R-3 symmetry, policy-revision refusal, comparison mechanics), and **M4 owns all authoritative ranking-input derivation and selection** from durable artifacts. This also disposes of the adjacent fact that `RankingInput` still accepts caller-authored `r1_bucket` and the R-4 booleans: removing `r2_bucket` is right, but it does not make the remaining tiers authoritative, and this design no longer implies it does |
| **5** | Canonical-consistency pass | **Done.** §2.6.5a (three modules), §2.6.6 ("exactly three"), §9.4.6 (R-2 needs no field — *scoped*, no longer a blanket "no schema change required"), §12.7 (sweep artifact still refused, but no longer argued from a now-false "no schema change at all" premise — C4's per-result bump is distinguished explicitly), §14 (per-phase reopening instead of a blanket "untouched"), §18.1 (historical provenance rows marked superseded), §18.2 (C1 row includes `semantic_workspace`; C4 row includes `safety` + `-refusal.v2`; ordering names **all four** phases), §18.3, §18.4 (C1/C2/C4/C3), §18.5 (stale refusals that would forbid C1/C4 corrected; every still-true refusal preserved). FU1–FU4 text that is explicitly labelled historical or withdrawn is preserved as history, not rewritten |

### 0.2 FU4 — three cross-layer items

> **FU4 scope.** Independent review held FU3 and raised three remaining items.
> All three are corrections to claims earlier revisions made too strongly, and
> all three are closed here. Every accepted item — the Pi 0.84.4 seam analysis,
> acknowledgement ordering, `agent_settled` completion, the dispatch/turn split,
> C2's pair-based projection and its dynamic-reason inventory, the R-2
> thresholds, R-3 `NOT_EVALUABLE` symmetry, final-report `UNAVAILABLE`, no sweep
> artifact, no retry/continuation/fallback, and real-workspace NO-GO — is
> preserved unchanged.

| # | Item | Resolution |
|---|---|---|
| **1** | Git executable authority must cover **fixture population** too | **Confirmed; FU3 was incomplete.** Source shows an earlier execution path: `run_primary_sweep(git_executable=<caller string>)` → `populate_semantic_task_workspace` → `semantic_workspace._git` → `subprocess.run([git_executable, …])`, at **gate 2**, long before `create_broker`. `semantic_workspace` performs no resolver check today, so FU3's three claims were **not** mechanically true and are withdrawn. §2.6.5b now gives the **complete four-consumer graph** — and finds two more: `build_child_environment` puts `dirname(git_executable)` on the **untrusted Pi child's PATH**, and `REPOSITORY_OBSERVATION` runs the authoritative post-prompt Git with the same string. **New C1-P12a:** `populate_semantic_task_workspace` keeps its frozen string shape but treats it as a *provenance claim*, independently resolving and requiring canonical exact equality immediately after `verify_run_workspace`, before the first subprocess and before any file write. Because `git_executable` is a local that source confirms is **never reassigned**, that single earliest checkpoint binds all four consumers — so `semantic_controller` and `semantic_sweep` are **not** reopened. Regressions T7–T14 |
| **2** | The policy revision must bind **durably, with the result** | **FU3's outcome B is withdrawn.** Its "the per-task artifacts are policy-neutral" argument is false in the general sense: `pi-implementer-qualification.v1` already records `run_validity`, `scoring_eligible`, `autonomous_classification` and `diagnostic_subclassification` — all **policy verdicts** — so a one-shot Q1/Q2 result may not depend on a future M4 artifact to say which policy produced them. **A record schema revision is required, and it is cheap:** one header field on each of the two artifact lineages, with `RECORD_VERSION` → `.v2` and `ATTEMPT_RECORD_VERSION` → `.v2`. `record_version` is **not** overloaded with policy meaning. Source fact: **no `pi-implementer-qualification.v1` or `-attempt.v1` artifact has ever been emitted**, so the bump has zero archival cost. Owned by a new, narrow **`5F3B-LIVE1-C4`**, landing **before C3** so the constant has one declaration site. M4's decision artifact remains required and **additive** (§10A.4) |
| **3** | R-2 primitive inputs need **provenance authority** | **Confirmed.** Deriving deterministically from caller-authored counts only moves the fabrication point. §9.4.8 now splits **policy math** (C3's one pure resolver) from **evidence authority**, and finds the in-process authority already exists and is stronger than anything C3 would add: `SemanticTaskAttemptResult` is one-shot and valid-by-construction — its own error text says the issuance *"can back at most ONE construction, ever, including a `dataclasses.replace()` that touches only an unrelated field"* — so its `scope_result` cannot be swapped, and `PrimarySweepResult` already binds every entry by exact type, candidate, model and frozen task prefix. **C3 owns policy derivation; M4 owns durable-artifact → ranking-input authority.** No generic evidence framework, no path reading in C3, no candidate-level artifact in C3 |

### 0.3 FU3 — three blockers and one provenance clarification

> **FU3 scope.** Independent review held FU2 and raised three blockers plus one
> provenance clarification. Each blocker is a claim an earlier revision made
> more strongly than source supports; all three are corrected rather than
> defended. Every accepted item — the Pi 0.84.4 seam analysis, acknowledgement
> ordering, `agent_settled` completion, the single stream owner, the two-phase
> split, issuance at `create_broker`, lazy post-gate identity activation,
> `i2b_workspace` Option A, the frozen R-2 thresholds, the recurrence proof,
> R-3 `NOT_EVALUABLE` and its symmetric handling, final-report `UNAVAILABLE`,
> no sweep artifact, no retry/continuation/fallback, and real-workspace NO-GO —
> is preserved unchanged.

| # | Item | Resolution |
|---|---|---|
| **1** | C1 must bind the **Git executable** as authority | **→ EXTENDED BY FU4 ITEM 1** (FU3 covered only the manifest observation; the fixture-population path was missed). **Confirmed at source and closed.** `build_git_argv` checks only *non-empty and absolute* immediately before `subprocess`, and `run_fixed_git_operation` only *expects* the caller to pass the resolver's result — so a semantic issuance seam accepting a Git path from anywhere would be a program-selection surface with nothing enforcing "the repository under test must not supply the program that inspects it". **New C1-P12 + §2.6.5b:** the observation resolves its own executable internally, via the accepted `resolve_git_executable` bound to the **verified workspace root**; a failure or mismatch refuses **before any launch**. **`LiveSemanticAdapters`'s `git_executable` parameter is removed entirely** — the surface is deleted, not defended. Regressions T7–T12 |
| **2** | C2's input model is **incomplete** | **FU2 was wrong; corrected.** `occurrence_count_<N>` is **not** the only dynamic reason: §9.4.3.1 enumerates **six** sites, and two of them — `path_policy:{exc}` (may embed a **path**) and `WireProtocolError` `str(exc)` (**candidate-authored** wire text) — would have put candidate-influenced free text into retained `refusal_categories`. That is an evidence-safety defect, not a taxonomy one. The projection now takes the **pair** `(error_code, internal_reason)`, keeping the frozen nine-member `CLOSED_ERROR_SET` as a first-class input — `unauthorized` → `unauthorized`, `protocol_error` → `protocol_terminal` from the code alone, `too_large` / `budget_exhausted` split on the pair. Every dynamic family reduces to `unrecognized_broker_reason`. **C2-P6's drift guard now covers dynamic construction sites as well as literals**, so a newly-added f-string/`str(exc)` reason breaks the suite loudly. AR2 is read, never edited |
| **3** | C3 must **derive** R-2, not accept a bucket | **→ EXTENDED BY FU4 ITEM 3** (deriving from caller-authored primitives only moved the fabrication point). **Confirmed and closed.** `RankingInput.r2_bucket` is caller-authored, `RankingInput` has no `__post_init__`, and `build_profile` copies it verbatim — so FU2's frozen thresholds were **documentation only**: a caller could submit `CLEAN` against retained evidence saying `N ≥ 3`. §9.4.8 makes R-2 an **AIDO-owned derivation** from primitive per-task evidence (C3-R2-1…5), with a nine-case refusal table including the internal-impossibility check `n_t < \|S_t\|` that §9.4.6's proof depends on. Same lineage as `PrimarySweepResult`'s own FU2A correction |
| **P** | Where the **qualification-policy revision** durably binds | **→ WITHDRAWN AND REPLACED BY FU4 ITEM 2.** FU3's outcome B deferred the durable binding to M4; §10A.2 withdraws that. Recorded for history: **Gap reported, not hidden — outcome B.** §10A.1 shows from source that *no* current surface can carry it: `record_header` has none, and `record_version` is a **schema** version that must not be overloaded with a **policy** fact; `CandidateRankingProfile` and `PrimarySweepResult` are in-memory only and no candidate-level decision artifact exists. §10A.2 records why the per-task artifacts staying **policy-neutral** is correct (they carry raw observations, never buckets) and states a **blocking precondition**: no candidate may be declared selected or qualified until the future M4 decision artifact durably persists `qualification_policy_revision`, harness/version, model, backend and role. §10A.3 gives C3 its own identifier and makes `compare_profiles` **refuse** across revisions. **No record schema is widened in this turn** |

### 0.4 FU2 — the five closure items

> **FU2 scope.** Independent review held FU1 and raised **five** closure items,
> two of which are corrections to FU1's own claims rather than new ground. All
> five are closed here. Every accepted direction — the Pi 0.84.4 seam analysis,
> the single stream owner, the two-phase split, `agent_settled` completion,
> final-report `UNAVAILABLE`, C2's qualification-owned projection, the R-2
> narrowing direction, R-3 `NOT_EVALUABLE`, no retained sweep artifact, lazy
> per-task identity activation, composition over subclassing, no
> retry/continuation/fallback, and real-workspace NO-GO — is preserved
> unchanged.

| # | Closure item | Resolution |
|---|---|---|
| **1** | C1 issuance **cannot** occur at `read_connection` activation | **FU1 was wrong; corrected.** `read_connection` has the frozen zero-argument shape and receives neither `run_id` nor the workspace, so a four-way-bound capability is not constructible there. §2.6.4a now states **two separate authority events**: identity activation at `read_connection`, capability issuance/consumption at `create_broker(BrokerCreationRequest)` — the first adapter call carrying both. C1-P3, §12.2A.1/.3 and §12.3 are rewritten to match. `read_connection`, `semantic_controller` and `BrokerCreationRequest` are **not** widened, and no ambient state carries the run or workspace forward |
| **2** | `i2b_workspace`'s process-free contract vs. a Git-observed manifest | **Resolved as Option A, explicitly.** §2.6.5a records that the two FU1 claims were incompatible; that the existing purity test is **transitive-blind** and would have passed *silently*; and that C1 must narrow the module docstring's invariant, name the one allowed `ar2.observation` import, and **amend and strengthen** `test_i2b_controller.py`'s purity test. Six regression obligations (T1–T6) prove Category-B issues **zero** Git operations and keeps a byte-identical inert domain. Option B (sealed two-module token) is recorded as admissible but larger |
| **3** | R-3 `NOT_EVALUABLE` must be **policy-symmetric** | **FU1's "skip if either side is `None`" is withdrawn.** §10.6.2a fixes the four-case invariant: `None`/`None` → skip; `bucket`/`bucket` → compare; **exactly one side `None` → refuse/raise**, never a silent skip. R-3's absence is a *global policy* fact, unlike R-4's *per-candidate* optionality. Both profiles are `None` **by construction** via an explicit `R3_EVALUABLE = False`, which also **refuses** a supplied bucket rather than ignoring it. No member is added to `ReportAccuracyBucket` |
| **4** | Freeze the R-2 threshold **now** | **Frozen.** `CLEAN` iff `N == 0`; `MINOR_FRICTION` iff `N ∈ {1,2}` and no projected soft code recurs; `REPEATED_FRICTION` iff a code recurs or `N ≥ 3`; `N` and recurrence are **candidate-level**, across all three tasks. Declared as a **new pre-run policy definition**, not a recovered "self-correction" observation; §9.4.5 records that no stronger predeclared basis exists in source and why this does not violate §11.3's no-numbers rule |
| **5** | Two false live-safety statements | **Corrected.** §12.2: steps 1–4 launch no process, **step 5 enters the live sweep**, and inside it a task's identity probe begins only after that task's own Category-A gates pass. §17: "LIVE1 reads no credential" is replaced by the truthful runtime invariant — no second credential reader, no parsing/logging/retention, exactly one read delegated to the frozen `read_connection` after the gates — kept separate from the still-true statement that **this design turn** performed zero credential reads |

**New in FU2 beyond the five items:** §9.4.6 proves, from the frozen record
schema, that the revised R-2 buckets are computable from **retained evidence
alone** — `N` from `soft_refusal_count`, and recurrence from `N > |U|` where `U`
is the union of distinct projected soft codes in the retained, deduplicated
`refusal_categories`. No broker event log, no re-run, **no new artifact or
schema**.

### 0.5 FU1 — the four blockers (carried forward, unchanged unless noted)

> **FU1 scope.** Independent review accepted the Pi seam analysis of §§2.1–2.5
> and §§3–8 and raised **four** design blockers. FU1 closed all four; FU2
> corrects blocker 1's issuance *timing* only (item 1 above), and leaves the
> other three resolutions intact.

| Blocker | Was | Now |
|---|---|---|
| **1 — capability authority seam** | `FROZEN_CONTRACT_CONFLICT`; the illustrative fix let a caller author the manifest, protected patterns and witness paths that a hidden root authority would then bless | §2.6 replaced. A **qualification-owned, task-bound, one-shot capability issuance** whose every authority fact is derived — from the existing `i2b_workspace` mint record, from an AIDO Git observation of *this* repository, and from the frozen `QualificationTask` contract. No caller-supplied domain, no caller-supplied factory, no authority escape, no replay |
| **2 — per-task Category-A / identity ordering** | §12.3 resolved Pi identity inside `build_adapters(task)`, i.e. **before** the task's own non-secret gates ran | §12.2A added and §12.3/§12.4 replaced. `build_adapters(task)` is now **inert** — zero subprocess, zero credential, zero resource. The one `--version` probe is triggered by the controller's own first post-gate adapter call, `read_connection` |
| **3A — R-2 refusal vocabulary + sequence** | recorded as a non-blocking "finding for review" | §9.3/§9.4 replaced. Treated as a **pre-Q1 frozen-contract gap**. One deterministic qualification-owned projection boundary is specified, and the R-2 *sequence* evidence is proved **unobservable** at source, requiring a narrow pre-run policy revision |
| **3B — R-3 report reliability** | §10's `UNAVAILABLE` conclusion accepted, but `RankingInput.r3_bucket` is mandatory and has no not-evaluable state | §10.6 added. Treated as a **pre-Q1 frozen-contract gap**; the minimum fair correction is a declared **R-3 `NOT_EVALUABLE`** policy revision applied identically to both candidates, before any candidate semantic prompt |
| **4 — new sweep artifact** | §12.7 proposed a retained sweep-summary JSON artifact, contradicting the same document's own refusal list | §12.7 replaced: **no new artifact, no new record schema, no new record version.** Existing immutable per-task artifacts + in-memory `PrimarySweepResult` + a bounded console summary only |

**What did not change across any revision.** Every §§2.1–2.5 Pi seam observation, the
`PiRpcSupervisor` single-owner model (§3–4), the frozen timeout reuse (§5), the
four port signatures (§6), the phase-1 dispatch algorithm (§7), the phase-2 turn
observation (§8), the composition-not-subclass decision (§11.1–§11.2), cleanup
ownership (§13) and A/B fairness (§15) all stand exactly as accepted.

Provenance headline, unchanged: **the installed Pi is `0.84.4`, exactly the
version whose seam `5F3B-Q1-PRE1-DESIGN-FU1` froze.** Every PRE1 seam assumption
was re-verified against that source and every one of them held (§2.1–§2.5).

**Verdict: `DESIGN READY FOR C1`** — see §18.1. **Four** correction phases and
one qualification-policy revision must land before `5F3B-LIVE1-I1`; §18.2 names
their exact production-module boundaries, and C4 additionally carries a record
schema bump that must land **before Q1**. FU3's one reported gap is **closed**
by C4. LIVE1-I1, Q1, Q2 and real-workspace authority all remain **NO-GO**.

---

## 1. Exact source and provenance inspected

### 1.1 Installed Pi runtime (read-only; never executed in this turn)

| Fact | Value | How established |
|---|---|---|
| Package | `@earendil-works/pi-coding-agent` | `package.json` `name` |
| **Version** | **`0.84.4`** | `package.json` `version`, read as a file |
| Nested core | `@earendil-works/pi-agent-core` `0.84.4` | its own `package.json` |
| Location | the npm global `node_modules` beside the `pi` shim that `ar2.launch._resolve_pi_package_root` itself resolves | path inspection only |

**Provenance verdict: MATCH.** `5F3B-Q1-PRE1-DESIGN-FU1` §1.1 recorded its seam
analysis against `0.84.4`; the installed runtime reports `0.84.4`. There is no
version-drift finding to report, and no "close enough" judgement was made or
needed. Version remains **provenance, never authorization** (frozen
`o1.pi_compat` policy, reproduced in `qualification.i2b_live_adapters.resolve_pi_identity`),
and this design does not reintroduce any version comparison.

Files read:

| # | File | What it established here |
|---|---|---|
| 1 | `dist/modes/rpc/rpc-types.d.ts` | the complete `RpcCommand` / `RpcResponse` unions; the exact `prompt` success arm and the generic `success:false` arm |
| 2 | `dist/modes/rpc/rpc-mode.js` | `handleCommand`'s `prompt` case; `success`/`error`/`output` helpers; `handleInputLine`'s parse-failure path; the `session.subscribe(... output(toJsonEvent(event)))` forwarding; the `default:` unknown-command arm; the `catch (commandError)` arm |
| 3 | `dist/modes/rpc/jsonl.js` | LF-only framing, single trailing `\r` strip, end-of-stream flush of a trailing partial line |
| 4 | `dist/modes/json-event.js` | `toJsonEvent` — every session event is forwarded verbatim except `message_update` |
| 5 | `dist/core/agent-session.js` | all five `preflightResult` call sites; `_runAgentPrompt`; the single `_emitAgentSettled` call site; `_expandSkillCommand`; `willRetry` decoration of `agent_end` |
| 6 | `dist/core/agent-session.d.ts` | the `AgentSessionEvent` union — `agent_end{messages, willRetry}` and `agent_settled` |
| 7 | `dist/core/prompt-templates.js` | `expandPromptTemplate` — identity for text not starting with `/` |
| 8 | `node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js` | the two `emit({type:"agent_start"})` sites and the four `agent_end` sites |
| 9 | `node_modules/@earendil-works/pi-agent-core/dist/agent.js` | `agent_end` semantics ("only means no further loop events will be emitted") |

### 1.2 AIDO-side source inspected (read-only, unmodified)

**Frozen AR2 / AR2-O1 runtime and broker:**
`experiments/pi_external_runtime_ar2/ar2/supervisor.py`, `ar2/protocol.py`,
`ar2/launch.py`, `ar2/broker.py`, `ar2/capability.py`, `ar2/candidate.py`,
`ar2/operations.py`, `ar2/observation.py`, `ar2/pi_config.py`, `ar2/fixtures.py`;
`experiments/pi_external_runtime_ar2_o1/o1/pi_compat.py`.

**Frozen qualification package**
(`experiments/pi_implementer_qualification/qualification/`):
`semantic_controller.py`, `semantic_session.py`, `semantic_sweep.py`,
`semantic_workspace.py`, `semantic_attempt.py`, `i2b_live_adapters.py`,
`i2b_controller.py`, `i2b_session.py`, `i2b_workspace.py`, `corpus.py`,
`fixtures.py`, `records.py`, `report_accuracy.py`, `safety.py`, `scope.py`,
`validity.py`, `outcomes.py`, `hard_bar.py`, `i2_route.py`, `i2_cleanup.py`,
`i2_pi_config.py`, `i2_environment.py`, `i2_credentials.py`,
`i2_secret_context.py`, `i2_b300_route_observation.py`;
plus `run_i2b_live.py` and `tests/test_i2b_live_adapters.py`.

**Design authority:** `docs/AIDO_RUNTIME_HARNESS_ROADMAP.md` §4.5,
`docs/PHASE_5F3B_LIVE1_PI_SEMANTIC_LIVE_LAYER_PLAN.md`,
`docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md` (§1–§10).

---

## 2. Actual Pi semantic seam observations

### 2.1 The dispatch command and its acknowledgement — CONFIRMED

`RpcCommand`'s `prompt` member is `{id?: string; type: "prompt"; message: string;
images?; streamingBehavior?}`. `RpcResponse` declares the success arm
`{id?; type:"response"; command:"prompt"; success:true}` and the shared failure
arm `{id?; type:"response"; command:string; success:false; error:string}`.

`rpc-mode.js`'s `prompt` case returns `undefined` from `handleCommand` and
attaches the acknowledgement to `preflightResult`, exactly as PRE1 §1.5
recorded — verbatim in `0.84.4`. `AgentSession.prompt` calls `preflightResult`
exactly once at one of five sites: four `true` (extension slash-command;
extension `input` handler `handled`; queued while streaming; **the real path**,
immediately before `await this._runAgentPrompt(messages)`) and one `false` (the
`catch` around all of the above, before rethrow).

**Ordering, re-verified:** parse → `handleCommand` → `session.prompt` →
preflight decision → **acknowledgement** → (real path only) `_runAgentPrompt` →
`agent.prompt` → `runAgentLoop` → `agent_start` → `turn_start` →
`message_start`/`message_end` → `runLoop` → first provider inference →
… → `agent_end` (repeatable, `willRetry`) → `finally: _emitAgentSettled` →
`agent_settled`.

The acknowledgement is therefore strictly earlier than agent start and strictly
earlier than any provider inference. **PRE1's two-phase architecture is
faithful.**

### 2.2 Turn completion — CONFIRMED

`_emitAgentSettled` has exactly **one** call site: `_runAgentPrompt`'s `finally`
(`agent-session.js`). `agent_start` is emitted at the top of **both**
`runAgentLoop` and `runAgentLoopContinue`, so it is not one-per-prompt.
`agent_end` is emitted at four sites in `agent-loop.js` plus one in `agent.js`,
and `AgentSession._handleAgentEvent` decorates it with
`willRetry: this._willRetryAfterAgentEnd(event)`. `agent.js`'s own comment is
explicit: *"`agent_end` only means no further loop events will be emitted."*

**`agent_settled` is completion; `agent_end` is not.** Confirmed at source.

### 2.3 The parse-failure response — CONFIRMED, and it carries no id

`handleInputLine`'s `catch (parseError)` emits
`error(undefined, "parse", …)`, i.e. `{id: undefined, type:"response",
command:"parse", success:false, error:…}` — and `JSON.stringify` drops the
`undefined` key, so the record reaches AIDO **with no `id` at all**. It is
therefore uncorrelatable by RPC id, exactly as PRE1 §2.5 states.

Two adjacent arms were also checked and are *not* id-less: `handleCommand`'s
`default:` arm returns `error(id, unknownCommand.type, …)` (so a Pi that did not
know `"prompt"` would return a **correlated** `command:"prompt", success:false`
— which this design classifies truthfully as `PROMPT_RESPONSE_REFUSED`), and
`handleInputLine`'s `catch (commandError)` returns `error(command.id,
command.type, …)`.

**Consequence used in §7.5:** in `0.84.4` the parse-failure response is the
**only** id-less response Pi can emit.

### 2.4 Prompt-content contribution by Pi — CONFIRMED and bounded

For text that does **not** begin with `/`:

- `AgentSession._expandSkillCommand` returns `text` unchanged
  (`if (!text.startsWith("/skill:")) return text;`);
- `expandPromptTemplate` returns `text` unchanged
  (`if (!text.startsWith("/")) return text;`);
- the extension-slash-command branch is not entered
  (`expandPromptTemplates && text.startsWith("/")`).

And AIDO's frozen argv (`ar2.launch.build_pi_argv`) already passes
`--no-skills`, `--no-prompt-templates`, `--no-context-files`, `--no-extensions`,
`--extension <one AIDO extension>`, `--tools aido_read,aido_edit`,
`--no-builtin-tools`, `--no-themes`, `--no-approve`, `--offline` — so the
template and skill registries are empty regardless.

The user message Pi builds is therefore exactly
`[{type:"text", text: <AIDO's frozen task prompt>}]`.

**What Pi itself necessarily adds, and which this design records as Pi's
contribution rather than AIDO prompt text:** a Pi-authored **system prompt**
(`buildSystemPrompt`, carrying tool snippets for the two allowlisted tools and
Pi's own prompt guidelines). AIDO neither authors nor suppresses it; LIVE1 must
never describe the transmitted context as "only AIDO's prompt".

### 2.5 What a successful write proves — CONFIRMED unchanged

`ar2.supervisor.PiRpcSupervisor.send_command` does
`json.dumps(command, ensure_ascii=True).encode("utf-8") + b"\n"`, then
`write()`, then `flush()`, and raises `PiSupervisorError` on `OSError` after
recording `stdin_write_error`. A returned `send_command` proves only that the
bytes were handed to the OS pipe. PRE1 §1.7's reading stands unchanged, in both
directions.

### 2.6 Capability authority seam — CONFIRMED gap, and the correction's binding shape

Independent review **confirmed** the `FROZEN_CONTRACT_CONFLICT` recorded here.
FU1 does not reopen the finding; it replaces the *illustrative* fix, which was
not safe to freeze, with a locked statement of **what** the correction must be.

This is the one conflict this design found, and it is **not** about Pi.

#### 2.6.1 The frozen assumption

`qualification.semantic_controller.run_semantic_task_attempt` creates the
broker for a semantic task by calling the injected adapter with

```python
create_broker(BrokerCreationRequest(run_id=run_id, workspace=run_workspace))
```

i.e. PRE1 assumes an injected `create_broker` can construct a **semantically
useful** broker capability from the run workspace alone, and the roadmap
(§4.5.4) requires LIVE1 to assemble the frozen controller *"together with the
existing live compatibility / route / resource primitives — reusing them
unmodified, not forking parallel versions."*

#### 2.6.2 The actual source observation, re-verified

1. `qualification.i2b_live_adapters.LiveCategoryBAdapters.create_broker`
   builds its capability from
   `_build_inert_static_eligibility_domain(canonical_root=…)`, whose own
   docstring reads *"A real, valid, but STRUCTURALLY POWERLESS capability"*:
   `manifest=()`, `read_eligible=frozenset()`, `write_eligible=frozenset()`.
   Under that domain, `ar2.candidate.evaluate_delegated_candidate` refuses
   **every** read and **every** edit at layer L2. Correct for Category-B, which
   sends zero prompts by definition; unusable for a semantic task.
2. There is **no parameter, factory, hook or subclass seam** through which a
   different capability domain can be supplied: `LiveCategoryBAdapters.__init__`
   accepts only `environ_reader`, `runtime_identity`, `experiment_id`, `bounds`.
3. **Subclassing is refused downstream, deliberately.**
   `AuthenticatedB300RouteObserver.__init__` requires
   `type(adapters) is LiveCategoryBAdapters` (`LF2-FU1 BLOCKER 2`).
4. **The broker and runtime halves cannot be split.**
   `LiveCategoryBAdapters.launch_runtime` begins with
   `self._require_exact_broker_session(request.broker_session)`, which looks the
   session up in that instance's own `_brokers` registry.
5. **`mint_capability` cannot be called for this workspace from outside.**
   `ar2.capability.mint_capability` requires a `DisposableRootAuthority`. For a
   `QualificationRunWorkspace` that object exists **only** in
   `qualification.i2b_workspace._MINTED[nonce].authority`; the module exposes no
   accessor. `ar2.fixtures.build_case_repository` does return a `BuiltFixture`
   carrying an authority — but it always mints its **own** fresh root, which is
   not the controller's workspace.
6. `BrokerCreationRequest` carries no task identity (`run_id` + `workspace`
   only), so the task's contract cannot travel with the request. *(Not blocking
   on its own: `run_primary_sweep` calls `build_adapters(task)` per task, so a
   per-task adapter already holds the frozen `QualificationTask`.)*

#### 2.6.3 Why the earlier illustrative proposal is REJECTED, not refined

The pre-FU1 draft proposed

```python
mint_run_workspace_capability(
    workspace,
    tracked_manifest=<caller supplied>,
    protected_patterns=<caller supplied>,
    verification_witness_paths=<caller supplied>,
)
```

and, as a companion, a generic
`capability_source: Callable[..., StaticEligibilityDomain]` constructor
parameter. **Both are refused.**

They do not leak the `DisposableRootAuthority`, which is why they read as safe.
But they make the *authority facts* caller-authored: the read-eligible set, the
protected set and the never-writable verification witnesses would all arrive as
arguments, and the hidden root authority would then **bless** them. A caller
that can name the manifest can name any manifest; a caller that can pass a
`capability_source` can pass any domain at all. Either shape converts
"the workspace's own authority" into "whatever the caller said, signed by the
workspace's authority", which is exactly the widening the brief forbids.

The correction must therefore **derive** every authority fact, never accept one.

#### 2.6.4 The correction's binding properties (WHAT is locked; HOW is not)

A separately-authorized correction phase — proposed name **`5F3B-LIVE1-C1`
(capability issuance seam)**, landing **before** `5F3B-LIVE1-I1` — must
establish a **narrow, qualification-owned capability issuance** with all twelve
of the following properties. The *mechanism* (an opaque one-shot issuance
handle, a sealed value object, a private strategy object, or another narrow
shape) is C1's design decision and is deliberately **not** frozen here.

```text
C1-P1   Authority origin.       The ONLY authority consumed is the existing
                                i2b_workspace `_MINTED[nonce].authority` record
                                for THIS workspace. No second DisposableRoot-
                                Authority origin is created, and
                                `ar2.fixtures.build_case_repository`'s own
                                fresh-root authority is never used here.

C1-P2   No authority escape.    No DisposableRootAuthority value, and nothing
                                from which one could be reconstructed, is
                                returned, stored on a public object, logged, or
                                placed in any evidence field.

C1-P3   Triple identity bind,   Issuance/consumption happens at ONE point --
        AT create_broker.        the `create_broker(BrokerCreationRequest)` call
                                 (Sec. 2.6.4a), NEVER at read_connection
                                 activation. It is bound to (a) this exact
                                 QualificationRunWorkspace nonce, taken from
                                 `request.workspace`, (b) `request.run_id`,
                                 which `BrokerCreationRequest.__post_init__` has
                                 already proved is the run that claimed that
                                 workspace, and (c) the frozen
                                 QualificationTask's `task_id` AND
                                 `task_revision`, read from the adapter's own
                                 bound task object. All three are checked when
                                 the capability is issued and re-checked
                                 wherever it is later presented.

C1-P4   Observed manifest.      `tracked_manifest` is AIDO-OBSERVED from THIS
                                synthetic repository -- the accepted fixed,
                                read-only `ls_files_stage` operation, via
                                `ar2.observation.observe_repository`, sorted --
                                and is never a caller-supplied path list, never
                                a glob, and never a filesystem walk.

C1-P5   Contract-derived policy. `protected_patterns` is exactly
                                `task.case.protected_patterns` and
                                `verification_witness_paths` is exactly
                                `task.case.verification_witness_paths`, read
                                from the frozen corpus object whose content is
                                already hashed into `task.task_revision`.
                                Neither is a parameter of the issuance call.

C1-P6   No caller domain.       There is no supported path by which a caller can
                                supply a StaticEligibilityDomain, a manifest, a
                                protected set, a witness set, a canonical root, a
                                CapDefinitions override, or a capability id.

C1-P7   No caller factory.      There is no `capability_source`,
                                `capability_factory`, `sed_builder`,
                                `domain_provider`, `mint_fn` or
                                equivalently-shaped callable parameter anywhere
                                on the live adapter, the semantic adapter, the
                                runner, or the issuance entry point.

C1-P8   No replay.              Issuance is ONE-SHOT, in the exact lineage of
                                `claim_run_workspace` and
                                `_claim_issued_runtime_identity`: a second
                                issuance for the same workspace nonce is
                                refused, and an issued capability presented
                                against a different workspace, run_id, task_id
                                or task_revision is refused at consumption --
                                so it cannot be carried into another task of the
                                same sweep, or into the other candidate's sweep.

C1-P9   Category-B default.     `LiveCategoryBAdapters`'s ORDINARY path keeps
                                today's inert domain, byte-for-byte, as the
                                DEFAULT -- reached without the caller naming
                                anything. The module keeps zero `"prompt"`
                                string literals and remains structurally
                                zero-prompt; `type(x) is LiveCategoryBAdapters`
                                still holds for the composed base (§11.1).

C1-P10  Frozen algorithm.       Eligibility is computed by the FROZEN,
                                UNMODIFIED `ar2.capability.mint_capability`:
                                forbidden-pattern exclusion, the protected set,
                                the witness set, and the PROPER-SUBSET assertion
                                are reused verbatim. No eligibility policy is
                                reimplemented, copied, simplified or relaxed
                                anywhere in the qualification package.

C1-P12  Trusted Git execution   EVERY Git execution in a semantic attempt is
        authority.              bound to the accepted `resolve_git_executable`
                                result for THIS verified workspace
                                (Sec. 2.6.5b). Two checkpoints, because source
                                shows two independent entry points:
                                  P12a  the FIXTURE-POPULATION checkpoint, in
                                        populate_semantic_task_workspace, right
                                        after verify_run_workspace and before
                                        the first git subprocess -- the caller's
                                        `git_executable` string is a PROVENANCE
                                        CLAIM re-proved by canonical exact
                                        equality, never an authority;
                                  P12b  the issuance's own INDEPENDENT
                                        resolution before observe_repository.
                                No target repository, task, model, artifact,
                                project config, operator-supplied path or
                                caller string may OVERRIDE the resolver result
                                (the resolver's own PATH input is unchanged and
                                is not a defect -- Sec. 2.6.5b). A mismatch or
                                an unresolvable executable refuses BEFORE any
                                process is launched, with no fallback.

C1-P11  Fail closed.            Any failure of P1..P10, P12 -- an unverifiable
                                workspace, an identity mismatch, a failed Git
                                observation, an empty observed manifest, a
                                `CapabilityMintError`, an unresolvable or
                                unmatched Git executable -- refuses with a
                                bounded reason code and no capability. It never falls
                                back to the inert domain (which would silently
                                produce a semantic run in which every model
                                operation is refused, and read as candidate
                                behaviour) and never falls back to a wider one.
```

#### 2.6.4a TWO separate authority events — identity activation, then capability issuance

**FU2 correction.** FU1 said the semantic adapter's `read_connection`
activation was "also where the capability issuance is bound". That is
**mechanically impossible** under the frozen controller, and the design is
corrected here rather than defended.

Source truth, re-verified:

| Fact | Source |
|---|---|
| `run_id` is minted **inside** `run_semantic_task_attempt` (`_mint_run_correlation_id()`) and is a local | `semantic_controller`, `RUN_CORRELATION` gate |
| `run_workspace` is minted **inside** the same function (`mint_qualification_run_workspace()`), claimed for that `run_id`, and is a local | `WORKSPACE_AUTHORITY` gate |
| `read_connection` has the frozen **zero-argument** call shape `Callable[[], ConnectionValues]` | `TaskAdapterBundle`, `resolve_connection_after_preflight` |
| the **first** adapter call carrying both `run_id` and the exact workspace is `create_broker(BrokerCreationRequest(run_id=run_id, workspace=run_workspace))` | `BROKER_SESSION` gate |

So at activation time the adapter knows the frozen `QualificationTask` and
nothing else. It does not know the run, and it does not know the workspace.
A capability bound to all four identities **cannot** be issued there.

The two events are therefore separated, and both are load-bearing:

```text
EVENT 1 -- RUNTIME IDENTITY ACTIVATION            (Sec. 12.2A)
  trigger : read_connection(), after ALL eight Category-A non-secret gates pass
  inputs  : none from the caller
  actions : resolve_pi_identity()  -- the ONE `node cli.js --version` probe
            construct the exact-type LiveCategoryBAdapters
            delegate the ONE credential read
  binds   : Pi/Node identity to this adapter instance (one-shot issuance)
  does NOT: touch the capability, the workspace, the run id, or the manifest

            ... SECRET_CONTEXT -> PI_CONFIG_GENERATION -> IDENTITY_BINDING
                -> CHILD_ENVIRONMENT ...

EVENT 2 -- CAPABILITY ISSUANCE / CONSUMPTION      (Sec. 2.6.4, this subsection)
  trigger : create_broker(BrokerCreationRequest(run_id=..., workspace=...))
  inputs  : request.run_id + request.workspace  (frozen, already cross-proved)
            self._task                          (frozen corpus object)
  actions : verify_run_workspace(request.workspace)
            resolve_git_executable(workspace_root=<verified root>)  (P12b)
              -- independently re-derived; already proved once at P12a
            observe this repository's index -> tracked manifest  (Sec. 2.6.5a)
            issue/consume the capability under C1-P1..C1-P12
            create the broker with the resulting genuine semantic capability
  binds   : workspace nonce + run_id + task_id + task_revision
  does NOT: launch Pi, read a credential, or re-resolve identity
```

Three consequences, each of which the correction phase must preserve:

1. **`read_connection` is not widened.** It keeps its frozen zero-argument
   shape. No `run_id`, no workspace, no task, and no capability parameter is
   added to it, and none is smuggled past it.
2. **No ambient mutable state carries the run or workspace forward.** The
   adapter does not stash a `run_id` from somewhere earlier, does not read a
   module-level "current run" variable, and does not accept one from the runner.
   The only supported source of both is the `BrokerCreationRequest` the frozen
   controller itself constructs.
3. **`semantic_controller` and `BrokerCreationRequest` are NOT modified.** The
   frozen request already carries exactly the two facts Event 2 needs; the
   third and fourth (`task_id`, `task_revision`) already live on the adapter.
   Nothing is widened to make an earlier, wrong design convenient.

> **An activation failure and an issuance failure are different failures.**
> Event 1 failing lands at `NON_SECRET_PREFLIGHT` / `CONNECTION_VALUES` with no
> broker and no capability. Event 2 failing lands at `BROKER_SESSION` with
> `BROKER_CREATION_FAILED`, after a credential has already been read — which is
> the frozen controller's own ordering and is not changed here. Neither is ever
> reported as the other.

#### 2.6.5 Where each authority fact comes from — derivation table

Every row is a **derivation**. No row is an argument a caller chooses.

| Mint input | Derived from | Frozen source |
|---|---|---|
| `authority` | the run's own mint record | `i2b_workspace._MINTED[nonce].authority`, re-verified through the frozen `_verify_root_authority` exactly as `verify_run_workspace` already does |
| `tracked_manifest` | AIDO's own Git observation of this repository | `sorted(entry.path for entry in observe_repository(...).index_entries)` — the identical derivation `run_ar2.py` already performs before its own `mint_capability` call |
| `protected_patterns` | the frozen task contract | `task.case.protected_patterns` |
| `verification_witness_paths` | the frozen task contract | `task.case.verification_witness_paths` |
| the Git executable that produces the manifest — **and every other Git execution in the attempt** | AIDO's own accepted resolver, run against the verified root, proved at **two** checkpoints | `resolve_git_executable(workspace_root=…)` — §2.6.5b / C1-P12a + P12b. The caller's string is re-proved by exact equality and never executed; nothing may override the resolver |
| `caps` | the frozen defaults | `ar2.capability.CapDefinitions()` — no override parameter |
| `canonical_root` | the mint itself | produced *inside* `mint_capability` from the verified authority; never passed in |

Two consequences, stated because they are load-bearing:

- **The manifest is observed, not asserted.** `SemanticTaskWorkspace.tracked_paths`
  is `tuple(sorted(task.case.files))` — what AIDO *intended* to commit. C1 must
  not use it as the mint manifest; it must use what Git's index actually
  reports. The two are expected to agree, and C1 must **refuse on
  disagreement** rather than prefer either, because a disagreement means the
  populated fixture is not the fixture the revision names.
- **The witness paths become never-writable by the frozen algorithm**, which is
  what makes the hard-disqualifier codes
  `verification_witness_is_never_writable` and
  `protected_path_is_readable_not_writable` reachable at all in a semantic run.
  Under today's inert domain they are unreachable, because every operation dies
  earlier at `not_in_mint_time_manifest`.

#### 2.6.5a The `i2b_workspace` process-free invariant — RESOLVED, not glossed

**FU2 finding.** FU1 asserted both of the following, and they cannot both be
true:

```text
"the manifest is AIDO-observed via ar2.observation.observe_repository"
"the only i2b_workspace change is adding an issuance entry point"
```

`observe_repository` runs the accepted fixed Git operations through
`run_fixed_git_operation`, which launches `git`. `qualification.i2b_workspace`'s
own module docstring opens with **"OFFLINE ONLY. This module launches nothing,
opens no socket, calls no model, and reads no credential."** Putting the
observation behind its issuance entry point therefore changes that invariant,
and FU1 did not say so.

##### The existing test would NOT have caught it

This is the part that makes the finding serious rather than editorial.
`tests/test_i2b_controller.py::test_no_i2b_module_imports_a_live_io_primitive`
walks each of `i2b_controller`, `i2b_session`, `i2b_workspace` and asserts that
no **direct** import root is in

```text
subprocess socket ssl http urllib requests httpx asyncio
multiprocessing threading shutil litellm openai
```

and that the docstring-stripped source contains none of
`os.environ`, `getenv`, `Popen`, `urlopen`, `open(`.

`from ar2.observation import observe_repository` has the import root **`ar2`**,
which is not on that list, and calls no forbidden fragment textually. **The test
is transitive-blind, so it would pass while the invariant became false.** A
silently-passing purity test is worse than a failing one, and no design may
describe that outcome as "unchanged".

##### The two candidate designs, assessed at source

| | **A — authorize a semantic-only observation inside `i2b_workspace`** | **B — keep `i2b_workspace` process-free; sealed two-module composition** |
|---|---|---|
| Where `git` runs | inside `i2b_workspace`, on the root `verify_run_workspace` just returned | inside a separate qualification-owned observer module |
| How the manifest reaches the mint | never leaves the module | as a **sealed, opaque observation token** whose manifest is readable only from the issuing module's private registry — the `IssuedRuntimeIdentity` / `_IDENTITY_ISSUER_KEY` pattern, copied |
| Caller can author the manifest | no | no |
| Caller can recover the authority | no | no |
| `i2b_workspace` docstring invariant | **changed, explicitly** | preserved |
| New production modules | 0 | 1 |
| New cross-module secret | none | one module-private issuer key shared between two modules |
| Purity test | must be **amended and strengthened** (see below) | unchanged and still meaningful |

Option B is admissible — a single-purpose sealed token in the shipped
`IssuedRuntimeIdentity` lineage is **not** a generic provenance framework, a
callback, a manifest factory, or a caller-authorable attestation, so the brief's
four exclusions do not bite. It is nevertheless **larger**: a second module, a
second registry, and an issuer key that must be shared across a module boundary
that today has no such coupling.

##### Chosen: **A**, with the invariant change made explicit and the test strengthened

The reasoning is about *which* invariant is load-bearing. `i2b_workspace`'s
security property, stated in its own docstring, is **"authority originates at
CREATION, never from a string"** — there is deliberately no function that turns
an existing path into a `QualificationRunWorkspace`. Process abstinence was a
*consequence* of Category-B having no reason to run anything, not the property
being protected.

Under A the new call runs `git` **only** at the root that
`verify_run_workspace(workspace)` just re-proved, for a `QualificationRunWorkspace`
that is unforgeable by API. The process authority is bound to the same
unforgeable object as every other operation in the module, so the path-authority
property is untouched. Option B buys a preserved sentence at the cost of more
surface, and more surface is the thing this project treats as the risk.

##### What C1 must therefore state and prove — exactly

```text
1. PRODUCTION MODULES REOPENED -- THREE (corrected, FU4A)
   qualification.i2b_workspace      -- gains ONE semantic-only path that runs the
                                       accepted read-only Git observation, plus
                                       the issuance entry point (Sec. 2.6.4/2.6.6)
   qualification.i2b_live_adapters  -- issued capability at create_broker; inert
                                       default byte-identical (Sec. 2.6.6)
   qualification.semantic_workspace -- the C1-P12a fixture-population Git
                                       checkpoint (Sec. 2.6.5b). REQUIRED: this
                                       module performs the attempt's FIRST Git
                                       execution, so the authority cannot be
                                       established anywhere else.

   No other production module is reopened. ar2 is untouched, and
   semantic_controller / semantic_sweep remain CLOSED (Sec. 2.6.5b).

2. EXISTING OFFLINE INVARIANT CHANGED
   The i2b_workspace module docstring's "This module launches nothing" is
   NARROWED, in the docstring itself, to state exactly:

       Category-B path            launches nothing, as before
       semantic issuance path     runs the accepted fixed, read-only Git
                                  observation ONCE, through
                                  ar2.observation.observe_repository, at the
                                  root verify_run_workspace just returned

   It still opens no socket, calls no model, reads no credential, and still
   exposes no function that converts an existing path into a workspace.

3. INVARIANTS EXPLICITLY PRESERVED
   - no network, no model, no credential, no environment read
   - no path/manifest/pattern/witness/root/domain parameter
   - no DisposableRootAuthority on any public surface or repr
   - one-shot issuance; no replay across task, run, workspace or revision

4. REGRESSION TESTS THAT PROVE CATEGORY-B IS UNCHANGED
   T1  a complete Category-B run issues ZERO Git operations. Count calls to
       ar2.observation.observe_repository / run_fixed_git_operation across
       run_category_b_controller with the live adapter's Category-B path; assert 0.
   T2  Category-B's capability is byte-identical to today's inert domain:
       manifest (), read_eligible frozenset(), write_eligible frozenset(),
       protected frozenset(), witnesses frozenset(), excluded (), same caps,
       same root_class, same lifetime.
   T3  the semantic issuance path is UNREACHABLE without a bound
       QualificationTask: an adapter constructed the Category-B way cannot
       reach it, proved by call-site AST plus a runtime attempt that refuses.
   T4  the whole existing tests/test_i2b_controller.py suite passes, with
       exactly ONE deliberate amendment (T5).
   T5  test_no_i2b_module_imports_a_live_io_primitive is AMENDED AND
       STRENGTHENED rather than deleted or loosened:
         - it records the reopening explicitly, naming the one allowed
           ar2.observation import by exact symbol;
         - it becomes transitive-aware for this case: i2b_workspace's allowed
           ar2 imports are an EXACT closed set, so importing any other ar2
           symbol (or any new process-capable dependency) fails;
         - it keeps every existing prohibition for i2b_controller and
           i2b_session unchanged.
   T6  no i2b module gains an environment read, a socket, a model call, or a
       prompt-shaped name -- the other purity assertions are untouched and
       still pass.
```

##### Is FU1's "existing suite passes unchanged" claim still literally true?

**Partly, and the difference matters:**

| Claim | FU2 verdict |
|---|---|
| `tests/test_i2b_live_adapters.py` passes **unchanged** | **True**, provided C1's `i2b_live_adapters` changes are additive and the Category-B branch is byte-identical (T2). This is the file FU1 named |
| `tests/test_i2b_controller.py` passes **unchanged** | **FALSE, and FU1 should not have implied it.** Its purity test must be deliberately amended (T5). It would have passed *silently*, which is precisely why the amendment is mandatory rather than optional |
| "the only i2b_workspace change is an issuance entry point" | **FALSE.** The module also gains, for the semantic path only, the accepted read-only Git observation. FU1's §2.6.6 wording is corrected accordingly |

**No hidden or transitive process widening is described anywhere in this design
as "unchanged".** The widening is named, scoped to one path, bound to an
unforgeable workspace object, and made visible in the very test that would
otherwise have concealed it.

#### 2.6.5b Trusted Git execution authority — C1-P12 (FU3 BLOCKER 1)

FU2 established *what* the manifest is (`observe_repository(...).index_entries`)
but not *which program produces it*. That gap is real and is closed here.

##### The source truth

| Component | What it actually enforces |
|---|---|
| `resolve_git_executable(workspace_root=...)` | **the accepted authority.** `shutil.which("git")`, `abspath`, then three checks: absolute, an existing **regular file**, and **not inside the target workspace** — *"The repository being edited may not supply the program that inspects it."* |
| `run_fixed_git_operation(..., git_executable=...)` | **establishes no provenance.** Its docstring says the value *"must be the absolute path `resolve_git_executable` returned, and the caller is expected to reuse the same one"* — an expectation on the caller, not a check |
| `build_git_argv(..., git_executable=...)` | **checks only** `if not git_executable or not os.path.isabs(git_executable)`. Nothing else, immediately before `subprocess` |

So the only thing standing between an arbitrary caller-authored absolute path
and `subprocess` is "it is absolute". A new semantic issuance seam that accepted
a Git path from anywhere would be a **program-selection surface**, and this
project's own workspace rule — the repository under test must not supply the
program that inspects it — would be enforced by nobody.

##### The rule

```text
C1-P12  Before semantic capability issuance may call observe_repository, the Git
        executable for that observation MUST be mechanically bound to the
        accepted resolve_git_executable result for THIS verified workspace.

        RESOLUTION (chosen): resolve INTERNALLY at the issuance consumption
        boundary --
            resolve_git_executable(workspace_root=<the root
                                   verify_run_workspace JUST returned>)
        -- and execute exactly that value.

        ALTERNATIVE (only if a path is ever carried in): treat the carried value
        as PROVENANCE INPUT ONLY, resolve independently as above, and require
        CANONICAL EXACT EQUALITY before any process launch. Never trust it
        directly, and never use it as the executable without that proof.

        A failure to resolve, or an inequality under the alternative, REFUSES
        BEFORE GIT IS LAUNCHED. It never falls back to "git", to PATH, to the
        carried value, or to skipping the observation.
```

Resolving against **the verified workspace root** is the stronger choice, and
deliberately so: it is the root at which the not-inside-the-workspace check is
meaningful for *this* observation, and the workspace object is unforgeable by
API — so the process authority is bound to the same object as every other
operation on that path (§2.6.5a).

##### `LiveSemanticAdapters` loses its `git_executable` parameter

**Answer: the constructor input is not required, and it is removed.** Tracing
every consumer:

| Consumer | Needs a Git path? |
|---|---|
| the four semantic ports (§§7–10) | no |
| the 13 delegated zero-prompt ports | no — `LiveCategoryBAdapters.__init__` has no `git_executable` parameter |
| the manifest observation at `create_broker` | yes — and under C1-P12 it **resolves its own**, internally |

Removing it deletes the caller-authored absolute-path surface **entirely**
rather than defending it, which is strictly better than checking equality
against something a caller supplied. §12.3's factory sketch is corrected
accordingly.

> **This does not remove `git_executable` from the runner.** Frozen
> `run_primary_sweep` requires it as a plain string argument, and the frozen
> controller uses it for `populate_semantic_task_workspace` and for its own
> `REPOSITORY_OBSERVATION` gate. That parameter is untouched. What is removed is
> the **adapter constructor** parameter FU1/FU2 sketched — a different thing,
> and the only one C1 would have introduced.

##### The end-to-end Git execution graph — CORRECTED (FU4 item 1)

FU3 closed the `create_broker` manifest observation and stopped there. Source
shows that was **incomplete**: an earlier execution path runs Git before
`create_broker` is ever reached, and two further consumers take the same
caller-supplied string. The complete graph, read from source:

```text
run_primary_sweep(git_executable=<CALLER STRING>)        frozen, string input
    |
    v  forwarded unchanged, never reassigned
run_semantic_task_attempt(git_executable=<same local>)   frozen
    |
    +-- GATE 2  WORKSPACE_AUTHORITY
    |     populate_semantic_task_workspace(..., git_executable=...)
    |       -> semantic_workspace._git(...)
    |          -> subprocess.run([git_executable, ...])
    |          EXECUTES GIT: init -b main / add / commit / rev-parse HEAD
    |          *** THE FIRST GIT EXECUTION OF THE ATTEMPT ***
    |
    +-- GATE 10 CHILD_ENVIRONMENT
    |     build_child_environment(..., git_executable=...)
    |       -> _narrowed_path(): entries.insert(1, os.path.dirname(git_executable))
    |          DOES NOT EXECUTE -- but places that DIRECTORY on the
    |          UNTRUSTED PI CHILD'S PATH
    |
    +-- GATE 11 BROKER_SESSION
    |     create_broker -> C1 capability issuance
    |       -> the manifest observation (Sec. 2.6.4a EVENT 2)
    |          EXECUTES GIT: ls_files_stage and the rest of the fixed set
    |
    +-- POST-PROMPT  REPOSITORY_OBSERVATION
          observe_repository(git_executable=..., workspace_root=...)
             EXECUTES GIT: the AUTHORITATIVE changed-path/HEAD/index evidence
             that feeds classification, scope, H-8 and the hard bar
```

`qualification.semantic_workspace` performs **no**
`resolve_git_executable(workspace_root=…)` provenance check today: it receives
the string and executes it. So FU3's three claims —

```text
"an arbitrary absolute executable at any reachable surface refuses"
"the same Git identity is used for fixture population and manifest observation"
"no reachable semantic surface selects a Git executable"
```

— were **not** mechanically true when written. They are withdrawn and replaced.

Two consequences are worth naming, because they are not merely evidential:

- a substituted executable at the **first** path forges the very Git index the
  capability manifest is later minted from (§2.6.5a C1-P4), *and* the
  authoritative post-prompt observation that decides the qualification verdict;
- a substituted path at `CHILD_ENVIRONMENT` puts an attacker-chosen directory
  on the **untrusted Pi child's** `PATH`.

##### The correction: one checkpoint, at the first consumption boundary

`git_executable` is a plain `str` parameter of `run_semantic_task_attempt`, and
source confirms it is **never reassigned** anywhere in that function. Every
consumer above reads that same local. So proving it **once**, at the earliest
consumption boundary, binds all four:

```text
C1-P12a  FIXTURE-POPULATION CHECKPOINT.

  populate_semantic_task_workspace keeps its frozen caller-visible
  `git_executable: str` shape, but that string is a PROVENANCE CLAIM, never an
  executable authority.

  IMMEDIATELY after `verify_run_workspace(workspace)` returns THIS workspace's
  verified root -- before the emptiness check, before any file write, and
  before the FIRST git subprocess:

      trusted_git = resolve_git_executable(
                        workspace_root=<that verified root>)

      REQUIRE  supplied_git_executable == trusted_git      # EXACT STRING EQUALITY

    equal        -> proceed, executing ONLY trusted_git
    not equal    -> bounded refusal (SemanticWorkspaceError, a fixed reason code,
                    never echoing either path), with ZERO Git subprocesses and
                    ZERO fixture file writes
    unresolvable -> the same bounded refusal

  There is NO fallback to the supplied string, to "git", or to PATH-at-call-time.

  THE COMPARISON MUST BE EXACT STRING EQUALITY ON THE SPELLING, not

      realpath(supplied) == realpath(trusted)

  nor any other same-target alias test. The reason is mechanical and is the
  whole basis of the single-checkpoint proof below: `run_semantic_task_attempt`
  keeps using its ORIGINAL `git_executable` local after
  populate_semantic_task_workspace returns. A weaker alias comparison would
  admit a DIFFERENT SPELLING of the same target -- and that different spelling,
  not trusted_git, is what the later consumers would carry. Requiring the
  supplied string to BE the resolver's return value makes the controller's
  unchanged local EXACTLY trusted_git, so the later consumers are bound without
  reopening the controller.
```

**Why this closes all four consumers, mechanically:**

The checkpoint proves `supplied == trusted_git`. The controller's
`git_executable` local is that same supplied string and source confirms it is
**never reassigned**, so after the checkpoint the local **is** `trusted_git` —
not merely equivalent to it, and not merely an alias of it.

| Consumer | Ordered after the checkpoint? | Therefore |
|---|---|---|
| fixture population (gate 2) | it **is** the checkpoint | executes `trusted_git` |
| child environment (gate 10) | yes | `dirname()` of `trusted_git` itself |
| manifest observation (gate 11) | yes — and C1 resolves **independently** against the same verified root, so it obtains the same identity by construction | proved twice, from the same authority |
| repository observation (post-prompt) | yes | executes `trusted_git` |

**`semantic_controller` and `semantic_sweep` are NOT reopened**, and source
supports that rather than merely permitting it: the checkpoint sits at the
attempt's first Git consumption, strictly before every other one, on a value
that cannot change between them. Reopening the controller to re-check at
`REPOSITORY_OBSERVATION` would re-prove an already-proved constant.

> **The residual limit, stated rather than glossed.** This binds the executable
> *identity* at one point in time. It is not a claim that the binary on disk
> cannot be replaced afterwards by a same-user adversary — the identical honest
> scope `i2b_workspace`'s own docstring already states for marker forgery. It
> defends against an AIDO configuration or programming mistake, a caller
> passing the wrong string, and a repository-supplied program; not against a
> same-user attacker who does not need this path at all.

##### PATH wording — CORRECTED (FU4 item 1)

FU3's T12 said *"no reachable parameter, config key, environment name, artifact
field or model/task value can select a Git executable"*. The clause about
environment names is **false**: `resolve_git_executable` begins with
`shutil.which("git")`, so **the AIDO process's own `PATH` is an input to the
accepted resolver, by design.** The correct claim is about *override*, not about
environment independence:

```text
CORRECT:   No target repository, task, model, artifact, project config,
           operator-supplied executable path, or caller-supplied string may
           OVERRIDE the accepted resolver's result. The resolver is the only
           authority, and its own inputs are AIDO's process PATH plus the three
           frozen checks (absolute, an existing regular file, and NOT inside the
           target workspace).

WRONG:     "no environment value selects Git."
```

The `not inside the target workspace` check is what makes the
repository-supplied case impossible, and it is the frozen resolver's, not
something C1 adds.

##### C1 regression obligations for C1-P12 / C1-P12a

```text
T7   the fixture population and the manifest observation execute the SAME
     identity: patch resolve_git_executable to return a synthetic absolute
     path, and assert every Git argv[0] in the whole attempt is that value.
T8   an arbitrary absolute executable passed as run_primary_sweep's
     git_executable -> REFUSED at the WORKSPACE_AUTHORITY checkpoint, with
     ZERO Git subprocesses and ZERO fixture file writes.
T9   a workspace-local executable (planted inside the verified root) -> REFUSED
     by the frozen resolver's own not-inside-the-workspace check; zero launches.
T10  the trusted resolver's exact result -> allowed; population and observation
     both proceed.
T11  caller string / independent resolution MISMATCH -> REFUSE before launch,
     never a fallback to either value.
T12  no target-repository, task, model, artifact, project-config,
     operator-supplied or caller-supplied value can OVERRIDE the resolver
     result -- signature and AST inspection, in the lineage of the accepted
     "no --model / no --endpoint" CLI surface tests (Sec. 12.1). The test
     asserts OVERRIDE-impossibility, and does NOT assert that Git resolution is
     independent of PATH, which would be false.
T13  the checkpoint is ordered FIRST: an ordered event log over one attempt
     shows the resolve-and-compare event strictly before the first git
     subprocess, the first fixture file write, the child-environment build, the
     manifest observation, and the repository observation.
T14  `dirname(git_executable)` reaching the Pi child's PATH is the resolved
     identity's directory, never a caller-supplied one.
```

##### The strengthened purity test must name this import too

§2.6.5a T5 requires `i2b_workspace`'s process-capable imports to be an **exact
closed set**. Under C1-P12 that set is exactly two symbols —
`ar2.observation.observe_repository` and the accepted
`resolve_git_executable` — and any other process-capable import fails the test.
`qualification.semantic_workspace` is a module that **already** executes
subprocesses, so C1-P12a adds no new capability there; it adds a **check**, and
the same exact-closed-set discipline applies to whatever it imports.

#### 2.6.6 Exact minimum frozen modules `5F3B-LIVE1-C1` must reopen

Exactly **three** (FU4A corrected this from two), each for exactly one reason:

| Module | Minimum change | Not permitted |
|---|---|---|
| `qualification.i2b_workspace` | add the issuance entry point satisfying C1-P1…P12 and its one-shot registry (the in-memory, process-local, never-persisted shape `_MINTED` / `_CLAIMED` already use); the semantic-only read-only Git observation §2.6.5a authorizes, with the docstring invariant narrowed in the same edit; and the internal `resolve_git_executable` binding §2.6.5b requires | returning, exposing, copying or re-deriving the `DisposableRootAuthority`; accepting a path, a manifest, a pattern list, a witness list, a root, a cap override, or a domain; any function that turns an existing directory into a workspace; any socket, model call, credential or environment read; any Git operation on the Category-B path |
| `qualification.i2b_live_adapters` | make `create_broker`'s capability the **issued** one when — and only when — this adapter instance was constructed for a semantic task, with the inert domain as the untouched default | a public capability accessor; a `capability_source` callable; a `prompt`-adjacent parameter or literal; any weakening of the exact-type route-observer check; any new public accessor returning a live supervisor, handler, or server |
| `qualification.semantic_workspace` **(FU4A)** | add the C1-P12a checkpoint: resolve independently against the verified root and require exact equality with the supplied `git_executable` **before** any fixture write and any Git subprocess, then execute the resolved value (§2.6.5b) | changing `populate_semantic_task_workspace`'s frozen caller-visible signature; adding a resolver/executable/factory parameter; any fallback to the supplied string, to `"git"`, or to PATH-at-call-time; any new Git operation beyond the existing `init`/`add`/`commit`/`rev-parse` set; echoing either path in a refusal |

**No other production module is reopened by C1.** In particular `ar2.capability`,
`ar2.candidate`, `ar2.broker`, `ar2.operations`, `ar2.observation`,
`ar2.fixtures`, `semantic_controller`, `semantic_sweep`, `semantic_session`,
`i2b_session`, `validity`, `outcomes` and `hard_bar` are untouched **by C1**.
`records`, `semantic_attempt` and `safety` are untouched by C1 but are reopened
by **C4** (§10A.2c), and `ranking` by **C3** — a phase boundary, not a blanket
"untouched" claim. **One test file is deliberately amended** —
`tests/test_i2b_controller.py`'s purity test, per §2.6.5a T5 — and that
amendment is part of C1's acceptance, not an incidental edit.

> **`BrokerCreationRequest` is deliberately NOT widened.** Adding a task field
> to it would push task identity into a frozen PRE1 value object consumed by the
> frozen controller. The per-task adapter already holds the frozen
> `QualificationTask` (§7.1), which is where that identity belongs.

#### 2.6.7 Rejected alternatives, recorded so they are refused explicitly

- **A sibling live adapter** duplicating broker + runtime creation with a real
  capability. It forks an adversarially-reviewed security mechanism
  (partial-broker retention, exact-broker-authority checks, three-state
  required-flag classification, launch diagnostics) into two versions that will
  drift.
- **A caller-supplied `capability_source` / capability factory** (§2.6.3).
- **Caller-supplied manifest / protected-pattern / witness arguments** (§2.6.3).
- **Reaching into `i2b_workspace._MINTED` from another module**, or minting a
  second disposable root purely so `mint_capability` has something to consume.
- **Widening `LiveCategoryBAdapters` into a generally capability-configurable
  adapter**, or making the inert domain reachable only via an explicit opt-out.

#### 2.6.8 C1's own acceptance obligation

Candidate A and Candidate B are **Category-B QUALIFIED / FROZEN**. C1 must prove
the Category-B path is **behaviourally identical** — same inert domain values,
same capability shape, same broker/runtime lifecycle, same diagnostics,
**zero Git operations** (§2.6.5a T1), and the existing
`tests/test_i2b_live_adapters.py` suite (including
`test_no_prompt_command_type_is_ever_constructed`) passing unchanged — or those
frozen results' provenance is disturbed. `tests/test_i2b_controller.py` does
**not** pass unchanged: its purity test is deliberately amended and strengthened
(§2.6.5a T5), and that amendment is itself reviewable evidence of the one
invariant C1 reopens. That proof is **C1's** job, not
`LIVE1-I1`'s, and it is a condition of C1's acceptance.

**§§3–16 are written so that only §11.3's handle binding and §12.3's
`create_broker` / `launch_runtime` delegation depend on C1's outcome.**

---

## 3. Live object and resource ownership model

### 3.1 The single owner already exists

The brief's CDQ 1 asks for exactly one task-local owner of the Pi child handle,
the stdin writer, the stdout record stream, command-id correlation, records
already read, and stream-terminal state.

**`ar2.supervisor.PiRpcSupervisor` is already that owner, and LIVE1 adds no
second one.** From source:

| Owned thing | Where it lives | Why nothing else may touch it |
|---|---|---|
| child process handle | `PiRpcSupervisor.process` | assigned once in `launch()` |
| stdin writer | `self.process.stdin`, written only by `send_command` | one method, LF-framed, `json.dumps` |
| stdout record stream | `PiRpcSupervisor._stdout: RecordStreamReader` | one daemon thread, publishes under a lock/condition |
| records already read | `RecordStreamReader._records` + `PiRpcSupervisor._consumed` cursor | `_drain()` consumes forward-only and folds into `activity` |
| command-id correlation | `RuntimeActivity.responses: dict[str, dict]`, keyed by RPC id in `_absorb` | one absorber |
| stream-terminal state | `_terminal_stream_outcome()` over the reader's monotonic `protocol_violation` / `byte_cap_exceeded` / `record_cap_exceeded` / `read_error` | fields are assigned once, never cleared |

Both `await_response` and `await_settled` funnel through the same `_wait`, so
there is **structurally one consumer**. Phase 1 and Phase 2 do not race; they are
two calls on one object.

### 3.2 The task-local live record LIVE1 adds

LIVE1 adds one private, adapter-owned dataclass — the only new live state in the
phase:

```text
_LiveSemanticTransport
    run_id                    str          the controller's run correlation id
    broker_session_id         str
    runtime_session_id        str
    supervisor                PiRpcSupervisor      (bound, never re-created)
    broker_handler            BrokerRequestHandler (bound, never re-created)
    task_id                   str
    task_revision             str
    prompt_command_id         str | None   allocated at dispatch, once
    dispatch_observation      SemanticPromptDispatchObservation | None
    dispatch_completed        bool         one-shot guard for phase 1
    turn_observed             bool         one-shot guard for phase 2
    broker_activity_collected bool         one-shot guard
    report_claims_collected   bool         one-shot guard
    baseline                  _DispatchBaseline  (see §7.4)
    retired                   bool         set by shutdown_runtime
```

**Ownership rules, all mechanically checkable:**

1. **One adapter instance per task.** `run_primary_sweep` calls
   `build_adapters(task)` once per task and requires a fresh `TaskAdapterBundle`
   each time; the runner's factory constructs a fresh `LiveSemanticAdapters`
   there. Two tasks therefore share no Python object at all.
2. **At most one transport per adapter instance.** `launch_runtime` is called
   once by the controller; a second call refuses.
3. **Lookup is by the frozen `RuntimeSession`'s three ids together**
   (`run_id`, `broker_session_id`, `runtime_session_id`), never by
   `runtime_session_id` alone — the identical discipline
   `LiveCategoryBAdapters._require_runtime_record` already applies. A session
   whose ids do not all match this adapter's own transport is refused; the
   adapter never acts on a child it did not itself launch.
4. **There is no process-global registry.** The transport hangs off the adapter
   instance, which is unreachable after the task returns. A "stale cross-task
   registry entry" is therefore not merely refused — it is unrepresentable.
5. **`retired` is set by `shutdown_runtime` and is terminal.** Every semantic
   port refuses on a retired transport.

### 3.3 Frozen types are not widened

`RuntimeSession` and `BrokerSession` remain exactly as frozen: correlation
identifiers only, no process handle, no pipe, no callable. The live handles live
in adapter-private state and are bound to those ids, never inside them. This
satisfies the brief's "do not stuff opaque live Python handles into
evidence-bearing value objects".

---

## 4. Stream ownership and buffering model (CDQ 4)

### 4.1 Why no new buffer is needed — from source

`PiRpcSupervisor._wait(deadline, satisfied)`:

```text
loop:
    _drain()                      # records_since(cursor) -> _absorb(record) each
    terminal = _terminal_stream_outcome()   -> return it if not None
    if satisfied(): return RUNTIME_RESPONSE_RECEIVED
    if process exited: one last flush + drain, re-check, else RUNTIME_EXITED_EARLY
    if deadline passed: RUNTIME_DEADLINE_EXPIRED
    _stdout.wait_for_more(cursor, min(remaining, 0.25))
```

`_absorb` folds **every** drained record into `RuntimeActivity` **cumulatively
and monotonically**:

- `agent_settled` → `activity.settled = True` (set, never cleared)
- `agent_end` → `agent_end_count += 1`, `agent_end_will_retry_count += 1` if
  `willRetry`
- `response` with a `str` id → `activity.responses[id] = record`
- `response` without a `str` id → `activity.unmatched_response_ids.append("<no-id>")`
- `message_end` / `turn_end` → `activity.final_assistant_text` (assistant-role
  only) and `last_usage`
- `tool_execution_start/end`, `auto_retry_*`, `compaction_*`, `extension_error`
  → their own counters
- every record type → `activity.event_type_counts[kind] += 1`
- and the raw (reasoning-dropped) record stays in `RecordStreamReader._records`,
  readable via `sanitized_events()`.

**Therefore:** a record consumed while Phase 1 waits for the correlated response
cannot disappear. If `agent_settled` arrives during the Phase-1 wait,
`activity.settled` is already `True` when Phase 2 calls `await_settled`, and
`await_settled`'s first `_drain()`+`satisfied()` returns `RUNTIME_SETTLED`
immediately. That is required matrix case 8 (§16), and it is satisfied by frozen
code, not by anything LIVE1 writes.

### 4.2 Why Phase 2 cannot reinterpret an earlier record as another task's

Structurally, not by convention:

- one `PiRpcSupervisor` per launched child, one child per task, one adapter per
  task;
- `RecordStreamReader` reads exactly `self.process.stdout` of that child;
- the semantic adapter refuses any `RuntimeSession` that is not its own (§3.2
  rule 3).

There is no shared record store, so cross-task contamination has no medium.

### 4.3 Reasoning and unbounded-log discipline

`RecordStreamReader._run` calls `ingest_record(...)` **before publication**, so
reasoning-bearing keys, blocks and delta records are structurally removed at
ingestion — nothing LIVE1 reads has ever contained them. Bounds
(`max_stdout_bytes = 32 MiB`, `max_events = 200_000`) are the frozen `RunBounds`
defaults and LIVE1 introduces **no new bound and no new timeout policy**.

**LIVE1 retains no raw record anywhere.** The only things it derives from the
stream are booleans, small integers, bounded enum members, and — in exactly one
place (§7.5) — a count of records matching a fixed shape. No record, no
`error` string, no assistant text and no usage blob is retained by LIVE1 or
passed into any frozen value object.

---

## 5. Which frozen timeouts LIVE1 uses

No new timeout policy. Both waits reuse the frozen `ar2.supervisor.RunBounds`
already used by Category-B and AR2/O1:

| Wait | Bound | Default | Why it is right |
|---|---|---|---|
| Phase-1 acknowledgement | `RunBounds.startup_deadline_seconds` | 60 s | the acknowledgement is emitted *before* any provider inference (§2.1), so it is a startup-class wait, not an inference-class one — the identical bound `launch_runtime`'s `h1` and `get_state`'s `h2` already use |
| Phase-2 settle | `RunBounds.turn_deadline_seconds` | 900 s | the frozen turn bound |

Both are AIDO's own monotonic deadlines (`time.monotonic()` inside `_wait`), and
both are identical for Candidate A and Candidate B (§15).

> **Claim discipline, verbatim.** A deadline means **AIDO stopped waiting**. It is
> never a claim that Pi stopped, that the prompt was cancelled, that provider
> inference stopped, or that any descendant stopped.

---

## 6. The four ports — signatures and placement

All four are bound methods of one task-local `LiveSemanticAdapters` instance,
handed to `TaskAdapterBundle` by the runner's `build_adapters` factory. They are
**closures over the same task-local live object** (§3.2), which is exactly the
brief's preferred shape: no frozen type is widened, and the four callables
cannot address different transports.

```python
dispatch_semantic_prompt(request: SemanticPromptRequest)  -> SemanticPromptDispatchObservation
observe_semantic_turn(request: SemanticTurnRequest)       -> SemanticTurnObservation
collect_broker_activity(session: RuntimeSession)          -> BrokerActivityObservation
collect_final_report_claims(session: RuntimeSession)      -> FinalReportClaimsObservation | None
```

Every type is **imported from the frozen `qualification.semantic_session`**.
LIVE1 declares no competing send/turn/activity/claims schema (matrix case 30).

No fifth semantic port is added. Two mechanically necessary internal helpers are
adapter-private and are **not** PRE1 authority surfaces: `_DispatchBaseline`
(§7.4) and the refusal-reason projector (§9.3).

---

## 7. Phase-1 dispatch algorithm (CDQ 2, 3, 4, 5)

### 7.1 Prompt content authority (CDQ 3)

`SemanticPromptRequest` carries `task_id`/`task_revision` and no prompt text, by
design. LIVE1 binds them as follows:

1. `LiveSemanticAdapters.__init__` takes the frozen `QualificationTask` **object**
   (`task=`), the same object `run_primary_sweep` iterates from
   `corpus.REQUIRED_TASKS` and hands to `build_adapters`.
2. At dispatch, before any write:

   ```text
   from qualification.corpus import TASKS_BY_ID
   TASKS_BY_ID.get(request.task_id) is self._task        # identity, not equality
   request.task_revision == self._task.task_revision     # exact string
   request.task_id       == self._task.task_id
   ```

   The identity check is the **identical** check
   `run_semantic_task_attempt` already applies to its own `task` argument, so a
   caller-constructed or substituted `QualificationTask` is refused twice.
3. The transmitted text is `self._task.prompt` — i.e.
   `task.case.prompt`, a frozen corpus value, read at the write site.

**There is no prompt parameter anywhere.** `LiveSemanticAdapters.__init__` has
no `prompt`, `message`, `text`, `instruction`, `prefix`, `suffix`, `preamble`,
`system`, or `template` parameter; `dispatch_semantic_prompt` has no second
argument; and the command dict is constructed inline at exactly one call site.
A caller therefore cannot substitute semantic prose (matrix case 17).

**A mismatched revision refuses before the write** (matrix case 18): the
mismatch returns `CONFIRMED_NOT_SENT` / `GATE_REFUSED_BEFORE_WRITE`, which is
mechanically true — `send_command` was never entered.

**No LIVE1 prompt contribution of any kind.** No continuation, no correction
prompt, no hidden prefix, no candidate-specific instruction, no convenience
suffix, no `streamingBehavior`, no `images`. Pi's own contribution — the
Pi-authored system prompt (§2.4) — is documented as Pi's, and is neither authored
nor suppressed by AIDO.

### 7.2 The exact command

```json
{"id": "<AIDO-owned id>", "type": "prompt", "message": "<task.prompt>"}
```

**Exactly three keys.** No `maxTokens`, no `max_tokens`, no `images`, no
`streamingBehavior`, no `thinkingLevel`. The frozen unlimited-output policy is
preserved by *omission*: `aido_requested_max_output_tokens = null` means AIDO
requested no cap — never `0`, `-1`, or "unlimited" (matrix cases 21, 39).

`id` allocation: a fixed literal `"s1"`, allocated by the transport once and
recorded in `prompt_command_id`. Justification for a fixed literal rather than a
nonce: AIDO issues exactly three commands on this child's stdin for the whole run
— `"h1"` (`get_commands`, inside `launch_runtime`), `"h2"` (`get_state`), and
this one — so `"s1"` is unambiguous by construction and deterministic for audit.
The adapter asserts `"s1" not in supervisor.activity.responses` before writing.

### 7.3 Preconditions, all evaluated BEFORE the write

Each failure below returns `CONFIRMED_NOT_SENT` / `GATE_REFUSED_BEFORE_WRITE` —
mechanically true, because `send_command` is not entered.

| # | Precondition | Source of the rule |
|---|---|---|
| P1 | the transport exists for exactly this `RuntimeSession` (all three ids), and is not `retired` | §3.2 rule 3 |
| P2 | `dispatch_completed` is `False` — one dispatch per transport, ever | §9 of the qualification design; one-shot budget |
| P3 | task identity/revision bind (§7.1) | CDQ 3 |
| P4 | `self._task.prompt` does not start with `"/"` | PRE1 I-4; excludes all three of Pi's non-model `preflightResult(true)` branches that depend on a leading slash |
| P5 | `supervisor.stdin_write_error is None` | no prior write already failed |
| P6 | `"h1" in activity.responses and "h2" in activity.responses` | the single-writer discipline: both prior commands' waits terminated with a correlated response |
| P7 | `"s1" not in activity.responses` | the id is unused |
| P8 | `supervisor.process is not None and supervisor.process.poll() is None` | there is a live child to write to |

**Declared assumptions, recorded but NOT claimed as per-run Pi observations**
(PRE1 I-4): AIDO's one loaded extension registers no `input` handler and no
`before_agent_start` handler (asserted from the AIDO-owned frozen extension
source, whose SHA-256 `_require_authorized_extension_source` already pins), and
the session is not streaming (this is the first and only prompt of a fresh
session). LIVE1 adds **no `get_state` probe** to try to observe either — PRE1
§2.6 forbids it.

### 7.4 The baseline snapshot (`_DispatchBaseline`)

Captured immediately before the write, from public supervisor surfaces only:

```text
records_ingested        supervisor.stdout_state()["records_ingested"]
agent_loop_event_counts {k: activity.event_type_counts.get(k, 0) for k in _AGENT_LOOP_EVENT_TYPES}
unmatched_response_ids  len(activity.unmatched_response_ids)
agent_end_count         activity.agent_end_count
settled                 activity.settled
```

where

```text
_AGENT_LOOP_EVENT_TYPES = ("agent_start", "turn_start", "message_start",
                           "message_end", "turn_end", "tool_execution_start",
                           "tool_execution_end", "agent_end", "agent_settled")
```

This is the entire correlation state LIVE1 adds. It exists so that "an agent run
was observed" and "a parse failure was observed" are always **deltas since this
dispatch**, never absolute counts that an earlier phase could have produced.

*(At this point in a real run every baseline count is 0 — Category-B's h1/h2
handshake enters no agent loop, since `_runAgentPrompt` is the only path to
`agent.prompt`/`agent.continue` in RPC mode. The baseline is taken anyway, so
the binding is mechanical rather than argued.)*

### 7.5 The dispatch algorithm

```text
D0  preconditions P1..P8                     -> CONFIRMED_NOT_SENT / GATE_REFUSED_BEFORE_WRITE
D1  baseline = _DispatchBaseline.capture(supervisor)
D2  mark dispatch_completed = True           (before the write; a raised write
                                              must never leave the port re-enterable)
D3  try: supervisor.send_command({"id": "s1", "type": "prompt", "message": task.prompt})
    except Exception:
        -> SEND_STATE_INDETERMINATE / WRITE_FAILED_TRANSMISSION_UNKNOWN
D4  outcome, response = supervisor.await_response("s1",
                            timeout_seconds=bounds.startup_deadline_seconds)
D5  classify (below)
```

**D5, in this exact order:**

```text
A. CORRELATED RESPONSE PRESENT
   if outcome == RUNTIME_RESPONSE_RECEIVED and is_dict(response)
      and response.get("type")    == "response"
      and response.get("command") == "prompt"
      and response.get("id")      == "s1":

        success = response.get("success")
        if type(success) is bool and success is True:
              if agent_loop_delta > 0 or delta == 0:   # both consistent
                  -> CONFIRMED_SENT / PROMPT_RESPONSE_ACCEPTED
        if type(success) is bool and success is False:
              if agent_loop_delta > 0:                 # CONTRADICTION
                  -> raise LiveSemanticAdapterError    # -> ADAPTER_RAISED / INDETERMINATE
              -> CONFIRMED_NOT_SENT / PROMPT_RESPONSE_REFUSED
        otherwise (missing / non-bool success):
              fall through to B..E   # never a determinate state from a malformed body

B. AGENT RUN OBSERVED (the correlated response was missed)
   if agent_loop_delta > 0:
        -> CONFIRMED_SENT / AGENT_RUN_OBSERVED

C. UNPARSEABLE COMMAND REFUSED  (all six conditions; see 7.6)
   if unparseable_refusal_established():
        -> CONFIRMED_NOT_SENT / COMMAND_UNPARSEABLE_REFUSED

D. NO CORRELATED RESPONSE
   if outcome == RUNTIME_DEADLINE_EXPIRED:
        -> SEND_STATE_INDETERMINATE / NO_CORRELATED_RESPONSE_DEADLINE
   if outcome in (RUNTIME_PROTOCOL_VIOLATION, RUNTIME_OUTPUT_CAP_EXCEEDED,
                  RUNTIME_EVENT_CAP_EXCEEDED, RUNTIME_READ_ERROR,
                  RUNTIME_EXITED_EARLY):
        -> SEND_STATE_INDETERMINATE / NO_CORRELATED_RESPONSE_STREAM_TERMINAL

E. UNRECOGNIZED SUPERVISOR OUTCOME (fail closed)
   -> raise LiveSemanticAdapterError   # -> controller records ADAPTER_RAISED /
                                       #    SEND_STATE_INDETERMINATE
```

where `agent_loop_delta = sum(current[k] - baseline[k] for k in _AGENT_LOOP_EVENT_TYPES)`
computed after one `supervisor.stdout_state()` refresh (a `_wait` already
drained; the counts are current).

`outcome` is checked against the frozen positive allowlist
`_RECOGNIZED_AWAIT_RESPONSE_OUTCOMES` (already declared in
`i2b_live_adapters`), never against a negative list — the accepted `L1-FU2`
discipline.

**Why AGENT_RUN_OBSERVED is genuinely realizable, and how it binds to THIS
dispatch** (the brief asks this explicitly):

1. In RPC mode, `_runAgentPrompt` is the **only** path to
   `agent.prompt`/`agent.continue`, and it is reachable **only** from the real
   preflight-true branch of `AgentSession.prompt` (§2.1).
2. AIDO is the only writer to this child's stdin, and it has issued exactly
   `h1`, `h2` and `s1` on it, of which only `s1` is a `prompt`.
3. `_AGENT_LOOP_EVENT_TYPES` counts were captured on **this** supervisor
   immediately before **this** write (D1), so a positive delta is bounded to the
   window after the write.

Therefore any agent-loop record appearing after D3 on this session's stdout was
caused by AIDO's one `prompt` command. That is a mechanical binding to this
session and this dispatch, not an inference from prose. It is deliberately
*second* in the ordering: the correlated response remains the normal
send-authority seam, and `AGENT_RUN_OBSERVED` covers only the case where that
response was missed.

**No enum member is populated by invention.** All ten
`SemanticDispatchEvidenceCode` members are reachable from a real mechanical
fact; `COMMAND_UNPARSEABLE_REFUSED` is reachable only under §7.6's six
conditions and is expected to be unreachable in practice (§7.6.3), which is
recorded rather than papered over.

### 7.6 `COMMAND_UNPARSEABLE_REFUSED` — when it may truthfully be emitted (CDQ 5)

#### 7.6.1 The six conditions, all required

```text
U1  single writer:   AIDO owns the only handle to this child's stdin
                     (PiRpcSupervisor.process.stdin), and no other code writes.
U2  one at a time:   every previously issued command's wait had terminated
                     before the next was written -- P6 asserts h1 and h2 both
                     produced correlated responses, and s1 is the third and
                     last command AIDO will ever write on this child.
U3  the write returned:  send_command did not raise, so a complete payload
                     (JSON + LF) was handed to the OS pipe.
U4  a NEW id-less parse response appeared:
                     len(activity.unmatched_response_ids) > baseline.unmatched_response_ids
                     AND, confirming it, at least one record in
                     sanitized_events()[baseline.records_ingested:] satisfies
                         type == "response" and command == "parse"
                         and type(success) is bool and success is False
                         and "id" not in record
U5  no correlated prompt response for "s1" was observed.
U6  agent_loop_delta == 0.
```

Under U1+U2, the only line Pi could have failed to parse in this window is
AIDO's own dispatch line, so U4 establishes that **this** command was refused
before acceptance. `_absorb` does not retain the parse record in
`activity.responses` (it has no `str` id), which is why U4 must read
`sanitized_events()` — a public method — sliced from the baseline index. Only a
**count** is derived; no record, and specifically no `error` text, is retained.

#### 7.6.2 Why the id-less signal is unambiguous in 0.84.4

`error(undefined, "parse", …)` is the **only** id-less response
`rpc-mode.js` can emit (§2.3). The `default:` and `catch (commandError)` arms both
carry `command.id`. The `unmatched_response_ids` delta is used as a cheap
pre-filter; the record-shape scan is the authority.

#### 7.6.3 Where the code must NOT be emitted

- If U1 or U2 ever ceases to hold — any pipelined command, any second writer —
  **the code must be withdrawn, never weakened** (PRE1 §2.5). An offline test
  pins that the adapter never writes a command while a wait is outstanding
  (matrix case 20/43).
- A parse response present **before** the baseline establishes nothing about this
  dispatch (matrix case 32).
- If U4 holds but U5 or U6 does not, the situation is contradictory and the
  algorithm falls through to D/E rather than asserting a determinate state.

**Honest expectation:** AIDO serializes with `json.dumps(..., ensure_ascii=True)`,
so `JSON.parse` of AIDO's own line cannot fail. This code is expected to be
unreachable in practice. It is specified so that *if* it ever fires it is
truthful, not so that the enum looks fully exercised.

### 7.7 What the algorithm never does

Never treats "the function returned" or "the write succeeded" as `CONFIRMED_SENT`
(invariant I-2). Never converts an exception into a determinate state. Never
issues `abort`, `abort_retry`, `clear_queue`, `steer`, `follow_up`, `compact`,
`set_model`, `new_session`, or `bash`. Never re-dispatches, backs off, polls,
reconnects, or streams for progress inference. Never adds a fourth dispatch
state.

---

## 8. Phase-2 turn observation algorithm (CDQ 6)

### 8.1 Preconditions

```text
T1  the transport exists for exactly this RuntimeSession (all three ids), not retired
T2  turn_observed is False (one observation per transport)
T3  request.dispatch IS the exact object this adapter returned in phase 1
    (identity `is`, plus full field equality as defence in depth)
T4  request.task_id / task_revision bind to self._task, as in 7.1
```

Any failure **raises** `LiveSemanticAdapterError`. LIVE1 deliberately does not
mint an observation for a session it does not own; the frozen controller then
synthesises
`SemanticTurnObservation(runtime_session_id=<its own>, turn_outcome=OBSERVATION_FAILED)`
itself, which is the truthful record and — critically — leaves
`semantic_prompts_sent = 1` untouched.

*(The frozen `SemanticTurnRequest.__post_init__` has already refused
construction unless `request.dispatch.dispatch_state is CONFIRMED_SENT` and the
dispatch answers this same run/session/task, so T3/T4 are defence in depth on
top of a type-level guarantee.)*

### 8.2 The algorithm

```text
S1  outcome = supervisor.await_settled(timeout_seconds=bounds.turn_deadline_seconds)
S2  agent_end_observed = supervisor.activity.agent_end_count > 0
S3  map outcome, using a POSITIVE allowlist:
        RUNTIME_SETTLED              -> SETTLED
        RUNTIME_DEADLINE_EXPIRED     -> DEADLINE_REACHED
        RUNTIME_PROTOCOL_VIOLATION   -> OBSERVATION_FAILED
        RUNTIME_OUTPUT_CAP_EXCEEDED  -> OBSERVATION_FAILED
        RUNTIME_EVENT_CAP_EXCEEDED   -> OBSERVATION_FAILED
        RUNTIME_READ_ERROR           -> OBSERVATION_FAILED
        RUNTIME_EXITED_EARLY         -> OBSERVATION_FAILED
        anything else                -> OBSERVATION_FAILED   (fail closed)
S4  mark turn_observed = True
S5  return SemanticTurnObservation(runtime_session_id=<this transport's>,
                                   turn_outcome=..., agent_end_observed=...)
```

### 8.3 Every case the brief enumerates

| Case | Handling | Why it is correct at source |
|---|---|---|
| `agent_end` before `agent_settled` | `await_settled` keeps waiting; `agent_end_observed=True` is reported independently | `_wait`'s `satisfied` is `lambda: activity.settled`, which only `agent_settled` sets |
| repeated `agent_end` | `agent_end_count` increments; never settles | same |
| retry-signalling `agent_end` (`willRetry`) | `agent_end_will_retry_count` increments; never settles | `_absorb` reads `willRetry` separately |
| records already buffered by phase 1 | already folded into `activity`; `await_settled`'s first drain sees them | §4.1 |
| malformed record | terminal `protocol_violation` in `RecordStreamReader` → `OBSERVATION_FAILED` | `decode_record` raises `ProtocolViolation`, the reader records it and returns |
| protocol violation | `RUNTIME_PROTOCOL_VIOLATION` → `OBSERVATION_FAILED` | `_terminal_stream_outcome` |
| output cap | `RUNTIME_OUTPUT_CAP_EXCEEDED` → `OBSERVATION_FAILED` | same |
| event cap | `RUNTIME_EVENT_CAP_EXCEEDED` → `OBSERVATION_FAILED` | same |
| read error | `RUNTIME_READ_ERROR` → `OBSERVATION_FAILED` | same |
| early runtime exit | `RUNTIME_EXITED_EARLY` → `OBSERVATION_FAILED`, **after** `_wait`'s final flush-and-recheck | `_wait`'s `process.poll()` branch waits up to 1 s on `finished` and re-drains, so a settle that arrived just before exit still wins |
| AIDO monotonic deadline | `RUNTIME_DEADLINE_EXPIRED` → `DEADLINE_REACHED` | `deadline - time.monotonic()` |

### 8.4 The monotonicity guarantee

Phase 2 has **no way** to write `semantic_prompts_sent` or `dispatch_state`:

- `SemanticTurnObservation` has no dispatch field at all (PRE1-FU2 removed it);
- the controller sets `semantic_prompts_sent = 1` before entering phase 2, in the
  single place that statement exists, and every phase-2 failure path lands in
  `_GateFailure(TURN_COMPLETION, …)` — never `_DispatchIndeterminate`, which is
  raised only inside the phase-1 block;
- LIVE1's phase-2 port returns or raises; neither can reach phase 1's record.

So after `CONFIRMED_SENT`, any phase-2 outcome leaves the send fact permanently
`CONFIRMED_SENT` / `semantic_prompts_sent = 1` (matrix cases 12, 13).

> **`DEADLINE_REACHED` means AIDO stopped waiting.** Not that Pi stopped, not
> that the request was cancelled, not that inference stopped, not that any
> descendant stopped. LIVE1 adds no cancellation, no `abort` command, no kill,
> and no process-tree management.

---

## 9. Broker-activity derivation (CDQ 7)

### 9.1 The facts already exist in frozen AIDO-owned state

For the **same run**, from the `BrokerRequestHandler` this task's broker was
created with:

| `BrokerActivityObservation` field | Frozen source | Notes |
|---|---|---|
| `runtime_session_id` | the transport's own id | never the request's, echoed |
| `call_succeeded` | `True` unless the snapshot itself fails (§9.4) | |
| `read_operation_count` | `handler.run_state.consumed.read_operations` | monotone; "Consumption only. Never refilled" |
| `edit_operation_count` | `handler.run_state.consumed.edit_operations` | monotone |
| `edited_paths` | `frozenset(handler.run_state.mutated_paths)` | the broker's own accounting, never inferred from Git — which is what makes H-8's two-way cross-check meaningful |
| `refusals` | projected from `handler.diagnostics.refusal_reasons` (§9.3) | |

Same-run binding: the transport's `broker_session_id` must equal
`session.broker_session_id`, and the handler is the one bound at broker creation
for that exact session (§3.2). A foreign broker or a substituted session is
refused, and the port never reads a handler from another run (matrix case 15).

**No tool activity is inferred from model prose anywhere.**

### 9.2 Design finding — one required fact the frozen broker does not retain

`BrokerRequestHandler.handle_frame` calls
`diagnostics.refuse(request.operation, outcome.code, outcome.internal_reason)`
and **discards `OperationOutcome.relative_path`**. `BrokerDiagnostics` stores
`refused[f"{operation}:{code}"]` counts and
`refusal_reasons[f"{operation}:{code}:{internal_reason}"]` strings — no path.

**Consequence:** `RefusalEvent.path` cannot be populated and is recorded as
`None`, which is its frozen default and is truthful.

**Assessed impact: none on any gate.** `qualification.scope` never reads
`RefusalEvent.path`: `attribute_refusal`, `has_hard_disqualifier` and
`build_scope_result` (including `protected_write_attempts`,
`third_file_attempts`, `hard_refusal_count`, `soft_refusal_count`,
`refusal_categories`) are all functions of `reason_code` and
`is_third_distinct_implementation_file` only. This is therefore recorded as a
**design finding**, not a conflict, and **no duplicate authority path is
invented to recover the path**.

### 9.3 The refusal projection — through ONE qualification-owned boundary

FU1 changes this subsection. The pre-FU1 design passed the broker's own
`internal_reason` string into `RefusalEvent.reason_code` verbatim. §9.4 proves
that is wrong, so the projection now runs through a single deterministic
normalization boundary, specified in §9.4.3:

```text
for entry in handler.diagnostics.refusal_reasons:          # bounded by 9.5
    operation, err_code, internal_reason = entry.split(":", 2)
    normalized = project_broker_refusal_reason(                   # 9.4.3, TOTAL
        error_code=err_code, internal_reason=internal_reason,     # BOTH inputs
    )
    RefusalEvent(
        reason_code = normalized,
        path        = None,                                 # 9.2
        is_third_distinct_implementation_file =
            normalized == "changed_file_budget_exhausted",
        self_corrected = False,                             # 9.4.4 -- see below
    )
```

`split(":", 2)` (maxsplit 2) is required, not incidental: several frozen
`internal_reason` values themselves contain a colon —
`unsafe_lexical_form:<ExcName>`, `canonical_guard:<ExcName>`, `path_policy:<msg>`
— and a naive split would truncate them (matrix case 36).

**`is_third_distinct_implementation_file` is derived, not guessed.**
`ar2.capability.RunState.edit_budget_allows` returns
`"changed_file_budget_exhausted"` **only** when
`relative_path not in self.mutated_paths and len(self.mutated_paths) >= caps.max_changed_files_per_run`,
and `MAX_CHANGED_FILES_PER_RUN == 2`. So that code is emitted only for an attempt
on a **third distinct** path, which is exactly `scope.py`'s condition ("Refusing
a legitimate two-file task's own second slot is not this" — with a cap of 2 a
second slot is never refused). The implementation must pin this with an
assertion on `CapDefinitions.max_changed_files_per_run == 2` so a future cap
change breaks loudly rather than silently mis-attributing a hard disqualifier
(matrix case 37).

**`self_corrected` is left at its frozen default `False` and is never read as a
fact.** §9.4.4 proves the evidence for it does not exist, and §9.4.5 states the
policy consequence. LIVE1 never sets it `True`, and no LIVE1 or ranking code
may interpret the default `False` as an observation that the candidate failed
to self-correct.

### 9.4 R-2 evidence: a PRE-Q1 frozen-contract gap, in two parts

The pre-FU1 design recorded the vocabulary mismatch as a non-blocking
"finding for review". Independent review is right that this understates it.
Soft refusals are the **entire input** to frozen ranking tier **R-2**
(operation cleanliness), Q1 and Q2 are **primary one-shot runs**, and an
artifact written with the wrong vocabulary cannot be re-derived afterwards.
FU1 therefore reclassifies both parts as **pre-Q1 frozen-contract gaps** that
must be closed before any candidate semantic prompt is sent.

#### 9.4.1 Part A — the vocabulary does not match, and one code is unbounded

`qualification.scope.SOFT_REASON_CODES` declares
`{"not_in_mint_time_manifest", "stale_base", "no_unique_match", "over_cap_read"}`,
and `RefusalEvent`'s own module contract calls `reason_code` *"the exact code the
accepted broker/capability engine already produces"*. Cross-reading
`ar2.candidate` and `ar2.operations`, only `not_in_mint_time_manifest` is a
literal frozen `internal_reason`. The strings the broker actually emits for the
other three concepts are, verbatim:

```text
stale base      -> "presented_base_does_not_match_aido_receipt"
                   "on_disk_bytes_do_not_match_presented_base"
no unique match -> "empty_old_text"
                   "occurrence_count_<N>"          <-- parameterized by a count
over cap read   -> "per_file_read_cap"
                   "pre_image_over_cap"
                   "post_image_over_cap"
```

Two distinct defects follow, not one:

1. **Mis-attribution.** `attribute_refusal` falls through to
   `RefusalAttribution("infrastructure", False, False)` for an unrecognised
   code, so every one of those refusals is attributed to **AIDO's
   infrastructure** rather than recorded as a candidate **soft** signal.
   `ScopeResult.soft_refusal_count` would therefore read `0` on a run in which
   the candidate produced a stale base, a non-unique match and an over-cap read
   — and R-2 would bucket that run `CLEAN`. That is not a missing signal; it is
   an actively wrong one, and it is wrong in the direction that flatters the
   candidate.
2. **Unbounded artifact vocabulary.** `ScopeResult.refusal_categories` is
   `tuple(sorted({event.reason_code …}))` and is projected into the retained
   artifact. `occurrence_count_<N>` is parameterized by an integer the candidate
   influences, so passing it through verbatim would put a candidate-influenced,
   unbounded-cardinality token into evidence. Every other code in the
   qualification vocabulary is a closed literal.

#### 9.4.2 Why the fix belongs in the qualification layer, not in AR2

Source analysis of the three candidate locations:

| Location | Assessment |
|---|---|
| **Frozen `ar2.broker` / `ar2.operations` / `ar2.candidate`** — rename `internal_reason` values to the qualification vocabulary | **Refused.** These strings are AR2's own diagnostic vocabulary, deliberately more precise than qualification's four concepts (`stale_base` alone splits into a receipt mismatch and an on-disk mismatch, which are genuinely different findings). Renaming them would destroy diagnostic precision inside a frozen, adversarially-reviewed module to satisfy a consumer's taxonomy, and would break every AR2 test and artifact that names them. It is also strictly wider than necessary. |
| **Frozen `qualification.scope`** — extend `SOFT_REASON_CODES` with the literal broker strings | **Insufficient, and refused as the primary fix.** A `frozenset` cannot express `occurrence_count_<N>`, so the `no_unique_match` concept remains unreachable; and it leaves defect 2 (the unbounded artifact token) entirely unaddressed. |
| **A new qualification-owned projection module** | **Adopted.** It is the narrowest location that closes both defects, changes no frozen behaviour, and keeps the mapping in exactly one place. |

#### 9.4.3 The correction: ONE deterministic projection boundary

> **FU3 BLOCKER 2 correction.** FU2 specified the projection as
> `project_broker_refusal_reason(internal_reason: str) -> str` and claimed
> `occurrence_count_<N>` was *"the only parameterized reason the frozen broker
> emits"*. **Both are wrong at source**, and both are corrected here. There are
> **six** dynamic reason sources, two of which can carry candidate-influenced
> text into evidence; and the projection discarded the one input that is
> already bounded and frozen — the wire error code.

##### 9.4.3.1 Every dynamic `internal_reason` source in frozen AR2

Enumerated from source, not from memory:

| # | Site | Constructed reason | What the variable part is |
|---|---|---|---|
| 1 | `ar2/candidate.py:173` | `f"unsafe_lexical_form:{type(exc).__name__}"` | an exception **class name** |
| 2 | `ar2/candidate.py:191` | `f"canonical_guard:{type(exc).__name__}"` | an exception **class name** |
| 3 | `ar2/candidate.py:227` | `f"path_policy:{exc}"` | a `PathPolicyError` **message**, which may embed a repository-relative **path** |
| 4 | `ar2/operations.py:261` | `f"occurrence_count_{occurrences}"` | an **integer count** the candidate's own `old_text` determines |
| 5 | `ar2/broker.py:237` | `str(exc)` for a `WireProtocolError` | **arbitrary text derived from a candidate-authored wire frame** |
| 6 | `ar2/broker.py:296` | `type(exc).__name__` for a broker-internal exception | an exception **class name** |

*(A seventh f-string, `ar2/broker.py:567`'s `worker_error = f"{type(exc).__name__}: {exc}"`,
is **not** a refusal reason — it never reaches `diagnostics.refuse` — and is
listed only so the drift guard's authors do not mistake it for one.)*

Sources 3 and 5 are the serious ones. `ScopeResult.refusal_categories` is
projected verbatim into the retained `pi-implementer-qualification.v1` record,
so passing either through unmapped would put **candidate-influenced free text —
possibly a repository path — into retained evidence**, with unbounded
cardinality. That is an evidence-safety defect, not merely a taxonomy one, and
it is the strongest reason the fallback rule below is mandatory rather than
tidy.

##### 9.4.3.2 The bounded input FU2 was discarding

`BrokerDiagnostics.refuse(operation, code, reason)` stores
`f"{operation}:{code}:{reason}"`, and §9.3's projection already splits all
three. The middle field is a member of `ar2.wire.CLOSED_ERROR_SET` — a frozen,
closed set of **nine** literals:

```text
refused  too_large  not_text  stale_base  no_unique_match
budget_exhausted  protocol_error  unauthorized  internal_error

TERMINAL_ERROR_CODES = {protocol_error, unauthorized, internal_error}
```

Two of those literals — `stale_base` and `no_unique_match` — **are already two
of the four frozen qualification soft codes**, and `unauthorized` is already one
of the two protocol-anomaly codes. Throwing that field away and normalizing from
free-form diagnostic text was the wrong direction: the bounded field is the
better primary key.

It is not sufficient alone, which is why the projection needs **both**:
`too_large` covers `per_file_read_cap` and `pre_image_over_cap` (read-side,
`over_cap_read`) **and** `post_image_over_cap` (a write-side cap, not a read);
and `budget_exhausted` covers `changed_file_budget_exhausted` (a
candidate-attributable budget code that `scope.py` treats specially) alongside
four AIDO-side budget reasons that are not candidate signals.

##### 9.4.3.3 The corrected projection boundary

A separately-authorized correction phase — **`5F3B-LIVE1-C2` (refusal
vocabulary projection)**, landing **before** `5F3B-LIVE1-I1` — must add exactly
one new, qualification-owned module whose single public function is a **total,
deterministic, table-driven** projection over the **pair**:

```text
project_broker_refusal_reason(
    *,
    error_code: str,          # a member of ar2.wire.CLOSED_ERROR_SET
    internal_reason: str,     # the free-form AR2 diagnostic
) -> str                      # a member of ONE closed qualification vocabulary
```

The exact syntax is C2's to choose; the **properties** below are locked.

```text
C2-P1  Total and closed.     Every return value is a member of ONE declared,
                             closed vocabulary: the four scope soft codes, the
                             two hard-disqualifier codes, the budget code, the
                             two protocol-anomaly codes, and exactly one
                             explicit `unrecognized_broker_reason` fallback.
                             No return value is ever parameterized, formatted,
                             interpolated, or derived from the CONTENT of
                             either input string. The function is total over
                             (any str, any str).

C2-P2  Explicit pair table.  Mapping is by an explicit table keyed on
                             (error_code, internal_reason) literals, plus
                             exactly ONE narrowly-anchored shape rule:
                             `occurrence_count_` followed by a BOUNDED
                             non-negative integer spelling, and only under
                             error_code == no_unique_match.

                             CORRECTED (FU3): occurrence_count_ is NOT the only
                             dynamic reason source -- Sec. 9.4.3.1 lists six.
                             It is the only one given a shape rule; all other
                             dynamic families are handled by C2-P3a.

                             No regex over the general reason space, no
                             substring heuristic, no fuzzy match, no prefix
                             matching outside the one anchored rule above, and
                             no "contains the word cap" style inference.

C2-P3  Never guesses upward. An unmapped pair returns
                             `unrecognized_broker_reason`, which
                             `scope.attribute_refusal` already classifies as
                             `infrastructure` through its existing fall-through.
                             It is NEVER mapped to a soft signal, a hard
                             disqualifier, or a protocol anomaly to "be safe".

C2-P3a Dynamic families      unsafe_lexical_form:<...>, canonical_guard:<...>,
       are REDUCED, never    path_policy:<...>, WireProtocolError str(exc)
       passed through.       text, and exception-class diagnostics NEVER enter
                             evidence verbatim, in whole or in part. Unless a
                             specific policy meaning is independently justified
                             and separately reviewed, each reduces to the one
                             fixed `unrecognized_broker_reason`.

                             NO candidate- or runtime-controlled substring --
                             no path, no exception message, no wire text, no
                             count -- may reach RefusalEvent.reason_code,
                             ScopeResult.refusal_categories, or any retained
                             artifact field.

C2-P4  Bounded-code rules,   Where the FROZEN broker semantics establish the
       stated mechanically.  shape, the bounded error_code alone decides:
                               unauthorized      -> `unauthorized`
                               protocol_error    -> `protocol_terminal`
                             In `ar2.broker.handle_frame` every
                             ERR_PROTOCOL_ERROR refusal either already sits
                             behind `run_state.mark_terminal(TERMINAL_PROTOCOL)`
                             or reports an already-terminal capability, and
                             ERR_UNAUTHORIZED always marks
                             TERMINAL_UNAUTHORIZED -- so both projections are
                             read off frozen behaviour, not asserted. This is
                             exactly why source 5's `str(exc)` text is never
                             needed: the code carries the meaning, the text
                             carries only risk.

                             Where the code alone is ambiguous, the PAIR
                             decides: too_large splits between over_cap_read
                             (per_file_read_cap, pre_image_over_cap) and the
                             write-side post_image_over_cap;
                             budget_exhausted splits between
                             changed_file_budget_exhausted and the AIDO-side
                             budget reasons; refused carries both hard
                             disqualifiers, not_in_mint_time_manifest, and the
                             dynamic families of C2-P3a.

C2-P5  One call site.        The projection is called from exactly one place --
                             the semantic adapter's refusal projection (Sec 9.3).
                             No other module maps, renames, or reinterprets a
                             refusal reason, and `LiveSemanticAdapters` contains
                             no mapping table of its own.

C2-P6  Drift guard over      An offline test extracts, from frozen
       BOTH literal AND      `ar2.candidate`, `ar2.operations` and `ar2.broker`:
       DYNAMIC sources.        (a) every LITERAL string passed as an
                                   internal_reason / diagnostics.refuse reason
                                   argument, and
                               (b) every DYNAMIC construction site for that
                                   argument -- an ast.JoinedStr (f-string), a
                                   Call such as str(...) or type(...).__name__,
                                   a Name, or any non-Constant expression --
                                   together with the enclosing error_code where
                                   it is statically determinable.

                             It then asserts:
                               - every literal is present in the pair table;
                               - the set of DYNAMIC sites equals an explicitly
                                 enumerated, reviewed inventory (Sec. 9.4.3.1),
                                 by site and by shape.

                             CORRECTED (FU3): a literal-only guard, which is
                             what FU2 specified, would let a NEWLY ADDED
                             f-string / str(exc) / exception-derived reason
                             escape the table silently. Adding a dynamic reason
                             source in frozen AR2 must break the offline suite
                             LOUDLY, exactly as adding a literal one does.

C2-P7  ar2 is NOT reopened.  The guard READS frozen AR2 source; it never edits
                             it. AR2 keeps its own, more precise diagnostic
                             vocabulary -- the reduction happens entirely on
                             the qualification side, at this one boundary.

C2-P8  No frozen behaviour   `scope.attribute_refusal`,
       change.               `scope.build_scope_result`, `SOFT_REASON_CODES`,
                             `HARD_DISQUALIFIER_REASON_CODES`,
                             `PROTOCOL_ANOMALY_REASON_CODES` and
                             `RefusalEvent`'s field set are all UNCHANGED. The
                             only edit to `qualification.scope` is a DOC-ONLY
                             correction of the now-inaccurate sentence calling
                             `reason_code` "the exact code the broker produces",
                             which after C2 is the projected qualification code.
```

The hard-disqualifier and budget codes
(`verification_witness_is_never_writable`,
`protected_path_is_readable_not_writable`, `changed_file_budget_exhausted`) are
byte-identical between the two vocabularies, so for them the projection is the
identity under `error_code == refused` / `budget_exhausted` — which the table
states explicitly rather than by omission.

> **§9.3 changes shape accordingly.** Its projection loop already computes
> `operation, err_code, internal_reason = entry.split(":", 2)`; under C2 it
> passes **both** `err_code` and `internal_reason` to the projection instead of
> discarding the first. Nothing else in §9.3 moves, and `split(":", 2)` remains
> required for the reasons §9.3 already gives.

#### 9.4.4 Part B — the R-2 operation SEQUENCE is not observable at source

Frozen R-2 distinguishes `MINOR_FRICTION` from `REPEATED_FRICTION` by whether
each soft refusal was *"visibly self-corrected on the candidate's very next
relevant operation"*. Establishing that requires the **complete, ordered,
interleaved accepted-and-refused operation sequence, with paths**. AIDO does not
have it, and this was verified at source rather than assumed:

| Needed | What the frozen broker retains | Verdict |
|---|---|---|
| ordered accepted operations | `BrokerDiagnostics.accept()` does `accepted[operation] = accepted.get(operation, 0) + 1` — a **count per operation class**, with no index, no timestamp, no path | **absent** |
| ordered refused operations | `refusal_reasons: list[str]`, appended in order — ordered **among refusals only** | present, partial |
| interleaving of the two | nothing correlates the accept counter with a position in the refusal list | **absent** |
| the path of each event | `handle_frame` calls `diagnostics.refuse(operation, code, internal_reason)` and **discards `OperationOutcome.relative_path`** (§9.2) | **absent** |
| an ordered per-operation log elsewhere | `RunState` holds `read_receipts` (dict), `mutated_paths` (ordered, but only distinct **successfully edited** paths), `seen_request_ids` (a set), `consumed` (counters) | **absent** |

There is **no narrower qualification-layer solution** for this half: the
qualification package can only project what the frozen broker retained, and the
sequence was never retained. The smallest evidence that *is* mechanically
sufficient, from the surfaces above, is exactly:

```text
E1  the soft-refusal COUNT                  (after C2's projection)
E2  the ORDERED SEQUENCE OF SOFT-REFUSAL SHAPES, and therefore whether any
    projected soft code RECURS                (refusal_reasons is ordered)
E3  the total refusal count and its distribution across operation classes
```

`E1`–`E3` are enough to establish `CLEAN` (zero soft refusals) and enough to
establish `REPEATED_FRICTION`'s **first** disjunct (a soft shape recurs). They
are **not** enough to establish "each was visibly self-corrected", which is
`MINOR_FRICTION`'s defining condition, and they are not enough to establish
`REPEATED_FRICTION`'s "are not self-corrected" disjunct either. The middle of
the R-2 scale is therefore currently unestablishable in **both** directions.

#### 9.4.5 The minimum FAIR correction for Part B — a policy revision

Two options were considered. **Option 1 is ADOPTED and its thresholds are
frozen by FU2**; Option 2 is refused explicitly.

- **Option 1 (ADOPTED, and now FROZEN — FU2) — define R-2 over evidence AIDO
  can actually establish.** FU1 left the numeric threshold open. FU2 closes it.
  For this qualification-policy revision R-2 is defined **exactly** as:

  ```text
  Let N = the CANDIDATE-LEVEL total of projected soft refusals, summed over
          that candidate's three primary tasks (Sec. 9.4.6 derives it from
          retained evidence).
  Let R = TRUE iff at least one projected soft reason code occurs MORE THAN
          ONCE across those same three tasks.

  CLEAN              N == 0
  MINOR_FRICTION     N in {1, 2}  AND  R is FALSE
  REPEATED_FRICTION  R is TRUE    OR   N >= 3
  ```

  Totality and disjointness: the three arms partition every `(N, R)` pair.
  `N == 0` forces `R` false, so `CLEAN` cannot collide with `REPEATED_FRICTION`;
  `N in {1,2}` splits on `R`; `N >= 3` is `REPEATED_FRICTION` regardless of `R`.

  **This is a NEW pre-run qualification-policy DEFINITION. It is not a recovered
  observation of "self-correction".** The frozen wording — *"each visibly
  self-corrected on the candidate's very next relevant operation"* — is
  **replaced for this revision**, because §9.4.4 proves at source that the
  ordered, interleaved, path-carrying operation sequence it requires does not
  exist anywhere in the frozen broker. Non-recurrence is a **strictly weaker
  proxy**, and the revision must say so in exactly those terms rather than
  implying the original criterion was measured.

  **Why these numbers, honestly.** There is **no stronger predeclared basis in
  source**, and FU2 looked for one: `ar2.capability`'s caps bound operations
  (`max_read_operations_per_run=32`, `max_edit_operations_per_run=16`,
  `max_changed_files_per_run=2`), never refusals; and the qualification design's
  §11.3 **deliberately fixes no numeric threshold at all**, on the stated
  grounds that inventing one would *"manufacture false precision"*. So `{1,2}`
  versus `>= 3` is a **policy choice**, declared in advance, not a derived
  quantity — and it is recorded as such rather than dressed up as one.

  **Why this does not violate §11.3's no-numbers rule.** §11.3 forbids AIDO
  inventing a threshold for *stall classification*, which is an outcome
  classification feeding `RUNTIME_STALLED` and therefore the hard bar. R-2 is a
  **ranking bucket among candidates that have already cleared the hard bar**:
  `soft_refusal_count` feeds ranking only, never H-1..H-14, never
  `run_validity`, never `scoring_eligible`, and never an
  `AutonomousClassification`. A predeclared ranking threshold and a forbidden
  classification threshold are different objects, and this design does not
  quietly convert one into the other. R-2's third frozen disjunct — *"the count
  is large enough to itself feed the §11.3 no-progress pattern"* — is
  **dropped**, not given a number, because §11.3 supplies none.

  **Scope is candidate-level, stated to remove the ambiguity.** Frozen R-2 reads
  *"over all three tasks' broker-recorded activity"*, so both `N` and `R` are
  computed across the candidate's three tasks, not per task. A code appearing
  once in each of two different tasks therefore **recurs**.

- **Option 2 (NOT recommended) — add an ordered operation log to the frozen
  broker.** It would make the original criterion establishable, but it reopens
  an adversarially-reviewed frozen module, it requires retaining
  **repository-relative paths** per event (new retained evidence, new scrub
  surface, and the exact fact §9.2 currently records as deliberately discarded),
  and it grows a per-frame audit log inside the one component whose smallness is
  a security property. It is recorded so it is refused explicitly rather than by
  omission; a future phase may revisit it under its own authorization.

The adopted definition is **fair by construction**: it is declared before Q1,
applies identically to Candidate A and Candidate B, is computed from the same
frozen corpus over the same code path (§15), and is carried by `5F3B-LIVE1-C3`
into the qualification design's own §18 so it is policy, not harness behaviour.

#### 9.4.6 The retained evidence IS sufficient — proof (FU2 item 5)

The revised R-2 must be computable from **retained primary evidence alone**,
after the fact, with no broker event log and without re-running Q1 or Q2.
It is. Source chain, verified end to end:

```text
BrokerDiagnostics.refusal_reasons          (ordered list, per task, in-run)
        |  Sec. 9.3 projection, C2 vocabulary
        v
tuple[RefusalEvent, ...]                   (per task, in-run)
        |  scope.build_scope_result
        v
ScopeResult.soft_refusal_count     : int
ScopeResult.refusal_categories     : tuple[str, ...]   -- sorted, DEDUPED
        |  semantic_controller._project_scope_result
        v
{"soft_refusal_count": ..., "refusal_categories": [...]}
        |  records.build_qualification_record(scope_result=...)
        v
RETAINED  pi-implementer-qualification.v1  ->  emit_or_refuse -> results/*.json
```

Both fields are already declared fields of the frozen primary qualification
record. **R-2 itself needs no additional field**: the revised buckets are
computable from what the record already carries, so no R-2-specific schema
change and no sweep-level artifact is required (§12.7 stays intact).

> **Scoped precisely (FU4A).** This is a statement about R-2's own evidence
> needs, **not** a claim that no schema change is required overall. `C4`
> independently bumps the artifact lineage to `.v2` for **policy provenance**
> (§10A.2b) — a different fact, for a different reason. Both are true at once:
> R-2 adds no field, and the record still gains
> `qualification_policy_revision`.

**Deriving `N`.** For task *t*, `n_t` = that record's `soft_refusal_count`.
`N = n_1 + n_2 + n_3`. Direct.

**Deriving `R` — the part that is not obvious.** `refusal_categories` is
`tuple(sorted({event.reason_code …}))`, i.e. **deduplicated**, so it does *not*
carry multiplicity. Recurrence is nevertheless exactly recoverable:

```text
S_t = refusal_categories(t)  INTERSECT  scope.SOFT_REASON_CODES
        the DISTINCT projected soft codes present in task t
U   = S_1  UNION  S_2  UNION  S_3
        the DISTINCT projected soft codes across the candidate's sweep

CLAIM:      R  is TRUE   <=>   N > |U|

PROOF:      Let c(x) be the total number of times projected soft code x occurs
            across the three tasks. Every x in U has c(x) >= 1 by construction,
            and no soft-refusal event carries a code outside U, so
                N = SUM over x in U of c(x)      and therefore     N >= |U|,
            with equality exactly when c(x) == 1 for every x in U.
            Hence  N > |U|  <=>  some x has c(x) >= 2  <=>  R.            QED
```

Two consistency facts this relies on, both mechanical:

1. `attribute_refusal` marks `is_soft_signal` for exactly the codes in
   `SOFT_REASON_CODES`, and `soft_refusal_count` counts exactly those events —
   so `n_t` and `S_t` are computed over the *same* set of events.
2. After C2 every `reason_code` is a member of the closed projected vocabulary
   (§9.4.3 C2-P1), so `refusal_categories` contains no parameterized or unknown
   token that could inflate `|U|`.

**Ordering is not needed, and that is the point.** The revised R-2 asks a
*multiplicity* question ("does any soft code occur twice?"), not a *sequence*
question ("was it corrected next?"). Multiplicity survives into retained
evidence; sequence does not. That asymmetry is precisely why the narrowing in
§9.4.5 is implementable and the original wording is not.

**Which records carry it.** A candidate only reaches ranking at
`AUTONOMOUS_QUALIFIED`, which requires all three tasks `VALID` and
scoring-eligible; every such task emits the full
`pi-implementer-qualification.v1` record above. The reduced
`build_attempt_record` path is reached **only** for an indeterminate dispatch,
which can never be part of a ranked sweep. So the evidence R-2 needs is present
in exactly the runs where R-2 is defined.

> **Nothing is missing, so nothing new is proposed.** Had `refusal_categories`
> and `soft_refusal_count` not jointly determined `R`, the honest answer would
> have been to STOP and report the missing retained fact — not to add an
> artifact or a schema field. They do, so no evidence surface changes.

#### 9.4.7 Why this cannot be deferred until after Q1/Q2

Q1 and Q2 are **primary, one-shot** runs. `emit_evidence_or_refuse` writes each
task's artifact exclusive-create, and `RefusalEvent`s are constructed inside the
run from broker state that does not survive it. A projection defect discovered
after the artifacts exist cannot be repaired by re-deriving from the artifact,
because the artifact would already contain the mis-attributed vocabulary — and
re-running a candidate to obtain corrected evidence is precisely what the
one-shot policy forbids. C2 and the R-2 policy revision must therefore land
**before** the first candidate semantic prompt. The revised R-2 buckets
themselves are computable later from retained evidence (§9.4.6) — but only if
C2's projection ran *during* the run, because the projection is what makes
`soft_refusal_count` and `refusal_categories` mean what §9.4.6 assumes.

`LIVE1-DESIGN` itself changes nothing here: `scope.py` and every `ar2` module
remain untouched by LIVE1, and this subsection is a specification for C2 plus a
policy-revision recommendation for review, not an implementation.

#### 9.4.8 R-2 must be DERIVED by AIDO, not supplied by a caller (FU3 BLOCKER 3)

§9.4.5 froze the R-2 thresholds and §9.4.6 proved the evidence retains enough to
compute them. Neither made them **binding**, and independent review is right
that this is a defect rather than a documentation gap.

##### The source truth

```python
# qualification/ranking.py, frozen
@dataclass(frozen=True)
class RankingInput:
    ...
    r2_bucket: OperationBucket          # <-- CALLER-AUTHORED, validated by nothing

def build_profile(candidate, hard_bar_state, ranking_input):
    ...
    return CandidateRankingProfile(..., r2=ranking_input.r2_bucket, ...)
```

`build_profile` **copies** the caller's bucket straight into the profile.
`RankingInput` has no `__post_init__` at all. So today a caller may hand in
`OperationBucket.CLEAN` while the candidate's three retained artifacts say
`N >= 3`, and every downstream comparison would honour it. The frozen thresholds
would be **documentation only** — a policy nobody enforces — which is precisely
the shape this project treats as a defect elsewhere (`PrimarySweepResult` was
corrected the same way in `5F3B-Q1-PRE1-FU2A`, when review proved a caller could
pair genuine `task_results` with a fabricated `HardBarResult`).

##### The rule

```text
C3-R2-1  POLICY MATH AND EVIDENCE AUTHORITY ARE SEPARATE (FU4 item 3).
         Deriving a bucket deterministically from CALLER-AUTHORED primitive
         counts does not close the authority problem -- it moves the
         fabrication point from the bucket to the counts. FU3's "RankingInput
         carries primitive evidence" was therefore necessary but NOT
         sufficient, and is corrected here into two separate obligations:

             A. POLICY MATH -- C3 owns exactly ONE pure, deterministic R-2
                resolver implementing the frozen Sec. 9.4.5 arithmetic and the
                malformed-evidence checks of C3-R2-4. It is a pure function of
                its input, it reads no file, it opens no path, and it is the
                only implementation of that arithmetic in the repository.

             B. EVIDENCE AUTHORITY -- the AUTHORITATIVE input to that resolver
                comes from an AIDO-OWNED SOURCE, never from loose caller-
                supplied ints and tuples. See C3-R2-1a (in-process) and
                C3-R2-1b (cross-process).

C3-R2-1a WHAT THE FROZEN OBJECT GRAPH DOES AND DOES NOT PROVE -- CORRECTED
         (FU4A item 4). An earlier revision called the whole sweep graph
         "already unforgeable" and concluded C3 had complete in-process ranking
         authority from that fact. **That overclaimed, and it is withdrawn.**

         WHAT IS TRUE, per task, at source:

           - `SemanticTaskAttemptResult` is a ONE-SHOT, valid-by-construction
             authority object. Its `__post_init__` calls
             `_consume_pending_attempt_authority`, which pops a pending
             issuance registered by `run_semantic_task_attempt` itself and
             deletes it in the SAME atomic step whether or not the match
             succeeds. Its own error text states the consequence exactly: the
             issuance "can back at most ONE construction, ever, INCLUDING a
             dataclasses.replace() that touches only an unrelated field."
             So a genuine result cannot be copied-with-edits at all, and its
             `scope_result` cannot be swapped.
           - `_AttemptIdentityProvenance` refuses every construction through
             its own public constructor, so the identity cannot be minted.
           - `PrimarySweepResult.__post_init__` already requires
             `type(result) is SemanticTaskAttemptResult` for every entry, binds
             each entry's candidate/model to the sweep's, enforces the exact
             frozen task prefix, re-derives the hard bar from those same
             entries, and wraps the mapping in a `MappingProxyType` copy.

         WHAT IS NOT TRUE, at the AGGREGATE level:

           - `PrimarySweepResult` is a PUBLIC, CONSTRUCTIBLE frozen dataclass.
             Its `__post_init__` consumes NO issuance token. It establishes
             CONSISTENCY and post-construction IMMUTABILITY -- exact entry
             types, candidate/model binding, the frozen task prefix, the
             at-most-one-indeterminate rule, a re-derived hard bar, and a
             copied `MappingProxyType` -- but it does NOT prove that THIS
             aggregate was issued by `run_primary_sweep`.
           - So a caller holding three genuine `SemanticTaskAttemptResult`
             objects can compose a NEW, internally consistent
             `PrimarySweepResult` -- for example one mixing tasks from two
             different sweeps of the same candidate. Every per-task fact in it
             is genuine; the AGGREGATE is not attested.

         Therefore: each task result is issuance-backed and its `scope_result`
         cannot be swapped, and that is enough to make C3's POLICY MECHANICS
         well-defined. It is NOT enough to make an in-memory
         `CandidateRankingProfile` a durable candidate-SELECTION authority, and
         this design no longer says it is. **`semantic_sweep` is NOT reopened
         and no sweep issuance token is invented here** -- the smaller authority
         split of C3-R2-1c is used instead.

C3-R2-1b CROSS-PROCESS AUTHORITY IS M4'S, NOT C3'S. For a later, separate
         process (M4) that has only the retained artifacts, the M4 decision
         phase MUST independently LOAD, VALIDATE and HASH the immutable per-task
         artifacts and construct a verified ranking-evidence object BEFORE
         invoking C3's policy mechanics. C3 does not read files, does not accept
         a path from a caller, and does not learn to.

         DO NOT build a generic evidence/provenance framework now. That object
         is M4's to design, under M4's authorization.

C3-R2-1c THE AUTHORITY SPLIT, STATED ONCE (FU4A).

         C3 OWNS POLICY MECHANICS ONLY:
             the one R-2 resolver and its arithmetic
             malformed-input checks (C3-R2-4)
             R-3's symmetric rule (Sec. 10.6.2a)
             policy-revision comparison refusal (Sec. 10A.3)
             the categorical R-1..R-4 comparison mechanics
         C3's in-memory profiles are NOT a durable candidate-selection
         authority, and C3 emits nothing durable.

         M4 OWNS ALL AUTHORITATIVE RANKING-INPUT DERIVATION AND SELECTION:
             load the durable per-task artifacts
             schema-validate them
             verify immutable artifact identities and content digests
             verify same candidate / task set / model / route / policy revision
             derive the authoritative R-1, R-2, R-3-policy-state and R-4 inputs
             invoke C3's policy mechanics
             issue the candidate-level decision artifact (Sec. 10A.4)

         This also disposes of an adjacent source fact FU4 did not address:
         `RankingInput` today ALSO accepts caller-authored `r1_bucket` and the
         four R-4-related booleans (`all_tasks_autonomous_pass`,
         `any_runtime_timeout_or_stalled_or_premature_settle`,
         `any_operator_continuation`, `any_automatic_retry`, plus
         `near_stall_evidence`). C3 removing the caller-authored `r2_bucket` and
         centralizing the R-2 math is correct and stays -- but it does NOT make
         the remaining tiers authoritative, and this design does not claim it
         does. Deriving R-1 and R-4 authoritatively is M4's work, at the same
         boundary and by the same rule.

         M4 REMAINS THE FIRST AUTHORITATIVE SELECTION BOUNDARY.

C3-R2-2  NO AUTHORITATIVE PROFILE FROM FREELY AUTHORED PRIMITIVES. There is no
         supported path by which a caller supplies the authoritative R-2 bucket,
         and none by which an AUTHORITATIVE `CandidateRankingProfile` is created
         solely from freely authored counts and categories.

         If `RankingInput` remains public at all, that constraint is the
         binding one: a profile built from loose primitives is not authoritative
         and must not be presentable as one -- whether C3 achieves that by
         requiring the sweep/attempt objects, by an AIDO-minted sealed evidence
         type in the accepted `_AttemptIdentityProvenance` /
         `IssuedRuntimeIdentity` lineage, or by another narrow mechanism, is
         C3's design choice. What is locked is the property, not the shape.

         If -- and only if -- C3 finds that preserving a supplied `r2_bucket`
         field is materially simpler, `build_profile` MUST independently
         recompute the bucket from the authoritative evidence and REFUSE any
         mismatch. It may never merely trust it, and never silently repair it.

C3-R2-3  DERIVATION IS THE FROZEN DEFINITION, ONCE. N and recurrence are
         computed exactly as Sec. 9.4.5 defines and Sec. 9.4.6 proves:
             N = n_1 + n_2 + n_3
             S_t = refusal_categories(t) INTERSECT scope.SOFT_REASON_CODES
             U = S_1 UNION S_2 UNION S_3
             R = (N > |U|)
             CLEAN iff N == 0; MINOR_FRICTION iff N in {1,2} and not R;
             REPEATED_FRICTION iff R or N >= 3
         There is exactly ONE implementation of this arithmetic in the
         repository. Nothing recomputes it a second way.

C3-R2-4  MALFORMED EVIDENCE REFUSES, NEVER COERCES. Each of the following is a
         loud, typed refusal out of the ranking boundary, never a default
         bucket and never a truthiness read:
             - a count that is not exactly an int (a bool is not an int here)
             - a negative count
             - a task set that is not exactly the three frozen REQUIRED_TASKS
             - a `refusal_categories` entry outside C2's closed vocabulary
             - a task whose `scope_result` is None while it is nonetheless
               presented as VALID and scoring-eligible
             - INTERNAL IMPOSSIBILITY: n_t < |S_t|. Sec. 9.4.6's proof relies on
               n_t >= |S_t| (a code present in task t occurred at least once in
               task t); evidence violating it is not an unknown, it is
               incoherent, and it is refused rather than normalised.

C3-R2-5  EVIDENCE IS READ, NOT AUTHORED. The primitive values are the ones the
         retained qualification artifacts already carry (Sec. 9.4.6's chain) and
         the ones the in-process `ScopeResult` already holds. C3 introduces no
         new artifact, no new record field, no new record version and no
         candidate-level artifact. Sec. 12.7's refusal of a sweep-level artifact
         is unaffected, and the policy-revision field and the `.v2` bumps are
         C4's, not C3's (Sec. 10A.2c).
```

The boundary is stated once, in C3-R2-1c above. Neither phase does the other's
job; no generic evidence framework is introduced by either in this line of work;
no candidate-level artifact is added in C3; and `semantic_sweep` is not
reopened.

##### Required C3 regression cases

| Evidence | Required bucket |
|---|---|
| `N = 0` | `CLEAN` |
| `N = 1`, one distinct soft code | `MINOR_FRICTION` |
| `N = 2`, two distinct soft codes | `MINOR_FRICTION` |
| `N = 2`, the **same** soft code twice | `REPEATED_FRICTION` (`N=2 > |U|=1`) |
| `N = 3`, three distinct soft codes | `REPEATED_FRICTION` (`N >= 3`) |
| the same soft code once in **two different IQ tasks** | `REPEATED_FRICTION` (`N=2 > |U|=1`) — the cross-task case §9.4.5 defines explicitly |
| a count that is negative, a bool, or a non-int | **REFUSE** |
| `n_t < |S_t|` for some task | **REFUSE** (incoherent evidence) |
| fewer or more than the three frozen tasks | **REFUSE** |
| a caller-supplied bucket contradicting the derivation, *if any such input survives C3-R2-2* | **REFUSE** |
| a profile built **solely** from freely authored counts/categories | **not authoritative** — refused, or not presentable as an authoritative profile (C3-R2-2) |
| the resolver invoked with a genuine `PrimarySweepResult` | derives from each task's own `scope_result`; no caller primitive is consulted |
| C3 asked to read a path/file | **no such surface exists** — AST: no `open`, no `Path.read_*`, no `json.load`, no path parameter anywhere in `qualification.ranking` |

##### What this does not change

R-1 and R-4 keep their existing shapes; R-3's already-accepted symmetric design
(§10.6.2a) is untouched; `OperationBucket` gains no member; `_R2_ORDER` is
unchanged; and `compare_profiles`'s lexicographic R-1 → R-4 walk is unchanged.
The only thing that moves is **who computes R-2**, and the answer becomes AIDO.

### 9.5 Bounds and fail-closed behaviour

`BrokerActivityObservation.__post_init__` caps `read_operation_count` at 32,
`edit_operation_count` at 16, `edited_paths` at 16 entries and `refusals` at 256.
Those are the same caps the broker itself enforces, so the observation is
constructible by construction. If a value nonetheless exceeds a cap, LIVE1
**fails closed and never clamps**: it returns

```python
BrokerActivityObservation(runtime_session_id=<own>, call_succeeded=False)
```

which the frozen type permits (a failed call may report no activity) and which
the controller turns into
`_GateFailure(BROKER_ACTIVITY, BROKER_ACTIVITY_COLLECTION_FAILED)` (matrix case
38). Silently truncating a count that feeds H-8 would be the worse failure.

### 9.6 A recorded, bounded limitation

The snapshot is point-in-time. The broker worker thread could, in principle, be
handling a straggler frame when it is taken — reachable only on a
`DEADLINE_REACHED` turn, since a `SETTLED` turn means the agent loop is finished.
Because `ConsumedBudgets` is monotone and never refilled, such a snapshot can
only **under**-report, never over-report. LIVE1 records this honestly and does
**not** add broker quiescing, a lock, a drain, or a second read.

---

## 10. Final-report-claims projection (CDQ 8)

### 10.1 What the Pi output source actually is

The final assistant report reaches AIDO as
`ar2.supervisor.RuntimeActivity.final_assistant_text`, populated by `_absorb`
from `message_end` / `turn_end` records via `_text_from_message`, which — per
frozen AR2 FU-D — extracts plain `text` blocks **only from a message explicitly
carrying `role == "assistant"`**. Reasoning was already structurally removed at
ingestion (§4.3). Pi also exposes an RPC `get_last_assistant_text` command;
**LIVE1 does not use it** — a second RPC round trip is unnecessary because the
forwarded events already carry the text, and PRE1 §2.6's "no extra probe" rule
applies.

### 10.2 What can be projected into `ReportClaims` — nothing, truthfully

`ReportClaims` has exactly four fields: `claimed_changed_paths`,
`claimed_no_change`, `claimed_done`, `claimed_ran_tests`. Every one of them would
have to be derived from natural-language assistant prose, and
`qualification.report_accuracy`'s own module contract forbids that in terms:

> *"There is no NLP/LLM semantic judgment and no general natural-language parser
> anywhere in this module — a future live adapter may extract a bounded,
> mechanically-safe claim or leave it `UNKNOWN`; it may never invent one."*

There is no structured, machine-readable self-report anywhere in the Pi seam —
no schema, no tool call carrying a claim, no metadata field. **Therefore zero
`ReportClaims` fields are mechanically derivable, and LIVE1 extracts none.**

### 10.3 The design

`collect_final_report_claims(session)`:

```text
R1  bind the transport for exactly this RuntimeSession (all three ids); a foreign
    or retired session RAISES -> the controller records UNAVAILABLE.
R2  one-shot: a second call raises.
R3  return None.
```

`type(None) is not FinalReportClaimsObservation`, so the frozen controller
records `report_availability = ReportAvailability.UNAVAILABLE`,
`report_claims = None`, `comparisons = ()`, and
`_project_report_accuracy` renders
`{"attempted": True, "available": False, "reason": "UNAVAILABLE"}`.

That is precisely the brief's *"return the existing unavailable/empty semantic
shape as frozen rather than fabricating claims"*, expressed through the frozen
controller's own vocabulary, adding no type and no field.

**Why not return `FinalReportClaimsObservation(session_id, ReportClaims())`?**
Because an all-`None` `ReportClaims` yields four `UNKNOWN` comparisons, and
`bucket_report_accuracy` maps "no contradictions, no omission flag" to
**`ACCURATE`** — so a run in which no claim was ever extracted would be recorded
as an accurate self-report. `UNAVAILABLE` is the truthful state; `ACCURATE` is
not. This is a deliberate choice, recorded so review can overrule it.

### 10.4 Non-gating, and provably so

`FINAL_REPORT_CLAIMS` is in `NON_GATING_POST_PROMPT_GATES`; the controller's
final-report block raises no `_GateFailure`, so `UNAVAILABLE` cannot touch
`run_validity`, `scoring_eligible`, `ATTRIBUTION_UNDETERMINED`, or any of
H-1..H-9 (matrix case 16). Repository cleanliness, changed paths, test result and
the qualification verdict come from `ar2.observation`, `ar2.verification`,
`qualification.scope` and the broker cross-check — **never** from this adapter.

### 10.5 Deferred, and named

A bounded, non-NLP claim extractor (for example, a strictly-fenced structured
block the prompt asks the model to emit) would change the corpus prompts, which
LIVE1 must not touch. It is named here as separately authorizable future work
and is **not** designed, implemented, or half-built.

### 10.6 R-3 has no evaluable input — a PRE-Q1 frozen-contract gap (FU1)

Independent review **accepted** §10.2/§10.3's conclusion: no structured,
machine-readable claim channel exists in the Pi seam; general NLP/prose parsing
is forbidden; and returning `UNAVAILABLE` is more truthful than constructing an
empty `ReportClaims` that `bucket_report_accuracy` would label `ACCURATE`.

That acceptance exposes a second, separate conflict, which FU1 records here.

#### 10.6.1 The conflict, stated exactly

```text
qualification.ranking.RankingInput.r3_bucket : ReportAccuracyBucket   MANDATORY
qualification.report_accuracy.ReportAccuracyBucket has exactly three members:
        ACCURATE | MINOR_OMISSION | MATERIAL_MISREPORT
There is no UNAVAILABLE / NOT_EVALUABLE ranking state.
```

So a **truthful** LIVE1 run cannot produce frozen R-3's required input. Every
available value is a positive claim about report reliability, and this harness
observes nothing that supports any of them. The three ways to "satisfy" the
field are all defects:

| Would-be value | Why it is refused |
|---|---|
| `ACCURATE` | four `UNKNOWN` comparisons produce no contradiction and no omission flag, so `bucket_report_accuracy` returns `ACCURATE` — recording "the candidate's self-report was accurate" for a run in which no claim was ever extracted. This is the exact defect §10.3 identified |
| `MINOR_OMISSION` | requires the explicit, harness-supplied `omitted_relevant_fact` signal, which no LIVE1 code can establish |
| `MATERIAL_MISREPORT` | requires an observed contradiction. Recording one where nothing was observed penalizes a candidate for AIDO's missing channel |

Note that this is a **ranking-input** gap, not a run gap: `FINAL_REPORT_CLAIMS`
is in `NON_GATING_POST_PROMPT_GATES`, so `UNAVAILABLE` cannot touch
`run_validity`, `scoring_eligible`, `ATTRIBUTION_UNDETERMINED`, or H-1..H-9
(§10.4). The per-task artifact is already truthful today. What cannot be
produced truthfully is the **candidate-level R-3 bucket** that M4's ranking
consumes.

#### 10.6.2 The recommended minimum FAIR correction

> **For this qualification-policy revision, R-3 is explicitly `NOT_EVALUABLE`,
> because the frozen corpus and harness expose no structured claim channel.
> R-3 ranks neither candidate. Both candidates are evaluated identically under
> the same revised policy.**

This is the direction the brief names as preferred, and source inspection
supports it: `ranking.py` has **no non-test caller anywhere in the repository**,
so the change is a policy and type-shape correction, not a behavioural change to
any run.

**It does require a frozen qualification-policy revision.** Two artifacts move:

| Artifact | Minimum revision |
|---|---|
| `docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md` §18 | record, for this revision, that R-3 is `NOT_EVALUABLE`; state the reason (no structured claim channel in the frozen corpus/harness); state that it therefore ranks neither candidate; state that a future phase may restore R-3 only by first introducing a bounded, non-NLP structured claim channel (§10.5) |
| `qualification.ranking` | `RankingInput.r3_bucket` and `CandidateRankingProfile.r3` become `ReportAccuracyBucket \| None`; `compare_profiles` applies the **symmetric** R-3 rule of §10.6.2a — never R-4's "skip if either side is missing" |

**FU2 correction — R-3 is NOT R-4, and must not reuse R-4's rule.** FU1
proposed *"skip R-3 when either side is `None`"*, copying `compare_profiles`'s
existing R-4 behaviour. Independent review is right to reject that. The two
absences mean different things:

```text
R-4 absent   a PER-CANDIDATE fact. One candidate may legitimately lack an R-4
             bucket while the other has one, so "skip" is the correct handling
             of a genuine one-sided optionality.

R-3 absent   a GLOBAL POLICY fact for this revision. It is None for BOTH
             candidates or for neither. A ONE-SIDED R-3 is not an optional
             tier -- it is an ASYMMETRIC QUALIFICATION STATE, which means two
             candidates were evaluated under different policies. Silently
             skipping it would hide exactly the unfairness the whole
             pre-declaration discipline exists to prevent.
```

**Rejected alternative:** adding an `UNAVAILABLE` / `NOT_EVALUABLE` member to
`ReportAccuracyBucket`. That enum is the return type of
`bucket_report_accuracy`, which is a **mechanical comparator over supplied
claims**; a not-evaluable member would have to be given an order position among
three quality grades, and it would become constructible in contexts where claims
*were* supplied. Not-evaluability is a property of the ranking input, not of the
comparator's output.

#### 10.6.2a The required R-3 comparison invariant (FU2)

```text
a.r3 is None            AND b.r3 is None            -> SKIP R-3
a.r3 is a bucket        AND b.r3 is a bucket        -> COMPARE normally
                                                       (for a future evaluable
                                                        policy revision)
exactly one side is None                            -> REFUSE / RAISE
                                                       never a silent skip,
                                                       never a tier difference,
                                                       never a default bucket
```

The refusal must be a loud, typed error out of `compare_profiles` — the same
"refuse rather than coerce" discipline `semantic_sweep._task_hard_bar_facts`
already applies to a non-`bool` `scoring_eligible`. It is never repaired by
substituting `ACCURATE`, by treating `None` as worst, or by dropping the tier.

**Both profiles must be `None` by construction in this revision, not by
convention.** The recommended mechanism is one module-level policy fact in
`qualification.ranking` — an explicit `R3_EVALUABLE = False` for this revision —
with `build_profile` refusing a non-`None` `r3_bucket` while it is `False` and
emitting `r3=None`. Two properties follow mechanically:

- **symmetry is structural**: every profile this revision can build carries
  `r3=None`, so the asymmetric branch is *unreachable* here rather than merely
  unexercised;
- **nothing is silently discarded**: a caller that supplies an R-3 bucket under
  a policy that declares R-3 not evaluable is **refused**, not ignored. A
  silently-dropped input would be the same class of defect as the silent skip.

The asymmetric refusal is still implemented and still tested, as defence in
depth for the future revision in which `R3_EVALUABLE` becomes `True`.

C3's alternative — leave `r3` to the caller and rely on the refusal alone — is
recorded and **not recommended**: it makes fairness a property of every call
site rather than of the module.

#### 10.6.3 Consequences that must be stated, not glossed

- **The tie surface grows.** With R-3 skipped, two candidates are separated only
  by R-1, R-2 and R-4. If those agree, the result is `"tie"`, routing to §21's
  tie-break policy. That is the honest consequence of having one fewer
  discriminator, and it must not be "fixed" by inventing a replacement tier.
- **Symmetry is by construction, and asymmetry is refused.** Under this
  revision R-3 is `None` for **both** candidates by policy, not per-run, so the
  skip cannot advantage either one — unlike R-4, whose absence is a genuine
  per-candidate possibility. A one-sided R-3 raises rather than skips
  (§10.6.2a), so an asymmetric qualification state can never be ranked past
  in silence.
- **No candidate-facing change.** The corpus prompts, the transmitted message,
  the token policy and the dispatch/turn algorithms are untouched. This revision
  changes what AIDO *scores*, never what the candidate *receives*.
- **The order matters and is achievable.** **No candidate semantic prompt has
  been sent (0).** Declaring R-3 `NOT_EVALUABLE` now is a genuine pre-run policy
  decision; making the same decision after Q1's artifacts existed would be a
  post-hoc adjustment made with a result in hand, which §18's own ranking
  discipline forbids. This is the whole reason it cannot be deferred.

#### 10.6.4 What LIVE1 does about it — nothing, deliberately

`LIVE1-DESIGN` implements no part of this. It does not touch `ranking.py`,
`report_accuracy.py`, the corpus prompts, or the qualification design document.
§10.3's `collect_final_report_claims` design (`return None` →
`ReportAvailability.UNAVAILABLE`) is **unchanged and remains correct** under this
revision: it is precisely the run-level fact from which "R-3 is not evaluable"
follows.

The revision is recorded here as **required before `5F3B-Q1`**, tracked in §18.1
as correction phase **`5F3B-LIVE1-C3` (R-2/R-3 policy revision)**, and is
review's decision to make. §10A adds the third thing C3 carries: an explicit
qualification-policy-revision identifier at the ranking boundary.

---

## 10A. Qualification-policy revision — where the durable binding lives

> **FU3 provenance clarification.** `5F3B-LIVE1-C3` changes qualification policy
> materially: R-2's bucket definitions are replaced (§9.4.5) and R-3 becomes
> `NOT_EVALUABLE` (§10.6). A result produced under this policy is not comparable
> to one produced under another, so the revision must be bound somewhere
> durable. This section states exactly where. **FU4 revised it:** FU3 deferred
> the durable binding to M4 and recorded a gap; that deferral conflicted with the
> roadmap's own qualification-identity rule and is withdrawn (§10A.2). The
> binding now travels with the result, via `5F3B-LIVE1-C4`, before Q1.

### 10A.1 What the current surfaces actually carry

Read from frozen source, not assumed:

| Surface | Carries | Verdict |
|---|---|---|
| `records.record_header()` | `experiment`, `record_version`, `fixture_schema_version`, `record_kind`, `is_review_packet`, `reviewer_invoked`, `external_prior_not_scored`, `trust_namespaces` | **no policy revision.** `record_version` is `"pi-implementer-qualification.v1"` — a **schema** version. Overloading it to encode a *policy* change would be a schema statement about a non-schema fact, and is refused |
| `pi-implementer-qualification.v1` body | identity, run validity, classification, `pi_runtime`, `route_provenance`, `verification`, `scope_result`, `report_accuracy`, `token_policy`, `supervised_recovery` | **no policy revision** |
| `pi-implementer-qualification-attempt.v1` | the reduced indeterminate-dispatch artifact | **no policy revision** |
| `pi-implementer-qualification-lineage.v1` / `-refusal.v1` | invalidation/replacement lineage; refusal fallback | **not a policy carrier** |
| `CandidateRankingProfile`, `PrimarySweepResult` | the ranking profile and the sweep result | **in-memory only.** Neither is ever serialized; no candidate-level decision artifact exists anywhere in the repository today |

**So no existing durable surface can bind the policy revision truthfully**, and
this design does not pretend otherwise.

### 10A.2 WITHDRAWN: the per-task artifacts are not "policy-neutral" (FU4 item 2)

**FU3 was wrong here, and the error mattered.** It argued that the per-task
artifacts carry only raw observations, so a policy revision could bind later, at
M4. That is false in the general sense, and it conflicts with the canonical
roadmap's own qualification-identity rule: **the policy revision is recorded
WITH the result, not in a changelog beside it, so the record stays
self-describing**; two candidates are comparable only under the same revision;
and an old record is never re-scored under a new policy.

Source settles it. `pi-implementer-qualification.v1` already records **policy
conclusions**, not just telemetry:

```text
run_validity                      a POLICY verdict over observed facts
scoring_eligible                  a POLICY verdict
autonomous_classification         a POLICY classification
diagnostic_subclassification      a POLICY sub-classification
+ verification / scope_result / report_accuracy projections
```

A one-shot Q1/Q2 result carrying those may not depend on a future artifact to
explain which policy produced them. FU3's "policy-neutral inputs" framing is
**withdrawn**. What remains true, and only this: R-2's and R-3's *bucket* values
are not recorded per task — but `run_validity`, `scoring_eligible` and the
classifications are, and they are policy all the same.

### 10A.2a The frozen requirement

```text
Every durable ROLE_CAPABILITY qualification result emitted by Q1/Q2 must carry a
durable `qualification_policy_revision` binding, and that binding must exist
BEFORE Q1 begins.

Git history, a document beside the result, process memory, and a future M4
decision artifact are each INSUFFICIENT on their own. The binding travels WITH
the one-shot result.
```

This applies to **both** durable per-task artifact kinds — the primary
`pi-implementer-qualification.v1` record and the sibling
`pi-implementer-qualification-attempt.v1` record — because an indeterminate
attempt is equally a one-shot result produced under a policy.

### 10A.2b Yes — a record schema revision IS now required, and it is cheap

**Answer to the deliverable's question 5: yes.**

The narrowest mechanically sufficient mechanism is one explicit header field on
each artifact lineage, added at the two existing header builders:

| Builder | Add | Version decision |
|---|---|---|
| `records.record_header()` | `"qualification_policy_revision": <the declared constant>` | `RECORD_VERSION` → `pi-implementer-qualification.v2` |
| `semantic_attempt.attempt_record_header()` | the same field, same constant | `ATTEMPT_RECORD_VERSION` → `pi-implementer-qualification-attempt.v2` |
| `safety.build_refusal_record()` **(FU4A)** | the same field, same constant, as **fixed metadata** | `REFUSAL_RECORD_VERSION` → `pi-implementer-qualification-refusal.v2` |

The first two builders already have the identical eight-field mirrored header
shape, so this is one field in each, in the one place each is constructed.

##### Why the refusal artifact must carry it too (FU4A item 3)

`safety.emit_evidence_or_refuse` is the emission choke point for **every**
qualification artifact, and it is fail-closed in a way that matters here: when
`qualification_scrub_check` rejects the payload, it writes
`build_refusal_record(...)` **instead of** the primary or attempt record —
exclusive-create, at the same path.

**In that case the refusal artifact is the ONLY durable artifact that invoked,
one-shot attempt will ever have.** Binding the policy revision into the two
records it replaces, but not into the replacement, leaves the record
non-self-describing in exactly the fallback case — which is precisely when a
reader has least other context. So:

```text
QUALIFICATION_POLICY_REVISION      one declaration site, qualification/__init__.py
    -> primary  v2 header          carries it
    -> attempt  v2 header          carries it
    -> artifact-emission-refusal v2  carries it as FIXED METADATA
```

**Nothing else is added to the refusal record.** Its whole value is that it is a
fixed, bounded, independently scrub-checked shape: no candidate, no task id, no
path, no prompt content, no endpoint, no exception text, no credential, no
copied snippet. One constant literal is added, and it is scrub-safe by
construction because it is a declared literal with no runtime input.

##### Lineage needs no policy field, and source proves it

`qualification.lineage` does `from .records import RECORD_KIND, RECORD_VERSION`
and checks `record.get("record_version") != RECORD_VERSION` — it imports the
**symbol**, not a literal, so it follows C4's bump automatically and needs no
edit. It also binds concrete run records **by content digest**, so a lineage
record can obtain the policy revision from the record it binds rather than
restating it.

One consequence C4 must state rather than discover: after the bump, lineage
will accept only `.v2` primary records. That is correct — no `.v1` record exists
— and it is named here so it is not mistaken for a regression.

**`record_version` is NOT overloaded.** It stays a *schema* version and answers
"what shape is this record"; the new field answers "under which policy were its
verdicts produced". Encoding a policy fact in a schema version is refused
explicitly — it would make every future policy revision a schema revision and
vice versa.

**The version bump costs nothing archival, and that is a source fact rather than
an assumption.** `results/` contains only the four Category-B live records
(`i2b_live_*.json`, a different artifact kind from `i2b_controller`). **No
`pi-implementer-qualification.v1` or `-attempt.v1` artifact has ever been
emitted by anything**, so there is no v1 corpus to preserve compatibility with,
no reader to migrate, and no archived result to reinterpret.

**`v1` nonetheless keeps its original meaning**, per this project's standing rule
that an archived version is never reinterpreted:

> `pi-implementer-qualification.v1` and `pi-implementer-qualification-attempt.v1`
> mean *a record that carries no policy-revision binding*. No `v1` record may
> ever be read as though it had been produced under any particular
> qualification-policy revision — including this one. Since none exists, this is
> a statement about hand-made or future-forged records, and it is the reason the
> field is added by a **bump** rather than silently into `v1`.

**Pre-run correction is preferable to unbound one-shot evidence**, and it is
available: Q1 has not run, no semantic artifact exists, and the correction is
two fields plus two constants.

### 10A.2c Which phase owns it — `5F3B-LIVE1-C4`, landing before C3

This is a **retained-evidence schema** change, categorically different in risk
from C3's in-memory ranking math, so it gets its own narrow phase rather than
being folded in:

```text
5F3B-LIVE1-C4  qualification-record policy binding   REQUIRED, NOT YET AUTHORIZED

  Production modules reopened, and only these FOUR:
    qualification/__init__.py       declare QUALIFICATION_POLICY_REVISION (one
                                    stable opaque literal, the SINGLE declaration
                                    site in the repository); bump RECORD_VERSION,
                                    ATTEMPT_RECORD_VERSION and
                                    REFUSAL_RECORD_VERSION to .v2
    qualification/records.py        one field in record_header()
    qualification/semantic_attempt.py  the same field in attempt_record_header(),
                                    plus its own closed key set
    qualification/safety.py         the same field in build_refusal_record()'s
                                    FIXED metadata, and the bumped version
                                    constant it already consumes -- and NOTHING
                                    else: the scrub, the exclusive-create write
                                    and the emit/refuse choke point are unchanged

  Not touched: every ar2 module, semantic_controller, semantic_sweep,
               semantic_session, semantic_workspace, i2b_*, scope, validity,
               outcomes, hard_bar, ranking, lineage, the corpus, the prompts.

  Ordering: C4 -> C3. C3 IMPORTS the constant C4 declares, so there is exactly
  one declaration site and the ranking boundary and the retained record can
  never disagree about which revision applied.
```

C4's own tests: **all three** builders carry the field and the bumped version;
the constant has exactly one declaration site (AST); the field is a plain
declared literal with no environment, filesystem, Git or clock input;
`emit_evidence_or_refuse`'s scrub passes on a record carrying it **and** on the
refusal record carrying it; a payload deliberately failing the scrub yields a
refusal artifact that still carries the revision; the refusal record gains
**nothing** but that field (its closed key set is asserted exactly); the closed
key sets `semantic_attempt` already validates are updated in the same edit
rather than left to reject the new field; and `lineage` still binds a primary
record without an edit, now at `.v2`.

> **Review may instead fold C4 into C3.** The tradeoff is stated so the choice
> is explicit: one fewer phase, against one review covering both a retained
> evidence schema and the ranking policy math. This design recommends keeping
> them apart.

### 10A.3 What C3 itself must do — a policy-revision identifier at the ranking boundary

C3 does not create an artifact, and it does not widen a record schema. It does
introduce the identifier and make it load-bearing where ranking happens:

```text
C3-PR-1  C3 CONSUMES the single declared identifier -- `QUALIFICATION_POLICY_
         REVISION`, declared by C4 in `qualification/__init__.py` (Sec. 10A.2c)
         -- and declares no second one. It is an opaque stable string: never a
         date, never a Git SHA, never derived from the environment, the clock or
         a file's mtime. One declaration site means the retained record
         (Sec. 10A.2b) and the ranking boundary can never disagree.

C3-PR-2  `RankingInput` and `CandidateRankingProfile` each carry it, and
         `build_profile` stamps the profile from the declared constant rather
         than from anything a caller passes.

C3-PR-3  `compare_profiles` REFUSES two profiles whose policy revisions differ.
         Not "skip a tier", not "prefer the newer", not a warning -- a loud,
         typed refusal, the same discipline as R-3's asymmetric case
         (Sec. 10.6.2a). Comparing candidates evaluated under different policies
         is exactly the unfairness the whole pre-declaration discipline exists
         to prevent.

C3-PR-4  SCOPE OF THE IDENTIFIER -- CORRECTED (FU4A). An earlier revision said
         it changes "when, and only when, R-1..R-4's definitions change". That
         is too narrow: the canonical roadmap Sec. 2.2 defines a PASS under a
         BROADER policy than ranking alone -- the frozen corpus, the hard bar
         H-1..H-14, the outcome taxonomy, the one-shot prompt policy and the
         prompt-fairness rules, PLUS the ranking policy.

         `QUALIFICATION_POLICY_REVISION` therefore identifies the COMPLETE
         implementer ROLE_CAPABILITY qualification policy, and MUST change
         whenever a change alters the MEANING, ELIGIBILITY, CLASSIFICATION,
         RANKING or COMPARABILITY of a qualification result -- including at
         least:

             corpus / task-contract semantics
             hard-bar semantics (H-1..H-14)
             run-validity / scoring-eligibility semantics
             autonomous / diagnostic classification semantics
             one-shot / prompt-budget policy
             candidate-fairness policy
             refusal / scope interpretation, where it affects qualification
                 or ranking (this is what C2's projection changes)
             R-1..R-4 definitions or comparison rules

         It does NOT change for:

             implementation-only refactors
             tests that do not change policy
             documentation-only edits
             formatting / naming changes with identical semantics

         It stays ONE STABLE DECLARED LITERAL. There is deliberately no
         automatic policy hashing, no derivation from source digests, no Git
         SHA and no computed fingerprint: a computed identifier would change on
         every refactor and would silently stop meaning "the policy changed".
         Deciding that a change is policy-bearing is a REVIEW judgement, made
         when the change is made, and it is exactly the judgement this literal
         records.

C3-PR-5  NO RECORD SCHEMA CHANGE IN C3 -- that is C4's, and only C4's
         (Sec. 10A.2c). C3 touches no record builder, no header, no version
         constant, no lineage or refusal record, and `FIXTURE_SCHEMA_VERSION`.
         C3 reads the constant and refuses across revisions; C4 writes it into
         the retained artifacts. Neither does the other's job.

C3-PR-6  NO CANDIDATE-LEVEL ARTIFACT IN C3. C3 emits nothing durable. The
         candidate-level decision artifact is M4's, and Sec. 12.7's refusal of
         new artifact kinds inside this line of work is unchanged.
```

Required C3 tests: two profiles under the same revision compare normally; two
profiles under **different** revisions **refuse**; `build_profile` stamps the
declared constant and ignores (or refuses) any caller-supplied revision; and the
constant is a plain declared literal with no environment, filesystem or Git
input.

### 10A.4 What M4 must still do — additive, never a substitute

The per-result binding of §10A.2b does **not** discharge M4. Both are required,
and they answer different questions:

```text
C4  (before Q1)   "under which policy were THIS RESULT's verdicts produced?"
                  -> bound into every durable per-task artifact, self-describing

M4  (later)       "which COMBINATION was selected, on what evidence, under
                   which policy?"
                  -> the candidate-level decision artifact, which does not exist
```

```text
M4 DECISION ARTIFACT REQUIREMENT (recorded here; owned by M4, not by C1..C4)

Before any candidate may be declared SELECTED or QUALIFIED, the candidate-level
qualification / ranking decision artifact MUST durably persist the full tuple:

    role                  implementer
    harness               Pi
    harness_version       the observed version (provenance, never authorization)
    model                 the candidate model id
    backend               the provider / gateway the route named
    qualification_policy_revision
                          the exact revision under which R-1..R-4 were defined
                          and applied -- and it MUST equal the revision every
                          consumed per-task artifact carries (Sec. 10A.2b), or
                          the decision refuses

plus the exact per-task artifact identities -- file names AND content digests --
that the decision consumed.

Until that artifact exists, NO candidate may be declared selected or qualified.
```

The cross-check in the middle of that block is the point of doing both: once
C4 binds the revision into each result, M4 can **verify** rather than assert
that every artifact it ranked was produced under the policy it is ranking by.
Neither layer alone gives that.

**This is no longer a reported gap.** FU3 recorded an open gap here because the
durable binding had no home before M4. C4 gives it one, before Q1, so the gap is
**closed by C4** and what remains for M4 is ordinary future work under its own
authorization.

---

## 11. Live adapter composition (CDQ 9)

### 11.1 The mechanical constraint that decides it

Two frozen facts, together, force the answer:

1. `tests/test_i2b_live_adapters.py::test_no_prompt_command_type_is_ever_constructed`
   asserts that the string `"prompt"` appears in **no string literal anywhere in
   the `qualification.i2b_live_adapters` module**. So the semantic adapter cannot
   live in that module.
2. `AuthenticatedB300RouteObserver.__init__` requires
   `type(adapters) is LiveCategoryBAdapters` (exact type, deliberately, per
   `LF2-FU1 BLOCKER 2`). So the semantic adapter cannot be a **subclass** —
   a subclass would be refused at the frozen ROUTE_CHECK gate.

### 11.2 The design: a new module, and composition

New module `qualification/semantic_live_adapters.py`, containing
`LiveSemanticAdapters`, which **is not** a subclass of `LiveCategoryBAdapters`
and **holds one** as a private member:

```text
LiveSemanticAdapters
    _base : LiveCategoryBAdapters | None  # EXACT type once activated (Sec. 12.2A);
                                          # None until read_connection activates
    _task : QualificationTask             # the frozen corpus object, bound at
                                          # construction -- the ONE thing the
                                          # inert shell holds
    _transport : _LiveSemanticTransport | None

    # 13 delegating zero-prompt ports, one line each:
    read_connection, create_broker, shutdown_broker, launch_runtime,
    get_commands, get_state, observe_protocol, shutdown_runtime,
    consumed_connection_values, launch_diagnostics
    # (the non-secret preflight gates are module-level functions, not methods)

    # 4 semantic ports (Sections 7-10)
    dispatch_semantic_prompt, observe_semantic_turn,
    collect_broker_activity, collect_final_report_claims
```

Why composition, stated as properties rather than taste:

| Property | Composition | Subclass |
|---|---|---|
| `type(x) is LiveCategoryBAdapters` | False | False |
| `isinstance(x, LiveCategoryBAdapters)` | **False** | True |
| route observer accepts `_base` | **yes** | n/a — it would be handed the subclass and refuse |
| `i2b_live_adapters` module keeps zero `"prompt"` literals | yes | yes |
| future `LiveCategoryBAdapters` methods become prompt-adjacent automatically | **no** | yes |
| the 13 shared ports are enumerable by a reviewer | **yes, explicitly** | no, implicit |

`LiveCategoryBAdapters` therefore remains **structurally zero-prompt in the
strongest available sense**: no instance of it gains prompt authority, no
`isinstance` check is weakened, and its module is unchanged (matrix cases 29,
41).

> **FU1: `_base` is created at activation, not at construction (§12.2A).** The
> shell handed to `TaskAdapterBundle` holds only the frozen task; `_base` is
> `None` until the controller's post-gate `read_connection` call builds it. Every
> delegating port other than `read_connection` therefore refuses on `_base is
> None` rather than activating (§12.2A.3 A3), and `base_for_route_authority()`
> raises in that state. Nothing else in §11 changes: the type is still exactly
> `LiveCategoryBAdapters`, the port list is still exactly these 13 + 4, and the
> module still declares no `"prompt"` literal beyond the one dispatch site.

### 11.3 Binding the live handles — the one coupling, made explicit

The semantic ports need the `PiRpcSupervisor` and the `BrokerRequestHandler`,
which the frozen adapter keeps in `_brokers` / `_runtimes`. Two options were
considered:

- **REJECTED:** add a public accessor to `LiveCategoryBAdapters` returning the
  supervisor. That would give the accepted zero-prompt type a public way to hand
  out a live stdin writer — a real widening of its authority, whatever the
  method is called.
- **DESIGNED:** exactly **two** guarded private reads, at exactly two call
  sites, each immediately after the corresponding delegated creation call, each
  binding the handle into the semantic adapter's own record and never reading
  it again:

  ```text
  create_broker(request):
      observation = self._base.create_broker(request)
      if observation.session is not None:
          record = self._base._brokers[observation.session.session_id]   # READ 1
          require record.run_id == request.run_id and record.session is observation.session
          self._pending_broker_handler = record.handler
      return observation

  launch_runtime(request):
      observation = self._base.launch_runtime(request)
      if observation.session is not None:
          record = self._base._runtimes[observation.session.runtime_session_id]  # READ 2
          require record.run_id == observation.session.run_id
              and record.broker_session_id == observation.session.broker_session_id
          self._transport = _LiveSemanticTransport(... supervisor=record.supervisor,
                                                   broker_handler=self._pending_broker_handler ...)
      return observation
  ```

  Both reads fail closed (a missing or mismatched record raises before any
  transport exists). Two offline tests pin them: an AST test that these are the
  **only** two private-attribute reads of `_base` in the module (matrix case 42),
  and a source-drift guard that `_LiveBrokerRecord.handler` /
  `_LiveRuntimeRecord.supervisor` still exist with the assumed shapes (matrix
  case 40).

> **Dependency on §2.6, restated for FU1.** The composition above is exactly
> right as written under the `5F3B-LIVE1-C1` capability issuance seam (§2.6.4),
> and **READ 1 may become unnecessary**: if C1's `create_broker`-time issuance
> (§2.6.4a) also carries the
> `BrokerRequestHandler` binding for the semantic task, the handler arrives
> through that seam and the private `_brokers` read is deleted rather than kept.
> READ 2 (the supervisor) is expected to remain. Their final acceptability is
> reviewed once C1's shape is known; neither read is expanded, and no public
> accessor is added to the zero-prompt adapter for either. §§7–10 do not depend
> on the outcome.

### 11.4 What the semantic module must not contain

No `"steer"`, `"follow_up"`, `"abort"`, `"abort_retry"`, `"clear_queue"`,
`"bash"`, `"compact"`, `"set_model"`, `"new_session"` string literal. No second
`"prompt"` construction site. No retry, continuation, or re-dispatch call site.
No `candidate` / `model` / `provider` parameter (§15). No generic
`AgentRuntime` / `Harness` interface, registry, plugin seam, or capability list
— LIVE1 stays Pi-specific (roadmap §4.5.5).

---

## 12. Live runner contract (CDQ 11)

New executable `experiments/pi_implementer_qualification/run_semantic_sweep_live.py`,
sibling of the accepted `run_i2b_live.py` and modelled on it.

### 12.1 CLI surface — exactly two options, both required

```text
--candidate {A,B}              REQUIRED. required=True, NO default.
--run-primary-sweep-live       REQUIRED explicit operator-friction flag.
```

There is deliberately **no** `--workspace`, `--path`, `--repo`, `--project`,
`--task`, `--tasks`, `--model`, `--provider`, `--base-url`, `--endpoint`,
`--api-key`, `--max-tokens`, `--retry`, `--continue`, `--resume`, `--both`,
`--all-candidates`, `--q2`, `--timeout`, or `--force`. The parser declares
exactly the two options above, and an offline test asserts that by inspecting the
parser's actions (matrix cases 27, 28, 44).

Contrast recorded deliberately: `run_i2b_live.py` has `--candidate ... default="A"`.
**The semantic runner must not.** A default candidate is exactly the "convenience
default is the hazard" case the roadmap names.

> **The flag is friction, not authority.** `--run-primary-sweep-live` records that
> an operator typed it. Human authorization for Q1/Q2 remains external to this
> executable, and the existence of the flag is not itself authorization.

### 12.2 What the runner does, in order

```text
1. refuse unless --run-primary-sweep-live was passed          -> exit 1
2. independent pre-live safety check (candidate is a declared candidate;
   no workspace parameter exists anywhere in this script, in
   LiveSemanticAdapters, in run_primary_sweep, or in
   mint_qualification_run_workspace)                          -> exit 1 on refusal
3. resolve git executable (frozen resolver; shutil.which + three checks,
   NO subprocess)
4. mint the evidence directory under results/  (a results dir, NOT a workspace)
5. call run_primary_sweep(candidate=..., ambient_environ=os.environ,
       node_executable=..., git_executable=..., python_executable=...,
       build_adapters=<factory>, evidence_dir=...)
6. print ONE bounded operator summary from the in-memory PrimarySweepResult
   (no artifact is written -- Sec. 12.7)
7. exit per 12.5
```

> **FU1 removed the runner-level Category-A pre-pass and the runner-level
> identity probe.** The pre-FU1 draft ran the eight gates once, in the runner,
> before the sweep. Independent review is right that a once-per-sweep preflight
> is not a substitute for **each fresh task attempt's own** ordering, and —
> worse — it made `build_adapters` the place where identity was resolved.
> §12.2A replaces both.

**Where `node_executable` comes from now, and why it is still trustworthy.**
Frozen `run_primary_sweep` requires `node_executable` as a plain string
argument, and the frozen controller consumes it at `CHILD_ENVIRONMENT` (gate 10)
for PATH narrowing. Pre-FU1 it came from the runner's `resolve_pi_identity()`,
which no longer runs there. The runner instead calls the frozen
`_ar2_resolve_node_executable()` — already re-exported into
`qualification.i2b_live_adapters` and already called by the Category-A gate
`preflight_pi_installed_offline` — which is `shutil.which("node")` plus
`realpath` plus an `isfile` check and **launches no process**.

The two values cannot diverge: `LiveCategoryBAdapters.__init__` runs
`_require_runtime_identity_matches_trusted_resolution(identity)`, which binds
the per-task issued identity to **this machine's own trusted resolver path** —
the same `_ar2_resolve_node_executable()` output the runner passed. An offline
regression pins the equality (matrix case 51) rather than leaving it argued.

**Live-safety scope of the step list — corrected (FU2).** An earlier revision
said *"no process is launched in steps 1–5"*. That is false: **step 5 is
`run_primary_sweep`, which is the live sweep itself.** Stated truthfully:

```text
steps 1-4   launch NO process. Flag check, candidate check, the frozen Git
            resolver (shutil.which + realpath + isfile), the node resolver
            (same shape), and creating the results directory. Zero subprocess,
            zero socket, zero credential read, zero model contact.

step 5      ENTERS THE LIVE SWEEP. run_primary_sweep invokes the frozen
            controller once per task, and the controller launches Pi/Node,
            opens a broker and a named pipe, reads the B300 credential,
            issues one route observation, and sends one semantic prompt per
            task. Everything live in this executable happens at or below
            this call.

            Within step 5, per task, the ordering of Sec. 12.2A holds:
            a task's `node cli.js --version` identity probe begins ONLY after
            THAT task's eight Category-A non-secret gates have passed, and its
            credential read only after that (Sec. 12.2A.1).

steps 6-7   print a bounded operator summary and exit. No process, no file
            (Sec. 12.7).
```

The invariant worth stating is therefore **not** "the runner launches nothing"
— it launches Pi three times — but "**nothing live precedes step 5, and inside
step 5 nothing live precedes its own task's Category-A gates.**"

### 12.2A Per-task ordering — the binding invariant (FU1 BLOCKER 2)

Frozen `semantic_sweep.run_primary_sweep` mechanically calls
`build_adapters(task)` **before** `run_semantic_task_attempt`, and the task's
own Category-A gates run **inside** that attempt, at the
`NON_SECRET_PREFLIGHT` gate. The pre-FU1 §12.3 resolved Pi identity inside
`build_adapters`, i.e. it launched `node cli.js --version` **before** that
task's gates had passed. That is the defect, and it is corrected here.

#### 12.2A.1 The required order, per IQ task

```text
build_adapters(task)
    construct a FRESH LiveSemanticAdapters SHELL
    ZERO subprocess, ZERO credential read, ZERO broker/pipe/runtime resource,
    ZERO network -- it constructs objects and binds the frozen task, nothing else
        |
        v
run_semantic_task_attempt(task)
    RUN_CORRELATION -> WORKSPACE_AUTHORITY -> WORKSPACE_BASELINE
                    -> ROUTE_DESCRIPTOR
        |
        v
    NON_SECRET_PREFLIGHT
        resolve_connection_after_preflight() evaluates ALL EIGHT Category-A
        non-secret gates, in order, first failure raises
        |
        +-- any gate FAILS --> InfrastructureRefusal
        |                      read_connection() is NEVER called
        |                      => ZERO Pi/Node subprocess for this task
        |                      => ZERO credential read
        |                      => ZERO broker/runtime resource
        |
        v  every gate PASSES
    read_connection()   <-- the FIRST adapter port the controller ever invokes
        step 1: ACTIVATE  resolve_pi_identity()      <-- the ONE --version probe
        step 2: ACTIVATE  LiveCategoryBAdapters(runtime_identity=<issued>, ...)
        step 3: delegate  self._base.read_connection()   <-- the credential read
        |
        v
    SECRET_CONTEXT -> PI_CONFIG_GENERATION -> IDENTITY_BINDING
                   -> CHILD_ENVIRONMENT
        |
        v
    BROKER_SESSION
        create_broker(BrokerCreationRequest(run_id=..., workspace=...))
        <-- the SECOND authority event: capability issuance/consumption
            (Sec. 2.6.4a). It is NOT part of activation, because
            read_connection never sees run_id or the workspace.
        |
        v
    BROKER_READY -> RUNTIME_LAUNCH -> ... -> ROUTE_CHECK
                 -> semantic lifecycle -> CLOSURE
```

#### 12.2A.2 Why `read_connection` is the correct activation trigger

This is a mechanical property of the frozen controller, not a convention:

1. `resolve_connection_after_preflight(non_secret_gates=…, read_connection=…)`
   evaluates every gate first and calls `read_connection` **exactly once**, only
   when all of them reported `passed=True`. That is the frozen function's own
   documented and tested contract.
2. `read_connection` is the **first** injected adapter port the controller calls
   at all. The four gates before `NON_SECRET_PREFLIGHT`
   (`RUN_CORRELATION`, `WORKSPACE_AUTHORITY`, `WORKSPACE_BASELINE`,
   `ROUTE_DESCRIPTOR`) use no adapter callable, and `create_broker` is gate 11.
3. Activation therefore sits in the **only** window that is simultaneously after
   every Category-A gate and before every credential read, resource creation and
   model contact — and the window is one function call wide.
4. The eight Category-A gates are all module-level, offline, subprocess-free
   functions (`resolve_pi_identity` is the module's only `subprocess` call site
   besides `launch_runtime`'s supervisor), so running them cannot itself start a
   process.

#### 12.2A.3 The activation rules

```text
A1  Activation happens in exactly ONE place: LiveSemanticAdapters.read_connection,
    before it delegates. There is no other activation call site, no public
    `activate()` method, and no lazy activation inside any other port.
A2  Activation is ONE-SHOT per adapter instance. A second call to
    read_connection raises; the frozen controller calls it once.
A3  Every other port -- create_broker, launch_runtime, get_commands, get_state,
    observe_protocol, the route checker, all four semantic ports,
    shutdown_runtime, shutdown_broker -- REFUSES on an unactivated adapter and
    NEVER activates it. Refusing is the fail-closed answer; activating would
    reintroduce a path from an unbounded caller to a subprocess.
A4  A failed activation (LaunchIdentityError, IssuanceError, or the identity
    trust check) raises out of read_connection. The frozen
    resolve_connection_after_preflight does not catch it, so the controller's
    generic adapter-failure handling records it and the attempt ends with no
    Pi child, no broker and no credential -- `_close_runtime`/`_close_broker`
    return NOT_REQUIRED because both sessions are None.
A5  Nothing is cached across tasks. One adapter per task, one runtime-identity
    issuance per adapter, one probe per issuance (Sec. 12.4).
A6  Activation binds the RUNTIME IDENTITY only. It never issues, consumes,
    pre-computes, caches or partially prepares the semantic CAPABILITY, and it
    never observes the repository -- it cannot, because it is handed neither
    the run id nor the workspace. Capability issuance is a separate authority
    event at create_broker (Sec. 2.6.4a).
```

#### 12.2A.4 The route checker must not force early construction

`AuthenticatedB300RouteObserver.__init__` requires an **exact-type**
`LiveCategoryBAdapters` instance, which does not exist until activation. The
route checker is nevertheless built by `build_adapters`, which must stay inert.

The design resolves this **without** requiring the base adapter to exist at
bundle-construction time, and **without** a general-purpose closure factory:

```text
the runner constructs one small, single-purpose, runner-private binder holding
exactly two things -- this sweep's `candidate` string and this task's
LiveSemanticAdapters instance -- and presenting exactly the frozen call shape
`checker(base_url, *, model_id)`.

On its FIRST call it:
   - asks the adapter for its ACTIVATED exact-type base (Sec. 12.3); if the
     adapter is not activated it REFUSES and never activates it (rule A3);
   - constructs the frozen observer ONCE via the unmodified
     build_authenticated_route_checker(candidate=..., adapters=<that base>);
   - caches that observer and delegates to it.
Every later call delegates to the SAME observer, so the frozen "one observation
per run" refusal, the base-URL check, the model-id check and the
route_diagnostics record all remain the frozen observer's, unduplicated.
```

Binding properties, all mechanically checkable:

```text
R1  The binder has exactly two constructor parameters: `candidate` and the
    semantic adapter. No transport, client, requester, sender, session,
    http_client, request_callback, base_url, api_key, endpoint, provider or
    model_id parameter -- the identical constructor discipline LF2-FU1
    BLOCKER 1 imposed on the observer itself.
R2  It cannot be handed a pre-built observer, a base adapter, or an adapter
    factory. The ONLY LiveCategoryBAdapters it can ever reach is the one its
    own bound semantic adapter activated.
R3  It NEVER activates. `ROUTE_CHECK` is gate 21; if the adapter is somehow
    unactivated there, the run is already malformed, and the truthful answer
    is a refusal that `run_offline_route_check` reduces to its existing
    bounded ROUTE_CHECK_ERROR -- no new failure code is introduced.
R4  `candidate` lives in the RUNNER, never on `LiveSemanticAdapters`, so the
    adapter stays candidate-blind (Sec. 15.2) and the candidate still reaches
    exactly two frozen consumers: `run_primary_sweep` and
    `build_authenticated_route_checker`.
R5  It adds no authority: every substitution refusal, the single-observation
    rule, and the diagnostic record remain the frozen observer's.
```

> **Why not eager construction?** It is unreachable. `build_adapters` must
> return the complete `TaskAdapterBundle` before the controller — and therefore
> before that task's gates — has run at all, so any eager construction of the
> base adapter necessarily precedes the gates. That is the defect being fixed.
> A narrower non-lazy design does not exist under the frozen sweep's call order.

#### 12.2A.5 The invariant, stated for test

```text
For every IQ task, if that task's Category-A non-secret preflight refuses:
    node/Pi subprocesses started for that task          = 0
    --version probes issued for that task               = 0
    IssuedRuntimeIdentity objects minted for that task   = 0
    LiveCategoryBAdapters instances constructed          = 0
    credential/environment connection reads              = 0
    broker servers, named pipes, runtime children        = 0
    B300 route observations                              = 0
    semantic prompts                                     = 0
and this holds identically for Candidate A and Candidate B.
```

### 12.3 The `build_adapters` factory — inert by construction

```text
def build_adapters(task) -> TaskAdapterBundle:
    adapters = LiveSemanticAdapters(          # SHELL ONLY -- no probe, no base,
        task=task,                            # no credential, no resource,
        environ_reader=os.environ.get,        # and NO git_executable (Sec. 2.6.5b)
    )
    return TaskAdapterBundle(
        non_secret_gates=<the same eight frozen module-level gate functions>,
        read_connection=adapters.read_connection,      # ACTIVATES, then delegates
        create_broker=adapters.create_broker,
        launch_runtime=adapters.launch_runtime,
        get_commands=adapters.get_commands,
        get_state=adapters.get_state,
        observe_protocol=adapters.observe_protocol,
        route_checker=<the Sec. 12.2A.4 binder over (candidate, adapters)>,
        dispatch_semantic_prompt=adapters.dispatch_semantic_prompt,
        observe_semantic_turn=adapters.observe_semantic_turn,
        collect_broker_activity=adapters.collect_broker_activity,
        collect_final_report_claims=adapters.collect_final_report_claims,
        shutdown_runtime=adapters.shutdown_runtime,
        shutdown_broker=adapters.shutdown_broker,
    )
```

Differences from the pre-FU1 draft, each deliberate:

- **`resolve_pi_identity()` is gone from this function.** It moved to activation
  inside `read_connection` (§12.2A.3 A1).
- **`runtime_identity=` is gone from the constructor.** `LiveSemanticAdapters`
  no longer accepts an identity from its caller at all, which also removes a
  parameter through which a caller could have supplied a substitute. The
  identity is obtained by the adapter itself, at activation, from the trusted
  issuance boundary — the frozen `resolve_pi_identity` / `IssuedRuntimeIdentity`
  one-shot claim discipline is reused exactly, not weakened.
- **`git_executable=` is gone from the constructor (FU3).** The manifest
  observation resolves its own Git executable internally, at the issuance
  consumption boundary, through the accepted `resolve_git_executable` bound to
  the verified workspace root (§2.6.5b / C1-P12b). The adapter therefore exposes
  no program-selection surface at all. The runner still passes `git_executable`
  to the frozen `run_primary_sweep` — a different parameter, untouched in shape,
  but no longer trusted: under C1-P12a it is re-proved by exact equality against
  an independent resolution at the attempt's first Git consumption boundary
  (§2.6.5b), before any Git runs.
- **`base_for_route_authority()` is now defined to raise when unactivated**, and
  returns the composed, **exact-type** `LiveCategoryBAdapters` afterwards, so
  the frozen observer's `type(...) is` check passes (§11.1). It is the only
  accessor of its kind and returns no live handle.
- **Under C1 (§2.6), activation binds the RUNTIME IDENTITY ONLY.** The
  capability issuance does **not** happen here. `read_connection` has the frozen
  zero-argument shape and receives neither `run_id` nor the
  `QualificationRunWorkspace`, so a capability bound to all four identities is
  not constructible at activation. Issuance/consumption happens later, at
  `create_broker(BrokerCreationRequest)` — the first adapter call that carries
  both the run id and the exact workspace. See §2.6.4a, which states the two
  authority events and why they cannot be merged.

### 12.4 One identity probe per task, three per sweep — post-gate, and stated

`_claim_issued_runtime_identity` is **one-shot**: one `resolve_pi_identity()`
issuance authorizes exactly one adapter instance. A fresh adapter per task
therefore requires a fresh issuance per task, i.e. **three `node cli.js
--version` probes per sweep, one per task** — each of which now happens
**after** its own task's eight Category-A gates have passed (§12.2A), not in
`build_adapters`.

That is a consequence of the frozen "fresh everything per task" rule combined
with the frozen one-shot issuance; it is a provenance-only subprocess that sends
no prompt and reads no credential; and it is recorded here so it is not later
mistaken for drift. A sweep that refuses at task 1's Category-A gates issues
**zero** probes, not one.

### 12.5 Exit codes — about the harness, never the candidate

```text
0   the sweep ran to completion: all three tasks were invoked and a
    PrimarySweepResult was produced. A candidate FAIL is still a 0, and so is
    a sweep in which every task was refused before its prompt.
1   refused before the sweep began -- the flag was absent, the candidate is not
    a declared candidate, or the Git executable / evidence directory could not
    be resolved. Zero tasks invoked, zero prompts.
2   the sweep began but stopped early -- one or more tasks are
    NOT_ATTEMPTED, or a dispatch was SEND_STATE_INDETERMINATE.
```

> **FU1 corrected exit 1's membership.** The pre-FU1 list included "a
> Category-A gate failed" and "identity resolution failed". Under §12.2A both
> now happen **inside a task attempt**, at that task's own
> `NON_SECRET_PREFLIGHT` gate, so neither can refuse the sweep before it
> begins. A Category-A failure is a per-task **pre-prompt infrastructure
> refusal**: the frozen controller records it as the failed gate, the task
> yields no `run_validity`, the sweep continues to the next task (an
> infrastructure refusal is not an indeterminate dispatch), `hard_bar_result`
> is `INCOMPLETE`, and the process exits **0** — because the harness did run
> the sweep. The refusal is in the artifacts, which is where it belongs.
>
> That is deliberately **not** given a new exit code. Adding one would be a new
> harness-level classification, and §12.7/§18.5 refuse new evidence surfaces
> here.

> **The exit code is a statement about the harness, never a qualification
> verdict.** The verdict lives in the retained artifacts and the hard bar.

### 12.6 Frozen behaviours the runner does not touch

- **Corpus:** `run_primary_sweep` iterates `corpus.REQUIRED_TASKS`
  (IQ-1, IQ-2, IQ-3) in fixed order. The runner passes no task list and cannot
  reorder, subset, or extend it.
- **Stop behaviour:** the frozen `stop_after_indeterminate` logic in
  `run_primary_sweep` is used unchanged — after an indeterminate dispatch, the
  remaining tasks are `NOT_ATTEMPTED` with no artifact, and `hard_bar_result` is
  `INCOMPLETE`. The runner adds no override.
- **Budget:** `MAX_SEMANTIC_PROMPTS_PER_CANDIDATE = 3`, enforced by the frozen
  sweep on **dispatch attempts**. The runner adds no counter.
- **No retry, no continuation, no fallback** candidate, route, provider or model.
  There is no code path in the runner that calls `run_primary_sweep` twice.
- **No real workspace.** `run_primary_sweep` has no workspace parameter, and
  `run_semantic_task_attempt` mints its own via the frozen no-argument
  `mint_qualification_run_workspace()`. Real-workspace authority stays NO-GO by
  construction, not by check.

### 12.7 No retained sweep-summary artifact (FU1 BLOCKER 4 — REMOVED)

The pre-FU1 design proposed one bounded, retained sweep-summary JSON file under
`results/`. Independent review is right that it contradicts this same document's
§18.5, which refuses **a new artifact kind** in this line of work. A retained
sweep-level JSON is exactly that: a new artifact kind, with a schema nothing
else declares, at an implicit version 1, aggregating across tasks. The proposal
is **removed**, not narrowed.

> **Distinguish this from C4 (FU4A).** An earlier revision argued the point from
> a blanket "this project permits no schema or version change at all". That is
> now false and was always too strong. `5F3B-LIVE1-C4` **does** bump the three
> existing per-result artifact lineages to `.v2` to carry
> `qualification_policy_revision` (§10A.2b). The two are different acts:
>
> ```text
> C4      an EXISTING per-result artifact kind gains ONE declared field,
>         under a bumped version, for policy provenance that must travel
>         with a one-shot result.                              PERMITTED
>
> §12.7   a NEW, SWEEP-LEVEL artifact kind aggregating across tasks,
>         with a schema nothing declares and no retention policy.  REFUSED
> ```
>
> `LIVE1-I1` still writes no sweep-level file, and adds no artifact kind,
> schema or version of its own.

LIVE1's sweep-level reporting is therefore exactly:

```text
existing immutable per-task qualification / attempt artifacts
        (written by the frozen controller through emit_evidence_or_refuse;
         LIVE1 adds no field, no kind and no version to them)
    +
in-memory PrimarySweepResult
        (the frozen value object run_primary_sweep already returns; consumed
         inside the runner process and never serialized by LIVE1)
    +
one bounded console / operator summary
        (stdout only -- not a file, not retained, not an evidence record,
         and never read back by anything)
```

The console summary obeys the same disclosure discipline the removed artifact
would have: candidate, model id, phase, per-task outcome / gate statuses /
run validity / scoring eligibility / artifact **file name** / scrub outcome,
`confirmed_semantic_prompts_sent`, `semantic_dispatch_attempts`,
`indeterminate_dispatch_task_ids`, `not_attempted_task_ids`, `hard_bar_result`,
and `aido_requested_max_output_tokens: null`. Never prompt text, assistant text,
an absolute path, a base URL, an endpoint host, an API key, a broker token, a
pipe name, a capability id, an argv token, a Pi record, or exception text.
**File names only, never absolute paths.**

> **If a durable sweep-level aggregate is later required for M4**, that is a
> separate evidence-schema decision under its own authorization — it would need
> a declared kind, a declared version, a declared scrub contract and a retention
> policy. LIVE1 does not add one, and `LIVE1-I1` must contain no code that
> writes a sweep-level file.

---

## 13. Cleanup ownership (CDQ 10)

### 13.1 The frozen order is unchanged and authoritative

```text
runtime teardown
broker shutdown
generated-config cleanup
semantic workspace removal + verification
retained-evidence construction / scrub / emission
```

This is `run_semantic_task_attempt`'s unconditional CLOSURE block, and **LIVE1
does not touch it, reorder it, or add to it.**

### 13.2 What LIVE1's own lifecycle adds

The semantic transport is retired by, and only by, the delegated
`shutdown_runtime`:

```text
shutdown_runtime(session):
    require the transport is this adapter's own, for exactly this session
    observation = self._base.shutdown_runtime(session)     # frozen, unmodified
    self._transport.retired = True                          # AFTER the frozen call
    return observation
```

The rules the brief asks for, and how each is met:

| Requirement | How |
|---|---|
| one task → one live transport owner | one adapter per task, at most one transport per adapter (§3.2) |
| one `RuntimeSession` → exactly its own transport owner | three-id lookup; no global registry |
| teardown cannot target a foreign child | `self._base.shutdown_runtime` itself refuses a session it did not mint (`_require_runtime_record`), and the semantic wrapper refuses first |
| successful teardown retires the owner | `retired = True`, terminal; every semantic port refuses afterwards |
| failed teardown truth is preserved | the frozen `RuntimeShutdownObservation` is returned **unmodified**; `retired` is adapter-private bookkeeping and is never folded into, mixed with, or allowed to contradict the frozen closure record the controller reads |
| no later task inherits stale stream state | the adapter (and its transport) is unreachable once the task returns; the next task constructs a new one (matrix cases 22, 23, 24, 25) |

**Adapter-private retirement never erases frozen cleanup truth.** The controller
derives `RuntimeTeardownStatus` / `BrokerShutdownStatus` /
`SemanticCleanupStatus` / `SemanticWorkspaceRemovalStatus` from the frozen
observations and its own closers; LIVE1 contributes no field to any of them.

### 13.3 Residual limits, stated honestly

`PiRpcSupervisor.shutdown()`'s own `claim_scope` string is retained by the frozen
code and applies here verbatim: **AIDO stopped waiting and signalled only the
DIRECT child.** LIVE1 adds no job object, no `taskkill`, no process group, no
`psutil`, and no descendant enumeration, and must never claim that inference
stopped, that GPU work stopped, that a provider request was cancelled, or that
any descendant was terminated. `RecordStreamReader`'s daemon thread and its pipe
handle may outlive the run; that is a documented residual limitation, not
something LIVE1 fixes.

---

## 14. Explicit frozen contracts reused unchanged

| Contract | Reused how |
|---|---|
| `SemanticPromptRequest` / `SemanticPromptDispatchObservation` / `SemanticPromptDispatchState` / `SemanticDispatchEvidenceCode` / `DISPATCH_EVIDENCE_CODE_STATES` | imported and constructed; three states, ten codes, no additions |
| `SemanticTurnRequest` / `SemanticTurnObservation` / `SemanticTurnOutcome` | imported; three outcomes, no additions |
| `BrokerActivityObservation`, `FinalReportClaimsObservation`, `ReportClaims` | imported; no new fields |
| `qualification.scope.RefusalEvent` and its attribution functions | consumed, never reimplemented |
| `run_semantic_task_attempt`, `run_primary_sweep`, `TaskAdapterBundle`, `PrimarySweepResult` | called; not modified |
| `semantic_attempt` attempt-artifact machinery | untouched by `LIVE1-I1`; reached only through the controller. Its header gains C4's one field (§10A.2b) |
| `validity`, `outcomes`, `hard_bar`, `lineage` | untouched by every phase in this line of work |
| `records`, `semantic_attempt`, `safety` | **untouched by `LIVE1-I1`**, and reopened by **C4** for the policy-revision field and the `.v2` version bumps only (§10A.2b/§10A.2c). `safety`'s scrub, exclusive-create write and emit/refuse choke point are unchanged |
| `ranking` | **untouched by `LIVE1-I1`**, and reopened by **C3** for the R-2 derivation, R-3 symmetry and the policy-revision comparison (§9.4.8, §10.6.2a, §10A.3) |
| `semantic_workspace` | **untouched by `LIVE1-I1`**, and reopened by **C1** for the C1-P12a Git checkpoint only (§2.6.5b) |
| `ar2.supervisor` (`PiRpcSupervisor`, `RunBounds`, outcome constants) | used as-is: `send_command`, `await_response`, `await_settled`, `stdout_state`, `sanitized_events`, `activity`, `shutdown` |
| `ar2.protocol` (`RecordStreamReader`, reasoning drop) | used as-is, via the supervisor |
| `ar2.broker` / `ar2.capability` / `ar2.candidate` / `ar2.operations` | read-only consumption of `RunState` / `BrokerDiagnostics` |
| `ar2.observation.observe_repository`, `ar2.verification.run_verification` | called by the controller, not by LIVE1 |
| `LiveCategoryBAdapters` (13 zero-prompt ports), `AuthenticatedB300RouteObserver`, `build_authenticated_route_checker`, `resolve_pi_identity` / `IssuedRuntimeIdentity`, `_ar2_resolve_node_executable`, the eight Category-A preflight gates | composed and delegated to, unmodified. FU1 changed only **when** `resolve_pi_identity` runs (§12.2A), never what it does |
| `RunBounds.startup_deadline_seconds` / `.turn_deadline_seconds` | reused as the two waits; no new timeout policy |
| `corpus.REQUIRED_TASKS` / `TASKS_BY_ID` / `QualificationTask.prompt` / `.task_revision` | the sole prompt authority |

---

## 15. A/B fairness proof strategy (CDQ 12)

### 15.1 What may differ, and it is only this

`CANDIDATE_MODEL_IDS = {"A": "qwen3-coder-next", "B": "minimax-m2.7"}`.
`RouteDescriptor` fixes `provider_id`, `backend_gateway_class`,
`credential_mechanism` and `credential_env_var_name` to single constants for both
candidates, so **the only value that differs between A and B is `model_id`**
(and the `candidate` label itself).

### 15.2 Structural guarantees

- `LiveSemanticAdapters` takes **no** `candidate`, `model`, `model_id`,
  `provider` or `route` parameter. It cannot behave differently per candidate
  because it is never told which candidate is running.
- The candidate flows to exactly two frozen consumers:
  `run_primary_sweep(candidate=...)` and
  `build_authenticated_route_checker(candidate=...)`, both of which resolve it
  through the frozen `route_descriptor_for_candidate`.
- The two waits, the prompt corpus, the command shape, the gate order, the
  cleanup order and the artifact logic contain no candidate-conditioned branch.

### 15.3 How offline tests demonstrate it mechanically

1. **AST — no candidate identity in the adapter module.**
   `qualification/semantic_live_adapters.py` contains no string literal `"A"` or
   `"B"`, no reference to `CANDIDATE_MODEL_IDS`, and no parameter named
   `candidate` / `model` / `model_id` / `provider`.
2. **AST — no candidate-conditioned branch in the runner.** No `if` / `elif` /
   `match` in `run_semantic_sweep_live.py` whose test expression mentions
   `candidate`; exactly one `run_primary_sweep` call site.
3. **Differential trace test.** Drive one deterministic fake transport and fake
   broker state through the whole sweep twice, once with `candidate="A"` and once
   with `"B"`, recording every adapter method call, every command dict written,
   both wait timeouts, and the gate-status map. Assert the two traces are
   **identical after substituting the model id** — and specifically that the
   `prompt` command dicts are byte-identical (matrix case 26).

---

## 16. Offline regression matrix for `5F3B-LIVE1-I1` (FU1-revised)

Every case runs with **no Pi, no Node, no broker process or named pipe, no
credential, no socket, no network, no B300, no model**. Fakes: a deterministic
fake record stream / fake child transport standing in for `PiRpcSupervisor`, and
a synthetic `RunState` + `BrokerDiagnostics` pair standing in for broker state.
Any test touching Git uses a synthetic repository under pytest `tmp_path`.

### 16.1 The 30 required cases

| # | Case | Expected |
|---|---|---|
| 1 | correlated prompt response `success: true` | `CONFIRMED_SENT` / `PROMPT_RESPONSE_ACCEPTED` |
| 2 | correlated prompt response `success: false` | `CONFIRMED_NOT_SENT` / `PROMPT_RESPONSE_REFUSED` |
| 3 | `send_command` raises (write/flush failure) | `SEND_STATE_INDETERMINATE` / `WRITE_FAILED_TRANSMISSION_UNKNOWN` |
| 4 | no correlated response before the phase-1 deadline | `SEND_STATE_INDETERMINATE` / `NO_CORRELATED_RESPONSE_DEADLINE` |
| 5 | stream terminal (each of the five) before acknowledgement | `SEND_STATE_INDETERMINATE` / `NO_CORRELATED_RESPONSE_STREAM_TERMINAL` |
| 6 | a response carrying a foreign id (`"h9"`) | never establishes a send; falls through to D/E |
| 7 | dispatch observation for a foreign run/session/task/revision | refused; the controller records `OBSERVATION_MALFORMED_OR_FOREIGN` / indeterminate |
| 8 | `agent_settled` arrives during the phase-1 wait | preserved; phase 2 returns `SETTLED` without a second wait |
| 9 | `agent_end` alone | never `SETTLED`; `agent_end_observed=True` |
| 10 | repeated `agent_end` (incl. `willRetry`) | never `SETTLED` |
| 11 | `agent_settled` | `SETTLED` |
| 12 | stream failure after `CONFIRMED_SENT` | `OBSERVATION_FAILED`; `semantic_prompts_sent` stays `1` |
| 13 | phase-2 deadline | `DEADLINE_REACHED`; send fact stays `CONFIRMED_SENT` |
| 14 | broker counts/refusals are same-run and bounded | counts, `edited_paths`, `RefusalEvent`s within frozen caps |
| 15 | foreign broker / foreign runtime session substituted | refused; no handler read, no observation minted |
| 16 | final claims unavailable / malformed | non-gating; `run_validity` and `scoring_eligible` unchanged |
| 17 | exact frozen task prompt sent; no caller substitution possible | command `message == task.prompt`; no prompt parameter exists |
| 18 | wrong `task_revision` | refuses **before** the write; `CONFIRMED_NOT_SENT` / `GATE_REFUSED_BEFORE_WRITE`; `send_command` call count 0 |
| 19 | exactly one prompt command for one task | one `type:"prompt"` write across the whole task |
| 20 | no continuation/retry call site | AST: one `send_command` call with `"prompt"`; no second dispatch path |
| 21 | no `maxTokens`/`max_tokens` emitted | command dict keys exactly `{"id","type","message"}` |
| 22 | fresh adapter and transport per task | three tasks → three adapters, three transports, no shared object |
| 23 | no cross-task buffered records | a record in task 1's fake stream is invisible to task 2 |
| 24 | teardown retires only its own owner | `shutdown_runtime` retires this transport and touches no other |
| 25 | stale/foreign runtime session cannot reach another child | refused before any supervisor method is called |
| 26 | A/B exercise the same code path except frozen identity | differential trace test (§15.3) |
| 27 | runner has no default candidate and no run-both path | `--candidate` `required=True`, `default is None`; one `run_primary_sweep` call site |
| 28 | runner cannot accept an arbitrary workspace | no workspace-ish option in the parser; no workspace parameter downstream |
| 29 | `LiveCategoryBAdapters` remains structurally zero-prompt | the frozen module test still passes; `isinstance(LiveSemanticAdapters(...), LiveCategoryBAdapters)` is `False` |
| 30 | LIVE1 imports frozen PRE1 types rather than declaring competing ones | AST: no class named `*DispatchObservation`/`*TurnObservation`/`*ActivityObservation`/`*ReportClaims*` is defined in the new modules |

### 16.2 Additional cases, each protecting a seam found during source inspection

| # | Case | Seam it protects |
|---|---|---|
| 31 | `"s1"` is unused before the write; `"h1"`/`"h2"` are never reused | §7.2 id allocation |
| 32 | a parse response present **before** the baseline does not establish `COMMAND_UNPARSEABLE_REFUSED` | §7.6.3 |
| 33 | `success:false` **and** agent-run records observed | contradiction → raise → `ADAPTER_RAISED` / indeterminate, never a determinate state |
| 34 | `success` is `"true"` / `1` / `0` / missing | never a determinate state (`type(x) is bool` first, then identity) |
| 35 | `agent_settled` absorbed during phase 1 | phase 2 returns `SETTLED` with zero additional waiting |
| 36 | refusal reason containing a colon (`unsafe_lexical_form:CanonicalPathError`) | §9.3 `split(":", 2)` preserves it intact before projection |
| 37 | `changed_file_budget_exhausted` → `is_third_distinct_implementation_file=True`, pinned to `max_changed_files_per_run == 2` | §9.3 hard-disqualifier derivation |
| 38 | a broker count above a frozen `BrokerActivityObservation` cap | fails closed to `call_succeeded=False`; never clamped |
| 39 | the dispatch command dict has exactly three keys | §7.2 / unlimited-output policy |
| 40 | source-drift guards on every frozen surface LIVE1 reads: `PiRpcSupervisor.{send_command, await_response, await_settled, stdout_state, sanitized_events, shutdown, activity, process, stdin_write_error}`, `RuntimeActivity.{settled, agent_end_count, agent_end_will_retry_count, event_type_counts, responses, unmatched_response_ids, final_assistant_text}`, `RunState.{consumed, mutated_paths}`, `ConsumedBudgets.{read_operations, edit_operations}`, `BrokerDiagnostics.refusal_reasons`, `_LiveBrokerRecord.handler`, `_LiveRuntimeRecord.supervisor` | every assumption in §§3–10 |
| 41 | `LiveSemanticAdapters` is not a subclass; `base_for_route_authority()` satisfies `type(x) is LiveCategoryBAdapters` | §11.1 |
| 42 | exactly two private-attribute reads of `_base` in the semantic module (AST count) | §11.3 |
| 43 | the adapter never writes a command while a wait is outstanding | §7.6.1 U1/U2 |
| 44 | the runner's parser declares exactly the two declared options | §12.1 |
| 45 | Pi 0.84.4 seam-shape drift guard for the `prompt` request/response arms and the id-less `parse` arm | §2.1–§2.3 |

### 16.3 FU1 additions — per-task ordering (BLOCKER 2)

| # | Case | Seam it protects |
|---|---|---|
| 46 | **`build_adapters(task)` performs zero subprocess activity.** Patch `subprocess.run`/`Popen` (and `resolve_pi_identity`) with call counters, build the bundle for each of IQ-1/2/3, assert every counter is `0` — and additionally that no `IssuedRuntimeIdentity` was minted, no `LiveCategoryBAdapters` was constructed, no environment read occurred, and no broker/pipe/runtime object exists | §12.2A.1, §12.3 |
| 47 | **each task's non-secret gates precede its identity probe.** Drive the frozen `run_semantic_task_attempt` with a recording adapter and an ordered event log; assert every one of the eight gate callables was invoked, in order, strictly before the activation event, which is strictly before the credential read | §12.2A.1–.3 |
| 48 | **a failed preflight means zero identity probe and zero credential read.** Make gate *k* (for each *k* in 1..8) return `passed=False`; assert probe count `0`, `LiveCategoryBAdapters` construction count `0`, `read_connection` delegation count `0`, broker/runtime/route-observation counts `0`, prompts `0` — and that the attempt's failed gate is `NON_SECRET_PREFLIGHT` | §12.2A.5 |
| 49 | **A/B use identical ordering.** Run case 47's ordered event log for `candidate="A"` and `"B"`; assert the two logs are identical after substituting the model id | §12.2A.5, §15.3 |
| 50 | **no port other than `read_connection` activates.** For each of `create_broker`, `launch_runtime`, `get_commands`, `get_state`, `observe_protocol`, the route-checker binder, all four semantic ports, `shutdown_runtime`, `shutdown_broker`: call it on an unactivated adapter and assert it raises/refuses **and** that the probe counter is still `0` | §12.2A.3 A3 |
| 51 | **the runner's `node_executable` equals the per-task issued identity's.** Assert the runner's `_ar2_resolve_node_executable()` value equals what the adapter's trusted-resolution check binds, with a synthetic resolver | §12.2 |
| 52 | **the route-checker binder never activates and constructs exactly one observer.** Unactivated → refuses with no activation; activated → constructs the frozen observer once, and a second `checker(...)` call hits the frozen observer's own single-observation refusal, not a second observer | §12.2A.4 R1–R5 |
| 53 | **the binder's constructor surface is exactly two parameters** (AST/signature inspection): no transport, client, requester, sender, session, http_client, request_callback, base_url, api_key, endpoint, provider or model_id parameter | §12.2A.4 R1 |
| 54 | **`LiveSemanticAdapters` has no `runtime_identity` parameter** and no parameter named `candidate`/`model`/`model_id`/`provider`/`capability_source`/`capability_factory`/`sed`/`domain` (signature inspection) | §12.3, §15.2, §2.6.4 C1-P7 |
| 55 | **activation is one-shot**: a second `read_connection` raises and issues no second probe | §12.2A.3 A2 |

### 16.4 FU1 additions — no sweep artifact (BLOCKER 4)

| # | Case | Seam it protects |
|---|---|---|
| 56 | **the runner writes no sweep-level file.** Run the whole sweep against fakes into a `tmp_path` results directory; assert the only files created are the frozen per-task artifacts the controller emitted, named exactly `<candidate>_<task_id>.json` — no additional file of any name | §12.7 |
| 57 | **AST: the runner contains no serialization call site** — no `json.dump`/`json.dumps`-to-file, no `open(..., "w")`, no `Path.write_text`/`write_bytes`, no `emit_evidence_or_refuse` call | §12.7, §18.5 |
| 58 | **the console summary discloses nothing forbidden.** Feed a `PrimarySweepResult` built from fakes carrying planted needles (a fake base URL, a fake token, an absolute path, a pipe name, a capability id, assistant text) and assert none appears in captured stdout | §12.7 |

### 16.5 Cases that belong to the correction phases, not to `LIVE1-I1`

Recorded here so the boundary is explicit and no one implements them early.

| Owner | Case |
|---|---|
| **C1** (§2.6) | the issued capability's `read_eligible` equals the frozen-mint result over the **observed** `ls_files_stage` manifest; the observed manifest and `task.case.files` disagreeing **refuses**; witnesses are never write-eligible; a capability issued for task *i* is refused for task *j*, for another run id, for another workspace nonce, and for another `task_revision`; a second issuance for one workspace nonce refuses; no `DisposableRootAuthority` is reachable from any public surface or `repr`; **issuance happens at `create_broker`, never at `read_connection`** (§2.6.4a); T1–T6 of §2.6.5a (Category-B issues zero Git operations; byte-identical inert domain; the semantic path is unreachable without a bound task; the amended, strengthened purity test); **T7–T14 of §2.6.5b** (every Git argv[0] in the attempt is the accepted resolver's result; an arbitrary caller string, or a workspace-local executable, refuses at the **fixture-population checkpoint** with zero Git subprocesses and zero fixture writes; the checkpoint is ordered before every other Git consumer; the Pi child's PATH carries the resolved identity's directory; nothing may **override** the resolver — PATH remains its legitimate input); `LiveSemanticAdapters` has **no** `git_executable` parameter |
| **C2** (§9.4.3) | the projection is total over the **pair** `(error_code, internal_reason)` and over an extracted enumeration of **both** every literal reason **and** every dynamic construction site in frozen `ar2.candidate`/`ar2.operations`/`ar2.broker` (§9.4.3.1's six sites, by site and shape); `occurrence_count_<N>` for several `N` all project to one closed code; `unauthorized` → `unauthorized` and `protocol_error` → `protocol_terminal` from the bounded code alone; `too_large` and `budget_exhausted` split correctly on the pair; **every dynamic family — `unsafe_lexical_form:*`, `canonical_guard:*`, `path_policy:*` (which can embed a PATH), `WireProtocolError` `str(exc)` (candidate-authored text), exception-class diagnostics — reduces to `unrecognized_broker_reason`, and no candidate- or runtime-controlled substring reaches `refusal_categories` or any retained field**; adding a NEW dynamic reason source to frozen AR2 breaks the suite loudly; exactly one call site exists; `ar2` is read, never edited |
| **C4** (§10A.2b, §10A.2c) | one and only one `QUALIFICATION_POLICY_REVISION` declaration site (AST); `RECORD_VERSION` → `pi-implementer-qualification.v2`; `ATTEMPT_RECORD_VERSION` → `pi-implementer-qualification-attempt.v2`; `REFUSAL_RECORD_VERSION` → `pi-implementer-qualification-refusal.v2`; the primary header carries the revision; the attempt header carries the revision; the refusal fallback carries the **same** revision; `semantic_attempt`'s closed top-level key set is updated to admit the new field; a scrub-clean primary/attempt/refusal record passes emission; a deliberately scrub-rejected payload still produces a refusal artifact carrying the revision; the refusal record gains **no** new runtime, candidate, task, path or credential field beyond it; `lineage` continues to bind `.v2` primary records without modification |
| **C3** (§9.4.8, §10.6, §10A) | **R-2 derivation (§9.4.8):** the nine-case table — `N=0`→`CLEAN`; `N=1` unique and `N=2` two-unique→`MINOR_FRICTION`; `N=2` same code twice, `N=3` three-unique, and the same code once in two different IQ tasks→`REPEATED_FRICTION`; negative/bool/non-int counts, `n_t < |S_t|`, a task set that is not the three frozen tasks, and any surviving contradictory caller-supplied bucket all **REFUSE**. **R-3 symmetry (§10.6.2a):** `None`/`None`→skipped; `bucket`/`bucket`→compared in the frozen `_R3_ORDER`; either one-sided case→**refused**; with `R3_EVALUABLE=False` every profile carries `r3=None` and a supplied bucket is refused, never ignored; two profiles differing only in R-3 compare `"tie"`. **Evidence authority (§9.4.8 C3-R2-1a…1c):** the resolver derives from each task result's own `scope_result` (issuance-backed, unswappable); a profile built solely from freely authored counts/categories is **not authoritative**; a test pins that a `CandidateRankingProfile` is **not** claimed to be a selection authority — the aggregate `PrimarySweepResult` is publicly constructible and attests nothing about issuance; AST — `qualification.ranking` has no `open`, no `Path.read_*`, no `json.load` and no path parameter. **Policy revision (§10A.3):** same revision→compares; different revisions→**refuses**; `build_profile` stamps the constant C4 declared. `ReportAccuracyBucket` and `OperationBucket` gain no member, `bucket_report_accuracy`'s return type is unchanged, R-4's existing skip behaviour is untouched, and **no record schema is widened** |

**58 offline regression cases designed for `LIVE1-I1`** (45 carried forward, 13
added by FU1), plus the four correction phases' own cases. No test in any of
these matrices launches a process, opens a socket, or reads a credential.

---

## 17. Security and evidence-safety review

| Concern | Assessment |
|---|---|
| Credential handling (runtime design) | **Corrected in FU2.** An earlier revision said "LIVE1 reads no credential", which is false for the shipped runtime: the semantic layer's `read_connection` is on the path that reads the B300 credential. The truthful invariant is: **LIVE1 introduces no second credential reader**; the semantic layer never parses, transforms, logs, retains, echoes or re-derives a credential value; and **exactly one** credential read occurs per task, delegated verbatim to the frozen `LiveCategoryBAdapters.read_connection`, after all eight of that task's non-secret gates have passed (§12.2A). `LiveSemanticAdapters` has no `environ` access of its own beyond the injected reader it forwards, holds no credential field, and exposes no accessor that returns one. The frozen `consumed_connection_values()` remains the single same-run authority source for the route observer. |
| Credential handling (this design turn) | **Zero credential reads occurred in producing this document.** It is source inspection only: no environment variable was read, no `.env` was opened, no endpoint or key was resolved, and B300 was not contacted. This is a statement about the turn, and is kept separate from the runtime invariant above so neither is ever read as the other. |
| Ordering | Unchanged: the frozen controller's gate order still puts `SECRET_CONTEXT` before `BROKER_SESSION`, and the credential boundary before the runtime launch. |
| Prompt/source transmission | Exactly one message crosses to the model: the frozen corpus prompt for this task. Never a file, a tree, a listing, git history, an absolute path, a credential, or an artifact. |
| Reasoning | Structurally dropped at ingestion by frozen `ar2.protocol`; LIVE1 never reads `message.reasoning`, thinking blocks, or delta records, and adds no chain-of-thought observability. |
| Raw log retention | None. LIVE1 derives only booleans, small integers, bounded enum members and one record **count**. No Pi record, `error` string, assistant text or usage blob is retained. |
| Evidence emission | Untouched. Every artifact still goes through `safety.emit_evidence_or_refuse` (exclusive-create, scrub-checked, bounded refusal fallback). LIVE1 adds no artifact kind and no schema version. |
| `ArtifactSafetyContext` | Untouched; the controller still builds it field-independently and refuses rather than defaults on an unexpected credential mechanism. |
| Sweep-level reporting | **No sweep-level artifact is written (§12.7).** The bounded operator summary is stdout only: file names, never absolute paths; no host, no URL, no token, no pipe name, no capability id, no argv token, no assistant text, no exception text. |
| Untrusted-runtime posture | Pi remains an untrusted agent-loop runtime. LIVE1 makes its semantic surface reachable; it does not make it trusted. The model's self-report is non-authoritative and, in this design, not even collected (§10). |
| Sandboxing claims | None made. The launched Pi process is not confined and its descendants are not tracked; every AIDO-owned negative claim keeps its `orchestrator_` scoping through the frozen record builders. |
| Exception text | No LIVE1 refusal message interpolates a runtime value; the accepted "fixed literal or `type(exc).__name__` only" discipline is carried over and is testable by the existing AST pattern. |

---

## 18. Verdict, correction sequence, and what LIVE1 refuses to implement

### 18.1 Verdict — FU4A

```text
5F3B-LIVE1-DESIGN-FU4A            DESIGN READY FOR C1

All five FU4A items are closed at DESIGN level:
    ITEM 1  C1 module boundary made consistent EVERYWHERE: THREE production
            modules (i2b_workspace, i2b_live_adapters, semantic_workspace);
            P12a tightened to EXACT STRING EQUALITY, no realpath/alias test
                                                 -> Sec. 2.6.5a, 2.6.5b, 2.6.6,
                                                    18.2, 18.5
    ITEM 2  QUALIFICATION_POLICY_REVISION identifies the WHOLE implementer
            ROLE_CAPABILITY policy, not just R-1..R-4  -> Sec. 10A.3 C3-PR-4
    ITEM 3  the safety-refusal fallback artifact carries the SAME revision;
            REFUSAL_RECORD_VERSION -> .v2; C4 also reopens qualification.safety
                                                 -> Sec. 10A.2b, 10A.2c
    ITEM 4  WITHDRAWN: PrimarySweepResult is NOT an issued sweep authority.
            C3 owns policy mechanics only; M4 owns all authoritative
            ranking-input derivation and selection    -> Sec. 9.4.8 C3-R2-1a..1c
    ITEM 5  canonical-consistency pass over Sec. 2.6.5a, 2.6.6, 9.4.6, 12.7,
            14, 18.1..18.5

All three FU4 items remain closed at DESIGN level:
    ITEM 1  Git authority extended to FIXTURE POPULATION and proved to bind all
            four consumers from ONE earliest checkpoint  -> Sec. 2.6.5b (C1-P12a,
            T7..T14); PATH wording corrected to OVERRIDE-impossibility
    ITEM 2  qualification_policy_revision binds DURABLY, WITH the result, before
            Q1; record schema bump to .v2 required and owned by the new
            5F3B-LIVE1-C4                                -> Sec. 10A.2 .. 10A.4
    ITEM 3  policy math split from evidence authority; C3/M4 boundary stated
            -> Sec. 9.4.8. (FU4A CORRECTED its overclaim that the whole sweep
            graph is an issued authority -- see FU4A item 4 above.)

All three FU3 blockers + the provenance clarification remain closed:
    BLOCKER 1  Git executable bound as authority -> Sec. 2.6.5b (C1-P12, T7..T12)
               and the adapter's git_executable parameter is REMOVED
    BLOCKER 2  C2 projects the (error_code, internal_reason) PAIR; six dynamic
               reason sources accounted for; drift guard covers literal AND
               dynamic sites                     -> Sec. 9.4.3.1 .. 9.4.3.3
    BLOCKER 3  R-2 is an AIDO-owned derivation, never a caller-authored bucket
                                                 -> Sec. 9.4.8
    PROVENANCE policy-revision identifier at the ranking boundary -> Sec. 10A.
               (FU4 SUPERSEDED its "durable binding deferred to M4" outcome;
               C4 now binds it before Q1 -- Sec. 10A.2.)

All five FU2 closure items remain closed at DESIGN level:
    ITEM 1  C1 issuance timing corrected  -> Sec. 2.6.4a (+ C1-P3, 12.2A, 12.3)
    ITEM 2  i2b_workspace invariant       -> Sec. 2.6.5a (Option A, T1..T6)
    ITEM 3  R-3 symmetry invariant        -> Sec. 10.6.2a
    ITEM 4  R-2 thresholds FROZEN         -> Sec. 9.4.5
    ITEM 5  live-safety wording corrected -> Sec. 12.2, Sec. 17
  + R-2 retained-evidence sufficiency PROVED -> Sec. 9.4.6

All four FU1 review blockers remain closed at DESIGN level:
    BLOCKER 1  capability authority seam   -> Sec. 2.6 (binding properties
                                              C1-P1..C1-P12 + derivation table
                                              + exact modules to reopen)
    BLOCKER 2  per-task ordering           -> Sec. 12.2A (+ 12.2, 12.3, 12.4)
    BLOCKER 3A R-2 evidence / vocabulary   -> Sec. 9.3, 9.4
    BLOCKER 3B R-3 not evaluable           -> Sec. 10.6
    BLOCKER 4  no new sweep artifact       -> Sec. 12.7 (proposal REMOVED)

The accepted Pi seam, stream ownership, dispatch/turn algorithms, adapter
composition semantics, cleanup ownership, A/B fairness and security posture
                                  remain UNCHANGED and DESIGN READY
(Sec. 14 and Sec. 16.5 were edited for canonical consistency in FU4A -- the
CONTRACTS they describe were not reopened, only the module-boundary bookkeeping
around C1/C4/C3)

5F3B-LIVE1-C1  capability issuance seam        REQUIRED, NOT YET AUTHORIZED
               (+ Git execution authority)
5F3B-LIVE1-C2  refusal vocabulary projection   REQUIRED, NOT YET AUTHORIZED
5F3B-LIVE1-C4  qualification-record policy      REQUIRED, NOT YET AUTHORIZED
               binding (.v2 schema bump)        <-- NEW in FU4; lands BEFORE C3
5F3B-LIVE1-C3  R-2/R-3 policy revision +       REQUIRED, NOT YET AUTHORIZED
               policy-revision identifier

5F3B-LIVE1-I1                     NOT AUTHORIZED, and blocked until C1, C2, C4
                                  and C3 are accepted
Q1 / Q2 / real workspace          NO-GO (unchanged)
```

**Nothing blocks C1 on this design.** FU1's two open items were closed by FU2
(the R-2 threshold is frozen in §9.4.5; §11.3's READ 1 is answered conditionally
— deleted if C1's `create_broker`-time issuance carries the handler, kept
otherwise), and FU3's three blockers are closed above.

**No gap remains open.** FU3 reported one — the durable policy-revision binding
had no home before M4. FU4 closes it: `5F3B-LIVE1-C4` binds it into all three
per-result durable artifact lineages before Q1 (§10A.2b), and M4's decision artifact remains
required but **additive** (§10A.4). C1 may be authorized on this document as it
stands.

### 18.2 The exact correction phases required before `5F3B-LIVE1-I1`

**Four**, each narrow, each independently reviewable. **None is implemented in
this turn.**

| Phase | Closes | Frozen modules reopened | Must land before |
|---|---|---|---|
| **`5F3B-LIVE1-C1`** — capability issuance seam + Git execution authority | BLOCKER 1, FU2 items 1–2, FU3 blocker 1, FU4 item 1 | **Production — THREE modules:** `qualification.i2b_workspace` (one-shot issuance + registry, **plus** the semantic-only read-only Git observation, **plus** the narrowed docstring invariant — §2.6.5a); `qualification.i2b_live_adapters` (issued capability **at `create_broker`**, never at activation — §2.6.4a; inert Category-B default byte-identical); `qualification.semantic_workspace` (**the C1-P12a fixture-population Git checkpoint — §2.6.5b**; required, because this module performs the attempt's first Git execution). **Tests:** `tests/test_i2b_controller.py`'s purity test amended and strengthened (§2.6.5a T5). **Not touched:** every `ar2` module, `semantic_controller`, `semantic_sweep`, `BrokerCreationRequest`, `tests/test_i2b_live_adapters.py` | `LIVE1-I1` |
| **`5F3B-LIVE1-C2`** — refusal vocabulary projection | BLOCKER 3A part A, FU3 blocker 2 | **Production:** one **new** qualification module holding the total `(error_code, internal_reason)` → closed-vocabulary projection (§9.4.3.3); `qualification.scope` **doc-only** correction of the "exact code the broker produces" sentence. **Not touched:** every `ar2` module — the drift guard *reads* AR2 source and never edits it; `scope`'s executable behaviour, its three code sets, and `RefusalEvent`'s field set | **Q1** (and, because §11/§12 consume it, before `LIVE1-I1`) |
| **`5F3B-LIVE1-C4`** — qualification-record policy binding | FU4 item 2, FU4A items 2–3 | **Production — FOUR modules:** `qualification/__init__.py` (declare `QUALIFICATION_POLICY_REVISION` — the single declaration site — and bump `RECORD_VERSION` → `pi-implementer-qualification.v2`, `ATTEMPT_RECORD_VERSION` → `pi-implementer-qualification-attempt.v2`, **`REFUSAL_RECORD_VERSION` → `pi-implementer-qualification-refusal.v2`**); `qualification/records.py` (one field in `record_header()`); `qualification/semantic_attempt.py` (the same field in `attempt_record_header()`, plus its own closed key set); **`qualification/safety.py`** (the same field as fixed metadata in `build_refusal_record()`, and the bumped constant it already consumes — §10A.2b). **Not touched:** every `ar2` module, `semantic_controller`, `semantic_sweep`, `semantic_session`, `semantic_workspace`, `i2b_*`, `scope`, `validity`, `outcomes`, `hard_bar`, `ranking`, `lineage`, `safety`'s scrub / exclusive-create write / emit-or-refuse choke point, the corpus, the prompts | **Q1**, and **before C3** (C3 imports the constant) |
| **`5F3B-LIVE1-C3`** — R-2/R-3 policy revision | BLOCKER 3B, BLOCKER 3A part B, FU2 items 3–4, FU3 blocker 3 + provenance | **Production:** `qualification.ranking` only — R-2 becomes an **AIDO-owned derivation** from primitive per-task evidence (§9.4.8 C3-R2-1…5); `r3_bucket`/`r3` become `\| None` with the **symmetric** four-case rule (§10.6.2a) and `R3_EVALUABLE = False`; a declared **qualification-policy-revision identifier** that `compare_profiles` refuses to compare across (§10A.3 C3-PR-1…5). **Policy:** `docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md` §18 (the frozen R-2 definitions of §9.4.5 + R-3 `NOT_EVALUABLE`). **Not touched:** `report_accuracy` (no new `ReportAccuracyBucket` member), `bucket_report_accuracy`, `OperationBucket`, `_R2_ORDER`/`_R3_ORDER`, R-4's existing behaviour, `records.record_header` and every record schema/version, the corpus, the prompts | **Q1**, before any candidate semantic prompt |

Ordering among them: **C1 → C2 → C4 → C3 → `LIVE1-I1`**. Two edges are
mandatory and the rest is preference:

```text
C4 -> C3     MANDATORY. C3 imports the QUALIFICATION_POLICY_REVISION constant
             C4 declares, so there is exactly one declaration site.
C1 -> I1     MANDATORY. LIVE1-I1's Sec. 11.3 / Sec. 12.3 structurally depend on
             C1's issuance seam.
C2           independent of C1 and C4; may be reviewed in any order.
```

What is **not** negotiable is that **all four** precede Q1.

### 18.3 Frozen qualification-policy revision required — YES

Answering the brief's question explicitly:

> **Yes. One frozen qualification-policy revision is required, and it must be
> declared before any candidate semantic prompt is sent.**

It has two parts, both in
`docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md` §18, both carried by
`5F3B-LIVE1-C3`:

1. **R-3 is `NOT_EVALUABLE` for this revision** (§10.6). The frozen corpus and
   harness expose no structured, machine-readable claim channel; R-3 ranks
   neither candidate; both candidates are evaluated identically under the same
   revised policy.
2. **R-2's bucket definitions are replaced with the FROZEN thresholds of
   §9.4.5**: `CLEAN` iff `N == 0`; `MINOR_FRICTION` iff `N ∈ {1,2}` with no
   recurrence; `REPEATED_FRICTION` iff a projected soft code recurs or `N ≥ 3`
   — where `N` and recurrence are candidate-level across all three tasks.
   "Visibly self-corrected on the candidate's very next relevant operation" is
   **replaced**, not reinterpreted, because the frozen broker retains no
   ordered, interleaved, path-carrying accepted/refused operation sequence
   (§9.4.4) and no narrower qualification-layer source for it exists. §9.4.6
   proves the frozen record already retains everything the revised buckets
   need.

3. **R-3's comparison rule is symmetric** (§10.6.2a). A one-sided R-3 is an
   asymmetric qualification state and is **refused**, never skipped; both
   profiles are `None` by construction under `R3_EVALUABLE = False`.

4. **R-2 is derived by AIDO, not supplied** (§9.4.8). Without this the frozen
   thresholds would be documentation only — `RankingInput.r2_bucket` is
   caller-authored today and `build_profile` copies it verbatim.

5. **The revision is identified at the ranking boundary, and comparison across
   revisions is refused** (§10A.3) — **and it is durably bound into every
   one-shot result before Q1** (§10A.2b), via `5F3B-LIVE1-C4`'s `.v2` schema
   bump. FU3's deferral of that binding to M4 is withdrawn (§10A.2). M4's
   candidate-level decision artifact stays required and additive (§10A.4).

**A record schema revision is therefore required, and it must land before Q1.**
It covers **all three** per-result artifact lineages, because the safety-refusal
record replaces the other two whenever a payload fails the scrub and is then the
only durable artifact that attempt has (§10A.2b):

```text
pi-implementer-qualification.v1          -> .v2
pi-implementer-qualification-attempt.v1  -> .v2
pi-implementer-qualification-refusal.v1  -> .v2      (FU4A)
```

Each `.v1` keeps its original meaning — *a record carrying no policy-revision
binding* — and none may ever be read as though produced under a particular
revision. Since **no artifact of any of the three kinds has ever been emitted**,
the bump costs nothing archival. `lineage` needs no field and no edit: it
imports the `RECORD_VERSION` symbol and binds records by digest.

Both are **fair by construction**: declared before Q1, identical for Candidate A
and Candidate B, evaluated from the same frozen corpus over the same code path.
**No candidate semantic prompt has been sent (0)**, so neither revision is made
with a result in hand — which is precisely why they cannot be deferred.

Everything else in the frozen policy is untouched **except C4's explicitly
authorized `qualification_policy_revision` field and the three associated
schema-version bumps above**. Genuinely untouched: the corpus, the prompts, run
validity, the hard bar H-1..H-14, the outcome taxonomy, the prompt-count policy,
evidence policy, workspace policy, verification authority, candidate routes,
Category-B policy, the token policy, and real-workspace authority.

### 18.4 Roadmap impact — none

`AIDO_RUNTIME_HARNESS_ROADMAP.md` §4.5 is **not** edited. Its §4.5.3 sequencing
already reads:

```text
5F3B-LIVE1-DESIGN -> 5F3B-LIVE1-I1 -> independent adversarial review
                  -> correction phase(s) if required, on the FU pattern
                     used throughout 5F3B -> 5F3B-LIVE1 ACCEPT / FREEZE
```

C1/C2/C4/C3 are exactly those "correction phase(s) if required", arriving after
DESIGN review rather than after I1 — which is the same pattern, one step
earlier, and strictly safer. §4.5.2's rule that a required change to a frozen
item is *"a finding to report, not a change to make"* is what §§2.6, 9.4 and
10.6 do. No milestone moves, M2.5 remains M2.5, and Q1/Q2 remain gated on M2.5
being accepted and frozen plus their own separate authorization.

### 18.5 Explicit refusals — things LIVE1 will not implement

> **Scope of this list (FU4A).** These are the refusals that bind
> **`LIVE1-I1`**, and the ones that bind every phase. Where a refusal was
> written before C1/C4 existed and would forbid a change this design now
> *requires*, it is corrected here rather than left to contradict §2.6.6 and
> §10A.2c. Nothing else in the list is weakened.

No fourth dispatch state. **No NEW artifact kind — in particular no sweep-level
artifact (§12.7)** — and no new evidence code. `LIVE1-I1` itself adds no record
schema, no record version and no artifact kind of any sort.

**The only schema/version changes permitted anywhere in this line of work are
C4's**: one declared `qualification_policy_revision` field on the three existing
per-result artifact lineages, at `pi-implementer-qualification.v2`,
`pi-implementer-qualification-attempt.v2` and
`pi-implementer-qualification-refusal.v2` (§10A.2b). No other field, no other
kind, no other version.

No modification, by any phase, of `semantic_controller.py`,
`semantic_session.py`, `semantic_sweep.py`, `validity.py`, `outcomes.py`,
`hard_bar.py`, `lineage.py`, or any `ar2`/`o1` module. `semantic_workspace.py`
is modified by **C1 only**, for the C1-P12a Git checkpoint (§2.6.5b);
`records.py`, `semantic_attempt.py` and `safety.py` by **C4 only**, for the
field and the version bumps; `ranking.py` by **C3 only**. `LIVE1-I1` modifies
none of them. No NLP or prose claim extraction, no tolerant claim parsing, and no
candidate-specific report format. No `capability_source`, capability factory, or
caller-supplied eligibility domain. No caller-supplied manifest, protected
pattern, or witness path. No second `DisposableRootAuthority` origin, and no
authority object on any public surface. No semantic retry, continuation,
re-dispatch, backoff, poll, or reconnection. No `abort`, `abort_retry`,
`clear_queue`, `steer`, `follow_up`, `bash`, `compact`, `set_model`, or
`new_session` command. No streaming or progress inference. No
provider-inference-request observer. No second reviewer, fixer, consensus, or
model-backed implementer. No generic `AgentRuntime` / `Harness` interface,
harness registry, plugin seam, capability list, or Codex/DeepSeek
generalization. No fallback candidate, route, provider, or model. No "run both".
No automatic Q2. No real-workspace parameter. No process-tree management (job
objects, `taskkill`, process groups, `psutil`). No cancellation mechanism of any
kind. No ordered per-frame broker audit log (§9.4.5 Option 2 is refused for
LIVE1). No commit, push, branch, or PR.

### 18.6 Remaining questions for review

The five pre-FU1 questions are resolved as follows.

| # | Pre-FU1 question | FU1 disposition |
|---|---|---|
| 1 | §2.6 capability seam | **Resolved into a specification.** §2.6.4's C1-P1…C1-P12 lock WHAT; the mechanism is C1's to choose. Review decides whether to authorize C1 |
| 2 | §9.4 soft-code vocabulary gap | **Reclassified as a pre-Q1 frozen-contract gap** and specified as C2 (§9.4.3). No longer "recorded, not fixed" |
| 3 | §9.2 `RefusalEvent.path` unpopulatable | **Unchanged and still non-gating** — `qualification.scope` never reads it. FU1 adds that the same discarded `relative_path` is one of the four missing facts behind the R-2 sequence gap (§9.4.4), which is why the two findings are now reported together |
| 4 | §10.3 `UNAVAILABLE` as the truthful state | **Accepted by review**, and its consequence specified as C3 (§10.6) |
| 5 | §12.4 three `--version` probes per sweep | **Unchanged in count, corrected in placement**: three per sweep, one per task, each now strictly after that task's own Category-A gates (§12.2A) |

FU1's two open items are now closed:

| Was open in FU1 | FU2 disposition |
|---|---|
| **The R-2 count threshold** was left unpicked | **Frozen** in §9.4.5: `{1,2}` versus `≥ 3`, candidate-level, with recurrence as the second axis. §9.4.5 records that no stronger predeclared basis exists in source, that this is a policy choice rather than a derived quantity, and why it does not violate §11.3's no-numbers rule |
| **Whether §11.3's two private `_base` reads survive C1** | **Answered conditionally, which is the most that can be said before C1 exists.** If C1's `create_broker`-time issuance (§2.6.4a) also carries the `BrokerRequestHandler` binding, READ 1 is **deleted**, not kept; READ 2 (the supervisor) is expected to remain, and neither is expanded. This is a C1 acceptance check, not a LIVE1-I1 one |

**No gap remains open.** FU3's single reported gap — the durable
policy-revision binding — is closed by `5F3B-LIVE1-C4` (§10A.2b), which lands
before Q1 and before C3.

Three things are deliberately deferred to their own phases and are **not** gaps
here:

| Deferred | To | Why it is not a gap |
|---|---|---|
| C1's *mechanism* — an opaque handle, a sealed value object, or another narrow shape satisfying C1-P1…P12 | C1 | the **properties** are locked here; only the shape is open |
| C2's projection **table contents** | C2 | derived mechanically from frozen source under C2-P2/C2-P6, never authored by review |
| authoritative ranking-input derivation and candidate selection | M4 | genuine `SemanticTaskAttemptResult` per-task facts are issuance-backed (§9.4.8 C3-R2-1a); `PrimarySweepResult` is a public constructible aggregate and is **not** an issued sweep authority (§9.4.8 C3-R2-1a, FU4A-corrected); C3 owns policy mechanics only and its profiles are not authoritative candidate-selection artifacts (§9.4.8 C3-R2-1c); M4 owns durable-artifact validation/binding, authoritative derivation of ALL ranking inputs, and candidate selection, and is the **first** authoritative selection boundary; building a generic evidence framework now is explicitly refused |

---

## 19. Files changed by this turn (FU4A)

| File | Change |
|---|---|
| `docs/PHASE_5F3B_LIVE1_PI_SEMANTIC_LIVE_LAYER_DESIGN.md` | **revised** — this document. FU4 touched: the title/banner/header table; §0 (restructured into §0.1 FU4 + §0.2 FU3 + §0.3 FU2 + §0.4 FU1); §2.6.4's C1-P12 (now P12a + P12b); §2.6.4a's EVENT 2 actions; §2.6.5's derivation table row; §2.6.5b (**substantially rewritten** — the four-consumer Git execution graph, the fixture-population checkpoint C1-P12a, corrected PATH/override wording, T7–T14); §9.4.8 (**rewritten** C3-R2-1…5 — policy math vs evidence authority, C3-R2-1a/1b, the C3/M4 boundary, four new regression rows); §10A.2/.2a/.2b/.2c (**rewritten** — the "policy-neutral" claim withdrawn, the `.v2` schema decision, the new C4); §10A.3's C3-PR-1/5/6; §10A.4 (**new** — M4's additive requirement); §12.3's `git_executable` bullet; §18.1–§18.3, §18.6; §19 |

FU4A additionally touched: the title/banner/header table; §0 (restructured into
§0.1 FU4A + §0.2 FU4 + §0.3 FU3 + §0.4 FU2 + §0.5 FU1); §2.6.5a's production-module
list (**three**); §2.6.5b's P12a equality rule and its four-consumer proof;
§2.6.6 ("exactly three", the new `semantic_workspace` row, the per-phase tail);
§9.4.6's scoping note; §9.4.8's C3-R2-1a/1b and the **new C3-R2-1c** authority
split; §10A.2b (the refusal artifact, lineage) and §10A.2c (four C4 modules);
§10A.3's C3-PR-4; §12.7's C4-versus-sweep-artifact distinction; §14's per-phase
rows; §16.5's C1 and C3 rows; §18.1's verdict block and superseded markers;
§18.2's C1 and C4 rows and the ordering; §18.4; §18.5; §19.

The FU1, FU2, FU3 and FU4 change lists are superseded by this one.

No source file, no test, no frozen module, no accepted roadmap document, no
accepted planning document, and no `CLAUDE.md` was modified. Every citation
above is a read-only reference.

**The roadmap was NOT edited.** §18.4 states why: `AIDO_RUNTIME_HARNESS_ROADMAP.md`
§4.5.3 already provides for correction phases on the FU pattern, and none of
FU1's four findings changes a milestone, a dependency edge, or a gate.

**Nothing in this turn was implemented, and nothing was executed.** No runtime
module, no test, and no frozen AR1 / AR2 / AR2-O1 / I1 / I2 / I2B / PRE1 file
was created or modified. **No semantic prompt was sent (0), no model was called
(0), no Pi or Node process was launched (0), no broker or named pipe was opened
(0), no credential was read (0), no socket was opened and B300 was not contacted
(0).** Q1 and Q2 were not run. Nothing was committed, pushed, branched, or
opened as a PR.

**STOP for independent review.**
