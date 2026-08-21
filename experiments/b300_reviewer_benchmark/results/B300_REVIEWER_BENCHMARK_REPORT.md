# B300 Reviewer Benchmark

Controlled, read-only comparative benchmark of four restored B300 models as
candidates for AIDO's controlled reviewer role, run through AIDO's current
production `l2-review-approved-file-edit` path. Experiment only — no AIDO
production code, tests, or `projects/mis_project.yaml` was modified.

## 1. Setup

- **Sandbox workspace:** `C:\dev\aido_rs1_rt1_sandbox` (synthetic, git-tracked,
  single-purpose). Untouched otherwise; only ever holds the one seeded
  modification to `src/quota/limits.py`.
- **Command under test:** `ai-dev-orchestrator l2-review-approved-file-edit`
  (production CLI, unmodified) — runs AIDO's own Phase 5F2D verification
  internally, then, only on a `verified` outcome, calls the one
  project-configured reviewer model.
- **Provider:** `litellm` for all four models, through the operator's existing
  local proxy (`127.0.0.1:18080` → internal LiteLLM/B300). No `vllm` provider,
  no structured output, no CLI overrides.
- **Experiment configs:** four project-config YAML copies under
  `experiments/b300_reviewer_benchmark/configs/`, identical in every field
  except `controlled_review.model`. `workspace_path` points at the sandbox,
  never at a real project.
- **Approved artifact:** one `approved-diff-proposal.v2` JSON artifact under
  `experiments/b300_reviewer_benchmark/artifacts/`, shared byte-for-byte across
  all four runs (same diff, same approved-plan prose, same approval identity).
- **Verification command:** a synthetic Python script
  (`experiments/b300_reviewer_benchmark/scripts/verify_quota.py`, lives outside
  the sandbox workspace as required) that exercises `within_quota()` at
  `3`, `15`, `0` against `limit=10` — deliberately never at `value == limit` —
  and `remaining()` once. It passes (`4 passed`, exit 0) even though the
  seeded regression breaks the equality boundary. This is the intended
  verification gap.
- **Reviewer supervision:** RS1 defaults from the project's real config carried
  through unchanged — `attempt_timeout_seconds: 90`,
  `max_output_tokens: 2048`, `compact_retry_on_unusable_output: false` (left
  off because the production config has it off). Transport retries forced to
  zero, hard cap of two semantic requests.

## 2. Proof of a shared synthetic case

All four runs verified the identical git state before any model was
contacted:

```
target:                src/quota/limits.py
change_type:            modify
pre_image (git HEAD):   return value <= limit
post_image (worktree):  return value < limit
pre_image_sha256/post_image_sha256:  identical across all 4 artifact reads
head_object_id:         unchanged before and after every run
only dirty path:        src/quota/limits.py (unstaged modification)
verification outcome:   "verified" in all 4 runs, output "collected 4 items / 4 passed"
```

The sandbox was reset to exactly this state (stray `__pycache__` removed)
between every invocation. No file other than `src/quota/limits.py` was ever
dirty going into a run.

## 3. Per-model results

### nemotron-3-super

- **Exit code:** 4 (verification passed, reviewer stage failed)
- **Verification:** passed
- **Reviewer request issued:** yes — 1 semantic attempt
- **Terminal classification:** `review_output_budget_exhausted` — provider
  returned a length `finish_reason` with no valid review recovered; no
  packet was produced
- **Strict parse:** N/A (no completion to parse into a valid review)
- **Compact retry:** not authorized (project config has it off; also this is
  the standard "completed-but-unusable" case that *would* be retry-eligible
  if the flag were on — it was not enabled for any of the four runs, so all
  four were treated identically)
- **Wall time:** 13s
- **Verdict:** none — reviewer unavailable
- **Assessment:** rejected for this benchmark run on output-budget grounds
  under the shared 2048-token cap. Not evidence of a strict-format
  incompatibility (nothing was returned to parse) — evidence of running out
  of budget before completing a structured reply.

### minimax-m2.7-thinking

- **Exit code:** 0
- **Verification:** passed
- **Reviewer request issued:** yes — 1 semantic attempt, `finish_reason: stop`
- **Strict parse:** accepted first attempt
- **Verdict:** `changes_requested`
- **Seeded correctness regression caught:** **yes** — finding (severity
  `major`, category `correctness`) identifies that `value < limit` now
  rejects `value == limit`, directly contradicting the function's own
  docstring
