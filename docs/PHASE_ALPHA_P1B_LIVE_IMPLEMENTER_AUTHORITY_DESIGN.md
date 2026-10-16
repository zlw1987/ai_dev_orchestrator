# ALPHA-P1B — Live Supervised Implementer Authority Design

> **CURRENT STATUS (2026-10-15, ALPHA-P1B-IMPL).** The operator adopted
> decisions D-1 to D-10 and authorized the **offline implementation and
> testing** of P1B. §11 records the adopted decisions and the two required
> refinements (D-6, D-9), and **supersedes** any conflicting statement in §0–§10,
> which are kept unchanged as design history. The implementation record is
> [PHASE_ALPHA_P1B_SUPERVISED_IMPLEMENTER_LIVE.md](PHASE_ALPHA_P1B_SUPERVISED_IMPLEMENTER_LIVE.md).
> Still **not** authorized: any live model request, any real source
> transmission, and any real-workspace access. The first live run needs the
> separate AUTH-PILOT decision (D-10) and a human-completed per-run consent.
>
> **ALPHA-P1B-FU1 (2026-10-15)** replaced evidence-directory consumption with a
> durable authorization ledger to close review blocker B-1. §11.6 supersedes
> R-10 and every statement that the evidence directory is the consumption
> ledger.
>
> *Original banner, as written for the design turn:*
>
> **DESIGN ONLY. AUTHORIZES NOTHING.**
>
> This document designs the smallest safe live extension of the ALPHA-P1A
> supervised implementer. It authorizes no implementation, no CLI command, no
> live request, no source transmission, no real-workspace access and no
> `CLAUDE.md` change. Each of those needs its own explicit operator
> authorization (§9).
>
> In the turn that wrote it: no code changed, no test was added, no model was
> contacted, no environment value was read, no socket was opened, no target
> workspace was touched, and `CLAUDE.md` was not modified.

| | |
|---|---|
| Kind | Phase design (live authority boundary) |
| Recorded | 2026-10-15 |
| Baseline | `4e02380` (P1A at `12f728c`, accepted and pushed) |
| Role / candidate / model | `supervised_implementer` / `SUP-D` / `qwen3.8-27b` |
| Backend | the operator's corporate OpenAI-compatible API, plaintext HTTP |
| Qualification credit | **none**, in either direction (policy §8) |
| Authorizes | **Nothing** |

**The endpoint is deliberately not written here.** The P1B prompt names the
corporate endpoint's URL. `CLAUDE.md` forbids placing a real internal endpoint
in canonical docs, runtime code or warning logic, so this document refers to it
only as "the corporate endpoint". It reaches AIDO only through the provider's
environment variables (§5.1). The operator's per-run consent names its host
(§3.2).

---

## 0. Verdict and frozen-contract check

**The live extension is designable without changing any frozen contract.** Its
implementation and its first run need three explicit decisions that do not
exist yet. None of them can be inferred from DEC-SUP.

| # | Authority | What it says | Effect on P1B |
|---|---|---|---|
| C-1 | `CLAUDE.md` "Current non-goals" and its final paragraph | "No model-backed implementer". Real model calls exist "only behind the three explicitly gated commands … nothing else may call a model." | **Not a prohibition on this design:** the same section permits additions "a future prompt explicitly asks" for. But a P1B implementation adds a fourth model-calling command and a live model-backed implementer. That would make both sentences **mechanically false**, a lifecycle-truthfulness defect under policy §1. DEC-SUP item 8 was never decided, and P1A accepted the staleness only for an *offline* library. **The implementation authorization must decide D-1** (§9): authorize a narrow `CLAUDE.md` update, or explicitly accept a live-path staleness. |
| C-2 | Policy §8, "Still not authorized" | Lists any live Qwen 3.8 request, any real-source transmission, and a CLI command for the supervised implementer | P1B implementation needs an appended policy amendment (proposed: §9, DEC-SUP-LIVE) that authorizes the **commands**. The **first live request** stays separately authorized per run (§2.1). |
| C-3 | Policy §3 closing paragraph, roadmap M4/M5 | The supervised branch "does not bypass the existing M4/M5 authority graph" | **No contradiction.** P1B writes nothing and stops before H6. Any later write goes through the unchanged 5F0 approval and the 5F2C writer, the same path Alpha-0 used with an external supplier. P1B adds no real-workspace implementer authority, which is M5's subject. |
| C-4 | L2 design §9 | A model-backed L2 needs "its own design document, its own project config block, its own flag, its own command". Source context must be path-bounded, size-bounded and announced in a non-suppressible banner before transmission | Satisfied by this document, the existing `supervised_implementer` block plus one new opt-in field (§2.4), two new flags, and the commands in §6. |
| C-5 | `CLAUDE.md` / P1A memory rule | Never place a real internal endpoint in code or docs | Honored (see above). |
| C-6 | DEC-SUP item 7 | Zero semantic retries and zero transport retries | Preserved exactly (§4). |

No frozen candidate evidence, hard bar, `CANDIDATE_MODEL_IDS` entry or
historical result is read as authority, modified, or reinterpreted.

---

## 1. Current P1A baseline and reuse points

P1A (`src/ai_dev_orchestrator/supervised_implementer/`) is offline and
library-only. Its runner accepts exactly `httpx.MockTransport`. No CLI command
reaches it.

| P1A element | Location | P1B use |
|---|---|---|
| Gate on the config block: strict types, `SUP-D ⇔ qwen3.8-27b`, `provider ∈ {litellm, vllm}` | `implementer.py: check_supervised_implementer_gate` | **Reuse unchanged.** P1B adds one separate check for the new live opt-in (§2.4). |
| Endpoint check: `https`, or `http` only with `allow_insecure_http`; refuses embedded credentials | `check_supervised_implementer_endpoint` | **Reuse and tighten.** Also refuse a query or fragment, and return the effective port (finding A-5). |
| Private re-validated copies of plan and config | `_private_copies` | **Reuse.** The canonical JSON of these copies is also what P1B digests (§3.1). |
| Identity and target-path checks (`files_likely_to_change`, not out of scope, `PathPolicy` ALLOWED, normal form) | `_check_identity`, `_check_target_path` | **Reuse unchanged.** |
| In-process Phase 5D2 bounded read, plus target-item checks (read, file, unredacted, canonical spelling) | `workspace/content_read.py`, `_target_item` | **Reuse unchanged**, in both `prepare` and `run`. |
| Writer text-domain pre-check and in-memory reachability proof | `_writer_text_domain_lines`, `_check_post_image_reachable` | **Reuse unchanged.** |
| Request builder: one JSON-encoded data object, fixed system text, generated schema | `request.py` | **Reuse unchanged.** P1B adds a digest over the canonical request (§3.1). |
| Strict output parser: exactly `{"content_text": str}`, rejected and never repaired | `models.py: parse_supervised_implementer_output` | **Reuse unchanged.** |
| AIDO-assembled `proposed-content.v1` with fixed prose; `build_deterministic_diff_proposal` | `implementer.py` steps 8–9 | **Reuse unchanged.** The assumption template's "through an offline mock transport" wording becomes transport-specific (§3.4). |
| `SourceTransmissionNotice` banner | `models.py` | **Reuse.** Add the run id and the authorization digest. `transport_kind` gains `live_http`. |
| `supervised-implementer-provenance.v1` and the result cross-check | `models.py` | **Do not widen v1.** P1B adds **v2** (§3.4). v1 keeps its meaning, *offline mock only*, and is never reinterpreted. |
| `run_supervised_implementer_offline` | `implementer.py` | **Kept, MockTransport-only, behavior unchanged.** The live path is a separate entry that never accepts a caller-supplied transport (A-18). |
| Provider-isolated environment reader (5F2E-V1-FU1) | `review/reviewer.py: reviewer_env_names_for_provider`, `_load_vllm_client_config`, `build_reviewer_client_config` | **Reuse the shape**, as a supervised-implementer function that resolves the provider to an exact name tuple before touching the environment (§5.1). |
| RS1-FU2 AIDO-owned wait deadline: one daemon worker, a one-shot slot, `Event.wait`, no join | `review/supervision.py: _await_reviewer_response` | **Reuse the pattern, not the module** (§4.2). The reviewer module stays untouched. |
| Lexical "outside the workspace" guard for operator artifacts | `cli.py: _is_same_or_under` | **Reuse** for the authorization file and the evidence directory, plus a canonical-path check (A-14). |
| H6 approval path (`approved-diff-proposal.v2`, exact phrase, `source: manual`) and the 5F1 preview | `file_editing`, Alpha-0 runbook step 6 | **Unchanged and not invoked.** P1B stops before it. |

