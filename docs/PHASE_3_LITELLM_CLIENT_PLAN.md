# Phase 3 — Internal LiteLLM Client Plan

> **This document began as the Phase 3A plan and is now maintained as the
> Phase 3 status/plan document.** It records both what has shipped and what
> remains planned across the Phase 3 sub-phases:
>
> - **Phase 3A** was **docs-only** — this plan, with no runtime code, module,
>   test, or network call.
> - **Phase 3B** added the typed request/response/config **models**
>   ([llm/models.py](../src/ai_dev_orchestrator/llm/models.py)) and the
>   environment-driven **config loader**
>   ([llm/config.py](../src/ai_dev_orchestrator/llm/config.py)). No network code.
> - **Phase 3C** added the **mockable OpenAI-compatible client**
>   ([llm/client.py](../src/ai_dev_orchestrator/llm/client.py)) and its tests
>   ([tests/test_llm_client.py](../tests/test_llm_client.py)). Tests use a faked
>   HTTP transport; no real model is ever called.
> - **Phase 3D** remains **future** — a mocked / dry-run CLI smoke test with no
>   real model call by default.
>
> Throughout, the safety boundaries hold: no real model calls by default, no
> agent behavior, no file editing, no command execution, no GitHub writes, and
> no target-workspace access.

This plan refines item **"Phase 3 — LiteLLM client"** of
[AI_DEV_ORCHESTRATOR_PLAN.md](AI_DEV_ORCHESTRATOR_PLAN.md).

## 1. Scope

In scope for the future Phase 3 client (designed here, built later):

- An **internal LiteLLM / OpenAI-compatible chat client abstraction** only.
- **Environment-driven configuration** — connection details and secrets come
  from environment variables, never from committed files.
- **Mockable tests** — the client must be testable with a faked HTTP transport.
- **No real network calls in tests** — deterministic, offline test runs.

Explicitly **out of scope** for all of Phase 3:

- No agent behavior (no planning, no orchestration loop, no role wiring).
- No file edits and no file-editing engine.
- No command execution.
- No GitHub writes (no PRs, comments, commits, or pushes).
- No target-workspace access — the client never reads project files.
- No embeddings, tool/function calling, or streaming in the first cut.

## 2. Provider policy

- **Default provider:** the internal **LiteLLM OpenAI-compatible endpoint**
  (company-hosted). This is the only provider the first implementation targets.
- **External providers disabled by default.** OpenAI, Anthropic, Copilot, and
  Codex remain off unless a future phase explicitly enables them, consistent
  with `Settings.enable_external_providers` (default `False`) in
  [config.py](../src/ai_dev_orchestrator/config.py).
- **Secrets only from environment variables.** No API key, token, or base URL
  with embedded credentials is ever stored in a repo file.
- **No secrets in repo files** — including example configs, tests, and docs.

### Proposed environment variables (proposed, NOT implemented in 3A)

| Variable | Purpose |
| --- | --- |
| `AIDO_LITELLM_BASE_URL` | Base URL of the internal LiteLLM endpoint. |
| `AIDO_LITELLM_API_KEY` | API key for the internal LiteLLM endpoint. |
| `AIDO_LITELLM_DEFAULT_MODEL` | Default model name when a caller omits one. |

> **Naming note (resolved):** Phase 3B **adopted the `AIDO_` prefix as
> canonical** and migrated [config.py](../src/ai_dev_orchestrator/config.py) off
> the unprefixed Phase 0 names (`LITELLM_BASE_URL`, `LITELLM_API_KEY`). The full
> set is `AIDO_LITELLM_BASE_URL`, `AIDO_LITELLM_API_KEY`,
> `AIDO_LITELLM_DEFAULT_MODEL`, plus optional `AIDO_LITELLM_TIMEOUT_SECONDS` and
> `AIDO_LITELLM_MAX_RETRIES`, loaded by
> [llm/config.py](../src/ai_dev_orchestrator/llm/config.py).

### Likely company models

- `minimax-m2.7` — candidate **implementer** model.
- `qwen3.6-27b` — candidate **reviewer** model.

These are referenced for context only; Phase 3 does not pin or wire roles.

