# Phase 5F3B-I2A — B300 / Pi Route and Credential Boundary Design

## CURRENT STATUS (read this first)

**DESIGN + LOCAL-RUNTIME-SOURCE-INSPECTION ONLY. No candidate model was run. No
network request, no model call, and no Pi process launch occurred while
producing this document.** Every mechanism below was established by reading:
locally installed Pi package source and bundled docs
(`@earendil-works/pi-coding-agent@0.84.3`, resolved at
`C:\Users\LEVIN-Z\AppData\Roaming\npm\node_modules\@earendil-works\pi-coding-agent`),
the accepted `docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md`, and the
frozen `experiments/pi_external_runtime_ar2/`,
`experiments/pi_external_runtime_ar2_o1/`, and existing AIDO reviewer/LLM
provider source under `src/ai_dev_orchestrator/`.

No environment-variable *value* was read, printed, or dumped at any point.
Only environment-variable *names* and Pi's own bundled source/docs were
inspected. No `set`/`env`/`printenv`/`os.environ` dump was executed.

This document **answers** 5F3B §15.2's and §25(Q2)'s open credential/route
question with local evidence, and it **freezes the architecture** I2
implementation must follow. It does **not** authorize I2 implementation to
begin coding — that remains a separate go/no-go, given in §25.

**Phase 5F3B-I2A-FU1 corrected four semantic inconsistencies in this
document** (§7.1, §11, §16, §12) — none of them changed the accepted
architecture (§6's chosen mechanism, the environment/config/cleanup design,
candidate symmetry, or the `maxTokens`-omission policy are all unchanged).
FU1 closed: (1) an incorrect equation of "one semantic prompt" with "one
provider HTTP request," and a false claim that `maxRetries: 0` bounds that
count; (2) a self-contradiction in the parent-side credential lifetime
(§8/§11 claimed no second reference existed, while also requiring the value
survive for `ArtifactSafetyContext` scrubbing); (3) a missing distinction
between a credential/route failure discovered *before* the one authorized
semantic prompt (`INFRASTRUCTURE_REFUSAL`) and one discovered only *after*
it was sent (`INFRASTRUCTURE_CONTAMINATED`, §16/§18); and (4) an overstated
claim that Q1/Q2 would make the wire-level `max_tokens` request body
observable, when no request-body observer exists in this architecture
(§12). See the correction record at the end of this document for the exact
before/after of each.

**Phase 5F3B-I2A-FU2 closed four remaining consistency issues** left after
FU1, none reopening the accepted architecture: (1) §23's I2-5 slice and the
Appendix lifecycle summary still described cleanup-verification failure as
unconditionally `INFRASTRUCTURE_CONTAMINATED`, contradicting §18's own
phase-aware rule — both are now phase-aware; (2) §19 listed
`provider_inference_requests_per_task` as though a numeric count were
observable, when no observer for it exists — replaced with an honest
`..._observation_available = false` field, keeping the underlying
"one prompt may cause many provider requests" invariant from §7.1 intact;
(3) the `16384` Pi-internal `maxTokens` default was stated as an
unconditional fact — rescoped to source provenance tied to the exact
inspected version (`0.84.3`), with `NOT_REESTABLISHED_FOR_OBSERVED_VERSION`
as the honest per-run fallback for a different (still capability-gated,
still unpinned) Pi version; (4) §9 implied I2 might silently fall back to a
keyless placeholder credential — withdrawn; this qualification route
requires the established `AIDO_LITELLM_API_KEY`, and a missing/blank value
is a pre-prompt `INFRASTRUCTURE_REFUSAL` (§16.A), never a silent
placeholder branch. See the FU2 correction record at the end of this
document.

**Phase 5F3B-I2A-DESIGN-FU3 superseded exactly ONE statement in this
document: §15 item 6.** That item claimed the zero-prompt `get_commands` gate
proves "exactly `aido_read`/`aido_edit` registered, nothing else" — a claim
about the **active tool registry**, which frozen AR0-FU1 §4.1j records
(source-verified) that Pi exposes no RPC command to enumerate, and which
AR2D §2.2's *mandated* truthfulness correction already ruled must never be
made. It is additionally unsatisfiable, because `get_commands` enumerates
`pi.registerCommand` slash commands while those two names are
`pi.registerTool` tools. The item's original text is preserved verbatim, in
place, under an explicit `SUPERSEDED BY` marker; the corrected observability
contract, the H1 proof contract, the credential-read ordering invariant, the
synthetic-workspace authority rule and the creator partial-failure contract
live in
[`docs/PHASE_5F3B_I2A_DESIGN_FU3_CATEGORY_B_OBSERVABILITY_CORRECTION.md`](PHASE_5F3B_I2A_DESIGN_FU3_CATEGORY_B_OBSERVABILITY_CORRECTION.md).
**No other section, semantic, or verdict of this document is changed by FU3**,
and §25's GO/NO-GO stands exactly as written.

## 1. Status / scope

| | |
|---|---|
| Phase | 5F3B-I2A — B300 / Pi Route and Credential Boundary Design |
| Kind | Design + local source/config inspection only |
| Writes | `docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md` only |
| Live activity | **None.** No prompt, no inference, no HTTP request, no Pi process launch, no credential value read |
| Candidate qualification | **Not begun.** Q1/Q2 remain unauthorized and unattempted |
| Frozen inputs | `docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md`, `experiments/pi_external_runtime_ar1/`, `experiments/pi_external_runtime_ar2/`, `experiments/pi_external_runtime_ar2_o1/`, `experiments/pi_implementer_qualification/` — none modified |

This document is the credential/route half of 5F3B's roadmap slice **I2**
(`docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md` §15.2, §24). It
answers, from local evidence rather than assumption, exactly which mechanisms
Pi 0.84.3 supports for reaching a custom OpenAI-compatible route with a
credential, and it designs the smallest architecture that lets AIDO's
qualification harness use one of them without ever placing a real credential
in a model prompt, a retained artifact, argv, or Git-tracked config.

## 2. Why I2A exists

5F3B §15.2 already established that both first-round implementer candidates
(`qwen3-coder-next`, `minimax-m2.7`) are served on B300 through the operator's
existing local LiteLLM proxy — the same backend surface AIDO's own
`l2-review-approved-file-edit` reviewer and `b300_reviewer_benchmark` already
use — and that the frozen AR1/AR2/O1 Pi harness has **no route to it**: AR2's
generated `models.json` is keyless-only, AR2's launch environment forbids any
name containing `MINIMAX`/`QWEN`/`OPENAI`/`PROXY`, and AR2/O1's config loader
hard-pins one model. §15.2 named the required slice **5F3B-I2** and listed,
without designing them, a route descriptor, a config loader, and "a narrow,
audited credential passthrough... if the route requires one."

The key unresolved question — restated from the task brief — is **whether Pi
can be given the B300 route and a credential at all, and by which exact
mechanism**, without embedding a real secret in a model-visible or
Git-tracked place. This document answers that from Pi's own source rather
than guessing, and designs the boundary. It does not implement it.

## 3. Accepted I1 prerequisites (binding, not reopened)

Everything in `docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md` §3, §7–§21
stands unchanged: the outcome taxonomy, the hard bar, the ranking policy, the
token policy (`aido_requested_max_output_tokens = null`, generated
`models.json` omits `maxTokens`), the run-validity/attribution model, and the
`ArtifactSafetyContext` shape from `experiments/pi_implementer_qualification/qualification/safety.py`
(`endpoint_host`, `api_key`, `bearer_token`, `broker_token`, `pipe_name`,
`capability_id`, `workspace_absolute_path`). I2A designs **on top of** these
and reopens none of them.

## 4. Local Pi source facts inspected

Locally installed package: `@earendil-works/pi-coding-agent@0.84.3`
(`package.json:3`), at
`C:\Users\LEVIN-Z\AppData\Roaming\npm\node_modules\@earendil-works\pi-coding-agent`.
Per 5F3B §14 and the task brief, this version is **provenance only** — no
exact pin, no semver range is introduced by this design.

Files read for this design (all local, no network):

- `docs/custom-provider.md` — extension `pi.registerProvider()` API, config
  reference, `apiKey` value-resolution syntax.
- `docs/providers.md` — built-in provider env-var table, auth-file shape,
  key-resolution rules, credential resolution order.
- `docs/models.md` — `models.json` schema, provider/model configuration
  tables, value-resolution rules, explicit statement that shell commands are
  "resolved at request time."
- `docs/environment-variables.md` — the full set of variables Pi itself reads
  (`PI_CODING_AGENT_DIR`, `PI_OFFLINE`, `PI_SKIP_VERSION_CHECK`,
  `PI_TELEMETRY`, etc.) and the session variables injected only into
  LLM-callable shell tools (`PI_PROVIDER`, `PI_MODEL`, ...) — AR2 exposes no
  shell tool, so this second category is moot here.
- `docs/security.md` — "Pi does not include a built-in sandbox... [it] runs
  with the permissions of the pi process," corroborating the accepted AR2D
  conclusion (5F3B §22.1) that the broker is not an OS sandbox.
- `dist/core/resolve-config-value.js` — the actual `apiKey`/header
  value-resolution implementation (see §7 for citations).
- `dist/core/model-runtime.js` — where resolved auth is consumed, per request
  (see §7).
- `dist/core/provider-composer.js` — where a custom model definition is
  merged into Pi's internal model registry, including the `maxTokens` default
  (see §12).

No `pi --help`, no `pi --version`, and no Pi process of any kind was launched
to produce this document; AR1/AR2's own launch modules
(`experiments/pi_external_runtime_ar2/ar2/launch.py:120-161`) already recorded
the exact accepted argv shape and CLI flags, and that evidence is reused
rather than re-derived.

## 5. Pi custom-provider/config schema facts

From `docs/models.md` §"Provider Configuration" and §"Model Configuration",
and `docs/custom-provider.md` §"Config Reference" (the `registerProvider`
form is schema-identical to `models.json`, per that doc's own statement that
both share "the same config value syntax"):

| Concept | `models.json` field | Notes |
|---|---|---|
| Base URL | `providers.<id>.baseUrl` | Required when defining models. Never recorded per AR2's `base_url_recorded: false` convention |
| Provider id | the `providers` object key | Free-form string chosen by the config author, not by Pi |
| Model id | `providers.<id>.models[].id` | Passed verbatim to the wire request as `model` |
| API type / compatibility | `providers.<id>.api` (or per-model `models[].api`) | `"openai-completions"` for OpenAI Chat Completions and compatibles — the type AR2 already uses and the type an internal LiteLLM/B300 proxy speaks |
| API key / authorization | `providers.<id>.apiKey` | Optional; three resolution shapes (§6). `authHeader: true` forces `Authorization: Bearer <key>` for a provider whose `api` type would not otherwise send it — not needed for `openai-completions`, which already sends it |

