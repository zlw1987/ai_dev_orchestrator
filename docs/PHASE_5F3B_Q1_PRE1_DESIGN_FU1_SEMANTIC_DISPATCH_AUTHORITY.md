# Phase 5F3B-Q1-PRE1-DESIGN-FU1 — Semantic Dispatch Authority + Indeterminate Evidence Contract

> **DESIGN / SOURCE INSPECTION ONLY. NOTHING WAS IMPLEMENTED IN THIS TURN.**
>
> No runtime module was modified. `semantic_session.py`,
> `semantic_controller.py`, `semantic_sweep.py`, `semantic_workspace.py` and
> every test file are byte-identical to how this turn found them. No frozen
> qualification module was touched. **No semantic prompt was sent, no Pi/Node
> process was launched, no credential was read, no socket was opened, no
> candidate was run, and B300 was not contacted.** Q1 and Q2 were not run.
> Nothing was committed, pushed, or opened as a PR. `CLAUDE.md` was not
> modified.
>
> **Standing status is unchanged by this document.** No model qualification
> has occurred. No candidate implementer PASS/FAIL exists. Candidate A and
> Candidate B are Category-B **compatibility** qualified/frozen only.
> **5F3B-Q1: NO-GO. 5F3B-Q2: NO-GO. Real-workspace authority: NO-GO.**

> **FU1A ADDENDUM (5F3B-Q1-PRE1-DESIGN-FU1A). DESIGN DOCUMENTATION ONLY —
> NOTHING WAS IMPLEMENTED IN THIS TURN EITHER.** Independent review accepted
> §0–§8 above in direction and found four additional gaps between them and
> the actual, already-implemented source of `semantic_workspace.py`,
> `semantic_controller.py`, `semantic_sweep.py`, `safety.py`,
> `i2_secret_context.py` and `i2b_workspace.py` — none of which this turn
> modified, launched, or executed. §9 adds and freezes the four missing
> contracts (semantic workspace ownership and verified removal; the full
> artifact safety context; the final assistant report's optional/untrusted
> status; and deep result/sweep immutability); §10 is the adversarial
> check. **No runtime module was modified, no test was modified, no
> Pi/Node process was launched, no credential was read, B300 was not
> contacted, and Q1/Q2 were not run.** `5F3B-Q1-PRE1-DESIGN-FU1` moves from
> `READY FOR INDEPENDENT REVIEW` to **`HOLD pending FU1A review`** — see the
> updated §8 Verdicts.

---

## 0. What this document is, and what it is answering

Independent review returned:

```text
5F3B-Q1-PRE1-FU1                      HOLD
5F3B-Q1-PRE1                          HOLD
Q1 / Q2 / real-workspace authority    NO-GO
```

FU1's introduction of a **three-state** semantic dispatch fact —

```text
CONFIRMED_NOT_SENT | CONFIRMED_SENT | SEND_STATE_INDETERMINATE
```

— was the right correction. Two things about it were not established, and this
document establishes them from source rather than from convention:

1. **Is the FU1 architecture faithful to the real Pi seam?** FU1 embeds the
   dispatch fact *inside* the whole-turn observation, so the send/no-send truth
   only exists if the entire turn adapter returns normally. §2 shows, from Pi's
   own source and from AIDO's own frozen supervisor, that this is **not**
   faithful: the real seam has an acknowledgement boundary that is strictly
   earlier than turn completion, and several reachable post-acknowledgement
   failures cannot be represented by the current type at all — forcing the
   adapter either to lie or to erase an already-established `CONFIRMED_SENT`.
2. **What evidence exists when the send state is indeterminate?** FU1 answers
   "`semantic_prompts_sent = None`, and no primary record is emitted." §3 shows
   that "no primary record" is currently implemented as **no artifact at all**,
   which is the more serious defect: an attempt that may already have spent the
   candidate's one authorized prompt currently leaves nothing immutable behind.

Everything below is derived from the files named in §1.1 and §1.2. Where a fact
is *not* mechanically establishable, this document says so and does not invent
an acknowledgement, event, or field that Pi does not expose.

---

## 1. OBJECTIVE 1 — the real Pi semantic-dispatch seam

### 1.1 Pi source inspected (locally installed runtime)

Package root: `@earendil-works/pi-coding-agent`, installed under the npm global
`node_modules` next to the `pi` shim that `ar2.launch._resolve_pi_package_root`
itself resolves. `package.json` reports **version `0.84.4`** — the same version
observed in every accepted Category-B live attempt. The seam facts below are
read from that tree, not from a changelog and not from `pi --help`.

| # | File | What it established |
|---|---|---|
| 1 | `dist/modes/rpc/rpc-types.d.ts` | The complete `RpcCommand` union, the complete `RpcResponse` union, and the exact response shape for `command: "prompt"` |
| 2 | `dist/modes/rpc/rpc-mode.js` | The stdin line loop, `handleCommand`, the `prompt` case, the `success`/`error`/`output` helpers, the parse-failure path, the event-forwarding subscription |
| 3 | `dist/modes/rpc/jsonl.js` | LF-only framing, single trailing `\r` strip, and the end-of-stream flush of a trailing partial line |
| 4 | `dist/modes/json-event.js` | `toJsonEvent` — which session events reach stdout, and in what shape |
| 5 | `dist/core/agent-session.js` | `AgentSession.prompt()` — every `preflightResult` call site; `_runAgentPrompt`; the single `_emitAgentSettled` call site; `_emitExtensionEvent` |
| 6 | `dist/core/agent-session.d.ts` | The `AgentSessionEvent` union — `agent_end` (with `willRetry`) and `agent_settled` |
| 7 | `node_modules/@earendil-works/pi-agent-core/dist/types.d.ts` | The core `AgentEvent` union, including `agent_start` |
| 8 | `node_modules/@earendil-works/pi-agent-core/dist/agent.js` | `Agent.prompt` / `Agent.continue` / `runPromptMessages` |
| 9 | `node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js` | The two `emit({type:"agent_start"})` sites, and that the provider call happens inside `runLoop` **after** them |
| 10 | `package.json` | Observed version `0.84.4` |

### 1.2 AIDO-side source inspected

Frozen / accepted (read only, not modified):
`experiments/pi_external_runtime_ar2/ar2/supervisor.py`, `ar2/protocol.py`,
`ar2/wire.py`, `ar2/launch.py`, `ar2/pi_config.py`, `ar2/handshakes.py`,
`experiments/pi_external_runtime_ar2/extension/index.ts`.

Qualification package: `qualification/semantic_session.py`,
`qualification/semantic_controller.py`, `qualification/semantic_sweep.py`,
`qualification/records.py`, `qualification/validity.py`,
`qualification/outcomes.py`, `qualification/lineage.py`,
`qualification/safety.py`, `qualification/i2_cleanup.py`,
`qualification/i2b_live_adapters.py`.

Design authority: `docs/PHASE_5F3B_PI_IMPLEMENTER_QUALIFICATION_DESIGN.md`
(§9, §10, §11.5, §15.1, §17.2, §17.3, §26) and
`docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md` (§7.1, §19).

### 1.3 Q1 — the exact RPC command that starts the semantic task turn

```json
{"id": "<AIDO-owned id>", "type": "prompt", "message": "<the frozen task prompt>"}
```

`type: "prompt"` is the **only** member of Pi 0.84.4's `RpcCommand` union that
begins a new semantic turn from an idle session. Its siblings are not
substitutes and must not be used here:

- `steer` and `follow_up` **queue into an already-streaming turn**; from an idle
  session they are not a task start.
- `bash` executes a shell command in Pi's own executor — categorically
  forbidden by this project's no-command-execution rule.
- every other member (`get_state`, `get_commands`, `set_model`, `compact`,
  `abort`, the session/tree/export family) is non-semantic and triggers no
  inference.

The command is written as **one LF-terminated JSON line** on Pi's stdin. AIDO's
existing frozen writer is `ar2.supervisor.PiRpcSupervisor.send_command`, which
does exactly `json.dumps(command, ensure_ascii=True).encode("utf-8") + b"\n"`,
then `write()` then `flush()`.

`id` is optional in Pi's schema (`id?: string`). **For this phase it is
mandatory on AIDO's side**: without it Pi's `success(id, "prompt")` helper
produces `{id: undefined, ...}`, `JSON.stringify` drops the key, and the
response becomes uncorrelatable — which would collapse `CONFIRMED_SENT` into
`SEND_STATE_INDETERMINATE` for every run.

### 1.4 Q2 — is there an ordinary correlated response? **Yes.**

`dist/modes/rpc/rpc-types.d.ts` declares it explicitly:

```ts
{ id?: string; type: "response"; command: "prompt"; success: true }
```

and the failure arm of the same union:

```ts
{ id?: string; type: "response"; command: string; success: false; error: string }
```

So a `prompt` command has a genuine, id-correlated, two-valued acknowledgement.
**This is a real seam, not an invention**, and it is the seam the two-phase
contract in §2 is built on.

### 1.5 Q3 — when is that response emitted?

`rpc-mode.js`'s `prompt` case is unlike every other command: it returns
`undefined` from `handleCommand` (so the generic "output the returned response"
path never fires for it) and instead attaches the acknowledgement to a callback:

```js
case "prompt": {
  // Start prompt handling immediately, but emit the authoritative response only after
  // prompt preflight succeeds. Queued and immediately handled prompts also count as success.
  let preflightSucceeded = false;
  void session.prompt(command.message, {
      images: command.images,
      streamingBehavior: command.streamingBehavior,
      source: "rpc",
      preflightResult: (didSucceed) => {
        if (didSucceed) { preflightSucceeded = true; output(success(id, "prompt")); }
      },
    })
    .catch((e) => { if (!preflightSucceeded) { output(error(id, "prompt", e.message)); } });
  return undefined;
}
```

`AgentSession.prompt` (`dist/core/agent-session.js`) calls `preflightResult`
exactly once, at one of five sites. Four are `true`; one is `false`:

| Site | Condition | Reached the model? | Session mutated? |
|---|---|---|---|
| `preflightResult?.(true)` — extension slash-command | `text.startsWith("/")` and an extension command of that name exists and ran | **No** | extension-defined |
| `preflightResult?.(true)` — extension `input` handler returned `handled` | only if some extension registered an `input` handler | **No** | extension-defined |
| `preflightResult?.(true)` — queued | `this.isStreaming` is true; message queued via `_queueSteer` / `_queueFollowUp` | **Not yet** | queue only |
| `preflightResult?.(true)` — **the real path** | after model validation, auth resolution, compaction check, user-message construction and `before_agent_start` | **About to be**; the very next statement is `await this._runAgentPrompt(messages)` | user message built, not yet handed to the agent run |
| `preflightResult?.(false)` | the `catch` around all of the above, immediately before rethrow | **No** | nothing appended |

**Ordering, exactly:**

