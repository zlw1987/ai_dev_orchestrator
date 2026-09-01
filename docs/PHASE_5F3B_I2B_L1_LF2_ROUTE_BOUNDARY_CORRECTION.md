# Phase 5F3B-I2B-L1-LF2 — Route Boundary Correction

**Status:** narrow superseding correction. Scope: the Category-B live route
check only.

This document supersedes exactly two clauses of the frozen
[I2A design](PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md) and
nothing else. **Historical I2A is not rewritten.** Its §15, §16, §23 and §24
keep their original text and remain the record of what was decided and why;
this file records what live evidence subsequently required to change, and is
the authority where the two disagree.

---

## 1. What triggered the correction

Candidate A's second real zero-prompt Category-B attempt
(`experiments/pi_implementer_qualification/results/i2b_live_A_20260831T224840Z.json`)
passed every runtime-side compatibility gate — broker, launch, RPC launch
shape, required launch flags, LF/JSONL correlation, `get_commands`, H1
extension identity, extension command namespace, `get_state`, H2
provider/model identity, protocol integrity, Pi version — and then failed
exactly one:

```text
failed_gate  = route_check
failure_code = ROUTE_CHECK_FAILED
exact_candidate_model_served = false
semantic_prompts_sent        = 0
```

**The gate-level refusal is accepted and is not reopened.** The route gate did
not establish success, and refusing was correct.

What the retained evidence does **not** establish is *why*. The live adapter
passed the frozen AR2 checker directly:

```python
route_checker = ar2.route_check.check_route_serves_model
```

which performs `GET <base_url>/models` through `httpx.Client(trust_env=False)`
**with no `Authorization` header and no credential parameter at all**. Its
single `configured_model_served=False` is therefore produced identically by:

| # | Source fact | What it is actually about |
|---|---|---|
| A | transport unreachable | the network |
| B | HTTP 401 | **authentication** |
| C | HTTP 403 | **authorization** |
| D | another non-200 status | the gateway |
| E | HTTP 200, malformed body | the response shape |
| F | HTTP 200, valid listing, candidate absent | **the model** |
| G | malformed checker result | the checker |

Only row F is a fact about the model. The frozen controller then reduces all
seven to one `ROUTE_CHECK_FAILED`, by design — correct as a *verdict*, and too
coarse as an *attribution*.

**Therefore the specific claim "B300 does not serve `qwen3-coder-next`" is NOT
established by the retained evidence**, and must not be written anywhere.

## 2. The design assumption that is superseded

I2A §24 item 1 recorded, honestly, that it was **unknown from local source**
whether the B300 LiteLLM proxy validates the `Authorization` header for this
route. I2A nevertheless required the future Category-B gate to reuse the
unauthenticated AR2 checker. Live evidence has now activated that open
question, so the *assumption* is what is corrected — not the checker.

### 2.1 Superseded text — I2A §15 item 9

> 9. B300 route serves the exact candidate model id, via the **unmodified**
>    `ar2.route_check.check_route_serves_model` non-inference `/models` GET
>    (`experiments/pi_external_runtime_ar2/ar2/route_check.py:89-160`) — reused
>    exactly as 5F3B §15.2 specifies, never copied or forked.

**Superseded by:**

> 9. **AR2's original route checker remains frozen and unmodified for AR2.**
>    `experiments/pi_external_runtime_ar2/ar2/route_check.py` is not edited,
>    forked, copied, wrapped, or given a credential parameter, and it remains
>    AR2's own accepted checker for AR2's own route.
>
>    **Category-B B300 qualification may not reuse it as the live checker when
>    the selected route is credential-bearing and the checker cannot express
>    that credential.** The B300 route is credential-bearing (§3 below), so the
>    Category-B live checker is the qualification-owned
>    `qualification.i2_b300_route_observation.observe_b300_route_serves_model`,
>    invoked only through the same-run-bound
>    `qualification.i2b_live_adapters.AuthenticatedB300RouteObserver`.
>
>    The gate's *meaning* is unchanged: one non-inference `GET /models`, no
>    prompt, no generation, no inference, never one of the four semantic
>    prompts, exact and case-sensitive model matching, nothing substituted or
>    auto-selected, and a failure means that case sends **zero prompts**.

### 2.2 Superseded text — I2A §23 slice I2-4

> **I2-4** | Wiring reuse of the unmodified
> `ar2.route_check.check_route_serves_model` for the non-inference gate, plus
> the credential-read-ordering discipline (§8: read only after every
> non-credential offline gate passes)

**Superseded by:** the credential-read-ordering discipline is **unchanged and
still binding** — the route observation happens after the credential read, not
before it, and the read still happens only after every non-credential offline
gate passes. Only the checker identity changes: the non-inference gate is
served by the qualification-owned authenticated observation described above.

### 2.3 What is explicitly NOT superseded

- I2A §16's two-path failure attribution (pre-prompt
  `INFRASTRUCTURE_REFUSAL` vs post-prompt `INFRASTRUCTURE_CONTAMINATED`).
- I2A §8's credential-read ordering.
- I2A §24 item 1's honesty: whether B300 *validates* the header is **still
  unresolved**. LF2 does not answer it and does not try to. A differential
  probe (one call with a good credential, one with a bad one) would answer it
  and is **not authorized** — it is not designed, not implemented, and not
  performed.
- The frozen controller's `ROUTE_CHECK_FAILED` verdict code, its gate
  ordering, and `CategoryBEvidence`. None is reopened.

## 3. The credential/header contract, established offline

Established mechanically from two independent in-repository sources. No live
traffic was used, no credential was read, and no endpoint was contacted.

