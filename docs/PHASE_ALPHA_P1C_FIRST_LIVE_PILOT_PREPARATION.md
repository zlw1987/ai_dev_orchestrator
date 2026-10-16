# ALPHA-P1C — First Qwen 3.8 Live Pilot Preparation

> **PREPARED — AWAITING AUTH-PILOT HUMAN APPROVAL.**
>
> This document prepares the first live supervised-implementer pilot. It
> **authorizes nothing**. No model request was made, no source was transmitted,
> no clone was created, no prepare was run, and no consent was filled while
> writing it. The real source transmission needs, in this order: an approved
> AUTH-PILOT (§5), then a fresh per-run H4S consent completed by the operator
> (§6, step 5). Neither of these is inferred from this document or from any
> earlier transmission authorization, H9b included.

| | |
|---|---|
| Kind | Pilot preparation (no implementation) |
| Recorded | 2026-10-15 |
| AIDO baseline | `b8ac9ea2f85adaa9a56a17bb36b2be62f7bd63df` (ALPHA-P1B + FU1) |
| Runtime | The accepted P1B commands, unchanged: `l2-supervised-implementer-prepare` and `l2-supervised-implementer-run` |
| Procedure source | [P1B design §6.2](PHASE_ALPHA_P1B_LIVE_IMPLEMENTER_AUTHORITY_DESIGN.md) and [P1B record §6–§7](PHASE_ALPHA_P1B_SUPERVISED_IMPLEMENTER_LIVE.md); Alpha-0 runbook steps 0–2 for the clone and the plan |
| Identity | `supervised_implementer` / `SUP-D` / `qwen3.8-27b` / `litellm`. **No qualification credit** in either direction |

The corporate endpoint is deliberately not written here. It exists only in the
operator's run window (§6, step 6) and in the operator-typed consent fields.

---

## 1. P1B baseline

| Check | Observed (2026-10-15) |
|---|---|
| Local `HEAD` | `b8ac9ea` — `alpha-p1b: add live supervised implementer with durable authorization` |
| Working tree | clean (`git status --porcelain` empty, untracked included) |
| `origin` | `https://github.com/zlw1987/ai_dev_orchestrator.git` |
| Remote `refs/heads/main` (`git ls-remote`) | **`4e02380`**, not `b8ac9ea` (see §8, B-1) |
| `src/` + `pyproject.toml` diff `39d81ba..HEAD` | 13 files (P1A + P1B). `workspace/git_adapter.py`, the writer and the plan models are unchanged, so the Alpha-0 helper's mirrored gate constants still hold |
| CLI option sets (`--help`, offline) | `prepare`: `--project-config --approved-plan --target-path --evidence-dir --out --prepare-supervised-implementation`. `run`: `--project-config --approved-plan --authorization --evidence-dir --transmit-approved-source --real-implementer`. Both match design §6.1 exactly |

## 2. Pilot task and target file

**Repository:** `zlw1987/ai_dev_orchestrator`, which is AIDO's own repository.
The disposable clone is separate from the AIDO checkout that runs the commands.

**Target:** `src/ai_dev_orchestrator/github/issue_parser.py`

| Property | Value |
|---|---|
| Git mode / blob | `100644` / `d0b90d3767ab7ac89c14f286ffd5356af8a361a2` (identical at `4e02380` and `b8ac9ea`) |
| Size / SHA-256 | 3,642 bytes / `d648f1e647cf2e1852e6cf0e435bdc97f2f0edcf24f3e3b830057cce89e3c231` |
| Text domain | UTF-8, no BOM, LF only, final newline, no NUL, form feed, vertical tab or U+2028/2029 |
| Redaction backstop | zero hits (the 5D2 read would not redact it, so the diff generator will not refuse it) |
| Attributes | none (`.gitattributes` names only `experiments/pi_harness_cfg1/pi_profile_policy/** -text`); no `.gitmodules` |
| Existing test path | `tests/test_issue_parser.py` (8 tests), unchanged. It is not run by P1C |
| Sensitivity | low: pure string parsing, no I/O, no authority, no credential handling |

