"""The O1 case fixture: a two-file coordinated implementation task.

Reuses ``ar2.fixtures.CaseFixture`` (the frozen AR2 dataclass) as its data
shape, and ``ar2.fixtures.build_case_repository`` /
``ar2.fixtures.remove_disposable_tree`` (the frozen AR2 disposable-root
builder/remover) to construct and tear down the repository. Nothing in
``ar2.fixtures`` is modified; O1 supplies its own :class:`CaseFixture`
VALUE, exactly the way a test module would, per
``ar2/fixtures.py``'s own documented ``build_synthetic_repository`` escape
hatch -- except O1 uses the declarative ``CaseFixture`` shape (like R1-R4)
rather than a bare file dict, since O1 has its own verification args,
protected patterns and expected-changed-paths, same as a real case does.

Task contract -- "enterprise" subscription tier
================================================

``subscription/normalize.py`` normalizes a raw tier spelling ("Pro",
" std ", ...) to a canonical tier name, and today only knows "standard" and
"pro". ``subscription/rates.py`` maps a canonical tier name to a per-seat
monthly rate in cents, and today only has entries for "standard" and "pro".
``subscription/quote.py`` composes the two (normalize, then rate-lookup,
then multiply by seat count) and is ALREADY CORRECT -- it needs no change
for a third tier to work, provided both of the modules it calls know about
one.

Adding the "enterprise" tier therefore genuinely requires editing BOTH
``normalize.py`` (so "enterprise" spellings normalize at all) AND
``rates.py`` (so the canonical name "enterprise" has a configured rate). A
single-file change to either one leaves the OTHER behavior missing, and a
change to ``quote.py`` alone cannot supply either missing behavior --
``quote.py`` has nothing to add: it already calls both functions correctly.
The independent unit tests below make this an objective, verification-
enforced property, not merely an intended one: ``test_normalize_enterprise_
variants`` and ``test_rate_enterprise`` each fail independently of the
other, and ``test_quote_enterprise`` additionally fails if EITHER underlying
behavior is missing, so it cannot be satisfied by patching only the
integration point.

``subscription/labels.py`` is an unrelated, untouched decoy module (invoice
label rendering) included so the repository is not suspiciously minimal.
"""

from __future__ import annotations

from ar2.fixtures import CaseFixture
from ar2.verification import VerificationOutcome

CASE_ID = "O1"

# -- fixture file bodies --------------------------------------------------

_INIT = '''\
"""Synthetic subscription-quoting package for the AIDO AR2-O1 broker experiment."""
'''

_NORMALIZE = '''\
"""Subscription tier name normalization."""

_CANONICAL_TIERS = {
    "standard": "standard",
    "std": "standard",
    "pro": "pro",
    "professional": "pro",
}


def normalize_tier(raw):
    """Return the canonical spelling of a subscription tier name.

    Matching ignores surrounding whitespace and letter case, so " Pro ",
    "pro" and "PRO" all normalize to "pro". Raises ValueError for a spelling
    with no known canonical tier.
    """
    key = str(raw).strip().lower()
    if key in _CANONICAL_TIERS:
        return _CANONICAL_TIERS[key]
    raise ValueError("unknown subscription tier: " + str(raw))
'''

_RATES = '''\
"""Per-seat monthly subscription rate lookup, in cents."""

RATE_CENTS_PER_SEAT = {
    "standard": 900,
    "pro": 2500,
}


def rate_cents_per_seat(tier):
    """Return the per-seat monthly rate in cents for a canonical tier name."""
    try:
        return RATE_CENTS_PER_SEAT[tier]
    except KeyError:
        raise ValueError("no rate configured for tier: " + str(tier))
'''

_QUOTE = '''\
"""Subscription quote assembly."""

from subscription.normalize import normalize_tier
from subscription.rates import rate_cents_per_seat


def quote_cents(raw_tier, seat_count):
    """Return the total monthly quote, in cents, for seat_count seats of raw_tier."""
    tier = normalize_tier(raw_tier)
    return rate_cents_per_seat(tier) * seat_count
'''

_LABELS = '''\
"""Subscription invoice label rendering."""


def format_seat_label(account_name, seat_count, tier):
    """Return a single-line invoice label string."""
    return "{0} | {1} seats | {2}".format(account_name, seat_count, tier)
'''

_TEST = '''\
from subscription.normalize import normalize_tier
from subscription.quote import quote_cents
from subscription.rates import rate_cents_per_seat


def test_normalize_standard_variants():
    assert normalize_tier("standard") == "standard"
    assert normalize_tier(" STD ") == "standard"


def test_normalize_pro_variants():
    assert normalize_tier("Pro") == "pro"
    assert normalize_tier("professional") == "pro"


def test_normalize_enterprise_variants():
    assert normalize_tier("Enterprise") == "enterprise"
    assert normalize_tier(" enterprise ") == "enterprise"


def test_rate_standard():
    assert rate_cents_per_seat("standard") == 900


def test_rate_pro():
    assert rate_cents_per_seat("pro") == 2500


def test_rate_enterprise():
    assert rate_cents_per_seat("enterprise") == 6000


def test_quote_standard():
    assert quote_cents("standard", 4) == 4 * 900


def test_quote_pro():
    assert quote_cents("pro", 3) == 3 * 2500


def test_quote_enterprise():
    assert quote_cents("enterprise", 2) == 2 * 6000
'''

_NOTES = '''\
Synthetic subscription package
===============================

This package computes monthly subscription quotes from a tier name and a
seat count. Tier-name normalization, per-seat rate lookup, quote assembly
and invoice label rendering each live in their own module.
'''