```text
AIDO write+flush of one LF-terminated line
  -> Pi jsonl reader emits the line (LF only; a trailing \r stripped)
  -> JSON.parse                       [failure here => uncorrelated parse response]
  -> handleCommand switch, case "prompt"
  -> session.prompt(...) begins
  -> PREFLIGHT decision
       -> success: output({type:"response",command:"prompt",id,success:true})   <-- THE ACK
       -> failure: output({type:"response",command:"prompt",id,success:false})  <-- THE REFUSAL
  -> (real path only) _runAgentPrompt -> agent.prompt -> runAgentLoop
       -> emit agent_start
       -> emit turn_start, message_start/message_end for the prompt
       -> runLoop  ->  FIRST PROVIDER INFERENCE REQUEST
       ...
       -> agent_end (possibly repeatedly; may carry willRetry)
  -> finally: _emitAgentSettled -> emit agent_settled
```

So the acknowledgement is emitted **after** parsing and acceptance, and
**strictly before** agent start and before any provider inference. It is
therefore a genuine *dispatch* acknowledgement, not a turn-completion signal.

**A `success: false` prompt response is a strong negative.** It can only be
produced by the `catch` in `AgentSession.prompt`, whose scope ends before
`_runAgentPrompt`; nothing was handed to the agent loop, no user message was
appended to the run, and no provider request was made. Its realistic causes are
exactly §11.5 infrastructure shapes: no model selected, no configured auth for
the provider, or a compaction in progress.

**A `success: true` prompt response is deliberately NOT read here as "the model
received the task".** Three of its four branches do not reach a model at all. It
is read as the weaker, sufficient fact: **Pi accepted and consumed AIDO's one
authorized semantic command.** That is the conservative reading, and it is the
right one for a one-shot fairness budget: in every one of the four branches the
task prompt was delivered into the session and cannot be un-delivered.

For completeness, the three non-model branches are excluded by construction in
this route — and their exclusion is argued from AIDO-owned artifacts, never from
a per-run Pi observation that does not exist:

- *extension slash-command*: gated on `text.startsWith("/")`. The frozen corpus
  prompt text is AIDO-owned and inspectable; a dispatch adapter can assert it.
- *extension `input` handler*: `hasHandlers("input")` is false because AIDO's one
  loaded extension (`experiments/pi_external_runtime_ar2/extension/index.ts`)
  registers exactly two tools and one inert command and **no** `input` or
  `before_agent_start` handler, launched under `--no-extensions` with
  `settings.json`'s `extensions: []`.
- *queued*: requires `isStreaming`, impossible on the first and only prompt of a
  fresh session.

These are stated as **design assumptions backed by AIDO-owned source and
config**, not as per-run mechanical observations, and §2.4 records them as such.

### 1.6 Q4 — is there an `agent_start`, and what does it prove?

**Yes.** `agent_start` is a member of the core `AgentEvent` union
(`pi-agent-core/dist/types.d.ts`), it is forwarded verbatim to stdout by
`rpc-mode.js`'s `session.subscribe((event) => output(toJsonEvent(event)))`, and
`toJsonEvent` passes through everything except `message_update` unchanged.

`agent-loop.js` emits it at the top of **both** `runAgentLoop` and
`runAgentLoopContinue`, before `runLoop` — i.e. before the first provider call of
that loop.

**What `agent_start` proves:** an agent loop was entered for this session. Since
`_runAgentPrompt` is the only path that reaches `agent.prompt`/`agent.continue`
in RPC mode, and `_runAgentPrompt` is only reached from the *real* preflight-true
branch, **observing `agent_start` is independent proof that the semantic prompt
was accepted and the turn began.**

**What `agent_start` does NOT prove:** it is not one-per-prompt.
`_runAgentPrompt` runs
`for (await agent.prompt(m); await _handlePostAgentRun();) await agent.continue()`,
and `runAgentLoopContinue` emits `agent_start` again on each continuation
(auto-retry, compaction continuation, queued-message drain). **`agent_start`
count is not a prompt count and must never be used as one** (see §4).

### 1.7 Q5 — what does a successful complete JSONL write/flush prove?

**Only local transport issuance.** Concretely, after `send_command` returns
without raising, AIDO knows:

- Python's buffered writer accepted the payload and `flush()` did not raise, so
  the bytes were handed to the OS pipe;

and AIDO does **not** know:

- whether Pi's process was alive to read them;
- whether Pi's `attachJsonlLineReader` framed a complete line from them;
- whether `JSON.parse` succeeded;
- whether `handleCommand` reached the `prompt` case;
- whether preflight ran, succeeded, or failed.

**A successful write is therefore evidence of neither `CONFIRMED_SENT` nor
`CONFIRMED_NOT_SENT`.** It is the canonical `SEND_STATE_INDETERMINATE`
precursor: the state stays indeterminate until a Pi-side observation resolves it.

A *failed* write is likewise not proof of not-sent. `send_command` writes
`payload = json + b"\n"` in one `write()` call on a `BufferedWriter`; an
`OSError` from `write()` or from `flush()` does not tell AIDO how many bytes
reached the pipe. It is tempting to argue "the LF is the last byte, so a partial
write means Pi never framed a line" — that argument fails for a `flush()` error
after a fully-buffered `write()`, and this design does **not** rely on it. A
write/flush exception is `SEND_STATE_INDETERMINATE` unless a Pi-side observation
resolves it.

### 1.8 Q6 — which of the five states can AIDO mechanically distinguish?

| State | Mechanically observable? | The observation |
|---|---|---|
| definitely not issued | **Yes** | AIDO's own dispatch gate refused before `send_command` was entered. AIDO-owned control flow; needs no Pi cooperation |
| definitely issued (locally) | **Yes** | `send_command` returned without raising. Proves issuance onto the pipe **only** — §1.7 |
| accepted by Pi | **Yes** | A correlated `{"type":"response","command":"prompt","id":<ours>,"success":true}` record. Its negation, `success:false`, is equally observable and is positive proof of **not** accepted into a turn |
| agent started | **Yes** | An `agent_start` record after dispatch. Also implied by any `turn_start` / `message_*` / `tool_execution_*` / `agent_end` / `agent_settled` record |
| semantic turn completed | **Yes** | An `agent_settled` record. `_emitAgentSettled` has exactly **one** call site — `_runAgentPrompt`'s `finally` — so `agent_settled` cannot be produced by any non-turn path in RPC mode |

Two things in this list are **intentionally unobservable and must not be
manufactured**:

- **There is no acknowledgement between "AIDO flushed the bytes" and "Pi emitted
  a response".** Pi exposes no receipt, no echo, no sequence number, and no
  stdin-drain signal. The gap in §1.7 is a real property of the seam.
- **There is no per-provider-request observability.** `agent_end` may repeat,
  `auto_retry_*` and `compaction_*` exist, but no AIDO-visible record maps
  one-to-one onto a provider HTTP request (see §4).

### 1.9 Q7 — a pipe/read exception AFTER a successful write

**Surviving authoritative fact: `send_command` returned — the command was issued
onto the pipe. Nothing more.**

The failure is on AIDO's *reading* side (`RecordStreamReader.read_error`,
`protocol_violation`, `byte_cap_exceeded`, `record_cap_exceeded`) or is a child
exit (`RUNTIME_EXITED_EARLY`). None of these say anything about whether Pi
consumed and acted on the line — Pi may be running the turn right now with
AIDO's stdout view broken.

Dispatch state: **`SEND_STATE_INDETERMINATE`**. It is *not* `CONFIRMED_NOT_SENT`
(the prompt may be executing) and *not* `CONFIRMED_SENT` (no Pi-side observation
was ever obtained).

### 1.10 Q8 — a failure AFTER a correlated acceptance but BEFORE `agent_settled`

**Surviving authoritative fact: `CONFIRMED_SENT`, permanently.**

The acknowledgement in §1.4/§1.5 already happened and was already read by AIDO.
It is a fact about the past; nothing that happens afterwards can unmake it. What
is lost is only *turn-completion* knowledge — whether the turn settled, hit
AIDO's deadline, or became unobservable.

Every one of the following is reachable strictly after a correlated
acknowledgement, and none of them may erase it:

`RUNTIME_DEADLINE_EXPIRED`, `RUNTIME_PROTOCOL_VIOLATION`,
`RUNTIME_OUTPUT_CAP_EXCEEDED`, `RUNTIME_EVENT_CAP_EXCEEDED`,
`RUNTIME_READ_ERROR`, `RUNTIME_EXITED_EARLY` — the exact reachable return domain
of `PiRpcSupervisor._wait`, already enumerated in the accepted
`_RECOGNIZED_AWAIT_RESPONSE_OUTCOMES`.

**This is the invariant FU1's architecture cannot hold. §2 is that finding.**

---

## 2. OBJECTIVE 2 — separating dispatch authority from turn completion

### 2.1 The defect in the FU1 architecture, stated structurally

FU1's controller has exactly one injected adapter for the whole thing:

```python
send_semantic_prompt: Callable[[SemanticPromptRequest], SemanticTurnObservation]
```

and `SemanticTurnObservation.__post_init__` (`semantic_session.py`) enforces:

- a non-`CONFIRMED_SENT` dispatch may carry no turn fact at all; and
- a `CONFIRMED_SENT` dispatch **requires** `call_succeeded is True` **and**
  exactly one of `agent_settled` / `deadline_reached` true —
  *"there is no third terminal state"*.

Now take the §1.10 case, which is reachable in the real seam: the correlated
acknowledgement arrived (so dispatch is mechanically `CONFIRMED_SENT`), and then
the stdout reader hit a protocol violation, an output cap, an event cap, a read
error, or the child exited early. A live adapter has exactly two options, and
**both are wrong**:

1. **Return** a `SemanticTurnObservation`. It cannot: the run neither settled nor
   reached AIDO's deadline, and the type refuses to represent that. The only way
   to construct one is to set `deadline_reached=True`, which is a fabricated
   fact.
2. **Raise.** The controller's dispatch gate catches *any* exception from
   `send_semantic_prompt` as `_DispatchIndeterminate`, which sets
   `dispatch_state = SEND_STATE_INDETERMINATE` and `semantic_prompts_sent = None`
   — **erasing a `CONFIRMED_SENT` that had already been mechanically
   established.**

The same erasure applies to a turn-phase adapter bug, a wrong-type result, and a
provenance mismatch: all three funnel into `_DispatchIndeterminate` even though
the acknowledgement may have been read minutes earlier.

**Verdict: the FU1 architecture is not faithful to the real Pi seam.** The seam
has an acknowledgement boundary strictly earlier than turn completion; the type
system collapses them into one, and the collapse is lossy in the direction that
matters most for fairness — it converts a *known spent* prompt into an *unknown*
one, and conversely it can only publish the send fact if the entire turn wait
also succeeds.

