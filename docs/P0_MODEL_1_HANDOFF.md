# P0-MODEL-1 — Qwen timeout path and MiniMax M3 as an independent candidate

| | |
|---|---|
| Kind | Implementation and review handoff (offline) |
| Recorded | 2026-11-23 |
| Baseline | `55239e1ac035e0c280ed309a6b55bace4f413d4f` |
| Lead engineer | Claude Code |
| Independent final reviewer | ChatGPT |
| Policy | [§13 P0-MODEL-1](AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md) |
| Status | **IMPLEMENTED offline, awaiting independent review.** Nothing committed, pushed or promoted. No live inference request was made. |

The endpoint host, the account name and any key are deliberately not written
here. Earlier evidence areas are named by their local folder only.

---

## 1. Summary

1. **The Qwen stalls come from a ~300 s response-start (or inactivity) limit in
   the serving path. They do not come from AIDO, and the serving path has no
   total-duration cap.**
   - Pi's **streaming** assistant messages to the same LiteLLM alias and the
     same backend pod often ran 300–783 s and completed. These durations are
     Pi's client-side stream lifetimes, not observed server-side HTTP request
     durations (§2.3, §10.1).
   - AIDO's **non-streaming** calls were cut at ~300 s and re-sent.
   - **While the ~300 s upstream cut is in place**, raising AIDO's 600 s
     deadline alone changes nothing, because the upstream cut comes first.
   - The smallest fix for the upstream cut is an administrator change: raise
     the non-streaming timeout at the hop that applies it, and stop retrying
     timeouts there.
   - **That fix alone does not guarantee success.** AIDO's own 600 s deadline
     then becomes the binding limit, so a generation that needs more than about
     600 s still stalls, and the stall is terminal (§2.5, §10.2). Until the fix
     lands, keep Qwen tasks small.
2. **`SUP-M3` = `minimax-m3` is a new, separately identified supervised
   implementer candidate.** The registry is append-only, `SUP-D` is
   byte-identical, and a mixed or variant identity is refused everywhere.
3. **The reviewer needed no source change** to use `minimax-m3`. It is an
   exact `controlled_review.model` string. New tests prove M3 review requests,
   strict rejection and coexistence with `gpt-oss-20b`.
4. **Offline regression**: see §6.

---

## 2. Part A — Pi versus AIDO, and the timeout

### 2.1 Sources (all read-only)

- Pi 1.6.0 configuration: `~/.pi/agent/models.json` and `settings.json`, read
  with the key masked.
- Pi's request builder, `pi-ai/dist/api/openai-completions.js`, in the installed
  package.
- Pi session metadata: model, duration, stop reason and reported usage only.
  No message content was read, and sessions named after the forbidden
  workspaces were skipped.
- AIDO's retained request evidence for all five live `qwen3.8-27b` implementer
  requests, as body keys and lengths only
  (`AIDO-p0correction2\evidence\08-request-shape-and-timing.txt`).
- The 2026-11-21 backend investigation
  (`AIDO-p0correction2\backend-investigation\FINDINGS.md`). Its Run:AI describe
  output and queue-proxy logs are re-read here, not re-fetched.
- One `GET /v1/models` to the existing LiteLLM proxy, for listing only (§4).

### 2.2 Effective wire parameters

| Parameter | Pi → `qwen3.8-27b` | AIDO SUP-D → `qwen3.8-27b` |
|---|---|---|
| Endpoint and alias | same LiteLLM base, alias `qwen3.8-27b` | same |
| Backend (per alias) | Run:AI `qwen3-8-27b`: vLLM v0.30.0, `Qwen3.8-27B-FP8`, `--reasoning-parser qwen3`, max-num-seqs 8 | same pod |
| **Streaming** | **`stream: true`**, `stream_options.include_usage` | **non-streaming** (field absent) |
| Request body keys | `model`, `messages`, `stream`, `stream_options`, `chat_template_kwargs`, `tools`, `max_completion_tokens` (when the agent passes a cap) | exactly `model`, `messages` |
| Thinking control | `chat_template_kwargs: {enable_thinking: true, preserve_thinking: true}` (`thinkingFormat: qwen-chat-template`). Pi's `xhigh` and `high` produce the same wire for this model. | none sent, so the template default applies |
| Output-token limit | model `maxTokens` 65536. The largest observed output was 62,473, consistent with a cap near 65,536, but this is not confirmed on the wire. | none (AIDO policy: no `max_tokens` by default) |
| Separate reasoning budget | none (no `thinking_token_budget` field for this compat) | none |
| Turn structure | multi-turn agent loop with tools; input up to ~130 k tokens | one system and one user message, 2.6–7.3 k characters |
| Client retries | SDK `maxRetries: 0`, plus Pi's own provider retry loop | 0, with AIDO's counting transport refusing a second request |
| Client wait | Node `undici` body timeout, 300 s of inactivity | AIDO's own 600 s deadline |
| Auth | Bearer key from Pi config; same proxy | Bearer key from `AIDO_LITELLM_API_KEY`; same proxy |