# -- TEST-SUPPORT ONLY -----------------------------------------------------
#
# The two individually-correct single-file edits, used ONLY by the offline
# suite to PROVE that a one-file change cannot satisfy the full verification
# suite (each is independently insufficient; both together are necessary and
# sufficient). The live case run NEVER uses these -- its only source of a
# file edit is the model, through the broker.
NORMALIZE_WITH_ENTERPRISE = _NORMALIZE.replace(
    '    "professional": "pro",\n',
    '    "professional": "pro",\n    "enterprise": "enterprise",\n',
)
RATES_WITH_ENTERPRISE = _RATES.replace(
    '    "pro": 2500,\n',
    '    "pro": 2500,\n    "enterprise": 6000,\n',
)
assert NORMALIZE_WITH_ENTERPRISE != _NORMALIZE
assert RATES_WITH_ENTERPRISE != _RATES

FILES: dict[str, str] = {
    "subscription/__init__.py": _INIT,
    "subscription/normalize.py": _NORMALIZE,
    "subscription/rates.py": _RATES,
    "subscription/quote.py": _QUOTE,
    "subscription/labels.py": _LABELS,
    "tests/test_subscription.py": _TEST,
    "NOTES.md": _NOTES,
}

# The two, and only two, implementation files the task genuinely requires.
EXPECTED_CHANGED_PATHS: frozenset[str] = frozenset(
    {"subscription/normalize.py", "subscription/rates.py"}
)

# A file that is write-eligible, untouched by a correct solution, and used by
# the offline suite to prove the changed-file budget still refuses a THIRD
# distinct edit even after the two genuinely-required files are both edited.
THIRD_FILE_PROBE_PATH = "subscription/labels.py"

VERIFICATION_WITNESS_PATHS: tuple[str, ...] = ("tests/test_subscription.py",)
PROTECTED_PATTERNS: tuple[str, ...] = ("tests/*", "*/tests/*", "test_*.py", "*/test_*.py")
VERIFICATION_ARGS: tuple[str, ...] = (
    "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf", "tests/test_subscription.py",
)

# The three test node-id SUBSTRINGS the seeded baseline must fail on -- one
# for each of the two independent missing behaviors, plus the integration
# test that depends on both. Order-independent; matched by substring.
EXPECTED_BASELINE_FAILING_SUBSTRINGS: tuple[str, ...] = (
    "test_normalize_enterprise_variants",
    "test_rate_enterprise",
    "test_quote_enterprise",
)

PROMPT = (
    "This repository computes monthly subscription quotes for named tiers. "
    "Today it recognizes two tiers, \"standard\" and \"pro\" (also spelled "
    "\"std\" and \"professional\"), matched case-insensitively with "
    "surrounding whitespace ignored.\n"
    "Add a third tier, \"enterprise\", recognized the same way "
    "(case-insensitive, surrounding whitespace ignored). Its per-seat "
    "monthly rate is 6000 cents.\n"
    "A quote for the enterprise tier must work correctly the same way it "
    "already does for standard and pro.\n"
    "Do not change any test file.\n"
    "Finish when the implementation change is complete."
)

O1_CASE = CaseFixture(
    case_id=CASE_ID,
    purpose=(
        "AR2D qualification follow-up. Can the same Pi + broker architecture "
        "complete ONE task that genuinely requires coordinated changes to TWO "
        "implementation files, under the unmodified accepted AR2 two-file "
        "changed-file cap? The implementation file paths are never named in "
        "the prompt; the model must discover both from the bounded manifest "
        "and the task description."
    ),
    files=FILES,
    verification_args=VERIFICATION_ARGS,
    verification_witness_paths=VERIFICATION_WITNESS_PATHS,
    protected_patterns=PROTECTED_PATTERNS,
    expected_changed_paths=EXPECTED_CHANGED_PATHS,
    baseline_expectation="seeded_failure",
    expected_baseline_failing_test=None,  # O1 uses its own multi-test contract check below
    names_the_implementation_file=False,
    prompt=PROMPT,
)


def baseline_matches_o1_contract(outcome: VerificationOutcome) -> tuple[bool, str]:
    """O1's own baseline contract check.

    ``ar2.verification.baseline_matches_case_contract`` requires EXACTLY ONE
    failing test, which is the R1-R4 single-defect shape and does not fit
    O1's two-independent-missing-behavior shape. This checks the shape O1
    actually declares: baseline verification must fail, with EXACTLY the
    three expected node ids failing (one per missing behavior, plus the
    integration test) and no other failure.
    """
    if outcome.passed:
        return False, "baseline verification passed; the seeded defect is absent"
    failed = outcome.failed_node_ids
    if len(failed) != len(EXPECTED_BASELINE_FAILING_SUBSTRINGS):
        return False, (
            f"baseline failing-test count was {len(failed)}, expected exactly "
            f"{len(EXPECTED_BASELINE_FAILING_SUBSTRINGS)}"
        )
    remaining = list(failed)
    for expected_substring in EXPECTED_BASELINE_FAILING_SUBSTRINGS:
        match = next((f for f in remaining if expected_substring in f), None)
        if match is None:
            return False, (
                f"baseline did not fail the expected node {expected_substring!r}; "
                f"observed failures were {failed!r}"
            )
        remaining.remove(match)
    return True, (
        "baseline shows exactly the three expected failures: both independent "
        "missing-behavior tests and the integration test that depends on both"
    )