**Task (issue 9101, a local identifier, not a GitHub issue):**
*Ignore heading-like lines inside fenced code blocks in the issue parser.*

The current parser treats a line such as `## Goal` as a section heading even
inside a fenced block (an example body pasted into an issue). This truncates
the enclosing section and invents a new one. The fix is a small, meaningful,
reviewable change of roughly ten lines in one function. Behavior outside fences
must not change. The human can check the whole diff against the stated fence
rule.

Why this task suits a first pilot:

- One self-contained function. The model needs no other file.
- The specification is complete and fits in the Goal prose that P1B actually
  sends. P1B sends the title, summary, scope summary, non-goals and proposed
  steps. It does **not** send acceptance criteria, so the full rule is in Goal.
- A wrong answer is easy to see in the diff (fence-length handling, tilde
  fences, the unclosed-fence case).
- A later, separately authorized H6–H9 could verify it against an existing
  test file.

Because the change is limited to a single file, P1C adds no new test. A
regression test would be a separate, later change.

### 2.1 Issue body (validated offline)

Save as `%P1C_IN%\02_issue_body.md` (UTF-8, no BOM). The Scope section contains
only the target. Non-goals contain no path-like or `name.ext` token, so the
plan's forbidden list stays `[.git, .git/**]`.

```markdown
## Goal
Make parse_issue_body treat every line inside a fenced code block as ordinary section text instead of a possible heading. A fence opens on a line whose first non-blank characters are a run of three or more backticks or three or more tildes. It closes on the next line whose first non-blank characters are a run of the same character at least as long as the opening run, followed only by whitespace. While a fence is open, including its opening and closing lines, no line is matched as a heading: the line is kept in the current recognized section exactly as other text is, or dropped when no recognized section is open. A fence that is never closed stays open to the end of the body. Parsing outside fenced code blocks is unchanged.

## Scope
- `src/ai_dev_orchestrator/github/issue_parser.py`

## Non-goals
- Do not change the canonical section names, the required or optional section lists, or the heading normalization rules
- Do not change the public names, the function signature or the ParsedIssue data class
- Do not add any import beyond the modules the file already imports
- Do not interpret indented code blocks, HTML blocks or block quotes
- Do not modify any other file

## Acceptance Criteria
- A body whose Scope section contains a fenced block holding a heading-like Goal line keeps that line inside Scope and starts no Goal section
- Bodies without fences parse exactly as before, and the existing issue parser tests still pass
- The proposed diff touches only the one target file

## Required Verification
- Prose only, never executed: a human reads the whole diff. Running the existing issue parser tests needs its own later authorization.
```

Offline check: `generate-plan` on this body and the config in §4.2 returned
exit 0 with `files_likely_to_change = [src/ai_dev_orchestrator/github/issue_parser.py]`,
`files_forbidden_or_out_of_scope = [.git, .git/**]`, five non-goals, and no
risks or open questions. The config loads through the shipped loader.

## 3. Clone and workspace authority checks

