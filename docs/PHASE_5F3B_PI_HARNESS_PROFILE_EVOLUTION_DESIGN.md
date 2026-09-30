# Phase 5F3B-PI-HARNESS-PROFILE-EVOLUTION — Pi Harness Profile Evolution and Adoption (Design)

```text
5F3B-PI-HARNESS-PROFILE-EVOLUTION-DESIGN     CANDIDATE (R3) / PENDING INDEPENDENT REVIEW
SOURCE READ AT                               90fda0bb6176977aeb3d629f089a96d31ede6200
AUTHORIZES                                   NOTHING (design only)
PE-0                                         CANDIDATE FOR ACCEPTANCE / PENDING INDEPENDENT REVIEW
CFG1-S1-A4                                   WITHDRAWN BEFORE CONSUMPTION / HISTORICAL ONLY / MUST NOT EXECUTE
HARNESS PROFILE POLICY REVISION DEFINED      HPP-1 (normative only once this design is accepted)
```

> **THIS DOCUMENT IS A DESIGN CANDIDATE. IT AUTHORIZES NO IMPLEMENTATION, NO
> LIVE EXECUTION, NO PROFILE APPROVAL, AND NO LIVE AUTHORIZATION.**
>
> **Disclosure of what the turns that authored this file did (exact).** They
> read repository documents and source inside `C:\dev\ai_dev_orchestrator` (the
> CFG1 design chain, FU1 R6 including OC-2, OC-3 AMEND1 including its accepted
> OC-3 archaeology summary, the A2/A3/A4 authorizations, the roadmap, the
> governance policy, the CFG1, AR1, AR2, O1 and qualification sources and
> tests, and — for R2 — the shipped `ai_dev_orchestrator.workspace.canonical`
> path primitives) and ran read-only `git`, `grep`, `sed`, `awk` and `wc`. They
> did **not** read anything outside the repository, did **not** inspect the installed Pi
> package, did **not** run Pi or Node, did **not** run `pi --version` or `npm`,
> did **not** contact any model or backend, did **not** read any credential or
> endpoint value, did **not** import any AIDO, CFG1, AR2 or qualification
> module, did **not** install, uninstall or downgrade anything, modified no file
> other than this one, and committed nothing.

---

## Revision history

| Rev | Change |
|---|---|
| R0 | Initial candidate. Profile identity = the 20-file `PI-SC1` seam table. |
| **R1** | Independent-review corrections. **R-J1 resolved** (explicit supersession of forward-looking 0.85.1 clauses permitted). **B1:** profile identity is now the bounded **Pi package payload** (every file under the Pi package root) plus a mechanically derived external-resolution exposure set; the 20-file table is demoted to a **seam fingerprint** used only for derivation-evidence reuse. C1/C2/C3 redefined; C2 proven mechanically from committed manifest bytes. **B2:** post-runtime payload re-observation (step L21A) is **mandatory** for any launched run; only `PROVEN_UNCHANGED` supports definite profile attribution. **B3:** declared version fields are parsed by the loader from committed manifest bytes bound to the payload inventory. **B4:** conclusions never transfer; evidence may be reused in a new explicit decision only when its declared premise scope is mechanically proven unchanged. Genesis becomes historical **seam evidence**, not a live-eligible profile. Migration PE-2 split into PE-2a/2b/2c. |
| **R2** | Independent review accepted the R1 architecture; three corrections only. **B5:** a closed dependency-map schema and one safe package-name parser (`@SCOPE/NAME` or `NAME`, conservative grammar) now stand between untrusted manifest keys and every path; paths are built only from validated components; `inventory_ref`/`manifest_bundle_ref` removed — policy files are located only at loader-owned, fingerprint-derived paths; evidence references are repo-relative and verified only by the offline evidence-reference verifier (§4.14). **B6:** the version-only review (EV) is replaced by **PMD — Permitted-Manifest-Delta consumer review**, covering every mechanically enumerated manifest delta (each `version`, each permitted internal dependency value, and the raw bytes of every differing manifest); `C2_MANIFEST_ONLY` approval and every reuse under `PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS` require a complete, clean PMD; a new approval class `C2_MANIFEST_DELTA_REACQUIRED` records the case where a delta matters; C2 structural comparison is made order-sensitive. **B7:** the top-level authority claim is replaced by a bounded statement; evidence language distinguishes **PROFILE-COVERED FACT** from **EXTERNAL RUNTIME RESIDUAL**; OC-2 is described as closed only for its package-payload portion. Nothing else is redesigned. |
| **R3** | Independent review accepted R2 (B1–B7); two narrow correctives only. **B8:** L21A no longer sits "immediately after L21"; the frozen closure execution order is `L21 → L22 → L23 → L24 → L21A → L25 → L26 → L27`, so broker shutdown and sensitive-material scrub keep priority over the payload re-walk; every B2 semantic is unchanged; a PE-2c ordering regression test is added. **B9:** C2 permits internal-dependency **value** changes only; key presence (and position) is immutable; the ambiguous "remove the permitted fields" wording is replaced by a structure-preserving value-slot projection; `INTERNAL_DEPENDENCY:<name>` PMD deltas exist only when the key is present on both sides; PE-2a classifier tests and a PE-2b loader test are added. Nothing else is redesigned. |

---

## 0. Scope and authority relationship

### 0.1 What this document is

The design of a **Pi-specific** mechanism by which AIDO:

1. stops requiring the installed Pi to equal one hard-coded historical release
   merely to proceed;
2. keeps the Pi version as **provenance**, never authority;
3. treats every newly observed Pi installation as an **unqualified candidate**
   that fails closed for ordinary live execution but remains eligible for a
   bounded qualification/onboarding path;
4. lets multiple **immutable approved Pi profiles** coexist;
5. adopts a newly approved profile **by committing reviewed data**, not by
   editing a version literal in production Python;
6. never rewrites historical qualification evidence.

**The bounded authority statement (B7) that governs everything here:**

> **A profile-aware live authorization may proceed only when the observed Pi
> package payload and its HPP-1 declared-dependency resolution boundary match an
> explicitly approved profile under the exact APS head bound by that
> authorization.**
>
> **HPP-1 profile authority is intentionally bounded. It does not claim complete
> identity of every byte Node may execute. The external-runtime residuals
> enumerated in §5.5 are outside profile authority and must never be represented
> in evidence as profile-covered or fully identified.**

This is the operator's governing aim — live execution uses only Pi bytes and
behavior whose authority was explicitly reviewed — made precise to what HPP-1
can mechanically establish. It weakens no runtime gate; it only forbids
overclaiming.

**Evidence language (mandatory in every record, console line and document
produced under HPP-1):**

```text
PROFILE-COVERED FACT
    a fact HPP-1 mechanically establishes: the resolved Pi package payload
    (every file and directory under the payload root) equalled approved profile X
    at the stated boundaries, and every declared-dependency exposure of X was
    absent from every ancestor node_modules at those boundaries

EXTERNAL RUNTIME RESIDUAL
    anything §5.5 enumerates (undeclared upward resolution, constructed-path
    loads, node.exe/built-ins/OS libraries, CommonJS global folders, external
    configuration/extension surfaces governed elsewhere, spawned processes):
    NOT identified by the profile, NOT observed by P or L21A, and never described
    as covered, pinned, proven unchanged, or part of "the Pi runtime identity"
```

No text may say a run used "the fully identified Pi runtime", that its Pi
"runtime identity is complete", or equivalent.

### 0.2 What this document is not

It is **not** a generic harness framework. It introduces no `AgentRuntime`, no
multi-harness interface, no harness plugin, no harness registry in the
roadmap's sense (a registry *of harnesses*), no Codex or DeepSeek Harness
integration, no cross-harness routing, and no capability negotiation. Every
object here is Pi-specific and consumed only by Pi-specific code. The roadmap's
deferred generic-harness work (`AIDO_RUNTIME_HARNESS_ROADMAP.md` §3.2) stays
deferred.

### 0.3 Subordination

This design is subordinate to, and **does not edit**:

- `AIDO_RUNTIME_HARNESS_ROADMAP.md` (§2 identity tuple, §2.1 `harness_version`,
  §2.2 policy revision, §2.3 qualification kinds, §3 Pi replaceability);
- `AIDO_PRODUCT_CLOSURE_AND_QUALIFICATION_POLICY.md`;
- the frozen CFG1 design chain (base design, L16-FU2 R2 + ERR1, FU1 R6, OC-3
  AMEND1, Y6 AMEND2, OC-4, P1 topology amendment);
- the A1/A2/A3/A4 authorizations and every historical evidence file.

Forward-looking 0.85.1 clauses are superseded only by the explicit PE-1
amendment (§3), never silently.

---

## 1. The operator policy change and the A4 disposition

### 1.1 The new product requirement

> AIDO must not permanently bind execution or qualification to a particular
> Pi/Harness version. Harness upgrades must be a supported first-class
> operation.

This changes the **adoption mechanism**. It does **not** change the evidence
integrity rule: a Harness change never silently carries an old PASS forward
(roadmap §2.1), and historical evidence states what was actually observed.

### 1.2 `CFG1-S1-A4` — recorded disposition

```text
CFG1-S1-A4
    content-reviewed                          yes (recorded outside files)
    post-commit reviewed and accepted         yes (recorded outside files)
    first authority consumption               NEVER OCCURRED
    status                                    WITHDRAWN BEFORE CONSUMPTION
                                              HISTORICAL ONLY
                                              MUST NOT EXECUTE
    reason                                    the operator rejected permanent
                                              operational version pinning
```

- The operator withdrew A4's execution authority **before** any call to
  `establish_stage_output_authority(stage_id="S1", stage_execution_id="CFG1-S1-A4")`;
  A4 §13's consumption boundary was never reached.
- `docs/PHASE_5F3B_HARNESS_CFG1_LIVE_S1_A4_AUTHORIZATION.md` and its commit
  `90fda0b…` are **preserved byte-for-byte** as historical evidence. Its
  in-file banner is not edited; acceptance and withdrawal are recorded outside
  that file (the withdrawal here).
- **The A4 launcher must not be produced, run, or consumed.** The literal
  `CFG1-S1-A4` is **burned**: it must never be used by any later authorization.
- **Mechanical backstops (not the authority).** A4's admission item A1 requires
  `HEAD == <A4_AUTH_COMMIT>`, which fails once any later commit exists; A4's G7
  accepts only the singleton 0.85.1 seam table. Neither is relied on (F-11).
- A4's E-class remedy text ("the operator may restore the approved Pi
  environment", A4 §10) is **historical**; no future authorization may carry it
  forward as the remedy for an unapproved profile (§9.8).

### 1.3 Fresh execution identity for the next live authorization

- The next profile-aware CFG1 Stage-1 authorization uses a **fresh**
  `stage_execution_id` literal satisfying the frozen grammar
  (`[A-Za-z0-9_-]{1,64}`, `type(...) is str`, `fullmatch`) that is **none of**
  `CFG1-S1-A1` … `CFG1-S1-A4` and has never been used or known to be used.
- By convention it would be `CFG1-S1-A5`; **this document reserves nothing**.
- Its admission must mechanically confirm `RESULTS_ROOT\CFG1-S1-A4` is
  **absent**, and must list A4 as `WITHDRAWN BEFORE CONSUMPTION / HISTORICAL ONLY`.
- It binds **no literal Pi version** (§9).

---

## 2. The central distinction

### 2.1 Four different things

```text
HARNESS VERSION     = provenance
                      descriptive text parsed from committed manifest bytes that
                      are hash-bound to the payload; recorded; grants nothing

PAYLOAD IDENTITY    = "which installed Pi payload is this?"
(profile_id)          the complete, bounded Pi package payload fingerprint plus
                      its external-resolution exposure set; the ONLY thing P
                      matches; the basis of live eligibility

SEAM FINGERPRINT    = "which AIDO derivation premises are byte-identical?"
                      the 20-file PI-SC1 table, derived FROM the payload; used
                      only to decide which derivation evidence may be reused;
                      NEVER identity, NEVER eligibility

APPROVAL POLICY     = authority to accept a profile
                      an immutable, reviewed approval record inside an
                      append-only approved-profile-set revision that a live
                      authorization binds by digest
```

### 2.2 The production question

```text
Is the currently observed Pi package payload (every file under the resolved Pi
package root, as AIDO itself just read it), together with the absence of its
declared external-resolution exposures, identical to a profile in the
live-eligible set of the sealed Harness-profile policy snapshot (HPP-1,
consumer contract CFG1-CC1) whose head digest this execution's live
authorization bound?
```

It is **never again**: *Is installed Pi exactly version 0.85.1?* — and it is
also **never**: *Do the 20 seam files match?*

### 2.3 Two symmetric prohibitions

- **A literal version string must not itself grant authority.** No code path
  compares a version string to decide admission, selection, matching,
  eligibility, or launch.
- **Removing version provenance is prohibited.** Every profile carries its
  declared versions, mechanically derived from bound bytes (§4.5); every
  profile-aware run record carries the matched profile's id and declared version
  (§10.3); historical records keep what they recorded.

---

## 3. Frozen-invariant compatibility — R-J1 RESOLVED

**R-J1 disposition (independent review): RESOLVED — explicit supersession
permitted.** The literal `Pi == 0.85.1` requirement is not an immutable security
invariant; it is a forward-looking operational consequence of the old
singleton-profile architecture, and the operator changed that product policy.
PE-1 may explicitly supersede the forward-looking clauses below, provided
historical frozen documents and evidence remain immutable. This is not reopened.

### 3.1 Security invariants — preserved

| Frozen invariant | Source | Preserved how |
|---|---|---|
| P executes nothing; no `--version` probe; first Node/Pi/JS execution is L14 `launch()` | AMEND1 AMD-1/AMD-6 | P gains only no-follow reads, hashing and in-memory membership (§7.2). No executing leaf. |
| P2 is complete, never a subset | R6 §5 P2 | Strengthened: P2 now observes the **complete package payload**, a strict superset of the 20 seams (§5, §7.2). |
| P1: first admissible `PATH` candidate is authoritative | P1 topology amendment | Unchanged; never searches onward for a matching install (S-21). |
| Gate is waste avoidance, returns nothing reusable | R6 §7.1, AMEND1 §12 | Unchanged (§7.4). |
| L1 re-proves from scratch | R6, AMEND1 | Unchanged (§7.3). |
| L14 launch-nearest re-proof | AMEND1 AMD-6 | Strengthened: complete payload re-walk, equality with **L1's** profile, exposure absence, then I_r, I_n (§7.5). |
| Static pass is provenance, never an observed/reported version | AMEND1 §7.1, §7.3 | Preserved: P never parses a version; declared versions live in loader-verified policy data (§4.5). |
| Authorization supplies exactly one runtime value (`stage_execution_id`) | CFG1 §14.1 | Preserved: APS bound via committed tree + launcher gate G6A (§9.4). |
| v1/v2 meanings immutable | AMEND1 §15, R6 §10 | Preserved; profile awareness goes to v3 (§10). |
| Mismatch refuses before any credential read | CFG1 §14.2 | Preserved; mismatch routes to onboarding (§6). |
| Closure always runs, step-local containment | OC-4 | New step L21A obeys it and executes after L24, before L25 (§7.6); OC-4 is otherwise not reopened. |

