from __future__ import annotations

import base64
import os
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from ldap3 import ALL, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app.auth.providers.catalog import AuthProviderType
from app.auth.results import (
    DATABASE_UNAVAILABLE_MESSAGE,
    INVALID_LOGIN_MESSAGE,
    PROVIDER_UNAVAILABLE_MESSAGE,
    USER_INACTIVE_MESSAGE,
    AuthResult,
)
from app.extensions import db
from app.models import ExternalIdentityLink, IdentityProvider, User


class ExternalProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExternalIdentity:
    subject: str
    username: str
    email: str | None
    display_name: str | None
    distinguished_name: str


def _attribute_value(entry: Any, attribute: str) -> Any:
    value = getattr(entry, attribute, None)
    return value.value if value is not None else None


def _stable_subject(value: Any) -> str:
    if value is None:
        raise ExternalProviderError('LDAP result is missing the configured stable identity attribute.')
    if isinstance(value, bytes):
        return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')
    return str(value)


class LdapDirectoryClient:
    def __init__(self, config: IdentityProvider):
        if config.provider_type != AuthProviderType.LDAP.value:
            raise ExternalProviderError('Identity provider is not an LDAP provider.')
        self.config = config

    def _server(self) -> Server:
        uri = (self.config.server_uri or '').strip()
        if not uri:
            raise ExternalProviderError('LDAP server URI is not configured.')

        parsed = urlparse(uri if '://' in uri else f'ldap://{uri}')
        if parsed.scheme not in {'ldap', 'ldaps'} or not parsed.hostname:
            raise ExternalProviderError('LDAP server URI must use ldap:// or ldaps:// and include a host.')

        tls_mode = (self.config.tls_mode or 'ldaps').lower()
        use_ssl = parsed.scheme == 'ldaps' or tls_mode == 'ldaps'
        host = parsed.hostname
        port = parsed.port or (636 if use_ssl else 389)

        tls = Tls(validate=ssl.CERT_REQUIRED) if tls_mode in {'ldaps', 'starttls'} or use_ssl else None
        return Server(
            host,
            port=port,
            use_ssl=use_ssl,
            tls=tls,
            get_info=ALL,
            connect_timeout=self.config.connect_timeout_seconds,
        )

    def _new_connection(self, *, user: str | None, password: str | None) -> Connection:
        return Connection(
            self._server(),
            user=user or None,
            password=password or None,
            auto_bind=False,
            receive_timeout=self.config.connect_timeout_seconds,
        )

    def _open_and_secure(self, connection: Connection) -> None:
        if not connection.open():
            raise ExternalProviderError('LDAP connection could not be opened.')
        if self.config.tls_mode == 'starttls' and not connection.server.ssl and not connection.start_tls():
            raise ExternalProviderError('LDAP StartTLS negotiation failed.')

    def _bound_connection(self, *, user: str | None, password: str | None) -> Connection:
        connection = self._new_connection(user=user, password=password)
        try:
            self._open_and_secure(connection)
            if not connection.bind():
                raise ExternalProviderError('LDAP bind failed.')
            return connection
        except LDAPException as exc:
            connection.unbind()
            raise ExternalProviderError('LDAP connection or bind failed.') from exc
        except ExternalProviderError:
            connection.unbind()
            raise

    def _service_connection(self) -> Connection:
        secret_name = (self.config.bind_password_env or '').strip()
        password = os.getenv(secret_name, '') if secret_name else ''
        if self.config.bind_dn and not password:
            raise ExternalProviderError(f'LDAP bind secret environment variable {secret_name or "<unset>"} is missing.')
        return self._bound_connection(user=self.config.bind_dn, password=password)

    def validate(self) -> None:
        connection = self._service_connection()
        connection.unbind()

    def search(self, query: str, *, limit: int = 20) -> list[ExternalIdentity]:
        normalized = query.strip()
        if len(normalized) < 2:
            return []
        escaped = escape_filter_chars(normalized)
        template = self.config.user_filter or (
            '(|({username_attribute}=*{query}*)({email_attribute}=*{query}*)({display_name_attribute}=*{query}*))'
        )
        try:
            search_filter = template.format(
                query=escaped,
                username_attribute=self.config.username_attribute,
                email_attribute=self.config.email_attribute,
                display_name_attribute=self.config.display_name_attribute,
            )
        except (KeyError, ValueError) as exc:
            raise ExternalProviderError('LDAP user search filter contains unsupported placeholders.') from exc

        attributes = sorted(
            {
                self.config.username_attribute,
                self.config.email_attribute,
                self.config.display_name_attribute,
                self.config.stable_id_attribute,
            }
        )
        connection = self._service_connection()
        try:
            ok = connection.search(
                search_base=self.config.base_dn or '',
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes,
                size_limit=min(max(limit, 1), 50),
            )
            if not ok and connection.result.get('description') not in {'success', 'sizeLimitExceeded'}:
                raise ExternalProviderError('LDAP directory search failed.')
            identities: list[ExternalIdentity] = []
            for entry in connection.entries:
                username = _attribute_value(entry, self.config.username_attribute)
                if not username:
                    continue
                identities.append(
                    ExternalIdentity(
                        subject=_stable_subject(_attribute_value(entry, self.config.stable_id_attribute)),
                        username=str(username),
                        email=str(_attribute_value(entry, self.config.email_attribute) or '') or None,
                        display_name=str(_attribute_value(entry, self.config.display_name_attribute) or '') or None,
                        distinguished_name=str(entry.entry_dn),
                    )
                )
            return identities
        finally:
            connection.unbind()

    def authenticate(self, distinguished_name: str, password: str) -> bool:
        if not distinguished_name or not password:
            return False
        connection = self._new_connection(user=distinguished_name, password=password)
        try:
            self._open_and_secure(connection)
            if connection.bind():
                return True
            description = str(connection.result.get('description') or '')
            if description == 'invalidCredentials':
                return False
            raise ExternalProviderError('LDAP user bind failed because the provider is unavailable.')
        except LDAPException as exc:
            raise ExternalProviderError('LDAP connection or bind failed.') from exc
        finally:
            connection.unbind()


