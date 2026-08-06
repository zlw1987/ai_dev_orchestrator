# Phase 4E — Optional Model-Backed L1 Planner (Design Review Only)

> **This document is a design review only. Phase 4E ships no runtime code.**
>
> It contains **no implementation**, makes **no model call**, makes **no
> network call**, reads **no environment variable**, and adds **no CLI
> option**. It refines §4, §5 and §7 of
> [PHASE_4_L1_PLAN_GENERATOR_PLAN.md](PHASE_4_L1_PLAN_GENERATOR_PLAN.md) —
> the Phase 4 status/plan document — for the *future* case where an L1 plan is
> produced by a model rather than by the deterministic Phase 4C
> [`FakeL1Planner`](../src/ai_dev_orchestrator/plan/fake_planner.py).
>
> Nothing described here is authorized to be built by this phase. Each item
> below becomes buildable only when a later, explicitly authorized sub-phase
> (§8) asks for it by name.

## 1. Goal

Describe how a **future, optional, model-backed L1 planner** could produce an
[`L1Plan`](../src/ai_dev_orchestrator/plan/models.py) from issue text plus
project configuration — as an alternative *engine* behind the same typed
output the `FakeL1Planner` already produces.

The goal is a **drop-in engine swap, not a capability expansion**:

- **Input:** the same three objects the Phase 4C planner already takes —
  `GitHubIssue`, `ParsedIssue`, `ProjectConfig`.
- **Output:** the same validated `L1Plan` — no new fields, no new output
  shape, no new consumers.
- **Difference:** `summary` / `scope_summary` / `proposed_steps` / `risks` /
  `open_questions` would be *reasoned* by a model instead of derived by fixed
  string rules.

