"""Encrypted TOTP enrollment, one-use recovery and replay-resistant MFA checks.

TOTP and recovery primitives are owned by the already approved PyOTP factor
adapter. KAORI never implements TOTP cryptography or posts QR secrets to a web service.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.mfa.audit import stage_authentication_security_event
from app.access.authentication.mfa.factors import (
    accepted_totp_step,
    generate_recovery_codes,
    hash_recovery_code,
    recovery_code_match,
    start_totp_enrollment,
)
from app.access.authentication.mfa.policy import MfaPolicyDecision, evaluate_mfa_policy
from app.extensions.db import db
from app.models.authentication_security import AuthenticationMfaFactor, AuthenticationSecurityPolicy
from app.models.user import User
from app.security.credentials import decrypt_credential

ENROLLMENT_TTL = timedelta(minutes=10)
MFA_CHALLENGE_TTL_SECONDS = 300


class MfaVerificationError(ValueError):
    """Reject with a generic message; never include factor secret or submitted code."""


def mfa_policy_mode() -> str:
    policy = db.session.get(AuthenticationSecurityPolicy, 1)
    return policy.mfa_mode if policy is not None else 'disabled'


def mfa_enrolled(user_id: int) -> bool:
    factor = AuthenticationMfaFactor.query.filter_by(user_id=user_id, enabled=True).first()
    return factor is not None


def mfa_decision(user: User) -> MfaPolicyDecision:
    return evaluate_mfa_policy(
        mfa_policy_mode(), privileged=bool(user.is_admin_level), enrolled=mfa_enrolled(user.id)
    )


def _accepted_step(secret: str, code: str, *, last_accepted_step: int | None, now: datetime) -> int | None:
    return accepted_totp_step(
        secret,
        code,
        last_accepted_step=last_accepted_step,
        timestamp=int(now.timestamp()),
    )


def begin_mfa_enrollment(user: User, *, authenticated: bool = True) -> str:
    """Create expiring encrypted factor; return seed ONLY to this POST response."""
    if mfa_enrolled(user.id):
        raise MfaVerificationError('MFA is already enrolled.')
    existing = AuthenticationMfaFactor.query.filter_by(user_id=user.id).with_for_update().first()
    enrollment = start_totp_enrollment(account_label=user.username)
    secret = decrypt_credential(enrollment.encrypted_secret)
    if secret is None:
        raise MfaVerificationError('MFA enrollment encryption is unavailable.')
    factor = existing if existing is not None else AuthenticationMfaFactor(user_id=user.id)
    factor.totp_secret = enrollment.encrypted_secret
    factor.enabled = False
    factor.last_accepted_step = None
    factor.recovery_hashes = []
    factor.enrollment_expires_at = datetime.now(UTC) + ENROLLMENT_TTL
    if existing is None:
        db.session.add(factor)
    db.session.add(stage_authentication_security_event(
        user, action='mfa_enrollment_started', authenticated=authenticated, success=True,
    ))
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return secret


def confirm_mfa_enrollment(user: User, code: str, *, authenticated: bool = True) -> list[str]:
    """Activate only after OTP proof; codes are returned ONCE, hashes persisted."""
    factor = AuthenticationMfaFactor.query.filter_by(user_id=user.id).with_for_update().first()
    now = datetime.now(UTC)
    if factor is None or factor.enabled or factor.enrollment_expires_at is None:
        raise MfaVerificationError('Start MFA enrollment again.')
    expires = factor.enrollment_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires <= now:
        raise MfaVerificationError('MFA enrollment expired; start again.')
    accepted = _accepted_step(factor.totp_secret, code, last_accepted_step=None, now=now)
    if accepted is None:
        raise MfaVerificationError('Verification code was not accepted.')
    recovery = list(generate_recovery_codes())
    factor.recovery_hashes = [hash_recovery_code(value) for value in recovery]
    factor.last_accepted_step = accepted
    factor.enabled = True
    factor.enrolled_at = now
    factor.enrollment_expires_at = None
    db.session.add(stage_authentication_security_event(
        user, action='mfa_enrollment_confirmed', authenticated=authenticated, success=True,
    ))
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return recovery


def verify_mfa_challenge(user: User, submitted: str, *, authenticated: bool = False) -> str:
    """Consume a factor proof under an exclusive row lock, preventing OTP replay."""
    if not isinstance(submitted, str) or not 6 <= len(submitted) <= 64:
        raise MfaVerificationError('Verification code was not accepted.')
    factor = AuthenticationMfaFactor.query.filter_by(user_id=user.id, enabled=True).with_for_update().first()
    if factor is None:
        raise MfaVerificationError('MFA enrollment is unavailable.')
    now = datetime.now(UTC)
    accepted = _accepted_step(
        factor.totp_secret, submitted, last_accepted_step=factor.last_accepted_step, now=now
    )
    kind = 'totp'
    if accepted is not None:
        factor.last_accepted_step = accepted
    else:
        kind = 'recovery'
        used_digest = recovery_code_match(submitted, factor.recovery_hashes or [])
        if used_digest is None:
            raise MfaVerificationError('Verification code was not accepted.')
        factor.recovery_hashes = [digest for digest in factor.recovery_hashes if digest != used_digest]
    db.session.add(stage_authentication_security_event(
        user, action='mfa_challenge_verified', authenticated=authenticated, success=True,
    ))
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return kind


def regenerate_mfa_recovery_codes(user: User) -> list[str]:
    """Call only after fresh primary reauthentication AND a consumed MFA proof."""
    factor = AuthenticationMfaFactor.query.filter_by(user_id=user.id, enabled=True).with_for_update().first()
    if factor is None:
        raise MfaVerificationError('MFA is not enrolled.')
    codes = list(generate_recovery_codes())
    factor.recovery_hashes = [hash_recovery_code(value) for value in codes]
    db.session.add(stage_authentication_security_event(
        user, action='mfa_recovery_regenerated', authenticated=True, success=True,
    ))
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return codes


def disable_mfa(user: User, submitted: str) -> None:
    """Delete protected factor only when current KAORI policy permits it."""
    if mfa_decision(user).policy_required:
        raise MfaVerificationError('MFA is required by the current security policy.')
    verify_mfa_challenge(user, submitted, authenticated=True)
    factor = AuthenticationMfaFactor.query.filter_by(user_id=user.id, enabled=True).with_for_update().first()
    if factor is None:
        raise MfaVerificationError('MFA is not enrolled.')
    db.session.delete(factor)
    db.session.add(stage_authentication_security_event(
        user, action='mfa_disabled', authenticated=True, success=True,
    ))
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
