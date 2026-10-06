from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.identity_provider.adapters.ldap.client import ExternalProviderError, LdapDirectoryClient
from app.access.authentication.results import (
    DATABASE_UNAVAILABLE_MESSAGE,
    INVALID_LOGIN_MESSAGE,
    PROVIDER_UNAVAILABLE_MESSAGE,
    USER_INACTIVE_MESSAGE,
    AuthResult,
)
from app.extensions.db import db
from app.models import ExternalIdentityLink, IdentityProvider, User


class LdapCredentialAdapter:
    adapter_key = 'ldap'

    def authenticate(self, username: str, password: str) -> AuthResult:
        normalized_username = username.strip()
        if not normalized_username or not password:
            return AuthResult(False, 'invalid_credentials', source='identity_provider', message=INVALID_LOGIN_MESSAGE)

        try:
            links = (
                ExternalIdentityLink.query.join(User, User.id == ExternalIdentityLink.user_id)
                .join(IdentityProvider, IdentityProvider.id == ExternalIdentityLink.provider_id)
                .filter(
                    func.lower(ExternalIdentityLink.external_username) == normalized_username.lower(),
                    User.auth_source == IdentityProvider.provider_key,
                    User.deleted_at.is_(None),
                    IdentityProvider.adapter_key == self.adapter_key,
                    IdentityProvider.enabled.is_(True),
                )
                .order_by(IdentityProvider.id.asc(), ExternalIdentityLink.id.asc())
                .all()
            )
        except SQLAlchemyError:
            db.session.rollback()
            return AuthResult(
                False, 'database_unavailable', source='identity_provider', message=DATABASE_UNAVAILABLE_MESSAGE
            )

        inactive_user: User | None = None
        active_link_seen = False
        provider_unavailable = False
        matched_user: User | None = None
        matched_source = 'identity_provider'
        for link in links:
            user = link.user
            if not isinstance(user, User):
                continue
            matched_user = user
            provider = link.provider
            if provider is None:
                continue
            matched_source = provider.provider_key
            if not user.is_active:
                inactive_user = inactive_user or user
                continue
            active_link_seen = True
            try:
                authenticated = LdapDirectoryClient(provider).authenticate(link.distinguished_name or '', password)
            except ExternalProviderError:
                provider_unavailable = True
                continue
            if authenticated:
                return AuthResult(True, 'success', source=provider.provider_key, user=user)

        if inactive_user is not None and not active_link_seen:
            return AuthResult(
                False, 'user_inactive', source=matched_source, user=inactive_user, message=USER_INACTIVE_MESSAGE
            )
        if provider_unavailable:
            return AuthResult(
                False,
                'provider_unavailable',
                source=matched_source,
                user=matched_user,
                message=PROVIDER_UNAVAILABLE_MESSAGE,
            )
        return AuthResult(
            False, 'invalid_credentials', source=matched_source, user=matched_user, message=INVALID_LOGIN_MESSAGE
        )
