"""Encrypted TOTP enrollment, one-use recovery and replay-resistant MFA checks.

RFC 6238 is implemented by cryptography's vetted TOTP primitive. KAORI never
reimplements OTP cryptography and never sends secrets to external QR endpoints.
"""

from __future__ import annotations

import base64
import binascii
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import Literal

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.twofactor import InvalidToken
from cryptography.hazmat.primitives.twofactor.totp import TOTP
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from app.access.authentication.admission import session_admission_reason
from app.access.authentication.audit import record_authentication_activity
from app.access.authentication.identity_provider.adapters.ldap.reauthentication import (
    LdapReauthenticationError,
    LdapReauthenticationProof,
    lock_ldap_reauthentication_proof,
    reauthenticate_ldap_account,
)
from app.access.authentication.identity_provider.proof import lock_external_credential_proof
from app.access.authentication.mfa.audit import stage_authentication_security_event
from app.access.authentication.mfa.policy import MfaGate, MfaPolicyDecision, MfaPolicyError, evaluate_mfa_policy
from app.access.authentication.password_policy import LOCAL_PASSWORD_MAX_LENGTH
from app.access.authentication.results import ExternalCredentialProof
from app.access.authentication.services import stage_successful_authentication
from app.access.authentication.session import AuthSessionError
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
    external_credential_proof: ExternalCredentialProof | None = None,
) -> str:
    """Create an expiring encrypted factor under the authoritative account lock."""
    try:
        if not authenticated and user.auth_source != 'database':
            lock_external_credential_proof(user.id, user.auth_source, external_credential_proof)
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
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError, AuthSessionError):
        db.session.rollback()
        raise
    return secret


def _stage_enrollment_confirmation(
    user: User,
    factor: AuthenticationMfaFactor | None,
    code: str,
    *,
    expected_generation: int,
    authenticated: bool,
) -> list[str]:
    """Stage activation and recovery issuance under locks; never commit independently."""
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
    return recovery


def confirm_mfa_enrollment(
    user: User, code: str, *, expected_generation: int, authenticated: bool = True
) -> list[str]:
    """Personal enrollment owns its own transaction; login uses staged activation."""
    try:
        if not authenticated:
            raise MfaVerificationError('Pending enrollment requires final session admission.')
        user = _lock_mfa_user(user, expected_generation, authenticated=True)
        factor = _locked_factor(user.id)
        recovery = _stage_enrollment_confirmation(
            user, factor, code, expected_generation=expected_generation, authenticated=True
        )
        db.session.commit()
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError):
        db.session.rollback()
        raise
    return recovery


def cancel_mfa_enrollment(
    user: User,
    *,
    expected_generation: int,
    authenticated: bool = True,
    external_credential_proof: ExternalCredentialProof | None = None,
) -> None:
    """Delete only an inactive setup owned by the presented context, with its audit."""
    try:
        if not authenticated and user.auth_source != 'database':
            lock_external_credential_proof(user.id, user.auth_source, external_credential_proof)
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
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError, AuthSessionError):
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


@dataclass(frozen=True)
class PendingMfaAdmission:
    generation: int
    session_reference: str
    remember_requested: bool
    recovery_codes: list[str] | None = field(default=None, repr=False)


def _pending_deadline_valid(expires_at: float) -> bool:
    return type(expires_at) in (int, float) and isfinite(expires_at) and datetime.now(UTC).timestamp() < expires_at


