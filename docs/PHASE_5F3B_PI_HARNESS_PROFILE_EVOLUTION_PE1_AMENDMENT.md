# Phase 5F3B-PI-HARNESS-PROFILE-EVOLUTION PE-1 — Normative CFG1 / HPP-1 Design Amendment

```text
5F3B-PI-HARNESS-PROFILE-EVOLUTION-PE1        CANDIDATE R2 / PENDING INDEPENDENT REVIEW
KIND                                         DESIGN AMENDMENT (additive supersession)
REVISION                                     R2 — closes independent-review hold B14 only
                                             (R1 closed B10–B13; accepted as closed, not reopened)
AUTHORIZES                                   NOTHING — no implementation, no live run,
                                             no profile, no approval, no authorization
BASE (ACCEPTED / FROZEN, NOT EDITED)         docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_DESIGN.md
                                             PE-0 R3, HPP-1 NORMATIVE
  committed at                               2f1ef0a1188be054f1ac91e80d74439f87c0d3b1
  git blob                                   1d26ee4331bd7111f743afa58d9ebe36a0d4dec5
  SHA-256                                    778876d31c1c6b940aeb98cde9add824c89260e5f12711a8b9f67946a052fb56
  (re-verified by this turn: sha256sum, git hash-object, git cat-file | sha256sum)
PE-0 B1–B9                                   NOT REOPENED
CFG1-S1-A4                                   WITHDRAWN BEFORE CONSUMPTION / HISTORICAL ONLY /
                                             MUST NOT EXECUTE — no A4 launcher may be produced or run
NEXT LIVE EXECUTION ID                       NOT CHOSEN, NOT RESERVED (chosen only by a future PE-6)
```

> **THIS DOCUMENT IS A DESIGN AMENDMENT CANDIDATE. IT GRANTS NO
> IMPLEMENTATION AUTHORITY AND NO LIVE AUTHORITY.** It converts the accepted
> HPP-1 architecture (PE-0 R3) into an exact implementation contract for PE-2a,
> PE-2b and PE-2c, each of which still needs its own explicit authorization.
>
> **Disclosure of what the turns that authored this file did (exact).** The R2
> turn edited only this file (§26.4, revision history, header, adversarial
> table and status) with the Edit tool and one standard-library-only Python
> one-off that renamed the §26.4 audit labels, and ran the same read-only
> validation commands; it read no other file. The R1
> turn additionally read `stage_decision.py`, `writers.py` (the stage-closure
> writer), `stage_output.py` (execution-directory establishment) and
> `stage_runner.py` (the nested terminal sealer) and the CFG1 base design
> §16.3.6, edited only this file with the Edit tool, ran the same read-only
> validation commands, and otherwise did exactly what the R0 disclosure below
> states. The R0 turn read
> repository documents and source inside `C:\dev\ai_dev_orchestrator` only
> (the PE-0 design; the CFG1 base design §12, §14, §19, §22; FU1 R6 banner, §2,
> §17; OC-3 AMEND1 banner, §5–§8, §12, §19; the A4 authorization §7–§8, §10–§11;
> the OC-4 and P1-topology outlines; and the CFG1 modules `classification.py`,
> `halt.py`, `records.py`, `run_contract.py`, `run_executor.py`,
> `pi_identity.py`, `pi_fs_leaves.py`, `preflight.py`, `stage_runner.py`) with
> read-only `git`, `grep`, `sed`, `ls`, `cat`, `head`, `tail`, `od`, `wc`, `tr`,
> `sha256sum` and the Read tool, and read the local `core.autocrlf` value and
> the absence of a `.gitattributes` file. It ran standard-library-only Python
> one-offs solely to apply cross-reference text replacements to this file and
> to check this file's section references. It did **not** import any AIDO, CFG1, AR2 or
> qualification module; did **not** inspect, walk, hash or qualify the installed
> Pi; did **not** run Pi, Node, npm or `pi --version`; did **not** contact B300
> or any backend or model; did **not** read any credential or endpoint value;
> created exactly this one file and modified nothing else; and committed
> nothing.

---

## Revision history

| Rev | Change |
|---|---|
| R0 | Initial PE-1 candidate. Independent review accepted the core design in principle and held PE-1 for B10–B13. |
| **R1** | **B10:** the generic pre-consumption admission checks the **bound fresh** execution namespace `RESULTS_ROOT\<BOUND_STAGE_EXECUTION_ID>`, not the burned A4 path; a new launcher step G9 uses the launcher's one bound literal for both the absence check and establishment (§23.1, §23.1a, §22.4, §26.4). **B11:** `stage_pi_profile_id`, `ordinal_pi_profile_binding` and `pi_profile_attribution_halt` are bound into `_DecisionMintRecord` **and** `CFG1StageClosureDecision` and into `_bound_fields()`; the writer keeps its `(authority, *, decision)` surface and derives every policy field itself (§20.2, §20.3); the stage declared version uses design **B** (writer-derived from the sealed profile id and the sealed snapshot). **B12:** discovery writes only into one fixed, AIDO-owned, non-authority staging namespace with exclusive create (§9.10). **B13:** PE-2a acceptance no longer requires the PE-2b loader; the loader-integration obligations move to PE-2b; a general phase-ownership rule is frozen (§26.0). Nothing else is redesigned; PE-0 is not reopened. |
| **R2** | **B14 only:** R1 §26.4's "no second string literal of the id grammar anywhere in the launcher" was over-broad and mechanically impossible (e.g. `stage_id="S1"` satisfies `[A-Za-z0-9_-]{1,64}`). It is replaced by **value uniqueness and use-site binding**: exactly one `Constant[str]` equal to the exact authorization-bound id, as the right-hand side of the one assignment to `BOUND_STAGE_EXECUTION_ID`; both the G9 precheck and the establishment call consume `Name("BOUND_STAGE_EXECUTION_ID")`; no reassignment or mutation. Unrelated grammar-valid literals are irrelevant. B10–B13 are accepted as closed and not reopened; no other semantics change. |

---

## 0. Reading rule, authority and precedence

1. **Effective design for a profile-aware CFG1 run** = the frozen CFG1 chain
   (base design, L16-FU2 R2 + ERR1, FU1 R6, OC-3 AMEND1, Y6 AMEND2, OC-4, P1
   topology amendment) **+ PE-0 R3 (HPP-1) + this amendment**. Where this
   amendment names a clause as superseded (§2.1) or extended (§2.3), this
   amendment governs **for profile-aware runs only**; every other frozen clause
   is preserved exactly.
2. **Historical documents are immutable.** This amendment edits no file. The
   CFG1 base design, L16-FU2 / ERR1, FU1 R6, OC-3 AMEND1, Y6 AMEND2, OC-4, the
   P1 topology amendment, the LIVE-S1/A2/A3/A4 authorizations and every
   historical v1/v2 evidence file keep their bytes and their historical
   meaning. A superseded clause remains a true statement of what was required
   at the time it was written; it only ceases to be forward-looking authority.
3. **PE-0 is not reopened.** Where this amendment is more exact than PE-0, it
   refines PE-0's accepted semantics and says so; it never contradicts a PE-0
   B1–B9 disposition. Three places where PE-0 left a literal to PE-1 and a
   naïve reading would be inconsistent with a frozen CFG1 fact are resolved
   explicitly: the "six P codes" terminology (§12.1), the `Allowed(F)` row for
   an unexpected L1 failure before P's commit (§19.3), and the halt vocabulary's
   closure under §19.4/§19.5 of the base design (§17.4).
4. **Normative words.** "Must", "exactly", "only", "never" are normative.
   Constants in `CODE FONT` are frozen literals. "Refuse" means fail closed with
   no partial result; nothing is truncated, sampled, repaired, defaulted or
   coerced anywhere in this contract.
5. **Scope.** Everything here is Pi-specific and CFG1-specific. No generic
   Harness abstraction, `AgentRuntime`, harness registry, plugin, routing or
   capability negotiation is introduced (PE-0 §0.2).

---

## 1. Governing rule

```text
HARNESS VERSION      = provenance only
PI PROFILE           = bounded, mechanically observed package-payload identity
                       + declared-dependency resolution boundary
APPROVAL             = explicit, independently reviewed authority
LIVE AUTHORIZATION   = binds one exact APS head and one exact source commit
```

- AIDO must not permanently bind execution or qualification to one Pi/Harness
  version, **and** a new Harness payload must not silently inherit an older
  payload's authority.
- **No production decision may compare a version string** to decide admission,
  matching, eligibility, launch, evidence reuse or qualification authority.
  Exactly two production comparisons of version text exist, and neither decides
  authority (§9.4, §10.2): (a) the loader's **integrity** check that a profile's
  `declared` field equals the projection it recomputes from the same committed,
  hash-bound bytes; (b) the classifier's **delta enumeration** for PMD, which
  lists a changed `version` value as a fact after the C2 relation has already
  been decided with that value masked. PE-2 audits enforce that no third
  comparison exists (§26.3 C-16).
- **Version provenance is never removed.** Every profile carries its declared
  versions; every v3 run record carries the matched profile's declared package
  version; historical records keep what they recorded.

---

## 2. Supersession matrix

### 2.1 Superseded forward-looking clauses (exact)

Each row is superseded **for future profile-aware CFG1 runs only**. The
historical text is not edited and keeps its historical meaning (§2.2).

| # | Clause | Old forward-looking meaning | New meaning (governs from acceptance of PE-1) |
|---|---|---|---|
| S-1 | **CFG1 base design §14.1 item 2**, bullet "Pi 0.85.1 with the §14.2 digests" | a LIVE-S1 authorization must authorize Pi 0.85.1 with the §14.2 digests | a live authorization must authorize **a Pi profile that is live-eligible under the exact HPP-1 APS head bound by that independently reviewed live authorization** (eligibility per §9.6; binding per §24). Every other §14.1 item-2 bullet (one declared `stage_execution_id`, model/route, credential-boundary ordering, route checks, schedule, §16/§19 rules, output root, no qualification artifact) is **preserved** and applies unchanged. |
| S-2 | **CFG1 base design §14.2** (the 20-entry "installed Pi 0.85.1" seam table, and its sentence "A mismatch refuses before any credential read. It means the derivation must be re-reviewed, not that Pi is incompatible.") | the singleton table is the current runtime identity authority of P | the table ceases to be runtime identity authority. It becomes the **historical / genesis `PI-SC1` seam evidence** (§5.3, §9.8), byte-for-byte, and is never matched by P. The preserved principle is restated for profiles: an unapproved payload refuses before any credential read, and means the payload must be onboarded and reviewed, not that Pi is incompatible. |
| S-3 | **FU1 R6 §2**, first bullet, the phrase "and `PINNED_PI_VERSION = "0.85.1"`. No entry is added, removed, re-derived, or repinned." | Pi remains pinned to 0.85.1 going forward; the seam set is the frozen identity | superseded for profile-aware runs: identity is the `PI-PC1` payload profile (§4); the 20-entry set is the `PI-SC1` derivation selector only (§5). The rest of R6 §2 is **preserved** except where §2.3 extends it for v3 only. |
| S-4 | **FU1 R6 §17 item 6** "Operator restores the approved Pi 0.85.1 environment." | remedy/barrier: restore Pi 0.85.1 | **route the currently installed Pi payload to HPP-1 profile onboarding** (§25). No downgrade, reinstall or restore is required by AIDO. The §17 sequence as a whole is the historical pre-A4 sequence; the forward-looking profile-aware sequence is §23.4. |
| S-5 | **OC-3 AMEND1 banner**, bullet "Pi remains pinned to **0.85.1** through the unchanged 20-entry `PINNED_PI_SEAM_DIGESTS`. Nothing here adds, removes, or repins a seam." | a forward-looking pin | superseded as forward-looking wording; identity is the profile (§4). |
| S-6 | **OC-3 AMEND1 §7.4** (`PINNED_PI_VERSION` as a retained design literal naming the pinned release) | the pinned release literal remains a design literal of the current identity | `PINNED_PI_VERSION` is **provenance only**, naming the release from which the genesis seam evidence was taken (PE-0 §11.1: DEAD for runtime). Its §7.4 prohibitions are **preserved and strengthened**: it must never be serialized into any record, compared with anything, or rendered as an observation. |
| S-7 | **OC-3 AMEND1 §19 item 5** "Operator restores the approved Pi 0.85.1 environment (item 6), outside AIDO." | remedy/barrier: restore Pi 0.85.1 | same replacement as S-4. AMEND1 §19 as a whole is the historical pre-A4 blocker list. |

### 2.2 What is NOT superseded (OC-3's security result and historical meanings)

Preserved exactly, for every run, profile-aware or not:

- **P executes nothing.** No `pi --version`, no executable version probe, no
  Node/Pi/JavaScript execution before L14 `launch()` (AMEND1 AMD-1, AMD-6).
- **Runtime- or model-reported versions are never authority** (AMEND1 §7.1;
  PE-0 S-6).
- AMEND1 §7.2/§7.3: v2 has no `pi_observed_version`, no
  `pi_version_probe_attempted`, and no replacement version field — the
  **v2 decision stands** for v2 (PE-0 §10.2); v3 adds a *declared, loader-bound*
  version for different reasons (§19).
- FU1 R6's banner sentence "Pi remains pinned to 0.85.1. Nothing here repins it
  to 0.87.0." is a true statement of what R6 did; it is **not** edited and is
  not forward-looking authority after PE-1.
- LIVE-S1, A2, A3, A4 need no amendment: none authorizes anything again
  (PE-0 §3.2). A4's §10 remedy text ("the operator may restore the approved Pi
  environment") is historical and must not be carried forward (§25).
- v1 `pi_observed_version` keeps meaning "AR2's `--version` probe reported
  this"; v2 `pi_seam_digests_match == true` keeps meaning "the complete
  singleton 20-entry 0.85.1 seam table matched" and **nothing** about the rest
  of the package (PE-0 §10.1). Neither is ever re-validated against an APS.

### 2.3 HPP-1-mandated additive extensions (not supersessions)

The accepted HPP-1 architecture requires four extensions of frozen CFG1
mechanics. None is a singleton-Pi clause, none weakens a security invariant,
and each is scoped so that every v1/v2 artifact, validator and vocabulary keeps
its frozen meaning:

| # | Frozen clause | Extension | Why it is not a weakening |
|---|---|---|---|
| X-1 | AMEND1 §5.1 P leaf set (inspection primitive, one-handle digest reader, ambient mapping) and FU1 R6 §5 P2 (20 seams) | P2 becomes the complete `PI-PC1` walk (§4.3). The leaf set gains **exactly one** leaf, a no-follow directory enumerator (§11.2); the digest reader returns the byte count it read. | PE-0 §3.1 already accepted P2 as a strict superset. The new leaf is a read-only, no-follow filesystem observation built on the **same four** `kernel32` calls `pi_fs_leaves` already uses (§11.2); no leaf can create a process. |
| X-2 | CFG1 §12.1 rows and order (preserved by R6 §2) | For v3 only, one row `INDETERMINATE_PI_PROFILE` is inserted after row 2 (§16). The v2 classifier and its 12-value domain are unchanged. | It can only move a run from a determinate to an indeterminate classification. |
| X-3 | CFG1 §19.1 items 1–4, §19.4's six `HALT_REASON_CODES`, §19.5 precedence (preserved by R6 §2; §19.5 requires a separately authorized amendment to add a seventh code) | For v3 stage closures only: admission item **1A**, halt code `PI_PROFILE_ATTRIBUTION_UNPROVEN`, and a seven-step v3 precedence (§17). The six-code set and the six-step function stay byte-identical objects for v1 stage closures. | It can only remove an admission; it never admits a run the base rules would halt. This amendment **is** the separately authorized design amendment §19.5 requires. |
| X-4 | CFG1 §22 record schemas; R6 §10 / AMEND1 §15 v2 | New record versions `pi-harness-cfg1-run.v3`, `pi-harness-cfg1-refusal.v3`, `pi-harness-cfg1-stage-closure.v3` (§19, §20). | Additive versions, dispatched only by exact `(record_version, record_kind)` pairs; no v1/v2 artifact can be routed through v3 semantics or the reverse. |

**Answer to the prompt's first question:** PE-1 can cleanly supersede S-1…S-7
without contradicting a frozen security invariant. Every security invariant
PE-0 §3.1 lists is preserved (P executes nothing; P2 complete; P1 first
admissible candidate; gate is waste avoidance; L1 from scratch; L14
launch-nearest; static pass is provenance; authorization supplies only
`stage_execution_id`; v1/v2 immutable; refusal before any credential read;
closure always runs), and X-1…X-4 are HPP-1-mandated, monotone-toward-refusal
extensions.

---

## 3. Frozen contract identities and literals

```text
PROFILE POLICY            HPP-1
PAYLOAD CONTRACT          PI-PC1
SEAM CONTRACT             PI-SC1
CONSUMER CONTRACT         CFG1-CC1
PROFILE RECORD            aido-pi-profile.v1
PAYLOAD INVENTORY         aido-pi-payload-inventory.v1
MANIFEST BUNDLE           aido-pi-manifest-bundle.v1
SEAM EVIDENCE             aido-pi-seam-evidence.v1
PROFILE APPROVAL          aido-pi-profile-approval.v1
PROFILE RETIREMENT        aido-pi-profile-retirement.v1
APPROVED PROFILE SET      aido-pi-approved-profile-set.v1
CFG1 RECORD               v3 for profile-aware runs:
                            pi-harness-cfg1-run.v3
                            pi-harness-cfg1-refusal.v3
                            pi-harness-cfg1-stage-closure.v3
```

Further frozen literals:

```text
DOMAIN TAG  payload fingerprint   b"aido.pi-payload.v1\x00"
DOMAIN TAG  profile id            b"aido.pi-profile.v1\x00"
DOMAIN TAG  seam fingerprint      b"aido.pi-seam.v1\x00"
B7          pi_profile_authority_scope     "PI_PACKAGE_PAYLOAD_AND_DECLARED_RESOLUTION_BOUNDARY"
B7          pi_external_runtime_residual   "NOT_IDENTIFIED_BY_PROFILE"
POLICY DIR  <CFG1 package dir>\pi_profile_policy
            (= <ROOT>\experiments\pi_harness_cfg1\pi_profile_policy)
STAGING     <CFG1 package dir>\pi_profile_candidates           (R1, B12; NON-AUTHORITY)
            (= <ROOT>\experiments\pi_harness_cfg1\pi_profile_candidates)
PACKAGE     root manifest name            "@earendil-works/pi-coding-agent"
IDENTITY    pi-ai manifest name           "@earendil-works/pi-ai"
            pi-agent-core manifest name   "@earendil-works/pi-agent-core"
```

