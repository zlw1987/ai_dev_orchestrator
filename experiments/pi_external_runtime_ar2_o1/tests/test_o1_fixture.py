"""Fixture shape proofs: file set, expected-changed-paths, protection status."""

from __future__ import annotations

from ar2.capability import matches_any
from o1.fixture import (
    EXPECTED_CHANGED_PATHS,
    FILES,
    PROTECTED_PATTERNS,
    THIRD_FILE_PROBE_PATH,
    VERIFICATION_WITNESS_PATHS,
)


def test_fixture_declares_at_least_five_non_test_files():
    non_test = [p for p in FILES if not matches_any(p, ("tests/*", "*/tests/*"))]
    assert len(non_test) >= 5, non_test


def test_fixture_has_exactly_one_test_witness_file():
    test_files = [p for p in FILES if matches_any(p, ("tests/*", "*/tests/*"))]
    assert test_files == list(VERIFICATION_WITNESS_PATHS)


def test_expected_changed_paths_is_exactly_two():
    assert len(EXPECTED_CHANGED_PATHS) == 2
    assert EXPECTED_CHANGED_PATHS <= set(FILES)


def test_neither_expected_file_is_the_witness_or_protected():
    for path in EXPECTED_CHANGED_PATHS:
        assert path not in VERIFICATION_WITNESS_PATHS
        assert not matches_any(path, PROTECTED_PATTERNS), path


def test_quote_module_is_not_among_the_expected_changed_paths():
    """quote.py already composes normalize + rate lookup correctly."""
    assert "subscription/quote.py" not in EXPECTED_CHANGED_PATHS


def test_third_file_probe_path_is_real_and_not_expected():
    assert THIRD_FILE_PROBE_PATH in FILES
    assert THIRD_FILE_PROBE_PATH not in EXPECTED_CHANGED_PATHS
    assert not matches_any(THIRD_FILE_PROBE_PATH, PROTECTED_PATTERNS)


def test_fixture_repository_tracks_exactly_the_declared_files(o1_repo):
    assert set(o1_repo.tracked_paths) == set(FILES)
