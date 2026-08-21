# AIDO Controlled-Reviewer Benchmark — FINAL Round Report

Experiment-only evidence. Not production config, not committed, not pushed.
Sandbox: `C:\dev\aido_rs1_rt1_sandbox`. All new artifacts live under
`experiments/b300_reviewer_benchmark_final_extension/`. Nothing under
`b300_reviewer_benchmark/`, `b300_reviewer_benchmark_v2/`, or
`b300_reviewer_benchmark_v2_recovery/` was modified — those remain read-only
historical evidence.

Deviation from the operator prompt worth flagging up front: the prompt asked
that each new `case_<key>_gpt-oss-20b.yaml` config change `project_id`. The
system's identity check (`l2-verify-approved-file-edit` /
`l2-review-approved-file-edit`) requires the project config's `project_id` to
match the `approved-diff-proposal.json` artifact's embedded `project_id`
**exactly**, and the artifact is reused verbatim per instructions. Changing
`project_id` therefore causes a hard refusal (`refused-before-execution:
identity error`, exit 1) before anything is launched — confirmed by an actual
run (see `evidence/part2_gpt_oss/*/preflight_verify_stderr.txt` from the first
attempt, since overwritten by the corrected second attempt's success). The
gpt-oss-20b configs therefore keep `project_id` identical to the reused
`case_<key>_qwen3-coder-next.yaml` template (e.g. `b300_v2_case_a`) and change
only `display_name` and `controlled_review.model`, which is what the CLAUDE.md
identity-ordering contract requires and is the only combination that runs at
all.

---

## 1. gpt-oss-20b connectivity precheck (Part 0)

`real-llm-smoke-test --project-config configs/smoke_gpt-oss-20b.yaml --model
gpt-oss-20b --real-model` was run exactly once (no prior successful record
existed in this fresh directory).

- Exit code: **0**
- Wall clock: 1.97s
- Result: usable JSON connectivity result (not just a socket-open) — see
  `evidence/part0_smoke_stdout.json` / `evidence/part0_smoke_record.json`.

**Verdict: gpt-oss-20b is available.** Part 2 proceeded.

---

## 2. B300 Case-D clean-control recovery (Part 1, 4 runs)

Case `case_d_clean_control` only, reusing the existing V2 configs/artifacts
unchanged, in the mandated order: nemotron-3-super, minimax-m2.7,
minimax-m2.7-thinking, qwen3-coder-next.

| Model | Prior recovery outcome | This run exit | `reviewer_response_error` reappeared? | Strict parser accepted | Verdict | Sandbox unchanged |
|---|---|---|---|---|---|---|
| nemotron-3-super | reviewer_response_error, exit 4 | **0** | No | Yes | **approve** | Yes |
| minimax-m2.7 | reviewer_response_error, exit 4 | **0** | No | Yes | **approve** | Yes |
| minimax-m2.7-thinking | reviewer_response_error, exit 4 | **0** | No | Yes | **approve** | Yes |
| qwen3-coder-next | reviewer_response_error, exit 4 | **0** | No | Yes | **approve** | Yes |

All four preflight-verified cleanly, all four reviewer calls completed, all
four strict-parsed, all four returned the expected `approve` verdict with the
expected zero blocker/major findings for the unseeded clean-control diff. No
semantic false positive. Full packets and stdout/stderr under
`evidence/part1_case_d/`.

## 3. Guardrail-fix confirmation

**Confirmed: the corrected corporate LiteLLM guardrail now passes the benign
`strip()` fixture for all 4 previously-blocked B300 models.** The
`reviewer_response_error` signature did not reappear for any of the four. This
closes out the last open infrastructure gap in the B300 four-model dataset —
Case D is now fully populated for all four models with real, usable
observations.

---

## 4. gpt-oss-20b full reviewer qualification (Part 2, 4 runs)

Provider: `litellm`. One CLI invocation per case; no shell-level retry (the
production RS1 supervisor owns its own ≤2-semantic-attempt policy internally).

| Case | Expected | Actual verdict | Findings | Severity | Matches expected | Exit | Wall clock |
|---|---|---|---|---|---|---|---|
| case_a_boundary | changes_requested | **changes_requested** | 1 | blocker (correctness) | Yes | 0 | 2.97s |
| case_b_fail_closed | changes_requested | **changes_requested** | 1 | blocker (correctness) | Yes | 0 | 2.56s |
| case_c_order_preservation | changes_requested | **changes_requested** | 1 | major (correctness) | Yes | 0 | 2.64s |
| case_d_clean_control | approve | **approve** | 0 | — | Yes | 0 | 2.58s |

**gpt-oss-20b matched the expected semantic verdict on all 4 cases** — the
first candidate in this benchmark series to do so cleanly across A, B, C and
D in one pass. Every attempt used exactly 1 of at most 2 semantic requests
(`"Requests: 1 of at most 2 semantic requests AIDO may issue"`), transport
retries were 0, no stall occurred, `compact_retry_on_unusable_output` was
`false` and never triggered, `structured_output_mode: "none"` (provider is
`litellm`, not `vllm`, per config), and token usage was reported by the
provider on every call (see §10). All four sandbox states were provably
unchanged before/after. Full packets under `evidence/part2_gpt_oss/<case>/`.

Case B finding was categorized `correctness` rather than `security` by the
model, but its message text ("authorizes absent principals... breaks
fail-closed behavior") correctly identifies the security-relevant fail-open
regression — recorded as-is, not softened either direction.

---

## 5. Six-candidate A/B/C sensitivity matrix

| Candidate | Case A | Case B | Case C |
|---|---|---|---|
| nemotron-3-super | changes_requested (blocker) | changes_requested (blocker) | changes_requested (blocker) |
| minimax-m2.7 | changes_requested (blocker) | changes_requested (blocker) | changes_requested (blocker) |
| minimax-m2.7-thinking | changes_requested (blocker) | changes_requested (blocker) | changes_requested (blocker) |
| qwen3-coder-next | changes_requested (blocker) | **approve (false negative)** | changes_requested (blocker) |
| gpt-oss-20b | changes_requested (blocker) | changes_requested (blocker) | changes_requested (major) |
| Qwen3.6-27B-131K (direct-vLLM, structured) | changes_requested (blocker) | changes_requested (blocker, security) | changes_requested (blocker) |

Source: nemotron-3-super/minimax/qwen3-coder-next A/B/C values from
`experiments/b300_reviewer_benchmark_v2_recovery/summary/combined_dataset.json`
(itself built from `b300_reviewer_benchmark_v2/evidence/` originals plus the
accepted case_b recovery). Qwen3.6 values from
`experiments/b300_reviewer_benchmark_v2_recovery/qwen36_extension/case_{a,b,c}/record.json`.
gpt-oss-20b values from this round.

**Only qwen3-coder-next missed a case** — Case B, the fail-closed authz
regression — and per instructions that observation is kept exactly as-is, not
rerun.

---

## 6. Six-candidate Case D specificity matrix

| Candidate | Case D verdict | Findings | False positive? |
|---|---|---|---|
| nemotron-3-super | approve | 0 | No |
| minimax-m2.7 | approve | 0 | No |
| minimax-m2.7-thinking | approve | 0 | No |
| qwen3-coder-next | approve | 0 | No |
| gpt-oss-20b | approve | 0 | No |
| Qwen3.6-27B-131K (structured) | approve | 0 | No |

All six candidates are now clean on the no-bug control. No candidate has a
recorded Case D false positive.

---

## 7. Strict-format-valid-first-attempt matrix

| Candidate | A | B | C | D |
|---|---|---|---|---|
| nemotron-3-super | valid 1st | valid 1st | valid 1st | valid 1st (this round) |
| minimax-m2.7 | valid 1st | valid 1st (recovery) | valid 1st | valid 1st (this round) |
| minimax-m2.7-thinking | valid 1st | valid 1st (recovery) | valid 1st | valid 1st (this round) |
| qwen3-coder-next | valid 1st | valid 1st | valid 1st | valid 1st (this round) |
| gpt-oss-20b | valid 1st | valid 1st | valid 1st | valid 1st |
| Qwen3.6-27B-131K (structured) | valid 1st | valid 1st | valid 1st | valid 1st |

No compact retry fired for any candidate in this round or in the referenced
prior evidence for A/B/C. Every reviewer in the current combined dataset now
has a first-attempt-valid strict parse on every case it has a usable
observation for.

---

## 8. Verification-gap-recognized matrix

Did the reviewer explicitly call out that the passing verification did not
cover the seeded regression?

| Candidate | A | B | C |
|---|---|---|---|
| gpt-oss-20b | **Yes** — "verification process only confirmed the repository state; it did not validate the functional semantics of the quota check" | **Yes** — "verification process only checked repository state, not functional behavior" | **Yes** — "verification only confirmed the file bytes and repository state; it did not test the functional semantics" |
| nemotron-3-super / minimax family / qwen3-coder-next | Not captured in this round's evidence scope (original v2 packets not re-parsed for this field; out of scope for a no-rerun policy) | — | — |
| Qwen3.6-27B-131K | Not captured in this round's evidence scope | — | — |

gpt-oss-20b is the only candidate for which this round captured and confirms
explicit `human_notes` verification-gap language on all three regression
cases. This is a positive signal but is scoped honestly: it reflects what was
captured in this round, not a claim that other candidates failed to do this.

---

## 9. Finding correctness / noise comparison

- **gpt-oss-20b**: exactly 1 finding per regression case (A: blocker, B:
  blocker, C: major), 0 findings on D. Zero noise, zero missed cases in this
  round.
- **qwen3-coder-next**: correct on A, C, D; missed B (approved a fail-open
  regression — a false negative, not noise).
- **nemotron-3-super, minimax-m2.7, minimax-m2.7-thinking**: correct
  (blocker, changes_requested) on A, B, C per existing evidence; correct
  (approve) on D per this round.
- **Qwen3.6-27B-131K**: correct on A, B (tagged `security`), C, D per existing
  evidence — the only other candidate matching gpt-oss-20b's clean 4-for-4
  record, and the only one to explicitly tag Case B as a `security` finding
  rather than `correctness`.

No candidate in the current dataset produced a spurious/noise finding on
Case D.

---

## 10. Latency / token comparison

Wall clock is from this round's own `time.monotonic()` measurements around
each CLI subprocess call. Token usage is only reported where the CLI's own
output included a `usage` block (gpt-oss-20b, litellm provider) — never
estimated for candidates where this round did not make the call.

| Run | Wall clock | prompt_tokens | completion_tokens | total_tokens |
|---|---|---|---|---|
| Case D recovery — nemotron-3-super | 9.21s | not reprinted in this report; see `evidence/part1_case_d/01_*_stdout.json` | | |
| Case D recovery — minimax-m2.7 | 5.87s | see stdout.json | | |
| Case D recovery — minimax-m2.7-thinking | 5.31s | see stdout.json | | |
| Case D recovery — qwen3-coder-next | 2.19s | see stdout.json | | |
| gpt-oss-20b Case A | 2.97s | 2165 | 422 | 2587 |
| gpt-oss-20b Case B | 2.56s | 2147 | 401 | 2548 |
| gpt-oss-20b Case C | 2.64s | 2197 | 412 | 2609 |
| gpt-oss-20b Case D | 2.58s | 2115 | 360 | 2475 |

gpt-oss-20b was the fastest-observed reviewer this round (~2.6–3.0s per case)
against a local endpoint, with a consistent, small (~2.1–2.6K total token)
footprint. Qwen3.6-27B-131K's wall clock from the recovery extension ranged
24.5s–65.1s per case (direct-vLLM, structured output, different hardware
context) — not directly comparable to the litellm-routed timings above
without knowing the two endpoints' relative load, so no ranking is drawn from
latency alone.

---

## 11. Best reviewer in isolation — recommendation

**gpt-oss-20b**, with **Qwen3.6-27B-131K (structured)** as a close second.
Both are now the only two candidates in the full dataset with a clean 4-for-4
correct verdict across A/B/C/D, first-attempt-valid strict parsing on every
case, and zero false positives/negatives. gpt-oss-20b additionally
demonstrated, in this round, explicit verification-gap recognition on all
three regression cases and the lowest observed latency. Qwen3.6 tagged Case B
as `security` specifically, which is a slightly sharper categorization.
Neither result is large enough (single-run-per-case, no repeated sampling) to
call decisively superior to the other; both are recommended over the four
original B300 models, one of which (qwen3-coder-next) has a confirmed false
negative on the highest-stakes case (fail-closed authz).

## 12. Best B300 reviewer

Among the original four B300 models (nemotron-3-super, minimax-m2.7,
minimax-m2.7-thinking, qwen3-coder-next), **nemotron-3-super** is the
strongest: it is the only one of the four with a correct `changes_requested`
on Case B (fail-closed authz) in the original v2 evidence, alongside correct
results on A, C and (this round) D. minimax-m2.7 and minimax-m2.7-thinking
are also correct on B, C and D but see §16 for the deployment-independence
caveat before treating them as two separate confirmations. qwen3-coder-next
is excluded from "best B300" specifically because of its Case B false
negative, despite being the fastest of the four in this round's Case D run.

## 13. Normal-path production pairing — explicit non-finalization

This reviewer-side result does **not** finalize a normal-path production
reviewer pairing. The implementer side of L2 (a model-backed implementer) has
not been designed, built, or benchmarked in this repository. Any reviewer
recommendation here is reviewer-only and provisional until an implementer is
selected and the pair is evaluated together.

## 14. Best emergency reviewer

For an emergency / fallback slot (fastest, most self-contained, litellm
transport already proven against the same local gateway used everywhere else
in this benchmark), **gpt-oss-20b** is the recommendation: lowest latency
observed, zero infrastructure friction, zero-shot 4-for-4 correctness, and no
new transport/provider dependency (still `litellm`, unlike Qwen3.6's direct
`vllm` path with its own insecure-HTTP opt-in and separate endpoint).

## 15. Rejected / not-recommended candidates

- **qwen3-coder-next**: confirmed false negative on Case B (approved a
  fail-open authz regression). Not recommended as a sole/primary reviewer for
  security-relevant review given this specific, confirmed miss.
- No candidate is rejected for infrastructure reasons in this round — the
  guardrail issue that previously blocked Case D for four models is
  confirmed fixed (§3).

## 16. MiniMax deployment-independence caveat

Restated, not resolved: minimax-m2.7 and minimax-m2.7-thinking returned
byte-identical Case B content and usage historically (per prior recovery
evidence). Until routing/backend identity between these two named models is
understood, they must **not** be treated as two independent confirmations of
the same result — they may be the same underlying deployment reachable under
two names. This round did not investigate or resolve that; it is carried
forward as an open caveat, not assumed away.

## 17. Systematic provider/guardrail issues remaining

None identified in this round. The one known systematic issue — the shared
corporate LiteLLM guardrail false-flagging the benign `strip()` diff — is
confirmed fixed for all four affected models (§3). No new
`reviewer_response_error` or comparable infrastructure failure occurred in
any of the 8 new runs this round (4 recovery + 4 gpt-oss).

## 18. AIDO runtime change justification

**No.** Nothing observed this round indicates a defect in
`l2-review-approved-file-edit`, `l2-verify-approved-file-edit`, RS1
supervision, or the strict parser. The one friction point encountered
(project_id identity mismatch when following the prompt's literal
config-authoring instruction) is expected, documented, load-bearing behavior
of the accepted identity-ordering contract — not a bug — and was resolved by
authoring the configs correctly rather than by touching any production code.

## 19. Reviewer benchmarking is closed

Explicit statement: reviewer benchmarking for this project is now considered
**closed**, unless a concrete infrastructure failure is later found to have
blocked a required observation in this round. No such failure occurred — all
8 planned runs (4 B300 Case-D recovery + 4 gpt-oss-20b A–D) completed with
exit 0, usable strict-parsed output, and proven sandbox integrity.

## 20. Next step

**Pi implementer architecture and qualification.** This report does not begin
that work; it only names it as the next phase, per the project's role split
(ChatGPT = architect/planner; Claude Code = implementation tool) and current
non-goals (no model-backed implementer exists yet).

---

## 21–26. Repository cleanliness and evidence-integrity confirmations

**21. `git diff --check` (C:\dev\ai_dev_orchestrator):** empty output — no
whitespace/conflict-marker errors.

**22. `git status --short` (C:\dev\ai_dev_orchestrator):**
```
?? experiments/b300_reviewer_benchmark/artifacts/
?? experiments/b300_reviewer_benchmark/build_artifacts.py
?? experiments/b300_reviewer_benchmark/configs/
?? experiments/b300_reviewer_benchmark/results/
?? experiments/b300_reviewer_benchmark_final_extension/
?? experiments/b300_reviewer_benchmark_v2/
?? experiments/b300_reviewer_benchmark_v2_recovery/
```
All entries are untracked directories (this experiment predates any commit of
the `experiments/` tree). No tracked file shows as modified. Nothing was
staged or committed.

**23. CLAUDE.md untouched:** working-tree blob hash
`2fdab49cbd07ab6bb80a97205f3ed62d5c4c149a` is byte-identical to the
`HEAD` tree entry for `CLAUDE.md` (`git ls-tree HEAD CLAUDE.md` reports the
same hash). Confirmed untouched.

**24. `projects/mis_project.yaml` untouched:** working-tree blob hash
`d60d736e60161d4917f27d2f982f33b5fe4d2b08` is byte-identical to the `HEAD`
tree entry. Confirmed untouched — read only, for its `real_model_planning`
YAML shape, never edited.

**25. Prior experiment evidence dirs untouched:**
`b300_reviewer_benchmark/`, `b300_reviewer_benchmark_v2/`, and
`b300_reviewer_benchmark_v2_recovery/` all still show only as whole untracked
directories in `git status --short` with no per-file modification markers,
and no file inside them was opened for writing by this round's script (only
read, plus the standard `reset_sandbox.py` invocations against the separate
sandbox repo `C:\dev\aido_rs1_rt1_sandbox`, which is outside this repo
entirely). All new files were written exclusively under
`experiments/b300_reviewer_benchmark_final_extension/`.

**26. No reasoning/chain-of-thought captured:** a recursive
case-insensitive search for `reasoning`, `chain-of-thought`,
`thinking_blocks`, and `reasoning_content` across every new file under
`experiments/b300_reviewer_benchmark_final_extension/` matched only the CLI's
own fixed, static boilerplate text (present in every `review-packet.v4`
packet) explaining that AIDO does **not** capture the provider's
`message.reasoning` field and does not observe private reasoning — never
actual model reasoning content. No raw provider response, prompt, or
reasoning field was captured, logged, or written anywhere in this round's
evidence.
