# ALPHA-P1A — Supervised Implementer, Offline and Library-Only

> **Authorized by DEC-SUP option A (2026-10-14).** See
> [ALPHA_P1A_DEC_SUP_DECISION_PROPOSAL.md](ALPHA_P1A_DEC_SUP_DECISION_PROPOSAL.md)
> and [policy §8](AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md).
>
> **What this phase is:** an offline foundation for a model-backed *supervised*
> implementer, built from the existing L2 contracts and tested only through
> `httpx.MockTransport`.
>
> **What this phase is not:** a qualification, a live integration, a CLI
> command, or a writer. **Qwen 3.8 has NOT passed Autonomous Implementer
> Qualification.** `SUP-D` carries no qualification credit of any kind.
>
> **Status (updated 2026-10-20): ACCEPTED and committed as `12f728c`** (an
> ancestor of the current history). The independent review had returned CHANGES
> REQUIRED (governance and offline-claim wording only); the ALPHA-P1A-FU1
> corrections (§7) were applied before that commit.
>
> *Superseded wording: "uncommitted, awaiting independent recheck".*

| | |
|---|---|
| Live requests made | **0** |
| Real source transmitted | **none** |
| Real workspace touched | **none** (tests use synthetic `tmp_path` directories) |
| Writer / verifier / reviewer invoked | **no** |
| `CANDIDATE_MODEL_IDS` | unchanged: exactly A, B, C |
| Closed Alpha-0 run directory | not read, not modified |

## 1. The flow

```text
approved plan + project config            re-validated into private copies
  → gates (all before any disk access):
      transmit_source is True             exact identity, never truthiness
      transport is exactly MockTransport  P1A offline restriction, by type
      supervised_implementer config       SUP-D ⇔ qwen3.8-27b, exact; provider litellm|vllm
      endpoint                            https, or http only with the acknowledgement
      identity                            plan ⇔ project, exact
      target path                         caller-chosen; in files_likely_to_change;
                                          not out of scope; ALLOWED for write; normal form
  → Phase 5D2 bounded read, IN-PROCESS    the shipped reader, extracted unchanged
  → target must be: read, a file, NOT redacted, canonical spelling == target,
                    uniform LF/CRLF with a terminal newline (the writer's domain)
  → announce(SourceTransmissionNotice)    before handing the request over
  → ONE request                           max_retries forced to 0; no fallback
  → reply checks                          model field == requested; finish_reason == "stop"
  → strict parse                          exactly {"content_text": str}; rejected, never repaired
  → AIDO assembles proposed-content.v1    path, change type and prose come from AIDO
  → build_deterministic_diff_proposal     unchanged 5E3 rules (scope, redaction, secrets, digests)
  → in-memory reachability                the writer's own strict applier and rejoin
                                          must reproduce the proposed bytes
  → SupervisedImplementerResult           diff proposal + content provenance, cross-checked
  → STOP                                  next_step: human_exact_diff_approval_required
```

The result carries **no approval**. A human approves the diff through the
unchanged Phase 5F0 artifact. After that, the unchanged 5F1 preview, 5F2C
writer, 5F2D verifier and 5F2E reviewer each keep their own gates and
consents. None of them changed.

## 2. Authority decisions

