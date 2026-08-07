# Phase 4H — Gated Real Model Planner (Design Review Only)

> **This document is a design review only. Phase 4H ships no runtime code.**
>
> It contains **no implementation**, makes **no model call**, makes **no
> network call**, reads **no environment variable**, calls
> **no `load_llm_client_config_from_env`**, and adds **no CLI command or
> option**. It changes neither `generate-plan` nor `llm-smoke-test`.
>
> It refines §5 (model call gate) and §7 (open security questions) of
> [PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md](PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md)
> for the one case Phase 4E deliberately left shut: a **real** model call made
> on behalf of an L1 planner.
>
> **Scope note.** Phase 4E's §8 listed "Phase 4H" as *design and
> implementation* of the gated real planner. That is now split: **Phase 4H is
> the design review only**, and implementation moves to the separately
> authorized Phase 4I / 4J / 4K / 4L sequence in §12. Nothing in this document
> is authorized to be built by this phase.
>
> **The invariant in [README.md](../README.md) is unchanged by this phase:
> there is still no CLI command that can call a real model.**
>
> **Update (Phase 4K, DONE):** that invariant has since been **deliberately
> retired by an explicitly authorized phase**. `real-llm-smoke-test` (§12) can
> call a real model — but only a *connectivity* call, only behind the full gate
> below, and only with an explicit `--real-model` flag. It sends a fixed prompt
> and **no issue text**, and produces **no plan**. There is still no CLI command
> that can plan with a real model.

## 1. Goal

Describe how a **future, explicitly authorized phase** could safely enable
**real** model-backed L1 planning — the Phase 4G
[`ModelBackedL1Planner`](../src/ai_dev_orchestrator/plan/model_planner.py) path
running against a genuine internal LiteLLM endpoint instead of an injected
`httpx.MockTransport`.

The goal is a **transport swap behind a hard gate, not a capability
expansion**. Everything downstream of the model call stays exactly as Phase
4F/4G built it:

- **Output is still only an [`L1Plan`](../src/ai_dev_orchestrator/plan/models.py)** —
  same nine model-controlled fields, same five caller-trusted fields, same
  Phase 4B validation, same Phase 4F strict parser and policy guard.
- **Still plan-only.** A real model call must not enable, and must not be
  accompanied by: file edits, command execution, GitHub writes (comments,
  labels, issue edits), branch creation, pull requests, or any read of a target
  project workspace tree or file contents.
- **The only new thing is a socket** — opened by the already-reviewed Phase 3C
  [`LLMClient`](../src/ai_dev_orchestrator/llm/client.py), to an endpoint named
  by environment variables, carrying a prompt built by the already-reviewed
  Phase 4G pure prompt builder.

Restating what does *not* change makes the risk surface precise: real model
planning changes **who writes the plan text and whether a network request
leaves the machine**. It changes nothing about what the orchestrator is allowed
to *do* with that text. The answer remains "print it for a human."

**This phase implements none of it.** Each item below becomes buildable only
when a later, explicitly authorized sub-phase (§12) asks for it by name.

## 2. Non-goals

Explicitly out of scope for Phase 4H:

- **No implementation in Phase 4H.** No new module, no new function, no new
  test, no change under `src/` or `tests/`.
- **No real model call.** Not in this phase, and not by any code this phase
  produces (it produces none).
- **No network call** of any kind.
- **No environment loading.** Phase 4H does not read `AIDO_LITELLM_BASE_URL`,
  `AIDO_LITELLM_API_KEY`, `AIDO_LITELLM_DEFAULT_MODEL`,
  `AIDO_LITELLM_TIMEOUT_SECONDS`, `AIDO_LITELLM_MAX_RETRIES`, or any other
  environment variable, and does not call
  [`load_llm_client_config_from_env`](../src/ai_dev_orchestrator/llm/config.py).
- **No CLI change.** No new command, no new option, and no behavior change to
  `generate-plan`, `llm-smoke-test`, `inspect-issue`, or `version`. In
  particular no `--real`, `--live`, `--model`, `--use-env`, `--github`, or
  `--fetch` option is added anywhere.
- **No GitHub fetch change and no GitHub write.** Issue access stays read-only
  and stays where Phase 2 put it.
- **No agent loop** — no plan/act/observe cycle, no self-retry with mutated
  prompts, no tool use, no multi-step orchestration, and no agent framework
  (LangGraph / CrewAI / AutoGen / n8n).
- **No target workspace access** — no read, list, stat, glob, or resolve of
  anything under a configured `repo.workspace_path`.
- No implementer / reviewer / fixer role wiring, no file editing engine, no
  command execution engine.

## 3. Real-call gate design