The reverse property is, however, correct in FU1 and must be preserved:
`CONFIRMED_SENT` / `CONFIRMED_NOT_SENT` are asserted only by a **returned,
well-typed, provenance-matched** observation — never by having called a Python
function, and never by an exception.

### 2.2 The proposed two-phase contract

The seam supports the separation the review asked for, and the phases below map
one-to-one onto real operations:

```text
compatibility established                  (existing gates, unchanged)
        |
        v
PHASE 1  dispatch_semantic_prompt(...)  ->  SemanticPromptDispatchObservation
         = supervisor.send_command({"id": ..., "type": "prompt", "message": ...})
           then supervisor.await_response(id, timeout_seconds=<dispatch deadline>)
        |
        v
DURABLE BOUNDED DISPATCH OBSERVATION   (recorded before anything else may run)
        |
        v
PROMPT-COUNT TRUTH ESTABLISHED         (semantic_prompts_sent fixed here, once)
        |
        v
PHASE 2  observe_semantic_turn(...)     ->  SemanticTurnObservation
         = supervisor.await_settled(timeout_seconds=<turn deadline>)
        |
        v
agent_settled  |  AIDO deadline  |  turn observation failed
```

**Phase 1 — `dispatch_semantic_prompt(request) -> SemanticPromptDispatchObservation`**

- Input is the existing `SemanticPromptRequest` (unchanged: run id, runtime
  session, task id, task revision; no free-text prompt parameter).
- Output is the existing `SemanticPromptDispatchObservation` **plus one new
  bounded field**, `dispatch_evidence_code` (§2.3), and **minus its role as a
  passenger inside the turn observation**.
- A raised exception, a wrong type, or a provenance mismatch yields
  `SEND_STATE_INDETERMINATE` — exactly FU1's accepted rule, kept.
- **The controller records this observation before phase 2 is entered.** After
  this point `semantic_prompts_sent` is fixed for the attempt and no later code
  path may write it.

**Phase 2 — `observe_semantic_turn(turn_request) -> SemanticTurnObservation`**

- Entered **only** when phase 1 returned `CONFIRMED_SENT`. `CONFIRMED_NOT_SENT`
  is a pre-prompt infrastructure refusal and `SEND_STATE_INDETERMINATE` is
  terminal for the attempt; neither reaches phase 2.
- `turn_request` binds run id / runtime session / task identity **and** carries
  the phase-1 observation for provenance checking. It is an input, so phase 2
  structurally cannot rewrite it.
- `SemanticTurnObservation` loses its embedded dispatch object and its
  `call_succeeded` flag, and gains a **three-valued** terminal outcome:

  | `turn_outcome` | Meaning | Producing supervisor outcome |
  |---|---|---|
  | `SETTLED` | Pi reported `agent_settled` | `RUNTIME_SETTLED` |
  | `DEADLINE_REACHED` | AIDO's own monotonic turn deadline elapsed first | `RUNTIME_DEADLINE_EXPIRED` |
  | `OBSERVATION_FAILED` | the turn became unobservable to AIDO | `RUNTIME_PROTOCOL_VIOLATION`, `RUNTIME_OUTPUT_CAP_EXCEEDED`, `RUNTIME_EVENT_CAP_EXCEEDED`, `RUNTIME_READ_ERROR`, `RUNTIME_EXITED_EARLY`, or a raised phase-2 adapter exception |

  `agent_end_observed` stays as today: an independent, non-completion fact
  (`agent_end` may carry `willRetry`, and is emitted once per loop iteration).

  `OBSERVATION_FAILED` is the "third terminal state" the current type denies. It
  is what makes §1.10 representable **without** either lying or erasing.

`DEADLINE_REACHED` and `OBSERVATION_FAILED` keep the accepted claim discipline
verbatim: AIDO stopped waiting. Neither claims Pi stopped, the provider request
was cancelled, or backend inference stopped.

### 2.3 The bounded dispatch evidence code

`SemanticPromptDispatchObservation` gains one field, `dispatch_evidence_code`,
drawn from a **closed, declared vocabulary** — never raw Pi text, never a
supervisor outcome string retained verbatim. This mirrors the accepted
`LaunchDiagnostic` discipline (`required_flags_code`, whose three-state
ACCEPTED / REJECTED / INDETERMINATE shape is the direct precedent for this whole
correction).

| `dispatch_state` | `dispatch_evidence_code` | Mechanical basis |
|---|---|---|
| `CONFIRMED_NOT_SENT` | `GATE_REFUSED_BEFORE_WRITE` | AIDO's own dispatch gate refused; `send_command` never entered |
| `CONFIRMED_NOT_SENT` | `PROMPT_RESPONSE_REFUSED` | correlated `{command:"prompt", id:<ours>, success:false}` — §1.5 proves nothing reached the agent loop |
| `CONFIRMED_NOT_SENT` | `COMMAND_UNPARSEABLE_REFUSED` | an uncorrelated `{command:"parse", success:false}` observed in the dispatch window, with no `prompt` response for AIDO's id. **Admissible only under the single-writer rule in §2.5.** Effectively unreachable, since AIDO serializes with `json.dumps` |
| `CONFIRMED_SENT` | `PROMPT_RESPONSE_ACCEPTED` | correlated `{command:"prompt", id:<ours>, success:true}` |
| `CONFIRMED_SENT` | `AGENT_RUN_OBSERVED` | an `agent_start` (or any later turn/message/tool/`agent_end`/`agent_settled` record) observed for this session after dispatch, when the correlated response itself was missed. §1.6 makes this independently sufficient |
| `SEND_STATE_INDETERMINATE` | `WRITE_FAILED_TRANSMISSION_UNKNOWN` | `send_command` raised; §1.7 |
| `SEND_STATE_INDETERMINATE` | `NO_CORRELATED_RESPONSE_DEADLINE` | `RUNTIME_DEADLINE_EXPIRED` waiting for the acknowledgement |
| `SEND_STATE_INDETERMINATE` | `NO_CORRELATED_RESPONSE_STREAM_TERMINAL` | `RUNTIME_PROTOCOL_VIOLATION` / `_OUTPUT_CAP_EXCEEDED` / `_EVENT_CAP_EXCEEDED` / `_READ_ERROR` / `_EXITED_EARLY` before any acknowledgement |
| `SEND_STATE_INDETERMINATE` | `ADAPTER_RAISED` | phase-1 adapter raised |
| `SEND_STATE_INDETERMINATE` | `OBSERVATION_MALFORMED_OR_FOREIGN` | wrong type, or `require_dispatch_matches_request` false |

The code is **audit-only**. Nothing branches on it except the accounting rules
this document defines; it exists so an artifact can say *which* mechanical fact
established the state, in the same way `stall_source` is recorded but never
branched on in the accepted reviewer supervisor.

### 2.4 The load-bearing invariants

**I-1 (monotonicity).** Once phase 1 returns `CONFIRMED_SENT`, that fact and the
`semantic_prompts_sent = 1` derived from it are **write-once**. No phase-2
outcome, no broker-observation failure, no repository-observation failure, no
verification failure, no report-claims failure, no runtime-teardown failure, no
broker-shutdown failure, no generated-config cleanup failure, and no
evidence-emission failure may move it back to `SEND_STATE_INDETERMINATE` or to
`0`. Mechanically: the controller's `_DispatchIndeterminate` path must become
reachable **only from inside the phase-1 block**, and the assignment
`semantic_prompts_sent = 1` must dominate every later statement.

**I-2 (no send by convention).** Calling `dispatch_semantic_prompt` establishes
nothing. `CONFIRMED_SENT` and `CONFIRMED_NOT_SENT` may be produced only by a
returned, well-typed, provenance-matched `SemanticPromptDispatchObservation`
carrying an evidence code from §2.3. This is FU1's accepted rule, unchanged.

**I-3 (no invented acknowledgement).** The only acknowledgements this design uses
are the ones Pi 0.84.4 actually emits: the correlated `prompt` response (both
arms), the uncorrelated `parse` failure, and the forwarded session events
`agent_start` / `agent_end` / `agent_settled`. No receipt, no ping, no
`get_state` probe used as a proxy for delivery, and no timing heuristic may be
added.

**I-4 (assumption-scoping).** The three non-model `success: true` branches (§1.5)
are excluded by AIDO-owned source and config, not by a per-run Pi observation. A
live adapter phase must record them as declared assumptions and must assert the
two it can assert locally — the frozen prompt text does not begin with `/`, and
AIDO's own extension registers no `input` handler — rather than claiming Pi
confirmed them.

### 2.5 The single-writer rule (needed for `COMMAND_UNPARSEABLE_REFUSED`)

Pi's parse-failure response carries **no id** (`error(undefined, "parse", ...)`),
so it cannot be correlated the way a `prompt` response can. It is admissible as
`CONFIRMED_NOT_SENT` only when AIDO can itself prove the failing line was AIDO's
dispatch line. That requires an AIDO-owned invariant the adapter must enforce and
record:

> AIDO is the **only** writer to Pi's stdin, it writes exactly one command line
> at a time, and it does not write the next command until the previous one's
> response has been observed or its wait has terminated.

The existing handshake sequence (`h1` `get_commands`, `h2` `get_state`) already
follows this discipline. If a future adapter ever pipelines commands, this
evidence code must be withdrawn — not weakened.

### 2.6 What this contract deliberately does not add

No abort/cancel command (`abort`, `abort_retry`, `clear_queue`) is issued
anywhere. No `steer` or `follow_up`. No second prompt of any kind. No streaming
consumption for progress inference. No `get_state` polling as a delivery probe.
No re-dispatch, no backoff, no reconnection. No generic multi-harness runtime
abstraction — this is Pi-specific Q1/PRE1 work, exactly as AR0 §17.3 requires.

---

## 3. OBJECTIVE 3 — the frozen evidence-schema gap

### 3.A Is a `SEND_STATE_INDETERMINATE` event a qualification run under the frozen primary schema?

**No.** `qualification.records._validate_run_shape` admits exactly two shapes:

- `infrastructure_refusal == True` **requires** `semantic_prompts_sent == 0`,
  `run_validity is None`, `scoring_eligible is False`; and
- otherwise **requires** `semantic_prompts_sent == 1` *and* a non-null
  `run_validity` from `VALID_RUN_VALIDITY`.

`None` fails the `isinstance(..., int)` check outright, and there is no third
branch. Both representable shapes would be false statements: shape 1 asserts the
prompt was **not** sent (i.e. `CONFIRMED_NOT_SENT`), shape 2 asserts it **was**
(`CONFIRMED_SENT`). The frozen schema has no slot for an unestablished send fact,
and FU1 was right not to force one.

The same is true of the frozen classifiers: `resolve_run_validity` raises unless
`semantic_prompts_sent == 0` for a refusal, `classify_cleanup_failure` raises for
anything but `0` or `1`, and `RunFacts`/`classify_outcome` presuppose a
determinate count.