Whether the two keys are the same virtual key was not compared, because no
key value was inspected.

### 2.3 Durations

| | Pi streaming `qwen3.8-27b` | AIDO non-streaming |
|---|---|---|
| Successful turns longer than 300 s, all time | **61** (max **783 s**) | 0 |
| Same pod, after its 2026-11-16 20:04Z start | **9** (304–541 s), all completed | 2 requests, both cut at ~300 s |
| Successes | median 74 tok/s | 13, 112 and 192 s (all under 300 s) |
| Queue-proxy `context canceled` since pod start | none correlated with Pi | 5, all within ~1–3 s of an AIDO request's +300/+600/+900 s marks |

**What a "turn" is here.** Each row above is a Pi **assistant message**: one
`stream()` call. It is not a user turn, which can span many messages and tool
calls. The duration is Pi's own `durationMs`, measured client-side on
`performance.now()`. It runs from the creation of that message's event stream
to its `done` or `error` event, so it includes client set-up and connection time
as well as the stream itself. It is **not** a server-side HTTP request duration,
which no log observed. §10.1 explains why it is nonetheless a reasonable
stand-in for one streaming request, and where that stops.

One Pi assistant message (2026-11-19 22:46Z) failed after 306 s with the client-side error
`UND_ERR_BODY_TIMEOUT`. That is undici's own 300 s body-inactivity timeout. It
is a single event and is not explained here.

### 2.4 What is confirmed and what is inferred

**Confirmed** (by observation):
- AIDO sent exactly one request each time. Its counting transport forwards
  one request and refuses a second.
- Both AIDO stalls coincide with queue-proxy `context canceled` errors at ~300 s
  intervals. The sidecar logged no other such error since pod start.
  The link between each cancellation and each AIDO request is **temporal
  only**: it is not proven by a request ID, because vLLM v0.30.0 logs none.
- vLLM `Waiting` was 0 in every sample, so the requests were not queued.
- **Pi's streaming assistant messages through the same alias and pod lasted
  past 300 s, measured client-side, and completed** (§2.3). Pi's SDK makes no
  transport retries, and Pi records a retry as a separate message, so each such
  message most likely corresponds to one HTTP request that stayed open past
  300 s. That last step is an inference, not a server-side observation (§10.1).
  On that inference, nothing on the path imposes a ~300 s cap on the total
  duration of a **streaming** request.

**Inferred** (consistent with everything observed, not proven):
- The binding limit is a ~300 s limit on **time to the first response byte,
  or on inactivity**. A non-streaming completion sends no byte until it is
  finished, so it hits such a limit. A streaming one sends bytes continuously,
  so it never does.
- Two mechanisms fit equally well. Only an administrator can say which, or
  whether both apply:
  - (a) LiteLLM's per-deployment `timeout` for this model. It maps to an httpx
    timeout, and httpx timeouts are per-operation and inactivity-based.
  - (b) A Knative response-start style timeout. The workload's
    `requestTimeoutSeconds` is null, so the cluster default applies.
- The re-send at each +300 s is most likely LiteLLM's retry. That is the
  usual default for a timeout, and AIDO never re-sends. This is unproven.
  A third attempt (02:20→02:25Z) ran after AIDO had stopped waiting.
- Prompt size and stricter specs plausibly made the SemVer generations longer
  than 300 s. No token count was ever reported for the cut attempts. No
  hidden-reasoning share is derived from response characters versus
  completion tokens.

### 2.5 Recommendation (smallest reliable fix)

1. **Do not raise `attempt_timeout_seconds` first.** While the upstream ~300 s
   cut exists, a longer AIDO wait only waits longer for a request that has
   already been cut.
