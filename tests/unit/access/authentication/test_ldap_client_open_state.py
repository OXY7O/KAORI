"""Regression: ldap3.Connection.open() returns None on a successful open (#2917).

All cases exercise KAORI's actual LdapDirectoryClient control flow without
network access, credentials, provider mutation, or disabled TLS verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.access.authentication.identity_provider.adapters.ldap.client import (
    ExternalProviderError,
    LdapDirectoryClient,
    LdapTransport,
)


@dataclass
class _Connection:
    """Small synchronous ldap3 stand-in: open() returns None on success."""

    leave_closed: bool = False
    tls_ok: bool = True
    bind_ok: bool = True
    closed: bool = True
    calls: list[str] = field(default_factory=list)

    def open(self) -> None:
        self.calls.append('open')
        if not self.leave_closed:
            self.closed = False

    def start_tls(self) -> bool:
        self.calls.append('start_tls')
        return self.tls_ok

    def bind(self) -> bool:
        self.calls.append('bind')
        return self.bind_ok

    def unbind(self) -> None:
        self.calls.append('unbind')
        self.closed = True


def _client(monkeypatch: pytest.MonkeyPatch, connection: _Connection, *, start_tls: bool) -> LdapDirectoryClient:
    client = object.__new__(LdapDirectoryClient)
    client.transport = LdapTransport(
        host='adds.kaori.cloud',
        port=389 if start_tls else 636,
        use_ssl=not start_tls,
        start_tls=start_tls,
    )
    monkeypatch.setattr(client, '_new_connection', lambda *, user, password: connection)
    return client


def test_ldaps_open_without_boolean_return_reaches_service_bind(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    client = _client(monkeypatch, connection, start_tls=False)

    assert client._bound_connection(user='CN=svc-kaori,DC=kaori,DC=cloud', password='test-only') is connection
    assert connection.calls == ['open', 'bind']
    assert not connection.closed


def test_ldaps_open_without_boolean_return_reaches_user_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    client = _client(monkeypatch, connection, start_tls=False)

    assert client.authenticate('CN=KAORI UAT User,DC=kaori,DC=cloud', 'test-only')
    assert connection.calls == ['open', 'bind', 'unbind']


def test_closed_connection_fails_closed_before_bind(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection(leave_closed=True)
    client = _client(monkeypatch, connection, start_tls=False)

    with pytest.raises(ExternalProviderError, match='LDAP connection could not be opened'):
        client._bound_connection(user='CN=svc-kaori,DC=kaori,DC=cloud', password='test-only')
    assert connection.calls == ['open', 'unbind']


def test_starttls_succeeds_before_credentials_are_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection()
    client = _client(monkeypatch, connection, start_tls=True)

    assert client._bound_connection(user='CN=svc-kaori,DC=kaori,DC=cloud', password='test-only') is connection
    assert connection.calls == ['open', 'start_tls', 'bind']


def test_starttls_failure_fails_closed_without_bind(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection(tls_ok=False)
    client = _client(monkeypatch, connection, start_tls=True)

    with pytest.raises(ExternalProviderError, match='LDAP StartTLS negotiation failed'):
        client._bound_connection(user='CN=svc-kaori,DC=kaori,DC=cloud', password='test-only')
    assert connection.calls == ['open', 'start_tls', 'unbind']