Record-version rule: `pi-harness-cfg1-stage-closure.v2` **never existed and is
never issued**. The stage-closure family skips from v1 to v3 so that one suffix,
`v3`, denotes "HPP-1 profile-aware" uniformly across run, refusal and
stage-closure records; any validator refuses a `.v2` stage-closure literal.

Every literal is compared with `type(x) is str and x == LITERAL`. No prefix
match, case folding, truthiness, default or fallback.

---

## 4. `PI-PC1` — the payload contract

### 4.1 Payload root and launch target

- The **payload root** is exactly the Pi package root selected by the frozen P1
  first-admissible-candidate semantics (FU1 R6 §5 P1 as amended by the P1
  topology amendment): `…\node_modules\@earendil-works\pi-coding-agent`,
  anchored by `pi.cmd`, in the two AR2 layouts. P1 is unchanged. P never
  searches onward for a matching installation.
- `dist/cli.js` is the launch target and **must be a regular payload file**
  (inventory kind `file`) in every approvable profile (§4.6).
- The payload root directory itself is not an inventory entry; every entry
  below it is.

### 4.2 Relative-path grammar (payload entries)

A payload relative path is a Python `str` of `/`-joined segments:

```text
path          1 ≤ number of segments ≤ MAX_PATH_SEGMENTS (128)
              1 ≤ len(path) ≤ MAX_RELATIVE_PATH_CHARS (1024)   (code points)
segment       1 ≤ len(segment) ≤ MAX_SEGMENT_CHARS (255)
              not "." and not ".."
              contains none of: U+0000–U+001F, U+007F–U+009F,
                                '\' '/' ':' '*' '?' '"' '<' '>' '|'
              contains no code point in U+D800–U+DFFF (no lone surrogate)
              does not end with '.' or ' '
              its stem before the first '.' is not, case-insensitively, one of
                con prn aux nul com0…com9 lpt0…lpt9
path          no leading '/', no trailing '/', no empty segment, no drive
```

A name enumerated from disk that fails the grammar makes the payload
**unobservable** (never skipped, never normalized). Non-ASCII names that pass
the grammar are permitted; they are serialized by the canonical encoding's
ASCII escaping (§7.1).

**Case-fold uniqueness:** no two inventory paths may be equal under
`str.casefold()`. A collision (possible on a case-sensitive NTFS directory)
makes the payload unobservable.

### 4.3 The walk (complete, no-follow, bounded, deterministic)

1. **Directory step.** Open the directory no-follow
   (`FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS`, read/list
   access, full sharing — AIDO never locks the Pi tree). The handle must
   classify as `directory` and must not carry `FILE_ATTRIBUTE_REPARSE_POINT`.
   Enumerate **through that same handle** (§11.2). `.` and `..` are skipped;
   every other entry is recorded.
2. **Entry classification.** For each enumerated entry: any
   `FILE_ATTRIBUTE_REPARSE_POINT` (symlink, junction, mount point, any reparse
   tag) → refuse; directory attribute → a `dir` entry, recursed into (depth
   first) by step 1; otherwise → a candidate `file`, opened no-follow by the
   one-handle reader, whose handle must classify `regular_file` (`GetFileType`
   disk, not directory, not reparse); anything else (`other`, a device, a
   pipe) → refuse.
3. **File content.** Size and SHA-256 come from **one opened handle**: read to
   EOF, hashing every byte and counting it; `size` = bytes read. The handle's
   reported size before the first read and after EOF must both equal the byte
   count, else refuse (the file changed during the read). Reading stops and
   refuses as soon as the count would exceed `MAX_PAYLOAD_FILE_BYTES`.
4. **Refusal conditions** (payload unobservable): any reparse point anywhere;
   any non-file/non-directory entry; any open, enumeration or read failure,
   including access denied and sharing violation ("unreadable-entry refusal");
   a grammar failure; a case-fold collision; any bound in §4.4 exceeded. A
   refusal returns **no** inventory, fingerprint or partial list.
5. **Inclusion.** Every directory (including empty ones and every nested
   `node_modules` tree) and every regular file of **every type and extension**
   (`.js`, `.mjs`, `.cjs`, `.json`, `.node`, `.wasm`, maps, data, docs,
   licences, anything). No extension, name, directory, dot-file or size class
   is ignored. No sampling, no truncation, no cache.
6. **Order independence.** The walk collects all entries, then sorts them
   (§4.5); the result is independent of enumeration order.
7. **What is not identity.** Timestamps, attributes, ACLs, owners, 8.3 short
   names and alternate data streams are not recorded. A metadata-only change
   does not change the profile; a change that makes an entry unreadable makes
   the payload unobservable. Hard links are hashed as content; a mutation made
   through any other link is a content change and is detected by the next walk.
8. **Mixed-instant observation is harmless for the content claim.** A walk
   observes each entry at its own instant. A fingerprint equal to an approved
   one means every byte AIDO read under the lexical payload root equalled the
   approved bytes, whichever objects supplied them (the AMEND1 §5.2 argument,
   extended from 20 files to the payload). P2R and L14's `I_r` re-proof bind the
   root object; a swap-and-restore wholly inside one walk is the accepted ABA
   residual (§27).
9. **Writes and OS metadata.** The walk issues no write, create, rename or
   delete. The OS may update access metadata while servicing reads, and may
   perform redirector I/O for operator-controlled paths; no claim is made
   otherwise (AMEND1 §12.3 wording, preserved).

### 4.4 Frozen resource refusal bounds

These are **resource-safety refusal limits**, not product token limits. They
were chosen from general properties of Node package trees and Windows
filesystems, **not** from any inspection of the installed Pi (none was
performed). Exceeding any bound **refuses**; nothing is ever truncated.