Both candidates need their own `models[].id` entries (`"qwen3-coder-next"`,
`"minimax-m2.7"`) under **the same** provider id, `api: "openai-completions"`,
and `baseUrl` pointed at the B300 LiteLLM proxy — structurally identical to
AR2's generated file
(`experiments/pi_external_runtime_ar2/ar2/pi_config.py:119-153`), differing
only in provider id, model ids, `baseUrl`, and the `apiKey` reference's target
variable.

## 6. Supported credential mechanisms (local evidence, all five checked)

The task brief's five candidate mechanisms, checked one at a time against
local source:

1. **Environment-variable reference in `models.json`.** **Supported.**
   `docs/models.md:156-161`: `"apiKey": "$ENV_VAR"` or `"${ENV_VAR}"`. This is
   exactly the mechanism AR2 already uses for its non-secret placeholder
   (`experiments/pi_external_runtime_ar2/ar2/pi_config.py:127`,
   `experiments/pi_external_runtime_ar2/ar2/environment.py:93-94`).
2. **Provider-specific API-key environment lookup.** **Supported, but wrong
   for this route.** `docs/providers.md:69-106` lists a fixed table of
   built-in provider ids and their own env vars — including
   `MINIMAX_API_KEY` for `minimax` and `QWEN_TOKEN_PLAN_API_KEY` for
   `qwen-token-plan`. These point at the **vendor's real hosted API**, not at
   B300. Registering under those provider ids, or naming those variables,
   would either silently route a request to the wrong backend or do nothing
   useful for a custom `baseUrl`. This is precisely why AR2's forbidden-name
   list already blocks `MINIMAX`/`QWEN`/`OPENAI` fragments
   (`experiments/pi_external_runtime_ar2/ar2/environment.py:73,75,59`) — not
   only to keep a real credential out of the child process, but to prevent
   the built-in catalog from ever being mistaken for the B300 route. I2 must
   preserve this exclusion in its own, new environment builder (§9).
3. **Generic OpenAI-compatible environment lookup.** **Not a separate
   mechanism.** There is no vendor-neutral `OPENAI_COMPATIBLE_API_KEY`-style
   fallback for a custom provider id; mechanism 1 (`$ENV` interpolation
   inside `models.json`) is the generic path, and it is the one this design
   selects.
4. **Direct literal `apiKey` in `models.json`.** **Supported, but rejected
   for this route.** `docs/models.md:167-170`: a bare string is used as a
   literal. This would place the real B300 credential's *value*, not just its
   name, into a JSON file on disk — the file `models.json` reloads "each time
   you open `/model`" (`docs/models.md:92`), so it must exist as a real file
   for the whole run, unlike the shell-command form. §15 of this document
   rejects this shape explicitly and states the fail-closed handling if it
   were ever the *only* option (it is not — see mechanism 1).
5. **Runtime-only/in-memory provider registration.** **Supported, via
   `pi.registerProvider()`** (`docs/custom-provider.md:35-88`), including a
   full custom-provider form with an async `auth.apiKey.resolve()` callback
   that can read `process.env` inside the extension's own TypeScript code at
   call time, never writing a `$ENV`-style reference to any file at all. This
   is real and available, but §7 explains why it is **not** the chosen
   mechanism for I2.

Two further mechanisms the task brief did not name, found while reading the
same source, and both explicitly rejected here:

6. **CLI credential argument.** `docs/providers.md:314` documents a CLI
   `--api-key` flag as resolution-order rank 1 (highest priority, ahead of
   `auth.json` and environment variables). This is exactly the "no secret in
   argv" case the task brief pre-empted: a process command line is externally
   observable (e.g. via `wmic`/Process Explorer/`/proc` on other platforms),
   so this flag is **never used** by I2. AR2's `build_pi_argv`
   (`experiments/pi_external_runtime_ar2/ar2/launch.py:120-161`) already
   contains no such flag, and I2 must not add one.
7. **`auth.json` / `/login`.** `docs/providers.md:60-155` — interactive OAuth
   or a stored API key under `~/.pi/agent/auth.json`, created with `0600`
   permissions. This requires either an interactive login flow or writing a
   real credential into a **persistent** file, and both AR1 and AR2 already
   redirect `PI_CODING_AGENT_DIR` specifically so this real, persistent file
   is never read or written by the experiment
   (`experiments/pi_external_runtime_ar2/ar2/pi_config.py:1-6`). I2 inherits
   this exclusion unchanged (§13, "NO GLOBAL PI CONFIG").

## 7. Chosen credential mechanism

**Mechanism 1 — `models.json` `apiKey: "$<ENV_NAME>"` environment
interpolation, in a new, I2-owned, disposable `models.json`, structurally
identical to AR2's already-accepted generator
(`experiments/pi_external_runtime_ar2/ar2/pi_config.py:84-153`) but not
modifying that frozen file.**

Why this, and not `pi.registerProvider()` (mechanism 5), even though both are
supported:

- **It is the already-accepted shape.** AR2 already generates exactly this
  structure for its own (non-secret) placeholder credential. I2 needs one new
  provider id, two new model ids, a real `baseUrl`, and one new environment
  variable name — not a new generation mechanism.
- **Smaller surface.** A `pi.registerProvider()`-based extension is
  TypeScript source that must itself be written, reviewed, and — if it
  embeds anything resolved from the credential — scrubbed. A declarative
  `models.json` with a `$ENV` reference needs no extension code at all for
  the credential path; only AR2's already-accepted broker/tool extension
  (`experiments/pi_external_runtime_ar2/extension/`) continues to exist, and
  it carries no auth code.
- **Same candidate-symmetry requirement.** 5F3B's design demands "same
  config builder" for candidates A and B (§"SAME POLICY FOR BOTH
  CANDIDATES" in the task brief, and 5F3B §13). One declarative generator
  function, called twice with a different `model_id`, trivially satisfies
  this; two mechanisms would not.

**Resolution timing (task brief Q3), established from source, not
assumed:**

`docs/models.md:172` states only that *shell commands* are "resolved at
request time," with no built-in caching. Reading the actual implementation
in `dist/core/resolve-config-value.js` shows the same is true of `$ENV`
interpolation, and more precisely so:

- `resolveEnvConfigValue(name, env)` (`resolve-config-value.js:71-73`) reads
  `env?.[name] || process.env[name]` — a **live** read of `process.env` at
  call time, with **no cache**. This is asymmetric with shell commands:
  `executeCommand` (`resolve-config-value.js:181-188`) explicitly caches into
  a module-level `commandResultCache` keyed by the command string ("Cache for
  shell command results (persists for process lifetime)",
  `resolve-config-value.js:7`); the template/`$ENV` path
  (`resolveTemplate`, lines 83-96) has no such cache at all.
- The call site that matters is `ModelRuntime.prepareRequest(model, options)`
  (`dist/core/model-runtime.js:422-451`), which calls `this.getAuth(model,
  ...)` (line 426) → `this.models.getAuth(providerOrModel, overrides)` (line
  342) on **every** `stream()`/`complete()` call
  (`model-runtime.js:452-459`), and `resolveConfigValue` is what ultimately
  supplies `resolution.auth.apiKey`.
- `dist/cli/credential-print.js:9` independently documents the same path:
  "`ModelRuntime.getAuth()`... refreshes and persists OAuth credentials...
  through the normal request-auth path" — i.e. `getAuth()` **is** the
  request-time auth path, not a one-time provider-construction step.

**Conclusion: neither "config parse time" nor a one-time "provider creation
time" cache. The `$ENV` value is read from the Pi child process's live
`process.env` every time a request is prepared, via `prepareRequest` →
`getAuth` → `resolveConfigValue`.** This has one practical consequence for
I2: the credential must be present in the Pi child's environment for the
**entire** run (it cannot be injected once and then removed mid-run), and
because it is never cached to a file or a long-lived in-process cache the
way a shell-command result is, there is no risk of AIDO tearing down the
generated `models.json` mid-run and Pi silently continuing on a stale cached
value — but conversely, the value **is** re-read from the OS environment
block on every single request, so its presence in that OS-level environment
block persists for the process's whole lifetime regardless of what AIDO does
to files on disk (see §11).

### 7.1 Semantic prompt count vs. provider-request count (5F3B-I2A-FU1 correction)

An earlier draft of this document said or implied that one authorized
semantic prompt corresponds to exactly one B300 chat-completion HTTP
request, and that the generated `settings.json`'s `maxRetries: 0`
(§10) is what keeps it that way. **Both are wrong, and are corrected here.**

A Pi coding-agent turn is a **loop**: Pi may call the provider, receive a
tool call, run the tool (here, `aido_read`/`aido_edit` through the broker),
call the provider again with the tool result appended, and repeat — all
within the **one** semantic task prompt AIDO sent — until the agent loop
itself decides the turn is done and emits `agent_settled`. Each of those
provider calls is a separate HTTP request to B300, and each one independently
triggers `prepareRequest` → `getAuth` → `resolveConfigValue`
(§7), so the credential is (re-)read from `process.env` on **every** one of
them, not once per semantic prompt.

Three concepts, frozen here as **distinct and non-interchangeable**:

```text
semantic_prompts_sent
    AIDO/controller-owned. The number of task prompts I2's own qualification
    controller sends. Primary qualification = exactly 1 per task (5F3B §9),
    unchanged by this correction.

provider_inference_requests
    Pi-owned. The number of individual chat-completion HTTP requests Pi's own
    agent loop issues to B300 while servicing that ONE semantic prompt, before
    agent_settled. May be 1, or may be many (one per tool-call round-trip).
    NOT counted, NOT capped, and NOT treated as a qualification metric by this
    design — Pi's agent-loop request count is Pi-owned behavior, exactly as
    5F3B already treats agent_settled as Pi's own runtime-turn signal, never
    AIDO's to dictate.

transport_retries_per_provider_request
    Pi-owned. `maxRetries: 0` (§10) means Pi's own HTTP transport layer does
    NOT automatically retry an individual failed provider request. It says
    nothing about, and does not bound, how many separate
    provider_inference_requests the agent loop issues across the turn.
```

