from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.auth.providers.ldap import ExternalProviderError, LdapDirectoryClient


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