def complete_pending_mfa_login(
    user: User,
    submitted: str,
    *,
    source: str,
    expected_generation: int,
    expires_at: float,
    enrollment: bool,
    remember_requested: bool,
    client_ip: str | None,
    external_credential_proof: ExternalCredentialProof | None = None,
) -> PendingMfaAdmission:
    """Commit factor proof, exact-generation admission and login audit once.

    The route may establish a browser session only after this returns. The
    transaction records server admission, not delivery of an HTTP cookie.
    """
    try:
        if not _pending_deadline_valid(expires_at):
            raise MfaVerificationError('Pending authentication expired.')
        # Match provider administration's provider -> user -> factor lock order.
        if source != 'database':
            lock_external_credential_proof(user.id, source, external_credential_proof)
        user = _lock_mfa_user(user, expected_generation, authenticated=False)
        if user.auth_source != source:
            raise AuthSessionError('Pending authentication source changed.')
        factor = _locked_factor(user.id)
        # Re-evaluate the current policy and factor after acquiring account/factor locks.
        policy = db.session.get(AuthenticationSecurityPolicy, 1, populate_existing=True)
        decision = evaluate_mfa_policy(
            policy.mfa_mode if policy is not None else 'disabled',
            privileged=bool(user.is_admin_level),
            enrolled=bool(factor is not None and factor.enabled),
        )
        recovery = None
        if enrollment and decision.gate == MfaGate.ENROLLMENT_REQUIRED:
            recovery = _stage_enrollment_confirmation(
                user, factor, submitted, expected_generation=expected_generation, authenticated=False
            )
        elif not enrollment and decision.gate == MfaGate.CHALLENGE and factor is not None and factor.enabled:
            _consume_factor_proof(user, factor, submitted, authenticated=False)
        else:
            raise MfaVerificationError('MFA admission changed; sign in again.')
        if not _pending_deadline_valid(expires_at):
            raise MfaVerificationError('Pending authentication expired.')
        remember = bool(remember_requested and read_session_policy().regular_remember and not user.is_admin_level)
        reference = secrets.token_hex(16)
        generation = stage_successful_authentication(
            user,
            source=source,
            client_ip=client_ip,
            pending_generation=expected_generation,
            external_credential_proof=external_credential_proof,
        )
        record_authentication_activity(
            action='login',
            username=user.username,
            source=source,
            result='success',
            reason='success',
            user=user,
            commit=False,
            issued_session_reference=reference,
        )
        if not _pending_deadline_valid(expires_at):
            raise MfaVerificationError('Pending authentication expired.')
        db.session.commit()
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError, AuthSessionError, MfaPolicyError):
        db.session.rollback()
        raise
    return PendingMfaAdmission(generation, reference, remember, recovery)


def _clear_replacement(factor: AuthenticationMfaFactor) -> None:
    factor.replacement_totp_secret = None
    factor.replacement_generation = None
    factor.replacement_expires_at = None
    factor.replacement_provider_proof = None


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


def mfa_replacement_supports_source(source: str) -> bool:
    """Only sources with implemented strict primary proof may replace a factor.

    Browser account selection, consent, token issuance and KAORI session recency
    do not establish upstream reauthentication. New sources require explicit
    qualification, not a fallback to the ordinary browser sign-in adapter.
    """
    return source in {'database', 'ldap_directory'}


def _require_replacement_source(source: str) -> None:
    if not mfa_replacement_supports_source(source):
        raise MfaVerificationError('Verified provider reauthentication is required.')


