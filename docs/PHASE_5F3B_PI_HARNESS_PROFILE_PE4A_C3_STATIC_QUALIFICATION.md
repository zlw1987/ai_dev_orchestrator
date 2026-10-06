# Phase 5F3B — Pi Harness Profile Evolution — PE-4A: C3_SEAM_CHANGED Static Qualification

```text
PE-4A  C3_SEAM_CHANGED STATIC QUALIFICATION  EVIDENCE / REVIEW ONLY — NOT AN AUTHORIZATION

source AIDO commit      d7bdb230599a6c9e2d0948378529cabfec6e6948
payload fingerprint     66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc
profile id              56651d0b2b6995e05b6de3aa012f5a82f276b2ac817dcce00844d1db2a9ffd67
mechanical floor        C3_SEAM_CHANGED
approvability           APPROVABILITY_FLOOR_MET
candidate authority     NON_AUTHORITY_CANDIDATE   (unchanged by this document)

PE-4A static result     see Sec.13 (disposition) and Sec.14 (findings)
independent review      D-1 ACCEPTED · D-2 ACCEPTED · D-3 ACCEPTED WITH CORRECTION (finding R-1, Sec.14)
                        C3_SEAM_CHANGED conclusion unchanged; R-1 is not C4 and not C5
PE-4B E4               REQUIRED / NOT EXECUTED / NOT YET AUTHORIZED
PE-5  approval         NOT STARTED   (no approval record, no APS r0002, no policy change)
```

**Reading rule.** This document is *evidence and review*. It grants nothing: it does not approve the profile, does not adopt it into the Approved Profile Set (APS), does not create live authorization, and does not mark any later phase complete. The three committed PE-3 candidate files are *evidence inputs* only; they were read and re-derived, never modified, copied or promoted. Anything below that reads like a conclusion about eligibility is a conclusion about *static evidence*, and PE-5 alone owns any adoption decision.

## 1. Scope and non-authority statement

