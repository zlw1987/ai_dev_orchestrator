# P0-UX-H2-SIMPLE — One-confirmation H2 consent

| | |
|---|---|
| Kind | Implementation and review handoff (offline) |
| Recorded | 2026-11-24 |
| Baseline | `7c63544f7e33a3a392095a4bfab695974c0af790` |
| Lead engineer | Claude Code |
| Independent final reviewer | ChatGPT |
| Policy | [§14 P0-UX-H2-SIMPLE](AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md) |
| Operations | [ALPHA_2A_TASK_COORDINATOR.md §11](ALPHA_2A_TASK_COORDINATOR.md), [PHASE_ALPHA_P1B_SUPERVISED_IMPLEMENTER_LIVE.md §11](PHASE_ALPHA_P1B_SUPERVISED_IMPLEMENTER_LIVE.md) |
| Status | **IMPLEMENTED offline, awaiting independent review.** Nothing committed, pushed, installed or promoted. No live model request, no real source transmission. The active M3LIVE1 run was not touched. `CLAUDE.md` was not edited. |

---

## 1. Summary

A project opts in by pinning its implementer destination in trusted project
config, as `supervised_implementer.endpoint` (scheme, host, explicit port,
base path). This reuses the existing `controlled_review.endpoint` model and
validator. For such a project:

- `task-approve` checks `AIDO_LITELLM_BASE_URL` against the pin **before**
  showing H2.
- It then shows the complete destination, its environment match, the TLS
  state (with a `NOT TLS-ENCRYPTED` banner for http), the candidate and model,
  the file and its digest, the request digest and the expiry.
- The operator types **`approve` once**. The endpoint, `transmit` and
  `plaintext` prompts are gone for pinned projects.
- The decision record says truthfully that one answer was typed, and holds the
  exact screen shown.
- `task-continue` is still the only sender. P1B's run checks the pin in full
  again before anything is consumed.

The typed flow is unchanged for every project without the pin, and for every
run started before the pin was added.

The mismatch that started this (an operator typed `/v1` with no port at H2 in
M3LIVE1) can no longer happen in a pinned project. The operator types no
endpoint, and the `/v1` path that the typed flow never checked is now
compared.

---

## 2. Source diff

| File | Change |
|---|---|
| `src/ai_dev_orchestrator/models.py` | `SupervisedImplementerConfig.endpoint: ControlledReviewEndpointConfig \| None = None`. A serializer helper `omit_absent_implementer_endpoint` drops it when absent, so unpinned configs and every digest over them are byte-identical. Docstrings corrected. |
| `src/ai_dev_orchestrator/supervised_implementer/live.py` | The live gate refuses a pinned `http` destination without `allow_insecure_http` (`endpoint_plaintext_not_permitted`). It adds `check_pinned_endpoint(base_url, pinned)`, which reuses the reviewer's `reviewer_request_url` and `check_reviewer_destination` (scheme, raw host, effective port, exact path `<base_path>/chat/completions`, no userinfo, query or fragment). It refuses as `endpoint_not_authorized`, naming only the component and never echoing the URL. `run_supervised_implementation` calls it after `check_live_endpoint` and before the unchanged consent comparison and consumption. |
| `src/ai_dev_orchestrator/task/approve.py` | Adds `SingleApprovalConsentBinding`. The run's mode comes from the pinned config inside `consent_subject`, which adds the candidate and the pinned destination to the recomputed binding. Also: mode-specific answer fields; a consistency check (environment matched, screen digest); serialization of the unchanged P1B consent block from the pin; the destination screen; `check_pinned_environment`; and `single_approval_answers`. |
| `src/ai_dev_orchestrator/cli.py` | `_run_task_approve` checks the environment before displaying a single-approval H2 and again after the answer. It records the printed screen. The `task-approve` help text names the mode. |
| `tests/test_task_approve_single_h2.py` | **New**, 48 offline tests (§4). |
| `docs/…` | Policy §14 (H2S-1 to H2S-4), coordinator §11 (operations and sample screen), P1B §11, and this handoff. |

No schema version changed. The following are untouched: `aido-task-decision.v1`,
`supervised-implementer-authorization.v1`, its consent phrases, the ledger, the
TTL, the wire payload, the transport, provenance, H1, H3, the reviewer, model
selection and generation parameters.

The complete diff is `git diff 7c63544` plus the new test file.

---

## 3. Contract amendment summary (policy §14)