| # | Requirement | How it is established | Who |
|---|---|---|---|
| C-1 | A **new** disposable clone, never a working checkout and never the Alpha-0 clone | `C:\aido_p1c_ws\run01` must not exist before step 1 | operator |
| C-2 | Clone `HEAD` is exactly `b8ac9ea2f85adaa9a56a17bb36b2be62f7bd63df` | `git -C <ws> rev-parse HEAD` compared with the recorded value. A mismatch is a STOP, not a reason to check out another commit | operator, then AIDO binds it |
| C-3 | Target tracked as the expected blob | `git -C <ws> rev-parse HEAD:<target>` = `d0b90d37…` | operator |
| C-4 | `core.autocrlf=false` in the clone's own config | `git clone -c core.autocrlf=false`, then `config --local --get` | operator |
| C-5 | Top level = `repo.workspace_path`, wholly clean, no submodule, no unmerged/assume-unchanged/skip-worktree entries, no execution-capable Git config visible to AIDO (global included, e.g. a git-lfs `filter.*`) | Alpha-0 helper `preflight` (read-only), then AIDO's own `_run_git_preflight` in `prepare` and twice more in `run` | AIDO |
| C-6 | Target is canonical, `ALLOWED` and writable by path policy, in `files_likely_to_change`, not forbidden | `prepare`'s target gate (`target_out_of_scope`, `target_not_writable`, `target_path_not_normal`) | AIDO |
| C-7 | Text domain and size admitted by 5D2 (`max_file_bytes` 50,000) | the 5D2 read inside `prepare` and `run` | AIDO |
| C-8 | Config, plan, evidence, ledger and authorization all outside the clone | layout §4; AIDO refuses `*_inside_workspace` and `*_linked` | AIDO |
| C-9 | AIDO-observed state is the authority | Git is observed before and after the read, at the same `HEAD`, in both `prepare` and `run`. The operator's snapshot is a record, not authority (D-6) | AIDO |

The helper defaults to `--verified-commit 39d81ba` and would stop on the P1B
source. P1C passes `--verified-commit b8ac9ea…`, and the helper then pins AIDO's
`src/` to the P1B baseline. The helper code itself is not changed.

## 4. External layout

### 4.1 Directories

| Purpose | Path | Lifecycle |
|---|---|---|
| AIDO runtime (read-only use) | `C:\dev\ai_dev_orchestrator` @ `b8ac9ea` | unchanged by the pilot |
| Disposable clone (`repo.workspace_path`) | `C:\aido_p1c_ws\run01` | P1C writes nothing. Delete it only after the pilot is closed |
| Run directory | `C:\Users\LEVIN-Z\AppData\Local\aido_p1c\run01` | `config\ inputs\ artifacts\ logs\ helpers\ state\ review\` |
| Evidence directory | `C:\Users\LEVIN-Z\AppData\Local\aido_p1c\run01\evidence` | source-bearing (request and accepted response). Inherits the per-user AppData ACL. May be archived freely |
| **Authorization ledger** | `C:\Users\LEVIN-Z\AppData\Local\aido_ledger\supervised_implementer` | **persistent**; see §4.3 |

Why these paths:

- `AppData\Local` is per-user (owner, SYSTEM and Administrators only by
  default), real (not a junction), and not a OneDrive Known Folder. It is
  suited to source-bearing evidence without any ACL edit.
- The clone sits on a short root path. AIDO's longest tracked path is 135
  characters, so the clone stays well under `MAX_PATH`.
- The ledger and the evidence are disjoint: neither contains the other
  (`authorization_ledger_not_independent`). Both are outside the clone.
- Write every path in this exact case. AIDO compares the given spelling with
  its canonical form and refuses an 8.3 short name or a link.

### 4.2 Project config

Save as `%P1C_CFG%` = `<run dir>\config\p1c_project.yaml` (UTF-8, no BOM). It
holds no secret and no endpoint. Every authority not needed for P1C is
**disabled**: `workspace_write`, `controlled_verification` and
`controlled_review` are all false. The P1C config therefore cannot reach H6 or
beyond.

```yaml
# ALPHA-P1C pilot project config. NO SECRETS. Connection details come only
# from the AIDO_LITELLM_* environment of the run window (H4S).
project_id: aido-p1c-pilot
display_name: AIDO ALPHA-P1C first live supervised implementer pilot

repo:
  workspace_path: "C:/aido_p1c_ws/run01"
  github_repo: "zlw1987/ai_dev_orchestrator"
  default_base_branch: "main"
  branch_prefix: "p1c"             # required by the schema; nothing creates branches

workspace_policy:
  deny_outside_workspace: true
  allow_symlinks: false
  max_changed_files: 1

allowed_paths:
  - "src/ai_dev_orchestrator/github/issue_parser.py"
