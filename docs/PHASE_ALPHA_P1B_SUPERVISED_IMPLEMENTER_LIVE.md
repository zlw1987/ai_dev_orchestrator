# ALPHA-P1B — Live Supervised Implementer (implementation record)

> **IMPLEMENTED OFFLINE — AWAITING INDEPENDENT REVIEW. NOT ACCEPTED.**
>
> **ALPHA-P1B-FU1 (2026-10-15):** the review returned CHANGES REQUIRED on one
> blocker, B-1 (replay after run-directory deletion or evidence rotation). FU1
> replaces evidence-directory consumption with a durable authorization ledger.
> See §7. It awaits an independent recheck.
>
> This phase implemented and tested the two live supervised-implementer
> commands **offline only**. No live model request was made, no real source was
> transmitted, no real endpoint was contacted, and no target workspace was
> written. Every test uses a synthetic Git repository under pytest `tmp_path`
> and an `httpx.MockTransport` behind a private seam, always wrapped by AIDO's
> real bounded transport.

| | |
|---|---|
| Kind | Phase implementation record |
| Recorded | 2026-10-15 |
| Baseline | `4e02380` (P1A accepted at `12f728c`) |
| Design | [PHASE_ALPHA_P1B_LIVE_IMPLEMENTER_AUTHORITY_DESIGN.md](PHASE_ALPHA_P1B_LIVE_IMPLEMENTER_AUTHORITY_DESIGN.md), §11 authoritative |
| Policy | [§9 DEC-SUP-LIVE](AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md) |
| Identity | `supervised_implementer` / `SUP-D` / `qwen3.8-27b`, **no qualification credit** |
| Authorizes | Nothing beyond the offline implementation. The first live run needs AUTH-PILOT (D-10) plus a human-completed per-run consent |

The corporate endpoint is deliberately not written in this document, the code
or the tests.

---

## 1. What was built

| File | Change |
|---|---|
| `supervised_implementer/live_authorization.py` | **New.** `supervised-implementer-authorization.v1`: the `bound` section (written by `prepare`), the human `consent` section, `binding_sha256`, exact-typed integers and booleans (R-3), the consent and plaintext phrases, the 60-minute TTL, the 16 MiB bound, the strict duplicate-key-rejecting parser, and the non-parsing draft template. |
| `supervised_implementer/live_transport.py` | **New.** `BoundedCountingTransport` (one request; exact URL, method and canonical body; identity encoding; status class; byte bound during receipt) and the RS1-FU2-pattern deadline worker (one daemon thread, one-shot slot, no join). |
| `supervised_implementer/live_ledger.py` | **New (FU1).** The durable single-use authorization ledger: the exclusive issuance record with its nonce (`prepare`), the read-only unspent check, and consumption by one `O_EXCL` tombstone followed by nonce destruction (`run`). See §7. |
| `supervised_implementer/live_workspace.py` | **New.** AIDO-observed Git state (D-6 / R-1): the 5F2C writer's read-only `_run_git_preflight`, imported unchanged, plus `rev_parse_head`. |
| `supervised_implementer/live.py` | **New.** The live gate, the tightened endpoint check, the wire-payload digest, the evidence-directory checks, `prepare_supervised_implementation`, `run_supervised_implementation`, the run recorder, provenance **v2**, the live result cross-check and `outcome.json`. |
| `supervised_implementer/implementer.py` | Refactor only: `_read_approved_source` and `_proposal_from_reply` extracted so the live path reuses P1A's source rules and reply-to-diff path verbatim. The offline runner's order and behavior are unchanged (P1A suite unchanged and green). |
| `supervised_implementer/models.py` | Refactor only: the v1 diff/provenance cross-check moved into `check_diff_agrees_with_content_provenance`, shared with v2. v1 is unchanged and still means offline mock only. |
| `supervised_implementer/__init__.py` | Docstring only. |
| `models.py` | `SupervisedImplementerConfig` gains `live_transmission_enabled: bool = False`, `attempt_timeout_seconds: float \| None = None` and (FU1) `authorization_ledger_dir: str \| None = None`. Every existing config loads unchanged. |
| `cli.py` | Two commands, `l2-supervised-implementer-prepare` and `l2-supervised-implementer-run`, with exactly the §6.1 option sets; the provider-isolated environment reader; category-only error handling. The module docstring now says four commands may open a socket. |
| `CLAUDE.md` | D-1: the narrow update (supervised vs autonomous implementer, four gated model-calling commands, the new "What the supervised implementer can and cannot do" section, the test rule). |
| Policy | §9 DEC-SUP-LIVE appended; §1–§8 unchanged. |
| Design doc | Current-status banner and §11 (adopted decisions, R-1 to R-12). §0–§10 unchanged as history. |
| `tests/test_supervised_implementer_live.py` | **New**, 135 offline tests. |
| Six command-snapshot test files, `test_workspace_write_target_guard.py`, `test_supervised_implementer.py` | Narrow: the two new command names are added to the frozen command lists, and the "no `implement` in help" assertions now exclude exactly those two lines. The P1A "no CLI command" test now pins that the CLI never reaches the offline runner. |