Also unchanged: `LLMClient`, `LLMClientConfig`, the `AIDO_LITELLM_MAX_RETRIES`
semantics for every other caller, the reviewer, the verifier, the writer,
`CANDIDATE_MODEL_IDS`, and every frozen qualification artifact.

---

## 2. Proposed live authority and lifecycle

### 2.1 Three separate authorizations

| # | Authorization | Grants | Does **not** grant |
|---|---|---|---|
| **AUTH-IMPL** | Operator prompt for the P1B implementation, plus policy amendment DEC-SUP-LIVE | Writing the code and the two commands, tested offline only (`httpx.MockTransport` behind the private test seam, synthetic `tmp_path` repos) | Any live request; any real source transmission |
| **AUTH-PILOT** | Operator decision naming the pilot repository, clone and target | Running the commands **once** against that disposable clone | H6 approval or a write. A second run needs a fresh decision. |
| **CONSENT (per run)** | The human-completed `supervised-implementer-authorization.v1` artifact (§3) | Exactly one HTTP request carrying exactly one bound source, to one bound endpoint, model and stage | Anything after `next_step: human_exact_diff_approval_required` |

Enabling a config field never grants per-run consent, and a per-run consent
never carries over to another run (§3.3).

### 2.2 Lifecycle

```text
H1  disposable clean clone + target chosen by the human         (operator; AUTH-PILOT)
H2  approved L1 plan (exact phrase, unchanged 5B)               (human)

P1  l2-supervised-implementer-prepare                           offline: no env read, no network
      gates → private copies → identity → target → 5D2 read in-process
      → writer-domain check → build the exact request → digests
      → write authorization DRAFT (bound section + empty consent) outside the workspace
      → state: PREPARED

H4S human source-transmission consent                           (human edits the consent block only)
      exact phrase(s), endpoint scheme/host/port typed by the human, binding digest echoed
      → state: CONSENTED

P2  l2-supervised-implementer-run
      a. flags; config; gates incl. live opt-in                  nothing read yet beyond config
      b. authorization + evidence-dir outside workspace; strict parse; expiry
      c. re-derive EVERYTHING in-process; compare to the bound section exactly
      d. provider-isolated env read; endpoint == consent         still nothing sent; auth NOT consumed
      e. CONSUME: exclusive-create <evidence>/<run_id>/CONSUMED  → state: CONSUMED
      f. write+fsync run-record {state: transmission_pending}
      g. non-suppressible stderr banner (announce)               failure here → nothing sent
      h. ONE request: one daemon worker, AIDO monotonic deadline, bounded transport
      i. reply checks → strict parse → proposed-content → 5E3 diff → reachability
      j. write evidence; run-record → terminal state
      → STOP: next_step = human_exact_diff_approval_required

    terminal states (exactly one, recorded):
      refused_before_transmission     (a–g failed; nothing handed to the transport)
      diff_proposed | no_change_proposed
      transport_failed | implementer_stalled | response_too_large
      output_rejected | evidence_incomplete

H6  (NOT part of P1B) exact-diff approval via the unchanged 5F0 path, under its own authorization
```

### 2.3 Non-negotiable invariants

- **I-1 Write authority: none.** P1B opens no workspace file for writing,
  creates no approval or approval draft, applies nothing, runs no verification,
  and performs no Git operation. Evidence is written only under an evidence
  directory that is proven outside the workspace.
- **I-2 One bound source per run.** The transmitted text is the in-memory
  result of the run's own 5D2 read. Its SHA-256 must equal the consented
  `source_sha256`. A saved packet is never transmission authority (DEC-SUP
  item 4).
- **I-3 One request per run.** One semantic request. Transport retries are
  zero at both the `LLMClient` and the `httpx.HTTPTransport` layers. A
  counting transport wrapper refuses a second request outright (A-11).
- **I-4 The model chooses nothing.** It chooses no path, change type, endpoint,
  model, retry, prose in the approval surface, or lifecycle transition. Only
  `content_text` comes from the model.
- **I-5 Consent is per run, single-use, bound and fail-closed** at consumption
  (§3).
- **I-6 Stall is terminal.** AIDO's wait ending is not cancellation (§4.3).
- **I-7 No credential in any artifact, stdout or stderr.** That includes an
  unexpected-exception path (A-6).
- **I-8 Unlimited product tokens by default.** No `max_tokens` is sent unless
  the operator configures a positive cap. The response-size bound limits
  **bytes AIDO will buffer**. It is not a token budget, and it is never sent
  (§4.4).
- **I-9 SUP-D earns nothing.** Every record carries
  `qualification_credit: "none"` and `autonomous_implementer_qualified: false`.
  No qualification record may reference it.

### 2.4 Configuration: one new opt-in, one wait bound

`SupervisedImplementerConfig` (strict, frozen) gains exactly two fields.

| Field | Type / default | Meaning |
|---|---|---|
| `live_transmission_enabled` | `bool = False` | The project permits the live commands at all. **Separate from `enabled`**, because P1A documented `enabled` as creating no live entry point. Reinterpreting it would silently upgrade every offline-enabled config to live-capable (A-1). This field grants **no** consent. |
| `attempt_timeout_seconds` | `float`, `gt=0`, `le=3600`, no NaN or inf; default per D-4 | AIDO's own wait bound for the one request (§4.2). It is also passed to the client as a *secondary* network-inactivity timeout, never as the proof. It is bound into the authorization. |

No field is added for an endpoint, base URL, key, environment-variable name,
retry count, fallback model, prompt, response-size override or multi-file
switch. `allow_insecure_http`, `structured_output` and `max_output_tokens` keep
their P1A meanings. Every existing config loads unchanged.

---

## 3. Consent and evidence contracts

### 3.1 `supervised-implementer-authorization.v1`

The schema is strict, frozen and `extra="forbid"`. Facts are `Literal` types,
digests match `^[0-9a-f]{64}$`, and integers are strict. It has two sections.

**`bound` — written by `prepare`, never edited by the human.**

| Field | Value / source | Requirement it binds |
|---|---|---|
| `schema_version` | `Literal["supervised-implementer-authorization.v1"]` | — |
| `run_id` | 32 lowercase hex characters from `secrets.token_hex(16)`, minted by `prepare` | Run identity |
| `stage` | `Literal["propose_diff_stop_before_h6"]` | Execution stage |
| `authorized_http_requests` | `Literal[1]` | Request count |
| `authorized_semantic_requests` | `Literal[1]` | Request count |
| `role` / `candidate` / `model` | `Literal["supervised_implementer"]` / `Literal["SUP-D"]` / `Literal["qwen3.8-27b"]` | Implementer identity and exact model |
| `provider` | `Literal["litellm", "vllm"]`, from config | Backend family |
| `project_id`, `repo`, `issue_number` | From the re-validated copies | Task |
| `approved_plan_sha256` | SHA-256 of the canonical JSON of the re-validated `ApprovedL1PlanArtifact` (includes its H2 approval) | Approved task and plan |
| `project_config_sha256` | SHA-256 of the canonical JSON of the re-validated `ProjectConfig`. It covers `workspace_path`, the path policy, the 5D2 caps and every `supervised_implementer` field | Workspace, policy and opt-ins |
| `target_path` | Repo-relative, normal form | Allowed file |
| `change_type` | `Literal["modify"]` | — |
| `source_sha256`, `source_bytes` | Over the 5D2 in-memory text (UTF-8) | Exact source identity |
| `request_sha256` | Over the canonical serialization of the whole `LLMRequest` (model, messages, `max_tokens`, `response_format`, temperature), sorted keys and compact separators. **It is not the wire bytes** (§3.5). | Exact content transmitted |
| `structured_output_mode` | `Literal["json_schema", "none"]` | Request shape (redundant with `request_sha256`, kept for readability) |
| `requested_max_output_tokens` | `int \| None` | Same |
| `attempt_timeout_seconds` | From config | Runtime bound |
| `max_response_body_bytes` | The fixed AIDO constant (§4.4) | Runtime bound |
| `allow_insecure_http` | From config | Transport acknowledgement (project level) |
| `evidence_dir_sha256` | SHA-256 of the canonical absolute evidence-directory path | Ties the consent to one consumption ledger (A-7) |
| `prepared_at`, `expires_at` | UTC; `expires_at = prepared_at + AUTH_TTL` (D-7) | Staleness |
| `aido_version` | Package version string | Diagnostics only. Not authority. |
| `binding_sha256` | SHA-256 over the canonical JSON of every field above | The value the human echoes |

