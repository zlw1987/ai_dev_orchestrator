"""Fixed I2 route-identity constants (5F3B-I2-FU3).

**OFFLINE ONLY. The one true leaf module.** This file imports nothing else
from this package, so every other I2 module -- including modules that need
to import EACH OTHER for their own valid-by-construction checks
(``i2_pi_config`` needs ``i2_secret_context``'s URL validator;
``i2_environment`` needs both ``i2_pi_config.GeneratedQualificationConfig``
and ``i2_secret_context.QualificationRouteSecretContext`` for its FU3
``build_child_environment`` signature) -- can import these two constants
without ever creating an import cycle.

Both constants are unchanged in VALUE from I2A/FU1/FU2; only their home
module changed. ``i2_environment`` and ``i2_pi_config`` both re-export them
(``from .i2_identity import ...`` at their own top), so every existing
``from qualification.i2_environment import CREDENTIAL_ENV_VAR_NAME`` /
``from qualification.i2_pi_config import PROVIDER_ID`` import site keeps
working unchanged.
"""

from __future__ import annotations

#: The ONE qualification credential carrier (I2A design Sec. 9). Deliberately
#: not ``AIDO_``-prefixed and deliberately free of every
#: ``i2_environment.FORBIDDEN_NAME_FRAGMENTS`` entry -- proven, not merely
#: asserted, by that module's forbidden-fragment audit. This is the one
#: exact-identity exception to that audit.
CREDENTIAL_ENV_VAR_NAME = "PI_QUALIFICATION_B300_ROUTE_KEY"

#: The one qualification-owned provider id (I2A Sec. 10/19).
PROVIDER_ID = "b300_pi_qualification"