| Object | Authority | How it is enforced |
|---|---|---|
| Candidate identity | `SUP-D` → `qwen3.8-27b`, a read-only `MappingProxyType`, separate from `CANDIDATE_MODEL_IDS` | Config must name **both** candidate and model, and they must match the registry exactly, so substitution is refused. The reply's `model` field must equal the requested model. |
| Write authority | **None.** Model output is proposed content | The package opens no file for writing, creates no approval, applies nothing, runs nothing. Source-inspection test. |
| Which file | The caller (a human), never the model | The model's reply schema has no path field; extra keys reject the whole reply. AIDO writes the path into proposed-content. |
| Source read | Phase 5D2, in-process, behind `read_only_workspace_content.enabled` | The same reader the CLI uses (extracted, not duplicated). No saved packet is trusted. |
| What is transmitted | One in-scope, ALLOWED, unredacted, writer-domain file; selected plan prose (redacted) | Plan risks, open questions, `required_verification`, approval text, other files, absolute paths and credentials are excluded (tested). |
| Transport | Accepts exactly `httpx.MockTransport` in P1A | `type(transport) is httpx.MockTransport`. A subclass, a real transport, `None` or a client are refused before any read. This guards against **accidental** live use; it is not a sandbox (see §4.3). |
| Plaintext | `allow_insecure_http` for **every** provider, shipping `false` | Refused before the read. When acknowledged, announced as `NOT TLS-ENCRYPTED`. |
| Retries | Zero transport, one semantic attempt | `max_retries` forced to 0 on a private copy of the client config. Any failure is terminal. A structured-output server rejection gets no unstructured fallback. |
| Tokens | Unlimited by default | `max_output_tokens: null` sends no `max_tokens`. A positive value is sent verbatim. |
| Content provenance | `supervised-implementer-provenance.v1` beside the diff | Frozen and `extra="forbid"`; facts are `Literal`. The result validator cross-checks path, digests and outcome. `revalidate_supervised_implementer_result` re-validates from JSON at a consumption boundary. |
| Approval-surface prose | AIDO-fixed text naming candidate and model | No model-authored prose enters the diff artifact. |

## 3. Files

**New**

- `src/ai_dev_orchestrator/supervised_implementer/__init__.py`
- `src/ai_dev_orchestrator/supervised_implementer/identity.py`: role and
  candidate registry.
- `src/ai_dev_orchestrator/supervised_implementer/models.py`: errors, the
  output contract and strict parser, the notice, provenance and result.
- `src/ai_dev_orchestrator/supervised_implementer/request.py`: request builder.
- `src/ai_dev_orchestrator/supervised_implementer/implementer.py`: gates and
  the offline runner.
- `src/ai_dev_orchestrator/workspace/content_read.py`: the Phase 5D2 bounded
  read, extracted unchanged from `cli.py`.
- `tests/test_supervised_implementer.py`: 102 offline tests.
- This document, and the DEC-SUP proposal.

**Changed**

- `src/ai_dev_orchestrator/models.py`: new `SupervisedImplementerConfig`
  (strict, frozen, ships disabled) and the `ProjectConfig.supervised_implementer`
  field. Every existing config loads unchanged.
- `src/ai_dev_orchestrator/cli.py`: `l2-read-workspace-files` steps 8–12 now
  call the extracted reader. The refusal text, output and gate order are
  identical. Helper names stay as aliases.
- `tests/test_cli_l2_read_workspace_files.py`: two source-inspection tests now
  include the extracted reader in "the command's source". Their assertions are
  otherwise unchanged.
- `tests/test_workspace_canonical_path_guard.py`: the read-guard caller
  tripwire now expects `["cli.py", "content_read.py"]`. The 5D2 call moved, as
  the test's docstring now records. The supervised package never names the
  guard.
- `docs/AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md`: appended §8, the
  DEC-SUP amendment.

**Not changed: `CLAUDE.md`.** P1A was not authorized to modify it. DEC-SUP
item 8 was never decided (see §7), and P1A's own prompt forbade the edit. An
earlier draft of this phase did edit it; ALPHA-P1A-FU1 restored the file
exactly to HEAD. Its existing non-goal wording ("no model-backed implementer",
"nothing else may call a model" outside three gated commands) is therefore
**stale relative to this authorized offline supervised library**, and that
staleness is acknowledged. Updating `CLAUDE.md` requires a separate, explicit
operator authorization.

## 4. Adversarial review

### 4.1 Pre-implementation findings (from the DEC-SUP proposal)

| Finding | Resolution |
|---|---|
| F-1 model authorship hidden behind `engine: deterministic` | Separate provenance record. AIDO-fixed rationale and assumption naming SUP-D and the model in the diff artifact itself. |
| F-2 model prose in the approval surface | The reply schema is `content_text` only. All prose is AIDO-fixed. |
| F-3 saved packet origin is convention | In-process 5D2 read through the shipped reader. |
| F-4 full-file egress | One file; redacted, protected, out-of-scope and writer-domain-violating files are refused **before** any request is built. |
| F-5 plaintext only refused for the vLLM reviewer | Acknowledgement required for every provider. |
| F-6 `create` allowed by proposed-content | AIDO fixes `change_type: modify`. |
| F-7 truthiness | Strict, frozen config. `is True` and exact-`type` checks. `Literal` facts. |