| # | Rule |
|---|---|
| H2S-1 | `supervised_implementer.endpoint` pins the destination in trusted config and authorizes, never replaces, `AIDO_LITELLM_BASE_URL`. A pinned http destination requires `allow_insecure_http: true`. The pin is bound through `project_config_sha256`. When absent, the config serializes byte-identically. |
| H2S-2 | The pin is the opt-in. The environment must match the pin in full before display and again before recording. One `approve` consents to the whole disclosed transmission, including a displayed plaintext risk. `reject` is recorded. Anything else cancels and records nothing. |
| H2S-3 | The record carries `confirmation: "single_approval"`, the pinned destination, `endpoint_matched_environment: true` and the exact screen with its SHA-256. It carries no `transmit` or `plaintext` answer. The P1B consent block is serialized from it with the fixed phrases. The record, not the block, is the audit of how consent was given. |
| H2S-4 | `task-approve` sends nothing. `task-continue` alone sends, and P1B rechecks the pin in full (`endpoint_not_authorized`) before consumption. |

**The mode belongs to the pinned config, never to the record.** A typed record
is refused in a pinned run, and a single-approval record is refused in an
unpinned one.

Amended: DEC-SUP-LIVE A-2 and PO-UX-1/2, **for pinned projects only**.

---

## 4. Focused tests and results

`tests/test_task_approve_single_h2.py`, 48 tests. All are offline: a synthetic
Git repository under `tmp_path` and `httpx.MockTransport` for both models.

