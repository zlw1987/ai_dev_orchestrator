# Alpha-0 Operator Runbook — Windows CMD

> **Status: READY FOR OPERATOR EXECUTION** against AIDO source identical to
> `39d81bac799d33cba66c38e09fb6588122d39fb6` (`src/` and `pyproject.toml`).
> The preflight refuses to run if AIDO's source differs from that commit.
>
> **Shell: `cmd.exe` only.** Do not paste these commands into PowerShell.
> **Helper:** [docs/alpha0/a0_helper.py](alpha0/a0_helper.py), Python standard
> library only, copied into the run directory and executed from there.

This runbook converts the accepted Alpha-0 workflow into CMD commands. It does
**not** change the workflow:

| # | Accepted workflow step | AIDO command (shipped) | Human boundary |
|---|---|---|---|
| 1 | Dedicated clean clone of a low-risk repository | — (`git clone`, then helper preflight) | H1 repository and target selection |
| 2 | Human-approved L1 plan | `generate-plan`, then `l2-dry-run` (offline validation) | **H2 plan approval** (exact sentence) |
| 3 | Bounded single-file workspace read | `l2-read-workspace-files` | — |
| 4 | Externally supplied `proposed-content.v1` | — (supplied file, helper check) | H4 supplier accepted |
| 5 | Deterministic diff proposal | `generate-diff-proposal` | — |
| 6 | Human approval of the exact diff | `l2-preview-file-edits` (offline validation) | **H6 diff approval** (exact sentence) |
| 7 | Existing single-file writer | `l2-apply-approved-file-edit` | **H7 go/no-go to write** |
| 8 | Controlled verification | `l2-verify-approved-file-edit` | **H8 consent to run unsandboxed code** |
| 9 | Existing independent reviewer | `l2-review-approved-file-edit` | **H9 consent to transmit source-derived code** |
| 10 | Human commit or restore, then final-state checks | — (human `git`, then helper snapshot) | **H10 commit-or-restore decision** |

The offline validators in steps 2 and 6 touch no workspace. They make the
shipped strict parsers check each human-edited artifact before anything acts on
it, and they do not add a step to the workflow.

---

## Contents