Not changed: the reviewer, the RS1 supervisor, the verifier, the writer, the
Git adapter, `LLMClient`, `LLMClientConfig`, the env loader, the 5D2 reader, the
5E3 generator, `CANDIDATE_MODEL_IDS`, and every qualification artifact.

## 2. Runtime and authority boundary

```text
prepare (offline; no provider env, no client)
  private copies → live gate → Windows → evidence dir (outside, canonical, exists)
  → identity → target → Git observe → 5D2 read → Git observe (same HEAD)
  → build request → wire payload → digests → bound + binding_sha256 → DRAFT (exclusive create)

run
  a. both flags (is True) → config → private copies → live gate → Windows
  b. strict authorization parse (binding recomputed; exact phrases; ack iff http)
     → not expired, not future, consented_at in [prepared_at, now + 5 min]
  c. evidence dir digest == bound; ledger dir (outside, canonical, disjoint from
     evidence) digest == bound; LEDGER: no tombstone, and an issuance record
     matching run id, binding and nonce digest (absence is never "unused");
     <evidence>/<run_id> must not exist (evidence is never overwritten)
  d. re-derive everything (Git observe → 5D2 read → Git observe) and compare
     plan, config, identity, target, source bytes, HEAD, request digest, limits
  e. read ONLY the 5 AIDO_LITELLM_* names, once → shipped loader → overrides
     (registry model, bound timeout, retries 0) → endpoint check → == consent
     scheme/host/port                                   [nothing sent or consumed yet]
  f. CONSUME in the ledger: O_EXCL create <run_id>.consumed.json [exclusive]
     → re-check the issuance bytes → delete them (nonce destroyed) → settled
     (any failure from here: spent, nothing sent)
  f2. os.mkdir(<evidence>/<run_id>)                      [evidence only]
  g. CONSUMED, authorization.json, request-messages.json, transmission-pending.json
     (each exclusive-create + fsync)
  h. announce banner on stderr (failure → nothing sent, consent spent)
  i. request digest re-checked on the exact object (A-9) → transport + client
  j. ONE request: daemon worker, AIDO monotonic deadline, bounded counting transport
  k. reply → model/finish checks → strict parser → AIDO proposed-content → 5E3 diff
     → writer reachability → provenance v2 + cross-check + JSON round trip
  l. response-content.txt, diff-proposal.json, provenance.json, outcome.json → STOP before H6
```

Exit codes: **0** a diff or no-change proposal; **1** refused (nothing sent;
before step f the authorization is untouched); **4** the request worker started
and no usable proposal resulted; **5** the request worker started and the
evidence is incomplete.

## 3. Adversarial analysis

### 3.1 Before coding