- **Verification gap noted:** yes, in `human_notes` ("test coverage of the
  boundary case (value == limit) is not visible in the supplied context")
- **Findings:** 1 actionable, 0 noise
- **Usage:** 1959 prompt / 992 completion / 2951 total tokens
- **Latency:** 6.99s (attempt-level), 9s wall

### qwen3-coder-next

- **Exit code:** 0
- **Verification:** passed
- **Reviewer request issued:** yes — 1 semantic attempt, `finish_reason: stop`
- **Strict parse:** accepted first attempt
- **Verdict:** `approve`
- **Seeded correctness regression caught:** **no** — zero findings; the
  boundary change is mentioned only as a `residual_risk` line and explicitly
  *not* flagged as a blocker ("not flagged as a blocker since the change
  matches the approved intent")
- **Verification gap noted:** mentioned in `human_notes` but not connected to
  a concrete finding or a non-`approve` verdict
- **Findings:** 0 actionable
- **Usage:** 1962 prompt / 136 completion / 2098 total tokens
- **Latency:** 1.12s (attempt-level), 3s wall — by far the fastest and
  leanest response, but at the cost of the one thing this benchmark
  prioritizes most

### minimax-m2.7

- **Exit code:** 0
- **Verification:** passed
- **Reviewer request issued:** yes — 1 semantic attempt, `finish_reason: stop`
- **Strict parse:** accepted first attempt
- **Verdict:** `changes_requested`
- **Seeded correctness regression caught:** **yes** — finding (severity
  `blocker`, category `correctness`), the strongest-worded of the three valid
  reviews, states the code and docstring are in "direct conflict" and offers
  two concrete resolutions
- **Verification gap noted:** yes, in `human_notes` ("tests may not be
  validating the boundary condition against the documented semantics")
- **Findings:** 1 actionable, 0 noise
- **Usage:** 1959 prompt / 794 completion / 2753 total tokens
- **Latency:** 5.59s (attempt-level), 7s wall

## 4. Comparison table

| | nemotron-3-super | minimax-m2.7-thinking | qwen3-coder-next | minimax-m2.7 |
|---|---|---|---|---|
| Valid strict AIDO JSON (1st attempt) | ✗ (budget exhausted) | ✓ | ✓ | ✓ |
| Final valid AIDO review | ✗ | ✓ | ✓ | ✓ |
| Boundary regression caught | — | ✓ (major) | ✗ | ✓ (blocker) |
| Verification gap identified | — | ✓ (notes) | partial (notes only) | ✓ (notes) |
| Verdict | none (unavailable) | changes_requested | **approve** | changes_requested |
| Actionable findings | — | 1 | 0 | 1 |
| False-positive / noise findings | — | 0 | 0 | 0 |
| Concise vs. checklist behavior | — | concise, targeted | concise, but under-caught | concise, targeted |
| Semantic attempts used | 1 of 2 | 1 of 2 | 1 of 2 | 1 of 2 |
| Terminal classification | review_output_budget_exhausted | valid_review | valid_review | valid_review |
| Attempt latency | 13s (stalled-out) | 6.99s | 1.12s | 5.59s |
| Total tokens | — (no usable completion) | 2951 | 2098 | 2753 |

## 5. Recommendation

**Priority order applied:** (1) catches the seeded regression, (2) produces
valid structured output, (3) low-noise actionable findings, (4) identifies the
verification gap, (5) runtime efficiency — in that order, so qwen3-coder-next's
speed advantage does not outweigh its missed regression.

- **Primary B300 reviewer: `minimax-m2.7`.** Valid output on the first
  attempt, correctly flagged the seeded regression at `blocker` severity with
  a precise, actionable message, zero noise, and noted the verification gap —
  all at moderate latency (5.6s) and token cost.
- **Secondary / manual alternate reviewer: `minimax-m2.7-thinking`.**
  Materially equivalent semantic quality to the primary (same regression
  caught, `major` rather than `blocker`, same zero-noise finding, same
  verification-gap note), at somewhat higher latency and token cost — a
  reasonable fallback or second opinion, not a reason to prefer it over the
  primary.
- **Not recommended for reviewer use (this configuration):**
  - **`qwen3-coder-next`** — fastest and cheapest by a wide margin, but
    **approved a change that should have been blocked**: it saw the seeded
    boundary regression and explicitly declined to flag it. A reviewer that
    approves a correctness regression is the single failure mode this role
    exists to prevent, and no amount of speed offsets it.
  - **`nemotron-3-super`** — produced no usable review under the shared
    2048-token output cap; classified `review_output_budget_exhausted`, not a
    format-compatibility failure. It may be viable with a larger
    `max_output_tokens` for this model specifically, but that is a
    per-project config decision, not something this benchmark authorizes or
    recommends changing globally.

No automatic fallback, failover, or consensus between these models is
recommended or implemented — none of that is authorized for AIDO, and this
benchmark did not build any.

## 6. Does the LiteLLM reviewer path expose a systematic strict-output problem?

**No, not systematically, based on this evidence.** Three of four models
(`minimax-m2.7-thinking`, `qwen3-coder-next`, `minimax-m2.7`) returned strict,
schema-valid JSON on the first attempt with `finish_reason: stop`, with no
structured-output constraint (`vllm_structured_output` is vLLM-only and was
off / inapplicable for all four `litellm` runs). The one failure
(`nemotron-3-super`) was an output-budget exhaustion, not a malformed
envelope — the earlier V2 finding (markdown-fenced JSON breaking the strict
parser) was **not** reproduced by any of these four runs. This sample is too
small (one run per model, no repeated trials) to rule out an intermittent
envelope problem for any individual model, but it gives no evidence of a
systematic LiteLLM-path format incompatibility.

## 7. Is any AIDO product/runtime change justified by this evidence?

Nothing is implemented here — this section is observational only, as scoped.

- The `nemotron-3-super` result is a plausible, narrow signal that this
  model's default verbosity may not fit comfortably under a 2048-token
  reviewer output cap for reviews of this size. That is evidence a human
  could weigh when *separately* deciding per-project
  `controlled_review.max_output_tokens` — nothing here recommends changing
  any default, and the task's token-budget policy note applies: AIDO's
  overall token budget stays unlimited by default, and this benchmark neither
  reinterprets nor proposes reinterpreting `max_output_tokens`,
  `reviewer_supervision`, or transport-retry fields as a global budget.
  This is a single data point, not a trend.
- No change to the strict parser, the reviewer transport, RS1 supervision, or
  the CLI surface is justified by four single-shot runs. That would need
  repeated trials per model at minimum.

## 8. Repository state

```
$ git diff --check
(exit 0, no output)

$ git status --short
?? experiments/
```

The only repository change is the new, entirely untracked
`experiments/b300_reviewer_benchmark/` directory (this report, the shared
approved-diff artifact, the synthetic verification script, the four
experiment-only project configs, and the four raw result JSON files). Nothing
was staged, committed, or pushed. `projects/mis_project.yaml` was not opened
for writing at any point.

Sandbox (`C:\dev\aido_rs1_rt1_sandbox`) status at the end of the benchmark:

```
 M src/quota/limits.py
```

— exactly the one pre-existing seeded change, unchanged by any of the four
runs.

## Experiment-only artifacts retained (not production, not committed)

```
experiments/b300_reviewer_benchmark/
  build_artifacts.py                  generator script (regenerates the below)
  scripts/verify_quota.py             synthetic verification program
  artifacts/approved-diff-proposal.json   shared approved-diff artifact
  configs/mis_b300_<model>.yaml       4 experiment-only project configs
  results/<model>.json                4 raw command stdout captures
  results/<model>.json.stderr         4 raw command stderr captures
  results/<model>.meta                exit code + wall time per run
  results/B300_REVIEWER_BENCHMARK_REPORT.md   this report
```

Retained as evidence per the task instructions, under an obviously
non-production path. Recommend deleting `experiments/` once this report has
been reviewed, or leaving it in place — it is inert, untracked, and contains
no secrets (all reviewer endpoint/credential values were redacted at the
source; only `endpoint_host` and `endpoint_scheme`, never the base URL or API
key, appear anywhere in the captured output).
