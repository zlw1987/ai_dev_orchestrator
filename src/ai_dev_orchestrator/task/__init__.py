"""Personal Alpha 2A: the single-file task coordinator (ALPHA-2A-T1).

A thin, resumable sequence over the accepted stages: approved plan, the live
supervised implementer (ALPHA-P1B), the 5F2C writer, and the 5F2E reviewer
(which runs the 5F2D verification itself). It adds no authority, no gate, no
model call and no subprocess of its own. See :mod:`.run`, :mod:`.preflight`,
:mod:`.doctor` and ``docs/ALPHA_2A_TASK_COORDINATOR.md``.
"""