The gate is the whole point of this document. Its design principle is
**fail-closed**: every precondition must be *affirmatively satisfied* before a
socket opens, and the absence, ambiguity, or unreadability of any precondition
is an error — never a silent default, never a fallback.

### 3.1 Opt-in, never default

- Real model planning is **off unless explicitly turned on at the call site**.
  There is no configuration state, environment variable, or installed package
  that can make a default invocation reach a real model.
- Turning it on requires **two independent affirmations** that cannot both be
  supplied by accident:
  1. an explicit, clearly named CLI/API entry point or flag (§6), and
  2. an explicit per-project opt-in in the project config (§4).
- The existing offline paths keep their current guarantee: `generate-plan` and
  `llm-smoke-test` remain incapable of a real call, and neither grows a flag
  that changes that. A user who wants a real call must **type a different
  command** (§6).

### 3.2 No silent reuse of the fake/offline path

- The real path must **not** be "the fake path with a different transport
  injected by config." The distinction must be visible in the command the user
  typed and in the output the user reads.
- **No fake→real promotion.** A request for the offline planner never becomes a
  real call because env vars happened to be set, or because a config field was
  enabled.
- **No real→fake demotion.** A request for a real call that cannot be satisfied
  (missing env, endpoint down, auth failure, disallowed model) **fails**; it
  never quietly substitutes a `FakeL1Planner` plan and presents it as a plan.
  This is the Phase 4E §3.5 "reject, never repair" rule applied to the gate
  itself.
- Consequence: there is exactly **one** code path that constructs a real client,
  it is reachable only from the real entry point, and it is the only place
  `load_llm_client_config_from_env` may be called.

### 3.3 Noisy before and after

The command must make a real model call **impossible to miss in a terminal
scrollback**, because "did that just call a real model?" must never be a
question a reader has to answer by re-reading source.

- **Before the call**, to stderr, it prints a warning block naming:
  - that a **real** model call is about to be made,
  - the **endpoint host** (host only — see §5.3),
  - the **model name**,
  - the **project id** and **issue number/repo**,
  - that issue text will be transmitted to that endpoint.
- **After the call**, to stderr, it prints a matching block confirming that the
  call completed (or failed), with the same host/model identifiers.
- The plan itself goes to **stdout**; the warnings go to **stderr**, so piping
  the JSON to a file still leaves the warnings visible, and the JSON stays
  machine-parseable.
- The banner is **not suppressible** in the first implementation. A `--quiet`
  that hides "a real model was contacted" is a footgun; if quiet mode is ever
  wanted, it is a separate, separately reviewed decision.

### 3.4 Preconditions — all of these fail closed

| Precondition | On failure |
| --- | --- |
| Explicit real-model entry point / flag present | not reached at all; default path is offline |
| Required `AIDO_LITELLM_*` env vars present and valid | **error**, exit non-zero, no call (§5) |
| Project config explicitly enables real model planning | **error**, exit non-zero, no call (§4) |
| Requested model is in the project's model allowlist | **error**, exit non-zero, no call (§4) |
| No input would carry target workspace file contents | **error**, exit non-zero, no call (§8) |
| `--body-file` passes the Phase 4D workspace guard | **error**, exit non-zero, no read, no call (§8) |
| Audit path (if requested) is outside every workspace | **error**, exit non-zero, no call (§7) |

Ordering matters: **every** precondition is checked **before** the client is
constructed and before any input file is read. A failure must never leave a
half-sent request or a partially written audit file.

### 3.5 No workspace content may reach the prompt

The gate must verify, structurally rather than by inspection, that the prompt
cannot contain target workspace file contents:

- The prompt builder's inputs remain exactly `GitHubIssue` / `ParsedIssue` /
  `ProjectConfig` (§8). There is no fourth input, and the real path must not add
  one.
- The real entry point must reject any option that would supply repository
  content — no `--file`, `--context-file`, `--tree`, `--diff`, or equivalent.
- The Phase 4D `--body-file` guard is reused unchanged: a body file that *is*,
  or sits *under*, the configured `repo.workspace_path` is rejected **before it
  is read**.
- This is worth stating as a gate precondition even though Phase 4G's prompt
  builder already has no reader for workspace files: the gate is the layer that
  must stay correct if a later phase is careless.

### 3.6 Explicit provenance

Output must state which engine produced it (§9). "Fake/offline" and
"real-model" plans must not be confusable after the fact — not in the terminal,
not in a saved JSON file, not in a pasted snippet. A plan whose provenance is
ambiguous is a plan whose trust level is unknown.

## 4. Project allowlist design

**Proposed future config field — not implemented, not parsed, not validated by
this phase.** `ProjectConfig`
([models.py](../src/ai_dev_orchestrator/models.py)) is `extra="forbid"`, so this
block would be **rejected** by today's loader; adding it is Phase 4I's job (§12).