The design's A-1 to A-22 stand. The pre-coding pass over every
authority-bearing object added R-1 to R-12, recorded in design §11.4: AIDO-owned
Git observation (D-6), structured output off (D-9), pydantic's `Literal[1]` /
`Literal[False]` truthiness hole, the shipped client parsing 3xx as success,
binding the wire payload instead of an AIDO serialization, the URL parser
differential, `trust_env` affecting TLS trust, transmission lagging the worker
start, two exclusive state files instead of a rewritten record, `mkdir` as the
consumption primitive, environment values echoed by `LLMConfigError`, and
linked evidence directories.

### 3.2 After coding, against the implementation

| # | Counterexample tried | Finding | Resolution |
|---|---|---|---|
| P-1 | Outbound body `{"max_tokens": true}` or `1.0` where `1` was consented | **Material.** The wrapper compared decoded JSON with Python `==`, which equates `true`, `1` and `1.0`. | Compare canonical JSON bytes. Regression: `test_the_wrapper_compares_canonical_json_not_python_equality`. |
| P-2 | stdout fails while printing the success provenance | **Material.** The CLI's post-report output was outside the catch-all, so a traceback (and the exception text) could render after a real transmission. | Report output wrapped; category-only message; exit 5 when the run had succeeded. Regression: `test_a_reporting_failure_after_transmission_never_shows_a_traceback`. |
| P-3 | The request object mutated after the binding comparison | Confirmed closed by the A-9 re-check, which runs **after** consumption: the run ends `refused_after_consumption`, nothing is sent, and the consent is spent. | Regression: `test_a_request_mutated_after_validation_is_never_sent`. |
| P-4 | A crash between `mkdir` and `CONSUMED` | Any existing run directory, even an empty one, blocks replay. §6.3's "a run directory with `CONSUMED`" is therefore read as "any run directory". | Regression: `test_any_existing_run_directory_blocks_replay`. |
| P-5 | Mismatched identity, consent forgery, replay, stale Git, proxy and redirect routing, failed and malformed responses, credential leakage | No further bypass found through the shipped entry points. | §4 lists the regressions. |

### 3.3 Residual limits (not defects; stated so they are not over-claimed)

- *(Superseded by FU1, §7.)* ~~The ledger is the evidence directory.~~ The
  ledger is now separate and durable. Its own residual, restoring a
  pre-consumption copy of the ledger, is in §7.5.
- **Unsigned artifacts (A-19, §3.3).** An operator who edits `bound` and
  recomputes `binding_sha256` defeats the digest. Every re-derivable field is
  still compared at consumption (`test_a_recomputed_binding_is_still_caught_by_re_derivation`).
  In-process Python can call lower-level functions directly; the private
  `_now` and `_inner_transport_factory` seams are test seams, and AIDO always
  wraps whatever inner transport in its own bounded transport.
- **A `BaseException` (for example Ctrl-C) after the worker started** leaves
  `transmission-pending.json` without `outcome.json`. The procedure treats that
  as "transmitted".
- **Evidence file permissions.** Files are created `0o600` where the platform
  honours it. On Windows they inherit the evidence directory's ACL; choosing a
  protected directory is the operator's job.
- **https with a private CA is unsupported.** The live transport ignores
  `SSL_CERT_FILE`/`SSL_CERT_DIR` (R-7) and there is no CA option, so such an
  endpoint fails closed as `transport_failed`. The pilot design uses http.
- **The Git observation brackets the read; it does not lock the tree**, and it
  says nothing about ignored files, the remote, or anything outside the
  repository.
- **Backend lifetime after a stall is unobserved.** The wording everywhere is
  "AIDO stopped waiting", never "cancelled".
- **Pre-existing, outside scope:** the shipped reviewer's client still honours
  environment proxies (A-3 backlog), and P1A's v1 provenance uses
  `Literal[False]`, which also accepts `0` (AIDO-built output only, not an
  authority input; unchanged).

## 4. Regression coverage (`tests/test_supervised_implementer_live.py`)