### 3.2 Forward-looking clauses to be explicitly superseded in PE-1

| Clause | Substance |
|---|---|
| CFG1 base design §14.1 item 2 | LIVE-S1 "must authorize … Pi 0.85.1 with the §14.2 digests" |
| CFG1 base design §14.2 | the singleton seam table "installed Pi 0.85.1" |
| FU1 R6 §2 | "Pi remains pinned to 0.85.1 … No entry is … repinned" |
| FU1 R6 §17 item 6 | "Operator restores the approved Pi 0.85.1 environment" |
| OC-3 AMEND1 banner, §7.4, §19 item 5 | pin wording; `PINNED_PI_VERSION` as design literal; "Operator restores … 0.85.1" |

The historical authorizations (LIVE-S1, A2, A3, A4) need no amendment: they
never authorize anything again. Until PE-1 is accepted, **no CFG1 live
authorization may be created**.

### 3.3 OC-2 after this design

FU1 R6 OC-2 (restated by AMEND1 §14) records that the frozen identity is the
20-file seam set while "everything else under the package root (and Node
itself) is unpinned yet executes at … L14", and names "a separate re-derivation
phase if a whole-package manifest and/or Node pin is wanted". This design is
that whole-package design for profile-aware runs, and **only** that: once
implemented, the **package-payload portion** of OC-2 (bytes under the Pi package
root) is covered by §5. OC-2 is **not** closed beyond that portion: the **Node**
part and every external-runtime residual of §5.5 remain open, stated, and
outside profile authority (B7).

---

## 4. Object model

"Code" = a reviewed constant/function in the CFG1 package; "data" = a canonical
JSON file inside the audited CFG1 source root (`experiments\pi_harness_cfg1`).
Exact module/file names are chosen by PE-2 within these constraints.

### 4.1 Payload contract — `PI-PC1` (code)

Defines, with no digest and no version:

- **the payload root:** the Pi package root exactly as P1 resolves it
  (`node_modules/@earendil-works/pi-coding-agent`, anchored by `pi.cmd`, the two
  AR2 layouts), and `dist/cli.js` as the launch target (must be a payload file);
- **the payload walk rules** (§5.2): what is enumerated, what refuses, bounds;
- **the permitted manifest set and fields** for class C2 (§8.2);
- **the declared-dependency containment rule and the exposure rule** (§5.3);
- the seam contract it carries: `PI-SC1`.

It changes only on a layout/scope change (class C5): a design amendment and
code change by definition.

### 4.2 Seam contract — `PI-SC1` (code)

The 20 relative paths of today's `preflight.PINNED_PI_SEAM_DIGESTS`, with its
cardinality assertion (the current `PINNED_SEAM_ENTRY_COUNT = 20`). It is a
**subset selector over the payload inventory**, nothing more. It identifies
which files AIDO's reviewed derivations cite.

### 4.3 Consumer contract — `CFG1-CC1` (code)

Names the AIDO-side derivations/code that consume Pi behavior (CFG1 §1.2/§2
compat semantics → `COMPAT_DETECTION_SUBSTRINGS`; FU1/FU2 `get_state`,
`jsonl.js`, `agent-loop.js` facts; arm derivations; generated-config
acceptance). Approvals are per consumer contract. A behavior change that forces
AIDO code to change (C4) moves the code to `CFG1-CC2`; every profile then needs
an approval for `CFG1-CC2` to be eligible under that code.

### 4.4 Payload inventory (data, immutable, one file per profile)

```text
record_kind     "aido-pi-payload-inventory.v1"
payload_contract "PI-PC1"
entries         sorted by relative path; each exactly one of
                  { "path": <rel>, "kind": "dir" }
                  { "path": <rel>, "kind": "file", "size": <int>, "sha256": <hex> }
```

`payload_fingerprint = SHA-256( b"aido.pi-payload.v1\x00" || canonical bytes of this record )`.

### 4.5 Manifest bundle (data, immutable, one file per profile) — the B3 binding

```text
record_kind     "aido-pi-manifest-bundle.v1"
payload_fingerprint   <hex> — the inventory it is bound to
manifests       { <rel path of EVERY inventory file whose basename is
                   "package.json">: <the file's exact bytes, base64> }
```

- Every manifest's bytes are size-bounded and **must hash to the inventory
  entry's `sha256`** for that path; the key set must equal exactly the set of
  inventory files named `package.json`.
- From these **bound bytes** the loader deterministically parses (strict UTF-8,
  no BOM, duplicate-key refusal, no `NaN`/`Infinity`, bounded depth/size):
  - the **declared projection** — `name` and `version` of the root,
    `node_modules/@earendil-works/pi-ai` and
    `node_modules/@earendil-works/pi-agent-core` manifests, each required to be
    an exact `str` of bounded length and printable-ASCII grammar;
  - the **declared-dependency containment result and exposure set** (§5.3),
    under the closed dependency-map schema and package-name parser of §5.3.1 —
    no dependency key reaches any path, in memory or on disk, before it parses.
- Any malformed, duplicate-key, missing, or non-string required field **fails
  the whole chain closed**. A real Pi release whose manifests cannot be parsed
  strictly therefore cannot be approved under HPP-1 (a policy amendment would be
  required), rather than being approved with unverified provenance.

This is the honest B3 solution: declared version text is **mechanically bound**
to bytes whose digests are in the payload inventory. It is still **only
descriptive**: no decision reads it.

### 4.6 Pi profile record (data, immutable)

```text
record_kind            "aido-pi-profile.v1"
payload_contract       "PI-PC1"
payload_fingerprint    <hex>   — must equal the committed inventory's fingerprint
resolution_exposures   sorted list of package names (possibly empty) — must equal
                       the set the loader recomputes from the manifest bundle
profile_id             SHA-256( b"aido.pi-profile.v1\x00" || canonical_json({
                          "payload_contract": "PI-PC1",
                          "payload_fingerprint": ...,
                          "resolution_exposures": [...] }) )
seam_contract          "PI-SC1"
seam_digests           the 20 PI-SC1 entries — must equal the inventory's digests
                       for those paths (all 20 must be present as files)
seam_fingerprint       SHA-256( b"aido.pi-seam.v1\x00" || canonical_json({
                          "seam_contract": "PI-SC1", "seam_digests": {...} }) )
declared               { package_name, package_version, pi_ai_version,
                         pi_agent_core_version } — must equal the loader's
                       projection from the manifest bundle
discovery              { aido_commit, discovery_tool_revision }
```

R2 **removes** R1's `inventory_ref` and `manifest_bundle_ref`. They were
redundant and path-bearing. The inventory and manifest bundle of a profile are
located **only** at the loader-owned, fingerprint-derived paths of §4.10; no
profile field can name a file to open.

**Everything derivable is recomputed; nothing derivable is trusted.** The loader
recomputes `payload_fingerprint`, `seam_digests`, `seam_fingerprint`,
`declared`, `resolution_exposures` and `profile_id` from committed bytes and
refuses any disagreement. No boolean appears in a profile record.

**Relation, exactly:**

```text
payload inventory ──(hash)──► payload_fingerprint ─┐
        │                                          ├─(hash)─► profile_id   (identity, eligibility)
        ├──(manifest bundle, parse)─► exposures ───┘
        ├──(manifest bundle, parse)─► declared versions      (provenance only)
        └──(select PI-SC1 paths)─► seam_digests ─(hash)─► seam_fingerprint (evidence reuse only)
```

`profile_id` determines `seam_fingerprint` (a function of the inventory); the
converse is false: many profiles may share one seam fingerprint.

### 4.7 Seam evidence record (data, immutable)

```text
record_kind        "aido-pi-seam-evidence.v1"
seam_contract      "PI-SC1"
seam_digests       the 20 entries
seam_fingerprint   recomputed
evidence           list of { repo_path, sha256 } — line-cited derivation documents
evidence_id        SHA-256 over the canonical record without this field
```

Holds reusable **derivation** evidence (E1) keyed by seam fingerprint. It is
**never** eligible, never matched by P, and never a profile.

### 4.8 Profile approval record (data, immutable)

```text
record_kind            "aido-pi-profile-approval.v1"
profile_id             must name a profile in the same set revision
consumer_contract      "CFG1-CC1"
policy_revision        "HPP-1"
qualification_class    "C2_MANIFEST_ONLY" | "C2_MANIFEST_DELTA_REACQUIRED"
                       | "C3_SEAM_EQUAL" | "C3_SEAM_CHANGED"
                       | "C4_CONTRACT_REVISED" | "CC_REAPPROVAL"
                       (conservativeness order, least → most, as listed)
reused_evidence        list of { evidence_kind, source_id, premise_scope, refs } (§8.5)
pmd                    the Permitted-Manifest-Delta consumer review (§8.6) —
                       REQUIRED whenever the mechanical floor is C2, and whenever
                       any reused_evidence entry uses
                       PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS; otherwise absent
evidence               non-empty list of { repo_path, sha256 } — new evidence
acceptance_reference   bounded text naming the external acceptance record (F-5)
approval_id            SHA-256 over the canonical record without this field
```

- One approval per `(profile_id, consumer_contract)` per lineage.
- **Class floor verification:** the loader recomputes the mechanical floor
  (§8.2) against the profiles and seam evidence present in the revision and
  refuses an approval whose class is **less conservative** than the floor.
- **Premise verification:** every `reused_evidence` entry's premise scope is
  mechanically checked (§8.5); a failed check refuses the chain.
- **PMD verification (§8.6):** the loader recomputes the manifest delta list
  and refuses a `pmd` that omits a delta, adds one, or is structurally
  inconsistent with the approval class or the reuse entries.
- An approval contains no digest table; it names a profile by id only.

### 4.9 Retirement record (data, immutable)

```text
record_kind      "aido-pi-profile-retirement.v1"
profile_id       must name an approved profile in the same lineage
consumer_contract "CFG1-CC1"
reason_code      closed enum: "SECURITY_ADVISORY" | "DERIVATION_INVALIDATED"
                 | "OPERATOR_WITHDRAWN" | "SUPERSEDED_BY_POLICY"
evidence         list of { repo_path, sha256 }
retirement_id    SHA-256 over the canonical record without this field
```

Removes eligibility from the revision that adds it onward; deletes nothing;
terminal under HPP-1.

### 4.10 Approved-profile-set revision — "APS" (data, append-only chain)

```text
record_kind                 "aido-pi-approved-profile-set.v1"
consumer_contract           "CFG1-CC1"
policy_revision             "HPP-1"
payload_contract            "PI-PC1"
seam_contract               "PI-SC1"
revision                    N (1, 2, 3, … contiguous)
previous_revision_sha256    null for N = 1; else SHA-256 of revision N-1's bytes
seam_evidence               list of seam evidence records
profiles                    list of profile records
approvals                   list of approval records
retirements                 list of retirement records
```

- **Loader-owned locations (B5).** One policy directory `<POLICY_DIR>`, fixed
  inside the CFG1 package and derived from the loading module's own `__file__`
  (never from an argument, environment variable, the current directory, or any
  record field). Exactly three fixed subdirectories and filename grammars:

  ```text
  <POLICY_DIR>\aps\aps.r<NNNN>.json                  NNNN = 4 decimal digits, 0001…
  <POLICY_DIR>\inventories\<payload_fingerprint>.json
  <POLICY_DIR>\manifest_bundles\<payload_fingerprint>.json
  ```

  A filename is formed only **after** its fingerprint has been validated as
  exactly 64 lowercase hex characters (`type(x) is str`, `fullmatch`), and only
  by concatenating that validated string with the fixed suffix. Every file is
  read no-follow through one handle. Every file present in the three
  directories must be referenced by the chain and every referenced file must be
  present; anything else (stray, extra, unreferenced, non-matching name,
  reparse point) fails the chain closed. **No profile-controlled or
  record-controlled filesystem path is ever opened.**
- **Append-only, mechanically checked:** revision N contains every record of
  N-1 canonically byte-identical, plus additions only. A removal, edit,
  reorder, gap, stray file, unreferenced or missing inventory/manifest-bundle
  file, or `previous_revision_sha256` mismatch fails the **whole** chain closed.
  (Evidence references are never opened by the loader; see §4.14.)
- No duplicate `profile_id`, no duplicate `payload_fingerprint`, no duplicate
  `evidence_id`.
- **Genesis (revision 1)** contains exactly **one seam evidence record** — the
  historical 0.85.1 `PI-SC1` table, byte-for-byte today's
  `PINNED_PI_SEAM_DIGESTS`, citing CFG1 §1.2/§2/§14.2, L16-FU2 §16 and the
  accepted OC-3 archaeology — and **zero profiles**. The historical 0.85.1
  approval was only ever an approval of seam bytes (OC-2), and no 0.85.1
  payload inventory exists in AIDO's evidence, so under HPP-1 it **cannot** be
  expressed as a profile. Its derivations remain reusable (E1) for any candidate
  with an equal or partially equal seam table. The genesis eligible set is
  therefore **empty** — correct, since nothing has been qualified as a payload.
- **Head digest** `H` = SHA-256 of the highest revision's bytes.
- **Live-eligible set**, computed, never stored:

  ```text
  eligible(CC) = { a.profile_id | a ∈ approvals, a.consumer_contract == CC,
                   a.policy_revision == "HPP-1" }
                 − { r.profile_id | r ∈ retirements, r.consumer_contract == CC }
  ```

  Exact-`str` `frozenset` membership; no truthiness, no default.

### 4.11 Sealed policy snapshot (in memory)

Loaded **once per process at import** of the profile-policy module, strictly
validated (§4.13), sealed into an immutable object constructible only by the
loader (module-private key). No reload, setter, path parameter, or parameter of
`run_cfg1_stage`/gate/P/L14/L21A accepts a snapshot. A malformed chain makes the
module fail to import → launcher G4 refuses. The snapshot is **policy, not
observation**.

### 4.12 Candidate profile record (data, never authority)