**I2A does not introduce a numeric cap on `provider_inference_requests`.**
Doing so would require AIDO to police Pi's internal agent-loop behavior,
which is out of scope here and unsupported by any local mechanism this
design found. The existing 5F3B accounting (`semantic_prompts_sent`,
`agent_settled`) is unaffected — it was always about AIDO's own task-prompt
issuance, never about Pi's internal request count, and no wording in this
document may again conflate the two.

**Quantity existing is not the same as AIDO being able to measure it
(5F3B-I2A-FU2 correction).** `provider_inference_requests` is a real
conceptual quantity — the count genuinely may be greater than one — but this
architecture establishes **no observer** that maps any AIDO-visible event
(a broker/RPC message, a tool call, `agent_settled`) one-to-one onto each
individual provider HTTP request. §19 therefore records
`provider_inference_request_count_observation_available = false` rather than
a numeric field an implementation might be tempted to populate from, say,
counted tool-call round-trips — that count is a *lower bound on tool-call
turns*, not a proven count of provider requests, and this document does not
claim otherwise. No HTTP observer, request-count instrumentation, or Pi-side
counting hook is added by this design to make that count real; if one is
ever added, it is a separately authorized capability, not an I2 default.

**Consequence for §8's credential lifetime:** the credential must remain
resolvable in the Pi child's environment for as long as the agent loop keeps
making provider requests within that one semantic task turn — i.e. for the
turn's whole duration, not for "one request." §8 and §11 are written with
this in mind.

## 8. Credential authority and lifetime

```text
operator process environment (AIDO_LITELLM_BASE_URL / AIDO_LITELLM_API_KEY)
    │  (the SAME B300 surface AIDO's reviewer/planner/benchmark already use —
    │   5F3B §15.2's own table. No new operator-facing variable name.)
    ▼
AIDO qualification controller (I2, new code)
    │  reads AIDO_LITELLM_BASE_URL / AIDO_LITELLM_API_KEY from AIDO's OWN
    │  process environment ONLY after every non-credential offline gate has
    │  passed (§16), mirroring the accepted 5F2E ordering: "verify first,
    │  read credentials second" (src/ai_dev_orchestrator/review/reviewer.py:39-55)
    ▼
qualification-owned Pi launch/config seam (I2, new modules, NOT ar2.environment/ar2.pi_config)
    │  writes the value ONLY as: (a) one entry in the disposable Pi child's
    │  OS environment block, under a NEW, non-AIDO_-prefixed name; and
    │  (b) a "$<that name>" TEXT REFERENCE (never the value) inside the
    │  disposable, per-run models.json
    ▼
Pi provider request(s) (Node child process, dist/core/resolve-config-value.js)
    │  reads process.env[<name>] itself, freshly, on EACH provider request —
    │  and per §7.1 one semantic task prompt may produce ONE OR MANY such
    │  provider requests before agent_settled, all within the SAME child
    │  process and the SAME launch environment
    ▼
one or more B300 chat-completion HTTP requests, all within the ONE
authorized semantic prompt's turn (count owned by Pi's agent loop, not AIDO)
```

**AIDO owns**, exactly as the task brief's conceptual shape requires:

- **Whether credential access is authorized at all** — gated behind every
  offline gate in §16 passing first, and behind the same project-level
  `controlled_review`-style opt-in discipline 5F2E established (a qualifying
  `pi_implementer_qualification` opt-in is a §24 implementation detail, not
  designed further here since I2A is design-only).
- **When the credential is read** — never before the offline gates pass;
  read once per run, immediately before building the Pi child's launch
  environment.
- **Minimum lifetime, corrected (5F3B-I2A-FU1)** — see §11 for the full,
  corrected lifecycle. In outline: read once → placed into **one run-scoped
  secret/safety context** (which also becomes the object §17's
  `ArtifactSafetyContext` values are drawn from) → placed into the `env=`
  mapping passed to the Pi child's launch call → held only as long as the
  run needs it, including for as long as Pi's agent loop keeps making
  provider requests within the one authorized semantic prompt's turn (§7.1)
  → released, where practical, only **after** every retainable artifact for
  that run has been scrubbed and safely emitted. An earlier draft of this
  bullet claimed the value was "never written to a... record" and existed
  in only one place, which directly contradicted requiring that same value
  for artifact scrubbing later. That contradiction is removed: the value
  necessarily has at least two live references during a run (the `env=`
  mapping, and the run-scoped secret/safety context), both minimized,
  neither logged or printed, and neither placed in a retained artifact.
- **Which child receives it** — exactly one Pi child process, for exactly
  one qualification task run, in a launch environment I2 builds from
  scratch (§9) — never the operator's ambient environment, never a shared
  environment reused across tasks or candidates.
- **Generated-config cleanup** — deletion of the disposable `models.json`,
  verified by `stat`, exactly like AR2's `scrub_generated_pi_config`
  (`experiments/pi_external_runtime_ar2/ar2/pi_config.py:221-238`); see §11
  and §18 for the phase-aware classification of a cleanup failure.
- **Artifact-scrub context** — the same run-scoped secret/safety context
  (above) supplies `ArtifactSafetyContext.api_key` (and every other §17
  field), and it is checked against **every** retainable artifact for that
  run before emission — not only the final qualification record, but also
  protocol/RPC summaries, any stdout/stderr-derived text, provider/exception
  error text, and lineage/refusal evidence (§11 states this as a binding
  rule: no such text is persisted to disk before this scrub runs).
- **Evidence claims** — every provenance field this design adds is
  conditional/negative-scoped per the disciplines 5F2D/5F2E/RS1 already
  established in `CLAUDE.md` (never an unscoped `network_called: false`,
  never a claim Python "erased" the value from memory, and — per this
  correction — never a claim that "no second reference exists").

**Pi owns only**: using its supported mechanism (§6/§7) to make whichever
provider request(s) its own agent loop decides to make within the one
authorized semantic prompt's turn (§7.1 — the count is Pi's, not AIDO's),
and its own commonplace Node runtime behavior on top of the credential.

## 9. Child environment policy

I2 needs **its own new environment builder**, structurally modeled on
`experiments/pi_external_runtime_ar2/ar2/environment.py` but **not editing
it** (5F3B §15.2 already says this explicitly, and frozen AR1/AR2/O1/I1 are
out of scope for any write here). The frozen AR2 `FORBIDDEN_NAME_FRAGMENTS`
tuple (`environment.py:48-86`) exists specifically to reject any name
containing `MINIMAX`, `QWEN`, `OPENAI`, `PROXY`, `AIDO_`, `API_KEY`,
`APIKEY`, `SECRET`, `TOKEN`, `CREDENTIAL`, and more — and this is exactly
the shape a B300/Pi credential name must be checked against, because the
candidates ARE named `qwen3-coder-next` / `minimax-m2.7`, and a careless
child-env variable name (or an accidentally-forwarded ambient one) could
otherwise look like — or actually be — a real vendor credential.

**I2 answer: yes, a qualification-owned child environment builder is
required**, with an **explicit positive allowlist**, never an inherited
ambient environment:

| Category | Names | Source |
|---|---|---|
| Windows process baseline | `SystemRoot`, `SystemDrive`, `windir`, `ComSpec`, `PATHEXT`, `NUMBER_OF_PROCESSORS`, `PROCESSOR_ARCHITECTURE`, `TEMP`, `TMP` | Identical to AR2's `BASE_WINDOWS_NAMES` (`environment.py:28-38`) — reused as a **value**, not by importing/modifying AR2's module as a dependency of production code |
| PATH | narrowed to Node dir + Git dir (optional) + `System32` + `SystemRoot` | Identical construction to AR2's `_narrowed_path` (`environment.py:113-131`) |
| Pi-owned | `PI_CODING_AGENT_DIR`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0` | `docs/environment-variables.md:75-93` — confirms these are the exact variables Pi's own process reads |
| Profile names | none included by default (`USERPROFILE`/`HOME`/`APPDATA` withheld) | Same AR0/AR2 rationale: a second independent barrier against `~/.pi/agent` resolution even if `PI_CODING_AGENT_DIR` redirection were incomplete |
| **Credential carrier (new, exactly one name)** | e.g. `PI_QUALIFICATION_B300_ROUTE_KEY` | New for I2. Deliberately **not** `AIDO_`-prefixed (keeps a clean boundary from the reviewer/planner credential surface and avoids colliding with `AIDO_LITELLM_*`/`AIDO_VLLM_*`'s own read-authority discipline in `src/ai_dev_orchestrator/review/reviewer.py:497-529`), and deliberately chosen to contain **none** of the forbidden fragments above (no `API_KEY`/`APIKEY`/`SECRET`/`TOKEN`/`CREDENTIAL`/`AIDO_`/`QWEN`/`MINIMAX`/`OPENAI`/`PROXY`) |

I2's own forbidden-fragment audit must run the **same style of check** AR2's
`audit_withheld_names` performs (`environment.py:201-221`) — by NAME only,
never by value — with the one credential-carrier name excepted from the
violation check by exact identity, exactly as AR2 excepts
`ROUTE_PLACEHOLDER_ENV_NAME` (`environment.py:180-183`).

**Corrected (5F3B-I2A-FU2): this B300 qualification route requires the
established `AIDO_LITELLM_API_KEY` credential — I2 supports exactly one
mode, not two.** An earlier draft of this bullet said the value under the
credential-carrier name "is never a fixed placeholder... unless the
operator's B300 credential is genuinely unnecessary," implying I2 might
silently fall back to a keyless mode (à la AR2's `no_api_key`) if the
credential were absent. That implied a second, undesigned branch, and it
directly conflicts with §16.A, which already, correctly, treats
`AIDO_LITELLM_API_KEY` unset/blank as a pre-prompt `INFRASTRUCTURE_REFUSAL`
(`semantic_prompts_sent = 0`) rather than something I2 quietly works around.
The wording is withdrawn: **I2 always reads a real `AIDO_LITELLM_API_KEY`
value and places it under the credential-carrier name; a missing or blank
value is a pre-prompt infrastructure refusal, never a trigger for a
placeholder credential.** If a future B300 deployment genuinely becomes
keyless, that is a separately reviewed route/configuration decision — not an
implicit branch inside this design — and it is not designed here.

## 10. Generated Pi-config policy

A new, I2-owned generator (not `ar2.pi_config`, structurally identical to it)
writes, into a fresh disposable `PI_CODING_AGENT_DIR` created only after the
offline gates pass:

- `settings.json` — identical in shape to AR2's
  (`experiments/pi_external_runtime_ar2/ar2/pi_config.py:95-117`): empty
  `packages`/`extensions`/`skills`/`prompts`/`themes`, `defaultProjectTrust:
  "never"`, telemetry/analytics disabled, provider transport retry disabled
  (`maxRetries: 0`). **Corrected meaning (5F3B-I2A-FU1):** this disables
  Pi's own HTTP-transport-level automatic retry of one **individual**
  failed provider request — it is not, and an earlier draft of this
  document wrongly implied it was, a bound on how many separate
  `provider_inference_requests` (§7.1) Pi's agent loop may issue while
  servicing the one authorized semantic prompt. `agent_settled`-based turn
  accounting (5F3B §11) remains the only thing that bounds AIDO's own
  semantic-prompt count, unchanged by this setting.
- `models.json` — **one** provider entry (new provider id, e.g.
  `b300_pi_qualification`), `api: "openai-completions"`, `baseUrl` set to
  the value read from `AIDO_LITELLM_BASE_URL` (never recorded — same
  `base_url_recorded: false` discipline as AR2/`route_check.py`), `apiKey:
  "$PI_QUALIFICATION_B300_ROUTE_KEY"` (the reference, never the value), and
  **exactly one** `models[]` entry per candidate run — `{"id":
  "qwen3-coder-next", "reasoning": true}` for Candidate A, `{"id":
  "minimax-m2.7", "reasoning": true}` for Candidate B. `maxTokens` is
  **omitted**, enforced the same way AR2 enforces it — a hard check on the
  serialized JSON text before it is written
  (`experiments/pi_external_runtime_ar2/ar2/pi_config.py:143-147`).
- The generator also enforces, as AR2 already does, that `apiKey` never uses
  `!shell` resolution (`pi_config.py:148-151`) — belt-and-braces, since the
  generator itself only ever emits the `$ENV` form.

**The generated `models.json` DOES contain the real B300 endpoint URL in
plaintext** (the `baseUrl` field) for the run's duration, exactly as AR2's
already does for its own (different, keyless) endpoint. It does **not**
contain the credential's value, under any resolution form, at any time.

## 11. Secret lifetime (5F3B-I2A-FU1: corrected lifecycle)

An earlier draft of this section claimed the credential's Python-level
reference was released once the child's `env=` mapping was built, and
"no code path retains a second reference" — while §17 simultaneously
required that same value to survive, in memory, long enough to populate
`ArtifactSafetyContext.api_key` for scrubbing every retained artifact. Those
two statements cannot both be true, and the earlier draft never resolved
the conflict. This section replaces both with one frozen, internally
consistent lifecycle:

```text
read credential only after every non-secret offline gate passes (§16 Path A)
    ↓