The bound section contains **no** source text, absolute path, base URL, key or
environment value. The evidence directory appears only as a digest.

**`consent` — written by the human.** The draft carries it empty, so a draft
never parses as consented.

| Field | Rule |
|---|---|
| `consented_by` | Non-blank, at most 200 characters |
| `consented_at` | ISO-8601 **with offset**; must satisfy `prepared_at ≤ consented_at ≤ now` (with a small clock-skew allowance) |
| `source` | `Literal["manual"]` |
| `binding_sha256` | Must equal `bound.binding_sha256` **and** a fresh recomputation over `bound` |
| `endpoint_scheme` | `Literal["https", "http"]`, typed by the human |
| `endpoint_host` | Exact host string, typed by the human. Compared to the environment-resolved host after IDNA/lowercase normalization, which is the only normalization. |
| `endpoint_port` | Strict int, the **effective** port (443 or 80 when the URL omits it) |
| `consent_text` | Exactly `I consent to sending this one approved file to this model and endpoint for one supervised implementer request` |
| `plaintext_acknowledgement` | **Required and exact iff `endpoint_scheme == "http"`:** `I acknowledge this transmission is NOT TLS-ENCRYPTED`. It must be absent for `https`. A present-but-unneeded acknowledgement is refused, not ignored. |

The consent text is distinct from the H2 plan sentence and the H6 diff
sentence, and each of those is refused here.

### 3.2 Consumption-boundary validation (run step c)

`run` trusts nothing from `prepare`. It re-derives every bound value in-process
and compares each one **exactly**. Any mismatch refuses before the environment
is read and before consumption. Nothing is sent, and the authorization is left
unconsumed, so a fresh `prepare` is the only remedy.

| Check | Fails closed when |
|---|---|
| Strict parse, consent complete | Any missing, extra or wrongly typed field; a draft; a wrong phrase; an acknowledgement present for `https` or missing for `http` |
| `binding_sha256` recomputation | `bound` was edited after the draft was made |
| `now < expires_at` | The consent is stale |
| `run_id` not already consumed in this evidence directory | Replay (§3.3) |
| `evidence_dir_sha256` | The authorization was moved to a different ledger |
| Config gate and `live_transmission_enabled is True` | Opt-in absent, or forged after load |
| `project_config_sha256` | Config changed since prepare. This covers toggles such as `allow_insecure_http`, `structured_output` and the timeout. |
| `approved_plan_sha256`, identity, `issue_number` | A different plan, project or task |
| `target_path`, then the 5D2 read, then `source_sha256`/`source_bytes` | A different file, or the file's bytes changed |
| `request_sha256`, recomputed on the object that will be sent | Prompt template, plan prose, model, `max_tokens` or schema drift (including an AIDO upgrade between prepare and run) |
| Environment-resolved scheme, host and port equal the consent, **after** the provider-isolated read | Hidden endpoint substitution (A-2, A-3); a TLS downgrade |

The comparisons use `==` on exact `str` and `int` types. There is no
truthiness, prefix match or case folding, except the one stated host
normalization.

### 3.3 Single use, replay and staleness

- **Consumption is an atomic exclusive create** of
  `<evidence_dir>/<run_id>/CONSUMED`, using `open(..., "x")` (`O_EXCL`), which
  is atomic on NTFS. It happens **after** all validation and the environment
  read, and **before** the banner and the request. Two concurrent invocations
  cannot both succeed.
- A consumed authorization is **never** reusable, whatever the outcome:
  refused-after-consumption, success, stall, rejection or crash. Repeating
  requires `prepare` again and new human consent, with a new `run_id`.
- The marker contains `run_id`, `binding_sha256` and the consumption time only.
- **Scope of the claim:** the artifact is unsigned. Consumption guards against
  stale, replayed, copied or mismatched consent **by accident or
  misconfiguration**. It does not defend against an operator who deliberately
  recomputes `binding_sha256` after editing, or against in-process Python that
  calls lower-level functions directly (§7, A-19). The operator is the
  authority in this threat model, and the human is the trust root, as with H2
  and H6.

### 3.4 Evidence records (all under `<evidence_dir>/<run_id>/`)

Every file is created exclusively (`"x"`) and never overwritten. Writes use a
temporary file then `os.replace`, inside the run directory. `run-record.json`
is fsynced before transmission.

| File | Written | Contents | Sensitive class |
|---|---|---|---|
| `CONSUMED` | step e | `run_id`, `binding_sha256`, time | none |
| `authorization.json` | step e | A byte copy of the consumed authorization | none (digests, host) |
| `run-record.json` | step f (`transmission_pending`), finalized at step j | State machine (§4.5), timestamps, outcome category, `transmission_attempted` | none |
| `request-messages.json` | step f | The exact `LLMRequest` canonical JSON whose digest is `request_sha256` (D-5) | **Source:** the full target file text and redacted plan prose. It is local only and never printed. |
| `response-content.txt` | step j, **only** for a reply that passed the strict parser **and** the 5E3 secret check (D-5) | Assistant `content` exactly | Source-derived |
| `diff-proposal.json` | step j, on `diff_proposed` / `no_change_proposed` | Unchanged `diff-proposal.v2` | Source-derived (diff lines) |
| `provenance.json` | step j | `supervised-implementer-provenance.v2` | none (digests, host) |

The following are **never written anywhere**: the API key or placeholder, the
base URL, request headers, the raw HTTP body, the provider's
`reasoning`/`reasoning_content` field, a rejected reply's content, environment
values, absolute workspace paths, or tracebacks. A rejected reply is recorded
by **digest and length only**, so a secret-shaped model output is never
persisted.

**`supervised-implementer-provenance.v2`** keeps every v1 field and meaning
except `transport_kind`, which becomes `Literal["live_http"]`. v1 remains
offline-mock only and is never reinterpreted. v2 adds:

```text
run_id, authorization_binding_sha256, request_sha256
aido_requested:   model, provider, requested_max_output_tokens (null = not sent),
                  structured_output_mode, attempt_timeout_seconds, max_response_body_bytes
transport_observed (by AIDO's own counting transport wrapper and clock):
                  endpoint_scheme, endpoint_host, endpoint_port, transport_tls,
                  environment_proxies_consulted: false, redirects_followed: false,
                  http_requests_handed_to_transport: 1, response_status_class: "2xx",
                  response_body_bytes, response_content_encoding: "identity",
                  elapsed_seconds (monotonic), stall_source: null
server_reported (claims, not facts):
                  response_model_field (normalized; equals the request when the server omitted it),
                  finish_reason, usage_reported (null = unknown, never zero)
aido_derived:     source_sha256, response_content_sha256, proposed_content_sha256,
                  pre/post_image_sha256 cross-checked with the diff (unchanged validator)
negative claims, orchestrator-scoped only:
                  orchestrator_approval_created: false, orchestrator_workspace_written: false,
                  orchestrator_git_operations: false, orchestrator_retries_issued: 0
backend lifetime, conditional wording only:
                  backend_inference_lifetime_if_stalled: "not observed; ..."
```

The assumption prose in `proposed-content.v1` becomes transport-specific, for
example "…through a live HTTP request (run `<run_id>`)…". It is still
AIDO-fixed, built only from registry values and `run_id`.

### 3.5 Traceability chain

```text
approved plan ─approved_plan_sha256─┐
project config ─project_config_sha256┤
5D2 in-memory read ─source_sha256────┼─► authorization.bound ─binding_sha256─► consent (human)
LLMRequest ─request_sha256───────────┘                                          │
                                                                                ▼ consumed (run_id)
request-messages.json ══ request_sha256 (recomputable offline)                  │
response content ─response_content_sha256─► strict parse ─proposed_content_sha256
                                                    │
                    proposed-content.v1 (AIDO-built) ─► 5E3 diff-proposal.v2
                       pre_image_sha256 == source_sha256 ; post_image_sha256 == proposed_content_sha256
                                                    │
                    provenance.v2 (cross-checked by validator) ─► STOP before H6
H6 (later): approved-diff-proposal.v2 wraps the untouched diff-proposal.v2 ─► 5F2C pins both digests on disk
```

**What it does not prove.** `request_sha256` is AIDO's canonical
serialization, not the wire bytes, because httpx serializes the body. The
response digest covers the normalized assistant `content`, not the raw body.
`response_model_field` is a server claim. None of the digests proves that the
content is correct, safe or minimal.