protected_paths: []
forbidden_paths:
  - ".git"
  - ".git/**"

real_model_planning:               # not used: the plan is generated offline
  enabled: false
  allowed_models: []

read_only_workspace_inspection:    # not used
  enabled: false

read_only_workspace_content:       # the 5D2 read prepare and run perform
  enabled: true
  max_files: 1
  max_file_bytes: 50000
  max_total_bytes: 50000
  allow_protected_paths: false

workspace_write:                   # P1C stops before H6: no write authority
  enabled: false

controlled_verification:           # not part of P1C
  enabled: false

controlled_review:                 # not part of P1C
  enabled: false

supervised_implementer:
  enabled: true
  live_transmission_enabled: true
  candidate: "SUP-D"
  model: "qwen3.8-27b"
  provider: "litellm"
  structured_output: false
  allow_insecure_http: true        # acknowledgement only; never a security claim
  attempt_timeout_seconds: 300.0   # bounds AIDO's wait only, not backend inference
  authorization_ledger_dir: "C:/Users/LEVIN-Z/AppData/Local/aido_ledger/supervised_implementer"
```

The following are deliberately left at their defaults:

- `max_output_tokens` is absent, so there is no product-level token cap.
- The response-body limit is P1B's fixed 16 MiB transport bound.
- Transport retries are forced to 0 by P1B.

`allow_insecure_http: true` is set only because the endpoint is expected to be
plaintext. If the operator's endpoint turns out to be https, set it to
`false` before `prepare`. The value is bound into the authorization.

### 4.3 Ledger lifecycle (authorized and persistent)

- Created once, by the operator, before `prepare`. It is **never** created
  inside the run directory, the evidence directory or the clone.
- It is **not** deleted, pruned, rotated, moved or restored when the pilot
  ends, when evidence is archived, or when the clone or run directory is
  deleted. The tombstones are the only proof that a run id is spent.
- It is not placed under OneDrive, File History or any sync or restore tool.
  Restoring a pre-consumption copy is outside the threat model (A-19), and P1C
  avoids it by placement.
- Pruning, if ever wanted, needs its own decision. Per P1B record §7.5 it is
  unsafe in the F-4 state (tombstone present, issuance record undeletable).
- The ledger holds no source, credential, URL or header, so it needs no
  special ACL beyond the per-user default.

## 5. AUTH-PILOT decision draft (D-10)

> **AUTH-PILOT — ALPHA-P1C first live supervised implementer pilot**
>
> **Status:** DRAFT — not approved. It becomes effective only when the operator
> fills the approval line below. Approving it does **not** consent to a
> transmission; that is H4S, per run.
>
> | Field | Value |
> |---|---|
> | Decision id | `AUTH-PILOT-P1C-01` |
> | AIDO runtime | `C:\dev\ai_dev_orchestrator` at `b8ac9ea2f85adaa9a56a17bb36b2be62f7bd63df`, clean |
> | Repository | `zlw1987/ai_dev_orchestrator`, cloned from `https://github.com/zlw1987/ai_dev_orchestrator.git`, branch `main` |
> | Clone | `C:\aido_p1c_ws\run01`. New, disposable, created only by §6 step 2. Never a working checkout, never the Alpha-0 clone |
> | Clone HEAD | `b8ac9ea2f85adaa9a56a17bb36b2be62f7bd63df`. Any other value: STOP |
> | Target file | `src/ai_dev_orchestrator/github/issue_parser.py`, blob `d0b90d37…`, SHA-256 `d648f1e6…c231`, 3,642 bytes |
> | Task | Issue 9101 (local id): ignore heading-like lines inside fenced code blocks (§2.1) |
> | Role / candidate / model | `supervised_implementer` / `SUP-D` / `qwen3.8-27b` |
> | Provider / backend | `litellm` contract; the existing corporate OpenAI-compatible API. Endpoint from the run window's environment only, never written down |
> | Transport | plaintext http expected: `allow_insecure_http: true` plus the exact per-run acknowledgement |
> | AIDO wait bound | `attempt_timeout_seconds: 300.0`. Bounds AIDO's wait only |
> | Token cap | none (`max_output_tokens` absent) |
> | Config / evidence / ledger | §4.1 paths |
> | Operator | `<OPERATOR_NAME>` |
> | Grants | Running `prepare` and then `run` **once** against this clone and file, for exactly one HTTP request carrying exactly one source file. A refused `run` (exit 1, authorization untouched) may be retried within the same authorization. A new `prepare` after a spent authorization needs the operator's explicit say-so, recorded in the run log |
> | Does not grant | H4S consent (separate, per run); H6 diff approval; any write, verification, review, branch, commit, push or PR; a second model request; a fallback model; a vllm provider; structured output; any other file, repository or clone; reuse of H9b or any earlier transmission authorization |
> | Ends at | `next_step: human_exact_diff_approval_required`. The pilot qualifies nothing |
>
> **Approval:** `I approve AUTH-PILOT-P1C-01` — `<OPERATOR_NAME>`, `<ISO-8601 with offset>`

