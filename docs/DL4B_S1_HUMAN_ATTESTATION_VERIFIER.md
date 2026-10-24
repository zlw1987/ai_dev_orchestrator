# DL-4B S1 — Human Attestation Verifier

**Status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**

| | |
|---|---|
| Baseline | `main` at `62e72d8103d2cfbc4b8392cb85e84ac3935572ac` (S0 + FU1 accepted and frozen for offline scope) |
| Contract | `docs/DL4B_REAL_INTEGRATION_BOUNDARY_DESIGN.md`: §5.1, FD-1 to FD-5, §8, slice S1 (§11) |
| Kind | Offline implementation. No store.v4, no integration session, no handoff, claim, acceptance or Alpha driver; no signing, no `ssh-keygen`, no authenticator, no subprocess, no network, no model, no account, ACL or registry change |
| New dependency | `cryptography==50.0.2` (FD-1a), pinned exactly, for Ed25519 verification only |
| Not authorized | S2 and later slices, E-6, E-12, any live run, any `CLAUDE.md` change |

S1 is the read-only verifier that decides whether one human attestation is a
human's approval of exactly one AIDO challenge. It checks an OpenSSH security-key
signature over a statement **AIDO rebuilds itself**, against an approver
registry whose protection it proves with S0's machinery. It never signs, holds
no private key, and caches nothing.

---

## 1. Modules

| Module | Role |
|---|---|
| `control_plane/attestation_v2.py` | Pure. `approval-challenge.v2`, `human-attestation.v2` (subject kinds + `exact_diff_approval`), `attestation-statement.v1` and its canonical bytes. Imports nothing outside `control_plane` and the DL-1 allowed set |
| `integration/sshsig.py` | Pure. Strict parser for the armored `SSHSIG` envelope, the `sk-ssh-ed25519@openssh.com` key and signature; reconstruction of both signed-data layers; Ed25519 verification through `cryptography` |
| `integration/approver_registry.py` | `approver-registry.v1` model and strict parser; the protected read, built from S0's own checks |
| `integration/attestation_verifier.py` | `RegistryHumanAttestationVerifier`, `VerifiedHumanAttestation`, refusal categories |

`control_plane/` does not import `integration/`; no CLI command reaches either.
The DL-4A v1 models, the frozen `HumanAttestationVerifier` protocol and every
v2/v3 store are unchanged.

## 2. Public contract

```python
RegistryHumanAttestationVerifier()                         # production: no parameter at all
RegistryHumanAttestationVerifier.from_facts(facts, *, clock)  # offline tests; records are "injected"

verifier.verify_for_consumption(*, state_root_id, challenge, attestation) -> VerifiedHumanAttestation
verifier.reprove(*, state_root_id, challenge, attestation) -> VerifiedHumanAttestation
```

- **Production construction takes nothing.** No registry, key, path, facts
  source or clock can be supplied. Each call constructs a fresh
  `WindowsSecurityFacts`, reads the code-constant
  `%ProgramData%\AIDO\approver-registry.v1.json` (`%ProgramData%` through
  `SHGetKnownFolderPath`) and uses the system UTC clock. Off Windows it refuses
  `registry_unprotected` without loading any Win32 code.
- **`from_facts`** runs the identical checks over a caller's facts source and
  clock. Its records are always `facts_origin="injected"` and never
  `is_production`, whatever the source claims. Only `__init__` can configure
  the `"windows"` origin (static test).
- **`verify_for_consumption`** is for a challenge the store is about to
  consume: AIDO's clock must be in `[issued_at, expires_at)`.
  **`reprove`** is for an attestation already consumed (FD-4): the clock is not
  compared with the challenge, and everything else, including the registry
  read and revocation, is repeated.
- **No `verify` method.** The verifier cannot be mistaken for DL-4A's v1
  protocol: a v3 authority store refuses to open with it (test).
- **`VerifiedHumanAttestation`** is a record of one successful run: minted
  only by the verifier (private token), immutable, not subclassable, not
  copyable or picklable. It carries `purpose`, the state root, challenge and
  subject, the approver, `attestation_sha256`, `statement_sha256`,
  `signature_sha256`, the key fingerprint, authenticator flags and counter,
  `user_verified`, `registry_sha256`, `identity_boundary_sha256`,
  `facts_origin`, `independent_evaluation` and `verified_at`. **It is not a
  capability.** Nobody should accept one from a caller.
- **Every refusal** is `HumanAttestationRefusedError`, a subclass of DL-4A's
  `AuthorityRefusedError` (code `authority_unproven`), with `.category` and a
  message `authority_unproven: <category>: <detail>`.

