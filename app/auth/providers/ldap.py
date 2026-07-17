from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.auth.results import AuthResult
from app.extensions import db
from app.models import ExternalIdentityLink, User
from app.users.providers import ExternalProviderError, LdapDirectoryProvider


class LdapAuthProvider:
    source = 'ldap'

    def authenticate(self, username: str, password: str) -> AuthResult:
        user: User | None = None
        try:
            link = (
                ExternalIdentityLink.query.join(User, User.id == ExternalIdentityLink.user_id)
                .filter(
                    ExternalIdentityLink.external_username == username.strip(),
                    User.auth_source == 'ldap',
                    User.deleted_at.is_(None),
                )
                .first()
            )
            if link is None:
                return AuthResult(False, 'invalid_credentials', source=self.source)
            linked_user = link.user
            if not isinstance(linked_user, User):
                return AuthResult(False, 'invalid_credentials', source=self.source)
            user = linked_user

            provider = link.provider
            if provider is None or not provider.enabled:
                return AuthResult(False, 'invalid_credentials', source=self.source, user=user)
            if not user.is_active:
                return AuthResult(False, 'user_inactive', source=self.source, user=user)
            authenticated = LdapDirectoryProvider(provider).authenticate(link.distinguished_name or '', password)
            if not authenticated:
                return AuthResult(False, 'invalid_credentials', source=self.source, user=user)
            return AuthResult(True, 'success', source=self.source, user=user)
        except ExternalProviderError:
            return AuthResult(False, 'provider_unavailable', source=self.source, user=user)
        except SQLAlchemyError:
            db.session.rollback()
            return AuthResult(False, 'database_unavailable', source=self.source)