Discovery output (§12): the complete inventory and manifest bundle (or the exact
unobservable relative paths and the reason), the would-be `profile_id`, seam
fingerprint, declared projection, exposure set and upward-absence observation,
and the mechanical floor class against the current APS. A different
`record_kind`, a separate directory the loader never reads; it becomes authority
only when its profile/inventory/bundle are copied into a new APS revision with a
separately reviewed approval.

### 4.13 Strict parsing rules (all data)

UTF-8, no BOM; size bounds per file; no-follow single-handle reads;
duplicate-key refusal; `NaN`/`Infinity` refusal; **canonical-bytes equality**
(sorted keys, fixed separators, ASCII-escaped — one admissible encoding);
closed key sets per `record_kind`; exact types (`type(x) is …`, never
`isinstance` with `bool`-subclassing ints); 64-lowercase-hex digests;
relative-path grammar (forward slashes, no empty/`.`/`..` segment, no drive,
no leading slash, no control character, case-fold-unique); closed enums; every
id recomputed.

### 4.14 Path-bearing policy references (B5)

| Reference | Form | Who opens it | Rule |
|---|---|---|---|
| APS revision, inventory, manifest bundle | none stored — derived | runtime loader | only the loader-owned fingerprint-derived paths of §4.10 |
| Payload inventory entry paths | relative path strings (§4.13 grammar) | **nobody** — in-memory keys only | P walks the real directory tree; it never opens a path read from an inventory |
| Manifest-bundle keys | inventory relative paths | **nobody** | keys must equal inventory entries named `package.json` |
| Dependency names / exposures | package names | P2X and discovery, **only as validated components** | §5.3.1 parser first, always |
| `evidence[*].repo_path`, `reused_evidence[*].refs[*].repo_path`, seam evidence `evidence[*].repo_path` | repo-relative reference | **only** the offline evidence-reference verifier; **never** the runtime loader, P, L1, L14, L21A or the gate | below |

**Evidence-reference verifier.** No shipped function currently does exactly
this job. The closest existing primitive is
`ai_dev_orchestrator.workspace.canonical.canonicalize_existing_path_under_workspace`
(lexical/colon/device-form refusal before touching disk, `allow_symlinks=False`
refusing any link or reparse component, and containment under a root); its own
docstring notes that nothing shipped calls it yet. PE-2b composes the
evidence-reference verifier from it and nothing broader:

1. the `repo_path` must satisfy the §4.13 relative-path grammar (string checks
   only, before any filesystem access);
2. `canonicalize_existing_path_under_workspace(<checkout root>, repo_path)` with
   `allow_symlinks=False`, where `<checkout root>` is the checkout derived from
   the verifying module's own location (as `pi_identity._GENUINE_CHECKOUT_ROOT`
   is today), never from an argument;
3. the result must be a regular file; its SHA-256 must equal the reference.

Tracked state is verified by the reviewer/operator approval procedure with
read-only Git against the commit being reviewed; per CLAUDE.md, the verifier's
own Git-exercising unit tests use synthetic repositories under `tmp_path`, and
the pytest check over the real checkout's committed APS performs steps 1–3
without Git. Eligibility never depends on opening an evidence reference: the
loader validates reference **syntax** only; the digest check is an offline
verification the approval and authorization reviews rely on.

---

## 5. Runtime payload scope — what can be identified statically

### 5.1 What Pi-controlled JavaScript can load from, under the accepted launch topology

The accepted launch is Node-direct: `node.exe <root>\dist\cli.js …` with the
L12 positive-allowlist environment, in which `NODE_OPTIONS` and `NODE_PATH` are
**withheld** (AMEND1 §9; FU1 R6 §5). Consequences, answered statically:

| Question | Answer |
|---|---|
| Which filesystem roots can Pi-controlled JS load from? | (a) **the Pi package root subtree**, including its nested `node_modules`; (b) **ancestor `node_modules` directories above the root**, via Node's upward bare-specifier lookup, whenever a specifier is not satisfied inside the root; (c) for CommonJS only, Node's global folders (`<node.exe dir>\..\lib\node` on Windows, and `.node_modules`/`.node_libraries` under the home directory if the environment names one); (d) any path Pi code constructs itself (relative `../` escapes, absolute paths, `file:` URLs, `createRequire` at arbitrary locations, `fs` read + `vm`/`eval`/`Function`, WASM by path); (e) Node built-ins inside `node.exe`. |
| Are all runtime dependencies nested under the Pi root in the architecture AIDO relies on? | CFG1 §1.2 observed, for 0.85.1 only, that `pi-ai` resolves **nested** and no hoisted global `pi-ai` exists. That is one historical observation, not a guarantee for any other release. R1 turns it into a **per-profile mechanical property** for **declared** dependencies (§5.3) and states the rest as residual. |
| Can globally hoisted/sibling `node_modules` packages participate? | Yes, for any bare specifier not satisfied inside the root: Node then searches `<ancestor>\node_modules` for every ancestor above the root whose basename is not `node_modules` — including the global npm directory holding **other projects' global packages**. |
| Can package `exports` reach outside the root? | Not by itself: Node rejects `exports`/`imports` targets that are not `./`-relative or that contain `..`/`node_modules` segments. But an `imports` entry may map to a **bare specifier**, which then resolves by normal lookup — covered only if declared (§5.3), else residual. |
| Can dynamic imports / runtime resolution reach outside? | Yes: computed `import()`/`require()` specifiers and constructed paths cannot be enumerated without a JavaScript analysis AIDO does not have. Residual R-EXT-1/R-EXT-2. |
| Which roots can be identified without executing Node/Pi? | The payload root (P1, lexical, no-follow); the lexical ancestor chain above it and each `<ancestor>\node_modules`; `node.exe`'s directory. The home directory is **not** identified (P reads only `PATH`). |

**Conclusion:** a complete execution closure **cannot** be derived statically
without executing or fully analyzing Pi's JavaScript. HPP-1 therefore defines the
strongest bounded identity — the **Pi package payload** plus a **mechanically
checked declared-dependency containment and exposure-absence property** — and
never calls it a complete runtime identity.

### 5.2 The payload (exact set the fingerprint covers)

Every entry under the resolved payload root, recursively, including all nested
`node_modules` trees, **of every file type** (`.js`, `.mjs`, `.cjs`, `.json`,
`.node` native addons, `.wasm`, data, docs, anything):

- enumerated no-follow; each directory recorded as a `dir` entry (so added
  empty directories and removed trees change the fingerprint); each regular
  file recorded with exact size and SHA-256 through one handle;
- **refused** (payload unobservable → `PI_PAYLOAD_UNPROVEN`): any reparse point
  (symlink, junction, any `FILE_ATTRIBUTE_REPARSE_POINT`) anywhere; any
  non-regular, non-directory entry; an unreadable entry; a name failing the
  relative-path grammar; a case-fold collision; exceeding the entry-count,
  per-file-size or total-size bounds fixed in PE-1 (bounds are refusal limits,
  never truncation);
- the 20 `PI-SC1` paths must be present as files for a profile to be
  **approvable**; at run time P matches the payload fingerprint only.

Reparse refusal also guarantees Node's realpath resolution cannot redirect a
payload path outside the root.

### 5.3 Declared-dependency containment and the exposure set

Computed by the loader (and by discovery) from the inventory plus the manifest
bundle, never at run time from Pi bytes. Every step below operates on
**validated package-name components** produced by §5.3.1, never on a raw key.

1. **Package roots in the payload:** the payload root, and every directory
   `…/node_modules/<name>` or `…/node_modules/@<scope>/<name>` in the inventory
   that holds a `package.json` (the `<name>`/`@<scope>` directory names are
   themselves checked by the §5.3.1 component grammar; a package root whose
   directory name fails it makes the payload C5 under HPP-1).
2. For each package root `K`, its manifest's dependency maps are validated by
   the §5.3.1 schema, and each key is parsed to components `C`. For each `C`,
   apply Node's upward lookup from `K`, **restricted to the inventory and
   expressed as in-memory relative keys**: `K + "/node_modules/" + "/".join(C)`,
   then each ancestor directory of `K` up to and including the payload root
   (skipping directories named `node_modules`) `+ "/node_modules/" + "/".join(C)`.
   If some candidate key is an inventory directory holding a `package.json`, the
   name is **contained**; otherwise it is an **exposure**.
3. `resolution_exposures` = the sorted set of exposure names, each stored in its
   canonical parsed-and-re-joined form (`NAME` or `@SCOPE/NAME`). It is part of
   the `profile_id` preimage. The loader re-parses every stored exposure with
   the same parser and refuses the chain if any fails or does not round-trip
   byte-identically.

**Exposure absence, checked at run time (P2X, §7.2):** for each exposure, its
components `C` are obtained **from the parser**, and for each ancestor `A` of the
payload root whose basename is not `node_modules`, the one path observed is
`ntpath.join(A, "node_modules", *C)` — built only from `A` (a lexical ancestor
of the already-proven payload root) and validated components. Each lexical
component from `A\node_modules` down to the final component is observed
no-follow: every intermediate component must be a plain directory or missing,
and the final entry must be **missing**; a present entry or any reparse point
refuses `PI_EXTERNAL_RESOLUTION_EXPOSED`. This closes the concrete
hoisted/sibling case **for declared dependencies**: if a declared dependency is
contained, Node finds the nested copy before any ancestor, so a sibling package
is irrelevant to resolution; if it is not contained, the sibling location is
proven empty.

#### 5.3.1 Dependency-map schema and the one package-name parser (B5)

Dependency keys come from **untrusted Pi package bytes**. They become path
components only through this contract, applied identically by discovery and by
the committed-manifest loader, and **before any path is formed, in memory or on
disk**.

**Dependency-map schema** (per package-root manifest, for each of
`dependencies`, `optionalDependencies`, `peerDependencies`):

