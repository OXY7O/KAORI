from __future__ import annotations

import re
from dataclasses import dataclass

from app.auth.providers.catalog import AuthProviderType, provider_definition
from app.auth.providers.ldap import LdapDirectoryClient
from app.auth.providers.registry import get_browser_sso_provider
from app.auth.sso import validate_jit_configuration
from app.models import IdentityProvider

_PROVIDER_KEY_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_-]{0,79}$')


@dataclass(frozen=True, slots=True)
class IdentityProviderConfiguration:
    provider_type: str
    key: str
    display_name: str
    enabled: bool
    jit_enabled: bool
    server_uri: str | None = None
    base_dn: str | None = None
    bind_dn: str | None = None
    bind_password_env: str | None = None
    user_filter: str | None = None
    tls_mode: str = 'ldaps'
    username_attribute: str = 'sAMAccountName'
    email_attribute: str = 'mail'
    display_name_attribute: str = 'displayName'
    stable_id_attribute: str = 'objectGUID'
    oidc_client_id: str | None = None
    oidc_client_secret_env: str | None = None
    default_role_id: int | None = None
    allowed_domains: str | None = None
    allowed_subjects: str | None = None


def normalize_provider_key(value: object) -> str:
    normalized = str(value or '').strip().lower()
    if not _PROVIDER_KEY_PATTERN.fullmatch(normalized):
        raise ValueError(
            'Provider key must start with a letter or number and contain only lowercase letters, numbers, hyphens, or underscores.'
        )
    return normalized


def apply_identity_provider_configuration(
    provider: IdentityProvider,
    configuration: IdentityProviderConfiguration,
) -> None:
    provider_type = str(configuration.provider_type or '').strip().lower()
    provider_definition(provider_type)
    is_ldap = provider_type == AuthProviderType.LDAP.value
    is_google = provider_type == AuthProviderType.GOOGLE_OIDC.value
    is_github = provider_type == AuthProviderType.GITHUB_OAUTH.value

    provider.key = normalize_provider_key(configuration.key)
    provider.display_name = str(configuration.display_name or '').strip()
    provider.provider_type = provider_type
    provider.enabled = bool(configuration.enabled)
    provider.jit_enabled = bool(configuration.jit_enabled) if not is_ldap else False

    provider.server_uri = _optional_text(configuration.server_uri) if is_ldap else None
    provider.base_dn = _optional_text(configuration.base_dn) if is_ldap else None
    provider.bind_dn = _optional_text(configuration.bind_dn) if is_ldap else None
    provider.bind_password_env = _optional_text(configuration.bind_password_env) if is_ldap else None
    provider.user_filter = _optional_text(configuration.user_filter) if is_ldap else None
    provider.tls_mode = str(configuration.tls_mode or 'ldaps') if is_ldap else 'ldaps'
    provider.username_attribute = _text_or_default(configuration.username_attribute, 'sAMAccountName')
    provider.email_attribute = _text_or_default(configuration.email_attribute, 'mail')
    provider.display_name_attribute = _text_or_default(configuration.display_name_attribute, 'displayName')
    provider.stable_id_attribute = _text_or_default(configuration.stable_id_attribute, 'objectGUID')

    provider.oidc_issuer = 'https://accounts.google.com' if is_google else None
    provider.oidc_client_id = _optional_text(configuration.oidc_client_id) if not is_ldap else None
    provider.oidc_client_secret_env = (
        _optional_text(configuration.oidc_client_secret_env) if not is_ldap else None
    )
    provider.default_role_id = configuration.default_role_id if provider.jit_enabled else None
    provider.allowed_domains = (
        _optional_text(configuration.allowed_domains) if is_google and provider.jit_enabled else None
    )
    provider.allowed_subjects = (
        _optional_text(configuration.allowed_subjects) if is_github and provider.jit_enabled else None
    )


def validate_identity_provider(provider: IdentityProvider) -> str:
    if provider.provider_type == AuthProviderType.LDAP.value:
        LdapDirectoryClient(provider).validate()
        return f'{provider.display_name} accepted an LDAP service connection.'

    adapter = get_browser_sso_provider(provider.provider_type)
    message = adapter.validate_configuration(provider)
    validate_jit_configuration(provider)
    return message


def _optional_text(value: object) -> str | None:
    normalized = str(value or '').strip()
    return normalized or None


def _text_or_default(value: object, default: str) -> str:
    return _optional_text(value) or default
