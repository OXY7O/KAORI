from __future__ import annotations

from dataclasses import dataclass

from app.auth import services
from app.auth.providers.registry import CredentialProviderRegistry
from app.auth.results import AuthResult


@dataclass
class StubProvider:
    result: AuthResult
    calls: int = 0

    source = 'stub'

    def authenticate(self, username: str, password: str) -> AuthResult:
        assert username == 'operator'
        assert password == 'secret'
        self.calls += 1
        return self.result


def _registry(local: StubProvider, *external: StubProvider) -> CredentialProviderRegistry:
    return CredentialProviderRegistry(local=local, external=external)


def test_local_success_is_authoritative(monkeypatch) -> None:
    user = object()
    local = StubProvider(AuthResult(True, 'success', user=user))
    ldap = StubProvider(AuthResult(False, 'invalid_credentials', source='ldap'))
    monkeypatch.setattr(services, 'build_credential_provider_registry', lambda: _registry(local, ldap))

    result = services.authenticate('operator', 'secret')

    assert result.success is True
    assert result.user is user
    assert local.calls == 1
    assert ldap.calls == 0


def test_local_identity_with_wrong_password_does_not_fall_through(monkeypatch) -> None:
    user = object()
    local = StubProvider(AuthResult(False, 'invalid_credentials', user=user))
    ldap = StubProvider(AuthResult(True, 'success', source='ldap', user=object()))
    monkeypatch.setattr(services, 'build_credential_provider_registry', lambda: _registry(local, ldap))

    result = services.authenticate('operator', 'secret')

    assert result.user is user
    assert result.success is False
    assert ldap.calls == 0


def test_unknown_local_identity_can_authenticate_through_ldap(monkeypatch) -> None:
    ldap_user = object()
    local = StubProvider(AuthResult(False, 'invalid_credentials'))
    ldap = StubProvider(AuthResult(True, 'success', source='ldap', user=ldap_user))
    monkeypatch.setattr(services, 'build_credential_provider_registry', lambda: _registry(local, ldap))

    result = services.authenticate('operator', 'secret')

    assert result.success is True
    assert result.source == 'ldap'
    assert result.user is ldap_user


def test_database_unavailable_stops_external_fallback(monkeypatch) -> None:
    local = StubProvider(AuthResult(False, 'database_unavailable'))
    ldap = StubProvider(AuthResult(True, 'success', source='ldap', user=object()))
    monkeypatch.setattr(services, 'build_credential_provider_registry', lambda: _registry(local, ldap))

    result = services.authenticate('operator', 'secret')

    assert result.reason == 'database_unavailable'
    assert ldap.calls == 0


def test_provider_unavailable_is_returned_after_all_external_providers_fail(monkeypatch) -> None:
    local = StubProvider(AuthResult(False, 'invalid_credentials'))
    unavailable = StubProvider(AuthResult(False, 'provider_unavailable', source='ldap'))
    invalid = StubProvider(AuthResult(False, 'invalid_credentials', source='ldap'))
    monkeypatch.setattr(services, 'build_credential_provider_registry', lambda: _registry(local, unavailable, invalid))

    result = services.authenticate('operator', 'secret')

    assert result.reason == 'provider_unavailable'