construct ONE run-scoped secret/safety context for this task run
    (this IS the object whose fields become ArtifactSafetyContext, §17)
    ↓
build the Pi child's launch environment from that context (§9)
    ↓
launch Pi; the credential is re-read from process.env on EACH of Pi's own
    provider_inference_requests for the whole semantic-prompt turn (§7.1)
    ↓
Pi child completes, or teardown is attempted (timeout/reap-grace, §18)
    ↓
generated Pi config (models.json/settings.json/PI_CODING_AGENT_DIR) cleanup
    is attempted and its result is VERIFIED by stat
    ↓
EVERY retainable artifact for this run is scrubbed using the SAME run-scoped
secret/safety context, including: the qualification record itself,
protocol/RPC summaries, any stdout/stderr-derived text, provider/exception/
error text, lineage/refusal evidence, and any other diagnostic artifact —
NONE of that text is written to disk in raw/unscrubbed form first (see
below)
    ↓
safe, scrubbed evidence is emitted
    ↓
ONLY THEN, where practical, does AIDO drop its remaining references to the
run-scoped secret/safety context and the child's env= mapping
```

| Question | Answer |
|---|---|
| When does the credential first enter memory? | When I2's controller reads `AIDO_LITELLM_API_KEY` from AIDO's own `os.environ`, immediately before constructing the run-scoped secret/safety context — after every non-secret offline gate (§16 Path A) has passed |
| Does it ever enter a file? | **No.** Only its variable *name* (`PI_QUALIFICATION_B300_ROUTE_KEY`) enters the generated `models.json`, as the text `"$PI_QUALIFICATION_B300_ROUTE_KEY"`. The value itself is never written to any file I2 controls |
| Does it enter the Pi child environment? | **Yes** — exactly one name, in the explicit positive-allowlist environment built for that one child process (§9), for the process's entire lifetime. Per §7/§7.1, Pi re-reads `process.env` freshly on **each** of its own `provider_inference_requests` — possibly more than one — for as long as that one semantic prompt's turn lasts, so the value's presence is not transient within the child |
| Does it enter argv? | **No.** §6 mechanism 6 (`--api-key`) is explicitly not used. AR2's `build_pi_argv` shape (§4) carries no credential-shaped argument, and I2 must not add one |
| When is generated config deleted/scrubbed? | Immediately after the Pi child process has exited or teardown was attempted (§18), before any evidence record is written. The disposable `PI_CODING_AGENT_DIR` (`models.json` + `settings.json`) is deleted and the deletion is **verified by `stat`**, exactly as `scrub_generated_pi_config` does (`pi_config.py:221-238`) |
| How many live references to the value exist in AIDO's own process? | **At least two, by design, and this document does not claim otherwise.** (1) The `env=` mapping handed to the Pi child's launch call, and (2) the run-scoped secret/safety context used to scrub every retainable artifact (§17). Both are minimized — neither is logged, printed, included in a retained artifact, or copied into a third location — but an earlier draft's claim that "no second reference exists" is **withdrawn** as false: the scrub step structurally requires a second reference to exist |
| When are in-memory references released, where practical? | **Not** merely after the `env=` mapping is built (corrected). Only after: (a) the Pi child has exited or teardown was attempted, (b) generated-config cleanup was attempted and its result verified, and (c) every retainable artifact for the run has been scrubbed against the run-scoped context and safely emitted. Even then, "released where practical" means AIDO drops its own remaining Python references — it does not mean the underlying memory is guaranteed cleared (see below) |
| What may AIDO truthfully claim after cleanup? | "The generated `models.json` was deleted and its absence was verified by `stat`," and "AIDO dropped its own remaining Python references to the value after every retainable artifact was scrubbed and emitted." **Never** "the credential was erased from memory," "no second reference existed," "the credential cannot be recovered," or any claim of forensic erasure — Python provides no guaranteed zeroization of string/bytes objects, page files, swap, or OS-level buffer cache, and this document makes no such claim |

**No raw Pi output is persisted before the scrub runs.** Pi's stdout/stderr,
RPC transcript text, and any provider/exception error text may be held only
under the existing bounded in-memory capture discipline already accepted
for verification output (5F2D's captured-output bound is the model to
follow, not a mechanism this document changes). None of that raw text is
written to disk, logged, or otherwise persisted **before** the
run-scoped-context scrub (§17) runs against it; only the scrubbed, bounded
form may be emitted.

**Cleanup failure classification is phase-aware (5F3B-I2A-FU1 correction).**
An earlier draft of this section said unconditionally that a failed cleanup
"must be recorded as `INFRASTRUCTURE_CONTAMINATED`," without regard to
whether a semantic prompt had been sent yet. That is corrected — see §18 for
the full, phase-aware rule; in outline:

- If generated-config cleanup fails **before** any semantic prompt was sent
  for that task (e.g. a compatibility gate failed pre-prompt and teardown of
  the not-yet-used config also fails), the task is still a **pre-prompt**
  `INFRASTRUCTURE_REFUSAL` with `semantic_prompts_sent = 0` — the cleanup
  failure is recorded as part of that same pre-prompt infrastructure record,
  never inflated into a scored, contaminated attempt that never happened.
- If cleanup or teardown fails **after** the one semantic prompt was sent,
  the run is `INFRASTRUCTURE_CONTAMINATED` (5F3B §17.3) with
  `semantic_prompts_sent = 1` truthfully preserved, `scoring_eligible =
  false`, and the disposable directory is never promoted to retained
  evidence.

**The prompt count itself is never rewritten based on when a failure was
discovered.** `semantic_prompts_sent` reflects only whether AIDO's
controller actually sent the one task prompt, not how or when the run
subsequently failed.

## 12. Token-budget invariants (preserved, with one new honest caveat)

Unchanged from 5F3B §19: `aido_requested_max_output_tokens = null` for every
qualification run, on both candidates, for every task. The generated
`models.json` omits `maxTokens` entirely (§10), and AR2's own generator
already enforces this by construction — I2's new generator repeats the same
enforced check independently rather than importing AR2's private function.

**New local finding, stated honestly because CLAUDE.md requires it, and
scoped honestly (5F3B-I2A-FU2 correction) to the exact version it was
observed in:** `dist/core/provider-composer.js:73`, inspected against the
locally installed **`@earendil-works/pi-coding-agent@0.84.3`** (§4), shows
`maxTokens: definition.maxTokens ?? 16384` — when a custom model definition
omits `maxTokens`, Pi 0.84.3's own internal model registry **object** still
carries a default of `16384` for that field. This is a real, cited fact
about **that inspected version's source**, and it must not be hidden behind
generic language. **It is not, and an earlier draft of this section did not
sufficiently guard against being read as, a permanent cross-version runtime
fact.** 5F3B §14's accepted Pi-version policy (§13 below) allows a different
Pi version to proceed once its own capability/behavior gates pass, without
re-pinning to `0.84.3` — and `provider-composer.js`'s exact default is an
implementation detail of one version's source, not a capability the
zero-prompt compatibility gate (§15) checks. A future run against a
different, still-compatible Pi version must **not** assume `16384` still
holds merely because this document once observed it in `0.84.3`. §19's
provenance wording is corrected accordingly to record this as **source
provenance tied to the inspected version**, never as an unconditional
per-run fact.

However, three further local facts — established from the same 0.84.3
source and equally scoped to it — bound what that default actually means:

1. `dist/core/agent-session.js:1585` is the **only** other local reference to
   `model.maxTokens`, and it uses the registry value purely to detect whether
   an already-finished assistant message looks like a truncated
   ("recoverable-length") response — a **diagnostic/retry heuristic**, not a
   value that is copied onto an outgoing request.
2. The wire-level cap is populated by a **separate** field,
   `options?.maxTokens` (`pi-ai openai-completions.js:568-574`:
   `if (options?.maxTokens) { params.max_tokens = ... }` /
   `params.max_completion_tokens = ...`), and this repository found **no**
   local evidence that Pi's own CLI/agent loop copies `model.maxTokens` into
   that `options.maxTokens` for an ordinary agent turn. AR2's accepted argv
   shape (`launch.py:140-161`) has no `--max-tokens`-style flag, and I2 must
   not add one.
3. Therefore: **omitting `maxTokens` from the generated `models.json` does
   not prove, from local source alone, that no `max_tokens` field reaches the
   wire request** — it proves that AIDO did not request one, and that Pi
   0.84.3's own internal bookkeeping default (`16384`) is not shown to reach
   the wire from the code paths this design read against that version.

**Correction (5F3B-I2A-FU1): Q1/Q2 do NOT make the wire-level request body
observable.** An earlier draft of this section said the true wire-level
`max_tokens` value would be "observable from... Q1/Q2 itself" and that Q1/Q2
"must record [it] honestly from whatever the real transmitted request body
turns out to contain." That overstates what this architecture can see.
Nothing designed anywhere in this document — nor in the accepted AR1/AR2/O1
harness it builds on — places AIDO **between** Pi and B300 on the wire. Pi
is launched as an ordinary child process (§4, §9); its own outbound HTTPS
request to B300 is not intercepted, proxied, or logged by anything AIDO
controls. AIDO observes Pi only through the accepted broker/RPC channel
(tool calls, `agent_settled`, and the other §11.1-listed observable
surfaces from 5F3B) — none of which exposes the HTTP request body Pi's own
`openai-completions` provider code constructs internally
(`pi-ai openai-completions.js:552-575`). **Running Q1/Q2 does not change
this**; it is not a "future observation," it is architecture that this
design does not provide, and no new proxy, interceptor, or instrumentation
layer is introduced here to provide it (that would itself be new capability
this design does not authorize, per §22).

**Provenance wording, corrected (5F3B-I2A-FU2 rescopes the internal-default
fact to source provenance, not a per-run runtime fact):**

```text
# AIDO-owned token facts. Invariant regardless of Pi's internal default or
# observed version — these are what AIDO itself requested, never what Pi
# does internally.
aido_requested_max_output_tokens        = null
models_json_omits_max_tokens            = true