| Element | Rule |
|---|---|
| the field | **absent**, or `type(value) is dict` (the strict parser's own `dict`, with duplicate keys already refused). `null`, list, string, number, `bool`, or any other type → refuse. No subclass, no truthiness repair, no coercion, no "empty means absent". |
| map size | at most 4096 keys (bound frozen in PE-1) |
| every key | `type(key) is str`; length 1…214; then the package-name parser below |
| every value | `type(value) is str`; length 0…1024. Values are **never** interpreted, resolved, or used to form a path; they are only compared (C2) and enumerated (PMD). No other JSON type is supported: HPP-1 has no reason to accept one, so list/int/bool/null/object values refuse. |

**Package-name parser** `parse_package_name(key) -> tuple[str] | tuple[str, str]`:

```text
precondition   type(key) is str                      (a str subclass refuses)
whole string   1 ≤ len ≤ 214; every character in [a-z0-9._@/-]
               (this alone refuses '\', ':', NUL, every control character,
               whitespace, uppercase, '%', and every non-ASCII character)
form           unscoped:  exactly zero '/' and no '@'           → (NAME,)
               scoped:    key[0] == '@', exactly one '/', no other '@'
                                                                → ("@" + SCOPE, NAME)
               anything else (two or more '/', '@' elsewhere, '/' without '@',
               '@' without '/')                                 → refuse
component      SCOPE and NAME each:
               - non-empty                      ('@/x', '@scope/', '' refuse)
               - matches [a-z0-9][a-z0-9._-]*   (cannot start with '.', '_' or '-';
                                                 so '.', '..' and '.x' refuse)
               - does not end with '.'          (Windows trailing-dot stripping
                                                 could otherwise normalize a name
                                                 into a different one)
               - is not "node_modules"
               - its stem before the first '.' is not a Windows reserved device
                 name (con, prn, aux, nul, com0-9, lpt0-9), case-insensitively
result         the exact components above; the canonical text form is
               NAME or "@" + SCOPE + "/" + NAME, which must equal the input
```

What the parser deliberately does **not** do: it never calls `os.path.normpath`,
`ntpath.normpath`, `realpath`, `abspath`, npm, Node or any package-manager
validation; it never strips, lowercases, or percent-decodes; it never "fixes" a
name. Because the character set excludes `\` and `:`, and components cannot be
empty, `.`, `..`, start with `.`, or end with `.`, no accepted name can express a
drive, an absolute path, a UNC or device path, a separator other than the single
scoped `/`, or a component that Windows would normalize to `.` or `..`.

**Path construction** uses only `ntpath.join(<proven ancestor>, "node_modules",
*components)` (on disk) or `"/".join((..., "node_modules", *components))` (in
memory). The raw key is never joined, formatted into, or concatenated with a
path.

**Conservative by design.** The grammar is a strict subset of what npm accepts
(no uppercase legacy names, no names starting with `_`/`-`/`.`, lowercase ASCII
only). A legitimate current or future dependency name outside it makes the
candidate **C5 under HPP-1** (discovery reports `PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR`
with the manifest's relative path, never the raw key text in any console line)
and requires an explicit HPP policy amendment; the grammar is never widened
automatically (F-15).

### 5.4 What this closes (B1)

Arbitrary changes to Pi-controlled files anywhere under the payload root —
`dist/cli/setup.js`, any other non-seam JS, any nested dependency file, any
manifest byte, any added or removed file or directory — change
`payload_fingerprint`, hence `profile_id`. **They can never remain C1 because
the 20 seams are unchanged.**

### 5.5 Residual external-dependency boundary (stated precisely, not closed)

| Id | Residual |
|---|---|
| R-EXT-1 | **Undeclared** bare specifiers (phantom dependencies, `imports`-to-bare mappings not declared, computed specifiers) that are not satisfied inside the payload resolve upward into ancestor `node_modules` without an exposure check. |
| R-EXT-2 | Loads by constructed path outside the root (relative escape, absolute path, `file:` URL, `createRequire` elsewhere, `fs`+`vm`/`eval`/`Function`, WASM by path). |
| R-EXT-3 | `node.exe`, its built-in modules, and OS libraries are not in the payload (F-4). |
| R-EXT-4 | CommonJS global folders (`<node dir>\..\lib\node`, home-directory `.node_modules`/`.node_libraries`) are not checked; the home directory is not identified. |
| R-EXT-5 | Pi configuration, extension, skill and prompt discovery outside the payload (agent directory, project `.pi/`) is **not** Pi payload; it is governed by CFG1's launch-configuration isolation and the L15 H1 extension-identity check (AIDO-owned bytes). |
| R-EXT-6 | Processes Pi spawns (e.g. `git`) are runtime behavior, not payload. |

The identity claim is therefore exactly the **PROFILE-COVERED FACT** of §0.1:
**"the Pi package payload and its declared-dependency resolution boundary equal
an approved profile"**. Every row above is an **EXTERNAL RUNTIME RESIDUAL**: it is
outside profile authority, it is not observed by P, L14 or L21A, and no evidence
may call it covered, pinned, unchanged or identified. The claim is never "the Pi
runtime is fully identified".

---

## 6. Lifecycle

### 6.1 States

```text
NEW / CHANGED PI INSTALLATION        (an external fact; AIDO is not told)
        │   next AIDO admission or explicit discovery
        ▼
STATIC DISCOVERY                     P0, P1, complete payload walk (twice, equal),
        │                            exposure computation + absence, P2R; executes nothing
        ▼
UNQUALIFIED PI PROFILE CANDIDATE     candidate record; floor class; ordinary live REFUSED
        ▼
PROFILE QUALIFICATION                evidence per class (§8); candidate code executes
        │                            only under a separate explicit authorization
        ▼
INDEPENDENT ACCEPTANCE               reviewed approval; no self-approval path
        ▼
APPROVED PI PROFILE                  profile + inventory + bundle + approval in APS N+1
        ▼
ADOPTION / LIVE ELIGIBILITY          fresh authorization binds commit + H(N+1)
```

Side exits: **REJECTED** (never enters an APS); **RETIRED**; **C4/C5** (design
amendment and code first).

### 6.2 What an unknown profile does during an ordinary live run

| Where | Behavior |
|---|---|
| Pre-consumption gate | `PI_PROFILE_UNAPPROVED`, `PI_PAYLOAD_UNPROVEN` or `PI_EXTERNAL_RESOLUTION_EXPOSED`. **Not consumed.** Nothing executes. |
| Launcher | E-class refusal; the documented remedy is **profile onboarding** (§12). No AIDO text instructs, requires or automates reinstalling an older Pi. |
| L1 (installation changed after the gate) | Same typed refusal → `(L1, OFFLINE_PREFLIGHT_FAILED)` with the P code; consumed (existing semantics); no credential read. |
| L14 | Re-observed payload ≠ L1's → `RUNTIME_LAUNCH_FAILED`; no `launch()`. |

Never matched to "the nearest" profile, never admitted with a warning, never
auto-queued for approval.

---

## 7. The static proof P and the runtime boundaries

### 7.1 Three boundaries plus closure

```text
pre-consumption observation != L1 authority != L14 launch-nearest authority
                                                       != L21A post-runtime attribution
```

Each re-observes the **untrusted installation** from scratch; they share only
the sealed **policy** snapshot.

### 7.2 P, revised

```text
P0    read exactly one ambient name, PATH, by name                        (unchanged)
P1    resolve node.exe and the Pi package root over the ADMISSIBLE PATH
      entries only; capture I_n and I_r                                    (unchanged)
P2    OBSERVE the complete payload (§5.2), no-follow, never cached
        not completely observable             → PI_PAYLOAD_UNPROVEN
      → payload_fingerprint pf
P2M   MATCH (in memory): the eligible profile whose payload_fingerprint == pf
      (at most one: the loader refused duplicates; >1 raises, never chooses)
        none                                  → PI_PROFILE_UNAPPROVED
P2X   EXPOSURE ABSENCE for the matched profile's resolution_exposures (§5.3)
        present or unobservable               → PI_EXTERNAL_RESOLUTION_EXPOSED
P2R   re-prove I_r, then I_n                                               (unchanged)
        drift                                 → PI_IDENTITY_DRIFTED_DURING_PROOF
→     PiProofResult; a pass carries Cfg1PiIdentity + matched_profile_id
```

- **Observe-then-match.** The path set is the whole payload, fixed by the walk
  rules before the first read; nothing Pi supplies selects which table is
  checked. Matching is by the fingerprint of the **complete** payload.
- P reads bytes only to hash them; it **never parses** Pi-authored content (the
  exposure names it checks come from the sealed, loader-verified policy data).
- P2 computes the payload fingerprint only; the seam fingerprint is not used at
  run time at all.
- Failure precedence is the fixed function order: resolution → payload
  observation → membership → exposure → identity drift.

### 7.3 L1

Same `prove_pi_identity` function object, same genuine leaves, from scratch;
P's family committed atomically plus `pi_profile_id` on a pass. **Stage profile
consistency:** the first ordinal's L1 match fixes the stage profile id in the
runner-local stage ledger; every later ordinal must re-prove from scratch **and**
equal it, else `PI_PROFILE_CHANGED_WITHIN_STAGE` before any credential read.
This is a narrowing constraint, never an authority.

### 7.4 Pre-consumption gate

Same P, same leaves, same sealed snapshot; reads only `PATH`; executes and
writes nothing; returns exactly one closed code:

```text
{ PI_IDENTITY_PROVEN, PI_IDENTITY_GATE_UNEXPECTED_FAILURE, PI_RESOLUTION_FAILED,
  PI_PAYLOAD_UNPROVEN, PI_PROFILE_UNAPPROVED, PI_EXTERNAL_RESOLUTION_EXPOSED,
  PI_IDENTITY_DRIFTED_DURING_PROOF }
```

Nothing reusable is returned.

### 7.5 L14

`reprove_pi_identity_for_launch(identity)`, fixed order: (1) complete uncached
payload re-walk → `pf'`; (2) `pf' == ` the payload fingerprint of
`identity.matched_profile_id` (**equality with L1's profile**, not
re-membership: a swap to a *different approved* profile is refused); (3)
exposure absence; (4) I_r; (5) I_n. Only an exact `True` proceeds to
`launch()`; nothing between it and `Popen` reads the Pi tree, resolves a name,
or executes anything. The check→use sliver now spans the whole payload walk
(stated residual).

### 7.6 L21A — mandatory post-runtime payload re-observation (B2)

**Placement (B8, R3).** The frozen closure **execution order** is:

```text
L21   runtime teardown (the DIRECT child's exit status and both reader EOFs)
L22   broker diagnostic capture
L23   broker shutdown
L24   sensitive generated-config / extension scrub
L21A  post-runtime payload re-observation              ← here, not after L21
L25   Git observation #1
L26   verification (runs repository-controlled code)
L27   workspace cleanup
```

The step keeps the design name `L21A`; the number records that it concerns the
runtime L21 closed, and does **not** imply physical adjacency to L21.
Rationale, frozen:

> Resource shutdown and sensitive-material scrub have priority over the
> potentially expensive post-runtime payload observation. L21A must not create a
> new interval in which an unrelated filesystem observation can delay broker
> shutdown or token/config scrub.

L21A still precedes L26, so its observation is taken before any
repository-controlled code runs. It obeys OC-4 exactly as every other closure
step does, and OC-4 is otherwise not reopened:

- `runtime_created == false` → `NOT_APPLICABLE`, and nothing is observed;
- `runtime_created == true` → L21A is **attempted exactly once**;
- a contained failure at L21, L22, L23 or L24 **must not** skip L21A (an L21
  failure is reflected only through L21A's own "L21 proved direct-child exit"
  condition, yielding `UNPROVEN`, never through skipping);
- a contained L21A failure **must not** skip L25, L26 or L27; it yields
  `UNPROVEN` (result table below).

It executes nothing, reads no credential, and writes nothing but its own
observation into the run's observations. Moving it after L24 lengthens the
interval between the child's exit and the observation by the duration of
L22–L24; this widens the documented A→B→A residual slightly and changes no
meaning (F-18).

**Applicability.** Applicable **iff** `runtime_created == true` (a Pi process
existed, so Pi code may have executed). Otherwise the value is
`NOT_APPLICABLE` — no observation is fabricated for a run in which Pi never
launched (including a `launch()` whose `CreateProcess` failed).

**Procedure.** A complete payload re-walk → `pf''`, then the exposure-absence
check, then I_r.

**Closed result** `pi_profile_post_runtime_reobservation`:

| Value | Condition |
|---|---|
| `NOT_APPLICABLE` | `runtime_created == false` |
| `CHANGED` | walk complete and `pf''` ≠ the run's profile payload fingerprint, **or** an exposure is now present |
| `UNPROVEN` | not `CHANGED`, and any of: L21 did not prove the direct child's exit; the walk was not completely observable; I_r drifted; the step raised |
| `PROVEN_UNCHANGED` | L21 proved direct-child exit, the walk is complete and `pf''` equals the run's profile fingerprint, exposures absent, I_r unchanged |

**Meaning, exactly.** `PROVEN_UNCHANGED` means *the payload observed at L14 and
at L21A are identical and the direct child had exited when L21A observed*. It
does **not** prove continuity between those instants (an A→B→A change is
undetectable), does not track descendants, and **prevents nothing**: a mid-run
change is only detected. `CHANGED`/`UNPROVEN` mean the run's Pi-profile
attribution **cannot be proven**.

**Consequences.**

- Only `PROVEN_UNCHANGED` may support a definite profile-attribution claim for a
  run that launched Pi.
- `CHANGED` or `UNPROVEN` ⇒ the run classification is
  **`INDETERMINATE_PI_PROFILE`** (a new indeterminate classification, evaluated
  after `INDETERMINATE_LIFECYCLE` and `REFUSED_PRE_DISPATCH` and before every
  dispatch/runtime classification), so it can never be `ACTIVE`/`INACTIVE` —
  i.e. never a normal profile-attributed result; by the existing arm rule the arm
  becomes `INDETERMINATE`.
- `CHANGED` or `UNPROVEN` ⇒ **stage halt** after that ordinal's closure
  (halt reason `PI_PROFILE_ATTRIBUTION_UNPROVEN`): no further ordinal is
  admitted under that stage execution; the stage cannot close as a normal
  completion; a later attempt needs a fresh diagnosis and a fresh authorization.
- No second execution, no retry, no re-run of the ordinal is introduced.
- A refused-pre-dispatch run in which the process was created (e.g. an L15/L16
  refusal) still records L21A and still halts the stage on `CHANGED`/`UNPROVEN`;
  its classification remains `REFUSED_PRE_DISPATCH`.

### 7.7 How a new version avoids editing production Python

| Change | What changes | Production Python edited? |
|---|---|---|
| New Pi release, same layout/scope, qualified at C2/C3 | one APS revision + inventory + bundle + evidence (data) | **No** |
| Profile retired | one APS revision (data) | **No** |
| Behavior change forcing AIDO logic to change (C4) | consumer code + `CFG1-CC` revision + re-approvals | Yes — behavior changed, not merely a version literal |
| Layout or payload-scope change (C5) | payload/seam contract + design amendment | Yes — by design |

---

## 8. Qualification depth and evidence reuse

### 8.1 Principle

**Conclusions never transfer.** No PASS, verdict, ranking, qualification
result, or approval ever becomes authority for a different profile, and nothing
here is automatic. **Evidence may be reused** in a **new, explicit**
qualification/adoption decision **only** when the premises that evidence depends
on are **mechanically** shown unchanged (§8.5). No semver range, compatibility
matrix, or auto-revalidation rule exists (roadmap §2.1). Classes set the
**minimum** evidence a reviewer must see, never an outcome.

### 8.2 Mechanical floor classification (discovery computes; loader re-verifies; reviewers may escalate, never downgrade)

Definitions: `R` ranges over approved profiles in the APS (with committed
inventories); `S` over seam evidence records and approved profiles' seam
tables. **Permitted manifest files** (`PI-PC1`): the root,
`node_modules/@earendil-works/pi-ai` and `node_modules/@earendil-works/pi-agent-core`
`package.json` files. **Permitted value slots** (B9, R3 — values only; never
keys, never presence, never position):

- the top-level `version` value (its presence is already required by the §4.5
  declaration schema, so only its exact-`str` value may differ);
- in those three manifests only, the **value** of a `dependencies` entry named
  `@earendil-works/pi-ai` or `@earendil-works/pi-agent-core`, **and only when
  that key is present in both the candidate and the reference**.

**Key presence is immutable under C2.** For each permitted internal dependency
entry, `candidate key present == reference key present` is mandatory. If
present in both, both values must be exact `str` and only those values may
differ. If presence differs (present → absent, or absent → present), the
candidate is **not** C2: a dependency key-set change is a non-permitted manifest
change and follows the normal C3 path. Absence is represented only as absence —
never as `None`, `""`, a falsy value, or any other sentinel that could be
confused with a valid value.

**The C2 comparison projection** (replaces R2's ambiguous "after removing only
the permitted fields"):

```text
1. parse candidate and reference strictly and order-preservingly
   (duplicate keys refused, exact types);
2. verify key presence of every permitted slot is identical on both sides —
   otherwise NOT C2 (no projection is attempted);
3. preserve the ENTIRE ordered object structure and EVERY key on both sides;
   for each permitted value slot present in both, replace ONLY that VALUE with
   one fixed internal comparison marker;
4. compare the complete ordered structures with exact types.
```

Nothing is deleted, popped or filtered, so no projection step can erase a
key-presence or key-position difference. The marker is an implementation detail
of PE-2a; it must lie **outside the JSON value domain** (e.g. a module-private
object), so no parsed JSON value — string, number, `null`, list or object — can
alias it.

| Class | Mechanical condition |
|---|---|
| **C1** | `profile_id` ∈ eligible — exact payload + exposure identity. Nothing to qualify. |
| **C1R** | equals a retired or ineligible known profile → refused; re-admission is a design decision. |
| **C2** | ∃ `R` such that: identical inventory path sets and kinds; every entry byte-identical **except** a non-empty subset of the permitted manifest files; for each differing manifest, the key presence of every permitted value slot is identical on both sides, and the two documents are equal **as complete ordered key/value structures at every level** (order-preserving parse; exact types) **under the structure-preserving value-slot projection above**; and the exposure sets are equal. Formatting-only byte differences (whitespace, escape spelling) are within C2 but are always enumerated as `RAW_BYTES` deltas for PMD (§8.6). |
| **C3_SEAM_EQUAL** | observable, not C1/C2, `PI-SC1` complete, and the seam fingerprint equals some `S`. |
| **C3_SEAM_CHANGED** | observable, not C1/C2, `PI-SC1` complete, and no `S` has an equal seam fingerprint (including when no reference exists at all). |
| **C4** | review outcome: a behavior AIDO relies on changed; AIDO code must change. |
| **C5** | payload not observable, a `PI-SC1` path absent, layout/anchor/package identity differs, manifests not strictly parseable, or bounds exceeded. |

Rules that close the R0 defect:

- **C1 is payload equality, never seam equality.**
- **Any change outside the 20 seams yields a different profile** (§5.4).
- **C2 is proven, not inferred:** "seam code unchanged" is never sufficient;
  every non-manifest payload byte must be identical and the manifest
  differences must lie exactly in permitted value slots whose keys are present
  on both sides, checked on bytes committed in the manifest bundle and bound to
  the inventory. A dependency key added or removed is never C2.
- **Every other payload change is at least C3.** Seam equality (C3_SEAM_EQUAL)
  only narrows the derivation re-review; it never collapses a changed payload
  into an approved profile.
- **The floor is mechanical; the approval class is a review conclusion.** A
  C2 floor never becomes C3 because a delta turns out to matter, and a
  `C2_MANIFEST_ONLY` approval is never implied by a C2 floor. When PMD finds a
  relevant delta, the floor stays C2 and the review concludes
  `C2_MANIFEST_DELTA_REACQUIRED` (evidence re-acquired, no AIDO code change) or
  escalates to C4 (AIDO code must change).

### 8.3 Evidence items

| Id | Evidence | Nature |
|---|---|---|
| E1 | Static seam derivations (CFG1 §1.2/§2; FU1/FU2 `get_state`, `jsonl.js`, `agent-loop.js`, `rpc-mode.js`) | line-cited against exact seam bytes |
| E2 | Manifest review (bin, main/exports/imports, type, engines, dependency sets) and the exposure set | static; mechanically derived facts + review |
| E3 | Non-seam payload diff review against the nearest reference inventory: every added/removed/changed file, reviewed for effect on AIDO's premises (process launch, RPC framing, extension loading, tool dispatch, request building, network, filesystem, prompt construction) | static; review depth recorded in evidence |
| E4 | Offline request-shape conformance (the T-3 class) | **executes candidate code** — separate explicit authorization only, credential-free |
| E5 | `RUNTIME_COMPATIBILITY` zero-prompt live check | live; separate authorization |
| E6 | `ROLE_CAPABILITY` qualification (Q1/Q2 IMPLEMENTER) | live; separate authorization |
| E7 | Publication provenance: payload compared with the published registry artifact of the declared version | download; separate authorization; recommended |
| PMD | **Permitted-Manifest-Delta consumer review** (§8.6), replacing R1's version-only EV: every mechanically enumerated manifest delta — each changed `version`, each changed permitted internal dependency value, and the raw bytes of every differing manifest — reviewed against every consumer category, per delta and per reused evidence item | static review over a mechanically complete delta list; mandatory for a C2 floor and for any `PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS` reuse |

### 8.4 Minimum evidence per class

| Class | Required | Approval as data only? |
|---|---|---|
| C1 | none — already approved | n/a |
| C2 floor → `C2_MANIFEST_ONLY` | complete PMD concluding every delta is irrelevant to `CFG1-CC1` behavior **and** to every reused item; E2 (confirm the mechanical C2 facts); a new profile + approval citing `R` | **Yes** |
| C2 floor → `C2_MANIFEST_DELTA_REACQUIRED` | complete PMD naming each affecting delta and each affected category/evidence item; affected evidence **not** reused; the reacquired evidence cited; E2 | **Yes**, if no AIDO code must change (else C4) |
| C3_SEAM_EQUAL | E1 reused by premise (§8.5); **E3 over every non-seam change**; E2; an explicit statement that `PI-SC1` remains sufficient (no changed non-seam file entered a derivation basis — else re-derive or C5); E4 if any request-building file (seam or not) changed | **Yes**, if no AIDO code must change |
| C3_SEAM_CHANGED | every E1 claim touching a changed seam file re-derived with line citations; E1 on unchanged seam files reusable by premise; E3; E2; sufficiency statement; E4 if the request-building path changed | **Yes**, if no AIDO code must change |
| C4 | consumer design + code amendment; new `CFG1-CC`; `CC_REAPPROVAL` for every profile to remain eligible; E4; E5 | No — code first |
| C5 | new payload/seam contract; design amendment; full E1–E5 | No |

CFG1's per-run fail-closed runtime gates (L15 H1; L16 H2/`get_state`/config
shape) remain the runtime backstop for C2/C3 approvals; they do not replace E1.

### 8.5 Evidence reuse: premise scopes (B4)

Every reused item in an approval declares `evidence_kind`, `source_id` (a
`profile_id` or seam `evidence_id`) and a closed `premise_scope`. The loader
mechanically verifies the premise between the source and the candidate:

| `premise_scope` | Mechanical check | Applicable evidence kinds |
|---|---|---|
| `SEAM_FILES:<listed PI-SC1 paths>` | those seam digests equal | E1 |
| `PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS` | the C2 relation (§8.2) holds between source and candidate profiles **and** the approval's `pmd` records, for this evidence item, `NOT_AFFECTED` for **every** delta | E3, E4, E5, E6 |

Rules:

1. **Reuse is never automatic.** It exists only as an entry in a new, explicitly
   reviewed approval or qualification decision; the loader verifies the premise
   but never creates the entry.
2. **A verified C2 structural relation alone is never enough.** Every reuse
   under `PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS` requires a complete PMD
   (§8.6) covering **all** actual manifest deltas — every changed `version`,
   every changed permitted internal dependency value, and the raw bytes of every
   differing manifest — and PMD must conclude, per delta, that the delta does not
   reach anything that evidence item depended on. If **any** delta reaches its
   premise, that item is **not** reused and the decision states what is
   re-acquired.
3. **Changed harness premises invalidate.** If agent-loop, tool, prompt,
   dispatch, request-building or any other non-permitted payload byte changed,
   the `PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS` check fails, E4/E5/E6 cannot be
   reused under HPP-1, and the decision explicitly chooses partial or full
   re-acquisition. A narrower premise map for E4/E5/E6 (e.g. "only these files")
   is **not** defined by HPP-1; it would require a separately authorized design.
4. **Non-Pi premises are outside this check** and must be unchanged by the
   decision's own record: model, backend, route, role, corpus, prompt policy and
   qualification policy revision (roadmap §2 tuple).
5. **Pre-HPP evidence** (Q1/Q2 results recording `observed_version` via
   `--version`, CFG1 v1/v2 records) has **no payload fingerprint**; its Pi
   premises cannot be mechanically shown unchanged against any profile, so it is
   citable as history only, never reusable under rule 3. The historical 0.85.1
   **seam** derivations are the exception, because their premise is exactly the
   genesis seam table (E1 via `SEAM_FILES`).
6. HPP-1 approvals grant **CFG1 live eligibility** under `CFG1-CC1` only. A
   `ROLE_CAPABILITY` claim for a profile remains a separate, explicitly
   authorized Q-phase decision, which may use rules 1–5 but is never implied by
   an HPP-1 approval.

### 8.6 PMD — Permitted-Manifest-Delta consumer review (B6)

**Why it exists.** A C2 floor proves that only permitted manifest facts
differ. It does not prove those facts are inert: unchanged Pi code may read a
parsed `version`, a parsed internal dependency range, or the raw `package.json`
bytes/text, and act on them. R1's version-only review (EV) covered only the
first of these; PMD covers all of them.

**The delta list is mechanical.** For a candidate and its C2 reference `R`,
discovery computes, and the loader recomputes, the complete ordered list of
delta facts. For each differing permitted manifest file `M`:

```text
RAW_BYTES                              always, for every differing M
VERSION                                if M's top-level "version" value differs
INTERNAL_DEPENDENCY:<canonical name>   for each permitted internal dependency
                                       ("@earendil-works/pi-ai",
                                        "@earendil-works/pi-agent-core")
                                       whose key is present in M's "dependencies"
                                       in BOTH reference and candidate, and whose
                                       exact-str value differs
```

A dependency key addition or removal is **never** a PMD delta: such a candidate
is not C2 in the first place (§8.2), so it never reaches a C2 PMD.

Each fact carries `M`'s relative path and the old and new values (for
`RAW_BYTES`: the two SHA-256 digests). Nothing else can differ under a C2 floor,
so this list is complete by construction.

**The PMD record** (in the approval; closed schema):

```text
pmd
  reference_profile_id        the C2 reference R
  deltas                      must equal the recomputed delta list exactly
                              (same facts, same order, same values)
  per delta:
    read_as_parsed_field      "NOT_READ" | "READ"         (with line-cited refs if READ)
    read_as_raw_manifest      "NOT_READ" | "READ"         (whether any payload code reads
                                                           this package.json as bytes/text)
    categories                exactly these keys, each "NOT_REACHED" | "REACHED_NO_EFFECT"
                              | "AFFECTS", with refs for anything but NOT_REACHED:
        PROMPT_OR_MODEL_VISIBLE_CONTENT   RPC_BEHAVIOR           REQUEST_SHAPE
        PROVIDER_OR_MODEL_SELECTION       FEATURE_GATES          CONFIG_MIGRATION
        TOOL_REGISTRATION_OR_DISPATCH     EXTENSION_BEHAVIOR     FILESYSTEM_BEHAVIOR
        NETWORK_BEHAVIOR                  TELEMETRY_USER_AGENT_OR_HEADERS
    cfg1_cc1_effect           "NOT_AFFECTED" | "AFFECTED"
    evidence_effect           for EACH reused_evidence item: "NOT_AFFECTED" | "AFFECTED"
  conclusion_refs             the review documents
```

**Mechanical rules the loader enforces:**

1. A PMD must be present whenever the floor is C2 or any reuse uses
   `PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS`; its `deltas` must equal the
   recomputed list exactly; every category key must be present; every
   `evidence_effect` map must have exactly one entry per `reused_evidence` item.
2. A category `AFFECTS` requires `cfg1_cc1_effect == "AFFECTED"` or the
   corresponding `evidence_effect` to be `AFFECTED` for at least one item, and
   vice versa — a finding cannot be both "affects" and "affects nothing".
3. `C2_MANIFEST_ONLY` is admissible **only** if every delta has
   `cfg1_cc1_effect == "NOT_AFFECTED"` and every `evidence_effect` entry is
   `NOT_AFFECTED`.
4. A reuse entry under `PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS` is admissible
   only if its `evidence_effect` is `NOT_AFFECTED` for **every** delta.
5. If any delta has `cfg1_cc1_effect == "AFFECTED"` or any `evidence_effect`
   is `AFFECTED`, the approval class must be `C2_MANIFEST_DELTA_REACQUIRED` or
   more conservative; the affected evidence may not appear in `reused_evidence`;
   the re-acquired evidence must appear in `evidence`.
6. If the effect requires AIDO consumer code to change, the only admissible path
   is C4 (code first); no data-only approval exists for it.

**What is mechanical and what is review.** The **completeness** of PMD (every
delta, every category, every reused item) and its **consistency** with the
approval class and reuse entries are mechanical. The **truth** of each finding
(e.g. that no payload code reads the raw manifest) is independent review,
line-cited against payload bytes committed or bound by the inventory. PMD never
changes the mechanical floor; the floor never substitutes for PMD.

**Raw bytes are always a delta.** Even when the parsed documents are equal
apart from permitted value slots (e.g. whitespace or escape-spelling changes), the
`RAW_BYTES` delta is listed, and a Pi code path that hashes, regex-scans, or
otherwise reads `package.json` as text must be found and assessed by PMD.

---

## 9. Adoption authority

### 9.1 Who may add an approved profile

Only the **operator**, by committing one new APS revision plus its inventory,
manifest bundle and evidence files, after an **independent acceptance** under the
project's review practice (recorded outside the file). No AIDO code path writes
an APS revision; discovery writes only candidate records; no agent commits.

### 9.2 What immutable evidence authorizes the addition

The approval's `evidence` and `reused_evidence` (premise-verified), the bound
inventory and manifest bundle, and the candidate record. The loader recomputes
every derivable field; every evidence reference is checked by the §4.14
evidence-reference verifier (grammar, containment, no links, regular file,
digest), and its tracked state by the approval procedure's read-only Git
review. Mechanically, an approval becomes
effective **only** when a separately reviewed live authorization binds an APS
head containing it (F-5).

### 9.3 Later approvals under an existing live authorization

**No.** A live authorization binds one exact head `H`; later approvals are not
eligible under it. Every CFG1 live authorization is single-use and bound to an
exact commit, so delegation would add no usability and would let unreviewed
approvals become live authority.

### 9.4 What the live authorization binds

```text
live authorization
    binds   source commit C, APS head digest H, CFG1-CC1, HPP-1, PI-PC1, PI-SC1
    permits exactly: an observed payload whose profile ∈ eligible(CFG1-CC1) of H,
                     with exposures absent, re-proven at L1 and L14,
                     and PROVEN_UNCHANGED at L21A for definite attribution
    authority scope: the PROFILE-COVERED FACT only (§0.1); the §5.5 external
                     runtime residuals are outside it and the authorization
                     must say so
    names   the eligible profiles (ids + declared versions) for reviewers only
    supplies to run_cfg1_stage: only the stage_execution_id (unchanged)
```

Launcher enforcement before consumption: existing source-origin gates (now also
covering the APS and evidence directories inside the audited root); **G6A** —
the sealed snapshot's head equals `APS_HEAD_SHA256` and its contract/policy
literals equal the launcher's; G7 gate; G8 re-audit. The authorization's review
must include the APS diff since the previously authorized head.

### 9.5 What prevents the installed Harness from modifying its approval state

- Before L14 Pi never runs; it only has bytes hashed.
- The APS lives in the AIDO checkout; P1 refuses Node/Pi resolved inside it; the
  trees are disjoint.
- P, L1, L14 and L21A parse nothing Pi-authored. The loader parses only
  **committed** manifest copies whose digests are bound to the inventory; the
  results are descriptive (versions) or policy the reviewers approved
  (exposures).
- After L14 Pi runs unconfined; the in-process snapshot is sealed and never
  re-read; any on-disk change fails the next admission (dirty tree, head ≠ `H`,
  or `HEAD` moved).

### 9.6 Retirement without rewriting history

An appended record in a new revision; earlier heads keep their meaning and
their eligible sets remain recomputable from the committed chain.

### 9.7 If state changes between boundaries

| Change | Effect |
|---|---|
| Payload changes between gate and L1 | L1 re-walks; unapproved → L1 refusal (consumed; existing residual); approved-but-different → allowed for ordinal 1 (fixes the stage profile) |
| Payload changes between ordinals | next L1: unapproved → refusal; approved-but-different → `PI_PROFILE_CHANGED_WITHIN_STAGE` |
| Payload changes between L1 and L14 | L14 `pf' ≠` L1's → `RUNTIME_LAUNCH_FAILED`, no launch |
| Payload changes after L14 | not prevented; L21A records `CHANGED` (if it persists) → `INDETERMINATE_PI_PROFILE`, stage halt |
| Exposure appears upward at any point | P2X refuses before launch; after launch L21A records `CHANGED` |
| APS files change on disk in-process | no effect (sealed); next admission fails |
| APS differs between processes | G6A refuses unless it equals the bound `H` |

### 9.8 Launcher remedy text

For `PI_PROFILE_UNAPPROVED`, `PI_PAYLOAD_UNPROVEN` and
`PI_EXTERNAL_RESOLUTION_EXPOSED`: *the installed Pi is not eligible under this
authorization's APS head; route it to profile onboarding; this authorization
cannot be used with it.* A4 §10's "restore the approved Pi environment" must
not be carried forward.

---

## 10. Records

### 10.1 Historical meanings (immutable)

- **v1**: `pi_observed_version` meant "AR2's `--version` probe reported this".
- **v2**: `pi_seam_digests_match == true` means "the complete singleton
  20-entry 0.85.1 seam table matched" — and, per OC-2, **nothing** about the
  rest of the package. Never re-validated or reinterpreted against an APS.

### 10.2 Why v3

A v2 record cannot say which payload matched. AMEND1 §7.3's reasons for
omitting a version field in v2 were (1) no information, (2) misreading risk,
(3) the singleton table already identified the bytes; (1) and (3) no longer hold,
(2) is addressed by naming and by mechanical binding. AMEND1's v2 decision
stands.

### 10.3 v3 fields (design; exact schema in PE-1)

| Field | Domain | Rule |
|---|---|---|
| `pi_payload_contract` / `pi_seam_contract` / `pi_consumer_contract` / `pi_profile_policy_revision` | literals `PI-PC1` / `PI-SC1` / `CFG1-CC1` / `HPP-1` | exact |
| `pi_profile_set_head_sha256` | 64 hex | always present |
| `pi_payload_observation_complete` | bool | per `Allowed(F)` |
| `pi_profile_id` | 64 hex or null | non-null iff P passed |
| `pi_profile_declared_package_version` | bounded text or null | copied from the matched profile (loader-bound to manifest bytes); null iff `pi_profile_id` null; named "declared" |
| `pi_identity_failure_code` | null or one of six codes | below |
| `pi_profile_post_runtime_reobservation` | `PROVEN_UNCHANGED` / `CHANGED` / `UNPROVEN` / `NOT_APPLICABLE` | `NOT_APPLICABLE` iff `runtime_created == false` |
| `pi_profile_authority_scope` | literal `"PI_PACKAGE_PAYLOAD_AND_DECLARED_RESOLUTION_BOUNDARY"` | exact; names what the PROFILE-COVERED FACT covers (B7) |
| `pi_external_runtime_residual` | literal `"NOT_IDENTIFIED_BY_PROFILE"` | exact, in **every** v3 record, including passes; a string, never a boolean, following the project's `"not sandboxed"` convention for facts AIDO does not observe |
| `run_classification` | existing domain + `INDETERMINATE_PI_PROFILE` | `ACTIVE`/`INACTIVE` require `PROVEN_UNCHANGED`; `CHANGED`/`UNPROVEN` with a dispatch-phase outcome ⇒ `INDETERMINATE_PI_PROFILE` |

`Allowed(F)`:

| `pi_identity_failure_code` | `pi_payload_observation_complete` | `pi_profile_id` |
|---|---|---|
| null (pass) | true | non-null |
| `PI_RESOLUTION_FAILED` | false | null |
| `PI_PAYLOAD_UNPROVEN` | false | null |
| `PI_PROFILE_UNAPPROVED` | true | null |
| `PI_EXTERNAL_RESOLUTION_EXPOSED` | true | null |
| `PI_IDENTITY_DRIFTED_DURING_PROOF` | true | null |
| `PI_PROFILE_CHANGED_WITHIN_STAGE` | true | null |

The v3 validator is a pure function of the artifact's own fields; binding
`pi_profile_id` and the declared version to the committed APS chain is a
separate read-only verifier. No v3 key, closed-enum value, halt reason or
console code may be named or worded so as to claim complete runtime identity
(e.g. `runtime_identity_complete`, `fully_identified`, `node_pinned`); a
`PROVEN_UNCHANGED` value speaks only to the PROFILE-COVERED FACT. The
stage-closure record carries the stage profile id, the invariant that every run
record carries it, and the `PI_PROFILE_ATTRIBUTION_UNPROVEN` halt reason when
applicable.

---

## 11. Disposition of every current singleton-version pin

**HIST** = historical evidence, immutable; **PROV** = provenance, no authority;
**AUTH** = current runtime authority, migrate; **TEST** = test fixture,
parameterize/profile-bind; **DEAD** = remove only in a later authorized phase.
Nothing is modified by this design.

### 11.1 CFG1 production source

| Occurrence | Class | Disposition |
|---|---|---|
| `preflight.PINNED_PI_SEAM_DIGESTS` | **AUTH** | Becomes, byte-for-byte, the **genesis seam evidence** record (not a profile). PE-2b keeps a test asserting equality; the dict then becomes DEAD or a frozen historical constant used only by that test. It stops being runtime identity. |
| `pi_identity.PINNED_SEAM_ENTRY_COUNT = 20` | **AUTH** | `PI-SC1` cardinality assertion. |
| `pi_identity._complete_seam_set_matches` | **AUTH** | Replaced by the payload walk (P2) + match (P2M) + exposure (P2X). |
| `pi_identity.reprove_pi_identity_for_launch` | **AUTH** | §7.5. |
| gate/failure vocabularies, `ALLOWED_SEAM_MATCH_FOR_FAILURE` | **AUTH** | §7.4, §10.3. |
| `pi_identity.Cfg1PiIdentity` | **AUTH** | Gains exactly `matched_profile_id`; no version slot. |
| `_PI_PACKAGE_PARTS`, `_PI_ANCHOR_NAME`, `dist/cli.js` | **AUTH** (layout) | Part of `PI-PC1`. |
| `identity.PINNED_PI_VERSION = "0.85.1"` | **DEAD** | No runtime consumer (AMEND1 §7.4); survives as provenance in the genesis seam evidence's citations. |
| `preflight.verify_pi_seam_digests` | **DEAD** | No production caller since FU1; follows links; superseded. |
| `preflight.COMPAT_DETECTION_SUBSTRINGS` | **AUTH** (consumer code) | A `CFG1-CC1` derivation; revalidated per profile via E1; a change is C4. |
| `arms.*`, `extension_pins.*` digests | not Pi pins | AIDO-owned bytes; their acceptance by Pi is E1. |
| `records.py` v1 `pi_observed_version`, `_PI_VERSION_PATTERN` | **HIST** | Unchanged. |
| `records.py` v2 identity group | **HIST** | Frozen to the singleton seam table. |
| `run_executor.py` L1/L14; closure ladder L21–L27 | **AUTH** | `matched_profile_id`, stage consistency, new L21A (§7.6). |
| `classification.py` `RUN_CLASSIFICATIONS` | **AUTH** | Gains `INDETERMINATE_PI_PROFILE` (§7.6). |
| docstrings "20-file frozen seam proof", "Pi 0.85.1" | **PROV** | Reworded in PE-2; historical citations kept. |

### 11.2 CFG1 tests

| Occurrence | Class | Disposition |
|---|---|---|
| `cfg1_doubles.py` monkeypatching `PINNED_PI_SEAM_DIGESTS` | **TEST** | Synthetic sealed snapshots over synthetic payload trees under `tmp_path`. |
| `test_cfg1_composition.py:703-709` | **TEST** | `PI-SC1` path-set + genesis-equality assertions. |
| `test_cfg1_pi_conformance.py`, `cfg1_t3_conformance.mjs` | **TEST** (machine-state) | Profile-bind: installed payload ∈ eligible set, else fail loudly "unapproved"; never skip, never compare a version. T-3 keeps its own execution authorization. |
| `test_cfg1_fu1_static_identity.py` synthetic `"0.87.0"` | **TEST** | Keep; extend per §14.3 and §14.4. |
| `cfg1_builders.py`, `test_cfg1_fu1_records_v2.py` v1 fixtures | **HIST** | Unchanged. |

### 11.3 Frozen historical experiments

| Occurrence | Class | Disposition |
|---|---|---|
| AR1 `PINNED_PI_VERSION = "0.84.2"`, exact `--version` equality | **HIST** | Frozen; not imported by CFG1. |
| AR2 `launch.py`/`__init__.py` `PINNED_PI_VERSION = "0.84.2"`, `resolve_runtime_identity`, `RuntimeIdentity.reported_version`; `run_ar2.py` fields | **HIST** | Frozen (AR2 live NO-GO, OC-6); CFG1 does not use them. |
| `ar2/tests/probe_support.py` 0.85.1 `get_state` shape | **TEST/PROV** | Unchanged unless AR2 reopens (not authorized). |
| O1 `pi_compat.py` (provenance-only) | **PROV** | Unchanged. |

### 11.4 Q1/Q2 qualification package

| Occurrence | Class | Disposition |
|---|---|---|
| `resolve_pi_identity`, `observed_pi_version` (I2B) | **PROV** | Never a gate; out of this consumer scope. |
| `preflight_pi_installed_offline` | **PROV** | Unchanged. |
| `test_live1_i1_pi_source_drift.py` version literals | **TEST** | The "advance a literal after re-review" pattern HPP-1 replaces; migration is a separate Q-scoped authorization. |
| LF1 "version mismatch alone never rejects" | **PROV** | Already correct. |
| `results/*_IQ-*.json` (`0.85.1`), `results/i2b_live_*.json` (`0.84.4`) | **HIST** | Immutable; pre-HPP evidence (§8.5 rule 5). |

### 11.5 CFG1 evidence

| Occurrence | Class |
|---|---|
| `results/CFG1-S1-A1`, `-A2` (`pi_observed_version: "0.85.1"`), `-A3` | **HIST** |

### 11.6 Documents

| Document | Class | Disposition |
|---|---|---|
| CFG1 §1.2, §2; L16-FU2 §16; OC-3 archaeology | **HIST** + genesis E1 | Cited by the genesis seam evidence. |
| CFG1 §14.1 item 2, §14.2; FU1 R6 §2, §17 item 6; AMEND1 §7.4, §19 item 5 | forward-looking | Superseded only by PE-1; not edited. |
| FU1 R6 OC-2 / AMEND1 §14 | **HIST** | Only the package-payload portion is covered by this design once implemented (§3.3); OC-2 is not closed beyond it — Node and every §5.5 external runtime residual remain. |
| LIVE-S1, A2, A3, A4 | **HIST** | Immutable; A4 withdrawn. |
| Roadmap §2/§2.1 | preserved principle | Satisfied by `(pi_profile_id, declared version)`. |

---

## 12. Onboarding the currently installed Pi — without downgrade

This document records **no fact** about the currently installed Pi and assumes
no version. The installed Pi is a **candidate**.

1. **Discovery (static, PE-3).** Runs P0, P1, the complete payload walk
   **twice** (the two inventories must be identical — stability against an
   in-progress install), the exposure computation and upward-absence check, and
   P2R; emits the candidate record including the inventory, manifest bundle,
   profile id, seam fingerprint, declared projection and floor class. Executes
   nothing, reads no credential, contacts nothing, writes only the candidate.
   Every dependency key is validated by the §5.3.1 schema and parser before it
   forms any in-memory key or filesystem path; a key outside the HPP-1 grammar
   makes the candidate C5 (`PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR`) with **no**
   upward-absence observation attempted for it.
2. **Qualification (PE-4)** per class. Because genesis has **no profile**, the
   first candidate cannot be C1/C2: its floor is C3_SEAM_EQUAL (reusing the
   historical seam derivations in full, plus E3 over the whole non-seam payload),
   C3_SEAM_CHANGED, or C5. The first adoption is the expensive one; later
   upgrades can be C2 or C3_SEAM_EQUAL against it. C4/C5 → design amendment —
   still **no downgrade**.
3. **Approval (PE-5).** APS revision 2: profile + inventory + bundle + approval.
4. **Adoption (PE-6).** A fresh live authorization binds the new commit and
   head. No production Python changed; no version literal edited.

The operator **may** use any installation whose profile is eligible; no AIDO
document, code path or remedy **requires** a particular release.

---

## 13. The motivating incident — another project upgrades global Pi

| When | Outcome |
|---|---|
| AIDO idle | Next gate: `PI_PROFILE_UNAPPROVED` (or `PI_PAYLOAD_UNPROVEN`/`PI_EXTERNAL_RESOLUTION_EXPOSED`); not consumed; onboarding. No downgrade required. |
| Another project installs a **sibling** global package | Irrelevant if every declared dependency is contained; if it lands on a declared exposure name, P2X refuses (before launch) or L21A records `CHANGED` (after). Undeclared resolution remains R-EXT-1: the profile does not change, and evidence describes it as an EXTERNAL RUNTIME RESIDUAL, never as covered. |
| Between gate and consumption | L1 refuses (consumed; existing residual). |
| Between ordinals | L1 refuses; stage halts. |
| Between L1 and L14 | L14 refuses; no launch. |
| While Pi runs | Not preventable; L21A detects a persisting change → `INDETERMINATE_PI_PROFILE`, stage halt. |

Admission attestation A0 cannot bind another project; the detections above are
what actually hold.

---

## 14. Security / adversarial analysis

### 14.1 Per object

| Object | Creator | Mutator | Provenance proof | Pi influence on decision? | Forgeable by a supported caller? | Two valid instances disagree? |
|---|---|---|---|---|---|---|
| `PI-PC1`, `PI-SC1`, `CFG1-CC1` | design + code review | only C4/C5 amendments | audited lineage (G4/G5) | No — fixed before the first read | No | No |
| Payload inventory | discovery; copied by operator | none | canonical hash = `payload_fingerprint`; chain + `H` | Pi supplies the bytes hashed; cannot make other bytes hash equal | Only via commit + review + authorization | Same bytes ⇒ same fingerprint |
| Manifest bundle | discovery | none | each manifest hash-bound to the inventory | Supplies descriptive text and dependency names — both loader-derived from bound bytes, reviewed | as above | Bound per path; mismatch refused |
| Seam evidence | operator | none | recomputed fingerprint | No | as above | Duplicate id refused |
| Profile record | discovery; copied by operator | none | every derivable field recomputed | Only via its own bytes → its own id | as above | Duplicates refused |
| Approval | operator after acceptance | none | recomputed id; class-floor and premise checks | No | as above | One per `(profile, CC)` |
| Retirement | operator | none | as approval | No | as above | Unknown target refused |
| APS revision | operator | none (append-only) | chain + canonical bytes + `H` + clean tree | No | as above | Superset rule |
| Sealed snapshot | loader at import | none | G6A | No | No constructor, no parameter | One per process |
| Candidate record | discovery | — | never authority | Yes — hence never loaded | Irrelevant | Irrelevant |
| `PiProofResult`/`Cfg1PiIdentity` | only P | none | exact-shape validation | No | No | No |
| L21A result | executor step | none | pure function of observations | Pi may **cause** `CHANGED`; it cannot cause `PROVEN_UNCHANGED` for different bytes | builder accepts only the step's value | closed enum + invariants |
| Live authorization | operator, reviewed | none | two-step acceptance | No | — | One `H` each |

### 14.2 Scenarios (corrected)

| # | Scenario | Result |
|---|---|---|
| S-1 | Make an approved profile match new bytes | Requires a SHA-256 second preimage on **some file of the payload inventory** (any file under the root) or on the inventory encoding. Bytes **outside** the payload (§5.5) are not covered: changing an undeclared upward dependency, `node.exe`, or a constructed-path target does not change the profile. |
| S-2 | Unknown installation accidentally matches an approved profile | Only by complete payload equality plus equal exposures; there is no partial or nearest match. A candidate whose 20 seams match but any other payload byte differs is **not** a match. |
| S-3 | Profile-id collision | Domain-separated SHA-256; duplicates refused. |
| S-4 | Two records for one payload | Duplicate `payload_fingerprint` refused. |
| S-5 | Pi self-approval via its version text | Version text is descriptive and loader-derived; a changed manifest changes the payload. |
| S-6 | Runtime/model version claims | Never an input. |
| S-7 | Malformed types/truthiness | Exact types, canonical bytes, no boolean authority, set membership. |
| S-8 | Malformed chain / stray / gap / edited record / missing inventory or manifest-bundle file | Whole chain refused at import → G4 refuses. |
| S-9 | Tampering before admission | Clean-tree/untracked checks or G6A. |
| S-10 | Tampering during a run | Snapshot sealed; next admission detects. |
| S-11 | Stale cache | No observation cached; policy snapshot bound by `H`. |
| S-12 | Payload changes between discovery and approval | Approval names the discovered `profile_id`; the changed install has a different fingerprint → `PI_PROFILE_UNAPPROVED`; re-discover. Discovery's double walk catches changes during discovery. The approved profile stays valid for the bytes actually reviewed. |
| S-13 | Change between gate and L1 | L1 re-walks. |
| S-14 | Change between L1 and L14 | L14 payload equality. |
| S-15 | Change between ordinals | Stage consistency. |
| S-16 | Uninstall/reinstall during proof | Incomplete walk, fingerprint mismatch, or I_r drift. |
| S-17 | Reparse topology in the Pi tree | Refused anywhere in the payload. |
| S-18 | Reparse in the APS/evidence directories | G2 refuses; loader reads no-follow. |
| S-19 | npm metadata disagrees with bytes | Never read; for manifests, only committed bytes bound to the inventory are parsed. |
| S-20 | Declared version disagrees with bytes | Impossible for a loadable record: the loader derives the projection from bound bytes and refuses a record that states anything else. Whether the manifest's own text is *truthful* about upstream provenance is E7, not authority. |
| S-21 | Multiple installs / PATH candidates | First admissible candidate only; never searches for a matching one. |
| S-22 | Rollback to an older profile | Eligible if still approved; retire to forbid. |
| S-23 | Forward upgrade to an unqualified profile | Refused; onboarding. |
| S-24 | Partial approval failure | Chain refused entirely; nothing partially eligible. |
| S-25 | Rejection of B | A unaffected. |
| S-26 | Historical mutation | v1/v2 unchanged; APS append-only; genesis tested equal. |
| S-27 | Another project changes global Pi | §13. |
| S-28 | Later approval leaking into an authorization | No delegation. |
| S-29 | CC1 approval used under CC2 code | Filtered out. |
| S-30 | Genesis smuggling a profile | Genesis contains **no** profile; tested equal to the historical seam table. |
| S-31 | Sibling global package shadows a declared-but-uncontained dependency | P2X refuses before launch; L21A `CHANGED` after. |
| S-32 | Understated approval class | Loader floor verification refuses it. |
| S-33 | Evidence reused across changed premises | Loader premise verification refuses the approval. |
| S-34 | Malicious dependency key escaping `node_modules` (`..`, `../x`, `..\x`, `C:\x`, `/x`, UNC) | §5.3.1 parser refuses before any path is formed; the candidate is C5; the loader refuses a committed record whose exposure does not re-parse. |
| S-35 | Scoped-name traversal (`@scope/../x`, `@scope/x/y`, `@/x`, `@scope/`) | Parser refuses (component grammar, exactly one `/`, non-empty components). |
| S-36 | Malformed dependency map or value type | Schema refuses (`dict` only; `str` values only; no subclass, no coercion). |
| S-37 | Profile-controlled file path | None exists: `inventory_ref`/`manifest_bundle_ref` removed; loader paths are fingerprint-derived; evidence paths are opened only by the offline verifier (§4.14). |
| S-38 | Dependency-range-only or version-only delta read by unchanged code | Always enumerated by PMD; reuse and `C2_MANIFEST_ONLY` refused unless PMD shows no effect. |
| S-39 | Undeclared external module changes while the payload is unchanged | Profile unchanged, L21A `PROVEN_UNCHANGED`; evidence carries `pi_external_runtime_residual = "NOT_IDENTIFIED_BY_PROFILE"` and never claims the change was covered. |

### 14.3 Required counterexamples and what PE-2 tests must mechanically prove

Every test uses synthetic payload trees and synthetic APS chains under
`tmp_path`; none touches an installed Pi; none executes Node.

| # | Counterexample | Design outcome | PE-2 test proves |
|---|---|---|---|
| 1 | 20 seams unchanged, `dist/cli/setup.js` changed | different `payload_fingerprint` → different `profile_id`; gate/L1 `PI_PROFILE_UNAPPROVED`; floor `C3_SEAM_EQUAL`, never C1 | P refuses; classifier returns `C3_SEAM_EQUAL`; loader refuses an approval labeled C2 for it |
| 2 | 20 seams unchanged, another non-seam JS changed | same as 1 | same, over a different path |
| 3 | nested dependency file changed (`node_modules/x/…`) | inside payload → new profile | P refuses; inventory differs only at that path |
| 4 | hoisted/sibling dependency changed | contained dependency: not in payload, not consulted by Node — correctly **no** profile change; declared exposure: P2X refuses if present upward; undeclared: R-EXT-1 residual | P2X refuses when `A\node_modules\N` exists for an exposure `N`; a sibling change for a contained dependency leaves P passing; exposure set recomputed by loader equals the record |
| 5 | only root `package.json` `version` changed | new profile, floor C2 relative to the prior profile | classifier returns C2; ids differ; the new profile is ineligible until approved |
| 6 | `package.json` dependencies/exports/type changed | not a permitted field → at least C3 | classifier refuses C2; loader refuses a C2-labeled approval |
| 7 | payload changed after discovery, before approval | approval binds the discovered id; installed differs → refused | gate returns `PI_PROFILE_UNAPPROVED` against a profile approved for the pre-change tree; discovery's double walk refuses a tree mutated between walks |
| 8 | payload changed between gate and L1 | L1 refuses from scratch | gate passes, mutation, L1 refusal with no credential port called |
| 9 | payload changed between L1 and L14 | L14 refuses | `launch()` never called; `runtime_created == false`; L21A `NOT_APPLICABLE` |
| 10 | payload changed after L14, before a lazy import | not prevented; L21A `CHANGED` | L21A `CHANGED`; classification `INDETERMINATE_PI_PROFILE`; stage halt `PI_PROFILE_ATTRIBUTION_UNPROVEN`; no further ordinal admitted; no retry |
| 11 | payload changed after the last lazy import, before L21A | conservatively `CHANGED` (Pi may not have loaded the changed bytes; attribution still unproven); a change reverted before L21A is undetected (residual) | same as 10; a double that mutates and restores before L21A yields `PROVEN_UNCHANGED` — asserting the documented ABA limit, not a guarantee |
| 12 | false declared-version metadata, correct hashes | loader derives the projection from bound bytes → mismatch → chain refused | loader refusal; also refusal when a bundle manifest's bytes do not hash to the inventory digest, or have duplicate keys / non-string `version` |
| 13 | same seam fingerprint, different payload fingerprint | two distinct profiles; seam equality only enables E1 reuse | distinct ids; no match across them; `SEAM_FILES` premise verifies, `PAYLOAD_EXCEPT…` fails |
| 14 | different versions, byte-identical effective runtime payload | cannot exist: the version text is in `package.json`, which is in the payload; two such installs differ exactly in permitted manifest fields → distinct profiles related by C2 | distinct ids; C2 relation verified; neither eligible without its own approval |
| 15 | prior role-capability evidence, premises unchanged | reusable only as an explicit `reused_evidence` entry with `PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS`, plus a complete PMD showing `NOT_AFFECTED` for that item on every delta; never automatic; no conclusion transfers | loader accepts the premise check for a C2-related pair with a clean, complete PMD; refuses the same entry with PMD absent or incomplete; eligibility never arises from the source profile's approval |
| 16 | prior role-capability evidence, harness-loop premises changed (e.g. `agent-loop.js` or any non-permitted byte) | premise check fails; not reusable; decision must re-acquire | loader refuses an approval citing it under `PAYLOAD_EXCEPT…` |

Further PE-2 tests: multiple eligible profiles coexist and each matches only its
own tree; retirement removes eligibility and leaves history recomputable;
duplicate/colliding ids and payload fingerprints refuse; canonical-bytes,
duplicate-key, `NaN`, `bool`-as-`int` and case-fold-collision refusals; reparse
anywhere in the payload refuses; bounds refuse rather than truncate; G6A
refuses a head mismatch; v3 validator enforces `Allowed(F)` and L21A
applicability; `ACTIVE`/`INACTIVE` impossible without `PROVEN_UNCHANGED`.

### 14.4 R2 adversarial additions (B5/B6/B7) and their PE-2 tests or review rules

**B5 — dependency keys and maps.** Each case below is a parametrized PE-2a test
run through **both** the discovery path and the committed-manifest loader path,
with the filesystem-observation leaf replaced by a **recording double that fails
the test if it is called for any path derived from the key**. Each must be
refused by the schema/parser **before** any in-memory lookup key or filesystem
path is formed:

| Input | Refused by |
|---|---|
| key `..` | component grammar (starts with `.`) |
| key `../x` | character set / form (`/` without leading `@`) |
| key `..\x` | character set (`\`) |
| key `C:\x` | character set (`:`, `\`, uppercase) |
| key `/x` | form (`/` without leading `@`) |
| key `\\server\share` | character set (`\`) |
| key `@scope/../x` | form (two `/`) |
| key `@scope/x/y` | form (two `/`) |
| key `@/x` | empty scope component |
| key `@scope/` | empty name component |
| key with embedded NUL or any control character | character set |
| key `x.` / `nul` / `con.js` / `node_modules` / `.x` / `_x` / `-x` / `X` | trailing dot / reserved device stem / reserved name / leading-char rule / uppercase |
| key that is a `str` subclass | `type(key) is str` |
| dependency map that is a list, a string, a `bool`, `null`, or a `dict` subclass | map schema |
| dependency value that is a list, an `int`, a `bool`, `null`, or a `str` subclass | value schema |
| over-long key (> 214) or value (> 1024), map with > 4096 keys | bounds |

Positive tests: `left-pad` → `("left-pad",)`; `@earendil-works/pi-ai` →
`("@earendil-works", "pi-ai")`; each builds exactly
`ntpath.join(A, "node_modules", *components)` and the in-memory key
`…/node_modules/<components joined by "/">`, and each round-trips to the
identical canonical text. A further test asserts statically (AST audit, as the
existing CFG1 P/gate audits do) that no code path passes a raw dependency key
to `ntpath.join`, `os.path.join`, string formatting or concatenation.

**B5 — path-bearing references.** Tests: a profile record carrying an
`inventory_ref`/`manifest_bundle_ref` key is refused (closed key set); a
fingerprint that is not exactly 64 lowercase hex never forms a filename; a stray
or unreferenced file in any policy subdirectory refuses the chain; the runtime
loader never calls the evidence-reference verifier or opens an evidence path
(recording double); the evidence-reference verifier refuses `..`, absolute,
drive, UNC, device and link-component references (synthetic trees; its Git
tracked-state checks use a synthetic repository under `tmp_path`).

**The eight required R2 scenarios:**

| # | Scenario | Outcome | PE-2 test or review rule |
|---|---|---|---|
| 1 | Malicious dependency key escaping `node_modules` | refused before path formation; candidate C5; committed record with such an exposure refuses the chain | the B5 table above, with the recording observation double |
| 2 | Scoped-name traversal | refused by form/component rules | `@scope/../x`, `@scope/x/y`, `@/x`, `@scope/` rows above |
| 3 | Malformed dependency map / value types | refused by schema | map and value rows above |
| 4 | Dependency-range-only C2 change whose unchanged code reads the range | floor stays C2; PMD lists `INTERNAL_DEPENDENCY:<name>` and `RAW_BYTES`; the review must find the reading code (`read_as_parsed_field = READ`); if it reaches a category, `C2_MANIFEST_ONLY` is inadmissible | loader test: a PMD omitting the `INTERNAL_DEPENDENCY` delta refuses; a PMD marking it `AFFECTS` with a `C2_MANIFEST_ONLY` class refuses; the same PMD with `C2_MANIFEST_DELTA_REACQUIRED` and re-acquired evidence loads |
| 5 | Version-only C2 change whose code reads raw `package.json` | PMD lists `VERSION` and `RAW_BYTES`; the review must set `read_as_raw_manifest = READ` and assess each category | loader test: a PMD lacking the `RAW_BYTES` delta refuses; **review rule**: every PMD must cite a search of payload code for reads of each changed manifest as text/bytes, not only for parsed-field reads |
| 6 | Manifest whitespace/raw-byte change with parsed semantic equality | within C2 (floor), always listed as `RAW_BYTES`; key-order change is **not** C2 (order-sensitive comparison) | classifier test: whitespace-only change → C2 with exactly one `RAW_BYTES` delta; key reordering → C3; loader refuses a PMD without the `RAW_BYTES` fact |
| 7 | Evidence marked reusable although a changed permitted fact reaches its premise | refused | loader test: `reused_evidence` entry under `PAYLOAD_EXCEPT…` whose `evidence_effect` is `AFFECTED` for any delta refuses; so does a PMD whose `evidence_effect` map omits the item |
| 8 | External undeclared module changes while payload unchanged | profile identity unchanged; P passes; L21A `PROVEN_UNCHANGED`; record says `pi_external_runtime_residual = "NOT_IDENTIFIED_BY_PROFILE"` | executor test with a synthetic sibling undeclared module mutated mid-run: P, L14 and L21A pass, the record carries both B7 literals; a static test asserts no v3 key, enum value, halt reason or console code uses complete-identity wording (§10.3) |

### 14.5 R3 regression requirements (B8/B9)

**B8 — closure order (PE-2c).** An executor test with doubles for every
closure port records **closure-step entry order** (each step's entry is
recorded before its first side effect, from the executor's own step cursor,
never from a port's claim) and mechanically asserts, for a run with
`runtime_created == true`:

```text
L21 < L22 < L23 < L24 < L21A < L25 < L26 < L27
```

It is parametrized so that:

| Injected contained failure | Required outcome |
|---|---|
| at L21, L22, L23 or L24 (each, separately) | L21A is still entered exactly once, after L24 and before L25; an L21 failure yields `UNPROVEN` (exit not proven); an L22/L23/L24 failure alone does not change L21A's result |
| at L21A (a raising walk or leaf) | L21A yields `UNPROVEN`; L25, L26 and L27 are all still entered in order; classification `INDETERMINATE_PI_PROFILE` for a dispatch-phase run; stage halt `PI_PROFILE_ATTRIBUTION_UNPROVEN` |
| none, `runtime_created == false` | L21A records `NOT_APPLICABLE` and performs **no** payload observation (recording double for the walk leaf never called) |

A further assertion proves no payload-walk leaf call occurs before L24's entry
has been recorded in a launched run, so L21A can never delay broker shutdown or
the sensitive-material scrub.

**B9 — C2 key presence (PE-2a classifier; PE-2b loader).** Synthetic
reference/candidate payloads differing only in one permitted manifest:

| Case | Required classification |
|---|---|
| same `@earendil-works/pi-ai` key, different exact-`str` value | may be C2 (with `INTERNAL_DEPENDENCY:@earendil-works/pi-ai` and `RAW_BYTES` deltas) |
| same key, same value, formatting-only raw-byte change | may be C2 with exactly one `RAW_BYTES` delta |
| reference has the key, candidate omits it | **not** C2 (C3 path) |
| reference omits the key, candidate adds it | **not** C2 (C3 path) |
| key moved/reordered within `dependencies` | follows the frozen order-sensitive rule: **not** C2 |
| key present on one side with a non-`str` value (e.g. `null`, list) | refused by the §5.3.1 value schema before classification |

Plus a projection test proving that no projection step can erase the presence
distinction: the projector is exercised on presence-differing inputs and must
never be invoked (step 2 refuses first), and, on presence-equal inputs, the
projected structures retain every key and key position of the originals; a
static audit asserts the projector performs no `pop`, `del`, filtering or
key-set construction. A marker-aliasing test proves no parsed JSON value
(including a string spelled like the marker's repr) compares equal to the
marker.

Loader test (PE-2b): an approval labeled `C2_MANIFEST_ONLY` or
`C2_MANIFEST_DELTA_REACQUIRED` is **refused** when the actual candidate/reference
relation contains a dependency key-presence change, because the recomputed floor
is not C2 and those labels are less conservative than the recomputed floor; a
PMD listing an `INTERNAL_DEPENDENCY` delta for a key absent on either side is
refused as not matching the recomputed delta list.

---

## 15. Findings, residuals and blockers

### 15.1 Findings

- **F-1 (supersession).** The §3.2 clauses must be superseded by PE-1. R-J1
  resolved; permitted.
- **F-2 (post-launch window).** Lazy loading means bytes are read after
  `Popen`; L21A **detects** a persisting change and makes attribution
  indeterminate; it prevents nothing and cannot see a change reverted before
  L21A (ABA).
- **F-3 (shared global installation).** AIDO cannot stop other projects
  modifying global Pi; this design converts that into qualification or
  indeterminate attribution. An AIDO-dedicated installation location is not
  designed here.
- **F-4 (Node not in the profile).** `node.exe` is identity-pinned per proof,
  never byte-pinned (R-EXT-3).
- **F-5 (human anchor).** Code cannot prove independent review; the anchor is
  the reviewed live authorization binding `H`, whose review includes the APS
  diff.
- **F-6 (external resolution — corrected, B7).** Non-seam files **inside** the
  package root are pinned by the payload fingerprint (PROFILE-COVERED FACT).
  Everything in §5.5 is an EXTERNAL RUNTIME RESIDUAL outside profile authority:
  undeclared upward resolution, constructed-path loads, Node, CJS global
  folders, spawned processes; configuration/extension discovery is governed by
  CFG1 isolation and H1, not by the profile. None of these may be represented as
  profile-covered or identified.
- **F-7 (seam sufficiency — corrected).** Seam sufficiency no longer affects
  identity (any payload change is a new profile). It affects only whether E1
  may be reused: if derivation-relevant logic moved to a non-seam file, E3 must
  catch it and the derivation be redone, or the case escalates to C5.
- **F-8 (SHA-256 reliance).** Accepted.
- **F-9 (stage mixing).** Enforced by §7.3 and by the L21A halt.
- **F-10 (v3 required).** Any profile-aware live run requires v3.
- **F-11 (A4 inertness).** At `90fda0b`, A4's A1 would still pass; the
  withdrawal is the authority; any later commit moves `HEAD`.
- **F-12 (cost and sliver).** The full payload is hashed at gate, L1, L14 and
  L21A per ordinal. The L14 check→use sliver now spans the payload walk.
  Accepted, stated.
- **F-13 (strict manifests).** A future Pi whose manifests fail strict parsing
  (e.g. duplicate keys) cannot be approved under HPP-1 — deliberate fail-closed;
  a policy revision would be needed.
- **F-14 (genesis not eligible).** Under HPP-1 no profile is eligible until the
  first candidate is qualified; there is no live path back to 0.85.1 without
  discovering and qualifying a 0.85.1 payload like any other candidate.
- **F-15 (conservative package-name grammar).** The §5.3.1 grammar is a strict
  subset of npm's (lowercase ASCII, no leading `_`/`-`/`.`). A real Pi
  dependency outside it — for example a legacy uppercase name — makes the
  candidate C5 until an explicit HPP policy amendment admits it. This is
  deliberate; it is not widened automatically. PE-3 discovery surfaces it early.
- **F-16 (PMD truth is review).** PMD's completeness and consistency are
  mechanical; the truth of each finding is independent review over bound bytes.
  A wrong "NOT_READ" finding is a review error that the mechanism cannot catch;
  the runtime backstops (L15/L16) still run on every live ordinal.
- **F-17 (evidence-reference verifier is new composition).** No shipped
  function verifies repo-relative evidence references today; PE-2b composes one
  from `workspace.canonical.canonicalize_existing_path_under_workspace` (not yet
  called by anything shipped). Evidence references never affect runtime
  eligibility.
- **F-18 (L21A placement, R3).** L21A runs after L24, so the interval between
  the child's exit and the payload re-observation now includes L22–L24. This
  slightly widens the already-documented A→B→A residual (F-2) and changes no
  result meaning; it is the accepted cost of giving broker shutdown and
  sensitive-material scrub priority.

### 15.2 Open blockers

No design blocker from the independent reviews remains open in R3 (see Status).
Before any new live CFG1 run, all of the following remain required:

1. Independent review and acceptance of R3 (PE-0, currently **candidate for
   acceptance / pending independent review**).
2. PE-1 amendment (supersession, v3 including the B7 literals, codes, L21A,
   classification, halt reason, G6A, `PI-PC1` bounds, the §5.3.1 schema and
   grammar, the policy-directory layout, the PMD schema).
3. PE-2a/2b/2c implementations and reviews.
4. PE-3 discovery and PE-4 qualification of the installed Pi (class unknown;
   at least C3, since genesis has no profile).
5. PE-5 approval; PE-6 fresh live authorization.

AR2 live remains NO-GO (OC-6); Stage 2, Q1/Q2 live and real-workspace authority
remain NO-GO unless separately authorized.

---

## 16. Migration phases after this design

| Phase | Kind | Content | Executes Pi/Node? |
|---|---|---|---|
| **PE-0** | review | Accept/freeze R3 (HPP-1 normative) | No |
| **PE-1** | design amendment | Supersede CFG1 §14.1 item 2 / §14.2, FU1 R6 §2 / §17 item 6, AMEND1 §7.4 / §19 item 5; freeze `PI-PC1` (walk rules, bounds, permitted value slots with immutable key presence, the structure-preserving C2 projection, order-sensitive C2 comparison, containment/exposure rule, **§5.3.1 dependency-map schema and package-name grammar**); the loader-owned policy-directory layout; the PMD schema; v3 record/refusal/stage-closure schemas including the two B7 literals; the six P codes; L21A vocabulary and its execution position in the closure order `L21 → L22 → L23 → L24 → L21A → L25 → L26 → L27`; `INDETERMINATE_PI_PROFILE`; halt `PI_PROFILE_ATTRIBUTION_UNPROVEN`; G6A; new pre-live barrier sequence without any "restore Pi" item | No |
| **PE-2a** | offline implementation | Payload walk leaf (no-follow, bounded, reparse refusal), inventory canonicalization, fingerprints, manifest-bundle binding and strict parsing, **dependency-map schema and package-name parser**, containment/exposure computation, floor classifier, **PMD delta-list computation**, and the static **discovery tool**; counterexample tests 1–7, 12–14, the §14.4 B5 tables and the §14.5 B9 classifier/projection tests | No |
| **PE-2b** | offline implementation | APS/profile/seam-evidence/approval/retirement schemas; strict loader (fingerprint-derived paths only; recompute everything derivable; class-floor, premise and **PMD** verification); the offline **evidence-reference verifier** (§4.14); sealed snapshot; **genesis revision 1** (seam evidence only); tests 13–16, §14.4 scenarios 4–7, the §14.5 B9 loader test, S-8/S-24/S-30/S-37 | No |
| **PE-2c** | offline implementation | P2/P2M/P2X in P (P2X paths only from parsed components); L1 stage consistency; L14 re-proof; gate vocabulary; L21A at its frozen position after L24; classification; stage halt; v3 records (with the B7 literals) + binding verifier; test migration; tests 8–11, §14.4 scenario 8, the §14.5 B8 closure-order test, and every v3 invariant | No (T-3 separately) |
| **PE-2R** | review | Independent review of each of 2a/2b/2c (2a may be reviewed before 2b/2c proceed) | No |
| **PE-3** | operator run | After PE-2a (and 2b for the floor class) is accepted: operator runs discovery read-only; candidate committed. May proceed in parallel with PE-2c. | No |
| **PE-4** | qualification | Evidence per the candidate's class; E4/E5 only under explicit authorization; C4/C5 → design/code chain | Only if separately authorized |
| **PE-5** | approval | APS revision 2 after independent acceptance | No |
| **PE-6** | live authorization | Fresh `stage_execution_id`; binds commit + `APS_HEAD_SHA256`; no literal version; A4 listed withdrawn | Only after its own acceptance |

Deferred, only if separately authorized: Node provenance; installation-location
isolation; a narrower premise map for E4/E5/E6; profile-binding the Q1/Q2 drift
guard.

---

## 17. Explicitly not authorized by this document

1. Any implementation, test change, or modification of production code, tests,
   frozen designs, the A4 authorization, historical evidence, the roadmap, or
   `CLAUDE.md`.
2. Executing, consuming or producing the A4 launcher; reusing `CFG1-S1-A4`.
3. Restoring, installing, uninstalling or downgrading Pi or Node.
4. Running Pi or Node, `pi --version`, `npm`, or any Pi JavaScript.
5. Contacting B300 or any backend; reading any credential or endpoint value.
6. Creating a live authorization, profile, inventory, manifest bundle, seam
   evidence, approval, retirement or APS revision.
7. A generic harness abstraction, `AgentRuntime`, harness plugins or registry,
   Codex or DeepSeek Harness integration, cross-harness routing, or capability
   negotiation.
8. Any semver range, compatibility matrix, or auto-revalidation rule.
9. Automatic transfer of any PASS, verdict, ranking, qualification result or
   approval to a new profile; automatic evidence reuse.
10. Branch, commit, push or PR by any agent.

---

## 18. Product-rule statements (made true by this design)

> **Another project upgrading the globally installed Pi may cause the next AIDO
> run to require profile qualification, but it must never require AIDO to
> downgrade Pi merely to satisfy a permanently pinned product version.**

True because no code path compares a version; an unapproved payload fails
closed **before consumption** with an onboarding remedy (§6.2, §9.8); the
onboarding path exists for any observable payload (§12); and no HPP-1 document
may state reinstallation of an older release as the remedy.

> **Once that new Pi profile is accepted, AIDO adopts it without rewriting
> historical qualification records and without editing production code merely
> to replace an old version literal.**

True because adoption is one appended APS revision with its bound inventory and
manifests (data) plus a fresh authorization binding its head (§9); earlier
revisions and v1/v2/v3 records are immutable (§4.10, §9.6, §10); and production
Python changes only when Pi's **behavior** (C4) or **layout/payload scope** (C5)
changes (§7.7).

And, after B1: **a Pi upgrade or mutation that changes any file under the Pi
package root can never silently inherit an earlier profile's approval,**
whether or not the 20 seam files changed (§5.4).

---

## Status

```text
5F3B-PI-HARNESS-PROFILE-EVOLUTION-DESIGN   CANDIDATE R3 / PENDING INDEPENDENT REVIEW
R-J1                                       RESOLVED
B1                                         CLOSED
B2                                         CLOSED
B3                                         CLOSED
B4                                         CLOSED
B5                                         CLOSED
B6                                         CLOSED
B7                                         CLOSED
B8                                         CLOSED BY R3 DESIGN
B9                                         CLOSED BY R3 DESIGN
PE-0                                       CANDIDATE FOR ACCEPTANCE / PENDING INDEPENDENT REVIEW
HARNESS PROFILE POLICY                     HPP-1 defined, not yet normative
PROFILE AUTHORITY                          BOUNDED: package payload + declared-resolution boundary only
OC-2 (FU1 R6 / AMEND1 §14)                 package-payload portion covered by design once implemented; NOT closed beyond it (Node + §5.5 external runtime residuals remain)
CFG1-S1-A4                                 WITHDRAWN BEFORE CONSUMPTION / HISTORICAL ONLY / MUST NOT EXECUTE
NEXT CFG1 LIVE AUTHORIZATION               NOT AUTHORIZED; requires PE-0 … PE-6; fresh id
CFG1-LIVE-S2                               NO-GO
Q1 / Q2 QUALIFICATION AUTHORITY            NO-GO
REAL-WORKSPACE AUTHORITY                   NO-GO
AR2 LIVE                                   NO-GO (OC-6)
GENERIC HARNESS ABSTRACTION                DEFERRED (unchanged)
```