| Design §7.3 item | Tests |
|---|---|
| 1 Gates | opt-in absent/false/forged (`"yes"`, `1`, `"true"`), vllm, structured output, missing timeout, `enabled: false`, wrong model; `live_transmission_enabled` turned off after prepare: no env read, no run dir |
| 2 Consent parse | draft, wrong / H2 / H6 phrase, missing / wrong / needless acknowledgement, naive time, `source`, wrong echoed digest, bool / string port, blank name, extra / missing key, duplicate key, consent before prepare |
| 3 Binding mismatches | timeout, max tokens, `allow_insecure_http` toggles; different plan; committed source edit; empty commit (HEAD only); modified and untracked files; patched system prompt; other evidence dir; expiry; endpoint host, port, missing port and https→http downgrade; nine edited bound fields including `true` for a count (R-3); recomputed-binding forgery |
| 4 Single use | replay after success and after failure; an existing run dir is refused and spends nothing; two concurrent consumers with exactly one winner and one request; FU1's ledger lifecycle regressions in §7.4 |
| 5 Provider isolation | spy environment for the CLI reader (vllm touches nothing) and for the loader; env model, timeout and retries overridden |
| 6 Endpoint | userinfo, query, fragment, ftp, backslash+`@`, whitespace, newline, bad port: refused and unechoed; http without the project opt-in; the URL path never echoed or persisted |
| 7 Transport | proxy variables not consulted; default transport `retries=0, trust_env=False`; 301/302/307/308 terminal; gzip refused; declared and streamed oversize; second request refused; unconsented URL/port/body refused before the inner transport; canonical body comparison; violations are not `httpx` errors |
| 8 Deadline | supervisor deadline: terminal, one request, daemon worker still alive, no join, conditional wording; client timeout; static checks for no executor/asyncio/join/cancel |
| 9 Failures | 400 (structured-output-style rejection), 401, 403, 429, 500, malformed body, connect error: each exactly one request, no completion recorded |
| 10 Output | fenced, `<think>`-prefixed, reasoning-only, extra key, `finish_reason` length and None (no budget claim), model substitution, secret-shaped content, missing final newline: rejected, digest-only, never persisted |
| 11 Mutation | announce callback mutating env, config and plan; failing announce; request mutated after validation |
| 12 Evidence | pending record before the request; evidence failure after a reply (exit 5); v2 cross-check, tamper and `0`-for-`false` refusal |
| 13 Secrets | key, `Bearer`, env default model and URL path absent from all output and evidence; unexpected exceptions before and after consumption are category-only; `pretty_exceptions_show_locals` is false; the real CLI entry point |
| 14 No writes | workspace bytes, HEAD and status unchanged across success, failure and rejection; static source checks for writes, subprocess, environ, approval, apply, verify |
| 15 Baselines | P1A suite; command snapshots; exact option sets; the CLI never reaches the offline runner or names a transport; no real endpoint in code, tests or design |

## 5. Offline test results

`.venv/Scripts/python.exe -m pytest tests -q` on 2026-10-15: **3741 passed,
0 failed** in 7 min 56 s. The new `tests/test_supervised_implementer_live.py`
contributes 135 tests, and the P1A suite stays at 102. The one warning is the
pre-existing pydantic serializer warning from a P1A forged-config test. All runs
were offline: no socket, no real key, no real target workspace.

Snapshot tests changed narrowly: the frozen command lists gained the two new
commands, the "no `implement` in root help" assertions now exclude exactly
those two lines, and the write-target-guard caller set gained
`live_workspace.py`, a read-only caller.

## 6. Conditions for the first live pilot (all required; none exists yet)

1. **Independent review accepts ALPHA-P1B** (this implementation, DEC-SUP-LIVE,
   and the `CLAUDE.md` update).
2. **AUTH-PILOT (D-10):** a separate operator decision naming the repository, a
   fresh disposable clone location, the one tracked target file, and the
   operator. Never a working checkout, never the Alpha-0 clone.
