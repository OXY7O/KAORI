from __future__ import annotations

import pytest

from app.auth.providers.catalog import (
    AuthProviderFamily,
    AuthProviderType,
    browser_sso_provider_types,
    configurable_provider_choices,
    provider_definition,
    provider_family,
    provider_types_for_family,
)


def test_provider_catalog_exposes_three_primary_families() -> None:
    assert provider_family(AuthProviderType.DATABASE) == AuthProviderFamily.DATABASE
    assert provider_family(AuthProviderType.LDAP) == AuthProviderFamily.LDAP
    assert provider_family(AuthProviderType.GOOGLE_OIDC) == AuthProviderFamily.SSO
    assert provider_family(AuthProviderType.GITHUB_OAUTH) == AuthProviderFamily.SSO


def test_sso_family_resolves_concrete_provider_types() -> None:
    assert provider_types_for_family(AuthProviderFamily.SSO) == ('google_oidc', 'github_oauth')
    assert browser_sso_provider_types() == ('google_oidc', 'github_oauth')


def test_only_external_provider_types_are_configurable() -> None:
    assert configurable_provider_choices() == [
        ('ldap', 'LDAP / Active Directory'),
        ('google_oidc', 'Google OpenID Connect'),
        ('github_oauth', 'GitHub OAuth'),
    ]


def test_unknown_provider_definition_is_rejected() -> None:
    with pytest.raises(ValueError, match='Unsupported authentication provider type'):
        provider_definition('unknown')
    with pytest.raises(ValueError, match='Unsupported authentication provider type'):
        provider_family('unknown')