### 3.B What artifact records that the attempt occurred?

A **new, separate, attempt-level infrastructure artifact**:

```text
record_version : pi-implementer-qualification-attempt.v1
record_kind    : "qualification attempt (indeterminate semantic dispatch)"
```

emitted through the **same** fail-closed choke point every other artifact in this
package uses — `qualification.safety.emit_evidence_or_refuse`, which is already
generic and parameterized by `record_kind`, writes with `O_CREAT|O_EXCL`, and
substitutes a bounded refusal record if the payload fails the scrub. Reusing the
*choke point* is correct; reusing the *refusal record's meaning* is not (§3.C).

Content, all of it already available at the point of failure:

- identity: candidate, `model_id`, `task_id`, `task_revision`, package/experiment
  header — the same header helper the primary record uses;
- `semantic_dispatch_state: "SEND_STATE_INDETERMINATE"` and the bounded
  `dispatch_evidence_code` from §2.3;
- `semantic_prompts_sent_established: false`, and **no** `semantic_prompts_sent`
  key at all — an absent field, never `null` doing double duty, and never `0`;
- `attempt_consumed: true` (§3.G);
- the gate-status map up to and including `semantic_prompt_dispatch`, the observed
  Pi version, and the compatibility facts established before dispatch;
- the closure facts that closure actually produced: runtime teardown, broker
  shutdown, generated-config cleanup — including a cleanup whose classification is
  absent because the frozen classifier could not be called (§3.F);
- explicit negative statements, scoped: `qualification_record_emitted: false`,
  `scoring_eligible: false`, `run_validity: null`,
  `autonomous_classification: null`, `hard_bar_evaluable: false`;
- a fixed `claim_scope` string stating, in the accepted vocabulary, that AIDO's
  wait ended and AIDO cannot establish whether the semantic command crossed the
  send boundary — and that this is **not** a claim that Pi stopped, that the
  request was cancelled, or that backend inference stopped.

Nothing raw, nothing secret, no absolute path, no endpoint, no prompt text, no
reasoning: the existing scrub applies unchanged.

### 3.C May it reuse the artifact-emission-refusal or lineage machinery?

**Artifact-emission-refusal record: NO.** `build_refusal_record` hard-codes
`outcome: "artifact_emission_refused"`, `scrub_checked: true`,
`candidate_artifact_not_emitted: true`, and a finding count/categories. It means
exactly one thing: *a candidate artifact was built and then withheld because it
failed the safety scrub*. An indeterminate dispatch is not a scrub failure;
emitting one would assert a safety finding that never occurred and would hide the
real event behind an unrelated code. Reuse of the meaning is refused.

**The shared emission choke point: YES.** `emit_evidence_or_refuse` is generic and
already takes `record_kind`; using it keeps exclusive-create immutability, the
scrub, and the refusal fallback identical for the new artifact. And the refusal
record *does* correctly apply to the new artifact in its own right: if the attempt
artifact itself fails the scrub, a refusal record is written in its place, exactly
as for a primary record.

**Lineage machinery: NOT AS-IS.** `lineage._require_run_record_shape` demands
`record_kind == RECORD_KIND` **and** `record_version == RECORD_VERSION` of both
the invalidated and the replacement record — deliberately, so that a refusal
record can never be passed off as a run record. An attempt artifact is neither, so
`build_invalidation_evidence` would raise `LineageBindingError` today. See §3.I
for the narrow extension this requires.

Reusing `INFRASTRUCTURE_CONTAMINATION` as the invalidation reason would also be a
lie: §17.2 case 2 explicitly means *"it consumed the one authorized semantic
prompt"* — i.e. `CONFIRMED_SENT`. Asserting it for an indeterminate attempt would
resolve the ambiguity by fiat in the direction we cannot prove.

### 3.D Does the primary schema need a new version or a new field?

**No. `pi-implementer-qualification.v1` stays exactly as frozen.**

Widening `semantic_prompts_sent` to `int | None` inside the primary record would
push an unestablished fact into every downstream consumer that currently gets to
assume it is determinate: `_validate_run_shape`, `resolve_run_validity`,
`classify_cleanup_failure`, `classify_outcome`, `evaluate_hard_bar`,
`build_invalidation_evidence`, and the ranking layer. Each would need its own
`None` branch, and every one of those branches would be a place where an unproven
fact could later be read as a proven one. That is precisely the "silently widen
the frozen record schema" failure this phase is told to avoid.

The correct shape is a **sibling artifact kind at its own version**, whose very
`record_kind` makes it unmistakable and unmergeable with a run record — and whose
absence of a `semantic_prompts_sent` key makes the gap explicit rather than
encoded as a sentinel.

### 3.E Correction to the frozen primary record, or a separate artifact?

**A separate attempt-level infrastructure artifact.** An indeterminate dispatch is
not a qualification *run*: no run validity applies, no autonomous classification
applies, no scoring applies, and the hard bar cannot see it. It is an
infrastructure event about an attempt. Recording it as a corrected primary record
would put a non-run into the primary corpus and would require exactly the schema
widening §3.D refuses.

### 3.F Must every invoked attempt leave immutable retained evidence?

**Yes — and today it does not. This is the second acceptance blocker.**

`semantic_controller.run_semantic_task_attempt` currently sets
`qualification_record = None` for an indeterminate dispatch and **writes no file
at all**; the `EVIDENCE_SAFETY` gate is marked `NOT_REQUIRED`. So the one outcome
in which AIDO cannot prove whether the candidate's single authorized prompt was
spent is the one outcome that leaves nothing on disk. The in-memory
`SemanticTaskAttemptResult` is not evidence — it dies with the process.

**Rule: exactly one artifact per invoked attempt, always — never zero, never
two.** Either the primary `pi-implementer-qualification.v1` record (determinate
send state) or the `pi-implementer-qualification-attempt.v1` artifact
(indeterminate), through the same choke point, at the same exclusive-create
evidence path the sweep already allocates.

"Invoked" is the boundary: a task the sweep never started (§3.J) has no attempt
and needs no artifact. A task whose attempt began and then refused before dispatch
already emits a primary record with `infrastructure_refusal: true` and
`semantic_prompts_sent: 0`, which is correct and unchanged.

A closure consequence, already visible in FU1: `SemanticCleanupStatus` for an
indeterminate attempt carries `classification = None` because
`classify_cleanup_failure` cannot be called with an unestablished count. That
honest gap must be carried into the artifact as an explicit
`cleanup_classification_unavailable_reason: "semantic dispatch send state
indeterminate"`, not as a missing key and not as a fabricated classification.

### 3.G Does an indeterminate send consume the one-shot attempt?

**Yes.** `attempt_consumed: true`.

Derivation, not preference. §9 states the primary policy exactly: one prompt, no
continuation, no retry, and *"once the prompt is sent, its evidence stands."*
§11.5 grants the "attempt NOT consumed" exemption only to
`INFRASTRUCTURE_REFUSAL`, which is defined by `semantic_prompts_sent = 0` — a
**proven** zero. An indeterminate state is not a proven zero. If AIDO treated it
as one and re-ran the task, the candidate could receive the same frozen task
twice, with the first exposure unrecorded. That is the fairness failure the
one-shot rule exists to prevent, and it is asymmetric: wrongly consuming an
attempt costs one replacement run under §15.1, while wrongly re-running silently
corrupts the comparison between Candidate A and Candidate B.

Note the consequence for the sweep's counters — §4 and §3.J.

### 3.H Is any automatic retry ever allowed?

**No.** Not immediately, not after a delay, not "the same prompt again because we
never saw an ack", not a different phrasing, not a fresh session for the same task
within the same sweep.

The reason is the same one that makes the accepted reviewer supervisor treat a
stall as terminal: **AIDO's wait ending is not the request ending.** If the first
prompt did cross the boundary, a second dispatch gives the same task two semantic
exposures and, on a local backend, potentially two concurrent turns against a
workspace AIDO believes is quiescent. There is no observable, trustworthy Pi-side
cancellation acknowledgement that would let AIDO establish the first turn ended;
§2.6 forbids adding one here.

`automatic_semantic_retry` stays permanently `false` in every record, exactly as
§26's field table requires.

### 3.I Operator-authorized infrastructure replacement, and the lineage link

**Yes**, under §15.1 and only under it: an explicit, recorded operator decision
naming what changed. The replacement is a **new attempt producing its own
record**; it never overwrites the ambiguous artifact and is never presented as an
invisible model retry.

Lineage must link them, and today it cannot (§3.C). The narrow extension required
— to be authorized and implemented separately, not here — is:

1. a third invalidation reason, `indeterminate_semantic_dispatch`, added to
   `lineage._VALID_REASONS`. It must **not** be folded into
   `INFRASTRUCTURE_CONTAMINATION`, whose §17.2-case-2 meaning asserts the prompt
   *was* consumed;
2. permission for the *invalidated* side of a lineage record to be an attempt
   artifact — verified by its own `record_kind`/`record_version` pair, with the
   same strictness `_require_run_record_shape` applies today, and with the
   existing refusal-record rejection preserved. The *replacement* side stays a
   real primary run record;
3. the replacement record carries the existing `supersedes_task_revision` /
   supersedes relationship, and lineage records both SHA-256 digests and filenames
   only, as it already does;
4. the lineage record states plainly that the superseded attempt's send state was
   never established — so a reader can never infer from the existence of a
   replacement that the original was proven not-sent.

Until that extension is authorized, an indeterminate attempt is recorded and the
task simply remains unresolved. That is an acceptable state; inventing a link is
not.

### 3.J Sweep behaviour after an indeterminate IQ-1

**Stop the sweep immediately. Do not attempt IQ-2 or IQ-3.**

Derived from frozen policy, not chosen for convenience:

1. **The verdict is already fixed.** `evaluate_hard_bar` requires all three tasks
   to be `VALID` and scoring-eligible. An indeterminate task can never become
   either — it has no `run_validity` at all. The sweep's hard-bar result is
   `INCOMPLETE` regardless of what IQ-2 and IQ-3 produce, so continuing buys no
   verdict.
2. **Continuing spends one-shot attempts against uncharacterised infrastructure.**
   By §3.G the indeterminate attempt is consumed. Its cause is by definition an
   *unestablished* infrastructure condition — a lost acknowledgement, a broken
   stdout view, an early child exit. §11.5 and §15.1 put re-running after an
   infrastructure failure in the operator's hands, under an explicit recorded
   decision. A sweep that plows on converts one replaceable task into three, and
   does so without the operator ever deciding.
3. **A possibly-live turn may still be running.** An indeterminate dispatch is
   exactly the state in which Pi may be executing the task while AIDO cannot see
   it — and the closure gates may themselves have failed. §9's guarantee that each
   task gets a fresh process and fresh repository with no shared state assumes the
   previous task's runtime is finished. Launching IQ-2's runtime and broker while
   that is unproven violates the assumption the fairness model rests on.
