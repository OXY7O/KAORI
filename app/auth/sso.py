from __future__ import annotations

import os
import re
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.auth.providers.browser import SsoIdentity
from app.auth.providers.catalog import AuthProviderType
from app.auth.providers.registry import registered_browser_sso_provider_types
from app.auth.results import DATABASE_UNAVAILABLE_MESSAGE, USER_INACTIVE_MESSAGE, AuthResult
from app.extensions import db
from app.models import ExternalIdentityLink, IdentityProvider, Role, User


class SsoAdmissionError(RuntimeError):
    pass


class SsoProviderStoreError(RuntimeError):
    pass


def find_enabled_sso_provider(provider_key: str) -> IdentityProvider | None:
    try:
        return (
            IdentityProvider.query.filter_by(key=provider_key.strip().lower(), enabled=True)
            .filter(IdentityProvider.provider_type.in_(registered_browser_sso_provider_types()))
            .first()
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise SsoProviderStoreError('The identity provider registry is temporarily unavailable.') from exc


def enabled_sso_providers() -> list[IdentityProvider]:
    try:
        providers = (
            IdentityProvider.query.filter(IdentityProvider.enabled.is_(True))
            .filter(IdentityProvider.provider_type.in_(registered_browser_sso_provider_types()))
            .order_by(IdentityProvider.display_name.asc())
            .all()
        )
    except SQLAlchemyError:
        # Authentication readiness is handled by the login route. Keep this helper
        # defensive so a missing or temporarily unavailable schema never causes a 500.
        db.session.rollback()
        return []

    return [
        provider
        for provider in providers
        if provider.oidc_client_id and provider.oidc_client_secret_env and os.getenv(provider.oidc_client_secret_env)
    ]


def resolve_sso_identity(provider: IdentityProvider, identity: SsoIdentity) -> AuthResult:
    try:
        link = ExternalIdentityLink.query.filter_by(provider_id=provider.id, subject=identity.subject).first()
    except SQLAlchemyError:
        db.session.rollback()
        return AuthResult(
            False,
            'database_unavailable',
            source=provider.provider_type,
            message=DATABASE_UNAVAILABLE_MESSAGE,
        )

    if link is not None:
        user = link.user
        if not user.is_active:
            return AuthResult(
                False,
                'user_inactive',
                source=provider.provider_type,
                user=user,
                message=USER_INACTIVE_MESSAGE,
            )
        try:
            _sync_link(link, identity)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            return AuthResult(
                False,
                'database_unavailable',
                source=provider.provider_type,
                user=user,
                message=DATABASE_UNAVAILABLE_MESSAGE,
            )
        return AuthResult(True, 'success', source=provider.provider_type, user=user)

    if not provider.jit_enabled:
        return AuthResult(
            False,
            'identity_not_provisioned',
            source=provider.provider_type,
            message='Your external identity is not provisioned for KAORI. Contact an administrator.',
        )

    try:
        user = _jit_project(provider, identity)
        db.session.commit()
    except SsoAdmissionError as exc:
        db.session.rollback()
        return AuthResult(False, 'identity_not_provisioned', source=provider.provider_type, message=str(exc))
    except IntegrityError:
        db.session.rollback()
        return AuthResult(
            False,
            'identity_not_provisioned',
            source=provider.provider_type,
            message='The external identity conflicts with an existing KAORI account.',
        )
    except SQLAlchemyError:
        db.session.rollback()
        return AuthResult(
            False,
            'database_unavailable',
            source=provider.provider_type,
            message=DATABASE_UNAVAILABLE_MESSAGE,
        )
    return AuthResult(True, 'success', source=provider.provider_type, user=user)


def validate_jit_configuration(provider: IdentityProvider) -> None:
    if not provider.jit_enabled:
        return
    role = db.session.get(Role, provider.default_role_id) if provider.default_role_id else None
    if role is None or not role.is_active or role.name == 'admin':
        raise SsoAdmissionError('JIT requires an active non-admin default role.')
    if provider.provider_type == AuthProviderType.GOOGLE_OIDC.value and not provider.allowed_domains_list:
        raise SsoAdmissionError('Google JIT requires at least one allowed email domain.')
    if provider.provider_type == AuthProviderType.GITHUB_OAUTH.value and not provider.allowed_subjects_list:
        raise SsoAdmissionError('GitHub JIT requires at least one allowed username or numeric user ID.')


def _jit_project(provider: IdentityProvider, identity: SsoIdentity) -> User:
    validate_jit_configuration(provider)
    _enforce_admission(provider, identity)
    role = db.session.get(Role, provider.default_role_id)
    if role is None:
        raise SsoAdmissionError('The configured default role is unavailable.')

    username = _unique_username(identity.username, provider)
    email = _jit_account_email(provider, identity)
    existing_email = User.query.filter(User.deleted_at.is_(None), User.email == email).first()
    if existing_email is not None:
        raise SsoAdmissionError('A KAORI account already uses this external email address.')

    user = User()
    user.username = username
    user.email = email.lower()
    user.display_name = identity.display_name
    user.auth_source = provider.provider_type
    user.external_id = identity.subject
    user.role_id = role.id
    user.account_is_active = True
    user.is_super_admin = False
    user.password_hash = ''
    db.session.add(user)
    db.session.flush()

    identity_link = ExternalIdentityLink()
    identity_link.user_id = user.id
    identity_link.provider_id = provider.id
    identity_link.subject = identity.subject
    identity_link.external_username = identity.username
    identity_link.email = identity.email
    identity_link.display_name = identity.display_name
    identity_link.projection_type = 'jit'
    identity_link.last_synced_at = datetime.now(UTC)
    db.session.add(identity_link)
    db.session.flush()
    return user


def _jit_account_email(provider: IdentityProvider, identity: SsoIdentity) -> str:
    if identity.email and identity.email_verified:
        return identity.email.strip().lower()
    return f'{provider.key}-{identity.subject}@external.invalid'.lower()


def _enforce_admission(provider: IdentityProvider, identity: SsoIdentity) -> None:
    if provider.provider_type == AuthProviderType.GOOGLE_OIDC.value:
        if not identity.email or not identity.email_verified:
            raise SsoAdmissionError('Google access requires a verified email address.')
        domain = identity.email.rsplit('@', 1)[-1].lower()
        if domain not in provider.allowed_domains_list:
            raise SsoAdmissionError('This Google account domain is not allowed to access KAORI.')
        return

    if provider.provider_type == AuthProviderType.GITHUB_OAUTH.value:
        allowed_subjects: list[str] = provider.allowed_subjects_list
        allowed = {item.strip().lower() for item in allowed_subjects if item.strip()}
        subject = str(identity.subject or '').strip().lower()
        username = str(identity.username or '').strip().lower()
        if subject not in allowed and username not in allowed:
            raise SsoAdmissionError('This GitHub account is not included in the KAORI admission allow-list.')
        return

    raise SsoAdmissionError('The provider does not support JIT admission.')


def _sync_link(link: ExternalIdentityLink, identity: SsoIdentity) -> None:
    link.external_username = identity.username
    link.email = identity.email
    link.display_name = identity.display_name
    link.last_synced_at = datetime.now(UTC)
    if identity.display_name:
        link.user.display_name = identity.display_name


def _unique_username(candidate: str, provider: IdentityProvider) -> str:
    base = re.sub(r'[^a-zA-Z0-9_.-]+', '-', candidate).strip('-.').lower() or provider.key
    base = base[:88]
    username = base
    counter = 1
    while User.query.filter(User.deleted_at.is_(None), User.username == username).first() is not None:
        counter += 1
        username = f'{base[: 88 - len(str(counter))]}-{counter}'
    return username
