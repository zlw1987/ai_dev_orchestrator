# Phase 5F3B-CFG1 — L9 Correction Dependency Note (A2)

```text
STATUS     NON-FROZEN, ADDITIVE, SHORT. A dependency note. L9 is NOT modified.
TOUCHES    nothing in L9: cfg1_pi_config.py, win_config_authority.py, the frozen
           CFG1 design (FU15 Sec. 37) and their tests are unchanged.
```

**The finding (recorded earlier, unchanged).** L9 creates its config directory
by pathname (`Path.mkdir`), pins it, then creates `settings.json` and
`models.json` by pathname (`create_exclusive_child`), and only then runs the
handle-enumeration parentage gate; content follows the gate. FU15 accepted the
pre-gate pathname creates on W3 ("a pinned directory cannot be converted in
place"). R1-FU3 (8343db1) measured that an attribute-only open converts an
**empty** pinned directory, so W3 does not hold for creation containment
(FU4 report §8). No endpoint byte has been shown to escape: the gate still
precedes every content byte, and L9's exact sequence was never run against a
conversion.

**Dependency on F5-A A2.** If the A2 candidate is qualified, the same mechanism
is the smallest L9 correction: the config directory becomes one handle-relative
directory create from the root pin, and the two files become handle-relative
file creates from that directory's returned handle; the gate and everything
after it are unchanged. That correction **depends on the same open evidence**
(A2-3, racing conversion, platform breadth) and must not precede it.

**Authority separation (must hold in any L9 correction).** F5-A's
`pi_runtime_provision` ledger, entries and provision object are provisioning-only
and are refused by L9's issuance consumers. A shared primitive, if ever factored,
must be provenance-free (parent handle, one name, kind); L9 keeps its
`GenerationInterval` / `ProvenConfigChildren` provenance and F5-A keeps its
ledger. Neither may mint, accept or convert the other's authority. Placing a
shared primitive in the frozen `win_config_authority.py` needs its own reviewer
decision; this candidate does not do it.

**R-ALIAS stays a separate, unresolved L9 issue.** FU15 §37.1 requires that no
endpoint-bearing byte is written outside CFG1's owned root. A recorded (not
reconciled) observation shows a hard link to a held share-0 child created from
outside the root. A2 does **not** address that, and handle-relative creation
does not prevent it. It is neither dismissed nor mitigated here; no link-count
gate is proposed, and L9's containment invariant is not weakened.
