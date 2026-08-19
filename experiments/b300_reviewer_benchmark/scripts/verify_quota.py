"""Synthetic verification program for the B300 reviewer benchmark (RT1 case).

Deliberately exercises within_quota() WITHOUT the equality boundary
(value == limit), so this verification PASSES even though the seeded
regression (`value <= limit` -> `value < limit`) breaks that boundary.
This is the intentional "verification gap" the benchmark asks reviewers
to notice.

Lives OUTSIDE the sandbox workspace (C:\\dev\\aido_rs1_rt1_sandbox) per the
controlled_verification contract: the repository being verified may not
supply its own verification program.
"""
import sys

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "src")

from quota.limits import remaining, within_quota  # noqa: E402

assert within_quota(3, 10) is True
assert within_quota(15, 10) is False
assert within_quota(0, 10) is True
assert remaining(3, 10) == 7

sys.stdout.write("collected 4 items\n4 passed\n")
sys.exit(0)