class LdapAuthProvider:
    source = AuthProviderType.LDAP.value

    def authenticate(self, username: str, password: str) -> AuthResult:
        normalized_username = username.strip()
        if not normalized_username or not password:
            return AuthResult(
                False,
                'invalid_credentials',
                source=self.source,
                message=INVALID_LOGIN_MESSAGE,
            )

        try:
            links = (
                ExternalIdentityLink.query.join(User, User.id == ExternalIdentityLink.user_id)
                .join(IdentityProvider, IdentityProvider.id == ExternalIdentityLink.provider_id)
                .filter(
                    func.lower(ExternalIdentityLink.external_username) == normalized_username.lower(),
                    User.auth_source == self.source,
                    User.deleted_at.is_(None),
                    IdentityProvider.provider_type == self.source,
                    IdentityProvider.enabled.is_(True),
                )
                .order_by(IdentityProvider.id.asc(), ExternalIdentityLink.id.asc())
                .all()
            )
        except SQLAlchemyError:
            db.session.rollback()
            return AuthResult(
                False,
                'database_unavailable',
                source=self.source,
                message=DATABASE_UNAVAILABLE_MESSAGE,
            )

        inactive_user: User | None = None
        active_link_seen = False
        provider_unavailable = False
        matched_user: User | None = None
        for link in links:
            user = link.user
            if not isinstance(user, User):
                continue
            matched_user = user
            if not user.is_active:
                inactive_user = inactive_user or user
                continue
            active_link_seen = True
            provider = link.provider
            if provider is None:
                continue
            try:
                authenticated = LdapDirectoryClient(provider).authenticate(
                    link.distinguished_name or '',
                    password,
                )
            except ExternalProviderError:
                provider_unavailable = True
                continue
            if authenticated:
                return AuthResult(True, 'success', source=self.source, user=user)

        if inactive_user is not None and not active_link_seen:
            return AuthResult(
                False,
                'user_inactive',
                source=self.source,
                user=inactive_user,
                message=USER_INACTIVE_MESSAGE,
            )
        if provider_unavailable:
            return AuthResult(
                False,
                'provider_unavailable',
                source=self.source,
                user=matched_user,
                message=PROVIDER_UNAVAILABLE_MESSAGE,
            )
        return AuthResult(
            False,
            'invalid_credentials',
            source=self.source,
            user=matched_user,
            message=INVALID_LOGIN_MESSAGE,
        )