### 2.1 FD-5 obligations left to S2

S1 defines the interface; the store implements the transaction. S2 must:

1. call `verify_for_consumption` (never `reprove`) **before** opening its
   write transaction, with fresh copies of **its own persisted** challenge and
   its own `state_root_id`, never caller-built ones;
2. inside the transaction, re-check that the challenge is unconsumed and
   unexpired, and that the attestation it consumes has exactly the
   `attestation_sha256` just returned (`challenge_spent` is the store's
   category; the verifier cannot know consumption state and is not a second
   source of truth for it);
3. call `reprove` on every authoritative proof and in `recover()`, and treat a
   refusal as untrusted state (FD-4, FD-3 total revocation);
4. require `is_production` in the production integration session, and compare
   `identity_boundary_sha256` with the digest bound in the plan activation.

## 3. Pre-implementation adversarial analysis

Questions asked of every authority-bearing object: who creates it, what
independent provenance it has, whether a supported caller can bypass it,
whether two valid objects can disagree, where it is re-validated, and what a
diagnostic could disclose.

| Object | Threat | Answer |
|---|---|---|
| **Registry file and ancestors** | A, X or O writes, appends, deletes, renames, re-permissions or takes over the file, its directory or any ancestor; a reparse point, hard link, short name or redirected final path substitutes another file; a caller supplies an alternate registry | Read from one handle that denies write sharing; S0's token, boundary, identity and anchor checks first; then the file must be admin-owned, one link, at its exact final path, at most readable by A, X and O, and not replaceable through any ancestor (`not_replaceable` for all three roles, including `WRITE_DAC`, `WRITE_OWNER` and owner-implicit rights). The path is a code constant. Bytes are parsed only after protection is proven |
| **Process** | Elevated, filtered-admin, high-integrity, privileged or non-A process; an unreadable fact | S0's `_check_token` and `_check_identities`; any facts exception or wrong type refuses |
| **Registered key** | Software `ssh-ed25519` key; key made for `ssh:` login; the same key under two entries or two approvers; a fingerprint not matching its key; a small-order Ed25519 point | Only `sk-ssh-ed25519@openssh.com`; application exactly `ssh:aido-approval` in both the entry and the key blob; fingerprint recomputed and compared; one entry per key; small-order points refused |
| **SSHSIG envelope** | Wrong magic or version, non-empty reserved field, other hash, other namespace, truncated or oversized length fields, trailing bytes at any level, non-canonical base64, mixed line endings | Strict reader: every length bounded by what remains, every nested string consumed exactly, no trailing bytes; version 1, `sha512`, reserved empty, namespace `aido-approval@v1`; canonical base64 only |
| **FIDO signature** | Signature type substitution (`ssh-ed25519`, `webauthn-sk-…`), flags or counter rewritten after signing, a different relying party (application), missing presence, missing PIN, extension or backup flags | Type exactly `sk-ssh-ed25519@openssh.com`; Ed25519 over `SHA256(application) ‖ flags ‖ counter ‖ SHA256(sshsig_data)` with the **registered** application; flags judged only after the signature proves them: presence required, UV when the entry requires it, any other bit refused |
| **Canonical statement** | Signature over another state root, challenge, subject, kind, approver, key, timestamp or phrase; two spellings of one instant | The statement is never an input. AIDO rebuilds it from its own challenge, its own state root id, the attestation and the registry fingerprint, in canonical JSON with UTC microsecond `Z` times. A valid signature over any other statement fails as `signature_invalid` |
| **Challenge** | TTL other than 60 minutes; attestation for a different challenge, subject or phrase; forged `attested_at`; expired challenge; clock before issuance | v2 model fixes `expires_at = issued_at + 60 min`; field agreement is `statement_mismatch`; `attested_at` must be inside the challenge (both modes) and not after AIDO's clock (consumption); `now >= expires_at` is `challenge_expired` |
| **Approver status** | Revoked key; key outside its window; rotation; key deleted; key reassigned to another approver; stale registry state | Re-read on every call. Revocation total, in both modes. The window must cover the **whole** challenge (`not_before <= issued_at` and `expires_at <= not_after`): those are AIDO's instants, not the signer's, so re-proof is deterministic |
| **Verifier result** | A caller constructs, mutates, subclasses, copies or pickles a success record; a caller supplies a success flag; injected facts claim to be Windows | Private-token record; no success flag anywhere; origin fixed by constructor |
| **Inputs** | Subclasses, `model_construct` objects, objects mutated after validation, v1 models, dicts, JSON strings, `str` subclasses | Exact-type check, then field-by-field re-validation into a fresh object; anything else is `input_invalid` |

