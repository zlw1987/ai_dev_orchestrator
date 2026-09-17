"""The regression-coverage guard: every frozen T-id has a named test.

``CFG1-IMPL`` must implement T-1 through T-162 (FU15 extended the range from
T-141 and renumbered, reused, deleted and rewrote no existing row), and the
authorization is explicit that no T-id may be omitted, reinterpreted,
renumbered or merged -- with T-124-T-132, T-133-T-136, T-137-T-141,
T-142-T-155, T-156-T-161 and T-162 each named as specifically non-omissible.

This is a MECHANICAL check, not a claim: it scans this suite's own test
function names for ``t<N>_`` and fails with the exact missing set. It proves
coverage of the ID SPACE, never that each test proves the right thing -- that
is what each test's own assertions are for.
"""

from __future__ import annotations

import re
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent

#: The frozen range, extended to exactly T-162 by FU15 (T-142-T-162 added;
#: FU15-D1 extended T-143 and rewrote T-154 IN PLACE, adding no id).
_FROZEN_T_IDS = frozenset(range(1, 163))

#: The groups the authorization names as specifically non-omissible. FU15's
#: three are listed SEPARATELY rather than as one T-142-T-162 span, because an
#: undifferentiated entry is exactly what let an earlier authorization fail to
#: name T-142-T-155 as its own group.
_NON_OMISSIBLE_GROUPS = {
    "terminal issuance boundary and successful completion (FU10/FU11)": range(124, 133),
    "seal-once versus consume-once separation (FU12)": range(133, 137),
    "terminal-decision mint-failure disposition (FU13/FU14)": range(137, 142),
    "Windows config-directory pin authority (FU15/FU15-D1)": range(142, 156),
    "malformed count projection, Findings B1/B2 (FU15)": range(156, 162),
    "OBS1 disposition -- no second mechanism (FU15)": range(162, 163),
}

_FUNCTION_NAME = re.compile(r"^def (test_\w+)", re.MULTILINE)

#: One ``_``-separated name token that IS a T-id: ``t135``, or ``t107a`` for a
#: design row with lettered sub-cases.
_T_ID_TOKEN = re.compile(r"^t(\d{1,3})[a-z]?$")


def _covered_t_ids() -> dict[int, list[str]]:
    """Every T-id named in a test FUNCTION NAME, crediting combined names.

    Tokenizing on ``_`` rather than anchoring at the start is deliberate: a
    single regression legitimately proves several frozen rows at once (T-37 and
    T-68 are the same positive control; T-135's three sub-cases ARE T-137,
    T-138 and T-139's own scenarios), and a scanner that credited only the
    first id would report those rows as missing when they are not.

    Docstring mentions are deliberately NOT counted -- prose is not coverage.
    """
    covered: dict[int, list[str]] = {}
    for source_path in sorted(_TESTS_DIR.glob("test_cfg1_*.py")):
        source = source_path.read_text(encoding="utf-8")
        for match in _FUNCTION_NAME.finditer(source):
            for token in match.group(1).split("_"):
                token_match = _T_ID_TOKEN.match(token)
                if token_match:
                    covered.setdefault(int(token_match.group(1)), []).append(
                        source_path.name
                    )
    return covered


def test_every_frozen_t_id_from_1_to_162_has_at_least_one_named_test():
    covered = _covered_t_ids()
    missing = sorted(_FROZEN_T_IDS - set(covered))
    assert missing == [], f"frozen T-ids with no named test: {missing}"


def test_no_test_claims_a_t_id_outside_the_frozen_range():
    """Nothing is renumbered upward, and nothing invents a T-163."""
    covered = _covered_t_ids()
    extra = sorted(set(covered) - _FROZEN_T_IDS)
    assert extra == [], f"tests naming T-ids outside the frozen range: {extra}"


def test_every_non_omissible_group_is_present_in_full():
    covered = _covered_t_ids()
    for label, group in _NON_OMISSIBLE_GROUPS.items():
        missing = sorted(set(group) - set(covered))
        assert missing == [], f"{label}: missing {missing}"


def test_the_coverage_scan_is_not_vacuous():
    """A scanner that matched nothing would make every assertion above pass."""
    covered = _covered_t_ids()
    assert len(covered) >= 162
    assert covered[1] and covered[141] and covered[162]
