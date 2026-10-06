from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from app.access.authentication.identity_provider.catalog import AuthProviderFamily, provider_definition
from app.access.authentication.identity_provider.directory import ExternalIdentity
from app.access.rbac.policy import role_is_access_admin_level, role_is_delegable_by_actor
from app.access.rbac.service import assignable_roles_for_actor
from app.extensions.db import db
from app.models import ExternalIdentityLink, IdentityProvider, Role, User

if TYPE_CHECKING:
    from app.access.identity_providers.forms import ExternalIdentityProvisionForm, ExternalIdentitySearchForm


class IdentityProjectionError(RuntimeError):
    pass


def enabled_directory_providers() -> list[IdentityProvider]:
    providers = IdentityProvider.query.filter_by(enabled=True).order_by(IdentityProvider.display_name.asc()).all()
    return [
        provider
        for provider in providers
        if provider_definition(provider.provider_key).family == AuthProviderFamily.DIRECTORY
    ]


def assign_provider_choices(form: ExternalIdentitySearchForm) -> None:
    form.provider_id.choices = [(str(provider.id), provider.display_name) for provider in enabled_directory_providers()]


def assign_projection_role_choices(form: ExternalIdentityProvisionForm, *, actor: User) -> None:
    roles = assignable_roles_for_actor(actor)
    form.role_id.choices = [(str(role.id), role.display_name) for role in roles]


def provision_external_identity(
    *,
    actor: User,
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
    if not role_is_delegable_by_actor(actor, role):
        if role_is_access_admin_level(role):
            raise IdentityProjectionError(
                'Only a Local Database Super Admin can assign an administrator-level role during directory provisioning.'
            )
        raise IdentityProjectionError('The selected role exceeds your delegation boundary.')

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
    user.auth_source = provider.provider_key
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
