"""Bounded secret-free maintenance of invalid pending MFA material (#5381)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import Delete, Update, delete, or_, select, update

from app.access.authentication.identity_provider.adapters.ldap.reauthentication import (
    LdapReauthenticationProof,
    ldap_binding_fingerprint,
)
from app.access.authentication.mfa.audit import stage_pending_mfa_cleanup_event
from app.access.authentication.mfa.service import MFA_RECENT_ADMISSION_TTL, mfa_replacement_supports_source
from app.extensions.db import db
from app.models import ExternalIdentityLink, IdentityProvider
from app.models.authentication_security import AuthenticationMfaFactor
from app.models.user import User

MAX_BATCH = 500


@dataclass(frozen=True)
class AccountMetadata:
    id: int
    generation: int
    source: str
    subject: str | None
    active: bool
    deleted_at: datetime | None


@dataclass(frozen=True)
class PendingMetadata:
    id: int
    user_id: int
    enabled: bool
    enrollment_generation: int | None
    enrollment_authenticated: bool | None
    enrollment_expires_at: datetime | None
    replacement_generation: int | None
    replacement_expires_at: datetime | None
    replacement_provider_proof: object
    replacement_seed_present: bool


CleanupKind = Literal['enrollment', 'replacement']


def _expired(deadline: datetime | None, now: datetime) -> bool:
    if deadline is None:
        return True
    return (deadline.replace(tzinfo=UTC) if deadline.tzinfo is None else deadline) <= now


def _generation_valid(generation: int | None, account: AccountMetadata) -> bool:
    return type(generation) is int and generation > 0 and generation == account.generation


def _provider_proof_valid(account: AccountMetadata, record: object, now: datetime) -> bool:
    if account.source == 'database':
        return record is None
    if account.source != 'ldap_directory':
        return False
    proof = LdapReauthenticationProof.from_record(record)
    if (
        proof is None
        or proof.subject != account.subject
        or not timedelta(0) <= now - proof.verified_at < MFA_RECENT_ADMISSION_TTL
    ):
        return False
    # A metadata-only read, never acquire provider/link locks after the user lock.
    # The confirmation path owns the authoritative provider-first fence.
    rows = db.session.execute(
        select(
            ExternalIdentityLink.id,
            ExternalIdentityLink.provider_id,
            ExternalIdentityLink.subject,
            ExternalIdentityLink.distinguished_name,
            IdentityProvider.authentication_revision,
            IdentityProvider.enabled,
            IdentityProvider.adapter_key,
        )
        .join(IdentityProvider, IdentityProvider.id == ExternalIdentityLink.provider_id)
        .where(ExternalIdentityLink.user_id == account.id, IdentityProvider.provider_key == 'ldap_directory')
        .limit(2)
    ).all()
    if len(rows) != 1:
        return False
    link_id, provider_id, subject, dn, revision, enabled, adapter = rows[0]
    return (
        enabled
        and adapter == 'ldap'
        and bool(dn)
        and link_id == proof.credential.link_id
        and provider_id == proof.credential.provider_id
        and revision == proof.credential.revision
        and subject == proof.subject
        and ldap_binding_fingerprint(subject, dn) == proof.binding_fingerprint
    )


def invalid_pending_material(
    account: AccountMetadata, factor: PendingMetadata, *, now: datetime
) -> tuple[CleanupKind, str] | None:
    """Classify only pending state; active factor attributes are not read."""
    if not factor.enabled:
        if not account.active or account.deleted_at is not None:
            return 'enrollment', 'account_inactive'
        if not _generation_valid(factor.enrollment_generation, account) or factor.enrollment_authenticated is None:
            return 'enrollment', 'invalid_owner'
        if _expired(factor.enrollment_expires_at, now):
            return 'enrollment', 'expired'
        return None
    if not any(
        (
            factor.replacement_seed_present,
            factor.replacement_generation is not None,
            factor.replacement_expires_at is not None,
            factor.replacement_provider_proof is not None,
        )
    ):
        return None
    if not account.active or account.deleted_at is not None:
        return 'replacement', 'account_inactive'
    if not factor.replacement_seed_present or not _generation_valid(factor.replacement_generation, account):
        return 'replacement', 'invalid_owner'
    if _expired(factor.replacement_expires_at, now):
        return 'replacement', 'expired'
    if not mfa_replacement_supports_source(account.source):
        return 'replacement', 'unsupported_source'
    if not _provider_proof_valid(account, factor.replacement_provider_proof, now):
        return 'replacement', 'invalid_provider_proof'
    return None


def _account_metadata(user_id: int, *, lock: bool) -> AccountMetadata | None:
    statement = select(
        User.id, User.auth_session_version, User.auth_source, User.external_id, User.account_is_active, User.deleted_at
    ).where(User.id == user_id)
    if lock:
        statement = statement.with_for_update(of=User, skip_locked=True)
    row = db.session.execute(statement).one_or_none()
    return AccountMetadata(*row) if row is not None else None


def _factor_metadata(factor_id: int, user_id: int, *, lock: bool) -> PendingMetadata | None:
    factor = AuthenticationMfaFactor
    statement = select(
        factor.id,
        factor.user_id,
        factor.enabled,
        factor.enrollment_generation,
        factor.enrollment_authenticated,
        factor.enrollment_expires_at,
        factor.replacement_generation,
        factor.replacement_expires_at,
        factor.replacement_provider_proof,
        factor.replacement_totp_secret.is_not(None),
    ).where(factor.id == factor_id, factor.user_id == user_id)
    if lock:
        statement = statement.with_for_update(of=factor, skip_locked=True)
    row = db.session.execute(statement).one_or_none()
    return PendingMetadata(*row) if row is not None else None


def _apply_cleanup(factor: PendingMetadata, kind: CleanupKind, *, now: datetime) -> None:
    model = AuthenticationMfaFactor
    statement: Delete | Update
    if kind == 'enrollment':
        statement = delete(model).where(model.id == factor.id, model.user_id == factor.user_id, model.enabled.is_(False))
    else:
        statement = (
            update(model)
            .where(model.id == factor.id, model.user_id == factor.user_id, model.enabled.is_(True))
            .values(
                replacement_totp_secret=None,
                replacement_generation=None,
                replacement_expires_at=None,
                replacement_provider_proof=None,
                updated_at=now,
            )
        )
    removed = db.session.execute(
        statement.returning(model.id).execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    if removed != factor.id:
        raise RuntimeError('Pending MFA cleanup lost its locked target.')


def cleanup_pending_mfa(*, execute: bool = False, limit: int = 100, after_id: int = 0) -> dict[str, int | bool | None]:
    """Own a bounded transaction; call from a dedicated maintenance context."""
    if type(limit) is not int or not 1 <= limit <= MAX_BATCH or type(after_id) is not int or after_id < 0:
        raise ValueError('Invalid maintenance page boundary.')
    model = AuthenticationMfaFactor
    try:
        candidates = db.session.execute(
            select(model.id, model.user_id)
            .where(
                model.id > after_id,
                or_(
                    model.enabled.is_(False),
                    model.replacement_totp_secret.is_not(None),
                    model.replacement_generation.is_not(None),
                    model.replacement_expires_at.is_not(None),
                    model.replacement_provider_proof.is_not(None),
                ),
            )
            .order_by(model.id.asc())
            .limit(limit + 1)
        ).all()
        result: dict[str, int | bool | None] = {
            'execute': execute,
            'examined': 0,
            'eligible_enrollment': 0,
            'eligible_replacement': 0,
            'removed_enrollment': 0,
            'cleared_replacement': 0,
            'skipped_or_missing': 0,
            'next_after_id': int(candidates[limit - 1][0]) if len(candidates) > limit else None,
        }
        examined = skipped = enrollment = replacement = removed = cleared = 0
        for factor_id, user_id in candidates[:limit]:
            examined += 1
            # Same account -> factor lock order as interactive MFA. A contended
            # or concurrently deleted candidate is revisited on a later pass.
            account = _account_metadata(user_id, lock=execute)
            factor = _factor_metadata(factor_id, user_id, lock=execute) if account is not None else None
            if account is None or factor is None:
                skipped += 1
                continue
            # Evaluate after acquiring locks: a replacement started after the
            # page selection must not look like a future-dated proof.
            now = datetime.now(UTC)
            decision = invalid_pending_material(account, factor, now=now)
            if decision is None:
                continue
            kind, reason = decision
            if kind == 'enrollment':
                enrollment += 1
            else:
                replacement += 1
            if execute:
                _apply_cleanup(factor, kind, now=now)
                db.session.add(
                    stage_pending_mfa_cleanup_event(
                        user_id=user_id, factor_id=factor_id, kind=kind, reason=reason, now=now
                    )
                )
                if kind == 'enrollment':
                    removed += 1
                else:
                    cleared += 1
        result.update(
            examined=examined,
            eligible_enrollment=enrollment,
            eligible_replacement=replacement,
            removed_enrollment=removed,
            cleared_replacement=cleared,
            skipped_or_missing=skipped,
        )
        if execute:
            db.session.commit()
        else:
            db.session.rollback()
        return result
    except Exception:
        db.session.rollback()
        raise
