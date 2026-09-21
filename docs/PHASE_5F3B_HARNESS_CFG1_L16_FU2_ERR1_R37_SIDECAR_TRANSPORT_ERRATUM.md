# Phase 5F3B-HARNESS-CFG1-L16-FU2-ERR1 — R-37 Transport Erratum

```text
CFG1-L16-FU2-ERR1 DESIGN ERRATUM CANDIDATE — PENDING INDEPENDENT REVIEW
Supersedes: R2 §11.6, R-37, ONE SENTENCE ONLY.
Adds: ONE test-side carrier to §11.7's permitted-edit list (P-10).
Grants: NOTHING until independently reviewed and explicitly accepted.
```

This is a **new, narrow erratum**. It does **not** modify, re-label or restate
the accepted/frozen R2 design
(`docs/PHASE_5F3B_HARNESS_CFG1_L16_FU2_RUNTIME_CAPABILITY_OBSERVATION_DESIGN.md`).
R2 is read together with this file, and where they differ **on the one sentence
named in §3, or on the one added §11.7 permission stated there, this file
governs and nothing else does**.

---

## 0. Binding

| Item | Value |
|---|---|
| Amended document | `docs/PHASE_5F3B_HARNESS_CFG1_L16_FU2_RUNTIME_CAPABILITY_OBSERVATION_DESIGN.md` |
| **Primary identity anchor — its Git blob id at HEAD** | `edae72154748b7de696036ef85a64dcf858e6311` |
| Recorded for convenience — SHA-256 of that same content as checked out on this Windows machine with CRLF line endings (index stores LF; working tree is CRLF) | `f8890e790cc1eff3233e6b78db8406aa2bf9b512f6372d55dc5992cb50d57eae` |
| Implementation commit that surfaced the finding | `3a591578a95d7f3cd9181df2f92450951f7a5600` |

The frozen R2 is **the Git blob above**. The working-tree SHA-256 is that blob's
content with CRLF line endings, and it is recorded so a reader on this machine
can match bytes; it is **not** the identity anchor. (The relationship was
checked: the blob's bytes, with each LF converted to CRLF, hash to exactly that
SHA-256.)

CRLF↔LF conversion of **that exact blob's content** — a file that differs from
the blob in line-ending bytes and in nothing else — is **not** semantic or design
drift, and **does not** require a new review. Any other difference, meaning any
content that differs from that blob by anything other than that line-ending
conversion (equivalently, a different Git blob whose content is not merely that
blob re-encoded), is a re-review event: this erratum is then bound to text that
no longer exists and must be re-reviewed before it is relied on. This sentence
concerns this one blob only; it is not a general line-ending policy.

---

## 1. The contradiction

**Requirement A — R2 §11.6, R-37 (accepted text):**

> Extend the T-3 harness report with the composed model object as
> `JSON.stringify` serializes it (synthetic `.invalid` base URL only).

R-37 then requires the synthetic peer to wrap that object, unchanged, into a
`get_state` response and to drive it through the real supervisor / reader /
probe / L16 path for each of Q, R, E and H.

**Requirement B — pre-existing, frozen T-3 regression**
(`experiments/pi_harness_cfg1/tests/test_cfg1_pi_conformance.py`,
`test_t3_no_real_credential_or_endpoint_was_used_anywhere`, unchanged by
`3a59157`):

```python
serialized = json.dumps(conformance_report)
...
for forbidden in ("PI_QUALIFICATION_B300_ROUTE_KEY_VALUE", "b300", "AIDO_LITELLM"):
    assert forbidden not in serialized, forbidden
```

**The fact that joins them.** The independent implementation review found that
the actual composed model legitimately contains the frozen provider id
`b300_pi_qualification` (`PROVIDER_ID`, `pi_harness_cfg1/identity.py`). That is a
frozen public constant — not a credential and not an endpoint.

## 2. Why the two cannot literally coexist

- A requires the **exact** `JSON.stringify` serialization to be part of the
  harness report. Every serialization of that model contains
  `b300_pi_qualification`, so `json.dumps(report)` contains `"b300"`, and B
  fails.
- B cannot be edited or narrowed: R2 §11.7 forbids weakening any existing test,
  and the phase instructions preserve the broad assertion.
