"""DL-4B — real integration, authority-identity side.

S0 is the Windows identity boundary: :mod:`.identity_boundary` proves, from
read-only Windows security facts (:mod:`.windows_security`), that the execution
identity cannot write, replace, re-permission or open anything on the authority
identity's plane, evaluated by :mod:`.security_descriptor`.

S1 is the human attestation verifier: :mod:`.attestation_verifier` checks an
OpenSSH security-key signature (:mod:`.sshsig`) over an AIDO-rebuilt statement
against ``approver-registry.v1`` (:mod:`.approver_registry`), whose protection
it proves with S0's machinery.

S2 is the integration authority store: :mod:`.integration_store`
(``aido-control-plane-store.v4``) re-runs the S0 proof at every consumption
boundary and consumes S1-verified approvals, and :mod:`.integration_session`
is the one way to open it. No API accepts claim, observation or evidence
bytes.

S3 is the exact-diff approval and the write handoff: Git-free authority
observations of the clone (:mod:`.workspace_observation`, FD-18), the per-ticket
handoff and outbox (:mod:`.exchange`) and the claim receiver
(:mod:`.claim_receiver`, FD-17) over A's file access (:mod:`.authority_files`),
mirror readers for the bytes A binds (:mod:`.claim_readers`), write-once blobs
(:mod:`.state_blobs`), and :mod:`.write_handoff`, the implementer port whose
recorder the session mints.

S6 is the human acceptance lifecycle: :mod:`.alpha_planner`, the deterministic
Alpha planner rule (no model), and :mod:`.acceptance_bundle`, the human's review
material, published into the A-owned ``published/`` directory; the hold and
the signed ``step-acceptance-subject.v2`` live in the integration store.

Nothing in this package launches a process, opens a socket, calls a model,
runs Git, reads a credential value or signs anything, and no CLI command
reaches it. The only ACL it ever sets is the protected DACL of a directory it
creates in its own exchange root, at creation. See the ``docs/DL4B_S*`` files.
"""