> **Update (Phase 4I, DONE):** the block below is now a real, typed, validated
> config field.
>
> **Update (Phase 4J, DONE):** it is now also **enforced** — by the library gate
> in
> [plan/real_model_gate.py](../src/ai_dev_orchestrator/plan/real_model_gate.py)
> (§12), over an **injected** env mapping and an **injected** client. No command
> reads it: there is still no CLI path to a real model call.

```yaml
# projects/<project>.yaml  — typed in Phase 4I; enforced by nothing yet
real_model_planning:
  enabled: false
  allowed_models:
    - minimax-m2.7
    - qwen3.6-27b
  allow_prompt_audit_files: false
```

### 4.1 Default false

`enabled` defaults to `false`, and an **absent** `real_model_planning` block
means disabled. Both the missing case and the explicit-false case fail closed,
so no existing project config silently becomes eligible when the field is
introduced. Enabling requires a human to edit a checked-in YAML file — a
reviewable, diffable, blameable act, unlike setting an env var in a shell.

### 4.2 Project-local opt-in

The opt-in lives in the **project config**, not in global config and not in the
environment, because the unit of risk is *the project whose issue text gets
transmitted*. This is the answer to Phase 4E §7 open question 2.

Why it matters: this repo's whole posture is that `mis_project`, `a8_oa`, and
`bible_reading_v2` are **out of bounds**. A stray flag on the wrong
`--project-config` is exactly the mistake this field is meant to stop. With the
allowlist, sending the wrong project's issue text to a model requires editing
*that project's* config file first — not just mistyping a path.

### 4.3 Model allowlist

`allowed_models` is an explicit list of model names the project may be planned
with. Rules:

- **Empty or missing list ⇒ no model is allowed**, even when `enabled: true`.
  An empty list is not "any model"; the permissive reading of an ambiguous
  config is the wrong default.
- The requested model must match a list entry **exactly** — no globs, no
  prefixes, no normalization. Fuzzy matching on model names is a silent way to
  reach an unintended (possibly external, possibly paid) model.
- `AIDO_LITELLM_DEFAULT_MODEL` does **not** bypass the allowlist. If the env
  default is not in `allowed_models`, the run fails; the env supplies
  *connection* details, the project config supplies *permission*.

This bounds cost and data exposure per project, and it keeps the provider policy
in [README.md](../README.md) enforceable at the point of use: no external paid
API by default, because no external model name is in anyone's allowlist.

### 4.4 `allow_prompt_audit_files`

A third, separately defaulted-false switch governing §7. Writing prompts and
completions to disk means writing **issue text** to disk; that deserves its own
opt-in rather than riding along with `enabled`.

### 4.5 Why the allowlist is not sufficient alone

The allowlist is **defense in depth, not the gate**. It stops "right command,
wrong project." It does not stop "right project, unintended invocation" — that
is what the explicit command/flag (§6) and the noisy banner (§3.3) are for.
Both layers are required; neither substitutes for the other.

## 5. Env / config design

### 5.1 Env vars used

The existing Phase 3B names
([llm/config.py](../src/ai_dev_orchestrator/llm/config.py)), unchanged — no new
variable is introduced:

| Variable | Required | Purpose |
| --- | --- | --- |
| `AIDO_LITELLM_BASE_URL` | yes | Endpoint base URL |
| `AIDO_LITELLM_API_KEY` | yes | Credential (never logged, never displayed) |
| `AIDO_LITELLM_DEFAULT_MODEL` | yes | Default model name (still subject to §4.3) |
| `AIDO_LITELLM_TIMEOUT_SECONDS` | no | Request timeout |
| `AIDO_LITELLM_MAX_RETRIES` | no | Bounded retries |

### 5.2 Where env may be read

- **Env is read only inside the future real path**, and only via the existing
  `load_llm_client_config_from_env`. No new env-reading code is written.
- **Fake/offline paths continue to read no environment variable.**
  `generate-plan`, `llm-smoke-test`, `FakeL1Planner`, the Phase 4F parser, the
  Phase 4G prompt builder, and `ModelBackedL1Planner` itself all stay env-free.
  In particular, `ModelBackedL1Planner` must **keep taking its client by
  injection**; the real entry point builds the client and hands it in. The
  planner class must never learn to construct one.
- Missing or blank required variables ⇒ `LLMConfigError` ⇒ command error, exit
  non-zero, **no fallback** (§10). Reading a `.env` file is still not done.
- **Tests never read the real environment.** `load_llm_client_config_from_env`
  already accepts an injected mapping; every test of the gate uses that plus
  `httpx.MockTransport`, exactly as Phases 3C/3D/4G do.

