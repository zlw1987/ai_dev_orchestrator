# ALPHA-1A-FU1 — Reviewer Egress Authority Correction (Implementation Contract)

> **ACCEPTED — committed and pushed.** FU1 is commit `5a38a67`; the FU2
> correction is commit `44bf3be05195a4fc050de7f0cad2407795d7c9b8`. Independent
> GitHub review accepted ALPHA-1A-FU1/FU2 at `44bf3be`, and no FU3 is needed
> (recorded 2026-10-20). `44bf3be` is the source pin for ALPHA-1B
> ([DEC-ALPHA1 §4.1](ALPHA_1A_DEC_ALPHA1_DECISION_PROPOSAL.md)).
>
> On 2026-10-19 the operator authorized A-1, A-2, A-3, A-4, A-5 and A-7 (§8).
> FU1 was then implemented offline as specified; §11 is the implementation
> record. A-6 (the narrow `CLAUDE.md` update) was authorized separately on
> 2026-10-20 and is part of the committed history. Only the endpoint
> value/authorization rule, the `review-packet.v5` wording and the
> `network_transport_factory` injection point changed. No model, network or live
> call was made by the implementation.
>
> *Status words in the body below that say "uncommitted", "IMPLEMENTED" or
> "awaiting" are the original wording at the time they were written; this banner
> supersedes them.*

| | |
|---|---|
| Kind | Narrow implementation contract (additive) |
| Recorded | 2026-10-19 |
| Corrects | [DEC-ALPHA1](ALPHA_1A_DEC_ALPHA1_DECISION_PROPOSAL.md) D-5. Its procedural reviewer-destination control is **rejected** as a source-egress guarantee, and D-5 is resolved as IMPLEMENTATION_REQUIRED |
| Baseline | `38081af…` (`src/` identical to `b8ac9ea`) when written; accepted result `44bf3be…` |
| Pattern reused | ALPHA-P1B `BoundedCountingTransport`: an outbound check on the actual `httpx.Request`, run before the network transport sees it. Only its URL/method idea is reused; nothing is shared or imported from it |

---

## 1. What was established by inspection (offline, no network)

| Fact | Consequence |
|---|---|
| The CLI review command builds its client with `_build_real_llm_client`, which is `LLMClient(config)`. It is shared with the planner and the smoke test | The reviewer needs its own transport. The shared builder stays unchanged |
| `LLMClient` with no injected transport builds `httpx.Client(timeout=…)`, with httpx's default `trust_env=True` | Environment proxies apply, and so does the **Windows registry proxy** (`urllib.request.getproxies()` falls back to the registry when no proxy variable is set) |
| `httpx.Client(transport=X)` computes `allow_env_proxies = trust_env and transport is None`, so passing an explicit transport disables **all** inherited proxy mounts. `httpx.HTTPTransport(proxy=None)` opens a direct `httpcore.ConnectionPool`. `trust_env=False` on the transport also stops `SSL_CERT_FILE`/`SSL_CERT_DIR` from being consulted | Proxy isolation can be achieved **without touching `LLMClient`**: AIDO hands it its own transport |
| `LLMClient.chat` posts to `f"{base_url.rstrip('/')}/chat/completions"`, and httpx parses that string. The reducers used for the banner and packet (`urlsplit`) parse a **different string** (the stripped base URL) | Any check must compare the URL **httpx actually requests**, not a separate parse |
| httpx's parse of `base + "/chat/completions"` has these effects: `?x=1` moves `/chat/completions` into the query (request path `/v1`); `#f` moves it into the fragment (request path `/v1`); `/v1/../x` becomes `/x/…`; a leading space yields a relative URL; `:80` on http and `:443` on https are dropped (`port is None`); `.host` decodes IDNA (`raw_host` does not); `127.1` and `h.example.` stay literal | Path, query, fragment and port must be compared on the request URL's `raw_path`, `query`, `fragment`, `raw_host` and effective port |
| `run_controlled_review(client_factory=…)` takes any object with `.chat()`. AIDO cannot see where such an object sends data | Enforcement cannot depend on what an injected client does. The injection point must move **behind** the check (§2.3) |
| An exception that is not `LLMClientError` and not raised by the parser passes through `LLMClient` and RS1 supervision unchanged, and the CLI's `except ReviewerStageError` turns it into exit 4 | A refusal raised in the transport needs no change to the supervision schema |