## 3. Proposed module structure

Suggested layout for the **future** implementation. **These files are NOT
created in Phase 3A.** They mirror the existing `github/` subpackage style
(`__init__.py`, `models.py`, `client.py`).

```
src/ai_dev_orchestrator/llm/__init__.py     # public exports for the llm package
src/ai_dev_orchestrator/llm/models.py       # typed request/response/config models
src/ai_dev_orchestrator/llm/config.py       # env-driven LLMClientConfig loader
src/ai_dev_orchestrator/llm/client.py       # chat-completion client (LiteLLM)
tests/test_llm_client.py                    # mocked-transport unit tests
```

Rationale: keeping `models.py` (data), `config.py` (env loading), and
`client.py` (transport) separate keeps the network surface small, isolates the
only env-reading code, and lets tests import models/config without touching the
client.

## 4. Proposed typed models

Described for the future; **not implemented in 3A.** Consistent with the
existing codebase, these should be **pydantic `BaseModel`** types (as in
[github/models.py](../src/ai_dev_orchestrator/github/models.py) and
[config.py](../src/ai_dev_orchestrator/config.py)).

### `LLMMessage`
A single chat message.
- `role: str` — one of `"system" | "user" | "assistant"`.
- `content: str` — message text.

*Reasoning:* mirrors the OpenAI chat schema so LiteLLM payloads map directly.

### `LLMRequest`
A chat-completion request.
- `model: str` — model name (e.g. `minimax-m2.7`).
- `messages: list[LLMMessage]` — ordered conversation.
- `temperature: float | None` — optional sampling control.
- `max_tokens: int | None` — optional output cap.

*Reasoning:* the minimal field set needed for chat completion; no tools,
functions, or streaming fields yet (kept out by scope).

### `LLMResponse`
A normalized chat-completion result.
- `model: str` — model that produced the response.
- `content: str` — assistant text (first choice).
- `finish_reason: str | None` — why generation stopped.
- `usage: LLMUsage | None` — token accounting if returned.

*Reasoning:* the orchestrator should depend on a small normalized shape, not the
raw provider JSON, so providers can change without breaking callers.

### `LLMUsage`
Token accounting.
- `prompt_tokens: int`
- `completion_tokens: int`
- `total_tokens: int`

*Reasoning:* enables cost/audit logging without re-parsing provider payloads.

### `LLMClientConfig`
Resolved connection settings (built from env vars in §2).
- `base_url: str` — internal LiteLLM endpoint.
- `api_key: str` — secret, loaded from env, never logged.
- `default_model: str` — fallback model name.
- `timeout_seconds: float` — request timeout (default proposed in §5).
- `max_retries: int` — retry budget (default proposed in §5).

*Reasoning:* one immutable config object passed to the client; the only place
that holds the secret, and the only thing tests need to fake.

## 5. Future client behavior

- **Chat completion only.** No embeddings, no tool/function calling, no
  streaming in the first implementation.
- **Timeouts.** Every request uses an explicit timeout (proposed default ~30s).
  No unbounded waits.
- **Retry policy.** Bounded retries (proposed default 2) with backoff, only on
  transient failures (connection errors, timeouts, HTTP 429/5xx). No retries on
  4xx auth/validation errors.
- **Clear error types.** Distinct exceptions, e.g.:
  - `LLMConfigError` — missing/invalid configuration (e.g. no base URL).
  - `LLMAuthError` — 401/403 from the endpoint.
  - `LLMTimeoutError` — request exceeded the timeout.
  - `LLMTransportError` — connection/network failure after retries.
  - `LLMResponseError` — non-2xx or unparseable response body.
- **Logging policy (no leaks).** Log endpoint, model, timing, status, and token
  usage. **Do not log** the API key, full prompts, or full completions by
  default. Prompt/response bodies may be logged only behind an explicit,
  off-by-default debug flag, and the API key is never logged under any flag.
- **Deterministic test strategy.** Tests inject a **mocked `httpx` transport**
  (e.g. `httpx.MockTransport`) so no socket is ever opened. Tests assert on the
  request the client builds and on how it maps faked responses/errors to the
  typed models and exceptions above.