### 5.3 Secret handling

- **The API key is never logged, printed, echoed, or written to an audit file —
  under any flag, at any verbosity.** `LLMClientConfig.api_key` is already
  `repr=False`; no new code may re-expose it, including in exception messages
  and tracebacks.
- **The endpoint host may be shown** (and should be — §3.3), because knowing
  *where* the data went is a safety property. Show the **host** (optionally
  scheme and port); do **not** dump the full request, the headers, or anything
  key-bearing. A base URL that embeds a credential in userinfo or a query string
  must be reduced to its host before display.
- **No secrets in project YAML.** The Phase 1 rule stands: project configs name
  environment variables (`base_url_env`, `api_key_env`), never values. The
  proposed `real_model_planning` block contains **no** credential field, and
  must never gain one.

## 6. CLI design options

**Designed, not implemented.** No option or command below exists after Phase 4H.

### Option A — extend `generate-plan` with explicit real-model flags

`generate-plan … --real-model --model minimax-m2.7`

*Pros:* one command to learn; shared option parsing and output formatting; the
offline/real difference is a single visible token in shell history.

*Cons, which dominate here:*

- It **breaks a shipped guarantee**. `generate-plan` is documented in
  [README.md](../README.md) and asserted in
  [tests/test_cli_generate_plan.py](../tests/test_cli_generate_plan.py) as
  having no `--live`/`--real`/`--model`/`--use-env` option and no way to reach a
  real model. Adding the flag deletes that guarantee and the test that protects
  it.
- **One command, two trust levels.** Every future change to `generate-plan` then
  has to be reviewed twice — once for the offline path, once for the real path —
  and a bug in shared code (option defaults, config loading, output assembly)
  reaches the real path automatically.
- **Flag-adjacency risk.** `--real-model` sits one typo, one shell-history
  recall, or one copied-script line away from an ordinary offline invocation.
- The env-read boundary blurs: a command that "usually reads no env" becomes
  "reads env sometimes," which is much harder to test as an invariant.

### Option B — a separate command (recommended)

`generate-model-plan … --real-model --model minimax-m2.7`

*Pros:*

- `generate-plan` **keeps its guarantee verbatim** — still offline-only, still
  env-free, still no real-model option, still covered by its existing tests
  unchanged.
- The real path gets its **own** argument parser, its own preconditions, its own
  banner, its own exit codes, and its own tests. "Does this command touch the
  network?" is answered by the command name.
- It mirrors the precedent already in the repo: `llm-smoke-test` is a *separate*
  command for exercising the LLM path, not a flag on something else.
- Removing or disabling the capability later is deleting one command, not
  unpicking flags from a shared one.

*Cons:* some duplicated option plumbing between the two commands, and users must
learn a second name. Both are acceptable — a little duplication is the price of
a boundary that cannot be crossed by a typo, and duplication that keeps trust
levels apart is a feature, not debt.

### Recommendation

**Adopt Option B: a separate command.** Given this project's safety posture —
fail-closed gating, an explicit workspace boundary, and a written "no CLI
command can call a real model" invariant — the argument for keeping the real
path physically separate is strong and the argument against is convenience only.

Additionally, even inside the separate command:

- The real call requires an **explicit flag** (e.g. `--real-model`); running
  `generate-model-plan` without it is an error, not a fake-planner run. The
  command name alone must not be sufficient authorization, so that a future
  `--dry-run`/mock mode can coexist without ever becoming implicit.
- The **model must be named explicitly** (`--model`), and it must pass §4.3. The
  env default does not silently select a model.

### The design must forbid

- **`--real` silently changing `generate-plan` semantics** — including any
  variant where `generate-plan` behaves differently based on env, config, or an
  installed extra. `generate-plan` stays offline, permanently.
- **Any option that fetches from GitHub and calls a real model in one ambiguous
  step.** Two network boundaries (GitHub read, model call) must not hide behind
  one flag; see §8.4.
- **Any default real-model behavior** — no config default, no env default, no
  "if credentials are present, use them," no interactive prompt that offers to
  go real.
- **Any silent fallback in either direction** between the fake and real engines
  (§3.2).

## 7. Prompt / audit design

### 7.1 Should prompts and outputs be auditable?

There is a real tension, and it resolves toward "**yes, but opt-in**":

- *For:* a real model call is the one step whose output is not reproducible from
  the inputs. When a plan looks wrong, the prompt actually sent and the raw
  completion actually received are the only evidence. Without them, debugging is
  guesswork, and prompt-injection incidents are undiagnosable after the fact.