## 2. Authority boundary

### 2.1 The authority

Add one new required sub-block, `controlled_review.endpoint`. It lives in the
human-reviewed project config, which the per-run helper pins by hash.

```yaml
controlled_review:
  enabled: true
  provider: "vllm"                 # unchanged: exactly litellm | vllm
  model: "<M_R>"                   # unchanged: the only model authority
  endpoint:                        # NEW (FU1): what the reviewer may be sent to
    scheme: "http"                 # exactly http | https
    host: "reviewer.example"       # synthetic in docs/tests; a real host only in a per-run config
    port: 8000                     # required StrictInt 1..65535; never inferred
    base_path: "/v1"               # "" or "/seg[/seg]*"
  # …existing RS1/V1/V2 fields unchanged…
```

Strict validation happens at load, before anything else runs:

| Field | Rule (fail-closed) |
|---|---|
| `scheme` | `Literal["http", "https"]`, exact and case-sensitive |
| `host` | ASCII, lowercase. Either LDH labels joined by `.` (1–63 characters each, at most 253 in total, no leading or trailing `-`), or a canonical dotted-quad IPv4 address (no leading zeros, each octet 0–255). Refused: an all-numeric name that is not a canonical IPv4 address (for example `127.1`), a trailing dot, `%`, `@`, `:`, `/`, `\`, whitespace, `xn--` or other non-ASCII forms, and IPv6 (backlog) |
| `port` | `StrictInt` 1..65535. Required, with no default, so it is always explicit |
| `base_path` | `""`, or `/` followed by segments matching `[A-Za-z0-9._~-]+`. Refused: an empty segment (`//`), `.` or `..`, a trailing `/`, `%`, `?`, `#`, `\`, and whitespace. It must never carry a secret (secrets come only from the environment) |
| block | `extra="forbid"`. It is **required when `enabled: true`**: `check_controlled_review_gate` refuses `controlled_review.endpoint` being absent, *before verification runs* (exit 1) |

**What this authority is.** It is project policy data, like `model`. It is not
a credential and not a per-run consent.

**What stays the same.** The base URL that is *used* still comes **only** from
`AIDO_LITELLM_BASE_URL` or `AIDO_VLLM_BASE_URL`, read only after `verified`. The
key still comes only from the environment. The config **authorizes**; the
environment **supplies**; AIDO requires the two to match.

### 2.2 The check (one function, used at two points)

`check_reviewer_destination(url: httpx.URL, authority) -> None` is a pure check
on the URL **as httpx parsed it**. It requires all of the following:

- `url.scheme == authority.scheme`;
- `url.raw_host == authority.host.encode("ascii")`;
- the effective port (`url.port`, or else 80/443 by scheme) `== authority.port`;
- `url.userinfo == b""`, `url.query == b""` and `url.fragment == ""`;
- `url.raw_path == (authority.base_path + "/chat/completions").encode("ascii")`.

On failure it raises `ReviewerEgressRefused(ReviewerStageError)`. The message is
fixed: it names the mismatched component (`scheme`, `host`, `port`, `path`,
`userinfo`, `query` or `fragment`). It **never** contains the URL, the observed
host, or any header or credential.

It runs at two points:

1. **Pre-client gate (fail early).** In `run_controlled_review`, right after
   `build_reviewer_client_config` and before the notice, the client or any
   request. It checks `httpx.URL(config.base_url.rstrip("/") + "/chat/completions")`,
   which is the exact expression `LLMClient.chat` uses. If the parse itself
   fails, the review is refused. This keeps the credential ordering: it runs
   only after `verified` and after the environment read.
