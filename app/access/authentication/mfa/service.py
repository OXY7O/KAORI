"""Encrypted TOTP enrollment, one-use recovery and replay-resistant MFA checks.

RFC 6238 is implemented by cryptography's vetted TOTP primitive. KAORI never
reimplements OTP cryptography and never sends secrets to external QR endpoints.
"""

from __future__ import annotations

import base64
import binascii
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.twofactor import InvalidToken
from cryptography.hazmat.primitives.twofactor.totp import TOTP
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from app.access.authentication.admission import session_admission_reason
from app.access.authentication.mfa.audit import stage_authentication_security_event
from app.access.authentication.mfa.policy import MfaPolicyDecision, evaluate_mfa_policy
from app.access.authentication.password_policy import LOCAL_PASSWORD_MAX_LENGTH
from app.access.authentication.session_lifecycle import SessionDeadlines, read_session_policy, session_deadlines
from app.extensions.db import db
from app.models.authentication_security import AuthenticationMfaFactor, AuthenticationSecurityPolicy
from app.models.user import User
from app.security.credentials import CredentialEncryptionError

ENROLLMENT_TTL = timedelta(minutes=10)
MFA_CHALLENGE_TTL_SECONDS = 300
MFA_RECENT_ADMISSION_TTL = timedelta(seconds=MFA_CHALLENGE_TTL_SECONDS)


class MfaVerificationError(ValueError):
    """Reject with a generic message; never include factor secret or submitted code."""


def mfa_policy_mode() -> str:
    policy = db.session.get(AuthenticationSecurityPolicy, 1)
    return policy.mfa_mode if policy is not None else 'disabled'


def mfa_enrolled(user_id: int) -> bool:
    factor = AuthenticationMfaFactor.query.filter_by(user_id=user_id, enabled=True).first()
    return factor is not None


def mfa_decision(user: User) -> MfaPolicyDecision:
    return evaluate_mfa_policy(mfa_policy_mode(), privileged=bool(user.is_admin_level), enrolled=mfa_enrolled(user.id))


def _totp(secret: str) -> TOTP:
    try:
        key = base64.b32decode(secret, casefold=False)
    except (ValueError, binascii.Error) as exc:
        raise MfaVerificationError('MFA factor is unavailable.') from exc
    # RFC 6238 TOTP uses keyed HMAC-SHA1; preserve compatibility with enrolled authenticators.
    # This is not SHA-1 for passwords or unkeyed digests.
    return TOTP(key, 6, hashes.SHA1(), 30)  # nosec B303


def _accepted_step(secret: str, code: str, *, last_accepted_step: int | None, now: datetime) -> int | None:
    if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdecimal():
        return None
    current_step = int(now.timestamp()) // 30
    verifier = _totp(secret)
    for step in (current_step - 1, current_step, current_step + 1):
        if step <= (last_accepted_step if last_accepted_step is not None else -1):
            continue
        try:
            verifier.verify(code.encode('ascii'), step * 30)
        except InvalidToken:
            continue
        return step
    return None


def _owns_pending_setup(factor: AuthenticationMfaFactor, generation: int, *, authenticated: bool) -> bool:
    return (
        not factor.enabled
        and type(generation) is int
        and generation > 0
        and factor.enrollment_generation == generation
        and factor.enrollment_authenticated is authenticated
    )


def has_owned_pending_setup(user_id: int, generation: int, *, authenticated: bool) -> bool:
    """Read only setup ownership, not the encrypted seed or recovery hashes."""
    return db.session.execute(
        select(AuthenticationMfaFactor.id).where(
            AuthenticationMfaFactor.user_id == user_id,
            AuthenticationMfaFactor.enabled.is_(False),
            AuthenticationMfaFactor.enrollment_generation == generation,
            AuthenticationMfaFactor.enrollment_authenticated.is_(authenticated),
        )
    ).scalar_one_or_none() is not None


def mfa_enrollment_state(
    factor: AuthenticationMfaFactor | None, *, now: datetime, expected_generation: int, authenticated: bool
) -> Literal['enrolled', 'pending', 'expired', 'not_enrolled']:
    """Project effective enrollment state, never infer a valid pending seed from a row alone."""
    if factor is None:
        return 'not_enrolled'
    if factor.enabled:
        return 'enrolled'
    if not _owns_pending_setup(factor, expected_generation, authenticated=authenticated):
        return 'expired'
    expires = factor.enrollment_expires_at
    if expires is None:
        return 'expired'
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return 'pending' if expires > now else 'expired'


