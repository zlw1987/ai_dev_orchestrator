# Phase 5F3B-HARNESS-CFG1 — Isolating the Pi Launch-Configuration Hypothesis

**DESIGN / SOURCE INSPECTION ONLY.** No production code or test was modified. Pi
was not launched. B300 was not contacted. No model was called. No credential or
endpoint value was read. Q1/Q2/Q3 were not re-run and their nine primary
artifacts were opened read-only. DX1 was not designed or run. M4 was not entered.
`CLAUDE.md` was not modified. Nothing was committed.

**This revision incorporates 5F3B-HARNESS-CFG1-DESIGN-FU1** — live-runner authority,
lifecycle and interpretation closure. FU1 does not reopen the compat experiment
(§7 arms, schedule, model, task, and the F1 separation are unchanged). It
records the reviewer's F2 decision as frozen (§0.1), and freezes the per-run
lifecycle state machine (§16), resource ownership (§17), partial-failure
semantics (§18), the cross-run contamination/halt rule (§19), evidence-versus-
cleanup ordering (§20), secret/diagnostic containment (§21), and CFG1 record
authority (§22). It also corrects the run classification for unexpected tool
activity (§12), the `get_state` manipulation check (§8.2), and the offline T-3
network-safety rule (§11.3). The itemized changelog is §23.

**This revision also incorporates 5F3B-HARNESS-CFG1-DESIGN-FU2** — closing
stage-level durable-output filesystem authority. FU2 does not reopen the compat
experiment, the lifecycle steps L0–L30 (except integrating the new stage-output
authority at L0), the resource-ownership model, the partial-failure table, the
admission/halt rule, or record semantics beyond the narrow corrections below.
It exists because independent review found `stage_execution_id` — a value the
future live authorization supplies and FU1 used directly inside a filesystem
path — had no mechanically closed domain, so a malformed value (`".."`, an
absolute or drive-qualified path, a UNC form, an embedded separator, a NUL or
control character) could turn an identifier into indirect path authority. FU2
freezes an exact identifier grammar and a fixed, module-owned results root
(new §16.3), a mechanical containment proof and existing-directory refusal
(§16.3), and a single immutable in-memory `CFG1StageOutputAuthority` value that
is the only source of run/stage output paths (§16.3, §17, §22.4). It adds the
corresponding record-binding and cross-field-invariant closure (§22.3) and new
required offline regressions (§11.3). It also clarifies the §22.3 OBS1
re-validation sentence for the unavailable-activity case, and records three
implementation uncertainties independent review resolved without touching any
frozen module (new §7.5). The itemized changelog is §24.

**This revision also incorporates 5F3B-HARNESS-CFG1-DESIGN-FU3** — closing
stage-output root provenance, authority forgery, and durable-artifact binding.
FU3 does not reopen the compat experiment, the L0–L30 lifecycle (beyond the
consumption-boundary re-proof already implicit in every path-deriving call),
the resource-closure/admission/halt model beyond one narrow carve-out (§19.2),
the classification/interpretation matrix, the `stage_execution_id` grammar, or
schedule-derived filenames. It exists because independent review found three
gaps in FU2's mechanism: (1) proving an execution directory is a resolved child
of a *resolved* results root proves nothing if the lexical results root itself
has been redirected by a symlink or reparse point — both sides resolve through
the same redirect and the check still passes; (2) `frozen=True` on
`CFG1StageOutputAuthority` prevents mutation but not direct construction, so
calling it "the only source of output paths" was not mechanically true; and
(3) payload-only record validation can prove a record's *declared* identity is
internally consistent without ever proving that file is still sitting where it
claims to sit. FU3 freezes an explicit root-provenance proof separating
package-owned infrastructure (`RESULTS_ROOT`) from stage-owned evidence
namespace (the execution directory) (new §16.3.0, rewritten §16.3.2), a
process-local mint registry that makes `CFG1StageOutputAuthority` valid-by-
construction and unforgeable (rewritten §16.3.3), mandatory consumption-
boundary re-proof before every filesystem-sensitive stage-output operation
(extended §16.3.4), and a separate, read-only, offline, post-hoc
durable-artifact binding verifier that is never consulted by the live runner
and grants no authority (new §22.5). It narrows T-13's and T-21's claims to
what payload-only validation actually proves and adds adversarial regressions
T-23–T-37 (§11.3, §22.5). The itemized changelog is §25.

**This revision also incorporates 5F3B-HARNESS-CFG1-DESIGN-FU4** — closing
final output consumption, schedule binding, and authority-lifetime mechanics.
FU4 does not reopen the compat experiment, the L0–L30 live-resource lifecycle,
the classification/interpretation matrix, the `stage_execution_id` grammar,
`RESULTS_ROOT`'s leaf provenance proof, the mint registry itself, the
consumption-boundary re-proof, or post-hoc artifact binding's core semantics —
it closes five remaining gaps in how those pieces are actually *consumed*.
Independent review found: (1) a bare path returned by a helper was, once
returned, indistinguishable from any other string — nothing stopped a writer
from accepting one directly, which is caller convention, not a mechanical
boundary; (2) `run_record_path(authority, run_ordinal, arm_id)` still let a
supported caller pick `arm_id` independently of the frozen schedule; (3)
`RESULTS_ROOT` establishment could `mkdir` before the trusted package
directory's own continued provenance was re-proven, so a redirected package
ancestor could get a foreign `results/` created under it before the later
proof ever ran; (4) the design called mint-registry discard "pure memory
hygiene," which is wrong for an authority whose declared lifetime is one
stage — while its entry remains registered, a genuine, unmutated authority
object from a completed stage could still pass every re-proof and derive a
path after that stage ended; and (5) the read-only binding verifiers had no
stated input-type boundary of their own, leaving `actual_path`/`parsed_record`
to whatever Python's path protocol or a hostile `Mapping` decided. FU4 closes
all five: writer functions accept only an authority, a schedule ordinal, and a
payload — never a path (new §16.3.8); the schedule-arm derivation is one
internal function every consumer (L0, payload construction, the writer, the
record validator, the artifact-binding verifier) shares by identity, never by
caller convention (§16.3.8); a package-parent re-proof runs before any
`RESULTS_ROOT` filesystem write, every time, using a value captured once at
import and never re-derived (extended §16.3.2); the mint registry gains an
explicit ACTIVE/RETIRED lifecycle, with retirement on every stage exit path
including immediately on a §16.3.7 hard stop (new §16.3.9); and both binding
verifiers gain an exact-type input gate plus a one-walk canonicalization
discipline before composing the existing payload validator (rewritten
§22.5.2). It adds regressions T-38–T-54 and narrows T-21 further. The
itemized changelog is §26.

**This revision also incorporates 5F3B-HARNESS-CFG1-DESIGN-FU5** — closing
final emission-identity and durable-artifact-bytes binding. FU5 does not
reopen the compat experiment, the L0–L30 lifecycle, `stage_execution_id`'s
grammar, package-parent/`RESULTS_ROOT` provenance, the mint registry, the
ACTIVE/RETIRED authority lifecycle, or the post-hoc-verifier *concept* — it
closes two remaining gaps in how a writer consumes a payload and how a
post-hoc verifier consumes an artifact. Independent review found: (1) §16.3.8's
FU4 writer sequence cross-checked `payload["arm_id"]` **before** the payload
had been type-gated and canonicalized, reading a caller-supplied field ahead
of the very TOCTOU boundary the design otherwise applies everywhere; and,
separately, a payload's *internal* self-consistency was never enough, because
a canonical payload could agree with itself while still belonging to a
different stage execution than the authority writing it; and (2) the
post-hoc verifiers' `verify_cfg1_*_binding(actual_path, parsed_record)`
signature let a caller supply an already-parsed record that was never bound to
the *current* bytes at `actual_path` — a stale `dict` could be asked about a
path whose file had since changed, which answers a different, useless
question — and `resolve()` was called before any symlink/reparse check,
destroying exactly the evidence a lexical check needs to see. FU5 closes both:
every `emit_cfg1_*` writer now type-gates and canonicalizes its payload
**before** touching any field (rewritten §16.3.8), then independently binds
the canonical snapshot to its own authority and schedule identity — for the
run-record, refusal-record, and stage-closure writers each — rather than
trusting the payload's internal agreement with itself; and both post-hoc
verifiers drop `parsed_record` entirely, becoming `verify_cfg1_*_binding(actual_path: str) -> bool`,
reading and parsing the artifact's own bytes themselves, with lexical
symlink/reparse/regular-file checks running **before** `resolve()` is ever
called (rewritten §22.5.2). It adds regressions T-55–T-68, revises T-33's
invocation shape and T-51–T-54's stale references, and removes the last stale
normative references to a public path-returning helper from §16.3.4 and
§22.4. The itemized changelog is §27.

**This revision also incorporates 5F3B-HARNESS-CFG1-DESIGN-FU6** — closing
record-family schemas, non-recursive fallback semantics, and exact emitted
bytes. FU6 does not reopen the compat experiment, the L0–L30 lifecycle, the
`stage_execution_id` grammar, package-parent/`RESULTS_ROOT` provenance, the
mint registry, the ACTIVE/RETIRED authority lifecycle, the writer-no-path
boundary, the canonicalize-before-read discipline, or the one-argument
byte-authoritative post-hoc verifier's *concept* — it closes five remaining
gaps in how the three durable record kinds are validated, how a failed
emission may (or, mostly, may not) fall back, and exactly what bytes a writer
is permitted to produce. Independent review found: (1) §16.3.8/§22.1 required
every writer to run "the full §22.1–§22.3 payload validator," but §22.1–§22.3
is defined only for `pi-harness-cfg1-run.v1`, leaving
`pi-harness-cfg1-refusal.v1` and `pi-harness-cfg1-stage-closure.v1` with no
validator of their own and §21.2's field lists merely descriptive, not a
closed schema; (2) the read-only run-artifact verifier's composition of "the"
payload validator could not, as specified, accept a genuine refusal record at
a run path, even though §18 row 11 makes a refusal record exactly that path's
other legitimate occupant; (3) the generic "on scrub failure, the CFG1-owned
refusal record may be written" rule, read literally, implied a refusal-emission
failure could itself trigger another refusal attempt — an unbounded recursion
the design never intended and §16.3.9's retirement table only partially
closed; (4) §16.3.8.1 spoke of "serializing the canonical object for the check
and later writing canonical," which permits two separate serializations of the
same object with different bytes, breaking the claim that the verifier's bound
also bounds the writer; and (5) T-21/T-38 stated "no public CFG1 function
accepts a path," which FU4/FU5's own accepted `verify_cfg1_*_binding(actual_path)`
signature makes false as written. FU6 closes all five: three independent,
closed payload validators are frozen, one per record kind, invoked by name
rather than by a shared generic call (§22.1, new §22.4.1, new §22.4.2); the
run-artifact verifier gains an explicit discriminator-based dispatch between
the run and refusal payload validators, proven never to misclassify a valid
artifact of either kind (new §22.4.3, rewritten §22.5.2 Step 3);
refusal-record and stage-closure-record emission failures are frozen as
**non-recursive** — a refusal writer never calls itself and a stage-closure
writer never calls the refusal writer — with one new closed emission status,
`EMISSION_FAILED`, for the case a run-record failure's one permitted refusal
fallback itself fails without a path collision (new §16.3.8.2, revised
§16.3.9's stage-closure retirement row, revised §17, §18, §19.1, §21.2); the
emitted-bytes pipeline is pinned to exactly one serialization step, checked
and then written verbatim, with `MAX_CFG1_ARTIFACT_BYTES` frozen at the exact
integer `65536` (revised §16.3.8.1); and T-21/T-38 are narrowed to the public
**write/emission** API surface, which still accepts no caller-selected path,
explicitly carving out the read-only verifiers' intentional `actual_path`
parameter as neither a regression nor a contradiction. It also corrects stale
`§16.3.8 step N` references left over from FU5's renumbering (filename
derivation is step 9, not step 5; the writer's schedule-arm binding check is
step 7, not step 4), separates the binding regressions into a
payload-schema-failure class (refused by the payload validator itself, never
reaching authority binding) and a valid-other-identity class (passes its own
validator, fails only at the authority-binding boundary), and replaces T-65's
non-deterministic byte-tamper oracle with one exact, mandatory-`False`
mutation. It adds regressions T-69 onward. The itemized changelog is §28.

**This revision also incorporates 5F3B-HARNESS-CFG1-DESIGN-FU7** — closing
final emission-state, stage-schema, and regression-constructibility
contradictions. FU7 does not reopen the compat experiment, the Q/R/E/H arms,
the Stage-1 schedule, the model/fixture, F1/F2, the L0–L30 resource
lifecycle, workspace/broker/runtime authority, the `stage_execution_id`
grammar, package-parent/`RESULTS_ROOT`/execution-directory provenance, the
mint/retirement architecture, the writer-no-path boundary, the
canonicalize-before-read discipline, the three-record-family validator split,
the one-argument byte-authoritative verifier, non-recursive refusal/
stage-closure behavior, or the exact `65536`-byte bound — it closes five
remaining contradictions FU6 left standing. Independent review found: (1) FU6
treated a run-record writer's refusal-fallback eligibility as bounded by
"before an exclusive-create collision," which is not mechanically true —
an exclusive-create can succeed and only *then* have its write, flush, or
close fail, leaving partial or full bytes at the final path with no safe way
to attempt a refusal fallback there without risking an overwrite or a second
writer racing a collision; (2) §22.4.2 let a "successfully completed" stage
(`halted_after_ordinal == null`) contain an `EMISSION_COLLISION` or
`EMISSION_FAILED` ordinal status, even though §19.1's admission rule already
forbids issuing an admission token after either — the schema permitted a
shape the admission rule can never actually produce; (3) `halt_reason_code`
was described as "closed enum, non-exhaustive minimum, extended with each new
halt-capable failure," which is not a closed vocabulary at all; (4) T-40 and
T-58–T-60's "valid-other-identity" constructions included an `arm_id`-only
and a `record_filename`-only mismatch, both of which are already
self-inconsistent under §22.3's own existing cross-field invariants (arm and
filename are pure functions of `stage_id`/`run_ordinal`) and so are refused
at the payload validator's step 6, never reaching step 7 — making those two
constructions unable to prove what they were cited for; and (5) the schema
already accepted `stage_id = "S1" | "S2"` and an S2 ordinal range with a
`_schedule_arm_for("S2", ...)` contract, but §13.2 left Stage 2's order as
"for example," giving `CFG1-IMPL` no way to implement that function for S2
without guessing. FU7 closes all five: an explicit emission-phase vocabulary
(`PRE_CREATE` → `FINAL_PATH_CREATE_ATTEMPTED` → `FINAL_PATH_CREATED` →
`BYTES_FULLY_WRITTEN` → `EMISSION_CONFIRMED`) is frozen and refusal-fallback
eligibility is narrowed to strictly `PRE_CREATE` failures only, with an
explicit post-create residue policy (leave untouched, never authoritative,
§16.3.8.2/§16.3.8.3); the stage-closure schema's successful-stage invariant
is corrected to a one-directional implication that is actually consistent
with §19.1 (§22.4.2); one exact, six-member `HALT_REASON_CODES` vocabulary is
frozen, derived directly from §19.1's own four admission conditions, shared
by the run record's and the stage-closure record's `halt_reason_code` fields,
and explicitly excluding the two cases that write no stage-closure record at
all (new §19.4); T-40/T-58–T-60 are rewritten to move the
already-self-inconsistent constructions to step-6 (payload-validator)
regressions and keep only genuinely constructible valid-other-identity cases
at step 7; and Stage 2's schedule is frozen exactly as `Q, H, H, Q, Q, H`
(§7.3a), with `_schedule_arm_for` and every S2-consuming schema/regression now
fully defined rather than left as an example. It adds regressions T-83
onward. **Existing T-1…T-82 numbering is preserved throughout — no test id
is renumbered, reused, or deleted — but this does not mean every row's
content is unchanged: T-40 and T-58–T-60 are substantively rewritten in
place (Finding 4 above), and T-75 is narrowed (Finding 1's precursor to
§16.3.8.2's phase model); every other row is unchanged.** (Wording corrected,
FU8: an earlier draft of this paragraph claimed FU7 "preserves T-1…T-82
exactly," which was never true of its own rewritten rows.) The itemized
changelog is §29.

**This revision also incorporates 5F3B-HARNESS-CFG1-DESIGN-FU8** — closing
final admission-time, emission-attribution, and residue-semantics
contradictions. FU8 does not reopen the compat experiment, the S1/S2
schedules, the model/fixture/prompt, F1/F2, the L1–L28 runtime/resource
lifecycle, `stage_execution_id` grammar, package-parent/`RESULTS_ROOT`
provenance, execution-directory authority, the mint/ACTIVE/RETIRED model,
the writer-no-path API, canonicalize-before-read, the three record-family
validators (except the one narrow run-record field correction below), the
single-serialization/`65536`-byte rule, the one-argument byte-authoritative
verifiers, the `PRE_CREATE`→`FINAL_PATH_CREATE_ATTEMPTED`→`FINAL_PATH_CREATED`→
`BYTES_FULLY_WRITTEN`→`EMISSION_CONFIRMED` phase model, the post-create
residue policy, or non-recursive fallback — it closes five remaining
contradictions in halt/admission evidence semantics FU7 left standing.
Independent review found: (1) FU7's `RUN_RECORD_REFUSAL_FALLBACK_FAILED`
halt code was mapped to **every** `EMISSION_FAILED` outcome, including a
direct post-create primary-writer failure for which, by FU7's own corrected
eligibility rule, no refusal fallback is ever attempted — a false attribution
asserting an attempt that never happened; (2) the run-record schema required
`halt_triggered_by_this_run` to equal "the §19.1 negation," but §19.1
depends on this very run's own emission outcome and registry state, neither
of which exists until **after** the run record's own emission has already
resolved — a payload-only validator cannot recompute a fact about its own
not-yet-decided future; (3) FU7's post-create residue policy — write may
finish, then flush or close may fail, leaving structurally valid residue —
applies to the stage-closure writer too, but T-76/T-87 still claimed no
stage-closure record could exist or be readable after any such failure,
which is not mechanically true for a post-create close failure; (4) L29 was
still described only in terms of FU6-era scrub-refusal/collision language,
stale relative to §16.3.8/§16.3.8.2's now-frozen writer contract; and (5) L0
requires the schedule-derived run path to be absent before admission, but
nothing closed the case where that path is already occupied by tampering
between stage-output mint and L0 — a case neither an ordinary halt (no run
was ever admitted) nor a writer-boundary collision (no writer ever ran) can
truthfully encode. FU8 closes all five: the halt code is renamed to the
truthful, neutral `RUN_RECORD_EMISSION_FAILED`, covering all three
`EMISSION_FAILED`-producing causes without distinguishing among them in this
closed field (§19.4); `halt_triggered_by_this_run` and `halt_reason_code` are
removed from the durable run-record schema entirely, remaining in-memory-only
L30 facts, with the stage-closure record as the sole durable authority for
whether/where/why the stage halted (§22.2, §22.3, §19.4); the stage-closure
residue invariant is corrected to separate a `PRE_CREATE` "truly nothing on
disk" claim from a post-create "live result is `FAILED` regardless of a
structurally-valid residue's later readability" claim, with a new mandatory
close-after-full-write regression (T-87, rewritten); L29 is rewritten as a
citation-only pointer to the frozen §16.3.8/§16.3.8.2 writer contract, adding
one previously-uncovered §18 row (row 18: a direct primary post-create
failure with zero fallback attempts); and a new hard-stop class,
`OUTPUT_NAMESPACE_PREOCCUPIED`, is frozen for L0's own path-already-occupied
case, distinct from both an ordinary halt and a writer's `EMISSION_COLLISION`
(new §16.3.10). It also corrects the stale claim that FU7 "preserves
T-1…T-82 exactly" and removes every remaining "refusal fallback failed" claim
that is not scoped to the one case it actually describes. It adds
regressions T-94 onward, preserving T-1…T-93 numbering (T-40, T-58–T-60, and
T-75 were already substantively rewritten by FU7 itself; FU8 further revises
T-74, T-76, T-78, T-79, T-87, T-89, T-90 in place). The itemized changelog is
§30.

**This revision also incorporates 5F3B-HARNESS-CFG1-DESIGN-FU9** — closing
final stage-decision provenance, halt-reason precedence, and create-attempt
failure classification. FU9 does not reopen the compat experiment, the S1/S2
schedules, the model/fixture/prompt, F1/F2, the L1–L28 runtime/resource
lifecycle, the L29-before-L30 ordering, stage-output filesystem authority,
ACTIVE/RETIRED semantics, the three artifact-family schemas (except the one
narrow provenance closure below), the run-record halt-field removal, the
stage-closure record's status as sole durable halt authority, the
writer-no-path boundary, canonicalize-before-read, the emission-phase model,
the post-create residue policy, non-recursive fallback, the exact
`65536`-byte bound, or `OUTPUT_NAMESPACE_PREOCCUPIED` — it closes five
remaining gaps FU8 left standing. Independent review found: (1) FU8 made the
stage-closure record the sole durable halt authority but never closed the
stage-closure **writer's own boundary** to match — it still conceptually
accepted a caller-supplied `payload` for `ordinal_status`/
`halted_after_ordinal`/`halt_reason_code`, bound only by internal
self-consistency, which is not provenance that the payload equals the actual
L30 decision; (2) with `halt_triggered_by_this_run`, `lifecycle_all_closed`,
`run_classification`, and emission status all capable of failing
simultaneously, no frozen order existed for which single `halt_reason_code`
a stage-closure record should carry, risking non-reproducible evidence for
mechanically identical situations; (3) the accepted emission-phase model
distinguished `FINAL_PATH_CREATE_ATTEMPTED`'s possible outcomes for the
primary run-record writer, but the partial-failure table left the refusal
writer's own collision folded ambiguously into its generic failure bucket,
and the stage-closure writer's own create-attempt outcomes as one
undifferentiated bucket; (4) §22.4.2 still stated the halt-reason vocabulary
was "shared identically" with the run record's own field — false since FU8
removed that field — and still counted only two no-durable-closure cases
when FU8's own §16.3.10 had already made three; and (5) the stage-closure
payload validator's role was never explicitly distinguished from the
writer's stronger, decision-backed provenance guarantee, risking a future
reader treating schema validity alone as proof a record reflects the real
L30 outcome. FU9 closes all five: a CFG1-owned, non-forgeable, mint-registry-backed
`CFG1StageClosureDecision`, sealed only at L30 after the current ordinal's
L29 result is known, is now the **only** source of stage-decision facts the
stage-closure writer accepts — `emit_cfg1_stage_closure(authority, *,
payload)` becomes `emit_cfg1_stage_closure(authority, *, decision)` (new
§16.3.8.3); one exact, deterministic six-step precedence,
`_resolve_halt_reason_code`, is frozen and shared by identity between L30's
decision-sealing call and every place the design reasons about halt-reason
selection, with the two emission-outcome checks taking precedence over the
four run/lifecycle-level checks (new §19.5); the
refusal writer's own collision is classified identically to the primary
writer's (`EMISSION_COLLISION`), and the stage-closure writer's own
create-attempt outcomes — collision, non-collision/ambiguous failure, and
post-create write/flush/close failure — are frozen as uniformly "live
`FAILED`, no fallback, authority retired," with two new §18 rows (18
broadened, 19 added) closing the gap (§16.3.8.2, §18); §22.4.2's stale
sharing claim and two-case count are corrected in place to match FU8's own
already-current state (three cases, run-record field absent); and
§16.3.8.3/§22.4.2 both now state explicitly that schema validation proves
coherence, never provenance, with the stronger guarantee stated as the
conjunction of valid schema, a genuine sealed decision, a matching ACTIVE
authority, and writer-internal derivation. It adds regressions T-102 onward,
preserving T-1…T-101 numbering exactly (no existing row rewritten this time
— every FU9 correction is additive: a new writer boundary, a new function, a
new §18 row, and in-place wording fixes to prose that made no test-relevant
claim). The itemized changelog is §31.

**This revision also incorporates 5F3B-HARNESS-CFG1-DESIGN-FU10** — closing
terminal stage-decision issuance provenance and freezing successful-completion
closure. FU10 does not reopen the compat experiment, the S1/S2 schedules, the
model/fixture/prompt, F1/F2, the L1–L29 runtime/resource lifecycle,
stage-output filesystem authority, ACTIVE/RETIRED semantics, the run/refusal/
stage-closure record schemas (§22.4.2's successful-stage shape is reused
exactly, not amended), the writer-no-path boundary, canonicalize-before-read,
the emission-phase model, the post-create residue policy, `HALT_REASON_CODES`,
FU9's halt-reason precedence, or FU9's create-attempt matrix — it closes two
remaining gaps FU9 left standing. Independent review found: (1) FU9 correctly
removed caller-selected closure facts from `emit_cfg1_stage_closure`'s own
boundary, but the fix moved them exactly one layer upstream, to
`seal_cfg1_stage_decision(authority, *, ordinal_status=…,
halted_after_ordinal=…, halt_reason_code=…)` — a function any supported
caller holding a genuine ACTIVE `CFG1StageOutputAuthority` could call
directly, with an alternate, internally self-consistent ledger/reason tuple
of its own choosing, and receive back a genuine, registry-backed,
mint-nonce-bearing `CFG1StageClosureDecision` that would pass every check
`emit_cfg1_stage_closure` performs — the mint registry proves *who* issued
the object, never that the *facts inside it* came from the real L30 stage
state; and (2) L30's own admission/closure logic (§16.2, §19.1, §19.2) was
specified only as a two-way branch — issue a token, or seal a HALTED decision
— which has no transition at all for the stage's own final declared ordinal
succeeding: `S1` ordinal 9 or `S2` ordinal 6 passing §19.1's admission
conditions has no ordinal *k*+1 to admit, and the design as FU9 left it would
either issue a token for a non-existent ordinal or leave a successful stage
with no terminal record at all, contradicting §22.4.2's own already-accepted
successful-stage schema shape. FU10 closes both: the stage-decision
**issuance** capability is removed from the public, authority-parameterized
API surface entirely — there is no longer a module-level, importable, or
otherwise externally-reachable name through which any caller, however
privileged, can request a sealed decision carrying facts of its own choosing;
sealing exists only as code lexically owned by the one stage-runner routine
that executes L0–L30, reading its `ordinal_status`, `halted_after_ordinal`,
and `halt_reason_code` inputs exclusively from that same routine's own local
state — a new runner-local, non-registry, non-exported stage-progress ledger
(new §16.3.8.4) populated ordinal-by-ordinal as each L29 result actually
resolves, never from an argument list any other code could populate (revised
§16.3.8.3); and L30's transition is frozen as an exact three-way rule — admit
*k*+1 (branch B); or, on the stage's own final declared ordinal succeeding,
seal a **SUCCESS** terminal decision and emit the successful stage-closure
record, issuing no token at all (branch C, new); or seal a **HALTED** one as
before (branch A, unchanged) — with `LAST_ORDINAL(stage_id)` derived from the
same frozen per-stage schedule source `_schedule_arm_for` already consults,
never an independently duplicated literal (new §19.6). `CFG1StageClosureDecision`
is confirmed to represent both terminal outcomes, never a halt-only type, and
a decision's `_STAGE_DECISION_SEALED` registry entry is revoked at the start
of its one permitted consumption — success or failure of the ensuing write —
so no decision can ever be consumed by a second stage-closure attempt. It
revises T-106, T-107, and T-110 in place (each assumed a callable,
authority-parameterized sealer, which no longer exists), makes a
wording-only update to T-102/T-103 (the mechanism each proves is unchanged;
only the sentence describing how a genuine decision comes to exist changes),
and adds regressions T-124 onward, preserving T-1…T-123 numbering exactly
otherwise. The itemized changelog is §32.

**This revision also incorporates 5F3B-HARNESS-CFG1-DESIGN-FU11** — correcting
final L30 cardinality, sharpening the registry-versus-issuer threat-model
boundary, and closing an implementation-scope gap. FU11 does not reopen
FU10's architecture: the runner-local stage-progress ledger, the
lexically-owned terminal decision issuer, the removal of caller-selected
decision facts, `CFG1StageClosureDecision`'s authenticity registry,
`emit_cfg1_stage_closure(authority, decision)`'s own signature, the decision
mutation/rebinding protections, revocation-before-payload-construction,
L29-before-L30 ordering, §19.5's halt-reason precedence, §19.6's three-way
transition and its branch meanings (A = HALTED, B = continue, C = SUCCESS),
`LAST_ORDINAL`'s schedule-derived provenance, and §22.4.2's successful-stage
schema are all unchanged and unreopened — it closes three narrow gaps FU10
left standing. Independent review found: (1) FU10's own normative text and
T-107 asserted "L30 runs exactly once per stage execution," which is false —
L30 executes once **per admitted ordinal**, up to nine times for `S1` and six
for `S2`, exactly as many times as §19.6 branch B is reached; the actual
exactly-once guarantee FU10 needed is on the **terminal decision**, not on
L30's own invocation count, and rested on a claim that was never true; (2)
T-125 required proving direct mutation of the internal `_STAGE_DECISION_SEALED`
registry fails because it has "no externally-reachable reference," conflating
the accepted requirement that the issuer and the stage-progress ledger have
no *supported-callable* path with an unrequired, unscoped claim that an
internal authenticity/revocation registry resists arbitrary same-process
memory tampering; and (3) §14.1 still authorized only `T-1…T-123`, silently
permitting a `CFG1-IMPL` authorization that omits every regression FU10
added. FU11 closes all three: §16.3.8.3 requirement 6 is corrected to state
the true invariant — L30 runs once per admitted ordinal, the local sealing
step fires only on branch A or C, and the actual **terminal** exactly-once
guarantee is the conjunction of the §19.6 state machine reaching a terminal
branch at most once per stage plus the decision registry's own one-seal-per-
authority rule, which remains the mechanical backstop against any malformed
or test-only second reach of the sealing step (revised §16.3.8.3, §17's
sealed-stage-decision row, T-107); T-125 is narrowed to prove only the
supported-API issuance boundary and the runner-local ledger's own
unsuppliable/unreturnable provenance, explicitly disclaiming any requirement
to prove `_STAGE_DECISION_SEALED` resists direct mutation, monkeypatching, or
other same-process memory tampering — outside this design's threat model
unless a future FU separately widens it (revised T-125); and §14.1 is
corrected to require `T-1…T-132`, with `T-124…T-132` named as
non-omissible from any `CFG1-IMPL` authorization (revised §14.1). It also
makes a wording-only correction to T-102/T-103's own historical-change note.
No frozen qualification, OBS1, AR2, runtime, compat, schedule, record-schema,
or filesystem-authority contract is reopened. The itemized changelog is §33.

**This revision also incorporates 5F3B-HARNESS-CFG1-DESIGN-FU12** — separating
terminal seal history from decision consumability. FU12 does not reopen
FU11's corrections or FU10's architecture: L30 executing once per admitted
ordinal, §19.6's branch A/B/C semantics, terminal sealing only on branch A or
C, the runner-local stage-progress ledger, the lexically-owned decision
issuer's unreachability to any supported caller, `CFG1StageClosureDecision`
itself, its field/nonce/authenticity checks, its authority-rebinding
protection, `emit_cfg1_stage_closure(authority, decision)`'s own signature,
decision one-consumption semantics, step 4a's position before payload
construction, and FU11's supported-caller threat-model scope are all
unchanged and unreopened — it closes one narrow gap FU11 left standing.
Independent review found: FU11 corrected requirement 6's cardinality claim
but left its *mechanism* resting entirely on `_STAGE_DECISION_SEALED` — the
same registry step 4a revokes the consumed decision's own entry from, at the
start of that decision's one permitted consumption. Because step 4a removes
the just-consumed decision's own entry before that entry can ever again
answer "has this authority already sealed a decision," the following
sequence was possible entirely within requirement 6's own stated threat
scope (malformed/test-only internal control flow, never a supported caller
or private-memory-tampering attack): seal `D1` for authority `A`; begin
consuming `D1`; step 4a removes `D1` from `_STAGE_DECISION_SEALED`; malformed
internal flow reaches the sealing step again for `A`; the registry no longer
contains evidence `A` already sealed; a second, genuinely different, genuine
decision could be registered — defeating the very "at most one terminal
decision per authority" guarantee requirement 6 exists to state. FU12 closes
this by separating two properties FU11 had left conflated in one registry:
`_STAGE_DECISION_SEALED[decision_nonce]` now proves **decision authenticity
and consumability only** (unchanged in shape from FU9/FU10), while a new,
independent, process-local, per-authority **seal-history fact**,
`_STAGE_TERMINAL_SEAL_HISTORY` (keyed by `authority.mint_nonce`), proves
**seal-once** — established exactly once, on the first terminal seal, before
the decision itself is ever registered or constructed, and never removed by
decision consumption, by that consumption's write succeeding or failing, or
by authority retirement (revised §16.3.8.3 requirement 6, revised step 4a,
revised "Decision lifetime," new "Terminal-seal history lifetime" and
"Partial-failure atomicity of the mint sequence" paragraphs, revised §17
sealed-stage-decision row, new §17 terminal-seal-history row). It revises
T-107 in place, adding the exact adversarial ordering (T-107B: a second seal
attempt forced **after** a first decision's own consumability revocation)
that FU11's mechanism could not have survived, and adds regressions
T-133–T-136, extending the implementation scope to T-1…T-136 (revised
§14.1). No frozen qualification, OBS1, AR2, runtime, compat, schedule,
record-schema, or filesystem-authority contract is reopened. The itemized
changelog is §34.

**This revision also incorporates 5F3B-HARNESS-CFG1-DESIGN-FU13** — closing
the terminal-decision mint failure exit path FU12 created but left with no
lifecycle disposition. FU13 does not reopen FU12's seal-once/consume-once
architecture: `_STAGE_DECISION_SEALED` as the per-decision authenticity/
consumability registry, `_STAGE_TERMINAL_SEAL_HISTORY` as the independent
per-authority seal-once history, requirement 6's history-check →
history-establishment → decision-registration → decision-construction
sequence, step 4a's scope (revoking only `_STAGE_DECISION_SEALED`), T-107A/
T-107B, T-132's consume-once proof, T-133/T-134's seal-history-survival
proofs, the terminal-seal-history lifetime, FU11's supported-caller
threat model, §19.6's branch A/B/C semantics, and the absence of any
supported-caller path to the lexical issuer or the stage-progress ledger are
all unchanged and unreopened — it closes one narrow gap FU12 left standing.
Independent review found: FU12's own "Partial-failure atomicity of the mint
sequence" paragraph correctly identifies three points at which the terminal-
decision mint sequence can fail after L30 has selected branch A or C
(§19.6) and begun sealing, but the design never assigns any of the three a
lifecycle disposition. No genuine `CFG1StageClosureDecision` exists in any
of the three cases, so `emit_cfg1_stage_closure(authority, decision=...)`
cannot be called — the failure is a real stage-exit path with no entry in
§16.3.9's retirement-ordering table, no row in §18's partial-failure table,
no disposition in §21.2's console sink, and no member of the four failure
classes §19.4/§22.4.2/T-123 previously enumerated as ending a stage without
a confirmed stage-closure record (those sections enumerated exactly three;
this is a fourth). FU12's own prose was additionally self-contradictory:
its pre-history-establishment failure case stated "a later attempt remains
a legitimate first seal," while the same subsection states elsewhere that
no recovery or retry path is invented for any mint failure, and T-135(c)
expected a subsequent legitimate seal attempt to succeed. FU13 closes both
gaps. It freezes one closed, console-only, bounded terminal code —
`STAGE_DECISION_MINT_FAILED` — that any mint-sequence failure occurring at
any point after L30 selects branch A or C receives, regardless of which of
the three failure points it occurs at; on this disposition, no second mint
attempt is permitted, no admission token is issued, no stage-closure writer
is called, all already-confirmed run/refusal artifacts remain untouched,
the stage-output authority is retired immediately (before console
reporting), and resumption requires a new authorization and a new
`stage_execution_id` — exactly as for any other hard stop. It also rewrites
the pre-history-establishment case to state the stricter rule this design
now freezes: technical retryability is irrelevant, because operational
retry is forbidden regardless of which registry is or is not populated
(revised §16.3.8.3 requirement 6's partial-failure-atomicity paragraph, new
"Terminal-decision mint failure disposition" paragraph, revised §16.3.9
retirement-ordering table, revised §18, revised §19.2, revised §19.4,
revised §22.4.2, revised T-123, rewritten T-135, extended T-136, new
T-137–T-141, extending the implementation scope to T-1…T-141 (revised
§14.1)). No frozen qualification, OBS1, AR2, runtime, compat, schedule, or
filesystem-authority contract is reopened, and `STAGE_DECISION_MINT_FAILED`
is never added to `HALT_REASON_CODES` — there is no durable stage-closure
record in which such a code could truthfully live. The itemized changelog
is §35.

**This revision also incorporates 5F3B-HARNESS-CFG1-DESIGN-FU14** — a
regression-lifetime wording correction, with no new test IDs and no
mechanism change. FU14 does not reopen FU13's architecture:
`STAGE_DECISION_MINT_FAILED` remains the uniform terminal disposition for
every terminal-decision mint failure, with zero operational retry, zero
next-ordinal admission, zero stage-closure writer call, immediate
stage-output-authority retirement before console reporting, untouched
prior run/refusal artifacts, bounded console-only reporting, raw-exception
containment, `_STAGE_TERMINAL_SEAL_HISTORY` surviving only through the
sealing-capable stage-runner invocation, final cleanup of both registries
only after that invocation leaves every sealing-capable code path, and
exactly four no-confirmed-stage-closure cases — all unchanged and
unreopened. Independent review found FU13's own regression prose, not its
mechanism, internally inconsistent in three places: (1) T-135's
introductory sentence claimed none of its three sub-cases is followed by
any further sealing attempt, while its own (a)/(b) bodies required a
synthetic subsequent sealing reach — conflating a forbidden **operational**
retry with a permitted **adversarial test-only injection** used to prove
the seal-history backstop; (2) T-138 claimed
`_STAGE_TERMINAL_SEAL_HISTORY` remains "for the remainder of the test
process's reachable lifetime," a lifetime wider than, and contradicting,
the exact before/after-runner-return lifetime T-136 already freezes; (3)
T-139 stated three assertions in a single list without ordering them
against the stage-runner invocation's own return, so its final assertion
("seal history still refuses a synthetic second seal") could be
misread as applying **after** the invocation returns — the same point at
which T-136 already requires the seal-history entry to be absent. FU14
corrects all three as pure wording/ordering fixes: T-135's introductory
sentence now states the stage-runner-performs-zero-retries claim and the
harness-may-force-one-test-only-reach permission as two separate, explicit
facts, and sub-case (c) — where no history entry is ever created — no
longer attempts to prove a second-seal refusal from a history fact that
never existed; T-138 is narrowed to state exactly the four ordered facts
T-136 already freezes, with the overbroad "remainder of the test process"
phrase removed; T-139 is restructured into two explicitly ordered groups —
everything true while the stage-runner invocation is still active,
strictly before everything true only after it returns, with the
seal-history entry proven absent in the second group, never asserted to
still refuse anything there. FU14 also narrows one piece of §16.3.8.3
prose, unchanged in meaning: the post-registration-failure orphan
`_STAGE_DECISION_SEALED` entry was described as becoming "permanently
orphaned data," which could be misread as contradicting FU13's own bounded
mint-failure cleanup; it is now described as "orphaned and unusable until
the bounded mint-failure cleanup removes it." No new regression IDs are
added; T-1…T-141 remains the exact implementation scope; T-136 remains the
sole authoritative cleanup-timing regression, unmodified. The itemized
changelog is §36.

---

## 0. Status block

```text
5F3B-HARNESS-CFG1-DESIGN (+FU1+FU2+FU3+FU4+FU5+FU6+FU7+FU8+FU9+FU10+FU11+FU12+FU13+FU14)  THIS DOCUMENT — NOT IMPLEMENTED, NOT AUTHORIZED TO RUN

5F3B-HARNESS-OBS1-CONTRACT-A1            ACCEPTED / FROZEN
5F3B-HARNESS-OBS1-DESIGN                 ACCEPTED / FROZEN
5F3B-HARNESS-OBS1-IMPL + FU1/FU2/FU3     ACCEPTED / FROZEN
5F3B-HARNESS-ATTR1                       ACCEPTED / FROZEN  (cited as the stated premise; see §0.2)

Q1 / A / qwen3-coder-next                NOT_QUALIFIED / FROZEN
Q2 / B / minimax-m2.7                    NOT_QUALIFIED / FROZEN
Q3 / C / qwen3.6-27b                     NOT_QUALIFIED / FROZEN
M4                                       HOLD
DX1                                      NOT AUTHORIZED

QUALIFICATION_POLICY_REVISION            r1       UNCHANGED
records.RECORD_VERSION                   .v2      UNCHANGED
ACTIVITY_RECORD_VERSION                  .v1      UNCHANGED
```

### 0.1 The two findings, and the frozen reviewer decision on F2

**FINDING F1 — a second, unvaried harness divergence exists and is at least a
candidate explanation of equal standing.** Historical AR2 and O1 transmitted
`ar2.manifest.compose_prompt(case.prompt, manifest)` — the task text **plus an
AIDO-computed repository file list plus the sentence "Use aido_read to read a
file and aido_edit to change one…"** (`ar2/manifest.py:96-110`,
`run_ar2.py:576`, `run_o1.py:561`). The live qualification layer transmits
**exactly `self._task.prompt` and nothing else** (`semantic_live_adapters.py:96-104`,
`:686-693`). The IQ prompts deliberately name no file (`corpus.py:15`, `:311`),
and the only tools the model has describe their `path` argument as "exactly as
it appears in the task's file list" / "exactly as listed in the task"
(`extension/tools.ts:47-62`, `:103-107`) — a list the qualification prompt never
contains. There is no list/search tool (`tools.ts:18-19`). CFG1 does not vary
this (§6, §10, §13.4). No ATTR1 artifact exists in this repository, so this
document cannot establish whether ATTR1 weighed it.

**FINDING F2 — RESOLVED (reviewer decision, frozen for CFG1).** The literal
`pi-implementer-qualification-activity.v1` companion is qualification-corpus-bound:
`AttemptIdentity.__post_init__` refuses non-corpus tasks
(`runtime_activity.py:265-295`), and the emitter binds only to the three
qualification record kinds (`runtime_activity.py:107-110`, `:1247-1254`). **The
reviewer accepted the separate CFG1 evidence lineage.** CFG1 does **not** emit
the companion artifact. It **imports and calls, unmodified,**
`project_runtime_tool_activity` and `RuntimeToolActivitySnapshot`, and it
preserves their per-dispatch correlation, capture-basis semantics, bounded tool
vocabulary, exact int/bool rules, cross-field invariants, and exclusion of raw
arguments/results/reasoning (§11.1). `AttemptIdentity`, the corpus,
`VALID_TASK_IDS`, OBS1 record kinds and OBS1 schema/version are **not amended**.
The CFG1 record (§22) is an independent diagnostic lineage with no qualification
authority.

### 0.2 Premise provenance

The ATTR1 facts restated in the phase prompt (historical: explicit
`supportsDeveloperRole=false`, `supportsReasoningEffort=false`, system role, no
`reasoning_effort`; qualification: no compat block, developer role,
`reasoning_effort=medium`) are **independently re-derived** in §2–§4 from source.
They agree with the premise. No ATTR1 document is present in `docs/`.

---

## 1. Exact sources inspected

### 1.1 Repository (read-only)

| Source | Established |
|---|---|
| `experiments/pi_implementer_qualification/qualification/i2_pi_config.py:390-414` | `_settings_document()`: emptied ambient sources, `defaultProjectTrust: "never"`, `retry {enabled: true, maxRetries: 3, baseDelayMs: 2000, provider.maxRetries: 0}`; **no `defaultThinkingLevel`** |
| `i2_pi_config.py:472-548` | `write_qualification_pi_config`: provider `b300_pi_qualification`, `baseUrl` (runtime), `api: "openai-completions"`, `apiKey: "$PI_QUALIFICATION_B300_ROUTE_KEY"`, `models: [{id, reasoning: true}]`; **no `compat`**; no `maxTokens`; config dir `experiment_root/i2_pi_config` |
| `qualification/i2_identity.py` | `PROVIDER_ID = "b300_pi_qualification"`, `CREDENTIAL_ENV_VAR_NAME = "PI_QUALIFICATION_B300_ROUTE_KEY"` |
| `qualification/i2_route.py:58-63`, `:152-172` | route is `b300_litellm_proxy`; descriptor differs per candidate only in `candidate`/`model_id` |
| `qualification/i2b_live_adapters.py:1739-1784` | generator symmetry preflight: A/B documents agree except model `id` |
| `qualification/records.py:74-84` | `CANDIDATE_MODEL_IDS` A/B/C; `VALID_TASK_IDS` |
| `qualification/semantic_controller.py:349-395`, `:2533-2546` | frozen gate order (workspace → baseline → credential → config → env → broker → runtime → handshakes → route check → prompt → post-prompt → runtime teardown → broker shutdown → config cleanup → workspace removal → evidence); **the controller itself calls `write_qualification_pi_config`** |
| `qualification/semantic_live_adapters.py:96-104`, `:234-253`, `:686-693`, `:862` | bare prompt; positive allowlist of turn-wait outcomes; `RunBounds()` defaults; `await_settled` |
| `qualification/semantic_session.py:221-280`, `:472-493` | dispatch-state vocabulary (`CONFIRMED_SENT`, `CONFIRMED_NOT_SENT`, `SEND_STATE_INDETERMINATE`, …); `SemanticTurnOutcome` = `SETTLED` / `DEADLINE_REACHED` / `OBSERVATION_FAILED` |
| `qualification/i2b_workspace.py:155-363` | mint registry pattern: process-local nonce → `DisposableRootAuthority`; single-use claim by run id; re-proof via frozen `ar2.capability._verify_root_authority` before consumption |
| `qualification/i2_environment.py:249-338` | child env policy: `PI_CODING_AGENT_DIR`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`; requires an I2-issued config |
| `qualification/i2_secret_context.py:60-94` | base URL structural validator (does **not** test Pi's compat-detection substrings) |
| `qualification/i2_b300_route_observation.py:378-390` | `observe_b300_route_serves_model(base_url, api_key, model_id)`: one authenticated non-inference `GET /models` |
| `qualification/runtime_activity.py:107-110`, `:249-295`, `:338-420`, `:561-648`, `:1189-1301` | companion kinds; corpus-bound identity; snapshot + invariants; pure projection; emitter |
| `qualification/safety.py:162-259` | `emit_evidence_or_refuse` stamps refusals with the **qualification** package id and policy revision; `qualification_scrub_check` is the pure check |
| `qualification/corpus.py:15`, `:276-313` | IQ prompts name no file |
| `experiments/pi_external_runtime_ar2/ar2/pi_config.py:84-237` | historical generator with explicit `compat {false, false}`; `write_disposable_extension`; verified `scrub_generated_extension_config` / `scrub_generated_pi_config` |
| `ar2/launch.py:19`, `:69-162`; `ar2/__init__.py:43` | Pi pinned `0.84.2`; Node-direct `--version` probe; argv has **no `--thinking`** |
| `ar2/manifest.py:96-110`; `ar2/fixtures.py:50-65`, `:479-670` | `compose_prompt`; `CaseFixture.manifest_in_prompt`; fresh-root minting with exclusive-create nonce marker; `remove_disposable_tree(path)` verifies removal but **takes a bare path** |
| `ar2/capability.py:245-556`, `:587-599` | `DisposableRootAuthority`; `_verify_root_authority` (marker re-read, scratch boundary, canonical paths); `mint_capability`; `RunState` |
| `ar2/broker.py:1-65`, `:102-123`, `:366-506`, `:689-841` | broker is an **in-process daemon thread + one first-instance named pipe**; states `CREATED→READY→SERVING→DRAINING→CLOSED` / `TEARDOWN_INCOMPLETE`; `start()` at most once; partial-start ownership partition A/B/C; `shutdown(trigger)` records `state_reached`, `worker_termination_observed`, `pending_operations_unreaped`; `worker_error` is raw text |
| `ar2/supervisor.py:51-60`, `:78-127`, `:166-472` | `RunBounds`; `RuntimeActivity` (`extension_errors` retains raw text ≤500 chars); `PiRpcSupervisor.launch` (Popen, reader threads); `await_response` correlates by RPC id; `shutdown()` ladder: stdin close → wait → terminate → kill → `gave_up_waiting`; `sanitized_events` |
| `ar2/verification.py:40-142` | fixed runner; `VerificationOutcome` carries `return_code`, `direct_child_killed`, raw `output_text`, regex-parsed `failed_node_ids` |
| `ar2/handshakes.py:32`, `:138` | `evaluate_extension_identity`, `evaluate_model_identity` |
| `ar2/extension/tools.ts`, `ipc.ts:77`, `:225-248`, `index.ts:38-42` | one `brokerCall` per tool execution; broker refusal or unavailability **throws** (→ Pi error result); no `before_provider_request` handler |
| `src/ai_dev_orchestrator/workspace/canonical.py:410-441` | `_lstat` (uses `os.lstat`, never follows a final symlink); `_is_symlink_or_reparse_point` (POSIX `S_ISLNK` **and** Windows `st_file_attributes` reparse bit **and** `st_reparse_tag` — both Windows-only attributes, absent elsewhere); already imported cross-module by `ar2/capability.py:39` |
| `qualification/i2b_workspace.py:155-264` | `_MINTED: dict[str, _MintRecord]` process-local nonce→record registry; `QualificationRunWorkspace.__post_init__` refuses any instance whose nonce is unregistered or whose paths mismatch the registered record — the exact "valid-by-construction, unforgeable public value object" shape FU3 mirrors for `CFG1StageOutputAuthority` |
| `qualification/i2_pi_config.py:348-387` | `GeneratedQualificationConfig.authority_token: str = field(repr=False)` — never written to disk, never shown in any repr/diagnostic/evidence; the precedent for `CFG1StageOutputAuthority.mint_nonce` |
| `pi_external_runtime_ar2_o1/results/ar2o1_case_O1_20260824T225809Z.json` | O1: Pi **0.84.3**, direct vLLM; 8 tool-call ids (6 read, 2 edit); Git observed after runtime exit and broker `CLOSED` |
| `pi_implementer_qualification/results/{A,B,C}_IQ-{1,2,3}.json` (read-only) | all nine: Pi **0.85.1**, `VALID`, 1 prompt, zero observed changed paths; pattern identical across A/B/C |
| `pi_implementer_qualification/results/i2b_live_*.json` | standalone Category-B passes exist for **A** and **B**; none for C |
| `docs/PHASE_5F3B_Q3_DESIGN_SECOND_ROUND_CANDIDATE_C_AUTHORIZATION.md:217-251` | `qwen3.6-27b` ≠ `Qwen3.6-27B-262K` as served identities |
| `docs/PHASE_5F3B_HARNESS_OBS1_RUNTIME_ACTIVITY_COMPANION_DESIGN.md` §7, §8, §13.6, §18 | prohibited retention; companion field set; DX1 definition |

### 1.2 Installed Pi 0.85.1 (offline, read-only)

Launch target `dist/cli.js` (unbundled, `ar2/launch.py:80`) resolves the **nested**
`node_modules/@earendil-works/pi-ai`; no hoisted global `pi-ai` exists.
`openai-completions` is registered lazily (`openai-completions.lazy.js:2`).

| File | Established |
|---|---|
| `pi-ai/dist/api/openai-completions.js` | `streamSimple` 533-546; `buildParams` 581-765; `convertMessages` 881-913; `convertTools` 1146-1177; `detectCompat` 1236-1318; `getCompat` 1323-1356 |
| `pi-ai/dist/api/simple-options.js` | `buildBaseOptions` 10-35 (`maxTokens` from `model.maxTokens`) |
| `pi-ai/dist/models.js` | `getSupportedThinkingLevels` / `clampThinkingLevel` 551-581 |
| `dist/core/model-config.js` | schema; `compat` optional at provider/model/override level (61-97, 139-183) |
| `dist/core/provider-composer.js` | `mergeCompat` 5-21; `modelFromJson` 48-78; `applyModelsJson` 85-117; `streamWith` 315-330 |
| `dist/core/defaults.js` | `DEFAULT_THINKING_LEVEL = "medium"` |
| `dist/core/sdk.js` | thinking-level resolution 115-138; `onPayload` → `before_provider_request` 208-214 |
| `dist/main.js` | CLI `--thinking` / `model:level` handling 358-408 |
| `pi-agent-core/dist/agent.js` | `reasoning` from thinking level 292; tools from state 280-286 |
| `pi-agent-core/dist/agent-loop.js` | request context 185-196; **unregistered tool name → `tool_execution_start` + immediate error result "Tool … not found" + `tool_execution_end` with `isError`** (263-338, 403-407, 532-538); never reaches an extension |
| `dist/core/system-prompt.js`, `agent-session.js:738-768` | system prompt from tools/snippets/guidelines/cwd only |
| `dist/core/agent-session.js:608-614` | `session.model` is `agent.state.model` (the composed model object, unnormalized) |
| `dist/modes/rpc/rpc-mode.js:28-36`, `:347-362`; `dist/modes/rpc/jsonl.js:8-10` | `get_state` returns `session.model` and `session.thinkingLevel`, serialized with plain `JSON.stringify` |
| `dist/core/model-runtime.js:422-466` | `prepareRequest` / `streamSimple` |

Full digests are pinned in §14.2. Not inspected, and **not inspectable here**:
Pi 0.84.2/0.84.3 source; the B300 LiteLLM proxy; vLLM; any chat template.

---

## 2. Pi 0.85.1 effective compat semantics

### 2.1 Load path: models.json → model object

1. `ModelConfig.load` validates `compat` as optional (`model-config.js:152`, `:170`, `:179`).
2. `modelFromJson` sets `reasoning: definition.reasoning ?? false`,
   `maxTokens: definition.maxTokens ?? 16384`, `contextWindow: … ?? 128000`, and
   `compat: mergeCompat(providerConfig.compat, definition.compat)`
   (`provider-composer.js:62-77`).
3. `mergeCompat(base, override)` returns `base` when `override` is falsy
   (`:5-21`). With no compat at either level, `model.compat === undefined`. With a
   provider-level block only, `model.compat` **is that block's object**.

### 2.2 Request-time resolution

`getCompat(model)` (`openai-completions.js:1323-1356`): if `!model.compat` return
`detectCompat(model)`; otherwise, per field, `model.compat.<field> ?? detected.<field>`
(`openRouterRouting ?? {}` equals detected `{}`; `vllmPriority` is `undefined`
either way).

`detectCompat` (`:1236-1318`) classifies on provider-id and base-URL substrings
only. For `b300_pi_qualification` (or `aido-ar2-qwen36-direct-vllm`) and a base
URL containing none of `api.z.ai`, `open.bigmodel.cn`, `api.together.ai`,
`api.together.xyz`, `api.moonshot.`, `openrouter.ai`, `api.cloudflare.com`,
`gateway.ai.cloudflare.com`, `integrate.api.nvidia.com`, `api.ant-ling.com`,
`deepseek.com`, `cerebras.ai`, `api.x.ai`, `chutes.ai`, `opencode.ai`:

| Field | Detected | Line |
|---|---|---|
| `supportsDeveloperRole` | **`true`** | 1279 |
| `supportsReasoningEffort` | **`true`** | 1280 |
| `thinkingFormat` | `"openai"` | 1288-1298 |
| `supportsStore` | `true` → `store: false` | 1278, 597-599 |
| `supportsUsageInStreaming` | `true` → `stream_options.include_usage` | 1281, 594-596 |
| `maxTokensField` | `"max_completion_tokens"` | 1283 |
| `supportsStrictMode` | `true` → `strict: false` per tool | 1306, 1173 |
| `supportsOpenAIGrammarTools`, `cacheControlFormat`, `sendSessionAffinityHeaders`, `requires*`, budget fields | `false`/`undefined` | 1276-1310 |

`prompt_cache_key` is sent only if the base URL contains `api.openai.com` (`:588-591`).

**Precondition this document cannot discharge:** the B300 base URL matches none
of those substrings. CFG1 verifies it per run without recording the URL (§16 L6).

### 2.3 Absence vs. explicit value

Because resolution is per-field `??`, a block holding only
`supportsDeveloperRole` and/or `supportsReasoningEffort` changes exactly those
effective fields. **Block presence alone is request-inert.** Absence is
equivalent to explicit `true` for both flags, never to `false`. Option A
("compat block only") is therefore not a live variable; it is asserted offline
(T-3).

### 2.4 Where each flag is consumed

| Flag | Consumer | Effect |
|---|---|---|
| `supportsDeveloperRole` | `convertMessages` `:909-913` | system-prompt message role = `(model.reasoning && compat.supportsDeveloperRole) ? "developer" : "system"` |
| `supportsReasoningEffort` | `buildParams` `thinkingFormat === "openai"` branch `:727-736` | emit `reasoning_effort` iff `options.reasoningEffort && model.reasoning && compat.supportsReasoningEffort` |

No other consumer exists on this path, in the agent core, or in `agent-session.js`.

### 2.5 What `get_state` reports (FU1)

`get_state` serializes `session.model` — the **composed model object**, not the
request-time `getCompat` result — with plain `JSON.stringify`
(`rpc-mode.js:28-36`, `:347-362`; `jsonl.js:8-10`; `agent-session.js:608-610`).
Consequences, source-derived:

- arm Q: `model.compat === undefined` → the **`compat` key is absent** from the
  serialized model (`JSON.stringify` drops `undefined`);
- arm R: `model.compat` is the provider block → `{"supportsDeveloperRole": false}`;
- arm E: `{"supportsReasoningEffort": false}`;
- arm H: `{"supportsDeveloperRole": false, "supportsReasoningEffort": false}`.

`get_state` therefore reports the **declared config shape**, never the effective
`true/true`, `false/true`, `true/false` values. Those remain source-derived and
offline-conformance facts (T-3). The live manipulation check compares against
the declared shape (§8.2).

---

## 3. Current qualification request-shape derivation

### 3.1 Generated configuration for A/B/C

```json
settings.json:
{ "packages": [], "extensions": [], "skills": [], "prompts": [], "themes": [],
  "defaultTools": [], "enableSkillCommands": false, "defaultProjectTrust": "never",
  "enableInstallTelemetry": false, "enableAnalytics": false, "quietStartup": true,
  "retry": { "enabled": true, "maxRetries": 3, "baseDelayMs": 2000,
             "provider": { "maxRetries": 0 } } }

models.json:
{ "providers": { "b300_pi_qualification": {
    "baseUrl": "<runtime B300 URL>",
    "api": "openai-completions",
    "apiKey": "$PI_QUALIFICATION_B300_ROUTE_KEY",
    "models": [ { "id": "<qwen3-coder-next | minimax-m2.7 | qwen3.6-27b>",
                  "reasoning": true } ] } } }
```

**A, B and C differ only in `models[0].id`** (no candidate branch,
`i2_pi_config.py:19-22`; descriptor `i2_route.py:152-172`; symmetry preflight
`i2b_live_adapters.py:1739-1784`).

### 3.2 Provenance of each fact

| Fact | Class |
|---|---|
| provider id, `api`, `$ENV` apiKey, `reasoning: true`, emptied settings, retry block, absence of `compat` / `maxTokens` / `defaultThinkingLevel` | **AIDO explicitly configured** |
| `baseUrl` value | AIDO-configured from the environment; never recorded |
| `model.maxTokens = 16384`, `contextWindow = 128000` | **Pi defaulted** |
| effective compat, thinking level `"medium"` | **Pi defaulted** |
| served model ids in `GET /models` | **provider metadata declared** |
| role, `reasoning_effort`, `max_completion_tokens`, `store`, `stream_options`, `strict` | **Pi transformed** |
| what the proxy forwards; what the template renders | **backend/model merely receives** |
| Pi version, sentinel, `get_state` model/compat/thinking level, tool-execution events | **runtime merely claims** |
| Git changed paths, verification result | **AIDO observes independently** |
| broker accepted reads/edits/refusals | AIDO-authored, diagnostic only |

### 3.3 Thinking level

No `--thinking` flag and no `model:level` suffix (`ar2/launch.py:140-162`;
`main.js:369-400`); settings define no default; so `"medium"` (`sdk.js:115-131`,
`defaults.js:1`), unclamped for `reasoning: true` with no `thinkingLevelMap`
(`models.js:551-566`), passed as `reasoning: "medium"` (`agent.js:292`) →
`reasoningEffort: "medium"` (`openai-completions.js:539-545`).

### 3.4 First-request payload (source-derived, not observed)

```text
POST <baseUrl>/chat/completions
{
  model: "<candidate id>",
  messages: [ { role: "developer", content: <Pi system prompt> },
              { role: "user",      content: <task prompt> } ],
  stream: true, stream_options: { include_usage: true }, store: false,
  max_completion_tokens: min(16384, 128000 - estimate - 4096),     <- Pi-defaulted
  tools: [ aido_read {strict:false}, aido_edit {strict:false} ],
  reasoning_effort: "medium"
}
no tool_choice, temperature, prompt_cache_key, priority, chat_template_kwargs
```

`onPayload` is a no-op (no `before_provider_request` handler registered).

### 3.5 Independence and non-effects

The role decision reads only `supportsDeveloperRole`; the effort decision reads
only `supportsReasoningEffort`. They are **coupled only through
`model.reasoning`**, which is therefore not a valid lever. Neither flag changes
tool presence, tool content or ordering, `tool_choice`, `promptGuidelines`
placement, system-prompt placement, message ordering, or request path (§1.2
citations). **A role change is not "tools unavailable."** Later-turn replay can
differ only as a consequence of model output.

---

## 4. Historical AR2/O1 request-shape derivation

### 4.1 Exact historical configuration

Same settings document, and:

```json
{ "providers": { "aido-ar2-qwen36-direct-vllm": {
    "baseUrl": "<AIDO_VLLM_BASE_URL>",
    "api": "openai-completions",
    "apiKey": "$AR2_ROUTE_PLACEHOLDER_KEY",
    "compat": { "supportsDeveloperRole": false, "supportsReasoningEffort": false },
    "models": [ { "id": "Qwen3.6-27B-262K", "reasoning": true } ] } } }
```

O1 reuses this generator and argv unmodified; its record confirms Pi 0.84.3,
direct vLLM, `http`, placeholder key, identical flags, native max tokens 16384.

### 4.2 What can and cannot be derived

Under Pi 0.85.1 semantics this would yield `role: "system"` and no
`reasoning_effort`. **But the historical runs executed Pi 0.84.2/0.84.3, which
were not inspected.** Historical config inputs are established; the historical
request shape is **not source-verified**.

### 4.3 Identity boundary preserved

```text
historical   Qwen3.6-27B-262K   direct vLLM   placeholder key   Pi 0.84.x
current      qwen3.6-27b        B300 LiteLLM  B300 credential   Pi 0.85.1
```

Two distinct served identities on two distinct routes. Historical tool activity
is architecture/config evidence only and gives Candidate C zero qualification
credit.

---

## 5. Mechanically established differences (historical vs. qualification)

| # | Dimension | Historical AR2/O1 | Q1/Q2/Q3 |
|---|---|---|---|
| D1 | `compat.supportsDeveloperRole` | explicit `false` | absent → `true` |
| D2 | `compat.supportsReasoningEffort` | explicit `false` | absent → `true` |
| D3 | system-message role (0.85.1 semantics) | `system` | `developer` |
| D4 | `reasoning_effort` (0.85.1 semantics) | omitted | `"medium"` |
| D5 | **transmitted prompt shape** | task + AIDO manifest + tool sentence | **bare task text** |
| D6 | task names the implementation file | varies by case | never |
| D7 | route | direct vLLM | B300 LiteLLM proxy |
| D8 | served model identity | `Qwen3.6-27B-262K` | three other ids |
| D9 | Pi version | 0.84.2 / 0.84.3 | 0.85.1 |
| D10 | credential | fixed placeholder | real B300 credential |
| D11 | provider id | `aido-ar2-qwen36-direct-vllm` | `b300_pi_qualification` |

Identical by source: settings, tool allowlist and extension sources,
`reasoning: true`, no `maxTokens`, launch flags, `RunBounds()`, `CapDefinitions()`,
one prompt.

---

## 6. Variables that remain confounded

### 6.1 Between history and qualification (not removable by CFG1)

D5–D11 co-vary with D1–D4. **D5** is a competing harness-owned explanation held
constant and untested here. **D7**: the proxy may rewrite `developer`→`system`
and/or drop `reasoning_effort` (unobservable). **D9**: 0.84.x never inspected.
**D8**: no weights-identity claim.

### 6.2 Within CFG1 (controlled, not eliminated)

| Residual | Control |
|---|---|
| sampling nondeterminism | N=3 per arm; unanimity rule (§13) |
| backend load drift; abandoned backend inference from a prior run | sequential runs; Latin-square order; lifecycle closure before admission (§19); backend lifetime never claimed |
| per-run absolute `cwd` text in the system prompt | fresh root per run; accepted residual |
| backend rejection of a variant request | `INDETERMINATE_PROVIDER` (§12) |
| base URL matching a detection substring | pre-dispatch refusal (§16 L6) |
| installed Pi drift | seam-digest refusal (§16 L1) |
| leaked live resources from a prior run | `INDETERMINATE_LIFECYCLE` + stage halt (§19) |

---

## 7. Chosen CFG1 experiment topology

### 7.1 Decision among A/B/C/D

A (block only) is request-inert and proven offline. **B → arm R. C → arm E.
D → Stage 1 = {Q, R, E}; Stage 2 = H, conditional and separately authorized.**
No Stage-1 arm combines two changes.

### 7.2 Arms

One CFG1-owned generator. Arm Q is byte-identical to `write_qualification_pi_config`
output for the same inputs (T-1). Each other arm adds exactly one provider-level
`compat` object between `apiKey` and `models`.

| Arm | `compat` added to Q | Declared shape (§2.5) | Effective `supportsDeveloperRole` / `supportsReasoningEffort` | Role | `reasoning_effort` | Stage |
|---|---|---|---|---|---|---|
| **Q** | *(none)* | `ABSENT` | true / true | `developer` | `"medium"` | 1 |
| **R** | `{"supportsDeveloperRole": false}` | `DEVELOPER_ROLE_FALSE_ONLY` | **false** / true | **`system`** | `"medium"` | 1 |
| **E** | `{"supportsReasoningEffort": false}` | `REASONING_EFFORT_FALSE_ONLY` | true / **false** | `developer` | **omitted** | 1 |
| **H** | both `false` | `BOTH_FALSE_ONLY` | false / false | `system` | omitted | 2 only |

Rejected levers: `reasoning: false` (couples both, clamps thinking off);
`--thinking off` (frozen argv shape, session state); `defaultThinkingLevel`
(session state, not historical); a `before_provider_request` hook (frozen
extension); an HTTP-capturing proxy (frozen route).

### 7.3 Stage 1 schedule (pre-declared, unconditional)

```text
block 1:  run 1 Q   run 2 R   run 3 E
block 2:  run 4 R   run 5 E   run 6 Q
block 3:  run 7 E   run 8 Q   run 9 R
```

Each arm occupies each within-block position once. Nine runs, at most nine
prompt writes. Runs are strictly sequential and gated by the admission rule
(§19). **No run is repeated, replaced, reordered or added.**

### 7.3a Stage 2 schedule (frozen, FU7)

**Finding 5, stated precisely.** The schema already accepted
`stage_id = "S1" | "S2"` throughout (§16.3.1, §22.2–§22.4.2), an S2 ordinal
range of `1..6` (§16.3.8 step 2, §22.4.2), and a `_schedule_arm_for(stage_id,
run_ordinal)` contract that is the **one** shared derivation every consumer
calls by identity (§16.3.8.1) — but §13.2 stated Stage 2's exact order only
as "for example `Q H H Q Q H`," deferred to Stage 2's own future
authorization. A schema that accepts `"S2"` while `_schedule_arm_for("S2",
...)` has no frozen definition to implement is not implementable without
guessing, which `CFG1-IMPL` must never do (§7.5's own rule: never invent a
schema the implementation phase should not choose).

**The already-proposed counterbalanced example is frozen as the exact S2
schedule, not merely illustrated:**

```text
S2 block 1:  run 1 Q   run 2 H
S2 block 2:  run 3 H   run 4 Q
S2 block 3:  run 5 Q   run 6 H
```

i.e. `_schedule_arm_for("S2", ordinal)` for `ordinal` in `1..6` returns,
in order, `Q, H, H, Q, Q, H` — identical to §13.2's own example, now
frozen rather than illustrative. `block = ((ordinal - 1) // 2) + 1` and
`position = ((ordinal - 1) % 2) + 1`, mirroring S1's
`block = ((ordinal - 1) // 3) + 1` / `position = ((ordinal - 1) % 3) + 1`
derivation at the analogous block size for two arms instead of three. As
§13.2 already states, **exact positional balance is impossible with three
pairs of two arms** — position 1 carries `Q, H, Q` and position 2 carries
`H, Q, H` across the three blocks — and this asymmetry is accepted exactly
as it already was when the schedule was only an example; freezing it changes
nothing about that acknowledged property.

**This freezes only the diagnostic design.** It does **not** authorize Stage
2 execution. `5F3B-HARNESS-CFG1-LIVE-S2` (§14.1 item 3) remains separately
required and, if ever authorized, **must** use this exact frozen schedule —
its authorization supplies only a `stage_execution_id`, exactly as
`LIVE-S1`'s does, never an order, a count, or an arm assignment of its own
choosing (§14.1 item 3, revised).

**One schedule truth for S2, exactly as for S1.** Every place this design
already states "the one shared `_schedule_arm_for` function, never a
separately-reimplemented lookup" (§16.3.8.1, §22.3, §22.5.2) now has an
actual frozen S2 table to be that one function's S2 branch, not merely an S1
table with an S2 parameter the function cannot yet resolve. Regressions:
T-93 (§11.3).

### 7.4 Execution topology — why not the frozen qualification stack

The frozen stack cannot host CFG1 without amendment: the controller generates the
config itself (`semantic_controller.py:2533-2546`); the frozen argv preflight
requires the exact AR2 flag set; `build_child_environment` accepts only an
I2-issued config; the OBS1 emitter refuses non-corpus identities; and
`emit_evidence_or_refuse` stamps refusals with qualification identity.

CFG1 is therefore a new package (proposed `experiments/pi_harness_cfg1/`) that
**composes frozen modules unmodified**, following the O1 precedent. **Controller
authority and cleanup semantics are not inherited by that composition; §16–§22
freeze CFG1's own.**

| Reused unmodified | For |
|---|---|
| `ar2.fixtures.build_case_repository` / `remove_disposable_tree`; `ar2.capability.mint_capability`, `CapDefinitions()`, `_verify_root_authority` (consumed exactly as `i2b_workspace` already does) | fresh root authority, SED, ownership re-proof |
| `ar2.broker` (`BrokerBinding`, `RunState`, `BrokerRequestHandler`, `BrokerServer`) | broker session, capability, lifecycle |
| `ar2.launch.resolve_runtime_identity` pattern / `build_pi_argv`; `ar2.supervisor.PiRpcSupervisor`, `RunBounds()`; `ar2.handshakes` | runtime launch, RPC, H1/H2 |
| `ar2.pi_config.write_disposable_extension`, `scrub_generated_extension_config` + static extension sources | extension binding |
| `ar2.observation`, `ar2.verification.run_verification` | Git truth, verification |
| `qualification.i2_credentials.resolve_connection_after_preflight`; `i2_secret_context.build_secret_context` | credential-boundary ordering, URL validation |
| `qualification.i2_b300_route_observation.observe_b300_route_serves_model` | same-run route check |
| `qualification.runtime_activity.project_runtime_tool_activity`, `RuntimeToolActivitySnapshot`; `semantic_session.SemanticTurnOutcome` | OBS1 evidence |
| `qualification.safety.qualification_scrub_check` (pure check only) | artifact scrub |
| `ai_dev_orchestrator.workspace.canonical._is_symlink_or_reparse_point` (imported directly, exactly as `ar2.capability.py:39` already does — `from ai_dev_orchestrator.workspace.canonical import _is_symlink_or_reparse_point`) | symlink/junction/reparse-point detection for `RESULTS_ROOT` and execution-directory provenance (§16.3) |

| New, CFG1-owned | Constraint |
|---|---|
| run-workspace registry | mirrors `i2b_workspace` mint/claim/re-proof semantics (§17) |
| `cfg1_pi_config` generator | Q byte-identical to I2; variants differ by one subtree (T-1, T-2); issuance-bound to the run (§17) |
| child-environment builder | equal to I2's policy for identical inputs (T-4) |
| pre-dispatch baseline capture; turn-outcome mapping | equal to `_DispatchBaseline.capture` and the frozen positive allowlist mapping (T-5) |
| run state machine, classification, record, stage-closure record, writer, own refusal record | §12, §16–§22 |
| fixture `CFG1-T1` | never in the corpus, `VALID_TASK_IDS`, or qualification results |

If the implementation phase finds any "reused unmodified" item unconsumable
without editing it — including `ArtifactSafetyContext`/`qualification_scrub_check`
for CFG1 values — it must **STOP and report**, never edit the frozen module.

### 7.5 Implementation uncertainties resolved by this review (FU2)

Independent review established, by source inspection, three points the
original design left as open implementation-time questions. None requires
touching a frozen module:

1. **`qualification_scrub_check` is a generic pure payload/needle check**
   (`safety.py`'s scrub function, not `emit_evidence_or_refuse` and not
   `build_refusal_record`). CFG1 consumes only that pure check (§7.4's "reused
   unmodified" table) and owns its own refusal-record builder and record-kind
   literals (§21.2, §22.1). No edit to `qualification.safety` is needed for
   CFG1 to have its own refusal-record shape.
2. **`i2b_workspace.py` already imports the frozen private `_verify_root_authority`
   under a local alias** (`_frozen_verify_root_authority`,
   `i2b_workspace.py:290`) and documents that reuse in its own module docstring
   and `verify_run_workspace`. CFG1's workspace registry (§17) may follow that
   exact, already-accepted precedent — a local aliased import of
   `ar2.capability._verify_root_authority` — without amending `ar2.capability`.
3. **The accepted verification runner (`ai_dev_orchestrator.verification.runner`,
   consumed via `ar2.verification.run_verification`) launches with a fixed
   minimal child environment, not the parent process environment.** Verification
   is model-influenced code (L26); this confirms it is not handed the B300
   endpoint or credential through environment inheritance, consistent with
   L24's ordering (endpoint/token material scrubbed from disk before L26 runs).

None of the three modules named above is modified by CFG1. The remaining
implementation-time source checks, deferred by design because they require
running the actual implementation phase's offline suite against the installed
package, are:

- pin the exact SHA-256 of `dist/modes/rpc/jsonl.js` (§14.2);
- pin the exact SHA-256 of `pi-agent-core/dist/agent-loop.js` (§14.2);
- confirm the exact installed `get_state` response shape (field names and
  nesting) matches §2.5/§8.2's derivation, via an offline test against the
  installed package rather than by further reading here.

A mismatch in any of these at implementation time is a re-review trigger
(§14.2), not evidence that Pi is incompatible.

---

## 8. Why this topology isolates the intended variable

### 8.1 Isolation argument

1. **Single-field manipulation, proven twice** — offline document diff (T-2)
   and source (§2.3–§2.4).
2. **Offline request conformance** — T-3 executes the installed request builder
   against each arm with network interception installed first (§11.3).
3. **Pre-dispatch declared-shape check** — §8.2. A mismatch refuses the run
   **before** the prompt is written.
4. **Shared, time-matched control** — Q interleaved with R and E.
5. **Lifecycle isolation** — no run starts until the previous run's live
   resources are proven closed (§19).
6. **Everything else frozen** — §8.3.

### 8.2 Runtime manipulation check — declared shape, not effective values (FU1)

After H2, one `get_state` response is projected (bounded literals only, never
`baseUrl`, headers, or any other model field):

| Projection | Domain |
|---|---|
| `runtime_reported_compat_shape` | `ABSENT` (no `compat` key) · `DEVELOPER_ROLE_FALSE_ONLY` (exactly `{supportsDeveloperRole: false}`) · `REASONING_EFFORT_FALSE_ONLY` · `BOTH_FALSE_ONLY` · `OTHER` (any other key set, any value other than exact JSON `false`, or a non-object) · `NOT_OBSERVED` |
| `runtime_reported_model_reasoning` | `TRUE` · `FALSE` · `OTHER` · `NOT_OBSERVED` |
| `runtime_reported_thinking_level` | `off` · `minimal` · `low` · `medium` · `high` · `xhigh` · `max` · `OTHER` · `NOT_OBSERVED` |

`manipulation_check_agrees` is true iff shape equals the arm's **declared** shape
(§7.2), reasoning is `TRUE`, and thinking level is `medium`. The check never
demands an explicit `true` for an absent field. If a live `get_state` ever
normalizes the model differently from §2.5, the run refuses as
`CONFIG_SHAPE_MISMATCH` (pre-dispatch, stage halts); the design is not silently
re-read.

### 8.3 Frozen across all arms and runs

```text
ROLE              implementer-style single-shot task (no reviewer)
HARNESS           Pi 0.85.1 with pinned seam digests, Node-direct RPC
PROVIDER route    b300_pi_qualification -> B300 LiteLLM proxy
MODEL             qwen3-coder-next for the whole stage
task / prompt     CFG1-T1, byte-identical prompt, bare transmission
tool allowlist    ("aido_read", "aido_edit")
extension         AR2 static sources, unmodified
workspace         fresh disposable Git repository per run
verification      fixed argv, witness-protected
OBS1 evidence     project_runtime_tool_activity / RuntimeToolActivitySnapshot, unmodified
settings.json     identical bytes
timeouts          RunBounds() defaults; broker deadlines; verification 300 s
retry policy      no AIDO semantic retry; Pi settings retry block identical
prompt writes     at most one per run
token policy      no AIDO maxTokens
credential policy PI_QUALIFICATION_B300_ROUTE_KEY via $ENV interpolation only
lifecycle         §16 state machine, identical for every run
```

**The only variable:** the provider-level `compat` object.

---

## 9. Candidate/model choice

**`qwen3-coder-next` (the frozen Candidate A pairing), diagnostic subject only.**
The Q pattern is candidate-invariant; A and B hold standalone Category-B passes on
this route and C does not; lowest-key tie-break between A and B is pre-declared;
C is not chosen and specifically not because of its name. No qualification credit,
verdict change, ranking or hard-bar input follows. Replication on another model
is separately authorized.

---

## 10. Synthetic task/fixture choice

### 10.1 Why a new task

IQ tasks are frozen lineage inputs and OBS1 §13.6 forbids probe reuse. CFG1's
dependent variable is whether the model requests the offered tools.

### 10.2 `CFG1-T1` (content fixed at implementation, then digest-pinned)

```text
greeting/__init__.py          empty
greeting/banner.py            banner(name) returns "Hi, " + name + "!"       <- seeded defect
tests/test_banner.py          asserts banner("Ada") == "Hello, Ada!"         <- protected witness
```

`seeded_failure` with exactly one failing test; `expected_changed_paths =
{"greeting/banner.py"}`; IQ-form protected patterns; `verification_args = ("-B",
"-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf", "tests/test_banner.py")`;
`names_the_implementation_file = True`; `manifest_in_prompt = False`; bare
transmission. Prompt (fixed; names no tool; no manifest):

> In this repository, the function banner(name) in greeting/banner.py must
> return exactly "Hello, " followed by the name and "!". For example,
> banner("Ada") must return "Hello, Ada!". It currently returns a different
> greeting. Change greeting/banner.py so it returns the documented text.
> Do not change any test file. Finish when the change is complete.

### 10.3 Rationale and trade-off

`aido_edit` requires the `aido_read` sha, so an edit implies a read. Naming the
path removes discoverability as a competing cause of inactivity. **Trade-off:**
CFG1 does not test D5 (§13.4).

### 10.4 Distinction from DX1

CFG1 is a paired contrast in which Q exists only as the control. Q runs are
interpreted only jointly with R and E, are never DX1 evidence, and do not pre-empt
DX1.

---

## 11. OBS1 evidence requirements

### 11.1 OBS1 reuse (frozen by the F2 decision)

- `project_runtime_tool_activity(activity, baseline, turn_outcome=...)` and
  `RuntimeToolActivitySnapshot` are **imported and called, never copied or
  subclassed** (T-6).
- `activity` is the run's own `PiRpcSupervisor.activity`; `baseline` is captured
  strictly before the one prompt write (§16 L17), carrying
  `agent_loop_event_counts` and a `frozenset` `pre_dispatch_tool_call_ids`,
  semantically equal to `_DispatchBaseline.capture` (T-5).
- `turn_outcome` is a `SemanticTurnOutcome` member mapped from the supervisor
  wait outcome through the **same positive allowlist** the frozen live adapter
  uses (`semantic_live_adapters.py:234-248`): `runtime_settled → SETTLED`;
  `runtime_deadline_expired → DEADLINE_REACHED`; every other recognized or
  unrecognized outcome → `OBSERVATION_FAILED` (T-5).
- Preserved without modification: per-dispatch delta correlation, capture basis
  (`agent_settled` iff `SETTLED`), the three-category vocabulary with exact
  case-sensitive matching, exact int/bool typing, the snapshot's cross-field
  invariants, and the absence of arguments, results, reasoning and literal tool
  names.
- An `ActivityRecordInvariantError` or any other projection failure sets
  `runtime_reported_tool_activity_available = false` and
  `activity_unavailable_reason = PROJECTION_REFUSED | INTERNAL_ERROR`; no
  exception text is retained.

### 11.2 Record content

The record field set, its closed domains, and its authority rules are specified
in **§22**. §21 governs what may never enter it.

### 11.3 Required offline tests (implementation phase)

| Id | Proves |
|---|---|
| T-1 | arm Q `settings.json`/`models.json` byte-identical to `write_qualification_pi_config` for the same synthetic inputs |
| T-2 | R, E, H parse-equal Q except exactly the declared `compat` subtree; redacted digests equal the pinned per-arm expectations |
| **T-3** | **offline request conformance under network interception** (below) |
| T-4 | CFG1 child environment equals I2's for identical inputs (names and non-secret values) |
| T-5 | baseline capture equals `_DispatchBaseline.capture`; turn-outcome mapping equals the frozen allowlist mapping, over every supervisor outcome literal plus an unknown literal |
| T-6 | OBS1 projection/snapshot imported, not copied; no OBS1 symbol redefined |
| T-7 | `sanitized_events` retains `message_end.message.stopReason` for a captured-shape synthetic record; otherwise `stop_reasons_available = false` and §12 applies |
| T-8 | CFG1 imports nothing from `hard_bar`, `ranking`, `validity`, `outcomes`, `records` builders, `lineage`, `semantic_sweep`, `semantic_controller` |
| T-9 | no CFG1 artifact is accepted by `lineage._require_run_record_shape` or `verify_activity_companion_binding` |
| T-10 | no test opens a socket, reads a real credential/endpoint, launches Pi, or calls a model |
| T-11 | the §16 state machine: every failure injected at every step reaches exactly the closure steps and classification §18 declares, using synthetic doubles |
| T-12 | ownership refusals: shutdown/removal of a broker, supervisor, config, or workspace not minted by the current run is refused before any side effect |
| T-13 | **payload-only** record authority (§22): closed keys, literal pins, schedule relations, digest binding, classification recomputation, TOCTOU-safe canonical snapshot, `stage_execution_id` grammar, and the internal `record_filename` field's self-consistency with the record's own `(stage_id, run_ordinal, arm_id)`. **This proves only that a record's declared fields agree with each other — it proves nothing about the record's actual filesystem location.** That stronger claim is T-33–T-37 against the artifact-binding verifier (§22.5), not this test (FU3 correction) |
| T-14 | admission rule (§19): no ordinal is admitted after a lifecycle failure, a pre-dispatch refusal, or an emission collision |
| T-15 | containment (§21): hostile raw values (URL, key, paths, pipe name, token, exception text, `worker_error`, `extension_errors`, verification output, fake `FAILED http://…` lines) never reach console, record, or refusal record |
| T-16 | a valid authorized identifier produces an execution directory that is exactly one child of the fixed CFG1 results root (§16.3) |
| T-17 | `"."` and `".."` are refused before any `mkdir` call |
| T-18 | a forward slash, a backslash, an absolute Unix path, a Windows drive-qualified path, a UNC/device-like value (`\\?\`, `\\.\`, `\\host\share`), an embedded NUL, any other control character, and leading/trailing whitespace are each refused before any `mkdir` call |
| T-19 | `pathlib.Path`, any `PathLike` (an object with `__fspath__`), a `str` subclass, `int`, `bool`, and `None` are each refused before any filesystem operation — read via a single local binding, never re-consulted (§16.3 TOCTOU closure) |
| T-20 | an already-existing execution directory refuses the entire stage before any run; the pre-existing directory's content is unchanged afterward |
| T-21 | **no public WRITE/EMISSION API accepts a caller-selected results-root, execution-directory, run-output-path, stage-closure-path, filename, or `arm_id` parameter** (narrowed, FU6: FU4's wording — "no CFG1 function... accepts" — became false the moment FU5's `verify_cfg1_*_binding(actual_path)` shipped, since those read-only verifiers intentionally accept a path; this test now scopes to the writer/emission surface only, mirroring T-38's identical narrowing, §16.3.8 Finding 5). `arm_id` is included (FU4), and §16.3.8's `emit_cfg1_*` writers are the entire public write/emission API — see T-38–T-40. The stage-closure path derives from the same internal filename derivation as run records; no timestamp, fallback, or replacement output path exists anywhere in the write/emission surface. **The read-only `verify_cfg1_run_artifact_binding`/`verify_cfg1_stage_closure_binding` functions' `actual_path` parameter is an intentional, explicit exception to this test, never a violation of it** — location is the object being verified, and accepting it grants no write authority (§22.5.1). (FU3 correction, unchanged: the claim "one valid record cannot be relabelled to another output path" is **removed from this test** — payload-only validation cannot prove that; it is T-33/T-34 against the artifact-binding verifier, §22.5.) |
| T-22 | filesystem-operation spies (`mkdir`/`open`/`write` intercepted) prove every malformed identifier in T-17–T-19 reaches **zero** such calls |
| T-23 | `RESULTS_ROOT` absent on first run: `establish_stage_output_authority` creates it, then proves it (§16.3.2) — accepted |
| T-24 | `RESULTS_ROOT` already a normal directory (every run after the first): step 1 no-ops, step 2 proves it — accepted |
| T-25 | direct `CFG1StageOutputAuthority(...)` construction, with every field set to plausible values but an unregistered `mint_nonce`, fails `__post_init__` with `UNKNOWN_MINT_NONCE` before any filesystem operation — proves direct construction cannot authorize any path or write |
| T-26 | a forged/guessed `mint_nonce` (never issued by `establish_stage_output_authority`) fails identically to T-25 |
| T-27 | a genuinely-minted authority with one field mutated via `object.__setattr__` (bypassing `frozen=True`) fails `verify_stage_output_authority`'s registry field-equality re-check (§16.3.4) at the next consumption boundary — proves a nonce learned from the genuine object, reused alongside substituted fields, gains no authority beyond that exact mint |
| T-28 | a genuinely-minted, unmutated authority passes `verify_stage_output_authority` and produces a valid path — accepted |
| T-29 | **filesystem tampering:** `RESULTS_ROOT`'s directory entry is replaced with a real symlink (POSIX) or junction (Windows, via the platform's reparse-point creation call) pointing outside the package before `establish_stage_output_authority` runs — refused as `RESULTS_ROOT_REDIRECTED` before any execution directory is derived or created |
| T-30 | `RESULTS_ROOT`'s path is occupied by a plain file instead of a directory — refused (both via `mkdir`'s `FileExistsError` and, independently, §16.3.2 step 2(c)) |
| T-31 | **filesystem tampering:** after a genuine mint, the execution directory is deleted and replaced with a real symlink/junction to another directory, then a second run's `emit_cfg1_run_record` call is made — `verify_stage_output_authority`'s re-`lstat` (§16.3.4 step 5) refuses before any write, proving a post-mint redirect is caught at the next consumption boundary, not just at mint time |
| T-32 | (reserved for a Windows-only ancestor-canonicalization case — e.g. an 8.3 short-name alias of `trusted_package_dir` — if the implementation platform can construct one; §16.3.2 step 2(d) must refuse it) |
| T-33 | **filesystem tampering:** a genuine, unmodified `results/S1-X1/S1_01_Q.json` payload is copied byte-for-byte to `results/S1-X2/S1_01_Q.json` (a different, also-genuine execution directory created for this test). The copied file's payload still validates against T-13's payload-only checks (its internal fields are self-consistent). `verify_cfg1_run_artifact_binding(actual_path)` — the one-argument API, §22.5.2 (FU5) — returns **false**, because the actual parent directory name (`S1-X2`) disagrees with the artifact's own `stage_execution_id` (`S1-X1`), read from the file itself |
| T-34 | a genuine run record is renamed in place from `S1_01_Q.json` to `S1_02_R.json` without touching its payload — `verify_cfg1_run_artifact_binding` returns **false**, because the actual filename disagrees with the filename recomputed from the payload's own `(stage_id, run_ordinal, arm_id)` |
| T-35 | a genuine stage-closure record is moved to a different, also-genuine execution directory — `verify_cfg1_stage_closure_binding` returns **false**, by the same parent-directory-name mismatch as T-33 |
| T-36 | a syntactically valid, internally self-consistent record is placed at a path entirely outside `RESULTS_ROOT` (for example a sibling temp directory) — both binding verifiers return **false**, because the fixed-root containment check (re-run inside the verifier, §22.5) fails first |
| T-37 | a genuine run record, in its genuine, untouched execution directory, and a genuine stage-closure record in its genuine directory — both binding verifiers return **true** |
| T-38 | **audits the public write/emission surface, not every public CFG1 function** (narrowed, FU6, §16.3.8 Finding 5). Signature-inspection audit (e.g. `inspect.signature`) over every `emit_cfg1_*` writer proves none declares a parameter named or typed as a path, filename, directory, `results_root`, `execution_directory`, or `arm_id` — the write/emission API surface itself, not documentation, forbids it (§16.3.8 Findings 1 and 2). **This audit explicitly excludes `verify_cfg1_run_artifact_binding`/`verify_cfg1_stage_closure_binding`**, whose one `actual_path` parameter is the read-only, intentional exception T-21 also states — including the two verifiers in this audit's scope would make the audit fail against the design's own accepted, frozen API, which is exactly the FU4/FU5-era wording error FU6 corrects |
| T-39 | with a genuine, ACTIVE authority in hand, calling any `emit_cfg1_*` writer with an additional/positional path-shaped argument raises `TypeError` from Python's own argument binding, proven directly — there is no supported way for a caller, however privileged, to write to an arbitrary path even while holding genuine authority |
| T-40 | **corrected to the step-6 payload-schema-failure class (FU7 Finding 4 — the FU6 text was itself wrong).** `_schedule_arm_for("S1", 1)` returns `"Q"` (the real §7.3 schedule). A run-record payload claiming `arm_id="E"` or `arm_id="R"` for `run_ordinal=1` is **not** internally self-consistent: §22.3's own cross-field invariant already requires `(stage_id, run_ordinal) ↦ arm_id` to equal `_schedule_arm_for(stage_id, run_ordinal)` as a **pure function of the payload's own two fields**, with no authority object needed to state or check it. Such a payload is therefore refused by `_require_valid_cfg1_run_payload` at **step 6**, before step 7's authority binding ever runs — proven by constructing the payload, calling the validator directly, and observing the refusal, then separately calling the full writer and observing zero authority-binding-specific refusal codes are ever reached (the step-6 refusal fires first). This is the FU6 text's own error, corrected: FU6 had claimed such a payload was "internally self-consistent" and caught only at step 7, which Finding 4 shows is false. See T-58's `Case B` for the genuinely step-7-only construction (a *different* ordinal's own fully-valid, self-consistent record) |
| T-41 | ordinal `0`, ordinal `10` (outside `S1`'s declared `1..9` range), `True`/`False` (rejected as not-exactly-`int`, since `bool` is an `int` subclass), and a `str` ordinal (e.g. `"1"`) are each refused before any schedule lookup is attempted |
| T-42 | valid ordinals `1..9` derive exactly the real schedule's own arms (`Q,R,E,R,E,Q,E,Q,R` per §7.3), and `L0`, payload construction, the writer, the record validator (§22.3), and the artifact-binding verifier (§22.5.2 step 10) are proven, by identity of the underlying callable object, to invoke the **same** `_schedule_arm_for` function — not five independently-reimplemented lookups that merely happen to agree today |
| T-43 | **filesystem tampering:** after `_CAPTURED_PACKAGE_DIR` is captured (module import), the package directory's own leaf, or one of its ancestors, is replaced with a real symlink/junction; `establish_stage_output_authority` refuses at Level A (`PACKAGE_DIR_REDIRECTED`/`PACKAGE_DIR_NOT_CANONICAL`) before `RESULTS_ROOT`'s `mkdir` is ever attempted, and no foreign `results/` directory is created anywhere on disk (§16.3.2) |
| T-44 | a genuinely-minted, unretired authority passes `verify_stage_output_authority` and every writer throughout one active stage's full run — positive control (§16.3.9) |
| T-45 | the same authority, presented again after the stage's **normal successful completion** (retirement already performed per §16.3.9's table), fails `verify_stage_output_authority` at `UNKNOWN_MINT_NONCE` |
| T-46 | the same authority, presented again after an **ordinary halt**'s own stage-closure write has completed (retirement already performed), fails identically |
| T-47 | the same authority, presented again after a **§16.3.7 hard-stop** retirement, fails identically — and, additionally, no write of any kind to `results/` occurred at any point after the provenance failure was first detected, matching §16.3.7's own guarantee |
| T-48 | the same authority, presented again after a **stage-closure record's own exclusive-create collision**, fails identically, and no fallback/replacement write was attempted for that collision |
| T-49 | every path-deriving/consuming helper and every `emit_cfg1_*` writer, called with a retired authority (one instance per retirement cause of T-45–T-48), refuses at its own first, unconditional `verify_stage_output_authority` call, before any filesystem operation |
| T-50 | `verify_cfg1_run_artifact_binding`/`verify_cfg1_stage_closure_binding` called with `actual_path` of type `None`, `int`, `bool`, `pathlib.Path`, an object with a custom `__fspath__`, and a `str` subclass each return `False`, with **zero** filesystem calls made (spy-proven, mirroring T-22) — this row is unaffected by FU5, since the `actual_path` type gate is unchanged |
| T-51 | **Retargeted (FU5).** This row originally tested the removed `parsed_record` parameter's type gate. FU5 deletes that parameter entirely (T-58), so the equivalent hostile-`Mapping`/`dict`-subclass concern now applies at the **writer** boundary instead: `emit_cfg1_run_record`'s `payload` and `emit_cfg1_refusal_record`'s `refusal_payload`, called with a hostile non-`dict` `Mapping` and separately a genuine `dict` **subclass**, each refuse at §16.3.8 step 3, before any field is read — see T-55 |
| T-52 | **Retargeted (FU5).** The "value changes on a second read" concern is now a **writer**-side property: a `payload` whose value for one key is a custom object that would answer differently on a second `__getitem__`/equality check cannot influence more than §16.3.8 step 4's single `json.dumps` walk — see T-57. The verifier itself never accepts such an object at all post-FU5 (there is no `parsed_record` parameter for one to be supplied through), which is the *stronger* property T-58 states directly |
| T-53 | **Retargeted (FU5).** `parsed_record` missing a required identity field, and containing a non-JSON-serializable nested value, are now: a writer-side canonicalization/validation failure for `payload` (T-56, §16.3.8 steps 4 and 6), and separately a verifier-side "the file's actual bytes are malformed JSON / not a conforming object" case reading **real** on-disk bytes (T-66, T-67) — never a second-argument gate, because there is no second argument |
| T-54 | a genuine `str` path to a genuine, fully §22.1–§22.3-valid, **on-disk** record (the verifier reads it itself; no second argument exists to pass a snapshot through) returns `True` — positive control, overlapping T-37 and restated explicitly here as the single-argument-API case; see also T-68 |
| T-55 | **writer input ordering (FU5, §16.3.8 Finding 3).** `emit_cfg1_run_record`'s `payload` and `emit_cfg1_refusal_record`'s `refusal_payload`, called with a hostile non-`dict` `Mapping` (hand-rolled `__getitem__`/`keys()`) and separately a genuine `dict` **subclass**, are each refused at step 3's exact-type gate — with **zero** payload-field reads having occurred, spy-proven exactly as T-22 proves it for the identifier grammar |
| T-56 | a `payload`/`refusal_payload` that raises during the step-4 `json.dumps` walk (a non-JSON-serializable nested value, e.g. raw `bytes` or a custom class instance) is refused with no exception text retained; a canonicalized payload missing a required key is separately refused at step 6 by the existing §22.1–§22.3 validator — neither case ever reaches step 7's identity binding |
| T-57 | a `payload` object whose `__getitem__`/equality would answer differently on a second read cannot influence the writer's decision, because `payload` — the original argument — is read exactly once (step 4) and never consulted again (step 5, T-55's zero-reads-before-canonicalization proof extended one step further); the writer's outcome is provably a function of the one canonical snapshot only |
| T-58 | **writer authority↔payload binding, run-record — genuinely constructible valid-other-identity cases only (FU5, §16.3.8 Finding 4; corrected to exclude logically-impossible variants, FU7 Finding 4).** FU6's five-variant list included an `arm_id`-only and a `record_filename`-only mismatch; both are **removed**, because §22.3 already makes `arm_id` and `record_filename` pure functions of `(stage_id, run_ordinal)` (and, for the filename, `arm_id` too) — a payload claiming a "wrong" value for either, with everything else held at the *same* ordinal, is already internally inconsistent and is refused at **step 6** (see T-91), never reaching step 7 at all, so it cannot demonstrate step 7 is load-bearing. The mandatory constructions, each first proven to pass `_require_valid_cfg1_run_payload` under its own claimed identity (T-92), then refused only at step 7 against a genuine, ACTIVE `S1-X1` authority: **Case A** — the same valid `S1` schedule identity (ordinal, arm, block, position, filename all mutually correct for the claimed ordinal), differing from the authority in exactly `stage_execution_id` (claiming a different, also grammar-valid `S1-X2`, itself a genuine sibling execution directory — see T-33). **Case B** — a complete, fully-valid record for a *different* `S1` ordinal: a different `run_ordinal`, with matching block, matching position, matching schedule-derived arm, and matching schedule-derived filename all for **that** ordinal — internally perfect, but presented to a writer minted for a different one. **Case C** — a complete, fully-valid `S2` identity (using §7.3a's now-frozen `S2` schedule: a valid `S2` ordinal with its own correct arm/block/position/filename) presented to an `S1` authority. All three pass step 6 and are refused only at step 7 |
| T-59 | the identical three cases (A/B/C), each again first proven to pass `_require_valid_cfg1_refusal_payload` under its own claimed identity (T-92), applied to `emit_cfg1_refusal_record`'s retained identity fields (`stage_id`, `stage_execution_id`, `run_ordinal`, `arm_id`) and its internally derived run-artifact filename, are each refused identically at step 7 — a refusal record cannot claim a different stage execution than the authority under which it is written, even when every one of its own fields agrees with itself |
| T-60 | for `emit_cfg1_stage_closure`, **valid-other-identity cases only (corrected, FU7 Finding 4): a filename-only mismatch is removed** — §22.4.2 already makes the stage-closure `record_filename` a pure function of `stage_id` alone, so a payload disagreeing with its own claimed `stage_id`'s filename is self-inconsistent and refused at step 6 (T-91), not a step-7 case. The two constructible cases, each first proven to pass `_require_valid_cfg1_stage_closure_payload` under its own claimed identity (T-92): a fully valid `stage_execution_id`-only mismatch (a different, also grammar-valid execution id under the **same** `stage_id`); and — now constructible under §7.3a's frozen `S2` schedule — a complete, fully-valid `S2` stage-closure identity (correct `stage_id = "S2"` with `S2`'s own correct closure filename) presented to an `S1` authority. Both are refused at step 7, before write |
| T-61 | a genuine canonical payload, bound in every field to the genuine authority (matching every field T-58–T-60 independently vary), is accepted and written — positive control for §16.3.8's full ten-step sequence |
| T-62 | **verifier has no second parameter (FU5, §22.5.2 Finding 5).** Signature inspection (`inspect.signature`) proves `verify_cfg1_run_artifact_binding` and `verify_cfg1_stage_closure_binding` each accept **exactly one** parameter, `actual_path`; there is no `parsed_record` parameter through which a stale, previously-parsed, or hand-built record object could be supplied — proven by the API surface itself, not merely documented |
| T-63 | **filesystem tampering, lexical-before-`resolve()`:** a real symlink whose leaf name matches a genuine record's filename, pointing at that genuine record, returns `False` from Step 1's lexical `lstat` — before `resolve()` is ever called, so the symlink's own presence is what is detected, not merely where it happens to point; separately, a real symlink/junction standing in for the record's parent (execution) directory returns `False` the same way, at the parent `lstat` |
| T-64 | a real directory created at a path shaped exactly like a record filename (e.g. `S1_01_Q.json/`) returns `False` at Step 1's `S_ISREG` check, never reaching `resolve()` or any read |
| T-65 | **genuine artifact, then on-disk tamper, detected by a fresh call — one exact mutation, one mandatory outcome (determinism pinned, FU6).** A genuine run record passes verification (`True`). Its on-disk JSON bytes are then directly edited to change **only** the `stage_execution_id` field's value from its genuine `"S1-X1"` to a different, still grammar-valid identifier `"S1-X2"` (schema-valid, without moving the file — every other field, and the file's actual path, is left untouched). A **fresh** call to the same verifier on the same `actual_path` re-reads and re-parses from scratch and **MUST return `False`** — never `True` under any circumstance — because the edited payload's own `stage_execution_id` now disagrees with its actual parent directory name (still `S1-X1`), failing Step 4 item 8 exactly as T-33 fails it. No cached result from the earlier call ever influences this one. A **separate** positive-control case — a fresh call against a genuine, entirely unchanged artifact, made after the tampered case above ran against a *different* path — returns `True`, proving the fresh-read discipline itself rather than merely the tamper detection |
| T-66 | the same artifact, with its on-disk bytes replaced by syntactically malformed JSON, returns `False` |
| T-67 | the same artifact, with its on-disk bytes replaced by the literal `{}`, returns `False` — it parses as a JSON object (passing the bare type check) but fails every dispatched payload validator's required-key checks at Step 3 (the discriminator lookup itself also fails first, since `{}` carries neither `record_version` nor `record_kind` — either failure reason independently returns `False`, and the test asserts `False`, not a specific internal reason) |
| T-68 | a genuine run record, read via `verify_cfg1_run_artifact_binding(actual_path)` from its own current, untouched bytes, returns `True`; a genuine stage-closure record likewise returns `True` via `verify_cfg1_stage_closure_binding` — positive controls under the finalized one-argument API, extending T-37/T-54 |
| **T-69** | **three-validator schema isolation (FU6, §22.4.3 Finding 1/5).** A full matrix: a genuine, valid `pi-harness-cfg1-run.v1` payload is refused by `_require_valid_cfg1_refusal_payload` and by `_require_valid_cfg1_stage_closure_payload`; a genuine, valid `pi-harness-cfg1-refusal.v1` payload is refused by `_require_valid_cfg1_run_payload` and by `_require_valid_cfg1_stage_closure_payload`; a genuine, valid `pi-harness-cfg1-stage-closure.v1` payload is refused by `_require_valid_cfg1_run_payload` and by `_require_valid_cfg1_refusal_payload`. Each of the six cross-calls is refused by a **closed-key-set** mismatch, not merely a coincidental literal mismatch — proving no validator is a wrapper that happens to also accept a foreign schema's shape |
| T-70 | a canonical payload whose serialized `artifact_bytes` is exactly `MAX_CFG1_ARTIFACT_BYTES` (`65536`) bytes is accepted by the writer's size check and by the verifier's bounded read (§16.3.8.1) |
| T-71 | a canonical payload whose serialized `artifact_bytes` is `65537` bytes is refused by the writer's size check before any exclusive-create, and, separately, an on-disk artifact of `65537` bytes is refused by the verifier's bounded read before any JSON parse (§16.3.8.1) |
| T-72 | **exact-bytes proof (Finding 4, FU6).** For all three record kinds, a spy wrapping the writer's serialization call proves it is invoked **exactly once** per emission, and the bytes passed to the size check (step 8) and the bytes passed to the exclusive-create write (step 10) are the **same object** (or byte-identical, if the implementation copies) — never two independently-produced serializations of the same `canonical` object, even ones expected to agree |
| T-73 | **refusal writer non-recursion (Finding 3, FU6, §16.3.8.2).** `emit_cfg1_refusal_record`, made to fail internally at each of construction, canonicalization, schema validation, authority binding, scrub, size check, and write in turn (one synthetic failure per sub-case), is proven — by a spy on the writer entry points — to call itself, or any other `emit_cfg1_refusal_record` invocation, **zero** times in every sub-case; it returns one bounded emission-failure result instead |
| T-74 | **stage-closure writer non-recursion, all sub-phases (Finding 3, FU6, §16.3.8.2; phase coverage made explicit, FU8).** `emit_cfg1_stage_closure`, made to fail internally at each of: `PRE_CREATE` validation, `PRE_CREATE` scrub, `PRE_CREATE` size check; and, separately, the post-create sub-phases — the exclusive-create call itself (both the collision case and a non-collision I/O-error case), a write-data failure, a flush failure, and a close failure — is proven, in **every** one of these seven sub-cases, by a spy on `emit_cfg1_refusal_record`'s entry point, to call it **zero** times, distinct from and in addition to T-73's proof that the refusal writer does not call itself |
| T-75 | **refusal-emission internal failure end-to-end, truthful code (FU6, §18 row 16; claim narrowed to the pre-create case, FU7; halt code corrected, FU8 Finding 1).** A primary run-record emission failure whose one permitted refusal fallback also fails **at a `PRE_CREATE` step** (T-73's construction/canonicalization/schema/authority-binding/scrub/size sub-cases, all of which precede any final-path exclusive-create) produces exactly the §18 row 16 outcome: the stage halts, **zero writes occurred at the run path at any point** (spy-proven zero exclusive-create calls, mirroring T-22 — this "zero writes" claim is mechanically true here specifically because every injected failure is `PRE_CREATE`), and the stage-closure record — if authority is still valid, which it is here — records `EMISSION_FAILED` for that ordinal with `halt_reason_code == RUN_RECORD_EMISSION_FAILED` (renamed from FU7's `RUN_RECORD_REFUSAL_FALLBACK_FAILED`, §19.4 Finding 1 — the code is deliberately neutral and asserts nothing about whether a fallback was attempted; this row's own **console-only** diagnostics may still show a fallback occurred and failed, but the durable `halt_reason_code` never says so, exactly as it would not for T-95's direct post-create case where no fallback was attempted at all), never `EVIDENCE_REFUSED` and never `EMISSION_COLLISION`. **The corresponding post-create sub-case, where residue may exist and "zero writes" would be false, is T-86/T-95 — not this test** (FU7 correction: an earlier draft of this row made an unconditional "no artifact of any kind exists" claim that a post-create refusal-writer failure would falsify) |
| T-76 | **stage-closure `PRE_CREATE`-only failure end-to-end (FU6, §18 row 17; narrowed to the pre-create sub-case, FU8 Finding 3).** A stage-closure emission failure at a `PRE_CREATE` sub-phase (T-74's validation/scrub/size sub-cases, all strictly before the exclusive-create call) produces exactly the §18 row 17 outcome: **zero final-path create calls occurred (spy-proven, mirroring T-22), so no artifact — valid, malformed, or partial — exists on disk for the stage-closure path at all**; reporting is console-only, the stage-output authority is retired immediately (§16.3.9's revised row), and every run record genuinely written before this failure remains on disk, untouched and individually still `True` under `verify_cfg1_run_artifact_binding`. **The "no artifact exists" claim in this row is scoped strictly to the `PRE_CREATE` sub-case — the post-create sub-case, where residue may exist and this claim would be false, is T-98, not this test** (FU8 correction: an earlier draft of this row made an unconditional "no stage-closure record exists on disk at all" claim regardless of phase, which Finding 3 shows is false for a post-create close failure) |
| T-77 | **refusal-record identity provenance (FU6, §16.3.8.2).** A primary run-record payload rejected for schema/invariant reasons carries attacker-shaped extra fields (a forged `stage_execution_id`, a forged `arm_id`, an oversized string) that the writer never even reads for the refusal artifact's own identity fields — the written refusal record's `stage_id`/`stage_execution_id`/`run_ordinal`/`arm_id`/`record_filename` are proven, by direct comparison, to equal the writer's own `authority`/schedule-derived values in every case, never any value traceable to the rejected payload |
| T-78 | **row-15 admission mechanics (FU6, §16.3.8.2, §19.1 item 2; `halt_triggered_by_this_run` confirmed in-memory-only, FU8 Finding 2).** A record self-validation failure (§18 row 15) whose refusal fallback **succeeds** (`EVIDENCE_REFUSED`) still yields an **in-memory** `halt_triggered_by_this_run == true` at L30 (this bool is never written into the run record's own durable payload — §22.2/§22.3), and the admission-token rule refuses to issue a token for ordinal *k*+1 — proving the admission refusal is driven by the bool, not merely inferred from the emission status, which alone would be indistinguishable from row 11's non-halting case. A companion assertion confirms the emitted run/refusal record for this ordinal carries **no** `halt_triggered_by_this_run`/`halt_reason_code` key at all (T-94 covers this schema-level absence directly; this row's own focus stays on the admission-time behavior) |
| T-79 | **row-11 vs. row-15 discrimination (FU6; field location corrected, FU8).** Two runs, both ending with emission status `EVIDENCE_REFUSED` — one from an ordinary scrub-needle hit (row 11) and one from a record self-validation/invariant failure (row 15) — are proven to differ only in the **in-memory** `halt_triggered_by_this_run` (`false` vs. `true`) computed at L30 and in the admission consequence that follows from it; the two runs' own **durable** run/refusal records are, by design, indistinguishable on this point (neither carries the bool at all, FU8), so the only place the distinction is durably observable is the stage-closure record's presence/absence of a `halt_reason_code == RUN_RECORD_SELF_VALIDATION_FAILED` entry for that ordinal — this test asserts that too, not merely the in-memory bool |
| T-80 | **run-artifact verifier, genuine run record (dispatch positive control, FU6, §22.5.2 Step 3).** A genuine, on-disk `pi-harness-cfg1-run.v1` artifact is read by `verify_cfg1_run_artifact_binding`, the discriminator pair dispatches to `_require_valid_cfg1_run_payload`, and the call returns `True` — restates T-37/T-68 explicitly as the dispatch mechanism's own positive control for the run-literal branch |
| T-81 | **run-artifact verifier, genuine refusal record (Finding 2, FU6, §22.5.2 Step 3).** A genuine, on-disk `pi-harness-cfg1-refusal.v1` artifact, written by `emit_cfg1_refusal_record` at a run path following a bounded primary-record failure, is read by `verify_cfg1_run_artifact_binding`; the discriminator pair dispatches to `_require_valid_cfg1_refusal_payload`; the call returns `True` — proving the verifier accepts the **other** legitimate run-path occupant, which FU4/FU5's undispatched "run the payload validator" composition could not have accepted |
| T-82 | **unknown/mixed/contradictory discriminator at a run path (Finding 2, FU6, §22.5.2 Step 3).** Four sub-cases at a run path — a `record_version`/`record_kind` pair matching neither known combination; one of the pair present and the other absent; both present but mismatched (the refusal `record_version` paired with the run `record_kind`, and the reverse); and a `record_version`/`record_kind` naming the stage-closure kind — each return `False` from `verify_cfg1_run_artifact_binding`, and a spy proves **neither** `_require_valid_cfg1_run_payload` **nor** `_require_valid_cfg1_refusal_payload` is invoked in any sub-case (no validator is called on ambiguous input, per Step 3's dispatch table) |
| **T-83** | **pre-create primary failure, exactly one fallback, zero final-path writes before it (Finding 1, FU7, §16.3.8.2).** A synthetic `PRE_CREATE` failure (schema validation, at step 6) for the primary run record is proven, by a filesystem-operation spy (mirroring T-22's discipline), to reach **zero** calls to the final-path exclusive-create before `emit_cfg1_refusal_record` is invoked exactly once; the refusal record's own emission then proceeds normally and either succeeds (`EVIDENCE_REFUSED`) or is separately exercised failing (T-86) |
| T-84 | **post-create primary write failure, zero fallback attempts (Finding 1, FU7).** A synthetic failure injected **after** a successful exclusive-create — first at the write call, then separately at flush, then separately at close (three sub-cases) — is proven, by a spy on `emit_cfg1_refusal_record`'s entry point, to result in **zero** calls to it in every sub-case; the outcome is `EMISSION_FAILED` directly, never `EVIDENCE_REFUSED`, distinguishing this from T-83's pre-create case at the one point that matters |
| T-85 | **post-create residue is never touched (Finding 1, FU7).** Following each of T-84's three sub-cases, a spy wrapping `unlink`/`rename`/`truncate`/any subsequent `open` call with a truncating mode against the same final path proves **zero** such calls occur for the remainder of that run's processing (including during stage-closure emission for the same stage) — the residue, whatever it contains, is left exactly as the failed write left it |
| T-86 | **refusal-writer post-create failure is `EMISSION_FAILED` and non-recursive (Finding 1, FU7, extends T-73).** A synthetic failure injected into the refusal writer's own write/flush/close (post-`FINAL_PATH_CREATED`) is proven, by the same spy discipline as T-73, to trigger **zero** further `emit_cfg1_refusal_record` calls (recursion still forbidden regardless of phase) and to yield `EMISSION_FAILED` for that ordinal; a companion sub-case repeats T-73's pre-create failures and confirms both phase classes converge on the identical non-recursion guarantee, differing only in whether residue exists afterward (T-85 covers the post-create sub-case's residue) |
| T-87 | **mandatory close-after-full-write regression — stage-closure post-create failure has a failed LIVE outcome regardless of residue readability (Finding 1, FU7, extends T-76; rewritten to the exact Finding-3 required shape, FU8).** The full, valid stage-closure `artifact_bytes` are written to the final path in full (create succeeds, every byte is transferred — `BYTES_FULLY_WRITTEN` is reached), and **then** a synthetic failure is injected at `close()` only. The test asserts, as independent assertions: (1) the **live** stage-closure emission result, as observed and acted on by the stage runner at the moment of the failure, is `FAILED` — `EMISSION_CONFIRMED` was never reached; (2) `emit_cfg1_refusal_record` is called **zero** times (T-74's non-recursion guarantee, extended to this exact close-after-full-write sub-case); (3) no replacement path is used and no second stage-closure attempt is made; (4) the stage-output authority is retired immediately (§16.3.9); (5) the residue — which in this specific sub-case is a complete, byte-for-byte valid artifact, since only `close()` failed — is left **untouched** (T-85's discipline, applied to the stage-closure path: zero unlink/rename/truncate/overwrite calls). **This row makes no claim about whether the residue is later readable — it explicitly is, in this sub-case — only that the live emission result was `FAILED` regardless.** See T-99 for the companion claim that a post-hoc `True` on this exact residue never retroactively changes result (1) |
| T-88 | **successful stage rejects `EMISSION_COLLISION`/`EMISSION_FAILED` (Finding 2, FU7, §22.4.2).** A candidate stage-closure payload with `halted_after_ordinal == null`, `halt_reason_code == null`, and every ordinal `RECORD_EMITTED`/`EVIDENCE_REFUSED` **except one** ordinal set to `EMISSION_COLLISION` (a second sub-case: `EMISSION_FAILED`) is refused by `_require_valid_cfg1_stage_closure_payload` — proving the schema itself, not merely the admission rule elsewhere, makes this shape unconstructible |
| T-89 | **halted stage accepts the correct failure status only with coherent metadata (Finding 2, FU7, §22.4.2; code renamed, FU8 Finding 1).** Four sub-cases against a stage that legitimately halted at ordinal *k*: (a) `ordinal_status[k] == EMISSION_COLLISION` with `halted_after_ordinal == k` and `halt_reason_code == RUN_RECORD_EMISSION_COLLISION` — accepted; (b) the same status with `halted_after_ordinal` set to a **different** ordinal — refused; (c) the same status with `halted_after_ordinal == k` but `halt_reason_code` set to a **different** member of §19.4's set (e.g. `RUN_RECORD_EMISSION_FAILED`) — refused; (d) `ordinal_status[k] == EMISSION_FAILED` with `halted_after_ordinal == k` and `halt_reason_code == RUN_RECORD_EMISSION_FAILED` (renamed from FU7's `RUN_RECORD_REFUSAL_FALLBACK_FAILED`) — accepted, mirroring (a) for the other status. A fifth sub-case (e) repeats (d) against each of the three underlying causes §19.4 now folds into `RUN_RECORD_EMISSION_FAILED` (a direct post-create primary failure, a `PRE_CREATE` fallback that itself later fails, and a refusal-writer's own post-create failure) — all three are accepted identically under the single renamed code, proving the schema does not (and must not) attempt to distinguish them |
| T-90 | **exact `HALT_REASON_CODES` set, stage-closure-only (Finding 3, FU7; scope corrected, FU8 Finding 2).** A source-level/enum-introspection regression proves the accepted domain for the stage-closure record's `halt_reason_code` field is **exactly** the six members of §19.4 — no more, no fewer, including the renamed `RUN_RECORD_EMISSION_FAILED` — and that both the stage-closure validator and the in-memory L30 admission-decision logic (§19.1 item 2) reference the **same** underlying enum object (by identity, mirroring T-42's discipline for `_schedule_arm_for`), not two independently-maintained lists that merely happen to agree today. A companion assertion (extending T-94) proves the **run-record** validator accepts no `halt_reason_code` key at all — there is no run-record-side domain to audit, because the field does not exist there (FU8 Finding 2) |
| T-91 | **off-schedule arm and wrong filename fail at step 6, not step 7 (Finding 4, FU7).** Three sub-cases, each a payload internally inconsistent under its **own** claimed `(stage_id, run_ordinal)`: (a) a run-record payload claiming `arm_id` that disagrees with `_schedule_arm_for(stage_id, run_ordinal)` for its own claimed ordinal (the corrected T-40 case); (b) a run/refusal-record payload whose `record_filename` disagrees with the internal derivation from its own `(stage_id, run_ordinal, arm_id)`; (c) a stage-closure payload whose `record_filename` disagrees with the internal derivation from its own `stage_id`. Each is refused by its dispatched payload validator (step 6) — proven directly by calling the validator alone, with **no** authority or writer involved — and, separately, calling the full writer with the same payload is proven to reach the step-6 refusal without any step-7 authority-binding code path executing (spy-proven zero authority-binding-specific comparisons attempted) |
| T-92 | **every step-7 test candidate first demonstrably passes its own validator (Finding 4, FU7, meta-test formalizing T-58–T-60's construction discipline).** For each of T-58's Cases A/B/C, T-59's Cases A/B/C, and T-60's two cases, the test harness calls the candidate's dispatched payload validator **directly** (independent of any writer or authority) and asserts it **accepts** the candidate **before** the same candidate is ever passed to the corresponding writer — making explicit, as its own regression rather than an implicit precondition buried in each test's prose, that every step-7 regression in this design proves step 7 is load-bearing only against inputs step 6 could not have already rejected |
| **T-93** | **exact `S2` schedule mapping (Finding 5, FU7, §7.3a).** `_schedule_arm_for("S2", ordinal)` for `ordinal` in `1..6` returns, in order, exactly `Q, H, H, Q, Q, H`; `(block, position)` for each ordinal equals `((ordinal-1)//2)+1, ((ordinal-1)%2)+1`; and the same identity-of-callable proof T-42 establishes for `S1`'s five call sites (`L0`, payload construction, the writer, the record validator, the artifact-binding verifier) is repeated for `S2`, proving no site has an `S1`-only hard-coded table masquerading as the shared function |
| **T-94** | **run-record schema carries no unrecomputable final-L30 state (Finding 2, FU8, §22.2/§22.3).** Signature/key-set introspection over `_require_valid_cfg1_run_payload` proves the closed key set contains **no** `halt_triggered_by_this_run` and **no** `halt_reason_code` key at all — a payload otherwise valid but carrying either key, under any value, is refused as an unrecognized key (closed-key-set violation, not a value-domain violation). A companion assertion constructs two canonical payloads differing **only** in facts available at or before L28 (never differing in anything only knowable after L29's emission resolves) and proves `_require_valid_cfg1_run_payload` recomputes `run_classification` identically for both from the payload alone, with no dependency on any in-memory L30 state — proving the one field this schema does retain for classification purposes remains genuinely payload-only recomputable even after the two removed fields are gone |
| T-95 | **direct post-create primary failure maps to the truthful generic code, zero refusal-writer calls (Finding 1, FU8, extends T-84).** A synthetic failure injected into the primary run writer's own write/flush/close, after a successful exclusive-create (T-84's three post-create sub-cases), is proven — by a spy on `emit_cfg1_refusal_record`'s entry point, extending T-84's own zero-calls proof — to result in a stage-closure `ordinal_status` of `EMISSION_FAILED` with `halt_reason_code == RUN_RECORD_EMISSION_FAILED` (§19.4), **never** the retired `RUN_RECORD_REFUSAL_FALLBACK_FAILED` literal, and never any code that could be read as claiming a fallback occurred |
| T-96 | **`PRE_CREATE` fallback-then-failure maps to the same truthful generic code (Finding 1, FU8, extends T-75/T-86).** A `PRE_CREATE` primary-writer failure whose one permitted refusal fallback is attempted and then itself fails — at any of the refusal writer's own `PRE_CREATE` or post-create sub-phases (T-73's and T-86's sub-cases) — is proven to result in the **identical** stage-closure `halt_reason_code == RUN_RECORD_EMISSION_FAILED` as T-95's direct-failure case, from a structurally different cause; the two cases are proven indistinguishable in this closed field by construction, satisfying §19.4's own "never distinguishes among them" claim as a regression rather than only as prose |
| T-97 | **`PRE_CREATE` stage-closure failure leaves no file (Finding 3, FU8, isolates T-76's claim as its own positive proof).** Repeats T-76's `PRE_CREATE` sub-cases with an explicit filesystem-operation spy (mirroring T-22/T-85) asserting **zero** calls of any kind — create, write, or otherwise — against the stage-closure path, for every `PRE_CREATE` failure cause, independent of T-76's own narrative assertion |
| T-98 | **post-create close failure has a failed live emission result despite valid residue (Finding 3, FU8 — this is the "mandatory close-after-full-write regression" Finding 3 requires; T-87 is this test, rewritten to the exact required shape).** See T-87 |
| T-99 | **post-hoc `True` on valid residue never mutates or reclassifies the live, already-sealed outcome (Finding 3, FU8, companion to T-87/T-98).** Following T-87/T-98's exact scenario (a stage-closure `close()` failure after a full, valid write), a **fresh** call to `verify_cfg1_stage_closure_binding(actual_path)` against the untouched residue is proven to return `True` (the bytes are, in this sub-case, a genuine, correctly-bound artifact — §22.5.2's existing byte-authoritative behavior, unchanged). The test then asserts that this `True` result: (a) is never consulted by any later stage or run for any purpose (§20's existing "nothing in `results/` authorizes anything" extended to reads, not only writes); (b) never causes the already-recorded live emission outcome (`FAILED`, from T-87/T-98) to be revised, retried, or reported differently after the fact; and (c) the identical property is proven for the **run-record** case too — a post-create primary-writer close failure (T-95's scenario) whose residue happens to be structurally valid under `verify_cfg1_run_artifact_binding` likewise never reclassifies that ordinal's already-sealed `EMISSION_FAILED` stage-closure status to `RECORD_EMITTED` |
| T-100 | **L0 output-namespace-preoccupied hard stop (Finding 5, FU8, §16.3.10).** With a genuine, ACTIVE stage-output authority already minted, a file or directory is placed at exactly the path `L0`'s own internal derivation would compute for the next ordinal's run record, **before** `L0` admits that ordinal. `L0`'s admission check is proven to detect the occupied path and, in a single sequence proven by spy: (1) create **zero** run-scoped resources (no workspace mint, no broker, no runtime launch — spy-proven, mirroring T-22); (2) retire the stage-output authority immediately (§16.3.9-identical timing to §16.3.7's hard stop); (3) report exactly one closed console-only code, `OUTPUT_NAMESPACE_PREOCCUPIED` (§16.3.10), and nothing else; (4) write **zero** run, refusal, or stage-closure artifacts of any kind (spy-proven zero exclusive-create calls at any of the three record paths); (5) leave the pre-existing occupying file/directory itself completely untouched. A companion sub-case repeats this for a directory (not a file) occupying the path, proving the same outcome regardless of what kind of filesystem object is doing the occupying |
| T-101 | **L29/L30 ordering — final admission occurs only after the emission result is known (Finding 4, FU8).** A direct test of the admission-decision function (§19.1, L30) proves, by construction of its own call signature/dependency graph, that it is never invoked, and an admission token is never issued, before the corresponding run's L29 emission attempt has fully resolved to one of `RECORD_EMITTED`/`EVIDENCE_REFUSED`/`EMISSION_COLLISION`/`EMISSION_FAILED` — i.e. §19.1 item 3's emission-status check cannot read a value that does not exist yet. This is proven directly (an attempt to call the admission logic with a not-yet-resolved/placeholder emission status raises, rather than silently treating it as any of the four closed values), not merely inferred from L28/L29/L30's documented ordering in §16.2 |
| **T-102** | **genuine sealed stage decision is accepted, and the decision type-gate rejects everything else with zero reads (Finding 1, FU9, §16.3.8.3 steps 1–2; sealing mechanism updated, FU10 — see T-127/T-128 for the sealing step itself exercised through a genuine stage run).** A genuine `CFG1StageClosureDecision`, produced by driving a genuine stage run to its own L30 sealing step (§16.3.8.3, no longer a directly-callable function — see T-127/T-128) under a genuine ACTIVE authority, is accepted by `emit_cfg1_stage_closure` and produces a valid, written stage-closure record — the positive control. Separately, `type(decision) is CFG1StageClosureDecision` is proven exact (not `isinstance`, no duck-typing): a hand-built object with an identical-looking `__class__.__name__`, a plain dict shaped like the decision's fields, and `None` are each refused immediately, with **zero** field reads (spy-proven, mirroring T-55) |
| T-103 | **direct/forged stage decision is refused before any closure-file I/O (Finding 1, FU9, §16.3.8.3 step 3; wording updated, FU10).** A direct `CFG1StageClosureDecision(...)` construction with every field set to plausible values but an unregistered `decision_nonce` fails `__post_init__` with `UNKNOWN_DECISION_NONCE`, mirroring T-25's proof for `CFG1StageOutputAuthority`; separately, a forged/guessed `decision_nonce` (never registered by the stage runner's own sealing step, and — per T-124 — never obtainable from any reachable callable in the first place) fails identically. Both sub-cases are spy-proven, mirroring T-22, to reach **zero** filesystem calls of any kind — no exclusive-create, no read, nothing — before the refusal |
| T-104 | **genuine decision with one field mutated is refused (Finding 1, FU9, §16.3.8.3 step 3).** A genuinely-sealed decision with one bound field (in turn: `ordinal_status`, `halted_after_ordinal`, `halt_reason_code`, `stage_id`, `stage_execution_id`) mutated via `object.__setattr__` (bypassing `frozen=True`) fails the writer's own re-verification against `_STAGE_DECISION_SEALED` with `DECISION_FIELD_MISMATCH` at the next consumption — proving a nonce learned from the genuine object, reused alongside a substituted field, gains no authority beyond the exact sealed state, mirroring T-27's proof for the stage-output authority |
| T-105 | **genuine decision rebound to a different authority is refused (Finding 1, FU9, §16.3.8.3 step 4).** A genuine, unmutated `CFG1StageClosureDecision`, sealed under authority `A` (a genuine, ACTIVE `S1-X1` authority), is presented to `emit_cfg1_stage_closure` alongside a **different**, separately genuine and ACTIVE authority `B` (a distinct `S1-X2` stage execution) — refused with `DECISION_AUTHORITY_MISMATCH` before any write, even though both the decision and the authority are individually genuine |
| T-106 | **revised, FU10 (originally tested a directly-callable `seal_cfg1_stage_decision`, which no longer exists as a supported name — Finding 1, FU9→FU10, §16.3.8.3 requirement 7; mirrors T-101's ordering discipline).** A source-level/call-graph proof over the stage runner's own local sealing step (the only code that writes `_STAGE_DECISION_SEALED`) shows it is never reached, for any ordinal, before that ordinal's L29 emission result has been appended to the stage-progress ledger (§16.3.8.4) — proven by construction of the routine's own statement ordering (mirroring T-101's technique, applied here to a lexically-scoped step rather than a call to a separately-nameable function, since FU10 removed the latter) |
| T-107 | **revised, FU10, cardinality corrected FU11, mechanism split FU12 (Finding 1, FU9→FU10→FU11→FU12, §16.3.8.3 requirement 6).** Proves, as four separate assertions, exactly what requirement 6 now freezes: (1) **L30 runs once per admitted ordinal, not once per stage** — a multi-ordinal `S1` run (mirroring T-131's construction below) is proven, by a spy on the L30 entry point, to reach L30 **more than once** across the stage (once per admitted ordinal); (2) **non-terminal L30 evaluations never seal** — for every one of those evaluations that selects §19.6 branch B, the same spy proves the local sealing step is **not** invoked and neither `_STAGE_DECISION_SEALED` nor `_STAGE_TERMINAL_SEAL_HISTORY` gains an entry (this sub-case restates T-126 as a within-this-test control, not a duplicate test); (3) **T-107A — second seal attempt before any consumption is refused.** A genuine decision `D1` is sealed for authority `A`. Before any writer consumes `D1`, a synthetic stage-runner construction (test-only harness scaffolding, never a supported code path, and never claimed to be reachable by any supported caller) forces the sealing step to be reached a second time for `A`; the second attempt is refused at requirement-6 step 2, before any second decision registration, exactly as T-25–T-27's registry-based refusals already establish for the analogous authority case; (4) **T-107B — second seal attempt after the first decision's own consumability revocation is refused identically (the regression FU11 lacked, closed by FU12).** `D1` is sealed for `A`, then `emit_cfg1_stage_closure(A, D1)` is driven through step 4a, so `D1`'s own `_STAGE_DECISION_SEALED` entry has already been revoked. Before the stage runner leaves the sealing-capable lifetime, the same synthetic construction forces a second terminal-seal reach for `A`; this attempt **still** refuses at requirement-6 step 2 and no second decision is ever registered — proving refusal depends on the independent `_STAGE_TERMINAL_SEAL_HISTORY` fact from requirement 6 step 3, which step 4a's revocation never touched, and **not** on `_STAGE_DECISION_SEALED`, which by this point holds no trace of `D1` at all. Sub-cases (3)/(4) are the actual mechanical backstop requirement 6 relies on — (4) specifically is what distinguishes the corrected FU12 mechanism from FU11's, which this exact scenario would have defeated; sub-cases (1)–(2) are what makes clear the backstop is doing real work, since ordinary control flow alone reaches L30 repeatedly without ever needing it |
| T-108 | **stage-closure writer has no caller-selectable stage-decision payload surface (Finding 1, FU9, §16.3.8.3 requirement 8; mirrors T-38).** Signature-inspection audit over `emit_cfg1_stage_closure` proves it declares no parameter named or typed as `ordinal_status`, `halted_after_ordinal`, `halt_reason_code`, `record_filename`, `stage_id`, or `stage_execution_id` — its **only** parameters are `authority` and `decision`. Calling it with any additional/positional argument shaped like one of these fields raises `TypeError` from Python's own argument binding, proven directly, mirroring T-39 |
| T-109 | **writer-produced closure bytes exactly reflect the genuine sealed decision (Finding 1, FU9, §16.3.8.3 step 5).** For a genuine, ACTIVE authority and a genuine decision sealed under it, the exact bytes `emit_cfg1_stage_closure` writes are proven, by direct comparison, to encode `canonical["ordinal_status"] == decision.ordinal_status`, `canonical["halted_after_ordinal"] == decision.halted_after_ordinal`, and `canonical["halt_reason_code"] == decision.halt_reason_code` — field-for-field, with no transformation, substitution, or default-value fallback anywhere in the write path |
| T-110 | **revised, FU10 (extended to close the FU9→FU10 gap directly — Finding 1, FU9 and FU10, the original threat both subsections close, proven as one integrated regression rather than only at the mechanism level of T-102–T-105/T-124).** Holding one genuine, ACTIVE authority and one genuine decision sealed under it (describing, say, a successful stage), an attempt is made to have `emit_cfg1_stage_closure` instead emit a **different**, fully self-consistent, schema-valid closure record (a different `ordinal_status`, a different `halted_after_ordinal`/`halt_reason_code` pair, itself passing every §22.4.2 cross-field check in isolation) — by constructing a second, independently self-consistent `CFG1StageClosureDecision`-shaped object through every available avenue: direct construction, a mutated copy of the genuine object, a hand-rolled object exposing the same attribute names, **and, new in FU10, every enumerable module-level/importable callable reachable while holding only the genuine authority** (T-124's own enumeration). Every avenue is refused — the first three by one of T-102–T-105's mechanisms, the last because no such reachable callable exists at all (T-124) — and **no avenue reaches step 5 (payload construction) with alternate facts** |
| **T-111** | **exact halt-reason precedence is frozen and tested for overlapping failures (Finding 2, FU9, §19.5).** For each pair of the six precedence-ordered conditions that can be constructed to co-occur, `_resolve_halt_reason_code` is called with both facts set to their failing values simultaneously, and the result is proven to equal the **higher-precedence** condition's code in every pairing — a full pairwise sweep, not only the two named examples in T-112/T-113 |
| T-112 | **row-15 self-validation defect + refusal-fallback-also-fails selects `RUN_RECORD_EMISSION_FAILED` under the frozen precedence (Finding 2, FU9).** Facts set to `emission_status == EMISSION_FAILED` **and** `halt_triggered_by_this_run == true` simultaneously (the exact row-15-then-row-16 overlap): `_resolve_halt_reason_code` returns `RUN_RECORD_EMISSION_FAILED` (precedence step 2), never `RUN_RECORD_SELF_VALIDATION_FAILED` (step 3) — proving the emission-outcome check's durable precedence over the underlying self-validation defect is what the implementation actually does, not only what this design states |
| T-113 | **lifecycle failure + registry-not-empty selects `LIFECYCLE_CLOSURE_UNPROVEN` under the frozen precedence (Finding 2, FU9).** Facts set to `lifecycle_all_closed == false` **and** registries-not-empty simultaneously: `_resolve_halt_reason_code` returns `LIFECYCLE_CLOSURE_UNPROVEN` (precedence step 4), never `RUN_SCOPED_REGISTRY_NOT_EMPTY` (step 6) |
| T-114 | **one shared precedence function, never reimplemented (Finding 2, FU9, mirrors T-42/T-93's identity-of-callable discipline).** L30's own decision-sealing call site and any other code path that could plausibly need a halt-reason value are proven, by identity of the underlying callable object, to invoke the **same** `_resolve_halt_reason_code` function — and, separately, the stage-closure validator and writer are proven to contain **no** independent reimplementation of steps 3–6 of the precedence (T-115 proves the validator's actual scope directly) |
| **T-115** | **validator enforces closed-set membership only, never derivation, for the four non-mechanical halt codes (Finding 5, FU9, §22.4.2).** For each of `PRE_DISPATCH_REFUSAL`, `LIFECYCLE_CLOSURE_UNPROVEN`, `RUN_SCOPED_REGISTRY_NOT_EMPTY`, and `RUN_RECORD_SELF_VALIDATION_FAILED`, a schema-valid stage-closure payload carrying that code alongside an `ordinal_status`/`halted_after_ordinal` shape that is **not** independently indicative of that specific cause (i.e. no `EMISSION_COLLISION`/`EMISSION_FAILED` entry at `halted_after_ordinal`) is accepted by `_require_valid_cfg1_stage_closure_payload` — proving the validator does not, and cannot, refuse a payload merely because `ordinal_status` "doesn't look like" that code's usual cause, since it has no mechanism to check that relationship at all for these four codes |
| **T-116** | **primary run writer create collision → `EMISSION_COLLISION` (Finding 3, FU9, §18 row 12).** A synthetic unambiguous already-exists result from the primary writer's own exclusive-create call produces exactly: stage halt, zero fallback attempted, the occupant left untouched (spy-proven zero unlink/overwrite calls), and `ordinal_status`/console both recording `EMISSION_COLLISION`/`RUN_RECORD_EMISSION_COLLISION` |
| T-117 | **primary run writer non-collision/ambiguous create error → `EMISSION_FAILED` (Finding 3, FU9, §18 row 18, extends T-84/T-95 to the create call itself rather than only write/flush/close).** A synthetic non-collision `OSError` (and, separately, a platform-ambiguous create result) raised by the primary writer's own exclusive-create call — never the specific already-exists signal — produces `EMISSION_FAILED`/`RUN_RECORD_EMISSION_FAILED`, zero fallback attempts (spy-proven), and never an inference that the path is absent |
| T-118 | **refusal writer create collision → `EMISSION_COLLISION` (Finding 3, FU9, §18 row 19 — collision is not a primary-writer-only concept).** A synthetic unambiguous already-exists result from the refusal writer's **own** exclusive-create call (reached only after a `PRE_CREATE` primary failure made the fallback eligible) produces exactly the same outcome as T-116: stage halt, zero further fallback, occupant untouched, `EMISSION_COLLISION`/`RUN_RECORD_EMISSION_COLLISION` — proving the classification is identical regardless of which writer's own create call is the one that collided |
| T-119 | **refusal writer non-collision/ambiguous create error → `EMISSION_FAILED` (Finding 3, FU9, §18 row 16, extends T-86 to the create call itself).** A synthetic non-collision/ambiguous create-attempt failure on the refusal writer's own exclusive-create call produces `EMISSION_FAILED`/`RUN_RECORD_EMISSION_FAILED`; any residue is left untouched and never authoritative (T-85's discipline applied to this exact sub-case) |
| T-120 | **none of T-116/T-117/T-118/T-119's create-attempt failures triggers another fallback (Finding 3, FU9, consolidates the non-recursion proof across all four).** A single spy on `emit_cfg1_refusal_record`'s entry point, run across all four sub-cases of T-116–T-119, proves **zero** additional writer invocations of any kind in every case — the same non-recursion guarantee T-73/T-74 already establish for other failure classes, now proven explicitly for create-attempt failures specifically |
| T-121 | **stage-closure create collision → failed live closure emission + retirement (Finding 3, FU9, §16.3.8.2/§18 row 17).** A synthetic unambiguous already-exists result from the stage-closure writer's own exclusive-create call is proven to produce: live emission result `FAILED` (`EMISSION_CONFIRMED` never reached), console-only bounded reporting (optionally a distinct closed code from the non-collision sub-case), zero fallback of any kind, immediate stage-output-authority retirement, and the pre-existing occupant left completely untouched |
| T-122 | **stage-closure non-collision/ambiguous create error → failed live closure emission + retirement (Finding 3, FU9, §16.3.8.2/§18 row 17).** A synthetic non-collision `OSError` from the stage-closure writer's own exclusive-create call produces the identical outcome shape as T-121 (live `FAILED`, console-only, zero fallback, immediate retirement, any residue untouched) — proving the stage-closure writer's response does not vary by create-failure cause, unlike the two run-scoped writers, which at least distinguish collision from non-collision in their own durable classification |
| **T-123** | **normative-text audit — §22.4.2 makes no run-record-sharing claim for `halt_reason_code`, and its own no-closure enumeration agrees literally with §19.4's (Finding 4, FU9; extended to four cases, FU13).** A source-of-truth check (implementation-phase discretion: a doc-lint step, or a shared constant both sections cite) proves §22.4.2's prose contains no claim that `halt_reason_code` is shared with, or accepted by, the run-record schema, and that the stage-ending cases it lists as writing no confirmed stage-closure record are the same set §19.4 lists, in substance if not verbatim wording. **This set is exactly four (FU13): the stage-output-authority hard stop, the stage-closure writer's own failed emission, `OUTPUT_NAMESPACE_PREOCCUPIED`, and `STAGE_DECISION_MINT_FAILED`** — the audit fails if either section's enumeration diverges from this set in count or membership, and separately fails if `STAGE_DECISION_MINT_FAILED` appears anywhere in the closed `HALT_REASON_CODES` set (§19.4) or in any of the three durable-record schemas (§22.1, §22.4.1, §22.4.2) |
| **T-124** | **the required adversarial proof — no supported callable API yields a genuine decision with invented facts (Finding 1, FU10, §16.3.8.3 requirement 9).** Given one genuine, ACTIVE `CFG1StageOutputAuthority` and nothing else, an exhaustive sweep of every module-level name the CFG1 package exports (`inspect.getmembers` over the package/module, mirroring T-38's audit discipline) is proven to contain **no** callable whose signature accepts `ordinal_status`, `halted_after_ordinal`, or `halt_reason_code` as an independent parameter, and **no** callable that, given only `authority`, returns an object satisfying `type(x) is CFG1StageClosureDecision`. Separately, the same sweep is repeated against every attribute reachable from the `authority` object itself (`vars(authority)`, its class's `__dict__`, its module) with the identical negative result. The attempt to obtain a genuine, alternate-fact `CFG1StageClosureDecision` therefore fails **before any decision mint is registered** — there is no candidate call to even attempt, which is the required proof in its strongest form |
| T-125 | **revised, FU11 — scoped to the supported-API issuance boundary and runner-local ledger provenance, not private-registry memory inaccessibility (Finding 1, FU10; scope corrected, FU11).** An invented, hand-assembled, fully self-consistent `ordinal_status`/`halted_after_ordinal`/`halt_reason_code` tuple describing a stage outcome that never happened is proven unable to become the content of a genuine sealed decision, through three assertions: (1) **the invented tuple cannot reach the genuine lexical issuer** — every avenue T-124 already enumerates as absent (no module-level, importable, or otherwise supported-callable path to the sealing step) is re-confirmed here as the reason the tuple has nowhere to be submitted to; (2) **the runner-local stage-progress ledger cannot be supplied, replaced, returned, or obtained through any supported API** — a sweep of every module-level name and every attribute reachable from a genuine `authority` object (mirroring T-124's own enumeration technique) proves none accepts a ledger argument, returns the runner's own ledger, or exposes a settable reference to it; (3) **the real terminal decision, when the stage runner does seal one, is proven by direct comparison to reflect only the runner-recorded L29 ledger entries** — never the invented tuple, even when both are held in the same test process at the same time. **This test does not attempt, and is not required to prove, that `_STAGE_DECISION_SEALED` itself resists direct mutation, monkeypatching, closure-cell tampering, or other same-process memory manipulation (Finding 2, FU11)** — `_STAGE_DECISION_SEALED` is an internal authenticity/revocation registry, not an issuance API, and defending against arbitrary same-user process-memory tampering is outside this design's threat model (§16.3.4's own scope note) unless a future FU separately widens it |
| T-126 | **non-final successful ordinal admits without sealing anything (§19.6 branch B).** For `k < LAST_ORDINAL(stage_id)` with §19.1 items 1–4 all satisfied, the admission token for `k+1` is issued, and a spy on the stage runner's own sealing step (proven reachable only through source-level instrumentation for test purposes) proves it is **not** invoked — no decision is sealed, `_STAGE_DECISION_SEALED` gains no entry, and `emit_cfg1_stage_closure` is not called |
| T-127 | **`S1` ordinal 9 successful: terminal SUCCESS, no ordinal-10 token (§19.6 branch C, `LAST_ORDINAL("S1") == 9`).** With `S1`'s full nine-ordinal schedule (§7.3) run to a genuinely successful ordinal 9 (items 1–4 all satisfied), the test proves, in one sequence: (1) no admission token for ordinal 10 is ever issued (spy-proven, mirroring T-22's zero-calls discipline, applied to token issuance); (2) exactly one `CFG1StageClosureDecision` is sealed, with `ordinal_status` containing keys `"1"`..`"9"` only, `halted_after_ordinal = null`, `halt_reason_code = null`; (3) `emit_cfg1_stage_closure` is called exactly once with that decision and produces a valid, `_require_valid_cfg1_stage_closure_payload`-accepted, on-disk record; (4) the stage-output authority is retired **after** that emission is confirmed, never before (§16.3.9) |
| T-128 | **`S2` ordinal 6 successful: identical terminal behavior (§19.6 branch C, `LAST_ORDINAL("S2") == 6`).** Repeats T-127's five assertions against `S2`'s six-ordinal schedule (§7.3a) run to a genuinely successful ordinal 6 — proving branch C's behavior is not `S1`-specific, and that `LAST_ORDINAL` is genuinely derived per-stage (T-129 separately proves the derivation mechanism itself) |
| T-129 | **`LAST_ORDINAL` is derived from the one shared schedule source, never a duplicated literal (§19.6).** Mirroring T-42/T-93/T-114's identity-of-callable discipline: `LAST_ORDINAL("S1")` and `LAST_ORDINAL("S2")` are proven, by direct inspection, to be computed from the **same** underlying `SCHEDULE` mapping `_schedule_arm_for` itself consults — not two independently-maintained integer constants that merely happen to equal `9` and `6` today. A companion assertion constructs a synthetic, differently-sized test schedule (test-only scaffolding, never a change to the frozen `S1`/`S2` tables) and proves `LAST_ORDINAL` tracks it, showing the derivation is genuinely computed rather than hard-coded per stage name |
| T-130 | **a halted ordinal still uses the unchanged §19.5 precedence and produces a HALTED decision (§19.6 branch A, regression continuity).** A run failing one or more of §19.1 items 1–4 before the stage's final ordinal is reached is proven to: issue no admission token for the next ordinal (as before FU10); resolve `halt_reason_code` via the unmodified `_resolve_halt_reason_code` (§19.5, T-111–T-114 unaffected); seal a decision with `halted_after_ordinal = k` (non-null) and the resolved code; and have that decision's `ordinal_status` sourced from the stage-progress ledger (§16.3.8.4) exactly as T-127/T-128 prove for the SUCCESS case, with every ordinal after `k` filled `NOT_EXECUTED` — proving the ledger-sourcing mechanism is common to both terminal branches, not special-cased for success alone |
| T-131 | **the successful decision's exact field shape (§19.6 branch C, restates §22.4.2's schema binding as a decision-object property).** For the genuine SUCCESS decision T-127/T-128 each produce, direct field inspection proves `halted_after_ordinal is None`, `halt_reason_code is None`, and `ordinal_status` contains, for every declared ordinal, one of `RECORD_EMITTED`/`EVIDENCE_REFUSED` — never `EMISSION_COLLISION`, `EMISSION_FAILED`, or `NOT_EXECUTED` — proving the decision object itself carries this invariant, not merely the JSON payload the validator later checks |
| T-132 | **a sealed decision cannot be consumed by a second stage-closure emission attempt (§16.3.8.3 "Decision lifetime," step 4a).** After a genuine decision (from either T-127's SUCCESS case or T-130's HALTED case) has been consumed by one successful `emit_cfg1_stage_closure` call, a second call presented with the **same**, still-genuine, unmutated `decision` object is refused at step 3 with `UNKNOWN_DECISION_NONCE` — identical to T-103's never-sealed case — proving the registry entry was actually revoked at consumption, not merely documented as "no longer useful." A companion sub-case repeats this after the **first** `emit_cfg1_stage_closure` attempt itself failed (mirroring T-121/T-122's stage-closure create-failure scenarios), proving revocation is unconditional on the ensuing write's outcome |
| **T-133** | **seal-history survives decision-consumability revocation (new, FU12, §16.3.8.3 requirement 6).** Direct positive proof, independent of T-107B's end-to-end framing: immediately after `emit_cfg1_stage_closure`'s step 4a revokes `D1`'s `_STAGE_DECISION_SEALED` entry, a direct inspection proves `_STAGE_TERMINAL_SEAL_HISTORY`'s entry for `D1`'s authority is **still present** — step 4a's revocation is proven, by inspecting both registries at once, to affect only the former |
| T-134 | **seal-history survives stage-closure writer failure (new, FU12, §16.3.8.3 requirement 6).** Repeats T-121/T-122's stage-closure create-failure scenarios (collision and non-collision) and, in each, confirms `_STAGE_TERMINAL_SEAL_HISTORY`'s entry for that authority remains present after the failed write, after the resulting immediate stage-output-authority retirement (§16.3.9) — proving the seal-history fact's lifetime is independent of both the write's own outcome and the authority's own ACTIVE/RETIRED state |
| T-135 | **rewritten, FU13; operational-retry-versus-test-injection distinction frozen explicitly, FU14 (Finding 1; originally expected a subsequent legitimate seal to succeed after a pre-history-establishment mint failure — a retry contradiction FU13 removed; §16.3.8.3 "Partial-failure atomicity of the mint sequence").** **In all three sub-cases, the stage runner itself performs zero second mint/seal attempts of its own** — this is proven directly (a spy on the stage runner's own call sites, mirroring T-106's technique, shows no internal code path reaches the sealing step a second time for this authority after the injected failure). Separately, in sub-cases (a) and (b) only, **the test harness deliberately forces exactly one malformed, test-only second reach of the lexical sealing step while the stage-runner invocation is still alive and the seal-history entry still exists** — this forced reach is not, and does not exercise, any operational retry path, and grants no production retry capability; it exists solely to prove the independent seal-history fact, not decision consumption, is what refuses it. (a) between requirement-6 steps 3 and 4 (history fact established, decision registration itself fails): the test proves `_STAGE_TERMINAL_SEAL_HISTORY` retains the authority's entry, no `CFG1StageClosureDecision` object is ever returned, and the harness's forced second reach refuses at requirement-6 step 2 **before any second decision registration**; (b) between steps 4 and 5 (decision registered, `__post_init__` construction itself fails): identical assertions, plus a direct check that the orphaned `_STAGE_DECISION_SEALED` entry from the failed step 4 grants no usable authority to any code path, and the harness's forced second reach again refuses at step 2 before any second registration; (c) strictly between steps 2 and 3 (before the history fact is established): **the failure occurs before seal-history establishment, so this sub-case proves no second-seal refusal from a history entry that was never created** — the stage runner performs zero retry **and the test harness performs zero synthetic second seal attempt of any kind**, and the test instead proves, directly: both registries are left with **zero** entries for that authority; the stage-output authority is retired; the terminal console disposition is `STAGE_DECISION_MINT_FAILED`; and **zero** calls reach the stage-closure writer. All three sub-cases assert the stage-output authority is retired before the console report. **No sub-case expects, or is followed by, a subsequent legitimate seal attempt succeeding** — this FU13 correction is unchanged by FU14; FU14 only sharpens the introductory sentence so it no longer contradicts (a)/(b)'s own forced-reach assertions |
| T-136 | **extended, FU13 (originally proved only normal-return cleanup timing; §16.3.8.3 "Terminal-seal history lifetime").** For a genuinely completed stage execution (successful or halted), the test proves `_STAGE_TERMINAL_SEAL_HISTORY`'s entry for that authority remains present and inspectable for the entire duration of the stage runner's own routine invocation — through decision sealing, the stage-closure write, and authority retirement — and is proven absent only after that same routine invocation has itself returned (a black-box "before/after the call returns" comparison, never claimed to be observable mid-invocation by any supported means, consistent with §16.3.8.3's own unreachability requirement for this fact). **New in FU13:** the identical before/after-return cleanup timing is separately proven for the terminal-decision-mint-failure exit — for each of T-135(a)/(b)'s two sub-cases in which a history entry was established before the failure, that entry is proven present throughout the mint-failure terminal unwind (retirement, console reporting) and absent only after the stage runner's own routine invocation returns; T-135(c), which never establishes a history entry, is not a case this test applies to |
| **T-137** | **decision-mint failure before history establishment: immediate retirement, zero retry, no closure write (new, FU13, §16.3.8.3, §16.3.9, §19.2's third exception).** A synthetic mint-sequence failure injected strictly between requirement-6 steps 2 and 3 (before `_STAGE_TERMINAL_SEAL_HISTORY` gains an entry) is proven, by one integrated sequence spy: (1) to leave zero entries in both `_STAGE_TERMINAL_SEAL_HISTORY` and `_STAGE_DECISION_SEALED`; (2) to retire the stage-output authority before the failure path returns (a following `verify_stage_output_authority` call on the same, genuine, unmutated authority object refuses `UNKNOWN_MINT_NONCE`, mirroring T-44–T-49's own retirement proof technique); (3) to make **zero** calls of any kind to `emit_cfg1_stage_closure` or to any stage-closure-writer internal (spy-proven, mirroring T-97); (4) to make **zero** attempts, by the stage runner's own code, to reach the sealing step a second time for this authority |
| **T-138** | **decision-mint failure after history establishment but before decision registration: same terminal disposition, history retained exactly through the frozen T-136 lifetime, never beyond it (new, FU13; lifetime scope corrected, FU14 Finding 2).** A synthetic mint-sequence failure injected strictly between requirement-6 steps 3 and 4 is proven to produce the identical outcome shape as T-137 — zero `emit_cfg1_stage_closure` calls, zero second-seal attempts by the stage runner's own code — with `_STAGE_TERMINAL_SEAL_HISTORY`'s lifetime proven as exactly four ordered facts, no more: (1) the entry is present through immediate stage-output-authority retirement; (2) the entry is present through the bounded console report of `STAGE_DECISION_MINT_FAILED`; (3) the entry remains present for the remainder of the stage runner's own invocation (never claimed to persist for "the remainder of the test process," which would contradict T-136); (4) the entry is proven **absent** after that same invocation returns, using T-136's own before/after-return comparison technique, not a separate or wider claim. `_STAGE_DECISION_SEALED` is proven to have gained no entry at all in this sub-case |
| **T-139** | **decision-mint failure after decision registration but before object construction: explicit before-return / after-return ordering (new, FU13; temporal ordering frozen explicitly, FU14 Finding 3, §16.3.8.3's "Registry cleanup on mint failure").** A synthetic `__post_init__` failure injected strictly between requirement-6 steps 4 and 5 is proven to leave, immediately after the failure, a registered-but-orphaned `_STAGE_DECISION_SEALED` entry (the decision nonce and fields are present in the registry, but no `CFG1StageClosureDecision` object was ever returned to any caller) and an established `_STAGE_TERMINAL_SEAL_HISTORY` entry. The test proves two ordered groups of assertions, never conflated: **(I) while the stage-runner invocation is still active, after the mint failure but before final bounded cleanup:** (1) `_STAGE_TERMINAL_SEAL_HISTORY`'s entry for this authority remains present; (2) a test-only, harness-forced malformed second reach of the sealing step is refused at requirement-6 step 2, before any second decision registration — this forced reach is not an operational retry (mirroring T-135(a)/(b)'s own distinction); (3) the orphaned `_STAGE_DECISION_SEALED` entry authenticates no usable decision — no code path anywhere can construct or return an object satisfying `type(x) is CFG1StageClosureDecision` for it, because no caller ever obtains the exact, freshly-generated `decision_nonce` `__post_init__` would need to re-check (mirroring T-124's enumeration technique). **(II) after the stage-runner invocation exits:** (4) the orphaned `_STAGE_DECISION_SEALED` entry is proven absent (bounded cleanup, not left indefinitely); (5) the `_STAGE_TERMINAL_SEAL_HISTORY` entry is **also** proven absent, using T-136's own before/after-return comparison technique — group (II) never re-asserts group (I)'s item 2 after return, because no sealing-capable lexical path exists at that point for any backstop to guard |
| **T-140** | **raw exception text from a synthetic mint failure never reaches console or any artifact (new, FU13, §16.3.8.3, §21.1's reduction rule).** For each of T-137/T-138/T-139's three injected failures, the synthetic exception carries a distinctive, deliberately identifying message and/or a distinctive exception type never otherwise used in this design's own code. The test captures the actual console output and every byte written to every run, refusal, and stage-closure path for the remainder of that stage execution, and proves: (1) the distinctive message/type appears in **none** of them; (2) the only code observable in the console output for this failure is the closed literal `STAGE_DECISION_MINT_FAILED`; (3) no traceback, `repr`, or `str(exc)` output of any kind reaches either sink |
| **T-141** | **§19.4/§22.4.2/T-123's no-confirmed-closure enumeration is exactly four and includes `STAGE_DECISION_MINT_FAILED` (new, FU13, mirrors T-123's own audit technique one level up).** A source-of-truth check proves: (1) the set of stage-ending cases §19.4 and §22.4.2 each enumerate as writing no confirmed stage-closure record has exactly four members in both sections, and the two sections' sets are identical; (2) `STAGE_DECISION_MINT_FAILED` is a member of that four-member set in both sections; (3) `STAGE_DECISION_MINT_FAILED` is, separately, proven **absent** from the closed `HALT_REASON_CODES` set (§19.4) and absent from all three closed record schemas (§22.1, §22.4.1, §22.4.2) — the same negative sweep technique T-94 already applies to the removed run-record fields, applied here to a code that must never be added to any of the four sets in the first place |

**T-3 network-safety rule (FU1, frozen):**

1. The harness runs Node with an **explicit minimal environment** that contains
   no `AIDO_*`, no `PI_QUALIFICATION_*`, and no proxy variables. The Python test
   asserts that name set before launching Node.
2. **Before any installed Pi module is imported or invoked**, the harness
   installs interception that throws on `globalThis.fetch` (except the injected
   fake), `net.connect`/`net.createConnection`, `tls.connect`, `http.request`,
   `https.request`, and `dns.lookup`/`dns.resolve*`. The fake `fetch` is passed
   explicitly through request options and returns a synthetic streamed response.
3. **Any attempted real network or DNS operation is a test failure**, never
   swallowed.
4. Endpoint and key are synthetic literals only (for example
   `http://cfg1-conformance.invalid/v1`, a reserved non-resolving name, and
   `cfg1-synthetic-key`). The real base URL and real credential are never read.
5. The payload is captured via `onPayload`, is **test-local**, is never written
   to the CFG1 results directory, and is not experiment evidence.
6. Assertions: Q vs R differ only in `messages[0].role`; Q vs E differ only in the
   presence of `reasoning_effort`; `compat: {}` and
   `compat: {supportsDeveloperRole: true, supportsReasoningEffort: true}` are
   payload-identical to Q; and the composed model object serialized with
   `JSON.stringify` has exactly the §2.5 `compat` shape for each arm.

**T-16…T-22 stage-output-authority regressions (FU2, frozen):** these prove the
§16.3 mechanism itself, independent of any live Pi/broker/workspace activity —
pure Python, `tmp_path`-scoped, no subprocess. The identifier grammar
(`re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value)`, applied only after
`type(value) is str` is exactly true) and the containment proof (§16.3) are
exercised directly against `establish_stage_output_authority`, never through a
live stage run. T-22 wraps `os.mkdir`/`Path.mkdir`/`open` with spies for the
duration of each malformed-identifier case and asserts the spy call count is
zero, so "refused before any filesystem operation" is verified mechanically
rather than by inspection of the refusal message alone.

**T-23…T-37 root-provenance, authority-forgery, and artifact-binding
regressions (FU3, frozen).** These prove §16.3.2's root provenance, §16.3.3's
mint-registry unforgeability, §16.3.4's consumption-boundary re-proof, and
§22.5's post-hoc artifact binding — again pure Python, `tmp_path`-scoped, no
live Pi/network/model/credential activity. **Where the platform allows it,
T-29 and T-31 use real filesystem tampering** — an actual symlink
(`os.symlink`) on POSIX runners, an actual junction/reparse point via the
platform's own reparse-point creation mechanism on Windows — **not only a
mocked `resolve()` or `lstat()` return value**, because the defect this closes
is specifically about what real `resolve()` does through a real redirect. If a
CI platform cannot create a reparse point without elevated privileges, the
implementation must still exercise the POSIX symlink form there and mark the
Windows-junction variant of T-29/T-31 as platform-conditional — never silently
skip the whole regression. T-33–T-37 construct **two or more genuine execution
directories** (via real, separate `establish_stage_output_authority` calls)
and move/copy/rename real files between them with the standard library
(`shutil.copyfile`, `os.rename`), then call the read-only binding verifiers —
via their FU5 one-argument `actual_path`-only API (§22.5.2) — on the real
resulting path. They never fabricate an in-memory record object to simulate a
moved file when a real move is just as cheap to construct in a test fixture,
and post-FU5 there is no parameter through which a fabricated object could be
supplied even if one wanted to.

**T-38…T-54 writer-boundary, schedule-binding, package-parent, authority-lifetime,
and post-hoc-input-boundary regressions (FU4, frozen).** T-38/T-39 are API
audits (signature inspection plus a direct `TypeError`-raising call attempt),
not behavioral simulations — they prove the writer surface itself, not merely
its documentation. T-40–T-42 exercise `_schedule_arm_for` directly against the
real, frozen §7.3 schedule values, including a same-object identity assertion
across all five call sites, so a future refactor that accidentally
reimplements the lookup somewhere fails the test even if the reimplementation
happens to agree today. T-43, like T-29/T-31, uses **real** filesystem
tampering where the platform allows it. T-44–T-49 construct one genuine
authority per test and drive it through each of the four retirement causes
independently, asserting the identical `UNKNOWN_MINT_NONCE` refusal in every
case (§16.3.9 deliberately does not distinguish them). T-50 exercises the
`actual_path` input gate in isolation from any live stage activity — pure
Python, `tmp_path`-scoped, no subprocess, spy-proven exactly as T-22 already
establishes for the identifier grammar. **T-51–T-54 are retargeted by FU5**
(see their individual rows): the `parsed_record` parameter they originally
tested is removed by FU5, so each row now points to its replacement among
T-55–T-68 rather than describing a still-current test of its own.

**T-55…T-68 writer-binding and byte-authoritative-verifier regressions (FU5,
frozen).** T-55–T-57 prove §16.3.8's Finding-3 ordering (type-gate,
canonicalize-once, never-re-read) using the same hostile-object shapes T-51/
T-52 originally described, now aimed at the writer's `payload`/
`refusal_payload` parameter instead of a verifier parameter that no longer
exists. T-58–T-61 are the mandatory five-mismatch-times-three-writer-type
matrix Finding 4 requires, run against one genuine `S1-X1` authority per test.
T-62 is a pure signature-inspection audit, proving Finding 5's "no such
parameter" claim about the API surface rather than merely asserting it. T-63
and T-64 are **real** filesystem tampering (an actual symlink and an actual
directory, respectively) exercised specifically to prove the lexical
`lstat`-before-`resolve()` ordering — a test that called `resolve()` first
would not distinguish these cases from their genuine counterparts, which is
exactly the defect Finding 3 identifies. T-65–T-67 prove the verifier is
byte-authoritative: the **same** `actual_path`, called twice with different
on-disk content in between, never returns a result influenced by the earlier
call. All are pure Python, `tmp_path`-scoped, no live Pi/network/model/
credential activity.

**T-69…T-82 record-family-schema, non-recursion, and exact-bytes regressions
(FU6, frozen).** T-69 is the mandatory three-by-two cross-validator matrix
Finding 1/5 requires — every genuine payload of one kind refused by both
other kinds' validators — proving schema isolation by behavior, not by
inspection of validator source. T-70–T-72 pin Finding 4's exact byte bound
and single-serialization discipline: a boundary-value pair at exactly the
frozen constant and one byte over it, plus a spy proving the writer never
serializes its canonical snapshot twice. T-73–T-79 prove Finding 3's
non-recursion and its consequences: T-73/T-74 are spy-proven zero-recursion
claims (mirroring T-22's and T-55's spy discipline) for each of the two
writers that must never call themselves or each other; T-75/T-76 are the
end-to-end outcomes those failures produce (`EMISSION_FAILED`, and
console-only reporting with authority retirement, respectively); T-77 proves
a refusal record's identity fields are freshly built, never copied from a
rejected payload, using an adversarial payload designed to look plausible if
copied; T-78/T-79 prove §19.1 item 2's admission-rule tie-in is mechanical —
a row-15 halt is driven by `halt_triggered_by_this_run`, not inferred from an
emission status two different halting/non-halting paths otherwise share.
T-80–T-82 prove Finding 2's run-artifact-verifier dispatch: two positive
controls (a genuine run record, and — newly possible under FU6 — a genuine
refusal record, both accepted at a run path) and one negative sweep (four
discriminator-ambiguous shapes, each refused with **zero** validator calls,
spy-proven). All are pure Python, `tmp_path`-scoped, no live
Pi/network/model/credential activity, consistent with every prior FU's
regressions in this section.

**T-83…T-93 emission-phase, successful-stage-invariant, halt-reason-vocabulary,
step-6/step-7-split, and S2-schedule regressions (FU7, frozen).** T-83–T-87
prove Finding 1's corrected phase boundary: T-83 is the positive case (a
`PRE_CREATE` failure gets exactly one fallback attempt, spy-proven zero
final-path writes before it); T-84 is its negative mirror (a post-create
failure gets zero fallback attempts, spy-proven); T-85 proves the residue
policy directly (zero overwrite/truncate/rename/unlink calls against a
post-create failure's leftover bytes); T-86 extends T-73's non-recursion
proof to the refusal writer's own post-create sub-case, paired with T-85's
residue discipline (**T-87 was originally this same extension for the
stage-closure writer; FU8 Finding 3 rewrote it into the mandatory
close-after-full-write regression — see below**). T-88/T-89 prove Finding
2's corrected schema-level invariant directly against the validator — a
shape the admission rule already forbids is now also unconstructible at the
schema — rather than only re-deriving the same conclusion from
admission-rule behavior (**T-89's halt-code literal and T-90's scope were
both revised by FU8 — see below**). T-91/T-92 prove Finding 4's
step-6/step-7 split directly: T-91 shows the now-corrected step-6 class
(off-schedule arm, mismatched filename) never reaches step 7, and T-92 is
the meta-test making explicit that every step-7 regression in this design
(T-58–T-60) first demonstrably passes its own payload validator, closing the
gap where an untested precondition could silently make a "step-7-only" claim
vacuous. T-93 proves Finding 5's frozen `S2` schedule by exact value and by
the same shared-callable-identity discipline T-42 already established for
`S1`. All are pure Python, `tmp_path`-scoped, no live Pi/network/model/
credential activity.

**T-94…T-101 halt-code truthfulness, run/stage-closure authority separation,
residue-versus-live-outcome, and admission-ordering regressions (FU8,
frozen).** T-94 proves Finding 2's schema correction directly — the removed
fields are absent from the closed key set (not merely undocumented), and
`run_classification` remains genuinely payload-only recomputable without
them. T-95/T-96 prove Finding 1's renamed, truthful `RUN_RECORD_EMISSION_FAILED`
code is produced identically by both of the two structurally different
causes it now covers (a direct post-create primary failure with no fallback
ever attempted, and a `PRE_CREATE` fallback that is attempted and then
itself fails) — proving the code's neutrality is a property of the
implementation, not just of this document's prose. T-97/T-98/T-99 prove
Finding 3's residue semantics as three separate claims that must not be
conflated: T-97 isolates the `PRE_CREATE` "truly nothing on disk" case; T-98
(via the rewritten T-87) proves a post-create close failure's **live**
result is `FAILED` even though its residue is, in this specific sub-case,
completely valid; T-99 proves a post-hoc `True` on that same valid residue
never feeds back into or revises the already-sealed live result, for both
the stage-closure and the run-record cases. T-100 proves Finding 5's new
hard-stop class end-to-end, mirroring §16.3.7's own already-accepted
zero-writes/immediate-retirement/console-only shape at the one point (L0,
before any run resource exists) that class did not yet cover. T-101 proves
Finding 4's L28→L29→L30 ordering mechanically, not only as documentation.
All are pure Python, `tmp_path`-scoped, no live Pi/network/model/credential
activity.

**T-102…T-123 sealed-stage-decision, halt-precedence, validation-versus-
provenance, and create-attempt-matrix regressions (FU9, frozen except
T-102, T-103, T-106, T-107, and T-110, each updated in place by FU10 — see
each row's own text; T-102/T-103's updates are wording-only, since the
mechanism they test — the type/nonce gate on an already-sealed `decision`
— is unchanged by FU10; T-106/T-107/T-110's updates are substantive, since
each assumed a directly-callable sealer FU10 removes; every other row is
unchanged).** T-102–T-105
prove Finding 1's mint-registry-mirrored unforgeability for
`CFG1StageClosureDecision`, in the same shape T-25–T-28 already established
for `CFG1StageOutputAuthority`: a genuine positive control, unregistered/
forged-nonce refusal with zero I/O, a mutated-field refusal at re-verification,
and an authority-rebinding refusal. T-106/T-107 prove the two remaining
"exactly once, exactly in order" guarantees — sealing cannot precede L29's
result (mirroring T-101), and a stage gets exactly one seal, ever. T-108/T-109
prove the writer's own boundary directly: a signature audit (mirroring T-38)
showing no caller-selectable stage-decision parameter exists at all, and a
field-for-field proof that written bytes are exactly the sealed decision's
own fields, no transformation. T-110 is the end-to-end regression closing the
loop: every avenue toward getting the writer to emit an *alternate*,
independently self-consistent closure record while holding a genuine
authority is proven to fail, because every avenue reduces to one of
T-102–T-105's already-proven mechanisms. T-111–T-114 prove Finding 2's
precedence is not just stated but implemented: a full pairwise sweep, the two
named overlap cases stated explicitly in the design, and an identity proof
that exactly one function computes it everywhere it is needed. T-115 proves
Finding 5's validator-scope claim directly — the four codes whose provenance
is L30-only are proven genuinely unenforceable from `ordinal_status` alone,
not merely asserted to be. T-116–T-122 are the create-attempt outcome matrix
Finding 3 requires, one dedicated test per (writer × collision-or-not) cell
plus the stage-closure writer's own two-cause pair, with T-120 consolidating
the shared non-recursion proof across the four run-path-writer sub-cases.
T-123 is a documentation/source-of-truth consistency check, included because
Finding 4's own defect was a normative-text drift between two sections that
no behavioral test would have caught. All are pure Python, `tmp_path`-scoped,
no live Pi/network/model/credential activity.

**T-124…T-132 terminal-issuance-boundary and successful-completion
regressions (new, FU10).** T-124 is the phase prompt's own required
adversarial proof, in its strongest form (no reachable callable exists at
all, not merely "every callable we tried refuses"). T-125 extends it to an
invented *ledger* rather than only an invented decision-fact tuple. T-126–
T-128 prove the three-way L30 transition end-to-end, including the two
concrete final-ordinal cases (`S1`/`S2`) the phase prompt names explicitly.
T-129 proves `LAST_ORDINAL` is genuinely derived, mirroring this design's
existing identity-of-callable discipline rather than inventing a new,
unverified one. T-130 proves the halted branch's continuity with the
unmodified §19.5 precedence machinery. T-131 restates §22.4.2's
already-accepted successful-stage schema shape as a decision-object-level
property, closing the loop between §16.3.8.3 and §22.4.2 explicitly. T-132
proves the decision **consume-once** mechanism directly (T-107, revised by
FU11 and FU12, is the companion **seal-once** proof — see below). All are
pure Python, `tmp_path`-scoped, no live Pi/network/model/credential
activity, consistent with every prior FU's own testing discipline.

**T-107 revised, and T-133…T-136 added (new, FU12, §16.3.8.3 requirement
6).** T-107 is strengthened from a single seal-once assertion into four:
L30's own per-admitted-ordinal cardinality, branch B's non-sealing
behavior, a second-seal-before-consumption refusal (T-107A), and — the
regression FU11 lacked — a second-seal-**after**-consumption-revocation
refusal (T-107B), proving the corrected `_STAGE_TERMINAL_SEAL_HISTORY`
mechanism survives exactly the adversarial internal ordering that would
have defeated FU11's single-registry mechanism. T-133/T-134 are direct,
narrow positive controls that the seal-history fact specifically survives
consumption revocation and writer failure, independent of T-107B's
end-to-end framing. T-135 is the required partial-failure-atomicity proof
across the mint sequence's three failure points, including the
fail-closed-not-reopened sub-case the phase prompt requires be shown
mechanically rather than assumed. T-136 proves the seal-history fact's own
cleanup timing — present for the entire stage-runner invocation, absent
only after it returns. All are pure Python, `tmp_path`-scoped, no live
Pi/network/model/credential activity.

**T-135 rewritten, T-136 extended, and T-137…T-141 added (new, FU13,
§16.3.8.3's new "Terminal-decision mint failure disposition").** T-135 is
rewritten to remove the retry expectation FU12 left standing for a
pre-history-establishment mint failure, replacing it with a proof that no
retry is attempted and the terminal `STAGE_DECISION_MINT_FAILED`
disposition is reached regardless. T-136 is extended to prove the identical
before/after-return cleanup timing for the mint-failure exit, not only for
ordinary stage completion. T-137–T-139 are the three required per-failure-
point proofs — before history establishment, after history but before
decision registration, and after decision registration but before object
construction — each proving the exact retirement timing, zero
stage-closure-writer calls, and zero second-seal attempts §16.3.8.3 now
freezes, plus (T-138/T-139) the correct fate of whichever registry entry
was already established. T-140 is the required raw-exception-containment
proof, mirroring §21.1's reduction rule discipline directly against a
synthetic mint failure rather than only asserting the rule applies. T-141
is the one-level-up audit T-123 already establishes a pattern for, applied
to the corrected four-case no-confirmed-closure enumeration and to
`STAGE_DECISION_MINT_FAILED`'s required absence from `HALT_REASON_CODES`
and from every durable schema. All are pure Python, `tmp_path`-scoped, no
live Pi/network/model/credential activity.

**T-135, T-138, and T-139 corrected in place (new, FU14).** No test IDs are
added. FU13's own T-135 text asserted, in its introductory sentence, that
none of its three sub-cases is followed by any further sealing attempt,
while its (a)/(b) bodies then required a synthetic subsequent sealing reach
— a direct self-contradiction. FU14 rewrites the introductory sentence to
state the true, non-contradictory rule: the **stage runner itself** performs
zero second mint/seal attempts in all three sub-cases (an operational-retry
claim), while sub-cases (a) and (b) separately permit the **test harness**
to force exactly one malformed, test-only second reach of the lexical
sealing step (an adversarial-injection technique, not a retry path, and one
that grants no production capability). Sub-case (c) is corrected to prove
no such forced reach at all — a history entry that was never created cannot
be the target of a second-seal-refusal proof, so (c) instead proves the
two registries are unchanged, the authority is retired, the console
disposition is `STAGE_DECISION_MINT_FAILED`, and the stage-closure writer
is never called. T-138 is corrected to state `_STAGE_TERMINAL_SEAL_HISTORY`'s
lifetime as exactly the four ordered facts T-136 already freezes — present
through retirement, present through console reporting, present for the
remainder of the stage runner's own invocation, and absent only after that
invocation returns — removing FU13's own overbroad "remainder of the test
process's reachable lifetime" wording, which claimed a lifetime T-136 does
not grant. T-139 is corrected to state its five assertions as two
explicitly ordered groups — everything true while the stage-runner
invocation is still active (history present, a forced second reach
refused, the orphan decision entry unusable) strictly before everything
true only after that invocation returns (both the orphan decision entry
and the seal-history entry now absent) — so it can no longer be read as
requiring the seal-history entry to still exist, or to still refuse
anything, after the runner has returned. None of these three corrections
changes what any of T-135/T-138/T-139 proves about the design; each
corrects only the sentence structure that made the proof's own wording
self-contradictory or overbroad. All are pure Python, `tmp_path`-scoped, no
live Pi/network/model/credential activity.

---

## 12. Run classification and failure semantics

### 12.1 Run classification (evaluated in order; first match wins)

| # | Classification | Condition |
|---|---|---|
| 1 | `INDETERMINATE_LIFECYCLE` | `lifecycle_all_closed == false` (§17 closure predicates) |
| 2 | `REFUSED_PRE_DISPATCH` | `pre_dispatch_refusal_code` non-null (includes `CONFIG_SHAPE_MISMATCH` and `PROMPT_REFUSED_BY_RUNTIME`) |
| 3 | `INDETERMINATE_DISPATCH` | `dispatch_state == SEND_STATE_INDETERMINATE` |
| 4 | `INDETERMINATE_RUNTIME_STREAM` | `runtime_wait_outcome` ∈ {`PROTOCOL_VIOLATION`, `OUTPUT_CAP_EXCEEDED`, `EVENT_CAP_EXCEEDED`, `READ_ERROR`, `UNRECOGNIZED`} |
| 5 | `INDETERMINATE_NO_ACTIVITY_EVIDENCE` | `runtime_reported_tool_activity_available == false` or `broker_recorded_activity_available == false` |
| 6 | `INDETERMINATE_UNEXPECTED_TOOL_ACTIVITY` | `runtime_reported_unexpected_tool_call_ids > 0` — **regardless of any `aido_*` activity** |
| 7 | `INDETERMINATE_UNATTRIBUTABLE_TOOL_CALL_ID` | `runtime_reported_unidentified_tool_call_id_seen == true` |
| 8 | `INDETERMINATE_OBSERVATION_DISAGREEMENT` | any predicate in §12.2 holds |
| 9 | `ACTIVE` | `aido_read_call_ids + aido_edit_call_ids >= 1` |
| 10 | `INDETERMINATE_PROVIDER` | zero expected activity and (`stop_reason_counts.error + aborted >= 1` or `auto_retry_events >= 1` or `stop_reasons_available == false`) |
| 11 | `INDETERMINATE_WAIT_ENDED` | zero expected activity and capture basis `wait_ended_before_settled` |
| 12 | `INACTIVE` | zero expected activity, basis `agent_settled`, no provider error, no auto-retry |

`INACTIVE` carries `length_terminated = (stop_reason_counts.length >= 1)`.

**Unexpected-tool correction (FU1).** Only `aido_read` and `aido_edit` were
offered. By source, an unregistered name receives an immediate "Tool … not
found" error result inside the agent loop and never reaches an extension or the
broker (`agent-loop.js:403-407`). A hallucinated call therefore proves nothing
about the intended AIDO tool path. Row 6 routes **any** unexpected call to
indeterminate, **before** `ACTIVE`, including runs that also carry expected
calls. Row 7 exists because OBS1's id-collapse can misattribute a collapsed
entry's category (OBS1 claim scope); a collapsed id could hide an unexpected call
inside an `aido_*` bucket or the reverse.

### 12.2 Observation-disagreement predicates (CFG1 interpretation only)

Evaluated only after rows 1–7 are excluded, so no unexpected or collapsed call is
present and both activity families are available. **Not an OBS1 schema invariant.**
They only ever route to indeterminate.

| Id | Predicate | Basis requirement | Source rationale |
|---|---|---|---|
| D-1 | `broker_read_ops + broker_edit_ops + broker_refusals > 0` while `aido_read_call_ids + aido_edit_call_ids == 0` | `agent_settled` only | only the run's extension holds the binding and connects to this run's pipe |
| D-2 | `aido_read_end_observed − aido_read_error_results > broker_read_ops`, or the same for edit | any | a non-error `aido_*` end is returned only after a successful `brokerCall`; refusal and unavailability throw (`ipc.ts:225-248`, `tools.ts:68`, `:127`) |
| D-3 | `broker_read_ops > aido_read_call_ids`, or `broker_edit_ops > aido_edit_call_ids`, or `broker_read_ops + broker_edit_ops + broker_refusals > aido_read_call_ids + aido_edit_call_ids` | `agent_settled` only | each execution issues exactly one `brokerCall` |
| D-4 | `broker_git_cross_check_agrees == false` at Git observation #1 | any | a change the broker did not make, or a broker mutation Git does not show, contaminates the workspace |

**Non-contradiction proof.** Unexpected calls never reach the broker (row 6
cause), and rows 6–7 exclude every case in which runtime category counts could be
misattributed. So D-1…D-3 compare only the two categories the broker can serve.
No run can satisfy both "unexpected-tool" and "disagreement": the first match
wins, and the D predicates never cite unexpected counts. D-1 and D-3 are
suppressed for `wait_ended_before_settled`, because runtime counts are then
lower bounds and broker frames may legitimately exceed them. D-2 remains sound
there, because a successful end still requires a prior accepted operation.

### 12.3 Arm and stage aggregation

- Arm **ACTIVE** — its three runs are all `ACTIVE`. Arm **INACTIVE** — all three
  `INACTIVE`.
- Arm **MIXED** — three determinate (`ACTIVE`/`INACTIVE`) runs, not unanimous.
- Arm **INDETERMINATE** — any run of the arm is indeterminate or refused, has
  `EVIDENCE_REFUSED` emission status, has `EMISSION_FAILED` emission status
  (new, FU6 — no successfully-confirmed, authoritative artifact exists for
  that run; a post-create write failure may leave non-authoritative residue
  on disk, but §16.3.8.2's residue policy means that residue is never read
  for classification, so the arm is exactly as indeterminate as a run with
  no artifact at all — wording corrected, FU7, to avoid the false-in-general
  claim that literally nothing was ever written), or was never executed
  because the stage halted (`NOT_EXECUTED`).
- A variant arm whose runs are all `INDETERMINATE_PROVIDER` while Q's are
  determinate is reported as "variant not deliverable through this route". The
  contrast is indeterminate.

### 12.4 What is not a retry

The schedule is fixed, unconditional, and outcome-independent. Pi's own
settings-level retry is identical across arms and recorded, never altered.

---

## 13. Pre-declared interpretation matrix

The 3/3-vs-0/3 unanimity threshold is the smallest replication at which complete
separation has one-sided exact probability 1/20 under exchangeability. That is a
declared descriptive threshold, **not** a statistical proof of causation. Every
conclusion is scoped to `qwen3-coder-next`, the B300 LiteLLM route, Pi 0.85.1,
`CFG1-T1`, and bare transmission with a named path.

### 13.1 Per-contrast (X ∈ {R, E})

| Q | X | Conclusion |
|---|---|---|
| INACTIVE | ACTIVE | **Configuration-sensitive behavior established for the single variable X.** Not yet root cause of Q1/Q2/Q3. |
| ACTIVE | ACTIVE | **Config hypothesis weakened** for named-path tasks; prior uncertainty consistent with missing observability; see §13.4. |
| INACTIVE | INACTIVE | **Variable X not supported as a causal explanation** at this route; cannot separate model insensitivity from proxy neutralization. |
| ACTIVE | INACTIVE | Sensitivity in the opposite direction: X suppresses tool requests; does not explain the Q pattern and refutes any assumption that historical settings are "correct". |
| MIXED (either) | — | Stochastic at N=3. No causal claim. No automatic escalation. |
| INDETERMINATE (either) | — | Contrast INDETERMINATE. Investigate the named cause; never read it as zero tool use. |

### 13.2 Stage-1 composite

| Q | R | E | Reading | Stage 2 (H) |
|---|---|---|---|---|
| INACTIVE | ACTIVE | ACTIVE | each variable alone flips tool requesting | not needed |
| INACTIVE | ACTIVE | INACTIVE | role sensitive; effort not | not needed |
| INACTIVE | INACTIVE | ACTIVE | effort sensitive; role not | not needed |
| INACTIVE | INACTIVE | INACTIVE | neither single variable sufficient | **may be authorized** (joint historical condition) |
| ACTIVE | determinate | determinate | compat hypothesis weakened; §13.1 for any suppressing variant; §13.4 | not warranted |
| otherwise | | | contrasts per §13.1; no composite claim | not authorized by this matrix |

Stage 2, if authorized, re-runs Q interleaved with H, N=3 each, in the
**frozen exact schedule `Q H H Q Q H`** (§7.3a — no longer "for example";
FU7 froze this design-time, and Stage 2's own future authorization supplies
only a `stage_execution_id`, never an order; exact positional balance is
impossible with three pairs). It never reuses Stage-1 Q runs, and it
inherits §16–§22 unchanged.

### 13.3 Edit-layer distinctions (secondary; never part of the contrast)

| Layer | Evidence | Trust |
|---|---|---|
| tool schema delivered | source (§3.5) + T-3 + H1 sentinel + accepted `--tools` | not observed on the wire |
| tool requested | `runtime_reported_aido_*_call_ids` | runtime claim — **primary dependent variable** |
| broker received | broker operations + refusals | AIDO-authored diagnostic |
| broker authorized | accepted read/edit counts | AIDO-authored diagnostic |
| filesystem mutation | `broker_recorded_edited_path_count` | diagnostic, never repository truth |
| Git-observed change | `changed_tracked_paths` at observation #1 | **authority** |
| verification | `verification_passed` | authority; controlled invocation, not a sandbox |

### 13.4 Roadmap consequence for F1 (FU1)

**If Q is ACTIVE under the named-path `CFG1-T1` fixture, and the compat contrasts
do not explain the historical pattern, then D5 — the prompt-manifest /
path-discoverability divergence — becomes the next leading harness-owned
hypothesis, to be designed separately.** This is a roadmap statement only: it
authorizes no execution, no manifest-bearing CFG1 arm, and no merge with DX1.

---

## 14. Exact future authorization required

### 14.1 Sequence

1. **`5F3B-HARNESS-CFG1-IMPL`** — offline only. Implements §7.4, §7.5, §11, §12,
   and §16–§22, plus **T-1…T-141** (FU6 extended the regression list from
   T-1…T-68 to T-1…T-82; FU7 extended it to T-1…T-93; FU8 extended it to
   T-1…T-101; FU9 extended it to T-1…T-123; FU10 extended it to T-1…T-132;
   FU12 extended it to T-1…T-136 — T-133–T-136 (new, FU12); T-107 revised
   in place, FU11 and again FU12; FU13 extended it to T-1…T-141 —
   T-137–T-141 (new, FU13); T-135 rewritten and T-136 extended in place,
   FU13; FU14 adds no new regression id and leaves the scope at T-1…T-141,
   correcting T-135, T-138, and T-139 in place for wording/ordering only
   (§11.3, this section unaffected in range). **No CFG1-IMPL authorization
   may omit T-124…T-132**
   (new, FU11), **T-133…T-136** (new, FU12), **or T-137…T-141** (new,
   FU13) — the first group proves the terminal-issuance boundary and
   successful-completion closure FU10 froze, the second proves the
   seal-once-versus-consume-once separation FU12 froze, and the third
   proves the terminal-decision-mint-failure disposition FU13 froze; an
   implementation lacking any group would be unverified against exactly
   the defect class its own FU exists to close. T-3 needs explicit
   authorization to execute the
   installed Pi library offline under Node with §11.3's interception rules;
   T-29/T-31/T-43/T-63 need explicit authorization to create real
   symlinks/junctions under `tmp_path` for filesystem-tampering regressions
   (still no live Pi/network/model/credential activity).
2. **`5F3B-HARNESS-CFG1-LIVE-S1`** — must authorize, verbatim and exhaustively:
   - one declared `stage_execution_id` literal (for example `S1-X1`), which
     must itself satisfy the §16.3.1 grammar (`type(...) is str`,
     `re.fullmatch(r"[A-Za-z0-9_-]{1,64}", ...)`) — the runtime independently
     re-proves this rather than trusting the authorization document — never
     reused and never a timestamp;
   - model `qwen3-coder-next` only, on `b300_pi_qualification` / `b300_litellm_proxy`;
   - reading `AIDO_LITELLM_BASE_URL` and `PI_QUALIFICATION_B300_ROUTE_KEY`
     through the frozen credential-boundary ordering, once per admitted run;
   - at most **9** authenticated non-inference `GET /models` checks (one per run);
   - exactly the §7.3 schedule, at most one prompt write per run, **9 maximum
     in total**;
   - the §16 lifecycle and §19 admission/halt rules as frozen, with no resume
     inside that authorization;
   - Pi 0.85.1 with the §14.2 digests;
   - output only to `RESULTS_ROOT/<stage_execution_id>/` (§16.3.2–§16.3.3)
     inside the CFG1 package — no other root, parameter, or override;
   - no qualification artifact, verdict, ranking, lineage or companion read for
     authority, written, or modified.
3. **`5F3B-HARNESS-CFG1-LIVE-S2`** — only if §13.2 row 4 obtains, with its own
   execution id. Count (6) and order (`Q H H Q Q H`, §7.3a) are **not**
   supplied by this authorization — they are frozen design-time by §7.3a
   (FU7) — so `LIVE-S2` states only the `stage_execution_id` literal, exactly
   as `LIVE-S1` does, never a schedule choice of its own.
4. **Resumption after any halt** requires a new authorization with a new
   `stage_execution_id`. It must state explicitly whether earlier completed runs
   participate in any contrast. The default is **no**.

### 14.2 Pinned seam digests (installed Pi 0.85.1, SHA-256)

```text
f1738e4b42203e5f22bcb513f13fb2fb224f1e98d1f129ff042f87048665a94c  package.json
8189b66abc4f9f431dbb70941dcba690d76d040de1fbfff212886be35a53639d  dist/cli.js
f0b7e5a8419af8d149ffe367af2992c76ce70b73484c15492bd50787d4f4962a  dist/main.js
6969bd56ba8e1628cd033bb15cb15fe38299f00b5ad84f4f8ef37a33a98681c9  dist/core/sdk.js
13196dce2ddb143f6f4c28af2e34374f84004e50c7b71ba7b900e1acf84479b6  dist/core/defaults.js
ac983b5825f96eb2bfdeb9776cedeb540724e14f1c9fe41ded9f5411038dd522  dist/core/model-config.js
8eca507009d00768130e46cd9a0831e4fa2f98b81435ae0a8d5079a1d27e13cd  dist/core/provider-composer.js
32cd50599d9e6e001229090e3d0554b60e4addb8ab7b3165635a574feb660b74  dist/core/model-runtime.js
00f57b9c60f990f059c48b14269e571fabdfefaab93b062ee77501d5fa9db0a7  dist/core/model-resolver.js
4a57f022a27f2ae22d7d0c0d8f0ef4a63f869b878483699d4102055239bdea0a  dist/core/system-prompt.js
fb8a3981c20c8c0bbd42231b1c99a10335fb3858b659056b341954de9cfa467f  dist/core/agent-session.js
e7e4724aa55c5aac73cf36793653b26736200e5c59d58373990fc31028f86477  dist/modes/rpc/rpc-mode.js
b54df5a36d523febdeebfc5682dc4faed101fee10aba913d5f3679582f018da3  node_modules/@earendil-works/pi-ai/package.json
1e2097ced37cf0e21aa5711297eecc77916de8a4ed81a9019bc7d97b22825fa3  node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js
1caf860e028e22639578aba3ec8b79e5be9650c27bd3f19471c78502976555f3  node_modules/@earendil-works/pi-ai/dist/api/simple-options.js
42610d47fe293d99f4b05b147971e181c7312ea47c9be2906a4803955276a8a4  node_modules/@earendil-works/pi-ai/dist/models.js
f4c388363706ae0eb8eca4e7663f85f231bf0882d7e32c16f7cfd98153b26551  node_modules/@earendil-works/pi-agent-core/package.json
d84351e451b9fef40fe2532c446aca90d26a4be9038b2d77d3d45dd6eab21d41  node_modules/@earendil-works/pi-agent-core/dist/agent.js
```

The implementation phase must extend this set with the exact digests of
`dist/modes/rpc/jsonl.js` and `pi-agent-core/dist/agent-loop.js`, which FU1 relies
on, at its own review. A mismatch refuses before any credential read. It means
the derivation must be re-reviewed, not that Pi is incompatible.

### 14.3 Frozen-boundary compliance

| Frozen item | CFG1 effect |
|---|---|
| OBS1 schema/version, `AttemptIdentity`, companion kinds | unchanged; projection and snapshot imported; no `.activity.v1` emitted |
| corpus, `VALID_TASK_IDS` | unchanged; `CFG1-T1` lives only in the CFG1 package |
| primary schema v2, lineage, policy r1, H1–H14, ranking, verdicts, nine artifacts | unchanged; not imported (T-8, T-9) |
| semantic retry, token, credential policies | unchanged |
| workspace authority, tool allowlist, extension code | reused unmodified |
| four semantic ports, `TaskAdapterBundle`, gate topology | not used, not amended |
| `ar2.capability._verify_root_authority`, `ar2.capability._is_symlink_or_reparse_point`-via-`ai_dev_orchestrator.workspace.canonical`, `qualification.i2b_workspace`'s mint-registry shape, `qualification.i2_pi_config`'s `repr=False` authority-token shape | reused (by direct import) or mirrored (by new CFG1-owned code following the same shape) unmodified (§7.4, §7.5, §16.3) |
| `CLAUDE.md` | unchanged |

**No frozen qualification, OBS1, or AR2 contract requires amendment.**

---

## 15. Explicit non-goals

- no production or test change in this phase; no Pi launch, B300 contact, model
  call, credential or endpoint read;
- no re-run, re-scoring, reinterpretation or backfill of Q1/Q2/Q3; no companion
  synthesized for historical artifacts;
- no qualification credit or verdict/ranking/hard-bar input from CFG1;
- no Candidate C; no lineage claim linking `qwen3.6-27b` to `Qwen3.6-27B-262K`;
- no DX1 design, prompt or task; Q arms are not DX1 evidence;
- no manifest-bearing variant (D5 identified and roadmapped, not tested);
- no change to `i2_pi_config.py`, `semantic_controller.py`, corpus,
  `VALID_TASK_IDS`, `runtime_activity.py`, `safety.py`, extension, `build_pi_argv`,
  `ar2.broker`, `ar2.supervisor`, `ar2.fixtures`, `ar2.capability`;
- no `before_provider_request` hook, capturing proxy, route change or
  direct-vLLM arm;
- no `--thinking`, `defaultThinkingLevel`, `reasoning: false`, `thinkingLevelMap`,
  `maxTokens`, `temperature`, or any compat field other than the two named;
- no H arm in Stage 1; no automatic Stage 2; no automatic N escalation; no
  replacement, timestamp-selected, or re-executed runs;
- no workspace or generated-config preservation as evidence;
- no kill-by-name, PID enumeration, process-tree management, job objects,
  `taskkill`, `psutil`, or descendant tracking;
- no debugging diagnostic channel that becomes durable evidence;
- no reasoning content or counts, assistant text, verification output text,
  failed node ids, or wall-clock timing as evidence;
- no claim that the request was observed on the wire, that the proxy forwarded
  it unchanged, that the backend honored the role or effort field, that backend
  inference stopped, or that descendants stopped;
- no sandboxing or isolation claim;
- no commit or push.

---

## 16. Per-run lifecycle state machine (FU1, +§16.3 FU2)

### 16.1 Principles

1. **One run owns exactly the resources it creates**, identified by in-memory
   handles minted in that run (§17). No resource is looked up by name, PID, path
   string, or file content.
2. **Every step has an authority precondition.** A step whose precondition fails
   never executes. Control transfers to the closure sequence, which acts only on
   resources whose creation fact is recorded.
3. **Closure always runs** after the first resource-creating step, in the fixed
   order L21→L27, skipping only steps whose resource was never created. It is
   never skipped because an earlier closure step failed; §18 declares each
   dependency.
4. **No durable write occurs before L29.** The record is sealed only after every
   lifecycle outcome is known (§20).
5. **Credential consumers are exactly** the route check (L7), the generated
   `$ENV` carrier into the Pi child environment (L12), and the scrub needles
   (L29). No Git, fixture, or verification child environment ever carries a
   credential or endpoint. Python string erasure is never claimed.

### 16.2 Steps

| Step | Action | Authority rationale / precondition | Failure transfers to |
|---|---|---|---|
| **L0** ADMISSION | Stage runner admits ordinal *k*: `(block, position) = SCHEDULE[k]`; `arm = _schedule_arm_for(stage_id, k)` (§16.3.8's one shared derivation, not a re-implemented lookup); fresh `run_id = secrets.token_hex(16)`; derive the record path **only** by calling the same internal path-derivation logic the writer itself will later use against the stage's already-established, ACTIVE `CFG1StageOutputAuthority` (§16.3.3, §16.3.8, §16.3.9), and require it absent | *k*=1, or run *k*−1 produced an **admission token** (§19); the stage output authority (§16.3) was established exactly once, before ordinal 1, is re-proven ACTIVE on every use, and is retired only at stage exit (§16.3.9). Schedule is a module constant, never a parameter | **normal admission refusal** (`k`≠1 and no token from `k`−1): ordinary stage HALT via §19, nothing created for *k*. **The path-already-exists case is different** (new, FU8): the derived path existing **before this ordinal is ever admitted** is `OUTPUT_NAMESPACE_PREOCCUPIED`, a hard stop distinct from an ordinary halt — no run resource of any kind is created, the stage-output authority is retired immediately, reporting is console-only, and no run/refusal/stage-closure record of any kind is written (§16.3.10) |
| **L1** OFFLINE PREFLIGHT | seam digests (§14.2); fixture revision pin; generator self-check on synthetic URL (T-1/T-2 relations); arm↔schedule binding; `preflight_pi_installed_offline`, environment forbidden-fragment audit; Node/Pi identity probe (`--version`, provenance) | no credential, no disposable resource; mirrors frozen non-secret-before-secret ordering | `REFUSED_PRE_DISPATCH`; nothing to close |
| **L2** WORKSPACE MINT + POPULATE | `build_case_repository(CFG1_T1)` creates the fresh root, marker, `repo/` child and one commit; on return, register `nonce → BuiltFixture.authority` and claim it for `run_id` | the only origin of root authority is the frozen creator; ownership becomes provable only when the authority object is returned | if raised before returning an authority → `INDETERMINATE_LIFECYCLE` (orphan unprovable, never deleted); otherwise closure from L27 |
| **L3** WORKSPACE BASELINE | re-prove root authority; observe HEAD, clean status, tracked manifest == fixture file set, witness SHA-256; run baseline verification once and require exactly the seeded failure | repository-controlled code (AIDO-authored fixture only) runs **before** any credential is in process memory — the frozen `WORKSPACE_BASELINE`-before-credential order | `REFUSED_PRE_DISPATCH`; closure L27 |
| **L4** CREDENTIAL BOUNDARY | `resolve_connection_after_preflight(non_secret_gates=<L1 results>, read_connection=<reads AIDO_LITELLM_BASE_URL, PI_QUALIFICATION_B300_ROUTE_KEY>)` | frozen I2A ordering: credential read only after every non-secret gate passed | `REFUSED_PRE_DISPATCH`; closure L27 |
| **L5** SECRET CONTEXT | `build_secret_context(base_url, api_key, model_id)` | frozen single URL validator | as L4 |
| **L6** BASE-URL COMPAT CLASSIFICATION | pure in-memory test against the §2.2 substring list + `api.openai.com` → one bool | effective values in §2.2 depend on it; URL never recorded | `REFUSED_PRE_DISPATCH(BASE_URL_COMPAT_DETECTION_TRIGGERED)`; closure L27 |
| **L7** ROUTE/MODEL CHECK | `observe_b300_route_serves_model(...)`, exactly once → reachable, served (exact bools) | same-run authority from this run's secret context. **Differs from the qualification controller**, which checks after handshakes; placed before broker/runtime creation so a route refusal creates no live resource | `REFUSED_PRE_DISPATCH(ROUTE_UNAVAILABLE)`; closure L27 |
| **L8** CAPABILITY MINT | `mint_capability(authority=<registered>, tracked_manifest=<L3 observation>, protected_patterns, witness, caps=CapDefinitions())` | frozen mint re-verifies the marker itself; manifest is AIDO-observed | `REFUSED_PRE_DISPATCH`; closure L27 |
| **L9** CFG1 CONFIG GENERATION | write `settings.json` + `models.json` for the arm into `<root>/cfg1_pi_config` (created `exist_ok=False`); register issuance `(run nonce, path) → token`; finalize on-disk digests; require redacted digest == pinned arm digest | issuance-bound to this run's workspace (§17 row 3) | `REFUSED_PRE_DISPATCH`; closure L24, L27 |
| **L10** BROKER CONSTRUCTION | `BrokerBinding.mint(sed.capability_id)`; `RunState(caps)`; `BrokerRequestHandler(sed, run_state, binding)`; `BrokerServer(handler)` (random 128-bit pipe name) — no OS resource yet | one instance per run; `start()` never called twice | `REFUSED_PRE_DISPATCH`; closure L24, L27 |
| **L11** EXTENSION GENERATION | `write_disposable_extension(<root>, pipe_name, capability_id, token)` → `<root>/pi_extension` | the only on-disk location of the token lives inside the owned root | `REFUSED_PRE_DISPATCH`; closure L24, L27 |
| **L12** CHILD ENVIRONMENT | CFG1 builder ≡ I2 policy; `PI_CODING_AGENT_DIR` = this run's L9 directory (re-verified digests); credential via `$ENV` carrier name | the only credential hand-off to a child | `REFUSED_PRE_DISPATCH`; closure L24, L27 |
| **L13** BROKER START → READY | `server.start()` once; READY within `BROKER_READY_DEADLINE_SECONDS` | a tool call before the server exists must be impossible (`broker.py:458-505`) | `REFUSED_PRE_DISPATCH(BROKER_NOT_READY)`; closure L23, L24, L27 |
| **L14** PI LAUNCH | `supervisor = PiRpcSupervisor(argv=build_pi_argv(identity, extension_entry=<L11>, tool_allowlist, provider, model), cwd=<repo root>, environment=<L12>, bounds=RunBounds())`; `launch()` | fresh supervisor per run; Popen handle is the only runtime identity | `REFUSED_PRE_DISPATCH(RUNTIME_LAUNCH_FAILED)`; closure L21 (if `process` set), L23, L24, L27 |
| **L15** RPC CORRELATION + H1 | `get_commands` via run-unique command id; `evaluate_extension_identity` (sentinel, source kind, extension path == this run's L11 entry); no protocol violation, no `extension_error` | correlation by RPC id on this supervisor only; a prior run's process cannot answer (§19) | `REFUSED_PRE_DISPATCH(RUNTIME_CORRELATION_FAILED)`; closure L21–L27 |
| **L16** H2 + MANIPULATION CHECK | `get_state`; `evaluate_model_identity` (provider/model); §8.2 projection | the prompt is written only to a runtime proven to have loaded this arm's declared shape | `REFUSED_PRE_DISPATCH(CONFIG_SHAPE_MISMATCH \| H2_MISMATCH)`; closure L21–L27 |
| **L17** PRE-DISPATCH BASELINE | capture event counts + `frozenset` of tool-call ids | strictly before the one write (OBS1 §5) | `REFUSED_PRE_DISPATCH`; closure L21–L27 |
| **L18** ONE PROMPT WRITE | `send_command({id, type: "prompt", message: CFG1_T1.prompt})`; `await_response(id, startup_deadline)` → `dispatch_state` | one-shot budget; the transmitted text is the pinned fixture prompt | see §18 rows 4a/4b; continue L19 or closure |
| **L19** TURN OBSERVATION | `await_settled(turn_deadline_seconds)` → `runtime_wait_outcome` | `agent_end` is not completion; `agent_settled` is | continue L20 |
| **L20** Φ4 PROJECTION | OBS1 snapshot (§11.1); stop-reason counts from `sanitized_events` (enum only); `auto_retry_events`; `extension_error_count` | runtime facts frozen into plain values **before** the runtime is torn down | projection failure → activity unavailable; continue |
| **L21** RUNTIME TEARDOWN | `supervisor.shutdown()` ladder on this run's Popen; then bounded wait (`shutdown_deadline_seconds`) for stdout and stderr reader EOF | only the direct child this run launched | failure recorded; continue L22 (§18 row 7) |
| **L22** Φ5 BROKER COUNTS | read accepted read/edit counts, edited-path count, refusal count from this run's `RunState`/diagnostics as ints | after the runtime can send no further frame (or after its teardown was attempted), before the broker is closed | continue |
| **L23** BROKER SHUTDOWN | `server.shutdown(TRIGGER_RUNTIME_SETTLED \| TRIGGER_AIDO_TEARDOWN)` on this instance → lifecycle facts | withdraws the capability; the frozen A/B/C partition owns handle closure | failure recorded; continue L24 |
| **L24** GENERATED MATERIAL SCRUB | verified unlink of `<root>/cfg1_pi_config/models.json` (endpoint-bearing) and `<root>/pi_extension/ar2_config.ts` (token-bearing), each after re-proving root authority and issuance | must precede any execution of model-influenced code (L26), which could otherwise read the endpoint or token | failure recorded; continue L25 |
| **L25** GIT OBSERVATION #1 | re-prove root authority; observe HEAD, status, changed tracked paths, untracked/staged counts; broker↔Git cross-check | read-only AIDO Git after the runtime and broker are closed (O1 precedent) | failure → `git_observation_1_performed=false`; continue |
| **L26** VERIFICATION + GIT OBSERVATION #2 | only if L21, L23 **and** L24 all proved closure: `run_verification(...)` once; project bounded fields; observe Git again | model-influenced code runs only with no live runtime, no live broker, and no endpoint/token on disk | skipped → `verification_skip_reason = LIFECYCLE_UNPROVEN`; continue |
| **L27** WORKSPACE REMOVAL | re-prove root authority (`_verify_root_authority` against the registered authority); `remove_disposable_tree(authority.experiment_root)`; discard registry, claim and issuance records | deletion only of a root this run's registry proves it created | failure recorded; continue L28 |
| **L28** LIFECYCLE FINALIZATION + CLASSIFICATION | compute §17 closure predicates → `lifecycle_all_closed`; compute §12 classification | everything the record needs is now immutable plain data | — |
| **L29** RUN-RECORD EMISSION | **Assemble the run-record payload from now-immutable L28 facts, then invoke `emit_cfg1_run_record(authority, run_ordinal, payload)` — the frozen §16.3.8 ten-step writer sequence and §16.3.8.2's non-recursive fallback/phase semantics, in full, by reference, never re-described here** (synchronized, FU8 Finding 4 — this row is a pointer to that frozen contract, not a duplicate of its algorithm). Covers, by citation rather than restatement: successful emission (`RECORD_EMITTED`, the ordinary case, no §18 row); an eligible `PRE_CREATE` primary failure's one permitted refusal fallback (§18 row 11, non-halting scrub case; §18 row 15, halting self-validation case — §16.3.8.2); a primary-writer collision at `FINAL_PATH_CREATE_ATTEMPTED` (§18 row 12, `EMISSION_COLLISION`); a refusal-writer's own non-collision failure, at any phase, after an eligible fallback was attempted (§18 row 16, `EMISSION_FAILED`, non-recursive); a direct primary-writer failure at or after `FINAL_PATH_CREATE_ATTEMPTED` with **zero** fallback attempts (§18 row 18, FU8/FU9, `EMISSION_FAILED`, non-recursive); and a refusal-writer's own collision at its own `FINAL_PATH_CREATE_ATTEMPTED` (§18 row 19, new FU9 Finding 3, `EMISSION_COLLISION`, identical treatment to row 12) — rows 16 and 18 resolve to the **identical**, deliberately neutral `halt_reason_code` (§19.4 Finding 1), and rows 12/19 resolve to the identical `RUN_RECORD_EMISSION_COLLISION`. **No live reference is ever placed in the payload** (§22); the writer's own authority re-proof, canonicalization, dispatched-validator, authority binding, scrub, and exact-byte-pipeline steps are exactly and only §16.3.8/§16.3.8.1/§16.3.8.2 — this row adds no additional mechanism. **Also (new, FU10): once this ordinal's `ordinal_status` outcome is known, the stage runner's own local code appends it to the stage-progress ledger (§16.3.8.4) — a local-variable write, not a separately-invocable step** | §16.3.8, §16.3.8.1, §16.3.8.2, §16.3.8.4; §22 (the three record-family schemas) | §18 rows 11, 12, 15, 16, 18, 19 |
| **L30** TERMINAL STAGE DECISION | **The first point at which the stage's final disposition for this ordinal is decided** (Finding 4, FU8 — restated explicitly: no admission token is ever issued, and no code path reads or infers an emission outcome, before L29 has fully resolved to one of `RECORD_EMITTED`/`EVIDENCE_REFUSED`/`EMISSION_COLLISION`/`EMISSION_FAILED`, §19.1 item 3; T-101). Compute the in-memory `halt_triggered_by_this_run` fact (§19.1 item 2, never written to the run record, §22.2/§22.3 FU8) from L29's now-known outcome. **Revised to an exact three-way transition (FU10, §19.6):** (A) if any of §19.1 items 1–4 fails, call §19.5's one shared `_resolve_halt_reason_code` over the now-known facts, then invoke the stage runner's own local sealing step (§16.3.8.3, no longer a caller-parameterized function) to seal a **HALTED** `CFG1StageClosureDecision` from the closed-over stage-progress ledger (§16.3.8.4) and the now-known `halted_after_ordinal`/`halt_reason_code`, then invoke `emit_cfg1_stage_closure(authority, decision=…)` with the genuine, sealed result — no admission token is issued; (B) if items 1–4 all hold **and** `k != LAST_ORDINAL(authority.stage_id)` (§19.6), issue the single-use admission token for *k*+1 — no decision is sealed and no stage closure is emitted; (C) if items 1–4 all hold **and** `k == LAST_ORDINAL(authority.stage_id)` (§19.6, new), no admission token is issued (there is no ordinal `LAST_ORDINAL+1`) and the stage runner's own local sealing step instead seals a **SUCCESS** `CFG1StageClosureDecision` (`halted_after_ordinal = null`, `halt_reason_code = null`, every declared ordinal present from the ledger) and invokes `emit_cfg1_stage_closure(authority, decision=…)` exactly as branch A does, with the SUCCESS decision. **The sealing step itself has no reachable name for any code outside this routine to call (§16.3.8.3 Finding 1, FU10) — that, together with this row's own frozen step ordering, is the mechanical proof a decision can never be sealed before this point, under any branch.** No stage-closure payload is ever assembled by hand outside this one call chain, in any of the three branches | §19.1, §19.5, §19.6, §16.3.8.3, §16.3.8.4, §22.4.2 | — |

### 16.3 Stage output authority (FU2, provenance/forgery-closed FU3)

**Finding (FU2).** `stage_execution_id` is supplied by the future live
authorization (§14.1 item 2) and FU1 used it directly to derive a durable
filesystem path (`results/<stage_execution_id>/…`). That makes it a
**caller-controlled value with direct path influence**, not a mere label.
Relying on the operator to choose a well-formed identifier is not a mechanical
closure.

**Finding (FU3).** Closing the identifier alone is not sufficient. Independent
review found two further gaps: proving `execution_directory` is a resolved
child of a *resolved* `RESULTS_ROOT` proves nothing if the lexical
`RESULTS_ROOT` path itself has been redirected — both sides resolve through
the same redirect and a parent/child check still passes (§16.3.2); and calling
`CFG1StageOutputAuthority` "the only source of output paths" was not
mechanically true while ordinary callers could construct one directly with
arbitrary fields, since `frozen=True` prevents mutation but not construction
(§16.3.3). This subsection now closes all three: the identifier (FU2), the
root and directory's own provenance (FU3), and the authority object's
unforgeability plus its continued validity at each point of use (FU3, §16.3.4).

#### 16.3.0 Two different things: package infrastructure vs. one-shot evidence namespace (FU3)

`RESULTS_ROOT` and an execution directory are not the same kind of resource and
must not be reasoned about with the same lifecycle:

| | `RESULTS_ROOT` | execution directory |
|---|---|---|
| Owner | the CFG1 **package** | one **stage** |
| Lifetime | spans every stage this package ever runs, across process invocations | one stage execution; never reused |
| Created | idempotently ensured present (§16.3.2) — creating it when absent is not a security event | exactly once, exclusively (§16.3.6) — creating it when absent **is** the one-shot guarantee |
| "Already exists" | the **expected, ordinary** case on every run after the first | refuses the **entire stage** (§16.3.6) |
| Provenance requirement | re-proven **every time** it is consulted (§16.3.2, §16.3.4), never cached across stages | re-proven **every time** it is consulted (§16.3.4), never cached across consumption points within the stage |

Conflating the two would either (a) make `RESULTS_ROOT`'s ordinary, expected
pre-existence look like a collision, or (b) let an execution directory be
casually re-created/reused like infrastructure. Neither is acceptable; §16.3.2
and §16.3.6 below are deliberately separate mechanisms for this reason.

#### 16.3.1 `stage_execution_id` identifier contract (FU2, unchanged)

Frozen as an **identifier, never a path fragment**:

```text
type(value) is str                          exactly — not a subclass, not
                                             PathLike, not int/bool/None, not
                                             anything with __fspath__ or __str__
grammar     re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value)
```

The alphabet is ASCII uppercase/lowercase letters, digits, `-`, and `_` only —
a small closed positive allowlist, per the phase prompt's own preference. The
length bound (1–64) and the exact alphabet are pinned design constants,
`STAGE_EXECUTION_ID_PATTERN` and `MAX_STAGE_EXECUTION_ID_LENGTH = 64`, tested
by T-16–T-19. FU3 makes no change to this contract: no `PathLike` acceptance,
no normalization, no `strip()`, no caller-selected output path.

Because the alphabet excludes `/`, `\`, NUL, every other control character,
whitespace, and `.` itself, the grammar **mechanically** refuses, with no
separate check needed: `.`, `..`, any absolute Unix path, any Windows
drive-qualified path (`:` is not in the alphabet), any UNC or device form
(`\\`, `\\?\`, `\\.\` all contain `\`), every path separator of either
platform, every control character, and leading/trailing whitespace. **A value
is refused, in full, the instant it fails `type(...) is str` or fails the
`fullmatch` — never normalized, stripped, truncated, or repaired.** `strip()`
is never called on it.

The future `LIVE-S1`/`LIVE-S2` authorization still pins one exact identifier
literal (§14.1). The runtime validator does not trust that the authorization
document is well-formed prose; it independently re-proves the literal belongs
to this grammar before using it for anything.

#### 16.3.2 Fixed results root — provenance, not just resolution (rewritten FU3, package-parent-ordered FU4)

CFG1 has **exactly one** module-owned results root, computed from the module's
own trusted file location — the same `Path(__file__).resolve().parent` idiom
already used throughout this repository's experiment entry points
(`run_ar2.py:40`, `run_o1.py:48`, `run_i2b_live.py:48`,
`run_semantic_sweep_live.py:48`):

```text
_CAPTURED_PACKAGE_DIR   = str(Path(__file__).resolve().parent)  — captured
                                                                   EXACTLY ONCE,
                                                                   at module
                                                                   import (a
                                                                   read, never a
                                                                   write); every
                                                                   later check
                                                                   re-proves
                                                                   THIS captured
                                                                   value, never
                                                                   re-derives
                                                                   Path(__file__)
                                                                   again
expected_results_root  = Path(_CAPTURED_PACKAGE_DIR) / "results"   (lexical
                                                                      join of one
                                                                      fixed
                                                                      literal
                                                                      component
                                                                      — not yet
                                                                      trusted)
```

**The FU2 defect this closes, stated precisely.** FU2's §16.3.5 containment
check compared `RESULTS_ROOT.resolve()` against `(RESULTS_ROOT /
validated_id).resolve()`. If the lexical `results` directory is itself a
symlink or a Windows junction/reparse point to an unrelated location, `.resolve()`
follows that redirect on **both** sides of the comparison — the check proves
"the execution directory is a child of wherever `results` currently points,"
never "`results` still points where CFG1 expects." **`resolve()` returning a
value is never treated as proof that value is the trusted root.**

**The FU3 gap this closes, stated precisely (FU4).** FU3's own state table
admitted "`trusted_package_dir` itself having moved since import" as a
possible cause of an ancestor-level canonical mismatch, but FU3's ordering
still ran `mkdir` on `expected_results_root` (derived from that possibly-moved
parent) **before** ever checking whether the parent had moved. If the parent
had been redirected, `mkdir` could create a **foreign** directory named
`results` under the redirect target, and only the *subsequent* canonical check
would notice — after the write already happened. **Creation authority must
never run ahead of the provenance proof of what it is creating under.**

**Ordering, frozen exactly — two levels, Level A strictly before Level B:**

**Level A — trusted package directory re-proof (new, FU4). Runs before *any*
`RESULTS_ROOT` `mkdir` or any other filesystem write, every single time
`RESULTS_ROOT` is established or re-proven (§16.3.4) — never skipped, never
reordered after Level B:**

```text
a. lex = os.lstat(_CAPTURED_PACKAGE_DIR)                — the CAPTURED string,
                                                            never a fresh
                                                            Path(__file__)
                                                            re-derivation
   (missing / unreadable)          -> refuse PACKAGE_DIR_ABSENT
b. _is_symlink_or_reparse_point(lex)
   (true)                          -> refuse PACKAGE_DIR_REDIRECTED
c. stat_module.S_ISDIR(lex.st_mode)
   (false)                         -> refuse PACKAGE_DIR_NOT_A_DIRECTORY
d. canonical = str(Path(_CAPTURED_PACKAGE_DIR).resolve(strict=True))
   (canonical != _CAPTURED_PACKAGE_DIR)
                                    -> refuse PACKAGE_DIR_NOT_CANONICAL
```

This is the **identical four-step shape** as Level B below, applied one level
up, checked against the value captured once at import rather than a fresh
re-derivation — which is exactly what makes it a genuine re-proof rather than
a tautology: if an **ancestor** of `_CAPTURED_PACKAGE_DIR` (not the leaf
itself) has been redirected since import, step (a)–(c) can still see an
ordinary, non-reparse leaf directory, but step (d)'s `resolve(strict=True)`
walks and resolves that now-redirected ancestor and returns a **different**
canonical path than the captured one — caught identically to a leaf-level
redirect, never adopted as "close enough" (mirrors §16.3.2 Level B's own
ancestor-mismatch handling, restated here because it is the load-bearing
mechanism for exactly this class of attack).

**Only if all four of Level A pass does Level B ever run:**

**Level B — `RESULTS_ROOT` establishment and provenance (FU3, unchanged in
mechanism, now correctly ordered after Level A):**

1. **Ensure presence (infrastructure step, not a security event).**
   `expected_results_root.mkdir(parents=False, exist_ok=True)`. This may create
   the directory (first run ever) or be a silent no-op (every later run) — it
   draws **no** security conclusion either way, because `exist_ok=True`
   follows a symlink when deciding whether the target already "is a
   directory," so a symlink redirect would also make this step a silent no-op.
   That is exactly why step 2 always runs regardless of what step 1 did.
2. **Provenance proof — unconditional, every single time `RESULTS_ROOT` is
   established or re-proven (§16.3.4), never skipped because step 1 was a
   no-op:**

   ```text
   a. lex = os.lstat(str(expected_results_root))          — never follows a
                                                              final symlink
      (missing / unreadable)          -> refuse RESULTS_ROOT_ABSENT
   b. _is_symlink_or_reparse_point(lex)                    — imported from
      ai_dev_orchestrator.workspace.canonical (§7.4), exactly as
      ar2/capability.py:39 already does; checks POSIX S_ISLNK AND the Windows
      reparse-point attribute/tag
      (true)                          -> refuse RESULTS_ROOT_REDIRECTED
   c. stat_module.S_ISDIR(lex.st_mode)
      (false)                         -> refuse RESULTS_ROOT_NOT_A_DIRECTORY
   d. canonical = str(Path(expected_results_root).resolve(strict=True))
      (canonical != str(expected_results_root))
                                       -> refuse RESULTS_ROOT_NOT_CANONICAL
   ```

   Only if **all four** pass is `expected_results_root` treated as the trusted
   `RESULTS_ROOT` for this call. Step (d) is what makes "resolves somewhere
   other than its expected lexical location" mechanically refuse rather than
   silently adopt the resolved target — a lexical/resolved mismatch after (b)
   has already ruled out the leaf itself being a reparse point can only mean an
   ancestor-level anomaly (e.g. a case or 8.3-short-name mismatch on Windows),
   and it is refused identically, never treated as "close enough." (Level A
   already independently rules out `_CAPTURED_PACKAGE_DIR` itself as the
   source of such an anomaly, so a Level-B-only ancestor mismatch at this
   point means the redirect sits strictly between the package directory and
   `results/` — impossible for a single-component join, but the check remains
   as defense in depth.)

**Frozen semantics, the complete state table (all seven prompt-listed states,
now gated by Level A first):**

| State | Outcome |
|---|---|
| package directory itself absent/redirected/non-canonical | Level A refuses (`PACKAGE_DIR_*`) — **before** `RESULTS_ROOT` is even considered (T-43) |
| root absent | Level A passes; Level B step 1 creates it; step 2 then proves it (ordinary first-run path) |
| root is a normal directory | Level A passes; step 1 no-ops; step 2 passes — accepted |
| root is a symlink | Level A passes; step 2(b) refuses `RESULTS_ROOT_REDIRECTED`, **before** any execution directory is ever derived from it |
| root is a junction/reparse redirect | Level A passes; step 2(b) refuses `RESULTS_ROOT_REDIRECTED` identically (the Windows attribute/tag branch of `_is_symlink_or_reparse_point`) |
| root resolves somewhere other than its expected lexical location | Level A passes; step 2(d) refuses `RESULTS_ROOT_NOT_CANONICAL` |
| root is a file | Level A passes; step 1's `mkdir` itself raises `FileExistsError` (a file is not a directory, so `exist_ok=True` does not suppress it) **and**, defensively, step 2(c) would independently refuse `RESULTS_ROOT_NOT_A_DIRECTORY` if that first defense were ever bypassed |
| root is otherwise non-canonical (e.g. a case or short-name alias) | Level A passes; step 2(d) refuses `RESULTS_ROOT_NOT_CANONICAL` |

**Root-presence contract, stated explicitly (per the phase prompt's requirement
not to leave this ambiguous): CFG1 is allowed to create `RESULTS_ROOT` when
absent, exactly via Level B step 1 above, and that creation authority is
trivial and unconditional** (an idempotent `mkdir`) **because it now runs only
after Level A has already proven the parent it is creating under, and is
itself followed, every time, by Level B's own unconditional provenance proof
— creation authority never runs ahead of a provenance proof at either level.**
No CFG1-IMPL variant may pre-create `results/` as packaged fixture content
instead — the design freezes the create-then-prove ordering, not a "must
already exist" precondition, so the offline implementation fixture must
exercise both the first-run (absent) and every-later-run (present) paths
through the identical sequence, at both levels.

No CLI flag, function parameter, environment variable, or config file may
select or replace `RESULTS_ROOT` or `_CAPTURED_PACKAGE_DIR`. Neither is part of
the stage authorization's vocabulary.

#### 16.3.3 `CFG1StageOutputAuthority` — mint-registry provenance, not a bare dataclass (rewritten, FU3)

**The FU2 defect this closes, stated precisely.** `frozen=True` proves that,
once an instance exists, its fields cannot be reassigned. It proves nothing
about *how* the instance came to exist: any caller holding the class could
construct `CFG1StageOutputAuthority(stage_id="S1", stage_execution_id="X",
execution_directory="C:\\anything")` directly, and nothing in FU2's text
stopped that value from being accepted downstream. "The only constructor" was
a documentation claim, not a mechanical one.

**Mechanism: a process-local mint registry, mirroring the already-accepted
shape of `qualification.i2b_workspace._MINTED` /
`QualificationRunWorkspace.__post_init__`** (§1.1; new, CFG1-owned code
following that precedent, not an import of it — no frozen module is touched):

```text
_STAGE_OUTPUT_MINTED: dict[str, _StageOutputMintRecord]     # process-local,
                                                             # in-memory only,
                                                             # never persisted

_StageOutputMintRecord (frozen):
    stage_id, stage_execution_id, results_root, execution_directory   — the
    authoritative, freshly-proven values recorded at the moment of minting

CFG1StageOutputAuthority (frozen):
    mint_nonce            str = field(repr=False)     # 128-bit, secrets.token_hex(16)
    stage_id              str
    stage_execution_id    str
    results_root          str
    execution_directory   str

    def __post_init__(self):
        record = _STAGE_OUTPUT_MINTED.get(self.mint_nonce)
        if record is None:
            raise ... UNKNOWN_MINT_NONCE
        if (record.stage_id, record.stage_execution_id,
            record.results_root, record.execution_directory) != \
           (self.stage_id, self.stage_execution_id,
            self.results_root, self.execution_directory):
            raise ... MINT_FIELD_MISMATCH
```

`mint_nonce` is `field(repr=False)`, exactly matching
`i2_pi_config.GeneratedQualificationConfig.authority_token`'s precedent (§1.1):
**never written to disk, never shown in any repr/diagnostic/evidence, and
never read by the run-record, refusal-record, or stage-closure-record
builders.** It is in-memory authority only.

`establish_stage_output_authority(*, stage_id, stage_execution_id) ->
CFG1StageOutputAuthority` is the **only supported path to a genuine instance**,
called **exactly once** at stage start, before ordinal 1:

1. validates `stage_id` against the closed `{"S1", "S2"}` domain;
2. validates `stage_execution_id` per §16.3.1 and §16.3.4's single-read
   binding;
3. establishes `RESULTS_ROOT` per §16.3.2 (creates-if-absent, then
   unconditionally proves provenance);
4. derives `execution_directory` as `RESULTS_ROOT / <validated id>` (a
   `pathlib` join of one already-separator-free component — never string
   concatenation) and proves containment (§16.3.5) against the now-proven
   `RESULTS_ROOT`;
5. proves the directory is currently absent, then creates it exactly once
   (§16.3.6), and immediately re-`lstat`s the freshly created directory to
   confirm it is a real directory and not a reparse point (closes a same-tick
   creation race under adversarial testing, T-30);
6. mints: generates `mint_nonce`, registers a `_StageOutputMintRecord` with
   the four proven values, then constructs and returns the
   `CFG1StageOutputAuthority`.

**Direct construction cannot authorize anything.** A caller who instantiates
`CFG1StageOutputAuthority(...)` with any nonce it did not receive from
`establish_stage_output_authority` — including an empty string, a guessed
value, or a nonce copied from a genuine object alongside substituted fields —
fails `__post_init__`'s registry lookup or its field-equality check, **before**
the object exists at all (T-25, T-26, T-27).

Every run/stage output path for the rest of the stage is a **pure function**
of this one object plus a schedule ordinal — never of a fresh string, a
caller-supplied filename, a caller-supplied `arm_id`, or a second read of
anything external. **The exact writer-boundary shape (no path parameter
anywhere, and the arm derived internally from the ordinal rather than accepted
from a caller) is specified in full in the new §16.3.8** — FU2/FU3 described
this as `run_record_path(authority, run_ordinal, arm_id)`, a signature that
still let a supported caller choose `arm_id` independently of the frozen
schedule; FU4 closes that (§16.3.8, Finding 2) and additionally removes any
public path-returning function at all, replacing it with writer functions that
derive and consume a path entirely internally (§16.3.8, Finding 1).

**No authority token or nonce is persisted to prove the path.** Filesystem
authority is exclusively an in-memory property of holding one genuinely-minted,
**still-ACTIVE** (§16.3.9) `CFG1StageOutputAuthority` instance; the durable
record (§22) carries `stage_execution_id`, `stage_id`, `run_ordinal`, and
`arm_id` as **identity facts**, and the validator re-derives the expected
filename from them with the same pure schedule-arm/filename function — it
never reads a stored authority object back, and it never needs `mint_nonce`
(§22.3).

#### 16.3.4 TOCTOU/type closure, and consumption-boundary re-proof (extended, FU3)

**Single-read type closure (FU2, unchanged).** `stage_execution_id` is read
from the authorization **exactly once**, into one local binding, at the moment
`establish_stage_output_authority` validates it. That validated binding — not
a property, not a `Mapping.__getitem__` result re-queried later, not a
caller-held mutable object — is what the frozen
`CFG1StageOutputAuthority.stage_execution_id` field stores. Because validation
requires `type(value) is str` exactly, the accepted value is an ordinary
immutable Python `str`, which cannot change after that check passes; there is
nothing further for a TOCTOU gap to exploit at the identifier itself. Rejected
before any filesystem access, by the same `type(...) is str` gate:
`pathlib.Path`, any object implementing `__fspath__`, a `str` subclass (whose
`__eq__`/`__str__` could disagree with its true content), `int`, `bool`,
`None`, and any Mapping/object wrapper (T-19).

**Consumption-boundary re-proof (new, FU3).** A validated object is not trusted
forever. The prompt's own instruction is exact: "Do not validate output
authority only once at stage start and then trust a Python object forever."
`verify_stage_output_authority(authority) -> None` (raises on any failure) is
called as the **unconditional first action** of every `emit_cfg1_*` writer
(§16.3.8) and of every other function that derives or consumes a stage-output
path. **There is no public path-returning helper of any kind (FU4/FU5): a
writer takes only an authority, a schedule ordinal, and a payload, re-proves
the authority itself as literally its first step, and derives its own output
path internally afterward (§16.3.8) — no bare path or filename value ever
crosses the writer's public boundary, in either direction.** This function
performs, fresh, every time:

1. `type(authority) is CFG1StageOutputAuthority` exactly — refuses a
   lookalike/subclass;
2. re-look-up `_STAGE_OUTPUT_MINTED.get(authority.mint_nonce)`; refuse
   `UNKNOWN_MINT_NONCE` if absent — **this refusal is also what a retired
   authority produces** (§16.3.9): retirement is registry removal, so a
   post-retirement lookup is indistinguishable from, and refused identically
   to, a nonce that was never issued at all;
3. re-compare **all four** bound fields (`stage_id`, `stage_execution_id`,
   `results_root`, `execution_directory`) against the registry record; refuse
   `MINT_FIELD_MISMATCH` on any disagreement — this is what catches a genuine,
   correctly-minted object whose fields were mutated after construction via a
   frozen-dataclass bypass (`object.__setattr__`), not merely a forged nonce
   (T-27);
4. re-establish `RESULTS_ROOT` provenance from scratch — **both levels**,
   Level A (the package-parent re-proof, §16.3.2) strictly before Level B (the
   `RESULTS_ROOT` proof itself), never a cached result of either — catches the
   package directory or `results/` itself being redirected mid-stage;
5. re-`lstat` `authority.execution_directory`: require it exists, require
   `_is_symlink_or_reparse_point` is false, require `S_ISDIR`, require
   `resolve(strict=True)` equals itself (canonical), require its resolved
   parent equals the just-re-proven `RESULTS_ROOT`, and require its basename
   equals `authority.stage_execution_id` — catches the execution directory
   itself being deleted-and-replaced-by-a-symlink/junction after the mint
   (T-28).

Only after all five steps pass does the caller proceed. This is deliberately
**not** a defense against arbitrary same-user concurrent memory corruption
(the phase prompt explicitly excludes that); it is a defense against ordinary
filesystem tampering occurring **between** lifecycle steps — a deletion, a
rename, a symlink swap — which is exactly the class of event that must fail
closed at the next consumption point rather than silently succeed against
whatever now occupies the path.

**Correction (FU4).** An earlier revision of this subsection called mint-registry
discard at stage end "pure memory hygiene, never a security boundary." That
was wrong: `CFG1StageOutputAuthority`'s declared lifetime is **one stage**, and
while its `_STAGE_OUTPUT_MINTED` entry remains registered, a genuine,
unmutated authority object from a stage that has already ended would still
pass every check in this subsection and could still derive a path. Retirement
— removing that entry — **is** a security boundary, and its exact timing is
frozen in §16.3.9.

#### 16.3.5 Containment proof — not lexical concatenation (unchanged reasoning, now sits after a proven root)

Before creation, the design requires a **structural** proof that
`execution_directory` is the immediate child `RESULTS_ROOT` was meant to gain,
not merely that its string happens to start with the right prefix. This
repository already establishes the idiom for exactly this shape of proof —
`qualification/semantic_workspace.py:302`, in the frozen
`populate_semantic_task_workspace`, refuses a target unless
`repo not in target.resolve().parents and target.resolve() != repo`. CFG1
follows the identical technique with its own values, as **new, CFG1-owned
code** — it does not call or import that frozen function, so no frozen module
is touched:

```text
resolved_root  = RESULTS_ROOT.resolve()          # RESULTS_ROOT is already
                                                  # §16.3.2-proven canonical and
                                                  # non-redirected at this point
resolved_exec  = (RESULTS_ROOT / validated_id).resolve()

require: resolved_root in resolved_exec.parents      (structural parent proof)
require: resolved_exec.parent == resolved_root       (immediate-child proof,
                                                        not merely an ancestor)
require: resolved_exec != resolved_root
```

**This check's soundness now depends on §16.3.2 having already run first** —
FU2's version of this check ran against a merely-`.resolve()`d root, which a
redirected root would pass just as easily as a genuine one (§16.3.2's Finding).
With §16.3.2's provenance proof as a precondition, `resolved_root` is known
non-redirected before this comparison is ever made, so a subsequent redirect
of the leaf `execution_directory` path specifically (rather than `results/`
itself) is the only remaining case this check plus §16.3.6's exclusive-create
must handle — and `mkdir(exist_ok=False)` refuses unconditionally when
anything (file, directory, or symlink) already occupies that exact path, so a
pre-placed symlink at the execution-directory location is refused by §16.3.6
without needing a separate check here.

Combined with §16.3.1's grammar (which already guarantees `validated_id`
contains no separator, so the `pathlib` join cannot itself escape
`RESULTS_ROOT`), this proves the derived path relationship mechanically rather
than asserting it from the join alone. This uses only the Python standard
library `pathlib` already used throughout the codebase for this purpose —
**no new generic filesystem-authority framework is introduced**, and none is
needed: the check is two path objects and three comparisons, owned entirely by
the CFG1 module.

#### 16.3.6 Existing-directory behavior (unchanged; now explicitly distinct from §16.3.2's root)

```text
execution_directory absent   -> create exactly once (mkdir, parents=False,
                                  exist_ok=False), at stage start, before
                                  ordinal 1 is admitted
execution_directory exists   -> REFUSE THE ENTIRE STAGE before any run;
                                  existing content is never read, merged,
                                  appended to, or deleted
```

**This is deliberately the opposite policy from `RESULTS_ROOT`'s §16.3.2 step 1
(§16.3.0):** the root's existing-directory case is the ordinary path taken on
every run after the first; the execution directory's existing-directory case
is always a refusal, because an execution id is a one-shot namespace by
design, never reused across stage executions.

`mkdir(..., exist_ok=False)` is itself the exclusive-create primitive (the
same discipline `ar2.fixtures.create_disposable_experiment_root`'s marker file
and `qualification.safety.write_evidence_exclusively` already use for their
own artifacts): a `FileExistsError` it raises **is** the mechanical proof of
collision, not a race the design papers over. There is no reuse, no merge, no
alternate name, no timestamp fallback, and no deletion of a pre-existing
directory, whatever it contains. An existing per-run record or the
stage-closure record remains an ordinary exclusive-create collision exactly as
§18 row 12 and §17 already specify — unchanged by this subsection, since both
already derive their path from this same authority.

#### 16.3.7 A stage-output authority failure is a hard stop, not an ordinary halt (new, FU3)

Every other halt case in this design (§19.2) writes a stage-closure record
before stopping. A stage-output authority failure — at establishment (§16.3.2,
§16.3.3) or at any later consumption-boundary re-proof (§16.3.4) — **cannot**
follow that pattern: the very location a stage-closure record would need is
what has just failed provenance. Writing into it would be either impossible
(if genuinely absent) or actively unsafe (if redirected to an attacker-
influenced location). The design therefore freezes a narrow, explicit
exception:

- **the authority is retired immediately upon detecting the failure — before
  console reporting even (§16.3.9)** — so that however execution proceeds
  afterward, no code path can use that mint again;
- **nothing is written to `results/`** — not a run record, not a refusal
  record, not a stage-closure record;
- the failure is reported **only** via the console channel (§21.2), with one
  of the closed codes from §16.3.2/§16.3.3/§16.3.4, and the process terminates;
- any run records genuinely written **before** the failure was discovered
  remain on disk, untouched and individually trustworthy (they were written
  while `RESULTS_ROOT`/the execution directory were still proven-good) — the
  stage is simply left without a stage-closure record, which is itself the
  observable signal that something ended abnormally;
- resumption requires a new authorization exactly as any other halt does
  (§14.1 item 4), and that new authorization's operator is expected to
  investigate the console-reported cause before choosing a new
  `stage_execution_id`.

This is the **only** carve-out from §19.2's "always write a stage-closure
record on halt" rule, and it exists only because durable evidence cannot
authorize or prove its own container's trustworthiness (§22.5).

#### 16.3.8 Writer consumption boundary — no path parameter, no caller-selected arm, canonicalize-then-bind (new FU4, ordering/binding closed FU5)

**Finding 1, stated precisely.** FU2/FU3's text said record/refusal/
stage-closure writers "consume only a path previously returned by
`run_record_path`/`stage_closure_path`." That is caller convention, not a
mechanical invariant: once a helper returns a path value, it is an ordinary
string or `Path` indistinguishable from any other — nothing stops a writer
function from being called with a hand-built path instead. **A helper-returned
bare path is never treated as an authority token.**

**Finding 2, stated precisely.** Even granting the previous point, the FU2/FU3
conceptual signature `run_record_path(authority, run_ordinal, arm_id)` still
took `arm_id` as an independent parameter — a supported caller could call it
with the correct `run_ordinal` and a *different* `arm_id` than the frozen
schedule assigns to that ordinal, producing a filename that looks legitimate
but names the wrong arm.

**The fix to both: the only public API is a small set of writer functions,
none of which accepts a path, filename, directory, `results_root`,
`execution_directory`, or `arm_id` as an independent argument.** Conceptually:

```python
emit_cfg1_run_record(authority, *, run_ordinal, payload) -> EmissionResult
emit_cfg1_refusal_record(authority, *, run_ordinal, refusal_payload) -> EmissionResult
emit_cfg1_stage_closure(authority, *, decision) -> EmissionResult
```

Exact names/decomposition are implementation discretion; the boundary is not.
**`emit_cfg1_stage_closure`'s signature is revised (new, FU9, §16.3.8.3):
`decision` replaces `payload`.** It accepts a genuine, sealed, CFG1-owned
`CFG1StageClosureDecision` — never a caller-supplied `payload` dict for the
stage-decision facts (`ordinal_status`, `halted_after_ordinal`,
`halt_reason_code`) — because internal self-consistency of a caller-supplied
payload is not provenance that the payload equals the actual L30 decision
(Finding 1, FU9). The two run-scoped writers are unaffected; they continue
to accept a caller-supplied `payload`/`refusal_payload`, because their own
identity/binding checks (step 7 below) were always sufficient for their own
domain — the stage-closure writer is the one place a supported caller could
otherwise construct a schema-valid, self-consistent, but factually
**invented** closure record while holding nothing more than a genuine ACTIVE
authority.

**Finding 5 (FU6), stated precisely.** These three writer functions were
described, from FU4 onward, as each running "the full §22.1–§22.3 payload
validator" (this subsection's own step 6, pre-FU6). §22.1–§22.3 is a schema
defined for exactly one `record_version` literal,
`pi-harness-cfg1-run.v1`. `emit_cfg1_refusal_record` and
`emit_cfg1_stage_closure` write payloads carrying `pi-harness-cfg1-refusal.v1`
and `pi-harness-cfg1-stage-closure.v1` respectively — different closed key
sets, different literals, different cross-field invariants — so a writer
literally running "the" run-record validator against a refusal or
stage-closure payload would refuse every genuine instance of either kind.
**Three durable record kinds require three independent, closed payload
validators**, conceptually `_require_valid_cfg1_run_payload`,
`_require_valid_cfg1_refusal_payload`, and
`_require_valid_cfg1_stage_closure_payload` — exact names are implementation
discretion, the existence of three separate, non-wrapping validators is not
(§22.1 for the run-record schema, new §22.4.1 for the refusal-record schema,
new §22.4.2 for the stage-closure schema, and §22.4.3 for the no-wrapper
requirement and the dispatch rule this implies for the read-only
run-artifact verifier, §22.5.2 Step 3). Step 6 below is corrected
accordingly.

**Finding 3 (FU5), stated precisely.** The FU4 draft of this sequence
cross-checked `payload["arm_id"]` (step 4 of that draft) **before** the
payload had been type-gated and canonicalized. That reads a caller-supplied
object's field before the same TOCTOU discipline this design applies
everywhere else (§16.3.4's identifier binding, §22.1 item 6's write-side
snapshot, §22.5.2's read-side snapshot) had even started — a hostile
`Mapping`, a `dict` subclass, or an object whose `__getitem__` answers
differently on a second call could influence step 4's decision using a value
that never survives into the canonical snapshot the rest of the sequence
actually acts on. **No payload field may be accessed before canonicalization
completes.**

**Finding 4 (FU5), stated precisely.** Internal payload self-consistency is
not enough: a canonical payload can have `stage_id`, `arm_id`, and
`record_filename` all agreeing *with each other* while still belonging to a
**different** stage execution than the one the writer is currently minted
for. The writer must independently bind the canonical payload to **its own**
authority and schedule identity — not merely validate the payload in
isolation (§22.1–§22.3 already does that, and remains necessary but is no
longer sufficient at the writer boundary).

**The frozen ten-step sequence — the two run-scoped writers, every time
either is called, no step skipped or reordered. The stage-closure writer
follows an adapted sequence, steps 1–7 replaced by §16.3.8.3's decision-based
equivalent (new, FU9) and steps 8–10 unchanged — see §16.3.8.3:**

1. `verify_stage_output_authority(authority)` (§16.3.4) — including the
   ACTIVE check of §16.3.9. Refuses before touching `run_ordinal` or
   `payload` at all. (The stage-closure writer performs the identical check
   as the first action of §16.3.8.3's own sequence.)
2. **Validate/derive schedule identity from trusted arguments only —
   `authority` and `run_ordinal`, never `payload`.** For the two run-scoped
   writers: `type(run_ordinal) is int` exactly (`bool` is an `int` subclass
   and is explicitly rejected — `True`/`False` are never accepted as an
   ordinal), `run_ordinal` within `authority.stage_id`'s exact declared range
   (`1..9` for `S1`, `1..6` for `S2`); anything else refuses before any
   lookup (T-41). Then `arm_id = _schedule_arm_for(authority.stage_id,
   run_ordinal)` — the **one**, frozen, module-level schedule constant,
   derived internally; there is no parameter through which a caller supplies
   an arm (T-40, T-42). (Not applicable to the stage-closure writer, which
   carries no `run_ordinal`/arm identity, unchanged from FU4.)
3. `type(payload) is dict` exactly (the analogous run-scoped parameter is
   `refusal_payload` for `emit_cfg1_refusal_record`) — **not** `isinstance`,
   **not** a `Mapping` acceptance, **no** coercion. Anything else refuses
   immediately, with **zero** payload-field reads having occurred (T-55).
   (Not applicable to the stage-closure writer as of FU9 — it has no
   caller-supplied `payload` parameter at all; §16.3.8.3 step 2's `decision`
   type-gate is its analogue.)
4. **Canonicalize exactly once**: `canonical = json.loads(json.dumps(payload))`,
   inside `try`/`except Exception`, mapping any failure (non-serializable
   value, pathological nesting, anything else) to a bounded refusal with no
   exception text retained (T-56). This is the **first** point at which any
   field of the caller's payload is read at all. (Not applicable to the
   stage-closure writer as of FU9 — §16.3.8.3 step 5 builds `canonical`
   directly from the already-immutable, already-verified `decision`'s own
   fields; there is no caller payload to canonicalize.)
5. **`payload` — the original argument — is never read again from this line
   on.** Every remaining step reads only `canonical`. A hostile object that
   would answer differently on a second read has no second read to answer
   (T-57). (Not applicable to the stage-closure writer as of FU9, for the
   same reason as step 4 — `decision` is CFG1-owned and immutable, not a
   caller-supplied mutable object this discipline needs to guard against.)
6. **Run the payload validator for this writer's own artifact kind — never a
   shared generic call (Finding 5, FU6).** `emit_cfg1_run_record` runs
   `_require_valid_cfg1_run_payload` (§22.1–§22.3); `emit_cfg1_refusal_record`
   runs `_require_valid_cfg1_refusal_payload` (§22.4.1);
   `emit_cfg1_stage_closure` runs `_require_valid_cfg1_stage_closure_payload`
   (§22.4.2) **against the `canonical` it built itself from `decision` in
   §16.3.8.3 step 5, never against caller input** (revised, FU9). Each
   independently enforces closed keys, exact literals, exact types, closed
   enumerations, and every cross-field invariant of its own exact schema;
   none is a wrapper that merely skips the run-record checks that do not
   apply to it (§22.4.3). Any failure refuses. **This step alone proves only
   schema validity — closed keys, exact literals/types, internal
   cross-field coherence — never that the payload equals the genuine L30
   decision** (Finding 5, FU9, §22.4.2/§22.5.1): for the two run-scoped
   writers that stronger provenance comes from step 7's authority binding
   below; for the stage-closure writer it comes from §16.3.8.3's decision
   authenticity checks, which already ran before this step.
7. **Bind the canonical snapshot to the writer's own authority/schedule
   identity — the enforcement boundary Finding 4 requires, run against
   `canonical`, never against `payload`:**

   | Writer | Required equalities (any mismatch refuses, before any write) |
   |---|---|
   | `emit_cfg1_run_record` | `canonical["stage_id"] == authority.stage_id`; `canonical["stage_execution_id"] == authority.stage_execution_id`; `canonical["run_ordinal"] == run_ordinal`; `canonical["arm_id"] == arm_id` (step 2's derived value); `canonical["record_filename"] ==` the filename internally derived (step 9) for that same `authority.stage_id` / `run_ordinal` / derived `arm_id` |
   | `emit_cfg1_refusal_record` | the same identity fields the refusal record retains — `stage_id`, `stage_execution_id`, `run_ordinal`, `arm_id` — bound identically to `authority`/`run_ordinal`/`arm_id`, plus its internally derived run-artifact filename bound the same way. **A refusal record cannot claim a different stage execution than the authority under which it is written.** |
   | `emit_cfg1_stage_closure` | **revised, FU9 — see §16.3.8.3 for the full sequence.** `canonical` is no longer built from a caller-supplied payload at all; it is built by the writer itself from `authority` and a genuine, sealed `decision` (§16.3.8.3 steps 1–4, which run **before** this step and subsume it: decision authenticity, exactly-once sealing, and authority-rebinding checks are decision-side gates, not payload-field equalities). The equalities below hold **by construction**, not by checking caller input, and are retained here only as the same defensive re-assertion every other writer performs: `canonical["stage_id"] == authority.stage_id`; `canonical["stage_execution_id"] == authority.stage_execution_id`; filename bound to the **one** stage-closure filename internally derived from `authority` (no `run_ordinal`/`arm_id` — a stage-closure record carries no arm identity) |

   **No payload is trusted merely because its own fields agree with one
   another** — every equality above compares against the writer's own
   `authority`/`run_ordinal`/derived-`arm_id`, never against another field of
   the same payload.
8. **Scrub** the canonical snapshot via `qualification_scrub_check`, then
   **serialize it exactly once** to `artifact_bytes` (§16.3.8.1's one emission
   pipeline), and enforce the artifact-size bound against `len(artifact_bytes)`
   — the identical bound the verifier applies on read, so a writer can never
   produce an artifact the verifier's own bounded read would truncate.
9. Derive the output filename internally — `f"{authority.stage_id}_
   {run_ordinal:02d}_{arm_id}.json"` for a run/refusal record,
   `f"{authority.stage_id}_stage_closure.json"` for the stage-closure record —
   and the full path as `authority.execution_directory / <that filename>`;
   **this derivation is never exposed as a return value a caller can capture
   and pass elsewhere.**
10. **Exclusive-create exactly that internally-derived path, then write, then
    flush, then close — four distinct sub-actions, not one atomic step
    (phase vocabulary frozen in §16.3.8.2, FU7).** Writing **exactly
    `artifact_bytes`** — the same bytes step 8 already size-checked, never a
    fresh re-serialization of `canonical` at write time (or, on a bounded
    pre-create failure at any of steps 1–9, the CFG1-owned refusal record's
    own `artifact_bytes`, produced by the identical one-serialization
    pipeline — never the caller's original `payload`; §16.3.8.2 governs
    exactly when this fallback is eligible), and nothing else. **Entering
    this step's exclusive-create call is itself the boundary past which no
    refusal fallback may ever be attempted at this run path, regardless of
    how this step's own create/write/flush/close subsequently resolves** —
    see §16.3.8.2 for the exact phase names and the residue policy that
    follows from crossing that boundary.

#### 16.3.8.1 Artifact-size bound, applied identically at write and verify (FU5, byte pipeline pinned FU6)

**One exact emission-bytes pipeline (Finding 4, FU6), no second
serialization:**

```text
canonical object (the step-4 snapshot)
    ↓
serialize ONCE to artifact_bytes         (deterministic UTF-8 JSON; the same
                                           `json.dumps(canonical, ...)` call
                                           whose output is used for every
                                           later purpose — never re-invoked)
    ↓
size-check len(artifact_bytes)           (step 8 above)
    ↓
exclusive-create the internally-derived path   (step 9 above)
    ↓
write EXACTLY artifact_bytes             (step 10 above)
```

The serialization format itself remains an internal implementation choice —
deterministic UTF-8 JSON is preferred — but whatever format is chosen, the
**same produced byte string** is what is size-checked and what is written.
**No second serialization of `canonical` occurs anywhere after the size
check.** An implementation that calls `json.dumps` a second time at write
time — even with the same arguments, even if it is expected to produce
identical bytes — violates this pipeline, because "expected to produce
identical bytes" is exactly the assumption FU6 closes: whitespace, key
ordering, or escaping could diverge between two separate serialization calls
for reasons as mundane as a dict-ordering change elsewhere in the process,
and a writer that reserializes could then write bytes the already-passed size
check never actually measured.

**`MAX_CFG1_ARTIFACT_BYTES` is pinned at the exact integer `65536` (Finding 4,
FU6)** — not "e.g. 64 KiB," not a value left to implementation discretion.
65536 is generous relative to this design's small, closed-schema records
(§22.2's run-record field set, and the smaller refusal- and
stage-closure-record schemas of §22.4.1/§22.4.2) while remaining a strict,
asserted bound; if source inspection at implementation time proves 65536
cannot hold a genuine instance of one of the three schemas, that is a
re-review trigger (mirroring §7.5's mismatch handling), not license to raise
the constant silently. The constant is defined once and consumed at **both**
boundaries:

- **write (step 8 above):** `len(artifact_bytes)` is checked against
  `MAX_CFG1_ARTIFACT_BYTES` before the exclusive-create; a violation refuses
  (unreachable in practice given the closed schema, but asserted rather than
  assumed);
- **verify (§22.5.2):** the artifact is read with a **bounded** read — at most
  `MAX_CFG1_ARTIFACT_BYTES + 1` bytes requested; if that many bytes come back,
  the file exceeds the bound and the verifier refuses (`False`) without
  reading further.

This is not a new, independently-invented limit competing with an existing
one: nothing elsewhere in this design already bounds a CFG1 artifact's byte
size, so this is the **one** place such a bound is declared, and both
consumers cite the same constant rather than each inventing their own. The
same pipeline and the same constant apply identically to all three record
kinds — run, refusal, and stage-closure — since all three are written by a
writer that follows the same ten-step sequence (§16.3.8).

Regressions: T-70 (65536 accepted), T-71 (65537 refused), T-72 (the exact
bytes checked for size are the exact bytes written, for all three record
kinds).

**The same schedule-arm derivation, used everywhere, by identity.**
`_schedule_arm_for(stage_id, run_ordinal)` is the **one** function called by:

```text
L0 admission           — to compute the expected record path for the absence
                          check (§16.2), using the same function, never a
                          separately-reimplemented lookup
payload construction    — the pipeline that builds a run record's payload
                          populates payload["arm_id"] by calling this same
                          function, so a correctly-behaving pipeline's payload
                          already agrees with step 7 above by construction —
                          step 7 is the enforcement boundary, not merely a
                          sanity check on a value nothing else could get wrong
the writer               — step 2 above
the record validator     — §22.3's "record_filename equals … derivation …
                          from (stage_id, run_ordinal, arm_id)" now names this
                          exact function
the artifact-binding
verifier                 — §22.5.2's "agrees with the frozen schedule
                          constant" step now names this exact function
```

No site re-implements the lookup independently. T-42 proves this by identity
(asserting the same underlying callable is what each call site invokes), not
merely by re-deriving the same numbers in five places and hoping they never
drift apart.

**The complete consumption-boundary chain, frozen end to end (FU4, step
numbers updated FU5):**

```text
trusted package directory re-proved              (§16.3.2 Level A)
    ↓
RESULTS_ROOT established + re-proved             (§16.3.2 Level B)
    ↓
execution directory exclusively created + re-proved   (§16.3.5, §16.3.6)
    ↓
ACTIVE stage authority minted                    (§16.3.3, §16.3.9)
    ↓
writer receives authority + schedule ordinal + payload  (this subsection)
    ↓
writer re-proves ACTIVE authority                (step 1)
    ↓
writer derives schedule identity from trusted args     (step 2)
    ↓
writer type-gates, then canonicalizes payload ONCE     (steps 3-5)
    ↓
writer validates canonical snapshot              (step 6)
    ↓
writer binds snapshot to authority/schedule identity   (step 7)
    ↓
writer scrubs + size-bounds                      (step 8)
    ↓
writer derives schedule-bound filename itself    (step 9)
    ↓
exclusive create                                 (step 10)
    ↓
final stage write
    ↓
authority retired                                (§16.3.9)
```

**No ordinary string or path value ever substitutes for authority at any point
in this chain, and no payload field is ever read before its one
canonicalization.** Every arrow is a function call carrying the authority
object (or, at the two ends, values proven canonical in-place), never a
previously-returned path handed forward as if it were itself a credential.

#### 16.3.8.2 Non-recursive fallback semantics, and the emission-phase boundary (new, FU6; phase boundary corrected FU7)

**Finding 3, stated precisely (FU6).** §18 row 11's rule — "on scrub failure,
the CFG1-owned refusal record may be written" — is stated for the **primary
run artifact's** own emission attempt. Read as a general rule for every
writer, it would imply a refusal-record emission failure could itself
trigger another refusal attempt, and a stage-closure emission failure could
summon a refusal record too. Neither is intended, neither is bounded, and
nothing in §16.3.9's retirement table closed the fallback's own failure path.
FU6 froze the distinction explicitly, per writer; FU7 corrects exactly where
the primary writer's fallback window closes.

**Finding 1, stated precisely (FU7).** FU6's eligibility rule for the
primary run-record fallback read "after steps 1–2... and before an
exclusive-create collision (step 10)" — phrasing that treats step 10 as
atomic and treats "collision" as its only failure mode. Neither is
mechanically true. Step 10 is **four distinct sub-actions**: the
exclusive-create call itself, then a write of `artifact_bytes`, then a flush,
then a close. The exclusive-create call can **succeed** and only
**afterward** have the write, the flush, or the close fail — at which point
the final path may already hold zero bytes, partial JSON, or the full bytes
whose successful durability was never established. A refusal fallback cannot
safely be attempted at that same path without either overwriting/colliding
with what is already there or leaving two candidate artifacts whose relative
trustworthiness is undefined. **The eligibility boundary is not "before a
collision" — it is "before the exclusive-create call is ever issued."**

**The frozen emission-phase vocabulary.** Every durable writer's step 10
passes through, in order, at least these five phases (exact internal
representation — an enum, a dataclass field, a log line — is implementation
discretion; the phases and their ordering are not):

```text
PRE_CREATE                    — steps 1-9 of §16.3.8; the final path has not
                                 been touched in any way
FINAL_PATH_CREATE_ATTEMPTED   — the exclusive-create call (O_CREAT | O_EXCL
                                 or the platform equivalent) has been issued;
                                 its outcome may be success, a collision, or
                                 an ambiguous OS-level failure
FINAL_PATH_CREATED            — that call returned success: the final path
                                 now exists, owned by this attempt, holding
                                 zero or more bytes
BYTES_FULLY_WRITTEN           — every byte of artifact_bytes has been
                                 transferred to the open file
EMISSION_CONFIRMED            — flush and close both completed without error;
                                 this writer's own local write sequence is
                                 done (never a durability, fsync, or storage-
                                 layer claim — see the design's existing
                                 non-sandboxing disclaimers, §5F2D-class
                                 language this design does not repeat but
                                 does not contradict either)
```

**Refusal-fallback eligibility, corrected (Finding 1).** A primary run-record
failure may attempt its one refusal fallback **only when the failure occurred
strictly within `PRE_CREATE`** — i.e. at any of steps 1–9: authority
re-proof, schedule derivation, type-gating, canonicalization, payload
validation, authority/schedule binding, scrub, or size validation —
**provided output authority remains valid**. The moment
`FINAL_PATH_CREATE_ATTEMPTED` is reached, **there is no refusal fallback at
that run path, under any subsequent outcome of that attempt**, including:

```text
exclusive-create collision                    (already EMISSION_COLLISION,
                                                 unchanged from FU6)
exclusive-create non-collision I/O failure    (new, FU7: e.g. a permission
                                                 error, a disk-full error, or
                                                 any other OSError that is not
                                                 unambiguously "the path
                                                 already existed")
write failure after successful create         (new, FU7)
flush/close failure after successful create   (new, FU7)
any state in which path creation is uncertain (new, FU7)
```

**Fail closed on ambiguity.** A generic `OSError` (or platform equivalent)
raised by the exclusive-create call is **never** interpreted as proof the
path is definitely absent merely because it is not the specific
already-exists error. Only an unambiguous, platform-defined "path already
existed" signal is classified as the collision case
(`EMISSION_COLLISION`); every other exception from the create call, and
every failure from write/flush/close, is treated identically —
`FINAL_PATH_CREATE_ATTEMPTED` was reached, no fallback is attempted, and the
post-create residue policy below applies.

**Post-create failure residue policy (new, FU7).** If CFG1 successfully
created the final run/refusal path (`FINAL_PATH_CREATED` or later) but the
write, flush, or close subsequently failed:

```text
DO NOT overwrite it
DO NOT truncate it
DO NOT rename over it
DO NOT unlink it by pathname
DO NOT attempt a refusal fallback at that path
```

The stage is one-shot and halts (§19.2), so the safe policy is to leave any
residue exactly as it is. **The residue is not authoritative CFG1 evidence.**
The run's stage-closure status is `EMISSION_FAILED`, provided stage-output
authority still permits a separate stage-closure write (§16.3.9 — a
post-create write failure is not itself an authority-provenance failure, so
§16.3.7's hard stop does not apply merely because it occurred). The post-hoc
run-artifact verifier (§22.5.2) must return `False` for malformed or partial
residue — its existing byte-bounded read, UTF-8 decode, JSON parse, and
payload-validator steps already do this mechanically, with no special-casing
needed for "this came from a failed write" versus any other malformed file.

**A structurally valid residue does not retroactively confirm emission.** If
the residue happens to contain bytes that parse and bind correctly despite
the live write operation itself having reported failure — for example, a
write that fully succeeded but whose subsequent `close()` call raised — a
post-hoc `verify_cfg1_run_artifact_binding(actual_path) == True` means
**only**: *the bytes currently on disk form a valid, correctly-bound CFG1
artifact.* It does **not** retroactively change that ordinal's
already-recorded stage-closure emission status from `EMISSION_FAILED` to
`EVIDENCE_REFUSED` or `RECORD_EMITTED`, and it does not prove the live
emission operation completed successfully — the stage-closure record's
status reflects what the writer itself observed at emission time, which is
authoritative for classification purposes even when a later, independent
read of the residue happens to succeed. **No later CFG1 stage or run ever
reads this (or any) residue for authority** — §20 already establishes that
nothing in `results/` authorizes cleanup or a future write; this paragraph
extends that to: a post-hoc read of one ordinal's residue never changes any
other record's or any other run's behavior, and never changes its own
ordinal's already-sealed classification either.

**Primary run-record emission failure, applying the corrected boundary.** For
a run record only, a bounded `PRE_CREATE` failure — in canonicalization,
schema validation, authority binding, scrub, serialization, or size
validation, **provided output authority remains valid** — may produce **at
most one** CFG1 refusal artifact, written at that same schedule-derived run
path (§18 row 11). That refusal artifact is freshly built from:

```text
authority identity           — authority.stage_id, authority.stage_execution_id
schedule-derived ordinal/arm — run_ordinal, and arm_id from step 2's
                                _schedule_arm_for derivation, never from the
                                rejected payload
bounded failure categories   — the closed finding_categories vocabulary
                                (§22.4.1), never the rejected payload's raw
                                content
already-finalized lifecycle bool — lifecycle_all_closed, already computed at
                                L28 before L29 ever runs
```

never from arbitrary fields of the rejected payload — the rejected payload
contributes only bounded finding-category facts (§22.4.1's
`finding_categories`/`finding_count`), never identity authority (already
frozen by §21.2; restated here because it is what makes "freshly built" a
mechanical requirement rather than a stylistic preference). **No recursive
fallback exists for this case**: if the refusal artifact itself cannot be
built or written, control passes to the next paragraph — `emit_cfg1_run_record`
does not retry itself, and `emit_cfg1_refusal_record` (below) does not retry
itself either. **If the primary run record's own failure occurs at or after
`FINAL_PATH_CREATE_ATTEMPTED`, no refusal artifact is attempted at all** —
this is the corrected case, distinct from the `PRE_CREATE` case above, and it
produces `EMISSION_FAILED` directly, with the post-create residue policy
applying to whatever (if anything) the failed create/write left behind.

**Refusal-record emission failure.** `emit_cfg1_refusal_record` **never**
attempts to emit another refusal record for its own failure, regardless of
whether its own failure was `PRE_CREATE`, a `FINAL_PATH_CREATE_ATTEMPTED`
collision, a non-collision create failure, or a post-create write/flush/close
failure — this non-recursion rule does not depend on the phase or exact
cause of the refusal writer's own failure. **Collision is not a
primary-writer-only concept (Finding 3, FU9): the refusal writer's own
exclusive-create can collide too, at its own `FINAL_PATH_CREATE_ATTEMPTED`,
and that collision is classified identically to a primary-writer collision —
`EMISSION_COLLISION`, `RUN_RECORD_EMISSION_COLLISION`, stage halt, no further
fallback, the occupant never overwritten, deleted, or reused.** The
distinction the design draws is never "primary writer versus refusal writer"
— it is always "collision versus every other failure mode," applied
identically to whichever writer's own create call is the one that failed:

```text
refusal writer's own exclusive-create collides at
FINAL_PATH_CREATE_ATTEMPTED (unambiguous already-exists result)
    -> EMISSION_COLLISION, RUN_RECORD_EMISSION_COLLISION
       (identical classification to a primary-writer collision;
        §17/§18 rows apply the same way)

refusal writer's own exclusive-create fails for any other reason, or its
create-state cannot be proved (a non-collision I/O error, an ambiguous
platform result) — new, FU9 Finding 3, closing a gap FU7/FU8 left implicit
    -> EMISSION_FAILED, RUN_RECORD_EMISSION_FAILED
       (never infer the path is absent; never delete or overwrite any
        possible residue/occupant)

refusal writer's own create succeeds, then write/flush/close fails
    -> EMISSION_FAILED, RUN_RECORD_EMISSION_FAILED (unchanged from FU7/FU8)
```

In every one of these three sub-cases, `emit_cfg1_refusal_record` returns
**one** bounded emission-failure result and nothing else — **no second
artifact is attempted at the run path**, and the stage halts. The scheduled
run has no successfully-confirmed run-path artifact in any of the three,
because the run record failed **and** the one permitted refusal fallback
also failed — for the non-collision/post-create sub-cases this durably
records `EMISSION_FAILED`/`RUN_RECORD_EMISSION_FAILED` (§19.4); for the
collision sub-case it durably records `EMISSION_COLLISION`/
`RUN_RECORD_EMISSION_COLLISION` instead, exactly as a primary-writer
collision would. **If the refusal writer's own failure left residue on disk
(possible only for the non-collision-create or post-create sub-cases — a
genuine collision, by definition, writes nothing new), the same residue
policy above applies: never overwritten, never deleted, never reused, never
treated as authoritative.** If stage-output authority is still valid at this
point (it is, by construction — none of these three refusal-writer failure
sub-cases is itself an authority-provenance failure, so §16.3.7's hard stop
does not apply here), the stage-closure writer may still record the
applicable status for that ordinal in the stage-closure record. If
stage-output authority itself had already failed, §16.3.7 remains
authoritative regardless: console only, no stage-closure write, and this
paragraph never runs.

**Stage-closure emission failure.** `emit_cfg1_stage_closure` **never** emits
a refusal record, under any failure of its own, at any phase — this is the
second non-recursion rule Finding 3 requires, distinct from the first
(**the stage-closure writer never has a refusal fallback at all — not a
narrowed-eligibility fallback, no fallback of any kind**), and it too does
not depend on whether the failure was `PRE_CREATE` or post-create.

**All create-attempt and post-create outcomes for the stage-closure writer,
frozen exhaustively (new, FU9 Finding 3 — FU6/FU7/FU8 stated this only as one
generic bucket):**

```text
PRE_CREATE validation/scrub/size failure
    (against _require_valid_cfg1_stage_closure_payload, §22.4.2)

FINAL_PATH_CREATE_ATTEMPTED collision
    (unambiguous already-exists result)

FINAL_PATH_CREATE_ATTEMPTED non-collision / ambiguous create failure
    (any other OSError, or a create-state that cannot be proved —
     the identical fail-closed-on-ambiguity discipline the primary and
     refusal writers already apply)

write failure          (after a successful create)
flush failure           (after a successful write)
close failure           (after a successful flush)
```

**Every one of these six resolves identically**, because the stage-closure
writer's response to failure never varies by cause — there is no fallback
whose eligibility could differ by phase, unlike the two run-scoped writers:

```text
live stage-closure emission FAILED   (EMISSION_CONFIRMED not reached)
console-only bounded report          (§21.2)
no replacement name, no fallback artifact, no recursive refusal
retire the stage-output authority    (§16.3.9's stage-closure row)
stage ends
any residue or pre-existing occupant left completely untouched
```

**A collision and a non-collision/ambiguous create failure may be reported
with distinct console-only closed codes, if useful for operator
diagnosis** — for example a `STAGE_CLOSURE_CREATE_COLLISION` alongside a
`STAGE_CLOSURE_CREATE_FAILED` (exact literals implementation discretion) —
**but neither ever becomes a durable `halt_reason_code`, because the
stage-closure artifact itself was never confirmed** (§19.4: `HALT_REASON_CODES`
is populated only by a *successfully emitted* stage-closure record, and this
entire paragraph is precisely the case where no stage-closure record exists
to carry one — the third of the three no-durable-halt-reason cases §19.4 and
§22.4.2 both enumerate). This distinguishes the stage-closure writer's own
collision from a run-path writer's collision in exactly the one place they
differ: a run-path collision still gets a durable `RUN_RECORD_EMISSION_COLLISION`
in a stage-closure record written by a *different*, still-succeeding write
(the stage-closure write itself); a stage-closure collision has no such
second writer above it to record anything durably at all.

**Any partial stage-closure residue is left untouched and is never treated
as a successful closure record** — the same post-create residue policy
applies here: no overwrite, no truncate, no rename, no unlink by pathname.
Existing genuine run artifacts already written before this failure remain
untouched on disk, individually trustworthy — exactly the same guarantee
§16.3.7 already states for the harder case of a root/directory provenance
failure, extended here to the narrower case of the stage-closure record's own
emission failing while output authority itself remains valid.

**Record self-validation failure semantics (Row 15 clarification, FU6;
phase-consistent, FU7).** If the **primary** run payload fails its own schema/
invariant validation (`_require_valid_cfg1_run_payload`, step 6) — an
implementation defect, not an ordinary scrub-needle hit, and necessarily a
`PRE_CREATE` failure since step 6 precedes step 10 entirely — this is §18 row
15: one bounded refusal artifact may be attempted per the
primary-run-record-emission-failure paragraph above, and the stage **halts
even if that refusal artifact succeeds**. A successfully written refusal
artifact does not convert an implementation defect into an admissible next
run. This is encoded mechanically, not left to prose: row 15's
`halt_triggered_by_this_run` is unconditionally `true` regardless of the
refusal artifact's own emission outcome, and §19.1's admission-token rule
requires `halt_triggered_by_this_run == false` as an explicit, independent
condition (revised item 2, §19.1) — so an `EVIDENCE_REFUSED` emission status
alone, without also checking this bool, can never admit ordinal *k*+1 after a
row-15 failure. (Ordinary scrub-needle refusals, §18 row 11, leave
`halt_triggered_by_this_run == false`, which is exactly why row 11 does not
halt and row 15 does — the two rows share an emission status,
`EVIDENCE_REFUSED`, but not this bool.)

**Emission-status meanings, corrected (Finding 2, FU7).** An earlier draft of
this design's status prose (carried in §22.4.2) inverted `EVIDENCE_REFUSED`'s
own description. The exact, corrected meanings, restated here as the
normative source both §22.4.2 and §17/§18 must agree with:

```text
RECORD_EMITTED
    a valid run record was successfully emitted (EMISSION_CONFIRMED reached
    for the primary run-record writer)

EVIDENCE_REFUSED
    a valid refusal record was successfully emitted at the run path
    (EMISSION_CONFIRMED reached for the refusal-record writer, whether
    triggered by row 11's ordinary scrub refusal or row 15's implementation
    defect — the halt metadata, not this status, disambiguates the two)

EMISSION_COLLISION
    the final run path collided at FINAL_PATH_CREATE_ATTEMPTED; no new
    valid run-path artifact was emitted by this run

EMISSION_FAILED
    no successfully-confirmed run-path or refusal-path emission exists for
    this ordinal, because emission failed without being classified as the
    path-collision case — covers both a PRE_CREATE refusal-fallback failure
    and any post-create failure of either writer, and a structurally valid
    residue found later by the post-hoc verifier does not change this status
    (see the post-create residue policy above)

NOT_EXECUTED
    this ordinal never ran, because the stage had already halted at or
    before it
```

Regressions: T-73–T-79, T-83–T-87 (§11.3).

#### 16.3.8.3 Sealed stage decision — CFG1-owned, non-forgeable, L30-only (new, FU9; issuance boundary closed, FU10)

**Finding 1, stated precisely (FU9).** FU8 correctly made the stage-closure record
the sole durable authority for whether the stage halted, after which
ordinal, why, and the per-ordinal emission ledger. But the stage-closure
writer's own boundary, as FU4–FU8 left it, still conceptually accepted
`emit_cfg1_stage_closure(authority, *, payload)` — an arbitrary caller
payload — and §16.3.8 step 7 bound only `stage_id`/`stage_execution_id`/
`record_filename` against `authority`. **Internal self-consistency is not
provenance.** A supported caller holding a genuine, ACTIVE
`CFG1StageOutputAuthority` could construct a different, fully schema-valid
closure payload — a different `ordinal_status`, a different
`halted_after_ordinal`, a different `halt_reason_code` — and step 7 has no
mechanical fact proving that payload equals the decision L30 actually
reached. The writer must never accept caller-selected stage-decision facts
at all.

**Finding 1, stated precisely (FU10) — the FU9 fix moved the same defect one
layer upstream instead of closing it.** FU9's own fix was specified as a
module-level, importable function:

```python
seal_cfg1_stage_decision(
    authority, *, ordinal_status, halted_after_ordinal, halt_reason_code,
) -> CFG1StageClosureDecision
```

FU9's own text asserted this is "called **only** by L30" and is "the only
call site in the entire design" — but nothing in that signature *enforces*
either claim. Any supported caller holding a genuine, ACTIVE
`CFG1StageOutputAuthority` can call this function directly, with its own
choice of `ordinal_status`/`halted_after_ordinal`/`halt_reason_code` — an
internally self-consistent tuple describing a stage execution that never
happened — and receive back a genuine object: a real `decision_nonce`, a
real `_STAGE_DECISION_SEALED` registry entry, and a real, matching
`authority.mint_nonce` binding. That object then passes every one of
`emit_cfg1_stage_closure`'s own checks (steps 1–5 below), because those
checks prove only that the decision presented is *the one the registry
knows about* — **the mint registry proves who issued the object, not that
the facts inside it came from the real L30 stage state.** This is exactly
the invariant §16.3.8's own Finding 1/Finding 2 already established for the
stage-closure writer itself ("caller-selected stage-decision facts are not
authority") — FU9 applied it to the writer's own boundary and left the
sealer, one call away, exempt from it. **"There is only one normal call
site" is a documentation claim about how the design intends the function to
be used, never a mechanical property of a function any importer can call
with any arguments it likes.** The sealer must obey the same invariant the
writer already does.

**The FU10 fix: remove stage-decision issuance from the public,
authority-parameterized API surface entirely — do not merely re-check its
inputs more carefully.** `seal_cfg1_stage_decision`, as a module-level
function taking `ordinal_status`/`halted_after_ordinal`/`halt_reason_code`
as independent, caller-suppliable arguments, **no longer exists.** Stronger
input validation on that function's arguments would not close this gap,
because the function's entire defect is that it *has* caller-suppliable
decision-fact arguments at all — there is no value of those arguments a
supported caller could supply that the function could distinguish from a
value the real L30 step would have computed, since both are, from the
function's own point of view, merely "arguments it was called with." The
only mechanical fix is to make the facts never arrive as arguments in the
first place.

**Mechanism (exact implementation shape discretionary; the property below is
not): sealing becomes an unindexed, lexically-owned step of the one stage-
runner routine that executes L0–L30, never a separately-nameable,
separately-callable, separately-importable function.** The stage runner
(§16.2's own already-frozen orchestration — there is exactly **one** such
routine, and exactly **one** invocation of it per stage execution) is
extended with one new, entirely local, non-registry, non-exported piece of
state — the **stage-progress ledger** (new §16.3.8.4) — that the routine
itself populates, ordinal by ordinal, as each ordinal's real L29 result
actually resolves (§16.2 row L29, revised below), and consults, only at its
own L30 step, to build the sealed decision's `ordinal_status`,
`halted_after_ordinal`, and `halt_reason_code`. Illustratively (one
acceptable concrete shape; equivalent shapes — e.g. a lexical/internal
issuer object the stage runner alone holds a reference to — are equally
acceptable, per the design's own "exact mechanism discretionary" latitude
used everywhere else in this section):

```python
def run_cfg1_stage(...):          # the one L0-L30 orchestration routine
    _ordinal_ledger = {}          # local variable — never a module global,
                                   # never returned, never passed to any
                                   # function outside this routine's own body

    def _record_ordinal_result(run_ordinal, ordinal_status):
        # a nested function, never bound to a module-level name; nothing
        # outside this routine's own call frame holds a reference to it
        _ordinal_ledger[run_ordinal] = ordinal_status

    def _seal_terminal_decision(halted_after_ordinal, halt_reason_code):
        # likewise nested and unreachable from outside; builds
        # ordinal_status from _ordinal_ledger (filling NOT_EXECUTED for
        # every declared ordinal absent from it, §22.4.2's own invariant),
        # then performs exactly the mint-and-register step FU9 already
        # specifies below — nonce, registry entry, frozen object — reading
        # stage_id/stage_execution_id from the closed-over `authority`,
        # never from a parameter
        ...
    ...
```

**Why this closes the gap, stated as the mechanical property the design
requires — not merely "this happens to be the only place it's called
today."** `_record_ordinal_result` and `_seal_terminal_decision` (or
whatever a concrete implementation names its equivalents) are never assigned
to a module attribute, never exported, never importable, and never
discoverable by introspecting any object a supported caller can obtain by
holding only a `CFG1StageOutputAuthority` — the authority object itself
carries no reference to them (§16.3.3's frozen-dataclass field set is
unchanged; FU10 adds no field to it). A supported caller therefore has no
name, no attribute path, and no object graph edge that leads to either
function. This is a **stronger** property than "there happens to be one call
site": a single call site is a fact about how correct code behaves; **no
reachable name** is a fact about what code holding only an authority is
capable of doing at all, regardless of intent — precisely what the phase
prompt requires and what "the helper name is private" (a single leading
underscore on an otherwise still-importable module function) would **not**
have provided. `halt_reason_code`, when the branch is a halt, is still never
a free choice inside this local step either: the stage runner's own L30 code
computes it by calling §19.5's one shared `_resolve_halt_reason_code`
function over the now-known local facts (the ledger's own just-recorded
entry for the current ordinal, plus `halt_triggered_by_this_run`,
`lifecycle_all_closed`, `run_classification`, and registry emptiness — every
one of these already an in-memory L30-local fact under the unchanged
FU8/FU9 design) and passes the **result** into the local sealing step —
never re-derived or overridden there, exactly as FU9 already required of the
now-removed public function.

**What must be true, mechanically, not merely by convention:**

1. **Created only at L30, after the current ordinal's L29 emission result is
   final.** There is no reachable call site for a supported caller anywhere
   in this design (§16.2's frozen step ordering, plus the absence of any
   externally-reachable name per the mechanism above, are the joint proof
   this needs — the sealing step simply has no name to be called by, before
   L30 or otherwise, from outside the one routine that contains it).
2. **Binds exactly:** `stage_id`, `stage_execution_id`, the complete
   per-ordinal emission-status ledger (`ordinal_status`), `halted_after_ordinal`,
   `halt_reason_code`, and the derived successful-vs-halted state (§22.4.2's
   own "successful stage" invariant, restated as a decision-object property
   rather than left to be independently re-derived by every reader).
3. **Immutable after sealing** — a frozen object (mirroring
   `CFG1StageOutputAuthority`'s own `frozen=True` dataclass shape), never
   mutated in place by any later code.
4. **Direct supported construction, a forged nonce, or field substitution
   cannot produce a valid decision.** The stage runner's own local sealing
   step mints a fresh, unguessable `decision_nonce` (`secrets.token_hex(16)`,
   mirroring `mint_nonce`) and registers `(decision_nonce, <every bound
   field>, authority.mint_nonce)` in a process-local registry,
   `_STAGE_DECISION_SEALED`
   (exact name discretion), **before** returning the frozen object; the
   object's own `__post_init__` refuses to construct unless its
   `decision_nonce` is already registered with exactly matching fields —
   identical in shape to `CFG1StageOutputAuthority.__post_init__`'s own
   registry re-check (§16.3.3). A caller who directly instantiates the class
   with plausible-looking fields and an unregistered or guessed
   `decision_nonce` fails identically to `CFG1StageOutputAuthority`'s own
   `UNKNOWN_MINT_NONCE` case; a caller who takes a genuine object and
   mutates a field via `object.__setattr__` (bypassing `frozen=True`) is
   caught the same way T-27 catches the analogous authority-field bypass —
   at the next re-proof (step 3 below), never trusted from a cached prior
   check.
5. **A genuine decision cannot be rebound to a different
   `CFG1StageOutputAuthority`.** The registered tuple includes
   `authority.mint_nonce` at seal time; the stage-closure writer's own
   consumption (below) re-checks `decision.authority_mint_nonce ==
   authority.mint_nonce` as an unconditional gate, refusing a genuine,
   unmutated decision presented alongside a different (even if also genuine
   and ACTIVE) authority object.
6. **At most one terminal decision may be sealed per `CFG1StageOutputAuthority`
   — proven by a seal-history fact independent of decision consumption
   (cardinality corrected FU11; mechanism corrected FU12).** L30 itself
   executes **once per admitted ordinal** — not once per stage execution. A
   normal `S1` stage reaches L30 up to nine times, an `S2` stage up to six,
   exactly as many times as §19.6 evaluates the three-way transition for an
   ordinal that was actually admitted (§19.6 branch B is reached, and L30
   runs again for the next ordinal, every time a run is neither the final
   one nor a halt). **The local sealing step is not invoked at every one of
   those L30 evaluations — only when that same evaluation selects branch A
   or branch C** (§19.6); branch B returns an admission token and never
   touches either registry below at all (T-126).

   **Finding (FU12), stated precisely.** FU11 corrected this requirement's
   *cardinality* claim but left its *mechanism* resting entirely on
   `_STAGE_DECISION_SEALED` — the very registry step 4a (below) revokes the
   consumed decision's own entry from, at the start of that decision's one
   permitted consumption. That is self-defeating: once step 4a has run,
   `_STAGE_DECISION_SEALED` retains no trace that this authority ever sealed
   anything, so a malformed or test-only second reach of the sealing step
   **after** a first decision has already been sealed *and consumed* would
   find the registry empty and could register a second, independently
   genuine decision — exactly the outcome this requirement exists to
   prevent, and squarely inside its own already-stated threat scope ("some
   malformed or test-only control flow... through a bug, a test harness, or
   any other means").

   **The fix separates two properties that were wrongly proven by one
   registry:**

   - **`_STAGE_DECISION_SEALED[decision_nonce]`** — decision
     **authenticity and one-shot consumability** (unchanged in shape from
     FU9/FU10): proves a presented `CFG1StageClosureDecision` is genuine and
     unmutated, and is revoked at the start of its one permitted consumption
     (step 4a). This answers *"is this specific decision object genuine and
     still consumable"* — never *"has this authority already had a terminal
     decision sealed."*
   - **`_STAGE_TERMINAL_SEAL_HISTORY` (exact name implementation
     discretion), keyed by `authority.mint_nonce`** — a per-authority
     **seal-history fact**, new in FU12, established exactly once, on the
     first terminal seal, and **never removed by decision consumption, by
     that consumption's write succeeding or failing, or by authority
     retirement** — only by the bounded process-memory cleanup the
     "Terminal-seal history lifetime" paragraph below permits, after the
     stage runner has irreversibly left every code path capable of reaching
     the sealing step. This answers exactly the question this requirement
     needs answered, correctly, regardless of what has since happened to any
     individual decision's own consumability.

   **The terminal sealing step's exact sequence, frozen in order (first
   attempted seal for a given `authority.mint_nonce`):**

   1. verify the authority/state conditions already frozen elsewhere (ACTIVE
      authority re-proof; the current ordinal's L29 result present in the
      stage-progress ledger, §16.3.8.4);
   2. **require no entry exists in `_STAGE_TERMINAL_SEAL_HISTORY` for
      `authority.mint_nonce`** — refuse, with no decision registered and none
      constructed, if one already does;
   3. **atomically establish the per-authority seal-history fact** — add
      `authority.mint_nonce` to `_STAGE_TERMINAL_SEAL_HISTORY`, **before**
      step 4, so that a failure in step 4 or step 5 still leaves this fact
      durably set ("Partial-failure atomicity of the mint sequence" below);
   4. register the decision's nonce/field authenticity record in
      `_STAGE_DECISION_SEALED` — identical in shape to FU9's own mechanism;
   5. construct and return the genuine, frozen `CFG1StageClosureDecision` —
      `__post_init__`'s existing registry re-check (unchanged) is what makes
      this step's success depend on step 4 having already succeeded.

   A **second** reach of the sealing step for the same `authority.mint_nonce`
   — at any later point, under any internal control-flow ordering, including
   **after** a first decision has already been fully consumed and its own
   `_STAGE_DECISION_SEALED` entry revoked by step 4a — refuses at step 2
   above, because step 3's fact is untouched by decision consumption. **This
   is the corrected mechanical backstop**: seal-once is a property of
   `_STAGE_TERMINAL_SEAL_HISTORY` alone, never of `_STAGE_DECISION_SEALED`,
   and the two registries' lifetimes are now independent by construction —
   revoking one can never weaken the other (T-107).

   As before, this does not depend on, and never claims, "L30 runs once" as
   its proof: because the sealing step still has no reachable name for any
   supported caller (Finding 1, FU10, requirement 9), this entire sequence —
   and every attempt to reach it a second time — can only ever be exercised
   by control flow **internal to** the stage runner's own implementation,
   never by a supported caller holding only `authority`.

   **Terminal-seal history lifetime, frozen exactly (new, FU12).**
   `_STAGE_TERMINAL_SEAL_HISTORY`'s entry for a given `authority.mint_nonce`
   must survive at least: the decision's own sealing (step 3 above); the
   entire first, and only, stage-closure writer attempt for that authority;
   that attempt's success or failure; stage-output-authority retirement
   (§16.3.9); and must continue to survive until the stage runner has
   irreversibly left every code path capable of reaching the sealing step for
   that authority — i.e., until that stage execution's own orchestration
   routine invocation itself returns. Only then may it be discarded, as
   bounded process-memory cleanup with no further significance. It is never
   persisted to disk, never becomes CFG1 evidence, and is never exposed
   through any supported API, reachable name, or object a caller could hold
   — identical in spirit to the stage-progress ledger's own unreachability
   (§16.3.8.4). Proving it resists direct mutation, monkeypatching, or other
   same-process memory tampering is **not** required, mirroring FU11's own
   threat-model scope for `_STAGE_DECISION_SEALED` exactly — this is an
   internal authenticity/history fact, not an issuance API, and the
   supported-caller threat model is unchanged and unwidened by FU12.

   **Partial-failure atomicity of the mint sequence (new, FU12).**
   Adversarially, three failure points exist between steps 2 and 5 above:

   - **Between step 2 (history check passes) and step 3 (history fact
     established).** In an ordinary, non-concurrent process (§16.3.4's own
     excluded-threat-class note, unchanged), establishing a single fact in a
     single in-memory set/dict is not itself decomposable into a further
     partial state — it either completes, or the surrounding call raises
     before it does, in which case **neither registry gains an entry**. No
     decision was registered and none was constructed, so nothing is
     stranded and nothing risks duplication. **This is corrected, FU13: the
     absence of any registry entry does not make a later attempt a
     legitimate first seal.** Technical retryability is irrelevant here —
     operationally, the stage runner does not attempt the mint sequence
     again for this authority under any circumstance, because the failure
     itself, at any of the three points below, unconditionally drives the
     stage into the terminal disposition the next paragraph freezes. The
     absence of stranded registry state is a fact this design proves (T-137);
     it is never treated as license to retry.
   - **Between step 3 (history fact established) and step 4 (decision
     registered).** The history fact from step 3 is already durably set. A
     later reach of the sealing step for this `authority.mint_nonce` refuses
     at step 2, permanently, for the remainder of the seal-history fact's
     lifetime. No decision was ever registered or constructed, so there is
     no decision object anywhere for any code to present to
     `emit_cfg1_stage_closure` — an apparently genuine decision without a
     valid authenticity record cannot arise, because no object escapes this
     failed call at all. The stage is left **unable ever to complete a
     terminal seal again** for this authority — a stranded, fail-closed
     state, never a reopened one, and the explicitly preferred outcome.
   - **Between step 4 (decision registered) and step 5 (frozen object
     constructed and returned).** The history fact and the
     `_STAGE_DECISION_SEALED` entry are both already set, but `__post_init__`
     never completes, so no `CFG1StageClosureDecision` object is ever
     returned to any caller — the registered `_STAGE_DECISION_SEALED` entry
     becomes **orphaned and unusable until the bounded mint-failure cleanup
     removes it** (§16.3.9's new row; the "Registry cleanup on mint failure"
     paragraph below), authenticating nothing in the meantime, since there is
     nothing left to present it to and no code path can construct the exact,
     freshly-generated `decision_nonce` needed to satisfy `__post_init__`'s
     check a second time. This is likewise harmless: the history fact from
     step 3 already forecloses any second seal attempt independently of it.

   **In every one of these three cases, both required negatives hold:** two
   genuine terminal decisions for one authority remains impossible (step 3's
   history fact, once set, is never re-cleared by any of these failures),
   and an apparently genuine decision without a valid authenticity record
   cannot arise (a decision object only ever exists once `__post_init__` has
   already confirmed a matching, registered `_STAGE_DECISION_SEALED` entry —
   no code path returns an unauthenticated-looking object). **No recovery or
   retry path is invented for any of these failures** — a stage that strands
   its own seal history this way simply never completes a terminal closure,
   an existing, already-accepted failure shape in spirit (§18 row 17's
   stage-closure-writer-failure treatment; here the failure occurs one step
   earlier, at minting rather than at writing, but the design's own "never
   repair, never reopen" discipline is identical).

   **Terminal-decision mint failure disposition (new, FU13).** FU12 named
   the three failure points above but never assigned any of them a lifecycle
   disposition — no genuine `CFG1StageClosureDecision` exists in any of the
   three, so `emit_cfg1_stage_closure(authority, decision=...)` cannot be
   called, and "the stage never completes a terminal closure" was left as an
   observation rather than a frozen, mechanically-closed exit. **Any failure
   of the terminal-decision mint sequence, at any point after L30 has
   selected §19.6 branch A or branch C and begun the sealing attempt,
   receives this exact, uniform disposition — regardless of which of the
   three failure points above it occurred at:**

   ```text
   STAGE_DECISION_MINT_FAILED
   ```

   This code is **console-only** (§21.2); it is **never** placed into a run
   record, a refusal record, or a stage-closure record; it is **never** the
   value of `halt_reason_code` and **never** added to `HALT_REASON_CODES`
   (§19.4) — there is no durable stage-closure record in which such a code
   could truthfully live, for the identical reason `OUTPUT_NAMESPACE_PREOCCUPIED`
   (§16.3.10) already is not a `HALT_REASON_CODES` member. It is **never**
   raw exception text, a `repr`, or a traceback — the stage runner converts
   the internal mint-sequence failure into this bounded code before it
   reaches any reporting surface, mirroring §21.1's reduction rule exactly:
   the raw value is dropped at the point it is caught, and only the closed
   code crosses that boundary.

   **On any such failure, unconditionally:**

   1. no second terminal-decision mint attempt is permitted, for this
      authority, ever — the stage runner does not retry the mint sequence
      regardless of which of the three failure points was hit, and
      regardless of what state either registry is left in;
   2. no admission token is issued;
   3. no stage-closure writer is called (there is no genuine decision to
      present to it);
   4. no stage-closure artifact is written;
   5. every already-confirmed run record and refusal record for this stage
      execution remains untouched — this failure never triggers cleanup,
      rewrite, or reclassification of any prior artifact;
   6. the stage-output authority is retired immediately — **before** console
      reporting and **before** the stage runner's own routine returns or
      raises out of the internal mint operation — identical timing to
      §16.3.7's and §16.3.10's own hard-stop retirement (§16.3.9's new row,
      below);
   7. exactly one bounded console report, `STAGE_DECISION_MINT_FAILED`, is
      produced, through the same bounded sink §16.3.10's
      `OUTPUT_NAMESPACE_PREOCCUPIED` report already uses (§21.2);
   8. the stage ends;
   9. interpretation for this stage is incomplete/unusable, exactly as for
      the stage-closure writer's own emission failure (§18 row 17);
   10. resumption requires a new authorization and a new
       `stage_execution_id` (§14.1 item 4), exactly as for any other halt or
       hard stop.

   **No automatic retry or recovery path exists for this disposition, under
   any of the three failure points, including the one before step 3 where
   neither registry gained an entry.** The corrected first bullet above
   states why: the absence of stranded registry state is a fact this design
   proves, never a license this design grants, to attempt the mint sequence
   again.

   **Registry cleanup on mint failure, keeping the two FU12 lifetimes
   distinct.** `_STAGE_TERMINAL_SEAL_HISTORY`: if step 3 already established
   the entry before the failure, it is **retained** through authority
   retirement and for the remainder of the stage runner's own invocation —
   it continues to block any malformed/test-only second reach of the sealing
   step, exactly as FU12 already requires, and is removed only by the
   runner's own final bounded in-memory cleanup once no lexical sealing path
   remains (§16.3.8.3's "Terminal-seal history lifetime" paragraph,
   unchanged, unwidened). If the failure occurred before step 3 ever ran, no
   history entry exists at all — this is not a gap and does not permit an
   operational retry, because the stage has already entered
   `STAGE_DECISION_MINT_FAILED` and its authority is already retired.
   `_STAGE_DECISION_SEALED`: if the failure occurred before step 4 (decision
   registration), no entry exists. If step 4 succeeded but step 5
   (`__post_init__` construction) then failed, the registered entry is an
   **orphan** — it authenticates no object that will ever exist, since no
   code path can reconstruct the exact, freshly-generated `decision_nonce`
   needed to satisfy `__post_init__` a second time — and is removed as
   bounded in-memory cleanup on this exit, so it does not survive
   indefinitely across completed stage-runner invocations. The independent
   seal-history fact, never the orphaned decision entry, remains the
   seal-once backstop until runner exit.

   Regressions: T-135 (rewritten), T-136 (extended), T-137–T-141 (new,
   §11.3).
7. **Cannot be sealed before the current L29 emission result exists.** This
   is a procedural guarantee, not a separate mechanical gate invented for
   its own sake: the local sealing step is the **only** code in the entire
   design that writes `_STAGE_DECISION_SEALED`, it has no reachable name for
   anything outside the stage runner's own routine to invoke (Finding 1,
   FU10) — so it is exercised from exactly the one place that routine's own
   L30 code calls it — and L30 by construction runs only after L29 has
   already resolved (T-101), reading the current ordinal's outcome from the
   stage-progress ledger (§16.3.8.4) that same L29 step just populated. The
   ledger's own append-only, runner-local nature (§16.3.8.4) is the
   mechanical form of this guarantee, exactly parallel to how §16.3.8.2's
   phase model requires no separate mechanism beyond correct step ordering
   to prove `PRE_CREATE` precedes `FINAL_PATH_CREATE_ATTEMPTED`.
8. **The stage-closure writer consumes exactly `(authority, decision)` and
   builds the JSON payload internally — never a caller-selected
   `ordinal_status`/`halted_after_ordinal`/`halt_reason_code`/
   `record_filename`/`stage_id`/`stage_execution_id` as an independent
   closure-payload authority.**
9. **No supported callable API — module-level, closure-returning, class
   method, or otherwise — reachable using only a genuine, ACTIVE
   `CFG1StageOutputAuthority` produces a sealed decision, under any facts,
   ever (new, FU10).** This is the mechanical answer to the phase prompt's
   own required issuance boundary: it is not merely that the two run-scoped
   writers and `emit_cfg1_stage_closure` refuse caller-selected facts (true
   since FU9) — a caller now has **no path at all**, of any shape, to obtain
   a `CFG1StageClosureDecision` describing anything other than what the
   stage runner's own L29/L30 code actually observed, because the only code
   capable of minting one is unreachable from outside that routine's own
   call frame.

**The adapted stage-closure writer sequence (replaces §16.3.8 steps 1–7 for
`emit_cfg1_stage_closure` only; steps 8–10 of §16.3.8 are unchanged and
apply identically):**

1. `verify_stage_output_authority(authority)` (§16.3.4, including the ACTIVE
   check of §16.3.9) — identical to §16.3.8 step 1, refuses before touching
   `decision` at all.
2. `type(decision) is CFG1StageClosureDecision` exactly — **not**
   `isinstance`, no duck-typing, no coercion. Anything else refuses
   immediately, with **zero** reads of `decision`'s fields (mirroring
   §16.3.8 step 3's discipline, T-102).
3. **Re-verify `decision` is genuine, fresh, every call** — never trusted
   from a cached prior check, mirroring `verify_stage_output_authority`'s
   own re-proof discipline (§16.3.4): re-look-up
   `_STAGE_DECISION_SEALED.get(decision.decision_nonce)`; refuse
   `UNKNOWN_DECISION_NONCE` if absent; re-compare every bound field against
   the registry record, refuse `DECISION_FIELD_MISMATCH` on any disagreement
   (catches a genuine decision object mutated via a `frozen=True` bypass,
   exactly as T-27 does for the authority).
4. **Authority-rebinding check:** `decision.authority_mint_nonce ==
   authority.mint_nonce` — refuse `DECISION_AUTHORITY_MISMATCH` otherwise. A
   genuine decision sealed under one stage execution can never be presented
   alongside a different stage's authority, even if that authority is
   itself genuine and ACTIVE.
4a. **Revoke the decision's own one-shot consumability entry only — never
   the per-authority seal-history fact (new, FU10, "Decision lifetime"
   below; scope corrected, FU12, requirement 6 above).** Immediately upon
   step 4 passing — before step 5 ever builds `canonical` — remove
   `decision.decision_nonce`'s entry from `_STAGE_DECISION_SEALED`,
   unconditionally, regardless of how steps 5–10 below subsequently resolve.
   **This step touches `_STAGE_DECISION_SEALED` only. It never touches,
   clears, or otherwise weakens `_STAGE_TERMINAL_SEAL_HISTORY`'s own entry
   for `authority.mint_nonce`** (requirement 6) — that fact was established
   once, at seal time, and this consumption-time step has no authority over
   it. This is the one point in the sequence, not two, where *consumability*
   revocation happens: it does not wait for `EMISSION_CONFIRMED`, because
   §16.3.8.2 already guarantees no second stage-closure attempt is ever made
   for either a successful or a failed write — this step makes that
   guarantee mechanically enforced for *this decision object* rather than
   resting only on "the design says don't call it twice." Whether a
   *different*, never-yet-sealed decision could later be minted for the same
   authority is a question this step has no bearing on either way — that
   question is answered exclusively by requirement 6's separate seal-history
   fact, untouched here (T-107).
5. **Build `canonical` internally, directly from `authority` and
   `decision`'s own already-immutable, already-reverified fields** — never
   from any caller-supplied dict. There is no analogue of §16.3.8 steps 4–5
   here: nothing is canonicalized from untrusted input, because nothing
   untrusted was ever accepted.
6. Run `_require_valid_cfg1_stage_closure_payload` against the
   internally-built `canonical` (§22.4.2) — identical validator, unchanged,
   run for the same reason every writer runs its dispatched validator: a
   final, independent structural check before anything is written, even
   though (unlike the two run-scoped writers) there is no untrusted caller
   input left to distrust at this point.
7. *(No separate authority-binding step is needed — `canonical` was built
   from `authority` directly in step 5, so agreement is true by
   construction. §16.3.8 step 7's table row documents this as a defensive
   re-assertion, not a caller-input check.)*
8–10. Scrub, single-serialize, size-check, derive filename internally,
   exclusive-create/write/flush/close — **exactly** §16.3.8 steps 8–10,
   unmodified.

**No wrapper, no wasted mechanism.** Steps 1, 3–4, 4a here are new (4a added
FU10); steps 2, 5–6 are §16.3.8's own steps re-scoped to `decision` instead
of `payload`; steps 8–10 are cited, never duplicated. This is the same
"point at the frozen contract, never re-describe its algorithm" discipline
L29's own §16.2 row already uses for the writer sequence as a whole (§16.2,
FU8 Finding 4).

**Decision lifetime — two independent one-shot properties, not one shared
mechanism (mechanism corrected, FU12).** FU10 originally described a single
registry, `_STAGE_DECISION_SEALED`, as proving both "a decision cannot be
consumed twice" and, via requirement 6, "a stage cannot be sealed twice."
Independent review (FU12) found this self-defeating, exactly as requirement
6 above now states: step 4a's own necessary revocation of a consumed
decision's entry silently destroyed the only evidence that its authority had
ever sealed anything, reopening the stage to a second, independently genuine
seal. The corrected design freezes **two** properties, proven by **two**
independent registries that never interfere with one another:

- **Consume-once (unchanged in outcome from FU10).** A genuine sealed
  decision is consumable only for its one stage-closure emission attempt.
  Step 4a still freezes the exact mechanism: the decision's own
  `_STAGE_DECISION_SEALED` entry is removed — never merely marked, never
  revertible, mirroring §16.3.9's own "registry membership *is* the state"
  discipline for the stage-output authority — as soon as the one supported
  writer that can ever receive a genuine decision has finished re-verifying
  it (steps 1–4). A second `emit_cfg1_stage_closure` call presented with the
  same, still-genuine `decision` object fails at step 3 with the identical
  `UNKNOWN_DECISION_NONCE` refusal a forged or never-sealed decision
  produces — the decision does not merely become "useless," it becomes
  mechanically indistinguishable from one that was never sealed at all
  (T-132, unchanged).
- **Seal-once (mechanism corrected, FU12).** At most one terminal decision
  may ever be sealed for a given `authority.mint_nonce`, proven by
  `_STAGE_TERMINAL_SEAL_HISTORY` (requirement 6 above) — a fact established
  once, at the first seal, and **never** removed by decision consumption, by
  that consumption's own write succeeding or failing, or by authority
  retirement (T-107).

Combined with Finding 1's issuance closure (no supported caller holding only
`authority` can reach the sealing step at all, so no *supported* path to a
second, independently sealed decision exists either), this proves: **no
second stage-closure emission attempt may ever consume the same sealed
decision (consume-once), and no second, independently genuine decision can
ever be sealed for the same authority, regardless of what has already
happened to a first decision's own consumability (seal-once) — the two
guarantees are proven by disjoint registries, and revoking one can never
weaken the other.**

**What this does and does not prove (Finding 5, stated precisely).**
`_require_valid_cfg1_stage_closure_payload` (step 6) remains a **pure closed-
schema validator** — closed keys, exact literals/types, schedule-sized
`ordinal_status`, internal cross-field coherence, halt-code vocabulary
membership. **It does not, by itself, prove the payload is the actual L30
decision** — a hand-crafted, schema-valid dict could pass it too, if one
ever reached it, which is exactly why steps 1–5 above exist to guarantee
none ever does. **The stronger live-writer guarantee is the conjunction**:
valid schema (step 6) **+** a genuine sealed stage decision (steps 2–3) **+**
an ACTIVE, matching stage-output authority (steps 1, 4) **+** a payload
internally derived from that decision by the writer itself (step 5) — never
schema validity alone. The read-only post-hoc artifact verifier (§22.5)
remains exactly as narrow as it already was: it proves current bytes are
valid and the current filesystem location matches those bytes (§22.5.1) — it
cannot, and this subsection does not newly claim it can, retroactively prove
that the original live `CFG1StageClosureDecision` object existed, was
genuine, or that the live emission operation itself completed successfully;
that is a `EMISSION_CONFIRMED`-or-not fact about the live writer's own run,
never something a later, independent read of bytes can establish (consistent
with §16.3.8.2's own residue-versus-live-outcome distinction, unreopened
here).

Regressions: T-102–T-110 (revised, FU10), T-124–T-125, T-131–T-132 (§11.3);
T-107 further revised and T-133–T-136 added (FU12, §11.3); T-135 rewritten,
T-136 extended, and T-137–T-141 added (FU13, §11.3).

#### 16.3.8.4 Stage-progress ledger — runner-local, unregistered, unreachable (new, FU10)

**What it is.** A plain, mutable, per-stage-execution structure — conceptually
a `dict[int, EmissionStatusLiteral]` keyed by ordinal — created once by the
stage runner immediately after `establish_stage_output_authority` returns a
genuine authority, and existing **only** as a local variable of that one
routine's own call frame for the remainder of that stage execution. Unlike
`CFG1StageOutputAuthority` and `CFG1StageClosureDecision`, it is **not**
registry-backed, carries no nonce, and is never itself a value any function
returns, accepts as a parameter, or exposes through any object a caller could
hold. This is a deliberately **stronger** property than the unforgeability
those two registries provide: a mint registry defends a *callable boundary*
(the object can be presented to a function; the registry proves whether it is
genuine); the stage-progress ledger has **no callable boundary to defend at
all**, because nothing outside the stage runner's own frame ever has a
reference to it, or to any function that reads or writes it, in the first
place.

**How it is populated.** §16.2's L29 row is revised (below) to add exactly
one local step, after that ordinal's real emission result is known: the
stage runner's own code appends `(run_ordinal, ordinal_status)` to the
ledger. This is an ordinary local-variable assignment inside the one routine
that also performs every other L29/L30 action already frozen elsewhere in
this design — not a call to any separately-nameable function, and therefore
not a capability a supported caller holding only `authority` could invoke
with an invented `(run_ordinal, ordinal_status)` pair of its own choosing.

**How it is consumed.** At L30 (§16.2, revised below), the stage runner's own
code reads the ledger — never a copy handed elsewhere, never a value passed
through any public function's parameter — to build the sealed decision's
`ordinal_status` (§16.3.8.3 requirement 2): every ordinal present in the
ledger populates directly; every declared ordinal in `1..LAST_ORDINAL(stage_id)`
(§19.6) absent from the ledger — necessarily every ordinal strictly after the
one that halted, if any — is filled as `NOT_EXECUTED`, mirroring §22.4.2's
own already-frozen `NOT_EXECUTED` invariant exactly, never a separately
re-derived rule.

**Lifetime.** The ledger is discarded with the stage runner's own call frame
when that routine returns — it is never persisted, never copied into
`_STAGE_DECISION_SEALED` or `_STAGE_OUTPUT_MINTED` (only the *values read
from it* at the moment of sealing become part of the immutable, registered
`CFG1StageClosureDecision`), and never consulted by any later stage
execution, mirroring §20's existing "nothing in `results/` authorizes a
future write" principle one level earlier — here, nothing in *process
memory outside one call frame* does either.

Regressions: T-124, T-130 (§11.3).

#### 16.3.9 Authority lifecycle: ACTIVE while minted, RETIRED on every exit path (new, FU4)

**Finding, stated precisely.** `CFG1StageOutputAuthority`'s declared lifetime is
**one stage**. An earlier revision of §16.3.4 called mint-registry discard at
stage end "pure memory hygiene." That is wrong: for as long as an entry
remains in `_STAGE_OUTPUT_MINTED`, the genuine, unmutated authority object
built from it continues to pass every check in §16.3.4 — including after the
stage that minted it has already completed.

**Mechanism: registry membership *is* the ACTIVE/RETIRED state — no second
field, no parallel bookkeeping.**

```text
ACTIVE    = the mint_nonce is currently a key in _STAGE_OUTPUT_MINTED
RETIRED   = it is not (removed — never merely marked, never revertible)
```

`verify_stage_output_authority`'s existing step 2 (§16.3.4) — "re-look-up
`_STAGE_OUTPUT_MINTED.get(authority.mint_nonce)`; refuse `UNKNOWN_MINT_NONCE`
if absent" — **already is** the ACTIVE-authority requirement; retirement needs
no new refusal code, because a retired nonce and a nonce that was never issued
produce, deliberately, the identical refusal. Both mean exactly the same
security fact: *this nonce currently grants no authority.* Distinguishing them
would add a diagnostic nicety and zero additional security property, so the
design does not.

**Retirement ordering, frozen for every exit path:**

| Exit path | Retirement point |
|---|---|
| ordinary successful completion | immediately **after** the final permitted stage-closure write succeeds |
| ordinary halt, triggered by a *run*-record failure (§18, e.g. row 12) | immediately **after** the halt's own stage-closure write succeeds — the run-record collision itself does not retire the authority, because the stage-closure record still needs to be written using it |
| stage-output authority hard stop (§16.3.7) | **immediately upon detecting** the provenance/forgery failure — before console reporting, before process termination, and in particular before any further code could possibly run |
| L0 output-namespace preoccupation (new, FU8, §16.3.10) | **immediately upon detecting** the expected next-run path already occupied — before console reporting, before any run-scoped resource is created, identical timing to the stage-output authority hard stop above (this is not that hard stop's own cause — the authority's provenance is unaffected — but it receives the identical retirement treatment because neither leaves anything left to write into `results/`) |
| the *stage-closure record's own* emission failure — an exclusive-create collision, **or** (revised, FU6, §16.3.8.2) a validation, scrub, size-check, or write failure of the stage-closure writer itself (§17's stage-closure row) | immediately upon observing that specific failure — no fallback or replacement write is attempted for *any* of these causes, and unlike an ordinary halt there is no further durable write this authority could still be needed for. The collision case and the other emission-failure causes share this identical retirement point; they differ only in which closed status (`EMISSION_COLLISION` vs. the failure being console-only with no stage-closure record at all) reaches a reader, never in retirement timing |
| terminal-decision mint failure at L30 — any failure of the mint sequence (§16.3.8.3 requirement 6) at any point after L30 selects §19.6 branch A or branch C and begins the sealing attempt (new, FU13) | **immediately upon observing the mint failure** — before console reporting (`STAGE_DECISION_MINT_FAILED`, §21.2) and before the stage runner's own routine returns or raises out of the internal mint operation. Unconditional regardless of which of the three failure points (§16.3.8.3's "Partial-failure atomicity") was hit — before seal-history establishment, after it but before decision registration, or after registration but before object construction. No stage-closure write precedes retirement here, because no genuine decision ever existed to authorize one; the `_STAGE_OUTPUT_MINTED` entry is gone before the failure path returns or raises |

In every case, retirement is the design's own action, not a side effect a
caller must remember to trigger, and it is unconditional: whatever else a
given exit path does or fails to do, the mint is removed from
`_STAGE_OUTPUT_MINTED` before that code path's own execution ends.

**Consequence, mechanically proven (not merely stated): after retirement, for
this exact `mint_nonce`,**

- `verify_stage_output_authority` refuses at step 2, for every future call,
  from any code, holding the exact same (still `frozen=True`, still
  byte-for-byte genuine) authority object;
- every writer (§16.3.8) therefore refuses at its own step 1, since it calls
  `verify_stage_output_authority` first, unconditionally;
- no path-deriving helper, writer, or verifier of any kind can be made to
  succeed for a retired authority — there is no separate "just derive a path,
  no write" code path that skips the re-proof (§16.3.8 lists no such
  exception).

**No resumption under the same authority, ever.** A new authorization
(§14.1 item 4) requires a new `stage_execution_id`, which — via
`establish_stage_output_authority` — mints a genuinely new, independent
`mint_nonce` and registry entry. The retired entry is never reactivated, and
`mint_nonce` values are never reused (`secrets.token_hex(16)`, 128 bits, per
mint).

Regressions: T-44–T-49 (§16.3.9's own four original exit paths); T-100
(§16.3.10's new L0-preoccupation exit path, new FU8); T-137–T-139
(§16.3.8.3's new terminal-decision mint failure exit path, new FU13).

#### 16.3.10 L0 output-namespace preoccupation — a third hard-stop class (new, FU8)

**Finding 5, stated precisely.** L0 (§16.2) requires the schedule-derived
run path for the ordinal being admitted to be **absent** before that ordinal
is admitted — but the execution directory, once minted (§16.3.6), is an
ordinary directory on disk between stage-output mint and each L0 admission
check, and nothing in §16.3.4's consumption-boundary re-proof inspects its
**contents** (only the directory's own identity, symlink status, and
parentage). A file or directory could therefore be placed at the exact path
L0's internal derivation would compute for the next ordinal, **before** that
ordinal is ever admitted. **This is not a writer-boundary collision** —
§16.3.8's `FINAL_PATH_CREATE_ATTEMPTED`/`EMISSION_COLLISION` machinery
(§16.3.8.2) governs a collision a writer's own `O_EXCL` call discovers
**after** a run has already been admitted and is attempting its own
emission. Here, **no run has been admitted at all** for the affected
ordinal — L0 itself observes the occupied path during its own absence check,
before `run_id`, workspace, broker, or runtime resources of any kind exist.

**Why this cannot be encoded as an ordinary halt.** §19.2's halt rule marks
`halted_after_ordinal = k` for the **last admitted** ordinal — but no
ordinal was admitted here; admission is exactly the step that just refused.
Setting `halted_after_ordinal` to the affected ordinal would misstate it as
having been admitted and attempted (contradicting `ordinal_status`'s own
`RECORD_EMITTED`/`EVIDENCE_REFUSED`/`EMISSION_COLLISION`/`EMISSION_FAILED`
domain, none of which fit "never admitted"); setting it to the ordinal
**before** the affected one is also wrong, because that ordinal (if any) may
have completed and admitted normally, with the contamination discovered only
at the **next** L0 check. **Inventing ordinal 0, or any other synthetic
ordinal, to hold this case is explicitly rejected** — it would misrepresent
the schedule (§7.3/§7.3a define ordinals starting at 1) and would require
`ordinal_status`'s exact key set (§22.4.2) to grow a member no genuine
schedule position ever occupies.

**The correct classification: the same class of "results namespace is no
longer safe to write into" hard stop §16.3.7 already defines, extended to
this one additional trigger.** `RESULTS_ROOT`/execution-directory provenance
failing (§16.3.7) and an execution directory whose **expected next-run
path** is already occupied are both cases where continuing to admit runs
into `results/` cannot be trusted — the difference is only *which* proof
failed, not the appropriate response. L0's absence check therefore gains one
closed, console-only code, distinct from `HALT_REASON_CODES` (§19.4) for
exactly the reason §19.4 itself now states — no stage-closure record is ever
written for it:

```text
OUTPUT_NAMESPACE_PREOCCUPIED
```

**Frozen sequence, on detection:**

```text
L0 observes: the expected run path for ordinal k already exists
    ↓
zero run-scoped resources created for ordinal k
    (no run_id claim beyond the check itself, no workspace mint, no broker,
    no runtime launch — L0 is the very first step, §16.2)
    ↓
stage-output authority retired immediately
    (§16.3.9-identical timing to §16.3.7's hard stop — before console
    reporting, before any further code could possibly run)
    ↓
console-only bounded report: OUTPUT_NAMESPACE_PREOCCUPIED
    (§21.2; never the occupying file's content, size, or any raw detail
    beyond the closed code itself and the already-permitted stage/ordinal
    identifiers)
    ↓
zero run, refusal, or stage-closure writes of any kind
    (mirrors §16.3.7's own "nothing is written to results/" guarantee
    exactly — this is the same guarantee, not a weaker one)
    ↓
the pre-existing occupying file or directory is left completely untouched
    (CFG1 never inspects its content beyond the existence check that
    triggered this path, never deletes it, never overwrites it — identical
    in spirit to the post-create residue policy of §16.3.8.2, applied here
    to a namespace occupant CFG1 itself never created)
    ↓
stage ends; resumption requires a new authorization with a new
stage_execution_id (§14.1 item 4), exactly as any other halt or hard stop
```

**Distinct from an ordinary writer-boundary collision.** A genuine
`FINAL_PATH_CREATE_ATTEMPTED` collision (§16.3.8.2), discovered by a writer
**after** its own run has already been admitted at L0 and has already
proceeded through L1–L28, remains exactly `EMISSION_COLLISION` — an
ordinary, already-frozen halt cause that **does** produce a stage-closure
record (§18 row 12, §19.4's `RUN_RECORD_EMISSION_COLLISION`). The two are
never conflated: L0's own absence check, run strictly before any resource
for that ordinal exists, is a **precondition of admission itself**; a
writer's `O_EXCL` collision is a **consequence of an already-admitted run's**
own emission attempt. The frozen §16.2 L0 step text is revised to state this
check's failure mode explicitly, citing this subsection.

Regressions: T-100 (§11.3).

---

## 17. Resource ownership (FU1)

| Resource | Created by | Ownership proof held by the run | May mutate | Torn down by | Closed iff | Partial creation | Partial teardown |
|---|---|---|---|---|---|---|---|
| **Credential/connection values** (memory) | L4 frozen resolver | the run's own `ConnectionValues`/secret-context objects | nobody | reference release at run end (no erasure claim) | n/a (not a live OS resource) | refusal; nothing else exists | n/a |
| **Workspace** (fresh root + `repo/`) | L2 `build_case_repository` | CFG1 registry: `nonce → DisposableRootAuthority` (marker nonce) + single-use claim by `run_id`; re-proved by `_verify_root_authority` at every consumption | fixture builder (pre-baseline); broker operations under this run's capability; the verification child | L27 CFG1 removal after authority re-proof | `workspace_authority_reproved ∧ removed ∧ residual_file_count == 0` | authority not returned → **no deletion ever**, `INDETERMINATE_LIFECYCLE`, halt | residual or re-proof failure → `INDETERMINATE_LIFECYCLE`, halt; residual never deleted by a later run |
| **Generated Pi config dir** `<root>/cfg1_pi_config` | L9 CFG1 generator | in-memory issuance record `(run nonce, resolved dir) → token` + finalized digests (I2 FU3A pattern); dir created `exist_ok=False` inside the owned root | CFG1 generator until finalize; Pi may create additional files there at runtime | L24 verified unlink of `models.json`; L27 root removal for the rest | `models_json_scrub_verified` (and root removal) | generator self-cleans inside the owned root and discards issuance; else L27 | scrub unverified → `INDETERMINATE_LIFECYCLE`, verification skipped, halt |
| **Extension dir** `<root>/pi_extension` | L11 frozen writer | returned `GeneratedExtension` held by the run + owned root | nobody after write | L24 `scrub_generated_extension_config`; L27 | `extension_binding_scrub_verified` | L27 removes | as config dir |
| **Broker thread + named pipe** | L13 `BrokerServer.start()` | the `BrokerServer` instance constructed at L10 (the pipe name is never used as a lookup key); first-instance pipe, `max_instances=1`, current-user DACL | the broker worker only | L23 `shutdown()` on that instance | `state_reached == CLOSED ∧ pending_operations_unreaped == 0 ∧ (worker_termination_observed ∨ no worker started)` | frozen partition: A (nothing created) → nothing to close; B/C (resource, no worker) → `shutdown()` closes only what it created | `TEARDOWN_INCOMPLETE` → `INDETERMINATE_LIFECYCLE`, halt |
| **Broker session / capability / run state** | L8 SED, L10 binding + `RunState` + handler | object references created in this run; token 256-bit, only on disk in L11's file | `BrokerRequestHandler` only | withdrawn by L23; token file scrubbed at L24 | follows broker closure + L24 | discarded with the instance | follows broker |
| **Pi runtime process** | L14 `PiRpcSupervisor.launch()` | the `Popen` object held by this run's supervisor (never a PID lookup) | Pi itself | L21 `supervisor.shutdown()` ladder on that handle only | `exit_status_observed is not None` | Popen raised → no process, nothing to close; Popen returned but reader start raised → `process` is set → L21 required | `gave_up_waiting` → `INDETERMINATE_LIFECYCLE`, halt. Descendants never claimed stopped |
| **RPC transport** (stdin/stdout/stderr pipes + two reader threads) | L14 | the same supervisor; command ids unique to this run | supervisor only | L21 (stdin close) + bounded EOF wait | `stdin_closed ∧ stdout_eof ∧ stderr_eof` | as runtime | EOF not observed (for example a descendant holding the pipe) → `INDETERMINATE_LIFECYCLE`, halt |
| **Verification child** | L26 frozen runner | the runner's own process handle for this invocation | repository-controlled code | the frozen runner's bounded wait + reap grace | `return_code is not None` (completed, or killed and reaped) | launch error → `verification_started=false`; nothing to close | timed out with `return_code is None` → `INDETERMINATE_LIFECYCLE`, halt. The abandoned reader thread is the documented runner residual, not a CFG1 resource |
| **Stage output authority** (§16.3, in-memory only) | stage runner, once, before ordinal 1, via `establish_stage_output_authority` | the `_STAGE_OUTPUT_MINTED[mint_nonce]` registry entry (§16.3.3); direct construction fails `__post_init__` without it (T-25); re-proven fresh, including its **ACTIVE** state (§16.3.9), at every consumption boundary, never trusted from a cached prior check (§16.3.4) | nobody (frozen dataclass; a bypassed mutation is caught at the next re-proof, T-27) | nothing (never a live OS resource beyond the one `mkdir` at construction) | n/a — validity is re-established per call, not "closed" once | root or directory provenance failure → hard stop, §16.3.7 (no stage-closure record, immediate retirement); nothing created but `RESULTS_ROOT` itself, which pre-exists the stage on every run after the first | **retired** (registry removal, §16.3.9) on every exit path — successful completion, ordinary halt, hard stop, or a stage-closure emission failure of any kind (collision or otherwise, FU6, §16.3.8.2); never merely "goes out of scope" |
| **Sealed stage decision** (§16.3.8.3, in-memory only, new FU9, issuance closed FU10, cardinality corrected FU11, seal-once mechanism separated from consume-once FU12) | at an L30 evaluation that selects §19.6 branch A or branch C — **at most once per `CFG1StageOutputAuthority`, never once per L30 evaluation** (L30 itself runs once per admitted ordinal, up to nine times for `S1` and six for `S2`; branch B, the ordinary non-final-ordinal case, never invokes the sealing step at all, T-107/T-126) — via the stage runner's own lexically-owned sealing step (no longer a caller-parameterized function, FU10), reading the stage-progress ledger (§16.3.8.4) after the current ordinal's L29 emission result is known, and only after the seal-history check below (§16.3.8.3 requirement 6 step 2) passes | the `_STAGE_DECISION_SEALED[decision_nonce]` registry entry (§16.3.8.3); direct construction fails `__post_init__` without it (T-103); re-verified fresh at the stage-closure writer's own consumption, never trusted from a cached prior check. **This registry proves decision authenticity/consumability only — since FU12 it is no longer relied on as the seal-once proof; see the separate "Terminal-seal history" row below for that** | nobody (frozen dataclass; a bypassed mutation is caught at the next re-verification, T-104) | nothing (never a live OS resource; never itself written to disk) | n/a — read exactly once, by exactly one consumer, immediately after sealing | **corrected, FU12:** a second terminal-seal attempt for the same `authority.mint_nonce` is refused by the separate `_STAGE_TERMINAL_SEAL_HISTORY` fact (see the row below), **not** by this registry, which a first decision's own consumption has by then already cleared (T-107); a seal attempt before the current ordinal's L29 result exists in the ledger cannot occur by construction (T-106); no supported caller holding only `authority` can reach the sealing step, or supply/replace/obtain the stage-progress ledger, through any supported API (T-124, T-125, new FU10, scoped FU11) | **revoked at the start of the one consumption attempt** (this registry's entry removed, `emit_cfg1_stage_closure` step 4a, new FU10) — **and this revocation is scoped to this registry only; it never touches the separate seal-history fact below** (scope corrected, FU12) — not merely "goes unused," a second consumption of the same decision fails identically to an unsealed one (T-132); never reused, never rebound (T-105), and carries no authority beyond that one consumption |
| **Terminal-seal history** (§16.3.8.3 requirement 6, in-memory only, new FU12) | the local sealing step, at requirement 6 step 3, before the decision itself is registered (step 4) or constructed (step 5) | the `_STAGE_TERMINAL_SEAL_HISTORY` entry for `authority.mint_nonce` — established exactly once, on the first attempt to reach step 3; a second sealing-step reach for the same `authority.mint_nonce`, at any later point including after a first decision has already been sealed and fully consumed, finds this entry present and refuses at step 2, before any decision registration or construction (T-107) | nobody (a plain history fact, not a mutable object with fields; no supported code path clears an established entry) | nothing (never a live OS resource; never itself written to disk; never exposed through any supported API, mirroring the stage-progress ledger's own unreachability, §16.3.8.4) | survives at least: decision sealing, the entire first stage-closure writer attempt, that attempt's success or failure, and stage-output-authority retirement; continues until the stage runner has irreversibly left every code path capable of reaching the sealing step for that authority ("Terminal-seal history lifetime," §16.3.8.3 requirement 6) | a failure between establishing this fact (step 3) and registering/constructing the decision (steps 4–5) leaves the fact durably set and the stage permanently, and by design irrecoverably, unable to complete a terminal seal — a stranded, fail-closed state, never reopened, and never a source of an apparently-genuine-but-unauthenticated decision object ("Partial-failure atomicity of the mint sequence," §16.3.8.3 requirement 6; T-135) | **never removed by decision consumption** — `emit_cfg1_stage_closure` step 4a revokes only the separate `_STAGE_DECISION_SEALED` consumability entry above and has no authority over this fact (T-133); discarded only as bounded process-memory cleanup after the stage runner's own lifetime for that authority has irreversibly ended, never before (T-136) |
| **Execution directory** `RESULTS_ROOT/<validated stage_execution_id>` | §16.3.6, inside `establish_stage_output_authority` | the mint registry's `execution_directory` field (§16.3.3), containment-proven (§16.3.5) against a §16.3.2-proven `RESULTS_ROOT` (Level A + Level B); re-`lstat`-proven at every consumption boundary (§16.3.4) | the `emit_cfg1_*` writers only (§16.3.8), each of which internally derives its own path and re-proves first — no caller ever supplies a path | never by CFG1 (no deletion path exists) | n/a | grammar/type/containment failure → nothing created; pre-existing directory → stage refuses, §16.3.6; package-parent redirect → refused before `RESULTS_ROOT` is even considered, §16.3.2 Level A | a post-mint redirect (delete + symlink) is refused at the **next** consumption boundary, §16.3.4 → hard stop, §16.3.7 |
| **Results path** `<execution_directory>/<stage>_<ordinal>_<arm>.json` | `emit_cfg1_run_record`/`emit_cfg1_refusal_record` (§16.3.8), called with `(authority, run_ordinal, payload)` only — never a path, filename, or `arm_id` argument | the `O_CREAT \| O_EXCL` create itself; the path is derived **internally by the writer** from the stage authority and the schedule-arm function, never accepted as an argument or as a previously-returned value (§16.3.8 Finding 1) | nobody after write | **never** by CFG1 (§16.3.8.2's post-create residue policy: no overwrite, no truncate, no rename, no unlink by pathname, ever) | n/a | **corrected, FU7 — outcome depends on the emission phase reached (§16.3.8.2):** a `PRE_CREATE` bounded run-record validation/scrub failure → **zero** final-path writes, at most one non-recursive refusal-record attempt at the same path, itself either succeeding (`EVIDENCE_REFUSED`) or itself failing `PRE_CREATE` (`EMISSION_FAILED`, T-83/T-86) or post-create (`EMISSION_FAILED`, residue left untouched, T-85/T-86); a collision at `FINAL_PATH_CREATE_ATTEMPTED` → no fallback, `EMISSION_COLLISION`; any post-create failure of the primary writer (write/flush/close, or an ambiguous create-time error, T-84/T-95, §18 row 18) → no fallback, `EMISSION_FAILED`, residue (if any) left untouched — every `EMISSION_FAILED`-producing case, whichever of the three it is, carries the identical, deliberately neutral `halt_reason_code == RUN_RECORD_EMISSION_FAILED` (§19.4 Finding 1, FU8) — in every one of these outcomes the stage halts except an ordinary `PRE_CREATE` scrub-triggered `EVIDENCE_REFUSED` (§19.3) | n/a |
| **Stage-closure record** `<execution_directory>/<stage>_stage_closure.json` | `emit_cfg1_stage_closure` (§16.3.8, adapted §16.3.8.3), called with `(authority, decision)` only — **never** a caller-supplied `payload` (revised, FU9 Finding 1; §16.3.8.3) | exclusive create; same authority as run records, path derived internally, identically; the closure-fact content is derived from a genuine, re-verified, authority-bound `decision` (§16.3.8.3), never from caller input | nobody after write | **never** by CFG1 (same post-create residue policy as the results path — §16.3.8.2) | n/a | any emission failure — a `PRE_CREATE` validation/scrub/size failure, a `FINAL_PATH_CREATE_ATTEMPTED` collision (classified and reported identically to a non-collision failure at the live-outcome level, distinguished only optionally at the console-only diagnostic level, FU9 Finding 3), or a post-create write/flush/close failure, whatever residue that last case may leave behind — → console only, halt already in effect, authority retired (§16.3.9); **never** a refusal-record fallback of any kind, and any partial residue is never treated as a successful closure record | n/a |

**Never, by construction:** kill a process by name or enumerate PIDs; shut down a
broker instance this run did not construct; delete a root absent from this run's
registry or failing re-proof; reuse a supervisor, broker instance, binding, SED,
command id, workspace, or config directory from another run; accept a resource
id, path, pipe name, or token from a caller, a file, or an earlier record; or
(new, FU9) accept a caller-selected `ordinal_status`, `halted_after_ordinal`,
or `halt_reason_code` as independent stage-closure-payload authority — the
stage-closure writer accepts only a genuine, re-verified, authority-bound
`CFG1StageClosureDecision` sealed exclusively by L30 (§16.3.8.3); or (new,
FU10) expose stage-decision sealing as a module-level, importable, or
otherwise externally-reachable callable parameterized by `ordinal_status`,
`halted_after_ordinal`, or `halt_reason_code` at all — a supported caller
holding only a genuine, ACTIVE `CFG1StageOutputAuthority` has no name, no
attribute path, and no object-graph edge leading to the sealing step
(§16.3.8.3 requirement 9); reuse a sealed decision for a second stage-closure
emission attempt (§16.3.8.3's "Decision lifetime," T-132); issue an
admission token for an ordinal the stage's own frozen schedule never
declares (§19.6 branch C exists precisely so this never needs to be
considered); or (new, FU12) let a consumed decision's own revocation
(`_STAGE_DECISION_SEALED`, step 4a) erase the independent fact that its
authority already sealed a terminal decision — the two registries are
disjoint, and a second, genuinely different decision can never be sealed
for the same `CFG1StageOutputAuthority` regardless of what has happened to
a first decision's own consumability (§16.3.8.3 requirement 6's
`_STAGE_TERMINAL_SEAL_HISTORY`, T-107).

---

## 18. Partial-failure semantics (FU1)

"Prompt sent?" means **whether a prompt write reached Pi's stdin**. It is never a
claim that a model request did or did not occur.

| # | Failure | Prompt sent? | Resources still requiring closure | Stage halts? | Retained run classification |
|---|---|---|---|---|---|
| 1 | broker constructed, `start()` raises or READY not reached (L13) | no | broker (partition B/C), config, extension, workspace | **yes** | `REFUSED_PRE_DISPATCH(BROKER_NOT_READY)`; `INDETERMINATE_LIFECYCLE` if any closure unproven |
| 2 | broker READY, Pi launch fails (L14) | no | runtime only if `process` was set; broker; config; extension; workspace | **yes** | `REFUSED_PRE_DISPATCH(RUNTIME_LAUNCH_FAILED)`, or `INDETERMINATE_LIFECYCLE` |
| 3 | Pi launched, RPC correlation / H1 / H2 / protocol integrity / manipulation check fails (L15–L16) | no | runtime, transport, broker, config, extension, workspace | **yes** | `REFUSED_PRE_DISPATCH(RUNTIME_CORRELATION_FAILED \| H2_MISMATCH \| CONFIG_SHAPE_MISMATCH)`, or `INDETERMINATE_LIFECYCLE` |
| 4a | prompt write raised, or no correlated response by the deadline, or stream terminal before response (L18) | **possibly** (`SEND_STATE_INDETERMINATE`) | full closure L21–L27 | no, if lifecycle closed | `INDETERMINATE_DISPATCH`; never a second write |
| 4b | correlated response with `success: false` (L18) | written to Pi, **not dispatched to a model** (`CONFIRMED_NOT_SENT`) | full closure | **yes** (systematic runtime refusal) | `REFUSED_PRE_DISPATCH(PROMPT_REFUSED_BY_RUNTIME)` |
| 5 | turn observation fails: protocol violation, output/event cap, read error, exited early, or deadline (L19) | yes | full closure | no, if lifecycle closed | stream terminals → `INDETERMINATE_RUNTIME_STREAM`; deadline or early exit → §12 rows 5–11 with basis `wait_ended_before_settled` |
| 6 | verification times out (L26) | yes | verification child (reap), workspace | only if `return_code is None` | reaped → classification unaffected, `verification_timed_out=true`; unreaped → `INDETERMINATE_LIFECYCLE` |
| 7 | runtime teardown fails: exit not observed or transport EOF not observed (L21) | yes, or no if pre-dispatch | broker (still shut down: withdraws capability), scrub, workspace removal attempted; **verification skipped** | **yes** | `INDETERMINATE_LIFECYCLE` |
| 8 | broker shutdown fails, `TEARDOWN_INCOMPLETE` (L23) | either | scrub; Git observation #1 allowed (read-only); **verification skipped**; workspace removal attempted | **yes** | `INDETERMINATE_LIFECYCLE` |
| 9 | config or extension scrub unverified (L24) | either | Git observation #1 allowed; **verification skipped**; workspace removal attempted | **yes** | `INDETERMINATE_LIFECYCLE` |
| 10 | workspace removal fails or authority re-proof fails (L27) | either | none further (residual left untouched) | **yes** | `INDETERMINATE_LIFECYCLE` |
| 11 | record fails `qualification_scrub_check` (L29) | either | none (all closure already finalized) | **no**, if `lifecycle_all_closed` (§19.3) | CFG1 refusal record written at the run path; emission status `EVIDENCE_REFUSED`; arm indeterminate |
| 12 | **the primary run-record writer's own** exclusive-create collides at `FINAL_PATH_CREATE_ATTEMPTED` (L29, phase term FU7, §16.3.8.2). **Distinct from row 19: this row is the primary writer's own collision; row 19 is the refusal writer's own collision, classified identically but at a different attempt** (scope clarified, FU9 Finding 3 — collision is never a primary-writer-only concept) | either | none | **yes** | nothing written **by this run** (a collision means the path was already occupied before this attempt — this specific case's "nothing written" claim remains mechanically true, unlike row 16 below); no fallback/replacement path attempted; emission status `EMISSION_COLLISION` in the stage-closure record and console. This is a *run*-record collision, which halts the stage: the stage-output authority is retired via the ordinary-halt path (§16.3.9), after the stage-closure record itself is written — never immediately, since that record still needs to be written here. **A collision on the stage-closure record's *own* write is different** (§17's stage-closure row): there, no further durable write is possible at all, so retirement happens immediately, matching the hard-stop timing |
| 13 | L2 raises before an authority object is returned | no | an orphan temp root may exist; **ownership unprovable, never deleted** | **yes** | `INDETERMINATE_LIFECYCLE` (reason `WORKSPACE_MINT_PARTIAL`) |
| 14 | L3 baseline verification child unreaped | no | workspace | **yes** | `INDETERMINATE_LIFECYCLE` |
| 15 | record self-validation fails (L29, before scrub — always a `PRE_CREATE`-class failure, since step 6 precedes step 10 entirely) | either | none | **yes** (implementation defect; `halt_triggered_by_this_run` is unconditionally `true` here, independent of the refusal artifact's own outcome — §16.3.8.2, §19.1 item 2) | refusal record with `refused_record_kind` and finding code `RECORD_INVARIANT`; emission status `EVIDENCE_REFUSED` if that refusal artifact itself was written, `EMISSION_FAILED` (FU6) if it was not — either way the stage halts |
| 16 | **a fallback was attempted and that fallback's own emission then fails for a non-collision reason** — the row-11/row-15 refusal writer's **own** `PRE_CREATE` failure (construction, canonicalization, schema validation against `_require_valid_cfg1_refusal_payload`, authority binding, scrub, size check), its own non-collision/ambiguous `FINAL_PATH_CREATE_ATTEMPTED` failure, or its own post-create (write, flush, or close) failure (L29, FU6, phase distinction FU7, non-collision scope narrowed FU9 — see row 19 for its own collision). **Distinct from row 18: here a `PRE_CREATE` primary failure made a fallback eligible and it was attempted; row 18 is the case where no fallback is ever attempted at all** (scope clarified, FU8) | either | none | **yes** | **corrected, FU7: "nothing written" holds only for the `PRE_CREATE` sub-case (T-83/T-75) — a post-create or non-collision-create sub-case may leave partial or full bytes at the run path, which are left untouched and are never authoritative (T-85/T-96/T-118).** No second fallback is attempted in any sub-case (`emit_cfg1_refusal_record` never retries itself); emission status `EMISSION_FAILED` in the stage-closure record and console, with `halt_reason_code == RUN_RECORD_EMISSION_FAILED` (renamed from `RUN_RECORD_REFUSAL_FALLBACK_FAILED`, FU8 Finding 1 — see §19.4) — **not** `EVIDENCE_REFUSED` (no successfully-confirmed refusal artifact exists) and **not** `EMISSION_COLLISION` (this row is defined as the non-collision case; see row 19 for the refusal writer's own collision) |
| 17 | the stage-closure record's **own** emission fails, for **any** cause — `PRE_CREATE` (validation against `_require_valid_cfg1_stage_closure_payload`, scrub, or size check), its own `FINAL_PATH_CREATE_ATTEMPTED` collision, its own non-collision/ambiguous create failure, **or** post-create (write, flush, or close) (L30, FU6, phase distinction FU7, collision folded in as one more uniformly-handled cause FU9 Finding 3 — **the stage-closure writer never has a refusal fallback of any kind, so unlike rows 12/16/19 there is no reason to carve collision out as a separately-numbered row here: every cause of this writer's own failure resolves identically**, §16.3.8.2) | either | none | **yes** (halt was already in effect; this is the closure write itself failing) | no **valid** stage-closure record exists for this stage execution (a post-create or non-collision-create sub-case may leave untouched, non-authoritative residue whose live emission result is nonetheless `FAILED` regardless of that residue's own later parseability — T-87/T-98/T-99); console-only bounded reporting, optionally with a code distinguishing collision from non-collision for operator diagnosis (§16.3.8.2) but **never** a durable `halt_reason_code` (no stage-closure record exists to carry one); the stage-output authority is retired immediately (§16.3.9's stage-closure row); **never** a refusal-record fallback (`emit_cfg1_stage_closure` never calls the refusal writer, at any phase, for any cause) |
| 18 | **the primary run-record writer's own non-collision failure at or after `FINAL_PATH_CREATE_ATTEMPTED`, with zero fallback attempts** — its own non-collision/ambiguous create-attempt failure (broadened, FU9 Finding 3 — a gap in the FU8 wording, which described only the write/flush/close sub-case), **or** write, flush, or close fails after that writer's own successful exclusive-create (FU8 Finding 1) (new, FU8 Finding 1; §16.3.8.2's corrected eligibility rule: `FINAL_PATH_CREATE_ATTEMPTED` was already reached by the *primary* writer, so no `PRE_CREATE`-only fallback is ever eligible for this failure, regardless of how "close" the failure is to a successful emission, or how early within `FINAL_PATH_CREATE_ATTEMPTED` it occurs). **Distinct from row 12: row 12 is this same writer's own *collision*; this row is every other cause** | either | none | **yes** | zero refusal-fallback attempts (spy-proven, T-95); any residue is left untouched and never authoritative (T-85's discipline applied to this exact sub-case); emission status `EMISSION_FAILED` in the stage-closure record and console, with the **identical** `halt_reason_code == RUN_RECORD_EMISSION_FAILED` row 16 produces — the two rows are indistinguishable in this closed field by design (§19.4, T-96) |
| 19 | **the refusal writer's own collision, at its own `FINAL_PATH_CREATE_ATTEMPTED`** (new, FU9 Finding 3 — collision is never a primary-writer-only concept; classified identically to row 12's primary-writer collision, at a structurally different attempt) | either | none | **yes** | nothing written **by the refusal writer** for this specific attempt (the path was already occupied before this attempt); no further fallback of any kind (the refusal writer never retries itself regardless of cause, unchanged from row 16/T-73); occupant never overwritten, deleted, or reused; emission status `EMISSION_COLLISION` in the stage-closure record and console, with `halt_reason_code == RUN_RECORD_EMISSION_COLLISION` — **identical treatment to row 12**, the only difference being which writer's own create call collided |
| 20 | **the terminal-decision mint sequence fails, at any of its three failure points (§16.3.8.3 requirement 6's "Partial-failure atomicity"), after L30 has selected §19.6 branch A or branch C and begun sealing (new, FU13).** No genuine `CFG1StageClosureDecision` exists in any of the three sub-cases, so `emit_cfg1_stage_closure` is never called — **this is its own authority-bearing failure boundary, not the stage-closure writer's own emission failure (row 17): row 17 presupposes a genuine sealed decision already exists and the writer's own attempt to persist it then fails; this row is the decision never coming to exist at all** | either | none | **yes** (there is no next ordinal to admit; no live runtime/broker/workspace remains at this point) | zero stage-closure writer calls (spy-proven, mirroring T-97's zero-I/O discipline, applied one step earlier); zero stage-closure artifacts written; the stage-output authority retired immediately, before console reporting (§16.3.9's new row); exactly one bounded console-only report, `STAGE_DECISION_MINT_FAILED` (§21.2) — **never** a `halt_reason_code`, **never** a member of `HALT_REASON_CODES` (§19.4), and **never** raw exception text, `repr`, or traceback; every already-confirmed run/refusal artifact for this stage execution left untouched; no automatic retry or recovery path, under any of the three sub-cases; the stage is unusable for interpretation, exactly as row 17 already is |

Closure dependencies, restated: L23 always runs if L13 created a resource,
whatever L21's outcome. L24 always runs if L9/L11 wrote. L26 requires L21 ∧ L23 ∧
L24 proven. L27 always runs if L2 returned an authority. A closure step never
repairs, retries, or escalates beyond the frozen ladder of the module it calls.

---

## 19. Cross-run contamination and halt rule (FU1)

### 19.1 Admission token

Run *k*+1 may be admitted (L0) only if run *k* produced an in-memory admission
token, issued at L30 iff **all** of:

1. `lifecycle_all_closed == true` — runtime exit observed, transport EOF
   observed, broker `CLOSED` with no unreaped operation, config and extension
   scrubs verified, verification child reaped (or verification not started),
   workspace authority re-proved and removal verified with zero residual;
2. `run_classification != REFUSED_PRE_DISPATCH`, **and, independently,
   `halt_triggered_by_this_run == false`** (revised, FU6). The second clause
   is not redundant with the first: §18 row 15's record self-validation
   failure sets `halt_triggered_by_this_run = true` **regardless of whether
   its own permitted refusal fallback succeeded**, so an `EVIDENCE_REFUSED`
   emission status alone (item 3 below) is not sufficient to distinguish an
   ordinary, non-halting scrub refusal (row 11) from an implementation-defect
   halt whose refusal artifact happened to succeed (row 15) — only this bool
   does, and it is what makes "a successfully written refusal artifact does
   not convert an implementation defect into an admissible next run"
   (§16.3.8.2) a mechanical admission-rule fact rather than a claim resting on
   prose alone. **`halt_triggered_by_this_run` is an in-memory L30 fact
   only (FU8 Finding 2): it is computed here, at L30, after L29's emission
   outcome is already known, and is never written into the run record's own
   durable payload (§22.2/§22.3) — a payload-only validator could not
   recompute a fact about its own not-yet-decided emission future. Its
   durable trace, when the run is the one that halted the stage, is the
   stage-closure record's `halt_reason_code` (§19.4), never a field on the
   run record itself;**
3. emission status ∈ {`RECORD_EMITTED`, `EVIDENCE_REFUSED`} — never
   `EMISSION_COLLISION`, never `EMISSION_FAILED` (new, FU6: a run whose
   emission failed and whose one permitted refusal fallback also failed
   admits nothing, exactly as a collision does not), never an invariant
   self-failure whose refusal artifact did not succeed;
4. the CFG1 workspace registry, config issuance registry, and live-object
   references for run *k* are empty;
5. **`k != LAST_ORDINAL(authority.stage_id)` (new, FU10, §19.6).** Items 1–4
   are the admission conditions §19.4/§19.5's `HALT_REASON_CODES` and
   precedence already exist to classify a *failure* of. Item 5 is different
   in kind: it never fails in the sense of indicating a defect — when items
   1–4 all hold and `k == LAST_ORDINAL(authority.stage_id)`, the run was
   completely ordinary and successful, but there is no ordinal *k*+1 for a
   token to name. **This is not a halt** (§19.2's closing paragraph) — see
   §19.6 for the exact three-way transition this item selects between.

The token is single-use and names ordinal *k*+1 only. It is never persisted and
never derived from a file.

### 19.2 Halt

Otherwise — meaning items 1–4 above, never item 5 alone (§19.6 branch C is
the case item 5 alone selects, and it is not this section) — the stage
**HALTS**:

- the completed run's safe evidence is retained where L29 can still seal it;
- the stage-closure record marks `halted_after_ordinal = k` with a closed
  `halt_reason_code`;
- every later ordinal is `NOT_EXECUTED`, and its arm is indeterminate;
- no next-run resource of any kind is created;
- resumption requires a new authorization (§14.1 item 4).

**Three narrow exceptions (§16.3.7 FU3; §16.3.10 new, FU8; §16.3.8.3 new,
FU13): none writes a stage-closure record at all.**

1. **A stage-output authority failure** (§16.3.7) — `RESULTS_ROOT` or the
   execution directory failing provenance, at establishment or at any later
   consumption-boundary re-proof.
2. **L0 output-namespace preoccupation** (§16.3.10, new FU8) — the
   schedule-derived path for the ordinal about to be admitted already exists,
   discovered by L0's own absence check **before** that ordinal is admitted,
   so there is no admitted run for `halted_after_ordinal` to name.
3. **Terminal-decision mint failure** (§16.3.8.3, new FU13) — the mint
   sequence fails, at any of its three failure points, after L30 has already
   selected §19.6 branch A or branch C and begun the sealing attempt, so no
   genuine `CFG1StageClosureDecision` ever exists for `emit_cfg1_stage_closure`
   to be called with.

Every other halt cause above still writes a stage-closure record; these
three are the only cases where either the container a stage-closure record
would need is itself what failed provenance (case 1), no run was ever
admitted for the affected ordinal in the first place (case 2), or no
genuine terminal decision was ever minted to author one (case 3), so no
write into `results/` is attempted in any. Reporting is console-only
(§21.2) for all three, and run records genuinely written before the failure
was discovered remain on disk, individually trustworthy. **The stage-output
authority is retired (§16.3.9) immediately upon detecting the failure,
before console reporting, in all three cases** — the earliest point in
every other halt case's own sequence, since here there is no closure write
to sequence it after.

Rationale: after uncertain teardown, a later arm could share a live process,
pipe, broker, workspace, or on-disk endpoint/token with an earlier one. Arms would
then no longer differ only by compat configuration.

**Reaching the stage's own final declared ordinal with items 1–4 all
satisfied is explicitly not a halt (new, FU10).** A stage-closure record is
still written — a stage cannot end without one, except the two exceptions
above — but it is written as **ordinary successful completion**: a
**SUCCESS** `CFG1StageClosureDecision` (§16.3.8.3, §19.6 branch C), never a
HALTED one, and this section's own bulleted consequences above (retained
"safe evidence," `halted_after_ordinal = k` with a closed `halt_reason_code`,
later ordinals `NOT_EXECUTED`) do not apply to it — §19.6 states the correct,
disjoint consequences for that branch.

### 19.3 Why evidence refusal (row 11) does not halt

By L29, every resource the run created has a finalized closure outcome, and
`lifecycle_all_closed == true` is a precondition for not halting. The refusal
path writes only one exclusive-create file whose name derives from ordinal *k*.
It holds no handle, touches no other path, and gives run *k*+1 nothing it
consumes: run *k*+1 mints fresh roots, pipes, bindings, supervisors and command
ids, and reads nothing from the results directory. Therefore it cannot
contaminate the next run. It does make that run's arm indeterminate (§12.3).

**Row 15 is not row 11 (FU6).** Row 15's record self-validation failure is an
**implementation defect**, not an ordinary scrub-needle hit, and §18 row 15
sets `halt_triggered_by_this_run = true` unconditionally — independent of
whether the row's own refusal-fallback attempt succeeded. §19.1 item 2 checks
this bool directly, so row 15 halts the stage even on an `EVIDENCE_REFUSED`
outcome, and the rationale above (no handle held, no path touched, nothing
run *k*+1 consumes) is deliberately **not** extended to it: an implementation
defect that corrupted one record's own internal consistency is exactly the
class of event this design chooses not to treat as "safely isolated," even
though the mechanical isolation argument above would, by itself, apply
equally to it. The distinction is a design choice about defect handling, not
a gap in the isolation proof.

### 19.4 Exact `HALT_REASON_CODES` vocabulary — the stage-closure record's sole durable authority (new, FU7; run-record authority removed, code corrected, FU8)

**Finding 3 (FU7), stated precisely.** §22.4.2's pre-FU7 text described
`halt_reason_code` as a "closed enum, non-exhaustive minimum, extended with
each new halt-capable failure this or a future revision adds" — which is not
a closed vocabulary at all; "non-exhaustive" and "extended... adds" are the
opposite of frozen. FU7 defined the complete, exact set.

**Finding 1 (FU8), stated precisely.** FU7's `RUN_RECORD_REFUSAL_FALLBACK_FAILED`
code was mapped to **every** `EMISSION_FAILED` outcome, including the
primary run writer's own direct post-create write/flush/close failure
(§16.3.8.2 Finding 1) — a case in which, by §16.3.8.2's own frozen
eligibility rule, **no refusal fallback is ever attempted at all**. Naming
that outcome "refusal fallback failed" is a false attribution: it asserts a
fallback attempt that never happened. The code is renamed to a truthful,
attribution-neutral literal covering every case that resolves to
`EMISSION_FAILED`, without claiming which specific writer step failed:

```text
RUN_RECORD_EMISSION_FAILED
```

**This one code covers, without distinguishing among them in this closed
field:**

```text
a direct post-create primary-writer failure, with zero refusal-fallback
    attempts (§16.3.8.2's corrected Finding-1 eligibility rule)

a PRE_CREATE primary-writer failure whose one permitted refusal-fallback
    attempt itself later fails, at any phase (§16.3.8.2's non-recursion rule)

a refusal-writer's own post-create failure (§16.3.8.2's residue policy)
```

**Which of the three actually happened is never claimed by this closed
field** — it is exactly the kind of fine-grained, potentially-sensitive
operational detail §21's reduction rule already keeps out of any durable
sink; console-only bounded diagnostics may distinguish them (§21.2), but
`halt_reason_code` never does, in either direction: it does not narrow to
one sub-case, and it does not (as FU7's name accidentally implied) assert a
specific sub-case occurred.

**Finding 2 (FU8), stated precisely.** FU7 also stated this vocabulary was
"used by both" the run record's and the stage-closure record's
`halt_reason_code` fields. §22.2/§22.3 (FU8) remove `halt_reason_code` (and
`halt_triggered_by_this_run`) from the durable run-record schema entirely —
see the note preceding §22.3 — because neither is recomputable from a
payload-only validator at run-record-validation time: both depend on this
very run's own emission outcome (§19.1 item 3) and registry state (item 4),
neither of which exists until **after** the run record's own emission has
already resolved. **This vocabulary is therefore the stage-closure record's
sole durable authority** (§22.4.2) for whether the stage halted, after which
ordinal, and why — restated from §22.3's note: a run record states
pre-emission facts; the stage-closure record states post-emission admission
facts. The vocabulary also remains an **in-memory-only** L30 computational
concept (§19.1 item 2's `halt_triggered_by_this_run`/its associated reason),
consumed immediately by the admission decision and never durably written
except via the stage-closure record.

**Derivation, not invention.** Every halt this design can produce is, by
construction, exactly a failure of one of §19.1's own four, already-frozen
admission conditions — that is what "the stage HALTS" (§19.2) *means*: no
admission token was issued, because at least one of items 1–4 failed. So the
complete `HALT_REASON_CODES` set is not a fresh enumeration of every §18 row;
it is **one code per §19.1 admission condition**, with item 2 split into its
two independent clauses (a `REFUSED_PRE_DISPATCH` classification and a
`halt_triggered_by_this_run` implementation-defect flag are independent
facts, and either alone forces a halt):

```text
PRE_DISPATCH_REFUSAL
    §19.1 item 2, clause 1 (run_classification == REFUSED_PRE_DISPATCH) —
    §18 rows 1, 2, 3, 4b, whenever lifecycle_all_closed remains true for
    that run

LIFECYCLE_CLOSURE_UNPROVEN
    §19.1 item 1 (lifecycle_all_closed == false) — §18 rows 1, 2, 3, 4a, 5,
    6, 7, 8, 9, 10, 13, 14, whenever the run's own classification is
    INDETERMINATE_LIFECYCLE rather than a clean pre-dispatch refusal

RUN_RECORD_SELF_VALIDATION_FAILED
    §19.1 item 2, clause 2 (halt_triggered_by_this_run == true) — §18 row
    15, the record-self-validation implementation defect (§16.3.8.2)

RUN_RECORD_EMISSION_COLLISION
    §19.1 item 3, EMISSION_COLLISION — §18 row 12: a genuine
    FINAL_PATH_CREATE_ATTEMPTED collision, no fallback ever eligible

RUN_RECORD_EMISSION_FAILED
    §19.1 item 3, EMISSION_FAILED — §18 row 16, renamed from FU7's
    RUN_RECORD_REFUSAL_FALLBACK_FAILED (Finding 1, FU8): a truthful, neutral
    code covering all three EMISSION_FAILED-producing cases listed above,
    never asserting a fallback was attempted when it was not

RUN_SCOPED_REGISTRY_NOT_EMPTY
    §19.1 item 4 (the CFG1 workspace registry, config issuance registry, or
    live-object references for the halting run are not empty) — a defensive
    condition not independently exercised by any single §18 row in the
    ordinary case, since item 1's closure proof already implies it, but
    retained as its own code because item 4 is its own, independently
    stated admission condition and a validator must have somewhere to put
    a halt driven by it if it is ever the *only* condition that failed
```

Exactly six members, unchanged in count from FU7 (one renamed). No other
value is accepted by the stage-closure record's `halt_reason_code` field
(§22.4.2) — the **only** durable field this vocabulary populates (FU8
Finding 2; it is never a run-record field, and it is also the in-memory L30
concept §19.1 item 2 computes and consumes before any stage-closure write).

**Four cases are explicitly excluded, because none of them writes a
`halt_reason_code` anywhere — none writes a stage-closure record at all
(count corrected from "two" to "three" by FU9 Finding 4, and from "three" to
"four" here by FU13):**

- the stage-output-authority hard stop (§16.3.7) writes **no** stage-closure
  record at all (§19.2's first narrow exception) — there is no record field
  for a code to occupy;
- the stage-closure record's **own** emission failure (§18 row 17,
  §16.3.8.2) likewise writes **no** stage-closure record — the very record
  that would carry the code is what failed to be written, so, symmetrically
  with §16.3.7, no code is needed or accepted for it;
- the L0 output-namespace-preoccupied hard stop (new, FU8 Finding 5, §16.3.10)
  likewise writes **no** stage-closure record — no run has yet been
  admitted for the affected ordinal, so there is no ordinal for
  `halted_after_ordinal` to name and no record for a code to occupy; its own
  closed console-only code, `OUTPUT_NAMESPACE_PREOCCUPIED`, is a **separate**
  vocabulary from `HALT_REASON_CODES` for exactly this reason (§16.3.10);
- the terminal-decision mint failure (new, FU13, §16.3.8.3, §19.2's third
  narrow exception) likewise writes **no** stage-closure record — no genuine
  `CFG1StageClosureDecision` ever exists for one, so there is no
  `halted_after_ordinal` to name and no record for a code to occupy; its own
  closed console-only code, `STAGE_DECISION_MINT_FAILED`, is a **separate**
  vocabulary from `HALT_REASON_CODES` for the identical reason
  `OUTPUT_NAMESPACE_PREOCCUPIED` already is — there is no durable record in
  which either code could truthfully live.

### 19.5 Exact L30 halt-reason precedence, one shared function (new, FU9 Finding 2)

**Finding 2, stated precisely.** Multiple §19.1 admission conditions can
fail simultaneously for the same run — for example a run whose emission
outcome is `EMISSION_FAILED` (item 3) may *also* have
`lifecycle_all_closed == false` (item 1), if the same underlying defect that
broke emission also left a closure step unproven. The stage-closure record
has exactly **one** `halt_reason_code` per halted ordinal. Without a frozen,
deterministic precedence, two independently-written implementations of L30
— or the same implementation on two different runs of the same failure
class — could durably record different codes for mechanically identical
situations, which is exactly the kind of non-reproducible evidence this
design exists to rule out.

**The frozen precedence, evaluated in order, first match wins — one shared
function, never independently reimplemented by the stage-closure validator
or writer:**

```text
1. emission_status == EMISSION_COLLISION
       -> RUN_RECORD_EMISSION_COLLISION

2. emission_status == EMISSION_FAILED
       -> RUN_RECORD_EMISSION_FAILED

3. halt_triggered_by_this_run == true
       -> RUN_RECORD_SELF_VALIDATION_FAILED

4. lifecycle_all_closed == false
       -> LIFECYCLE_CLOSURE_UNPROVEN

5. run_classification == REFUSED_PRE_DISPATCH
       -> PRE_DISPATCH_REFUSAL

6. run-scoped registries / live references not empty
       -> RUN_SCOPED_REGISTRY_NOT_EMPTY

otherwise -> no halt_reason_code (the run admitted normally)
```

**This ordering is a deliberate design choice, not an arbitrary tie-break.**
Placing the two emission-outcome checks first means an emission failure
discovered while trying to durably persist evidence of a *different*,
lower-priority defect (for example, row 15's self-validation defect, whose
one permitted refusal fallback then itself fails at `PRE_CREATE`) takes
durable precedence over that underlying defect: the record correctly states
"this ordinal's evidence could not be confirmed on disk" ahead of "and also,
separately, here is why the run was invalid to begin with" — because the
first fact is what a reader checking `results/` for admissible evidence
needs foremost, and the second fact remains available through whatever
already-permitted diagnostic channel produced it (never as raw text in
durable evidence, per §21's reduction rule — the finer underlying facts stay
exactly as bounded and as sparse as §18/§21.2 already require; this
precedence function does not loosen that in either direction).

**Exactly one function, called from exactly two places, never
reimplemented.** `_resolve_halt_reason_code(emission_status,
halt_triggered_by_this_run, lifecycle_all_closed, run_classification,
registries_empty) -> HALT_REASON_CODES | None` (exact name implementation
discretion) is the **one** shared callable: L30 (§16.2) calls it to determine
the value it seals into the stage decision (§16.3.8.3), and it is the same
underlying callable object §22.4.2's validator cites when checking the two
mechanically-derivable bindings (`EMISSION_COLLISION`/`EMISSION_FAILED` →
`halted_after_ordinal` + matching code) — mirroring the identity-of-callable
discipline `_schedule_arm_for` already established (T-42, T-93). The
validator never independently reconstructs steps 3–6 of this precedence from
`ordinal_status` alone, because it cannot: those four codes depend on facts
(`halt_triggered_by_this_run`, `lifecycle_all_closed`,
`run_classification`, registry emptiness) that are not, and by FU8's own
Finding 2 must not be, present anywhere in durable payload data (§22.4.2's
own cross-field-rules note, revised below). Their live provenance is the
sealed L30 decision alone (§16.3.8.3); the validator's job for those four
codes is exactly the same as for any other closed-enum field — proving the
*value present* is a member of the closed set — never proving *which*
underlying condition produced it.

Regressions: T-111–T-114 (§11.3).

**Future widening requires a design amendment.** No implementation may add a
seventh code, alias an existing one, or infer a new one from a novel failure
mode without a new, separately authorized FU. Regressions: T-90 (§11.3).

### 19.6 Exact L30 three-way terminal transition, and `LAST_ORDINAL` derivation (new, FU10)

**Finding 2, stated precisely.** §19.1/§19.2, as FU1 through FU9 left them,
describe a two-way rule: issue an admission token, or seal a HALTED decision
and halt. That is incomplete for the stage's own last declared ordinal: for
`S1` (`k = 9`) or `S2` (`k = 6`), a run that satisfies every one of §19.1's
original four admission conditions has no ordinal `k+1` to admit. The
two-way rule, applied literally, would either issue a token for an ordinal
the schedule (§7.3/§7.3a) never declares, or leave a genuinely successful
stage with no terminal stage-closure record at all — silently contradicting
§22.4.2's own already-accepted successful-stage schema shape (`halted_after_ordinal
== null`, `halt_reason_code == null`, every ordinal `RECORD_EMITTED`/
`EVIDENCE_REFUSED`), which has had a defined shape for a successful stage
since FU7 with nothing in the L30 procedure ever specified to produce it.

**`LAST_ORDINAL(stage_id)` — derived, never a duplicated literal.**

```text
LAST_ORDINAL(stage_id) = max(key for key in SCHEDULE[stage_id])
```

where `SCHEDULE` is the **same** frozen, per-stage mapping that already
backs `_schedule_arm_for` (§16.3.8.1) — the one shared schedule-arm
derivation T-42/T-93/T-114 already prove is invoked by identity from every
consumption site in this design, never independently reimplemented. `S1`'s
schedule (§7.3) has nine entries, so `LAST_ORDINAL("S1") = 9`; `S2`'s
schedule (§7.3a) has six, so `LAST_ORDINAL("S2") = 6` — both are stated here
as **consequences** of the already-frozen schedule tables, not as a second,
separately-pinned constant an implementation or a future schedule change
could drift out of agreement with. No CFG1-IMPL variant may hard-code `9` or
`6` directly anywhere `LAST_ORDINAL` is needed; every such site calls this
one derivation, mirroring `_schedule_arm_for`'s own identity-of-callable
discipline exactly (T-127/T-128 below extend T-42/T-93/T-114's proof
technique to this new derivation).

**The frozen three-way transition, evaluated at L30 for the ordinal *k* that
just ran, after L29's result for *k* has resolved and been recorded into the
stage-progress ledger (§16.3.8.4):**

**Branch A — admission conditions fail.** Any of §19.1 items 1–4 is false
(item 5 is irrelevant to this branch — a failed run never reaches the
question of whether it was the last ordinal). Then: do not issue an
admission token; resolve `halt_reason_code` via §19.5's frozen precedence;
seal exactly one **HALTED** `CFG1StageClosureDecision` from the
stage-progress ledger, with `halted_after_ordinal = k` and the resolved
non-null `halt_reason_code`; emit the stage closure from that decision;
retire the stage-output authority immediately after that emission succeeds
(§16.3.9's "ordinary halt" row, unchanged). Subject to the existing
§19.2/§16.3.7/§16.3.10 no-stage-closure hard-stop exceptions, which this
branch does not alter.

**Branch B — admission conditions pass, and *k* is not the stage's final
ordinal.** §19.1 items 1–4 all hold, **and** `k != LAST_ORDINAL(authority.stage_id)`.
Then, and only then: issue the single-use admission token for `k+1`; do not
seal a stage decision of either kind; do not emit a stage closure; the stage
continues. This is FU1 through FU9's original rule, entirely unchanged — it
is simply no longer the *only* outcome of "items 1–4 all hold."

**Branch C — admission conditions pass, and *k* is the stage's final
ordinal (new).** §19.1 items 1–4 all hold, **and**
`k == LAST_ORDINAL(authority.stage_id)`. Then: do **not** issue an admission
token (there is no ordinal `LAST_ORDINAL+1` for one to name, and inventing
one would misrepresent the frozen schedule exactly as §16.3.10 already
rejects inventing a synthetic ordinal 0 for the symmetric admission-time
case); seal exactly one **SUCCESS** `CFG1StageClosureDecision` — `ordinal_status`
containing every declared ordinal from `1..LAST_ORDINAL(stage_id)`, each
populated from the stage-progress ledger (§16.3.8.4), `halted_after_ordinal
= null`, `halt_reason_code = null`; emit the successful stage closure from
that decision; retire the stage-output authority immediately after that
emission succeeds — the identical retirement timing §16.3.9's "ordinary
successful completion" row already states, now given an exact decision and
transition to produce it from. This is **ordinary successful stage
completion**, not a halt, not a hard stop, and not a new failure mode.

**A single terminal-decision model, restated as the frozen invariant these
three branches jointly establish.** `CFG1StageClosureDecision` (§16.3.8.3)
represents **both** a SUCCESS terminal decision (branch C) and a HALTED
terminal decision (branch A) — it is not, and must never become, a
halt-only type with success handled by some separate, unsealed shape.
Exactly one decision is sealed per stage execution that reaches a terminal
branch (A or C); **no** decision is ever sealed while branch B still applies
(the stage has not yet terminated) — branch B's own defining property is
precisely "neither A nor C fires for this ordinal." The two no-record
hard-stop classes (§16.3.7's stage-output-authority failure; §16.3.10's
`OUTPUT_NAMESPACE_PREOCCUPIED`) remain entirely outside this three-way
model, exactly as §19.2 already states — neither is reached by evaluating
§19.1 at all, so this subsection does not, and need not, reconcile them with
branches A/B/C. A stage-closure writer's own emission failure (§18 row 17,
§16.3.8.2) likewise remains outside this model in the sense that matters
here: it can follow **either** a sealed HALTED decision (branch A) or a
sealed SUCCESS decision (branch C) — a stage-closure write can fail after
either kind of decision is sealed — and in both cases it still produces no
confirmed durable closure record, exactly as already frozen; this
subsection changes nothing about that.

**Successful-stage schema binding — reused, not amended.** §22.4.2's
"Successful-stage semantics, corrected (Finding 2)" paragraph (frozen since
FU7) already states the exact required shape for `halted_after_ordinal ==
null ∧ halt_reason_code == null`: every ordinal exactly one of
`RECORD_EMITTED`/`EVIDENCE_REFUSED`, never `EMISSION_COLLISION`,
`EMISSION_FAILED`, or `NOT_EXECUTED`. Branch C's SUCCESS decision is the
**live provenance** for a record in exactly that shape, in exactly the same
way branch A's HALTED decision is already accepted as live provenance for a
halted closure record (§16.3.8.3's own "what this does and does not prove"
paragraph, unchanged). No code path hand-assembles this shape as a plain,
unsealed payload — branch C's decision is sealed through the identical
mint-registry mechanism (§16.3.8.3 requirement 4) as every HALTED decision,
never special-cased as a bare dict.

**Cross-reference, not a reopening (new, FU13).** Branches A and C each
describe sealing a decision as a step that succeeds; §16.3.8.3's own new
"Terminal-decision mint failure disposition" governs the case where that
sealing attempt itself fails after either branch has already been selected
— a failure mode this subsection's own branch semantics are silent on, and
which FU13 closes without altering what branch A or branch C means when
sealing succeeds.

Regressions: T-126–T-132 (§11.3).

---

## 20. Evidence-versus-cleanup ordering (FU1)

| Phase | Finalized into immutable plain values | Before destroying |
|---|---|---|
| Φ1 | schedule binding, preflight results, fixture revision, baseline Git facts, route bools, base-URL classification bool, config redacted digests | — |
| Φ2 | Pi observed version (bounded pattern or `UNRECOGNIZED`), H1/H2 bools, §8.2 projection | — |
| Φ3 | `dispatch_state`, `prompt_writes` | — |
| Φ4 (L20) | OBS1 snapshot, wait outcome, stop-reason counts, auto-retry count, extension-error count | the runtime (L21) |
| Φ5 (L22) | broker counts | the broker (L23) |
| Φ6 | runtime/transport closure facts | — |
| Φ7 | broker lifecycle facts (closed literals and bools only) | — |
| Φ8 | scrub outcomes | — |
| Φ9 (L25) | Git observation #1 facts, cross-check bool | the workspace (L27) |
| Φ10 (L26) | verification bounded fields, Git observation #2 facts | the workspace (L27) |
| Φ11 (L27) | removal outcome | — |
| Φ12 (L28–L29) | lifecycle aggregate → classification → record → canonical snapshot → validation → scrub → exclusive create | — |

Ordering guarantees:

1. **Observations are finalized before their source resource is destroyed**, and
   the record never holds a live object: supervisor, activity, broker, `RunState`,
   Popen, handles, `Path`, or authority objects.
2. **The durable record is sealed only after the lifecycle outcome is known**, so
   no written record ever needs amendment. No rewrite cycle exists.
3. **Separated stages:** configuration and tool observations (Φ1–Φ5); repository
   and verification observations (Φ9–Φ10); live-resource teardown outcome
   (Φ6–Φ7); cleanup outcome (Φ8, Φ11); record assembly, scrub and exclusive
   create (Φ12).
4. **No durable evidence file authorizes cleanup.** Cleanup authority is only
   the in-memory registry, issuance records, and frozen marker re-proof. Nothing
   in `results/` is ever read by the runner.
5. No workspace, config, or extension material is ever preserved.

---

## 21. Secret and diagnostic containment (FU1)

### 21.1 Reduction rule

Every exception, OS error, RPC error or error response, provider error, broker
refusal detail, `worker_error`, `extension_errors` entry, stderr tail,
verification output, and raw event is reduced **at the step where it is caught**
to a member of a closed code set. The raw value is dropped there. No `str(exc)`,
`repr`, traceback, or raw text crosses a step boundary.

### 21.2 What may enter each sink

**This table is a sink-boundary summary, not the schema (revised, FU6).** The
run, refusal, and stage-closure field lists below are constrained further,
into three exact closed schemas — closed key sets, exact literals, exact
types, closed enumerations, cross-field invariants, no coercion — by §22.1
(run), §22.4.1 (refusal), and §22.4.2 (stage-closure). Where this table and
those sections could be read as disagreeing on a field's presence, §22.1/
§22.4.1/§22.4.2 govern; this table exists to state, in one place, what class
of value is categorically excluded from every sink (the forbidden column and
the paragraph beneath it), which those sections do not repeat field-by-field.

| Sink | Allowed | Forbidden |
|---|---|---|
| **Console** | fixed-format lines: `stage_execution_id`, stage, ordinal, arm, step name, closed status/refusal/halt codes, run classification, stage summary counts | everything in the forbidden column below |
| **CFG1 run record** | only §22.1–§22.3's declared fields and closed domains | everything below, plus diffs, failed node ids, verification output tail, final assistant text, usage tokens, timing series, reasoning content or counts, tool arguments/results, literal unexpected tool names, raw event JSON, `get_state` model fields other than §8.2's projections |
| **CFG1 refusal record** | exactly §22.4.1's closed schema: `experiment`, `record_version = "pi-harness-cfg1-refusal.v1"`, `record_kind = "cfg1 artifact emission refusal"`, `stage_id`, `stage_execution_id`, `run_ordinal`, `arm_id` (all schedule literals), **`record_filename`** (the internally-derived run-artifact filename this refusal record stands in for, added FU6 so §16.3.8/T-59's filename-binding requirement has a field to validate), `refused_record_kind`, `finding_count`, sorted closed `finding_categories`, `lifecycle_all_closed` | any value from the refused payload |
| **Stage-closure record** | exactly §22.4.2's closed schema: `experiment`, `record_version = "pi-harness-cfg1-stage-closure.v1"`, `stage_id`, `stage_execution_id`, **`record_filename`** (the internally-derived stage-closure filename, added FU6), per-ordinal closed emission status (`RECORD_EMITTED` · `EVIDENCE_REFUSED` · `EMISSION_COLLISION` · `EMISSION_FAILED` (new, FU6 — see §22.4.2) · `NOT_EXECUTED`), `halted_after_ordinal`, closed `halt_reason_code` | as above |

**Console-only closed codes, outside every durable schema (new, FU13
wording; the codes themselves are FU8's and FU13's).** `OUTPUT_NAMESPACE_PREOCCUPIED`
(§16.3.10) and `STAGE_DECISION_MINT_FAILED` (§16.3.8.3) are both members of
the Console row's "closed status... codes" category above and **neither**
ever reaches the run record, the refusal record, or the stage-closure
record — both name a stage-ending failure for which no durable record of
any kind exists to carry a code, so both are reported exclusively through
this bounded console sink, subject to the identical reduction rule (§21.1):
bounded, never raw exception text, never a `repr`, never a traceback.

**Forbidden everywhere:** base URL, host, port, or scheme-plus-host; credential
value; credential-bearing header text; raw exception text/repr/traceback; raw
provider body; raw RPC event; raw broker refusal text; absolute workspace, config,
extension, or results paths; pipe name; broker token; capability id; `run_id`;
Pi session id; RPC command ids; the marker nonce; issuance tokens.

The only paths ever retained are fixture-relative literals from
`CFG1_T1.files` (changed tracked paths, which must be a subset of that set).
Untracked or unexpected paths are retained as counts only.

### 21.3 Debug diagnostics

`CFG1-IMPL` defines **no** debug channel. Any future debugging output requires a
separate design with its own scrub, and never becomes durable experiment
evidence.

### 21.4 Scrub needles

`qualification_scrub_check` runs with needles for the base URL, its host, the
credential, the experiment-root and repository absolute paths, the pipe name,
the token, and the capability id, constructed in memory at L29 and discarded
after. If the frozen safety context cannot be built for CFG1 values unmodified,
the implementation STOPs (§7.4).

---

## 22. CFG1 record authority and binding (FU1, +FU2)

### 22.1 Fail-closed boundary

**This is the run-record validator, `_require_valid_cfg1_run_payload` —
one of three independent, closed payload validators this design freezes
(FU6). It is never run against a refusal or stage-closure payload, and
neither of the other two is a wrapper around this one** — see §22.4.1
(refusal), §22.4.2 (stage-closure), and §22.4.3 (the no-wrapper requirement
and the dispatch rule this implies for the read-only run-artifact verifier).

The implementation must provide, for `pi-harness-cfg1-run.v1`:

1. **closed top-level key set**, checked by exact set equality;
2. **exact literals**: `experiment = "pi_harness_cfg1"`,
   `record_version = "pi-harness-cfg1-run.v1"`,
   `record_kind = "harness configuration diagnostic run"`,
   `scoring_authority = false`, `qualification_credit = false`,
   `is_review_packet = false`, `reviewer_invoked = false`, the fixed `claim_scope`
   literal;
3. **exact typing**: `type(v) is bool` / `type(v) is int` (never a bool masquerading
   as an int) / `type(v) is str` with closed domains; no coercion or clamping;
4. **closed enumerations** for stage, arm, schedule position, declared and
   reported shapes, dispatch state, wait outcome, refusal codes, skip
   reasons, and classification — **no emission or halt code appears in this
   schema** (FU8 Finding 2: `halt_triggered_by_this_run`/`halt_reason_code`
   are removed; there was never an "emission code" field on the run record
   to begin with — emission status is the stage-closure record's own
   per-ordinal field, §22.4.2);
5. **cross-field invariants** (§22.3);
6. **canonical plain-object snapshot** before write — `json.loads(json.dumps(payload))`,
   after which the original payload is never read again (the OBS1 FU4 TOCTOU
   discipline), then re-checked;
7. **independent final validation**, which recomputes classification and bindings
   from the snapshot rather than trusting assembled values;
8. **scrub** via `qualification_scrub_check`;
9. **exclusive create**, never overwrite, with a CFG1-owned refusal record on
   scrub failure.

### 22.2 Field set

```text
header            experiment, record_version, record_kind, scoring_authority,
                  qualification_credit, is_review_packet, reviewer_invoked, claim_scope

schedule binding  stage_id ("S1"|"S2"), stage_execution_id (validated identifier;
                  type(v) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", v) — §16.3.1),
                  run_ordinal (1..9 | 1..6), block, position, arm_id, record_filename

config variant    declared_compat_shape, models_json_redacted_sha256,
                  settings_json_sha256, derived_effective_supports_developer_role,
                  derived_effective_supports_reasoning_effort, derived_system_role,
                  derived_reasoning_effort_sent

identity          model_id, provider_id, backend_gateway_class, fixture_task_id ("CFG1-T1"),
                  fixture_revision, pi_observed_version, pi_seam_digests_match

pre-dispatch      base_url_compat_detection_clear, route_reachable,
                  route_configured_model_served, broker_reached_ready,
                  h1_extension_identity_matched, h2_provider_model_identity_matched,
                  runtime_reported_compat_shape, runtime_reported_model_reasoning,
                  runtime_reported_thinking_level, manipulation_check_agrees,
                  pre_dispatch_refusal_code (closed | null), refused_at_step (closed | null)

dispatch          dispatch_state (NOT_ATTEMPTED | CONFIRMED_SENT | CONFIRMED_NOT_SENT |
                  SEND_STATE_INDETERMINATE), prompt_writes (0|1),
                  automatic_semantic_retry (false), operator_continuation (false)

turn              runtime_wait_outcome (SETTLED | DEADLINE_EXPIRED | EXITED_EARLY |
                  PROTOCOL_VIOLATION | OUTPUT_CAP_EXCEEDED | EVENT_CAP_EXCEEDED |
                  READ_ERROR | UNRECOGNIZED | NOT_OBSERVED)

OBS1              runtime_reported_tool_activity_available,
                  runtime_reported_tool_activity_capture_basis,
                  runtime_reported_tool_execution_start_events / _end_events,
                  runtime_reported_distinct_tool_call_ids,
                  runtime_reported_unidentified_tool_call_id_seen,
                  runtime_reported_aido_read_call_ids / _end_observed / _error_results,
                  runtime_reported_aido_edit_call_ids / _end_observed / _error_results,
                  runtime_reported_unexpected_tool_call_ids / _end_observed / _error_results,
                  activity_unavailable_reason

provider          stop_reasons_available, stop_reason_counts {stop, length, toolUse,
                  error, aborted, other}, auto_retry_events, extension_error_count

broker            broker_recorded_activity_available, broker_recorded_read_operation_count,
                  broker_recorded_edit_operation_count, broker_recorded_edited_path_count,
                  broker_recorded_refusal_count

lifecycle         runtime_created, runtime_exit_observed, runtime_transport_eof_observed,
                  broker_resource_created, broker_state_closed, broker_pending_unreaped_zero,
                  broker_worker_terminated_or_absent, generated_config_scrub_verified,
                  extension_binding_scrub_verified, verification_child_reaped_or_not_started,
                  workspace_authority_reproved, workspace_removed_verified,
                  workspace_residual_file_count, lifecycle_all_closed, lifecycle_failure_steps
                  (sorted closed step names)

repository        git_observation_1_performed, head_moved, changed_tracked_paths (sorted
                  subset of CFG1_T1.files), untracked_path_count, staged_path_count,
                  broker_git_cross_check_agrees, git_observation_2_performed,
                  post_verification_changed_tracked_paths

verification      verification_attempted, verification_skip_reason (null |
                  LIFECYCLE_UNPROVEN | PRE_DISPATCH_REFUSAL), verification_started,
                  verification_completed, verification_timed_out,
                  verification_output_limit_exceeded, verification_return_code (int | null),
                  verification_passed, verification_counts {passed, failed, error}

classification    run_classification
                  (FU8 Finding 2: halt_triggered_by_this_run and
                  halt_reason_code are REMOVED from this durable schema —
                  see §22.3's note immediately below the field-set close, and
                  §19.4)
```

**`halt_triggered_by_this_run`/`halt_reason_code` are removed from this
durable schema (new, FU8 Finding 2).** FU6/FU7 carried both fields in the
run record and required `halt_triggered_by_this_run` to equal "the §19.1
negation" — but §19.1's own admission conditions include this run's **own
emission status** (item 3) and run-scoped registry emptiness (item 4), and
neither is knowable until **after** L29's emission attempt for this very
record has already resolved (§16.2 L28→L29→L30). A payload-only validator
that claims to recompute `halt_triggered_by_this_run` from the record's own
fields would be claiming to recompute a fact about the record's own
not-yet-decided future — the record cannot durably assert whether it (or a
refusal fallback for it) will still be successfully emitted moments from now,
because emission is the very operation depositing this record on disk.
**`run_classification` has no such problem** and stays: it is a pure function
of pre-emission observations already finalized at L28 (§12), independent of
this run's own write outcome, so it remains payload-only recomputable and
is retained unchanged.

Both removed facts continue to exist — as **in-memory-only** stage-control
state, computed at L30 from the now-known emission outcome (never written
into any durable run-record payload), and consumed immediately by that same
L30 admission decision. **The stage-closure record is the sole durable
authority for whether the stage halted, after which ordinal, and why**
(§22.4.2, §19.4) — a strictly cleaner separation than FU7's: a *run* record
states facts finalized **before** durable emission; the *stage-closure*
record states facts about admission decided **after** the emission outcome
is known. Row 15 loses no evidence under this split: a self-invalid run
payload cannot exist as a *valid* run artifact regardless (it is refused by
`_require_valid_cfg1_run_payload` at step 6, §16.3.8); the refusal artifact
that may follow it identifies the bounded `RECORD_INVARIANT` finding category
(§22.4.1); and the stage-closure record carries the final, authoritative
halt reason (§19.4). Regressions: T-94 (§11.3).

### 22.3 Cross-field invariants (non-exhaustive minimum)

- `type(stage_execution_id) is str` and `re.fullmatch(r"[A-Za-z0-9_-]{1,64}",
  stage_execution_id)` — the **same** grammar `establish_stage_output_authority`
  enforces (§16.3.1), re-proven independently by the record validator rather
  than trusted from the field's mere presence.
- `(stage_id, run_ordinal) ↦ arm_id` equals `_schedule_arm_for(stage_id,
  run_ordinal)` (§16.3.8) — the **one** shared schedule-arm derivation every
  other consumer (L0, payload construction, the writer, this validator, and
  the artifact-binding verifier of §22.5) also calls, never a
  separately-reimplemented lookup — and `(block, position)` equal the frozen
  schedule constant for that ordinal; `record_filename` equals the internal
  filename derivation (§16.3.8 step 9 — corrected from a stale `step 5`
  reference left over from FU4's draft numbering, FU6) from
  `(stage_id, run_ordinal, arm_id)` alone — the validator recomputes this from
  the record's own fields, without
  needing (and without ever being given) the live `CFG1StageOutputAuthority`
  instance, because the derivation is a pure function of those three values. A
  record whose `stage_execution_id`, `run_ordinal`, `arm_id`, or
  `record_filename` has been altered relative to any of the others fails this
  recomputation.
- the stage-closure record's own filename equals the identical internal
  stage-closure filename derivation (§16.3.8 step 9 — corrected from a stale
  `step 5` reference, FU6) from `stage_id` alone, so it is bound to the same
  authority-derived naming scheme as every run record, never a
  separately-chosen name.
- `declared_compat_shape` equals `ARM_SHAPE[arm_id]`;
  `models_json_redacted_sha256` equals `ARM_REDACTED_DIGEST[arm_id]` for the
  pinned model id; `settings_json_sha256` equals the pinned constant; the four
  `derived_*` fields equal `ARM_EFFECTIVE[arm_id]`.
- `model_id`, `provider_id`, `backend_gateway_class`, `fixture_task_id`,
  `fixture_revision` equal their pinned literals.
- `prompt_writes == 0` ⇔ `dispatch_state == NOT_ATTEMPTED`;
  `pre_dispatch_refusal_code != null` ⇒ `dispatch_state ∈ {NOT_ATTEMPTED, CONFIRMED_NOT_SENT}`;
  `dispatch_state == CONFIRMED_NOT_SENT` ⇒ `pre_dispatch_refusal_code == PROMPT_REFUSED_BY_RUNTIME`.
- `manipulation_check_agrees` ⇔ (`runtime_reported_compat_shape == declared_compat_shape`
  ∧ `runtime_reported_model_reasoning == TRUE` ∧ `runtime_reported_thinking_level == medium`);
  `dispatch_state != NOT_ATTEMPTED` ⇒ `manipulation_check_agrees`.
- activity/broker availability false ⇒ that family's counts are all zero and
  capture basis is null; basis non-null iff runtime activity is available;
  basis `agent_settled` ⇒ `runtime_wait_outcome == SETTLED`.
- **OBS1 re-validation branches on availability (clarified, FU2).** When
  `runtime_reported_tool_activity_available == true`, the validator
  re-establishes every `RuntimeToolActivitySnapshot` invariant by constructing
  an exact `RuntimeToolActivitySnapshot` from the record's own retained OBS1
  fields (capture basis, the twelve counts, the unidentified-id flag) and
  requiring that construction to succeed unmodified. When it is `false`, the
  validator does **not** construct a snapshot at all — there is no genuine
  observation to reconstruct — and instead directly requires
  `runtime_reported_tool_activity_capture_basis == null`, every
  `runtime_reported_*` count field `== 0`, and
  `runtime_reported_unidentified_tool_call_id_seen == false`. Fabricating an
  "available" snapshot merely to validate an unavailable observation is never
  done; the two branches use different, exact checks.
- `broker_edited_path_count ≤ broker_edit_operation_count`.
- `lifecycle_all_closed` equals the conjunction of its component bools (with
  "not created" counting as closed), and `lifecycle_failure_steps` is empty iff
  it is true.
- `verification_attempted` ⇒ (`runtime_exit_observed ∧ runtime_transport_eof_observed ∧ broker_state_closed ∧ generated_config_scrub_verified ∧ extension_binding_scrub_verified`);
  `verification_attempted == false` ⇒ `verification_skip_reason != null`.
- `changed_tracked_paths ⊆ CFG1_T1.files`.
- `run_classification` equals `classify(snapshot)` recomputed by the validator
  (§12) — a pure function of pre-emission observations only (§12.1's rows
  never read this run's own emission outcome), so it remains independently
  recomputable from the payload alone even though `halt_triggered_by_this_run`
  and `halt_reason_code` no longer appear in this schema at all (removed,
  FU8 Finding 2, see the note immediately above §22.3's heading).
- `automatic_semantic_retry == false`, `operator_continuation == false`, always.

Because the arm's config digest, declared shape, derived effective values, and
schedule position are all pinned functions of `arm_id` and ordinal, a valid Q
record's **own internal fields** cannot be edited to claim to be R or E, or to
claim a different ordinal, without failing this payload-only validation
(T-13). **This is a claim about the record's self-consistency, not about where
it sits on disk** (FU3 correction) — a byte-for-byte copy of a genuine record
placed under a different execution directory still passes every check in this
section, because every field it carries is still internally consistent; that
case is caught only by the artifact-binding verifier of §22.5 (T-33), which
checks the record against its actual path, not against itself.

### 22.4 Output identity

```text
experiments/pi_harness_cfg1/results/<stage_execution_id>/<stage_id>_<run_ordinal:02d>_<arm_id>.json
    e.g.  results/S1-X1/S1_01_Q.json  …  results/S1-X1/S1_09_R.json
experiments/pi_harness_cfg1/results/<stage_execution_id>/<stage_id>_stage_closure.json
```

where `<stage_execution_id>` is validated per §16.3.1, `results/` is the fixed
`RESULTS_ROOT` of §16.3.2, and every path is produced **only internally by an
`emit_cfg1_*` writer** (§16.3.8), against the one `CFG1StageOutputAuthority`
the stage established (§16.3.3) — never returned from a public helper, never
passed as an argument, and never string-formatted fresh anywhere else in the
implementation.

The execution directory is created only if absent, at stage start, by
exclusive creation (§16.3.6), after the containment proof of §16.3.5. An
existing directory refuses the stage before any run: an execution id is never
reused. Names derive **only** from the schedule constant, the arm/ordinal, and
the authorization-pinned, grammar-validated execution id. No caller path, no
timestamp, and no replacement name exists (T-21).

### 22.4.1 Refusal-record schema — exact, closed (new, FU6)

§21.2's refusal-record row, and the original design's §21.2 predecessor, were
**descriptive allowlists**, not an enforced schema. FU6 freezes
`_require_valid_cfg1_refusal_payload` (exact name implementation discretion)
as an independent validator for `pi-harness-cfg1-refusal.v1`, structurally
parallel to §22.1's run-record validator but over its own, smaller, closed
schema. It is never a wrapper around the run-record validator with checks
skipped — it enforces its own closed key set from first principles.

**Closed top-level key set:**

```text
experiment                  = "pi_harness_cfg1"                     (exact literal)
record_version               = "pi-harness-cfg1-refusal.v1"          (exact literal)
record_kind                  = "cfg1 artifact emission refusal"      (exact literal)
stage_id                     = "S1" | "S2"                           (closed enum)
stage_execution_id           = type(v) is str, re.fullmatch(r"[A-Za-z0-9_-]{1,64}", v)
run_ordinal                  = type(v) is int (bool rejected), 1..9 for S1, 1..6 for S2
arm_id                       = closed enum ("Q"|"R"|"E"|"H", scoped to the
                                stage's declared arm set)
record_filename               = type(v) is str; the filename this refusal
                                record stands in for at the run path — never
                                this refusal record's own filename, which is
                                identical to it by construction (§16.3.8.2)
refused_record_kind          = closed enum: exactly "pi-harness-cfg1-run.v1"
                                for FU6 (the only kind a refusal record may
                                currently stand in for at a run path — see
                                §16.3.8.2; a future kind requires a future,
                                separately authorized amendment, never a
                                silent widening of this enum)
finding_count                 = type(v) is int (bool rejected), >= 1
finding_categories            = sorted, de-duplicated list of a closed
                                category enum (below); len(finding_categories)
                                <= finding_count, and finding_count == 0 is
                                refused (a refusal record with zero findings
                                is not a coherent refusal — something bounded
                                must have gone wrong for one to exist at all)
lifecycle_all_closed          = type(v) is bool
```

No key outside this set is accepted; no key in this set may be absent.

**`finding_categories` vocabulary (closed enum, exact members):**

```text
SCHEMA_VIOLATION        — the rejected payload failed a closed-key/literal/
                           type/enum check (§22.1 items 1-4, or the run
                           validator's own equivalent)
CROSS_FIELD_INVARIANT   — the rejected payload failed a §22.3-class
                           cross-field invariant
AUTHORITY_BINDING       — the rejected payload failed §16.3.8 step 7's
                           authority/schedule-identity binding (internally
                           self-consistent, but bound to the wrong authority)
SCRUB_NEEDLE_MATCH      — `qualification_scrub_check` found a forbidden
                           needle in the canonical snapshot
SIZE_BOUND_EXCEEDED     — the canonical snapshot's serialized bytes exceeded
                           `MAX_CFG1_ARTIFACT_BYTES` (§16.3.8.1)
RECORD_INVARIANT        — the specific §18 row-15 case: a **primary run**
                           payload failed its own self-validation as an
                           implementation defect, distinct from an ordinary
                           SCHEMA_VIOLATION/CROSS_FIELD_INVARIANT hit in that
                           it is never expected under correct operation
```

`finding_categories` is sorted (lexical) and de-duplicated: the same category
observed for multiple independent reasons within one rejected payload appears
once. `finding_count` counts the **findings**, which may exceed
`len(finding_categories)` (multiple findings of the same category collapse to
one category entry but still count individually) and may never be less than
`len(finding_categories)`.

**Cross-field invariants (non-exhaustive minimum):** the same
`stage_execution_id` grammar, `(stage_id, run_ordinal) ↦ arm_id`, and
`record_filename`-equals-internal-derivation checks §22.3 states for the run
record apply here identically, using the **same** `_schedule_arm_for`
function — a refusal record's identity fields describe the run path it
stands in for, and that path is schedule-derived exactly as a genuine run
record's own path would be. **A refusal record's identity fields must be
built from the live authority and schedule truth, never copied from the
rejected payload** (§16.3.8.2) — this validator checks the field values for
internal closure and grammar conformance; it is §16.3.8 step 7's authority
binding, not this validator, that additionally proves those values agree with
the writer's own authority (mirroring the run record's own split between
§22.1–§22.3's payload-only proof and §16.3.8 step 7's authority-binding proof).

### 22.4.2 Stage-closure record schema — exact, closed (new, FU6)

`_require_valid_cfg1_stage_closure_payload` (exact name implementation
discretion) is the third independent validator, for
`pi-harness-cfg1-stage-closure.v1`.

**Closed top-level key set:**

```text
experiment                  = "pi_harness_cfg1"                     (exact literal)
record_version               = "pi-harness-cfg1-stage-closure.v1"    (exact literal)
record_kind                  = "cfg1 stage closure"                  (exact literal)
stage_id                     = "S1" | "S2"                           (closed enum)
stage_execution_id           = type(v) is str, re.fullmatch(r"[A-Za-z0-9_-]{1,64}", v)
record_filename               = type(v) is str; equals the internal
                                stage-closure filename derivation (§16.3.8
                                step 9) from `stage_id` alone
ordinal_status                = the exact per-ordinal status structure below
halted_after_ordinal          = type(v) is int (bool rejected) and within the
                                stage's declared ordinal range, **or** `null`
                                iff the stage completed every declared ordinal
                                without halting
halt_reason_code              = closed enum (below) if `halted_after_ordinal`
                                is non-null, else `null`; never both non-null
                                and both null
```

No key outside this set is accepted; no key in this set may be absent (a
`null` value is a value, and is accepted only where stated above).

**`ordinal_status` — one exact JSON structure, not an implementation-time
choice.** It is a JSON **object** (mapping), never a list or nested-object
tree, whose keys are the stage's ordinals rendered as **decimal-digit
strings with no leading zero** (`"1"`, `"2"`, … — JSON object keys are always
strings, so this is the canonical string form of the `int` ordinal, not a
separate encoding), and whose values are each a **string**, one of the closed
emission-status enum members below — never a nested object, never a list,
never carrying `arm_id` or any other field inline:

```json
{ "1": "RECORD_EMITTED", "2": "EVIDENCE_REFUSED", "3": "EMISSION_COLLISION",
  "4": "EMISSION_FAILED", "5": "NOT_EXECUTED", "6": "NOT_EXECUTED",
  "7": "NOT_EXECUTED", "8": "NOT_EXECUTED", "9": "NOT_EXECUTED" }
```

**Exact entry/key set, closed:**

- `S1`: exactly the keys `"1"` through `"9"`, no more, no fewer.
- `S2`: exactly the keys `"1"` through `"6"`, no more, no fewer.
- Ordinal ordering is not separately encoded — a JSON object's own key
  membership is checked as a set equality against the stage's declared
  ordinal range (`{"1".."9"}` or `{"1".."6"}`), never as an ordered sequence,
  since JSON object key order carries no normative meaning in this design.
- **Schedule-derived arm identity is not retained inline** in `ordinal_status`
  — each entry is a bare status string, not `{"status": ..., "arm_id": ...}`.
  The arm for any ordinal is always re-derivable from `_schedule_arm_for`
  (§16.3.8.1), so duplicating it here would be redundant data that could
  itself drift from the schedule truth; the validator never accepts an
  `ordinal_status` entry shaped as an object.

**Allowed emission-status values (closed enum, exact members; meanings
corrected, FU7 Finding 2 — this is the normative source; §16.3.8.2 restates
it):**

```text
RECORD_EMITTED
    a valid run record was successfully emitted (EMISSION_CONFIRMED reached
    for the primary run-record writer, §16.3.8.2)

EVIDENCE_REFUSED
    a valid refusal record was successfully emitted at the run path
    (EMISSION_CONFIRMED reached for the refusal-record writer) — whether
    triggered by an ordinary row-11 scrub refusal (non-halting) or a row-15
    implementation defect (halting); the halt metadata below, not this
    status alone, disambiguates the two (§19.3)

EMISSION_COLLISION
    the final run path collided at FINAL_PATH_CREATE_ATTEMPTED (§16.3.8.2);
    no new valid run-path artifact was emitted by this run

EMISSION_FAILED
    no successfully-confirmed run-path or refusal-path emission exists for
    this ordinal, because emission failed without being classified as the
    path-collision case — covers both a PRE_CREATE refusal-fallback failure
    (§18 row 16) and any post-create failure of either writer (§16.3.8.2);
    a post-hoc structurally-valid residue read later never changes this
    already-sealed status

NOT_EXECUTED
    this ordinal never ran, because the stage had already halted at or
    before it
```

**`NOT_EXECUTED` invariants:** an ordinal's status is `NOT_EXECUTED` if and
only if `halted_after_ordinal` is non-null and that ordinal is strictly
greater than `halted_after_ordinal`; every ordinal less than or equal to
`halted_after_ordinal` (or every ordinal, if `halted_after_ordinal` is
`null`) has one of `RECORD_EMITTED`/`EVIDENCE_REFUSED`/`EMISSION_COLLISION`/
`EMISSION_FAILED`. `halted_after_ordinal` semantics: the ordinal of the last
run this stage execution actually attempted before halting (never the last
run that *succeeded* — a halt is frequently triggered by that very ordinal's
own failure, in which case `halted_after_ordinal` names that same ordinal,
whose own status is one of the four non-`NOT_EXECUTED` values, never
`RECORD_EMITTED` alone implied by the presence of a halt).

**`EMISSION_COLLISION`/`EMISSION_FAILED` → halt binding (new, FU7 Finding
2).** Both `EMISSION_COLLISION` and `EMISSION_FAILED` are, by §18 rows 12/16
and §19.1 item 3, **always** halt-triggering — no ordinal can carry either
status and have the stage admit a later ordinal. The validator therefore
enforces, as a mandatory cross-field invariant, the converse binding: **any
ordinal *j* whose `ordinal_status[j]` is `EMISSION_COLLISION` or
`EMISSION_FAILED` must have `halted_after_ordinal == j` exactly** (never a
different ordinal, never left implicit), with `halt_reason_code` set to
exactly the matching member of §19.4's frozen vocabulary
(`RUN_RECORD_EMISSION_COLLISION` or `RUN_RECORD_EMISSION_FAILED`
respectively — the latter renamed from FU7's `RUN_RECORD_REFUSAL_FALLBACK_FAILED`
by FU8 Finding 1, since that name falsely claimed a fallback was attempted
in every case it covers). A record claiming either status at an ordinal other than
`halted_after_ordinal` — or claiming either status while `halted_after_ordinal`
is `null` — is rejected as internally inconsistent.

**Validation proves schema coherence, never stage-decision provenance
(Finding 5, FU9, stated explicitly).** The binding above is a **payload-only
cross-field check**: it proves that *if* `ordinal_status[j]` claims
`EMISSION_COLLISION` or `EMISSION_FAILED`, the same payload's own
`halted_after_ordinal`/`halt_reason_code` fields are internally coherent
with that claim. **It does not, by itself, prove the claim is true of the
actual stage execution** — a hand-crafted payload could satisfy this
coherence check while describing a stage execution that never happened.
`_require_valid_cfg1_stage_closure_payload` remains exactly what §16.3.8.3
already states it is: a pure closed-schema validator, proving closed keys,
exact literals/types, schedule-sized `ordinal_status`, internal cross-field
coherence, and halt-code vocabulary membership — **never**, by itself, that
the payload is the genuine L30 decision. That stronger guarantee is the
conjunction §16.3.8.3 defines: valid schema **+** a genuine sealed
`CFG1StageClosureDecision` **+** an ACTIVE, matching stage-output authority
**+** a payload the writer itself derived from that decision — and it holds
only for records the frozen `emit_cfg1_stage_closure` writer actually
produced, never as a property of schema validity in isolation.

**Which codes this validator *can* mechanically derive from `ordinal_status`
alone, and which it cannot (Finding 5, FU9).** `RUN_RECORD_EMISSION_COLLISION`
and `RUN_RECORD_EMISSION_FAILED` are the **only** two members of
`HALT_REASON_CODES` this payload-only validator enforces a derivable
relationship for — both are functions of `ordinal_status`, a field already
present in this same payload, so the binding above is genuinely
self-contained. The other four members —

```text
PRE_DISPATCH_REFUSAL
LIFECYCLE_CLOSURE_UNPROVEN
RUN_SCOPED_REGISTRY_NOT_EMPTY
RUN_RECORD_SELF_VALIDATION_FAILED
```

— depend on facts (`run_classification`, `lifecycle_all_closed`, registry
emptiness, `halt_triggered_by_this_run`) that do **not** appear anywhere in
the stage-closure payload, and by FU8 Finding 2 must not — those facts live
only in the removed run-record fields' in-memory L30 successors and in
§19.5's shared `_resolve_halt_reason_code` function. The validator therefore
does **not**, and must not pretend to, independently recompute or verify
*which* of these four applies from `ordinal_status` alone; for these four
codes it enforces only that the value present is a member of the closed
`HALT_REASON_CODES` set (§22.1 item 4's general closed-enumeration
discipline, applied here) — the same treatment any other closed-enum field
gets, no stronger. Their live provenance is exclusively the sealed L30
decision (§16.3.8.3), never payload-only inference. Regressions: T-115
(§11.3).

**Successful-stage semantics, corrected (Finding 2).** The earlier draft
stated this disjunctively ("every ordinal's status is one of
`RECORD_EMITTED`/`EVIDENCE_REFUSED`/`EMISSION_COLLISION`/`EMISSION_FAILED`"),
which wrongly implied a successful, non-halted stage could still carry an
`EMISSION_COLLISION` or `EMISSION_FAILED` ordinal — directly contradicting
§19.1, which forbids admitting a later ordinal after either. The binding
above makes the corrected rule a **derived consequence**, stated here
explicitly because an archived record alone should make it verifiable
without re-deriving it: **a stage that completed every declared ordinal
without halting** (`halted_after_ordinal == null` **and** `halt_reason_code
== null`) **must have, for every ordinal, exactly one of `RECORD_EMITTED` or
`EVIDENCE_REFUSED` — and never `EMISSION_COLLISION`, `EMISSION_FAILED`, or
`NOT_EXECUTED`.** (`EVIDENCE_REFUSED` remains possible in a successful stage
only as an ordinary, non-halting row-11 scrub refusal — a row-15
implementation-defect `EVIDENCE_REFUSED` is, by the binding above and
§19.1 item 2's `halt_triggered_by_this_run` check, always accompanied by a
non-null `halted_after_ordinal` at that same ordinal, so it can never appear
in a `halted_after_ordinal == null` record.) This restates §19.1's admission
rule as a stage-closure-record invariant that the validator itself enforces,
not merely prose the implementation is trusted to honor. **This shape is
reused, not amended, by FU10:** the SUCCESS `CFG1StageClosureDecision` L30's
own branch C (§19.6) seals for the stage's final ordinal succeeding produces
exactly this shape, through the identical validator and the identical
mint-registry-backed decision mechanism (§16.3.8.3) that already governs a
HALTED decision — this schema was already closed for it; FU10 only closes
the gap in *how a record of this shape ever gets written*.

**`halt_reason_code` — one exact, closed vocabulary, accepted only here
(Finding 3, FU7; stale sharing claim corrected, FU9 Finding 4).** §19.4
freezes the complete `HALT_REASON_CODES` set — exactly six members, derived
directly from §19.1's own four admission conditions. **`HALT_REASON_CODES`
is accepted only by the stage-closure record. The run-record schema contains
no `halt_reason_code` field at all** — removed by FU8 Finding 2 (§22.2, the
note preceding §22.3), because neither it nor `halt_triggered_by_this_run`
is recomputable from a payload-only validator at run-record-validation time.
An earlier draft of this paragraph (through FU8) described the vocabulary as
"shared identically by this field and by the run record's own
`halt_reason_code` field" — that claim was already false the moment FU8
removed the run-record field, and is corrected here rather than left
standing in this normative schema section.

See §19.4 for the exact six members and for the **explicit exclusion of
exactly four stage-ending cases** (corrected from FU7's stale "two cases" to
"three," FU9 Finding 4; corrected from "three" to "four" here, FU13) that
write no confirmed stage-closure record and therefore need no
`halt_reason_code` here at all: (1) the stage-output-authority hard stop
(§16.3.7); (2) the stage-closure writer's own failed emission (§18 row 17);
(3) `OUTPUT_NAMESPACE_PREOCCUPIED` (§16.3.10, added by FU8 Finding 5, after
this paragraph's own "two cases" wording was first written); and (4)
`STAGE_DECISION_MINT_FAILED` (§16.3.8.3, new FU13 — no genuine
`CFG1StageClosureDecision` ever exists to authorize a stage-closure write).
No `"for example"`, no non-exhaustive minimum, and no future widening
without a design amendment. **Also see §19.5 (FU9): the value written
here is the output of one shared, frozen precedence function — never a
field the stage-closure writer or validator independently infers from
`ordinal_status` for any code other than the two collision/failure codes
§22.4.2's cross-field rules below already bind mechanically.**

**`record_filename` relationship:** identical in kind to the refusal record's
own field — a value the record carries about its own identity, checked by
the validator against the internal derivation (§16.3.8 step 9), and
separately re-checked against the *actual* on-disk filename only by the
post-hoc artifact-binding verifier (§22.5.2), never by this payload-only
validator, which cannot see the filesystem.

**`stage_execution_id` grammar:** identical to §16.3.1/§22.3 — re-proven
independently here, never trusted from presence alone.

### 22.4.3 Validator dispatch, and the no-wrapper requirement (new, FU6)

**Three independent validators, never a shared generic call, never a
wrapper.** §22.1 (run), §22.4.1 (refusal), and §22.4.2 (stage-closure) are
called by name, from the specific writer that produces that exact record
kind (§16.3.8 step 6). None is implemented as a thin wrapper around another
with irrelevant checks skipped — for example, `_require_valid_cfg1_refusal_payload`
does not call `_require_valid_cfg1_run_payload` and then ignore its
`run_ordinal`/`arm_id`-specific failures; it independently checks its own
closed key set, literals, types, enums, and invariants from §22.4.1, so that
a future change to the run-record schema cannot silently alter refusal- or
stage-closure-record acceptance by accident of shared code.

**Dispatch is the read-only run-artifact verifier's own responsibility, not
the writers'.** Each writer already knows, by construction, which exact
validator applies to it (Finding 2 is a **verifier**-side gap, not a
writer-side one — see §22.5.2 Step 3). `verify_cfg1_run_artifact_binding`
reads the discriminator pair `(record_version, record_kind)` from the
artifact's own parsed bytes and dispatches to exactly one of the run or
refusal validators (§22.5.2); `verify_cfg1_stage_closure_binding` uses only
the stage-closure validator, unconditionally, since a stage-closure path
never legitimately holds any other kind.

Regressions: T-69 (each validator accepts only its own exact schema), T-80–T-82
(§11.3).

### 22.5 Durable-artifact path binding — a separate, read-only, post-hoc verifier (new, FU3)

**The gap this closes.** §22.1–§22.4 validate a record's **payload**: its own
declared fields agree with each other (closed keys, literals, schedule
relations, the internal `record_filename` field, the `stage_execution_id`
grammar). That is real and unchanged (T-13). But a payload-only check cannot
distinguish a genuine `results/S1-X1/S1_01_Q.json` from a byte-for-byte copy
of it sitting at `results/S1-X2/S1_01_Q.json` — both payloads are internally
self-consistent; only the **actual filesystem location** differs from what
the payload claims. §22.1–§22.4 never claimed otherwise in their own terms,
but FU2's T-21 phrased a stronger claim ("one valid record cannot be
relabelled to another output path") that belongs here, not there — corrected
in T-13/T-21 above.

#### 22.5.1 Four distinct concepts, not one (frozen distinction; extended FU9)

```text
emission-time authority     = the in-memory CFG1StageOutputAuthority (§16.3.3),
                               live only during one stage run, gates every write

sealed stage decision       = the in-memory CFG1StageClosureDecision (§16.3.8.3,
                               new FU9), live only from L30 until the stage-
                               closure write resolves, the sole source the
                               stage-closure writer may draw stage-decision
                               facts from — never itself durable, never itself
                               read back from disk

durable evidence identity   = the bounded record fields (§22.2, §22.4.1,
                               §22.4.2) — a claim the record makes about
                               itself, nothing more

post-hoc artifact binding   = the ACTUAL BYTES currently at an actual filesystem
                               path, read and parsed by the verifier itself,
                               checked against that same path's fixed-root
                               position — never a caller-supplied parsed object
                               (FU5, §22.5.2 below)
```

**The post-hoc verifier cannot retroactively prove the sealed decision
existed or that emission completed successfully (Finding 5, FU9).** Reading
a stage-closure record back and finding it schema-valid and correctly bound
to its filesystem location (`verify_cfg1_stage_closure_binding(actual_path)
== True`, §22.5.2) proves exactly, and only, what §22.5.2 has always proved:
*the current bytes at this path form a valid CFG1 artifact whose own
identity fields match their current location.* It does **not** — and this
subsection makes explicit what was previously only implicit — reconstruct or
verify the original, now-gone `CFG1StageClosureDecision` object; it does not
prove the live `emit_cfg1_stage_closure` invocation reached
`EMISSION_CONFIRMED` rather than merely leaving structurally valid
post-create residue behind (§16.3.8.2's own residue-versus-live-outcome
distinction applies identically here); and it grants no authority of any
kind, exactly as the paragraph below already establishes for every other
durable record.

**A durable record is not itself filesystem authority. A durable record never
recreates a stage-output authority.** Reading a record back and finding its
fields self-consistent does **not** hand the reader (or any future process) a
`CFG1StageOutputAuthority` — there is no code path that constructs one from
record contents, and §20 already establishes that nothing in `results/`
authorizes cleanup; FU3 extends that to: nothing in `results/` authorizes
**anything**, including a future write. The binding verifiers below are
strictly read-only, strictly offline, and are **never called by the live
stage runner** — they exist for a human, an auditor, or a future CFG1-IMPL
test examining archived evidence after the fact. This mirrors OBS1's own
companion artifact, which likewise carries "authority: NONE, observational
provenance only" (`runtime_activity.py` module docstring, §1.1) — the binding
verifiers' result is exactly that class of fact: observational, not
authorizing.

#### 22.5.2 The verifiers — one argument, the artifact's own bytes (rewritten, FU5)

```python
verify_cfg1_run_artifact_binding(actual_path: str) -> bool
verify_cfg1_stage_closure_binding(actual_path: str) -> bool
```

Exact names are implementation discretion; the signature and behavior are not.

**Finding 5 (FU5), stated precisely.** FU3/FU4's `verify_cfg1_*_binding(actual_path,
parsed_record)` took an **already-parsed record as a second argument**. That
never bound `parsed_record` to the *current* bytes at `actual_path` — a caller
could hold an old genuine `dict`, modify or replace the file on disk, and still
ask "would this old dict belong at this path," which answers a different,
useless question. **`parsed_record` is removed entirely.** There is no
parameter through which a stale, hand-built, or otherwise
not-actually-read-from-this-file object can be supplied — the API itself has
no such parameter, which is a stronger guarantee than any runtime check could
be (T-62). The verifier reads and parses the artifact **itself**, from the one
`actual_path` argument, so a `True` result means:

> the bytes **currently** at `actual_path` form a valid CFG1 artifact, **and**
> those same bytes' own identity fields match that artifact's current
> filesystem location.

**Step 0 — the lexical input boundary, before `resolve()`, before any read:**

1. `type(actual_path) is str` exactly — **not** `isinstance`, **not**
   `PathLike` acceptance, **no** `os.fspath()` call, **no** `str(actual_path)`
   coercion. Anything else returns `False` immediately, with **zero**
   filesystem calls made (T-50, spy-proven exactly as T-22 already proves it
   for the identifier grammar).

**Step 1 — lexical resource checks, operating on the ORIGINAL, unresolved
path. `resolve()` is never called first: resolving before checking destroys
exactly the evidence (a symlink or reparse point at the leaf, or at the
parent) these checks exist to see.**

```text
lexical = Path(actual_path)                     — the literal argument, unresolved

lstat lexical                                    — never follows a final symlink
    missing / unreadable         -> False
    is symlink/reparse point     -> False        (a symlink alias to a genuine
                                                     record must return False —
                                                     it is not the record itself)
    not S_ISREG                  -> False        (a directory named like a
                                                     record file must return
                                                     False)

lstat lexical.parent
    missing / unreadable         -> False
    is symlink/reparse point     -> False        (a symlink/junction standing
                                                     in for the execution
                                                     directory must return
                                                     False — the artifact may be
                                                     a perfectly ordinary file
                                                     UNDER a redirected parent)
    not S_ISDIR                  -> False
```

**Only after every check in Step 1 passes** may the verifier resolve or
canonicalize anything.

**Step 2 — the verifier reads and parses the artifact's own bytes. No
external parsed object participates at any point:**

```text
size-bounded read     — request at most MAX_CFG1_ARTIFACT_BYTES + 1 bytes
                          (§16.3.8.1); receiving that many means the file
                          exceeds the bound -> False, without reading further
decode as UTF-8        — invalid encoding -> False
json.loads the text    — malformed JSON -> False
type(parsed) is dict    — a JSON array, string, number, boolean, null, or any
                          other top-level shape -> False (a file containing
                          literal "{}" parses as a dict but then fails the
                          payload validator at step 3 below for missing
                          required keys — a different, later, correctly-typed
                          `False`)
```

Any read failure (permission error, the file vanishing between Step 1's
`lstat` and this read, anything else) also returns `False`. **No raw
exception text, repr, or traceback is ever emitted, retained, or returned by
either verifier, under any failure in Steps 0–2.**

**Step 3 — payload validation, dispatched by discriminator (Finding 2, FU6),
run against the bytes the verifier itself just parsed:**

**`verify_cfg1_run_artifact_binding` accepts either legitimate occupant of a
run path.** A scheduled run path may genuinely contain exactly one of two
record kinds — `pi-harness-cfg1-run.v1` (§18 row 15's success case and the
ordinary path) or `pi-harness-cfg1-refusal.v1` (§18 rows 11/15's refusal
fallback, §16.3.8.2) — because a bounded, non-recursive refusal fallback is
written at that **same** path when the primary run record's own emission
fails. Treating a valid refusal artifact as an invalid run-path artifact
merely because it is not `pi-harness-cfg1-run.v1` would be wrong: it is one
of exactly two legitimate kinds for that path, not a third, unrecognized one.
The verifier therefore:

```text
1. inspect only the exact bounded discriminator pair
   (parsed.get("record_version"), parsed.get("record_kind"))
       == ("pi-harness-cfg1-run.v1", "harness configuration diagnostic run")
           -> dispatch to _require_valid_cfg1_run_payload   (§22.1–§22.3)
       == ("pi-harness-cfg1-refusal.v1", "cfg1 artifact emission refusal")
           -> dispatch to _require_valid_cfg1_refusal_payload (§22.4.1)
       anything else (unknown, missing, mixed, malformed, or a
       contradictory pairing — e.g. the refusal literal's record_version
       with the run literal's record_kind) -> False, no validator invoked
2. run exactly the one dispatched validator against `parsed` — closed keys,
   exact literals, exact types, closed enumerations, every cross-field
   invariant of that record kind's own schema, including the schedule-arm
   recomputation each schema states. Any failure returns `False`.
```

Both legitimate kinds then proceed to the **same** Step 4 path-binding checks
below, over the identity fields both schemas share
(`stage_execution_id`/`stage_id`/`run_ordinal`/`arm_id`/`record_filename`) —
a refusal record's own on-disk filename is, by §16.3.8.2's construction,
identical to the run-record filename it stands in for, so no separate
binding logic is needed for it. **This does not turn the durable record into
filesystem authority** (§22.5.1) — a final `True` denotes the stronger,
still-read-only fact: *the current bytes form a valid CFG1 payload of one of
the two legitimate run-path kinds **and** those bytes' own identity fields
match their current actual filesystem location*.

`verify_cfg1_stage_closure_binding` performs **no** dispatch: a stage-closure
path never legitimately holds any kind other than
`pi-harness-cfg1-stage-closure.v1`, so it runs only
`_require_valid_cfg1_stage_closure_payload` (§22.4.2) unconditionally — a
run or refusal record found at a stage-closure path is simply malformed for
that validator and returns `False`, with no discriminator branch to take.

**Step 4 — path binding, only for a payload that already passed Step 3, every
check against the actual, resolved path:**

5. **fresh** §16.3.2-shape root-provenance proof (Level A, the trusted
   package-directory re-proof, strictly before Level B, the `RESULTS_ROOT`
   proof itself) — never a cached result, and never assumed from the fact that
   a live stage once proved it;
6. `resolved_actual = Path(actual_path).resolve(strict=True)` — now safe to
   call, since Step 1 already proved the lexical artifact and its lexical
   parent are each an ordinary, non-reparse regular file / directory
   respectively; a symlink or reparse point anywhere in this path was already
   refused before this line could ever run;
7. `resolved_actual.parent.parent == canonical_results_root` — **artifact
   parent is exactly one execution-directory level below `RESULTS_ROOT`**, not
   two, not zero, not a sibling reached through a different chain;
8. `resolved_actual.parent.name == parsed["stage_execution_id"]` — **the
   actual parent directory's name equals the artifact's own claimed
   identity** (this is what T-33 exercises: a copy at a different execution
   directory fails here even though every payload field is internally
   consistent);
9. `resolved_actual.name ==` the filename recomputed by the **same**
   `_schedule_arm_for`-based internal derivation §16.3.8 defines, applied to
   `parsed["stage_id"]`, `parsed["run_ordinal"]`, `parsed["arm_id"]` — **the
   actual filename equals the schedule-derived filename for the artifact's own
   claimed identity** (T-34: a rename fails here);
10. `(parsed["stage_id"], parsed["run_ordinal"]) ↦ parsed["arm_id"]` agrees
    with `_schedule_arm_for` for that `stage_id` (re-checked here, not merely
    assumed from step 9's filename match — Step 3's payload validator already
    checked this too, so this is defense in depth, not the only check);
11. neither `resolved_actual` nor `resolved_actual.parent` is itself a
    symlink/reparse point relative to a **fresh** `lstat` taken again at this
    point (defense in depth beyond Step 1's earlier check and step 7's
    resolved-path equality — closes the gap where the leaf or parent was
    genuine at Step 1 but was replaced between Step 1 and here; directly
    exercised by T-36's outside-`RESULTS_ROOT` case using a real redirect
    rather than only a differently-rooted path).

Returns `True` only if every step passes (T-33, T-34, T-36, T-37, T-54, T-63,
T-64, T-66, T-67, T-68).

`verify_cfg1_stage_closure_binding(actual_path)` is the identical shape (same
lexical boundary, same self-read, same payload-validator composition, same
root re-proof), substituting the stage-closure filename derivation for step 9
and requiring no `run_ordinal`/`arm_id`/schedule check at steps 9–10 (a
stage-closure record carries no arm identity) — otherwise proving the same
parent-directory-name and fixed-root bindings (T-35).

Malformed, unreadable, or tampered artifacts fail closed and are **never
rewritten, repaired, or moved back** by either verifier — a `False` result is
the entire output, and no exception text, repr, or traceback is ever part of
that output. **A fresh call to either verifier, after the on-disk bytes at the
same path have changed since a prior call, re-reads and re-parses from
scratch — there is no cached result, and no verifier call is ever influenced
by a previous call's outcome** (T-65, mutation and required outcome pinned
exactly, FU6 — see §11.3). Regressions are T-33–T-37, T-50, T-62–T-68
(verifier); the writer-boundary regressions this rewrite also required are
T-55–T-61 (§16.3.8); FU6 adds the dispatch-rule regressions T-80–T-82, the
three-validator regressions T-69, and the remaining T-70 onward (§11.3).

---

## 23. Changelog — FU1 against the original CFG1 design

| # | Original | FU1 |
|---|---|---|
| G1 | F2 presented as an open reviewer decision point | Recorded as the frozen reviewer decision (§0.1); OBS1 reuse rules made explicit (§11.1) |
| G2 | Runner topology stated; controller authority implicitly assumed | Per-run state machine L0–L30 with authority rationales (§16) |
| G3 | No resource ownership model | Ownership table (§17) and never-by-construction rules |
| G4 | Generic post-dispatch indeterminates only | Fifteen-row partial-failure table (§18) |
| G5 | Only pre-dispatch refusals halted | Admission-token rule; `INDETERMINATE_LIFECYCLE` halts; evidence refusal proven non-contaminating (§19) |
| G6 | Record assembly order unspecified | Φ1–Φ12 ordering; sealed after lifecycle; no rewrite cycle; no file authorizes cleanup (§20) |
| G7 | Retention list only | Reduction rule; per-sink allowlists; refusal and stage-closure record shapes (§21) |
| G8 | Field list without authority | Closed-key, literal, typing, invariant, recomputation, and relabel-proof binding rules; schedule-derived output identity (§22) |
| G9 | `ACTIVE` counted `unexpected_tool` calls | Unexpected activity → `INDETERMINATE_UNEXPECTED_TOOL_ACTIVITY` before `ACTIVE`; unidentified ids → indeterminate; disagreement predicates re-derived and proven non-contradictory (§12) |
| G10 | Manipulation check compared runtime state to effective values, post-dispatch | Compares to the **declared** shape, which is what `get_state` serializes (§2.5); now a pre-dispatch gate (§8.2, L16) |
| G11 | T-3 described without a network-safety contract | Interception installed before any Pi import; network/DNS attempt = test failure; synthetic values; test-local payload (§11.3) |
| G12 | Route check and credential position unspecified relative to the workspace | Workspace + baseline before credential (frozen order); route check before any live resource, with the deviation from the controller documented (§16) |
| G13 | Verification output tail and failed node ids implicitly retainable | Removed: model-influenced code can print arbitrary text (§21.2) |
| G14 | Config scrub order unspecified | Endpoint/token material scrubbed before any model-influenced code runs (L24 before L26) |
| G15 | F1 consequence implicit | Explicit roadmap consequence (§13.4) |

---

## 24. Changelog — FU2 against FU1

| # | FU1 | FU2 |
|---|---|---|
| H1 | `stage_execution_id` was described as "an authorization literal" with no mechanically closed domain, used directly inside a filesystem path | Frozen exact grammar — `type(v) is str` + `re.fullmatch(r"[A-Za-z0-9_-]{1,64}", v)` — checked before any filesystem access, never normalized/stripped/repaired (§16.3.1) |
| H2 | `results/<stage_execution_id>/` implied a results root without stating its authority | Fixed, module-owned `RESULTS_ROOT` constant; no parameter may select or replace it (§16.3.2) |
| H3 | Output paths were built by ad hoc string formatting (`SCHEDULE[k]`, `<execution_id>`) at several call sites (L0, §17, §22.4) | One immutable `CFG1StageOutputAuthority`, established once per stage; every run/stage-closure path is a pure function of that one object (§16.3.3) |
| H4 | No TOCTOU or type-confusion closure was stated for the execution id | Single-read, single-bind closure on an exact `str`; `Path`/`PathLike`/subclass/`int`/`bool`/`None` refused before any filesystem operation (§16.3.4, T-19) |
| H5 | Containment was implied by string concatenation | Explicit `resolve()`-based structural parent/child proof, following the repository's own existing `semantic_workspace.py:302` idiom as new CFG1-owned code — no frozen module touched, no new generic framework introduced (§16.3.5) |
| H6 | Existing-directory behavior was unstated for the execution directory specifically | `mkdir(exist_ok=False)` is the exclusive-create proof; existing directory refuses the whole stage; no reuse/merge/rename/delete (§16.3.6) |
| H7 | The record bound `stage_execution_id` and `record_filename` without tying either to a single derivation authority | Record validator re-derives both from the same pure functions the live authority uses, over the record's own retained fields, without needing the live object; stage-closure filename bound identically (§22.3) |
| H8 | §22.3's OBS1 re-validation sentence did not distinguish the unavailable-activity case | Split into two explicit branches: construct-and-validate when available, direct zero/null checks when not — never a fabricated "available" snapshot (§22.3) |
| H9 | Three implementation-time source questions (`qualification_scrub_check` reuse, `_verify_root_authority` reuse, verification child environment) were open | Recorded as resolved by source inspection, with citations, and confirmed to require no frozen-module edit (§7.5) |
| H10 | No offline regressions existed for path/identifier authority | T-16–T-22 added, including a filesystem-operation-spy proof of zero `mkdir`/`open`/`write` calls for every malformed identifier (§11.3) |

---

## 25. Changelog — FU3 against FU2

| # | FU2 | FU3 |
|---|---|---|
| I1 | Containment compared `RESULTS_ROOT.resolve()` against `(RESULTS_ROOT / id).resolve()` — a redirected `RESULTS_ROOT` passes this identically to a genuine one, since both sides resolve through the same redirect | Explicit root-provenance proof, run unconditionally every time `RESULTS_ROOT` is established or re-proven: `lstat` → not-a-symlink/reparse-point (via `ai_dev_orchestrator.workspace.canonical._is_symlink_or_reparse_point`, imported exactly as `ar2/capability.py:39` already does) → `S_ISDIR` → `resolve(strict=True)` equals the lexical expected path exactly. A `resolve()` result is never adopted as trusted merely because it returned (§16.3.2) |
| I2 | No stated contract for whether `RESULTS_ROOT` must pre-exist or may be created | Explicit, frozen ordering: idempotent `mkdir(exist_ok=True)` (an infrastructure step drawing no security conclusion) always followed, unconditionally, by the provenance proof of I1 — including when the `mkdir` was a no-op through a redirect (§16.3.2) |
| I3 | `CFG1StageOutputAuthority` was a `frozen=True` dataclass; "the only constructor" was a documentation claim a caller could bypass by direct instantiation | Process-local mint registry (`_STAGE_OUTPUT_MINTED`), mirroring `qualification.i2b_workspace`'s already-accepted `_MINTED`/`QualificationRunWorkspace` shape (§1.1): `__post_init__` refuses any instance whose `mint_nonce` is unregistered or whose fields disagree with the registered record, so direct/forged construction fails before the object exists (§16.3.3, T-25–T-27) |
| I4 | The authority object, once validated at stage start, was implicitly trusted for the rest of the stage | `verify_stage_output_authority` re-proves type, registry membership, field agreement, `RESULTS_ROOT` provenance, and the execution directory's own `lstat`/canonical/parent/name facts, as the unconditional first action of every path-deriving/consuming call — never cached, never assumed (§16.3.4, T-28, T-31) |
| I5 | No behavior was specified for the execution directory being deleted and replaced by a symlink/junction after a successful mint | Caught at the next consumption boundary by I4's re-`lstat`, before any further write (§16.3.4, T-31) |
| I6 | A stage-output authority failure had no stated console/durable-record split, and the general halt rule (always write a stage-closure record) would have implied writing into the very location that failed provenance | Narrow, explicit carve-out: nothing is written to `results/` on a stage-output authority failure; console-only reporting; already-written genuine run records remain untouched (new §16.3.7, §19.2) |
| I7 | T-13/T-21 claimed payload-only record validation proves a record "cannot be relabelled/moved to another output path" | Narrowed to what payload-only validation actually proves (self-consistency of a record's own declared fields); the filesystem-location claim moved to a new, separate, read-only, offline, post-hoc verifier that the live runner never calls and that grants no authority (§22.3, §22.5) |
| I8 | No mechanism existed to check an archived record's claimed identity against its actual on-disk path | `verify_cfg1_run_artifact_binding`/`verify_cfg1_stage_closure_binding` (§22.5): fixed-root provenance, parent-directory-name-equals-`stage_execution_id`, filename-equals-recomputed-from-payload, schedule-position-still-valid, and not-a-redirect checks against the **actual** resolved path, returning a plain bool, never repairing or rewriting |
| I9 | "Package-owned fixed root" vs. "stage-owned execution directory" ownership was implicit inside a single subsection | Explicit side-by-side contrast of owner, lifetime, creation policy, existing-path policy, and re-proof cadence for the two (new §16.3.0) |
| I10 | No adversarial regressions existed for root redirection, authority forgery, or artifact relocation | T-23–T-37 added, using real filesystem tampering (symlinks/junctions, real copy/rename across genuine execution directories) where the platform allows it, not only mocked return values (§11.3) |

None of I1–I10 required amending `ar2.capability`, `ar2.fixtures`,
`qualification.i2b_workspace`, `qualification.i2_pi_config`, or
`ai_dev_orchestrator.workspace.canonical` — every mechanism is either a direct
import of an already cross-module-imported private helper (I1, following
`ar2/capability.py:39`'s own precedent) or new, CFG1-owned code that mirrors an
already-accepted in-repo shape (I3 mirrors `i2b_workspace`; I1's containment
half and I8 mirror `semantic_workspace.py:302`'s idiom, unchanged from FU2).

---

## 26. Changelog — FU4 against FU3

| # | FU3 | FU4 |
|---|---|---|
| J1 | Writers were described as consuming "only a path previously returned by `run_record_path`/`stage_closure_path`" — a caller convention, since any string is indistinguishable once returned | `emit_cfg1_run_record`/`emit_cfg1_refusal_record`/`emit_cfg1_stage_closure` accept only an authority, a schedule ordinal, and a payload; each derives its own path internally as its own unconditional first action, and no public function anywhere accepts a path/filename/directory/`results_root`/`execution_directory` argument (new §16.3.8, T-38, T-39) |
| J2 | `run_record_path(authority, run_ordinal, arm_id)` let a supported caller choose `arm_id` independently of the frozen schedule | `arm_id` is derived internally, by the one shared `_schedule_arm_for(stage_id, run_ordinal)` function every consumer (L0, payload construction, the writer, the validator, the binding verifier) calls by identity; the writer additionally cross-checks a payload's own claimed `arm_id` against that schedule truth before accepting it (§16.3.8, T-40–T-42) |
| J3 | `RESULTS_ROOT` establishment could `mkdir` before re-proving that the trusted package directory itself had not been redirected since import | A new Level A package-parent re-proof — the identical four-step shape as `RESULTS_ROOT`'s own proof, checked against a value captured once at import and never re-derived — runs before any `RESULTS_ROOT` `mkdir` or other filesystem write, every time, at both mint and re-proof (extended §16.3.2, T-43) |
| J4 | Mint-registry discard at stage end was called "pure memory hygiene, never a security boundary" | Corrected: retirement (registry removal) is the security boundary for an authority whose declared lifetime is one stage; frozen retirement timing for all four exit paths, reusing the existing `UNKNOWN_MINT_NONCE` refusal rather than inventing a new code (new §16.3.9, T-44–T-49) |
| J5 | The read-only binding verifiers had no stated input-type boundary; `actual_path`/`parsed_record` were left to Python's path protocol or a caller-supplied `Mapping` | Exact-type gates (`type(actual_path) is str`, `type(parsed_record) is dict`, both before any filesystem operation) plus a one-walk `json.dumps`/`json.loads` canonicalization discipline (mirroring §22.1 item 6's write-side TOCTOU rule) that consults the original `parsed_record` exactly once; the verifiers then compose the full existing payload validator before the path-binding checks, so `True` denotes "valid payload **and** correct binding" (rewritten §22.5.2, T-50–T-54) |

None of J1–J5 required amending any frozen qualification, OBS1, or AR2 module,
or `ai_dev_orchestrator.workspace.canonical` — every mechanism is new,
CFG1-owned code operating on CFG1's own values (`_schedule_arm_for`, the
`emit_cfg1_*` writers, the Level A package-parent proof, the mint-registry
removal, the verifiers' input gates), reusing the same idioms this design has
used throughout (the exact-type-gate discipline of §16.3.1, the canonical-
snapshot discipline `records.py`'s own `_require_valid_primary_payload` and
this design's §22.1 item 6 already establish, and the four-step provenance
shape §16.3.2 already established for `RESULTS_ROOT` itself, now applied one
level up).

---

## 27. Changelog — FU5 against FU4

| # | FU4 | FU5 |
|---|---|---|
| K1 | §16.3.8's writer sequence read `payload["arm_id"]` (its step 4) before the payload had been type-gated or canonicalized | Reordered into a ten-step sequence: authority re-proof, then trusted-argument schedule derivation, then type-gate, then one-time canonicalization, then "never read the original payload again," then full payload validation, then authority/schedule identity binding, then scrub, then internal filename derivation, then exclusive create — no payload field is read before canonicalization completes (rewritten §16.3.8, T-55–T-57) |
| K2 | A payload's internal self-consistency (its own `arm_id` agreeing with its own `record_filename`) was implicitly treated as sufficient | Every writer independently binds the canonical snapshot to its **own** `authority`/`run_ordinal`/derived-`arm_id` — five identity fields for a run record, the same four plus filename for a refusal record, two plus filename for a stage-closure record — refusing any payload that disagrees with the writer's own identity even if the payload agrees with itself (new §16.3.8 step 7, T-58–T-61) |
| K3 | `verify_cfg1_run_artifact_binding`/`verify_cfg1_stage_closure_binding` took `(actual_path, parsed_record)` — an already-parsed object never bound to the current on-disk bytes | Reduced to `(actual_path: str) -> bool`; the verifier reads and parses the artifact itself, so `True` means the **current** bytes at that path are a valid CFG1 artifact whose own identity fields match that current location — no parameter exists through which a stale or hand-built object could be supplied (rewritten §22.5.2, T-62) |
| K4 | The verifier's path-binding checks called `resolve()` before any symlink/reparse detection, which destroys the evidence a symlink check needs (a resolved path no longer shows whether the original was a link) | A new lexical Step 1 — `lstat` on the literal, unresolved `actual_path` and its parent, checking existence, non-reparse status, and exact kind (regular file / directory) — runs **before** any `resolve()` call; only a lexically-clean artifact and parent ever reach resolution (new §22.5.2 Step 1, T-63, T-64) |
| K5 | No rule bounded how many bytes a post-hoc read, or a writer's own write, could involve | One CFG1-owned `MAX_CFG1_ARTIFACT_BYTES` constant, applied identically at both the writer's pre-write size check and the verifier's bounded read, so neither boundary can be forced into an unbounded read and neither invents a second, unrelated limit (new §16.3.8.1) |
| K6 | §16.3.4 and §22.4 still contained normative language describing `run_record_path`/`stage_closure_path` as public helpers whose return value writers "accept," contradicting §16.3.8's own no-path-parameter API | Both corrected to state, normatively, that writers take only authority, schedule identity, and payload, re-prove authority themselves, and derive every path internally — no bare path or filename crosses the writer boundary in either direction |
| K7 | No regression existed proving the verifier is byte-authoritative across repeated calls, or that a writer never reads a payload field before canonicalization | T-65–T-67 tamper the same on-disk artifact between two verifier calls and prove the later call is unaffected by the earlier one; T-55/T-57 prove zero payload-field reads before the one canonicalization walk, using hostile `Mapping`/`dict`-subclass/mutating-value objects |

T-33's invocation shape is revised to the one-argument API without weakening
its claim (§11.3); T-51–T-54, which tested the now-removed `parsed_record`
parameter, are marked as retargeted to their FU5 replacements rather than
deleted or silently left describing a parameter that no longer exists,
preserving T-1…T-54's numbering exactly as instructed.

None of K1–K7 required amending any frozen qualification, OBS1, or AR2 module.
Every mechanism is a reordering or tightening of CFG1's own already-designed
functions (`emit_cfg1_*`, `verify_cfg1_*_binding`), reusing the canonicalization
discipline §22.1 item 6 and §16.3.1 already established and the lexical-before-
resolve discipline `ai_dev_orchestrator.workspace.canonical`'s own module
docstring already documents as its own order of operations (§1.1's citation of
`canonical.py:410-441`; the module docstring states its steps as "Existence
and kind checks... Symlink/reparse-point checks... Strict canonicalization,"
in that order) — FU5 applies the identical ordering principle to CFG1's own
verifier, not a new invention.

---

## 28. Changelog — FU6 against FU5

| # | FU5 | FU6 |
|---|---|---|
| L1 | §16.3.8/§22.1 required every writer to run "the full §22.1–§22.3 payload validator," a schema defined only for `pi-harness-cfg1-run.v1`, leaving `pi-harness-cfg1-refusal.v1` and `pi-harness-cfg1-stage-closure.v1` with no validator of their own | Three independent, closed payload validators frozen by name — `_require_valid_cfg1_run_payload` (§22.1, unchanged schema), `_require_valid_cfg1_refusal_payload` (new §22.4.1), `_require_valid_cfg1_stage_closure_payload` (new §22.4.2) — invoked by the writer appropriate to each writer's own artifact kind (§16.3.8 step 6, Finding 5); none is a wrapper around another (§22.4.3) |
| L2 | §21.2's refusal- and stage-closure-record field lists were descriptive allowlists, with no closed key set, no `record_filename` field, and no frozen `finding_categories`/`refused_record_kind`/`ordinal_status` vocabulary | §22.4.1/§22.4.2 freeze exact closed schemas: closed key sets, exact literals, `record_filename` added to both (so the existing §16.3.8/T-59 filename-binding requirement has a field to validate), a closed `finding_categories` enum with sorted/de-duplicated/count-relationship rules, a closed `refused_record_kind` enum, and one exact JSON `ordinal_status` structure (a flat object keyed by decimal-string ordinal, valued by a closed status string, arm identity deliberately not duplicated inline) |
| L3 | The read-only run-artifact verifier composed "the" payload validator unconditionally, which could not, as specified, accept a genuine refusal record at a run path — even though §18 row 11 makes that path's other legitimate occupant exactly a refusal record | `verify_cfg1_run_artifact_binding` reads the bounded discriminator pair `(record_version, record_kind)` and dispatches to exactly the run or the refusal validator; any unknown, mixed, missing, or contradictory pair returns `False` with no validator invoked; `verify_cfg1_stage_closure_binding` performs no dispatch, since a stage-closure path never legitimately holds any other kind (new §22.4.3, rewritten §22.5.2 Step 3, T-80–T-82) |
| L4 | The generic "on scrub failure, the CFG1-owned refusal record may be written" rule, read as a general fallback rule, implied a refusal-emission failure could itself trigger another refusal attempt — an unbounded recursion never intended, and §16.3.9's retirement table only partially addressed it (only the collision sub-case) | Frozen, per-writer non-recursion: a primary run-record failure gets at most one freshly-built refusal attempt at the same path (never sourced from the rejected payload's own fields beyond bounded finding categories); `emit_cfg1_refusal_record` never re-attempts itself on its own failure, returning one bounded `EMISSION_FAILED` result instead; `emit_cfg1_stage_closure` never calls the refusal writer under any of its own failures (new §16.3.8.2); one new closed status, `EMISSION_FAILED`, names the refusal-fallback-also-failed case, distinct from both `EVIDENCE_REFUSED` and `EMISSION_COLLISION` (revised §17, §18 rows 16-17, §19.1 item 3, §21.2, §22.4.2) |
| L5 | §16.3.8.1 spoke of "serializing the canonical object for the check and later writing canonical" — two separate serialization calls whose byte-identity was assumed, never pinned, and the size bound itself was stated as "e.g. 64 KiB" rather than an exact integer | One exact emission-bytes pipeline: canonical object → serialize once to `artifact_bytes` → size-check `artifact_bytes` → exclusive-create → write exactly `artifact_bytes`, with no second serialization anywhere after the size check, applied identically to all three record kinds; `MAX_CFG1_ARTIFACT_BYTES` pinned at the exact integer `65536` (rewritten §16.3.8.1, T-70–T-72) |
| L6 | T-21/T-38 stated "no CFG1 function... accepts a path/parameter," which FU4/FU5's own accepted `verify_cfg1_*_binding(actual_path)` signature had already made false as written | Both narrowed to the public **write/emission** API surface, with the read-only verifiers' intentional `actual_path` parameter stated as an explicit, named exception rather than an unaddressed contradiction (revised T-21, T-38) |
| L7 | `§16.3.8 step N` references had drifted from FU5's own renumbering: §22.3 cited "step 5" for the filename derivation that FU5's ten-step sequence places at step 9, and T-40 cited "step 4" (canonicalization) for a schedule-arm mismatch actually caught at step 7 (authority/schedule binding) | Both corrected in place, each annotated with the stale value it replaces so the correction is auditable rather than silent (§22.3 ×2, T-40) |
| L8 | T-58–T-60 described their five-mismatch payloads only as "internally self-consistent," which is also true of a payload that fails its own schema/cross-field checks (e.g. an off-schedule arm for its own claimed ordinal) — collapsing two distinct failure classes into one test description and requiring every malformed identity to reach step 7 | Split explicitly into a payload-schema-failure class (refused by the writer's own dispatched validator at step 6, never reaching step 7 — new T-69's cross-validator matrix is one instance of this class; a second instance, an off-schedule-arm-for-a-fixed-ordinal payload, is implied by T-41's existing ordinal-range coverage and is exercised alongside T-58–T-60's construction) and a valid-other-identity class (passes its own validator at step 6, fails only at step 7's authority binding — T-58–T-60, reworded to state this explicitly, including the "same S1 ordinal/arm, different valid `stage_execution_id`" and "fully valid record for another ordinal, including that ordinal's own correct block/position/arm/filename" constructions) |
| L9 | T-65 permitted two outcomes — `False`, "or `True` with different, correctly-updated content, if the edit happens to preserve valid binding" — which is not a regression oracle, since a non-deterministic expected outcome cannot fail closed on a broken implementation that happens to land on the permitted branch | One exact mutation (`stage_execution_id` changed to a different grammar-valid identifier, file not moved) with one mandatory outcome, `False`; a separate, distinct positive control proves the fresh-read discipline itself against a genuinely untampered artifact (rewritten T-65) |
| L10 | No regressions existed for record-family schema isolation, non-recursive fallback behavior, the exact byte pipeline, or run-artifact-verifier dispatch | T-69–T-82 added (§11.3) |

None of L1–L10 required amending any frozen qualification, OBS1, or AR2
module, `ai_dev_orchestrator.workspace.canonical`, or any accepted FU1–FU5
mechanism's *concept*. Every change is either a genuine three-way schema
split of CFG1's own already-designed record family (L1, L2, mirroring the
existing per-record-kind literal distinctions §22.1 item 2 already made),
a dispatch addition to CFG1's own read-only verifier that leaves its
one-argument signature and lexical-before-`resolve()` discipline untouched
(L3), an explicit non-recursion statement about CFG1's own already-designed
writers that adds one closed status rather than a new mechanism (L4), a
pinning of a bound and a pipeline ordering already gestured at but not fully
closed in FU5 (L5), or a wording/reference correction with no behavioral
change (L6, L7, L8, L9, L10).

---

## 29. Changelog — FU7 against FU6

| # | FU6 | FU7 |
|---|---|---|
| M1 | The primary run-record writer's refusal-fallback eligibility was stated as "before an exclusive-create collision (step 10)," treating step 10 as atomic and collision as its only failure mode | An explicit five-phase vocabulary (`PRE_CREATE` → `FINAL_PATH_CREATE_ATTEMPTED` → `FINAL_PATH_CREATED` → `BYTES_FULLY_WRITTEN` → `EMISSION_CONFIRMED`) is frozen; eligibility is narrowed to strictly `PRE_CREATE` failures, with every post-create outcome (collision, non-collision I/O failure, write/flush/close failure, or ambiguous create-time state) uniformly ineligible for a fallback (rewritten §16.3.8.2 Finding 1, revised step 10 of §16.3.8) |
| M2 | No stated policy existed for bytes left on disk by a create that succeeded followed by a write/flush/close that failed | An explicit post-create residue policy: never overwrite, truncate, rename, or unlink by pathname; the stage-closure status is `EMISSION_FAILED`; the post-hoc verifier's existing malformed-input handling already returns `False` for partial residue with no special-casing needed; a structurally valid residue found later never retroactively changes the already-sealed `EMISSION_FAILED` classification (new §16.3.8.2 paragraph) |
| M3 | §22.4.2 allowed a `halted_after_ordinal == null` ("successfully completed") stage-closure record to contain `EMISSION_COLLISION` or `EMISSION_FAILED` ordinal statuses, directly contradicting §19.1's admission rule, which forbids admitting a later ordinal after either | A mandatory cross-field invariant binds `EMISSION_COLLISION`/`EMISSION_FAILED` at ordinal *j* to `halted_after_ordinal == j` with the matching `halt_reason_code`; the "successful stage" rule is restated as the **derived consequence** — every ordinal exactly `RECORD_EMITTED` or `EVIDENCE_REFUSED`, never the other three statuses (rewritten §22.4.2) |
| M4 | `EVIDENCE_REFUSED`'s prose was inverted ("no valid refusal artifact exists" — actually `EMISSION_FAILED`'s meaning) | All five status meanings restated exactly, in one normative location (§22.4.2, cross-referenced from §16.3.8.2): `RECORD_EMITTED`, `EVIDENCE_REFUSED`, `EMISSION_COLLISION`, `EMISSION_FAILED`, `NOT_EXECUTED` |
| M5 | `halt_reason_code` was "closed enum, non-exhaustive minimum, extended with each new halt-capable failure this or a future revision adds" — not actually closed | One exact, six-member `HALT_REASON_CODES` vocabulary frozen, derived directly from §19.1's own four admission conditions (with item 2 split into its two independent clauses); shared identically by the run record's and the stage-closure record's `halt_reason_code` fields; explicitly excludes §16.3.7's hard stop and §18 row 17's stage-closure-own-failure, both of which write no stage-closure record at all (new §19.4) |
| M6 | T-40 claimed an off-schedule-arm payload was "internally self-consistent" and caught only at writer step 7 — false, since §22.3's own cross-field invariant already makes `arm_id` a pure function of `(stage_id, run_ordinal)`, so such a payload fails at step 6 | T-40 rewritten to state the step-6 refusal correctly, with a forward reference to T-58 Case B for the genuine step-7-only construction; new T-91 proves the step-6 class directly (off-schedule arm, and the analogous wrong-`record_filename` case for both run/refusal and stage-closure records) |
| M7 | T-58–T-60's "valid-other-identity" constructions included an `arm_id`-only and a `record_filename`-only mismatch — both logically impossible, since either field's "wrongness" is already a step-6 self-inconsistency under §22.3/§22.4.2's own invariants | T-58/T-59 rewritten to exactly three genuinely constructible cases (A: different `stage_execution_id`; B: a complete, fully-valid record for a different ordinal; C: a complete, fully-valid `S2` identity presented to an `S1` authority, now constructible under §7.3a); T-60 rewritten to two cases (different `stage_execution_id`; a complete, fully-valid `S2` stage-closure identity presented to an `S1` authority); new T-92 makes explicit, as its own regression, that every step-7 candidate must first be proven to pass its own validator |
| M8 | `stage_id = "S1" \| "S2"` and an S2 ordinal range were schema-accepted, but §13.2 left Stage 2's order as "for example `Q H H Q Q H`," giving `_schedule_arm_for("S2", ...)` no frozen definition to implement | The exact schedule is frozen (new §7.3a): `Q, H, H, Q, Q, H` for ordinals 1–6, with block/position derived at block-size 2; §13.2's "for example" hedge is removed; `LIVE-S2`'s authorization is narrowed to supply only a `stage_execution_id`, never an order (revised §14.1 item 3); new T-93 proves the exact mapping and the shared-function-identity property across all five S2-consuming call sites |
| M9 | T-75 claimed a refusal-fallback-also-fails outcome always means "no artifact of any kind exists at the run path (spy-proven zero writes)" — an unconditional claim FU7's phase model shows is false for the post-create sub-case | T-75 narrowed to the `PRE_CREATE` sub-case only, where "zero writes" is mechanically true; the post-create sub-case is split out as new T-86 (non-recursion + `EMISSION_FAILED`) and T-85 (residue left untouched); §17's Results-path/Stage-closure-record rows and §18 rows 12/16/17 similarly corrected to state "nothing written" only where mechanically true, never as a blanket claim |
| M10 | §12.3's arm-classification note for `EMISSION_FAILED` stated "no artifact of any kind exists for that run" unconditionally | Corrected to "no successfully-confirmed, authoritative artifact exists," with an explicit note that non-authoritative residue may exist but is never read for classification (§12.3) |

None of M1–M10 required amending any frozen qualification, OBS1, or AR2
module, `ai_dev_orchestrator.workspace.canonical`, or any accepted
FU1–FU6 mechanism's *concept*. Every change is either a phase-boundary
correction to CFG1's own already-designed writer sequence with no new
mechanism beyond naming five already-implicit sub-states (M1, M2, M9, M10),
a cross-field invariant added to a schema this design already owns end to
end (M3, M4), a vocabulary freeze derived mechanically from an
already-accepted admission rule rather than invented fresh (M5), a
regression-construction correction that removes logically-impossible test
inputs rather than changing any production semantics (M6, M7), or a
schedule freeze that mirrors Stage 1's own already-accepted shape at a
different block size, changing no accepted S1 behavior (M8).

---

## 30. Changelog — FU8 against FU7

| # | FU7 | FU8 |
|---|---|---|
| N1 | `RUN_RECORD_REFUSAL_FALLBACK_FAILED` was mapped to every `EMISSION_FAILED` outcome, including a direct post-create primary-writer failure for which no refusal fallback is ever eligible or attempted (§16.3.8.2's own corrected eligibility rule) — a false attribution | Renamed to the truthful, neutral `RUN_RECORD_EMISSION_FAILED`, covering all three `EMISSION_FAILED`-producing causes (direct post-create primary failure; `PRE_CREATE` fallback that itself later fails; refusal-writer's own post-create failure) without distinguishing among them in this closed field (rewritten §19.4, §18 rows 16/18, T-89/T-90/T-95/T-96) |
| N2 | The run-record schema required `halt_triggered_by_this_run` to equal "the §19.1 negation" and carried `halt_reason_code`, but §19.1 depends on this run's own emission outcome and registry state, neither knowable until after the run record's own emission resolves — a payload-only validator claiming to recompute its own not-yet-decided future | Both fields removed from the durable `pi-harness-cfg1-run.v1` schema; they remain in-memory-only L30 facts; the stage-closure record becomes the sole durable authority for whether the stage halted, after which ordinal, and why; `run_classification` is confirmed to remain genuinely payload-only recomputable (§22.2, new note before §22.3, §19.4, T-78/T-79/T-94 revised) |
| N3 | T-76/T-87 claimed no stage-closure record could exist or be readable after any non-collision emission failure, regardless of phase — not mechanically true for a post-create close failure, whose residue may be a complete, structurally valid artifact | T-76 narrowed to the `PRE_CREATE` sub-case only (new T-97 isolates its zero-writes proof); T-87 rewritten into the mandatory close-after-full-write regression Finding 3 requires, asserting the **live** emission result is `FAILED` independent of the residue's later parseability; new T-99 proves a post-hoc `True` on that residue never retroactively reclassifies the already-sealed live outcome, for both the stage-closure and run-record cases |
| N4 | L29 was described only in FU6-era scrub-refusal/collision terms, stale relative to §16.3.8/§16.3.8.2's now-frozen ten-step writer contract and phase model, and did not cover the direct primary post-create failure case at all | L29 rewritten as a citation-only pointer to the frozen §16.3.8/§16.3.8.2 contract, never duplicating its algorithm; a previously-uncovered case is given its own §18 row (row 18: direct primary post-create failure, zero fallback attempts); L30 restated as the first point admission is decided, with the L29→L30 ordering made a direct regression (T-101) rather than only documented |
| N5 | No mechanism existed for L0 discovering the next scheduled run path already occupied before that ordinal was ever admitted — neither an ordinary halt (`halted_after_ordinal` would misstate an unadmitted ordinal as admitted) nor `EMISSION_COLLISION` (no writer ever ran) can truthfully encode it | New hard-stop class, `OUTPUT_NAMESPACE_PREOCCUPIED` (new §16.3.10), structurally mirroring §16.3.7's own zero-writes/immediate-retirement/console-only shape: zero run resources created, immediate authority retirement, console-only report, zero durable writes, the occupying object left untouched, resumption requires a new authorization — a third case (alongside §16.3.7 and §18 row 17) explicitly excluded from `HALT_REASON_CODES` because none of the three ever writes a stage-closure record (revised §19.1/§19.2/§19.4, new T-100) |
| N6 | The FU7 header paragraph claimed FU7 "preserves T-1…T-82 exactly," which was not true even of FU7's own changes (T-40, T-58–T-60, T-75 were substantively rewritten) | Corrected in place: existing numbering is preserved (no id renumbered, reused, or deleted) while acknowledging which specific rows' content changed |

None of N1–N6 required amending any frozen qualification, OBS1, or AR2
module, `ai_dev_orchestrator.workspace.canonical`, or any accepted
FU1–FU7 mechanism's *concept* — including the emission-phase model, the
post-create residue no-touch policy, and the three-writer non-recursion
rule, all of which N1–N4 build on unchanged. Every change is either a
truthful renaming of a closed enum member with no change to when it is
produced (N1), a schema narrowing that moves two fields from "durable but
unrecomputable" to "in-memory and immediately usable, with a clean durable
home already provided by the stage-closure record" (N2), a claim narrowed
to the exact phase where it is mechanically true, paired with a regression
proving the previously-overbroad claim's negation in the other phase (N3), a
documentation synchronization pointing L29 at a contract this design already
finalized in FU6/FU7 (N4), a new hard-stop class built by direct structural
analogy by §16.3.7's own already-accepted shape (N5), or a wording
correction with no behavioral change (N6).

---

## 31. Changelog — FU9 against FU8

| # | FU8 | FU9 |
|---|---|---|
| O1 | `emit_cfg1_stage_closure(authority, *, payload)` bound only `stage_id`/`stage_execution_id`/`record_filename` against `authority`; a supported caller holding a genuine ACTIVE authority could construct a different, schema-valid closure payload with no mechanical fact tying it to the actual L30 decision | New `CFG1StageClosureDecision`, sealed only by `seal_cfg1_stage_decision` at L30 after the current ordinal's L29 result is known, mint-registry-backed exactly like `CFG1StageOutputAuthority` (unforgeable, un-mutatable, non-rebindable, exactly-once); the writer's signature becomes `emit_cfg1_stage_closure(authority, *, decision)`, with no caller-selectable `ordinal_status`/`halted_after_ordinal`/`halt_reason_code`/`record_filename`/`stage_id`/`stage_execution_id` surface at all (new §16.3.8.3, revised §16.3.8 step 7's stage-closure row, T-102–T-110) |
| O2 | Multiple §19.1 admission conditions could fail simultaneously with no frozen order for which single `halt_reason_code` a stage-closure record durably carries | One exact, six-step precedence, `_resolve_halt_reason_code`, frozen and derived directly from §19.1's own four conditions (item 2 split), with the two emission-outcome checks taking priority over the four run/lifecycle-level checks; called from exactly one place (L30) and cited by identity everywhere a halt-reason value is needed (new §19.5, T-111–T-114) |
| O3 | The refusal writer's own `FINAL_PATH_CREATE_ATTEMPTED` collision was left implicitly folded into its generic non-collision failure bucket ("a genuine collision has its own... status and is not this case," with no case actually defined for it); the stage-closure writer's own create-attempt outcomes were one undifferentiated bucket | The refusal writer's own collision is classified identically to a primary-writer collision (`EMISSION_COLLISION`); the stage-closure writer's six create/write/flush/close outcome classes are frozen as uniformly "live `FAILED`, no fallback, authority retired," with an optional console-only (never durable) code distinguishing collision from non-collision; new §18 row 19 (refusal-writer collision), row 12/18 scoped explicitly to the primary writer, row 17 broadened to name collision as one of its own uniformly-handled causes (revised §16.3.8.2, §18, T-116–T-122) |
| O4 | §22.4.2 still stated `HALT_REASON_CODES` was "shared identically" with the run record's own `halt_reason_code` field (false since FU8 removed that field) and named only two no-durable-closure cases (stale since FU8's own §16.3.10 added a third) | Both corrected in place to match FU8's own already-current state: the vocabulary is stated as accepted only by the stage-closure record, and the exclusion list names all three cases (§16.3.7 hard stop, stage-closure's own failed emission, `OUTPUT_NAMESPACE_PREOCCUPIED`) (revised §22.4.2, T-123) |
| O5 | Schema validation's relationship to stage-decision provenance was never stated explicitly — a reader could treat `_require_valid_cfg1_stage_closure_payload` returning `True` as proof a record reflects the genuine L30 outcome | Stated explicitly, in both §16.3.8.3 and §22.4.2: validation proves closed-schema coherence only; the stronger guarantee is the conjunction of valid schema, a genuine sealed decision, a matching ACTIVE authority, and writer-internal derivation — and only two of `HALT_REASON_CODES`' six members (`RUN_RECORD_EMISSION_COLLISION`/`RUN_RECORD_EMISSION_FAILED`) are payload-derivable at all; the other four have no mechanical relationship to `ordinal_status` for the validator to check (T-115) |

None of O1–O5 required amending any frozen qualification, OBS1, or AR2
module, `ai_dev_orchestrator.workspace.canonical`, or any accepted FU1–FU8
mechanism's *concept*, including the L1–L28 lifecycle, stage-output
filesystem authority, the emission-phase model, or the post-create residue
policy, all of which O1 and O3 build on unchanged. Every change is either a
new, CFG1-owned mint-registry mechanism mirroring one this design already
uses for `CFG1StageOutputAuthority` (O1, following §16.3.3's own precedent
exactly), a vocabulary-ordering freeze derived mechanically from an
already-accepted admission rule rather than invented fresh (O2, mirroring
§19.4's own existing derivation discipline), a classification gap closed by
applying an already-accepted rule ("collision is never writer-specific")
symmetrically rather than introducing a new rule (O3), or a wording
correction bringing one section's prose into agreement with a design fact
FU8 itself already established elsewhere (O4, O5). **Unlike FU7 and FU8,
FU9 rewrites no existing regression row in place — every T-102 onward
addition is purely additive**, because every FU9 finding was a gap in
coverage or a stale cross-reference, never an incorrect claim an existing
test was built to prove.

---

## 32. Changelog — FU10 against FU9

| # | FU9 | FU10 |
|---|---|---|
| O1 | `seal_cfg1_stage_decision(authority, *, ordinal_status=…, halted_after_ordinal=…, halt_reason_code=…)` was a module-level, importable function; any supported caller holding a genuine, ACTIVE `CFG1StageOutputAuthority` could call it directly with an invented, internally self-consistent fact tuple and receive back a genuine, registry-backed `CFG1StageClosureDecision` — the mint registry proved who issued the object, never that its facts reflected the real L30 stage state | Stage-decision issuance removed from the public, authority-parameterized API surface entirely: sealing exists only as an unindexed, lexically-owned step of the one stage-runner routine that executes L0–L30, reading its facts exclusively from a new runner-local, non-registry, non-exported stage-progress ledger (new §16.3.8.4) populated ordinal-by-ordinal as each L29 result actually resolves — no module-level, importable, or otherwise externally-reachable name exists through which any caller, however privileged, can request a decision carrying facts of its own choosing (revised §16.3.8.3, new requirement 9, T-124–T-125) |
| O2 | L30 was specified as a two-way branch (issue a token, or seal a HALTED decision) with no transition for the stage's own final declared ordinal succeeding — `S1` ordinal 9 or `S2` ordinal 6 passing every admission condition had no ordinal *k*+1 to admit and no L30 rule that produced a terminal record for it, silently contradicting §22.4.2's own already-accepted successful-stage schema shape | L30's transition is frozen as an exact three-way rule (new §19.6): branch A (admission fails) seals a HALTED decision exactly as before; branch B (admission passes, not the final ordinal) issues a token exactly as before; branch C (admission passes, the final ordinal) is new — no token is issued, and a SUCCESS `CFG1StageClosureDecision` is sealed and emitted instead, with `LAST_ORDINAL(stage_id)` derived from the same frozen schedule source `_schedule_arm_for` already consults, never an independently duplicated literal (§19.1 item 5, §19.2's closing paragraph, T-126–T-131) |
| O3 | The decision registry's one-shot consumption was described only as "the decision's own usefulness ends the moment the one `emit_cfg1_stage_closure` call... returns," without freezing an exact mechanism — a still-valid, unrevoked registry entry could in principle answer a second, redundant consumption attempt the same way it answered the first | A new step 4a in the adapted stage-closure writer sequence revokes the decision's `_STAGE_DECISION_SEALED` entry unconditionally, immediately upon re-verification succeeding and before `canonical` is ever built — a second presentation of the same, still-genuine `decision` object fails identically to `UNKNOWN_DECISION_NONCE`, exactly as an unsealed one would (§16.3.8.3 "Decision lifetime," T-132) |

None of O1–O3 required amending any frozen qualification, OBS1, or AR2
module, `ai_dev_orchestrator.workspace.canonical`, or any accepted
FU1–FU9 mechanism's *concept*, including the L1–L29 lifecycle, stage-output
filesystem authority, the three record-family schemas (§22.4.2's
successful-stage shape is reused exactly, not amended), the writer-no-path
boundary, canonicalize-before-read, the emission-phase model, the
post-create residue policy, `HALT_REASON_CODES`, or §19.5's halt-reason
precedence, all of which O1–O3 build on unchanged. `CFG1StageClosureDecision`
itself gains no new field and no new constructor path (O1); §22.4.2's schema
gains no new key, enum member, or invariant (O2); `_STAGE_DECISION_SEALED`'s
own shape (nonce, registered-tuple-equality re-check) is unchanged (O3) —
every change is either removing a public capability that should never have
existed (O1), completing an already-accepted schema's own transition logic
with a derivation from data this design already freezes (O2), or an exact
timing freeze for a lifecycle property the design already asserted in prose
(O3). **T-106, T-107, and T-110 are revised in place** because each assumed
a directly-callable, authority-parameterized sealer that no longer exists;
**T-102 and T-103 receive a wording-only update** for the same reason (the
mechanism each proves — the decision type/nonce gate — is unchanged); every
other T-1…T-123 row is unchanged. T-124 onward is purely additive. (FU11
further revises T-107 and T-125 in place, and updates this row's own and
§17's normative cardinality claims — see §33.)

---

## 33. Changelog — FU11 against FU10

| # | FU10 | FU11 |
|---|---|---|
| O1 | §16.3.8.3 requirement 6 and T-107 stated "L30 runs exactly once per stage execution, exactly as L0–L29 each do" as the mechanical proof that a second terminal seal cannot occur — false: L30 executes once per **admitted ordinal** (up to nine times for `S1`, six for `S2`), exactly once per §19.6 evaluation, and the vast majority of those evaluations (every branch-B one) are ordinary, non-terminal, and never touch the sealing step at all | Requirement 6 is corrected to state the true invariant: L30 runs once per admitted ordinal; the local sealing step fires only when that evaluation selects §19.6 branch A or branch C; the §19.6 state machine itself reaches a terminal branch **at most once** per stage execution (branch A halts the stage, branch C is defined only for the stage's own last ordinal, so no further L30 evaluation for that authority follows either); and even a malformed or test-only second reach of the sealing step is refused by the decision registry's own one-seal-per-`mint_nonce` rule before any second registration — the registry rule, not an L30-invocation-count claim, is the actual mechanical backstop (revised §16.3.8.3 requirement 6, §16.3.8.3's "Decision lifetime" paragraph, §17's sealed-stage-decision row, T-107) |
| O2 | T-125 required proving that direct mutation of the internal `_STAGE_DECISION_SEALED` registry fails because it has "no externally-reachable reference," conflating the accepted issuer/ledger unreachability requirement with an unrequired claim that an internal authenticity/revocation registry resists same-process memory tampering | T-125 is narrowed to prove exactly three things: an invented decision-fact tuple cannot reach the genuine lexical issuer through any supported callable; the runner-local stage-progress ledger cannot be supplied, replaced, returned, or obtained through any supported API; and the real terminal decision, when sealed, reflects only the runner-recorded ledger. It explicitly disclaims any requirement to prove `_STAGE_DECISION_SEALED` resists direct mutation, monkeypatching, closure-cell tampering, or other same-process memory manipulation — an internal authenticity/revocation registry is not an issuance API, and defending arbitrary same-user process-memory tampering remains outside this design's threat model (revised T-125) |
| O3 | §14.1 still authorized only `T-1…T-123`, even though FU10 added `T-124…T-132` — a `CFG1-IMPL` authorization following §14.1's literal text could omit every regression proving FU10's own terminal-issuance-boundary and successful-completion closure | §14.1 is corrected to require `T-1…T-132`, with `T-124…T-132` stated as non-omissible from any `CFG1-IMPL` authorization, and its own FU-by-FU regression-count history extended to name FU10's contribution explicitly (revised §14.1) |

None of O1–O3 required amending any frozen qualification, OBS1, or AR2
module, `ai_dev_orchestrator.workspace.canonical`, or any accepted FU1–FU10
mechanism's *concept*, including the runner-local stage-progress ledger, the
lexically-owned terminal decision issuer, the removal of caller-selected
decision facts, `CFG1StageClosureDecision`'s authenticity registry,
`emit_cfg1_stage_closure(authority, decision)`'s own signature, the decision
mutation/rebinding protections, revocation-before-payload-construction,
L29-before-L30 ordering, §19.5's precedence, §19.6's three-way transition and
branch meanings, `LAST_ORDINAL`'s derivation, or §22.4.2's successful-stage
schema, all of which O1–O3 build on unchanged. `CFG1StageClosureDecision`
itself gains no new field, `_STAGE_DECISION_SEALED`'s own shape is unchanged,
and §19.6's branch behavior is unchanged (O1); the issuer/ledger
unreachability requirement itself is unchanged, only its scope relative to
the internal registry is clarified (O2); no new regression is added and no
existing regression's numbering changes (O3) — every change is either a
wording/proof correction to an invariant that was already intended but
misstated (O1), a scope correction removing an unrequired and previously
unstated defense burden (O2), or a normative-scope correction bringing
§14.1's authorized range into agreement with a regression set FU10 already
froze (O3). T-107 and T-125 are revised in place; T-124, T-126, T-127, T-128,
T-130, T-131, and T-132 are unchanged; T-102/T-103's own FU10-era
change-history note is corrected for accuracy but the tests themselves are
unchanged.

---

## 34. Changelog — FU12 against FU11

| # | FU11 | FU12 |
|---|---|---|
| O1 | Requirement 6's mechanism proved "at most one terminal decision per authority" entirely via `_STAGE_DECISION_SEALED` — the same registry step 4a revokes the consumed decision's own entry from, at the start of that decision's one permitted consumption. A malformed/test-only second reach of the sealing step **after** a first decision was sealed *and consumed* would find the registry with no trace of the first seal, and could register a second, independently genuine decision — a sequence entirely within requirement 6's own stated threat scope | A new, independent, process-local registry, `_STAGE_TERMINAL_SEAL_HISTORY` (keyed by `authority.mint_nonce`), proves seal-once on its own: established once, at the first seal, strictly before the decision itself is registered or constructed, and never removed by decision consumption, by that consumption's own write succeeding or failing, or by authority retirement. `_STAGE_DECISION_SEALED` is narrowed to prove decision authenticity/consumability only — the property it was always able to prove soundly — and step 4a's revocation is scoped explicitly to never touch the new registry (revised §16.3.8.3 requirement 6, revised step 4a, revised "Decision lifetime," new "Terminal-seal history lifetime" and "Partial-failure atomicity of the mint sequence," revised §17 rows, revised T-107, new T-133–T-136) |

O1 required no amendment to any frozen qualification, OBS1, or AR2 module,
`ai_dev_orchestrator.workspace.canonical`, or any accepted FU1–FU11
mechanism's *concept*, including L30's per-admitted-ordinal cardinality,
§19.6's branch A/B/C semantics and terminal-sealing-only-on-A-or-C rule, the
runner-local stage-progress ledger, the lexically-owned issuer's
unreachability, `CFG1StageClosureDecision` itself (no new field, no changed
constructor path), its field/nonce/authenticity checks (§16.3.8.3 steps
2–3, unchanged), its authority-rebinding protection (step 4, unchanged),
`emit_cfg1_stage_closure(authority, decision)`'s own signature (unchanged),
decision one-consumption semantics (T-132, unchanged), step 4a's position
before payload construction (unchanged — only its *scope* is clarified, not
its timing), or FU11's supported-caller threat-model scope (unchanged and
unwidened — `_STAGE_TERMINAL_SEAL_HISTORY` is held to the identical
"internal fact, not an issuance API, no private-memory-tampering defense
required" standard FU11 already established for `_STAGE_DECISION_SEALED`),
all of which O1 builds on unchanged. The change is exactly what the Finding
requires and no more: one new, disjoint, in-memory-only fact with its own
frozen lifetime and partial-failure behavior, added because the existing
registry could not simultaneously serve as both the consume-once mechanism
(which *requires* revocation) and the seal-once mechanism (which *requires*
the opposite — a fact that survives revocation) — the two requirements were
never reconcilable within one registry, and FU12 gives each its own. T-107
is revised in place (its threat-scope statement was already correct; only
its mechanism-proof needed the exact adversarial ordering T-107B adds);
T-124, T-126, T-127, T-128, T-130, T-131, and T-132 are unchanged; T-133–T-136
are purely additive.

---

## 35. Changelog — FU13 against FU12

| # | FU12 | FU13 |
|---|---|---|
| O1 | The "Partial-failure atomicity of the mint sequence" paragraph named three points at which the terminal-decision mint sequence can fail but assigned none of them a lifecycle disposition: no retirement timing, no console-reporting rule, no row in §16.3.9's retirement table or §18's partial-failure table, and no member of §19.4/§22.4.2/T-123's no-confirmed-closure enumeration. Its first bullet additionally claimed that a failure before history establishment leaves "a later attempt... still a legitimate first seal," contradicting the same subsection's own "no recovery or retry path is invented for any of these failures," and T-135(c) expected a subsequent legitimate seal to succeed | One closed, console-only, bounded terminal code, `STAGE_DECISION_MINT_FAILED`, is frozen for any mint-sequence failure at any of the three points, occurring at any point after L30 selects §19.6 branch A or branch C. On this disposition: no second mint attempt, no admission token, no stage-closure writer call, no stage-closure artifact, all already-confirmed run/refusal artifacts untouched, immediate stage-output-authority retirement (before console reporting), one bounded console report, and required-new-authorization resumption — never added to `HALT_REASON_CODES`, never placed in any durable schema. The first bullet's retry claim is removed and replaced with an explicit statement that technical retryability is irrelevant and operational retry is forbidden regardless of which registry gained an entry (revised §16.3.8.3 requirement 6's partial-failure-atomicity paragraph, new "Terminal-decision mint failure disposition" paragraph, revised §16.3.9 retirement-ordering table, revised §18 (new row 20), revised §19.2 (third narrow exception), revised §19.4 (four excluded cases), revised §22.4.2 (four excluded cases), revised §21.2 console-sink note, revised T-123, rewritten T-135, extended T-136, new T-137–T-141) |

O1 required no amendment to any frozen qualification, OBS1, or AR2 module,
`ai_dev_orchestrator.workspace.canonical`, or any accepted FU1–FU12
mechanism's *concept*, including `_STAGE_DECISION_SEALED` as the per-decision
authenticity/consumability registry, `_STAGE_TERMINAL_SEAL_HISTORY` as the
independent per-authority seal-once history, requirement 6's exact
history-check → history-establishment → decision-registration →
decision-construction sequence (unchanged in order and in step numbering),
step 4a's scope (still revoking only `_STAGE_DECISION_SEALED`, never
`_STAGE_TERMINAL_SEAL_HISTORY`), T-107A/T-107B, T-132's consume-once proof,
T-133/T-134's seal-history-survival proofs, the terminal-seal-history
lifetime's own frozen survival requirements, FU11's supported-caller threat
model, §19.6's branch A/B/C semantics and terminal-sealing-only-on-A-or-C
rule, `LAST_ORDINAL`'s schedule-derived provenance, and §22.4.2's
successful-stage schema — all of which FU13 builds on unchanged. §19.6
itself gains one cross-reference sentence, not a changed branch semantic:
branches A and C still mean exactly what FU10 froze when their own sealing
attempt succeeds; FU13 only names what happens when that attempt does not.
The change is exactly what the two findings require and no more: one new
closed terminal code with a fully specified, uniform lifecycle disposition
across all three already-named failure points, plus the removal of one
self-contradictory retry claim the same FU12 text made and immediately
undercut elsewhere. T-107, T-124–T-134 are unchanged; T-135 is rewritten in
place (its three sub-cases are preserved, but sub-case (c)'s expected
outcome is corrected); T-136 is extended, not replaced; T-137–T-141 are
purely additive; T-123 gains an extended scope (three cases to four) without
changing its own audit technique; §19.4 and §22.4.2 each gain one additional
excluded case without changing the treatment of the three they already
named.

---

## 36. Changelog — FU14 against FU13

| # | FU13 | FU14 |
|---|---|---|
| O1 | T-135's introductory sentence claimed none of its three sub-cases is followed by any further sealing attempt, while sub-cases (a) and (b) then required a synthetic subsequent sealing reach to prove `_STAGE_TERMINAL_SEAL_HISTORY` refuses it — a direct, self-contradictory pair of claims within one regression's own text | T-135's introductory sentence is split into two explicit, non-contradictory claims: the **stage runner itself** performs zero second mint/seal attempts in all three sub-cases (the operational-retry guarantee), while sub-cases (a) and (b) separately and explicitly permit **the test harness** to force exactly one malformed, test-only second reach of the sealing step, which is not an operational retry and grants no production retry path. Sub-case (c), where no history entry is ever created, is corrected to prove zero registry entries, authority retirement, `STAGE_DECISION_MINT_FAILED`, and zero closure-writer calls — never a second-seal refusal from a history fact that was never established (revised T-135) |
| O2 | T-138 claimed `_STAGE_TERMINAL_SEAL_HISTORY` remains present "for the remainder of the test process's reachable lifetime" — a lifetime wider than, and contradicting, T-136's own frozen before/after-runner-return lifetime | T-138 is narrowed to state exactly the four ordered facts T-136 already freezes: present through retirement, present through console reporting, present for the remainder of the stage runner's own invocation, and absent after that invocation returns — the "test process" wording is removed and never reintroduced (revised T-138) |
| O3 | T-139 listed three assertions — orphan decision entry exists; after the runner returns the orphan is absent; seal history still refuses a synthetic second seal — without ordering the third against the runner's own return, so it could be misread as claiming the seal-history entry still exists and still refuses a second reach *after* return, contradicting T-136 | T-139 is restructured into two explicitly ordered groups: **while the stage-runner invocation is still active** (history present; a harness-forced malformed second reach refused at requirement-6 step 2; the orphan decision entry unusable), strictly **before** **after the invocation returns** (the orphan decision entry absent; the seal-history entry also absent; no post-return backstop claimed or required, since no sealing-capable lexical path remains) (revised T-139) |
| O4 | §16.3.8.3's post-registration-failure paragraph described the orphaned `_STAGE_DECISION_SEALED` entry as becoming "permanently orphaned data," a phrase readable as contradicting FU13's own bounded mint-failure cleanup | The phrase is narrowed to "orphaned and unusable until the bounded mint-failure cleanup removes it," with no change to the underlying authority semantics (revised §16.3.8.3 wording only) |

O1–O4 required no amendment to any frozen qualification, OBS1, or AR2
module, `ai_dev_orchestrator.workspace.canonical`, or any accepted
FU1–FU13 mechanism's *concept*. `STAGE_DECISION_MINT_FAILED` remains the
uniform terminal disposition for every terminal-decision mint failure;
zero operational retry, zero next-ordinal admission, zero stage-closure
writer call, immediate stage-output-authority retirement before console
reporting, untouched prior run/refusal artifacts, bounded console-only
reporting, and raw-exception containment are all unchanged. §16.3.8.3
requirement 6's exact step sequence, `_STAGE_DECISION_SEALED`'s and
`_STAGE_TERMINAL_SEAL_HISTORY`'s own distinct properties and lifetimes,
the retirement-ordering table's new row, §18's row 20, §19.2's third
exception, §19.4's and §22.4.2's four-case enumeration, and §21.2's
console-sink note are all unchanged and unreopened by FU14. No test ID is
added, removed, or renumbered: T-135, T-138, and T-139 are corrected in
place for wording and internal ordering only, each still proving exactly
what its FU13 version proved about the design; T-136 is untouched and
remains the sole authoritative cleanup-timing regression; T-1…T-141 remains
the exact, unchanged implementation scope (§14.1, wording-only note added).

---

## Final outcome

```text
CFG1 DESIGN READY — IMPLEMENTATION MAY BE AUTHORIZED
```