2. **Consumption boundary (binding).** `ReviewerEgressTransport(httpx.BaseTransport)`
   runs it in `handle_request` on the actual `httpx.Request`, along with a
   `POST` check, **before** delegating to the inner transport. That covers every
   request the client produces: both RS1 attempts, and a redirect if any layer
   ever followed one.

   The authority is a frozen copy captured once by the gate, before
   verification. Later changes to the config object, the `LLMClientConfig`, the
   environment or the URL therefore cannot widen it.

### 2.3 Supported callers and the injection-point change

| Caller | After FU1 |
|---|---|
| CLI `l2-review-approved-file-edit` | **Enforced.** It passes `network_transport_factory=build_reviewer_network_transport`, which returns a `ReviewerDirectNetworkTransport` (an argument-less `httpx.HTTPTransport` subclass fixed to `retries=0, trust_env=False`). This is the only transport the packet records as `direct_no_inherited_proxy` (FU2) |
| Library `run_controlled_review(...)` | **Enforced.** `client_factory` is **replaced** by a required `network_transport_factory: Callable[[], httpx.BaseTransport]`. `run_controlled_review` itself builds `LLMClient(config, transport=ReviewerEgressTransport(inner=network_transport_factory(), authority=…))`. The caller supplies only the inner transport (tests: `httpx.MockTransport`), and every request passes the check before reaching it. **FU2:** the packet records `injected_transport_not_established` for any inner transport that is not exactly a `ReviewerDirectNetworkTransport`, and claims nothing about its proxy, TLS trust or encryption |
| `request_model_review`, `run_supervised_review` (lower-level primitives with a caller-built client) | **Not an authority boundary, and not claimed to be one.** They read no environment, run no verification and hold no endpoint authority. Their docstrings must say so. No product path calls them except `run_controlled_review` |
| Planner, smoke test, P1B | Unchanged. `_build_real_llm_client`, `LLMClient`, `AIDO_LITELLM_MAX_RETRIES` and the timeout semantics are untouched |

**Stated limit (as in P1B A-19).** An injected inner transport is trusted
in-process code. It receives only requests that have already been checked, but
nothing stops arbitrary in-process code from opening its own socket. The
guarantee is that **AIDO's reviewer path hands source-derived material only to
the authorized destination**. It is not a sandbox against code in the same
process.

**Name resolution.** The authority is the scheme, the host *as text*, the port
and the path. DNS answers, the hosts file and routing are not observed. Over
`https`, the certificate is verified against `authority.host`, using httpx's
default trust store. Over `http`, nothing authenticates the server: it remains
an acknowledgement (`vllm_allow_insecure_http`), never a security claim.

## 3. Files to change (minimal)

| File | Change |
|---|---|
| `src/ai_dev_orchestrator/models.py` | `ControlledReviewEndpointConfig` (strict, §2.1); `ControlledReviewConfig.endpoint: ControlledReviewEndpointConfig \| None = None` (validated at load, required by the gate) |
| `src/ai_dev_orchestrator/review/egress.py` (**new**, small) | `ReviewerEndpointAuthority` (a frozen copy), `check_reviewer_destination`, `ReviewerEgressTransport`, `build_reviewer_network_transport`. Nothing else: no counting, no response checks, no body checks |
| `src/ai_dev_orchestrator/review/models.py` | `ReviewerEgressRefused(ReviewerStageError)` |
| `src/ai_dev_orchestrator/review/reviewer.py` | The gate requires `endpoint` and returns the frozen authority; `run_controlled_review` replaces `client_factory` with `network_transport_factory`, runs the pre-client check, builds the wrapped `LLMClient`; `ReviewerCallNotice` gains `endpoint_port` and `endpoint_base_path` |
| `src/ai_dev_orchestrator/review/packet.py` | `review-packet.v5` (§5) |
| `src/ai_dev_orchestrator/review/__init__.py` | Exports |
| `src/ai_dev_orchestrator/cli.py` | Review command only: the injection point is renamed, the production factory is wired in, and the banner gains a line: `endpoint: <scheme>://<host>:<port><base_path> — matches project-config authorization`, and (FU2) a `Network path:` line derived from the transport actually used (`direct; no environment or platform proxy inherited`, or `NOT ESTABLISHED — caller-supplied network transport …`). The `reviewer-egress-refused` category exits 4 with "refused before it reached any network transport" (FU2 corrected the earlier "No request was issued") |
| `src/ai_dev_orchestrator/llm/client.py` | **No change** |

