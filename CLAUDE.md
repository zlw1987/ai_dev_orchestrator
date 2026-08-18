# CLAUDE.md

This file is the **operating guide for Claude Code** in this repository. Read it
before doing any work here.

## Workspace boundary

- **Allowed:** `C:\dev\ai_dev_orchestrator` — operate only inside this folder.
- **Forbidden** (do not read, search, list, or modify):
  - `C:\dev\mis_project`
  - `C:\dev\a8_oa`
  - `C:\dev\bible_reading_v2`
  - any parent directory above `C:\dev\ai_dev_orchestrator`

## Current phase

- **Phases 0 through 5F2E-V1-FU1: complete.** See
  [docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md](docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md)
  — read its **CURRENT STATUS** block first; older sections in that file are
  design history and some of their status claims are deliberately stale.
- **Phase 5F2C shipped the first controlled target-workspace write**, and
  Phase 5F2C-FU1 corrected six review findings against it (§28.13).
- **Phase 5F2D shipped the first controlled verification execution** (§29) —
  the first separately authorized capability here to run repository-controlled
  code — and Phase 5F2D-FU1 corrected five review findings against it (§29.13):
  a wall-clock bound that was not actually a bound, an unpinned HEAD, globally
  scoped capability claims, an unprovable `next_step`, and an overstated
  environment-forwarding claim. **Phase 5F2D-FU2** (§29.14) then corrected three
  more: an output cap that was not enforced when it was passed, an imprecise
  timeout-versus-reap-grace contract, and an overstated abandoned-reader lifetime
  claim.
- **Phase 5F2E shipped the first controlled reviewer integration** (§30) — the
  first runtime capability here that deliberately sends **source-derived code**
  to a model. One command, `l2-review-approved-file-edit`, runs the accepted
  5F2D verification itself and, only on a `verified` outcome, sends one approved
  diff plus selected plan prose and redacted verification output to one
  project-configured reviewer model, then prints one human-facing packet.
- **Phase 5F2E-RS1 shipped bounded reviewer runtime supervision** (§31),
  corrected by **5F2E-RS1-FU1** (§31.16) and **5F2E-RS1-FU2** (§31.17), because a
  **local** reviewer model can burn inference wall time, GPU occupancy,
  concurrent-request capacity and context occupancy while producing nothing
  usable. The controlled reviewer forces its transport `max_retries` to **0** —
  so one semantic attempt is exactly one HTTP/model request — and the supervisor
  owns a hard maximum of **two** semantic requests AIDO may issue. FU1 made a
  **stall terminal** (no retry after an unconfirmed timeout), narrowed the retry
  to **completed but unusable** responses, renamed the opt-in to
  `compact_retry_on_unusable_output`, and corrected the resource-bound wording.
  FU2 then established the wait bound itself: httpx's timeout is a
  network-operation/inactivity timeout, so AIDO now runs each attempt's single
  client call on **one daemon worker** and waits to its **own monotonic
  deadline**. The output artifact was **`review-packet.v2`**.
- **Phase 5F2E-V1 shipped the direct vLLM reviewer provider.** It is a
  **reviewer-provider extension and nothing else**: `controlled_review.provider`
  now accepts exactly `"litellm"` or `"vllm"`, matched exactly and
  case-sensitively. LiteLLM remains supported for when internal infrastructure
  returns; direct vLLM is an **additional** explicit option, not a replacement.
  Every accepted 5F2E and RS1 semantic is unchanged and applies identically to
  both providers. The output artifact is now **`review-packet.v3`**, which
  additionally records the reviewer provider and the transport scheme truthfully.
- **Phase 5F2E-V1-FU1 corrected V1's one acceptance blocker**: the reviewer's
  environment reader snapshotted **both** provider families from the process
  environment and discarded the unconfigured one afterwards, which is still
  reading it. The reader is now handed the provider and resolves it to an exact
  name tuple **before** touching any environment, so a vLLM review never reads an
  `AIDO_LITELLM_*` value and a LiteLLM review never reads an `AIDO_VLLM_*` value.
  The union env-name constant and the narrow-afterwards helper were **removed**.
  FU1 also made the CLI's reviewer-environment failure category
  provider-neutral and corrected stale `v2`/LiteLLM-only prose. No accepted V1 or
  RS1 behavior was reopened.
