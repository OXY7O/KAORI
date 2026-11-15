"""Regression: ldap3.Connection.open() returns None on a successful open (#2917).

All cases exercise KAORI's actual LdapDirectoryClient control flow without
network access, credentials, provider mutation, or disabled TLS verification.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from app.access.authentication.identity_provider.adapters.ldap import client as ldap_client
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


def _transport_for_tls_test(*, start_tls: bool) -> LdapDirectoryClient:
    client = object.__new__(LdapDirectoryClient)
    client.transport = LdapTransport(
        host='adds.kaori.cloud',
        port=389 if start_tls else 636,
        use_ssl=not start_tls,
        start_tls=start_tls,
    )
    client.config = {'connect_timeout_seconds': 5}
    return client


@pytest.mark.parametrize('start_tls', [False, True])
def test_configured_ldap_ca_bundle_is_used_with_required_verification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, start_tls: bool
) -> None:
    # This is a wiring test; a real TLS certificate chain is verified during UAT.
    bundle = tmp_path / 'ca.pem'
    bundle.write_text('test-only CA fixture, never a real certificate', encoding='utf-8')
    monkeypatch.setenv('KAORI_LDAP_CA_BUNDLE', str(bundle))
    monkeypatch.setattr(ldap_client, 'Tls', lambda **options: options)
    monkeypatch.setattr(ldap_client, 'Server', lambda host, **options: {'host': host, **options})

    server = _transport_for_tls_test(start_tls=start_tls)._server()

    assert server['host'] == 'adds.kaori.cloud'
    assert server['use_ssl'] is not start_tls
    assert server['tls']['validate'] == ssl.CERT_REQUIRED
    assert server['tls']['ca_certs_file'] == str(bundle)


def test_no_ldap_ca_override_preserves_system_trust(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('KAORI_LDAP_CA_BUNDLE', raising=False)
    monkeypatch.setattr(ldap_client, 'Tls', lambda **options: options)
    monkeypatch.setattr(ldap_client, 'Server', lambda host, **options: {'host': host, **options})

    server = _transport_for_tls_test(start_tls=False)._server()

    assert server['tls']['validate'] == ssl.CERT_REQUIRED
    assert server['tls']['ca_certs_file'] is None


@pytest.mark.parametrize('invalid_path', ['relative-ca.pem', '/nonexistent/kaori/ldap/ca.pem'])
def test_invalid_configured_ldap_ca_fails_closed_without_network(
    monkeypatch: pytest.MonkeyPatch, invalid_path: str
) -> None:
    monkeypatch.setenv('KAORI_LDAP_CA_BUNDLE', invalid_path)

    with pytest.raises(ExternalProviderError, match='LDAP CA bundle is unavailable or unreadable'):
        _transport_for_tls_test(start_tls=False)._server()