3. The clone is on **Windows**, its top level is exactly `repo.workspace_path`,
   its tree is **wholly clean**, it has no filter/helper configuration (global
   included, e.g. git-lfs) and no submodule, and the target is tracked as an
   ordinary blob in uniform LF or CRLF text ending in a newline. AIDO verifies
   all of this itself; the operator only chooses.
4. Config: `supervised_implementer` with `enabled: true`,
   `live_transmission_enabled: true`, `candidate: SUP-D`, `model: qwen3.8-27b`,
   `provider: litellm`, `structured_output: false`, an explicit
   `attempt_timeout_seconds`, `max_output_tokens` absent, and
   `allow_insecure_http: true` only if the endpoint is http, and (FU1)
   `authorization_ledger_dir` naming an existing directory outside the clone,
   not inside or around the evidence directory, and not in a folder that a
   sync client or backup tool restores.
   `read_only_workspace_content.enabled: true` with caps that admit the file.
5. An approved L1 plan (exact H2 phrase) naming the target in
   `files_likely_to_change`, stored outside the clone.
6. An evidence directory outside the clone, named by its canonical path, with
   an ACL appropriate for source-bearing evidence.
7. A fresh shell in which **only** the five `AIDO_LITELLM_*` names are set for
   the corporate endpoint; this machine's persistent reviewer variables must be
   cleared or overridden (A-2). AIDO refuses any host, port or scheme the human
   did not type.
8. `prepare`, then a human-completed consent within 60 minutes: `consented_by`,
   `consented_at`, `binding_sha256` echoed, the endpoint scheme, host and
   **effective** port typed by the human, the exact consent phrase, and the
   exact plaintext acknowledgement for http.
9. `run` with `--transmit-approved-source --real-implementer`. The operator
   confirms the banner names the expected host, port, model and
   `NOT TLS-ENCRYPTED` (for http) before it matters.
10. STOP at `human_exact_diff_approval_required`. H6 and anything after it
    needs its own authorization. The pilot qualifies nothing.

## 7. ALPHA-P1B-FU1 — durable single-use authorization (B-1)

### 7.1 Root cause

Single use was decided by one fact: whether `<evidence>/<run_id>` existed. The
evidence directory is operator-managed, and deleting, rotating and archiving it
are ordinary lifecycle operations. Its **absence** was treated as proof that the
authorization was unused, so the reviewer could send source a second time after
a success, after a 500, and after a stall whose first request was still in
flight. `authorization_reusable: false` and the `CLAUDE.md` line "never
replayable" were therefore untrue. The operator chose route (a): durable
consumption state.

### 7.2 Mechanism (design §11.6)

```text
prepare  … bound gains authorization_ledger_dir_sha256 + issuance_sha256 = SHA-256(nonce)
         → O_EXCL create <ledger>/<run_id>.issued.json {run_id, binding_sha256, nonce, issued_at}
run   c. ledger dir digest == bound; no <run_id>.consumed.json; issued record present,
         plain, small, strict, and matching run_id, binding_sha256 and SHA-256(nonce)
      f. O_EXCL create <run_id>.consumed.json        ← the ONE linearization point
         → re-check issued bytes → delete issued (nonce destroyed) → settled
      f2. mkdir <evidence>/<run_id> → … → ONE request
```

- **Who creates authority.** Only AIDO's `prepare`, by exclusively creating the
  issuance record. The record grants nothing without a human consent that
  echoes `binding_sha256`, and `binding_sha256` covers `issuance_sha256`.
- **What proves "never consumed".** A present issuance record whose nonce
  hashes to the bound `issuance_sha256`, together with no tombstone. Nothing
  else does: a missing ledger, a missing record, an unreadable or foreign record
  all refuse.
- **Why `O_EXCL`.** Measured on this machine with 4 racing threads × 300
  trials: `O_CREAT|O_EXCL` had exactly one winner every time. `os.rename` of one
  source reported success in **all four** threads in every trial, because each
  opened the source before any rename finished. `os.remove` reported several
  successes in 80 of 300 trials. Neither is used as a claim.