- **The first controlled write → verify → supervised review → human path now
  exists.** **L2 as originally defined is still NOT complete**: there is no
  model-backed implementer, no automatic fixer, no branch creation, no commit, no
  push, no PR, and no generalized writer.

```text
5F2C           Controlled Single-File Writer        DONE / ACCEPTED
5F2D           Controlled Verification              DONE / ACCEPTED
5F2E           Controlled Reviewer Integration      DONE / ACCEPTED
5F2E-RS1       Reviewer Runtime Supervision         DONE
5F2E-RS1-FU1   Terminal timeout + wording fixes     DONE
5F2E-RS1-FU2   AIDO-owned reviewer wait deadline    DONE
5F2E-V1        Direct vLLM Reviewer Provider        DONE
5F2E-V1-FU1    Provider env isolation + wording     DONE
→ bounded write → verify → supervised review → human
```

Do **not** insert generalized writer work here, and do **not** implement a fixer
(old Phase 7) or a model-backed implementer: both remain separately
unauthorized. The old roadmap's **Phase 6 "qwen reviewer" is superseded** by
5F2E's configurable reviewer — 5F2E hard-codes no model, so no separate
qwen-only integration phase is required.

### What the writer can and cannot do

One command, `l2-apply-approved-file-edit`, writes a file. It is deliberately
narrow, and the narrowness is the design — not a gap to fill in:

- **one** file per invocation, **`modify` only**, on an existing Git-tracked
  ordinary UTF-8 file, in a **wholly clean Windows Git repository** whose top
  level is exactly the configured workspace root;
- gated by a project opt-in (`workspace_write`, ships disabled) plus two
  explicit CLI flags plus an exactly-worded human approval of the concrete diff;
- the diff is applied **exactly** — no fuzz, no offset search, no repair — and
  both the pre-image and post-image are pinned by SHA-256;
- everything outside that domain **fails closed**.

Do **not** add any of the following without an explicit, separate prompt: file
creation, deletion or renaming; multi-file writes; protected-path writes; a
transaction framework; a journal; rollback; crash recovery; a concurrency
framework; or a generalized Git executor.

### What the verifier can and cannot do

A **separate** command, `l2-verify-approved-file-edit`, executes the project's
own configured verification process. The writer has no verification flag, and
the verifier writes nothing.

- **one** already-applied approved `modify`, bound on both sides: the target's
  bytes must hash to the approved `post_image_sha256`, the **HEAD object id must
  be exactly unchanged**, and the Git-visible dirty state must be **exactly**
  that one path as an unstaged modification — before the process runs and again
  after it terminates;
- **one** command, **once**: argv is exactly
  `[configured_absolute_executable, *configured_args]`, `shell=False`, cwd is the
  canonical workspace root, stdin is `DEVNULL`, with an output bound enforced
  during capture — at the moment the cap is passed, never waiting for a buffer to
  fill, and the over-limit bytes are dropped — and a bound on **AIDO's own
  wait**. No retry, no fallback, no PATH search;
- gated by a project opt-in (`controlled_verification`, ships disabled) plus two
  explicit CLI flags. The executable must be absolute, existing, a regular file,
  and **outside** the target workspace;
- the child environment is a fixed minimal allowlist — **no** `AIDO_*`, no
  `GITHUB_TOKEN`, no credential, and no way to configure forwarding. That is a
  claim about the *environment* only: configured `args` are trusted config data
  used verbatim, and AIDO does not prove they contain no sensitive literal;
- exit **1** refused before launch, **2** ran and did not pass, **3** ran and the
  repository is no longer provably the approved state (never called "failed", and
  never repaired).