**Counterexamples constructed** (each is a test): malformed binary lengths
(every truncation of a valid blob, `0xFFFFFFFF` and over-bound lengths, 31/33
byte keys, 63/65 byte signatures); duplicate JSON keys and duplicate key
entries; trailing bytes on envelope, key and signature; unsupported algorithms
(version 0/2, `sha256`, `SHA512`, `ssh-ed25519`, `webauthn`); signature
substitution (another approver's key, an unregistered key, a bit flip,
re-signed flags/counter/application); wrong application (`ssh:`,
look-alikes); missing presence; forged timestamps; stale registry state
(revocation, rotation, deletion, reassignment, replacement between proofs);
mismatched state roots; revoked keys; unexpected Python types; filesystem
substitution (reparse, link, redirected final path, directory, short name);
ancestor take-over; caller-supplied trust.

## 4. What is checked, in order

1. **Inputs.** Exact types; fresh re-validated copies; `state_root_id` exactly
   32 lowercase hex characters in an exact `str`.
2. **Statement fields.** Challenge id, subject kind and digest, phrase.
3. **Timestamps.** `issued_at <= attested_at <= expires_at`; for consumption
   also `issued_at <= now < expires_at` and `attested_at <= now`.
4. **Proof structure.** Armor, canonical base64, SSHSIG v1, key and signature
   types, `sha512`, empty reserved field, no trailing bytes; then namespace.
5. **Registry** (I/O begins here; nothing above reads a fact): platform, token,
   `identity-boundary.v1` and anchor, identities, then the registry file's
   protection, then its strict parse.
6. **Key.** Approver id has entries; exact public-key blob match (a same-key,
   other-application blob is `application_mismatch`); not revoked; window
   covers the challenge.
7. **Signature.** Ed25519 over the rebuilt nested signed data.
8. **Flags.** No bit beyond UP/UV; UP set; UV if required.
9. **Record.** `verified_at` from the clock.

## 5. Refusal categories

§5.1's nine are kept with their meanings: `registry_unprotected`,
`key_unknown`, `key_revoked`, `signature_invalid`, `presence_missing`,
`namespace_mismatch`, `statement_mismatch`, `challenge_spent` (reserved for
the store), `challenge_expired`. Refinements, so each test and audit line
names one check:

| Category | Meaning |
|---|---|
| `registry_unreadable` | No registry at the code-constant path |
| `registry_malformed` | Not a strictly valid `approver-registry.v1` |
| `input_invalid` | Wrong type, constructed, mutated or v1 input |
| `timestamp_invalid` | `attested_at` outside the challenge or after the clock; clock before issuance or unusable |
| `proof_malformed` | Armor, base64 or wire-format violation |
| `algorithm_unsupported` | Other key or signature type, SSHSIG version or hash |
| `application_mismatch` | The registered key, created for another FIDO application |
| `key_not_valid` | The entry's window does not cover the whole challenge |
| `user_verification_missing` | The entry requires UV and the authenticator did not assert it |
| `flags_unsupported` | A flag other than UP or UV |

`registry_unprotected` raised by an S0 check carries the S0 message
(`isolation_unproven:<category>: …`) as its detail. Messages name categories,
roles, SIDs and fingerprints; never the proof, a key blob, registry or
boundary bytes, environment contents, or the text of a facts exception (all
re-raised `from None`).

## 6. Provisioning assumptions

These are prerequisites for E-5/E-6; S1 refuses if they do not hold.

1. **Registry location and ownership.** `%ProgramData%\AIDO\approver-registry.v1.json`,
   beside `identity-boundary.v1.json`, owned by SYSTEM, Administrators or
   TrustedInstaller (set explicitly if the "object creator" owner policy is in
   force), one hard link, readable at most by A, X and O, in the S0-proven
   anchor directory. Every S0 anchor prerequisite applies.
2. **Registry format.**

   ```json
   {"schema_version": "approver-registry.v1",
    "approvers": [{
      "approver_id": "…",
      "public_key": "sk-ssh-ed25519@openssh.com AAAA…",
      "application": "ssh:aido-approval",
      "fingerprint_sha256": "SHA256:…",
      "require_user_verification": true,
      "not_before": "2026-11-01T00:00:00Z",
      "not_after": "2027-11-01T00:00:00Z",
      "revoked": false}]}
   ```

   UTF-8, no BOM, no duplicate keys, 1–64 entries. `public_key` is the `.pub`
   line **without its comment**. Instants are RFC 3339 with an offset.
