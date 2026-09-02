# Phase 5F3B-I1 / I2 -- Pi Implementer Qualification Corpus + Offline Harness

> **NO MODEL QUALIFICATION HAS OCCURRED.**
> **NO CANDIDATE PASS/FAIL EXISTS YET.**
> **NO SEMANTIC PROMPT HAS EVER BEEN SENT.**
> **5F3B-Q1 / Q2 ARE NOT AUTHORIZED.**
> **CANDIDATE A IS NOT YET QUALIFIED (Category-B compatibility QUALIFIED /
> FROZEN; implementer qualification NOT YET QUALIFIED). CANDIDATE B IS NOT
> YET QUALIFIED (Category-B compatibility QUALIFIED / FROZEN, established by
> the single authorized zero-prompt live attempt; implementer qualification
> NOT YET QUALIFIED). The 5F3B-I2B-L1 Category-B compatibility workstream is
> now COMPLETE / FROZEN for both first-round candidates. No further
> Category-B live attempt is authorized for either candidate.**

> **Corrected 5F3B-I2B-L1: exactly ONE zero-prompt Category-B live attempt
> has now occurred** (Candidate A, `results/i2b_live_A_20260831T192543Z.json`,
> observed Pi `0.84.4`). It refused fail-closed at `required_launch_flags`
> having sent **zero** semantic prompts, and it tore down, shut down and
> cleaned up verifiably. It launched a real Node/Pi process, opened a real
> named pipe and read a real credential, so the two blanket claims that
> previously stood here -- "NO ZERO-PROMPT LIVE GATE HAS RUN" and "no
> Pi/Node process has ever been launched from this package" -- are no longer
> true and are corrected in place. **5F3B-I2B-L1-LF1** then established that
> the refusal's ATTRIBUTION was wrong (an adapter type defect, not an
> unknown-flag rejection) and corrected the producer; see
> [FINDINGS.md](FINDINGS.md) section "5F3B-I2B-L1-LF1". The live artifact
> itself is retained unedited. **No further live attempt is authorized.**
>
> **5F3B-I2B-L1-LF1-FU1** then found LF1's own correction still
> over-attributing: it computed `required_flags_accepted` as
> `argv_options_source_established and lf_jsonl_correlation_succeeded`, whose
> reverse implication does not hold — **no correlated response does not imply
> an unknown CLI flag was rejected** — so *every* correlation failure (a
> deadline, a launch-window protocol violation, an output cap, an event cap, a
> read error, a generic early exit) was reported as
> `REQUIRED_LAUNCH_FLAGS_REJECTED`. Required-flag evidence is now three-state
> internally — **ACCEPTED / REJECTED / INDETERMINATE** — and only the two
> definite states reach the frozen `bool`: a rejection must be mechanically
> established from a bounded startup diagnostic naming an option actually in
> AIDO's own argv, and an indeterminate launch fails closed at the
> runtime-launch boundary (no session, `RUNTIME_LAUNCH_FAILED`,
> `required_launch_flags` left `NOT_REACHED`) rather than inventing a more
> specific cause. Nothing was added to the frozen
> `RuntimeLaunchObservation` or the frozen controller. See
> [FINDINGS.md](FINDINGS.md) section "5F3B-I2B-L1-LF1-FU1".

> **A SECOND zero-prompt Category-B live attempt has since occurred**
> (Candidate A, `results/i2b_live_A_20260831T224840Z.json`, observed Pi
> `0.84.4`). It is a **VALID FAIL-CLOSED RUN**: it passed every runtime-side
> compatibility gate, refused at `route_check` with `ROUTE_CHECK_FAILED` and
> `exact_candidate_model_served = false`, sent **zero** semantic prompts, and
> tore down, shut down, cleaned up and scrubbed verifiably. The artifact is
> retained unedited.
>
> **`route_check` did not establish that the exact candidate model is
> served. It did NOT establish that `qwen3-coder-next` is absent from B300.**
> The live checker was the unmodified `ar2.route_check.check_route_serves_model`,
> which sends no `Authorization` header and accepts no credential parameter,
> so a transport failure, a 401, a 403, any other non-200, a malformed listing
> and a genuinely absent model all produce the identical result. **5F3B-I2B-L1-LF2**
> reproduced that collapse offline, corrected the design assumption behind it
> (frozen I2A §15 item 9 — see
> [`docs/PHASE_5F3B_I2B_L1_LF2_ROUTE_BOUNDARY_CORRECTION.md`](../../docs/PHASE_5F3B_I2B_L1_LF2_ROUTE_BOUNDARY_CORRECTION.md)),
> and replaced the live checker with a qualification-owned, credential-bearing,
> same-run-bound observation plus a bounded route diagnostic. **AR2's own
> `route_check.py` is untouched and stays frozen.** LF2 performed **no live
> activity of any kind**. See [FINDINGS.md](FINDINGS.md) section
> "5F3B-I2B-L1-LF2".