2. **Administrator fix (preferred).** Ask the LiteLLM administrator to:
   - read this model's `timeout`, `stream_timeout` and `num_retries`, and the
     router retry policy, for the two request times;
   - raise the non-streaming `timeout` for `qwen3.8-27b` **above** AIDO's
     deadline, for example 900 s against AIDO's 600 s, so the proxy is never
     the limit that ends a request AIDO is still waiting for;
   - set retries for **timeout** errors to 0, using `num_retries` or a retry
     policy with timeout retries set to 0.

   **Even then, success is not guaranteed.** AIDO's 600 s deadline becomes the
   binding limit: a generation that needs more than about 600 s before its
   response completes still ends in a terminal stall on the implementer path,
   with no retry (P1B: a stall is terminal). Whether SemVer-sized tasks finish under
   600 s is unknown, because none of the cut attempts was allowed to finish.
   See §10.2 for what the evidence does and does not say, and for the follow-up
   (a separate, PO-decided `attempt_timeout_seconds` value).

   If LiteLLM's value is already larger, the remaining suspect is Knative. Its
   fix is the workload's request timeout, which the workload owner can set,
   but it restarts the shared model (~10 min). A value above 600 s also needs
   the cluster's Knative maximum. The drafts in `FINDINGS.md` §6 still apply.
   Add the new Pi fact that streaming requests over 300 s succeed.
3. **Per-request retry suppression exists, but was not adopted.** The
   documentation shows LiteLLM accepting:
   - `x-litellm-num-retries`, since v1.109.0, documented to override body,
     deployment and global settings;
   - `x-litellm-timeout`, documented to take precedence over deployment
     timeouts.

   Neither was added. Both would change the consented request contract (a new
   header outside `request_sha256`, needing its own H2 disclosure). The
   proxy's version and whether it honours them are unknown: `/model/info` is
   403 and no `x-litellm-*` response header was observed. Adopting either needs
   a separate decision.
4. **Streaming is the evidence-backed AIDO-side alternative, and is not
   authorized.** It would avoid the response-start limit, but it changes the
   request contract, the evidence model and RS1's explicit "no streaming"
   rule. It needs its own design and authorization.
5. **Until one of these lands:** keep Qwen tasks small. Treat a Qwen stall as
   the known path limit, not a model failure.

---

## 3. Part B/C — what changed

### 3.1 Registry and configuration

```text
SUPERVISED_CANDIDATE_MODEL_IDS (append-only, read-only)
  SUP-D  -> qwen3.8-27b    unchanged
  SUP-M3 -> minimax-m3     new, separately identified
```

A project selects the M3 implementer only by naming both values:

```yaml
supervised_implementer:
  enabled: true
  live_transmission_enabled: true
  candidate: "SUP-M3"
  model: "minimax-m3"
  provider: "litellm"
  allow_insecure_http: true          # only if the endpoint is http; an acknowledgement, not security
  structured_output: false           # D-9 unchanged
  output_envelope: "delimited_file"  # optional; recommended after P0-RECOVERY
  attempt_timeout_seconds: 600
  authorization_ledger_dir: "<outside the workspace>"
```

The reviewer choice is the existing field, unchanged in kind:

```yaml
controlled_review:
  enabled: true
  provider: "litellm"
  model: "minimax-m3"      # or "gpt-oss-20b", which remains the operational default
  endpoint: { ... }        # from task-doctor, unchanged
```

There is no new CLI option, environment variable, alias, fallback or failover.

### 3.2 Source diff (summary; `git diff` is authoritative)

| File | Change |
|---|---|
| `supervised_implementer/identity.py` | `SUP-M3` constant; registry entry; widened `SupervisedCandidateId`/`SupervisedModelId` literals; `require_registered_candidate_pair()` |
| `supervised_implementer/models.py` | provenance v1 uses the registry literals and validates the pair |
| `supervised_implementer/live_authorization.py` | `AuthorizationBound` uses the registry literals and validates the pair |
| `supervised_implementer/live.py` | provenance v2 and `AidoRequested` use the registry literals; v2 validates the pair and `aido_requested.model == model` |
| `task/approve.py` | the H2 display names the bound candidate instead of a hard-coded `SUP-D` |
| `cli.py`, `models.py`, `supervised_implementer/__init__.py` | help text, docstrings, export of `SUPERVISED_CANDIDATE_M3_ID` |
| `tests/test_supervised_implementer.py` | the registry assertion now expects the two entries; `SUP-D`'s value is asserted separately |
| `tests/test_p0_model1_model_choice.py` | new (§5) |