---

## 4. Runtime supervision and failure semantics

### 4.1 Request issuance

- `LLMClientConfig.max_retries` is forced to `0` on a private copy, overriding
  any `AIDO_LITELLM_MAX_RETRIES` (P1A behavior, unchanged).
- The transport is built by AIDO: `httpx.HTTPTransport(retries=0)` wrapped in
  the **bounded counting transport** (§4.4). It is passed explicitly to
  `LLMClient`, so httpx does not consult environment proxies (A-3) and does
  not follow redirects. A 3xx response is a terminal `transport_failed`.
- **No other HTTP request is made:** no `/v1/models` listing, no health check,
  no warm-up. An HTTP 200 from anything is not qualification evidence.

### 4.2 AIDO-owned wait deadline (RS1-FU2 pattern)

One daemon worker per run performs exactly `client.chat(request)` and
publishes the response or exception into a one-shot slot. The main thread
waits with `Event.wait(attempt_timeout_seconds)`. The rules:

- no join, no executor, no pool, no thread kill, no socket close from the
  supervisor, no asyncio, no process;
- a deadline expiry and an `LLMTimeoutError` both produce
  `implementer_stalled`, distinguished only by the audit field `stall_source`
  (`supervisor_deadline` | `client_timeout`). Nothing branches on it;
- **terminal**: no second request, no sleep-and-retry, no backoff, no
  cancellation call, no streaming.

**Recommendation: implement the mechanism inside the supervised-implementer
package**, as a private copy of the ~40-line RS1-FU2 function, rather than
extracting a shared helper from `review/supervision.py`. That keeps the
accepted reviewer module byte-identical and avoids creating a "reusable task
framework". A test asserts the copy's properties (daemon, single start, no
join, terminal stall, at most one abandoned worker).

### 4.3 Timeout is not cancellation

```text
AIDO wait ended  !=  worker stopped  !=  HTTP request cancelled  !=  backend inference stopped
```

After a stall, AIDO records `implementer_stalled`. It states that the abandoned
worker, the HTTP request and the backend inference may still be active, and
that no cancellation was requested or observed. It never writes "cancelled",
"terminated" or "the runtime is bounded". The stderr notice tells the operator
that an immediate re-run could give the same local model two concurrent jobs.
The re-run needs fresh consent anyway (§3.3).

### 4.4 Response-size bound (bytes, not tokens)

The shipped client reads the whole body before `content_text`'s 1,000,000
character cap applies, and the provider may include a large reasoning field.
P1B adds a **transport-level byte bound**, independent of any token setting:

- `MAX_RESPONSE_BODY_BYTES`, a fixed AIDO constant. The recommended value is
  16 MiB: worst-case JSON escaping of 1,000,000 astral characters is about
  12 MB, plus envelope and reasoning headroom (D-8). It is never sent to the
  server and never derived from a token count.
- The counting wrapper replaces the request's `Accept-Encoding` with `identity`
  and **refuses a response with any other `Content-Encoding`**. Counting
  compressed bytes would not bound what httpx decodes into memory (A-4).
- It refuses up front when `Content-Length` exceeds the bound. Otherwise it
  wraps the response stream and raises the private `_ResponseTooLarge` the
  moment the cumulative count passes the bound. Bytes past the bound are not
  buffered.
- It refuses a **second** `handle_request` call on the same run (I-3), and it
  records `response_body_bytes` and the status class as observed facts.
- `_ResponseTooLarge` is not an `httpx.TransportError`, so `LLMClient` cannot
  swallow or retry it. The worker republishes it, and the supervisor maps it to
  `response_too_large` (terminal).

### 4.5 Outcome table

| Terminal state | Cause | Handed to transport? | Authorization | Exit | Evidence |
|---|---|---|---|---|---|
| `refused_before_transmission` | Any check in steps a–d | no | **not** consumed | 1 | none, or a stderr category |
| `refused_before_transmission` | Steps e–g: consumption race lost, evidence write failed, banner write failed | no | consumed (except on a lost race) | 1 | Marker and run-record with `transmission_attempted: false` |
| `transport_failed` | Connect error, 401/403, other 4xx (including a structured-output rejection), 429, 5xx, 3xx, malformed body, non-identity encoding | yes | consumed | 4 | run-record, provenance-less failure record |
| `implementer_stalled` | Deadline or client timeout | yes | consumed | 4 | Same, plus `stall_source` and the conditional lifetime notes |
| `response_too_large` | Byte bound exceeded | yes | consumed | 4 | Same |
| `output_rejected` | Model-field mismatch, `finish_reason != "stop"`, strict-parse failure, `proposed_content_invalid`, `diff_generation_refused`, `post_image_unreachable`, `result_inconsistent` | yes | consumed | 4 | Category, response digest and length only |
| `diff_proposed` / `no_change_proposed` | Accepted | yes | consumed | 0 | All §3.4 files |
| `evidence_incomplete` | A reply was received but final evidence could not be written | yes | consumed | 5 | Pending run-record. Stderr says that transmission occurred and the outcome is not fully recorded. |

There is no automatic second request in any row. A structured-output server
rejection gets no unstructured fallback. `finish_reason: length` is rejected
as `incomplete_reply`, and its message must not claim that an AIDO-requested
budget was exhausted when `requested_max_output_tokens` is null.

### 4.6 Partial failure and crash

- **Before consumption:** nothing is persisted, and the authorization stays
  valid until it expires.
- **Between consumption and the banner:** the run-record says
  `transmission_attempted: false`, and the authorization is spent.
- **Crash after the pending run-record is fsynced:** the run directory shows
  `CONSUMED` plus `transmission_pending` with no terminal state. The operator
  procedure (§6.3) treats that as "transmission may have occurred".
- AIDO performs no cleanup, restore, retry or deletion of evidence.

---

## 5. Transport and credential boundaries

### 5.1 Provider-isolated environment read

A new function, `supervised_implementer_env_names_for_provider(provider)`,
answers from the provider alone, **before** any environment access. It returns
the same exact tuples as the reviewer: LiteLLM's five names, or vLLM's two (D-3
covers a dedicated namespace instead). Only `run` calls it, once, after every
offline check. `prepare` reads no environment at all.

- **`litellm`:** the shipped loader. `default_model` is overridden by the
  registry model, `max_retries` is forced to `0`, and `timeout_seconds` is set
  to `attempt_timeout_seconds` as a secondary bound.
- **`vllm`:** `AIDO_VLLM_BASE_URL` is required and `AIDO_VLLM_API_KEY` is
  optional. With no key, the fixed non-secret placeholder `no_api_key` is used
  for client-shape compatibility. It is never described as authentication.
- The other provider family's names are never looked up. A regression test
  uses a mapping that raises on any unexpected key access.

### 5.2 Endpoint

- The base URL comes from the environment only, never from config or the CLI.
- It is refused with userinfo, a query or a fragment, or with a scheme other
  than `http`/`https` (A-5). It is never echoed.
- `http` requires **both** the project's `allow_insecure_http: true` **and**
  the per-run `plaintext_acknowledgement` phrase. Neither is a security claim.
  The banner says `NOT TLS-ENCRYPTED`. An internal or same-network endpoint is
  not private because of where it sits.
- Scheme, host and effective port must equal the human-typed consent values.
  The base-URL path is not consent-bound. Its SHA-256 is recorded in the
  run-record for traceability.
- `https` uses httpx's default certificate verification. No option disables it.

### 5.3 Model

- The model comes from the registry via config. It is bound in the
  authorization and the request digest. No CLI or environment override exists.
- A reply whose normalized `model` field differs is rejected
  (`model_substitution`). Equality is weak evidence and is labeled as a server
  claim.
- No fallback model, no second candidate, no provider failover.

### 5.4 Credential hygiene

- The key exists only in the private `LLMClientConfig` (`repr=False`) and the
  `Authorization` header built inside `LLMClient`. P1B never calls
  `model_dump()` or `model_dump_json()` on a client config outside the private
  copy step, and never persists either.
- **The command boundary catches every exception** and prints only a category
  and a fixed message. No traceback reaches stderr. An uncaught exception
  renders a traceback with the chained exception texts, and those may include
  the request URL. Rendering local variables is off in the installed Typer
  (0.27.1, `pretty_exceptions_show_locals` defaults to `False`). If it were
  turned on, a local `env` mapping would print the raw key, so a test pins
  that setting too (A-6).