3. **Key generation.** `-t ed25519-sk -O application=ssh:aido-approval` on the
   signing device, by the human (FD-2). AIDO never sees the private part.
   Setting `require_user_verification` needs a key that asserts UV (PIN).
4. **Signing.** Namespace `aido-approval@v1` over the exact statement bytes
   AIDO presents (S2/S7 present them; S1 only defines them).
5. **Rotation.** Close the old entry's window (`not_after`) or set `revoked`;
   do **not** delete it. A deleted entry makes every earlier attestation by
   that key unverifiable (`key_unknown`), which `recover()` treats as
   untrusted. Revocation is total and retroactive by design (D-11).
6. **Windows must cover whole challenges.** A key whose window ends inside a
   challenge's 60 minutes refuses for that challenge.

## 7. Tested vectors

`tests/test_dl4b_s1_attestation_verifier.py`, 240 cases. Signatures come from
**test-only software Ed25519 keys** (seeds `sha256(b"aido-s1-test-key-N")`)
that emulate the authenticator: the test builds the FIDO authenticator data
and the SSHSIG signed data with its own code, independent of `sshsig.py`.

- **Known-answer vectors.** The exact statement bytes; key 1's public-key line
  and fingerprint (`SHA256:AZJl4ebxCEJg9+Vo7cxvoi6nJYQCnw+Wkb2HccGNIk0`); the
  exact armored SSHSIG of the `plan_activation` statement (flags `0x05`,
  counter 42), reproduced deterministically and verified; the nested signed
  data rebuilt by hand and checked with `cryptography` directly.
- **Valid forms.** Every subject kind; LF and CRLF armor; line widths 64/70/76;
  no final newline (all the same `signature_sha256`).
- **Structure.** 15 malformed armors; non-canonical base64 of a valid blob;
  every truncation; 14 envelope/signature mutations; 9 public-key blob
  mutations; 63/65-byte signatures; oversize lengths; 400 random mutations,
  none accepted.
- **Signature, identity, flags.** Bit flip; flags, UV, counter and application
  rewritten after signing; a valid signature over another state root,
  approver, subject, challenge, kind, time, fingerprint or application;
  another approver's key; unregistered key and approver; application
  look-alikes; presence and UV; 8 unsupported flag sets; counter recorded.
- **Challenge and time.** Field disagreement; forged `attested_at` in both
  modes; future `attested_at`; TTL boundary to the microsecond; clock before
  issuance; naive, string, `None`, integer and raising clocks; typed phrases
  and digests as proofs.
- **Registry content.** 10 malformed documents; 20 malformed entries; one key
  twice; missing registry; parser messages without registry bytes.
- **Revocation and rotation** across repeated calls on one verifier instance:
  revoke → refuse (both modes) → un-revoke → accept (nothing cached); other
  approvers unaffected; 5 window violations; offset-equivalent instants; full
  rotation (old key's re-proof survives a closed window, old key refused for a
  new challenge, new key accepted, deleted entry untrusts); reassignment.
