# Phase 5F3B-I2A-DESIGN-FU3 — Category-B Observability Truth and Synthetic Workspace Authority

## CURRENT STATUS (read this first)

**DESIGN / ANALYSIS ONLY. Nothing was executed.** No Pi or Node process was
launched, no socket was opened, no model was called, no network request was
made, no credential value was read, and no candidate model was run while
producing this document. No code was implemented. The only files this phase
writes are this document and one explicitly-labelled supersession marker
inside the frozen I2A design (§5.4).

This document is a **narrow correction** to one frozen statement in
`docs/PHASE_5F3B_I2A_B300_PI_ROUTE_CREDENTIAL_BOUNDARY_DESIGN.md` (§15 item
6), plus the design contracts a future **5F3B-I2B-FU2** must satisfy before
any Category-B live execution could ever be authorized.

**The contradiction the task brief suspected is REAL, and it is worse than a
wording problem.** I2A §15 item 6 says `get_commands` proves "exactly
`aido_read`/`aido_edit` registered, nothing else." Frozen AR0-FU1 §4.1j
(source-verified), AR1 FINDINGS §4, AR2 FINDINGS §7.4 and — decisively —
AR2D §2.2's *mandated* truthfulness correction all record that Pi exposes
**no RPC command that enumerates the active tool registry**, and that
`get_commands` proves extension **load**, not registry contents. On top of
that, `aido_read`/`aido_edit` are registered with `pi.registerTool` while
`get_commands` enumerates `pi.registerCommand` **slash commands**, so those
two names can never appear in a `get_commands` response at all. The gate as
written is both *unprovable* and *unsatisfiable*. §5 states the correction.

**This document was itself adversarially re-opened once, before being treated
as final, and three defects in its first draft were corrected in place
(none of §§1–4, §6–8, §10–13 were affected):**

1. §5.2's corrected observability rule originally filtered on the **top-level**
   `source` field — which is itself unsatisfiable, proven by mechanical
   re-inspection of the genuine observed shape (new evidence E19–E22,
   including two real captured live-run records against Pi 0.84.2 and Pi
   0.84.3 respectively): Pi's own inline `llama` command reports the **same**
   top-level `source == "extension"` value AIDO's sentinel does. The real
   discriminator is `sourceInfo.source` (`"cli"` vs `"inline"`); §5.2/§5.3 now
   reflect that.
2. §9.3's original three-state creator-outcome model
   (`NOTHING_CREATED`/`AUTHORITY_RETURNED`/`CLOSED_BY_CREATOR`) was not
   exhaustive: it had no truthful representation for "a resource was created,
   the creator's own bounded self-close was attempted, and that self-close
   itself failed or could not be verified." The fix committed at the time
   introduced a `live_resource_created` / `cleanup_handle` / self-close-
   provenance model with a new controller-owned partial-close adapter per
   resource kind. **This fix was itself withdrawn in the FU3A re-opening
   below — see that entry.**
3. A foreign (`run_id`/`broker_session_id`-mismatched) session was still being
   **passed to the shutdown adapter** — merely excluded from
   `closure_satisfied` — which is a live action against a resource this run
   never proved it owns. §9.4 (new) makes this refusal absolute: the shutdown
   adapter is never called for a session this run cannot prove it created.
   **This correction was not reopened and stands.**

**5F3B-I2A-DESIGN-FU3A re-opened this document a second time, for exactly one
area: §9.3's partial-resource cleanup contract.** Everything else above —
§§1–8, §9.1, §9.2's own diagnosis, §9.4, §10–§13 — was explicitly out of
scope and was not touched. Two further defects were found in item 2's own
fix, above, and closed:

4. **Partial-handle provenance.** `PartialRuntimeHandle`/`PartialBrokerHandle`
   carried no run/session correlation, so *possession* of a returned partial
   handle was — by itself — sufficient to authorize the controller's close
   call, reopening one layer down the exact "possession is not authority"
   defect item 3 had just closed for full sessions.
5. **Double cleanup.** The withdrawn design allowed a creator that had
   already verifiably self-closed a resource to still be followed by the
   controller's own close call against the same resource, silently assuming
   the underlying close primitive is safe to call twice — a property nothing
   in this design establishes.

**Both are closed in the current §9.3 by returning to frozen O1's own shape
(§9.1): no handle of any kind crosses into the controller for a partial
failure. The creator retains ownership, performs at most one bounded
internal attempt, and reports three orthogonal facts
(`resource_created`/`cleanup_attempted`/`cleanup_verified_success`) instead
of a handle.** This closes partial-handle provenance *by elimination* (there
is no longer a handle to forge) and double cleanup *mechanically* (there is
structurally only one possible caller of a close primitive per branch).

**5F3B-I2A-DESIGN-FU3B re-opened this document a third time, for exactly one
residual issue left inside FU3A's own §9.3: a physically real creator
outcome that FU3A's table marked unconstructible.** Everything else —
§§1–8, §9.1, §9.2, §9.4, §9.5, §10–§13, and FU3A's own diagnosis in items
1–5 above — was explicitly out of scope and was not touched.

6. **Stranded partial resource, no cleanup attempt.** FU3A's table refused
   `session=None, resource_created=True, cleanup_attempted=False,
   cleanup_verified_success=None` — a resource created, then the creator
   failing or being interrupted *before it could even invoke its own bounded
   cleanup primitive*. That state is physically possible, and refusing it
   forced a truthful adapter hitting it to either lie or collapse into the
   generic `ADAPTER_RAISED`/`*_AUTHORITY_UNAVAILABLE` bucket, losing the
   specific evidence that a partial resource may remain live with cleanup
   never attempted.