- The environment mapping is dropped once the client config is built.
- Tests plant sentinel values for every provider variable, force the expected
  and the unexpected failure paths, and scan stdout, stderr and every evidence
  file for each sentinel.

---

## 6. Initial CLI interface and operator workflow

### 6.1 Commands

The two new commands are the only live entry points. Neither changes any
existing command's option set.

```text
l2-supervised-implementer-prepare
    --project-config PATH            (exists)
    --approved-plan PATH             outside the workspace (lexical check before read)
    --target-path TEXT               repo-relative; the human's choice
    --evidence-dir PATH              outside the workspace (lexical + canonical); digested into the authorization
    --out PATH                       authorization DRAFT; outside the workspace; created exclusively
    --prepare-supervised-implementation   required flag
  Reads: config, plan, the 5D2-approved files. No environment, no network, no client.
  Prints (stderr): target, source bytes/sha256, model, provider, run_id, expires_at,
                   binding_sha256, and the exact consent phrase(s) to type.
  Exit: 0 draft written; 1 refused.

l2-supervised-implementer-run
    --project-config PATH
    --approved-plan PATH
    --authorization PATH             consented artifact; outside the workspace
    --evidence-dir PATH              must hash to bound.evidence_dir_sha256
    --transmit-approved-source       required flag (consent to send source)
    --real-implementer               required flag (consent to contact a real model)
  Exit: 0 proposal produced (diff or no change); 1 refused, nothing handed to the transport;
        4 transmission attempted, no usable proposal; 5 transmission attempted, evidence incomplete.
  Stdout: provenance.v2 JSON only. The diff proposal is in the evidence directory.
  Stderr: the non-suppressible SOURCE TRANSMISSION banner (provider, model, host, port,
          scheme, TLS / NOT TLS-ENCRYPTED, file, bytes, sha256, run_id), then outcome lines.
```

There are no `--model`, `--endpoint`, `--base-url`, `--api-key`,
`--provider`, `--timeout`, `--max-tokens`, `--retries`,
`--allow-insecure-http`, `--structured-output` or `--force` options. Both
flags are checked with `is True` before any file is read.

### 6.2 First live pilot procedure (requires AUTH-PILOT)

1. **H1.** Make a fresh disposable `git clone` of the chosen low-risk
   repository, never a working checkout and never the Alpha-0 clone. Choose one
   tracked text file. Record HEAD and a clean `git status` with the operator
   helper snapshot. The P1B commands add no Git subprocess caller (D-6).
2. **H2.** Approve the L1 plan with the exact plan phrase. Validate it offline
   with `l2-dry-run`.
3. Configure `supervised_implementer`:
   - `enabled: true`, `live_transmission_enabled: true`;
   - `candidate: SUP-D`, `model: qwen3.8-27b`, `provider` per D-2;
   - `allow_insecure_http: true` (corporate endpoint is plaintext);
   - `structured_output` per D-9;
   - `max_output_tokens` absent.
   Also configure `read_only_workspace_content.enabled: true` with caps that
   admit the file.
4. Run `prepare`. Read its summary.
5. **H4S.** In a fresh window, set **only** the configured provider's
   variables and clear the other family. This matters because this machine
   persists `AIDO_*` reviewer variables. Fill the consent block: the phrase,
   the acknowledgement, the endpoint scheme, host and port, and
   `binding_sha256`.
6. Run `run` with both flags. Confirm the banner names the expected host,
   port, model and `NOT TLS-ENCRYPTED`.
7. Inspect `<evidence>/<run_id>/`. Re-check the clone's HEAD, clean status and
   target hash with the helper snapshot. All three must be unchanged, because
   P1B writes nothing.
8. **STOP.** The pilot ends at `human_exact_diff_approval_required`. Continuing
   to H6/H7/H8/H9 needs its own authorization, reuses the unchanged Alpha-0
   steps 6–10, and must end H10 in COMMIT or RESTORE. The pilot itself never
   commits or pushes.
9. Record that the pilot **qualifies nothing**.

### 6.3 Interpreting a failed or interrupted run

- Exit 1 with no run directory means nothing was sent and the authorization is
  reusable until it expires.
- A run directory with `CONSUMED` means the authorization is spent. Run
  `prepare` again.
- `transmission_pending` without a terminal state, or exit 5, means the source
  **may have been transmitted**. Treat it as sent.
- After a stall, the backend may still be running inference. Wait before
  preparing a new run, and do not expect AIDO to report when it ends.

---

## 7. Adversarial analysis and minimum regression requirements

### 7.1 Authority-bearing objects

"Observed" means AIDO checks it mechanically at consumption. "Claim" means it
comes from the model, the server or the runtime and is never authority.

