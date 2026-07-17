from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import ExternalIdentityLink, IdentityProvider, Role, User
from app.users.providers import ExternalIdentity


class IdentityProjectionError(RuntimeError):
    pass


def enabled_ldap_providers() -> list[IdentityProvider]:
    return (
        IdentityProvider.query
        .filter_by(provider_type='ldap', enabled=True)
        .order_by(IdentityProvider.display_name.asc())
        .all()
    )


def assign_provider_choices(form) -> None:
    form.provider_id.choices = [(provider.id, provider.display_name) for provider in enabled_ldap_providers()]


def assign_projection_role_choices(form, *, include_admin_roles: bool) -> None:
    query = Role.query.filter_by(is_active=True)
    if not include_admin_roles:
        query = query.filter(Role.name != 'admin')
    form.role_id.choices = [(role.id, role.display_name) for role in query.order_by(Role.display_name.asc()).all()]


def provision_external_identity(
    *,
    provider: IdentityProvider,
    identity: ExternalIdentity,
    role_id: int,
    is_active: bool,
) -> User:
    existing_link = ExternalIdentityLink.query.filter_by(provider_id=provider.id, subject=identity.subject).first()
    if existing_link is not None:
        raise IdentityProjectionError('This external identity is already provisioned in KAORI.')

    role = db.session.get(Role, role_id)
    if role is None or not role.is_active:
        raise IdentityProjectionError('The selected role is unavailable.')

    existing_user = User.query.filter(
        User.deleted_at.is_(None),
        (User.username == identity.username) | (User.email == (identity.email or '').lower()),
    ).first()
    if existing_user is not None:
        raise IdentityProjectionError('A KAORI user already uses this username or email.')

    user = User(
        username=identity.username,
        email=(identity.email or f'{identity.username}@external.invalid').lower(),
        display_name=identity.display_name,
        auth_source='ldap',
        external_id=identity.subject,
        role_id=role.id,
        role=role.name,
        account_is_active=is_active,
        is_super_admin=False,
        password_hash='',
    )
    db.session.add(user)
    db.session.flush()
    db.session.add(ExternalIdentityLink(
        user_id=user.id,
        provider_id=provider.id,
        subject=identity.subject,
        external_username=identity.username,
        distinguished_name=identity.distinguished_name,
        email=identity.email,
        display_name=identity.display_name,
        projection_type='administrative',
        last_synced_at=datetime.now(UTC),
    ))
    try:
        db.session.flush()
    except IntegrityError as exc:
        raise IdentityProjectionError('The external identity could not be projected because it conflicts with existing data.') from exc
    return user