- A cannot be satisfied approximately: R-37's whole value is that the bytes
  entering the receive boundary are *exactly* what the installed composer's
  serializer produced. Redacting, renaming or dropping the provider id, or
  rebuilding the object from selected fields, would re-create the hand-built
  document R-37 exists to eliminate.
- Encoding the text so the substring is absent from the report (base64, hex,
  `b`-style escaping, splitting the token) is **not authorized**. It would
  exist only to evade B and would not be "as `JSON.stringify` serializes it".

The only resolution that keeps both intent-bearing requirements is to keep the
exact text **out of the harness report** while still delivering it, byte for
byte, to the Python test. That is a transport change and nothing more.

This should have been reported **before** implementation. It was instead
resolved silently in the implementation (see §7).

---

## 3. Exactly what is superseded

**One sentence**, in R2 §11.6, R-37:

> Extend the T-3 harness report with the composed model object as
> `JSON.stringify` serializes it (synthetic `.invalid` base URL only).

**Replaced, for the purposes of R-37, by:**

> For each arm, the T-3 harness writes the exact text returned by
> `JSON.stringify(model)` — the composed model object, unmodified — to a
> test-local sidecar file in the T-3 work directory, beside that arm's generated
> `models.json`. The harness report carries **only the path** of that sidecar to
> locate it. The composed model object and its serialized text are never placed
> in the report. The sidecar contains the synthetic `.invalid` endpoint
> composition only.