- **Protection.** File writable/appendable/deletable/re-permissionable/
  takeable by A, X, O or `Users` (20 cases); directory `DELETE_CHILD` for each
  role; `WRITE_DAC`/`WRITE_OWNER` on `C:\` and `C:\ProgramData` for X; an
  X-owned ancestor; non-admin owners; reparse, link, redirect, short name,
  directory; X able to plant files; inheritable X rights; a protected file
  under a deletable directory; elevated, filtered, high-integrity, privileged,
  X- or O-run, administrator-member tokens; unprotected, malformed or missing
  identity boundary; X's account not computable; X's rights through a real
  group; every facts method raising; wrong fact types; non-Windows facts;
  re-reads per call; registry replaced between proofs; AuthZ union.
- **Bypass.** Record and verifier forgery/mutation/subclass/copy/pickle/
  re-configuration; injected facts claiming Windows; DL-4A v3 store refuses the
  verifier; v1 models; constructed, mutated, subclassed, dict and JSON inputs;
  malformed state root ids; a mutated-but-valid attestation judged on its
  real contents; disclosure scan of refusal messages; the §9 regressions.
- **Production entry point.** No parameter; refuses off Windows without
  loading Win32; on this development host refuses (no provisioned registry,
  boundary or authority account) using only read-only fact methods; malformed
  input refused before any fact is read.
- **Static.** No subprocess, socket, HTTP, `ctypes`, `os`, environment,
  file-writing, signing or private-key name in any S1 module; no harness or CLI
  import; the only `cryptography` names are `Ed25519PublicKey` and
  `InvalidSignature`; the pin; the registry check reuses S0 and adds no rights
  evaluator; code-constant location; only the production constructor mints
  `"windows"`; no CLI or control-plane module reaches S1.

S0's module-set test was extended by exactly the three S1 module names; no
other S0 test changed.

## 8. Implementation choices the reviewer should confirm

1. **S0 internals reused, S0 unchanged.** `approver_registry.py` calls S0's
   `_Run`, `_check_platform`, `_check_token`, `_read_boundary`,
   `_check_identities`, `_check_anchor`, `limit_object` and
   `not_replaceable`. These are private names of a frozen module, so a future
   S0 change must keep them (the static test pins their use).
2. **No environment check.** FD-5 makes the verifier read no environment.
   S0's step-6 environment check stays the integration session's job (S2).
   Session, process-DACL and code-load checks are likewise S0's at session
   open; the verifier proves only FD-2 (a)–(e).
3. **Stricter than the minimum.** Registry application fixed to
   `ssh:aido-approval`; flags beyond UP/UV refused; SSHSIG reserved field must
   be empty; registry rights limited for O as well as A and X.
4. **Validity window = the whole challenge**, not the signer-supplied
   `attested_at`, and not the clock at re-proof.
5. **Armor tolerance** is limited to LF/CRLF and line widths ≤ 76; the record's
   `signature_sha256` identifies the signature independently of wrapping.
6. **Refusal subclasses `AuthorityRefusedError`**, so S2 can propagate it as
   `authority_unproven` unchanged.

## 9. Post-implementation adversarial review

A second pass over the actual code, looking for any path to success or any
non-refusal outcome:

| Id | Finding | Severity | Fix and regression |
|---|---|---|---|
| R-1 | A facts source that is not one (`None`, an object lacking a method) raised `AttributeError` out of the verifier instead of a refusal: S0's `run.call(…, run.facts.x)` evaluates the attribute before its guard | Fail-closed but outside the refusal contract | Any non-registry exception while reading facts is `registry_unprotected`. `test_r1_*` |
| R-2 | Re-validation by `model_dump_json()` made pydantic print a serializer warning containing the unexpected value, so a constructed attestation with `proof=b"…"` printed proof bytes to stderr | Diagnostic disclosure | Re-validation is field by field (`model_validate`), no serializer. `test_r2_*` asserts no warning and no output |
| R-3 | Checked: a `str` subclass overriding `__eq__` as `state_root_id` | None (already refused by the exact-type check) | `test_r3_*` pins it |

Also re-examined and found sound: the registry window and revocation use the
matched entry only, and one key has one entry; flags are judged only after the
signature proves them; namespace and hash are inside the signed data; the
statement uses the registry fingerprint, which equals the one computed from
the exact matched blob; no refusal chains an exception; the clock is read only
for consumption bounds and `verified_at`.

## 10. Residuals and the remaining E-6 gate

- **Real-authenticator interoperability is unproven (E-6).** The wire formats
  follow `PROTOCOL.sshsig` and `PROTOCOL.u2f` and the KATs are self-consistent,
  but no signature from a real authenticator or from `ssh-keygen -Y sign` has
  been verified (S1 may not invoke either). E-6 must sign one throwaway
  statement with the real key and verify it here, and confirm: the key line
  and application, the armor form OpenSSH for Windows writes, the flags the
  authenticator sets (S1 refuses anything but `0x01`/`0x05`), and whether it
  asserts UV. A useful additional E-6 check, if separately authorized, is
  `ssh-keygen -Y verify` on the KAT in §7, which would confirm the format from
  OpenSSH's side.
- **Software keys are indistinguishable.** SSHSIG carries no FIDO attestation
  certificate. A software key formatted as `sk` verifies exactly like a
  hardware one; the registry (admin-written, provisioned from the human's own
  authenticator) is the only thing that makes a key a human's.
- **Same-host signing** (D-5) and **statement presentation** are outside S1.
- **Host clock** (D-8) and **restored state roots** (D-7) are unchanged
  residuals.
- **A proof is a moment.** As in S0: only A, an administrator or SYSTEM could
  change the registry after a check; every consumer re-verifies.
- **In-process code** reaching private attributes (the record token, the
  verifier's slots) is out of scope (DL-4A §2).

No frozen contract was changed. `control_plane/authority.py`, every DL-1/2/3/4A
module and every S0 module are untouched.

**Final status: IMPLEMENTED — PENDING INDEPENDENT REVIEW.**