- **The ledger is not the evidence.** It is a separate config-named directory,
  disjoint from the evidence directory, so the two never share a lifecycle.

### 7.3 Pre-coding adversarial analysis

| # | Question | Answer |
|---|---|---|
| 1 | Who creates the durable authority? | `prepare` only, one exclusive issuance record per run id, written last after every check. |
| 2 | Who may mutate or delete it? | AIDO's `run` creates the tombstone and deletes the issuance record. The OS account can do anything; AIDO does not defend against deliberate rollback of its own state (A-19), the same as recomputing `binding_sha256`. |
| 3 | What proves an authorization was never consumed? | A positive, matching issuance record and no tombstone. Absence never does. |
| 4 | Evidence rotated independently of authority? | It cannot restore authority: the ledger is a different, disjoint directory, and the evidence only records. |
| 5 | Concurrent consumers? | Serialized by the `O_EXCL` tombstone create. A loser gets `FileExistsError` and refuses before any request. |
| 6 | Restart and partial failure? | State is only on disk. A crash after the tombstone leaves it spent, with or without evidence. A failure to create the tombstone writes nothing, so the authorization is untouched. Every failure after the tombstone exists ends `refused_after_consumption` with nothing sent. |
| 7 | Can a supported caller bypass it? | `run_supervised_implementation` is the only live entry point, and it always calls `check_unspent` and then `consume_issuance` before the transport exists. Ledger switching is refused by the bound digest and the config digest; evidence switching by `evidence_dir_mismatch`. |
| 8 | Malformed identities, post-validation mutation? | The run id is regex-checked before it becomes a file name. Records are `lstat`-checked (regular, no reparse point, ≤ 4 KiB) and strictly parsed. The issuance bytes are re-checked by the tombstone's creator, so a swap after the read-only check spends and sends nothing. |
| 9 | Sensitive diagnostics on storage failure? | Fixed category and message only, never a path or exception text. The ledger holds no source, credential, URL or header, and the nonce is never printed. |

### 7.4 Regressions (`tests/test_supervised_implementer_live.py`, section 6b)

| Required scenario | Tests |
|---|---|
| 1 success → delete run dir | `test_fu1_success_then_run_dir_deleted_replay_is_refused` |
| 2 HTTP failure → delete run dir | `test_fu1_http_failure_then_run_dir_deleted_replay_is_refused` |
| 3 stall → rotate evidence, original still in flight | `test_fu1_stall_then_evidence_rotated_replay_is_refused_while_in_flight` (also deletes the rotated evidence) |
| 4 concurrency | `test_fu1_concurrent_consumers_produce_at_most_one_transmission[2,4]` and the original two-thread test, all forced to race at the exclusive create |
| 5 crash / exception after consumption | `test_fu1_crash_after_consumption_then_restart_replay_is_refused` (a child process `os._exit`s right after consuming), `test_fu1_crash_in_flight_then_restart_replay_is_refused` (dies inside the request), `test_fu1_an_exception_after_consumption_spends_and_sends_nothing` |
| 6 process restart | the two crash tests replay in a fresh interpreter, and `test_fu1_process_restart_after_success_replay_is_refused` |
| 7 missing / corrupt state | `test_fu1_missing_corrupt_or_foreign_ledger_state_fails_closed` (15 cases: record deleted or renamed, ledger rotated or deleted, garbage, extra key, wrong type, oversize, directory, wrong nonce, binding or run id, a genuine record from another authorization, planted or directory tombstone) and `test_fu1_post_consumption_ledger_lifecycle_never_restores_authority` (tombstone deleted, ledger rotated, pre-consumption copy restored beside the tombstone, ledger and evidence both rotated) |
| 8 evidence substitution | `test_fu1_another_ledger_or_evidence_dir_cannot_regain_authority` (a copied ledger, another evidence dir, both, before and after consumption) |
| 9 identity mismatch | `test_fu1_a_recomputed_issuance_digest_is_refused`, `test_fu1_edited_ledger_bindings_are_refused`, the foreign-record cases above, `test_fu1_a_record_swapped_after_validation_spends_and_sends_nothing` |
| 10 durable-state write failure | `test_fu1_a_failed_consumption_create_sends_nothing_and_spends_nothing`, `…_a_partial_consumption_record…`, `…_an_unremovable_issuance_record…`, `…_a_run_dir_failure_after_consumption…`, `…_an_issuance_write_failure_writes_no_draft`, `…_an_existing_out_writes_no_ledger_record` |
| 11 fresh authorization works once | `test_fu1_fresh_authorization_still_sends_exactly_once_and_settles_spent` (also: nonce absent everywhere afterwards; a second fresh authorization works once) |
| Location rules | `test_fu1_the_ledger_location_is_required_and_independent` (absent, null, relative, missing, in workspace, equal to / under / around evidence), forged types, `test_fu1_the_ledger_is_not_part_of_p1a` |