> **Controlled invocation is not sandboxed execution.** The launched process is
> not confined, and its descendants are not tracked and may still be running
> after the command returns. Never write code or documentation claiming the
> verification made no network access, touched only allowed paths, spawned no
> children, had its children terminated, could not reach credentials, or was
> side-effect free.
>
> **Scope every AIDO-owned negative claim.** Fields like `committed: false` or
> `pushed: false` must never appear unscoped — the child may have done those
> things. Use the `orchestrator_` prefix, and keep child-scoped fields as
> `"not sandboxed"` strings rather than booleans.
>
> **The timeout bounds AIDO's wait, not the child's life.** A descendant holding
> the inherited output pipe must not be able to block the reader past the
> deadline (that was the 5F2D-FU1 defect), but nothing may claim descendants were
> stopped. Stated exactly: the configured timeout bounds the execution/capture
> wait, and after it AIDO may spend at most a fixed direct-child reap grace on
> that one process handle. The abandoned reader thread and its pipe handle may
> outlive the run indefinitely — that is a documented residual limitation, **not**
> something to fix with job objects, `taskkill`, process groups, `psutil`, or
> descendant enumeration.

The L1 plan's `required_verification` is **never** command authority. Do not
split it, parse it, run it, or turn it into argv.

Do **not** add any of the following without an explicit, separate prompt: a
shell or command string; command chaining, pipelines or redirection; multiple
command profiles, command ids, or before/after hooks; retries; automated repair,
`git restore`, or any cleanup of a failed verification; environment or secret
forwarding; installation or dependency commands; a generalized command executor;
a process-tree management framework (job objects, `taskkill`, process groups,
`psutil`); or any form of sandboxing or child-effect auditing.

### What the reviewer can and cannot do

A **third** command, `l2-review-approved-file-edit`, is the first runtime
capability here that deliberately sends **source-derived code** to a model. It
does **not** run the writer, and it does **not** duplicate the verifier — it
calls the accepted 5F2D library path.

- **verify first, review second.** The command runs the existing verification
  itself; there is **no `--verification-result` input** and no saved report is
  trusted as authority. Only a `verified` outcome proceeds;
- **credential ordering is load-bearing.** No reviewer endpoint or credential
  value of **either** provider — `AIDO_LITELLM_API_KEY`, `AIDO_LITELLM_BASE_URL`,
  `AIDO_LITELLM_DEFAULT_MODEL`, `AIDO_VLLM_BASE_URL`, `AIDO_VLLM_API_KEY` — is
  read until after verification returns `verified`, so reviewer credentials never
  coexist in process state with unsandboxed repository-controlled execution.
  Reviewer credentials are never forwarded to the verification child, and 5F2D's
  environment policy is unchanged;
- gated by a project opt-in (`controlled_review`, ships disabled) plus two
  explicit CLI flags (`--verify-approved-file-edit`, `--real-reviewer`). The
  model comes **only** from `controlled_review.model` — no CLI `--model`, no
  environment default of either provider, no glob or case-folded matching.
  `real_model_planning` does **not** authorize review;
- the reviewer receives **only**: trusted identity, selected approved-plan prose,
  the **one** approved unified diff, and the freshly produced verification facts
  with their already-bounded, redacted output. Never the full target file, never
  unrelated source, a listing, a tree, git history, an absolute path, the
  approval text, the raw artifact, or any credential;
- the reply must be exactly one strict JSON object; it is **rejected, never
  repaired** — no parser repair, no "fix your JSON" round trip, no merging of two
  replies;
- exit **1** refused, **2** verification did not pass, **3** workspace untrusted,
  **4** reviewer stage failed after verification passed, **0** a valid review —
  for `approve`, `changes_requested` **and** `needs_human_review` alike.

### Which reviewer backend, and over what transport (5F2E-V1)

V1 is a **reviewer-provider extension and nothing else**. It is not Pi
integration, not a model-backed implementer, not an agent loop, not RS2 reviewer
failover, not a fallback or second reviewer, not a fixer, not a review/fix loop,
not backend cancellation, and not a generic provider framework. Do not add any of
those here.

- `controlled_review.provider` accepts **exactly** `"litellm"` or `"vllm"`,
  matched **exactly and case-sensitively**. No alias, no glob, no case folding,
  no `"openai"`, no `"openai_compatible"`, no provider registry, no plugin
  system, no provider list, no provider priority, and no failover. A small
  explicit two-way branch dispatches them — do not generalize it;
- **LiteLLM stays supported**, unchanged, for when internal infrastructure
  returns. Direct vLLM is an **additional** option, not a replacement, and V1 must
  not retroactively break an accepted LiteLLM deployment;