# Source-provenance fact, tied to the EXACT Pi version this design inspected.
# Never a claim about every compatible Pi version, and never re-asserted for
# a run whose observed_pi_version (§13) differs unless separately re-verified.
pi_source_observation:
    inspected_version                     = "0.84.3"
    internal_registry_default_max_tokens  = 16384   # provider-composer.js:73;
                                                       # bookkeeping/registry fact
                                                       # only, NOT shown by local
                                                       # source to reach the wire
                                                       # request (see above)

# Per-run fact. observed_pi_version is always recorded independently (§13).
# If a run's observed_pi_version differs from "0.84.3" and this internal-
# default fact has not been separately re-established for that version, the
# per-run record uses this truthful state rather than repeating 16384 or
# guessing:
internal_registry_default_max_tokens_for_this_run = 16384 if observed_pi_version == "0.84.3"
                                                     else "NOT_REESTABLISHED_FOR_OBSERVED_VERSION"

# No request-body observer exists anywhere in this architecture (unchanged
# from 5F3B-I2A-FU1).
wire_level_max_tokens_observation_available = false
```

**Exact version equality is never an authorization gate, and no semver
range is introduced by this correction** — §13's accepted policy (Pi version
is provenance, not authorization; a different version may proceed if its own
capability/behavior gates pass) is unchanged. The
`NOT_REESTABLISHED_FOR_OBSERVED_VERSION` state is a **provenance/reporting**
value only: it does not fail a gate, does not block a run, and does not
require re-running I2A's own source inspection before a differently-versioned
Pi may be used — it only prevents a stale, version-specific implementation
detail from being silently repeated as though it were still true.

`wire_level_max_tokens_observation_available = false` remains a permanent
architectural fact of this design, not a temporary "not yet run" state.
**If a future, separately authorized phase adds a request-body observer
(a logging proxy, an interceptor, or equivalent instrumentation), it would
create new evidence and could flip this field — that possibility is noted
and not designed further here, and it must not be assumed, relied upon, or
treated as already existing.**

## 13. Pi capability/version policy

Unchanged from 5F3B §14: `observed_pi_version` is recorded truthfully
(`0.84.3` as of this design), never pinned, never compared via a semver
range. The zero-prompt compatibility gate (H1/H2, `get_commands`,
`get_state`, protocol/extension-error absence, the non-inference `/models`
route check) is re-proven per run, exactly as O1 established.

**No global Pi config is ever read.** I2's disposable `PI_CODING_AGENT_DIR`
is created fresh per run, exactly as AR1/AR2/O1 already do
(`pi_config.py:1-6`: "AR2 never reads, copies, or inspects the user's real Pi
configuration"), and I2 copies that isolation discipline rather than the
harness code itself.

## 14. Offline preflight gates (Category A — this phase's kind of check)

Entirely file/string-level; no process launch, no network, no credential
read:

1. Pi package installed and its `package.json` `version` field observed by a
   plain file read (no process launch — this is how §4 obtained `0.84.3`).
2. The I2 config generator's own output is schema-checked in-process:
   required keys present, `apiKey` matches exactly the `"$<NAME>"` shape,
   `maxTokens` is absent from the serialized text, no `!` shell-command form
   is ever produced.
3. The I2 environment builder's output passes its own forbidden-fragment
   audit (§9), with the one credential-carrier name excepted by exact
   identity, mirroring AR2's `audit_withheld_names` shape.
4. Candidate A and Candidate B route descriptors are built by **calling the
   same generator function twice** with only `model_id` varying — asserted
   by a unit test comparing the two generated documents field-by-field
   except `models[0].id`.
5. The planned CLI argv is compared, by exact tuple equality, against the
   already-accepted AR2 shape (`launch.py:140-161`) with only `--provider`
   and `--model` values substituted — proving no new flag, and specifically
   no `--api-key`, is ever introduced.
6. `ArtifactSafetyContext` population is exercised with synthetic
   stand-in values (never a real credential) to prove the scrub backstop
   actually refuses a record containing any of `endpoint_host`, `api_key`,
   `bearer_token`, `broker_token`, `pipe_name`, `capability_id`, or
   `workspace_absolute_path`.
7. A unit test proves the generator has **no code path** capable of
   embedding a literal (non-`$ENV`) value into `apiKey`, e.g. by asserting
   the function's signature accepts only a variable *name*, never a value,
   for the credential field.

## 15. Future zero-prompt live gates (Category B — NOT run in this phase)

Authorized only for a future I2 implementation phase, and only after that
phase's own explicit go/no-go — **not performed here**:

1. Pi installed/version observed via Node-direct launch (`node cli.js
   --version`), exactly as `resolve_runtime_identity`
   (`launch.py:69-117`) already does — this launches a real (non-inference)
   Pi process, which is why it is Category B rather than Category A.
2. Node-direct RPC launch shape (`--mode rpc`) reaching a live broker.
3. Required CLI flags accepted (no "unknown flag" startup error).
4. LF-framed JSONL request/response correlation (RPC transport sanity).
5. H1 — exact extension identity (`sourceInfo.source == "cli"`, per the
   AR1-FU1/AR2 precedent).
6. **[SUPERSEDED BY `docs/PHASE_5F3B_I2A_DESIGN_FU3_CATEGORY_B_OBSERVABILITY_CORRECTION.md` §5. The original text is preserved verbatim below and must NOT be implemented.]**
   ~~`get_commands` — exactly `aido_read`/`aido_edit` registered, nothing
   else.~~
   *Why superseded:* this claims the contents of the **active tool registry**,
   which frozen AR0-FU1 §4.1j records (source-verified) that Pi exposes no RPC
   command to enumerate — and which AR2D §2.2's mandated correction already
   ruled must never be claimed. It is also unsatisfiable: `get_commands`
   enumerates `pi.registerCommand` **slash commands**, while
   `aido_read`/`aido_edit` are `pi.registerTool` **tools**, so those two names
   can never appear in a `get_commands` response. The corrected gate
   partitions every top-level-`"extension"`-sourced entry by its
   `sourceInfo.source` — **not** by the top-level `source` field, which both
   AIDO's sentinel and Pi's own inline commands (e.g. `llama`) share
   identically: exactly one `sourceInfo.source == "cli"` entry, H1-valid;
   any `sourceInfo.source == "inline"` entry tolerated by mechanically
   checked provenance; anything else refused closed — with the active tool
   registry recorded as an explicit non-observation. See FU3 §5.2/§5.3.
7. `get_state` — H2, exact candidate provider/model identity echoed back
   matches the configured route descriptor exactly.
8. Absence of any protocol or extension error.
9. B300 route serves the exact candidate model id, via the **unmodified**
   `ar2.route_check.check_route_serves_model` non-inference `/models` GET
   (`experiments/pi_external_runtime_ar2/ar2/route_check.py:89-160`) — reused
   exactly as 5F3B §15.2 specifies, never copied or forked.
10. Broker reaches `READY`.

**Whether credential validation itself can be established without
inference — answered honestly: NOT from local source alone.**
`route_check.py`'s own docstring (`route_check.py:1-42`) is explicit that the
`/models` listing "does **not** authorize anything" and proves only that the
configured model id is served — it says nothing about whether the endpoint
enforces the `Authorization` header at all. Whether a malformed or absent
B300 credential would make `/models` itself fail (proving something about
auth) or succeed regardless (proving nothing) is **unknown from this
repository's local evidence** and is explicitly listed as an open question
in §25 rather than assumed in either direction. A future I2 implementation
*could* add a differential check — call `check_route_serves_model` once with
the real credential and once with a deliberately empty/invalid one, and
compare results — but that is a **design option for a later phase**, not
something this document authorizes or performs, and not something CLAUDE.md
permits this document to newly design in detail (it would be new gate logic,
not the accepted `route_check` reused unmodified).

## 16. Authentication/route failure attribution (5F3B-I2A-FU1: split into two paths)

An earlier draft of this section named "provider authentication rejected" as
a single, unconditional `INFRASTRUCTURE_REFUSAL` case. That silently assumed
an auth/route failure is always discoverable *before* the semantic prompt is
sent. §15 already states, honestly, that this is **not established** — B300
credential validation might only surface as an error on the actual first
chat-completion request, i.e. *after* the one authorized semantic prompt was
already sent. Reporting that case as `INFRASTRUCTURE_REFUSAL` (which the
accepted I1 schema reserves for `semantic_prompts_sent = 0`) would be a false
record. This section is corrected into two explicit, non-overlapping paths.

### 16.A — Failure established BEFORE the semantic prompt (pre-prompt)

Every one of the following is a pre-prompt gate outcome. Each yields
`INFRASTRUCTURE_REFUSAL` with `semantic_prompts_sent = 0`, exactly as 5F3B
§11.5/§17.2 case 1 already defines — **never** a candidate-model failure, and
**never** an automatic fallback to the other candidate or another route:

| Condition | Named gate | Classification |
|---|---|---|
| Credential unavailable | `AIDO_LITELLM_API_KEY` (or `AIDO_LITELLM_BASE_URL`) unset/blank in AIDO's own environment | `INFRASTRUCTURE_REFUSAL`, `semantic_prompts_sent = 0` |
| Credential malformed / config rejected | The generated `models.json` fails its own schema self-check (§14.2), or Pi reports the provider as unconfigured/unavailable in `/model`-equivalent state before any tool call | `INFRASTRUCTURE_REFUSAL`, `semantic_prompts_sent = 0` |
| Route unreachable at the zero-prompt gate | `route_check.check_route_serves_model` reports `reachable=False` | `INFRASTRUCTURE_REFUSAL`, `semantic_prompts_sent = 0` |
| Candidate model not served | `route_check` reports `configured_model_served=False` | `INFRASTRUCTURE_REFUSAL`, `semantic_prompts_sent = 0` |
| Pi provider config incompatible | The zero-prompt compatibility gate (§15) fails on any of H1/`get_commands`/H2/`get_state`/protocol-error checks | `INFRASTRUCTURE_REFUSAL`, `semantic_prompts_sent = 0` |
| Provider authentication rejected, observed pre-prompt | Pi/B300 surfaces an explicit auth error via `get_state`/provider-availability signals, observed **before** `agent_start` | `INFRASTRUCTURE_REFUSAL`, `semantic_prompts_sent = 0` |
| H1/H2 mismatch | Extension identity or provider/model identity does not match the configured route descriptor | `INFRASTRUCTURE_REFUSAL`, `semantic_prompts_sent = 0` |
| Broker not READY | The B-rpc broker's own lifecycle never reaches `READY` | `INFRASTRUCTURE_REFUSAL`, `semantic_prompts_sent = 0` |
| Generated-config cleanup fails before any prompt was sent | Teardown of a not-yet-used disposable config fails its `stat` verification while `semantic_prompts_sent` is still 0 | `INFRASTRUCTURE_REFUSAL`, `semantic_prompts_sent = 0` (§11, §18) |

Each is recorded, with its exact failed gate named, per 5F3B §11.5's existing
rule — never silently absorbed, never re-run except under 5F3B §15.1's
explicit infrastructure-replacement policy.

### 16.B — Infrastructure-attributable failure established AFTER the semantic prompt (post-prompt)

The one authorized semantic prompt for that task **was already sent** when
the failure is discovered. This is **never** called `INFRASTRUCTURE_REFUSAL`
— that term is reserved by the accepted I1 schema for the zero-prompt
paths in §16.A. Instead, per 5F3B §17.2 case 2 / §17.3, it is:

```text
semantic_prompts_sent   = 1                          (truthfully preserved)
run_validity             = INFRASTRUCTURE_CONTAMINATED
scoring_eligible         = false
```

The candidate is **neither credited nor blamed**; the attempt is retained in
full in the historical record (never deleted, never silently re-run as if
nothing happened); and the task may be replaced only under 5F3B §15.1's
explicit infrastructure-replacement policy — never by an automatic retry and
never by an automatic fallback to the other candidate or another route.

Examples this path covers:

| Condition | Classification |
|---|---|
| The first chat-completion request returns an explicit auth rejection (401/403 or equivalent), not observable at any pre-prompt gate | `run_validity = INFRASTRUCTURE_CONTAMINATED`, `semantic_prompts_sent = 1`, `scoring_eligible = false` |
| A route/provider failure that was not observable pre-prompt (e.g. the route becomes unreachable mid-turn, after having passed the zero-prompt `/models` check) | Same as above |
| Generated-config cleanup or Pi-process teardown fails its `stat`/reap verification **after** the semantic prompt was already sent | Same as above (§11, §18) |

**§15's open question about whether `/models` proves credential validity is
exactly why both paths must exist.** Until that question is resolved (§24),
I2 cannot assume every credential/route failure is pre-prompt-observable,
and must not misclassify a post-prompt discovery as a zero-prompt refusal.

## 17. Artifact-safety integration

I2 populates the **existing, unmodified**
`experiments/pi_implementer_qualification/qualification/safety.py`
`ArtifactSafetyContext` (§3) with:

| Field | I2 value |
|---|---|
| `endpoint_host` | the B300 base URL's host only (never scheme, port beyond the host component, path, query, or the full URL) — same extraction discipline as `route_check.py`'s `endpoint_host` |
| `api_key` | the resolved credential value, held only long enough to run the scrub check, never persisted itself |
| `bearer_token` | `None` — the B300 route uses a single `apiKey`/`Authorization: Bearer` value; there is no separate bearer token distinct from `api_key` for this route |
| `broker_token` | the per-run capability token, generated fresh per task exactly as AR2 already does |
| `pipe_name` | the per-run named-pipe identifier, generated fresh per task |
| `capability_id` | the per-run capability id, generated fresh per task |
| `workspace_absolute_path` | the synthetic fixture's canonical root for that task |

This document does **not** alter I1's `ArtifactSafetyContext` definition,
its `forbidden_needles` logic, or its refusal-record path
(`safety.py:57-181`) in any way — I2 only supplies values into fields I1
already defined.

## 18. Cleanup/teardown semantics (5F3B-I2A-FU1: made phase-aware)

Per task run, in order:

1. Pi child process exits (normally, on timeout, or on the accepted
   reap-grace boundary — this document does not redefine that boundary,
   which belongs to the runtime-turn deadline machinery 5F3B §3 already
   inherits).
2. The disposable `models.json` is deleted and the deletion is verified by
   `stat`, mirroring `scrub_generated_pi_config`
   (`pi_config.py:221-238`) exactly.
3. The disposable `settings.json` and the whole `PI_CODING_AGENT_DIR` are
   likewise deleted and the deletion verified.
4. Only after verified deletion does the run proceed to evidence emission:
   every retainable artifact for the run is scrubbed against the run-scoped
   secret/safety context (§11, §17), and only then is safe evidence emitted.
5. **Corrected (5F3B-I2A-FU1): a failed verification at step 2 or 3 is
   classified by whether the task's one semantic prompt had already been
   sent when the failure occurred — never unconditionally.** An earlier
   draft of this step said any cleanup-verification failure "must be
   recorded as `INFRASTRUCTURE_CONTAMINATED`," regardless of timing; that
   collapsed §16.A and §16.B into one case and is corrected here:
   - If `semantic_prompts_sent = 0` for that task at the point cleanup is
     attempted (e.g. the Pi process was only launched far enough to fail a
     zero-prompt compatibility gate, and teardown of its never-used
     disposable config then also fails to verify), the outcome remains
     `INFRASTRUCTURE_REFUSAL` with `semantic_prompts_sent = 0` (§16.A) — the
     cleanup failure is folded into that same pre-prompt infrastructure
     record, not elevated into a scored, contaminated attempt that never
     happened.
   - If `semantic_prompts_sent = 1` for that task (the one authorized
     semantic prompt had already been sent before cleanup was attempted),
     the outcome is `run_validity = INFRASTRUCTURE_CONTAMINATED`,
     `scoring_eligible = false` (§16.B) — the candidate is neither credited
     nor blamed, and the disposable directory is never promoted to retained
     evidence in either case.
   - **`semantic_prompts_sent` itself is never rewritten** based on when the
     cleanup failure was discovered; only `run_validity`/classification
     depends on that timing.
6. The Python-level references to the credential (the `env=` mapping and the
   run-scoped secret/safety context, §11) are allowed to go out of scope
   only after step 4's scrub-and-emit has completed; no explicit
   zeroization is attempted or claimed, and no claim is made that this was
   the only reference ever held (§11).

## 19. Evidence/provenance fields

In addition to every field 5F3B §26's record schema already defines, I2 adds
exactly these, all **never** carrying a credential, host, or absolute path
value:

```text
route_descriptor.provider_id            e.g. "b300_pi_qualification"
route_descriptor.model_id               "qwen3-coder-next" | "minimax-m2.7"
route_descriptor.backend_gateway_class  "b300_litellm_proxy"  (never "direct_vllm")
route_descriptor.credential_mechanism   "models_json_env_interpolation"
route_descriptor.credential_env_var_name_carried_to_child   the ONE new name (§9) — a NAME, never a value
models_json_omits_max_tokens            true
aido_requested_max_output_tokens        null

