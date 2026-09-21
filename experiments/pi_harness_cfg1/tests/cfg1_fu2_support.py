"""CFG1-L16-FU2 test support: the REAL supervisor over a synthetic peer. Tests only.

Loads the AR2 suite's synthetic-peer support module by path, under a private
module name, so both suites drive the identical peer script. The peer is a
Python script written under ``tmp_path`` and launched with a pinned absolute
argv; it is never the real Pi, and nothing here opens a socket, calls a model,
or reads a credential or endpoint.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_AR2_TESTS = Path(__file__).resolve().parents[2] / "pi_external_runtime_ar2" / "tests"
_MODULE_NAME = "ar2_fu2_probe_support"


def _load_support():
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _AR2_TESTS / "probe_support.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


support = _load_support()


def cfg1_supervisor(peer, *, bounds=None):
    """A real supervisor bound to CFG1's frozen identity, exactly as L14 builds it."""
    from ar2.supervisor import PiRpcSupervisor

    from pi_harness_cfg1.identity import CFG1_MODEL_ID, PROVIDER_ID

    return PiRpcSupervisor(
        argv=peer.argv,
        cwd=str(Path(peer.argv[1]).parent),
        environment=support._minimal_environment(),
        bounds=bounds or support.FAST_BOUNDS,
        expected_provider=PROVIDER_ID,
        expected_model=CFG1_MODEL_ID,
    )


def cfg1_state_frame(arm_id: str = "Q", *, reasoning: Any = True, thinking: str = "medium") -> str:
    """One correlated ``get_state`` frame for a runtime that loaded ``arm_id``."""
    from pi_harness_cfg1.arms import ARM_COMPAT
    from pi_harness_cfg1.identity import CFG1_MODEL_ID, PROVIDER_ID

    compat = ARM_COMPAT[arm_id]
    data = support.state_data(
        reasoning=reasoning,
        provider=PROVIDER_ID,
        model_id=CFG1_MODEL_ID,
        compat=None if compat is None else dict(compat),
        include_compat=compat is not None,
        thinking=thinking,
    )
    return support.get_state_frame(data)