- **model authority is unchanged and provider-independent:**
  `project_config.controlled_review.model` only. The vLLM path deliberately has
  **no** `AIDO_VLLM_DEFAULT_MODEL`, and the LiteLLM path still overrides
  `AIDO_LITELLM_DEFAULT_MODEL`;
- **the endpoint is environment-only, never project config.** vLLM requires
  `AIDO_VLLM_BASE_URL`; `AIDO_VLLM_API_KEY` is optional. **No** `AIDO_LITELLM_*`
  variable is required, read, or accepted for a vLLM reviewer, and the reverse
  holds too;
- **only the configured provider's names are ever read** (5F2E-V1-FU1). The
  reader is handed the provider and resolves it to an exact name tuple **before**
  it touches the process environment, so the other family is never looked up at
  all. Do **not** reintroduce a union snapshot narrowed afterwards: reading a
  credential and then discarding it is still reading it, and that was V1's one
  acceptance blocker. There is deliberately no union `REVIEWER_ENV_NAMES`
  constant left to regress to;
- **a keyless vLLM server gets a placeholder, not a credential.** When
  `AIDO_VLLM_API_KEY` is absent or blank, AIDO substitutes the fixed, non-secret
  literal `no_api_key` so the existing client shape — which always sends an
  `Authorization` header and requires a non-blank `api_key` — works unchanged.
  **Never describe it as authentication**, and do **not** weaken the generic
  `LLMClientConfig` to make `api_key` optional;
- **plaintext HTTP fails closed for vLLM.** `http` is refused before any model
  request unless `controlled_review.vllm_allow_insecure_http` is true (it ships
  `false`). The refusal happens after verification may already have passed —
  ordering is preserved — and never prints the full base URL. Nothing upgrades,
  rewrites, or tunnels the URL. The rule is **not** applied to the LiteLLM
  provider;
- **the opt-in is an acknowledgement, not a security property.** It means only
  that this project explicitly permits source-derived reviewer material over
  plaintext vLLM transport. It does **not** mean secure, encrypted, private,
  authenticated, company-approved, or safe for secrets, and an internal,
  colleague-hosted, or same-network endpoint is not private merely because of
  where it sits. Never write otherwise, and never hard-code a real endpoint or IP
  into runtime code, warning logic, or documentation;
- **the human-facing banner names the provider, the endpoint host and the
  transport**, and an unencrypted transport is announced unmistakably as
  `NOT TLS-ENCRYPTED`. Host only — never the base URL, the API key, the
  placeholder, the prompt, the diff, or an absolute path;
- **no CLI surface change.** `l2-review-approved-file-edit` keeps its exact
  option set: no new command, no `--provider`, `--model`, `--endpoint`,
  `--base-url`, `--api-key`, or `--allow-insecure-http`. Provider selection is
  project-config only; endpoint selection is environment-only;
- **RS1 applies identically to both providers.** A vLLM timeout is still
  `review_stalled`, still terminal, and still gets no retry; the only second
  request remains the accepted completed-but-unusable compact retry. Do not add a
  provider-specific retry, timeout, or backoff.

The output artifact is **`review-packet.v3`**, whose reviewer provenance carries
`provider`, `model`, `model_source`, `endpoint_host`, `endpoint_scheme` and
`transport_tls` — and still never a base URL, credential, header, full path,
query, fragment, or workspace absolute path. **`v1` and `v2` keep their original
meanings**: both were LiteLLM-only and reported no transport scheme, and an
archived `v2` packet must never be reinterpreted as though it may have come from
vLLM.

### What the reviewer supervisor can and cannot do (5F2E-RS1 + FU1 + FU2)

RS1 exists because a **local** model's cost is inference wall time, GPU
occupancy, concurrency and context occupancy — not an API price. State its scope
exactly:

> **RS1 bounds AIDO's reviewer request issuance and AIDO's wait budget.** It
> proves: reviewer transport retries issued by AIDO = 0; at most 2 semantic
> requests issued by AIDO; **an AIDO-owned monotonic deadline on each attempt's
> wait**; the requested max output tokens; and the completed-response retry
> policy.
>
> It does **NOT** prove a bound on the abandoned worker's lifetime, the HTTP
> request's lifetime after AIDO stops waiting, backend inference lifetime, GPU
> occupancy lifetime after a client disconnect, backend context lifetime, or
> server-side cancellation latency. **Never write "the reviewer runtime is
> bounded", "the resource envelope is bounded", or any claim that total GPU time
> is bounded.**