**Closed by making the state constructible and explicitly named** —
`PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT` — with zero cleanup calls by
anyone, `closure_satisfied=False` unconditionally, and terminal PASS
impossible (§9.3's now four-row table, §9.3.2 case 2). FU3B additionally
**freezes the meaning of `cleanup_verified_success=True`** (new §9.3.1): it
is permitted only when the resource-kind-specific postcondition this design
already accepts elsewhere (direct-child exit for runtime, `STATE_CLOSED` for
broker) is actually verified — never merely "the close call didn't raise."
No controller-owned cleanup authority was added, no partial-handle type was
reintroduced, and no retry/polling/process-tree/backend-cancellation
mechanism was added.

**5F3B-I2A-DESIGN-FU3C re-opened this document a fourth time, for exactly
one residual evidence-integrity issue in §9.3/§9.3.1.** Everything else —
§§1–8, §9.1, §9.2, §9.4, §9.5, §10–§13, FU3A's diagnosis, and FU3B's own
stranded-state correction — was explicitly out of scope and was not touched.

7. **The creator still supplied the generic verdict directly.** FU3B froze
   the *meaning* of `cleanup_verified_success=True` in prose, but the
   observation's constructor still **accepted** `cleanup_verified_success`
   as a caller-supplied `bool | None`, and the controller consumed that
   value as-is. A future adapter/refactor could implement "close returned
   without raising ⇒ `cleanup_verified_success=True`" — nothing in the
   *type* prevented it, only the *prose* did. This repeats, at the cleanup
   boundary, exactly the class of defect §6 already closed for H1: an
   adapter must supply mechanically relevant **components**, never the
   final verdict.

**Closed by removing `cleanup_verified_success` as a creator-supplied field
entirely.** The creator now reports only the narrow, resource-kind-specific
**observed postcondition** it can actually observe —
`direct_child_reported_exit` (runtime) or `reached_closed` (broker), each
exactly the same fact this design already accepts for ordinary teardown.
`cleanup_verified_success` becomes a value AIDO's own code derives, always
identically:
`cleanup_attempted and (postcondition is True)` — never bare Python
truthiness, never a "no exception" shortcut. See the corrected §9.3.1 and
the new §9.3.3 adversarial analysis. No controller-owned cleanup authority
was added, no partial handle was reintroduced, and
`PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT` (FU3B) is untouched.

Verdicts, unchanged except where stated:

| | |
|---|---|
| **5F3B-I2A-DESIGN-FU3C** | **ACCEPT** |
| **5F3B-I2A-DESIGN-FU3B** | **ACCEPT** (superseded only within §9.3.1, by FU3C) |
| **5F3B-I2A-DESIGN-FU3A** | **ACCEPT** (superseded only within §9.3, as stated above) |
| **5F3B-I2A design family** | **FREEZE** — no further open issues identified across four re-openings; see §13 |
| **5F3B-I2B-FU2 implementation** | **GO** (design blockers resolved here; I2B-FU1 is not frozen) |
| **Category-B live execution** | **NO-GO** (unchanged) |
| **5F3B-Q1 / Q2** | **NO-GO** (unchanged) |
| **Real-workspace authority** | **NO-GO** (unchanged, and made structurally harder by §8) |

---

## 1. Scope

| | |
|---|---|
| Phase | 5F3B-I2A-DESIGN-FU3 / 5F3B-I2B-FU2 preparation |
| Kind | Design correction + frozen-evidence reconciliation. No implementation |
| Writes | This document; one supersession marker in the frozen I2A design (§5.4) |
| Live activity | **None.** No prompt, no inference, no HTTP request, no process launch, no credential read |
| Frozen inputs read | `experiments/pi_external_runtime_ar1/`, `.../ar2/`, `.../ar2_o1/`, `docs/PHASE_5F3A_AR0_FU1_...`, `docs/PHASE_5F3A_AR2D_...`, `docs/PHASE_5F3B_I2A_...` — none modified except as stated |
| Working-tree inputs read | `experiments/pi_implementer_qualification/qualification/i2b_controller.py`, `i2b_session.py`, `i2_credentials.py`, `i2_route.py`, `i2_pi_config.py` (the **unfrozen** I2B-FU1 slice) |

**Observation-boundary note.** Every conclusion below rests on evidence
**inside this repository**. This phase did not re-open the locally installed
`@earendil-works/pi-coding-agent@0.84.3` package tree, which lives outside the
CLAUDE.md workspace boundary. That is not a gap in the argument: the in-repo
evidence used here is itself source-verified (AR0-FU1 marks each finding `(V)`
against Pi's own `dist/` and bundled `docs/rpc.md`), and every correction below
**fails closed** — none of them would become unnecessary if a future
re-inspection found a tool-enumeration RPC, they would merely become
strengthenable.

---

## 2. Exact frozen evidence inspected

| # | Source | What it establishes |
|---|---|---|
| E1 | `docs/PHASE_5F3A_AR0_FU1_PI_RUNTIME_CONFINEMENT_DESIGN.md:315-318` §4.1(j), marked `(V)` | "**There is no RPC command that enumerates the active tool set.** The complete command list in `docs/rpc.md` has no `get_tools`; `get_state` returns model, thinking level, streaming/compaction flags, session identity and message counts — **not tools**." |
| E2 | same file `:318-322` §4.1(k), `(V)` | `get_commands` **does** enumerate extension-registered **commands**, with `source: "extension"` and the extension `path`. It is "**a positive, in-protocol, pre-prompt proof that this exact extension loaded**" |
| E3 | same file `:894` risk **N4** | "The `get_commands` sentinel proves *extension load*, not *registry contents*. Record the difference honestly" |
| E4 | same file `:405-425` §4.3(1) | Distinct `aido_*` names + `--tools` naming only those means a failed extension load leaves **zero** matching tools — the unobservable failure mode is *absence of capability*, never *unconfined capability* |
| E5 | `experiments/pi_external_runtime_ar1/FINDINGS.md:146-152` §3.1 | `get_commands` reports origin under `sourceInfo.path`, not the flat `path` the shipped `docs/rpc.md` example shows |
| E6 | same file `:153-158` §3.2 | **Pi ships its own inline extension command** (`llama`, `sourceInfo.source: "inline"`), so `get_commands` shows two extension-sourced commands even with `--no-extensions` and one `-e`. "It is a slash **command**, not a tool; the `--tools` registry filter governs tools regardless" |
| E7 | same file `:176` §4, and `ar1/record.py:64-68` | Residual limitation, in the emitted record: "`get_commands` proves the extension loaded, not the active tool registry's contents" |
| E8 | `experiments/pi_external_runtime_ar2/FINDINGS.md:238-239` §7.4 | "`get_commands` proves the intended extension **loaded at the expected path**; Pi exposes no RPC command that enumerates the active tool registry" |
| E9 | `experiments/pi_external_runtime_ar2/README.md:133-136` | Same, plus: a broker that received only `read_file`/`edit_file` frames is evidence about **what was requested through the broker**, never proof of registry contents |
| E10 | `docs/PHASE_5F3A_AR2D_DELEGATED_WORKSPACE_AUTHORITY_DESIGN.md:143-156` §2.2, **mandated** correction | The three-way distinction, verbatim: `configured registry allowlist` (AIDO's own argv) / `observed live tool calls` / `extension identity` (handshaken) / **`NOT established`: an RPC registry query proving the active runtime registry contained only those two**. "**AR2 must preserve it.**" |
| E11 | `experiments/pi_external_runtime_ar2/ar2/handshakes.py:32-135` | The frozen H1 evaluator `evaluate_extension_identity`, its five components, and its own `does_not_prove` string: "the exact contents of the active tool registry" |
| E12 | `experiments/pi_external_runtime_ar2/ar2/pi_config.py:40-41` | `SENTINEL_COMMAND_NAME = "aido_ar2_broker_active"`; `TOOL_ALLOWLIST = ("aido_read", "aido_edit")` — **two disjoint namespaces** |
| E13 | `experiments/pi_external_runtime_ar2/extension/index.ts:38,40,42` | `pi.registerTool(...)` ×2 for read/edit; `pi.registerCommand(AIDO_SENTINEL_COMMAND, ...)` ×1 for the sentinel |
| E14 | `experiments/pi_external_runtime_ar2_o1/FINDINGS.md:2-10, 44-52, 88-105` | Pi **0.84.3** observed; version is provenance, never authorization; the corrected **13-named-check** compatibility gate and its results |
| E15 | `experiments/pi_external_runtime_ar2_o1/o1/handshake.py:1-63` | The exception-safe launch/handshake lifecycle: catch any exception, attempt **one** bounded self-shutdown, never let the cleanup failure mask the original failure, track `pi_config_dir`/`extension_dir` independently |
| E16 | `experiments/pi_external_runtime_ar2_o1/run_o1.py:412-424, 617` | Broker handle constructed first, `start()` guarded, `server.shutdown(...)` reachable on **every** path |
| E17 | `experiments/pi_external_runtime_ar2/ar2/capability.py:246-288, 331-348, 487-547` and `ar2/fixtures.py:479-545, 611-641` | `DisposableRootAuthority`: authority originates **only** at fresh-root creation; no function converts an existing path into one; marker written with `O_CREAT\|O_EXCL`; `mint_capability` re-verifies the marker rather than trusting the object |
| E18 | `docs/PHASE_5F3B_I2A_..._DESIGN.md:761-792` §14, `:793-834` §15 | The Category-A / Category-B gate split under correction here |

---

## 3. What Pi `get_commands` actually enumerates — answered mechanically

**It enumerates slash commands, and only slash commands.**

Each reported entry carries a `name`, a `source` (`"extension"`, or something
else such as one of Pi's own built-ins), and — per E5 — an optional
`sourceInfo` object holding `{source, path}`, where `source` is an origin kind
(`"cli"` for a CLI-loaded extension, `"inline"` for one Pi ships itself) and
`path` is the extension entry point.

Three facts follow, each mechanically checkable in this repository:

1. **Tools and commands are two disjoint namespaces in the accepted
   extension** (E12, E13). `aido_read` and `aido_edit` are registered with
   `pi.registerTool`. The sentinel — `aido_ar2_broker_active` in AR2 — is
   registered with `pi.registerCommand`. `get_commands` reports commands.
   Therefore **`aido_read` and `aido_edit` can never appear in a
   `get_commands` response** produced by the accepted extension shape.
2. **A real `get_commands` response is not limited to AIDO's own entries**
   (E6). Pi's own inline `llama` command is reported with
   `sourceInfo.source: "inline"` even under `--no-extensions` with one
   explicit `--extension`. Any exact-equality rule over the *whole* reported
   set is therefore wrong on its face.
3. **What the response does prove is extension identity** (E2, E11): a command
   with the intended sentinel name exists, its `source` is exactly
   `"extension"`, its reported path resolves to exactly the entry point AIDO
   itself passed via `--extension`, and any reported `sourceInfo.source` does
   not contradict `"cli"`.

---

## 4. Does Pi 0.84.3 offer ANY already-authorized zero-prompt observation of the active tool registry? — **No**

**Answer: no, and no already-authorized mechanism substitutes for one.**

- **No RPC command.** E1 is explicit and source-verified: Pi's complete RPC
  command list contains no `get_tools`, and `get_state` returns model,
  thinking level, streaming/compaction flags, session identity and message
  counts — not tools. E3 records the same as a named residual risk (N4);
  E7/E8/E9 repeat it in three independently emitted records; E11 states it in
  the frozen evaluator's own `does_not_prove` field.
- **Not from `get_commands`.** §3 above: wrong namespace.
- **Not from `get_state`.** E1 enumerates its contents; tools are not among
  them.
- **Not from the launch argv.** `--tools aido_read,aido_edit` is the
  **configured allowlist** — AIDO's own bytes, provable *offline*. E10 is a
  mandated correction that exists precisely to stop this from being reported
  as registry evidence.
- **Not from broker traffic.** E9: frames received are evidence about what was
  *requested through the broker*, never about what the registry contained.
- **Not established for 0.84.3 either.** O1 is the only phase that ever ran
  against Pi **0.84.3** (E14). Its corrected compatibility gate is 13 named
  checks; **none of them is a tool-registry check.** Checks 5 and 6 are
  `get_commands_response_shape_understood` and `h1_extension_identity_passed`;
  check 10, `required_launch_flags_accepted`, records that the argv
  *including* `--tools aido_read,aido_edit` was **accepted** — that the flag
  did not cause a startup rejection, which is a launch fact, not a registry
  observation. So the one phase with real 0.84.3 runtime evidence composed its
  gate without such a check and reported finding none.

The only mechanism ever proposed for closing this is AR0-FU1 §4.1j's own
suggestion — "consider a first-turn probe tool call in a later slice" (E3).
That is a **model turn**, i.e. a semantic prompt. It is categorically
unavailable to a zero-prompt gate, and the task brief forbids inventing a
probe prompt, an HTTP interceptor, a proxy, a model call, or a generic runtime
capability to make the old wording true. **Nothing is added here.**

---

## 5. The contradiction is REAL — I2A §15 item 6 is superseded

### 5.1 Two independent defects, not one wording slip

**Defect 1 — the claim is unprovable.** "exactly `aido_read`/`aido_edit`
registered, nothing else" is a claim about the **active tool registry**. Per §4
no zero-prompt observation of it exists. E10 already ruled, as a *mandated*
truthfulness correction that AR2 was ordered to preserve, that exactly this
class of sentence overstates the evidence.

**Defect 2 — the claim is unsatisfiable.** Even setting provability aside,
`get_commands` reports **commands**, and `aido_read`/`aido_edit` are **tools**
(§3.1). A live run of the accepted extension shape would report the sentinel
command and Pi's inline `llama` command — never those two names. A gate
comparing the reported command names to `("aido_edit", "aido_read")` fails on
every correct run.

**Both defects are live in the unfrozen I2B-FU1 controller.**
`qualification/i2b_controller.py` defines
`AUTHORIZED_TOOL_NAMES = ("aido_edit", "aido_read")` and gates `TOOL_REGISTRY`
on
`sorted(commands_observation.command_names_in_report_order()) == AUTHORIZED_TOOL_NAMES`,
recording the result as the compatibility fact
`authorized_tool_registry_exact`. `i2b_session.ObservedCommand` even documents
`source` as *deliberately not* part of the rule, on the stated ground that
"I2A Sec. 15 item 6 defines that gate over the REGISTERED COMMAND SET" — which
is precisely the superseded sentence. The controller faithfully implemented an
incorrect specification; correcting the specification is the fix, and the
implementation follows in I2B-FU2.

### 5.2 The corrected Category-B observability contract

**Self-correction, made before this document was ever treated as final.** An
earlier draft of this section wrote the rule as "entries whose `source` is not
`\"extension\"` are not part of this rule" — implying the **top-level**
`source` field distinguishes AIDO's own CLI-loaded extension from Pi's own
`llama` command. Mechanical re-inspection of the actual observations (E19–E22
below), not prose, disproves that: **both** report top-level
`source == "extension"`. The real discriminator is `sourceInfo.source`
(`"cli"` for AIDO's CLI-loaded extension, `"inline"` for Pi's own). The draft
rule was therefore itself unsatisfiable in exactly the way §5.1 Defect 2
criticized the original item 6 for being — it would have failed
`EXTENSION_COMMAND_NAMESPACE` on every real run, because `llama` also reports
`source == "extension"` at the top level. This subsection replaces that draft
with the mechanically verified shape.

**Additional evidence inspected for this correction:**

| # | Source | What it establishes |
|---|---|---|
| E19 | `experiments/pi_external_runtime_ar1/tests/test_lifecycle_and_gates.py:293-310`, `test_pi_ships_its_own_inline_extension_command_and_it_is_not_a_tool` | The genuine reported shape: sentinel = `{"name": SENTINEL, "source": "extension", "sourceInfo": {"path": entry, "source": "cli"}}`; `llama` = `{"name": "llama", "source": "extension", "sourceInfo": {"path": "<inline:llama.cpp>", "source": "inline"}}`. **Both** carry top-level `"source": "extension"` |
| E20 | `experiments/pi_external_runtime_ar2/results/ar2_case_R1_20260824T175158Z.json` — a **real captured live run** against Pi 0.84.2 | `handshake_extension.extension_command_count: 2`, `non_extension_command_count: 0` — two top-level-`"extension"`-sourced commands were reported, none of any other top-level `source` |
| E21 | `experiments/pi_external_runtime_ar2_o1/results/ar2o1_case_O1_20260824T225809Z.json` — a **real captured live run** against Pi **0.84.3** | Identical: `extension_command_count: 2`, `non_extension_command_count: 0`. The count is stable across two Pi versions and three separate real runs (AR1's live run, AR2's R1, O1) |
| E22 | `experiments/pi_external_runtime_ar2/run_ar2.py:388-392`, `experiments/pi_external_runtime_ar2_o1/o1/handshake.py:288-292` | The exact, source-verified computation: `extension_command_count = sum(1 for c in commands if c.get("source") == "extension")` — confirms the counted field is the **top-level** `source`, so E20/E21's `count == 2` is proof, not inference, that `llama` shares AIDO's sentinel's top-level `source` value |

The **intended safety invariant** behind item 6 is worth stating plainly,
because it survives the correction intact:

> The model must be offered no filesystem capability other than AIDO's two
> broker-backed tools.

That invariant is established by **four** things, of which only two are
Category-B observations, plus one thing that is explicitly **not**
established:

```text
A-1  configured tool allowlist        OFFLINE (Category A)  argv exact-tuple equality
                                      -- AIDO's own bytes; already I2A Sec. 14 item 5
A-2  fail-closed-by-naming            OFFLINE (Category A)  distinct aido_* names, never
                                      overrides, so a failed extension load leaves ZERO
                                      matching tools (AR0-FU1 Sec. 4.3(1))
B-1  extension identity (H1)          LIVE, zero-prompt     the intended extension loaded,
                                      at the expected path, non-contradictory origin
B-2  extension command PROVENANCE     LIVE, zero-prompt     every top-level-"extension"
                                      partition (corrected)  -sourced entry classifies, by
                                                             sourceInfo.source, as EITHER the
                                                             one valid AIDO/cli entry OR a
                                                             mechanically-verified Pi-owned
                                                             inline entry -- nothing else
--   active tool registry contents    NOT OBSERVABLE        recorded as an explicit
                                      non-observation, never as a passing gate
```

**The corrected item 6 reads:**

> 6. `get_commands` — every reported command whose **top-level** `source` is
>    `"extension"` is classified by its `sourceInfo.source`:
>    - entries reporting `sourceInfo.source == "cli"` are candidate
>      AIDO-loaded-extension entries. There must be **exactly one**, and it
>      must be H1-valid (§6) — a second such entry, or one that is not
>      H1-valid, fails closed;
>    - entries reporting `sourceInfo.source == "inline"` (a well-formed
>      `sourceInfo` object, the exact bounded string `"inline"`, nothing
>      malformed) are Pi's own and are tolerated without further constraint
>      on their name, path or count — Pi's own catalog is not this gate's
>      business, and a Pi upgrade adding or removing one must not need this
>      gate to change;
>    - any other top-level-`"extension"`-sourced entry — missing `sourceInfo`,
>      malformed `sourceInfo`, or a `sourceInfo.source` that is neither `"cli"`
>      nor `"inline"` — is an **unrecognized provenance** and fails closed.
>
>    This proves the extension **command provenance partition** is exactly
>    what AIDO intended; it does **not** prove the contents of the active tool
>    registry, which Pi exposes no zero-prompt observation of.

Four properties of this rule matter and must not be traded away:

- it is **satisfiable against the genuine observed shape** — proven by E19–E22
  against real Pi 0.84.2 and 0.84.3 runs, not merely a synthetic double;
- it is **provable** — every input is a field of the one `get_commands`
  response;
- Pi-owned commands are tolerated **only on mechanically established
  provenance** — `sourceInfo.source == "inline"` exactly, never "any entry not
  matching the sentinel by name is assumed to be Pi's";
- it is a **real** gate, not a weakening. A second `"cli"`-sourced entry, or an
  entry with unrecognized provenance, means an extension AIDO did not intend
  is present or Pi's origin reporting changed shape unexpectedly — exactly the
  fail-open surface AR0-FU1's N1 warns about. Failing closed on it is a
  genuine safety property the original unsatisfiable item 6 never delivered.

### 5.3 What I2B-FU2 must change (specification, not code)

| Current (I2B-FU1) | Corrected |
|---|---|
| `AUTHORIZED_TOOL_NAMES = ("aido_edit", "aido_read")` compared against `get_commands` output | **Removed from the `get_commands` comparison.** The tool allowlist belongs to the Category-A argv gate, if anywhere |
| `CategoryBGateName.TOOL_REGISTRY` | `CategoryBGateName.EXTENSION_COMMAND_NAMESPACE` |
| `CategoryBFailureCode.TOOL_REGISTRY_MISMATCH` | split into `CategoryBFailureCode.UNEXPECTED_CLI_EXTENSION_COMMAND` (a second, or an invalid, `"cli"`-sourced entry) and `CategoryBFailureCode.EXTENSION_COMMAND_PROVENANCE_UNKNOWN` (malformed/unrecognized `sourceInfo.source` on a top-level-`"extension"`-sourced entry) |
| `CompatibilityFacts.authorized_tool_registry_exact` | `CompatibilityFacts.no_unexpected_extension_command_observed` |
| `ObservedCommand.source` "deliberately NOT part of the rule" | top-level `source` is used only to select the top-level-`"extension"`-sourced subset (identical computation to the already-accepted `extension_command_count`, E22 — reused, not reinvented); `sourceInfo.source` becomes the **load-bearing** discriminator within that subset |
| comparison target | the sentinel-named entry is H1-validated (§6); every **other** top-level-`"extension"`-sourced entry is classified by its own `sourceInfo.source` — never by name comparison against a hard-coded literal |
| (absent) | new evidence field `active_tool_registry_observation_available: false`, alongside the already-accepted `provider_request_count_observation_available: false` and `wire_level_max_tokens_observation_available: false` — the shape already exists in the evidence body, so this is a new field of an accepted kind, not a new mechanism |
| (absent) | a **mandatory offline regression case** reproducing E19's exact genuine shape (sentinel `sourceInfo.source == "cli"` + `llama` `sourceInfo.source == "inline"`) and asserting the gate **passes** — the corrected rule must be proven satisfiable against the real shape, not merely against a synthetic double invented for this document |

**Honesty about what is reused versus new.** Only the sentinel-named entry's
evaluation is the frozen, unmodified `ar2.handshakes.evaluate_extension_identity`
(§6.3). Classifying the *other* top-level-`"extension"`-sourced entries by
`sourceInfo.source` is **new I2B-owned code** — AR2 never needed it, because
`evaluate_extension_identity` only ever examined the sentinel-named entry. It
must not be described as "the frozen evaluator, reused," and it must reuse
the same bounded-string/malformed-metadata validation primitives already in
`i2b_session.py` (`_require_pattern`, `ObservedCommand`'s own bounds) rather
than inventing a second validation style.

The evidence body must additionally carry the E10 three-way distinction
verbatim in its `claim_scope`, so an archived Category-B packet can never be
read as a registry claim.

**The comparison stays a sorted sequence, never a set, wherever a name list is
compared** — the I2B-FU1 duplicate-collapse fix is correct and is preserved.

### 5.4 Supersession marker

Because I2A is frozen, its §15 item 6 text is **left verbatim** and annotated
in place with an explicit `SUPERSEDED BY` pointer to this document, plus a
paragraph in I2A's `CURRENT STATUS` block. Nothing else in I2A is touched, and
no I2A semantic is silently rewritten.

---

## 6. The H1 proof contract

### 6.1 The accepted H1 rule (frozen, not reopened)

`ar2.handshakes.evaluate_extension_identity` (E11) requires, in order, with no
partial credit and no path repair:

1. a command with the intended sentinel name was reported at all;
2. its reported `source` is exactly `"extension"`;
3. its reported path — `sourceInfo.path`, falling back to the flat `path`
   (E5) — resolves, via `normcase(realpath(...))` on both sides, to exactly
   the extension entry point AIDO itself passed via `--extension`;
4. when a `sourceInfo.source` origin is reported, it does not contradict the
   one known-expected value for a CLI-loaded extension (`"cli"`);
5. no malformed metadata anywhere (`sourceInfo` present but not an object,
   `sourceInfo.path` present but not a string, flat `path` present but not a
   string).

`passed = 1 and 2 and 3 and 4 and not 5`.

### 6.2 Why the current shape is insufficient

`GetCommandsObservation.extension_identity_matched: bool` is a **single
caller-supplied verdict**. AIDO records it as the compatibility fact
`h1_extension_identity_matched` without deriving anything. Nothing anywhere
establishes that the value came from the frozen rule rather than from an
adapter that computed something weaker — for instance the pre-AR1-FU1 gate
that a same-named command merely *existed*, which is exactly the defect
AR1-FU1 was written to close. A bare boolean cannot be accepted as the whole
proof.

### 6.3 The required contract — decompose, recompute, and prove equivalence

**(a) The adapter returns components, never a verdict.** The bounded
observation carries the frozen rule's own five components as five independent
exact-`bool` fields, plus two bounded origin tokens:

```text
sentinel_name_matched                     bool
sentinel_source_is_extension              bool
sentinel_path_resolves_to_expected_entry  bool
noncontradictory_source_origin            bool
malformed_source_metadata                 bool
expected_source_kind                      bounded token   ("cli")
reported_source_kind                      bounded token | None
```

**(b) AIDO recomputes the verdict.** The controller — not the adapter —
evaluates `1 and 2 and 3 and 4 and not 5`. No single adapter field can
authorize H1, and a future adapter that starts returning `True` for a weaker
notion of "matched" cannot express that as a pass, because the field it would
have to lie about is the specific one it did not check.

**(c) The adapter is proven to use the frozen evaluator, offline.** The live
adapter's contract is fixed: obtain the raw `get_commands` command list, call
the **frozen, unmodified**
`ar2.handshakes.evaluate_extension_identity(commands, extension_entry=<the entry AIDO itself passed>)`,
and project that function's returned dict **field-for-field** onto the seven
fields above — discarding `failure_reasons` (its only free-text field) and
never retaining the raw list. Compliance is proven by a **differential
conformance test in the offline suite**: a fixed adversarial corpus of
synthetic `get_commands` command lists is run through both the frozen
evaluator and the adapter's projection, and the five booleans must agree
exactly on every row. The corpus must include, at minimum, the cases AR1/AR2
already exercise — sentinel absent; sentinel present with
`source != "extension"`; correct name and source but a non-matching path;
`sourceInfo` present but not an object; `sourceInfo.path` present but not a
string; flat `path` present but not a string; neither path field usable; a
contradicting `sourceInfo.source`; the genuine match; and AR1's observed
real-world shape of Pi's inline `llama` command alongside the sentinel (E6).
This is the same "reuse the frozen thing, never fork it" discipline I2A §15
item 9 already mandates for `check_route_serves_model`, applied to H1.

**(d) No unsafe raw text is retained.** The observation holds booleans plus two
bounded origin tokens. The **expected extension entry path** is an absolute
path: it is an input the adapter needs, never an observation field, never
`repr`-rendered, and never placed in the evidence body — and the
generated-config/extension directory it lives under is declared to
`ArtifactSafetyContext` so the scrub gate would refuse an artifact carrying it.

**(e) Honest residual, stated in the same class as the `run_id` nonce.** The
adapter is AIDO's own future live code, inside the trust boundary. This
contract is a correctness/integrity control against a **projection defect or a
future refactor**, not a defense against a hostile adapter that deliberately
fabricates all five components. Never write otherwise.

---

## 7. Credential-read ordering (required I2B-FU2 invariant)

### 7.1 The invariant

> **Every deterministic non-secret refusal that can be established before the
> credential read MUST occur before that read.** In particular an unknown
> candidate, or any invalid route descriptor, must invoke the credential
> reader **zero** times.

This strengthens, and never weakens, I2A §8/§16's accepted ordering: it adds
gates *before* the credential boundary; it moves none across it.

### 7.2 The defect in I2B-FU1

`run_category_b_controller` calls
`resolve_connection_after_preflight(non_secret_gates=..., read_connection=...)`
**first**, and only then calls `route_descriptor_for_candidate(candidate)`.
`route_descriptor_for_candidate` is fully deterministic and non-secret — a
membership test against the frozen `CANDIDATE_MODEL_IDS` mapping plus
fixed-constant equality on `provider_id`, `backend_gateway_class`,
`credential_mechanism` and `credential_env_var_name`. It consumes nothing from
the connection, and its output is not needed until `build_secret_context`.

**Consequence today:** `run_category_b_controller(candidate="typo", ...)`
invokes the credential reader **once**, and only afterwards refuses with
`ROUTE_DESCRIPTOR_INVALID`. A run that could never have proceeded caused a real
credential read.

### 7.3 The corrected pre-credential prefix

```text
1  AIDO-supplied argument validation      CategoryBControllerInputError (raised, not a gate)
2  RUN_CORRELATION                        mint the per-run run_id, bounded (Sec. 10)
3  WORKSPACE_AUTHORITY                    verify + single-use claim for this run (Sec. 8)
4  ROUTE_DESCRIPTOR                       deterministic, non-secret        <-- MOVED UP
5  NON_SECRET_PREFLIGHT                   reused i2_credentials, unmodified
------------------------------------------------------------ CREDENTIAL BOUNDARY
6  CONNECTION_VALUES                      the one credential read
7  SECRET_CONTEXT -> PI_CONFIG_GENERATION -> ... (unchanged from I2B-FU1)
```

### 7.4 How it is proven

The package already has the mechanism: `resolve_connection_after_preflight`'s
own offline tests wrap `read_connection` in a call-counting double. I2B-FU2
extends that to assert **`read_connection` call count == 0** for each of:

- an unknown candidate;
- a reversed / mismatched candidate-model pairing;
- a workspace authority that cannot be verified;
- a workspace authority belonging to a different run;
- a workspace authority already claimed (cross-run reuse);
- correlation-id generation failure.

A source-level assertion additionally fixes the order: the `CONNECTION_VALUES`
gate's position in `COMPATIBILITY_GATES` must be strictly greater than
`ROUTE_DESCRIPTOR`'s, `WORKSPACE_AUTHORITY`'s and `RUN_CORRELATION`'s.

---

## 8. Synthetic workspace authority

### 8.1 The defect

`run_category_b_controller` takes `workspace_root: str` and
`experiment_root: str` as **arbitrary caller-supplied strings**, validated only
as "non-blank". They flow, unverified, into:

- `BrokerCreationRequest.workspace_root` — the capability scope;
- `RuntimeLaunchRequest.workspace_root` — what the runtime is launched against;
- `build_run_safety_context(workspace_root=...)` — the scrub needle;
- `write_qualification_pi_config(experiment_root, ...)`, which performs
  `Path(experiment_root) / "i2_pi_config"` followed by
  `mkdir(parents=True, exist_ok=False)`.

That last one is a filesystem write to a caller-named location.
`run_category_b_controller(experiment_root=r"C:\dev\mis_project", ...)` is today
a well-typed call. **This is not acceptable while real-workspace authority is
NO-GO**, and it is the same class of defect AR2-FU1A already closed once, for
AR2 (E17).

### 8.2 The rule — authority originates at creation, never from a string

The narrowest correct design **reuses the accepted AR2 mechanism unmodified**
rather than inventing a second one. `qualification/fixtures.py` already sets
this precedent, building every qualification fixture through
`ar2.fixtures.build_case_repository`, which always originates a fresh root via
`ar2.fixtures.create_disposable_experiment_root`.

One new I2B-owned value object, `QualificationRunWorkspace`, wraps the result:

```text
run_workspace_nonce   the creation nonce minted with the root
experiment_root       from the verified DisposableRootAuthority
workspace_root        the authority's repo_root -- the ONLY workspace identity
                      the run has, used for the broker, the runtime and the
                      ArtifactSafetyContext alike
```

There is exactly **one** function that produces it, and it *creates* the root in
the same step. **There is no function anywhere that accepts an existing path and
returns one** — that is the whole property, and it is AR2-FU1A's own wording
(E17).

### 8.3 Required properties, and how each is met

| Property | Mechanism |
|---|---|
| canonical / absolute identity | `tempfile.mkdtemp()` + `os.path.realpath` at creation, exactly as `create_disposable_experiment_root` already does |
| created / verified by qualification machinery, not caller prose | the minting function creates the directory itself; the controller's `workspace_root: str` and `experiment_root: str` **parameters are removed** and replaced by one `QualificationRunWorkspace` parameter |
| cannot name `C:\dev\mis_project`, a sibling project, a parent workspace, or any unrelated directory | structurally: the root is one `mkdtemp()` created moments earlier under `approved_scratch_boundary()`. AR2's `diagnostic_forbidden_root_reason` runs too, as **belt-and-braces only** — never as the proof |
| exact identity available for `ArtifactSafetyContext` | `build_run_safety_context` takes `workspace_absolute_path` from the verified `workspace_root`, never from a caller string |
| same identity bound to broker and runtime authority | `BrokerCreationRequest` and `RuntimeLaunchRequest` take the `QualificationRunWorkspace`, not a string. The launch request already refuses a foreign broker session; it now equally refuses a workspace object that is not the one the broker was created for |
| fail closed on **substitution** | the object is unforgeable through the public API: its constructor requires a token registered by the minting call, mirroring `i2_issuance`'s accepted register/finalize pattern for the generated config |
| fail closed on **relocation / tampering** | the on-disk marker is **re-verified**, not trusted, at each consumption boundary — immediately before broker creation and again before runtime launch. AR2's `mint_capability` already re-reads the marker rather than trusting the object (E17); the same discipline applies here |
| fail closed on **cross-run reuse** | a **single-use claim**: `claim_run_workspace(workspace, run_id=run_id)` registers `workspace_nonce -> run_id` exactly once. A second claim — by this run or any other — refuses. This preserves I2B-FU1's controller-minted `run_id` nonce rather than replacing it |

### 8.4 What this is NOT

This is **not** production real-workspace authority, and it must never be
described as a step toward one. It is the opposite: it makes a real workspace
**structurally unreachable** from this code path, by removing the only parameter
through which one could have been named. Real-workspace authority remains NO-GO
(5F3B §22.1, I2A §22), and nothing here reduces the work a future authorized
phase would owe.

The honest scope is AR2-FU1A's, unchanged: this defends against an AIDO
configuration or programming mistake — a stale variable, a copy-paste error, a
future refactor handing the wrong object across. It is **not** a defense against
a same-user adversary, who could forge a marker trivially and does not need this
code path at all.

---

## 9. Creator partial failure

### 9.1 The frozen O1 shape

Two properties, both observable in frozen O1 (E15, E16):

1. **The handle is obtained before the resource is created, and survives every
   path.** `run_o1.phase_case` constructs `BrokerServer(handler)` *outside* the
   `try`, guards `server.start()` *inside* it, and reaches `server.shutdown(...)`
   on every outcome. A broker that failed to start is still a broker AIDO can
   close.
2. **A creator that fails cleans up its own partial resource, and says so
   truthfully.** `o1.handshake.launch_and_handshake` catches **any** exception in
   the launch/handshake sequence, attempts exactly **one** bounded
   `PiRpcSupervisor.shutdown()`, and packages the result. FU1A additionally
   guarantees that a failing self-shutdown can never mask or replace the original
   failure (the original is always the reported primary failure; whether a
   shutdown was attempted and whether it *also* raised are separate independent
   facts), and that a failed shutdown is never reported as though the child
   stopped — `termination` stays `{}`, the same "nothing observed" shape used
   when no shutdown was attempted at all.

### 9.2 The gap in I2B-FU1 — the three states are not exhaustive

**Self-correction.** An earlier draft of this section proposed exactly three
creator-outcome states — `NOTHING_CREATED` / `AUTHORITY_RETURNED` /
`CLOSED_BY_CREATOR` — and required every creation attempt to land in one of
them. That is not exhaustive. It has no representation for the physically
real fourth outcome: **a live resource was actually brought into existence,
AND the creator's own bounded self-close was attempted, AND that self-close
itself failed or could not be verified.** Under the three-state model this
adapter has no honest way to report that: it cannot claim
`NOTHING_CREATED` (something was created), it cannot claim
`CLOSED_BY_CREATOR` (the close did not verifiably succeed — claiming it did
would be exactly the false "closed" state the brief forbids), and
`AUTHORITY_RETURNED`'s only payload was a **fully session-correlated**
`RuntimeSession`/`BrokerSession` (carrying `run_id`, a `session_id`, and — for
the runtime side — a matching `broker_session_id`), which a partially-launched
resource frequently cannot produce (e.g. a process exists but never reached
the point where an RPC-correlated session id was assigned). The existing
`RuntimeLaunchObservation.__post_init__` therefore makes this real state
**unconstructible** — not merely undocumented — so a truthful adapter hitting
it is forced to violate the type's own invariant, which surfaces as
`MALFORMED_ADAPTER_RESULT`/`ADAPTER_RAISED` at the `_invoke` boundary. That is
a *bounded* refusal (fails closed), but it is not an *honest* one: the emitted
evidence records a generic malformed-adapter code, never "a partial resource
may still be live and this run's own attempt to verify its closure did not
succeed."

The **broker** side is additionally missing the runtime side's partial
symmetry entirely: `create_broker: Callable[[BrokerCreationRequest], BrokerSession]`
returns a **bare** `BrokerSession` with no failure-carrying shape at all. And
for **both** adapters, a **raise** bypasses every rule: `_invoke` catches it,
AIDO holds no authority, and the run refuses with `*_AUTHORITY_UNAVAILABLE` —
honest as far as it goes, but the *creator contract* still permits an adapter
to raise after creating a live resource, which is exactly the stranding the
brief forbids, and which the fourth-state gap above shows the contract cannot
yet even fully close by construction.

**This diagnosis of the gap is correct and stands.** What does not stand is
the fix §9.3 originally proposed for it — see the FU3A note at the top of
§9.3 below for why, and for the corrected contract.

### 9.3 [5F3B-I2A-DESIGN-FU3A, corrected by FU3B and FU3C] The required creator contract — no handle crosses the boundary

**[5F3B-I2A-DESIGN-FU3C]** One evidence-integrity issue remained after FU3B:
the observation still let the creator **directly supply the generic verdict**
`cleanup_verified_success: bool | None`, and the controller consumed that
caller-supplied verdict as-is to record `CLOSED_BY_CREATOR_VERIFIED`/
`closure_satisfied=True`. That repeats, at the cleanup boundary, exactly the
class of defect §6 (H1) already closed: an adapter supplying a **final
verdict** rather than the narrow, individually-checkable **components** AIDO
itself derives the verdict from. A future adapter could implement "close
returned without raising ⇒ `cleanup_verified_success=True`" — a materially
weaker claim than the postcondition §9.3.1 already requires — and nothing in
the FU3B shape mechanically prevented that specific mistake, even though
§9.3.1's *prose* already forbade it. FU3C removes `cleanup_verified_success`
as a **creator-supplied** field entirely. The creator now reports only the
narrow, resource-kind-specific **observed postcondition**
(`direct_child_reported_exit` for runtime, `reached_closed` for broker), and
`cleanup_verified_success` becomes a **read-only value AIDO's own code
derives** — `cleanup_attempted and postcondition is True`, computed the same
way everywhere, never reimplemented per adapter. See §9.3.1 (rewritten) and
the new §9.3.3 adversarial analysis. Nothing else in §9.3 — the four-row
constructibility table's states, row 4's stranded semantics, the
single-cleanup-owner property, the elimination of the partial handle — is
reopened by FU3C.

**[5F3B-I2A-DESIGN-FU3B]** FU3A's own table below originally marked one
physically real state **unconstructible**:
`session=None, resource_created=True, cleanup_attempted=False,
cleanup_verified_success=None` — a resource was created and the creator
failed, or was itself interrupted, *before it could even invoke its own
bounded cleanup primitive*. Refusing that observation forced a truthful
adapter hitting it to either lie (falsely claim an attempt was made) or fall
back to the generic `ADAPTER_RAISED`/`*_AUTHORITY_UNAVAILABLE` bucket,
losing the specific, important evidence that a partial resource may remain
live with cleanup never even attempted. FU3B makes this state **constructible
and explicitly named** — `PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT` — as
the table's fourth row now shows, and freezes the meaning of
`cleanup_verified_success=True` (§9.3.1) so it can never be silently
weakened to "the close call merely didn't raise." Nothing else in §9.3, and
none of §9.1, §9.2, §9.4, §9.5, is reopened by FU3B.

**FU3 was placed on HOLD for exactly this subsection (first by FU3A, then by
FU3B for one residual issue within it).** The handle-based fix
above (`cleanup_handle` + two new controller-owned
`close_partial_runtime_resource`/`close_partial_broker_resource` adapters)
closed §9.2's exhaustiveness gap, but doing so **introduced two new defects
of its own**, found on re-opening:

1. **Partial-handle provenance.** `PartialRuntimeHandle`/`PartialBrokerHandle`
   carried no `run_id`/session correlation at all — by design, since a
   partially-launched resource frequently cannot produce one yet. But that
   means **possession of a returned handle was, by itself, sufficient to
   authorize the controller's close call** — exactly the "possession is not
   authority" defect §9.4 had just closed for full sessions, reopened one
   layer down for partial ones. A supported adapter returning an
   individually-valid partial handle belonging to a *different* invocation
   would have been acted on with no mechanical proof it came from *this*
   creation attempt.
2. **Double cleanup.** The table's own third row — `creator_attempted_self_close=True`,
   `creator_self_close_verified_success=True`, `cleanup_handle` still present
   — required the controller to perform its **own** close call on a resource
   the creator had *already verifiably closed*. That assumes the underlying
   close/shutdown primitive is safe to call twice. Nothing in this design
   establishes that, and the brief is explicit: do not assume it.

**The corrected contract eliminates both defects by elimination, not by
patching the handle.** It returns to the shape §9.1 shows frozen O1 already
uses for real — a creator that retains its own cleanup authority and
performs, internally, **at most one** bounded attempt, never handing a raw
handle to the controller at all:

```text
                     +-- session established & trusted? --+
                     |                                     |
                    YES                                    NO
                     |                                     |
        ownership TRANSFERS to controller      creator RETAINS ownership;
        (normal, unchanged §9.4-gated           performs >= 0, <= 1 bounded
         teardown call applies)                 internal cleanup attempt;
                                                 returns 3 bounded facts;
                                                 NO handle crosses the boundary
```

**The observation shape, per resource kind** (`RuntimeLaunchObservation`,
corrected in place; the new `BrokerCreationObservation` replacing today's
bare `BrokerSession` return type):

```text
session                  RuntimeSession | BrokerSession | None
                          -- fully correlated (run_id, session_id, and for
                          runtime the matching broker_session_id) exactly as
                          today; unrelated to this correction
resource_created          bool  -- did creation bring ANY live resource into
                                   existence, even partially?
cleanup_attempted         bool  -- did the CREATOR itself, internally, before
                                   returning, attempt exactly one bounded
                                   close of that resource?

-- [5F3B-I2A-DESIGN-FU3C] the creator supplies ONE resource-kind-specific
-- OBSERVED POSTCONDITION field -- never a generic verdict:
direct_child_reported_exit  bool | None   -- RUNTIME kind only. None iff
                                             cleanup_attempted is False;
                                             exact bool iff True
reached_closed               bool | None  -- BROKER kind only. Same rule.

-- cleanup_verified_success is NO LONGER a constructor field on either
-- observation. It is a READ-ONLY property AIDO's own code computes,
-- identically for both kinds:
--     cleanup_verified_success := cleanup_attempted and (postcondition is True)
-- where `postcondition` is direct_child_reported_exit (runtime) or
-- reached_closed (broker). The creator cannot set this value directly, by
-- any name, at any layer.
```

Plus, unchanged, the resource kind's own independent creation-failure facts
that already exist and are the "primary creation failure classification":
for runtime, the already-accepted `launch_shape_valid` /
`required_flags_accepted` / `lf_jsonl_correlation_succeeded` /
`observed_pi_version` (unmodified by this correction); for broker, one new
bounded fact, `start_attempted: bool` — whether the underlying start call was
even reached, distinguishing "failed before touching the resource at all"
from "the start call itself failed partway" — mirroring the runtime side's
existing granularity rather than inventing a free-text reason.

**[5F3B-I2A-DESIGN-FU3B, `cleanup_verified_success` column corrected by
FU3C] Exactly four constructible states — every physically possible outcome
representable, no forced lie, no double call, no crossing handle, no
creator-supplied verdict:**

| `session` | `resource_created` | `cleanup_attempted` | postcondition field | derived `cleanup_verified_success` | Meaning | Who may call a close primitive |
|---|---|---|---|---|---|---|
| not `None` | forced `True` | forced `False` | forced `None` | forced `False` | **Ownership transferred.** A fully correlated, trusted session exists; the creator performed no internal close on it | the **controller**, later, via the existing unchanged `shutdown_runtime`/`shutdown_broker` (gated by §9.4, unaffected) |
| `None` | `False` | forced `False` | forced `None` | forced `False` | **Nothing created.** Failed before touching any resource (e.g. `mkdir`/argv-build/constructor failed first) | nobody — there is nothing to close |
| `None` | `True` | `True` | exact `bool` — `direct_child_reported_exit`/`reached_closed` | **derived**: `postcondition is True` | **Creator retained ownership and attempted exactly one self-close.** No trusted session could be established; the creator attempted its one bounded close before returning, and reports only the narrow, resource-kind-specific postcondition it actually observed (§9.3.1) — never a verdict | the **creator**, internally, exactly once — the controller has no callable for this branch at all |
| `None` | `True` | `False` | forced `None` | forced `False` | **[FU3B] `PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT`.** A resource was created, no trusted session was established, and the creator's own bounded cleanup primitive was **never invoked** — e.g. the creator itself failed or was interrupted between creating the resource and reaching its own cleanup step. Constructible and explicitly named, not refused: refusing it would force the exact lie or evidence-loss this correction exists to prevent | **nobody.** Zero cleanup calls occur — not by the creator (never invoked), not by the controller (no callable exists for this branch, exactly as row 3) |

Row 4 is the physically real case FU3A's own first draft of this table
incorrectly marked unconstructible; it is corrected here. It is **not** a
weaker state than row 3 — it is a **more honest** one: the resource may
still be live, and the evidence says so plainly (`FAILED:
PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT`) rather than collapsing into a
generic malformed-adapter code. `closure_satisfied=False` unconditionally for
this row (§9.3's evidence/closure paragraph below), and the resource kind's
own independent creation-failure facts (`launch_shape_valid`/etc. for
runtime, `start_attempted` for broker) remain separately recorded alongside
it, never overwritten by the fact that no cleanup was attempted.

**Why this structurally forecloses both FU3A defects, not merely by
policy — unaffected by FU3B's row-4 addition:**

- *Partial-handle provenance* is closed **by elimination** — there is no
  handle type left to forge, cache, or substitute across invocations. The
  only object with correlation identity that ever crosses the boundary is
  the fully-formed `session`, and that path is already governed, unchanged,
  by §9.4's foreign-session refusal.
- *Double cleanup* is closed **mechanically, not by discipline.** In the
  "ownership transferred" row the creator is *forbidden* from having
  attempted a close (`cleanup_attempted` forced `False` — a creator that
  both hands back a live trusted session *and* claims it already closed
  something is refused at construction, a case the original three-state
  draft never even considered). In **both** "creator retained ownership"
  rows (3 and 4 — whether or not the creator got as far as attempting its
  one self-close) the controller has **no adapter callable to invoke at
  all** — `close_partial_runtime_resource`/`close_partial_broker_resource`
  are **removed entirely**, not merely "not called by policy." Row 4 does
  not reopen this: it adds a new *reason* the creator branch can be reached
  with zero cleanup calls (the creator never got to attempt one), never a
  new *caller*. There is structurally only ever one possible caller of a
  close primitive per branch, so no proof of repeat-close safety is ever
  required, because no path exists for a repeat call to occur — in row 4
  there is no path for **any** cleanup call, by anyone, to occur at all.

**The "exactly one attempt" property is a requirement on the creator's own
internal implementation, honestly scoped.** Nothing outside the creator can
mechanically verify it made only one attempt before returning — this is the
same class of trust-boundary residual O1's own accepted design already
carries (§9.1: "attempts exactly one bounded `PiRpcSupervisor.shutdown()`" is
a documented discipline of `o1.handshake`, not something its caller
independently proves). What *is* new and mechanically enforced here, beyond
O1's own shape, is that the *controller* structurally cannot add a second
attempt on top of the creator's — the old handle-based design could have.

**A bare raise remains a contract violation, named as one — but is no longer
the only honest option for this scenario.** `_invoke` still catches a raise,
the controller still holds no authority (no observation object was ever
returned, nothing to act on), and the run still refuses as
`*_AUTHORITY_UNAVAILABLE`. The controller genuinely **cannot** distinguish,
from a bare raise alone, "raised having created nothing" from "raised having
created something and abandoned it without even attempting a close" — both
present identically (no observation exists), and both are treated with the
same conservative, honest refusal. **[5F3B-I2A-DESIGN-FU3B]** Row 4 above is
the *preferred*, more informative alternative for exactly this scenario: an
adapter that catches its own internal failure between creating the resource
and reaching its own cleanup step, and is therefore *able* to determine
`resource_created=True`, should return the well-formed row-4 observation
(`cleanup_attempted=False`) rather than let the exception propagate as a bare
raise. Both paths are equally safe — zero cleanup calls, `closure_satisfied
=False`, terminal PASS impossible either way — but row 4 preserves evidence
a bare raise discards. Neither is *required* over the other by construction
(a raise remains a legitimate, if less informative, failure mode this
contract must still tolerate); row 4 exists so a well-behaved adapter is not
forced to choose between lying and raising when it already knows the truth.

**Evidence and closure semantics.** `RuntimeTeardownStatus`/
`BrokerShutdownStatus` gain three status texts for the "creator retained
ownership" branches — `CLOSED_BY_CREATOR_VERIFIED` (`closure_satisfied=True`,
from the **derived** `cleanup_verified_success=True`, row 3),
`FAILED:CLOSED_BY_CREATOR_UNVERIFIED` (`closure_satisfied=False`, from the
**derived** `cleanup_verified_success=False`, row 3), and
`FAILED:PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT`
(`closure_satisfied=False`, row 4, `authority_available=False` — no cleanup
call was ever possible, by anyone) — replacing the single collapsed
`closed_by_creator: bool` this correction supersedes. **[FU3C]** The
controller (or the observation's own read-only property — the exact
implementation split is an implementation choice, not prescribed here) is
the **only** code that ever computes `cleanup_verified_success`; the value is
never accepted as a constructor argument from the creator at any layer.
`resource_created`/`cleanup_attempted`/the resource-kind-specific
postcondition/the derived `cleanup_verified_success` are recorded in the
evidence body alongside the resource kind's own independent creation-failure
facts, which are **never** overwritten or masked by the cleanup outcome — the
two remain orthogonal fields in the same observation, exactly as O1's own
`CompatibilityHandshakeError` already keeps the original failure and the
shutdown-attempt facts separate (§9.1).

**Malformed values.** `resource_created` and `cleanup_attempted` must be
exactly `bool` (`type(x) is bool`, reusing the existing `require_exact_bool`
helper, unchanged). **[FU3C]** The resource-kind-specific postcondition field
(`direct_child_reported_exit` for runtime, `reached_closed` for broker) must
be exactly `bool` when `cleanup_attempted is True`, and `None` is valid
**only** when `cleanup_attempted is False` — a creator that claims it
attempted its one bounded close must report a definite observed
postcondition, never "attempted, result unknown," and never a non-bool
truthy/falsy stand-in (`1`, `"true"`, or any other coercible value is refused
outright, exactly the `require_exact_bool` discipline already used
throughout this package — no exception, no shortcut for "the call merely
returned without raising"). Every malformed or inconsistent combination is
refused at construction (`ObservationError`), never coerced. This bool-typing
rule remains the *entire* constraint linking `resource_created`/
`cleanup_attempted`/the postcondition field — FU3A's draft additionally
required `cleanup_attempted=True` whenever `session is None and
resource_created is True`, which is exactly the extra business-rule refusal
row 4 corrects (unaffected by FU3C); a `resource_created=True,
cleanup_attempted=False` combination remains valid by construction (row 4),
with the postcondition field correctly forced to `None`.

### 9.3.1 The creator reports observed components; AIDO derives the verdict (FU3B postcondition, corrected by FU3C)

**FU3B's own version of this subsection stated the postcondition as a
*rule* the creator's `cleanup_verified_success=True` had to obey.** That
still let the creator supply the generic verdict directly — a well-meaning
but wrongly-implemented adapter could set `cleanup_verified_success=True`
whenever its close call merely returned without raising, and nothing in the
FU3B *type* prevented it; only the FU3B *prose* forbade it. This is exactly
the class of defect §6 (H1) already closed once: an adapter must never be
trusted to compute and hand over the final verdict itself — it must hand
over the narrow, individually-checkable **observed component**, and AIDO's
own code, written once, computes the verdict identically every time.

**[5F3B-I2A-DESIGN-FU3C] `cleanup_verified_success` is removed as a
creator-supplied field.** In its place, the creator supplies exactly one
resource-kind-specific **observed postcondition** — the same postcondition
this design already accepts for the ordinary (ownership-transferred)
teardown path, applied identically here so the two paths cannot silently
diverge in what "verified" means:

- **Runtime:** `direct_child_reported_exit: bool | None` — the same fact
  `RuntimeShutdownObservation.orchestrator_direct_child_reported_exit`
  already reports for ordinary teardown: AIDO's own direct child process
  reported exit.
- **Broker:** `reached_closed: bool | None` — the same fact
  `BrokerShutdownObservation.reached_closed` already reports: the broker's
  own lifecycle reaching `STATE_CLOSED`. Frozen `BrokerServer.shutdown()`
  itself already distinguishes this outcome from an incomplete one
  (`experiments/pi_external_runtime_ar2/ar2/broker.py:700-703`: reaching
  `STATE_CLOSED` only when `worker_termination_observed` holds, else
  `STATE_TEARDOWN_INCOMPLETE`).

**AIDO derives the generic verdict, once, the same way for both kinds and
both call sites (creator self-close and ordinary teardown alike):**

```text
cleanup_verified_success := cleanup_attempted and (postcondition is True)
```

Using `is True` (identity against the singleton), never bare truthiness —
`1`, `"true"`, or any other value that merely *evaluates* truthy is refused
at construction (§9.3's "Malformed values" paragraph), not silently accepted
as `True`. A close call that returns without an exception but does not
confirm the postcondition must report the field as exactly `False`, never
omit it, never report `None` while `cleanup_attempted=True`, and never let
"no exception" stand in for "verified."

**Why deriving rather than trusting closes the gap FU3B's prose alone could
not.** The postcondition field's very *name* ties it to one specific,
narrowly measurable event — there is no field called "success" or "verified"
anywhere in the creator-facing contract for a future implementer to
misjudge. The one place the AND-derivation lives is AIDO's own code
(equivalently, a read-only property on the observation object), never
reimplemented per adapter or per resource kind — exactly how H1's five
components feed one conjunction AIDO alone evaluates (§6.3(b)).

**Scope is preserved, not widened.** The derived `cleanup_verified_success`
remains, exactly like every other closure fact in this design, a claim about
**AIDO's own direct resource** (the process or pipe it created) — never
about a descendant process, provider inference, or GPU work. Where the
underlying primitive genuinely cannot observe more than "AIDO's own close
call returned and the direct-child/lifecycle postcondition held," that is
exactly what a derived `True` may mean and nothing stronger; the existing
`NOT OBSERVED` wording for backend/descendant lifetime (§9.5,
`backend_inference_lifetime_after_teardown`/
`descendant_process_lifetime_after_teardown`) is unchanged and applies
identically to this path.

### 9.3.2 Required adversarial analysis (FU3A, extended by FU3B; cells updated for FU3C's derived verdict)

| # | Case | Cleanup owner | # of cleanup calls | Evidence recorded | `closure_satisfied`? | Terminal `CATEGORY_B_GATE_PASSED` possible? |
|---|---|---|---|---|---|---|
| 1 | Nothing created | nobody | 0 | Row 2: `resource_created=False, cleanup_attempted=False (forced), postcondition=None (forced), derived cleanup_verified_success=False`; teardown status `NOT_REQUIRED` | `True` (nothing owed) | **No** — the corresponding creation gate already failed for this run |
| 2 | Created + cleanup **not attempted** | **nobody.** Not the creator (its own cleanup primitive was never invoked); not the controller (no callable exists for this branch) | **0** | Row 4: `resource_created=True, cleanup_attempted=False, postcondition=None (forced), derived cleanup_verified_success=False`; status `FAILED:PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT`; the resource-kind's own independent creation-failure facts (e.g. `launch_shape_valid=False`, or broker `start_attempted`) recorded separately and never masked | `False` | No |
| 3 | Created + cleanup attempted + **verified success** | creator (internal) | exactly 1, by creator | Row 3: `resource_created=True, cleanup_attempted=True`, postcondition (`direct_child_reported_exit`/`reached_closed`) `=True` (exact bool, the creator's OWN observed fact — never a verdict) → **derived** `cleanup_verified_success=True` per §9.3.1's `cleanup_attempted and (postcondition is True)`; status `CLOSED_BY_CREATOR_VERIFIED`; primary failure facts recorded independently | `True` | **No** — the run's own creation gate already failed; a satisfied closure only means the refusal is clean, never that it can become a pass |
| 4 | Created + cleanup attempted + **failure/unverified** | creator (internal) | exactly 1 (attempted, unverified) — controller calls none | Row 3: postcondition `=False` (exact bool) → **derived** `cleanup_verified_success=False`; status `FAILED:CLOSED_BY_CREATOR_UNVERIFIED`; primary failure facts unchanged, never masked | `False` | No (doubly: the creation gate already failed, and closure is independently unsatisfied) |
| 5 | Full trusted session + ordinary controller teardown | controller (existing, unchanged flow) | exactly 1, by controller, at end-of-run, exactly as already accepted | Row 1: `resource_created=True (forced), cleanup_attempted=False (forced), postcondition=None (forced), derived cleanup_verified_success=False`. This derived value is irrelevant to this row — closure comes from the controller's own unchanged `shutdown_runtime`/`shutdown_broker` result, not from this derivation; teardown status `SUCCEEDED`/`FAILED:RUNTIME_TEARDOWN_FAILED` per existing unchanged logic | per existing unchanged logic | **Yes** — the only branch where PASS was ever reachable, unaffected by FU3A, FU3B or FU3C |
| 6 | Foreign full session (§9.4, not reopened) | nobody — refused | 0 | `RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION`/`BROKER_SHUTDOWN_REFUSED_FOREIGN_SESSION` (§9.4, unchanged); the creator never self-closes something it returns as a valid full session (`cleanup_attempted` forced `False`, row 1) — the refusal to act is entirely the controller's own §9.4 decision | `False` | No |
| 7 | Creator **raises** before creating anything | nobody (nothing exists) | 0 | No observation was ever returned → `*_AUTHORITY_UNAVAILABLE`. Identical, from the controller's view, to case 8 — see below | `False` | No |
| 8 | Creator **raises** after resource creation, before reaching its own cleanup step | **unknown to the controller** — the resource may still be live, uncleaned | 0 (by the controller; the creator's own cleanup primitive was never reached, matching case 2's substance, but reported as a bare raise instead of a well-formed observation) | Identical to case 7 — no observation object exists, so the controller **cannot** distinguish "raised having created nothing" from "raised having created something and abandoned it." Both are refused identically and conservatively (an honest, stated residual). Case 2's row 4 is the **preferred** alternative for this exact scenario: an adapter that catches its own failure here and reports it via row 4 instead of raising preserves strictly more evidence for an identical safety outcome | `False` | No |
| 9 | Malformed bool/`None`/truthiness combinations | n/a | 0 | `ObservationError` at construction — `require_exact_bool` on `resource_created`/`cleanup_attempted`; the postcondition field must be exactly `bool` when not `None`, and `None` only when `cleanup_attempted=False` (permitting row 4, §9.3's "Malformed values" paragraph) — see §9.3.3 for the postcondition-specific malformed cases this table row summarizes → `MALFORMED_ADAPTER_RESULT` at `_invoke` → bounded gate failure. Never silently coerced into a passing fact | `False` | No |

**Case 8 is the one place this design remains honestly imprecise, and says
so rather than hiding it.** A bare raise carries strictly less information
than a well-formed row-4 observation, and the controller cannot recover the
missing distinction after the fact — this is the same class of residual
already accepted throughout this design (adapters are AIDO's own future
code inside the trust boundary; a raise is a defect to fix in the adapter,
not something this contract can detect from outside). What FU3B adds is not
a way to eliminate that imprecision, but a way to let a *well-behaved*
adapter avoid it entirely by preferring case 2's reporting path.

### 9.3.3 Required adversarial analysis (FU3C — postcondition-derivation level)

FU3B's §9.3.2 above tests the four *branches* of §9.3's table. This
subsection tests the **derivation** within row 3/4 specifically — the exact
concern FU3C was re-opened to close: can a creator (through any combination
of malformed, coerced, or under/over-supplied values) cause AIDO to record a
`cleanup_verified_success` that does not match
`cleanup_attempted and (postcondition is True)` exactly?

| # | Case | Derived `cleanup_verified_success` | `closure_satisfied`? | Terminal `CATEGORY_B_GATE_PASSED` possible? |
|---|---|---|---|---|
| 1 | Cleanup call returns normally but the runtime **direct child did NOT report exit** | `cleanup_attempted=True, direct_child_reported_exit=False` (exact bool — the creator's own close call completed and determined non-exit, not merely "didn't raise") → derived **`False`** | `False` (status `FAILED:CLOSED_BY_CREATOR_UNVERIFIED`) | No |
| 2 | Cleanup call returns normally but the broker reaches **`STATE_TEARDOWN_INCOMPLETE`** | `cleanup_attempted=True, reached_closed=False` → derived **`False`** | `False` | No |
| 3 | Runtime **direct child exit observed** | `cleanup_attempted=True, direct_child_reported_exit=True` (exact bool, actually confirmed) → derived **`True`** | `True` | **No** — the creation gate for this run already failed; a satisfied closure never becomes a pass on its own |
| 4 | Broker **`STATE_CLOSED` observed** | `cleanup_attempted=True, reached_closed=True` → derived **`True`** | `True` | No (same reasoning as case 3) |
| 5 | Adapter tries to supply `1`, `"true"`, or another truthy non-`bool` for the postcondition field | Refused at construction — `type(x) is bool` fails; `ObservationError` → `MALFORMED_ADAPTER_RESULT` at `_invoke`. **No derived value is ever computed**; the observation does not exist | `False` (bounded gate failure, not a closure computation) | No |
| 6 | `cleanup_attempted=False` with a **non-`None`** postcondition | Refused at construction — the "attempted=False requires postcondition=None" rule (§9.3's "Malformed values" paragraph) is violated; `ObservationError` → `MALFORMED_ADAPTER_RESULT` | `False` | No |
| 7 | `cleanup_attempted=True` with **postcondition=`None`** | Refused at construction — the "attempted=True requires an exact-bool postcondition" rule is violated (`None` is not a substitute for "the attempt's outcome is unknown"); `ObservationError` → `MALFORMED_ADAPTER_RESULT` | `False` | No |
| 8 | Stranded / no cleanup attempt (§9.3 row 4, unchanged by FU3C) | `cleanup_attempted=False`, postcondition forced `None` → derived **`False`** (though the recorded status is `PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT`, not `CLOSED_BY_CREATOR_UNVERIFIED` — the STATUS distinguishes "never attempted" from "attempted and failed"; the derived boolean alone would not, which is exactly why §9.3's status text, not the bare derived boolean, is what the evidence body records) | `False` | No |
| 9 | Full-session ordinary teardown (§9.3 row 1, unchanged by FU3C) | `cleanup_attempted` forced `False` → derived **`False`**, but **irrelevant**: this row's `closure_satisfied` comes entirely from the controller's own unchanged `shutdown_runtime`/`shutdown_broker` call result, never from this derivation | per existing unchanged logic | **Yes** — the only branch where PASS was ever reachable |

**What this table proves that §9.3.2 alone could not.** Cases 1/2 show the
exact scenario the re-opening named — a close call that "returns normally"
— cannot produce a `True` verdict unless the postcondition field itself is
`True`; "returned without raising" and "postcondition observed" are now
mechanically distinct inputs, and only the second can ever produce a
`True` derivation. Cases 5–7 show every malformed/coerced/inconsistent
input is refused at construction, before any derivation is computed at all
— there is no code path in which a non-bool, an inconsistent `None`, or a
missing postcondition silently becomes a passing verdict. Cases 3/4 confirm
the positive path still works exactly as intended. Cases 8/9 confirm the
two branches FU3B and the original FU3A design already established are
untouched by this derivation change.

### 9.4 Possession is not authority — foreign sessions are refused, never "attempted but uncounted"

**The gap.** I2B-FU1's `_close_runtime`/`_close_broker` already compute
`session_trusted` — `False` when the returned `RuntimeSession`/`BrokerSession`
does not carry this run's own `run_id`/matching `broker_session_id`. But when
`session_trusted` is `False`, the current code still **calls the shutdown
adapter anyway**, reasoning (in its own comment) that "abandoning it would
strand a resource" — it only withholds *counting* the result toward
`closure_satisfied`. That is a **live, side-effecting action taken against a
resource this run did not prove it owns.** If the foreign session genuinely
belongs to another, possibly still-active invocation, this run's shutdown
call can race that invocation's own lifecycle or terminate a resource it
still needs — interference this design's entire `run_id`-binding discipline
exists to prevent everywhere else. "Merely obtained an object back from a
call" (possession) has been silently doing duty as "authorized to act on it"
(authority); those must be mechanically separate.

**The fix — refuse to act, never merely refuse to count.** When
`session_trusted` is `False`, the shutdown/close adapter for that session
**MUST NOT be called at all.** `RuntimeTeardownStatus`/`BrokerShutdownStatus`
gain a distinct, honestly-named terminal state —
`RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION` /
`BROKER_SHUTDOWN_REFUSED_FOREIGN_SESSION` — with `attempted=False`,
`authority_available=False`, `closure_satisfied=False`. This is a
**narrowing**, not a weakening: the run now does strictly less to a resource
it cannot prove is its own, exactly matching "does not clean up a resource it
did not create."

**Why this is safe to do uniformly, even for the narrower case the old
comment worried about.** The old comment's concern was specifically: what if
`create_broker`/`launch_runtime` genuinely created a **brand-new** resource
for **this** invocation, but mislabeled it with a stale/wrong `run_id` when
constructing the returned session object (an adapter labeling bug, not a
truly foreign live resource)? The controller has **no way to mechanically
distinguish** that case from "the adapter actually returned a handle to some
other run's pre-existing resource" — both present identically as "an object
whose `run_id` does not match this run's own." Since the two cannot be told
apart from here, and since adapters are AIDO's own future code inside the
trust boundary (never a hostile party, per this package's own established
scope statement), the correct, requested behavior is uniform refusal for
both: a real labeling bug on a freshly-created resource becomes a genuinely
leaked resource this run cannot close — an adapter defect to fix in the
adapter, not something this controller should paper over by guessing that
"this one is probably safe to touch."

**Mechanical binding, restated precisely.** Authority to close a session
requires **all** of:

1. the session's `run_id` equals the controller's own freshly-minted `run_id`
   for **this** invocation (already the existing check);
2. for a runtime session, its `broker_session_id` equals **this** invocation's
   own `broker_session_id` (already the existing check);
3. the session was returned **directly** by the create/launch adapter call
   **this same invocation made** — i.e. it is the exact object identity this
   controller received from its own `create_broker`/`launch_runtime` call,
   never one fetched, cached, looked up, or reconstructed from elsewhere. This
   is enforced structurally, not by an extra field: the controller never
   stores or accepts a session object from any source other than the return
   value of its own creation call in this same `run_category_b_controller`
   invocation.

Value-equality on (1)/(2) remains, honestly, a **correlation** control against
an adapter bug or a stale/leftover object — not authentication against a
hostile adapter (unchanged scope statement, §6.3(e)). (3) is what makes
"possession" (the controller literally holding a Python object) insufficient
by itself: a session object is only ever *acted on* if it is both the
directly-returned result of this invocation's own creation call **and**
carries this invocation's own correlation identifiers.

**Required adversarial offline tests (I2B-FU2):**

- a `launch_runtime` double that returns a `RuntimeSession` carrying a
  **different** `run_id` (simulating a stale/foreign session) → the run
  reaches `RUNTIME_SESSION_MISMATCH` at the launch gate (unchanged), **and**
  `shutdown_runtime` is asserted **never called** (call-counting double),
  **and** `RuntimeTeardownStatus.status_text` reports
  `RUNTIME_SHUTDOWN_REFUSED_FOREIGN_SESSION`, not `SUCCEEDED` and not a
  masked `FAILED`;
- the same for a `create_broker` double returning a foreign-`run_id`
  `BrokerSession` → `shutdown_broker` asserted **never called**;
- a `RuntimeSession` carrying this run's own `run_id` but a **foreign**
  `broker_session_id` (a same-run, wrong-broker substitution) → same refusal,
  same never-called assertion;
- a positive control: a genuinely same-run, same-broker session still closes
  normally, and `shutdown_runtime`/`shutdown_broker` **are** called exactly
  once, proving the refusal is specific to the foreign case and not a general
  regression.

### 9.5 Truthful scope — no backend-cancellation claims

Neither the creator's own observed postcondition
(`direct_child_reported_exit`/`reached_closed`), nor AIDO's
`cleanup_verified_success` derived from it, nor the controller's ordinary
`shutdown_runtime`/`shutdown_broker` result, is, or may ever be read as, a
claim that a descendant process was terminated, that Pi or provider
inference stopped, or that GPU work stopped. The existing
`claim_scope` wording and the
`backend_inference_lifetime_after_teardown: "not observed"` /
`descendant_process_lifetime_after_teardown: "not observed"` fields apply
unchanged to every state introduced by §9.3/§9.4, and no cancellation
mechanism of any kind — thread-kill, process-tree enumeration, a second
attempt, polling — is added anywhere in this correction.

---

## 10. Correlation-id generation failure

`run_id = secrets.token_hex(16)` is currently unguarded. If it raised — an
exhausted OS entropy source being the realistic case — the raw exception would
escape `run_category_b_controller`: neither a `CategoryBControllerInputError` (it
is not a caller-argument error) nor a bounded Category-B outcome. That is an
unbounded leak from a controller whose entire design is bounded refusal.

**Required:** bound it as an ordinary infrastructure failure. Add one gate,
`RUN_CORRELATION`, and one failure code, `RUN_CORRELATION_UNAVAILABLE`. On
failure the run is an `INFRASTRUCTURE_REFUSAL` with `semantic_prompts_sent = 0`,
zero credential reads, zero resources created, and every closure status
`NOT_REQUIRED`. The exception's `str()`/`repr()` is never read or retained,
exactly as `_invoke` already handles adapter exceptions.

A new public exception type is deliberately **not** introduced: keeping this
inside the gate model preserves the accepted property that every bounded
infrastructure failure is a Category-B refusal, and adds no surface.

---

## 11. What remains unchanged

**Three behaviors are further tightened, not merely preserved — recorded
here so none is mistaken for "unchanged."**

1. I2B-FU1's shipped `_close_runtime`/`_close_broker` already detect a
   foreign (`run_id`- or `broker_session_id`-mismatched) session and
   correctly withhold `closure_satisfied`, but they still **call** the
   shutdown adapter against that foreign session before withholding it. §9.4
   tightens this: the shutdown adapter is now **never called** for a foreign
   session at all. This is a narrowing of live-adapter interaction, not a
   reversal of any accepted semantic — `closure_satisfied` was already
   `False` in this case and remains `False`.
2. **[5F3B-I2A-DESIGN-FU3A]** The handle-based partial-cleanup fix this same
   document first proposed in §9.3 (`PartialRuntimeHandle`/
   `PartialBrokerHandle` plus two controller-owned
   `close_partial_*_resource` adapters) is **withdrawn and replaced**, not
   merely refined — it introduced exactly the two authority defects §9.3
   now documents (partial-handle provenance; possible double cleanup). The
   corrected §9.3 returns to O1's own creator-retains-ownership shape:
   no handle crosses into the controller for a partial failure, and the
   creator's one bounded internal attempt is reported as three orthogonal
   facts (`resource_created`/`cleanup_attempted`/`cleanup_verified_success`)
   instead. §9.4 (foreign **full**-session refusal) is unaffected and was
   not reopened by FU3A.
3. **[5F3B-I2A-DESIGN-FU3B]** FU3A's own §9.3 table refused one physically
   real state — a resource created, then the creator failing or being
   interrupted before it could even attempt its own cleanup — forcing a
   truthful adapter to either lie or fall back to a generic, less
   informative refusal code. FU3B makes it constructible and explicitly
   named (`PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT`), with zero cleanup
   calls by anyone and `closure_satisfied` unconditionally `False`. FU3B
   also freezes `cleanup_verified_success=True` to mean the same
   resource-kind-specific postcondition (`orchestrator_direct_child_
   reported_exit` / `reached_closed`) already accepted for ordinary
   teardown — never a bare no-exception return.
4. **[5F3B-I2A-DESIGN-FU3C]** FU3B's freeze of `cleanup_verified_success`
   was stated as a *rule on a creator-supplied field*, which a future
   adapter could still violate by construction (the type accepted any
   `bool | None`). FU3C removes `cleanup_verified_success` as a
   creator-supplied field entirely: the creator now reports only the
   resource-kind-specific observed postcondition
   (`direct_child_reported_exit`/`reached_closed`), and AIDO's own code
   derives the generic verdict — `cleanup_attempted and (postcondition is
   True)` — identically everywhere, mirroring how H1's five components feed
   one AIDO-owned conjunction (§6.3). `PARTIAL_RESOURCE_STRANDED_NO_
   CLEANUP_ATTEMPT` (FU3B) and every other branch of §9.3's table are
   unaffected.

**Preserved from I2B-FU1, all correct and none reopened:**

- broker `READY` before runtime launch, enforced by the type
  (`RuntimeLaunchRequest` is unconstructible from a not-ready or foreign broker
  session);
- per-run `run_id` correlation and session-id binding on every observation;
- the single-observation H1 / `get_commands` relationship, and the
  single-observation H2 / `get_state` relationship;
- four independent launch facts from one launch observation;
- the explicit protocol / extension-error gate;
- teardown → broker shutdown → generated-config cleanup ordering (frozen O1's
  order), attempted on every path;
- teardown, cleanup and evidence all required for a terminal PASS;
- immutable result and evidence surfaces (`MappingProxyType`, canonical
  serialized body, immutable scrub tuple);
- zero semantic prompts, proven by the AST source-regression tests;
- no finite model output-token cap (`aido_requested_max_output_tokens: null`,
  generated `models.json` omits `maxTokens`);
- no generic `AgentRuntime` / `RuntimeAdapter` framework;
- sorted-sequence (never set) command comparison;
- exact-`bool` typing and `type(x) is expected` adapter-boundary checks;
- the truthful claim scope on teardown, and the "not observed" residual fields.

**Unchanged in frozen I2A:** §§6–13 (credential mechanism, environment policy,
config policy, secret lifetime, token invariants, version policy), §14
(Category-A gates), §15 items **1–5 and 7–10**, §16 (the two failure-attribution
paths), §17, §18, §19, §20 (candidate symmetry), §21, §23, §24, §25. Only §15
item 6 is superseded.

**Unchanged and unmodified frozen code:** every module under
`experiments/pi_external_runtime_ar1/`, `.../ar2/`, `.../ar2_o1/` — in particular
`ar2.handshakes.evaluate_extension_identity` (reused, never forked),
`ar2.route_check.check_route_serves_model` (reused unmodified),
`ar2.fixtures.create_disposable_experiment_root` and `ar2.capability` (reused
unmodified). Nothing under `src/`, `tests/`, `projects/` is touched, and
`CLAUDE.md` is not modified.

**Unchanged accepted I1 semantics:** the outcome taxonomy, the hard bar, the
ranking policy, the run-validity/attribution model, and the
`ArtifactSafetyContext` shape.

---

## 12. What this correction does NOT authorize

- No probe prompt, first-turn tool call, or any other semantic prompt.
- No HTTP interceptor, proxy, request-body observer, or wire instrumentation.
- No new Pi capability, no upstream patch, no forked evaluator.
- No generic runtime capability, registry, plugin system, or provider framework.
- No real live adapter — I2B-FU2 remains offline wiring with injected adapters
  and synthetic doubles.
- No backend-cancellation mechanism, process-tree management, or descendant
  enumeration.
- No real-workspace authority, no sibling-project access.
- No candidate model run, no scoring, no ranking, no verdict.

---

## 13. GO / NO-GO

**5F3B-I2A-DESIGN-FU3C: ACCEPT.** The one residual issue named in the
re-opening is closed: the creator can no longer directly supply the generic
`cleanup_verified_success` verdict. It is now removed as a constructor
field; the creator reports only the narrow, resource-kind-specific observed
postcondition (`direct_child_reported_exit` for runtime, `reached_closed`
for broker), and AIDO's own code derives the verdict, always identically,
as `cleanup_attempted and (postcondition is True)` — never bare Python
truthiness, never a "no exception" shortcut (§9.3.1). Every required
invariant from the re-opening holds exactly: the postcondition field is
forced `None` when `cleanup_attempted=False` and must be an exact `bool`
when `True`; no truthy non-`bool` is ever accepted;
`CLOSED_BY_CREATOR_VERIFIED` requires the derived postcondition `True`;
`FAILED:CLOSED_BY_CREATOR_UNVERIFIED` requires `attempted=True` and derived
`False`; `PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT` (FU3B) is untouched;
`NOT_REQUIRED` and the full-trusted-session/foreign-session paths are
untouched; no partial handle or controller-owned partial-close authority was
introduced. The nine required postcondition-level adversarial cases (§9.3.3)
all resolve to: a close call that merely "returns normally" can never derive
`True` unless the postcondition itself is `True` (cases 1–2 vs. 3–4), every
malformed/coerced/inconsistent input is refused before any derivation is
computed (cases 5–7), and the two branch-level states FU3B established
remain unaffected (cases 8–9). Nothing outside §9.3/§9.3.1/§9.3.2/§9.3.3 was
reopened — §5, §6, §7, §8, §9.1, §9.2, §9.4, §9.5, §10 all stand exactly as
FU3B left them.

**5F3B-I2A design family: FREEZE.** Four successive re-openings of §9.3
(the initial correction, then FU3A, FU3B, FU3C) each found and closed exactly
one class of defect, and each subsequent re-opening confirmed the prior
corrections held under adversarial pressure without needing to reopen them.
FU3C's own fix introduces no new authority type, no new controller-owned
call, and no new adapter surface beyond renaming one field into two
narrower ones — there is no known further defect class in §9.3, and no
open issue remains anywhere in §§1–13 of this document. The design is ready
to freeze pending only I2B-FU2's own implementation and offline-test pass.

**5F3B-I2A-DESIGN-FU3B: ACCEPT**, superseded only within §9.3.1 by FU3C as
recorded above. The stranded-state fix itself is untouched and remains
correct: `PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT` is still
constructible, still records zero cleanup calls by anyone, and still forces
`closure_satisfied=False`.

**5F3B-I2A-DESIGN-FU3A: ACCEPT**, superseded only within §9.3 by FU3B (and,
for the verdict-derivation detail, by FU3C) as recorded above. Both defects
FU3A's own re-opening named remain closed: partial-handle provenance by
elimination (no partial-handle type remains in the design at all), and
double cleanup mechanically (only one possible caller of a close primitive
exists per branch, never both, and no repeat-close-safety assumption is
required anywhere). FU3's HOLD on §9.3, placed by FU3A, narrowed by FU3B,
and narrowed again by FU3C to exactly the verdict-derivation issue, is now
fully lifted.

**5F3B-I2B-FU2 implementation: GO.** The design blockers are resolved here,
the slice being corrected is not frozen, and every change is a narrowing of
an existing shape rather than a new capability. FU2's required content is
exactly §5.3 (observability, corrected `sourceInfo.source` shape), §6.3 (H1
proof), §7.3 (credential ordering), §8 (workspace authority), §9.3
(FU3A/FU3B/FU3C-corrected, handle-free, four-state creator contract —
`RuntimeLaunchObservation`'s in-place correction plus the new
`BrokerCreationObservation` type, both now carrying the resource-kind-
specific postcondition field rather than a creator-supplied verdict), §9.3.1
(AIDO-derived `cleanup_verified_success`), §9.4 (possession-vs-authority /
foreign-full-session refusal) and §10 (correlation-id bounding) — plus their
offline tests, including the mandatory E19-shape regression case (§5.3), the
four §9.4 adversarial foreign-session tests, the nine §9.3.2 branch-level
adversarial cases, and the nine §9.3.3 postcondition-derivation adversarial
cases. Nothing else.

**Category-B live execution: NO-GO.** Unchanged. No real adapter exists for any
live boundary, I2B-FU2 has not landed, and a future live phase requires its own
explicit go/no-go.

**5F3B-Q1 / Q2: NO-GO.** Unchanged from 5F3B §26 and I2A §25.

**Real-workspace authority: NO-GO.** Unchanged from 5F3B §22.1 and I2A §22.

---

## Appendix: final report checklist

| Item | Result |
|---|---|
| Live activity | **None.** No Pi/Node process, no socket, no model call, no network request, no credential read, no candidate run |
| Frozen evidence inspected | E1–E18 (§2) plus E19–E22, added in this re-opening (§5.2), including two **real captured live-run records** (AR2 R1 against Pi 0.84.2, O1 against Pi 0.84.3) |
| Tool-registry contradiction | **REAL**, and doubly so: unprovable (§5.1 Defect 1) **and** unsatisfiable (§5.1 Defect 2) |
| Old statement | I2A §15 item 6, **left verbatim** and marked `SUPERSEDED BY` this document (§5.4) |
| Corrected observability contract | §5.2 — A-1/A-2 offline, B-1/B-2 live (provenance-partitioned on `sourceInfo.source`, corrected from an earlier, itself-unsatisfiable top-level-`source` draft), registry contents recorded as an explicit non-observation. Satisfiability proven against the genuine E19–E22 shape, not only a synthetic double |
| H1 proof contract | §6.3 — decompose into the frozen rule's five components, AIDO recomputes the verdict, offline differential conformance against the frozen evaluator, no raw RPC text retained |
| Credential-read ordering | §7 — route descriptor, workspace authority and correlation id all move **before** the credential boundary; unknown candidate ⇒ **zero** reader invocations |
| Synthetic workspace authority | §8 — one qualification-minted `QualificationRunWorkspace`; the raw `workspace_root`/`experiment_root` string parameters are removed |
| Creator partial-failure contract (superseded within this document, three times) | §9.3's first draft (`live_resource_created`/`cleanup_handle`/controller-owned second close) closed §9.2's exhaustiveness gap but introduced partial-handle provenance and double-cleanup defects; FU3A's replacement then marked one physically real state unconstructible, closed by FU3B; FU3B's own `cleanup_verified_success` field still let the creator supply the generic verdict directly, closed by FU3C |
| Creator partial-failure contract (FU3A+FU3B+FU3C, current) | §9.3 — no handle crosses the boundary; the creator retains ownership and performs at most one internal bounded close, reporting `resource_created`/`cleanup_attempted`/one resource-kind-specific **observed postcondition** (never a verdict); ownership transfers to the controller only when a full trusted session is established. **Four** constructible states (FU3B added `PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT`), no forced lie, no double call, no creator-supplied verdict |
| `cleanup_verified_success`, AIDO-derived | §9.3.1 (FU3B's freeze corrected by FU3C) — removed as a creator-supplied field; AIDO's own code derives it as `cleanup_attempted and (postcondition is True)` from the narrow `direct_child_reported_exit`/`reached_closed` fact the creator actually observed, mirroring H1's component-then-conjunction pattern (§6.3) |
| Adversarial analysis (branch level) | §9.3.2 — nine required counterexamples (FU3A's set, extended per FU3B's exact required list; cells updated for FU3C's derived verdict), each resolved: cleanup-call count, authority owner, evidence, `closure_satisfied`, terminal-PASS reachability |
| Adversarial analysis (postcondition-derivation level) | §9.3.3 (FU3C) — nine required counterexamples proving a close call that merely "returns normally" can never derive `True` unless the postcondition itself is `True`, and every malformed/coerced/inconsistent input is refused before any derivation is computed |
| Possession vs. authority (full session) | §9.4, not reopened by FU3A, FU3B or FU3C — a foreign (`run_id`/`broker_session_id`-mismatched) session is **never** passed to the shutdown adapter, not merely excluded from `closure_satisfied`; four adversarial regression tests required |
| Correlation-id failure | §10 — bounded as `RUN_CORRELATION_UNAVAILABLE`, an ordinary zero-prompt refusal |
| 5F3B-I2A-DESIGN-FU3C | **ACCEPT** |
| 5F3B-I2A design family | **FREEZE** |
| 5F3B-I2A-DESIGN-FU3B | **ACCEPT** (superseded only within §9.3.1, by FU3C) |
| 5F3B-I2A-DESIGN-FU3A | **ACCEPT** (superseded only within §9.3, by FU3B/FU3C) |
| I2B-FU2 implementation | **GO** |
| Category-B live execution | **NO-GO** |
| Q1 / Q2 | **NO-GO** |
| Real-workspace authority | **NO-GO** |