Tests (§6): one new file, `tests/test_review_egress.py`, plus mechanical
migration of six existing review test files and `tests/test_controlled_review_config.py`.

## 4. Frozen behavior that must not change

- **Verification before credentials.** The gate (including the endpoint
  authority) runs, then verification, then the environment is read for the
  configured provider's names only, then the pre-client check, then the
  client. No `AIDO_*` read happens before `verified`. The verification child's
  environment policy is unchanged.
- **Provider and model.** `provider` is exactly `litellm` or `vllm`, with no
  alias. `model` comes only from config. There is no environment default model,
  no CLI option, and no `AIDO_VLLM_DEFAULT_MODEL`. The `no_api_key` placeholder
  rule for keyless vLLM is unchanged. `vllm_allow_insecure_http` keeps its
  meaning; `endpoint.scheme: http` is required **in addition**, never instead.
- **RS1.** `max_retries=0`; one HTTP request per attempt; at most two semantic
  attempts; AIDO's own monotonic deadline; one daemon worker per attempt with no
  join; a stall is terminal; the compact retry applies only to completed but
  unusable output; the token policy (`max_output_tokens` unset → no
  `max_tokens`). The transport adds no retry, no timeout and no count.
- **V2.** The generated schema, `response_format` only when opted in, no
  fallback, and the strict parser unchanged.
- **Output.** Strict JSON, rejected and never repaired. The verdict is advisory
  and terminal. No fixer, no second reviewer, no fallback model.
- **CLI surface.** The same option set: no `--endpoint`, `--base-url`,
  `--port`, `--provider` or `--model`. Exit codes 0–4 keep their meaning.
- **Logging.** Never print the key, the `Authorization` header, the base URL, a
  URL with userinfo, query or fragment, the prompt, the diff, or the raw
  response. Refusal messages are fixed text.
- **History.** `v1`–`v4` packets keep their meaning. Alpha-0 runbook, helper,
  qualification records and roadmap are untouched.

## 5. `review-packet.v5` (additive)

The `reviewer` block gains:

| Field | Value |
|---|---|
| `endpoint_port` | the effective port (always present) |
| `endpoint_base_path` | the authorized `base_path` |
| `endpoint_authority_source` | `Literal["project_config.controlled_review.endpoint"]` |
| `endpoint_matched_authority_before_each_request` | `Literal[True]`. A mismatch produces no packet |
| `transport_proxy_mode` | `Literal["direct_no_inherited_proxy", "injected_transport_not_established"]`. **FU2:** derived from the inner transport actually used, not fixed. The first value only for an exact `ReviewerDirectNetworkTransport` |
| `transport_note` | text selected by `transport_proxy_mode`. Both: every request was checked against the endpoint; the name is resolved by the system resolver, which is not observed. Direct mode adds the proxy/`SSL_CERT_*`/certificate/`http` statements; injected mode instead says AIDO did not establish them |

`endpoint_host`, `endpoint_scheme` and `transport_tls` keep their exact v4
meanings. The superseded-version note says that **no v1–v4 packet records
endpoint authorization or proxy isolation**, and none may be read as proving
either.

Why bump the version rather than reuse v4? If v4 were kept, packets with the
same schema string would mean different things depending on the AIDO revision
that wrote them. That is the silent semantic drift §4 forbids.

## 6. Required tests (all offline, `httpx.MockTransport`, synthetic hosts)

