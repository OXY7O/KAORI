from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from app.auth.providers.ldap import ExternalIdentity
from app.extensions.db import db
from app.models import ExternalIdentityLink, IdentityProvider, Role, User

if TYPE_CHECKING:
    from app.users.forms import ExternalIdentityProvisionForm, ExternalIdentitySearchForm


class IdentityProjectionError(RuntimeError):
    pass


def enabled_ldap_providers() -> list[IdentityProvider]:
    return (
        IdentityProvider.query.filter_by(provider_type='ldap', enabled=True)
        .order_by(IdentityProvider.display_name.asc())
        .all()
    )


def assign_provider_choices(form: ExternalIdentitySearchForm) -> None:
    form.provider_id.choices = [(str(provider.id), provider.display_name) for provider in enabled_ldap_providers()]


def assign_projection_role_choices(form: ExternalIdentityProvisionForm, *, include_admin_roles: bool) -> None:
    query = Role.query.filter_by(is_active=True)
    if not include_admin_roles:
        query = query.filter(Role.name != 'admin')
    form.role_id.choices = [(str(role.id), role.display_name) for role in query.order_by(Role.display_name.asc()).all()]


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

    user = User()
    user.username = identity.username
    user.email = (identity.email or f'{identity.username}@external.invalid').lower()
    user.display_name = identity.display_name
    user.auth_source = 'ldap'
    user.external_id = identity.subject
    user.role_id = role.id
    user.account_is_active = is_active
    user.is_super_admin = False
    user.password_hash = ''
    db.session.add(user)
    db.session.flush()

    identity_link = ExternalIdentityLink()
    identity_link.user_id = user.id
    identity_link.provider_id = provider.id
    identity_link.subject = identity.subject
    identity_link.external_username = identity.username
    identity_link.distinguished_name = identity.distinguished_name
    identity_link.email = identity.email
    identity_link.display_name = identity.display_name
    identity_link.projection_type = 'administrative'
    identity_link.last_synced_at = datetime.now(UTC)
    db.session.add(identity_link)
    try:
        db.session.flush()
    except IntegrityError as exc:
        raise IdentityProjectionError(
            'The external identity could not be projected because it conflicts with existing data.'
        ) from exc
    return user