- *Against:* an audit file is **issue text written to disk** — potentially
  internal, personal, or customer-referencing content — in an unencrypted file
  that outlives the run, may be committed by accident, and may be backed up.
  Phase 4E §5's default is no prompt/completion logging, and that default is
  correct.

### 7.2 Safe future approach

- **Default: no prompt or completion logging at all.** Not to stdout, not to
  stderr, not to file, not at any verbosity level. This is the shipped behavior
  of the Phase 3C client and must not regress.
- **Opt-in only, doubly gated**: an explicit CLI flag (e.g.
  `--audit-dir <path>`) **and** `real_model_planning.allow_prompt_audit_files:
  true` in the project config (§4.4). Either alone is insufficient.
- **Audit path safety.** The directory must be inside this repo, or an
  explicitly provided path the user names; it is validated with the **same
  guard** the Phase 4D `--body-file` check uses, and it must be rejected if it
  is, or sits under, **any** configured `repo.workspace_path`. Never write audit
  files into a target workspace — that would turn a plan-only command into
  something that creates files in a forbidden tree.
- **Never any API key** in an audit file, and never full request headers. The
  audit records the *messages*, not the *transport*.
- **Labelled contents.** Each audit record should carry: model name, endpoint
  **host**, UTC timestamp, issue number / repo / title, engine provenance
  (§9), and the outcome (parsed / parse error / validation error / policy
  rejection / transport error). Enough to answer "what did we send where, and
  what came back," and nothing more.
- **Failures are audited too**, when auditing is on — a rejected or malformed
  completion is precisely the case worth keeping.
- **Retention is the user's.** The command writes; it never prunes, uploads,
  or transmits audit files, and the docs should state plainly that these files
  contain issue text and are the user's to manage or delete.

### 7.3 Stated risk

Writing issue text to disk is a **deliberate, acknowledged data-at-rest
tradeoff**. It should be off by default, obvious when on (the banner should say
an audit file was written and where), and never enabled implicitly by any other
flag.

## 8. Input source design

### 8.1 Allowed inputs

Real model planning may consume **only** the three objects the Phase 4C/4G
planners already take:

- **`GitHubIssue`** — `number`, `title`, `body`, `state`, `html_url`, `labels`.
- **`ParsedIssue`** — the canonical sections plus the missing-section report.
- **`ProjectConfig`** — path **patterns**, `workspace_policy` flags, and `repo`
  metadata as configured values.

No fourth input.

### 8.2 Explicitly forbidden inputs

- **No target workspace tree or file contents** — no source files, no config
  files, no directory listing, no file tree, no git history, no diff, no
  `repo.workspace_path` value itself. Boundaries are conveyed **by pattern**,
  never by content, exactly as Phase 4G already implements.
- No option, flag, or config field that would supply such content (§3.5).

### 8.3 Local body file

A local `--body-file` remains the offline way to supply issue text, and it must
still pass the **Phase 4D workspace guard** unchanged: rejected if it is, or
sits under, the configured `repo.workspace_path`, checked **before the file is
read**, using string/path normalization only — never resolving, stat'ing, or
listing that path on disk. The guard's known gaps (symlinks, UNC, 8.3 short
names) are unchanged here and remain open (§11).

### 8.4 If GitHub fetch is ever combined with real model planning

Not recommended for the first implementation, and if ever done:

- GitHub access stays **read-only** — fetching one issue, exactly as Phase 2
  does. No comments, labels, issue edits, branches, or PRs, ever.
- It must be **separately explicit**: a distinct flag from the real-model flag,
  so the user affirms *two* network boundaries independently, and the banner
  names both.
- It must be **impossible to trigger implicitly** — no "fetch if `--issue` looks
  like a number and no body file was given" inference.
- Fetch failure must not fall back to a synthetic or cached issue, and fetched
  text remains **untrusted input** under the Phase 4G delimiter/escaping scheme.

## 9. Output / provenance design

### 9.1 Provenance is wrapper metadata, not `L1Plan` fields

**`L1Plan` gains no fields.** Its schema
([plan/models.py](../src/ai_dev_orchestrator/plan/models.py)) is the Phase 4B
contract, validated by the Phase 4F parser, and adding engine/endpoint fields
would (a) enlarge the surface a model's output is checked against, (b) require
the parser to distinguish yet more trusted-vs-model-controlled fields, and (c)
break every existing consumer and test. Provenance describes **how the plan was
produced**, which is a property of the run, not of the plan's content.

Instead, provenance is a **wrapper the command emits around**
`plan.model_dump()` — the pattern `generate-plan` already uses for its `notice`
field ([cli.py](../src/ai_dev_orchestrator/cli.py)).

### 9.2 Proposed wrapper shape

