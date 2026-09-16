"""``CFG1-T1`` -- the one synthetic task this experiment uses.

Design Sec. 10. A NEW task, never a corpus reuse: the IQ tasks are frozen
lineage inputs and OBS1 Sec. 13.6 forbids probe reuse. ``CFG1-T1`` lives only
in this package -- it is not in ``qualification.corpus``, not in
``VALID_TASK_IDS``, and not in any qualification result.

The dependent variable is whether the model REQUESTS the offered tools, so the
task names the implementation file explicitly (Sec. 10.3): ``aido_edit``
requires the ``aido_read`` sha, so an edit implies a read, and naming the path
removes discoverability as a competing cause of inactivity. The accepted
trade-off is that CFG1 therefore does not test D5, the prompt-manifest
divergence (Sec. 13.4).

The prompt names no tool and carries no manifest -- ``manifest_in_prompt`` is
``False`` and the transmission is bare, exactly the qualification layer's own
shape (Sec. 8.3).
"""

from __future__ import annotations

import hashlib
import json

from ar2.fixtures import CaseFixture

CFG1_TASK_ID = "CFG1-T1"

_BANNER_SEEDED_DEFECT = '''\
"""Synthetic greeting module for the AIDO CFG1 launch-configuration harness."""


def banner(name):
    """Return the documented greeting for ``name``."""
    return "Hi, " + name + "!"
'''

_BANNER_TEST_WITNESS = '''\
from greeting.banner import banner


def test_banner_uses_the_documented_greeting():
    assert banner("Ada") == "Hello, Ada!"
'''

#: The fixed prompt. Names the implementation file, names NO tool, carries no
#: file list and no tool-usage sentence, and is transmitted verbatim with
#: nothing prepended or appended (Sec. 10.2).
CFG1_T1_PROMPT = (
    "In this repository, the function banner(name) in greeting/banner.py must "
    'return exactly "Hello, " followed by the name and "!". For example, '
    'banner("Ada") must return "Hello, Ada!". It currently returns a different '
    "greeting. Change greeting/banner.py so it returns the documented text. "
    "Do not change any test file. Finish when the change is complete."
)

CFG1_T1 = CaseFixture(
    case_id=CFG1_TASK_ID,
    purpose=(
        "CFG1 launch-configuration diagnostic. One seeded semantic defect in a "
        "named implementation file, with a protected test witness. Carries no "
        "qualification authority of any kind."
    ),
    files={
        "greeting/__init__.py": "",
        "greeting/banner.py": _BANNER_SEEDED_DEFECT,
        "tests/test_banner.py": _BANNER_TEST_WITNESS,
    },
    verification_args=(
        "-B",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rf",
        "tests/test_banner.py",
    ),
    verification_witness_paths=("tests/test_banner.py",),
    protected_patterns=("tests/**", "**/test_*.py", "**/*_test.py"),
    expected_changed_paths=frozenset({"greeting/banner.py"}),
    baseline_expectation="seeded_failure",
    expected_baseline_failing_test=(
        "tests/test_banner.py::test_banner_uses_the_documented_greeting"
    ),
    prompt=CFG1_T1_PROMPT,
    manifest_in_prompt=False,
    names_the_implementation_file=True,
)

#: Every fixture-relative path a CFG1 record may ever name. ``changed_tracked_paths``
#: and ``post_verification_changed_tracked_paths`` must be sorted subsets of
#: this set; anything else is retained as a COUNT only (Sec. 21.2).
CFG1_T1_FILES: frozenset[str] = frozenset(CFG1_T1.files)


def _compute_fixture_revision() -> str:
    """A content digest over everything that defines this fixture's identity.

    Derived, never hand-maintained: editing any file, the prompt, the
    verification argv, the witness set or the protected patterns changes the
    revision, so a record pinned to one revision cannot silently describe a
    different task.
    """
    material = {
        "case_id": CFG1_T1.case_id,
        "files": dict(sorted(CFG1_T1.files.items())),
        "prompt": CFG1_T1.prompt,
        "verification_args": list(CFG1_T1.verification_args),
        "verification_witness_paths": list(CFG1_T1.verification_witness_paths),
        "protected_patterns": list(CFG1_T1.protected_patterns),
        "expected_changed_paths": sorted(CFG1_T1.expected_changed_paths),
        "baseline_expectation": CFG1_T1.baseline_expectation,
        "expected_baseline_failing_test": CFG1_T1.expected_baseline_failing_test,
        "manifest_in_prompt": CFG1_T1.manifest_in_prompt,
        "names_the_implementation_file": CFG1_T1.names_the_implementation_file,
    }
    serialized = json.dumps(material, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


#: The pinned revision every run record carries, as an explicit LITERAL.
#:
#: Pinned rather than computed at import for the same reason the arm digests
#: are (see :mod:`arms`): if the record carried whatever the current fixture
#: happens to hash to, editing the fixture would silently redefine what a
#: "correct" record is, and every archived record would retroactively become
#: wrong without anything failing. A dedicated regression compares this
#: constant against :func:`_compute_fixture_revision`, so fixture drift is a
#: test failure instead.
PINNED_CFG1_T1_REVISION = (
    "32d8b7606e55bf0f8f00f3698f67f9c35188976272eba04bb5b066fe5d0f75d9"
)

CFG1_T1_REVISION = PINNED_CFG1_T1_REVISION