def _lock_mfa_user(user: User, expected_generation: int, *, authenticated: bool) -> User:
    """Lock the presented generation before any factor mutation or proof consumption."""
    if type(expected_generation) is not int or expected_generation < 1:
        raise MfaVerificationError('Sign in again before changing MFA.')
    source = user.auth_source
    locked = db.session.execute(
        select(User)
        .where(
            User.id == user.id,
            User.auth_session_version == expected_generation,
            User.auth_source == source,
            User.account_is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .with_for_update(of=User)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if locked is None or session_admission_reason(locked, source=source) is not None:
        raise MfaVerificationError('Sign in again before changing MFA.')
    if authenticated:
        try:
            deadlines = session_deadlines(locked, read_session_policy(), datetime.now(UTC))
        except ValueError as exc:
            raise MfaVerificationError('Sign in again before changing MFA.') from exc
        if not isinstance(deadlines, SessionDeadlines):
            raise MfaVerificationError('Sign in again before changing MFA.')
    return locked


def has_recent_kaori_admission(user: User, *, now: datetime) -> bool:
    """Bound the age of committed admission, not the upstream credential age."""
    issued = user.auth_session_issued_at
    if issued is None:
        return False
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=UTC)
    age = now - issued
    return timedelta(0) <= age < MFA_RECENT_ADMISSION_TTL


def require_personal_factor_assurance(
    user: User, current_password: str | None, *, now: datetime, strict_primary: bool = False
) -> None:
    """Called only after locking the originally presented admitted user row.

    KAORI owns Local Database passwords. External sign-in recency does not
    prove upstream credential reauthentication; never promote it to strict
    primary assurance for authenticator replacement.
    """
    if user.auth_source == 'database':
        if (
            not current_password
            or len(current_password) > LOCAL_PASSWORD_MAX_LENGTH
            or not user.check_password(current_password)
        ):
            raise MfaVerificationError('Your current password was not accepted.')
        return
    if strict_primary:
        raise MfaVerificationError('Verified provider reauthentication is required.')
    if not has_recent_kaori_admission(user, now=now):
        raise MfaVerificationError('Recent sign-in required before changing MFA.')


def _locked_factor(user_id: int) -> AuthenticationMfaFactor | None:
    """Refresh the factor after locking, rather than using an earlier ORM snapshot."""
    return AuthenticationMfaFactor.query.filter_by(user_id=user_id).with_for_update().populate_existing().first()


def begin_mfa_enrollment(
    user: User,
    *,
    expected_generation: int,
    authenticated: bool = True,
    current_password: str | None = None,
) -> str:
    """Create an expiring encrypted factor under the authoritative account lock."""
    try:
        user = _lock_mfa_user(user, expected_generation, authenticated=authenticated)
        if authenticated:
            require_personal_factor_assurance(user, current_password, now=datetime.now(UTC))
        existing = _locked_factor(user.id)
        # A concurrent confirmation may have activated the factor since the caller read posture.
        if existing is not None and existing.enabled:
            raise MfaVerificationError('MFA is already enrolled.')
        secret = base64.b32encode(secrets.token_bytes(20)).decode('ascii')
        factor = existing if existing is not None else AuthenticationMfaFactor()
        if existing is None:
            factor.user_id = user.id
        factor.totp_secret = secret
        factor.enabled = False
        factor.last_accepted_step = None
        factor.recovery_hashes = []
        factor.enrollment_expires_at = datetime.now(UTC) + ENROLLMENT_TTL
        factor.enrollment_generation = expected_generation
        factor.enrollment_authenticated = authenticated
        if existing is None:
            db.session.add(factor)
        db.session.add(
            stage_authentication_security_event(
                user, action='mfa_enrollment_started', authenticated=authenticated, success=True
            )
        )
        db.session.commit()
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError):
        db.session.rollback()
        raise
    return secret