```jsonc
{
  "notice": "L1 PLAN ONLY — … human must review and approve …",
  "provenance": {
    "engine": "real-model",          // "fake" | "mock-model" | "real-model"
    "real_call": true,               // did a socket open to a real endpoint?
    "model": "minimax-m2.7",
    "endpoint_host": "litellm.internal",   // host only; never the API key
    "generated_at": "2026-08-06T12:34:56Z",// UTC, ISO 8601
    "issue_number": 123,
    "repo": "owner/name",
    "title": "…",
    "project_id": "…"
  },
  "automation_level": "L1",          // from L1Plan, unchanged
  "requires_human_approval": true,   // from L1Plan, unchanged
  "...": "remaining L1Plan fields"
}
```

Rules:

- **`engine`** is one of `fake` (deterministic `FakeL1Planner`), `mock-model`
  (model-backed planner over a mock transport), `real-model` (real endpoint).
  It is set by the command from what it actually did — never from model output.
- **`real_call`** is redundant with `engine` by design: a boolean is trivially
  greppable and hard to misread, and redundancy here is cheap insurance.
- **`endpoint_host` is host-only**, per §5.3. `model`, `generated_at`,
  `issue_number`, `repo`, `title`, and `project_id` all come from the command's
  own inputs.
- **`automation_level: "L1"` and `requires_human_approval: true`** stay inside
  `L1Plan`, where the Phase 4B validators pin them. They are repeated at the top
  of the output only in the sense that they are already there — the wrapper does
  not restate or override them.
- **Determinism note:** `generated_at` makes the wrapper non-deterministic. That
  is acceptable for the *real* command's output but must not leak into the pure
  prompt builder or the parser, which stay clock-free.
- Whether the offline `generate-plan` should also emit a
  `provenance.engine: "fake"` block is a **separate, later decision** — it would
  change existing output and existing tests, so it is not authorized here.

## 10. Failure handling

**Fail-closed, typed, and total.** Every failure below produces a non-zero exit
and **no plan output of any kind** — not a partial plan, not a placeholder, not
a fake plan wearing the real command's name.

| Condition | Result |
| --- | --- |
| Required `AIDO_LITELLM_*` var missing/blank/invalid | `LLMConfigError` → command error, **no call**, **no fallback** |
| Project not allowlisted (`real_model_planning` absent or `enabled: false`) | typed gate error, **no call** |
| Requested model not in `allowed_models` (or list empty/missing) | typed gate error, **no call** |
| Body file inside `repo.workspace_path` | Phase 4D guard error, **no read**, **no call** |
| Audit path invalid or inside a workspace | typed gate error, **no call**, no file written |
| Completion is not exactly one strict JSON object | `ModelPlannerParseError` |
| Decoded JSON fails `L1Plan` validation / missing or extra keys / model supplied a trusted field | `ModelPlannerValidationError` |
| Model proposes commands, file edits, branches, PRs, GitHub writes, workspace reads, escalation, or skipping approval | `ModelPlannerPolicyError` |
| Network / auth / timeout / bad response | existing `LLMTransportError` / `LLMAuthError` / `LLMTimeoutError` / `LLMResponseError`, unchanged |

Additional rules:

- **No new error types are needed for parsing** — Phase 4F's hierarchy is
  reused as-is. The gate's own preconditions warrant a small typed gate error
  (a `ModelPlannerError` subclass, so callers can catch the whole family).
- **No fallback, in either direction** (§3.2). A failed real call is a visible
  failure a human resolves.
- **No auto-retry with prompt mutation.** The Phase 3C client's bounded retries
  for *transport-level* failures (identical request resent) remain; re-prompting
  because the model produced bad output stays out of scope, because silent
  re-prompting hides how often a gated feature fails.
- **Errors never contain the API key**, and by default never contain the full
  prompt or completion (§5.3, §7.2).
- **Policy rejection is distinct from parse failure** — same content, very
  different follow-up. The exit path should make the distinction obvious in the
  message.
- **The "after" banner still prints on failure** (§3.3), stating that a real
  call was attempted and how it ended. Knowing a request left the machine
  matters even when nothing usable came back.

## 11. Remaining open questions

Unresolved; each must be settled by the phase that implements the corresponding
behavior, not here.

1. **Exact CLI command name.** `generate-model-plan`, `generate-plan-real`,
   `plan-with-model`, or something else. §6 recommends the *shape* (a separate
   command plus an explicit flag), not the spelling. *(Settled. Phase 4K
   shipped `real-llm-smoke-test` and Phase 4L shipped `generate-model-plan` —
   the first candidate above — each adopting the recommended shape: a separate
   command plus a required `--real-model` flag.)*