It stays **L1 plan-only**, exactly as
[PHASE_4_L1_PLAN_GENERATOR_PLAN.md §6](PHASE_4_L1_PLAN_GENERATOR_PLAN.md#6-safety--boundary-rules)
requires. A model-backed planner must **not**:

- edit files,
- execute commands,
- write to GitHub (no comments, labels, issue edits, branches, or PRs),
- create branches,
- read target project workspace files (nothing under `repo.workspace_path`),
- escalate its own automation level above `"L1"`,
- mark its own output as not requiring human approval.

Swapping the planner engine changes **who writes the plan text**. It changes
nothing about what the orchestrator is allowed to *do* with that text: the
answer remains "print it for a human."

## 2. Non-goals

Explicitly out of scope for Phase 4E:

- **No implementation of any kind.** No new module, no new function, no new
  test, no change under `src/` or `tests/`.
- **No real model call**, in this phase or in any code this phase produces.
- **No environment loading.** Phase 4E does not read `AIDO_LITELLM_BASE_URL`,
  `AIDO_LITELLM_API_KEY`, `AIDO_LITELLM_DEFAULT_MODEL`,
  `AIDO_LITELLM_TIMEOUT_SECONDS`, `AIDO_LITELLM_MAX_RETRIES`, or any other
  environment variable, and does not call
  [`load_llm_client_config_from_env`](../src/ai_dev_orchestrator/llm/config.py).
- **No CLI real-model flag.** No `--live`, `--real`, `--model`, `--use-env`,
  `--github`, or `--fetch` option is added to `generate-plan` or to any other
  command. `generate-plan` stays offline-only, exactly as Phase 4D shipped it.
- **No GitHub fetch and no GitHub write.**
- **No agent loop** — no plan/act/observe cycle, no self-retry, no tool use,
  no multi-step orchestration, and no agent framework (LangGraph / CrewAI /
  AutoGen / n8n).
- No implementer / reviewer / fixer role wiring, no file editing engine, no
  command execution engine, no target project workspace access.

## 3. Future architecture

A model-backed planner would be assembled from four pieces, three of which are
pure functions. Only one of them can ever touch a network, and it is the one
already built, already mockable, and still gated (§5).

```
GitHubIssue ─┐
ParsedIssue ─┼─> prompt builder (pure) ─> LLMRequest
ProjectConfig┘                               │
                                             v
                              LLM client (Phase 3C, GATED)
                                             │
                                             v
                                        LLMResponse
                                             │
                                             v
                        output parser (pure) ─> L1Plan | typed error
```

### 3.1 Input

The same inputs the Phase 4C planner already consumes
([PHASE_4_L1_PLAN_GENERATOR_PLAN.md §2](PHASE_4_L1_PLAN_GENERATOR_PLAN.md#2-inputs)):

- **`GitHubIssue`**
  ([github/models.py](../src/ai_dev_orchestrator/github/models.py)) —
  `number`, `title`, `body`, `state`, `html_url`, `labels`. Already fetched (or
  synthesized offline, as `generate-plan` does today); the planner itself never
  fetches.
- **`ParsedIssue`**
  ([github/issue_parser.py](../src/ai_dev_orchestrator/github/issue_parser.py)) —
  the canonical sections `Goal`, `Current Context`, `Scope`, `Non-goals`,
  `Acceptance Criteria`, `Required Verification`, `AI Instructions`,
  `Automation Authorization`, plus the missing-section report.
- **`ProjectConfig`** ([models.py](../src/ai_dev_orchestrator/models.py)) —
  `allowed_paths` / `protected_paths` / `forbidden_paths`, `workspace_policy`,
  and `repo` metadata. The planner reads this **config object**; it never reads
  files from `repo.workspace_path`.

No fourth input. In particular, **no directory listing, no repository tree, no
file contents, and no git history** are inputs to the planner.

### 3.2 Prompt builder — pure function

A pure function with no IO:

```
build_planner_request(issue, parsed, project, *, model) -> LLMRequest
```

Properties this design requires:

- **Pure and deterministic** — same inputs produce a byte-identical
  `LLMRequest`. No clock, no randomness, no environment reads, no filesystem
  reads, no network.
- **Returns a typed `LLMRequest`**
  ([llm/models.py](../src/ai_dev_orchestrator/llm/models.py)) — it *builds* a
  request; it never *sends* one. The function has no client, no transport, and
  no way to reach a socket.
- **Independently testable offline** — its entire contract is
  "inputs in, `LLMRequest` out," so its tests assert on prompt text without any
  transport at all (not even a mock).
- **Content rules** are specified in §4 and are part of this function's
  contract, not left to the caller.

Because it is pure, the prompt builder is the piece that can be implemented and
reviewed earliest and most safely (§8, Phase 4F).

### 3.3 LLM client — existing Phase 3C client, gated

The existing [`LLMClient`](../src/ai_dev_orchestrator/llm/client.py) is the
**only** component permitted to perform a network call, and it already has the
properties needed:

- no network call at import or construction time,
- no environment reads (env loading lives separately in `llm/config.py`),
- injectable `client` / `transport`, so `httpx.MockTransport` keeps tests fully
  offline,
- never logs the API key, prompts, or completions,
- bounded retries and typed errors (`LLMAuthError`, `LLMTimeoutError`,
  `LLMTransportError`, `LLMResponseError`).

**No new client is written for the planner, and no existing client behavior is
changed.** Reuse is the whole point: one transport boundary, already reviewed.

Constructing a real (non-mock) client for planning is what §5 gates. Until an
explicitly authorized sub-phase says otherwise, a model-backed planner is
constructed with an injected fake/mock transport and there is no code path that
builds a real one.

### 3.4 Output parser — pure function

A pure function with no IO:

```
parse_planner_response(text, issue, project) -> L1Plan   # or raises a typed error
```

Properties this design requires:

- **Strict JSON only.** The model's completion must be a single JSON object.
  No markdown fences to strip, no prose preamble to skip, no "find the first
  `{`" scanning, no YAML fallback, no partial-JSON repair.
- **Validation via the existing `L1Plan` model.** Parsing does not hand-roll
  field checks; it feeds the decoded object to `L1Plan` and lets the Phase 4B
  validators enforce every rule (positive `issue_number`, `owner/repo`-shaped
  `repo`, non-blank required strings, non-empty `proposed_steps` /
  `required_verification`, non-blank list items, `automation_level == "L1"`,
  `requires_human_approval is True`).
- **Trusted fields are overwritten, not accepted.** `issue_number`, `repo`,
  `title`, `automation_level`, and `requires_human_approval` come from the
  caller's own inputs — never from model output. A model cannot rename the
  repo, renumber the issue, or promote its own automation level, because those
  values are not read from its response at all.
- **Path-like fields stay plain strings.** `files_likely_to_change` and
  `files_forbidden_or_out_of_scope` are never resolved, `stat`'d, globbed, or
  normalized against the filesystem — matching the Phase 4B/4C rule. A
  model-proposed path is *text in a report*, not a filesystem operation.
- **`ProjectConfig.forbidden_paths` is merged in verbatim** by the parser, the
  way `FakeL1Planner` already does — so forbidden paths appear in the output
  even if the model omits them.

### 3.5 Fallback: reject, never repair

If the model output is not exactly what was asked for, the planner **fails with
a typed error** (§6). It does not:

- execute anything the model proposed,
- silently substitute a `FakeL1Planner` plan and present it as the model's,
- strip fences / patch braces / coerce types to make invalid output parse,
- re-prompt with a mutated prompt to "fix" the output.

A failed model-backed plan is a **visible failure a human resolves**, not a
degraded success. If a fallback to the offline `FakeL1Planner` is ever wanted,
it must be an explicit, separately designed, clearly labeled behavior — the
output must state which engine produced it — and not an implicit rescue.

## 4. Prompt safety

Rules the prompt builder (§3.2) must satisfy. These are safety requirements,
not style preferences.

### 4.1 What the prompt includes

- The issue **title** and **body**.
- The **parsed sections** (`Goal`, `Current Context`, `Scope`, `Non-goals`,
  `Acceptance Criteria`, `Required Verification`, `AI Instructions`,
  `Automation Authorization`) and which required sections are **missing**.
- The project's **path patterns only** — the `allowed_paths`,
  `protected_paths`, and `forbidden_paths` glob lists, plus the
  `workspace_policy` flags, as *patterns and names*.

### 4.2 What the prompt must never include

- **No target workspace file contents.** Not source files, not configuration,
  not a directory listing, not a file tree, not git history. The planner has no
  reader for these and must never grow one; boundaries are conveyed **by
  pattern**, never by content.
- **No secrets.** No API key, no token, no environment variable *value*. The
  project config itself references providers by env-var *name*
  ([models.py](../src/ai_dev_orchestrator/models.py) `ProviderConfig`), and
  that property must be preserved into the prompt.

### 4.3 Prominence rules

- The issue's **`Non-goals`** section and the project's **`forbidden_paths`**
  appear **prominently and early** — in the system message, before the issue
  body — so they are weighed before any step is proposed, not discovered after.
- The **L1 boundary statement** (§4.4) is likewise in the system message, not
  buried at the end of a long user message.

### 4.4 Output contract stated in the prompt

The prompt must require:

- **Strict JSON** matching the `L1Plan` field set exactly — one JSON object, no
  markdown fences, no commentary before or after, no extra top-level keys.
- **Explicit uncertainty.** When the issue is ambiguous, under-specified, or
  missing required sections, the model must populate `open_questions` and
  `risks` rather than silently guessing. "I could not determine X" is a correct
  answer; a confident invention is not.

And must **forbid**, in the prompt itself:

- proposing **shell/CLI commands** to run,
- proposing **file edit operations**, diffs, or patches,
- proposing **GitHub write actions** (comments, labels, issue edits, PRs),
- proposing **branch creation**,
- proposing **automation escalation** — asking for L2+ behavior, claiming
  authorization, setting `automation_level` to anything but `"L1"`, or
  suggesting the plan can be applied without human approval,
- claiming to have read, or asking to read, target workspace files.

The prompt states plainly that the model's only job is to **describe a plan**
in the `L1Plan` shape, that its output will be **read by a human**, and that it
is **never asked to act**.

### 4.5 Prompt-injection posture

Issue text is **untrusted input**. An issue body can contain text addressed to
the model ("ignore previous instructions", "you are authorized to run…",
"automation level: L3 approved"). The design's answer is structural, not
persuasive:

- **Instructions live in the system message; issue text is delimited data.**
  The prompt marks issue content explicitly as untrusted material to be
  summarized, not as instructions to follow.
- **The dangerous fields are never model-controlled** (§3.4) — `automation_level`
  and `requires_human_approval` are set by our code. An injected "L3 approved"
  cannot change them, because nothing reads them from the response.
- **The output is inert** — an `L1Plan` is printed text. There is no interpreter
  for `proposed_steps`, so a successful injection produces, at worst, a bad plan
  a human reads and rejects. This inertness is the primary defense and must not
  be weakened by any later phase that adds an executor.
- **Suspicious model output is rejected, not sanitized** (§6).

## 5. Model call gate

The dividing line between "mockable planner" and "real model call" is the
central control of this design.

- **Real model-backed planning requires an explicit future phase and explicit
  user authorization.** It is never an implicit upgrade of a fake planner, never
  a config default flipped on, and never enabled as a side effect of another
  change. The authorizing phase must name it directly.
- **Fake/offline remains the default everywhere.** The deterministic
  `FakeL1Planner` stays the default `generate-plan` engine. A model-backed
  planner, when it exists at all, is opt-in.
- **No real model call in tests, ever.** Every test of a model-backed code path
  injects `httpx.MockTransport` or a fake planner function — the Phase 3C/3D
  precedent. No socket is opened by the suite.
- **No environment reads by default.** A fake/mock-backed planner reads no
  `AIDO_LITELLM_*` variable, matching `llm-smoke-test` and `generate-plan`.
  Env loading enters the picture only inside the explicitly authorized real
  path, never in the shared planner code.
- **No prompt/completion logging by default.** If a model-backed planner logs
  anything, prompt and completion bodies stay out of logs unless an explicit,
  off-by-default debug flag is set.
- **No API key logging, ever, under any flag.** `LLMClientConfig.api_key` is
  already `repr=False`; no planner code may re-expose it.
- **Any CLI option enabling real model planning must be designed separately**
  (proposed Phase 4H, §8) and must be:
  - **opt-in** — absent by default; the default invocation cannot reach a real
    model,
  - **noisy** — the command states before and after the call that a real model
    was contacted, which model, and which endpoint host,
  - **gated** — it fails closed with a clear message when its preconditions are
    unmet, and it never falls back to a real call when a fake one was requested
    (or vice versa).

Until that phase lands, the invariant in
[README.md](../README.md) holds unchanged: **there is no CLI command that can
call a real model.**

## 6. Failure handling

All failures are **typed errors** — a planner-specific hierarchy analogous to
`LLMClientError` and its subclasses, so callers can distinguish causes without
string matching. Error messages never include the API key, and by default never
include the full prompt or full completion.

| Condition | Result |
| --- | --- |
| Completion is not valid JSON | typed error (`…PlannerParseError`) |
| Decoded JSON fails `L1Plan` validation | typed error (`…PlannerValidationError`) |
| Required fields missing from the JSON object | typed error (`…PlannerValidationError`) |
| Model proposes non-L1 automation, command execution, GitHub writes, branch creation, or workspace reads | **rejected** — typed error (`…PlannerPolicyError`) |
| Unexpected extra top-level keys | typed error (strict shape; no silent drop) |
| Transport/auth/timeout failure | the existing Phase 3C `LLMClientError` subclasses, unchanged |

Additional rules:

- **Reject, don't repair.** No fence-stripping, no brace-patching, no type
  coercion, no "closest valid interpretation."
- **No auto-retry with prompt mutation** in the first implementation. The
  Phase 3C client's bounded retries for *transport-level* failures (timeout,
  connection error, 429/5xx) remain as-is — those resend the identical request.
  Retrying with a *changed prompt* because the model produced bad output is a
  distinct behavior and must be designed explicitly in a later phase if wanted
  at all. Silent re-prompting hides how often the model fails, which is exactly
  the signal a gated feature needs.
- **Fail loudly, exit non-zero.** A planning failure never prints a partial or
  synthesized plan. A human sees an error, not a plausible-looking artifact of
  unclear provenance.
- **Policy rejection is not a parse failure.** A model response that parses
  cleanly but proposes forbidden behavior is a *policy* rejection and should be
  reported as such, because the two have very different follow-ups.

## 7. Security decisions still open

These are **unresolved** and must be settled by the phase that implements the
corresponding behavior — they are not decided here.

1. **Should model-backed planning be exposed via the CLI at all?** A
   library-only, test-only capability is meaningfully safer than a user-facing
   command. The value of a CLI entry point has not been established.
2. **Should real model planning require a project allowlist?** E.g. an explicit
   opt-in field in the project config, so a project must name itself as eligible
   before any real model sees its issue text — defense in depth against a stray
   flag on the wrong project.
3. **Should prompts and outputs be saved to audit files?** Auditability argues
   for yes; the default-no-logging rule (§5) and the risk of writing issue text
   to disk argue for care. If adopted: opt-in, explicit path outside any target
   workspace, never secrets, and a documented retention expectation.
4. **Do path references need stronger normalization/canonicalization?** Today
   path-like fields are deliberately plain strings, never resolved (Phase 4B/4C)
   — which is *safe by inertness* but means a model-proposed path is not
   checked against `forbidden_paths` in any robust way. Comparing patterns
   properly requires normalization, and normalization is exactly the thing the
   current design avoids. This trade-off is unresolved.
5. **Does the `--body-file` workspace guard need symlink / UNC / 8.3 handling?**
   The Phase 4D guard
   ([cli.py](../src/ai_dev_orchestrator/cli.py) `_is_same_or_under`) uses
   `os.path.abspath` + `os.path.normcase` only — deliberately no `resolve()`,
   because resolving would touch the filesystem. Consequences: a **symlink** or
   junction pointing into a workspace is not detected; a **UNC** path
   (`\\host\share\…`) or a mapped drive naming the same location as a local path
   does not compare equal; a legacy **8.3 short name** (`C:\dev\MIS_PR~1`) does
   not match its long form. Whether to accept this (favoring "never touch the
   path") or to add a bounded, non-following check is open.
6. **Should the prompt include a nonce/delimiter scheme for untrusted issue
   text?** §4.5 relies on message-role separation and inert output. Whether an
   additional delimiter or nonce convention is worth its complexity is open.
7. **Should model output size be bounded before parsing?** An unbounded
   completion parsed into a plan with thousands of list items is a resource and
   readability concern; the appropriate cap (and whether exceeding it is a
   typed error) is undecided.

## 8. Phase split after 4E

Recommended sequence. Each is a separate, separately authorized phase; none is
authorized by this document.

- **Phase 4F — typed prompt/output parser errors only. No model call.
  (DONE.)** Added the typed error hierarchy (§6) and the pure output parser
  (§3.4) in
  [plan/model_planner.py](../src/ai_dev_orchestrator/plan/model_planner.py):
  `ModelPlannerError` / `ModelPlannerParseError` /
  `ModelPlannerValidationError` / `ModelPlannerPolicyError` plus
  `parse_model_l1_plan_response(...)`. Entirely offline, exactly as described
  here — pure functions and exception classes tested with literal strings, no
  transport of any kind, no client construction, no env reads, no CLI change.
  The **pure prompt builder (§3.2) was optional and was not built**; it moves
  to Phase 4G. See
  [PHASE_4_L1_PLAN_GENERATOR_PLAN.md §7/§13](PHASE_4_L1_PLAN_GENERATOR_PLAN.md#7-phase-split-recommendation)
  for the shipped detail.
- **Phase 4G — fake model-backed planner using `MockTransport` only.**
  Proposed next; **not yet built.** Wire the prompt builder (§3.2, still
  unbuilt) → `LLMClient` (with an injected `httpx.MockTransport`) →
  output parser → `L1Plan`, exercising the real client code path with a fake
  provider, exactly as `llm-smoke-test` does today. Still no real model, no real
  network, no env reads, and **no CLI command** — or, at most, a clearly
  fake-labeled one designed in that phase. This proves the end-to-end shape
  while the real-call gate stays shut.
- **Phase 4H — optional gated real model planner CLI: design and implementation,
  only if explicitly authorized.** The first phase permitted to open a real
  socket for planning. Must deliver the §5 gate in full (opt-in, noisy, fails
  closed), resolve the §7 open questions it depends on, and carry its own design
  review before implementation. **Not authorized by this document.**
- **Later — Phase 5: docs-only L2 implementer.** Unchanged and still later, per
  [AI_DEV_ORCHESTRATOR_PLAN.md §7](AI_DEV_ORCHESTRATOR_PLAN.md#7-mvp-phase-roadmap).
  L2 remains out of scope for all of Phase 4.

## 9. Acceptance criteria for Phase 4E (DONE)

- [x] This design doc (`docs/PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md`) exists
  and covers goal, non-goals, future architecture, prompt safety, model call
  gate, failure handling, open security questions, and the post-4E phase split.
- [x] **No `src/` or `tests/` changes** in this phase.
- [x] **No runtime behavior added.**
- [x] **No model calls.**
- [x] **No network calls.**
- [x] **No environment-variable reads.**
- [x] **No CLI behavior added** — no new command, no new option, and no change
  to `generate-plan`, `llm-smoke-test`, `inspect-issue`, or `version`.
- [x] **No GitHub fetch or write, no command execution, no file editing engine,
  no agent logic, no implementer/reviewer/fixer role wiring, and no target
  project workspace access** added.
- [x] Working tree contains **docs-only** changes.