4. **The budget can no longer be proven.** §9 caps a candidate at three semantic
   prompts. After an indeterminate dispatch the *confirmed* count is 0 but the
   *possible* count is 1. Continuing could issue three more, for a possible total
   of four (§4).

Recording, then: IQ-1 emits its attempt artifact; IQ-2 and IQ-3 are recorded in
the sweep result as `NOT_ATTEMPTED` with **no artifact** (nothing was invoked, so
§3.F does not apply); `hard_bar_result` is `INCOMPLETE`; the sweep result names
the indeterminate task id, as FU1's `indeterminate_dispatch_task_ids` already
does.

The operator may then authorize a §15.1 replacement for IQ-1 and a continuation of
the sweep. That is an explicit human decision, which is the point.

---

## 4. OBJECTIVE 4 — the four counts stay distinct

Frozen I2A §7.1/§19 already establish that **one AIDO semantic task prompt may
cause one or many provider inference requests**, and that AIDO has **no
authoritative numeric observer** for the provider request count — I2A §19 records
the correction that replaced a per-task `provider_inference_requests_per_task`
count with `provider_inference_request_count_observation_available = false`. This
design preserves that unchanged and adds nothing that could be mistaken for such
an observer.

| Count | Owner | Observable? | Where it lives |
|---|---|---|---|
| `semantic_prompts_sent` | AIDO / controller | **Yes**, three-state via §2.3 | `0` or `1` in a primary record; **absent** in an attempt artifact |
| Pi provider inference requests | the provider / backend | **No** | never recorded as a number, anywhere |
| RPC command/response count | AIDO ↔ Pi wire | Yes (AIDO issues them) | `PiRpcSupervisor.commands_sent`, and the event-type counts; **not** a semantic count |
| Model HTTP request count | the backend | **No** | never recorded |

Three concrete anti-conflations this document makes explicit:

- **`agent_start` count is not a prompt count.** `runAgentLoopContinue` emits
  `agent_start` on every continuation, and `_runAgentPrompt` loops on
  `_handlePostAgentRun` (auto-retry, compaction, queued drain). One AIDO prompt
  can produce many.
- **`agent_end` count is not a turn count.** `agent_end` may carry `willRetry`;
  only `agent_settled` is the turn-completion signal, and it has exactly one
  emission site.
- **Pi's own provider retry is not an AIDO prompt.** AIDO's generated
  `settings.json` sets `retry.maxRetries: 3` with `retry.provider.maxRetries: 0` —
  Pi owns that retry, AIDO does not, and it never increments any AIDO count.

And two new counters the sweep needs (§3.G/§3.J), which must **not** be collapsed
into one:

- `confirmed_semantic_prompts_sent` — the honest confirmed count, `<= 3`. An
  indeterminate task contributes `0`. This is FU1's existing
  `total_semantic_prompts_sent`, kept, and it must never be read as a claim that
  no prompt was issued.
- `semantic_dispatch_attempts` — how many times phase 1 was entered, `<= 3`, and
  **this** is the budget the sweep enforces. An indeterminate task contributes
  `1`. Without it, FU1's accounting permits a possible fourth prompt.

---

## 5. OBJECTIVE 5 — adversarial state/trace table

Abbreviations: **SPS** = the `semantic_prompts_sent` fact; **DISP** = dispatch
fact; **EV** = required retained evidence; **RA** = retry authority.
"Attempt consumed" is the §3.G fairness question, distinct from SPS.

Rows 1–3 are pre-send by construction. Rows 4–6 are the write/parse boundary.
Rows 7–11 are post-acceptance. Rows 12–15 are closure and emission.

| # | State | DISP | SPS | Scoring eligible | run_validity / classification | RA | EV required | Cleanup classification | Next-step authority |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Compatibility gate fails before dispatch (Pi/route/broker/config) | `CONFIRMED_NOT_SENT` (`GATE_REFUSED_BEFORE_WRITE`) | `0` | No | `run_validity` **absent**; `INFRASTRUCTURE_REFUSAL` | None automatic | Primary record, `infrastructure_refusal: true` | `classify_cleanup_failure(0)` if cleanup also fails | Attempt **not** consumed; re-run under §15.1 |
| 2 | Dispatch API never entered (an earlier gate raised, or the sweep stopped) | `CONFIRMED_NOT_SENT` (`GATE_REFUSED_BEFORE_WRITE`) | `0` | No | as row 1 | None automatic | Primary record | as row 1 | as row 1 |
| 3 | Adapter refuses to write (its own preconditions unmet; `send_command` never called) | `CONFIRMED_NOT_SENT` (`GATE_REFUSED_BEFORE_WRITE`) | `0` | No | as row 1 | None automatic | Primary record | as row 1 | as row 1 |
| 4 | `send_command` raises — partial/unknown transmission | `SEND_STATE_INDETERMINATE` (`WRITE_FAILED_TRANSMISSION_UNKNOWN`) | **unestablished — key absent** | No | none; **no primary record** | **None. Never automatic** (§3.H) | **Attempt artifact** `...-attempt.v1` | unavailable; reason recorded | Attempt **consumed**; sweep **stops** (§3.J); §15.1 replacement only |
| 5 | Complete write, then no response of any kind (deadline, or stream terminal before any ack) | `SEND_STATE_INDETERMINATE` (`NO_CORRELATED_RESPONSE_DEADLINE` / `..._STREAM_TERMINAL`) | unestablished | No | none | None | Attempt artifact | unavailable | as row 4 |
| 6 | Pi refuses before semantic acceptance — correlated `{command:"prompt", success:false}`, or an uncorrelated `{command:"parse", success:false}` under §2.5 | `CONFIRMED_NOT_SENT` (`PROMPT_RESPONSE_REFUSED` / `COMMAND_UNPARSEABLE_REFUSED`) | `0` | No | `INFRASTRUCTURE_REFUSAL` | None automatic | Primary record, `infrastructure_refusal: true` | `classify_cleanup_failure(0)` | Attempt **not** consumed; re-run under §15.1 |
| 7 | Acceptance mechanically established (`success:true`, or `agent_start` observed) | `CONFIRMED_SENT` | `1` — **write-once from here (I-1)** | pending phase 2 | pending | Never | Primary record (shape settled by rows 8–11) | `classify_cleanup_failure(1)` if cleanup fails | Turn observation proceeds |
| 8 | Acceptance established, then the turn read fails (protocol violation / output cap / event cap / read error / early exit / phase-2 raise) | `CONFIRMED_SENT` — **not erased** | `1` | **No** | `INFRASTRUCTURE_CONTAMINATED` (§17.2 case 2 — AIDO's own observation channel failed) if mechanically attributable to AIDO/Pi/route; otherwise `ATTRIBUTION_UNDETERMINED` (case 4). `turn_outcome = OBSERVATION_FAILED` | Never | Primary record, retained immutably | `classify_cleanup_failure(1)` | Attempt consumed; replacement only under §15.1 |
| 9 | Acceptance established, then AIDO's turn deadline elapses | `CONFIRMED_SENT` | `1` | Yes — a deadline is a **model outcome**, not contamination | `VALID`; `AUTONOMOUS_FAIL` / `RUNTIME_TIMEOUT`. `turn_outcome = DEADLINE_REACHED`. Never a claim that Pi stopped or inference stopped | Never | Primary record | `classify_cleanup_failure(1)` | Sealed; supervised-recovery probe is separate evidence only (§10) |
| 10 | `agent_end` observed without `agent_settled` (deadline or observation failure first) | `CONFIRMED_SENT` | `1` | per row 9 / row 8 | `agent_end_observed: true` is recorded as an **independent, non-completion** fact; `willRetry` means the run was still going. It never upgrades the outcome | Never | Primary record | as row 9 / row 8 | as row 9 / row 8 |
| 11 | `agent_settled` observed | `CONFIRMED_SENT` | `1` | Yes, if closure and the remaining gates hold | `VALID`; §8 classification from repository/verification/scope facts | Never | Primary record | `classify_cleanup_failure(1)` | Sealed on emission (§9) |
| 12 | Teardown / broker-shutdown failure **after** confirmed send | `CONFIRMED_SENT` — **not erased** | `1` | **No** | `INFRASTRUCTURE_CONTAMINATED` — AIDO's own closure machinery failed; §17.2 case 2 is mechanical here, since the candidate cannot influence whether AIDO's shutdown call succeeds | Never | Primary record | `classify_cleanup_failure(1)` -> `INFRASTRUCTURE_CONTAMINATED` | Replacement only under §15.1 |
| 13 | Cleanup failure after confirmed **not**-sent | `CONFIRMED_NOT_SENT` | `0` | No | `INFRASTRUCTURE_REFUSAL` | None automatic | Primary record | `classify_cleanup_failure(0)` -> `INFRASTRUCTURE_REFUSAL` | Attempt **not** consumed; re-run under §15.1 |
| 14 | Cleanup failure after **indeterminate** send | `SEND_STATE_INDETERMINATE` | unestablished | No | none | None | **Attempt artifact**, carrying the raw closure facts | **unavailable** — the frozen classifier is never called with an unestablished count; reason recorded explicitly | Attempt consumed; sweep stops; §15.1 |
| 15 | Evidence emission fails (scrub refusal, or path collision) | unchanged by emission | unchanged | **No** — `artifact_scrub_passed` false fails the hard bar's H-14 | for a `CONFIRMED_SENT` run: the bounded refusal record stands in place of the record; for `CONFIRMED_NOT_SENT`: same, over the refusal record; for `SEND_STATE_INDETERMINATE`: same, over the attempt artifact | Never | The bounded `...-refusal.v1` record, written exclusive-create in place of the unsafe payload. **A path collision is terminal and writes nothing** — emitted artifacts are immutable | unchanged | Operator investigation; no automatic re-emission, no overwrite variant exists |

Three properties the table is meant to make checkable at a glance:

- **Rows 8, 9, 10, 12 all keep `CONFIRMED_SENT` and `SPS = 1`.** That is invariant
  I-1. Under the current FU1 code, rows 8 and 12 can reach `_DispatchIndeterminate`
  and lose it.
- **Rows 4, 5, 14 never produce `0` or `1`.** The key is absent, not
  null-as-zero.
- **Rows 1–3, 6, 13 are the only "attempt not consumed" rows**, and every one of
  them is a *proven* zero.

---

## 9. FU1A — four closure contracts DESIGN-FU1 omitted

§0–§8 above are accepted in direction and **unchanged** by this section. This
section closes four gaps independent review found between them and the
**actual, already-implemented** source of `semantic_workspace.py`,
`semantic_controller.py`, `semantic_sweep.py`, `safety.py`,
`i2_secret_context.py`, and `i2b_workspace.py`. Every citation below is a
read-only line reference as of this turn; **nothing in this section modifies
any of those files.**

### 9.1 Semantic workspace ownership and verified removal

**9.1.1 The gap, from source.**

- `qualification.semantic_controller.run_semantic_task_attempt` mints
  (`mint_qualification_run_workspace()`), single-use-claims
  (`claim_run_workspace`), and populates (`populate_semantic_task_workspace`)
  one `QualificationRunWorkspace` at the `WORKSPACE_AUTHORITY` gate
  (`semantic_controller.py` lines ~1067–1080).
- The function's unconditional CLOSURE block calls exactly three closers —
  `_close_runtime`, `_close_broker`, `_attempt_cleanup` (the generated
  Pi-config scrub) — and then goes straight to `build_run_safety_context` and
  record emission (`semantic_controller.py` lines ~1573–1791). **It never
  calls workspace removal.**
- The removal function already exists, frozen and unmodified:
  `qualification.i2b_workspace.remove_run_workspace`. Its own docstring
  states plainly: *"This is a fixture/teardown convenience for the offline
  suite; the controller never calls it."* That sentence is the gap, verbatim,
  from the frozen module's own author.
- Consequence: every semantic task attempt today — pass, fail, or
  indeterminate — leaves its disposable Git fixture tree (task source,
  `.git` history, and, on some paths, an un-scrubbed generated-config
  sibling) on disk under `ar2.capability.approved_scratch_boundary()`
  indefinitely. This is a disclosure/accumulation defect distinct from, and
  unaddressed by, the frozen generated-config scrub.

**9.1.2 Ownership.** The workspace is owned by the semantic task attempt from
the instant `mint_qualification_run_workspace()` returns inside that
attempt's own call to `run_semantic_task_attempt` — never shared, never
handed to another attempt (already guaranteed structurally: the mint
function takes no argument and always creates a fresh root, and
`claim_run_workspace` is single-use). Ownership implies exactly one
obligation: this attempt, and no other code, is responsible for removing it.

**9.1.3 Frozen closure order.**

```text
runtime teardown
broker shutdown
generated-config cleanup
semantic workspace removal + verification          <- NEW
retained-evidence construction / scrub / emission
```

This is DESIGN-FU1's own accepted, already-implemented order for the first
three steps, with exactly one step inserted before evidence emission, which
stays last. **Why generated-config cleanup precedes workspace removal
rather than folding both into one blanket removal:**
`scrub_generated_qualification_config` re-verifies the config's own
creation-time issuance authority (`i2_issuance`) against the still-registered
token before deleting anything — an authority-scoped deletion, not a generic
sweep. `remove_run_workspace` → `ar2.fixtures.remove_disposable_tree` is a
generic, authority-blind tree removal (verified only by the frozen root
marker, never by any per-file issuance record). Removing the workspace first
would let the generic remover silently absorb a config directory whose
specific authority was never re-checked, discarding the more specific,
already-accepted contract without a decision ever being made about it.
**Why teardown/shutdown precede both cleanups:** the runtime session's cwd
and the broker's capability scope are both bound to `workspace_root`
(`BrokerCreationRequest.workspace`, `RuntimeLaunchRequest.workspace`) —
removing the tree out from under a still-open runtime or broker is the same
"cleanup racing a live resource" class of defect frozen O1's own
runtime-first-then-broker ordering already exists to prevent, extended here
to the workspace itself.

**9.1.4 Strict removal semantics — reused, not reinvented.**
`remove_run_workspace`'s return value is the frozen
`ar2.fixtures.remove_disposable_tree` dict, passed through unmodified. This
design freezes the **identical** strict acceptance predicate
`run_i2b_live.py`'s `_workspace_removal_succeeded` already applies to
Category-B's own outer cleanup (verbatim, because it is the same frozen
return shape, not a new one):

