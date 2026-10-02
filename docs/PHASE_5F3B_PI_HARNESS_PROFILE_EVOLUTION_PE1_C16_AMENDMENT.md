# Phase 5F3B-PI-HARNESS-PROFILE-EVOLUTION PE-1-C16 — Narrow Contract Correction (Version-Text Comparison Count)

```text
5F3B-PI-HARNESS-PROFILE-EVOLUTION-PE1-C16    CANDIDATE / PENDING INDEPENDENT REVIEW
KIND                                         NARROW CONTRACT CORRECTION (additive supersession
                                             of exactly two PE-1 statements)
CORRECTS                                     ONE internal contradiction of PE-1 R2:
                                             §1 / §26.3 C-16 ("exactly two" version-text
                                             comparisons) vs §21 rule 4 / §26.3 C-11
                                             (mandatory declared-version equality in the
                                             post-hoc binding verifier)
AUTHORIZES                                   NOTHING — no implementation, no acceptance, no
                                             profile, no approval, no live run, no authorization
BASE (FROZEN, NOT EDITED)                    docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md
                                             PE-1 R2
  committed at                               c64b9aaffe85b4dc040f7284b1ad251587f79090
  git blob                                   3d81947c74491df4daf0108cfc0c887794e88446
  SHA-256                                    220710deb9dbf45cc854aca8cc088d7e3f82770b31cdd683d8c7e8824f899794
  (re-verified by this turn: working file git hash-object == HEAD:<path> blob; sha256sum)
PE-0 / HPP-1                                 ACCEPTED / FROZEN — not edited, not reopened
PE-1 B10–B14                                 CLOSED — not reopened
PE-2a / PE-2b                                ACCEPTED SEMANTICS — not reopened
PE-2c                                        IMPLEMENTED UNCOMMITTED / PENDING INDEPENDENT CODE
                                             REVIEW — NOT ACCEPTED BY THIS DOCUMENT
REPOSITORY HEAD AT AUTHORING                 87d2adb5304bf494bf8409b78dd2f4c100ff37fc
CORRECTED COUNT                              EXACTLY THREE permitted production comparisons of
                                             declared version text (V1, V2, V3); any fourth forbidden
```

> **THIS DOCUMENT CORRECTS EXACTLY ONE CONTRADICTION AND GRANTS NO AUTHORITY.**
> It makes PE-1 §1's count of permitted version-text comparisons consistent
> with the verifier PE-1 §21 already mandates. It is monotone toward evidence
> integrity: the only effect of the comparison it admits into the count is that
> a read-only, post-hoc verifier may **reject** an evidence packet.
>
> **Disclosure of what the turn that authored this file did (exact).** It read,
> inside `C:\dev\ai_dev_orchestrator` only, with read-only `git`, `grep`,
> `sed`, `ls`, `wc`, `sha256sum` and the Read tool: PE-1 R2 (§0–§2, §4.7, §6.5,
> §8.3, §9.4, §10.2–§10.5, §19.3, §20.3 item 7, §21, §26, §29, Status), PE-0
> §2.3 and §18, and — without modifying them — the uncommitted PE-2c files
> `pi_profile_binding_verifier.py` (header, rule-4 helper, entry point) and the
> C-16 audit in `tests/test_cfg1_pe2c_records.py`, plus a `grep` for importers
> of the verifier module. It created exactly this one file, modified, formatted,
> staged and committed nothing, ran no test suite, imported no AIDO/CFG1 module,
> did not run Pi, Node, npm or `pi --version`, did not contact B300 or any
> backend or model, and read no credential or endpoint value.

---

## 0. Scope, precedence and reading rule

1. **Effective design for a profile-aware CFG1 run** = the frozen CFG1 chain +
   PE-0 R3 (HPP-1) + PE-1 R2 + **this correction**. This correction governs only
   over the two PE-1 statements it names in §9. Every other PE-1 clause — and
   every PE-0, CFG1-chain, PE-2a and PE-2b semantic — is preserved exactly.
