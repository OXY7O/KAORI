from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.auth.identity_provider.catalog import AuthFlow, AuthProviderFamily, provider_definition
from app.auth.identity_provider.registry import get_browser_sso_adapter, get_directory_provider_adapter
from app.auth.sso import validate_jit_configuration
from app.models import IdentityProvider

_PROVIDER_KEY_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_-]{0,79}$')


@dataclass(frozen=True, slots=True)
class IdentityProviderConfiguration:
    provider_key: str
    key: str
    display_name: str
    enabled: bool
    jit_enabled: bool
    default_role_id: int | None
    configuration: dict[str, Any]
    admission_policy: dict[str, Any]


def normalize_instance_key(value: object) -> str:
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
    definition = provider_definition(configuration.provider_key)
    provider.key = normalize_instance_key(configuration.key)
    provider.display_name = str(configuration.display_name or '').strip()
    provider.provider_key = definition.provider_key
    provider.adapter_key = definition.adapter_key
    provider.enabled = bool(configuration.enabled)
    provider.jit_enabled = bool(configuration.jit_enabled) if definition.supports_jit else False
    provider.default_role_id = configuration.default_role_id if provider.jit_enabled else None
    provider.configuration_json = dict(configuration.configuration or {})
    provider.admission_policy_json = dict(configuration.admission_policy or {}) if provider.jit_enabled else {}


def identity_provider_configuration_complete(provider: IdentityProvider) -> bool:
    """Return whether required non-secret configuration references are present for the selected adapter profile."""

    definition = provider_definition(provider.provider_key)
    config = provider.configuration_json or {}
    if definition.configuration_profile == 'ldap':
        required = ('server_uri', 'base_dn', 'bind_dn', 'bind_password_env')
        return all(str(config.get(key) or '').strip() for key in required)
    if definition.configuration_profile == 'browser_client':
        required = ('client_id', 'client_secret_env')
        return all(str(config.get(key) or '').strip() for key in required)
    return False


def validate_identity_provider(provider: IdentityProvider) -> str:
    definition = provider_definition(provider.provider_key)
    if definition.family == AuthProviderFamily.DIRECTORY:
        return get_directory_provider_adapter(provider.adapter_key).validate_configuration(provider)
    if definition.flow == AuthFlow.BROWSER:
        adapter = get_browser_sso_adapter(provider.adapter_key)
        message = adapter.validate_configuration(provider)
        validate_jit_configuration(provider)
        return message
    raise ValueError(
        f'Identity provider {definition.provider_key!r} does not expose a configurable validation adapter.'
    )


def config_value(provider: IdentityProvider, key: str, default: Any = None) -> Any:
    return (provider.configuration_json or {}).get(key, default)


def config_text(provider: IdentityProvider, key: str) -> str | None:
    value = config_value(provider, key)
    normalized = str(value or '').strip()
    return normalized or None
