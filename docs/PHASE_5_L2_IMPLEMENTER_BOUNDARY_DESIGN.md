# Phase 5A — L1-to-L2 Implementer Boundary (Design Review Only)

> ## CURRENT STATUS (2026-08-13) — read this first
>
> This document began as a Phase 5A design review and has accumulated the
> design history of every Phase 5 sub-phase since. **The sections below describe
> what was true when each phase shipped**, and several of them say things that
> are no longer current. The current status is:
>
> - **Phase 5F2C is DONE and is the first controlled single-file workspace
>   write** (§28, corrected by §28.13). One command,
>   `l2-apply-approved-file-edit`, applies one approved modification to one
>   tracked UTF-8 file in one clean Windows Git repository. **Statements
>   elsewhere in this document that "nothing edits a target file" or that
>   "5F2F remains the first controlled workspace write" are stale and are
>   preserved only as history.**
> - **Phase 5F2C-FU1 is DONE** (§28.13): it corrected the unsupported
>   `ReplaceFileW` flag, the unsafe post-replacement cleanup, the Git
>   filter-execution escape, ambient executable resolution, an overstated
>   output bound, and a misleading `files_created: false` report field.
> - **Phase 5F2D is DONE and is the first controlled verification execution**
>   (§29). One command, `l2-verify-approved-file-edit`, executes exactly one
>   project-configured verification process, once, bound on both sides to one
>   already-applied approved modification. **It is the first separately
>   authorized capability here to execute repository-controlled code**, so
>   statements elsewhere in this document that "no command execution exists",
>   that "nothing runs a project's own checks", or that §7's command-execution
>   policy is entirely unimplemented are **stale** and preserved only as history.
>   **Controlled invocation is not sandboxed execution**, and the result report
>   says so.
> - **Phase 5F2D-FU1 is DONE** (§29.13): it corrected a wall-clock bound that was
>   not actually a bound (a descendant holding the inherited output pipe kept
>   AIDO's reader blocked long past the deadline), pinned the HEAD object id
>   across the run, scoped every AIDO-owned negative capability claim with an
>   `orchestrator_` prefix, rewrote `next_step` to stop making unprovable global
>   claims, and narrowed the environment-forwarding claim to what is proved.
> - **Phase 5F2D-FU2 is DONE** (§29.14): it corrected an output cap that was not
>   enforced when it was passed (a fixed 64 KiB buffered read could sit waiting
>   long after the cap had been exceeded), made the configured-timeout versus
>   direct-child-reap-grace contract exact, and corrected the claim that the
>   abandoned reader's lifetime was bounded. **No process-tree management was
>   added.**
> - **Phase 5F2E is DONE and is the first controlled reviewer integration**
>   (§30). One command, `l2-review-approved-file-edit`, runs the accepted 5F2D
>   verification itself and — only on a `verified` outcome — sends one approved
>   unified diff, selected approved-plan prose, and the redacted verification
>   output to one project-configured reviewer model, then prints one review
>   packet. **It is the first runtime capability here that deliberately sends
>   source-derived code to a model**, so statements elsewhere in this document
>   that "no model receives source", that "no reviewer exists", or that §9's
>   model-usage policy is entirely unimplemented are **stale** and preserved only
>   as history. The verdict is **advisory** and ends at a human.
> - **Phase 5F2E-RS1 is DONE** (§31), **as corrected by 5F2E-RS1-FU1** (§31.16).
>   The controlled reviewer forces its transport `max_retries` to **0**, so one
>   semantic attempt is exactly one HTTP/model request, and the supervisor — not
>   the transport — owns a hard maximum of **two** semantic requests AIDO may
>   issue. The output artifact is now **`review-packet.v2`**, so statements in
>   §30 that "exactly one semantic reviewer request" is made and that the packet
>   is `review-packet.v1` are **superseded** and preserved only as history.
>   **This is observable resource supervision, not agent-progress supervision**:
>   no streaming, no reasoning inspection, no tool/file/test counters, and no
>   claim that a backend stopped inference.
> - **FU2 (§31.17) established the wait bound itself.** httpx's timeout is a
>   network-operation/inactivity timeout, not an absolute deadline around
>   `client.chat()`, so a busy peer could outlive it. AIDO now runs each attempt's
>   single client call on **one daemon worker** and waits to its **own monotonic
>   deadline**; when that deadline wins the worker is **abandoned, not stopped**.
>   `attempt_timeout_seconds` is now a real AIDO wait bound. No executor, pool,
>   join, process, asyncio, cancellation request, or thread-kill was added.
> - **FU1 (§31.16) made a stall TERMINAL.** RS1's draft retried after a client
>   timeout, which contradicted its own correct statement that a timeout proves
>   nothing about the backend — the model may still be generating, so a second
>   request could give it two concurrent inference jobs. The compact retry is now
>   limited to a **completed but unusable** response, the opt-in is
>   `compact_retry_on_unusable_output` (the draft `compact_retry_on_stall` is
>   **rejected**, not aliased), and the scope claim is exact: **RS1 bounds AIDO's
>   request issuance and wait budget, NOT backend inference lifetime or GPU
>   occupancy.** Any text anywhere claiming "the reviewer runtime/resource
>   envelope is bounded" is stale.
> - **Phase 5F2E-V1 is DONE** (§32), **as corrected by 5F2E-V1-FU1** (§32.11):
>   the **direct vLLM reviewer provider**.
>   `controlled_review.provider` now accepts exactly `"litellm"` or `"vllm"`,
>   matched exactly and case-sensitively, with the vLLM endpoint coming from
>   `AIDO_VLLM_BASE_URL` and an optional `AIDO_VLLM_API_KEY`, and the model still
>   coming only from `controlled_review.model`. LiteLLM remains supported;
>   direct vLLM is an **additional** option, not a replacement. Plaintext HTTP is
>   refused for vLLM unless the project sets `vllm_allow_insecure_http`, which is
>   an **acknowledgement, never a security claim**. The output artifact is now
>   **`review-packet.v3`**, so statements in §30 and §31 that the packet is
>   `review-packet.v1`/`v2` are **superseded** and preserved only as history —
>   though `v1` and `v2` keep their original LiteLLM-only meanings and must never
>   be reinterpreted as possibly-vLLM. **Every accepted RS1 semantic is
>   unchanged**, and V1 added no command, flag, role, loop, fallback, second
>   reviewer, fixer, implementer, cancellation, or provider framework.
> - **FU1 (§32.11) made the provider-specific environment claim true.** V1's
>   reader snapshotted **both** provider families from the process environment and
>   discarded the unconfigured one afterwards — and reading a credential then
>   dropping it is still reading it. The reader is now handed the provider and
>   resolves it to an exact name tuple **before** touching any environment, so a
>   vLLM review never reads an `AIDO_LITELLM_*` value and a LiteLLM review never
>   reads an `AIDO_VLLM_*` value. The union `REVIEWER_ENV_NAMES` constant and the
>   narrow-afterwards helper `select_reviewer_env` were **removed**, not renamed.
>   FU1 also made the CLI's reviewer-environment failure category
>   provider-neutral and corrected stale `v2`/LiteLLM-only prose in live
>   docstrings and examples. **No accepted V1 or RS1 behavior was reopened.**
> - **Phase 5F2E-V2 is DONE** (§33): **structured vLLM reviewer output.** A
>   controlled real-model trial returned HTTP 200, `finish_reason=stop`, and a
>   review that **correctly identified a seeded semantic bug** — wrapped in a
>   ```json fence, which the strict parser rejected. The identical prompt with a
>   JSON-Schema `response_format` produced one bare JSON object the *unmodified*
>   parser accepted. **The reasoning was never the failure; the envelope was**,
>   so V2 adds one **generation constraint** and changes the parser not at all.
>   `controlled_review.vllm_structured_output` (vLLM only, ships `false`) sends
>   the `ModelReviewResult` schema — **generated**, never hand-maintained — on
>   **both** possible semantic requests. A server that rejects the schema is a
>   terminal reviewer-stage failure: there is **no structured → unstructured
>   fallback**. The output artifact is now **`review-packet.v4`**, so statements
>   in §30–§32 that the packet is `review-packet.v1`/`v2`/`v3` are **superseded**
>   and preserved only as history — and `v1`, `v2` and `v3` all keep their
>   original meanings, none of which record structured-generation provenance.
>   **Every accepted RS1 and V1 semantic is unchanged**, the provider's separate
>   `message.reasoning` field is deliberately **not** captured, and no command,
>   flag, role, loop, fallback, second reviewer, fixer, implementer, or
>   cancellation was added.
> - **Operator token policy corrected: AIDO imposes NO model output-token
>   ceiling by default.** Real deployment evidence exposed the defect — a reviewer
>   benchmark inherited the shipped `controlled_review.max_output_tokens: 2048`,
>   the model completed its request, the provider reported a length finish
>   condition, AIDO classified it `review_output_budget_exhausted`, and no packet
>   was produced under a ceiling the operator never intended. The field is now
>   `int | None`, defaulting to **`None`**, and "unlimited" means exactly one
>   thing on the wire: **no OpenAI-compatible `max_tokens` field is sent** — never
>   a substituted large number, a context size, or a per-model guess. A positive
>   integer remains an explicit operator-requested cap, sent verbatim on **both**
>   possible semantic attempts, and the artifact-only ceiling `le=32_000` was
>   removed as an AIDO policy artifact expressing no provider-independent truth.
>   Provenance is truthful: `requested_max_output_tokens` is **`null`** exactly
>   when AIDO requested no cap, never `0`, `-1`, or `"unlimited"`. The
>   classification token `review_output_budget_exhausted` is retained for
>   artifact compatibility, but all human-facing wording now distinguishes a
>   provider-native output limit from an AIDO-requested one, and never claims to
>   know which native limit was reached. The dormant `AIRoleConfig.max_tokens`
>   default was corrected to `None` for the same reason — **`ai_roles` remains
>   unwired**. **`review-packet.v4` was NOT bumped**: an existing field merely
>   gained `null`, no archived packet becomes ambiguous, and every archived
>   integer still means exactly what it always meant. **Every accepted RS1, V1 and
>   V2 semantic is unchanged**, and the real smoke test's deliberate
>   `_REAL_SMOKE_MAX_TOKENS = 512` connectivity probe is untouched.
> - **The first controlled write → verify → supervised review → human path now
>   exists.**
> - **L2 as originally defined is still NOT complete.** There is no model-backed
>   implementer, no automatic fixer, no local branch creation, no local commit, no
>   push, no PR, and no generalized writer.
> - The **old 5F2C–5F2F roadmap in §26.12 is superseded** by §27; §26.12 is kept
>   as history and marked as such. **No generalized writer work was inserted
>   between 5F2D and 5F2E.**
> - The old top-level roadmap's **Phase 6 "qwen reviewer" is superseded by Phase
>   5F2E** (§30.12). 5F2E hard-codes no model: a project configures an allowed
>   internal reviewer model, so a separate qwen-only integration phase is no
>   longer required. **Phase 7 (fixer) remains separately unauthorized** and is
>   deliberately not renumbered here.
>
> ```text
> 5F2C           Controlled Single-File Writer        DONE / ACCEPTED
> 5F2D           Controlled Verification              DONE / ACCEPTED
> 5F2E           Controlled Reviewer Integration      DONE / ACCEPTED
> 5F2E-RS1       Reviewer Runtime Supervision         DONE
> 5F2E-RS1-FU1   Terminal timeout + wording fixes     DONE
> 5F2E-RS1-FU2   AIDO-owned reviewer wait deadline    DONE
> 5F2E-V1        Direct vLLM Reviewer Provider        DONE
> 5F2E-V1-FU1    Provider env isolation + wording     DONE
> 5F2E-V2        Structured vLLM Reviewer Output      DONE
> (token policy) Unlimited-by-default output tokens   DONE
> → bounded write → verify → supervised review → human
> ```
>
> **L2 is still not complete. Phase 7 (fixer) remains unauthorized.**
>
> ---
>
> **This document is a design review only. Phase 5A implements nothing.**
>
> It contains **no implementation**, adds **no runtime behavior**, adds **no CLI
> command and no CLI option**, makes **no model call**, makes **no network
> call**, reads **no environment variable**, constructs **no `LLMClient`**,
> fetches nothing from GitHub and writes nothing to GitHub, executes **no
> command**, edits **no file**, adds **no agent logic** and **no
> implementer/reviewer/fixer role wiring**, and reads, lists, stats, or resolves
> **no target project workspace**.
>
> **L2 remains proposed, not built.** Nothing described here is authorized to be
> implemented by this phase. Every sub-phase in §13 (Phase 5B and later) is a
> *proposal* and requires its own explicit authorization. (Phase 5B has since
> been authorized and implemented as **typed models and a parser only** — §15 —
> Phase 5C as a **dry-run validation command only** — §16, Phase 5D0 as a
> **canonical path guard library only** — §17, Phase 5D1 as **read-only
> workspace metadata inspection only** — §18, Phase 5E0 as **patch proposal
> artifact models and a parser only** — §19, Phase 5E1 as a **deterministic,
> offline proposal generator and one CLI command** — §20, Phase 5D2 as
> **bounded read-only file-content inspection only** — §21, Phase 5E2 as
> **unified diff proposal artifact models and a parser only** — §22, Phase
> 5E3 as a **deterministic, offline diff proposal producer and one CLI command**
> — §23, Phase 5F0 as **file-edit write gate models and a parser only** — §24,
> Phase 5F1 as a **dry-run file-edit preview command only** — §25, and Phase
> 5F2A as a **design-only first-workspace-write safety contract** — §26, and
> Phase 5F2B as a **create-aware canonical write-target guard library only** —
> §26.3 and §26.12. *(That list ended there when Phase 5F2B shipped. **Phase
> 5F2C has since been authorized and completed as the first controlled
> single-file workspace write** — §27 and §28, corrected by §28.13 — so "Phase
> 5F2C onward remain proposals" and "nothing edits a file" are **no longer
> true as statements of current status**. Phase 5F2D and Phase 5F2E remain
> proposals, and L2 is still not complete.)*)
>
> **L2 may not be invoked by any existing command after this phase.** After
> Phase 5A the shipped CLI surface is exactly what Phase 4L left behind —
> `version`, `inspect-issue`, `llm-smoke-test`, `generate-plan`,
> `real-llm-smoke-test`, `generate-model-plan` — and none of them gains an L2
> path, an `--apply` flag, or any other way to reach an implementer. (Phase 5C
> later added one **new** command, `l2-dry-run`, which validates and prints and
> takes no action; Phase 5D1 added a second, `l2-inspect-workspace`, which
> reports path metadata and takes no action. Neither changed any of the six
> above, and neither implements anything. Phase 5E1 added a third,
> `generate-patch-proposal`, which generates a prose-only proposal artifact
> offline and prints it; Phase 5D2 added a fourth,
> `l2-read-workspace-files`, which prints bounded, redacted file contents and
> takes no action; Phase 5E3 added a fifth, `generate-diff-proposal`, which
> generates unified diff text offline from local JSON inputs and prints it,
> applying nothing; Phase 5F1 added a sixth, `l2-preview-file-edits`, which
> validates a Phase 5F0 approved diff proposal against a project config and the
> lexical write policy and prints a **dry-run preview** of what a future write
> phase would be allowed to attempt, editing nothing. None of them changed any
> of the others, and none implements anything. **Phase 5F2C then added a
> seventh, `l2-apply-approved-file-edit`, which — unlike every command before
> it — really does write one file**, under the narrow contract of §28; it
> changed none of the others either, and no earlier command gained a write
> path.)
>
> It refines item **"Phase 5 — docs-only L2 implementer"** of
> [AI_DEV_ORCHESTRATOR_PLAN.md §7](AI_DEV_ORCHESTRATOR_PLAN.md#7-mvp-phase-roadmap)
> and picks up where
> [PHASE_4_L1_PLAN_GENERATOR_PLAN.md](PHASE_4_L1_PLAN_GENERATOR_PLAN.md) stops.
>
> **Phase 5B is now DONE** (§15). It implemented the §3 artifact as **typed
> models and a strict parser only** — no CLI behavior, no file loading, no
> workspace access, no model/network/environment access, and no L2 action.
>
> **Phase 5C is now DONE** (§16). It added the `l2-dry-run` command: it reads a
> project config and an approved-plan artifact, validates them, and prints the
> scope a future L2 *would* be bounded by. **No workspace access, no
> implementation, no model/network/environment access, no GitHub fetch or
> write, no command execution, no file editing, and no approval stamping.**
>
> **Phase 5D0 is now DONE** (§17). It implemented the §6.4 canonicalization
> sketch as a **library-only** path guard —
> `workspace/canonical.py` — and nothing else. **It is not workspace
> inspection**: no CLI command was added or changed, no shipped code path calls
> it, and its tests use pytest `tmp_path` directories only. It is the
> **prerequisite** §6.4 requires before Phase 5D.
>
> **Phase 5D1 is now DONE** (§18). It added the `l2-inspect-workspace` command
> and is the **first shipped code that may touch a configured target
> workspace** — as `stat` and nothing more. For each path an approved plan lists
> under `files_likely_to_change` it reports existence, kind, and size, after two
> explicit flags, a project-level opt-in, artifact validation, exact identity
> matching, candidate-count caps, the lexical Phase 1 path policy, and the Phase
> 5D0 canonical guard. **It reads no file contents, lists no directory, runs no
> command, edits no file, proposes no patch, and calls no model.**
>
> **Phase 5E0 is now DONE** (§19). It typed the **patch proposal artifact** as
> pydantic models plus a strict parser — `ai_dev_orchestrator.patch_proposal` —
> and nothing else. **It is not patch generation**: there is no generator, and
> the artifact deliberately carries **no unified diff**, no patch, no edit
> script, no command, and no file content. Library only — no CLI behavior, no
> workspace access, no file contents read, no file edited, no command run, no
> model / network / environment access, and no approval stamped.
>
> **Phase 5E1 is now DONE** (§20). It added the one thing Phase 5E0 withheld: a
> **deterministic, offline generator**, `build_deterministic_patch_proposal`,
> plus the `generate-patch-proposal` command that reads a project config and an
> approved plan, generates the artifact, and prints it to stdout. **It is still
> not a diff and still not file editing**: the artifact carries **no unified
> diff**, no patch, no edit script, no file content, no command, and no command
> output — only prose about paths the approved plan already named. **No
> workspace access, no file contents read, no file edited, no command run, no
> model / network / environment access, no GitHub fetch or write, no artifact
> file written, and no approval stamped.**
>
> **Phase 5D2 is now DONE** (§21). It added the `l2-read-workspace-files`
> command — the first phase whose **output may contain target workspace
> source**. For each path an approved plan lists under `files_likely_to_change`
> it canonicalizes, stats, and — only for a regular file inside the configured
> byte caps — reads, decodes as UTF-8, and prints the text after **mandatory**
> secret-like redaction. Gated by two explicit flags, a **separate**
> project-level opt-in from Phase 5D1's, artifact validation, exact identity
> matching, candidate-count caps, the lexical Phase 1 path policy, and the Phase
> 5D0 canonical guard. **It lists no directory, generates no diff, edits no
> file, runs no command, calls no model, and sends no content to one.**
>
> **Phase 5E2 is now DONE** (§22). It typed the **unified diff proposal
> artifact** as pydantic models plus a strict parser —
> `ai_dev_orchestrator.diff_proposal` — and nothing else. It lets a diff-shaped
> artifact **exist as data** and be validated for shape: one single-file textual
> diff per change, headers naming exactly the declared path, at least one hunk,
> and no binary/rename/delete/mode payload. **It is not diff generation and not
> diff application**: nothing here produces a diff, modifies one, applies one, or
> asks whether one would apply. Library only — no CLI behavior, no workspace
> access, no file contents read, no file edited, no command run, no model /
> network / environment access, and no approval stamped.
>
> **Phase 5E3 is now DONE** (§23). It added the producer Phase 5E2 withheld:
> `build_deterministic_diff_proposal`, plus the `generate-diff-proposal` command
> that reads four local files — a project config, an approved plan, a Phase 5D2
> `l2-read-workspace-files` packet, and a proposed-content JSON object — runs
> `difflib` over strings, and prints a Phase 5E2 artifact to stdout. **It reads
> no target workspace file directly**: original text arrives inside the packet
> or the generation for that path fails. **It generates diff text and does
> nothing with it** — no diff applied, no apply-cleanliness checked, no file
> edited, no command run, no model / network / environment access, no GitHub
> fetch or write, no artifact file written, and no approval stamped.
>
> **Phase 5F0 has since been authorized and implemented as file-edit write gate
> models and a strict parser only** — the second, separate human approval a
> future file-editing phase would need, typed as data (§24). It edits nothing,
> applies nothing, checks no apply-cleanliness, runs nothing, adds no command,
> and stamps no approval.
>
> **Phase 5F1 has since been authorized and implemented as a dry-run file-edit
> preview command only** (§25). It added `build_file_edit_preview` plus the
> `l2-preview-file-edits` command, which reads two local files — a project config
> and a human-approved Phase 5F0 diff proposal artifact — validates the artifact
> against the config by exact identity matching and against the **lexical** Phase
> 1 write policy, and prints what a future write phase *would be allowed to
> attempt*: permitted paths, change types, and **counts** summarizing each diff.
> It carries no diff text and no source contents. **It edits no file, applies no
> diff, checks no apply-cleanliness, reads/lists/stats/resolves/canonicalizes no
> target workspace, opens none of the paths the approved diff names, runs no
> command, calls no model, makes no network call, reads no environment variable,
> fetches nothing from and writes nothing to GitHub, creates no branch, commit,
> push or PR, writes no artifact file, and stamps no approval.** A preview
> describes a hypothetical; it authorizes nothing.
>
> **Phase 5F2A has since been authorized and completed as a design-only phase**
> (§26). It refines the contract the **first** workspace-write phase would have
> to satisfy — the dirty-tree check versus the no-command-execution promise, the
> input artifact path guard, canonicalization immediately before each write with
> create-vs-modify handled separately, the exact authorized path set,
> `max_changed_files`, protected and forbidden paths, transaction semantics,
> backup and rollback, where the apply-cleanliness check belongs, the
> stdout/stderr/exit-code contract, the capabilities still excluded, and the
> phase decomposition that follows. **It implements nothing.** No module, no
> function, no model, no config field, no CLI command, no CLI option, no file
> edit, no diff application, no apply-cleanliness check, no subprocess, no
> verification, no workspace read/list/stat/resolve/canonicalization, no model
> call, no network call, no environment read, no GitHub access, no
> branch/commit/push/PR, no artifact file written, and no approval stamped.
>
> **Phase 5F2B has since been authorized and completed as a library-only phase**
> — the create-aware canonical write-target guard of §26.3, hardened by
> 5F2B-FU1 against the remaining Win32 namespace aliases — with no config field,
> no CLI command, no CLI option, no caller, and no write. *(That paragraph
> originally continued "**Phase 5F2C, 5F2D, 5F2E, 5F2F / Phase 5F and every later
> sub-phase in §13 remain proposed and not authorized**, 5F2F remains the first
> controlled workspace write, **L2 is still not built, and nothing shipped so far
> edits a target workspace file**". **Phase 5F2C and Phase 5F2D have since been
> authorized and completed** — §28 and §29 — so those claims are history. Phase
> 5F2E and every later sub-phase in §13 remain proposals, and L2 is still not
> complete.)*
>
> **Phase 5F2C has since been authorized and completed** as the first controlled
> single-file workspace write (§28, corrected by §28.13), and **Phase 5F2D as the
> first controlled verification execution** (§29). Phase 5F2D added an eighth
> command, `l2-verify-approved-file-edit`, which — unlike every command before it
> — really does execute a program the *project* chose. It changed none of the
> other commands, the writer gained no verification flag, and the two capabilities
> remain independently invokable.

## 1. Goal

Design how a **future, separately authorized** L2 implementer could consume an
**approved** `L1Plan` and produce a **bounded implementation patch**, without
weakening any Phase 4 safety property.

The framing is deliberately narrow. Phase 4 ends with a plan artifact and a
human who must read it. Phase 5 asks one question: *what would have to be true
before any code could act on that artifact at all?* This document answers that
question and stops there.

To restate the boundary conditions of this phase explicitly:

- **Phase 5A implements nothing.** No module, no function, no test, no config
  field, no CLI surface.
- **No runtime behavior is added.** Importing the package behaves exactly as it
  did at Phase 4L; running any command behaves exactly as it did at Phase 4L.
- **L2 remains proposed, not built.** The handoff artifact in §3, the approval
  gate in §4, the capability stages in §5, and the phase split in §13 are
  designs, not commitments, and none of them is authorized.
- **L2 may not be invoked by any existing command after this phase.** There is
  no L2 entry point to invoke. When one eventually exists it will be a
  **separate command** (§4), never a flag bolted onto `generate-plan` or
  `generate-model-plan`.

### What L2 means here

[AI_DEV_ORCHESTRATOR_PLAN.md §4](AI_DEV_ORCHESTRATOR_PLAN.md#4-automation-levels)
defines L2 as *"local branch + implement + local commit."* This document treats
that definition as the **eventual** end state of a long sequence, not as the
first thing to build. The first useful L2 increment is much smaller than
"implement and commit": it is *read an approved plan, prove you understood its
boundaries, and print what you would do*. Everything past that is a separate
authorization.

## 2. Relationship to Phase 4

### 2.1 What Phase 4 now provides

Phase 4 shipped four things that Phase 5 would build on, and nothing else:

- **An offline `generate-plan` command** (Phase 4D,
  [cli.py](../src/ai_dev_orchestrator/cli.py)). It reads exactly two local files
  — `--project-config` and `--body-file` — parses the body with the Phase 2
  `parse_issue_body`, synthesizes an in-memory `GitHubIssue`, and runs the
  deterministic Phase 4C
  [`FakeL1Planner`](../src/ai_dev_orchestrator/plan/fake_planner.py). No GitHub
  fetch, no model call, no environment read, no workspace read.
- **A fake / model-backed library path** (Phases 4F and 4G,
  [plan/model_planner.py](../src/ai_dev_orchestrator/plan/model_planner.py)):
  the pure prompt builder `build_model_l1_plan_request(...)`, the
  `ModelBackedL1Planner` that takes an **injected** client, and the strict
  parser `parse_model_l1_plan_response(...)` that rejects — never repairs —
  invalid or policy-violating output. Library only; wired into nothing.
- **A gated real smoke command** (Phase 4K), `real-llm-smoke-test`: the first
  command permitted to open a real socket, behind `--real-model` plus a project
  opt-in and an exact model allowlist, sending a fixed connectivity prompt and
  no issue text.
- **A gated real L1 plan command** (Phase 4L), `generate-model-plan`: a separate
  command that does transmit the `--title` value and the local `--body-file`
  text to a real model, behind the same gate, and returns a plan.

And the property that matters most:

- **Every output remains L1 only and requires human approval.** `L1Plan`
  ([plan/models.py](../src/ai_dev_orchestrator/plan/models.py)) fixes
  `automation_level` to `"L1"` and `requires_human_approval` to `True` at the
  model level. Both the fake planner and the real one get those values from the
  orchestrator, never from model output; the Phase 4F parser **rejects** a
  response that even supplies them, so an injection attempt surfaces instead of
  being silently ignored.

### 2.2 The critical boundary

Three statements define the whole L1/L2 seam. Any future L2 design that
contradicts one of them is wrong.

**`L1Plan` is not executable instructions.** It is a description of intended
work, written for a human. `proposed_steps` is prose. `files_likely_to_change`
is a list of plain strings that were never resolved, stat'd, globbed, or
normalized — Phase 4B is explicit about this, and Phase 4C infers them from
path-shaped *tokens in issue text*, which is to say from untrusted input. A
future L2 must treat every one of those fields as a **hint to validate**, never
as a command to run or a path to trust.

**A real model plan is still only text for human review.** `generate-model-plan`
changes the *engine* that produced the words. It does not change their status.
A plan produced by a real model has exactly the same authority as one produced
by `FakeL1Planner`: none. The gate in Phase 4J/4K/4L authorizes *a model call*,
not *an action*, and §9 below states plainly that Phase 4L's authorization does
not extend to L2 in any form.

**Future L2 must require explicit human approval of a specific `L1Plan`
artifact before doing anything.** Not "an approved plan exists somewhere". Not
"the issue said automation was authorized". A *specific*, *saved*, *identified*
plan artifact that a *named human* approved, matched against the *exact*
project, repo, and issue L2 was asked to act on. §3 designs the artifact and §4
designs the gate.

### 2.3 What Phase 4 deliberately did not solve

Phase 5 inherits two open problems from Phase 4, both of which matter more once
writes are on the table:

- **Path handling is lexical.** See §6.4.
- **Prompt injection through issue text is contained, not eliminated.** Phase 4G
  wraps issue text in untrusted-data delimiters and Phase 4F rejects
  policy-violating output, but a plan whose *content* is adversarial is still a
  valid plan. See §12.

## 3. L1-to-L2 handoff artifact

**Typed in Phase 5B** — see §15. The shape below is now
[handoff/models.py](../src/ai_dev_orchestrator/handoff/models.py):
`PlanApproval`, `L1PlanProvenance`, `ApprovedL1PlanArtifact`, and the strict
parser `parse_approved_l1_plan_artifact`. Typing it added **models and a parser
only**: nothing loads such an artifact from disk, nothing consumes one, and no
command can reach it.

### 3.1 Suggested future shape

```jsonc
{
  "approval": {
    "approved_by": "...",
    "approved_at": "...",
    "approval_text": "I approve this L1 plan for L2 implementation",
    "source": "manual"
  },
  "plan_provenance": { /* engine, model, endpoint host, generated_at, ... */ },
  "plan": { /* ... the L1Plan, verbatim ... */ },
  "project_id": "...",
  "repo": "...",
  "issue_number": 42
}
```

### 3.2 Wrapper metadata vs `L1Plan` fields

The approval **must not** live inside `L1Plan`. This is the same call Phase 4H
§9.1 made for provenance, for the same reason, and it is even more important
here.

`L1Plan` is the shape a *planner* produces, and one of the two planners is a
model. Every field on that model is a field an adversarial or confused model
could try to fill in. Phase 4F already had to add explicit rejection of
model-supplied `automation_level` and `requires_human_approval`; adding an
`approved_by` field to `L1Plan` would create a third such trap, and a far worse
one — a model that writes `"approved_by": "the user"` into its JSON would be
attempting to forge consent.

So: **`L1Plan` stays exactly as Phase 4B defined it.** Approval, provenance, and
identity are **wrapper** fields, produced by the orchestrator and by a human,
sitting *around* an untouched plan. The wrapper is the only place a future L2
looks for authority, and the plan is the only place it looks for content. A
model can influence the second and can never influence the first.

### 3.3 Immutable plan snapshot

The `plan` field is a **snapshot**, not a reference. It carries the full plan
text as it stood when the human read it. Consequences:

- The human approves **the bytes they saw**, not a plan id that might resolve to
  something else later.
- A future L2 that reads the wrapper is reading the reviewed content by
  construction; there is no second fetch that could return different text.
- A future phase may add an integrity check over the snapshot (a digest in the
  wrapper, recomputed at load). This is worth doing but is **not** a substitute
  for the checks in §4 — a digest proves the plan was not edited after approval,
  which is a different claim from "a human approved this plan for this issue".

### 3.4 Why L2 should consume a saved artifact, not re-run planning

The tempting shortcut is a single command that plans and then implements. It
must be rejected, and the reasons compound:

- **Re-planning silently discards the review.** If L2 re-runs the planner, the
  plan it acts on is not the plan the human read. With a real model in the loop
  this is not even deterministic — the same issue can produce different plans on
  two calls.
- **It destroys the audit trail.** "Which plan was approved?" must have a
  file-shaped answer.
- **It fuses two authorizations into one.** Phase 4L authorizes a model call.
  A future phase would authorize workspace action. Fusing them means a single
  invocation crosses both boundaries with one confirmation, which is exactly the
  pattern the separate-command decision in Phase 4H §6 exists to prevent.
- **It reintroduces the untrusted path at the worst moment.** Planning consumes
  issue text — untrusted input. Implementation touches a workspace. Keeping a
  human-reviewed artifact between them is the only thing that stops untrusted
  text from reaching a write path in one hop.

So a future L2 takes `--approved-plan <path>` and **has no planning options at
all**: no `--body-file`, no `--title`, no `--model`, no `--issue` to plan from.
If the plan is missing, L2 stops. It never generates one.

### 3.5 Exact plan/repo/issue matching

L2 would be invoked with a project config *and* a plan artifact. Those two are
independent inputs that can disagree, so every identity field is checked for
**exact** equality — string equality, no normalization, no case folding, no
prefix matching, no globbing — mirroring the Phase 4J model-allowlist decision:

- `wrapper.project_id` == `ProjectConfig.project_id`
- `wrapper.repo` == `ProjectConfig.repo.github_repo`
- `wrapper.repo` == `wrapper.plan.repo`
- `wrapper.issue_number` == `wrapper.plan.issue_number`

Any mismatch is a hard stop with no action taken. The failure mode this prevents
is concrete and easy to hit by accident: a plan approved for `mis_project`
issue 42 being applied against the `a8_oa` workspace because the operator passed
the wrong `--project-config`.

### 3.6 Approval cannot be inferred from the presence of a file

**Writing a file is not approving a plan.** A future L2 must never treat "the
artifact exists", "the artifact parsed", or "the artifact has an `approval` key"
as approval. It must find, inside that block:

- a non-blank `approved_by`,
- a parseable `approved_at`,
- an `approval_text` matching the **exact required phrase**, and
- a `source` from a fixed, closed enum whose only initially permitted value is
  `"manual"`.

Anything else — a missing block, an empty block, a null field, a paraphrased
approval sentence, an unrecognized `source` — is **not approval**, and L2 stops.
Note the asymmetry this creates on purpose: it is trivially easy for a human to
approve a plan deliberately, and impossible to approve one by accident.

Two corollaries, restated because they are the ones most likely to be eroded
later:

- **The orchestrator never writes an `approval` block itself.** If a future
  phase adds a convenience command that stamps approval, that command is the
  approval act, it must demand an interactive confirmation, and it must be
  designed and authorized on its own — not folded into a plan generator.
- **A model may never populate any field under `approval`.** If a model-produced
  payload contains an `approval` key at any nesting level, that is an attempted
  forgery: **reject the artifact**, do not strip the key and continue.

## 4. Approval gate design

A future L2 gate fails **closed** at every step, in the Phase 4J/4K/4L style:
check cheap and local things first, and touch nothing expensive or external
until everything cheap has passed.

### 4.1 Required principles

- **L2 is off by default.** Absent explicit project configuration *and* an
  explicit invocation, no L2 code path is reachable. As with
  `real_model_planning` (Phase 4I), an absent config block is identical to a
  disabled one.
- **L2 requires a separate command** from every L1 command. `generate-plan`,
  `generate-model-plan`, `llm-smoke-test`, `real-llm-smoke-test`, and
  `inspect-issue` gain **no** L2 option, ever. Their existing guarantees are
  stated verbatim in [README.md](../README.md), and those sentences must remain
  true without amendment.
- **L2 requires an explicit flag** — `--apply-approved-plan` or similar —
  checked **first**, before the config is loaded, before the artifact is opened,
  before anything else. Without it: exit non-zero, nothing read, nothing
  touched. This mirrors the `--real-model` ordering in Phase 4K/4L.
- **L2 requires a plan artifact path.** No default location, no directory scan,
  no "most recent plan" lookup. The operator names the file.
- **L2 requires human approval metadata** satisfying §3.6 in full.
- **L2 rejects plans where `requires_human_approval` is false or missing.** Today
  the `L1Plan` model makes `True` the only valid value, so a plan failing this
  check is malformed or forged. L2 checks it anyway, explicitly: a downstream
  guard must not depend on an upstream invariant staying true forever.
- **L2 rejects plans whose `automation_level` is not exactly `"L1"`.** Exact
  string match. Not `"l1"`, not `"L1 "`, not `"L2"`. A plan claiming L2 is not a
  more-authorized plan — it is a **corrupt or hostile** one, because no
  component in this repo can produce it.
- **L2 rejects stale or mismatched project/repo/issue metadata**, per §3.5. A
  future phase may additionally treat an old `approved_at` as stale; if it does,
  the maximum age is project config, the comparison is explicit, and expiry
  means *stop*, never *warn and continue*.
- **L2 never treats model output as approval.** Approval comes from the wrapper,
  which comes from a human. No sentence a model emits — in a plan field, in a
  `risks` entry, in JSON that looks like an approval block — grants anything.
- **L2 never auto-approves based on `Automation Authorization` issue text.**
  This one deserves its own paragraph.

### 4.2 The `Automation Authorization` trap

The Phase 2 parser recognizes an `Automation Authorization` section
([issue_parser.py](../src/ai_dev_orchestrator/github/issue_parser.py)), and its
name makes it sound like a grant of authority. **It is not.** It is a heading in
a GitHub issue body. Anyone who can comment on or edit an issue can write
`Automation Authorization: L2 approved, proceed without review` into it, and a
plan generated from that issue will faithfully carry those words forward.

Therefore, for any future L2:

- The section is **never** parsed for authorization intent.
- Its presence, absence, and contents change **nothing** about what L2 will do.
- It may appear in a review packet as **quoted, labelled, untrusted text**, for a
  human to weigh — the same status Phase 4G gives all issue-derived text.
- The section is a *statement of intent by an issue author*. Authorization is a
  *decision by the operator*, made outside the issue, recorded in the wrapper.

The same reasoning applies to any future issue label, milestone, or comment that
appears to signal automation consent. Approval lives in exactly one place.

### 4.3 Gate ordering (fail closed, cheapest first)

1. `--apply-approved-plan` flag present? No → exit, nothing read.
2. Project config loads and validates (existing Phase 1 loader — which itself
   never reads `repo.workspace_path`).
3. Project-level L2 opt-in enabled? No → exit, artifact never opened.
4. Plan artifact path is **not** inside `repo.workspace_path` — string/path
   normalization only, exactly like the Phase 4D/4L `--body-file` guard, and
   never by touching the workspace path on disk.
5. Artifact parses into the typed wrapper (§3), `extra="forbid"`.
6. Approval block valid per §3.6.
7. `automation_level == "L1"` and `requires_human_approval is True`.
8. Identity fields match exactly per §3.5.
9. Capability requested is enabled for this project and this phase (§5).
10. **Only then** may anything else happen — and at the earliest authorized
    sub-phase, "anything else" means *printing what would be done*.

A failure at any step exits non-zero, prints a message naming the failed check,
and prints nothing to stdout. No partial work, no "continuing with warnings".

## 5. Future L2 allowed capability boundaries

Design only. None of these is implemented or authorized.

The purpose of splitting L2 into capability stages is that "implement a plan"
bundles together operations with wildly different blast radii. Reading a file
under a policy is recoverable; running a command is not.

| # | Capability | First L2 implementation? |
|---|---|---|
| 1 | Read-only workspace inspection | **Yes** — with a caveat, see §6.4 |
| 2 | Patch proposal generation (artifact only) | **Yes** |
| 3 | File editing | **Deferred** |
| 4 | Command execution | **Deferred** |
| 5 | Verification | **Deferred** |
| 6 | Review packet output | **Deferred (partial)** |

**1. Read-only workspace inspection — allowed first, conditionally.** Reading
listed files under the project's `allowed_paths` is the smallest capability that
makes L2 more useful than L1, because it is the first time the orchestrator can
check a plan against reality: does `src/foo/bar.py` exist, does the function the
plan names appear in it, is a "small change" actually small. It is also the
first capability that touches a target workspace at all, which is why §6.4's
canonicalization question must be settled **before** it ships, not after.

*Phase 5D1 has since shipped the first half of this capability* (§18): the
**metadata** half — existence, kind, and size — and not the content half. The
split was not in the original plan and is worth recording. "Does `src/foo.py`
exist and is it 40 lines or 4000" is a genuinely different disclosure from "here
is what `src/foo.py` says", and it is enough to check a plan's most common
failure mode (a path that is simply wrong) while disclosing almost nothing.

*Phase 5D2 has since shipped the content half* (§21), as its own command behind
its own project opt-in rather than as a flag on the metadata one — bounded by a
file-count cap, a per-file byte cap and a total-byte cap, and with mandatory
secret-like redaction on everything it prints. It reads and prints; it still
diffs nothing, edits nothing, runs nothing, and sends nothing to a model.

**2. Patch proposal generation — allowed first.** A patch *proposal* is an
artifact: a unified diff, or a list of intended edits, written to a path
**outside** the workspace and never applied. It carries most of the value of L2
(a human sees concrete changes instead of prose) at a fraction of the risk (an
unreviewed proposal changes nothing). If a proposal is wrong, the cost is a
discarded file.

**3. File editing — deferred.** The first write to a target workspace is the
single largest step-change in this project's risk profile, and it should not
share a phase with anything else. It needs the write-path policy of §6, the
`max_changed_files` cap, a dirty-tree check, and its own authorization.

*Phase 5F2A has since written the full safety contract for that first write*
(§26) — including how the dirty-tree requirement is met **without** command
execution (§26.1) — **as design only**. Nothing was implemented, and every
phase that would write remains unauthorized.

**4. Command execution — deferred, and deferred *after* file editing.** Running
a process is the only capability whose blast radius is not bounded by the path
policy at all. See §7.

**5. Verification — deferred.** Verification is command execution wearing a
different hat, and gets the same treatment (§7), plus a rule keeping the two
allowlists separate.

**6. Review packet output — deferred, but partially available early.** A packet
summarizing inspection findings and a patch proposal is worth having as soon as
stages 1–2 exist. The *full* packet of §11 needs diffs, command output, and
verification status, so the complete form waits for those stages.

### Recommendation

**The first L2 implementation should be read-only workspace inspection plus a
patch proposal artifact — not direct file writes.** Direct file edits and
command execution belong in later, separately authorized sub-phases.

This is the same shape Phase 4 used to good effect: `FakeL1Planner` before any
model, `MockTransport` before any socket, a library gate before any command.
Each step was small enough to review completely. An L2 that reads a workspace
and writes a diff to a scratch file is reviewable in the same way. An L2 that
edits files and runs commands on its first outing is not.

## 6. Workspace access policy for future L2

Design only. Today **nothing** in this repo reads a target workspace, and Phase
5A does not change that.

### 6.1 Which workspace, and when

- L2 may access **only** the `repo.workspace_path` configured for the **selected
  project**, and only after the §4 gate has fully passed.
- **Never another project's workspace.** `C:\dev\mis_project`, `C:\dev\a8_oa`,
  and `C:\dev\bible_reading_v2` are separate projects; holding an approved plan
  for one grants nothing anywhere else.
- **Never `C:\dev` itself or any parent.** A path resolving to or above the
  parent directory is a hard boundary violation, not a policy warning.
- The workspace root comes from **config**, never from a plan field, never from
  a command-line override, and never from issue text.

### 6.2 Path rules

Within that root, the existing Phase 1 precedence applies —
**forbidden > protected > allowed > unlisted**, as implemented in
[workspace/path_policy.py](../src/ai_dev_orchestrator/workspace/path_policy.py):

- **Refuse anything outside `allowed_paths`.** Unlisted is not neutral; it is
  denied. `PathPolicy.check_write` already behaves this way.
- **Require extra approval for `protected_paths`.** `check_write` exposes this
  as `allow_protected`, and `check_read` flags protected reads as requiring
  authorization. For L2 that approval must be **per-invocation and explicit**,
  not a config flag someone sets once and forgets.
- **Always refuse `forbidden_paths`**, with no override, no escalation flag, and
  no "authorized protected" equivalent.
- **Enforce `workspace_policy.max_changed_files`.** It defaults to 20. It is
  checked against the **proposed** change set *before* any write begins — a run
  that would exceed the cap fails entirely rather than writing the first N files
  and stopping. Partial application of a plan is a worse outcome than no
  application.
- **Honor `workspace_policy.deny_outside_workspace`** and
  `workspace_policy.allow_symlinks` (§6.4).

Each of these bullets is carried forward and made precise for the first write
phase in §26 — the exact authorized path set in §26.4, `max_changed_files` in
§26.5, and the forbidden/protected rules (including why there is deliberately
**no** standing config switch for protected writes) in §26.6.

### 6.3 Centralize the checks

Every path decision goes through **one** module. Not one per command, not one
per capability. Phase 4 already shows the cost of duplication: `_is_same_or_under`
in [cli.py](../src/ai_dev_orchestrator/cli.py) exists separately from
`PathPolicy` because they answer different questions, and both `generate-plan`
and `generate-model-plan` now carry their own copy of the same guard call. With
two commands and one guard that is manageable; with six capabilities and three
guards it is a latent divergence bug in which one caller quietly misses a check.

The rule for any future L2: **a capability that touches a path calls the policy
module and cannot proceed without a `PathDecision`.** No direct `open()`, no
direct `Path.read_text`, no ad-hoc string comparison in a command body.

### 6.4 The known Phase 4 string-normalization gap

Phase 4's path handling is **lexical by design and by necessity**.
`PathPolicy.normalize` splits on separators, resolves `.` and `..` in memory,
casefolds for comparison, and matches glob patterns with `fnmatch` — it never
touches disk. `_is_same_or_under` uses `os.path.abspath` + `os.path.normcase`,
which join and normalize but perform no filesystem access. That was the right
call for Phase 4: the whole point was to evaluate paths for `C:\dev\mis_project`
**without ever touching that folder**, and a lexical check cannot be tricked into
touching it.

The gap is that a lexical check is only sound when nothing on disk redirects a
path. It does not account for:

- **Symlinks and NTFS junctions / directory reparse points.** A junction at
  `<workspace>\vendor` pointing at `C:\dev\a8_oa` passes every lexical check and
  lands outside the workspace. `workspace_policy.allow_symlinks` defaults to
  `False`, but today that flag is only *exposed* by `PathPolicy.allow_symlinks`
  — filesystem checks are explicitly deferred, and nothing enforces it, because
  nothing reads a workspace.
- **UNC paths** (`\\server\share\...`). `_DRIVE_RE` matches a drive letter;
  `_split` drops empty components, so the leading `\\` is lost and a UNC path
  can normalize into something that compares against a local root in unintended
  ways.
- **Mapped network drives.** `Z:\` and `\\server\share` can be the same
  location; lexically they share nothing.
- **8.3 short names** (`MIS_PR~1`) and other Windows aliasing, including
  trailing dots/spaces and the `\\?\` prefix form, all of which name the same
  file with different strings.
- **Case sensitivity assumptions.** Casefolding is right for typical Windows
  volumes and wrong for case-sensitive ones.

**Decision: yes — canonicalization must be strengthened before any
write-capable phase, and before read-only inspection.** The reasoning is that
the moment L2 touches the filesystem, the lexical check stops being a complete
answer, and that moment arrives at **stage 1 (read-only inspection)**, not at
stage 3 (file editing). A read that follows a junction out of the workspace is
already a boundary violation — it discloses another project's source.

What strengthening should look like, as a design sketch for a future phase:

- Keep the lexical check as a **first, cheap, disk-free gate**. It stays exactly
  as it is, and it keeps its property of never touching the path it rejects. It
  is necessary but no longer sufficient.
- Add a **second, on-disk canonicalization step** that runs *only after* the
  lexical gate passes and only within the already-approved workspace root: real
  path resolution, containment re-verification against the resolved root, and an
  explicit reparse-point/symlink check honoring `allow_symlinks`.
- **Fail closed on ambiguity.** If a path cannot be canonicalized, if resolution
  changes its containment answer, or if a reparse point is encountered while
  `allow_symlinks` is false, the operation stops.
- **Re-verify at use, not only at plan time.** A check performed once and reused
  later is a time-of-check/time-of-use bug; containment is re-established
  immediately before each read or write.
- Handle UNC and extended-length prefixes explicitly rather than letting them
  fall through the drive-letter path.

This work is a **prerequisite** for Phase 5D in §13, not a follow-up to it.

**Phase 5D0 has since implemented this sketch as a library** — see §17. The
lexical gate is unchanged, and the new module adds the on-disk second gate,
the reparse-point check, the fail-closed ambiguity handling, and explicit
UNC/extended-length/device/trailing-dot-or-space/8.3 rejection. It is **not**
wired into anything: the prerequisite is now built, and Phase 5D itself remains
unauthorized.

## 7. Command execution policy for future L2

Design only. **Nothing in this repo executes commands**, and Phase 5A adds no
such capability.

- **Off by default**, at every level: absent config, absent flag, absent phase
  authorization all mean no execution.
- **Allowlisted commands only, from project config.** A closed list of
  executable names with their permitted arguments. Exact matching, in the Phase
  4J style — no prefixes, no globs, no "starts with `pytest`".
- **No `shell=True`, ever.** Argument vectors only. No shell means no
  metacharacter interpretation, no pipes, no chaining, no redirection, and no
  quoting bugs that turn one command into two.
- **No arbitrary command strings from model output.** This is absolute. A model
  never selects, composes, or parameterizes a command. Phase 4F's policy guard
  already *rejects plans* that propose command execution; L2 must additionally
  have no code path that could accept one if a plan somehow carried it.
- **No commands outside the repo workspace.** The working directory is the
  approved workspace root, established after §6.4 canonicalization.
- **Timeout required.** Every execution carries a bounded timeout with no
  unlimited option. Timeout means stop and report (§10).
- **Output capture with redaction.** Output is captured, size-bounded, and
  passed through redaction before it is stored or displayed.
- **Command output may contain secrets and must not be blindly sent to a
  model.** Test output, stack traces, and debug logs routinely contain tokens,
  connection strings, and file contents from paths L2 was never allowed to read.
  Sending captured output to a model is a **separate authorization** with its
  own design, subject to the same rules as source context in §9.
- **Verification commands are separate from implementation commands.** Two
  distinct allowlists, two distinct config keys, two distinct authorizations.
  Permission to run `pytest` is not permission to run `pip install`, and a phase
  that grants verification must not silently widen into a build/install phase.

## 8. Git policy for future L2

Design only.

- **The AI still must not commit or push, by default.** This is the standing
  rule in [CLAUDE.md](../CLAUDE.md) and in
  [AI_DEV_ORCHESTRATOR_PLAN.md §4](AI_DEV_ORCHESTRATOR_PLAN.md#4-automation-levels),
  and Phase 5 does not relax it. Note the divergence from the roadmap's L2
  definition ("local commit"): this design **defers local commit** past the
  first L2 implementations, because file editing and committing are separate
  risks and there is no reason to take them together.
- **Branch creation only if explicitly authorized in a later phase**, with its
  own design. `repo.branch_prefix` exists in config for this eventual purpose
  and is read by nothing today.
- **No push without explicit human approval**, per invocation. Never a config
  flag alone.
- **No PR creation without explicit human approval.** GitHub remains read-only
  (Phase 2 `inspect-issue`) until a phase explicitly authorizes otherwise.
- **`git diff` may be read only after workspace read access is authorized** —
  it is a workspace read, and it goes through §6's policy and §7's execution
  rules (or an equivalent bounded, allowlisted mechanism). Diff output can also
  contain secrets from files L2 may not read, so it is subject to §7's redaction
  and §9's transmission rules.
- **Never merge `main`.** Unchanged, unconditional.
- **The review packet is the deliverable**, not a commit: diff, changed files,
  verification result, and risk summary (§11). A human commits.

## 9. Model usage policy for future L2

Design only.

- **L2 implementation may be fake/deterministic first.** A deterministic L2 that
  turns an approved plan into a patch proposal through fixed rules — no model at
  all — is genuinely useful for building and testing the gate, the path policy,
  and the packet format, exactly as `FakeL1Planner` was for Phase 4.
- **Any model-backed L2 needs a separate design and a separate gate.** Its own
  design document, its own project config block, its own flag, its own command.
- **Real model L2 does not inherit Phase 4L authorization.** Phase 4L was
  authorized for `generate-model-plan` and for that command only — the
  acceptance criteria say so explicitly. A real model *implementer* is a
  different capability at a different automation level with a different blast
  radius, and it requires new, explicit authorization. Reusing the
  `real_model_planning` config block for it would be a **misuse of a
  planning-scoped opt-in**; L2 gets its own.
- **Do not send source files to a model** unless a later phase explicitly
  authorizes source-context transmission. Note what this means for a model-backed
  L2: a plan-only implementer with no source context is of limited use, so the
  source-context question must be answered *before* a model-backed L2 is
  designed, not discovered midway.
- **If source context is ever sent, it must be path-bounded, size-bounded, and
  audit-aware**: only files that passed the §6 read policy; a hard cap on file
  count and total bytes, enforced before the request is built; the operator told
  in a non-suppressible stderr banner **which files** are being transmitted,
  before transmission — the Phase 4K/4L banner pattern, extended to name the
  payload.
- **No secrets in prompts.** No API keys, no `GITHUB_TOKEN`, no `.env` contents,
  no captured command output containing credentials. `forbidden_paths` exists
  partly for this, and secret-shaped content must be excluded even from files
  that are otherwise readable.

## 10. Failure handling

Design only. Every case fails **closed**: stop, report, change nothing.

| Condition | Behavior |
|---|---|
| No approved plan supplied | No L2 action. Exit non-zero before anything is read. |
| Invalid plan artifact (unparseable, wrong shape, extra keys, invalid approval block) | No action. Nothing opened past the artifact itself. |
| Project / repo / issue mismatch | No action. Name the mismatched field; never "proceed with the config's value". |
| `automation_level != "L1"` or `requires_human_approval` not `True` | No action. Treated as corrupt or forged, not as elevated. |
| Path outside `allowed_paths`, or containment ambiguity (§6.4) | No action for that path, and no partial run — the whole invocation stops. |
| `forbidden_paths` conflict | No action. No override exists. |
| `protected_paths` conflict | No action **unless** explicitly escalated for that invocation; escalation is per-run and per-path, never a standing config grant. |
| Change set exceeds `max_changed_files` | No action at all — never write the first N and stop. |
| Verification failure | No commit, no push, no PR. Report the failure in the packet. |
| Model parser failure (Phase 4F error types) | No edits. Report the failure category by name; do not echo the raw reply (Phase 4L precedent). |
| Command timeout | Stop, report the command and that it timed out. No retry, no continuation of later steps. |
| Dirty working tree | Stop. A dirty tree makes "what did the AI change?" unanswerable, which defeats review. **§26.1 refines this**: the verdict is tri-state, `undetermined` is treated as dirty, it is computed **without** running `git` or any other command, and a human attestation may not replace it. |
| Git divergence (local behind/ahead/diverged from remote) | Stop. Do not fetch, rebase, merge, or reset to fix it. |

Two cross-cutting rules:

- **Never repair, never continue.** Phase 4F's "reject, never repair" applies to
  every L2 input, not just model output. There is no L2 failure whose correct
  handling is "warn and proceed".
- **Failures are quiet about content and loud about category.** Phase 4L set the
  precedent: name *what kind* of thing failed; do not echo raw model output, and
  do not echo file contents or captured output that may carry secrets.

## 11. Output / review packet design

Design only. The review packet is what L2 produces **for a human** — the analog
of `L1Plan`, one level down.

Contents:

- **The approved plan snapshot** — the exact plan acted on, plus the approval
  metadata (who, when) that authorized it.
- **Files inspected** — every path read, with its `PathDecision` classification.
  This is the audit trail proving L2 stayed inside its boundary.
- **Files proposed or changed** — with the count checked against
  `max_changed_files`.
- **The diff**, if any — proposed (early phases) or applied (later phases),
  clearly labelled as to which.
- **Commands run and their outputs** — only when command execution is authorized
  and only from the allowlist, with §7 redaction applied.
- **Verification status** — what ran, what passed, what failed.
- **Risks and unresolved questions**, carried forward from the plan's `risks` /
  `open_questions` and added to by L2 — including anything it could not check,
  such as a plan step naming a path outside `allowed_paths`.
- **Human next steps** — explicitly what the human must do, given that L2 does
  not commit, push, or open PRs.

And two hard exclusions:

- **No secrets.** No API keys, no tokens, no `.env` content, no credential-shaped
  strings from files or command output.
- **No raw prompt or completion by default.** Same rule as Phase 3 §5 and Phase
  4L: prompt/completion bodies stay out of default output, behind an
  off-by-default, separately designed audit mechanism at most. Note that Phase 4I
  already types `allow_prompt_audit_files` as `false` by default and **nothing
  writes such a file today**; L2 does not change that.

## 12. Security and privacy risks

The major risks a future L2 must be designed against:

- **Prompt injection from the issue body.** Issue text is untrusted and
  attacker-controllable. Phase 4G's delimiters and Phase 4F's rejection rules
  contain it during planning; L2's defense is that it never reads issue text at
  all — it reads an approved plan.
- **Plan injection through `L1Plan` fields.** A model-produced plan's fields are
  model-controlled. `files_likely_to_change` in particular is a list of strings a
  model chose, and Phase 4C derives it from *issue text*. L2 must treat every
  path in a plan as a **request to validate**, never as an authorization.
- **Accidental workspace traversal.** Wrong `--project-config`, `..` in a path,
  a plan naming an absolute path. §3.5 identity matching and §6 policy are the
  defenses.
- **Symlink / junction bypass.** §6.4. The one gap where the current lexical
  approach is provably insufficient once the filesystem is touched.
- **Source code leakage to real models.** The largest privacy risk in the whole
  project. §9 keeps it behind an explicit, bounded, announced authorization.
- **Secrets in files or command output.** `.env` files, credential-bearing
  configs, tokens in test output. Mitigated by `forbidden_paths`, redaction
  (§7), and the packet exclusions (§11) — none of which is complete on its own.
- **A model inventing edits beyond scope.** A model-backed L2 can propose
  changes no one asked for. Mitigated by the path policy, `max_changed_files`,
  proposal-before-write staging, and human review of the packet.
- **Command execution escalation.** A build command that runs arbitrary project
  scripts is an arbitrary-code-execution path with a friendly name. §7's
  allowlist, no-shell, and separate-verification rules are the mitigation, and
  the residual risk is real enough to justify deferring the capability.
- **GitHub write accidents.** Any write is externally visible and hard to undo.
  Read-only until explicitly authorized (§8).
- **Approval confusion** — believing something was approved when it was not:
  presence of a file mistaken for approval (§3.6), `Automation Authorization`
  text mistaken for approval (§4.2), an approval for issue 41 applied to issue
  42 (§3.5), a Phase 4L model-call authorization mistaken for an L2 action
  authorization (§9). This class of risk is the reason approval is a single,
  explicit, human-written, exactly-matched artifact and nothing else.

## 13. Proposed Phase 5 split

**Proposals only. None of the following is authorized by this phase.** Each
sub-phase requires its own explicit prompt, and each may be re-scoped or
abandoned.

- **Phase 5A — this docs-only boundary design.** No code. *(This document.)*
- **Phase 5B — typed approved-plan handoff models and parser only. DONE.** The
  §3 wrapper as pydantic models plus a strict parser, `extra="forbid"`, in the
  Phase 4B/4F style. Library only, wired into nothing. **No workspace access, no
  CLI behavior, no model call, no network call, no environment read.** See §15.
- **Phase 5C — L2 dry-run CLI that validates an approved plan and prints the
  intended scope only. DONE.** A separate command running the §4 gate as far as
  this phase is authorized to go and printing what *would* be in scope. **No
  workspace access**, no reads of `repo.workspace_path`, no edits, no commands.
  See §16.
- **Phase 5D0 — canonical path guard library only. DONE.** The §6.4
  canonicalization step as a reusable library: strict on-disk canonicalization,
  robust containment re-verification, a symlink/junction/reparse-point policy,
  and a fail-closed lexical precheck for ambiguous Windows path forms. **Library
  only** — no CLI behavior, no command, no option, and no caller. **It is not
  workspace inspection**, and its tests use pytest `tmp_path` only. See §17.
- **Phase 5D1 — read-only workspace *metadata* inspection. DONE.** The first
  phase that touches a target workspace, and only through the Phase 5D0 guard
  plus `stat`: existence, kind, and size for the paths an approved plan lists
  under `files_likely_to_change`. **No file contents, no directory listing, no
  glob, no tree walk, no writes, no commands, no model.** See §18.
- **Phase 5D2 — bounded read-only file *contents* under the path policy. DONE.**
  The disclosure Phase 5D1 deliberately stopped short of: "does
  `src/foo/bar.py` exist and how big is it" and "what does `src/foo/bar.py`
  say" are different questions, and this phase answers the second — bounded by
  a per-file cap, a total-bytes cap, and a file-count cap, behind its **own**
  project opt-in, and with mandatory secret-like redaction on every byte
  printed. **No directory listing, no glob, no tree walk, no diff, no writes,
  no commands, no model, and no content sent to a model.** See §21.
- **Phase 5E0 — patch proposal artifact models and parser only. DONE.** The
  proposal artifact as pydantic models plus a strict parser, `extra="forbid"`,
  in the Phase 4B/4F/5B style. **Library only, wired into nothing**, and **not a
  generator**: nothing produces a proposal, and the artifact carries **no
  unified diff**, no patch, no edit script, no command, and no file content —
  only prose describing suggested work on paths the approved plan already named.
  **No workspace access, no file contents read, no CLI behavior, no model call,
  no network call, no environment read, no file editing, no command execution,
  and no approval stamping.** See §19.
- **Phase 5E1 — a deterministic patch proposal generator. DONE.** The thing
  that actually *produces* a Phase 5E0 artifact from an approved plan:
  `build_deterministic_patch_proposal`, a pure offline function over two
  already-loaded objects, plus the `generate-patch-proposal` command that prints
  its result to stdout. It restates the plan's own `files_likely_to_change` as
  one prose `modify` change each, and **generates no diff** and carries no file
  content — carrying a real diff is Phase 5E2, which has since shipped the
  *artifact* for one but still no producer. **No workspace access, no
  file contents read, no file editing, no command execution, no model/network/
  environment access, no artifact file written, and no approval stamped.**
  See §20.
- **Phase 5E2 — unified diff proposal artifact models and parser only. DONE.**
  The half of "carrying a real diff" that can be built without producing one:
  the diff-bearing artifact as pydantic models plus a strict parser,
  `extra="forbid"`, in the Phase 5E0 style. A `unified_diff` field now exists and
  may contain source lines as diff context — that is what a diff is, and it is
  allowed **as data** — but **nothing generates it, modifies it, or applies it**,
  and `applies_cleanly_checked` is `Literal[False]` because asking whether a diff
  applies means touching a workspace. **Library only, wired into nothing.** **No
  workspace access, no file contents read, no CLI behavior, no model call, no
  network call, no environment read, no file editing, no command execution, and
  no approval stamping.** See §22.
- **Phase 5E3 — a deterministic producer for the Phase 5E2 artifact. DONE.**
  Something that actually *generates* a unified diff — from a Phase 5D2 content
  packet and a proposed-content input supplied as **local JSON files**, never
  from a direct workspace read of its own — behind its own gate. It ships
  `build_deterministic_diff_proposal` and the `generate-diff-proposal` command.
  The remaining decision that Phase 5E2 left open is answered here in the
  restrictive direction: a diff generated from **redacted** source is refused
  outright, and a generated diff that looks like it carries a credential is
  discarded rather than redacted, because a redacted diff reads like a patch and
  could never apply. **No diff applied, no apply-cleanliness checked, no
  workspace read, no file edits, no commands, no model, no artifact file
  written.** See §23.
- **Phase 5F0 — file-edit write gate models and parser (DONE).** The explicit,
  separately worded human approval of one **concrete diff proposal**, typed as
  data. It is the gate a write would have to pass, built and reviewable before
  anything can write. **No file edit, no diff application, no apply-cleanliness
  check, no workspace read, no commands, no model, no CLI command, no artifact
  file written, no approval stamped.** See §24.
- **Phase 5F1 — dry-run file-edit preview command (DONE).** The separately gated
  dry-run plan this slot reserved: what a write *would* touch, and nothing more.
  It ships `build_file_edit_preview` and the `l2-preview-file-edits` command,
  which validates a Phase 5F0 approved diff proposal against the project config
  and the **lexical** Phase 1 write policy and prints the permitted paths, change
  types, and diff **counts** — no diff text, no source contents. Protected paths
  are refused outright and one refusal fails the whole preview. **No file edit,
  no diff application, no apply-cleanliness check, no workspace read, list, stat,
  resolve, or canonicalization, no commands, no model, no branch/commit/push/PR,
  no artifact file written, no approval stamped.** See §25.
- **Phase 5F2A — first workspace write safety design (DONE).** Design only, and
  the reason the single "Phase 5F2" slot below became five. It writes the
  contract the first write phase must satisfy — the dirty-tree requirement met
  **without** command execution, the input artifact path guard, canonicalization
  immediately before each write with `create` and `modify` handled differently,
  the exact authorized path set, `max_changed_files`, forbidden and protected
  paths, transaction semantics, backup/rollback, where the apply-cleanliness
  check belongs, the stdout/stderr/exit-code contract, and the excluded
  capabilities. **It implements nothing**: no module, no function, no model, no
  config field, no CLI command or option, no file edit, no diff applied, no
  apply-cleanliness check, no subprocess, no workspace touch, no model or
  network call, no branch/commit/push/PR, no approval stamped. See §26.
- **Phase 5F2B — create-aware canonical write-target guard (DONE). Library
  only.** Closes the gap §26.3 identifies: the Phase 5D0 guard resolves with
  `strict=True` and cannot validate a destination that does not exist yet, so a
  `create` target had no guard at all. `canonicalize_write_target_under_workspace`
  is the second entry point in `workspace/canonical.py` — a caller-declared
  `change_type` of exactly `modify` or `create` (never inferred from disk), the
  same fail-closed lexical precheck before any filesystem use, the Phase 5D0
  containment/symlink machinery for `modify`, parent canonicalization plus
  final-component rules plus `ENOENT`-via-`lstat` for `create`, the
  dangling-link refusal, and the destination-is-never-a-link rule in both
  `allow_symlinks` modes. It returns a frozen `CanonicalWriteTarget` describing
  the filesystem **at the time of the call**, which is not a durable
  authorization: §26.3 still requires re-canonicalization immediately before an
  actual write, and 5F2B does not solve TOCTOU. **No config field, no CLI
  command, no option, no caller, no directory created, no file created, no
  write.**
  - **Phase 5F2B-FU1 (DONE)** then hardened that guard's own lexical gate
    against the remaining Win32 namespace aliases — alternate data streams and
    stray colons, drive-relative `C:file` forms, reserved device names, and
    reserved/control characters (§26.3) — layered as a **write-target-only**
    helper so Phase 5D0 read semantics and its caller are untouched. Still
    library only: no config field, no CLI command, no option, no caller, and no
    write. It also recorded the **hard-link** question as unresolved (§26.13
    item 11) rather than implementing any hard-link behavior.
- **Phase 5F2C — typed workspace-write gate models. Library only. Proposed, not
  authorized.** The per-invocation protected-path authorization of §26.6 and
  whatever `workspace_write` opt-in the writer needs, as models plus a strict
  parser — with **no** standing protected-write switch. **Wired into nothing, no
  write, no approval stamped.**
- **Phase 5F2D — read-only Git-state probe. Proposed, not authorized.** §26.1's
  mechanism, behind its own project opt-in: a tri-state `clean` / `dirty` /
  `undetermined` verdict computed by reading `.git` in-process. **No `git`
  binary, no subprocess, no shell, no repository content in the output, no
  write.**
- **Phase 5F2E — read-only write preflight command. Proposed, not authorized.**
  Composes 5F2B/5F2C/5F2D with the Phase 5F1 preview and the Phase 5D2 content
  read to answer "would this write be permitted right now, and would each diff
  apply?", including the **advisory** apply-cleanliness check of §26.9. It is
  the first thing that canonicalizes a write destination. **Writes nothing,
  stages nothing, creates no journal, and its verdict is never consumed by the
  writer.**
- **Phase 5F2F / Phase 5F — the first controlled workspace write under
  `allowed_paths`. Proposed, not authorized.** The first write.
  `max_changed_files` enforced, dirty-tree verdict enforced, staged and
  journalled with all-or-nothing rollback per §26.7 and §26.8. **No command
  execution.**
- **Phase 5G — allowlisted verification commands.** §7 in full. **No commit, no
  push.**
- **Phase 5H — review packet generation.** §11 in full.
- **Later — optional branch / commit / PR workflow**, only if explicitly
  authorized, each as its own phase (§8).

Two notes on this ordering. First, it deliberately puts three non-workspace
phases (5B, 5C, and this one) before anything touches a target project — the
gate is fully built and reviewable before it guards anything. Second, the
roadmap's original L2 definition (branch + implement + local commit) is spread
across 5F and "later" rather than landing in one phase, because bundling them
would mean a single authorization crossing three distinct risk boundaries.

## 14. Acceptance criteria for Phase 5A (DONE)

- [x] The design doc (`docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md`) exists
  and covers the goal, the Phase 4 relationship and critical boundary, the
  handoff artifact, the approval gate, capability boundaries, workspace access
  policy (including the string-normalization gap and a decision on it), command
  execution policy, git policy, model usage policy, failure handling, the review
  packet, security/privacy risks, the proposed phase split, and these criteria.
- [x] **Docs-only.** The working tree contains changes to Markdown files only.
- [x] **No `src/` or `tests/` changes** in this phase.
- [x] **No runtime behavior added.**
- [x] **No CLI behavior added** — no new command, no new option, and no change
  to `version`, `inspect-issue`, `llm-smoke-test`, `generate-plan`,
  `real-llm-smoke-test`, or `generate-model-plan`.
- [x] **No model call, no network call, and no environment-variable read** —
  including no `AIDO_LITELLM_*` read and no `LLMClient` construction.
- [x] **No GitHub fetch and no GitHub write.**
- [x] **No command execution.**
- [x] **No file editing engine.**
- [x] **No agent logic and no implementer/reviewer/fixer role wiring.**
- [x] **No target project workspace access** — nothing under
  `repo.workspace_path` for any project was read, listed, stat'd, or resolved,
  and `C:\dev\mis_project`, `C:\dev\a8_oa`, `C:\dev\bible_reading_v2`, and the
  `C:\dev` parent were not touched.
- [x] **L2 is not implemented and cannot be invoked.** No existing command gains
  an L2 path, and no L2 entry point exists.
- [x] **Phase 5B and every later sub-phase in §13 remain proposed and not
  authorized.** *(Phase 5B was subsequently authorized and implemented — see
  §15. Phase 5C onward are still unauthorized.)*

## 15. Phase 5B — typed handoff models and strict parser (DONE)

Phase 5B implemented §3 of this document, and **only** §3's data shape.

### 15.1 What it is

- [handoff/models.py](../src/ai_dev_orchestrator/handoff/models.py) —
  `ApprovedPlanError` / `ApprovedPlanParseError` / `ApprovedPlanValidationError`,
  the exact constant `REQUIRED_APPROVAL_TEXT`, the `PlanApproval`,
  `L1PlanProvenance` and `ApprovedL1PlanArtifact` models (all `extra="forbid"`),
  and the pure function `parse_approved_l1_plan_artifact(text) ->
  ApprovedL1PlanArtifact`.
- [handoff/\_\_init\_\_.py](../src/ai_dev_orchestrator/handoff/__init__.py) —
  exports those eight names and nothing else.
- [tests/test_approved_plan_handoff_models.py](../tests/test_approved_plan_handoff_models.py)
  — literal JSON strings only; no artifact is read from disk, no environment
  value is read, no socket is opened.

The parser is strict in the Phase 4F sense: exactly one JSON object, surrounding
whitespace tolerated, and **reject rather than repair** — markdown fences, prose
before or after, arrays, strings, numbers, booleans and `null` all fail, unknown
fields are never stripped, and missing fields are never inferred.

`L1Plan` is **unchanged**. Approval, provenance, and identity are wrapper fields
(§3.2), and `ApprovedL1PlanArtifact` additionally rejects any field inside `plan`
that `L1Plan` does not declare — so a forged `plan.approval` fails the artifact
instead of being silently dropped (§3.6). No digest was added; §3.3's integrity
check remains a later phase's problem.

### 15.2 What it is not

*(Statements in this sub-section describe the tree as Phase 5B left it. Phase 5C
later added the `l2-dry-run` command, which is the first and only caller of this
package and the first code that reads an approved-plan artifact from disk — see
§16. Everything else below still holds.)*

- **Typed models and a parser only.** Phase 5B added no behavior beyond turning
  text it is handed into a validated object.
- **No CLI behavior.** No command and no option was added, and none was changed.
  The shipped surface is still exactly `version`, `inspect-issue`,
  `llm-smoke-test`, `generate-plan`, `real-llm-smoke-test`,
  `generate-model-plan`. `generate-plan` is still offline-only and
  `generate-model-plan` is unchanged. Nothing imports the `handoff` package.
- **No file loading.** There is no artifact loader. The parser takes a string;
  obtaining that string is out of scope, and no implementation code reads or
  writes an approved-plan artifact on disk.
- **No workspace access.** No target project workspace was read, listed, stat'd,
  or resolved. Path-like plan fields stay plain strings, exactly as in Phase 4B.
- **No model call, no network call, no environment read.** `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env` and
  `GitHubClient` are absent from the module's globals, and so are `os`, `socket`
  and `subprocess`.
- **No clock.** `approved_at` and `generated_at` are *parsed* when supplied and
  are never produced. There is no default timestamp and no staleness check.
- **No L2 action.** A successful parse means the artifact is well-formed and
  carries a valid approval. It authorizes nothing, because nothing consumes it.
- **No approval stamping.** The orchestrator still never writes an `approval`
  block (§3.6). No command creates one.
- **No GitHub fetch or write, no command execution, no file editing engine, no
  agent logic, and no implementer/reviewer/fixer role wiring.**

### 15.3 Acceptance criteria for Phase 5B (DONE)

- [x] Typed errors, the exact `REQUIRED_APPROVAL_TEXT` constant, the three
  models, and the strict parser exist and are exported from the `handoff`
  package.
- [x] **Approval fails closed.** A missing, null, empty, incomplete, or
  malformed `approval` block is rejected; `approval_text` must match the
  required phrase **exactly**; `approved_by` must be non-blank; `source` must be
  exactly `"manual"`; `approved_at` must parse. No approval field has a default.
- [x] **`Automation Authorization` text is not approval.** An artifact whose plan
  prose asserts automation was authorized is still rejected without a valid
  wrapper approval block.
- [x] **Identity mismatches are rejected** — wrapper vs provenance
  (`project_id`, `repo`, `issue_number`), wrapper vs plan (`repo`,
  `issue_number`), and provenance vs plan (`title`) — with exact string
  equality, no normalization.
- [x] **The plan must still be an unescalated L1 plan** —
  `automation_level == "L1"` and `requires_human_approval is True`, checked
  explicitly by the wrapper.
- [x] **`extra="forbid"` everywhere**, including a wrapper-side rejection of
  unknown fields inside `plan`. API-key-, base-URL-, prompt- and
  completion-shaped fields in provenance are rejected as extras, and
  `endpoint_host` is **rejected — never stripped** when it contains `/`, `?`,
  `#`, or `@`.
- [x] **The parser performs no IO**, verified by monkeypatching `builtins.open`,
  `os.getenv`, `os.environ.get`, `os.stat`, `os.listdir`, `os.scandir`,
  `os.path.exists`, `os.path.abspath`, `os.path.realpath`, `socket.socket`,
  `socket.create_connection`, `socket.getaddrinfo` and `subprocess.Popen` around
  both a successful parse and the failure paths.
- [x] **`L1Plan` was not modified** and carries no approval field.
- [x] **No CLI behavior added**, per §15.2.
- [x] **No target project workspace access** — `C:\dev\mis_project`,
  `C:\dev\a8_oa`, `C:\dev\bible_reading_v2`, and the `C:\dev` parent were not
  touched.
- [x] **L2 is still not built and cannot be invoked.**
- [x] **Phase 5C and every later sub-phase in §13 remain proposed and not
  authorized.** *(Phase 5C was subsequently authorized and implemented — see
  §16. Phase 5D onward are still unauthorized.)*

## 16. Phase 5C — L2 dry-run validation command (DONE)

Phase 5C added **one** command, `l2-dry-run`. It runs the §4 gate as far as this
phase is authorized to go and **prints what a future L2 would be bounded by**.
It is the analog of `generate-plan`, one level down: a read-and-report command
that changes nothing.

### 16.1 What it is

```bash
python -m ai_dev_orchestrator l2-dry-run \
  --project-config projects/my_project.yaml \
  --approved-plan path/to/approved_plan.json \
  --apply-approved-plan
```

- [cli.py](../src/ai_dev_orchestrator/cli.py) — the private helper
  `_run_l2_dry_run(...)` and the `l2-dry-run` command wrapping it. Options:
  `--project-config`, `--approved-plan`, `--apply-approved-plan`, and
  `--format json`. There is no `--model`, `--real-model`, `--body-file`,
  `--issue`, `--title`, `--github`, `--fetch`, `--workspace`, `--file`,
  `--context-file`, `--command`, `--edit`, or `--audit-dir`.
- [tests/test_cli_l2_dry_run.py](../tests/test_cli_l2_dry_run.py) — literal
  artifacts under pytest's `tmp_path` only; no environment value is read, no
  socket is opened, no command is run, and no configured workspace is touched.

**It reads exactly two files, in this order:** the `--project-config` YAML and
the `--approved-plan` artifact. Nothing else. The artifact is validated with the
Phase 5B parser `parse_approved_l1_plan_artifact`, then cross-checked against the
config for exact `project_id`, `repo`, `plan.repo`, and `plan_provenance.repo`
equality (§3.5). The issue number comes from the artifact alone — GitHub is not
contacted to confirm it.

**Gate ordering (§4.3, fail closed, cheapest first):**

1. `--apply-approved-plan` present? No → exit 1, **nothing read at all** — not
   the artifact, and not even the project config.
2. Project config loads and validates. On failure → exit 1, artifact never
   opened.
3. `--approved-plan` is not `repo.workspace_path` itself and does not sit under
   it → checked with the existing `_is_same_or_under` string/path normalization,
   **before** the artifact is read or stat'd. This is why `--approved-plan`
   carries no Typer `exists=`/`readable=` check: those would touch the path
   before the guard could run, exactly as for Phase 4L's `--body-file`.
4. The artifact is read. A missing or unreadable file → exit 1.
5. Strict parse. `ApprovedPlanParseError` and `ApprovedPlanValidationError` are
   reported **by category and by name**, and the artifact text and plan prose are
   never echoed (Phase 4L precedent).
6. Exact identity matching against the config. A mismatch names the field and
   both values, and stops.
7. Only then is the scope JSON printed to stdout.

Every failure exits non-zero, writes to **stderr only**, and prints **no stdout
JSON**. There is no partial output and no "continuing with warnings".

**Output.** One JSON object carrying: a `notice` stating no workspace was read,
no file was edited, no command was run and no implementation occurred; `mode:
"l2-dry-run"`; the project's `project_id`, `repo` and `workspace_policy` flags;
the approval's `approved_by` / `approved_at` / `source`, the plan's engine, its
`real_call` flag and model, and the issue number and title; an `intended_scope`
block copying `files_likely_to_change`, `files_forbidden_or_out_of_scope`,
`required_verification`, `proposed_steps`, `risks` and `open_questions`
**verbatim** from the approved plan snapshot, under a `note` labelling them as
plan text that was not acted on; and `next_authorization_required`.

Deliberately **not** in the output: the raw artifact text, any prompt or
completion, any API key or base URL, the configured `workspace_path`, any source
file content, and `approval_text` (it is required to equal a fixed phrase, so
echoing it adds nothing to the `approved_by`/`approved_at` pair).

### 16.2 What it is not

- **No workspace access.** The configured `repo.workspace_path` is never read,
  listed, stat'd, or resolved; nothing under it is opened; and no path named in
  `files_likely_to_change` is read, stat'd, resolved, globbed, or checked for
  existence. Plan paths remain plain strings — hints a later phase would have to
  validate, exactly as §12 requires.
- **No implementation.** Nothing is inspected, proposed, patched, edited, or
  applied. No branch, commit, or PR. No `required_verification` entry is run —
  they are carried as labelled plan text.
- **No command execution, no file editing engine, no agent logic, and no
  implementer/reviewer/fixer role wiring.**
- **No model call, no network call, no environment read.** No `AIDO_LITELLM_*`
  read, no `LLMClient` construction, no `httpx`/`requests` import in the command
  path, no socket.
- **No GitHub fetch and no GitHub write.** There is no option to reach GitHub.
- **No artifact writing and no approval stamping.** The command reads the
  artifact and never rewrites it; the orchestrator still never writes an
  `approval` block (§3.6). Approval remains a human act performed outside this
  tool.
- **No change to any other command.** `version`, `inspect-issue`,
  `llm-smoke-test`, `generate-plan`, `real-llm-smoke-test`, and
  `generate-model-plan` are untouched, and none of them gained an `--apply`,
  `--approved-plan`, or any other L2 path.
- **Not a project-level L2 opt-in.** Step 3 of §4.3 — an L2 config block, the
  analog of `real_model_planning` — is deliberately **not** implemented here:
  this command takes no L2 action, so there is nothing for a project to opt into
  yet. It belongs with the phase that first touches a workspace, and Phase 5C
  added no config field. *(Phase 5D1 is that phase, and it added
  `read_only_workspace_inspection` — see §18. `l2-dry-run` still does not read
  the block for any purpose beyond ordinary config loading.)*

### 16.3 Acceptance criteria for Phase 5C (DONE)

- [x] Exactly one new command, `l2-dry-run`, exposing `--project-config`,
  `--approved-plan`, `--apply-approved-plan`, and `--format`, and none of the
  forbidden options.
- [x] **Fails closed without `--apply-approved-plan`**, before any file is read —
  including before the project config.
- [x] **An `--approved-plan` inside `repo.workspace_path` is rejected before the
  artifact is read or stat'd**, by string/path normalization only, and its
  content never surfaces on stdout or stderr.
- [x] **A missing or unreadable artifact fails cleanly** with exit code 1 after
  the config load and the path guard.
- [x] **Parse and validation failures fail closed** with the category named, no
  stdout JSON, and no echo of artifact text or plan prose.
- [x] **Identity mismatches fail** — `project_id`, `repo`, `plan.repo`,
  `plan_provenance.repo` — with exact string equality, no case folding.
- [x] **A valid artifact prints the dry-run scope JSON**, including the notice,
  the approval metadata, the issue number and title, the intended scope copied
  from the plan, and the next-authorization statement.
- [x] **Output excludes** raw artifact text, `approval_text`, API keys, base
  URLs, `workspace_path`, and source file contents.
- [x] **Exactly two files are read on success**, in order: config, then artifact.
- [x] **No target project workspace access** — verified by tracking every path
  passed to `builtins.open`, `os.stat`, `os.listdir`, `os.scandir`,
  `os.path.exists` and `os.path.realpath`, and by detonating those entry points
  around a run. `os.path.abspath` is left working because `_is_same_or_under`
  needs it and it touches no filesystem.
- [x] **No environment read, no socket, no subprocess, no `LLMClient`, no
  `httpx`/`requests`, no `GitHubClient`.**
- [x] **No artifact writing and no approval stamping.**
- [x] **No CLI behavior changed except adding `l2-dry-run`.**
- [x] **Phase 5D and every later sub-phase in §13 remain proposed and not
  authorized.** Phase 5D is the first phase that might touch a workspace and is
  blocked on the §6.4 canonicalization work.

## 17. Phase 5D0 — canonical path guard library (DONE)

Phase 5D0 implemented the §6.4 design sketch as a **library**, and nothing else.
It exists because §6.4 decided that canonicalization must be strengthened
**before** read-only workspace inspection, not after it — so the prerequisite is
built and reviewable on its own, ahead of the phase that would use it.

**Phase 5D0 is not Phase 5D.** It performs no workspace inspection, adds no
command, and is called by nothing.

*(§17 describes the tree as Phase 5D0 left it. Phase 5D1 later became the
guard's first and only caller — see §18 — so the "called by nothing" statements
below record what shipped in 5D0, not what is true today. Everything else in
§17 still holds: the guard itself is unchanged, adds no command of its own, and
still reads no file contents and lists no directory.)*

### 17.1 What it is

- [workspace/canonical.py](../src/ai_dev_orchestrator/workspace/canonical.py) —
  the error family `CanonicalPathError` /  `CanonicalPathInputError` /
  `CanonicalPathResolutionError` / `CanonicalPathContainmentError` /
  `CanonicalPathSymlinkError` / `CanonicalPathAmbiguityError`, the frozen
  data-only `CanonicalWorkspacePath`, and the single entry point
  `canonicalize_existing_path_under_workspace(workspace_root, candidate, *,
  allow_symlinks=False)`.
- [workspace/\_\_init\_\_.py](../src/ai_dev_orchestrator/workspace/__init__.py) —
  exports those eight names alongside the existing Phase 1 path-policy names.
- [tests/test_workspace_canonical_path_guard.py](../tests/test_workspace_canonical_path_guard.py)
  — pytest `tmp_path` directories and files only.

The function proves one claim about one path: *this existing candidate is
genuinely inside this existing workspace root*. It runs in this order, cheapest
and most conservative first:

1. **Type and blank checks** on both inputs, and on `allow_symlinks`.
2. **A fail-closed lexical precheck**, before any filesystem call: UNC
   (`\\server\share\...`), extended-length (`\\?\C:\...`), device (`\\.\...`),
   any component ending in a space or a dot, and any 8.3-short-name-looking
   component (`PROGRA~1`, `LONGFI~1.TXT`) are **refused, never normalized or
   repaired**. Both separators are treated alike, so the forward-slash spellings
   are refused too. This is deliberately **conservative** and may reject strings
   that name a real file on Windows: every form here can denote the same
   location as some other string, which is exactly what makes containment
   reasoning unsound.
3. **Existence and kind checks** — `os.lstat` for existence (so a dangling
   symlink surfaces as a *symlink* decision, not a missing path), and the
   workspace root must resolve to a directory.
4. **The symlink / reparse-point policy** (§17.2).
5. **Strict canonicalization** of both paths, `Path.resolve(strict=True)`.
6. **Containment re-verification** of the resolved candidate against the
   resolved root, via `os.path.commonpath` on `os.path.normcase`-normalized
   paths — **not** a string prefix test. A sibling sharing a string prefix
   (`repo` vs `repo_evil`) is outside. A comparison that cannot be made at all —
   a drive mismatch — raises `CanonicalPathAmbiguityError` rather than being
   guessed.

A relative candidate is joined to the workspace root before resolution; an
absolute candidate is never joined and is validated against the root as given.
`relative_path` is returned relative to the resolved root. A candidate **equal
to** the workspace root is **accepted as inside**, reporting `relative_path ==
"."` — a deliberate choice, documented on the function: "inside the workspace"
and "is a file" are different questions, and a future caller that needs a file
must check the kind separately.

Inputs are not mutated, nothing is created, and nothing is deleted.

### 17.2 Symlink, junction, and reparse-point policy

With `allow_symlinks=False` (the default) the guard refuses:

- a workspace root that is itself a symlink or reparse point;
- any component between the root and the candidate that is one;
- and a candidate that is not *lexically* under the root — so a link cannot be
  used to **enter** the workspace either.

Rejection happens **before** the path is accepted, even when the link points
back inside the workspace. Note the guard never inspects components *above* the
workspace root: the root is the boundary, and walking above it would make the
check depend on the ancestors of whatever directory the operator configured.

With `allow_symlinks=True` links are followed and containment is then re-checked
against the resolved root: a link resolving outside the workspace is still
rejected, and one resolving inside may be accepted.

Detection is best-effort and platform-aware. POSIX symlinks appear in
`st_mode`. Windows junctions and directory mount points are reparse points that
`stat` follows silently and that `S_ISLNK` does not report, so
`st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT` and `st_reparse_tag` are
checked as well.

**Time of check is not time of use.** A returned decision describes the
filesystem as it was during the call. Per §6.4 a future caller must re-establish
containment immediately before each read — never cache one answer and reuse it.

### 17.3 What it is not

- **Not workspace inspection.** Phase 5D is still proposed and unauthorized.
  This module reads no file contents, lists no directory, globs nothing, and
  walks no tree. It answers one question about one path the caller already
  named.
- **No CLI behavior.** No command and no option was added, and none was changed.
  The shipped surface is exactly what Phase 5C left: `version`,
  `inspect-issue`, `llm-smoke-test`, `generate-plan`, `real-llm-smoke-test`,
  `generate-model-plan`, `l2-dry-run`. `l2-dry-run`, `generate-plan` and
  `generate-model-plan` behave identically to before.
- **Not wired in.** No shipped module imports `workspace.canonical` or calls
  `canonicalize_existing_path_under_workspace`; only the package `__init__`
  re-exports it, and a test asserts that.
- **No target workspace access by any shipped command.** Nothing under any
  configured `repo.workspace_path` was read, listed, stat'd, or resolved, and
  no path named by an approved plan was inspected.
- **Not a permission decision.** Containment is not authorization. A returned
  `CanonicalWorkspacePath` says the path is inside the root; whether the path is
  *allowed* remains `PathPolicy`'s question (§6.2), and a future caller must
  satisfy **both** gates. The lexical Phase 1 policy is unchanged and stays the
  cheap first gate.
- **No model call, no network call, no environment read, no command execution,
  no file editing, no agent logic, and no implementer/reviewer/fixer role
  wiring.** `httpx`, `requests`, `LLMClient`, `LLMClientConfig`,
  `load_llm_client_config_from_env`, `GitHubClient`, `typer`, `socket` and
  `subprocess` are absent from the module's globals.
- **No GitHub fetch and no GitHub write.**
- **No approved-plan artifact was created or modified, and no approval was
  stamped.**
- **No config change.** No new config field, and `workspace_policy.allow_symlinks`
  is **not** read by this module — `allow_symlinks` is an explicit keyword
  argument, so nothing here silently inherits a project setting. Connecting the
  two belongs to the phase that first calls the guard.

### 17.4 Acceptance criteria for Phase 5D0 (DONE)

- [x] The six-error hierarchy, the frozen data-only `CanonicalWorkspacePath`,
  and `canonicalize_existing_path_under_workspace` exist and are exported from
  the `workspace` package — those eight names and nothing else added.
- [x] **Happy paths pass**: an existing file under the workspace, an existing
  directory, a relative candidate, and an absolute candidate are all accepted;
  `relative_path` is relative and stable across spellings; and
  `resolved_candidate` is inside `resolved_workspace_root`.
- [x] **Input failures fail closed**: blank or wrongly-typed `workspace_root`
  or `candidate`, a missing workspace root, a workspace root that is a file, and
  a missing candidate.
- [x] **Escapes fail closed**: a relative candidate escaping via `..`, an
  absolute candidate outside the workspace, the workspace parent, and sibling
  prefix confusion (`repo` vs `repo_evil`) — all rejected, with and without
  `allow_symlinks`.
- [x] **Containment is commonpath-based, not prefix-based**, case handling
  follows `os.path.normcase`, and a drive mismatch fails closed as ambiguity.
  Case behavior is tested in a platform-aware way only.
- [x] **The symlink policy is tested**: a symlink inside the workspace pointing
  inside is rejected with `allow_symlinks=False` and accepted with
  `allow_symlinks=True`; one pointing outside is rejected either way; an
  intermediate directory symlink is rejected; a symlinked workspace root is
  rejected with `allow_symlinks=False`; and a dangling symlink fails closed.
  Symlink tests skip gracefully where the platform or user cannot create one.
  Windows junctions need no admin rights to create but do need a subprocess, so
  reparse-point detection is covered instead by exercising the detector against
  fabricated `st_file_attributes` / `st_reparse_tag` stat results, plus two
  end-to-end runs with `os.lstat` faked to report a reparse point on the root
  and on an intermediate component.
- [x] **Unsafe lexical forms are rejected before any disk touch** — UNC,
  extended-length, device, trailing-dot, trailing-space, and 8.3-like
  components, in both separator spellings, for both the workspace root and the
  candidate — proven by detonating `os.stat`, `os.lstat`, `Path.resolve`,
  `os.path.realpath`, `os.path.exists`, `os.listdir`, `os.scandir` and
  `builtins.open` around the call. `.` and `..` are not mistaken for
  trailing-dot components.
- [x] **No forbidden behavior**, verified by test: the forbidden names are absent
  from module globals; the happy path and the failure paths run with
  `builtins.open`, `os.getenv`, `os.environ.get`, `os.listdir`, `os.scandir`,
  `os.walk`, `os.system`, `subprocess.Popen`, `subprocess.run`,
  `socket.socket`, `socket.create_connection` and `socket.getaddrinfo` all
  detonating.
- [x] **Every path touched is under `tmp_path`**, asserted by tracking every
  argument passed to `os.lstat`, `os.stat` and `Path.resolve` during a run; and
  neither the implementation nor the test module names a real `C:\dev` project
  workspace.
- [x] **No CLI behavior changed.** Root help still lists exactly the seven
  Phase 5C commands and gains no canonicalization command; `l2-dry-run`,
  `generate-plan` and `generate-model-plan` help are unchanged and gain no
  `--allow-symlinks` or equivalent option.
- [x] **Nothing calls the guard.** Asserted across the whole package.
- [x] **Phase 5D and every later sub-phase in §13 remain proposed and not
  authorized.** Phase 5D0 satisfies the §6.4 prerequisite; it does not authorize
  the phase that would use it.

## 18. Phase 5D1 — read-only workspace metadata inspection (DONE)

Phase 5D1 added **one** command, `l2-inspect-workspace`. It is the **first
shipped code that may touch a configured target workspace**, and the touch it
makes is the smallest one available: canonicalize a path the approved plan
already named, then `stat` it.

**Phase 5D1 is not L2.** It proposes nothing, patches nothing, edits nothing,
runs nothing, and commits nothing. It is the analog of `l2-dry-run` with one
capability added — the dry run says "the plan claims it will change
`src/foo.py`"; this command says "and that path exists, is a file, and is 1,240
bytes." That is the whole difference.

### 18.1 What it is

```bash
python -m ai_dev_orchestrator l2-inspect-workspace \
  --project-config projects/my_project.yaml \
  --approved-plan path/to/approved_plan.json \
  --apply-approved-plan \
  --inspect-workspace
```

- [models.py](../src/ai_dev_orchestrator/models.py) — the new
  `ReadOnlyWorkspaceInspectionConfig` block and the
  `ProjectConfig.read_only_workspace_inspection` field, defaulting to disabled.
- [cli.py](../src/ai_dev_orchestrator/cli.py) — the private helpers
  `_run_l2_inspect_workspace(...)`, `_stat_kind_and_size(...)` and
  `_dedupe_preserving_order(...)`, and the `l2-inspect-workspace` command
  wrapping the first. Options: `--project-config`, `--approved-plan`,
  `--apply-approved-plan`, `--inspect-workspace`, and `--format json`. There is
  no `--model`, `--real-model`, `--body-file`, `--issue`, `--title`,
  `--github`, `--fetch`, `--workspace`, `--file`, `--context-file`,
  `--command`, `--edit`, `--audit-dir`, or `--allow-symlinks`.
- [projects/mis\_project.yaml.example](../projects/mis_project.yaml.example) —
  the new block, shipped **disabled**.
- [tests/test\_cli\_l2\_inspect\_workspace.py](../tests/test_cli_l2_inspect_workspace.py)
  — pytest `tmp_path` only. The "workspace" every test configures is a directory
  the test created moments earlier; no real project path is named.

This is the first caller the Phase 5D0 guard has ever had, and it remains the
only one. The Phase 1 lexical policy is unchanged and still runs first.

### 18.2 The project-level opt-in

`read_only_workspace_inspection` is the §4.3 step-3 block that Phase 5C
deliberately deferred, added now because this is the phase that first touches a
workspace and therefore the first phase with something to opt into:

```yaml
read_only_workspace_inspection:
  enabled: false
  max_inspected_files: 20
  allow_protected_paths: false
```

`enabled` defaults to `false`; an absent block is identical to a disabled one,
in the Phase 4I `real_model_planning` style. `max_inspected_files` must be
`1..100`. `allow_protected_paths` defaults to `false`. `extra="forbid"`, and the
block holds **no credentials**: no API key, no base URL, no endpoint, no model
name, and no environment-variable name. It is a separate block rather than a
reuse of `real_model_planning` for the reason §9 gives: a planning-scoped opt-in
must not silently authorize a workspace-touching capability.

No other command reads this block for any purpose beyond ordinary config
loading, and `l2-inspect-workspace` refuses to touch the workspace at all while
it is disabled — failing before the approved-plan artifact is even opened.

### 18.3 Gate ordering (fail closed, cheapest first)

Ordering *is* the safety property here, because the last step is the one that
touches another project's files.

1. `--apply-approved-plan` present? No → exit 1, **nothing read at all**.
2. `--inspect-workspace` present? No → exit 1, **nothing read at all**. Two
   flags rather than one on purpose: approving a plan and permitting a workspace
   to be examined are separate consents, and this command needs both.
3. Project config loads and validates. The first file read.
4. `read_only_workspace_inspection.enabled` is true → otherwise exit 1, with the
   artifact never opened and the workspace never touched.
5. `--approved-plan` is not `repo.workspace_path` and does not sit under it —
   the existing `_is_same_or_under` string/path check, **before** the artifact is
   read or stat'd, which is why the option carries no Typer `exists=`/`readable=`
   check.
6. The artifact is read. The second and final file read.
7. Strict Phase 5B parse. Failures are reported by category and by name; the
   artifact text and the plan prose are never echoed.
8. Exact identity matching against the config — `project_id`, `repo`,
   `plan.repo`, `plan_provenance.repo` (§3.5). This check matters more here than
   in Phase 5C: getting it wrong would mean stat'ing another project's files.
9. Candidates are taken from `plan.files_likely_to_change` **only**, exact
   duplicates dropped with order preserved. `files_forbidden_or_out_of_scope` is
   never inspected — naming a path as out of scope must not become a way to have
   it examined — and `proposed_steps`, `required_verification`, `risks`, and
   `open_questions` are prose that is never treated as a path. An empty list
   succeeds with an empty result and touches nothing. The count must not exceed
   `read_only_workspace_inspection.max_inspected_files` **or**
   `workspace_policy.max_changed_files`.
10. The lexical Phase 1 `PathPolicy.check_read` runs for **every** candidate.
    Forbidden, outside-the-workspace, traversal-escaping, and unlisted paths are
    refused always; protected paths are refused unless `allow_protected_paths`
    is true. One refusal abandons the **whole** run — a plan naming one
    forbidden path gets no partial inspection of its other paths, per §10's
    no-partial-run rule.
11. **Only now** is the workspace touched. The configured root is canonicalized
    first, which proves it exists, is a directory, and satisfies the symlink
    policy before any candidate is resolved against it. Then each candidate goes
    through `canonicalize_existing_path_under_workspace(...)` with
    `allow_symlinks=project.workspace_policy.allow_symlinks` — the connection
    §17.3 said belonged to "the phase that first calls the guard" — and, on
    success, through a single `os.stat`.

### 18.4 What is reported

One JSON object on stdout carrying: the `notice`; `mode:
"l2-inspect-workspace"`; the project's `project_id`, `repo`, `workspace_policy`
flags, and `inspection_policy` flags; the approval metadata, plan engine,
`real_call`, model, issue number and title; a `workspace_inspection` block; and
`next_authorization_required`.

Each inspected item carries `original_plan_path`, `canonical_relative_path`,
`status`, `kind` (`file` / `directory` / `other`), `size_bytes` (regular files
only), and `symlinks_allowed`. The block also carries the literal
`candidate_source`, and `file_contents_read`, `directories_listed` and
`commands_run` — all three permanently `false`, stated rather than implied.

A candidate that does not exist is reported as `status: "missing"` and the run
continues: a plan naming a file that has not been created yet is ordinary, not a
boundary violation. A containment, symlink, ambiguity, or resolution failure is
a boundary violation and stops the **whole** run with no stdout output. A `stat`
that fails after canonicalization stops the run too, except for a
`FileNotFoundError`, which is the time-of-check/time-of-use race §17.2 describes
and is recorded as `missing`.

Deliberately **not** in the output: the configured `workspace_path`, any
resolved absolute path, any file content, any directory listing, the raw
artifact text, `approval_text`, any prompt or completion, and any API key or
base URL. `required_verification` is absent too — this command did not run it,
and reprinting it here would only invite someone to.

Every failure exits non-zero, writes to **stderr only**, and prints **no stdout
JSON**.

### 18.5 What it is not

- **Not file content access.** No workspace file is opened or read. Verified by
  replacing `Path.read_text` and `builtins.open` with guards that raise for any
  workspace path while leaving the config and artifact reads working.
- **Not directory listing.** A candidate that *is* a directory is reported as
  one and its entries are never enumerated. Verified with `os.listdir`,
  `os.scandir` and `os.walk` detonating around a run that inspects a directory.
- **Not globbing or tree walking.** Candidates come from the plan, one string at
  a time. Nothing is discovered.
- **Not patch proposal, file editing, or command execution.** No diff is
  produced, no file is written, and no `required_verification` entry — or any
  other command — is run. `subprocess.Popen`, `subprocess.run` and `os.system`
  detonate during the tests.
- **Not model-backed.** No model call, no network call, no environment read, no
  `LLMClient`, no `httpx`/`requests` in the command path, no socket.
- **No GitHub fetch and no GitHub write.** There is no option to reach it.
- **No branch, commit, push, or PR.**
- **No artifact writing and no approval stamping.** The command reads the
  artifact and never rewrites it; the orchestrator still never writes an
  `approval` block (§3.6).
- **No agent logic and no implementer/reviewer/fixer role wiring.**
- **No change to any other command.** `version`, `inspect-issue`,
  `llm-smoke-test`, `generate-plan`, `real-llm-smoke-test`,
  `generate-model-plan`, and `l2-dry-run` are untouched, and none of them gained
  an `--inspect-workspace` path or any other L2 option.

### 18.6 Acceptance criteria for Phase 5D1 (DONE)

- [x] Exactly one new command, `l2-inspect-workspace`, exposing
  `--project-config`, `--approved-plan`, `--apply-approved-plan`,
  `--inspect-workspace`, and `--format`, and none of the forbidden options.
- [x] `ReadOnlyWorkspaceInspectionConfig` exists, defaults to disabled, bounds
  `max_inspected_files` to `1..100`, defaults `allow_protected_paths` to false,
  forbids extra fields, holds no secrets, and is absent-means-disabled. The
  example YAML ships it **disabled**.
- [x] **Both confirmation flags fail closed before any file is read** — not the
  artifact, and not even the project config.
- [x] **A disabled or absent config block fails before the artifact is read and
  before the workspace is touched.**
- [x] **An `--approved-plan` inside `repo.workspace_path` is rejected before the
  artifact is read or stat'd**, and its content never surfaces.
- [x] **Parse, validation, and identity failures all occur before any workspace
  touch**, verified by tracking every path passed to `os.stat`, `os.lstat`,
  `os.listdir`, `os.scandir`, `os.path.exists`, `os.path.realpath` and
  `builtins.open`.
- [x] **Candidate-count caps fail before any workspace touch**, for both
  `max_inspected_files` and `max_changed_files`.
- [x] **Lexical `PathPolicy` refusals happen before any canonicalization or
  stat** — forbidden, unlisted, traversal-escaping, absolute-outside, and
  (without `allow_protected_paths`) protected — proven by detonating `os.stat`,
  `os.lstat`, `os.listdir`, `os.scandir`, `os.walk`, `os.path.exists`,
  `os.path.realpath`, `Path.resolve` and `builtins.open` around the call. One
  refusal abandons the whole run.
- [x] **A valid run reports metadata** for existing files (kind, size, canonical
  relative path), existing directories (kind `directory`, null size, contents
  not listed), and missing paths (`status: "missing"`, run continues).
  Duplicates are deduplicated with order preserved.
- [x] **Only `files_likely_to_change` is inspected.**
  `files_forbidden_or_out_of_scope` is not, and `proposed_steps`,
  `required_verification`, `risks` and `open_questions` are never treated as
  paths — asserted by tracking every `os.stat` argument and by checking that
  path-shaped sentinels in those fields never reach stdout.
- [x] **Output omits** `workspace_path`, resolved absolute paths, file contents,
  raw artifact text, `approval_text`, prompt/completion, and any API key or base
  URL.
- [x] **The Phase 5D0 guard is used for every existing candidate**, the root is
  canonicalized first, and `workspace_policy.allow_symlinks` is passed through —
  asserted by spying on the guard. A symlink inside the workspace is rejected
  when `allow_symlinks` is false; one pointing outside is rejected even when it
  is true; and containment/symlink/ambiguity/resolution errors fail closed with
  no stdout.
- [x] **No forbidden behavior**, verified by test: workspace file contents are
  never opened or read; no directory is listed; no command is executed; no
  environment variable, socket, `LLMClient` or `GitHubClient` is reached; no
  file in the workspace or in `tmp_path` is created, modified, or deleted; and
  no artifact is written and no approval stamped.
- [x] **Tests use pytest `tmp_path` only** and name no real target workspace.
- [x] **No CLI behavior changed except adding `l2-inspect-workspace`.**
- [x] **Phase 5D2, Phase 5E, and every later sub-phase in §13 remain proposed
  and not authorized.** Reading file *contents*, proposing a patch, editing a
  file, executing a command, committing, pushing, and opening a PR all still
  require their own explicit authorization. *(Phase 5E has since been split, and
  only its first slice — Phase 5E0, the proposal artifact's models and parser,
  with no generator and no diff — has been authorized and implemented. See §19.
  Phase 5D2 — bounded, redacted file-content reads behind their own project
  opt-in — has since been authorized and implemented too; see §21. Everything
  else on this line is unchanged.)*

## 19. Phase 5E0 — patch proposal artifact models and parser (DONE)

Phase 5E0 is the **first slice** of §13's "Phase 5E — patch proposal artifact
only", and it is deliberately the slice with nothing executable in it: the
artifact's **shape**, as typed models plus a strict parser, and nothing that
produces one.

It ships `src/ai_dev_orchestrator/patch_proposal/` — `models.py` and
`__init__.py` — plus `tests/test_patch_proposal_artifact_models.py`. It is
**library only, wired into nothing**, in the Phase 4B/4F/5B/5D0 tradition.

### 19.1 What it is

- **An error hierarchy.** `PatchProposalError`, and under it
  `PatchProposalParseError` (the text was not one strict JSON object) and
  `PatchProposalValidationError` (the object failed the model). Parser and model
  errors only — there is no apply error, edit error, or command error, because
  there is no apply, edit, or command.
- **Two constants.** `PATCH_PROPOSAL_SCHEMA_VERSION = "patch-proposal.v1"` and
  `PATCH_PROPOSAL_MODE = "proposal-only"`, both enforced as `Literal` on the
  artifact. A different version is a *different artifact* and is rejected, not
  upgraded. There is one mode and it is the harmless one; adding an "apply" mode
  would be a separately authorized phase, not a new enum member.
- **`PatchProposalChange`** — one file a proposal suggests a **human** change:
  `path`, `change_type` (`"modify"` or `"create"`), `rationale`,
  `proposed_steps`, `risks`, and `requires_human_review: Literal[True]` with no
  default. `path` is validated as a **string**: relative, non-blank, no parent
  traversal, no absolute or drive-lettered form, no UNC, no extended-length or
  device prefix, no `:` (so no drive-relative form and no NTFS alternate data
  stream), no `.` or `..` component (so not `"."` either), no empty component,
  no component ending in a dot or a space, and nothing that looks like an 8.3
  short name. The check is **lexical**, mirroring the Phase 5D0 precheck's
  conservatism without importing it — nothing is joined to a workspace root,
  canonicalized, stat'd, or read to decide it.
- **`PatchProposalProvenance`** — `engine` (`"deterministic"`, `"manual"`, or
  `"model"`), `operation` (fixed to `"patch-proposal"`), `real_call`, optional
  `model`, optional `generated_at`, and the identity fields `project_id`,
  `repo`, `issue_number`, `title`. A non-model engine must carry `model: null`
  and `real_call: false` — an engine that does not call a model has no model
  name and made no call, and claiming otherwise is a contradiction rather than
  extra detail. `"model"` must name a model, but that is a **record of a claim**
  about something that happened elsewhere: parsing it calls nothing.
- **`PatchProposalArtifact`** — `schema_version`, `mode`, `provenance`, an
  **untouched `ApprovedL1PlanArtifact` snapshot**, `changes`, `omitted_paths`,
  `assumptions`, `risks`, `open_questions`, the three `Literal[False]` flags
  `file_contents_read` / `files_edited` / `commands_run`,
  `requires_human_review: Literal[True]`, and a non-blank
  `next_authorization_required`.
- **`parse_patch_proposal_artifact(text)`** — a pure strict-JSON parser.
  Surrounding whitespace is tolerated; markdown fences, prose before or after,
  arrays, strings, numbers, booleans and `null` all fail. It **rejects rather
  than repairs**: unknown fields are never stripped and missing fields are never
  inferred. Pydantic's `ValidationError` is wrapped as
  `PatchProposalValidationError`, summarized to field locations and messages so
  a failure never echoes plan prose, rationales, or provenance.

Three cross-field rules carry the safety weight:

- **The approval travels with the thing it approved.** The proposal wraps a full
  `ApprovedL1PlanArtifact`, re-validated on every parse, so a proposal cannot
  restate its own authorization — it can only carry one a human already gave.
  `automation_level == "L1"` and `requires_human_approval is True` are
  re-checked explicitly even though the wrapped model already guarantees both.
- **Exact identity matching** between `provenance` and the approved plan —
  `project_id`, `repo`, `issue_number`, and `title` against the plan's title.
  String equality only, per §3.5.
- **Scope containment: a proposal may narrow, never widen.** Every
  `changes[].path` must appear **exactly** in the plan's
  `files_likely_to_change` and must **not** appear in
  `files_forbidden_or_out_of_scope` — checked forbidden-first, so a
  self-contradicting plan is never resolved in the permissive direction.
  `omitted_paths` carry the same path-safety checks.

**Duplicate paths are rejected, not merged.** This was a deliberate choice: two
changes for one file have no defined precedence, and silently keeping one would
discard work a human was meant to read.

### 19.2 Why there is no diff

The central shape decision is that `PatchProposalChange` carries a *rationale*
and *prose steps* and has **no field for a unified diff**, a hunk, a patch, an
edit script, a command, before/after content, or any other applyable payload.
That is not an omission to be filled in later by adding a key — a payload
carrying one is rejected as an extra field, at every model level.

Two reasons. First, a real diff requires reading file **contents**, which is
Phase 5D2 and is not authorized; a proposal artifact that could carry one would
quietly create demand for that read. Second, an artifact with nothing applyable
in it cannot be applied by mistake: there is no payload for a future bug, a
future command, or a confused operator to feed to a patch tool.

The three `Literal[False]` flags work the same way. In Phase 5E0 they are not
*observations* — they are the **shape of a legal artifact**. Nothing in this
repository can produce a proposal for which any of them would be true, so a
payload claiming one is describing something this phase does not do, and it is
rejected.

### 19.3 What it is not

- **Not patch generation.** There is no generator, deterministic or otherwise.
  Nothing here produces a proposal; a parsed one was written elsewhere.
- **Not a diff.** See §19.2.
- **Not file editing, not command execution.** Nothing is applied, run, or
  written.
- **No file contents read.** No source text, excerpt, or command output has a
  field here, and the parser opens nothing.
- **No workspace access.** No target project workspace is read, listed, stat'd,
  or resolved. Paths are strings, validated lexically, never canonicalized.
- **No file loading.** The parser is handed a string; there is no loader.
- **No CLI behavior.** No command, no option, and nothing in `cli.py` changed or
  imports the package.
- **No model, network, or environment access.** `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `os`, `pathlib`, `socket` and `subprocess` are not
  imported, so no code path can reach any of them.
- **No clock.** `generated_at` is parsed when supplied and never produced.
- **No approval stamping.** Nothing writes an approved-plan artifact or creates
  an approval; the wrapped one is re-validated, never authored.
- **Not authorization.** A parsed proposal is data describing suggested work.
  L2 remains unbuilt, and nothing consumes this.

### 19.4 Acceptance criteria for Phase 5E0 (DONE)

- [x] `PatchProposalError` / `PatchProposalParseError` /
  `PatchProposalValidationError` exist, share one base, and cover parsing and
  validation only.
- [x] `PATCH_PROPOSAL_SCHEMA_VERSION` and `PATCH_PROPOSAL_MODE` exist and are
  enforced exactly — a near-miss version or mode is rejected, and neither has a
  default.
- [x] A valid artifact parses, carries an **unchanged** `ApprovedL1PlanArtifact`
  snapshot, and may have **empty** `changes` (meaning "no patch proposed yet").
  One `modify` change and one `create` change each parse.
- [x] `provenance` identity must match the approved plan exactly on
  `project_id`, `repo`, `issue_number`, and `title`; matching is not normalized.
- [x] `provenance` rejects `endpoint_host`, `base_url`, `api_key`, `prompt`,
  `completion`, `messages`, `raw_response` and `workspace_path` as extras, and
  the rejection never echoes what the field held.
- [x] `"deterministic"` and `"manual"` require `real_call: false` and
  `model: null`; `"model"` requires a non-blank model name and still performs no
  model call — asserted with `socket` and `os.getenv` detonated.
- [x] Every `changes[].path` must be exactly one of the plan's
  `files_likely_to_change`; a path in `files_forbidden_or_out_of_scope` is
  rejected even when the plan also lists it as likely to change.
- [x] **Duplicate change paths are rejected**, deliberately, and documented.
- [x] Unsafe paths are rejected for both `changes[].path` and `omitted_paths`:
  blank, absolute, drive-lettered, parent traversal, UNC, extended-length,
  device, `:`-bearing, trailing dot, trailing space, 8.3-like, `"."`, `"./x"`,
  and empty components — refused **lexically**, with `os.stat`,
  `os.path.realpath` and `builtins.open` detonated.
- [x] `rationale` non-blank, `proposed_steps` non-empty and non-blank, `risks`
  entries non-blank, `requires_human_review` true with no default.
- [x] `file_contents_read`, `files_edited` and `commands_run` are rejected when
  true and have no defaults; `requires_human_review` false is rejected;
  `next_authorization_required` is required and non-blank.
- [x] **Extra fields are rejected at every model level**, including
  diff/patch/hunk/edit, file-content, before/after, command and command-output,
  prompt/completion, API-key/base-URL, `workspace_path`, raw-artifact-text, and
  a top-level `approval`. No such field exists on any model.
- [x] The parser accepts surrounding whitespace and rejects empty text, invalid
  JSON, markdown-fenced JSON, prose before or after the object, and JSON arrays,
  strings, numbers, booleans and `null`.
- [x] **The parser performs no file, network, process, environment or workspace
  IO**, on both success and failure paths, verified by detonating
  `builtins.open`, `os.getenv`, `os.environ.get`, `os.stat`, `os.lstat`,
  `os.listdir`, `os.scandir`, `os.walk`, `os.path.exists`, `os.path.abspath`,
  `os.path.realpath`, `socket.socket`, `socket.create_connection`,
  `socket.getaddrinfo` and `subprocess.Popen`. It prints nothing and writes no
  file.
- [x] The implementation module's globals contain none of `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `Path`, `os`, `socket`, `subprocess`.
- [x] The package exports exactly the nine Phase 5E0 names, and no generator,
  applier, loader, or implementer.
- [x] **No CLI behavior added.** Root help still lists exactly `version`,
  `inspect-issue`, `llm-smoke-test`, `generate-plan`, `real-llm-smoke-test`,
  `generate-model-plan`, `l2-dry-run`, `l2-inspect-workspace`; `cli.py` is
  unchanged and does not import the package; and `l2-inspect-workspace`,
  `l2-dry-run`, `generate-plan` and `generate-model-plan` keep their exact
  options. *(Phase 5E1 has since added a ninth command,
  `generate-patch-proposal`, which imports the package lazily inside its own
  body. Nothing else in this list changed. See §20.)*
- [x] **No forbidden behavior**: no workspace access, no file contents read, no
  patch generated, no file edited, no command executed, no GitHub fetch or
  write, no model or network or environment access, no agent logic or role
  wiring, no approved-plan artifact written, and no approval stamped.
- [x] **Phase 5D2, Phase 5E1, Phase 5E2, and every later sub-phase in §13 remain
  proposed and not authorized.** Generating a proposal, carrying a real diff,
  reading file contents, editing a file, executing a command, committing,
  pushing, and opening a PR all still require their own explicit authorization.
  *(Phase 5E1 — generating a proposal, deterministically and offline, with no
  diff and no file contents — has since been authorized and implemented. See
  §20. So has Phase 5D2 — bounded, redacted file-content reads printed to
  stdout, still with no diff and no edits; see §21. So has Phase 5E2 — typing a
  diff-bearing artifact and parsing it, with no generator and no applier; see
  §22. Everything else on this line is unchanged.)*

## 20. Phase 5E1 — deterministic patch proposal generator (DONE)

Phase 5E0 shipped the proposal artifact's shape and deliberately no producer.
Phase 5E1 is the producer, and it is deliberately the dullest one that could
exist.

It ships `src/ai_dev_orchestrator/patch_proposal/generator.py`, the one new CLI
command `generate-patch-proposal`, and
`tests/test_patch_proposal_generator.py` plus
`tests/test_cli_generate_patch_proposal.py`.

### 20.1 What it is

- **`build_deterministic_patch_proposal(*, approved_plan, project)`** — a
  **pure function** over two already-loaded objects, an `ApprovedL1PlanArtifact`
  and a `ProjectConfig`, returning a validated `PatchProposalArtifact`. No file
  IO, no workspace access, no environment read, no model, no network, no
  GitHub, no clock, no command, no file edit, no diff, and no artifact file
  written. It prints nothing.
- **`PatchProposalGenerationError`** — one error, for an identity mismatch, a
  self-contradicting plan, a candidate count above the cap, or a failure of the
  Phase 5E0 artifact validation. There is deliberately **no apply error, edit
  error, or command error**, because there is no apply, no edit, and no command.
  Its messages name the failed field and the category and never echo the
  artifact text, the plan prose, or any supplied value.
- **`generate-patch-proposal`** — exactly one new command, with exactly five
  options: `--project-config`, `--approved-plan`, `--apply-approved-plan`,
  `--generate-proposal`, and `--format json`. There is no `--output`, no
  `--model`, no `--real-model`, no `--diff`, no `--apply-patch`, no
  `--read-contents`, no `--inspect-workspace`, no `--command`, no `--edit`, and
  no `--github`.

**What it proposes.** Candidates come from the approved plan's
`files_likely_to_change` and **nowhere else**. Exact duplicates are deduplicated
preserving order; `files_forbidden_or_out_of_scope` is never a candidate source;
and `proposed_steps`, `required_verification`, `risks` and `open_questions` are
prose that is never read as a path. Each surviving path becomes one `modify`
change carrying a fixed rationale, two prose review steps, one risk, and
`requires_human_review: true`. An empty `files_likely_to_change` produces a
valid artifact with `changes: []` and an assumption saying so — a well-formed
statement about a plan, not a defect.

**Determinism is a property, not a nicety.** The same inputs produce a
byte-identical artifact, which is why `generated_at` is `None` and why every
rationale, step, assumption and risk is fixed prose. A generator that stamped a
timestamp would be impossible to diff or re-verify.

**The generated provenance describes the generator, not its input.** `engine:
"deterministic"`, `real_call: false`, `model: null` — facts about this function.
The wrapped plan's own provenance may well record a real model call; that claim
stays inside the untouched snapshot and is never promoted to the proposal.

### 20.2 How it fails closed

In order, before anything is produced: exact identity matching of
`project_id`, `repo`, `plan.repo` and `plan_provenance.repo` against the project
config (string equality only — no normalization, no case folding, no prefix
matching, per §3.5); a re-check that the plan is `automation_level == "L1"` with
`requires_human_approval is True`, even though `ApprovedL1PlanArtifact`
guarantees both; refusal of a plan that lists a path as **both** likely-to-change
and forbidden, rather than resolving the contradiction in the permissive
direction; and the `workspace_policy.max_changed_files` cap on distinct
candidates.

The artifact is then assembled and handed to `PatchProposalArtifact` validation
rather than constructed field by field, so an unsafe path, an out-of-scope path,
a duplicate, or an identity slip is caught by the **same** rules that guard a
proposal arriving from outside this repository. The generator gets no privileged
path around them.

The command's gate ordering mirrors `l2-dry-run`'s with one more consent in
front: `--apply-approved-plan` and `--generate-proposal` both first — with **no
file read at all** if either is missing — then the project config, then a
string/path check rejecting an `--approved-plan` inside the configured workspace
**before** the artifact is opened or stat'd, then the strict Phase 5B parse,
then the generator. Any failure exits non-zero with stderr only and nothing on
stdout.

### 20.3 What it is not

- **Not a diff.** §19.2 applies unchanged. `PatchProposalChange` still has no
  field for a unified diff, a hunk, a patch, an edit script, before/after
  content, a command, or command output, so the generator has nothing applyable
  to emit.
- **No file contents read.** Nothing is opened, which is exactly why
  `change_type` is always `"modify"`: telling "create" from "modify" would need
  workspace metadata this phase does not gather. That limit is recorded as an
  *assumption in the artifact* rather than guessed at.
- **No workspace access.** No target project workspace is read, listed, stat'd,
  globbed, walked, or resolved. Paths stay strings and are never joined to a
  workspace root or canonicalized; the Phase 5D0 guard is not called.
- **No artifact file written.** The command prints to **stdout only**, with no
  wrapper around the artifact, so its output parses with
  `parse_patch_proposal_artifact`. There is no `--output` option.
- **Not file editing, not command execution.** Nothing is applied, run, or
  written. `required_verification` travels inside the embedded plan snapshot as
  the plan prose it always was, and is never executed.
- **No model, network, environment, or GitHub access.** `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `Path`, `os`, `socket` and `subprocess` are not
  importable in the generator module.
- **No agent logic, no role wiring, no approval stamping.** The approval inside
  the wrapped `ApprovedL1PlanArtifact` travels through unchanged and is
  re-validated, never authored.
- **Not authorization.** A generated proposal is data describing suggested work.
  L2 remains unbuilt.

### 20.4 Acceptance criteria for Phase 5E1 (DONE)

- [x] `build_deterministic_patch_proposal` is a pure keyword-only function over
  an `ApprovedL1PlanArtifact` and a `ProjectConfig`, and returns a
  `PatchProposalArtifact` that round-trips through
  `parse_patch_proposal_artifact`.
- [x] The wrapped approved-plan snapshot travels through **unchanged**, and the
  input object is not mutated.
- [x] Generation is **deterministic**: the same inputs produce byte-identical
  JSON.
- [x] One path yields one `modify` change; multiple paths preserve order;
  duplicates are deduplicated preserving first position; an empty
  `files_likely_to_change` yields `changes: []` plus an explanatory assumption.
- [x] `files_forbidden_or_out_of_scope` is never proposed, and `proposed_steps`,
  `required_verification`, `risks` and `open_questions` are never treated as
  paths.
- [x] Fails closed on: a path listed as both likely and forbidden, an unsafe
  path, more distinct paths than `workspace_policy.max_changed_files`, and a
  `project_id` or `repo` mismatch (including a case-folded repo).
- [x] Generated provenance is `engine: "deterministic"`, `real_call: false`,
  `model: null`, `generated_at: null`, and does not inherit the wrapped plan's
  real-model claim.
- [x] `file_contents_read`, `files_edited` and `commands_run` are all false;
  `requires_human_review` is true; `next_authorization_required` names Phase
  5D2/5E2 and the actions still unauthorized.
- [x] No diff, content, or command field exists on the artifact or on any
  change, and each change carries exactly `path`, `change_type`, `rationale`,
  `proposed_steps`, `risks`, `requires_human_review`.
- [x] **The generator performs no file, environment, network, process, or
  workspace IO**, on both success and failure paths, verified by detonating
  `builtins.open`, `os.getenv`, `os.environ.get`, `os.stat`, `os.listdir`,
  `os.scandir`, `os.walk`, `os.path.exists`, `os.path.abspath`,
  `os.path.realpath`, `socket.*` and `subprocess.*`. It prints nothing and
  writes no file.
- [x] The generator module's globals contain none of `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `Path`, `os`, `socket`, `subprocess`, and the CLI
  helper's source names none of them either.
- [x] `generate-patch-proposal` appears in root help alongside the eight
  existing commands; its help exposes only `--project-config`,
  `--approved-plan`, `--apply-approved-plan`, `--generate-proposal`,
  `--format` and `--help`, and rejects `--output`, `--model`, `--real-model`,
  `--diff`, `--apply-patch`, `--read-contents`, `--inspect-workspace`,
  `--command`, `--edit`, `--body-file`, `--issue`, `--title`, `--github`,
  `--fetch`, `--workspace`, `--file`, `--context-file` and `--audit-dir`.
- [x] A missing `--apply-approved-plan` or `--generate-proposal` fails **before
  any file is read** — not the artifact, and not even the config — with stderr
  only and empty stdout.
- [x] An `--approved-plan` inside the configured workspace is rejected **before
  it is read or stat'd**, and only the config had been read at that point.
- [x] An invalid approved artifact fails before generation; an identity
  mismatch, a self-contradicting plan, an over-cap path count and an unsafe path
  all fail closed with empty stdout and without echoing plan prose or the
  approval text.
- [x] The command reads **exactly two files**, both named on the command line,
  config first.
- [x] Stdout is the artifact itself with no wrapper and parses with
  `parse_patch_proposal_artifact`; it omits `workspace_path`, absolute paths,
  raw artifact text, API keys and base URLs, source contents, diffs and command
  output. `approval_text` appears only inside the embedded snapshot.
- [x] **No CLI behavior changed except adding `generate-patch-proposal`.**
  `l2-inspect-workspace`, `l2-dry-run`, `generate-plan`, `generate-model-plan`
  and `real-llm-smoke-test` keep their exact options, and no other command
  gained `--generate-proposal`, `--diff`, or `--apply-patch`.
- [x] **No forbidden behavior**: no workspace access, no file contents read, no
  diff generated, no file edited, no command executed, no GitHub fetch or write,
  no model / network / environment access, no agent logic or role wiring, no
  artifact file written, and no approval stamped.
- [x] **Tests use pytest `tmp_path` and literal data only**, and name no real
  target workspace.
- [x] **Phase 5D2, Phase 5E2, and every later sub-phase in §13 remain proposed
  and not authorized.** Reading file contents, carrying a real diff, editing a
  file, executing a command, committing, pushing, and opening a PR all still
  require their own explicit authorization. *(Phase 5D2 — bounded, redacted
  file-content reads — has since been authorized and implemented; see §21. It
  supplies the reads Phase 5E2 would need and authorizes none of the rest. Phase
  5E2 has since been implemented as **models and a parser only** — a diff may
  now be carried and validated as data, but still not generated, modified, or
  applied; see §22.)*

## 21. Phase 5D2 — bounded read-only file-content inspection (DONE)

Phase 5D1 shipped the first command that may *touch* a target workspace. Phase
5D2 adds **one** command, `l2-read-workspace-files`, and it is the first phase
whose **output may contain that workspace's source**.

That is the whole of the increase, and it is deliberately treated as a bigger
step than it looks. §18 draws the line between "does `src/foo/bar.py` exist and
how big is it" and "what does `src/foo/bar.py` say"; this phase crosses it, and
so it re-runs every Phase 5D1 gate, adds a second consent flag and a **separate**
project opt-in in front of them, bounds the read three ways, and redacts
everything it prints.

**Phase 5D2 is not L2.** It proposes nothing, diffs nothing, patches nothing,
edits nothing, runs nothing, and calls no model. It ships
`tests/test_cli_l2_read_workspace_files.py`, a new config block, and no new
module.

### 21.1 What it is

- **`l2-read-workspace-files`** — exactly one new command, with exactly five
  options: `--project-config`, `--approved-plan`, `--apply-approved-plan`,
  `--read-contents`, and `--format json`. There is no `--output`, no `--model`,
  no `--real-model`, no `--diff`, no `--apply-patch`, no `--generate-proposal`,
  no `--inspect-workspace`, no `--workspace`, no `--file`, no `--command`, no
  `--edit`, no `--run`, no `--verify`, and no `--github`.
- **`ReadOnlyWorkspaceContentConfig`** — a project-level opt-in block,
  `read_only_workspace_content`, holding `enabled` (default false), `max_files`
  (default 10, ≤ 50), `max_file_bytes` (default 50 000, ≤ 1 000 000),
  `max_total_bytes` (default 200 000, ≤ 5 000 000), and `allow_protected_paths`
  (default false). `extra="forbid"`; no credential, endpoint, model name, or
  environment-variable name may appear in it. An absent block is identical to a
  disabled one, and the shipped example config ships it **disabled**.

**It is a separate opt-in from Phase 5D1's on purpose.** A project that has
agreed to have its path names stat'd has not thereby agreed to have its source
printed. `read_only_workspace_inspection.enabled: true` grants nothing here, and
this command refuses to touch the workspace at all until
`read_only_workspace_content.enabled` is true — failing before the approved-plan
artifact is even opened.

**What it reads.** Candidates come from the approved plan's
`files_likely_to_change` and **nowhere else**. Exact duplicates are deduplicated
preserving order; `files_forbidden_or_out_of_scope` is never read — naming a
path as out of scope must not become a way to have it printed — and
`proposed_steps`, `required_verification`, `risks` and `open_questions` are
prose that is never treated as a path. An empty `files_likely_to_change`
succeeds with `items: []` and an explanatory note, and the workspace is not
touched at all.

**How the read is bounded.** Three caps, each enforced separately: at most
`max_files` distinct candidates (checked *before* the workspace is touched); at
most `max_file_bytes` for any single file; and at most `max_total_bytes` across
the whole invocation. The per-file cap is enforced at the read itself — the
helper asks for `limit + 1` bytes and refuses anything longer — so a file that
grew between the `stat` and the open is still refused rather than slurped
whole.

**Redaction is mandatory.** Every byte that reaches stdout passes through
`_redact_secret_like_text`, which blanks `Bearer <token>`, `key = value` pairs
for `api_key`/`apikey`/`token`/`secret`/`password`/`passwd`/`pwd`, and
OpenAI-style `sk-…` strings. It is deliberately three simple deterministic
patterns and **does not claim to be reliable secret detection** — the output
says as much, reports `redacted`, `redaction_count` and `redaction_kinds`, and
there is **no configuration option and no flag that turns redaction off**.

### 21.2 How it fails closed

Before the workspace is touched at all, in order: `--apply-approved-plan`, then
`--read-contents` (a plain invocation missing either reads **no file at all** —
not the artifact, and not even the config); then the project config; then
`read_only_workspace_content.enabled`; then a string/path check rejecting an
`--approved-plan` inside the configured workspace **before** it is read or
stat'd; then the artifact read; then the strict Phase 5B parse; then exact
`project_id`/`repo`/`plan.repo`/`plan_provenance.repo` matching against the
config; then the `max_files` and `max_changed_files` candidate caps; then the
lexical Phase 1 path policy for **every** candidate, with forbidden, outside and
unlisted paths always refused and protected paths refused unless
`allow_protected_paths` is true. One refused candidate abandons the whole run —
a plan naming one forbidden path does not get the contents of its other paths
printed.

Only then is the workspace touched, root first, through the Phase 5D0 guard
honoring `workspace_policy.allow_symlinks`. Per candidate the outcomes split
into two kinds. **Reportable, run continues:** `missing`,
`directory_no_content`, `other_no_content`, `too_large`, `skipped_total_limit`,
`binary_or_non_utf8` — each with a null `content_text` and `bytes_read: 0`.
**Fatal, whole run abandoned with empty stdout:** any containment, symlink,
ambiguity or resolution failure from the guard, and any read error after the
`stat` other than a `FileNotFoundError` race, which is recorded as `missing`.

Every failure exits non-zero with stderr only, prints no stdout JSON, and never
echoes the artifact text, the plan prose, the approval text, or any file
content.

### 21.3 What it is not

- **Not directory listing.** `os.listdir`, `os.scandir` and `os.walk` are never
  called, and no glob or tree walk exists. A candidate that *is* a directory is
  reported as `directory_no_content`; its entries are neither enumerated nor
  named.
- **Not diff generation.** Nothing produces a unified diff, a hunk, a patch, or
  a before/after pair, and no item carries a field that could hold one.
- **Not file editing, not command execution.** Nothing is written, applied, or
  run. `required_verification` is not output and not executed.
- **Not model-backed, and not a path to a model.** No `LLMClient`, no `httpx`,
  no socket, no environment read. The content this command reads goes to stdout
  and nowhere else; **file content is never sent to a model.**
- **Not full L2.** It creates no branch, no commit, no PR, writes no artifact
  file, stamps no approval, and adds no agent logic or implementer/reviewer/
  fixer role wiring.
- **Not authorization.** Printing what a file says is not permission to change
  it. L2 remains unbuilt.

### 21.4 Output shape

Stdout is one JSON object: a `notice`, `mode: "l2-read-workspace-files"`, the
`project` block (identity, `workspace_policy`, and the `content_policy` caps
including `redaction: "mandatory_basic_secret_like_redaction"`), the
`approved_plan` provenance summary, a `workspace_content` block, and
`next_authorization_required`.

`workspace_content` carries the note, `candidate_source`, the four false flags
`directories_listed` / `commands_run` / `model_called` / `diffs_generated` /
`files_edited`, `file_contents_read: true`, `total_bytes_read`, and `items`.
Deliberately absent everywhere: the configured `workspace_path`, any resolved
absolute path, any directory listing, any diff, any command or command output,
the raw artifact text, `approval_text`, `required_verification`, any prompt or
completion, and any API key or base URL. **File content appears in exactly one
place** — `workspace_content.items[].content_text` — after the byte caps and
after redaction.

### 21.5 Acceptance criteria for Phase 5D2 (DONE)

- [x] `l2-read-workspace-files` appears in root help alongside the nine existing
  commands; its help exposes only `--project-config`, `--approved-plan`,
  `--apply-approved-plan`, `--read-contents`, `--format` and `--help`, and
  rejects `--output`, `--model`, `--real-model`, `--body-file`, `--issue`,
  `--title`, `--github`, `--fetch`, `--workspace`, `--file`, `--context-file`,
  `--command`, `--edit`, `--audit-dir`, `--inspect-workspace`,
  `--generate-proposal`, `--diff`, `--apply-patch`, `--run` and `--verify`.
- [x] `read_only_workspace_content` defaults to disabled when absent, rejects
  unknown fields, and rejects out-of-range or non-integer caps. The shipped
  example config carries the block **explicitly disabled**.
- [x] A missing `--apply-approved-plan` or `--read-contents` fails **before any
  file is read** — not the artifact, and not even the config — with stderr only
  and empty stdout, with every filesystem entry point detonated.
- [x] A disabled or absent config block fails **before the artifact read and
  before any workspace touch**, and Phase 5D1's opt-in does not substitute for
  it.
- [x] An `--approved-plan` inside the configured workspace is rejected **before
  it is read or stat'd**, with only the config read at that point.
- [x] Artifact parse failure, artifact validation failure, identity mismatch,
  and both candidate caps each fail **before any workspace touch**.
- [x] Lexical path-policy refusals — forbidden, unlisted, escaping, absolute-
  outside, and protected without `allow_protected_paths` — happen **before any
  canonicalization, stat, or open**, and one refusal abandons the whole run.
- [x] An existing small UTF-8 file under an allowed path reports `read` with its
  `content_text`; multiple files preserve plan order; duplicates are
  deduplicated preserving first position; an empty candidate list succeeds
  without touching the workspace.
- [x] `missing`, `directory_no_content`, `too_large`, `skipped_total_limit` and
  `binary_or_non_utf8` are each reported with a null `content_text` and
  `bytes_read: 0`, and the run continues. A NUL byte and invalid UTF-8 are both
  refused, and neither file's bytes appear in the output.
- [x] Only `files_likely_to_change` is read: `files_forbidden_or_out_of_scope`
  and the prose fields are never opened and never printed, verified with real
  files present at those paths.
- [x] Redaction blanks Bearer tokens, `api_key`/`token`/`secret`/`password`/
  `passwd`/`pwd` assignment values (including underscore-prefixed names) and
  `sk-…` keys, reports `redacted`, `redaction_count` and `redaction_kinds`, and
  **cannot be disabled** by any config field or flag.
- [x] The Phase 5D0 guard is used for every candidate, the root is proven first,
  `workspace_policy.allow_symlinks` is passed through, a symlink inside the
  workspace is rejected when symlinks are disallowed, one pointing outside is
  rejected even when they are allowed, and containment/symlink/ambiguity/
  resolution failures fail closed with empty stdout.
- [x] **No forbidden behavior**: no directory listed (`os.listdir`,
  `os.scandir`, `os.walk` detonated), no command executed (`subprocess.Popen`,
  `subprocess.run`, `os.system` detonated), no environment/network/model access
  (`os.getenv`, `os.environ.get`, `socket.*`, `LLMClient`,
  `load_llm_client_config_from_env` detonated), no GitHub access
  (`GitHubClient.__init__`/`get_issue` detonated), no diff generated, no file
  edited (workspace and tmp bytes snapshotted before and after), no artifact
  written and no approval stamped.
- [x] The command reads **exactly** the config, the artifact, and the approved
  candidate files — the first two as text in that order, the candidates as
  bytes through one bounded helper — and the command's source names none of
  `httpx`, `requests`, `LLMClient`, `load_llm_client_config_from_env`,
  `GitHubClient`, `subprocess`, `os.environ`, `getenv`, `difflib`,
  `unified_diff`, `apply_patch`, `git commit`, `git push`, or any write call.
- [x] Output omits `workspace_path`, resolved absolute paths, raw artifact text,
  `approval_text`, `required_verification`, diffs, command output and
  credentials; file content appears only under `items[].content_text`.
- [x] **No CLI behavior changed except adding `l2-read-workspace-files`.**
  `generate-patch-proposal`, `l2-inspect-workspace`, `l2-dry-run`,
  `generate-plan` and `generate-model-plan` keep their exact options, and no
  other command gained `--read-contents`.
- [x] **Tests use pytest `tmp_path` only**, and name no real target workspace.
- [x] **Phase 5E2 and every later sub-phase in §13 remain proposed and not
  authorized.** Generating a diff, editing a file, executing a command,
  committing, pushing, opening a PR, and sending source contents to a model all
  still require their own explicit authorization. *(Phase 5E2 — typing a
  diff-bearing artifact and parsing it, with no generator and no applier — has
  since been authorized and implemented as §22. It authorizes none of the
  actions above.)*

## 22. Phase 5E2 — unified diff proposal artifact models and parser (DONE)

Phase 5E0 typed a proposal that deliberately carried **prose only**. Its
`PatchProposalChange` had a `rationale` and `proposed_steps` and no field a diff
could live in, because a real diff meant reading file contents, which was
unauthorized then. Phase 5D2 has since shipped bounded, redacted content reads
behind their own project opt-in and two explicit flags.

Phase 5E2 is the next step and is deliberately the inert half of it: it lets a
unified-diff-shaped artifact **exist as data** and be validated. It ships
`ai_dev_orchestrator.diff_proposal` — `DiffProposalFileChange`,
`DiffProposalProvenance`, `DiffProposalArtifact`, the three-error hierarchy, and
`parse_diff_proposal_artifact` — and **nothing else**.

**Phase 5E2 is not diff generation, and not diff application.** There is no
generator here and no applier. Nothing produces a diff, modifies one, applies
one, or asks whether one would apply — a parsed diff was written by something
outside this repository, and the producer is Phase 5E3, which is proposed and not
authorized.

### 22.1 What the artifact carries, and what it refuses to carry

The wrapper is Phase 5E0's, one field wider:

- an **untouched** `ApprovedL1PlanArtifact` snapshot, re-validated on every parse
  and matched **exactly** on `project_id`, `repo`, `issue_number` and `title`;
- an **optional, untouched** Phase 5E0 `PatchProposalArtifact` snapshot — the
  prose proposal the diffs were drafted from. When present, its approved plan
  must match this one by `model_dump`, its identity must match, and no diff may
  name a path the prose proposal did not (unless it named none at all, which
  means "no paths chosen yet", not "no paths permitted");
- `changes`, each carrying a **`unified_diff`**;
- the same scope containment as 5E0: every `changes[].path` **exactly** in
  `files_likely_to_change`, never in `files_forbidden_or_out_of_scope`, no
  duplicates (rejected, never merged), and the same conservative lexical path
  safety on every path string;
- flags describing what did and did not happen: `diffs_generated` is
  `Literal[True]`, `files_edited` / `commands_run` / `applies_cleanly_checked`
  are `Literal[False]` with no defaults, and `source_contents_read` is a plain
  `bool` because a producer plausibly *did* read contents to draft a diff — the
  parser records that **claim** and reads nothing itself.

The `unified_diff` string may contain source lines as diff context. That is what
a diff is, and it is allowed **as data in this artifact**. It arrived in the text
handed to the parser; nothing here opened a file to obtain it and nothing here
sends it anywhere. There is deliberately **no** separate `before_content`,
`after_content`, `file_contents` or `source_contents` field: source text lives
inside the diff or nowhere. There is likewise no `command`, `command_output`,
`apply`, `auto_apply`, `workspace_path`, `prompt`, `completion`, `api_key`,
`base_url`, `approval`, or `raw_artifact_text` field, and every model is
`extra="forbid"`, so a payload carrying one is **rejected**, not stored.

### 22.2 What "a valid diff" means here — shape, never applicability

The accepted shape is the narrowest thing that is still a real diff:

```
--- a/<path>        (or '--- /dev/null' when change_type is 'create')
+++ b/<path>
@@ ... @@
...
```

Exactly one `---` line and one `+++` line, the second immediately after the
first, both equal to the expected header **exactly** — no timestamp suffix, no
`a/`-less form, no substituted path — followed by at least one `@@` hunk header.
`change_type` is `modify` or `create` only.

Refused outright, as substrings anywhere in the payload: `GIT binary patch`,
`Binary files `, `rename from `, `rename to `, `similarity index `,
`delete file mode`, `old mode `, `new mode `, and `diff --git`. The first two are
not reviewable text; the next four move or destroy a path, and a path the plan
listed as changeable is not thereby a path it authorized removing; mode changes
are invisible in a reviewed diff body; and `diff --git` is the *envelope* that
carries all of them and that multi-file patches are built from. A multi-file
patch therefore fails on the header count, and so — conservatively, on purpose —
does a diff whose body happens to contain a line starting with `--- ` or `+++ `.
A NUL byte is refused, and the payload is capped at 200 000 characters.

**Applicability is never checked.** Whether the hunk counts are arithmetically
consistent, whether the context matches any real file, and whether the diff would
apply are all questions this phase does not ask, because the last two require
touching a workspace. No patch tooling is invoked, `difflib` is not imported, and
line endings inside a diff are **not normalized** — the string is carried through
byte for byte.

### 22.3 Acceptance criteria for Phase 5E2 (DONE)

- [x] A valid artifact parses; a `modify` diff and a `create` diff each parse;
  an artifact with **empty** `changes` parses ("no diff proposed yet" is
  well-formed); surrounding whitespace is tolerated.
- [x] The wrapped `ApprovedL1PlanArtifact` round-trips unchanged, and the
  optional `PatchProposalArtifact` snapshot may be absent, null, or present —
  and when present must match by `model_dump` and by identity.
- [x] `schema_version` is exactly `diff-proposal.v1` and `mode` exactly
  `proposal-only`; `diffs_generated` must be true; `files_edited`,
  `commands_run` and `applies_cleanly_checked` must be false; each has no
  default; `requires_human_review` must be true; `next_authorization_required`
  is required and non-blank.
- [x] Provenance identity must match the approved plan exactly, `operation` is
  `diff-proposal` only, non-model engines carry no model and no real call, a
  `model` engine must name one — and parsing it **calls nothing**, with sockets
  and the environment detonated. `generated_at` is parsed, never produced.
- [x] Provenance rejects `endpoint_host`, `base_url`, `api_key`, `prompt`,
  `completion`, `messages`, `raw_response` and `workspace_path` as extras, and
  the rejection never echoes what they held.
- [x] Scope containment holds: paths outside `files_likely_to_change` are
  rejected, forbidden paths are rejected (and forbidden wins over a
  self-contradicting plan), duplicates are rejected, and a diff for a path the
  wrapped patch proposal did not name is rejected.
- [x] The full unsafe-path set — blank, absolute, drive-lettered, colon/ADS,
  traversal, UNC, extended-length, device, trailing dot, trailing space,
  8.3-like, `.`, `./x`, doubled separator — is refused for `changes[].path` and
  `omitted_paths`, lexically, even when the plan itself lists the unsafe path.
- [x] Diff shape is enforced: exact `--- a/<path>` / `+++ b/<path>` for
  `modify`, exact `--- /dev/null` / `+++ b/<path>` for `create`, mismatched or
  unsafe header paths rejected, missing `---` / `+++` / `@@` rejected, headers
  out of order rejected, multi-file rejected, `diff --git` rejected, binary /
  rename / delete / mode metadata rejected, NUL rejected, over-long rejected.
- [x] **No apply check is performed**: an arithmetically nonsense diff whose
  context matches nothing parses fine, with `subprocess` and `open` detonated.
  Line endings and source lines are carried through verbatim.
- [x] Artifact-level and change-level payload extras are rejected —
  `raw_artifact_text`, `source_contents`, `file_contents`, `before_content`,
  `after_content`, `command`, `commands`, `command_output`, `prompt`,
  `completion`, `api_key`, `base_url`, `workspace_path`, `approval`, `apply`,
  `auto_apply` — and no rejection echoes the value.
- [x] The parser rejects empty text, invalid JSON, markdown-fenced JSON (both a
  JSON fence and a `diff` fence), prose before or after, and JSON arrays /
  strings / numbers / booleans / `null`; it wraps `ValidationError` as
  `DiffProposalValidationError`, never repairs, never strips unknown fields, is
  deterministic, and **prints nothing**.
- [x] **The parser performs no IO**: `builtins.open`, `os.getenv`,
  `os.environ.get`, `os.stat`, `os.lstat`, `os.listdir`, `os.scandir`,
  `os.walk`, `os.path.exists/abspath/realpath`, `socket.*`, `subprocess.run`
  and `subprocess.Popen` are all detonated across a successful parse and across
  failure paths, and no file is written.
- [x] The implementation module's globals contain none of `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `Path`, `os`, `socket`, `subprocess`, `yaml`,
  `difflib`, and its source names no transport, CLI, workspace, or clock import.
- [x] The package exports exactly the nine Phase 5E2 names, and no generator, no
  applier, no loader, and no writer.
- [x] **No CLI behavior added.** Importing `diff_proposal` registers no command;
  `l2-read-workspace-files`, `generate-patch-proposal`, `l2-inspect-workspace`,
  `l2-dry-run`, `generate-plan` and `generate-model-plan` keep their exact
  options and gain no `--diff`, `--diff-proposal`, `--apply-patch`,
  `--edit-files` or `--implement`. *(Phase 5E3 has since added an eleventh
  command, `generate-diff-proposal`, which produces this artifact and prints it;
  it changed none of the ten above — see §23.)*
- [x] **Tests use literal dicts and hand-typed diffs only** — no real file, no
  real environment, no network, no target workspace created or named.
- [x] **Phase 5E3 and every later sub-phase in §13 remain proposed and not
  authorized.** Generating a diff, applying one, editing a file, executing a
  command, committing, pushing, opening a PR, and sending source contents to a
  model all still require their own explicit authorization. *(Phase 5E3 —
  generating a diff, deterministically and offline, from local JSON inputs, with
  nothing applied and no workspace read — has since been authorized and
  implemented; see §23. Applying a diff, editing a file, executing a command,
  committing, pushing, opening a PR, and sending source contents to a model all
  still require their own explicit authorization.)*

## 23. Phase 5E3 — deterministic diff proposal generator (DONE)

Phase 5E2 typed the diff proposal artifact and shipped no producer. Phase 5E3 is
that producer, and it is deliberately the dullest one that could exist:
`build_deterministic_diff_proposal`, a **pure function over four already-loaded
objects** that runs `difflib` over strings and returns a validated
`DiffProposalArtifact`, plus the `generate-diff-proposal` command that loads
those four objects from local files and prints the result.

The four inputs are the whole story, and **none of them is a workspace**:

1. an `ApprovedL1PlanArtifact` — the human approval and the path scope;
2. a `ProjectConfig` — the identity the approval must match;
3. a **Phase 5D2 workspace-content packet** — JSON a human previously printed
   with `l2-read-workspace-files`, carrying bounded, redacted original file text
   as *data*;
4. a **proposed-content input** (`proposed-content.v1`, mode `proposal-only`) —
   the final text a human or an external tool wants each file to have.

### 23.1 What it does, and the four things it deliberately cannot do

It generates diff text and **does nothing with it**. In particular:

- **It does not read target workspace files.** Original text arrives inside the
  packet or the generation for that path fails. The paths the approved plan
  names are never opened, stat'd, listed, globbed, walked, or resolved, and no
  path is joined to a workspace root or canonicalized.
- **It does not apply a diff, and it does not check whether one applies.** No
  patch tooling is invoked and nothing is staged. `applies_cleanly_checked` is
  `false` because the question was never asked — asking it means touching the
  workspace this phase refuses to touch.
- **It does not edit files, run commands, or call a model.** `httpx`,
  `requests`, `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `Path`, `os`, `socket` and `subprocess` are absent
  from the generator module's globals, so no code path there can reach one.
  `required_verification` is plan prose that is never executed.
- **It does not write an artifact file.** stdout only, with no wrapper, so the
  output parses with `parse_diff_proposal_artifact`. Nothing stamps an approval:
  the wrapped `ApprovedL1PlanArtifact` travels through unchanged.

`generated_at` is `None` and every assumption and risk is fixed prose, so the
same inputs always produce a byte-identical artifact. Provenance is
`engine="deterministic"`, `real_call=false`, `model=null` — facts about the
function, not claims copied from an input — and `patch_proposal` is always
`null`: these diffs were drafted from a content packet, not from a Phase 5E0
prose proposal.

### 23.2 Where it fails closed

Scope narrows and never widens: every proposed path must appear **exactly** in
`files_likely_to_change`, must **not** appear in `files_forbidden_or_out_of_scope`
(checked first, so a self-contradicting plan resolves restrictively), and must
appear in the packet. Identity is matched with exact string equality against
both the project config and the packet — `project_id`, `repo`, `issue_number`,
`title` — and the L1 invariants are re-checked rather than assumed.

The interesting refusals are the ones about *source text*:

- **Redacted source is refused.** Phase 5D2 replaces secret-like values with a
  placeholder, so a diff built from redacted text describes a file that does not
  exist. A misleading patch is worse than no patch.
- **A `modify` whose packet item is not a successfully read regular file** —
  missing, a directory, too large, skipped by the total cap, binary — is refused
  rather than guessed at, and so is a read item carrying no `content_text`.
- **A `create` whose path was actually read is refused**: this phase does not
  overwrite an existing file under the name "create". A `create` with empty
  content is refused too, because no hunk can express it and silently dropping
  it would misreport the proposal.
- **A generated diff matching a secret-like pattern is refused, not redacted.**
  The Phase 5D2 regexes are reused **detection-only**: redacting a diff would
  produce text that reads like a patch and could never apply. The error names
  the category and the path and never echoes the value or the diff.

A `modify` whose proposed text already matches the recorded original produces no
diff at all: the path goes into `omitted_paths` rather than being emitted as a
fabricated one. `changes` may therefore be **empty**, which is well-formed.
Because the artifact is validated through the Phase 5E2 model rather than
constructed field by field, a generated diff that would not parse — the awkward
case being a source line beginning `--` or `++`, which prefixes into something
that reads like a second file header — is discarded rather than emitted.

### 23.3 The command's gate ordering

`generate-diff-proposal` takes `--project-config`, `--approved-plan`,
`--workspace-content`, `--proposed-content`, the two consent flags
`--apply-approved-plan` and `--generate-diff`, and `--format`. It fails closed in
order: **both flags first** (without either, *nothing* is read, not even the
config), then the config, then a string/path check rejecting **any** of the
three inputs that sits inside the configured `repo.workspace_path` — checked for
all three together, **before any of them is opened**, which is why none carries a
Typer `exists=`/`readable=` check — then the strict Phase 5B parse, then the
packet, then the proposed content, then generation. Any failure exits non-zero
with stderr only and nothing on stdout, and never echoes the artifact text, the
plan prose, the proposed content, any file content, any diff text, or any
secret-like value.

### 23.4 Acceptance criteria for Phase 5E3 (DONE)

- [x] A valid `modify` and a valid `create` each generate a
  `DiffProposalArtifact`, and the generated artifact re-parses with
  `parse_diff_proposal_artifact`. Generation is byte-for-byte deterministic.
- [x] The wrapped `ApprovedL1PlanArtifact` travels through unchanged, and the
  input object is not mutated.
- [x] A no-op `modify` is reported in `omitted_paths`, never emitted as a
  fabricated diff; an empty proposed-content input yields `changes == []`;
  multiple changes preserve the input's order.
- [x] Duplicate proposed paths, paths outside `files_likely_to_change`, paths in
  `files_forbidden_or_out_of_scope`, and paths absent from the packet are all
  rejected. Plan prose is never read as a path.
- [x] A `modify` requires a packet item with status `read`, kind `file`, a
  non-null `content_text` and `redacted == false`; **a redacted source fails
  closed**. A `create` requires status `missing`, and a `create` over a read
  item fails closed. `too_large`, `binary_or_non_utf8`, `directory_no_content`,
  `other_no_content` and `skipped_total_limit` items cannot be changed.
- [x] Identity mismatches fail on `project_id`, `repo`, `issue_number` and
  `title`, against both the config and the packet, by exact string equality, and
  the message names the field without echoing the values.
- [x] Provenance is `deterministic` / `diff-proposal` / `real_call=false` /
  `model=null` / `generated_at=null`; `source_contents_read` reflects whether
  recorded original content was consulted; `diffs_generated` is true and
  `files_edited`, `commands_run` and `applies_cleanly_checked` are false.
- [x] **No apply-cleanliness check is performed**, with `builtins.open`,
  `subprocess` and the `os` filesystem entry points detonated across a
  successful generation.
- [x] A secret-like generated diff fails closed and the message never echoes the
  value or the diff.
- [x] Both input parsers reject empty text, invalid JSON, markdown fences, prose
  around the object, and non-object JSON; the proposed-content models reject
  unsafe paths, duplicates, oversized or NUL-bearing content, and every
  forbidden extra (`unified_diff`, `diff`, `command`, `apply`, `workspace_path`,
  `before_content`/`after_content`, `approval`, `prompt`, `completion`,
  `api_key`, `base_url`, `command_output`); the packet parser rejects a wrong
  `mode` or `candidate_source`, a broken identity, duplicates, unknown item
  statuses, unsafe item paths, and unexpected item fields.
- [x] **The generator performs no IO**: no file, environment, network, or
  process access on the success path or on any failure path, and no file is
  written. The plan's paths are never opened.
- [x] The command reads **exactly the four files named on its command line**, in
  order, and fails before reading anything when a flag is missing, before
  reading any input when one of the three sits inside the workspace, and before
  reading the next input when an earlier one is invalid.
- [x] stdout is the artifact with no wrapper and carries no `workspace_path`, no
  absolute path, no raw input text, no API key or base URL, no command output,
  and no apply result; source text appears only as diff context inside the
  generated diffs, and `approval_text` only inside the embedded plan snapshot.
- [x] **No CLI behavior changed except the added command.**
  `l2-read-workspace-files`, `generate-patch-proposal`, `l2-inspect-workspace`,
  `l2-dry-run`, `generate-plan` and `generate-model-plan` keep their exact
  options, and none gains `--generate-diff` or `--proposed-content`.
- [x] **Tests use pytest `tmp_path` and literal JSON only** — no real
  environment, no network, no target workspace read, and no real `C:\dev` path.
- [x] **Phase 5F and every later sub-phase in §13 remain proposed and not
  authorized. Phase 5F is the first phase that could edit a file.** Applying a
  diff, editing a file, executing a command, committing, pushing, opening a PR,
  and sending source contents to a model all still require their own explicit
  authorization. *(Phase 5F0 — typing the human approval a write would have to
  pass — has since been implemented as **models and a parser only**; see §24.
  Nothing edits a file.)*

## 24. Phase 5F0 — file-edit write gate models and parser (DONE)

Phase 5E3 produces a concrete `DiffProposalArtifact` deterministically and
offline, and prints it. Nobody has read it. Phase 5F0 types the **explicit human
approval** that any future file-editing phase would have to be handed before it
could write a single byte into a target workspace — and ships nothing that
writes.

**Phase 5F0 is file-edit write gate models and a strict parser only.** It is
**not** file editing, **not** diff application, **not** apply-cleanliness
checking, **not** command execution, **not** model-backed L2, and **not** L2. It
is a library: `src/ai_dev_orchestrator/file_editing/`, wired into no command.

### 24.1 Why a second approval exists

Phase 5B's `REQUIRED_APPROVAL_TEXT` records that a human approved an **L1 plan**
for L2 implementation. That is an approval of *intent* — a summary, a scope, a
list of files that may change. It is not an approval of the **concrete diff**
Phase 5E3 later generated from that plan, which the human had not seen when they
approved the plan.

So Phase 5F0 introduces a second, differently worded sentence:

```
REQUIRED_DIFF_EDIT_APPROVAL_TEXT = "I approve this diff proposal for workspace file editing"
```

It is compared with `==`. A paraphrase, a case variant, padded whitespace,
trailing punctuation, and the Phase 5B plan sentence are all **not** approval.

The orchestrator must never infer this approval from:

- the approved L1 plan artifact wrapped inside the proposal — a different
  approval of a different thing, re-validated here and never reused;
- the diff proposal artifact existing, parsing, or setting
  `requires_human_review`, which *requests* review and never records that it
  happened;
- a file being present on disk;
- issue prose or an `Automation Authorization` heading, which anyone who can
  edit an issue can write;
- model output of any kind.

Nothing in this phase stamps an approval. Writing the block **is** the approval
act, and it is a human's.

### 24.2 What the artifact carries, and what it refuses to carry

`ApprovedDiffProposalArtifact` is `schema_version`
(`"approved-diff-proposal.v1"`), `mode` (`"file-edit-approval-only"`),
`approval` (a `DiffEditApproval`), `diff_proposal` (an **untouched** Phase 5E2
snapshot), `project_id`, `repo`, `issue_number`, `title`, and
`next_authorization_required`. Every model is `extra="forbid"`.

Identity is matched **exactly**, in both directions — against
`diff_proposal.provenance` and against `diff_proposal.approved_plan` (whose
title lives on `.plan.title`). String equality only; no normalization, no case
folding. The failure this prevents is an approval given for one issue being
carried into another.

Every invariant the proposal already guarantees is **re-checked here**: the plan
is still `automation_level == "L1"` with `requires_human_approval` true; the
proposal still has `requires_human_review` true and `diffs_generated` true, with
`files_edited`, `commands_run` and `applies_cleanly_checked` all false; no
duplicate `changes[].path`; every path exactly inside `files_likely_to_change`
and none inside `files_forbidden_or_out_of_scope`. A write gate must not inherit
its safety from a model it does not own, and pydantic does not re-validate a
model instance it is handed — so an object mutated or hand-built after
validation reaches the gate, and the gate checks it again. An optional wrapped
patch proposal keeps Phase 5E2's consistency rules unchanged and unloosened.

`diff_proposal.changes` may be **empty**: a human may approve a proposal that
proposes nothing, in which case a future apply phase would have nothing to edit.
That is well-formed, and it authorizes no write.

There is **no field** for raw artifact text, source contents outside a diff,
`before_content`/`after_content`, a prompt, a completion, an API key, a base
URL, a workspace path, a command or its output, an apply result, `auto_apply`, a
branch name, a commit id, or a PR URL. Each is rejected as an extra. Source text
appears only as diff context inside the wrapped diffs.

**This model does not prove a diff applies** — `applies_cleanly_checked` must
still be false, because nobody asked. It does not authorize command execution,
and it does not authorize commits, pushes, or PRs. It records a human approval
that a future, separately authorized file-editing phase may consider, and no
such phase exists.

### 24.3 Acceptance criteria for Phase 5F0 (DONE)

- [x] A valid artifact parses into `ApprovedDiffProposalArtifact`, carries a
  `DiffEditApproval`, and carries the wrapped `DiffProposalArtifact` snapshot
  unchanged. It may wrap a `modify` diff, a `create` diff, or empty changes.
  Surrounding whitespace is accepted; the three constants are the exact strings
  above; the three error types share one base.
- [x] The approval block is required; `approved_by` must be non-blank,
  `approved_at` parseable, `source` `"manual"` only, and `approval_text` an
  exact match. Lowercase variants, a trailing period, padded whitespace,
  paraphrases, `"I approve this L1 plan for L2 implementation"` and
  `"Automation Authorization: approved"` are all rejected, as are missing
  fields, extra fields, and `model`/`automatic`/`github`/`issue` sources.
- [x] **Approval is never inferred** — not from the wrapped L1 plan approval
  (which is valid and approves something else), not from
  `diff_proposal.requires_human_review`, and not from a file being present.
  There is no loader, no writer, and nothing that stamps an approval.
- [x] Wrapper `project_id`/`repo`/`issue_number`/`title` must match the
  proposal's provenance **and** its nested approved plan exactly; case
  differences are rejected. `repo` must look like `owner/repo`, `issue_number`
  must be positive, and `project_id`, `title` and `next_authorization_required`
  must be non-blank. `schema_version` and `mode` are exact.
- [x] `diff_proposal` is required, a malformed one is rejected through nested
  validation, and every proposal invariant is re-checked — through JSON **and**
  on a mutated object handed in directly: the flags, the L1 level and human
  approval requirement, duplicate paths, out-of-scope paths, and forbidden
  paths. A positive control proves the direct-construction path itself works.
- [x] Every forbidden artifact-level extra is rejected (`raw_artifact_text`,
  `source_contents`, `file_contents`, `before_content`/`after_content`,
  `command`/`commands`/`command_output`, `prompt`, `completion`, `api_key`,
  `base_url`, `workspace_path`, `apply`/`auto_apply`, `branch`, `commit`,
  `push`, `pr_url`), as is every forbidden approval-level extra
  (`endpoint_host`, `base_url`, `api_key`, `prompt`, `completion`, `messages`,
  `raw_response`, `workspace_path`). No apply/edit/command/git field exists on
  either model, and error messages never echo the diff, the approval text, or a
  secret-like value.
- [x] The parser accepts surrounding whitespace and rejects empty text, invalid
  JSON, markdown fences, prose before or after the object, non-object JSON, and
  non-string input. It wraps `ValidationError`, never repairs, never strips
  unknown fields, never infers missing ones, prints nothing, and is
  deterministic.
- [x] **The parser performs no IO** — no file, environment, network, or process
  access on the success path or on any failure path, and no file is written. The
  implementation module's globals contain none of `httpx`, `requests`,
  `LLMClient`, `LLMClientConfig`, `load_llm_client_config_from_env`,
  `GitHubClient`, `typer`, `Path`, `os`, `socket`, `subprocess`, `difflib`.
- [x] The package exports exactly the nine Phase 5F0 names and no editor,
  applier, loader, writer, runner, or git helper.
- [x] **No CLI behavior added.** Root help still lists exactly the eleven Phase
  5E3 commands; importing `file_editing` adds none; `generate-diff-proposal`,
  `l2-read-workspace-files`, `generate-patch-proposal`, `l2-inspect-workspace`,
  `l2-dry-run`, `generate-plan` and `generate-model-plan` keep their exact
  options and none gains an approve/apply/edit flag. No workspace access, no
  GitHub fetch or write, no command execution, no file editing, no branch,
  commit, push or PR, no agent logic, no implementer/reviewer/fixer role wiring,
  no artifact writing, and no approval stamping.
- [x] **Tests use literal dicts and JSON only** — no real environment, no
  network, no target workspace read, and no real `C:\dev` path.
- [x] **Phase 5F1 and every later sub-phase in §13 remain proposed and not
  authorized.** Phase 5F1 may add a separately gated **dry-run apply plan**, but
  **not file editing** unless explicitly authorized. Applying a diff, editing a
  file, executing a command, committing, pushing, opening a PR, and sending
  source contents to a model all still require their own explicit authorization.
  *(Phase 5F1 — the dry-run file-edit preview — has since been authorized and
  shipped; see §25. It is a preview and still edits nothing.)*

## 25. Phase 5F1 — dry-run file-edit preview command (DONE)

Phase 5F0 typed the human approval a future file-editing phase would have to be
handed, and shipped nothing that consumes it. Phase 5F1 is the first consumer:
it validates one Phase 5F0 approved diff proposal against a project config and
the **lexical** Phase 1 write policy, and prints what a future write phase
*would be allowed to attempt*.

**Phase 5F1 is a dry-run preview only.** It is **not** file editing, **not**
diff application, **not** apply-cleanliness checking, **not** command execution,
**not** model-backed L2, and **not** L2. It adds one library helper —
`build_file_edit_preview` in `src/ai_dev_orchestrator/file_editing/preview.py` —
and **one** command, `l2-preview-file-edits`.

```
python -m ai_dev_orchestrator l2-preview-file-edits ^
  --project-config projects\my_project.yaml ^
  --approved-diff-proposal path\to\approved_diff_proposal.json ^
  --apply-approved-plan ^
  --preview-file-edits
```

### 25.1 What it establishes, and what it deliberately leaves unknown

Three things, and no more:

1. the Phase 5F0 approval is a **real, exactly-worded file-edit approval** of one
   concrete diff proposal — established by `ApprovedDiffProposalArtifact`
   validation, **never inferred** from the wrapped L1 plan approval, from the
   diff proposal existing or parsing, from `requires_human_review`, from a file
   being present, from issue prose, or from model output;
2. the artifact is **this project's**, matched by exact string equality in all
   six places it records identity — `project_id` and `repo` on the wrapper, on
   `diff_proposal.provenance`, and on `diff_proposal.approved_plan`;
3. every path the approved diff names passes the **lexical** Phase 1
   `PathPolicy.check_write` check, no path is duplicated, and the change count
   fits inside `workspace_policy.max_changed_files`.

What it leaves unknown is everything that would require looking at the
workspace: whether any of those paths exists, what it currently contains,
whether its canonical form resolves back inside the workspace root, and whether
the diff would apply. Those questions are unanswered **because answering them
means touching a target workspace**, and this phase does not. The report says so
in `checks_not_performed`, `canonicalization_checked` included — a path that
passes the lexical policy could still resolve, on a real filesystem, somewhere
the policy would refuse.

### 25.2 Fail-closed rules

- **Protected paths are refused outright.** Phase 5F1 ships no
  `--allow-protected` flag: permitting a protected write is a decision for a
  phase that actually writes, made with its own authorization.
- **One refused path fails the whole preview.** A forbidden, unlisted,
  traversal-escaping, or protected path produces stderr and a non-zero exit,
  never a report with a `"denied"` row. `policy_result` is
  `Literal["allowed"]` with no other member, so a report either describes a
  fully permitted change set or does not exist — a partially permitted preview
  would be an invitation to apply the permitted part.
- **Duplicate paths are re-checked** even though both upstream models reject
  them, because pydantic does not re-validate an instance it is handed.
- **Empty changes are valid.** `paths_count` is 0 and a future phase would
  attempt no write. That is a well-formed statement, not a defect and not a
  loophole.

### 25.3 What the report carries, and what it refuses to carry

`FileEditPreviewReport` is `schema_version` (`"file-edit-preview.v1"`), `mode`
(`"dry-run-preview-only"`), `project`, `approved_diff`, `preview`,
`checks_performed`, `checks_not_performed`, the four `Literal[False]` flags
`files_edited` / `commands_run` / `applies_cleanly_checked` /
`workspace_touched`, `requires_future_authorization` (`Literal[True]`), and
`next_authorization_required`. Every model is `extra="forbid"`.

A diff is summarized as **counts** — `diff_bytes_utf8`, `diff_lines`,
`hunk_count`, `added_lines`, `removed_lines`, `context_lines` — computed by
scanning the string the artifact already carried. `difflib` is not imported: no
diff is generated, modified, normalized, or checked for applicability, and the
`--- ` / `+++ ` file headers are excluded from the added and removed counts.

There is **no field** for unified diff text, source contents, an approval text,
raw artifact text, a workspace path, a resolved absolute path, a command or its
output, an apply result, an API key, a base URL, a prompt, a completion, a
branch, a commit, or a PR URL. Each is rejected as an extra. The only
branch/commit/push/PR mentions anywhere in the output are the `false` flags in
`checks_not_performed` recording that none of them happened.

### 25.4 Gate ordering (fail closed, cheapest first)

1. `--apply-approved-plan` — missing, and **nothing is read at all**, not even
   the config.
2. `--preview-file-edits` — a second, separate consent, also before any read.
3. The project config loads. **First file read.**
4. `--approved-diff-proposal` is rejected if it is, or sits under, the
   configured `repo.workspace_path` — by the existing `_is_same_or_under`
   string/path guard, **before** the artifact is read or stat'd.
5. The artifact is read. **Second and final file read.**
6. `parse_approved_diff_proposal_artifact` parses it strictly.
7. `build_file_edit_preview` runs: identity, count, uniqueness, path policy.
8. The report is printed to stdout, with no wrapper.

Any failure exits non-zero with stderr only and nothing on stdout, and never
echoes the artifact text, the approval text, any diff, or any file content.

### 25.5 Acceptance criteria for Phase 5F1 (DONE)

- [x] `build_file_edit_preview` is a **pure function over two already-loaded
  objects**: no file IO, no workspace access, no environment read, no model, no
  network, no GitHub, no subprocess, no clock, no command execution, no file
  editing, no patch application, no apply-cleanliness check, and no artifact
  file writing. It is deterministic.
- [x] A valid approved diff with a `modify` change, one with a `create` change,
  and one with **empty** changes all produce a valid `FileEditPreviewReport`;
  multiple changes preserve input order; `omitted_paths` is carried through.
- [x] Identity is matched against the project config with **exact string
  equality** in all six places, in both directions, and case differences are
  rejected. A mutated provenance or nested-plan identity is caught.
- [x] Duplicate paths are rejected even when the nested object was mutated after
  validation; a change count above `workspace_policy.max_changed_files` is
  rejected; a count of zero succeeds, including under a cap of zero.
- [x] The Phase 1 `PathPolicy` **write** check is the one that runs, with
  `allow_protected` left at its fail-closed default. Forbidden, unlisted and
  **protected** paths are refused, one refusal fails the whole preview, and an
  allowed path yields `policy_result: "allowed"` with `protected_path: false`.
- [x] Diff statistics are computed correctly, headers are excluded from the
  added/removed counts, hunks are counted, bytes are UTF-8 bytes, and nothing is
  normalized. No `unified_diff` text and no source content appears in the report.
- [x] `files_edited`, `commands_run`, `applies_cleanly_checked` and
  `workspace_touched` are false; `requires_future_authorization` is true; and
  `checks_performed` / `checks_not_performed` are accurate and complete.
- [x] **No canonicalization, stat, open, listdir, scandir, walk, realpath, or
  abspath touches a workspace** on the success path or on any failure path, and
  no file is written.
- [x] The command appears in root help, exposes exactly `--project-config`,
  `--approved-diff-proposal`, `--apply-approved-plan`, `--preview-file-edits`,
  `--format` and `--help`, and exposes none of the forbidden options
  (`--output`, `--model`, `--real-model`, `--body-file`, `--issue`, `--title`,
  `--github`, `--fetch`, `--workspace`, `--file`, `--context-file`,
  `--command`, `--edit`, `--audit-dir`, `--inspect-workspace`,
  `--read-contents`, `--generate-proposal`, `--generate-diff`, `--apply-patch`,
  `--apply-diff`, `--write-files`, `--run`, `--verify`, `--branch`, `--commit`,
  `--push`, `--pr`, `--open-pr`).
- [x] Missing `--apply-approved-plan` or `--preview-file-edits` fails before any
  file read; an artifact inside the configured workspace is rejected before it
  is read; an invalid artifact fails after the config read and before the
  preview; identity and policy failures fail with stderr only and no stdout.
- [x] stdout is the report itself with no wrapper, and omits the unified diff,
  source contents, raw artifact text, approval text, workspace path, absolute
  resolved paths, command output, apply results, and any branch/commit/push/PR
  claim or executable command instruction.
- [x] **No CLI behavior changed except adding `l2-preview-file-edits`.**
  `generate-diff-proposal`, `l2-read-workspace-files`,
  `generate-patch-proposal`, `l2-inspect-workspace`, `l2-dry-run`,
  `generate-plan` and `generate-model-plan` keep their exact options. No
  workspace access, no GitHub fetch or write, no command execution, no file
  editing, no branch, commit, push or PR, no agent logic, no
  implementer/reviewer/fixer role wiring, no artifact writing, and no approval
  stamping.
- [x] **Tests use literal dicts, literal JSON, and pytest `tmp_path` only** — no
  real environment, no network, no target workspace read, and no real `C:\dev`
  path.
- [x] **Phase 5F2 / Phase 5F and every later sub-phase in §13 remain proposed and
  not authorized.** A preview describes a hypothetical; it authorizes nothing.
  The first real workspace write may be added only under its own explicit
  authorization, as may applying a diff, checking whether one applies, executing
  a command, committing, pushing, opening a PR, and sending source contents to a
  model. *(Phase 5F2A — the first-workspace-write safety design — has since been
  authorized and completed as a **design-only** phase; see §26. It implemented
  nothing. Of the write phases it describes, now split as 5F2B through 5F2F,
  only **5F2B** has since been authorized and completed, as a **library-only**
  path guard that writes nothing; 5F2C through 5F2F are still proposed and not
  authorized.)*

## 26. Phase 5F2A — first workspace write safety design (DONE)

Phase 5F1 prints what a future write phase *would be allowed to attempt*. It
answers three questions and deliberately leaves every filesystem question
unanswered. Phase 5F2A is the phase that answers them **on paper**, so that the
first phase which actually writes a byte into a target workspace arrives with a
contract that was reviewed before it was coded.

**Phase 5F2A is design only.** It implements **nothing**. It adds no module, no
function, no model, no config field, no test of runtime behavior, no CLI command
and no CLI option. It does not edit a file, apply a diff, check whether a diff
applies, execute a subprocess, run `git`, read, list, stat, resolve, or
canonicalize a target workspace, call a model, open a socket, read an
environment variable, fetch from or write to GitHub, create a branch, commit,
push, or PR, write an artifact file, or stamp an approval. **Nothing shipped in
this repository edits a target file, and L2 is still not built.**

Everything below describes phases that are **PROPOSED and NOT AUTHORIZED**. The
word "the writer" throughout means *a hypothetical future first-write phase*,
not code that exists. Where this section uses "must", it is stating a
requirement that a future phase would have to satisfy in order to be
authorizable — not a description of present behavior.

### 26.1 The dirty-tree / no-command-execution conflict, and its resolution

**The conflict, stated plainly.** Two commitments in this document contradict
each other as written:

- §6.2, §10 and the §13 roadmap entry all require the first write phase to
  **enforce a dirty working tree check**. The stated reason (§10) is that a
  dirty tree makes "what did the AI change?" unanswerable, which defeats the
  human review the whole project is built around.
- The same §13 entry, and §7 in full, state that the first write phase performs
  **no command execution**, and §7 defers command execution to a *later* phase
  than file editing on purpose.

`git status` is a command. Running it would be command execution, performed by
the very phase that promised not to execute commands, against a target
workspace, with a working directory inside that workspace, using an executable
resolved from `PATH`. That is not a small carve-out: `git` is a program that
reads repository configuration (`core.fsmonitor`, `core.hooksPath`, `core.pager`,
alias definitions) which is itself content inside the workspace, and which a
sufficiently unlucky or hostile repository can use to run further programs. A
"just one command" exception is the exact shape of escalation §7 exists to
prevent, and §12 names under "command execution escalation".

The conflict is therefore **real**, and it is resolved here rather than papered
over. In particular this document does **not** quietly assume `git status` is
allowed, and it does not delete the dirty-tree requirement to make the
no-execution promise easier to keep.

**The three candidate directions were:**

- **(a) A non-subprocess Git-state mechanism.** Determine cleanliness by reading
  the repository's own on-disk state — `.git/HEAD`, `.git/index`, and the
  working tree — in-process, with no child process and no `git` binary. Either a
  purpose-built minimal reader or an existing pure-Python Git library
  (`dulwich` is the obvious candidate).
- **(b) Move enforcement into a separately authorized prerequisite phase.** The
  write phase does not implement any Git-state mechanism; it *consumes* one that
  a prior, separately reviewed, read-only phase already shipped.
- **(c) Something else equally fail-closed** — for example, refusing to write
  unless the operator supplies an out-of-band attestation.

**Decision: (a) implemented inside (b).** The mechanism is a non-subprocess
Git-state probe, and it ships as its **own separately authorized, read-only
prerequisite phase** (5F2D in §26.12) rather than as a side effect of the phase
that writes. Two independent reasons:

1. The no-command-execution promise is preserved **verbatim**. No subprocess, no
   `git` executable, no shell, no `PATH` lookup, no repository-controlled
   configuration deciding what runs. §7 remains intact and command execution
   remains deferred to a later, separate authorization.
2. A Git-state reader is a non-trivial piece of code whose failure mode is
   *fail-open* — a subtly wrong index comparison reports "clean" for a dirty
   tree, and the write proceeds when it should not. Code with that failure mode
   must be reviewable **on its own**, with its own tests, before anything
   depends on it. Bundling it into the first-write phase would mean reviewing
   the riskiest new capability and the subtlest new correctness problem in one
   sitting.

**The verdict is tri-state and fails closed.** The probe reports exactly one of
`clean`, `dirty`, or `undetermined`. `undetermined` is treated **identically to
`dirty`**: the write is refused. Every condition the probe cannot decide
correctly resolves to `undetermined` — an unparseable or unknown-version index,
a `.git` file rather than a directory (worktrees and submodules), a sparse
checkout, a split index, an unmerged/conflicted stage, an unresolved
`core.autocrlf` or clean/smudge filter that changes what "unchanged" means, an
unreadable path, a symlink where a regular file was expected, a missing `.git`
entirely, or anything the reader has not been explicitly written to handle. The
probe never guesses in the permissive direction, and there is no flag that
converts `undetermined` into permission.

**A non-git workspace is not a special case.** If the configured workspace is
not a Git repository, the verdict is `undetermined` and the write is refused.
Writing into a directory with no version control is precisely the situation in
which "what did the AI change?" is least answerable. This document does not
authorize and does not design an exception; see §26.13.

**Human attestation is explicitly rejected as a substitute.** A flag such as
`--i-attest-the-tree-is-clean` would be a fail-open control: it converts a
verifiable fact into an unverifiable claim, it is the single easiest thing for a
hurried operator to pass habitually, and unlike the §3.6 and §24.1 approval
sentences it asserts a property of the *world* rather than a *decision by the
human*. An approval sentence is unforgeable-by-accident because only a human can
mean it; an attestation about a working tree is simply an assertion that may be
false, and the writer has no way to tell. So:

- Attestation **may not** replace the check, and this document declines to
  justify a security tradeoff in which it does.
- Attestation **may** be required *in addition*: a future phase may decide that
  a `clean` verdict is necessary but not sufficient. Adding a human confirmation
  on top of a machine check is a tightening; replacing the machine check with a
  human claim is a loosening, and only the first is available here.

**What the writer does with the verdict.** The writer computes the verdict
**itself, immediately before staging**, using the 5F2D mechanism. It does not
read a verdict from an artifact, does not accept one on the command line, and
does not reuse one produced earlier by the read-only preflight (§26.9, §26.12):
a verdict is a statement about a filesystem at an instant, and a cached one is a
time-of-check/time-of-use bug of exactly the kind §6.4 already warns about. A
verdict other than `clean` ends the invocation before any staging occurs, with
nothing touched.

**One boundary note on reading `.git`.** The probe reads inside `.git`, which
the example project config lists under `forbidden_paths` — and must continue to
list there. There is no contradiction, because the two rules govern different
things: `allowed_paths` / `protected_paths` / `forbidden_paths` classify
**members of the approved change set**, and `.git` being forbidden is exactly
the property that guarantees `.git` can never be a write destination. The probe
is not a change-set path. Its access is therefore scoped by construction rather
than by the path lists: a **fixed** relative location (`.git`) under the
canonicalized workspace root, **read-only**, opened only for the specific
metadata the verdict needs, behind its **own** project-level opt-in (separate
from Phase 5D1's and Phase 5D2's), and emitting **no** repository content — the
output is the tri-state verdict plus counts, never a path list of dirty files,
never a diff, never a blob, never a commit message, never a branch name.

### 26.2 Where the approved diff may be read from

Unchanged from the pattern Phase 4D, Phase 4L, Phase 5C, Phase 5D1, Phase 5D2
and Phase 5F1 already use, and restated here because the write phase is the one
where getting it wrong matters most:

- The approved-diff artifact named by `--approved-diff-proposal` **must never be
  read from inside the configured target workspace.** If it is
  `repo.workspace_path` itself, or sits anywhere beneath it, the invocation
  exits non-zero.
- The check is **lexical, and it runs before the read.** `_is_same_or_under` in
  [cli.py](../src/ai_dev_orchestrator/cli.py) joins and normalizes two strings
  with `os.path.abspath` / `os.path.normcase` and touches no disk. The artifact
  path is therefore **rejected before it is opened, stat'd, or resolved**, and
  the workspace path is never touched in order to perform the rejection. This
  rejection-before-read ordering is preserved exactly; it must not be "improved"
  into a canonicalizing check that resolves the workspace root, because doing so
  would make the guard itself touch the thing it is guarding.
- The reason is not tidiness. An artifact living inside the workspace is an
  artifact the write itself could modify, an artifact a target repository's
  contributors can edit, and an artifact whose approval block travels with the
  code it authorizes changes to. Approval must arrive from outside the blast
  radius.
- The same rule applies to **every** file path the writer accepts on the command
  line — the project config, the approved diff, and the journal/backup directory
  of §26.8. Each is lexically rejected if it is or is under the workspace root,
  before it is opened.

### 26.3 Canonicalization immediately before each write

The order is fixed, and each step is a precondition of the next.

**Step 1 — lexical Phase 1 write policy, for every declared destination, before
any disk contact.** `PathPolicy.check_write` (§6.2) is the same check Phase 5F1
already performs: normalization, `.`/`..` resolution, containment against the
workspace root **as a string**, and classification with precedence
forbidden > protected > allowed > unlisted. It reads nothing. A refusal here
means the invocation ends having touched no filesystem at all. Every destination
in the set must pass before *any* destination is canonicalized, so a run that
would be refused is refused before the workspace is touched even once.

**Step 2 — canonicalize the configured workspace root, once.** The root comes
from `repo.workspace_path` in the project config and from nowhere else (§6.1) —
never from a plan field, a diff header, an artifact, a model, or a command-line
override. It is canonicalized with the Phase 5D0 rules: the fail-closed lexical
precheck (UNC, `\\?\`, `\\.\`, trailing dot or space, 8.3-looking components),
`lstat`, a reparse-point check honoring `workspace_policy.allow_symlinks`,
strict resolution, and a directory-kind check. A root that is itself a symlink
or reparse point with `allow_symlinks` false is refused; a root that cannot be
resolved is refused. The resolved root is the only root used for every
subsequent containment comparison.

**Step 3 — canonicalize and revalidate each destination immediately before that
destination is written.** Not once for all paths at the start, not at staging
time, not from a preflight artifact. Immediately before the individual write, in
the commit phase of §26.7 — because a check performed at time T and used at time
T+n is a time-of-check/time-of-use bug, which §6.4 already commits this project
to avoiding, and which the Phase 5D0 module docstring restates.

**Create versus modify.** These need different handling, and the difference is
not cosmetic: the shipped Phase 5D0 guard,
`canonicalize_existing_path_under_workspace`, `lstat`s the candidate and
resolves it with `strict=True`. **A destination that does not yet exist cannot
be passed to it at all** — it raises `CanonicalPathInputError`. This is correct
for a read-only inspector and useless for a writer, so a future phase needs a
second, create-aware entry point (5F2B in §26.12). Its contract — **now
implemented, library only, by `canonicalize_write_target_under_workspace` in
`workspace/canonical.py`, which has no caller and performs no write**:

- **modify** — the destination must exist and must be a **regular file**. The
  existing guard applies unchanged: containment of the resolved destination
  inside the resolved root, no reparse point on the root, none on any component
  between root and destination, and no link as the final component. A
  destination that does not exist is **not** silently upgraded to a create; the
  approved artifact said `modify`, and the world disagreeing with the approval
  is a reason to stop, not to reinterpret.
- **create** — the destination must **not** exist. Because it does not exist, it
  cannot be canonicalized; what is canonicalized instead is its **parent
  directory**, which must already exist. Concretely: apply the same lexical
  ambiguity rejections to the full destination string; require the final
  component to be a plain file name (no separator, not `.`, not `..`, no
  trailing dot or space, not 8.3-shaped); canonicalize the parent directory with
  the existing guard and verify it is a directory genuinely inside the resolved
  root; then `lstat` the destination and require `ENOENT`. Anything else —
  a regular file, a directory, or a **dangling symlink** — refuses the write. A
  dangling link deserves the explicit mention: `os.path.exists` would call it
  absent while an `open(...,"x")` would follow it out of the workspace, so
  existence is tested with `lstat`, which does not follow.
- **Win32 namespace aliases are refused lexically, for write destinations
  only** (added by Phase 5F2B-FU1, on top of the Phase 5D0 precheck above).
  Each of these stats and resolves like an ordinary file, so the decision is
  made on the string, before any filesystem call, and nothing is normalized,
  stripped, or probed: NTFS **alternate data streams** (`file.py:stream`,
  `file.py::$DATA`) — a colon is permitted only as a fully-qualified drive
  designator, and an ADS path is never reduced to its base file; **drive-relative**
  forms (`C:file.py`), which depend on ambient per-drive current-directory
  state, while `C:\...` continues through the normal machinery; **reserved
  device names** (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`,
  their superscript-digit spellings, and `CONIN$`/`CONOUT$`), case-insensitively
  and including when carrying an extension, since `NUL.txt` is still the device;
  and the **reserved characters** `< > " | ? *` plus control characters. Phase
  5E2 rejects colon-bearing paths upstream, and the write-target guard
  deliberately does not rely on that invariant holding at its own boundary. The
  rules apply on every platform, so an approval naming a Windows destination
  cannot validate as safe merely because the check ran elsewhere.
- **No directory is ever created.** If a `create` destination's parent directory
  does not exist, the invocation fails. `mkdir` would bring its own containment,
  symlink, cleanup and rollback questions (what removes a directory the writer
  created if a later path fails?), and the first write phase does not need it:
  a human can create the directory. This also usefully bounds the set of
  derived paths in §26.8 to directories that already existed.
- **Empty-set case** — nothing to canonicalize, nothing to write; see §26.5.

**Symlinks honor `workspace_policy.allow_symlinks`, plus one writer-specific
rule.** With `allow_symlinks` false (the default, and what the example config
ships) the Phase 5D0 behavior applies as written: a link at the root, a link on
any intermediate component, or a candidate not *lexically* under the root is
refused, so link-mediated entry is impossible. With `allow_symlinks` true, links
are followed and containment is then re-verified against the resolved root, so a
link resolving outside is still refused. **The writer adds a further rule that
`allow_symlinks` does not relax: the final component of a write destination may
never be a symlink or reparse point, in either setting.** Writing through a link
writes bytes to a path the human did not read and did not approve, even when
that path is inside the workspace; `allow_symlinks` is a policy about
*traversal*, and this is a rule about *destinations*.

**No path may escape the workspace, at any step.** Containment is established
twice — lexically in step 1 and against resolved paths in step 3 — with the
resolved comparison using the Phase 5D0 `commonpath`-based check rather than a
string prefix test, so that a sibling sharing a prefix (`repo_evil` next to
`repo`) is not treated as contained. An incomparable pair (different drive, a
path form that cannot be compared) is ambiguity, and ambiguity refuses.

### 26.4 The exact authorized path set

The set of paths a future writer may write is **exactly**:

```
{ change.path for change in approved_diff.diff_proposal.changes }
```

taken from the concrete, human-approved Phase 5F0
`ApprovedDiffProposalArtifact` handed to that invocation, and from nowhere else.
It is computed once, frozen before any disk contact, and never recomputed,
extended, or re-derived.

Nothing may add to it. Named explicitly, because each of these is a plausible
"reasonable" widening:

- **Not** `approved_plan.plan.files_likely_to_change` — Phase 4B/4C prose
  derived from *issue text*, which §2.2 and §12 classify as untrusted.
- **Not** the wrapped Phase 5E0 patch proposal's prose, and not any
  `rationale`, `risks`, `assumptions`, `open_questions`, or
  `next_authorization_required` string.
- **Not** `omitted_paths`. The proposal recorded those as considered and *not*
  diffed. They carry no diff, so there is nothing to apply, and naming a path is
  not proposing a change to it.
- **Not** paths read out of the unified diff's own `--- ` / `+++ ` headers. The
  headers are re-checked to name exactly the declared `path` (Phase 5E2 already
  requires this at validation time, and the writer re-checks it rather than
  inheriting it), and on any disagreement the invocation fails. A header is
  attacker-influenceable text inside a payload; it is a thing to verify, never a
  source of destinations.
- **Not** anything discovered on the filesystem — no directory listing, no glob,
  no tree walk, no "the diff mentions a neighbouring file", no rename target, no
  companion file.
- **Not** anything a model said, in any field, at any nesting level.
- **Not** the journal, staging, backup, or temporary paths of §26.8. Those are
  *derived* paths with their own rules; they are never destinations, and their
  existence must not be readable as an authorization to write anywhere new.

**Duplicates remain invalid.** Two changes naming one path have no defined
precedence, and silently keeping one would apply less than the human approved
while reporting success. Both upstream models already reject duplicates during
validation; the writer re-checks anyway, for the reason Phase 5F1 already
records — pydantic does not re-validate an instance it is handed, so a mutated
or hand-built object arrives with duplicates intact.

**One invalid path fails the entire invocation.** Not that path, the whole run.
This is the same rule Phase 5F1 states for previews and it matters more here:
"apply the paths that passed" is partial application, which §6.2 already calls a
worse outcome than no application, and it hands the operator a workspace whose
state matches no artifact anyone approved. There is no `--skip-refused`, no
`--best-effort`, and no report row with a `denied` result.

### 26.5 `max_changed_files`

`workspace_policy.max_changed_files` (`int`, `ge=0`, default 20) is checked
against the **cardinality of the frozen set from §26.4**, before anything is
canonicalized, before anything is staged, and before the first byte is written.
Phase 5F1 already performs exactly this check for previews; the writer performs
it again on its own inputs.

- **Over the cap fails the whole invocation.** The writer never applies the
  first N changes and stops. A cap is a statement about how large a change set
  may be, not an instruction to truncate one — and a truncated application is
  the partial state §26.4 and §26.7 exist to prevent.
- **The cap is not the only bound.** It bounds the number of destinations, not
  the number of bytes; a future phase may add byte bounds in the Phase 5D2
  style, and this document does not.
- **An empty change set is a valid no-op input.** A human may approve a proposal
  that proposes nothing (Phase 5F0 §24.2 permits it explicitly). The writer
  accepts it, writes nothing, stages nothing, backs up nothing, creates no
  journal, exits 0, and reports zero paths written. Note the interaction with
  `ge=0`: a project configuring `max_changed_files: 0` permits **only** the
  empty change set, which is a coherent way to say "this project may be
  previewed but never written to".

### 26.6 Protected and forbidden paths

**Forbidden paths have no override.** No flag, no config key, no escalation, no
per-invocation authorization, no "authorized forbidden" analogue of the
protected mechanism. `forbidden_paths` beats everything (§6.2, and the
precedence implemented in `PathPolicy.classify`), and the example config uses it
for exactly the things that must never be writable: `.git`, `.env`, `.venv`,
the database file, media, caches. A future phase that adds a forbidden override
would be reversing this project's central safety decision and is not
authorizable as an increment.

**Protected paths require explicit per-invocation authorization**, and Phase
5F1 currently refuses them outright because it ships no mechanism for that
authorization. The first write phase would need one. Its **shape**, defined here
and implemented by nothing:

- **Two independent human acts, both required, matched exactly.**
  1. *In the approval artifact*: the Phase 5F0 approval would carry an optional
     `protected_path_authorizations` block — a list of entries, each naming one
     **exact** path string that also appears in `changes[].path`, alongside its
     own separately worded exact sentence (the §24.1 pattern: a distinct
     constant, compared with `==`, so approving a diff is not accidentally
     approving a protected write within it). Absent block ≡ empty list ≡ no
     protected write authorized.
  2. *At the invocation*: a repeatable `--allow-protected-path <path>` option
     naming each protected destination explicitly. No `--allow-protected`
     blanket flag, no wildcard, no `--all`.
- **Set equality, not subset.** The set named on the command line must equal the
  set named in the artifact must equal the set of destinations the policy
  actually classified `PROTECTED`. Any asymmetry fails: a flag for a path the
  human never approved, an approval for a path the operator did not name, an
  approval for a path that turns out not to be protected, or a protected
  destination covered by neither. This makes an over-broad approval as loud as a
  missing one.
- **Per path, never per run and never per project.** Authorizing
  `config/settings.py` authorizes that one path in that one invocation.
- **No standing project-config switch.** This document explicitly declines to
  design a `workspace_write.allow_protected_paths: true` key, even though
  Phase 5D1's and Phase 5D2's *read* opt-ins each have one. The asymmetry is
  deliberate and worth stating: a standing read permission discloses; a standing
  write permission modifies, permanently, every future invocation, silently,
  including invocations nobody was thinking about when the key was set. §6.2 and
  §10 already require this approval to be "per-run and per-path, never a
  standing config grant", and §26.6 keeps that promise rather than eroding it
  with a convenience key.
- **Nothing here stamps that approval.** As in §3.6 and §24.1, writing the block
  is the approval act and it is a human's.

### 26.7 Transaction semantics: what "no partial writes" means precisely

**The claim this document makes.** *No destination is ever left in a state that
is neither its exact pre-image nor its exact approved post-image, and if any
destination fails, every destination ends at its pre-image.*

**The claim this document does not make.** Filesystems are not transactional.
There is no multi-file atomic commit on NTFS available to this design (the
Windows transactional-NTFS APIs are deprecated and are not a foundation to build
on), `os.replace` is atomic for **one** path on **one** volume and says nothing
about a set, a crash or a power loss can interrupt any sequence at any point,
and a concurrent process or editor can touch a destination between two of the
writer's own operations. Any design claiming "the write set is atomic" would be
lying. What is achievable is a **journalled, staged, best-effort-reversible
sequence with a precisely stated recovery contract**, and that is what is
specified here.

**Four ordered phases.**

1. **Preflight — no workspace mutation whatsoever.** The §4 gate, Phase 5F0
   artifact validation, §26.2 input-path guard, identity matching, §26.4 set
   freezing and duplicate re-check, §26.5 cap check, §26.6 protected
   authorization matching, §26.3 step 1 lexical policy, and the §26.1 Git-state
   verdict. Every failure here is an ordinary fail-closed rejection: exit 1,
   stderr only, nothing on stdout, nothing touched.
2. **Stage — everything expensive and everything fallible, still with zero
   destination mutation.** For each destination, in the artifact's order:
   canonicalize per §26.3; read the current bytes (for `modify`); record a
   digest of those bytes as the **pre-image identity**; verify the approved diff
   applies exactly to them (§26.9); compute the full post-image **in memory**;
   write the post-image, and for `modify` a byte-exact backup of the pre-image,
   into the journal directory; append a journal entry. Any failure aborts the
   whole invocation with **no destination modified** — the run is
   indistinguishable from a preflight rejection except in its exit message. This
   ordering is the core of the design: nearly every way a write can go wrong
   (a missing file, a link, a non-UTF-8 file, a diff that does not apply, a
   canonicalization refusal, a full disk on the journal volume) is discovered
   here, where the cost of discovery is zero.
3. **Commit — the only phase that mutates a destination.** For each destination,
   in the same order: **re-canonicalize immediately** (§26.3 step 3); re-read
   the current bytes and require their digest to still equal the pre-image
   identity recorded in staging — if the file changed underneath the writer,
   stop and roll back, because the approved post-image was computed from bytes
   that no longer exist; write the staged post-image to a **temporary sibling in
   the destination's own directory**; flush and `fsync` it; `os.replace` it onto
   the destination; mark the journal entry committed. The sibling is required
   for atomicity: `os.replace` is atomic only within a volume, and the journal
   directory lives outside the workspace and may be on another one (§26.8).
4. **Cleanup** — §26.8.

**Failures during each phase.**

- *During staging*: abort, delete the partial journal contents or leave them per
  the §26.8 retention rule, report the failing path and category. Zero
  destinations were modified, so there is nothing to roll back.
- *During replacement*: destinations `1..N-1` are already committed and
  destination `N` is not. This is precisely the state §26.7's claim forbids, so
  the writer immediately enters rollback. It does **not** continue to `N+1`, and
  it does **not** retry `N`.
- *During rollback*: see §26.8.

**What is deliberately not attempted.** No lock file, no cross-process mutual
exclusion, no crash-recovery `--resume` mode, no automatic re-run, no journal
replay tool. Each is a real gap and each is recorded in §26.13 rather than
half-designed here. A crash mid-commit leaves a workspace whose recovery is a
**human** operation informed by the journal, and the design says so instead of
implying otherwise.

### 26.8 Backup, staging, rollback, and cleanup

**Where staged content lives.** In a **journal directory** named on the command
line (`--write-journal-dir`), which must satisfy the §26.2 rule — it may not be,
and may not sit under, the configured workspace root — and inside which the
writer creates one fresh, uniquely named run directory per invocation. If that
run directory already exists, the invocation fails rather than reusing it. It
holds, per destination: the pre-image backup (`modify` only), the computed
post-image, and a journal entry recording the relative destination path, the
change type, the pre-image and post-image digests, and the entry's state
(`staged` → `committed` → `rolled_back` / `rollback_failed`). It holds **no**
approval text, no unified diff copy, and no project config copy.

**Why outside the workspace.** A staging area inside the workspace would create
files at paths that are not in the §26.4 authorized set, inside the very tree
whose contents the review is about, possibly matching a pattern in
`allowed_paths` and thereby becoming indistinguishable from an approved change,
and certainly polluting the Git-state verdict of §26.1 for the next run. The
journal directory therefore lives outside, and **its existence broadens no
destination set**: nothing in the journal is ever a write destination, journal
paths are never derived from artifact content, and the writer refuses to treat
a journal path as a workspace path or vice versa.

**The one derived path inside the workspace, and its rules.** Atomic
replacement requires a temporary file on the same volume as the destination,
which in practice means the destination's own directory. This is the single
place where the writer touches a workspace path that is not in the authorized
set, and it is bounded tightly:

- the same directory as an authorized destination, and that directory already
  existed (§26.3 creates none);
- a fixed, recognizable name derived only from the destination's file name, the
  run id, and a constant suffix — never from artifact content;
- it must not already exist; if it does, the invocation fails rather than
  overwriting;
- it is never a directory, never followed as a link, and never itself a
  destination;
- it is removed on **every** exit path, success or failure;
- it is transient by construction: after `os.replace` it no longer exists,
  because it *became* the destination.

The residual is stated rather than hidden: for the interval between creating the
sibling and replacing with it, one extra file exists in the workspace at a path
no human approved. The alternative — copying from a journal on another volume
directly onto the destination — replaces a bounded, self-deleting temporary with
a non-atomic write that can leave a destination **truncated or half-written**,
which is a far worse violation of §26.7. The tradeoff is taken deliberately in
favour of atomicity.

**Rollback, per change type.**

- **modify** — restore the pre-image from its backup, using the same
  temp-sibling + `os.replace` mechanism, so the restore is itself atomic.
  Verify afterwards that the destination's digest equals the pre-image digest.
- **create** — remove the file the writer created. **Guarded**: it is removed
  only if the journal records that this invocation created it *and* its current
  digest still equals the post-image the writer wrote. If either fails, the file
  is left in place and the entry is reported as `rollback_failed`; deleting a
  file whose content the writer does not recognize would risk destroying
  something another process created in the interval.
- Rollback proceeds in **reverse commit order**, over committed entries only.

**If rollback itself fails.** This is the one place where "never continue after
a failure" is deliberately relaxed, and the justification is that continuing
*reduces* damage rather than extending authority: if restoring destination K
fails, the writer **continues attempting rollback for the remaining committed
destinations**, records `rollback_failed` for each that could not be restored,
and then reports every failure together. Stopping at K would leave
`K-1 … 1` modified as well, for no benefit. Then:

- the run ends with the **catastrophic** exit code and stderr category of
  §26.10, distinct from every ordinary fail-closed rejection;
- stderr names **which** destinations are in an indeterminate state, by
  workspace-relative path, and where the journal directory is, because a human
  needs both to recover;
- **nothing is retried, nothing is repaired, and no further write is attempted.**
- the journal is **retained unconditionally**, whatever the retention setting
  says.

**Cleanup.**

- *Full success*: temp siblings are already gone; the journal run directory is
  **retained by default** as the audit record of what was written (a future
  phase may add an explicit opt-in to delete it, never a default). Backups
  contain pre-image source, so retention is a disclosure decision the operator
  makes by choosing where the journal lives, and the writer prints its path
  category, not its contents.
- *Staging failure*: no destination was touched; the run directory is retained
  by default for the same reason.
- *Successful rollback*: retained, and marked `rolled_back`.
- *Rollback failure*: retained unconditionally, as above.
- No cleanup step ever deletes anything inside the target workspace other than
  a temp sibling this invocation created and recorded, and the guarded `create`
  rollback above.

**Loud by category, quiet about content.** Every failure message names the
failure category and the workspace-relative path. None of them prints file
contents, backup contents, post-image contents, diff text, approval text, or a
secret-shaped value — the Phase 4L precedent (§10), applied to a phase that now
has backups and post-images to leak as well.

### 26.9 Where the apply-cleanliness check belongs

**Today nothing in this repository checks whether a diff applies.** Phase 5E2
fixes `applies_cleanly_checked` to `Literal[False]` precisely because answering
the question means touching a workspace, Phase 5E3 generates diffs without
asking, and Phase 5F1 lists it under `checks_not_performed`. Phase 5F2A
implements no such check.

**Decision: both, with only one of them authoritative.**

- **An advisory check belongs in a separately authorized, read-only preflight
  phase** (5F2E in §26.12) — not before it in some ad-hoc form, and not as a
  standalone capability. Answering "would this apply?" requires reading current
  file contents, which is the Phase 5D2 disclosure and needs the surrounding
  gate, caps, and opt-in that a read-only phase already knows how to provide.
  Getting the answer *before* the write phase exists is valuable: it is the
  single most likely reason a write would fail, and discovering it without a
  writer in the room is strictly better.
- **The authoritative check is intrinsic to the writer's staging phase**
  (§26.7 step 2) and is not a separate capability at all. The writer must
  compute a post-image from the current bytes plus the approved diff; if the
  diff does not apply exactly to those bytes, there is no post-image, and
  staging fails with nothing written. That is not "the writer also checks
  applicability" — it is the writer being unable to proceed.
- **The writer never relies on the preflight's answer.** A preflight verdict is
  a statement about the workspace at an earlier instant; consuming it would be
  the same time-of-check/time-of-use error as caching a canonicalization or a
  Git-state verdict. The preflight is for humans, not for the writer.
- **Exact application only.** No fuzz factor, no offset search, no
  whitespace-insensitive matching, no three-way merge, no "apply what applies".
  A diff that does not apply exactly to the bytes on disk is a diff whose
  post-image the human did not review.

### 26.10 stdout / stderr / exit-code contract

**Success (exit 0).** One JSON report on stdout, no wrapper — the Phase 5F1
convention. It carries: schema version and mode; project identity
(`project_id`, `repo`) and the workspace-policy switches, but **not**
`repo.workspace_path`; the approval's `approved_by` / `approved_at` / `source`,
issue number and title, but **not** the approval text; per destination the
**workspace-relative** path, change type, whether it was protected-authorized,
and byte counts; the Git-state verdict as the bare word `clean`; the journal
directory's presence as a boolean or a path *category*, not necessarily its
value; and explicit `false` flags for everything still not done (commands run,
verification run, model called, branch, commit, push, PR).

It carries **no** unified diff text, no source contents, no pre- or post-image,
no backup contents, no approval text, no raw artifact text, no absolute paths,
no `repo.workspace_path`, no temp-sibling names, no secret-shaped values, no
prompt, no completion, no API key, no base URL, and no content digests (a digest
of a short file is a confirmation oracle for its contents — digests belong in
the journal, which is a file on the operator's own disk, not in printed output).

**Ordinary fail-closed rejection (exit 1, preserving this repo's existing
convention).** Everything in preflight, and everything in staging: a missing
flag, a config that will not load, an artifact inside the workspace, an invalid
or mismatched artifact, a duplicate path, a cap breach, a policy refusal, a
protected-authorization asymmetry, a canonicalization or symlink refusal, a
non-`clean` Git verdict, a diff that does not apply. **stderr only, naming the
category and the failing workspace-relative path; nothing at all on stdout.** No
partial report, no report with a `denied` row, and above all **no success JSON**
— a consumer must never be able to parse a rejection as a success.

**Write failure with successful rollback (a distinct non-zero code, e.g. 3).**
Some destination was committed and then everything was restored. Every
destination is back at its pre-image, so nothing persists — but this is *not*
the same event as a preflight rejection and must not be reported as one, because
the workspace was mutated and un-mutated, timestamps moved, and any watcher saw
it. stderr carries the category, the failing path, the rolled-back paths, and
the journal location. stdout stays empty.

**Catastrophic rollback failure (a distinct, higher non-zero code, e.g. 4).**
The category above, plus at least one destination the writer could not restore.
This is the loudest outcome the design has, and it is deliberately separate from
every other exit:

- a non-suppressible stderr banner naming the category explicitly (something
  like `CATASTROPHIC_ROLLBACK_FAILURE`), so it is greppable and cannot be
  mistaken for an ordinary refusal;
- the workspace-relative path of **every** destination in an indeterminate
  state, and for each, which state it is believed to be in;
- the journal directory path, because it holds the backups a human needs;
- an explicit statement that the workspace is inconsistent and that recovery is
  a human action;
- **no** automatic retry, **no** repair, **no** suggestion that re-running will
  fix it;
- still **no** file contents, backup contents, or diff text;
- and still **nothing on stdout**.

**One rule across all four.** The presence of JSON on stdout means, and may only
ever mean, that every approved destination was written exactly as approved.

### 26.11 Capabilities the first write phase still excludes

Even with the entire design above implemented, the first write phase would
still exclude, each requiring its own separate authorization:

- **Arbitrary command execution.** No subprocess, no shell, no `PATH` lookup, no
  `git` binary — including for the dirty-tree check (§26.1). §7 is unchanged.
- **`required_verification` execution.** The plan's verification string is prose
  the writer reads as prose and never as a command. §7's two-allowlist rule
  stands: permission to write files is not permission to run tests.
- **Model calls** of any kind, for any purpose — not to resolve a conflict, not
  to repair a diff, not to summarize a failure.
- **Network calls.** No socket is opened.
- **GitHub reads and writes.** Nothing is fetched; nothing is posted.
- **Branch creation, commits, pushes, and PR creation.** §8 stands: the human
  commits. The writer leaves modified files in the working tree and says so.
- **Automatic repair and retry.** No fuzzy application, no re-run, no
  "continuing with warnings", no partial application, no self-healing rollback
  loop. §10's "never repair, never continue" applies to every input.
- **Source transmission to a model.** §9 stands, and the writer now holds
  pre-images, post-images and backups — more source than any prior phase — which
  makes the exclusion more important, not less.
- **Directory creation, deletion, rename, mode/ownership change**, and any
  binary or non-UTF-8 write. The Phase 5E2 artifact carries no
  rename/delete/mode/binary payload; the writer must not invent one.
- **Writing outside the frozen §26.4 set**, other than the single bounded
  temp sibling of §26.8.

### 26.12 Recommended phase decomposition after 5F2A — HISTORICAL

> **Status: superseded prospectively by §27 (2026-08-12).** This section records
> the decomposition the project chose **after Phase 5F2A and before the
> post-5F2B roadmap review**. It is preserved as design history and is **not**
> the current roadmap. The sequence it recommends — 5F2C typed gate models, 5F2D
> custom Git-state reader, 5F2E standalone preflight, 5F2F generalized
> transactional writer — was replaced by §27's minimum safe vertical slice, and
> **5F2F is no longer "the first controlled workspace write"**: Phase 5F2C is,
> and it shipped. The reasoning below about *why* fine granularity helps is
> still sound; what changed is the judgement about *which* things deserve their
> own phase. Nothing here is being rewritten to pretend it said something else.

The repository's own history is the argument for fine granularity: 5D0/5D1/5D2
and 5E0/5E1/5E2/5E3 each separated "the shape of a thing" from "the thing that
produces it" from "the thing that consumes it", and each was reviewable in one
sitting. The same split applies here, and it matters more, because this is the
sequence that ends in a write.

The prerequisites are deliberately separated from the write itself. Each needs
its own prompt. **5F2B has since been authorized and completed as a library-only
phase; 5F2C, 5F2D, 5F2E and 5F2F remain PROPOSED and NOT AUTHORIZED**, and
5F2F remains the first controlled workspace write.

- **5F2B — create-aware canonical write-target guard. Library only. DONE.**
  Extended the Phase 5D0 module with the entry point §26.3 showed was missing:
  the shipped guard resolves with `strict=True` and cannot accept a destination
  that does not exist, so a `create` target could not be validated at all. Added
  `canonicalize_write_target_under_workspace`, the frozen `CanonicalWriteTarget`
  result, and one new typed error (`CanonicalPathWriteTargetError`) for the one
  failure the existing hierarchy could not express — the destination's on-disk
  state contradicting the declared `change_type` — plus parent canonicalization,
  the final-component rules, the `ENOENT`-via-`lstat` requirement, the
  dangling-link refusal, and the destination-is-never-a-link rule.
  `canonicalize_existing_path_under_workspace` is unchanged, and its callers
  behave exactly as before. **No config field, no CLI command, no option, no
  caller, no write** — tested entirely with pytest `tmp_path`, exactly as Phase
  5D0 was. Follow-up **5F2B-FU1** added the write-target-only Win32 namespace
  rules of §26.3 (streams, drive-relative forms, device names, reserved
  characters), again without touching the Phase 5D0 read guard.
- **5F2C — typed workspace-write gate models. Library only.** The
  `protected_path_authorizations` block of §26.6 and its exact-sentence
  constant, plus whatever project-level `workspace_write` opt-in the writer
  needs — carrying an `enabled` flag and caps, and **no** standing
  protected-write switch. Models and a strict parser in the 5B/5E0/5E2/5F0
  style. **Wired into nothing; nothing stamps an approval.**
- **5F2D — read-only Git-state probe. Its own opt-in, no subprocess.** §26.1's
  mechanism: the tri-state verdict, the fail-closed `undetermined` handling, the
  `.git`-scoped read, and a command that reports the verdict and nothing else.
  **No `git` binary, no subprocess, no shell, no repository content in the
  output, no write.** Shipping it here rather than inside the writer is the
  whole point of the §26.1 resolution.
- **5F2E — read-only write preflight command.** Composes 5F2B + 5F2C + 5F2D with
  the Phase 5F1 preview and the Phase 5D2 content read, and answers the full
  question "would this write be permitted right now, and would each diff apply?"
  — including the **advisory** apply-cleanliness check of §26.9. It
  canonicalizes write destinations for the first time and reads current file
  contents; it **writes nothing, stages nothing, creates no journal, and its
  verdict is never consumed by the writer.**
- **5F2F — the first controlled workspace write.** Only §26.7's four phases and
  §26.8's journal/backup/rollback machinery, over the frozen §26.4 set, with
  every exclusion in §26.11 intact. By the time it is proposed, every check it
  performs already exists and has been reviewed on its own, so the new code
  under review is the staging/commit/rollback sequence and nothing else.

Two notes on the ordering. First, 5F2B through 5F2E together touch a workspace
only to **read** it, so the entire pre-write contract becomes testable and
reviewable before anything can write — the same shape as building the §4 gate
across 5B/5C before it guarded anything. Second, the sequence deliberately does
**not** end at "L2 is done": branch creation, commits, pushes, PRs, verification
execution and model-backed implementation all remain later, separate phases per
§7, §8 and §9.

If a smaller starting point than 5F2B is wanted, there isn't one — it is already
a single function over two path strings.

### 26.13 Unresolved questions

Recorded explicitly rather than settled by omission. None of these blocked 5F2B,
which shipped as a library-only path guard; several block 5F2D and 5F2F.

> **Phase 5F2C update (2026-08-12).** Several of these are now **resolved for
> the Phase 5F2C writer's narrow input domain only**, by refusal rather than by
> design, exactly as §27's phase-admission rule prescribes. Question 1 is
> answered differently than proposed (a fixed Git adapter, not a custom reader —
> §28.4); question 3 is answered "refused" for the supported domain; question 4
> is answered by refusing anything but uniform UTF-8 text with a terminal
> newline (§28.7); question 7 is answered by ``ReplaceFileW`` plus an attribute
> allowlist (§28.8); question 8 is answered by declaring the quiescent
> single-writer contract and failing closed on detection (§28.6); and question
> 11 is answered by refusing a link count other than one (§28.5). Questions 2,
> 5, 6, 9 and 10 remain open. **None of these is settled for a generalized
> writer** — each is settled only inside the domain 5F2C supports.

1. **Which non-subprocess Git-state implementation.** A vendored minimal reader
   (`HEAD`, `index`, working-tree comparison) keeps the dependency surface at
   zero but reimplements subtle logic; `dulwich` is mature and pure-Python but
   is a third-party runtime dependency this project does not currently have, and
   the repository has no stated policy on adding one. **Undecided.** Either way
   the `undetermined`-is-dirty rule (§26.1) is what makes an imperfect
   implementation safe.
2. **Whether the `.git` read needs a path-policy concept of its own.** §26.1
   scopes it structurally and by a dedicated opt-in rather than through
   `allowed_paths`, and requires `.git` to stay in `forbidden_paths` so it can
   never be a destination. Whether that structural exemption should instead be
   expressed as an explicit "policy-exempt read locations" list is open.
3. **Writing into a non-Git workspace.** Currently refused (`undetermined`).
   Whether a project should ever be able to opt out of the Git-state
   requirement, and what would replace the review property it provides, is
   **open and not authorized**.
4. **Line endings, encoding, and the trailing newline.** The Phase 5E3 pipeline
   is UTF-8 text and `difflib`-derived. A destination that is not valid UTF-8,
   uses CRLF, mixes line endings, or lacks a final newline must round-trip
   **byte-exactly** through pre-image → post-image. The requirement is settled;
   the mechanism (and whether non-UTF-8 destinations are simply refused) is not.
5. **Same-volume assumptions.** The temp sibling is on the destination's volume
   by construction, but a workspace spanning a mount point, or a filesystem
   without atomic replace semantics, is undesigned. Probably a fail-closed
   detection, probably `undetermined`-shaped.
6. **Where the journal directory may live.** §26.2 requires only "outside the
   workspace". Whether it should be further constrained to this orchestrator
   repository, and how long retained backups (which contain target source)
   should live, is a disclosure decision left open.
7. **File mode, permissions, ACL and ownership across `os.replace`.** Replacing
   a file can change inherited ACLs on Windows and mode bits on POSIX. Whether
   the writer must preserve and restore them, or refuse when it cannot, is
   undecided.
8. **Concurrency.** Two orchestrator runs, or a run and a human editor, against
   one workspace. The pre-image digest re-check in §26.7 step 3 detects
   interference at the last moment for a single destination; there is no lock
   and no cross-invocation mutual exclusion. **Open.**
9. **Crash recovery.** A power loss mid-commit leaves a journal with `committed`
   and `staged` entries and no process to finish. §26.7 declares recovery a
   human operation informed by the journal; whether a read-only journal
   *inspection* command should exist is open, and any replay/resume capability
   would be its own authorization.
10. **Whether the preflight (5F2E) should be mandatory before the writer runs.**
    Currently no: the writer re-establishes everything itself, and requiring a
    preflight artifact would create a second thing that looks like an
    authorization. Whether the operator should nonetheless be *required* to have
    run one is open.
11. **Hard links to a `modify` destination.** A regular file may carry several
    hard links, and none of the checks this document specifies reveals the other
    names: canonical containment answers "where is this path", and the
    symlink/reparse rules answer "is this path an indirection" — neither
    enumerates the alternate names pointing at the same inode, which may sit
    anywhere on the volume, including outside the workspace. This interacts
    badly with the temp-sibling-plus-`os.replace` strategy of §26.7/§26.8:
    replacement rebinds *the approved name* to a new file, so the other links
    keep the old content and the approved path silently leaves the link set,
    rather than the in-place mutation a reviewer would expect. That changes what
    the pre-image means and what rollback restores. A policy must be chosen
    **before Phase 5F2F** — for example, refusing a `modify` destination whose
    link count is reliably greater than one (fail closed when the count cannot
    be determined), or designing a mechanism that provably preserves the
    intended semantics. **Open, and not addressed by Phase 5F2B or 5F2B-FU1**,
    which validate a path and never open, replace, or write anything.

### 26.14 Acceptance criteria for Phase 5F2A (DONE)

- [x] The design resolves the **dirty-tree vs. no-command-execution conflict**
  explicitly (§26.1): the conflict is named, `git status` is **not** assumed
  allowed, three directions are weighed, and the chosen one is a non-subprocess
  Git-state probe shipped as its **own separately authorized read-only
  prerequisite phase** with a fail-closed tri-state verdict. **Human attestation
  is explicitly rejected as a replacement**, with the reason stated, and is
  permitted only as an additional requirement on top of a machine check.
- [x] The **input artifact path guard** is restated (§26.2): the approved diff
  may never be read from inside the configured workspace, and the existing
  **lexical rejection-before-read** pattern is preserved rather than replaced by
  a resolving check.
- [x] **Canonicalization immediately before write** is specified (§26.3) in a
  fixed order — Phase 1 lexical write policy for every destination first, then
  the workspace root, then per-destination canonicalization immediately before
  that destination's write — with **create-vs-modify** handled explicitly,
  including the finding that the shipped Phase 5D0 guard cannot accept a
  non-existent path, the parent-directory rule, the no-`mkdir` rule, the
  dangling-symlink refusal, and a symlink policy honoring
  `workspace_policy.allow_symlinks` plus a destination-is-never-a-link rule. No
  path may escape the workspace at any step.
- [x] The **exact authorized path set** is defined (§26.4) as the paths in the
  concrete human-approved Phase 5F0 proposal and nothing else, with every
  plausible widening named and refused, duplicates invalid, and **one invalid
  path failing the entire invocation**.
- [x] **`max_changed_files`** is enforced before the first write against the
  frozen set (§26.5); truncation to the first N is forbidden; an empty change
  set is a valid no-op.
- [x] **Forbidden paths have no override**; **protected writes require explicit
  per-invocation authorization** represented as two matching human acts with set
  equality; **no standing project-config switch** for protected writes is
  designed, and the asymmetry with the Phase 5D1/5D2 read opt-ins is justified
  (§26.6).
- [x] **Transaction semantics** are stated precisely (§26.7): the all-or-nothing
  claim, the explicit disclaimer that filesystem operations are **not**
  transactional, four ordered phases that push every fallible operation into
  staging, and defined behavior for failures during staging, replacement, and
  rollback.
- [x] A concrete **backup/rollback strategy** covers both `modify` and `create`
  (§26.8); staging lives in a controlled journal directory outside the workspace
  and **broadens no destination set**; the single in-workspace temp sibling is
  bounded, justified, and self-deleting; cleanup is defined per outcome; and
  **rollback failure** is defined, including best-effort continuation, mandatory
  journal retention, and a distinct loud report that names categories and paths
  without dumping source.
- [x] **Diff applicability** is placed (§26.9): an **advisory** check in the
  separately authorized read-only preflight, an **authoritative** one intrinsic
  to the writer's staging step, never consumed from a cached verdict, exact
  application only — and **none of it implemented in 5F2A**, with
  `applies_cleanly_checked` still false everywhere it appears.
- [x] The **stdout/stderr/exit-code contract** is specified (§26.10): success
  JSON leaks no source, diff, approval text, backup content, digest, or absolute
  path; every gate or safety failure is stderr-only, non-zero, with **no
  misleading success JSON**; and catastrophic rollback failure has its own exit
  code, its own banner, and its own report shape, distinct from an ordinary
  fail-closed pre-write rejection.
- [x] The **excluded capabilities** are listed in full (§26.11): arbitrary
  command execution, `required_verification` execution, model calls, network
  calls, GitHub reads/writes, branch creation, commits, pushes, PR creation,
  automatic repair or retry, and source transmission to a model.
- [x] A **phase decomposition** is recommended (§26.12) that splits the
  prerequisites (5F2B create-aware guard, 5F2C typed gate models, 5F2D Git-state
  probe, 5F2E read-only preflight) from the first write (5F2F), chosen from this
  repository's actual architecture — the Phase 5D0 guard's strict-existence
  limitation, the existing per-phase opt-in pattern, and the shipped Phase 5F1
  preview — with 5F2B named as the recommended immediate next phase.
- [x] **Unresolved questions are recorded explicitly** (§26.13) rather than
  hidden: the Git-state implementation choice, `.git` policy expression,
  non-Git workspaces, encoding/line-ending fidelity, volume assumptions, journal
  location and retention, permissions across replacement, concurrency, crash
  recovery, and whether preflight should be mandatory.
- [x] **Documentation only.** This phase changed Markdown files only. No `src/`
  change, no runtime behavior change, no new or changed CLI command or option,
  no test of new behavior.
- [x] **Nothing was implemented.** No file edit engine, no apply function, no
  apply-cleanliness check, no subprocess, no verification, no branch, commit,
  push or PR, no model call, no network call, no environment read, no GitHub
  access, and no approval stamping.
- [x] **No target project workspace was touched.** Nothing under any project's
  `repo.workspace_path` was read, listed, stat'd, resolved, or modified, no
  `git` command was run against one, and `C:\dev\mis_project`, `C:\dev\a8_oa`,
  `C:\dev\bible_reading_v2` and the `C:\dev` parent were not touched.
- [x] **Phase 5F2B, 5F2C, 5F2D, 5F2E, 5F2F and every later sub-phase in §13
  remain PROPOSED and NOT AUTHORIZED.** L2 is still not built, no command can
  invoke it, and **nothing shipped in this repository edits a target file.**
  *(This criterion records the state at the end of Phase 5F2A. **Phase 5F2B has
  since been authorized and completed as a library-only path guard** — see
  §26.3 and §26.12 — with no command, no option, no config field, no caller and
  no write. **Phase 5F2C has since been authorized and completed as the first
  controlled workspace write** — see §27 and §28 — so the sentence "nothing
  shipped edits a target file" is **no longer true as a statement of current
  status**, and is retained here only as a record of where Phase 5F2A ended. L2
  is still not built: controlled verification (5F2D) and reviewer integration
  (5F2E) remain unauthorized.)*

---

## 27. Post-5F2B roadmap rebalance: the minimum safe vertical slice (2026-08-12)

> **This section is current, and it supersedes the future-roadmap
> recommendations of §26.12 prospectively.** §26.12 is preserved unchanged as
> design history — it records what the project decided after Phase 5F2A, and
> that record is not being rewritten. What follows is what the project decided
> **after Phase 5F2B shipped and the roadmap was independently reviewed.**

### 27.1 Why the roadmap changed

The review's conclusion was not that the safety philosophy was wrong. It was
that the *shape of the plan* had drifted, in a way that is easy to reach one
careful phase at a time:

- **The safety philosophy remains correct.** Fail closed; never repair; an
  approval is for one specific thing; containment is not authorization; a
  downstream guard re-establishes what an upstream guard already proved. None of
  that is in question, and none of it was weakened.
- **Safety maturity had run ahead of positive-capability maturity.** By the end
  of 5F2B the repository held twelve commands, four artifact schemas, two path
  guards, a lexical policy, a preview, and two separately worded human
  approvals — and could not change a single character of a single file. The
  ratio had stopped being evidence of care and started being evidence of
  imbalance.
- **Too many intermediate shape/producer/consumer/preflight seams were delaying
  the first complete behavioral slice.** The 5D0/5D1/5D2 and 5E0/5E1/5E2/5E3
  splits were genuinely valuable, and §26.12 reasoned by analogy from them. But
  those splits separated *things that already had a user*. The proposed
  5F2C/5F2D/5F2E seams separated things whose only consumer was a phase that did
  not exist yet, which is a different and much weaker justification.
- **Generalized mutation-engine concerns should not all precede the first
  narrowly supported write.** A transaction framework, a journal, a rollback
  path, crash recovery and a concurrency protocol are the right answers to
  problems a *general* writer has. A writer that touches one file, in a clean
  repository, with both byte-images pinned, does not have most of those
  problems — and building the machinery first means reviewing an abstraction
  before anyone has seen the concrete case it abstracts over.
- **Complexity is itself part of the reliability and security surface.** A
  hand-written `.git` index parser, a journal format, and a rollback state
  machine are all code that can be subtly wrong in ways no test thought to
  check. Choosing them over "refuse this input" is choosing more attack surface
  in exchange for supporting cases nobody has needed yet.

### 27.2 The new phase-admission rule

Before adding another prerequisite phase, ask exactly one question:

> **Does this issue threaten workspace containment, approved scope, approved
> content identity, or an interpretable failure state — inside the currently
> supported input domain?**

If **yes**, it is a correctness blocker and must be handled.

If **no**, prefer to **reject the unsupported case** rather than generalize. A
narrower supported domain with an honest refusal is a smaller, more reviewable,
more trustworthy artifact than a broader domain with machinery nobody has
exercised.

Phase 5F2C applies this rule visibly and repeatedly. Mixed line endings, files
without a terminal newline, non-UTF-8 files, hard-linked files, read-only or
sparse or compressed files, assume-unchanged index entries, submodules,
non-Windows platforms, `create`, second files, and protected paths are all
**refused**, not supported. Every one of them could be designed for. None of
them had to be, to prove the first useful mutation.

### 27.3 The positive-capability rule

> **Consume the existing safety primitives to prove the next useful capability,
> before creating additional generalized primitives.**

By the end of 5F2B the project owned: a lexical path policy, a canonical read
guard, a create-aware canonical write guard, two human-approval schemas, a
diff-carrying artifact, a deterministic diff generator, and a dry-run preview.
Phase 5F2C added the smallest things that were genuinely missing — exact image
identities on the diff artifact, a strict applier, a fixed Git adapter, and a
Windows replacement primitive — and **consumed everything else that already
existed** rather than building parallel machinery for the writer to use.

### 27.4 Current capability buckets

Recorded at a high level, so the boundary is legible without reading the code.

**Established before the first write happens:**

- explicit, exactly-worded, scoped human approval of one concrete diff;
- exact project/repo/issue identity, matched by string equality in six places;
- exact approved target scope — one path, from the approval and nowhere else;
- forbidden and protected path refusal, with no override anywhere;
- lexical containment (Phase 1) **and** canonical containment (Phase 5F2B);
- a known-clean Git baseline for the whole repository;
- one ordinary, tracked, stage-0, regular, single-linked file;
- exact pre-image and post-image identity binding;
- bounded input — file size, diff size, Git output size, subprocess time;
- full revalidation immediately before the mutation;
- fail-closed refusal on every unsupported case;
- machine verification of the postcondition after the mutation.

**Deferred until a routine or generalized writer is separately authorized:**

- `create`, delete, rename, directory creation, mode/ownership changes;
- multi-file writes;
- protected-path writes;
- a transaction/journal framework;
- a rollback framework;
- a concurrency framework;
- crash recovery;
- unusual filesystem states (links, reparse points, sparse/compressed/encrypted
  files, non-simple index states);
- broad encoding, line-ending, and binary support.

### 27.5 The new near-term roadmap

The old sequence recorded in §26.12 —

```text
5F2C standalone gate schema
5F2D custom in-process Git-state reader
5F2E standalone preflight
5F2F generalized transactional writer
```

— **is superseded by**:

```text
5F2C  Controlled Single-File Writer Slice      (DONE - see §28)
5F2D  Controlled Verification Slice            (NOT AUTHORIZED)
5F2E  Reviewer Integration Slice               (NOT AUTHORIZED)
   -> first complete controlled implement -> verify -> review -> human loop
```

> **Status note (history).** The authorization states in the block above are the
> ones that held when §27 was written. **Both have since been authorized and
> completed** — 5F2D in §29, 5F2E in §30 — and the current sequence is
> `5F2C DONE → 5F2D DONE → 5F2E DONE`. The block is preserved as the record of
> the roadmap pivot, not as current status.

Only **after** that loop exists should generalized writer expansion resume:
multi-file, `create`, protected-path writes, the transaction/journal framework,
crash recovery, concurrency, and broader filesystem semantics.

### 27.6 Two milestones, deliberately separated

**The writer milestone (reached by Phase 5F2C):**

> AIDO can safely apply one exact approved modification to one supported file in
> one clean supported repository, and prove it did.

**The first complete L2 development-loop milestone (not reached):**

> AIDO can carry an approved concrete change through
> `write → verify → reviewer → human-facing result` without the human manually
> acting as the message bus between those stages.

Phase 5F2C is the first of these and **not** the second. Verification is 5F2D;
reviewer integration is 5F2E; and branch creation, commits, pushes, PRs and a
model-backed implementer remain later, separate phases per §7, §8 and §9.

### 27.7 Roadmap constraint after 5F2C

> **No generalized writer-hardening phase should be inserted between 5F2C and
> 5F2D unless it is required for correctness inside the already-supported
> single-file writer domain.**

This constraint exists specifically to stop the project from repeating the
imbalance §27.1 describes. "It would be good to have a journal" is not a reason
to insert a phase. "The single-file writer is incorrect without X" is.

---

## 28. Phase 5F2C — controlled single-file writer slice (DONE)

Phase 5F2C is **the first shipped controlled target-workspace write**. One new
command, `l2-apply-approved-file-edit`, can transform one file. Everything else
about it is a refusal.

The capability, stated once and precisely:

> Given one explicitly human-approved concrete modification, AIDO can safely
> transform one existing tracked ordinary UTF-8 file from one exact approved
> pre-image into one exact approved post-image inside one clean supported
> Windows Git repository, then prove the expected postcondition and leave the
> resulting change for human review.

### 28.1 The supported input domain, exhaustively

Every one of these must hold. Anything else fails closed:

- `sys.platform == "win32"`;
- a local Git working tree, with a valid `HEAD`;
- the configured `repo.workspace_path` is **exactly** the Git worktree root;
- the **whole repository** is clean under §28.4's contract;
- exactly **one** proposed change;
- `change_type == "modify"`;
- the target is already Git-tracked as one ordinary stage-0 blob;
- the target is an existing **regular file**;
- no symlink or reparse-point traversal, and the destination is not one;
- the project sets `workspace_policy.allow_symlinks: false`;
- the project sets `workspace_policy.deny_outside_workspace: true`;
- the target is **not** protected and **not** forbidden;
- the target is permitted by the Phase 1 lexical write policy;
- the target passes the Phase 5F2B canonical write-target guard;
- the target's hard-link count is exactly **1**;
- ordinary UTF-8 text, no NUL bytes;
- one uniform line-ending convention, with a terminal newline;
- both images inside `workspace_write.max_file_bytes`;
- explicit human approval of the concrete diff, in the Phase 5F0 wording;
- the on-disk bytes hash to the approved **pre-image** digest;
- the applied diff hashes to the approved **post-image** digest;
- one AIDO writer, against a quiescent workspace.

### 28.2 The project-level write opt-in

```yaml
workspace_write:
  enabled: false        # absent == disabled; no workspace touch while false
  max_file_bytes: 200000
```

Two fields, and that is the whole block. There is deliberately **no**
`allow_protected_paths` (§26.6 rejects a standing protected-write switch, and
5F2C refuses protected destinations outright), no create flag, no multi-file
switch, no rollback or journal setting, no credential, no model, and no command.
`workspace_policy.max_changed_files` already exists and is **not** duplicated;
the writer enforces it **and** its own hard requirement of exactly one change,
and a `max_changed_files` of `0` permits no write at all.

### 28.3 Approved-diff schema evolution: binding both image identities

The Phase 5E2 change carried a path, a change type, a diff, a rationale, risks,
and a review flag. That is enough for a human to read and **not** enough for a
writer to act on, because a diff describes a transformation without saying which
exact bytes it starts from or ends at.

So the **existing** concrete-diff artifact was evolved — rather than a second
human-visible "prepared write" artifact being invented to avoid touching a
completed schema. `diff-proposal.v1` became **`diff-proposal.v2`**, and
`approved-diff-proposal.v1` became **`approved-diff-proposal.v2`** in step. Each
change now additionally carries:

```text
pre_image_sha256   lowercase 64-hex SHA-256 of the whole original file's exact
                   UTF-8 bytes - required for `modify`, and `null` for `create`
post_image_sha256  lowercase 64-hex SHA-256 of the whole resulting file's exact
                   UTF-8 bytes - always required
```

The version was **raised rather than v1's meaning silently changed**: a v1
artifact does not carry those identities, there is no honest way to invent them,
so it is rejected as a different artifact. The repository is pre-production, so
no compatibility subsystem was built to keep hand-written v1 artifacts parsing;
fixtures and tests were updated instead.

The `generate-diff-proposal` producer computes both digests from the exact UTF-8
bytes of the strings it already holds — the Phase 5D2 packet's recorded original
and the proposed-content input's final text — with **no normalization** first.

**The human approval sentence is unchanged**, and there is no second approval
artifact:

```text
I approve this diff proposal for workspace file editing
```

The invariant is what matters: *a specific human explicitly approved this
specific immutable concrete transformation*. Where that binding is stored is a
representation detail; that it exists is the architecture.

### 28.4 The Git contract, and why it is a fixed adapter

§26.1 proposed a non-subprocess Git-state reader so that "the writer needs to
know whether the tree is clean" would not become "the orchestrator may run
programs". §27's review kept the goal and changed the mechanism: a hand-written
`.git` parser reimplements subtle logic Git already implements correctly, and
getting it subtly wrong is itself a safety problem.

`ai_dev_orchestrator.workspace.git_adapter` is the replacement, and the
distinction it holds is explicit in the code and here:

> **Fixed, AIDO-owned Git plumbing is part of the writer's own correctness
> contract. Repository-configured verification is a separate executable
> capability, and Phase 5F2C does not have it.**

This is **not** arbitrary command execution:

- the executable is the literal string `"git"`;
- every argv is assembled from constants in `FIXED_GIT_OPERATIONS`, and an
  operation outside that set raises;
- **no model, user, config file, or artifact supplies an executable, a
  subcommand, a flag, or a shell fragment**; the only variable component in the
  module is one already-validated repo-relative path, passed after `--`;
- `shell=False` always;
- the cwd is the canonical workspace root;
- the environment is a **minimal allowlist**, so no `AIDO_LITELLM_*` value, no
  `GITHUB_TOKEN`, and no inherited `GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE`
  reaches the child;
- optional locking, fsmonitor, external diff, textconv, the pager, terminal
  prompting, askpass, and system config/attributes are all disabled;
- output is capped and the call is bounded by a timeout;
- **every operation in the set is read-only** — there is no `add`, `commit`,
  `checkout`, `restore`, `reset`, `branch`, `apply`, `fetch` or `push`, and no
  network operation at all. Remote divergence is deliberately not a first-writer
  correctness prerequisite.

**Clean baseline.** Before reading or writing the target: the workspace is a Git
working tree; the canonical Git top level equals the canonical configured
workspace root; `HEAD` exists; and `git status --porcelain=v1 -z
--untracked-files=all --ignore-submodules=none` reports **nothing at all**. That
one condition covers staged changes, unstaged changes, untracked files, deleted
tracked files, renames, unmerged entries, and dirty submodule state.
**Any Git-visible deviation refuses the run.**

**Special index state.** `git ls-files -v` is read and **every** tag other than
`H` is refused — a lowercase tag (assume-unchanged), `S` (skip-worktree), `M`
(unmerged), and anything else. `git ls-files --stage` is read and any gitlink
(mode `160000`) or non-zero stage refuses the **whole repository**. That is the
preferred MVP behavior: if the simple clean-baseline contract cannot be proved,
the repository is not one this writer supports. **No custom Git index parser was
built.**

**Tracked target.** The single target must be exactly one stage-0 entry with an
ordinary blob mode (`100644`/`100755`). Untracked, symlink index mode
(`120000`), gitlink, unmerged, and ambiguous multiple entries are all refused.

### 28.5 The path and target contract

In order, before any target content is read:

1. validate project/diff identity (six exact string comparisons);
2. require exactly one change;
3. require `change_type == "modify"`;
4. run the Phase 1 lexical `PathPolicy.check_write`;
5. protected → refuse (no flag, no config field permits it);
6. forbidden → refuse;
7. unlisted → refuse;
8. require `allow_symlinks == false`;
9. call `canonicalize_write_target_under_workspace(..., change_type="modify",
   allow_symlinks=False)`;
10. require an existing regular file;
11. require `st_nlink == 1`.

**Hard links.** §26.13's open question 11 is resolved **for this writer only**:
a link count other than one is refused, and a link count that cannot be
established reliably is also refused. The count comes from
`GetFileInformationByHandle` rather than `os.stat`, because the answer must be
trustworthy for the refusal to mean anything. This does **not** establish
generalized hard-link semantics.

### 28.6 Pre-image validation, final revalidation, and the single-writer contract

The target is read only after every cheaper gate passes, the read is
size-bounded, and:

```text
sha256(current_bytes) == approved pre_image_sha256
```

A mismatch refuses. There is deliberately **no** fallback of "but does the diff
still apply anyway?" — the human approved transforming *these* bytes, and
different bytes are a different transformation nobody approved.

**Immediately before the mutation**, everything is re-established from scratch:
the canonical write-target guard is re-run, the destination is re-checked as a
regular file with no reparse point and a link count of one, its Windows
attributes are re-read and required to be unchanged, the bytes are re-read, the
pre-image digest is recomputed and required to still match, and the Git baseline
and index contract are re-proved. **No earlier canonicalization result is reused
as durable authority** — Phase 5F2B already documents that its result is a
point-in-time observation.

**The single-writer contract, stated plainly:**

> Phase 5F2C supports one AIDO writer operating against a quiescent workspace.
> Concurrent modification by a human, an editor, or another process is outside
> the supported execution contract.

There is no file-lock service, no editor integration, no filesystem watcher, no
multi-process orchestration lock, and no concurrency protocol. Interference is
detected by immediate pre-write revalidation and immediate post-write
verification, and detection means failing closed. **Concurrency is not solved,
and this phase does not claim it is.**

### 28.7 The text domain

This is not a general text writer. Required: strict UTF-8 decode; no NUL bytes;
one uniform line-ending style (LF **or** CRLF, never mixed, never bare CR); a
terminal newline; and both images within `workspace_write.max_file_bytes`. The
original style is preserved.

The terminal-newline requirement is not fussiness — it is what makes the round
trip exact. With it, splitting on the line ending and rejoining with
`ending.join(lines) + ending` reproduces the file byte for byte, so applying a
diff over lines cannot silently add or drop a trailing newline.

There is **no encoding detection, no conversion, no normalization, and no
repair.** A file outside the supported representation is refused.

### 28.8 Windows write mechanics and the metadata contract

The writer is **explicitly Windows-only** and refuses elsewhere before any
target workspace touch. It does not pretend to be cross-platform.

`os.replace` is deliberately **not** used: it maps to `MoveFileEx` with
`MOVEFILE_REPLACE_EXISTING`, which gives the destination the *new* file's
security descriptor and attributes — so an approved content-only edit could
quietly become an ACL change. **`ReplaceFileW`** is used instead, which preserves
the replaced file's attributes, ACLs and creation time while swapping in the
replacement's contents. `REPLACEFILE_IGNORE_MERGE_ERRORS` and
`REPLACEFILE_IGNORE_ACL_ERRORS` are **not** passed: both exist to make the call
succeed when the metadata contract could not be honored, which is the opposite
of what is wanted.

The sequence: create **one** unique sibling temp file in the destination's own
directory, exclusively (`O_CREAT | O_EXCL`); write the exact post-image bytes;
flush; `fsync`; then `ReplaceFileW` with `REPLACEFILE_WRITE_THROUGH` and
**`NULL` for the backup file** — this phase ships no backup or journal
framework. On a failure before the replacement, the known temp file is removed
and the destination is untouched. **No directory is ever created.** The temp
sibling is the one narrowly authorized path outside the approved destination.

**Metadata envelope.** File attributes are read before the write via
`GetFileInformationByHandle`, and an **allowlist** is applied: only `ARCHIVE`,
`NORMAL` and `NOT_CONTENT_INDEXED` are supported. Read-only, hidden, system,
reparse, sparse, encrypted, compressed, offline, temporary, virtual,
recall-on-open, directory and device attributes all refuse the candidate,
because preserving semantics the writer has not reasoned about is not something
it can claim to do. After the replacement the mask is re-read and required to be
unchanged. **No cross-platform ACL/ownership abstraction was built.**

### 28.9 Post-write machine verification

A successful `ReplaceFileW` is **not** proof the write is correct. After the
write:

1. re-canonicalize the target;
2. re-read the exact bytes;
3. require `sha256(actual_bytes) == approved post_image_sha256`;
4. re-read and compare the file attributes;
5. obtain `git status` again;
6. prove **exactly** the approved path is dirty, as an unstaged modification;
7. prove no other staged/unstaged/untracked/unmerged/submodule state appeared;
8. obtain a human-facing `git diff` for **only** the approved path, with
   external diff, textconv, color and the pager disabled.

Machine truth is the exact post-image digest, the exact expected dirty-path set,
and an otherwise-clean supported repository. Git's textual diff is **not**
required to be byte-identical to the approved `difflib` text — those are two
renderings of the same change by different tools. The diff is for the human; the
digest is the correctness invariant.

### 28.10 Failure semantics: refused vs. indeterminate

Two failure kinds, never conflated, with distinct exit codes.

**Pre-write refusal (exit 1).** No replacement was attempted. The target is
unchanged, stderr names the failure category, stdout is empty, and no source,
diff, approval text, absolute path, or credential is echoed.

**Write-attempted, state indeterminate (exit 3).** A replacement was attempted
and its postconditions could not be completely proved. It **never** claims
nothing changed. The run stops immediately; nothing is retried; **nothing is
rolled back**; no `git restore`, `checkout`, `reset` or `clean` is run; nothing
proceeds to a later step; and the human is told plainly that repository
inspection and recovery are required. Only bounded, safe metadata is reported.

The clean Git baseline proved beforehand exists precisely so that a human has a
known recovery reference. **No automatic rollback framework is authorized in
this slice.**

### 28.11 Output, CLI, and the capabilities that do not exist

The success report carries the project id, repo, issue and title; the relative
target path, `change_type: "modify"`, the line-ending style and the two image
sizes; the checks proved (baseline clean, target tracked, canonicalization
verified, pre-image verified, post-image verified, only the approved target
dirty); `files_edited: 1`; the fixed Git operations used; the resulting Git diff
for the approved path; the single-writer contract; and the statement that the
next step requires human review. It carries **no** absolute path, no configured
workspace path, no API key, no environment value, no approval text, no raw input
artifact, no approved diff, no unrelated source, no digest, and no arbitrary
command output.

The command is `l2-apply-approved-file-edit`, with exactly five options:
`--project-config`, `--approved-diff-proposal`, `--apply-approved-plan`,
`--write-approved-file`, `--format`. Both action flags are checked **first**, so
a missing one reads nothing at all. Then the config loads; then
`workspace_write.enabled`; then the Windows-only platform check; then the
existing lexical guard rejecting an approved-diff artifact **inside** the target
workspace before it is read; then the strict parse; then the writer's own gates.

**No write flag was added to any other command.** `generate-plan`,
`generate-model-plan`, `l2-dry-run`, `l2-inspect-workspace`,
`l2-read-workspace-files`, `generate-patch-proposal`, `generate-diff-proposal`
and `l2-preview-file-edits` are exactly as they were. The write command has no
`--workspace`, no arbitrary file or command argument, no model flag, no
protected override, no create flag, no force flag, no fuzzy flag, no rollback
flag, and no commit/push/PR flag.

**No project verification.** 5F2C may run only its own fixed Git operations. It
must not and does not run pytest, npm, make, build scripts,
`required_verification`, any project-configured verification command, or any
model-proposed command. **Those are Phase 5F2D.**

**No model, network, or GitHub.** No model call, no `LLMClient`, no LiteLLM, no
environment credential read, no socket, no GitHub API, no GitHub write, and no
source transmitted to a model.

### 28.12 Acceptance criteria for Phase 5F2C (DONE)

- [x] The **roadmap pivot is recorded** (§27) with its reasoning, the new
  phase-admission rule, the positive-capability rule, the capability buckets,
  the new near-term sequence, the two separated milestones, and the constraint
  against inserting generalized hardening before 5F2D. §26.12 is preserved as
  history and marked superseded prospectively.
- [x] The **supported input domain is exhaustive and narrow** (§28.1), and every
  case outside it fails closed.
- [x] A **project-level write opt-in** exists with an enable switch and a size
  ceiling and nothing else (§28.2) — no protected-path override, no create flag,
  no multi-file switch, no rollback/journal setting, no credential, no model, no
  command. `max_changed_files` is not duplicated, and `0` permits no write.
- [x] The **concrete diff artifact was evolved**, not sidestepped (§28.3):
  `diff-proposal.v2` and `approved-diff-proposal.v2` bind exact pre-image and
  post-image SHA-256 identities; the deterministic producer computes them from
  unnormalized UTF-8 bytes; v1 is rejected rather than upgraded; the single
  human approval sentence is unchanged and no second approval artifact exists.
- [x] **Diff application is strict** (§28.3, `diff_apply.py`): no external patch
  engine, exact hunk locations, exact context and deletion matching, no offset
  search, no fuzz, no nearest-match, no three-way merge, no repair, no
  normalization; malformed, overlapping and self-inconsistent hunks fail closed;
  output is deterministic; and a produced post-image that does not hash to the
  approved digest refuses before any write.
- [x] The **Git adapter is fixed, read-only, shell-free, environment-minimal,
  bounded, and model-inaccessible** (§28.4), and the fixed-plumbing versus
  repository-verification distinction is explicit in code and docs.
- [x] The **clean-baseline definition** is stated and enforced, and **special
  index states** (assume-unchanged, skip-worktree, unmerged, gitlink) refuse the
  whole repository (§28.4). No custom Git index parser was built. Nothing is
  fetched and no remote is consulted.
- [x] The **tracked-target proof** requires exactly one ordinary stage-0 blob
  entry (§28.4).
- [x] The **hard-link policy** refuses any count other than one, and refuses
  when the count cannot be established (§28.5) — resolving §26.13 question 11
  for this writer only.
- [x] The **UTF-8 / line-ending / size policy** is stated and enforced by
  refusal, with no detection, conversion, normalization or repair (§28.7).
- [x] The **Windows metadata and replacement contract** uses `ReplaceFileW` with
  fail-closed flags, an exclusive sibling temp file, flush and `fsync`, no backup
  or journal, an attribute allowlist, and a post-write attribute re-check
  (§28.8).
- [x] **Final pre-write revalidation** re-establishes canonicalization, file
  kind, reparse state, link count, bytes, pre-image digest and Git state, and
  reuses no earlier result as authority (§28.6).
- [x] **Post-write verification** proves the exact post-image digest, exactly
  one dirty path, and an otherwise-clean repository, and does not require Git's
  diff text to match the approved diff text (§28.9).
- [x] **Pre-write refusal and post-attempt indeterminacy are distinct** (§28.10)
  with distinct exit codes (1 and 3); the indeterminate path never claims
  nothing changed, never retries, never rolls back, and never runs
  `git restore`.
- [x] **One new command** with five options (§28.11); no other command changed;
  no widening flag exists.
- [x] **No project verification command, no model call, no network call, no
  GitHub access, no branch, no commit, no push, and no PR** (§28.11).
- [x] **Tests use only synthetic Git repositories created under pytest
  `tmp_path`.** No real target project workspace was read or written by any
  test, and `C:\dev\mis_project`, `C:\dev\a8_oa`, `C:\dev\bible_reading_v2` and
  the `C:\dev` parent were not touched.
- [x] **Phase 5F2D (controlled verification) and Phase 5F2E (reviewer
  integration) remain PROPOSED and NOT AUTHORIZED.** L2 is not complete, no
  commit/push/PR exists, and no model-backed implementer exists.

### 28.13 Phase 5F2C-FU1 — Git execution isolation and Windows replacement correctness (DONE)

Phase 5F2C was reviewed before acceptance and six findings were returned. This
section records what was wrong and what was changed. **The supported input
domain was not widened**, and §27's rules were applied throughout: every finding
was closed by refusing an unsupported case, never by generalizing.

#### 28.13.1 `ReplaceFileW` was passing an unsupported flag

The original code defined and passed `REPLACEFILE_WRITE_THROUGH = 0x00000001`.
Microsoft's `ReplaceFileW` documentation states that flag is **not supported**,
so passing it claimed a durability guarantee the API does not provide.

`dwReplaceFlags` is now **exactly `0`**. The constant is gone; a single
`REPLACE_FILE_FLAGS = 0` remains so the value passed is pinnable by a test.
`REPLACEFILE_IGNORE_MERGE_ERRORS` and `REPLACEFILE_IGNORE_ACL_ERRORS` remain
absent for the original reason: both exist to make the call succeed when the
metadata contract could not be honored.

Durability is unchanged in substance and honest in description: the temp file is
written, flushed and **`fsync`ed before** the replacement call, and that is the
only durability claim made. `ReplaceFileW` is **not** replaced by `os.replace` —
the metadata-preserving architecture is deliberate and remains.

#### 28.13.2 Post-replacement cleanup was unsafe

The original helper deleted the temp file on a failed `ReplaceFileW`. A failed
replacement may have already changed filename or replacement state, so the
filesystem is indeterminate at that point and deleting the temp file could
discard the only intact copy of the new content.

Cleanup is now **asymmetric around the replacement call**:

- **Before** it — an exclusive-create failure, or a write/flush/`fsync` failure —
  the known temp file is this module's own private object and is removed. The
  destination is untouched, `WindowsStagingError` is raised, and the writer
  reports a **pre-write refusal**.
- **Once the call has been made**, `WindowsReplacementAttemptedError` is raised
  and **no automatic mutation of any kind is permitted**: nothing is deleted,
  renamed, restored or retried, and no Git mutation (`restore`, `checkout`,
  `reset`, `clean`, `stash`) is run. The temp file's *name* travels on the
  exception so a human can be told where to look, and the writer reports the
  existing **exit-3 indeterminate** outcome demanding inspection.

An unclassified failure from the write helper is treated as the *more* serious
outcome, because it cannot be proved to have happened before the call.

#### 28.13.3 The fixed argv did **not** prevent repository-controlled execution

This was the most serious finding, and the original Phase 5F2C reasoning was
simply wrong. It assumed:

```text
literal "git" + fixed argv + shell=False  =  no repository-controlled execution
```

Git runs clean, smudge and process **filters** — commands configured through
`filter.<driver>.*` and selected by `.gitattributes` — from inside a perfectly
fixed argv. Reproduced against a real `git` binary in a synthetic `tmp_path`
repository, a repository-configured `filter.evil.clean` executes during:

- `git diff -- <path>`; and
- **`git status --porcelain` on a wholly clean tree**, whenever a tracked path's
  cached stat data is stale. A bare `touch` is enough: Git must re-hash the file
  to prove it is unchanged, and hashing a filtered path runs the filter.

The second case fires during the writer's very first preflight, against a
repository it would otherwise consider clean. That is a direct violation of the
Phase 5F2C boundary.

**The fix is a fail-closed configuration gate, not a Git reimplementation.** The
abandoned custom `.git` parser was *not* resurrected, and no generic command
executor was created. Instead:

> A repository whose effective Git configuration can cause filter or helper
> execution — or can *indirect* to configuration that could — is **unsupported**
> and is refused before any operation that reads working-tree content.

Two new fixed, read-only operations implement it, in this order and for this
reason:

1. `config --list --local -z --no-includes --name-only` answers "does this
   repository ask us to follow configuration somewhere else, and does its own
   file define anything execution-capable?" — **without following the
   indirection**, so the decision about whether includes are allowed is not
   itself made by processing them.
2. Only once that passes, `config --list -z --show-scope --name-only` covers
   every scope Git would actually apply, catching an execution-capable key
   inherited from the user's **global** config (git-lfs's `filter.lfs.*` is the
   common real-world case). The adapter's own `-c` hardening flags arrive in the
   `command` scope and are excluded; an unrecognized scope fails closed.

`--name-only` means **no configuration value ever enters the process**, so a
refusal can name a key with no risk of reporting a secret, a path, or a command
line. Refusal is on the key **name** alone — `filter.lfs.clean` pointing at
something benign is still refused, because deciding which configured command is
safe to run is exactly the judgement this phase declines to make.

The refused set is documented in `find_unsupported_config_keys` and covers, at
minimum: `filter.*` (clean/smudge/process/required), `include.path`,
`includeIf.*`, `extensions.*` (worktree config in particular), `core.fsmonitor`,
`core.hooksPath`, `core.pager`, `core.editor`, `core.sshCommand`,
`core.gitProxy`, `core.askpass`, `core.alternateRefsCommand`,
`core.attributesFile`, `core.excludesFile`, `diff.external`,
`diff.<x>.command`/`textconv`, `merge.<x>.driver`, `difftool.*`, `mergetool.*`,
`credential.*`, `pager.*`, `alias.*`, `protocol.*`, `ssh.*`, `gpg.program`,
`sequence.editor`, `uploadpack.packObjectsHook`, and
`remote.<x>.uploadpack`/`receivepack`/`proxy`/`vcs`.

The pre-existing disabling of fsmonitor, external diff, textconv, the pager,
askpass and terminal prompting **remains** — each is correct on its own terms —
but it is no longer described as, or relied on for, neutralizing filters.

**Residual scope note.** This is a narrow contract, and it is deliberately
over-broad in one direction: a machine with git-lfs configured globally will
have its repositories refused. That is the intended failure direction.

#### 28.13.4 Git gate ordering

The old order asked `git status --ignore-submodules=none` before it knew the
index was gitlink-free, so the status walk could descend into a submodule the
writer was about to refuse anyway. The order is now stated as **data**, in
`ordered_preflight_operations()`, so a test can assert it rather than trusting a
comment:

```text
resolve trusted absolute Git executable
        ↓
rev_parse_show_toplevel      safe metadata: no working-tree content read
rev_parse_head
        ↓
config_list_local            reject unsupported Git configuration
config_list_scoped
        ↓
ls_files_stage               reject gitlinks / unmerged stages / odd index tags
ls_files_verbose
        ↓
status_porcelain             ONLY NOW: working-tree cleanliness
        ↓
target tracked proof         (from the already-fetched index rows)
```

`CONTENT_READING_OPERATIONS` names the operations that can make Git open a
tracked file, and a test asserts every one of them sorts after every gate. The
same order runs again during the final pre-write revalidation.

#### 28.13.5 Executable selection was ambient

`GIT_EXECUTABLE = "git"` is not good enough for a component described as
AIDO-owned fixed Git plumbing: Python recommends a fully-qualified path, and
Windows resolution of a bare name follows a search order this project does not
control.

`resolve_git_executable(workspace_root=...)` resolves Git via `shutil.which` over
this process's own `PATH`, and then requires the result to be an absolute path to
an existing regular file that is **not inside the target workspace** — the
repository being edited may not supply the program that inspects it. The resolved
path is threaded through every `run_fixed_git_operation` call in the run.

The invariant is stated precisely, because an earlier draft of this section
overstated it as "resolved before any workspace use". That is not what the code
does, and the documentation is corrected rather than the code moved: the writer
canonicalizes the approved target and probes its filesystem metadata *first*, and
only then resolves Git. Those probes are `lstat`/`GetFileInformationByHandle`
calls made by this process — they launch nothing. The property that actually
matters is therefore:

> **Git is resolved to one absolute executable path before any Git invocation or
> child process is launched; a candidate inside the target workspace is refused;
> and the same resolved path is reused for the whole run.**

No code was moved to make the older sentence true. There is no independent
runtime reason to resolve Git earlier — the filesystem probes cannot be
influenced by which `git` binary would later be chosen — and documentation
describes the implementation, not the other way round.

`git_executable` is a **required keyword argument with no default** on both
`build_git_argv` and `run_fixed_git_operation`, and an unqualified value raises
`GitExecutableError`. There is therefore no silent fallback to `"git"`, no
project config field, no model/user/artifact input, and no search of the target
workspace. The bare `GIT_EXECUTABLE` constant is gone.

#### 28.13.6 Output was measured after capture, not bounded during it

`subprocess.run(..., capture_output=True)` reads everything and *then* compares
against the cap, so the original "bounded output" claim was not true.

The adapter now uses `Popen` with stdout on a pipe and **stderr on `DEVNULL`**.
One pipe means a single-threaded read loop cannot deadlock, so stdout is read in
64 KiB chunks and the child is **killed the moment the cap is passed** — at most
one chunk beyond the cap is ever held in memory. A `threading.Timer` watchdog
kills the child at the timeout, so the mandatory time bound holds even for a
child that neither writes nor exits. Both overflow and timeout fail closed.

This is a genuine bound, not a narrowed claim, and it was achieved without
building a general process framework. Two consequences are recorded honestly
rather than hidden:

- **stderr is discarded.** It was never used to make a decision, and Git's
  stderr can contain paths and content this project's no-echo policy would have
  to strip anyway. `GitResult` has no `stderr` field.
- **Residual limitation.** The bound is on *output volume and wall time*, not on
  everything a hostile local repository could do. A repository crafted to make
  Git consume CPU or memory internally, or to produce output just under the cap
  on every call, is still capable of wasting local resources. Phase 5F2C is a
  single-writer, quiescent-workspace, locally-trusted-repository tool; it is not
  a sandbox, and it does not claim to be one.

#### 28.13.7 The report claimed no file was created

`files_created: false` was misleading: a successful write always creates one
ephemeral operational sibling temp file, which `ReplaceFileW` then consumes.

The exclusions block is now **target-scoped** — `target_files_created`,
`target_files_deleted`, `target_files_renamed` — and a new `operational_files`
block states the truth:

```text
operational_files.temp_sibling_used:                     true
operational_files.temp_sibling_consumed_by_replacement:  true
operational_files.temp_sibling_left_behind:              false
operational_files.directories_created:                   false
operational_files.backup_or_journal_files_created:       false
```

The facts this encodes: no approved target was ever created (`modify` only); one
ephemeral operational sibling may be created; a successful replacement consumes
it; a **safe pre-replacement** failure cleans it up; and after a replacement
attempt automatic cleanup is **forbidden**, so a leftover temp file is expected
in exactly that case and is reported to the human instead. **No journal and no
backup were added.**

The Git block additionally records `git_executable_absolute`,
`git_executable_outside_workspace`, `git_executable_pinned_for_run`,
`config_execution_surface_checked` and `unsupported_config_found`. The
executable **path itself is never reported** — it is an absolute filesystem
path, and this report carries none.

#### 28.13.8 Acceptance criteria for Phase 5F2C-FU1 (DONE)

- [x] `ReplaceFileW` is called with `dwReplaceFlags == 0`; the unsupported
  `REPLACEFILE_WRITE_THROUGH` constant is gone; neither "ignore errors" flag is
  used; `os.replace` did **not** replace `ReplaceFileW`; and a test pins the
  actual flag value reaching the Win32 call as zero.
- [x] Temp cleanup runs **only** before the replacement call. A test proves
  `_remove_quietly` is not called after `ReplaceFileW` is invoked and fails, and
  another proves a staging failure still cleans up its own temp file.
- [x] The Git filter escape is **reproduced against a real `git` binary** in a
  synthetic `tmp_path` repository, then proved closed: the repository is
  refused, the sentinel marker is never created, and no target write occurs.
  `filter.<driver>.process` is covered too.
- [x] Gate order is data (`ordered_preflight_operations`), asserted by test, and
  gitlinks are refused **before** `status` can descend into one.
- [x] The Git executable is absolute, resolved **before any Git invocation or
  child process is launched**, refused when inside the target workspace, pinned
  for the run, and never defaulted to the literal `"git"`.
- [x] stdout is bounded **during** capture with a kill on overflow, a watchdog
  enforces the timeout, and the residual resource-exhaustion limitation is
  recorded rather than hidden.
- [x] The result schema no longer claims no file was created; operational temp
  usage is explicit.
- [x] **No generalized writer feature was added.** No create, no multi-file, no
  protected writes, no transaction framework, no journal, no rollback, no crash
  recovery, no concurrency framework, and no generalized Git executor. The
  supported input domain of §28.1 is unchanged.
- [x] **Phase 5F2D (controlled verification) and Phase 5F2E (reviewer
  integration) remain NOT AUTHORIZED**, and the §27 roadmap pivot stands.
  *(History. Phase 5F2D has since been authorized and completed — §29 — and so
  has Phase 5F2E — §30. This line records what was true when 5F2C shipped.)*

## 29. Phase 5F2D — controlled verification slice (DONE)

**Status: DONE.** Phase 5F2D is the **first separately authorized capability in
this repository to execute repository-controlled code**. It shipped one new
command, `l2-verify-approved-file-edit`, one new project opt-in,
`controlled_verification`, and one new package,
`ai_dev_orchestrator.verification`.

The positive capability, in one sentence:

> Given one already-applied Phase 5F2C approved single-file modification, and one
> explicitly enabled project verification command from trusted project
> configuration, AIDO can prove that the workspace still represents exactly the
> approved post-image, execute exactly that configured verification process once
> under bounded conditions, capture and redact its output, then prove the
> Git-visible workspace state still contains only the approved modification.

**5F2C writes. 5F2D verifies. 5F2E reviewer integration is next and is not
authorized. L2 is still not complete.**

### 29.1 The architectural distinction this phase must not blur

Phase 5F2C's `workspace/git_adapter.py` is **AIDO-owned fixed repository
inspection**: a closed, hard-coded set of read-only Git commands that exists to
make the writer's own correctness claims true. No repository content selects what
it runs.

Phase 5F2D is **explicitly authorized execution of repository/project-controlled
code**. A verification command such as pytest can import arbitrary project
modules, execute `conftest.py`, create files, access other filesystem paths, open
network connections, spawn child processes, and read whatever environment it is
given.

```text
controlled invocation  !=  sandboxed execution
```

AIDO is **not** sandboxing the project in Phase 5F2D. That is stated in the code,
in the report schema, and here, because the failure mode this phase most needs to
avoid is a safety report that overstates what it established.

The report therefore **must not** claim, and has no field capable of claiming:

- that verification made no network access;
- that verification touched only allowed paths;
- that verification could not launch child processes;
- that verification could not access credentials;
- that verification was side-effect free.

The `capability_boundaries` block splits along exactly that line. The
`orchestrator_*` and action fields are `Literal[False]` — properties of a module
that imports no client, opens no socket, and has no Git-mutation, GitHub, branch,
commit, push or PR capability at all. The `child_process_*` fields are
**strings**, and every one of them reads `"not sandboxed"`. A boolean there would
invite `false`, and `network_called: false` as a claim about the whole invocation
would be a lie.

### 29.2 `required_verification` is never command authority

The L1 plan carries `required_verification`. It is planner-controlled prose, and
a model may have written it. Phase 5F2D never:

- splits it;
- parses it as shell syntax;
- runs it;
- transforms it into argv;
- uses it to select an executable;
- uses it to add or remove an argument.

A plan that says `pytest tests/foo.py`, `rm -rf …`, or `curl …` changes
**nothing** about which process runs. The field is read exactly twice in
`verifier.py` — once to bind it, once to take its `len()` for the report — and a
test asserts that with an **AST walk** rather than a text scan, so the module's
(deliberately extensive) prose about the field cannot make the assertion pass.
`runner.py`, the module that actually launches processes, does not mention the
field at all.

Execution authority is exactly: the project config's `controlled_verification`
block, plus two explicit CLI flags.

### 29.3 The project config block

```yaml
controlled_verification:
  enabled: false
  executable: "C:\\absolute\\path\\to\\python.exe"
  args:
    - "-m"
    - "pytest"
    - "tests/test_targeted.py"
    - "-q"
  timeout_seconds: 120
  max_output_bytes: 200000
```

- absent block == disabled; `enabled` defaults false;
- exactly **one** configured verification command in this first slice;
- the executable has **no default** and is never looked up on `PATH`; it must be
  an absolute path to an existing regular file, validated at run time;
- `args` is an exact ordered argv tail, strings only, NUL refused, used
  **verbatim** — no interpolation, no environment substitution, no `{path}`
  template, no model or artifact substitution, no shell-syntax interpretation;
- cwd is always the canonical configured repository root; there is no
  working-directory override field.

The resulting argv is exactly `[configured_absolute_executable, *configured_args]`
and nothing else.

Deliberately **absent**, each because adding it would either turn a
per-invocation decision into standing configuration or widen a capability this
phase does not have: any shell command string, multiple command profiles, command
ids, before/after hooks, a retry setting, an install or dependency step, and any
environment or secret forwarding field.

Shape validation (blank, NUL, non-string args, bound ranges) happens in the
pydantic model. Absoluteness, existence, file-kind and workspace separation are
**run-time** properties and are checked at the gate, so a disabled or absent
block can never make an unrelated command fail to load.

### 29.4 The executable must resolve outside the target workspace

For this first slice, a verification executable that canonicalizes inside the
target workspace is **refused**.

The verification process may still execute project code **from** the workspace —
that is the capability being authorized. What may not come from inside it is the
program that launches that code. Without this rule an ignored `.venv` or a
project-supplied binary becomes a second mutable executable target inside the
very tree whose state this phase is trying to pin down, and the whole point of
the pre/post state binding is that the executable's identity does not move
underneath it.

Comparison is canonical, and inability to establish separation is treated as
"not separate" — the caller refuses on that answer. This restriction may be
revisited if real project usage proves workspace-local virtual environments are
required. **It is not solved now.**

### 29.5 The child environment

A fixed minimal allowlist, never a copy of `os.environ`: `PATH`, `SystemRoot`,
`SystemDrive`, `ComSpec`, `windir`, `TEMP`, `TMP`, `PATHEXT`, and the two
processor variables — the OS/runtime variables a Windows child needs to
initialize and a test runner needs to find its tools.

Never forwarded, with **no configuration field that could add them**:
`AIDO_LITELLM_*`, `GITHUB_TOKEN`, any `*_API_KEY` / `*_SECRET` / `*_TOKEN` /
`*_PASSWORD`, database and cloud credentials, and `GIT_DIR` / `GIT_WORK_TREE` /
`GIT_INDEX_FILE` / `GIT_CONFIG`. The allowlist result is re-filtered against a
forbidden-fragment list, so a careless future widening of the allowlist fails
loudly instead of leaking.

A project whose tests require credentials is **outside this first supported
domain and may fail**. That is accepted, and the report states that environment
forwarding is minimal and that no project-configured secret forwarding exists.
*(**Narrowed by §29.13.5.** "No project-configured secret forwarding" also read
as a claim about argv, which is passed verbatim. The report now claims exactly
`environment_forwarding_configurable: false` and states separately that AIDO does
not prove configured args contain no sensitive literal.)*

### 29.6 The CLI command, separate from the writer

```text
l2-verify-approved-file-edit
  --project-config
  --approved-diff-proposal
  --apply-approved-plan
  --verify-approved-file-edit
  --format
```

Five options, asserted as a set by test. The writer did **not** gain a
verification flag: write and verification remain independently invokable
capabilities. There is no `--command`, `--executable`, `--args`, `--shell`,
`--verification`, `--force`, `--repair`, `--retry`, `--commit`, `--push`, `--pr`
or `--model`, because the executable and args are project-config authority, not
CLI authority.

Both explicit action flags are checked **before any input file is read**, and the
remaining order is the writer's, with one substitution: config → the
`controlled_verification` opt-in → the Windows-only platform check → the
lexical rejection of an `--approved-diff-proposal` inside the configured
workspace (before it is opened or stat'd) → the strict parse → the verifier.

### 29.7 Pre-execution state binding

Verification is authorized for the exact already-applied approved change and for
nothing else. Before any process is launched:

**Artifact/config gates.** The same strict approved-diff parsing and the same six
exact identity comparisons the writer uses; exactly one change; `modify` only;
protected, forbidden and unlisted targets refused; `allow_symlinks == false`;
`deny_outside_workspace == true`.

**Canonical target.** The Phase 5F2B write-target guard re-run read-only: inside
the canonical workspace, existing, regular, no symlink or reparse point, one
supported target. Nothing is created, opened for writing, or modified.

**Exact post-image.** The target is read bounded by
`workspace_write.max_file_bytes` and must satisfy

```text
sha256(current_target_bytes) == approved post_image_sha256
```

Verification does **not** run against the pre-image, a partially edited file, a
file where the diff merely "still applies", or a different change.

**Git state**, using the same safe fixed machinery in the same safe order — safe
metadata, then the configuration gate, then the index gate, and only then
anything that reads working-tree content:

- workspace top-level == configured workspace root;
- `HEAD` exists;
- the Git configuration execution surface satisfies the writer's supported
  inspection contract (a repository that could run a filter is refused **before**
  `status` reads working-tree content);
- simple index: no gitlink, no unmerged stage, no assume-unchanged, no
  skip-worktree, no unusual index tag;
- the target is tracked as exactly one ordinary stage-0 blob;
- the Git-visible dirty state is **exactly** the approved target;
- that target's status is an **unstaged modification** (`" M"`);
- nothing staged, nothing else unstaged, nothing untracked, no deletion, rename,
  unmerged entry or submodule state.

This is the verification baseline, and it differs from the writer's on purpose:

```text
writer baseline:
    zero dirty paths

verification baseline:
    exactly one approved dirty target
```

The distinction is not weakened anywhere.

### 29.8 The execution

`verification/runner.py` owns one operation: execute the exact configured
verification argv once. It is deliberately **not** a general process executor,
and `git_adapter.py` was **not** turned into one — there is no public "run
arbitrary command" utility anywhere in the repository.

- configured absolute executable only; fixed configured args;
- `shell=False`; canonical repo root as cwd; `stdin=DEVNULL`;
- one execution only — no retry, no fallback executable, no PATH search;
- a bounded wall-clock timeout enforced by a `threading.Timer` watchdog that
  kills the child; *(**superseded by §29.13.1.** That arrangement did not
  actually bound anything: the main thread read the pipe, and a descendant with
  inherited standard handles kept it open past the deadline. The read now happens
  on a daemon thread and the main thread returns at a monotonic deadline. The
  bound is on **AIDO's wait**, not on the child's life.)*
- output bounded **during** capture, with the child killed the moment the cap is
  passed; *(**This was not true as shipped either** — see §29.14.1. The reader
  used a fixed 64 KiB blocking `read` and tested the cap only afterwards, so a
  child that passed the cap and then stopped writing was discovered only when the
  timeout fired. The read strategy now requests `min(remaining + 1, 64 KiB)` via
  `read1`, making the sentence accurate, and the over-limit bytes are dropped
  rather than retained.)*
- `stdout=PIPE` with `stderr=STDOUT`, so exactly **one** pipe exists and a
  single-threaded bounded read loop cannot deadlock. Merging rather than
  discarding stderr is the one deliberate difference from the Git adapter: a test
  runner's diagnostics are the very thing a human needs to read, whereas the
  adapter never used stderr for a decision.

No generic multi-stream process framework was built.

### 29.9 Output capture and redaction

Verification output can contain source text, paths, credentials, tokens, stack
traces and environment-derived values.

**Bounding happens first.** Redacting text that was already truncated does not
make the truncation honest. If output exceeds the cap the child is killed, the
outcome is "did not pass", the report records `output_limit_exceeded` and sets
`output.complete` to `false`, and **truncated output is never presented as
complete**.

**Redaction happens second, through the Phase 5D2 implementation** — not a second
detector. The helper was extracted **unchanged in behavior** to
`ai_dev_orchestrator/redaction.py`, and the CLI's Phase 5D2 names are now aliases
onto it. Two independently maintained secret detectors drift, and the one that
drifts is the one that silently stops catching a shape the other still catches.
Phase 5D2 behavior was not weakened, narrowed, or made configurable, and there is
still no off switch. Redaction remains a **backstop, not a guarantee**, and the
report says so in a `redaction_note` field rather than only in documentation.

### 29.10 Result semantics and exit codes

A process returning non-zero is **not** an AIDO internal error. It is a valid
verification outcome, and it produces a typed `verification-result.v1` report.

```text
outcome: "verified" | "verification-failed" | "workspace-state-untrusted"
```

| Exit | Meaning |
| --- | --- |
| `0` | Verification passed and the workspace is still exactly the approved change. |
| `1` | **Refused before project command execution.** Missing flag, disabled config, invalid artifact, identity mismatch, wrong workspace state, target bytes ≠ approved post-image, invalid executable, executable inside the workspace. No process was started; stdout is empty. |
| `2` | **A process was started and verification did not pass** — non-zero return code, timeout, or output cap exceeded. The structured result is returned. Nothing is retried, repaired, restored, or committed. |
| `3` | **Verification ran, but the post-execution workspace state is not trustworthy.** Never reported as merely "failed": the repository state itself requires human inspection. No automatic repair, no `git restore`, no cleanup command. |

An untrusted workspace **outranks** a failing test run. A suite that fails *and*
leaves the repository changed is exit 3, because the repository state is the more
serious fact and the one a human must act on first. A non-zero test result with a
still-valid workspace is exit 2.

### 29.11 Post-execution workspace verification

After the verification process terminates, times out, or is killed for output
overflow — **including** in those failure cases, because a killed process may
well have changed the tree before it died — the workspace state is re-established
before the result is finalized:

1. re-canonicalize the approved target;
2. re-read its bounded bytes;
3. require the exact approved `post_image_sha256`;
4. re-run the safe Git configuration and index gates;
5. obtain status;
6. require the Git-visible state to still be exactly one unstaged modification of
   the approved target.

Any additional staged, unstaged, untracked, deleted, renamed, unmerged or
submodule state means **exit 3**, and it is **not cleaned up**. This deliberately
catches a verification process that altered tracked or untracked Git-visible
repository state.

**What it does not detect**, recorded in the report itself as
`workspace_postcondition.detection_limits` rather than only here:

- Git-ignored files;
- changes outside the repository;
- network effects;
- registry or system changes;
- spawned external services or processes left running;
- any filesystem change invisible to Git.

**No sandbox was built in this phase.**

### 29.12 Acceptance criteria for Phase 5F2D (DONE)

- [x] Two inherited documentation inaccuracies corrected first: the README's
  current-capability description of the Git adapter (absolute pinned executable,
  the FU1 configuration probes in the fixed set, execution-capable configuration
  refused before content-reading operations, `dwReplaceFlags == 0`, output
  bounded during capture), and §28.13's "resolved before any workspace use"
  claim, corrected to the accurate invariant **without moving any code**.
- [x] `controlled_verification` config block: absent == disabled, `enabled`
  defaults false, exactly one command, absolute executable with no default and no
  PATH lookup, exact argv list, NUL refused, no shell string, no cwd override, no
  interpolation, no secret forwarding, no profiles/ids/hooks.
- [x] The argv is exactly `[configured_absolute_executable, *configured_args]`,
  asserted by test, with shell metacharacters passed through as one opaque
  argument rather than interpreted.
- [x] A malicious sentinel `required_verification` is proved never to run and
  never to enter argv; an AST test proves the field is read only to count it; the
  runner module never mentions it.
- [x] Executable validation: unset, blank, relative, missing, directory, and
  workspace-local all refused, each before any process is launched.
- [x] Minimal child environment proved against a real child process: `AIDO_*` and
  `GITHUB_TOKEN` are set in the parent and absent in the child.
- [x] One new CLI command with exactly five options; both action flags checked
  before any file is read; the writer gained no verification flag.
- [x] Pre-execution binding: identity, single `modify`, policy, canonical target,
  exact approved post-image, and a Git baseline of exactly one approved unstaged
  dirty target — with clean, wrong-bytes, pre-image, second-dirty-file, staged,
  untracked, deleted, renamed, unmerged, assume-unchanged, skip-worktree, gitlink
  and executable-config repositories all refused.
- [x] One bounded execution: `shell=False`, canonical cwd, `DEVNULL` stdin, one
  combined stream, timeout kill, output-overflow kill, no retry. *(The timeout
  half of this was **not actually true as shipped** — see §29.13.1, which
  reproduced a 1.0s timeout returning after 60.30s and corrected the mechanism.)*
- [x] Return code 0 → exit 0; non-zero → exit 2 with a structured result;
  timeout → exit 2; output overflow → exit 2 with `output.complete == false`.
- [x] Output redacted through the **shared** Phase 5D2 helper, extracted rather
  than duplicated, with Phase 5D2 behavior unchanged and no off switch.
- [x] Post-execution proof, with synthetic commands that alter the approved
  target, modify a second tracked file, create an untracked file, and stage the
  approved target — each exit 3, each left unrepaired. A failing verification
  that changes nothing stays exit 2; a failing verification that dirties the tree
  becomes exit 3.
- [x] Absent capabilities proved: no model call, no orchestrator socket, no
  GitHub access, no branch, no commit, no push, no PR, no retry, no repair, no
  `git restore`, no Git mutation of any kind, and no command selected from an
  artifact, a model, or a plan. **The child process is explicitly not claimed to
  be confined.**
- [x] Every real execution test uses a synthetic Git repository under pytest
  `tmp_path` and a synthetic Python verification script. **No real target project
  was used.**
- [x] **No generalized writer capability was added.** No create, no delete, no
  rename, no multi-file writes, no protected writes, no transaction framework, no
  journal, no rollback, no crash recovery, no concurrency framework, and no
  generalized Git executor. The supported input domain of §28.1 is unchanged.
- [x] Phase 5F2E (reviewer integration) was NOT AUTHORIZED when this list was
  written, the §27 roadmap pivot stands, and no generalized writer work was
  inserted between 5F2D and 5F2E. *(Phase 5F2E has since been authorized and
  completed — §30 — so only the second and third clauses remain current status.)*

### 29.13 Phase 5F2D-FU1 — verification lifetime and post-state integrity (DONE)

Phase 5F2D was reviewed before acceptance and five findings were returned. All
five are fixed. **The verification capability was not broadened to fix any of
them** — two were real defects closed by narrow mechanism changes, and three were
claims the implementation could not support, closed by correcting the claim.

Nothing here adds a shell, arbitrary commands, multiple command profiles, a
retry, repair, `git restore`, sandboxing, a generalized process executor, a
process-tree management framework, writer expansion, or reviewer/fixer
integration.

#### 29.13.1 The claimed hard timeout was not a hard invocation bound

The original runner was::

    watchdog = threading.Timer(timeout_seconds, process.kill)   # background
    ...
    chunk = stream.read(_READ_CHUNK_BYTES)                      # main thread

and the reasoning was "the timer kills the child, so the read ends". **That
reasoning was wrong, and a synthetic repository proves it.**

Phase 5F2D explicitly permits the direct verification child to spawn descendants.
A descendant launched with inherited standard handles — which is simply what
`subprocess.Popen(...)` with `stdout=None` does — holds the **write end of the
same pipe**. Killing or exiting the direct parent does not close the handle the
descendant owns, so the pipe never reaches EOF and AIDO's main thread stays
blocked in `read()` until the descendant lets go.

Reproduced in this repository against a real synthetic parent/descendant pair
under `tmp_path`, on Windows, with no monkeypatching:

```text
configured timeout:            1.0 s
descendant lifetime cap:      60   s
OLD algorithm returned after: 60.30 s      <-- the bound did not exist
NEW algorithm returned after:  1.03 s
```

So the previous statement that Phase 5F2D had a hard wall-clock bound was false,
and §29.8's "a bounded wall-clock timeout enforced by a `threading.Timer`
watchdog that kills the child" described something that did not hold.

**The new invariant, stated precisely:**

> AIDO's verification invocation stops waiting and returns in bounded time when
> the configured timeout expires, even if a descendant inherited stdout/stderr
> and remains alive.

**The mechanism, deliberately the smallest one.** The blocking read moved to a
private daemon thread (`_BoundedOutputReader`); the main thread waits on that
thread's completion event with a monotonic deadline. At expiry it kills the
**direct** child, takes whatever the reader accumulated under a lock, and
**returns — abandoning the reader thread** rather than joining it. Reaping the
direct child after the kill is itself bounded, so the kill cannot become a second
unbounded wait.

Everything else is unchanged: one combined stdout/stderr stream, `shell=False`,
bounded capture, one launch, no retry.

Two consequences are recorded rather than hidden:

- The abandoned daemon thread holds the pipe's read end until the descendant
  closes it or the process exits. That is a known, bounded cost of *not* managing
  a process tree, and it is preferred to an unbounded wait.
- **This does not terminate descendants.** No job object, no `taskkill`, no
  process group, no `psutil`, no enumeration of children. A test asserts none of
  those appear in the module.

**Honesty in the schema.** The execution block now separates what was bounded
from what was stopped:

```text
execution.aido_wait_bounded:                 true
execution.direct_child_killed:               true | false
execution.descendant_processes_terminated:   "not tracked; descendants may
                                              still be running"
```

`descendant_processes_terminated` is a fixed **string**, not a boolean, for the
same reason the `child_process_*` fields are: a boolean invites `false`, and
`false` would read as "we checked". A timeout also now marks
`output_complete: false`, because abandoning the stream mid-flight means the
captured text is a prefix — previously only overflow did.

A run whose pipe is still held at the deadline is reported `timed_out` with no
return code **even if the direct child already exited**. That is the honest
answer: AIDO stopped waiting, so it has neither the whole output nor an exit
status it may report.

#### 29.13.2 HEAD identity was not bound across verification

The Git proof ran `rev-parse --verify HEAD` on both sides and **discarded the
answer**, establishing only that *a* HEAD existed. That is not the same
repository state.

A verification process running:

```text
git commit --allow-empty -m "side effect"
```

moves the baseline commit while leaving the approved target as an unstaged
modification. Every other postcondition still held —

```text
exact approved target bytes      ✓
exactly one dirty path           ✓
approved path reported as " M"   ✓
```

— and the run reported success against a repository whose history had changed
underneath it.

**The new invariant.** The exact HEAD object id is captured before the process is
launched, from the existing fixed `rev_parse_head` operation, and retained as
in-memory state only. Afterwards HEAD is obtained again through the same safe
fixed adapter and required to be **exactly equal**. A HEAD that moved, or that
cannot be re-established, is:

```text
outcome = workspace-state-untrusted
exit    = 3
```

Nothing is repaired, reset, or checked out. The id is **never written anywhere
and never reported as a value** — the report carries only
`workspace_postcondition.head_unchanged: true/false`, and a test asserts the
actual object id does not appear in stdout.

No branch-name pinning was added. The writer permits a detached HEAD, and what
matters here is preserving the exact baseline commit, not which ref points at it.

#### 29.13.3 Capability result fields made global claims about an unsandboxed child

The block correctly scoped `orchestrator_model_called`,
`orchestrator_network_called`, `orchestrator_github_accessed`,
`orchestrator_shell_invoked` and `orchestrator_files_written` — and then carried
these **unscoped**, all set to `false`:

```text
git_mutation_performed   branch_created   committed   pushed   pr_created
retry_attempted   automatic_repair_attempted
rollback_or_restore_performed   reviewer_or_fixer_invoked
```

Under this phase's own explicit model that is misleading. The child is not
sandboxed and may itself run Git, create a branch, commit, or push — and some of
those effects are not inferable from the final working-tree state at all, since a
`git push` leaves it untouched. A reader scanning `pushed: false` would take it
as a statement about the invocation.

Every AIDO-owned negative claim now carries an `orchestrator_` prefix, and a test
asserts that **every** key in the block begins with `orchestrator_` or
`child_process_`, with the old unscoped names proved absent.

The child half stays honest, and gained two fields:

```text
child_process_git_effects:  "not sandboxed; not observed beyond the
                             post-execution Git-visible state"
child_process_lifetime:     "not sandboxed; descendants are not tracked and
                             may still be running"
```

**No detection was added.** AIDO does not attempt to observe the child's Git,
network, or process effects; that is sandbox and process-audit scope and is not
authorized.

#### 29.13.4 `next_step` contained unprovable global claims

It read approximately "Nothing was committed, nothing was pushed, no branch was
created, no PR was opened…". None of that can be proven about an unsandboxed
child. It now scopes what AIDO did and admits what is unobserved:

```text
AIDO left the approved change uncommitted in the working tree for human review.
AIDO did not create a branch, commit, push, open a PR, call a model, contact
GitHub, or run a reviewer. The verification child was NOT sandboxed: effects
outside the post-execution Git-visible state — including network activity,
pushes, and processes left running — are not comprehensively observed, and this
report makes no claim about them. Phase 5F2E (reviewer integration) must be
explicitly authorized before this result flows any further.
```

The report now distinguishes *what AIDO did* from *what the verification child
may have done* in the schema itself, not only in explanatory prose.

*(Phase 5F2E note: the final sentence quoted above is the FU1 text. Since 5F2E
shipped, that sentence would be false — reviewer integration **is** authorized —
so the live string now says instead that AIDO ran no reviewer **while producing
this report**, and that a verified result may be taken to a configured reviewer
by the separate 5F2E command, whose verdict is advisory and ends with a human.
The scoping FU1 introduced is unchanged; only the stale authorization claim was
corrected. The Phase 5F2C writer's own `next_step` was corrected the same way.)*

#### 29.13.5 `project_configured_secret_forwarding: false` overstated what is proved

The environment genuinely is a non-configurable minimal allowlist, and that part
was correct. But the configured argv is passed **verbatim**, so a project config
could in principle contain:

```yaml
args:
  - "--api-key"
  - "literal-secret"
```

The project-wide rule is that secrets live in environment variables and never in
files, and args are trusted configuration data written by a human — but Phase
5F2D does not *prove* that an arbitrary argument string contains no sensitive
literal, and the old field name claimed the broader property.

The field became:

```text
command.environment_forwarding_configurable:  false
command.configured_args_trust_note:           "The configured args are trusted
    project-configuration data and are used verbatim. AIDO does not inspect them
    and does not prove that an arbitrary argument string contains no sensitive
    literal. They are never echoed into this report."
```

`ENVIRONMENT_FORWARDING_POLICY` was likewise reworded to speak only about the
environment: *there is no project-configurable environment-variable or credential
forwarding mechanism in this phase*.

**No heuristic argv secret detection was added**, and configured args are still
never echoed into the report — only `arg_count`.

#### 29.13.6 The post-execution state model after FU1

```text
canonical target still valid
        ↓
exact approved post-image still present
        ↓
same Git repository / valid HEAD
        ↓
HEAD object id exactly unchanged from pre-execution
        ↓
Git configuration gate still supported
        ↓
simple index / no gitlink / no unusual state
        ↓
exactly one dirty path
        ↓
approved target exactly " M"
```

Any failure after the verification process was started is
`workspace-state-untrusted`, exit 3. No repair, no retry, no restore.

#### 29.13.7 Acceptance criteria for Phase 5F2D-FU1 (DONE)

- [x] The timeout is a real bound on AIDO's wait, proved by a regression using a
  **real** synthetic process under `tmp_path` whose descendant inherits
  stdout/stderr and outlives the deadline while the direct parent exits. The
  runner returns within a small margin of the configured timeout, reports
  `timed_out`, `completed == false`, `passed == false`, `return_code is None`,
  and starts exactly one process. Not faked with a monkeypatch.
- [x] The regression cleans up its synthetic descendant after asserting, so the
  pytest process is not polluted.
- [x] Nothing claims descendants were killed. A test asserts the module contains
  no `taskkill`, job object, process group, `psutil`, or child enumeration, and
  that the bounded reader is private.
- [x] HEAD object id captured pre-execution and compared for exact equality
  post-execution; `git commit --allow-empty` with an otherwise identical approved
  state is exit 3, with the empty commit left in place and no reset or restore.
- [x] An ordinary passing verification leaves HEAD unchanged and returns exit 0;
  a failing verification with unchanged HEAD and workspace stays exit 2.
- [x] The HEAD object id never appears in the report.
- [x] Every capability-boundary key is scoped `orchestrator_*` or
  `child_process_*`; no global `"committed": false` / `"pushed": false` style
  claim survives anywhere in the report.
- [x] `next_step` scopes its claims to AIDO and states the child was not
  sandboxed and is not comprehensively observed.
- [x] Environment forwarding remains non-configurable and is claimed as exactly
  that; configured args are documented as unproven and are never echoed; no argv
  secret scanner exists.
- [x] `required_verification` remains non-authoritative, and no retry, repair,
  restore, generalized executor, or sandbox was added.
- [x] Every real Git/process test uses a synthetic repository and a synthetic
  program under pytest `tmp_path`. **No real target project was used.**
- [x] **Phase 5F2E (reviewer integration) remains NOT AUTHORIZED.**

### 29.14 Phase 5F2D-FU2 — exact output-cap enforcement and lifetime claim accuracy (DONE)

The final narrow follow-up for Phase 5F2D. One remaining runtime defect in the
process runner, plus two directly related contract inaccuracies. The verifier was
not redesigned and the verification capability was not broadened.

#### 29.14.1 The output cap was not enforced when it was passed

The private reader did:

```python
chunk = stream.read(_READ_CHUNK_BYTES)   # 64 * 1024
...
if self._total > self._max_output_bytes:  # tested only after read() returns
```

`BufferedReader.read(n)` blocks until it has **n** bytes or reaches EOF. So a
child that had already emitted more than the configured cap, and then stopped
writing, was **not** detected: the read sat waiting for a 64 KiB buffer that
would never fill. The documented contract —

> the child is killed the moment the configured output cap is passed

— was therefore false. The overflow surfaced only when more output happened to
arrive, when the child exited, or when the **timeout** fired, which also meant
the run was reported with the wrong outcome (`timed_out`) for the wrong reason.

The pre-existing flood regression could not catch this: it writes megabytes, so
the 64 KiB request fills immediately. This is a different failure shape.

**Measured against a real Windows pipe**, child writes 5001 bytes, flushes, then
sleeps 30s:

```text
read(65536)  -> returned after 30.1   s   (only once the child exited)
read1(5001)  -> returned after  0.078 s
```

**Measured end to end**, `max_output_bytes = 5_000`, child writes 5001 then
sleeps 120s, configured timeout 20s:

```text
OLD strategy: overflow never detected within the timeout; the run would have
              ended as a TIMEOUT after 20.00 s
NEW strategy: returned after 0.09 s
              output_limit_exceeded=True  timed_out=False  bytes_kept=5000
```

**The fix is a read strategy, not a framework.** Each iteration requests:

```python
request = min(remaining + 1, _MAX_READ_REQUEST_BYTES)
chunk = stream.read1(request)
```

`read1` performs **one** underlying read and returns as soon as any data is
available rather than waiting for the request to be filled. Once fewer than
64 KiB of allowance remain, the request is exactly `remaining + 1`, so the
arrival of that single sentinel byte *is* the proof that the cap was passed.
While more than 64 KiB of allowance remains, overflow is arithmetically
impossible in one read, so the 64 KiB ceiling only bounds the per-read
allocation.

**No asyncio, no selectors, no polling loop, no non-blocking mode, no generic
streaming API, no process supervisor.** The FU1 reader thread remains the
lifetime boundary, unchanged.

**The over-limit bytes are dropped, not stored.** The old code discarded the
entire overflowing chunk; the new code keeps exactly the bytes that fit and drops
the excess, so the reported output is at most the configured cap **exactly**.
Overflow remains `> cap`, not `>= cap`: a child that emits exactly the cap and
exits is a clean, complete, passing run.

#### 29.14.2 The new regression

A real synthetic Windows child under pytest `tmp_path`:

1. writes exactly `max_output_bytes + 1` bytes;
2. flushes;
3. sleeps far longer than the configured timeout.

```text
max_output_bytes   = 5_000
child output       = 5_001 bytes
configured timeout = 20 seconds
observed runner return: ~0.09 s
```

The test proves the runner returned because of **overflow, not timeout**:
`output_limit_exceeded is True`, `timed_out is False`, `completed is False`,
`passed is False`, `return_code is None`, `output_complete is False`,
`len(output_bytes) <= max_output_bytes`, exactly one AIDO `Popen`, and no retry.
Companion tests pin that exactly the cap is retained (`b"z" * 5000`), and that
output exactly at the cap is **not** an overflow.

The existing large-flood regression is kept — it covers the other shape — and its
assertion was tightened from "at most cap + one chunk" to "exactly the cap".

The command-level equivalents prove the same shape is **exit 2** with a trusted
workspace, and that an untrusted workspace still **outranks** an overflow: a child
that creates an untracked file *and* overflows the cap is exit 3, uncleaned.

#### 29.14.3 The exact timing contract

`_KILL_REAP_SECONDS = 5.0` meant statements like "the function returns at the
configured deadline" were not literally true in the worst case. Rather than build
new process management to remove the grace, the contract is made precise. The
constant is now public and named, and the two quantities are distinguished:

```text
configured execution/capture timeout   — from project config
fixed direct-child reap grace          — DIRECT_CHILD_REAP_GRACE_SECONDS, 5.0s,
                                         not configurable, not a second timeout
```

> The configured timeout bounds the execution and output-capture wait. After that
> deadline AIDO sends one kill to the direct child and may spend at most the
> fixed direct-child reap grace waiting for that one process handle. It never
> waits for descendants, and it never waits for the abandoned output reader.
> Worst-case AIDO wait is therefore the configured timeout plus the reap grace,
> and nothing else.

That text is `WAIT_BOUND_POLICY`, and the execution block of the report carries
it alongside `configured_timeout_seconds` and
`direct_child_reap_grace_seconds`. **No measured high-resolution timing is
reported, and no process id is exposed.**

#### 29.14.4 The abandoned reader's lifetime is not bounded

FU1's docstring described the abandoned daemon thread and its pipe handle as
"a bounded, known cost". That conflated two different things. The **AIDO wait**
is bounded; the **abandoned resource lifetime** is not — a descendant may retain
the inherited write handle indefinitely, and the reader thread and the pipe's
read end stay alive with it.

The corrected statement:

> Abandoning the daemon reader prevents its lifetime from extending the AIDO
> invocation; the reader and the pipe may themselves remain alive for as long as
> a descendant retains the inherited handle, possibly indefinitely.

This is a **documented residual limitation**. It was explicitly *not* fixed by
killing descendants, enumerating descendants, job objects, `taskkill`, process
groups, `psutil`, or any process-tree manager. No runtime expansion is authorized
here, and none was made.

#### 29.14.5 Outcome semantics are unchanged

```text
exit 1   refused before the project verification process was launched
exit 2   the process ran, verification did not pass, and the post-execution
         workspace proof still succeeds — output overflow lands here when the
         workspace is still trusted
exit 3   the process ran and the post-execution repository state is not provably
         the approved state; this still outranks overflow, timeout and a plain
         test failure
```

Nothing is repaired, restored, or retried at any exit code.

#### 29.14.6 Acceptance criteria for Phase 5F2D-FU2 (DONE)

- [x] Overflow is detected on the read that carries the first over-cap byte, via
  a `min(remaining + 1, 64 KiB)` `read1` request, without waiting for a
  fixed-size buffer to fill. Asserted against the read loop's own source, not the
  module text.
- [x] A real synthetic Windows child writing `cap + 1` bytes, flushing, then
  hanging far past the configured timeout causes a prompt overflow return
  (~0.09s against a 20s timeout) with `output_limit_exceeded`, `timed_out` false,
  `completed` false, `passed` false, `return_code is None`, `output_complete`
  false, one `Popen`, and no retry.
- [x] Retained output is at most the configured cap exactly; the over-limit bytes
  are dropped. Output exactly at the cap is not an overflow.
- [x] The large-flood regression is kept and tightened.
- [x] The timing contract distinguishes the configured timeout from the fixed
  direct-child reap grace, in prose and in the report, with no measured timing
  and no process id.
- [x] The abandoned reader's lifetime is documented as unbounded and as a
  residual limitation, with the earlier "bounded, known cost" phrasing corrected
  and attributed.
- [x] **No process-tree management, sandbox, generic process runner, streaming
  framework, or retry was added.** Asserted by tests over imports and the read
  loop.
- [x] FU1's fixes are intact: exact HEAD object id pinned pre/post, moved HEAD →
  exit 3 with no reset/checkout/restore, every AIDO negative action field
  `orchestrator_*`, child effects unsandboxed and unobserved, `next_step` scoped
  to AIDO, no claim that configured args are secret-free, and
  `required_verification` completely non-authoritative.
- [x] Every real execution test uses synthetic programs and repositories under
  pytest `tmp_path`. **No real target project was used.**
- [x] Phase 5F2E (reviewer integration) was NOT AUTHORIZED at the time this
  acceptance list was written. *(It has since been authorized and completed —
  see §30 — so this line is history, not current status.)*

## 30. Phase 5F2E — controlled reviewer integration (DONE)

> **Status: DONE.** This section describes what shipped.
>
> Phase 5F2C writes one approved file. Phase 5F2D asks the project's own
> verification process whether that change holds up. **Phase 5F2E is the first
> runtime capability in this repository that deliberately sends source-derived
> code to a model**, and the first that completes a useful controlled path:
>
> ```text
> human-approved concrete diff
>         ↓
> 5F2C applies the approved single-file modification
>         ↓
> 5F2E command
>         ↓
> existing 5F2D verification
>         ↓
> controlled model-backed reviewer
>         ↓
> one structured human-facing review packet
> ```
>
> **The verdict is advisory and the path ends at a human.** No fixer, no second
> reviewer, no retry after findings, no patch generation, no file edit, no
> revert, no branch, no commit, no push, no PR. **L2 as originally defined is
> still not complete.**

### 30.1 What shipped

One new CLI command, one new project-config block, one new package:

```text
l2-review-approved-file-edit          the command
controlled_review:                    the project opt-in (ships disabled)
ai_dev_orchestrator.review            models + parser, request builder,
                                      packet, and the verify-then-review ordering
```

The command's entire option surface is five options:

```text
--project-config
--approved-diff-proposal
--verify-approved-file-edit
--real-reviewer
--format
```

There is deliberately **no** `--model`, `--provider`, `--prompt`, `--message`,
`--command`, `--shell`, `--fix`, `--repair`, `--retry`, `--commit`, `--branch`,
`--push`, `--pr`, `--github`, `--fetch`, `--apply`, and **no
`--verification-result`**. Both action flags must be present before **any** input
file is read; a missing flag refuses immediately, having read nothing.

### 30.2 5F2E does not run the writer

The command starts from the exact state Phase 5F2C leaves behind: one approved
`modify`, the exact approved post-image present, exactly one Git-visible dirty
path, the approved target as a plain unstaged `" M"`, a valid HEAD, and a
workspace otherwise satisfying the accepted 5F2D contract. The operator still
invokes `l2-apply-approved-file-edit` separately.

### 30.3 Verify first, review second — and why the command runs the verifier

The command runs the **existing** 5F2D verification internally rather than
accepting a verification result as input. That is deliberate, and it buys four
things:

- the operator does not hand-carry a verification report into a reviewer;
- the verification is **fresh** for the review it informs;
- if reviewer configuration, network, or model parsing fails, the approved dirty
  change remains reviewable and the *same* command can be run again;
- reviewer credentials need not be loaded before repository-controlled
  verification runs.

A previously saved verification-result file is **never** trusted as authority,
and there is no input through which one could be supplied.

The accepted 5F2D library path is **called, not copied**. Its Git proof is not
duplicated into a parallel reviewer-specific implementation, and its outcomes
keep their meanings and their exit semantics exactly:

| 5F2D outcome | 5F2E behavior |
| --- | --- |
| pre-execution refusal | exit 1, no model call, no reviewer environment read |
| `verification-failed` | exit 2, report returned to the human, no model call, no reviewer environment read |
| `workspace-state-untrusted` | exit 3, report returned to the human, no model call, no reviewer environment read, nothing repaired |
| `verified` | proceed to the reviewer |

### 30.4 Reviewer credential ordering (load-bearing)

Before verification the command may read: the action flags, the project config,
the approved diff artifact, `controlled_review.enabled`, the configured reviewer
provider/model, and ordinary non-secret policy data. It must **not** read
`AIDO_LITELLM_API_KEY`, `AIDO_LITELLM_BASE_URL`, `AIDO_LITELLM_DEFAULT_MODEL`, or
any other reviewer credential or endpoint value.

Only after the verifier returns `verified` is the LiteLLM environment loaded and
the real reviewer client built. The reason is 5F2D's own model: that phase
deliberately executes **unsandboxed repository-controlled code**, and reviewer
credentials do not need to coexist in AIDO process state while it runs. The
environment reader is an injected callable, so the ordering is testable directly
rather than by inspection.

Reviewer credentials are **not** forwarded to the verification child, and 5F2D's
environment policy is unchanged.

### 30.5 The project opt-in

```yaml
controlled_review:
  enabled: false
  provider: "litellm"
  model: "qwen3-coder-next"
```

- an absent block is identical to an explicitly disabled one;
- `enabled` defaults to `false` and ships disabled;
- `provider` currently supports only the existing internal OpenAI-compatible
  LiteLLM path, `"litellm"`; the *shape* is validated at load and *support* is
  enforced at the review gate, so a mis-set block in a disabled project cannot
  make an unrelated command fail to load its config (the 5F2D `executable`
  precedent);
- an enabled block requires a non-blank **exact** model string. No glob, no
  prefix, no case folding, no CLI override, and no environment default;
- there is no `api_key`, `base_url`, endpoint, credential, environment-variable
  name, prompt template, header, retry count, or fixer configuration, and
  `extra="forbid"` rejects one.

**`real_model_planning` is not reviewer authorization.** Planning authorization
and review authorization are separate capabilities, and neither block is
consulted on the other's behalf. No generic implementer/fixer role configuration
was introduced for symmetry: this phase implements the reviewer role only.

### 30.6 The source-to-reviewer boundary

The reviewer receives **only**:

1. trusted identity — project id, repo name, issue number, issue title, and one
   **repo-relative** approved target path;
2. selected approved-plan context — summary, scope summary, non-goals, proposed
   steps, risks, open questions;
3. the one approved unified diff from `approved-diff-proposal.v2`;
4. verification facts from the freshly completed 5F2D result — `verified`,
   passed, the already-bounded and redacted output text, and the detection-limit
   language that bounds what it proves.

It never receives `repo.workspace_path`, any absolute path, the configured Git
executable path, the configured verification executable path, an API key, a base
URL, raw environment, a GitHub token, unrelated source files, a directory
listing, a repository tree, git history, a repository status dump, the entire
current target file, raw unredacted verification bytes, the approval text, or the
raw input artifact JSON.

The approved diff is sufficient source context for this first reviewer slice.
**Whole-file transmission was not added.** The plan's `required_verification` is
not transmitted either: it is command-shaped planner prose, and this phase keeps
it away from every consumer that might read it as an instruction.

### 30.7 Redaction before transmission

Project-controlled text — the approved diff, the L1 prose fields, and the
verification output — passes through the repository's one shared secret-like
redactor before it is placed in the prompt, into a **review-context copy**. The
authoritative artifact and the verification report are never mutated. The packet
records that redaction was applied and reports safe counts and kinds.

**Redaction remains a best-effort backstop, not a guarantee.** Nothing in the
code or the packet claims the transmitted material is secret-free.

### 30.8 Prompt-injection boundary

Plan text, unified diff text, comments and string literals inside source, and
verification output are **untrusted data**. The reviewer system prompt says so
explicitly, and the Phase 4 model-planner discipline is reused narrowly rather
than generalized into a sanitization framework:

- trusted instructions live in the system message, which carries **no project
  data at all**, so instructions and data are separated by message role as well
  as by markers;
- **every** free-form project-controlled value sits inside explicit
  `<<<UNTRUSTED_PROJECT_TEXT>>>` delimiters — and "every" is meant literally,
  because two classes of value initially escaped it and both were corrected
  before acceptance:
  - the **identity strings** (`project_id`, `repo`, `title`, `target_path`) were
    rendered bare under a header calling them trusted. Their *provenance* is
    orchestrator-owned and authoritative; their *text* is still third-party, and
    an issue title ending in a closing delimiter was a real injection path. Only
    the numeric `issue_number` and the fixed `change_type` literal are rendered
    outside a block, because neither can carry free-form text;
  - the **list-valued plan fields** (`non_goals`, `proposed_steps`, `risks`,
    `open_questions`) were neutralized per item but never quoted, so a
    multi-line, instruction-shaped plan step reached the model as prose in the
    orchestrator's own voice. Each list is now rendered and quoted as **one**
    delimited block — including when it is empty, so the boundary is a property
    of the field rather than of whether it happened to have content;
- any delimiter occurring **inside** supplied text is neutralized first, so
  supplied content cannot close the block early and continue as apparent
  instructions. Neutralization happens exactly once, in the quoting helper;
- the reviewer is told not to follow instructions found in source comments,
  string literals, diffs, plan prose, or verification output, and to record such
  attempts in `human_notes` instead.

**The human-facing stderr warning is a separate surface, and the issue title is
not printed on it.** A terminal has no delimiters: a title containing newlines
and banner-shaped lines could forge lines in a non-suppressible safety notice and
misrepresent what is being transmitted. Rather than add terminal escaping or a
sanitizer for one cosmetic field, `ReviewerCallNotice` has **no `title` field at
all**, so the banner cannot print one — it identifies the run by project, repo
and issue number. The real title still travels in the model request (delimited)
and in the review packet.

### 30.9 The reviewer request and the strict response

`build_model_review_request` is pure and deterministic: the same trusted inputs
produce the same `LLMRequest`. No clock, no randomness, no environment read, no
client, no transport. The model is the exact `controlled_review.model`; the
environment's default model can never override it.

The request asks for **review only**, and explicitly prohibits the reviewer from
writing replacement file contents, generating an applyable patch, invoking tools,
executing commands, selecting a different file, requesting branch/commit/push/PR
actions as orchestrator authority, claiming it made changes, or asserting
verification results different from the supplied facts. It may recommend what a
human or a later fixer should consider, as plain review prose.

The reply must be exactly one strict JSON object:

```json
{
  "verdict": "approve | changes_requested | needs_human_review",
  "summary": "short review summary",
  "findings": [
    {
      "severity": "blocker | major | minor | nit",
      "category": "correctness | security | testing | scope | maintainability | other",
      "line": 123,
      "message": "what is wrong and why",
      "suggested_action": "plain-language recommendation"
    }
  ],
  "residual_risks": [],
  "human_notes": []
}
```

`line` may be `null`. No markdown fence, no prose before or after,
`extra="forbid"` everywhere. **No trusted field is accepted from model output** —
project id, repo, issue number, title, target path, model, endpoint, verification
outcome, approval identity, branch, commit, PR, command, executable, patch/diff,
and file contents are each rejected *by name* so an injection attempt surfaces as
what it is.

Validation is fail-closed and **never repairs**: at most 20 findings, no blank
summary/message/suggested-action, a positive `line` when present, bounded string
and list sizes, closed severity/category enums, `changes_requested` requires at
least one `blocker` or `major`, `approve` must carry none, and
`needs_human_review` is unconstrained. Duplicate findings are preserved — there is
no semantic merging.

Invalid JSON, schema violations, contradictory verdict/severity combinations and
extra fields are **reviewer failures**. There is no second prompt, no
"please fix your JSON" retry, and no parser repair. Precisely: **one semantic
reviewer request** is issued; the existing `LLMClient` keeps its already-shipped
bounded *transport*-level retries, which are a transport property and not a
re-review. No application-level re-review logic was added.

> **Superseded by §31 (Phase 5F2E-RS1).** The parser is still strict and still
> never repairs, but the request policy changed: the reviewer client now forces
> transport `max_retries=0`, and a project may authorize **one** bounded compact
> second semantic attempt. The maximum is two semantic attempts, one HTTP/model
> request each. The paragraph above is preserved as history.

### 30.10 The review packet

> **Superseded by §31.12.** The artifact is now `review-packet.v2`: it preserves
> every block below, adds a `reviewer_supervision` block, and replaces the
> hard-coded `orchestrator_review_retry_or_reprompt_attempted` field with
> truthful ones. `review-packet.v1` keeps its original meaning for archived
> packets. The description below is preserved as history.

On success the command prints one `review-packet.v1` artifact in
`controlled-review` mode, carrying orchestrator-owned identity plus:

- **target** — repo-relative path and `change_type: modify`;
- **verification** — the freshly generated, validated `VerificationResultReport`,
  **embedded unchanged** rather than summarized into something weaker, so its
  detection limits and child-process caveats travel with the review;
- **reviewer provenance** — provider, exact configured model, endpoint **host
  only** (via the existing safe host-reduction helper), operation `code-review`,
  `real_call: true`, one semantic request, and token usage when the response
  supplies it. Never a base URL, an API key, headers, or an absolute path;
- **review** — the strict validated verdict, summary, findings, residual risks
  and human notes;
- **transmission boundary** — explicit booleans for what was and was not sent,
  plus the redaction counts/kinds and a note that redaction is not a guarantee;
- **capability boundaries** — see §30.11;
- **human decision** — the terminal next step.

The approved diff is deliberately **not** re-echoed into the packet: it already
exists in the artifact the operator approved, and copying source text into a
second file buys no review benefit.

### 30.11 Truthful capability scoping

This command really does two consequential things, and the packet says both
plainly:

```text
orchestrator_model_called: true
orchestrator_network_called: true
orchestrator_repository_controlled_code_executed_by_verification_stage: true
```

So there is **no blanket `network_called: false` and no `commands_run: false`**
for the invocation. Every negative claim carries the `orchestrator_` prefix, and
several are scoped further to the review *stage*:

```text
orchestrator_files_written_by_review_stage: false
orchestrator_workspace_read_by_review_stage: false
orchestrator_verification_rerun_after_review: false
orchestrator_fixer_invoked: false
orchestrator_second_reviewer_invoked: false
orchestrator_review_retry_or_reprompt_attempted: false
orchestrator_patch_generated_from_findings: false
orchestrator_file_edit_from_findings: false
orchestrator_automatic_repair_attempted: false
orchestrator_rollback_or_restore_performed: false
orchestrator_branch_created: false
orchestrator_committed: false
orchestrator_pushed: false
orchestrator_pr_created: false
orchestrator_github_accessed: false
```

Child-process facts stay where they were honestly established — inside the
embedded verification report — and the packet points at them rather than
restating or weakening them.

### 30.12 Exit codes, and the human as the terminal step

```text
0  a valid structured review — for approve, changes_requested AND
   needs_human_review alike. All three are successful reviewer completions,
   not AIDO runtime errors.
1  refused before anything ran.
2  verification ran and did not pass. No model was contacted.
3  verification ran and the repository is no longer provably the approved
   state. No model was contacted, and nothing was repaired.
4  verification PASSED and the reviewer stage failed — environment/client
   setup, transport under the existing client policy, non-strict JSON, or
   schema/policy validation.
```

**Exit 2 and exit 3 are scoped the same way.** The exit-2 message originally
ended "nothing was retried, repaired, restored, or committed" — but the
unsandboxed verification child had already run, so `committed` was a claim about
the invocation rather than about AIDO. Both messages now say only what is
established: no reviewer was contacted and no reviewer environment value was
read; the returned Phase 5F2D report is what establishes the approved bytes, the
unchanged HEAD object id and the expected Git-visible dirty state; AIDO performed
no retry, repair, restore, or reviewer-stage action; and the child was not
sandboxed, so effects outside Phase 5F2D's documented detection boundary are not
claimed. **No Git inspection or child-effect detection was added** to say more.

**Exit-4 claims are scoped to AIDO's review stage, and that scoping is load
bearing.** By the time a reviewer-stage failure is possible, the **unsandboxed**
Phase 5F2D verification child has already run. An unscoped "no file was written,
no Git state was changed, no branch/commit/push/PR happened" would be a claim
about the whole invocation, and this phase cannot make it: a verification child
may write Git-ignored files, write outside the repository, reach the network,
push, create an additional ref that leaves HEAD and the worktree unchanged, or
leave descendants running — and Phase 5F2D deliberately does not observe those
effects.

What exit 4 does state, in three separated parts:

1. **AIDO's review stage** repaired nothing, restored nothing, retried nothing,
   re-prompted nothing, wrote no file into the target workspace, performed no Git
   mutation, and created no branch, commit, push or PR. The error output carries
   no raw model response, no API key, no base URL, and no echoed approved diff.
2. **The verification that had already passed** established the approved target's
   exact bytes, a HEAD object id equal to the one the run started from, and a
   Git-visible dirty state of exactly that one unstaged path — subject to the
   same quiescent, single-actor limitation.
3. **Nothing beyond that boundary is claimed.** The verification child was not
   sandboxed, and Phase 5F2E makes no additional claim about effects outside
   Phase 5F2D's documented detection boundary. **No child-effect detection, no
   branch scanning, and no sandboxing were added** to narrow it.

The operator can correct the reviewer configuration and run the same command
again.

A completed verdict is **not executable authority**. There is no automatic next
action of any kind. The human decides.

### 30.13 The old "Phase 6 — qwen reviewer" roadmap entry is superseded

The top-level roadmap in
[AI_DEV_ORCHESTRATOR_PLAN.md §7](AI_DEV_ORCHESTRATOR_PLAN.md#7-mvp-phase-roadmap)
listed **Phase 6 — qwen reviewer**. That milestone is **absorbed by and
superseded by Phase 5F2E's configurable controlled reviewer integration**. 5F2E
does not hard-code Qwen: a project configures an allowed internal reviewer model
in `controlled_review.model`, and pointing it at a Qwen model is a configuration
choice, not a phase. **No separate qwen-only integration phase is now required.**

Phases were deliberately **not renumbered**, and **Phase 7 (fixer) remains
separately unauthorized**.

### 30.14 Acceptance criteria (all met)

- [x] One new command with exactly five options, and none of the forbidden ones.
- [x] Both action flags are required before any input file is read.
- [x] `controlled_review` ships disabled; absent == disabled; enabled requires a
  non-blank exact model; unsupported provider refused; no credential, endpoint,
  prompt template, header, retry count or fixer field, with `extra="forbid"`.
- [x] `real_model_planning` does **not** authorize review.
- [x] The accepted 5F2D verifier is **called**, not duplicated, and its refusal /
  exit-2 / exit-3 semantics are preserved exactly.
- [x] Reviewer credential environment names are not read until verification
  returns `verified` — proved by ordering, not merely by final output.
- [x] The exact configured model is used; the environment default cannot override
  it; there is no CLI override.
- [x] The prompt carries the approved diff, selected plan context and the
  verification facts, and carries no full target file, unrelated source,
  absolute path, workspace path, approval text, or credential.
- [x] Project-controlled text is redacted into a transmission copy without
  mutating the artifact, and is delimited as untrusted data that injected
  delimiters cannot escape.
- [x] The request builder is pure and deterministic.
- [x] The response parser is strict and never repairs: fences, prose, extra
  fields, trusted-field injection, over-long lists, blank strings, invalid enum
  members and contradictory verdict/severity combinations are all rejected.
- [x] Exactly one semantic reviewer request; no application-level retry or
  re-prompt; a reviewer-stage failure is exit 4 and leaks no raw response,
  API key, base URL, or diff.
- [x] `approve`, `changes_requested` and `needs_human_review` all exit 0.
- [x] The packet validates as `review-packet.v1`, embeds the validated 5F2D
  result, takes identity from the orchestrator, reports the endpoint as a host
  only, does not re-echo the approved diff, and admits the model/network call
  and the repository-controlled execution while scoping every negative claim.
- [x] Every Git/workspace/verification test uses synthetic `tmp_path`
  repositories and synthetic verification programs; **no real target project was
  touched**.
- [x] Every reviewer test uses `httpx.MockTransport`; **no real model call, no
  socket, and no API key is needed**.
- [x] Phase 5F2C, 5F2D, `generate-plan`, `generate-model-plan` and
  `real-llm-smoke-test` behavior is unchanged.
- [x] **No generalized writer, command executor, fixer, review/fix loop, second
  reviewer, full-file transmission, branch, commit, push, PR, or GitHub write was
  added.**
- [x] The old Phase 6 "qwen reviewer" roadmap entry is explicitly reconciled
  (§30.13); Phase 7 / fixer remains unauthorized.

## 31. Phase 5F2E-RS1 — bounded reviewer runtime supervision (DONE)

> **Status: DONE, as corrected by §31.16 (FU1) and §31.17 (FU2).** This section
> describes what shipped, and it **supersedes two specific claims in §30**: that
> "exactly one semantic reviewer request" is made, and that the output artifact
> is `review-packet.v1`. Everything else in §30 — the verify-then-review
> ordering, the credential ordering, the transmission boundary, the strict
> never-repaired parser, the advisory verdict, and the exit codes — is unchanged.
>
> **Read §31.16 and §31.17 with this section.** RS1's first draft made a
> timed-out attempt retry-eligible, which contradicted its own (correct)
> statement that a client timeout proves nothing about the backend. **FU1**
> corrected that: a stall is terminal, the retry is limited to a *completed but
> unusable* response, the opt-in is `compact_retry_on_unusable_output`, and the
> resource claim was narrowed. **FU2** then established the wait bound the phase
> had only been asserting: httpx's timeout is a network-operation/inactivity
> timeout, not an absolute deadline around `client.chat()`, so AIDO now owns a
> monotonic deadline of its own. The text below already reflects both
> corrections.

### 31.1 The production motivation

The requirement came from a real multi-AI workflow failure mode observed with
**local** reviewer models: a reviewer can consume substantial resources and still
produce nothing a human can act on.

For a local model, cost is not an API line item. It is:

- inference wall time;
- GPU occupancy;
- concurrent-request capacity;
- context occupancy.

Phase 5F2E issued one reviewer request and waited. That is adequate against a
hosted endpoint that either answers or errors promptly. Against a local model it
is not: a stalled generation held a slot indefinitely, and — worse — the generic
client's *hidden* transport retries could turn that one stalled semantic review
into three full inference requests that nobody asked for and nothing recorded.

RS1 makes **AIDO's reviewer request issuance and wait budget** bounded, owned,
and auditable. It does *not* bound the backend's own inference — see §31.5 and
§31.16.

### 31.2 What RS1 can observe, and what it deliberately cannot

The reviewer here is **not an agent**, and the existing `LLMClient` is **not
streaming**. There are no tool calls, no reviewer file reads, no reviewer test
runs, and no partial-generation events. So RS1 classifies attempts using only
facts this architecture actually produces:

| Observable | Used for |
| --- | --- |
| the request returned a response | success path |
| the request raised `LLMTimeoutError` | `review_stalled` |
| the request raised another typed `LLMClientError` | auth / response / transport classification |
| `finish_reason` | `review_output_budget_exhausted` |
| `usage`, when supplied | attempt accounting (unknown when absent) |
| content empty / non-empty | feeds the strict parser |
| strict parser accepted or rejected the reply | `valid_review` / `review_unusable_output` |

And the explicit non-list. RS1 does **not** compute embedding or reasoning
similarity, inspect chain-of-thought, ask the model to expose its reasoning, poll
tokens, open an SSE or streaming connection, count tool calls, count files the
reviewer inspected, count tests the reviewer ran, measure time-to-first-token or
time-to-first-finding, or add a generic event bus. **None of those are honestly
observable here**, and a report containing them would be fabrication.

The distinction, stated once:

```text
observable resource supervision        <-- what RS1 is
private reasoning / agent progress     <-- what RS1 is NOT
supervision
```

RS1 is resource-budget supervision for a **one-shot** reviewer. It is not an
agent-loop supervisor, and it must not grow into one here.

### 31.3 Retry ownership (load-bearing)

The generic `LLMClient` has bounded transport retries. With `max_retries = N`,
one `client.chat(...)` may produce **N + 1** HTTP/model requests on timeout,
transport error, HTTP 429, or HTTP 5xx. That is correct for the generic Phase 3
client and **wrong as hidden retry ownership for a supervised local reviewer**.

So, for the controlled reviewer only:

```python
LLMClientConfig(..., max_retries=REVIEWER_TRANSPORT_MAX_RETRIES)   # == 0
```

`build_reviewer_client_config` **overrides** the environment-derived value. The
consequences are exact:

- **one semantic reviewer attempt == one HTTP/model request**;
- the supervisor, not the transport, owns any second attempt;
- an authentication failure, a non-retryable 4xx, a 429, a 5xx, or a connection
  refusal costs **one** request and surfaces immediately.

**Nothing global changed.** The generic client keeps its shipped retry loop and
its `max_retries` default of 2; `AIDO_LITELLM_MAX_RETRIES` keeps its meaning for
every other caller; and the planner and smoke-test paths are untouched. A
regression test proves the counterfactual directly: the same environment that
gives the reviewer *one* request per attempt still gives a generic client
*three*.

The same builder also replaces the connection timeout with
`controlled_review.attempt_timeout_seconds`, so the reviewer's bound is the
project's declared reviewer budget rather than whatever generic value the
environment carried.

### 31.4 The project config extension

```yaml
controlled_review:
  enabled: false
  provider: "litellm"
  model: "qwen3-coder-next"
  attempt_timeout_seconds: 90            # finite, > 0, <= 3600
  max_output_tokens: 2048                # positive, bounded (<= 32000)
  compact_retry_on_unusable_output: false  # default OFF
```

- `extra="forbid"` still applies, and there is **no** `fallback_model`, no
  `reviewer_chain`, no `reviewers`, no `secondary_model`, no attempt-count field,
  no backoff setting, no retry prompt, and **no retry-on-timeout field**;
- every field has a safe default, so **existing Phase 5F2E project configs load
  unchanged**;
- the field is named for what it actually covers. RS1's draft called it
  `compact_retry_on_stall`, which became actively misleading once a stall was
  made terminal (§31.16). It is **not** retained as an alias: `extra="forbid"`
  rejects it, so a stale draft config fails loudly rather than silently keeping
  the wrong semantics;
- `compact_retry_on_unusable_output` defaults to **false**. That is the
  fail-closed choice this repository's discipline calls for: a second model call
  is a small capability addition, and a project that never opted into it keeps
  exactly the accepted 5F2E behavior of one semantic request. The shipped example
  config sets it explicitly rather than relying on the default;
- the maximum number of semantic attempts is a **constant**, not configuration:
  `MAX_SEMANTIC_REVIEW_ATTEMPTS = 2`;
- there is **no CLI override** for any of these. The command's option surface is
  still exactly the accepted five options.

### 31.5 Timeout truthfulness

**Two mechanisms share one configured number, and only one of them is the
proof** (see §31.17):

```text
httpx timeout           = network-operation / inactivity timeout. It fires when
                          an individual socket operation stalls. A peer that
                          keeps producing activity often enough can hold one
                          request open far past the configured value without any
                          single read ever reaching its timeout.

RS1 supervisor deadline = an AIDO-owned monotonic wall-clock deadline around ONE
                          `client.chat(request)` call. It fires on total elapsed
                          wait, whatever the network was doing.  <-- THE PROOF
```

`attempt_timeout_seconds` therefore means: **the maximum time AIDO waits for the
reviewer HTTP/model call to complete**, subject only to small local scheduling
overhead. The reviewer's client still receives the same value as a *secondary*
network-inactivity timeout, which is useful — and is explicitly not what
establishes the bound.

AIDO may truthfully say:

- the reviewer request used the configured value as its wait deadline;
- if the client reported `LLMTimeoutError`, **or** if AIDO's own deadline expired
  first, the attempt is classified `review_stalled` (distinguished only by
  `stall_source`, for auditing — nothing branches on it);
- **AIDO stopped waiting.**

AIDO must **not** say:

- that the HTTP request ended when AIDO stopped waiting;
- that the worker performing the call was stopped, terminated, or cancelled — it
  is **abandoned** (§31.17);
- that a remote or internal backend stopped inference at the same moment;
- that this is a process-style hard wall-clock kill of the Phase 5F2D kind;
- that the abandoned worker's lifetime, backend inference lifetime, GPU
  occupancy, backend context lifetime or server-side cancellation latency is
  bounded by this phase. **Total GPU time is not bounded here.**

Backend cancellation semantics are **outside this phase's observation boundary**,
and the packet says so in `reviewer_supervision.timeout_semantics_note`,
`reviewer_supervision.wait_bound_note` and
`reviewer_supervision.supervision_scope_note`. No multiprocessing, no streaming,
no cancellation request, and no thread-kill mechanism was added to manufacture a
stronger-sounding claim; the single daemon worker of §31.17 exists only so the
main thread can stop waiting.

**That asymmetry is why a stall is terminal.** Retrying after a stall would mean
issuing a second request while the first may still be generating on the same
local model — see §31.16. RS1 therefore bounds AIDO's *request issuance* and
AIDO's *wait*, and says so exactly:

```text
RS1 PROVES                              RS1 DOES NOT PROVE
transport retries issued by AIDO = 0    abandoned worker lifetime
<= 2 semantic requests issued by AIDO   HTTP request lifetime after AIDO stops
an AIDO-owned monotonic deadline on       waiting
  each attempt's wait                   backend inference lifetime after a stall
requested max output tokens             GPU occupancy after client disconnect
completed-response retry policy         backend context lifetime
                                        server-side cancellation latency
```

### 31.6 The output-token budget

Each reviewer request sets the **existing** `LLMRequest.max_tokens` field, which
the existing client already serializes into the OpenAI-compatible payload. No
second transport abstraction was added, and `LLMRequest` was not changed.

The packet reports this as a **requested** cap. Provider semantics differ, and it
says nothing about hidden reasoning or backend accounting. Reported `usage` is
whatever the provider actually returned; when a provider returned none, usage is
recorded as `usage_reported: false` / `usage: null` — **unknown, never an
invented zero**.

### 31.7 Attempt 1

Attempt 1 is the accepted Phase 5F2E full request, unchanged: the same
source-transmission boundary, the same untrusted-data delimiters, the approved
diff, the selected plan context, the verification facts and output, the same
strict review JSON schema, `temperature = 0`, and the exact configured model. The
only addition is the configured `max_tokens`.

It is exactly one `client.chat()` and — because reviewer `max_retries == 0` —
exactly one HTTP/model request.

### 31.8 The two retry-eligible conditions, and only those

One compact second semantic request is issued **only** when
`compact_retry_on_unusable_output == true` **and** attempt 1 returned a
**completed but unusable** response, for one of exactly these reasons:

| Condition | Classification |
| --- | --- |
| `finish_reason` indicates output-length exhaustion (`length`, `max_tokens`, `max_output_tokens`) and no valid review resulted | `review_output_budget_exhausted` |
| a response was returned and strict parsing/validation did not produce a valid `ModelReviewResult` | `review_unusable_output` |

What the two share is the whole justification: **the first HTTP/model response
was actually returned to AIDO**, so the first request is no longer an unknown
in-flight operation occupying the backend.

The second case is **not parser repair**. Attempt 1's reply is discarded whole as
an invalid review, and a separate, explicitly bounded review request is issued.
Attempt 1's JSON is never modified, never partially mined for findings, never
quoted into the second prompt, and never merged with attempt 2.

**No compact retry** for: a timeout (`review_stalled` — terminal, §31.16),
`ReviewerEnvironmentError`, authentication failure, non-retryable HTTP 4xx,
generic connection refusal, HTTP 429, HTTP 5xx, any other service-availability or
transport failure, the retry finding cap — or an already valid structured review,
including `changes_requested` and `needs_human_review`.

### 31.9 The compact retry request

`build_compact_model_review_request` is pure and deterministic, exactly like the
full builder, and it uses the **same** configured reviewer model. There is no
model switch anywhere in the code path.

It carries a **strict subset** of what the full request already carried:

| Kept | Dropped |
| --- | --- |
| authoritative identity | plan summary |
| plan scope summary | plan proposed steps |
| plan non-goals | plan risks |
| the one approved unified diff | plan open questions |
| verification facts | |
| bounded, redacted verification output | |
| the same detection-limit language | |

**No new source is added**, so the compact attempt cannot widen the accepted
transmission boundary. It still never sends the full target file, unrelated
files, a workspace path, an absolute path, a credential, the raw environment, the
raw artifact, or the approval text, and every free-form value is still inside the
accepted untrusted-data delimiters.

The output schema is **identical** — the strict `ModelReviewResult` is not
changed for the retry. The instruction changes only the review posture, in
substance:

> Review only the supplied changed diff, scope/non-goals, and verification
> evidence. Return at most 5 concrete findings. Do not perform generic checklist
> enumeration. Do not repeat observations merely to fill space. If the supplied
> context is insufficient, use `needs_human_review`. Return the same strict JSON
> review object and nothing else.

The retry-specific cap of **5 findings** is enforced **after** strict parsing: a
retry result carrying more is `review_retry_finding_cap_exceeded` and unusable.
It is rejected, never truncated. The 20-finding bound still applies to a full
first attempt.

There is still no third attempt.

### 31.10 The human circuit-breaker signals

Three concise stderr notices, and the wording distinguishes them because they are
genuinely different failures. None of them prints the prompt, the diff, a
completion, an API key, a base URL, or an absolute path — the event object has no
field capable of carrying one.

```text
=== REVIEW STALLED ===                      <-- TERMINAL. No retry follows.
  model, the attempt number, the review_stalled classification,
  that AIDO stopped waiting for the request,
  that backend cancellation / inference termination is NOT observed,
  that NO compact retry is being issued and why,
  that the reviewer is unavailable and a human decision is required

=== REVIEW UNUSABLE — compact retry authorized ===
  ONLY for a completed but unusable response: model, attempt 1 of 2,
  the classification, exactly one compact retry, same model,
  no fallback reviewer selected
  (a parse error is NEVER called "stalled", and a stall is never
   announced as a retry)

=== REVIEWER UNAVAILABLE FOR THIS REVIEW ===
  exact configured model, attempts used of at most 2, final failure
  category, no fallback reviewer contacted, human decision required
```

A timed-out run prints `REVIEW STALLED` followed by `REVIEWER UNAVAILABLE`, and
its **attempts used is 1** — the output must never look as though two requests
were issued.

### 31.11 Second-attempt failure, and success

If no attempt produces a valid review — attempt 1 timed out, attempt 1 failed for
a non-retryable reason, or the one compact retry also failed: no further semantic
request, no transport retry, no fallback model, no fixer, no workspace mutation,
no re-verification, and no repair or restore. The command returns the **existing**
reviewer-stage failure family and **exit 4** — deliberately preserved rather than
given a new exit code merely for wording. The raw response text is never exposed.

A valid second-attempt result is a **successful review**: exit 0, and all three
verdicts keep their meanings and stay advisory. No fixer follows.

### 31.12 `review-packet.v2`

Adding attempt metadata is a material schema change, so the packet was
**evolved**, not silently redefined:

```text
review-packet.v1  Phase 5F2E     one semantic request, generic transport
                                 retries in effect and unreported
review-packet.v2  Phase 5F2E-RS1 reviewer transport retries forced to 0,
                                 at most two supervised semantic attempts,
                                 full attempt accounting
```

`v1`'s meaning is preserved as history in the packet itself
(`superseded_schema_version_note`) so an archived packet stays legible and is not
reinterpreted under `v2` rules.

`v2` preserves every accepted `v1` block — orchestrator-owned identity, target,
the embedded `VerificationResultReport`, reviewer provenance, the validated
review, the transmission boundary, truthful capability boundaries,
`human_decision_required`, `next_step` — and adds one narrow block:

```text
reviewer_supervision:
  supervision_enabled: true
  supervision_scope: "orchestrator_request_issuance_and_wait_budget"
  max_semantic_attempts: 2
  semantic_attempts_used: 1 | 2
  transport_retries_per_attempt: 0
  transport_requests_per_attempt: 1
  compact_retry_enabled: <bool>
  compact_retry_used: <bool>
  compact_retry_finding_cap: 5
  timeout_attempt_is_terminal: true
  attempt_wait_bound: "orchestrator_monotonic_deadline"   <-- NOT httpx timeout
  backend_inference_lifetime_if_stalled: "Conditional policy, ... IF ..."
  abandoned_worker_lifetime_if_supervisor_deadline_expires: "Conditional ..."
                                          ^^^ both STRINGS, never bools, and both
                                              CONDITIONAL — see below
  configured_attempt_timeout_seconds: <float>
  requested_max_output_tokens: <int>
  first_attempt_outcome: <classification>
  final_attempt_outcome: <classification>
  attempts:
    - attempt, kind (full|compact), outcome, transport_requests,
      requested_max_output_tokens, finish_reason, usage_reported, usage,
      elapsed_seconds, stall_source (client_timeout | supervisor_deadline | null)
  same_model_used_for_every_attempt: true
  fallback_reviewer_model_available: false
  supervision_scope_note / retry_ownership_note /
  compact_retry_policy_note / timeout_semantics_note /
  wait_bound_note / output_cap_note / observability_note
```

**Two kinds of field live in this block, and conflating them was a real defect.**

*Facts about this run*: `semantic_attempts_used`, `compact_retry_used`,
`first_attempt_outcome`, `final_attempt_outcome`, and each record in `attempts`
with its `outcome` and `stall_source`.

*Conditional policy*: `timeout_attempt_is_terminal`,
`backend_inference_lifetime_if_stalled` and
`abandoned_worker_lifetime_if_supervisor_deadline_expires`. Both of the latter are
**strings**, following the Phase 5F2D `child_process_*` precedent — AIDO cannot
observe either, so neither may be reported as a boolean claim in either direction
— and both are worded from an explicit **IF**.

That conditional wording is load-bearing. A supervision block only ever reaches a
packet on the **success path**: a stall is terminal, raises
`ReviewerAttemptExhaustedError`, and the command exits 4 with no packet at all.
So in every packet that exists, no attempt outcome is `review_stalled`, every
`stall_source` is `None`, and **no abandoned worker was left behind**. An earlier
draft stated these fields as facts (`abandoned_worker_lifetime_after_deadline:
"...the worker thread is abandoned rather than stopped..."`), which made an
ordinary successful run read as though a worker had been abandoned in it. The
fields now describe what *would* be known after a future stall and explicitly
disclaim asserting that one happened.

`attempt_wait_bound` exists so a reader cannot mistake the client's
network-inactivity timeout for the proof, and `stall_source` records which
mechanism ended a wait — `supervisor_deadline` is precisely the case in which an
abandoned worker would exist. Nothing branches on it.

No prompt and no raw completion is retained. **This is not a generalized event
log** — it is one fixed block with one record per attempt.

Two provenance fields changed shape: `reviewer.semantic_requests` is now an
integer fact about this run rather than the literal `1`, joined by
`max_semantic_requests: 2`, `transport_retries_per_semantic_request: 0`, and
`fallback_model_configured` / `fallback_model_used`, both fixed `false`.

**One capability-boundary field was removed rather than left lying.**
`orchestrator_review_retry_or_reprompt_attempted` was a hard-coded `false`; under
RS1 it would have been false only when the compact retry did not run. Its
replacements are truthful:

```text
orchestrator_bounded_compact_retry_used:              <real boolean>
orchestrator_third_semantic_attempt_made:             false
orchestrator_parser_repair_attempted:                 false
orchestrator_partial_findings_merged_across_attempts: false
orchestrator_fallback_reviewer_model_used:            false
```

Every negative claim still carries the `orchestrator_` prefix, and the
child-process facts still live only inside the embedded verification report.

### 31.13 Attempt timing

Elapsed attempt duration is recorded with a **monotonic** clock, and the clock is
**injectable** so unit tests assert durations deterministically. It is reported as
*measured elapsed time* for AIDO's own wait — never as guaranteed backend
inference time, and never as time-to-first-token or time-to-first-finding. Timing
is not an authority boundary: nothing branches on it, and no generic metrics
framework was built.

### 31.14 RS2 — explicit reviewer failover (DEFERRED, NOT AUTHORIZED)

A future candidate, **documented here and deliberately not implemented**:

```text
RS2 — Explicit Reviewer Failover
```

Automatic model failover is a **separate authority decision**, because it would
send the approved source-derived diff to *another model*. RS1 uses only the
already-authorized `controlled_review.model`. There is no `fallback_model`, no
`reviewer_chain`, no `reviewers`, and no `secondary_model` field anywhere, and
none may be added without an explicit, separate prompt.

### 31.15 Acceptance criteria (all met)

- [x] Reviewer transport `max_retries` is forced to **0**, proved with a
  `MockTransport` returning retryable failures; the generic client's behavior,
  its default, and `AIDO_LITELLM_MAX_RETRIES` semantics are unchanged for every
  other caller.
- [x] One semantic attempt == one HTTP/model request; the maximum in one review
  command is **two**.
- [x] `controlled_review` gained exactly three fields, all with safe defaults;
  existing configs still load; non-positive/non-finite `attempt_timeout_seconds`
  and non-positive/unbounded `max_output_tokens` are rejected; `extra="forbid"`
  still rejects `fallback_model`, `reviewer_chain`, `reviewers`,
  `secondary_model`, an attempt count, a retry prompt, a transport retry count,
  any retry-on-timeout field, and the superseded draft name
  `compact_retry_on_stall`. No CLI override was added — the command still has
  exactly five options.
- [x] Both requests carry the exact configured `max_tokens` through the existing
  `LLMRequest` field; no second transport abstraction was added.
- [x] The compact retry fires only for the two documented **completed-response**
  conditions, uses the **same** configured model, sends a strict subset of the
  accepted transmission boundary, keeps free-form text inside the untrusted
  delimiters, and enforces its 5-finding cap by rejection after parsing.
- [x] **A stall is terminal** (§31.16): it costs exactly one request even with
  the compact option enabled, and is never announced as a retry — whether the
  client reported the timeout or AIDO's own deadline expired first (§31.17).
- [x] **AIDO's wait is bounded by AIDO's own monotonic deadline** (§31.17), not
  by httpx timeout semantics, proved by a fake client with no transport at all.
- [x] Auth failure, 400/404, 429, 5xx and connection errors each cost exactly one
  request and get no compact retry.
- [x] A valid review — `approve`, `changes_requested` or `needs_human_review` —
  never triggers a retry.
- [x] `REVIEW STALLED` is used only for a timeout; a parse or length failure is
  announced as `REVIEW UNUSABLE`; the terminal notice is `REVIEWER UNAVAILABLE
  FOR THIS REVIEW`. No notice carries a prompt, diff, completion, credential,
  base URL, or absolute path.
- [x] A second-attempt failure returns the existing exit **4**; a valid
  second-attempt result exits **0**.
- [x] The packet is `review-packet.v2`, preserves every `v1` block, records
  attempts and known usage, records missing usage as unknown rather than zero,
  states that a timeout is terminal and that backend inference lifetime is
  unobserved, and reports no unobservable signal and no claim that backend or GPU
  time is bounded.
- [x] No fallback reviewer, no fixer, no review/fix loop, no second reviewer, no
  consensus, no model-backed implementer, no branch, no commit, no push, and no
  PR was added.
- [x] Every workspace/Git/verification test uses synthetic `tmp_path`
  repositories and synthetic verification programs; **no real target project was
  touched**. Every reviewer test uses `httpx.MockTransport`; **no real model
  call, no socket, and no API key is needed**.
- [x] Phase 5F2C, 5F2D and the accepted 5F2E behavior are unchanged apart from
  the explicitly authorized move from "at most one semantic review request" to
  "at most two supervised semantic requests AIDO may issue, one transport request
  each".

### 31.16 Phase 5F2E-RS1-FU1 — terminal timeout and truthful scope (DONE)

> **Status: DONE.** RS1 was **not accepted** as first drafted. Its core
> retry-ownership implementation was sound, but acceptance was blocked by one
> architecture contradiction plus two narrow truthfulness cleanups. This
> subsection records the correction; §31.1–§31.15 above already describe the
> corrected behavior.

#### The blocker: RS1 retried after an unconfirmed timeout

RS1 stated, correctly, that `attempt_timeout_seconds` is only the existing
request/transport timeout and that AIDO does **not** observe or prove that the
backend stopped inference when the client timed out.

And then it made `review_stalled` retry-eligible and immediately issued a second
request to the same model. Those two things cannot both be right.

```text
request 1 reaches a local inference backend
  -> the client times out
  -> AIDO stops waiting
  -> the backend may STILL be running, holding its slot and context
  -> AIDO immediately sends compact request 2
  -> the same local model may now hold TWO concurrent inference jobs
```

That can **increase** GPU occupancy, concurrent-request pressure, context
occupancy and total inference resource usage — the precise failure mode this
phase exists to contain. A client timeout is not evidence that the inference slot
was released, and this architecture has no way to obtain that evidence.

So, with the current observable architecture:

```text
LLMTimeoutError
  -> review_stalled
  -> REVIEW STALLED  (terminal wording, no retry announced)
  -> REVIEWER UNAVAILABLE FOR THIS REVIEW
  -> exit 4, attempts used = 1
```

**Nothing was added to guess around it.** No sleep, no backoff, no polling, no
cancellation request, no streaming, no threads, and no Run:AI- or
LiteLLM-specific cancellation behavior. A timeout may become retryable only in a
future, **separately authorized** phase in which AIDO gains an observable,
trustworthy backend-cancellation acknowledgement.

#### Correction 1 — retry eligibility narrowed to completed responses

```python
RETRY_ELIGIBLE_OUTCOMES = (
    "review_output_budget_exhausted",
    "review_unusable_output",
)
```

`review_stalled` is **not** in it. What the two survivors share is the property
that makes a retry safe: a response was **actually returned to AIDO**, so the
first request is no longer an unknown in-flight operation.

Everything else stays terminal, unchanged: authentication failures, non-retryable
4xx, 429, 5xx, connection/transport failures, the compact finding-cap failure, a
valid review (terminal success), and no third attempt.

#### Correction 2 — the config field was renamed before acceptance

`compact_retry_on_stall` became actively misleading the moment a stall was made
terminal. Because RS1 had not been accepted, the public name was fixed rather
than carrying a misleading compatibility alias forever:

```yaml
controlled_review:
  enabled: false
  provider: "litellm"
  model: "qwen3-coder-next"
  attempt_timeout_seconds: 90
  max_output_tokens: 2048
  compact_retry_on_unusable_output: false
```

- default remains `false`; `extra="forbid"` still applies;
- `compact_retry_on_stall` is **not** retained as an alias — an old RS1 draft
  config using it now fails loudly rather than silently retaining wrong
  semantics;
- no generic retry-enabled field, no retry-on-timeout field, no max-attempt
  field, and no CLI override.

#### Correction 3 — the resource-bound claim was narrowed

RS1 prose sometimes said "the reviewer runtime is bounded" and "the reviewer
resource envelope is bounded". Both are stronger than the implementation can
prove, because a timed-out backend may continue inference. The exact contract is
now:

> **RS1 bounds AIDO's reviewer request issuance and AIDO's wait budget.**
>
> It proves: reviewer transport retries issued by AIDO = 0; at most 2 semantic
> requests issued by AIDO; the configured timeout applied to each request wait;
> the requested max output tokens; and the completed-response retry policy.
>
> It does **not** prove a bound on: backend inference lifetime after a timeout;
> GPU occupancy lifetime after a client disconnect; backend context lifetime; or
> server-side cancellation latency.

The phase is still called "Reviewer Runtime Supervision", and its documentation
defines that scope exactly. **Total GPU time is never claimed to be bounded.**

#### Circuit-breaker wording

`REVIEW STALLED` is now a **terminal** notice. It states the model, the attempt,
the `review_stalled` classification, that AIDO stopped waiting, that backend
cancellation / inference termination is **not** observed, that **no** compact
retry is being issued and why, and that a human decision is required. It never
says "compact retry authorized", and the run reports **attempts used = 1**.

`REVIEW UNUSABLE — compact retry authorized` is emitted only for a completed but
unusable response, immediately before the one compact request.

#### Packet wording (still `review-packet.v2`)

RS1 had not been accepted, so this is a correction to the **draft** v2 semantics,
not a v3 evolution. No new packet version was created. The supervision block now
states explicitly that a timeout is terminal because backend cancellation is
unobserved, that the compact retry is only for a completed but unusable response,
that the maximum AIDO may **issue** is two, and that none of this proves the
backend's inference lifetime is bounded — carried by the new
`supervision_scope`, `timeout_attempt_is_terminal`,
`backend_inference_lifetime_if_stalled`, `supervision_scope_note` and
`compact_retry_policy_note` fields.

#### Stale Python contracts corrected

Current, non-historical docstrings that still claimed "no second prompt",
"retries nothing", "re-prompts nothing", or that the reviewer uses the generic
transport retries were corrected in `review/models.py` (module docstring,
`ReviewerStageError`, `ReviewerAttemptExhaustedError`), `review/reviewer.py`
(module docstring, `build_reviewer_client_config`, `run_controlled_review`),
`review/supervision.py`, `review/packet.py` and the CLI. The truthful wording is:
model output is never repaired; a rejected response is never edited, partially
mined, or merged; RS1 may issue one separate compact second request **only** after
a completed but unusable first response and only when the project enabled it;
timeout never gets a second request; reviewer transport retries are zero.
Historical §30 text remains, explicitly marked superseded by §31.

#### What did NOT change

The generic `LLMClient` retry behavior and its default; generic
`AIDO_LITELLM_MAX_RETRIES` semantics; reviewer `max_retries = 0`; the configured
reviewer attempt timeout; the requested `max_tokens`; the strict parser; the full
and compact request data boundaries; the same-model rule; the 5-finding retry cap;
the `review-packet.v2` structure apart from the naming and wording this
correction required; verify-before-review ordering; credential ordering; the exit
codes; and the human-terminal verdict semantics.

**No backend-cancellation API, LiteLLM-specific cancellation, Run:AI integration,
retry-after-timeout, sleep/backoff, polling, streaming/SSE, reasoning monitoring,
tool/file/test progress, fallback reviewer, RS2, fixer, branch, commit, push, or
PR was added.**

#### FU1 acceptance criteria (all met)

- [x] A timeout produces exactly **one** HTTP request even with the compact
  option enabled, and exits 4 with `REVIEW STALLED` present, `REVIEW UNUSABLE`
  absent, and attempts used = 1.
- [x] A timeout with the compact option disabled behaves identically.
- [x] A compact retry that itself times out is terminal, with no third request.
- [x] A malformed response with the compact option enabled issues exactly two
  requests, the second compact, with the same model.
- [x] A `length` finish_reason with an unusable body issues exactly two requests.
- [x] `RETRY_ELIGIBLE_OUTCOMES == {"review_output_budget_exhausted",
  "review_unusable_output"}`.
- [x] `compact_retry_on_unusable_output` is accepted and defaults to `false`;
  `compact_retry_on_stall` is rejected as an unknown field; no timeout-retry or
  generic retry field exists.
- [x] A successful compact retry still reports max 2, used 2, compact used true,
  same model true, transport retries 0.
- [x] A first-attempt success remains exactly one request, and every auth / 4xx /
  429 / 5xx / connection failure remains exactly one request.
- [x] No note or field claims backend inference lifetime, GPU occupancy, or total
  GPU time is bounded.
- [x] No backend-cancellation capability exists, so no test pretends to exercise
  one.

### 31.17 Phase 5F2E-RS1-FU2 — the wait bound is AIDO's own deadline (DONE)

> **Status: DONE.** FU1 correctly fixed retry-after-timeout, but RS1 still could
> not be accepted: its claim that `attempt_timeout_seconds` **bounds AIDO's
> reviewer wait** was not established by the existing `LLMClient`. This
> subsection records the correction. §31.1–§31.16 already describe the corrected
> behavior.

#### The blocker: an httpx timeout is not an absolute deadline

`LLMClient` builds its `httpx.Client` with `timeout=config.timeout_seconds`. That
is a **network-operation / inactivity** timeout: it fires when an individual
socket operation stalls. It is **not** an absolute deadline around the whole
synchronous `client.chat()` call.

So a peer that keeps producing network activity frequently enough — a local model
trickling tokens, a proxy keeping the connection warm — can hold one request open
for far longer than `attempt_timeout_seconds` without any single read ever
reaching its timeout. RS1 exists specifically to stop AIDO waiting indefinitely
on an unusable local reviewer, and the mechanism it was pointing at could not
deliver that.

```text
httpx timeout           = network-operation / inactivity timeout
RS1 supervisor deadline = AIDO-owned wall-clock wait deadline   <-- THE PROOF
```

The generic `LLMClient` timeout semantics were **not** modified, and httpx
behavior was **not** globally replaced. The AIDO-side wait bound was fixed
instead.

#### The mechanism, and why it is this small

```text
run_one_review_attempt
    |
    +-- start ONE daemon worker thread ------------------+
    |                                                    |
    |   worker performs exactly:  client.chat(request)   |
    |   then publishes ONE of:  response | exception     |
    |                                                    |
    +-- main thread waits to an AIDO-owned monotonic <---+
        deadline (Event.wait(timeout=...))
            |
     +------+------+
     |             |
 published    deadline reached
     |             |
 existing      classify review_stalled
 parsing       (stall_source = supervisor_deadline)
 path              |
               TERMINAL — no retry
```

- **exactly one worker per semantic attempt**, `daemon=True`;
- **no `ThreadPoolExecutor`**, no pool, no registry, no reusable task framework —
  an executor's shutdown would wait for the worker, which is the one thing that
  must not happen;
- **no `join`, bounded or otherwise.** `Event.wait` returns on the deadline and
  does not return early spuriously, so one bounded wait suffices: no loop, no
  polling;
- **no attempt to kill a Python thread**, no socket close from the supervisor, no
  cancellation request, no process, no asyncio;
- the worker does *only* `client.chat(request)` — no classification, no parsing,
  no timing, no decision. The main thread owns the deadline decision, and
  re-raises the worker's exception unchanged so behavior matches a direct call.

The publication box is a two-slot object plus a `threading.Event`, not a queue or
a future. `Event.set` / `Event.wait` provide the ordering, so no extra lock
exists, and the supervisor reads the slot **only** after `done` is set — if the
deadline wins it never reads it at all.

#### Client lifetime

The worker owns execution of `client.chat()`. The supervisor never calls
`client.close()` and never mutates the client while a worker may still be inside
that call. `LLMClient.chat` continues to own and close any temporary transport
client it created, if and when it returns. **No new shared or global client was
introduced.**

#### Deadline semantics

`controlled_review.attempt_timeout_seconds` now means: **the maximum time AIDO
waits for the reviewer HTTP/model call to complete**, subject only to small local
scheduling overhead. The reviewer's `LLMClient` still receives the same value as
a *secondary* network-inactivity timeout — useful, but explicitly not the proof.

If the worker has not published by the deadline, the attempt is `review_stalled`
and the invocation stops waiting. AIDO does **not** then wait for that worker,
join it, issue the compact retry, issue any second HTTP/model request, close its
socket from another thread, claim the worker stopped, claim the request was
cancelled, or claim backend inference stopped.

#### FU1's terminal rule is preserved, from both sources

```text
review_stalled -> REVIEW STALLED -> REVIEWER UNAVAILABLE -> exit 4
                                 -> no second semantic request
```

This holds whether the stall came from httpx raising `LLMTimeoutError` before the
supervisor deadline, or from the AIDO deadline expiring first. **Both classify as
`review_stalled`**, and no second timeout outcome was created. The two are
distinguished only by a small closed field, `ReviewAttemptRecord.stall_source`
(`client_timeout` | `supervisor_deadline`), recorded for truthful auditing:
`supervisor_deadline` is precisely the case in which an abandoned worker exists.
**Nothing branches on it.**

#### The abandoned worker, stated exactly

After an AIDO-side deadline the daemon worker may still be executing
`client.chat()`. This is the HTTP-side equivalent of the accepted Phase 5F2D
abandoned-reader limitation, and it is documented, not fixed:

- **AIDO's wait is bounded**;
- AIDO does not wait for the abandoned worker;
- the worker may **outlive this review invocation** in a long-lived Python
  process;
- the network operation may still be active;
- backend inference may still be active;
- process exit may ultimately end local daemon-thread state, but RS1 does **not**
  use or depend on interpreter exit as a cancellation mechanism.

The worker is never called "terminated", its lifetime is never called bounded,
and **no worker tracking or cleanup infrastructure was added**. Because a stall is
terminal, **one command invocation can leave at most one abandoned reviewer
worker.**

#### Attempt timing

`ReviewAttemptRecord.elapsed_seconds` is still measured with a monotonic clock,
and the clock is still injectable. On a supervisor-deadline stall it represents
**how long AIDO waited** before declaring the attempt stalled — never how long
the request or any backend inference eventually ran. The existing wording that it
is not backend inference time is unchanged.

#### Retry ownership is unchanged

The reviewer client still forces `max_retries = 0`, and generic `LLMClient`
behavior remains untouched. Therefore: one semantic attempt begins exactly one
HTTP/model request; **a supervisor deadline does not create another transport
request**; a stall remains terminal; and a completed-but-unusable response may
still buy one compact second request when configured.

#### Packet truthfulness (still `review-packet.v2`)

RS1 has still not been accepted, so this is a correction to the **draft** v2
semantics — **no version bump**. The claim

> RS1 bounds AIDO's reviewer request issuance and AIDO's wait budget

may now stand, and the packet clarifies that it is established by the supervisor
monotonic deadline and **not** by httpx timeout semantics. Three narrow fields
and one note carry it: `attempt_wait_bound`,
`abandoned_worker_lifetime_if_supervisor_deadline_expires`,
`ReviewAttemptRecord.stall_source`, and `wait_bound_note`. The two
residual-limit fields are **conditional**, because a successful packet can never
describe a stall that occurred — see §31.12. The packet continues to state that it does **not** bound
the abandoned worker's lifetime, the HTTP request's lifetime after AIDO stops
waiting, backend inference lifetime, GPU occupancy lifetime, backend context
lifetime, or server-side cancellation latency. **The packet was not turned into a
generic thread or event report.**

#### The distinction, in one place

```text
httpx timeout            = network-operation / inactivity timeout
RS1 supervisor deadline  = AIDO-owned wall-clock wait deadline

AIDO wait ended  !=  worker stopped
                 !=  request cancelled
                 !=  backend inference stopped
```

#### FU2 acceptance criteria (all met)

- [x] AIDO's wait is bounded by its own monotonic deadline, proved by a fake
  client with **no transport at all** — so no httpx timeout can be credited —
  whose `chat()` blocks on a `threading.Event`.
- [x] A "slow progress" discriminator: an operation that stays demonstrably
  active past the configured value still ends at the supervisor deadline.
- [x] A response arriving before the deadline behaves exactly as before
  (`stall_source is None`).
- [x] An httpx `LLMTimeoutError` before the deadline is a terminal stall recorded
  as `client_timeout`.
- [x] A supervisor deadline before the client returns is a terminal stall
  recorded as `supervisor_deadline`, with exactly **one** request begun and no
  compact retry even when `compact_retry_on_unusable_output=true`.
- [x] A compact attempt that itself exceeds the deadline is terminal: two total
  requests, never a third.
- [x] At CLI level: `REVIEW STALLED`, no "compact retry authorized", attempts
  used = 1, exit 4.
- [x] The worker is verified `daemon=True` and never joined, asserted via `ast`
  rather than substring search (this module's own prose disclaims the very words
  a grep would flag).
- [x] No executor, pool, registry, queue, process, asyncio, `psutil` or `signal`
  import exists in the supervision module; no `join`, `close`, `shutdown`,
  `cancel`, `abort`, `terminate` or `kill` call exists anywhere in the review
  package.
- [x] Generic `LLMClient` timeout and retry behavior is unchanged.
- [x] No packet, note, or message claims the abandoned worker or backend
  inference stopped, or that either lifetime is bounded.
- [x] **A successful packet never implies a stall or an abandoned worker
  occurred.** The two residual-limit fields are named and worded conditionally
  (`backend_inference_lifetime_if_stalled`,
  `abandoned_worker_lifetime_if_supervisor_deadline_expires`), and regressions on
  both success paths — first-attempt success and successful compact retry —
  assert that no attempt outcome is `review_stalled`, every `stall_source` is
  `None`, and no value asserts an abandonment as fact.
- [x] Every blocked synthetic worker is released in a `finally`, so the suite
  leaves nothing parked. All tests remain fully offline.

#### Also corrected here: a stale `ReviewerCallNotice` docstring

`ReviewerCallNotice` claimed that `project_id` and `repo` are "constrained by
their own validators (`repo` must be `owner/repo`)". `RepoConfig` enforces no such
shape and `ProjectConfig` does not constrain `project_id` beyond requiring it, so
the sentence was simply wrong — previously recorded as a non-blocking
documentation note.

The docstring now says what is actually true: those values are kept because they
come from the **project config**, which this repository treats as trusted
authority, unlike an issue title that arrives with the issue. That is a statement
about *provenance*, not validation. **No validator was added merely to make the
prose true, and no terminal-escaping infrastructure was created.** Project config
remains the trusted authority for those values.

---

## 32. Phase 5F2E-V1 — direct vLLM reviewer provider (DONE)

> **Status:** DONE. This section describes the accepted implementation.
>
> **Scope, stated exactly:** V1 is a **reviewer-provider extension and nothing
> else.** It is **not** Pi integration, a model-backed implementer, an agent
> loop, RS2 reviewer failover, a fallback reviewer, a second reviewer, a fixer, a
> review/fix loop, backend cancellation, a generic provider framework, a generic
> OpenAI-compatible provider abstraction, or branch/commit/push/PR work. None of
> those were added, and none may be added under this section's authority.

### 32.1 Why

Phase 5F2E's reviewer *transport* was already OpenAI-compatible, but its reviewer
**authority and provenance** were LiteLLM-specific in four places:

1. `controlled_review.provider` accepted only `"litellm"`;
2. reviewer environment loading read only the five `AIDO_LITELLM_*` names;
3. a successful `review-packet.v2` reported the provider as `litellm`;
4. `review-packet.v2`'s `provider` field *meant* LiteLLM by construction.

A second reviewer backend is now explicitly supported: a **direct
OpenAI-compatible vLLM endpoint**. LiteLLM remains supported for when internal
infrastructure returns; direct vLLM is an **additional** option, not a
replacement, and V1 must not retroactively break an accepted LiteLLM deployment.

No model name and no endpoint is hard-coded anywhere in runtime code or in this
document. Model authority remains exactly
`project_config.controlled_review.model`, and endpoint authority remains the
environment. Examples here use neutral `.invalid` hostnames only.

### 32.2 Configuration contract

```yaml
controlled_review:
  enabled: true
  provider: "vllm"                        # exactly "litellm" or "vllm"
  model: "my-served-model-name"           # the ONLY place a reviewer model is named
  attempt_timeout_seconds: 90
  max_output_tokens: 2048
  compact_retry_on_unusable_output: false
  vllm_allow_insecure_http: false         # vLLM only; ships false
```

- `provider` is matched **exactly and case-sensitively** against exactly two
  values. No alias, no case folding, no whitespace trimming, no glob, no
  `"openai"`, no `"openai_compatible"`, no provider registry, no plugin system,
  no provider list, no provider priority, and no failover. Shape is validated at
  load (non-blank) and **support** is enforced at the review gate, so a mis-set
  reviewer block still cannot make an unrelated command fail to load its project
  config — the accepted Phase 5F2D executable precedent.
- `vllm_allow_insecure_http` is the **only** new field. It defaults to `false`,
  so every existing Phase 5F2E / RS1 config loads unchanged with unchanged
  behavior. It exists solely to authorize direct vLLM plaintext HTTP transport.
- Nothing else was broadened. The block still has **no** field for an endpoint
  URL, an API key, a header, an environment-variable name, a `fallback_model`, a
  `secondary_model`, a `reviewer_chain`, a provider priority or list, a model
  list, or a transport retry count — and there is no CLI override for any of
  them.

### 32.3 Provider-specific environment, and the preserved ordering

The accepted ordering is unchanged and remains the safety property:

```text
verify FIRST  →  reviewer environment SECOND
```

No reviewer endpoint or credential value of **either** provider is read before
the accepted Phase 5F2D verifier returns `verified`.

| provider | required | optional |
| --- | --- | --- |
| `litellm` | `AIDO_LITELLM_BASE_URL`, `AIDO_LITELLM_API_KEY`, `AIDO_LITELLM_DEFAULT_MODEL` | `AIDO_LITELLM_TIMEOUT_SECONDS`, `AIDO_LITELLM_MAX_RETRIES` |
| `vllm` | `AIDO_VLLM_BASE_URL` | `AIDO_VLLM_API_KEY` |

A vLLM reviewer requires **no** `AIDO_LITELLM_*` variable, and there is
deliberately **no** `AIDO_VLLM_DEFAULT_MODEL`: the environment must never be able
to select the reviewer model.

The injected reader is called **once**, as `read_env(provider)`, and only the
configured provider's names are ever read. See §32.11, which corrected this: V1
shipped a reader that snapshotted the union of both families and narrowed the
result afterwards, which is still *reading* the unconfigured provider's values.

The existing LiteLLM loader and the generic `LLMClient` were **not** globally
altered.

### 32.4 Keyless vLLM without weakening the generic client

`LLMClientConfig.api_key` is a required non-blank string, and the shipped
OpenAI-compatible client always sends an `Authorization` header. A keyless vLLM
server accepts the request regardless of that header's contents.

Rather than make `api_key` optional for every caller — which would weaken a model
whose purpose is to hold the one credential copy in one place — the vLLM branch
substitutes a fixed literal when `AIDO_VLLM_API_KEY` is absent or blank:

```text
VLLM_COMPATIBILITY_PLACEHOLDER_API_KEY = "no_api_key"
```

**It is a compatibility placeholder, not a credential.** It carries no secret,
grants no access, proves nothing about the endpoint, and must never be described
as authentication. When a real key *is* supplied it reaches the client config and
nothing else — never stdout, stderr, the packet, an error, a warning, or a log,
and `LLMClientConfig` still excludes it from `repr`.

### 32.5 Insecure-transport refusal (vLLM only)

- HTTPS: allowed normally.
- HTTP: **refused**, unless `controlled_review.vllm_allow_insecure_http` is true.

The refusal happens while the connection settings are being built — before a
client exists — so no model request can be issued past it. Verification may
already have passed, because the credential ordering is preserved; that is
expected, and the command exits **4** (reviewer stage failed after verification
passed) with the Phase 5F2E-scoped failure text. The message never prints the
full base URL or any credential; the endpoint **host** is shown only where the
existing banner already shows it.

Nothing upgrades, rewrites, or tunnels the URL. Schemes other than `http` and
`https` are refused for both providers before a client is built — `httpx` could
not have spoken them either, so no working deployment can be affected.

> **The opt-in means exactly one thing:** *this project explicitly permits
> source-derived reviewer material to be sent over direct vLLM plaintext HTTP
> transport.* It does **not** mean secure, encrypted, private, authenticated,
> company-approved, or safe for secrets, and an internal, colleague-hosted, or
> same-network endpoint is **not** private merely because of where it sits.

The rule is deliberately **not** applied to the LiteLLM provider, whose
deployments were accepted before this phase existed.

### 32.6 Client construction

The vLLM branch produces the same `LLMClientConfig` concepts as the LiteLLM one:

| field | value |
| --- | --- |
| `base_url` | `AIDO_VLLM_BASE_URL` |
| `api_key` | the supplied vLLM key, or the fixed compatibility placeholder |
| `default_model` | the exact `controlled_review.model` |
| `timeout_seconds` | `controlled_review.attempt_timeout_seconds` |
| `max_retries` | `REVIEWER_TRANSPORT_MAX_RETRIES` (`0`) |

The existing `LLMClient` is reused. **No** second HTTP client, vLLM SDK,
`requests`, `aiohttp`, or `curl` dependency was added, and generic `LLMClient`
retry or timeout behavior is unchanged for every other caller.

### 32.7 What did NOT change

The reviewer prompt, the compact-retry prompt semantics, the transmitted source
boundary, the strict JSON parser, the finding limits, the verdict semantics, the
RS1 attempt classifications, `RETRY_ELIGIBLE_OUTCOMES`, the terminal-timeout
rule, the daemon-worker wait deadline, the maximum of two semantic attempts,
`max_retries=0`, `stall_source`, the output-token policy, and every
backend-cancellation disclaimer are all **unchanged**, and apply **identically**
to both providers.

A vLLM timeout is still `review_stalled` → terminal → **no retry after the
stall**, unless the accepted completed-but-unusable compact-retry policy applies.
No provider-specific retry, timeout, backoff, streaming, or cancellation behavior
was added.

The CLI is unchanged: no new command, and `l2-review-approved-file-edit` keeps
its exact option surface. Provider selection is project-config only; endpoint
selection is environment-only.

### 32.8 `review-packet.v3`

`review-packet.v2` is **not** redefined. Its `provider` contract was
LiteLLM-specific and it reported no transport scheme, so silently widening it
would have made every archived `v2` packet ambiguous about which backend produced
it, and would have implied a transport claim those packets never made.

Schema-version history, as the packet itself now states:

- **`review-packet.v1`** — original Phase 5F2E semantics: exactly one semantic
  reviewer attempt, unreported generic transport retries, no attempt accounting,
  **LiteLLM-only** reviewer provenance, no transport-scheme reporting.
- **`review-packet.v2`** — Phase 5F2E-RS1 supervision semantics (transport
  retries forced to zero, at most two semantic requests, an AIDO-owned
  per-attempt wait deadline, a terminal stall, per-attempt accounting), still
  with **LiteLLM-only** reviewer provenance and still no transport-scheme
  reporting. **An archived `v2` packet must never be read as though it may have
  come from vLLM.**
- **`review-packet.v3`** — the **same** accepted RS1 supervision semantics as
  `v2`, now with explicit LiteLLM/vLLM reviewer provenance and truthful
  transport-scheme reporting.

`v3` reviewer provenance adds:

```text
provider:        "litellm" | "vllm"      (from trusted project config)
model:           exact configured model
model_source:    project_config.controlled_review.model
endpoint_host:   host (or host:port) only
endpoint_scheme: "http" | "https"
transport_tls:   endpoint_scheme == "https"
```

`transport_tls` is a statement about the configured URL **scheme** and nothing
more — not a certificate, cipher, peer-identity, or network-privacy claim. It is
reported truthfully for both providers, including the synthetic `http` URLs the
offline test suite uses; that is test provenance being recorded honestly, not a
security approval.

Still absent, because there is no field for any of them: the base URL, the API
key, any header, the full endpoint path, the query, the fragment, and any
workspace absolute path. `provider` **cannot be forged by model output** — the
strict reviewer schema has no such field, and the block is assembled entirely
from orchestrator-owned values.

### 32.9 Human-facing notice

The pre-call stderr banner gains three safe lines — the provider, the transport,
and the existing endpoint host — and a plaintext transport is announced
unmistakably:

```text
Provider:      vllm
Endpoint host: vllm.example.invalid:8000
Transport:     HTTP — NOT TLS-ENCRYPTED. Source-derived code will be sent
               UNENCRYPTED over this network path. Being internal,
               colleague-hosted, or on a particular network does NOT make it
               private.
```

The banner still carries no API key, no base URL, no prompt, no diff, no absolute
path, and no issue title. No real endpoint or IP appears in warning logic or in
this document.

### 32.10 Verification checklist

- [x] Existing LiteLLM configs load unchanged, with `vllm_allow_insecure_http`
  defaulting to `false` and every RS1 default untouched.
- [x] The existing `AIDO_LITELLM_*` contract is unchanged, and a
  project-configured model still overrides `AIDO_LITELLM_DEFAULT_MODEL`.
- [x] Reviewer transport `max_retries` is `0` for **both** providers.
- [x] `provider` matching is exact and case-sensitive; `"VLLM"`, `"vllm "`,
  `"LiteLLM"`, `"openai"`, `"openai_compatible"` and arbitrary values all refuse
  at the gate, before workspace access, verification launch, environment read,
  client construction, or model contact.
- [x] A vLLM reviewer requires no `AIDO_LITELLM_*` variable and no
  `AIDO_VLLM_DEFAULT_MODEL`; the exact configured model becomes
  `LLMClientConfig.default_model`.
- [x] A missing or blank `AIDO_VLLM_BASE_URL` fails after verification and before
  any model request.
- [x] An absent or blank `AIDO_VLLM_API_KEY` yields the fixed non-secret
  placeholder; a supplied key reaches only the client config and appears in no
  packet, stdout, stderr, or error text.
- [x] LiteLLM environment values cannot supply a vLLM endpoint, credential, or
  model — or the reverse.
- [x] vLLM HTTPS works with the default opt-out; vLLM HTTP is refused by default
  before model contact; vLLM HTTP proceeds only with the explicit opt-in; the
  refusal echoes no URL or credential; the HTTP banner says **NOT TLS-ENCRYPTED**.
- [x] Successful packets record `endpoint_scheme` / `transport_tls` truthfully
  for `http` and `https`, and for both providers.
- [x] For **both** providers: a disabled review, an unsupported provider, or a
  missing action flag reads no reviewer environment; verification exit 2 or 3
  reads no reviewer environment and contacts no model; the provider's environment
  is read only after `verified`, and only the configured provider's names are
  read at all (see §32.11).
- [x] RS1 invariants hold on the vLLM path: one request on first-attempt success;
  a client timeout is terminal at one request; an expired AIDO deadline is
  terminal at one request; a completed-but-unusable response uses the compact
  retry only when the project enabled it; never a third request; no fallback
  model.
- [x] `REVIEW_PACKET_SCHEMA_VERSION == "review-packet.v3"`; `v1` and `v2`
  semantic-history constants remain present and truthful; `v2` is documented as
  LiteLLM-only and explicitly not vLLM-capable; the packet's provider cannot be
  forged by model output.
- [x] No Pi import or invocation, no implementer, no fixer, no fallback or
  reviewer chain, no new subprocess worker, no backend cancellation, and no CLI
  surface expansion.
- [x] Every reviewer test uses `httpx.MockTransport`. No socket, no real API key,
  and no real endpoint appears in the suite.

### 32.11 Phase 5F2E-V1-FU1 — provider environment isolation (DONE)

V1 was implemented but not yet accepted. One runtime blocker was found against
it, plus a few directly related truthfulness defects. This sub-section records
their correction. **Nothing else about V1 was reopened**: the provider set, the
matching rule, model authority, the vLLM environment contract, the keyless
placeholder, the insecure-HTTP refusal and its opt-in, `review-packet.v3`, the
`v1`/`v2` historical meanings, and every RS1 semantic are exactly as §32
describes.

#### The blocker: read-then-discard is still reading

V1's real reader, `cli._read_reviewer_env()`, took **no argument**. It snapshotted
the union of both provider families from `os.environ` and returned it; the
configured provider's subset was selected afterwards, inside
`run_controlled_review`.

So a vLLM review really did read `AIDO_LITELLM_API_KEY` from the process
environment before discarding it, and a LiteLLM review really did read
`AIDO_VLLM_BASE_URL`. That contradicted the contract §32.3 documents, and it was
the wrong way round: **the selection must happen before the environment is
touched, not after.**

#### The fix

The smallest explicit shape, and no framework:

```text
read_env(provider)                      # injected reader, called ONCE
  └─ reviewer_env_names_for_provider(provider)   -> exact tuple of NAMES
       └─ {name: environ[name] for name in names if name in environ}
```

`reviewer_env_names_for_provider` answers from the provider alone — no
environment access, no default, no fallback, no aliasing — and raises for an
unsupported provider **before** any name is resolved, so a bad provider cannot
read a value either. A LiteLLM review resolves to exactly the five
`AIDO_LITELLM_*` names; a vLLM review resolves to exactly `AIDO_VLLM_BASE_URL`
and `AIDO_VLLM_API_KEY`.

Two things were **removed** rather than left as decoys:

- `select_reviewer_env` — the narrow-afterwards helper, which now has no
  truthful purpose;
- the union constant `REVIEWER_ENV_NAMES` — which was the defect's enabler.
  There is deliberately no union read authority left to regress to.
  `LITELLM_REVIEWER_ENV_NAMES`, `VLLM_REVIEWER_ENV_NAMES` and
  `REVIEWER_ENV_NAMES_BY_PROVIDER` remain, documenting the two exact families.

The verify-first / credential-second ordering is **unchanged**: the reader is
still called only after the accepted Phase 5F2D verifier returns `verified`, and
still exactly once. `_read_real_llm_env`, used by the planner and smoke-test
commands, is untouched.

#### The regressions

The tests deliberately **fail against the old implementation**. Rather than pass
a pre-built mapping and check the filtering, they replace `os.environ` with a
tracking mapping (seeded from a copy of the real one, with the seven reviewer
names removed and synthetic values added) that instruments `__getitem__`,
`__contains__` and `get`, records every lookup of a watched name, and raises
immediately on a forbidden one. Verified: simulating V1's union snapshot makes
**eight** of these tests fail.

They prove: a vLLM review looks up only the two `AIDO_VLLM_*` names; a LiteLLM
review looks up only the five `AIDO_LITELLM_*` names; an unsupported provider
looks up none; a verification exit 2 or 3 looks up none of the seven; a refused
run looks up none of the seven; and the reader runs exactly once with the
configured provider. Two of them drive the whole command with the **real
wired-in** reader rather than an injected one.

#### Truthfulness corrections shipped alongside

- **Provider-neutral connection-failure category.** The CLI's
  `ReviewerEnvironmentError` category said *"the AIDO_LITELLM_\* connection
  settings were missing or invalid"*, which misdescribes every vLLM failure. It
  is now *"reviewer connection configuration failure — the configured reviewer
  connection settings were missing, invalid, or disallowed"*. "Disallowed" covers
  the refused-transport case, which is neither missing nor invalid. The category
  names no provider family and carries no value; the raised **exception** still
  safely names the required variable *name* (for example `AIDO_VLLM_BASE_URL`)
  and never an endpoint, credential, or raw environment value.
- **`review/packet.py`'s module docstring** still opened by calling the artifact
  `review-packet.v2`. Corrected to `v3` / Phase 5F2E-V1 semantics, and the
  reviewer-provenance bullet now mentions the transport scheme. Prose only:
  `REVIEW_PACKET_SCHEMA_VERSION`, the `v1`/`v2` semantics constants, the `v3`
  schema and every packet field are unchanged.
- **Stale live prose corrected**: `ControlledReviewConfig`'s docstring described
  connection details as `AIDO_LITELLM_*` only; the CLI runner's ordering
  docstring described the narrow-afterwards behavior; `mis_project.yaml.example`
  still said `provider` accepts only `"litellm"`, that connection details "still
  come from the `AIDO_LITELLM_*` environment", and (pre-RS1) that the material is
  sent to the one model "once"; `.env.example`'s "read ONLY when provider is
  vllm" claim is now literally true and says why. Sections explicitly marked as
  design history were left alone.

## 33. Phase 5F2E-V2 — structured vLLM reviewer output (DONE)

> **Status:** DONE. This section describes the accepted implementation.
>
> **Scope, stated exactly:** V2 adds **one controlled generation constraint** for
> direct-vLLM reviewers, and nothing else. It is **not** parser repair, output
> normalization, tolerant parsing, a structured-output framework, Pi integration,
> a model-backed implementer, a fixer, a review/fix loop, RS2 reviewer failover,
> a second reviewer, a provider registry, backend cancellation, or
> branch/commit/push/PR work. None of those were added, and none may be added
> under this section's authority.

### 33.1 Why — the observed evidence

V2 exists because controlled synthetic real-model trials established a specific
compatibility problem and a specific solution. The trials used a direct vLLM
endpoint serving a local Qwen-family reviewer model; no endpoint, address, or
port appears in this document or in runtime code.

| trial | what happened |
| --- | --- |
| **RT1** | Full review completed. Classified `review_unusable_output`. |
| **RT1-C1** | Full review completed → `review_unusable_output`; the accepted compact retry completed → `review_unusable_output` again. |
| **RT1-D1** | Same shipped full AIDO review prompt. HTTP 200, `finish_reason=stop`. **The semantic bug was correctly identified.** The provider returned `message.reasoning` separately, and `message.content` was the intended review JSON **wrapped in a ```json fence**. `parse_model_review_response` rejected the unmodified content. |
| **RT1-D2** | Same exact prompt, context, model, temperature and `max_tokens`. **Only request delta: `response_format` = JSON Schema**, generated from `ModelReviewResult.model_json_schema()`. HTTP 200; reasoning still returned separately; `message.content` became **one bare JSON object**; `parse_model_review_response` accepted it **unmodified**; verdict `changes_requested`, with a blocker correctness finding that correctly identified the seeded inclusive-boundary regression. |

Two conclusions follow, and both shaped the design:

- **the reviewer's reasoning was never the failure.** The model found the seeded
  bug in D1 as well as in D2. What failed was the **envelope** — a markdown
  fence around otherwise correct JSON;
- **the strict parser was right to reject it.** A parser that stripped the fence
  would have "fixed" the problem by becoming exactly the tolerant, repairing
  parser this repository refuses to have.

So the fix belongs where the problem is: on the **generation** side, as a server
constraint, leaving the parser untouched.

```text
generation constraint  →  raw returned content  →  existing strict
(response_format)         (never modified)          parse_model_review_response()
                                                          ↓
                                                    valid  or  rejected
```

**Invalid content remains rejected, never repaired.**

### 33.2 The core rule: the strict parser did not change

`review/models.py` is byte-identical in behavior. V2 added **no**:

markdown-fence stripping; prose stripping; JSON extraction; tolerant parsing;
parser repair; field renaming; type coercion; extra-field deletion; verdict
repair; or model-response normalization.

The test suite proves this structurally, not just by assertion: it tokenizes the
parser module, strips every comment and string literal, and asserts that no
repair-shaped token (`repair`, `normalize`, `coerce`, `partition`, `splitlines`,
`replace`, `re`, `removeprefix`, …) appears in the code that actually runs. It
also asserts that the whole `review` package exports no callable whose name
contains `repair`, `fence`, `extract`, `normalize`, or `salvage`.

### 33.3 Configuration contract

Exactly one narrow field was added to `ControlledReviewConfig`:

```yaml
controlled_review:
  enabled: true
  provider: "vllm"                        # exactly "litellm" or "vllm"
  model: "my-served-model-name"
  attempt_timeout_seconds: 90
  max_output_tokens: 2048
  compact_retry_on_unusable_output: false
  vllm_allow_insecure_http: false
  vllm_structured_output: false           # V2; vLLM only; ships false
```

- **`vllm_structured_output: bool = False`.** When it is `true` **and**
  `provider == "vllm"`, AIDO requests the `ModelReviewResult` JSON Schema through
  the OpenAI-compatible `response_format`/`json_schema` request field.
- **The default is `false`**, so every existing Phase 5F2E-V1 project config and
  every accepted direct-vLLM deployment keeps exactly its accepted behavior.
- **`provider != "vllm"` with the field `true` FAILS CLOSED at the review
  gate**, with a clear config error naming the configured provider. It is
  deliberately **not** silently ignored for LiteLLM: quietly dropping a setting an
  operator wrote would make the packet's provenance disagree with the config that
  produced it.

Nothing else was broadened. The block still has **no** field for an arbitrary
`response_format`, a schema path, a schema string, a schema file, a
structured-output *mode*, `guided_json`, a grammar, a regex, provider
capabilities, or fallback transport behavior — and `extra="forbid"` rejects every
one of them at load.

### 33.4 The generation constraint, exactly

For `provider == "vllm"` **and** `vllm_structured_output == true`, and only then,
the request carries:

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "aido_controlled_review",
      "schema": "<ModelReviewResult.model_json_schema()>"
    }
  }
}
```

The schema is **generated from the current shipped `ModelReviewResult`** by
`review.request.build_review_response_format()`. There is exactly **one**
`model_json_schema()` call site in the repository and **no hand-maintained second
JSON schema anywhere** — the tests assert both, so the schema and the parser
cannot drift apart.

Nothing simplifies or weakens what Pydantic produced. The generated document
reaches the server with `additionalProperties: false`, the full top-level
`required` list, the severity enum, the category enum, the `ReviewFinding`
object and its own `additionalProperties: false`, the `$ref`-based finding list,
and the nullable `line` shape (`anyOf: [integer, null]`) all intact.

### 33.5 JSON Schema is not Pydantic — and the parser stays final

It is accepted and truthful that Pydantic **model-level validators are not fully
expressible in JSON Schema**. The generated schema states the closed key set, the
required fields, the scalar types, the two enums, the finding object shape and
the nullable line — and states nothing at all about:

- the string length caps (`summary`, `message`, `suggested_action`, note
  entries);
- the non-blank rules;
- `line > 0`;
- the finding-count and note-count bounds;
- the verdict/finding consistency rules (`changes_requested` requires a
  blocking finding; `approve` must carry none);
- the compact retry's five-finding cap.

**`parse_model_review_response` remains the final authority for all of them**,
and is unchanged. The tests supply five payloads that satisfy everything the
generated schema can express and are still rejected — including the
verdict/finding inconsistency case and an `approve` carrying a blocker.

This is stated once as a constant,
`review.request.STRUCTURED_OUTPUT_PARSER_AUTHORITY_NOTE`, and carried into every
successful packet as `reviewer.structured_output_note`, so no message or
document can quietly upgrade the claim. Recording `structured_output_mode:
"json_schema"` says what AIDO **requested** — never that generation was in fact
constrained, that the server honored the schema, or that the reply was therefore
valid.

### 33.6 Request model and client

The existing `LLMClient` is reused. **No** direct-vLLM HTTP client, second
reviewer transport, vLLM SDK, `requests`, `aiohttp`, or `curl` subprocess
transport was added.

The smallest typed capability was added instead:

- `LLMJSONSchemaResponseFormat` — a model that can express **only** this exact
  JSON-schema shape. Its `type` is the closed literal `"json_schema"`, so there
  is no `json_object` mode, no grammar, no regex, and no `guided_json`;
- `LLMRequest.response_format: LLMJSONSchemaResponseFormat | None = None`.

There is deliberately **no** generic `extra_body`, arbitrary kwargs, or arbitrary
provider body dictionary, so no caller can smuggle a provider payload through it.

**Omission is total.** When `response_format` is `None`, `_build_payload` emits no
`response_format` key at all, so every existing caller's payload is exactly what
it was. The wire member is `"schema"` while the field is `json_schema` — `schema`
shadows a `BaseModel` attribute and cannot be a field name — and the client owns
that one explicit mapping.

Verified with no `response_format` in the serialized request:

- planning (`build_model_l1_plan_request`);
- the dry-run and real smoke tests;
- a LiteLLM controlled review;
- a vLLM review with `vllm_structured_output` absent or `false`.

And verified for a structured run: the **only** payload-key difference is the
added `response_format`; every other key is byte-equal.

### 33.7 Full and compact attempts

When structured output is enabled, **both** possible semantic reviewer requests
carry the **same** `response_format` with the **same** schema, because both
expect exactly the same `ModelReviewResult` output.

There is deliberately **no smaller second schema** for the compact retry. The
compact retry's maximum of five findings remains an **AIDO** rule, enforced by
rejection after parsing, exactly as RS1 accepted it.

Neither review prompt changed.

### 33.8 RS1 is unchanged — and there is NO fallback

Preserved exactly:

```text
REVIEWER_TRANSPORT_MAX_RETRIES = 0
maximum two semantic attempts
one HTTP/model request per semantic attempt
terminal timeout / stall
compact retry only for COMPLETED unusable output
same model for the retry
AIDO-owned monotonic wait deadline
```

A **structured-output server rejection is an ordinary reviewer-stage
request/response failure**, and it is terminal:

```text
HTTP 400 "response_format unsupported"  →  terminal reviewer-stage failure (exit 4)
structured decoding 5xx                 →  terminal reviewer-stage failure (exit 4)
```

AIDO must **never** issue:

```text
request 1: structured
request 2: unstructured      ← FORBIDDEN
```

That would be an unauthorized fallback and would violate RS1's retry ownership.
The tests drive a 400, a 422 and a 503 with the compact retry **enabled**, and
assert one HTTP request, exit 4, and that every request issued carried the
schema.

### 33.9 Provider behavior

| provider | `vllm_structured_output` | request |
| --- | --- | --- |
| `litellm` | absent / `false` | no `response_format` — accepted behavior, unchanged |
| `litellm` | `true` | **refused at the review gate** |
| `vllm` | absent / `false` | no `response_format` — accepted V1 behavior, unchanged |
| `vllm` | `true` | `response_format`/`json_schema` with the generated schema |

There is no automatic provider capability detection, no fallback, and no provider
registry.

### 33.10 `review-packet.v4`

`review-packet.v3` is **not** redefined. V2 changes a provenance fact that
materially affects **how the reviewer response was generated**, and no `v1`, `v2`
or `v3` packet records it — so silently widening `v3` would have made every
archived `v3` packet ambiguous about whether a constraint was used.

Preserved historical meanings:

- **`review-packet.v1`** — original Phase 5F2E semantics: exactly one semantic
  reviewer attempt, unreported generic transport retries, no attempt accounting,
  LiteLLM-only reviewer provenance, no transport-scheme reporting, **no
  structured-generation provenance**.
- **`review-packet.v2`** — Phase 5F2E-RS1 supervision semantics, still
  LiteLLM-only, still no transport-scheme reporting, **no structured-generation
  provenance**.
- **`review-packet.v3`** — RS1 supervision **plus** LiteLLM/vLLM provider and
  transport provenance, **but no structured-generation provenance**. An archived
  `v3` packet must **not** be interpreted as proving whether
  `response_format`/`json_schema` was used.
- **`review-packet.v4`** — every accepted `v3` and RS1 semantic retained
  unchanged, plus structured-generation provenance.

`v4` reviewer provenance adds:

```text
structured_output_mode:           "none" | "json_schema"
structured_output_schema_source:  null | "ai_dev_orchestrator.review.models.ModelReviewResult"
structured_output_note:           the JSON-Schema-vs-Pydantic authority boundary
```

- `vllm_structured_output: true` → `structured_output_mode = "json_schema"` and
  the schema-source identifier;
- LiteLLM, **or** `vllm_structured_output: false` → `structured_output_mode =
  "none"` and a `null` source.

The schema source is **derived** from the mode inside the builder rather than
passed, so the two cannot disagree.

Deliberately **not** included, because there is no field for any of them: the
full JSON schema, the `response_format` request JSON, the prompt, the raw model
response, the reasoning, the base URL, the API key, and the `Authorization`
header.

The structured-output provenance is **orchestrator-owned, not model output**. It
comes from the review gate's reading of trusted project config; the strict
reviewer schema has no such field; and a reply whose *prose* claims a schema was
enforced changes nothing in the packet.

### 33.11 The reasoning field is deliberately NOT captured

D1 and D2 both observed that vLLM returns Qwen's reasoning separately from
`content`. V2 does **not** need that field to solve the compatibility problem, so
it adds **no** support for it: `message.reasoning` is not read, logged,
transmitted, parsed, stored, or exposed anywhere. The controlled reviewer
continues to use only the assistant `content`. **No chain-of-thought
observability was added**, which keeps RS1's observability boundary exactly where
it was accepted.

### 33.12 Human-facing notice

The existing pre-call stderr banner gains **one** safe line, carrying the mode
token only:

```text
Structured output: json_schema
Structured output: none
```

No schema body is printed, and no new sensitive value is exposed.

### 33.13 CLI

Unchanged. No new command, and `l2-review-approved-file-edit` keeps its exact
option surface — specifically **no** `--structured-output`, `--response-format`,
`--json-schema`, or `--guided-json`. Authority remains project config only.

### 33.14 Verification checklist

- [x] Existing `ControlledReviewConfig` blocks load unchanged;
  `vllm_structured_output` defaults `false`; every V1/RS1 default is untouched.
- [x] `provider: "vllm"` with the opt-in is accepted at the gate;
  `provider: "litellm"` with it is **refused** there, before any workspace
  access, verification launch, environment read, client construction, or model
  contact.
- [x] Arbitrary structured-output config (`response_format`, `schema_path`,
  `guided_json`, `grammar`, `regex`, `extra_body`, `provider_capabilities`, a
  mode string in place of the bool, …) is rejected at load.
- [x] The schema is generated from `ModelReviewResult.model_json_schema()`;
  exactly one generating call site exists; no hand-written duplicate schema
  exists.
- [x] The generated schema retains `additionalProperties: false`, all required
  top-level fields, the severity and category enums, the finding shape, and the
  nullable line.
- [x] The JSON-Schema-vs-Pydantic-validator boundary is documented, carried in
  the packet, and asserted by tests that reject schema-valid replies.
- [x] No `response_format` appears for planning, the smoke tests, a LiteLLM
  review, or a vLLM review with the opt-in off; a structured run's only payload
  delta is the added key.
- [x] Full and compact attempts send the identical schema; no third request.
- [x] A structured-output 400/422/503 is terminal at one HTTP request, with no
  unstructured re-issue, even with the compact retry enabled.
- [x] A timeout remains terminal at one request; `REVIEW STALLED` never says a
  compact retry was authorized.
- [x] The strict parser is unchanged: fenced JSON is still rejected, bare JSON is
  still accepted, and no repair helper exists in the executable source.
- [x] `REVIEW_PACKET_SCHEMA_VERSION == "review-packet.v4"`; `v1`/`v2`/`v3`
  semantics constants remain present and truthful; each is documented as
  carrying **no** structured-generation provenance.
- [x] Structured vLLM packets report `provider: "vllm"`,
  `structured_output_mode: "json_schema"` and the correct schema-source
  identifier; LiteLLM and unstructured vLLM packets report `"none"` and `null`.
- [x] A model reply cannot forge structured-output provenance.
- [x] No Pi import or invocation, no implementer, no fixer, no provider failover,
  no model fallback, no parser repair, no reasoning-field capture, no CLI
  expansion, and no backend cancellation.
- [x] Every reviewer test uses `httpx.MockTransport`. No socket, no real API key,
  and no real endpoint appears in the suite.