```text
success  <=>  type(result) is dict
          and {"removed", "residual_file_count", "verified"} <= result.keys()
          and result["removed"] is True           # identity, not truthiness
          and result["verified"] is True           # identity, not truthiness
          and type(result["residual_file_count"]) is int
          and result["residual_file_count"] == 0   # bool excluded: type(x) is int is False for a bool
```

Any other shape — a non-dict, a missing key, `"removed": "true"`,
`residual_file_count = True`, a nonzero residual with `verified: True` — is a
removal **failure**, never a partial success and never inferred as safe from
the absence of a raised exception. A raised exception from
`remove_run_workspace` itself is likewise a removal failure
(`attempted=True, verified=False`), reported, never swallowed, and never
allowed to skip evidence construction — the same `try`/`except Exception`
discipline `run_i2b_live._run_outer_cleanup` already applies to this
identical call.

**9.1.5 Recording across the three dispatch states.**

| Dispatch state | Workspace-removal recording |
|---|---|
| `CONFIRMED_NOT_SENT` | Removal is still attempted and its raw facts (`attempted`, `verified`, and the exact `{"removed", "residual_file_count", "verified"}` dict — safe to retain verbatim; it carries no path) are recorded in the primary record's cleanup section alongside `infrastructure_refusal: true`. A removal failure here is truthfully retained; it does **not** retroactively contest `semantic_prompts_sent = 0`, which is a fact about dispatch, not about disk state. |
| `CONFIRMED_SENT` | `semantic_prompts_sent` stays `1`, permanently (I-1, amended in 9.1.6). Workspace-removal failure is folded into `closure_established` exactly as runtime teardown / broker shutdown / generated-config cleanup already are (`semantic_controller.py`'s `closure_established` conjunction, ~lines 1594–1598) — so an unverified removal drives the same `INFRASTRUCTURE_CONTAMINATED` / `scoring_eligible = False` path a teardown or shutdown failure already drives (Sec. 17.2 case 2: AIDO's own closure machinery failed; the candidate cannot influence whether AIDO's own tree removal succeeds). |
| `SEND_STATE_INDETERMINATE` | No 0/1 cleanup classifier is fabricated for workspace removal any more than for generated-config cleanup (§3.F's existing rule, unchanged). The attempt-level artifact (`pi-implementer-qualification-attempt.v1`, §3.B) gains the raw bounded removal facts plus an explicit `workspace_removal_classification_unavailable_reason: "semantic dispatch send state indeterminate"` — the identical shape §3.F already freezes for `cleanup_classification_unavailable_reason`, applied to this new closure step rather than duplicated as a second mechanism. |

**9.1.6 Amendment to invariant I-1.** §2.4's I-1 list of failures that may
never move a `CONFIRMED_SENT` / `semantic_prompts_sent = 1` fact backward is
extended by exactly one entry: **no semantic-workspace-removal failure** may
move it back to `SEND_STATE_INDETERMINATE` or to `0` either. The mechanism is
identical to every other entry already in that list: `semantic_prompts_sent`
is set once, in one place, strictly before closure begins, and no
closure-time fact — workspace removal included — may rewrite it.

**9.1.7 Sealing evidence.** Because workspace removal now precedes "retained
evidence construction / scrub / emission" in the frozen order (9.1.3), the
primary record / attempt artifact is sealed only after workspace-removal
truth is known, for every dispatch state — there is no path that builds or
emits evidence and only afterward attempts removal.

### 9.2 Full artifact safety context

**9.2.1 The gap, from source.** `semantic_controller.build_run_safety_context`
(lines ~701–726):

```python
def build_run_safety_context(*, secret_context, broker_session, run_workspace, route_descriptor):
    if secret_context is None:
        return ArtifactSafetyContext.none_declared()
    return secret_context.to_safety_context(
        broker_token=broker_session.broker_token if broker_session is not None else None,
        ...
        workspace_absolute_path=run_workspace.experiment_root if run_workspace is not None else None,
    )
```

This is already a correct reuse of the accepted I2B rule *in the one order
the current gate sequence permits it to run* — `SECRET_CONTEXT` strictly
precedes `BROKER_SESSION` in `run_semantic_task_attempt`'s linear body (see
the module's own gate-order docstring), so `broker_session` can never be
non-`None` while `secret_context` is `None` in practice today. But the
function's own shape does not express that as a *proven* invariant — it
expresses it as an early return keyed on one field's presence, so its
correctness is a fact about caller control flow, not about the function
itself. A future live-adapter refactor, a caught-and-recovered
secret-context failure, or a second call site would silently reintroduce
exactly the I2B-FU1 defect this rule was written to close (a live
broker/pipe/capability value substituted with `None`). Notably,
`route_descriptor` is already accepted as a parameter and is **not read
anywhere in the function body** — an unused seam this contract now gives a
job to (see the `bearer_token` bullet below).

**9.2.2 Frozen rule.** `ArtifactSafetyContext` construction is
**field-independent**: each of the seven fields is populated from whatever
value actually exists at the time evidence is retained, and the presence or
absence of any one field's source object must never gate whether another
field's source object is consulted. Restated as the exact per-field rule:

- `workspace_absolute_path` is declared whenever `run_workspace is not None`
  — independent of `secret_context` or `broker_session`.
- `broker_token` / `pipe_name` / `capability_id` are declared whenever
  `broker_session is not None` — independent of `secret_context`.
- `endpoint_host` / `api_key` are declared whenever `secret_context is not
  None`.
- `bearer_token` is `None` **only** as a value mechanically DERIVED from the
  frozen credential mechanism, never as a bare default. It is sound
  specifically because `qualification.i2_route.RouteDescriptor.__post_init__`
  already refuses construction of any descriptor whose
  `credential_mechanism != "models_json_env_interpolation"`
  (`i2_route.py` line ~112) — so every `RouteDescriptor` this package can
  construct already proves the mechanism by the time it exists. A future
  implementation that reads `route_descriptor` in this function (as the
  already-present, currently-unused parameter invites) must assert
  `type(route_descriptor) is RouteDescriptor and route_descriptor.credential_mechanism
  == CREDENTIAL_MECHANISM` before defaulting `bearer_token` to `None`, and
  must **refuse safety-context construction** — never silently default — if
  a future second mechanism ever reaches this call with a descriptor that
  assertion rejects. There is no other bearer-value source anywhere in this
  package, so this is currently unreachable in practice; the contract exists
  so it stays refused, not silently accepted, the day a second mechanism is
  added.
- No branch anywhere in this construction may return
  `ArtifactSafetyContext.none_declared()` while **any** of `secret_context`,
  `broker_session`, or `run_workspace` is non-`None`. `none_declared()` is
  reserved for the true all-absent case only (mirrors I2B's own accepted
  rule for `i2b_controller.build_run_safety_context`, restated here because
  this module's own version currently achieves the same *result* through a
  narrower, order-dependent *mechanism*).

**9.2.3 Applies identically to all three record shapes.** The rule in 9.2.2
governs the ONE safety context every retained artifact in an attempt shares
— there is a single `safety_context` value per attempt in the current
controller (`semantic_controller.py` line ~1588), reused for the primary
qualification record, for a `SEND_STATE_INDETERMINATE` attempt artifact once
§3's extension lands, and for the emission-refusal fallback record
`emit_evidence_or_refuse` substitutes on a scrub failure (`safety.py` lines
~206–237, which re-scrubs the refusal record against the same `safety`
argument its caller passed). No real existing needle may be narrower for one
of these three shapes than for another, because all three are built from the
same `ArtifactSafetyContext` value.

### 9.3 Final assistant report is optional, untrusted evidence

**9.3.1 The gap, from source.** In `run_semantic_task_attempt`,
`FINAL_REPORT_CLAIMS` is one of `POST_PROMPT_GATES` (`semantic_controller.py`
line ~345) and is invoked through the **same** `_invoke`/`_GateFailure`
machinery as `BROKER_ACTIVITY`, `REPOSITORY_OBSERVATION`, and
`AUTHORITATIVE_VERIFICATION` (lines ~1520–1533): an adapter exception or a
malformed `FinalReportClaimsObservation` raises
`_GateFailure(FINAL_REPORT_CLAIMS, ...)`, caught by the generic `except
_GateFailure` handler, which sets `failed_gate =
SemanticGateName.FINAL_REPORT_CLAIMS`. Downstream, at lines ~1651–1668, ANY
non-`None` `failed_gate` for a `semantic_prompts_sent == 1` run (after
closure succeeded) takes the branch:

```python
attribution = attribute_protocol_anomaly(pre_prompt=False, mechanically_attributed_to=None)
validity_result = resolve_run_validity(infrastructure_refusal=False, semantic_prompts_sent=1, anomaly_attribution=attribution)
```

`attribute_protocol_anomaly(..., mechanically_attributed_to=None)` returns
the literal string `"undetermined"` (`scope.py` lines ~118–120), and
`resolve_run_validity(..., anomaly_attribution="undetermined")` returns
`RunValidity.ATTRIBUTION_UNDETERMINED` with `scoring_eligible=False`
(`validity.py` lines ~92–93). **Concretely: today, a final-report-claims
adapter failure or a malformed model report makes an otherwise-successful,
fully-verified, fully-closed run `ATTRIBUTION_UNDETERMINED` and
unscorable** — exactly the outcome this section's freeze forbids. The
model's own final text (or the harness's failure to extract it) is currently
on equal gating footing with `AUTHORITATIVE_VERIFICATION`, which is never
correct: verification is AIDO's own authoritative fact; the model's
self-report is not.

**9.3.2 Frozen authority hierarchy.**

```text
1. repository observation           (ar2.observation, reused unmodified)   -- implementation truth
2. authoritative verification       (ar2.verification, reused unmodified)  -- implementation truth
3. broker/Git cross-check           (BrokerActivityObservation vs. observed paths) -- implementation truth
4. scope/refusal facts              (qualification.scope)                  -- implementation truth
-------------------------------------------------------------------------------------------------
5. final assistant report claims    (qualification.report_accuracy)        -- OPTIONAL, UNTRUSTED
```

Layers 1–4 are exactly the facts `run_validity` / `scoring_eligible` / the
hard bar already gate on (`verification_passed`,
`expected_changed_paths_satisfied`, `head_unchanged`, `index_clean`,
`protected_witness_untouched`,
`no_unexpected_untracked_or_create_delete_rename`,
`broker_git_cross_check_agrees` — exactly `hard_bar.py`'s
`_CONJUNCTIVE_CHECKS` H-2 through H-8). Layer 5 — the model's own final
assistant prose — is never implementation authority and must never be
promoted to it by a collection failure any more than by its content.

**9.3.3 Bounded report-availability state.** Final-report
extraction/parsing produces exactly one of a closed three-value
classification — `AVAILABLE`, `UNAVAILABLE`, `MALFORMED` (names
illustrative; any equivalent bounded closed representation satisfies this
contract) — and this classification is **orthogonal to `failed_gate`**: a
report-collection failure must never route through `_GateFailure` /
`failed_gate` at all, because that path is shared with genuinely gating
post-prompt facts. The frozen rule for a future implementation:

- `FINAL_REPORT_CLAIMS_COLLECTION_FAILED` and `MALFORMED_ADAPTER_RESULT` for
  the `collect_final_report_claims` adapter must **not** raise
  `_GateFailure`. They must produce a bounded `report_availability` fact
  (`UNAVAILABLE` for an adapter exception or a wrong-type return;
  `MALFORMED` for a well-typed `FinalReportClaimsObservation` whose `claims`
  nonetheless fails `report_accuracy`'s own bounded parsing/comparison) and
  leave `report_claims = None` / `comparisons = ()`, exactly as
  `_project_report_accuracy(())` already renders `{"attempted": False}`
  today for the "adapter never ran" case.
- `UNAVAILABLE` / `MALFORMED` must not change repository truth (layer 1),
  verification truth (layer 2), or scope truth (layer 4) — none of those
  layers reads report claims at all today, and this contract forbids ever
  wiring one to read the other.
- `UNAVAILABLE` / `MALFORMED` must not by themselves change `run_validity` —
  i.e. `FINAL_REPORT_CLAIMS` must be removed from the set of gates whose
  failure can produce a non-`None` `failed_gate` feeding the
  `attribute_protocol_anomaly` / `resolve_run_validity` branch at lines
  ~1651–1668. An otherwise-`VALID`, closure-satisfied,
  `AUTHORITATIVE_VERIFICATION`-passed run stays `VALID` /
  `scoring_eligible=True` regardless of `report_availability`.
- `UNAVAILABLE` / `MALFORMED` must never create `ATTRIBUTION_UNDETERMINED` —
  the specific defect in 9.3.1 — because report unavailability is never a
  protocol anomaly; it is, at most, evidence about the report layer alone.
- `UNAVAILABLE` / `MALFORMED` must not make an otherwise-valid result
  unscorable: `scoring_eligible` and the hard bar's H-1 through H-9
  conjunctive checks (none of which is report-accuracy) are computed exactly
  as if the report had never been requested.
- Its only effect is that `report_accuracy` becomes not-evaluable:
  `_project_report_accuracy` records `{"attempted": False}` (adapter never
  produced usable claims) or a new bounded `{"attempted": True, "available":
  False, "reason": ...}` shape distinguishing "the model produced nothing
  parseable" from "the harness could not collect it" — purely descriptive,
  never scored, never fed to the hard bar (`report_accuracy` is not one of
  the H-1..H-9 checks today, and this contract keeps it that way).

**9.3.4 When a report is available and parseable.** No change:
`report_accuracy.compare_report(report_claims, observed_facts)` runs exactly
as it does today (`semantic_controller.py` lines ~1733–1739), comparing the
model's claims against the same layer 1–4 facts, conservatively (QD-4).
Availability does not relax that comparison; it only determines whether the
comparison happens at all.

**9.3.5 Report parsing failure is never a semantic retry reason.** Restates
and extends §3.H/§2.6's existing "no automatic retry, ever" rule to this
specific trigger, because a malformed final report is exactly the kind of
"the harness didn't get what it expected" event a retry temptation attaches
to: it is not one, for the identical reason a stall is not (§3.H) — AIDO's
wait for report-collection ending is not proof the one authorized prompt
needs reissuing, and the prompt was already confirmed sent regardless of
what its own self-report says about itself.

### 9.4 Result and sweep deep immutability

**9.4.1 The gaps, from source — three concrete, currently-reachable mutation
paths.**

1. `SemanticTaskAttemptResult.gate_statuses: Mapping[str, str]`
   (`semantic_controller.py` line ~859) is constructed as
   `gate_statuses=dict(gate_statuses)` (line ~1807) — a **plain, mutable
   `dict`**, type-hinted `Mapping` but never checked or wrapped in
   `__post_init__` (contrast `i2b_controller.CategoryBControllerResult.gate_statuses`,
   which FU2A already made a `MappingProxyType` over a throwaway dict
   specifically to close this class of defect for Category-B). A caller
   holding the dict passed into the constructor, or reading
   `result.gate_statuses` and mutating it in place, can rewrite any gate's
   recorded outcome after validation, with nothing to detect or refuse it.
2. `SemanticTaskAttemptResult.qualification_record: dict[str, Any] | None`
   is the literal object `emit_evidence_or_refuse` returns (`{"emitted":
   ..., "refused": ..., "path": ..., "scrub": {"scrub_checked": ...,
   "findings": [...], "clean": ...}}`), stored by reference with no
   defensive copy and no `MappingProxyType`. `PrimarySweepResult`'s own
   `_task_hard_bar_facts` (`semantic_sweep.py` lines ~251–254) reads
   `result.qualification_record.get("refused")` to derive
   `artifact_scrub_passed` for the hard bar — so mutating this nested dict
   (including its nested `"findings"` **list**, also unwrapped) between
   attempt-result construction and hard-bar evaluation changes a fact the
   hard bar trusts, with no relationship enforced to the immutable on-disk
   artifact `emit_evidence_or_refuse` already wrote via
   `write_evidence_exclusively`'s exclusive-create.
3. `PrimarySweepResult.task_results: dict[str, SemanticTaskAttemptResult]`
   (`semantic_sweep.py` line ~152) is a **plain, mutable `dict`**.
   `__post_init__` (lines ~157–193) validates `total_semantic_prompts_sent`
   and `indeterminate_dispatch_task_ids` against `self.task_results` **at
   construction time**, but nothing prevents a caller from replacing,
   adding, or deleting an entry afterward
   (`result.task_results["IQ-2"] = forged_result`) — after which
   `hard_bar_result` (already computed by `evaluate_hard_bar` before
   `PrimarySweepResult.__init__` runs, per `run_primary_sweep`'s own
   sequencing at lines ~343–353) permanently disagrees with the now-mutated
   `task_results` it was supposedly derived from, with no re-validation and
   no detection.

**9.4.2 Frozen rule.** Every fact consumed by classification
(`outcomes.classify_outcome`), the hard bar (`hard_bar.evaluate_hard_bar`),
ranking (`ranking`, once wired), evidence generation
(`records.build_qualification_record`, `safety.emit_evidence_or_refuse`), or
audit (any human/independent reading of a `SemanticTaskAttemptResult` /
`PrimarySweepResult`) must be **mechanically immutable after successful
construction** — a frozen dataclass whose fields are themselves mutable
containers (a plain `dict`, `list`, or mutable `set`) is explicitly **NOT
SUFFICIENT**, because `@dataclass(frozen=True)` only refuses reassigning the
FIELD, never mutating the OBJECT the field refers to. At minimum, the
following must each be proven immutable by type, not by caller convention:

| Fact family | Current shape | Required shape |
|---|---|---|
| Task gate statuses | `SemanticTaskAttemptResult.gate_statuses: dict` (mutable) | `MappingProxyType` over a private, never-externally-referenced backing `dict` — the identical fix FU2A already applied to `CategoryBControllerResult.gate_statuses` |
| Dispatch/turn observations | `SemanticPromptDispatchObservation`, `SemanticTurnObservation` (already `@dataclass(frozen=True)`, all scalar/enum fields) | Already satisfies this contract — cited here only to record that the sweep is what does not, not to reopen these types |
| Bounded closure facts | `RuntimeTeardownStatus` / `BrokerShutdownStatus` / `SemanticCleanupStatus` (already frozen, scalar/enum fields only) | Already satisfies this contract |
| Primary-record projection | `qualification_record: dict` holding a live reference to `emit_evidence_or_refuse`'s own return object, including a mutable nested `"findings"` list | A frozen, immutable projection: either a `MappingProxyType` wrapping a recursively-immutable copy (nested `"findings"` as a `tuple`, not a `list`), or — preferably, since the on-disk artifact is the actual evidence — a narrower typed record (emitted/refused/path/clean/finding tuple) rather than re-exposing `emit_evidence_or_refuse`'s raw return shape by reference at all |
| Attempt-record projection | The new §3.B attempt artifact (not yet implemented) | Must be built as an immutable value from the start — this contract applies to its first implementation, not as a retrofit |
| Task-result collections | `PrimarySweepResult.task_results: dict[str, SemanticTaskAttemptResult]` (mutable) | `MappingProxyType` over a private backing `dict`, exactly mirroring the `gate_statuses` fix, applied one level up |
| Sweep `task_results` | (same object as above — cited under both headings because both this document's instructions and the adversarial check name it separately) | (same fix) |
| Indeterminate-task collections | `PrimarySweepResult.indeterminate_dispatch_task_ids: tuple[str, ...]` (already a tuple) | Already satisfies this contract |
| Hard-bar inputs | `hard_bar_tasks: dict[str, TaskHardBarFacts \| None]` (`semantic_sweep.py` lines ~343–346) is a **local, throwaway** dict never exposed on any returned object — `evaluate_hard_bar` consumes it and returns `HardBarResult` (already frozen, tuple fields only) before any caller could reach the local dict at all | Already satisfies this contract by construction (no reference ever escapes) — cited to show the difference between a safe internal-only mutable dict and an unsafe one reachable through a public field |

**9.4.3 What a caller must not be able to do, restated as the exact
refusals this contract requires:**

- mutate a task result after validation — refused once `gate_statuses` and
  `qualification_record`'s replacement types (9.4.2) ship, because there is
  no longer a mutable object reachable from the frozen
  `SemanticTaskAttemptResult` at all;
- mutate gate statuses after result construction — refused by the same
  `MappingProxyType` wrap (`mp["x"] = "y"` raises `TypeError`), applied at
  the point the throwaway dict is wrapped, never exposing the throwaway dict
  itself afterward (the FU2A discipline: the private dict is discarded from
  the constructing scope; only the proxy is retained);
- mutate qualification/attempt record projection through the result —
  refused once the projection is either a `MappingProxyType`-wrapped
  fully-immutable copy or a narrow frozen dataclass, per 9.4.2's row;
- replace/add/remove a sweep task result after hard-bar evaluation —
  refused by wrapping `PrimarySweepResult.task_results` in
  `MappingProxyType`, so `result.task_results["IQ-2"] = x` raises
  `TypeError` rather than silently succeeding;
- create disagreement between `hard_bar_result` and its validated task
  inputs — once `task_results` cannot be mutated post-construction,
  `hard_bar_result` (computed from the same task results before
  `PrimarySweepResult.__init__` even runs, per `run_primary_sweep`'s
  existing sequencing) can no longer drift from the object a reader can
  still inspect, because there is no longer any way to change what that
  object shows.

**9.4.4 Two separate requirements, stated explicitly.** Disk-artifact
exclusive-create immutability (`safety.write_evidence_exclusively`'s
`O_CREAT | O_EXCL`, already accepted and unchanged by this document) and
in-memory result immutability (9.4.1–9.4.3, newly frozen here) are
**separate properties, and satisfying one does not satisfy the other**. The
gap this section closes is precisely a case where the first was already
true and the second was not: `emit_evidence_or_refuse` writes an immutable
file, and the exact same information's in-memory reflection on
`SemanticTaskAttemptResult.qualification_record` was, until this contract,
a live-referenced, fully mutable dict that nothing re-validated against the
file it was supposed to describe.

---

## 10. FU1A adversarial design check

Each row names one case from the assignment's adversarial list, which
subsection closes it, and how.

| Adversarial case | Closed by | How |
|---|---|---|
| Workspace minted then any pre-prompt failure | §9.1.3 / §9.1.5 | Closure order applies unconditionally on every terminal path (mirrors the existing `except _DispatchIndeterminate` / `except _GateFailure` / `except Exception` → unconditional CLOSURE structure already in `run_semantic_task_attempt`); a pre-prompt `_GateFailure` — including one during `WORKSPACE_AUTHORITY` itself, once a workspace was already minted before `populate_semantic_task_workspace` raised — still reaches workspace removal, recorded under `CONFIRMED_NOT_SENT` per the table in §9.1.5 |
| Workspace removal returns but leaves residual files | §9.1.4 | `residual_file_count != 0` with `verified: True` is explicitly enumerated as a removal FAILURE by the strict predicate, never a partial success |
| Workspace removal raises | §9.1.4 | `try`/`except Exception` around the call reports `attempted=True, verified=False`, mirroring `run_i2b_live._run_outer_cleanup`'s existing accepted pattern; never escapes and never skips subsequent evidence construction |
| Cleanup fails after confirmed sent | §9.1.5 (`CONFIRMED_SENT` row) | Folded into `closure_established`, driving `INFRASTRUCTURE_CONTAMINATED` exactly as an existing teardown/shutdown/generated-config-cleanup failure already does |
| Cleanup fails after indeterminate dispatch | §9.1.5 (`SEND_STATE_INDETERMINATE` row) | Raw bounded facts plus an explicit unavailable-classification reason recorded on the attempt artifact; no classifier fabricated |
| Workspace exists before secret context | §9.2.2 | `workspace_absolute_path` is declared whenever `run_workspace is not None`, independent of `secret_context` — the field-independence rule exists specifically so this ordering can never suppress a real needle |
| Broker exists without secret context | §9.2.1 / §9.2.2 | Currently structurally unreachable in `run_semantic_task_attempt`'s own gate order (`SECRET_CONTEXT` strictly precedes `BROKER_SESSION`), stated explicitly rather than left as an accidental property; the frozen rule still requires broker fields be declared independent of `secret_context`'s presence so a future reordering or second call site cannot silently reintroduce the I2B-FU1 defect |
| Unexpected credential mechanism | §9.2.2 (`bearer_token` bullet) | `RouteDescriptor.__post_init__` already refuses any other mechanism at construction; the contract additionally requires a future safety-context builder that reads `route_descriptor` to assert the mechanism explicitly and REFUSE rather than default `bearer_token` if that assertion ever fails |
| Final model report absent | §9.3.3 (`UNAVAILABLE`) | Adapter exception/wrong-type return → bounded `UNAVAILABLE`, never `_GateFailure`, never touches `run_validity` |
| Final model report malformed | §9.3.3 (`MALFORMED`) | Well-typed observation whose claims fail bounded parsing → bounded `MALFORMED`, identical non-gating treatment |
| Final model report contradicts Git | §9.3.4 | Unchanged: `compare_report` already runs the comparison and records the disagreement in `report_accuracy` — a contradiction is a report-accuracy FINDING, never a `run_validity` change, exactly preserving today's accepted (and correct) behavior for an available-and-parseable report |
| Caller mutates original dict after result construction | §9.4.3 (bullets 1–2) | `MappingProxyType` wrap refuses the mutation with `TypeError`; the throwaway backing dict is never retained by the constructing scope for a caller to reach independently |
| Caller mutates sweep `task_results` after hard-bar calculation | §9.4.3 (bullets 4–5) | `MappingProxyType` wrap on `PrimarySweepResult.task_results` refuses `__setitem__`/`__delitem__`; `hard_bar_result` and `task_results` can no longer drift because neither can change after construction |
| Attempt artifact scrub refusal after workspace removal | §9.1.7 / §3.C (existing) | Workspace removal precedes evidence construction/scrub/emission (§9.1.3); a scrub refusal at that later step still substitutes the existing accepted `build_refusal_record` in place of the attempt artifact, and does not and cannot retroactively undo or misreport the workspace-removal truth already sealed into whichever record §9.1.5 said to attach it to |

---

## 6. What this document does not authorize

No implementation. No modification of `semantic_session.py`,
`semantic_controller.py`, `semantic_sweep.py`, `semantic_workspace.py`, their
tests, or any frozen qualification, AR2, or `src/` module. No live adapter. No Q1
or Q2 execution. No candidate run. No Pi/Node launch, credential read, socket, or
B300 contact. No abort/cancel/steer/follow-up command. No streaming or progress
inference. No provider-request observer. No generic multi-harness runtime
abstraction. No fixer, no second reviewer, no model-backed implementer. No
widening of `pi-implementer-qualification.v1`.

Real-workspace authority remains **NO-GO**.

---

## 7. Files changed by this turn

**FU1 (original):**

| File | Change |
|---|---|
| `docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md` | **new** — this document |
| `experiments/pi_implementer_qualification/README.md` | one status paragraph recording the HOLD and pointing here |
| `experiments/pi_implementer_qualification/FINDINGS.md` | one section recording the two blockers and the design decisions |

**FU1A (this turn):**

| File | Change |
|---|---|
| `docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md` | added the FU1A addendum blockquote, §9 (four closure contracts), §10 (adversarial check), and this updated §7/§8 |
| `experiments/pi_implementer_qualification/README.md` | narrowed the `5F3B-Q1-PRE1-DESIGN-FU1` verdict line from `READY FOR INDEPENDENT REVIEW` to `HOLD pending FU1A review`, with a pointer to §9 |
| `experiments/pi_implementer_qualification/FINDINGS.md` | narrowed the same verdict line for the identical reason |

No source file, no test, and no frozen module was modified or read-write
touched in either turn. `CLAUDE.md` was not modified. `semantic_session.py`,
`semantic_controller.py`, `semantic_sweep.py`, `semantic_workspace.py`,
`safety.py`, `i2_secret_context.py`, `i2b_workspace.py`, and every test file
are byte-identical to how this turn found them — every citation to them
above is a read-only line reference.

---

## 8. Verdicts

```text
5F3B-Q1-PRE1-DESIGN-FU1A       READY FOR INDEPENDENT REVIEW
5F3B-Q1-PRE1-DESIGN-FU1        HOLD  (pending FU1A review; was READY FOR INDEPENDENT REVIEW)
5F3B-Q1-PRE1-FU1               HOLD
5F3B-Q1-PRE1                   HOLD
Q1                             NO-GO
Q2                             NO-GO
Real-workspace authority       NO-GO
```