## 6. Operator sequence (Windows CMD)

`window A` runs everything except the transmission and **never** holds an
`AIDO_*` provider variable. `window B` exists only for step 6.

### Step 0 — prerequisites

1. Resolve §8 B-1, so that the remote `main` is `b8ac9ea`.
2. The operator approves AUTH-PILOT (§5).

### Step 1 — run environment (window A)

Create `C:\Users\LEVIN-Z\AppData\Local\aido_p1c\run01\p1c_env.cmd` (UTF-8, **no
secrets**):

```bat
@echo off
rem ALPHA-P1C run environment. NO SECRETS IN THIS FILE.
set "AIDO_REPO=C:\dev\ai_dev_orchestrator"
set "AIDO_PY=%AIDO_REPO%\.venv\Scripts\python.exe"
set "P1C_BASE=b8ac9ea2f85adaa9a56a17bb36b2be62f7bd63df"
set "P1C_RUN=C:\Users\LEVIN-Z\AppData\Local\aido_p1c\run01"
set "P1C_WS=C:\aido_p1c_ws\run01"
set "P1C_LEDGER=C:\Users\LEVIN-Z\AppData\Local\aido_ledger\supervised_implementer"
set "P1C_EVID=%P1C_RUN%\evidence"
set "P1C_TARGET=src/ai_dev_orchestrator/github/issue_parser.py"
set "P1C_CFG=%P1C_RUN%\config\p1c_project.yaml"
set "P1C_H=%P1C_RUN%\helpers\a0_helper.py"
set "P1C_ART=%P1C_RUN%\artifacts"
set "P1C_IN=%P1C_RUN%\inputs"
set "P1C_LOG=%P1C_RUN%\logs"
rem Persistent user/system AIDO_* variables are inherited by every window; clear them all.
set "AIDO_LITELLM_BASE_URL="
set "AIDO_LITELLM_API_KEY="
set "AIDO_LITELLM_DEFAULT_MODEL="
set "AIDO_LITELLM_TIMEOUT_SECONDS="
set "AIDO_LITELLM_MAX_RETRIES="
set "AIDO_VLLM_BASE_URL="
set "AIDO_VLLM_API_KEY="
cd /d "%P1C_RUN%"
echo ALPHA-P1C environment loaded: %P1C_RUN%
```

```bat
mkdir "C:\Users\LEVIN-Z\AppData\Local\aido_p1c\run01"
notepad "C:\Users\LEVIN-Z\AppData\Local\aido_p1c\run01\p1c_env.cmd"
call "C:\Users\LEVIN-Z\AppData\Local\aido_p1c\run01\p1c_env.cmd"
for %d in (helpers config inputs artifacts review logs state evidence) do mkdir "%P1C_RUN%\%d"
mkdir "%P1C_LEDGER%"
git -C "%AIDO_REPO%" rev-parse HEAD
git -C "%AIDO_REPO%" status --porcelain
copy /b "%AIDO_REPO%\docs\alpha0\a0_helper.py" "%P1C_H%"
notepad "%P1C_CFG%"
```