**Config (`test_controlled_review_config.py`):**
- every §2.1 rule accepts and refuses as specified;
- `enabled: true` without `endpoint` loads, but the gate refuses it before the
  verification process starts (exit 1, zero child launches, no environment
  read);
- `extra` keys are refused, and boolean or string ports are refused.

**Destination check (`test_review_egress.py`).** Each case has a fixed
authority of `http`, `reviewer.example`, `8000`, `/v1`. Each refusal must happen
with **zero** inner-transport calls, after verification, and with no URL in the
output:

| Base URL in the environment | Expected |
|---|---|
| `http://reviewer.example:8000/v1`, `…/v1/`, `http://REVIEWER.example:8000/v1` | accepted |
| `https://…:8000/v1` | refused: scheme |
| `http://other.example:8000/v1`, `http://reviewer.example.:8000/v1`, `http://127.1:8000/v1` (with authority `127.0.0.1`) | refused: host |
| `http://reviewer.example:8001/v1`, `http://reviewer.example/v1` (effective 80) | refused: port |
| `http://reviewer.example:8000/v2`, `…/v1/../v1x`, `…//v1`, `…/v1%2f..` | refused: path |
| `http://u:p@reviewer.example:8000/v1` | refused: userinfo; no part of the userinfo appears in the output |
| `…/v1?x=1`, `…/v1#f`, `http://evil.example#@reviewer.example:8000/v1`, `http://reviewer.example:8000\@evil.example/v1` | refused (query, fragment or host) |
| ` http://reviewer.example:8000/v1` (leading space), `not a url`, an empty value | refused before any client is built |
| authority with port 80 and URL `http://reviewer.example/v1` | accepted (effective port equality) |

**Consumption boundary:**
- if `config.base_url` is changed after the pre-client gate (simulated
  post-validation mutation), the transport refuses before the inner transport
  is called, and the CLI exits 4 with `reviewer-egress-refused` and no packet;
- a 3xx response with a `Location` to another host does not cause a second
  outbound request. If a second request is forced, it is refused;
- the compact retry's second request passes the same check;
- the `Authorization` header reaches only the inner transport of an accepted
  request.

**Proxy isolation:**
- with `HTTP_PROXY`, `HTTPS_PROXY` and `ALL_PROXY` set, and with
  `urllib.request.getproxies` monkeypatched to return a registry proxy, the
  production transport and the client `LLMClient` builds around it have **no**
  proxy mounts;
- the production factory returns `httpx.HTTPTransport` with `retries=0` and
  `trust_env=False`;
- these tests create no socket (the network transport is never invoked).

**Ordering and isolation regressions:**
- the reviewer environment is still read only after `verified`, and only the
  configured provider's names;
- a mismatch never causes a second environment read;
- the existing provider-isolation tests pass unchanged in intent.

**Library entry:**
- `run_controlled_review` **without** `network_transport_factory` is a
  `TypeError`;
- there is no remaining parameter through which a caller can supply a client.

**Packet:**
- the v5 fields and values are present;
- v1–v4 constants and notes are unchanged;
- the banner prints host, port, path and the proxy line, and never the base URL.

**Unchanged suites:** RS1 supervision, V1 vLLM provider, V2 structured output,
token-cap, planner, smoke test and P1B pass. Their review-path fixtures migrate
mechanically, from `client_factory=lambda c: LLMClient(c, transport=Mock…)` to
`network_transport_factory=lambda: Mock…`. Config assertions that captured the
`LLMClientConfig` call the public `build_reviewer_client_config` directly, or
assert on the observed request.

## 7. Adversarial review