2. **Historical documents are immutable.** PE-1 R2 is not edited. The
   superseded statements remain a true record of what PE-1 R2 said; they only
   cease to be forward-looking contract.
3. **Normative words** carry PE-1 §0.4 meanings ("must", "exactly", "only",
   "never"; "refuse" = fail closed with no partial result).
4. **Nothing here is a PE-2c review.** Observations of the uncommitted PE-2c
   working tree in §10 are informative only and establish no acceptance.

---

## 1. The exact contradiction

PE-1 R2 §1 (Governing rule), second bullet, states (verbatim):

> **No production decision may compare a version string** to decide admission,
> matching, eligibility, launch, evidence reuse or qualification authority.
> Exactly two production comparisons of version text exist, and neither decides
> authority (§9.4, §10.2): (a) the loader's **integrity** check that a profile's
> `declared` field equals the projection it recomputes from the same committed,
> hash-bound bytes; (b) the classifier's **delta enumeration** for PMD, which
> lists a changed `version` value as a fact after the C2 relation has already
> been decided with that value masked. PE-2 audits enforce that no third
> comparison exists (§26.3 C-16).

PE-1 R2 §21 (Profile binding verifier — read-only, post-hoc, never in the
runtime path), rule 4, requires (verbatim):

> recomputes `eligible(CFG1-CC1)` at that revision; `stage_pi_profile_id` and
> every non-null run `pi_profile_id` must be members and equal the stage
> profile; every declared version must equal that profile's
> `declared.package_version`;

PE-1 R2 §26.3 then requires both:

| Id | PE-1 R2 text (verbatim) |
|---|---|
| C-11 | binding verifier: head lookup, eligibility at `H`, declared-version equality, mismatches and v1/v2 inputs refused |
| C-16 | AST audit: no production module compares a declared version outside the two permitted sites of §1 |

