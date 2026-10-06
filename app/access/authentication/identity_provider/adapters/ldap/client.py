from __future__ import annotations

import base64
import os
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from flask import current_app, has_app_context
from ldap3 import ALL, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from app.access.authentication.identity_provider.directory import ExternalIdentity
from app.models import IdentityProvider


class ExternalProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LdapTransport:
    host: str
    port: int
    use_ssl: bool
    start_tls: bool


def resolve_ldap_transport(
    server_uri: str | None,
    tls_mode: str | None,
    *,
    allow_plaintext: bool = False,
) -> LdapTransport:
    uri = str(server_uri or '').strip()
    if not uri:
        raise ExternalProviderError('LDAP server URI is not configured.')

    parsed = urlparse(uri if '://' in uri else f'ldap://{uri}')
    if parsed.scheme not in {'ldap', 'ldaps'} or not parsed.hostname:
        raise ExternalProviderError('LDAP server URI must use ldap:// or ldaps:// and include a host.')
    if parsed.username is not None or parsed.password is not None:
        raise ExternalProviderError('LDAP server URI must not embed credentials.')
    if parsed.path not in {'', '/'} or parsed.params or parsed.query or parsed.fragment:
        raise ExternalProviderError('LDAP server URI must contain only the scheme, host, and optional port.')
    try:
        port = parsed.port
    except ValueError as exc:
        raise ExternalProviderError('LDAP server URI contains an invalid port.') from exc

    mode = str(tls_mode or 'ldaps').strip().lower()
    if mode not in {'ldaps', 'starttls', 'plain'}:
        raise ExternalProviderError('LDAP TLS mode must be ldaps, starttls, or plain.')
    if mode == 'ldaps' and parsed.scheme != 'ldaps':
        raise ExternalProviderError('LDAPS mode requires an ldaps:// server URI.')
    if mode in {'starttls', 'plain'} and parsed.scheme != 'ldap':
        raise ExternalProviderError(f'{mode.title()} mode requires an ldap:// server URI.')
    if mode == 'plain' and not allow_plaintext:
        raise ExternalProviderError('Plain LDAP transport is disabled by KAORI configuration.')

    use_ssl = mode == 'ldaps'
    return LdapTransport(
        host=parsed.hostname,
        port=port or (636 if use_ssl else 389),
        use_ssl=use_ssl,
        start_tls=mode == 'starttls',
    )


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
    def __init__(self, config: IdentityProvider, *, allow_plaintext: bool | None = None):
        if config.adapter_key != 'ldap':
            raise ExternalProviderError('Identity provider does not use the LDAP adapter.')
        self.provider = config
        self.config = dict(config.configuration_json or {})
        self.allow_plaintext = (
            bool(current_app.config.get('AUTH_LDAP_ALLOW_PLAINTEXT', False))
            if allow_plaintext is None and has_app_context()
            else bool(allow_plaintext)
        )
        self.transport = resolve_ldap_transport(
            self._text('server_uri'),
            self._text('tls_mode') or 'ldaps',
            allow_plaintext=self.allow_plaintext,
        )

    def _text(self, key: str, default: str | None = None) -> str | None:
        value = str(self.config.get(key) or default or '').strip()
        return value or None

    def _timeout_seconds(self) -> int:
        try:
            value = int(self.config.get('connect_timeout_seconds') or 5)
        except (TypeError, ValueError):
            value = 5
        return max(2, min(value, 30))

    def _server(self) -> Server:
        tls = Tls(validate=ssl.CERT_REQUIRED) if self.transport.use_ssl or self.transport.start_tls else None
        return Server(
            self.transport.host,
            port=self.transport.port,
            use_ssl=self.transport.use_ssl,
            tls=tls,
            get_info=ALL,
            connect_timeout=self._timeout_seconds(),
        )

    def _new_connection(self, *, user: str | None, password: str | None) -> Connection:
        return Connection(
            self._server(),
            user=user or None,
            password=password or None,
            auto_bind=False,
            receive_timeout=self._timeout_seconds(),
        )

    def _open_and_secure(self, connection: Connection) -> None:
        if not connection.open():
            raise ExternalProviderError('LDAP connection could not be opened.')
        if self.transport.start_tls and not connection.start_tls():
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
        secret_name = self._text('bind_password_env') or ''
        password = os.getenv(secret_name, '') if secret_name else ''
        bind_dn = self._text('bind_dn')
        if bind_dn and not password:
            raise ExternalProviderError(f'LDAP bind secret environment variable {secret_name or "<unset>"} is missing.')
        return self._bound_connection(user=bind_dn, password=password)

    def validate(self) -> None:
        connection = self._service_connection()
        connection.unbind()

    def search(self, query: str, *, limit: int = 20) -> list[ExternalIdentity]:
        normalized = query.strip()
        if len(normalized) < 2:
            return []
        escaped = escape_filter_chars(normalized)
        username_attribute = self._text('username_attribute', 'sAMAccountName') or 'sAMAccountName'
        email_attribute = self._text('email_attribute', 'mail') or 'mail'
        display_name_attribute = self._text('display_name_attribute', 'displayName') or 'displayName'
        stable_id_attribute = self._text('stable_id_attribute', 'objectGUID') or 'objectGUID'
        template = self._text('user_filter') or (
            '(|({username_attribute}=*{query}*)({email_attribute}=*{query}*)({display_name_attribute}=*{query}*))'
        )
        try:
            search_filter = template.format(
                query=escaped,
                username_attribute=username_attribute,
                email_attribute=email_attribute,
                display_name_attribute=display_name_attribute,
            )
        except (KeyError, ValueError) as exc:
            raise ExternalProviderError('LDAP user search filter contains unsupported placeholders.') from exc

        attributes = sorted({username_attribute, email_attribute, display_name_attribute, stable_id_attribute})
        connection = self._service_connection()
        try:
            ok = connection.search(
                search_base=self._text('base_dn') or '',
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes,
                size_limit=min(max(limit, 1), 50),
            )
            if not ok and connection.result.get('description') not in {'success', 'sizeLimitExceeded'}:
                raise ExternalProviderError('LDAP directory search failed.')
            identities: list[ExternalIdentity] = []
            for entry in connection.entries:
                username = _attribute_value(entry, username_attribute)
                if not username:
                    continue
                identities.append(
                    ExternalIdentity(
                        subject=_stable_subject(_attribute_value(entry, stable_id_attribute)),
                        username=str(username),
                        email=str(_attribute_value(entry, email_attribute) or '') or None,
                        display_name=str(_attribute_value(entry, display_name_attribute) or '') or None,
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
