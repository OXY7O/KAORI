"""Deterministic MFA assurance policy, separate from primary identity providers.

This pure policy kernel does not mint an authenticated Flask-Login session.
An MFA challenge controller is not admitted until factor persistence, bounded
pending-auth state, and recovery flows satisfy the approved #562 contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MfaPolicyError(ValueError):
    """Invalid policy input must not silently downgrade required assurance."""


class MfaPolicyMode(StrEnum):
    DISABLED = 'disabled'
    OPTIONAL = 'optional'
    REQUIRED_PRIVILEGED = 'required_privileged'
    REQUIRED_ALL = 'required_all'


class MfaGate(StrEnum):
    ALLOW = 'allow'
    CHALLENGE = 'challenge'
    ENROLLMENT_REQUIRED = 'enrollment_required'


@dataclass(frozen=True, slots=True)
class MfaPolicyDecision:
    mode: MfaPolicyMode
    gate: MfaGate
    policy_required: bool

    @property
    def requires_challenge(self) -> bool:
        return self.gate == MfaGate.CHALLENGE

    @property
    def can_enter_application(self) -> bool:
        # Only a policy that requires no factor can permit session issuance
        # without a second-factor verification result.
        return self.gate == MfaGate.ALLOW


def evaluate_mfa_policy(
    mode: MfaPolicyMode | str,
    *,
    privileged: bool,
    enrolled: bool,
) -> MfaPolicyDecision:
    """Evaluate post-primary-authentication policy without trusting role names.

    Caller must supply privilege from effective KAORI RBAC/super-admin policy;
    `enrolled` must come from a committed verified factor, not an untrusted form.
    Neither this function nor a pending challenge grants KAORI authorization.
    """
    try:
        selected = MfaPolicyMode(mode)
    except (TypeError, ValueError) as exc:
        raise MfaPolicyError('Unsupported MFA assurance policy.') from exc
    if type(privileged) is not bool or type(enrolled) is not bool:
        raise MfaPolicyError('MFA admission needs explicit trusted boolean evidence.')

    if selected == MfaPolicyMode.DISABLED:
        return MfaPolicyDecision(selected, MfaGate.ALLOW, False)

    required = selected == MfaPolicyMode.REQUIRED_ALL or (
        selected == MfaPolicyMode.REQUIRED_PRIVILEGED and privileged
    )
    if required and not enrolled:
        return MfaPolicyDecision(selected, MfaGate.ENROLLMENT_REQUIRED, True)
    if enrolled:
        return MfaPolicyDecision(selected, MfaGate.CHALLENGE, required)
    return MfaPolicyDecision(selected, MfaGate.ALLOW, False)


def can_issue_session(decision: MfaPolicyDecision, *, factor_verified: bool = False) -> bool:
    """Must be checked *before* a new login generation can be committed.

    Required enrollment cannot be bypassed by a forged 'verified' flag.
    Challenge verifications must eventually come from a bounded server-side
    proof, never a browser-controlled boolean.
    """
    if type(factor_verified) is not bool:
        raise MfaPolicyError('MFA verification evidence must be a trusted boolean.')
    if decision.gate == MfaGate.ALLOW:
        return True
    return decision.gate == MfaGate.CHALLENGE and factor_verified