| Requirement | Tests |
|---|---|
| Exactly one approval | `test_h2_takes_exactly_one_typed_approve_and_sends_only_at_task_continue` (one prompt, environment read twice, nothing sent or consumed until `task-continue`, then exactly one request to `…/v1/chat/completions`, H3 still separate); `test_the_typed_answers_do_not_apply_in_a_pinned_run` |
| Screen shows destination and HTTP risk | `test_the_screen_discloses_the_destination_the_transmission_and_the_http_risk`; `test_an_https_destination_is_shown_as_tls_and_needs_no_plaintext_acknowledgement` |
| Environment matches the pin, including `/v1` | `test_an_environment_that_is_not_the_pinned_destination_shows_and_records_nothing` (10 cases: unset, no `/v1`, `/v2`, `/v1/extra`, port 9090, implicit port 80, https, other host, userinfo, query; nothing shown, asked or recorded, and the URL is not echoed); `test_an_environment_that_changes_while_displayed_records_nothing`; `test_a_trailing_slash_is_the_same_request_and_matches`; `test_check_pinned_endpoint_compares_scheme_host_port_and_path` |
| Checked again before transmission | `test_p1b_checks_the_pinned_destination_again_before_sending` (3 cases: a path-only change, which P1B's old scheme/host/port check would have let through, is refused as `endpoint_not_authorized`, unconsumed; the same consent then works with the right environment) |
| Config coherence | `test_a_pinned_http_destination_needs_allow_insecure_http` (refused at `task-start`; https accepted) |
| Config change, stale or altered drafts and records, expiry | `test_a_changed_config_refuses_approval_and_transmission`; `test_an_altered_draft_is_refused`; `test_a_draft_changed_while_displayed_records_nothing`; `test_an_altered_decision_record_is_refused_and_sends_nothing` (10 mutations: port, base path, host, TLS flag, model and candidate, target, screen, environment flag, missing `confirmation`, added `transmission_confirmed`); `test_an_expired_authorization_can_be_neither_decided_nor_sent` |
| Cancel and reject | `test_cancel_records_nothing` (7 answers, including a typed endpoint and `transmit`); `test_reject_is_recorded_truthfully_and_ends_the_task` |
| No carry-over | `test_a_decision_does_not_carry_over_to_a_fresh_authorization`; `test_a_decision_does_not_carry_over_to_another_run`; `test_a_typed_record_from_the_old_contract_is_refused_in_a_pinned_run`; `test_the_correction_round_uses_the_same_single_approval_and_its_own_decision` (round 1's record copied into round 2 is refused; round 2 takes one `approve` on its own authorization) |
| Backward compatibility | `test_a_config_without_the_pin_serializes_byte_identically_and_keeps_the_typed_h2` |

**Actual results** (venv interpreter, `-p no:cacheprovider`, offline: synthetic
repositories under `tmp_path`, `httpx.MockTransport`, no socket, no real model):

| Run | Result |
|---|---|
| `tests/test_task_approve_single_h2.py` (new) | **48 passed** |
| Baseline at `7c63544`, before the change: the six focused coordinator, approval and P1B files | 651 passed, 1 warning, 713 s |
| Full `tests/` directory **with** the change | **6188 passed, 0 failed, 1 warning**, 7511 s (2 h 05 min) |

The one warning is the same before and after: a deliberate pydantic serializer
warning in `test_a_post_load_forged_block_is_refused_by_revalidation`, which
forges `enabled='yes'` after load. It is unrelated to this change. The DL-4B S0
machine-DACL test that has failed on this machine before did not fail in this
run.

---

## 5. Sample H2 screen

This is real output from the synthetic offline setup (`fake-gateway.invalid`
is a test host). Digests are shortened here. The full screen is in
[ALPHA_2A_TASK_COORDINATOR.md §11](ALPHA_2A_TASK_COORDINATOR.md).

```text
DESTINATION (pinned by the project config, project_config.supervised_implementer.endpoint):
  http://fake-gateway.invalid:8080/v1
  scheme http, host fake-gateway.invalid, port 8080, base path /v1
  the one request goes to exactly http://fake-gateway.invalid:8080/v1/chat/completions
  environment: AIDO_LITELLM_BASE_URL matches this destination exactly (scheme, host, effective port and path; checked just now, again before your answer is recorded, and again by task-continue immediately before sending)
  transport: NOT TLS-ENCRYPTED (plaintext http)
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!  PLAINTEXT HTTP: this source will be sent NOT TLS-ENCRYPTED.        !!
!!  Anyone on the network path can read it. This is not secure.        !!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Typing 'approve' consents to this ENTIRE transmission as shown above, including sending it NOT TLS-ENCRYPTED. It is the only confirmation. It records the decision only and sends nothing: the transmission happens only when you run task-continue --transmit-approved-source --real-implementer, within the authorization's validity.

Type 'approve' to approve this implementer consent, 'reject' to reject it, anything else to cancel: approve
APPROVED: recorded in 20-authorization-1.decision.json. Recording runs nothing: nothing was prepared, sent, written or verified.
```

Above the destination block, the screen shows the same lines as today:
workspace, source scope, provider, model and candidate, what is sent, the file
with its size, SHA-256 and HEAD, the request SHA-256, and the authorization id
with prepared and expiry times, minutes left and "single use".

---

## 6. Backward-compatibility evidence

- **Serialization.** An unpinned config's `model_dump` has no `endpoint` key
  and round-trips byte-identically. So `project_config_sha256`, every
  `binding_sha256` and the golden request digests are unchanged. The existing
  suites pass unmodified (§4).
- **Existing active runs.** A run is pinned to its config by SHA-256. A run
  started without the pin derives the typed mode from that config on every
  step, and adding the pin to its config refuses every later step, as before.
  The M3LIVE1 run's config has no pin, so it would keep the typed H2; it was
  not touched.
- **Historical records.** `ConsentBinding` and every v1 decision record are
  unchanged and still parse. In an unpinned run a typed record is validated
  exactly as before. `tests/test_task_approve.py` passes unmodified.
- **No silent fallback.** A pinned run never accepts a typed record or typed
  answers. An unpinned run never accepts a single-approval record. A
  destination mismatch refuses; nothing falls back to the typed flow or to a
  weaker check.
- **Unchanged identities.** `SUP-D` and `SUP-M3`, model selection, generation
  parameters, transport retries (0) and every reviewer path are untouched.

---

## 7. Review notes and residual limits

- **The consent block's plaintext phrase.** P1B's schema requires the exact
  acknowledgement phrase for http, and this amendment does not change P1B's
  schema. In single-approval mode AIDO therefore serializes that phrase from
  the one `approve`, which policy H2S-2 defines as covering the displayed
  plaintext risk. The decision record (`confirmation: "single_approval"`, the
  exact screen) is the truthful account of what was typed.
- **Reading the environment before the decision.** In pinned mode, the one
  environment value `AIDO_LITELLM_BASE_URL` is read before the screen is
  shown, so the screen can state the match. In the typed mode it was read
  after `approve`. No key is read in either mode.
- **A mismatched environment means no screen.** H2 cannot be shown, or
  rejected, until the environment matches. The operator fixes the environment;
  an unconsumed authorization simply expires.
- **Validator wording.** A malformed pin is refused by the shared validator,
  whose message says `controlled_review.endpoint`. Pydantic's error location
  names `supervised_implementer.endpoint`. The wording was left as it is so the
  reviewer path is unchanged.
- **Scope of the check.** The host is authorized as text: DNS and routing are
  not observed, and over http nothing authenticates the server. The recorded
  screen proves what AIDO printed, not that a person read it (A-19).
- **Not added:** no new command, flag, approval stage, schema version,
  authorization framework, `task-doctor` pin writer, or run-time derivation of
  the pin.
