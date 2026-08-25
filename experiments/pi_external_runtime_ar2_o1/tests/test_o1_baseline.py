"""Baseline verification proofs, using AR2's unmodified bounded runner.

Proves: (1) the seeded baseline fails on exactly the three expected node ids
(both independent missing behaviors plus the integration test), and (2)
NEITHER single-file "correct" edit alone satisfies the full verification
suite -- only editing BOTH files does. This is the objective, verification-
enforced property the operating brief requires: no one-file workaround can
make the complete suite pass without breaking the task contract.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ar2.verification import run_verification
from o1.fixture import (
    NORMALIZE_WITH_ENTERPRISE,
    O1_CASE,
    RATES_WITH_ENTERPRISE,
    baseline_matches_o1_contract,
)


def _run(repo_root: str):
    return run_verification(
        python_executable=sys.executable,
        workspace_root=repo_root,
        args=O1_CASE.verification_args,
    )


def test_baseline_fails_both_seeded_missing_behaviors(o1_repo):
    outcome = _run(o1_repo.repo_root)
    assert not outcome.passed
    matches, why = baseline_matches_o1_contract(outcome)
    assert matches, why
    failed = " ".join(outcome.failed_node_ids)
    assert "test_normalize_enterprise_variants" in failed
    assert "test_rate_enterprise" in failed
    assert "test_quote_enterprise" in failed


def test_normalize_only_fix_is_insufficient(o1_repo):
    """Fixing normalize.py alone must still leave rate/quote behavior broken."""
    path = Path(o1_repo.repo_root, "subscription", "normalize.py")
    path.write_text(NORMALIZE_WITH_ENTERPRISE, encoding="utf-8", newline="\n")
    outcome = _run(o1_repo.repo_root)
    assert not outcome.passed
    failed = " ".join(outcome.failed_node_ids)
    assert "test_rate_enterprise" in failed
    assert "test_quote_enterprise" in failed
    assert "test_normalize_enterprise_variants" not in failed


def test_rates_only_fix_is_insufficient(o1_repo):
    """Fixing rates.py alone must still leave normalize/quote behavior broken."""
    path = Path(o1_repo.repo_root, "subscription", "rates.py")
    path.write_text(RATES_WITH_ENTERPRISE, encoding="utf-8", newline="\n")
    outcome = _run(o1_repo.repo_root)
    assert not outcome.passed
    failed = " ".join(outcome.failed_node_ids)
    assert "test_normalize_enterprise_variants" in failed
    assert "test_quote_enterprise" in failed
    assert "test_rate_enterprise" not in failed


def test_both_fixes_together_are_necessary_and_sufficient(o1_repo):
    Path(o1_repo.repo_root, "subscription", "normalize.py").write_text(
        NORMALIZE_WITH_ENTERPRISE, encoding="utf-8", newline="\n"
    )
    Path(o1_repo.repo_root, "subscription", "rates.py").write_text(
        RATES_WITH_ENTERPRISE, encoding="utf-8", newline="\n"
    )
    outcome = _run(o1_repo.repo_root)
    assert outcome.passed, outcome.output_text[-2000:]
