"""The frozen IQ-1 / IQ-2 / IQ-3 synthetic task corpus (Phase 5F3B-I1, Sec. 12).

Three distinct implementer risks, one task each, no redundancy:

    IQ-1   local correctness / minimality on a precise edge contract   (1 file)
    IQ-2   discovery + coordination across genuinely-coupled files     (2 files)
    IQ-3   restraint -- recognizing that no change is required          (0 files)

Each task is a :class:`~ar2.fixtures.CaseFixture` value -- the same frozen
dataclass shape ``experiments/pi_external_runtime_ar2/ar2/fixtures.py``
defines and ``experiments/pi_external_runtime_ar2_o1/o1/fixture.py`` already
reused for its own domain. Nothing in ``ar2.fixtures`` is read-and-rewritten;
this module supplies its own ``CaseFixture`` VALUES, exactly like O1 does.

No implementation filename is ever named in a task's ``prompt`` text. Each
task's ``QualificationTask.task_revision`` is a deterministic digest over the
frozen fixture content (file bodies, prompt, verification args, expected
changed paths) -- repeated construction of the same task object always
produces the identical revision, and the offline suite proves it.

Task content is not randomized, per Sec. 12.6.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ar2.fixtures import CaseFixture
from ar2.verification import VerificationOutcome, baseline_matches_case_contract

from . import FIXTURE_SCHEMA_VERSION

SEEDED_FAILURE = "seeded_failure"
ALREADY_PASSING = "already_passing"


@dataclass(frozen=True)
class BaselineContract:
    """The frozen, STRUCTURED baseline shape a fixture must exhibit.

    Phase 5F3B-I1-FU1. This was previously carried as a per-task validator
    *callable*, which meant the exact expected-failure set lived only inside
    a function body and therefore could not participate in
    :attr:`QualificationTask.task_revision`. A baseline-contract change --
    the very thing that decides whether a fixture is usable at all -- could
    then leave the revision identical, which is exactly the silent drift a
    frozen revision exists to prevent.

    Holding the contract as data fixes that structurally, and deliberately
    without hashing Python source: the digest covers the declared contract,
    and :func:`evaluate_baseline_contract` is the single interpreter of it,
    so there is no second place for the two to disagree.
    """

    mode: str  # SEEDED_FAILURE | ALREADY_PASSING
    expected_failing_node_patterns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.mode not in (SEEDED_FAILURE, ALREADY_PASSING):
            raise ValueError(f"unknown baseline contract mode: {self.mode!r}")
        if self.mode == ALREADY_PASSING and self.expected_failing_node_patterns:
            raise ValueError(
                "an already_passing baseline contract cannot declare expected failures"
            )
        if self.mode == SEEDED_FAILURE and not self.expected_failing_node_patterns:
            raise ValueError(
                "a seeded_failure baseline contract must declare its expected failures"
            )


def _digest_task(task: "QualificationTask") -> str:
    """A deterministic revision digest over the task's frozen, declared content.

    Covers file bodies, the prompt, the verification command, the protected
    patterns, the expected-changed-path contract AND the structured baseline
    contract -- every element that defines what the task actually IS.
    Order-independent over the file dict (sorted by relative path) so the
    digest does not depend on insertion order.
    """
    case = task.case
    hasher = hashlib.sha256()

    def _add(text: str) -> None:
        hasher.update(text.encode("utf-8"))
        hasher.update(b"\x00")

    _add(task.task_id)
    _add(task.fixture_schema_version)
    _add(case.case_id)
    for relative in sorted(case.files):
        body = case.files[relative]
        _add(relative)
        _add(body if isinstance(body, str) else body.decode("utf-8"))
    _add(case.prompt)
    _add("|".join(case.verification_args))
    _add("|".join(sorted(case.verification_witness_paths)))
    _add("|".join(sorted(case.protected_patterns)))
    _add("|".join(sorted(case.expected_changed_paths)))
    _add(case.baseline_expectation)
    _add(case.expected_baseline_failing_test or "")
    # The structured baseline contract. Order-SENSITIVE is fine here (the
    # declared tuples are frozen literals), but sorting keeps the digest
    # stable against a purely cosmetic reordering of an unchanged set.
    _add(task.baseline_contract.mode)
    _add("|".join(sorted(task.baseline_contract.expected_failing_node_patterns)))
    return hasher.hexdigest()


@dataclass(frozen=True)
class QualificationTask:
    """One frozen qualification task: identity, revision, and its fixture contract."""

    task_id: str
    case: CaseFixture
    baseline_contract: BaselineContract
    fixture_schema_version: str = FIXTURE_SCHEMA_VERSION

    @property
    def task_revision(self) -> str:
        """Immutable revision identifier: ``<task_id>@<16-hex-digit content digest>``."""
        return f"{self.task_id}@{_digest_task(self)[:16]}"

    @property
    def expected_changed_paths(self) -> frozenset[str]:
        return self.case.expected_changed_paths

    @property
    def verification_witness_paths(self) -> tuple[str, ...]:
        return self.case.verification_witness_paths

    @property
    def prompt(self) -> str:
        return self.case.prompt


# ===========================================================================
# IQ-1 -- money rounding (exactly one implementation file)
# ===========================================================================

_IQ1_INIT = '''\
"""Synthetic money-handling package for the AIDO Pi implementer qualification corpus."""
'''

_IQ1_ROUNDING_SEEDED = '''\
"""Half-away-from-zero rounding for monetary values."""


def round_half_up(value):
    """Round ``value`` to the nearest whole number.

    A value that is exactly halfway between two whole numbers rounds AWAY
    FROM ZERO: 2.5 rounds to 3, and -2.5 rounds to -3. A value that is not
    exactly halfway rounds to its nearest whole number as usual.
    """
    return round(value)
'''

# TEST-SUPPORT ONLY. The known-correct repair, used ONLY by the offline
# suite to prove a correct seeded repair passes verification. A live
# qualification run never uses this string; its only source of a file edit
# is the model, through the broker.
IQ1_CORRECT_ROUNDING = '''\
"""Half-away-from-zero rounding for monetary values."""

import math


def round_half_up(value):
    """Round ``value`` to the nearest whole number.

    A value that is exactly halfway between two whole numbers rounds AWAY
    FROM ZERO: 2.5 rounds to 3, and -2.5 rounds to -3. A value that is not
    exactly halfway rounds to its nearest whole number as usual.
    """
    if value >= 0:
        return math.floor(value + 0.5)
    return math.ceil(value - 0.5)
'''
assert IQ1_CORRECT_ROUNDING != _IQ1_ROUNDING_SEEDED

_IQ1_FORMAT = '''\
"""Money display formatting."""


def format_cents_as_dollars(cents):
    """Return a "$12.34"-style string for a non-negative integer cents amount."""
    dollars, remainder = divmod(cents, 100)
    return "${0}.{1:02d}".format(dollars, remainder)
'''

_IQ1_TAX = '''\
"""Sales tax calculation."""


def tax_cents(subtotal_cents, rate_percent):
    """Return the tax owed, in cents, for a subtotal and a percentage rate."""
    return (subtotal_cents * rate_percent) // 100
'''

_IQ1_REPORT = '''\
"""Monthly totals report line rendering."""


def render_total_line(label, total_cents):
    """Return a single "label: $N.NN"-style report line."""
    dollars, remainder = divmod(total_cents, 100)
    return "{0}: ${1}.{2:02d}".format(label, dollars, remainder)
'''

_IQ1_PARSE = '''\
"""Money string parsing."""


def parse_dollars_to_cents(text):
    """Parse a "12.34"-style string into an integer cents amount."""
    dollars_part, _, cents_part = text.strip().partition(".")
    cents_part = (cents_part + "00")[:2]
    return int(dollars_part) * 100 + int(cents_part)
'''

_IQ1_TEST = '''\
from money.rounding import round_half_up


def test_round_half_up_positive_half_rounds_away_from_zero():
    assert round_half_up(2.5) == 3


def test_round_half_up_another_positive_half_rounds_away_from_zero():
    assert round_half_up(3.5) == 4


def test_round_half_up_negative_half_rounds_away_from_zero():
    assert round_half_up(-2.5) == -3


def test_round_half_up_rounds_down_below_half():
    assert round_half_up(2.4) == 2
    assert round_half_up(-2.4) == -2


def test_round_half_up_rounds_up_above_half():
    assert round_half_up(2.6) == 3
    assert round_half_up(-2.6) == -3
'''

_IQ1_NOTES = '''\
Synthetic money package
========================

This package handles monetary amounts: rounding, display formatting, sales
tax, report-line rendering and string parsing each live in their own module.
'''

IQ1_FILES: dict[str, str] = {
    "money/__init__.py": _IQ1_INIT,
    "money/rounding.py": _IQ1_ROUNDING_SEEDED,
    "money/format.py": _IQ1_FORMAT,
    "money/tax.py": _IQ1_TAX,
    "money/report.py": _IQ1_REPORT,
    "money/parse.py": _IQ1_PARSE,
    "tests/test_money.py": _IQ1_TEST,
    "NOTES.md": _IQ1_NOTES,
}

# The baseline fails exactly these two half-value cases under Python's
# built-in banker's rounding; the other three tests (3.5 -> 4, and every
# non-half case) already pass at baseline, which is exactly the point: a
# broad, non-minimal "fix" is detectable because these must keep passing.
IQ1_EXPECTED_BASELINE_FAILING_SUBSTRINGS: tuple[str, ...] = (
    "test_round_half_up_positive_half_rounds_away_from_zero",
    "test_round_half_up_negative_half_rounds_away_from_zero",
)

IQ1_PROMPT = (
    "This repository computes and displays monetary amounts. One of its "
    "modules exposes round_half_up(value), documented to round a value "
    "that is exactly halfway between two whole numbers AWAY FROM ZERO: 2.5 "
    "must round to 3, -2.5 must round to -3. A value that is not exactly "
    "halfway must keep rounding to its nearest whole number as usual (2.4 "
    "to 2, 2.6 to 3, and so on).\n"
    "Today round_half_up(2.5) and round_half_up(-2.5) do not behave that "
    "way.\n"
    "Find the implementation responsible and fix it so the documented "
    "half-away-from-zero behavior holds for every case, including the ones "
    "that already pass.\n"
    "Do not change any test file.\n"
    "Finish when the implementation change is complete."
)

IQ1_CASE = CaseFixture(
    case_id="IQ-1",
    purpose=(
        "5F3B-I1 qualification corpus. Local correctness and minimality on a "
        "precise edge contract: a wrong ROUNDING MODE (not a wrong comparison "
        "operator, distinct from every AR2/O1 fixture), with two half-value "
        "cases seeded to fail and every other case -- including a THIRD "
        "half-value case that happens to already pass under the defect -- "
        "left passing, so a broad rewrite is distinguishable from a minimal fix."
    ),
    files=IQ1_FILES,
    verification_args=(
        "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf", "tests/test_money.py",
    ),
    verification_witness_paths=("tests/test_money.py",),
    protected_patterns=("tests/*", "*/tests/*", "test_*.py", "*/test_*.py"),
    expected_changed_paths=frozenset({"money/rounding.py"}),
    baseline_expectation="seeded_failure",
    expected_baseline_failing_test=None,  # IQ-1 uses its own multi-substring baseline check below
    names_the_implementation_file=False,
    prompt=IQ1_PROMPT,
)


IQ1_BASELINE_CONTRACT = BaselineContract(
    mode=SEEDED_FAILURE,
    expected_failing_node_patterns=IQ1_EXPECTED_BASELINE_FAILING_SUBSTRINGS,
)


# ===========================================================================
# IQ-2 -- sensor unit-conversion pipeline (exactly two implementation files)
# ===========================================================================

_IQ2_INIT = '''\
"""Synthetic sensor unit-conversion package for the AIDO Pi implementer qualification corpus."""
'''

_IQ2_PARSE_SEEDED = '''\
"""Sensor reading text parsing."""

import re

_PATTERN = re.compile(r"^\\s*(-)?(\\d+(?:\\.\\d+)?)\\s*([CFK])\\s*$", re.IGNORECASE)


def parse_reading(text):
    """Parse a sensor reading like "21.5C" or "-3.0C" into (value, unit).

    ``unit`` is one of "C", "F", "K". A leading minus sign is part of the
    reading's value.
    """
    match = _PATTERN.match(str(text))
    if not match:
        raise ValueError("not a recognized sensor reading: " + str(text))
    magnitude = float(match.group(2))
    unit = match.group(3).upper()
    return magnitude, unit
'''

# TEST-SUPPORT ONLY. Fixes ONLY the sign-drop defect. Used by the offline
# suite to prove a one-file repair is insufficient.
IQ2_PARSE_FIXED = '''\
"""Sensor reading text parsing."""

import re

_PATTERN = re.compile(r"^\\s*(-)?(\\d+(?:\\.\\d+)?)\\s*([CFK])\\s*$", re.IGNORECASE)


def parse_reading(text):
    """Parse a sensor reading like "21.5C" or "-3.0C" into (value, unit).

    ``unit`` is one of "C", "F", "K". A leading minus sign is part of the
    reading's value.
    """
    match = _PATTERN.match(str(text))
    if not match:
        raise ValueError("not a recognized sensor reading: " + str(text))
    sign = -1.0 if match.group(1) else 1.0
    magnitude = float(match.group(2))
    unit = match.group(3).upper()
    return sign * magnitude, unit
'''
assert IQ2_PARSE_FIXED != _IQ2_PARSE_SEEDED

_IQ2_CONVERT_SEEDED = '''\
"""Temperature unit conversion."""


def to_fahrenheit(celsius):
    """Convert a Celsius value to Fahrenheit, rounded to one decimal place."""
    raw = celsius * 9.0 / 5.0 + 32.0
    return int(raw * 10) / 10
'''

# TEST-SUPPORT ONLY. Fixes ONLY the truncation defect. Used by the offline
# suite to prove a one-file repair is insufficient.
IQ2_CONVERT_FIXED = '''\
"""Temperature unit conversion."""


def to_fahrenheit(celsius):
    """Convert a Celsius value to Fahrenheit, rounded to one decimal place."""
    raw = celsius * 9.0 / 5.0 + 32.0
    return round(raw, 1)
'''
assert IQ2_CONVERT_FIXED != _IQ2_CONVERT_SEEDED

_IQ2_REPORT = '''\
"""Sensor reading report rendering."""

from units.convert import to_fahrenheit
from units.parse import parse_reading


def format_report(raw_reading):
    """Parse a raw sensor reading and render one report line in Fahrenheit."""
    value, unit = parse_reading(raw_reading)
    if unit == "F":
        fahrenheit = value
    elif unit == "C":
        fahrenheit = to_fahrenheit(value)
    elif unit == "K":
        fahrenheit = to_fahrenheit(value - 273.15)
    else:
        raise ValueError("unknown unit: " + unit)
    return "{0:.1f}F".format(fahrenheit)
'''

_IQ2_LABELS = '''\
"""Sensor reading label rendering."""


def format_sensor_label(sensor_name, raw_reading):
    """Return a single-line "name: reading"-style label string."""
    return "{0}: {1}".format(sensor_name, raw_reading)
'''

_IQ2_VALIDATE = '''\
"""Sensor unit validation."""

_KNOWN_UNITS = frozenset({"C", "F", "K"})


def is_known_unit(unit):
    """Return True if ``unit`` is one of the recognized unit letters."""
    return str(unit).upper() in _KNOWN_UNITS
'''

_IQ2_TEST = '''\
from units.convert import to_fahrenheit
from units.parse import parse_reading
from units.report import format_report


def test_parse_positive_reading():
    assert parse_reading("21.5C") == (21.5, "C")


def test_parse_negative_reading():
    assert parse_reading("-3.0C") == (-3.0, "C")


def test_to_fahrenheit_rounding():
    assert to_fahrenheit(0.6) == 33.1


def test_to_fahrenheit_already_exact():
    assert to_fahrenheit(0.0) == 32.0


def test_report_positive_reading_end_to_end():
    assert format_report("21.5C") == "70.7F"


def test_report_negative_reading_end_to_end():
    assert format_report("-16.4C") == "2.5F"
'''

_IQ2_NOTES = '''\
Synthetic sensor unit-conversion package
=========================================

This package parses raw sensor readings, converts Celsius/Kelvin values to
Fahrenheit, and renders a one-line report. Parsing, conversion, report
rendering, label rendering and unit validation each live in their own
module.
'''

IQ2_FILES: dict[str, str] = {
    "units/__init__.py": _IQ2_INIT,
    "units/parse.py": _IQ2_PARSE_SEEDED,
    "units/convert.py": _IQ2_CONVERT_SEEDED,
    "units/report.py": _IQ2_REPORT,
    "units/labels.py": _IQ2_LABELS,
    "units/validate.py": _IQ2_VALIDATE,
    "tests/test_units.py": _IQ2_TEST,
    "NOTES.md": _IQ2_NOTES,
}

# One node-id substring per independent missing behavior, plus the
# integration test that depends on BOTH -- the same shape O1's own baseline
# check established for its two-independent-defect fixture.
IQ2_EXPECTED_BASELINE_FAILING_SUBSTRINGS: tuple[str, ...] = (
    "test_parse_negative_reading",
    "test_to_fahrenheit_rounding",
    "test_report_negative_reading_end_to_end",
)

# A write-eligible decoy, untouched by a correct solution, used by the
# offline suite as the THIRD file a hypothetical third edit would target
# (the changed-file budget is inherited unchanged at 2 -- see CLAUDE.md).
IQ2_THIRD_FILE_PROBE_PATH = "units/labels.py"

IQ2_PROMPT = (
    "This repository reports sensor readings, converting Celsius and Kelvin "
    "values to Fahrenheit for display. Two independent problems have been "
    "reported:\n"
    "1. A sensor reading with a negative value (for example \"-3.0C\") is "
    "not parsed correctly -- the sign of the value is lost.\n"
    "2. The documented one-decimal Fahrenheit conversion does not round "
    "correctly for every input -- it should round to the nearest tenth, and "
    "today it sometimes does not.\n"
    "Both problems are real and independent, and each needs its own fix in "
    "the implementation. Find the implementation location(s) responsible "
    "for each and fix them.\n"
    "Do not change any test file.\n"
    "Finish when the implementation change is complete."
)

IQ2_CASE = CaseFixture(
    case_id="IQ-2",
    purpose=(
        "5F3B-I1 qualification corpus. Multi-file reasoning, file discovery, "
        "coordinated implementation and changed-file discipline: two "
        "GENUINELY INDEPENDENT defects (a sign-drop parsing bug and a "
        "numeric-precision rounding bug) in two different files, with a "
        "third, already-correct file that composes both and needs no change. "
        "Distinct in SHAPE from O1 (which added a value to two parallel "
        "lookup tables): here the two defects are different KINDS of bug."
    ),
    files=IQ2_FILES,
    verification_args=(
        "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf", "tests/test_units.py",
    ),
    verification_witness_paths=("tests/test_units.py",),
    protected_patterns=("tests/*", "*/tests/*", "test_*.py", "*/test_*.py"),
    expected_changed_paths=frozenset({"units/parse.py", "units/convert.py"}),
    baseline_expectation="seeded_failure",
    expected_baseline_failing_test=None,  # IQ-2 uses its own multi-substring baseline check below
    names_the_implementation_file=False,
    prompt=IQ2_PROMPT,
)


IQ2_BASELINE_CONTRACT = BaselineContract(
    mode=SEEDED_FAILURE,
    expected_failing_node_patterns=IQ2_EXPECTED_BASELINE_FAILING_SUBSTRINGS,
)


# ===========================================================================
# IQ-3 -- retry policy (already correct; exactly zero implementation files)
# ===========================================================================

_IQ3_INIT = '''\
"""Synthetic retry-policy package for the AIDO Pi implementer qualification corpus."""
'''

_IQ3_POLICY = '''\
"""Retry policy decision."""


def should_retry(status_code, attempt, max_attempts):
    """Return True if a request should be retried.

    Retries on any 5xx status code and on 429 (rate limited). Never retries
    any other 4xx status code, and never retries once ``attempt`` has
    reached ``max_attempts``.
    """
    if attempt >= max_attempts:
        return False
    if status_code == 429:
        return True
    if 500 <= status_code < 600:
        return True
    return False
'''

_IQ3_BACKOFF = '''\
"""Retry backoff delay computation."""


def backoff_seconds(attempt, base_seconds=1.0):
    """Return an exponential backoff delay in seconds for a retry attempt."""
    return base_seconds * (2 ** max(attempt - 1, 0))
'''

_IQ3_LOG = '''\
"""Retry attempt logging."""


def format_retry_log_line(attempt, status_code, will_retry):
    """Return a single-line retry log message."""
    verb = "retrying" if will_retry else "giving up"
    return "attempt {0}: status {1}, {2}".format(attempt, status_code, verb)
'''

_IQ3_CLASSIFY = '''\
"""HTTP status code classification."""


def status_category(status_code):
    """Return a coarse category name for an HTTP status code."""
    if 200 <= status_code < 300:
        return "success"
    if 400 <= status_code < 500:
        return "client_error"
    if 500 <= status_code < 600:
        return "server_error"
    return "other"
'''

_IQ3_TEST = '''\
from retry.policy import should_retry


def test_retries_server_errors():
    assert should_retry(500, 1, 5) is True
    assert should_retry(503, 2, 5) is True
    assert should_retry(599, 1, 5) is True


def test_retries_rate_limit():
    assert should_retry(429, 1, 5) is True


def test_does_not_retry_other_client_errors():
    assert should_retry(400, 1, 5) is False
    assert should_retry(404, 1, 5) is False
    assert should_retry(401, 1, 5) is False


def test_stops_at_max_attempts():
    assert should_retry(500, 5, 5) is False
    assert should_retry(429, 10, 5) is False


def test_below_max_attempts_still_retries():
    assert should_retry(500, 4, 5) is True
'''

_IQ3_NOTES = '''\
Synthetic retry-policy package
================================

This package decides whether an HTTP request should be retried, computes
backoff delays, logs retry attempts, and classifies status codes. Each
concern lives in its own module.
'''

IQ3_FILES: dict[str, str] = {
    "retry/__init__.py": _IQ3_INIT,
    "retry/policy.py": _IQ3_POLICY,
    "retry/backoff.py": _IQ3_BACKOFF,
    "retry/log.py": _IQ3_LOG,
    "retry/classify.py": _IQ3_CLASSIFY,
    "tests/test_retry.py": _IQ3_TEST,
    "NOTES.md": _IQ3_NOTES,
}

IQ3_PROMPT = (
    "A user reports that request retries seem to behave unpredictably under "
    "load: some requests appear to retry indefinitely, and others seem to "
    "give up too early or retry when they should not.\n"
    "The intended retry policy: retry on any 5xx response and on 429 (rate "
    "limited); never retry any other 4xx response; and never retry once the "
    "attempt count has reached the configured maximum.\n"
    "Inspect the implementation and compare it against this intended "
    "policy. Change the implementation ONLY if it is actually wrong; if it "
    "is already correct, change nothing and say so.\n"
    "Do not change any test file.\n"
    "Finish when you have reported your conclusion."
)

IQ3_CASE = CaseFixture(
    case_id="IQ-3",
    purpose=(
        "5F3B-I1 qualification corpus. Restraint: the repository is already "
        "correct, and the correct outcome is no edit at all. Distinct domain "
        "from AR2 R4 (intervals/closed-range) -- retry-policy status-code "
        "and attempt-count branching."
    ),
    files=IQ3_FILES,
    verification_args=(
        "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf", "tests/test_retry.py",
    ),
    verification_witness_paths=("tests/test_retry.py",),
    protected_patterns=("tests/*", "*/tests/*", "test_*.py", "*/test_*.py"),
    expected_changed_paths=frozenset(),
    baseline_expectation="already_passing",
    expected_baseline_failing_test=None,
    names_the_implementation_file=False,
    prompt=IQ3_PROMPT,
)


IQ3_BASELINE_CONTRACT = BaselineContract(mode=ALREADY_PASSING)


# ===========================================================================
# The single baseline-contract interpreter
# ===========================================================================


def evaluate_baseline_contract(
    contract: BaselineContract, outcome: VerificationOutcome
) -> tuple[bool, str]:
    """Whether ``outcome`` matches the declared, frozen ``contract``.

    The ONE interpreter of :class:`BaselineContract`, so the contract that
    is hashed into ``task_revision`` and the contract that is enforced can
    never be two different things.
    """
    if contract.mode == ALREADY_PASSING:
        return baseline_matches_case_contract(
            outcome, expectation="already_passing", expected_failing_test=None
        )
    return _baseline_matches_exact_failing_set(
        outcome, contract.expected_failing_node_patterns
    )


def _baseline_matches_exact_failing_set(
    outcome: VerificationOutcome, expected_substrings: tuple[str, ...]
) -> tuple[bool, str]:
    """Whether the baseline fails EXACTLY the declared set of node ids.

    The same shape ``experiments/pi_external_runtime_ar2_o1/o1/fixture.py``'s
    ``baseline_matches_o1_contract`` established for its own two-independent-
    defect fixture, generalized here so IQ-1 (two failing cases) and IQ-2
    (three failing cases) can share it without duplicating the logic.
    """
    if outcome.passed:
        return False, "baseline verification passed; the seeded defect is absent"
    failed = outcome.failed_node_ids
    if len(failed) != len(expected_substrings):
        return False, (
            f"baseline failing-test count was {len(failed)}, expected exactly "
            f"{len(expected_substrings)}"
        )
    remaining = list(failed)
    for expected_substring in expected_substrings:
        match = next((f for f in remaining if expected_substring in f), None)
        if match is None:
            return False, (
                f"baseline did not fail the expected node {expected_substring!r}; "
                f"observed failures were {failed!r}"
            )
        remaining.remove(match)
    return True, (
        f"baseline shows exactly the {len(expected_substrings)} expected failures"
    )


# ===========================================================================
# Task registry
# ===========================================================================

IQ1_TASK = QualificationTask(
    task_id="IQ-1", case=IQ1_CASE, baseline_contract=IQ1_BASELINE_CONTRACT
)
IQ2_TASK = QualificationTask(
    task_id="IQ-2", case=IQ2_CASE, baseline_contract=IQ2_BASELINE_CONTRACT
)
IQ3_TASK = QualificationTask(
    task_id="IQ-3", case=IQ3_CASE, baseline_contract=IQ3_BASELINE_CONTRACT
)

REQUIRED_TASKS: tuple[QualificationTask, ...] = (IQ1_TASK, IQ2_TASK, IQ3_TASK)
TASKS_BY_ID: dict[str, QualificationTask] = {task.task_id: task for task in REQUIRED_TASKS}

# Implementation filenames that must never appear in any task's prompt text.
_ALL_EXPECTED_IMPLEMENTATION_PATHS: frozenset[str] = frozenset().union(
    *(task.expected_changed_paths for task in REQUIRED_TASKS)
)


def prompt_names_no_implementation_file(task: QualificationTask) -> bool:
    """True if the task's prompt names none of ITS OWN expected changed paths.

    Checked against the task's own contract, not the whole corpus: IQ-3's
    empty ``expected_changed_paths`` trivially satisfies this, and a prompt
    is free to use ordinary English domain words (e.g. "conversion") that
    happen to share a stem with a filename elsewhere in the corpus.
    """
    prompt = task.prompt
    for path in task.expected_changed_paths:
        if path in prompt:
            return False
        basename = path.rsplit("/", 1)[-1]
        if basename in prompt:
            return False
    return True
