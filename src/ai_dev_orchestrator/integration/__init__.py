"""DL-4B — real integration, authority-identity side.

S0 is the Windows identity boundary: :mod:`.identity_boundary` proves, from
read-only Windows security facts (:mod:`.windows_security`), that the execution
identity cannot write, replace, re-permission or open anything on the authority
identity's plane, evaluated by :mod:`.security_descriptor`.

S1 is the human attestation verifier: :mod:`.attestation_verifier` checks an
OpenSSH security-key signature (:mod:`.sshsig`) over an AIDO-rebuilt statement
against ``approver-registry.v1`` (:mod:`.approver_registry`), whose protection
it proves with S0's machinery.

Nothing in this package launches a process, opens a socket, calls a model,
runs Git, reads a credential value, signs anything, or sets an ACL, and no CLI
command reaches it. See ``docs/DL4B_S0_WINDOWS_IDENTITY_BOUNDARY.md`` and
``docs/DL4B_S1_HUMAN_ATTESTATION_VERIFIER.md``.
"""