**In scope (static only).** E1 (re-derive every AIDO derivation claim whose premise touches a changed seam file), E2 (manifest and exposure review), E3 (mechanical accounting and review of the *whole* non-seam payload as this first HPP profile's reference baseline), the seam-sufficiency determination, the request-building-change determination, and the C3 / C4 / C5 disposition.

**Out of scope / not done.** No Pi, Node or npm execution; no import, require or evaluation of any installed JavaScript; no `--version`/`--help`; no JS parser that evaluates modules; no T-3 / E4; no B300, model or backend contact from repository code; no credential or endpoint read; no policy, APS, results, launcher or A4 action; no change to the candidate artifacts, production Python, tests, `CLAUDE.md` or the roadmap; no staging, commit, push, branch, amend or rebase. E4 is **required but not executed** (Sec.11).

**Method and its limits.**

- *Authorized reading.* Installed bytes were read statically through the accepted no-follow reader (`pi_fs_leaves.read_payload_file_bytes`, one handle, no reparse following). Before any file was relied on, its size and SHA-256 were bound to the committed PE-3 inventory entry; after all citations were resolved every cited file was re-read and re-hashed. A fresh complete `PI-PC1` walk of the installed tree was also compared with the committed inventory at the start and again at the end of the phase (Sec.2.3).
- *Tooling.* Python standard library plus accepted AIDO pure-Python functions only. Import/require edges were extracted from file **text** by regular expressions and resolved with Node's published resolution rules re-implemented over the inventory path set (no filesystem resolution, no execution). This is not a JavaScript parser: it can over-approximate (a specifier inside a string) and under-approximate (computed specifiers). Computed specifiers are therefore enumerated and reviewed separately (Sec.7.5).
- *Line citations are computed, not typed.* Each E1 citation is an `(installed file, exact anchor text, nth occurrence)` triple resolved to a line number inside the hash-verified bytes by the analysis (223 citations, 0 unresolved, 0 digest mismatches). The analysis scripts are scratch material, not committed (this document is the single deliverable); Appendix B gives the rules in enough detail to re-implement them, and group digests to compare against.
- *Nothing here is sampled.* Where a sound review of a class was not possible individually, the class was accounted for by an explicit, total, rule-ordered partition (Sec.7) and the rule that makes its members irrelevant to an AIDO premise is stated and mechanically checkable. No class is represented by examples.

## 2. Immutable candidate identity

### 2.1 Bound identity

| Field | Value |
|---|---|
| source AIDO commit (HEAD at phase start) | `d7bdb230599a6c9e2d0948378529cabfec6e6948` (working tree clean at start) |
| payload contract / seam contract / consumer contract | `PI-PC1` / `PI-SC1` / `CFG1-CC1` (policy revision `HPP-1`) |
| payload fingerprint | `66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc` |
| profile id | `56651d0b2b6995e05b6de3aa012f5a82f276b2ac817dcce00844d1db2a9ffd67` |
| seam fingerprint (candidate) | `52ada9a1b4957bd97a139039de5bf6a9c7ffff2716098c051f82c4da00da5de9` |
| mechanical floor | `C3_SEAM_CHANGED` (reference view = committed APS head `aps.r0001.json`, which has **zero** profiles) |
| approvability | `APPROVABILITY_FLOOR_MET` (no C5 reason; no manifest path) |
| authority | `NON_AUTHORITY_CANDIDATE` |
| PE-3 exposure observation | `EXPOSURES_PROVEN_ABSENT` (31 derived exposure names) |
| declared provenance only | `@earendil-works/pi-coding-agent` 1.0.3 (`pi-agent-core` 1.0.3, `pi-ai` 1.0.3) — **never** used here to grant authority or compatibility |
| authority-scope literal | `PI_PACKAGE_PAYLOAD_AND_DECLARED_RESOLUTION_BOUNDARY` |
| external-runtime residual literal | `NOT_IDENTIFIED_BY_PROFILE` |
| discovery tool revision recorded | `PE-2b` |

The three committed files (evidence inputs, unmodified):

| File (under `experiments/pi_harness_cfg1/pi_profile_candidates/`) | Bytes | SHA-256 of committed bytes |
|---|---:|---|
| `66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc.candidate.json` | 3 734 | `16d0e8573cabf5a381d1d067856f3e2ef854918e44829f6ad3b337ef86d80c75` |
| `66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc.inventory.json` | 2 708 753 | `f84fb68dd4b90ae81b77049197373497b3b05e33cb679465cb513f6b86671e82` |
| `66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc.manifest_bundle.json` | 382 200 | `ebbc12b96729d53485f8d0dccee7b508a3e1a980209a255b64f1ede802ee72b2` |

### 2.2 Candidate re-check against the committed inventory (accepted pure-Python functions only)

| Check | Result |
|---|---|
| each of the 3 working-tree files byte-equals its `HEAD` git blob | true ×3 |
| inventory record round-trips through `inventory_from_record`; recomputed payload fingerprint equals the committed file name | true |
| inventory file bytes equal `policy_file_bytes(inventory.to_record())` | true |
| manifest bundle rebuilt via `bundle_from_record` — all 149 manifests bound to inventory entries by size and SHA-256 | true (149/149) |
| bundle file bytes equal `policy_file_bytes(bundle.to_record())` | true |
| `compute_profile_facts(inventory, bundle)` reproduces `profile_id`, `seam_digests`, `seam_fingerprint`, `declared`, `resolution_exposures` | true ×5 |
| `classify_floor(facts, head_reference_view())` | `C3_SEAM_CHANGED` (equals the candidate's recorded floor) |
| candidate files absent from the policy directory; APS head `profiles == []`; candidate profile id not present in APS bytes | true ×3 |

### 2.3 Installed-payload identity re-check

The installed Pi package root was resolved with the **accepted, unchanged P1 first-admissible-candidate functions** (`_path_entries`, `_resolve_node`, `_resolve_package_root`; nothing executed — the `node.exe` candidate is only observed). The path is omitted from this document by design. A fresh complete `PI-PC1` observation (`observe_payload`) was run at the **start** and again at the **end** of the phase: both were complete, both produced payload fingerprint `66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc`, and the canonical record bytes (with the accepted trailing LF) equal the committed inventory file. The installed payload therefore **did not drift** from the PE-3 candidate during this phase, and no mixed bytes were qualified.

## 3. The 20-file PI-SC1 seam — changed vs unchanged

Genesis column = APS `r0001` seam evidence (`evidence_id 37ba2815…`, the historical Pi 0.85.1 table). Candidate column = the installed bytes, which equal the committed candidate `seam_digests` (verified for all 20).

| # | Path | Status | Genesis sha256 | Candidate sha256 | Bytes | Lines |
|---:|---|---|---|---|---:|---:|
| 1 | `dist/cli.js` | **UNCHANGED** | `8189b66abc4f9f43…` | `8189b66abc4f9f43…` | 169 | 6 |
| 2 | `dist/core/agent-session.js` | **CHANGED** | `fb8a3981c20c8c0b…` | `35ca1dabd54d98c2…` | 163913 | 3536 |
| 3 | `dist/core/defaults.js` | **UNCHANGED** | `13196dce2ddb143f…` | `13196dce2ddb143f…` | 214 | 11 |
| 4 | `dist/core/model-config.js` | **CHANGED** | `ac983b5825f96eb2…` | `24a0e0f98672766e…` | 13747 | 294 |
| 5 | `dist/core/model-resolver.js` | **CHANGED** | `00f57b9c60f990f0…` | `66a7c13b8aff81e0…` | 26373 | 590 |
| 6 | `dist/core/model-runtime.js` | **CHANGED** | `32cd50599d9e6e00…` | `da26f76339a03145…` | 36245 | 758 |
| 7 | `dist/core/provider-composer.js` | **CHANGED** | `8eca507009d00768…` | `b088d1babb75360d…` | 24395 | 488 |
| 8 | `dist/core/sdk.js` | **CHANGED** | `6969bd56ba8e1628…` | `fe643170de3d259c…` | 15014 | 315 |
| 9 | `dist/core/system-prompt.js` | **CHANGED** | `4a57f022a27f2ae2…` | `83aa42fae07830d5…` | 7787 | 147 |
| 10 | `dist/main.js` | **CHANGED** | `f0b7e5a8419af8d1…` | `060521b0b81f9194…` | 37764 | 825 |
| 11 | `dist/modes/rpc/jsonl.js` | **UNCHANGED** | `049a9f8ca4242c79…` | `049a9f8ca4242c79…` | 1562 | 49 |
| 12 | `dist/modes/rpc/rpc-mode.js` | **CHANGED** | `e7e4724aa55c5aac…` | `631697cd35928fc8…` | 28129 | 655 |
| 13 | `node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js` | **CHANGED** | `6732a1c65c09577d…` | `65def8c7f3fa01e3…` | 28866 | 667 |
| 14 | `node_modules/@earendil-works/pi-agent-core/dist/agent.js` | **CHANGED** | `d84351e451b9fef4…` | `163ad28551f1c38b…` | 16973 | 437 |
| 15 | `node_modules/@earendil-works/pi-agent-core/package.json` | **CHANGED** | `f4c388363706ae0e…` | `3f942a1a617eca69…` | 1033 | 51 |
| 16 | `node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js` | **CHANGED** | `1e2097ced37cf0e2…` | `5a79cc5aa41dee18…` | 64669 | 1345 |
| 17 | `node_modules/@earendil-works/pi-ai/dist/api/simple-options.js` | **CHANGED** | `1caf860e028e2263…` | `9b3cc0ae6daa86fd…` | 3485 | 73 |
| 18 | `node_modules/@earendil-works/pi-ai/dist/models.js` | **CHANGED** | `42610d47fe293d99…` | `633161a0067abbb2…` | 31839 | 718 |
| 19 | `node_modules/@earendil-works/pi-ai/package.json` | **CHANGED** | `b54df5a36d523feb…` | `2c316535cf6c207c…` | 2721 | 107 |
| 20 | `package.json` | **CHANGED** | `f1738e4b42203e5f…` | `4c4956a9a414f7fb…` | 4062 | 109 |

**3 / 20 unchanged** (`dist/cli.js`, `dist/core/defaults.js`, `dist/modes/rpc/jsonl.js`); **17 / 20 changed**. This reproduces the mechanical delta stated in the brief exactly; the floor is `C3_SEAM_CHANGED` and nothing found below requires escalation to C4 or C5 (Sec.13).

The three package manifests in the seam changed, and the declared version moved from the genesis table's 0.85.1 to 1.0.3. That is *provenance*: no conclusion below depends on a version number.

## 4. E1 — claim-by-claim reuse / re-derivation matrix

**Source of the claim set.** The claims were recovered from the three documents APS `r0001` cites as genesis seam evidence — `PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md` (§1.2, §2, §3, §14.2; sha256 `dee474f0…`), `PHASE_5F3B_HARNESS_CFG1_L16_FU2_RUNTIME_CAPABILITY_OBSERVATION_DESIGN.md` (§16, F-4; `d224e4c6…`) and `PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_OC3_AMEND1_DESIGN.md` (§1; `bd8569e4…`) — as rows **G-01…G-19**. The brief additionally requires revisiting the prompt-acknowledgement ordering, settle semantics, and the H1 / H2 / OBS1 premises. Those are *not* APS-cited genesis claims (their origin is `Q1-PRE1-FU1` §1.3-1.6, AR0/AR2, `runtime_activity.py`, `ar2/handshakes.py`), so they are labelled **N-01…N-12** (kind `NEW`) rather than disguised as inherited evidence.

**Reuse rule applied.** A genesis conclusion is reused *only* when its **complete premise scope** lies in unchanged seam files. That holds for exactly two claims — **G-16** (framing; premise `jsonl.js`) and **G-19** (OC-3 topology; premise `cli.js`) — plus the `DEFAULT_THINKING_LEVEL = "medium"` sub-conclusion inside G-08 (`defaults.js`; its *consumption chain* is still re-derived). Every other claim touches at least one changed seam file and is re-derived with current-bytes citations. No conclusion is carried over because the old Pi behaved correctly, and the 0.85.1 line numbers in the genesis documents are history, not evidence.

Premise-file markers: **C** = changed seam file, **U** = unchanged seam file, **N** = non-seam file (hash-bound by the profile fingerprint, not by `PI-SC1`).

| Id | Origin | Premise files | Kind | Verdict |
|---|---|---|---|---|
| G-01 | CFG1 design Sec.2.1 step 1 (APS evidence #1) | `model-config.js`(C) | REDERIVE | HOLDS |
| G-02 | CFG1 Sec.2.1 steps 2-3 | `provider-composer.js`(C) | REDERIVE | HOLDS |
| G-03 | CFG1 Sec.2.2 (getCompat) | `openai-completions.js`(C) | REDERIVE | HOLDS |
| G-04 | CFG1 Sec.2.2 (detectCompat table) + CC1 COMPAT_DETECTION_SUBSTRINGS | `openai-completions.js`(C) | REDERIVE | HOLDS-CHANGED |
| G-05 | CFG1 Sec.2.3 | `openai-completions.js`(C) | REDERIVE | HOLDS |
| G-06 | CFG1 Sec.2.4 | `openai-completions.js`(C) | REDERIVE | HOLDS |
| G-07 | CFG1 Sec.2.5 (+FU1) | `rpc-mode.js`(C), `agent-session.js`(C), `jsonl.js`(U), `provider-composer.js`(C), `models.js`(C) | REDERIVE | HOLDS |
| G-08 | CFG1 Sec.3.3 (thinking level) | `sdk.js`(C), `agent.js`(C), `models.js`(C), `openai-completions.js`(C), `defaults.js`(U), `settings-manager.js`(N) | REDERIVE | HOLDS |
| G-09 | CFG1 Sec.3.4 (first-request payload) | `openai-completions.js`(C), `simple-options.js`(C), `sdk.js`(C), `transcript.js`(N), `text.js`(N), `transform-messages.js`(N), `constrained-sampling.js`(N) | REDERIVE | HOLDS-CHANGED |
| G-10 | CFG1 Sec.3.5 (independence) | `openai-completions.js`(C), `agent-loop.js`(C) | REDERIVE | HOLDS |
| G-11 | CFG1 Sec.1.2 (system prompt) | `system-prompt.js`(C), `agent-session.js`(C) | REDERIVE | HOLDS-CHANGED |
| G-12 | CFG1 Sec.1.2 (agent-loop) | `agent-loop.js`(C), `agent.js`(C) | REDERIVE | HOLDS |
| G-13 | CFG1 Sec.1.2 (model-runtime) | `model-runtime.js`(C), `sdk.js`(C) | REDERIVE | HOLDS |
| G-14 | CFG1 Sec.1.2 / FU1 (buildBaseOptions) | `simple-options.js`(C) | REDERIVE | HOLDS |
| G-15 | CFG1 CLI handling (main.js 358-408 in genesis) | `main.js`(C), `model-resolver.js`(C) | REDERIVE | HOLDS |
| G-16 | L16-FU2 Sec.16 + CFG1 Sec.2.5 (framing) | `jsonl.js`(U) | REUSE | HOLDS |
| G-17 | L16-FU2 Sec.16 / R-31 (RPC response shapes) | `rpc-mode.js`(C), `output-guard.js`(N) | REDERIVE | HOLDS |
| G-18 | L16-FU2 F-4 | `rpc-mode.js`(C) | REDERIVE | HOLDS |
| G-19 | OC-3 AMEND1 Sec.1 (APS evidence #3) | `cli.js`(U) | REUSE | HOLDS |
| N-01 | Q1-PRE1-FU1 Sec.1.3-1.6 (prompt acknowledgement ordering) | `rpc-mode.js`(C), `agent-session.js`(C), `agent-loop.js`(C) | NEW | HOLDS-CHANGED |
| N-02 | AR0/Q1 (agent_settled is the completion signal; agent_end is not) | `agent-session.js`(C), `rpc-mode.js`(C) | NEW | HOLDS |
| N-03 | OBS1 (tool_execution_*, message_update usage, extension_error) | `agent-loop.js`(C), `rpc-mode.js`(C), `json-event.js`(N) | NEW | HOLDS |
| N-04 | AR2 handshakes H1 (get_commands extension identity) | `rpc-mode.js`(C), `runner.js`(N), `resource-loader.js`(N), `source-info.js`(N), `loader.js`(N) | NEW | HOLDS |
| N-05 | AR2 handshakes H2 (get_state model identity) | `rpc-mode.js`(C), `provider-composer.js`(C), `model-resolver.js`(C) | NEW | HOLDS |
| N-06 | AR2 build_pi_argv (launch flags) | `args.js`(N), `main.js`(C), `resource-loader.js`(N) | NEW | HOLDS |
| N-07 | CFG1 environment/config policy (PI_* names, settings keys) | `config.js`(N), `settings-manager.js`(N), `telemetry.js`(N), `model-runtime.js`(C) | NEW | HOLDS |
| N-08 | AR2 --tools allowlist is the registry control | `sdk.js`(C), `agent-session.js`(C), `resource-loader.js`(N) | NEW | HOLDS |
| N-09 | AR2 shutdown ladder (stdin-close lever) | `rpc-mode.js`(C) | NEW | HOLDS |
| N-10 | CFG1 Sec.3.2 (Pi-defaulted vs AIDO-configured: retries, no extra requests) | `sdk.js`(C), `openai-completions.js`(C), `provider-retry.js`(N), `cache-warmer.js`(N), `settings-manager.js`(N) | NEW | HOLDS |
| N-11 | CFG1 secret containment (headers/URLs sent) | `provider-attribution.js`(N), `telemetry.js`(N), `openai-completions.js`(C) | NEW | HOLDS |
| N-12 | CFG1 extension acceptance (AIDO-owned extension bytes accepted by Pi) | `loader.js`(N), `tool-definition-wrapper.js`(N) | NEW | HOLDS |

Totals: 31 claims — 2 REUSE, 17 REDERIVE, 12 NEW. Verdicts: **HOLDS** 27, **HOLDS-CHANGED** 4 (the conclusion AIDO relies on holds, but a documented sub-fact differs from genesis — G-04, G-09, G-11, N-01), **no claim is falsified**.

### 4.1 Where the candidate differs from, or adds to, what the genesis documents state

Only differences that are *documented* in the genesis text are called changes; behavior the genesis documents never described is called an addition.

| # | Genesis-documented fact | Candidate | Consumed by AIDO production code? |
|---|---|---|---|
| 1 | `supportsStrictMode` default `true` → each tool carries `strict:false` (CFG1 §2.2, §3.4) | default `false` → tool declarations carry **no** `strict` key | **No** (not in `arms.py`, `preflight.py` or any production module; asserted only by T-3) → **F-1** |
| 2 | system prompt = tools + snippets + guidelines + cwd (CFG1 §1.2) | ordered sections incl. a new `docs` section with **absolute** Pi README/docs/examples paths | No — arm-independent shared constant → **F-4** |
| 3 | the T-3 harness (test code) drives `streamSimple` with `{systemPrompt, messages, tools}` | system prompt and tool declarations are transcript *system messages* (`normalizeContext` / `resolveTranscript` / `getCurrentTools`) | No (production); it invalidates the **harness call shape** → **F-2** |
| 4 | prompt ack is `success:true/false` driven by `preflightResult(didSucceed)` (Q1-PRE1-FU1 §1.5) | ack carries `data:{disposition}`; refusal paths unchanged (throw before ack) | No — AIDO reads only `success` (`run_executor.py:1120-1125`) → **F-11** |
| 5 | AR2 H1 matches a command by its reported `name` | `name` is the command's `invocationName` (differs only on duplicates) | No — a duplicate would make H1 fail **closed** → **F-9** (addition, not a documented change) |
| 6 | cache warming is not part of any genesis derivation | a warmer exists, default mode `streaming`, inert for AIDO's model object (no `promptCache`) | No → **F-6** (addition) |

## 5. New E1 derivations — exact observed behavior with file / hash / line evidence

Every cited file is a member of the committed inventory; its SHA-256 is given in the legend (Appendix C) and was re-verified after inspection. A citation `name:Lnnn` is the line at which the quoted anchor text occurs. Anchors, not hand-typed numbers, produced every `Lnnn`.

### G-01 — CFG1 design Sec.2.1 step 1 (APS evidence #1)

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

models.json is loaded by ModelConfig.load; `compat` is OPTIONAL at provider, model-definition and model-override level; the generated Q/R/E/H documents satisfy the schema.

*Evidence:* `model-config.js:L207` · `model-config.js:L184` · `model-config.js:L214` · `model-config.js:L250` · `model-config.js:L73` · `model-config.js:L74`

*Note:* Union of three compat schemas (OpenAI-completions / responses / Anthropic); the OpenAI-completions member still lists both flags as optional booleans.

### G-02 — CFG1 Sec.2.1 steps 2-3

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

modelFromJson: reasoning ?? false, maxTokens ?? 16384, contextWindow ?? 128000, compat = mergeCompat(provider.compat, model.compat); mergeCompat returns `base` when `override` is falsy, so with no compat at either level model.compat is undefined and with a provider-level block only it IS that block's object.

*Evidence:* `provider-composer.js:L9` · `provider-composer.js:L103` · `provider-composer.js:L109` · `provider-composer.js:L110` · `provider-composer.js:L114` · `provider-composer.js:L111` · `provider-composer.js:L150`

*Note:* New fields (samplingParams, promptCache, thinkingLevelMap, inputLimits) are all `definition.*` pass-throughs and are undefined for AIDO's documents.

### G-03 — CFG1 Sec.2.2 (getCompat)

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

getCompat resolves per field `model.compat.<f> ?? detected.<f>` (returning `detected` unchanged when model.compat is absent); a compat block holding only supportsDeveloperRole and/or supportsReasoningEffort therefore changes exactly those effective fields.

*Evidence:* `openai-completions.js:L1310` · `openai-completions.js:L1312` · `openai-completions.js:L1316` · `openai-completions.js:L1317` · `openai-completions.js:L1342`

### G-04 — CFG1 Sec.2.2 (detectCompat table) + CC1 COMPAT_DETECTION_SUBSTRINGS

*Kind:* **REDERIVE** · *Verdict:* **HOLDS-CHANGED**

For a provider id and base URL matching none of the listed triggers detectCompat still yields supportsDeveloperRole=true, supportsReasoningEffort=true, supportsStore=true, supportsUsageInStreaming=true, maxTokensField=max_completion_tokens, thinkingFormat=openai. The URL-substring trigger set is unchanged (same 15 substrings; api.openai.com still matters only for prompt_cache_key). CHANGED sub-fact: supportsStrictMode now defaults to FALSE (genesis: true).

*Evidence:* `openai-completions.js:L1221` · `openai-completions.js:L1224` · `openai-completions.js:L1242` · `openai-completions.js:L1263` · `openai-completions.js:L1264` · `openai-completions.js:L1265` · `openai-completions.js:L1266` · `openai-completions.js:L1268` · `openai-completions.js:L1292` · `openai-completions.js:L1273` · `openai-completions.js:L576`

*Note:* AIDO preflight.COMPAT_DETECTION_SUBSTRINGS (preflight.py:60-77) remains a superset of every URL trigger in detectCompat, provider-attribution.js, anthropic-messages.js and openai-responses.js (scan in Sec.5.3).

### G-05 — CFG1 Sec.2.3

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

Block presence alone is request-inert; absence of a flag is equivalent to explicit `true` for both flags (never `false`). Follows from G-03/G-04.

*Evidence:* `openai-completions.js:L1312` · `openai-completions.js:L1316`

### G-06 — CFG1 Sec.2.4

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

supportsDeveloperRole is consumed ONLY at the instruction-message role decision (model.reasoning && supportsDeveloperRole ? developer : system); supportsReasoningEffort is consumed, for the default thinkingFormat `openai`, ONLY at `reasoning_effort` emission (options.reasoningEffort && model.reasoning && supportsReasoningEffort). An exhaustive scan of the payload finds no other consumer on the openai-completions path (the extra occurrences at openai-completions.js:624/634/659/675/701 are other thinkingFormat branches; llama/provider.js sets the flags for its own, unloaded, provider).

*Evidence:* `openai-completions.js:L899` · `openai-completions.js:L922` · `openai-completions.js:L714` · `openai-completions.js:L716`

*Note:* Exhaustive consumer scan reproduced in Sec.5.1.

### G-07 — CFG1 Sec.2.5 (+FU1)

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

get_state serializes `session.model` (the COMPOSED model object, unnormalized) and `session.thinkingLevel` with plain JSON.stringify; arm Q therefore has NO `compat` key and arms R/E/H carry exactly the provider block. session.model is agent.state.model; the model object is the one provider.getModels() returned, through ModelsImpl.getModels unchanged.

*Evidence:* `rpc-mode.js:L345` · `rpc-mode.js:L347` · `rpc-mode.js:L348` · `rpc-mode.js:L360` · `agent-session.js:L1018` · `agent-session.js:L1019` · `agent-session.js:L1022` · `jsonl.js:L9` · `provider-composer.js:L395` · `models.js:L73`

*Note:* jsonl.js is byte-identical to genesis (reused for the framing sub-claim G-16).

### G-08 — CFG1 Sec.3.3 (thinking level)

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

With no --thinking flag, no model:level suffix, no defaultThinkingLevel and no per-model thinking level, Pi's own `medium` applies; for a reasoning model with no thinkingLevelMap it is unclamped and reaches the request as reasoning_effort `medium`. (defaults.js is UNCHANGED: its DEFAULT_THINKING_LEVEL conclusion is REUSED; its consumption chain is re-derived.)

*Evidence:* `defaults.js:L1` · `sdk.js:L135` · `sdk.js:L142` · `settings-manager.js:L558` · `models.js:L678` · `models.js:L680` · `models.js:L690` · `agent.js:L307` · `openai-completions.js:L524` · `agent-session.js:L2022`

### G-09 — CFG1 Sec.3.4 (first-request payload)

*Kind:* **REDERIVE** · *Verdict:* **HOLDS-CHANGED**

First request body: model; messages = [instruction message (developer|system) carrying the Pi system prompt, user message]; stream:true; stream_options.include_usage; store:false; max_completion_tokens (Pi-defaulted); tools = the two allowlisted tools; reasoning_effort (arms Q/R). NOT sent: tool_choice, temperature, prompt_cache_key, priority, chat_template_kwargs, max_tokens. CHANGED sub-fact relative to the genesis document: (a) tool declarations carry NO `strict` key (genesis CFG1 Sec.2.2/3.4: strict:false). Further observations the genesis text does not address: (b) the user message content is an array of text parts; (c) the instruction text and tool list reach the request through the transcript model (normalizeContext / resolveTranscript / getCurrentTools).

*Evidence:* `openai-completions.js:L575` · `openai-completions.js:L583` · `openai-completions.js:L586` · `openai-completions.js:L594` · `openai-completions.js:L601` · `openai-completions.js:L1156` · `openai-completions.js:L1158` · `openai-completions.js:L613` · `openai-completions.js:L616` · `openai-completions.js:L641` · `openai-completions.js:L576` · `simple-options.js:L23` · `openai-completions.js:L153` · `openai-completions.js:L920` · `openai-completions.js:L939` · `transcript.js:L102` · `transcript.js:L41` · `text.js:L11` · `transform-messages.js:L54` · `constrained-sampling.js:L174` · `sdk.js:L262` · `sdk.js:L215`

*Note:* The T-3 expectation `strict is False` and the harness's raw-context call shape are stale (Sec.11 and Sec.14 F-1/F-2).

### G-10 — CFG1 Sec.3.5 (independence)

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

The role decision reads only supportsDeveloperRole; the effort decision only supportsReasoningEffort; they couple only through model.reasoning. Neither flag changes tool presence/content/order, tool_choice, promptGuidelines placement, system-prompt placement, message ordering or request path: tool declarations come from transcript tool state (declareToolChanges/getCurrentTools), not from compat flags.

*Evidence:* `openai-completions.js:L899` · `openai-completions.js:L567` · `agent-loop.js:L219` · `transcript.js:L198`

### G-11 — CFG1 Sec.1.2 (system prompt)

*Kind:* **REDERIVE** · *Verdict:* **HOLDS-CHANGED**

The system prompt is built from the selected tools' snippets and guidelines, the cwd and fixed text. CHANGED: it is now an ordered set of named sections (preamble, tools, rules, docs, [addendum], [project_context], [skills], cwd, [custom]) and the `docs` section embeds ABSOLUTE paths of Pi's README/docs/examples. Under AIDO's argv (--no-context-files, --no-skills, no SYSTEM.md in the pinned config dir) addendum/project_context/skills are empty.

*Evidence:* `system-prompt.js:L67` · `system-prompt.js:L80` · `system-prompt.js:L84` · `system-prompt.js:L85` · `system-prompt.js:L86` · `system-prompt.js:L105` · `agent-session.js:L1267` · `config.js:L361` · `resource-loader.js:L941` · `resource-loader.js:L939`

*Note:* Arm-independent: the same code builds it for every arm, so it is a frozen shared constant for CFG1's contrast; it is a model-visible-content change (Sec.14 F-4).

### G-12 — CFG1 Sec.1.2 (agent-loop)

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

An unregistered tool name gets tool_execution_start, an immediate error result `Tool <name> not found` with isError, and tool_execution_end; it never reaches an extension. Additional path present in the candidate (not described by the genesis derivation): a `length`-truncated assistant message fails EVERY tool call the same way (events + isError) without executing any.

*Evidence:* `agent-loop.js:L482` · `agent-loop.js:L486` · `agent-loop.js:L379` · `agent-loop.js:L642` · `agent-loop.js:L163` · `agent-loop.js:L342` · `agent.js:L300`

### G-13 — CFG1 Sec.1.2 (model-runtime)

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

The request path is sdk streamFn -> ModelRuntime.streamSimple -> prepareRequest (auth resolution, header transform) -> composed provider.streamSimple -> openai-completions.streamSimple.

*Evidence:* `sdk.js:L260` · `model-runtime.js:L447` · `model-runtime.js:L489` · `model-runtime.js:L513` · `provider-composer.js:L382` · `compat.js:L111` · `openai-completions.lazy.js:L2`

### G-14 — CFG1 Sec.1.2 / FU1 (buildBaseOptions)

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

max output tokens: AIDO requests none; Pi's own value is clampMaxTokensToContext(model.maxTokens ?? 16384 default, ...) and is sent as max_completion_tokens.

*Evidence:* `simple-options.js:L23` · `simple-options.js:L5` · `openai-completions.js:L594`

### G-15 — CFG1 CLI handling (main.js 358-408 in genesis)

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

`--provider P --model M` resolves the model from the composed catalog filtered to provider P by exact (case-insensitive) provider id; no --thinking and no `:level` suffix leaves options.thinkingLevel undefined (so G-08 applies).

*Evidence:* `main.js:L353` · `main.js:L367` · `main.js:L411` · `model-resolver.js:L292` · `model-resolver.js:L382` · `model-resolver.js:L70`

### G-16 — L16-FU2 Sec.16 + CFG1 Sec.2.5 (framing)

*Kind:* **REUSE** · *Verdict:* **HOLDS**

RPC framing is strict LF-only JSONL via plain JSON.stringify with no replacer/toJSON. Premise scope = jsonl.js alone, which is byte-identical to genesis (sha256 049a9f8c...). REUSED by premise; current-bytes citation shown for the reader.

*Evidence:* `jsonl.js:L9` · `jsonl.js:L18`

### G-17 — L16-FU2 Sec.16 / R-31 (RPC response shapes)

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

success(id, command, data) = {id, type:"response", command, success:true[, data]} (data omitted when undefined); error(id, command, message) = {id, type:"response", command, success:false, error}; handleCommand binds `const id = command.id`; get_state returns success(id,"get_state",state); a thrown command error emits error(command.id, command.type, ...); a parse failure emits error(undefined, "parse", ...). Responses/events reach stdout as serializeJsonLine(obj) through output-guard.writeRawStdout, an ordered write queue that does not alter the bytes.

*Evidence:* `rpc-mode.js:L31` · `rpc-mode.js:L35` · `rpc-mode.js:L37` · `rpc-mode.js:L38` · `rpc-mode.js:L293` · `rpc-mode.js:L635` · `rpc-mode.js:L608` · `rpc-mode.js:L29` · `output-guard.js:L71` · `output-guard.js:L45`

*Note:* takeOverStdout redirects stray console writes to stderr, so stdout carries only protocol records.

### G-18 — L16-FU2 F-4

*Kind:* **REDERIVE** · *Verdict:* **HOLDS**

get_state data also carries sessionFile, sessionId, sessionName and (inside model) baseUrl; other fields present: isStreaming, isCompacting, steeringMode, followUpMode, autoCompactionEnabled, messageCount, pendingMessageCount.

*Evidence:* `rpc-mode.js:L353` · `rpc-mode.js:L354` · `rpc-mode.js:L350`

### G-19 — OC-3 AMEND1 Sec.1 (APS evidence #3)

*Kind:* **REUSE** · *Verdict:* **HOLDS**

dist/cli.js statically imports ./cli/setup.js, which is OUTSIDE the seam, so unpinned Pi JavaScript evaluates before the cli.js body. Premise scope = cli.js alone (UNCHANGED, sha256 8189b66a...). REUSED. Current observation: setup.js still outside the seam; it sets PI_CODING_AGENT/AI_AGENT, silences emitWarning and calls configureHttpDispatcher().

*Evidence:* `cli.js:L2` · `cli.js:L4` · `setup.js:L10`

### N-01 — Q1-PRE1-FU1 Sec.1.3-1.6 (prompt acknowledgement ordering)

*Kind:* **NEW** · *Verdict:* **HOLDS-CHANGED**

`prompt` is acknowledged by ONE correlated response emitted BEFORE any agent_start/provider request: refusal paths (no model, no auth, compaction in progress) THROW before the ack and yield success:false; the real path calls preflightResult("started") immediately before `await this._runAgentPrompt`. CHANGED: the ack now carries data:{disposition} ("handled"|"queued"|"started") and preflightResult no longer carries a boolean; AIDO reads only `success` (run_executor.py:1120-1125), so the ack remains a two-valued dispatch acknowledgement.

*Evidence:* `rpc-mode.js:L298` · `rpc-mode.js:L309` · `rpc-mode.js:L313` · `agent-session.js:L1481` · `agent-session.js:L1533` · `agent-session.js:L1544` · `agent-session.js:L1594` · `agent-session.js:L1595` · `agent-loop.js:L50`

### N-02 — AR0/Q1 (agent_settled is the completion signal; agent_end is not)

*Kind:* **NEW** · *Verdict:* **HOLDS**

agent_settled is emitted once per _runAgentPrompt, in its `finally`, after all agent_end events; agent_end carries willRetry computed from the retry settings; the RPC layer forwards every session event to stdout.

*Evidence:* `agent-session.js:L1344` · `agent-session.js:L1376` · `agent-session.js:L671` · `agent-session.js:L677` · `agent-session.js:L736` · `rpc-mode.js:L266` · `json-event.js:L16`

### N-03 — OBS1 (tool_execution_*, message_update usage, extension_error)

*Kind:* **NEW** · *Verdict:* **HOLDS**

tool_execution_start {toolCallId, toolName, args} and tool_execution_end {toolCallId, toolName, result, isError} are emitted for every model-issued call (including not-found and truncated); message_update is reduced to {type, usage, assistantMessageEvent}; extension_error is {extensionPath, event, error}.

*Evidence:* `agent-loop.js:L347` · `agent-loop.js:L646` · `json-event.js:L25` · `rpc-mode.js:L260`

### N-04 — AR2 handshakes H1 (get_commands extension identity)

*Kind:* **NEW** · *Verdict:* **HOLDS**

get_commands lists extension commands as {name: command.invocationName, source:"extension", sourceInfo}; for a CLI-loaded (`--extension <path>`) file the sourceInfo is {path, source:"cli", scope:"temporary", origin:"top-level", baseDir}, matching AIDO's EXPECTED_EXTENSION_SOURCE_KIND="cli". Note: `name` is the command's invocationName, which differs from the registered name only when two commands share it (then `name:<n>`); in that case H1's exact-name match fails CLOSED.

*Evidence:* `rpc-mode.js:L540` · `rpc-mode.js:L544` · `rpc-mode.js:L546` · `rpc-mode.js:L547` · `runner.js:L570` · `resource-loader.js:L391` · `resource-loader.js:L701` · `source-info.js:L17` · `loader.js:L242`

### N-05 — AR2 handshakes H2 (get_state model identity)

*Kind:* **NEW** · *Verdict:* **HOLDS**

H2 reads model.provider (= the models.json provider id), model.id, model.api (= "openai-completions") and model.maxTokens (16384 default) from the get_state model object; those are exactly modelFromJson's provider/id/api/maxTokens and reach get_state unchanged (G-02, G-07).

*Evidence:* `provider-composer.js:L101` · `provider-composer.js:L98` · `provider-composer.js:L100` · `provider-composer.js:L110` · `rpc-mode.js:L347`

### N-06 — AR2 build_pi_argv (launch flags)

*Kind:* **NEW** · *Verdict:* **HOLDS**

Every flag AIDO passes is recognised with the semantics AIDO relies on: --mode rpc, --no-session (in-memory SessionManager), --no-extensions + --extension <path> (built-in extensions excluded, explicit path kept), --tools <allowlist>, --no-builtin-tools, --no-skills, --no-prompt-templates, --no-themes, --no-context-files, --no-approve (projectTrustOverride=false), --offline (also sets PI_OFFLINE=1, PI_SKIP_VERSION_CHECK=1), --provider, --model.

*Evidence:* `args.js:L40` · `args.js:L86` · `args.js:L148` · `args.js:L152` · `args.js:L113` · `args.js:L110` · `args.js:L177` · `args.js:L180` · `args.js:L183` · `args.js:L186` · `args.js:L221` · `args.js:L224` · `main.js:L452` · `main.js:L455` · `main.js:L287` · `main.js:L595` · `main.js:L598` · `resource-loader.js:L461` · `resource-loader.js:L419`

### N-07 — CFG1 environment/config policy (PI_* names, settings keys)

*Kind:* **NEW** · *Verdict:* **HOLDS**

The pinned config dir is selected by PI_CODING_AGENT_DIR (name derived from APP_NAME "pi", because piConfig carries no name); PI_OFFLINE disables model-catalog network refresh; PI_TELEMETRY=0 disables install telemetry/attribution headers; every key in AIDO's settings.json is still read by SettingsManager; the retry block (enabled/maxRetries/baseDelayMs, provider.maxRetries) is still consumed.

*Evidence:* `config.js:L476` · `config.js:L491` · `model-runtime.js:L92` · `telemetry.js:L6` · `settings-manager.js:L659` · `settings-manager.js:L691` · `settings-manager.js:L743` · `settings-manager.js:L1021`

### N-08 — AR2 --tools allowlist is the registry control

*Kind:* **NEW** · *Verdict:* **HOLDS**

With --tools aido_read,aido_edit the registry keeps only allowlisted built-ins (none exist by those names) and the allowlisted extension tools; naming a tool activates it; therefore the declared tool set is exactly {aido_read, aido_edit}. tool_search/codemode/MCP tools cannot be declared (their extensions are not loaded, and they are not allowlisted).

*Evidence:* `sdk.js:L145` · `agent-session.js:L1099` · `agent-session.js:L2833` · `resource-loader.js:L403` · `resource-loader.js:L246` · `package-manager.js:L742`

### N-09 — AR2 shutdown ladder (stdin-close lever)

*Kind:* **NEW** · *Verdict:* **HOLDS**

Closing stdin triggers shutdown(): runtimeHost.dispose(), then process.exit — the in-protocol termination lever the supervisor ladder tries first.

*Evidence:* `rpc-mode.js:L642` · `rpc-mode.js:L639` · `rpc-mode.js:L589`

### N-10 — CFG1 Sec.3.2 (Pi-defaulted vs AIDO-configured: retries, no extra requests)

*Kind:* **NEW** · *Verdict:* **HOLDS**

One model call = one HTTP request: the SDK is invoked with maxRetries:0 and retries are owned by retryProviderRequest with maxRetries = settings retry.provider.maxRetries (AIDO: 0). The cache warmer's DEFAULT mode is `streaming`, but it issues no extra request because the AIDO model object has no promptCache (cache lifetime unavailable). Compaction/auto-retry are session-level and unchanged in kind.

*Evidence:* `openai-completions.js:L195` · `openai-completions.js:L197` · `provider-retry.js:L77` · `sdk.js:L190` · `settings-manager.js:L681` · `cache-warmer.js:L31` · `cache-warmer.js:L126` · `cache-warmer.js:L127` · `provider-composer.js:L108`

### N-11 — CFG1 secret containment (headers/URLs sent)

*Kind:* **NEW** · *Verdict:* **HOLDS**

Default attribution headers (OpenRouter/NVIDIA/Cloudflare/opencode) are gated by isInstallTelemetryEnabled (PI_TELEMETRY=0 => off) and by host match; AIDO's provider id/base URL match none. The only extra header is `User-Agent: pi (<os> <release>; <arch>)`. The apiKey `$NAME` form is resolved from the environment (not a shell command: only a leading `!` executes).

*Evidence:* `provider-attribution.js:L27` · `provider-attribution.js:L28` · `openai-completions.js:L533` · `resolve-config-value.js:L66` · `resolve-config-value.js:L54`

### N-12 — CFG1 extension acceptance (AIDO-owned extension bytes accepted by Pi)

*Kind:* **NEW** · *Verdict:* **HOLDS**

Pi accepts AIDO's generated TypeScript extension: it is loaded by jiti with an alias map that provides `typebox`, requires a default-exported factory function, requires registerTool definitions to carry an object `parameters` schema and registerCommand to carry a handler, and wraps execute(toolCallId, params, signal, onUpdate, ctx).

*Evidence:* `loader.js:L42` · `loader.js:L481` · `loader.js:L483` · `loader.js:L231` · `loader.js:L234` · `loader.js:L248` · `tool-definition-wrapper.js:L12`

### 5.1 Exhaustive consumer scan for the two compat flags (supports G-06)

A scan of every `.js/.mjs/.cjs` in the payload (excluding `dist/bundle`, which AIDO does not launch, and the `openai`/`@anthropic-ai` SDK trees) for the identifiers `supportsDeveloperRole` and `supportsReasoningEffort` yields: `model-config.js` schema declarations; `llama/provider.js:91-92` (the unloaded llama.cpp built-in's own provider); `openai-responses*.js` (a different API); and in `openai-completions.js` — role decision (`:899`), `detectCompat`/`getCompat` (`:1264-1265`, `:1316-1317`), and the reasoning-effort sites `:624 :634 :659 :675 :701` (non-`openai` `thinkingFormat` branches, unreachable for AIDO's default `thinkingFormat: "openai"`) and `:714 :718` (the `openai` branch). **No other consumer exists**, which re-establishes CFG1 §2.4.

### 5.2 First-request payload under the current candidate (source-derived, **not observed**)

| Field | Genesis (0.85.1, CFG1 §3.4) | Candidate (1.0.3, this derivation) |
|---|---|---|
| path | `POST <baseUrl>/chat/completions` | same (`openai` SDK `buildURL`, `baseURL + path`; SDK retries forced to 0 at `openai-completions.js` request options) |
| `model` | candidate id | same |
| `messages[0]` | `{role: developer\|system, content: <Pi system prompt>}` | same role rule; `content` = `getSystemMessageText(system message)` = preamble, tools, rules, **docs (new)**, cwd sections |
| `messages[1]` | `{role: user, content: <task prompt>}` | `{role: user, content: [{type:"text", text: <task prompt>}]}` (array form; AIDO prompt is not a `/command`, so no template/skill expansion) |
| `stream`, `stream_options.include_usage`, `store:false` | present | present (`supportsUsageInStreaming`, `supportsStore` true for non-matching URL) |
| max output tokens | `max_completion_tokens = min(16384, 128000 − estimate − 4096)` (Pi-defaulted) | same rule (`clampMaxTokensToContext`), field `max_completion_tokens` |
| `tools` | `[aido_read{strict:false}, aido_edit{strict:false}]` | `[aido_read, aido_edit]` as `{type:function, function:{name, description, parameters}}` — **no `strict` key** (**CHANGED**) |
| `reasoning_effort` | `"medium"` (arms Q, R); absent (E, H) | same |
| not sent | `tool_choice`, `temperature`, `prompt_cache_key`, `priority`, `chat_template_kwargs`, `max_tokens` | same (plus: no `prompt_cache_retention`, no sampling params, no thinking-budget field) |
| `onPayload` | no-op | no-op: `before_provider_request` runner hook has no handler (no extension registers one) |

### 5.3 URL-trigger completeness scan (supports G-04 and the CC1 `COMPAT_DETECTION_SUBSTRINGS` precondition)

CFG1 refuses a run whose base URL contains any substring in `preflight.COMPAT_DETECTION_SUBSTRINGS` (16 entries, lower-cased match). The precondition that makes the effective-compat derivation valid is that **no URL-keyed behavior in the launched code path can fire for a URL that passes that check.** A scan of all first-party reachable JavaScript (excluding `dist/bundle`) for `baseUrl`/host comparisons finds: (a) `openai-completions.js` `detectCompat` — 15 substrings (`api.z.ai`, `open.bigmodel.cn`, `api.together.ai`, `api.together.xyz`, `api.moonshot.`, `openrouter.ai`, `api.cloudflare.com`, `gateway.ai.cloudflare.com`, `integrate.api.nvidia.com`, `api.ant-ling.com`, `cerebras.ai`, `deepseek.com`, `api.x.ai`, `chutes.ai`, `opencode.ai`) plus `api.openai.com` for `prompt_cache_key`; (b) `provider-attribution.js` — exact-hostname matches for `openrouter.ai`, `integrate.api.nvidia.com`, `api.cloudflare.com`, `gateway.ai.cloudflare.com`, `opencode.ai`; (c) `anthropic-messages.js` / `openai-responses.js` — `openrouter.ai` (other APIs); (d) `azure-openai-config.js` and `bedrock-converse-stream.js` — Azure / AWS hostnames (their own APIs only). **Every URL trigger that can affect an `openai-completions` request is a member of AIDO's list; the added provider-*id* triggers (`zai`, `deepseek`, `openrouter`, …) cannot match AIDO's fixed provider id `b300_pi_qualification`.** The CC1 precondition therefore stands unchanged.

### 5.4 Where the source cannot answer (kept honest)

- *Wire bytes* — header set beyond `User-Agent`, `Authorization` and SDK `X-Stainless-*` telemetry headers, exact JSON whitespace, TLS/HTTP framing — are the OpenAI SDK's and undici's (Sec.7.4); they are not AIDO premises and are not claimed.
- *The model's behavior* given the request, the proxy's forwarding, and chat-template rendering are outside the payload and are not derived here (as in genesis).
- Several of the derivations above are **conditional on AIDO-owned inputs** (no `compat.thinkingFormat`, no `promptCache`, no `thinkingLevelMap`, `apiKey` of the `$NAME` form, argv and env as built by `build_pi_argv` / `environment.py`). They are the same inputs CFG1 already freezes; a change to any of them would re-open the corresponding row.

## 6. E2 — manifest and exposure review

All manifests were decoded **as data only** (strict UTF-8, JSON) from the committed bundle; no manifest value was evaluated, and no `scripts` entry was run. The 149 manifests in the bundle are bound to inventory entries by size and SHA-256 (Sec.2.2); the three seam manifests were additionally re-read from the installed tree and re-hashed.

### 6.1 First-party package identity (nested package identity)

| Package dir | `name` | `version` (provenance) | `type` | `main` | `bin` | `engines` | deps | files |
|---|---|---|---|---|---|---|---:|---:|
| `(root)` | `@earendil-works/pi-coding-agent` | 1.0.3 | module | ./dist/index.js | {"pi": "dist/bundle/cli.js"} | {"node": ">=22.19.0"} | 23 | 1252 |
| `examples/plugins/pi-example-plugin` | `@earendil-works/pi-example-plugin` | 1.0.0 | module | — | — | — | 0 | 5 |
| `node_modules/@earendil-works/chord` | `@earendil-works/chord` | 1.0.3 | module | ./dist/index.js | — | {"node": ">=22.19.0"} | 1 | 119 |
| `node_modules/@earendil-works/pi-agent-core` | `@earendil-works/pi-agent-core` | 1.0.3 | module | ./dist/index.js | — | {"node": ">=22.19.0"} | 2 | 26 |
| `node_modules/@earendil-works/pi-ai` | `@earendil-works/pi-ai` | 1.0.3 | module | ./dist/index.js | {"pi-ai": "dist/cli.js"} | {"node": ">=22.19.0"} | 10 | 817 |
| `node_modules/@earendil-works/pi-codemode` | `@earendil-works/pi-codemode` | 1.0.3 | module | ./dist/index.js | — | {"node": ">=22.19.0"} | 1 | 42 |
| `node_modules/@earendil-works/pi-mcp` | `@earendil-works/pi-mcp` | 1.0.3 | module | ./dist/index.js | — | {"node": ">=22.19.0"} | 1 | 76 |
| `node_modules/@earendil-works/pi-telemetry` | `@earendil-works/pi-telemetry` | 1.0.3 | module | ./dist/index.js | — | {"node": ">=22.19.0"} | 0 | 26 |
| `node_modules/@earendil-works/pi-tui` | `@earendil-works/pi-tui` | 1.0.3 | module | dist/index.js | — | {"node": ">=22.19.0"} | 2 | 200 |

Every nested `@earendil-works/*` manifest `name` equals the name implied by its install path; all declare `1.0.3` and `type: module`. The example plugin (`examples/plugins/pi-example-plugin`) is a *separate*, `private` package whose peer dependencies name `^0.84.4` — it is example content, not a runtime dependency (Sec.7.2).

### 6.2 Facts that CFG1-CC1 assumes, and whether they changed

| CFG1-CC1 assumption | Candidate manifest / package fact | Alters CFG1-CC1? |
|---|---|---|
| package identity and install layout `node_modules/@earendil-works/pi-coding-agent` with `dist/cli.js` as the launch anchor | root `name` as required; `dist/cli.js` is a regular file in the inventory and is **byte-identical** to genesis | No |
| AIDO launches Node-direct on `dist/cli.js` (unbundled) | root `bin.pi` points at **`dist/bundle/cli.js`** (the *bundled* build); the unbundled `dist/cli.js` ships too and is what AIDO launches | No for CC1 — but a **scope fact**: nothing in this review speaks to `dist/bundle/**` (F-7) |
| ESM entry, Node-direct launch | `"type": "module"`; `main ./dist/index.js`; `exports` has `.` (types/import), `./rpc-entry`, `./client`, `./experimental/plugin` (the last two `source`-conditioned, not shipped as dist) | No |
| env-var names derive from the app name | `piConfig` carries only `configDir: ".pi"` — **no `name`** — so `APP_NAME = "pi"` and the names stay `PI_CODING_AGENT_DIR`, `PI_OFFLINE`, `PI_TELEMETRY`, `PI_SKIP_VERSION_CHECK` (N-07) | No |
| Node runtime | `engines.node >= 22.19.0` (declared). `node.exe` is **not** part of any profile; its version was not (and could not statically be) established here | No — HPP-1 external-runtime residual; PE-4B prerequisite (F-12) |
| declared versions are provenance | `1.0.3` throughout; **not used** for any conclusion | No |
| dependency sets | root declares 23 runtime dependencies (first-party: `chord`, `pi-agent-core`, `pi-ai`, `pi-codemode`, `pi-mcp`, `pi-tui`; third-party incl. `jiti`, `undici`, `typebox`, `quickjs-wasi`); `pi-ai` declares 10 incl. `@earendil-works/pi-telemetry`; `pi-agent-core` declares 2 (no genesis manifests exist to diff against — declared sets are recorded, not compared) | No for CC1 (E3 covers the added code); `pi-telemetry` is declared but **imported by nothing** in the payload (Sec.7.5) |

### 6.3 Derived external-resolution exposure set and the PE-3 absence observation

The 31 names in the candidate's `resolution_exposures` were **re-derived** from the committed manifests by the accepted PE-2a function and equal the committed list. For each, the declaring package(s) and dependency map:

| Exposure name | Declared by (map) |
|---|---|
| `@esbuild/aix-ppc64` | esbuild (optionalDependencies) |
| `@esbuild/android-arm` | esbuild (optionalDependencies) |
| `@esbuild/android-arm64` | esbuild (optionalDependencies) |
| `@esbuild/android-x64` | esbuild (optionalDependencies) |
| `@esbuild/darwin-arm64` | esbuild (optionalDependencies) |
| `@esbuild/darwin-x64` | esbuild (optionalDependencies) |
| `@esbuild/freebsd-arm64` | esbuild (optionalDependencies) |
| `@esbuild/freebsd-x64` | esbuild (optionalDependencies) |
| `@esbuild/linux-arm` | esbuild (optionalDependencies) |
| `@esbuild/linux-arm64` | esbuild (optionalDependencies) |
| `@esbuild/linux-ia32` | esbuild (optionalDependencies) |
| `@esbuild/linux-loong64` | esbuild (optionalDependencies) |
| `@esbuild/linux-mips64el` | esbuild (optionalDependencies) |
| `@esbuild/linux-ppc64` | esbuild (optionalDependencies) |
| `@esbuild/linux-riscv64` | esbuild (optionalDependencies) |
| `@esbuild/linux-s390x` | esbuild (optionalDependencies) |
| `@esbuild/linux-x64` | esbuild (optionalDependencies) |
| `@esbuild/netbsd-arm64` | esbuild (optionalDependencies) |
| `@esbuild/netbsd-x64` | esbuild (optionalDependencies) |
| `@esbuild/openbsd-arm64` | esbuild (optionalDependencies) |
| `@esbuild/openbsd-x64` | esbuild (optionalDependencies) |
| `@esbuild/openharmony-arm64` | esbuild (optionalDependencies) |
| `@esbuild/sunos-x64` | esbuild (optionalDependencies) |
| `@esbuild/win32-arm64` | esbuild (optionalDependencies) |
| `@esbuild/win32-ia32` | esbuild (optionalDependencies) |
| `@modelcontextprotocol/sdk` | @google/genai (peerDependencies) |
| `@smithy/hash-node` | openai (peerDependencies) |
| `bufferutil` | ws (peerDependencies) |
| `kerberos` | proxy-agent-negotiate (peerDependencies) |
| `utf-8-validate` | ws (peerDependencies) |
| `zod` | @anthropic-ai/sdk (peerDependencies); openai (peerDependencies) |

**Interpretation, kept narrow.** `EXPOSURES_PROVEN_ABSENT` is *evidence* that, at PE-3 discovery time, none of these 31 names was resolvable by the accepted upward-absence check from the payload root. It is a statement about *declared* resolution names, not about Node resolution in general. A literal-specifier scan of all code reachable from `dist/cli.js` (2 106 files) finds that the only specifiers that resolve **outside** the payload are three *optional* `require()` calls — `bufferutil`, `utf-8-validate` (both in the exposure list) and `supports-color` (from `debug`, which declares it only in `peerDependenciesMeta`, so it is **not** in the exposure list; `debug` is reachable only lazily, through the proxy-agent and Google-auth packages that only the Bedrock / Codex / Google APIs load — never for `openai-completions`). That last case is exactly the HPP-1 residual *undeclared upward resolution* and is stated as such in Sec.12 (F-13).

### 6.4 B7 residual wording (preserved verbatim)

```text
pi_profile_authority_scope        PI_PACKAGE_PAYLOAD_AND_DECLARED_RESOLUTION_BOUNDARY
pi_external_runtime_residual      NOT_IDENTIFIED_BY_PROFILE
```

Neither this document nor any conclusion in it claims complete runtime identity.

## 7. E3 — whole non-seam payload accounting

**Why the whole payload.** Genesis recorded no payload inventory, so there is no historical full payload against which to diff. For this first HPP profile the committed inventory *is* the reference baseline, and every regular non-seam file must be accounted for. No byte diff is pretended: where this section says "reviewed" it means reviewed *as a baseline*, with the depth stated per class.

### 7.1 Totals and coverage proof

| Quantity | Count |
|---|---:|
| inventory entries | 16482 |
| directories | 1436 |
| regular files | 15046 |
| PI-SC1 files (all regular files; 17 `.js`/3 `package.json`) | 20 |
| **non-seam regular files** | **15026** |
| JavaScript files (`.js/.mjs/.cjs`) | 4858 (statically reachable from `dist/cli.js`: 1421 eager + 685 lazy-only = 2106) |

**Machine-checkable coverage check (executed during analysis):**

```text
set(all regular inventory files)  ==  set(PI-SC1 files) UNION set(accounted non-seam files)     -> True
set(PI-SC1 files) INTERSECT set(accounted non-seam files)  == empty                              -> True
groups pairwise disjoint (sum of group sizes == size of union)                                   -> True   (15026 == 15026)
unexplained 'other' bucket                                                                       -> none (rule D8 matched 0 files)
```

### 7.2 The groups: selection rule, depth, and the premise-influence determination

Rules are evaluated **in the order shown; the first match wins**, so the partition is total by construction and was asserted total and disjoint. "First-party" = the root `pi-coding-agent` package and the `@earendil-works/*` packages (including the example plugin); "eager" = statically reachable from `dist/cli.js` through `import`/`export … from`/`require` with a literal specifier; "lazy" = reachable only through `import("literal")`; "unreached" = neither.

| Group | Selection rule | Files | Bytes | Review depth / inspection mode | Premise-influence determination |
|---|---|---:|---:|---|---|
| **M1** | `package.json` files other than the 3 seam manifests | 146 | 273048 | Individual (data): each decoded, tabulated (name, version, type, main/module/exports/bin, scripts) — Appendix A | Manifests are data to Node's resolver and to Pi's `config.js` (root only). Their *effect* on which file an `import` binds to was modelled in the resolver; every literal edge from reachable code resolves inside the payload except the 3 optional `require`s in Sec.6.3. No install script is ever run by Pi or AIDO. |
| **N1** | `.node .so .dll .dylib .wasm .exe` | 15 | 15311954 | Individual: each of the 15 listed and hashed (Sec.8.3) | Not loadable by AIDO's flow: the 6 pi-tui `.node` addons load only through the clipboard/terminal-image helpers (interactive); `photon_rs_bg.wasm` only through image resize; `quickjs.wasm`/`*.so` only through the codemode runtime (extension not loaded); `esbuild.exe` and `doom.wasm` are never referenced by reachable code. |
| **D1** | `*.d.ts *.d.mts *.d.cts` | 4796 | 20388479 | Structural: counted; not loadable as code by Node | Type declarations are never evaluated by Node; the AIDO extension is loaded by `jiti` as TypeScript but its only Pi import is `import type`, erased at transform. No runtime effect. |
| **D2** | `*.map` source maps | 3777 | 30781006 | Structural: counted | Never loaded unless `--enable-source-maps` (AIDO's argv has none). No runtime effect. |
| **FP-I** | first-party JS **inspected individually** (explicit list, Sec.8.1) | 54 | 564842 | Individual: whole file or the premise-relevant regions, as marked per file in Sec.8.1 | These are the files that entered derivation bases or whose behavior is a startup effect; findings in Sec.8–9. |
| **FP-E** | first-party JS, eager-reachable, not individually read | 359 | 2380463 | Mechanical: capability scan (spawn/net/fs-write/env/dynamic import/eval/wasm/worker), top-level-statement scan, and an invocation-gate analysis for **every** file carrying a premise-relevant capability (Sec.7.3) | Module *evaluation* of these files runs at import; the top-level-statement scan found only schema builders, registries, constants and platform checks — **no spawn, no network and no file write at module load**; the only module-load file *read* is `config.js` reading the package's own `package.json`, and the only module-load imports of Node built-ins by fixed name are in `env-api-keys.js` (`fs`/`os`/`path`). Behavior is reached only through the gates in Sec.7.3, none of which AIDO's argv opens. |
| **FP-L** | first-party JS reachable only via `import("literal")` | 50 | 544783 | Mechanical + gate analysis (Sec.7.3) | Loaded only on demand: other model APIs (not selected for `openai-completions`), MCP/codemode runtimes and OAuth (extensions not loaded; no login), plus `jiti-loader.js` / `jiti-static-loader.js` (the `jiti` factory loaded for AIDO's own extension; thin wrappers, gate in Sec.7.3). |
| **FP-U** | first-party JS with no literal static/dynamic edge from `dist/cli.js` | 152 | 9849903 | Reachability + non-literal-loader analysis (Sec.7.5); entry-point inventory | `dist/bundle/**` (the packaged `bin` build — 75 JS files), `dist/bun/**` (4), `rpc-entry.js`, `chord`, `pi-telemetry`, OAuth flow modules, `pi-ai` Bedrock/Cloudflare modules, etc. Reachable only via the 5 non-literal loaders, each a fixed-specifier switch gated by a flow AIDO does not run. |
| **TP-I** | third-party JS individually read | 1 | 73588 | Individual, targeted region | `node_modules/openai/client.mjs` — the HTTP request transport: base-URL join, header build, retry gate, timeout (Sec.8.2). |
| **TP-E** | third-party JS, eager-reachable | 998 | 3309381 | Package-level: identity (bytes hash-bound), role, importers, capability scan (Appendix A) | Generic libraries (schema, YAML, semver, undici, highlight.js, diff, …). Their *behavior* is not an AIDO premise; their *presence at pinned bytes* is what the profile fingerprint pins. |
| **TP-L** | third-party JS, lazy-only | 627 | 6950937 | Package-level + the lazy trigger that loads it | `openai` (loaded when `openai-completions.js` loads — it IS on the request path), Anthropic/Google/AWS SDKs (selected only by other `model.api` values), `ws`, `node-fetch`, … |
| **TP-U** | third-party JS with no literal edge from `dist/cli.js` | 2600 | 17152729 | Package-level: unreferenced files of reachable packages + wholly unreferenced packages (Appendix A) | Not reachable under AIDO's flow; accounted for by package, version and count. |
| **D3** | TypeScript sources `*.ts *.mts *.cts *.tsx` (non-`.d.ts`) | 706 | 6774990 | Structural: counted by package | Present for source-map/IDE use and in `examples/`; Node does not load `.ts`; only `jiti`, for the one path Pi is told to load (`--extension`), transpiles TypeScript. |
| **D4** | docs/text: `.md .txt` and `LICENSE/README/CHANGELOG…` | 391 | 3788062 | Structural: counted | Inert text. The system prompt's new `docs` section *names* three of these paths (F-4); their contents are not read by any AIDO-allowlisted tool. |
| **D5R** | JSON statically imported by reachable code (`with {type:"json"}`) | 43 | 918494 | Individual by rule: all 43 are the built-in provider/model catalog (`pi-ai/dist/providers/data/*.json` + `.manifest.json`), loaded at module evaluation | Feed the *built-in* model pool seen by `resolveCliModel`. None defines the provider id `b300_pi_qualification` (mechanically checked); AIDO selects its own provider by exact id (G-15). |
| **D5** | other data/config: non-reachable `.json`, `.proto`, dotfiles, `Makefile`, lockfiles, `.c/.h/.m` native sources | 69 | 318698 | Structural: counted; rule-listed | Not referenced by a literal edge from reachable code; examples' `package-lock.json`, protobuf descriptors, native source files, editor/CI dotfiles. Theme JSONs under `dist/modes/interactive/theme/` are read by `initTheme` (colors only) and are in this group. |
| **D6** | images and web assets (`.png .jpg .gif .svg .css .scss .html`) | 212 | 3408560 | Structural: counted | Interactive/export assets; no AIDO premise. |
| **D7** | scripts and shims (`.sh .cmd .ps1 .bat`; extensionless files under `bin/` or `.bin/`) | 30 | 30472 | Individual list (Sec.8.3): 30 files | npm bin shims (8 binaries) and build scripts. Not on AIDO's narrowed `PATH` (Node dir, Git, system dir) and never spawned by reachable code. |

Group totals: **15026** files, 122820389 bytes — equal to the non-seam file count above.

Group path-list digests (SHA-256 of the newline-joined, sorted inventory paths of the group), for comparison by an independent re-implementation of the Appendix B rules:

```text
M1      146  8ca9c9a1adcdf3f9bd00c9a0243f886f616e33cef83b6502a753a23cee033c46
N1       15  3f2d0b077173cb66b7e7629a01da7abc9f9b6ca605a848cabac7c6b7f25d5075
D1     4796  a1e9d5fb59b235468728eb39351f8176519f0623d238a79ebe7a754ae7961617
D2     3777  39c058a55c2f7566eb6f4560270983e4c9ad8c6f74b88989ead1d57b19978750
FP-I     54  a2dfa5ac5dd894dd62451198aa75ea2bc0f86a955236d9f0e9bda234cdb4bef8
FP-E    359  cbc9f3c772b723bfd2747b53c5b8338346bb39bb20f198a6c3b7b10e2eaa7e7b
FP-L     50  2de76f2923aad9455fc352e8b9025dc8713e8eb1a9cbadcc6cf8149a1a69c426
FP-U    152  eac672bb188e567443fdfc4a4948132307b5eca4645d43104933662c1d690ef1
TP-I      1  c2dc616e4d4aa347d54922da17f11e2aed0dd5eba1eee991c3d364cf4d69f67c
TP-E    998  d50e008902c17730e221746e17c19f0b885e348da67de86a2b9a848e2b1bbbef
TP-L    627  38d8ad149ce9b93ac813668600b25f4c5a69709183b3a3006fa700576d28d5f5
TP-U   2600  9ff060fa2183ee7bad94e88a127d102c9005027db1668bfaaa332ab5c1a0a69e
D3      706  701fccf98a6500568ddb8eab731bdc7550528045fa316ec6906b06e10ae2d5e2
D4      391  3b5204bbb56e6e400eb40373afae1eceb8c2bf4872e49b39bcb3f3de013bda9e
D5R      43  c7c871f84e34ad1ff9b225ef55d89843ee5de3373cf196624c8e2f3832630452
D5       69  82178876aac74242c0dcf2925abfa2d9805a50d7bc3544cc9db3097b2001e42a
D6      212  ebfd59e7da2123eeff336e1dea1401c01666793f2f51801483f101f7390c72c5
D7       30  9796ec3194c8ac1b0ce70e61b89654754f40da861b090e9b2e27df6ef42fd127
```

**Adequacy of the depths.** The depth for each class is adequate because the *rule that makes a class irrelevant is itself mechanical and total*: (i) non-code classes (D1, D2, D3, D4, D6) are never evaluated by Node — the only TypeScript Pi transpiles is the single `--extension` path; (ii) code classes are split by *reachability from the launch anchor* and, inside the reachable set, by *capability* — every reachable first-party file that can spawn, touch the network, write files, read the environment, load code dynamically, or use WASM/native is listed with the gate that must be opened to invoke it (Sec.7.3) and none of those gates is opened by AIDO's argv, environment or configuration; (iii) the files whose logic actually participates in a derivation (Sec.9) were read individually. Where a gate is a *flag*, the flag handling itself (`args.js`, `main.js`, `resource-loader.js`, `agent-session.js`) is an individually read, cited derivation (N-06, N-08).

### 7.3 First-party capability-bearing files and the gate that guards each

Every first-party JS file in the eager or lazy reachable set that carries a premise-relevant capability, grouped by the **invocation gate**. *Status* values: **EXECUTES AT STARTUP** (runs on AIDO's launch), **NOT INVOKED** (gate closed under AIDO's argv/env/config), **NOT LOADED** (module is evaluated at import but its feature is never constructed), **INDIVIDUALLY READ**.

| Gate (what must be true for the code to run) | Status | Files (capabilities) |
|---|---|---|
| user commands (`/bug`, export); not in the RPC command set | **NOT INVOKED** | `dist/core/bug-report-upload.js` (net_http); `dist/core/export-html/index.js` (fs_write); `dist/core/session-export.js` (fs_write) |
| no caller in the non-interactive payload | **NOT INVOKED** | `dist/core/crash-log.js` (fs_write) |
| ExtensionAPI `exec`; AIDO's extension never calls it | **NOT INVOKED** | `dist/core/exec.js` (child_process) |
| interactive footer only | **NOT INVOKED** | `dist/core/footer-data-provider.js` (child_process) |
| built-in extension; excluded by `--no-extensions` (`resource-loader.js` `extensionPaths = cliEnabledExtensions`, N-08) | **NOT LOADED** | `dist/core/mcp-servers.js` (net_http); `dist/extensions/llama/client.js` (net_http); `dist/extensions/llama/huggingface.js` (net_http); `dist/extensions/mcp/config.js` (fs_write); `dist/extensions/mcp/log.js` (fs_write); `dist/extensions/mcp/oauth.js` (net_http,fs_write) |
| built-in tool implementation; excluded from the registry by the `--tools` allowlist (`agent-session.js` `_refreshToolRegistry` filter, N-08) | **NOT INVOKED** | `dist/core/tools/bash.js` (child_process); `dist/core/tools/edit.js` (fs_write); `dist/core/tools/find.js` (child_process); `dist/core/tools/grep.js` (child_process); `dist/core/tools/write.js` (fs_write) |
| InteractiveMode only — `main.js` `appMode === "interactive"`; AIDO's `--mode rpc` makes `appMode` `rpc` (main.js:81-84, 776-808) | **NOT INVOKED** | `dist/modes/interactive/components/session-selector.js` (child_process); `dist/modes/interactive/external-editor.js` (child_process,fs_write); `dist/modes/interactive/interactive-mode.js` (child_process,net_http,fs_write); `dist/modes/interactive/session-share.js` (child_process,net_http,fs_write) |
| print/json modes only (`main.js:809-823`) | **NOT INVOKED** | `dist/modes/print-mode.js` (child_process) |
| `RpcClient` embedding class; never instantiated by `main` | **NOT INVOKED** | `dist/modes/rpc/rpc-client.js` (child_process) |
| `handlePackageCommand`/`handleConfigCommand`/`mcp` subcommands only (`main.js:469-488`) | **NOT INVOKED** | `dist/package-manager-cli.js` (net_http,fs_write); `dist/utils/zip.js` (fs_write) |
| image/clipboard/browser helpers reached from tools or interactive mode | **NOT INVOKED** | `dist/utils/child-process.js` (child_process); `dist/utils/clipboard-command.js` (child_process); `dist/utils/clipboard-image.js` (fs_write); `dist/utils/clipboard.js` (fs_write); `dist/utils/image-resize.js` (worker); `dist/utils/open-browser.js` (child_process); `dist/utils/output-files.js` (fs_write); `dist/utils/photon.js` (wasm_native,createRequire) |
| `fetchWithRetry` helper used by tools-manager, version-check and `remote-catalog-provider` (model-catalog refresh runs only when `allowNetwork`, which `--offline`/`PI_OFFLINE` and `ModelRuntime.create` default to false) | **NOT INVOKED** | `dist/utils/management-http.js` (net_http) |
| `killTrackedDetachedChildren` runs on SIGTERM and only kills children the (inactive) bash tool tracked | **NOT INVOKED (no tracked children)** | `dist/utils/shell.js` (child_process) |
| `ensureTool` is called only from `find.js:119` / `grep.js:52`; also `PI_OFFLINE`-gated (`tools-manager.js:13`) | **NOT INVOKED** | `dist/utils/tools-manager.js` (child_process,fs_write) |
| `streamProxy` client; `sdk.js` wires `streamFn` to `ModelRuntime`, not to it | **NOT INVOKED** | `node_modules/@earendil-works/pi-agent-core/dist/proxy.js` (net_http) |
| backing library of the MCP / codemode built-in extensions (not loaded) | **NOT LOADED** | `node_modules/@earendil-works/pi-codemode/dist/runtime/host.js` (wasm_native,worker); `node_modules/@earendil-works/pi-codemode/dist/runtime/prelude-source.js` (net_http); `node_modules/@earendil-works/pi-codemode/dist/wasm.js` (wasm_native,createRequire); `node_modules/@earendil-works/pi-mcp/dist/oauth/callback.js` (net_http); `node_modules/@earendil-works/pi-mcp/dist/oauth/discovery.js` (net_http); `node_modules/@earendil-works/pi-mcp/dist/transports/stdio.js` (child_process); `node_modules/@earendil-works/pi-mcp/dist/transports/streamable-http.js` (net_http) |
| TUI library; used only by interactive components, clipboard and terminal-image helpers | **NOT INVOKED** | `node_modules/@earendil-works/pi-tui/dist/autocomplete.js` (child_process); `node_modules/@earendil-works/pi-tui/dist/native-module-path.js` (createRequire); `node_modules/@earendil-works/pi-tui/dist/native-platform.js` (createRequire); `node_modules/@earendil-works/pi-tui/dist/terminal-image.js` (child_process); `node_modules/@earendil-works/pi-tui/dist/terminal.js` (fs_write); `node_modules/@earendil-works/pi-tui/dist/tui-main-screen.js` (fs_write) |
| `jiti` factory for the one `--extension` path | **EXECUTES (for AIDO's extension)** | `dist/core/extensions/jiti-loader.js` (jiti); `dist/core/extensions/jiti-static-loader.js` (jiti) |
| selected only by another `model.api` value or by an OAuth/Bedrock flow; AIDO's model is `openai-completions` with an env-resolved API key | **NOT INVOKED** | `node_modules/@earendil-works/pi-ai/dist/api/bedrock-converse-stream.lazy.js` (dyn_import_nonlit; read); `node_modules/@earendil-works/pi-ai/dist/api/openai-codex-responses.js` (net_http); `node_modules/@earendil-works/pi-ai/dist/api/openai-responses.js` (net_http); `node_modules/@earendil-works/pi-ai/dist/api/openrouter-images.js` (net_http); `node_modules/@earendil-works/pi-ai/dist/auth/oauth/load.js` (dyn_import_nonlit; read) |
| every write is gated by `persist`; `--no-session` constructs `SessionManager.inMemory` (`main.js:286-288`) | **NOT INVOKED (in-memory)** | `dist/core/session-manager.js` (fs_write; read) |
| `cleanupWindowsSelfUpdateQuarantine(getPackageDir())` runs on every `win32` start (`main.js:460-462`) | **EXECUTES AT STARTUP (F-5)** | `dist/utils/windows-self-update.js` (fs_write; read) |
| default auth context: `env()` reads `process.env`; `fileExists()` probes a path with `fs.access` (e.g. `~/.config/gcloud/application_default_credentials.json` for the built-in `google-vertex`) | **EXECUTES AT STARTUP (F-5)** | `node_modules/@earendil-works/pi-ai/dist/auth/context.js` (dyn_import_nonlit; read) |
| node:fs/os/path loaded by fixed specifier at import; an `existsSync` probe of the same ADC path inside the Google-Vertex credential check | **EXECUTES AT STARTUP (built-ins only; probe during availability refresh, F-5)** | `node_modules/@earendil-works/pi-ai/dist/env-api-keys.js` (dyn_import_nonlit; read) |

*Capability-bearing files not covered by a gate row above (group shown; FP-I = individually inspected, so their behavior is cited in Sec.5/8):*

- `dist/config.js` (wasm_native, createRequire) — group FP-I
- `dist/core/agent-session-runtime.js` (child_process, fs_write) — group FP-I
- `dist/core/auth-storage.js` (fs_write) — group FP-I
- `dist/core/extensions/loader.js` (dyn_import_nonlit, createRequire, jiti) — group FP-I
- `dist/core/http-dispatcher.js` (net_http) — group FP-I
- `dist/core/package-manager.js` (fs_write) — group FP-I
- `dist/core/resolve-config-value.js` (child_process) — group FP-I
- `dist/core/settings-manager.js` (fs_write) — group FP-I
- `dist/core/trust-manager.js` (fs_write) — group FP-I
- `dist/migrations.js` (fs_write) — group FP-I
- `node_modules/@earendil-works/pi-ai/dist/providers/radius-config.js` (net_http) — group FP-I

**Startup-executed behaviors that are not premises but are recorded (F-5):** (i) on `win32` Pi recursively deletes `<enclosing node_modules>/.pi-native-quarantine` if present — a delete *outside* both the payload root and AIDO's workspace (absent at review time); (ii) `AuthStorage` creates `auth.json` (`{}`) and `FileModelsStore` creates `models-store.json` in the pinned config directory, and `proper-lockfile` creates transient `*.lock` entries beside `settings.json`/`auth.json` — AIDO's removal of the config directory is recursive (`remove_disposable_tree`), so extra files do not defeat cleanup; (iii) the provider-availability refresh probes the *existence* (not contents) of well-known credential files such as the Google ADC path under the OS-resolved home. None of these reads or forwards a credential, and none alters a CFG1-CC1 derivation.

### 7.4 Third-party code that carries a request-path or launch-path role (individually bounded)

- **`openai` 7.19.0** — `client.mjs` read at the transport region: `buildURL` joins `baseURL + path`; `maxRetries` is `options.maxRetries ?? this.maxRetries` and Pi passes `maxRetries: 0` per request; the SDK reads `OPENAI_BASE_URL/OPENAI_API_KEY/OPENAI_CUSTOM_HEADERS` from the environment **only when options are absent** (Pi always passes `apiKey` and `baseURL`; AIDO's child environment carries neither name); workload-identity/X.509 auth paths exist but are opt-in by option and conflict with `apiKey`. Loaded lazily, exactly when `openai-completions.js` loads (G-13).
- **`undici` 8.10.2** — installed as the *global* dispatcher by `configureHttpDispatcher` (`EnvHttpProxyAgent`, body/headers timeouts from `httpIdleTimeoutMs`); proxy variables are read from the environment, and AIDO's allowlisted child environment withholds every name containing `PROXY` (`environment.py` `FORBIDDEN_NAME_FRAGMENTS`).
- **`jiti` 2.7.0** — transpiles and loads AIDO's TypeScript extension (N-12). It executes AIDO-authored code by design (accepted runtime trust model); it is where Pi evaluates AIDO-supplied code.
- **`typebox` 1.3.27** — compiles the `models.json` schema validator (`model-config.js`); no `eval`-class construct was found in reachable `typebox` files by the capability scan.
- Reachable third-party capability totals (eager ∪ lazy): `child_process` 8 files (Anthropic SDK 3, `cross-spawn` 2, `google-auth-library` 2, `openai` 1), `worker` 2, `wasm_native` 4, `eval_like` 1 (`photon-node`), `net_http` 57. All sit behind the same gates as their first-party importers.

### 7.5 Dynamically reachable files — the non-literal loaders

Reachability above uses literal specifiers. The complete list of **non-literal** `import()` sites in reachable first-party code (5), and what each can load:

| Site | What it can load | Opened by AIDO's flow? |
|---|---|---|
| `core/extensions/loader.js` `jiti.import(extensionPath)` | the extension path(s) Pi is told to load | **Yes — AIDO's own `--extension` file only** (`--no-extensions` removes every other source) |
| `pi-ai/dist/auth/oauth/load.js` `importOAuthModule("./<provider>.ts")` | a fixed set of OAuth flow modules (the `auth/oauth/*.js` files, all unreached by literal edges) | No — OAuth login/refresh only |
| `pi-ai/dist/api/bedrock-converse-stream.lazy.js` | `./bedrock-converse-stream.js` | No — only for `api: bedrock-converse-stream` |
| `pi-ai/dist/auth/context.js`, `pi-ai/dist/env-api-keys.js` | `node:fs`, `node:fs/promises`, `node:os`, `node:path` (fixed built-ins) | Yes (built-ins only) |

Other dynamic-code constructs in reachable first-party code: `createRequire` (`config.js` for `quickjs-wasi` path resolution, `loader.js`, `photon.js`, pi-tui native-module lookup) — all resolve fixed package names or fixed relative `.node`/`.wasm` paths; **no** `eval`, `new Function` or `vm` in any reachable first-party file; WASM/native use is confined to codemode, photon image resize and the pi-tui clipboard helpers (not invoked).

**Entry points that would reach the unreached groups** (declared in `package.json`): `bin.pi → dist/bundle/cli.js` (the bundle), `exports["./rpc-entry"] → dist/bundle/rpc-entry.js`, `main → dist/index.js` (a library surface). AIDO launches none of them.

### 7.6 Review of the AIDO premise classes against the whole non-seam payload

| Class named in the brief | E1 premise(s) | Non-seam files individually read for it | Whole-payload conclusion |
|---|---|---|---|
| process launch | G-19, N-06 | `cli/setup.js`, `cli/args.js`, `config.js`, `main.js`(seam) | Node-direct `dist/cli.js` → `setup.js` → `main.js`; flags recognised; offline flags set env. No new launch layer. |
| RPC framing | G-16, G-17, N-09 | `core/output-guard.js`, `modes/json-event.js` | Framing bytes unchanged; stdout write path is an ordered queue; stray stdout redirected to stderr. |
| extension loading | N-04, N-08, N-12 | `core/resource-loader.js`, `core/package-manager.js`, `core/extensions/{loader,runner,wrapper,index}.js`, `core/source-info.js`, `extensions/index.js` | **New:** four built-in extensions exist; `--no-extensions` excludes them (static derivation); AIDO's extension loads via `jiti`. |
| tool dispatch | G-12, N-03, N-08 | `core/tools/tool-definition-wrapper.js`, `core/extensions/wrapper.js` | Declared tools = allowlist; dispatch via `agent-loop` only; no `tool_search`/codemode/MCP surface. |
| request building | G-03…G-11, G-13, G-14, N-10, N-11 | `pi-ai` `utils/{transcript,text}.js`, `api/{transform-messages,constrained-sampling,lazy}.js`, `compat.js`, `utils/{provider-retry,provider-env,pi-user-agent,sanitize-unicode}.js`, `core/{messages,settings-manager,provider-attribution,telemetry,cache-warmer,resolve-config-value}.js` | **Changed (Sec.10).** Production-consumed facts hold; two documented sub-facts differ. |
| provider/model composition & resolution | G-01, G-02, G-07, G-15, N-05 | `core/{agent-session-services,models-store,auth-storage,radius,http-dispatcher}.js`, `pi-ai/providers/radius-config.js` | Custom provider composed from `models.json`; no built-in id collision; offline gates verified. |
| network behavior relevant to CFG1 | N-07, N-10, N-11 | `http-dispatcher.js`, `radius-config.js`, `cache-warmer.js`, `provider-attribution.js` | Model-catalog/Radius/tools-manager/version-check network paths are gated by `--offline`/`PI_OFFLINE` or by features not selected; one HTTP request per model call. |
| filesystem behavior relevant to CFG1 | N-07, F-5 | `migrations.js`, `auth-storage.js`, `models-store.js`, `trust-manager.js`, `project-trust.js`, `settings-manager.js`, `windows-self-update.js` | Config-dir extra files (recursively removed); one out-of-tree delete candidate (absent); project config excluded by trust=false. |
| prompt / system-prompt construction | G-11 | `system-prompt.js`(seam), `pi-ai/utils/text.js`, `core/resource-loader.js` (SYSTEM.md discovery) | Sections incl. new `docs`; SYSTEM.md/APPEND discovery is trust-gated (project) or config-dir (none present). |
| configuration discovery | N-06, N-07 | `resource-loader.js`, `settings-manager.js`, `trust-manager.js`, `project-trust.js` | `--no-approve` ⇒ `projectTrusted=false` (`main.js:593-597`); pinned config dir; no auto-discovered resource survives the flags. |
| agent/session lifecycle | N-01, N-02 | (seam) + `core/agent-session-runtime.js` | Ack → `agent_start` → … → `agent_end`(willRetry) → `agent_settled` order preserved. |
| stop/settle behavior | N-02, N-09 | (seam) | `agent_settled` in `finally`; stdin-close shutdown lever intact. |

## 8. Individual escalations from E3

### 8.1 Non-seam first-party files inspected individually (group FP-I, 54 files)

Depth: **whole** = the file was read end to end; **region** = the regions bearing on the cited premise were read (keyword-located, then read with context); a region-depth inspection is *not* a whole-file audit and is not claimed to be.

| File | Depth | Why escalated | Outcome |
|---|---|---|---|
| `dist/cli/args.js` | region | flag semantics (N-06) | read; no counter-example to the E1 derivations |
| `dist/cli/setup.js` | whole | launch path; OC-3 premise | read; no counter-example to the E1 derivations |
| `dist/config.js` | region | env/config dir names (N-07); doc paths (G-11) | read; no counter-example to the E1 derivations |
| `dist/core/agent-session-runtime.js` | region | capability scan hit (child_process/fs_write) — `fork(` and `mkdirSync` are session import/fork helpers, not startup | read; false-positive capability hit (no process spawn); `mkdirSync` only in `importFromJsonl` |
| `dist/core/agent-session-services.js` | whole | model runtime + resource loader composition | read; no counter-example to the E1 derivations |
| `dist/core/auth-storage.js` | region | config-dir writes | read; creates `auth.json` / `models-store.json` (+lock entries) in the config dir (F-5) |
| `dist/core/cache-warmer.js` | whole | possible extra model requests (N-10) | read; default mode `streaming` but inert without `promptCache` (F-6) |
| `dist/core/extensions/index.js` | whole | extension API surface | read; no counter-example to the E1 derivations |
| `dist/core/extensions/loader.js` | region | extension acceptance (N-12) | read; no counter-example to the E1 derivations |
| `dist/core/extensions/runner.js` | region | invocationName (N-04) | read (region); `invocationName` uniqueness (F-9) |
| `dist/core/extensions/wrapper.js` | whole | tool execute wrapper (N-12) | read; no counter-example to the E1 derivations |
| `dist/core/http-dispatcher.js` | whole | global network dispatcher | read; no counter-example to the E1 derivations |
| `dist/core/messages.js` | whole | convertToLlm (G-09) | read; no counter-example to the E1 derivations |
| `dist/core/models-store.js` | whole | config-dir writes | read; creates `auth.json` / `models-store.json` (+lock entries) in the config dir (F-5) |
| `dist/core/output-guard.js` | whole | stdout framing path (G-17) | read; no counter-example to the E1 derivations |
| `dist/core/package-manager.js` | region | CLI extension source parsing (N-04, N-08) | read; no counter-example to the E1 derivations |
| `dist/core/project-trust.js` | whole | trust decision | read; no counter-example to the E1 derivations |
| `dist/core/prompt-templates.js` | region | prompt expansion only for `/…` text (N-01) | read; no counter-example to the E1 derivations |
| `dist/core/provider-attribution.js` | whole | URL/host-keyed headers (N-11) | read; host/provider-keyed, all inside the AIDO substring list; gated by `PI_TELEMETRY` |
| `dist/core/radius.js` | whole | network gateway default | read; no counter-example to the E1 derivations |
| `dist/core/resolve-config-value.js` | whole | `$ENV` vs `!command` apiKey semantics (N-11) | read; `!` prefix executes a shell command — AIDO's key is `$NAME` |
| `dist/core/resource-loader.js` | region | extension/skill/prompt/theme/context discovery (N-04, N-08) | read; no counter-example to the E1 derivations |
| `dist/core/session-manager.js` | region | persistence gated by `persist` (in-memory under `--no-session`) | read; no counter-example to the E1 derivations |
| `dist/core/settings-manager.js` | region | settings keys, retry, thinking, cache warming (N-07, N-10) | read; no counter-example to the E1 derivations |
| `dist/core/source-info.js` | whole | H1 sourceInfo (N-04) | read; no counter-example to the E1 derivations |
| `dist/core/telemetry.js` | whole | telemetry gate (N-11) | read; no counter-example to the E1 derivations |
| `dist/core/tools/tool-definition-wrapper.js` | whole | tool execute wrapper (N-12) | read; no counter-example to the E1 derivations |
| `dist/core/trust-manager.js` | region | project trust / home probes | read; no counter-example to the E1 derivations |
| `dist/core/virtual-models.js` | region | virtual-model gate on `model.api` | read; no counter-example to the E1 derivations |
| `dist/extensions/codemode/index.js` | whole | built-in tool surface | read; no counter-example to the E1 derivations |
| `dist/extensions/index.js` | whole | built-in extension list | read; no counter-example to the E1 derivations |
| `dist/extensions/tool-search/index.js` | whole | built-in tool surface | read; no counter-example to the E1 derivations |
| `dist/migrations.js` | whole | startup writes | read; legacy-file migrations; no-op for AIDO's pinned config dir (no `apiKeys`, `oauth.json`, `commands/`) and workspace |
| `dist/modes/index.js` | whole | mode exports | read; no counter-example to the E1 derivations |
| `dist/modes/json-event.js` | whole | event serialization (N-03) | read; no counter-example to the E1 derivations |
| `dist/utils/paths.js` | region | `isLocalPath` (N-04) | read; no counter-example to the E1 derivations |
| `dist/utils/windows-self-update.js` | whole | runs at every win32 start (F-5) | read; recursive delete of `<node_modules>/.pi-native-quarantine` on every win32 start (F-5) |
| `node_modules/@earendil-works/pi-ai/dist/api/bedrock-converse-stream.lazy.js` | whole | non-literal loader (7.5) | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/api/constrained-sampling.js` | region | request building (G-09) | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/api/lazy.js` | whole | request building (G-09) | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/api/openai-completions.lazy.js` | whole | request building (G-09) | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/api/transform-messages.js` | whole | request building (G-09) | read; system/user messages pass through unchanged |
| `node_modules/@earendil-works/pi-ai/dist/auth/context.js` | whole | default auth context: env + file-existence probe | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/auth/oauth/load.js` | region | non-literal loader (7.5) | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/compat.js` | whole | request building (G-09) | read; API registry: `openai-completions` → lazy `openai-completions.js`; also registers 9 other APIs |
| `node_modules/@earendil-works/pi-ai/dist/env-api-keys.js` | region | request building (G-09) | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/legacy-api-aliases.js` | region | API alias registry | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/providers/radius-config.js` | region | request building (G-09) | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/utils/pi-user-agent.js` | whole | request building (G-09) | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/utils/provider-env.js` | whole | request building (G-09) | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/utils/provider-retry.js` | whole | request building (G-09) | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/utils/sanitize-unicode.js` | whole | request building (G-09) | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/utils/text.js` | whole | request building (G-09) | read; no counter-example to the E1 derivations |
| `node_modules/@earendil-works/pi-ai/dist/utils/transcript.js` | whole | request building (G-09) | read; no counter-example to the E1 derivations |

### 8.2 Third-party file read individually (group TP-I)

`node_modules/openai/client.mjs` (sha256 `fc5b25a2e1a7a3a0f67e2cf1c21b4bd768d778aaeb877cbc3789088e3e1eca02`) — request transport; see Sec.7.4. No counter-example.

### 8.3 Native, WASM and script files (groups N1 and D7) — listed individually

| Path | Bytes | SHA-256 | Basename named by reachable JS |
|---|---:|---|---|
| `examples/extensions/doom-overlay/doom/build/doom.wasm` | 380169 | `571d161956593508cf4ade732ae93753f00484bb526667a8676571cca14dec7d` | — |
| `node_modules/@earendil-works/pi-tui/native/darwin/prebuilds/darwin-arm64/darwin-platform.node` | 52024 | `36e909adf35c2734a2a52b3d65b7dbfb83f2278f306d51b7e32c5045516dfb7f` | computed path (`native-platform.js`) |
| `node_modules/@earendil-works/pi-tui/native/darwin/prebuilds/darwin-x64/darwin-platform.node` | 22784 | `7ec59a02fff9562f6354274ad070ba35f8e0998b3b111eb27ad3de579ffb6c65` | computed path (`native-platform.js`) |
| `node_modules/@earendil-works/pi-tui/native/linux/prebuilds/linux-arm64/linux-platform-x11.node` | 67240 | `63d4545349a25b5c97e352ea6d254cea50ff3c14161212ad3ddb3fc28022ddb5` | computed path (`native-platform.js`) |
| `node_modules/@earendil-works/pi-tui/native/linux/prebuilds/linux-x64/linux-platform-x11.node` | 18008 | `522d2550f7fa5d0d5bd204f45983f786ce2be9cf80f27f00179640d31d0689d6` | computed path (`native-platform.js`) |
| `node_modules/@earendil-works/pi-tui/native/win32/prebuilds/win32-arm64/win32-platform.node` | 9216 | `0e5671ab39ef577940483ced58fdf29ecdf5f864f368d90a771eec4aeeae11b8` | computed path (`native-platform.js`) |
| `node_modules/@earendil-works/pi-tui/native/win32/prebuilds/win32-x64/win32-platform.node` | 8704 | `51bee02bcb73b165ab92af75ae15b88aba3f5d99f072e63ef60af92ffdc4d565` | computed path (`native-platform.js`) |
| `node_modules/@esbuild/win32-x64/esbuild.exe` | 11694592 | `c7bee37877d0aa6a046e52783fa0a2cf1a9ce5579d68bb3083bda99d4bff18ef` | — |
| `node_modules/@silvia-odwyer/photon-node/photon_rs_bg.wasm` | 1881634 | `10468181565c56004c867f3a4af96f89a0ef5a63a72f2b5fb12c1f1992a3615c` | `photon.js`, `photon_rs.js` |
| `node_modules/quickjs-wasi/extensions/crypto/crypto.so` | 120228 | `fa26b6fafda251c3b1442dcc4c876b3ac73689639519f4ddfc2c410ebdb5b7c2` | — |
| `node_modules/quickjs-wasi/extensions/encoding/encoding.so` | 7715 | `d501aa2a8410ee07c196103f0d169b226ec61c922883713510fd723fe14036c3` | — |
| `node_modules/quickjs-wasi/extensions/headers/headers.so` | 8896 | `42c847104d6aa8d4666fa41bb74d324c2ee9a4d15c2492fca013b1631232b011` | — |
| `node_modules/quickjs-wasi/extensions/structured-clone/structured-clone.so` | 6007 | `0ac5a36c0545c659ba6f9f8de5af11862df84546d151d0f15ec5184c95fd6cb3` | — |
| `node_modules/quickjs-wasi/extensions/url/url.so` | 397332 | `af780a79f1fb131b5e6fa1d6fedc481e265420cf2f254fe966255230f4c1bc62` | — |
| `node_modules/quickjs-wasi/quickjs.wasm` | 637405 | `d4c9375f2b1ca4dc95f72c8aa2982a7a9951ac8011490d79c6582df732b4bbd9` | `config.js`, `wasm.js` |

Scripts and shims (D7, 30): `examples/extensions/doom-overlay/doom/build.sh`, `node_modules/.bin/anthropic-ai-sdk`, `node_modules/.bin/anthropic-ai-sdk.cmd`, `node_modules/.bin/anthropic-ai-sdk.ps1`, `node_modules/.bin/esbuild`, `node_modules/.bin/esbuild.cmd`, `node_modules/.bin/esbuild.ps1`, `node_modules/.bin/jiti`, `node_modules/.bin/jiti.cmd`, `node_modules/.bin/jiti.ps1`, `node_modules/.bin/marked`, `node_modules/.bin/marked.cmd`, `node_modules/.bin/marked.ps1`, `node_modules/.bin/node-which`, `node_modules/.bin/node-which.cmd`, `node_modules/.bin/node-which.ps1`, `node_modules/.bin/pi-ai`, `node_modules/.bin/pi-ai.cmd`, `node_modules/.bin/pi-ai.ps1`, `node_modules/.bin/semver`, `node_modules/.bin/semver.cmd`, `node_modules/.bin/semver.ps1`, `node_modules/.bin/yaml`, `node_modules/.bin/yaml.cmd`, `node_modules/.bin/yaml.ps1`, `node_modules/@anthropic-ai/sdk/bin/cli`, `node_modules/@earendil-works/pi-tui/native/darwin/build.sh`, `node_modules/@earendil-works/pi-tui/native/linux/build.sh`, `node_modules/esbuild/bin/esbuild`, `node_modules/which/bin/node-which`.

### 8.4 Nested `node_modules`, example/plugin content, and other classes the brief names

- **Nested `node_modules` (4 packages):** `node_modules/@aws-sdk/credential-provider-sso/node_modules/@aws-sdk/token-providers` (@aws-sdk/token-providers 3.1138.0); `node_modules/gaxios/node_modules/agent-base` (agent-base 7.1.4); `node_modules/gaxios/node_modules/https-proxy-agent` (https-proxy-agent 7.0.6); `node_modules/proper-lockfile/node_modules/retry` (retry 0.12.0). Each is bound by its manifest, accounted in Appendix A, and resolved by the Node nesting rule in the import-graph model (e.g. `proper-lockfile` → its own `retry`).
- **Examples and plugins (`examples/**`, 136 files):** not a Pi discovery root. Pi discovers extensions from `<config dir>/extensions`, `<cwd>/.pi/extensions` (trust-gated), `settings.packages`, built-ins and `--extension`; `examples/` appears only in documentation and in the system prompt's `docs` text. AIDO's `packages: []`, `extensions: []`, `--no-extensions` and `projectTrusted=false` close every one of those sources. `examples/plugins/pi-example-plugin` is a separate `private` package (peer `^0.84.4`) that would matter only if installed as a package.
- **Extension/plugin presence that *could* affect discovery:** the four built-in extensions (`llama.cpp`, `codemode`, `tool-search`, `mcp`) — see F-8. They are *present*, *excluded by flag*, and their exclusion is a static derivation (N-08), not a per-run AIDO observation.
- **`package.json` files:** 146 non-seam manifests tabulated (Appendix A and 6.1); install scripts exist in 14 third-party manifests (`esbuild`, `protobufjs` postinstall, several `prepare`) — they ran, if ever, at npm-install time, outside this review; nothing in AIDO or Pi runs them.

### 8.5 Adversarial static review — counter-examples sought against the old derivations

| Search | Result |
|---|---|
| new imports from files outside PI-SC1 | **Yes.** Every changed seam file imports non-seam first-party modules (table 9.2). The ones that carry derivation logic are individually read (FP-I); the rest are accounted for under their capability gates. |
| new lazy/dynamic imports | 5 non-literal sites enumerated (7.5); 50 lazy-only first-party files and 627 lazy-only third-party files accounted for by trigger. |
| new process spawning | 22 first-party eager files carry `child_process`; every one is gated (7.3). The only spawning an AIDO launch can reach is `resolve-config-value.js` for an apiKey beginning `!` (AIDO's begins `$`) and `jiti`-loaded extension code. |
| new network/request builders | `openai-completions.js` (seam) + `openai` SDK + global `undici`; Radius/model-catalog/tools-manager/version-check/bug-report are gated (`--offline`, features not selected). One HTTP request per model call (N-10). |
| alternate API implementations | `compat.js` registers 10 APIs; the model's `api` is the exact string `openai-completions` (AIDO-written), so `getApiProvider` returns the lazy `openai-completions` implementation. An extension could register an override; none does. |
| new tool-dispatch paths | `ctx.executeTool` / nested calls and `tool_search`/codemode/MCP exist; none is loaded or allowlisted. Dispatch for model-issued calls is `agent-loop.js` only (G-12). |
| new extension/plugin discovery | built-in extensions; package-manager auto-discovery; project resources — all closed by flags/config (N-08, 8.4). |
| changed RPC acknowledgement ordering | No — ack still strictly precedes `agent_start` (N-01); payload gained `data.disposition`. |
| changed agent lifecycle ordering | No — `agent_start` … `agent_end` … `agent_settled` order and `finally` placement preserved (N-02); extension `agent_settled` handlers run *before* the session emits it (none registered). |
| new prompt/system-prompt layers | Yes: sections incl. `docs`; `before_agent_start` extension hook can add sections (none); SYSTEM.md/APPEND_SYSTEM.md discovery (gated / absent). |
| changed model/provider resolution | Yes in structure (`ModelRuntime`, catalogs, virtual models, Radius); AIDO's outcome unchanged (G-02, G-15, N-05). |
| new filesystem/config lookup surfaces | `models-store.json`, `trust.json`, `bin/`, quarantine root, ADC existence probe, `~/.agents/skills` (skills disabled by `--no-skills`) — F-5. |
| `createRequire` / dynamic import / `eval` / `vm` / WASM / native-load relevant to the relied-upon behavior | none relevant; `eval`/`vm`/`new Function`: 0 in reachable first-party code (7.5). |
| request-building logic moved outside the seam | **Yes** — `transcript.js`, `text.js`, `transform-messages.js`, `constrained-sampling.js`, `provider-retry.js`, `compat.js` (Sec.9). |
| load-bearing logic delegated to a dependency E1 does not cover | `openai` SDK transport and `undici` dispatcher (bounded in 7.4; not AIDO premises); `jiti` (accepted trust model). |

**Accepted HPP-1 residuals were not turned into blockers.** Nothing above makes a *frozen CFG1 claim* mechanically false; the items that touch external-runtime residuals are stated in Sec.12.

## 9. Seam-sufficiency determination

**Question.** Does `PI-SC1` still contain every file required to support the E1 derivations AIDO relies on?

**Answer: No — not as a self-contained evidence set for this candidate.** The derivations of the request shape, the system prompt, the framing byte path, the extension-identity (H1) gate and the launch/offline/retry semantics now require reading **23 non-seam files** (list below; the first-party ones are the group FP-I files that appear in a citation or premise column of Sec.4–5). In the genesis derivations the equivalent logic lived in seam files (e.g. system-prompt text assembly in `system-prompt.js`/`agent-session.js`; the instruction-message and tool list inside `openai-completions.js`); in the candidate it has moved into `pi-ai` transcript/text helpers and into coding-agent services. (Some genesis premises — H1 identity and the generated-config acceptance — never lived in the seam at all and were established by the runtime gates L15/L16; that does not change the present finding.)

**Non-seam files that entered a derivation basis in this phase (23):**

`dist/cli/args.js`, `dist/cli/setup.js`, `dist/config.js`, `dist/core/cache-warmer.js`, `dist/core/extensions/loader.js`, `dist/core/extensions/runner.js`, `dist/core/output-guard.js`, `dist/core/package-manager.js`, `dist/core/provider-attribution.js`, `dist/core/resolve-config-value.js`, `dist/core/resource-loader.js`, `dist/core/settings-manager.js`, `dist/core/source-info.js`, `dist/core/telemetry.js`, `dist/core/tools/tool-definition-wrapper.js`, `dist/modes/json-event.js`, `node_modules/@earendil-works/pi-ai/dist/api/constrained-sampling.js`, `node_modules/@earendil-works/pi-ai/dist/api/openai-completions.lazy.js`, `node_modules/@earendil-works/pi-ai/dist/api/transform-messages.js`, `node_modules/@earendil-works/pi-ai/dist/compat.js`, `node_modules/@earendil-works/pi-ai/dist/utils/provider-retry.js`, `node_modules/@earendil-works/pi-ai/dist/utils/text.js`, `node_modules/@earendil-works/pi-ai/dist/utils/transcript.js`.

**What the brief and the design say to do.** `PI-SC1` was *not* casually expanded, and nothing here proposes expanding it. HPP-1 design **F-7** states the rule exactly: *seam sufficiency affects only whether E1 may be reused; if derivation-relevant logic moved to a non-seam file, E3 must catch it and the derivation be redone, or the case escalates to C5.* E3 caught it (Sec.7–8), and each affected derivation was **redone** with line citations against hash-bound bytes (Sec.5). The question the brief asks next — *can the affected derivation be soundly re-derived with the current contract?* — is answered **yes** for this candidate, for three reasons:

1. The **payload fingerprint pins every one of those 23 files** (PROFILE-COVERED FACT). The derivations are therefore bound to exactly these bytes even though `PI-SC1` does not name them.
2. This candidate's approval would cite these derivations as **new evidence for this profile**, not as *reused* evidence. The only reuse mechanism the APS schema offers for E1 (`premise_scope: SEAM_FILES`) is **not used** by any claim whose premise includes a non-seam file (the checker above enforces this: the two `REUSE` claims have no changed or non-seam premise).
3. No claim needed a premise the current contract cannot express for a *first, non-reused* profile.

**Reuse restriction recorded for PE-5 and any later candidate.** Because `premise_scope: SEAM_FILES` can name only seam paths, derivations **G-08, G-09, G-10, G-11, G-13, G-17, N-02, N-03, N-04, N-06, N-07, N-08, N-10, N-11, N-12** (those whose derivation basis — premise or cited evidence — includes a non-seam file) **must not be reused** for a future candidate on the strength of seam equality alone: a candidate with identical seam digests but a different `transcript.js`, `text.js`, `settings-manager.js`… would match the premise and carry the derivation forward unsoundly. (Claims whose basis is entirely seam files remain reusable by `SEAM_FILES` in the ordinary way.) A future `C3_SEAM_EQUAL` against this profile must therefore either re-derive the listed ones or the design must be amended to name non-seam premise files — that is the genuine, forward-looking design gap, and it is **not** triggered by approving *this* candidate.

**Reviewer determination D-1 (flagged, not decided here).** If the reviewer reads the brief's instruction — *"if the frozen seam is no longer sufficient, report C5"* — as applying to *any* seam insufficiency regardless of re-derivability, the finding to adjudicate is this section. This document's position is the F-7 reading above: **C5 is not triggered for this candidate; the future-reuse restriction is recorded instead.** **Independent-review disposition: D-1 = ACCEPTED.**

### 9.1 Does each changed seam file still do what the genesis derivation said it does?

Re-derived at line level in Sec.5. In summary: `model-config.js`, `provider-composer.js`, `model-runtime.js`, `model-resolver.js` — yes (composition path unchanged in effect); `openai-completions.js`, `simple-options.js`, `models.js` — yes except `supportsStrictMode`; `sdk.js`, `agent-session.js`, `agent.js`, `agent-loop.js` — yes, with the transcript/tool-declaration restructuring; `system-prompt.js` — structurally changed (sections), effect on AIDO premises none; `rpc-mode.js` — yes, with `disposition` and `invocationName`; `main.js` — yes, flag set intact; `package.json` ×3 — identity facts intact (Sec.6).

### 9.2 Non-seam first-party modules imported by changed seam files

| Seam file | Non-seam first-party/third-party modules it imports (group) |
|---|---|
| `dist/cli.js` | `dist/cli/setup.js`[FP-I] |
| `dist/core/agent-session.js` | `dist/core/prompt-templates.js`[FP-I], `dist/core/extensions/runner.js`[FP-I], `dist/core/session-export.js`[FP-E], `dist/core/settings-manager.js`[FP-I], `dist/modes/interactive/theme/theme.js`[FP-E], `dist/core/extensions/index.js`[FP-I], `@ew/pi-ai/dist/compat.js`[FP-I], `dist/core/bash-executor.js`[FP-E], `dist/utils/tool-result-images.js`[FP-E], `dist/core/tools/index.js`[FP-E], `dist/core/export-html/index.js`[FP-E], `dist/core/compaction/index.js`[FP-E], `dist/core/export-html/tool-renderer.js`[FP-E], `dist/core/auth-guidance.js`[FP-E], `dist/core/usage-totals.js`[FP-E], `dist/core/virtual-models.js`[FP-I], `dist/utils/sleep.js`[FP-E], `dist/core/model-registry.js`[FP-E], `dist/core/messages.js`[FP-I], `@ew/pi-ai/dist/index.js`[FP-E], `dist/utils/frontmatter.js`[FP-E], `dist/core/bug-report.js`[FP-E], `dist/core/nested-tool-calls.js`[FP-E], `@ew/pi-agent-core/dist/index.js`[FP-E], `dist/core/source-info.js`[FP-I], `dist/core/tools/tool-definition-wrapper.js`[FP-I], `dist/core/tools/bash.js`[FP-E], `dist/utils/image-process.js`[FP-E], `dist/core/session-manager.js`[FP-I] |
| `dist/core/model-config.js` | `dist/utils/json.js`[FP-E], `node_modules/typebox/build/compile/index.mjs`[TP-E], `node_modules/typebox/build/index.mjs`[TP-E], `dist/utils/paths.js`[FP-I], `dist/utils/text.js`[FP-E] |
| `dist/core/model-resolver.js` | `@ew/pi-ai/dist/index.js`[FP-E], `dist/cli/args.js`[FP-I], `node_modules/minimatch/dist/esm/index.js`[TP-E], `node_modules/chalk/source/index.js`[TP-E] |
| `dist/core/model-runtime.js` | `dist/core/virtual-models.js`[FP-I], `dist/core/auth-storage.js`[FP-I], `@ew/pi-ai/dist/providers/all.js`[FP-E], `dist/core/models-store.js`[FP-I], `@ew/pi-ai/dist/utils/model-operations.js`[FP-E], `dist/core/remote-catalog-provider.js`[FP-E], `dist/config.js`[FP-I], `@ew/pi-ai/dist/index.js`[FP-E], `dist/core/runtime-credentials.js`[FP-E], `dist/utils/abort.js`[FP-E] |
| `dist/core/provider-composer.js` | `@ew/pi-ai/dist/utils/model-operations.js`[FP-E], `dist/core/resolve-config-value.js`[FP-I], `@ew/pi-ai/dist/compat.js`[FP-I], `@ew/pi-ai/dist/index.js`[FP-E] |
| `dist/core/sdk.js` | `dist/core/session-manager.js`[FP-I], `dist/core/virtual-models.js`[FP-I], `dist/core/timings.js`[FP-E], `dist/utils/paths.js`[FP-I], `dist/core/messages.js`[FP-I], `dist/core/settings-manager.js`[FP-I], `@ew/pi-ai/dist/compat.js`[FP-I], `dist/core/tools/index.js`[FP-E], `dist/core/resource-loader.js`[FP-I], `@ew/pi-agent-core/dist/index.js`[FP-E], `dist/config.js`[FP-I], `dist/core/provider-attribution.js`[FP-I], `dist/core/agent-session-runtime.js`[FP-I], `dist/core/auth-guidance.js`[FP-E], `dist/core/cache-warmer.js`[FP-I] |
| `dist/core/system-prompt.js` | `dist/core/skills.js`[FP-E], `dist/config.js`[FP-I], `@ew/pi-ai/dist/index.js`[FP-E] |
| `dist/main.js` | `dist/core/export-html/index.js`[FP-E], `dist/utils/paths.js`[FP-I], `dist/cli/project-trust.js`[FP-E], `dist/modes/interactive/theme/theme.js`[FP-E], `dist/modes/interactive/theme/theme-json.js`[FP-E], `dist/cli/auth-command.js`[FP-E], `dist/core/agent-session-runtime.js`[FP-I], `dist/package-manager-cli.js`[FP-E], `dist/cli/credential-print.js`[FP-E], `dist/config.js`[FP-I], `dist/extensions/index.js`[FP-I], `dist/core/session-manager.js`[FP-I], `dist/cli/session-picker.js`[FP-E], `@ew/pi-tui/dist/index.js`[FP-E], `dist/core/output-guard.js`[FP-I], `dist/core/http-dispatcher.js`[FP-I], `dist/extensions/mcp/cli.lazy.js`[FP-E], `dist/core/settings-manager.js`[FP-I], `dist/core/project-trust.js`[FP-I], `dist/core/agent-session-services.js`[FP-I], `dist/cli/auth-check.js`[FP-E], `dist/core/auth-storage.js`[FP-I], `node_modules/chalk/source/index.js`[TP-E], `dist/core/session-cwd.js`[FP-E], `dist/cli/args.js`[FP-I], `dist/utils/windows-self-update.js`[FP-I], `dist/core/settings-diagnostics.js`[FP-E], `@ew/pi-ai/dist/index.js`[FP-E], `dist/core/timings.js`[FP-E], `dist/cli/file-processor.js`[FP-E], `dist/modes/index.js`[FP-I], `dist/cli/startup-ui.js`[FP-E], `dist/cli/list-models.js`[FP-E], `dist/core/auth-guidance.js`[FP-E], `dist/core/trust-manager.js`[FP-I], `dist/cli/initial-message.js`[FP-E], `dist/migrations.js`[FP-I] |
| `dist/modes/rpc/rpc-mode.js` | `dist/modes/interactive/theme/theme.js`[FP-E], `dist/core/output-guard.js`[FP-I], `dist/modes/json-event.js`[FP-I], `dist/utils/shell.js`[FP-E] |
| `node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js` | `@ew/pi-agent-core/dist/stream-fn.js`[FP-E], `@ew/pi-ai/dist/index.js`[FP-E] |
| `node_modules/@earendil-works/pi-agent-core/dist/agent.js` | `@ew/pi-agent-core/dist/stream-fn.js`[FP-E], `@ew/pi-ai/dist/index.js`[FP-E] |
| `node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js` | `@ew/pi-ai/dist/utils/hash.js`[FP-L], `@ew/pi-ai/dist/utils/transcript.js`[FP-I], `@ew/pi-ai/dist/api/openai-prompt-cache.js`[FP-L], `node_modules/openai/index.mjs`[TP-L], `@ew/pi-ai/dist/utils/text.js`[FP-I], `@ew/pi-ai/dist/utils/error-body.js`[FP-L], `@ew/pi-ai/dist/api/constrained-sampling.js`[FP-I], `@ew/pi-ai/dist/utils/json-parse.js`[FP-E], `@ew/pi-ai/dist/utils/pi-user-agent.js`[FP-I], `@ew/pi-ai/dist/utils/sanitize-unicode.js`[FP-I], `@ew/pi-ai/dist/utils/provider-env.js`[FP-I], `@ew/pi-ai/dist/api/github-copilot-headers.js`[FP-L], `@ew/pi-ai/dist/utils/event-stream.js`[FP-E], `@ew/pi-ai/dist/utils/headers.js`[FP-L], `@ew/pi-ai/dist/utils/provider-retry.js`[FP-I], `@ew/pi-ai/dist/api/transform-messages.js`[FP-I] |
| `node_modules/@earendil-works/pi-ai/dist/api/simple-options.js` | `@ew/pi-ai/dist/utils/estimate.js`[FP-L] |
| `node_modules/@earendil-works/pi-ai/dist/models.js` | `@ew/pi-ai/dist/auth/resolve.js`[FP-E], `@ew/pi-ai/dist/utils/transcript.js`[FP-I], `@ew/pi-ai/dist/utils/model-operations.js`[FP-E], `@ew/pi-ai/dist/auth/credential-store.js`[FP-E], `@ew/pi-ai/dist/models-store.js`[FP-E], `@ew/pi-ai/dist/api/lazy.js`[FP-I], `@ew/pi-ai/dist/auth/context.js`[FP-I], `@ew/pi-ai/dist/utils/abort.js`[FP-E] |

(`~` = dynamic literal import; group codes as in 7.2.)

## 10. Request-building-change determination

**Determination: the request-building path changed.** Evidence: `openai-completions.js` is changed (seam); request context assembly moved to the transcript model (`agent-loop.js` `declareToolChanges`, `normalizeContext`, `resolveTranscript`, `getCurrentTools`); tool serialization changed behavior (`supportsStrictMode` default); the system-prompt text is assembled from sections; retries moved to `retryProviderRequest`; header construction gained `transformHeaders`/attribution. Per the PE design's minimum-evidence table, *E4 is required whenever the request-building path changed* — it did, in seam **and** non-seam files. See Sec.11.

**What did not change in effect (for AIDO):** the role rule, the effort rule, the presence/absence of the same set of request fields, the Pi-defaulted token cap rule, the default thinking level, the retry settings consumption, the stream/usage/store flags. The two sub-facts that *do* differ and are test-visible are F-1 (`strict`) and the transcript-shaped call convention (F-2).

## 11. E4 — REQUIRED, NOT EXECUTED

**E4 is required** (Sec.10). **E4 was not executed**, simulated, approximated or inferred in this phase: no `test_cfg1_pi_conformance.py` run, no `cfg1_t3_conformance.mjs` run, no Node, Pi, npm or JavaScript of any kind, and nothing in this document stands in for a T-3 result. `PE-4B` must authorize E4 separately, after this document is independently accepted.

**Static facts PE-4B will need (found by reading, not by running):**

1. *Harness call shape (F-2).* `cfg1_t3_conformance.mjs` calls `openai-completions.js` `streamSimple(model, {systemPrompt, messages, tools}, …)`. In the candidate that function expects a **transcript-shaped** context: `resolveTranscript`/`getCurrentSystemMessage` read system prompt and tools from system *messages*, and `getCurrentTools` from `toolsAdded`. Fed the old raw shape, the request would carry no instruction message and no `tools`, so T-3's role and tool assertions cannot be satisfied as written. A faithful offline harness must normalize the context (`normalizeContext`, exported from `pi-ai`) or drive `ModelRuntime`/`compat.streamSimple`. This is a **test-harness amendment**, not a change to a production consumer.
2. *Stale expectation (F-1).* `test_t3_the_shared_payload_shape_matches_the_source_derivation` asserts `strict is False` on every tool; the candidate emits no `strict` key.
3. *Module/API names still present:* `ModelConfig.load`, `composeModelProvider(providerId, base, modelConfig, extension)` (same signature), `provider.getModels()`, and `streamSimple` all exist with compatible shapes; the three module paths the harness imports exist at the same inventory-relative locations.
4. *Runtime prerequisite:* Node ≥ 22.19.0 (declared). Not established here.
5. *What E4 can and cannot show.* Offline request-shape conformance of the *composed model and request builder under injected transport*; it cannot observe the process launch, extension loading, RPC ordering, settle behavior, or backend behavior (those remain E5 / runtime gates).

These items are *inputs to a future authorization decision*; this document does not authorize any of them.

## 12. External-runtime residual statement

Everything in this review is a statement about the **profile-covered fact**: the bytes of the Pi package payload and its *declared* resolution boundary. The HPP-1 residual is **`NOT_IDENTIFIED_BY_PROFILE`**: nothing here identifies, pins or proves any of the following, and none of them is turned into a blocker unless a frozen CFG1 claim became mechanically false (none did):

- **Node itself** (`node.exe` is identity-pinned per proof, never byte-pinned; `engines >= 22.19.0` is declared, not verified here; **F-12**).
- **Undeclared upward resolution** — e.g. `require('supports-color')` in `debug` (declared only in `peerDependenciesMeta`; lazy-reachable) and the optional `bufferutil` / `utf-8-validate` (in the exposure list, observed absent).
- **Constructed-path loads** — `core/extensions/loader.js` `getAliases()` derives sibling workspace paths (`…/agent/dist/index.js`, `…/ai/dist/compat.js`, `…/tui/dist/index.js`) one level above the package root and prefers them if they exist; the install scope directory held only `pi-coding-agent` at review time (metadata listing, not authority).
- **Spawned processes and their descendants**, CJS global folders, and **configuration/extension discovery**, which are governed by CFG1's isolation and by H1/H2 at run time — not by the profile.
- **Real-home lookups** — `os.homedir()` resolves through the OS even when `HOME`/`USERPROFILE` are withheld; the only such lookups found on AIDO's flow are existence probes (Sec.7.3).

Nothing in this document may be cited as *complete runtime identity*.

## 13. Disposition: C3_SEAM_CHANGED vs C4 vs C5

| Class | Condition (brief / HPP-1) | Finding |
|---|---|---|
| **C4** | an AIDO-consumed behavioral contract actually changed *and* AIDO production code or `CFG1-CC1` must change | **Not established.** Every production-consumed fact re-derived holds: compat detection triggers (superset intact), per-arm effective role/effort (`ARM_EFFECTIVE`), declared compat shapes (`ARM_SHAPE`), default thinking level, `get_state`/`get_commands`/framing/ack/settle/event shapes, argv flags, env/settings consumption, retry consumption, extension acceptance. The two changed derived facts (F-1 `strict`, F-2 harness call shape) are asserted only in **test code** and CFG1 design prose; no production module reads them. Test-only amendment ≠ `CFG1-CC1` change (flagged **D-2/D-3** for reviewer confirmation). |
| **C5** | the current `PI-PC1`/`PI-SC1` contract cannot soundly express or support the candidate | **Not triggered** under HPP-1 F-7 (Sec.9): derivations were redone against hash-bound non-seam bytes; no claim reuses a seam premise it cannot support. A forward-looking reuse restriction is recorded (Sec.9) — **D-1**. |
| **C3_SEAM_CHANGED** | all required static evidence complete; no AIDO/CC1 code change; `PI-SC1` adequate *for its evidence-selector purpose*; no contract/bounds/layout condition requires C5 | **Static evidence is complete** (E1 ×31, E2, E3 15 026/15 026 files, adversarial review, sufficiency, request-building determination). `PI-SC1` is *inadequate as a self-contained derivation set* but adequate as the contract's selector once F-7's "redo the derivation" is applied. Approval **remains possible** as `C3_SEAM_CHANGED`, subject to PE-4B (E4) and the reviewer determinations D-1…D-3. |

**CFG1-CC1 / AIDO production code must change?** On the static evidence: **no**. **Test code** (the T-3 harness and one T-3 expectation) will need an explicitly authorized amendment before E4 can be meaningful (F-1, F-2). Per independent review (R-1) that is the harness amendment **plus** a separate exact-candidate qualification path carrying candidate-specific shape evidence; the ordinary generic expectation and the ordinary APS gate are not weakened.

**This document does not mark the profile approved, does not mark PE-5 complete, creates no approval record and no APS `r0002`.**

## 14. Unresolved findings

Severity: **A** = needs reviewer determination before PE-4B/PE-5; **B** = carry into PE-4B authorization; **C** = recorded, no action required for C3; **L** = carried live-launch blocker (does not block PE-4B request-builder E4; must be resolved before E5 / any full Pi CLI launch / PE-6).

| Id | Sev | Finding | Disposition / owner |
|---|:--:|---|---|
| F-1 | A (D-2) | `detectCompat` now defaults `supportsStrictMode:false`, so tool declarations carry **no** `strict` key (genesis: `strict:false`). Shared across arms; no contrast effect; asserted only in T-3 and CFG1 design §2.2/§3.4 prose. | Treat as expectation drift, not a CC1 change; the ordinary generic `strict is False` expectation is left unchanged (not widened to accept either shape) and PE-4B proves this candidate's shape separately (no `strict` key at all). **D-2 = ACCEPTED** (independent review). |
| F-2 | A (D-3) | T-3 harness passes the pre-transcript raw context shape; unmodified it cannot produce a faithful request on 1.0.3. | PE-4B must authorize a bounded, test-only harness amendment before E4. **D-3 = ACCEPTED WITH CORRECTION** (independent review): the amendment is test-only and not C4; the correction is that the candidate cannot be qualified through the ordinary APS-gated T-3 path at all — see **R-1**. |
| F-3 | A (D-1) | `PI-SC1` is not a self-contained derivation set for this candidate (non-seam files in derivation bases: see Sec.9); `SEAM_FILES` reuse cannot express them. | F-7 reading adopted (redo, don't reuse); **reuse restriction** recorded for PE-5/future candidates; design amendment needed only for future reuse. **D-1 = ACCEPTED** (independent review). |
| F-4 | B | System prompt gained a `docs` section embedding absolute Pi README/docs/examples paths (`PI_PACKAGE_DIR` can override). Arm-independent shared constant, but model-visible and operator-path-bearing. | Note for the CFG1 confounds list; not a CC1 change. |
| F-5 | L | Startup effects: Windows quarantine-root delete (`<enclosing node_modules>/.pi-native-quarantine`, a recursive delete outside both the payload and the AIDO workspace; absent now); `auth.json`/`models-store.json`/lock entries in the config dir; ADC-path existence probe under the OS home. | **Carried live-launch blocker** (promoted from "recorded, no action" by independent review). It does **not** block PE-4B request-builder E4, because E4 never enters the CLI/main startup path: the request-builder modules E4 loads (`model-config.js`, `provider-composer.js`, `openai-completions.js`, `transcript.js`) have a relative-import closure of 37 files that reaches none of `dist/main.js`, `dist/cli.js`, RPC mode, the extension loader or `dist/utils/windows-self-update.js` (static, regex-based, over hash-bound bytes; relative imports only — bare third-party specifiers such as `openai` were listed, not traversed; scratch analysis, not committed). It **must be resolved before E5 / any full Pi CLI launch / PE-6**. AIDO's recursive removal tolerating config-dir extras remains true but is not the resolution. |
| R-1 | A (reviewer) | **Candidate qualification authority gap.** The existing ordinary T-3 path requires the installed payload to be an eligible profile of the sealed APS head, but PE-4 qualification necessarily precedes PE-5 approval, so the PE-3 candidate can never satisfy that gate. | PE-4B requires a **separately bounded exact-candidate qualification path** — bound to the committed PE-3 candidate's pinned artifact bytes and re-derived facts, with a fresh complete no-follow `PI-PC1` observation before the one Node launch and again after it exits — while the **ordinary APS gate remains unchanged** (not weakened, bypassed, generalized to "candidate allowed", or replaced by a mode flag). R-1 does **not** alter the static `C3_SEAM_CHANGED` conclusion and is **not** C4/C5. |
| F-6 | C | Cache-warmer default `streaming` is inert only because the model object has no `promptCache` (an AIDO-owned input). | Latent coupling; re-open if `models.json` ever gains `promptCache`. |
| F-7 | C | Packaged `bin.pi` targets the **bundled** build `dist/bundle/cli.js`; AIDO launches unbundled `dist/cli.js`. No claim here covers `dist/bundle/**`. | Scope fact for PE-4B/E5 (they exercise the unbundled path only). |
| F-8 | B | Four built-in extensions are new; `--no-extensions` excluding them is a **static** derivation, and no AIDO runtime check asserts their absence (H1 proves only that the sentinel loaded; the `--tools` allowlist independently bars their tools). | Candidate item for E5/H1 hardening if the reviewer wants a runtime backstop. |
| F-9 | C | `get_commands` reports `invocationName`; a duplicate command name would suffix it and H1 would fail closed. | No action. |
| F-10 | C | A `length`-truncated assistant message now fails every tool call without executing it (events + `isError`). | OBS1/D-rule neutral (fewer broker ops than call ids is not a disagreement). |
| F-11 | C | `prompt` ack now carries `data.disposition`; AIDO reads only `success`. `handled`/`queued` cannot occur for AIDO's prompt (not `/…`, no `input` handler, not streaming). | No action. |
| F-12 | B | Node version/engine requirement (≥ 22.19.0) not established statically. | PE-4B prerequisite; HPP-1 residual. |
| F-13 | C | `supports-color` optional `require` in lazy-reachable `debug` is outside the declared-exposure list (peerDependenciesMeta only). | HPP-1 *undeclared upward resolution* residual; observed absent in the install scope. |

No finding is classified as blocking C3, C4 or C5 on the static evidence. **A** findings need an explicit reviewer acknowledgement before this evidence is relied on in PE-5. Independent review has now acknowledged D-1 (ACCEPTED), D-2 (ACCEPTED) and D-3 (ACCEPTED WITH CORRECTION → R-1). R-1 is a requirement on the PE-4B authority path, not a C4/C5 condition and not a change to the `C3_SEAM_CHANGED` floor; F-5 (L) blocks only E5 / any full Pi CLI launch / PE-6.

## Appendix A — Third-party and nested packages (140 manifests)

Columns: files = all inventory files owned by the package; js = JS files; **e/l/u** = eager / lazy-only / unreached JS files; importers = packages (or `(root)` = pi-coding-agent) whose reachable files import it; caps = capabilities present in its *reachable* files (c = child_process, n = net/http, w = fs write, d = non-literal import, e = eval-like, m = wasm/native, k = worker, r = createRequire, j = jiti, v = reads `process.env`, f = reads files, h = home-dir lookup); scripts = npm lifecycle scripts declared (never run).

The 140 rows are every manifest that is not a first-party package listed in Sec.6.1: real third-party packages, 5 example-extension packages under `examples/extensions/` (named `pi-extension-*`), and bare `{"type": …}` marker manifests inside packages (no `name`; shown by directory).

| Package | Version | Files | js | e/l/u | Importers (≤6) | caps | scripts |
|---|---|---:|---:|---|---|---|---|
| `pi-extension-custom-provider-anthropic` | 1.0.3 | 3 | 0 | 0/0/0 | — | — | — |
| `pi-extension-custom-provider-gitlab-duo` | 1.0.3 | 3 | 0 | 0/0/0 | — | — | — |
| `pi-extension-gondolin` | 1.0.3 | 3 | 0 | 0/0/0 | — | — | — |
| `pi-extension-sandbox` | 1.0.3 | 3 | 0 | 0/0/0 | — | — | — |
| `pi-extension-with-deps` | 1.0.3 | 3 | 0 | 0/0/0 | — | — | — |
| `@anthropic-ai/sdk` | 0.129.0 | 1753 | 388 | 0/129/259 | @earendil-works/pi-ai | cvfwhn | — |
| `@aws-sdk/client-bedrock-runtime` | 3.1127.0 | 109 | 36 | 0/0/36 | @earendil-works/pi-ai | — | — |
| `@aws-sdk/core` | 3.978.1 | 363 | 125 | 0/0/125 | @aws-sdk/client-bedrock-runtime, @aws-sdk/credential-provider-env, @aws-sdk/credential-provider-http, @aws-sdk/credential-provider-ini, @aws-sdk/credential-provider-login, @aws-sdk/credential-provider-process | — | — |
| `@aws-sdk/credential-provider-env` | 3.972.72 | 10 | 3 | 0/0/3 | @aws-sdk/credential-provider-ini, @aws-sdk/credential-provider-node | — | — |
| `@aws-sdk/credential-provider-http` | 3.972.74 | 27 | 9 | 0/0/9 | @aws-sdk/credential-provider-ini, @aws-sdk/credential-provider-node | — | — |
| `@aws-sdk/credential-provider-ini` | 3.973.17 | 34 | 11 | 0/0/11 | @aws-sdk/credential-provider-node | — | — |
| `@aws-sdk/credential-provider-login` | 3.972.79 | 15 | 5 | 0/0/5 | @aws-sdk/credential-provider-ini | — | — |
| `@aws-sdk/credential-provider-node` | 3.972.84 | 16 | 5 | 0/0/5 | @aws-sdk/client-bedrock-runtime, openai | — | — |
| `@aws-sdk/credential-provider-process` | 3.972.72 | 19 | 6 | 0/0/6 | @aws-sdk/credential-provider-ini, @aws-sdk/credential-provider-node | — | — |
| `@aws-sdk/credential-provider-sso` | 3.973.16 | 26 | 9 | 0/0/9 | @aws-sdk/credential-provider-ini, @aws-sdk/credential-provider-node | — | — |
| `@aws-sdk/token-providers` | 3.1138.0 | 37 | 12 | 0/0/12 | @aws-sdk/credential-provider-sso | — | — |
| `@aws-sdk/credential-provider-web-identity` | 3.972.78 | 13 | 4 | 0/0/4 | @aws-sdk/credential-provider-ini, @aws-sdk/credential-provider-node | — | — |
| `@aws-sdk/eventstream-handler-node` | 3.972.35 | 16 | 5 | 0/0/5 | @aws-sdk/client-bedrock-runtime | — | — |
| `@aws-sdk/middleware-eventstream` | 3.972.30 | 19 | 6 | 0/0/6 | @aws-sdk/client-bedrock-runtime | — | — |
| `@aws-sdk/middleware-websocket` | 3.972.54 | 37 | 12 | 0/0/12 | @aws-sdk/client-bedrock-runtime | — | — |
| `@aws-sdk/nested-clients` | 3.997.46 | 357 | 124 | 0/0/124 | @aws-sdk/credential-provider-ini, @aws-sdk/credential-provider-login, @aws-sdk/credential-provider-sso, @aws-sdk/credential-provider-sso/@aws-sdk/token-providers, @aws-sdk/credential-provider-web-identity, @aws-sdk/token-providers | — | — |
| `@aws-sdk/signature-v4-multi-region` | 3.996.47 | 16 | 5 | 0/0/5 | @aws-sdk/nested-clients | — | — |
| `@aws-sdk/token-providers` | 3.1127.0 | 37 | 12 | 0/0/12 | @aws-sdk/client-bedrock-runtime | — | — |
| `@aws-sdk/types` | 3.974.6 | 124 | 41 | 0/0/41 | — | — | — |
| `@aws-sdk/xml-builder` | 3.972.41 | 28 | 9 | 0/0/9 | @aws-sdk/core | — | — |
| `@aws/lambda-invoke-store` | 0.3.0 | 7 | 2 | 0/0/2 | @aws-sdk/core | — | — |
| `@babel/runtime` | 7.29.7 | 126 | 123 | 0/0/123 | — | — | — |
| `node_modules/@babel/runtime/helpers/esm` | — | 123 | 122 | 0/0/122 | — | — | — |
| `@esbuild/win32-x64` | 0.28.2 | 3 | 0 | 0/0/0 | — | — | — |
| `@google/genai` | 2.21.0 | 23 | 9 | 0/1/8 | @earendil-works/pi-ai | vwn | preinstall,prepare |
| `@google/genai/node` | — | 1 | 0 | 0/0/0 | — | — | — |
| `@google/genai/web` | — | 1 | 0 | 0/0/0 | — | — | — |
| `@protobufjs/aspromise` | 1.1.2 | 6 | 2 | 0/0/2 | @protobufjs/fetch, protobufjs | — | — |
| `@protobufjs/base64` | 1.1.2 | 6 | 2 | 0/0/2 | protobufjs | — | — |
| `@protobufjs/codegen` | 2.0.5 | 6 | 2 | 0/0/2 | protobufjs | — | — |
| `@protobufjs/eventemitter` | 1.1.1 | 7 | 2 | 0/0/2 | protobufjs | — | — |
| `@protobufjs/fetch` | 1.1.1 | 9 | 3 | 0/0/3 | protobufjs | — | — |
| `@protobufjs/float` | 1.0.2 | 8 | 4 | 0/0/4 | protobufjs | — | — |
| `@protobufjs/path` | 1.1.2 | 6 | 2 | 0/0/2 | protobufjs | — | — |
| `@protobufjs/pool` | 1.1.0 | 7 | 2 | 0/0/2 | protobufjs | — | — |
| `@protobufjs/utf8` | 1.1.2 | 9 | 2 | 0/0/2 | protobufjs | — | — |
| `@silvia-odwyer/photon-node` | 0.3.4 | 7 | 2 | 0/1/1 | (root) | efm | — |
| `@smithy/core` | 3.35.1 | 1109 | 387 | 0/0/387 | @aws-sdk/client-bedrock-runtime, @aws-sdk/core, @aws-sdk/credential-provider-env, @aws-sdk/credential-provider-http, @aws-sdk/credential-provider-ini, @aws-sdk/credential-provider-login | — | — |
| `@smithy/credential-provider-imds` | 4.5.2 | 56 | 18 | 0/0/18 | @aws-sdk/credential-provider-ini, @aws-sdk/credential-provider-node | — | — |
| `@smithy/fetch-http-handler` | 5.8.0 | 17 | 5 | 0/0/5 | @aws-sdk/client-bedrock-runtime, @aws-sdk/credential-provider-http, @aws-sdk/middleware-websocket, @aws-sdk/nested-clients | — | — |
| `@smithy/node-http-handler` | 4.12.1 | 56 | 18 | 0/0/18 | @aws-sdk/client-bedrock-runtime, @aws-sdk/credential-provider-http, @aws-sdk/nested-clients, @earendil-works/pi-ai | — | — |
| `@smithy/signature-v4` | 5.7.4 | 47 | 15 | 0/0/15 | @aws-sdk/core, @aws-sdk/signature-v4-multi-region, openai | — | — |
| `@smithy/types` | 4.19.0 | 224 | 74 | 0/0/74 | @aws-sdk/types, @smithy/core | — | — |
| `@stablelib/base64` | 1.0.1 | 15 | 3 | 0/1/2 | standardwebhooks | — | — |
| `@types/node` | 26.6.4 | 92 | 0 | 0/0/0 | — | — | — |
| `@types/retry` | 0.12.0 | 4 | 0 | 0/0/0 | — | — | — |
| `agent-base` | 9.0.0 | 11 | 2 | 0/0/2 | http-proxy-agent, https-proxy-agent | — | — |
| `balanced-match` | 4.0.4 | 3 | 0 | 0/0/0 | — | — | prepare |
| `node_modules/balanced-match/dist/commonjs` | — | 5 | 1 | 0/0/1 | brace-expansion/dist/commonjs | — | — |
| `node_modules/balanced-match/dist/esm` | — | 5 | 1 | 1/0/0 | brace-expansion/dist/esm | — | — |
| `base64-js` | 1.5.1 | 6 | 2 | 0/1/1 | google-auth-library | — | — |
| `bignumber.js` | 9.3.1 | 10 | 2 | 0/1/1 | json-bigint | — | — |
| `bowser` | 2.14.1 | 14 | 10 | 0/0/10 | @aws-sdk/core | — | — |
| `brace-expansion` | 5.0.12 | 3 | 0 | 0/0/0 | — | — | prepare |
| `node_modules/brace-expansion/dist/commonjs` | — | 5 | 1 | 0/0/1 | minimatch/dist/commonjs | — | — |
| `node_modules/brace-expansion/dist/esm` | — | 5 | 1 | 1/0/0 | minimatch/dist/esm | — | — |
| `buffer-equal-constant-time` | 1.0.1 | 7 | 2 | 0/1/1 | jwa | — | — |
| `chalk` | 6.0.0 | 12 | 5 | 3/0/2 | (root), @protobufjs/float | — | — |
| `cross-spawn` | 7.0.6 | 9 | 6 | 6/0/0 | (root), @earendil-works/pi-mcp | cv | — |
| `data-uri-to-buffer` | 4.0.1 | 6 | 1 | 0/1/0 | node-fetch | — | — |
| `debug` | 4.4.3 | 7 | 4 | 0/4/0 | gaxios/https-proxy-agent, http-proxy-agent, https-proxy-agent | v | — |
| `diff` | 8.0.4 | 8 | 3 | 0/0/3 | — | — | — |
| `node_modules/diff/libcjs` | — | 64 | 21 | 0/0/21 | — | — | — |
| `node_modules/diff/libesm` | — | 64 | 21 | 19/0/2 | (root) | — | — |
| `ecdsa-sig-formatter` | 1.0.11 | 7 | 2 | 0/2/0 | google-auth-library, jwa | — | — |
| `esbuild` | 0.28.2 | 7 | 2 | 0/0/2 | @earendil-works/chord | — | postinstall |
| `extend` | 3.0.2 | 10 | 1 | 0/1/0 | gaxios, gaxios/build/esm | — | — |
| `fast-sha256` | 1.3.0 | 6 | 2 | 0/1/1 | standardwebhooks | — | — |
| `fetch-blob` | 3.2.0 | 10 | 4 | 0/4/0 | formdata-polyfill, node-fetch | f | — |
| `formdata-polyfill` | 4.0.10 | 8 | 4 | 0/1/3 | node-fetch | — | — |
| `gaxios` | 7.3.1 | 40 | 12 | 0/6/6 | gaxios/build/esm, gcp-metadata, google-auth-library | vn | prepare |
| `node_modules/gaxios/build/esm` | — | 38 | 12 | 0/0/12 | gaxios | — | — |
| `agent-base` | 7.1.4 | 11 | 2 | 0/2/0 | gaxios/https-proxy-agent | n | — |
| `https-proxy-agent` | 7.0.6 | 11 | 2 | 0/2/0 | gaxios, gaxios/build/esm | n | — |
| `gcp-metadata` | 8.1.2 | 9 | 2 | 0/2/0 | google-auth-library | vf | prepare |
| `get-east-asian-width` | 1.6.0 | 8 | 4 | 4/0/0 | @earendil-works/pi-tui | — | — |
| `google-auth-library` | 10.9.1 | 95 | 46 | 0/44/2 | @google/genai | cvfhn | prepare |
| `google-logging-utils` | 1.1.3 | 15 | 4 | 0/3/1 | gcp-metadata, google-auth-library | v | prepare |
| `graceful-fs` | 4.2.11 | 7 | 4 | 4/0/0 | proper-lockfile | vfw | — |
| `grok-mermaid` | 0.2.3 | 64 | 12 | 11/0/1 | (root) | — | — |
| `highlight.js` | 10.7.3 | 398 | 194 | 22/171/1 | (root) | fwhn | — |
| `hosted-git-info` | 9.0.3 | 7 | 4 | 4/0/0 | (root) | n | — |
| `http-proxy-agent` | 9.1.0 | 7 | 1 | 0/0/1 | @earendil-works/pi-ai | — | — |
| `https-proxy-agent` | 9.1.0 | 11 | 2 | 0/0/2 | @earendil-works/pi-ai | — | — |
| `ignore` | 7.0.8 | 6 | 2 | 1/0/1 | (root) | — | — |
| `isexe` | 2.0.0 | 8 | 4 | 3/0/1 | which | vf | — |
| `jiti` | 2.7.0 | 16 | 9 | 0/4/5 | (root) | rdvfwjm | — |
| `json-bigint` | 1.0.0 | 6 | 3 | 0/3/0 | gcp-metadata | — | — |
| `json-schema-to-ts` | 3.1.1 | 267 | 132 | 0/0/132 | — | — | — |
| `jwa` | 2.0.1 | 5 | 1 | 0/1/0 | jws | — | — |
| `jws` | 4.0.1 | 10 | 5 | 0/5/0 | google-auth-library | — | — |
| `long` | 5.3.2 | 6 | 1 | 0/0/1 | — | — | — |
| `node_modules/long/umd` | — | 4 | 1 | 0/0/1 | protobufjs | — | — |
| `lru-cache` | 11.5.3 | 3 | 0 | 0/0/0 | — | — | prepare |
| `node_modules/lru-cache/dist/commonjs` | — | 55 | 15 | 1/0/14 | hosted-git-info | n | — |
| `node_modules/lru-cache/dist/esm` | — | 55 | 15 | 0/0/15 | — | — | — |
| `marked` | 18.0.11 | 12 | 4 | 1/0/3 | @earendil-works/pi-tui | — | — |
| `minimatch` | 10.2.6 | 3 | 0 | 0/0/0 | — | — | prepare |
| `node_modules/minimatch/dist/commonjs` | — | 25 | 6 | 0/0/6 | — | — | — |
| `node_modules/minimatch/dist/esm` | — | 25 | 6 | 6/0/0 | (root) | v | — |
| `ms` | 2.1.3 | 4 | 1 | 0/1/0 | debug | — | — |
| `node-domexception` | 1.0.0 | 42 | 25 | 0/1/24 | fetch-blob | k | — |
| `node-fetch` | 3.3.2 | 17 | 13 | 0/13/0 | gaxios, gaxios/build/esm | n | — |
| `openai` | 7.19.0 | 3548 | 787 | 0/199/588 | @earendil-works/pi-ai | cvn | — |
| `p-retry` | 4.6.2 | 5 | 1 | 0/1/0 | @google/genai | — | — |
| `partial-json` | 0.1.7 | 9 | 2 | 2/0/0 | @earendil-works/pi-ai | — | — |
| `path-key` | 3.1.1 | 5 | 1 | 1/0/0 | cross-spawn | v | — |
| `proper-lockfile` | 4.1.2 | 8 | 4 | 4/0/0 | (root) | w | — |
| `retry` | 0.12.0 | 17 | 10 | 3/0/7 | proper-lockfile | — | — |
| `protobufjs` | 7.6.6 | 79 | 48 | 0/0/48 | @google/genai | — | postinstall |
| `proxy-agent-negotiate` | 1.1.0 | 5 | 1 | 0/0/1 | http-proxy-agent, https-proxy-agent | — | — |
| `quickjs-wasi` | 3.6.2 | 25 | 4 | 0/0/4 | @earendil-works/pi-codemode | — | — |
| `retry` | 0.13.1 | 8 | 5 | 0/3/2 | p-retry | — | — |
| `safe-buffer` | 5.2.1 | 5 | 1 | 0/1/0 | ecdsa-sig-formatter, jwa, jws | — | — |
| `semver` | 7.8.5 | 53 | 49 | 46/0/3 | (root) | v | — |
| `shebang-command` | 2.0.0 | 4 | 1 | 1/0/0 | cross-spawn | — | — |
| `shebang-regex` | 3.0.0 | 5 | 1 | 1/0/0 | shebang-command | — | — |
| `signal-exit` | 3.0.7 | 5 | 2 | 2/0/0 | proper-lockfile | — | — |
| `standardwebhooks` | 1.1.1 | 8 | 2 | 0/2/0 | @anthropic-ai/sdk | — | prepare |
| `ts-algebra` | 2.0.0 | 104 | 49 | 0/0/49 | — | — | — |
| `tslib` | 2.8.1 | 11 | 3 | 0/0/3 | tslib/modules | — | — |
| `node_modules/tslib/modules` | — | 3 | 1 | 0/0/1 | — | — | — |
| `typebox` | 1.3.27 | 1385 | 691 | 668/0/23 | (root), @earendil-works/pi-ai | — | — |
| `undici` | 8.10.2 | 214 | 112 | 110/0/2 | (root), openai | vfwnmk | prepare |
| `undici-types` | 8.9.0 | 48 | 0 | 0/0/0 | — | — | — |
| `web-streams-polyfill` | 3.3.3 | 38 | 15 | 0/1/14 | fetch-blob | — | prepare |
| `web-streams-polyfill-es2018` | — | 1 | 0 | 0/0/0 | — | — | — |
| `web-streams-polyfill-es6` | — | 1 | 0 | 0/0/0 | — | — | — |
| `web-streams-ponyfill` | — | 1 | 0 | 0/0/0 | — | — | — |
| `web-streams-ponyfill-es2018` | — | 1 | 0 | 0/0/0 | — | — | — |
| `web-streams-ponyfill-es6` | — | 1 | 0 | 0/0/0 | — | — | — |
| `which` | 2.0.2 | 6 | 1 | 1/0/0 | cross-spawn | v | — |
| `ws` | 8.22.0 | 19 | 16 | 0/14/2 | @google/genai, openai | vn | — |
| `yaml` | 2.9.0 | 158 | 77 | 72/0/5 | (root) | v | — |
| `node_modules/yaml/browser` | — | 75 | 74 | 0/0/74 | — | — | — |

## Appendix B — Reproducibility: the partition and graph rules

**Inventory source.** `…/pi_profile_candidates/66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc.inventory.json` (16 482 entries).

**Packages and ownership.** Every `package.json` in the bundle defines a package directory; a file is owned by the deepest package directory that is a path prefix of it. First-party = the root, the seven `node_modules/@earendil-works/*` packages present (`chord`, `pi-agent-core`, `pi-ai`, `pi-codemode`, `pi-mcp`, `pi-telemetry`, `pi-tui`), and `examples/plugins/pi-example-plugin`.

**Module graph.** For every `.js/.mjs/.cjs` file: strip block comments and full-line `//` comments; extract specifiers from `import … from "x"`, `export … from "x"`, bare `import "x"`, `import("x")` (literal), `require("x")` (literal). Resolve: relative → exact inventory path (ESM) or Node CJS file/extension/index rules; bare → walk up `node_modules` ancestors inside the payload, honour `exports` (conditions `import`,`node`,`default` for ESM; `require`,`node`,`default` for CJS, with `*` patterns), then `main`/`module`; `#imports` via the package `imports` map. Built-ins and unresolved specifiers are recorded, not followed. Entry anchor: `dist/cli.js`. *Eager* = closure over static and `require` edges; *lazy* = additional files via literal dynamic `import()`.

**Partition (first match wins).** (1) basename `package.json` → M1; (2) extension in {.node,.so,.dll,.dylib,.wasm,.exe} → N1; (3) `.d.ts/.d.mts/.d.cts` → D1; (4) `.map` → D2; (5) `.js/.mjs/.cjs`: first-party → FP-I (explicit list, 8.1) / FP-E / FP-L / FP-U by reachability; third-party → TP-I (`openai/client.mjs`) / TP-E / TP-L / TP-U; (6) `.ts/.mts/.cts/.tsx` → D3; (7) `.md/.txt/.markdown/.rst` or basename LICENSE/NOTICE/README/CHANGELOG/AUTHORS/COPYING… → D4; (8) images and `.css/.scss/.html` → D6; (9) `.sh/.cmd/.ps1/.bat`, or extensionless under `bin/` or `node_modules/.bin/` → D7; (10) path in the set of non-JS targets of literal edges from reachable files (all JSON imported with `with {type:"json"}`) → D5R; (11) dotfiles, `Makefile`, `CODEOWNERS`, and `.json/.yml/.yaml/.proto/.bnf/.jsdoc/.tsbuildinfo/.m/.c/.h/.keep/.1/.eslintrc/.eslintignore/.npmignore/.editorconfig/.nvmrc` → D5; (12) residual → D8 (matched 0 files).

**Capability scan.** Per reachable JS file, regular-expression presence of: `child_process|spawn|spawnSync|execSync|execFile|fork(|cross-spawn`; `http|https|http2|net|tls|dgram|dns` module specifiers, `fetch(`, `undici`, `WebSocket`, SDK constructors; fs write/create calls; `process.env`; `homedir|USERPROFILE|APPDATA|XDG_*|HOME`; non-literal `import(`; `eval(|new Function(|vm.`; `WebAssembly|.wasm|.node|process.dlopen|quickjs`; `worker_threads|new Worker(`; `createRequire`; `jiti`.

**What was executed during analysis:** Python 3 (standard library + accepted AIDO modules `pi_fs_leaves`, `pi_identity`, `pi_payload`, `pi_manifest`, `pi_profile_floor`, `pi_profile_policy_loader`), `git show`/`git status`/`git diff --check`, and directory metadata listings of the install scope. **Not executed:** Node, Pi, npm, any installed JavaScript, any T-3/E4 command.

## Appendix C — Legend: files cited in Sec.5 (all hash-bound to the committed inventory)

| Label | Payload-relative path | Seam | SHA-256 |
|---|---|---|---|
| `cli.js` | `dist/cli.js` | U | `8189b66abc4f9f431dbb70941dcba690d76d040de1fbfff212886be35a53639d` |
| `args.js` | `dist/cli/args.js` | — | `f48f91efc303fc7b826f0ce02ba6eb70fcc271d31671f0f68f562fdd8c6885e6` |
| `setup.js` | `dist/cli/setup.js` | — | `4a2a7a0dbf82e2e5d18cec90896b36cbedce78b3d09e78d4040ac94fa3fbeba8` |
| `config.js` | `dist/config.js` | — | `b53418ca3bc54b70e18ccb192eb471696f5211c5aa2e80d68fe6fe3851ff23ae` |
| `agent-session.js` | `dist/core/agent-session.js` | C | `35ca1dabd54d98c236c9601b569c2856b726ade392d06b2eaaf50158f48913ab` |
| `cache-warmer.js` | `dist/core/cache-warmer.js` | — | `9c4b000930d6d3c567073102f6b6a52660110bb0f79cf78dd72c4dd1ebc87fc0` |
| `defaults.js` | `dist/core/defaults.js` | U | `13196dce2ddb143f6f4c28af2e34374f84004e50c7b71ba7b900e1acf84479b6` |
| `loader.js` | `dist/core/extensions/loader.js` | — | `44a356da552c9cf2ea619c61944cfb28f81b45f09b325f152c91a914bfce1bc0` |
| `runner.js` | `dist/core/extensions/runner.js` | — | `258f142bc56cc84d953ef6146222e5ff3a94cc908592a1b3d075d34bbcd68b36` |
| `model-config.js` | `dist/core/model-config.js` | C | `24a0e0f98672766e16e00d9f61587f50f9481915581156ae71a14e48ee912e4c` |
| `model-resolver.js` | `dist/core/model-resolver.js` | C | `66a7c13b8aff81e09e4a25327ab17ab245d7217799727c6b01863b86e7b87ed3` |
| `model-runtime.js` | `dist/core/model-runtime.js` | C | `da26f76339a031456f6d239a249159231776f760ab4ac538c6b54c417dea6f67` |
| `output-guard.js` | `dist/core/output-guard.js` | — | `e860db94650c57e07582c300983671737bf9e796682193b498f75e3dd72e9024` |
| `package-manager.js` | `dist/core/package-manager.js` | — | `cfd718348caadc3b74df206e9af417afb9f409cdd7b508891eb7608c21fade80` |
| `provider-attribution.js` | `dist/core/provider-attribution.js` | — | `da98e466cbaacad5d2ccdf6d37b650580e81691f2ebe7f3ca3fb04c62fc83a73` |
| `provider-composer.js` | `dist/core/provider-composer.js` | C | `b088d1babb75360da6bf1bcbe8e140ce600e1db15f51345f1965d3d1e9f267ef` |
| `resolve-config-value.js` | `dist/core/resolve-config-value.js` | — | `01fdb1673990635bb419c7418eefa298b6a1c6fbb3c6193d3b05a4902e51992d` |
| `resource-loader.js` | `dist/core/resource-loader.js` | — | `710e367e37c40df9f8f0239ebee6955e0a971a028d20467024bf4ea9ff55a42a` |
| `sdk.js` | `dist/core/sdk.js` | C | `fe643170de3d259c7e06179d9e18270a009dfb54df915f6e3de515425b8d009b` |
| `settings-manager.js` | `dist/core/settings-manager.js` | — | `b3a424ac1af9bd0c380796f9e5d812e2c61755ed3b31dd39982a57bbe0d5a391` |
| `source-info.js` | `dist/core/source-info.js` | — | `67562eea112e99f4a7880913143730bd90e3655381c0f353e3dd18c5e9f1ef07` |
| `system-prompt.js` | `dist/core/system-prompt.js` | C | `83aa42fae07830d5a73431935af3390ec397d8333269d75cfe49c1afbc55369c` |
| `telemetry.js` | `dist/core/telemetry.js` | — | `e8c06bed2c216daeca853468232268f973f542156d231fa4ed68499a9f4946b5` |
| `tool-definition-wrapper.js` | `dist/core/tools/tool-definition-wrapper.js` | — | `02fe785c52294d14216605d40d5592ac2accd1a3125891523e2a6c87feb5810c` |
| `main.js` | `dist/main.js` | C | `060521b0b81f91948d8ded9139e423e5d0c9e6808a45c81750cc30519de4d2db` |
| `json-event.js` | `dist/modes/json-event.js` | — | `5f3756470739fa4a1595feeaf1ce2dfd29e36a2cffd9e642f914fc23f540d606` |
| `jsonl.js` | `dist/modes/rpc/jsonl.js` | U | `049a9f8ca4242c79f1911ed977949e8d8906b4561f424c2729687f426fabaacf` |
| `rpc-mode.js` | `dist/modes/rpc/rpc-mode.js` | C | `631697cd35928fc827f4a423538c43ff227b8cbf63c2a2f11060616f55eba6db` |
| `agent-loop.js` | `node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js` | C | `65def8c7f3fa01e38fe05467520efc8673c22ea8197833a3b04b29c8a60cb1e3` |
| `agent.js` | `node_modules/@earendil-works/pi-agent-core/dist/agent.js` | C | `163ad28551f1c38b8eb899a5c9dd89cd9d9005fb7dd9c4abeb008ee380e98c51` |
| `constrained-sampling.js` | `node_modules/@earendil-works/pi-ai/dist/api/constrained-sampling.js` | — | `3364d03ce8f7ef17ac336e35a134bf3b3b7582430a3841ac78bbf5ca216010d0` |
| `openai-completions.js` | `node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js` | C | `5a79cc5aa41dee180692695e65771720d1ea556e9a978649dc2040278be51753` |
| `openai-completions.lazy.js` | `node_modules/@earendil-works/pi-ai/dist/api/openai-completions.lazy.js` | — | `a3d37d272ed600ddae2a9b05884e1c11c65487c1d8aa30d0b19ba571ffc7ea76` |
| `simple-options.js` | `node_modules/@earendil-works/pi-ai/dist/api/simple-options.js` | C | `9b3cc0ae6daa86fdc050bc0cb0f3f986401e64ccddbde6757183c9f8ad411be2` |
| `transform-messages.js` | `node_modules/@earendil-works/pi-ai/dist/api/transform-messages.js` | — | `9d747a3d64c533f7bfaf2a66e8446dc006086559d364a09d4c51d1c8c9c332e5` |
| `compat.js` | `node_modules/@earendil-works/pi-ai/dist/compat.js` | — | `df55dca273cb2a7053187b7b29d0fe5b91966a5099ab02d2efe38bb31c3f9738` |
| `models.js` | `node_modules/@earendil-works/pi-ai/dist/models.js` | C | `633161a0067abbb20a434acc3605f8f25d2fa6d32f903cc7edcdcaa7e0ba7083` |
| `provider-retry.js` | `node_modules/@earendil-works/pi-ai/dist/utils/provider-retry.js` | — | `4aa5c34d72f58d3cb67bc8b71c486f11237cda02c86889e7a67c20d6418c35a9` |
| `text.js` | `node_modules/@earendil-works/pi-ai/dist/utils/text.js` | — | `95037d5b787075ffb951cdeaf3b93aeb89735d10b31b82e19d2921f505ac2b04` |
| `transcript.js` | `node_modules/@earendil-works/pi-ai/dist/utils/transcript.js` | — | `4c772c6691be0c5b4c308a09e3eeaa4d965b59e39652442b3aef0600ffb5fccb` |

*End of PE-4A evidence document.*