| Attack | Result under FU1 |
|---|---|
| Endpoint substitution (environment points elsewhere) | Refused at the pre-client gate. If it is changed later, refused at the transport. No byte, header or key leaves |
| Alternative or default port | The effective port is compared, so `:80` versus no port behaves correctly and `8001` is refused |
| Ambiguous parsing (`\@`, `#@`, userinfo) | The check uses httpx's parse of the request URL, which is the parse that opens the socket. A differential with `urlsplit` cannot widen the authority |
| Query, fragment or path substitution | `raw_path`, `query` and `fragment` are compared exactly, and the authorized `base_path` is canonical by construction |
| IDNA or homograph | ASCII LDH only, compared on `raw_host`. Punycode and non-ASCII are refused |
| Proxy inheritance (environment or registry) | An explicit transport means the client mounts no inherited proxy. The production transport is direct; an injected one is recorded as `injected_transport_not_established` (FU2) |
| Mismatched provider | Only the configured provider's variables are read. The URL must still match the single authority. A missing variable is the existing refusal |
| Stale approval or stale config | The authority sits in the pinned per-run config. A changed file stops the helper snapshots, and a different file is visible in the packet (endpoint fields, model). It is project policy, not single-use consent; per-run consent remains the human H9 act |
| Injected client factory | Removed. The only injection point sits behind the check |
| Post-validation mutation | The authority is frozen at the gate, and every request is re-checked at the transport |
| Redirect | Not followed (httpx default). If it ever were, the next request is re-checked |
| Credential leakage via the URL or logs | Userinfo and query are refused. Messages are fixed text, and the base URL is never printed |
| DNS, hosts file, routing | **Out of scope** and stated (§2.3). Not a leak through AIDO's authority, but not prevented either |
| In-process code opening its own socket | **Out of scope** (A-19 analog). Stated |

## 8. Explicit human authorization needed before implementation