1. **What credential Pi receives for this route.** The generated disposable
   `models.json` (`qualification/i2_pi_config.py`) writes
   `providers.b300_pi_qualification.apiKey = "$PI_QUALIFICATION_B300_ROUTE_KEY"`
   — a `$ENV` reference, never a literal — and the child environment carries
   that variable, whose value is the `AIDO_LITELLM_API_KEY` resolved by
   `qualification.i2_credentials.read_connection_values` alongside
   `AIDO_LITELLM_BASE_URL`.
2. **What header shape that credential produces.** The provider is declared
   `api: "openai-completions"`. I2A §5's provider table records that this api
   type **already sends** `Authorization: Bearer <key>`, which is exactly why
   `authHeader: true` is documented as unnecessary for it and is not emitted.
3. **Whether AIDO's existing B300 integration already uses that shape.** Yes.
   `src/ai_dev_orchestrator/llm/client.py` builds
   `{"Authorization": f"Bearer {api_key}"}` from the `AIDO_LITELLM_API_KEY`
   loaded beside `AIDO_LITELLM_BASE_URL` — the same two variables, the same
   value, the same header.
4. **Whether `/models` is expected to use the same authenticated route
   identity.** Yes. `/models` is a path on the same OpenAI-compatible route
   named by `AIDO_LITELLM_BASE_URL`, reached under the same provider identity
   Pi is configured with. Observing it anonymously — as the AR2 checker did —
   asks a *different* question than the one the run depends on. This is an
   expectation about which identity the request is made under; it is **not** a
   claim that the endpoint enforces it (see §2.3).

## 4. Authority binding for the authenticated checker

The observer takes **no** caller-supplied base URL, API key, provider id,
endpoint or model id — there is no parameter for any of them anywhere on the
live adapter boundary. Its authority is derived:

| Value | Derived from |
|---|---|
| base URL | the `ConnectionValues` the frozen controller consumed via `adapters.read_connection()` on this run |
| credential | the same `ConnectionValues` |
| model id | `route_descriptor_for_candidate(candidate).model_id` — the frozen I1 pairing |
| provider | not a parameter at all |

At call time the arguments the frozen controller passes are treated as
**claims to be checked**, never as instructions:

- base URL not byte-identical to the consumed one → refused;
- model id not exactly the frozen pairing's id for this candidate → refused
  (this is what makes "Candidate B's route during a Candidate A run"
  mechanically impossible);
- no consumed connection values yet → refused;
- a second call → refused, so one run issues exactly one non-inference GET.

Every refusal raises before any HTTP request is made, records
`route_authority_refused`, and is reduced by the unmodified
`run_offline_route_check` to its existing bounded `ROUTE_CHECK_ERROR`.

`qualification/i2b_live_adapters.py` no longer imports
`ar2.route_check.check_route_serves_model` **at all** — the import is deleted
rather than left unused, so the unauthenticated checker cannot re-enter live
wiring by accident. An offline test asserts the module has no reference to it.

## 5. Bounded route diagnostic vocabulary

Declared literals only, in `qualification/i2_b300_route_observation.py`:

```text
route_model_served            HTTP 200 + valid bounded listing + exact id present
route_transport_unreachable   no HTTP response at all
route_auth_rejected           HTTP 401 or 403 — an AUTH fact, never a model fact
route_http_rejected           any other non-200, including an unfollowed 3xx
route_listing_malformed       HTTP 200, body not a strict bounded listing
route_model_not_listed        HTTP 200 + valid bounded listing + exact id ABSENT
route_result_malformed        a checker result object that did not conform
route_authority_refused       same-run authority failed; NO request was issued
route_not_observed            the route stage was never reached (the default)
```

`exact_candidate_model_served = true` requires **all three** of HTTP 200, a
valid bounded listing shape, and the exact case-sensitive candidate id.
Success is never inferred from HTTP 200 alone.

The diagnostic is recorded by the L1 harness **alongside** the controller's
result (`route_diagnostics`, exactly as LF1's `launch_diagnostics` already is),
never inside `CategoryBEvidence`. **It is attribution, not verdict authority.**
The frozen controller keeps `ROUTE_CHECK_FAILED` for every failure shape.

## 6. Redirect policy

**Redirects are disabled**, explicitly (`follow_redirects=False`), not
inherited from an httpx default that a future version could change.

A credential-bearing request must never be moved to an authority this run
never approved: httpx re-sends the `Authorization` header across a same-origin
redirect, and a cross-origin redirect would either leak the credential or
silently change which endpoint answered the question. No redirect target is
"proven to remain within the authorized origin", because none is followed at
all. A 3xx is simply a non-200 and classifies as `route_http_rejected`.
Nothing upgrades, rewrites, or tunnels the URL.

`trust_env=False` is likewise explicit, inherited from AR2's own FU-C
reasoning: ambient `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` must not decide
where a credential-bearing request goes.

## 7. Retention

A finished observation carries **two exact bools and one declared code**.
There is deliberately no status code, no served-model-id list, no response
body, no failure prose, no endpoint, no host, no base URL and no credential —
and no exception message, type name, or traceback on any failure path. AR2's
checker retains a status code and the served ids; this one does not, because
this request carries a credential.

## 8. What LF2 does not do

No live activity of any kind was performed in this phase. No `/models` request
was made, no credential was read, no Node/Pi process was launched, no broker
was opened, no semantic prompt was sent, and neither Candidate-A live result
artifact was edited. Candidate A is **not yet qualified**; Candidate B, Q1/Q2
and real-workspace authority all remain NO-GO.