The first `git` must print `%P1C_BASE%`, and the second must print nothing.
Paste §4.2 into the config. **H0:** read the saved config and confirm the
following:

- `workspace_path` names the clone, which does not exist yet.
- `allowed_paths` is the one target.
- The three non-P1C authorities are `false`.
- The `supervised_implementer` block matches §5.

### Step 2 — H1 clone and preflight (window A)

```bat
git clone -c core.autocrlf=false --branch main "https://github.com/zlw1987/ai_dev_orchestrator.git" "%P1C_WS%"
git -C "%P1C_WS%" config --local --get core.autocrlf
git -C "%P1C_WS%" rev-parse HEAD
git -C "%P1C_WS%" rev-parse HEAD:%P1C_TARGET%
"%AIDO_PY%" "%P1C_H%" preflight --run-dir "%P1C_RUN%" --workspace "%P1C_WS%" ^
  --target "%P1C_TARGET%" --config "%P1C_CFG%" --aido-repo "%AIDO_REPO%" --max-bytes 50000 ^
  --verified-commit %P1C_BASE%
```

Required results:

- `false`
- `b8ac9ea2f85adaa9a56a17bb36b2be62f7bd63df`
- `d0b90d3767ab7ac89c14f286ffd5356af8a361a2`
- `A0 RESULT: PREFLIGHT_PASS`

Anything else: **STOP**. Do not edit the clone to make a check pass.

### Step 3 — H2 approved plan (window A)

Save §2.1 as `%P1C_IN%\02_issue_body.md`, then run:

```bat
"%AIDO_PY%" -m ai_dev_orchestrator generate-plan --project-config "%P1C_CFG%" ^
  --repo zlw1987/ai_dev_orchestrator --issue 9101 ^
  --title "Ignore heading-like lines inside fenced code blocks in the issue parser" ^
  --body-file "%P1C_IN%\02_issue_body.md" --format json ^
  1> "%P1C_ART%\02_plan_generated.json" 2> "%P1C_LOG%\02_generate_plan.stderr.txt"
"%AIDO_PY%" "%P1C_H%" plan-draft --run-dir "%P1C_RUN%" --generated "%P1C_ART%\02_plan_generated.json" ^
  --project-id aido-p1c-pilot --out "%P1C_ART%\02_approved_plan.DRAFT.json"
copy "%P1C_ART%\02_approved_plan.DRAFT.json" "%P1C_ART%\02_approved_plan.json"
notepad "%P1C_ART%\02_approved_plan.json"
```

**H2.** Read the whole plan and confirm that `files_likely_to_change` is
exactly the target. Then fill only the `approval` block:

| Field | Value |
|---|---|
| `approved_by` | `<OPERATOR_NAME>` |
| `approved_at` | ISO-8601 with offset |
| `approval_text` | `I approve this L1 plan for L2 implementation` |
| `source` | `manual` |

```bat
"%AIDO_PY%" "%P1C_H%" approval-check --run-dir "%P1C_RUN%" --kind plan ^
  --draft "%P1C_ART%\02_approved_plan.DRAFT.json" --approved "%P1C_ART%\02_approved_plan.json"
"%AIDO_PY%" -m ai_dev_orchestrator l2-dry-run --project-config "%P1C_CFG%" ^
  --approved-plan "%P1C_ART%\02_approved_plan.json" --apply-approved-plan --format json ^
  1> "%P1C_ART%\02_l2_dry_run.json" 2> "%P1C_LOG%\02_l2_dry_run.stderr.txt"
set "P1C_RC=%ERRORLEVEL%"
echo l2-dry-run-rc=%P1C_RC%
"%AIDO_PY%" "%P1C_H%" snapshot --run-dir "%P1C_RUN%" --step 02-end --rc %P1C_RC% --expect baseline
```