| # | Change that needs explicit assent | Why |
|---|---|---|
| A-1 | Implement FU1 as specified (§3, §6) | Source change to an accepted reviewer |
| A-2 | **`controlled_review.endpoint` becomes mandatory.** Every existing accepted 5F2E/V1/V2 config is refused at the review gate until it gains the block | This intentionally breaks existing configs, failing closed. The alternative, optional with legacy behavior when absent, would not make the guarantee mandatory, and is **not recommended** |
| A-3 | **Library API change:** `run_controlled_review(client_factory=…)` becomes `network_transport_factory=…` (and the same for the CLI's private `_run_l2_review_approved_file_edit`) | A frozen public signature changes |
| A-4 | **`review-packet.v4` → `v5`** | A schema change (§5) |
| A-5 | `trust_env=False` on the reviewer transport. An `https` reviewer that relied on `SSL_CERT_FILE` or `SSL_CERT_DIR` for a private CA will now fail closed | A behavior change for some https deployments (matches P1B) |
| A-6 | **A narrow `CLAUDE.md` update, authorized separately.** Its rule "the endpoint is environment-only, never project config" becomes: "the endpoint value is environment-only; the endpoint *authorization* (scheme, host, port, base path) is project config, and they must match". Plus the v5 packet and the injection-point change. This proposal does not edit `CLAUDE.md` | The project's operating guide would otherwise contradict the code |
| A-7 | Additive banner and stderr wording (endpoint line, `reviewer-egress-refused`) | A human-facing CLI text change; the options are unchanged |

## 9. ALPHA-1 source and version binding

- **Nothing historical is rewritten.**
  - The Alpha-0 runbook stays pinned to `39d81ba`, and its helper default stays
    `VERIFIED_AIDO_COMMIT`.
  - P1C/P1D evidence keeps its recorded pins (`b8ac9ea` / `38081af`) and
    snapshots.
  - Those pins remain true statements about the runs that used them.
- **A new pin for ALPHA-1.**
  - Once FU1 is accepted, the user commits it as `C_FU1` and pushes it to
    `origin/main`. Pushing is a human action, and the P1C B-1 lesson applies.
  - ALPHA-1B records `C_FU1` (the full SHA) as `aido_source_commit` in
    AUTH-ALPHA1B, and passes the helper `--verified-commit <C_FU1>`.
  - The frozen helper then requires AIDO's `src/` and `pyproject.toml` to be
    byte-identical to `C_FU1` and clean, and it pins the copied helper's hash.
- **The old pins stop working, as intended.**
  - FU1 changes `src/`, so `--verified-commit b8ac9ea` or `38081af` makes the
    helper preflight **STOP** against the new runtime.
  - The Alpha-0 runbook, run against FU1 source, likewise stops at its own
    preflight. It is not silently reinterpreted.
- **Re-verifying the CLI for ALPHA-1B.**
  - Before S0, the ALPHA-1B procedure re-checks the shipped `--help` option sets
    at `C_FU1`. All eight Alpha-0 commands and both P1B commands are expected to
    be unchanged.
  - The config template gains `controlled_review.endpoint`.
- **Clone baseline.** The ALPHA-1B clone's HEAD becomes `C_FU1` or later (D-3).
  The target file (`issue_parser.py`) is unaffected by FU1.

## 10. Remaining DEC-ALPHA1 decisions

| Decision | Status after FU1 |
|---|---|
| D-5 | **Resolved: IMPLEMENTATION_REQUIRED** via FU1 (A-1..A-7) |
| D-3 | Amend: baseline = `C_FU1` (§9) |
| D-6 | Unchanged in substance. The reviewer endpoint is now written into the **per-run config** (`controlled_review.endpoint`) and reviewed at H0. It is still never written into this repository |
| DEC-ALPHA1 §6.2 | Simplified. The read-back, `NO_PROXY=*` and the post-hoc packet comparison are no longer the control. AIDO enforces the destination. The H9 record remains the human consent, and the packet's v5 endpoint fields replace the comparison as closure evidence. The window hygiene (clearing persistent `AIDO_*` variables) stays |
| G-1, G-2 (DEC-ALPHA1 §6.3) | Closed mechanically for the CLI and `run_controlled_review`. G-3..G-7 are unchanged |
| D-1, D-2, D-4, D-7..D-12 | **Ready to finalize now.** None depends on FU1's mechanism |

**FU1 recommendation: IMPLEMENTATION_REQUIRED.** The scope is §3 and §6, and it
requires A-1..A-5 and A-7 (A-6 separately). After FU1 is accepted and committed
as `C_FU1`, DEC-ALPHA1 can be finalized with the amendments above, and ALPHA-1B
needs no further code change.

Stopping before implementation.

---

## 11. Implementation record (2026-10-19; written on `38081af`, since committed as `5a38a67` and `44bf3be`)

**Source.**

| File | What changed |
|---|---|
| `models.py` | `ControlledReviewEndpointConfig` (strict, frozen, `extra="forbid"`, the §2.1 rules), plus `ControlledReviewConfig.endpoint`. Docstrings state the field is an authorization, not an endpoint value |
| `review/egress.py` (new) | `ReviewerEndpointAuthority`, `check_reviewer_destination`, `reviewer_request_url`, `effective_port`, `ReviewerEgressTransport`, `build_reviewer_network_transport` (returns `ReviewerDirectNetworkTransport`, fixed to `retries=0, trust_env=False`), `transport_proxy_mode_of`, and the packet constants. It imports no `os`, `subprocess` or `socket` |
| `review/models.py` | `ReviewerEgressRefused(ReviewerStageError)` with fixed, component-only text |
| `review/reviewer.py` | The gate requires `endpoint`; `ReviewerAuthority.endpoint`; `ReviewerCallNotice.endpoint_port`/`endpoint_base_path`; `run_controlled_review(network_transport_factory=…)` with the pre-client check; the client is built internally around the egress transport. `request_model_review` is documented as not an authority boundary |
| `review/supervision.py` | Docstring only: `run_supervised_review` is not an authority boundary |
| `review/packet.py` | `review-packet.v5` with the six §5 fields; v4 meaning preserved in `REVIEW_PACKET_SCHEMA_VERSION_V4_SEMANTICS` |
| `review/__init__.py` | Exports |
| `cli.py` | The review command passes `_build_reviewer_network_transport`. Banner lines: `Endpoint: scheme …, port …, base path … — matches project-config authorization` and `Network path: …` (FU2). Failure category `reviewer-egress-refused` (exit 4). `--project-config` help names `controlled_review.endpoint`. **The option set is unchanged.** The planner and smoke-test `client_factory` paths and `LLMClient` are untouched |

**Tests.**

- New: `tests/test_review_egress.py` (50 tests).
- Extended: `tests/test_controlled_review_config.py` (+64 endpoint-validation and gate tests).
- Migrated mechanically: the six existing review test files and `test_review_supervision.py`.
  - The test helper `_mock_client_factory` keeps its name but now returns a `MockTransport` factory.
  - Assertions that used to inspect a captured `LLMClientConfig` now assert on the **observed request** instead: URL, bearer token, payload model, httpx read timeout (`_ObservedRequest`). Zero transport retries is proved by exactly one request for a retryable 503.
  - Blocking-client stall tests now block inside an inner transport.
  - Version assertions moved to `v5`.

**Departures from the contract text.** None in behavior. Notes:

- The CLI's private `_run_l2_review_approved_file_edit` keeps a default for its
  injection point (the production transport), exactly as its old
  `client_factory` default did. The public library parameter has no default.
- `ReviewerCallNotice` gained two **required** keyword fields.
- The unparseable-URL refusal reports component `url`. A leading-space or
  scheme-less value is parsed by httpx as a relative URL and is refused as
  `scheme`. Both happen before any client exists.

**Verification.** On this Windows machine, the full offline suite (`pytest tests`) gave **3908 passed, 1 warning** in 9 min 39 s. The warning is a pre-existing Pydantic serializer warning in a P1B test.

Nothing in the suite opens a socket or reads a real credential. Every endpoint is synthetic (`.invalid` or `reviewer.example`).

The Alpha-0 helper and its tests were not touched.

**Status of the original open items (updated 2026-10-20):**
1. Independent review of FU1/FU2: **done, accepted at `44bf3be`.**
2. A-6 (narrow `CLAUDE.md` update): **done and committed** with FU1.
3. `C_FU1` commit and push: **done.** The pin for ALPHA-1B is `44bf3be`, because FU2 changed `src/` after `5a38a67` (so `5a38a67` alone is not the source pin).
4. The DEC-ALPHA1 amendments in §10: **applied** in the finalized
   [DEC-ALPHA1 proposal](ALPHA_1A_DEC_ALPHA1_DECISION_PROPOSAL.md).

## FU2 amendment (ALPHA-1A-FU2): transport provenance is derived

Independent review (finding R-1) found that `review-packet.v5` claimed `direct_no_inherited_proxy` unconditionally, although `run_controlled_review` accepts an injected `network_transport_factory`. That was true of the production CLI transport but not established for an injected one.

- `transport_proxy_mode` is derived from the inner transport object actually used: `direct_no_inherited_proxy` only for an exact `ReviewerDirectNetworkTransport`; `injected_transport_not_established` for everything else, including a bare `httpx.HTTPTransport`, a proxied transport, a subclass and `httpx.MockTransport`.
- The inner transport is now built after the destination check and the review context, and immediately before the notice; it opens no socket. Endpoint authorization, the per-request check, verification-before-credentials ordering, RS1 supervision and retry semantics are unchanged.
- The banner and `transport_note` follow the same value. For an injected transport with an `https` URL the banner no longer says `TLS-encrypted`.
- `ReviewerEgressRefused` wording: `method` and `url` are no longer described as not matching the endpoint configuration, and "No request was issued" became "refused before it reached any network transport".
- The version stays `review-packet.v5`. Disclosed: a `v5` packet from commit 5a38a67 produced through an injected transport carried the unestablished direct claim; production-CLI packets from it were accurate. `v1`–`v4` are untouched.
- **Residual:** the exact-type check shows how the transport was built, not that in-process code left it alone; DNS, routing and the hosts file remain unobserved.