2. **Exact project config schema.** Field names (`real_model_planning` vs.
   something scoped differently), whether it nests under an existing block,
   whether `allowed_models` should reference the existing `providers` /
   `ai_roles` maps instead of naming models directly, and how it interacts with
   `run_limits.max_model_calls_per_issue`.
3. **Should prompt/audit files exist at all?** §7 designs them as
   doubly-opt-in, but "never write issue text to disk" remains a defensible
   position, and shipping without audit files is strictly safer.
4. **Should model output size be bounded before JSON parsing?** Carried over
   from Phase 4E §7.7 and now more pressing: with a real endpoint the completion
   size is not under our control. The appropriate cap, whether it is enforced at
   the client or the parser, and whether exceeding it is a typed error, are
   undecided.
5. **Is stronger path canonicalization needed?** Carried over from Phase 4E §7.4
   and §7.5 — the deliberate "never resolve a path" stance leaves symlinks,
   junctions, UNC paths, mapped drives, and 8.3 short names undetected by the
   `--body-file` and audit-path guards. A real command that transmits data
   raises the stakes of a guard bypass.
6. **Should GitHub fetch and real model planning ever be one command?** §8.4
   says "not first, and only if separately explicit." Whether it should exist at
   all is unsettled.
7. **Should provenance metadata be added to the existing offline
   `generate-plan` output too?** Consistent labelling argues yes; it changes
   shipped output and shipped tests, so it needs its own decision (§9.2).
8. **Should the banner ever be suppressible** (`--quiet`, CI use)? Currently no
   (§3.3); a CI-friendly mode that still records provenance in the output is
   conceivable but unreviewed.

## 12. Proposed implementation split after this design

Recommended sequence. **Each is a separate, separately authorized phase; none is
authorized by this document.** This supersedes the single "Phase 4H — design and
implementation" entry in
[PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md §8](PHASE_4E_MODEL_BACKED_PLANNER_DESIGN.md#8-phase-split-after-4e).

- **Phase 4I — typed config model for the `real_model_planning` allowlist.
  (DONE.)** `RealModelPlanningConfig` and `ProjectConfig.real_model_planning`
  now exist in [models.py](../src/ai_dev_orchestrator/models.py) as pure
  pydantic models (§4), defaulting to disabled: **no env read, no CLI change,
  no client, no network, and no gate function.** A config omitting the block
  still loads, and a block with `enabled: false` is behaviorally
  indistinguishable from an absent one. `allowed_models` rejects blank names and
  duplicates; `extra="forbid"` rejects credential-shaped keys. Nothing reads the
  block yet — enforcement is Phase 4J's job.
- **Phase 4J — the real planner gate as a library function. (DONE.)** The
  precondition checks of §3.4 and the failure taxonomy of §10 now exist in
  [plan/real_model_gate.py](../src/ai_dev_orchestrator/plan/real_model_gate.py)
  as `check_real_model_planning_gate(...)`,
  `create_real_model_l1_plan_with_gate(...)`,
  `endpoint_host_from_base_url(...)`, `build_real_model_provenance(...)`, and
  the typed `RealModelPlanningGateError` (a `ModelPlannerError` subclass, per
  §10). The env mapping is **injected** — `os.environ` is never read, and a
  missing mapping is a gate error rather than a fallback — and the client is
  **injected**, so the module constructs none (`httpx` is not imported;
  `LLMClient` is `TYPE_CHECKING`-only) and **no real network call** is possible.
  `audit_dir` is validated as a **flag only** per §4.4: refused unless
  `allow_prompt_audit_files` is true, and never created, read, stat'd, or
  resolved — §7's audit *writing* is still unimplemented. Per §4.3 a differing
  `AIDO_LITELLM_DEFAULT_MODEL` is not fatal but cannot select the model: the
  returned `LLMClientConfig` has `default_model` pinned to the allowlisted
  `requested_model`, which is also what is passed to the Phase 4G planner.
  Provenance (§9.2) is built without `generated_at`, since clock use was not
  authorized here. Tested with `httpx.MockTransport` and literal env dicts only.
  **No CLI behavior was added**, and there is still no command that can call a
  real model.
- **Phase 4K — real model *smoke test* command. (DONE — explicitly
  authorized.)** `real-llm-smoke-test` in
  [cli.py](../src/ai_dev_orchestrator/cli.py) is the smallest possible first
  real call, and the first code in this repo permitted to open a real socket:
  a fixed trivial prompt, the full §3.3 banner before and after, the full §3.4
  preconditions via the Phase 4J gate, **no issue text, and no planning**. It
  follows §6's recommendation exactly — a **separate command** (Option B), plus
  a required explicit `--real-model` flag, plus an explicitly named `--model`
  that must pass the §4.3 allowlist; the command name alone authorizes nothing.
  Ordering per §3.4: the flag, the project config, the project opt-in, and the
  allowlist are all checked **before** any `AIDO_LITELLM_*` value is read (the
  gate is probed with an empty mapping to get exactly that ordering), and the
  banner is printed **before** the client is constructed. Per §5.3 the API key
  is never printed and the endpoint is shown as a **host only**; per §7.2 no
  prompt/completion audit file is written and no `--audit-dir` option exists.
  Output carries §9.2-shaped provenance with `operation: "smoke-test"` — and
  no `generated_at`, which stays open for §9. Failures follow §10: no output on
  stdout, exit non-zero, and the post-call block appears only when a real call
  was actually attempted. Its tests use `httpx.MockTransport` and literal env
  dicts only and open no socket.
- **Phase 4L — gated real model *plan* command. (DONE — explicitly
  authorized.)** `generate-model-plan` in
  [cli.py](../src/ai_dev_orchestrator/cli.py) is the §6 separate command,
  wiring Phase 4J's gate to the Phase 4G planner with a real client and emitting
  the §9 provenance wrapper. It follows §6 exactly — a separate command (Option
  B) rather than a flag on `generate-plan`, plus a required `--real-model`, plus
  an explicitly named `--model` that must pass the §4.3 allowlist. Ordering per
  §3.4, with one step more than 4K because this command transmits issue text:
  the flag, the project config, the §8.3/Phase 4D `--body-file` workspace guard,
  the project opt-in, and the allowlist are all checked **before** any
  `AIDO_LITELLM_*` value is read (the gate is probed with an empty mapping to
  get that ordering), the environment gate runs next, and **only then** is the
  body file opened, the §3.3 banner printed, and the client constructed. The
  banner states plainly that the issue title and body text will be transmitted.
  Inputs are exactly §8's: `GitHubIssue` (synthesized in memory from `--issue` /
  `--title` / the local body file), `ParsedIssue`, and `ProjectConfig` — **no
  GitHub fetch** (§8.4), no source files, no workspace contents, no directory
  listings, and no git history. Per §5.3 the API key is never printed and the
  endpoint is shown as a **host only**; per §7.2 no prompt/completion audit file
  is written and no `--audit-dir` option exists. Output carries §9.2-shaped
  provenance with `operation: "l1-plan"` — and, unlike 4K, a `generated_at` UTC
  stamp, settling that part of §9 — wrapped around `plan` (the `L1Plan`) and
  `usage`. Failures follow §10: nothing on stdout, exit non-zero, the post-call
  block only when a real call was attempted, and parse/validation/policy
  failures distinguished **by type name without echoing the completion**. Its
  tests use `httpx.MockTransport` and literal env dicts only and open no socket.
