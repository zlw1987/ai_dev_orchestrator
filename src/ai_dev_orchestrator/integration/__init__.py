"""DL-4B — real integration, authority-identity side.

S0 (this slice) is the Windows identity boundary: :mod:`.identity_boundary`
proves, from read-only Windows security facts (:mod:`.windows_security`), that
the execution identity cannot write, replace, re-permission or open anything on
the authority identity's plane, evaluated by :mod:`.security_descriptor`.

Nothing in this package launches a process, opens a socket, calls a model,
runs Git, reads a credential value, or sets an ACL, and no CLI command reaches
it. See ``docs/DL4B_S0_WINDOWS_IDENTITY_BOUNDARY.md``.
"""