def confirm_mfa_enrollment(
    user: User, code: str, *, expected_generation: int, authenticated: bool = True
) -> list[str]:
    """Activate only after OTP proof under the original admitted generation."""
    try:
        user = _lock_mfa_user(user, expected_generation, authenticated=authenticated)
        factor = _locked_factor(user.id)
        now = datetime.now(UTC)
        if factor is None or factor.enabled or factor.enrollment_expires_at is None:
            raise MfaVerificationError('Start MFA enrollment again.')
        if not _owns_pending_setup(factor, expected_generation, authenticated=authenticated):
            raise MfaVerificationError('Start MFA enrollment again.')
        if mfa_enrollment_state(
            factor, now=now, expected_generation=expected_generation, authenticated=authenticated
        ) != 'pending':
            raise MfaVerificationError('MFA enrollment expired; start again.')
        accepted = _accepted_step(factor.totp_secret, code, last_accepted_step=None, now=now)
        if accepted is None:
            raise MfaVerificationError('Verification code was not accepted.')
        recovery = [secrets.token_hex(8).upper() for _ in range(8)]
        factor.recovery_hashes = [generate_password_hash(value) for value in recovery]
        factor.last_accepted_step = accepted
        factor.enabled = True
        factor.enrolled_at = now
        factor.enrollment_expires_at = None
        factor.enrollment_generation = None
        factor.enrollment_authenticated = None
        db.session.add(
            stage_authentication_security_event(
                user, action='mfa_enrollment_confirmed', authenticated=authenticated, success=True
            )
        )
        db.session.commit()
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError):
        db.session.rollback()
        raise
    return recovery


def cancel_mfa_enrollment(user: User, *, expected_generation: int, authenticated: bool = True) -> None:
    """Delete only an inactive setup owned by the presented context, with its audit."""
    try:
        user = _lock_mfa_user(user, expected_generation, authenticated=authenticated)
        factor = _locked_factor(user.id)
        if factor is None or not _owns_pending_setup(factor, expected_generation, authenticated=authenticated):
            raise MfaVerificationError('Start MFA enrollment again.')
        db.session.delete(factor)
        db.session.add(
            stage_authentication_security_event(
                user, action='mfa_enrollment_cancelled', authenticated=authenticated, success=True
            )
        )
        db.session.commit()
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError):
        db.session.rollback()
        raise


def _consume_factor_proof(user: User, factor: AuthenticationMfaFactor, submitted: str, *, authenticated: bool) -> str:
    """Stage one proof consumption and its audit in the caller-owned transaction."""
    if not isinstance(submitted, str) or not 6 <= len(submitted) <= 64:
        raise MfaVerificationError('Verification code was not accepted.')
    now = datetime.now(UTC)
    accepted = _accepted_step(factor.totp_secret, submitted, last_accepted_step=factor.last_accepted_step, now=now)
    kind = 'totp'
    if accepted is not None:
        factor.last_accepted_step = accepted
    else:
        kind = 'recovery'
        remaining: list[str] | None = None
        for index, stored_hash in enumerate(factor.recovery_hashes or []):
            if check_password_hash(stored_hash, submitted.upper()):
                remaining = [value for i, value in enumerate(factor.recovery_hashes) if i != index]
                break
        if remaining is None:
            raise MfaVerificationError('Verification code was not accepted.')
        factor.recovery_hashes = remaining
    db.session.add(
        stage_authentication_security_event(
            user, action='mfa_challenge_verified', authenticated=authenticated, success=True
        )
    )
    return kind


def verify_mfa_challenge(
    user: User, submitted: str, *, expected_generation: int, authenticated: bool = False
) -> str:
    """Consume one factor proof under the presented generation and factor locks."""
    try:
        user = _lock_mfa_user(user, expected_generation, authenticated=authenticated)
        factor = _locked_factor(user.id)
        if factor is None or not factor.enabled:
            raise MfaVerificationError('MFA enrollment is unavailable.')
        kind = _consume_factor_proof(user, factor, submitted, authenticated=authenticated)
        db.session.commit()
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError):
        db.session.rollback()
        raise
    return kind


def _clear_replacement(factor: AuthenticationMfaFactor) -> None:
    factor.replacement_totp_secret = None
    factor.replacement_generation = None
    factor.replacement_expires_at = None


def mfa_replacement_state(
    factor: AuthenticationMfaFactor | None, *, generation: int, now: datetime
) -> Literal['not_started', 'pending', 'expired']:
    """Read replacement ownership and expiry without loading the encrypted seed."""
    if factor is None or not factor.enabled or factor.replacement_generation is None:
        return 'not_started'
    expires = factor.replacement_expires_at
    if factor.replacement_generation != generation or expires is None:
        return 'expired'
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return 'pending' if now < expires else 'expired'