- **the wait bound is AIDO's OWN deadline, not httpx's (FU2).** An httpx timeout
  is a **network-operation/inactivity** timeout, not an absolute deadline around
  `client.chat()`: a peer producing frequent activity can hold one request open
  far past the configured value without any single read timing out. So each
  attempt runs its one client call on **one daemon worker thread** that publishes
  the response or the exception, while the main thread waits to a monotonic
  deadline and owns the decision. Keep it exactly this small — **no**
  `ThreadPoolExecutor` (its shutdown would wait for the worker), no pool, no
  registry, no reusable task framework, **no `join` at all**, no thread kill, no
  socket close from the supervisor, no process, no asyncio. The reviewer client
  keeps receiving the same value as a *secondary* network-inactivity timeout, but
  that is never the proof;
- **the abandoned worker is abandoned, not terminated.** After a deadline the
  worker may still be inside `client.chat()`. Say only: AIDO's wait is bounded;
  AIDO does not wait for it; it may outlive the invocation in a long-lived
  process; the network operation and backend inference may still be active.
  **Never call it terminated, never claim its lifetime is bounded, never claim
  the request was cancelled**, and do not add worker tracking or cleanup. Process
  exit may end local daemon-thread state, but RS1 must never use or claim
  interpreter exit as a cancellation mechanism. Because a stall is terminal, one
  invocation can leave **at most one** abandoned worker;
- **keep packet facts and packet policy apart.** A stall is terminal and exits 4
  with **no packet**, so every successful packet came from a run in which nothing
  stalled and no worker was abandoned. Residual-limit fields must therefore be
  named and worded conditionally — `backend_inference_lifetime_if_stalled`,
  `abandoned_worker_lifetime_if_supervisor_deadline_expires`, each opening from
  an explicit **IF** — never as a record of this run. What actually happened
  lives in `attempts[*].outcome` and `attempts[*].stall_source`. An earlier draft
  stated these as facts and made every ordinary success read as though a worker
  had been abandoned in it;
- **retry ownership is explicit and load-bearing.** The reviewer client is built
  with `max_retries=0`, **overriding** `AIDO_LITELLM_MAX_RETRIES` for this
  command only, so one semantic attempt is exactly **one** HTTP/model request.
  A supervisor deadline never creates another transport request. The generic
  `LLMClient` keeps its shipped transport retries **and its timeout semantics**
  for every other caller, and planner / smoke-test behavior is unchanged. **Do
  not globally change `LLMClient` retry or timeout behavior, or
  `AIDO_LITELLM_MAX_RETRIES` semantics**;
- **A STALL IS TERMINAL (FU1).** `LLMTimeoutError` **or** an expired AIDO
  deadline → `review_stalled` → `REVIEW STALLED` → reviewer unavailable. Both
  sources are the same outcome; they differ only in the audit-only
  `stall_source` field (`client_timeout` | `supervisor_deadline`), and nothing
  branches on it. **Never** issue a second request after a stall: AIDO's wait
  ending is not the request ending, and a second request could give the same
  local model two concurrent inference jobs and *increase* GPU, concurrency and
  context pressure. Do not sleep and guess the first job ended, do not add a
  backoff, do not poll, do not send a cancellation request, do not add streaming,
  and do not add Run:AI / LiteLLM-specific cancellation behavior. A stall may
  become retryable only in a future, separately authorized phase in which AIDO
  gains an observable, trustworthy backend-cancellation acknowledgement;
- **hard maximum of TWO semantic requests.** Not configurable, not reachable from
  a CLI flag. `RETRY_ELIGIBLE_OUTCOMES` is exactly
  `("review_output_budget_exhausted", "review_unusable_output")` — both are
  **completed** responses AIDO actually received, so the first request is no
  longer an unknown in flight. Timeouts, auth failures, non-retryable 4xx, 429,
  5xx, connection failures, the retry finding cap, and any already-valid review
  are all terminal;
