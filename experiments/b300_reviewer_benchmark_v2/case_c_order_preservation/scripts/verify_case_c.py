"""Synthetic verification program for B300 V2 CASE C (order regression).

Deliberately uses an input whose desired first-occurrence order already
matches sorted order (["a", "b", "a"] -> ["a", "b"]), so this verification
PASSES even though the seeded regression (sorted(set(...))) discards caller
ordering. It omits an order-sensitive input such as
["b", "a", "b"] -> ["b", "a"]. This is the intentional "verification gap".

Lives OUTSIDE the sandbox workspace per the controlled_verification contract.
"""
import sys

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "src")

from dedupe.ordered import dedupe_preserve_order  # noqa: E402

assert dedupe_preserve_order(["a", "b", "a"]) == ["a", "b"]

sys.stdout.write("collected 1 items\n1 passed\n")
sys.exit(0)