What stays unchanged:
- every gate, phrase constant, schema version, golden digest, the ledger, the
  TTL, the transport wrapper and the strict parsers;
- the reviewer source;
- the coordinator's sequencing.

A `55239e1` (or older) reader refuses an `SUP-M3` authorization or provenance
record through its strict `Literal["SUP-D"]` rather than misreading it, so the
change fails closed across runtime versions. The official runtime is not
promoted by this phase.

The existing gate was already registry-driven (`unknown_candidate` /
`candidate_model_mismatch`). The existing `model_substitution` check already
rejects a reply naming another model. Neither needed changing.

### 3.3 Contract change

- Policy §13 (MOD-1 to MOD-3) is a prospective, append-only amendment.
- The documents directly affected were synchronized:
  - P1B implementation record §10 and its identity row;
  - coordinator §8 (the "implementer other than SUP-D" deferral is removed);
  - `CLAUDE.md`: one status bullet, one phase-table row and one identity
    sub-bullet. These need explicit PO approval to keep; §10.5 lists them
    exactly.
- No historical evidence or qualification record was edited.

---

## 4. MiniMax M3 deployment identity

| Fact | Evidence | Strength |
|---|---|---|
| LiteLLM advertises `minimax-m3` | `GET /v1/models` on 2026-11-23 lists `minimax-m3`, and separately `minimax-m3-thinking` | listing only; it is **not** inference proof |
| The alias serves completions | Pi session metadata, 2026-11-23: 146 streaming turns, all completed (141 `toolUse`, 5 `stop`), 0.3–81 s, median ~184 tok/s, `usage.reasoning` reported on every turn | operational, from Pi, not AIDO |
| Reasoning text placement | On those turns Pi recorded no thinking block and no `<think>` in the text, while the server reported reasoning tokens. Pi reads `reasoning`/`reasoning_content`/`reasoning_text` and does not strip inline tags, so streamed reasoning arrived in neither place. | inferred for non-streaming AIDO requests |
| Operator label | Pi config names it "MiniMax M3 NVFP4 (B300)", context 1,048,576, maxTokens 65,536, text and image input, `supportsReasoningEffort: false` | an operator label, **not** deployment evidence |
| Backend, weights, quantization, engine, reasoning parser, timeout and retry policy | not observed. `/model/info` is 403 for this key, and `runai workload list` failed because the CLI token has expired (re-login is the user's action) | **unknown** |

Remaining unknowns that matter for AIDO:
- whether `minimax-m3` and `minimax-m3-thinking` are one deployment with
  different defaults;
- whether a non-streaming reply ever carries inline `<think>` text. The
  strict parsers reject that by design, and the new tests pin it;
- whether the same ~300 s non-streaming limit applies. At the observed rate
  it would bind only very long generations.

---

## 5. Offline tests added (`tests/test_p0_model1_model_choice.py`, 45 cases)

| Claim | Tests |
|---|---|
| Registry append-only; `SUP-D` unchanged; read-only; `SUP-M3` outside `CANDIDATE_MODEL_IDS` | `test_the_registry_is_append_only…`, `test_the_frozen_autonomous_registry…` |
| Only exact pairs; mixed, variant and neighbour ids refused | `test_exact_registry_pairs…`, `test_mixed_or_variant_pairs…`, `test_the_gate_refuses_any_m3_substitution…`, `TestLive::test_prepare_refuses_a_mixed_pair…` |
| The selected pair is bound at H2 and is the requested model (JSON and delimited) | `TestLive::test_sup_m3_is_bound_at_h2…`, `…delimited_envelope`, `test_offline_sup_m3_request_and_provenance…` |
| No cross-candidate reuse of an authorization | `TestLive::test_an_authorization_for_sup_d_never_sends_for_sup_m3` and the reverse |
| Strict records refuse mixed pairs, even with a recomputed binding | `test_offline_provenance_refuses…`, `TestLive::test_the_authorization_record_refuses…`, `…live_provenance_refuses…`, `…edited_bound_identity…` |
| A reply naming another model is rejected, with no retry and no substitution | `TestLive::test_a_reply_naming_another_model_is_rejected_as_substitution` |
| An inline-`<think>` reply is rejected, never repaired | `TestLive::test_a_think_prefixed_json_reply…`, `TestReviewer::test_an_m3_envelope_violation…` |
| The reviewer requests the configured model; the env default never wins; packet `v5` records it; `gpt-oss-20b` still works | `TestReviewer::test_the_configured_reviewer_model…` |
| An M3 `changes_requested` verdict is preserved and ends at a human | `TestReviewer::test_an_m3_changes_requested…` |
| End to end, one implementer and one reviewer request each, and nothing automatic: SUP-M3 + gpt-oss-20b, and SUP-D + minimax-m3 | `TestCoordinatorPairings::test_one_task_end_to_end` |

`SUP-D` byte-identity is proved by the existing pinned golden tests, which were
not edited:
- the default config digest `c9c1fe63…`;
- the JSON and delimited system-instruction digests;
- the correction golden digests.

## 6. Offline regression result

Command (run offline; no network, no API key):

```text
.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

Result on the uncommitted working tree over `55239e1`:

```text
6140 passed, 1 warning in 9109.86s (2:31:49)
EXIT=0
```

- **No failures, nothing skipped or deselected.** The DL-4B S0 machine-DACL
  failure seen in an earlier phase did not recur on this run.
- **The one warning comes from an existing test, not from this change.**
  `test_a_post_load_forged_block_is_refused_by_revalidation` is in `HEAD`
  unchanged. It deliberately forges `enabled="yes"` to prove that revalidation
  refuses the forged value, and Pydantic warns while serializing that value.
- The new file `tests/test_p0_model1_model_choice.py` (45 cases) is included in
  the 6140.

---

## 7. Part D — minimal live acceptance (proposed; NOT executed)

Each item needs its own Product Owner authorization **and** the usual
H1/H2/H3 decisions. No model is both implementer and reviewer on the same task.

| # | Implementer | Reviewer | Precondition |
|---|---|---|---|
| L-1 | `SUP-M3` / `minimax-m3` | `gpt-oss-20b` | PO authorization |
| L-2 | `SUP-D` / `qwen3.8-27b` | `minimax-m3` | PO authorization **and** the Qwen timeout path is ready (§2.5 admin change confirmed), or a task small enough to finish well under 300 s |
| L-3 | none (human-authored seeded-defect diff) | `minimax-m3` | PO authorization; fixture frozen by SHA-256 before any request |

**Fixture.** Use the P0-CORR-2 `parse_version` fixture or an equivalent
disposable LF repository that is not an AIDO clone (HB-1). Its frozen suite
fails on the starter and passes on the reference.

**L-3 seeded defect.** Use one immutable `proposed-content.v1` whose code passes
a deliberately incomplete verification suite but contains one real defect, for
example accepting a leading-zero numeric identifier. The verification must
pass, or the reviewer is never reached. The expected verdict is
`changes_requested` with a finding on the defect line. `approve` is a recorded
miss, not a failure of AIDO.

**Record for each run:**
- implementation correctness against the frozen suite;
- the verification result;
- the reviewer verdict and whether it found the seeded defect;
- AIDO-observed `elapsed_seconds`;
- reported usage (unknown stays unknown);
- any stall and its `stall_source`.

### 7.1 Shortest safe commands (PowerShell; L-1 shown)

Set up the project config from §3.1, with reviewer model `gpt-oss-20b`, then:

```powershell
ai-dev-orchestrator task-doctor --project-config <cfg> --target-path <file>
```

```powershell
ai-dev-orchestrator task-start --project-config <cfg> --title "<title without (issue N)>" --issue <n> --target-path <file> --description-file <spec>
```

```powershell
ai-dev-orchestrator task-approve --run-dir <run>
```

```powershell
ai-dev-orchestrator task-continue --run-dir <run> --prepare-supervised-implementation
```

```powershell
ai-dev-orchestrator task-approve --run-dir <run>
```

```powershell
ai-dev-orchestrator task-continue --run-dir <run> --transmit-approved-source --real-implementer
```

```powershell
ai-dev-orchestrator task-approve --run-dir <run>
```

```powershell
ai-dev-orchestrator task-continue --run-dir <run> --apply-approved-plan --write-approved-file --verify-approved-file-edit --real-reviewer
```

The steps, in order:
1. H1: approve the plan.
2. Run prepare (offline).
3. H2: consent. Type the endpoint yourself, then `transmit`, then
   `plaintext` if the endpoint is http.
4. Send the one implementer request. **This is the live call.**
5. H3: approve the exact diff.
6. Write, verify, then send the one review request. **This is the second live
   call.**

L-2 is the same sequence with `candidate: SUP-D`, `model: qwen3.8-27b` and
reviewer `minimax-m3`. L-3 uses the existing direct commands, in this order:
`l2-read-workspace-files`, `generate-diff-proposal --generate-diff`, the human
5F0 approval edit, `l2-apply-approved-file-edit --apply-approved-plan
--write-approved-file`, then `l2-review-approved-file-edit
--verify-approved-file-edit --real-reviewer`. Only the last makes a model
call.

Set `PYTHONIOENCODING=utf-8` when capturing output. Expect the coordinator's
pinned config digest to refuse any config edit after `task-start`.

---

## 8. Blocked on someone else

| Item | Who | Why |
|---|---|---|
| The `qwen3.8-27b` LiteLLM `timeout`/`num_retries`/retry policy, and logs for the two requests | LiteLLM administrator | the key is limited to the API routes (`/model/info` 403) |
| Knative `revision-timeout-seconds` / `max-revision-timeout-seconds` and any ingress response-start timeout | Run:AI cluster administrator | cluster setting |
| Raising the workload request timeout | the workload owner, after a PO decision | restarts a shared model |
| `minimax-m3` backend identity (weights, quantization, reasoning parser) | LiteLLM or Run:AI administrator, or re-login to the Run:AI CLI | token expired; `/model/info` 403 |
| Proxy version and support for `x-litellm-num-retries` | LiteLLM administrator | not observable with this key |

Nothing in this phase changed LiteLLM, Run:AI or cluster settings.

## 9. Sources

- LiteLLM request headers:
  https://docs.litellm.ai/docs/proxy/request_headers
- LiteLLM timeouts: https://docs.litellm.ai/docs/proxy/timeout
- Knative-based request timeout (Google Cloud):
  https://docs.cloud.google.com/kubernetes-engine/enterprise/knative-serving/docs/configuring/request-timeout

---

## 10. Responses to the independent-review request (2026-11-23)

These answers come from the existing implementation and evidence. No code was
changed for them, the full suite was not re-run, and no model was contacted.
§1, §2.3, §2.4, §2.5 and §3.3 were corrected in place to match.

### 10.1 A Pi message over 300 s is not a measured HTTP request over 300 s

There are three different measurements, and only the first was observed:

| Measurement | Observed? | Source |
|---|---|---|
| **(a) Pi assistant-message lifetime.** One `stream()` call, from creation of its event stream to its `done` or `error` event, on the client's monotonic clock. | **Yes** | `durationMs` in Pi's session records (pi-ai `AssistantMessageEventStream`) |
| **(b) The client-side HTTP request lifetime.** The socket request inside that stream. | **No** | inferred from (a) |
| **(c) The server-side request duration** at LiteLLM, Knative or vLLM | **No** | no request-ID log exists (vLLM v0.30.0 logs none) |

Why (a) is a reasonable stand-in for (b), and where that stops:

- Pi's OpenAI SDK client runs with `maxRetries: 0`, so one `stream()` call
  issues one HTTP request from Pi's side.
- Pi's own retry loop (`agent-session.js`) acts on a message that has
  **already ended** with `stopReason: "error"`, and then starts a new one. A Pi
  retry therefore never inflates a *successful* message's `durationMs`.
- (a) includes client set-up, connection and post-stream time, so it can only
  overstate (b), by a small amount.
- (a) cannot see a **proxy-side** retry. If LiteLLM had retried upstream before
  the first byte, one Pi request would span two upstream requests. That cannot
  be excluded. It would not change the conclusion, because the request Pi held
  still stayed open past 300 s and completed.

**So the defensible statement is narrower than "an HTTP request exceeded
300 s".** Pi held one streaming request open past 300 s, measured client-side,
and it completed; no server-side duration was measured. That is enough to
rule out a hard ~300 s cap on the total duration of a **streaming** request on
this path. It is **not** enough to identify the mechanism that cuts
non-streaming requests. That mechanism stays inferred (§2.4).

### 10.2 A 900 s proxy timeout alone cannot guarantee success

- AIDO's live implementer waits at most `attempt_timeout_seconds` (600 s
  configured) on its own monotonic deadline. A stall at that deadline is
  **terminal**: one request per authorization, no retry, and no proposal.
- With the proxy timeout raised to 900 s and its timeout retries at 0, the
  proxy no longer ends requests that AIDO is still waiting for. AIDO's 600 s
  deadline then becomes the binding limit.
- A non-streaming generation succeeds only if the complete response arrives
  within about 600 s, with connection and proxy overhead counted.
- The evidence does not show that this holds for the stalled tasks:
  - AIDO's completed Qwen requests took 13, 112 and 192 s.
  - The SemVer attempts were cut at about 300 s and never allowed to finish, so
    their true generation time is **unknown**.
  - At least one Pi streaming message ran 783 s. That is not comparable work,
    but it shows the model can run longer than 600 s on this backend.
- The proxy value must be **strictly greater** than AIDO's deadline. A value
  equal to it lets the two limits race. A value below it recreates today's
  failure.
- Raising AIDO's deadline is a project-config change to
  `supervised_implementer.attempt_timeout_seconds`. That value is bound into
  the H2 authorization, so it would take effect only through a new per-run H2.
  If the PO wants it, it is a separate decision, and it should be made
  **after** the proxy fix. It must keep the proxy timeout above it, and it
  inherits the RS1-style caveat: AIDO's wait ending is not cancellation, and
  the backend may keep generating after AIDO stops waiting.
- **Recommended order:**
  1. The administrator fixes the proxy timeout and sets timeout retries to 0.
  2. Run L-2 with a small task under the unchanged 600 s deadline.
  3. Only if a task that matters still needs longer, the PO decides a new
     `attempt_timeout_seconds` below the proxy value.

### 10.3 Identity validation in every authorization, provenance, offline and live path

Every place a supervised candidate or model enters, is recorded or is compared:

| Path | Location | Validation |
|---|---|---|
| Project config gate (offline runner, `prepare`, `run`) | `supervised_implementer/implementer.py` gate (unchanged; registry-driven) | `type is str`. A candidate not in the registry refuses `unknown_candidate`. A model that is not the registry's model for that candidate refuses `candidate_model_mismatch`. Both refuse before any read or request. |
| Wire request | `live.py` / `implementer.py` request build | The model is the gated `settings.model`. `request_sha256` binds the exact payload, model included. |
| Authorization record (H2), `AuthorizationBound` | `live_authorization.py` `candidate`/`model` fields and `_binding_and_expiry_agree` | Strict `Literal` (`SUP-D`/`SUP-M3`, `qwen3.8-27b`/`minimax-m3`). `require_registered_candidate_pair` runs first, so a mixed pair is refused **even with a recomputed `binding_sha256`**. |
| Authorization against the current project at `run` | `live.py` `_bound_mismatches` | Bound `candidate`, `model` and `provider` (and every other bound field) must equal the gated config, or the run refuses `authorization_mismatch` and sends nothing. Tested both ways: a SUP-D authorization never sends for SUP-M3, and the reverse. |
| Model reply | `implementer.py` `model_substitution` (unchanged; shared by offline and live) | A reply whose `model` differs from the requested model is rejected, never accepted. Tested with `qwen3.8-27b` and `minimax-m3-thinking` replying to an M3 request. |
| Offline provenance v1 | `supervised_implementer/models.py` | Strict `Literal` plus the pair validator. |
| Live provenance v2 and `aido_requested` | `live.py` `SupervisedImplementerLiveProvenance`, `AidoRequested` | Strict `Literal`, the pair validator, and `aido_requested.model == model`. |
| Correction round 2 | `task/correction.py` `BASELINE_FIELDS` (unchanged) | `candidate` and `model` must repeat round 1 exactly, so a correction round cannot switch candidates. |
| H2 display (`task-approve`) | `task/approve.py` | Display only; it now prints the bound candidate. The decision binding is unchanged, and the strict parser still decides. |
| stderr transmission banner | `live.py` `LiveTransmissionNotice` | Display only. It is typed `str` and filled from the already-gated settings, never parsed back as authority. |

**Historical compatibility:**

- Each widened `Literal` is a strict superset of the old `Literal["SUP-D"]` and
  `Literal["qwen3.8-27b"]`. `SUP-D` with `qwen3.8-27b` remains a registered
  pair.
- No field was added, renamed or removed, and no schema version changed, so a
  SUP-D record serializes as before.
- The unchanged golden request digests in `test_supervised_implementer*.py`
  pass, for both the default and the delimited envelope. So the SUP-D request
  bytes are unchanged.
- A `55239e1`-or-older reader refuses a `SUP-M3` record through its strict
  literal. Old runtimes fail closed and never misread one.
- **Not done:** re-parsing real archived run records under
  `%LOCALAPPDATA%\AIDO\runs` or the earlier evidence folders. They are outside
  this session's workspace boundary. Compatibility rests on the type argument
  above and the in-repo tests that load SUP-D records. A reviewer who wants
  direct proof can load an archived authorization and provenance with the
  candidate runtime.

### 10.4 Choosing MiniMax M3 as reviewer does not weaken the strict parser

- **No reviewer source changed.** `git status` and `git diff` are empty for
  `src/ai_dev_orchestrator/review/` (which holds `parse_model_review_response`),
  for `llm/` and for `verification/`. The reviewer prompt, the generated JSON
  schema, RS1 supervision and the egress checks are byte-identical to `55239e1`.
- `controlled_review.model` was already a free, exact string. Nothing in the
  parser depends on the model's name.
- New tests run the unchanged parser against M3-style output:
  - a markdown-fenced reply, and a `<think>…</think>` prefix with or without a
    blank line, are each rejected with exit 4 after exactly one request, with
    no packet;
  - a valid `changes_requested` reply is preserved as given, and ends at a
    human;
  - the configured model wins over `AIDO_LITELLM_DEFAULT_MODEL`, and the
    packet stays `review-packet.v5`.
- If a project enables `compact_retry_on_unusable_output`, a rejected M3 reply
  is a **completed but unusable** response. Under the unchanged RS1 policy it
  may get the one compact retry. That is the existing behavior for every
  model, not something M3 adds.
- **Disclosed residual, unchanged and not introduced here.** The reviewer does
  not compare the reply's own `model` field with the requested model, unlike
  the implementer's `model_substitution` check. The packet records what AIDO
  **requested**. Because `minimax-m3-thinking` is advertised beside
  `minimax-m3`, a proxy misroute would not be detected by the reviewer. Adding
  such a check would be a reviewer-contract change and needs its own decision.

### 10.5 `CLAUDE.md` changes (keeping them needs explicit PO approval)

Exactly three additions; nothing in `CLAUDE.md` was removed or reworded. They are
shown here as the unified diff against `55239e1`:

```diff
@@ -101,6 +101,11 @@ before doing any work here.
   `json_content_text` stays byte-identical; `delimited_file` is opt-in by
   project config. See "What the supervised implementer can and cannot do"
   below.
+- **P0-MODEL-1 appended a second, separately identified supervised candidate**,
+  `SUP-M3` = `minimax-m3` (policy §13). It also proved that the reviewer
+  accepts an explicitly configured `minimax-m3`. It is implemented offline and
+  awaits independent review. `SUP-D` is byte-identical, and nothing selects,
+  substitutes or fails over between models.
 - **The first controlled write → verify → supervised review → human path now
@@ -122,6 +127,7 @@ ALPHA-2A-T1    Single-File Task Coordinator         IMPLEMENTED (awaiting review
 ALPHA-2B-T1    One Human-Supervised Correction Round IMPLEMENTED (awaiting review)
 P0-UX1-T1      Interactive Human Approval (D-2′)    ACCEPTED (offline scope)
 P0-RECOVERY-T2 Optional Plain-Text Reply Envelope   IMPLEMENTED (awaiting review)
+P0-MODEL-1     SUP-M3 Candidate + M3 Reviewer Choice IMPLEMENTED (awaiting review)
 → bounded write → verify → supervised review → human
@@ -625,6 +631,14 @@ authorized.
   `qwen3.8-27b`. It is outside `CANDIDATE_MODEL_IDS`, earns **no** qualification
   credit in either direction, and is not Candidate D's autonomous
   qualification. Never imply that Qwen 3.8 is qualified.
+- **A second candidate (P0-MODEL-1, policy §13).** The registry is
+  append-only and also holds `SUP-M3` = exactly `minimax-m3`, with the same
+  zero credit. A project names exactly one pair, `candidate` **and** `model`.
+  - A mixed pair is refused at the gate and by every strict record.
+  - H2 and `request_sha256` bind the pair.
+  - A reply naming another model is rejected as `model_substitution`.
+  - Never add an alias, an automatic choice, a fallback or failover between
+    candidates, or a CLI model option.
```

- **C-1, status bullet** (after the P0-RECOVERY-T2 bullet): records the phase
  and its non-failover property.
- **C-2, phase-table row**: `IMPLEMENTED (awaiting review)`.
- **C-3, identity sub-bullet** (under "What the supervised implementer can and
  cannot do"): the operating rule a future Claude Code session must follow.

If the PO declines any of them, revert only `CLAUDE.md`. No code or test depends
on its text. The review package carries both `CLAUDE.md` versions and this diff
as `CLAUDE.md.diff`.