Changed existing tests: the fixtures add a ledger directory; the old
"any run directory blocks replay" test is now
`test_an_existing_run_directory_is_never_overwritten` (category
`evidence_run_dir_exists`, nothing spent); the recomputed-binding forgery is now
refused first by the ledger, and still by re-derivation when the ledger record
is forged too; the concurrency barrier moved to the exclusive create; and
`live_ledger.py` joined the static no-write/no-environ/no-subprocess check.

FU1 offline results (2026-10-15), all on the project venv:

- `pytest tests/test_supervised_implementer_live.py`: **188 passed**
  (135 → 188).
- P1A + live + CLI snapshot + write-guard suites, rerun on the final source:
  **696 passed**.
- Full `pytest tests`: **3794 passed, 0 failed**, in 9 min 27 s. The one
  warning is the pre-existing P1A pydantic serializer warning.
- The concurrency and rotation tests were repeated 6–10 times each without a
  failure.

### 7.5 Post-implementation self-review

| # | Attack on the actual code | Finding | Resolution |
|---|---|---|---|
| F-1 | A first draft claimed by `os.rename(issued → claimed)` so that deletion would be monotone in every state. | **Material.** The concurrency regression showed two and four "winners". Measured: racing renames of one source all succeed on Windows. | Reverted to the `O_EXCL` tombstone as the only linearization point; the measurement is recorded in §7.2 and in the module docstring, and `CLAUDE.md` forbids rename/remove as the claim. |
| F-2 | A recomputed `binding_sha256` | Now refused earlier by the ledger, which pins the binding prepare wrote. | Test split so both layers stay covered. |
| F-3 | An existing `--out` at prepare | Would have left an orphan issuance record. Harmless, because it grants nothing without consent, but untidy. | The CLI refuses an existing `--out` before `prepare` touches the ledger. |
| F-4 | Delete the tombstone in the one unsettled state where the issuance record could not be deleted | Restores an authorization that **never transmitted**, so it still permits at most one request in total. It needs an OS failure and then a deliberate manual deletion. | Documented residual. |
| F-5 | Rotation tests on Windows | Renaming a just-written evidence directory was intermittently denied by an external holder (an indexer or scanner). | The test helper retries for at most 10 s. A handle leaked by AIDO would outlast that and fail the test; 10 of 10 repeated runs passed. |

Residual limits, none of them material to B-1:

- **A deliberate rollback** of the ledger to a pre-consumption copy, together
  with deleting the tombstone, restores the authorization until it expires.
  That is outside A-19's threat model, like recomputing the binding. The
  pilot procedure (§6, item 4) keeps the ledger out of restoring folders.
- **F-4 above.**
- **Power loss.** Records are fsynced, but Windows has no directory fsync, and
  durability across power loss is not claimed.
- **Growth.** Tombstones and the issuance records of unused authorizations
  accumulate. Pruning is safe except in the F-4 state.

---

**Status: ALPHA-P1B IMPLEMENTED; FU1 (B-1) IMPLEMENTED — READY FOR INDEPENDENT
RECHECK.** Not accepted.
