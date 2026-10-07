# PE-4B — E4 Qualification Execution Evidence

**Status: EVIDENCE ONLY. This document approves nothing.**

E4 PASS does **not** approve the candidate. It grants no APS eligibility, no live
authority and no PE-5 approval. PE-5 remains separately unauthorized pending
independent acceptance of this evidence.

## 1. Bindings

| Item | Value |
| --- | --- |
| AIDO source commit (PE-4B runner) | `455b96f06c23364b80852cf877a07d520d1791df` |
| PE-3 source commit (candidate) | `d7bdb230599a6c9e2d0948378529cabfec6e6948` |
| payload fingerprint | `66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc` |
| profile id | `56651d0b2b6995e05b6de3aa012f5a82f276b2ac817dcce00844d1db2a9ffd67` |
| qualification floor | `C3_SEAM_CHANGED` |
| consumer contract | `CFG1-CC1` |
| policy revision | `HPP-1` |
| candidate status | `NON_AUTHORITY_CANDIDATE` (unchanged) |

Candidate identity comes **only** from the Python PRE_LAUNCH and POST_EXIT PI-PC1
observations. The Node-generated report is not an authority for candidate
identity, and the report hash below is provenance only — it is not candidate
identity.

## 2. How it was executed

- Pre-execution gate (read-only Git): `HEAD` equal to the source commit above;
  `git status --short` empty; the three committed blobs below matched, both as
  committed and as hashed in the working tree:
  - `experiments/pi_harness_cfg1/tests/cfg1_t3_conformance.mjs` → `0379cfa401998f67ff96b1a7b1dcc8f47e3ddc4f`
  - `experiments/pi_harness_cfg1/tests/test_cfg1_pi_conformance.py` → `70b814626292d96e444b55a871678faf4b29ec57`
  - `experiments/pi_harness_cfg1/tests/test_cfg1_pe4b_candidate_qualification.py` → `9509f4dbc55857cbd3395c94f072db6e14c20534`
- The committed, unmodified `_run_candidate_e4` was called **exactly once** by a
  temporary one-shot Python caller kept **outside** the repository. The caller
  supplied only a minimal `mktemp`-like object whose work directories were
  created outside the repository. It patched nothing, passed no candidate
  identity/path/fingerprint/profile parameter, and did not alter `PATH`.
- No pytest test or fixture executed the launcher, and no repository file was
  modified to make it callable.
- The function **returned normally**. That is the only PASS condition: it means
  the frozen runner completed exact committed-candidate loading, a fresh
  PRE_LAUNCH PI-PC1 observation, exposure-absence and root/node identity checks,
  the frozen harness execution, network/DNS interception, the in-process Node
  engine floor, request-builder execution through the synthetic transport, a
  fresh POST_EXIT PI-PC1 observation, and the candidate-specific request-shape
  evidence checks.

## 3. Result

**E4 = PASS** (for this single bounded execution only).

Deterministic report SHA-256 (provenance only; JSON serialized with sorted keys,
compact separators, ASCII-escaped, UTF-8):

```text
2183b48c9f80afed021a9c82bd62ab7b2e1814784d8f9c19d8d6de6354b750db
```

## 4. Sanitized summary of the returned report

- **Arm set:** `Q`, `R`, `E`, `H`, `CONTROL_EMPTY`, `CONTROL_EXPLICIT_TRUE`
  (six arms).
- **Fetch calls:** 6, every one to the synthetic endpoint
  `http://cfg1-conformance.invalid/v1/chat/completions`. Every arm reports
  `fetchCallsForThisArm = 1`, i.e. each arm used the injected transport exactly
  once.
- **Q/R role contrast:** passed. `Q` (no compat override) sends the system
  message with role `developer`; `R` (`supportsDeveloperRole: false`) sends
  `system`. Both send `reasoning_effort`.
- **Q/E reasoning_effort contrast:** passed. `Q` sends `reasoning_effort`
  (`medium`); `E` (`supportsReasoningEffort: false`) sends none, with the role
  unchanged (`developer`).
- **H combined contrast:** passed. `H` (both overrides off) sends role `system`
  and no `reasoning_effort`.
- **Controls:** `CONTROL_EMPTY` (empty compat) and `CONTROL_EXPLICIT_TRUE`
  (both flags explicitly true) were each request-identical to `Q`.
- **Tools:** identity, order and schema passed — `aido_read`, then `aido_edit`,
  identical in every arm. The Pi 1.0.3 candidate tool declarations contained
  **no `strict` key**.
- **Request envelope:** every arm carried the same remaining keys (`model`,
  `messages`, `stream`, `stream_options`, `store`, `max_completion_tokens`,
  `tools`, plus `reasoning_effort` only where not suppressed).
- **Endpoint:** synthetic `.invalid` host only.
- **Network/DNS:** `violations` was empty. `failedToInstall` was empty; the
  interception was installed for `globalThis.fetch`, `net.connect`,
  `net.createConnection`, `tls.connect`, `http.request`, `https.request`, and
  the `dns.*` and `dns.promises.*` lookup/resolve entry points (36 hooks).
- **Candidate PRE and POST observations:** both passed.
- **Node engine floor:** the harness's own in-process Node >=22.19.0 gate
  passed. No separate `node`/`pi`/`npm` version or help probe was run, and
  Node is not profile-byte-pinned.

## 5. What did and did not run

- E4 **executed candidate code** under this one-shot authorization: one Node
  process created by the frozen runner loaded the installed Pi candidate's
  request-builder modules (ModelConfig, `composeModelProvider`, `streamSimple`,
  `normalizeContext`) behind the frozen synthetic transport.
- **No** Pi CLI, `main`, RPC mode, extension loading, or Pi agent/model session
  ran. E5, E6, PE-5, PE-6 and A4 did not run.
- **No** backend, model, provider or B300 contact occurred. Only the synthetic
  `.invalid` transport was used, and no real network or DNS was performed.
- **No** real credential or endpoint value was read.
- No policy, APS, candidate artifact, production code, frozen design, `CLAUDE.md`
  or roadmap was modified, and no APS approval or revision was created.

## 6. Residuals and standing blockers

- **A→B→A residual (accepted, not closed):** the candidate was observed at
  PRE_LAUNCH and again at POST_EXIT. A change that is reverted between the two
  observations is not detectable by comparing them, so **continuity between the
  observations is not claimed**. This is the already-accepted residual.
- **Node** is not pinned by profile bytes; only the frozen in-process engine
  floor was proven.
- **PE-4A F-5** (full-startup filesystem-delete finding) is outside the E4
  request-builder path and **still blocks** E5, full Pi launch and PE-6. Nothing
  here enters `main`/CLI startup.
- **PE-5 remains separately unauthorized** pending independent acceptance of
  this evidence. The candidate is not approved, and E4 must not be rerun on the
  strength of this document.
