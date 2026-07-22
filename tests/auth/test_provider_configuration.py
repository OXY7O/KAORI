from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.auth.provider_configuration import (
    IdentityProviderConfiguration,
    apply_identity_provider_configuration,
    normalize_provider_key,
)


def _configuration(provider_type: str, *, jit_enabled: bool = False) -> IdentityProviderConfiguration:
    return IdentityProviderConfiguration(
        provider_type=provider_type,
        key=' Corporate-Login ',
        display_name=' Corporate Login ',
        enabled=True,
        jit_enabled=jit_enabled,
        server_uri='ldaps://directory.example.com',
        base_dn='DC=example,DC=com',
        bind_dn='CN=KAORI,DC=example,DC=com',
        bind_password_env='LDAP_BIND_PASSWORD',
        user_filter=None,
        tls_mode='ldaps',
        username_attribute='sAMAccountName',
        email_attribute='mail',
        display_name_attribute='displayName',
        stable_id_attribute='objectGUID',
        oidc_client_id='client-id',
        oidc_client_secret_env='CLIENT_SECRET',
        default_role_id=7,
        allowed_domains='example.com',
        allowed_subjects='operator',
    )


def test_ldap_configuration_clears_sso_only_fields() -> None:
    provider = SimpleNamespace()

    apply_identity_provider_configuration(provider, _configuration('ldap', jit_enabled=True))

    assert provider.key == 'corporate-login'
    assert provider.provider_type == 'ldap'
    assert provider.jit_enabled is False
    assert provider.server_uri == 'ldaps://directory.example.com'
    assert provider.oidc_client_id is None
    assert provider.default_role_id is None
    assert provider.allowed_domains is None
    assert provider.allowed_subjects is None


def test_google_configuration_clears_ldap_and_github_only_fields() -> None:
    provider = SimpleNamespace()

    apply_identity_provider_configuration(provider, _configuration('google_oidc', jit_enabled=True))

    assert provider.provider_type == 'google_oidc'
    assert provider.server_uri is None
    assert provider.bind_dn is None
    assert provider.oidc_issuer == 'https://accounts.google.com'
    assert provider.default_role_id == 7
    assert provider.allowed_domains == 'example.com'
    assert provider.allowed_subjects is None


def test_provider_key_is_canonical_and_url_safe() -> None:
    assert normalize_provider_key(' Corporate_Login-01 ') == 'corporate_login-01'
    with pytest.raises(ValueError, match='Provider key must start'):
        normalize_provider_key('corporate login')
    with pytest.raises(ValueError, match='Provider key must start'):
        normalize_provider_key('../provider')