The next R-37 sentence ("The synthetic peer wraps it exactly as §16 establishes
Pi does …") is **kept verbatim**; "it" now denotes the **sidecar text read
verbatim**. Every acceptance condition in R-37 — `R == "TRUE"`, the correct `C`
per arm, `h2 is True`, no `reasoning` key surviving anywhere, the synthetic base
URL absent from the returned facts and from every emitted record — is unchanged.

"Only the path" governs what is **added to the report for locating the model**.
The three scalar fields the report already carried before this erratum
(`serializedModelHasCompatKey`, `serializedCompat`, `serializedModelReasoning`)
are relied on by frozen tests and **stay**; they are derived facts, not the
serialized model.

**One added permission — an addition to §11.7's permitted-edit list, not a
supersession of any R2 sentence.** R2 §11.7 names the only permitted edits to
existing tests. This erratum adds exactly one item: a single private,
test-local **Python-workdir carrier** in `test_cfg1_pi_conformance.py`, defined
and bounded by P-02 and P-10, whose sole purpose is to preserve Python's own
authority over the T-3 work directory. It is needed because the report is
produced by Node and therefore cannot be the source of the directory its own
claimed path is checked against. Nothing else in §11.7 changes.

---

## 4. The sidecar (test machinery only)

- One file per arm the harness iterates, at the fixed derived name
  `<that arm's models.json path>.composed-model.json`. The two control arms
  receive one too as a side effect of the harness's uniform loop; nothing
  consumes them and every rule here applies to them equally.
- It is **not CFG1 result evidence** and is **never** written under
  `experiments/pi_harness_cfg1/results` or anywhere in the repository.
- Its content is the exact `JSON.stringify(model)` text of the offline T-3
  fixture: the synthetic `.invalid` endpoint and the frozen provider/model
  composition. It contains no real credential and no real endpoint.
- It lives only under the pytest-managed temporary directory. It is **not**
  deleted by the test; its lifetime is pytest's own temporary-directory
  retention (see §8.1). It has no CFG1, AR2 or run-record role.
- It grants **no** runtime or filesystem authority. Nothing outside the R-37 test
  may read it; no production module may reference it.
- This is **not** a general artifact or file-handoff mechanism, and none is
  authorized: no registry, no manifest, no second consumer, no schema, no
  cross-test sharing, no production-side reader.

**Receive-boundary chain (unchanged in substance; the middle link is the
amendment):**

```text
installed Pi composer
  → exact JSON.stringify(model) bytes
  → test-local sidecar (T-3 work directory)
  → synthetic LF-terminated get_state response
  → real PiRpcSupervisor
  → real RecordStreamReader
  → real ingest_record
  → real bounded probe
  → real CFG1 L16
```

---

## 5. Provenance and containment regression (required)

The R-37 implementation regression must prove **all** of the following. Row ids
are erratum-local (`P-xx`) and do not join R2's row namespace. Where a row says
"fails", it is a test failure, never a warning.

Anchor rule for P-01/P-02: there are exactly two anchors, and **both are
Python-owned, never supplied by Node's report**:

- **containment anchor** — pytest's own `tmp_path_factory.getbasetemp()`;
- **provenance anchor** — the authoritative T-3 work directory, meaning the
  exact `Path` object that the Python fixture itself obtained from
  `tmp_path_factory.mktemp("cfg1_t3")`, carried to R-37 by the P-02/P-10
  carrier. It is **never** recovered from the reported path, from that path's
  parent, or from a directory scan or name match (a directory whose name merely
  begins `cfg1_t3` is not the authoritative work directory).

The report supplies only the *claimed* path (`serializedModelPath`). It is
verified against both anchors and never trusted.

| ID | Requirement |
|---|---|
| P-01 | **Claimed-path integrity, in this exact order; the first failure fails the test and no later step runs.** The order is: claimed report path → exact type check → the lexical path itself is not a symlink → required existence and file-type checks → strict resolution → containment checks on the resolved path. **(a) Type.** `type(claimed) is str` (a `str` subclass fails), non-empty, no NUL character, and absolute. **(b) Lexical link status, before any resolution.** `os.lstat(claimed)` — which does not follow links — is taken on the claimed path exactly as reported; `stat.S_ISLNK` must be false and, where the platform reports it, the reparse-point attribute (`st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT`) must be unset; an `lstat` error fails. Following the link is never how a symlink is detected, because `resolve()` and `stat()` follow it. **(c) Existence and type, from that same `lstat` result:** `stat.S_ISREG` must be true, so the claimed path itself names a regular file. **(d) Strict resolution:** `Path(claimed).resolve(strict=True)`; failure fails. **(e) Containment, on the resolved path only:** it lies under `tmp_path_factory.getbasetemp().resolve()`, and it is **not** inside `experiments/pi_harness_cfg1/results` and **not** anywhere under the repository root. Both sides of every comparison use `resolve()`; Windows path-case differences must not decide the outcome. These checks are read-only: they never delete, replace, repair, follow-and-accept or clean up anything. **Counterexample that must fail:** a symlink at the expected lexical location whose target is another plausible regular file fails at (b), before it is ever resolved. |
| P-02 | **Provenance against the Python-owned work directory, never a report-supplied parent.** The test holds `workdir` — the authoritative T-3 work directory of the anchor rule — and asserts (i) `conformance_report is carrier.report`, so the report the test uses and the work directory it holds come from the one fixture run; (ii) `workdir` itself is a real directory by `os.lstat` (not a symlink, no reparse point) and `workdir.parent.resolve() == tmp_path_factory.getbasetemp().resolve()`. For each arm `X` the test derives, from `workdir` and the arm id **only**, `models_X = workdir / f"models_{X}.json"` and `expected_sidecar = workdir / f"models_{X}.json.composed-model.json"`. Then, **after P-01 (a)–(e) have passed**, it requires the claimed `serializedModelPath` string to equal `str(expected_sidecar)` exactly (no normalization) **and** `Path(claimed).resolve(strict=True) == expected_sidecar.resolve(strict=True)`. The derivation never reads the claimed path's parent. `models_X` must exist, and its decoded text (`read_text`, not raw bytes — the fixture wrote it with `write_text`, which translates newlines on Windows) must equal `serialize_config_document(models_document(arm_id=X, base_url=SYNTHETIC_BASE_URL))` regenerated independently by the test. Every later step reads the sidecar **from `expected_sidecar`**, not from the claimed string. An arbitrary external path — including one that is real, readable and contains plausible JSON — fails. **Counterexample that must fail:** a `serializedModelPath` naming a *different* directory under the same pytest base directory — even one whose name also begins `cfg1_t3` and which holds a plausible regenerated `models_Q.json` and sidecar — fails here, because that directory is not the `workdir` Python created and equality with `expected_sidecar` is required. |
| P-03 | **Exact text.** The test reads `expected_sidecar.read_bytes()` (the P-02 path) and decodes strictly as UTF-8: no BOM, non-empty, no `\r` or `\n` byte (so the text is safe inside one LF-terminated frame), no leading or trailing whitespace, `"__ID__"` absent. Parsing it as a JSON object is permitted **for checks only**, and the parsed value never reaches frame construction. The parsed object must agree with the report's own scalars for that arm: `("compat" in obj) == serializedModelHasCompatKey`, `obj.get("compat") == serializedCompat`, and `obj["reasoning"] is serializedModelReasoning`. A **source check** on `cfg1_t3_conformance.mjs` proves the sidecar text is the unmodified value of a single-argument `JSON.stringify(model)` call (no replacer, no `space`, no post-processing), is the *only* string the sidecar write receives, and is the *only* input to the `JSON.parse` that yields those scalars. This proves the sidecar is the string the harness produced and that the scalars derive from that same string; it does **not** re-prove Node's serializer. |
| P-04 | **Synthetic-only content.** At least one URL-scheme token is present in the sidecar text and **every** such token equals `SYNTHETIC_BASE_URL` (host ends `.invalid`). `PI_QUALIFICATION_B300_ROUTE_KEY_VALUE`, `AIDO_LITELLM` and the synthetic API key literal are absent. Lower-case `b300` may occur **only** as the frozen `PROVIDER_ID`: after removing every occurrence of `PROVIDER_ID`, no `b300` remains. |
| P-05 | **No real credential or environment value read to create it.** The harness source contains no `process.env` reference (its only process reads are `process.argv` and `process.stdout`); the sidecar path is built solely from the config-supplied `modelsJsonPath` plus the fixed suffix; the frozen minimal-environment assertions (fixture Rule 1) and the existing `os.environ` absence assertions are retained; and the R-37 test itself reads no environment variable and no credential file. |
| P-06 | **Per-arm isolation.** Q, R, E and H have four distinct sidecar paths and four pairwise-distinct texts. In each iteration the frame is built from **that iteration's** freshly read text (no cache, no reuse across arms), contains exactly one occurrence of it, and L16's compat-shape observation equals `ARM_SHAPE[X]`. Because those shapes differ across the four arms, a crossed sidecar cannot pass. |
| P-07 | **Verbatim insertion, no parse-and-rebuild.** The frame is one expression `PREFIX + text + SUFFIX` in which `PREFIX` and `SUFFIX` are literal constants and `text` is the decoded sidecar name itself; an AST check on the R-37 test proves no call, `format`, f-string over a parsed object, `replace`, or JSON re-serialization sits in that operand's path, and no name bound to a parsed copy appears in the frame expression. The test asserts `frame[len(PREFIX):len(frame)-len(SUFFIX)] == text` and that the peer's configured response is that frame (with only the `__ID__` placeholder substituted by the probe-minted id) plus a single LF. |
| P-08 | **The existing no-`b300` assertion is unchanged.** `test_t3_no_real_credential_or_endpoint_was_used_anywhere` is byte-identical to its text at `3a59157`, still fed the whole report. Additionally, the report's `serializedModelPath` is a path string only: neither the sidecar text nor `PROVIDER_ID` appears as a serialized-model value anywhere in `json.dumps(report)` on account of this feature. |
| P-09 | **No durable-evidence entry.** After the run, `experiments/pi_harness_cfg1/results` contains no file matching `*composed-model*`; the emitted `[l16, payload]` text contains neither the sidecar path, its filename, nor its text; and a source scan of every non-test module under `experiments/` finds no reference to `composed-model` or `serializedModelPath`. A1/A2 evidence (R2 §13 digests) is untouched. |
| P-10 | **No general handoff; one narrow provenance carrier.** The report gains exactly one new field per arm (`serializedModelPath`); the R-37 test is the only consumer of the sidecar. The **only** test-side addition permitted is one private, test-local carrier (a module-scoped fixture or value in `test_cfg1_pi_conformance.py`, underscore-named) whose sole purpose is preserving Python's own T-3 work-directory authority. It holds **exactly two members**: the parsed Node report, and the `Path` that `tmp_path_factory.mktemp("cfg1_t3")` returned in the same fixture run. The existing `conformance_report` fixture continues to return **exactly the same report value** — the same object, with no key added, removed or changed, and never carrying the work directory — to every pre-existing consumer, and no pre-existing test's inputs change. Only R-37 additionally requests the carrier, and no other test may. Nothing further is permitted: no general artifact or file-handoff mechanism, no production symbol, no manifest or registry, no durable schema, no sidecar or model record held in the carrier, no cross-test authority, and no helper or fixture added for any other purpose. |

P-01…P-10 add checks to **one replaced test** and one harness, and add the one
carrier of P-10 (see the "one added permission" paragraph of §3). Apart from
that carrier they do not amend R2 §11.7's permitted-edit list.

---

## 6. Everything else stays frozen

Not reopened, not amended, not weakened:

- R2's production architecture — the probe, the reader/supervisor changes, the
  lifecycle and launch-authority rules (§5.6, §5.6.1, §5.6.2), and the
  compatibility-authority correction;
- raw-reasoning classification (§8.2), the reasoning drop, probe correlation
  (§7, §16) and R-31's source-inspection re-proof;
- the schemas, `RUN_RECORD_VERSION`, refusal vocabulary and manipulation
  predicate (§12.2);
- every other §11 row, including the L, W, S, C, R and R-38…R-40 rows, and
  R-37's own acceptance conditions listed in §3;
- §11.7's rule that no existing test may be deleted or weakened, and its
  permitted-edit list — which gains **only** the one carrier of P-10 and
  nothing else;
- §13: A1 and A2 remain consumed, non-participating, valid **historical**
  evidence exactly as recorded; A2's `runtime_reported_model_reasoning = OTHER`
  is never reinterpreted;
- §14's gates: **A3 remains NOT AUTHORIZED**; **CFG1-LIVE-S2 remains NO-GO**.

---

## 7. Observed state at `3a59157` (factual, non-authorizing)

Read-only inspection of the commit shows the transport this erratum describes
already exists, introduced during implementation without prior report:

- `tests/cfg1_t3_conformance.mjs` writes
  `${arm.modelsJsonPath}.composed-model.json` from `JSON.stringify(model)` and
  puts `serializedModelPath` in the report.
- the R-37 test reads that reported path with `read_text` and asserts only that
  the text contains `SYNTHETIC_BASE_URL` and `"reasoning":true`.

Rows **P-01…P-10 are therefore not yet satisfied**: the committed test trusts
the report-supplied path and validates none of §5, and the committed fixture
keeps its work directory as a local variable, so no Python-owned work-directory
carrier exists. This erratum does **not**
accept the committed mechanism, does **not** grant authority to change it, and
does **not** amend it. Bringing the implementation to §5 is a separate step that
requires this erratum to be independently reviewed and explicitly accepted
first.

---

## 8. Wording limits and residual limitations

1. **"Temporary" is not "deleted".** The sidecar sits under the pytest temporary
   directory and is removed only by pytest's own retention rotation. The project
   configures no retention policy, so pytest's default keeps recent base
   directories. The sidecar holds only synthetic data, so retention is harmless,
   but no document or test may claim the test deletes it.
2. **"T-3 work directory" means the exact `Path` the T-3 fixture itself created**
   with `tmp_path_factory.mktemp("cfg1_t3")` and carried to R-37 (P-02, P-10) —
   not any directory whose name begins `cfg1_t3`, and never one recovered from
   the report. It is a sibling of, not the same as, the R-37 test's own
   function-scoped `tmp_path` (which holds the synthetic peers). The sidecar is
   read **in place**, never copied.
3. **The frozen no-`b300` assertion now sees an absolute temporary path** in the
   report. It is a substring test, so it depends on the temp path not containing
   `b300`. That is inherent to carrying a path and fails closed if it ever
   occurs; it is **not** a reason to edit the assertion.
4. **Exactness is proved by proxy, not by re-serializing in Python.** P-03's
   source check plus report-scalar agreement is the mechanical evidence; Python
   cannot independently reproduce Node's `JSON.stringify` output.
5. **Link checks are limited to what P-01/P-02 name.** They reject a symlink or
   Windows reparse point at the claimed file and at the work directory. They do
   not claim to detect a hard link, and they are point-in-time checks, not a
   guarantee against a change between the check and the read.
6. **Synthetic, not live.** This still proves a synthetic frame through AIDO's
   real receive path. It is not evidence of what a live Pi process reports, and
   R-31 remains source inspection only.

---

## 9. Authority

Nothing in this document authorizes implementation, a change to any test or
production file, a live run, a Pi launch, a B300, model or network contact, or
A3. It is bound to the R2 text identified in §0 and takes effect only when it is
**independently reviewed and explicitly accepted, with the acceptance recorded
outside this file** and naming this file by the SHA-256 of its exact bytes.
`CFG1-LIVE-S2` remains **NO-GO**.