# 5F3B-I2A-FU2: rescoped to source provenance tied to the inspected version,
# never an unconditional per-run runtime fact (see §12's corrected wording).
pi_source_observation.inspected_version                    "0.84.3"
pi_source_observation.internal_registry_default_max_tokens 16384   (bookkeeping/registry
                                                                     fact only, tied to
                                                                     0.84.3's source, §12)
internal_registry_default_max_tokens_for_this_run   16384 if observed_pi_version == "0.84.3"
                                                     else "NOT_REESTABLISHED_FOR_OBSERVED_VERSION"

wire_level_max_tokens_observation_available   false    (permanent architectural fact, §12 —
                                                          NOT "not yet observed"; corrected
                                                          by 5F3B-I2A-FU1 from an earlier,
                                                          overstated "observed from Q1/Q2" claim)

# 5F3B-I2A-FU2: no observer for the Pi -> B300 provider-request COUNT exists
# either (distinct from the request-BODY non-observability above). The
# conceptual invariant ("one semantic prompt may cause one or many provider
# requests," §7.1) is unchanged; only the false implication that AIDO could
# record a numeric count is removed.
provider_inference_request_count_observation_available   false

semantic_prompts_sent                   0 | 1 — AIDO/controller-owned task-prompt count only
                                          (§7.1), truthfully preserved regardless of when a
                                          subsequent failure is discovered (§16, §18)
generated_config_scrub_verified         true | false    (combined with semantic_prompts_sent,
                                                          decides §16.A vs §16.B classification
                                                          — never an unconditional
                                                          INFRASTRUCTURE_CONTAMINATED, §18)
```

No endpoint value, host, IP, credential, header, or key is ever recorded —
identical to 5F3B §15's existing rule, unchanged.

## 20. Candidate symmetry

Candidate A (`qwen3-coder-next`) and Candidate B (`minimax-m2.7`) use:

- the same provider id, `api` type, and generated-config generator function;
- the same child-environment builder and the same one credential-carrier
  name;
- the same compatibility gate (§15);
- the same token policy (§12);
- the same retry policy (Pi-side provider `maxRetries: 0` in the generated
  `settings.json`, §10);
- the same semantic-prompt policy (5F3B §9: one per task, no retry, no
  continuation).

Only `route_descriptor.model_id` (and the resulting `models[]` entry in the
generated `models.json`) differs between the two. No candidate-specific
compatibility flag, timeout, prompt wording, or credential handling is
introduced by this design.

## 21. Security limitations / honest claims

- **This is not a sandbox, and I2 does not create one.** `docs/security.md`
  states plainly that Pi "does not include a built-in sandbox" and "runs
  with the permissions of the pi process" — corroborating, from Pi's own
  documentation, the accepted AR2D conclusion (5F3B §22.1) that the broker
  is a capability boundary for AIDO-mediated filesystem operations, not an
  OS-level isolation boundary or a credential-confidentiality guarantee
  against a same-user adversary.
- **The credential is only as safe as the OS process environment block.** A
  same-user process with sufficient privilege (e.g. a debugger, or another
  process reading `/proc`-equivalent Windows process memory) could read the
  Pi child's environment block for the run's duration. This design does not
  claim otherwise, and no OS-level environment-block protection is added.
- **Redaction is a backstop, never a guarantee.** The `ArtifactSafetyContext`
  scrub (§17) is a best-effort check against a small number of known-shape
  needles, exactly as the accepted 5F2E redaction policy already states for
  its own text redactor.
- **No claim of memory zeroization.** Python provides no guaranteed
  zeroization of string data; this document (§11) explicitly declines to
  claim the credential is "erased" from memory after use.
- **`/models` proving credential validity is unresolved** (§15) — this
  document does not claim either way, and flags it as an open question
  rather than silently assuming the safer or the more convenient answer.
- **Cleanup verification is a `stat` check, not a forensic guarantee.** A
  deleted file's prior on-disk bytes are not claimed to be unrecoverable by
  forensic means; only that the file no longer exists under its known path.

## 22. What is NOT authorized by this phase

- Running any candidate model, now or as part of producing this document.
- Implementing the I2 config generator, environment builder, or route
  descriptor code.
- Modifying frozen `experiments/pi_external_runtime_ar1/`,
  `experiments/pi_external_runtime_ar2/`, `experiments/pi_external_runtime_ar2_o1/`,
  or `experiments/pi_implementer_qualification/`.
- Modifying `src/`, `tests/`, `projects/`, `CLAUDE.md`, or the root README.
- Reading, printing, or recording any real environment-variable value.
- Any network request, any HTTP call (including the non-inference `/models`
  check), or any Pi process launch.
- A `pi.registerProvider()`-based extension (§7 explains why mechanism 1 is
  chosen instead — this remains available as a future alternative, not
  something this phase implements).
- The differential `/models` credential-validity probe named as an open
  design option in §15 — noted, not designed in detail, not authorized.
- Real-workspace or sibling-project implementation of any kind (unchanged
  from 5F3B §22.1).

## 23. Minimum I2 implementation slices (for a future, separately authorized phase)

Staged, smallest-viable, none implemented now:

| Slice | Content |
|---|---|
| **I2-1** | The I2-owned child-environment builder (§9): explicit positive allowlist, one new credential-carrier name, forbidden-fragment audit, offline unit tests only |
| **I2-2** | The I2-owned disposable Pi-config generator (§10): `settings.json` + `models.json`, `$ENV` apiKey reference, `maxTokens` omitted and enforced, offline unit tests only |
| **I2-3** | The route descriptor + qualification-owned config loader accepting exactly `qwen3-coder-next` / `minimax-m2.7`, replacing AR2/O1's single-model pin **in new code only** |
| **I2-4** | Wiring reuse of the unmodified `ar2.route_check.check_route_serves_model` for the non-inference gate, plus the credential-read-ordering discipline (§8: read only after every non-credential offline gate passes) |
| **I2-5** | The generated-config scrub/teardown path (§18) plus `ArtifactSafetyContext` population (§17), with offline tests proving **both** phase-aware branches of §16/§18's corrected classification: a scrub-verification failure while `semantic_prompts_sent == 0` yields `INFRASTRUCTURE_REFUSAL`, and a scrub-verification failure while `semantic_prompts_sent == 1` yields `run_validity = INFRASTRUCTURE_CONTAMINATED` with `scoring_eligible = false` — never the other way around, and never a rewritten prompt count in either case. Neither branch promotes the disposable directory to retained evidence |

Each slice remains **fully offline and testable without any live model
activity**, mirroring how I1 was built and accepted before any route
dependency existed. Only after all of I2-1 through I2-5 land, pass their own
offline suites, and receive their own explicit go-ahead would the Category B
zero-prompt live gates (§15) become executable — and only after those pass
would Q1/Q2 (5F3B §24) become executable, unchanged from 5F3B's existing
ordering constraints.

## 24. Open questions / blockers

1. **Does the B300 LiteLLM proxy actually validate the `Authorization`
   header for the Pi-served route, and does a missing/invalid credential
   fail closed?** Unknown from local source (§15). Not a blocker for
   *designing* the mechanism (§7's `$ENV` interpolation works identically
   whether the proxy validates the key or not), but it is exactly why §16
   is now split into Path A (pre-prompt, `INFRASTRUCTURE_REFUSAL`) and Path
   B (post-prompt, `INFRASTRUCTURE_CONTAMINATED`) — I2 cannot assume a bad
   credential is always pre-prompt-observable, and the failure-attribution
   logic (I2-4) must implement **both** paths rather than only the
   pre-prompt one. **Not resolved here; carried forward as an I2
   implementation question**, and both classification paths remain correct
   regardless of how it resolves.
2. **`wire_level_max_tokens_observation_available` is permanently `false`
   in this architecture (§12), not merely "unknown until Q1/Q2."** This is
   not an open question this document expects Q1/Q2 to answer — it is a
   corrected, settled fact: no request-body observer exists anywhere in the
   designed flow. Whether a *future, separately authorized* instrumentation
   phase could add one is left genuinely open, but is explicitly not
   designed, assumed, or relied upon here.
3. **Whether the B300 proxy needs any `compat` flags** (e.g.
   `supportsDeveloperRole: false`, matching AR2's own reasoning-model
   compat block) is unverified for this specific proxy/model pair from
   local source alone; §15's zero-prompt compatibility gate is the
   earliest point this could be observed without spending a semantic
   prompt, but even that gate cannot fully prove wire-format
   compatibility — only Q1/Q2's actual transmission can.
4. **The exact credential-carrier environment-variable name** proposed in
   §9 (`PI_QUALIFICATION_B300_ROUTE_KEY`) is this design's recommendation,
   not a frozen constant — a future I2 implementation may choose a
   different exact string, provided it satisfies the same non-`AIDO_`,
   non-forbidden-fragment, single-exception discipline this document
   requires.

No blocker prevents I2A's own conclusion (§25) — every open question above
is explicitly deferred to I2 implementation or to Q1/Q2's own live evidence,
never silently assumed.

## 25. GO / NO-GO for I2 implementation

**5F3B-I2A is ACCEPTED and ready to freeze. GO for 5F3B-I2 implementation of
slices I2-1 through I2-5 (§23), on the architecture this document freezes —
unchanged in verdict after 5F3B-I2A-FU1 and 5F3B-I2A-FU2.**

FU1 corrected four **semantic inconsistencies** in this document's wording
and accounting (§7.1 prompt-vs-request count, §11 credential lifecycle,
§16/§18 failure-attribution phase split, §12 wire-observability overstatement).
FU2 then closed four more, all residual staleness left over from FU1's own
edits rather than new problems (§18/§23/Appendix cleanup-classification
wording that had not caught up to §18's own phase-aware rule; §19's
overstated provider-request-count observability; §12/§19's unscoped `16384`
version fact; §9's implied keyless-fallback branch). **None of the eight
corrections across FU1 and FU2 touched the accepted architecture itself:**
the chosen credential mechanism (§7), the environment/config generator
design (§9/§10), candidate symmetry (§20), and the `maxTokens`-omission
policy (§12's core rule) are all unchanged. Correcting inaccurate claims
about them is not a new blocker — it is exactly the kind of closure a
design-only phase is for, and after two such passes finding no further
architectural issue, this document freezes.

**No new blocker exists after FU2.** The open questions carried forward
from FU1 (§24) are unchanged and remain explicitly deferred to I2
implementation or to Q1/Q2's own live evidence — none of them was a
blocker before, and none is one now.

Justification:

- Every one of the task brief's five-plus candidate credential mechanisms
  was checked against actual local Pi 0.84.3 source (not assumption), with
  file/line citations (§6).
- The chosen mechanism (§7) reuses an already-accepted shape (AR2's `$ENV`
  interpolation pattern) rather than introducing a new one, minimizing new
  attack surface and new review burden.
- The credential never touches a file, argv, a model prompt, or Git-tracked
  config at any point in the designed flow (§8, §11).
- The one new environment-variable name is subject to the same
  forbidden-fragment discipline AR2 already established, applied by new,
  non-modifying code (§9).
- Every gate is cleanly separated into fully-offline (§14) and
  zero-semantic-prompt-live (§15) categories, so I2-1 through I2-5 can be
  built and tested with **zero** live model or network activity, exactly as
  I1 was.
- Every unresolved fact (§24) is named honestly rather than guessed, and
  none of them blocks writing or testing the offline slices.

**NO-GO, explicitly, for everything else at this time:**

- **I2 implementation code itself is not written by this phase** — this
  document is design only, per its own hard write scope.
- **The Category B zero-prompt live gates (§15) are not run** — they
  require I2 implementation to exist first.
- **5F3B-Q1/Q2 remain NOT authorized** — unchanged from 5F3B §26.
- **Real-workspace authority remains NOT authorized** (5F3B §22.1,
  unchanged).

---

## FU1 correction record (5F3B-I2A-FU1)

Four semantic inconsistencies closed, none reopening the accepted
architecture:

| # | Inconsistency (as it stood before FU1) | Correction | Where |
|---|---|---|---|
| 1 | "One semantic prompt == one B300 HTTP request," and `maxRetries: 0` was said to enforce that bound | Froze three distinct concepts — `semantic_prompts_sent` (AIDO-owned, still exactly 1), `provider_inference_requests` (Pi-owned, uncapped, not a qualification metric), `transport_retries_per_provider_request` (what `maxRetries: 0` actually bounds — one request's own retry, not the turn's request count) | §7.1 (new), §8 diagram/bullets, §10 |
| 2 | Parent-side lifetime claimed the credential's only reference was released after building `env=`, while §17 required the same value survive for artifact scrubbing — a direct contradiction | Froze one lifecycle: read → one run-scoped secret/safety context → child env → launch → teardown → generated-config cleanup verified → **every** retainable artifact (record, protocol/RPC summaries, stdout/stderr-derived text, provider/error text, lineage/refusal evidence) scrubbed against that same context → safe emission → only then may references be released, where practical. Withdrew the "no second reference exists" and implicit zeroization claims | §11 (rewritten), §8 bullets |
| 3 | A credential/route failure was classified as `INFRASTRUCTURE_REFUSAL` regardless of whether it was discovered before or after the semantic prompt was sent | Split into 16.A (pre-prompt → `INFRASTRUCTURE_REFUSAL`, `semantic_prompts_sent = 0`) and 16.B (post-prompt, infrastructure-attributable → `run_validity = INFRASTRUCTURE_CONTAMINATED`, `semantic_prompts_sent = 1` truthfully preserved, `scoring_eligible = false`). Cleanup-failure classification (§18) made phase-aware the same way. Prompt count is never rewritten based on discovery timing | §16 (split), §18 (rewritten) |
| 4 | Claimed the true wire-level `max_tokens` would be "observable from Q1/Q2 itself" | Corrected: no request-body observer exists anywhere in this architecture; `wire_level_max_tokens_observation_available = false` is a permanent architectural fact, not a "not yet run" state; a future, separately authorized instrumentation layer is noted but not designed or assumed here | §12 (rewritten), §19, §24 item 2 |

## FU2 correction record (5F3B-I2A-FU2)

Four further consistency issues closed — all residual staleness left by
FU1's own edits not fully propagating, none reopening the accepted
architecture:

| # | Inconsistency (as it stood before FU2) | Correction | Where |
|---|---|---|---|
| 1 | §23's I2-5 slice and the Appendix "Generated-config lifecycle" summary still said a scrub/cleanup-verification failure unconditionally yields `INFRASTRUCTURE_CONTAMINATED`, contradicting §18's own FU1-corrected phase-aware rule | Made both spots phase-aware, matching §18: `semantic_prompts_sent == 0` at the time of failure → `INFRASTRUCTURE_REFUSAL`; `semantic_prompts_sent == 1` → `run_validity = INFRASTRUCTURE_CONTAMINATED`, `scoring_eligible = false`. I2-5 must offline-test **both** branches | §23 (I2-5 row), Appendix item 10 |
| 2 | §19 listed `provider_inference_requests_per_task` as though a numeric per-task count were observable evidence, when §7.1 never established any observer mapping an AIDO-visible event one-to-one onto each provider HTTP request | Replaced with `provider_inference_request_count_observation_available = false`; added an explicit "quantity exists != AIDO can measure it" paragraph to §7.1. The underlying invariant (one semantic prompt may cause one or many provider requests) is unchanged; no HTTP observer, instrumentation, or counting hook is added | §7.1, §19 |
| 3 | `pi_internal_registry_default_max_tokens = 16384` was written as though it were an unconditional per-run runtime fact for every compatible Pi version | Rescoped to `pi_source_observation` (tied explicitly to inspected version `"0.84.3"`), with a per-run field that falls back to `NOT_REESTABLISHED_FOR_OBSERVED_VERSION` when `observed_pi_version` differs — never a new exact-version gate, never a semver range. `aido_requested_max_output_tokens = null` and `models_json_omits_max_tokens = true` remain invariant AIDO-owned facts, unaffected | §12 (rewritten), §19 |
| 4 | §9 said the credential-carrier value "is never a fixed placeholder... unless the operator's B300 credential is genuinely unnecessary," implying an undesigned second, keyless mode | Withdrawn. This qualification route requires the established `AIDO_LITELLM_API_KEY`; a missing/blank value is a pre-prompt `INFRASTRUCTURE_REFUSAL` (§16.A) — never a silent placeholder substitution. A genuinely keyless future B300 deployment would be a separately reviewed route/configuration change, not an implicit branch here | §9 (rewritten) |

## Appendix: final report checklist

1. **Document created:** `docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md` (this file).
2. **Locally inspected Pi version:** `0.84.3` (`package.json:3`), provenance
   only per 5F3B §14 — no pin introduced.
3. **Exact Pi credential/config mechanisms found:** `$ENV`/`${ENV}`
   interpolation, `!command` shell execution, literal value, `auth.json`
   (OAuth or stored API key), CLI `--api-key`, and
   `pi.registerProvider()`-based extension `resolve()` credential callbacks
   (§6).
4. **Local source evidence for those mechanisms:** `docs/models.md:147-176`,
   `docs/providers.md:58-186,310-317`, `docs/custom-provider.md:35-90,655-695`,
   `dist/core/resolve-config-value.js` (full file), `dist/core/model-runtime.js:339-451`,
   `dist/cli/credential-print.js:1-9` (§4, §6, §7).
5. **Chosen credential mechanism and why:** `$ENV` interpolation inside a new,
   I2-owned, AR2-shaped disposable `models.json` — smallest new surface,
   reuses an already-accepted pattern, satisfies candidate-symmetry (§7).
6. **Whether any credential must enter `models.json`:** No — only the
   variable *name*, as `"$PI_QUALIFICATION_B300_ROUTE_KEY"` text, never the
   value (§10, §11).
7. **Whether any credential enters the Pi child environment:** Yes — exactly
   one value, under exactly one new, non-`AIDO_`-prefixed, non-forbidden-
   fragment name, for the run's duration (§9, §11).
8. **Confirmation no credential enters argv:** Confirmed — the CLI
   `--api-key` mechanism (§6, item 6) is explicitly identified and explicitly
   excluded; the accepted AR2 argv shape carries no such flag and none is
   added (§11).
9. **Proposed qualification-owned env allowlist:** §9's table — Windows
   baseline names, narrowed `PATH`, Pi-owned `PI_*` variables, no profile
   names, and exactly one new credential-carrier name.
10. **Generated-config lifecycle:** created only after offline gates pass →
    used for the run's duration → deleted and deletion verified by `stat`
    before evidence emission. A verification failure is phase-aware
    (corrected by FU2, consistent with FU1): if `semantic_prompts_sent == 0`
    at that point, it stays an `INFRASTRUCTURE_REFUSAL`; only if
    `semantic_prompts_sent == 1` does it become
    `run_validity = INFRASTRUCTURE_CONTAMINATED` (§10, §11, §16, §18).
11. **Candidate A/B route descriptors:** same provider id/generator/child-env
    policy/compat/token/retry/semantic-prompt policy; only `model_id` differs
    (`qwen3-coder-next` vs `minimax-m2.7`) (§20).
12. **Token-policy preservation:** `aido_requested_max_output_tokens = null`
    preserved; generated `models.json` omits `maxTokens`; one honest caveat
    recorded, scoped by FU2 to the exact Pi version inspected (`0.84.3`) as
    source provenance rather than a permanent cross-version fact — Pi
    0.84.3's own internal `16384` registry default is not shown, from local
    source, to reach the wire request (§12).
13. **Offline gates:** §14, seven checks, all file/string-level, no process
    launch, no network, no credential read.
14. **Future zero-prompt live gates:** §15, ten checks, explicitly not run in
    this phase, requiring I2 implementation first.
15. **Failure attribution policy:** §16, corrected by FU1 into two paths —
    16.A (pre-prompt: `INFRASTRUCTURE_REFUSAL`, `semantic_prompts_sent = 0`)
    and 16.B (post-prompt infrastructure-attributable:
    `run_validity = INFRASTRUCTURE_CONTAMINATED`, `semantic_prompts_sent =
    1`, `scoring_eligible = false`) — never a candidate failure in either
    path, never an automatic fallback or retry.
16. **`ArtifactSafetyContext` integration:** §17 table populating I1's
    existing, unmodified fields; I1's scrub logic itself is untouched.
17. **Security limitations:** §21 — not a sandbox, OS-level environment-block
    exposure is not eliminated, redaction is a backstop, no memory-
    zeroization claim, `/models`-proves-auth is unresolved.
18. **Implementation slices:** §23, I2-1 through I2-5, each fully offline and
    testable before any live gate.
19. **Blocker, if any:** None blocking this design's own conclusion; four
    open questions (§24) are explicitly deferred to I2 implementation or to
    Q1/Q2's own live evidence.
20. **GO/NO-GO for actual I2 implementation:** **GO** for I2-1 through I2-5
    (offline slices only), per §25. Q1/Q2 remain **NOT authorized**.
21. **Files changed:** exactly one — this new document. No other file was
    created, edited, or deleted.
22. **`git diff --check`:** N/A for a new, untracked file; no whitespace
    errors introduced (verified by review of this file's own content).
23. **`git status --short`:** shows exactly one new untracked file,
    `docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md`.
24. **Confirmation no environment values were dumped/read:** Confirmed — no
    `set`, `env`, `printenv`, `os.environ` dump, or `Get-ChildItem Env:` was
    executed at any point; only environment-variable **names** were read
    from source/docs/config files.
25. **Confirmation no credential value was read:** Confirmed — no API key,
    bearer token, or other credential value was read, printed, or copied
    into any fixture at any point.
26. **Confirmation no network/model/Pi semantic prompt occurred:** Confirmed
    — no HTTP request, no model call, and no Pi process (not even
    `--version`) was launched while producing this document.
27. **Confirmation frozen AR1/AR2/O1/I1 remained untouched:** Confirmed —
    only `Read`/`Grep`/`Bash` (read-only `find`/`grep`) operations were used
    against those directories; no file under
    `experiments/pi_external_runtime_ar1/`,
    `experiments/pi_external_runtime_ar2/`,
    `experiments/pi_external_runtime_ar2_o1/`, or
    `experiments/pi_implementer_qualification/` was created, edited, or
    deleted.