> **5F3B-I2B-L1-LF2-FU1 (independent review, completed outside this
> repository's own tooling) closed LF2's two remaining public-authority
> blockers on the live route checker:** `AuthenticatedB300RouteObserver` and
> `build_authenticated_route_checker` expose only `candidate` and `adapters`
> — no public transport/client/request-injection parameter exists at that
> boundary, so a caller cannot inject a fabricated transport that manufactures
> route-served evidence without contacting B300; and route authority now
> requires `type(adapters) is LiveCategoryBAdapters` exactly, so a forged
> subclass is refused before its authority or HTTP mechanism is ever
> consulted. Strict malformed-listing handling, authenticated `Bearer`
> `/models`, the bounded route diagnostic vocabulary, no redirects,
> `trust_env=False`, one request/no retry/no fallback, the frozen AR2
> checker, and the frozen I2B controller all remain accepted, unchanged.
> **Verdict: `5F3B-I2B-L1-LF2-FU1: ACCEPT` / `5F3B-I2B-L1-LF2: ACCEPT /
> FREEZE`.** See [FINDINGS.md](FINDINGS.md) section
> "5F3B-I2B-L1-LF2-FU1".

> **Candidate A Category-B live attempt #3 has since occurred and is
> ACCEPTED** (Candidate A, `results/i2b_live_A_20260901T174244Z.json`,
> observed Pi `0.84.4`). Controller outcome `CATEGORY_B_GATE_PASSED`, no
> failed gate, all 13 Category-B compatibility facts `true`, authenticated
> route observation `route_model_served` from exactly one route observation
> request, **zero** semantic prompts, runtime teardown `SUCCEEDED`, broker
> shutdown `CLOSED`, generated-config cleanup `VERIFIED_REMOVED`, outer
> cleanup verified, evidence retention ready, and no evidence-scrub findings.
> **Verdict: `Candidate A Category-B live attempt #3: ACCEPT / VALID PASS`;
> `Candidate A Category-B compatibility: QUALIFIED / FROZEN`; `5F3B-I2B-L1
> live compatibility path (Candidate A): ACCEPT / FROZEN`.** See
> [FINDINGS.md](FINDINGS.md) section "5F3B-I2B-L1 — Candidate A Category-B
> Live Attempt #3".
>
> **Frozen claim scope.** This PASS qualifies Candidate A only for the
> Category-B runtime/route compatibility boundary — that a real Node/Pi
> process launches correctly, speaks the frozen RPC/LF-JSONL protocol,
> presents the expected extension and provider/model identity, and that the
> authenticated B300 route serves the exact candidate model id. It does
> **NOT** constitute semantic implementer qualification, model-quality
> scoring, Q1/Q2 qualification, an active-tool-registry observation, or
> real-workspace authority. **Candidate A implementer qualification remains
> NOT YET QUALIFIED. Candidate B Category-B remains NOT YET RUN. Q1/Q2 remain
> NO-GO. Real-workspace authority remains NO-GO.** (Superseded below: exactly
> one future Candidate B Category-B live attempt is now authorized. No
> further Candidate A live attempt is authorized.)

> **5F3B-I2B-L2: independent review of Candidate A Category-B live attempt #3
> is complete, and now authorizes exactly ONE future Candidate B Category-B
> zero-prompt live attempt** (`minimax-m2.7`). The existing offline
> controller and the live CLI already prove candidate symmetry: Candidate A
> and Candidate B execute the identical `run_one_category_b_live_attempt`
> controller path and the identical Category-B compatibility policy,
> differing only by the frozen candidate/model identity (A ->
> `qwen3-coder-next`, B -> `minimax-m2.7`). This is a **paper-trail-only**
> update -- no live network call, Pi/Node process, broker, credential read,
> or `/models` request occurred, and no implementation code changed. See
> [FINDINGS.md](FINDINGS.md) section "5F3B-I2B-L2 — Candidate B Category-B
> Live Authorization".
>
> ```text
> Candidate B Category-B live attempt #1:   AUTHORIZED, exactly once, zero-prompt
> Candidate B implementer qualification:    NOT YET QUALIFIED
> Candidate A Category-B compatibility:     QUALIFIED / FROZEN (unchanged)
> Q1/Q2:                                    NO-GO (unchanged)
> Real-workspace authority:                 NO-GO (unchanged)
> ```
>
> This authorization does **NOT** cover: a Candidate A rerun; a second
> Candidate B attempt; semantic prompts; Q1/Q2; model scoring; a real project
> workspace; a fallback model, provider, endpoint, or runtime; differential
> auth probing; code changes; automatic repair; or commit/push/PR.

> **Candidate B Category-B live attempt #1 has since occurred and is
> ACCEPTED, following independent review** (Candidate B, `minimax-m2.7`,
> `results/i2b_live_B_20260901T180415Z.json`, observed Pi `0.84.4`).
> Controller outcome `CATEGORY_B_GATE_PASSED`, no failed gate, no failure
> code, all 13 Category-B compatibility facts `true`, authenticated route
> observation `route_model_served` from exactly one route observation
> request, **zero** semantic prompts, runtime teardown `SUCCEEDED`, broker
> shutdown `CLOSED`, generated-config cleanup `VERIFIED_REMOVED`, outer
> cleanup verified, evidence retention ready, and no evidence-scrub findings.
> This was the single authorized invocation -- no retry occurred, Candidate A
> was not rerun, no semantic prompt was sent, and Q1/Q2 were not run.
>
> **Verdict: `Candidate B Category-B live attempt #1: ACCEPT / VALID PASS`;
> `Candidate B Category-B compatibility: QUALIFIED / FROZEN`; `Candidate A
> Category-B compatibility: remains QUALIFIED / FROZEN`; `5F3B-I2B-L1
> Category-B compatibility workstream: COMPLETE / FROZEN for both
> first-round candidates`.** See [FINDINGS.md](FINDINGS.md) section
> "5F3B-I2B-L1 — Candidate B Category-B Live Attempt #1".
>
> **Frozen claim scope.** This PASS qualifies Candidate B only for the
> frozen Category-B runtime/route compatibility boundary. It does **NOT**
> constitute semantic implementer qualification, model-quality scoring,
> Q1/Q2 qualification, an active-tool-registry observation, or real-workspace
> authority.
>
> ```text
> Candidate A Category-B:                   QUALIFIED / FROZEN
> Candidate B Category-B:                   QUALIFIED / FROZEN
> Candidate A implementer qualification:    NOT YET QUALIFIED
> Candidate B implementer qualification:    NOT YET QUALIFIED
> Q1/Q2:                                    NOT YET EXECUTED
> Real-workspace authority:                 NO-GO
> ```
>
> No further Category-B live attempt is authorized for either candidate.

> **HOW TO READ THE HISTORICAL SECTIONS IN THIS FILE.** The per-phase status
> blocks below are records written when each phase was accepted. Where one
> says "Category-B live execution not run", read it as a fact **as of that
> phase's acceptance** — superseded by the correction above, not a claim about
> now. Nothing below is rewritten to pretend the live attempt did not happen,
> and no historical result artifact is edited.

**5F3B-I2 (route/credential offline machinery, slices I2-1 through I2-6) is
now implemented, fully offline, per
[`docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md`](../../docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md).**
This establishes that the future live qualification route CAN be constructed
safely -- it does NOT authorize using it. Beyond the single 5F3B-I2B-L1
Category-B attempt recorded above, no Pi/Node process has been launched from
this package, and no candidate model has ever been run: that attempt sent
zero semantic prompts and never reached a model call.

**EXPERIMENT ONLY.** Not production code. Not a CLI command. Lives outside
`src/`, adds no `ProjectConfig` field, and this whole directory may be
deleted as one unit without touching anything else in the repository.

## What this is

The binding design is
[`docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md`](../../docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md).
This package implements exactly its Section 24 slice **5F3B-I1**: the frozen
IQ-1/IQ-2/IQ-3 synthetic task corpus, baseline contract validation, the
autonomous outcome classifier, the run-validity model, refusal attribution
and scope metrics, a conservative report-accuracy comparator, the hard
qualification bar, categorical ranking, a versioned record schema with a
fail-closed safe-emission choke point, and immutable invalidation/
replacement lineage evidence.

**This is fully offline.** No Pi process is launched, no model is called, no
socket or HTTP request is opened, no credential is read, and no B300/vLLM/
LiteLLM route is touched. Every "model run" the test suite classifies is a
plain Python fact structure (`RunFacts`, `RefusalEvent`, `ReportClaims`, ...)
fed directly to a pure policy function. The only subprocess activity is
local: `git` (fixture construction/inspection) and `python -m pytest`
(running each fixture's own fixed verification command against itself).

## Why this exists

5F3B-I1 makes the future Q1/Q2 one-shot live evidence *interpretable before
either candidate model is run*: a green offline suite here means a live
`AUTONOMOUS_FAIL` in a later round is a **model fact**, not a harness
defect. Building the corpus and the classifier first, and proving them
correct against synthetic evidence, is exactly what the accepted O1
offline-suite-before-live-run precedent already established.

## What I2 adds (offline only)

Per `docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md` Section
23's slices I2-1 through I2-6 (I2-6 was added by 5F3B-I2-FU3A and is part of
the accepted, frozen I2 scope):

- **I2-1** (`qualification/i2_environment.py`) -- the qualification-owned
  positive-allowlist child-environment builder: Windows baseline names,
  narrowed `PATH`, Pi-owned `PI_*` variables, and exactly ONE credential
  carrier (`PI_QUALIFICATION_B300_ROUTE_KEY`). No profile names, no keyless
  placeholder. Also `qualification/i2_secret_context.py`, the run-scoped
  secret context whose secret-bearing fields cannot leak through `repr()`.
- **I2-2** (`qualification/i2_pi_config.py`) -- the disposable
  `settings.json` (`maxRetries: 0`) + `models.json` (`apiKey:
  "$PI_QUALIFICATION_B300_ROUTE_KEY"`, `maxTokens` omitted) generator.
  **Since 5F3B-I2-FU1, `write_qualification_pi_config` takes only
  `model_id`/`base_url`** -- the provider id and the credential carrier are
  fixed internal constants, not caller-supplied parameters, so an arbitrary
  provider (`"openai"`) or credential carrier (`OPENAI_API_KEY`) cannot be
  requested through this API at all, and `model_id` is validated against
  the frozen candidate pairing before any file is written.
- **I2-3** (`qualification/i2_route.py`) -- route descriptors for Candidate A
  (`qwen3-coder-next`) / Candidate B (`minimax-m2.7`), always
  `b300_litellm_proxy`, never direct vLLM, plus the offline-only,
  dependency-injected wiring shape for the future `check_route_serves_model`
  zero-prompt gate.
- **I2-4** (`qualification/i2_credentials.py`) -- the credential-read-ordering
  contract: non-secret gates must ALL pass before the injected connection
  reader is ever called, proven with a call-counting double, never a real
  environment read.
- **I2-5** (`qualification/i2_cleanup.py`) -- generated-config teardown
  verified by `stat`, the phase-aware cleanup-failure classification
  (`semantic_prompts_sent == 0` -> `INFRASTRUCTURE_REFUSAL`;
  `== 1` -> `INFRASTRUCTURE_CONTAMINATED` / `scoring_eligible = False`), and
  the pre-persistence raw-diagnostic safety boundary that reuses I1's
  existing scrub primitive rather than a second secret scanner.
- **I2-6** (`qualification/i2_issuance.py`, 5F3B-I2-FU3A, encapsulated in
  FU3B) -- the process-local, in-memory-only registry that proves a
  disposable config's authority token was genuinely issued by this package,
  for that exact directory, in this process -- closing the gap where a
  caller-forged token with a correctly-computed FU3 marker could still
  authorize construction/cleanup. Also backs the cleanup-authority-vs-
  complete-content-integrity split
  (`i2_pi_config.verify_cleanup_authority` / `verify_generated_config_integrity`)
  that every launch-capable consumption path (`build_child_environment`,
  `describe_generated_config`, `verify_i2_identity_binding`) now requires.
  **Since 5F3B-I2-FU3B, every registry function is package-internal
  (underscore-prefixed)** -- only `i2_pi_config`/`i2_cleanup` call it; there
  is no public `register_issuance`/`finalize_issuance`/`discard_issuance`/
  `lookup_issuance` anywhere. Its `IssuanceRecord` is frozen and repr-safe,
  and finalization is one-shot (a second finalization for an already-
  finalized token is refused, never silently overwriting a trusted digest).

## What I2B adds (offline wiring only)

**AS OF THE 5F3B-I2B ACCEPTANCE THIS SECTION RECORDS: I2B CONTROLLER WIRED
OFFLINE. CATEGORY-B LIVE EXECUTION NOT YET RUN. NO CANDIDATE MODEL RUN.
Q1/Q2 NO-GO.** (One zero-prompt Category-B live attempt has since occurred --
see the corrected note at the head of this file. No candidate model has run,
then or now.)

`qualification/i2b_controller.py` (the state machine) and
`qualification/i2b_session.py` (the run-scoped resource authority and the
bounded live observations) implement the SHAPE the future Category-B
zero-prompt live gate will execute -- they do not run any of it. Every
future live boundary is an INJECTED adapter; every offline test supplies a
synthetic double, never a real subprocess, socket, or model call.

### 5F3B-I2B-FU1 -- what the first I2B controller could not actually prove

The initial I2B was rebuilt in FU1 against the frozen AR2/O1 lifecycle
rather than against I2A Sec. 15's narrative checklist. Five corrections:

1. **Broker first, launch second.** The initial controller confirmed
   `broker_ready` LAST. Frozen O1 (`run_o1.py`) mints the broker binding,
   reaches `STATE_READY`, and only THEN calls `launch_and_handshake(...,
   pipe_name=..., capability_id=..., token=...)` -- the launch writes that
   binding into the disposable extension, so it cannot precede a ready
   broker. The ordering is now enforced by the type: a
   `RuntimeLaunchRequest` is unconstructible from a broker session that is
   not `reached_ready`, or that belongs to another run.
2. **Every observation is bound to the SAME runtime.** The initial
   controller's no-argument `h1_check()` / `get_state()` / `teardown()`
   callbacks could each return a valid result describing a DIFFERENT
   runtime, undetectably. Each adapter now takes the run's `RuntimeSession`
   (or `BrokerSession`) and returns an observation carrying the session id
   it came from; a mismatch is refused.
3. **H1 and the second `get_commands` fact come from ONE response.** Frozen
   AR2's own H1 evaluator takes that response's command list as its argument,
   so modelling H1 as an unrelated observation was never faithful to the
   seam. They stay two DISTINCT gate facts, derived from one
   `GetCommandsObservation`. `get_state`/H2 follow the same rule.
   *(The one-observation discipline stands. FU1's naming of the second fact
   as "the tool registry" is **superseded** -- see FU2 item 1 below: it is
   the extension COMMAND-PROVENANCE partition, and `get_commands` proves
   nothing about the active tool registry.)*
4. **The terminal pass rule includes lifecycle closure.** The initial
   controller decided `CATEGORY_B_GATE_PASSED` from the last compatibility
   gate BEFORE teardown, cleanup and the evidence scrub ran -- so a run
   whose teardown failed still passed, and its evidence still said
   `compatibility_gate_passed: true`.
5. **The safety context carries the run's REAL sensitive values.** The
   initial controller hard-coded `broker_token=None, pipe_name=None,
   capability_id=None, workspace_absolute_path=None` -- silently
   substituting `None` for values a live run genuinely has.

### 5F3B-I2B-FU2 -- conformance with the now-frozen I2A/FU3 design family

**I2B-FU1 was never accepted.** The frozen `5F3B-I2A-DESIGN-FU3` family
(FU3 + FU3A/FU3B/FU3C) names six defects in it. FU2 corrects all six, adds
`qualification/i2b_workspace.py`, and changes no frozen AR1/AR2/O1/I1/I2 code
or semantics.

1. **`get_commands` enumerates SLASH COMMANDS, not the active tool
   registry.** FU1 gated `TOOL_REGISTRY` on `sorted(reported command names)
   == ("aido_edit", "aido_read")`. That gate was both *unprovable* -- Pi
   exposes NO RPC command that enumerates the active tool registry (AR0-FU1
   Sec. 4.1(j), source-verified; repeated in AR1, AR2, and AR2D Sec. 2.2's
   mandated correction) -- and *unsatisfiable*: `aido_read`/`aido_edit` are
   registered with `pi.registerTool` while `get_commands` reports
   `pi.registerCommand` slash commands, so those two names can never appear
   in a response at all. The gate is now `EXTENSION_COMMAND_NAMESPACE`, a
   **provenance partition** over the top-level-`"extension"`-sourced
   entries: exactly ONE `sourceInfo.source == "cli"` entry, which must be
   the H1-validated sentinel; any number of mechanically-established
   `"inline"` (Pi-owned) entries, tolerated without further constraint on
   name, path or count; anything else -- missing, malformed, or unrecognized
   `sourceInfo` -- fails closed. Both AIDO's sentinel and Pi's own inline
   `llama` report the SAME top-level `source`, which is exactly why the top
   level is a selector and `sourceInfo.source` is the discriminator. The
   evidence records `active_tool_registry_observation_available: false` and
   carries AR2D Sec. 2.2's three-way distinction. The configured
   `aido_read`/`aido_edit` allowlist remains an AIDO-owned argv/config fact
   and is no longer compared against any observation.
2. **H1 arrives as COMPONENTS; AIDO recomputes the verdict.**
   `GetCommandsObservation.extension_identity_matched` was a single
   caller-supplied boolean. The observation now carries the frozen
   evaluator's own five components plus two bounded origin tokens, and
   `h1_identity_established` is AIDO's own conjunction over them.
   `h1_components_from_frozen_evaluation` is the fixed projection a future
   live adapter must apply to the **frozen, unmodified**
   `ar2.handshakes.evaluate_extension_identity`, and a **differential
   conformance test** runs an adversarial corpus -- including the genuine
   observed sentinel(`cli`) + `llama`(`inline`) shape -- through both,
   requiring exact agreement on all five components and on the verdict. The
   sentinel command NAME is AIDO's own declared constant, so an adapter
   cannot nominate some other reported command as "the sentinel".
3. **Every deterministic non-secret refusal precedes the credential read.**
   FU1 called `resolve_connection_after_preflight` FIRST and only then
   `route_descriptor_for_candidate`, so an unknown candidate caused one real
   credential read before refusing. The prefix is now `RUN_CORRELATION ->
   WORKSPACE_AUTHORITY -> ROUTE_DESCRIPTOR -> NON_SECRET_PREFLIGHT`, and
   only then `CONNECTION_VALUES`. A source-level test pins that ordering,
   and call-counting doubles prove **zero** reader invocations for every
   pre-credential refusal.
4. **Synthetic workspace authority replaces caller-supplied paths.** FU1's
   `workspace_root: str` / `experiment_root: str` were arbitrary non-blank
   strings that flowed into a `mkdir`. Both parameters are **removed**. The
   controller takes one `QualificationRunWorkspace`, obtainable only from
   `mint_qualification_run_workspace()` -- which takes no argument at all
   and CREATES a fresh disposable root through the frozen
   `ar2.fixtures.create_disposable_experiment_root`. **No function anywhere
   converts an existing path into one.** The same verified identity binds
   the generated Pi config location, broker creation, runtime launch and
   `ArtifactSafetyContext.workspace_absolute_path`; authority is re-proved
   against the filesystem (through the frozen AR2 marker verification) at
   every consumption boundary; and a single-use claim binds one workspace to
   one `run_id`, so cross-run reuse, relocation, marker tampering and object
   substitution all fail closed.
5. **The creator partial-failure contract (FU3A/FU3B/FU3C).** No
   authority-bearing partial handle crosses into the controller. Ownership
   either transfers whole (a trusted, fully correlated session) or stays
   with the creator, which reports three orthogonal facts --
   `resource_created`, `cleanup_attempted`, and ONE
   resource-kind-specific observed postcondition
   (`direct_child_reported_exit` / `reached_closed`). All four states are
   constructible, including `PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT`,
   for which zero cleanup calls occur by anyone and no controller recovery
   action is authorized. **`cleanup_verified_success` is not a constructor
   field at all**: AIDO derives it as
   `cleanup_attempted and (postcondition is True)`, never bare truthiness
   and never a "the close call did not raise" shortcut. `create_broker` now
   returns a `BrokerCreationObservation` rather than a bare `BrokerSession`,
   so the broker side has the runtime side's partial accounting too.
6. **Possession is not authority.** FU1 still CALLED the shutdown adapter
   for a session whose `run_id`/`broker_session_id` did not match this run,
   and merely withheld `closure_satisfied` -- a live action against a
   resource the run never proved it owns. The adapter is now **never called
   at all** for such a session; the outcome is
   `RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION` /
   `BROKER_SHUTDOWN_REFUSED_FOREIGN_SESSION` with `attempted=False`,
   `authority_available=False`, `closure_satisfied=False`. A same-run,
   same-broker positive control proves ordinary teardown still happens
   exactly once.

Plus FU3 Sec. 10: a failure to mint the run correlation id is bounded as
`RUN_CORRELATION_UNAVAILABLE` -- an `INFRASTRUCTURE_REFUSAL` with zero
credential reads, zero resources, every closure `NOT_REQUIRED`, and no raw
exception text retained -- instead of escaping as an unbounded exception.

### What a Category-B PASS now mechanically requires

Thirteen INDEPENDENTLY established compatibility facts (`CompatibilityFacts`,
one exact-`bool` field each -- never one caller-supplied "passed" boolean):
Pi version observable (**provenance only**, never an exact-version
authorization); RPC launch shape valid; required launch flags accepted; LF
JSONL request/response correlation; `get_commands` response shape
understood; H1 exact extension identity (recomputed by AIDO from the frozen
rule's own components); no unexpected extension command observed (the
corrected provenance partition -- **never** a claim about the active tool
registry); `get_state` response shape understood; H2 exact provider/model
identity; no protocol violation observed; no extension error observed; the
exact candidate model served (via the unmodified `i2_route` route-check
wiring); and the broker's required READY state.

**PLUS** all of: `semantic_prompts_sent == 0`; every required teardown
closed truthfully (runtime first, then broker -- frozen O1's order);
generated-config cleanup VERIFIED; and retention-ready, scrub-clean
evidence. Anything else -- including all thirteen facts alongside a failed
teardown, an unclosed broker, an unverified cleanup, or a refused evidence
scrub -- is `INFRASTRUCTURE_REFUSAL` with `semantic_prompts_sent = 0`.
`compatibility_gate_passed = true` is structurally unable to appear
alongside a failed closure.

### Fail-closed properties, stated precisely

- an adapter that RAISES, returns `None`, returns a wrong type, or returns a
  SUBCLASS of an observation type is a bounded refusal -- never a crash, and
  never a pass;
- the extension command partition is over SORTED SEQUENCES, never sets, so a
  duplicated CLI-sourced entry cannot collapse into the one expected entry;
- a command entry, a Pi version, or a provider/model identity that is not a
  bounded, well-formed value is refused at construction, so no raw stdout,
  stderr, RPC body, path, URL or exception text can reach a retained
  observation;
- an observation cannot describe an incoherent state -- a failed call that
  also reports a matched identity, a "clean" scrub carrying findings, or a
  teardown claiming closure for a resource that was never created are all
  unconstructible;
- a creation that hands back no trusted session reports three orthogonal
  facts rather than a handle, and the controller has no partial-close
  callable for that branch at all -- so zero cleanup calls occur, by anyone,
  and no repeat-close-safety assumption is ever required. A launch or broker
  adapter that RAISES leaves AIDO no authority at all, reported as
  `*_AUTHORITY_UNAVAILABLE`, which can never pass;
- a returned session that does not carry this run's own `run_id` (and, for a
  runtime session, this run's own `broker_session_id`) is **never passed to
  the shutdown adapter**; the refusal is an explicit state, not a discounted
  attempt;
- AIDO's own arguments (`candidate`, `node_executable`, and the
  `QualificationRunWorkspace` itself) are validated FIRST, so a run that
  could never produce provably safe evidence never causes a credential read
  at all.

### What is deliberately NOT claimed

- **Not** "every possible failure maps to `INFRASTRUCTURE_REFUSAL`". Every
  bounded adapter/gate failure does. A caller-programming error in AIDO's
  own arguments raises `CategoryBControllerInputError` before any gate runs,
  deliberately -- that is not a Category-B outcome at all.
- **Not** that teardown stopped anything beyond AIDO's own direct child. The
  evidence records `backend_inference_lifetime_after_teardown: "not
  observed"` and `descendant_process_lifetime_after_teardown: "not
  observed"`, and its `claim_scope` says so explicitly. A returned local
  teardown call is never a claim that backend inference stopped.
- **Not** that the per-run `run_id` nonce authenticates an adapter. It is a
  CORRELATION control -- it catches a stale or foreign session object. The
  adapter necessarily receives the nonce in order to echo it, and is AIDO's
  own future live code, inside the trust boundary.
- **Not** that redaction/scrubbing guarantees secret-free evidence. The
  scrub is a backstop, as I1 already states.

### The FULL artifact safety context

`build_run_safety_context` populates every field I1's `ArtifactSafetyContext`
declares, from the run's real value when that value exists: `endpoint_host`
and `api_key` from the run's secret context; `broker_token`, `pipe_name` and
`capability_id` from the live broker session; and `workspace_absolute_path`
from the run's verified synthetic **experiment root**. That last choice is
deliberate: the run has three absolute paths (the experiment root, the
workspace root beneath it, and the generated Pi config directory beside
that), the scrub matches substrings, and the enclosing root is the one
needle that refuses an artifact carrying ANY of the three -- declaring only
the narrower workspace root would leave the generated-config directory
undeclared. `bearer_token` is `None` as a
DERIVED, proven absence -- I2A's frozen credential mechanism for this route
is `models_json_env_interpolation`, which mints no separate bearer value at
all; a descriptor reporting any other mechanism refuses rather than
guessing. A run that failed before a secret context existed still declares
whatever it does have, rather than falling back to `none_declared()`.

### Immutable results and evidence

`CategoryBControllerResult.gate_statuses` is a `MappingProxyType` over a
throwaway dict, so neither it nor a copy taken from it can rewrite a
validated result. `CategoryBEvidence` holds one canonical,
already-scrub-checked JSON string; each `as_dict()` returns a FRESHLY
deserialized copy, so no caller ever receives a reference into the object --
mutating a returned dict (including the `gate_statuses` and
`compatibility_facts` nested inside it) cannot rewrite the evidence or a
later reader's view. The scrub result is an immutable `tuple` of bounded
finding codes plus a `bool`, never a mutable dict whose `clean` key could be
flipped after validation. A refused evidence body is not retained in any
form.

### Reused unmodified

`i2_credentials.resolve_connection_after_preflight` (the credential-read
ordering proof), `i2_route.run_offline_route_check` (the future `/models`
exact-model gate), `i2_cleanup.scrub_generated_qualification_config` plus
`classify_cleanup_failure(semantic_prompts_sent=0)`,
`i2_composition.verify_i2_identity_binding`, `i2_pi_config`,
`i2_environment.build_child_environment`, and
`safety.qualification_scrub_check`. I2B introduces no new raw
`api_key`/`base_url`/config-path/provider-id/model-id parameter anywhere.

### Zero-prompt authority

`SEMANTIC_PROMPTS_SENT` is a module constant `0`. Neither I2B module defines
any function that accepts, sends or forwards a prompt, and a source-level
AST regression test asserts that no NAME in either module (identifier,
attribute, parameter, function or class) contains a prompt-shaped fragment
apart from the zero-valued counter itself, and that neither module imports a
live-I/O primitive. There is no candidate classification, no hard bar, no
ranking, and no `AUTONOMOUS_PASS`/`AUTONOMOUS_FAIL` reachable from here.

Candidate A and Candidate B run through the identical controller function,
differing only in the `candidate` argument. 124 fully offline tests
(`tests/test_i2b_controller.py`) cover the frozen-O1 lifecycle order,
resource authority binding, one-observation H1/registry and H2/state
derivation, every individual gate refusal, the terminal closure rule,
partial-resource accounting, malformed/duplicate/foreign/subclassed adapter
results, filesystem tampering, repeated invocation, result/evidence
immutability, the full safety context, and zero-prompt authority.

## What is explicitly NOT here

Per the design's Section 24/23 roadmaps:

- Any live Pi/Node process launch, RPC broker, or compatibility handshake,
  **as of the 5F3B-I2 acceptance this list records** -- at that point every
  live boundary of `i2b_controller.py`/`i2b_session.py` was an injected
  adapter this package supplied no real implementation for, and no real live
  adapter existed anywhere in it. (5F3B-I2B-L1 later added
  `qualification/i2b_live_adapters.py`, the real live adapters, and ran one
  zero-prompt Category-B attempt -- see the corrected note at the head of
  this file. Nothing here authorizes another.)
- Any real credential value read, anywhere, at any point.
- A live qualification executor -- nothing here can run a candidate model.
- Any model comparison result. The Section 26 comparison table in the design
  document is deliberately unfilled, and nothing in this package fills it.
- A reviewer, real workspace authority, automatic continuation, or a
  production stall circuit breaker.
- A generic `AgentRuntime` / multi-runtime abstraction (stays deferred).

## Package layout

```text
experiments/pi_implementer_qualification/
    README.md                  this file
    FINDINGS.md                offline harness facts only; no candidate results
    .gitignore
    qualification/
        __init__.py            package identity, version constants
        corpus.py               IQ-1 / IQ-2 / IQ-3 frozen fixtures + task contracts
        fixtures.py              build/teardown + baseline contract validation
        outcomes.py              Sec. 8 / Sec. 11 autonomous outcome classifier
        validity.py              Sec. 17.3 run-validity / scoring-eligibility model
        scope.py                 Sec. 17 refusal attribution + QD-2 scope metrics
        report_accuracy.py       QD-4 conservative report-accuracy comparator
        hard_bar.py              Sec. 16 hard qualification bar (H-1..H-14)
        ranking.py               Sec. 18 categorical ranking (R-1..R-4)
        safety.py                THE evidence safety + exclusive-create emission choke point
        records.py               pi-implementer-qualification.v1 schema + invariant gate
        lineage.py               Sec. 13/26 immutable invalidation/replacement evidence
        i2_environment.py        I2-1 child-environment builder (offline)
        i2_secret_context.py     I2-1 run-scoped secret context (repr-safe, no evidence helper)
        i2_pi_config.py          I2-2 disposable settings.json/models.json generator (offline)
        i2_route.py              I2-3 route descriptors + offline route-check wiring
        i2_b300_route_observation.py
                                 5F3B-I2B-L1-LF2: the authenticated, credential-bearing B300 /models
                                 observation + the bounded route diagnostic vocabulary (one GET, no
                                 retry, no redirect, nothing raw retained). Imports NOTHING from ar2.
        i2_credentials.py        I2-4 credential read ordering + connection contract (offline)
        i2_cleanup.py            I2-5 cleanup, phase-aware failure classification, diagnostic safety
        i2_identity.py           5F3B-I2-FU3: the leaf module for CREDENTIAL_ENV_VAR_NAME/PROVIDER_ID
        i2_composition.py        5F3B-I2-FU3: config/secret/route identity binding
        i2_issuance.py           5F3B-I2-FU3A/FU3B: the leaf module for the process-local issuance registry (internal-only API)
        i2b_workspace.py         5F3B-I2B-FU2: synthetic, qualification-MINTED Category-B workspace authority (no path parameter anywhere)
        i2b_session.py           5F3B-I2B-FU2: run-scoped Category-B resource authority + bounded live observations (offline)
        i2b_controller.py        5F3B-I2B-FU2, hardened by FU2A + FU2B + FU2C + FU2D + FU2E + FU2F: the Category-B zero-prompt live-gate controller (offline wiring only)
    tests/
        conftest.py              sys.path wiring, git_executable fixture, thread-leak check
        test_iq1_fixture.py      IQ-1 fixture, baseline, correct-repair proof
        test_iq2_fixture.py      IQ-2 fixture, two-file necessity proof
        test_iq3_fixture.py      IQ-3 fixture, no-change proof
        test_baselines.py        baseline contract validation, synthetic outcomes
        test_task_revision.py    frozen task-revision identity (incl. baseline contract)
        test_outcomes.py         autonomous outcome classifier
        test_run_validity.py     run-validity / scoring-eligibility
        test_scope.py            refusal attribution + scope metrics
        test_report_accuracy.py  QD-4 comparator
        test_hard_bar.py         hard qualification bar
        test_ranking.py          categorical ranking
        test_records.py          record invariant gate + safe/exclusive-create emission
        test_lineage.py          immutable invalidation/replacement lineage
        test_i2_environment.py   I2-1 child-environment builder
        test_i2_secret_context.py I2-1 run-scoped secret context safety
        test_i2_pi_config.py     I2-2 disposable config generator
        test_i2_route.py         I2-3 route descriptors + offline route-check wiring, plus the
                                 5F3B-I2B-L1-LF2 attribution-collapse reproduction against the
                                 UNMODIFIED AR2 checker (MockTransport only)
        test_i2_b300_route_observation.py
                                 5F3B-I2B-L1-LF2: the authenticated route observation matrix --
                                 auth/transport/malformed/absent classification, exact
                                 case-sensitive matching, redirect refusal, trust_env, no retry,
                                 and the secret-retention proof (MockTransport only)
        test_i2_credentials.py   I2-4 credential read ordering
        test_i2_cleanup.py       I2-5 cleanup, classification, diagnostic safety
        test_safety_repr.py      5F3B-I2-FU1: ArtifactSafetyContext repr-safety proof
        test_i2_composition.py   5F3B-I2-FU3: config/secret/route identity binding
        test_i2_issuance.py      5F3B-I2-FU3A/FU3B: process-local issuance registry contract (white-boxes internal-only API)
        test_i2b_controller.py   5F3B-I2B-FU2 + FU2A + FU2B + FU2C + FU2D + FU2E + FU2F: Category-B observability/H1-conformance/credential-ordering/workspace-authority/partial-lifecycle/foreign-session/closure/result-and-evidence-integrity/cross-field-coherence/resource-state-failure-code-domains/first-failure-attribution/cleanup-classification-coherence/refusal-trace-reachability/resource-existence-coherence/observation-availability/protocol-failure-code-mapping/terminal-evidence-state/evidence-safety-origin-attribution/immutability (offline doubles only)
```

**All qualification evidence is written by exactly one function**
(`safety.write_evidence_exclusively`, `O_CREAT | O_EXCL`), through one
fail-closed choke point that requires an explicit `ArtifactSafetyContext`.
There is deliberately no overwrite, append, or force variant anywhere in the
package, and two source-level regression tests enforce that.

## Reuse, not duplication

This package deliberately does **not** copy the AR2/O1 harness. It reuses,
unmodified, exactly the pieces that are generic and safe:

| Reused from (frozen, unmodified)                         | What                                             |
|------------------------------------------------------------|---------------------------------------------------|
| `experiments/pi_external_runtime_ar2/ar2/fixtures.py`       | `CaseFixture`, `build_case_repository`, `remove_disposable_tree`, the disposable-root authority origin |
| `experiments/pi_external_runtime_ar2/ar2/verification.py`   | `VerificationOutcome`, `run_verification`, `baseline_matches_case_contract` |
| `experiments/pi_external_runtime_ar2/ar2/record.py`         | `scrub_check` (generic secret/reasoning/ASCII scrub) |
| `src/ai_dev_orchestrator/workspace/git_adapter.py`          | the fixed, read-only Git operation set (status/ls-files observation) |

Nothing under `ar2/` or `src/` is modified. This package imports **none** of
AR2's live-runtime machinery (`broker`, `supervisor`, `launch`, `handshakes`,
`route_check`, `pi_config`, `environment`, `wire`, `winpipe`, `candidate`,
`operations`, `observation`) -- there is no live runtime to integrate with
here at all.