| Constant | Value | Applies to | Rationale |
|---|---|---|---|
| `MAX_PAYLOAD_ENTRIES` | `250000` (dirs + files) | walk | Large bundled Node CLIs with nested dependency trees are typically 10³–10⁵ entries; 250 000 leaves ≥ 2.5× headroom over a very large tree while bounding memory for the sorted inventory. |
| `MAX_PAYLOAD_FILE_BYTES` | `536870912` (512 MiB) | each payload file | Native addons and WASM blobs are the largest legitimate payload files (tens to low hundreds of MiB); 512 MiB admits them with headroom and bounds one read. Replaces the historical R6 `MAX_SEAM_FILE_BYTES = 16 MiB` for profile-aware P. |
| `MAX_PAYLOAD_TOTAL_BYTES` | `4294967296` (4 GiB) | sum of hashed file bytes | ≥ 8× a large installed agent package; bounds each walk's hashing work. Worst case per stage (gate + 3 walks × 9 ordinals = 28 walks) stays bounded; cost is F-12's accepted residual. |
| `MAX_RELATIVE_PATH_CHARS` | `1024` | each payload path | Well above practical nested `node_modules` paths; far below any pathological path an attacker could construct to inflate records. |
| `MAX_PATH_SEGMENTS` | `128` | each payload path | Bounds recursion depth; modern hoisted trees rarely exceed ~20. |
| `MAX_SEGMENT_CHARS` | `255` | each segment | The NTFS component limit. |
| `MAX_MANIFEST_BYTES` | `1048576` (1 MiB) | each `package.json` (bundle, loader, discovery) | Real manifests are KiB-scale; 1 MiB is > 100× typical. P hashes manifests as ordinary files (512 MiB bound) but a profile with a larger manifest cannot be approved. |
| `MAX_MANIFEST_COUNT` | `20000` | `package.json` files per payload | ≥ one per package plus nested `type` markers in a very large tree. |
| `MAX_MANIFEST_TOTAL_BYTES` | `67108864` (64 MiB) | sum of all manifest bytes | Bounds the bundle independently of the count. |
| `MAX_MANIFEST_JSON_DEPTH` | `64` | manifest parser | Real manifests nest < 10 levels; a parser `RecursionError` also refuses. |
| `MAX_MANIFEST_NUMBER_TOKEN_CHARS` | `256` | each JSON number token in a manifest | Prevents big-integer / long-float parsing work. |
| `MAX_DEPENDENCY_MAP_KEYS` | `4096` | each dependency map (frozen by PE-0 §5.3.1) | as PE-0 |
| dependency key / value | key 1…214, value 0…1024 chars | each map entry | as PE-0 (214 = npm's name limit) |
| declared name / version | name 1…214, version 1…128, each char in 0x21–0x7E | declared projection | bounded printable-ASCII provenance text |
| `MAX_APS_REVISION_FILE_BYTES` | `16777216` (16 MiB) | each `aps.rNNNN.json` | APS records are small; 16 MiB admits hundreds of profiles with large PMDs. |
| `MAX_INVENTORY_FILE_BYTES` | `100663296` (96 MiB) | each inventory file | Keeps every committed policy file below common Git-hosting per-file limits (100 MiB); an inventory above it cannot be committed as one reviewed file and is refused (C5 in discovery). |
| `MAX_MANIFEST_BUNDLE_FILE_BYTES` | `100663296` (96 MiB) | each bundle file | Same reason; base64 of 64 MiB fits. |
| `MAX_APS_REVISIONS` | `9999` | chain | the 4-digit filename grammar |
| `MAX_PROFILES` | `256` | profiles in the head revision | One per adopted release for many years; bounds import-time recomputation. |
| `MAX_POLICY_TOTAL_BYTES` | `1073741824` (1 GiB) | sum of all policy files the loader reads at import | Bounds import-time work independently of per-file bounds. |
| `MAX_POLICY_JSON_DEPTH` | `24` | policy parser | Policy schemas nest ≤ 10 levels. |
| policy integers | `0 … 9007199254740991` | every integer in policy data | exact `int`, never `bool`, never float |
| evidence refs | ≤ 256 per list; `repo_path` ≤ 512 chars | policy records | review-document references |
| finding refs | ≤ 64 per finding | PMD | |
| `acceptance_reference` | 1…1024 chars, each in 0x20–0x7E | approval | bounded text naming the external acceptance record |

There is **no wall-clock bound** on the walk: a slow filesystem delays a walk;
it cannot make a walk accept bytes it did not read. A future Pi exceeding a
bound is **C5 under HPP-1** and needs an explicit policy amendment; bounds are
never raised automatically.

### 4.5 Canonical inventory and payload fingerprint

```text
record_kind       "aido-pi-payload-inventory.v1"
payload_contract  "PI-PC1"
entries           list, strictly ascending by the UTF-8 encoding of "path"
                  (equivalently, code-point order), no duplicates; each exactly
                    {"kind": "dir",  "path": <rel>}
                    {"kind": "file", "path": <rel>, "sha256": <64 lc hex>, "size": <int>}
```

- **Tree closure:** every proper ancestor path of every entry is itself a `dir`
  entry; no entry is a descendant of a `file` entry.
- `payload_fingerprint = SHA-256( b"aido.pi-payload.v1\x00" || canonical_json_bytes(inventory) )`
  (§7.1), rendered as 64 lowercase hex.
- **Any byte change anywhere under the payload root** — content of any file,
  any added/removed/renamed file or directory, any added empty directory —
  changes the canonical inventory and therefore `payload_fingerprint`, absent a
  SHA-256 collision (PE-0 §5.4, F-8).

### 4.6 Approvability (a profile may enter an APS only if all hold)

1. The walk completed (§4.3) within every bound (§4.4).
2. `dist/cli.js` is a `file` entry.
3. All 20 `PI-SC1` paths (§5.1) are `file` entries.
4. Every package-root manifest (§6.4) parses strictly (§6.2) and satisfies the
   dependency-map schema and package-name grammar (§6.3).
5. The declared projection (§6.5) succeeds, including the three exact package
   names of §3.
6. The canonical inventory and bundle files fit §4.4.

Failure of any item is **C5 under HPP-1** (§8.2). At run time P matches the
payload fingerprint only; approvability is enforced by the loader for every
committed profile and by discovery for every candidate.

### 4.7 Profile identity

```text
profile_id = SHA-256( b"aido.pi-profile.v1\x00" || canonical_json_bytes({
                 "payload_contract":     "PI-PC1",
                 "payload_fingerprint":  <64 lc hex>,
                 "resolution_exposures": <canonical exposure list, §6.6> }) )
```

Version text is excluded from authority except insofar as its manifest bytes
already contribute to `payload_fingerprint`. The profile claim is bounded:

```text
PROFILE-COVERED FACT
    the resolved Pi package payload (every file and directory under the payload
    root) equalled approved profile X at the stated boundaries, and every
    declared-dependency exposure of X was absent from every ancestor
    node_modules at those boundaries

EXTERNAL RUNTIME RESIDUAL
    everything PE-0 §5.5 (R-EXT-1…R-EXT-6) and §27 leave outside that boundary:
    NOT identified by the profile, NOT observed by P, L14 or L21A
```

No record, console line, enum value or document may claim complete Node/Pi
runtime identity.

---

## 5. `PI-SC1` — the seam contract

### 5.1 The selector (exactly these 20 relative paths)

```text
package.json
dist/cli.js
dist/main.js
dist/core/sdk.js
dist/core/defaults.js
dist/core/model-config.js
dist/core/provider-composer.js
dist/core/model-runtime.js
dist/core/model-resolver.js
dist/core/system-prompt.js
dist/core/agent-session.js
dist/modes/rpc/rpc-mode.js
dist/modes/rpc/jsonl.js
node_modules/@earendil-works/pi-ai/package.json
node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js
node_modules/@earendil-works/pi-ai/dist/api/simple-options.js
node_modules/@earendil-works/pi-ai/dist/models.js
node_modules/@earendil-works/pi-agent-core/package.json
node_modules/@earendil-works/pi-agent-core/dist/agent.js
node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js
```

(Exactly the key set of today's `preflight.PINNED_PI_SEAM_DIGESTS`; cardinality
assertion `20`.)

### 5.2 Meaning

`PI-SC1` is a **derivation-evidence selector only**. It is **not** profile
identity and **not** live eligibility; P never computes or uses a seam
fingerprint at run time. It selects which payload digests AIDO's reviewed
derivations (E1) cite:

```text
seam_digests     = { p: inventory[p].sha256  for p in PI-SC1 }   (all 20 must be files)
seam_fingerprint = SHA-256( b"aido.pi-seam.v1\x00" || canonical_json_bytes({
                     "seam_contract": "PI-SC1", "seam_digests": seam_digests }) )
```

### 5.3 Genesis

APS revision 1 contains exactly one seam evidence record whose `seam_digests`
equal today's `PINNED_PI_SEAM_DIGESTS` byte-for-byte, and **no** live-eligible
profile (§9.8). The genesis eligible set is empty.

---

## 6. Manifests, the B5 grammar, and declared-dependency containment

### 6.1 Manifest bundle

```text
record_kind          "aido-pi-manifest-bundle.v1"
payload_fingerprint  <64 lc hex> — equals the bound inventory's fingerprint
manifests            { <rel path of EVERY inventory file whose last segment is
                        exactly "package.json">: <standard base64, RFC 4648 §4,
                        padded, no line breaks, of that file's exact bytes> }
```

- Key set equals exactly the set of inventory `file` entries whose last segment
  is `package.json` (case-sensitive; a case-fold variant such as
  `Package.json` is not a manifest and is only hashed).
- Each decoded value must re-encode to the identical base64 text, have length
  ≤ `MAX_MANIFEST_BYTES`, and hash to that entry's `sha256` with that entry's
  `size`. Count ≤ `MAX_MANIFEST_COUNT`; total ≤ `MAX_MANIFEST_TOTAL_BYTES`.
- **Only package-root manifests are parsed** (§6.4). Every other bundled
  manifest is bound by bytes and participates in identity only through its
  bytes; it is never parsed or interpreted. (A package's test fixture with a
  deliberately malformed `package.json` therefore does not make Pi C5.)

### 6.2 The strict manifest parser

Applied to package-root manifests from **bound bytes only** (committed bundle
bytes in the loader; just-read bytes in discovery). Never at run time by P,
L1, L14 or L21A.

```text
bytes      length ≤ MAX_MANIFEST_BYTES; must not start with EF BB BF (BOM)
decode     UTF-8, errors="strict"
parse      JSON (RFC 8259) with:
             object_pairs_hook   refuses any duplicate key at any depth and
                                 builds an exact dict preserving key order
             parse_constant      refuses NaN, Infinity, -Infinity
             parse_float         refuses a token > 256 chars or a non-finite
                                 result (e.g. 1e400)
             parse_int           refuses a token > 256 chars
             strict string rules (no raw control characters)
           nesting depth ≤ 64; a RecursionError refuses
top level  type(value) is dict
result     exact types: dict (ordered), list, str, int (never bool), float,
           bool, None
```

The result is **order-preserving**: C2 compares ordered key sequences (§8.3).
No refusal is repaired; no default is supplied.

### 6.3 Dependency-map schema and the one package-name parser (B5, frozen)

For each of `dependencies`, `optionalDependencies`, `peerDependencies` in each
package-root manifest:

| Element | Rule |
|---|---|
| field | **absent**, or `type(value) is dict`. `null`, list, str, number, bool, or any other type → refuse. No subclass, no truthiness repair, no coercion, no "empty means absent". |
| map size | `≤ 4096` keys |
| key | `type(key) is str`; `1 ≤ len(key) ≤ 214`; then `parse_package_name` |
| value | `type(value) is str`; `0 ≤ len(value) ≤ 1024`. Values are never interpreted, resolved, or used to form a path; they are only compared (C2) and enumerated (PMD). |

`parse_package_name(key) -> tuple[str] | tuple[str, str]` — exactly PE-0
§5.3.1, frozen:

```text
precondition   type(key) is str                      (a str subclass refuses)
whole string   1 ≤ len ≤ 214; every character in [a-z0-9._@/-]
form           unscoped: zero '/' and no '@'                         → (NAME,)
               scoped:   key[0] == '@', exactly one '/', no other '@'
                                                                     → ("@"+SCOPE, NAME)
               anything else                                         → refuse
component      SCOPE and NAME each: non-empty; fullmatch [a-z0-9][a-z0-9._-]*;
               does not end with '.'; is not "node_modules"; stem before the
               first '.' is not (case-insensitively) con prn aux nul com0-9 lpt0-9
result         canonical text NAME or "@"+SCOPE+"/"+NAME must equal the input
```

Only `NAME` and `@SCOPE/NAME` parse. The parser never calls `normpath`,
`realpath`, `abspath`, npm or Node; never strips, lowercases or
percent-decodes; never "fixes" a name. Its character set excludes `\` and `:`
and its components cannot be empty, `.`, `..`, start with `.` or end with `.`,
so no accepted name can express traversal, a drive, an absolute path, a UNC or
device path, a control character, or a component Windows would normalize.

**Path construction:** only `ntpath.join(<proven ancestor>, "node_modules",
*components)` on disk, or `"/".join((..., "node_modules", *components))` in
memory. A raw key is **never** joined, formatted, interpolated or concatenated
into any path. Only parser output reaches P2X, L14 or L21A path construction.

A legitimate name outside the grammar makes the candidate **C5 under HPP-1**
(discovery reason `PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR`, reported with the
manifest's relative path and never with the raw key text in any console line);
the grammar is never widened automatically.

### 6.4 Package roots

The payload root, and every inventory `dir` entry of the form
`…/node_modules/<N>` or `…/node_modules/<@S>/<N>` that has a `file` child
`package.json`. The directory names `<N>`, `<@S>` must pass the §6.3 component
grammar (as `NAME` / `@SCOPE`), else the payload is C5. A `node_modules/@S`
directory with no `package.json` of its own is not a package root.

### 6.5 Declared projection (provenance only)

From the three `PI-SC1` package-root manifests:

```text
package_name           root manifest "name"          must be exactly "@earendil-works/pi-coding-agent"
package_version        root manifest "version"
pi_ai_version          node_modules/@earendil-works/pi-ai/package.json "version"
                       (its "name" must be exactly "@earendil-works/pi-ai")
pi_agent_core_version  node_modules/@earendil-works/pi-agent-core/package.json "version"
                       (its "name" must be exactly "@earendil-works/pi-agent-core")
```

Each `version` must be `type(v) is str`, length 1…128, every character in
0x21–0x7E. The three name equalities are **package-identity** checks of
`PI-PC1` (a mismatch is C5), not version comparisons. The version values decide
nothing.

### 6.6 Containment and the exposure set (frozen R3 algorithm)

Computed by discovery and recomputed by the loader from **the committed
inventory, the committed hash-bound manifest bytes and validated components
only**. Never at run time from Pi bytes.

```text
for each package root K (§6.4), in inventory order:
  for each map in (dependencies, optionalDependencies, peerDependencies) of K:
    for each key (in map order):
      C = parse_package_name(key)                        # refuse → C5
      candidates = [ K + "/node_modules/" + "/".join(C) ]
                 + [ A + "/node_modules/" + "/".join(C)
                     for A in proper ancestors of K up to and including the
                         payload root (""), nearest first,
                     skipping every A whose last segment is "node_modules" ]
      contained(C) = some candidate is an inventory "dir" entry that has a
                     "file" child "package.json"
      if not contained(C): add canonical_text(C) to exposures
resolution_exposures = sorted(set(exposures))   # ascending by ASCII text
```

(For the payload root, `"" + "/node_modules/…"` means `node_modules/…`.) A
directory without `package.json` is not containment (conservative: Node might
resolve it, but HPP-1 then requires upward absence). The loader re-parses every
stored exposure and refuses the chain if any fails or does not round-trip
byte-identically.

**Exposure absence (P2X / L14 / L21A):** for each exposure, `C` is obtained
from the parser; for each lexical ancestor `A` of the proven payload root whose
last component is not `node_modules` (nearest first, up to the volume root), the
one path observed is `ntpath.join(A, "node_modules", *C)`. Each lexical
component from `A\node_modules` down to the final component is observed
no-follow: every intermediate component must be a plain directory or
**missing** (a missing component ends that ancestor's check as absent); the
final entry must be **missing**. A present final entry, any reparse point, any
`other` classification, or any observation failure → exposed / unobservable.

**Package granularity (precision, not a new mechanism).** Containment is proven
per **package name**. A request for a *subpath* of a contained package that is
not satisfiable inside the nested copy (for example a CommonJS `require` of a
missing subpath of a package without `exports`) can still fall through to
ancestor `node_modules`. That request is "a specifier not satisfied inside the
payload" and belongs to the accepted **R-EXT-1** residual (§27). Evidence must
never claim subpath-level containment or that "every declared dependency
resolves inside the payload".

Undeclared and dynamic resolution are **not** brought into HPP-1 (R-EXT-1,
R-EXT-2).

---

## 7. Canonical encodings and strict policy parsing

### 7.1 `canonical_json_bytes`

```text
canonical_json_bytes(v) =
    json.dumps(v, sort_keys=True, separators=(",", ":"),
               ensure_ascii=True, allow_nan=False).encode("ascii")
```

over values restricted to: `dict` with `str` keys, `list`, `str` (no lone
surrogate), `int` (exact, not `bool`, 0 … 2⁵³−1), `bool`, `None`. **No float**
anywhere in policy data.

### 7.2 Policy file bytes

Every policy file's bytes are exactly
`canonical_json_bytes(record) + b"\n"` (one LF, no CR anywhere).

### 7.3 Strict policy parser (loader)

Size bound first (per file kind, §4.4); every byte < 0x80; no CR; exactly one
trailing LF; parse with duplicate-key refusal, `NaN`/`Infinity` refusal, float
refusal, depth ≤ 24; closed key set per `record_kind`; exact types
(`type(x) is …`); 64-lowercase-hex digests (`fullmatch [0-9a-f]{64}`); then
**canonical re-encoding must equal the file bytes exactly** (one admissible
encoding). Every derivable field is recomputed (§9.4).

### 7.4 Line endings (PE-2b repository requirement)

The authoring checkout has `core.autocrlf=true` and no `.gitattributes`. A
text-converting checkout would change policy file bytes and therefore the APS
head digest. Frozen requirements:

1. PE-2b adds exactly one attribute rule, scoped to the policy directory:
   `experiments/pi_harness_cfg1/pi_profile_policy/** -text`
   (no end-of-line conversion; no other path affected).
2. Independently of (1), the loader refuses any CR byte (fail closed): a
   converted checkout can never load with a different head than the committed
   blobs.
3. The APS head digest a live authorization binds is the SHA-256 of the
   committed blob bytes, which must equal the working-tree bytes the loader
   reads; the PE-6 review verifies both.
4. Evidence-reference digests (§9.9) are over committed blob bytes; a checkout
   whose working-tree bytes differ fails the offline verifier closed.

---

## 8. Classification C1–C5 and the C2 relation

### 8.1 Reference sets

For a candidate evaluated against APS state `P` (discovery: the head revision;
loader: revision `N−1` for an approval first appearing in revision `N`, §9.5):

- `R` ranges over profiles **eligible** for `CFG1-CC1` in `P` (approved and not
  retired), with their committed inventories and bundles.
- `S` ranges over seam fingerprints of every seam evidence record in `P` (and,
  for the loader, those added in revision `N` itself) and of every eligible
  profile in `P`.

### 8.2 Floor classes (mechanical; discovery computes, loader re-verifies)

Evaluated in this order; first match wins:

| Class | Mechanical condition |
|---|---|
| **C5** | walk not complete or a bound exceeded; any §4.6 approvability item fails |
| **C1** | `profile_id ∈ eligible(CFG1-CC1)` of `P` |
| **C1R** | `profile_id` equals a profile present in `P` that is not eligible (retired) → refused; re-admission is a design decision |
| **C2** | ∃ `R` with `C2(candidate, R)` (§8.3) |
| **C3_SEAM_EQUAL** | `seam_fingerprint` ∈ `S` |
| **C3_SEAM_CHANGED** | otherwise (including when `P` has no reference at all) |

**C4** is never mechanical: it is a review outcome ("AIDO consumer code must
change") and cannot be approved under `CFG1-CC1` (§9.5).

### 8.3 The C2 relation (B9, frozen exactly)

`C2(X, R)` holds iff all of:

1. **Identical tree:** the sets of `(path, kind)` of X and R are equal.
2. **Differing files:** `D` = file paths whose `(size, sha256)` differ; `D` is
   non-empty and `D ⊆ PERMITTED_MANIFESTS`, where

   ```text
   PERMITTED_MANIFESTS = { "package.json",
                           "node_modules/@earendil-works/pi-ai/package.json",
                           "node_modules/@earendil-works/pi-agent-core/package.json" }
   ```

3. For each `M ∈ D`, with both sides parsed strictly and order-preservingly
   (§6.2):
   - **key presence is immutable:** for each internal name
     `I ∈ ("@earendil-works/pi-ai", "@earendil-works/pi-agent-core")`,
     `(I is a key of X.dependencies) == (I is a key of R.dependencies)` —
     where a missing `dependencies` field means "not a key"; if presence
     differs, `C2` is **false** and no projection is attempted;
   - **structure-preserving value-slot projection:** copy each document's
     entire ordered structure, keeping **every** key at **every** position,
     and replace **only these values** with `MARKER`: the top-level `version`
     value; and, for each `I` present on **both** sides, the value of
     `dependencies[I]`. Nothing is deleted, popped, filtered or re-keyed;
   - the two projected structures are **equal as complete ordered key/value
     structures at every level, with exact types** (a dict compares as its
     ordered item list; `1` ≠ `1.0` ≠ `True`).
4. **Equal exposure sets** (implied by 1–3; still checked).

`MARKER` is a module-private object outside the JSON value domain; no parsed
JSON value (including a string spelled like its `repr`) can equal it. The
permitted slots are **values only**: never keys, never presence, never
position. A dependency key added or removed is **never** C2; a key reorder is
never C2; any non-manifest byte change is at least C3. Formatting-only byte
differences (whitespace, escape spelling, `-0.0` vs `0.0`) are within C2 and
always produce a `RAW_BYTES` delta (§10).

### 8.4 Approval classes

Conservativeness order, least → most:

```text
C2_MANIFEST_ONLY < C2_MANIFEST_DELTA_REACQUIRED < C3_SEAM_EQUAL < C3_SEAM_CHANGED
                 < C4_CONTRACT_REVISED < CC_REAPPROVAL
```

Floor → least admissible class: C2 → `C2_MANIFEST_ONLY`;
C3_SEAM_EQUAL → `C3_SEAM_EQUAL`; C3_SEAM_CHANGED → `C3_SEAM_CHANGED`;
C5 → not approvable. An approval's class must be ≥ its recomputed floor's least
admissible class (reviewers may escalate, never downgrade). The floor is
mechanical; the approval class is a review conclusion; neither substitutes for
the other.

---

## 9. Policy authority — directory, records, chain, loader

### 9.1 The policy directory

```text
<POLICY_DIR> = <directory containing the loader module>\pi_profile_policy
             = <ROOT>\experiments\pi_harness_cfg1\pi_profile_policy
```

- Derived **only** from the loading module's own `__file__` (the loader module
  lives directly in `experiments\pi_harness_cfg1`). Never from a caller
  argument, environment variable, current directory, record field, or Pi
  content. The production code has exactly **one** call site that loads the
  genuine tree, passing that derived constant; a module-private loader
  function parameterized by a directory exists solely so tests can load
  synthetic trees under `tmp_path`; an AST audit proves no other production
  call site passes a directory (§26.2 B-11).
- `<POLICY_DIR>` lies inside the audited CFG1 source root, so the A4-style
  topology walk (§23.2), clean-tree checks and untracked-shadow checks cover
  it.

### 9.2 Layout (exact)

```text
<POLICY_DIR>\aps\aps.r<NNNN>.json                    NNNN: 4 decimal digits, 0001…9999
<POLICY_DIR>\inventories\<payload_fingerprint>.json
<POLICY_DIR>\manifest_bundles\<payload_fingerprint>.json
```

- `<POLICY_DIR>` contains exactly the entries `aps`, `inventories`,
  `manifest_bundles` (each a plain directory), except that `inventories` and
  `manifest_bundles` **may be absent iff the chain references no file in
  them** (Git cannot track an empty directory; at genesis both are
  unreferenced). If present, each must be a plain directory whose entries are
  exactly the referenced files (an empty present directory is accepted when
  nothing is referenced). `aps` must be present and hold ≥ 1 revision.
- A filename is formed only **after** its fingerprint has been validated as
  `type(x) is str` and `fullmatch [0-9a-f]{64}`, by concatenating that string
  with `".json"`. Revision filenames are formed from validated integers.
- **Revision numbers are contiguous from `0001`**; the set of `aps` filenames
  must be exactly `aps.r0001.json … aps.r<NNNN>.json` for the highest `NNNN`.
- Every file is read **no-follow through one handle**. Any reparse point, any
  non-regular entry, any name not matching the grammar, any stray, extra,
  unreferenced, duplicate or missing file (including a `__pycache__`, README,
  temporary or editor file) **fails the whole chain closed**.
- **No profile-controlled or record-controlled path is ever opened.** Evidence
  references are opened only by the offline verifier (§9.9).

### 9.3 Exact record schemas (closed key sets)

All ids and digests are 64 lowercase hex. All lists preserve order. "refs" =
non-empty list (≤ 256, or ≤ 64 inside PMD findings) of
`{"repo_path": <§9.9 grammar>, "sha256": <hex>}`.

**Seam evidence** `aido-pi-seam-evidence.v1`:
```text
record_kind, seam_contract ("PI-SC1"), seam_digests (exactly the 20 PI-SC1 keys),
seam_fingerprint (recomputed), evidence (refs), evidence_id
evidence_id = SHA-256(canonical_json_bytes(record without "evidence_id"))
```

**Profile** `aido-pi-profile.v1`:
```text
record_kind, payload_contract ("PI-PC1"), payload_fingerprint, resolution_exposures,
profile_id, seam_contract ("PI-SC1"), seam_digests, seam_fingerprint,
declared { package_name, package_version, pi_ai_version, pi_agent_core_version },
discovery { aido_commit (40 lc hex), discovery_tool_revision ([A-Za-z0-9._-]{1,64}) }
```
No `inventory_ref`, no `manifest_bundle_ref`, no boolean, no path field.

**Approval** `aido-pi-profile-approval.v1`:
```text
record_kind, profile_id, consumer_contract ("CFG1-CC1"), policy_revision ("HPP-1"),
qualification_class, reused_evidence (list, possibly empty), pmd (null | object, §10),
evidence (refs, non-empty), acceptance_reference, approval_id
approval_id = SHA-256(canonical_json_bytes(record without "approval_id"))

reused_evidence[i] = {
  "evidence_kind": "E1" | "E3" | "E4" | "E5" | "E6",
  "source_id":     <profile_id or seam evidence_id>,
  "premise_scope": {"kind": "SEAM_FILES", "paths": [sorted, unique, non-empty ⊆ PI-SC1]}
                 | {"kind": "PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS"},
  "refs": <refs> }
```
(`SEAM_FILES:<paths>` in HPP-1 prose denotes the first `premise_scope` form.)

**Retirement** `aido-pi-profile-retirement.v1`:
```text
record_kind, profile_id, consumer_contract ("CFG1-CC1"),
reason_code ("SECURITY_ADVISORY" | "DERIVATION_INVALIDATED" | "OPERATOR_WITHDRAWN"
             | "SUPERSEDED_BY_POLICY"),
evidence (refs, non-empty), retirement_id
retirement_id = SHA-256(canonical_json_bytes(record without "retirement_id"))
```

**APS revision** `aido-pi-approved-profile-set.v1`:
```text
record_kind, consumer_contract ("CFG1-CC1"), policy_revision ("HPP-1"),
payload_contract ("PI-PC1"), seam_contract ("PI-SC1"),
revision (int = NNNN of its filename), previous_revision_sha256 (null iff revision 1),
seam_evidence, profiles, approvals, retirements            (lists)
```

(Every record carries its own `record_kind`, so each id preimage is already
domain-separated.)

### 9.4 Recompute everything derivable, trust nothing derivable

For every profile the loader: reads the inventory and bundle at the
fingerprint-derived paths; validates the inventory (§4.2, §4.5 tree closure,
case-fold uniqueness, bounds); recomputes `payload_fingerprint` (must equal the
filename and the record); verifies every bundle manifest (§6.1); strictly
parses every package-root manifest; recomputes the declared projection,
`resolution_exposures`, `profile_id`, `seam_digests`, `seam_fingerprint`;
re-checks approvability (§4.6); and refuses any disagreement. It recomputes
every `evidence_id`, `approval_id` and `retirement_id`. No field is trusted
because it is present.

### 9.5 Chain and lineage rules

- **Append-only:** for every `N ≥ 2`, each of the four lists in revision `N`
  has revision `N−1`'s list as an exact prefix (element-wise canonical byte
  equality); additions are appended only. A removal, edit or reorder fails the
  whole chain. `previous_revision_sha256` of `N` equals SHA-256 of revision
  `N−1`'s file bytes. All contract/policy literals are equal in every revision.
- **Uniqueness:** no duplicate `profile_id`, `payload_fingerprint`,
  `evidence_id`, `approval_id` or `retirement_id`; at most one approval per
  `(profile_id, "CFG1-CC1")`; at most one retirement per profile.
- **Profiles enter only with their approval:** every profile first appearing
  in revision `N` must be the subject of exactly one approval first appearing in
  the same revision `N`. (REJECTED candidates never enter an APS.)
- **References resolve against `N−1`:** an approval first appearing in `N` is
  verified against revision `N−1`'s state: its floor (§8), `R`, every
  `reused_evidence.source_id` that is a profile (must be eligible in `N−1`),
  and `pmd.reference_profile_id` (must be eligible in `N−1`). Seam evidence
  `source_id`s may resolve to seam evidence in revision ≤ `N` (seam evidence has
  no references, so no cycle arises). An approval can never depend on itself,
  on a sibling approval of the same revision, or on a retired profile.
- **Classes admissible under `CFG1-CC1`:** exactly `C2_MANIFEST_ONLY`,
  `C2_MANIFEST_DELTA_REACQUIRED`, `C3_SEAM_EQUAL`, `C3_SEAM_CHANGED`.
  `C4_CONTRACT_REVISED` and `CC_REAPPROVAL` are reserved enum names for a future
  `CFG1-CC2` lineage (code first, PE-0 §8.4) and are refused by the
  `CFG1-CC1` loader.
- **Floor verification:** class ≥ recomputed floor (§8.4); a C5 or C1R
  candidate can never be approved.
- **Retirement:** target must be eligible in `N−1`; removes eligibility from
  `N` onward; terminal under HPP-1; deletes nothing.
- **Mutable state does not exist:** there is no `approved=true`, no default,
  no truthiness, no "latest profile wins", no nearest match, no automatic
  semver compatibility.

### 9.6 Eligibility (computed, never stored)

```text
eligible(CC, N) = { a.profile_id | a ∈ approvals(N), a.consumer_contract == CC,
                    a.policy_revision == "HPP-1" }
                − { r.profile_id | r ∈ retirements(N), r.consumer_contract == CC }
```

Exact-`str` `frozenset` membership. A live-eligible profile for `CFG1-CC1` is
exactly `approved(profile, CFG1-CC1, HPP-1) ∧ ¬retired(profile, CFG1-CC1)` at
the **bound** head. Earlier heads keep their eligible sets, recomputable from
the committed chain.

### 9.7 Head

`H` = SHA-256 of the highest revision file's bytes, 64 lowercase hex. A later
revision is never authority under an authorization that bound an earlier `H`
(G6A exact equality, §22.2; the authorization's commit pins the tree).

### 9.8 Genesis revision 1 (created in PE-2b)

Exactly: one seam evidence record (§5.3) whose `evidence` cites, by committed
blob digest, the CFG1 base design (§1.2/§2/§14.2), the L16-FU2 design (§16) and
OC-3 AMEND1 (the accepted OC-3 archaeology); zero profiles, approvals and
retirements; `previous_revision_sha256 = null`. The genesis eligible set is
empty, so **every** installed Pi is `PI_PROFILE_UNAPPROVED` until a candidate
is onboarded (PE-0 F-14).

### 9.9 Evidence references (offline only)

`repo_path` grammar: `/`-joined segments, each `fullmatch [A-Za-z0-9._-]+`, not
`.`/`..`, total ≤ 512 chars, no leading/trailing `/`. The runtime loader checks
**syntax only** and never opens a reference. The offline evidence-reference
verifier (PE-2b) composes PE-0 §4.14 exactly:
`canonicalize_existing_path_under_workspace(<checkout root derived from its own
module location>, repo_path, allow_symlinks=False)`, regular file, SHA-256
equal. Eligibility never depends on it; it is never imported by the runtime
path (recording-double test).

### 9.10 Candidate staging namespace (R1, B12) — the discovery write boundary

Discovery is **static and non-executing**, but it is **not** write-free: it
creates bounded candidate artifacts. Its entire write authority is this closed
boundary; no supported caller can make discovery create a file anywhere else.

**Fixed location.**

```text
<STAGING> = <directory containing the discovery module>\pi_profile_candidates
          = <ROOT>\experiments\pi_harness_cfg1\pi_profile_candidates
```

- Derived **only** from the discovery module's own `__file__` (the module lives
  directly in `experiments\pi_harness_cfg1`). Never from a caller argument,
  command-line option, environment variable, current directory, record field,
  or Pi content. The discovery entry point accepts **no** output-path,
  directory or filename parameter of any kind.
- `<STAGING>` is disjoint from `<POLICY_DIR>` (a sibling, never nested either
  way) and from `results\`.

**Exact file layout (flat; no subdirectories).**

```text
<STAGING>\<payload_fingerprint>.candidate.json
<STAGING>\<payload_fingerprint>.inventory.json
<STAGING>\<payload_fingerprint>.manifest_bundle.json
```

Positive filename grammar, exact:
`^[0-9a-f]{64}\.(candidate|inventory|manifest_bundle)\.json$`. A filename is
formed only by concatenating a `payload_fingerprint` that discovery itself just
computed and validated (`type is str`, `fullmatch [0-9a-f]{64}`) with one of the
three frozen suffix literals. No other name is ever formed.

**Write procedure (frozen).**

1. **Topology proof before any write.** The CFG1 package directory is the
   audited parent. `<STAGING>` is observed no-follow: it must be a plain
   directory (no reparse attribute) or **missing**. If missing, discovery
   creates **exactly that one directory** with a non-recursive,
   exclusive `mkdir` (parent must already exist; `exist_ok=False`), then
   re-observes it no-follow as a plain directory. Anything else refuses.
2. **Structural containment.** Each target path is
   `ntpath.join(<STAGING>, <validated name>)`; containment is proven
   structurally (the joined path's parent is exactly `<STAGING>`, the name has
   no separator, drive, colon or `..`), never by string prefix.
3. **All-absent precheck.** All three target names are observed no-follow and
   must be **missing**; if any exists (file, directory, reparse point or
   anything else) discovery refuses before creating anything.
4. **Exclusive create, in fixed order** (`candidate` last): each file is created
   with exclusive-create semantics (`O_CREAT | O_EXCL`, no-follow), written
   once, flushed and closed. A create collision or write failure stops the
   sequence and is reported on the console; files this invocation already
   created are **left as residue** (never deleted), and any later discovery of
   the same fingerprint refuses at step 3 until the operator resolves it.
5. **Forbidden:** overwrite, append, truncate, rename-around, temporary-file
   swap, deletion or cleanup of any pre-existing object, creation of any
   directory other than `<STAGING>` itself, and any write under
   `<POLICY_DIR>`, `results\` or anywhere else.
6. **No fingerprint, no file.** If the walk is not complete (no
   `payload_fingerprint` exists), discovery writes **nothing** and reports a
   bounded console diagnosis only.

**Non-authority.** The runtime policy loader, P, the gate, L1, L14 and L21A
never read `<STAGING>`; candidate existence never grants eligibility; the
loader's §9.2 rules never consider it. An operator reviews candidate artifacts
and commits them manually; authority arises only when PE-5 separately copies a
reviewed profile, inventory and bundle into a new APS revision under
`<POLICY_DIR>` with an independently accepted approval. Untracked staging files
make the live launcher's untracked-shadow admission refuse (§23.2), so a
candidate cannot linger silently in a live checkout. The candidate record's
internal schema (beyond: it names its fingerprint, would-be `profile_id`, floor
class — or `NOT_COMPUTED` until PE-2b wires the committed reference view
(§26.0) — or C5 reason, declared projection and exposure set, and is never loaded
as authority) is a PE-2a implementation detail precisely because it cannot
affect authority. This is not general file-output infrastructure.

---

## 10. PMD — Permitted-Manifest-Delta consumer review (frozen schema)

### 10.1 When present

`pmd` is **required** (non-null) iff the approval's recomputed floor is C2
**or** any `reused_evidence` entry uses
`PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS`; otherwise it **must be null**.

### 10.2 The mechanical delta list

For candidate `X` and reference `R = pmd.reference_profile_id` (which must be
eligible in `N−1` and satisfy `C2(X, R)`), for each `M ∈ D` in inventory order,
in this fixed order within `M`:

```text
RAW_BYTES                                      always; old/new = R's / X's sha256 of M
VERSION                                        iff the top-level "version" values differ;
                                               old/new = exact strings
INTERNAL_DEPENDENCY:@earendil-works/pi-ai      iff that key is present in M's
                                               "dependencies" on BOTH sides and the
                                               exact-str values differ; old/new = values
INTERNAL_DEPENDENCY:@earendil-works/pi-agent-core   likewise
```

A dependency key addition or removal is never a PMD delta (such a pair is not
C2). Nothing else can differ under C2, so the list is complete by construction.

### 10.3 Schema

```text
pmd = {
  "reference_profile_id": <profile_id>,
  "deltas": [ {
      "delta":         "RAW_BYTES" | "VERSION"
                       | "INTERNAL_DEPENDENCY:@earendil-works/pi-ai"
                       | "INTERNAL_DEPENDENCY:@earendil-works/pi-agent-core",
      "manifest_path": <rel>,
      "old": <str>, "new": <str>,
      "read_as_parsed_field": {"finding": "NOT_APPLICABLE" | "NOT_READ" | "READ", "refs": [...]},
      "read_as_raw_manifest": {"finding": "NOT_READ" | "READ", "refs": [...]},
      "categories": { <exactly the 11 keys below>:
                      {"finding": "NOT_REACHED" | "REACHED_NO_EFFECT" | "AFFECTS",
                       "refs": [...]} },
      "cfg1_cc1_effect": "NOT_AFFECTED" | "AFFECTED",
      "evidence_effect": { "<i>": "NOT_AFFECTED" | "AFFECTED"
                           for exactly i = 0 … len(reused_evidence)−1, as decimal strings }
  } ... ],
  "conclusion_refs": <refs, non-empty> }

categories: PROMPT_OR_MODEL_VISIBLE_CONTENT  RPC_BEHAVIOR          REQUEST_SHAPE
            PROVIDER_OR_MODEL_SELECTION      FEATURE_GATES         CONFIG_MIGRATION
            TOOL_REGISTRATION_OR_DISPATCH    EXTENSION_BEHAVIOR    FILESYSTEM_BEHAVIOR
            NETWORK_BEHAVIOR                 TELEMETRY_USER_AGENT_OR_HEADERS
```

A category finding is **relative to `CFG1-CC1` and to this approval's reused
evidence**: `AFFECTS` means the delta reaches that category with an effect on
either; `REACHED_NO_EFFECT` means it reaches the category with no such effect.

### 10.4 Mechanical rules (loader-enforced)

1. The projection `(delta, manifest_path, old, new)` of `deltas`, in order,
   equals the recomputed list exactly (§10.2); an omitted, extra, reordered or
   altered delta refuses.
2. `read_as_parsed_field.finding == "NOT_APPLICABLE"` iff `delta == "RAW_BYTES"`
   (with `refs == []`); otherwise `NOT_READ` or `READ` with non-empty `refs`
   (for `NOT_READ` the refs cite the search performed).
3. `read_as_raw_manifest.refs` is non-empty for both findings (the mandatory
   search for reads of `M` as bytes/text, PE-0 §14.4 scenario 5), and all deltas
   of the same `manifest_path` carry the same `read_as_raw_manifest.finding`.
4. Every category key is present; `refs == []` iff finding `NOT_REACHED`.
5. `evidence_effect` has exactly one key per `reused_evidence` index.
6. **Consistency (bi-implication):** some category is `AFFECTS` ⇔
   `cfg1_cc1_effect == "AFFECTED"` or some `evidence_effect` value is
   `AFFECTED`.
7. Any `evidence_effect` value `AFFECTED` **refuses the approval**: an affected
   item may not be reused; the reviewer must remove it from `reused_evidence`
   (which removes its key) and cite the re-acquired evidence in `evidence`. So
   in every loadable approval all `evidence_effect` values are `NOT_AFFECTED`,
   and rule 6 reduces to `AFFECTS ⇔ cfg1_cc1_effect == AFFECTED`.
8. `C2_MANIFEST_ONLY` is admissible only if every delta has
   `cfg1_cc1_effect == "NOT_AFFECTED"`.
9. Any delta with `cfg1_cc1_effect == "AFFECTED"` requires class
   `C2_MANIFEST_DELTA_REACQUIRED` or more conservative.
10. Every `PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS` reuse entry must have
    `source_id == pmd.reference_profile_id`.

### 10.5 Mechanical completeness vs review truth

The loader proves **structural completeness and consistency**: every actual
delta is listed, every category and reused item is addressed, and the class and
reuse entries do not contradict the findings. It **cannot** prove that a
finding is true — e.g. that `NOT_READ` is correct, that re-acquired evidence
actually re-acquires what was affected, or that an effect needs no AIDO code
change (else C4). Those are **independent-review truths** over bound payload
bytes (PE-0 F-16). No document, record or console line may present a loaded PMD
as proof that a delta is inert.

---

## 11. The canonical proof P, the leaf surface and the sealed snapshot

### 11.1 P (profile-aware, frozen sequence)

```text
P0   read exactly one ambient name, PATH, by name                   → PI_RESOLUTION_FAILED
P1   first admissible node.exe + Pi package root over admissible
     PATH entries; capture I_n and I_r (unchanged)                  → PI_RESOLUTION_FAILED
P2   complete PI-PC1 payload observation (§4.3), uncached
     not completely observable / bound exceeded                     → PI_PAYLOAD_UNPROVEN
     → payload_fingerprint pf
P2M  exact membership: the eligible runtime profile whose
     payload_fingerprint == pf (exact str, from the sealed snapshot)
     none                                                           → PI_PROFILE_UNAPPROVED
     more than one: impossible for a loaded chain; RAISES, never chooses
P2X  the matched profile's declared exposures absent (§6.6)
     present or unobservable                                        → PI_EXTERNAL_RESOLUTION_EXPOSED
P2R  re-prove I_r (package root), then I_n (node.exe)               → PI_IDENTITY_DRIFTED_DURING_PROOF
→    PiProofResult
```

- Failure precedence is the fixed function order above.
- P executes no Node/Pi/JavaScript; runs no `pi --version`; reads no
  package-manager metadata; makes no runtime/model claim; reads no credential
  or endpoint; writes nothing; **parses nothing Pi-authored** (exposure names
  come from the sealed, loader-verified policy; P never imports the manifest
  parser — AST audit).
- Observe-then-match: the observed path set is fixed by the walk rules before
  the first read; nothing Pi supplies selects what is checked.

### 11.2 Leaf surface (X-1)

`PiProofLeaves` has exactly these slots: `inspect` (the §7.2 no-follow
inspection/identity primitive, unchanged), `read_digest` (the one-handle reader,
now returning classification, exact byte count, SHA-256 and within-bound, per
§4.3 step 3), `enumerate_directory` (**new**: opens one no-follow handle,
classifies it, and lists `(name, reparse|directory|file)` entries through
**that handle** via `GetFileInformationByHandleEx` directory-information
classes, refusing once a caller-supplied entry budget is exceeded), and
`checkout_root`. `pi_fs_leaves`' native surface remains exactly
`CreateFileW`, `GetFileInformationByHandleEx`, `GetFileType`, `CloseHandle`
plus `msvcrt.open_osfhandle`, `os.read`, `os.close`; it imports no
`subprocess`, `multiprocessing` or `asyncio.subprocess` (Test AA, extended). No
leaf can create a process.

### 11.3 `PiProofResult` and `Cfg1PiIdentity`

- `PiProofResult` slots: `failure_code`, `payload_observation_complete`,
  `identity` (`seam_digests_match` is removed from the profile-aware result).
  Pass: `failure_code is None`, `payload_observation_complete is True`,
  `identity` an exact `Cfg1PiIdentity`. Refusal: `failure_code` ∈ the five
  proof codes (§12.1), `payload_observation_complete` equal to `Allowed_O`
  (§19.3), `identity is None`.
- `Cfg1PiIdentity` gains exactly one attribute, `matched_profile_id` (exact
  64-hex `str`); no version slot.
- `require_pi_proof_result_shape` refuses anything else, **including** a
  `failure_code` of `PI_PROFILE_CHANGED_WITHIN_STAGE`, `PI_IDENTITY_PROVEN` or
  `PI_IDENTITY_GATE_UNEXPECTED_FAILURE`, and a pass whose `matched_profile_id`
  is not in the sealed snapshot's eligible set.

### 11.4 Sealed policy snapshot

- Loaded **once, at import** of the policy module, only from `<POLICY_DIR>`
  (§9.1); strictly validated (§7.3, §9.4, §9.5, §10.4) **before** any use; a
  malformed chain makes the module fail to import (→ launcher G4 refuses).
- Sealed into an immutable object constructible only by the loader
  (module-private key); no setter, no reload, no path parameter; no parameter of
  `run_cfg1_stage`, the gate, P, L1, L14 or L21A accepts a snapshot; no
  caller-supplied snapshot exists.
- Carries only **policy**: `policy_revision`, `payload_contract`,
  `seam_contract`, `consumer_contract`, `aps_revision` (int), `aps_head_sha256`,
  `policy_directory` (for G6 only), the computed `eligible_profile_ids`
  (`frozenset[str]`), and for each eligible profile an immutable runtime view
  `(profile_id, payload_fingerprint, resolution_exposures as component tuples,
  declared_package_version)`. It is never an observation of the installed Pi.
- The eligible set is computed at load, never read from a stored field.
- Import-time behavior changes by exactly this: the policy module performs
  no-follow, read-only reads of files under `<POLICY_DIR>` and bounded CPU work
  (§4.4). It still reads no environment variable, opens no network connection,
  starts no process and writes no file.

---

## 12. Failure-code namespaces (distinct; each has fixed origins)

### 12.1 Canonical proof failures — `PiProofResult.failure_code`

```text
PI_RESOLUTION_FAILED               P0, P1
PI_PAYLOAD_UNPROVEN                P2
PI_PROFILE_UNAPPROVED              P2M
PI_EXTERNAL_RESOLUTION_EXPOSED     P2X
PI_IDENTITY_DRIFTED_DURING_PROOF   P2R
```

Exactly **five**. HPP-1 defines no further canonical proof code: a missing
`dist/cli.js` or `PI-SC1` file surfaces as `PI_PROFILE_UNAPPROVED` (no approved
profile lacks them); a bound breach is `PI_PAYLOAD_UNPROVEN`; a duplicate match
is impossible for a loaded chain and raises; an unloadable policy never reaches
P (import fails). Produced **only** by P.

**Terminology resolution.** PE-0 §10.3/§16 speak of "six P codes". Precisely,
that phrase means **the six values of the v3 durable field
`pi_identity_failure_code`** = the five canonical proof codes above **plus**
`PI_PROFILE_CHANGED_WITHIN_STAGE` (§12.3), which is not produced by P. The
accepted semantics are unchanged; only the name is made exact.

### 12.2 Gate wrapper — the gate's return domain (seven values)

```text
PI_IDENTITY_PROVEN                   pass (exact str)
PI_IDENTITY_GATE_UNEXPECTED_FAILURE  the gate caught a raise or a malformed P result
+ the five §12.1 codes, passed through unchanged
```

`PI_IDENTITY_GATE_UNEXPECTED_FAILURE` is **not** a `PiProofResult` claim: it is
never a `failure_code`, never a value of `pi_identity_failure_code`, and never
produced by L1. The gate never returns `PI_PROFILE_CHANGED_WITHIN_STAGE` (it has
no stage).

### 12.3 Stage-level profile consistency

```text
PI_PROFILE_CHANGED_WITHIN_STAGE      L1 only, ordinal k > first ordinal, after a
                                     passing P whose matched_profile_id differs
                                     from the stage's fixed profile
```

It is not a version mismatch, not a membership failure, and not a P code.

### 12.4 Other namespaces (each closed; none overlaps another)

| Namespace | Values | Origin |
|---|---|---|
| v3 `pi_identity_failure_code` | null + §12.1 (5) + §12.3 (1) | L1 commit only |
| `pre_dispatch_refusal_code` | unchanged v2 domain; P codes are never members | executor |
| L14 re-proof | exact `True` / not-`True` → `RUNTIME_LAUNCH_FAILED` | L14 |
| `pi_profile_post_runtime_reobservation` | `NOT_APPLICABLE` `CHANGED` `UNPROVEN` `PROVEN_UNCHANGED` | L21A (executor) |
| classification | + `INDETERMINATE_PI_PROFILE` (v3 only) | v3 classifier |
| halt | + `PI_PROFILE_ATTRIBUTION_UNPROVEN` (v3 stage closure only) | L30 |
| launcher | `G6A_*`, `G7_<gate code>`, `G7_PI_GATE_MALFORMED_RETURN`, `G7_PI_GATE_RAISED`, `G9_BOUND_ID_INVALID`, `G9_EXECUTION_NAMESPACE_OCCUPIED`, `G9_EXECUTION_NAMESPACE_UNOBSERVABLE` | PE-6 launcher, console only; none consumes |
| policy loader | one exception type with a closed, diagnostic-only reason set (PE-2b names it) | import |
| discovery | candidate floor + diagnostic reasons (e.g. `PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR`) — never authority | PE-2a tool |

---

## 13. Pre-consumption gate

```text
pre_consumption_pi_identity_gate(ambient_environ) -> str
    same canonical P (same function object), same genuine leaves,
    same sealed policy snapshot; reads PATH only; executes nothing;
    writes nothing; no credential; no stage-output authority;
    returns exactly one of the seven §12.2 codes; returns nothing reusable
```

Only the exact `str` `PI_IDENTITY_PROVEN` may continue; every other value,
type, `str` subclass, raise or refusal stops **before** Stage-output authority
consumption. The gate remains waste avoidance; L1 and L14 carry the security
claims.

---

## 14. L1 — authority boundary and stage profile consistency

### 14.1 Handoff (exact)

`Cfg1RunAdmission` gains exactly one field, `stage_pi_profile_id: str | None`:
`None` iff the admitted ordinal is the stage execution's first ordinal (1);
otherwise the exact 64-hex id the runner-local stage-progress ledger fixed from
ordinal 1's L1 pass. It is a **narrowing constraint, never an authority**; the
runner derives it only from its own ledger.

### 14.2 L1 sequence (cursor `L1`)

1. Validate the admission value's shape (first ordinal: exactly `None`;
   otherwise `type is str` and `fullmatch [0-9a-f]{64}`). A violation raises →
   `UNEXPECTED_STEP_FAILURE` at `L1` with **nothing** of P's family committed.
2. Run P **from scratch** with the same function object, genuine leaves and
   sealed snapshot; no gate result is reused (none exists to reuse).
3. `require_pi_proof_result_shape` (§11.3).
4. Compute the family as plain values (nothing can raise here):
   - P refusal → `(F = code, O = Allowed_O(code), pid = null, v = null)`;
   - P pass, `stage_pi_profile_id` non-null and `identity.matched_profile_id
     != stage_pi_profile_id` (exact `str` comparison) →
     `(F = PI_PROFILE_CHANGED_WITHIN_STAGE, O = true, pid = null, v = null)`;
   - otherwise pass → `(F = null, O = true, pid = matched_profile_id,
     v = snapshot.declared_package_version(pid))`.
5. **Commit atomically** `pi_identity_failure_code`,
   `pi_payload_observation_complete`, `pi_profile_id`,
   `pi_profile_declared_package_version` (and, for `F ≠ null`,
   `pre_dispatch_refusal_code = OFFLINE_PREFLIGHT_FAILED`,
   `refused_at_step = L1`) as plain assignments of validated values.
6. `F ≠ null` → refuse (`REFUSED_PRE_DISPATCH`; the stage halts by the frozen
   CFG1 §19.1 item 2).
7. Otherwise retain the identity in executor state and proceed to Git
   resolution (unchanged, OC-7).

No credential or endpoint is read before L4; every identity and profile gate
above precedes L4. An unknown or changed profile therefore refuses before any
credential read.

### 14.3 Stage profile

The runner's ledger fixes `stage_pi_profile_id` from ordinal 1's outcome
observations iff `pi_profile_id` there is an exact 64-hex `str`; it never
changes afterwards within that stage execution. A resumed attempt is a new
stage execution under a new authorization and fixes its own stage profile.

**Runner-local profile ledger (R1, B11).** Beside the frozen stage-progress
ledger (`_ordinal_ledger`, CFG1 §16.3.8.4), the one stage-runner routine holds a
second plain local of the same frame, `_profile_ledger`, with the same
confinement: never a module global, never returned, never passed to any
function outside that routine's own body, never persisted. It holds exactly:

- `stage_pi_profile_id` (`str | None`), set once from ordinal 1 as above;
- per executed ordinal `k`, the exact L1 profile fact `profile_fact[k]` — the
  64-hex `str` if `outcome.observations["pi_profile_id"]` is exactly that,
  otherwise the sentinel `NONE` (a malformed value is never repaired into a
  profile);
- per executed ordinal `k`, the pair `(runtime_created, L21A)` read with exact
  types, consumed only by item 1A (§17.1).

**Capture point, frozen:** each entry is written by a local assignment the
moment `execute_cfg1_run` returns ordinal `k`'s in-memory `Cfg1RunOutcome` —
**before** L29 emission and independent of its outcome. The source is only
that in-memory executor outcome. It is **never** filled from
`Cfg1RunAdmission` (which carries the stage profile *to* the executor, never
back), never from a public argument, and never by reading or parsing any run,
refusal or stage-closure artifact on disk.

---

## 15. L14 and L21A

### 15.1 L14 — launch-nearest re-proof (not a fresh membership choice)

`reprove_pi_identity_for_launch(identity, leaves)` in fixed order:

```text
1  complete, uncached PI-PC1 payload walk → pf'
2  pf' == the payload_fingerprint of identity.matched_profile_id
   (equality with L1's exact matched profile — NOT re-membership; a different
    but independently approved profile refuses)
3  exposure absence for that profile (§6.6)
4  I_r re-proof
5  I_n re-proof
→  exact True only; anything else, or a raise → RUNTIME_LAUNCH_FAILED, no launch()
```

Nothing that reads the Pi tree, resolves a name or executes anything sits
between the exact `True` and `launch()`/`Popen`. The L14→`Popen` TOCTOU
sliver, now spanning the payload walk, is preserved as a documented residual
and not solved here.

### 15.2 L21A — mandatory post-runtime payload re-observation

**Execution position (frozen, B8):**

```text
L21 → L22 → L23 → L24 → L21A → L25 → L26 → L27
```

- **Applicability** is read **after L21** has made its OC-4 D-3 decision
  (which may move `runtime_created` from `false` to `true` when `launch()` was
  called and absence of a process cannot be proven):
  `runtime_created == false` → `NOT_APPLICABLE` and **no** payload walk;
  `runtime_created == true` → attempted **exactly once**.
- A contained failure at L21, L22, L23 or L24 must not suppress L21A; an L21
  failure reaches L21A only through its own condition (`runtime_exit_observed`
  not exactly `True` → at best `UNPROVEN`).
- A contained L21A failure must not suppress L25, L26 or L27.
- L21A is total by OC-4 step-local containment: a raise, a malformed leaf
  output, a missing `identity`, or any value outside
  `{CHANGED, UNPROVEN, PROVEN_UNCHANGED}` from the procedure → `UNPROVEN`. The
  executor alone decides `NOT_APPLICABLE`.
- **Procedure:** complete walk → `pf''`; exposure-absence check; `I_r`.
  (`I_n` is not re-proved; `node.exe` is outside the profile.)
- **Result** `pi_profile_post_runtime_reobservation`:

| Value | Condition (evaluated in this order) |
|---|---|
| `NOT_APPLICABLE` | `runtime_created is False` |
| `CHANGED` | walk complete and `pf''` ≠ the run's profile fingerprint, **or** an exposure is present |
| `UNPROVEN` | not `CHANGED`, and any of: `runtime_exit_observed is not True`; walk not complete; exposure observation unobservable; `I_r` drifted; the step raised or returned a malformed value |
| `PROVEN_UNCHANGED` | `runtime_exit_observed is True`, walk complete, `pf''` equal, exposures absent, `I_r` unchanged |

- L21A **is an observation, not a closure predicate**: it never changes
  `lifecycle_all_closed`, `lifecycle_failure_steps` or their domains. It
  executes nothing, reads no credential, writes nothing but its observation.
- **Meaning:** only `PROVEN_UNCHANGED` supports a definite profile attribution
  for a launched run, and it means only *the payload at L14 and at L21A were
  identical and the direct child had exited when L21A observed*. No
  continuity between L14 and L21A is claimed; an A→B→A change is undetectable
  (accepted residual); descendants are not tracked; nothing is prevented.

---

## 16. Run classification (v3)

The v3 classifier is the frozen CFG1 §12.1 table with **one row inserted**;
first match wins:

```text
1   INDETERMINATE_LIFECYCLE                 (unchanged)
2   REFUSED_PRE_DISPATCH                    (unchanged)
2A  INDETERMINATE_PI_PROFILE                pi_profile_post_runtime_reobservation
                                            ∈ {CHANGED, UNPROVEN}
3…12                                        (unchanged, same order: INDETERMINATE_DISPATCH …
                                             ACTIVE … INACTIVE)
```

- Precedence exactly as accepted: after `INDETERMINATE_LIFECYCLE` and
  `REFUSED_PRE_DISPATCH`, before every dispatch/runtime classification. No
  other row moves.
- For a launched run, `CHANGED` or `UNPROVEN` can never become `ACTIVE` or
  `INACTIVE`. A refused-pre-dispatch run with a created process (e.g. an
  L15/L16 refusal) keeps `REFUSED_PRE_DISPATCH` and still records its L21A
  value and still halts the stage on `CHANGED`/`UNPROVEN` (§17).
- `INDETERMINATE_PI_PROFILE` is not determinate; by the frozen CFG1 §12.3 rule its
  arm is `INDETERMINATE`.
- The **v2 classifier, its 12-value domain and the v2 validator are
  unchanged**; the v2 domain never contains `INDETERMINATE_PI_PROFILE`.

---

## 17. Admission, halt and stage-halt semantics (v3, X-3)

### 17.1 Admission item 1A

For a profile-aware stage, CFG1 §19.1 gains item **1A**, evaluated with items 1–4:

```text
1A  (type(runtime_created) is bool) and
    ( (runtime_created is False and L21A == "NOT_APPLICABLE") or
      (runtime_created is True  and L21A == "PROVEN_UNCHANGED") )
    with L21A compared as an exact str
```

Anything else — `CHANGED`, `UNPROVEN`, or any malformed value — fails item 1A
(fail closed).

### 17.2 Stage halt `PI_PROFILE_ATTRIBUTION_UNPROVEN`

When an applicable L21A yields `CHANGED` or `UNPROVEN`: the ordinal finishes
its closure (L25–L27) and its evidence production (L28, L29) exactly as frozen;
then L30 takes **branch A** (halt) because item 1A failed. No retry, no second
execution, no re-run of the ordinal, no next ordinal; later ordinals are
`NOT_EXECUTED`; the stage can never close as a normal completion (branch C
requires items 1–4 **and** 1A); a later attempt needs a fresh diagnosis and a
fresh authorization.

### 17.3 v3 halt vocabulary and precedence

`HALT_REASON_CODES_V3` = the six frozen codes ∪ `{PI_PROFILE_ATTRIBUTION_UNPROVEN}`
(seven). The frozen six-member `HALT_REASON_CODES` object and the six-step
`_resolve_halt_reason_code` remain **unchanged** and continue to govern v1
stage-closure validation. The v3 precedence, one shared function, first match
wins:

```text
1   emission_status == EMISSION_COLLISION        → RUN_RECORD_EMISSION_COLLISION
2   emission_status == EMISSION_FAILED           → RUN_RECORD_EMISSION_FAILED
3   halt_triggered_by_this_run == true           → RUN_RECORD_SELF_VALIDATION_FAILED
4   lifecycle_all_closed == false                → LIFECYCLE_CLOSURE_UNPROVEN
5   run_classification == REFUSED_PRE_DISPATCH   → PRE_DISPATCH_REFUSAL
5A  item 1A failed                               → PI_PROFILE_ATTRIBUTION_UNPROVEN
6   registries not empty                         → RUN_SCOPED_REGISTRY_NOT_EMPTY
```

Step 5A sits where the classification row sits relative to lifecycle and
pre-dispatch refusal. Because one code per halted ordinal cannot carry two
causes, the **independent** stage-closure field `pi_profile_attribution_halt`
(§20.2) records item 1A's failure regardless of which code wins. It is an L30
value exactly like `halt_reason_code`: computed by L30 from the runner-local
profile ledger for ordinal `k` (§14.3), and handed to the nested terminal sealer
by the same routine that computes it (§20.3); it is `True` iff branch A was taken
**and** item 1A failed for `k`, and `False` otherwise (including branch C).

### 17.4 Closure of the vocabulary

This amendment is the separately authorized design amendment CFG1 §19.5
requires for a seventh code. Its closure rule is inherited: no implementation
may add an eighth v3 code, alias one, or infer one from a novel failure without
a further authorized amendment. The four no-stage-closure dispositions
(`STAGE_OUTPUT_AUTHORITY_HARD_STOP`, `STAGE_CLOSURE_EMISSION_FAILED`,
`OUTPUT_NAMESPACE_PREOCCUPIED`, `STAGE_DECISION_MINT_FAILED`) are unchanged and
remain outside every durable vocabulary.

---

## 18. Closure order (restated, exact)

Per ordinal, after the dispatch phase:

```text
L21   runtime teardown (direct child exit status, both reader EOFs; D-3 applicability)
L22   broker diagnostic capture
L23   broker shutdown
L24   sensitive generated-config / extension scrub (AMEND2)
L21A  post-runtime payload re-observation (§15.2)
L25   Git observation #1
L26   verification (repository-controlled code) and Git observation #2
L27   workspace cleanup
L28   finalize observations (lifecycle closure computed; L21A not a predicate)
L29   emission
L30   admission decision / stage decision (items 1–4 + 1A; §17)
```

Resource shutdown and sensitive-material scrub keep priority over the
potentially expensive payload walk; L21A precedes any repository-controlled
code (L26). No `try` spans more than one step (OC-4 I-8).

---

## 19. v3 run record `pi-harness-cfg1-run.v3`

### 19.1 Key set

Exactly the v2 key set **minus** `pi_seam_digests_match` **plus**:

| Field | Domain | Rule |
|---|---|---|
| `pi_payload_contract` | `"PI-PC1"` | exact literal |
| `pi_seam_contract` | `"PI-SC1"` | exact literal |
| `pi_consumer_contract` | `"CFG1-CC1"` | exact literal |
| `pi_profile_policy_revision` | `"HPP-1"` | exact literal |
| `pi_profile_set_head_sha256` | 64 lc hex | always present (the sealed snapshot's head) |
| `pi_payload_observation_complete` | exact bool | §19.3 |
| `pi_profile_id` | 64 lc hex or null | §19.3 |
| `pi_profile_declared_package_version` | 1…128 chars in 0x21–0x7E, or null | copied from the matched profile's loader-bound `declared.package_version`; null iff `pi_profile_id` null; "declared", never observed/reported |
| `pi_identity_failure_code` | null or the six values of §12.1 + §12.3 | §19.3 |
| `pi_profile_post_runtime_reobservation` | the four L21A values | §15.2, §19.3 |
| `pi_profile_authority_scope` | `"PI_PACKAGE_PAYLOAD_AND_DECLARED_RESOLUTION_BOUNDARY"` | exact, every v3 run record |
| `pi_external_runtime_residual` | `"NOT_IDENTIFIED_BY_PROFILE"` | exact, every v3 run record **including successful ones**; a string, never a boolean |
| `run_classification` | v2 domain ∪ `{INDETERMINATE_PI_PROFILE}` | recomputed by the v3 classifier |

**Forbidden in v3:** `pi_observed_version`, `pi_version_probe_attempted`,
`pi_seam_digests_match`; and no v3 key, enum value, halt code or console code
may contain (case-insensitively) `fully_identified`, `identity_complete`,
`complete_identity`, `runtime_identity`, `node_pinned`, `runtime_pinned` or
otherwise claim complete Node/Pi runtime identity.

### 19.2 Header and dispatch

Header literals as v2 (`scoring_authority false`, `qualification_credit false`,
`is_review_packet false`, `reviewer_invoked false`, `claim_scope`), with
`record_version = "pi-harness-cfg1-run.v3"`. The v3 validator is its own
implementation, never a wrapper over v2 (CFG1 §22.4.3 discipline). Dispatch adds the
exact pairs `(run.v3, run kind)` and `(refusal.v3, refusal kind)`; the v1/v2
pairs keep dispatching to their unchanged validators. A v1/v2 payload fails the
v3 literal check before any v3 rule could reinterpret it, and vice versa.

### 19.3 Identity/profile invariants (pure functions of the payload)

Let `K = refused_at_step`, `C = pre_dispatch_refusal_code`,
`F = pi_identity_failure_code`, `O = pi_payload_observation_complete`,
`Pid = pi_profile_id`, `V = pi_profile_declared_package_version`,
`L = pi_profile_post_runtime_reobservation`, `RC = runtime_created`.

```text
Allowed_O:  PI_RESOLUTION_FAILED → false     PI_PAYLOAD_UNPROVEN → false
            PI_PROFILE_UNAPPROVED → true     PI_EXTERNAL_RESOLUTION_EXPOSED → true
            PI_IDENTITY_DRIFTED_DURING_PROOF → true
            PI_PROFILE_CHANGED_WITHIN_STAGE → true
```

| Rule | Statement |
|---|---|
| R3-S1 | domains and exact key set as §19.1 |
| R3-S2 | `F ≠ null` ⇒ `K == "L1"` ∧ `C == OFFLINE_PREFLIGHT_FAILED` ∧ `O == Allowed_O(F)` ∧ `Pid == null` |
| R3-S3 | `K == "L1"` ∧ `C == OFFLINE_PREFLIGHT_FAILED` ∧ `F == null` ⇒ `O == true` ∧ `Pid ≠ null` (the Git-resolution refusal, its only meaning) |
| R3-S4 | `K == "L1"` ∧ `C == UNEXPECTED_STEP_FAILURE` ⇒ `F == null` ∧ (`(O, Pid) == (false, null)` — before the commit — **or** `O == true ∧ Pid ≠ null` — after it) |
| R3-S5 | `K` null or `K ≠ "L1"` ⇒ `F == null` ∧ `O == true` ∧ `Pid ≠ null` |
| R3-S6 | `K == "L1"` ⇒ `C ∈ {OFFLINE_PREFLIGHT_FAILED, UNEXPECTED_STEP_FAILURE}` |
| R3-S7 | `V == null` ⇔ `Pid == null` |
| R3-S8 | `L == "NOT_APPLICABLE"` ⇔ `RC is False` |
| R3-S9 | `K == "L1"` ⇒ `RC is False` |
| R3-S10 | `C == null` ⇒ `RC is True` (every non-refused run launched Pi) |
| R3-S11 | `run_classification ∈ {ACTIVE, INACTIVE}` ⇒ `L == "PROVEN_UNCHANGED"` |
| R3-S12 | `run_classification == INDETERMINATE_PI_PROFILE` ⇔ (`lifecycle_all_closed` true ∧ `C == null` ∧ `L ∈ {CHANGED, UNPROVEN}`) |
| R3-S13 | `run_classification` equals the v3 classifier over the payload |
| R3-S14 | the two B7 literals and four contract literals are present and exact |

The R3-S rules are exhaustive and mutually exclusive over `(K, C, F)` exactly
as AMEND1's R-S1…R-S6. **R3-S4 refines PE-0's `Allowed(F)` table**, whose "null
(pass)" row did not cover an unexpected L1 failure before P's commit (the
frozen R-S4 case); every PE-0 row is otherwise reproduced exactly. All
remaining v2 invariants (schedule, arm, modes, W, dispatch, OBS1, broker,
lifecycle, repository, verification) carry over unchanged. A record violating
any rule fails self-validation (`RECORD_INVARIANT`; halt, CFG1 §18 row 15).

Binding `pi_profile_id` and the declared version to the committed APS chain is
the separate read-only verifier of §21, never the payload validator.

---

## 20. v3 refusal and stage-closure records

### 20.1 `pi-harness-cfg1-refusal.v3`

The v2 refusal shape, independently implemented, with
`record_version = "pi-harness-cfg1-refusal.v3"`,
`refused_record_kind = "pi-harness-cfg1-run.v3"`, plus the four contract
literals, `pi_profile_set_head_sha256`, and the two B7 literals. It carries no
per-run profile field (it stands in for a run record that could not be
emitted; it never supplies that record's profile evidence).

### 20.2 `pi-harness-cfg1-stage-closure.v3`

Keys: the v1 stage-closure keys (with `record_version =
"pi-harness-cfg1-stage-closure.v3"` and `halt_reason_code ∈
HALT_REASON_CODES_V3 ∪ {null}`) **plus**:

| Field | Domain |
|---|---|
| `pi_payload_contract`, `pi_seam_contract`, `pi_consumer_contract`, `pi_profile_policy_revision` | exact literals |
| `pi_profile_set_head_sha256` | 64 lc hex |
| `stage_pi_profile_id` | 64 lc hex or null |
| `stage_pi_profile_declared_package_version` | bounded text or null |
| `ordinal_pi_profile_binding` | map, keys exactly the declared ordinals (as strings), values `"STAGE_PROFILE"` \| `"NO_PROFILE"` \| `"NO_RUN_EVIDENCE"` \| `"NOT_EXECUTED"` |
| `pi_profile_attribution_halt` | exact bool |
| `pi_profile_authority_scope`, `pi_external_runtime_residual` | the two B7 literals |

**Two classes of field, two sources (R1, B11):**

| Class | Fields | Sole source |
|---|---|---|
| **Stage-dependent, decision-authenticated** | `stage_pi_profile_id`, `ordinal_pi_profile_binding`, `pi_profile_attribution_halt` (plus the frozen `ordinal_status`, `halted_after_ordinal`, `halt_reason_code`) | the runner-local ledgers (§14.3) and the actual L30 decision, bound at terminal seal time into `_DecisionMintRecord` **and** `CFG1StageClosureDecision` (§20.3) |
| **Policy-derived, writer-internal** | the four contract literals, `pi_profile_set_head_sha256`, the two B7 literals, `stage_pi_profile_declared_package_version` | derived **inside** the v3 writer from frozen module literals and the same audited module-level sealed HPP-1 snapshot (§11.4); never a parameter of anything |

**Binding values (computed by the nested sealer from the two ledgers at seal
time), for each declared ordinal `k`:**

| Value | Condition |
|---|---|
| `NOT_EXECUTED` | `ordinal_status[k] == NOT_EXECUTED` |
| `NO_RUN_EVIDENCE` | `ordinal_status[k] ∈ {EVIDENCE_REFUSED, EMISSION_COLLISION, EMISSION_FAILED}` — the ordinal ran but no confirmed run record exists; **whatever its in-memory profile fact was, it contributes no per-ordinal profile claim** |
| `STAGE_PROFILE` | `ordinal_status[k] == RECORD_EMITTED` ∧ `profile_fact[k]` is an exact `str` equal to `stage_pi_profile_id` |
| `NO_PROFILE` | `ordinal_status[k] == RECORD_EMITTED` ∧ not `STAGE_PROFILE` |

These are **stage-ledger facts**, not per-run evidence: the closure never reads
a run or refusal record to produce them, never fills a missing or refused run
record, and an `EVIDENCE_REFUSED` run is never a source of per-ordinal profile
authority. `stage_pi_profile_id` is different in kind: it is the **constraint
the runner actually enforced** on every later L1 (§14.1), captured from ordinal
1's in-memory outcome before its emission; it is recorded because it is what
the stage ran under, and it is corroborated durably only by the
`STAGE_PROFILE` ordinals' run records (§21).

**Invariants (coherence; independently implemented; all v1 invariants kept):**

1. `stage_pi_profile_id == null` ⇔ `stage_pi_profile_declared_package_version == null`.
2. `stage_pi_profile_id == null` ⇒ `halted_after_ordinal == 1` ∧
   `ordinal_pi_profile_binding["1"] ∈ {NO_PROFILE, NO_RUN_EVIDENCE}`.
3. Any `STAGE_PROFILE` value ⇒ `stage_pi_profile_id != null`.
4. `binding[k] == NOT_EXECUTED` ⇔ `ordinal_status[k] == NOT_EXECUTED`.
5. `binding[k] == NO_RUN_EVIDENCE` ⇔ `ordinal_status[k] ∈ {EVIDENCE_REFUSED,
   EMISSION_COLLISION, EMISSION_FAILED}`; `binding[k] ∈ {STAGE_PROFILE,
   NO_PROFILE}` ⇔ `ordinal_status[k] == RECORD_EMITTED`.
6. `binding[k] == NO_PROFILE` ⇒ `k == halted_after_ordinal`.
7. `pi_profile_attribution_halt` ⇒ `halted_after_ordinal != null` ∧
   `stage_pi_profile_id != null` ∧ `binding[halted_after_ordinal] ∈
   {STAGE_PROFILE, NO_RUN_EVIDENCE}`.
8. `halt_reason_code == PI_PROFILE_ATTRIBUTION_UNPROVEN` ⇒ `pi_profile_attribution_halt`.
9. `halted_after_ordinal == null` (normal completion) ⇒
   `pi_profile_attribution_halt` is false ∧ `stage_pi_profile_id != null` ∧
   every binding ∈ {`STAGE_PROFILE`, `NO_RUN_EVIDENCE`}.

So the closure proves the exact stage profile the stage ran under, that every
ordinal with a confirmed run record either bound that profile or was the
refused halt ordinal, the exact APS head and contract literals, whether the
stage halted for profile attribution, and that no normal completion co-exists
with `PI_PROFILE_ATTRIBUTION_UNPROVEN` — all through the one sealed-decision
authenticity chain.

### 20.3 Decision authentication of the new stage facts (R1, B11)

The frozen provenance chain is preserved and extended, never paralleled:

```text
runner-local state (_ordinal_ledger, _profile_ledger, L30's computed values)
  -> lexically owned nested _seal_terminal_decision (no module-level sealer)
  -> _DecisionMintRecord            (registered in _STAGE_DECISION_SEALED)
  -> CFG1StageClosureDecision       (__post_init__ registry re-check)
  -> _verify_sealed_decision        (fresh re-proof at consumption)
  -> emit_cfg1_stage_closure(authority, *, decision)
```

**PE-2c migration, frozen:**

1. **`_DecisionMintRecord`** gains exactly three fields, appended after
   `halt_reason_code`: `stage_pi_profile_id: str | None`,
   `ordinal_pi_profile_binding: tuple[tuple[int, str], ...]` (sorted by
   ordinal, one pair per declared ordinal), `pi_profile_attribution_halt: bool`.
2. **`CFG1StageClosureDecision`** gains the same three fields in the same order.
   It remains the **one** decision type (SUCCESS and HALTED); no second decision
   object and no parallel registry are created. `__post_init__` keeps its
   registry re-check.
3. **`_bound_fields()`** returns the frozen six-element tuple **followed by** the
   three new fields, so the object/record comparison in `__post_init__` and in
   `_verify_sealed_decision` covers them. The comparison becomes
   **type-exact**: each element pair must satisfy `type(a) is type(b) and a == b`
   (recursively for tuples), so `True` can never stand in for `1`, nor `1` for
   `True`, in any bound field. A mismatch raises the existing
   `DECISION_FIELD_MISMATCH`.
4. **Nested `_seal_terminal_decision`** (inside `run_cfg1_stage`'s own body)
   keeps its five-step mint order and its seal-once check. It reads
   `stage_pi_profile_id` and the per-ordinal profile facts from the
   closed-over `_profile_ledger`, computes `ordinal_pi_profile_binding` from
   `_ordinal_ledger` and `_profile_ledger` per §20.2, and receives
   `pi_profile_attribution_halt` as a keyword argument alongside the two L30
   values it already receives (`halted_after_ordinal`, `halt_reason_code`) —
   all three computed by L30 in that same routine. It refuses before step 3 if
   `pi_profile_attribution_halt` is not an exact `bool`, or is `True` while
   `halted_after_ordinal is None`. No public, module-level or importable sealer
   is introduced.
5. **`_verify_sealed_decision`** is unchanged in steps and codes, and now
   compares the extended, type-exact `_bound_fields()`.
6. **Writer canonical construction:** `emit_cfg1_stage_closure(authority, /, *,
   decision)` keeps exactly those parameters (no `payload`, `profile_id`,
   `ordinal_profile_binding`, `profile_attribution_halt`, `aps_head`,
   `declared_version`, `**kwargs` or any other). Steps 1 (authority), 2 (exact
   type), 3–4 (`_verify_sealed_decision`) and 4a (revoke consumability) run
   **before** any payload is built. Step 5 then builds the v3 canonical payload
   internally: stage-dependent fields only from the re-verified `decision`;
   policy-derived fields only from frozen literals and the module-level sealed
   snapshot.
7. **Stage declared version — design B (chosen).**
   `stage_pi_profile_declared_package_version` is **not** bound into the
   decision. The writer derives it at step 5 exclusively from the sealed
   `decision.stage_pi_profile_id` and the same module-level sealed HPP-1
   snapshot: `null` when the sealed id is `null`; otherwise the snapshot
   runtime view's `declared_package_version` for that exact id. If the id is not
   an eligible runtime profile of the snapshot, step 5 raises and the write
   resolves as the existing `PRE_CREATE` failure (no fallback, no caller value
   exists).
8. **Unchanged:** `_STAGE_DECISION_SEALED` (authenticity and one-shot
   consumability, revoked at writer step 4a) and
   `_STAGE_TERMINAL_SEAL_HISTORY` (per-authority seal-once history) keep their
   exact meanings, owners and lifetimes; `_discard_stage_decision_state` is
   unchanged; run records never become closure authority.

---

## 21. Profile binding verifier (read-only, post-hoc, never in the runtime path)

Inputs: one stage execution's v3 artifacts and the committed policy chain of
the verifying checkout (loaded by the same strict loader). It:

1. refuses any v1/v2 artifact (it never applies HPP-1 to historical evidence);
2. requires every v3 artifact of the stage to carry the same head and literals;
3. finds the revision whose file SHA-256 equals that head (append-only chains
   keep earlier revisions) — none → refuse;
4. recomputes `eligible(CFG1-CC1)` at that revision; `stage_pi_profile_id` and
   every non-null run `pi_profile_id` must be members and equal the stage
   profile; every declared version must equal that profile's
   `declared.package_version`;
5. cross-checks `ordinal_pi_profile_binding` against every `RECORD_EMITTED` run
   record (`STAGE_PROFILE` ⇔ that record's `pi_profile_id` equals the stage
   profile); it never infers anything for `NO_RUN_EVIDENCE` or `NOT_EXECUTED`
   ordinals and never reads a refusal record as profile evidence.

---

## 22. G6A and the gates around it

### 22.1 G6 additions (source-origin, PE-6 launcher)

G6 additionally proves: the policy module's `_POLICY_DIR` equals
`<ROOT>\experiments\pi_harness_cfg1\pi_profile_policy`; the sealed snapshot
object P, L1, L14 and L21A consult **is** (identity) the policy module's
module-level snapshot, whose `policy_directory` equals that path; the executor's
L21A procedure and the payload-walk functions **are** the audited
`pi_identity` / walker functions; `PI_IDENTITY_GATE_CODES` equals the launcher's
closed **seven**-code vocabulary.

### 22.2 G6A (new)

After G6, before G7, in the launcher process; every comparison
`type(x) is str and x == expected`:

```text
G6A   snapshot.aps_head_sha256    == APS_HEAD_SHA256   (launcher literal, the
                                                        authorization's exact head)
      snapshot.policy_revision    == "HPP-1"
      snapshot.payload_contract   == "PI-PC1"
      snapshot.seam_contract      == "PI-SC1"
      snapshot.consumer_contract  == "CFG1-CC1"
```

No truthiness, default, fallback, prefix or "contains". Any failure →
`G6A_<FIELD>_MISMATCH`, class T, **not consumed**. G6A executes before
Stage-output authority consumption. The eligible set is a function of the
bound head and is not separately compared.

### 22.3 G7, G8

G7 is the §13 gate; exact `PI_IDENTITY_PROVEN` only. Classes: `G7_PI_RESOLUTION_FAILED`,
`G7_PI_PAYLOAD_UNPROVEN`, `G7_PI_PROFILE_UNAPPROVED`,
`G7_PI_EXTERNAL_RESOLUTION_EXPOSED` → E (Pi environment; §25 remedy);
`G7_PI_IDENTITY_DRIFTED_DURING_PROOF`, `G7_PI_IDENTITY_GATE_UNEXPECTED_FAILURE`,
`G7_PI_GATE_MALFORMED_RETURN`, `G7_PI_GATE_RAISED` → T. G8 re-runs the full
origin audit and additionally re-checks that the module-level snapshot object
and its `aps_head_sha256` are unchanged. All refusals: not consumed.

### 22.4 G9 — bound execution-namespace absence (R1, B10)

The launcher holds **exactly one** execution-id literal,
`BOUND_STAGE_EXECUTION_ID`, a module-level constant whose value is the fresh
literal frozen in the PE-6 authorization (its bytes are bound by
`LAUNCHER_SHA256`). It is never chosen, derived, computed, read from the
environment, the command line, a file or the current directory.

After G8 and immediately before consumption, in the launcher process:

```text
G9  1  type(BOUND_STAGE_EXECUTION_ID) is str
       and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", BOUND_STAGE_EXECUTION_ID)
       and BOUND_STAGE_EXECUTION_ID not in {"CFG1-S1-A1", "CFG1-S1-A2",
                                            "CFG1-S1-A3", "CFG1-S1-A4"}
                                                  else G9_BOUND_ID_INVALID
    2  RESULTS_ROOT is the audited root G6 proved (stage_output's own
       derivation — never recomputed by the launcher from anything else)
    3  observe ntpath.join(RESULTS_ROOT, BOUND_STAGE_EXECUTION_ID) no-follow:
         missing                                  → pass
         directory / file / reparse / other       → G9_EXECUTION_NAMESPACE_OCCUPIED
         observation error                        → G9_EXECUTION_NAMESPACE_UNOBSERVABLE
then, and only then:
    authority = establish_stage_output_authority(
        stage_id="S1", stage_execution_id=BOUND_STAGE_EXECUTION_ID)
    run_cfg1_stage(authority)
```

Steps 1–3 are performed by calling the audited PE-2c namespace-precheck
primitive (§26.3 C-27) with that constant; the launcher does not reimplement
them. The **same name** `BOUND_STAGE_EXECUTION_ID` is the only argument source
for both the G9 absence check and the establishment call. G9 creates nothing and
writes nothing. Every G9 refusal is console-only and **does not consume** the
authorization. G9 is **waste avoidance** before the irreversible
authorization-consumption call: `establish_stage_output_authority` remains
independently fail-closed (CFG1 §16.3.6: an existing execution directory
refuses the entire stage with `EXECUTION_DIRECTORY_EXISTS`, never merged,
reused or deleted). A directory created by another process **after** G9 and
before establishment still makes establishment refuse — **after** consumption;
that is the existing filesystem TOCTOU residual, stated and not solved here
(R-NAMESPACE-RACE, §27).

---

## 23. Pre-live barrier and source provenance

### 23.1 Profile-aware pre-consumption order (conceptual, frozen)

```text
A-items   exact authorization / Git / workspace admission
          (HEAD == authorization commit; tracked tree and index clean; no
           untracked import-shadow, policy or candidate-staging state;
           RESULTS_ROOT\<BOUND_STAGE_EXECUTION_ID> ABSENT;
           launch directory, temp, Git-resolution sanity; credential NAMES present,
           values never seen)
   ↓
G0–G6     source-origin / import-provenance admission
          (G4 imports the lineage, which now includes the policy loader and the
           profile modules: the sealed HPP-1 policy is loaded and validated here;
           a malformed chain fails the import)
   ↓
G6A       sealed HPP-1 policy binding to the authorization's exact APS head
   ↓
G7        canonical static Pi profile gate  → exact PI_IDENTITY_PROVEN only
   ↓
G8        post-gate source / module / snapshot re-audit
   ↓
G9        RESULTS_ROOT\<BOUND_STAGE_EXECUTION_ID> absent (launcher's one bound literal)
   ↓
authority = establish_stage_output_authority(stage_id="S1",
                                             stage_execution_id=BOUND_STAGE_EXECUTION_ID)
   ↓
run_cfg1_stage(authority)
```

`<BOUND_STAGE_EXECUTION_ID>` is the exact fresh literal frozen in the future
PE-6 authorization, and it is the **same** literal at every place it appears in
this order: the operator's A-item absence check (read from the authorization
text), the launcher's G9 check, and the establishment call (both from the
launcher's single constant, §22.4). Neither the operator procedure nor the
launcher may choose, derive or substitute a different id.

PE-1 authorizes no concrete execution id and reserves nothing (not
`CFG1-S1-A5`). A future PE-6 authorization chooses a fresh literal satisfying
the frozen grammar that is none of `CFG1-S1-A1…A4`. `CFG1-S1-A4` is burned.

### 23.1a Namespace admission semantics (R1, B10)

- **Generic contract:** the only namespace absence the profile-aware
  pre-consumption order checks is `RESULTS_ROOT\<BOUND_STAGE_EXECUTION_ID>`. R0's
  generic item `RESULTS_ROOT\CFG1-S1-A4 ABSENT` is **withdrawn** from the
  forward-looking order: A4 is burned and never executes, so its path is not the
  namespace any future run will consume.
- **Purpose:** waste avoidance before the irreversible consumption call. An
  occupied namespace found by the A-item or by G9 **does not consume** the
  authorization.
- **Independent backstop:** `establish_stage_output_authority` remains
  fail-closed on an existing execution directory (CFG1 §16.3.6); a race after
  G9 can still make establishment refuse after consumption — the accepted
  filesystem TOCTOU residual (R-NAMESPACE-RACE), not solved here.
- **Historical references remain.** A4 remains `WITHDRAWN BEFORE CONSUMPTION /
  HISTORICAL ONLY / MUST NOT EXECUTE`, and the literal stays burned. PE-0 §1.3's
  requirement that the next authorization's admission confirm the historical A4
  namespace absent (evidence that A4 was never consumed) is **not reopened**:
  it is a PE-6 historical-evidence-state check of that specific authorization,
  distinct from and never a substitute for the generic bound-namespace
  admission above.

### 23.2 Source provenance

The profile-aware launcher preserves A3/A4's source-origin strength exactly:
`-I -S -B` with an empty external pycache prefix; explicit `SourceFileLoader`
binding of the four packages; full origin audit before and after the gate; the
five-root link-free topology walk (which already covers `<POLICY_DIR>` and
`<STAGING>` inside `experiments\pi_harness_cfg1`); clean tree and index vs
`HEAD`; the untracked import-shadow check (an untracked policy or
candidate-staging file refuses; the loader refuses any stray policy file). The new policy/profile modules are **inside the eager lineage and
its origin audit**; the lineage and closure count are recomputed by static
analysis at PE-6. The policy data files are bound by the clean committed tree,
the `HEAD` pin and G6A. No looser import path, data-driven module selection,
`importlib`, `runpy` or dynamic loading is introduced because the policy is
data.

### 23.3 Credentials — no change

Profile discovery, matching, the gate, L1 and every pre-credential identity
step read no credential or endpoint. The frozen credential carrier semantics
(names, session mapping, presence checks, L4/L7/L12/L29 consumers) are
unchanged. An unknown profile refuses before any credential read (gate or L1).

### 23.4 Forward-looking barrier sequence (replaces FU1 R6 §17 / AMEND1 §19 for profile-aware runs)

1. PE-0 accepted (done). 2. PE-1 accepted/frozen. 3. PE-2a implemented and
independently accepted. 4. PE-2b implemented (including genesis r0001 and the
§7.4 attribute rule) and accepted. 5. PE-2c implemented and accepted. 6. PE-3
static / non-executing discovery of the installed Pi by the operator — it
executes nothing and writes only bounded candidate artifacts into `<STAGING>`
(§9.10); the operator reviews and commits them.
7. PE-4 qualification per floor class (E4/E5 only under separate explicit
authorizations; T-3 keeps its own authorization). 8. PE-5: APS revision 2
independently accepted and committed. 9. PE-6: a fresh live authorization,
two-step accepted, binding its commit and exact `APS_HEAD_SHA256`, reviewing the
APS diff since genesis (or the previously authorized head), listing A4 as
`WITHDRAWN BEFORE CONSUMPTION / HISTORICAL ONLY`, naming the eligible profiles
(ids + declared versions) for reviewers only, stating the PROFILE-COVERED FACT
and the external runtime residuals, and binding **no literal Pi version**.
There is **no** "restore Pi" item.

---

## 24. Future live-authorization binding semantics (content requirements only)

A profile-aware live authorization binds exactly: source commit `C`, APS head
`H`, `HPP-1`, `PI-PC1`, `PI-SC1`, `CFG1-CC1`, and one fresh
`stage_execution_id` — which its launcher carries as the single constant
`BOUND_STAGE_EXECUTION_ID` used for both the G9 namespace check and the
establishment call (§22.4). It permits exactly: an observed payload whose profile is
in `eligible(CFG1-CC1)` at `H`, exposures absent, re-proven at L1 and L14, and
`PROVEN_UNCHANGED` at L21A for definite attribution. It supplies only the
`stage_execution_id` to `run_cfg1_stage` (unchanged). Later approvals are never
eligible under it (no delegation, PE-0 §9.3).

---

## 25. Profile onboarding remedy (frozen text)

For `PI_PROFILE_UNAPPROVED`, `PI_PAYLOAD_UNPROVEN` and
`PI_EXTERNAL_RESOLUTION_EXPOSED` (gate, L1 or launcher):

> **The installed Pi is not eligible under this authorization's APS head. Route
> the installed Pi to profile onboarding / diagnosis. This authorization cannot
> be used with it.**

For `PI_RESOLUTION_FAILED`: *diagnose PATH / installation topology (P1
admissibility).* No AIDO document, code path, console line or remedy may say
"restore Pi 0.85.1", "downgrade Pi", "install the pinned Pi", or otherwise
require, instruct or automate installing an older release (static wording
audit, §26.3 C-18). HPP-1 does not require downgrading.

---

## 26. PE-2 implementation authorities and acceptance criteria

Three separate authorities, each needing its own explicit prompt; none executes
Node or Pi; every test uses synthetic trees and chains under pytest `tmp_path`
(Git-exercising tests use synthetic repositories under `tmp_path`); real
reparse points under `tmp_path` need the same explicit authorization as CFG1
T-29/T-31/T-43/T-63/T-144; no installed Pi is touched. Each is independently
reviewed (PE-2R); PE-2a may be reviewed before 2b/2c proceed.

### 26.0 Phase-ownership rule (R1, B13)

An implementation phase may define and test **shared primitives** that later
phases consume, but its independent acceptance must **never** require production
code whose ownership this document assigns exclusively to a later phase.
Integration obligations belong to the phase that owns the consuming code. In
particular: the strict manifest parser, dependency-map schema, package-name
parser, containment/exposure helper, floor classifier and PMD delta list are
PE-2a primitives accepted as pure functions (with synthetic inputs); the
committed-policy loader's use of them (B-14) and the discovery tool's floor
computation against the **committed** APS reference view (B-15) are PE-2b
acceptance obligations; runtime use by P/L1/L14/L21A is PE-2c's. Until PE-2b
exists, PE-2a discovery records the floor as `NOT_COMPUTED`.

### 26.1 PE-2a — offline profile observation and classification

Scope: payload walker and leaf extension (§4.3, §11.2); canonical inventory,
fingerprints, profile id (§4.5, §4.7, §5.2); manifest bundle (§6.1); strict
manifest parser (§6.2); dependency-map schema and package-name parser (§6.3);
package roots, declared projection, containment/exposure computation and the
exposure-absence observer (§6.4–§6.6); C1/C1R/C2/C3/C5 floor classifier and C2
projection as pure functions over supplied reference sets (§8); PMD delta-list
computation (§10.2); the static, non-executing discovery tool (double walk,
candidate artifacts written **only** through the §9.10 staging boundary,
no output-path parameter, reads only `PATH`, executes nothing, never a raw key
in console).

Acceptance tests (minimum):

| Id | Proves |
|---|---|
| A-1 | walk records every dir (incl. empty) and file of every extension; nested `node_modules` |
| A-2 | a one-byte change at each of: a seam file, `dist/cli/setup.js`, another non-seam JS, a nested dependency file, a `.node`, a `.wasm`, a doc — and add/remove/rename file, add empty dir — changes `payload_fingerprint` and `profile_id` (counterexamples 1–3) |
| A-3 | reparse anywhere (file symlink, dir symlink, junction; mount point under the T-144-class authorization) refuses; the walk never enters it |
| A-4 | `other` classification, open/enumeration/read failure, size instability each refuse (leaf doubles); nothing is skipped |
| A-5 | every §4.2 grammar rule and case-fold collision refuses |
| A-6 | each §4.4 bound: at-bound accepted, bound+1 refused, no partial result (mechanism with patched constants) plus a static test pinning the frozen values |
| A-7 | enumeration-order permutations yield identical canonical bytes; golden vectors for inventory bytes, `payload_fingerprint` and `profile_id` computed by the test from this spec |
| A-8 | strict manifest parser: BOM, invalid UTF-8, duplicate keys at depth, NaN/Infinity/-Infinity, `1e400`, long number token, depth 65, > 1 MiB, non-object top level, raw control character |
| A-9 | (R1, B13) the PE-0 §14.4 B5 malicious-name corpus through the PE-2a code that exists: the shared strict manifest/dependency-map parser, the package-name parser, the discovery path and the containment/exposure helper — each refusing before any key-derived in-memory key or filesystem observation (recording observation double that fails the test if called for a key-derived path); positive round-trips; AST audit: no raw dependency key reaches `ntpath.join`, `os.path.join`, formatting or concatenation. (The loader-path half moved to B-14.) |
| A-10 | containment/exposure: contained nested; directory without `package.json` is an exposure; scoped; `node_modules`-named ancestors skipped; `@scope` ancestor candidate; optional/peer dependencies; exposure-absence observer: missing, plain-dir-then-missing, present, reparse, unobservable |
| A-11 | classifier: counterexamples 5, 6, 13, 14; PE-0 §14.5 B9 table; key reorder → not C2; whitespace-only → C2 with exactly one `RAW_BYTES`; presence change → not C2 |
| A-12 | projection: never invoked on presence-differing input; retains every key and position; AST audit: no `pop`, `del`, filter or key-set construction; marker-aliasing test |
| A-13 | PMD delta list: order, completeness, `RAW_BYTES` always, no `INTERNAL_DEPENDENCY` for presence-differing keys |
| A-14 | approvability: missing `PI-SC1` path, `dist/cli.js` as dir, wrong package name, bad version grammar → C5 |
| A-15 | discovery: walks differing between passes refuse; no process creation / Node import (static audit); only `PATH` read; floor recorded `NOT_COMPUTED` without PE-2b |
| A-16 | (R1, B12) write boundary: the discovery entry point has no output-path, directory or filename parameter (signature audit) and reads no environment variable or current directory to choose one; every attempt to steer output — `..`, an absolute path, a drive or UNC path, another repository path, `<POLICY_DIR>`, `results\`, or any arbitrary destination, via arguments, environment or CWD — has no effect or refuses, and a recording filesystem double proves no create/open-for-write occurs outside `<STAGING>` |
| A-17 | (R1, B12) staging topology: `<STAGING>` derived from the module's `__file__`; missing → exactly one non-recursive exclusive `mkdir`; `<STAGING>` as a junction, symlink, file or other → refuse with nothing written; structural containment of every target; filename grammar `^[0-9a-f]{64}\.(candidate\|inventory\|manifest_bundle)\.json$` and names formed only from the validated fingerprint |
| A-18 | (R1, B12) exclusive create: any pre-existing target (file, dir, reparse) refuses before any create; a mid-sequence collision/failure leaves prior files as residue and deletes nothing; no overwrite, append, truncate, rename or temp-swap (static audit of the write calls); incomplete walk → nothing written |
| A-19 | (R1, B12) non-authority, PE-2a share: no PE-2a module other than the discovery writer references the staging literal, and none reads from `<STAGING>` (static audit). The loader-side and runtime-side audits are B-16 and C-26, owned by the phases that own that code (§26.0). |

### 26.2 PE-2b — policy authority

Scope: `<POLICY_DIR>` layout and loader (§9.1–§9.5); record schemas; strict
policy parser (§7); recomputation (§9.4); lineage, uniqueness, reference and
class rules (§9.5); PMD structural validation (§10.4); eligibility (§9.6); sealed
snapshot (§11.4); offline evidence-reference verifier (§9.9); the §7.4
attribute rule; **genesis revision 1** (§9.8).

| Id | Proves |
|---|---|
| B-1 | layout: stray file at each level, unreferenced/missing inventory or bundle, bad names (uppercase hex, 63 chars, `.JSON`, `aps.r1.json`, `aps.r00001.json`), reparse entry, `__pycache__` → refuse; absent `inventories`/`manifest_bundles` accepted iff unreferenced |
| B-2 | chain: gap, `r0000`, duplicate, `previous_revision_sha256` mismatch, edited/removed/reordered record, CR byte, non-canonical bytes (space, key order, non-ASCII, missing/extra LF), float, `bool`-as-int, NaN → refuse |
| B-3 | every derivable field tampered in turn (fingerprint, seam digests/fingerprint, declared, exposures, profile/evidence/approval/retirement ids) → refuse; forged ids refuse |
| B-4 | the committed genesis r0001 loads through the real loader (pytest, no Git): exactly one seam evidence equal to `PINNED_PI_SEAM_DIGESTS`, zero profiles, empty eligible set |
| B-5 | two approved profiles coexist; retirement removes eligibility from its revision on and leaves earlier eligible sets recomputable |
| B-6 | floor: counterexample 1 labelled C2 refused; understated classes refused; `C4_CONTRACT_REVISED`/`CC_REAPPROVAL` refused under CC1; PE-0 §14.5 loader B9 test |
| B-7 | reuse: counterexamples 13, 15, 16; `SEAM_FILES` digest mismatch; E6 via `SEAM_FILES` refused; E2/E7 reuse refused; source not eligible in `N−1` or retired refused; `PAYLOAD_EXCEPT…` without PMD or with a different reference refused |
| B-8 | PMD: PE-0 §14.4 scenarios 4–7; every §10.4 rule violated in turn; PMD present when not required, absent when required → refuse |
| B-9 | references: approval citing a same-revision profile; profile without its approval; second approval; retirement of a non-eligible or already retired profile → refuse |
| B-10 | evidence-reference verifier refuses `..`, absolute, drive, UNC, device, link component, non-regular, digest mismatch; the runtime loader never calls it (recording double) |
| B-11 | snapshot: not constructible outside the loader; immutable; no setter/reload; AST audit of the single production load site and its `__file__`-derived directory; policy module reads no environment variable and starts no process |
| B-12 | every policy bound of §4.4: at-bound accepted, over refused |
| B-13 | the §7.4 attribute rule exists and is scoped to `<POLICY_DIR>` only |
| B-14 | (R1, B13) loader integration: the committed-policy loader calls the **accepted PE-2a** strict manifest/dependency-map parser and package-name parser by identity (AST/identity audit — no second, looser or re-implemented parser on the loader path); the PE-0 §14.4 B5 malicious corpus, placed in committed synthetic manifest-bundle data, refuses the chain before any path-forming operation (recording double); malformed committed manifest data refuses before any path is formed |
| B-15 | (R1, B13) discovery floor integration: with a committed synthetic APS, discovery computes the floor through the loader-owned reference view and the PE-2a classifier by identity, never through a copy |
| B-16 | (R1, B12) the loader never references or reads `<STAGING>` (static audit + recording double); a candidate file placed in `<STAGING>` never changes the loaded chain, head or eligible set |

### 26.3 PE-2c — CFG1 integration

Scope: P2/P2M/P2X/P2R in P (§11); gate (§13); L1 and the admission handoff
(§14); stage consistency and the runner-local profile ledger (§14.3); L14
(§15.1); L21A at its frozen position (§15.2, §18); v3 classifier (§16); item 1A,
v3 halt precedence and stage halt (§17); v3 run/refusal/stage-closure records
and validators (§19, §20); the B11 decision-authentication migration of
`_DecisionMintRecord`, `CFG1StageClosureDecision`, `_bound_fields()`, the nested
sealer, `_verify_sealed_decision` and the writer's canonical construction
(§20.3); the G9 namespace-precheck primitive (§22.4, C-27); binding verifier
(§21); test migration (`cfg1_doubles` over synthetic snapshots; composition
test → `PI-SC1` + genesis equality; conformance tests profile-bound and failing
loudly as unapproved, never skipped, never comparing a version — T-3 execution
still separately authorized). It exposes the snapshot surface G6A reads but
does not write the PE-6 launcher.

| Id | Proves |
|---|---|
| C-1 | P order and precedence; each of the five codes reachable; duplicate match raises; P imports no manifest parser; reads only `PATH` |
| C-2 | gate returns exactly the seven values; never `PI_PROFILE_CHANGED_WITHIN_STAGE`; nothing reusable |
| C-3 | `require_pi_proof_result_shape` refuses stage/gate codes as failure codes, wrong `O`, a pass with a non-eligible id |
| C-4 | L1: ordinal 1 fixes the stage profile; same profile passes; different approved profile → `PI_PROFILE_CHANGED_WITHIN_STAGE` with `O = true`, `Pid = null`, no credential port called; malformed admission value → `UNEXPECTED_STEP_FAILURE` with P uncommitted; counterexample 8 |
| C-5 | L14: counterexample 9; a different approved profile refused; exposure appearing between L1 and L14 refused; `I_r`/`I_n` drift; no Pi-tree read between `True` and `launch()` |
| C-6 | L21A: the PE-0 §14.5 B8 closure-order test and failure-injection table; applicability after D-3 flip; each result row; counterexamples 10, 11 (ABA asserted as the documented limit); malformed value → `UNPROVEN`; `lifecycle_all_closed` unaffected |
| C-7 | v3 classification row position; `ACTIVE`/`INACTIVE` impossible without `PROVEN_UNCHANGED`; v2 classifier and domain byte-identical |
| C-8 | item 1A (including malformed values); v3 seven-step precedence; frozen six-code set and function unchanged objects; last-ordinal `CHANGED` → branch A, never C; no retry, re-run or next ordinal |
| C-9 | v3 run validator: every R3-S rule and each Allowed_O row; B7 literals mandatory on passes and refusals; forbidden keys; v1/v2 ↔ v3 cross-dispatch refused |
| C-10 | refusal v3 and stage-closure v3 validators: every §20.2 invariant; `.v2` stage-closure literal refused |
| C-11 | binding verifier: head lookup, eligibility at `H`, declared-version equality, mismatches and v1/v2 inputs refused |
| C-12 | PE-0 §14.4 scenario 8: undeclared sibling mutated mid-run → P, L14, L21A pass; B7 literals present |
| C-13 | static wording audit: no v3 key, enum value, halt code or console code claims complete runtime identity |
| C-14 | no credential/endpoint read on any profile refusal path (port recording) |
| C-15 | stage closure never reads run records to fill ledger facts; `EVIDENCE_REFUSED` ordinals carry no synthesized profile evidence |
| C-16 | AST audit: no production module compares a declared version outside the two permitted sites of §1 |
| C-17 | test migration as scoped above |
| C-18 | static audit: no restore/downgrade/install-pinned wording in any new code or console string |
| C-19 | (R1, B11) a genuine sealed decision with `stage_pi_profile_id` mutated via `object.__setattr__` → `DECISION_FIELD_MISMATCH` at `_verify_sealed_decision` |
| C-20 | (R1, B11) the same for `ordinal_pi_profile_binding` and for `pi_profile_attribution_halt` (including `True`→`1` and `False`→`0`, caught by the type-exact comparison) |
| C-21 | (R1, B11) a registry record omitting, or disagreeing with the object on, any of the three new bound fields refuses (`DECISION_FIELD_MISMATCH` / construction refusal); `_bound_fields()` returns the frozen six fields followed by exactly the three new ones |
| C-22 | (R1, B11) `inspect.signature(emit_cfg1_stage_closure)` is exactly `(authority, /, *, decision)` with no `**kwargs`; passing `profile_id=`, `ordinal_profile_binding=`, `profile_attribution_halt=`, `aps_head=`, `payload=` or `declared_version=` raises `TypeError`; no caller-selected APS head, profile, binding, flag or version can reach the canonical payload (the only sources are the re-verified decision and the module-level snapshot) |
| C-23 | (R1, B11) ordering: a recording double proves the v3 canonical payload (and its bytes) is built only after authority verification, exact-type check, `_verify_sealed_decision` and consumability revocation; an unknown stage profile id in the snapshot resolves as `PRE_CREATE` failure with no fallback; declared version is `null` iff the sealed id is `null` |
| C-24 | (R1, B11) an `EVIDENCE_REFUSED` ordinal's binding is exactly `NO_RUN_EVIDENCE` whatever its in-memory profile fact, and no refusal or run artifact is ever read to build the closure (recording filesystem double) |
| C-25 | (R1, B11) profile-ledger facts are captured by local assignment from the in-memory `Cfg1RunOutcome` before L29; they cannot be supplied through `Cfg1RunAdmission`, a public argument of `run_cfg1_stage` or any writer, or run-record parsing (signature and static audits; mutated admission objects never reach the ledger); no module-level sealer exists (import surface audit); the seal-once history and consumability registries keep their frozen meanings (existing T-124…T-141 regressions pass unchanged in intent) |
| C-26 | (R1, B12) no runtime module (P, gate, L1, L14, L21A, runner, writers) references or reads `<STAGING>` (static audit) |
| C-27 | (R1, B10) the PE-2c namespace-precheck primitive used by G9: takes only the id, validates the frozen grammar and the burned A1–A4 set, derives the path only from `stage_output`'s audited `RESULTS_ROOT`, observes no-follow, returns one closed code, creates and writes nothing, and never calls `establish_stage_output_authority` |

### 26.4 PE-6 launcher acceptance requirement (R1, B10; audit corrected R2, B14)

**The authority property is VALUE uniqueness plus use-site binding — never
grammar membership.** Let `ID` be the one exact fresh execution-id value frozen
in the PE-6 authorization. The PE-6 authorization's review (and any launcher
test it authorizes) must mechanically prove, over the exact launcher bytes bound
by `LAUNCHER_SHA256`, by AST analysis of the launcher module:

```text
U1  assignments whose target is Name("BOUND_STAGE_EXECUTION_ID")   == exactly 1
    and that one assignment is a plain module-level
        BOUND_STAGE_EXECUTION_ID = "<ID>"
    whose right-hand side is an ast.Constant with type(value) is str and value == ID

U2  ast.Constant nodes with type(value) is str and value == ID      == exactly 1
    and that Constant IS the right-hand side of the U1 assignment

U3  the G9 precheck call's execution-id argument
        == ast.Name(id="BOUND_STAGE_EXECUTION_ID", ctx=Load)

U4  the establish_stage_output_authority(...) call's
        stage_execution_id keyword argument
        == ast.Name(id="BOUND_STAGE_EXECUTION_ID", ctx=Load)

U5  no other binding or mutation path exists for BOUND_STAGE_EXECUTION_ID:
        no second Name(..., ctx=Store), no Name(..., ctx=Del), no AugAssign,
        AnnAssign, NamedExpr (walrus), for/with/except/import target,
        global/nonlocal rebinding, function parameter of that name, or
        setattr/globals()/vars()/module-dict write targeting it
```

Both U3 and U4 must refer to **that one module-level constant**. Neither call
may receive another string literal, an alias carrying a copied id, a computed
value, a parameter, an environment value, file content, a second constant
holding the same id, or any other independently derived identifier. String
literals whose value is **not** `ID` are **not counted**, even when they satisfy
`[A-Za-z0-9_-]{1,64}`.

**Acceptance examples (normative):**

| Launcher content | Audit result |
|---|---|
| `stage_id="S1"` | allowed (value ≠ `ID`) |
| `"HPP-1"`, `"PI-PC1"`, `"CFG1-CC1"`, `"G9_BOUND_ID_INVALID"` | allowed |
| any other unrelated grammar-valid literal | allowed |
| a second `Constant` whose value equals `ID`, anywhere | **REFUSE** (U2) |
| G9 precheck given a copied literal `"<ID>"` | **REFUSE** (U2, U3) |
| establishment given a copied literal `"<ID>"` | **REFUSE** (U2, U4) |
| a second constant, e.g. `OTHER = "<ID>"`, even if unused | **REFUSE** (U2) |
| `ALIAS = BOUND_STAGE_EXECUTION_ID` then `ALIAS` passed to either call | **REFUSE** (U3/U4 require the exact `Name`) |
| a computed id (concatenation, formatting, `os.environ`, file read, argument) at either call | **REFUSE** (U3/U4) |
| any reassignment, augmented assignment or deletion of `BOUND_STAGE_EXECUTION_ID` | **REFUSE** (U1, U5) |

In addition, as in R1: G9 runs after G8 and before establishment, and every G9
refusal exits without calling establishment (not consumed); and the operator
A-item's absence check names the identical value `ID`.

**B10 is not weakened:** exactly one authorization-bound execution id; G9 and
establishment consume the same source; G9 remains pre-consumption waste
avoidance; `establish_stage_output_authority` remains independently fail-closed
(CFG1 §16.3.6); A1–A4 remain burned (G9 step 1); PE-1 still selects and
reserves no future id.

---

## 27. Residuals explicitly accepted (not expanded here)

| Id | Residual |
|---|---|
| R-EXT-1 | undeclared or dynamic bare-specifier resolution upward, **including** a subpath of a contained package that is not satisfiable inside the nested copy (§6.6 package-granularity precision) |
| R-EXT-2 | constructed-path loads outside the payload (relative escape, absolute, `file:`, `createRequire`, `fs`+`vm`/`eval`, WASM by path, alternate data streams) |
| R-EXT-3 | `node.exe`, built-ins, OS libraries (Node identity-pinned per proof, never byte-pinned) |
| R-EXT-4 | CommonJS global folders; the home directory is not identified |
| R-EXT-5 | Pi configuration/extension/skill/prompt discovery outside the payload (governed by CFG1 isolation and H1) |
| R-EXT-6 | processes Pi spawns |
| R-ABA | A→B→A mutation inside a walk, between L14 and L21A, or between the child's exit and L21A (slightly widened by L22–L24, F-18) |
| R-SLIVER | the L14 → `Popen` check→use window, now spanning the payload walk (F-12) |
| R-COST | full payload hashing at gate, L1, L14, L21A per ordinal, bounded by §4.4 |
| R-GATE-L1 | a payload change between gate and L1 consumes the authorization (existing residual) |
| R-REVIEW | PMD finding truth and the adequacy of re-acquired evidence are review, not mechanism (F-16) |
| R-SHARED | AIDO cannot stop other projects modifying the shared global installation (F-3) |
| R-METADATA | OS access-metadata updates and redirector I/O during reads (no AIDO write) |
| R-NAMESPACE-RACE | (R1) the bound execution directory created by another process after G9 and before establishment: establishment still refuses (CFG1 §16.3.6), but after consumption |
| R-STAGING-RESIDUE | (R1) a discovery write sequence interrupted mid-way leaves earlier candidate files as residue; nothing deletes them; a repeat discovery of that fingerprint refuses until the operator resolves them |

---

## 28. Mandatory adversarial analysis

Each case was reasoned against the current CFG1 contracts. "Blocker" means a
finding that could falsify profile authority, profile evidence, lifecycle
closure, sensitive cleanup or stage correctness.

| # | Case | Outcome under PE-1 | Rule | Blocker? |
|---|---|---|---|---|
| 1 | payload file changed outside `PI-SC1` | new `payload_fingerprint` → `PI_PROFILE_UNAPPROVED`; floor `C3_SEAM_EQUAL` | §4.5, §8.2 | no |
| 2 | `package.json` byte-only difference | new profile; C2 with one `RAW_BYTES` | §8.3, §10.2 | no |
| 3 | permitted value changes | C2; `VERSION` / `INTERNAL_DEPENDENCY` + `RAW_BYTES`; PMD mandatory | §8.3, §10 | no |
| 4 | dependency key add/remove | not C2 → at least C3; an approval labelled C2 refused; PMD with such a delta refused | §8.3, §10.4 | no |
| 5 | malicious dependency names | parser refuses before any path; C5; committed exposure not round-tripping refuses the chain | §6.3 | no |
| 6 | malformed JSON / type / truthiness | strict parsers; exact types; no coercion | §6.2, §7.3 | no |
| 7 | duplicate keys | refused at any depth (manifest → C5; policy → chain refused) | §6.2, §7.3 | no |
| 8 | case-fold collisions | payload unobservable; inventory refused by loader | §4.2 | no |
| 9 | reparse anywhere in payload | `PI_PAYLOAD_UNPROVEN`; never followed | §4.3 | no |
| 10 | enormous trees/files | refused at the bound, never truncated | §4.4 | no |
| 11 | unapproved profile | gate/L1 refuse before credentials; onboarding remedy | §13, §14, §25 | no |
| 12 | retired profile | not in eligible set → `PI_PROFILE_UNAPPROVED`; discovery C1R | §9.6, §8.2 | no |
| 13 | two approved profiles | exact fingerprint match; each matches only its own tree | §11.1 | no |
| 14 | profile swap gate → L1 | L1 re-proves; approved B fixes the stage profile (ordinal 1); unapproved → consumed refusal (R-GATE-L1) | §14 | no |
| 15 | profile swap ordinal → ordinal | `PI_PROFILE_CHANGED_WITHIN_STAGE` before credentials; stage halts | §14.2 | no |
| 16 | profile swap L1 → L14 | L14 equality with L1's profile refuses, even for an approved profile | §15.1 | no |
| 17 | persistent mutation during runtime | L21A `CHANGED` → `INDETERMINATE_PI_PROFILE`; halt | §15.2, §17 | no |
| 18 | A→B→A runtime mutation | undetected; accepted R-ABA | §27 | no (residual) |
| 19 | APS tampering (working tree, commit, in-process) | A-items clean-tree/HEAD pin; loader chain refusal at import; sealed snapshot never re-read | §9.5, §11.4, §23 | no |
| 20 | APS head mismatch | G6A refuses, not consumed | §22.2 | no |
| 21 | policy directory stray file | chain refused → import fails → G4 | §9.2 | no |
| 22 | forged profile/approval id | recomputed ids refuse | §9.4 | no |
| 23 | stale/malformed evidence reuse | premise verification against `N−1`; closed schema | §9.5, §9.3 | no |
| 24 | PMD missing one delta | exact list equality refuses | §10.4 rule 1 | no |
| 25 | PMD inconsistent with reuse | rules 5–7, 10 refuse | §10.4 | no |
| 26 | malformed L21A result | step-local → `UNPROVEN`; validator refuses out-of-domain; item 1A fails closed | §15.2, §17.1 | no |
| 27 | L21–L24 failure before L21A | L21A still attempted once; L21 failure → at best `UNPROVEN` | §15.2 | no |
| 28 | L21A failure before L25 | L25–L27 still run | §15.2, §18 | no |
| 29 | `PI_PROFILE_CHANGED_WITHIN_STAGE` mistaken for a P failure | separate namespace; refused as a `PiProofResult` code; never a gate value | §12 | no |
| 30 | unexpected gate return mistaken for a proof result | not a proof code, not a durable value; launcher exact-equality | §12.2, §22.3 | no |
| 31 | v3 evidence claiming full Node/runtime identity | B7 literals mandatory; forbidden wording audit | §19.1 | no |
| 32 | old v1/v2 evidence reinterpreted under v3 | exact-pair dispatch; binding verifier refuses v1/v2 | §19.2, §21 | no |
| 33 | policy bytes changed by EOL conversion | loader refuses CR; `-text` rule; head binds committed bytes | §7.4 | no (frozen here) |
| 34 | Git cannot track empty policy subdirectories | absent iff unreferenced | §9.2 | no (frozen here) |
| 35 | approval depending on a same-revision sibling or retired reference | references resolve against `N−1` eligible state | §9.5 | no (frozen here) |
| 36 | unexpected L1 failure before P's commit vs PE-0's `Allowed(F)` | R3-S4 refines, preserving AMEND1 R-S4 | §19.3 | no (resolved here) |
| 37 | seventh halt code vs CFG1 §19.5 closure | v3-only vocabulary under this authorized amendment; six-code objects unchanged | §17.3–§17.4 | no (resolved here) |
| 38 | halt precedence hides the profile cause | independent `pi_profile_attribution_halt` | §20.2 | no |
| 39 | CommonJS subpath fall-through for a contained package | classified into R-EXT-1; evidence forbidden from subpath-level claims | §6.6, §27 | no (residual) |
| 40 | test-only loader entry used to inject a policy | module-private; single production call site audited; G6 identity of the snapshot and its directory | §9.1, §22.1 | no |
| 41 | (R1, B10) generic admission checks the burned A4 path while the fresh namespace is already occupied | the only generic check is `RESULTS_ROOT\<BOUND_STAGE_EXECUTION_ID>` (A-item + G9), not consumed on refusal | §22.4, §23.1a | closed by R1 |
| 42 | (R1, B10) launcher prechecks one id and establishes another | one constant used for both; AST audit | §22.4, §26.4 | closed by R1 |
| 43 | (R1, B10) namespace created between G9 and establishment | establishment refuses (CFG1 §16.3.6) after consumption; R-NAMESPACE-RACE | §23.1a, §27 | no (residual) |
| 44 | (R1, B11) a caller holding a genuine authority mutates a genuine decision's profile id, binding or attribution flag | type-exact `_bound_fields()` re-proof → `DECISION_FIELD_MISMATCH` | §20.3 | closed by R1 |
| 45 | (R1, B11) a caller passes a chosen APS head, profile, binding or flag to the writer | writer surface is `(authority, *, decision)` only; policy fields writer-derived from the sealed snapshot | §20.3 | closed by R1 |
| 46 | (R1, B11) a refused run record or a mutated admission object becomes closure profile authority | `NO_RUN_EVIDENCE` for non-emitted ordinals; ledger filled only from in-memory outcomes before L29 | §14.3, §20.2 | closed by R1 |
| 47 | (R1, B12) discovery steered to write outside the staging area (`..`, absolute, drive, UNC, another repo, `<POLICY_DIR>`) | no output parameter; fixed `__file__`-derived `<STAGING>`; validated names; exclusive create only | §9.10 | closed by R1 |
| 48 | (R1, B12) a planted candidate file or a staging junction grants authority or redirects writes | staging is never read by loader/runtime; reparse refuses before any write | §9.10 | closed by R1 |
| 49 | (R1, B13) PE-2a acceptance blocked on the PE-2b loader | A-9 tests PE-2a primitives only; loader integration is B-14/B-15/B-16 | §26.0 | closed by R1 |
| 50 | (R2, B14) the PE-6 uniqueness audit counts every grammar-valid literal, so a correct launcher (`stage_id="S1"`) is refused — or a reviewer weakens the audit ad hoc to pass it | audit is value uniqueness + use-site binding: exactly one `Constant` equal to the exact bound id, as the RHS of the one `BOUND_STAGE_EXECUTION_ID` assignment; G9 and establishment both consume that `Name`; no rebinding; unrelated literals not counted | §26.4 | closed by R2 |

**No PE-1 blocker remains.** Findings 33–40 are closed by the exact
requirements above or classified into accepted residuals, findings 41–49
record the R1 closure of B10–B13 (with one accepted residual, 43), and
finding 50 records the R2 closure of B14; none
falsifies profile authority, profile evidence, lifecycle closure, sensitive
cleanup or stage correctness.

---

## 29. Explicitly not authorized by this document

1. Any implementation, test, production-code, data, `.gitattributes`, roadmap,
   governance or `CLAUDE.md` change; any edit of PE-0 or any frozen/historical
   document or evidence.
2. Creating APS data, genesis, profiles, inventories, bundles, seam evidence,
   approvals, retirements or candidate records.
3. Inspecting, walking, hashing or qualifying the installed Pi; running Pi,
   Node, npm or `pi --version`; installing, restoring or downgrading anything.
4. Contacting B300 or any backend or model; reading any credential or endpoint.
5. Producing, running or consuming an A4 launcher; reusing `CFG1-S1-A4`;
   choosing or reserving any live execution id; any live authorization.
6. A generic harness abstraction; semver ranges, compatibility matrices,
   auto-revalidation; automatic transfer of any conclusion or automatic
   evidence reuse.
7. Branch, commit, push or PR by any agent.

---

## Status

```text
PE-0 / HPP-1                               ACCEPTED / FROZEN — not edited, not reopened

B10                                        CLOSED BY PE-1 R1
B11                                        CLOSED BY PE-1 R1
B12                                        CLOSED BY PE-1 R1
B13                                        CLOSED BY PE-1 R1
B14                                        CLOSED BY PE-1 R2

PE-1                                       CANDIDATE R2 / PENDING INDEPENDENT REVIEW
PE-1 BLOCKERS                              NONE KNOWN AFTER R2

NAMESPACE ADMISSION (R1)                   RESULTS_ROOT\<BOUND_STAGE_EXECUTION_ID> ABSENT
                                           (A-item + G9; one launcher literal; not consumed on refusal)
PE-6 ID AUDIT (R2)                         value uniqueness + use-site binding of BOUND_STAGE_EXECUTION_ID;
                                           unrelated grammar-valid literals not counted
STAGE-CLOSURE AUTHORITY (R1)               profile id, ordinal binding, attribution halt bound into
                                           _DecisionMintRecord + CFG1StageClosureDecision + _bound_fields();
                                           writer surface (authority, *, decision); declared version: design B
DISCOVERY WRITE BOUNDARY (R1)              <ROOT>\experiments\pi_harness_cfg1\pi_profile_candidates only;
                                           exclusive create; NON-AUTHORITY
PHASE OWNERSHIP (R1)                       PE-2a acceptance independent of PE-2b (§26.0)
SUPERSEDED (profile-aware runs only)       CFG1 §14.1 item 2 (Pi bullet), CFG1 §14.2,
                                           FU1 R6 §2 (pin phrase), FU1 R6 §17 item 6,
                                           AMEND1 banner pin bullet, AMEND1 §7.4, AMEND1 §19 item 5
PRESERVED                                  P executes nothing; no --version; runtime/model
                                           versions never authority; v1/v2 meanings
HPP-1 EXTENSIONS (v3 only)                 X-1 leaf set · X-2 classification row 2A ·
                                           X-3 admission 1A + seventh halt code · X-4 v3 records
LITERALS                                   HPP-1 · PI-PC1 · PI-SC1 · CFG1-CC1 · record kinds §3
PROFILE AUTHORITY                          BOUNDED: package payload + declared-resolution boundary
EXTERNAL RUNTIME RESIDUAL                  NOT_IDENTIFIED_BY_PROFILE (every v3 record)
PE-2a / PE-2b / PE-2c                      NOT AUTHORIZED (each needs its own prompt)
CFG1-S1-A4                                 WITHDRAWN BEFORE CONSUMPTION / HISTORICAL ONLY / MUST NOT EXECUTE
NEXT LIVE AUTHORIZATION                    NOT AUTHORIZED; fresh id chosen only by PE-6; nothing reserved
CFG1-LIVE-S2 · Q1/Q2 · REAL-WORKSPACE      NO-GO
AR2 LIVE                                   NO-GO (OC-6)
GENERIC HARNESS ABSTRACTION                DEFERRED
```