## 6. Safety / boundary rules

The future client is a **thin text/structured-IO boundary**. It MUST NOT:

- know about or read workspace files;
- execute commands or shell out;
- write to GitHub (no commits, pushes, PRs, comments);
- access target project workspaces (`C:\dev\mis_project`, `C:\dev\a8_oa`,
  `C:\dev\bible_reading_v2`, or any path outside this repo).

The client MUST only:

- accept an `LLMRequest`, perform a chat completion against the configured
  internal endpoint, and return an `LLMResponse` (or raise a typed error).

**Later phases decide how to use model output.** The client returns text;
interpreting, applying, or acting on that text is never the client's job.

## 7. Phase split recommendation

- **Phase 3A — design doc only.** *(this document)* No runtime code.
- **Phase 3B — typed models + config loader.** Add `llm/models.py` and
  `llm/config.py` with the §4 models and env loading from the §2 variables.
  Unit tests for model validation and config loading. No network code.
- **Phase 3C — mockable LiteLLM client. (DONE.)** Added
  [llm/client.py](../src/ai_dev_orchestrator/llm/client.py) with `LLMClient`:
  one chat completion (`POST {base_url}/chat/completions`), `config`-driven
  timeout, bounded retries on transient failures (timeout, transport error,
  HTTP 429/5xx) with minimal injectable backoff, and the §5 typed errors
  (`LLMClientError`, `LLMAuthError`, `LLMTimeoutError`, `LLMTransportError`,
  `LLMResponseError`). The client reads no env vars, makes no request at import
  or construction time, and never logs the API key. Tests
  ([tests/test_llm_client.py](../tests/test_llm_client.py)) use
  `httpx.MockTransport`; no real calls.
- **Phase 3D — CLI smoke test (mocked / dry-run only).** Wire a CLI entry that
  exercises the client against a **faked provider or explicit dry-run** —
  still no real model call by default.
- **Later — implementer / reviewer role wiring.** Connect `minimax-m2.7` and
  `qwen3.6-27b` to orchestrator roles. Out of scope for all of Phase 3.

## 8. Phase acceptance criteria / current status

Per-sub-phase acceptance criteria. Boxes are checked as each ships; **no real
model call or external network call is made in any phase's tests.**

### Phase 3A — design doc (DONE)

- [x] The design doc (`docs/PHASE_3_LITELLM_CLIENT_PLAN.md`) exists.
- [x] **No runtime code added in this phase** — no `src/` or `tests/` changes.
- [x] No tests required (docs-only).
- [x] **No external calls** of any kind.

### Phase 3B — typed models + config loader (DONE)

- [x] `llm/models.py` defines `LLMMessage`, `LLMRequest`, `LLMResponse`,
  `LLMUsage`, and `LLMClientConfig` as pydantic models.
- [x] `llm/config.py` builds `LLMClientConfig` from `AIDO_LITELLM_*` env vars
  only (no `.env` files), raising `LLMConfigError` on missing/invalid values.
- [x] Unit tests cover model validation and env loading.
- [x] **No network code** and no model call.

### Phase 3C — mockable client (DONE)

- [x] `llm/client.py` defines `LLMClient` plus the typed errors
  `LLMClientError`, `LLMAuthError`, `LLMTimeoutError`, `LLMTransportError`,
  `LLMResponseError`.
- [x] `chat()` POSTs to `{base_url}/chat/completions`, uses
  `config.timeout_seconds`, and applies bounded retries
  (`config.max_retries`) only on transient failures (timeout, transport error,
  HTTP 429/5xx).
- [x] The client reads no env vars, makes no request at import or construction
  time, and never logs the API key, prompts, or completions.
- [x] Tests (`tests/test_llm_client.py`) use `httpx.MockTransport`; **no real
  network call and no real model call.**

### Phase 3D — CLI smoke test (FUTURE)

- [ ] A CLI entry exercises the client against a **faked provider or explicit
  dry-run**, with **no real model call by default**.
- [ ] Remains offline-testable; no agent behavior, file editing, command
  execution, GitHub writes, or target-workspace access is introduced.