| Object | Creator → permitted mutators | Provenance evidence | Bypass / mismatch risk | Consumption validation | Type / truthiness | Post-validation mutation | Partial failure | Diagnostic exposure | Observed vs claim |
|---|---|---|---|---|---|---|---|---|---|
| Project config + `live_transmission_enabled` | Operator file → none at runtime | Loader, strict model, `project_config_sha256` | Offline-enabled block becoming live (A-1); toggles between prepare and run | Gate + digest | Strict bool, `is True` | Private re-validated copy | — | Errors name fields, never values | Observed |
| Approved plan (H2) | Human → none | Exact phrase, strict parser, digest | Different plan or task | Digest + identity | `Literal` / strict | Private copy | — | Plan prose not echoed | Observed (approval is the human's) |
| Target path | Human (CLI) → none | Bound in the authorization | Model-chosen path; case or traversal variants | Exact `==` + P1A checks | `type is str` | Copied string | — | Path only | Observed |
| 5D2 source read | AIDO in-process → none | `source_sha256` | Saved packet substituted; file changed after prepare | Re-read + digest | — | **Transmitted bytes are the in-memory text that was digested** (A-8) | — | Source never echoed | Observed |
| Authorization draft (`bound`) | `prepare` → none | `binding_sha256` | Edited bound fields; stale draft | Recompute + compare all fields | Strict / `Literal` | Frozen model | Exclusive create, so no overwrite | No source, URL or key | Observed |
| Consent | Human → none | Exact phrase, echoed binding digest, `source: manual` | Inferred from config; H2/H6 phrase reused; acknowledgement on https | Strict parse + exact phrases | `Literal`, timezone-aware datetime | Frozen | — | — | Human statement |
| Consumption marker | `run` → none | `O_EXCL` create | Replay; concurrent runs; copied to another directory (A-7) | Exclusive create + `evidence_dir_sha256` | — | — | Spent on every outcome (§4.6) | — | Observed |
| Environment / client config / key | Process environment → none after the private copy | Provider-isolated reader | Other family read; persistent reviewer variables (A-2) | Endpoint == consent | `str` checks | Client built from the checked private copy before the banner (P1A R-2) | — | **Key in tracebacks or locals (A-6)** | Observed (scheme, host, port) |
| Transport | AIDO only (live). The test seam is private. | Wrapper counts requests and bytes | Env proxies (A-3), redirects, transport retries, a second request (A-11), decompression (A-4) | Wrapper invariants | — | Built once, never caller-supplied (A-18) | Failure is terminal | Exception categories only | Observed |
| `LLMRequest` | AIDO builder → none | `request_sha256` | Mutable pydantic model, so messages could change after the digest (A-9) | Recompute on the exact object handed to the worker | — | Re-validated copy; digest re-checked just before worker start | — | Never printed | Observed (canonical, not wire) |
| Response | Server / model | `response_content_sha256`, body bytes | Oversize, fenced, `<think>`-prefixed, extra keys, model substitution, `finish_reason` ≠ stop | Byte bound → field checks → strict parser | Strict JSON, duplicate-key rejection | Frozen parse result | Rejected, never repaired | Rejected content never persisted | Claim |
| Proposed content / diff | AIDO assembly / 5E3 | Digests + reachability proof | Model prose in the approval surface; unreachable post-image | Unchanged 5E3 + writer applier | `Literal` | Frozen artifacts | — | Diff only in the evidence directory | Observed derivation of claimed content |
| Provenance v2 | AIDO → none | Validator cross-checks the diff | v1 read as live; forged record | `revalidate_*` JSON round trip | `Literal` facts | Frozen | Written last | No key or URL | Labeled sections |
| Banner / notice | AIDO | Built from checked values | Callback redirects the request (P1A R-2) | Client built before the banner | — | Frozen dataclass | Banner failure → nothing sent | Host and port only | Observed |

### 7.2 Findings, by materiality

**Material: could leak source or credentials, misroute transmission, or
falsify evidence. Each must be closed by the implementation.**

| # | Scenario | Impact | Required resolution |
|---|---|---|---|
| A-1 | P1A's `enabled` reused as the live gate | Every config enabled for offline tests becomes live-capable with no new decision, contradicting P1A's documented meaning | New `live_transmission_enabled`, default false. `enabled` alone never reaches a live client. |
| A-2 | This machine persists `AIDO_LITELLM_*` / `AIDO_VLLM_BASE_URL` for the **reviewer** | The implementer silently sends full source to the reviewer's endpoint (cross-role endpoint substitution), and the provenance names that host truthfully but unconsented | The human types scheme, host and port in the consent. A mismatch refuses **before** consumption and transmission. The procedure clears the other family. |
| A-3 | httpx honors `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` when `LLMClient` builds its own client (`trust_env` applies when no transport is given; verified in httpx 0.28.1) | Source is routed via an unconsented proxy, and recorded transport facts are false | P1B always passes an explicit transport, so environment proxies are not consulted. A regression test sets proxy variables and asserts no proxy mount exists. **The shipped reviewer path has the same property. That is recorded as backlog and is not changed by P1B.** |
| A-4 | Response-size bound counted on compressed bytes | A small gzip body decodes to an arbitrarily large string in AIDO's memory | `Accept-Encoding: identity`, and refuse any other `Content-Encoding` |
| A-5 | Secret in the base URL (userinfo, query token, fragment) | The secret is echoed in errors, or persisted via a URL | Refuse all three. Never echo. Record only scheme, host, port and a path digest. |
| A-6 | An uncaught exception prints a traceback with chained httpx texts (the base URL). Or locals rendering is turned on (off by default in Typer 0.27.1), exposing the `env` mapping. Or a client config is dumped (`model_dump` includes `api_key` despite `repr=False`). | **The base URL or API key is printed** to stderr or a log | Catch-all at the command boundary with category-only output. Never dump client config. A test pins `pretty_exceptions_show_locals is False`. Sentinel-scan tests, including a forced unexpected exception. |
| A-7 | An authorization reused: a second run, a copy into a new evidence directory, a concurrent double run | More than one transmission under one consent | Exclusive-create marker, `evidence_dir_sha256` binding, `binding_sha256` recomputation, expiry |
| A-8 | The file changes between prepare and run, or during run | Different bytes sent than consented | Re-read and compare the digest. The bytes sent are the bytes digested. The writer re-pins on disk later. |
| A-9 | `LLMRequest` is a mutable model | The message list changes after `request_sha256` is computed, so unconsented content is sent | Hand the worker a re-validated copy, and recompute the digest on that exact object immediately before `Thread.start` |
| A-10 | `finish_reason: length` with no `max_tokens` sent | Human-facing text falsely blames an AIDO budget | Fixed wording: "the server reported `length`; AIDO requested no `max_tokens`" |
| A-11 | Hidden extra requests: `AIDO_LITELLM_MAX_RETRIES`, httpx connect retries, a future refactor | One consent, several inferences, and a false `requests: 1` record | `max_retries=0`, `HTTPTransport(retries=0)`, and the wrapper **refuses** a second `handle_request` and records the observed count |
| A-12 | A stall followed by an immediate re-run | Two concurrent inferences on the local model | A stall is terminal; consent is spent; the notice says inference may continue |
| A-13 | A crash between send and evidence | The record would understate transmission | Pending run-record fsynced **before** transmission; exit 5 semantics |
| A-14 | Evidence directory or authorization inside the workspace | The clone gets dirty; the 5D2 read could pick up evidence; the writer could later act on it | Lexical **and** canonical outside-workspace checks for `--evidence-dir`, `--authorization` and `--out` |
| A-15 | TLS downgrade: the environment switches https → http after consent | Plaintext transmission without acknowledgement | Consent binds the scheme; the plaintext phrase is required iff http; the config acknowledgement is required too |

**Important, not blocking:**

| # | Scenario | Resolution |
|---|---|---|
| A-16 | Qwen emits `<think>…</think>` or a fenced reply in `content` when the server does not separate reasoning | Rejected by the unchanged strict parser. No repair or stripping. D-9 (`structured_output`) is the only lever. **This is a material pilot risk to success, not to safety.** |
| A-17 | Truthiness forgeries: `"yes"`, `1`, a `str` subclass, `model_construct` | Strict models, `is True`, `type is str`, JSON round-trip re-validation (P1A pattern) |
| A-18 | Public live API accepting a caller transport | The live runner never takes a transport. Tests use a private seam at the CLI layer, the reviewer's `client_factory` precedent. `run_supervised_implementer_offline` stays MockTransport-only (regression test). |
| A-19 | In-process Python calls `LLMClient` or private helpers directly | **Out of scope by design.** No library function is a security boundary against code in the same process. Guarantees apply to AIDO's entry points. The doc and docstrings must say so. |
| A-20 | Secret-shaped model output | 5E3 refuses it. P1B persists only its digest and length. |
| A-21 | P1A provenance v1 mistaken for live evidence | v2 is a separate schema with `transport_kind: live_http`. v1 is documented as offline-only. |
| A-22 | The clock is changed to dodge expiry | Expiry is a staleness guard, not a security property, and is stated so |

### 7.3 Minimum regression requirements

All tests are offline: `httpx.MockTransport` behind the private seam,
synthetic `tmp_path` Git repos, no socket, no real key.

1. **Gates:** `live_transmission_enabled` absent, false or forged (`"yes"`,
   `1`) refuses with **no environment read** (the mapping raises on access) and
   no evidence directory created. `enabled: true` alone never reaches a client.
2. **Consent parse:** draft, wrong or reused (H2, H6) phrase, missing,
   needless or wrong plaintext acknowledgement, naive datetime, `source` other
   than `manual`, extra or missing keys, and edited `bound` fields (digest
   recomputation) are each refused before consumption.
3. **Binding mismatches, one test per field:** plan, config (including a
   toggle of each `supervised_implementer` field), target, source bytes
   (edited file), request (patched template constant), evidence directory,
   expiry, and endpoint scheme, host and port. Each: refused, unconsumed,
   nothing sent.
4. **Single use:** a second run with the same authorization is refused after
   both success and failure. Two concurrent consumptions produce exactly one
   success. A copy to another evidence directory is refused.
5. **Provider isolation:** a spy mapping proves only the configured family's
   names are touched. `prepare` touches none.
6. **Endpoint:** userinfo, query, fragment and non-http(s) schemes are
   refused unechoed. http without either acknowledgement is refused. Persistent
   reviewer-style variables pointing to another host are refused (A-2).
7. **Transport:** proxy environment variables do not create a proxy mount
   (A-3). A 3xx is not followed and is terminal. A second `handle_request` is
   refused (A-11). The `Accept-Encoding: identity` request header is set. A
   gzip response is refused. `Content-Length` over the bound and a streamed
   over-bound body both give `response_too_large`, with the buffered count no
   more than the bound plus one chunk.
8. **Deadline:** a handler blocking past the deadline gives
   `implementer_stalled` (`supervisor_deadline`), exactly one request, no
   join, the worker still alive, and the elapsed time bounded by the deadline
   plus scheduling slack. A client timeout gives `client_timeout`. Neither is
   followed by a request.
9. **Failures, each with exactly one request:** 400 (including a structured
   output rejection with no unstructured follow-up), 401, 403, 429, 500,
   connect error, malformed body.
10. **Output:** every P1A malformed-reply case, plus `<think>`-prefixed and
    reasoning-only replies. `finish_reason` length or None. Model substitution.
    A secret-shaped `content_text` is persisted by digest only.
11. **Mutation:** a banner callback mutating config, environment or request
    after the checks does not change what is sent (digest re-check). A
    `model_construct` authorization is refused.
12. **Evidence:** exclusive creates. The pending record exists before the
    handler is invoked (the handler asserts it). The evidence write failure
    path gives exit 5. Provenance v2 re-validates and cross-checks the diff.
13. **Secrets:** sentinel key, URL path, query and environment values never
    appear in stdout, stderr or any evidence file, including on a forced
    unexpected exception (A-6).
14. **No writes:** the workspace snapshot (bytes, mtime, Git status) is
    unchanged across every outcome. Source inspection finds no writer, applier
    write, approval construction, subprocess or Git call in the new code.
15. **Unchanged baselines:** P1A's suite, `l2-read-workspace-files`, diff,
    writer, verifier and reviewer suites, and the CLI command-set snapshot plus
    the two new commands.

---

## 8. Implementation acceptance criteria

| # | Criterion |
|---|---|
| 1 | The two commands exist with exactly the §6.1 option sets. No other command, option or config field changes, except the §2.4 fields. |
| 2 | `run` sends at most one HTTP request per consumed authorization, proven by the wrapper count, with zero transport retries at both layers. |
| 3 | Every §3.2 binding fails closed at consumption, with the authorization left unconsumed and nothing sent. |
| 4 | Consumption is atomic and single-use across all outcomes, including concurrent invocations. |
| 5 | Only the configured provider's environment names are read, only in `run`, only after every offline check. |
| 6 | The endpoint must equal the human-typed scheme, host and port. Plaintext needs the config acknowledgement and the per-run phrase. No proxy, redirect or substitution is possible through the shipped path. |
| 7 | AIDO's monotonic deadline bounds the wait. A stall is terminal and is never described as cancellation. |
| 8 | The byte bound is enforced during receipt, with identity encoding only. No `max_tokens` is sent by default. |
| 9 | The strict parser, 5E3 generator and writer-domain and reachability checks are reused unchanged. The model authors only `content_text`. |
| 10 | The evidence files and provenance v2 follow §3.4. Transport facts, server claims and AIDO-derived digests are kept apart. Rejected content is never persisted. |
| 11 | No credential or base URL appears in any output or artifact on any path, including unexpected exceptions. |
| 12 | No workspace write, approval, Git operation, subprocess, commit or push. Every negative claim is `orchestrator_`-scoped. |
| 13 | P1A's offline runner, the reviewer, verifier, writer, `LLMClient` semantics for other callers, and `CANDIDATE_MODEL_IDS` are unchanged. The full offline suite is green. |
| 14 | No live request is made during implementation or testing. |
| 15 | Docs: a phase document, a DEC-SUP-LIVE policy amendment, and `CLAUDE.md` exactly per D-1. No real endpoint is written anywhere. |

---

## 9. Decisions requiring operator approval

| # | Decision | Options | Recommendation |
|---|---|---|---|
| **D-1** | `CLAUDE.md` truthfulness (C-1). **Blocks implementation authorization.** | (a) Authorize a narrow update: add the supervised implementer as the fourth gated model-calling path, and reword "no model-backed implementer" to "no *autonomous* model-backed implementer; one supervised, proposal-only implementer per DEC-SUP"; (b) explicitly accept the staleness for a live path | **(a).** A live path that the operating guide says cannot exist is a lifecycle-truthfulness defect. |
| **D-2** | Provider family for the corporate endpoint | `litellm` (requires key and default-model variables, the latter overridden) or `vllm` (base URL required, key optional) | Whichever matches the server's actual contract. The operator knows it. Both paths get identical gates. |
| D-3 | Environment namespace | Reuse the provider families (`AIDO_LITELLM_*` / `AIDO_VLLM_*`), or add a role-specific `AIDO_SUPIMPL_*` | **Reuse.** A-2's consent binding closes substitution, and a new namespace is a larger contract change. Reconsider if the reviewer and implementer must use different keys on the same provider. |
| D-4 | `attempt_timeout_seconds` default | A fixed default, or required with no default when live is enabled | **Required with no default when `live_transmission_enabled` is true.** Whole-file generation by a 27B reasoning model has no evidence-based default, and the value is bound into consent anyway. |
| D-5 | Evidence content retention | Persist `request-messages.json` and accepted `response-content.txt` locally, or digests only | **Persist both** (local, outside the workspace, never printed). They make the digests re-verifiable. Rejected content stays digest-only. |
| D-6 | AIDO-side Git preconditions (clean tree, HEAD) for the source clone | Operator helper snapshot, or reuse the 5F2C writer's read-only Git inspection from the new command | **Operator snapshot for P1B.** Reusing the writer's inspection adds a new caller of a subprocess capability that `CLAUDE.md` scopes to the writer's own contract. The source digest is what transmission authority needs, and the writer re-checks at H7. |
| D-7 | Authorization TTL | Fixed AIDO constant | **60 minutes**, as a staleness guard only |
| D-8 | `MAX_RESPONSE_BODY_BYTES` | Fixed constant, or configurable | **Fixed 16 MiB.** A configurable value invites raising it to "make it work". |
| D-9 | `structured_output` for the pilot | On or off | **On** if the corporate backend supports `response_format: json_schema`, per the 5F2E-V2 evidence. A rejection is terminal, with no fallback, and needs a new consent to try with it off. |
| D-10 | AUTH-PILOT specifics | Repository, clone location, target file, operator | Operator to name them at pilot time. Not before implementation acceptance. |

---

## 10. Readiness

**P1B implementation is ready for authorization once D-1 and D-2 are
answered.** D-3 to D-9 have recommended defaults that the implementation
prompt can adopt by reference. The implementation is still offline-only, and
the first live request needs AUTH-PILOT and a human-completed per-run consent,
neither of which exists.

Residual risks that remain after a correct implementation:

- **Plaintext transport.** Source crosses the network unencrypted. The
  acknowledgement records acceptance; it mitigates nothing.
- **Redaction is a backstop.** An unredacted file is not proven secret-free.
- **Unsigned artifacts.** Consent and provenance resist accident, not a
  deliberate forger (A-19, §3.3).
- **Backend lifetime after a stall is unobserved** (§4.3).
- **The model may simply fail the strict contract** (A-16). The pilot can
  legitimately end in `output_rejected`. That is a correct outcome, not a
  defect to repair around.
- **The shipped reviewer's client also honors environment proxies** (A-3).
  This is backlog, outside P1B.

---

## 11. Adopted decisions and implementation refinements (ALPHA-P1B-IMPL, 2026-10-15)

> **This section supersedes §0–§10 wherever they conflict.** It records the
> operator's decisions and the refinements the implementation adopted. It
> authorizes the offline implementation only.

### 11.1 Adopted decisions

| # | Adopted | Effect on the implementation |
|---|---|---|
| D-1 | **(a)** Narrow `CLAUDE.md` update | `CLAUDE.md` names the supervised, proposal-only implementer as a fourth gated model-calling path and distinguishes it from the still-absent **autonomous** model-backed implementer. No unrelated operating rule changes. |
| D-2 | **`litellm`** | The **live** gate accepts `provider: "litellm"` only. `"vllm"` is refused by the live gate (`live_provider_not_authorized`). P1A's offline library keeps accepting both. |
| D-3 | **Reuse `AIDO_LITELLM_*`** | `run` reads exactly the five shipped `AIDO_LITELLM_*` names through the shipped loader, once, after every offline check. No `AIDO_VLLM_*` name is ever looked up. `AIDO_LITELLM_DEFAULT_MODEL`, `_TIMEOUT_SECONDS` and `_MAX_RETRIES` are read by the loader and then **overridden** (registry model, the bound timeout, `0`). |
| D-4 | **Required, no default** | New field `attempt_timeout_seconds: float \| None = None` (`> 0`, `≤ 3600`, finite). The live gate refuses `None`. The value is bound into the authorization. |
| D-5 | **Retain request and accepted response locally** | `request-messages.json` (the exact canonical payload whose digest is `request_sha256`) and, only for an accepted reply, `response-content.txt`. No key, header, base URL or raw body is ever persisted. A rejected reply is recorded by digest and length only. |
| D-6 | **Independently verified workspace state** (refined, §11.2) | AIDO observes the Git state itself at prepare **and** at consumption, and binds the HEAD object id. An operator snapshot is no longer the authority. |
| D-7 | **60 minutes** | `AUTH_TTL`. A staleness guard, not a security property (A-22). |
| D-8 | **16 MiB** | `MAX_RESPONSE_BODY_BYTES = 16 * 1024 * 1024`, a fixed transport safety limit on buffered response bytes. Never sent, never a token budget, not configurable. |
| D-9 | **Structured output disabled for the pilot** (refined, §11.3) | The live gate refuses `structured_output: true`. The strict local parser is always enforced. |
| D-10 | **Separate AUTH-PILOT** | Repository, clone and file are chosen by a later, separate live-pilot authorization. Nothing in this phase names them. |

Exact implementer identity: `SUP-D` / `qwen3.8-27b`. SUP-D stays outside
autonomous-implementer qualification and earns no qualification credit.

### 11.2 Refinement R-1 (D-6): AIDO-observed Git state at the consumption boundary

The design's recommended D-6 option (operator snapshot) is **rejected** by the
operator: a clean-clone claim written by the operator is not independently
verifiable. The refinement:

- **What is observed.** AIDO runs the **5F2C writer's exact read-only Git
  preflight** (`_run_git_preflight`: the worktree top level is exactly the
  canonical workspace root; no execution-capable or indirecting Git
  configuration; a simple, submodule-free index in which the target is tracked
  once as an ordinary blob; a **wholly clean** working tree), then
  `rev_parse_head` for the exact HEAD object id. These operations are already in
  the fixed read-only set: **no Git operation is added**, nothing mutates, and
  the adapter's minimal child environment (no `AIDO_*` value) is unchanged.
- **Where.** In `prepare` (the HEAD object id is bound as
  `workspace_head_object_id`) and again in `run`, **bracketing** the in-process
  5D2 read: preflight, read, preflight. Both observations must report a clean
  tree at exactly the bound HEAD, before any environment read and before
  consumption.
- **Why it is the right domain.** It is exactly the state the 5F2C writer will
  require at H7. A proposal produced from a tree the writer would refuse could
  never be applied.
- **Platform.** The writer, and therefore this observation, is Windows-only;
  the live commands refuse other platforms.
- **What it does not prove.** Git-ignored files, anything outside the
  repository, remote state, or an atomic snapshot (the read is bracketed, not
  locked). A blob-hash comparison of the read bytes against the index entry was
  considered and **not** adopted: legitimate end-of-line conversion
  (`core.autocrlf`) makes working-tree bytes differ from the blob, so it would
  refuse ordinary Windows clones. A clean `git status`, under the configuration
  gate that refuses filters, is Git's own conversion-aware answer.

### 11.3 Refinement R-2 (D-9): structured output disabled for live

- The live gate refuses `supervised_implementer.structured_output: true` with
  `structured_output_not_authorized_for_live`, before any file or environment is
  read. The authorization binds `structured_output_mode: "none"` as a
  `Literal`, so no consented artifact can carry another mode.
- Enabling it later needs a separate authorization that establishes the exact
  supported mode of the actual backend. There is no capability detection and no
  fallback, and the live path sends no `response_format`.
- The strict local response contract (`parse_supervised_implementer_output`,
  unchanged) is always the final authority. A fenced or `<think>`-prefixed reply
  is rejected (`output_rejected`), never repaired (A-16).
- P1A's offline library is unchanged and still honours `structured_output`.

### 11.4 Other refinements from the pre-coding adversarial analysis

| # | Finding | Resolution |
|---|---|---|
| R-3 | **Pydantic strict mode does not make `Literal[1]` or `Literal[False]` type-exact.** Verified on pydantic 2.13.4: JSON `true` validates as `Literal[1]`, and JSON `0` validates as `Literal[False]`, even with `strict=True`. | Every integer and boolean in the authorization and in the new P1B records uses `StrictInt` / `StrictBool` with an exact-value check. P1A's v1 provenance has the same property, but only on AIDO-constructed output that is not an authority input; it is left unchanged. |
| R-4 | **The shipped client treats any status below 400 as success**, so a 3xx (or 1xx) body would be parsed as a completion. | The AIDO transport wrapper refuses any status outside 2xx/4xx/5xx before the client sees it (`transport_failed` / `unexpected_status_class`). httpx follows no redirects. |
| R-5 | **A digest over an AIDO serialization did not bind the bytes sent.** | `request_sha256` is the SHA-256 of the canonical JSON of the exact **wire payload** (`model`, `messages`, and only the optional members the shipped client sends). The wrapper decodes the actual outbound body and refuses it, **before anything reaches the network transport**, unless it equals that payload exactly, the method is `POST`, and the URL is exactly `<base>/chat/completions` at the consented scheme, host and port. |
| R-6 | **URL parser differential** (`urlsplit` vs httpx) could make the checked host differ from the contacted host. | The base URL is refused when it carries whitespace, control characters, a backslash, `@`, non-ASCII, a query or a fragment, or when `urlsplit` and `httpx.URL` disagree on scheme, host or port. The outbound check in R-5 is the final word. |
| R-7 | **`HTTPTransport` honours `SSL_CERT_FILE`/`SSL_CERT_DIR`** when `trust_env` is true, so the environment could change TLS trust. | The live transport is `httpx.HTTPTransport(retries=0, trust_env=False)`. Passing an explicit transport also disables environment proxies (A-3). |
| R-8 | **"Handed to the transport" can lag the decision to send.** After a stall the worker may not have reached the wrapper yet, and may still send later. | `transmission_attempted` is `true` as soon as the worker starts. The observed forward count is recorded separately, labelled as observed when AIDO stopped waiting. |
| R-9 | **A rewritten run-record contradicts "never overwritten".** | Two exclusive, fsynced state files instead: `transmission-pending.json` (before the banner and the request) and `outcome.json` (terminal). A pending file without an outcome means "treat the source as transmitted". |
| R-10 | **Consumption primitive.** *(Superseded by ALPHA-P1B-FU1, §11.6.)* | `os.mkdir(<evidence>/<run_id>)` is the atomic, exclusive consumption; `CONSUMED` is then created with `"x"`. A lost race refuses without consuming anything of its own. |
| R-11 | **`LLMConfigError` messages can echo raw environment values** (`_parse_float`, pydantic input values). | The live path maps a loader failure to the category `environment_invalid` with a fixed message and never prints the exception. |
| R-12 | **A linked evidence directory** could place source-bearing evidence somewhere the operator did not intend. | `--evidence-dir` must exist, be a directory, sit outside the workspace lexically **and** canonically, and its canonical path must equal its lexical absolute path (no link or junction on the way). Only its canonical-path digest is bound. |

### 11.5 Superseded statements

- §2.2 step **P1** "no env read": `prepare` reads **no provider environment
  variable** and builds no client. It does run the fixed read-only Git
  inspection (R-1), whose child environment is the adapter's fixed allowlist.
- §2.4: the timeout field is `float | None = None` (D-4), and the live gate also
  refuses `provider != "litellm"` (D-2) and `structured_output: true` (D-9).
- §3.1: `provider` is `Literal["litellm"]`; `structured_output_mode` is
  `Literal["none"]`; the bound section gains `workspace_head_object_id`; integer
  and boolean facts are exact-typed (R-3).
- §3.4: `run-record.json` is replaced by `transmission-pending.json` and
  `outcome.json` (R-9).
- §6.2 step 1: the operator snapshot is no longer the authority (R-1). The
  operator may still keep one as a personal record.
- §9 D-9's recommendation "on" is superseded by the operator's decision "off".

### 11.6 ALPHA-P1B-FU1: durable single-use authorization (B-1, route (a))

Independent review found that single use rested only on `<evidence>/<run_id>`
existing. Deleting that directory, or rotating the evidence directory, made a
spent authorization usable again until it expired. The operator chose route
(a), durable consumption state, and kept the invariant: *a consumed
authorization is never reusable, whatever the request outcome or the evidence
directory's lifecycle.*

This supersedes R-10, §3.3's "the marker", and every statement that the
evidence directory is the consumption ledger.

- **A separate ledger.** `supervised_implementer.authorization_ledger_dir`:
  required for the live path, absolute, existing, canonical, outside the
  workspace, and disjoint from the evidence directory. Its canonical-path
  digest is bound as `authorization_ledger_dir_sha256`, and the path is also
  covered by `project_config_sha256`.
- **Unused is proven positively.** `prepare` creates
  `<ledger>/<run_id>.issued.json` exclusively. It holds a fresh 256-bit nonce,
  and the authorization binds the nonce's digest as `issuance_sha256`. `run`
  refuses a missing ledger, a missing record, or a record whose run id, binding
  or nonce digest differs. Absence is never "unused".
- **Consumption is one `O_EXCL` create** of `<run_id>.consumed.json`, the only
  primitive that measured exclusive under thread contention on Windows. A
  rename and a delete each let several racers "succeed".
- **The nonce is destroyed.** Only the tombstone's creator re-checks the
  issuance record and deletes it. The run transmits only from that settled
  state, and every failure before it sends nothing.
- **The run directory is evidence only.** It is created after consumption.
  If it already exists before consumption, the run is refused
  (`evidence_run_dir_exists`) and nothing is spent.
- **Residual (outside A-19's threat model).** Restoring a pre-consumption copy
  of the ledger and deleting the tombstone restores the authorization until it
  expires. So does deleting the tombstone by hand after the one OS-failure
  state `authorization_ledger_settle_failed`, but no request was ever sent in
  that state.