**The contradiction.** §21 rule 4 / C-11 mandate a production comparison of
declared version text (each v3 run/stage declared package version against the
bound profile's `declared.package_version` at the exact APS head). That
comparison is neither §1 site (a) (the loader's recomputation integrity check)
nor §1 site (b) (PMD delta enumeration). §1 says no third comparison exists and
C-16 audits that it does not. An implementation therefore cannot satisfy C-11
and C-16 simultaneously: any conforming §21 verifier is a C-16 violation, and
any C-16-clean tree lacks the §21 check.

**Root cause.** §1's count enumerated the comparisons inside the policy
authority (PE-2a/PE-2b) and omitted the one inside the read-only post-hoc
verifier that §21 separately specifies. The *purpose* rule of §1 ("neither
decides authority") is internally consistent with §21; only the *count* and
C-16's reference to "the two permitted sites" are wrong.

---

## 2. Removing the §21 equality is not a resolution

The contradiction could be "resolved" mechanically by deleting the
declared-version equality from the binding verifier. **That is a weakening and
is NOT authorized.** It would let a v3 packet carry declared-version provenance
that disagrees with the committed policy it claims to be bound to, and still
verify — exactly the provenance-integrity failure PE-1 §1's third bullet
("Version provenance is never removed") and §21 exist to exclude. §21 rule 4 and
C-11 are **preserved unchanged and remain mandatory** (§9.3). The correction is
made on the count side only.

---

## 3. Corrected version-text rule

### 3.1 Replacement for the superseded PE-1 §1 sentences

For profile-aware runs, from acceptance of this correction, the PE-1 R2 §1
second bullet reads as follows (the first sentence is unchanged; the remaining
sentences replace the superseded ones):

> **No production decision may compare a version string** to decide admission,
> matching, eligibility, launch, evidence reuse or qualification authority.
> **Exactly three** production comparisons of declared version text exist, and
> none decides authority: **V1** the PE-2b loader's **integrity** check that a
> profile's stored `declared` projection equals the projection it recomputes
> from the same committed, hash-bound bytes (§9.4); **V2** the PE-2a
> classifier's PMD **delta enumeration**, which lists a changed `version` value
> as a fact after the C2 relation has already been decided with that value
> masked (§8.3, §10.2); **V3** the PE-2c read-only, post-hoc profile binding
> verifier's **evidence-integrity** equality of each v3 declared package version
> with the bound profile's `declared.package_version` at the exact APS head
> carried by that evidence (§21 rule 4). PE-2 audits enforce that no fourth
> comparison exists (§26.3 C-16 as corrected by PE-1-C16).

### 3.2 Definition — what a "comparison of declared version text" is

For this correction and for C-16, a **comparison of declared version text** is
any production operation whose result depends on the relation between a
declared version value (`package_version`, `pi_ai_version`,
`pi_agent_core_version`, or a manifest top-level `"version"` value, or any value
derived from one by slicing, parsing, splitting, normalizing or case folding)
and another value — whether by equality, inequality, ordering, membership,
containment, prefix/suffix/substring test, pattern match against another
version, semver or numeric parse-and-compare, or a lookup keyed by a version
value — **and** whose result can change control flow, a returned value or a
recorded fact.

---

## 4. The exactly three permitted sites

Each site is defined by its **owner, its operands and its purpose**. A site's
extent is exactly that; it is not widened or narrowed by this correction.

### SITE V1 — PE-2b loader integrity

| | |
|---|---|
| Owner | the accepted PE-2b committed-policy loader |
| Operands | a committed profile record's stored `declared` projection, and the projection the loader freshly recomputes (§6.5) from the same committed, hash-bound inventory / manifest-bundle bytes (§9.4) |
| Purpose | committed policy integrity only — "recompute everything derivable, trust nothing derivable" |
| May | refuse the policy chain on disagreement (existing §9.4 behavior) |
| Must not | choose, rank or admit a profile from the version value; express any notion of semantic-version compatibility; decide eligibility (eligibility is §9.6, computed from approval and retirement records, never from version text) |

### SITE V2 — PE-2a PMD delta enumeration

| | |
|---|---|
| Owner | the accepted PE-2a classifier / PMD delta-list machinery (§10.2), including its use by identity on the PE-2b loader path (§26.0, B-14/B-15) |
| Operands | the top-level `"version"` values of a permitted manifest `M ∈ D` on the candidate and reference sides |
| Purpose | mechanical delta enumeration only — emit a `VERSION` delta with exact old/new strings |
| Precondition | the C2 relation (§8.3) has **already** been determined with that version value slot replaced by `MARKER` |
| Must not | decide C2 membership, a floor class, compatibility, or any approval consequence from the version value |

The loader's §10.4 rule 1 equality between a committed PMD delta list and the
list recomputed by the accepted PE-2a enumeration is the loader's integrity
consumption of the V2 enumeration — the same accounting PE-1 R2 §1 already made
by citing §10.2 — and is **not** a fourth site. This sentence records the
existing extent of V1/V2; it adds and removes nothing.

### SITE V3 — PE-2c post-hoc evidence binding verifier

| | |
|---|---|
| Owner | the PE-2c read-only profile binding verifier specified by PE-1 §21 |
| Operands | each v3 run record's `pi_profile_declared_package_version` (for a non-null `pi_profile_id`) and the stage closure's `stage_pi_profile_declared_package_version`, and the exact `declared.package_version` of the profile eligible at the exact APS head carried by that evidence, as recomputed by the accepted PE-2b loader for the committed revision whose file SHA-256 equals that head |
| Purpose | durable evidence integrity only — the recorded copy of declared provenance equals the committed source it claims to be copied from |
| May | cause the **post-hoc verifier** to reject an evidence packet (refuse; closed result code) |
| Must not influence | P; profile matching; eligibility; approval; retirement; launch; L1 admission; L14; L21A; stage execution; evidence reuse; qualification class; live-authorization consumption; any runtime control flow |

**The verifier is not in the runtime authorization path.** This restates, and
does not change, PE-1 §21's title and §19.3's last paragraph ("Binding
`pi_profile_id` and the declared version to the committed APS chain is the
separate read-only verifier of §21, never the payload validator").

### 4.1 Any fourth comparison is forbidden

No production module may contain a comparison of declared version text (§3.2)
outside V1, V2 and V3. In particular there is no comparison of declared version
text in P, the gate, L1, L14, L21A, the classifier of runs, the halt or
admission logic, the executor, the stage runner, any writer, any validator of a
record payload, the discovery tool's choice of anything, or the evidence-reuse
rules.

---

## 5. Core rule preserved unchanged — no semver, no version authority

The stronger core rule of PE-0 §2.3 and PE-1 §1 is preserved exactly. **No
production decision may use a version string to decide:**

- admission;
- profile matching;
- eligibility;
- launch;
- evidence reuse;
- qualification authority;
- compatibility;
- profile selection;
- live authorization.

There remains **no** semver compatibility rule, **no** version fallback,
**no** nearest-version match, **no** version-based authority, and **no**
runtime- or model-reported version authority (PE-1 §2.2: P executes nothing; no
`pi --version`; runtime/model-reported versions are never authority). Version
remains **provenance / evidence metadata**. PE-0 §18's shorthand "no code path
compares a version" continues to be read under PE-0 §2.3's purpose-qualified
statement ("to decide admission, selection, matching, eligibility, or launch"),
exactly as it already had to be for PE-1 R2's sites (a) and (b); PE-0 is not
edited or superseded.

---

## 6. C-11 / C-16 normalization

### 6.1 C-11 — unchanged

C-11 is **unchanged in meaning and remains mandatory**: the binding verifier
must verify declared-version equality at the exact bound APS head and refuse a
mismatch (together with head lookup, eligibility at `H`, and refusal of v1/v2
inputs).

### 6.2 C-16 — corrected text

PE-1 R2 §26.3 row C-16 is replaced, for acceptance of PE-2c, by:

| Id | Proves |
|---|---|
| C-16 | AST/static audit: no production module compares declared version text (PE-1-C16 §3.2) outside the **exact three** permitted integrity/delta sites — **V1** PE-2b loader integrity, **V2** PE-2a PMD delta enumeration, **V3** PE-2c post-hoc binding-verifier evidence-integrity equality (PE-1-C16 §4); any fourth production comparison fails the audit; the audit is not vacuous (V1 and V3 are detected where they are implemented) |

### 6.3 What the C-16 audit counts and does not count

The audit must be **semantic / AST-based**: it identifies comparison operations
by their operands and effect (§3.2), not by textual coincidence. It must not be
defeated by, and must not count as version comparisons:

- key-name strings (e.g. the literal `"package_version"` used as a dictionary
  key or record-schema key);
- schema-field names and closed key-set declarations;
- length checks and the §6.5 grammar validation of a single version value
  (type, 1…128 characters, 0x21–0x7E) — a validation of one value against a
  fixed grammar, not a comparison of version text with other version text;
- nullness and type-exact checks, including the bi-implications
  `V == null ⇔ Pid == null` (§19.3 R3-S7) and §20.2 invariant 1;
- serialization (canonical JSON emission) of a declared value;
- copying declared provenance (e.g. the writer's design-B derivation of the
  stage declared version from the sealed snapshot, §20.3 item 7; copying the
  matched profile's declared version into a v3 run record, §19.1);
- comments and docstrings.

Conversely, the audit must not be evadable by indirection: a comparison of a
value derived from a declared version, a comparison performed through a helper
function, or a lookup keyed by a version value is a comparison (§3.2) and is
attributed to the site whose owner and purpose it serves. A conceptual site may
be implemented across a function and private helpers of the **same owning
module**; independent code review must confirm that every allow-listed location
performs only its site's comparison for its site's purpose. Test modules are not
production modules for C-16; the separate PE-0 §11.2 / PE-1 §26.3 rule that
conformance tests never compare a version is unchanged.

---

## 7. Proof that V3 is post-hoc evidence integrity, not runtime authority

1. **Position.** PE-1 §21 defines the verifier as "read-only, post-hoc, never in
   the runtime path". Its inputs are one stage execution's **already-written**
   v3 artifacts and the committed policy chain of the verifying checkout. Those
   artifacts exist only after the runtime decisions (P, gate, L1, L14, L21A,
   item 1A, halt, classification, closure) have been made and recorded, so V3's
   result is temporally incapable of being an input to any of them.
2. **Operands are copied provenance, not selection inputs.** Runtime profile
   selection is by `profile_id`, which is a function of the payload fingerprint
   and resolution exposures (§4.7) — "Version text is excluded from authority
   except insofar as its manifest bytes already contribute to
   `payload_fingerprint`". The v3 declared version is **copied** from the matched
   profile's loader-bound value (§19.1) or **derived by the writer** from the
   sealed snapshot (§20.3 item 7, design B). V3 checks that a recorded copy
   equals its committed source; it consults no version to choose, rank or admit
   anything.
3. **Direction is refusal-only.** A V3 match adds nothing: it creates no
   eligibility, approval, reuse right, qualification class, authorization or
   launch permission ("a verified result recreates no authority"). A V3 mismatch
   can only make the post-hoc verifier reject a packet. There is no
   nearest-version match, fallback or repair.
4. **Exact-head binding, not compatibility.** The reference value is the one
   `declared.package_version` of the one profile id at the one revision whose
   file SHA-256 equals the head the evidence carries (§21 rules 3–4). No other
   profile, no other revision and no version relation other than exact equality
   is consulted.
5. **Normative firewall (this correction).** §4 SITE V3 "Must not influence"
   freezes that V3's result never reaches P, matching, eligibility, approval,
   retirement, launch, L1, L14, L21A, stage execution, evidence reuse,
   qualification class, live-authorization consumption or runtime control flow.
   Wiring V3's result into any of them would be a fourth, forbidden use and a
   violation of §21's "never in the runtime path".

Therefore V3 is a durable-evidence-integrity check of exactly the kind PE-1 §1
already permits in purpose ("neither decides authority"); only its omission from
§1's count was wrong.

---

## 8. Authority impact

**This correction grants NO new authority.** It does not:

- approve a profile;
- change any eligible set;
- change P;
- change L1, L14 or L21A;
- alter runtime classification;
- alter halt or stage-halt semantics;
- alter APS structure, chain or head rules;
- alter PMD authority or the C2 relation;
- alter evidence reuse;
- alter PE-6 authorization semantics.

It only makes PE-1 §1's version-comparison count consistent with the already
mandatory §21 evidence-binding verifier. Removing the verifier comparison would
be a weakening and is **NOT authorized** (§2).

---

## 9. Supersession scope (exact)

### 9.1 Superseded — exactly two statements

| # | PE-1 R2 location | Superseded text | Replacement |
|---|---|---|---|
| C16-S1 | §1, second bullet, sentences two and three | "Exactly two production comparisons of version text exist, and neither decides authority (§9.4, §10.2): (a) … (b) … PE-2 audits enforce that no third comparison exists (§26.3 C-16)." — specifically the normative claim that **exactly two** production version-text comparisons exist and **no third** exists | §3.1 of this correction: **exactly three** (V1, V2, V3); no fourth |
| C16-S2 | §26.3 row C-16 | "AST audit: no production module compares a declared version outside the two permitted sites of §1" — specifically the reference to "the two permitted sites of §1" | §6.2 of this correction: the exact three sites V1, V2, V3 |

The first sentence of the §1 second bullet ("No production decision may compare
a version string to decide admission, matching, eligibility, launch, evidence
reuse or qualification authority") is **not** superseded. PE-1 R2's sites (a)
and (b) survive unchanged as V1 and V2.

### 9.2 Not superseded

**Nothing else in PE-1 is superseded.** In particular, unchanged: PE-1 §1 first
and third bullets; §2 supersession matrix S-1…S-7 and extensions X-1…X-4; §4.7;
§6.5; §8.3; §9.4; §9.6; §10; §19 (including R3-S7 and §19.3's last paragraph);
§20 (including §20.3 item 7, design B); §21 in full; every §26 row other than
C-16 (including C-11); §26.4; §27–§29; and every PE-0 B1–B9 and PE-1 B10–B14
disposition.

### 9.3 Preserved and mandatory

**PE-1 §21 (all five rules) and §26.3 C-11 remain mandatory.** The binding
verifier must perform the declared-version equality at the exact bound APS head
and refuse a mismatch.

---

## 10. PE-2c disposition

- **PE-2c implementation exposed the contradiction.** Its binding verifier
  necessarily contains the §21 rule-4 equality, which the frozen C-16 wording
  forbade.
- **The current implementation's third comparison, in the read-only post-hoc
  binding verifier, is the intended V3 site.** (Informative observation of the
  uncommitted working tree: `experiments/pi_harness_cfg1/pi_profile_binding_verifier.py`
  performs the equality in its rule-4 helper and documents that nothing in P,
  the gate, L1, L14, L21A, the executor, the runner or any writer imports it; a
  `grep` of the package's production modules found no importer. The PE-2c C-16
  test already allow-lists the verifier site alongside the loader and PMD
  sites.)
- **PE-2c remains pending independent code review and is NOT accepted by this
  correction.** This correction does not retroactively approve PE-2c, its V3
  implementation, or its C-16 audit; whether that audit meets §6.3 (semantic,
  not textual; not vacuous; not evadable by indirection) is a review question.
- No PE-2c file was modified, reverted or formatted by the turn that authored
  this document.

---

## 11. Closure discipline — explicitly not authorized by this document

This correction may not be used to add, and does not add:

1. any other version comparison, or any widening of V1, V2 or V3;
2. semver logic, version ranges, compatibility matrices, fallback or
   nearest-version matching;
3. runtime version probes (`pi --version` or any executable/version query);
4. Pi version pinning of any kind;
5. new policy fields or record schemas;
6. new evidence fields or record versions;
7. new security architecture;
8. new qualification requirements or acceptance rows (C-16 is reworded only to
   name three sites instead of two; C-11 is unchanged);
9. any implementation, test, data, roadmap, governance or `CLAUDE.md` change;
   any edit of PE-0, PE-1 or any other frozen or historical document or evidence;
10. acceptance of PE-2c, any live authorization, or any branch, commit, push or
    PR by any agent.

**Exactly one contradiction is corrected.**

---

## Status

```text
PE-1-C16                                   CANDIDATE / PENDING INDEPENDENT REVIEW
CONTRADICTION                              PE-1 §1 + C-16 ("exactly two"; "no third")
                                           vs §21 rule 4 + C-11 (mandatory declared-version
                                           equality in the post-hoc binding verifier)
RESOLUTION                                 count corrected to EXACTLY THREE; §21/C-11 kept
PERMITTED SITES                            V1 PE-2b loader integrity (§9.4)
                                           V2 PE-2a PMD delta enumeration (§8.3, §10.2)
                                           V3 PE-2c post-hoc binding verifier evidence integrity (§21)
FOURTH COMPARISON                          FORBIDDEN
V3 AUTHORITY                               NONE — may only make the post-hoc verifier reject a packet;
                                           never in the runtime authorization path
VERSION AUTHORITY                          NONE — no semver, no fallback, no nearest match,
                                           no runtime/model-reported version authority
SUPERSEDED                                 PE-1 R2 §1 "exactly two … no third" claim;
                                           PE-1 R2 §26.3 C-16 "two permitted sites of §1"
PRESERVED / MANDATORY                      PE-1 §21 (all rules), §26.3 C-11
OTHER PE-1 / PE-0 / PE-2a / PE-2b SEMANTICS UNCHANGED
NEW AUTHORITY                              NONE
PE-2c                                      NOT ACCEPTED — pending independent code review
NEXT LIVE AUTHORIZATION                    NOT AUTHORIZED
```
