from __future__ import annotations

import base64
import os
import ssl
from dataclasses import dataclass
from typing import Any

from ldap3 import ALL, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from app.models import IdentityProvider


class ExternalProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
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


class LdapDirectoryProvider:
    def __init__(self, config: IdentityProvider):
        if config.provider_type != 'ldap':
            raise ExternalProviderError('Identity provider is not an LDAP provider.')
        self.config = config

    def _server(self) -> Server:
        uri = (self.config.server_uri or '').strip()
        if not uri:
            raise ExternalProviderError('LDAP server URI is not configured.')

        tls_mode = (self.config.tls_mode or 'ldaps').lower()
        use_ssl = uri.lower().startswith('ldaps://') or tls_mode == 'ldaps'
        host = uri.split('://', 1)[-1]
        port = 636 if use_ssl else 389
        if ':' in host and not host.startswith('['):
            host, raw_port = host.rsplit(':', 1)
            if raw_port.isdigit():
                port = int(raw_port)

        tls = Tls(validate=ssl.CERT_REQUIRED) if tls_mode in {'ldaps', 'starttls'} or use_ssl else None
        return Server(
            host,
            port=port,
            use_ssl=use_ssl,
            tls=tls,
            get_info=ALL,
            connect_timeout=self.config.connect_timeout_seconds,
        )

    def _bound_connection(self, *, user: str | None, password: str | None) -> Connection:
        connection = Connection(
            self._server(),
            user=user or None,
            password=password or None,
            auto_bind=False,
            receive_timeout=self.config.connect_timeout_seconds,
        )
        try:
            if not connection.open():
                raise ExternalProviderError('LDAP connection could not be opened.')
            if self.config.tls_mode == 'starttls' and not connection.server.ssl:
                if not connection.start_tls():
                    raise ExternalProviderError('LDAP StartTLS negotiation failed.')
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
        search_filter = template.format(
            query=escaped,
            username_attribute=self.config.username_attribute,
            email_attribute=self.config.email_attribute,
            display_name_attribute=self.config.display_name_attribute,
        )
        attributes = list(
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
        try:
            connection = self._bound_connection(user=distinguished_name, password=password)
            connection.unbind()
            return True
        except ExternalProviderError:
            return False