Required results, in order:

1. `A0 RESULT: PLAN_DRAFT_READY`
2. `A0 RESULT: APPROVAL_CONSISTENT kind=plan`
3. `l2-dry-run-rc=0`
4. `A0 RESULT: SNAPSHOT_OK`

### Step 4 — P1 prepare (window A; offline, no environment read, no network)

```bat
"%AIDO_PY%" -m ai_dev_orchestrator l2-supervised-implementer-prepare ^
  --project-config "%P1C_CFG%" --approved-plan "%P1C_ART%\02_approved_plan.json" ^
  --target-path "%P1C_TARGET%" --evidence-dir "%P1C_EVID%" ^
  --out "%P1C_ART%\03_authorization.DRAFT.json" --prepare-supervised-implementation
echo prepare-rc=%ERRORLEVEL%
dir /b "%P1C_LEDGER%"
```

Required results:

- `prepare-rc=0`.
- The ledger holds exactly one new `<run_id>.issued.json`.
- On stderr, check the target, the source byte count and SHA-256 (they must
  match §2), the model, the provider, `run_id`, `expires_at` and
  `binding_sha256`.
- **Write down `binding_sha256` and `expires_at`.** The 60-minute window
  starts at `prepared_at`.

### Step 5 — H4S per-run consent (human only)

```bat
copy "%P1C_ART%\03_authorization.DRAFT.json" "%P1C_ART%\04_authorization.json"
notepad "%P1C_ART%\04_authorization.json"
```

Edit **only** the `consent` block. Do not touch `bound`. Save as UTF-8
without a BOM.

| Field | Value (typed by the operator) |
|---|---|
| `consented_by` | `<OPERATOR_NAME>` |
| `consented_at` | now, ISO-8601 with offset. It must be at or after `prepared_at` and no more than 5 minutes ahead of the clock |
| `source` | `manual` (already set) |
| `binding_sha256` | the value `prepare` printed |
| `endpoint_scheme` | `http` |
| `endpoint_host` | the corporate host, typed by the operator, as the host name or address only |
| `endpoint_port` | the **effective** port as a JSON number: the explicit port in the base URL, or `80` for http without one |
| `consent_text` | `I consent to sending this one approved file to this model and endpoint for one supervised implementer request` |
| `plaintext_acknowledgement` | `I acknowledge this transmission is NOT TLS-ENCRYPTED` (replaces `null`) |

### Step 6 — P2 run: the one transmission (window B)

Open a **new** CMD window and run:

```bat
call "C:\Users\LEVIN-Z\AppData\Local\aido_p1c\run01\p1c_env.cmd"
set "AIDO_LITELLM_BASE_URL=<typed by the operator; never saved to a file>"
set "AIDO_LITELLM_API_KEY=<typed by the operator; never saved to a file>"
set "AIDO_LITELLM_DEFAULT_MODEL=qwen3.8-27b"
"%AIDO_PY%" -m ai_dev_orchestrator l2-supervised-implementer-run ^
  --project-config "%P1C_CFG%" --approved-plan "%P1C_ART%\02_approved_plan.json" ^
  --authorization "%P1C_ART%\04_authorization.json" --evidence-dir "%P1C_EVID%" ^
  --transmit-approved-source --real-implementer 1> "%P1C_ART%\06_provenance.json"
set "P1C_RC=%ERRORLEVEL%"
>>"%P1C_LOG%\06_run_rc.txt" echo run-rc=%P1C_RC%
echo run-rc=%P1C_RC%
exit
```

- The loader requires `AIDO_LITELLM_DEFAULT_MODEL` to be non-blank, but P1B
  overrides it with the registry model. Timeout and retries stay cleared:
  P1B binds 300 s and forces 0 retries.