- **Later — Phase 5: docs-only L2 implementer.** Unchanged and still later, per
  [AI_DEV_ORCHESTRATOR_PLAN.md §7](AI_DEV_ORCHESTRATOR_PLAN.md#7-mvp-phase-roadmap).
  L2 remains out of scope for all of Phase 4.

Phases 4K and 4L are the **only** ones that would ever open a real socket, and
both were explicitly conditional on authorization. **Both have since been
authorized and shipped.** Those two sockets are reachable only through
`real-llm-smoke-test --real-model` (which carries no issue text) and
`generate-model-plan --real-model` (which carries the explicitly provided local
issue text and nothing else), each with an allowlisting project config. Neither
fetches from or writes to GitHub, edits a file, runs a command, reads a target
workspace, or produces anything above **L1**.

## 13. Acceptance criteria for Phase 4H (DONE)

- [x] This design doc (`docs/PHASE_4H_GATED_REAL_MODEL_PLANNER_DESIGN.md`)
  exists and covers goal, non-goals, the real-call gate, the project allowlist,
  env/config handling, CLI options with a recommendation, prompt/audit design,
  input sources, output provenance, failure handling, open questions, and the
  post-4H phase split.
- [x] **No `src/` or `tests/` changes** in this phase.
- [x] **No runtime behavior added.**
- [x] **No model calls.**
- [x] **No network calls.**
- [x] **No environment-variable reads**, and no call to
  `load_llm_client_config_from_env`.
- [x] **No CLI behavior added** — no new command, no new option, no real/live/
  model option, and no change to `generate-plan`, `llm-smoke-test`,
  `inspect-issue`, or `version`.
- [x] **No GitHub fetch or write, no command execution, no file editing engine,
  no agent logic, no implementer/reviewer/fixer role wiring, and no target
  project workspace access** added.
- [x] Phase 4H is clearly marked **design-only**; real model planning remains
  **unauthorized and unimplemented**.
- [x] Working tree contains **docs-only** changes.