- **the retry is a smaller review, not a repair.** Same configured model, a
  strict subset of the already-accepted transmission boundary (plan summary,
  proposed steps, risks and open questions dropped; no new source added), the
  same strict schema, and an extra post-parse cap of 5 findings enforced by
  rejection. Attempt 1's reply is discarded whole — never patched, never mined
  for partial findings, never quoted into attempt 2, never merged;
- three config fields with safe defaults (`attempt_timeout_seconds`,
  `max_output_tokens`, `compact_retry_on_unusable_output` — the last defaults to
  `false`), so every existing 5F2E config loads unchanged. The unaccepted draft
  name `compact_retry_on_stall` is **rejected**, never aliased;
- the packet carries a `reviewer_supervision` block. It was
  **`review-packet.v2`** when RS1 shipped; Phase 5F2E-V1 bumped it to
  **`review-packet.v3`** for reviewer provenance only, leaving every RS1
  supervision field and meaning exactly as accepted.

> **Do not describe RS1 as a hard wall-clock kill.** `attempt_timeout_seconds`
> bounds AIDO's *wait*, via AIDO's own monotonic deadline. **Never claim the
> request was cancelled, the worker stopped, or a backend stopped inference** —
> all three are outside this phase's observation boundary. State the chain
> exactly:
>
> ```text
> AIDO wait ended  !=  worker stopped  !=  request cancelled
>                  !=  backend inference stopped
> ```
>
> No multiprocessing, streaming, cancellation request, or thread-kill mechanism
> may be added to imply otherwise.
>
> **Name the failures accurately on stderr.** `REVIEW STALLED` is a **terminal**
> notice for a stall — from either source — and must never say "compact retry
> authorized". `REVIEW UNUSABLE — compact retry authorized` is for a
> completed-but-unusable response only. A parse error is never called a stall,
> and a run that stalled on its first attempt must report attempts used = 1.
>
> **`max_output_tokens` is a REQUESTED cap**, not a guarantee about hidden
> reasoning or backend accounting. Record the usage a provider actually reported;
> when none is supplied, report it as **unknown, never zero**.
>
> **Only supervise what is observable.** RS1 may classify on: response returned,
> typed client error, `finish_reason`, reported `usage`, empty/non-empty content,
> and strict-parser acceptance. It must **never** report or infer private
> reasoning, reasoning repetition or similarity, chain-of-thought,
> time-to-first-token, time-to-first-finding, tool calls, files the reviewer
> inspected, or tests the reviewer ran. This is *observable resource
> supervision*, not *agent-progress supervision*.

Do **not** add any of the following without an explicit, separate prompt: a
`fallback_model`, `reviewer_chain`, `reviewers` or `secondary_model` field;
automatic model failover (the deferred, **unauthorized** RS2 — it would send the
approved source-derived diff to another model); a third semantic attempt; a
configurable attempt count; a retry prompt in config; a CLI timeout/token
override; streaming or SSE; a backend cancellation call of any kind (LiteLLM,
Run:AI, or otherwise); a second worker, an executor, a worker pool, a worker
registry, a task framework, a process worker, or an asyncio migration; worker
tracking or cleanup infrastructure; or a generic metrics, event-bus, or
resource-policy framework. The **one** daemon worker per semantic attempt added
by FU2 is the entire concession, and it exists only so the main thread can stop
waiting.

> **A verdict is advisory and terminal.** All three verdicts end at a human.
> Never add a fixer, a second reviewer, a retry after findings, patch generation
> from findings, a file edit from findings, a revert or restore, a branch, a
> commit, a push, or a PR. (RS1's compact retry is not a counter-example: it
> exists only when a **completed** response carried no usable review at all,
> never to revisit a verdict that was produced.)
>
> **Scope claims truthfully here too.** This command *does* make a model/network
> call, and its verification stage *does* execute repository-controlled code — so
> a blanket `network_called: false` or `commands_run: false` is forbidden for the
> invocation. Keep the `orchestrator_` prefix, scope review-stage claims to the
> review stage, and leave child-process facts inside the embedded verification
> report.
>
> **Redaction is a backstop, not a guarantee.** Never write code or documentation
> claiming the transmitted material is secret-free.