- stderr is **not** redirected, so the operator sees the
  `SOURCE TRANSMISSION` banner. Confirm that it names the expected host and
  port, `qwen3.8-27b`, `litellm`, `NOT TLS-ENCRYPTED`, the target, and 3,642
  bytes.
- Close window B immediately afterwards, so the key does not stay in a live
  shell.

Exit codes:

| Code | Meaning | Next step |
|---|---|---|
| 0 | proposal produced (diff or no change) | step 7 |
| 1 | refused before transmission | If `%P1C_LEDGER%\<run_id>.consumed.json` does not exist, nothing was sent and the authorization is untouched: fix the cause and rerun step 6 before `expires_at`. If it exists, the authorization is spent and nothing was sent |
| 4 | request worker started, no usable proposal | treat the source as **sent**. On a stall, AIDO stopped waiting; the backend may still be running inference. Do not prepare again without the operator's explicit decision |
| 5 | request worker started, evidence incomplete | treat the source as **sent** |

Spent or unspent is decided by the **ledger** tombstone, not by the evidence
directory (P1B-FU1).

### Step 7 — post-run checks and STOP (window A)

```bat
type "%P1C_LOG%\06_run_rc.txt"
"%AIDO_PY%" "%P1C_H%" snapshot --run-dir "%P1C_RUN%" --step 07-post-run --rc <run-rc from the line above> --expect baseline
dir /b "%P1C_LEDGER%"
dir /b "%P1C_EVID%"
```

Required results:

- `A0 RESULT: SNAPSHOT_OK`: the clone's HEAD, clean status and target hash are
  unchanged, because P1B writes nothing.
- The ledger shows `<run_id>.consumed.json` and no `<run_id>.issued.json`.
- `<evidence>\<run_id>\` holds `outcome.json`, `provenance.json` and, on
  success, `diff-proposal.json`.

Read the proposed diff, then **STOP** at `human_exact_diff_approval_required`.
H6 and everything after it need a separate authorization.

## 7. Remaining prerequisites before real transmission

1. **B-1 resolved** (§8): the remote `main` equals `b8ac9ea`.
2. **AUTH-PILOT approved** by the named operator (§5).
3. **Git config visible to AIDO is clean.** The helper preflight checks it.
   If a global `filter.lfs.*` (from `git lfs install`) or any
   `credential.*`/`alias.*`/`include*` key exists in the user's global config,
   the preflight stops and the global config must be changed by the operator
   first. This could not be checked from here, because the global config lies
   outside the AIDO workspace boundary.
4. **The endpoint facts are known to the operator**: scheme, host and
   effective port, and whether a key is required. If the endpoint is https
   with a private CA, P1B fails closed (`transport_failed`; record §3.3), and
   the pilot cannot run as designed.
5. **The endpoint must accept** the model id `qwen3.8-27b` exactly as written.
   P1B refuses a response that names a different model.
6. Steps 1–4 complete with every required result, and step 6 starts before
   `expires_at`.

## 8. Material blockers

- **B-1 (material for the pilot as specified): P1B is not on the remote.** The
  P1C brief says P1B was committed and pushed. Locally `main` is `b8ac9ea`,
  `ahead 1`. But `git ls-remote origin` on 2026-10-15 returned
  `refs/heads/main = 4e02380` and no other branch containing `b8ac9ea`. A clone
  of `main` would therefore get `4e02380` and fail C-2.

  The target file is byte-identical at both commits, so the pilot content is
  not affected. Only the recorded HEAD and the "pushed" baseline are. Resolve
  it in one of two ways:
  - the operator pushes `b8ac9ea` (preferred; nothing in this document
    changes); or
  - the operator records `4e02380` as the clone HEAD in AUTH-PILOT instead.

No other material blocker was found. P1B's commands, config schema, consent
schema and phrases, ledger rules and exit codes support this pilot without any
change.

---

**ALPHA-P1C PILOT PREPARED — AWAITING AUTH-PILOT HUMAN APPROVAL.** No model
request was executed.