### 4.2 Post-implementation findings (fixed, with regressions)

| # | Bypass constructed | Impact before the fix | Fix |
|---|---|---|---|
| R-1 | Reply drops the final newline, or changes line endings | 5E3 diffs over `splitlines()`, so the change is invisible in the diff while `post_image_sha256` covers the bytes. The proposal passed to H6, and the writer refused it **after** a human approved. A newline-only change hit an internal inconsistency error. | Before sending: refuse a file outside the writer's text domain. After the reply: prove reachability in memory with the writer's own `apply_strict_unified_diff` and rejoin. `post_image_unreachable` is the rejection. |
| R-2 | `announce` callback mutates the caller's `client_config.base_url` after the endpoint gate | The request could go to a host other than the one that was checked and announced, and the provenance would misreport it. | The client is built from a validated private copy before `announce`. |
| R-3 | Deeply nested JSON reply | `RecursionError` escaped the strict parser untyped | Caught as `output_invalid_json`. |
| R-4 | Reply with a lone-surrogate escape | An untyped `UnicodeEncodeError` from digest computation | Rejected by the output contract. |

Also exercised, with no defect found:

- consent given as `False`, `None`, `1`, `"yes"` or `"True"`;
- a live transport, a `MockTransport` subclass, `None` or a client (no
  filesystem touch);
- a post-load forged config block and a `model_construct` plan with a forged
  approval (refused at re-validation);
- a caller mutating its plan mid-run (no scope widening);
- out-of-scope, forbidden, protected, unlisted, traversal, absolute,
  backslash and case-variant targets;
- missing and redacted targets;
- an identity mismatch, and the read opt-in disabled;
- fenced, prose-wrapped, extra-key, wrong-type, duplicate-key, array, empty
  and NUL replies;
- `finish_reason` of `length`, `None` or `content_filter`;
- a substituted model id, and model content carrying a secret (refused by 5E3);
- HTTP 400/401/429/500, a timeout or a connect error, each with **exactly one**
  request even when the caller asked for 5 retries;
- an announcement failure, which sends nothing;
- tampered and `model_construct` results, and repeated invocations;
- the API key appearing in no record;
- no CLI command reaching the package.

### 4.3 Residual limitations (deferred, not P1A blockers)