Do **not** add any of the following without an explicit, separate prompt: a
model-backed implementer; a fixer; a review/fix loop; a second reviewer,
consensus, or voting; multiple reviewer models; full-file or repository-wide
transmission; multi-file review; a prompt audit file; a persistent review
database, queue, or background job.

## Role split

- **ChatGPT** = architect / planner / reviewer / prompt writer.
- **Claude Code** = implementation tool for this orchestrator project.
- Claude Code **must not broaden scope** beyond the current prompt. Do exactly
  what the active task asks — no speculative extras.

## Current non-goals

None of the following are implemented, and none may be added unless a future
prompt explicitly asks:

- No **GitHub writes**. Read-only issue inspection exists; nothing posts,
  labels, branches, commits, pushes, or opens a PR.
- No **general file editing engine**. The Phase 5F2C writer applies **one**
  approved `modify` diff to **one** tracked file and refuses everything else; it
  is not a general editor and must not grow into one here.
- No **command execution engine**. There is no shell anywhere, no command string,
  no chaining, no pipeline, no redirection, no install or package-manager action,
  and no model-proposed command. `required_verification` remains planner prose
  and is **never** command authority. Exactly two subprocess capabilities exist,
  and neither is a general executor: the Phase 5F2C writer's **fixed, read-only**
  Git inspection set, which is part of that writer's own correctness contract;
  and Phase 5F2D's single project-config-authorized verification invocation.
  Neither may grow into a general executor here.
- **Project verification execution exists, in exactly one narrow form.** Phase
  5F2D's `l2-verify-approved-file-edit` launches **one** absolute executable
  named by the `controlled_verification` opt-in (ships disabled), with an exact
  configured argv, once, bounded. It runs repository-controlled code by design —
  **controlled invocation, not a sandbox** — and must never claim otherwise.
- **Reviewer integration exists, in exactly one narrow form** (Phase 5F2E,
  supervised by 5F2E-RS1, with two selectable backends since 5F2E-V1), and it is
  the **only** role wired up. Two *providers* is not two *reviewers*: exactly one
  project-configured model reviews, over exactly one project-configured backend.
  There is **no fixer**, no review/fix loop, no second reviewer, no consensus, no
  fallback model, no provider failover, and no model-backed implementer. A reviewer verdict is advisory and ends
  at a human. The only application-level second model call anywhere is RS1's
  **one** bounded compact retry, which fires only after a **completed** response
  carried no usable review at all — never after a timeout, and never to revisit a
  verdict that was produced.
- No **agent logic** beyond that one reviewer role and its bounded attempt
  policy. RS1 is resource-budget supervision of a one-shot reviewer, **not** an
  agent-loop supervisor, and must not grow into one here.
- No LangGraph / CrewAI / AutoGen / n8n (no agent framework).

Real model calls exist only behind the three explicitly gated commands
(`real-llm-smoke-test`, `generate-model-plan`, `l2-review-approved-file-edit`);
nothing else may call a model, and no model output may ever select a path, a
command, an executable, or a file to change.

## Coding discipline

- One phase at a time.
- Do not implement future phases early.
- Tests are required for implementation phases.
- **Do not commit or push unless the user explicitly asks.** The user handles
  git commit and push manually.
- Prefer **fail-closed refusal of an unsupported case** over generalizing (see
  the design doc §27). Rejecting an input is a legitimate, preferred answer.
- Any test that exercises the writer, the verifier, or Git must use a **synthetic
  repository under pytest `tmp_path`**. Never test against a real target project.
  A verification test's program must likewise be a **synthetic script written
  under `tmp_path`**, never a real project executable.
- Any test that exercises the reviewer must use the existing mockable LiteLLM
  client path with `httpx.MockTransport`. **No real model call and no socket in
  the test suite**, and no API key is ever needed to run it.

## Safety principles

- **Workspace boundary enforcement is core** to this project.
- Model roles (implementer / reviewer / fixer) must be **configurable**.
- **No external paid AI API by default.** Internal LiteLLM is the intended
  default provider; OpenAI / Anthropic / Copilot / Codex are optional, future,
  and disabled by default.
- **Secrets must only come from environment variables** — never stored in files.