def begin_mfa_replacement(user: User, submitted: str, *, expected_generation: int, current_password: str | None) -> str:
    """Verify current primary and active factor; never replace the active seed here."""
    try:
        user = _lock_mfa_user(user, expected_generation, authenticated=True)
        require_personal_factor_assurance(user, current_password, now=datetime.now(UTC), strict_primary=True)
        factor = _locked_factor(user.id)
        if factor is None or not factor.enabled:
            raise MfaVerificationError('MFA is not enrolled.')
        _consume_factor_proof(user, factor, submitted, authenticated=True)
        secret = base64.b32encode(secrets.token_bytes(20)).decode('ascii')
        factor.replacement_totp_secret = secret
        factor.replacement_generation = expected_generation
        factor.replacement_expires_at = datetime.now(UTC) + MFA_RECENT_ADMISSION_TTL
        db.session.add(
            stage_authentication_security_event(user, action='mfa_replacement_started', authenticated=True, success=True)
        )
        db.session.commit()
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError):
        db.session.rollback()
        raise
    return secret


def confirm_mfa_replacement(user: User, code: str, *, expected_generation: int) -> tuple[list[str], int]:
    """Swap the factor and recovery codes, revoke the prior generation and audit atomically."""
    try:
        user = _lock_mfa_user(user, expected_generation, authenticated=True)
        if user.auth_source != 'database':
            raise MfaVerificationError('Verified provider reauthentication is required.')
        factor = _locked_factor(user.id)
        now = datetime.now(UTC)
        if (
            factor is None
            or mfa_replacement_state(factor, generation=expected_generation, now=now) != 'pending'
            or not factor.replacement_totp_secret
        ):
            raise MfaVerificationError('Start authenticator replacement again.')
        replacement_secret = factor.replacement_totp_secret
        accepted = _accepted_step(replacement_secret, code, last_accepted_step=None, now=now)
        if accepted is None:
            raise MfaVerificationError('Verification code was not accepted.')
        codes = [secrets.token_hex(8).upper() for _ in range(8)]
        hashes = [generate_password_hash(value) for value in codes]
        # Slow proof/hash work must not outlive the original assurance or session deadline.
        now = datetime.now(UTC)
        if mfa_replacement_state(factor, generation=expected_generation, now=now) != 'pending':
            raise MfaVerificationError('Start authenticator replacement again.')
        if not isinstance(session_deadlines(user, read_session_policy(), now), SessionDeadlines):
            raise MfaVerificationError('Sign in again before changing MFA.')
        factor.totp_secret = replacement_secret
        factor.recovery_hashes = hashes
        factor.last_accepted_step = accepted
        factor.enrolled_at = now
        _clear_replacement(factor)
        issued_generation = expected_generation + 1
        user.auth_session_version = issued_generation
        db.session.add(
            stage_authentication_security_event(
                user, action='mfa_replacement_confirmed', authenticated=True, success=True
            )
        )
        db.session.commit()
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError):
        db.session.rollback()
        raise
    return codes, issued_generation


def cancel_mfa_replacement(user: User, *, expected_generation: int) -> None:
    """Discard only the caller's pending replacement; leave the active factor intact."""
    try:
        user = _lock_mfa_user(user, expected_generation, authenticated=True)
        factor = _locked_factor(user.id)
        if (
            user.auth_source != 'database'
            or factor is None
            or not factor.enabled
            or factor.replacement_generation != expected_generation
        ):
            raise MfaVerificationError('Start authenticator replacement again.')
        _clear_replacement(factor)
        db.session.add(
            stage_authentication_security_event(
                user, action='mfa_replacement_cancelled', authenticated=True, success=True
            )
        )
        db.session.commit()
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError):
        db.session.rollback()
        raise


def regenerate_mfa_recovery_codes(
    user: User, submitted: str, *, expected_generation: int, current_password: str | None = None
) -> list[str]:
    """Atomically consume the factor proof, replace recovery hashes and record both events."""
    try:
        user = _lock_mfa_user(user, expected_generation, authenticated=True)
        require_personal_factor_assurance(user, current_password, now=datetime.now(UTC))
        factor = _locked_factor(user.id)
        if factor is None or not factor.enabled:
            raise MfaVerificationError('MFA is not enrolled.')
        _consume_factor_proof(user, factor, submitted, authenticated=True)
        codes = [secrets.token_hex(8).upper() for _ in range(8)]
        factor.recovery_hashes = [generate_password_hash(value) for value in codes]
        if factor.replacement_generation is not None:
            _clear_replacement(factor)
            db.session.add(
                stage_authentication_security_event(
                    user, action='mfa_replacement_cancelled', authenticated=True, success=True
                )
            )
        db.session.add(
            stage_authentication_security_event(user, action='mfa_recovery_regenerated', authenticated=True, success=True)
        )
        db.session.commit()
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError):
        db.session.rollback()
        raise
    return codes