**I2's own `i2_environment.py` / `i2_pi_config.py` / `i2_route.py` are
structurally modeled on** `ar2/environment.py`, `ar2/pi_config.py`, and
`ar2/route_check.py` (I2A design Sec. 9/10/15) -- the accepted VALUES
(Windows baseline names, forbidden-fragment list, generated-config shape,
the `check_route_serves_model` call shape) are duplicated as new I2-owned
data and wiring, never imported as a dependency. `i2_route.py`'s offline
route-check wiring is exercised only against an INJECTED synthetic checker;
the real, unmodified `ar2.route_check.check_route_serves_model` function is
never imported or called by anything in this package.

## Running the offline suite

```bash
python -m pytest experiments/pi_implementer_qualification/tests -q
```

(Use the project's own virtual environment's `python`/`pytest` if `pydantic`
and friends are not on the ambient interpreter's path.)

## Status

Corpus, classifier, hard-bar and ranking machinery (I1) are ready offline.
**I2's offline machinery (slices I2-1 through I2-6) is implemented and
green** -- the child-environment builder, the run-scoped secret context, the
disposable Pi config generator, the route descriptors, the credential
read-ordering contract, and the phase-aware cleanup-failure classification.

**5F3B-I2-FU1 (Credential/Route Boundary Integrity Closure) closed seven
implementation gaps** an independent review found in I2's source: every
secret-bearing object (`ConnectionValues`, `LaunchEnvironment`, and the
narrowly-authorized `ArtifactSafetyContext`) is now repr-safe; the
`narrow_path` PATH-inheritance bypass is removed; the config generator no
longer accepts a caller-supplied `provider_id`/`credential_env_var_name`;
raw route-check failure text is no longer retained; a missing/blank/
malformed connection value is now a true bounded `InfrastructureRefusal`;
preflight failure detail is a bounded code, not free prose; and the B300
base URL is structurally validated before it can become safety-context
data. See `FINDINGS.md`'s `5F3B-I2-FU1` section for the full closure record.
None of it reopens the accepted I2A architecture.

**5F3B-I2-FU2 (Authority + Trusted-Value Closure) closed a further class of
gaps**: a safe factory existed, but its public value object could still be
forged by direct construction, or a destructive API trusted an unproven
path. `GeneratedQualificationConfig` required creation-time authority
before it could even be constructed, and `scrub_generated_qualification_config`
took that typed object -- never a raw path -- re-verifying the same
authority immediately before deleting anything.
`ConnectionValues`/`RouteDescriptor`/`QualificationRouteSecretContext` became
valid by construction (`__post_init__` enforces every field), with
`run_offline_route_check` additionally revalidating the descriptor at the
consumption boundary; the config generator's `base_url` went through the
one shared validator; `PreflightGateResult` could no longer express an
impossible `passed`/`failure_code` combination; and an exception a route
checker raises was reduced to a bounded `RouteFailureCode.ROUTE_CHECK_ERROR`,
never retaining `str(exc)`/`repr(exc)`/traceback text. See `FINDINGS.md`'s
`5F3B-I2-FU2` section for the full closure record.

**5F3B-I2-FU3 (Run Authority and Cross-Boundary Binding Closure) closed the
next class of gaps**, mainly in FU2's own authority mechanism and in two
remaining "raw value instead of trusted object" boundaries. FU2's
directory-deletion authority was a FIXED, PUBLIC marker string -- forgeable
by copying it into any directory. It is now a fresh, unpredictable, per-run
128-bit token (`secrets.token_hex(16)`), held only in memory
(`field(repr=False)`, never written to disk), with the on-disk marker
carrying only a path-keyed SHA-256 binding -- copying the marker to a
different directory no longer authorizes it. The generator now cleans up
its own partial failure (an injected internal write failure triggers a
verified delete using the authority it just established, never leaving an
endpoint-bearing partial config behind). `build_child_environment` no
longer accepts a raw `pi_config_dir`/`credential_value` string -- it
consumes an authority-reverified `GeneratedQualificationConfig` and a
`QualificationRouteSecretContext`, so the child's `PI_CODING_AGENT_DIR` and
credential can never disagree with the run's own trusted objects.
`LaunchEnvironment.environment` is now a read-only `MappingProxyType` view
(assignment raises `TypeError`); a fresh mutable copy is available only via
`as_launch_snapshot()`. `PreflightGateResult.passed` and the route
checker's `reachable`/`configured_model_served` now require `type(...) is
bool` exactly -- `"false"`/`1`/`0` no longer coerce through Python's own
truthiness. A new `i2_composition.verify_i2_identity_binding` binds
config/secret/route identity so the three cannot silently disagree once
composed for one run. See `FINDINGS.md`'s `5F3B-I2-FU3` section for the
full closure record. None of FU1/FU2/FU3 reopens the accepted I2A
architecture.

**5F3B-I2-FU3A (Issuance Authority, Content Integrity, Mandatory Binding
Closure) is the final offline-only closure.** FU3's marker still never
required the token itself to be genuinely I2-issued -- a caller could mint
its own token, hand-compute the same public binding formula, and forge a
marker into an arbitrary directory. A new process-local, in-memory-only
registry (`qualification/i2_issuance.py`) now records every token I2 itself
issues, for the exact directory it issued it for, and authority requires
BOTH the marker binding AND registry presence
(`i2_pi_config.verify_cleanup_authority`). A stricter
`verify_generated_config_integrity` additionally requires the issuance to be
FINALIZED and the on-disk `settings.json`/`models.json` bytes to still match
the SHA-256 digests recorded when I2 wrote them -- used by every
launch-capable consumption path, so a config edited after generation (a
relabeled model id, a substituted literal secret, an added `maxTokens`, a
changed `baseUrl`, a retry/trust policy edit) is refused, while cleanup of a
tampered-but-genuinely-issued config remains possible. `build_child_environment`
and `run_offline_route_check` now each independently refuse a
generated-config/secret-context or route-descriptor/secret-context identity
mismatch themselves, rather than relying on a caller remembering to call
`verify_i2_identity_binding` first. `LaunchEnvironment.__post_init__` now
copies its input dict before validating, closing an external-mutable-alias
gap independent review reproduced. See `FINDINGS.md`'s `5F3B-I2-FU3A`
section for the full closure record.

**5F3B-I2-FU3B (Issuance Registry Encapsulation Closure) is the final
offline-only correction.** FU3A's own registry mutation functions
(`register_issuance`/`finalize_issuance`/`discard_issuance`) were PUBLIC.
Independent review used ONLY that public surface -- no `object.__new__`, no
private-global mutation, no live activity -- to self-issue authority for an
arbitrary victim directory (call `register_issuance` for its own chosen
token/path/identity, then satisfy every other check normally), and
separately to overwrite an already-trusted digest with a tampered one by
calling `finalize_issuance` a second time. `qualification/i2_issuance.py`
now exposes only underscore-prefixed functions
(`_register_issuance`/`_finalize_issuance`/`_lookup_issuance`/
`_discard_issuance`); `i2_pi_config`/`i2_cleanup` remain its only callers.
`IssuanceRecord` is now `@dataclass(frozen=True)` with a bounded custom
`__repr__` (never the token or the canonical path), the registry is keyed by
token alone (one token = one issued config; a token already registered for
any path is refused), and finalization is one-shot -- a second finalization
for an already-finalized token is refused
(`ISSUANCE_ALREADY_FINALIZED`), never silently replacing trusted digests.
See `FINDINGS.md`'s `5F3B-I2-FU3B` section for the full closure record.
This closes the accepted 5F3B-I2 scope; no further FU is anticipated absent
a new independent-review finding.

**5F3B-I2B-FU2A (Terminal Result + Evidence Integrity Closure).**
Independent review of FU2 found `CategoryBControllerResult` was not valid by
construction at all -- `runtime_teardown`/`broker_shutdown`/`cleanup` were
consumed via bare attribute access with **no type check whatsoever**, and
`facts`/`evidence` used `isinstance`, which a subclass overriding a
read-only property (`all_established`/`closure_satisfied`/
`retention_ready`) satisfied while lying about its own state -- plus two
narrower defects: `CleanupStatus.scrub_verified` accepted any truthy value
via bare Python truthiness (`scrub_verified="false"` reported
`VERIFIED_REMOVED`), and `CategoryBEvidence`'s public constructor accepted
`retention_ready=True` and an arbitrary `_serialized` body directly, with no
proof either had ever been scrub-checked. All three are closed: every
nested authority value at the result boundary is now checked by **exact
type** (`type(x) is ExactType`, never `isinstance`); `CleanupStatus` requires
`scrub_verified` to be exactly `bool`; and `CategoryBEvidence`'s every field
is `init=False` (the public constructor takes no arguments at all), with the
only two populated-instance paths being package-internal classmethods that
each **derive** `retention_ready` from an actual call to the frozen
`qualification_scrub_check`, never accept it as an assertion. `_gate_status_pairs`
is newly validated against a bounded, declared vocabulary, with an explicit
rule that a `CATEGORY_B_GATE_PASSED` outcome can never carry a
`NOT_REACHED`/`FAILED:...` entry for any gate. See `FINDINGS.md`'s
`5F3B-I2B-FU2A` section for the full counterexample-by-counterexample
closure record. `i2b_session.py`/`i2b_workspace.py` were not touched --  a
sweep for the same defect classes found nothing else in either module.

**Correction (5F3B-I2B-FU2B).** FU2A's own closing claim that
`CategoryBControllerResult` was thereby "valid by construction" was itself
**overstated**. FU2A hardened individual field TYPES but never bound them to
EACH OTHER: the FU2A test helper's own default kwargs -- reused, unnoticed,
across roughly twenty test cases -- were themselves the exact contradiction
(`pi_config_created=True` alongside `cleanup.attempted=False`;
`runtime_session_established`/`broker_created=True` alongside
`runtime_teardown`/`broker_shutdown` left at `NOT_REQUIRED`; a single GLOBAL
vocabulary of gate-status strings that let `route_check = "NOT_REQUIRED"` --
a text only a CLOSURE gate ever produces -- sit inside an otherwise-passing
result; and a retention-ready `CategoryBEvidence` scrub-built from a payload
with no relationship to the result consuming it at all,
`{"ok": True}`, accepted unconditionally). FU2B closes these; see the
`5F3B-I2B-FU2B` section in `FINDINGS.md` for the full record, including a
genuine PRODUCTION bug this phase's own new checks surfaced end to end
(`CleanupStatus.status_text` embedded a DIFFERENT enum's value than the one
the controller's own `_fail()` actually records for the same gate) and a
bypass found in this phase's OWN post-implementation self-review
(`CompatibilityFacts` fields were not bound to their own compatibility
gate's status at all).

**5F3B-I2B-FU2B remained HOLD after independent source review.** FU2B's own
structural checks left three residual gaps, each reproduced against the
pre-fix code before any change was made:

1. `_ResourceClosureStatus` validated `failure_code` by TYPE only -- ANY
   `CategoryBFailureCode` was accepted on ANY `ResourceClosureState`, on
   EITHER resource kind. `RuntimeTeardownStatus(state=SHUTDOWN_FAILED,
   failure_code=BROKER_SHUTDOWN_INCOMPLETE)` and a foreign-session state
   carrying the generic teardown-failed code instead of its own
   foreign-session-specific code both constructed successfully, so the
   closure gate then trusted that typed object's own `status_text` as
   internally-consistent but FALSE evidence.
2. `failed_gate`/`failure_code` were checked for agreement with THAT gate's
   own recorded text, but nothing verified `failed_gate` was the FIRST
   failed gate in the controller's own evaluation order -- a hand-built
   result could name an earlier genuinely-failed gate in `gate_statuses`
   while nominating a later one as `failed_gate`.
3. `CleanupStatus` checked `classification`'s TYPE
   (`CleanupFailureClassification`) but never its FIELDS -- an
   internally-impossible instance (e.g. `semantic_prompts_sent=1` alongside
   the pre-prompt classification, a shape `classify_cleanup_failure` itself
   never returns, since Category-B is structurally pre-prompt) constructed
   successfully and was accepted.

**5F3B-I2B-FU2C** closes all three. `_ResourceClosureStatus` subclasses
(`RuntimeTeardownStatus`/`BrokerShutdownStatus`) now each declare their OWN
per-STATE allowed-failure-code table, read directly off their actual
`_close_runtime`/`_close_broker` producer -- a code valid for one state, or
for one resource kind, is refused on any other. `CategoryBControllerResult`
now additionally scans its gate statuses in the controller's own declared
evaluation order and requires `failed_gate` to be the FIRST `FAILED:...`
entry found (and requires a `CATEGORY_B_GATE_PASSED` result to have no
`FAILED` gate at all). `CleanupStatus` now compares a non-`None`
`classification` field-by-field against a FRESH call to
`classify_cleanup_failure(semantic_prompts_sent=0)` -- by identity/exact-type,
never truthiness -- rather than trusting the wrapping exact-type check alone;
this reuses the frozen `i2_cleanup` function's own return value for
comparison rather than importing/naming `AutonomousClassification` inside
`i2b_controller.py` (which `test_no_candidate_scoring_machinery_is_reachable`
already forbids). See `FINDINGS.md`'s `5F3B-I2B-FU2C` section for the full
counterexample-by-counterexample closure record, including the corrected
`test_every_unsatisfied_closure_state_reports_no_orchestrator_attempt` test,
which had itself been asserting a code/state pairing the real controller
never produces.

**Correction (5F3B-I2B-FU2D): FU2C's "READY FOR INDEPENDENT REVIEW" verdict
was premature.** FU2C closed *which* failure code a resource or gate may
carry and *which* gate may be nominated as `failed_gate`, but stopped one
layer short: individually valid resource and gate objects could still
describe an **execution trace the controller could never have produced**.
The suite's own launch-facts "positive control" was exactly such a trace --
it asserted as legitimate a result claiming `PI_CONFIG_GENERATION = PASSED`
alongside `pi_config_created=False` and a `NOT_REQUIRED` cleanup, and
`RUNTIME_LAUNCH = FAILED:RUNTIME_SESSION_MISMATCH` alongside
`runtime_session_established=False`. Both are impossible: the controller
assigns `generated_config` exactly on that gate's success path, and a
session-mismatch refusal is reached only *after* a session object was
returned. **Refusing to shut a foreign session down is not the same fact as
no session having been returned.**

FU2D closes this with three narrow, source-transcribed additions: each
existence boolean is bound to the gate status that determines it and to a
per-status map of the closure states that status can actually produce; and
`_require_reachable_gate_trace` requires every compatibility gate to be
reached **exactly** when the controller's own `if` condition for that stage
was satisfied (a biconditional, so a gate claiming `NOT_REACHED` when its
prerequisite passed is refused too). Both intentional multi-fact observation
groups survive untouched -- the four launch-fact gates still fail
independently, and H1 and the namespace gate still both fail from one
`get_commands` response. Nine existing tests that encoded impossible traces
were corrected, and the old `_all_not_reached_pairs` test helper (whose
premise was itself an impossible-trace generator) was replaced by one that
derives every field from a reachable trace. A further bypass found in this
phase's own second adversarial review -- creator-retained runtime closure
states surviving on a trace where the launch adapter was never called -- was
fixed and regressed. See the `5F3B-I2B-FU2D` section in `FINDINGS.md`,
including the 29-real-controller-trace test that proves the new rules are
derived from the source rather than merely plausible.

**Correction (5F3B-I2B-FU2E): FU2D's own "READY FOR FINAL FREEZE REVIEW"
verdict was premature.** FU2D closed *whether a gate trace is reachable*, but
a gate trace being reachable does not by itself prove every `CompatibilityFacts`
field on it is honest: the fact-vs-gate binding **skipped the check entirely**
whenever a fact's own gate read `NOT_REACHED`, correct only for the four
LAUNCH facts (I2A's own accepted asymmetry -- they are recorded from the
`RUNTIME_LAUNCH` observation before the controller knows whether
`RUNTIME_LAUNCH` itself will pass) but far too broad for the other seven
single-mapped facts, whose own gate and whose own observation are always set
together, unconditionally, in the SAME block. And the `PROTOCOL_INTEGRITY`
conjunction check proved only that the two protocol facts agreed with
pass/fail, never *which* failure code they were consistent with --
`FAILED:PROTOCOL_VIOLATION_OBSERVED` and `FAILED:EXTENSION_ERROR_OBSERVED`
each pin a DIFFERENT exact pair of fact values, and the old check could not
tell them apart.

FU2E closes both, plus one further terminal-state gap: `CategoryBEvidence()`'s
bare, no-argument constructor produces a safe INTERMEDIATE placeholder
(`scrub_findings == ("evidence_not_yet_built",)`) that is legitimate to
construct in isolation but is never a shape `run_category_b_controller` itself
returns -- nothing previously refused a terminal `CategoryBControllerResult`
carrying it. All fourteen of this phase's own mandatory counterexamples were
reproduced against a scratch reconstruction of the pre-fix module (each
constructed cleanly there) before being closed; every one is now refused
except the two accepted positive controls (a valid `RuntimeLaunchObservation`
with `session=None` -- `RUNTIME_LAUNCH_FAILED` -- or a foreign session --
`RUNTIME_SESSION_MISMATCH` -- still independently carries the four launch
facts even though their own gates stay `NOT_REACHED`). See the `5F3B-I2B-FU2E`
section in `FINDINGS.md` for the full record, including the exact
observation-availability rule, the exact protocol failure-code/fact mapping,
and the second-adversarial-sweep notes.

**Correction (5F3B-I2B-FU2F): FU2E's own "READY FOR FINAL INDEPENDENT FREEZE
REVIEW" verdict was premature, for exactly one narrow residual.** FU2E bound
every `CompatibilityFacts` field to the gate that produced it, but
`EVIDENCE_SAFETY`'s own failure code was still bound only to
`evidence.retention_ready` -- never to WHICH of the controller's two
mutually-exclusive evidence-construction paths actually produced a
non-retention-ready `CategoryBEvidence`. The suite's own
`test_fu2c_evidence_safety_alone_failing_may_be_failed_gate` still accepted
`gate_statuses['evidence_safety'] = FAILED:EVIDENCE_SCRUB_REFUSED` paired
with `CategoryBEvidence._refused(("safety_context_unprovable",))` -- the
real controller's SAFETY_CONTEXT_UNPROVABLE-branch shape, which
`EVIDENCE_SCRUB_REFUSED` (only ever emitted for a non-retention-ready
`_build_from_payload` body) can never accompany.

FU2F closes this by having `CategoryBEvidence` stamp its own construction
origin (`_refused` vs `_build_from_payload` vs the untouched bare-constructor
default), and binding `EVIDENCE_SAFETY`'s code to that origin by DIRECT,
PER-ORIGIN EQUALITY -- the same pattern the three lifecycle-closure gates
already use against their own typed objects' `status_text`. The fix also
surfaced a SECOND, symmetric bypass the old `retention_ready`-only check
permitted (`SAFETY_CONTEXT_UNPROVABLE` paired with a REAL dirty
`_build_from_payload` body), closed the same way; and it resolved
`EVIDENCE_SAFETY`'s defensive `MALFORMED_ADAPTER_RESULT` branch, PROVEN
unreachable under the controller's own invariants (`EVIDENCE_SAFETY` is
unconditionally resolved on every path before that guard runs) and removed
from the gate's accepted terminal vocabulary, so a future regression that
somehow reaches it would now raise loudly at result construction rather than
silently accepting an unproducible code. See the `5F3B-I2B-FU2F` section in
`FINDINGS.md` for the full record, including the exhaustive cross-swap sweep.

**5F3B-I2B, as corrected by 5F3B-I2B-FU1, brought into conformance with the
frozen I2A/FU3 design family by 5F3B-I2B-FU2, made cross-field-coherent by
5F3B-I2B-FU2A and 5F3B-I2B-FU2B, given exact resource/state failure-code
domains, first-failure attribution and cleanup-classification coherence by
5F3B-I2B-FU2C, made refusal-trace/resource-existence coherent by
5F3B-I2B-FU2D, given exact observation-availability and terminal-evidence-
state closure by 5F3B-I2B-FU2E, and given exact evidence-safety failure
attribution by 5F3B-I2B-FU2F, is offline wiring only.**
`qualification/i2b_controller.py`, `qualification/i2b_session.py`
and `qualification/i2b_workspace.py` implement the state machine, the
run-scoped resource authority and the synthetic workspace authority that
will LATER execute the accepted Category-B gates -- the frozen-O1 lifecycle
order, the corrected pre-credential ordering, session-bound observations,
thirteen independently established compatibility facts (including the
corrected extension-command-provenance gate, which is explicitly **not** a
tool-registry observation, and each now BOUND to its own compatibility
gate's status), the handle-free creator partial-failure contract, absolute
foreign-session refusal, a terminal pass rule that requires the ACTUAL
successful Category-B shape (every typed closure object genuinely
`CLOSED_BY_ORCHESTRATOR`/verified, never merely `closure_satisfied`, which
`NOT_REQUIRED` also satisfies), per-gate-bounded status text, a
retention-ready evidence body mechanically bound to the exact result
consuming it, and immutable results -- entirely through injected adapters
and synthetic offline doubles.
**AS OF THE 5F3B-I2B-FU2F ACCEPTANCE THIS SECTION RECORDS: I2B CONTROLLER
WIRED OFFLINE. CATEGORY-B LIVE EXECUTION NOT YET RUN. NO CANDIDATE MODEL RUN.
Q1/Q2 NO-GO.** See the "What I2B adds" section above for the full closure
record, including what it deliberately does NOT claim. (One zero-prompt
Category-B live attempt has since occurred -- see the corrected note at the
head of this file.)

**5F3B-I2B-FU2F verdict: COMPLETE. 5F3B-I2B verdict: READY FOR FINAL FREEZE
REVIEW.** Category-B live execution, 5F3B-Q1/Q2 and real-workspace authority
all remain **NO-GO** -- FU2F closes an evidence-safety failure-code
attribution gap in the OFFLINE result validator; it authorizes no live
Pi/Node launch, no network call, no credential read, no model call and no
semantic prompt, and reopens no accepted I2A/FU3 or
5F3B-I2B-FU2/FU2A/FU2B/FU2C/FU2D/FU2E design decision. See the
`5F3B-I2B-FU2F` section in `FINDINGS.md` for the full closure record.

**As of the 5F3B-I2B-FU2F acceptance recorded above, this was still an
offline-only implementation:** no zero-prompt live gate (I2A Sec. 15) had
run, and no candidate model had run. Exactly one zero-prompt live gate
attempt has since occurred (5F3B-I2B-L1 -- see the corrected note at the head
of this file); **no candidate model has run, then or now**, and 5F3B-Q1/Q2
(the first live candidate sweeps) remain **NOT authorized**.

### 5F3B-I2B-L1-LF2 — Credentialed B300 Route Observation + Route Failure Attribution

**Verdict: COMPLETE, pending independent review. No live activity was
performed.**

Candidate-A live attempt #2 refused at `route_check` with
`ROUTE_CHECK_FAILED`. That refusal is accepted. What it could not do is say
*why*, because the live checker was the frozen, **unauthenticated**
`ar2.route_check.check_route_serves_model`: a transport failure, HTTP 401,
HTTP 403, any other non-200, a malformed listing, a genuinely absent model and
a malformed checker result all collapse into one `configured_model_served =
false`. LF2 reproduces that collapse offline against the real, unmodified
function, and corrects the assumption behind it.

What changed:

- **AR2's `route_check.py` stays frozen and unmodified.** It is no longer
  imported by the live adapters at all — the import is deleted, not left
  unused, and the former `route_checker` module attribute is gone.
- **A new qualification-owned observation**,
  `i2_b300_route_observation.observe_b300_route_serves_model`: exactly one
  non-inference `GET <base_url>/models` carrying this run's
  `Authorization: Bearer` header (the shape established from Pi's
  `openai-completions` provider type *and* from AIDO's own shipped LiteLLM
  client, which already uses it against the same two environment variables),
  with `trust_env=False`, **redirects disabled**, a bounded timeout, no retry,
  no fallback endpoint, no fallback model, strict bounded response-shape
  validation, and exact case-sensitive matching.
- **Same-run authority, not caller-supplied.** The live checker is
  `AuthenticatedB300RouteObserver`, bound to this run's consumed
  `ConnectionValues` and the frozen I1 candidate pairing. There is no
  `base_url`, `api_key`, `endpoint`, `provider` or `model_id` parameter
  anywhere at that boundary; a substituted URL, model, candidate or forged
  authority object is refused **before any request is issued**, and a second
  observation is refused outright.
- **A bounded route diagnostic** (`route_model_served`,
  `route_transport_unreachable`, `route_auth_rejected`, `route_http_rejected`,
  `route_listing_malformed`, `route_model_not_listed`, `route_result_malformed`,
  `route_authority_refused`, `route_not_observed`), recorded by the harness
  **alongside** the frozen result exactly as LF1's launch diagnostic is. It is
  **attribution, never verdict authority**: the frozen controller keeps its
  single `ROUTE_CHECK_FAILED` and gained no new failure code, and
  `CategoryBEvidence` is untouched.
- **Nothing raw is retained**: no response body, no served-model-id list, no
  status code, no endpoint, no host, no base URL, no credential, and no
  exception message or traceback on any path.

What LF2 does **not** establish: that `qwen3-coder-next` is served by B300 or
that it is not; that the B300 proxy validates the `Authorization` header (I2A
§24 item 1 stays open, and a differential auth probe is **not** authorized);
and nothing about the retained live artifacts, which are unedited.

**Candidate A: NOT YET QUALIFIED. Candidate A further live: NO-GO until
independent LF2 review. Candidate B: NO-GO. Q1/Q2: NO-GO. Real-workspace
authority: NO-GO.**

---

## 5F3B-Q1-PRE1 / PRE1-FU1 / PRE1-FU2: STILL ON HOLD

The untracked `qualification/semantic_*.py` modules and their tests are
**5F3B-Q1-PRE1 work that independent review placed on HOLD.** They are not
accepted, not frozen, and must not be treated as the qualification package's
semantic path.

**`5F3B-Q1-PRE1-FU2` implemented the now-frozen DESIGN-FU1/FU1A contracts**
(§2 two-phase dispatch/turn, §3 the indeterminate-attempt evidence contract,
§3.J the sweep stop policy, §4 distinct count ownership, §9.1 semantic
workspace ownership and verified removal, §9.2 the full artifact safety
context, §9.3 the optional/untrusted final report, §9.4 deep result/sweep
immutability). That work is **OFFLINE IMPLEMENTATION ONLY** and changes none
of the standing verdicts below: `5F3B-Q1-PRE1` remains **HOLD pending
independent FU2 review**, and Q1 / Q2 / real-workspace authority remain
**NO-GO**. No candidate was run, no semantic prompt was sent, no Pi/Node
process was launched, no credential was read, no socket or named pipe was
opened, and B300 was not contacted.

`5F3B-Q1-PRE1-DESIGN-FU1` inspected the locally installed Pi `0.84.4` RPC seam
and established two blockers against them:

1. **Dispatch authority is not separable.** FU1 embeds the send/no-send fact
   inside the whole-turn observation, so a post-acknowledgement turn-read
   failure or a post-send teardown failure can **erase** an already-established
   `CONFIRMED_SENT` back to `SEND_STATE_INDETERMINATE`. Pi's real seam emits a
   correlated `prompt` response strictly before `agent_start` and before any
   inference, so the two facts are genuinely separable and must be separated.
2. **An indeterminate attempt currently retains no evidence at all.** The one
   outcome in which AIDO cannot prove whether the candidate's single authorized
   prompt was spent is the one outcome that writes no artifact.

The design correction — a two-phase dispatch/turn contract, a write-once
`semantic_prompts_sent`, a separate `pi-implementer-qualification-attempt.v1`
artifact (the frozen primary schema is **not** widened), no automatic retry, an
indeterminate send **consuming** the one-shot attempt, and the sweep stopping
immediately — is specified in
[`docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md`](../../docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md)
and summarized in [FINDINGS.md](FINDINGS.md). **It is not implemented.**

**`5F3B-Q1-PRE1-DESIGN-FU1A` (design documentation only; also not
implemented) found four further gaps against the actual `semantic_*.py`
source** — no semantic workspace removal on any closure path, an
artifact-safety-context builder whose correctness depends on gate order
rather than being proven independently per field, a final-report-collection
failure that today wrongly drives an otherwise-valid run to
`ATTRIBUTION_UNDETERMINED`, and mutable `dict`/`list` fields on
`SemanticTaskAttemptResult`/`PrimarySweepResult` that a caller could mutate
after validation — and freezes the closing contracts for all four in the
same document's §9. Independent review subsequently **ACCEPTED and FROZE**
both `5F3B-Q1-PRE1-DESIGN-FU1` and `5F3B-Q1-PRE1-DESIGN-FU1A`, and
`5F3B-Q1-PRE1-FU2` implemented them; the design document itself is unchanged
by that implementation turn.

That design phase performed **no live activity of any kind**: no semantic
prompt, no Pi/Node launch, no credential read, no socket, no B300 contact.
**NO SEMANTIC PROMPT HAS EVER BEEN SENT.** Q1: NO-GO. Q2: NO-GO.
Real-workspace authority: NO-GO.
