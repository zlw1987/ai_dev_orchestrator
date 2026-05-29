# CLAUDE.md

This file is the **operating guide for Claude Code** in this repository. Read it
before doing any work here.

## Workspace boundary

- **Allowed:** `C:\dev\ai_dev_orchestrator` — operate only inside this folder.
- **Forbidden** (do not read, search, list, or modify):
  - `C:\dev\mis_project`
  - `C:\dev\a8_oa`
  - `C:\dev\bible_reading_v2`
  - any parent directory above `C:\dev\ai_dev_orchestrator`

## Current phase

- **Phase 0 (bootstrap): complete.**
- **Phase 1 (next): config + workspace policy.**

## Role split

- **ChatGPT** = architect / planner / reviewer / prompt writer.
- **Claude Code** = implementation tool for this orchestrator project.
- Claude Code **must not broaden scope** beyond the current prompt. Do exactly
  what the active task asks — no speculative extras.

## Current non-goals

None of the following are implemented yet, and must not be added unless a future
prompt explicitly asks:

- No GitHub API calls yet.
- No LiteLLM calls yet.
- No agent logic yet.
- No file editing engine yet.
- No command execution engine yet.
- No LangGraph / CrewAI / AutoGen / n8n (no agent framework).

## Coding discipline

- One phase at a time.
- Do not implement future phases early.
- Tests are required for implementation phases.
- Do not commit unless the user approves the diff.

## Safety principles

- **Workspace boundary enforcement is core** to this project.
- Model roles (implementer / reviewer / fixer) must be **configurable**.
- **No external paid AI API by default.** Internal LiteLLM is the intended
  default provider; OpenAI / Anthropic / Copilot / Codex are optional, future,
  and disabled by default.
- **Secrets must only come from environment variables** — never stored in files.