- **No AIDO-owned wait deadline.** A mock cannot stall. A live pilot needs the
  RS1-FU2 pattern (one daemon worker plus AIDO's own monotonic deadline), with
  a stall treated as terminal.
- **No transport-level response-size bound.** `content_text` is capped at
  1,000,000 characters only after the whole body is read.
- **The reply's `model` field is weak evidence.** The shipped client falls back
  to the requested name when a server omits it. This is documented on the
  provenance field.
- **Provenance is not signed.** Like every AIDO artifact, a serialized record
  can be forged. It grants no authority, and the writer still pins digests
  against disk.
- **The in-process read reads every approved file** (the shipped 5D2
  behavior, bounded by its caps). Only the target is transmitted.
- **Redaction is a backstop.** An unredacted file is not proven secret-free.
- **The transport gate is not a sandbox.** The runner accepts exactly an
  `httpx.MockTransport` and rejects every other supplied transport type, which
  guards against accidental live use. But a `MockTransport` handler is
  arbitrary, trusted, caller-supplied Python code, and it could itself open a
  socket or forward the request anywhere. AIDO does not inspect or confine the
  handler, so the gate is no guarantee against a malicious or network-capable
  injected handler. What keeps P1A offline is that it has **no authorized live
  invocation entry point**: no CLI command reaches the package, and nothing in
  AIDO constructs a handler for it.

## 5. Acceptance criteria

| # | Criterion | Met by |
|---|---|---|
| 1 | Explicit candidate identity; no silent replacement | Registry and gate tests; frozen-registry AST test |
| 2 | No direct write authority | Source-inspection test; workspace snapshot unchanged; no approval in the result |
| 3 | Only approved bounded source enters the request | Request-content tests, the redaction refusal, the injection round trip |
| 4 | Existing consumption-boundary validation | `ProposedContentInput` and `WorkspaceContentPacket` validated; 5E3 unchanged |
| 5 | Diff generation reuses existing authority rules | `build_deterministic_diff_proposal` plus the writer's own applier |
| 6 | Missing human approval prevents writes | 5F0 parse refuses without the exact phrase; P1A never writes |
| 7 | Fail closed, no semantic retry or fallback | Transport-failure and malformed-reply tests, each with one request |
| 8 | Offline regression tests pass | Product `tests/`: 3594 passed. The one failure was the caller tripwire, updated deliberately and rerun green with the affected suites (381 passed). Offline CFG1: 3655 passed, 4 skipped, 16 Node/Pi tests deselected. Qualification suite: 2666 passed. Its 6 failures are pre-existing installed-Pi drift (global Pi 1.2.0 vs frozen 0.85.1), outside the repo and unrelated to this phase |
| 9 | Alpha-0 behavior intact | All existing `l2-read-workspace-files`, diff, writer, verifier and reviewer suites pass; no CLI surface change |
| 10 | No live transmission or real-workspace execution | The runner accepts exactly `MockTransport` by type; P1A has no authorized live entry point; tests use network-free handlers over synthetic `tmp_path` only |

## 6. Conditions for the first live Qwen 3.8 supervised pilot

These require a **separate authorization**:

1. Lift the `MockTransport`-only restriction **only** behind a new, explicit
   gate, and add the RS1-FU2-style AIDO-owned wait deadline (terminal stall)
   and a response-size bound.
2. Add a provider-isolated environment reader in the 5F2E-V1-FU1 shape. Read
   only the configured provider's names, with no endpoint in config and no
   real endpoint in code or docs.
3. Add one CLI command with its own consent flags and a non-suppressible
   stderr banner (the `SourceTransmissionNotice`), writing the diff proposal
   and the provenance record to files outside the workspace.
4. Use a dedicated, disposable clean clone of a low-risk repository: one file,
   `modify` only, an H2-approved plan, and an acknowledged plaintext transport
   when the endpoint is `http`.
5. Keep H6 exact-diff approval and the unchanged H7/H8/H9 gates, and end H10 in
   COMMIT or RESTORE.
6. State that the pilot qualifies nothing.

## 7. ALPHA-P1A-FU1 — governance and offline-claim corrections

The independent review of P1A returned **CHANGES REQUIRED** with two blockers
and no material defect in the supervised execution path. FU1 corrects the two
blockers and nothing else. No production behavior, API contract, transport
gate, qualification registry or hard bar changed.

| Blocker | Defect | Correction |
|---|---|---|
| B-1 | P1A modified `CLAUDE.md` without authorization, and policy §8 row 8 recorded a permission that was never given. Proposal §6 item 8 had no recommended option, so approving "the recommended answers" did not decide it. | `CLAUDE.md` restored exactly to HEAD (all four hunks were P1A's; nothing unrelated was lost). Policy §8 row 8 and the proposal's decision banner now record item 8 as **not authorized**, with the staleness acknowledged. §3 above no longer lists `CLAUDE.md` as changed. Every other DEC-SUP decision, and the autonomous C → D sequence, is unchanged. |
| B-2 | The `implementer.py` docstring said the offline restriction was "enforced mechanically"; the `SupervisedImplementerConfig` docstring said enabling it "cannot cause a real model request"; the package docstring and this document stated the transport gate without its limits; and the now-restored `CLAUDE.md` hunk said the library "cannot make a real model call". A `MockTransport` handler is arbitrary Python and can do network I/O. | Reworded to the precise claim: the runner accepts exactly `httpx.MockTransport` and rejects other transport types, as a guard against accidental live use; the gate is not a sandbox; and P1A has no authorized live invocation entry point (§4.3). |

**Nonblocking review findings (N-1, N-2, N-3) and the P1B backlog are recorded
for later work and are not addressed here.** They are not P1A blockers. One
framing point applies to any later work on them: removing a public export of
the request builder would not be a security boundary. The builder only formats
a request. Authority must stay enforced at the runner gate and at each
consumption boundary.
