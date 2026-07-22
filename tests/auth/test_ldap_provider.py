from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.auth.providers.ldap import ExternalProviderError, LdapDirectoryClient, resolve_ldap_transport


class ConnectionStub:
    def __init__(
        self,
        *,
        opened: bool = True,
        bound: bool = True,
        description: str = 'success',
        tls_started: bool = True,
    ):
        self._opened = opened
        self._bound = bound
        self._tls_started = tls_started
        self.result = {'description': description}
        self.server = SimpleNamespace(ssl=False)
        self.unbound = False

    def open(self) -> bool:
        return self._opened

    def start_tls(self) -> bool:
        return self._tls_started

    def bind(self) -> bool:
        return self._bound

    def unbind(self) -> None:
        self.unbound = True


def _config(**overrides):
    values = {
        'provider_type': 'ldap',
        'server_uri': 'ldaps://directory.example.com:636',
        'tls_mode': 'ldaps',
        'connect_timeout_seconds': 5,
        'bind_password_env': None,
        'bind_dn': None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_invalid_directory_password_is_not_reported_as_provider_outage(monkeypatch) -> None:
    connection = ConnectionStub(bound=False, description='invalidCredentials')
    client = LdapDirectoryClient(_config())
    monkeypatch.setattr(client, '_new_connection', lambda **_kwargs: connection)

    assert client.authenticate('CN=Operator,DC=example,DC=com', 'wrong') is False
    assert connection.unbound is True


def test_operational_bind_failure_is_reported_as_provider_unavailable(monkeypatch) -> None:
    connection = ConnectionStub(bound=False, description='unavailable')
    client = LdapDirectoryClient(_config())
    monkeypatch.setattr(client, '_new_connection', lambda **_kwargs: connection)

    with pytest.raises(ExternalProviderError, match='provider is unavailable'):
        client.authenticate('CN=Operator,DC=example,DC=com', 'secret')


def test_starttls_failure_is_reported_as_provider_error(monkeypatch) -> None:
    connection = ConnectionStub(tls_started=False)
    client = LdapDirectoryClient(_config(server_uri='ldap://directory.example.com', tls_mode='starttls'))
    monkeypatch.setattr(client, '_new_connection', lambda **_kwargs: connection)

    with pytest.raises(ExternalProviderError, match='StartTLS'):
        client.authenticate('CN=Operator,DC=example,DC=com', 'secret')


def test_missing_credentials_are_rejected_without_network_access(monkeypatch) -> None:
    client = LdapDirectoryClient(_config())
    monkeypatch.setattr(
        client,
        '_new_connection',
        lambda **_kwargs: pytest.fail('network connection should not be created'),
    )

    assert client.authenticate('', 'secret') is False
    assert client.authenticate('CN=Operator', '') is False


def test_ldaps_transport_requires_matching_secure_uri() -> None:
    transport = resolve_ldap_transport('ldaps://directory.example.com', 'ldaps')

    assert transport.host == 'directory.example.com'
    assert transport.port == 636
    assert transport.use_ssl is True
    assert transport.start_tls is False

    with pytest.raises(ExternalProviderError, match='requires an ldaps://'):
        resolve_ldap_transport('ldap://directory.example.com', 'ldaps')


def test_starttls_transport_requires_ldap_uri() -> None:
    transport = resolve_ldap_transport('ldap://directory.example.com:1389', 'starttls')

    assert transport.port == 1389
    assert transport.use_ssl is False
    assert transport.start_tls is True

    with pytest.raises(ExternalProviderError, match='requires an ldap://'):
        resolve_ldap_transport('ldaps://directory.example.com', 'starttls')


def test_plain_ldap_is_fail_closed_unless_explicitly_enabled() -> None:
    with pytest.raises(ExternalProviderError, match='disabled by KAORI'):
        resolve_ldap_transport('ldap://directory.example.com', 'plain')

    transport = resolve_ldap_transport(
        'ldap://directory.example.com',
        'plain',
        allow_plaintext=True,
    )
    assert transport.use_ssl is False
    assert transport.start_tls is False

def test_ldap_transport_rejects_embedded_credentials_and_url_components() -> None:
    with pytest.raises(ExternalProviderError, match='must not embed credentials'):
        resolve_ldap_transport('ldaps://svc:secret@directory.example.com', 'ldaps')

    with pytest.raises(ExternalProviderError, match='only the scheme, host, and optional port'):
        resolve_ldap_transport('ldaps://directory.example.com/dc=example,dc=com', 'ldaps')


def test_ldap_transport_normalizes_invalid_port_as_configuration_error() -> None:
    with pytest.raises(ExternalProviderError, match='invalid port'):
        resolve_ldap_transport('ldaps://directory.example.com:not-a-port', 'ldaps')