def begin_mfa_replacement(user: User, submitted: str, *, expected_generation: int, current_password: str | None) -> str:
    """Verify current primary and active factor; never replace the active seed here."""
    try:
        source = user.auth_source
        _require_replacement_source(source)
        provider_proof = None
        if source == 'ldap_directory':
            # No remote bind while holding database row locks.
            if user.auth_session_version != expected_generation:
                raise MfaVerificationError('Sign in again before changing MFA.')
            provider_proof = reauthenticate_ldap_account(
                user.id, current_password, expected_subject=user.external_id
            )
            lock_ldap_reauthentication_proof(user.id, provider_proof)
        user = _lock_mfa_user(user, expected_generation, authenticated=True)
        if user.auth_source != source:
            raise MfaVerificationError('Sign in again before changing MFA.')
        if source == 'ldap_directory' and provider_proof is not None:
            if user.external_id != provider_proof.subject:
                raise MfaVerificationError('Verified provider reauthentication is required.')
            assurance_expires_at = provider_proof.verified_at + MFA_RECENT_ADMISSION_TTL
        else:
            require_personal_factor_assurance(user, current_password, now=datetime.now(UTC), strict_primary=True)
            assurance_expires_at = datetime.now(UTC) + MFA_RECENT_ADMISSION_TTL
        factor = _locked_factor(user.id)
        if factor is None or not factor.enabled:
            raise MfaVerificationError('MFA is not enrolled.')
        _consume_factor_proof(user, factor, submitted, authenticated=True)
        now = datetime.now(UTC)
        if (
            now >= assurance_expires_at
            or (provider_proof is not None and provider_proof.verified_at > now)
            or not isinstance(session_deadlines(user, read_session_policy(), now), SessionDeadlines)
        ):
            raise MfaVerificationError('Sign in again before changing MFA.')
        secret = base64.b32encode(secrets.token_bytes(20)).decode('ascii')
        factor.replacement_totp_secret = secret
        factor.replacement_generation = expected_generation
        factor.replacement_expires_at = assurance_expires_at
        factor.replacement_provider_proof = provider_proof.to_record() if provider_proof is not None else None
        db.session.add(
            stage_authentication_security_event(
                user,
                action='mfa_replacement_started',
                authenticated=True,
                success=True,
                primary_assurance='ldap_linked_user_bind' if provider_proof is not None else 'local_current_password',
                external_proof=provider_proof.credential if provider_proof is not None else None,
            )
        )
        db.session.commit()
    except (LdapReauthenticationError, AuthSessionError) as exc:
        db.session.rollback()
        raise MfaVerificationError('Verified provider reauthentication is required.') from exc
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError):
        db.session.rollback()
        raise
    return secret


def confirm_mfa_replacement(user: User, code: str, *, expected_generation: int) -> tuple[list[str], int]:
    """Swap the factor and recovery codes, revoke the prior generation and audit atomically."""
    try:
        source = user.auth_source
        _require_replacement_source(source)
        provider_proof = None
        if source == 'ldap_directory':
            record = db.session.execute(
                select(AuthenticationMfaFactor.replacement_provider_proof).where(
                    AuthenticationMfaFactor.user_id == user.id,
                    AuthenticationMfaFactor.replacement_generation == expected_generation,
                )
            ).scalar_one_or_none()
            provider_proof = LdapReauthenticationProof.from_record(record)
            if provider_proof is None:
                raise MfaVerificationError('Verified provider reauthentication is required.')
            lock_ldap_reauthentication_proof(user.id, provider_proof)
        user = _lock_mfa_user(user, expected_generation, authenticated=True)
        if user.auth_source != source or (provider_proof is not None and user.external_id != provider_proof.subject):
            raise MfaVerificationError('Verified provider reauthentication is required.')
        factor = _locked_factor(user.id)
        now = datetime.now(UTC)
        if (
            factor is None
            or mfa_replacement_state(factor, generation=expected_generation, now=now) != 'pending'
            or not factor.replacement_totp_secret
            or factor.replacement_provider_proof != (provider_proof.to_record() if provider_proof is not None else None)
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
        if mfa_replacement_state(factor, generation=expected_generation, now=now) != 'pending' or (
            provider_proof is not None
            and not provider_proof.verified_at <= now < provider_proof.verified_at + MFA_RECENT_ADMISSION_TTL
        ):
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
                user,
                action='mfa_replacement_confirmed',
                authenticated=True,
                success=True,
                primary_assurance='ldap_linked_user_bind' if provider_proof is not None else 'local_current_password',
                external_proof=provider_proof.credential if provider_proof is not None else None,
            )
        )
        db.session.commit()
    except (LdapReauthenticationError, AuthSessionError) as exc:
        db.session.rollback()
        raise MfaVerificationError('Verified provider reauthentication is required.') from exc
    except (SQLAlchemyError, CredentialEncryptionError, MfaVerificationError):
        db.session.rollback()
        raise
    return codes, issued_generation


def cancel_mfa_replacement(user: User, *, expected_generation: int) -> None:
    """Discard only the caller's pending replacement; leave the active factor intact."""
    try:
        _require_replacement_source(user.auth_source)
        user = _lock_mfa_user(user, expected_generation, authenticated=True)
        _require_replacement_source(user.auth_source)
        factor = _locked_factor(user.id)
        if (
            factor is None
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
