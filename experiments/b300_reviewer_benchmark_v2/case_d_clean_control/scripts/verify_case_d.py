"""Synthetic verification program for B300 V2 CASE D (clean control, no bug).

Covers normal non-empty text, an empty string, and a whitespace-only string.
There is no seeded bug and no deliberately omitted boundary in this case.

Lives OUTSIDE the sandbox workspace per the controlled_verification contract.
"""
import sys

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "src")

from text.name_check import is_nonempty_name  # noqa: E402

assert is_nonempty_name("Ada") is True
assert is_nonempty_name("") is False
assert is_nonempty_name("   ") is False

sys.stdout.write("collected 3 items\n3 passed\n")
sys.exit(0)