- [0. Read before starting](#0-read-before-starting)
- [Step 0. Operator setup](#step-0-operator-setup)
- [Step 1. Dedicated clean clone and real-repository preflight](#step-1-dedicated-clean-clone-and-real-repository-preflight)
- [Step 2. Human-approved L1 plan](#step-2-human-approved-l1-plan)
- [Step 3. Bounded single-file workspace read](#step-3-bounded-single-file-workspace-read)
- [Step 4. Externally supplied proposed-content.v1](#step-4-externally-supplied-proposed-contentv1)
- [Step 5. Deterministic diff proposal](#step-5-deterministic-diff-proposal)
- [Step 6. Human approval of the exact diff](#step-6-human-approval-of-the-exact-diff)
- [Step 7. Single-file write](#step-7-single-file-write)
- [Step 8. Controlled verification](#step-8-controlled-verification)
- [Step 9. Independent reviewer](#step-9-independent-reviewer)
- [Step 10. Human commit or restore, then final-state checks](#step-10-human-commit-or-restore-then-final-state-checks)
- [Appendix A. Project config template](#appendix-a-project-config-template)
- [Appendix B. CLI options verified against shipped source](#appendix-b-cli-options-verified-against-shipped-source)
- [Appendix C. Exit codes and decision table](#appendix-c-exit-codes-and-decision-table)
- [Appendix D. Artifacts, schemas and exact approval wording](#appendix-d-artifacts-schemas-and-exact-approval-wording)
- [Appendix E. Conversion findings](#appendix-e-conversion-findings)

---

## 0. Read before starting

### 0.1 Rules that apply to every step

1. **One run directory per attempt.** Never reuse a run directory, an artifact
   filename, or a redirect target. Every `1>` below writes a new file.
2. **Every artifact, helper, config and log lives in the run directory,
   outside the target workspace.** Never `cd` into the workspace for an AIDO
   step. All AIDO and helper commands run from `%A0_RUN%`.
3. **Record every exit code.** Each AIDO command is followed by
   `set "A0_RC=%ERRORLEVEL%"` on its own line and then by a helper `report`
   and/or `snapshot` that writes the code, file hashes, `HEAD` and Git status
   to `%A0_RUN%\logs\a0_ledger.jsonl`.
4. **Read the `A0 RESULT:` line after every helper call.** Anything with
   `STOP` in it ends the run at that point. Go to
   [Appendix C](#appendix-c-exit-codes-and-decision-table). Never continue
   past a `STOP`.
5. **Never retry a write.** The writer (step 7) runs at most once per run
   directory. If it refused, the run ends. A new attempt needs a new run
   directory and new approvals.
6. **Never repair an artifact by hand** except to fill in the four approval
   fields described in steps 2 and 6. If an AIDO command or helper rejects an
   artifact, fix its *input* and regenerate it.
7. **Humans approve; nothing else does.** The helper writes approval drafts
   whose four approval fields are **empty strings**. Only a human types those
   values. No script in this runbook generates, fills, copies or signs an
   approval.
8. **Verification is unsandboxed execution.** Steps 8 and 9 each launch the
   project's own configured program, which runs repository-controlled code
   with no confinement. Its descendants are not tracked and may still be
   running after AIDO returns. AIDO controls only which absolute executable
   runs, with which exact arguments, where, with which minimal environment,
   how long AIDO waits, and how much output it captures.
9. **Scope every claim.** The ledger records what AIDO and the helper observed:
   exit codes, hashes, `HEAD`, Git status, and the documented report fields.
   Nothing here proves what the verification child did outside that boundary.
10. **The helper writes only inside the run directory, and checks it where it
    writes.** `plan-draft --out`, `proposed-assemble --out`, `diff-draft --out`
    and `diff-draft --diff-out` must each be an absolute path to a **new file
    directly inside** `%A0_ART%`, `%A0_IN%`, `%A0_ART%` and `%A0_REV%`
    respectively. A path anywhere else (the workspace, the run directory root,
    another subfolder, a nested folder, a relative path, a link or junction, an
    existing file) is refused at the moment of writing, whatever the command line
    said.
11. **A changed config means a new run.** There is no mid-run config amendment.
    Every snapshot compares the config, the helper and every approved artifact
    with the hash pinned earlier. If any of them changes, the run ends: start a
    fresh run directory, a fresh preflight and fresh approvals.
12. **An unproven state ends the run.** `snapshot --expect none` only *records*
    what it observed. It prints `STOP_STATE_UNPROVEN`, exits 1, and halts the run:
    no later snapshot can report success and no further workflow step is accepted.
    Only `inventory` may still be run, to close the run as a record.

### 0.2 CMD conventions

- Lines ending in ` ^` continue onto the next line. When pasting, make sure
  **nothing follows the `^`**, not even a space.
- `%ERRORLEVEL%` must be read on the line **immediately after** the command.
  Every step does this with `set "A0_RC=%ERRORLEVEL%"`.
- Values in `set "NAME=value"` must not contain `"`, `%`, `^`, `&`, `|`, `<`,
  `>` or `!`. This matters for the issue title.

### 0.3 Placeholders

The runbook does not choose a repository, a file, or a model. Replace every
`<...>` before use.

| Placeholder | Meaning | Constraint |
|---|---|---|
| `<RUN_DIR>` | This attempt's run directory, for example `C:\aido_runs\alpha0-<YYYYMMDD>-<NN>` | Absolute; new; **outside** the target workspace and outside the AIDO repository |
| `<TARGET_WORKSPACE>` | Where the dedicated clone goes | Absolute; does not exist yet; not a junction or symlink; outside `<RUN_DIR>` and the AIDO repository |
| `<TARGET_WORKSPACE_FWD>` | `<TARGET_WORKSPACE>` with `/` separators, for the YAML | Same directory |
| `<REPO_CLONE_URL>` | Clone URL of the low-risk repository | — |
| `<OWNER>/<REPO>` | GitHub `owner/repo` identity | Exactly `owner/repo` |
| `<BASE_BRANCH>` | Branch the clone checks out | — |
| `<TARGET_FILE>` | The one file to modify, repo-relative | `/` separators; only `A-Z a-z 0-9 _ - . /`; see [eligibility](#11-target-eligibility) |
| `<PROJECT_ID>` | Project id for the config and artifacts | Non-blank; no spaces |
| `<ISSUE_NUMBER>` | Positive integer identifying the change | — |
| `<ISSUE_TITLE>` | One-line title | No `" % ^ & \| < > !` |
| `<VERIFY_EXECUTABLE_FWD>` | Absolute path of the one verification program, with `/` separators | Exists; regular file; **outside** the target workspace |
| `<VERIFY_ARG_1>` … | Its exact argv tail | Used verbatim; no shell syntax; no secrets |
| `<REVIEW_PROVIDER>` | `litellm` or `vllm` | Exact, case-sensitive |
| `<REVIEW_MODEL>` | Exact reviewer model name | Non-blank |
| `<OPERATOR_NAME>` | The approving human's name | Non-blank |

---

## Step 0. Operator setup

Open **CMD window A**. Use it for steps 0 through 8 and for step 10.

### 0.1 Create the run directory and its environment file

```bat
mkdir "<RUN_DIR>"
notepad "<RUN_DIR>\a0_env.cmd"
```

Paste the following into Notepad, replace the placeholders, and save it as
**UTF-8**. The file holds **no secrets**.

```bat
@echo off
rem Alpha-0 run environment. NO SECRETS IN THIS FILE.
set "AIDO_REPO=C:\dev\ai_dev_orchestrator"
set "AIDO_PY=%AIDO_REPO%\.venv\Scripts\python.exe"
set "A0_RUN=<RUN_DIR>"
set "A0_WS=<TARGET_WORKSPACE>"
set "A0_TARGET=<TARGET_FILE>"
set "A0_PROJECT_ID=<PROJECT_ID>"
set "A0_REPO_SLUG=<OWNER>/<REPO>"
set "A0_ISSUE=<ISSUE_NUMBER>"
set "A0_TITLE=<ISSUE_TITLE>"
set "A0_CFG=%A0_RUN%\config\alpha0_project.yaml"
set "A0_H=%A0_RUN%\helpers\a0_helper.py"
set "A0_ART=%A0_RUN%\artifacts"
set "A0_IN=%A0_RUN%\inputs"
set "A0_REV=%A0_RUN%\review"
set "A0_LOG=%A0_RUN%\logs"
if /i "%~1"=="review" goto :a0_keep_reviewer_env
rem Steps 0-8 and 10 run with NO reviewer variables in the window.
rem Persistent Windows user/system variables are inherited by every new window,
rem so they are cleared here explicitly.
set "AIDO_LITELLM_BASE_URL="
set "AIDO_LITELLM_API_KEY="
set "AIDO_LITELLM_DEFAULT_MODEL="
set "AIDO_LITELLM_TIMEOUT_SECONDS="
set "AIDO_LITELLM_MAX_RETRIES="
set "AIDO_VLLM_BASE_URL="
set "AIDO_VLLM_API_KEY="
:a0_keep_reviewer_env
cd /d "%A0_RUN%"
echo Alpha-0 environment loaded: %A0_RUN%
```

Load it. If you open a new window later, run the same `call` again.

```bat
call "<RUN_DIR>\a0_env.cmd"
for %d in (helpers config inputs artifacts review logs state) do mkdir "%A0_RUN%\%d"
```

### 0.2 Pin the tool chain

```bat
"%AIDO_PY%" -m ai_dev_orchestrator version
git -C "%AIDO_REPO%" rev-parse HEAD
git -C "%AIDO_REPO%" diff --quiet 39d81bac799d33cba66c38e09fb6588122d39fb6 HEAD -- src pyproject.toml
echo AIDO-src-diff-rc=%ERRORLEVEL%
copy /b "%AIDO_REPO%\docs\alpha0\a0_helper.py" "%A0_H%"
```

- `AIDO-src-diff-rc=0` is required. Any other value: **STOP**. This runbook was
  verified only against that source.
- The preflight repeats this check, then pins the SHA-256 of the copied helper.
  Every later snapshot re-verifies that hash.

### 0.3 Write the project config

```bat
notepad "%A0_CFG%"
```

Paste [Appendix A](#appendix-a-project-config-template), replace the
placeholders, and save it as **UTF-8**.

> **H0. Human config review.** Before continuing, read the saved config and confirm:
> - `repo.workspace_path` is `<TARGET_WORKSPACE_FWD>`, and the clone does not exist yet;
> - `allowed_paths` is exactly `<TARGET_FILE>`, `protected_paths` is empty, and `max_changed_files` is `1`;
> - you understand that `read_only_workspace_content`, `workspace_write`,
>   `controlled_verification` and `controlled_review` are each **explicitly
>   enabled**, and that each one is a separate authority that ships disabled;
> - `controlled_verification.executable` is absolute and lies outside the
>   workspace, and you accept that it and its `args` run **unsandboxed**, twice
>   (in steps 8 and 9);
> - `controlled_review.provider` and `model` name the one reviewer you accept
>   receiving source-derived material.
>
> The preflight in step 1 pins the config's SHA-256. Every later snapshot fails
> if the config changes. There is no way to accept a changed config mid-run: a
> change needs a new run directory (see Appendix C).

---

## Step 1. Dedicated clean clone and real-repository preflight

### 1.1 Target eligibility

The target repository and file must satisfy all of the following. The preflight
enforces every item marked ✔. Items marked ☐ are the operator's
responsibility.

- ✔ A dedicated clone made by this step and nothing else, whose Git top level is
  the workspace root and which has a valid `HEAD`;
- ✔ a wholly clean repository, with no staged, unstaged or untracked changes;
- ✔ no submodules, no unmerged index entries, and no assume-unchanged or
  skip-worktree entries;
- ✔ no Git configuration visible to AIDO's hardened Git environment that names
  a program or an indirection: `filter.*`, `credential.*`, `alias.*`,
  `core.hooksPath`, `core.editor`, `include.path`, `includeIf.*`,
  `extensions.*`, `diff.*.textconv`, and the rest of the list mirrored in the
  helper from `workspace/git_adapter.py`;
- ✔ the target is tracked as one ordinary blob (`100644` or `100755`). It is a
  regular file with a link count of 1 and only ARCHIVE, NORMAL or
  NOT_CONTENT_INDEXED attributes, and it is at most 50,000 bytes;
- ✔ the target is valid UTF-8 with no BOM, no NUL, no form feed, vertical tab
  or Unicode line/paragraph separator, uses **one** line ending (all LF or all
  CRLF), and ends with that line ending;
- ✔ `git` on `PATH` resolves to a regular file outside the workspace;
- ☐ the repository uses **no Git LFS**;
- ☐ the target is not a protected or sensitive file (the writer refuses
  protected paths anyway), and it contains no secret-like text such as
  `token=`, `password:`, `api_key=`, `Bearer …` or `sk-…`. The step 3 read
  redacts such text, and the diff generator then refuses to diff a redacted
  file;
- ☐ the change is low-risk and small enough for a human to read the whole diff.

> **H1. Human selection.** Record the repository, the target file, and why both
> are low-risk in `%A0_LOG%\01_selection.txt` (`notepad "%A0_LOG%\01_selection.txt"`).

### 1.2 Clone

`core.autocrlf=false` is written into the clone's own config. AIDO's Git runs
with system config disabled (`GIT_CONFIG_NOSYSTEM=1`). Without a local setting,
your interactive `git`, which reads Git for Windows' system
`core.autocrlf=true`, and AIDO's `git` could disagree about whether the tree is
clean.

```bat
git clone -c core.autocrlf=false --branch "<BASE_BRANCH>" "<REPO_CLONE_URL>" "%A0_WS%"
set "A0_RC=%ERRORLEVEL%"
>>"%A0_LOG%\01_clone.txt" echo clone-rc=%A0_RC%
git -C "%A0_WS%" config --local --get core.autocrlf
```

The clone must exit `0` and the last command must print `false`. Otherwise:
**STOP**.

### 1.3 Real-repository preflight (must pass before anything else touches the clone)

```bat
"%AIDO_PY%" "%A0_H%" preflight --run-dir "%A0_RUN%" --workspace "%A0_WS%" ^
  --target "%A0_TARGET%" --config "%A0_CFG%" --aido-repo "%AIDO_REPO%" --max-bytes 50000
set "A0_RC=%ERRORLEVEL%"
```

The preflight is read-only. It runs only `git rev-parse`, `config --list
--name-only`, `ls-files` and `status`, with AIDO's own hardened Git options and
minimal environment, in AIDO's own gate order. It checks:

- the locations are separate;
- the config's `workspace_path` is this clone;
- no reviewer variables are present in this window;
- the target path shape;
- the Git executable, top level, `HEAD`, configuration gate, index, index tags
  and cleanliness;
- the target's file kind, attributes, link count, size and text domain;
- that AIDO's source is unchanged since the verified commit.

It writes `logs\00_preflight.json` and `state\a0_state.json`, and it pins the
config and helper hashes.

**Required:** `A0 RESULT: PREFLIGHT_PASS`. Anything else: **STOP**. Do not edit
the clone to make it pass. Pick another target or repository and start a new
run directory.

---

## Step 2. Human-approved L1 plan

### 2.1 Write the issue body

```bat
notepad "%A0_IN%\02_issue_body.md"
```

Use exactly these headings. The **Scope** section must contain the target path
and **nothing else that looks like a path or a `name.ext` token**. The offline
planner turns every such token in Scope into a `files_likely_to_change` entry,
and the helper refuses any plan whose list is not exactly `[<TARGET_FILE>]`.

```markdown
## Goal
<one or two sentences: what the change achieves>

## Scope
- `<TARGET_FILE>`

## Non-goals
- <what must not change; avoid path-like tokens here unless you mean to forbid them>

## Acceptance Criteria
- <observable result a human can check in the diff>

## Required Verification
- <prose only — this is NEVER executed; execution authority is controlled_verification in the config>
```

### 2.2 Generate the plan (offline, deterministic)

```bat
"%AIDO_PY%" -m ai_dev_orchestrator generate-plan --project-config "%A0_CFG%" ^
  --repo "%A0_REPO_SLUG%" --issue %A0_ISSUE% --title "%A0_TITLE%" ^
  --body-file "%A0_IN%\02_issue_body.md" --format json ^
  1> "%A0_ART%\02_plan_generated.json" 2> "%A0_LOG%\02_generate_plan.stderr.txt"
set "A0_RC=%ERRORLEVEL%"
"%AIDO_PY%" "%A0_H%" report --run-dir "%A0_RUN%" --step 02-generate-plan --kind generic --rc %A0_RC% ^
  --stdout "%A0_ART%\02_plan_generated.json" --stderr "%A0_LOG%\02_generate_plan.stderr.txt"
```

Required: `A0 RESULT: OK`.

### 2.3 Assemble the unapproved plan artifact

```bat
"%AIDO_PY%" "%A0_H%" plan-draft --run-dir "%A0_RUN%" --generated "%A0_ART%\02_plan_generated.json" ^
  --project-id "%A0_PROJECT_ID%" --out "%A0_ART%\02_approved_plan.DRAFT.json"
```

Required: `A0 RESULT: PLAN_DRAFT_READY`. The helper:

- removes `generate-plan`'s top-level `notice` key, which an approved artifact's
  `plan` must not contain;
- wraps the untouched plan with `plan_provenance` set to
  `engine: deterministic`, `operation: generate-plan`, `real_call: false` and
  `model: null`, plus the identity fields;
- puts an **empty** approval stub at the top of the file.

### 2.4 H2 — Human plan approval

```bat
copy "%A0_ART%\02_approved_plan.DRAFT.json" "%A0_ART%\02_approved_plan.json"
notepad "%A0_ART%\02_approved_plan.json"
```

1. Read the whole plan. Approve it only if `files_likely_to_change` is exactly
   `[<TARGET_FILE>]` and the summary, scope and non-goals are what you intend.
2. In the `"approval"` block at the top, type the four values. Change nothing
   else in the file:

   | Field | Value |
   |---|---|
   | `approved_by` | `<OPERATOR_NAME>` |
   | `approved_at` | the current time as ISO-8601 with offset, for example `2026-10-13T14:05:00+08:00` (`echo %DATE% %TIME%` shows local time) |
   | `approval_text` | `I approve this L1 plan for L2 implementation` |
   | `source` | `manual` |

   The approval text must match exactly: the same case, no trailing period, and
   no extra spaces.
3. Save with **File → Save**. The encoding must be **UTF-8**, not "UTF-8 with
   BOM".

### 2.5 Check the approval, then let AIDO validate it offline

```bat
"%AIDO_PY%" "%A0_H%" approval-check --run-dir "%A0_RUN%" --kind plan ^
  --draft "%A0_ART%\02_approved_plan.DRAFT.json" --approved "%A0_ART%\02_approved_plan.json"
```

Required: `A0 RESULT: APPROVAL_CONSISTENT kind=plan`. The helper confirms that:

- the four fields are filled;
- the sentence and source are exact;
- there is no BOM;
- nothing outside the approval block differs from the draft.

It then pins the approved file's SHA-256. If any check fails, fix the file in
Notepad and run this check again. This is an edit of the approval only, not a
repair of an artifact.

```bat
"%AIDO_PY%" -m ai_dev_orchestrator l2-dry-run --project-config "%A0_CFG%" ^
  --approved-plan "%A0_ART%\02_approved_plan.json" --apply-approved-plan --format json ^
  1> "%A0_ART%\02_l2_dry_run.json" 2> "%A0_LOG%\02_l2_dry_run.stderr.txt"
set "A0_RC=%ERRORLEVEL%"
"%AIDO_PY%" "%A0_H%" report --run-dir "%A0_RUN%" --step 02-l2-dry-run --kind generic --rc %A0_RC% ^
  --stdout "%A0_ART%\02_l2_dry_run.json" --stderr "%A0_LOG%\02_l2_dry_run.stderr.txt"
"%AIDO_PY%" "%A0_H%" snapshot --run-dir "%A0_RUN%" --step 02-end --rc %A0_RC% --expect baseline
```

Required: `A0 RESULT: OK`, then `A0 RESULT: SNAPSHOT_OK`. `l2-dry-run` reads only
the config and the artifact. It strictly parses the approval and checks identity
against the config, and it touches no workspace.

---

## Step 3. Bounded single-file workspace read

```bat
"%AIDO_PY%" -m ai_dev_orchestrator l2-read-workspace-files --project-config "%A0_CFG%" ^
  --approved-plan "%A0_ART%\02_approved_plan.json" --apply-approved-plan --read-contents --format json ^
  1> "%A0_ART%\03_workspace_content.json" 2> "%A0_LOG%\03_read.stderr.txt"
set "A0_RC=%ERRORLEVEL%"
"%AIDO_PY%" "%A0_H%" report --run-dir "%A0_RUN%" --step 03-read --kind generic --rc %A0_RC% ^
  --stdout "%A0_ART%\03_workspace_content.json" --stderr "%A0_LOG%\03_read.stderr.txt"
"%AIDO_PY%" "%A0_H%" packet-check --run-dir "%A0_RUN%" --packet "%A0_ART%\03_workspace_content.json"
"%AIDO_PY%" "%A0_H%" snapshot --run-dir "%A0_RUN%" --step 03-end --rc %A0_RC% --expect baseline
```

Required: `OK`, `PACKET_OK` and `SNAPSHOT_OK`. `packet-check` requires:

- exactly one item, for the target, with status `read`, kind `file` and
  encoding `utf-8`;
- **`redacted: false`**;
- `content_text` that hashes to the preflight pre-image. This proves the read
  saw exactly the bytes that were preflighted.

The packet contains target source text. Keep the run directory private.

---

## Step 4. Externally supplied proposed-content.v1

The final content of the target is supplied from outside AIDO, by a person or a
tool. AIDO has no model-backed implementer, and this runbook does not add one.

> **H4.** Record the supplier and how the content was produced in
> `%A0_LOG%\04_supplier.txt`.

**4.1 (normal path): a supplied `proposed-content.v1` JSON file.** Copy it to
`%A0_IN%\04_proposed_content.json`. It must be **outside** the workspace, which
the run directory already is. Its schema must be exactly:

```json
{
  "schema_version": "proposed-content.v1",
  "mode": "proposal-only",
  "changes": [
    {
      "path": "<TARGET_FILE>",
      "change_type": "modify",
      "content_text": "<the ENTIRE final file text, JSON-escaped>",
      "rationale": "<non-blank>",
      "risks": [],
      "requires_human_review": true
    }
  ],
  "assumptions": [],
  "risks": [],
  "open_questions": [],
  "requires_human_review": true,
  "next_authorization_required": "<non-blank>"
}
```

**4.1-alt (assembly path): the supplier delivers the final file instead of the
JSON.** Put the final file at `%A0_IN%\04_final_content.txt`, its byte-exact
final contents, and a one-paragraph rationale at `%A0_IN%\04_rationale.txt`.
Then:

```bat
"%AIDO_PY%" "%A0_H%" proposed-assemble --run-dir "%A0_RUN%" --final-file "%A0_IN%\04_final_content.txt" ^
  --rationale-file "%A0_IN%\04_rationale.txt" --out "%A0_IN%\04_proposed_content.json"
```

**4.2 Check the proposed content (both paths):**

```bat
"%AIDO_PY%" "%A0_H%" proposed-check --run-dir "%A0_RUN%" --proposed "%A0_IN%\04_proposed_content.json" --max-bytes 50000
"%AIDO_PY%" "%A0_H%" snapshot --run-dir "%A0_RUN%" --step 04-end --rc 0 --expect baseline
```

Required: `PROPOSED_CONTENT_OK`, then `SNAPSHOT_OK`. Beyond the schema shape,
`proposed-check` requires the content to:

- use the **same line ending as the target**;
- **end with it**;
- contain no NUL and no extra `splitlines()` boundary characters;
- differ from the current file.

The writer rebuilds the file with the target's own line ending and checks the
result against the approved post-image hash, so content that fails here would be
refused at step 7, after a human had already approved it. The check records the
content's SHA-256 as the expected post-image.

---

## Step 5. Deterministic diff proposal

```bat
"%AIDO_PY%" -m ai_dev_orchestrator generate-diff-proposal --project-config "%A0_CFG%" ^
  --approved-plan "%A0_ART%\02_approved_plan.json" ^
  --workspace-content "%A0_ART%\03_workspace_content.json" ^
  --proposed-content "%A0_IN%\04_proposed_content.json" ^
  --apply-approved-plan --generate-diff --format json ^
  1> "%A0_ART%\05_diff_proposal.json" 2> "%A0_LOG%\05_diff.stderr.txt"
set "A0_RC=%ERRORLEVEL%"
"%AIDO_PY%" "%A0_H%" report --run-dir "%A0_RUN%" --step 05-diff --kind generic --rc %A0_RC% ^
  --stdout "%A0_ART%\05_diff_proposal.json" --stderr "%A0_LOG%\05_diff.stderr.txt"
"%AIDO_PY%" "%A0_H%" snapshot --run-dir "%A0_RUN%" --step 05-end --rc %A0_RC% --expect baseline
```

Required: `OK`, then `SNAPSHOT_OK`. The proposal is `diff-proposal.v2`:

- `pre_image_sha256` is the SHA-256 of the read bytes;
- `post_image_sha256` is the SHA-256 of the proposed content;
- `applies_cleanly_checked: false`, because nothing was applied.

A failure exits `1` with stderr only. In particular, a secret-like generated diff
is refused rather than redacted.

---

## Step 6. Human approval of the exact diff

### 6.1 Assemble the unapproved diff approval and the human-readable diff

```bat
"%AIDO_PY%" "%A0_H%" diff-draft --run-dir "%A0_RUN%" --proposal "%A0_ART%\05_diff_proposal.json" ^
  --diff-out "%A0_REV%\06_proposed.diff" --out "%A0_ART%\06_approved_diff_proposal.DRAFT.json"
```

Required: `A0 RESULT: DIFF_DRAFT_READY`. The helper first requires:

- exactly one `modify` of the target;
- no omitted paths;
- `pre_image_sha256` equal to the preflight hash;
- `post_image_sha256` equal to the proposed content's hash.

It then writes the diff text **exactly as carried in the artifact** to
`review\06_proposed.diff`. It wraps the untouched proposal as
`approved-diff-proposal.v2`, with mode `file-edit-approval-only` and an **empty**
approval stub at the top.

### 6.2 H6 — Human diff approval

```bat
notepad "%A0_REV%\06_proposed.diff"
copy "%A0_ART%\06_approved_diff_proposal.DRAFT.json" "%A0_ART%\06_approved_diff_proposal.json"
notepad "%A0_ART%\06_approved_diff_proposal.json"
```

1. Read **every line** of `06_proposed.diff`. You are approving the
   transformation of the exact bytes with the printed `pre_image_sha256` into
   the exact bytes with the printed `post_image_sha256`. Nothing else is
   approved.
2. In the `"approval"` block at the top of `06_approved_diff_proposal.json`,
   type the four values. Change nothing else:

   | Field | Value |
   |---|---|
   | `approved_by` | `<OPERATOR_NAME>` |
   | `approved_at` | the current time, ISO-8601 with offset |
   | `approval_text` | `I approve this diff proposal for workspace file editing` |
   | `source` | `manual` |

   This sentence is **not** the plan sentence. Using the plan sentence here is
   rejected.
3. Save as **UTF-8** (no BOM).

### 6.3 Check the approval, then let AIDO validate it offline

```bat
"%AIDO_PY%" "%A0_H%" approval-check --run-dir "%A0_RUN%" --kind diff ^
  --draft "%A0_ART%\06_approved_diff_proposal.DRAFT.json" --approved "%A0_ART%\06_approved_diff_proposal.json"
"%AIDO_PY%" -m ai_dev_orchestrator l2-preview-file-edits --project-config "%A0_CFG%" ^
  --approved-diff-proposal "%A0_ART%\06_approved_diff_proposal.json" --apply-approved-plan --preview-file-edits --format json ^
  1> "%A0_ART%\06_preview.json" 2> "%A0_LOG%\06_preview.stderr.txt"
set "A0_RC=%ERRORLEVEL%"
"%AIDO_PY%" "%A0_H%" report --run-dir "%A0_RUN%" --step 06-preview --kind generic --rc %A0_RC% ^
  --stdout "%A0_ART%\06_preview.json" --stderr "%A0_LOG%\06_preview.stderr.txt"
"%AIDO_PY%" "%A0_H%" snapshot --run-dir "%A0_RUN%" --step 06-end --rc %A0_RC% --expect baseline
```

Required: `APPROVAL_CONSISTENT kind=diff`, `OK`, then `SNAPSHOT_OK`. The approved
diff file is now pinned. From here on, any change to it stops every later
snapshot. `l2-preview-file-edits` runs the shipped strict parse and the lexical
write policy and touches no workspace.

---

## Step 7. Single-file write

### 7.1 Pre-write gate and H7

```bat
if exist "%A0_ART%\07_write_report.json" echo A0 RESULT: STOP  a write report already exists - this run directory has already attempted a write
"%AIDO_PY%" "%A0_H%" snapshot --run-dir "%A0_RUN%" --step 07-pre --rc 0 --expect baseline
```

Required: no `STOP` line, and `A0 RESULT: SNAPSHOT_OK`. That proves:

- `HEAD` is the baseline;
- the tree is clean;
- the target is the exact pre-image;
- the config, the helper, the packet, the proposed content, the diff proposal
  and both approved artifacts are byte-identical to what was checked.

> **H7. Go/no-go.** Write `GO <OPERATOR_NAME> <time>` into
> `%A0_LOG%\07_go.txt` only if steps 1–6 all ended with their required results
> and no editor, IDE, sync tool or other process will touch the clone during
> steps 7–9. The writer supports one writer against a quiescent workspace; it
> detects interference and fails closed, but does not prevent it.

### 7.2 Write — run once

```bat
"%AIDO_PY%" -m ai_dev_orchestrator l2-apply-approved-file-edit --project-config "%A0_CFG%" ^
  --approved-diff-proposal "%A0_ART%\06_approved_diff_proposal.json" ^
  --apply-approved-plan --write-approved-file --format json ^
  1> "%A0_ART%\07_write_report.json" 2> "%A0_LOG%\07_write.stderr.txt"
set "A0_RC=%ERRORLEVEL%"
type "%A0_LOG%\07_write.stderr.txt"
"%AIDO_PY%" "%A0_H%" report --run-dir "%A0_RUN%" --step 07-write --kind write --rc %A0_RC% ^
  --stdout "%A0_ART%\07_write_report.json" --stderr "%A0_LOG%\07_write.stderr.txt"
```

### 7.3 Branch on the result

| `A0 RESULT` | Meaning | Next command | Then |
|---|---|---|---|
| `WRITTEN` | rc 0, `workspace-write-result.v1`, `outcome: written-and-verified`, and dirty paths are exactly the target | `snapshot --step 07-end --expect written` | Step 8 |
| `WRITE_REFUSED` | rc 1: AIDO refused **before** any replacement | `snapshot --step 07-end --expect baseline` | `SNAPSHOT_OK` → run ends unchanged; record it at step 10.3. Otherwise **STOP (indeterminate)** |
| `WRITE_INDETERMINATE_STOP` | rc 3: a replacement **was attempted** and its final state is unproven | `snapshot --step 07-end --expect none` (observation only: prints `STOP_STATE_UNPROVEN`, exits 1, halts the run) | **STOP.** No retry, no `git restore` by script. Human repository inspection against the baseline `HEAD` in `logs\00_preflight.json` |
| `USAGE_ERROR` | rc 2 with empty stdout: Typer rejected the command line, so nothing was read or written | `snapshot --step 07-usage --expect baseline` | Only if `SNAPSHOT_OK`: delete the empty `07_write_report.json`, correct the command line, and issue 7.2 again. This is not a retry, because the writer never started. |
| `UNEXPECTED_STOP` | anything else | `snapshot --step 07-end --expect none` | **STOP** |

Snapshot command form (fill in `--step` and `--expect` from the table):

```bat
"%AIDO_PY%" "%A0_H%" snapshot --run-dir "%A0_RUN%" --step 07-end --rc %A0_RC% --expect written
```

---

## Step 8. Controlled verification

> **H8. Consent to run unsandboxed code.** This step executes
> `controlled_verification.executable` with its configured `args`, once, in the
> clone, with a fixed minimal environment and **no** `AIDO_*`, `GITHUB_TOKEN`
> or credential variables. It is **not sandboxed**. The program may read and
> write files, reach the network and spawn children. Its descendants are not
> tracked and may outlive the command. `timeout_seconds` bounds AIDO's wait,
> not the program's life. Any new untracked, non-ignored file it creates in
> the clone, such as `__pycache__` or a cache directory, makes the
> postcondition fail (exit 3). Write `CONSENT <OPERATOR_NAME> <time>` into
> `%A0_LOG%\08_consent.txt`.

```bat
"%AIDO_PY%" -m ai_dev_orchestrator l2-verify-approved-file-edit --project-config "%A0_CFG%" ^
  --approved-diff-proposal "%A0_ART%\06_approved_diff_proposal.json" ^
  --apply-approved-plan --verify-approved-file-edit --format json ^
  1> "%A0_ART%\08_verification_report.json" 2> "%A0_LOG%\08_verify.stderr.txt"
set "A0_RC=%ERRORLEVEL%"
type "%A0_LOG%\08_verify.stderr.txt"
"%AIDO_PY%" "%A0_H%" report --run-dir "%A0_RUN%" --step 08-verify --kind verify --rc %A0_RC% ^
  --stdout "%A0_ART%\08_verification_report.json" --stderr "%A0_LOG%\08_verify.stderr.txt"
```

| `A0 RESULT` | Meaning | Snapshot `--expect` | Then |
|---|---|---|---|
| `VERIFIED` | rc 0, `outcome: verified`, HEAD unchanged, only the target dirty | `written` | Step 9 |
| `VERIFICATION_FAILED` | rc 2 **and** a JSON report with `outcome: verification-failed`. The program ran and did not pass (non-zero exit, timeout, or output cap) | `written` | **Skip step 9.** Go to step 10; restore is the expected decision |
| `WORKSPACE_UNTRUSTED_STOP` | rc 3: the program ran and the repository is no longer provably the approved state | `none` | **STOP.** Human inspection. Nothing was restored or retried |
| `REFUSED_BEFORE_EXECUTION` | rc 1: nothing was launched | `written` | **STOP**, and read the stderr category. Step 10 (restore) is the expected decision |
| `USAGE_ERROR` | rc 2 with empty stdout: the command line was rejected and nothing ran | `written` | Correct the command line, delete the empty report file, and issue step 8 again |
| `UNEXPECTED_STOP` | anything else | `none` | **STOP** |

```bat
"%AIDO_PY%" "%A0_H%" snapshot --run-dir "%A0_RUN%" --step 08-end --rc %A0_RC% --expect written
```

---

## Step 9. Independent reviewer

> **H9. Consent to transmit.** This command **runs the step 8 verification
> again**, unsandboxed, with the same caveats. Only if that returns `verified`
> does it read the configured provider's environment variables and send these
> to the one configured reviewer model:
>
> - the **one approved unified diff**;
> - selected plan prose;
> - the redacted verification output.
>
> Redaction is a best-effort backstop, **not** a guarantee that the material is
> secret-free. The verdict is advisory; no fixer, patch, commit or PR follows
> it. Before running, confirm in `%A0_CFG%` the `provider` and `model` you
> accept, and confirm the endpoint host and scheme of the URL you are about to
> set. A plaintext `http` vLLM endpoint is refused unless
> `vllm_allow_insecure_http: true`, and that setting is an acknowledgement, not
> a security property. Write `CONSENT <OPERATOR_NAME> <time> provider=<...>
> model=<...> host=<...>` into `%A0_LOG%\09_consent.txt`.

### 9.1 Open a separate window for the reviewer variables

Open **CMD window B**. Use it for step 9 only, and close it afterwards. Load the
run environment **without** clearing reviewer variables:

```bat
call "<RUN_DIR>\a0_env.cmd" review
```

Then set **only the configured provider's** variables. Skip this if they are
already defined persistently in your Windows environment. Type the values
yourself; never write them into a file:

- `provider: vllm`: `set "AIDO_VLLM_BASE_URL=<https URL ending in the OpenAI-compatible base, e.g. .../v1>"`
  is required. `set "AIDO_VLLM_API_KEY=<key>"` is optional; without it AIDO
  sends a fixed non-secret placeholder, which is not authentication.
- `provider: litellm`: `AIDO_LITELLM_BASE_URL`, `AIDO_LITELLM_API_KEY` and
  `AIDO_LITELLM_DEFAULT_MODEL` are all required and non-blank. The last one
  never selects the reviewer model, which comes only from
  `controlled_review.model`. `AIDO_LITELLM_TIMEOUT_SECONDS` and
  `AIDO_LITELLM_MAX_RETRIES` are optional and are overridden for this command.

CMD echoes typed input. Clear the screen (`cls`) after setting a key.

### 9.2 Review

This command takes **no** `--apply-approved-plan`. Passing it is a usage error
(exit 2).

```bat
"%AIDO_PY%" -m ai_dev_orchestrator l2-review-approved-file-edit --project-config "%A0_CFG%" ^
  --approved-diff-proposal "%A0_ART%\06_approved_diff_proposal.json" ^
  --verify-approved-file-edit --real-reviewer --format json ^
  1> "%A0_ART%\09a_review_packet.json" 2> "%A0_LOG%\09a_review.stderr.txt"
set "A0_RC=%ERRORLEVEL%"
type "%A0_LOG%\09a_review.stderr.txt"
"%AIDO_PY%" "%A0_H%" report --run-dir "%A0_RUN%" --step 09a-review --kind review --rc %A0_RC% ^
  --stdout "%A0_ART%\09a_review_packet.json" --stderr "%A0_LOG%\09a_review.stderr.txt"
"%AIDO_PY%" "%A0_H%" snapshot --run-dir "%A0_RUN%" --step 09a-end --rc %A0_RC% --expect written
```

Read the banner in the `type` output and confirm that the provider, endpoint
host, transport, model and structured-output mode are what you consented to. If
they are not, record it as an incident in `%A0_LOG%\09_incident.txt`.

| `A0 RESULT` | Meaning | Then |
|---|---|---|
| `REVIEWED verdict=…` | rc 0, `review-packet.v4`, embedded verification `verified`. `approve`, `changes_requested` and `needs_human_review` are all successful reviews | Close window B. Go to step 10 |
| `VERIFICATION_FAILED` | rc 2: the re-run verification did not pass, and no model was contacted | Close window B. Go to step 10; restore is expected |
| `WORKSPACE_UNTRUSTED_STOP` | rc 3, and no model was contacted | **STOP.** Human inspection |
| `REVIEWER_STAGE_FAILED` | rc 4: verification passed, then the reviewer stage failed (environment, transport, strict JSON, schema, stall, or attempt budget). The approved change is untouched by AIDO's review stage | Human decision: correct the **reviewer environment** and re-run 9.2 with the next suffix (`09b_…`), or go to step 10 without a review. Each re-run executes the verification again and may transmit again |
| `REFUSED_BEFORE_EXECUTION` | rc 1, and nothing ran | **STOP.** Read the stderr category. If the cause is the `controlled_review` block, the config cannot be amended in this run: close the run (step 10), then start a new run directory with the corrected config, a fresh preflight and fresh approvals |
| `USAGE_ERROR` | rc 2 with empty stdout | Correct the command line and re-run with the next suffix |
| `UNEXPECTED_STOP` | anything else | **STOP** |

`REVIEW STALLED` on stderr is **terminal**. AIDO's wait ended; the request,
worker and backend inference were **not** cancelled or observed to stop. Do not
start another review against the same reviewer until you are satisfied the
backend is no longer processing the abandoned request.

Close window B with `exit`.

---

## Step 10. Human commit or restore, then final-state checks

Continue in **window A**.

> **H10. Decision.** Read `07_write_report.json`, `08_verification_report.json`
> and, if present, the review packet (`review.verdict`, `review.findings`,
> `review.residual_risks`). Decide **COMMIT** or **RESTORE**. Write
> `<COMMIT|RESTORE> <OPERATOR_NAME> <time> <reason>` into
> `%A0_LOG%\10_decision.txt`. A `changes_requested` verdict, or a failed
> verification, normally means RESTORE. Alpha-0 has no fixer and no
> review/fix loop.

Both paths are **your** Git commands, run by you. AIDO never commits or
restores. Your `git` uses your own configuration, so repository or global hooks
may run during a commit.

### 10.1 COMMIT

```bat
git -C "%A0_WS%" status --porcelain=v1 --untracked-files=all
git -C "%A0_WS%" diff -- "%A0_TARGET%"
git -C "%A0_WS%" add -- "%A0_TARGET%"
git -C "%A0_WS%" commit -m "<COMMIT_MESSAGE>"
set "A0_RC=%ERRORLEVEL%"
"%AIDO_PY%" "%A0_H%" snapshot --run-dir "%A0_RUN%" --step 10-final-commit --rc %A0_RC% --expect committed
```

`--expect committed` proves all of the following:

- the tree is clean;
- `HEAD` moved;
- the new commit's **only** parent is the baseline `HEAD`;
- the commit changes **exactly** the target;
- the committed blob and the working file both hash to the approved
  post-image.

Pushing, branching and PRs are outside Alpha-0.

### 10.2 RESTORE

```bat
git -C "%A0_WS%" restore --source=HEAD --worktree -- "%A0_TARGET%"
set "A0_RC=%ERRORLEVEL%"
"%AIDO_PY%" "%A0_H%" snapshot --run-dir "%A0_RUN%" --step 10-final-restore --rc %A0_RC% --expect restored
```

`--expect restored` proves that `HEAD` is the baseline, the tree is clean, and
the target hashes to the approved pre-image.

### 10.3 Writer refused (from 7.3): no Git action

```bat
"%AIDO_PY%" "%A0_H%" snapshot --run-dir "%A0_RUN%" --step 10-final-unchanged --rc 1 --expect baseline
```

### 10.4 Close the run

Required: the final snapshot printed `A0 RESULT: SNAPSHOT_OK`. Then:

```bat
"%AIDO_PY%" "%A0_H%" inventory --run-dir "%A0_RUN%"
type "%A0_LOG%\a0_ledger.jsonl"
```

`inventory` appends its closing ledger event first, then hashes every other file
in the run directory (the ledger included, as it now stands), and writes
`logs\99_inventory.json`. The inventory's existence **closes the run**: every
later helper command, including the STOP handler, refuses to touch the ledger or
state, so the recorded hashes stay the final ones. The inventory also records
`final_state`, a description of the last snapshot:

| `final_state` | Meaning |
|---|---|
| `LAST_SNAPSHOT_OK` | the last snapshot passed its expectation. Read the ledger to see **which** step and expectation it was |
| `LAST_SNAPSHOT_NOT_OK_OR_ABSENT` | the last snapshot failed, or none was recorded |
| `UNPROVEN_HALTED` | a `snapshot --expect none` halted the run; the workspace state is unproven |

It is a record of the run directory, not a proof about the clone.

> **If the final snapshot printed `STOP_STATE_MISMATCH` or
> `STOP_STATE_UNPROVEN`, the final state is unproven. STOP.** Do not run further Git commands to "fix" it. Record the
> printed problems in `%A0_LOG%\10_incident.txt` and inspect the clone by hand
> against `baseline_head` and the pre-/post-image hashes in
> `state\a0_state.json`. The clone is dedicated and disposable, but nothing is
> deleted until a human has finished inspecting it.

---

## Appendix A. Project config template

Save as `%A0_CFG%`, which is `<RUN_DIR>\config\alpha0_project.yaml`. Keep the
`workspace_path:` line in this exact form. The preflight reads that one line
and refuses a config that does not name the preflighted clone.

```yaml
# Alpha-0 project config. NO SECRETS. Connection details come from the
# configured reviewer provider's environment variables only (step 9).
project_id: <PROJECT_ID>
display_name: <PROJECT_ID> Alpha-0

repo:
  workspace_path: "<TARGET_WORKSPACE_FWD>"
  github_repo: "<OWNER>/<REPO>"
  default_base_branch: "<BASE_BRANCH>"
  branch_prefix: "alpha0"          # required by the schema; nothing creates branches

workspace_policy:
  deny_outside_workspace: true     # the writer requires true
  allow_symlinks: false            # the writer requires false
  max_changed_files: 1

allowed_paths:
  - "<TARGET_FILE>"
protected_paths: []                # the target must not be protected; the writer refuses protected paths
forbidden_paths:
  - ".git"
  - ".git/**"

real_model_planning:               # not used: the plan is generated offline
  enabled: false
  allowed_models: []

read_only_workspace_inspection:    # not used
  enabled: false

read_only_workspace_content:       # step 3 opt-in
  enabled: true
  max_files: 1
  max_file_bytes: 50000
  max_total_bytes: 50000
  allow_protected_paths: false

workspace_write:                   # step 7 opt-in
  enabled: true
  max_file_bytes: 50000

controlled_verification:           # steps 8 and 9 opt-in -- UNSANDBOXED EXECUTION
  enabled: true
  executable: "<VERIFY_EXECUTABLE_FWD>"   # absolute, existing, OUTSIDE the workspace
  args:                                   # exact argv tail, verbatim, no shell syntax, no secrets
    - "<VERIFY_ARG_1>"
  timeout_seconds: 300             # bounds AIDO's wait (1..3600), not the program's life
  max_output_bytes: 200000

controlled_review:                 # step 9 opt-in -- source-derived code leaves the machine
  enabled: true
  provider: "<REVIEW_PROVIDER>"    # exactly litellm or vllm
  model: "<REVIEW_MODEL>"
  attempt_timeout_seconds: 90
  compact_retry_on_unusable_output: false
  vllm_allow_insecure_http: false  # vllm only; true is an acknowledgement, never a security claim
  vllm_structured_output: false    # vllm only; true with litellm is refused at the review gate
```

Notes on `controlled_verification`:

- The child environment contains only `PATH`, `SystemRoot`/`SYSTEMROOT`,
  `SystemDrive`, `ComSpec`/`COMSPEC`, `windir`, `TEMP`, `TMP`, `PATHEXT`,
  `NUMBER_OF_PROCESSORS` and `PROCESSOR_ARCHITECTURE`. Neither `HOME` nor
  `USERPROFILE` is passed, and nothing can be forwarded. A program that needs
  more fails, and that is a legitimate `verification-failed`.
- The program must leave **no new untracked, non-ignored file** in the clone.
  For a Python test runner, for example, arguments that suppress bytecode and
  cache writing avoid an exit 3. Choosing the program is the operator's
  decision; this runbook names none.
- The L1 plan's `required_verification` is prose. It is **never** command
  authority and is never run.

---

## Appendix B. CLI options verified against shipped source

These were enumerated from the Typer application itself
(`typer.main.get_command(ai_dev_orchestrator.cli.app)`, Typer 0.27.1, Python
3.14.7) at `39d81bac799d`, and cross-checked against `src/ai_dev_orchestrator/cli.py`.
Every flag defaults to off. `--format` accepts only `json`.

| Command | Required options | Consent flags (all must be given) |
|---|---|---|
| `generate-plan` | `--project-config` (must exist), `--repo`, `--issue`, `--title`, `--body-file` (must exist, outside workspace) | — |
| `l2-dry-run` | `--project-config`, `--approved-plan` | `--apply-approved-plan` |
| `l2-read-workspace-files` | `--project-config`, `--approved-plan` | `--apply-approved-plan`, `--read-contents` |
| `generate-diff-proposal` | `--project-config`, `--approved-plan`, `--workspace-content`, `--proposed-content` | `--apply-approved-plan`, `--generate-diff` |
| `l2-preview-file-edits` | `--project-config`, `--approved-diff-proposal` | `--apply-approved-plan`, `--preview-file-edits` |
| `l2-apply-approved-file-edit` | `--project-config`, `--approved-diff-proposal` | `--apply-approved-plan`, `--write-approved-file` |
| `l2-verify-approved-file-edit` | `--project-config`, `--approved-diff-proposal` | `--apply-approved-plan`, `--verify-approved-file-edit` |
| `l2-review-approved-file-edit` | `--project-config`, `--approved-diff-proposal` | `--verify-approved-file-edit`, `--real-reviewer` (**no** `--apply-approved-plan`) |

Project opt-ins checked by the commands themselves:

| Command | Opt-in | Other gates |
|---|---|---|
| `l2-read-workspace-files` | `read_only_workspace_content.enabled` | — |
| `l2-apply-approved-file-edit` | `workspace_write.enabled` | `sys.platform == "win32"` |
| `l2-verify-approved-file-edit` | `controlled_verification.enabled` | Windows |
| `l2-review-approved-file-edit` | `controlled_review.enabled`, a supported provider and a non-blank model, plus `controlled_verification.enabled` | Windows |

Neither `l2-dry-run` nor `l2-preview-file-edits` has an opt-in, and neither
touches the workspace. Every artifact path option is checked lexically against
`repo.workspace_path` **before** the file is opened.

---

## Appendix C. Exit codes and decision table

| Command | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| `generate-plan`, `l2-dry-run`, `l2-read-workspace-files`, `generate-diff-proposal`, `l2-preview-file-edits` | success; stdout is one JSON object | refused or failed; stderr only | Typer usage error | — | — |
| `l2-apply-approved-file-edit` | written and verified | refused **before** any write; target unchanged | Typer usage error | **write attempted, state indeterminate** | — |
| `l2-verify-approved-file-edit` | `verified` | refused before execution | **verification did not pass** (report on stdout) *or* Typer usage error (empty stdout) | **workspace untrusted** | — |
| `l2-review-approved-file-edit` | valid review (any verdict) | refused before execution | verification did not pass *or* Typer usage error | workspace untrusted | reviewer stage failed after verification passed |

Exit 2 is ambiguous for `verify` and `review`; see
[Appendix E](#appendix-e-conversion-findings) finding 1. The helper's `report`
tells the two apart by stdout. A usage error leaves stdout empty and prints
`Usage:` to stderr. A verification failure prints a JSON report.

**Universal stop conditions.** Stop the run at:

- any helper `A0 RESULT: STOP …` or `STOP_STATE_MISMATCH`;
- any `*_STOP` class;
- exit 3 from the writer or verifier;
- a final snapshot that is not `SNAPSHOT_OK`.

At a stop: record it, inspect by hand, and do not retry, restore by script, or
continue.

**No config amendment.** The helper has no `config-amend` command. The config's
hash is fixed at preflight and every snapshot re-checks it. A changed project
configuration, of any block, requires a **fresh run directory, a fresh preflight
and fresh approvals**. The old run is closed with `inventory` and kept as a record.

**`snapshot --expect none` is observation only.** It is used where no expected
state exists to compare against (an indeterminate write, an untrusted workspace,
an unexpected stop). It records `HEAD`, Git status and the target's hash, then
prints `A0 RESULT: STOP_STATE_UNPROVEN`, exits 1, and halts the run. It never
prints `SNAPSHOT_OK`. After it, the helper accepts no further workflow step and no
success snapshot; only `inventory` can still run.

---

## Appendix D. Artifacts, schemas and exact approval wording

| File (under `<RUN_DIR>`) | Produced by | Schema / content |
|---|---|---|
| `logs\00_preflight.json`, `state\a0_state.json` | helper `preflight` | baseline `HEAD`, pre-image SHA-256, pinned hashes |
| `artifacts\02_plan_generated.json` | `generate-plan` | `L1Plan` fields plus a top-level `notice` |
| `artifacts\02_approved_plan.DRAFT.json` | helper `plan-draft` | `ApprovedL1PlanArtifact` shape with an **empty** approval |
| `artifacts\02_approved_plan.json` | **human** | `ApprovedL1PlanArtifact`: `approval`, `plan_provenance`, `plan`, `project_id`, `repo`, `issue_number` |
| `artifacts\02_l2_dry_run.json` | `l2-dry-run` | offline validation report |
| `artifacts\03_workspace_content.json` | `l2-read-workspace-files` | mode `l2-read-workspace-files`, one item. **Contains source text** |
| `inputs\04_proposed_content.json` | external supplier, or helper `proposed-assemble` | `proposed-content.v1`, mode `proposal-only` |
| `artifacts\05_diff_proposal.json` | `generate-diff-proposal` | `diff-proposal.v2`, mode `proposal-only`, engine `deterministic` |
| `review\06_proposed.diff` | helper `diff-draft` | the artifact's `unified_diff`, verbatim |
| `artifacts\06_approved_diff_proposal.DRAFT.json` | helper `diff-draft` | `approved-diff-proposal.v2` shape with an **empty** approval |
| `artifacts\06_approved_diff_proposal.json` | **human** | `approved-diff-proposal.v2`, mode `file-edit-approval-only` |
| `artifacts\06_preview.json` | `l2-preview-file-edits` | offline preview |
| `artifacts\07_write_report.json` | `l2-apply-approved-file-edit` | `workspace-write-result.v1`, `outcome: written-and-verified` |
| `artifacts\08_verification_report.json` | `l2-verify-approved-file-edit` | `verification-result.v1`, `outcome` one of `verified`, `verification-failed`, `workspace-state-untrusted` |
| `artifacts\09a_review_packet.json` | `l2-review-approved-file-edit` | `review-packet.v4` (embeds the step-9 verification report) |
| `logs\a0_ledger.jsonl` | helper | every exit code, hash, `HEAD`, Git status and result class |
| `logs\99_inventory.json` | helper `inventory` | SHA-256 of every other run file, as of the final ledger, plus `final_state`; closes the run |

**Exact approval sentences.** Each is compared with `==`. Copy them character
for character.

| Approval | `approval_text` | `source` |
|---|---|---|
| L1 plan (step 2) | `I approve this L1 plan for L2 implementation` | `manual` |
| Concrete diff (step 6) | `I approve this diff proposal for workspace file editing` | `manual` |

---

## Appendix E. Conversion findings

These were found while converting the workflow to CMD and checking it against
the shipped source. **None required an AIDO code change.** Each is handled
inside this runbook.

1. **Exit code 2 collides for verify and review.** Typer exits `2` on any
   command-line error: an unknown option, a missing option, or a nonexistent
   `--project-config`. That is the same number `l2-verify-approved-file-edit`
   and `l2-review-approved-file-edit` use for "verification ran and did not
   pass". Reproduced at `39d81bac799d`: `l2-review-approved-file-edit
   --apply-approved-plan` → rc 2, `No such option`. *Handled:* `report`
   classifies by stdout. A usage error leaves stdout empty; a failure carries a
   `verification-failed` report.
2. **`generate-plan` output is not directly wrappable.** Its stdout has a
   top-level `notice` key and no provenance. `ApprovedL1PlanArtifact` rejects
   any `plan` key `L1Plan` does not declare, and it requires
   `plan_provenance`. *Handled:* `plan-draft` removes only `notice` and adds
   `plan_provenance` with `engine: deterministic`, `operation: generate-plan`,
   `real_call: false` and `model: null`.
3. **A UTF-8 BOM defeats every strict parser.** The artifact readers use
   `read_text(encoding="utf-8")` and require the stripped text to start with
   `{`. A BOM written by Notepad's "UTF-8 with BOM" is not stripped. *Handled:*
   save as UTF-8; `approval-check` and every helper reader refuse a BOM with a
   specific message.
4. **The generator and the writer split lines differently.** The generator uses
   `difflib` over `str.splitlines()` and hashes the proposed text raw. The
   writer splits on the file's single line ending and rebuilds with it and a
   terminal newline. If the proposed content's line ending or terminal newline
   differs from the target's, or if the content contains a `splitlines()`-only
   boundary (`\v`, `\f`, `\x1c`–`\x1e`, `\x85`, U+2028, U+2029), the diff
   proposal is accepted but the writer refuses it with exit 1. *Handled:*
   `preflight` and `proposed-check` enforce one ending, a terminal newline,
   matching endings, and no such characters.
5. **AIDO's Git does not see your Git configuration.** AIDO runs `git` with
   `GIT_CONFIG_NOSYSTEM=1` and a minimal environment. Git for Windows' system
   `core.autocrlf=true` therefore applies to your interactive `git` but not to
   AIDO's. *Handled:* the clone is made with a local `core.autocrlf=false`, and
   the preflight runs Git with AIDO's exact options and environment.
6. **The review command has a different flag set.** It takes no
   `--apply-approved-plan`. *Handled:* the step 9 command and Appendix B.
7. **Verification runs twice.** The reviewer re-runs verification internally,
   because it accepts no saved result. *Handled:* the H8 and H9 consents both
   state this, and step 9 branches on the re-run.
8. **`repo.branch_prefix` is a required config field** even though nothing
   creates branches. *Handled:* the template sets it.
9. **Persistent reviewer variables.** On the machine used for conversion,
   `AIDO_LITELLM_*` and `AIDO_VLLM_BASE_URL` are defined in the persistent
   Windows environment, so every new CMD window inherits them. AIDO itself reads
   them only after verification passes, and never forwards them to the
   verification child. *Handled:* `a0_env.cmd` clears them for steps 0–8 and 10;
   the preflight refuses to run while any is set; step 9 uses its own window.
10. **Offline-planner path extraction.** `FakeL1Planner` treats every `x/y` or
    `name.ext` token in the Scope section as a path. *Handled:* the Scope
    template names only the target, the target-path shape is restricted, and
    `plan-draft` requires `files_likely_to_change == [<TARGET_FILE>]`.

11. **Helper corrective fixes (ALPHA0-FU1).** An independent review reproduced
    four helper defects: `plan-draft` could create a file inside the target
    workspace; `config-amend` accepted a non-reviewer change (a
    `workspace_write.enabled` edit) as `CONFIG_REPINNED`; `inventory` hashed the
    ledger and then appended to it, leaving a wrong ledger hash; and
    `snapshot --expect none` could print `SNAPSHOT_OK` without proving anything.
    *Handled:* every helper output is authorized against the run directory at the
    point of writing; `config-amend` is removed; `inventory` closes the run after
    its last ledger write; `snapshot --expect none` is `STOP_STATE_UNPROVEN` and
    halts the run. No AIDO source was changed. Regressions are in
    [docs/alpha0/test_a0_helper.py](alpha0/test_a0_helper.py), run with
    `.venv\Scripts\python.exe -m pytest docs/alpha0/test_a0_helper.py -q`.

The helper was exercised only against **synthetic** repositories in a scratch
directory, with LF and CRLF targets. Its plan, packet-shape, proposed-content
and approval outputs were parsed by the shipped
`parse_approved_l1_plan_artifact`, `parse_workspace_content_packet`,
`parse_proposed_content_input`, `build_deterministic_diff_proposal`,
`parse_approved_diff_proposal_artifact` and `build_file_edit_preview`. The
shipped `apply_strict_unified_diff` reproduced the approved post-image hash for
both line endings. The Alpha-0 workflow itself, meaning the writer, verifier and
reviewer, was **not** run, and no real target repository was touched.
